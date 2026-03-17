"""
etl/main.py

Frammer Analytics ETL Pipeline Orchestrator

Pipeline order:

1. Ingestion (load raw CSVs)
2. Transform (clean + build star schema)
3. Validation (data quality checks)

Run:
    python etl/main.py
"""

import os
import sys
import argparse
import logging
import duckdb

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ingestion.registry import FileRegistry
from ingestion.backfill import run_backfill
from ingestion.watcher import start_watcher
from transform import run_transform
from validation import run_validation


# ─────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────

WATCH_DIR = "./data/raw"
DB_PATH   = "frammer_analytics.duckdb"
REG_PATH  = "registry.db"


# ─────────────────────────────────────────────
# CLI arguments
# ─────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="Frammer Analytics Pipeline",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help=(
            "Wipe DuckDB and registry, then reprocess all CSVs from scratch.\n"
            "Use this when the schema changes or data is corrupted."
        )
    )
    parser.add_argument(
        "--watch-only",
        action="store_true",
        help=(
            "Skip backfill on startup. Only watch for new/changed files.\n"
            "Use this if DB is already in sync and you just want the watcher running."
        )
    )
    return parser.parse_args()

# ─────────────────────────────────────────────
# Reset helper
# ─────────────────────────────────────────────

def wipe_state():

    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        logger.warning("DuckDB wiped")

    if os.path.exists(REG_PATH):
        os.remove(REG_PATH)
        logger.warning("Registry wiped")


# ─────────────────────────────────────────────
# Main pipeline
# ─────────────────────────────────────────────

def run_pipeline(reset=False):

    logger.info("================================================")
    logger.info(" Frammer Analytics ETL Pipeline")
    logger.info("================================================")

    if reset:
        wipe_state()

    os.makedirs(WATCH_DIR, exist_ok=True)

    logger.info("Connecting to DuckDB...")
    conn = duckdb.connect(DB_PATH)

    registry = FileRegistry(REG_PATH)

    try:

        # ─────────────────────────────
        # 1. INGESTION
        # ─────────────────────────────

        logger.info("STEP 1 — Running ingestion layer")

        run_backfill(
            watch_dir=WATCH_DIR,
            registry=registry,
            duckdb_conn=conn,
            force=reset
        )

        logger.info("Ingestion completed")

        # ─────────────────────────────
        # 2. CREATE STAR SCHEMA
        # ─────────────────────────────

        logger.info("STEP 2 — Creating star schema tables")

        from schema_loader import load_star_schema

        load_star_schema(conn)

        logger.info("Star schema created")

        # ─────────────────────────────
        # 3. TRANSFORM
        # ─────────────────────────────

        logger.info("STEP 3 — Running transform layer")

        run_transform(conn)

        logger.info("Transform completed")

        conn.commit()

        # ─────────────────────────────
        # 4. VALIDATION
        # ─────────────────────────────

        logger.info("STEP 3 — Running validation checks")

        passed = run_validation(conn)

        if not passed:
            logger.error("Validation failed")
        else:
            logger.info("Validation passed")

    finally:

        conn.close()

    logger.info("================================================")
    logger.info(" Pipeline completed successfully")
    logger.info("================================================")


# ─────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────

if __name__ == "__main__":

    args = parse_args()

    run_pipeline(reset=args.reset)