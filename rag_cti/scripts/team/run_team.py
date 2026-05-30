#!/usr/bin/env python
"""Entry point: launch the 4-role CTI-RAG agent team (persistent threads + mailbox).

Each role runs as an independent thread with its own agent loop polling a drain-on-read
JSONL inbox on a shared file-backed MessageBus. Task state and the Phase C->D gate
handshake persist under .team/ and are recoverable across restarts.

Run (WSL venv, from repo root rag_cti/):
  ./cti-rag-venv/bin/python scripts/team/run_team.py
"""

from __future__ import annotations

import argparse
import shutil
import sys
import threading
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parent.parent            # scripts/team -> scripts -> repo root (rag_cti)
sys.path.insert(0, str(_HERE))         # sibling modules (message_bus, task_board, ...)
sys.path.insert(0, str(_REPO / "src"))  # rag_cti package

from common import MAX_WALL_S, ROLES, TeamContext, log  # noqa: E402
from message_bus import MessageBus  # noqa: E402
from roles import run_certifier, run_eval_gate, run_gold_builder, run_lead  # noqa: E402
from task_board import TaskBoard  # noqa: E402

# The two prior full DeepSeek runs (Enterprise Micro-F1 0.6703 / 0.6548) — see memory.
_HISTORICAL = [
    "data/eval/certification_full_deepseek_2026-05-29T22-44-30Z.json",  # 0.6703
    "data/eval/certification_full_deepseek_2026-05-29T23-13-46Z.json",  # 0.6548
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the CTI-RAG agent team")
    parser.add_argument("--new-runs", type=int, default=2, help="new certification passes to run")
    parser.add_argument("--sample-size", type=int, default=5, help="relationship_direct gold sample size")
    parser.add_argument("--fresh", action="store_true", help="wipe .team state before run")
    args = parser.parse_args()

    team_dir = _REPO / ".team"
    if args.fresh and team_dir.exists():
        shutil.rmtree(team_dir)
    team_dir.mkdir(parents=True, exist_ok=True)

    historical = [_REPO / p for p in _HISTORICAL]
    for p in historical:
        if not p.exists():
            raise SystemExit(f"missing historical cert record: {p}")

    ctx = TeamContext(
        repo_root=_REPO,
        team_dir=team_dir,
        bus=MessageBus(team_dir),
        board=TaskBoard(team_dir),
        stop=threading.Event(),
        done=threading.Event(),
        historical_json=historical,
        new_runs=args.new_runs,
        sample_size=args.sample_size,
    )

    log("orchestrator", f"starting team roles={ROLES} new_runs={args.new_runs} "
                        f"sample={args.sample_size} gate_threshold={ctx.gate_threshold}")
    targets = {
        "lead": run_lead,
        "certifier": run_certifier,
        "gold_builder": run_gold_builder,
        "eval_gate": run_eval_gate,
    }
    threads = {
        name: threading.Thread(target=fn, args=(ctx,), name=name, daemon=True)
        for name, fn in targets.items()
    }
    for t in threads.values():
        t.start()

    ctx.done.wait(timeout=MAX_WALL_S)
    ctx.stop.set()
    for t in threads.values():
        t.join(timeout=10)

    report = team_dir / "final_report.md"
    log("orchestrator", f"team finished; final report at {report}")
    if report.exists():
        print("\n" + "=" * 78 + "\n" + report.read_text(encoding="utf-8") + "=" * 78)


if __name__ == "__main__":
    main()
