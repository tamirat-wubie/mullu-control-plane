"""Purpose: append-only rejected-path receipts for blocked capability attempts.
Governance scope: rejected delta witness records only.
Dependencies: dataclasses and runtime invariant helpers.
Invariants:
  - Every record binds actor, capability, reason, and occurred_at.
  - Records are append-only within the in-memory recorder.
  - Query output is deterministic by insertion order.
"""

from __future__ import annotations

from dataclasses import dataclass

from mcoi_runtime.core.invariants import ensure_iso_timestamp, ensure_non_empty_text


@dataclass(frozen=True, slots=True)
class RejectedPathRecord:
    record_id: str
    capability: str
    actor_id: str
    reason: str
    occurred_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "record_id", ensure_non_empty_text("record_id", self.record_id))
        object.__setattr__(self, "capability", ensure_non_empty_text("capability", self.capability))
        object.__setattr__(self, "actor_id", ensure_non_empty_text("actor_id", self.actor_id))
        object.__setattr__(self, "reason", ensure_non_empty_text("reason", self.reason))
        object.__setattr__(self, "occurred_at", ensure_iso_timestamp("occurred_at", self.occurred_at))


class RejectedPathRecorder:
    """Append-only in-memory recorder for Phi_gov rejected paths."""

    def __init__(self) -> None:
        self._records: list[RejectedPathRecord] = []

    def append(self, record: RejectedPathRecord) -> RejectedPathRecord:
        self._records.append(record)
        return record

    def list_records(self) -> tuple[RejectedPathRecord, ...]:
        return tuple(self._records)
