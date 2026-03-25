"""Comprehensive tests for remediation runtime contracts.

Covers all 6 enums and 10 dataclasses in
mcoi_runtime.contracts.remediation_runtime.
"""

from __future__ import annotations

from types import MappingProxyType

import pytest

from mcoi_runtime.contracts.remediation_runtime import (
    CorrectiveAction,
    PreventiveAction,
    RemediationAssignment,
    RemediationClosureReport,
    RemediationDecision,
    RemediationDisposition,
    RemediationPriority,
    RemediationRecord,
    RemediationSnapshot,
    RemediationStatus,
    RemediationType,
    RemediationViolation,
    ReopenRecord,
    VerificationRecord,
    RemediationVerificationStatus,
    PreventiveActionStatus,
)

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

TS = "2025-06-01T12:00:00+00:00"
TS2 = "2025-07-15T09:30:00+00:00"


# ===================================================================
# Enum tests
# ===================================================================


class TestRemediationStatus:
    def test_member_count(self):
        assert len(RemediationStatus) == 7

    def test_names(self):
        expected = {
            "OPEN", "IN_PROGRESS", "PENDING_VERIFICATION",
            "VERIFIED", "CLOSED", "REOPENED", "ESCALATED",
        }
        assert {m.name for m in RemediationStatus} == expected

    def test_open_value(self):
        assert RemediationStatus.OPEN.value == "open"

    def test_in_progress_value(self):
        assert RemediationStatus.IN_PROGRESS.value == "in_progress"

    def test_pending_verification_value(self):
        assert RemediationStatus.PENDING_VERIFICATION.value == "pending_verification"

    def test_verified_value(self):
        assert RemediationStatus.VERIFIED.value == "verified"

    def test_closed_value(self):
        assert RemediationStatus.CLOSED.value == "closed"

    def test_reopened_value(self):
        assert RemediationStatus.REOPENED.value == "reopened"

    def test_escalated_value(self):
        assert RemediationStatus.ESCALATED.value == "escalated"


class TestRemediationPriority:
    def test_member_count(self):
        assert len(RemediationPriority) == 4

    def test_names(self):
        assert {m.name for m in RemediationPriority} == {"LOW", "MEDIUM", "HIGH", "CRITICAL"}

    def test_low_value(self):
        assert RemediationPriority.LOW.value == "low"

    def test_medium_value(self):
        assert RemediationPriority.MEDIUM.value == "medium"

    def test_high_value(self):
        assert RemediationPriority.HIGH.value == "high"

    def test_critical_value(self):
        assert RemediationPriority.CRITICAL.value == "critical"


class TestRemediationType:
    def test_member_count(self):
        assert len(RemediationType) == 4

    def test_names(self):
        assert {m.name for m in RemediationType} == {
            "CORRECTIVE", "PREVENTIVE", "DETECTIVE", "COMPENSATING",
        }

    def test_corrective_value(self):
        assert RemediationType.CORRECTIVE.value == "corrective"

    def test_preventive_value(self):
        assert RemediationType.PREVENTIVE.value == "preventive"

    def test_detective_value(self):
        assert RemediationType.DETECTIVE.value == "detective"

    def test_compensating_value(self):
        assert RemediationType.COMPENSATING.value == "compensating"


class TestRemediationVerificationStatus:
    def test_member_count(self):
        assert len(RemediationVerificationStatus) == 4

    def test_names(self):
        assert {m.name for m in RemediationVerificationStatus} == {
            "PENDING", "PASSED", "FAILED", "WAIVED",
        }

    def test_pending_value(self):
        assert RemediationVerificationStatus.PENDING.value == "pending"

    def test_passed_value(self):
        assert RemediationVerificationStatus.PASSED.value == "passed"

    def test_failed_value(self):
        assert RemediationVerificationStatus.FAILED.value == "failed"

    def test_waived_value(self):
        assert RemediationVerificationStatus.WAIVED.value == "waived"


class TestPreventiveActionStatus:
    def test_member_count(self):
        assert len(PreventiveActionStatus) == 5

    def test_names(self):
        assert {m.name for m in PreventiveActionStatus} == {
            "PROPOSED", "APPROVED", "IMPLEMENTED", "VERIFIED", "REJECTED",
        }

    def test_proposed_value(self):
        assert PreventiveActionStatus.PROPOSED.value == "proposed"

    def test_approved_value(self):
        assert PreventiveActionStatus.APPROVED.value == "approved"

    def test_implemented_value(self):
        assert PreventiveActionStatus.IMPLEMENTED.value == "implemented"

    def test_verified_value(self):
        assert PreventiveActionStatus.VERIFIED.value == "verified"

    def test_rejected_value(self):
        assert PreventiveActionStatus.REJECTED.value == "rejected"


