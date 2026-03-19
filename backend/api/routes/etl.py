"""
api/routes/etl.py — ETL trigger endpoint

Routes:
  POST /api/etl/run     → trigger full pipeline (ingestion → validate → transform)
  GET  /api/etl/status  → last run status and timestamp

ROOT CAUSE OF "No module named 'ingestion'" ERROR:
  The files inside etl/ use bare imports like:
      from ingestion.registry import FileRegistry
      from ingestion.router   import route_file
  These work only when the etl/ directory itself is in sys.path.
  When called from the API, only backend/ is in sys.path, so Python
  looks for a top-level package called 'ingestion' and fails.

  FIX: add both backend/ AND backend/etl/ to sys.path before any ETL import.
"""

import os
import sys
import threading
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, HTTPException

# ── Absolute paths ────────────────────────────────────────────────────────────
# __file__ is  backend/api/routes/etl.py
_BACKEND_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)
# THE KEY FIX: etl/ must be on sys.path so that files inside it can do
#   from ingestion.registry import ...
#   from ingestion.router    import ...
# without those imports failing with "No module named 'ingestion'"
_ETL_ROOT = os.path.join(_BACKEND_ROOT, "etl")

for _p in [_BACKEND_ROOT, _ETL_ROOT]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

router = APIRouter(prefix="/api/etl", tags=["etl"])


# ─────────────────────────────────────────────────────────────────────────────
# In-memory run state
# ─────────────────────────────────────────────────────────────────────────────

_state: dict = {
    "status": "idle",
    "started_at": None,
    "finished_at": None,
    "message": "No run yet.",
    "lock": threading.Lock(),
}


def _set(msg=None, status=None, finished=False):
    """Thread-safe state update."""
    with _state["lock"]:
        if status:
            _state["status"] = status
        if msg:
            _state["message"] = msg
        if finished:
            _state["finished_at"] = datetime.utcnow().isoformat()


# ─────────────────────────────────────────────────────────────────────────────
# Background pipeline task
# ─────────────────────────────────────────────────────────────────────────────

def _run_pipeline_task(force: bool) -> None:
    """
    Runs the full ETL pipeline in a background thread.

    Step 1 — Backfill: load/update raw CSVs into DuckDB flat tables.
             Skips unchanged files (hash check) unless force=True.
    Step 2 — Validation: PASS/WARN/FAIL checks. Aborts if FAIL and not forced.
    Step 3 — Transform: clean -> star schema -> Parquet files -> summary_stats
             -> cross-dimension Parquets (all in one DuckDB connection).
    """
    _set(status="running", msg="Pipeline running: importing modules ...")
    with _state["lock"]:
        _state["started_at"] = datetime.utcnow().isoformat()
        _state["finished_at"] = None

    try:
        import duckdb

        # These imports work because _BACKEND_ROOT is in sys.path
        from config import DATABASE_PATH, DATA_PATH

        # These resolve because _ETL_ROOT (backend/etl/) is in sys.path,
        # matching how etl/main.py and the ingestion files import each other
        from etl.ingestion.registry import FileRegistry
        from etl.ingestion.backfill import run_backfill

        # These use the full package path from backend/
        from etl.validation import run_validation
        from etl.transform import run_transform

        registry_path = os.path.join(_BACKEND_ROOT, "registry.db")

        # ── Single connection for the whole pipeline ───────────────────────
        conn = duckdb.connect(DATABASE_PATH)

        # ── Step 1: Ingestion ──────────────────────────────────────────────
        _set(msg="Pipeline running: ingesting raw CSVs ...")
        registry = FileRegistry(registry_path)
        run_backfill(DATA_PATH, registry, conn, force=force)

        # ── Step 2: Validation ─────────────────────────────────────────────
        _set(msg="Pipeline running: validating data ...")
        passed = run_validation(conn)

        if not passed and not force:
            conn.close()
            _set(
                status="failed",
                msg=(
                    "Validation reported FAIL-level issues. "
                    "Retry with ?force=true to skip validation."
                ),
                finished=True,
            )
            return

        # ── Step 3: Transform + cross Parquets ────────────────────────────
        _set(msg="Pipeline running: transforming data and writing Parquet files ...")
        # internally calls build_cross_parquets(force=True)
        run_transform(conn)
        conn.close()

        _set(status="success", msg="Pipeline completed successfully.", finished=True)

    except Exception as exc:
        import traceback
        print(f"[etl] Pipeline failed:\n{traceback.format_exc()}")
        _set(
            status="failed",
            msg=f"Pipeline error: {exc}",
            finished=True,
        )


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

    Returns 202 immediately. Poll GET /api/etl/status to check progress.

    ?force=false (default)  skip unchanged files; abort on validation FAIL
    ?force=true             reprocess all files; ignore validation failures
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
        "message": "ETL pipeline started. Poll /api/etl/status for progress.",
    }


@router.get("/status")
def get_pipeline_status():
    """Return the status and timing of the last ETL run."""
    with _state["lock"]:
        return {
            "status": _state["status"],
            "started_at": _state["started_at"],
            "finished_at": _state["finished_at"],
            "message": _state["message"],
        }
