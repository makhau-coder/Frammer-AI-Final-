# nlp/synthesiser.py
#
# Step 2 of the NLP pipeline.
# Takes the raw DuckDB result + SQL + original question
# and produces a natural language insight with explainability.
#
# Uses the same google.genai client pattern as sql_generator.py.
#
# Streaming:
#   synthesise()        — original blocking call, returns SynthesisResult.
#                         Used internally by the LangGraph agent node.
#   synthesise_stream() — generator that yields text chunks as they arrive.
#                         Used by engine.query_stream() for low-latency output.


import os
import logging
from dataclasses import dataclass
from dotenv import load_dotenv


load_dotenv()


from google import genai
from google.genai import types


logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────────────────────────────


# Controls how many rows are sent to Gemini for synthesis.
# Lower = fewer tokens consumed = more room for the insight response.
_MAX_ROWS_IN_PROMPT = 100


GEMINI_MODEL = "gemini-2.5-flash"


GENERATION_CONFIG = types.GenerateContentConfig(
    temperature=0.6,       # slightly higher than before (was 0.4) — more expressive prose
    max_output_tokens=8192,
    candidate_count=1,
)


# ──────────────────────────────────────────────────────────────────────
# CLIENT — same pattern as sql_generator.py
# ──────────────────────────────────────────────────────────────────────


def _get_client() -> genai.Client:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY environment variable is not set. "
            "Get a key at https://aistudio.google.com/app/apikey"
        )
    return genai.Client(api_key=api_key)


# ──────────────────────────────────────────────────────────────────────
# PROMPT TEMPLATE
# ──────────────────────────────────────────────────────────────────────


SYNTHESIS_PROMPT = """
You are a senior data analyst for Frammer, a video content production platform.
A SQL query has already been executed. Your job is to deliver a thorough, insightful
analysis — not just a summary of what the data says, but what it MEANS.

---
USER QUESTION:
{question}

---
SQL EXECUTED:
{sql}

---
TABLES USED:
{tables}

---
FILTERS / DIMENSIONS APPLIED:
{filters}

---
QUERY RESULTS ({row_count} row(s)):
{data}

---
RESPONSE STRUCTURE — follow this order exactly:

**Direct Answer**
One clear sentence that directly answers the user's question with the key number or fact.

**Data Breakdown**
Walk through the most important values in the result set. Call out the highest, lowest,
and any outliers. If there are multiple rows, rank or compare them. Be specific —
use actual numbers from the data.

**Derived Insights**
This is where you go beyond the raw data. Compute or reason about metrics the user
did not explicitly ask for but which illuminate the data further. Examples:
- If given upload + published counts, derive and comment on publish rate even if not asked.
- If given monthly counts, comment on the trend direction (growth, decline, plateau).
- If given per-user data, comment on the spread — is one user dominant, or is it distributed?
- If given duration data, convert to meaningful units (hours, minutes per clip) and interpret.
- Flag any anomalies: a month with zero publications, a user with very high creation but
  zero publishes, a channel that seems inactive, a compression ratio that is unusually high/low.
- If the data suggests a seasonal pattern, workload spike, or pipeline bottleneck — say so.

**Explainability**
End with exactly one line starting with "Explainability:" naming the table, columns used,
and any WHERE / ORDER BY / LIMIT clauses applied.

---
RULES:
- Anchor every number you state to the data provided — never invent figures.
- Derived metrics (e.g. publish rate, averages, ratios) computed from the data ARE allowed
  and encouraged — just label them clearly as derived (e.g. "giving a derived publish rate of...").
- Use light markdown: **bold** for key numbers and entity names, no headers beyond the
  structure above.
- If results are empty, say so clearly and suggest the most likely reason.
- Prioritise insight density over length — every sentence should add value.
  Skip filler phrases like "It is worth noting that..." or "This is interesting because...".
""".strip()


# ──────────────────────────────────────────────────────────────────────
# RETURN TYPE
# ──────────────────────────────────────────────────────────────────────


@dataclass
class SynthesisResult:
    success:      bool
    insight:      str
    raw_response: str
    error:        str | None


# ──────────────────────────────────────────────────────────────────────
# INTERNAL HELPERS
# ──────────────────────────────────────────────────────────────────────


def _extract_filters(sql: str) -> str:
    """
    Pulls WHERE / HAVING / QUALIFY lines and summarises ORDER BY + LIMIT.
    Skips GROUP BY — not useful for explainability prose.
    """
    filters = []

    for line in sql.split("\n"):
        stripped = line.strip()
        if any(stripped.upper().startswith(kw) for kw in (
            "WHERE", "HAVING", "QUALIFY",
        )):
            filters.append(stripped)

    # ORDER BY — first occurrence only
    order_line = next(
        (l.strip() for l in sql.split("\n")
         if l.strip().upper().startswith("ORDER BY")), None
    )
    if order_line:
        filters.append(order_line)

    # LIMIT — first occurrence only
    limit_line = next(
        (l.strip() for l in sql.split("\n")
         if l.strip().upper().startswith("LIMIT")), None
    )
    if limit_line:
        filters.append(limit_line)

    return "\n".join(filters) if filters else "None (full table scan)"


def _compress_data(data: list[dict]) -> str:
    """
    Converts row dicts into a compact pipe-delimited table string.
    Avoids JSON punctuation overhead — same numbers, far fewer tokens.
    Rows shown is controlled by _MAX_ROWS_IN_PROMPT.
    """
    if not data:
        return "(no rows)"

    rows = data[:_MAX_ROWS_IN_PROMPT]
    cols = list(rows[0].keys())

    lines = [" | ".join(cols)]
    lines.append("-" * len(lines[0]))

    for row in rows:
        lines.append(" | ".join(str(row.get(c, "")) for c in cols))

    if len(data) > _MAX_ROWS_IN_PROMPT:
        lines.append(f"... ({len(data) - _MAX_ROWS_IN_PROMPT} more rows not shown)")

    return "\n".join(lines)


