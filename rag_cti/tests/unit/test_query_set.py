"""Unit tests for evaluation/query_set.py."""

from __future__ import annotations

import json

from rag_cti.evaluation.query_set import (
    QueryCategory,
    QuerySetRecord,
    load_query_set,
    save_query_set,
)


def _make_record(
    query_id: str = "q1",
    query: str = "How does APT29 use T1566?",
    category: str = "precise",
    expected_chunk_ids: list[str] | None = None,
    gold_attack_ids: list[str] | None = None,
    gold_sources: list[str] | None = None,
    reference_answer: str | None = "Spearphishing is used for initial access.",
    notes: str = "",
) -> QuerySetRecord:
    return QuerySetRecord(
        query_id=query_id,
        query=query,
        category=QueryCategory(category),
        expected_chunk_ids=expected_chunk_ids or ["chunk-abc"],
        gold_attack_ids=gold_attack_ids or ["T1566"],
        gold_sources=gold_sources or ["mitre"],
        reference_answer=reference_answer,
        notes=notes,
    )


def _jsonl_line(
    query_id: str = "q1",
    query: str = "How does APT29 use T1566?",
    category: str = "precise",
    expected_chunk_ids: list[str] | None = None,
    gold_attack_ids: list[str] | None = None,
    gold_sources: list[str] | None = None,
    reference_answer: str | None = "Spearphishing is used for initial access.",
    notes: str = "",
) -> str:
    return json.dumps(
        {
            "query_id": query_id,
            "query": query,
            "category": category,
            "expected_chunk_ids": expected_chunk_ids or ["chunk-abc"],
            "gold_attack_ids": gold_attack_ids or ["T1566"],
            "gold_sources": gold_sources or ["mitre"],
            "reference_answer": reference_answer,
            "notes": notes,
        }
    )


# ---------------------------------------------------------------------------
# load_query_set
# ---------------------------------------------------------------------------


def test_load_query_set_returns_list_of_records(tmp_path) -> None:
    f = tmp_path / "qs.jsonl"
    f.write_text(_jsonl_line() + "\n", encoding="utf-8")
    records = load_query_set(f)
    assert len(records) == 1
    assert isinstance(records[0], QuerySetRecord)


def test_load_query_set_query_id_parsed(tmp_path) -> None:
    f = tmp_path / "qs.jsonl"
    f.write_text(_jsonl_line(query_id="q99") + "\n", encoding="utf-8")
    assert load_query_set(f)[0].query_id == "q99"


def test_load_query_set_query_text_parsed(tmp_path) -> None:
    f = tmp_path / "qs.jsonl"
    f.write_text(_jsonl_line(query="ransomware lateral movement") + "\n", encoding="utf-8")
    assert load_query_set(f)[0].query == "ransomware lateral movement"


def test_load_query_set_category_parsed(tmp_path) -> None:
    f = tmp_path / "qs.jsonl"
    f.write_text(_jsonl_line(category="fuzzy") + "\n", encoding="utf-8")
    assert load_query_set(f)[0].category == QueryCategory.FUZZY


def test_load_query_set_expected_chunk_ids_parsed(tmp_path) -> None:
    f = tmp_path / "qs.jsonl"
    f.write_text(_jsonl_line(expected_chunk_ids=["id-a", "id-b"]) + "\n", encoding="utf-8")
    assert load_query_set(f)[0].expected_chunk_ids == ["id-a", "id-b"]


def test_load_query_set_gold_attack_ids_parsed(tmp_path) -> None:
    f = tmp_path / "qs.jsonl"
    f.write_text(_jsonl_line(gold_attack_ids=["T1059", "T1003"]) + "\n", encoding="utf-8")
    assert load_query_set(f)[0].gold_attack_ids == ["T1059", "T1003"]


def test_load_query_set_gold_sources_parsed(tmp_path) -> None:
    f = tmp_path / "qs.jsonl"
    f.write_text(_jsonl_line(gold_sources=["mitre", "otx"]) + "\n", encoding="utf-8")
    assert load_query_set(f)[0].gold_sources == ["mitre", "otx"]


def test_load_query_set_reference_answer_none(tmp_path) -> None:
    f = tmp_path / "qs.jsonl"
    f.write_text(_jsonl_line(reference_answer=None) + "\n", encoding="utf-8")
    assert load_query_set(f)[0].reference_answer is None


def test_load_query_set_skips_blank_lines(tmp_path) -> None:
    f = tmp_path / "qs.jsonl"
    f.write_text(_jsonl_line() + "\n\n" + _jsonl_line(query_id="q2") + "\n", encoding="utf-8")
    assert len(load_query_set(f)) == 2


def test_load_query_set_multiple_records(tmp_path) -> None:
    lines = "\n".join(_jsonl_line(query_id=f"q{i}") for i in range(5))
    f = tmp_path / "qs.jsonl"
    f.write_text(lines + "\n", encoding="utf-8")
    records = load_query_set(f)
    assert len(records) == 5
    assert [r.query_id for r in records] == [f"q{i}" for i in range(5)]


def test_load_query_set_missing_optional_fields_default_empty(tmp_path) -> None:
    obj = {"query_id": "q1", "query": "test", "category": "semantic"}
    f = tmp_path / "qs.jsonl"
    f.write_text(json.dumps(obj) + "\n", encoding="utf-8")
    r = load_query_set(f)[0]
    assert r.expected_chunk_ids == []
    assert r.gold_attack_ids == []
    assert r.gold_sources == []
    assert r.notes == ""


# ---------------------------------------------------------------------------
# save_query_set
# ---------------------------------------------------------------------------


def test_save_query_set_creates_file(tmp_path) -> None:
    out = tmp_path / "out.jsonl"
    save_query_set([_make_record()], out)
    assert out.exists()


def test_save_query_set_round_trips(tmp_path) -> None:
    out = tmp_path / "out.jsonl"
    original = [_make_record(query_id="q1"), _make_record(query_id="q2")]
    save_query_set(original, out)
    loaded = load_query_set(out)
    assert len(loaded) == 2
    assert loaded[0].query_id == "q1"
    assert loaded[1].query_id == "q2"


def test_save_query_set_category_written_as_string(tmp_path) -> None:
    out = tmp_path / "out.jsonl"
    save_query_set([_make_record(category="fuzzy")], out)
    line = out.read_text(encoding="utf-8").strip()
    obj = json.loads(line)
    assert obj["category"] == "fuzzy"


def test_save_query_set_creates_parent_dirs(tmp_path) -> None:
    out = tmp_path / "nested" / "dir" / "out.jsonl"
    save_query_set([_make_record()], out)
    assert out.exists()


def test_save_query_set_empty_list_produces_empty_file(tmp_path) -> None:
    out = tmp_path / "empty.jsonl"
    save_query_set([], out)
    assert out.read_text(encoding="utf-8") == ""
