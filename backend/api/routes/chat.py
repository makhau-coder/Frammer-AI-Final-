"""
api/routes/chat.py — NLP query endpoints

POST /api/chat              → natural language question (JSON response)
GET  /api/chat/stream       → same pipeline, SSE streaming (for Chatbot.jsx)
GET  /api/chat/chart/{id}   → serve the generated PNG chart

FIXES applied:
  1. Import path: 'from nlp.engine import ...' (sys.path already has nlp_frammer/)
  2. Unique thread_id per request — prevents LangGraph conversation history
     from one user polluting the next user's queries.
  3. Added GET /api/chat/stream SSE endpoint for Chatbot.jsx EventSource.
"""

import os
import sys
import json
import uuid
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

# ── Paths ─────────────────────────────────────────────────────────────────────
_BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_NLP_ROOT     = os.path.join(_BACKEND_ROOT, "nlp_frammer")

if _NLP_ROOT not in sys.path:
    sys.path.insert(0, _NLP_ROOT)

# ── Set env vars BEFORE importing any NLP modules ─────────────────────────────
# These must be set before any nlp.* import so executor.py and
# chart_generator.py pick them up via their lazy resolver functions.
from config import DATABASE_PATH as _OUR_DB
os.environ["FRAMMER_DB_PATH"] = _OUR_DB

_CHART_DIR = os.path.join(_BACKEND_ROOT, "data", "charts")
os.makedirs(_CHART_DIR, exist_ok=True)
os.environ["FRAMMER_CHART_DIR"] = _CHART_DIR

# ── Now safe to import NLP ────────────────────────────────────────────────────
# sys.path already has _NLP_ROOT = .../backend/nlp_frammer/
# so 'nlp.engine' resolves to nlp_frammer/nlp/engine.py  ✓
from nlp.engine import query, NLPResult

router = APIRouter(prefix="/api", tags=["chat"])
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Request / Response models
# ─────────────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    question:   str
    session_id: str | None = None   # Optional: caller can supply a stable session ID


class ChatResponse(BaseModel):
    # Pipeline status
    success:         bool
    question:        str

    # SQL + data
    sql:             str
    data:            list[dict]
    row_count:       int

    # Agent outputs
    insight:         str | None
    message:         str | None
    needs_input:     bool
    cannot_answer:   bool

    # Chart
    chart_url:       str | None
    chart_type:      str | None

    # Debug / metadata
    error:           str | None
    retrieved_tables: list[str]


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/chat  — JSON response
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    """
    Full NLP pipeline returning a single JSON response.

    Each request gets its own LangGraph thread_id so user sessions
    are isolated — no history leaking between separate requests.

    Optionally pass session_id in the request body to preserve
    multi-turn context within the same conversation session.
    """
    question = req.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    # FIX: Use a unique thread_id per request (or per session if provided).
    # The old code used a single global CONFIG with thread_id="main" which
    # caused conversation history from one user to pollute the next user's query.
    thread_id = req.session_id or str(uuid.uuid4())

    logger.info(f"[chat] POST {question!r} (thread={thread_id})")

    try:
        result: NLPResult = query(question, thread_id=thread_id)
    except Exception as e:
        logger.error(f"[chat] Pipeline crashed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"NLP error: {e}")

    chart_url = _build_chart_url(result.chart_path)

    return ChatResponse(
        success          = result.success,
        question         = result.query,
        sql              = result.sql or "",
        data             = result.data,
        row_count        = result.row_count,
        insight          = result.insight,
        message          = result.message,
        needs_input      = result.needs_input,
        cannot_answer    = result.cannot_answer,
        chart_url        = chart_url,
        chart_type       = result.chart_type,
        error            = result.error,
        retrieved_tables = result.retrieved_tables,
    )


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/chat/stream  — SSE streaming (consumed by Chatbot.jsx EventSource)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/chat/stream")
def chat_stream(question: str, session_id: str | None = None):
    """
    SSE streaming endpoint for Chatbot.jsx.

    EventSource (GET) emits events in order:
      sql_ready      { sql }
      data_ready     { rows, row_count }
      insight_ready  { insight }
      chart_ready    { chart_url, chart_type }   (only if chart generated)
      error          { message }                  (on failure/cannot_answer)
      done           {}
    """
    question = question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    thread_id = session_id or str(uuid.uuid4())
    logger.info(f"[chat] SSE {question!r} (thread={thread_id})")

    def _generate():
        try:
            result: NLPResult = query(question, thread_id=thread_id)
        except Exception as e:
            logger.error(f"[chat/stream] Pipeline crashed: {e}", exc_info=True)
            yield _sse("error", {"message": f"Internal error: {e}"})
            yield _sse("done", {})
            return

        # THE FIX: Send graceful rejections and clarifications as normal chat bubbles ("insight_ready")
        if result.cannot_answer or result.needs_input:
            yield _sse("insight_ready", {
                "insight": result.message or result.error or "I cannot answer this question right now."
            })
            yield _sse("done", {})
            return

        # THE FIX: Even if the SQL crashes, show the friendly error in the chat UI
        if not result.success and result.error:
            friendly_err = result.message if result.message else result.error
            yield _sse("insight_ready", {"insight": friendly_err})
            yield _sse("done", {})
            return

        if result.sql:
            yield _sse("sql_ready", {"sql": result.sql})

        if result.data:
            yield _sse("data_ready", {"rows": result.data, "row_count": result.row_count})

        if result.insight:
            yield _sse("insight_ready", {"insight": result.insight})

        chart_url = _build_chart_url(result.chart_path)
        if chart_url and result.chart_type:
            yield _sse("chart_ready", {"chart_url": chart_url, "chart_type": result.chart_type})

        if result.success and result.row_count == 0 and not result.insight:
            yield _sse("insight_ready", {
                "insight": result.message or "No results found for your query."
            })

        yield _sse("done", {})

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":               "no-cache",
            "X-Accel-Buffering":           "no",
            "Access-Control-Allow-Origin": "*",
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/chat/chart/{chart_id}  — serve PNG chart
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/chat/chart/{chart_id}")
def get_chart(chart_id: str):
    """
    Serve a generated Plotly chart PNG.
    chart_id = filename e.g. "3f2a1b4c.png"
    Charts are stored in backend/data/charts/ (set via FRAMMER_CHART_DIR).
    """
    if ".." in chart_id or "/" in chart_id or "\\" in chart_id:
        raise HTTPException(status_code=400, detail="Invalid chart ID.")

    path = os.path.join(_CHART_DIR, chart_id)

    if not os.path.exists(path):
        raise HTTPException(
            status_code=404,
            detail=f"Chart '{chart_id}' not found.",
        )

    return FileResponse(
        path,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _build_chart_url(chart_path: str | None) -> str | None:
    if chart_path and os.path.exists(chart_path):
        return f"/api/chat/chart/{os.path.basename(chart_path)}"
    return None


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"
