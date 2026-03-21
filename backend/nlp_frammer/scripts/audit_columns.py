# scripts/audit_columns.py
#
# Prints ALL table names and their EXACT column names from DuckDB.
# Useful for verifying that metadata.py column names match reality.
#
# Usage:
#   python scripts/audit_columns.py
#
# The DB path is read from FRAMMER_DB_PATH in your .env file.
# If not set, it defaults to backend/frammer_analytics.duckdb relative
# to this script's location.

import os
import sys
import duckdb
from dotenv import load_dotenv

# Load .env from the nlp_frammer directory (one level up from scripts/)
_DOTENV_PATH = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(_DOTENV_PATH)

# Resolve DB path — same logic as executor.py
_FALLBACK_DB = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "frammer_analytics.duckdb")
)

raw = os.environ.get("FRAMMER_DB_PATH", "").strip()
if not raw:
    DB_PATH = _FALLBACK_DB
elif len(raw) >= 2 and raw[1] == ":" and raw[0].isalpha():
    # Windows absolute path — use as-is (script may be run locally on Windows)
    DB_PATH = raw
else:
    DB_PATH = os.path.normpath(raw)

if not os.path.exists(DB_PATH):
    print(f"ERROR: Database not found at: {DB_PATH}")
    print("Set FRAMMER_DB_PATH in your .env file, or run the ETL pipeline first.")
    sys.exit(1)

print(f"Database: {DB_PATH}\n")

conn = duckdb.connect(DB_PATH, read_only=True)
tables = conn.execute("SHOW TABLES").fetchall()

for (table,) in tables:
    cols = conn.execute(f'DESCRIBE "{table}"').fetchall()
    print(f"\n{'─' * 60}")
    print(f"TABLE: {table}")
    for col in cols:
        print(f"  {col[0]!r:45} {col[1]}")

conn.close()
print(f"\nTotal tables: {len(tables)}")