class TestRemediationDisposition:
    def test_member_count(self):
        assert len(RemediationDisposition) == 5

    def test_names(self):
        assert {m.name for m in RemediationDisposition} == {
            "RESOLVED", "ACCEPTED_RISK", "TRANSFERRED", "ESCALATED", "INEFFECTIVE",
        }

    def test_resolved_value(self):
        assert RemediationDisposition.RESOLVED.value == "resolved"

    def test_accepted_risk_value(self):
        assert RemediationDisposition.ACCEPTED_RISK.value == "accepted_risk"

    def test_transferred_value(self):
        assert RemediationDisposition.TRANSFERRED.value == "transferred"

    def test_escalated_value(self):
        assert RemediationDisposition.ESCALATED.value == "escalated"

    def test_ineffective_value(self):
        assert RemediationDisposition.INEFFECTIVE.value == "ineffective"


# ===================================================================
# Fail-closed default tests
# ===================================================================


class TestFailClosedDefaults:
    def test_remediation_status_defaults_open(self):
        r = RemediationRecord(
            remediation_id="r1", tenant_id="t1", title="fix",
            owner_id="o1", created_at=TS,
        )
        assert r.status is RemediationStatus.OPEN

    def test_verification_status_defaults_pending(self):
        v = VerificationRecord(
            verification_id="v1", remediation_id="r1",
            verifier_id="u1", verified_at=TS,
        )
        assert v.status is RemediationVerificationStatus.PENDING

    def test_preventive_action_status_defaults_proposed(self):
        p = PreventiveAction(
            action_id="a1", remediation_id="r1", title="prevent",
            target_type="policy", target_id="pol1", owner_id="o1",
            created_at=TS,
        )
        assert p.status is PreventiveActionStatus.PROPOSED

    def test_remediation_disposition_defaults_ineffective_decision(self):
        d = RemediationDecision(
            decision_id="d1", remediation_id="r1",
            decided_by="u1", decided_at=TS,
        )
        assert d.disposition is RemediationDisposition.INEFFECTIVE

    def test_remediation_disposition_defaults_ineffective_closure(self):
        c = RemediationClosureReport(
            report_id="rpt1", remediation_id="r1",
            tenant_id="t1", closed_at=TS,
        )
        assert c.disposition is RemediationDisposition.INEFFECTIVE


# ===================================================================
# RemediationRecord tests
# ===================================================================


class TestRemediationRecord:
    def _make(self, **overrides):
        defaults = dict(
            remediation_id="rem-1", tenant_id="t-1",
            title="Fix the issue", owner_id="owner-1",
            created_at=TS,
        )
        defaults.update(overrides)
        return RemediationRecord(**defaults)

    def test_valid_construction(self):
        r = self._make()
        assert r.remediation_id == "rem-1"
        assert r.tenant_id == "t-1"
        assert r.title == "Fix the issue"
        assert r.owner_id == "owner-1"
        assert r.created_at == TS
        assert r.remediation_type is RemediationType.CORRECTIVE
        assert r.priority is RemediationPriority.MEDIUM
        assert r.status is RemediationStatus.OPEN

    def test_empty_remediation_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(remediation_id="")

    def test_whitespace_remediation_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(remediation_id="   ")

    def test_empty_tenant_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(tenant_id="")

    def test_empty_title_rejected(self):
        with pytest.raises(ValueError):
            self._make(title="")

    def test_empty_owner_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(owner_id="")

    def test_invalid_remediation_type_rejected(self):
        with pytest.raises(ValueError):
            self._make(remediation_type="corrective")

    def test_invalid_priority_rejected(self):
        with pytest.raises(ValueError):
            self._make(priority="high")

    def test_invalid_status_rejected(self):
        with pytest.raises(ValueError):
            self._make(status="open")

    def test_garbage_datetime_rejected(self):
        with pytest.raises(ValueError):
            self._make(created_at="not-a-date")

    def test_numeric_datetime_rejected(self):
        with pytest.raises(ValueError):
            self._make(created_at="12345")

    def test_metadata_frozen(self):
        r = self._make(metadata={"key": "val"})
        assert isinstance(r.metadata, MappingProxyType)
        assert r.metadata["key"] == "val"

    def test_nested_metadata_frozen(self):
        r = self._make(metadata={"nested": [1, 2]})
        assert isinstance(r.metadata["nested"], tuple)

    def test_immutability(self):
        r = self._make()
        with pytest.raises(AttributeError):
            r.title = "changed"  # type: ignore[misc]

    def test_to_dict(self):
        r = self._make()
        d = r.to_dict()
        assert d["remediation_id"] == "rem-1"
        assert d["status"] is RemediationStatus.OPEN
        assert d["remediation_type"] is RemediationType.CORRECTIVE
        assert isinstance(d, dict)

    def test_to_dict_preserves_enum_objects(self):
        r = self._make(
            remediation_type=RemediationType.DETECTIVE,
            priority=RemediationPriority.CRITICAL,
            status=RemediationStatus.ESCALATED,
        )
        d = r.to_dict()
        assert d["remediation_type"] is RemediationType.DETECTIVE
        assert d["priority"] is RemediationPriority.CRITICAL
        assert d["status"] is RemediationStatus.ESCALATED

    def test_all_status_values_accepted(self):
        for s in RemediationStatus:
            r = self._make(status=s)
            assert r.status is s


