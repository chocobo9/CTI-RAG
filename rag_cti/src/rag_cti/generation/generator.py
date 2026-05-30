from __future__ import annotations

import time
from typing import Any

from rag_cti._logging import get_logger
from rag_cti.evaluation.set_metrics import normalize_id
from rag_cti.evaluation.techniquerag import parse_gold_ids
from rag_cti.generation.context_builder import build_context_messages, extract_cited_ids
from rag_cti.generation.llm_router import LLMRouter, TaskType
from rag_cti.generation.prompts import (
    ACTOR_ATTRIBUTION_SYSTEM,
    TECHNIQUE_ANNOTATION_SYSTEM,
)
from rag_cti.observability.tracing import add_trace_metadata, traced
from rag_cti.types import GeneratedAnswer, QueryResult, RetrievalResult

logger = get_logger(__name__)

# Returned by _call_llm when the provider call raises (product behaviour kept).
_LLM_FAILURE_SENTINEL = "Unable to generate answer: LLM call failed."

# How many reranked candidates to inject into the eval-only annotation prompts.
# SPEC §B.1: retrieve top_k=40 then inject top-10 — wider than TechniqueRAG's
# k=3 because this corpus mixes OTX/PDF noise, so we keep extra margin.
DEFAULT_CANDIDATE_K = 10

# Retrieval depth for the technique-annotation path before per-technique dedup.
# CERTIFIED baseline (Phase C): callers retrieve top-TECHNIQUE_RETRIEVE_K, then
# annotate_techniques dedups to distinct techniques before injecting candidate_k.
TECHNIQUE_RETRIEVE_K = 300

# Cap per-candidate content so the prompt stays bounded with many candidates.
_CANDIDATE_CONTENT_CHARS = 600

# Model outputs that mean "no actor" — normalized to "" so they score as Incorrect.
_ACTOR_NONE_TOKENS = frozenset(
    {"", "none", "unknown", "n/a", "na", "no actor", "cannot be determined", "undetermined"}
)


class Generator:
    """Generates grounded CTI answers via Groq, with context injected in the user message."""

    def __init__(self, client: Any, router: LLMRouter, settings: Any) -> None:
        self._client = client
        self._router = router
        self._settings = settings

    @traced("generation", run_type="llm")
    def generate(self, query: str, query_result: QueryResult) -> GeneratedAnswer:
        model = self._router.model_for(TaskType.ANALYSIS)
        messages = build_context_messages(query, query_result.results)

        t0 = time.perf_counter()
        answer_text = self._call_llm(model, messages)
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)

        cited = extract_cited_ids(answer_text)
        add_trace_metadata(
            model=model,
            cited_chunk_ids=cited,
            generation_ms=elapsed_ms,
            context_chunk_ids=[r.document.id for r in query_result.results],
        )
        logger.debug(
            "generation complete",
            model=model,
            cited_count=len(cited),
            elapsed_ms=elapsed_ms,
        )
        return GeneratedAnswer(
            query=query,
            answer=answer_text,
            cited_chunk_ids=cited,
            query_result=query_result,
            generation_ms=elapsed_ms,
            model=model,
        )

    # ------------------------------------------------------------------
    # Eval-only annotation heads (Phase B). NOT traced, NOT used by generate().
    # Reuse _call_llm; raise on provider failure so certification/scoring can
    # abort rather than silently score a fabricated empty answer (CLAUDE.md §2.6).
    # ------------------------------------------------------------------

    def annotate_techniques(
        self,
        text: str,
        query_result: QueryResult,
        candidate_k: int = DEFAULT_CANDIDATE_K,
    ) -> list[str]:
        """Extract the ATT&CK technique-ID set the text describes (order-deduped)."""
        model = self._router.model_for(TaskType.ANALYSIS)
        candidates = _format_candidates(_dedup_to_distinct_techniques(query_result.results), candidate_k)
        messages = [
            {"role": "system", "content": TECHNIQUE_ANNOTATION_SYSTEM},
            {
                "role": "user",
                "content": (
                    f"CTI text:\n{text}\n\n"
                    f"Candidate techniques (top {candidate_k} retrieved):\n{candidates}\n\n"
                    "ATT&CK technique IDs:"
                ),
            },
        ]
        output = self._call_llm(model, messages)
        if output == _LLM_FAILURE_SENTINEL:
            raise RuntimeError("annotate_techniques: LLM call failed")
        return parse_technique_ids(output)

    def attribute_actor(
        self,
        text: str,
        query_result: QueryResult,
        candidate_k: int = DEFAULT_CANDIDATE_K,
    ) -> str:
        """Return the single most likely threat-actor name ("" if undetermined)."""
        model = self._router.model_for(TaskType.ANALYSIS)
        candidates = _format_candidates(query_result.results, candidate_k)
        messages = [
            {"role": "system", "content": ACTOR_ATTRIBUTION_SYSTEM},
            {
                "role": "user",
                "content": (
                    f"CTI text:\n{text}\n\n"
                    f"Candidate context (top {candidate_k} retrieved):\n{candidates}\n\n"
                    "Threat actor:"
                ),
            },
        ]
        output = self._call_llm(model, messages)
        if output == _LLM_FAILURE_SENTINEL:
            raise RuntimeError("attribute_actor: LLM call failed")
        return parse_actor_name(output)

    def _call_llm(self, model: str, messages: list[dict[str, Any]]) -> str:
        try:
            response = self._client.chat.completions.create(
                model=model,
                max_tokens=self._settings.generation_max_tokens,
                messages=messages,
            )
            return _extract_text(response)
        except Exception as exc:
            logger.warning("generation llm call failed", error=str(exc))
            return _LLM_FAILURE_SENTINEL


