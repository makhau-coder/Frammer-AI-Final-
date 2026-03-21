# nlp/executor.py
#
# MERGED — combines YOUR lazy path fix + FRIEND's persistent connection:
#
# YOUR fix kept:
#   - _get_db_path() resolves DB path lazily at call time (not import time)
#   - Windows drive-letter guard (C:, D:, E:, ...) — falls back to relative path
#   - Fallback path: nlp/executor.py → nlp/ → nlp_frammer/ → backend/
#
# FRIEND's improvement added:
#   - Persistent module-level DuckDB connection (_conn) — opened once, reused
#   - Auto-reconnect on ConnectionException (one retry before failing)
#   - No open/close overhead per query
#
# NOTE: The persistent connection uses _get_db_path() so it still resolves
# lazily and correctly handles the Windows path guard.

import os
import logging
import duckdb
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Fallback: nlp/executor.py → nlp/ → nlp_frammer/ → backend/ → frammer_analytics.duckdb
_FALLBACK_DB = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "frammer_analytics.duckdb")
)


def _get_db_path() -> str:
    """
    Resolve the DuckDB path at call time (not import time).

    Priority: FRAMMER_DB_PATH env var → fallback sibling path.

    Guards against Windows absolute paths on Linux/Mac servers —
    i.e. when a dev's Windows .env is accidentally used in production.
    On Windows itself (os.name == "nt") the path is used as-is.
    """
    raw = os.environ.get("FRAMMER_DB_PATH", "").strip()

    if not raw:
        return _FALLBACK_DB

    # Only redirect Windows drive-letter paths when running on a non-Windows OS.
    # On Windows (os.name == "nt") the path is valid and should be used directly.
    if len(raw) >= 2 and raw[1] == ":" and raw[0].isalpha() and os.name != "nt":
        logger.warning(
            f"[executor] FRAMMER_DB_PATH is a Windows path ({raw!r}) but "
            f"server is not Windows. Using fallback: {_FALLBACK_DB}"
        )
        return _FALLBACK_DB

    return os.path.normpath(raw)


# ──────────────────────────────────────────────────────────────────────
# PERSISTENT CONNECTION — opened once, reused for all queries
# ──────────────────────────────────────────────────────────────────────

def _open_connection() -> duckdb.DuckDBPyConnection:
    db_path = _get_db_path()
    try:
        conn = duckdb.connect(db_path, read_only=True)
        logger.info(f"[executor] DuckDB connection opened: {db_path}")
        return conn
    except duckdb.Error as e:
        logger.critical(f"[executor] Failed to open DuckDB at {db_path}: {e}")
        raise


_conn: duckdb.DuckDBPyConnection = _open_connection()


# ──────────────────────────────────────────────────────────────────────
# RETURN TYPE
# ──────────────────────────────────────────────────────────────────────

@dataclass
class ExecutionResult:
    success:   bool
    data:      list[dict]   # rows as list of column→value dicts
    row_count: int
    error:     str | None


# ──────────────────────────────────────────────────────────────────────
# PUBLIC: EXECUTE
# ──────────────────────────────────────────────────────────────────────

def execute(sql: str) -> ExecutionResult:
    """
    Runs the given SQL against the DuckDB database (read-only).
    Uses a persistent module-level connection — no open/close per query.
    Auto-reconnects once if the connection is lost.

    Args:
        sql: A valid DuckDB SQL string ending with a semicolon.

    Returns:
        ExecutionResult with rows as list of dicts, or error details.
    """
    global _conn

    try:
        rel  = _conn.execute(sql)
        rows = rel.fetchall()
        cols = [desc[0] for desc in rel.description]
        data = [dict(zip(cols, row)) for row in rows]

        return ExecutionResult(
            success=True,
            data=data,
            row_count=len(data),
            error=None,
        )

    except duckdb.ConnectionException as e:
        # Connection was closed or invalidated — attempt one reconnect
        logger.warning(f"[executor] Connection lost, attempting reconnect: {e}")
        try:
            _conn = _open_connection()
            rel   = _conn.execute(sql)
            rows  = rel.fetchall()
            cols  = [desc[0] for desc in rel.description]
            data  = [dict(zip(cols, row)) for row in rows]
            return ExecutionResult(
                success=True,
                data=data,
                row_count=len(data),
                error=None,
            )
        except duckdb.Error as retry_e:
            logger.error(f"[executor] Reconnect failed: {retry_e}")
            return ExecutionResult(success=False, data=[], row_count=0, error=str(retry_e))

    except duckdb.Error as e:
        logger.error(f"[executor] DuckDB execution error:\nSQL: {sql}\nError: {e}")
        return ExecutionResult(
            success=False,
            data=[],
            row_count=0,
            error=str(e),
        )