"""Generate a custom evaluation query set from sampled Qdrant corpus chunks.

Usage:
    python scripts/build_query_set.py [--n-precise 20] [--n-semantic 20] [--n-fuzzy 20] \
        [--output data/eval/query_set.jsonl] [--seed 42] [--dry-run]

Generates ≥60 queries across 3 categories:
  precise  — specific IOC/tool/hash lookups; BM25 exact-match strength
  semantic — conceptual TTP questions; dense recall strength
  fuzzy    — "memory fog" vague queries; robustness criterion
"""

from __future__ import annotations

import argparse
import random
import re
import sys
from pathlib import Path
from typing import Any

import instructor
from groq import Groq  # type: ignore[import]
from pydantic import BaseModel, field_validator

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rag_cti.config import get_settings
from rag_cti.evaluation.query_set import QueryCategory, QuerySetRecord, save_query_set

# ---------------------------------------------------------------------------
# Instructor response schemas
# ---------------------------------------------------------------------------

class PreciseQueryResponse(BaseModel):
    query: str
    expected_chunk_id: str
    notes: str

    @field_validator("query")
    @classmethod
    def query_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("query must not be empty")
        return v.strip()


class SemanticQueryResponse(BaseModel):
    query: str
    expected_chunk_id: str
    notes: str

    @field_validator("query")
    @classmethod
    def query_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("query must not be empty")
        return v.strip()


class FuzzyQueryResponse(BaseModel):
    query: str
    gold_attack_ids: list[str]
    gold_sources: list[str]
    notes: str

    @field_validator("query")
    @classmethod
    def query_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("query must not be empty")
        return v.strip()


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_PRECISE_SYSTEM = """\
You are building an evaluation test set for a Cyber Threat Intelligence retrieval system.
Your task: given a single corpus chunk, write ONE precise search query that would retrieve this EXACT chunk.

Rules:
- FORBIDDEN: Do NOT use ATT&CK technique IDs (T1059, T1027.006, etc.) as the query anchor — \
they appear in hundreds of chunks and are useless for distinguishing retrieval
- FORBIDDEN: Do NOT use the technique name alone (e.g. "Office Template Macros") — too generic
- REQUIRED: Anchor on a CONCRETE detail unique to this specific chunk: a specific tool name, \
malware family, exact command or registry path, CVE number, domain, IP, file hash, \
actor group name, campaign name, or a distinctive attack scenario described in the chunk body
- Write the query as a natural analyst search string or question, NOT a keyword dump
- If the chunk describes a technique abstractly with no concrete examples, use the most specific \
behavior phrase from the description (e.g. "hollowing suspended process to evade AV scan")
- Copy the chunk_id field back EXACTLY as given — do not alter it

Good examples:
- "What malware used Ethereum smart contracts as a C2 channel?"
- "CVE-2023-46604 Apache ActiveMQ exploit in the wild"
- "Kinsing cryptominer targeting Docker API"
- "UltraVNC deployed as persistent remote access by threat actor"
- "DGA-based botnet using registry key Performance for persistence"
"""

_SEMANTIC_SYSTEM = """\
You are building an evaluation test set for a Cyber Threat Intelligence retrieval system.
Your task: given a single corpus chunk, write ONE semantic search query about the TOPIC of this chunk.

Rules:
- Describe the technique, tactic, behavior, or threat type conceptually
- Do NOT use exact IOC values, CVE IDs, specific tool names, or malware family names from the chunk
- Phrase the query as a general question an analyst would ask about this class of threat
- The query should retrieve this chunk AND conceptually similar chunks
- Copy the chunk_id field back EXACTLY as given — do not alter it
"""

