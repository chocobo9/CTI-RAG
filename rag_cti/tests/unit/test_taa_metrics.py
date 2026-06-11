"""Unit tests for taa_metrics — faithful cti-bench actor-attribution scorer.

Expected connection classes are reasoned directly from the shipped actor
dictionaries (NOT produced by the function under test):

  alias_dict['bahamut']        == ['dropping elephant']        -> direct alias  -> C
  alias_dict['charmingcypress'] -> 'mint sandstorm' -> 'phosphorus'             -> C (2-hop)
  related_dict['confucius']    == ['patchwork'] (no alias path)                 -> P
  related_dict['bahamut']      == ['windshift']  (no alias path)                -> P
  'fin7' is absent from both dicts                                             -> I
"""

from __future__ import annotations

import pickle
from pathlib import Path

import pytest

from rag_cti.evaluation.taa_metrics import (
    TAAResult,
    compute_taa_accuracy,
    load_actor_dicts,
    safe_unpickle,
    score_taa,
    threat_actor_connection,
)

_CTIBENCH_DIR = Path(__file__).resolve().parents[2] / "data" / "eval" / "ctibench"


@pytest.fixture(scope="module")
def actor_dicts() -> tuple[dict, dict]:
    # ctibench actor dicts are CC BY-NC-SA and deliberately untracked
    # (.gitignore: "copy locally") — absent in CI checkouts, so skip there.
    try:
        return load_actor_dicts(_CTIBENCH_DIR)
    except FileNotFoundError:
        pytest.skip(f"ctibench actor dicts not available under {_CTIBENCH_DIR}")


# ---------------------------------------------------------------------------
# load_actor_dicts
# ---------------------------------------------------------------------------


def test_load_actor_dicts_shape(actor_dicts: tuple[dict, dict]) -> None:
    alias, related = actor_dicts
    assert len(alias) == 37
    assert len(related) == 37
    assert alias["bahamut"] == ["dropping elephant"]
    assert related["confucius"] == ["patchwork"]


# ---------------------------------------------------------------------------
# threat_actor_connection — hand-reasoned cases
# ---------------------------------------------------------------------------


def test_alias_direct_is_correct(actor_dicts: tuple[dict, dict]) -> None:
    alias, related = actor_dicts
    assert threat_actor_connection("bahamut", "dropping elephant", alias, related) == "C"


def test_alias_is_bidirectional(actor_dicts: tuple[dict, dict]) -> None:
    # Reverse direction must also be Correct (dicts rebuilt symmetrically).
    alias, related = actor_dicts
    assert threat_actor_connection("dropping elephant", "bahamut", alias, related) == "C"


def test_alias_multi_hop_chain_is_correct(actor_dicts: tuple[dict, dict]) -> None:
    # charmingcypress -> mint sandstorm -> phosphorus (phosphorus is NOT a direct alias)
    alias, related = actor_dicts
    assert "phosphorus" not in alias["charmingcypress"]
    assert "phosphorus" in alias["mint sandstorm"]
    assert threat_actor_connection("charmingcypress", "phosphorus", alias, related) == "C"


def test_related_only_is_plausible(actor_dicts: tuple[dict, dict]) -> None:
    alias, related = actor_dicts
    assert threat_actor_connection("confucius", "patchwork", alias, related) == "P"


def test_related_edge_bahamut_windshift_is_plausible(actor_dicts: tuple[dict, dict]) -> None:
    alias, related = actor_dicts
    assert threat_actor_connection("bahamut", "windshift", alias, related) == "P"


def test_absent_actor_is_incorrect(actor_dicts: tuple[dict, dict]) -> None:
    alias, related = actor_dicts
    assert "fin7" not in alias
    assert "fin7" not in related
    assert threat_actor_connection("turla", "fin7", alias, related) == "I"
    assert threat_actor_connection("lazarus", "fin7", alias, related) == "I"


def test_case_and_whitespace_insensitive(actor_dicts: tuple[dict, dict]) -> None:
    alias, related = actor_dicts
    assert threat_actor_connection("  BAHAMUT ", "Dropping Elephant", alias, related) == "C"


# ---------------------------------------------------------------------------
# score_taa — aggregation (fractions per SPEC §M)
# ---------------------------------------------------------------------------


def test_score_taa_counts_and_fractions(actor_dicts: tuple[dict, dict]) -> None:
    alias, related = actor_dicts
    pairs = [
        ("bahamut", "dropping elephant"),  # C
        ("confucius", "patchwork"),  # P
        ("turla", "fin7"),  # I
    ]
    r = score_taa(pairs, alias, related)
    assert isinstance(r, TAAResult)
    assert (r.n, r.correct, r.plausible, r.incorrect) == (3, 1, 1, 1)
    assert r.correct_acc == pytest.approx(1 / 3)
    assert r.plausible_acc == pytest.approx(2 / 3)


# ---------------------------------------------------------------------------
# compute_taa_accuracy — faithful TSV port (PERCENTAGES)
# ---------------------------------------------------------------------------


def test_compute_taa_accuracy_from_tsv(actor_dicts: tuple[dict, dict], tmp_path: Path) -> None:
    alias, related = actor_dicts
    tsv = tmp_path / "resp.tsv"
    tsv.write_text(
        "GT\tpred\n"
        "bahamut\tdropping elephant\n"  # C
        "confucius\tpatchwork\n"  # P
        "turla\tfin7\n",  # I
        encoding="utf-8",
    )
    correct_pct, plausible_pct = compute_taa_accuracy(tsv, "pred", alias, related)
    assert correct_pct == pytest.approx(100 / 3, abs=1e-3)  # 1/3
    assert plausible_pct == pytest.approx(200 / 3, abs=1e-3)  # 2/3


# ---------------------------------------------------------------------------
# Restricted unpickler — security
# ---------------------------------------------------------------------------


def test_safe_unpickle_loads_data_only_pickle(tmp_path: Path) -> None:
    p = tmp_path / "ok.pickle"
    p.write_bytes(pickle.dumps({"apt29": ["cozy bear"]}))
    assert safe_unpickle(p) == {"apt29": ["cozy bear"]}


class _NeedsGlobal:
    """__reduce__ returns a global callable, forcing find_class on load."""

    def __reduce__(self):  # type: ignore[override]
        return (len, ([1, 2],))  # emits GLOBAL builtins.len; blocked before REDUCE


def test_safe_unpickle_blocks_global_lookup(tmp_path: Path) -> None:
    # Any pickle that references a global (here builtins.len) must be refused,
    # so a malicious pickle can never reach a REDUCE / code execution.
    p = tmp_path / "evil.pickle"
    p.write_bytes(pickle.dumps(_NeedsGlobal()))
    with pytest.raises(pickle.UnpicklingError):
        safe_unpickle(p)
