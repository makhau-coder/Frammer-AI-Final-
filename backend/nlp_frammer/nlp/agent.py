# nlp/agent.py
#
# FIXES applied in this version:
#   1. _get_llm_plain() max_output_tokens: 256 → 1024
#      Old value was too small for node_handle_empty_results which asks Gemini
#      to list ALL known entity values — responses were truncated mid-sentence.
#
#   2. Low-confidence fuzzy match cutoff: 0.2 → 0.35
#      A cutoff of 0.2 matched almost any word against any entity name,
#      generating false "ASK CONFIRMATION" prompts for unrelated words.
#
#   3. Windows path guard: now covers ALL drive letters (C:, D:, E:, ...)
#      The old guard only checked raw.startswith("C:") and silently failed
#      for projects on D:, E:, or any other drive letter.
#
#   4. run() now accepts thread_id parameter (default "main")
#      The old code hardcoded CONFIG = {"configurable": {"thread_id": "main"}}
#      at module level, so every user shared the same LangGraph memory thread.
#      Conversation history from one user would contaminate the next user's
#      query. Pass a unique thread_id (e.g. UUID) per user/session from chat.py.


import os
import re
import difflib
import logging
import duckdb
from typing import TypedDict, Annotated, cast
import operator


from dotenv import load_dotenv
load_dotenv()


from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver


from nlp.executor import execute
from nlp.synthesiser import synthesise
from nlp.prompt_builder import SYSTEM_PROMPT


logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────────────────────────────

GEMINI_MODEL = "gemini-2.5-flash"


def _get_llm() -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model=GEMINI_MODEL,
        google_api_key=os.environ.get("GEMINI_API_KEY", ""),
        temperature=0.0,
        max_output_tokens=8192,
    )


def _get_llm_plain() -> ChatGoogleGenerativeAI:
    """Plain LLM for short follow-up calls — no tools bound."""
    return ChatGoogleGenerativeAI(
        model=GEMINI_MODEL,
        google_api_key=os.environ.get("GEMINI_API_KEY", ""),
        temperature=0.0,
        max_output_tokens=1024,  # FIX: was 256, too small for entity listing
    )


# ──────────────────────────────────────────────────────────────────────
# STATE
# ──────────────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    messages:         Annotated[list[BaseMessage], operator.add]
    user_question:    str
    schema:           str
    retrieved_tables: list[str]
    generated_sql:    str
    sql_error:        str | None
    data:             list[dict]
    row_count:        int
    insight:          str | None
    needs_input:      bool
    cannot_answer:    bool
    final_message:    str


# ──────────────────────────────────────────────────────────────────────
# PROMPT FRAGMENTS
# ──────────────────────────────────────────────────────────────────────

CANNOT_ANSWER_RULES = """
If the question cannot be answered from the available schema, return:
CANNOT_ANSWER: <one sentence why> | <suggestion 1> | <suggestion 2> | <suggestion 3>
""".strip()


# ──────────────────────────────────────────────────────────────────────
# KNOWN ENTITY VALUES — loaded from DuckDB once at startup
# ──────────────────────────────────────────────────────────────────────

_KNOWN_ENTITIES: dict[str, list[str]] = {}


