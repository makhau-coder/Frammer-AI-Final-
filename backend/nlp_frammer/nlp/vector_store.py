import os
from typing import Optional
import chromadb
import chromadb.utils.embedding_functions as embedding_functions

# Note: Ensure these imports work based on your tree structure
from nlp.metadata import METADATA
from nlp.metrics import METRICS
from nlp.examples import EXAMPLES

# ──────────────────────────────────────────────────────────────────────
# CONSTANTS
# ──────────────────────────────────────────────────────────────────────

CHROMA_DB_PATH   = os.path.join(os.path.dirname(__file__), "..", "data", "chroma_db")
COLLECTION_NAME  = "frammer_analytics"
EMBEDDING_MODEL  = "models/gemini-embedding-001" 

ALL_CHUNKS = METADATA + METRICS + EXAMPLES

# ──────────────────────────────────────────────────────────────────────
# CLIENT + EMBEDDING FUNCTION
# ──────────────────────────────────────────────────────────────────────

def _get_client():
    """Returns a persistent ChromaDB client pointing to data/chroma_db/."""
    os.makedirs(CHROMA_DB_PATH, exist_ok=True)
    return chromadb.PersistentClient(path=CHROMA_DB_PATH)

def _get_embedding_fn():
    """Returns the Google Gemini API embedding function."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        # For local scripts, this error is helpful
        raise ValueError("GEMINI_API_KEY is missing from environment variables.")
    
    return embedding_functions.GoogleGenerativeAiEmbeddingFunction(
        api_key=api_key,
        model_name=EMBEDDING_MODEL,
        task_type="RETRIEVAL_DOCUMENT"
    )

# ──────────────────────────────────────────────────────────────────────
# PUBLIC: GET COLLECTION
# ──────────────────────────────────────────────────────────────────────

def get_collection():
    import logging
    logger = logging.getLogger(__name__)
    
    client = _get_client()
    
    # FIX for Chroma v0.6.0: list_collections() now returns strings directly
    existing_names = client.list_collections()

    if COLLECTION_NAME not in existing_names:
        logger.info(f"[vector_store] Collection '{COLLECTION_NAME}' not found. Auto-building...")
        index_all()

    try:
        return client.get_collection(
            name=COLLECTION_NAME,
            embedding_function=_get_embedding_fn(),
        )
    except Exception as e:
        if "does not exist" in str(e).lower():
            logger.warning(f"[vector_store] Stale reference — rebuilding index.")
            index_all(force=True)
            return client.get_collection(
                name=COLLECTION_NAME,
                embedding_function=_get_embedding_fn(),
            )
        raise

# ──────────────────────────────────────────────────────────────────────
# PUBLIC: INDEX ALL CHUNKS
# ──────────────────────────────────────────────────────────────────────

def index_all(force: bool = False) -> None:
    client       = _get_client()
    embedding_fn = _get_embedding_fn()

    # FIX for Chroma v0.6.0: checking names directly
    existing_names = client.list_collections()
    
    if force and COLLECTION_NAME in existing_names:
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

    print(f"[vector_store] Index built successfully with {EMBEDDING_MODEL}.\n")

def _count_by_type(chunks: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for chunk in chunks:
        t = chunk.get("type", "unknown")
        counts[t] = counts.get(t, 0) + 1
    return counts