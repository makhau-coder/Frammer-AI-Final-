import os
from typing import Optional
import chromadb
import chromadb.utils.embedding_functions as embedding_functions

from nlp.metadata import METADATA
from nlp.metrics import METRICS
from nlp.examples import EXAMPLES

# ──────────────────────────────────────────────────────────────────────
# CONSTANTS
# ──────────────────────────────────────────────────────────────────────

CHROMA_DB_PATH   = os.path.join(os.path.dirname(__file__), "..", "data", "chroma_db")
COLLECTION_NAME  = "frammer_analytics"

ALL_CHUNKS = METADATA + METRICS + EXAMPLES

# ──────────────────────────────────────────────────────────────────────
# CLIENT + EMBEDDING FUNCTION
# ──────────────────────────────────────────────────────────────────────

def _get_client():
    """Returns a persistent ChromaDB client pointing to data/chroma_db/."""
    os.makedirs(CHROMA_DB_PATH, exist_ok=True)
    return chromadb.PersistentClient(path=CHROMA_DB_PATH)

def _get_embedding_fn():
    """Returns the Google Gemini API embedding function (Zero local RAM)."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is missing from environment variables.")
    
    return embedding_functions.GoogleGenerativeAiEmbeddingFunction(
        api_key=api_key,
        task_type="RETRIEVAL_DOCUMENT"
    )

# ──────────────────────────────────────────────────────────────────────
# PUBLIC: GET COLLECTION (used by retriever at query time)
# ──────────────────────────────────────────────────────────────────────

def get_collection():
    client = _get_client()
    existing = [c.name for c in client.list_collections()]

    if COLLECTION_NAME not in existing:
        raise RuntimeError(
            f"ChromaDB collection '{COLLECTION_NAME}' not found. "
            f"Run: python scripts/build_index.py"
        )

    try:
        return client.get_collection(
            name=COLLECTION_NAME,
            embedding_function=_get_embedding_fn(),
        )
    except Exception as e:
        if "does not exist" in str(e).lower() or "notfounderror" in type(e).__name__.lower():
            import logging
            logging.getLogger(__name__).warning(
                f"[vector_store] Stale ChromaDB UUID detected — auto-rebuilding index."
            )
            index_all(force=True)
            return client.get_collection(
                name=COLLECTION_NAME,
                embedding_function=_get_embedding_fn(),
            )
        raise

# ──────────────────────────────────────────────────────────────────────
# PUBLIC: INDEX ALL CHUNKS (called once from build_index.py)
# ──────────────────────────────────────────────────────────────────────

def index_all(force: bool = False) -> None:
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
        metadata={"hnsw:space": "cosine"}, 
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

    collection.upsert(
        ids=ids,
        documents=documents,
        metadatas=metadatas,
    )

    counts = _count_by_type(ALL_CHUNKS)
    print(
        f"[vector_store] Index built successfully with Gemini API.\n"
        f"  Total chunks indexed: {len(ALL_CHUNKS)}\n"
    )

def _count_by_type(chunks: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for chunk in chunks:
        t = chunk.get("type", "unknown")
        counts[t] = counts.get(t, 0) + 1
    return counts