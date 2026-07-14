from __future__ import annotations

import json

from rag_cti.intermediate.contract import CONTRACT_ID_LENGTH, CONTROLLED_VOCABULARIES, contract_id
from rag_cti.intermediate.jsonl import write_jsonl


def test_contract_id_is_deterministic_prefixed_and_24_hex() -> None:
    first = contract_id("em", ("record-1", "adversary", "actor", "Cleaver"))
    second = contract_id("em", ("record-1", "adversary", "actor", "Cleaver"))

    assert first == second
    assert first.startswith("em_")
    digest = first.removeprefix("em_")
    assert len(digest) == CONTRACT_ID_LENGTH
    assert int(digest, 16) >= 0


def test_contract_id_keeps_tuple_slots_separate() -> None:
    assert contract_id("em", ("ab", "c")) != contract_id("em", ("a", "bc"))


def test_contract_id_distinguishes_none_from_empty_string() -> None:
    assert contract_id("em", (None,)) != contract_id("em", ("",))


def test_contract_id_distinguishes_string_from_number() -> None:
    assert contract_id("em", ("1",)) != contract_id("em", (1,))


def test_contract_id_keeps_object_slots_canonical_and_ordered() -> None:
    first = contract_id("em", ({"b": 2, "a": 1}, "tail"))
    second = contract_id("em", ({"a": 1, "b": 2}, "tail"))

    assert first == second
    assert first != contract_id("em", ("tail", {"a": 1, "b": 2}))


def test_controlled_vocabulary_contains_issue_1_contract_values() -> None:
    assert "otx" in CONTROLLED_VOCABULARIES["connector_source"]
    assert "weakly_labeled_narrative" in CONTROLLED_VOCABULARIES["source_class"]
    assert "weak_direct_attribution" in CONTROLLED_VOCABULARIES["signal_type"]
    assert "uses-nameserver" in CONTROLLED_VOCABULARIES["predicate.mapped_value"]


def test_write_jsonl_creates_parent_and_writes_one_canonical_json_object_per_line(tmp_path) -> None:
    out = tmp_path / "nested" / "rows.jsonl"
    count = write_jsonl(out, [{"b": 2, "a": 1}, {"z": None}])

    assert count == 2
    lines = out.read_text(encoding="utf-8").splitlines()
    assert lines == ['{"a":1,"b":2}', '{"z":null}']
    assert [json.loads(line) for line in lines] == [{"a": 1, "b": 2}, {"z": None}]


def test_write_jsonl_escapes_unicode_line_separators(tmp_path) -> None:
    out = tmp_path / "rows.jsonl"
    count = write_jsonl(out, [{"value": "http://\u2028139.59.79.86/a\u2029b"}])

    text = out.read_text(encoding="utf-8")
    lines = text.splitlines()
    assert count == 1
    assert len(lines) == 1
    assert "\\u2028" in lines[0]
    assert "\\u2029" in lines[0]
    assert json.loads(lines[0]) == [{"value": "http://\u2028139.59.79.86/a\u2029b"}][0]
