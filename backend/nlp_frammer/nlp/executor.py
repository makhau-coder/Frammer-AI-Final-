# nlp/executor.py
#
# Executes validated SQL against the DuckDB analytics database
# and formats the result into a clean list of dicts.
#
# FIX (CRITICAL): DB path is now resolved lazily inside _get_db_path(),
# called on every execute() invocation — NOT at module load time.
#
# The old code read FRAMMER_DB_PATH at the module level:
#   DUCKDB_PATH = os.environ.get("FRAMMER_DB_PATH", ...)   ← frozen at import
#
# When FastAPI starts, chat.py sets os.environ["FRAMMER_DB_PATH"] AFTER
# Python has already imported executor.py, so the module-level variable
# captured the wrong (Windows dev) path and every SQL query failed with
# "file not found" in production.

import os
import logging
import duckdb
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Fallback path: nlp/executor.py → nlp/ → nlp_frammer/ → backend/ → frammer_analytics.duckdb
_FALLBACK_DB = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "frammer_analytics.duckdb")
)


def _get_db_path() -> str:
    """
    Resolve the DuckDB path at call time (not import time).

    Priority: FRAMMER_DB_PATH env var → fallback sibling path.

    Guards against Windows absolute paths on Linux servers by checking
    for any drive letter pattern (C:, D:, E:, etc.) — not just C:.
    """
    raw = os.environ.get("FRAMMER_DB_PATH", "").strip()

    if not raw:
        return _FALLBACK_DB

    # Guard: any Windows drive-letter path (C:\, D:\, C:/, D:/, etc.)
    if len(raw) >= 2 and raw[1] == ":" and raw[0].isalpha():
        logger.warning(
            f"[executor] FRAMMER_DB_PATH looks like a Windows path ({raw!r}). "
            f"Using fallback: {_FALLBACK_DB}"
        )
        return _FALLBACK_DB

    return os.path.normpath(raw)


# ──────────────────────────────────────────────────────────────────────
# RETURN TYPE
# ──────────────────────────────────────────────────────────────────────

@dataclass
class ExecutionResult:
    success:    bool
    data:       list[dict]   # rows as list of column→value dicts
    row_count:  int
    error:      str | None


# ──────────────────────────────────────────────────────────────────────
# PUBLIC: EXECUTE
# ──────────────────────────────────────────────────────────────────────

def execute(sql: str) -> ExecutionResult:
    """
    Runs the given SQL against the DuckDB database (read-only).

    Args:
        sql: A valid DuckDB SQL string ending with a semicolon.

    Returns:
        ExecutionResult with rows as list of dicts, or error details.
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