# ===================================================================
# CorrectiveAction tests
# ===================================================================


class TestCorrectiveAction:
    def _make(self, **overrides):
        defaults = dict(
            action_id="act-1", remediation_id="rem-1",
            title="Replace component", owner_id="o-1",
            created_at=TS,
        )
        defaults.update(overrides)
        return CorrectiveAction(**defaults)

    def test_valid_construction(self):
        a = self._make()
        assert a.action_id == "act-1"
        assert a.status is RemediationStatus.OPEN

    def test_empty_action_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(action_id="")

    def test_whitespace_action_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(action_id="  \t  ")

    def test_empty_remediation_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(remediation_id="")

    def test_empty_title_rejected(self):
        with pytest.raises(ValueError):
            self._make(title="")

    def test_empty_owner_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(owner_id="")

    def test_invalid_status_rejected(self):
        with pytest.raises(ValueError):
            self._make(status="open")

    def test_garbage_datetime_rejected(self):
        with pytest.raises(ValueError):
            self._make(created_at="yesterday")

    def test_numeric_datetime_rejected(self):
        with pytest.raises(ValueError):
            self._make(created_at="99999")

    def test_metadata_frozen(self):
        a = self._make(metadata={"k": "v"})
        assert isinstance(a.metadata, MappingProxyType)

    def test_immutability(self):
        a = self._make()
        with pytest.raises(AttributeError):
            a.action_id = "new"  # type: ignore[misc]

    def test_to_dict(self):
        a = self._make()
        d = a.to_dict()
        assert d["action_id"] == "act-1"
        assert d["status"] is RemediationStatus.OPEN

    def test_to_dict_preserves_enum(self):
        a = self._make(status=RemediationStatus.CLOSED)
        d = a.to_dict()
        assert d["status"] is RemediationStatus.CLOSED


# ===================================================================
# PreventiveAction tests
# ===================================================================


class TestPreventiveAction:
    def _make(self, **overrides):
        defaults = dict(
            action_id="pa-1", remediation_id="rem-1",
            title="Add monitoring", target_type="system",
            target_id="sys-1", owner_id="o-1", created_at=TS,
        )
        defaults.update(overrides)
        return PreventiveAction(**defaults)

    def test_valid_construction(self):
        p = self._make()
        assert p.action_id == "pa-1"
        assert p.status is PreventiveActionStatus.PROPOSED

    def test_empty_action_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(action_id="")

    def test_empty_remediation_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(remediation_id="")

    def test_empty_title_rejected(self):
        with pytest.raises(ValueError):
            self._make(title="")

    def test_empty_target_type_rejected(self):
        with pytest.raises(ValueError):
            self._make(target_type="")

    def test_empty_target_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(target_id="")

    def test_empty_owner_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(owner_id="")

    def test_invalid_status_rejected(self):
        with pytest.raises(ValueError):
            self._make(status="proposed")

    def test_garbage_datetime_rejected(self):
        with pytest.raises(ValueError):
            self._make(created_at="nope")

    def test_numeric_datetime_rejected(self):
        with pytest.raises(ValueError):
            self._make(created_at="42")

    def test_metadata_frozen(self):
        p = self._make(metadata={"a": {"b": [1]}})
        assert isinstance(p.metadata, MappingProxyType)
        assert isinstance(p.metadata["a"], MappingProxyType)
        assert isinstance(p.metadata["a"]["b"], tuple)

    def test_immutability(self):
        p = self._make()
        with pytest.raises(AttributeError):
            p.title = "x"  # type: ignore[misc]

    def test_to_dict(self):
        p = self._make(status=PreventiveActionStatus.VERIFIED)
        d = p.to_dict()
        assert d["status"] is PreventiveActionStatus.VERIFIED
        assert d["action_id"] == "pa-1"


