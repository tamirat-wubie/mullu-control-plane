"""Phase 202D — Audit trail tests."""

import pytest
from mcoi_runtime.core.audit_trail import AuditTrail, AuditEntry

FIXED_CLOCK = lambda: "2026-03-26T12:00:00Z"


class TestAuditEntry:
    def test_record(self):
        trail = AuditTrail(clock=FIXED_CLOCK)
        entry = trail.record(
            action="llm.complete", actor_id="actor-1", tenant_id="t1",
            target="model/claude", outcome="success",
        )
        assert entry.action == "llm.complete"
        assert entry.sequence == 1
        assert entry.entry_hash
        assert entry.previous_hash

    def test_sequential_ids(self):
        trail = AuditTrail(clock=FIXED_CLOCK)
        e1 = trail.record(action="a", actor_id="x", tenant_id="t", target="y", outcome="ok")
        e2 = trail.record(action="b", actor_id="x", tenant_id="t", target="z", outcome="ok")
        assert e1.sequence == 1
        assert e2.sequence == 2

    def test_hash_chain(self):
        trail = AuditTrail(clock=FIXED_CLOCK)
        e1 = trail.record(action="a", actor_id="x", tenant_id="t", target="y", outcome="ok")
        e2 = trail.record(action="b", actor_id="x", tenant_id="t", target="z", outcome="ok")
        assert e2.previous_hash == e1.entry_hash

    def test_with_detail(self):
        trail = AuditTrail(clock=FIXED_CLOCK)
        entry = trail.record(
            action="llm.complete", actor_id="a1", tenant_id="t1",
            target="model", outcome="success", detail={"cost": 0.5, "tokens": 100},
        )
        assert entry.detail["cost"] == 0.5


class TestAuditQueries:
    def _setup(self):
        trail = AuditTrail(clock=FIXED_CLOCK)
        trail.record(action="llm.complete", actor_id="a1", tenant_id="t1", target="m1", outcome="success")
        trail.record(action="execute", actor_id="a1", tenant_id="t1", target="g1", outcome="success")
        trail.record(action="llm.complete", actor_id="a2", tenant_id="t2", target="m1", outcome="denied")
        trail.record(action="session.create", actor_id="a1", tenant_id="t1", target="s1", outcome="success")
        return trail

    def test_query_all(self):
        trail = self._setup()
        entries = trail.query()
        assert len(entries) == 4

    def test_query_by_tenant(self):
        trail = self._setup()
        entries = trail.query(tenant_id="t1")
        assert len(entries) == 3
        assert all(e.tenant_id == "t1" for e in entries)

    def test_query_by_action(self):
        trail = self._setup()
        entries = trail.query(action="llm.complete")
        assert len(entries) == 2

    def test_query_by_outcome(self):
        trail = self._setup()
        entries = trail.query(outcome="denied")
        assert len(entries) == 1

    def test_query_with_limit(self):
        trail = self._setup()
        entries = trail.query(limit=2)
        assert len(entries) == 2

    def test_query_by_actor(self):
        trail = self._setup()
        entries = trail.query(actor_id="a2")
        assert len(entries) == 1

    def test_combined_filters(self):
        trail = self._setup()
        entries = trail.query(tenant_id="t1", action="llm.complete")
        assert len(entries) == 1


class TestChainVerification:
    def test_verify_empty(self):
        trail = AuditTrail(clock=FIXED_CLOCK)
        valid, checked = trail.verify_chain()
        assert valid is True
        assert checked == 0

    def test_verify_valid_chain(self):
        trail = AuditTrail(clock=FIXED_CLOCK)
        for i in range(10):
            trail.record(action=f"action-{i}", actor_id="a", tenant_id="t", target="x", outcome="ok")
        valid, checked = trail.verify_chain()
        assert valid is True
        assert checked == 10

    def test_entry_count(self):
        trail = AuditTrail(clock=FIXED_CLOCK)
        assert trail.entry_count == 0
        trail.record(action="a", actor_id="x", tenant_id="t", target="y", outcome="ok")
        assert trail.entry_count == 1


class TestAuditSummary:
    def test_summary(self):
        trail = AuditTrail(clock=FIXED_CLOCK)
        trail.record(action="llm.complete", actor_id="a", tenant_id="t", target="m", outcome="success")
        trail.record(action="llm.complete", actor_id="a", tenant_id="t", target="m", outcome="denied")
        trail.record(action="execute", actor_id="a", tenant_id="t", target="g", outcome="success")
        summary = trail.summary()
        assert summary["entry_count"] == 3
        assert summary["chain_valid"] is True
        assert summary["actions"]["llm.complete"] == 2
        assert summary["outcomes"]["success"] == 2
        assert summary["outcomes"]["denied"] == 1


# ═══════════════════════════════════════════
# G3 — External Verifier (tamper detection)
# ═══════════════════════════════════════════

