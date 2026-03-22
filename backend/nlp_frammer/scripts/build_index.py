# scripts/build_index.py
#
# Run this ONCE to build the ChromaDB index.
# Re-running is safe — upsert won't create duplicates.
#
# Usage:
#   python scripts/build_index.py          # upsert (safe re-run)
#   python scripts/build_index.py --force  # wipe + rebuild from scratch


import sys
import os

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from nlp.vector_store import index_all

if __name__ == "__main__":
    force = "--force" in sys.argv
    if force:
        print("[build_index] --force flag detected. Wiping and rebuilding index...")
    index_all(force=force)
