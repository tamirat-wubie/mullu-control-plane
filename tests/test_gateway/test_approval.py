"""Approval Router Tests.

Tests: Risk classification, approval lifecycle, pending management,
    auto-approve, timeout handling.
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gateway.approval import (  # noqa: E402
    ApprovalRouter,
    ApprovalStatus,
    RiskTier,
    classify_risk,
)


# ═══ Risk Classification ═══


class TestRiskClassification:
    def test_low_risk_informational(self):
        assert classify_risk("query", "what time is it?") == RiskTier.LOW

    def test_medium_risk_create(self):
        assert classify_risk("create_event", "schedule a meeting") == RiskTier.MEDIUM

    def test_high_risk_delete(self):
        assert classify_risk("delete_file", "remove old reports") == RiskTier.HIGH

    def test_high_risk_send_email(self):
        assert classify_risk("compose", "send_email to boss") == RiskTier.HIGH

    def test_high_risk_payment(self):
        assert classify_risk("process", "make a payment of $500") == RiskTier.HIGH

    def test_medium_risk_book(self):
        assert classify_risk("calendar", "book a room for tomorrow") == RiskTier.MEDIUM

    def test_low_risk_read_only(self):
        assert classify_risk("read", "show me my calendar") == RiskTier.LOW


# ═══ Approval Lifecycle ═══


class TestApprovalLifecycle:
    def test_low_risk_auto_approved(self):
        router = ApprovalRouter()
        req = router.request_approval(
            tenant_id="t1", identity_id="u1", channel="whatsapp",
            action_description="query", body="what is the weather?",
        )
        assert req.status == ApprovalStatus.APPROVED
        assert req.resolved_by == "auto"
        assert router.pending_count == 0

    def test_high_risk_creates_pending(self):
        router = ApprovalRouter()
        req = router.request_approval(
            tenant_id="t1", identity_id="u1", channel="telegram",
            action_description="delete", body="delete all old files",
        )
        assert req.status == ApprovalStatus.PENDING
        assert req.risk_tier == RiskTier.HIGH
        assert router.pending_count == 1

    def test_resolve_approve(self):
        router = ApprovalRouter()
        req = router.request_approval(
            tenant_id="t1", identity_id="u1", channel="web",
            action_description="send_email", body="send report to team",
        )
        resolved = router.resolve(req.request_id, approved=True, resolved_by="user1")
        assert resolved is not None
        assert resolved.status == ApprovalStatus.APPROVED
        assert resolved.resolved_by == "user1"
        assert router.pending_count == 0

    def test_resolve_deny(self):
        router = ApprovalRouter()
        req = router.request_approval(
            tenant_id="t1", identity_id="u1", channel="web",
            action_description="delete", body="delete everything",
        )
        resolved = router.resolve(req.request_id, approved=False)
        assert resolved.status == ApprovalStatus.DENIED

    def test_resolve_unknown_returns_none(self):
        router = ApprovalRouter()
        assert router.resolve("nonexistent", approved=True) is None

    def test_double_resolve_returns_none(self):
        router = ApprovalRouter()
        req = router.request_approval(
            tenant_id="t1", identity_id="u1", channel="web",
            action_description="execute", body="run script",
        )
        router.resolve(req.request_id, approved=True)
        assert router.resolve(req.request_id, approved=True) is None

    def test_expired_pending_resolves_to_expired(self):
        times = [
            "2026-04-20T12:00:00+00:00",
            "2026-04-20T12:10:00+00:00",
        ]

        def clock() -> str:
            return times.pop(0) if len(times) > 1 else times[0]

        router = ApprovalRouter(clock=clock, timeout_seconds=60)
        req = router.request_approval(
            tenant_id="t1", identity_id="u1", channel="web",
            action_description="delete", body="delete old files",
        )
        resolved = router.resolve(req.request_id, approved=True, resolved_by="user1")
        assert resolved is not None
        assert resolved.status == ApprovalStatus.EXPIRED
        assert resolved.resolved_by == "timeout"


# ═══ Pending Management ═══


class TestPendingManagement:
    def test_get_pending_all(self):
        router = ApprovalRouter()
        router.request_approval(
            tenant_id="t1", identity_id="u1", channel="web",
            action_description="delete", body="delete file",
        )
        router.request_approval(
            tenant_id="t2", identity_id="u2", channel="web",
            action_description="send_email", body="send to client",
        )
        assert len(router.get_pending()) == 2

    def test_get_pending_by_tenant(self):
        router = ApprovalRouter()
        router.request_approval(
            tenant_id="t1", identity_id="u1", channel="web",
            action_description="delete", body="delete file",
        )
        router.request_approval(
            tenant_id="t2", identity_id="u2", channel="web",
            action_description="send_email", body="send report",
        )
        assert len(router.get_pending("t1")) == 1
        assert len(router.get_pending("t2")) == 1
        assert len(router.get_pending("t3")) == 0

    def test_get_pending_prunes_expired_requests(self):
        times = [
            "2026-04-20T12:00:00+00:00",
            "2026-04-20T12:10:00+00:00",
        ]

        def clock() -> str:
            return times.pop(0) if len(times) > 1 else times[0]

        router = ApprovalRouter(clock=clock, timeout_seconds=60)
        router.request_approval(
            tenant_id="t1", identity_id="u1", channel="web",
            action_description="delete", body="delete file",
        )
        assert router.get_pending() == []
        assert router.pending_count == 0


# ═══ Summary ═══


class TestApprovalSummary:
    def test_summary(self):
        router = ApprovalRouter()
        router.request_approval(
            tenant_id="t1", identity_id="u1", channel="web",
            action_description="query", body="what is 2+2",
        )
        router.request_approval(
            tenant_id="t1", identity_id="u1", channel="web",
            action_description="delete", body="delete old files",
        )
        summary = router.summary()
        assert summary["total"] == 2
        assert summary["pending"] == 1
        assert summary["history_count"] == 1  # Low-risk auto-approved
        assert summary["by_status"] == {"approved": 1, "pending": 1}
        assert summary["by_risk_tier"] == {"high": 1, "low": 1}
        assert summary["pending_by_risk_tier"] == {"high": 1}
        assert summary["resolution_reasons"] == {"auto_approved": 1}
        assert summary["total_evicted"] == 0

    def test_summary_counts_expired_requests_in_history(self):
        times = [
            "2026-04-20T12:00:00+00:00",
            "2026-04-20T12:10:00+00:00",
        ]

        def clock() -> str:
            return times.pop(0) if len(times) > 1 else times[0]

        router = ApprovalRouter(clock=clock, timeout_seconds=60)
        router.request_approval(
            tenant_id="t1", identity_id="u1", channel="web",
            action_description="delete", body="delete old files",
        )
        summary = router.summary()
        assert summary["pending"] == 0
        assert summary["history_count"] == 1
        assert summary["total"] == 1
        assert summary["by_status"] == {"expired": 1}
        assert summary["resolution_reasons"] == {"timed_out": 1}

    def test_summary_uses_bounded_resolution_reasons(self):
        router = ApprovalRouter()
        approved = router.request_approval(
            tenant_id="t1", identity_id="u1", channel="web",
            action_description="send_email", body="send report",
        )
        denied = router.request_approval(
            tenant_id="t1", identity_id="u2", channel="web",
            action_description="delete", body="delete file",
        )

        router.resolve(approved.request_id, approved=True, resolved_by="operator-secret")
        router.resolve(denied.request_id, approved=False, resolved_by="operator-secret")
        summary = router.summary()

        assert summary["total"] == 2
        assert summary["by_status"] == {"approved": 1, "denied": 1}
        assert summary["resolution_reasons"] == {
            "operator_approved": 1,
            "operator_denied": 1,
        }
        assert "operator-secret" not in summary["resolution_reasons"]

    def test_capacity_eviction_is_recorded_as_bounded_resolution(self):
        times = [
            "2026-04-20T12:00:00+00:00",
            "2026-04-20T12:00:01+00:00",
        ]

        def clock() -> str:
            return times.pop(0) if len(times) > 1 else times[0]

        router = ApprovalRouter(clock=clock)
        router.MAX_PENDING = 1
        first = router.request_approval(
            tenant_id="t1", identity_id="u1", channel="web",
            action_description="delete", body="delete first",
        )
        second = router.request_approval(
            tenant_id="t1", identity_id="u2", channel="web",
            action_description="delete", body="delete second",
        )
        summary = router.summary()

        assert router.lookup_request(first.request_id) is None
        assert router.lookup_request(second.request_id) is not None
        assert summary["pending"] == 1
        assert summary["history_count"] == 1
        assert summary["total_evicted"] == 1
        assert summary["resolution_reasons"] == {"capacity_evicted": 1}
