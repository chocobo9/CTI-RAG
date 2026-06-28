"""Unit tests for the agentic tool-call dedup cache (knowledge.tool_cache)."""

from __future__ import annotations

from rag_cti.knowledge.evidence_ledger import EvidenceLedger
from rag_cti.knowledge.tool_cache import ToolCache, as_duplicate, canonicalize_args

# --- canonicalize_args (shared by the action log AND the cache key) ------------


def test_canonicalize_args_sorts_keys() -> None:
    assert canonicalize_args({"b": "2", "a": "1"}) == "a=1, b=2"


def test_canonicalize_args_truncates_long_values() -> None:
    assert canonicalize_args({"query": "x" * 100}) == "query=" + "x" * 60 + "…"


def test_canonicalize_args_empty_is_blank() -> None:
    assert canonicalize_args({}) == ""


def test_canonicalize_matches_action_log() -> None:
    # The action log MUST key calls identically to the cache, else "what I did" and "what I
    # cached" diverge. add_action stores exactly canonicalize_args(args) — this is the contract.
    led = EvidenceLedger()
    args = {"subject_id": "actor_G0016", "predicate": "uses"}
    led.add_action("graph_query", args)
    assert led.actions[-1].args == canonicalize_args(args)


# --- ToolCache get/put ---------------------------------------------------------


def test_cache_miss_then_put_then_hit() -> None:
    cache = ToolCache()
    assert cache.get("retrieve", {"query": "apt29"}) is None
    cache.put("retrieve", {"query": "apt29"}, {"chunks": [1, 2]})
    assert cache.get("retrieve", {"query": "apt29"}) == {"chunks": [1, 2]}


def test_cache_distinguishes_args() -> None:
    cache = ToolCache()
    cache.put("retrieve", {"query": "a"}, {"r": "a"})
    assert cache.get("retrieve", {"query": "b"}) is None


def test_cache_key_is_name_and_canonical_args() -> None:
    assert ToolCache.key("resolve_entity", {"name": "APT29"}) == "resolve_entity(name=APT29)"


def test_ledger_cache_get_put_roundtrip() -> None:
    led = EvidenceLedger()
    assert led.cache_get("graph_query", {"subject_id": "x"}) is None
    led.cache_put("graph_query", {"subject_id": "x"}, {"total": 5})
    assert led.cache_get("graph_query", {"subject_id": "x"}) == {"total": 5}


# --- as_duplicate (model-facing duplicate payload) -----------------------------


def test_as_duplicate_dict_merges_marker() -> None:
    out = as_duplicate({"total": 3, "objects": []})
    assert out["cached"] is True
    assert out["total"] == 3
    assert "do not repeat" in out["note"].lower()


def test_as_duplicate_nondict_nests_under_result() -> None:
    out = as_duplicate([{"entity_id": "actor_G0016"}])
    assert out["cached"] is True
    assert out["result"] == [{"entity_id": "actor_G0016"}]
