"""Unit tests for the Phase D eval_attribution fixes.

Required by PROJECT_SPEC.md §D.2 step 2: prove the `actor_in_content` backdoor is
gone (otx_actor no longer hits merely because a chunk mentions the actor name),
and sanity-check the new set/pulse metric helpers. Inputs use real CTI values.

(Note: this test file is mandated by §D.2 step 2's verify clause even though the
SPEC's terse File Structure list only enumerates the A/B test files.)
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(_SCRIPTS))

ea = importlib.import_module("eval_attribution")


def _result(content: str = "", source: str = "otx", attack_id: str = "", pulse_id: str = ""):
    metadata: dict[str, str] = {}
    if attack_id:
        metadata["attack_id"] = attack_id
    if pulse_id:
        metadata["pulse_id"] = pulse_id
    doc = SimpleNamespace(content=content, source=source, metadata=metadata)
    return SimpleNamespace(document=doc)


def _otx_actor_record():
    return ea.QueryRecord(
        query_id="q-otx-1",
        query="Which APT used this infrastructure?",
        category="otx_actor",
        gold_attack_ids=[],
        gold_sources=["otx"],
        gold_actor="Cobalt",
        gold_pulse_ids=["598b04c2fa0f7856c241f5e1"],
        gold_malware=None,
        notes="",
    )


# ---------------------------------------------------------------------------
# Backdoor removal (the core §D.2-step-2 requirement)
# ---------------------------------------------------------------------------


def test_otx_actor_does_not_hit_on_actor_name_in_content() -> None:
    rec = _otx_actor_record()
    # Chunk mentions the actor name but has the WRONG pulse_id.
    # Pre-fix this returned True (actor_in_content backdoor); post-fix it must be False.
    bait = _result(
        content="Cobalt Group deployed Cobalt Strike beacons.", pulse_id="WRONG_PULSE_ID"
    )
    assert ea.is_hit(bait, rec) is False


def test_otx_actor_hits_only_on_correct_pulse_id() -> None:
    rec = _otx_actor_record()
    good = _result(content="some unrelated text", pulse_id="598b04c2fa0f7856c241f5e1")
    assert ea.is_hit(good, rec) is True


def test_otx_actor_no_pulse_no_name_is_miss() -> None:
    rec = _otx_actor_record()
    miss = _result(content="generic threat report", pulse_id="OTHER")
    assert ea.is_hit(miss, rec) is False


# ---------------------------------------------------------------------------
# Set / pulse metric helpers
# ---------------------------------------------------------------------------


def test_ranked_attack_ids_preserves_order_and_drops_blanks() -> None:
    results = [
        _result(attack_id="T1059.001", source="mitre"),
        _result(source="mitre"),  # no attack_id
        _result(attack_id="T1003", source="mitre"),
    ]
    assert ea._ranked_attack_ids(results, 10) == ["T1059.001", "T1003"]


def test_pulse_recall_at_k_micro() -> None:
    # q1 gold {p1,p2,p3}, ranked [p1,x,p2] -> @1 hit p1; @3 hits p1,p2
    # q2 gold {p4},        ranked [p4]      -> @1 hit p4
    ranked = [["p1", "x", "p2"], ["p4"]]
    gold = [["p1", "p2", "p3"], ["p4"]]
    out = ea._pulse_recall_at_k(ranked, gold, (1, 3))
    # @1: TP = p1 + p4 = 2 ; denom = 3 + 1 = 4 -> 0.5
    assert out[1] == 0.5
    # @3: TP = p1,p2 + p4 = 3 ; denom 4 -> 0.75
    assert out[3] == 0.75
