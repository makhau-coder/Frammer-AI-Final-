"""
api/main.py — FastAPI application entry point

Start the server:
    uvicorn api.main:app --host localhost --port 8000

AUTO-REFRESH:
    When any CSV file in data/raw/ is saved/replaced, the server
    automatically runs the full ETL pipeline (ingest -> validate ->
    transform -> parquets) within ~3 seconds. No manual trigger needed.

NOTE: Run WITHOUT --reload flag when auto-watcher is active.
      uvicorn --reload conflicts with the file watcher on some systems.
"""

import os
import sys
import logging
import threading

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# ── Absolute backend root (works regardless of CWD) ──────────────────────────
_BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_ETL_ROOT     = os.path.join(_BACKEND_ROOT, "etl")

for _p in [_BACKEND_ROOT, _ETL_ROOT]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from config import API_HOST, API_PORT, DATA_PATH
from config import DATABASE_PATH as _DB_PATH
import os as _os
_os.environ["FRAMMER_DB_PATH"] = _DB_PATH

from api.routes.analytics import router as analytics_router
from api.routes.etl        import router as etl_router, _run_pipeline_task
from api.routes.kpis       import router as kpi_router
from api.routes.chat       import router as chat_router
from api.routes.data_quality import router as dq_router
# ...

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# App
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title       = "Frammer Analytics API",
    description = "Analytics API for the Frammer AI content platform",
    version     = "2.0.0",
    docs_url    = "/docs",
    redoc_url   = "/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins    = ["*"],
    allow_methods    = ["GET", "POST"],
    allow_headers    = ["*"],
    allow_credentials=True,
)

app.include_router(analytics_router)
app.include_router(etl_router)
app.include_router(kpi_router)
app.include_router(chat_router)
app.include_router(dq_router)


# ─────────────────────────────────────────────────────────────────────────────
# File watcher — auto-triggers full pipeline when CSVs change
# ─────────────────────────────────────────────────────────────────────────────

_DEBOUNCE_SECS  = 3.0
_PIPELINE_LOCK  = threading.Lock()
_DEBOUNCE_TIMER = None


def _schedule_pipeline(filepath: str) -> None:
    """
    Called by watchdog handler on CSV change.
    Debounce: waits 3s after last change before running pipeline.
    """
    global _DEBOUNCE_TIMER

    filename = os.path.basename(filepath)
    logger.info(f"[watcher] Change detected: {filename} — running ETL in {_DEBOUNCE_SECS}s")

    if _DEBOUNCE_TIMER is not None:
        _DEBOUNCE_TIMER.cancel()

    _DEBOUNCE_TIMER = threading.Timer(_DEBOUNCE_SECS, _fire_pipeline)
    _DEBOUNCE_TIMER.daemon = True
    _DEBOUNCE_TIMER.start()


def _fire_pipeline() -> None:
    """Run the full pipeline in a background thread. Skip if already running."""
    if not _PIPELINE_LOCK.acquire(blocking=False):
        logger.info("[watcher] Pipeline already running — skipping.")
        return
    try:
        logger.info("[watcher] Auto-triggering ETL pipeline ...")
        _run_pipeline_task(force=False)
        logger.info("[watcher] Auto-ETL complete.")
    finally:
        _PIPELINE_LOCK.release()