def _load_known_entities() -> dict[str, list[str]]:
    global _KNOWN_ENTITIES
    if _KNOWN_ENTITIES:
        return _KNOWN_ENTITIES

    # FIX: Guard covers ANY Windows drive letter (C:, D:, E:, ...) not just C:
    _fallback_db = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "..", "frammer_analytics.duckdb")
    )
    raw_path = os.environ.get("FRAMMER_DB_PATH", "").strip()
    if not raw_path:
        db_path = _fallback_db
    elif len(raw_path) >= 2 and raw_path[1] == ":" and raw_path[0].isalpha():
        logger.warning(
            f"[agent] FRAMMER_DB_PATH looks like a Windows path ({raw_path!r}). "
            f"Using fallback: {_fallback_db}"
        )
        db_path = _fallback_db
    else:
        db_path = os.path.normpath(raw_path)

    SOURCES = {
        "User":        ("combined_data2025_3_1_2026_2_28_by_user",       "User"),
        "Channel":     ("client_1_combined_data2025_3_1_2026_2_28",       "Channel"),
        "Input Type":  ("combined_data2025_3_1_2026_2_28_by_input_type",  "Input Type"),
        "Output Type": ("combined_data2025_3_1_2026_2_28_by_output_type", "Output Type"),
        "Language":    ("combined_data2025_3_1_2026_2_28_by_language",    "Language"),
        "Month":       ("monthly_chart",                                   "Month"),
    }

    try:
        conn = duckdb.connect(db_path, read_only=True)
        for label, (table, col) in SOURCES.items():
            rows = conn.execute(
                f'SELECT DISTINCT "{col}" FROM "{table}" '
                f'WHERE "{col}" IS NOT NULL ORDER BY "{col}"'
            ).fetchall()
            _KNOWN_ENTITIES[label] = [r[0] for r in rows]
        conn.close()
        logger.info(
            f"[agent] Known entities loaded: "
            f"{ {k: len(v) for k, v in _KNOWN_ENTITIES.items()} }"
        )
    except Exception as e:
        logger.error(f"[agent] Failed to load known entities: {e}")

    return _KNOWN_ENTITIES


def _format_entities() -> str:
    """Full entity list — used in node_handle_empty_results for precise diagnosis."""
    return "\n".join(
        f"  {label}: {', '.join(str(v) for v in vals)}"
        for label, vals in _load_known_entities().items()
    )


# ──────────────────────────────────────────────────────────────────────
# TOKEN NORMALIZERS
# These run BEFORE fuzzy matching so that natural language phrases like
# "February 2026" or "Hindi" are converted to their DB representations
# ("Feb, 2026", "hi") and picked up by the high-confidence pass.
# ──────────────────────────────────────────────────────────────────────

# Maps lowercase full/common month spellings → DB abbreviation
_MONTH_ALIASES: dict[str, str] = {
    "january":   "Jan",
    "february":  "Feb",
    "march":     "Mar",
    "april":     "Apr",
    "may":       "May",
    "june":      "Jun",
    "july":      "Jul",
    "august":    "Aug",
    "september": "Sep",
    "october":   "Oct",
    "november":  "Nov",
    "december":  "Dec",
}

# Maps lowercase full language names → DB language code
_LANGUAGE_ALIASES: dict[str, str] = {
    "english": "en",
    "hindi":   "hi",
    "spanish": "es",
    "arabic":  "ar",
    "marathi": "mr",
    "mixed":   "mix",
}


def _normalize_month_tokens(tokens: list[str]) -> list[str]:
    """
    Synthesises "Mon, YYYY" tokens from natural month mentions — with typo tolerance.

    Strategy:
      1. Exact lookup in _MONTH_ALIASES (e.g. "december" → "Dec")
      2. Fuzzy match against alias keys at cutoff=0.75 for typos

      If YEAR is present in query:
        → Build "Mon, YYYY" tokens via cross-product (existing behaviour)
           e.g. "february 2026" → "Feb, 2026"

      If NO YEAR in query:                           ← THIS IS THE FIX
        → Look up known Month entities from DB and
          find all entries whose prefix matches the resolved abbreviation.
          e.g. "december" → scans known Months → finds "Dec, 2025" → adds it.
          This fires SILENT CORRECT without asking the user for a year.
    """
    extra: list[str] = []
    years = [t for t in tokens if re.fullmatch(r"20\d{2}", t)]

    resolved_abbrevs: list[str] = []
    for token in tokens:
        if token in _MONTH_ALIASES:
            resolved_abbrevs.append(_MONTH_ALIASES[token])
        else:
            matches = difflib.get_close_matches(
                token,
                list(_MONTH_ALIASES.keys()),
                n=1,
                cutoff=0.75,
            )
            if matches:
                resolved_abbrevs.append(_MONTH_ALIASES[matches[0]])

    if years:
        # Original behaviour — explicit year present in query
        for abbrev in resolved_abbrevs:
            for year in years:
                db_token = f"{abbrev}, {year}"
                if db_token not in extra:
                    extra.append(db_token)
    else:
        # No year — resolve against known DB month values directly.
        # e.g. "december" → abbrev "Dec" → scans ["Mar, 2025", ..., "Dec, 2025", ...]
        #      → finds "Dec, 2025" → appends it as a high-confidence token.
        # If a month appears in two years (e.g. "Jan" could be "Jan, 2026" only),
        # all matches are added — Gemini picks the right one from context.
        known_months = _load_known_entities().get("Month", [])
        for abbrev in resolved_abbrevs:
            prefix = f"{abbrev},"          # e.g. "Dec,"
            for known in known_months:
                if known.startswith(prefix) and known not in extra:
                    extra.append(known)

    return tokens + extra



