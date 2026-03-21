# nlp/engine.py
#
# FULLY MERGED — all three versions combined:
#
# From YOUR backend version:
#   - thread_id on query() and query_stream() — per-session isolation
#   - sys.path.append for standalone use outside backend context
#
# From FRIEND2 version:
#   - query_stream() uses synthesise_stream() for true token-by-token streaming
#
# From LAST version:
#   - is_general_answer passthrough in query(): returns final_message as insight
#     so the API response carries the answer text in the right field
#   - is_general_answer passthrough in query_stream(): yields the answer text
#     as a streaming chunk so the frontend receives it (not silently dropped)

import logging
import os
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
    sql:              str          # Generated SQL (empty if cannot_answer or general)
    data:             list[dict]   # Query results as list of row dicts
    row_count:        int          # Number of rows returned
    retrieved_tables: list[str]    # Tables referenced in retrieved chunks
    cannot_answer:    bool         # True if question is out of scope
    needs_input:      bool         # True if agent is asking the user a question
    message:          str          # Final user-facing message from the agent
    error:            str | None   # Error message if success=False

    # ── Synthesiser / general answer output ──────────────────────────
    insight:          str | None   # Natural language answer (synthesis or general)
                                   # None if synthesis failed or not applicable

    # ── Chart output ──────────────────────────────────────────────────
    chart_path:       str | None   # Absolute path to saved PNG
    chart_type:       str | None   # e.g. "line", "bar", "heatmap", "dual_axis"

    # ── Debug ─────────────────────────────────────────────────────────
    prompt_tokens:    int  = field(default=0, repr=False)


# ──────────────────────────────────────────────────────────────────────
# PUBLIC: QUERY (blocking)
# ──────────────────────────────────────────────────────────────────────

def query(text: str, debug: bool = False, thread_id: str = "main") -> NLPResult:
    """
    Full NLP pipeline (blocking):
        1. ChromaDB retrieval
        2. Build schema prompt
        3. LangGraph agent (GENERAL route → direct answer, or
                            DATA route → SQL generation → execution → synthesis)
        4. Plotly chart generation (DATA path only)

    Args:
        text:      The user's natural language question.
        debug:     If True, populates prompt_tokens.
        thread_id: LangGraph memory thread ID. Pass a unique UUID per
                   user/session to prevent conversation history leaking.
    """
    text = text.strip()
    if not text:
        return _error_result(text, "Empty query.")

    logger.info(f"[engine] Query received: {text!r}")

    # ── Step 1: Retrieve relevant context from ChromaDB ──────────────
    try:
        context = retrieve(text)
        logger.debug(
            f"[engine] Retrieved {context.total_chunks} chunks "
            f"({len(context.table_chunks)} table, "
            f"{len(context.metric_chunks)} metric, "
            f"{len(context.example_chunks)} example)"
        )
    except RuntimeError as e:
        return _error_result(text, str(e))

    # ── Step 2: Build schema string ──────────────────────────────────
    schema    = build_prompt(text, context)
    token_est = estimate_tokens(schema)
    logger.debug(f"[engine] Estimated prompt tokens: {token_est}")

    # ── Step 3: Run agent ─────────────────────────────────────────────
    agent_result = agent_run(text, schema, context.referenced_tables, thread_id=thread_id)

    # ── General answer: return immediately, no chart ──────────────────
    if agent_result.get("is_general_answer"):
        answer = agent_result["final_message"]
        return NLPResult(
            success=True,
            query=text,
            sql="",
            data=[],
            row_count=0,
            retrieved_tables=agent_result["retrieved_tables"],
            cannot_answer=False,
            needs_input=False,
            message=answer,
            error=None,
            insight=answer,
            chart_path=None,
            chart_type=None,
            prompt_tokens=token_est if debug else 0,
        )

    # ── Step 4: Chart (only if agent got real data) ───────────────────
    chart_path, chart_type = None, None
    if agent_result["row_count"] > 0:
        try:
            chart = generate_chart(text, agent_result["data"], agent_result["generated_sql"])
            if chart:
                chart_path, chart_type = chart
        except Exception as e:
            logger.warning(f"[engine] Chart generation failed (non-fatal): {e}")

    return NLPResult(
        success=agent_result["row_count"] > 0,
        query=text,
        sql=agent_result["generated_sql"],
        data=agent_result["data"],
        row_count=agent_result["row_count"],
        retrieved_tables=agent_result["retrieved_tables"],
        cannot_answer=agent_result["cannot_answer"],
        needs_input=agent_result["needs_input"],
        message=agent_result["final_message"],
        error=agent_result["sql_error"],
        insight=agent_result["insight"],
        chart_path=chart_path,
        chart_type=chart_type,
        prompt_tokens=token_est if debug else 0,
    )


# ──────────────────────────────────────────────────────────────────────
# PUBLIC: QUERY_STREAM (streaming)
# ──────────────────────────────────────────────────────────────────────

