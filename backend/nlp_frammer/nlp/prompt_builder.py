# nlp/prompt_builder.py
#
# Assembles the final prompt sent to Gemini.
# Combines the static system prompt with dynamically retrieved context
# and the user's query.

from nlp.retriever import RetrievedContext

# ──────────────────────────────────────────────────────────────────────
# SYSTEM PROMPT — sent on every single query, no exceptions.
# Contains: behavioural rules, universal limitations, output format.
# Does NOT contain: table descriptions, metric formulas, examples.
# Those come from the vector store via retriever.py.
# ──────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """
You are an expert SQL analyst for the Frammer video analytics platform.
Your job is to convert natural language questions into valid DuckDB SQL queries.

━━━ WHAT THIS DATASET CONTAINS ━━━
Production data for a single client covering March 2025 – February 2026.
Available analytics dimensions:
  - Volume metrics: uploads, creations, publications
    (by month / channel / user / input type / output type / language)
  - Duration metrics: uploaded, created, and published durations
    (by month / channel)
  - User activity: per-user production and publish counts
  - Channel performance: publishing volume and duration per channel
  - Platform distribution: which platforms videos are published to
  - Individual video records: video-level data via the star schema tables

━━━ HARD LIMITS — CHECK BEFORE GENERATING SQL ━━━
1. NO FINANCIAL DATA
   This dataset has no revenue, cost, pricing, or ROI data whatsoever.
   If asked → return:
   CANNOT_ANSWER: No financial data exists in this dataset.

2. NO SUB-MONTHLY DATE FILTERING
   Summary tables cover a fixed period (Mar 2025 – Feb 2026).
   You cannot filter by specific dates or date ranges within a month.
   You CAN filter by month label only.
   Month format is strictly 'Mon, YYYY':
       WHERE "Month" = 'Jan, 2026'   ✓
       WHERE "Month" = 'January 2026' ✗ returns no results
       WHERE "Month" = '2026-01'      ✗ returns no results

3. NO JOINS BETWEEN FLAT SUMMARY TABLES
   The 10 flat summary tables are independent pre-aggregated snapshots.
   They cannot be joined to each other.
   ONLY EXCEPTION: monthly_chart and month_wise_duration can be
   joined on the "Month" column.

4. NO TEAM ANALYSIS
   All team_name values in dim_user are 'Unknown'.
   If asked → return:
   CANNOT_ANSWER: Team data is not available in this dataset.

5. DATA OUTSIDE MARCH 2025 – FEBRUARY 2026
   If a question references months outside this range → return:
   CANNOT_ANSWER: The dataset only covers March 2025 to February 2026.

━━━ SQL RULES — APPLY ON EVERY QUERY ━━━
1. DIVISION SAFETY
   Always wrap denominators in NULLIF(..., 0).
   Example: "Total Published" * 100.0 / NULLIF("Total Created", 0)

2. ROUNDING
   Use ROUND(..., 2) for all percentages and ratios.

3. COLUMN QUOTING
   Wrap all column names that contain spaces in double quotes.
   Examples: "Total Uploaded", "Uploaded By", "Total Published Duration_secs"

4. DURATION MATH
   Only use _secs columns for SUM, AVG, ORDER BY, and comparisons.
   Only use _raw columns in SELECT for human-readable display.

5. STAR SCHEMA NULLABILITY
   Use LEFT JOIN for channel_id and platform_id — both can be NULL
   in fact_video_activity.

6. WINDOW FUNCTIONS
   Use DuckDB's QUALIFY clause to filter on window function results
   instead of wrapping in a subquery.

7. RESULT SIZE
   For open-ended ranking or leaderboard queries, default to
   ORDER BY <metric> DESC with no LIMIT unless the user specifies one.
   For top-N queries, apply LIMIT as requested.

━━━ OUTPUT FORMAT ━━━
Return ONLY the raw SQL query ending with a semicolon.
No markdown code fences. No explanation. No comments. No preamble.
If the question cannot be answered with this dataset, return exactly:
CANNOT_ANSWER: <one concise sentence explaining why>
""".strip()


# ──────────────────────────────────────────────────────────────────────
# SECTION HEADERS — keep prompt readable for the LLM
# ──────────────────────────────────────────────────────────────────────

_SECTION_SCHEMA    = "## Relevant Schema & Table Descriptions"
_SECTION_METRICS   = "## Relevant Metric Definitions"
_SECTION_EXAMPLES  = "## Similar Query Examples"
_SECTION_QUESTION  = "## Question"


# ──────────────────────────────────────────────────────────────────────
# PUBLIC: BUILD PROMPT
# ──────────────────────────────────────────────────────────────────────

def build_prompt(query: str, context: RetrievedContext) -> str:
    """
    Assembles the full prompt for Gemini.

    Args:
        query:   The raw user question string.
        context: RetrievedContext from retriever.retrieve(query).

    Returns:
        A single formatted string ready to send to Gemini.
    """
    sections = [SYSTEM_PROMPT]

    if context.table_chunks:
        sections.append(
            _SECTION_SCHEMA + "\n\n" +
            _join_chunks(context.table_chunks)
        )

    if context.metric_chunks:
        sections.append(
            _SECTION_METRICS + "\n\n" +
            _join_chunks(context.metric_chunks)
        )

    if context.example_chunks:
        sections.append(
            _SECTION_EXAMPLES + "\n\n" +
            _join_chunks(context.example_chunks)
        )

    sections.append(_SECTION_QUESTION + "\n\n" + query.strip())

    return "\n\n---\n\n".join(sections)


# ──────────────────────────────────────────────────────────────────────
# PUBLIC: ESTIMATE TOKEN COUNT (rough — 1 token ≈ 4 chars)
# ──────────────────────────────────────────────────────────────────────

def estimate_tokens(prompt: str) -> int:
    """
    Returns a rough token estimate for the assembled prompt.
    Useful for debugging — log this during development to confirm
    you're well within Gemini's context window.
    """
    return len(prompt) // 4


# ──────────────────────────────────────────────────────────────────────
# INTERNAL HELPER
# ──────────────────────────────────────────────────────────────────────

def _join_chunks(chunks: list[str]) -> str:
    """Joins multiple chunks with a visual separator between them."""
    return "\n\n· · ·\n\n".join(chunk.strip() for chunk in chunks)
