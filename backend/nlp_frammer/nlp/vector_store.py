# nlp/vector_store.py
#
# MERGED — uses FRIEND's singleton pattern over YOUR version:
#
# FRIEND's improvements kept:
#   - _client and _collection singletons — opened once, reused forever
#   - No reconnect cost on every get_collection() call
#   - Singleton invalidated on force-rebuild (index_all(force=True))
#   - Collection warmed after index_all() so first query has no load cost
#   - logging added throughout
#
# YOUR version re-opened client/collection on every get_collection() call.
# All other logic (embedding model, upsert, chunk assembly) is unchanged.

from __future__ import annotations
import os
import logging
import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from nlp.metadata import METADATA
from nlp.metrics  import METRICS
from nlp.examples import EXAMPLES

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────
# CONSTANTS
# ──────────────────────────────────────────────────────────────────────

CHROMA_DB_PATH  = os.path.join(os.path.dirname(__file__), "..", "data", "chroma_db")
COLLECTION_NAME = "frammer_analytics"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

ALL_CHUNKS = METADATA + METRICS + EXAMPLES

# ──────────────────────────────────────────────────────────────────────
# SINGLETONS — client + collection opened once, reused forever
# ──────────────────────────────────────────────────────────────────────

_client:     chromadb.PersistentClient | None = None
_collection: chromadb.Collection       | None = None


def _get_client() -> chromadb.PersistentClient:
    global _client
    if _client is None:
        os.makedirs(CHROMA_DB_PATH, exist_ok=True)
        _client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
        logger.info(f"[vector_store] ChromaDB client opened: {os.path.abspath(CHROMA_DB_PATH)}")
    return _client


def _get_embedding_fn() -> SentenceTransformerEmbeddingFunction:
    return SentenceTransformerEmbeddingFunction(
        model_name=EMBEDDING_MODEL,
        device="cpu",
        normalize_embeddings=True,
    )


# ──────────────────────────────────────────────────────────────────────
# PUBLIC: GET COLLECTION
# ──────────────────────────────────────────────────────────────────────

def get_collection() -> chromadb.Collection:
    """
    Returns the ChromaDB collection for querying.
    Client and collection are singletons — no reconnect cost per query.
    Raises RuntimeError if build_index.py hasn't been run yet.
    """
    global _collection
    if _collection is not None:
        return _collection

    client   = _get_client()
    existing = [c.name for c in client.list_collections()]

    if COLLECTION_NAME not in existing:
        raise RuntimeError(
            f"ChromaDB collection '{COLLECTION_NAME}' not found. "
            f"Run: python scripts/build_index.py"
        )

    _collection = client.get_collection(
        name=COLLECTION_NAME,
        embedding_function=_get_embedding_fn(),
    )
    logger.info(f"[vector_store] Collection '{COLLECTION_NAME}' loaded.")
    return _collection


# ──────────────────────────────────────────────────────────────────────
# PUBLIC: INDEX ALL CHUNKS (called once from build_index.py)
# ──────────────────────────────────────────────────────────────────────

def index_all(force: bool = False) -> None:
    """
    Embeds and upserts all chunks into ChromaDB.

    force=True deletes and recreates the collection from scratch.
    Default (force=False) upserts — safe to re-run, no duplicates.
    """
    global _collection
    client       = _get_client()
    embedding_fn = _get_embedding_fn()

    if force:
        existing = [c.name for c in client.list_collections()]
        if COLLECTION_NAME in existing:
            client.delete_collection(COLLECTION_NAME)
            _collection = None   # invalidate singleton
            print(f"[vector_store] Deleted existing collection '{COLLECTION_NAME}'.")

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_fn,
        metadata={"hnsw:space": "cosine"},
    )

    ids, documents, metadatas = [], [], []

    for chunk in ALL_CHUNKS:
        ids.append(chunk["id"])
        documents.append(chunk["text"].strip())
        metadatas.append({
            "type":   chunk["type"],
            "tables": ", ".join(chunk.get("tables", [])),
        })

    collection.upsert(ids=ids, documents=documents, metadatas=metadatas)

    # Warm the singleton so the first query doesn't pay collection-load cost
    _collection = collection

    counts = _count_by_type(ALL_CHUNKS)
    print(
        f"[vector_store] Index built successfully.\n"
        f"  Collection : {COLLECTION_NAME}\n"
        f"  Path       : {os.path.abspath(CHROMA_DB_PATH)}\n"
        f"  Total      : {len(ALL_CHUNKS)}\n"
        + "\n".join(f"  {k:<12}: {v}" for k, v in counts.items())
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
