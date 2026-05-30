"""Shared context, constants, events, and thread-safe logging for the CTI-RAG agent team.

Two execution modes share the same role loops:
  * threaded   (run_team.py)  — 4 threads in one process, ``threading.Event`` stop/done.
  * multi-proc (run_role.py)  — 4 OS processes (4 shells), ``FileEvent`` stop/done flags on
    disk so the independent processes coordinate with no shared memory.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from message_bus import MessageBus
from task_board import TaskBoard

ROLES: tuple[str, ...] = ("lead", "certifier", "gold_builder", "eval_gate")

POLL_INTERVAL_S = 0.5
GATE_MEAN_THRESHOLD = 0.65          # USER-set Phase C gate: Enterprise Micro-F1 mean
CERT_SUBPROCESS_TIMEOUT_S = 3600    # per certification run
MAX_WALL_S = 9000                   # safety cap for the whole team run

_print_lock = threading.Lock()
_START = time.time()


def log(role: str, message: str) -> None:
    """Thread-safe, timestamped, role-prefixed line to stdout."""
    with _print_lock:
        print(f"[{time.time() - _START:7.1f}s] {role:<12} | {message}", flush=True)


class EventLike(Protocol):
    """The subset of threading.Event the role loops use (so FileEvent can stand in)."""

    def is_set(self) -> bool: ...
    def set(self) -> None: ...
    def wait(self, timeout: float | None = None) -> bool: ...


class FileEvent:
    """A cross-process event flag backed by the existence of a file on disk."""

    def __init__(self, path: Path) -> None:
        self._p = Path(path)

    def is_set(self) -> bool:
        return self._p.exists()

    def set(self) -> None:
        self._p.touch()

    def wait(self, timeout: float | None = None) -> bool:
        deadline = None if timeout is None else time.monotonic() + timeout
        while not self.is_set():
            if deadline is not None and time.monotonic() >= deadline:
                return False
            time.sleep(0.2)
        return True


@dataclass
class TeamContext:
    repo_root: Path
    team_dir: Path
    bus: MessageBus
    board: TaskBoard
    stop: EventLike
    done: EventLike
    historical_json: list[Path]
    new_runs: int = 2
    sample_size: int = 5
    gate_threshold: float = GATE_MEAN_THRESHOLD
    point_kind: str = "historical"   # label for points loaded from historical_json
    log: Callable[[str, str], None] = field(default=log)
