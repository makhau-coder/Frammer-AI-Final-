# nlp/agent.py
#
# FULLY MERGED — all three versions combined:
#
# From YOUR backend version:
#   - thread_id parameter on run() — per-session LangGraph isolation (CRITICAL)
#   - fuzzy match cutoff 0.2 → 0.35 (prevents false confirmation prompts)
#   - Windows drive-letter guard on FRAMMER_DB_PATH (C:, D:, E:, ...)
#   - _get_llm_plain() max_output_tokens 256 → 1024
#   - Month normalisation: "february" → "Feb, 2026" (no-year resolution)
#   - Language normalisation: "hindi" → "hi"
#   - Channel letter rescue: single-letter channel names preserved
#
# From FRIEND2 / LAST version:
#   - thinking_budget=0 on _get_llm_plain() — faster responses
#   - _get_llm_classifier() — micro LLM for GENERAL/DATA routing (8 tokens)
#   - is_general_answer field on AgentState
#   - GENERAL/DATA classifier in node_generate_sql (Step 1)
#   - _GENERAL_ANSWER_PROMPT — schema-aware direct answers for general questions
#   - Platform entities loaded from dim_platform star schema table (STAR_SOURCES)
#   - general_answer route in graph → END (skips DB entirely)
#   - General answer stream passthrough in engine.py query_stream()
#
# FIXED vs LAST version:
#   - run() restores thread_id parameter (LAST dropped it, re-introduced
#     module-level CONFIG with hardcoded thread_id="main" — breaks multi-user)

from __future__ import annotations

import os
import re
import difflib
import logging
import duckdb
from typing import TypedDict, Annotated, cast, Optional
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
    """Plain LLM for general answer + empty-result calls — thinking disabled."""
    return ChatGoogleGenerativeAI(
        model=GEMINI_MODEL,
        google_api_key=os.environ.get("GEMINI_API_KEY", ""),
        temperature=0.0,
        max_output_tokens=1024,   # FIX: was 256 — too small for entity listing
        thinking_budget=0,        # disables chain-of-thought — faster responses
    )


def _get_llm_classifier() -> ChatGoogleGenerativeAI:
    """Micro LLM just for GENERAL/DATA routing — outputs one word only."""
    return ChatGoogleGenerativeAI(
        model=GEMINI_MODEL,
        google_api_key=os.environ.get("GEMINI_API_KEY", ""),
        temperature=0.0,
        max_output_tokens=8,
        thinking_budget=0,
    )


# ──────────────────────────────────────────────────────────────────────
# STATE
# ──────────────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    messages:          Annotated[list[BaseMessage], operator.add]
    user_question:     str
    schema:            str
    retrieved_tables:  list[str]
    generated_sql:     str
    sql_error:         Optional[str]
    data:              list[dict]
    row_count:         int
    insight:           Optional[str]
    needs_input:       bool
    cannot_answer:     bool
    final_message:     str
    is_general_answer: bool   # True when question answered directly without SQL


# ──────────────────────────────────────────────────────────────────────
# PROMPT FRAGMENTS
# ──────────────────────────────────────────────────────────────────────

CANNOT_ANSWER_RULES = """
If the question cannot be answered from the available schema, return:
CANNOT_ANSWER: <one sentence why> | <suggestion 1> | <suggestion 2> | <suggestion 3>
""".strip()

# ──────────────────────────────────────────────────────────────────────
# GENERAL QUESTION PROMPTS
# Split into two calls:
#   1. _CLASSIFIER_PROMPT   — routes DATA vs GENERAL (no schema, 8 tokens)
#   2. _GENERAL_ANSWER_PROMPT — answers the general question (schema injected)
# Kept separate so SYSTEM_PROMPT (SQL instructions) never interferes.
# ──────────────────────────────────────────────────────────────────────

_CLASSIFIER_PROMPT = """
You are a strict query router. Classify the user message into exactly one category: GENERAL or DATA.

GENERAL:
The user is asking about the software platform itself, asking for definitions of metrics, or saying hello.
Examples: "what is frammer ai", "what does publish rate mean", "hi", "what metrics do you have"

DATA:
The user wants specific information, stats, or details about the content. IF THE USER MENTIONS A SPECIFIC PERSON, CHANNEL, PLATFORM, OR DATE, IT IS ALWAYS DATA.
Examples: "give info about channel q", "give info about neha", "how many videos were uploaded", "top 5 users"

Reply with exactly one word: GENERAL or DATA
""".strip()