def _start_watcher() -> None:
    """Start watchdog observer on data/raw/ in a daemon thread."""
    import os # Just in case it isn't imported locally in this scope
    
    # ── FIX: Ensure the directory exists before watchdog tries to attach to it
    if not os.path.exists(DATA_PATH):
        try:
            os.makedirs(DATA_PATH, exist_ok=True)
            logger.info(f"[watcher] Created missing directory: {DATA_PATH}")
        except Exception as e:
            logger.warning(f"[watcher] Could not create {DATA_PATH}. Watcher disabled: {e}")
            return
    # ─────────────────────────────────────────────────────────

    try:
        from watchdog.observers import Observer
        from watchdog.events    import FileSystemEventHandler
        from etl.ingestion.config   import FILE_CONFIG
    except ImportError as e:
        logger.warning(f"[watcher] watchdog not available — auto-refresh disabled: {e}")
        return

    class _CSVHandler(FileSystemEventHandler):

        def _relevant(self, path: str) -> bool:
            return path.endswith(".csv") and os.path.basename(path) in FILE_CONFIG

        def on_created(self, event):
            if not event.is_directory and self._relevant(event.src_path):
                _schedule_pipeline(event.src_path)

        def on_modified(self, event):
            if not event.is_directory and self._relevant(event.src_path):
                _schedule_pipeline(event.src_path)

    observer = Observer()
    observer.schedule(_CSVHandler(), DATA_PATH, recursive=False)
    observer.daemon = True
    observer.start()
    app.state.watcher = observer
    logger.info(f"[watcher] Watching '{DATA_PATH}' for CSV changes ...")


# ─────────────────────────────────────────────────────────────────────────────
# Startup / Shutdown
# ─────────────────────────────────────────────────────────────────────────────

@app.on_event("startup")
def startup_tasks() -> None:
    # 1. Build missing cross parquets
    try:
        from etl.cross_parquet import build_cross_parquets
        results = build_cross_parquets(force=False)
        ok  = sum(1 for v in results.values() if str(v).startswith("ok"))
        skp = sum(1 for v in results.values() if v == "skipped")
        logger.info(f"[startup] Cross parquets: {ok} built, {skp} skipped.")
    except Exception as e:
        logger.warning(f"[startup] Cross parquet build skipped: {e}")

    # 2. Start file watcher
    _start_watcher()


@app.on_event("shutdown")
def shutdown_tasks() -> None:
    watcher = getattr(app.state, "watcher", None)
    if watcher:
        watcher.stop()
        watcher.join(timeout=5)
        logger.info("[shutdown] File watcher stopped.")
    if _DEBOUNCE_TIMER:
        _DEBOUNCE_TIMER.cancel()


# ─────────────────────────────────────────────────────────────────────────────
# Health
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/", tags=["health"])
def health():
    return {
        "status" : "ok",
        "service": "frammer-analytics-api",
        "version": "2.0.0",
        "watcher": "active" if getattr(app.state, "watcher", None) else "inactive",
    }


@app.get("/health", tags=["health"])
def health_detailed():
    import duckdb
    from config import DATABASE_PATH, PROCESSED_PATH

    db_ok      = os.path.exists(DATABASE_PATH)
    parquet_ok = (
        os.path.isdir(PROCESSED_PATH) and
        any(f.endswith(".parquet") for f in os.listdir(PROCESSED_PATH))
    )
    detail = {
        "database_exists"      : db_ok,
        "processed_data_exists": parquet_ok,
        "watcher_active"       : bool(getattr(app.state, "watcher", None)),
        "watching_dir"         : DATA_PATH,
    }
    if db_ok:
        try:
            con = duckdb.connect(DATABASE_PATH, read_only=True)
            tables = [t[0] for t in con.execute("SHOW TABLES").fetchall()]
            detail["tables"] = tables
            if "fact_video" in tables:
                detail["fact_video_rows"] = con.execute(
                    "SELECT COUNT(*) FROM fact_video"
                ).fetchone()[0]
            if "summary_stats" in tables:
                detail["summary_stats_ok"] = con.execute(
                    "SELECT COUNT(*) FROM summary_stats"
                ).fetchone()[0] > 0
            con.close()
        except Exception as exc:
            detail["db_error"] = str(exc)
    if os.path.isdir(PROCESSED_PATH):
        detail["parquet_files"] = sorted(
            f for f in os.listdir(PROCESSED_PATH) if f.endswith(".parquet")
        )
    detail["ready"] = db_ok and parquet_ok
    return detail


# ─────────────────────────────────────────────────────────────────────────────
# Dev runner
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host   = str(API_HOST),
        port   = int(API_PORT),
        reload = False,   # IMPORTANT: do not use reload=True with the file watcher
    )
