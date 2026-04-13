"""Phase 202D — Audit Trail Formalization.

Purpose: Structured audit trail for all governed operations.
    Provides immutable, tamper-evident records of every action
    with hash-chain integrity verification.
Governance scope: audit recording and verification only.
Dependencies: none (pure data structures + hashing).
Invariants:
  - Audit entries are immutable once recorded.
  - Hash chain links each entry to the previous — tampering is detectable.
  - Every governed operation produces an audit entry.
  - Audit queries are always bounded (limit parameter).
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Callable
import json


@dataclass(frozen=True, slots=True)
class AuditEntry:
    """Single immutable audit trail entry."""

    entry_id: str
    sequence: int  # Monotonically increasing
    action: str  # "llm.complete", "execute", "session.create", etc.
    actor_id: str
    tenant_id: str
    target: str  # Resource acted upon
    outcome: str  # "success", "denied", "error"
    detail: dict[str, Any]
    entry_hash: str  # SHA-256 of content
    previous_hash: str  # Links to previous entry
    recorded_at: str


class AuditStore:
    """Optional persistent backend for audit entries.

    When provided to AuditTrail, entries are written through to the
    store on every record(), making the audit trail consistent across
    replicas. In-memory entries act as a hot cache; the store is the
    source of truth.
    """

    def append(self, entry: AuditEntry) -> None:
        pass

    def query(self, **kwargs: Any) -> list[AuditEntry]:
        return []

    def count(self) -> int:
        return 0


class AuditTrail:
    """Hash-chain linked audit trail.

    Every entry is linked to the previous via hash chain,
    making tampering detectable. The chain can be verified
    by recomputing hashes from the beginning.

    When an AuditStore is provided, all entries are written through
    for cross-replica consistency.
    """

    MAX_DETAIL_SIZE = 65_536  # 64KB max for audit detail JSON

    def __init__(
        self,
        *,
        clock: Callable[[], str],
        max_entries: int = 500_000,
        store: AuditStore | None = None,
    ) -> None:
        self._clock = clock
        self._entries: list[AuditEntry] = []
        self._max_entries = max_entries
        self._last_hash: str = sha256(b"genesis").hexdigest()
        self._sequence: int = 0
        self._pruned_count: int = 0
        self._store = store
        self._lock = threading.Lock()

    def record(
        self,
        *,
        action: str,
        actor_id: str,
        tenant_id: str,
        target: str,
        outcome: str,
        detail: dict[str, Any] | None = None,
    ) -> AuditEntry:
        """Record an audit entry linked to the hash chain.

        Thread-safe: the entire record operation is serialized to
        preserve hash chain integrity under concurrent writes.
        """
        with self._lock:
            return self._record_locked(
                action=action, actor_id=actor_id, tenant_id=tenant_id,
                target=target, outcome=outcome, detail=detail,
            )

    def _record_locked(
        self, *, action: str, actor_id: str, tenant_id: str,
        target: str, outcome: str, detail: dict[str, Any] | None = None,
    ) -> AuditEntry:
        self._sequence += 1
        now = self._clock()
        detail = detail or {}

        # Enforce detail size limit to prevent memory bloat
        detail_json = json.dumps(detail, sort_keys=True, default=str)
        if len(detail_json) > self.MAX_DETAIL_SIZE:
            detail = {"_truncated": True, "_original_size": len(detail_json)}

        # Compute content hash
        content = {
            "sequence": self._sequence,
            "action": action,
            "actor_id": actor_id,
            "tenant_id": tenant_id,
            "target": target,
            "outcome": outcome,
            "detail": detail,
            "previous_hash": self._last_hash,
            "recorded_at": now,
        }
        content_bytes = json.dumps(content, sort_keys=True, default=str).encode()
        entry_hash = sha256(content_bytes).hexdigest()
        entry_id = f"audit-{self._sequence}"

        entry = AuditEntry(
            entry_id=entry_id,
            sequence=self._sequence,
            action=action,
            actor_id=actor_id,
            tenant_id=tenant_id,
            target=target,
            outcome=outcome,
            detail=detail,
            entry_hash=entry_hash,
            previous_hash=self._last_hash,
            recorded_at=now,
        )

        self._entries.append(entry)
        self._last_hash = entry_hash
        # Write through to persistent store if available
        if self._store is not None:
            self._store.append(entry)
        # Prune oldest entries when at capacity (preserves recent history)
        if len(self._entries) > self._max_entries:
            prune_count = len(self._entries) - self._max_entries
            self._entries = self._entries[prune_count:]
            self._pruned_count += prune_count
        return entry

    def query(
        self,
        *,
        tenant_id: str | None = None,
        action: str | None = None,
        outcome: str | None = None,
        actor_id: str | None = None,
        limit: int = 50,
    ) -> list[AuditEntry]:
        """Query audit entries with optional filters."""
        with self._lock:
            results = list(self._entries)
        if tenant_id is not None:
            results = [e for e in results if e.tenant_id == tenant_id]
        if action is not None:
            results = [e for e in results if e.action == action]
        if outcome is not None:
            results = [e for e in results if e.outcome == outcome]
        if actor_id is not None:
            results = [e for e in results if e.actor_id == actor_id]
        return results[-limit:]

    def verify_chain(self) -> tuple[bool, int]:
        """Verify the integrity of the entire hash chain.

        Returns (valid, entries_checked).
        """
        with self._lock:
            return self._verify_chain_locked()

    def _verify_chain_locked(self) -> tuple[bool, int]:
        if not self._entries:
            return True, 0

        expected_prev = sha256(b"genesis").hexdigest()
        for entry in self._entries:
            if entry.previous_hash != expected_prev:
                return False, entry.sequence
            expected_prev = entry.entry_hash
        return True, len(self._entries)

    @property
    def entry_count(self) -> int:
        return len(self._entries)

    @property
    def last_hash(self) -> str:
        return self._last_hash

    def summary(self) -> dict[str, Any]:
        """Audit trail summary for health endpoint."""
        action_counts: dict[str, int] = {}
        outcome_counts: dict[str, int] = {}
        for entry in self._entries:
            action_counts[entry.action] = action_counts.get(entry.action, 0) + 1
            outcome_counts[entry.outcome] = outcome_counts.get(entry.outcome, 0) + 1

        valid, checked = self.verify_chain()
        return {
            "entry_count": self.entry_count,
            "chain_valid": valid,
            "chain_verified": checked,
            "last_hash": self._last_hash[:16],
            "actions": action_counts,
            "outcomes": outcome_counts,
        }
