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
from typing import Any, Callable, Mapping
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


# ═══════════════════════════════════════════
# External Verifier (operates on raw entry dicts)
# ═══════════════════════════════════════════

GENESIS_HASH = sha256(b"genesis").hexdigest()


@dataclass(frozen=True, slots=True)
class ExternalVerifyResult:
    """Result of externally verifying a hash chain from raw entry dicts."""

    valid: bool
    entries_checked: int
    failure_reason: str = ""
    failure_sequence: int = -1  # -1 if no failure
    failure_field: str = ""     # "previous_hash" | "entry_hash" | "schema"


def _recompute_entry_hash(entry: Mapping[str, Any]) -> str:
    """Recompute the SHA-256 hash for an entry using the canonical content layout.

    Mirrors AuditTrail.record() exactly: sorted JSON of the content fields.
    """
    content = {
        "sequence": entry["sequence"],
        "action": entry["action"],
        "actor_id": entry["actor_id"],
        "tenant_id": entry["tenant_id"],
        "target": entry["target"],
        "outcome": entry["outcome"],
        "detail": entry["detail"],
        "previous_hash": entry["previous_hash"],
        "recorded_at": entry["recorded_at"],
    }
    content_bytes = json.dumps(content, sort_keys=True, default=str).encode()
    return sha256(content_bytes).hexdigest()


def verify_chain_from_entries(
    entries: list[dict[str, Any]],
) -> ExternalVerifyResult:
    """Verify a hash chain from a list of raw entry dicts.

    External verification: recomputes each entry_hash and checks the
    previous_hash linkage from the genesis anchor (sha256(b"genesis")).
    This is the canonical verifier for exported audit ledgers and the
    foundation of audit-trail integrity claims.

    Detects:
      - Schema corruption (missing required fields)
      - Entry tampering (entry_hash mismatch)
      - Chain breakage (previous_hash mismatch)
      - Genesis violation (first entry's previous_hash != GENESIS_HASH)

    Returns ExternalVerifyResult with detailed failure context.
    """
    if not entries:
        return ExternalVerifyResult(valid=True, entries_checked=0)

    required_fields = {
        "sequence", "action", "actor_id", "tenant_id", "target",
        "outcome", "detail", "entry_hash", "previous_hash", "recorded_at",
    }

    expected_prev = GENESIS_HASH
    for i, entry in enumerate(entries):
        # Schema check
        missing = required_fields - set(entry.keys())
        if missing:
            return ExternalVerifyResult(
                valid=False,
                entries_checked=i,
                failure_reason=f"missing required fields: {sorted(missing)}",
                failure_sequence=entry.get("sequence", -1),
                failure_field="schema",
            )

        # Chain linkage check
        if entry["previous_hash"] != expected_prev:
            return ExternalVerifyResult(
                valid=False,
                entries_checked=i,
                failure_reason=(
                    f"previous_hash mismatch at sequence {entry['sequence']}: "
                    f"expected {expected_prev[:16]}..., got {entry['previous_hash'][:16]}..."
                ),
                failure_sequence=entry["sequence"],
                failure_field="previous_hash",
            )

        # Entry hash check (tamper detection)
        recomputed = _recompute_entry_hash(entry)
        if recomputed != entry["entry_hash"]:
            return ExternalVerifyResult(
                valid=False,
                entries_checked=i,
                failure_reason=(
                    f"entry_hash mismatch at sequence {entry['sequence']}: "
                    f"recomputed {recomputed[:16]}..., stored {entry['entry_hash'][:16]}..."
                ),
                failure_sequence=entry["sequence"],
                failure_field="entry_hash",
            )

        expected_prev = entry["entry_hash"]

    return ExternalVerifyResult(valid=True, entries_checked=len(entries))
