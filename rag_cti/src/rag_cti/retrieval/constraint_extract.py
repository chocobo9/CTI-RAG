"""Build a structured boost constraint from a query + LLM-extracted entities.

The query-understanding front-end (``query_rewrite``) reuses its single LLM call
to emit named entities alongside the rewritten sub-queries. This module turns those
entities — plus deterministic regex/keyword signals read straight off the query —
into a :class:`PayloadConstraint` used for *soft* re-scoring (``constraint_boost``),
never a hard filter.

Two signal sources, merged into one constraint:
- **Deterministic (zero-LLM)**: technique ids via ``query_normalize._ATTACK_ID`` and
  source types via a conservative trigger-phrase vocabulary. These run even when the
  LLM rewrite is disabled.
- **LLM entities**: actor/family names resolved to stable ``entity_id``s through the
  *strict* (exact-only) registry resolver; technique mentions (whose name is an ATT&CK
  id) feed both ``attack_ids`` and the ``technique_*`` ``entity_id`` namespace.

Everything is conservative: an unresolved or ambiguous mention contributes nothing
(a wrong id would boost the wrong chunks). An all-empty constraint is a boost no-op.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from rag_cti.preprocess.entity_registry import resolve_entity_ids_strict
from rag_cti.retrieval.query_normalize import _ATTACK_ID
from rag_cti.types import PayloadConstraint

# Entity types we route. actor/family resolve by name/alias; technique by ATT&CK id.
ENTITY_TYPES = frozenset({"actor", "family", "technique"})

# A technique id (T1059 / T1059.001) — the only kind that belongs in the payload
# ``attack_ids`` field. _ATTACK_ID also matches TA/S/G/M/DET codes; those are NOT
# attack_ids (S/G live in entity_ids), so technique extraction filters to this shape.
_TECHNIQUE_ID = re.compile(r"T\d{4}(?:\.\d{3})?$")

# Conservative source_type trigger phrases. Values MUST equal the stored
# ``source_type`` (or ``source`` fallback) so the boost matcher can compare directly:
# mitre / otx / pdf / whois / pdns / vt. Bare "report" is intentionally excluded
# (far too broad to signal the PDF source).
_SOURCE_TYPE_TRIGGERS: dict[str, tuple[str, ...]] = {
    "mitre": ("mitre", "att&ck", "attack matrix", "technique catalog"),
    "otx": ("otx", "alienvault", "pulse", "open threat exchange"),
    "pdf": ("whitepaper", "white paper", "write-up", "writeup", "analysis report"),
    "whois": ("whois", "registrant", "registrar", "domain registration"),
    "pdns": ("passive dns", "pdns", "resolution history", "dns history"),
    "vt": ("virustotal", "vt report"),
}


@dataclass(frozen=True)
class ExtractedEntity:
    """A named entity the rewrite LLM pulled out of the query."""

    name: str
    type: str


@dataclass(frozen=True)
class RewriteOutput:
    """The full result of the single query-understanding LLM call."""

    queries: tuple[str, ...]
    entities: tuple[ExtractedEntity, ...] = field(default_factory=tuple)


def extract_attack_ids(text: str) -> tuple[str, ...]:
    """Technique ids (``T1059`` / ``T1059.001``) found in *text*, upper, deduped, sorted.

    Reuses the index-side IOC tokenizer's ATT&CK pattern so query and index agree,
    then keeps only technique-shaped ids (the payload ``attack_ids`` field carries
    techniques, not TA tactics or S/G/M object codes).
    """
    out = {m.upper() for m in _ATTACK_ID.findall(text) if _TECHNIQUE_ID.match(m.upper())}
    return tuple(sorted(out))


def extract_source_types(query: str) -> tuple[str, ...]:
    """Source types signalled by conservative trigger phrases in *query*."""
    q = query.lower()
    return tuple(
        sorted(
            st for st, triggers in _SOURCE_TYPE_TRIGGERS.items() if any(t in q for t in triggers)
        )
    )


def build_constraint(
    query: str,
    entities: tuple[ExtractedEntity, ...] = (),
    ontology_nodes: list[dict[str, object]] | None = None,
) -> PayloadConstraint:
    """Merge deterministic + entity signals into one :class:`PayloadConstraint`.

    ``attack_ids`` = regex technique ids ∪ technique-entity ids; ``entity_ids`` =
    resolved actor/family ids ∪ ``technique_*`` ids; ``source_types`` = trigger
    vocabulary. actor/family resolution needs *ontology_nodes* (name→id); without
    it those mentions contribute nothing. All-empty → ``is_empty`` → boost no-op.
    """
    attack_ids: set[str] = set(extract_attack_ids(query))
    entity_ids: set[str] = set()
    name_mentions: list[tuple[str, str]] = []

    for ent in entities:
        if ent.type == "technique":
            # A technique mention IS its id (exact identity, ungated). A non-id name
            # yields nothing; a bogus id simply never matches — harmless for a boost.
            for tid in extract_attack_ids(ent.name):
                attack_ids.add(tid)
                entity_ids.add(f"technique_{tid}")
        elif ent.type in ("actor", "family"):
            name_mentions.append((ent.name, ent.type))

    if name_mentions and ontology_nodes:
        entity_ids.update(resolve_entity_ids_strict(name_mentions, ontology_nodes))

    return PayloadConstraint(
        source_types=extract_source_types(query),
        attack_ids=tuple(sorted(attack_ids)),
        entity_ids=tuple(sorted(entity_ids)),
    )
