"""File-backed MessageBus for the CTI-RAG agent team — safe for threads AND processes.

A single shared bus that every teammate uses to communicate. Two durability guarantees:

  * Every message is appended to an append-only audit log (.team/mailbox.jsonl) — the
    full, never-drained history, for recovery and post-hoc audit.
  * Every message is also appended to the recipient's inbox queue
    (.team/inbox/<role>.jsonl). ``drain(role)`` returns the recipient's unread messages
    and advances a persisted per-role cursor (.team/inbox/<role>.cursor) — "drain on
    read": each message is delivered exactly once, and a restart resumes from the cursor.

Concurrency: an in-process re-entrant lock guards threaded use; an OS file lock (fcntl)
on .team/.lock guards multi-process use, so 4 independent processes can share one bus.
The message sequence number is a counter file (.team/seq) bumped under the lock, so seq
is globally unique across processes.
"""

from __future__ import annotations

import json
import threading
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

try:
    import fcntl  # POSIX (WSL) — present in this project's runtime
except ImportError:  # pragma: no cover - non-POSIX fallback (in-process lock only)
    fcntl = None  # type: ignore[assignment]


@dataclass(frozen=True)
class Message:
    """One immutable message on the bus."""

    seq: int
    ts: float
    frm: str
    to: str
    type: str
    body: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_json(cls, line: str) -> Message:
        d = json.loads(line)
        return cls(
            seq=d["seq"], ts=d["ts"], frm=d["frm"], to=d["to"],
            type=d["type"], body=d.get("body", {}),
        )

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


class MessageBus:
    """Thread- and process-safe, file-backed, drain-on-read message bus."""

    def __init__(self, root: Path) -> None:
        self._inbox_dir = root / "inbox"
        self._mailbox = root / "mailbox.jsonl"
        self._seqfile = root / "seq"
        self._lockfile = root / ".lock"
        self._inbox_dir.mkdir(parents=True, exist_ok=True)
        self._tlock = threading.RLock()
        with self._critical():
            if not self._seqfile.exists():
                self._seqfile.write_text(str(self._recover_seq()), encoding="utf-8")

    @contextmanager
    def _critical(self):
        """Hold both the in-process lock and the cross-process file lock."""
        with self._tlock:
            if fcntl is None:
                yield
                return
            with self._lockfile.open("a+") as fh:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(fh.fileno(), fcntl.LOCK_UN)

    def _recover_seq(self) -> int:
        if not self._mailbox.exists():
            return 0
        last = 0
        for line in self._mailbox.read_text(encoding="utf-8").splitlines():
            if line.strip():
                last = max(last, int(json.loads(line)["seq"]))
        return last

    def send(self, frm: str, to: str, type: str, body: dict[str, Any] | None = None) -> Message:
        """Append a message to the audit log and the recipient's inbox (atomically)."""
        with self._critical():
            seq = int(self._seqfile.read_text(encoding="utf-8").strip() or "0") + 1
            self._seqfile.write_text(str(seq), encoding="utf-8")
            msg = Message(seq=seq, ts=time.time(), frm=frm, to=to, type=type, body=body or {})
            line = msg.to_json() + "\n"
            with self._mailbox.open("a", encoding="utf-8") as fh:
                fh.write(line)
            with (self._inbox_dir / f"{to}.jsonl").open("a", encoding="utf-8") as fh:
                fh.write(line)
            return msg

    def drain(self, role: str) -> list[Message]:
        """Return ``role``'s unread messages and advance its cursor (drain-on-read)."""
        with self._critical():
            inbox = self._inbox_dir / f"{role}.jsonl"
            if not inbox.exists():
                return []
            lines = [ln for ln in inbox.read_text(encoding="utf-8").splitlines() if ln.strip()]
            cursor = self._read_cursor(role)
            unread = lines[cursor:]
            self._write_cursor(role, len(lines))
            return [Message.from_json(ln) for ln in unread]

    def _cursor_path(self, role: str) -> Path:
        return self._inbox_dir / f"{role}.cursor"

    def _read_cursor(self, role: str) -> int:
        p = self._cursor_path(role)
        if not p.exists():
            return 0
        try:
            return int(p.read_text(encoding="utf-8").strip() or "0")
        except ValueError:
            return 0

    def _write_cursor(self, role: str, value: int) -> None:
        self._cursor_path(role).write_text(str(value), encoding="utf-8")
