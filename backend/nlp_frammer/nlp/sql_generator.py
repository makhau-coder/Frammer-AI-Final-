# nlp/sql_generator.py
#
# Sends the assembled prompt to Gemini and extracts the SQL
# (or CANNOT_ANSWER response) from the reply.

import os
import re
import logging
from dotenv import load_dotenv

load_dotenv() 

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────────────────────────────

GEMINI_MODEL = "gemini-2.5-flash"   # upgrade to gemini-2.5-flash by June 2026

GENERATION_CONFIG = types.GenerateContentConfig(
    temperature=0.0,        # deterministic — same question = same SQL every time
    max_output_tokens=8192, # more than enough for any single SQL query
    candidate_count=1,
)

# ──────────────────────────────────────────────────────────────────────
# CLIENT — initialised once at module load
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
# RETURN TYPE
# ──────────────────────────────────────────────────────────────────────

from dataclasses import dataclass

@dataclass
class GenerationResult:
    success:        bool    # True = valid SQL extracted
                            # False = CANNOT_ANSWER or parsing failed
    sql:            str     # Raw SQL string if success, else ""
    cannot_answer:  bool    # True if Gemini returned CANNOT_ANSWER
    reason:         str     # Populated if cannot_answer=True or error
    raw_response:   str     # Full raw text from Gemini (for debugging)


# ──────────────────────────────────────────────────────────────────────
# PUBLIC: GENERATE
# ──────────────────────────────────────────────────────────────────────

def generate(prompt: str) -> GenerationResult:
    """
    Sends the prompt to Gemini and parses the response.

    Args:
        prompt: Fully assembled prompt from prompt_builder.build_prompt().

    Returns:
        GenerationResult with extracted SQL or CANNOT_ANSWER details.
    """
    client = _get_client()

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=GENERATION_CONFIG,
        )
        raw = response.text.strip()
        logger.debug(f"[sql_generator] Raw Gemini response:\n{raw}")

    except Exception as e:
        logger.error(f"[sql_generator] Gemini API call failed: {e}")
        return GenerationResult(
            success=False,
            sql="",
            cannot_answer=False,
            reason=f"Gemini API error: {str(e)}",
            raw_response="",
        )

    return _parse(raw)


# ──────────────────────────────────────────────────────────────────────
# INTERNAL: PARSE RESPONSE
# ──────────────────────────────────────────────────────────────────────

def _parse(raw: str) -> GenerationResult:
    """
    Parses Gemini's raw text response into a GenerationResult.

    Handles three cases:
      1. CANNOT_ANSWER: <reason>   → cannot_answer = True
      2. Valid SQL string           → success = True
      3. Anything else / unparseable → success = False
    """

    # ── Case 1: CANNOT_ANSWER ──────────────────────────────────────────
    if raw.startswith("CANNOT_ANSWER"):
        reason = raw.split("CANNOT_ANSWER:")[-1].strip()
        return GenerationResult(
            success=False,
            sql="",
            cannot_answer=True,
            reason=reason,
            raw_response=raw,
        )

    # ── Case 2: Gemini ignored instructions and wrapped in markdown fences
    # e.g. ```sql\nSELECT ...\n```  — strip them defensively
    fenced = re.search(r"```(?:sql)?\s*(.*?)```", raw, re.DOTALL | re.IGNORECASE)
    if fenced:
        raw = fenced.group(1).strip()
        logger.warning("[sql_generator] Gemini returned markdown fences — stripped.")

    # ── Case 3: Validate it looks like SQL ────────────────────────────
    sql_keywords = ("SELECT", "WITH", "INSERT", "UPDATE", "DELETE", "EXPLAIN")
    if not any(raw.upper().startswith(kw) for kw in sql_keywords):
        logger.error(f"[sql_generator] Response does not look like SQL:\n{raw}")
        return GenerationResult(
            success=False,
            sql="",
            cannot_answer=False,
            reason=f"Gemini returned an unexpected response: {raw[:120]}",
            raw_response=raw,
        )

    # ── Ensure it ends with a semicolon ───────────────────────────────
    sql = raw if raw.endswith(";") else raw + ";"

    return GenerationResult(
        success=True,
        sql=sql,
        cannot_answer=False,
        reason="",
        raw_response=raw,
    )
