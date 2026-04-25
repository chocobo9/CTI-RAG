"""RAG-powered Cyber Threat Intelligence retrieval system.

Public interface:
    query(text, k) -> list[Chunk]   retrieve relevant CTI chunks
"""

from __future__ import annotations

from rag_cti.types import Chunk, QueryResult

__all__ = ["query", "QueryResult", "Chunk"]

__version__ = "0.1.0"


def query(text: str, k: int = 10) -> list[Chunk]:
    """Retrieve the top-k most relevant CTI chunks for the given query text.

    Args:
        text: Natural language query or IOC string.
        k: Number of results to return.

    Returns:
        Ranked list of Chunk objects, most relevant first.
    """
    # Wired up in Phase 4 when retrieval/pipeline.py is complete.
    raise NotImplementedError(
        "query() is not yet implemented. Complete Phase 4 (Retrieval Layer) first."
    )
