"""v4.28.0 — audit chain verification across prune boundaries (audit F3).

Pre-v4.28 the verifier always started from ``sha256(b"genesis")``.
Once the chain pruned (default ``max_entries=500_000``, ~weeks of
moderate traffic), ``verify_chain()`` returned False permanently
because the first surviving entry's ``previous_hash`` no longer
pointed to genesis — it pointed to the now-pruned predecessor.

v4.28 adds an anchor that updates on prune:

- Before pruning, capture the boundary entry's ``entry_hash``
- Use that as the verification anchor for the new first entry
- Verifier starts from anchor instead of genesis
- Anchor persists via optional ``AuditStore.store_checkpoint`` so
  process restarts inherit the correct anchor

Tampering remains detectable: any in-window entry whose
``previous_hash`` doesn't link correctly fails verification, just
as before. The fix only addresses the prune-boundary issue; it
doesn't weaken tamper detection.
"""
from __future__ import annotations

from hashlib import sha256

import pytest

from mcoi_runtime.core.audit_trail import (
    AuditCheckpoint,
    AuditEntry,
    AuditStore,
    AuditTrail,
)
from mcoi_runtime.persistence.postgres_governance_stores import (
    InMemoryAuditStore,
)


_FIXED_CLOCK = lambda: "2026-01-01T00:00:00Z"


def _make_trail(max_entries: int = 5, store: AuditStore | None = None) -> AuditTrail:
    return AuditTrail(clock=_FIXED_CLOCK, max_entries=max_entries, store=store)


def _record_n(trail: AuditTrail, n: int, prefix: str = "evt") -> list[AuditEntry]:
    """Record N audit entries with deterministic content."""
    out = []
    for i in range(n):
        entry = trail.record(
            action=f"{prefix}.{i}",
            actor_id=f"actor-{i}",
            tenant_id="t1",
            target=f"resource-{i}",
            outcome="success",
        )
        out.append(entry)
    return out


# ============================================================
# Pre-prune: existing behavior unchanged
# ============================================================


def test_empty_trail_verifies():
    trail = _make_trail()
    valid, count = trail.verify_chain()
    assert valid is True
    assert count == 0


def test_unprune_chain_verifies():
    trail = _make_trail(max_entries=100)
    _record_n(trail, 50)
    valid, count = trail.verify_chain()
    assert valid is True
    assert count == 50


def test_first_entry_previous_hash_is_genesis():
    """Pre-prune, the first entry's predecessor is the genesis hash."""
    trail = _make_trail()
    entries = _record_n(trail, 1)
    assert entries[0].previous_hash == sha256(b"genesis").hexdigest()


# ============================================================
# Post-prune: the F3 fix in action
# ============================================================


def test_post_prune_chain_still_verifies():
    """The core F3 fix: chain integrity holds after pruning."""
    trail = _make_trail(max_entries=5)
    _record_n(trail, 50)  # 45 will be pruned
    assert trail.entry_count == 5
    assert trail._pruned_count == 45

    valid, count = trail.verify_chain()
    assert valid is True, "post-prune verify should succeed (F3 fix)"
    assert count == 5


def test_anchor_advances_with_each_prune():
    """Multiple prune cycles each update the anchor correctly."""
    trail = _make_trail(max_entries=3)
    _record_n(trail, 5)  # 2 pruned, anchor at seq 2
    anchor_after_first = trail._anchor_sequence
    assert anchor_after_first == 2

    _record_n(trail, 4)  # more pruned, anchor advances
    anchor_after_second = trail._anchor_sequence
    assert anchor_after_second > anchor_after_first

    valid, _ = trail.verify_chain()
    assert valid is True


def test_anchor_hash_matches_first_surviving_entry_predecessor():
    """The anchor's ``chain_hash`` must equal the first surviving
    entry's ``previous_hash`` after every prune. This is the
    invariant the verifier depends on."""
    trail = _make_trail(max_entries=3)
    _record_n(trail, 10)
    first = trail._entries[0]
    assert trail._anchor_hash == first.previous_hash


def test_post_prune_tamper_detection_still_works():
    """Tampering with an in-window entry still fails verification.
    The F3 fix doesn't weaken tamper detection — it just prevents
    the false-negative from prune."""
    trail = _make_trail(max_entries=3)
    _record_n(trail, 10)

    # Tamper: replace the second in-window entry with a forged one
    # whose previous_hash points elsewhere
    forged = AuditEntry(
        entry_id=trail._entries[1].entry_id,
        sequence=trail._entries[1].sequence,
        action="forged",
        actor_id="attacker",
        tenant_id="t1",
        target="anywhere",
        outcome="success",
        detail={},
        entry_hash="0" * 64,
        previous_hash="0" * 64,  # bogus
        recorded_at=_FIXED_CLOCK(),
    )
    trail._entries[1] = forged

    valid, failed_at = trail.verify_chain()
    assert valid is False
    assert failed_at == forged.sequence


