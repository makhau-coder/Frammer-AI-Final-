import logging
import os
from typing import Optional
import sys
from dataclasses import dataclass, field

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from nlp.retriever       import retrieve
from nlp.prompt_builder  import build_prompt, estimate_tokens
from nlp.agent           import run as agent_run, clear_memory
from nlp.chart_generator import generate_chart
from nlp.synthesiser     import synthesise_stream, SynthesisResult

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────
# PUBLIC RETURN TYPE
# ──────────────────────────────────────────────────────────────────────

@dataclass
class NLPResult:
    success:          bool         # True if SQL ran and returned data
    query:            str          # Original user question
    sql:              str          # Generated SQL
    data:             list[dict]   # Query results as list of row dicts
    row_count:        int          # Number of rows returned
    retrieved_tables: list[str]    # Tables referenced in retrieved chunks
    cannot_answer:    bool         # True if question is out of scope
    needs_input:      bool         # True if agent is asking the user a question
    message:          str          # Final user-facing message from the agent
    error:            Optional[str]   # Error message if success=False
    insight:          Optional[str]   # Natural language answer
    chart_path:       Optional[str]   # Absolute path to saved PNG
    chart_type:       Optional[str]   # e.g. "line", "bar", "heatmap"
    prompt_tokens:    int  = field(default=0, repr=False)


# ──────────────────────────────────────────────────────────────────────
# FIX: SMARTER SQL DETECTION
# ──────────────────────────────────────────────────────────────────────

def _is_sql(text: Optional[str]) -> bool:
    """Returns True if the text looks like SQL, stripping markdown blocks first."""
    if not text:
        return False
    s = text.strip().upper()
    # Strip markdown formatting that Gemini loves to add
    s = s.replace("```SQL", "").replace("```", "").strip()
    # Check if the core string starts with a SQL keyword
    return any(s.startswith(kw) for kw in ("SELECT", "WITH", "INSERT", "UPDATE", "DELETE"))


def _safe_insight(insight: Optional[str], fallback: str) -> Optional[str]:
    """Returns insight if it's natural language; uses fallback if empty or SQL."""
    # THE FIX: If insight is None/Empty, use the fallback (which has our Clarify text!)
    if not insight:
        return fallback if fallback and not _is_sql(fallback) else None
        
    if _is_sql(insight):
        logger.warning("[engine] Insight contains raw SQL. Attempting fallback.")
        if fallback and not _is_sql(fallback):
            return fallback
        return None
        
    return insight

# ──────────────────────────────────────────────────────────────────────
# PUBLIC: QUERY (blocking)
# ──────────────────────────────────────────────────────────────────────

def query(text: str, debug: bool = False, thread_id: str = "main") -> NLPResult:
    text = text.strip()
    if not text:
        return _error_result(text, "Empty query.")

    logger.info(f"[engine] Query received: {text!r}")

    # 1: Retrieve context
    try:
        context = retrieve(text)
    except RuntimeError as e:
        return _error_result(text, str(e))

    # 2: Build prompt
    schema    = build_prompt(text, context)
    token_est = estimate_tokens(schema)

    # 3: Run agent
    agent_result = agent_run(text, schema, context.referenced_tables, thread_id=thread_id)

    print(f"\n[DEBUG 🚀] 4. AGENT FINAL STATE (query):")
    print(f"  - Needs Input: {agent_result.get('needs_input')}")
    print(f"  - Generated SQL: {agent_result.get('generated_sql')}")
    print(f"  - Final Message: {agent_result.get('final_message')}\n")

    # General answer: return immediately
    if agent_result.get("is_general_answer"):
        answer = agent_result["final_message"]
        return NLPResult(
            success=True, query=text, sql="", data=[], row_count=0,
            retrieved_tables=agent_result["retrieved_tables"], cannot_answer=False,
            needs_input=False, message=answer, error=None, insight=answer,
            chart_path=None, chart_type=None, prompt_tokens=token_est if debug else 0,
        )

    # 4: Generate Chart
    chart_path, chart_type = None, None
    if agent_result["row_count"] > 0:
        try:
            chart = generate_chart(text, agent_result["data"], agent_result["generated_sql"])
            if chart:
                chart_path, chart_type = chart
        except Exception as e:
            logger.warning(f"[engine] Chart generation failed: {e}")

    # FIX 5: Force Synthesis for DATA queries
    # If the agent got data, we run the dedicated synthesiser to guarantee an English answer,
    # completely bypassing the agent's tendency to just spit out raw SQL.
    insight_text = ""
    if agent_result["row_count"] > 0:
        logger.info("[engine] Running dedicated synthesis to format data into English...")
        chunks = []
        for chunk in synthesise_stream(
            question=text,
            sql=agent_result["generated_sql"],
            tables=agent_result["retrieved_tables"],
            data=agent_result["data"]
        ):
            if isinstance(chunk, str):
                chunks.append(chunk)
        insight_text = "".join(chunks).strip()

    # Fallback to safe agent output if synthesis failed
    if not insight_text:
        insight_text = _safe_insight(agent_result.get("insight"), agent_result.get("final_message"))

    return NLPResult(
        success=agent_result["row_count"] > 0,
        query=text,
        sql=agent_result["generated_sql"],
        data=agent_result["data"],
        row_count=agent_result["row_count"],
        retrieved_tables=agent_result["retrieved_tables"],
        cannot_answer=agent_result["cannot_answer"],
        needs_input=agent_result["needs_input"],
        message=insight_text or "Data retrieved successfully.",
        error=agent_result["sql_error"],
        insight=insight_text,
        chart_path=chart_path,
        chart_type=chart_type,
        prompt_tokens=token_est if debug else 0,
    )

