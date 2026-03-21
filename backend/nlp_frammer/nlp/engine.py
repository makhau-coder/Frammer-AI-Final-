# nlp/engine.py
#
# FIX (CRITICAL): query_stream() no longer calls synthesise_stream().
# The old code ran two Gemini synthesis calls per streaming query:
#   1. Blocking: inside agent_run() → node_synthesise() → synthesise()
#   2. Streaming: synthesise_stream() called afterwards
# The first result was discarded; only the second was used.
# Now query_stream() reuses agent_result["insight"] from the first call
# and emits it as a single yielded chunk, eliminating the redundant call.

#
# Public entry point for the NLP layer.
# This is the only file the rest of your application imports.
#
# Usage:
#   from nlp.engine import query, NLPResult
#   result = query("Which user uploaded the most videos?")


import logging
from dataclasses import dataclass, field
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from nlp.retriever       import retrieve
from nlp.prompt_builder  import build_prompt, estimate_tokens
from nlp.agent           import run as agent_run, clear_memory   # LangGraph agent
from nlp.chart_generator import generate_chart
# synthesise_stream removed — query_stream now uses agent_result["insight"] directly


logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────
# PUBLIC RETURN TYPE
# ──────────────────────────────────────────────────────────────────────


@dataclass
class NLPResult:
    success:          bool         # True if SQL ran and returned data
    query:            str          # Original user question
    sql:              str          # Generated SQL (empty if cannot_answer)
    data:             list[dict]   # Query results as list of row dicts
    row_count:        int          # Number of rows returned
    retrieved_tables: list[str]    # Tables referenced in retrieved chunks
    cannot_answer:    bool         # True if question is out of scope
    needs_input:      bool         # True if agent is asking the user a question
    message:          str          # Final user-facing message from the agent
    error:            str | None   # Error message if success=False

    # ── Synthesiser output ────────────────────────────────────────
    insight:          str | None   # Natural language answer + explainability
                                   # None if synthesis failed or not applicable

    # ── Chart output ──────────────────────────────────────────────
    chart_path:       str | None   # Absolute path to saved PNG
                                   # None if data shape doesn't suit a chart
    chart_type:       str | None   # e.g. "line", "bar", "heatmap", "dual_axis"
                                   # None if no chart was generated

    # ── Debug fields — populated in dev, ignored in prod ─────────
    prompt_tokens:    int  = field(default=0,  repr=False)


# ──────────────────────────────────────────────────────────────────────
# PUBLIC: QUERY
# ──────────────────────────────────────────────────────────────────────


def query(text: str, debug: bool = False, thread_id: str = "main") -> NLPResult:
    """
    Full NLP pipeline:
        1. ChromaDB retrieval
        2. Build schema prompt
        3. LangGraph agent (SQL generation → execution → synthesis)
        4. Plotly chart generation

    Args:
        text:  The user's natural language question.
        debug: If True, populates prompt_tokens.

    Returns:
        NLPResult — see dataclass definition above.
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

    # ── Step 3: Run agent (replaces generate + execute + synthesise) ─
    agent_result = agent_run(text, schema, context.referenced_tables, thread_id=thread_id)

    # ── Step 4: Chart (only runs if agent got real data) ─────────────
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
# PUBLIC: QUERY_STREAM
# ──────────────────────────────────────────────────────────────────────


def query_stream(text: str, debug: bool = False, thread_id: str = "main"):
    """
    Streaming variant of query().

    Runs the full pipeline identically to query() — ChromaDB retrieval,
    prompt building, LangGraph agent (SQL generation + execution) — but
    instead of waiting for the synthesiser to finish, it yields insight
    text chunks as they stream from Gemini.

    Yield protocol (same pattern as synthesise_stream):
        str       — incremental insight text chunk; print immediately.
        NLPResult — final item; always last. Carries the complete result
                    (including the fully accumulated insight string) so
                    callers can inspect sql, data, chart_path, etc.

    Caller pattern (see main.py):
        for chunk in query_stream(text):
            if isinstance(chunk, str):
                print(chunk, end="", flush=True)
            else:
                result = chunk  # NLPResult — pipeline is complete

    Non-streaming parts of the pipeline (retrieval, SQL gen, execution,
    chart generation) are unchanged and happen before the first chunk is
    yielded.  If the agent returns needs_input / cannot_answer / error,
    no streaming occurs — an NLPResult is yielded immediately, just like
    query() would return it.

    Args:
        text:  The user's natural language question.
        debug: If True, populates prompt_tokens in the final NLPResult.
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

    # ── Step 3: LangGraph agent (SQL gen + execution) ─────────────────
    # The agent internally calls the blocking synthesise() to populate
    # agent_result["insight"].  We will RE-stream the insight ourselves
    # below, so we only use the agent for SQL + data here.
    agent_result = agent_run(text, schema, context.referenced_tables, thread_id=thread_id)

    # ── Early-exit: clarification / cannot_answer / SQL error ────────
    # Nothing to stream — yield a complete NLPResult immediately.
    if (
        agent_result["needs_input"]
        or agent_result["cannot_answer"]
        or agent_result["sql_error"]
        or agent_result["row_count"] == 0
    ):
        chart_path, chart_type = None, None
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

    # ── Step 4: Chart (non-blocking, runs before streaming starts) ────
    chart_path, chart_type = None, None
    try:
        chart = generate_chart(text, agent_result["data"], agent_result["generated_sql"])
        if chart:
            chart_path, chart_type = chart
    except Exception as e:
        logger.warning(f"[engine] Chart generation failed (non-fatal): {e}")

    # ── Step 5: Yield the agent's insight — no second Gemini call ───────
    # FIX (CRITICAL): The old code called synthesise_stream() here, making a
    # second Gemini API call for synthesis after agent_run() had already made a
    # first blocking call inside node_synthesise. This doubled synthesis cost
    # and latency on every streaming request.
    #
    # The agent already populated agent_result["insight"] via its synthesise node.
    # We emit it as a single yielded string chunk so callers get the token-by-token
    # UX expectation met, then yield the final NLPResult.
    insight = agent_result.get("insight") or ""

    if insight:
        yield insight   # ← emitted as one chunk; callers print it immediately

    # ── Step 6: Yield the complete NLPResult as the final item ────────
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
        insight=insight or None,
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