_FUZZY_SYSTEM = """\
You are a CTI analyst experiencing "memory fog" — you vaguely remember reading threat reports \
but can only recall fragments and impressions, not specifics.

Given several corpus chunks summarised below, write ONE memory-fog search query obeying ALL rules:

1. Use ONLY vague, conceptual language — NO exact technique IDs (T1059, etc.), malware names, \
tool names, CVE numbers, or specific IOCs from the chunks
2. Simulate PARTIAL knowledge: you know the victim industry OR threat actor region, \
but NOT the specific tool or technique used
3. Use hedging language such as: "something about", "I think it involved", \
"vaguely recall", "related to", "might have been"
4. Describe the VIBE or scenario impression — not the technical facts
5. The query must read as natural analyst shorthand, not a technical specification

Good examples of memory-fog queries:
- "something about Eastern European actors going after bank login pages, credential theft vibes"
- "I think I read about a healthcare breach involving file tampering, or maybe exfil?"
- "vaguely recall a report on energy sector intrusions, remote access somehow"
- "wasn't there something about persistence on Windows endpoints tied to a nation-state group?"

Also extract from the chunk metadata: ATT&CK technique IDs (if any) and the source tags present.
"""

# ---------------------------------------------------------------------------
# Qdrant sampling
# ---------------------------------------------------------------------------

# How many chunks to pull per source for each category pool.
# whois/pdns excluded from precise/fuzzy — those collections are sparse and
# IOC-record chunks don't produce strong retrieval evaluation queries.
# _PRECISE_SOURCES  = {"mitre": 7, "otx": 9, "pdf": 4}    # total = 20
# _SEMANTIC_SOURCES = {"mitre": 10, "otx": 6, "pdf": 4}    # total = 20
# _FUZZY_SOURCES    = {"mitre": 40, "otx": 35, "pdf": 25}  # total = 100 → 20 batches×5
# How many chunks to pull per source for each category pool
_PRECISE_SOURCES  = {"mitre": 5, "otx": 8, "pdf": 4, "whois": 2, "pdns": 1}
_SEMANTIC_SOURCES = {"mitre": 10, "otx": 6, "pdf": 4}
_FUZZY_SOURCES    = {"mitre": 30, "otx": 30, "pdf": 20, "whois": 10, "pdns": 10}
_ATTACK_RE = re.compile(r"T\d{4}(?:\.\d{3})?")


def _scroll_source(
    client: Any, collection: str, source: str, limit: int
) -> list[dict[str, Any]]:
    from qdrant_client.http import models as qm  # type: ignore[import]

    records, _ = client.scroll(
        collection_name=collection,
        scroll_filter=qm.Filter(
            must=[qm.FieldCondition(key="source", match=qm.MatchValue(value=source))]
        ),
        limit=limit,
        with_payload=True,
        with_vectors=False,
    )
    return [
        r.payload
        for r in records
        if r.payload and len(r.payload.get("content", "")) > 120
    ]


def _sample_chunks(
    client: Any,
    collection: str,
    source_counts: dict[str, int],
    rng: random.Random,
    fetch_multiplier: int = 4,
) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    for source, n in source_counts.items():
        pool = _scroll_source(client, collection, source, n * fetch_multiplier)
        chunks.extend(rng.sample(pool, min(n, len(pool))))
    return chunks


