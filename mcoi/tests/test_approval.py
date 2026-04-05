"""Tests for approval contracts, engine, validation, expiry, and override."""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.approval import (
    ApprovalDecisionRecord,
    ApprovalRequest,
    ApprovalScope,
    ApprovalScopeType,
    ApprovalStatus,
    OverrideRecord,
    OverrideType,
)
from mcoi_runtime.core.approval import ApprovalEngine


T0 = "2025-01-15T10:00:00+00:00"
T1 = "2025-01-15T11:00:00+00:00"
T_PAST = "2025-01-14T00:00:00+00:00"
T_FUTURE = "2025-01-16T00:00:00+00:00"


def _engine(clock_time=T0):
    return ApprovalEngine(clock=lambda: clock_time)


def _scope(target_id="sk-1", scope_type=ApprovalScopeType.SKILL, **kw):
    return ApprovalScope(scope_type=scope_type, target_id=target_id, **kw)


def _request(request_id="req-1", scope=None, **kw):
    defaults = dict(
        request_id=request_id,
        requester_id="system",
        scope=scope or _scope(),
        reason="action requires approval",
        requested_at=T0,
    )
    defaults.update(kw)
    return ApprovalRequest(**defaults)


# --- Contracts ---


class TestApprovalContracts:
    def test_scope_valid(self):
        s = _scope()
        assert s.scope_type is ApprovalScopeType.SKILL
        assert s.max_executions == 1

    def test_scope_empty_target_rejected(self):
        with pytest.raises(ValueError):
            ApprovalScope(scope_type=ApprovalScopeType.EXECUTION, target_id="")

    def test_scope_zero_executions_rejected(self):
        with pytest.raises(ValueError):
            ApprovalScope(scope_type=ApprovalScopeType.EXECUTION, target_id="x", max_executions=0)

    def test_request_valid(self):
        r = _request()
        assert r.request_id == "req-1"

    def test_decision_active(self):
        d = ApprovalDecisionRecord(
            decision_id="d-1", request_id="req-1", approver_id="op-1",
            status=ApprovalStatus.APPROVED, decided_at=T0,
        )
        assert d.is_active
        assert not d.is_terminal

    def test_decision_terminal(self):
        for status in (ApprovalStatus.REJECTED, ApprovalStatus.EXPIRED, ApprovalStatus.REVOKED):
            d = ApprovalDecisionRecord(
                decision_id="d-1", request_id="req-1", approver_id="op-1",
                status=status, decided_at=T0,
            )
            assert d.is_terminal
            assert not d.is_active

    def test_override_valid(self):
        o = OverrideRecord(
            override_id="ovr-1", operator_id="admin-1",
            override_type=OverrideType.POLICY_OVERRIDE,
            target_id="policy-1", original_decision="deny",
            new_decision="allow", reason="emergency",
            overridden_at=T0,
        )
        assert o.override_type is OverrideType.POLICY_OVERRIDE


# --- Engine: request management ---


class TestApprovalRequestManagement:
    def test_submit_and_get(self):
        engine = _engine()
        req = _request()
        engine.submit_request(req)
        assert engine.get_request("req-1") is req

    def test_duplicate_request_rejected(self):
        engine = _engine()
        engine.submit_request(_request())
        with pytest.raises(ValueError, match="^approval request already exists$") as exc_info:
            engine.submit_request(_request())
        assert "req-1" not in str(exc_info.value)

    def test_list_pending(self):
        engine = _engine()
        engine.submit_request(_request("req-1"))
        engine.submit_request(_request("req-2"))
        assert len(engine.list_pending()) == 2

    def test_decided_request_not_pending(self):
        engine = _engine()
        engine.submit_request(_request("req-1"))
        engine.record_decision(request_id="req-1", approver_id="op-1", approved=True)
        assert len(engine.list_pending()) == 0


# --- Engine: decision management ---


class TestApprovalDecisions:
    def test_approve(self):
        engine = _engine()
        engine.submit_request(_request())
        d = engine.record_decision(request_id="req-1", approver_id="op-1", approved=True)
        assert d.status is ApprovalStatus.APPROVED
        assert d.is_active

    def test_reject(self):
        engine = _engine()
        engine.submit_request(_request())
        d = engine.record_decision(request_id="req-1", approver_id="op-1", approved=False, reason="too risky")
        assert d.status is ApprovalStatus.REJECTED
        assert d.reason == "too risky"

    def test_expired_before_decision(self):
        engine = _engine(clock_time=T1)  # Clock is past expiry
        engine.submit_request(_request(expires_at=T0))  # Expires at T0, clock at T1
        d = engine.record_decision(request_id="req-1", approver_id="op-1", approved=True)
        assert d.status is ApprovalStatus.EXPIRED

    def test_request_not_found(self):
        engine = _engine()
        with pytest.raises(ValueError, match="^approval request unavailable$") as exc_info:
            engine.record_decision(request_id="missing", approver_id="op-1", approved=True)
        assert "missing" not in str(exc_info.value)