def query_stream(text: str, debug: bool = False, thread_id: str = "main"):
    """
    Streaming variant of query().

    For DATA queries: runs the full pipeline then streams the insight
    token-by-token via synthesise_stream().

    For GENERAL queries: yields the answer text as a single chunk then
    the final NLPResult — so the frontend receives it exactly like a
    streamed synthesis response.

    Yield protocol:
        str       — incremental text chunk (print immediately).
        NLPResult — final item; always last.

    If the agent returns needs_input / cannot_answer / error / no data,
    an NLPResult is yielded immediately with no streaming.

    Args:
        text:      The user's natural language question.
        debug:     If True, populates prompt_tokens in the final NLPResult.
        thread_id: LangGraph memory thread ID — unique per user/session.
    """
    text = text.strip()
    if not text:
        yield _error_result(text, "Empty query.")
        return

    logger.info(f"[engine] query_stream received: {text!r}")

    # ── Step 1: ChromaDB retrieval ────────────────────────────────────
    try:
        context = retrieve(text)
    except RuntimeError as e:
        yield _error_result(text, str(e))
        return

    # ── Step 2: Build schema prompt ───────────────────────────────────
    schema    = build_prompt(text, context)
    token_est = estimate_tokens(schema)

    # ── Step 3: LangGraph agent ───────────────────────────────────────
    agent_result = agent_run(text, schema, context.referenced_tables, thread_id=thread_id)

    # ── General answer: stream the text then yield NLPResult ──────────
    if agent_result.get("is_general_answer"):
        answer = agent_result["final_message"]
        if answer:
            yield answer   # caller prints this immediately
        yield NLPResult(
            success=True,
            query=text,
            sql="",
            data=[],
            row_count=0,
            retrieved_tables=agent_result["retrieved_tables"],
            cannot_answer=False,
            needs_input=False,
            message=answer,
            error=None,
            insight=answer,
            chart_path=None,
            chart_type=None,
            prompt_tokens=token_est if debug else 0,
        )
        return

    # ── Early-exit: clarification / cannot_answer / SQL error / no data
    if (
        agent_result["needs_input"]
        or agent_result["cannot_answer"]
        or agent_result["sql_error"]
        or agent_result["row_count"] == 0
    ):
        yield NLPResult(
            success=agent_result["row_count"] > 0,
            query=text,
            sql=agent_result["generated_sql"],
            data=agent_result["data"],
            row_count=agent_result["row_count"],
            retrieved_tables=agent_result["retrieved_tables"],
            cannot_answer=agent_result["cannot_answer"],
            needs_input=agent_result["needs_input"],
            message=agent_result["final_message"],
            error=agent_result["sql_error"],
            insight=agent_result["insight"],
            chart_path=None,
            chart_type=None,
            prompt_tokens=token_est if debug else 0,
        )
        return

    # ── Step 4: Chart (non-blocking, before streaming) ────────────────
    chart_path, chart_type = None, None
    try:
        chart = generate_chart(text, agent_result["data"], agent_result["generated_sql"])
        if chart:
            chart_path, chart_type = chart
    except Exception as e:
        logger.warning(f"[engine] Chart generation failed (non-fatal): {e}")

    # ── Step 5: Stream the insight token-by-token ─────────────────────
    final_synthesis: SynthesisResult | None = None

    for chunk in synthesise_stream(
        question=text,
        sql=agent_result["generated_sql"],
        tables=agent_result["retrieved_tables"],
        data=agent_result["data"],
    ):
        if isinstance(chunk, str):
            yield chunk           # caller prints this token immediately
        else:
            final_synthesis = chunk   # SynthesisResult sentinel

    insight = final_synthesis.insight if final_synthesis else None

    # ── Step 6: Yield the complete NLPResult ──────────────────────────
    yield NLPResult(
        success=agent_result["row_count"] > 0,
        query=text,
        sql=agent_result["generated_sql"],
        data=agent_result["data"],
        row_count=agent_result["row_count"],
        retrieved_tables=agent_result["retrieved_tables"],
        cannot_answer=agent_result["cannot_answer"],
        needs_input=agent_result["needs_input"],
        message=insight or agent_result["final_message"],
        error=agent_result["sql_error"],
        insight=insight,
        chart_path=chart_path,
        chart_type=chart_type,
        prompt_tokens=token_est if debug else 0,
    )


# ──────────────────────────────────────────────────────────────────────
# INTERNAL HELPERS
# ──────────────────────────────────────────────────────────────────────

def _error_result(text: str, reason: str) -> NLPResult:
    return NLPResult(
        success=False,
        query=text,
        sql="",
        data=[],
        row_count=0,
        retrieved_tables=[],
        cannot_answer=False,
        needs_input=False,
        message=reason,
        error=reason,
        insight=None,
        chart_path=None,
        chart_type=None,
    )