def _extract_attack_ids(chunk: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    if aid := (chunk.get("metadata") or {}).get("attack_id"):
        ids.append(str(aid).strip().upper())
    ids.extend(_ATTACK_RE.findall(chunk.get("content", "")))
    return list(dict.fromkeys(ids))


# ---------------------------------------------------------------------------
# Query generation
# ---------------------------------------------------------------------------

def _generate_precise(
    llm: instructor.Instructor,
    model: str,
    chunk: dict[str, Any],
    seed_ids: set[str],
) -> PreciseQueryResponse | None:
    chunk_id = chunk.get("id", "")
    user_msg = (
        f"chunk_id: {chunk_id}\n"
        f"source: {chunk.get('source', '')}\n\n"
        f"Content:\n{chunk.get('content', '')[:800]}"
    )
    try:
        resp = llm.chat.completions.create(
            model=model,
            max_tokens=512,
            messages=[
                {"role": "system", "content": _PRECISE_SYSTEM},
                {"role": "user", "content": user_msg},
            ],
            response_model=PreciseQueryResponse,
        )
        if resp.expected_chunk_id not in seed_ids:
            resp = PreciseQueryResponse(
                query=resp.query,
                expected_chunk_id=chunk_id,
                notes=resp.notes + " [chunk_id corrected]",
            )
        return resp
    except Exception as exc:
        print(f"  [warn] precise failed for {chunk_id}: {exc}", file=sys.stderr)
        return None


def _generate_semantic(
    llm: instructor.Instructor,
    model: str,
    chunk: dict[str, Any],
    seed_ids: set[str],
) -> SemanticQueryResponse | None:
    chunk_id = chunk.get("id", "")
    user_msg = (
        f"chunk_id: {chunk_id}\n"
        f"source: {chunk.get('source', '')}\n\n"
        f"Content:\n{chunk.get('content', '')[:800]}"
    )
    try:
        resp = llm.chat.completions.create(
            model=model,
            max_tokens=512,
            messages=[
                {"role": "system", "content": _SEMANTIC_SYSTEM},
                {"role": "user", "content": user_msg},
            ],
            response_model=SemanticQueryResponse,
        )
        if resp.expected_chunk_id not in seed_ids:
            resp = SemanticQueryResponse(
                query=resp.query,
                expected_chunk_id=chunk_id,
                notes=resp.notes + " [chunk_id corrected]",
            )
        return resp
    except Exception as exc:
        print(f"  [warn] semantic failed for {chunk_id}: {exc}", file=sys.stderr)
        return None


def _generate_fuzzy(
    llm: instructor.Instructor,
    model: str,
    batch: list[dict[str, Any]],
) -> FuzzyQueryResponse | None:
    summaries = "\n\n".join(
        f"[chunk {i+1}] source={c.get('source', '')} | "
        f"snippet={c.get('content', '')[:300]}"
        for i, c in enumerate(batch)
    )
    try:
        return llm.chat.completions.create(
            model=model,
            max_tokens=512,
            messages=[
                {"role": "system", "content": _FUZZY_SYSTEM},
                {"role": "user", "content": f"Chunk batch:\n\n{summaries}"},
            ],
            response_model=FuzzyQueryResponse,
        )
    except Exception as exc:
        print(f"  [warn] fuzzy batch failed: {exc}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Build CTI evaluation query set")
    parser.add_argument("--n-precise", type=int, default=20)
    parser.add_argument("--n-semantic", type=int, default=20)
    parser.add_argument("--n-fuzzy", type=int, default=20)
    parser.add_argument("--output", default="data/eval/query_set.jsonl")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--model", default="llama-3.3-70b-versatile")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Sample chunks and show stats without calling the LLM",
    )
    args = parser.parse_args()

    rng = random.Random(args.seed)
    settings = get_settings()
    output_path = Path(args.output)

    from qdrant_client import QdrantClient  # type: ignore[import]

    qdrant = QdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key.get_secret_value() or None,
    )
    collection = settings.qdrant_collection

    print("Sampling corpus chunks from Qdrant...")
    precise_chunks = _sample_chunks(qdrant, collection, _PRECISE_SOURCES, rng)[: args.n_precise]
    semantic_chunks = _sample_chunks(qdrant, collection, _SEMANTIC_SOURCES, rng)[: args.n_semantic]
    fuzzy_pool = _sample_chunks(qdrant, collection, _FUZZY_SOURCES, rng)

    rng.shuffle(fuzzy_pool)
    batch_size = 5
    fuzzy_batches = [
        fuzzy_pool[i : i + batch_size]
        for i in range(0, min(len(fuzzy_pool), args.n_fuzzy * batch_size), batch_size)
    ][: args.n_fuzzy]

    print(
        f"  precise seeds={len(precise_chunks)}, "
        f"semantic seeds={len(semantic_chunks)}, "
        f"fuzzy batches={len(fuzzy_batches)}×{batch_size}"
    )

    if args.dry_run:
        print("[dry-run] skipping LLM calls.")
        return

    if settings.ollama_enabled:
        from openai import OpenAI  # type: ignore[import]

        raw = OpenAI(base_url=settings.ollama_base_url, api_key="ollama")
        llm = instructor.from_openai(raw, mode=instructor.Mode.JSON)
        if args.model == "llama-3.3-70b-versatile":
            args.model = settings.ollama_model
        print(f"LLM provider: ollama  model={args.model}")
    else:
        groq_key = settings.groq_api_key.get_secret_value()
        if not groq_key:
            print("ERROR: GROQ_API_KEY required (or set OLLAMA_ENABLED=true).", file=sys.stderr)
            sys.exit(1)
        llm = instructor.from_groq(Groq(api_key=groq_key), mode=instructor.Mode.JSON)
        print(f"LLM provider: groq  model={args.model}")
    all_seed_ids = {c.get("id", "") for c in precise_chunks + semantic_chunks}

    records: list[QuerySetRecord] = []

    print(f"\nGenerating {len(precise_chunks)} PRECISE queries...")
    for i, chunk in enumerate(precise_chunks):
        resp = _generate_precise(llm, args.model, chunk, all_seed_ids)
        if resp is None:
            continue
        records.append(QuerySetRecord(
            query_id=f"P{i+1:03d}",
            query=resp.query,
            category=QueryCategory.PRECISE,
            expected_chunk_ids=[resp.expected_chunk_id],
            gold_attack_ids=_extract_attack_ids(chunk),
            gold_sources=[chunk.get("source", "")],
            reference_answer=None,
            notes=resp.notes,
        ))
        print(f"  P{i+1:03d}: {resp.query[:80]}")

    print(f"\nGenerating {len(semantic_chunks)} SEMANTIC queries...")
    for i, chunk in enumerate(semantic_chunks):
        resp = _generate_semantic(llm, args.model, chunk, all_seed_ids)
        if resp is None:
            continue
        records.append(QuerySetRecord(
            query_id=f"S{i+1:03d}",
            query=resp.query,
            category=QueryCategory.SEMANTIC,
            expected_chunk_ids=[resp.expected_chunk_id],
            gold_attack_ids=_extract_attack_ids(chunk),
            gold_sources=[chunk.get("source", "")],
            reference_answer=None,
            notes=resp.notes,
        ))
        print(f"  S{i+1:03d}: {resp.query[:80]}")

    print(f"\nGenerating {len(fuzzy_batches)} FUZZY (memory-fog) queries...")
    for i, batch in enumerate(fuzzy_batches):
        resp = _generate_fuzzy(llm, args.model, batch)
        if resp is None:
            continue
        gold_sources = resp.gold_sources or list({c.get("source", "") for c in batch})
        records.append(QuerySetRecord(
            query_id=f"F{i+1:03d}",
            query=resp.query,
            category=QueryCategory.FUZZY,
            expected_chunk_ids=[],
            gold_attack_ids=resp.gold_attack_ids or [],
            gold_sources=gold_sources,
            reference_answer=None,
            notes=resp.notes,
        ))
        print(f"  F{i+1:03d}: {resp.query[:80]}")

    save_query_set(records, output_path)
    p = sum(1 for r in records if r.category == QueryCategory.PRECISE)
    s = sum(1 for r in records if r.category == QueryCategory.SEMANTIC)
    f = sum(1 for r in records if r.category == QueryCategory.FUZZY)
    print(f"\nSaved {len(records)} queries → {output_path}  (P={p} S={s} F={f})")
    if len(records) < 60:
        print(f"WARNING: {len(records)} < 60 target — increase --n-* or fix failed generations.")


if __name__ == "__main__":
    main()
