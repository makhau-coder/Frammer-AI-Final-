# nlp/executor.py
#
# Opens a fresh read-only DuckDB connection per query and closes immediately.
#
# WHY per-query (not persistent):
#   A persistent read_only=True connection blocks the ETL pipeline from opening
#   a write connection to the same file. DuckDB does not allow mixing read-only
#   and read-write connections on the same database file simultaneously.
#   POST /api/etl/run would fail with:
#     "Can't open a connection to same database file with a different configuration"
#
# Per-query has ~5ms overhead — negligible compared to Gemini API latency.

import os
from typing import Optional
import logging
import duckdb
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Fallback: nlp/executor.py -> nlp/ -> nlp_frammer/ -> backend/ -> frammer_analytics.duckdb
_FALLBACK_DB = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "frammer_analytics.duckdb")
)


def _get_db_path() -> str:
    """
    Resolve the DuckDB path at call time (not import time).

    Priority: FRAMMER_DB_PATH env var -> fallback sibling path.

    Guards against Windows absolute paths on Linux/Mac servers.
    On Windows itself (os.name == "nt") the path is used as-is.
    """
    raw = os.environ.get("FRAMMER_DB_PATH", "").strip()

    if not raw:
        return _FALLBACK_DB

    if len(raw) >= 2 and raw[1] == ":" and raw[0].isalpha() and os.name != "nt":
        logger.warning(
            f"[executor] FRAMMER_DB_PATH is a Windows path ({raw!r}) but "
            f"server is not Windows. Using fallback: {_FALLBACK_DB}"
        )
        return _FALLBACK_DB

    return os.path.normpath(raw)


# ──────────────────────────────────────────────────────────────────────
# RETURN TYPE
# ──────────────────────────────────────────────────────────────────────

@dataclass
class ExecutionResult:
    success:   bool
    data:      list[dict]
    row_count: int
    error:     Optional[str]


# ──────────────────────────────────────────────────────────────────────
# PUBLIC: EXECUTE
# ──────────────────────────────────────────────────────────────────────

def execute(sql: str) -> ExecutionResult:
    """
    Runs the given SQL against the DuckDB database (read-only).
    Opens a fresh connection per query and closes it immediately after,
    ensuring the ETL pipeline can always open a write connection.
    """
    db_path = _get_db_path()
    try:
        conn = duckdb.connect(db_path, read_only=True)
        rel  = conn.execute(sql)
        rows = rel.fetchall()
        cols = [desc[0] for desc in rel.description]
        conn.close()

        data = [dict(zip(cols, row)) for row in rows]

        return ExecutionResult(
            success=True,
            data=data,
            row_count=len(data),
            error=None,
        )

    except duckdb.Error as e:
        logger.error(f"[executor] DuckDB execution error:\nSQL: {sql}\nError: {e}")
        return ExecutionResult(
            success=False,
            data=[],
            row_count=0,
            error=str(e),
        )