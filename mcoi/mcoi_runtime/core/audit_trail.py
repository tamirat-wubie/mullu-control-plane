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


@dataclass(frozen=True, slots=True)
class AuditCheckpoint:
    """Anchor for chain verification across prune boundaries.

    v4.28.0+. Pre-v4.28 the verifier always started from
    ``sha256(b"genesis")``, which made ``verify_chain()`` permanently
    return False after the first prune (the in-memory window's first
    entry's ``previous_hash`` no longer matched genesis — it pointed
    to the now-pruned predecessor's entry_hash).

    This dataclass records the predecessor's entry_hash at the
    pruning boundary. The verifier uses it as ``expected_previous_hash``
    for the first in-memory entry, so post-prune chains still verify.

    ``at_sequence`` is the sequence of the predecessor entry (i.e., the
    last entry pruned). ``chain_hash`` is that entry's ``entry_hash``.
    The first surviving entry's ``previous_hash`` must equal
    ``chain_hash`` for the chain to verify.
    """

    at_sequence: int
    chain_hash: str
    recorded_at: str


class AuditStore:
    """Optional persistent backend for audit entries.

    When provided to AuditTrail, entries are written through to the
    store on every record(), making the audit trail consistent across
    replicas. In-memory entries act as a hot cache; the store is the
    source of truth.

    v4.28.0+: ``store_checkpoint`` / ``latest_checkpoint`` extend the
    store interface with prune-safe verification anchors. Stores that
    don't implement these (the base class) are degraded gracefully —
    the in-process anchor still works for single-process integrity.
    """

    def append(self, entry: AuditEntry) -> None:
        pass

    def query(self, **kwargs: Any) -> list[AuditEntry]:
        return []

    def count(self) -> int:
        return 0

    def store_checkpoint(self, checkpoint: "AuditCheckpoint") -> None:
        """Persist a checkpoint anchor (v4.28.0+). Optional override."""

    def latest_checkpoint(self) -> "AuditCheckpoint | None":
        """Return the most recent persisted checkpoint, or None.

        v4.28.0+. Used at AuditTrail bootstrap to restore the anchor
        across process restarts when the store is durable.
        """
        return None


