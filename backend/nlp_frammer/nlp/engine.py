# nlp/engine.py
#
# Public entry point for the NLP layer.
# This is the only file the rest of your application imports.
#
# Usage:
#   from nlp.engine import query, NLPResult
#   result = query("Which user uploaded the most videos?")


import logging
from dataclasses import dataclass, field

from nlp.retriever       import retrieve
from nlp.prompt_builder  import build_prompt, estimate_tokens
from nlp.sql_generator   import generate
from nlp.executor        import execute
from nlp.synthesiser     import synthesise
from nlp.chart_generator import generate_chart


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
    error:            str | None   # Error message if success=False

    # ── Step 2: Synthesiser output ────────────────────────────────
    insight:          str | None   # Natural language answer + explainability
                                   # None if synthesis failed or not applicable

    # ── Step 3: Chart output ──────────────────────────────────────
    chart_path:       str | None   # Absolute path to saved PNG
                                   # None if data shape doesn't suit a chart
    chart_type:       str | None   # e.g. "line", "bar", "heatmap", "dual_axis"
                                   # None if no chart was generated

    # ── Debug fields — populated in dev, ignored in prod ─────────
    prompt_tokens:    int  = field(default=0,  repr=False)
    raw_response:     str  = field(default="", repr=False)


# ──────────────────────────────────────────────────────────────────────
# PUBLIC: QUERY
# ──────────────────────────────────────────────────────────────────────


def query(text: str, debug: bool = False) -> NLPResult:
    """
    Full NLP pipeline:
        1. ChromaDB retrieval
        2. Gemini SQL generation
        3. DuckDB execution
        4. Gemini insight synthesis   ← new
        5. Plotly chart generation    ← new

    Args:
        text:  The user's natural language question.
        debug: If True, populates prompt_tokens and raw_response.

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

    # ── Step 2: Assemble prompt ───────────────────────────────────────
    prompt    = build_prompt(text, context)
    token_est = estimate_tokens(prompt)
    logger.debug(f"[engine] Estimated prompt tokens: {token_est}")

    # ── Step 3: Call Gemini → SQL ─────────────────────────────────────
    gen_result = generate(prompt)

    if gen_result.cannot_answer:
        logger.info(f"[engine] CANNOT_ANSWER: {gen_result.reason}")
        return NLPResult(
            success=False,
            query=text,
            sql="",
            data=[],
            row_count=0,
            retrieved_tables=context.referenced_tables,
            cannot_answer=True,
            error=gen_result.reason,
            insight=gen_result.reason,   # surface the reason directly
            chart_path=None,
            chart_type=None,
            prompt_tokens=token_est if debug else 0,
            raw_response=gen_result.raw_response if debug else "",
        )

    if not gen_result.success:
        logger.error(f"[engine] SQL generation failed: {gen_result.reason}")
        return NLPResult(
            success=False,
            query=text,
            sql="",
            data=[],
            row_count=0,
            retrieved_tables=context.referenced_tables,
            cannot_answer=False,
            error=gen_result.reason,
            insight=None,
            chart_path=None,
            chart_type=None,
            prompt_tokens=token_est if debug else 0,
            raw_response=gen_result.raw_response if debug else "",
        )

    logger.info(f"[engine] Generated SQL:\n{gen_result.sql}")

    # ── Step 4: Execute on DuckDB ─────────────────────────────────────
    exec_result = execute(gen_result.sql)

    if not exec_result.success:
        logger.error(f"[engine] Execution failed: {exec_result.error}")
        return NLPResult(
            success=False,
            query=text,
            sql=gen_result.sql,
            data=[],
            row_count=0,
            retrieved_tables=context.referenced_tables,
            cannot_answer=False,
            error=exec_result.error,
            insight=None,
            chart_path=None,
            chart_type=None,
            prompt_tokens=token_est if debug else 0,
            raw_response=gen_result.raw_response if debug else "",
        )

    logger.info(f"[engine] Execution success — {exec_result.row_count} row(s).")

    # ── Step 5: Synthesise natural language insight ───────────────────
    insight = _safe_synthesise(
        question=text,
        sql=gen_result.sql,
        tables=context.referenced_tables,
        data=exec_result.data,
    )

    # ── Step 6: Generate chart ────────────────────────────────────────
    chart_path, chart_type = _safe_chart(
        question=text,
        data=exec_result.data,
        sql=gen_result.sql,
    )

    return NLPResult(
        success=True,
        query=text,
        sql=gen_result.sql,
        data=exec_result.data,
        row_count=exec_result.row_count,
        retrieved_tables=context.referenced_tables,
        cannot_answer=False,
        error=None,
        insight=insight,
        chart_path=chart_path,
        chart_type=chart_type,
        prompt_tokens=token_est if debug else 0,
        raw_response=gen_result.raw_response if debug else "",
    )


# ──────────────────────────────────────────────────────────────────────
# INTERNAL HELPERS
# ──────────────────────────────────────────────────────────────────────


def _safe_synthesise(
    question: str,
    sql: str,
    tables: list[str],
    data: list[dict],
) -> str | None:
    """
    Wraps synthesise() so a failure never crashes the whole pipeline.
    The user still gets their data rows even if insight generation fails.
    """
    try:
        result = synthesise(question=question, sql=sql,
                            tables=tables, data=data)
        if result.success:
            logger.debug("[engine] Synthesis complete.")
        else:
            logger.warning(f"[engine] Synthesis soft-failed: {result.error}")
        return result.insight   # always return the string — even on soft fail
    except Exception as e:
        logger.warning(f"[engine] Synthesis failed (non-fatal): {e}")
        return None


def _safe_chart(
    question: str,
    data: list[dict],
    sql: str,
) -> tuple[str | None, str | None]:
    """
    Wraps generate_chart() so a failure never crashes the whole pipeline.
    Returns (chart_path, chart_type) or (None, None).
    """
    try:
        result = generate_chart(
            question=question,
            data=data,
            sql=sql,
        )
        if result is None:
            logger.debug("[engine] No chart generated (data shape not suitable).")
            return None, None
        # generate_chart returns (path, chart_type) tuple
        path, chart_type = result
        logger.debug(f"[engine] Chart generated: {chart_type} → {path}")
        return path, chart_type
    except Exception as e:
        logger.warning(f"[engine] Chart generation failed (non-fatal): {e}")
        return None, None


def _error_result(text: str, reason: str) -> NLPResult:
    return NLPResult(
        success=False,
        query=text,
        sql="",
        data=[],
        row_count=0,
        retrieved_tables=[],
        cannot_answer=False,
        error=reason,
        insight=None,
        chart_path=None,
        chart_type=None,
    )
