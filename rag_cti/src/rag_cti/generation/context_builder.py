from __future__ import annotations

import json
import re
from typing import Any

from rag_cti.generation.prompts import ANSWER_SYNTHESIS_SYSTEM
from rag_cti.types import RetrievalResult

_CITED_ID_RE = re.compile(r"\[([a-zA-Z0-9_\-]+)\]")


def build_context_messages(
    query: str,
    results: list[RetrievalResult],
    system_prompt: str = ANSWER_SYNTHESIS_SYSTEM,
) -> list[dict[str, Any]]:
    """Build a [system, user] message list for Groq, embedding context chunks in the user message.

    Each chunk is serialised as JSON with its chunk_id so the model can cite it as [chunk_id].
    The system message instructs the model to cite chunk IDs and stay grounded in the context.
    """
    chunks = [
        {
            "chunk_id": r.document.id,
            "source": r.document.source,
            "score": round(r.score, 4),
            "rank": r.rank,
            "content": r.document.content,
        }
        for r in results
    ]
    context_text = json.dumps(chunks, default=str)
    return [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": f"Query: {query}\n\nContext chunks:\n{context_text}",
        },
    ]


def extract_cited_ids(answer: str) -> list[str]:
    """Return chunk IDs cited as [chunk_id] in the answer, in order, deduplicated."""
    seen: set[str] = set()
    ids: list[str] = []
    for match in _CITED_ID_RE.finditer(answer):
        cid = match.group(1)
        if cid not in seen:
            seen.add(cid)
            ids.append(cid)
    return ids