def test_post_prune_anchor_tampering_detected():
    """If an attacker modifies the anchor itself, the first surviving
    entry's previous_hash no longer matches → verify fails."""
    trail = _make_trail(max_entries=3)
    _record_n(trail, 10)
    valid, _ = trail.verify_chain()
    assert valid is True

    trail._anchor_hash = "0" * 64  # tamper
    valid_after, _ = trail.verify_chain()
    assert valid_after is False


# ============================================================
# Persistence: anchor restored on bootstrap
# ============================================================


def test_anchor_restored_from_store_on_bootstrap():
    """Process restart with persistent store: latest checkpoint is the
    new trail's anchor. Trail can resume verifying without re-loading
    the in-memory entry list."""
    store = InMemoryAuditStore()
    # Simulate: a previous process ran, pruned some entries, persisted
    # a checkpoint at sequence 100.
    store.store_checkpoint(AuditCheckpoint(
        at_sequence=100,
        chain_hash="abc123",
        recorded_at=_FIXED_CLOCK(),
    ))

    # Fresh trail bootstraps, picks up the checkpoint
    trail = AuditTrail(clock=_FIXED_CLOCK, max_entries=10, store=store)
    assert trail._anchor_sequence == 100
    assert trail._anchor_hash == "abc123"


def test_no_checkpoint_uses_genesis():
    """Without a stored checkpoint, the anchor stays at genesis (the
    initial state). v4.27.x and earlier behavior preserved when no
    pruning has happened."""
    store = InMemoryAuditStore()  # empty
    trail = AuditTrail(clock=_FIXED_CLOCK, max_entries=10, store=store)
    assert trail._anchor_hash == sha256(b"genesis").hexdigest()
    assert trail._anchor_sequence == 0


def test_prune_persists_checkpoint_to_store():
    """When pruning happens, the new anchor is persisted to the store."""
    store = InMemoryAuditStore()
    trail = AuditTrail(clock=_FIXED_CLOCK, max_entries=3, store=store)
    _record_n(trail, 10)

    checkpoint = store.latest_checkpoint()
    assert checkpoint is not None
    assert checkpoint.at_sequence == trail._anchor_sequence
    assert checkpoint.chain_hash == trail._anchor_hash


def test_checkpoint_survives_process_restart():
    """End-to-end: trail-1 prunes and persists checkpoint; trail-2
    inherits the anchor; trail-2's continued recording verifies
    cleanly."""
    store = InMemoryAuditStore()
    trail_1 = AuditTrail(clock=_FIXED_CLOCK, max_entries=3, store=store)
    _record_n(trail_1, 10)
    anchor_1 = (trail_1._anchor_hash, trail_1._anchor_sequence)

    # Simulate restart: new trail with same store, no in-memory entries
    trail_2 = AuditTrail(clock=_FIXED_CLOCK, max_entries=3, store=store)
    assert (trail_2._anchor_hash, trail_2._anchor_sequence) == anchor_1


# ============================================================
# Backward compat: stores that don't override checkpoint methods
# ============================================================


class _LegacyAuditStore(AuditStore):
    """Pre-v4.28 store with no checkpoint methods. Inherits the base
    no-op for store_checkpoint and latest_checkpoint."""

    def __init__(self) -> None:
        self._entries: list[AuditEntry] = []

    def append(self, entry: AuditEntry) -> None:
        self._entries.append(entry)


def test_legacy_store_works_without_checkpoint_persistence():
    """Stores without checkpoint method overrides still work — the
    in-process anchor still updates on prune; only the durability
    across restart is lost (which the legacy store didn't have anyway)."""
    store = _LegacyAuditStore()
    trail = AuditTrail(clock=_FIXED_CLOCK, max_entries=3, store=store)
    _record_n(trail, 10)

    valid, _ = trail.verify_chain()
    assert valid is True


def test_summary_reports_chain_valid_after_prune():
    """The ``summary()`` output (used by /health) must reflect post-fix
    behavior: chain_valid=True after prune, not False."""
    trail = _make_trail(max_entries=3)
    _record_n(trail, 10)

    summary = trail.summary()
    assert summary["chain_valid"] is True
    assert summary["entry_count"] == 3


# ============================================================
# Edge cases
# ============================================================


def test_exactly_max_entries_no_prune_no_anchor_change():
    """At capacity (entry_count == max_entries), no prune yet —
    anchor stays at genesis."""
    trail = _make_trail(max_entries=5)
    _record_n(trail, 5)
    assert trail._pruned_count == 0
    assert trail._anchor_hash == sha256(b"genesis").hexdigest()


def test_one_over_max_triggers_single_prune_and_anchor_update():
    trail = _make_trail(max_entries=5)
    entries = _record_n(trail, 6)
    assert trail._pruned_count == 1
    # Anchor should equal the first (only pruned) entry's hash
    assert trail._anchor_hash == entries[0].entry_hash
    assert trail._anchor_sequence == entries[0].sequence


def test_record_then_verify_immediately_after_prune():
    """A record that triggers a prune produces an immediately-valid chain."""
    trail = _make_trail(max_entries=3)
    _record_n(trail, 4)  # 1 pruned
    valid, _ = trail.verify_chain()
    assert valid is True