# --- Validation ---


class TestApprovalValidation:
    def test_valid_approval(self):
        engine = _engine()
        engine.submit_request(_request(scope=_scope(target_id="sk-1")))
        d = engine.record_decision(request_id="req-1", approver_id="op-1", approved=True)
        valid, reason = engine.validate_approval(d.decision_id, target_id="sk-1", action="execute")
        assert valid

    def test_scope_mismatch_fails(self):
        engine = _engine()
        engine.submit_request(_request(scope=_scope(target_id="sk-1")))
        d = engine.record_decision(request_id="req-1", approver_id="op-1", approved=True)
        valid, reason = engine.validate_approval(d.decision_id, target_id="sk-OTHER", action="execute")
        assert not valid
        assert "scope mismatch" in reason

    def test_action_not_allowed(self):
        engine = _engine()
        scope = _scope(target_id="sk-1", allowed_actions=("execute",))
        engine.submit_request(_request(scope=scope))
        d = engine.record_decision(request_id="req-1", approver_id="op-1", approved=True)
        valid, reason = engine.validate_approval(d.decision_id, target_id="sk-1", action="delete")
        assert not valid
        assert "not in allowed actions" in reason

    def test_execution_limit(self):
        engine = _engine()
        scope = _scope(target_id="sk-1", max_executions=1)
        engine.submit_request(_request(scope=scope))
        d = engine.record_decision(request_id="req-1", approver_id="op-1", approved=True)

        # First use
        valid, _ = engine.validate_approval(d.decision_id, target_id="sk-1", action="execute")
        assert valid
        engine.consume_approval(d.decision_id)

        # Second use — should fail
        valid, reason = engine.validate_approval(d.decision_id, target_id="sk-1", action="execute")
        assert not valid
        assert "execution limit" in reason

    def test_multi_execution_approval(self):
        engine = _engine()
        scope = _scope(target_id="sk-1", max_executions=3)
        engine.submit_request(_request(scope=scope))
        d = engine.record_decision(request_id="req-1", approver_id="op-1", approved=True)

        for _ in range(3):
            valid, _ = engine.validate_approval(d.decision_id, target_id="sk-1", action="execute")
            assert valid
            engine.consume_approval(d.decision_id)

        valid, _ = engine.validate_approval(d.decision_id, target_id="sk-1", action="execute")
        assert not valid

    def test_rejected_decision_fails_validation(self):
        engine = _engine()
        engine.submit_request(_request())
        d = engine.record_decision(request_id="req-1", approver_id="op-1", approved=False)
        valid, reason = engine.validate_approval(d.decision_id, target_id="sk-1", action="execute")
        assert not valid

    def test_decision_not_found(self):
        engine = _engine()
        valid, reason = engine.validate_approval("missing", target_id="x", action="x")
        assert not valid
        assert "not found" in reason

    def test_expired_at_validation_time(self):
        """Approval was valid when decided but expired when validated."""
        engine = _engine(clock_time=T0)
        engine.submit_request(_request(expires_at=T_FUTURE))
        d = engine.record_decision(request_id="req-1", approver_id="op-1", approved=True)
        assert d.is_active

        # Now advance clock past expiry
        engine._clock = lambda: "2025-01-17T00:00:00+00:00"
        valid, reason = engine.validate_approval(d.decision_id, target_id="sk-1", action="execute")
        assert not valid
        assert "expired" in reason


# --- Revocation ---


class TestRevocation:
    def test_revoke_active_approval(self):
        engine = _engine()
        engine.submit_request(_request())
        d = engine.record_decision(request_id="req-1", approver_id="op-1", approved=True)
        revoked = engine.revoke(d.decision_id, reason="changed mind")
        assert revoked is not None
        assert revoked.status is ApprovalStatus.REVOKED

    def test_revoked_fails_validation(self):
        engine = _engine()
        engine.submit_request(_request())
        d = engine.record_decision(request_id="req-1", approver_id="op-1", approved=True)
        engine.revoke(d.decision_id, reason="security concern")
        valid, reason = engine.validate_approval(d.decision_id, target_id="sk-1", action="execute")
        assert not valid

    def test_revoke_nonexistent_returns_none(self):
        engine = _engine()
        assert engine.revoke("missing", reason="x") is None


# --- Override ---


