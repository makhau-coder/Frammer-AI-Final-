from __future__ import annotations
import logging
import time
from dataclasses import dataclass
from nlp.vector_store import get_collection

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────
# TUNING CONSTANTS
# ──────────────────────────────────────────────────────────────────────

TOP_K_TABLES   = 4
TOP_K_METRICS  = 3
TOP_K_EXAMPLES = 3
MIN_SIMILARITY = 0.20

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
    collection = get_collection()
    t0         = time.perf_counter()

    table_chunks   = _query_collection(collection, query, ["table", "relationship", "limitation"], TOP_K_TABLES)
    metric_chunks  = _query_collection(collection, query, ["metric"],  TOP_K_METRICS)
    example_chunks = _query_collection(collection, query, ["example"], TOP_K_EXAMPLES)

    # Combine and deduplicate preserving order
    seen, combined = set(), []
    for chunk in table_chunks + metric_chunks + example_chunks:
        if chunk not in seen:
            seen.add(chunk)
            combined.append(chunk)

    logger.info(
        f"[timing] retrieve      total    : {int((time.perf_counter() - t0) * 1000):>6} ms  "
        f"| chunks={len(combined)} "
    )

    return RetrievedContext(
        table_chunks=table_chunks,
        metric_chunks=metric_chunks,
        example_chunks=example_chunks,
        all_chunks=combined,
    )

# ──────────────────────────────────────────────────────────────────────
# INTERNAL: FETCH
# ──────────────────────────────────────────────────────────────────────

def _query_collection(
    collection,
    query: str,
    types: list[str],
    top_k: int,
) -> list[str]:
    
    where_filter = (
        {"type": {"$in": types}}
        if len(types) > 1
        else {"type": types[0]}
    )

    results   = collection.query(
        query_texts=[query],
        n_results=top_k,
        where=where_filter,
        include=["documents", "distances"],
    )

    if not results["documents"] or not results["documents"][0]:
        return []

    documents = results["documents"][0]
    distances = results["distances"][0]

    # Convert distance to similarity
    candidates = [
        doc
        for doc, dist in zip(documents, distances)
        if (1 - dist) >= MIN_SIMILARITY
    ]

    return candidates