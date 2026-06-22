"""Per-run tool-call dedup cache for the agentic gather loop (over-calling mitigation).

The gather loop's five tools are idempotent within a single run — ``graph_query`` /
``resolve_entity`` / ``graph_outline`` / ``facts_for_evidence`` are deterministic graph reads,
and ``retrieve`` over the same query returns the same chunks — so an identical re-dispatch can
return the previously gathered result instead of re-executing the tool (a repeated ``retrieve``
is a full ``Pipeline.run``, the dominant per-call cost). The cache is keyed by the SAME canonical
(name, args) string the action log uses (``canonicalize_args`` lives here so both share one
implementation and "what I cached" never diverges from "what I did"). A hit returns the cached
payload flagged as a duplicate, so the model also sees it already gathered this.

Phase-0 measured exact-dups at only 0–15% of calls (the fresh state view already suppresses most
repeats), so this is primarily a correctness/guarantee lever — "never re-execute an identical
call" — with a modest, query-class-dependent latency benefit, not a headline speedup.

One cache per ``EvidenceLedger`` (held as a field); never shared across runs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Tool arg values longer than this are truncated in the canonical key (a long retrieve query
# still keys stably on its prefix; identical queries collide as intended).
_MAX_VALUE_LEN = 60


def canonicalize_args(args: dict[str, Any]) -> str:
    """Render tool args as a stable string: keys sorted, each value str-ified and truncated at
    ``_MAX_VALUE_LEN``. This is the single canonicalization shared by the action log
    (``ActionRecord.args``) and the tool-cache key, so a recorded call and a cached call always
    agree on call identity. Empty args -> ''."""
    parts: list[str] = []
    for key in sorted(args):
        value = str(args[key])
        if len(value) > _MAX_VALUE_LEN:
            value = value[:_MAX_VALUE_LEN] + "…"
        parts.append(f"{key}={value}")
    return ", ".join(parts)


@dataclass
class ToolCache:
    """Per-run ``(name, args) -> result`` store for idempotent gather tools. Plain dict; the
    thread-safety for concurrent dispatch (B2) comes from the owning ledger's lock, not here."""

    store: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def key(name: str, args: dict[str, Any]) -> str:
        return f"{name}({canonicalize_args(args)})"

    def get(self, name: str, args: dict[str, Any]) -> Any | None:
        return self.store.get(self.key(name, args))

    def put(self, name: str, args: dict[str, Any], result: Any) -> None:
        self.store[self.key(name, args)] = result


_DUPLICATE_NOTE = "Duplicate call — identical result already gathered this run; do not repeat."


def as_duplicate(cached: Any) -> dict[str, Any]:
    """Wrap a cached tool result as the model-facing duplicate payload. A dict result is
    shallow-merged with the duplicate marker; a non-dict (e.g. ``resolve_entity``'s list) is
    nested under ``result`` so the ``cached`` marker is always at the top level."""
    if isinstance(cached, dict):
        return {**cached, "cached": True, "note": _DUPLICATE_NOTE}
    return {"cached": True, "result": cached, "note": _DUPLICATE_NOTE}