# ===================================================================
# RemediationAssignment tests
# ===================================================================


class TestRemediationAssignment:
    def _make(self, **overrides):
        defaults = dict(
            assignment_id="asg-1", remediation_id="rem-1",
            assignee_id="user-1", role="lead",
            assigned_at=TS,
        )
        defaults.update(overrides)
        return RemediationAssignment(**defaults)

    def test_valid_construction(self):
        a = self._make()
        assert a.assignment_id == "asg-1"
        assert a.role == "lead"

    def test_empty_assignment_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(assignment_id="")

    def test_empty_remediation_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(remediation_id="")

    def test_empty_assignee_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(assignee_id="")

    def test_whitespace_assignee_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(assignee_id="  ")

    def test_empty_role_rejected(self):
        with pytest.raises(ValueError):
            self._make(role="")

    def test_garbage_datetime_rejected(self):
        with pytest.raises(ValueError):
            self._make(assigned_at="garbage")

    def test_numeric_datetime_rejected(self):
        with pytest.raises(ValueError):
            self._make(assigned_at="000")

    def test_metadata_frozen(self):
        a = self._make(metadata={"x": "y"})
        assert isinstance(a.metadata, MappingProxyType)

    def test_immutability(self):
        a = self._make()
        with pytest.raises(AttributeError):
            a.role = "other"  # type: ignore[misc]

    def test_to_dict(self):
        a = self._make()
        d = a.to_dict()
        assert d["assignment_id"] == "asg-1"
        assert isinstance(d, dict)


# ===================================================================
# VerificationRecord tests
# ===================================================================


class TestVerificationRecord:
    def _make(self, **overrides):
        defaults = dict(
            verification_id="ver-1", remediation_id="rem-1",
            verifier_id="user-1", verified_at=TS,
        )
        defaults.update(overrides)
        return VerificationRecord(**defaults)

    def test_valid_construction(self):
        v = self._make()
        assert v.verification_id == "ver-1"
        assert v.status is RemediationVerificationStatus.PENDING

    def test_explicit_status(self):
        v = self._make(status=RemediationVerificationStatus.PASSED)
        assert v.status is RemediationVerificationStatus.PASSED

    def test_empty_verification_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(verification_id="")

    def test_empty_remediation_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(remediation_id="")

    def test_empty_verifier_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(verifier_id="")

    def test_whitespace_verifier_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(verifier_id="\t\n")

    def test_invalid_status_rejected(self):
        with pytest.raises(ValueError):
            self._make(status="pending")

    def test_garbage_datetime_rejected(self):
        with pytest.raises(ValueError):
            self._make(verified_at="bad")

    def test_numeric_datetime_rejected(self):
        with pytest.raises(ValueError):
            self._make(verified_at="7777")

    def test_metadata_frozen(self):
        v = self._make(metadata={"evidence": [1, 2, 3]})
        assert isinstance(v.metadata, MappingProxyType)
        assert isinstance(v.metadata["evidence"], tuple)
        assert v.metadata["evidence"] == (1, 2, 3)

    def test_immutability(self):
        v = self._make()
        with pytest.raises(AttributeError):
            v.status = RemediationVerificationStatus.FAILED  # type: ignore[misc]

    def test_to_dict(self):
        v = self._make(status=RemediationVerificationStatus.WAIVED)
        d = v.to_dict()
        assert d["status"] is RemediationVerificationStatus.WAIVED
        assert d["verification_id"] == "ver-1"


# ===================================================================
# ReopenRecord tests
# ===================================================================


