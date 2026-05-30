#!/usr/bin/env python
"""Run ONE teammate as its own OS process (its own shell) — multi-process team.

Launch this four times, each in its own shell:

    ./cti-rag-venv/bin/python scripts/team/run_role.py lead
    ./cti-rag-venv/bin/python scripts/team/run_role.py certifier
    ./cti-rag-venv/bin/python scripts/team/run_role.py gold_builder
    ./cti-rag-venv/bin/python scripts/team/run_role.py eval_gate

The four processes coordinate ONLY through the shared .team/ mailbox + task board; stop
and done are file flags (.team/STOP, .team/DONE) so the processes need no shared memory.
Shared run config is read from .team/config.json (written by the launcher). Recoverable:
re-launch any role and it resumes from the persisted board + cursors.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parent.parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_REPO / "src"))

import roles as roles_mod  # noqa: E402
from common import ROLES, FileEvent, TeamContext, log  # noqa: E402
from message_bus import MessageBus  # noqa: E402
from task_board import TaskBoard  # noqa: E402

_ROLE_FN = {
    "lead": roles_mod.run_lead,
    "certifier": roles_mod.run_certifier,
    "gold_builder": roles_mod.run_gold_builder,
    "eval_gate": roles_mod.run_eval_gate,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one CTI-RAG teammate process")
    parser.add_argument("role", choices=ROLES)
    args = parser.parse_args()

    team_dir = _REPO / ".team"
    cfg = json.loads((team_dir / "config.json").read_text(encoding="utf-8"))

    ctx = TeamContext(
        repo_root=_REPO,
        team_dir=team_dir,
        bus=MessageBus(team_dir),
        board=TaskBoard(team_dir),
        stop=FileEvent(team_dir / "STOP"),
        done=FileEvent(team_dir / "DONE"),
        historical_json=[_REPO / p for p in cfg["reuse_records"]],
        new_runs=int(cfg.get("new_runs", 0)),
        sample_size=int(cfg.get("sample_size", 5)),
        gate_threshold=float(cfg.get("gate_threshold", 0.65)),
        point_kind=cfg.get("point_kind", "reused"),
    )

    log(args.role, f"process up (pid={os.getpid()}); entering agent loop over .team mailbox")
    _ROLE_FN[args.role](ctx)
    log(args.role, "agent loop exited (STOP observed)")


if __name__ == "__main__":
    main()
