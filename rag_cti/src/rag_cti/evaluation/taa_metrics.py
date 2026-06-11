"""Threat-actor attribution (TAA) scoring — faithful port of the cti-bench scorer.

Source: maveryn/cti-bench ``evaluation/evaluation.ipynb`` cells 17-18
(``threat_actor_connection`` / ``is_alias_connected`` / ``is_related_connected``
/ ``compute_taa_accuracy``). Logic is reproduced verbatim per PROJECT_SPEC.md §M
and CLAUDE.md §2.8 — DO NOT loosen the actor matching (no substring matching, no
invented rules). Connection classes:
    "C" — connected via an alias chain        (Correct)
    "P" — connected via a related-group chain (Plausible)
    "I" — no connection found                 (Incorrect)

Actor dictionaries originate from the repo's ``alias_dict.pickle`` /
``related_dict.pickle``. Those pickles were verified benign (pickletools: only
dict/list/str opcodes, no GLOBAL/REDUCE) and converted to JSON. At runtime we
load the JSON; if only the pickle is present we deserialize with a restricted
unpickler that refuses every global, so untrusted pickles cannot execute code.
"""

from __future__ import annotations

import json
import pickle
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

_DEFAULT_CTIBENCH_DIR = Path("data/eval/ctibench")

ActorDict = dict[str, list[str]]


# ---------------------------------------------------------------------------
# Safe loading of the actor dictionaries
# ---------------------------------------------------------------------------


class _RestrictedUnpickler(pickle.Unpickler):
    """Unpickler that refuses ALL global lookups.

    The actor dicts are pure ``dict[str, list[str]]`` (no custom classes), so a
    legitimate load never needs ``find_class``. Refusing it removes the
    arbitrary-code-execution risk of unpickling externally-sourced files.
    """

    def find_class(self, module: str, name: str) -> object:  # noqa: D401
        raise pickle.UnpicklingError(f"blocked global lookup: {module}.{name}")


def safe_unpickle(path: Path) -> ActorDict:
    """Deserialize a data-only pickle, refusing any code-execution opcodes."""
    with open(path, "rb") as fh:
        return cast(ActorDict, _RestrictedUnpickler(fh).load())


def load_actor_dicts(ctibench_dir: Path = _DEFAULT_CTIBENCH_DIR) -> tuple[ActorDict, ActorDict]:
    """Load (alias_dict, related_dict). Prefer JSON; fall back to safe-unpickle.

    Returns dicts of ``actor -> [aliases/related actors]`` exactly as shipped by
    cti-bench (case/whitespace are normalized later, inside the scorer).
    """
    alias = _load_one(ctibench_dir, "alias_dict")
    related = _load_one(ctibench_dir, "related_dict")
    return alias, related


def _load_one(ctibench_dir: Path, stem: str) -> ActorDict:
    json_path = ctibench_dir / f"{stem}.json"
    if json_path.exists():
        with open(json_path, encoding="utf-8") as fh:
            return cast(ActorDict, json.load(fh))
    pickle_path = ctibench_dir / f"{stem}.pickle"
    if pickle_path.exists():
        return safe_unpickle(pickle_path)
    raise FileNotFoundError(f"actor dict not found: {json_path} or {pickle_path}")


# ---------------------------------------------------------------------------
# Scorer (verbatim logic from cti-bench)
# ---------------------------------------------------------------------------


def is_alias_connected(actor1: str, actor2: str, alias_dict: ActorDict) -> bool:
    """BFS over the alias graph only. Verbatim from cti-bench."""
    visited: set[str] = set()
    queue = [actor1]
    while queue:
        current_actor = queue.pop(0)
        visited.add(current_actor)
        for alias in alias_dict.get(current_actor, []):
            if alias == actor2:
                return True
            if alias not in visited:
                queue.append(alias)
    return False


def is_related_connected(
    actor1: str, actor2: str, alias_dict: ActorDict, related_dict: ActorDict
) -> bool:
    """BFS over both alias and related-group edges. Verbatim from cti-bench."""
    visited: set[str] = set()
    queue = [actor1]
    while queue:
        current_actor = queue.pop(0)
        visited.add(current_actor)
        for alias in alias_dict.get(current_actor, []):
            if alias == actor2:
                return True
            if alias not in visited:
                queue.append(alias)
        for related_actor in related_dict.get(current_actor, []):
            if related_actor == actor2:
                return True
            if related_actor not in visited:
                queue.append(related_actor)
    return False


