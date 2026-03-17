# nlp/vector_store.py
#
# ChromaDB setup and indexing.
# Embeds all chunks from metadata.py, metrics.py, and examples.py
# and stores them in a single persistent ChromaDB collection.
#
# Called once via: python scripts/build_index.py
# Used at query time via: get_collection()

import os
import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from nlp.metadata import METADATA
from nlp.metrics import METRICS
from nlp.examples import EXAMPLES

# ──────────────────────────────────────────────────────────────────────
# CONSTANTS
# ──────────────────────────────────────────────────────────────────────

CHROMA_DB_PATH   = os.path.join(os.path.dirname(__file__), "..", "data", "chroma_db")
COLLECTION_NAME  = "frammer_analytics"
EMBEDDING_MODEL  = "all-MiniLM-L6-v2"

# Single combined collection — all chunk types live here.
# The `type` metadata field distinguishes them if needed for filtering.
ALL_CHUNKS = METADATA + METRICS + EXAMPLES

# ──────────────────────────────────────────────────────────────────────
# CLIENT + EMBEDDING FUNCTION
# ──────────────────────────────────────────────────────────────────────

def _get_client() -> chromadb.PersistentClient:
    """Returns a persistent ChromaDB client pointing to data/chroma_db/."""
    os.makedirs(CHROMA_DB_PATH, exist_ok=True)
    return chromadb.PersistentClient(path=CHROMA_DB_PATH)


def _get_embedding_fn() -> SentenceTransformerEmbeddingFunction:
    """Returns the sentence-transformers embedding function.
    Model is downloaded (~91MB) on first call and cached automatically."""
    return SentenceTransformerEmbeddingFunction(
        model_name=EMBEDDING_MODEL,
        device="cpu",          # no GPU needed — model is tiny
        normalize_embeddings=True,
    )


# ──────────────────────────────────────────────────────────────────────
# PUBLIC: GET COLLECTION (used by retriever at query time)
# ──────────────────────────────────────────────────────────────────────

def get_collection() -> chromadb.Collection:
    """
    Returns the ChromaDB collection for querying.
    Call this in retriever.py — it does NOT re-index anything.
    Raises RuntimeError if the collection doesn't exist yet
    (i.e. build_index.py hasn't been run).
    """
    client = _get_client()
    existing = [c.name for c in client.list_collections()]

    if COLLECTION_NAME not in existing:
        raise RuntimeError(
            f"ChromaDB collection '{COLLECTION_NAME}' not found. "
            f"Run: python scripts/build_index.py"
        )

    return client.get_collection(
        name=COLLECTION_NAME,
        embedding_function=_get_embedding_fn(),
    )


# ──────────────────────────────────────────────────────────────────────
# PUBLIC: INDEX ALL CHUNKS (called once from build_index.py)
# ──────────────────────────────────────────────────────────────────────

def index_all(force: bool = False) -> None:
    """
    Embeds and upserts all chunks into ChromaDB.

    Args:
        force: If True, deletes and recreates the collection from scratch.
               If False (default), upserts — safe to re-run, no duplicates.

    Logs a summary of what was indexed on completion.
    """
    client       = _get_client()
    embedding_fn = _get_embedding_fn()

    if force:
        existing = [c.name for c in client.list_collections()]
        if COLLECTION_NAME in existing:
            client.delete_collection(COLLECTION_NAME)
            print(f"[vector_store] Deleted existing collection '{COLLECTION_NAME}'.")

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_fn,
        metadata={"hnsw:space": "cosine"},  # cosine similarity for semantic search
    )

    ids       = []
    documents = []
    metadatas = []

    for chunk in ALL_CHUNKS:
        ids.append(chunk["id"])
        documents.append(chunk["text"].strip())
        metadatas.append({
            "type":   chunk["type"],
            "tables": ", ".join(chunk.get("tables", [])),
        })

    # upsert is idempotent — re-running won't create duplicates
    collection.upsert(
        ids=ids,
        documents=documents,
        metadatas=metadatas,
    )

    counts = _count_by_type(ALL_CHUNKS)
    print(
        f"[vector_store] Index built successfully.\n"
        f"  Collection : {COLLECTION_NAME}\n"
        f"  Path       : {os.path.abspath(CHROMA_DB_PATH)}\n"
        f"  Total chunks indexed: {len(ALL_CHUNKS)}\n"
        f"    table      : {counts.get('table', 0)}\n"
        f"    metric     : {counts.get('metric', 0)}\n"
        f"    example    : {counts.get('example', 0)}\n"
        f"    relationship: {counts.get('relationship', 0)}\n"
        f"    limitation : {counts.get('limitation', 0)}\n"
        f"    sql_rules  : {counts.get('sql_rules', 0)}\n"
    )


# ──────────────────────────────────────────────────────────────────────
# HELPER
# ──────────────────────────────────────────────────────────────────────

def _count_by_type(chunks: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for chunk in chunks:
        t = chunk.get("type", "unknown")
        counts[t] = counts.get(t, 0) + 1
    return counts
