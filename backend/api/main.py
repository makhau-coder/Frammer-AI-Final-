"""
main.py — FastAPI application entry point

Start the server:
    uvicorn api.main:app --reload --host localhost --port 8000
"""

import os
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import API_HOST, API_PORT
from api.routes.analytics import router as analytics_router
from api.routes.etl import router as etl_router
# from api.routes.multidim import router as multidim_router
from api.routes.kpis import router as kpi_router
from api.routes.chat import router as chat_router
from api.routes.analytics import generate_cross_parquets


# ─────────────────────────────────────────────
# FastAPI App
# ─────────────────────────────────────────────

app = FastAPI(
    title="Frammer Analytics API",
    description="Analytics API for the Frammer content platform",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ─────────────────────────────────────────────
# CORS
# ─────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────
# Routers
# ─────────────────────────────────────────────

app.include_router(analytics_router)
app.include_router(etl_router)
# app.include_router(multidim_router)
app.include_router(kpi_router)
app.include_router(chat_router)

@app.on_event("startup")
def startup_tasks():
    """Auto-build cross parquets if any are missing when server starts."""
    try:
        from etl.cross_parquet import build_cross_parquets
        build_cross_parquets(force=False)   # force=False = skip if already exist
        print("Cross parquet datasets ready.")
    except Exception as e:
        print(f"[startup] Cross parquet generation warning: {e}")

# ─────────────────────────────────────────────
# Health Check
# ─────────────────────────────────────────────

@app.get("/", tags=["health"])
def health():
    return {"status": "ok", "service": "frammer-analytics-api"}


@app.get("/health", tags=["health"])
def health_detailed():

    import duckdb
    from config import DATABASE_PATH, PROCESSED_PATH

    db_ok = os.path.exists(DATABASE_PATH)

    parquet_ok = (
        os.path.isdir(PROCESSED_PATH)
        and any(f.endswith(".parquet") for f in os.listdir(PROCESSED_PATH))
    )

    detail = {
        "database_exists": db_ok,
        "processed_data_exists": parquet_ok,
    }

    if db_ok:

        try:

            con = duckdb.connect(DATABASE_PATH, read_only=True)

            tables = con.execute("SHOW TABLES").fetchall()

            detail["tables"] = [t[0] for t in tables]

            detail["fact_video_rows"] = con.execute(
                "SELECT COUNT(*) FROM fact_video"
            ).fetchone()[0]

            detail["dim_users"] = con.execute(
                "SELECT COUNT(*) FROM dim_user"
            ).fetchone()[0]

            detail["dim_platforms"] = con.execute(
                "SELECT COUNT(*) FROM dim_platform"
            ).fetchone()[0]

            detail["dim_teams"] = con.execute(
                "SELECT COUNT(*) FROM dim_team"
            ).fetchone()[0]

            detail["dim_input_types"] = con.execute(
                "SELECT COUNT(*) FROM dim_input_type"
            ).fetchone()[0]

            con.close()

        except Exception as exc:

            detail["db_error"] = str(exc)

    detail["ready"] = db_ok and parquet_ok

    return detail


# ─────────────────────────────────────────────
# Dev Runner
# ─────────────────────────────────────────────

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        "api.main:app",
        host=str(API_HOST),
        port=int(API_PORT),
        reload=True,
    )
