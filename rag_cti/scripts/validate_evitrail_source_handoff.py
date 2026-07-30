"""Validate a non-OTX five-file handoff with the exact EviTRAIL consumer."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from collections import Counter
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

FILES = (
    "nodes.jsonl",
    "edges.jsonl",
    "events.jsonl",
    "source_claims.jsonl",
    "rejected_records.jsonl",
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--handoff", type=Path, required=True)
    parser.add_argument("--evitrail-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = validate(
        handoff=args.handoff.resolve(),
        evitrail_root=args.evitrail_root.resolve(),
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


def validate(*, handoff: Path, evitrail_root: Path) -> dict[str, Any]:
    missing = [name for name in FILES if not (handoff / name).is_file()]
    if missing:
        raise FileNotFoundError(f"missing handoff files: {missing}")

    files = {name: _file_stats(handoff / name) for name in FILES}
    portable = _portable_reference_scan(handoff)
    reader = _exact_reader_validation(handoff, evitrail_root)
    smoke = _pipeline_smoke(handoff, evitrail_root)
    edge_lines = files["edges.jsonl"]["lines"]
    reader_edge_observations = reader["stats"]["indicators"] + reader["stats"]["relations"]
    errors = []
    if portable["absolute_reference_count"]:
        errors.append("absolute_paths_present")
    if edge_lines != reader_edge_observations:
        errors.append(f"reader_edge_observations:{reader_edge_observations}!={edge_lines}")
    if smoke["status"] != "passed":
        errors.append("pipeline_smoke_failed")
    return {
        "contract": "evitrail_non_otx_source_handoff_validation_v1",
        "status": "passed" if not errors else "failed",
        "consumer": {
            "root": str(evitrail_root),
            "commit": _git_revision(evitrail_root),
        },
        "handoff_ref": handoff.name,
        "handoff": str(handoff),
        "files": files,
        "portable_reference_scan": portable,
        "exact_current_read_handoff": reader,
        "exact_current_pipeline_smoke": smoke,
        "checks": {
            "exact_five_files": sorted(path.name for path in handoff.iterdir()) == sorted(FILES),
            "portable_raw_references": not portable["absolute_reference_count"],
            "reader_preserves_every_edge_observation": (edge_lines == reader_edge_observations),
            "four_source_pipeline_smoke": smoke["status"] == "passed",
        },
        "known_boundaries": [
            (
                "ORKL, APTnotes, and CISA narrative actor claims remain "
                "report_context/provenance_only under current reader policy."
            ),
        ],
        "errors": errors,
    }


def _file_stats(path: Path) -> dict[str, Any]:
    digest = hashlib.sha256()
    lines = 0
    with path.open("rb") as handle:
        for row in handle:
            lines += 1
            digest.update(row)
    return {
        "bytes": path.stat().st_size,
        "lines": lines,
        "sha256": digest.hexdigest(),
    }


def _portable_reference_scan(handoff: Path) -> dict[str, Any]:
    absolute: list[dict[str, Any]] = []
    absolute_count = 0
    references = 0
    for name in FILES:
        for line_number, row in enumerate(_iter_jsonl(handoff / name), start=1):
            for key, value in _reference_values(row):
                references += 1
                if _is_absolute_reference(value):
                    absolute_count += 1
                    if len(absolute) < 20:
                        absolute.append(
                            {
                                "file": name,
                                "line": line_number,
                                "field": key,
                                "value": value,
                            }
                        )
    return {
        "references_checked": references,
        "absolute_reference_count": absolute_count,
        "absolute_reference_samples": absolute,
    }


def _reference_values(value: Any, path: str = "") -> Iterable[tuple[str, str]]:
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            if isinstance(child, str) and (
                key in {"raw_ref", "source_ref", "document_ref"} or str(key).endswith("_ref")
            ):
                yield child_path, child
            yield from _reference_values(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _reference_values(child, f"{path}[{index}]")


def _is_absolute_reference(value: str) -> bool:
    normalized = value.replace("\\", "/")
    return (
        len(normalized) >= 3 and normalized[0].isalpha() and normalized[1:3] == ":/"
    ) or normalized.startswith(("//", "/"))


def _exact_reader_validation(handoff: Path, evitrail_root: Path) -> dict[str, Any]:
    sys.path.insert(0, str(evitrail_root))
    from evitrail.data.readers import read_handoff

    try:
        import psutil
    except ImportError:
        psutil = None

    process = psutil.Process(os.getpid()) if psutil else None
    baseline = process.memory_info().rss if process else None
    peak = baseline
    stopped = threading.Event()

    def monitor() -> None:
        nonlocal peak
        assert process is not None
        while not stopped.wait(0.02):
            rss = process.memory_info().rss
            peak = max(peak or rss, rss)

    thread = threading.Thread(target=monitor, daemon=True) if process is not None else None
    if thread:
        thread.start()
    started = time.perf_counter()
    bundle = read_handoff(str(handoff))
    elapsed = time.perf_counter() - started
    stopped.set()
    if thread:
        thread.join()
    if process:
        peak = max(peak or 0, process.memory_info().rss)
    stats = dict(bundle.reader_stats["handoff"])
    by_source = Counter(event.event.source for event in bundle.events)
    return {
        "status": "passed",
        "stats": stats,
        "events_by_source": dict(sorted(by_source.items())),
        "elapsed_seconds": round(elapsed, 3),
        "baseline_rss_bytes": baseline,
        "peak_rss_bytes": peak,
        "peak_rss_gib": round(peak / (1024**3), 3) if peak else None,
    }


def _pipeline_smoke(handoff: Path, evitrail_root: Path) -> dict[str, Any]:
    events_by_source: dict[str, dict[str, Any]] = {}
    for row in _iter_jsonl(handoff / "events.jsonl"):
        events_by_source.setdefault(str(row.get("source") or ""), row)
        if len(events_by_source) == 4:
            break
    event_ids = {str(row["event_id"]) for row in events_by_source.values()}
    edges: list[dict[str, Any]] = []
    node_ids = set(event_ids)
    per_event: Counter[str] = Counter()
    for row in _iter_jsonl(handoff / "edges.jsonl"):
        source_id = str(row.get("source_id") or "")
        if (
            source_id in event_ids
            and str(row.get("relation") or "").startswith("event_contains_")
            and per_event[source_id] < 5
        ):
            edges.append(row)
            node_ids.add(str(row["target_id"]))
            per_event[source_id] += 1
    nodes = [
        row
        for row in _iter_jsonl(handoff / "nodes.jsonl")
        if str(row.get("node_id") or "") in node_ids
    ]
    claims = [
        row
        for row in _iter_jsonl(handoff / "source_claims.jsonl")
        if str(row.get("event_id") or "") in event_ids
    ]
    with tempfile.TemporaryDirectory(prefix="evitrail-source-smoke-") as temp:
        root = Path(temp)
        smoke_handoff = root / "handoff"
        smoke_handoff.mkdir()
        _write_jsonl(smoke_handoff / "events.jsonl", events_by_source.values())
        _write_jsonl(smoke_handoff / "edges.jsonl", edges)
        _write_jsonl(smoke_handoff / "nodes.jsonl", nodes)
        _write_jsonl(smoke_handoff / "source_claims.jsonl", claims)
        _write_jsonl(smoke_handoff / "rejected_records.jsonl", [])
        output = root / "output"
        command = [
            sys.executable,
            "-m",
            "evitrail.data.pipeline",
            "--handoff",
            str(smoke_handoff),
            "--raw-root",
            "__disabled__",
            "--out",
            str(output),
            "--enrichment",
            "none",
            "--vocabulary-mode",
            "frozen",
        ]
        env = dict(os.environ)
        env["PYTHONPATH"] = str(evitrail_root)
        completed = subprocess.run(
            command,
            cwd=evitrail_root,
            env=env,
            text=True,
            capture_output=True,
            timeout=180,
            check=False,
        )
        summary_path = output / "pipeline_summary.json"
        summary = (
            json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
        )
        return {
            "status": "passed" if completed.returncode == 0 else "failed",
            "exit_code": completed.returncode,
            "sources": sorted(events_by_source),
            "events": len(events_by_source),
            "edges": len(edges),
            "claims": len(claims),
            "base": summary.get("base"),
            "stderr_tail": completed.stderr[-2000:] or None,
        }


def _iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(
                json.dumps(
                    row,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                )
                + "\n"
            )


def _git_revision(root: Path) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        check=False,
    )
    return completed.stdout.strip()


if __name__ == "__main__":
    main()
