"""Disk-backed task board for the agent team — one JSON file per task under .team/tasks/.

States: pending -> in_progress -> done | error | blocked. The Phase C gate uses the
pending -> approved | rejected handshake. Every transition is timestamped and appended to
the task's history, so the board is fully recoverable: ``create`` never clobbers an
existing task, and roles read prior state on restart to resume rather than redo work.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any


class TaskBoard:
    def __init__(self, root: Path) -> None:
        self._dir = root / "tasks"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def _path(self, task_id: str) -> Path:
        return self._dir / f"{task_id}.json"

    def create(self, task_id: str, title: str, owner: str, state: str, phase: str) -> dict[str, Any]:
        """Create a task, or return the existing one unchanged (recovery-safe)."""
        with self._lock:
            p = self._path(task_id)
            if p.exists():
                return json.loads(p.read_text(encoding="utf-8"))
            now = time.time()
            task: dict[str, Any] = {
                "id": task_id, "title": title, "owner": owner, "state": state, "phase": phase,
                "created_ts": now, "updated_ts": now,
                "history": [{"ts": now, "state": state, "note": "created"}],
                "result": {},
            }
            self._write(p, task)
            return task

    def get(self, task_id: str) -> dict[str, Any] | None:
        with self._lock:
            p = self._path(task_id)
            return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

    def update(
        self,
        task_id: str,
        state: str | None = None,
        note: str = "",
        result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            p = self._path(task_id)
            task = json.loads(p.read_text(encoding="utf-8"))
            now = time.time()
            if state:
                task["state"] = state
            if result is not None:
                task["result"] = {**task.get("result", {}), **result}
            task["updated_ts"] = now
            task["history"].append({"ts": now, "state": task["state"], "note": note})
            self._write(p, task)
            return task

    def all(self) -> list[dict[str, Any]]:
        with self._lock:
            return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(self._dir.glob("*.json"))]

    @staticmethod
    def _write(path: Path, task: dict[str, Any]) -> None:
        path.write_text(json.dumps(task, indent=2, ensure_ascii=False), encoding="utf-8")
