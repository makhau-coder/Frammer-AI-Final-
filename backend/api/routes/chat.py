"""
api/routes/chat.py

NLQ Chatbot endpoint.

Two modes:
  POST /api/chat          → Standard JSON (full result in one response)
  GET  /api/chat/stream   → Server-Sent Events — streams steps progressively:
                            thinking → sql_ready → data_ready → insight_ready → chart_ready → done

The streaming endpoint is what the dashboard chatbot page uses so the user
sees live progress instead of a blank screen for 3–5 seconds.
"""

import json
import asyncio
import logging
import os
import sys
import time

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# ─────────────────────────────────────────────────────────────────────────────
# Correct sys.path — resolve relative to this file's location
# ─────────────────────────────────────────────────────────────────────────────

_BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_NLP_ROOT     = os.path.join(_BACKEND_ROOT, "nlp_frammer")

if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)
if _NLP_ROOT not in sys.path:
    sys.path.insert(0, _NLP_ROOT)

from nlp_frammer.nlp.engine import query as nlp_query

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["chat"])


# ─────────────────────────────────────────────────────────────────────────────
# Request / Response Models
# ─────────────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    question: str
    debug: bool = False


class ChatResponse(BaseModel):
    success:          bool
    question:         str
    sql:              str | None
    data:             list[dict]
    row_count:        int
    insight:          str | None
    chart_json:       dict | None   # Plotly JSON — frontend renders with Plotly.js
    chart_type:       str | None
    cannot_answer:    bool
    error:            str | None
    retrieved_tables: list[str]
    took_ms:          int


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/chat  — Standard (full response)
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    """
    Submit a natural language question and receive the full analytics result.

    Returns:
      - sql:        The generated DuckDB SQL
      - data:       Query result rows (list of dicts)
      - insight:    Gemini-synthesised natural language answer with explainability
      - chart_json: Plotly chart spec (pass directly to Plotly.js react component)
      - chart_type: e.g. "bar", "line", "heatmap", "dual_axis", "pie"
    """
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    t0     = time.monotonic()
    result = nlp_query(req.question.strip(), debug=req.debug)
    took   = int((time.monotonic() - t0) * 1000)

    # chart_path is now a dict (Plotly JSON) from the new chart_generator.py
    # Handle both old (str path) and new (dict) for backward compat
    chart_json = None
    if result.chart_path is not None:
        if isinstance(result.chart_path, dict):
            chart_json = result.chart_path
        else:
            # Legacy PNG path — skip (not usable by frontend)
            logger.warning("[chat] chart_path is a file path, not Plotly JSON — skipped")

    return ChatResponse(
        success          = result.success,
        question         = result.query,
        sql              = result.sql or None,
        data             = result.data,
        row_count        = result.row_count,
        insight          = result.insight,
        chart_json       = chart_json,
        chart_type       = result.chart_type,
        cannot_answer    = result.cannot_answer,
        error            = result.error,
        retrieved_tables = result.retrieved_tables,
        took_ms          = took,
    )


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/chat/stream  — SSE Streaming (for live dashboard chatbot)
# ─────────────────────────────────────────────────────────────────────────────

def _sse(event: str, data: dict) -> str:
    """Format a single SSE message."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.get("/chat/stream")
def chat_stream(
    question: str = Query(..., description="Natural language question"),
):
    """
    Server-Sent Events endpoint for the live chatbot UI.

    The frontend opens an EventSource to this endpoint and receives
    progressive updates as each pipeline stage completes:

      thinking      → "Analysing your question…"
      sql_ready     → { sql: "SELECT …" }
      data_ready    → { rows: [...], row_count: N }
      insight_ready → { insight: "The top channel is …" }
      chart_ready   → { chart_json: {...}, chart_type: "bar" }
      done          → { took_ms: N, retrieved_tables: [...] }
      error         → { message: "…" }

    Frontend usage (JavaScript):
        const es = new EventSource(`/api/chat/stream?question=...`);
        es.addEventListener("sql_ready",     e => console.log(JSON.parse(e.data)));
        es.addEventListener("insight_ready", e => showInsight(JSON.parse(e.data).insight));
        es.addEventListener("chart_ready",   e => renderPlotly(JSON.parse(e.data).chart_json));
        es.addEventListener("done",          e => es.close());
    """
    if not question.strip():
        raise HTTPException(status_code=400, detail="question cannot be empty.")

    async def stream():
        t0 = time.monotonic()

        yield _sse("thinking", {"message": "Analysing your question…"})

        # Run NLP pipeline in a thread so we don't block the event loop
        loop   = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, lambda: nlp_query(question.strip(), debug=False)
        )

        took = int((time.monotonic() - t0) * 1000)

        # ── Cannot answer ─────────────────────────────────────────────
        if result.cannot_answer:
            yield _sse("error", {
                "message"     : result.error or "This question cannot be answered with the available data.",
                "cannot_answer": True,
            })
            yield _sse("done", {"took_ms": took})
            return

        # ── Pipeline failed ───────────────────────────────────────────
        if not result.success:
            yield _sse("error", {
                "message"      : result.error or "An error occurred processing your question.",
                "cannot_answer": False,
                "sql"          : result.sql or None,
            })
            yield _sse("done", {"took_ms": took})
            return

        # ── SQL ready ─────────────────────────────────────────────────
        yield _sse("sql_ready", {"sql": result.sql})

        # ── Data ready ───────────────────────────────────────────────
        yield _sse("data_ready", {
            "rows"      : result.data,
            "row_count" : result.row_count,
        })

        # ── Insight ready ────────────────────────────────────────────
        if result.insight:
            yield _sse("insight_ready", {"insight": result.insight})

        # ── Chart ready ──────────────────────────────────────────────
        chart_json = None
        if result.chart_path is not None:
            if isinstance(result.chart_path, dict):
                chart_json = result.chart_path

        if chart_json:
            yield _sse("chart_ready", {
                "chart_json": chart_json,
                "chart_type": result.chart_type,
            })

        # ── Done ─────────────────────────────────────────────────────
        yield _sse("done", {
            "took_ms"         : took,
            "retrieved_tables": result.retrieved_tables,
        })

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control" : "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx buffering
        },
    )