class AuditTrail:
    """Hash-chain linked audit trail.

    Every entry is linked to the previous via hash chain,
    making tampering detectable. The chain can be verified
    by recomputing hashes from the beginning.

    When an AuditStore is provided, all entries are written through
    for cross-replica consistency.
    """

    MAX_DETAIL_SIZE = 65_536  # 64KB max for audit detail JSON

    # Sentinel: initial anchor before any entry exists.
    _GENESIS_HASH: str = sha256(b"genesis").hexdigest()

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
        self._last_hash: str = self._GENESIS_HASH
        self._sequence: int = 0
        self._pruned_count: int = 0
        self._store = store
        self._lock = threading.Lock()
        # v4.28.0 (audit F3): anchor for chain verification across
        # prune boundaries. ``_anchor_hash`` is what the first
        # in-memory entry's ``previous_hash`` must equal for the
        # chain to verify. ``_anchor_sequence`` is the sequence of
        # the entry whose hash is in ``_anchor_hash`` (or 0 for
        # genesis). Updated on every prune; restored from store
        # on bootstrap if the store has a checkpoint.
        self._anchor_hash: str = self._GENESIS_HASH
        self._anchor_sequence: int = 0
        if self._store is not None:
            checkpoint = self._store.latest_checkpoint()
            if checkpoint is not None:
                self._anchor_hash = checkpoint.chain_hash
                self._anchor_sequence = checkpoint.at_sequence

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

        # Compute content hash via the canonical v1 helper. The writer
        # and the external verifier both call _canonical_hash_v1, so
        # they cannot drift apart — the spec layout is enforced by
        # construction, not by convention. See LEDGER_SPEC.md.
        source = {
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
        entry_hash = _canonical_hash_v1(source)
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
        # Prune oldest entries when at capacity (preserves recent history).
        # v4.28.0 (audit F3): before pruning, capture the boundary entry's
        # hash as the verification anchor. Without this, ``verify_chain()``
        # would permanently return False once the first entry's
        # predecessor is pruned out of the in-memory window.
        if len(self._entries) > self._max_entries:
            prune_count = len(self._entries) - self._max_entries
            # The LAST entry being pruned becomes the new anchor —
            # the entry whose hash equals the next surviving entry's
            # ``previous_hash``.
            boundary = self._entries[prune_count - 1]
            self._anchor_hash = boundary.entry_hash
            self._anchor_sequence = boundary.sequence
            self._entries = self._entries[prune_count:]
            self._pruned_count += prune_count
            # Persist the checkpoint so post-restart verification has
            # the same anchor. No-op when store is None or doesn't
            # override store_checkpoint.
            if self._store is not None:
                self._store.store_checkpoint(
                    AuditCheckpoint(
                        at_sequence=self._anchor_sequence,
                        chain_hash=self._anchor_hash,
                        recorded_at=now,
                    )
                )
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

        # v4.28.0 (audit F3): start from the verification anchor, not
        # genesis. ``_anchor_hash`` equals genesis until the first
        # prune; after that, it equals the ``entry_hash`` of the last
        # pruned entry. The first surviving entry's ``previous_hash``
        # must match. Pre-v4.28 this always started from genesis,
        # which made ``verify_chain()`` permanently return False
        # after the first prune.
        expected_prev = self._anchor_hash
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

# Maximum ledger schema version this verifier knows how to interpret.
# Bump only when LEDGER_SPEC.md defines a new canonical content layout.
LEDGER_SCHEMA_VERSION_MAX = 1

# Single source of truth for v1 entry-hash content layout.
# Both the writer (AuditTrail._record_locked) and the verifier
# (verify_chain_from_entries / _recompute_entry_hash) MUST derive the
# canonical content from this exact field set in this exact order.
# Drift between writer and spec is structurally impossible because both
# code paths use _canonical_content_v1 below.
#
# Changing this list is a breaking change to LEDGER_SPEC.md and requires
# bumping LEDGER_SCHEMA_VERSION_MAX. See docs/LEDGER_SPEC.md
# §"Canonical entry-hash content layout (v1)".
LEDGER_V1_CONTENT_FIELDS: tuple[str, ...] = (
    "sequence",
    "action",
    "actor_id",
    "tenant_id",
    "target",
    "outcome",
    "detail",
    "previous_hash",
    "recorded_at",
)


def _canonical_content_v1(source: Mapping[str, Any]) -> dict[str, Any]:
    """Extract the v1 canonical content from a source mapping.

    Used by both the writer (when computing entry_hash for a new entry)
    and the verifier (when recomputing entry_hash for an existing entry).
    Single source of truth for the v1 layout — drift is impossible.
    """
    return {field: source[field] for field in LEDGER_V1_CONTENT_FIELDS}


def _canonical_hash_v1(source: Mapping[str, Any]) -> str:
    """Compute SHA-256 of the canonical v1 content of `source`.

    `source` must contain all keys in LEDGER_V1_CONTENT_FIELDS.
    """
    content = _canonical_content_v1(source)
    content_bytes = json.dumps(content, sort_keys=True, default=str).encode()
    return sha256(content_bytes).hexdigest()


@dataclass(frozen=True, slots=True)
class ExternalVerifyResult:
    """Result of externally verifying a hash chain from raw entry dicts.

    failure_field values (from LEDGER_SPEC.md §"Verification semantics"):
      - "schema"         — missing field or unknown schema_version (writer bug)
      - "sequence"       — non-monotonic sequence numbers (deletion attack)
      - "previous_hash"  — chain linkage broken (tamper or fabrication)
      - "entry_hash"     — entry content modified after writing (tamper)

    Operationally distinguish "schema" (writer bug, exit 3) from the
    other three (security event, exit 1).
    """

    valid: bool
    entries_checked: int
    failure_reason: str = ""
    failure_sequence: int = -1  # -1 if no failure
    failure_field: str = ""     # "schema" | "sequence" | "previous_hash" | "entry_hash"


def _recompute_entry_hash(entry: Mapping[str, Any]) -> str:
    """Recompute the SHA-256 hash for an entry using the canonical v1 layout.

    Thin wrapper over _canonical_hash_v1 — kept for backward compatibility
    of the test surface. Both this and AuditTrail._record_locked delegate
    to _canonical_hash_v1, so writer/verifier drift is impossible.
    """
    return _canonical_hash_v1(entry)


def verify_chain_from_entries(
    entries: list[dict[str, Any]],
    *,
    anchor_hash: str | None = None,
    anchor_sequence: int | None = None,
) -> ExternalVerifyResult:
    """Verify a hash chain from a list of raw entry dicts.

    External verification of an exported audit ledger. See
    docs/LEDGER_SPEC.md for the full specification.

    Args:
        entries: List of entry dicts (e.g., loaded from JSONL).
        anchor_hash: Required only for slice verification. If supplied,
            entries[0].previous_hash must equal this value (instead of
            GENESIS_HASH). Used to anchor a slice to a trusted external
            checkpoint. None = full-chain verification from genesis.
        anchor_sequence: First expected sequence number. Required when
            anchor_hash is set (slices don't start at sequence 1).
            None = full-chain verification (start at sequence 1).

    Returns:
        ExternalVerifyResult with detailed failure context.

    The verifier checks (in order, per entry):
      1. Schema completeness — every required field is present
      2. Schema version — schema_version (if present) <= LEDGER_SCHEMA_VERSION_MAX
      3. Sequence monotonicity — entries[i].sequence == entries[i-1].sequence + 1
      4. Chain linkage — previous_hash matches prior entry's entry_hash
      5. Entry-hash integrity — recomputed hash equals stored entry_hash
    """
    if not entries:
        return ExternalVerifyResult(valid=True, entries_checked=0)

    required_fields = {
        "sequence", "action", "actor_id", "tenant_id", "target",
        "outcome", "detail", "entry_hash", "previous_hash", "recorded_at",
    }

    # Determine the expected first-entry anchor.
    if anchor_hash is not None:
        expected_prev = anchor_hash
        expected_sequence = anchor_sequence if anchor_sequence is not None else 1
    else:
        expected_prev = GENESIS_HASH
        expected_sequence = 1

    for i, entry in enumerate(entries):
        # 1. Schema check
        missing = required_fields - set(entry.keys())
        if missing:
            return ExternalVerifyResult(
                valid=False,
                entries_checked=i,
                failure_reason=f"missing required fields: {sorted(missing)}",
                failure_sequence=entry.get("sequence", -1),
                failure_field="schema",
            )

        # 2. Schema version check
        version = entry.get("schema_version", 1)
        if not isinstance(version, int) or version < 1:
            return ExternalVerifyResult(
                valid=False,
                entries_checked=i,
                failure_reason=f"invalid schema_version: {version!r}",
                failure_sequence=entry.get("sequence", -1),
                failure_field="schema",
            )
        if version > LEDGER_SCHEMA_VERSION_MAX:
            return ExternalVerifyResult(
                valid=False,
                entries_checked=i,
                failure_reason=(
                    f"unknown schema_version {version} at sequence "
                    f"{entry['sequence']}: this verifier supports up to "
                    f"v{LEDGER_SCHEMA_VERSION_MAX}. Upgrade the verifier."
                ),
                failure_sequence=entry["sequence"],
                failure_field="schema",
            )

        # 3. Sequence monotonicity check (G3.2)
        # Detects deletion-with-rewrite: an attacker who deletes a middle
        # entry and re-hashes downstream entries can pass chain linkage,
        # but the sequence numbers will have a gap (or be renumbered
        # consistently — caught by entry_hash since sequence is hashed).
        if entry["sequence"] != expected_sequence:
            return ExternalVerifyResult(
                valid=False,
                entries_checked=i,
                failure_reason=(
                    f"sequence gap at index {i}: expected {expected_sequence}, "
                    f"got {entry['sequence']}"
                ),
                failure_sequence=entry["sequence"],
                failure_field="sequence",
            )

        # 4. Chain linkage check
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

        # 5. Entry hash check (tamper detection)
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
        expected_sequence += 1

    return ExternalVerifyResult(valid=True, entries_checked=len(entries))