def _normalize_language_tokens(tokens: list[str]) -> list[str]:
    """
    Converts full language names → DB language codes — with typo tolerance.

    Strategy:
      1. Exact lookup in _LANGUAGE_ALIASES (e.g. "hindi" → "hi")
      2. Fuzzy match against alias keys at cutoff=0.80 for typos
         (e.g. "hindii", "hendi" → "hi")
         Higher cutoff than months because language codes are very short
         and false positives are more damaging (e.g. "mix" vs "hi").

    The DB code itself ("hi", "en") is appended as a new token so it
    hits the high-confidence pass in _format_entities_for_clarification
    and resolves silently without asking the user for confirmation.
    """
    extra: list[str] = []
    for token in tokens:
        if token in _LANGUAGE_ALIASES:
            code = _LANGUAGE_ALIASES[token]
            if code not in extra:
                extra.append(code)
        else:
            matches = difflib.get_close_matches(
                token,
                list(_LANGUAGE_ALIASES.keys()),
                n=1,
                cutoff=0.80,
            )
            if matches:
                code = _LANGUAGE_ALIASES[matches[0]]
                if code not in extra:
                    extra.append(code)
    return tokens + extra


# ──────────────────────────────────────────────────────────────────────
# ENTITY CLARIFICATION FORMATTER
# ──────────────────────────────────────────────────────────────────────

def _format_entities_for_clarification(user_question: str) -> str:
    entities = _load_known_entities()

    _STOPWORDS = {
        "a", "an", "the", "is", "are", "how", "give", "me", "show",
        "about", "for", "any", "info", "information", "user", "channel",
        "relevant", "and", "or", "can", "u", "his", "her", "their",
        "what", "which", "who", "get", "find", "list", "tell", "with",
        "all", "do", "did", "has", "have", "please", "want", "now",
    }

    raw_tokens = re.findall(r"[a-zA-Z0-9]+", user_question)
    tokens = [
        t.lower() for t in raw_tokens
        if len(t) >= 1 and t.lower() not in _STOPWORDS
    ]

     # ── CHANNEL LETTER RESCUE ─────────────────────────────────────────
    # Single letters like "a", "d" are valid channel names but get wiped
    # by stopwords ("a") or are too short to be meaningful alone.
    # If the user wrote "channel X" explicitly, always preserve X.

    channel_refs = re.findall(r'\bchannel\s+([a-zA-Z])\b', user_question, re.IGNORECASE)
    for ref in channel_refs:
        t = ref.lower()
        if t not in tokens:
            tokens.append(t)
            
    # Also catch "metrics for X", "info about X", "stats for X" when X is a single letter
    entity_refs = re.findall(
        r'\b(?:channel|for|about|of)\s+([a-zA-Z])\b',
        user_question,
        re.IGNORECASE
    )
    for ref in entity_refs:
        t = ref.lower()
        if t not in tokens:
            tokens.append(t)

    concat = re.sub(r"[^a-zA-Z0-9]", "", user_question).lower()
    if concat and concat not in tokens:
        tokens.append(concat)

    # ── Normalize months and languages BEFORE fuzzy matching ──────────
    # This converts "february" → "Feb, 2026" and "hindi" → "hi" so they
    # hit the high-confidence (≥0.80) pass and resolve silently.
    tokens = _normalize_month_tokens(tokens)
    tokens = _normalize_language_tokens(tokens)

    lines: list[str] = []
    for label, values in entities.items():
        values_lower: dict[str, str] = {
            str(v).lower(): str(v) for v in values
        }

        high_conf: list[str] = []   # similarity >= 0.80 — safe to correct silently
        low_conf:  list[str] = []   # similarity 0.35–0.79 — ask for confirmation

        for token in tokens:
            # High confidence pass
            for m in difflib.get_close_matches(token, list(values_lower.keys()), n=3, cutoff=0.80):
                v = values_lower.get(m, m)
                if v not in high_conf:
                    high_conf.append(v)

            # Low confidence pass
            for m in difflib.get_close_matches(token, list(values_lower.keys()), n=3, cutoff=0.35):  # FIX: was 0.2 (too aggressive)
                v = values_lower.get(m, m)
                if v not in high_conf and v not in low_conf:
                    low_conf.append(v)

        top_high: list[str] = high_conf[:3]
        top_low:  list[str] = low_conf[:3]

        if top_high:
            lines.append(
                f"  {label} (SILENT CORRECT — high confidence): {', '.join(top_high)}"
            )
        elif top_low:
            lines.append(
                f"  {label} (ASK CONFIRMATION — similar but not certain): {', '.join(top_low)}"
            )
        else:
            lines.append(
                f"  {label}: No match found — ask user to check spelling or "
                f"provide more characters. Do NOT list all {len(values)} values."
            )

    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────────────