def _extract_text(response: Any) -> str:
    return response.choices[0].message.content or ""


# ---------------------------------------------------------------------------
# Eval-only parsers + candidate formatting (module-level, pure, unit-testable)
# ---------------------------------------------------------------------------

def parse_technique_ids(output: str) -> list[str]:
    """Extract ATT&CK technique IDs from raw LLM output, order-preserving deduped.

    Reuses techniquerag.parse_gold_ids (the same _TECHNIQUE_RE used elsewhere) so
    that "T1059.001,T1027", prose like "describes T1059 and T1027", and "NONE"
    all parse consistently. Returns [] when no ID is present.
    """
    seen: set[str] = set()
    ids: list[str] = []
    for tid in parse_gold_ids(output):
        if tid not in seen:
            seen.add(tid)
            ids.append(tid)
    return ids


def parse_actor_name(output: str) -> str:
    """Extract a single actor name from raw LLM output.

    Takes the first non-empty line, strips wrapping quotes/markdown/whitespace and
    a trailing period, and maps explicit "no actor" replies (NONE/unknown/...) to "".
    """
    if not output:
        return ""
    line = next((ln.strip() for ln in output.splitlines() if ln.strip()), "")
    line = line.strip(" \t\"'`*").rstrip(".").strip()
    if line.lower() in _ACTOR_NONE_TOKENS:
        return ""
    return line


def _dedup_to_distinct_techniques(results: list[RetrievalResult]) -> list[RetrievalResult]:
    """Collapse retrieved candidates to one chunk per ATT&CK technique (score desc).

    Ported from the certified diag_retrieval_ceiling dedup logic: normalize each
    candidate's attack_id to technique level, drop candidates with no attack_id (no
    technique label = useless for technique annotation), keep the highest-scoring
    chunk per distinct technique, and return them sorted by score descending. The
    caller then injects the top candidate_k. Immutable — never mutates the inputs.
    """
    best: dict[str, RetrievalResult] = {}
    for r in results:
        tech = normalize_id(r.document.metadata.get("attack_id") or "", "technique")
        if not tech:
            continue
        prev = best.get(tech)
        if prev is None or r.score > prev.score:
            best[tech] = r
    return sorted(best.values(), key=lambda r: r.score, reverse=True)


def _format_candidates(results: list[RetrievalResult], candidate_k: int) -> str:
    """Render the top-k retrieved results as numbered candidate lines for the prompt."""
    lines: list[str] = []
    for i, r in enumerate(results[:candidate_k], start=1):
        metadata = r.document.metadata or {}
        attack_id = metadata.get("attack_id") or "-"
        content = " ".join((r.document.content or "").split())
        if len(content) > _CANDIDATE_CONTENT_CHARS:
            content = content[:_CANDIDATE_CONTENT_CHARS] + "…"
        lines.append(f"[{i}] attack_id={attack_id} | source={r.document.source} | {content}")
    return "\n".join(lines) if lines else "(no candidates retrieved)"