def _build_prompt(
    question: str,
    sql: str,
    tables: list[str],
    data: list[dict],
) -> str:
    return SYNTHESIS_PROMPT.format(
        question=question,
        sql=sql,
        tables=", ".join(tables) if tables else "unknown",
        filters=_extract_filters(sql),
        row_count=len(data),
        data=_compress_data(data),
    )


# ──────────────────────────────────────────────────────────────────────
# PUBLIC: SYNTHESISE
# ──────────────────────────────────────────────────────────────────────


def synthesise(
    question: str,
    sql: str,
    tables: list[str],
    data: list[dict],
) -> SynthesisResult:
    """
    Generates a natural language insight from raw query results.

    Args:
        question: Original user question.
        sql:      SQL that was executed.
        tables:   List of table names referenced.
        data:     Raw query results as list of row dicts.

    Returns:
        SynthesisResult with insight string and success flag.
    """
    if not data:
        return SynthesisResult(
            success=True,
            insight=(
                "The query returned no results. "
                "This may mean no data matches the specified filters, "
                "or the value you searched for does not exist in the dataset."
            ),
            raw_response="",
            error=None,
        )

    prompt = _build_prompt(question, sql, tables, data)
    client = _get_client()

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=GENERATION_CONFIG,
        )
        raw = response.text.strip()

        # ── Guard: warn if response was cut mid-generation ────────────
        candidate = response.candidates[0] if response.candidates else None
        if candidate:
            finish_reason = str(candidate.finish_reason)
            logger.debug(f"[synthesiser] finish_reason: {finish_reason}")
            if "MAX_TOKENS" in finish_reason:
                logger.warning(
                    "[synthesiser] Response hit max_output_tokens — "
                    f"insight may be truncated. "
                    f"Consider reducing _MAX_ROWS_IN_PROMPT (currently {_MAX_ROWS_IN_PROMPT})."
                )

        logger.debug(f"[synthesiser] Raw Gemini response:\n{raw}")

    except Exception as e:
        logger.error(f"[synthesiser] Gemini API call failed: {e}")
        return SynthesisResult(
            success=False,
            insight="Results retrieved successfully, but insight generation failed.",
            raw_response="",
            error=f"Gemini API error: {str(e)}",
        )

    if not raw:
        return SynthesisResult(
            success=False,
            insight="Results retrieved successfully, but insight generation returned empty.",
            raw_response=raw,
            error="Empty response from Gemini.",
        )

    return SynthesisResult(
        success=True,
        insight=raw,
        raw_response=raw,
        error=None,
    )


# ──────────────────────────────────────────────────────────────────────
# PUBLIC: SYNTHESISE_STREAM
# ──────────────────────────────────────────────────────────────────────


def synthesise_stream(
    question: str,
    sql: str,
    tables: list[str],
    data: list[dict],
):
    """
    Streaming version of synthesise().

    Yields text chunks (str) as they arrive from the Gemini API, so the
    caller can print or forward them immediately without waiting for the
    full response.  The complete accumulated text is yielded as the very
    last item wrapped in a SynthesisResult — this lets engine.py capture
    the final insight string for NLPResult without a second API call.

    Yield protocol:
        str             — incremental text chunk (print these immediately)
        SynthesisResult — final item; always the last thing yielded.
                          Signals end-of-stream and carries the complete insight.

    Caller pattern:
        for chunk in synthesise_stream(...):
            if isinstance(chunk, str):
                print(chunk, end="", flush=True)
            else:
                result = chunk   # SynthesisResult

    Args:
        question: Original user question.
        sql:      SQL that was executed.
        tables:   List of table names referenced.
        data:     Raw query results as list of row dicts.
    """
    # ── Fast-path: no data — yield the static message immediately ────
    if not data:
        static = (
            "The query returned no results. "
            "This may mean no data matches the specified filters, "
            "or the value you searched for does not exist in the dataset."
        )
        yield static
        yield SynthesisResult(success=True, insight=static, raw_response="", error=None)
        return

    prompt = _build_prompt(question, sql, tables, data)
    client = _get_client()

    accumulated = []

    try:
        for chunk in client.models.generate_content_stream(
            model=GEMINI_MODEL,
            contents=prompt,
            config=GENERATION_CONFIG,
        ):
            # chunk.text can be None on the final usage-only chunk
            text = chunk.text or ""
            if text:
                accumulated.append(text)
                yield text  # ← caller prints this immediately

    except Exception as e:
        logger.error(f"[synthesiser] Streaming Gemini API call failed: {e}")
        fallback = "Results retrieved successfully, but insight generation failed."
        yield fallback
        yield SynthesisResult(
            success=False,
            insight=fallback,
            raw_response="",
            error=f"Gemini API error: {str(e)}",
        )
        return

    full_text = "".join(accumulated).strip()

    if not full_text:
        fallback = "Results retrieved successfully, but insight generation returned empty."
        yield fallback
        yield SynthesisResult(
            success=False,
            insight=fallback,
            raw_response="",
            error="Empty response from Gemini.",
        )
        return

    logger.debug(f"[synthesiser] Streamed insight ({len(full_text)} chars)")

    # Final sentinel — carries the complete insight for NLPResult
    yield SynthesisResult(
        success=True,
        insight=full_text,
        raw_response=full_text,
        error=None,
    )
