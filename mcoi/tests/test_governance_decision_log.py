"""Governance Decision Log Tests — Queryable decision recording."""

import pytest
from mcoi_runtime.core.governance_decision_log import (
    GovernanceDecision,
    GovernanceDecisionLog,
    GuardDecisionDetail,
)


def _log(**kw):
    return GovernanceDecisionLog(
        clock=kw.pop("clock", lambda: "2026-04-07T12:00:00Z"),
        **kw,
    )


def _guards_allowed():
    return [
        GuardDecisionDetail("auth", True),
        GuardDecisionDetail("rbac", True),
        GuardDecisionDetail("rate_limit", True),
    ]


def _guards_denied():
    return [
        GuardDecisionDetail("auth", True),
        GuardDecisionDetail("rbac", False, reason="access denied"),
    ]


# ── Basic recording ────────────────────────────────────────────

class TestRecording:
    def test_record_allowed(self):
        log = _log()
        d = log.record(
            tenant_id="t1", identity_id="user1",
            endpoint="/api/v1/llm", method="POST",
            allowed=True, guards=_guards_allowed(),
        )
        assert d.decision_id == "govdec-1"
        assert d.allowed is True
        assert d.tenant_id == "t1"
        assert len(d.guards_evaluated) == 3

    def test_record_denied(self):
        log = _log()
        d = log.record(
            tenant_id="t1", identity_id="user1",
            endpoint="/api/v1/llm", method="POST",
            allowed=False,
            blocking_guard="rbac",
            blocking_reason="access denied",
            guards=_guards_denied(),
        )
        assert d.allowed is False
        assert d.blocking_guard == "rbac"
        assert d.blocking_reason == "access denied"

    def test_sequence_increments(self):
        log = _log()
        d1 = log.record(tenant_id="t1", allowed=True)
        d2 = log.record(tenant_id="t1", allowed=True)
        assert d1.sequence == 1
        assert d2.sequence == 2

    def test_hash_chain(self):
        log = _log()
        d1 = log.record(tenant_id="t1", allowed=True)
        d2 = log.record(tenant_id="t1", allowed=True)
        assert d1.decision_hash != ""
        assert d2.decision_hash != ""
        assert d1.decision_hash != d2.decision_hash

    def test_counters(self):
        log = _log()
        log.record(tenant_id="t1", allowed=True)
        log.record(tenant_id="t1", allowed=True)
        log.record(tenant_id="t1", allowed=False)
        assert log.allowed_count == 2
        assert log.denied_count == 1
        assert log.decision_count == 3

    def test_to_dict(self):
        log = _log()
        d = log.record(
            tenant_id="t1", identity_id="u1",
            endpoint="/api", method="GET",
            allowed=True, guards=_guards_allowed(),
        )
        data = d.to_dict()
        assert data["decision_id"] == "govdec-1"
        assert data["allowed"] is True
        assert len(data["guards_evaluated"]) == 3
        assert data["guards_evaluated"][0]["guard_name"] == "auth"


# ── Query ──────────────────────────────────────────────────────

class TestQuery:
    def _populated_log(self):
        log = _log()
        log.record(tenant_id="t1", identity_id="u1", endpoint="/api/v1/llm", method="POST", allowed=True)
        log.record(tenant_id="t1", identity_id="u2", endpoint="/api/v1/llm", method="POST", allowed=False, blocking_guard="rbac")
        log.record(tenant_id="t2", identity_id="u3", endpoint="/api/v1/query", method="GET", allowed=True)
        log.record(tenant_id="t1", identity_id="u1", endpoint="/api/v1/execute", method="POST", allowed=False, blocking_guard="rate_limit")
        log.record(tenant_id="t2", identity_id="u4", endpoint="/api/v1/llm", method="POST", allowed=False, blocking_guard="budget")
        return log

    def test_query_all(self):
        log = self._populated_log()
        results = log.query(limit=100)
        assert len(results) == 5

    def test_query_by_tenant(self):
        log = self._populated_log()
        results = log.query(tenant_id="t1")
        assert len(results) == 3
        assert all(d.tenant_id == "t1" for d in results)

    def test_query_denials(self):
        log = self._populated_log()
        results = log.query(allowed=False)
        assert len(results) == 3
        assert all(not d.allowed for d in results)

    def test_query_approvals(self):
        log = self._populated_log()
        results = log.query(allowed=True)
        assert len(results) == 2

    def test_query_by_blocking_guard(self):
        log = self._populated_log()
        results = log.query(blocking_guard="rbac")
        assert len(results) == 1
        assert results[0].blocking_guard == "rbac"

    def test_query_by_endpoint(self):
        log = self._populated_log()
        results = log.query(endpoint="/api/v1/llm")
        assert len(results) == 3

    def test_query_by_identity(self):
        log = self._populated_log()
        results = log.query(identity_id="u1")
        assert len(results) == 2

    def test_query_combined_filters(self):
        log = self._populated_log()
        results = log.query(tenant_id="t1", allowed=False)
        assert len(results) == 2

    def test_query_limit(self):
        log = self._populated_log()
        results = log.query(limit=2)
        assert len(results) == 2
        # Most recent first
        assert results[0].sequence > results[1].sequence

    def test_query_returns_reverse_chronological(self):
        log = self._populated_log()
        results = log.query(limit=100)
        for i in range(len(results) - 1):
            assert results[i].sequence > results[i + 1].sequence

    def test_get_by_id(self):
        log = _log()
        log.record(tenant_id="t1", allowed=True)
        d = log.get("govdec-1")
        assert d is not None
        assert d.decision_id == "govdec-1"

    def test_get_not_found(self):
        log = _log()
        assert log.get("nonexistent") is None


