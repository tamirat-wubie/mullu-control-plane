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
