import sys
import os

# Add project root to Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import duckdb
from config import DATABASE_PATH
# DuckDB will create database automatically if it doesn't exist
con = duckdb.connect(DATABASE_PATH)

print("Database connected successfully!")