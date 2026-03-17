"""
api/routes/etl.py — ETL trigger endpoint

Routes:
  POST /api/etl/run     → trigger full pipeline (ingestion → transform → cross parquets)
  GET  /api/etl/status  → last run status and timestamp
"""

import os
import sys
import threading
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, HTTPException

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

router = APIRouter(prefix="/api/etl", tags=["etl"])

# ─────────────────────────────────────────────────────────────────────────────
# In-memory run state
# ─────────────────────────────────────────────────────────────────────────────

_state: dict = {
    "status"     : "idle",
    "started_at" : None,
    "finished_at": None,
    "message"    : "No run yet.",
    "lock"       : threading.Lock(),
}


def _run_pipeline_task(force: bool) -> None:
    """
    Background task: runs the full ETL pipeline and updates _state.

    FIX 1: Set status to 'running' BEFORE starting any work (was after).
    FIX 2: Removed the non-existent run_ingestion() call.
    Correct order: set state → backfill → validate → transform → cross parquets
    """
    # ── Set state to running FIRST (race condition fix) ────────────────────
    with _state["lock"]:
        _state["status"]      = "running"
        _state["started_at"]  = datetime.utcnow().isoformat()
        _state["finished_at"] = None
        _state["message"]     = "Pipeline running: ingestion …"

    try:
        import duckdb
        from config import DATABASE_PATH
        from etl.ingestion.registry import FileRegistry
        from etl.ingestion.backfill import run_backfill
        from etl.validation import run_validation
        from etl.transform import run_transform
        from etl.cross_parquet import build_cross_parquets

        # ── Step 1: Ingestion ──────────────────────────────────────────────
        with _state["lock"]:
            _state["message"] = "Pipeline running: loading raw CSVs …"

        conn = duckdb.connect(DATABASE_PATH)
        registry = FileRegistry()
        run_backfill("./data/raw", registry, conn, force=force)
        conn.close()

        # ── Step 2: Validation ─────────────────────────────────────────────
        with _state["lock"]:
            _state["message"] = "Pipeline running: validating data …"

        conn2  = duckdb.connect(DATABASE_PATH)
        passed = run_validation(conn2)
        conn2.close()

        if not passed and not force:
            with _state["lock"]:
                _state["status"]      = "failed"
                _state["finished_at"] = datetime.utcnow().isoformat()
                _state["message"]     = (
                    "Validation reported FAIL-level issues. "
                    "Use ?force=true to proceed anyway."
                )
            return

        # ── Step 3: Transform + Cross Parquets ────────────────────────────
        with _state["lock"]:
            _state["message"] = "Pipeline running: transforming and building parquets …"

        conn3 = duckdb.connect(DATABASE_PATH)
        run_transform(conn3)   # transform now calls build_cross_parquets internally
        conn3.close()

        with _state["lock"]:
            _state["status"]      = "success"
            _state["finished_at"] = datetime.utcnow().isoformat()
            _state["message"]     = "Pipeline completed successfully."

    except Exception as exc:
        with _state["lock"]:
            _state["status"]      = "failed"
            _state["finished_at"] = datetime.utcnow().isoformat()
            _state["message"]     = f"Pipeline error: {exc}"


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/run")
def trigger_pipeline(
    background_tasks: BackgroundTasks,
    force: bool = False,
):
    """
    Trigger the full ETL pipeline in the background.

    Returns immediately with 202 Accepted.
    Poll GET /api/etl/status to check progress.
    Pass ?force=true to skip validation failures and reprocess all files.
    """
    with _state["lock"]:
        if _state["status"] == "running":
            raise HTTPException(
                status_code=409,
                detail="Pipeline is already running. Check /api/etl/status.",
            )

    background_tasks.add_task(_run_pipeline_task, force)
    return {
        "accepted": True,
        "message" : "ETL pipeline started. Poll /api/etl/status for progress.",
    }


@router.get("/status")
def get_pipeline_status():
    """Return the status and timing of the last ETL run."""
    with _state["lock"]:
        return {
            "status"     : _state["status"],
            "started_at" : _state["started_at"],
            "finished_at": _state["finished_at"],
            "message"    : _state["message"],
        }