def _clean_sql(raw: str) -> str:
    fenced = re.search(r"```(?:sql)?\s*(.*?)```", raw, re.DOTALL | re.IGNORECASE)
    if fenced:
        raw = fenced.group(1).strip()
    sql = raw.strip()
    if sql and not sql.endswith(";"):
        sql += ";"
    return sql


def _parse_cannot_answer(text: str) -> dict:
    parts = text.split("CANNOT_ANSWER:", 1)[-1].strip()
    return {
        "cannot_answer": True,
        "needs_input":   False,
        "generated_sql": "",
        "sql_error":     None,
        "final_message": parts,
    }


def _parse_clarify(text: str) -> dict:
    question = text.split("CLARIFY:", 1)[-1].strip()
    return {
        "needs_input":   True,
        "cannot_answer": False,
        "generated_sql": "",
        "sql_error":     None,
        "final_message": question,
    }


# ──────────────────────────────────────────────────────────────────────
# NODES
# ──────────────────────────────────────────────────────────────────────

def node_generate_sql(state: AgentState) -> dict:
    llm = _get_llm()

    system_text = (
        SYSTEM_PROMPT
        + "\n\n---\n\n"
        + "## Available Schema\n\n"
        + state["schema"]
        + "\n\n---\n\n"
        + CANNOT_ANSWER_RULES
    )

    messages: list[BaseMessage] = [SystemMessage(content=system_text)]

    all_msgs: list[BaseMessage] = state["messages"]  # type: ignore[assignment]
    history = all_msgs[:-1] if all_msgs else []
    recent_history = history[-4:] if len(history) > 4 else history
    messages.extend(recent_history)

    entity_reminder = f"""Before writing any SQL, check every name, month, channel,
or category the user mentioned against the KNOWN VALUES listed below.

KNOWN VALUES IN THE DATABASE (pre-matched to this query):
{_format_entities_for_clarification(state["user_question"])}

RULES — follow strictly in order:

1. SILENT CORRECT — high confidence match:
   The value is clearly a casing difference or minor typo of the known value.
   → Use the known value directly in the SQL.
   → Add one comment: -- Interpreted "chandan" as "Chandan"
   Example: "chandan" → "Chandan", "neh" → "Neha", "february 2026" → "Feb, 2026",
            "hindi" → "hi", "english" → "en"

2. ASK CONFIRMATION — similar but not certain match:
   The value resembles a known value but is not obviously the same name.
   → Do NOT write SQL yet.
   → Return: CLARIFY: I found a possible match for "<typed_value>": "<matched_value>".
     Did you mean "<matched_value>", or did you mean someone else?
   Example: "harry" → ask before assuming "Harish"
            "alice" → ask before assuming any similar name

3. No match found:
   → Do NOT write SQL.
   → Return: CLARIFY: I couldn't find a match for "<value>". Could you check
     the spelling or type the first few letters of the name you're looking for?

4. Question outside available data:
   → Return: CANNOT_ANSWER: <reason> | <suggestion 1> | <suggestion 2> | <suggestion 3>

Never use a raw user-typed string in a WHERE clause.
Never assume a name substitution without confirmation from the user."""

    messages.append(
        HumanMessage(
            content=f"{entity_reminder}\n\nUser question: {state['user_question']}"
        )
    )

    try:
        response = llm.invoke(messages)
        raw = str(response.content).strip()
        logger.debug(f"[agent] Raw Gemini response:\n{raw}")
    except Exception as e:
        logger.error(f"[agent] Gemini API call failed: {e}")
        return {
            "sql_error":     f"Gemini API error: {e}",
            "generated_sql": "",
            "final_message": f"SQL generation failed: {e}",
            "messages":      [AIMessage(content=f"Error: {e}")],
        }

    if raw.startswith("CLARIFY:"):
        result = _parse_clarify(raw)
        result["messages"] = [AIMessage(content=raw)]
        return result

    if raw.startswith("CANNOT_ANSWER"):
        result = _parse_cannot_answer(raw)
        result["messages"] = [AIMessage(content=raw)]
        return result

    sql = _clean_sql(raw)
    return {
        "generated_sql": sql,
        "sql_error":     None,
        "messages":      [AIMessage(content=sql)],
    }