from dataclasses import asdict
from mcoi_runtime.core.audit_trail import (
    GENESIS_HASH,
    ExternalVerifyResult,
    verify_chain_from_entries,
)


def _trail_to_entries(trail: AuditTrail) -> list[dict]:
    """Convert recorded entries to dicts (as if exported to JSONL)."""
    return [asdict(e) for e in trail.query(limit=10000)]


class TestExternalVerifier:
    def test_empty_chain_is_valid(self):
        result = verify_chain_from_entries([])
        assert result.valid is True
        assert result.entries_checked == 0

    def test_intact_chain_passes(self):
        trail = AuditTrail(clock=FIXED_CLOCK)
        for i in range(5):
            trail.record(
                action=f"a{i}", actor_id="x", tenant_id="t",
                target="y", outcome="ok",
            )
        entries = _trail_to_entries(trail)
        result = verify_chain_from_entries(entries)
        assert result.valid is True
        assert result.entries_checked == 5

    def test_tampered_detail_detected(self):
        """Mutating an entry's detail should fail entry_hash check."""
        trail = AuditTrail(clock=FIXED_CLOCK)
        trail.record(action="a", actor_id="x", tenant_id="t",
                     target="y", outcome="ok", detail={"k": "original"})
        trail.record(action="b", actor_id="x", tenant_id="t",
                     target="y", outcome="ok")
        entries = _trail_to_entries(trail)
        # Tamper with first entry's detail
        entries[0]["detail"] = {"k": "tampered"}
        result = verify_chain_from_entries(entries)
        assert result.valid is False
        assert result.failure_field == "entry_hash"
        assert result.failure_sequence == 1

    def test_tampered_action_detected(self):
        trail = AuditTrail(clock=FIXED_CLOCK)
        trail.record(action="benign", actor_id="x", tenant_id="t",
                     target="y", outcome="ok")
        entries = _trail_to_entries(trail)
        entries[0]["action"] = "malicious"
        result = verify_chain_from_entries(entries)
        assert result.valid is False
        assert result.failure_field == "entry_hash"

    def test_broken_chain_link_detected(self):
        """Mutating previous_hash should fail chain linkage check."""
        trail = AuditTrail(clock=FIXED_CLOCK)
        for _ in range(3):
            trail.record(action="a", actor_id="x", tenant_id="t",
                         target="y", outcome="ok")
        entries = _trail_to_entries(trail)
        # Tamper with second entry's previous_hash
        entries[1]["previous_hash"] = "0" * 64
        result = verify_chain_from_entries(entries)
        assert result.valid is False
        assert result.failure_field == "previous_hash"
        assert result.failure_sequence == 2

    def test_genesis_violation_detected(self):
        """First entry's previous_hash must equal GENESIS_HASH."""
        trail = AuditTrail(clock=FIXED_CLOCK)
        trail.record(action="a", actor_id="x", tenant_id="t",
                     target="y", outcome="ok")
        entries = _trail_to_entries(trail)
        entries[0]["previous_hash"] = "f" * 64
        result = verify_chain_from_entries(entries)
        assert result.valid is False
        assert result.failure_field == "previous_hash"

    def test_deleted_entry_detected(self):
        """Removing an entry from the middle should break the chain."""
        trail = AuditTrail(clock=FIXED_CLOCK)
        for _ in range(5):
            trail.record(action="a", actor_id="x", tenant_id="t",
                         target="y", outcome="ok")
        entries = _trail_to_entries(trail)
        # Delete entry at index 2 (sequence 3)
        del entries[2]
        result = verify_chain_from_entries(entries)
        assert result.valid is False
        assert result.failure_field == "previous_hash"

    def test_missing_required_field_detected(self):
        trail = AuditTrail(clock=FIXED_CLOCK)
        trail.record(action="a", actor_id="x", tenant_id="t",
                     target="y", outcome="ok")
        entries = _trail_to_entries(trail)
        del entries[0]["entry_hash"]
        result = verify_chain_from_entries(entries)
        assert result.valid is False
        assert result.failure_field == "schema"
        assert "entry_hash" in result.failure_reason

    def test_in_memory_verify_matches_external(self):
        """AuditTrail.verify_chain() and verify_chain_from_entries() must agree."""
        trail = AuditTrail(clock=FIXED_CLOCK)
        for _ in range(10):
            trail.record(action="a", actor_id="x", tenant_id="t",
                         target="y", outcome="ok")
        in_memory_valid, in_memory_count = trail.verify_chain()
        external = verify_chain_from_entries(_trail_to_entries(trail))
        assert in_memory_valid == external.valid
        assert in_memory_count == external.entries_checked

    def test_genesis_hash_constant(self):
        """GENESIS_HASH must be sha256(b'genesis') for spec stability."""
        from hashlib import sha256
        assert GENESIS_HASH == sha256(b"genesis").hexdigest()
