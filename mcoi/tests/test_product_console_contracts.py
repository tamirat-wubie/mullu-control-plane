"""Tests for product console / multi-tenant admin surface contracts."""

from __future__ import annotations

import dataclasses
from dataclasses import FrozenInstanceError
from types import MappingProxyType

import pytest

from mcoi_runtime.contracts.product_console import (
    AdminActionRecord,
    AdminActionStatus,
    AdminPanel,
    ConsoleAssessment,
    ConsoleClosureReport,
    ConsoleDecision,
    ConsoleRole,
    ConsoleSession,
    ConsoleSnapshot,
    ConsoleStatus,
    ConsoleSurface,
    ConsoleViolation,
    NavigationNode,
    NavigationScope,
    SurfaceDisposition,
    ViewMode,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TS = "2025-06-01T12:00:00+00:00"
TS2 = "2025-06-15T09:00:00+00:00"


def _surface(**kw) -> ConsoleSurface:
    defaults = dict(
        surface_id="surf-001",
        tenant_id="t-001",
        display_name="Tenant Admin",
        status=ConsoleStatus.ACTIVE,
        disposition=SurfaceDisposition.VISIBLE,
        role=ConsoleRole.TENANT_ADMIN,
        created_at=TS,
    )
    defaults.update(kw)
    return ConsoleSurface(**defaults)


def _node(**kw) -> NavigationNode:
    defaults = dict(
        node_id="node-001",
        tenant_id="t-001",
        surface_ref="surf-001",
        parent_ref="root",
        label="Dashboard",
        scope=NavigationScope.TENANT,
        order=0,
        created_at=TS,
    )
    defaults.update(kw)
    return NavigationNode(**defaults)


def _panel(**kw) -> AdminPanel:
    defaults = dict(
        panel_id="panel-001",
        tenant_id="t-001",
        surface_ref="surf-001",
        display_name="Admin Panel",
        target_runtime="customer_runtime",
        view_mode=ViewMode.FULL,
        created_at=TS,
    )
    defaults.update(kw)
    return AdminPanel(**defaults)


def _session(**kw) -> ConsoleSession:
    defaults = dict(
        session_id="sess-001",
        tenant_id="t-001",
        identity_ref="id-001",
        surface_ref="surf-001",
        status=ConsoleStatus.ACTIVE,
        started_at=TS,
    )
    defaults.update(kw)
    return ConsoleSession(**defaults)


def _action(**kw) -> AdminActionRecord:
    defaults = dict(
        action_id="act-001",
        tenant_id="t-001",
        session_ref="sess-001",
        panel_ref="panel-001",
        operation="update_config",
        status=AdminActionStatus.PENDING,
        performed_at=TS,
    )
    defaults.update(kw)
    return AdminActionRecord(**defaults)


def _decision(**kw) -> ConsoleDecision:
    defaults = dict(
        decision_id="dec-001",
        tenant_id="t-001",
        action_ref="act-001",
        disposition="approved",
        reason="Policy allows",
        decided_at=TS,
    )
    defaults.update(kw)
    return ConsoleDecision(**defaults)


def _snapshot(**kw) -> ConsoleSnapshot:
    defaults = dict(
        snapshot_id="snap-001",
        tenant_id="t-001",
        total_surfaces=1,
        total_panels=2,
        total_sessions=3,
        total_actions=4,
        total_violations=0,
        captured_at=TS,
    )
    defaults.update(kw)
    return ConsoleSnapshot(**defaults)


def _violation(**kw) -> ConsoleViolation:
    defaults = dict(
        violation_id="viol-001",
        tenant_id="t-001",
        operation="cross_tenant_access",
        reason="Tenant mismatch",
        detected_at=TS,
    )
    defaults.update(kw)
    return ConsoleViolation(**defaults)


def _assessment(**kw) -> ConsoleAssessment:
    defaults = dict(
        assessment_id="assess-001",
        tenant_id="t-001",
        total_surfaces=2,
        total_active_sessions=1,
        action_success_rate=0.8,
        assessed_at=TS,
    )
    defaults.update(kw)
    return ConsoleAssessment(**defaults)


def _closure_report(**kw) -> ConsoleClosureReport:
    defaults = dict(
        report_id="rpt-001",
        tenant_id="t-001",
        total_surfaces=3,
        total_panels=2,
        total_sessions=5,
        total_actions=10,
        total_violations=1,
        created_at=TS,
    )
    defaults.update(kw)
    return ConsoleClosureReport(**defaults)


# ====================================================================
# ENUM TESTS
# ====================================================================


class TestConsoleStatusEnum:
    def test_values(self):
        assert ConsoleStatus.ACTIVE.value == "active"
        assert ConsoleStatus.SUSPENDED.value == "suspended"
        assert ConsoleStatus.CLOSED.value == "closed"
        assert ConsoleStatus.MAINTENANCE.value == "maintenance"

    def test_member_count(self):
        assert len(ConsoleStatus) == 4

    def test_unique_values(self):
        vals = [e.value for e in ConsoleStatus]
        assert len(vals) == len(set(vals))

    def test_is_enum(self):
        assert isinstance(ConsoleStatus.ACTIVE, ConsoleStatus)


class TestViewModeEnum:
    def test_values(self):
        assert ViewMode.FULL.value == "full"
        assert ViewMode.RESTRICTED.value == "restricted"
        assert ViewMode.READ_ONLY.value == "read_only"
        assert ViewMode.HIDDEN.value == "hidden"

    def test_member_count(self):
        assert len(ViewMode) == 4

    def test_unique_values(self):
        vals = [e.value for e in ViewMode]
        assert len(vals) == len(set(vals))


class TestAdminActionStatusEnum:
    def test_values(self):
        assert AdminActionStatus.PENDING.value == "pending"
        assert AdminActionStatus.EXECUTED.value == "executed"
        assert AdminActionStatus.DENIED.value == "denied"
        assert AdminActionStatus.ROLLED_BACK.value == "rolled_back"

    def test_member_count(self):
        assert len(AdminActionStatus) == 4

    def test_unique_values(self):
        vals = [e.value for e in AdminActionStatus]
        assert len(vals) == len(set(vals))


class TestNavigationScopeEnum:
    def test_values(self):
        assert NavigationScope.TENANT.value == "tenant"
        assert NavigationScope.WORKSPACE.value == "workspace"
        assert NavigationScope.SERVICE.value == "service"
        assert NavigationScope.PROGRAM.value == "program"
        assert NavigationScope.GLOBAL.value == "global"

    def test_member_count(self):
        assert len(NavigationScope) == 5


class TestSurfaceDispositionEnum:
    def test_values(self):
        assert SurfaceDisposition.VISIBLE.value == "visible"
        assert SurfaceDisposition.HIDDEN.value == "hidden"
        assert SurfaceDisposition.RESTRICTED.value == "restricted"
        assert SurfaceDisposition.LOCKED.value == "locked"

    def test_member_count(self):
        assert len(SurfaceDisposition) == 4


class TestConsoleRoleEnum:
    def test_values(self):
        assert ConsoleRole.TENANT_ADMIN.value == "tenant_admin"
        assert ConsoleRole.WORKSPACE_ADMIN.value == "workspace_admin"
        assert ConsoleRole.OPERATIONS_MANAGER.value == "operations_manager"
        assert ConsoleRole.CUSTOMER_ADMIN.value == "customer_admin"
        assert ConsoleRole.PARTNER_ADMIN.value == "partner_admin"
        assert ConsoleRole.COMPLIANCE_VIEWER.value == "compliance_viewer"

    def test_member_count(self):
        assert len(ConsoleRole) == 6


# ====================================================================
# ConsoleSurface TESTS
# ====================================================================


class TestConsoleSurfaceConstruction:
    def test_valid_construction(self):
        s = _surface()
        assert s.surface_id == "surf-001"
        assert s.tenant_id == "t-001"
        assert s.display_name == "Tenant Admin"
        assert s.status == ConsoleStatus.ACTIVE
        assert s.disposition == SurfaceDisposition.VISIBLE
        assert s.role == ConsoleRole.TENANT_ADMIN
        assert s.created_at == TS

    def test_custom_status(self):
        s = _surface(status=ConsoleStatus.SUSPENDED)
        assert s.status == ConsoleStatus.SUSPENDED

    def test_custom_disposition(self):
        s = _surface(disposition=SurfaceDisposition.LOCKED)
        assert s.disposition == SurfaceDisposition.LOCKED

    def test_custom_role(self):
        s = _surface(role=ConsoleRole.PARTNER_ADMIN)
        assert s.role == ConsoleRole.PARTNER_ADMIN

    def test_all_roles(self):
        for role in ConsoleRole:
            s = _surface(role=role)
            assert s.role == role

    def test_all_statuses(self):
        for st in ConsoleStatus:
            s = _surface(status=st)
            assert s.status == st

    def test_all_dispositions(self):
        for d in SurfaceDisposition:
            s = _surface(disposition=d)
            assert s.disposition == d

    def test_metadata_default_empty(self):
        s = _surface()
        assert len(s.metadata) == 0

    def test_metadata_frozen(self):
        s = _surface(metadata={"key": "val"})
        assert isinstance(s.metadata, MappingProxyType)
        assert s.metadata["key"] == "val"

    def test_metadata_nested_frozen(self):
        s = _surface(metadata={"nested": {"a": 1}})
        assert isinstance(s.metadata["nested"], MappingProxyType)

    def test_metadata_mutation_blocked(self):
        s = _surface(metadata={"key": "val"})
        with pytest.raises(TypeError):
            s.metadata["new"] = "x"


class TestConsoleSurfaceValidation:
    def test_empty_surface_id(self):
        with pytest.raises(ValueError):
            _surface(surface_id="")

    def test_blank_surface_id(self):
        with pytest.raises(ValueError):
            _surface(surface_id="   ")

    def test_empty_tenant_id(self):
        with pytest.raises(ValueError):
            _surface(tenant_id="")

    def test_empty_display_name(self):
        with pytest.raises(ValueError):
            _surface(display_name="")

    def test_invalid_status_type(self):
        with pytest.raises(ValueError, match="status must be a ConsoleStatus"):
            _surface(status="active")

    def test_invalid_disposition_type(self):
        with pytest.raises(ValueError, match="disposition must be a SurfaceDisposition"):
            _surface(disposition="visible")

    def test_invalid_role_type(self):
        with pytest.raises(ValueError, match="role must be a ConsoleRole"):
            _surface(role="admin")

    def test_invalid_created_at(self):
        with pytest.raises(ValueError):
            _surface(created_at="not-a-date")

    def test_empty_created_at(self):
        with pytest.raises(ValueError):
            _surface(created_at="")

    def test_none_surface_id(self):
        with pytest.raises((ValueError, TypeError)):
            _surface(surface_id=None)

    def test_none_tenant_id(self):
        with pytest.raises((ValueError, TypeError)):
            _surface(tenant_id=None)


class TestConsoleSurfaceFrozen:
    def test_frozen_surface_id(self):
        s = _surface()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            s.surface_id = "new"

    def test_frozen_tenant_id(self):
        s = _surface()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            s.tenant_id = "new"

    def test_frozen_status(self):
        s = _surface()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            s.status = ConsoleStatus.CLOSED

    def test_frozen_disposition(self):
        s = _surface()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            s.disposition = SurfaceDisposition.HIDDEN

    def test_frozen_role(self):
        s = _surface()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            s.role = ConsoleRole.PARTNER_ADMIN

    def test_frozen_created_at(self):
        s = _surface()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            s.created_at = TS2


class TestConsoleSurfaceSerialization:
    def test_to_dict(self):
        s = _surface()
        d = s.to_dict()
        assert d["surface_id"] == "surf-001"
        assert d["tenant_id"] == "t-001"
        # to_dict preserves enum objects
        assert isinstance(d["status"], ConsoleStatus)
        assert d["status"] == ConsoleStatus.ACTIVE

    def test_to_dict_preserves_enum_objects(self):
        s = _surface(role=ConsoleRole.PARTNER_ADMIN)
        d = s.to_dict()
        assert isinstance(d["role"], ConsoleRole)
        assert isinstance(d["disposition"], SurfaceDisposition)

    def test_to_json_dict_converts_enums(self):
        s = _surface()
        d = s.to_json_dict()
        assert d["status"] == "active"
        assert d["disposition"] == "visible"
        assert d["role"] == "tenant_admin"

    def test_to_json(self):
        s = _surface()
        import json
        j = s.to_json()
        parsed = json.loads(j)
        assert parsed["surface_id"] == "surf-001"
        assert parsed["status"] == "active"

    def test_to_dict_metadata(self):
        s = _surface(metadata={"x": 1})
        d = s.to_dict()
        assert d["metadata"] == {"x": 1}

    def test_round_trip_fields(self):
        s = _surface()
        d = s.to_dict()
        assert set(d.keys()) == {f.name for f in dataclasses.fields(ConsoleSurface)}


# ====================================================================
# NavigationNode TESTS
# ====================================================================


class TestNavigationNodeConstruction:
    def test_valid_construction(self):
        n = _node()
        assert n.node_id == "node-001"
        assert n.tenant_id == "t-001"
        assert n.surface_ref == "surf-001"
        assert n.parent_ref == "root"
        assert n.label == "Dashboard"
        assert n.scope == NavigationScope.TENANT
        assert n.order == 0

    def test_custom_scope(self):
        n = _node(scope=NavigationScope.WORKSPACE)
        assert n.scope == NavigationScope.WORKSPACE

    def test_all_scopes(self):
        for sc in NavigationScope:
            n = _node(scope=sc)
            assert n.scope == sc

    def test_custom_order(self):
        n = _node(order=10)
        assert n.order == 10

    def test_zero_order(self):
        n = _node(order=0)
        assert n.order == 0

    def test_metadata_default_empty(self):
        n = _node()
        assert len(n.metadata) == 0

    def test_metadata_frozen(self):
        n = _node(metadata={"key": "val"})
        assert isinstance(n.metadata, MappingProxyType)


class TestNavigationNodeValidation:
    def test_empty_node_id(self):
        with pytest.raises(ValueError):
            _node(node_id="")

    def test_empty_tenant_id(self):
        with pytest.raises(ValueError):
            _node(tenant_id="")

    def test_empty_surface_ref(self):
        with pytest.raises(ValueError):
            _node(surface_ref="")

    def test_empty_parent_ref(self):
        with pytest.raises(ValueError):
            _node(parent_ref="")

    def test_empty_label(self):
        with pytest.raises(ValueError):
            _node(label="")

    def test_invalid_scope_type(self):
        with pytest.raises(ValueError, match="scope must be a NavigationScope"):
            _node(scope="tenant")

    def test_negative_order(self):
        with pytest.raises(ValueError):
            _node(order=-1)

    def test_invalid_created_at(self):
        with pytest.raises(ValueError):
            _node(created_at="bad")

    def test_bool_order_rejected(self):
        with pytest.raises(ValueError):
            _node(order=True)


class TestNavigationNodeFrozen:
    def test_frozen_node_id(self):
        n = _node()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            n.node_id = "new"

    def test_frozen_label(self):
        n = _node()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            n.label = "new"

    def test_frozen_scope(self):
        n = _node()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            n.scope = NavigationScope.GLOBAL

    def test_frozen_order(self):
        n = _node()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            n.order = 99


class TestNavigationNodeSerialization:
    def test_to_dict(self):
        n = _node()
        d = n.to_dict()
        assert d["node_id"] == "node-001"
        assert isinstance(d["scope"], NavigationScope)

    def test_to_json_dict_scope_string(self):
        n = _node()
        d = n.to_json_dict()
        assert d["scope"] == "tenant"

    def test_round_trip_fields(self):
        n = _node()
        d = n.to_dict()
        assert set(d.keys()) == {f.name for f in dataclasses.fields(NavigationNode)}


# ====================================================================
# AdminPanel TESTS
# ====================================================================


class TestAdminPanelConstruction:
    def test_valid_construction(self):
        p = _panel()
        assert p.panel_id == "panel-001"
        assert p.tenant_id == "t-001"
        assert p.surface_ref == "surf-001"
        assert p.display_name == "Admin Panel"
        assert p.target_runtime == "customer_runtime"
        assert p.view_mode == ViewMode.FULL

    def test_all_view_modes(self):
        for vm in ViewMode:
            p = _panel(view_mode=vm)
            assert p.view_mode == vm

    def test_metadata_frozen(self):
        p = _panel(metadata={"k": "v"})
        assert isinstance(p.metadata, MappingProxyType)


class TestAdminPanelValidation:
    def test_empty_panel_id(self):
        with pytest.raises(ValueError):
            _panel(panel_id="")

    def test_empty_tenant_id(self):
        with pytest.raises(ValueError):
            _panel(tenant_id="")

    def test_empty_surface_ref(self):
        with pytest.raises(ValueError):
            _panel(surface_ref="")

    def test_empty_display_name(self):
        with pytest.raises(ValueError):
            _panel(display_name="")

    def test_empty_target_runtime(self):
        with pytest.raises(ValueError):
            _panel(target_runtime="")

    def test_invalid_view_mode_type(self):
        with pytest.raises(ValueError, match="view_mode must be a ViewMode"):
            _panel(view_mode="full")

    def test_invalid_created_at(self):
        with pytest.raises(ValueError):
            _panel(created_at="bad")


class TestAdminPanelFrozen:
    def test_frozen_panel_id(self):
        p = _panel()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            p.panel_id = "new"

    def test_frozen_view_mode(self):
        p = _panel()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            p.view_mode = ViewMode.HIDDEN

    def test_frozen_target_runtime(self):
        p = _panel()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            p.target_runtime = "other"


class TestAdminPanelSerialization:
    def test_to_dict_preserves_enum(self):
        p = _panel()
        d = p.to_dict()
        assert isinstance(d["view_mode"], ViewMode)

    def test_to_json_dict_converts_enum(self):
        p = _panel()
        d = p.to_json_dict()
        assert d["view_mode"] == "full"

    def test_round_trip_fields(self):
        p = _panel()
        d = p.to_dict()
        assert set(d.keys()) == {f.name for f in dataclasses.fields(AdminPanel)}


# ====================================================================
# ConsoleSession TESTS
# ====================================================================


class TestConsoleSessionConstruction:
    def test_valid_construction(self):
        s = _session()
        assert s.session_id == "sess-001"
        assert s.tenant_id == "t-001"
        assert s.identity_ref == "id-001"
        assert s.surface_ref == "surf-001"
        assert s.status == ConsoleStatus.ACTIVE
        assert s.started_at == TS

    def test_all_statuses(self):
        for st in ConsoleStatus:
            s = _session(status=st)
            assert s.status == st

    def test_metadata_frozen(self):
        s = _session(metadata={"k": "v"})
        assert isinstance(s.metadata, MappingProxyType)


class TestConsoleSessionValidation:
    def test_empty_session_id(self):
        with pytest.raises(ValueError):
            _session(session_id="")

    def test_empty_tenant_id(self):
        with pytest.raises(ValueError):
            _session(tenant_id="")

    def test_empty_identity_ref(self):
        with pytest.raises(ValueError):
            _session(identity_ref="")

    def test_empty_surface_ref(self):
        with pytest.raises(ValueError):
            _session(surface_ref="")

    def test_invalid_status_type(self):
        with pytest.raises(ValueError, match="status must be a ConsoleStatus"):
            _session(status="active")

    def test_invalid_started_at(self):
        with pytest.raises(ValueError):
            _session(started_at="bad")


class TestConsoleSessionFrozen:
    def test_frozen_session_id(self):
        s = _session()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            s.session_id = "new"

    def test_frozen_status(self):
        s = _session()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            s.status = ConsoleStatus.CLOSED

    def test_frozen_identity_ref(self):
        s = _session()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            s.identity_ref = "other"


class TestConsoleSessionSerialization:
    def test_to_dict_preserves_enum(self):
        s = _session()
        d = s.to_dict()
        assert isinstance(d["status"], ConsoleStatus)

    def test_to_json_dict_converts_enum(self):
        s = _session()
        d = s.to_json_dict()
        assert d["status"] == "active"


# ====================================================================
# AdminActionRecord TESTS
# ====================================================================


class TestAdminActionRecordConstruction:
    def test_valid_construction(self):
        a = _action()
        assert a.action_id == "act-001"
        assert a.tenant_id == "t-001"
        assert a.session_ref == "sess-001"
        assert a.panel_ref == "panel-001"
        assert a.operation == "update_config"
        assert a.status == AdminActionStatus.PENDING
        assert a.performed_at == TS

    def test_all_statuses(self):
        for st in AdminActionStatus:
            a = _action(status=st)
            assert a.status == st

    def test_metadata_frozen(self):
        a = _action(metadata={"k": "v"})
        assert isinstance(a.metadata, MappingProxyType)


class TestAdminActionRecordValidation:
    def test_empty_action_id(self):
        with pytest.raises(ValueError):
            _action(action_id="")

    def test_empty_tenant_id(self):
        with pytest.raises(ValueError):
            _action(tenant_id="")

    def test_empty_session_ref(self):
        with pytest.raises(ValueError):
            _action(session_ref="")

    def test_empty_panel_ref(self):
        with pytest.raises(ValueError):
            _action(panel_ref="")

    def test_empty_operation(self):
        with pytest.raises(ValueError):
            _action(operation="")

    def test_invalid_status_type(self):
        with pytest.raises(ValueError, match="status must be an AdminActionStatus"):
            _action(status="pending")

    def test_invalid_performed_at(self):
        with pytest.raises(ValueError):
            _action(performed_at="bad")


class TestAdminActionRecordFrozen:
    def test_frozen_action_id(self):
        a = _action()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            a.action_id = "new"

    def test_frozen_status(self):
        a = _action()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            a.status = AdminActionStatus.EXECUTED

    def test_frozen_operation(self):
        a = _action()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            a.operation = "delete"


class TestAdminActionRecordSerialization:
    def test_to_dict_preserves_enum(self):
        a = _action()
        d = a.to_dict()
        assert isinstance(d["status"], AdminActionStatus)

    def test_to_json_dict_converts_enum(self):
        a = _action()
        d = a.to_json_dict()
        assert d["status"] == "pending"

    def test_round_trip_fields(self):
        a = _action()
        d = a.to_dict()
        assert set(d.keys()) == {f.name for f in dataclasses.fields(AdminActionRecord)}


# ====================================================================
# ConsoleDecision TESTS
# ====================================================================


class TestConsoleDecisionConstruction:
    def test_valid_construction(self):
        d = _decision()
        assert d.decision_id == "dec-001"
        assert d.tenant_id == "t-001"
        assert d.action_ref == "act-001"
        assert d.disposition == "approved"
        assert d.reason == "Policy allows"
        assert d.decided_at == TS

    def test_metadata_frozen(self):
        d = _decision(metadata={"k": "v"})
        assert isinstance(d.metadata, MappingProxyType)


class TestConsoleDecisionValidation:
    def test_empty_decision_id(self):
        with pytest.raises(ValueError):
            _decision(decision_id="")

    def test_empty_tenant_id(self):
        with pytest.raises(ValueError):
            _decision(tenant_id="")

    def test_empty_action_ref(self):
        with pytest.raises(ValueError):
            _decision(action_ref="")

    def test_empty_disposition(self):
        with pytest.raises(ValueError):
            _decision(disposition="")

    def test_empty_reason(self):
        with pytest.raises(ValueError):
            _decision(reason="")

    def test_invalid_decided_at(self):
        with pytest.raises(ValueError):
            _decision(decided_at="bad")


class TestConsoleDecisionFrozen:
    def test_frozen_decision_id(self):
        d = _decision()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            d.decision_id = "new"

    def test_frozen_disposition(self):
        d = _decision()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            d.disposition = "denied"


class TestConsoleDecisionSerialization:
    def test_to_dict(self):
        d = _decision()
        result = d.to_dict()
        assert result["decision_id"] == "dec-001"

    def test_round_trip_fields(self):
        d = _decision()
        result = d.to_dict()
        assert set(result.keys()) == {f.name for f in dataclasses.fields(ConsoleDecision)}


# ====================================================================
# ConsoleSnapshot TESTS
# ====================================================================


class TestConsoleSnapshotConstruction:
    def test_valid_construction(self):
        s = _snapshot()
        assert s.snapshot_id == "snap-001"
        assert s.tenant_id == "t-001"
        assert s.total_surfaces == 1
        assert s.total_panels == 2
        assert s.total_sessions == 3
        assert s.total_actions == 4
        assert s.total_violations == 0
        assert s.captured_at == TS

    def test_zero_counts(self):
        s = _snapshot(total_surfaces=0, total_panels=0, total_sessions=0,
                      total_actions=0, total_violations=0)
        assert s.total_surfaces == 0

    def test_metadata_frozen(self):
        s = _snapshot(metadata={"k": "v"})
        assert isinstance(s.metadata, MappingProxyType)


class TestConsoleSnapshotValidation:
    def test_empty_snapshot_id(self):
        with pytest.raises(ValueError):
            _snapshot(snapshot_id="")

    def test_empty_tenant_id(self):
        with pytest.raises(ValueError):
            _snapshot(tenant_id="")

    def test_negative_total_surfaces(self):
        with pytest.raises(ValueError):
            _snapshot(total_surfaces=-1)

    def test_negative_total_panels(self):
        with pytest.raises(ValueError):
            _snapshot(total_panels=-1)

    def test_negative_total_sessions(self):
        with pytest.raises(ValueError):
            _snapshot(total_sessions=-1)

    def test_negative_total_actions(self):
        with pytest.raises(ValueError):
            _snapshot(total_actions=-1)

    def test_negative_total_violations(self):
        with pytest.raises(ValueError):
            _snapshot(total_violations=-1)

    def test_bool_total_surfaces_rejected(self):
        with pytest.raises(ValueError):
            _snapshot(total_surfaces=True)

    def test_invalid_captured_at(self):
        with pytest.raises(ValueError):
            _snapshot(captured_at="bad")


class TestConsoleSnapshotFrozen:
    def test_frozen_snapshot_id(self):
        s = _snapshot()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            s.snapshot_id = "new"

    def test_frozen_total_surfaces(self):
        s = _snapshot()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            s.total_surfaces = 99


class TestConsoleSnapshotSerialization:
    def test_to_dict(self):
        s = _snapshot()
        d = s.to_dict()
        assert d["snapshot_id"] == "snap-001"
        assert d["total_surfaces"] == 1

    def test_round_trip_fields(self):
        s = _snapshot()
        d = s.to_dict()
        assert set(d.keys()) == {f.name for f in dataclasses.fields(ConsoleSnapshot)}


# ====================================================================
# ConsoleViolation TESTS
# ====================================================================


class TestConsoleViolationConstruction:
    def test_valid_construction(self):
        v = _violation()
        assert v.violation_id == "viol-001"
        assert v.tenant_id == "t-001"
        assert v.operation == "cross_tenant_access"
        assert v.reason == "Tenant mismatch"
        assert v.detected_at == TS

    def test_metadata_frozen(self):
        v = _violation(metadata={"k": "v"})
        assert isinstance(v.metadata, MappingProxyType)


class TestConsoleViolationValidation:
    def test_empty_violation_id(self):
        with pytest.raises(ValueError):
            _violation(violation_id="")

    def test_empty_tenant_id(self):
        with pytest.raises(ValueError):
            _violation(tenant_id="")

    def test_empty_operation(self):
        with pytest.raises(ValueError):
            _violation(operation="")

    def test_empty_reason(self):
        with pytest.raises(ValueError):
            _violation(reason="")

    def test_invalid_detected_at(self):
        with pytest.raises(ValueError):
            _violation(detected_at="bad")


class TestConsoleViolationFrozen:
    def test_frozen_violation_id(self):
        v = _violation()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            v.violation_id = "new"

    def test_frozen_reason(self):
        v = _violation()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            v.reason = "other"


class TestConsoleViolationSerialization:
    def test_to_dict(self):
        v = _violation()
        d = v.to_dict()
        assert d["violation_id"] == "viol-001"

    def test_round_trip_fields(self):
        v = _violation()
        d = v.to_dict()
        assert set(d.keys()) == {f.name for f in dataclasses.fields(ConsoleViolation)}


# ====================================================================
# ConsoleAssessment TESTS
# ====================================================================


class TestConsoleAssessmentConstruction:
    def test_valid_construction(self):
        a = _assessment()
        assert a.assessment_id == "assess-001"
        assert a.tenant_id == "t-001"
        assert a.total_surfaces == 2
        assert a.total_active_sessions == 1
        assert a.action_success_rate == 0.8
        assert a.assessed_at == TS

    def test_zero_rate(self):
        a = _assessment(action_success_rate=0.0)
        assert a.action_success_rate == 0.0

    def test_one_rate(self):
        a = _assessment(action_success_rate=1.0)
        assert a.action_success_rate == 1.0

    def test_metadata_frozen(self):
        a = _assessment(metadata={"k": "v"})
        assert isinstance(a.metadata, MappingProxyType)


class TestConsoleAssessmentValidation:
    def test_empty_assessment_id(self):
        with pytest.raises(ValueError):
            _assessment(assessment_id="")

    def test_empty_tenant_id(self):
        with pytest.raises(ValueError):
            _assessment(tenant_id="")

    def test_negative_total_surfaces(self):
        with pytest.raises(ValueError):
            _assessment(total_surfaces=-1)

    def test_negative_total_active_sessions(self):
        with pytest.raises(ValueError):
            _assessment(total_active_sessions=-1)

    def test_action_success_rate_below_zero(self):
        with pytest.raises(ValueError):
            _assessment(action_success_rate=-0.1)

    def test_action_success_rate_above_one(self):
        with pytest.raises(ValueError):
            _assessment(action_success_rate=1.01)

    def test_action_success_rate_nan(self):
        import math
        with pytest.raises(ValueError):
            _assessment(action_success_rate=math.nan)

    def test_action_success_rate_inf(self):
        import math
        with pytest.raises(ValueError):
            _assessment(action_success_rate=math.inf)

    def test_action_success_rate_bool_rejected(self):
        with pytest.raises(ValueError):
            _assessment(action_success_rate=True)

    def test_invalid_assessed_at(self):
        with pytest.raises(ValueError):
            _assessment(assessed_at="bad")

    def test_action_success_rate_is_unit_float(self):
        a = _assessment(action_success_rate=0.5)
        assert 0.0 <= a.action_success_rate <= 1.0


class TestConsoleAssessmentFrozen:
    def test_frozen_assessment_id(self):
        a = _assessment()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            a.assessment_id = "new"

    def test_frozen_action_success_rate(self):
        a = _assessment()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            a.action_success_rate = 0.5


class TestConsoleAssessmentSerialization:
    def test_to_dict(self):
        a = _assessment()
        d = a.to_dict()
        assert d["assessment_id"] == "assess-001"
        assert d["action_success_rate"] == 0.8

    def test_round_trip_fields(self):
        a = _assessment()
        d = a.to_dict()
        assert set(d.keys()) == {f.name for f in dataclasses.fields(ConsoleAssessment)}


# ====================================================================
# ConsoleClosureReport TESTS
# ====================================================================


class TestConsoleClosureReportConstruction:
    def test_valid_construction(self):
        r = _closure_report()
        assert r.report_id == "rpt-001"
        assert r.tenant_id == "t-001"
        assert r.total_surfaces == 3
        assert r.total_panels == 2
        assert r.total_sessions == 5
        assert r.total_actions == 10
        assert r.total_violations == 1
        assert r.created_at == TS

    def test_zero_counts(self):
        r = _closure_report(total_surfaces=0, total_panels=0, total_sessions=0,
                            total_actions=0, total_violations=0)
        assert r.total_surfaces == 0

    def test_metadata_frozen(self):
        r = _closure_report(metadata={"k": "v"})
        assert isinstance(r.metadata, MappingProxyType)


class TestConsoleClosureReportValidation:
    def test_empty_report_id(self):
        with pytest.raises(ValueError):
            _closure_report(report_id="")

    def test_empty_tenant_id(self):
        with pytest.raises(ValueError):
            _closure_report(tenant_id="")

    def test_negative_total_surfaces(self):
        with pytest.raises(ValueError):
            _closure_report(total_surfaces=-1)

    def test_negative_total_panels(self):
        with pytest.raises(ValueError):
            _closure_report(total_panels=-1)

    def test_negative_total_sessions(self):
        with pytest.raises(ValueError):
            _closure_report(total_sessions=-1)

    def test_negative_total_actions(self):
        with pytest.raises(ValueError):
            _closure_report(total_actions=-1)

    def test_negative_total_violations(self):
        with pytest.raises(ValueError):
            _closure_report(total_violations=-1)

    def test_bool_total_panels_rejected(self):
        with pytest.raises(ValueError):
            _closure_report(total_panels=True)

    def test_invalid_created_at(self):
        with pytest.raises(ValueError):
            _closure_report(created_at="bad")


class TestConsoleClosureReportFrozen:
    def test_frozen_report_id(self):
        r = _closure_report()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            r.report_id = "new"

    def test_frozen_total_surfaces(self):
        r = _closure_report()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            r.total_surfaces = 99


class TestConsoleClosureReportSerialization:
    def test_to_dict(self):
        r = _closure_report()
        d = r.to_dict()
        assert d["report_id"] == "rpt-001"
        assert d["total_violations"] == 1

    def test_round_trip_fields(self):
        r = _closure_report()
        d = r.to_dict()
        assert set(d.keys()) == {f.name for f in dataclasses.fields(ConsoleClosureReport)}


# ====================================================================
# CROSS-CUTTING: Parametrized tests
# ====================================================================

ALL_CONSTRUCTORS = [
    ("ConsoleSurface", _surface),
    ("NavigationNode", _node),
    ("AdminPanel", _panel),
    ("ConsoleSession", _session),
    ("AdminActionRecord", _action),
    ("ConsoleDecision", _decision),
    ("ConsoleSnapshot", _snapshot),
    ("ConsoleViolation", _violation),
    ("ConsoleAssessment", _assessment),
    ("ConsoleClosureReport", _closure_report),
]


class TestAllContractsAreDataclasses:
    @pytest.mark.parametrize("name,ctor", ALL_CONSTRUCTORS)
    def test_is_dataclass(self, name, ctor):
        obj = ctor()
        assert dataclasses.is_dataclass(obj)

    @pytest.mark.parametrize("name,ctor", ALL_CONSTRUCTORS)
    def test_is_frozen(self, name, ctor):
        obj = ctor()
        assert dataclasses.fields(obj)[0].name  # has fields
        # frozen=True means setattr raises
        field_name = dataclasses.fields(obj)[0].name
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(obj, field_name, "mutated")


class TestAllContractsHaveToDict:
    @pytest.mark.parametrize("name,ctor", ALL_CONSTRUCTORS)
    def test_has_to_dict(self, name, ctor):
        obj = ctor()
        assert hasattr(obj, "to_dict")
        d = obj.to_dict()
        assert isinstance(d, dict)

    @pytest.mark.parametrize("name,ctor", ALL_CONSTRUCTORS)
    def test_has_to_json_dict(self, name, ctor):
        obj = ctor()
        assert hasattr(obj, "to_json_dict")
        d = obj.to_json_dict()
        assert isinstance(d, dict)

    @pytest.mark.parametrize("name,ctor", ALL_CONSTRUCTORS)
    def test_has_to_json(self, name, ctor):
        obj = ctor()
        assert hasattr(obj, "to_json")
        import json
        parsed = json.loads(obj.to_json())
        assert isinstance(parsed, dict)


class TestAllContractsTenantId:
    @pytest.mark.parametrize("name,ctor", ALL_CONSTRUCTORS)
    def test_has_tenant_id(self, name, ctor):
        obj = ctor()
        assert hasattr(obj, "tenant_id")
        assert obj.tenant_id == "t-001"


class TestAllContractsSlots:
    @pytest.mark.parametrize("name,ctor", ALL_CONSTRUCTORS)
    def test_uses_slots(self, name, ctor):
        obj = ctor()
        assert hasattr(type(obj), "__slots__")


# ====================================================================
# Edge cases and corner cases
# ====================================================================


class TestDateTimeFormats:
    def test_iso_with_z_suffix(self):
        s = _surface(created_at="2025-06-01T12:00:00Z")
        assert s.created_at == "2025-06-01T12:00:00Z"

    def test_iso_with_offset(self):
        s = _surface(created_at="2025-06-01T12:00:00+05:30")
        assert s.created_at == "2025-06-01T12:00:00+05:30"

    def test_short_iso_date(self):
        s = _surface(created_at="2025-06-01")
        assert s.created_at == "2025-06-01"

    def test_iso_no_offset(self):
        s = _surface(created_at="2025-06-01T12:00:00")
        assert s.created_at == "2025-06-01T12:00:00"


class TestMetadataIsolation:
    def test_input_dict_not_shared(self):
        original = {"key": "value"}
        s = _surface(metadata=original)
        original["key"] = "changed"
        assert s.metadata["key"] == "value"

    def test_nested_dict_not_shared(self):
        original = {"nested": {"a": 1}}
        s = _surface(metadata=original)
        original["nested"]["a"] = 999
        assert s.metadata["nested"]["a"] == 1


class TestMultipleTenantIds:
    def test_different_tenants_surface(self):
        s1 = _surface(surface_id="s1", tenant_id="t-001")
        s2 = _surface(surface_id="s2", tenant_id="t-002")
        assert s1.tenant_id != s2.tenant_id

    def test_different_tenants_session(self):
        s1 = _session(session_id="sess-a", tenant_id="t-001")
        s2 = _session(session_id="sess-b", tenant_id="t-002")
        assert s1.tenant_id != s2.tenant_id


class TestWhitespaceHandling:
    def test_whitespace_only_surface_id(self):
        with pytest.raises(ValueError):
            _surface(surface_id="   \t  ")

    def test_whitespace_only_tenant_id(self):
        with pytest.raises(ValueError):
            _surface(tenant_id="   \n  ")

    def test_whitespace_only_label(self):
        with pytest.raises(ValueError):
            _node(label="   ")
