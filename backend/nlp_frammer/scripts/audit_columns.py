# scripts/audit_columns.py
# Run this to print ALL table names and their EXACT column names from DuckDB.

import duckdb
import os

DB_PATH = "C:/Users/LEGION/projects/nlp_frammer/frammer_analytics.duckdb"

conn = duckdb.connect(DB_PATH, read_only=True)
tables = conn.execute("SHOW TABLES").fetchall()

for (table,) in tables:
    cols = conn.execute(f'DESCRIBE "{table}"').fetchall()
    print(f"\n{'─'*60}")
    print(f"TABLE: {table}")
    for col in cols:
        print(f"  {col[0]!r:45} {col[1]}")

conn.close()
