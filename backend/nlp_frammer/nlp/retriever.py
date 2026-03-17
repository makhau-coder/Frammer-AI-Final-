# nlp/retriever.py
#
# Embeds the user's query and fetches the top-k most relevant chunks
# from ChromaDB. Returns structured results that prompt_builder.py
# assembles into the final prompt.

from dataclasses import dataclass
from nlp.vector_store import get_collection

# ──────────────────────────────────────────────────────────────────────
# TUNING CONSTANTS
# ──────────────────────────────────────────────────────────────────────

# How many chunks to retrieve per type.
# Tuned to stay well under ~1000 tokens of retrieved context.
TOP_K_TABLES    = 4   # table + relationship + limitation chunks
TOP_K_METRICS   = 2   # metric definition chunks
TOP_K_EXAMPLES  = 3   # few-shot Q→SQL example chunks

# Minimum similarity score to include a chunk (0.0 – 1.0, cosine).
# Chunks below this threshold are too semantically distant to be useful.
MIN_SIMILARITY  = 0.25


# ──────────────────────────────────────────────────────────────────────
# RETURN TYPE
# ──────────────────────────────────────────────────────────────────────

@dataclass
class RetrievedContext:
    table_chunks:   list[str]   # table/relationship/limitation descriptions
    metric_chunks:  list[str]   # metric formula definitions
    example_chunks: list[str]   # few-shot Q→SQL pairs
    all_chunks:     list[str]   # combined, deduped — used by prompt_builder

    @property
    def total_chunks(self) -> int:
        return len(self.all_chunks)

    @property
    def referenced_tables(self) -> list[str]:
        """Extracts unique table names from retrieved chunk metadata."""
        tables = set()
        for chunk in self.table_chunks:
            # Table name always appears on line: "Table: <name>"
            for line in chunk.splitlines():
                if line.strip().startswith("Table:"):
                    tables.add(line.split("Table:")[-1].strip())
        return sorted(tables)


# ──────────────────────────────────────────────────────────────────────
# MAIN RETRIEVER
# ──────────────────────────────────────────────────────────────────────

def retrieve(query: str) -> RetrievedContext:
    """
    Embeds the user query and retrieves top-k relevant chunks
    from ChromaDB, split by chunk type.

    Args:
        query: The raw user question string.

    Returns:
        RetrievedContext with separate lists per chunk type
        and a combined all_chunks list for the prompt.
    """
    collection = get_collection()

    table_chunks   = _query(collection, query, ["table", "relationship", "limitation"], TOP_K_TABLES)
    metric_chunks  = _query(collection, query, ["metric"],                              TOP_K_METRICS)
    example_chunks = _query(collection, query, ["example"],                             TOP_K_EXAMPLES)

    # Combine and deduplicate preserving order: tables → metrics → examples
    seen     = set()
    combined = []
    for chunk in table_chunks + metric_chunks + example_chunks:
        if chunk not in seen:
            seen.add(chunk)
            combined.append(chunk)

    return RetrievedContext(
        table_chunks=table_chunks,
        metric_chunks=metric_chunks,
        example_chunks=example_chunks,
        all_chunks=combined,
    )


# ──────────────────────────────────────────────────────────────────────
# INTERNAL QUERY HELPER
# ──────────────────────────────────────────────────────────────────────

def _query(
    collection,
    query: str,
    types: list[str],
    top_k: int,
) -> list[str]:
    """
    Queries ChromaDB for top_k chunks matching the given types,
    filtered by MIN_SIMILARITY threshold.

    Args:
        collection: Active ChromaDB collection.
        query:      User query string.
        types:      List of chunk types to include (e.g. ["table", "limitation"]).
        top_k:      Max number of results to return.

    Returns:
        List of document text strings, ordered by relevance.
    """
    where_filter = (
        {"type": {"$in": types}}
        if len(types) > 1
        else {"type": types[0]}
    )

    results = collection.query(
        query_texts=[query],
        n_results=top_k,
        where=where_filter,
        include=["documents", "distances"],
    )

    documents = results["documents"][0]   # list of text strings
    distances = results["distances"][0]   # cosine distances (lower = more similar)

    # ChromaDB returns cosine DISTANCE (0 = identical, 2 = opposite).
    # Convert to similarity score: similarity = 1 - (distance / 2)
    filtered = [
        doc
        for doc, dist in zip(documents, distances)
        if (1 - dist / 2) >= MIN_SIMILARITY
    ]

    return filtered