class TestReopenRecord:
    def _make(self, **overrides):
        defaults = dict(
            reopen_id="reo-1", remediation_id="rem-1",
            reopened_by="user-1", reopened_at=TS,
        )
        defaults.update(overrides)
        return ReopenRecord(**defaults)

    def test_valid_construction(self):
        r = self._make()
        assert r.reopen_id == "reo-1"

    def test_empty_reopen_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(reopen_id="")

    def test_empty_remediation_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(remediation_id="")

    def test_empty_reopened_by_rejected(self):
        with pytest.raises(ValueError):
            self._make(reopened_by="")

    def test_whitespace_reopened_by_rejected(self):
        with pytest.raises(ValueError):
            self._make(reopened_by="   ")

    def test_garbage_datetime_rejected(self):
        with pytest.raises(ValueError):
            self._make(reopened_at="nah")

    def test_numeric_datetime_rejected(self):
        with pytest.raises(ValueError):
            self._make(reopened_at="111")

    def test_metadata_frozen(self):
        r = self._make(metadata={"k": "v"})
        assert isinstance(r.metadata, MappingProxyType)

    def test_immutability(self):
        r = self._make()
        with pytest.raises(AttributeError):
            r.reason = "new"  # type: ignore[misc]

    def test_to_dict(self):
        r = self._make(reason="failed verification")
        d = r.to_dict()
        assert d["reopen_id"] == "reo-1"
        assert d["reason"] == "failed verification"


# ===================================================================
# RemediationDecision tests
# ===================================================================


class TestRemediationDecision:
    def _make(self, **overrides):
        defaults = dict(
            decision_id="dec-1", remediation_id="rem-1",
            decided_by="user-1", decided_at=TS,
        )
        defaults.update(overrides)
        return RemediationDecision(**defaults)

    def test_valid_construction(self):
        d = self._make()
        assert d.decision_id == "dec-1"
        assert d.disposition is RemediationDisposition.INEFFECTIVE

    def test_explicit_disposition(self):
        d = self._make(disposition=RemediationDisposition.RESOLVED)
        assert d.disposition is RemediationDisposition.RESOLVED

    def test_empty_decision_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(decision_id="")

    def test_empty_remediation_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(remediation_id="")

    def test_empty_decided_by_rejected(self):
        with pytest.raises(ValueError):
            self._make(decided_by="")

    def test_invalid_disposition_rejected(self):
        with pytest.raises(ValueError):
            self._make(disposition="resolved")

    def test_garbage_datetime_rejected(self):
        with pytest.raises(ValueError):
            self._make(decided_at="nope")

    def test_numeric_datetime_rejected(self):
        with pytest.raises(ValueError):
            self._make(decided_at="555")

    def test_metadata_frozen(self):
        d = self._make(metadata={"notes": "approved"})
        assert isinstance(d.metadata, MappingProxyType)

    def test_immutability(self):
        d = self._make()
        with pytest.raises(AttributeError):
            d.disposition = RemediationDisposition.RESOLVED  # type: ignore[misc]

    def test_to_dict(self):
        d = self._make(disposition=RemediationDisposition.ACCEPTED_RISK)
        out = d.to_dict()
        assert out["disposition"] is RemediationDisposition.ACCEPTED_RISK
        assert out["decision_id"] == "dec-1"

    def test_to_dict_preserves_enum(self):
        d = self._make(disposition=RemediationDisposition.TRANSFERRED)
        out = d.to_dict()
        assert out["disposition"] is RemediationDisposition.TRANSFERRED


# ===================================================================
# RemediationSnapshot tests
# ===================================================================


class TestRemediationSnapshot:
    def _make(self, **overrides):
        defaults = dict(
            snapshot_id="snap-1", captured_at=TS,
        )
        defaults.update(overrides)
        return RemediationSnapshot(**defaults)

    def test_valid_construction(self):
        s = self._make()
        assert s.snapshot_id == "snap-1"
        assert s.total_remediations == 0
        assert s.open_remediations == 0

    def test_with_counts(self):
        s = self._make(
            total_remediations=10, open_remediations=3,
            total_corrective=5, total_preventive=2,
            total_verifications=4, total_reopens=1,
            total_decisions=2, total_violations=1,
        )
        assert s.total_remediations == 10
        assert s.open_remediations == 3
        assert s.total_corrective == 5
        assert s.total_preventive == 2
        assert s.total_verifications == 4
        assert s.total_reopens == 1
        assert s.total_decisions == 2
        assert s.total_violations == 1

    def test_empty_snapshot_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(snapshot_id="")

    def test_negative_total_remediations_rejected(self):
        with pytest.raises(ValueError):
            self._make(total_remediations=-1)

    def test_negative_open_remediations_rejected(self):
        with pytest.raises(ValueError):
            self._make(open_remediations=-1)

    def test_negative_total_corrective_rejected(self):
        with pytest.raises(ValueError):
            self._make(total_corrective=-1)

    def test_negative_total_preventive_rejected(self):
        with pytest.raises(ValueError):
            self._make(total_preventive=-1)

    def test_negative_total_verifications_rejected(self):
        with pytest.raises(ValueError):
            self._make(total_verifications=-1)

    def test_negative_total_reopens_rejected(self):
        with pytest.raises(ValueError):
            self._make(total_reopens=-1)

    def test_negative_total_decisions_rejected(self):
        with pytest.raises(ValueError):
            self._make(total_decisions=-1)

    def test_negative_total_violations_rejected(self):
        with pytest.raises(ValueError):
            self._make(total_violations=-1)

    def test_bool_total_remediations_rejected(self):
        with pytest.raises(ValueError):
            self._make(total_remediations=True)

    def test_float_total_remediations_rejected(self):
        with pytest.raises(ValueError):
            self._make(total_remediations=1.5)

    def test_garbage_datetime_rejected(self):
        with pytest.raises(ValueError):
            self._make(captured_at="oops")

    def test_numeric_datetime_rejected(self):
        with pytest.raises(ValueError):
            self._make(captured_at="9876")

    def test_metadata_frozen(self):
        s = self._make(metadata={"region": "us-east-1"})
        assert isinstance(s.metadata, MappingProxyType)

    def test_immutability(self):
        s = self._make()
        with pytest.raises(AttributeError):
            s.total_remediations = 99  # type: ignore[misc]

    def test_to_dict(self):
        s = self._make(total_remediations=5)
        d = s.to_dict()
        assert d["snapshot_id"] == "snap-1"
        assert d["total_remediations"] == 5


