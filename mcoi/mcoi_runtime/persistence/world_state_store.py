"""Phase 201B — World-State Persistence Store.

Purpose: Persist world-state snapshots, deltas, and entity history.
    Enables replay, audit, and time-travel debugging of the world-state plane.
Governance scope: world-state persistence only.
Dependencies: world_state contracts, persistence base.
Invariants:
  - Snapshots are immutable once stored.
  - Deltas link exactly two snapshots.
  - Entity history is append-only.
  - Store operations are deterministic and auditable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping
from hashlib import sha256
import json


@dataclass(frozen=True, slots=True)
class StoredSnapshot:
    """Persisted world-state snapshot record."""

    snapshot_id: str
    state_hash: str
    entity_count: int
    relation_count: int
    overall_confidence: float
    captured_at: str
    payload: Mapping[str, Any]  # Serialized snapshot data


@dataclass(frozen=True, slots=True)
class StoredDelta:
    """Persisted delta between two snapshots."""

    delta_id: str
    previous_snapshot_id: str
    current_snapshot_id: str
    changes: tuple[Mapping[str, Any], ...]
    computed_at: str


@dataclass(frozen=True, slots=True)
class EntityHistoryEntry:
    """Single entry in an entity's change history."""

    entry_id: str
    entity_id: str
    snapshot_id: str
    attributes: Mapping[str, Any]
    confidence: float
    recorded_at: str


class WorldStateStore:
    """In-memory persistence for world-state plane.

    Provides:
    - Snapshot storage and retrieval
    - Delta linking between snapshots
    - Entity history tracking
    - Time-range queries
    """

    def __init__(self) -> None:
        self._snapshots: dict[str, StoredSnapshot] = {}
        self._deltas: dict[str, StoredDelta] = {}
        self._entity_history: dict[str, list[EntityHistoryEntry]] = {}
        self._snapshot_order: list[str] = []

    def store_snapshot(
        self,
        snapshot_id: str,
        state_hash: str,
        entity_count: int,
        relation_count: int,
        overall_confidence: float,
        captured_at: str,
        payload: dict[str, Any],
    ) -> StoredSnapshot:
        """Store a world-state snapshot."""
        if snapshot_id in self._snapshots:
            raise ValueError(f"snapshot already exists: {snapshot_id}")

        stored = StoredSnapshot(
            snapshot_id=snapshot_id,
            state_hash=state_hash,
            entity_count=entity_count,
            relation_count=relation_count,
            overall_confidence=overall_confidence,
            captured_at=captured_at,
            payload=payload,
        )
        self._snapshots[snapshot_id] = stored
        self._snapshot_order.append(snapshot_id)
        return stored

    def get_snapshot(self, snapshot_id: str) -> StoredSnapshot | None:
        return self._snapshots.get(snapshot_id)

    def latest_snapshot(self) -> StoredSnapshot | None:
        if not self._snapshot_order:
            return None
        return self._snapshots[self._snapshot_order[-1]]

    def list_snapshots(self, limit: int = 50) -> list[StoredSnapshot]:
        """List snapshots in reverse chronological order."""
        ids = self._snapshot_order[-limit:]
        ids.reverse()
        return [self._snapshots[sid] for sid in ids]

    def store_delta(
        self,
        delta_id: str,
        previous_snapshot_id: str,
        current_snapshot_id: str,
        changes: list[dict[str, Any]],
        computed_at: str,
    ) -> StoredDelta:
        """Store a delta between two snapshots."""
        if delta_id in self._deltas:
            raise ValueError(f"delta already exists: {delta_id}")

        stored = StoredDelta(
            delta_id=delta_id,
            previous_snapshot_id=previous_snapshot_id,
            current_snapshot_id=current_snapshot_id,
            changes=tuple(changes),
            computed_at=computed_at,
        )
        self._deltas[delta_id] = stored
        return stored

    def get_delta(self, delta_id: str) -> StoredDelta | None:
        return self._deltas.get(delta_id)

    def deltas_for_snapshot(self, snapshot_id: str) -> list[StoredDelta]:
        """Get all deltas where this snapshot is the current."""
        return [
            d for d in self._deltas.values()
            if d.current_snapshot_id == snapshot_id
        ]

    def record_entity_state(
        self,
        entity_id: str,
        snapshot_id: str,
        attributes: dict[str, Any],
        confidence: float,
        recorded_at: str,
    ) -> EntityHistoryEntry:
        """Record an entity's state at a point in time."""
        entry_id = sha256(
            f"{entity_id}:{snapshot_id}:{recorded_at}".encode()
        ).hexdigest()[:16]

        entry = EntityHistoryEntry(
            entry_id=entry_id,
            entity_id=entity_id,
            snapshot_id=snapshot_id,
            attributes=attributes,
            confidence=confidence,
            recorded_at=recorded_at,
        )

        if entity_id not in self._entity_history:
            self._entity_history[entity_id] = []
        self._entity_history[entity_id].append(entry)
        return entry

    def entity_history(self, entity_id: str, limit: int = 50) -> list[EntityHistoryEntry]:
        """Get change history for an entity."""
        entries = self._entity_history.get(entity_id, [])
        return entries[-limit:]

    def entity_at_snapshot(self, entity_id: str, snapshot_id: str) -> EntityHistoryEntry | None:
        """Get entity state at a specific snapshot."""
        for entry in self._entity_history.get(entity_id, []):
            if entry.snapshot_id == snapshot_id:
                return entry
        return None

    @property
    def snapshot_count(self) -> int:
        return len(self._snapshots)

    @property
    def delta_count(self) -> int:
        return len(self._deltas)

    @property
    def tracked_entity_count(self) -> int:
        return len(self._entity_history)

    def summary(self) -> dict[str, Any]:
        """Store summary for health/status endpoints."""
        return {
            "snapshots": self.snapshot_count,
            "deltas": self.delta_count,
            "tracked_entities": self.tracked_entity_count,
            "latest_snapshot": self._snapshot_order[-1] if self._snapshot_order else None,
        }