_GENERAL_ANSWER_PROMPT = """
You are a Frammer analytics assistant. Frammer is an AI-powered video content
production platform that processes uploaded source videos and generates
multiple output clips, which can then be published to social platforms.

You have access to the following schema and platform knowledge:

{schema}

Answer the user's question directly and helpfully in plain English.
Use light markdown (bold, bullet lists) where it improves readability.
Do NOT mention SQL, databases, or that you are any kind of query tool.
You are simply a Frammer analytics assistant.
""".strip()


# ──────────────────────────────────────────────────────────────────────
# KNOWN ENTITY VALUES — loaded from DuckDB once at startup
# ──────────────────────────────────────────────────────────────────────

_KNOWN_ENTITIES: dict[str, list[str]] = {}


def _load_known_entities() -> dict[str, list[str]]:
    global _KNOWN_ENTITIES
    if _KNOWN_ENTITIES:
        return _KNOWN_ENTITIES

    _fallback_db = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "..", "frammer_analytics.duckdb")
    )
    raw_path = os.environ.get("FRAMMER_DB_PATH", "").strip()

    if not raw_path:
        db_path = _fallback_db
    elif (
        len(raw_path) >= 2
        and raw_path[1] == ":"
        and raw_path[0].isalpha()
        and os.name != "nt"          # only block Windows paths when running on Linux/Mac
    ):
        # Windows absolute path detected on a non-Windows server — use relative fallback
        # so a dev's local .env doesn't break the production server.
        # On Windows itself (os.name == "nt") the path is used as-is.
        logger.warning(
            f"[agent] FRAMMER_DB_PATH is a Windows path ({raw_path!r}) but "
            f"server is not Windows. Using fallback: {_fallback_db}"
        )
        db_path = _fallback_db
    else:
        db_path = os.path.normpath(raw_path)

    # Flat summary tables
    SOURCES = {
        "User":        ("combined_data2025_3_1_2026_2_28_by_user",       "User"),
        "Channel":     ("client_1_combined_data2025_3_1_2026_2_28",       "Channel"),
        "Input Type":  ("combined_data2025_3_1_2026_2_28_by_input_type",  "Input Type"),
        "Output Type": ("combined_data2025_3_1_2026_2_28_by_output_type", "Output Type"),
        "Language":    ("combined_data2025_3_1_2026_2_28_by_language",    "Language"),
        "Month":       ("monthly_chart",                                   "Month"),
    }

    # Star schema dimension tables (LAST version addition)
    STAR_SOURCES = {
        "Platform": ("dim_platform", "platform_name"),
    }

    try:
        conn = duckdb.connect(db_path, read_only=True)

        for label, (table, col) in SOURCES.items():
            rows = conn.execute(
                f'SELECT DISTINCT "{col}" FROM "{table}" '
                f'WHERE "{col}" IS NOT NULL ORDER BY "{col}"'
            ).fetchall()
            _KNOWN_ENTITIES[label] = [r[0] for r in rows]

        for label, (table, col) in STAR_SOURCES.items():
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
# Run BEFORE fuzzy matching so natural phrases like "February 2026" or
# "Hindi" are converted to DB representations ("Feb, 2026", "hi") and
# picked up by the high-confidence pass.
# ──────────────────────────────────────────────────────────────────────

_MONTH_ALIASES: dict[str, str] = {
    "january":   "Jan", "february":  "Feb", "march":     "Mar",
    "april":     "Apr", "may":       "May", "june":      "Jun",
    "july":      "Jul", "august":    "Aug", "september": "Sep",
    "october":   "Oct", "november":  "Nov", "december":  "Dec",
}

_LANGUAGE_ALIASES: dict[str, str] = {
    "english": "en", "hindi": "hi", "spanish": "es",
    "arabic":  "ar", "marathi": "mr", "mixed": "mix",
}


