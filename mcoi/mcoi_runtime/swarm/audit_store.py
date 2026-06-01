"""Append-only JSONL audit store for governed swarm records.

Purpose: persist swarm audit records with deterministic JSON serialization and
duplicate-run protection.
Governance scope: UWMA witness anchoring and PRS readback verification.
Dependencies: json, pathlib, and swarm audit records.
Invariants: records are append-only by run id and cannot silently overwrite a
prior proof.
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass
from pathlib import Path

from .contracts import SwarmInvariantViolation
from .record import SwarmAuditRecord

# Per-file append locks. The duplicate-run-id check and the append must form one
# atomic critical section: without serialization, two concurrent appends with
# the same run_id both pass the check and both persist, breaking the
# append-only-by-run-id invariant. Locks are keyed by absolute path so every
# store targeting the same file shares one lock, regardless of how many
# SwarmAuditStore instances exist. This serializes appends within a process;
# multiple processes writing one file would additionally need an OS file lock.
_APPEND_LOCKS_GUARD = threading.Lock()
_APPEND_LOCKS: dict[str, threading.Lock] = {}


def _append_lock_for(path: Path) -> threading.Lock:
    key = os.path.abspath(str(path))
    with _APPEND_LOCKS_GUARD:
        lock = _APPEND_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _APPEND_LOCKS[key] = lock
        return lock


@dataclass
class SwarmAuditStore:
    """Append-only local JSONL store for swarm audit records."""

    path: Path

    def __post_init__(self) -> None:
        self.path = Path(self.path)

    def append(self, record: SwarmAuditRecord) -> None:
        """Append one record, rejecting duplicate run ids.

        The duplicate check and the write run under a per-file lock so that
        concurrent appends with the same run_id cannot both persist.
        """

        with _append_lock_for(self.path):
            if self.get(record.run_id) is not None:
                raise SwarmInvariantViolation(f"duplicate swarm run_id: {record.run_id}")
            self.path.parent.mkdir(parents=True, exist_ok=True)
            line = json.dumps(record.to_dict(), sort_keys=True, separators=(",", ":"))
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")

    def get(self, run_id: str) -> SwarmAuditRecord | None:
        """Return one record by run id, or None when absent."""

        for record in self.list_records():
            if record.run_id == run_id:
                return record
        return None

    def list_records(self) -> tuple[SwarmAuditRecord, ...]:
        """Return all persisted records in append order."""

        if not self.path.exists():
            return ()
        records: list[SwarmAuditRecord] = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    records.append(SwarmAuditRecord.from_dict(json.loads(stripped)))
                except (KeyError, TypeError, json.JSONDecodeError, SwarmInvariantViolation) as exc:
                    raise SwarmInvariantViolation(f"invalid audit record at line {line_number}") from exc
        return tuple(records)

    @property
    def count(self) -> int:
        """Return persisted record count."""

        return len(self.list_records())