def node_execute_sql(state: AgentState) -> dict:
    exec_result = execute(state["generated_sql"])

    if not exec_result.success:
        logger.error(f"[agent] Execution failed: {exec_result.error}")
        return {
            "sql_error":     exec_result.error,
            "data":          [],
            "row_count":     0,
            "final_message": f"SQL execution error: {exec_result.error}",
        }

    return {
        "data":      exec_result.data,
        "row_count": exec_result.row_count,
        "sql_error": None,
    }


def node_handle_empty_results(state: AgentState) -> dict:
    """
    Uses the FULL entity list (_format_entities) here intentionally —
    this node is diagnosing a WHERE clause mismatch and needs to
    compare exhaustively, not just against fuzzy token matches.
    """
    llm = _get_llm_plain()

    prompt_text = f"""A SQL query returned zero results.

SQL that was executed:
{state["generated_sql"]}

User question: "{state["user_question"]}"

KNOWN VALUES IN THE DATABASE:
{_format_entities()}

Compare every value in the WHERE clause of the SQL above against the
KNOWN VALUES. Identify which value is likely causing zero results.

Respond with EXACTLY one of these two formats — nothing else:

If an entity mismatch is likely:
CLARIFY: I couldn't find "<where_value>" in the dataset. The available <label> values are: <list ALL values for that label from KNOWN VALUES>

If the data genuinely does not exist in the dataset:
CANNOT_ANSWER: <reason> | <suggestion 1> | <suggestion 2> | <suggestion 3>"""

    try:
        response = llm.invoke([HumanMessage(content=prompt_text)])
        raw = str(response.content).strip()
        logger.debug(f"[agent] Empty-result handler response:\n{raw}")
    except Exception as e:
        logger.error(f"[agent] Empty-result Gemini call failed: {e}")
        return {
            "needs_input":   False,
            "cannot_answer": True,
            "final_message": "No results were found and I could not determine why. Please check the entity name and try again.",
        }

    if raw.startswith("CLARIFY:"):
        return {
            "needs_input":   True,
            "cannot_answer": False,
            "final_message": raw[len("CLARIFY:"):].strip(),
        }

    if raw.startswith("CANNOT_ANSWER:"):
        parts = raw[len("CANNOT_ANSWER:"):].strip().split("|")
        reason      = parts[0].strip()
        suggestions = [p.strip() for p in parts[1:]]
        msg = reason
        if suggestions:
            msg += "\n\nYou could try:\n" + "\n".join(
                f"  {i+1}) {s}" for i, s in enumerate(suggestions)
            )
        return {
            "needs_input":   False,
            "cannot_answer": True,
            "final_message": msg,
        }

    return {
        "needs_input":   True,
        "cannot_answer": False,
        "final_message": raw,
    }


def node_synthesise(state: AgentState) -> dict:
    result = synthesise(
        question=state["user_question"],
        sql=state["generated_sql"],
        tables=state["retrieved_tables"],
        data=state["data"],
    )

    insight   = result.insight if result.success else None
    final_msg = insight or "Results retrieved successfully."
    return {
        "insight":       insight,
        "final_message": final_msg,
        "messages":      [AIMessage(content=final_msg)],
    }


