"""Unit tests for the Composer pure logic (knowledge.composer) with a fake ComposeFn."""

from __future__ import annotations

import json

from rag_cti.knowledge.agentic_state import BranchReport
from rag_cti.knowledge.composer import AGENTIC_COMPOSE_SYSTEM, build_compose_user, compose


def _report(entity: str, techniques: list[tuple[str, str, str]], cited: list[str]) -> BranchReport:
    return BranchReport(
        focus_entity=entity,
        sub_question=f"What techniques does {entity} use?",
        sub_answer="",  # gather-only worker
        techniques=tuple(techniques),
        cited_ids=tuple(cited),
    )


def test_build_compose_user_carries_question_and_structured_reports() -> None:
    reports = [
        _report("APT29", [("T1059", "Command", "fact_a")], ["fact_a"]),
        _report(
            "Turla", [("T1059", "Command", "fact_b"), ("T1566", "Phishing", "fact_c")], ["fact_b"]
        ),
    ]
    payload = json.loads(build_compose_user("Compare APT29 and Turla", reports))
    assert payload["question"] == "Compare APT29 and Turla"
    assert len(payload["branch_reports"]) == 2
    first = payload["branch_reports"][0]
    assert first["focus_entity"] == "APT29"
    # structured (attack_id, name, fact_id) triple reaches the Composer
    assert first["techniques"] == [["T1059", "Command", "fact_a"]]
    assert first["cited_ids"] == ["fact_a"]


def test_compose_invokes_composer_with_system_and_rendered_user() -> None:
    captured: dict[str, str] = {}

    def fake_composer(system: str, user: str) -> str:
        captured["system"] = system
        captured["user"] = user
        return "APT29 and Turla share [fact_a]."

    reports = [_report("APT29", [("T1059", "Command", "fact_a")], ["fact_a"])]
    out = compose(fake_composer, "Compare APT29 and Turla", reports)

    assert out == "APT29 and Turla share [fact_a]."
    assert captured["system"] == AGENTIC_COMPOSE_SYSTEM
    assert "Compare APT29 and Turla" in captured["user"]
    assert "T1059" in captured["user"]  # structured technique id is in the prompt


def test_compose_handles_empty_reports() -> None:
    out = compose(lambda s, u: "no branches", "q", [])
    assert out == "no branches"
