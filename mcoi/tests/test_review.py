"""Tests for review engine — lifecycle, gating, expiry fail-closed."""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.review import (
    ReviewDecision,
    ReviewRequest,
    ReviewScope,
    ReviewScopeType,
    ReviewStatus,
)
from mcoi_runtime.core.review import ReviewEngine


T0 = "2025-01-15T10:00:00+00:00"
T1 = "2025-01-15T11:00:00+00:00"
T_PAST = "2025-01-14T00:00:00+00:00"
T_FUTURE = "2025-01-16T00:00:00+00:00"


def _engine(clock_time=T0):
    return ReviewEngine(clock=lambda: clock_time)


def _scope(target_id="rb-1", scope_type=ReviewScopeType.RUNBOOK_ADMISSION):
    return ReviewScope(scope_type=scope_type, target_id=target_id, description="test scope")


def _request(request_id="rev-1", scope=None, **kw):
    defaults = dict(
        request_id=request_id,
        requester_id="system",
        scope=scope or _scope(),
        reason="requires review",
        requested_at=T0,
    )
    defaults.update(kw)
    return ReviewRequest(**defaults)


# --- Basic lifecycle ---


class TestReviewLifecycle:
    def test_submit_and_get(self):
        engine = _engine()
        req = _request()
        engine.submit(req)
        assert engine.get_request("rev-1") is req

    def test_duplicate_rejected(self):
        engine = _engine()
        engine.submit(_request())
        with pytest.raises(ValueError, match="already exists"):
            engine.submit(_request())

    def test_approve(self):
        engine = _engine()
        engine.submit(_request())
        d = engine.decide(request_id="rev-1", reviewer_id="reviewer-1", approved=True)
        assert d.status is ReviewStatus.APPROVED

    def test_reject(self):
        engine = _engine()
        engine.submit(_request())
        d = engine.decide(request_id="rev-1", reviewer_id="reviewer-1", approved=False, comment="not ready")
        assert d.status is ReviewStatus.REJECTED
        assert d.comment == "not ready"

    def test_expired_before_decision(self):
        engine = _engine(clock_time=T1)
        engine.submit(_request(expires_at=T0))
        d = engine.decide(request_id="rev-1", reviewer_id="reviewer-1", approved=True)
        assert d.status is ReviewStatus.EXPIRED

    def test_request_not_found(self):
        engine = _engine()
        with pytest.raises(ValueError, match="not found"):
            engine.decide(request_id="missing", reviewer_id="reviewer-1", approved=True)

    def test_list_pending(self):
        engine = _engine()
        engine.submit(_request("rev-1"))
        engine.submit(_request("rev-2"))
        assert len(engine.list_pending()) == 2

    def test_decided_not_pending(self):
        engine = _engine()
        engine.submit(_request("rev-1"))
        engine.decide(request_id="rev-1", reviewer_id="reviewer-1", approved=True)
        assert len(engine.list_pending()) == 0


# --- Gating ---


class TestReviewGating:
    def test_gate_approved(self):
        engine = _engine()
        engine.submit(_request())
        engine.decide(request_id="rev-1", reviewer_id="reviewer-1", approved=True)
        allowed, reason = engine.check_gate("rev-1")
        assert allowed

    def test_gate_pending(self):
        engine = _engine()
        engine.submit(_request())
        allowed, reason = engine.check_gate("rev-1")
        assert not allowed
        assert "pending" in reason

    def test_gate_rejected(self):
        engine = _engine()
        engine.submit(_request())
        engine.decide(request_id="rev-1", reviewer_id="reviewer-1", approved=False)
        allowed, reason = engine.check_gate("rev-1")
        assert not allowed
        assert "not approved" in reason


# --- Fail-closed expiry on malformed timestamps ---


class TestReviewExpiryFailClosed:
    """_is_expired must fail closed: malformed or empty timestamps are treated as expired."""

    def test_valid_future_expiry_not_expired(self):
        engine = _engine(clock_time=T0)
        assert not engine._is_expired(T_FUTURE)

    def test_valid_past_expiry_is_expired(self):
        engine = _engine(clock_time=T0)
        assert engine._is_expired(T_PAST)

    def test_malformed_expiry_treated_as_expired(self):
        engine = _engine(clock_time=T0)
        assert engine._is_expired("not-a-date")

    def test_empty_string_expiry_treated_as_expired(self):
        engine = _engine(clock_time=T0)
        assert engine._is_expired("")

    def test_malformed_expiry_blocks_decision(self):
        """A request with a malformed expires_at must be marked EXPIRED at decision time."""
        engine = _engine(clock_time=T0)
        engine.submit(_request(expires_at="garbage-timestamp"))
        d = engine.decide(request_id="rev-1", reviewer_id="reviewer-1", approved=True)
        assert d.status is ReviewStatus.EXPIRED

    def test_malformed_expiry_blocks_gate(self):
        """A review with malformed expiry that somehow got approved should still be gated
        if checked via _is_expired path (tested indirectly via decision)."""
        engine = _engine(clock_time=T0)
        engine.submit(_request(expires_at="corrupt!"))
        d = engine.decide(request_id="rev-1", reviewer_id="reviewer-1", approved=True)
        # Decision should be EXPIRED because _is_expired("corrupt!") returns True
        assert d.status is ReviewStatus.EXPIRED
