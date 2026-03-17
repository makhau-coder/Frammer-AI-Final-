"""
nlp/sql_generator.py

Sends the assembled prompt to Gemini and extracts SQL
(or CANNOT_ANSWER) from the reply.

Uses gemini-2.5-flash with thinking budget for significantly
better accuracy on complex multi-join / window function queries.
"""

import os
import re
import logging
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────

GEMINI_MODEL = "gemini-2.5-flash"

GENERATION_CONFIG = types.GenerateContentConfig(
    temperature     = 0.0,          # deterministic — same question → same SQL
    max_output_tokens = 8096,       # increased from 1024 to allow thinking + SQL
    candidate_count = 1,
    thinking_config = types.ThinkingConfig(
        thinking_budget = 1024,     # let Gemini reason before writing SQL
                                    # dramatically improves complex query accuracy
    ),
)


# ─────────────────────────────────────────────────────────────────────────────
# CLIENT
# ─────────────────────────────────────────────────────────────────────────────

def _get_client() -> genai.Client:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY environment variable is not set. "
            "Get a key at https://aistudio.google.com/app/apikey"
        )
    return genai.Client(api_key=api_key)


# ─────────────────────────────────────────────────────────────────────────────
# RETURN TYPE
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class GenerationResult:
    success:       bool   # True = valid SQL extracted
    sql:           str    # Raw SQL string if success, else ""
    cannot_answer: bool   # True if Gemini returned CANNOT_ANSWER
    reason:        str    # Populated if cannot_answer=True or error
    raw_response:  str    # Full raw text from Gemini (for debugging)


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC: GENERATE
# ─────────────────────────────────────────────────────────────────────────────

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
            model   = GEMINI_MODEL,
            contents= prompt,
            config  = GENERATION_CONFIG,
        )
        raw = response.text.strip()
        logger.debug(f"[sql_generator] Raw Gemini response:\n{raw}")

    except Exception as e:
        logger.error(f"[sql_generator] Gemini API call failed: {e}")
        return GenerationResult(
            success=False, sql="", cannot_answer=False,
            reason=f"Gemini API error: {str(e)}", raw_response="",
        )

    return _parse(raw)


# ─────────────────────────────────────────────────────────────────────────────
# INTERNAL: PARSE RESPONSE
# ─────────────────────────────────────────────────────────────────────────────

def _parse(raw: str) -> GenerationResult:
    """
    Parses Gemini's raw text into a GenerationResult.

    Handles:
      1. CANNOT_ANSWER: <reason>    → cannot_answer = True
      2. Valid SQL string            → success = True
      3. Markdown-fenced SQL         → strip fences, then success = True
      4. Anything else              → success = False
    """
    # ── Case 1: CANNOT_ANSWER ──────────────────────────────────────────────
    if raw.startswith("CANNOT_ANSWER"):
        reason = raw.split("CANNOT_ANSWER:")[-1].strip()
        return GenerationResult(
            success=False, sql="", cannot_answer=True,
            reason=reason, raw_response=raw,
        )

    # ── Case 2: Strip markdown fences defensively ─────────────────────────
    fenced = re.search(r"```(?:sql)?\s*(.*?)```", raw, re.DOTALL | re.IGNORECASE)
    if fenced:
        raw = fenced.group(1).strip()
        logger.warning("[sql_generator] Gemini returned markdown fences — stripped.")

    # ── Case 3: Validate it looks like SQL ────────────────────────────────
    sql_keywords = ("SELECT", "WITH", "INSERT", "UPDATE", "DELETE", "EXPLAIN")
    if not any(raw.upper().startswith(kw) for kw in sql_keywords):
        logger.error(f"[sql_generator] Response does not look like SQL:\n{raw}")
        return GenerationResult(
            success=False, sql="", cannot_answer=False,
            reason=f"Gemini returned unexpected response: {raw[:120]}",
            raw_response=raw,
        )

    # ── Ensure trailing semicolon ──────────────────────────────────────────
    sql = raw if raw.endswith(";") else raw + ";"

    return GenerationResult(
        success=True, sql=sql, cannot_answer=False,
        reason="", raw_response=raw,
    )
