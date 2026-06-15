"""Query-time ontology expansion (retrieval-layer §6).

Widen a technique filter along the ATT&CK sub-technique hierarchy so a query for
a sub-technique also matches its parent, and a query for a parent also matches its
sub-techniques — **one hop in each direction** (siblings, two hops away, are not
pulled in). This is the forward-time version of the parent/child normalization
that previously lived only in eval ``set_metrics.py``.

It reads the M0 ``ontology_edges`` (``subtechnique-of`` rows); other edge kinds
(``belongs-to-tactic``) are definitional-but-not-hierarchical and ignored.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from rag_cti.types import PayloadConstraint


def expand_attack_ids(attack_ids: Iterable[str], edges: list[dict[str, Any]]) -> tuple[str, ...]:
    """Attack ids widened one hop over subtechnique-of edges; deduped and sorted."""
    parent_of: dict[str, str] = {}
    children_of: dict[str, list[str]] = {}
    for edge in edges:
        if edge.get("edge") != "subtechnique-of":
            continue
        child, parent = edge.get("child", ""), edge.get("parent", "")
        if child and parent:
            parent_of[child] = parent
            children_of.setdefault(parent, []).append(child)

    out: set[str] = set()
    for aid in attack_ids:
        out.add(aid)
        if aid in parent_of:
            out.add(parent_of[aid])  # sub-technique -> its parent
        out.update(children_of.get(aid, ()))  # parent -> its sub-techniques
    return tuple(sorted(out))


def expand_constraint(
    constraint: PayloadConstraint, edges: list[dict[str, Any]]
) -> PayloadConstraint:
    """Return ``constraint`` with ``attack_ids`` ontology-expanded.

    ``source_types`` / ``entity_ids`` are untouched; a constraint with no
    ``attack_ids`` is returned unchanged.
    """
    if not constraint.attack_ids:
        return constraint
    return constraint.model_copy(
        update={"attack_ids": expand_attack_ids(constraint.attack_ids, edges)}
    )
