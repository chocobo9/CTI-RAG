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
from typing import Any

from rag_cti._logging import get_logger
from rag_cti.observability.tracing import traced
from rag_cti.retrieval.fusion import DEFAULT_RRF_K, reciprocal_rank_fusion
from rag_cti.retrieval.query_normalize import is_pure_ioc, prepare, refang, restore_iocs
from rag_cti.types import PayloadConstraint, RetrievalResult, RetrieverProto, SettingsProto

logger = get_logger(__name__)

# Temperature 0: rewriting must be deterministic and faithful, not creative.
_TEMPERATURE = 0.0

_SYSTEM_PROMPT = """You are a cyber-threat-intelligence (CTI) search-query normalizer. \
Given the conversation so far and the user's latest query, output a JSON array of one or \
more clean, standalone CTI search queries that capture the user's intent.

Output ONLY a JSON array of strings, e.g. ["first query", "second query"] — no prose, no markdown.

Rules:
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

Examples:
Latest query: Office macro persistence techniques
["Office macro persistence techniques"]

Latest query: waht persistnce techniqes duz Cozy Bear use
["What persistence techniques does Cozy Bear (APT29) use"]

Latest query: what malware does APT28 use and which countries do they target
["What malware does APT28 use", "Which countries does APT28 target"]

Conversation so far (most recent last):
- What techniques does APT29 use
Latest query: and who do they target?
["Who does APT29 target"]

Latest query: what drops <IOC_1>
["What malware drops <IOC_1>"]"""

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
                self._llm_provider = "anthropic"

    def rewrite(self, query: str, history: list[str] | None = None) -> list[str]:
        """Return one or more clean standalone queries. Falls back to ``[query]``."""
        if not getattr(self._settings, "query_rewrite_enabled", False):
            return [query]
        # A bare IOC lookup: the LLM can only mangle it — just refang and pass through.
        if is_pure_ioc(query):
            return [refang(query)]

        protected, mapping = prepare(query)
        raw = self._generate_raw(_SYSTEM_PROMPT, self._user_prompt(protected, history))
        subqueries = self._parse(raw, mapping)
        if not subqueries:
            return [query]  # fallback: never worse than no rewrite
        max_sub = getattr(self._settings, "query_rewrite_max_subqueries", 4)
        return subqueries[:max_sub]

    @staticmethod
    def _user_prompt(protected_query: str, history: list[str] | None) -> str:
        prefix = ""
        if history:
            turns = "\n".join(f"- {h}" for h in history)
            prefix = f"Conversation so far (most recent last):\n{turns}\n\n"
        return f"{prefix}Latest query: {protected_query}"

    def _parse(self, raw: str | None, mapping: dict[str, str]) -> list[str]:
        """Parse the JSON array, restore IOC placeholders, validate. [] on failure."""
        if not raw:
            return []
        text = _FENCE_RE.sub("", raw.strip())
        try:
            parsed = json.loads(text)
        except (json.JSONDecodeError, ValueError):
            return []
        if not isinstance(parsed, list):
            return []
        out = [str(q).strip() for q in parsed if isinstance(q, str) and str(q).strip()]
        if not out:
            return []
        # IOC-loss guard: if the query had IOCs but the model dropped every
        # placeholder, restoring can't reinsert them — fall back rather than drop.
        if mapping and not any(_PLACEHOLDER_RE.search(q) for q in out):
            logger.warning("query rewrite dropped all IOC placeholders, falling back")
            return []
        return [restore_iocs(q, mapping) for q in out]

    @traced("retrieval.query_rewrite.generate", run_type="llm")
    def _generate_raw(self, system: str, user: str) -> str | None:
        max_tokens = getattr(self._settings, "query_rewrite_max_tokens", 300)
        try:
            if self._llm_provider in ("groq", "ollama"):
                model = (
                    self._settings.ollama_model
                    if self._llm_provider == "ollama"
                    else self._settings.groq_query_model
                )
                resp = self._llm.chat.completions.create(
                    model=model,
                    max_tokens=max_tokens,
                    temperature=_TEMPERATURE,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                )
                text: str = (resp.choices[0].message.content or "").strip()
                return text or None
            response = self._llm.messages.create(
                model=self._settings.llm_routing_model,
                max_tokens=max_tokens,
                temperature=_TEMPERATURE,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            doc: str = response.content[0].text.strip()
            return doc or None
        except Exception as exc:
            logger.warning("query rewrite llm call failed, falling back", error=str(exc))
            return None


class QueryRewriteRetriever:
    """Retriever wrapper: rewrite the query into sub-queries, retrieve each through
    the base retriever, fuse with RRF (query-rewrite §3).

    Outermost wrapper (wraps HyDE/hybrid), so both production (``Pipeline.run``) and
    eval (which calls ``retriever.search`` directly) get the rewrite uniformly. A
    single sub-query (the common case) is a straight pass-through — identical to the
    pre-rewrite behaviour. ``history`` is keyword-only and optional, so this still
    satisfies the retriever protocol used elsewhere.
    """

    def __init__(
        self,
        base_retriever: RetrieverProto,
        rewriter: LLMQueryRewriter,
        rrf_k: int = DEFAULT_RRF_K,
    ) -> None:
        self._base = base_retriever
        self._rewriter = rewriter
        self._rrf_k = rrf_k

    def search(
        self,
        query: str,
        top_k: int = 10,
        *,
        source_filter: str | list[str] | None = None,
        constraint: PayloadConstraint | None = None,
        history: list[str] | None = None,
    ) -> list[RetrievalResult]:
        subqueries = self._rewriter.rewrite(query, history)
        if len(subqueries) == 1:
            return self._base.search(
                subqueries[0], top_k=top_k, source_filter=source_filter, constraint=constraint
            )
        result_lists = [
            self._base.search(sq, top_k=top_k, source_filter=source_filter, constraint=constraint)
            for sq in subqueries
        ]
        return reciprocal_rank_fusion(result_lists, k=self._rrf_k)[:top_k]
