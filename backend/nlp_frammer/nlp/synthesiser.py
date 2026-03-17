# nlp/synthesiser.py
#
# Step 2 of the NLP pipeline.
# Takes the raw DuckDB result + SQL + original question
# and produces a natural language insight with explainability.
#
# Uses the same google.genai client pattern as sql_generator.py.


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
_MAX_ROWS_IN_PROMPT = 20

GEMINI_MODEL = "gemini-2.5-flash"

GENERATION_CONFIG = types.GenerateContentConfig(
    temperature=0.4,
    max_output_tokens=2048,
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
You are a data analyst assistant for Frammer, a video content production platform.

A SQL query has already been executed against the database. Your job is to:
1. Give a direct plain-English answer to the user's question.
2. Highlight the key insight or notable pattern visible in the data.
3. End with a single "Explainability:" line stating exactly which table,
   columns, filters (WHERE clauses), and aggregations were used.

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
RULES:
- Start with a direct 1-sentence answer.
- Follow with 2-3 sentences of supporting insight from the data only.
- End with exactly one line starting with "Explainability:" summarising
  the table, columns, WHERE/ORDER BY/LIMIT clauses applied.
- Plain English only. No markdown. No bullet points. No headers.
- Never invent numbers not present in the data above.
- If results are empty, say so and suggest why.
- Keep total response under 150 words.
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
        data=_compress_data(data),   # ← compact table, not json.dumps
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