# ── Denial summary ─────────────────────────────────────────────

class TestDenialSummary:
    def test_denial_summary(self):
        log = _log()
        log.record(tenant_id="t1", endpoint="/api/llm", allowed=False, blocking_guard="rbac")
        log.record(tenant_id="t1", endpoint="/api/llm", allowed=False, blocking_guard="rbac")
        log.record(tenant_id="t1", endpoint="/api/exec", allowed=False, blocking_guard="rate_limit")
        log.record(tenant_id="t1", allowed=True)
        summary = log.denial_summary(tenant_id="t1")
        assert summary["total_denials"] == 3
        assert summary["by_guard"]["rbac"] == 2
        assert summary["by_guard"]["rate_limit"] == 1
        assert summary["by_endpoint"]["/api/llm"] == 2

    def test_empty_denial_summary(self):
        log = _log()
        log.record(tenant_id="t1", allowed=True)
        summary = log.denial_summary()
        assert summary["total_denials"] == 0
        assert summary["by_guard"] == {}


# ── Bounding ───────────────────────────────────────────────────

class TestBounding:
    def test_bounded_capacity(self):
        log = _log(max_decisions=10)
        for i in range(20):
            log.record(tenant_id="t1", allowed=True)
        assert log.decision_count == 10

    def test_oldest_evicted(self):
        log = _log(max_decisions=5)
        for i in range(10):
            log.record(tenant_id="t1", allowed=True)
        # First 5 should be evicted
        assert log.get("govdec-1") is None
        assert log.get("govdec-10") is not None

    def test_counters_survive_eviction(self):
        log = _log(max_decisions=3)
        for _ in range(10):
            log.record(tenant_id="t1", allowed=True)
        assert log.allowed_count == 10  # Counters not affected by eviction
        assert log.decision_count == 3  # But active entries bounded


# ── Summary ────────────────────────────────────────────────────

class TestSummary:
    def test_summary_fields(self):
        log = _log()
        log.record(tenant_id="t1", allowed=True)
        log.record(tenant_id="t1", allowed=False)
        summary = log.summary()
        assert summary["total_decisions"] == 2
        assert summary["allowed"] == 1
        assert summary["denied"] == 1
        assert summary["denial_rate"] == 0.5
        assert summary["active_entries"] == 2

    def test_empty_summary(self):
        log = _log()
        summary = log.summary()
        assert summary["total_decisions"] == 0
        assert summary["denial_rate"] == 0.0


# ── Guard detail preservation ──────────────────────────────────

class TestGuardDetails:
    def test_guard_chain_preserved(self):
        log = _log()
        guards = [
            GuardDecisionDetail("api_key", True),
            GuardDecisionDetail("jwt", True),
            GuardDecisionDetail("tenant", True),
            GuardDecisionDetail("rbac", True),
            GuardDecisionDetail("content_safety", True),
            GuardDecisionDetail("rate_limit", False, reason="rate limited"),
        ]
        d = log.record(
            tenant_id="t1", allowed=False,
            blocking_guard="rate_limit",
            blocking_reason="rate limited",
            guards=guards,
        )
        assert len(d.guards_evaluated) == 6
        assert d.guards_evaluated[5].guard_name == "rate_limit"
        assert d.guards_evaluated[5].allowed is False
        assert d.guards_evaluated[5].reason == "rate limited"

    def test_guard_detail_immutable(self):
        g = GuardDecisionDetail("auth", True, "ok")
        with pytest.raises(AttributeError):
            g.allowed = False
