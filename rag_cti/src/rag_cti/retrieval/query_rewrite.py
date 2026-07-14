"""LLM query rewrite — the query-understanding front-end (query-rewrite §2).

One LLM call turns a messy user query (typos, bad word order, aliases, defanged
IOCs, cross-turn references, multiple intents) into a list of clean, standalone
CTI search queries. Rules can't do fully-fuzzy typos or word-order or anaphora —
only an LLM that reads intent can; rules (``query_normalize``) only guard exact
IOCs from the LLM.

Returns a *list* so a compound query decomposes into sub-queries (the pipeline
retrieves each and fuses). Length 1 for a simple query — then the pipeline behaves
exactly as before. On any failure it falls back to ``[original query]`` (never
worse than no rewrite).
"""

from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from rag_cti._logging import get_logger
from rag_cti.observability.tracing import traced
from rag_cti.retrieval.constraint_boost import apply_constraint_boost
from rag_cti.retrieval.constraint_extract import (
    ENTITY_TYPES,
    ExtractedEntity,
    RewriteOutput,
    build_constraint,
)
from rag_cti.retrieval.fusion import DEFAULT_RRF_K, reciprocal_rank_fusion
from rag_cti.retrieval.query_normalize import is_pure_ioc, prepare, refang, restore_iocs
from rag_cti.types import PayloadConstraint, RetrievalResult, RetrieverProto, SettingsProto

logger = get_logger(__name__)

# Temperature 0: rewriting must be deterministic and faithful, not creative.
_TEMPERATURE = 0.0

_SYSTEM_PROMPT = """You are a cyber-threat-intelligence (CTI) search-query normalizer. \
Given the conversation so far and the user's latest query, output a JSON object with two keys:
- "queries": an array of one or more clean, standalone CTI search queries that capture intent.
- "entities": an array of the threat-intel entities explicitly named, each \
{"name": ..., "type": ...} with type one of "actor", "family", "technique".

Output ONLY the JSON object, e.g. \
{"queries": ["a query"], "entities": [{"name": "APT29", "type": "actor"}]} — no prose, no markdown.

Rules for "queries":
- If the query is already clear and single-intent, return it unchanged as one string.
- Fix spelling and word order; expand abbreviations (C2 -> command and control, \
LPE / priv-esc -> privilege escalation).
- Normalize a threat-actor or malware name to its common canonical name AND keep the \
original term, both in the same query string (e.g. "Cozy Bear (APT29)").
- Resolve references to earlier turns ("it", "they", "that group") into explicit terms \
using the conversation.
- Split a query that asks several distinct things into one query per thing; otherwise \
output exactly one query.
- Keep every <IOC_n> placeholder token EXACTLY as given; never alter, translate, or drop one.
- Do NOT invent techniques, IOCs, actors, or facts not present in the query.

Rules for "entities":
- Include ONLY entities the user explicitly named: threat actors/groups (type "actor"), \
malware/tools (type "family"), ATT&CK techniques (type "technique").
- For a technique, set "name" to its ATT&CK id (e.g. "T1566.001") when stated or unambiguous; \
otherwise omit that technique.
- Use the canonical name for actors/families when known (e.g. "APT29", "Cobalt Strike").
- "entities" may be empty. Never invent an entity not in the query. \
Never put an <IOC_n> placeholder in an entity.

Examples:
Latest query: Office macro persistence techniques
{"queries": ["Office macro persistence techniques"], "entities": []}

Latest query: waht persistnce techniqes duz Cozy Bear use
{"queries": ["What persistence techniques does Cozy Bear (APT29) use"], \
"entities": [{"name": "APT29", "type": "actor"}]}

Latest query: what malware does APT28 use and which countries do they target
{"queries": ["What malware does APT28 use", "Which countries does APT28 target"], \
"entities": [{"name": "APT28", "type": "actor"}]}

Conversation so far (most recent last):
- What techniques does APT29 use
Latest query: and who do they target?
{"queries": ["Who does APT29 target"], "entities": [{"name": "APT29", "type": "actor"}]}

Latest query: what drops <IOC_1>
{"queries": ["What malware drops <IOC_1>"], "entities": []}"""

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)
_PLACEHOLDER_RE = re.compile(r"<IOC_\d+>")


