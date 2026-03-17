"""
nlp/engine.py — Public entry point for the NLP layer.

Usage:
    from nlp.engine import query, NLPResult
    result = query("Which user uploaded the most videos?")
"""

import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import logging
from dataclasses import dataclass, field

from nlp.retriever       import retrieve
from nlp.prompt_builder  import build_prompt, estimate_tokens
from nlp.sql_generator   import generate
from nlp.executor        import execute
from nlp.synthesiser     import synthesise
from nlp.chart_generator import generate_chart

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC RETURN TYPE
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class NLPResult:
    success:          bool
    query:            str
    sql:              str
    data:             list[dict]
    row_count:        int
    retrieved_tables: list[str]
    cannot_answer:    bool
    error:            str | None

    # Synthesiser output
    insight:          str | None

    # Chart output — NOW A DICT (Plotly JSON) rather than a file path
    chart_path:       dict | str | None   # dict = Plotly JSON; str = legacy path; None = no chart
    chart_type:       str | None          # e.g. "line", "bar", "heatmap", "dual_axis", "pie"

    # Debug fields
    prompt_tokens:    int  = field(default=0,  repr=False)
    raw_response:     str  = field(default="", repr=False)


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC: QUERY
# ─────────────────────────────────────────────────────────────────────────────

def query(text: str, debug: bool = False) -> NLPResult:
    """
    Full NLP pipeline:
        1. ChromaDB retrieval
        2. Gemini SQL generation
        3. DuckDB execution
        4. Gemini insight synthesis
        5. Plotly chart generation (returns JSON dict, not a file path)

    Args:
        text:  The user's natural language question.
        debug: If True, populates prompt_tokens and raw_response.

    Returns:
        NLPResult
    """
    text = text.strip()
    if not text:
        return _error_result(text, "Empty query.")

    logger.info(f"[engine] Query received: {text!r}")

    # ── Step 1: Retrieve context from ChromaDB ────────────────────────────
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

    # ── Step 2: Assemble prompt ───────────────────────────────────────────
    prompt    = build_prompt(text, context)
    token_est = estimate_tokens(prompt)
    logger.debug(f"[engine] Estimated prompt tokens: {token_est}")

    # ── Step 3: Call Gemini → SQL ─────────────────────────────────────────
    gen_result = generate(prompt)

    if gen_result.cannot_answer:
        logger.info(f"[engine] CANNOT_ANSWER: {gen_result.reason}")
        return NLPResult(
            success=False, query=text, sql="", data=[], row_count=0,
            retrieved_tables=context.referenced_tables,
            cannot_answer=True, error=gen_result.reason,
            insight=gen_result.reason,
            chart_path=None, chart_type=None,
            prompt_tokens=token_est if debug else 0,
            raw_response=gen_result.raw_response if debug else "",
        )

    if not gen_result.success:
        logger.error(f"[engine] SQL generation failed: {gen_result.reason}")
        return NLPResult(
            success=False, query=text, sql="", data=[], row_count=0,
            retrieved_tables=context.referenced_tables,
            cannot_answer=False, error=gen_result.reason,
            insight=None, chart_path=None, chart_type=None,
            prompt_tokens=token_est if debug else 0,
            raw_response=gen_result.raw_response if debug else "",
        )

    logger.info(f"[engine] Generated SQL:\n{gen_result.sql}")

    # ── Step 4: Execute on DuckDB ─────────────────────────────────────────
    exec_result = execute(gen_result.sql)

    if not exec_result.success:
        logger.error(f"[engine] Execution failed: {exec_result.error}")
        return NLPResult(
            success=False, query=text, sql=gen_result.sql,
            data=[], row_count=0,
            retrieved_tables=context.referenced_tables,
            cannot_answer=False, error=exec_result.error,
            insight=None, chart_path=None, chart_type=None,
            prompt_tokens=token_est if debug else 0,
            raw_response=gen_result.raw_response if debug else "",
        )

    logger.info(f"[engine] Execution success — {exec_result.row_count} row(s).")

    # ── Step 5: Synthesise insight ────────────────────────────────────────
    insight = _safe_synthesise(
        question=text,
        sql=gen_result.sql,
        tables=context.referenced_tables,
        data=exec_result.data,
    )

    # ── Step 6: Generate chart (returns Plotly JSON dict) ─────────────────
    chart_json, chart_type = _safe_chart(
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
        chart_path=chart_json,   # dict (Plotly JSON) or None
        chart_type=chart_type,
        prompt_tokens=token_est if debug else 0,
        raw_response=gen_result.raw_response if debug else "",
    )


# ─────────────────────────────────────────────────────────────────────────────
# INTERNAL HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _safe_synthesise(question, sql, tables, data) -> str | None:
    """Wraps synthesise() so failures never crash the pipeline."""
    try:
        result = synthesise(question=question, sql=sql, tables=tables, data=data)
        if not result.success:
            logger.warning(f"[engine] Synthesis soft-failed: {result.error}")
        return result.insight
    except Exception as e:
        logger.warning(f"[engine] Synthesis failed (non-fatal): {e}")
        return None


def _safe_chart(question, data, sql) -> tuple[dict | None, str | None]:
    """
    Wraps generate_chart() so failures never crash the pipeline.
    Returns (chart_json_dict, chart_type) or (None, None).
    """
    try:
        result = generate_chart(question=question, data=data, sql=sql)
        if result is None:
            logger.debug("[engine] No chart generated (data shape not suitable).")
            return None, None
        chart_json, chart_type = result
        logger.debug(f"[engine] Chart generated: {chart_type}")
        return chart_json, chart_type
    except Exception as e:
        logger.warning(f"[engine] Chart generation failed (non-fatal): {e}")
        return None, None


def _error_result(text: str, reason: str) -> NLPResult:
    return NLPResult(
        success=False, query=text, sql="", data=[], row_count=0,
        retrieved_tables=[], cannot_answer=False, error=reason,
        insight=None, chart_path=None, chart_type=None,
    )
