# nlp/executor.py
#
# Executes validated SQL against the DuckDB analytics database
# and formats the result into a clean list of dicts.

import os
import logging
import duckdb
from dotenv import load_dotenv

load_dotenv() 

logger = logging.getLogger(__name__)

DUCKDB_PATH = os.path.normpath(
    os.environ.get(
        "FRAMMER_DB_PATH",
        os.path.join(os.path.dirname(__file__), "..", "..", "frammer_analytics.duckdb")
    ).strip()
)

# print(f"[executor] DB path: {repr(DUCKDB_PATH)}")


# ──────────────────────────────────────────────────────────────────────
# RETURN TYPE
# ──────────────────────────────────────────────────────────────────────

from dataclasses import dataclass

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
    try:
        conn = duckdb.connect(DUCKDB_PATH, read_only=True)
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

