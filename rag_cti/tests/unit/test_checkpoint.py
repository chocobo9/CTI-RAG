from __future__ import annotations

from pathlib import Path

from rag_cti.checkpoint import append_checkpoint, load_checkpoint


def test_load_missing_file_returns_empty(tmp_path: Path) -> None:
    assert load_checkpoint(tmp_path / "absent.jsonl") == {}


def test_append_then_load_round_trips(tmp_path: Path) -> None:
    path = tmp_path / "checkpoint.jsonl"
    append_checkpoint(path, {"pulse_id": "6543a1b2c3d4e5f6a7b8c9d0", "status": "ok", "chunks": 3})
    append_checkpoint(
        path,
        {
            "pulse_id": "789fedcba987654321001122",
            "status": "error",
            "error": "HTTP 429",
            "chunks": 0,
        },
    )

    records = load_checkpoint(path)
    assert records["6543a1b2c3d4e5f6a7b8c9d0"]["status"] == "ok"
    assert records["6543a1b2c3d4e5f6a7b8c9d0"]["chunks"] == 3
    assert records["789fedcba987654321001122"]["status"] == "error"


def test_later_record_for_same_pulse_wins(tmp_path: Path) -> None:
    path = tmp_path / "checkpoint.jsonl"
    append_checkpoint(path, {"pulse_id": "6543a1b2c3d4e5f6a7b8c9d0", "status": "error"})
    append_checkpoint(path, {"pulse_id": "6543a1b2c3d4e5f6a7b8c9d0", "status": "ok"})

    assert load_checkpoint(path)["6543a1b2c3d4e5f6a7b8c9d0"]["status"] == "ok"


def test_malformed_lines_are_skipped(tmp_path: Path) -> None:
    path = tmp_path / "checkpoint.jsonl"
    append_checkpoint(path, {"pulse_id": "6543a1b2c3d4e5f6a7b8c9d0", "status": "ok"})
    with path.open("a", encoding="utf-8") as fh:
        fh.write('{"truncated by crash...\n')
        fh.write('{"no_pulse_id_key": true}\n')
        fh.write("\n")

    records = load_checkpoint(path)
    assert list(records) == ["6543a1b2c3d4e5f6a7b8c9d0"]


def test_append_creates_parent_dirs(tmp_path: Path) -> None:
    path = tmp_path / "data" / "raw" / "otx" / ".checkpoint.jsonl"
    append_checkpoint(path, {"pulse_id": "6543a1b2c3d4e5f6a7b8c9d0", "status": "ok"})
    assert path.exists()
