"""Tests for operator identity and attribution contracts."""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.operator import (
    ActionAttribution,
    ActorType,
    ApprovalAttribution,
    AuditEntry,
    ManualOverride,
    OperatorIdentity,
    OperatorRole,
)


class TestOperatorIdentity:
    def test_valid_human(self):
        op = OperatorIdentity(
            operator_id="op-1",
            name="Alice",
            actor_type=ActorType.HUMAN,
            role=OperatorRole.OPERATOR,
            email="alice@company.com",
        )
        assert op.operator_id == "op-1"
        assert op.actor_type is ActorType.HUMAN
        assert op.role is OperatorRole.OPERATOR

    def test_valid_system(self):
        op = OperatorIdentity(
            operator_id="sys-1",
            name="MCOI Runtime",
            actor_type=ActorType.SYSTEM,
            role=OperatorRole.ADMIN,
        )
        assert op.actor_type is ActorType.SYSTEM

    def test_empty_id_rejected(self):
        with pytest.raises(ValueError):
            OperatorIdentity(operator_id="", name="x", actor_type=ActorType.HUMAN, role=OperatorRole.OBSERVER)

    def test_invalid_role_rejected(self):
        with pytest.raises(ValueError):
            OperatorIdentity(operator_id="x", name="x", actor_type=ActorType.HUMAN, role="bad")


class TestActionAttribution:
    def test_valid(self):
        attr = ActionAttribution(
            attribution_id="attr-1",
            operator_id="op-1",
            action_type="run_skill",
            target_id="sk-1",
            timestamp="2025-01-15T10:00:00+00:00",
            reason="operator initiated",
        )
        assert attr.operator_id == "op-1"
        assert attr.action_type == "run_skill"

    def test_empty_fields_rejected(self):
        with pytest.raises(ValueError):
            ActionAttribution(
                attribution_id="", operator_id="op-1",
                action_type="x", target_id="t", timestamp="ts",
            )


class TestApprovalAttribution:
    def test_valid(self):
        attr = ApprovalAttribution(
            approval_id="appr-1",
            approver_id="op-2",
            decision="approved",
            target_id="exec-1",
            correlation_id="corr-1",
            timestamp="2025-01-15T10:00:00+00:00",
            reason="reviewed and accepted",
        )
        assert attr.approver_id == "op-2"
        assert attr.decision == "approved"
        assert attr.correlation_id == "corr-1"

    def test_empty_correlation_rejected(self):
        with pytest.raises(ValueError):
            ApprovalAttribution(
                approval_id="a", approver_id="op",
                decision="approved", target_id="t",
                correlation_id="", timestamp="ts",
            )


class TestManualOverride:
    def test_valid(self):
        ovr = ManualOverride(
            override_id="ovr-1",
            operator_id="op-admin",
            overridden_decision_id="policy-123",
            original_status="deny",
            new_status="allow",
            reason="emergency maintenance window",
            timestamp="2025-01-15T10:00:00+00:00",
        )
        assert ovr.original_status == "deny"
        assert ovr.new_status == "allow"

    def test_empty_reason_rejected(self):
        with pytest.raises(ValueError):
            ManualOverride(
                override_id="o", operator_id="op",
                overridden_decision_id="d", original_status="x",
                new_status="y", reason="", timestamp="ts",
            )


class TestAuditEntry:
    def test_valid_human_action(self):
        entry = AuditEntry(
            entry_id="audit-1",
            operator_id="op-1",
            actor_type=ActorType.HUMAN,
            action="approve_execution",
            target_artifact_id="exec-42",
            timestamp="2025-01-15T10:00:00+00:00",
            details={"correlation_id": "corr-1"},
        )
        assert entry.actor_type is ActorType.HUMAN
        assert entry.details["correlation_id"] == "corr-1"

    def test_valid_system_action(self):
        entry = AuditEntry(
            entry_id="audit-2",
            operator_id="sys-1",
            actor_type=ActorType.SYSTEM,
            action="auto_prune_traces",
            target_artifact_id="trace-batch",
            timestamp="2025-01-15T10:00:00+00:00",
        )
        assert entry.actor_type is ActorType.SYSTEM

    def test_invalid_actor_type(self):
        with pytest.raises(ValueError):
            AuditEntry(
                entry_id="a", operator_id="op",
                actor_type="bad", action="x",
                target_artifact_id="t", timestamp="ts",
            )

    def test_details_frozen(self):
        entry = AuditEntry(
            entry_id="audit-3",
            operator_id="op-1",
            actor_type=ActorType.HUMAN,
            action="test",
            target_artifact_id="t",
            timestamp="2025-01-15T10:00:00+00:00",
            details={"key": "value"},
        )
        assert entry.details["key"] == "value"
