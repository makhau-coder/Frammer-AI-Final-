import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import DATABASE_PATH


def load_star_schema(conn):

    with open("models/star_schema.sql", "r") as f:
        schema_sql = f.read()

    conn.execute(schema_sql)

    print("Star schema created successfully.")