def threat_actor_connection(
    actor1: str, actor2: str, alias_dict: ActorDict, related_dict: ActorDict
) -> str:
    """Return "C" (alias chain), "P" (related chain), or "I" (none).

    Verbatim from cti-bench: both actors are lower/strip-normalized, and the
    dicts are rebuilt bidirectionally (symmetric) on every call.
    """
    actor1 = actor1.strip().lower()
    actor2 = actor2.strip().lower()

    # Normalize dictionaries and ensure bidirectional alias relationships.
    alias_dict = {
        k.strip().lower(): [v.strip().lower() for v in val] for k, val in alias_dict.items()
    }
    for actor in list(alias_dict):
        aliases = alias_dict[actor]
        for alias in aliases:
            if actor not in alias_dict.setdefault(alias, []):
                alias_dict[alias].append(actor)

    related_dict = {
        k.strip().lower(): [v.strip().lower() for v in val] for k, val in related_dict.items()
    }
    for actor in list(related_dict):
        related_groups = related_dict[actor]
        for related_actor in related_groups:
            if actor not in related_dict.setdefault(related_actor, []):
                related_dict[related_actor].append(actor)

    if is_alias_connected(actor1, actor2, alias_dict):
        return "C"
    if is_related_connected(actor1, actor2, alias_dict, related_dict):
        return "P"
    return "I"


# ---------------------------------------------------------------------------
# Accuracy aggregation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TAAResult:
    """correct_acc / plausible_acc as FRACTIONS in [0,1] per SPEC §M, plus counts."""

    n: int
    correct: int
    plausible: int
    incorrect: int
    correct_acc: float
    plausible_acc: float


def score_taa(
    pairs: Sequence[tuple[str, str]],
    alias_dict: ActorDict,
    related_dict: ActorDict,
) -> TAAResult:
    """Score (gt, pred) pairs. Mirrors cti-bench's argument order: gt is actor1.

    Correct Acc = #C / total ; Plausible Acc = (#C + #P) / total.
    """
    correct = plausible = incorrect = 0
    for gt, pred in pairs:
        res = threat_actor_connection(gt, pred, alias_dict, related_dict)
        if res == "C":
            correct += 1
        elif res == "P":
            plausible += 1
        else:
            incorrect += 1
    total = len(pairs)
    correct_acc = correct / total if total else 0.0
    plausible_acc = (correct + plausible) / total if total else 0.0
    return TAAResult(
        n=total,
        correct=correct,
        plausible=plausible,
        incorrect=incorrect,
        correct_acc=correct_acc,
        plausible_acc=plausible_acc,
    )


def compute_taa_accuracy(
    fname: str | Path,
    col: str,
    alias_dict: ActorDict,
    related_dict: ActorDict,
) -> tuple[float, float]:
    """Faithful port of cti-bench ``compute_taa_accuracy`` — returns PERCENTAGES.

    Reads a TSV with a 'GT' column and a prediction column ``col``; returns
    ``(correct_pct, plausible_pct)`` in [0, 100]. Used to reproduce the repo's
    own response-file numbers. Live scoring should use ``score_taa`` (fractions).
    """
    import pandas as pd  # local import: only the TSV path needs pandas

    df = pd.read_csv(fname, sep="\t")
    correct = plausible = total = 0
    for _, row in df.iterrows():
        # str() is the only intentional deviation from the cti-bench original
        # (which does row[col].lower()): it hardens against NaN / non-string
        # cells without changing results for valid string predictions.
        pred = str(row[col]).lower().strip()
        gt = str(row["GT"]).lower().strip()
        res = threat_actor_connection(gt, pred, alias_dict, related_dict)
        if res == "C":
            correct += 1
        elif res == "P":
            plausible += 1
        total += 1
    if total == 0:
        return 0.0, 0.0
    return correct / total * 100, (correct + plausible) / total * 100
