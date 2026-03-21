# nlp/retriever.py
#
# MERGED — uses FRIEND's two-stage retrieval (bi-encoder + cross-encoder reranker)
#
# YOUR version: single-stage bi-encoder only (ChromaDB / all-MiniLM-L6-v2)
# FRIEND's version: two-stage retrieval:
#   Stage 1 — bi-encoder (ChromaDB): fast approximate retrieval,
#              fetches RERANK_FETCH_K=10 candidates per type (wider net)
#   Stage 2 — cross-encoder (ms-marco-MiniLM-L-6-v2): precise joint
#              scoring of (query, chunk) pairs, trims back to TOP_K_* per type
#
# Net effect: same number of chunks reach Gemini, but they are the
# best chunks from a wider first-pass pool — measurably better SQL quality.

from __future__ import annotations
import logging
import time
from dataclasses import dataclass
from nlp.vector_store import get_collection
from sentence_transformers import CrossEncoder

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────
# TUNING CONSTANTS
# ──────────────────────────────────────────────────────────────────────

# Final top-k sent to Gemini per chunk type (unchanged from before)
TOP_K_TABLES   = 4
TOP_K_METRICS  = 3
TOP_K_EXAMPLES = 3

# How many candidates to fetch from ChromaDB before reranking.
# Rule of thumb: 3-4× the final top-k gives the reranker enough to work with.
RERANK_FETCH_K = 10

# Minimum bi-encoder similarity to enter the reranker candidate pool.
# Kept low intentionally — the reranker will sort out relevance.
MIN_SIMILARITY = 0.20

# Cross-encoder model. Same MiniLM family as the bi-encoder —
# no extra download if sentence-transformers is already installed.
# ~85MB, loaded once at module import.
RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

# ──────────────────────────────────────────────────────────────────────
# RERANKER SINGLETON — loaded once, reused for every query
# ──────────────────────────────────────────────────────────────────────

_reranker: CrossEncoder | None = None


def _get_reranker() -> CrossEncoder:
    global _reranker
    if _reranker is None:
        logger.info(f"[retriever] Loading cross-encoder: {RERANKER_MODEL}")
        _reranker = CrossEncoder(RERANKER_MODEL)
        logger.info("[retriever] Cross-encoder loaded.")
    return _reranker


# ──────────────────────────────────────────────────────────────────────
# RETURN TYPE
# ──────────────────────────────────────────────────────────────────────

@dataclass
class RetrievedContext:
    table_chunks:   list[str]
    metric_chunks:  list[str]
    example_chunks: list[str]
    all_chunks:     list[str]

    @property
    def total_chunks(self) -> int:
        return len(self.all_chunks)

    @property
    def referenced_tables(self) -> list[str]:
        """Extracts unique table names from retrieved chunk metadata."""
        tables = set()
        for chunk in self.table_chunks:
            for line in chunk.splitlines():
                if line.strip().startswith("Table:"):
                    tables.add(line.split("Table:")[-1].strip())
        return sorted(tables)


# ──────────────────────────────────────────────────────────────────────
# MAIN RETRIEVER
# ──────────────────────────────────────────────────────────────────────

def retrieve(query: str) -> RetrievedContext:
    """
    Two-stage retrieval: bi-encoder (ChromaDB) → cross-encoder (reranker).

    Args:
        query: The raw user question string.

    Returns:
        RetrievedContext with the best chunks per type after reranking.
    """
    collection = get_collection()
    t0         = time.perf_counter()
    reranker   = _get_reranker()

    table_chunks   = _query_and_rerank(collection, reranker, query, ["table", "relationship", "limitation"], TOP_K_TABLES)
    metric_chunks  = _query_and_rerank(collection, reranker, query, ["metric"],  TOP_K_METRICS)
    example_chunks = _query_and_rerank(collection, reranker, query, ["example"], TOP_K_EXAMPLES)

    # Combine and deduplicate preserving order: tables → metrics → examples
    seen, combined = set(), []
    for chunk in table_chunks + metric_chunks + example_chunks:
        if chunk not in seen:
            seen.add(chunk)
            combined.append(chunk)

    logger.info(
        f"[timing] retrieve       total    : {int((time.perf_counter() - t0) * 1000):>6} ms  "
        f"| chunks={len(combined)} "
        f"(tables={len(table_chunks)}, metrics={len(metric_chunks)}, examples={len(example_chunks)})"
    )

    return RetrievedContext(
        table_chunks=table_chunks,
        metric_chunks=metric_chunks,
        example_chunks=example_chunks,
        all_chunks=combined,
    )


# ──────────────────────────────────────────────────────────────────────
# INTERNAL: FETCH + RERANK
# ──────────────────────────────────────────────────────────────────────

def _query_and_rerank(
    collection,
    reranker: CrossEncoder,
    query: str,
    types: list[str],
    top_k: int,
) -> list[str]:
    """
    Stage 1: Fetch RERANK_FETCH_K candidates from ChromaDB via bi-encoder.
    Stage 2: Score all candidates with the cross-encoder, return top_k.

    If fewer candidates than top_k pass MIN_SIMILARITY, returns whatever
    passed — never pads with low-quality chunks.
    """
    where_filter = (
        {"type": {"$in": types}}
        if len(types) > 1
        else {"type": types[0]}
    )

    # ── Stage 1: bi-encoder retrieval ────────────────────────────────
    results   = collection.query(
        query_texts=[query],
        n_results=RERANK_FETCH_K,
        where=where_filter,
        include=["documents", "distances"],
    )

    documents = results["documents"][0]
    distances = results["distances"][0]

    # Filter by minimum bi-encoder similarity before passing to reranker.
    # ChromaDB returns cosine DISTANCE (0=identical, 2=opposite).
    # Convert: similarity = 1 - (distance / 2)
    candidates = [
        doc
        for doc, dist in zip(documents, distances)
        if (1 - dist / 2) >= MIN_SIMILARITY
    ]

    if not candidates:
        return []

    # ── Stage 2: cross-encoder reranking ─────────────────────────────
    pairs  = [(query, doc) for doc in candidates]
    scores = reranker.predict(pairs)   # numpy array of floats

    # Sort by score descending, take top_k
    ranked = sorted(zip(scores, candidates), key=lambda x: x[0], reverse=True)
    return [doc for _, doc in ranked[:top_k]]