class TestOverrides:
    def test_record_override(self):
        engine = _engine()
        ovr = OverrideRecord(
            override_id="ovr-1", operator_id="admin-1",
            override_type=OverrideType.POLICY_OVERRIDE,
            target_id="policy-deny-1", original_decision="deny",
            new_decision="allow", reason="emergency maintenance",
            overridden_at=T0,
        )
        engine.record_override(ovr)
        overrides = engine.list_overrides()
        assert len(overrides) == 1
        assert overrides[0].override_type is OverrideType.POLICY_OVERRIDE


# --- Golden scenarios ---


class TestApprovalGoldenScenarios:
    def test_skill_approval_full_lifecycle(self):
        """Request -> approve -> validate -> consume -> exhausted."""
        engine = _engine()
        engine.submit_request(_request(
            scope=_scope(target_id="sk-deploy", max_executions=1),
        ))
        d = engine.record_decision(request_id="req-1", approver_id="ops-lead", approved=True)
        valid, _ = engine.validate_approval(d.decision_id, target_id="sk-deploy", action="execute")
        assert valid
        engine.consume_approval(d.decision_id)
        valid, reason = engine.validate_approval(d.decision_id, target_id="sk-deploy", action="execute")
        assert not valid
        assert "execution limit" in reason

    def test_recovery_approval_with_scope(self):
        """Recovery rollback requires scoped approval."""
        engine = _engine()
        scope = _scope(
            target_id="inc-1",
            scope_type=ApprovalScopeType.RECOVERY,
            allowed_actions=("rollback",),
        )
        engine.submit_request(_request(scope=scope, incident_id="inc-1"))
        d = engine.record_decision(request_id="req-1", approver_id="admin-1", approved=True)
        valid, _ = engine.validate_approval(d.decision_id, target_id="inc-1", action="rollback")
        assert valid
        # But retry is not allowed in this scope
        valid, reason = engine.validate_approval(d.decision_id, target_id="inc-1", action="retry")
        assert not valid

    def test_expired_approval_blocks_execution(self):
        """Approval that expires between request and use fails closed."""
        engine = _engine(clock_time=T0)
        engine.submit_request(_request(expires_at=T1))
        d = engine.record_decision(request_id="req-1", approver_id="op-1", approved=True)
        # Fast-forward past expiry
        engine._clock = lambda: "2025-01-15T12:00:00+00:00"
        valid, reason = engine.validate_approval(d.decision_id, target_id="sk-1", action="execute")
        assert not valid
        assert "expired" in reason

    def test_revoked_approval_prevents_reuse(self):
        """Revoked approvals cannot be used even if originally valid."""
        engine = _engine()
        engine.submit_request(_request())
        d = engine.record_decision(request_id="req-1", approver_id="op-1", approved=True)
        engine.revoke(d.decision_id, reason="security review")
        valid, _ = engine.validate_approval(d.decision_id, target_id="sk-1", action="execute")
        assert not valid

    def test_override_recorded_with_attribution(self):
        """Manual override carries full operator attribution."""
        engine = _engine()
        ovr = OverrideRecord(
            override_id="ovr-1", operator_id="admin-1",
            override_type=OverrideType.AUTONOMY_OVERRIDE,
            target_id="autonomy-decision-1",
            original_decision="blocked", new_decision="allowed",
            reason="emergency maintenance window",
            overridden_at=T0, approval_id="approval-42",
        )
        engine.record_override(ovr)
        recorded = engine.list_overrides()[0]
        assert recorded.operator_id == "admin-1"
        assert recorded.approval_id == "approval-42"


# --- Fail-closed expiry on malformed timestamps ---


class TestApprovalExpiryFailClosed:
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
        """A request with a malformed expires_at must be rejected at construction time."""
        with pytest.raises(ValueError, match="expires_at"):
            _request(expires_at="garbage-timestamp")

    def test_malformed_expiry_blocks_validation(self):
        """A request with a malformed expires_at must fail validation."""
        engine = _engine(clock_time=T0)
        # Create request without expiry first, then monkey-patch to simulate corruption
        engine.submit_request(_request(expires_at=None))
        d = engine.record_decision(request_id="req-1", approver_id="op-1", approved=True)
        assert d.is_active
        # Replace the stored request with a duck-typed copy carrying a
        # corrupt expires_at, avoiding object.__setattr__ on frozen dataclass.
        import dataclasses as _dc
        import types as _types
        req = engine._requests["req-1"]
        ns = _types.SimpleNamespace(
            **{f.name: getattr(req, f.name) for f in _dc.fields(req)},
        )
        ns.expires_at = "corrupt!"
        engine._requests["req-1"] = ns
        valid, reason = engine.validate_approval(d.decision_id, target_id="sk-1", action="execute")
        assert not valid
        assert "expired" in reason
