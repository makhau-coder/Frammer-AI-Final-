"""
api/routes/chat.py — NLP query endpoint

POST /api/chat              → natural language question through NLP pipeline
GET  /api/chat/chart/{id}   → serve the generated PNG chart

The NLP module is at backend/nlp_frammer/nlp/ — your friend's code, unchanged
except for the bugs fixed in this session (table names, chart dir, agent path).

This file handles:
  - sys.path so NLP imports resolve from nlp_frammer/
  - FRAMMER_DB_PATH override (Windows dev path → our DuckDB) before ANY import
  - FRAMMER_CHART_DIR set to backend/data/charts/ so charts persist and are serveable
  - Clean JSON response covering all NLPResult fields including new agent fields
  - PNG chart serving from backend/data/charts/
"""

import os
import sys
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

# ── Paths ─────────────────────────────────────────────────────────────────────
_BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_NLP_ROOT     = os.path.join(_BACKEND_ROOT, "nlp_frammer")

if _NLP_ROOT not in sys.path:
    sys.path.insert(0, _NLP_ROOT)

# ── Set env vars BEFORE importing any NLP modules ─────────────────────────────
# 1. FRAMMER_DB_PATH — executor.py reads this lazily but we set it early too
#    to handle any module-level reads.
from config import DATABASE_PATH as _OUR_DB
os.environ["FRAMMER_DB_PATH"] = _OUR_DB

# 2. FRAMMER_CHART_DIR — chart_generator.py reads this at module load.
#    Set to backend/data/charts/ so charts persist across restarts and
#    can be served by this file's GET endpoint.
_CHART_DIR = os.path.join(_BACKEND_ROOT, "data", "charts")
os.makedirs(_CHART_DIR, exist_ok=True)
os.environ["FRAMMER_CHART_DIR"] = _CHART_DIR

# ── Now safe to import NLP ────────────────────────────────────────────────────
from nlp_frammer.nlp.engine import query, NLPResult

router    = APIRouter(prefix="/api", tags=["chat"])
logger    = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Request / Response models
# ─────────────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    question: str


class ChatResponse(BaseModel):
    # Pipeline status
    success:         bool
    question:        str

    # SQL + data
    sql:             str
    data:            list[dict]
    row_count:       int

    # Agent outputs
    insight:         str | None   # Gemini natural language synthesis
    message:         str | None   # Final user-facing message from agent
                                  #   (clarification question or cannot_answer text)
    needs_input:     bool         # True = agent is asking a follow-up question
    cannot_answer:   bool         # True = question is out of scope

    # Chart
    chart_url:       str | None   # e.g. /api/chat/chart/<id>.png
    chart_type:      str | None   # "line", "bar", "heatmap", "dual_axis"

    # Debug / metadata
    error:           str | None
    retrieved_tables: list[str]


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/chat
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    """
    Full NLP pipeline:
      1. ChromaDB retrieval  — schema + metric + few-shot examples
      2. LangGraph agent     — Gemini SQL generation with entity resolution,
                               DuckDB execution, empty-result handling
      3. Gemini synthesis    — natural language insight from result rows
      4. Chart generation    — Plotly PNG saved to backend/data/charts/

    If the agent needs clarification (e.g. ambiguous user name):
      → success=False, needs_input=True, message="Did you mean X or Y?"

    If the question is out of scope:
      → success=False, cannot_answer=True, message="<reason> | <suggestion>"
    """
    question = req.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    logger.info(f"[chat] {question!r}")

    try:
        result: NLPResult = query(question)
    except Exception as e:
        logger.error(f"[chat] Pipeline crashed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"NLP error: {e}")

    # Build chart URL — served from backend/data/charts/ via GET /api/chat/chart/<id>
    chart_url = None
    if result.chart_path and os.path.exists(result.chart_path):
        chart_url = f"/api/chat/chart/{os.path.basename(result.chart_path)}"
        logger.info(f"[chat] Chart: {result.chart_type} → {chart_url}")

    return ChatResponse(
        success          = result.success,
        question         = result.query,
        sql              = result.sql or "",
        data             = result.data,
        row_count        = result.row_count,
        insight          = result.insight,
        message          = result.message,          # agent clarification / cannot_answer text
        needs_input      = result.needs_input,      # True = agent asked a question
        cannot_answer    = result.cannot_answer,
        chart_url        = chart_url,
        chart_type       = result.chart_type,
        error            = result.error,
        retrieved_tables = result.retrieved_tables,
    )


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/chat/chart/{chart_id}
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/chat/chart/{chart_id}")
def get_chart(chart_id: str):
    """
    Serve a generated Plotly chart PNG.
    chart_id = filename e.g. "3f2a1b4c.png"
    Charts are stored in backend/data/charts/ (set via FRAMMER_CHART_DIR).
    """
    # Sanitise — prevent path traversal
    if ".." in chart_id or "/" in chart_id or "\\" in chart_id:
        raise HTTPException(status_code=400, detail="Invalid chart ID.")

    path = os.path.join(_CHART_DIR, chart_id)

    if not os.path.exists(path):
        raise HTTPException(
            status_code=404,
            detail=f"Chart '{chart_id}' not found. It may not have been generated yet."
        )

    return FileResponse(
        path,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )