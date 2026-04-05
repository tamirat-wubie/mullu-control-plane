"""Phase 228C — Rollback Snapshot Manager.

Purpose: Create and restore system state snapshots for governed rollback.
    Captures configuration, feature flags, and deployment state.
Dependencies: None (stdlib only).
Invariants:
  - Snapshots are immutable once created.
  - Rollback restores exact captured state.
  - Snapshot storage is bounded (oldest evicted).
  - All operations are auditable.
"""
from __future__ import annotations

import copy
import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(frozen=True)
class Snapshot:
    """An immutable system state snapshot."""
    snapshot_id: str
    name: str
    state: dict[str, Any]
    checksum: str
    created_at: float
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "name": self.name,
            "checksum": self.checksum,
            "created_at": self.created_at,
            "state_keys": sorted(self.state.keys()),
            "metadata": copy.deepcopy(self.metadata),
        }


@dataclass
class RollbackResult:
    """Result of a rollback operation."""
    snapshot_id: str
    success: bool
    restored_keys: list[str] = field(default_factory=list)
    error: str = ""
    timestamp: float = field(default_factory=time.time)


def _clone_snapshot(snapshot: Snapshot) -> Snapshot:
    return Snapshot(
        snapshot_id=snapshot.snapshot_id,
        name=snapshot.name,
        state=copy.deepcopy(snapshot.state),
        checksum=snapshot.checksum,
        created_at=snapshot.created_at,
        metadata=copy.deepcopy(snapshot.metadata),
    )


def _bounded_rollback_error(exc: Exception) -> str:
    return f"rollback apply failed ({type(exc).__name__})"


class SnapshotManager:
    """Creates and manages system state snapshots for rollback."""

    def __init__(self, max_snapshots: int = 50,
                 clock: Callable[[], str] | None = None):
        self._max_snapshots = max_snapshots
        self._clock = clock
        self._snapshots: dict[str, Snapshot] = {}
        self._order: list[str] = []  # insertion order
        self._rollback_history: list[RollbackResult] = []
        self._total_snapshots = 0
        self._total_rollbacks = 0

    def create_snapshot(self, snapshot_id: str, name: str,
                        state: dict[str, Any],
                        **metadata: Any) -> Snapshot:
        """Create an immutable snapshot of the given state."""
        if len(self._snapshots) >= self._max_snapshots:
            oldest_id = self._order.pop(0)
            del self._snapshots[oldest_id]

        frozen_state = copy.deepcopy(state)
        checksum = hashlib.sha256(
            json.dumps(frozen_state, sort_keys=True, default=str).encode()
        ).hexdigest()[:16]

        snapshot = Snapshot(
            snapshot_id=snapshot_id,
            name=name,
            state=frozen_state,
            checksum=checksum,
            created_at=time.time(),
            metadata=copy.deepcopy(metadata),
        )
        self._snapshots[snapshot_id] = snapshot
        self._order.append(snapshot_id)
        self._total_snapshots += 1
        return _clone_snapshot(snapshot)

    def get_snapshot(self, snapshot_id: str) -> Snapshot | None:
        snapshot = self._snapshots.get(snapshot_id)
        if snapshot is None:
            return None
        return _clone_snapshot(snapshot)

    def rollback(self, snapshot_id: str,
                 apply_fn: Callable[[dict[str, Any]], None] | None = None) -> RollbackResult:
        """Restore state from a snapshot."""
        snapshot = self._snapshots.get(snapshot_id)
        if not snapshot:
            result = RollbackResult(
                snapshot_id=snapshot_id, success=False,
                error="snapshot not found",
            )
            self._rollback_history.append(result)
            return result

        try:
            restored_state = copy.deepcopy(snapshot.state)
            if apply_fn:
                apply_fn(restored_state)
            result = RollbackResult(
                snapshot_id=snapshot_id,
                success=True,
                restored_keys=sorted(restored_state.keys()),
            )
        except Exception as exc:
            result = RollbackResult(
                snapshot_id=snapshot_id,
                success=False,
                error=_bounded_rollback_error(exc),
            )

        self._rollback_history.append(result)
        self._total_rollbacks += 1
        return result

    def list_snapshots(self, limit: int = 10) -> list[Snapshot]:
        return [_clone_snapshot(self._snapshots[sid]) for sid in reversed(self._order[-limit:])]

    def delete_snapshot(self, snapshot_id: str) -> bool:
        if snapshot_id in self._snapshots:
            del self._snapshots[snapshot_id]
            self._order.remove(snapshot_id)
            return True
        return False

    @property
    def snapshot_count(self) -> int:
        return len(self._snapshots)

    def summary(self) -> dict[str, Any]:
        return {
            "total_snapshots_created": self._total_snapshots,
            "current_snapshots": self.snapshot_count,
            "max_snapshots": self._max_snapshots,
            "total_rollbacks": self._total_rollbacks,
            "last_rollback": (
                self._rollback_history[-1].snapshot_id
                if self._rollback_history else None
            ),
        }
