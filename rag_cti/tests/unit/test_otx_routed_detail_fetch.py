from __future__ import annotations

import json
from pathlib import Path

import pytest

from rag_cti.intermediate.otx_routed_detail_fetch import load_routed_detail_plan


def _write(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def test_plan_only_selects_missing_actor_evidenced_details(tmp_path: Path) -> None:
    manifest = tmp_path / "routing.jsonl"
    _write(
        manifest,
        [
            {"pulse_id": "fetch", "decision": "acquire_actor_evidenced", "existing_detail": False},
            {"pulse_id": "reuse", "decision": "acquire_multi_actor", "existing_detail": True},
            {"pulse_id": "defer", "decision": "deferred_query_only", "existing_detail": False},
        ],
    )

    plan = load_routed_detail_plan(manifest)

    assert plan.acquire_ids == ("fetch", "reuse")
    assert plan.network_ids == ("fetch",)
    assert plan.deferred_count == 1


def test_plan_rejects_duplicate_pulse_ids(tmp_path: Path) -> None:
    manifest = tmp_path / "routing.jsonl"
    _write(
        manifest,
        [
            {"pulse_id": "same", "decision": "acquire_actor_evidenced", "existing_detail": False},
            {"pulse_id": "same", "decision": "deferred_query_only", "existing_detail": False},
        ],
    )

    with pytest.raises(ValueError, match="duplicate pulse_id"):
        load_routed_detail_plan(manifest)


def test_plan_can_retry_only_latest_retryable_failures(tmp_path: Path) -> None:
    manifest = tmp_path / "routing.jsonl"
    _write(
        manifest,
        [
            {"pulse_id": "done", "decision": "acquire_actor_evidenced", "existing_detail": False},
            {"pulse_id": "retry", "decision": "acquire_unmapped_actor_label", "existing_detail": False},
            {"pulse_id": "terminal", "decision": "acquire_ambiguous_actor", "existing_detail": False},
        ],
    )
    statuses = tmp_path / "statuses.jsonl"
    _write(
        statuses,
        [
            {"pulse_id": "done", "status": "complete"},
            {"pulse_id": "retry", "status": "retryable_error"},
            {"pulse_id": "terminal", "status": "not_found"},
        ],
    )

    plan = load_routed_detail_plan(manifest, statuses_path=statuses, retry_only=True)

    assert plan.network_ids == ("retry",)