# ===================================================================
# RemediationViolation tests
# ===================================================================


class TestRemediationViolation:
    def _make(self, **overrides):
        defaults = dict(
            violation_id="viol-1", remediation_id="rem-1",
            tenant_id="t-1", operation="close_without_verify",
            detected_at=TS,
        )
        defaults.update(overrides)
        return RemediationViolation(**defaults)

    def test_valid_construction(self):
        v = self._make()
        assert v.violation_id == "viol-1"
        assert v.operation == "close_without_verify"

    def test_empty_violation_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(violation_id="")

    def test_empty_remediation_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(remediation_id="")

    def test_empty_tenant_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(tenant_id="")

    def test_whitespace_tenant_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(tenant_id="\n\t")

    def test_empty_operation_rejected(self):
        with pytest.raises(ValueError):
            self._make(operation="")

    def test_garbage_datetime_rejected(self):
        with pytest.raises(ValueError):
            self._make(detected_at="when")

    def test_numeric_datetime_rejected(self):
        with pytest.raises(ValueError):
            self._make(detected_at="321")

    def test_metadata_frozen(self):
        v = self._make(metadata={"severity": "high"})
        assert isinstance(v.metadata, MappingProxyType)

    def test_immutability(self):
        v = self._make()
        with pytest.raises(AttributeError):
            v.operation = "other"  # type: ignore[misc]

    def test_to_dict(self):
        v = self._make()
        d = v.to_dict()
        assert d["violation_id"] == "viol-1"
        assert d["operation"] == "close_without_verify"


# ===================================================================
# RemediationClosureReport tests
# ===================================================================


