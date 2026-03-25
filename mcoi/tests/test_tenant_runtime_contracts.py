"""Tests for tenant / workspace / environment isolation runtime contracts."""

from __future__ import annotations

import dataclasses
from types import MappingProxyType

import pytest

from mcoi_runtime.contracts.tenant_runtime import (
    BoundaryPolicy,
    EnvironmentKind,
    EnvironmentPromotion,
    EnvironmentRecord,
    IsolationLevel,
    IsolationViolation,
    PromotionStatus,
    ScopeBoundaryKind,
    TenantClosureReport,
    TenantDecision,
    TenantHealth,
    TenantRecord,
    TenantStatus,
    WorkspaceBinding,
    WorkspaceRecord,
    WorkspaceStatus,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TS = "2025-06-01T12:00:00+00:00"
TS2 = "2025-06-15T09:00:00+00:00"


def _tenant(**overrides) -> TenantRecord:
    defaults = dict(tenant_id="t-001", name="Acme Corp", created_at=TS)
    defaults.update(overrides)
    return TenantRecord(**defaults)


def _workspace(**overrides) -> WorkspaceRecord:
    defaults = dict(
        workspace_id="ws-001",
        tenant_id="t-001",
        name="Primary",
        created_at=TS,
    )
    defaults.update(overrides)
    return WorkspaceRecord(**defaults)


def _environment(**overrides) -> EnvironmentRecord:
    defaults = dict(
        environment_id="env-001",
        workspace_id="ws-001",
        created_at=TS,
    )
    defaults.update(overrides)
    return EnvironmentRecord(**defaults)


def _boundary(**overrides) -> BoundaryPolicy:
    defaults = dict(
        policy_id="pol-001",
        tenant_id="t-001",
        created_at=TS,
    )
    defaults.update(overrides)
    return BoundaryPolicy(**defaults)


def _binding(**overrides) -> WorkspaceBinding:
    defaults = dict(
        binding_id="bind-001",
        workspace_id="ws-001",
        resource_ref_id="res-001",
        bound_at=TS,
    )
    defaults.update(overrides)
    return WorkspaceBinding(**defaults)


def _promotion(**overrides) -> EnvironmentPromotion:
    defaults = dict(
        promotion_id="promo-001",
        source_environment_id="env-001",
        target_environment_id="env-002",
        requested_at=TS,
    )
    defaults.update(overrides)
    return EnvironmentPromotion(**defaults)


def _violation(**overrides) -> IsolationViolation:
    defaults = dict(
        violation_id="viol-001",
        tenant_id="t-001",
        detected_at=TS,
    )
    defaults.update(overrides)
    return IsolationViolation(**defaults)


def _health(**overrides) -> TenantHealth:
    defaults = dict(tenant_id="t-001", assessed_at=TS)
    defaults.update(overrides)
    return TenantHealth(**defaults)


def _decision(**overrides) -> TenantDecision:
    defaults = dict(
        decision_id="dec-001",
        tenant_id="t-001",
        title="Suspend workspace",
        confidence=0.8,
        decided_at=TS,
    )
    defaults.update(overrides)
    return TenantDecision(**defaults)


def _closure(**overrides) -> TenantClosureReport:
    defaults = dict(
        report_id="rpt-001",
        tenant_id="t-001",
        closed_at=TS,
    )
    defaults.update(overrides)
    return TenantClosureReport(**defaults)


# ---------------------------------------------------------------------------
# Enum members
# ---------------------------------------------------------------------------


class TestEnumMembers:
    def test_tenant_status_members(self):
        expected = {"ACTIVE", "SUSPENDED", "PROVISIONING", "DECOMMISSIONING", "ARCHIVED"}
        assert {m.name for m in TenantStatus} == expected
        assert len(TenantStatus) == 5

    def test_workspace_status_members(self):
        expected = {"ACTIVE", "SUSPENDED", "PROVISIONING", "ARCHIVED"}
        assert {m.name for m in WorkspaceStatus} == expected
        assert len(WorkspaceStatus) == 4

    def test_environment_kind_members(self):
        expected = {"DEVELOPMENT", "STAGING", "PRODUCTION", "SANDBOX", "DR"}
        assert {m.name for m in EnvironmentKind} == expected
        assert len(EnvironmentKind) == 5

    def test_isolation_level_members(self):
        expected = {"STRICT", "STANDARD", "SHARED", "CUSTOM"}
        assert {m.name for m in IsolationLevel} == expected
        assert len(IsolationLevel) == 4

    def test_scope_boundary_kind_members(self):
        expected = {
            "MEMORY", "CONNECTOR", "BUDGET", "CAMPAIGN",
            "PROGRAM", "CONTROL", "REPORT", "GRAPH",
        }
        assert {m.name for m in ScopeBoundaryKind} == expected
        assert len(ScopeBoundaryKind) == 8

    def test_promotion_status_members(self):
        expected = {
            "REQUESTED", "APPROVED", "IN_PROGRESS",
            "COMPLETED", "FAILED", "ROLLED_BACK",
        }
        assert {m.name for m in PromotionStatus} == expected
        assert len(PromotionStatus) == 6


# ---------------------------------------------------------------------------
# Construction tests (one class per dataclass)
# ---------------------------------------------------------------------------


class TestTenantRecordConstruction:
    def test_minimal(self):
        t = _tenant()
        assert t.tenant_id == "t-001"
        assert t.name == "Acme Corp"
        assert t.status is TenantStatus.ACTIVE
        assert t.isolation_level is IsolationLevel.STANDARD
        assert t.owner == ""
        assert t.workspace_ids == ()
        assert t.created_at == TS
        assert t.updated_at == ""
        assert t.metadata == {}

    def test_full(self):
        t = _tenant(
            status=TenantStatus.SUSPENDED,
            isolation_level=IsolationLevel.STRICT,
            owner="alice",
            workspace_ids=("ws-1", "ws-2"),
            updated_at=TS2,
            metadata={"tier": "enterprise"},
        )
        assert t.status is TenantStatus.SUSPENDED
        assert t.isolation_level is IsolationLevel.STRICT
        assert t.owner == "alice"
        assert t.workspace_ids == ("ws-1", "ws-2")
        assert t.updated_at == TS2
        assert t.metadata["tier"] == "enterprise"


class TestWorkspaceRecordConstruction:
    def test_minimal(self):
        w = _workspace()
        assert w.workspace_id == "ws-001"
        assert w.tenant_id == "t-001"
        assert w.name == "Primary"
        assert w.status is WorkspaceStatus.ACTIVE
        assert w.isolation_level is IsolationLevel.STANDARD
        assert w.environment_ids == ()
        assert w.resource_bindings == ()
        assert w.created_at == TS
        assert w.updated_at == ""
        assert w.metadata == {}

    def test_full(self):
        w = _workspace(
            status=WorkspaceStatus.PROVISIONING,
            isolation_level=IsolationLevel.SHARED,
            environment_ids=("env-1", "env-2"),
            resource_bindings=("res-1",),
            updated_at=TS2,
            metadata={"region": "us-east"},
        )
        assert w.status is WorkspaceStatus.PROVISIONING
        assert w.environment_ids == ("env-1", "env-2")
        assert w.resource_bindings == ("res-1",)
        assert w.metadata["region"] == "us-east"


class TestEnvironmentRecordConstruction:
    def test_minimal(self):
        e = _environment()
        assert e.environment_id == "env-001"
        assert e.workspace_id == "ws-001"
        assert e.kind is EnvironmentKind.DEVELOPMENT
        assert e.name == ""
        assert e.promoted_from == ""
        assert e.connector_ids == ()
        assert e.created_at == TS
        assert e.updated_at == ""
        assert e.metadata == {}

    def test_full(self):
        e = _environment(
            kind=EnvironmentKind.PRODUCTION,
            name="prod-us-east",
            promoted_from="env-000",
            connector_ids=("conn-1", "conn-2"),
            updated_at=TS2,
            metadata={"az": "us-east-1a"},
        )
        assert e.kind is EnvironmentKind.PRODUCTION
        assert e.name == "prod-us-east"
        assert e.promoted_from == "env-000"
        assert e.connector_ids == ("conn-1", "conn-2")


class TestBoundaryPolicyConstruction:
    def test_minimal(self):
        b = _boundary()
        assert b.policy_id == "pol-001"
        assert b.tenant_id == "t-001"
        assert b.boundary_kind is ScopeBoundaryKind.MEMORY
        assert b.isolation_level is IsolationLevel.STRICT
        assert b.enforced is True
        assert b.description == ""
        assert b.created_at == TS
        assert b.metadata == {}

    def test_full(self):
        b = _boundary(
            boundary_kind=ScopeBoundaryKind.BUDGET,
            isolation_level=IsolationLevel.CUSTOM,
            enforced=False,
            description="Custom budget boundary",
            metadata={"source": "admin"},
        )
        assert b.boundary_kind is ScopeBoundaryKind.BUDGET
        assert b.enforced is False
        assert b.description == "Custom budget boundary"


class TestWorkspaceBindingConstruction:
    def test_minimal(self):
        b = _binding()
        assert b.binding_id == "bind-001"
        assert b.workspace_id == "ws-001"
        assert b.resource_ref_id == "res-001"
        assert b.resource_type is ScopeBoundaryKind.CAMPAIGN
        assert b.environment_id == ""
        assert b.bound_at == TS

    def test_full(self):
        b = _binding(
            resource_type=ScopeBoundaryKind.CONNECTOR,
            environment_id="env-001",
        )
        assert b.resource_type is ScopeBoundaryKind.CONNECTOR
        assert b.environment_id == "env-001"


class TestEnvironmentPromotionConstruction:
    def test_minimal(self):
        p = _promotion()
        assert p.promotion_id == "promo-001"
        assert p.source_environment_id == "env-001"
        assert p.target_environment_id == "env-002"
        assert p.status is PromotionStatus.REQUESTED
        assert p.compliance_check_passed is False
        assert p.promoted_by == ""
        assert p.requested_at == TS
        assert p.completed_at == ""
        assert p.metadata == {}

    def test_full(self):
        p = _promotion(
            status=PromotionStatus.COMPLETED,
            compliance_check_passed=True,
            promoted_by="bob",
            completed_at=TS2,
            metadata={"pipeline": "ci-main"},
        )
        assert p.status is PromotionStatus.COMPLETED
        assert p.compliance_check_passed is True
        assert p.promoted_by == "bob"
        assert p.completed_at == TS2
        assert p.metadata["pipeline"] == "ci-main"


class TestIsolationViolationConstruction:
    def test_minimal(self):
        v = _violation()
        assert v.violation_id == "viol-001"
        assert v.tenant_id == "t-001"
        assert v.workspace_id == ""
        assert v.boundary_kind is ScopeBoundaryKind.MEMORY
        assert v.violating_resource_ref == ""
        assert v.description == ""
        assert v.escalated is False
        assert v.detected_at == TS
        assert v.metadata == {}

    def test_full(self):
        v = _violation(
            workspace_id="ws-001",
            boundary_kind=ScopeBoundaryKind.GRAPH,
            violating_resource_ref="ref-123",
            description="Cross-tenant graph access",
            escalated=True,
            metadata={"severity": "high"},
        )
        assert v.boundary_kind is ScopeBoundaryKind.GRAPH
        assert v.violating_resource_ref == "ref-123"
        assert v.escalated is True


class TestTenantHealthConstruction:
    def test_minimal(self):
        h = _health()
        assert h.tenant_id == "t-001"
        assert h.total_workspaces == 0
        assert h.active_workspaces == 0
        assert h.total_environments == 0
        assert h.total_bindings == 0
        assert h.total_violations == 0
        assert h.compliance_pct == 0.0
        assert h.assessed_at == TS
        assert h.metadata == {}

    def test_full(self):
        h = _health(
            total_workspaces=5,
            active_workspaces=3,
            total_environments=12,
            total_bindings=20,
            total_violations=2,
            compliance_pct=95.5,
            metadata={"snapshot": "auto"},
        )
        assert h.total_workspaces == 5
        assert h.active_workspaces == 3
        assert h.compliance_pct == 95.5


class TestTenantDecisionConstruction:
    def test_minimal(self):
        d = _decision()
        assert d.decision_id == "dec-001"
        assert d.tenant_id == "t-001"
        assert d.title == "Suspend workspace"
        assert d.description == ""
        assert d.confidence == 0.8
        assert d.decided_by == ""
        assert d.decided_at == TS
        assert d.metadata == {}

    def test_full(self):
        d = _decision(
            description="Workspace idle too long",
            confidence=0.95,
            decided_by="system",
            metadata={"policy": "auto-suspend"},
        )
        assert d.description == "Workspace idle too long"
        assert d.confidence == 0.95
        assert d.decided_by == "system"
        assert d.metadata["policy"] == "auto-suspend"


class TestTenantClosureReportConstruction:
    def test_minimal(self):
        c = _closure()
        assert c.report_id == "rpt-001"
        assert c.tenant_id == "t-001"
        assert c.total_workspaces == 0
        assert c.total_environments == 0
        assert c.total_bindings == 0
        assert c.total_promotions == 0
        assert c.total_violations == 0
        assert c.total_decisions == 0
        assert c.compliance_pct == 0.0
        assert c.closed_at == TS
        assert c.metadata == {}

    def test_full(self):
        c = _closure(
            total_workspaces=3,
            total_environments=9,
            total_bindings=15,
            total_promotions=4,
            total_violations=1,
            total_decisions=7,
            compliance_pct=98.2,
            metadata={"reason": "decommission"},
        )
        assert c.total_workspaces == 3
        assert c.total_promotions == 4
        assert c.compliance_pct == 98.2
        assert c.metadata["reason"] == "decommission"


# ---------------------------------------------------------------------------
# Frozen immutability
# ---------------------------------------------------------------------------


class TestFrozenImmutability:
    def test_tenant_record_frozen(self):
        t = _tenant()
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            t.name = "changed"  # type: ignore[misc]

    def test_workspace_record_frozen(self):
        w = _workspace()
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            w.name = "changed"  # type: ignore[misc]

    def test_environment_record_frozen(self):
        e = _environment()
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            e.name = "changed"  # type: ignore[misc]

    def test_boundary_policy_frozen(self):
        b = _boundary()
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            b.description = "changed"  # type: ignore[misc]

    def test_workspace_binding_frozen(self):
        b = _binding()
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            b.environment_id = "changed"  # type: ignore[misc]

    def test_environment_promotion_frozen(self):
        p = _promotion()
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            p.promoted_by = "changed"  # type: ignore[misc]

    def test_isolation_violation_frozen(self):
        v = _violation()
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            v.description = "changed"  # type: ignore[misc]

    def test_tenant_health_frozen(self):
        h = _health()
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            h.compliance_pct = 1.0  # type: ignore[misc]

    def test_tenant_decision_frozen(self):
        d = _decision()
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            d.confidence = 0.5  # type: ignore[misc]

    def test_tenant_closure_report_frozen(self):
        c = _closure()
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            c.report_id = "x"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# require_non_empty_text (only * fields)
# ---------------------------------------------------------------------------


class TestRequireNonEmptyText:
    # TenantRecord
    def test_tenant_empty_id(self):
        with pytest.raises(ValueError, match="tenant_id"):
            _tenant(tenant_id="")

    def test_tenant_whitespace_id(self):
        with pytest.raises(ValueError, match="tenant_id"):
            _tenant(tenant_id="   ")

    def test_tenant_empty_name(self):
        with pytest.raises(ValueError, match="name"):
            _tenant(name="")

    # WorkspaceRecord
    def test_workspace_empty_id(self):
        with pytest.raises(ValueError, match="workspace_id"):
            _workspace(workspace_id="")

    def test_workspace_empty_tenant_id(self):
        with pytest.raises(ValueError, match="tenant_id"):
            _workspace(tenant_id="")

    def test_workspace_empty_name(self):
        with pytest.raises(ValueError, match="name"):
            _workspace(name="")

    # EnvironmentRecord
    def test_environment_empty_id(self):
        with pytest.raises(ValueError, match="environment_id"):
            _environment(environment_id="")

    def test_environment_empty_workspace_id(self):
        with pytest.raises(ValueError, match="workspace_id"):
            _environment(workspace_id="")

    # BoundaryPolicy
    def test_boundary_empty_policy_id(self):
        with pytest.raises(ValueError, match="policy_id"):
            _boundary(policy_id="")

    def test_boundary_empty_tenant_id(self):
        with pytest.raises(ValueError, match="tenant_id"):
            _boundary(tenant_id="")

    # WorkspaceBinding
    def test_binding_empty_binding_id(self):
        with pytest.raises(ValueError, match="binding_id"):
            _binding(binding_id="")

    def test_binding_empty_workspace_id(self):
        with pytest.raises(ValueError, match="workspace_id"):
            _binding(workspace_id="")

    def test_binding_empty_resource_ref_id(self):
        with pytest.raises(ValueError, match="resource_ref_id"):
            _binding(resource_ref_id="")

    # EnvironmentPromotion
    def test_promotion_empty_promotion_id(self):
        with pytest.raises(ValueError, match="promotion_id"):
            _promotion(promotion_id="")

    def test_promotion_empty_source_environment_id(self):
        with pytest.raises(ValueError, match="source_environment_id"):
            _promotion(source_environment_id="")

    def test_promotion_empty_target_environment_id(self):
        with pytest.raises(ValueError, match="target_environment_id"):
            _promotion(target_environment_id="")

    # IsolationViolation
    def test_violation_empty_violation_id(self):
        with pytest.raises(ValueError, match="violation_id"):
            _violation(violation_id="")

    def test_violation_empty_tenant_id(self):
        with pytest.raises(ValueError, match="tenant_id"):
            _violation(tenant_id="")

    # TenantHealth
    def test_health_empty_tenant_id(self):
        with pytest.raises(ValueError, match="tenant_id"):
            _health(tenant_id="")

    # TenantDecision
    def test_decision_empty_decision_id(self):
        with pytest.raises(ValueError, match="decision_id"):
            _decision(decision_id="")

    def test_decision_empty_tenant_id(self):
        with pytest.raises(ValueError, match="tenant_id"):
            _decision(tenant_id="")

    def test_decision_empty_title(self):
        with pytest.raises(ValueError, match="title"):
            _decision(title="")

    # TenantClosureReport
    def test_closure_empty_report_id(self):
        with pytest.raises(ValueError, match="report_id"):
            _closure(report_id="")

    def test_closure_empty_tenant_id(self):
        with pytest.raises(ValueError, match="tenant_id"):
            _closure(tenant_id="")


# ---------------------------------------------------------------------------
# Optional fields accept empty string (no ValueError)
# ---------------------------------------------------------------------------


class TestOptionalFieldsAcceptEmpty:
    def test_tenant_owner_empty(self):
        t = _tenant(owner="")
        assert t.owner == ""

    def test_tenant_updated_at_empty(self):
        t = _tenant(updated_at="")
        assert t.updated_at == ""

    def test_workspace_updated_at_empty(self):
        w = _workspace(updated_at="")
        assert w.updated_at == ""

    def test_environment_name_empty(self):
        e = _environment(name="")
        assert e.name == ""

    def test_environment_promoted_from_empty(self):
        e = _environment(promoted_from="")
        assert e.promoted_from == ""

    def test_environment_updated_at_empty(self):
        e = _environment(updated_at="")
        assert e.updated_at == ""

    def test_boundary_description_empty(self):
        b = _boundary(description="")
        assert b.description == ""

    def test_binding_environment_id_empty(self):
        b = _binding(environment_id="")
        assert b.environment_id == ""

    def test_promotion_promoted_by_empty(self):
        p = _promotion(promoted_by="")
        assert p.promoted_by == ""

    def test_promotion_completed_at_empty(self):
        p = _promotion(completed_at="")
        assert p.completed_at == ""

    def test_violation_violating_resource_ref_empty(self):
        v = _violation(violating_resource_ref="")
        assert v.violating_resource_ref == ""

    def test_violation_description_empty(self):
        v = _violation(description="")
        assert v.description == ""

    def test_violation_workspace_id_empty(self):
        v = _violation(workspace_id="")
        assert v.workspace_id == ""

    def test_decision_description_empty(self):
        d = _decision(description="")
        assert d.description == ""

    def test_decision_decided_by_empty(self):
        d = _decision(decided_by="")
        assert d.decided_by == ""


# ---------------------------------------------------------------------------
# require_unit_float
# ---------------------------------------------------------------------------


class TestRequireUnitFloat:
    def test_confidence_zero(self):
        d = _decision(confidence=0.0)
        assert d.confidence == 0.0

    def test_confidence_one(self):
        d = _decision(confidence=1.0)
        assert d.confidence == 1.0

    def test_confidence_mid(self):
        d = _decision(confidence=0.5)
        assert d.confidence == 0.5

    def test_confidence_negative_rejected(self):
        with pytest.raises(ValueError, match="confidence"):
            _decision(confidence=-0.1)

    def test_confidence_above_one_rejected(self):
        with pytest.raises(ValueError, match="confidence"):
            _decision(confidence=1.01)

    def test_confidence_nan_rejected(self):
        with pytest.raises(ValueError, match="confidence"):
            _decision(confidence=float("nan"))

    def test_confidence_inf_rejected(self):
        with pytest.raises(ValueError, match="confidence"):
            _decision(confidence=float("inf"))

    def test_confidence_bool_rejected(self):
        with pytest.raises(ValueError, match="confidence"):
            _decision(confidence=True)


# ---------------------------------------------------------------------------
# require_non_negative_int
# ---------------------------------------------------------------------------


class TestRequireNonNegativeInt:
    # TenantHealth
    def test_health_total_workspaces_zero(self):
        h = _health(total_workspaces=0)
        assert h.total_workspaces == 0

    def test_health_total_workspaces_positive(self):
        h = _health(total_workspaces=5)
        assert h.total_workspaces == 5

    def test_health_total_workspaces_negative_rejected(self):
        with pytest.raises(ValueError, match="total_workspaces"):
            _health(total_workspaces=-1)

    def test_health_active_workspaces_negative_rejected(self):
        with pytest.raises(ValueError, match="active_workspaces"):
            _health(active_workspaces=-1)

    def test_health_total_environments_negative_rejected(self):
        with pytest.raises(ValueError, match="total_environments"):
            _health(total_environments=-1)

    def test_health_total_bindings_negative_rejected(self):
        with pytest.raises(ValueError, match="total_bindings"):
            _health(total_bindings=-1)

    def test_health_total_violations_negative_rejected(self):
        with pytest.raises(ValueError, match="total_violations"):
            _health(total_violations=-1)

    # TenantClosureReport
    def test_closure_total_workspaces_negative_rejected(self):
        with pytest.raises(ValueError, match="total_workspaces"):
            _closure(total_workspaces=-1)

    def test_closure_total_environments_negative_rejected(self):
        with pytest.raises(ValueError, match="total_environments"):
            _closure(total_environments=-1)

    def test_closure_total_bindings_negative_rejected(self):
        with pytest.raises(ValueError, match="total_bindings"):
            _closure(total_bindings=-1)

    def test_closure_total_promotions_negative_rejected(self):
        with pytest.raises(ValueError, match="total_promotions"):
            _closure(total_promotions=-1)

    def test_closure_total_violations_negative_rejected(self):
        with pytest.raises(ValueError, match="total_violations"):
            _closure(total_violations=-1)

    def test_closure_total_decisions_negative_rejected(self):
        with pytest.raises(ValueError, match="total_decisions"):
            _closure(total_decisions=-1)

    def test_bool_rejected_as_int(self):
        with pytest.raises(ValueError, match="total_workspaces"):
            _health(total_workspaces=True)


# ---------------------------------------------------------------------------
# require_non_negative_float
# ---------------------------------------------------------------------------


class TestRequireNonNegativeFloat:
    # TenantHealth compliance_pct
    def test_health_compliance_pct_zero(self):
        h = _health(compliance_pct=0.0)
        assert h.compliance_pct == 0.0

    def test_health_compliance_pct_positive(self):
        h = _health(compliance_pct=99.9)
        assert h.compliance_pct == 99.9

    def test_health_compliance_pct_negative_rejected(self):
        with pytest.raises(ValueError, match="compliance_pct"):
            _health(compliance_pct=-0.1)

    # TenantClosureReport compliance_pct
    def test_closure_compliance_pct_negative_rejected(self):
        with pytest.raises(ValueError, match="compliance_pct"):
            _closure(compliance_pct=-1.0)

    def test_nan_rejected(self):
        with pytest.raises(ValueError, match="compliance_pct"):
            _health(compliance_pct=float("nan"))

    def test_inf_rejected(self):
        with pytest.raises(ValueError, match="compliance_pct"):
            _health(compliance_pct=float("inf"))

    def test_bool_rejected(self):
        with pytest.raises(ValueError, match="compliance_pct"):
            _health(compliance_pct=True)


# ---------------------------------------------------------------------------
# require_datetime_text
# ---------------------------------------------------------------------------


class TestRequireDatetimeText:
    def test_tenant_invalid_created_at(self):
        with pytest.raises(ValueError, match="created_at"):
            _tenant(created_at="not-a-date")

    def test_workspace_invalid_created_at(self):
        with pytest.raises(ValueError, match="created_at"):
            _workspace(created_at="nope")

    def test_environment_invalid_created_at(self):
        with pytest.raises(ValueError, match="created_at"):
            _environment(created_at="invalid")

    def test_boundary_invalid_created_at(self):
        with pytest.raises(ValueError, match="created_at"):
            _boundary(created_at="xyz")

    def test_binding_invalid_bound_at(self):
        with pytest.raises(ValueError, match="bound_at"):
            _binding(bound_at="bad")

    def test_promotion_invalid_requested_at(self):
        with pytest.raises(ValueError, match="requested_at"):
            _promotion(requested_at="bad")

    def test_violation_invalid_detected_at(self):
        with pytest.raises(ValueError, match="detected_at"):
            _violation(detected_at="bad")

    def test_health_invalid_assessed_at(self):
        with pytest.raises(ValueError, match="assessed_at"):
            _health(assessed_at="bad")

    def test_decision_invalid_decided_at(self):
        with pytest.raises(ValueError, match="decided_at"):
            _decision(decided_at="bad")

    def test_closure_invalid_closed_at(self):
        with pytest.raises(ValueError, match="closed_at"):
            _closure(closed_at="bad")

    def test_iso_z_suffix_accepted(self):
        t = _tenant(created_at="2025-06-01T12:00:00Z")
        assert t.created_at == "2025-06-01T12:00:00Z"

    def test_empty_created_at_rejected(self):
        with pytest.raises(ValueError, match="created_at"):
            _tenant(created_at="")


# ---------------------------------------------------------------------------
# Enum type validation
# ---------------------------------------------------------------------------


class TestEnumTypeValidation:
    def test_tenant_status_string_rejected(self):
        with pytest.raises(ValueError, match="status"):
            _tenant(status="active")

    def test_tenant_isolation_level_string_rejected(self):
        with pytest.raises(ValueError, match="isolation_level"):
            _tenant(isolation_level="standard")

    def test_workspace_status_string_rejected(self):
        with pytest.raises(ValueError, match="status"):
            _workspace(status="active")

    def test_workspace_isolation_level_string_rejected(self):
        with pytest.raises(ValueError, match="isolation_level"):
            _workspace(isolation_level="standard")

    def test_environment_kind_string_rejected(self):
        with pytest.raises(ValueError, match="kind"):
            _environment(kind="development")

    def test_boundary_kind_string_rejected(self):
        with pytest.raises(ValueError, match="boundary_kind"):
            _boundary(boundary_kind="memory")

    def test_boundary_isolation_level_string_rejected(self):
        with pytest.raises(ValueError, match="isolation_level"):
            _boundary(isolation_level="strict")

    def test_binding_resource_type_string_rejected(self):
        with pytest.raises(ValueError, match="resource_type"):
            _binding(resource_type="campaign")

    def test_promotion_status_string_rejected(self):
        with pytest.raises(ValueError, match="status"):
            _promotion(status="requested")

    def test_violation_boundary_kind_string_rejected(self):
        with pytest.raises(ValueError, match="boundary_kind"):
            _violation(boundary_kind="memory")

    def test_boundary_enforced_non_bool_rejected(self):
        with pytest.raises(ValueError, match="enforced"):
            _boundary(enforced=1)

    def test_promotion_compliance_check_non_bool_rejected(self):
        with pytest.raises(ValueError, match="compliance_check_passed"):
            _promotion(compliance_check_passed=1)

    def test_violation_escalated_non_bool_rejected(self):
        with pytest.raises(ValueError, match="escalated"):
            _violation(escalated=1)


# ---------------------------------------------------------------------------
# freeze_value (metadata, tuple fields)
# ---------------------------------------------------------------------------


class TestFreezeValue:
    def test_tenant_metadata_frozen(self):
        t = _tenant(metadata={"k": "v"})
        assert isinstance(t.metadata, MappingProxyType)
        with pytest.raises(TypeError):
            t.metadata["new"] = "x"  # type: ignore[index]

    def test_workspace_metadata_frozen(self):
        w = _workspace(metadata={"k": "v"})
        assert isinstance(w.metadata, MappingProxyType)

    def test_environment_metadata_frozen(self):
        e = _environment(metadata={"k": "v"})
        assert isinstance(e.metadata, MappingProxyType)

    def test_boundary_metadata_frozen(self):
        b = _boundary(metadata={"k": "v"})
        assert isinstance(b.metadata, MappingProxyType)

    def test_promotion_metadata_frozen(self):
        p = _promotion(metadata={"k": "v"})
        assert isinstance(p.metadata, MappingProxyType)

    def test_violation_metadata_frozen(self):
        v = _violation(metadata={"k": "v"})
        assert isinstance(v.metadata, MappingProxyType)

    def test_health_metadata_frozen(self):
        h = _health(metadata={"k": "v"})
        assert isinstance(h.metadata, MappingProxyType)

    def test_decision_metadata_frozen(self):
        d = _decision(metadata={"k": "v"})
        assert isinstance(d.metadata, MappingProxyType)

    def test_closure_metadata_frozen(self):
        c = _closure(metadata={"k": "v"})
        assert isinstance(c.metadata, MappingProxyType)

    def test_tenant_workspace_ids_tuple(self):
        t = _tenant(workspace_ids=["ws-1", "ws-2"])
        assert isinstance(t.workspace_ids, tuple)
        assert t.workspace_ids == ("ws-1", "ws-2")

    def test_workspace_environment_ids_tuple(self):
        w = _workspace(environment_ids=["env-1", "env-2"])
        assert isinstance(w.environment_ids, tuple)
        assert w.environment_ids == ("env-1", "env-2")

    def test_workspace_resource_bindings_tuple(self):
        w = _workspace(resource_bindings=["res-1"])
        assert isinstance(w.resource_bindings, tuple)

    def test_environment_connector_ids_tuple(self):
        e = _environment(connector_ids=["conn-1"])
        assert isinstance(e.connector_ids, tuple)
        assert e.connector_ids == ("conn-1",)

    def test_nested_metadata_frozen(self):
        t = _tenant(metadata={"nested": {"inner": 1}})
        assert isinstance(t.metadata["nested"], MappingProxyType)
        with pytest.raises(TypeError):
            t.metadata["nested"]["new"] = 2  # type: ignore[index]

    def test_list_to_tuple_in_metadata(self):
        t = _tenant(metadata={"tags": [1, 2, 3]})
        assert isinstance(t.metadata["tags"], tuple)
        assert t.metadata["tags"] == (1, 2, 3)

    def test_empty_metadata_is_mapping_proxy(self):
        t = _tenant()
        assert isinstance(t.metadata, MappingProxyType)


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------


class TestDefaults:
    def test_tenant_defaults(self):
        t = _tenant()
        assert t.status is TenantStatus.ACTIVE
        assert t.isolation_level is IsolationLevel.STANDARD
        assert t.owner == ""
        assert t.workspace_ids == ()
        assert t.updated_at == ""
        assert t.metadata == {}

    def test_workspace_defaults(self):
        w = _workspace()
        assert w.status is WorkspaceStatus.ACTIVE
        assert w.isolation_level is IsolationLevel.STANDARD
        assert w.environment_ids == ()
        assert w.resource_bindings == ()
        assert w.updated_at == ""
        assert w.metadata == {}

    def test_environment_defaults(self):
        e = _environment()
        assert e.kind is EnvironmentKind.DEVELOPMENT
        assert e.name == ""
        assert e.promoted_from == ""
        assert e.connector_ids == ()
        assert e.updated_at == ""
        assert e.metadata == {}

    def test_boundary_defaults(self):
        b = _boundary()
        assert b.boundary_kind is ScopeBoundaryKind.MEMORY
        assert b.isolation_level is IsolationLevel.STRICT
        assert b.enforced is True
        assert b.description == ""
        assert b.metadata == {}

    def test_binding_defaults(self):
        b = _binding()
        assert b.resource_type is ScopeBoundaryKind.CAMPAIGN
        assert b.environment_id == ""

    def test_promotion_defaults(self):
        p = _promotion()
        assert p.status is PromotionStatus.REQUESTED
        assert p.compliance_check_passed is False
        assert p.promoted_by == ""
        assert p.completed_at == ""
        assert p.metadata == {}

    def test_violation_defaults(self):
        v = _violation()
        assert v.workspace_id == ""
        assert v.boundary_kind is ScopeBoundaryKind.MEMORY
        assert v.violating_resource_ref == ""
        assert v.description == ""
        assert v.escalated is False
        assert v.metadata == {}

    def test_health_defaults(self):
        h = _health()
        assert h.total_workspaces == 0
        assert h.active_workspaces == 0
        assert h.total_environments == 0
        assert h.total_bindings == 0
        assert h.total_violations == 0
        assert h.compliance_pct == 0.0
        assert h.metadata == {}

    def test_decision_defaults(self):
        d = _decision()
        assert d.description == ""
        assert d.decided_by == ""
        assert d.metadata == {}

    def test_closure_defaults(self):
        c = _closure()
        assert c.total_workspaces == 0
        assert c.total_environments == 0
        assert c.total_bindings == 0
        assert c.total_promotions == 0
        assert c.total_violations == 0
        assert c.total_decisions == 0
        assert c.compliance_pct == 0.0
        assert c.metadata == {}


# ---------------------------------------------------------------------------
# Edge-case boundaries
# ---------------------------------------------------------------------------


class TestEdgeCaseBoundaries:
    def test_all_enum_values_for_tenant_status(self):
        for status in TenantStatus:
            t = _tenant(status=status)
            assert t.status is status

    def test_all_enum_values_for_workspace_status(self):
        for status in WorkspaceStatus:
            w = _workspace(status=status)
            assert w.status is status

    def test_all_enum_values_for_environment_kind(self):
        for kind in EnvironmentKind:
            e = _environment(kind=kind)
            assert e.kind is kind

    def test_all_enum_values_for_isolation_level(self):
        for level in IsolationLevel:
            t = _tenant(isolation_level=level)
            assert t.isolation_level is level

    def test_all_enum_values_for_scope_boundary_kind(self):
        for kind in ScopeBoundaryKind:
            b = _boundary(boundary_kind=kind)
            assert b.boundary_kind is kind

    def test_all_enum_values_for_promotion_status(self):
        for status in PromotionStatus:
            p = _promotion(status=status)
            assert p.status is status

    def test_confidence_exact_boundaries(self):
        assert _decision(confidence=0.0).confidence == 0.0
        assert _decision(confidence=1.0).confidence == 1.0

    def test_int_coerced_to_float_for_confidence(self):
        d = _decision(confidence=1)
        assert d.confidence == 1.0
        assert isinstance(d.confidence, float)

    def test_whitespace_only_id_rejected(self):
        with pytest.raises(ValueError, match="tenant_id"):
            _tenant(tenant_id="\t\n ")

    def test_large_compliance_pct_accepted(self):
        h = _health(compliance_pct=999.9)
        assert h.compliance_pct == 999.9


# ---------------------------------------------------------------------------
# to_dict serialization
# ---------------------------------------------------------------------------


class TestToDictSerialization:
    def test_tenant_to_dict_preserves_enums(self):
        t = _tenant(
            status=TenantStatus.SUSPENDED,
            isolation_level=IsolationLevel.STRICT,
            metadata={"k": "v"},
        )
        d = t.to_dict()
        assert d["tenant_id"] == "t-001"
        assert d["name"] == "Acme Corp"
        assert d["status"] is TenantStatus.SUSPENDED
        assert d["isolation_level"] is IsolationLevel.STRICT
        assert d["metadata"] == {"k": "v"}
        assert isinstance(d["metadata"], dict)

    def test_tenant_to_dict_tuples_become_lists(self):
        t = _tenant(workspace_ids=("ws-1", "ws-2"))
        d = t.to_dict()
        assert d["workspace_ids"] == ["ws-1", "ws-2"]
        assert isinstance(d["workspace_ids"], list)

    def test_workspace_to_dict(self):
        w = _workspace(
            status=WorkspaceStatus.PROVISIONING,
            environment_ids=("env-1",),
            resource_bindings=("res-1",),
        )
        d = w.to_dict()
        assert d["status"] is WorkspaceStatus.PROVISIONING
        assert d["environment_ids"] == ["env-1"]
        assert isinstance(d["environment_ids"], list)
        assert d["resource_bindings"] == ["res-1"]
        assert isinstance(d["resource_bindings"], list)

    def test_environment_to_dict(self):
        e = _environment(
            kind=EnvironmentKind.PRODUCTION,
            connector_ids=("conn-1",),
        )
        d = e.to_dict()
        assert d["kind"] is EnvironmentKind.PRODUCTION
        assert d["connector_ids"] == ["conn-1"]
        assert isinstance(d["connector_ids"], list)

    def test_boundary_to_dict(self):
        b = _boundary(
            boundary_kind=ScopeBoundaryKind.BUDGET,
            isolation_level=IsolationLevel.CUSTOM,
        )
        d = b.to_dict()
        assert d["boundary_kind"] is ScopeBoundaryKind.BUDGET
        assert d["isolation_level"] is IsolationLevel.CUSTOM

    def test_binding_to_dict(self):
        b = _binding(resource_type=ScopeBoundaryKind.CONNECTOR)
        d = b.to_dict()
        assert d["binding_id"] == "bind-001"
        assert d["resource_type"] is ScopeBoundaryKind.CONNECTOR

    def test_promotion_to_dict(self):
        p = _promotion(
            status=PromotionStatus.COMPLETED,
            metadata={"ci": True},
        )
        d = p.to_dict()
        assert d["status"] is PromotionStatus.COMPLETED
        assert d["metadata"] == {"ci": True}
        assert isinstance(d["metadata"], dict)

    def test_violation_to_dict(self):
        v = _violation(
            boundary_kind=ScopeBoundaryKind.GRAPH,
            metadata={"severity": "high"},
        )
        d = v.to_dict()
        assert d["boundary_kind"] is ScopeBoundaryKind.GRAPH
        assert d["metadata"] == {"severity": "high"}

    def test_health_to_dict(self):
        h = _health(total_workspaces=5, compliance_pct=95.0)
        d = h.to_dict()
        assert d["total_workspaces"] == 5
        assert d["compliance_pct"] == 95.0

    def test_decision_to_dict(self):
        dec = _decision(confidence=0.9, metadata={"tag": "urgent"})
        d = dec.to_dict()
        assert d["confidence"] == 0.9
        assert d["metadata"] == {"tag": "urgent"}

    def test_closure_to_dict(self):
        c = _closure(
            total_promotions=4,
            compliance_pct=98.0,
            metadata={"done": True},
        )
        d = c.to_dict()
        assert d["total_promotions"] == 4
        assert d["compliance_pct"] == 98.0
        assert d["metadata"] == {"done": True}

    def test_to_dict_round_trip_preserves_enums(self):
        b = _binding()
        d = b.to_dict()
        assert d["resource_type"] is ScopeBoundaryKind.CAMPAIGN