def _normalize_month_tokens(tokens: list[str]) -> list[str]:
    """
    "february" → "Feb, 2026" (with year) or resolves against known DB months
    (without year) so it hits the high-confidence pass silently.
    """
    extra: list[str] = []
    years = [t for t in tokens if re.fullmatch(r"20\d{2}", t)]
    resolved_abbrevs: list[str] = []

    for token in tokens:
        if token in _MONTH_ALIASES:
            resolved_abbrevs.append(_MONTH_ALIASES[token])
        else:
            matches = difflib.get_close_matches(
                token, list(_MONTH_ALIASES.keys()), n=1, cutoff=0.75,
            )
            if matches:
                resolved_abbrevs.append(_MONTH_ALIASES[matches[0]])

    if years:
        for abbrev in resolved_abbrevs:
            for year in years:
                db_token = f"{abbrev}, {year}"
                if db_token not in extra:
                    extra.append(db_token)
    else:
        known_months = _load_known_entities().get("Month", [])
        for abbrev in resolved_abbrevs:
            prefix = f"{abbrev},"
            for known in known_months:
                if known.startswith(prefix) and known not in extra:
                    extra.append(known)

    return tokens + extra


def _normalize_language_tokens(tokens: list[str]) -> list[str]:
    """"hindi" → "hi", "english" → "en" — with typo tolerance (cutoff 0.80)."""
    extra: list[str] = []
    for token in tokens:
        if token in _LANGUAGE_ALIASES:
            code = _LANGUAGE_ALIASES[token]
            if code not in extra:
                extra.append(code)
        else:
            matches = difflib.get_close_matches(
                token, list(_LANGUAGE_ALIASES.keys()), n=1, cutoff=0.80,
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
    # by stopwords. "channel X" → preserve X explicitly.
    channel_refs = re.findall(r'\bchannel\s+([a-zA-Z])\b', user_question, re.IGNORECASE)
    for ref in channel_refs:
        t = ref.lower()
        if t not in tokens:
            tokens.append(t)

    entity_refs = re.findall(
        r'\b(?:channel|for|about|of)\s+([a-zA-Z])\b', user_question, re.IGNORECASE
    )
    for ref in entity_refs:
        t = ref.lower()
        if t not in tokens:
            tokens.append(t)

    concat = re.sub(r"[^a-zA-Z0-9]", "", user_question).lower()
    if concat and concat not in tokens:
        tokens.append(concat)

    # Normalize months and languages BEFORE fuzzy matching
    tokens = _normalize_month_tokens(tokens)
    tokens = _normalize_language_tokens(tokens)

    lines: list[str] = []
    for label, values in entities.items():
        values_lower: dict[str, str] = {str(v).lower(): str(v) for v in values}

        high_conf: list[str] = []
        low_conf:  list[str] = []

        for token in tokens:
            for m in difflib.get_close_matches(token, list(values_lower.keys()), n=3, cutoff=0.80):
                v = values_lower.get(m, m)
                if v not in high_conf:
                    high_conf.append(v)

            # YOUR FIX: cutoff 0.35 (was 0.2 — too aggressive, caused false prompts)
            for m in difflib.get_close_matches(token, list(values_lower.keys()), n=3, cutoff=0.35):
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
        "cannot_answer":     True,
        "needs_input":       False,
        "generated_sql":     "",
        "sql_error":         None,
        "final_message":     parts,
        "is_general_answer": False,
    }


def _parse_clarify(text: str) -> dict:
    question = text.split("CLARIFY:", 1)[-1].strip()
    return {
        "needs_input":       True,
        "cannot_answer":     False,
        "generated_sql":     "",
        "sql_error":         None,
        "final_message":     question,
        "is_general_answer": False,
    }


# ──────────────────────────────────────────────────────────────────────
# NODES
# ──────────────────────────────────────────────────────────────────────

def node_generate_sql(state: AgentState) -> dict:

    # ── STEP 1: Route — GENERAL question or DATA query? ───────────────
    # Tiny call: no schema, thinking disabled, max 8 output tokens.
    # Outputs exactly one word: GENERAL or DATA.
    try:
        route_raw = str(
            _get_llm_classifier().invoke([
                SystemMessage(content=_CLASSIFIER_PROMPT),
                HumanMessage(content=state["user_question"]),
            ]).content
        ).strip().upper()
        logger.info(f"[agent] Classifier route: {route_raw!r}")
    except Exception as e:
        logger.warning(f"[agent] Classifier failed ({e}) — defaulting to DATA.")
        route_raw = "DATA"

    # ── STEP 2: GENERAL → answer directly, skip SQL entirely ──────────
    if "GENERAL" in route_raw:
        try:
            answer_prompt = _GENERAL_ANSWER_PROMPT.format(schema=state["schema"])
            answer_raw = str(
                _get_llm_plain().invoke([
                    SystemMessage(content=answer_prompt),
                    HumanMessage(content=state["user_question"]),
                ]).content
            ).strip()
            logger.info("[agent] General question — answered directly, skipping SQL.")
        except Exception as e:
            logger.error(f"[agent] General answer call failed ({e}).")
            answer_raw = "I'm sorry, I wasn't able to generate a response. Please try again."

        return {
            "generated_sql":     "",
            "sql_error":         None,
            "needs_input":       False,
            "cannot_answer":     False,
            "is_general_answer": True,
            "final_message":     answer_raw,
            "messages":          [AIMessage(content=answer_raw)],
        }

    # ── STEP 3: DATA → full SQL generation ────────────────────────────
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