class TestRemediationClosureReport:
    def _make(self, **overrides):
        defaults = dict(
            report_id="rpt-1", remediation_id="rem-1",
            tenant_id="t-1", closed_at=TS,
        )
        defaults.update(overrides)
        return RemediationClosureReport(**defaults)

    def test_valid_construction(self):
        c = self._make()
        assert c.report_id == "rpt-1"
        assert c.disposition is RemediationDisposition.INEFFECTIVE
        assert c.total_corrective == 0

    def test_with_counts(self):
        c = self._make(
            total_corrective=3, total_preventive=2,
            total_verifications=5, total_reopens=1,
            total_violations=0,
        )
        assert c.total_corrective == 3
        assert c.total_preventive == 2
        assert c.total_verifications == 5
        assert c.total_reopens == 1
        assert c.total_violations == 0

    def test_explicit_disposition(self):
        c = self._make(disposition=RemediationDisposition.RESOLVED)
        assert c.disposition is RemediationDisposition.RESOLVED

    def test_empty_report_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(report_id="")

    def test_empty_remediation_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(remediation_id="")

    def test_empty_tenant_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(tenant_id="")

    def test_whitespace_report_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(report_id="   ")

    def test_invalid_disposition_rejected(self):
        with pytest.raises(ValueError):
            self._make(disposition="resolved")

    def test_negative_total_corrective_rejected(self):
        with pytest.raises(ValueError):
            self._make(total_corrective=-1)

    def test_negative_total_preventive_rejected(self):
        with pytest.raises(ValueError):
            self._make(total_preventive=-1)

    def test_negative_total_verifications_rejected(self):
        with pytest.raises(ValueError):
            self._make(total_verifications=-1)

    def test_negative_total_reopens_rejected(self):
        with pytest.raises(ValueError):
            self._make(total_reopens=-1)

    def test_negative_total_violations_rejected(self):
        with pytest.raises(ValueError):
            self._make(total_violations=-1)

    def test_bool_total_corrective_rejected(self):
        with pytest.raises(ValueError):
            self._make(total_corrective=False)

    def test_garbage_datetime_rejected(self):
        with pytest.raises(ValueError):
            self._make(closed_at="never")

    def test_numeric_datetime_rejected(self):
        with pytest.raises(ValueError):
            self._make(closed_at="8888")

    def test_metadata_frozen(self):
        c = self._make(metadata={"summary": {"k": "v"}})
        assert isinstance(c.metadata, MappingProxyType)
        assert isinstance(c.metadata["summary"], MappingProxyType)

    def test_immutability(self):
        c = self._make()
        with pytest.raises(AttributeError):
            c.report_id = "new"  # type: ignore[misc]

    def test_to_dict(self):
        c = self._make(disposition=RemediationDisposition.ESCALATED)
        d = c.to_dict()
        assert d["report_id"] == "rpt-1"
        assert d["disposition"] is RemediationDisposition.ESCALATED

    def test_to_dict_preserves_enum(self):
        c = self._make(disposition=RemediationDisposition.ACCEPTED_RISK)
        d = c.to_dict()
        assert d["disposition"] is RemediationDisposition.ACCEPTED_RISK


# ===================================================================
# Cross-cutting immutability
# ===================================================================


class TestCrossCuttingImmutability:
    """Every dataclass must reject attribute mutation."""

    def test_remediation_record_frozen(self):
        r = RemediationRecord(
            remediation_id="r1", tenant_id="t1", title="t",
            owner_id="o1", created_at=TS,
        )
        with pytest.raises(AttributeError):
            r.remediation_id = "x"  # type: ignore[misc]

    def test_corrective_action_frozen(self):
        a = CorrectiveAction(
            action_id="a1", remediation_id="r1", title="t",
            owner_id="o1", created_at=TS,
        )
        with pytest.raises(AttributeError):
            a.remediation_id = "x"  # type: ignore[misc]

    def test_preventive_action_frozen(self):
        p = PreventiveAction(
            action_id="a1", remediation_id="r1", title="t",
            target_type="pol", target_id="p1", owner_id="o1",
            created_at=TS,
        )
        with pytest.raises(AttributeError):
            p.action_id = "x"  # type: ignore[misc]

    def test_assignment_frozen(self):
        a = RemediationAssignment(
            assignment_id="a1", remediation_id="r1",
            assignee_id="u1", role="r", assigned_at=TS,
        )
        with pytest.raises(AttributeError):
            a.assignment_id = "x"  # type: ignore[misc]

    def test_verification_frozen(self):
        v = VerificationRecord(
            verification_id="v1", remediation_id="r1",
            verifier_id="u1", verified_at=TS,
        )
        with pytest.raises(AttributeError):
            v.verification_id = "x"  # type: ignore[misc]

    def test_reopen_frozen(self):
        r = ReopenRecord(
            reopen_id="r1", remediation_id="rem1",
            reopened_by="u1", reopened_at=TS,
        )
        with pytest.raises(AttributeError):
            r.reopen_id = "x"  # type: ignore[misc]

    def test_decision_frozen(self):
        d = RemediationDecision(
            decision_id="d1", remediation_id="r1",
            decided_by="u1", decided_at=TS,
        )
        with pytest.raises(AttributeError):
            d.decision_id = "x"  # type: ignore[misc]

    def test_snapshot_frozen(self):
        s = RemediationSnapshot(snapshot_id="s1", captured_at=TS)
        with pytest.raises(AttributeError):
            s.snapshot_id = "x"  # type: ignore[misc]

    def test_violation_frozen(self):
        v = RemediationViolation(
            violation_id="v1", remediation_id="r1",
            tenant_id="t1", operation="op", detected_at=TS,
        )
        with pytest.raises(AttributeError):
            v.violation_id = "x"  # type: ignore[misc]

    def test_closure_report_frozen(self):
        c = RemediationClosureReport(
            report_id="rpt1", remediation_id="r1",
            tenant_id="t1", closed_at=TS,
        )
        with pytest.raises(AttributeError):
            c.report_id = "x"  # type: ignore[misc]