# ──────────────────────────────────────────────────────────────────────
# PUBLIC: QUERY_STREAM (streaming)
# ──────────────────────────────────────────────────────────────────────

def query_stream(text: str, debug: bool = False, thread_id: str = "main"):
    text = text.strip()
    if not text:
        yield _error_result(text, "Empty query.")
        return

    # 1: Retrieval
    try:
        context = retrieve(text)
    except RuntimeError as e:
        yield _error_result(text, str(e))
        return

    schema    = build_prompt(text, context)
    token_est = estimate_tokens(schema)

    # 2: Agent
    agent_result = agent_run(text, schema, context.referenced_tables, thread_id=thread_id)

    print(f"\n[DEBUG 🚀] 4. AGENT FINAL STATE (stream):")
    print(f"  - Needs Input: {agent_result.get('needs_input')}")
    print(f"  - Generated SQL: {agent_result.get('generated_sql')}")
    print(f"  - Final Message: {agent_result.get('final_message')}\n")

    # General answer
    if agent_result.get("is_general_answer"):
        answer = agent_result["final_message"]
        if answer:
            yield answer
        yield NLPResult(
            success=True, query=text, sql="", data=[], row_count=0,
            retrieved_tables=agent_result["retrieved_tables"], cannot_answer=False,
            needs_input=False, message=answer, error=None, insight=answer,
            chart_path=None, chart_type=None, prompt_tokens=token_est if debug else 0,
        )
        return

    # Early exit conditions
    if agent_result["needs_input"] or agent_result["cannot_answer"] or agent_result["sql_error"] or agent_result["row_count"] == 0:
        yield NLPResult(
            success=agent_result["row_count"] > 0, query=text, sql=agent_result["generated_sql"],
            data=agent_result["data"], row_count=agent_result["row_count"],
            retrieved_tables=agent_result["retrieved_tables"], cannot_answer=agent_result["cannot_answer"],
            needs_input=agent_result["needs_input"], message=agent_result["final_message"],
            error=agent_result["sql_error"], insight=agent_result["insight"],
            chart_path=None, chart_type=None, prompt_tokens=token_est if debug else 0,
        )
        return

    # 3: Chart
    chart_path, chart_type = None, None
    try:
        chart = generate_chart(text, agent_result["data"], agent_result["generated_sql"])
        if chart:
            chart_path, chart_type = chart
    except Exception as e:
        logger.warning(f"[engine] Chart generation failed: {e}")

    # 4: Stream Synthesis
    final_synthesis: Optional[SynthesisResult] = None
    for chunk in synthesise_stream(
        question=text,
        sql=agent_result["generated_sql"],
        tables=agent_result["retrieved_tables"],
        data=agent_result["data"],
    ):
        if isinstance(chunk, str):
            yield chunk
        else:
            final_synthesis = chunk

    insight = final_synthesis.insight if final_synthesis else None

    # 5: Yield final result
    yield NLPResult(
        success=True, query=text, sql=agent_result["generated_sql"],
        data=agent_result["data"], row_count=agent_result["row_count"],
        retrieved_tables=agent_result["retrieved_tables"], cannot_answer=False,
        needs_input=False, message=insight or agent_result["final_message"],
        error=None, insight=insight, chart_path=chart_path, chart_type=chart_type,
        prompt_tokens=token_est if debug else 0,
    )

def _error_result(text: str, reason: str) -> NLPResult:
    return NLPResult(
        success=False, query=text, sql="", data=[], row_count=0,
        retrieved_tables=[], cannot_answer=False, needs_input=False,
        message=reason, error=reason, insight=None, chart_path=None, chart_type=None,
    )