3. No match found:
   → Do NOT write SQL.
   → Return: CLARIFY: I couldn't find a match for "<value>". Could you check
     the spelling or type the first few letters of the name you're looking for?

4. Question outside available data:
   → Return: CANNOT_ANSWER: <reason> | <suggestion 1> | <suggestion 2> | <suggestion 3>

Never use a raw user-typed string in a WHERE clause.
Never assume a name substitution without confirmation from the user.

User question: {state['user_question']}"""

    messages.append(HumanMessage(content=entity_reminder))

    try:
        response = llm.invoke(messages)
        raw = str(response.content).strip()
        logger.debug(f"[agent] Raw Gemini response:\n{raw}")
    except Exception as e:
        logger.error(f"[agent] Gemini API call failed: {e}")
        return {
            "sql_error":         f"Gemini API error: {e}",
            "generated_sql":     "",
            "final_message":     f"SQL generation failed: {e}",
            "is_general_answer": False,
            "messages":          [AIMessage(content=f"Error: {e}")],
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
        "generated_sql":     sql,
        "sql_error":         None,
        "is_general_answer": False,
        "messages":          [AIMessage(content=sql)],
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
    Uses the FULL entity list (_format_entities) — diagnosing a WHERE
    clause mismatch requires exhaustive comparison, not fuzzy tokens.
    """
    llm = _get_llm_plain()

    prompt_text = f"""A SQL query returned zero results.

SQL that was executed:
{state["generated_sql"]}

User question: "{state["user_question"]}"

KNOWN VALUES IN THE DATABASE:
{_format_entities()}

Compare every value in the WHERE clause against the KNOWN VALUES.
Identify which value is likely causing zero results.

Respond with EXACTLY one of these two formats — nothing else:

If an entity mismatch is likely:
CLARIFY: I couldn't find "<where_value>" in the dataset. The available <label> values are: <list ALL values for that label from KNOWN VALUES>

If the data genuinely does not exist:
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
        parts       = raw[len("CANNOT_ANSWER:"):].strip().split("|")
        reason      = parts[0].strip()
        suggestions = [p.strip() for p in parts[1:]]
        msg = reason
        if suggestions:
            msg += "\n\nYou could try:\n" + "\n".join(
                f"  {i+1}) {s}" for i, s in enumerate(suggestions)
            )
        return {"needs_input": False, "cannot_answer": True, "final_message": msg}

    return {"needs_input": True, "cannot_answer": False, "final_message": raw}


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
    if state.get("is_general_answer"):
        return "general_answer"
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
        "execute":        "execute_sql",
        "needs_input":    END,
        "cannot_answer":  "format_cannot_answer",
        "general_answer": END,   # answered directly — skip DB entirely
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
        thread_id:        LangGraph memory thread ID. Use a unique UUID
                          per user/session to prevent conversation history
                          leaking between users. Defaults to "main" for
                          the interactive CLI (main.py).
    """
    config = {"configurable": {"thread_id": thread_id}}
    result = compiled.invoke(
        {
            "messages":          [HumanMessage(content=user_question)],
            "user_question":     user_question,
            "schema":            schema,
            "retrieved_tables":  retrieved_tables,
            "generated_sql":     "",
            "sql_error":         None,
            "data":              [],
            "row_count":         0,
            "insight":           None,
            "needs_input":       False,
            "cannot_answer":     False,
            "final_message":     "",
            "is_general_answer": False,
        },
        config=config,
    )
    return cast(AgentState, result)


def clear_memory() -> None:
    global memory, compiled
    memory   = MemorySaver()
    compiled = _graph.compile(checkpointer=memory)