# ===================================================================
# Cross-cutting metadata freeze semantics
# ===================================================================


class TestMetadataFreezeSemantics:
    """Verify freeze_value produces tuples and MappingProxyType."""

    def test_list_in_metadata_becomes_tuple(self):
        r = RemediationRecord(
            remediation_id="r1", tenant_id="t1", title="t",
            owner_id="o1", created_at=TS,
            metadata={"items": [1, 2, 3]},
        )
        assert isinstance(r.metadata["items"], tuple)
        assert r.metadata["items"] == (1, 2, 3)

    def test_dict_in_metadata_becomes_mapping_proxy(self):
        r = RemediationRecord(
            remediation_id="r1", tenant_id="t1", title="t",
            owner_id="o1", created_at=TS,
            metadata={"nested": {"a": 1}},
        )
        assert isinstance(r.metadata["nested"], MappingProxyType)
        assert r.metadata["nested"]["a"] == 1

    def test_metadata_proxy_is_immutable(self):
        r = RemediationRecord(
            remediation_id="r1", tenant_id="t1", title="t",
            owner_id="o1", created_at=TS,
            metadata={"k": "v"},
        )
        with pytest.raises(TypeError):
            r.metadata["k"] = "new"  # type: ignore[index]

    def test_deeply_nested_freeze(self):
        v = RemediationViolation(
            violation_id="v1", remediation_id="r1",
            tenant_id="t1", operation="op", detected_at=TS,
            metadata={"a": {"b": {"c": [4, 5]}}},
        )
        inner = v.metadata["a"]["b"]["c"]
        assert isinstance(inner, tuple)
        assert inner == (4, 5)

    def test_empty_metadata_is_mapping_proxy(self):
        r = RemediationRecord(
            remediation_id="r1", tenant_id="t1", title="t",
            owner_id="o1", created_at=TS,
        )
        assert isinstance(r.metadata, MappingProxyType)
        assert len(r.metadata) == 0


# ===================================================================
# Cross-cutting datetime validation
# ===================================================================


class TestDatetimeValidation:
    """Datetime fields reject garbage and numeric strings."""

    def test_remediation_record_empty_created_at_rejected(self):
        with pytest.raises(ValueError):
            RemediationRecord(
                remediation_id="r1", tenant_id="t1", title="t",
                owner_id="o1", created_at="",
            )

    def test_corrective_action_empty_created_at_rejected(self):
        with pytest.raises(ValueError):
            CorrectiveAction(
                action_id="a1", remediation_id="r1", title="t",
                owner_id="o1", created_at="",
            )

    def test_assignment_empty_assigned_at_rejected(self):
        with pytest.raises(ValueError):
            RemediationAssignment(
                assignment_id="a1", remediation_id="r1",
                assignee_id="u1", role="r", assigned_at="",
            )

    def test_verification_empty_verified_at_rejected(self):
        with pytest.raises(ValueError):
            VerificationRecord(
                verification_id="v1", remediation_id="r1",
                verifier_id="u1", verified_at="",
            )

    def test_reopen_empty_reopened_at_rejected(self):
        with pytest.raises(ValueError):
            ReopenRecord(
                reopen_id="r1", remediation_id="rem1",
                reopened_by="u1", reopened_at="",
            )

    def test_decision_empty_decided_at_rejected(self):
        with pytest.raises(ValueError):
            RemediationDecision(
                decision_id="d1", remediation_id="r1",
                decided_by="u1", decided_at="",
            )

    def test_snapshot_empty_captured_at_rejected(self):
        with pytest.raises(ValueError):
            RemediationSnapshot(snapshot_id="s1", captured_at="")

    def test_violation_empty_detected_at_rejected(self):
        with pytest.raises(ValueError):
            RemediationViolation(
                violation_id="v1", remediation_id="r1",
                tenant_id="t1", operation="op", detected_at="",
            )

    def test_closure_empty_closed_at_rejected(self):
        with pytest.raises(ValueError):
            RemediationClosureReport(
                report_id="rpt1", remediation_id="r1",
                tenant_id="t1", closed_at="",
            )

    def test_z_suffix_accepted(self):
        """UTC Z suffix should be accepted."""
        r = RemediationRecord(
            remediation_id="r1", tenant_id="t1", title="t",
            owner_id="o1", created_at="2025-06-01T12:00:00Z",
        )
        assert r.created_at == "2025-06-01T12:00:00Z"