class LLMQueryRewriter:
    """Rewrites a query into clean standalone sub-queries via one LLM call."""

    def __init__(
        self,
        llm_client: object,
        settings: SettingsProto,
        llm_provider: str = "",
    ) -> None:
        self._settings = settings
        self._llm: Any
        # Mirror HyDE's client handling: accept (provider, client) or a bare client.
        if isinstance(llm_client, tuple) and len(llm_client) == 2:
            detected_provider, bare_client = llm_client
            self._llm = bare_client
            self._llm_provider = llm_provider or str(detected_provider)
        else:
            self._llm = llm_client
            if llm_provider:
                self._llm_provider = llm_provider
            elif hasattr(llm_client, "chat"):
                self._llm_provider = (
                    "ollama" if getattr(settings, "ollama_enabled", False) else "groq"
                )
            else:
                self._llm_provider = "groq"

    def rewrite(self, query: str, history: list[str] | None = None) -> list[str]:
        """Return one or more clean standalone queries. Falls back to ``[query]``.

        Back-compat thin wrapper over :meth:`rewrite_with_entities` for callers that
        only need the sub-queries (the queries side is unchanged from before entities).
        """
        return list(self.rewrite_with_entities(query, history).queries)

    def rewrite_with_entities(self, query: str, history: list[str] | None = None) -> RewriteOutput:
        """One LLM call → clean sub-queries + named entities. Never worse than no rewrite.

        On disable, a pure-IOC query, or any LLM/parse failure, returns
        ``RewriteOutput(queries=(query-or-refang,))`` with empty entities — identical
        sub-query behaviour to before entities existed. Entity extraction fails
        independently (a bad ``entities`` block never degrades the sub-queries).
        """
        if not getattr(self._settings, "query_rewrite_enabled", False):
            return RewriteOutput(queries=(query,))
        # A bare IOC lookup: the LLM can only mangle it — just refang and pass through.
        if is_pure_ioc(query):
            return RewriteOutput(queries=(refang(query),))

        protected, mapping = prepare(query)
        raw = self._generate_raw(_SYSTEM_PROMPT, self._user_prompt(protected, history))
        queries, entities = self._parse(raw, mapping)
        if not queries:
            return RewriteOutput(queries=(query,))  # fallback: never worse than no rewrite
        max_sub = getattr(self._settings, "query_rewrite_max_subqueries", 4)
        return RewriteOutput(queries=tuple(queries[:max_sub]), entities=tuple(entities))

    @staticmethod
    def _user_prompt(protected_query: str, history: list[str] | None) -> str:
        prefix = ""
        if history:
            turns = "\n".join(f"- {h}" for h in history)
            prefix = f"Conversation so far (most recent last):\n{turns}\n\n"
        return f"{prefix}Latest query: {protected_query}"

    def _parse(
        self, raw: str | None, mapping: dict[str, str]
    ) -> tuple[list[str], list[ExtractedEntity]]:
        """Parse the LLM output into (queries, entities). ``([], [])`` on query failure.

        Dual-form: the current object ``{"queries": [...], "entities": [...]}`` and the
        legacy bare array (treated as queries-only, entities empty) — so older canned
        responses / cached prompts keep working. Entities are parsed independently and
        defensively; a malformed entities block yields ``[]`` without touching queries.
        """
        if not raw:
            return [], []
        text = _FENCE_RE.sub("", raw.strip())
        try:
            parsed = json.loads(text)
        except (json.JSONDecodeError, ValueError):
            return [], []
        if isinstance(parsed, list):
            raw_queries: Any = parsed
            raw_entities: Any = []
        elif isinstance(parsed, dict):
            raw_queries = parsed.get("queries", [])
            raw_entities = parsed.get("entities", [])
        else:
            return [], []
        queries = self._parse_queries(raw_queries, mapping)
        if not queries:
            return [], []
        return queries, self._parse_entities(raw_entities)

    @staticmethod
    def _parse_queries(raw_queries: Any, mapping: dict[str, str]) -> list[str]:
        """Validate sub-query strings + restore IOC placeholders. [] on failure."""
        if not isinstance(raw_queries, list):
            return []
        out = [str(q).strip() for q in raw_queries if isinstance(q, str) and str(q).strip()]
        if not out:
            return []
        # IOC-loss guard: if the query had IOCs but the model dropped every
        # placeholder, restoring can't reinsert them — fall back rather than drop.
        if mapping and not any(_PLACEHOLDER_RE.search(q) for q in out):
            logger.warning("query rewrite dropped all IOC placeholders, falling back")
            return []
        return [restore_iocs(q, mapping) for q in out]

    @staticmethod
    def _parse_entities(raw_entities: Any) -> list[ExtractedEntity]:
        """Validate named entities defensively. Drops anything malformed silently.

        An IOC placeholder must never become an entity (it is not a real name and
        would corrupt resolution), so any name carrying one is rejected.
        """
        if not isinstance(raw_entities, list):
            return []
        out: list[ExtractedEntity] = []
        for item in raw_entities:
            if not isinstance(item, dict):
                continue
            name, etype = item.get("name"), item.get("type")
            if not isinstance(name, str) or not name.strip():
                continue
            if etype not in ENTITY_TYPES or _PLACEHOLDER_RE.search(name):
                continue
            out.append(ExtractedEntity(name=name.strip(), type=etype))
        return out

    @traced("retrieval.query_rewrite.generate", run_type="llm")
    def _generate_raw(self, system: str, user: str, max_tokens: int | None = None) -> str | None:
        output_tokens = max_tokens or getattr(self._settings, "query_rewrite_max_tokens", 300)
        try:
            model = (
                self._settings.ollama_model
                if self._llm_provider == "ollama"
                else self._settings.groq_query_model
            )
            resp = self._llm.chat.completions.create(
                model=model,
                max_tokens=output_tokens,
                temperature=_TEMPERATURE,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
            text: str = (resp.choices[0].message.content or "").strip()
            return text or None
        except Exception as exc:
            logger.warning("query rewrite llm call failed, falling back", error=str(exc))
            return None


class QueryRewriteRetriever:
    """Retriever wrapper: rewrite the query into sub-queries, retrieve each through
    the base retriever, fuse with RRF (query-rewrite §3), then optionally soft-boost
    results that match the query's structured constraint (retrieval routing).

    Outermost wrapper (wraps HyDE/hybrid), so both production (``Pipeline.run``) and
    eval (which calls ``retriever.search`` directly) get rewrite + boost uniformly. A
    single sub-query (the common case) is a straight pass-through — identical to the
    pre-rewrite behaviour. ``history`` is keyword-only and optional, so this still
    satisfies the retriever protocol used elsewhere.

    Routing has two entry shapes for one LLM call:
    - **Direct** (``search`` with no ``subqueries``): self-rewrites via
      :meth:`understand`, then soft-boosts here (the eval/direct-search terminus).
    - **Pipeline-driven** (``search`` with ``subqueries`` + ``boost_constraint``):
      the pipeline already called :meth:`understand` once and re-applies the boost
      after reranking, so this skips the LLM and just fans out + boosts.

    ``settings`` / ``ontology_nodes`` are optional: absent them, routing is off and
    behaviour is exactly the pre-routing rewrite-only wrapper.
    """

    def __init__(
        self,
        base_retriever: RetrieverProto,
        rewriter: LLMQueryRewriter,
        rrf_k: int = DEFAULT_RRF_K,
        *,
        settings: SettingsProto | None = None,
        ontology_nodes: list[dict[str, Any]] | None = None,
    ) -> None:
        self._base = base_retriever
        self._rewriter = rewriter
        self._rrf_k = rrf_k
        self._settings = settings
        self._ontology_nodes = ontology_nodes

    def understand(
        self, query: str, history: list[str] | None = None
    ) -> tuple[tuple[str, ...], PayloadConstraint]:
        """One LLM call → (sub-queries, boost constraint). The single understanding seam.

        The pipeline calls this once and passes the sub-queries back into
        :meth:`search` (so the LLM fires exactly once per query). Falls back to a
        ``.rewrite``-only rewriter (no entity support) and to an empty constraint when
        routing is disabled or no ontology is wired.
        """
        rewriter = self._rewriter
        if hasattr(rewriter, "rewrite_with_entities"):
            out = rewriter.rewrite_with_entities(query, history)
            subqueries, entities = out.queries, out.entities
        else:  # pragma: no cover - exercised via legacy test fakes only
            subqueries, entities = tuple(rewriter.rewrite(query, history)), ()
        if self._routing_enabled():
            return subqueries, build_constraint(query, entities, self._ontology_nodes)
        return subqueries, PayloadConstraint()

    def search(
        self,
        query: str,
        top_k: int = 10,
        *,
        source_filter: str | list[str] | None = None,
        constraint: PayloadConstraint | None = None,
        history: list[str] | None = None,
        subqueries: tuple[str, ...] | None = None,
        boost_constraint: PayloadConstraint | None = None,
    ) -> list[RetrievalResult]:
        # ``constraint`` is the hard payload pre-filter (flows to the store);
        # ``boost_constraint`` is the soft re-scoring signal — distinct concerns.
        # When the pipeline supplies ``subqueries`` it owns the boost (re-applied
        # post-rerank); applying it here too would double-count if the reranker is a
        # no-op. So seam-1 boost fires ONLY on the direct path (no subqueries given).
        pipeline_driven = subqueries is not None
        if subqueries is None:
            subqueries, boost_constraint = self.understand(query, history)
        results = self._fanout(subqueries, top_k, source_filter, constraint)
        if pipeline_driven:
            return results
        return self._maybe_boost(results, boost_constraint)

    def _fanout(
        self,
        subqueries: tuple[str, ...],
        top_k: int,
        source_filter: str | list[str] | None,
        constraint: PayloadConstraint | None,
    ) -> list[RetrievalResult]:
        if len(subqueries) == 1:
            return self._base.search(
                subqueries[0], top_k=top_k, source_filter=source_filter, constraint=constraint
            )
        result_lists = self._search_subqueries(subqueries, top_k, source_filter, constraint)
        return reciprocal_rank_fusion(result_lists, k=self._rrf_k)[:top_k]

    def _search_subqueries(
        self,
        subqueries: tuple[str, ...],
        top_k: int,
        source_filter: str | list[str] | None,
        constraint: PayloadConstraint | None,
    ) -> list[list[RetrievalResult]]:
        """One base search per sub-query, kept in submission order so RRF input is identical to
        the serial path. Serial by default; concurrent when
        ``query_rewrite_parallel_fanout_enabled`` — each sub-query is an INDEPENDENT HyDE+hybrid
        retrieval (the cross-encoder reranker runs at the Pipeline level, OUTSIDE this fan-out,
        so there is no shared-GPU contention here), so latency becomes max() not sum(). Each
        per-sub-query HyDE call hits the provider, so concurrency is capped and each search goes
        through the Groq admission limiter to stay under the 429 ceiling."""

        def _one(sq: str) -> list[RetrievalResult]:
            return self._base.search(
                sq, top_k=top_k, source_filter=source_filter, constraint=constraint
            )

        if self._settings is None:
            return [_one(sq) for sq in subqueries]

        from typing import cast

        from rag_cti.config import Settings
        from rag_cti.generation.limiter import get_limiter

        limiter = get_limiter("groq", cast(Settings, self._settings))
        cap = max(
            1,
            min(
                len(subqueries),
                int(getattr(self._settings, "query_rewrite_max_parallel_subqueries", 4)),
            ),
        )

        def _one_limited(sq: str) -> list[RetrievalResult]:
            with limiter.slot():
                return _one(sq)

        with ThreadPoolExecutor(max_workers=cap) as ex:
            return list(ex.map(_one_limited, subqueries))

    def _maybe_boost(
        self, results: list[RetrievalResult], boost_constraint: PayloadConstraint | None
    ) -> list[RetrievalResult]:
        if not self._routing_enabled() or boost_constraint is None or boost_constraint.is_empty:
            return results
        return apply_constraint_boost(results, boost_constraint, self._boost_weight())

    def _routing_enabled(self) -> bool:
        return bool(getattr(self._settings, "constraint_routing_enabled", False))

    def _boost_weight(self) -> float:
        return float(getattr(self._settings, "constraint_boost_weight", 0.0))