def node_format_cannot_answer(state: AgentState) -> dict:
    raw: str = str(state.get("final_message", ""))
    parts = [p.strip() for p in raw.split("|")]

    if len(parts) >= 2:
        reason      = parts[0]
        suggestions = parts[1:]
        numbered    = "\n".join(f"  {i}. {s}" for i, s in enumerate(suggestions, 1))
        message     = f"{reason}\n\nHere are some things you could ask instead:\n{numbered}"
    else:
        message = raw

    return {
        "final_message": message,
        "messages":      [AIMessage(content=message)],
    }


# ──────────────────────────────────────────────────────────────────────
# ROUTING
# ──────────────────────────────────────────────────────────────────────

def route_after_generation(state: AgentState) -> str:
    if state.get("needs_input"):
        return "needs_input"
    if state.get("cannot_answer"):
        return "cannot_answer"
    return "execute"


def route_after_execution(state: AgentState) -> str:
    if state.get("sql_error"):
        return "sql_error"
    if state.get("row_count", 0) == 0:
        return "empty_results"
    return "has_results"


def route_after_empty(state: AgentState) -> str:
    if state.get("needs_input"):
        return "needs_input"
    return "cannot_answer"


# ──────────────────────────────────────────────────────────────────────
# GRAPH ASSEMBLY
# ──────────────────────────────────────────────────────────────────────

def _build_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    graph.add_node("generate_sql",         node_generate_sql)
    graph.add_node("execute_sql",          node_execute_sql)
    graph.add_node("handle_empty_results", node_handle_empty_results)
    graph.add_node("synthesise",           node_synthesise)
    graph.add_node("format_cannot_answer", node_format_cannot_answer)

    graph.set_entry_point("generate_sql")

    graph.add_conditional_edges("generate_sql", route_after_generation, {
        "execute":       "execute_sql",
        "needs_input":   END,
        "cannot_answer": "format_cannot_answer",
    })

    graph.add_conditional_edges("execute_sql", route_after_execution, {
        "has_results":   "synthesise",
        "empty_results": "handle_empty_results",
        "sql_error":     END,
    })

    graph.add_conditional_edges("handle_empty_results", route_after_empty, {
        "needs_input":   END,
        "cannot_answer": "format_cannot_answer",
    })

    graph.add_edge("synthesise",           END)
    graph.add_edge("format_cannot_answer", END)

    return graph


# ──────────────────────────────────────────────────────────────────────
# COMPILED GRAPH + MEMORY
# ──────────────────────────────────────────────────────────────────────

memory   = MemorySaver()
_graph   = _build_graph()
compiled = _graph.compile(checkpointer=memory)

# FIX (MAJOR): Removed module-level CONFIG with hardcoded thread_id="main".
# All users sharing a single thread_id means conversation history from User A
# pollutes User B's next query. run() now accepts an optional thread_id so
# each HTTP request / user session gets its own isolated memory thread.
# Default is "main" for backward-compat with main.py interactive harness.


# ──────────────────────────────────────────────────────────────────────
# PUBLIC API
# ──────────────────────────────────────────────────────────────────────

def run(
    user_question: str,
    schema: str,
    retrieved_tables: list[str],
    thread_id: str = "main",
) -> AgentState:
    """
    Invoke the LangGraph agent for a single question.

    Args:
        user_question:    Raw user input string.
        schema:           Assembled prompt text from build_prompt().
        retrieved_tables: Table names retrieved from ChromaDB.
        thread_id:        LangGraph memory thread ID. Use a unique value
                          per user/session (e.g. a UUID) to prevent
                          conversation history leaking between users.
                          Defaults to "main" for the interactive CLI.
    """
    config = {"configurable": {"thread_id": thread_id}}
    result = compiled.invoke(
        {
            "messages":         [HumanMessage(content=user_question)],
            "user_question":    user_question,
            "schema":           schema,
            "retrieved_tables": retrieved_tables,
            "generated_sql":    "",
            "sql_error":        None,
            "data":             [],
            "row_count":        0,
            "insight":          None,
            "needs_input":      False,
            "cannot_answer":    False,
            "final_message":    "",
        },
        config=config,
    )
    return cast(AgentState, result)


def clear_memory() -> None:
    global memory, compiled
    memory   = MemorySaver()
    compiled = _graph.compile(checkpointer=memory)