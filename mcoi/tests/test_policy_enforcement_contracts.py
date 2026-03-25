"""Comprehensive tests for policy enforcement contracts.

Covers enums, dataclass construction, validation, immutability,
freeze_value behavior, default values, and to_dict serialization.
"""

from __future__ import annotations

import dataclasses
from types import MappingProxyType

import pytest

from mcoi_runtime.contracts.policy_enforcement import (
    SessionStatus,
    SessionKind,
    PrivilegeLevel,
    EnforcementDecision,
    RevocationReason,
    StepUpStatus,
    SessionRecord,
    SessionConstraint,
    PrivilegeElevationRequest,
    PrivilegeElevationDecision,
    EnforcementEvent,
    RevocationRecord,
    SessionSnapshot,
    EnforcementAuditRecord,
    PolicySessionBinding,
    SessionClosureReport,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TS = "2025-06-01T12:00:00+00:00"
TS2 = "2025-07-01T08:00:00+00:00"


# ---------------------------------------------------------------------------
# Helpers — minimal-valid constructors with override support
# ---------------------------------------------------------------------------


def _session(**kw):
    defaults = dict(
        session_id="ses-1",
        identity_id="id-1",
        opened_at=TS,
    )
    defaults.update(kw)
    return SessionRecord(**defaults)


def _constraint(**kw):
    defaults = dict(
        constraint_id="con-1",
        session_id="ses-1",
        created_at=TS,
    )
    defaults.update(kw)
    return SessionConstraint(**defaults)


def _elev_request(**kw):
    defaults = dict(
        request_id="req-1",
        session_id="ses-1",
        identity_id="id-1",
        requested_at=TS,
    )
    defaults.update(kw)
    return PrivilegeElevationRequest(**defaults)


def _elev_decision(**kw):
    defaults = dict(
        decision_id="dec-1",
        request_id="req-1",
        approver_id="app-1",
        decided_at=TS,
    )
    defaults.update(kw)
    return PrivilegeElevationDecision(**defaults)


def _enforcement_event(**kw):
    defaults = dict(
        event_id="evt-1",
        session_id="ses-1",
        identity_id="id-1",
        evaluated_at=TS,
    )
    defaults.update(kw)
    return EnforcementEvent(**defaults)


def _revocation(**kw):
    defaults = dict(
        revocation_id="rev-1",
        session_id="ses-1",
        identity_id="id-1",
        revoked_at=TS,
    )
    defaults.update(kw)
    return RevocationRecord(**defaults)


def _snapshot(**kw):
    defaults = dict(
        snapshot_id="snap-1",
        captured_at=TS,
    )
    defaults.update(kw)
    return SessionSnapshot(**defaults)


def _audit(**kw):
    defaults = dict(
        audit_id="aud-1",
        session_id="ses-1",
        identity_id="id-1",
        recorded_at=TS,
    )
    defaults.update(kw)
    return EnforcementAuditRecord(**defaults)


def _binding(**kw):
    defaults = dict(
        binding_id="bind-1",
        session_id="ses-1",
        resource_type="connector",
        resource_id="res-1",
        bound_at=TS,
    )
    defaults.update(kw)
    return PolicySessionBinding(**defaults)


def _closure(**kw):
    defaults = dict(
        report_id="rpt-1",
        session_id="ses-1",
        identity_id="id-1",
        closed_at=TS,
    )
    defaults.update(kw)
    return SessionClosureReport(**defaults)


# ===================================================================
# ENUM TESTS
# ===================================================================


class TestSessionStatus:
    def test_member_count(self):
        assert len(SessionStatus) == 5

    def test_values(self):
        assert SessionStatus.ACTIVE.value == "active"
        assert SessionStatus.SUSPENDED.value == "suspended"
        assert SessionStatus.EXPIRED.value == "expired"
        assert SessionStatus.REVOKED.value == "revoked"
        assert SessionStatus.CLOSED.value == "closed"

    def test_members_are_unique(self):
        values = [m.value for m in SessionStatus]
        assert len(values) == len(set(values))


class TestSessionKind:
    def test_member_count(self):
        assert len(SessionKind) == 5

    def test_values(self):
        assert SessionKind.INTERACTIVE.value == "interactive"
        assert SessionKind.SERVICE.value == "service"
        assert SessionKind.CONNECTOR.value == "connector"
        assert SessionKind.CAMPAIGN.value == "campaign"
        assert SessionKind.SYSTEM.value == "system"

    def test_members_are_unique(self):
        values = [m.value for m in SessionKind]
        assert len(values) == len(set(values))


class TestPrivilegeLevel:
    def test_member_count(self):
        assert len(PrivilegeLevel) == 5

    def test_values(self):
        assert PrivilegeLevel.STANDARD.value == "standard"
        assert PrivilegeLevel.ELEVATED.value == "elevated"
        assert PrivilegeLevel.ADMIN.value == "admin"
        assert PrivilegeLevel.SYSTEM.value == "system"
        assert PrivilegeLevel.EMERGENCY.value == "emergency"

    def test_members_are_unique(self):
        values = [m.value for m in PrivilegeLevel]
        assert len(values) == len(set(values))


class TestEnforcementDecision:
    def test_member_count(self):
        assert len(EnforcementDecision) == 5

    def test_values(self):
        assert EnforcementDecision.ALLOWED.value == "allowed"
        assert EnforcementDecision.DENIED.value == "denied"
        assert EnforcementDecision.STEP_UP_REQUIRED.value == "step_up_required"
        assert EnforcementDecision.SUSPENDED.value == "suspended"
        assert EnforcementDecision.REVOKED.value == "revoked"

    def test_members_are_unique(self):
        values = [m.value for m in EnforcementDecision]
        assert len(values) == len(set(values))


class TestRevocationReason:
    def test_member_count(self):
        assert len(RevocationReason) == 7

    def test_values(self):
        assert RevocationReason.POLICY_VIOLATION.value == "policy_violation"
        assert RevocationReason.TENANT_CHANGE.value == "tenant_change"
        assert RevocationReason.ENVIRONMENT_CHANGE.value == "environment_change"
        assert RevocationReason.RISK_ESCALATION.value == "risk_escalation"
        assert RevocationReason.COMPLIANCE_FAILURE.value == "compliance_failure"
        assert RevocationReason.MANUAL_REVOCATION.value == "manual_revocation"
        assert RevocationReason.DELEGATION_EXPIRED.value == "delegation_expired"

    def test_members_are_unique(self):
        values = [m.value for m in RevocationReason]
        assert len(values) == len(set(values))


class TestStepUpStatus:
    def test_member_count(self):
        assert len(StepUpStatus) == 4

    def test_values(self):
        assert StepUpStatus.PENDING.value == "pending"
        assert StepUpStatus.APPROVED.value == "approved"
        assert StepUpStatus.DENIED.value == "denied"
        assert StepUpStatus.EXPIRED.value == "expired"

    def test_members_are_unique(self):
        values = [m.value for m in StepUpStatus]
        assert len(values) == len(set(values))


# ===================================================================
# SessionRecord TESTS
# ===================================================================


class TestSessionRecord:
    def test_minimal_construction(self):
        r = _session()
        assert r.session_id == "ses-1"
        assert r.identity_id == "id-1"
        assert r.opened_at == TS

    def test_defaults(self):
        r = _session()
        assert r.kind is SessionKind.INTERACTIVE
        assert r.status is SessionStatus.ACTIVE
        assert r.privilege_level is PrivilegeLevel.STANDARD
        assert r.scope_ref_id == ""
        assert r.environment_id == ""
        assert r.connector_id == ""
        assert r.campaign_id == ""
        assert r.expires_at == ""
        assert r.closed_at == ""
        assert r.metadata == {}

    def test_full_construction(self):
        r = _session(
            kind=SessionKind.SERVICE,
            status=SessionStatus.SUSPENDED,
            privilege_level=PrivilegeLevel.ADMIN,
            scope_ref_id="scope-1",
            environment_id="env-1",
            connector_id="conn-1",
            campaign_id="camp-1",
            expires_at=TS2,
            closed_at=TS2,
            metadata={"key": "val"},
        )
        assert r.kind is SessionKind.SERVICE
        assert r.status is SessionStatus.SUSPENDED
        assert r.privilege_level is PrivilegeLevel.ADMIN
        assert r.scope_ref_id == "scope-1"
        assert r.environment_id == "env-1"
        assert r.connector_id == "conn-1"
        assert r.campaign_id == "camp-1"
        assert r.expires_at == TS2
        assert r.closed_at == TS2
        assert r.metadata["key"] == "val"

    def test_frozen(self):
        r = _session()
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.session_id = "other"

    def test_session_id_empty_rejected(self):
        with pytest.raises(ValueError, match="session_id"):
            _session(session_id="")

    def test_session_id_whitespace_rejected(self):
        with pytest.raises(ValueError, match="session_id"):
            _session(session_id="   ")

    def test_identity_id_empty_rejected(self):
        with pytest.raises(ValueError, match="identity_id"):
            _session(identity_id="")

    def test_identity_id_whitespace_rejected(self):
        with pytest.raises(ValueError, match="identity_id"):
            _session(identity_id="  \t ")

    def test_opened_at_invalid(self):
        with pytest.raises(ValueError, match="opened_at"):
            _session(opened_at="not-a-date")

    def test_opened_at_empty(self):
        with pytest.raises(ValueError, match="opened_at"):
            _session(opened_at="")

    def test_kind_string_rejected(self):
        with pytest.raises(ValueError, match="kind"):
            _session(kind="interactive")

    def test_status_string_rejected(self):
        with pytest.raises(ValueError, match="status"):
            _session(status="active")

    def test_privilege_level_string_rejected(self):
        with pytest.raises(ValueError, match="privilege_level"):
            _session(privilege_level="standard")

    def test_metadata_frozen_to_mapping_proxy(self):
        r = _session(metadata={"a": 1})
        assert isinstance(r.metadata, MappingProxyType)

    def test_metadata_nested_list_frozen(self):
        r = _session(metadata={"tags": [1, 2, 3]})
        assert isinstance(r.metadata["tags"], tuple)
        assert r.metadata["tags"] == (1, 2, 3)

    def test_to_dict_preserves_enums(self):
        r = _session()
        d = r.to_dict()
        assert d["kind"] is SessionKind.INTERACTIVE
        assert d["status"] is SessionStatus.ACTIVE
        assert d["privilege_level"] is PrivilegeLevel.STANDARD

    def test_to_dict_metadata_thawed(self):
        r = _session(metadata={"x": [1, 2]})
        d = r.to_dict()
        assert isinstance(d["metadata"], dict)
        assert isinstance(d["metadata"]["x"], list)

    def test_to_dict_returns_all_fields(self):
        r = _session()
        d = r.to_dict()
        field_names = {f.name for f in dataclasses.fields(r)}
        assert set(d.keys()) == field_names


# ===================================================================
# SessionConstraint TESTS
# ===================================================================


class TestSessionConstraint:
    def test_minimal_construction(self):
        r = _constraint()
        assert r.constraint_id == "con-1"
        assert r.session_id == "ses-1"
        assert r.created_at == TS

    def test_defaults(self):
        r = _constraint()
        assert r.resource_type == ""
        assert r.action == ""
        assert r.environment_id == ""
        assert r.connector_id == ""
        assert r.max_privilege is PrivilegeLevel.STANDARD
        assert r.valid_from == ""
        assert r.valid_until == ""

    def test_full_construction(self):
        r = _constraint(
            resource_type="file",
            action="read",
            environment_id="env-1",
            connector_id="conn-1",
            max_privilege=PrivilegeLevel.ELEVATED,
            valid_from=TS,
            valid_until=TS2,
        )
        assert r.resource_type == "file"
        assert r.max_privilege is PrivilegeLevel.ELEVATED

    def test_frozen(self):
        r = _constraint()
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.constraint_id = "other"

    def test_constraint_id_empty_rejected(self):
        with pytest.raises(ValueError, match="constraint_id"):
            _constraint(constraint_id="")

    def test_constraint_id_whitespace_rejected(self):
        with pytest.raises(ValueError, match="constraint_id"):
            _constraint(constraint_id="   ")

    def test_session_id_empty_rejected(self):
        with pytest.raises(ValueError, match="session_id"):
            _constraint(session_id="")

    def test_created_at_invalid(self):
        with pytest.raises(ValueError, match="created_at"):
            _constraint(created_at="bad")

    def test_max_privilege_string_rejected(self):
        with pytest.raises(ValueError, match="max_privilege"):
            _constraint(max_privilege="standard")

    def test_to_dict_preserves_enum(self):
        d = _constraint().to_dict()
        assert d["max_privilege"] is PrivilegeLevel.STANDARD


# ===================================================================
# PrivilegeElevationRequest TESTS
# ===================================================================


class TestPrivilegeElevationRequest:
    def test_minimal_construction(self):
        r = _elev_request()
        assert r.request_id == "req-1"
        assert r.session_id == "ses-1"
        assert r.identity_id == "id-1"

    def test_defaults(self):
        r = _elev_request()
        assert r.requested_level is PrivilegeLevel.ELEVATED
        assert r.reason == ""
        assert r.resource_type == ""
        assert r.action == ""
        assert r.status is StepUpStatus.PENDING
        assert r.metadata == {}

    def test_full_construction(self):
        r = _elev_request(
            requested_level=PrivilegeLevel.ADMIN,
            reason="deploy",
            resource_type="cluster",
            action="write",
            status=StepUpStatus.APPROVED,
            metadata={"tier": "high"},
        )
        assert r.requested_level is PrivilegeLevel.ADMIN
        assert r.status is StepUpStatus.APPROVED
        assert r.metadata["tier"] == "high"

    def test_frozen(self):
        r = _elev_request()
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.request_id = "x"

    def test_request_id_empty_rejected(self):
        with pytest.raises(ValueError, match="request_id"):
            _elev_request(request_id="")

    def test_session_id_empty_rejected(self):
        with pytest.raises(ValueError, match="session_id"):
            _elev_request(session_id="")

    def test_identity_id_empty_rejected(self):
        with pytest.raises(ValueError, match="identity_id"):
            _elev_request(identity_id="")

    def test_requested_level_string_rejected(self):
        with pytest.raises(ValueError, match="requested_level"):
            _elev_request(requested_level="elevated")

    def test_status_string_rejected(self):
        with pytest.raises(ValueError, match="status"):
            _elev_request(status="pending")

    def test_requested_at_invalid(self):
        with pytest.raises(ValueError, match="requested_at"):
            _elev_request(requested_at="nope")

    def test_metadata_frozen(self):
        r = _elev_request(metadata={"a": [1]})
        assert isinstance(r.metadata, MappingProxyType)
        assert isinstance(r.metadata["a"], tuple)

    def test_to_dict_preserves_enums(self):
        d = _elev_request().to_dict()
        assert d["requested_level"] is PrivilegeLevel.ELEVATED
        assert d["status"] is StepUpStatus.PENDING


# ===================================================================
# PrivilegeElevationDecision TESTS
# ===================================================================


class TestPrivilegeElevationDecision:
    def test_minimal_construction(self):
        r = _elev_decision()
        assert r.decision_id == "dec-1"
        assert r.request_id == "req-1"
        assert r.approver_id == "app-1"

    def test_defaults(self):
        r = _elev_decision()
        assert r.status is StepUpStatus.DENIED
        assert r.reason == ""
        assert r.metadata == {}

    def test_full_construction(self):
        r = _elev_decision(
            status=StepUpStatus.APPROVED,
            reason="policy met",
            metadata={"reviewed": True},
        )
        assert r.status is StepUpStatus.APPROVED
        assert r.reason == "policy met"

    def test_frozen(self):
        r = _elev_decision()
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.decision_id = "x"

    def test_decision_id_empty_rejected(self):
        with pytest.raises(ValueError, match="decision_id"):
            _elev_decision(decision_id="")

    def test_request_id_empty_rejected(self):
        with pytest.raises(ValueError, match="request_id"):
            _elev_decision(request_id="")

    def test_approver_id_empty_rejected(self):
        with pytest.raises(ValueError, match="approver_id"):
            _elev_decision(approver_id="")

    def test_approver_id_whitespace_rejected(self):
        with pytest.raises(ValueError, match="approver_id"):
            _elev_decision(approver_id="  ")

    def test_status_string_rejected(self):
        with pytest.raises(ValueError, match="status"):
            _elev_decision(status="denied")

    def test_decided_at_invalid(self):
        with pytest.raises(ValueError, match="decided_at"):
            _elev_decision(decided_at="x")

    def test_metadata_frozen(self):
        r = _elev_decision(metadata={"k": {"nested": [1]}})
        assert isinstance(r.metadata, MappingProxyType)
        assert isinstance(r.metadata["k"], MappingProxyType)

    def test_to_dict_preserves_enum(self):
        d = _elev_decision().to_dict()
        assert d["status"] is StepUpStatus.DENIED


# ===================================================================
# EnforcementEvent TESTS
# ===================================================================


class TestEnforcementEvent:
    def test_minimal_construction(self):
        r = _enforcement_event()
        assert r.event_id == "evt-1"
        assert r.session_id == "ses-1"
        assert r.identity_id == "id-1"

    def test_defaults(self):
        r = _enforcement_event()
        assert r.resource_type == ""
        assert r.action == ""
        assert r.decision is EnforcementDecision.DENIED
        assert r.reason == ""
        assert r.environment_id == ""
        assert r.connector_id == ""
        assert r.metadata == {}

    def test_full_construction(self):
        r = _enforcement_event(
            resource_type="api",
            action="call",
            decision=EnforcementDecision.ALLOWED,
            reason="passed",
            environment_id="prod",
            connector_id="c-1",
            metadata={"latency": 42},
        )
        assert r.decision is EnforcementDecision.ALLOWED
        assert r.metadata["latency"] == 42

    def test_frozen(self):
        r = _enforcement_event()
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.event_id = "x"

    def test_event_id_empty_rejected(self):
        with pytest.raises(ValueError, match="event_id"):
            _enforcement_event(event_id="")

    def test_session_id_empty_rejected(self):
        with pytest.raises(ValueError, match="session_id"):
            _enforcement_event(session_id="")

    def test_identity_id_empty_rejected(self):
        with pytest.raises(ValueError, match="identity_id"):
            _enforcement_event(identity_id="")

    def test_decision_string_rejected(self):
        with pytest.raises(ValueError, match="decision"):
            _enforcement_event(decision="denied")

    def test_evaluated_at_invalid(self):
        with pytest.raises(ValueError, match="evaluated_at"):
            _enforcement_event(evaluated_at="bad")

    def test_metadata_frozen(self):
        r = _enforcement_event(metadata={"a": [1, 2]})
        assert isinstance(r.metadata, MappingProxyType)
        assert r.metadata["a"] == (1, 2)

    def test_to_dict_preserves_enum(self):
        d = _enforcement_event().to_dict()
        assert d["decision"] is EnforcementDecision.DENIED

    def test_to_dict_tuples_become_lists(self):
        r = _enforcement_event(metadata={"x": [1, 2]})
        d = r.to_dict()
        assert isinstance(d["metadata"]["x"], list)


# ===================================================================
# RevocationRecord TESTS
# ===================================================================


class TestRevocationRecord:
    def test_minimal_construction(self):
        r = _revocation()
        assert r.revocation_id == "rev-1"
        assert r.session_id == "ses-1"
        assert r.identity_id == "id-1"

    def test_defaults(self):
        r = _revocation()
        assert r.reason is RevocationReason.MANUAL_REVOCATION
        assert r.detail == ""
        assert r.metadata == {}

    def test_full_construction(self):
        r = _revocation(
            reason=RevocationReason.POLICY_VIOLATION,
            detail="exceeded threshold",
            metadata={"alert": True},
        )
        assert r.reason is RevocationReason.POLICY_VIOLATION
        assert r.detail == "exceeded threshold"

    def test_frozen(self):
        r = _revocation()
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.revocation_id = "x"

    def test_revocation_id_empty_rejected(self):
        with pytest.raises(ValueError, match="revocation_id"):
            _revocation(revocation_id="")

    def test_session_id_empty_rejected(self):
        with pytest.raises(ValueError, match="session_id"):
            _revocation(session_id="")

    def test_identity_id_whitespace_rejected(self):
        with pytest.raises(ValueError, match="identity_id"):
            _revocation(identity_id="   ")

    def test_reason_string_rejected(self):
        with pytest.raises(ValueError, match="reason"):
            _revocation(reason="manual_revocation")

    def test_revoked_at_invalid(self):
        with pytest.raises(ValueError, match="revoked_at"):
            _revocation(revoked_at="nope")

    def test_all_revocation_reasons_accepted(self):
        for reason in RevocationReason:
            r = _revocation(reason=reason)
            assert r.reason is reason

    def test_metadata_frozen(self):
        r = _revocation(metadata={"k": "v"})
        assert isinstance(r.metadata, MappingProxyType)

    def test_to_dict_preserves_enum(self):
        d = _revocation().to_dict()
        assert d["reason"] is RevocationReason.MANUAL_REVOCATION


# ===================================================================
# SessionSnapshot TESTS
# ===================================================================


class TestSessionSnapshot:
    def test_minimal_construction(self):
        r = _snapshot()
        assert r.snapshot_id == "snap-1"
        assert r.captured_at == TS

    def test_defaults(self):
        r = _snapshot()
        assert r.scope_ref_id == ""
        assert r.total_sessions == 0
        assert r.active_sessions == 0
        assert r.suspended_sessions == 0
        assert r.revoked_sessions == 0
        assert r.total_constraints == 0
        assert r.total_step_ups == 0
        assert r.total_revocations == 0
        assert r.total_enforcements == 0
        assert r.metadata == {}

    def test_full_construction(self):
        r = _snapshot(
            scope_ref_id="scope-1",
            total_sessions=100,
            active_sessions=80,
            suspended_sessions=5,
            revoked_sessions=3,
            total_constraints=50,
            total_step_ups=10,
            total_revocations=3,
            total_enforcements=500,
            metadata={"region": "us"},
        )
        assert r.total_sessions == 100
        assert r.active_sessions == 80
        assert r.total_enforcements == 500

    def test_frozen(self):
        r = _snapshot()
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.snapshot_id = "x"

    def test_snapshot_id_empty_rejected(self):
        with pytest.raises(ValueError, match="snapshot_id"):
            _snapshot(snapshot_id="")

    def test_captured_at_invalid(self):
        with pytest.raises(ValueError, match="captured_at"):
            _snapshot(captured_at="bad")

    def test_total_sessions_negative_rejected(self):
        with pytest.raises(ValueError, match="total_sessions"):
            _snapshot(total_sessions=-1)

    def test_active_sessions_negative_rejected(self):
        with pytest.raises(ValueError, match="active_sessions"):
            _snapshot(active_sessions=-1)

    def test_suspended_sessions_negative_rejected(self):
        with pytest.raises(ValueError, match="suspended_sessions"):
            _snapshot(suspended_sessions=-1)

    def test_revoked_sessions_negative_rejected(self):
        with pytest.raises(ValueError, match="revoked_sessions"):
            _snapshot(revoked_sessions=-1)

    def test_total_constraints_negative_rejected(self):
        with pytest.raises(ValueError, match="total_constraints"):
            _snapshot(total_constraints=-1)

    def test_total_step_ups_negative_rejected(self):
        with pytest.raises(ValueError, match="total_step_ups"):
            _snapshot(total_step_ups=-1)

    def test_total_revocations_negative_rejected(self):
        with pytest.raises(ValueError, match="total_revocations"):
            _snapshot(total_revocations=-1)

    def test_total_enforcements_negative_rejected(self):
        with pytest.raises(ValueError, match="total_enforcements"):
            _snapshot(total_enforcements=-1)

    def test_total_sessions_bool_rejected(self):
        with pytest.raises(ValueError, match="total_sessions"):
            _snapshot(total_sessions=True)

    def test_active_sessions_bool_rejected(self):
        with pytest.raises(ValueError, match="active_sessions"):
            _snapshot(active_sessions=False)

    def test_metadata_frozen(self):
        r = _snapshot(metadata={"a": [1]})
        assert isinstance(r.metadata, MappingProxyType)
        assert isinstance(r.metadata["a"], tuple)

    def test_to_dict_returns_all_fields(self):
        d = _snapshot().to_dict()
        assert "total_sessions" in d
        assert "total_enforcements" in d
        assert "captured_at" in d

    def test_zero_values_accepted(self):
        r = _snapshot(total_sessions=0, total_enforcements=0)
        assert r.total_sessions == 0
        assert r.total_enforcements == 0


# ===================================================================
# EnforcementAuditRecord TESTS
# ===================================================================


class TestEnforcementAuditRecord:
    def test_minimal_construction(self):
        r = _audit()
        assert r.audit_id == "aud-1"
        assert r.session_id == "ses-1"
        assert r.identity_id == "id-1"

    def test_defaults(self):
        r = _audit()
        assert r.action == ""
        assert r.resource_type == ""
        assert r.decision is EnforcementDecision.DENIED
        assert r.environment_id == ""
        assert r.connector_id == ""
        assert r.metadata == {}

    def test_full_construction(self):
        r = _audit(
            action="delete",
            resource_type="bucket",
            decision=EnforcementDecision.ALLOWED,
            environment_id="staging",
            connector_id="c-2",
            metadata={"source": "api"},
        )
        assert r.decision is EnforcementDecision.ALLOWED
        assert r.action == "delete"

    def test_frozen(self):
        r = _audit()
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.audit_id = "x"

    def test_audit_id_empty_rejected(self):
        with pytest.raises(ValueError, match="audit_id"):
            _audit(audit_id="")

    def test_session_id_empty_rejected(self):
        with pytest.raises(ValueError, match="session_id"):
            _audit(session_id="")

    def test_identity_id_empty_rejected(self):
        with pytest.raises(ValueError, match="identity_id"):
            _audit(identity_id="")

    def test_decision_string_rejected(self):
        with pytest.raises(ValueError, match="decision"):
            _audit(decision="denied")

    def test_recorded_at_invalid(self):
        with pytest.raises(ValueError, match="recorded_at"):
            _audit(recorded_at="x")

    def test_metadata_frozen(self):
        r = _audit(metadata={"k": "v"})
        assert isinstance(r.metadata, MappingProxyType)

    def test_to_dict_preserves_enum(self):
        d = _audit().to_dict()
        assert d["decision"] is EnforcementDecision.DENIED


# ===================================================================
# PolicySessionBinding TESTS
# ===================================================================


class TestPolicySessionBinding:
    def test_minimal_construction(self):
        r = _binding()
        assert r.binding_id == "bind-1"
        assert r.session_id == "ses-1"
        assert r.resource_type == "connector"
        assert r.resource_id == "res-1"
        assert r.bound_at == TS

    def test_frozen(self):
        r = _binding()
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.binding_id = "x"

    def test_binding_id_empty_rejected(self):
        with pytest.raises(ValueError, match="binding_id"):
            _binding(binding_id="")

    def test_binding_id_whitespace_rejected(self):
        with pytest.raises(ValueError, match="binding_id"):
            _binding(binding_id="   ")

    def test_session_id_empty_rejected(self):
        with pytest.raises(ValueError, match="session_id"):
            _binding(session_id="")

    def test_resource_type_empty_rejected(self):
        with pytest.raises(ValueError, match="resource_type"):
            _binding(resource_type="")

    def test_resource_type_whitespace_rejected(self):
        with pytest.raises(ValueError, match="resource_type"):
            _binding(resource_type="\t")

    def test_resource_id_empty_rejected(self):
        with pytest.raises(ValueError, match="resource_id"):
            _binding(resource_id="")

    def test_bound_at_invalid(self):
        with pytest.raises(ValueError, match="bound_at"):
            _binding(bound_at="bad-date")

    def test_bound_at_empty_rejected(self):
        with pytest.raises(ValueError, match="bound_at"):
            _binding(bound_at="")

    def test_to_dict_returns_all_fields(self):
        d = _binding().to_dict()
        expected = {"binding_id", "session_id", "resource_type", "resource_id", "bound_at"}
        assert set(d.keys()) == expected

    def test_no_metadata_field(self):
        r = _binding()
        assert not hasattr(r, "metadata")


# ===================================================================
# SessionClosureReport TESTS
# ===================================================================


class TestSessionClosureReport:
    def test_minimal_construction(self):
        r = _closure()
        assert r.report_id == "rpt-1"
        assert r.session_id == "ses-1"
        assert r.identity_id == "id-1"
        assert r.closed_at == TS

    def test_defaults(self):
        r = _closure()
        assert r.total_enforcements == 0
        assert r.total_denials == 0
        assert r.total_step_ups == 0
        assert r.total_revocations == 0
        assert r.bindings_count == 0
        assert r.constraints_count == 0
        assert r.metadata == {}

    def test_full_construction(self):
        r = _closure(
            total_enforcements=100,
            total_denials=5,
            total_step_ups=3,
            total_revocations=1,
            bindings_count=10,
            constraints_count=8,
            metadata={"duration_s": 3600},
        )
        assert r.total_enforcements == 100
        assert r.total_denials == 5
        assert r.bindings_count == 10
        assert r.constraints_count == 8

    def test_frozen(self):
        r = _closure()
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.report_id = "x"

    def test_report_id_empty_rejected(self):
        with pytest.raises(ValueError, match="report_id"):
            _closure(report_id="")

    def test_session_id_empty_rejected(self):
        with pytest.raises(ValueError, match="session_id"):
            _closure(session_id="")

    def test_identity_id_empty_rejected(self):
        with pytest.raises(ValueError, match="identity_id"):
            _closure(identity_id="")

    def test_identity_id_whitespace_rejected(self):
        with pytest.raises(ValueError, match="identity_id"):
            _closure(identity_id="  ")

    def test_closed_at_invalid(self):
        with pytest.raises(ValueError, match="closed_at"):
            _closure(closed_at="not-valid")

    def test_total_enforcements_negative_rejected(self):
        with pytest.raises(ValueError, match="total_enforcements"):
            _closure(total_enforcements=-1)

    def test_total_denials_negative_rejected(self):
        with pytest.raises(ValueError, match="total_denials"):
            _closure(total_denials=-1)

    def test_total_step_ups_negative_rejected(self):
        with pytest.raises(ValueError, match="total_step_ups"):
            _closure(total_step_ups=-1)

    def test_total_revocations_negative_rejected(self):
        with pytest.raises(ValueError, match="total_revocations"):
            _closure(total_revocations=-1)

    def test_bindings_count_negative_rejected(self):
        with pytest.raises(ValueError, match="bindings_count"):
            _closure(bindings_count=-1)

    def test_constraints_count_negative_rejected(self):
        with pytest.raises(ValueError, match="constraints_count"):
            _closure(constraints_count=-1)

    def test_total_enforcements_bool_rejected(self):
        with pytest.raises(ValueError, match="total_enforcements"):
            _closure(total_enforcements=True)

    def test_bindings_count_bool_rejected(self):
        with pytest.raises(ValueError, match="bindings_count"):
            _closure(bindings_count=False)

    def test_metadata_frozen(self):
        r = _closure(metadata={"k": {"nested": "v"}})
        assert isinstance(r.metadata, MappingProxyType)
        assert isinstance(r.metadata["k"], MappingProxyType)

    def test_to_dict_returns_all_fields(self):
        d = _closure().to_dict()
        field_names = {f.name for f in dataclasses.fields(SessionClosureReport)}
        assert set(d.keys()) == field_names

    def test_zero_counts_accepted(self):
        r = _closure(
            total_enforcements=0,
            total_denials=0,
            total_step_ups=0,
            total_revocations=0,
            bindings_count=0,
            constraints_count=0,
        )
        assert r.total_enforcements == 0
        assert r.constraints_count == 0


# ===================================================================
# CROSS-CUTTING / EDGE-CASE TESTS
# ===================================================================


class TestFreezeValueBehavior:
    """Tests for freeze_value via metadata fields across dataclasses."""

    def test_empty_dict_becomes_empty_mapping_proxy(self):
        r = _session(metadata={})
        assert isinstance(r.metadata, MappingProxyType)
        assert len(r.metadata) == 0

    def test_nested_dict_frozen_recursively(self):
        r = _enforcement_event(metadata={"a": {"b": {"c": 1}}})
        assert isinstance(r.metadata["a"], MappingProxyType)
        assert isinstance(r.metadata["a"]["b"], MappingProxyType)
        assert r.metadata["a"]["b"]["c"] == 1

    def test_list_in_metadata_becomes_tuple(self):
        r = _revocation(metadata={"items": [10, 20, 30]})
        assert r.metadata["items"] == (10, 20, 30)
        assert isinstance(r.metadata["items"], tuple)

    def test_nested_list_in_dict_becomes_tuple(self):
        r = _audit(metadata={"outer": {"inner": [1, 2]}})
        assert isinstance(r.metadata["outer"]["inner"], tuple)

    def test_metadata_mapping_proxy_is_immutable(self):
        r = _session(metadata={"key": "val"})
        with pytest.raises(TypeError):
            r.metadata["key"] = "new"

    def test_metadata_mapping_proxy_no_new_keys(self):
        r = _session(metadata={})
        with pytest.raises(TypeError):
            r.metadata["new"] = "val"


class TestToDictSerialization:
    """Tests for to_dict behavior across dataclasses."""

    def test_session_to_dict_tuples_to_lists(self):
        r = _session(metadata={"tags": [1, 2, 3]})
        d = r.to_dict()
        assert isinstance(d["metadata"]["tags"], list)
        assert d["metadata"]["tags"] == [1, 2, 3]

    def test_enforcement_event_to_dict_enum_not_string(self):
        d = _enforcement_event(decision=EnforcementDecision.STEP_UP_REQUIRED).to_dict()
        assert d["decision"] is EnforcementDecision.STEP_UP_REQUIRED
        assert not isinstance(d["decision"], str)

    def test_revocation_to_dict_enum_not_string(self):
        d = _revocation(reason=RevocationReason.COMPLIANCE_FAILURE).to_dict()
        assert d["reason"] is RevocationReason.COMPLIANCE_FAILURE

    def test_session_to_dict_all_enum_fields_preserved(self):
        r = _session(
            kind=SessionKind.CAMPAIGN,
            status=SessionStatus.REVOKED,
            privilege_level=PrivilegeLevel.EMERGENCY,
        )
        d = r.to_dict()
        assert isinstance(d["kind"], SessionKind)
        assert isinstance(d["status"], SessionStatus)
        assert isinstance(d["privilege_level"], PrivilegeLevel)

    def test_constraint_to_dict_completeness(self):
        d = _constraint().to_dict()
        field_names = {f.name for f in dataclasses.fields(SessionConstraint)}
        assert set(d.keys()) == field_names

    def test_elev_request_to_dict_metadata_thawed(self):
        r = _elev_request(metadata={"x": [1]})
        d = r.to_dict()
        assert isinstance(d["metadata"], dict)
        assert isinstance(d["metadata"]["x"], list)

    def test_snapshot_to_dict_int_fields_preserved(self):
        r = _snapshot(total_sessions=42, active_sessions=30)
        d = r.to_dict()
        assert d["total_sessions"] == 42
        assert d["active_sessions"] == 30


class TestDatetimeValidation:
    """Tests for datetime validation across dataclasses."""

    def test_z_suffix_accepted_for_session(self):
        r = _session(opened_at="2025-06-01T12:00:00Z")
        assert r.opened_at == "2025-06-01T12:00:00Z"

    def test_z_suffix_accepted_for_constraint(self):
        r = _constraint(created_at="2025-06-01T12:00:00Z")
        assert r.created_at == "2025-06-01T12:00:00Z"

    def test_naive_datetime_accepted(self):
        r = _session(opened_at="2025-06-01T12:00:00")
        assert r.opened_at == "2025-06-01T12:00:00"

    def test_random_string_rejected(self):
        with pytest.raises(ValueError):
            _constraint(created_at="hello-world")

    def test_numeric_string_rejected(self):
        with pytest.raises(ValueError):
            _enforcement_event(evaluated_at="12345")


class TestEdgeCases:
    """Miscellaneous edge-case tests."""

    def test_session_all_session_kinds(self):
        for kind in SessionKind:
            r = _session(kind=kind)
            assert r.kind is kind

    def test_session_all_statuses(self):
        for status in SessionStatus:
            r = _session(status=status)
            assert r.status is status

    def test_session_all_privilege_levels(self):
        for level in PrivilegeLevel:
            r = _session(privilege_level=level)
            assert r.privilege_level is level

    def test_enforcement_event_all_decisions(self):
        for decision in EnforcementDecision:
            r = _enforcement_event(decision=decision)
            assert r.decision is decision

    def test_elev_decision_all_step_up_statuses(self):
        for status in StepUpStatus:
            r = _elev_decision(status=status)
            assert r.status is status

    def test_snapshot_large_values(self):
        r = _snapshot(total_sessions=999_999_999, total_enforcements=999_999_999)
        assert r.total_sessions == 999_999_999

    def test_closure_large_values(self):
        r = _closure(total_enforcements=1_000_000, constraints_count=500_000)
        assert r.total_enforcements == 1_000_000

    def test_binding_different_resource_types(self):
        for rt in ("connector", "campaign", "environment", "tenant"):
            r = _binding(resource_type=rt)
            assert r.resource_type == rt

    def test_session_metadata_with_none_value(self):
        r = _session(metadata={"key": None})
        assert r.metadata["key"] is None

    def test_enforcement_event_metadata_empty_list(self):
        r = _enforcement_event(metadata={"items": []})
        assert r.metadata["items"] == ()

    def test_session_is_dataclass(self):
        assert dataclasses.is_dataclass(SessionRecord)

    def test_constraint_is_dataclass(self):
        assert dataclasses.is_dataclass(SessionConstraint)

    def test_snapshot_is_dataclass(self):
        assert dataclasses.is_dataclass(SessionSnapshot)

    def test_binding_is_dataclass(self):
        assert dataclasses.is_dataclass(PolicySessionBinding)

    def test_closure_is_dataclass(self):
        assert dataclasses.is_dataclass(SessionClosureReport)

    def test_session_slots(self):
        assert hasattr(SessionRecord, "__slots__")

    def test_binding_slots(self):
        assert hasattr(PolicySessionBinding, "__slots__")
