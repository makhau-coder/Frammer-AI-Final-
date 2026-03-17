import logging
from ingestion.config import FILE_CONFIG, Strategy
from ingestion.strategies.full_replace import ingest_full_replace
from ingestion.strategies.incremental import ingest_incremental

logger = logging.getLogger(__name__)

# Strategy dispatch table — maps each Strategy enum value to its function
STRATEGY_MAP = {
    Strategy.FULL_REPLACE: ingest_full_replace,
    Strategy.INCREMENTAL:  ingest_incremental,
}

def route_file(filepath: str, filename: str, duckdb_conn) -> int:
    """
    Looks up which strategy applies to this file and executes it.
    Returns the number of rows ingested.
    Raises ValueError for unknown files — never silently processes them.
    """
    if filename not in FILE_CONFIG:
        raise ValueError(
            f"Unknown file '{filename}' — not registered in FILE_CONFIG. "
            f"Add it to config.py before ingesting."
        )

    strategy = FILE_CONFIG[filename]
    ingest_fn = STRATEGY_MAP[strategy]

    logger.info(f"Routing '{filename}' → {strategy.value}")
    return ingest_fn(filepath, filename, duckdb_conn)
