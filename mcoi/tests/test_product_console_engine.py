"""Tests for product console / multi-tenant admin surface engine."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
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
from mcoi_runtime.core.engine_protocol import FixedClock
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.product_console import ProductConsoleEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FIXED_TIME = "2026-01-01T00:00:00+00:00"


def _make_engine(clock=None) -> tuple[EventSpineEngine, ProductConsoleEngine]:
    es = EventSpineEngine()
    clk = clock or FixedClock(FIXED_TIME)
    eng = ProductConsoleEngine(es, clock=clk)
    return es, eng


def _engine_with_surface(
    surface_id="surf-001", tenant_id="t-001", display_name="Admin Console",
    role=ConsoleRole.TENANT_ADMIN, disposition=SurfaceDisposition.VISIBLE,
    clock=None,
) -> tuple[EventSpineEngine, ProductConsoleEngine, ConsoleSurface]:
    es, eng = _make_engine(clock=clock)
    s = eng.register_surface(surface_id, tenant_id, display_name, role=role, disposition=disposition)
    return es, eng, s


def _engine_with_session(
    clock=None,
) -> tuple[EventSpineEngine, ProductConsoleEngine, ConsoleSurface, ConsoleSession]:
    es, eng, s = _engine_with_surface(clock=clock)
    sess = eng.start_console_session("sess-001", "t-001", "id-001", "surf-001")
    return es, eng, s, sess


def _engine_with_panel(
    clock=None,
) -> tuple[EventSpineEngine, ProductConsoleEngine, ConsoleSurface, AdminPanel]:
    es, eng, s = _engine_with_surface(clock=clock)
    p = eng.register_panel("panel-001", "t-001", "surf-001", "Panel", "runtime_a")
    return es, eng, s, p


def _engine_with_action(
    clock=None,
) -> tuple[EventSpineEngine, ProductConsoleEngine, AdminActionRecord]:
    es, eng, s = _engine_with_surface(clock=clock)
    eng.register_panel("panel-001", "t-001", "surf-001", "Panel", "runtime_a")
    sess = eng.start_console_session("sess-001", "t-001", "id-001", "surf-001")
    act = eng.record_admin_action("act-001", "t-001", "sess-001", "panel-001", "update_config")
    return es, eng, act


# ====================================================================
# CONSTRUCTOR TESTS
# ====================================================================


class TestEngineConstructor:
    def test_valid_construction(self):
        es, eng = _make_engine()
        assert eng.surface_count == 0
        assert eng.node_count == 0
        assert eng.panel_count == 0
        assert eng.session_count == 0
        assert eng.action_count == 0
        assert eng.decision_count == 0
        assert eng.violation_count == 0

    def test_invalid_event_spine(self):
        with pytest.raises(RuntimeCoreInvariantError):
            ProductConsoleEngine("not_an_event_spine")

    def test_none_event_spine(self):
        with pytest.raises(RuntimeCoreInvariantError):
            ProductConsoleEngine(None)

    def test_clock_optional(self):
        es = EventSpineEngine()
        eng = ProductConsoleEngine(es)
        assert eng.surface_count == 0

    def test_fixed_clock_injection(self):
        clk = FixedClock("2026-06-15T10:00:00+00:00")
        es = EventSpineEngine()
        eng = ProductConsoleEngine(es, clock=clk)
        s = eng.register_surface("s1", "t1", "Name")
        assert s.created_at == "2026-06-15T10:00:00+00:00"

    def test_invalid_clock_falls_back(self):
        es = EventSpineEngine()
        eng = ProductConsoleEngine(es, clock="not_a_clock")
        # Should fallback to WallClock - engine still works
        assert eng.surface_count == 0


# ====================================================================
# SURFACE TESTS
# ====================================================================


class TestRegisterSurface:
    def test_register_surface_basic(self):
        es, eng, s = _engine_with_surface()
        assert s.surface_id == "surf-001"
        assert s.tenant_id == "t-001"
        assert s.display_name == "Admin Console"
        assert s.status == ConsoleStatus.ACTIVE
        assert s.role == ConsoleRole.TENANT_ADMIN
        assert s.disposition == SurfaceDisposition.VISIBLE
        assert eng.surface_count == 1

    def test_register_surface_emits_event(self):
        es, eng, s = _engine_with_surface()
        assert es.event_count >= 1

    def test_register_surface_custom_role(self):
        es, eng, s = _engine_with_surface(role=ConsoleRole.PARTNER_ADMIN)
        assert s.role == ConsoleRole.PARTNER_ADMIN

    def test_register_surface_custom_disposition(self):
        es, eng, s = _engine_with_surface(disposition=SurfaceDisposition.LOCKED)
        assert s.disposition == SurfaceDisposition.LOCKED

    def test_register_all_roles(self):
        es, eng = _make_engine()
        for i, role in enumerate(ConsoleRole):
            s = eng.register_surface(f"s-{i}", "t-001", f"Surface {i}", role=role)
            assert s.role == role
        assert eng.surface_count == len(ConsoleRole)

    def test_register_all_dispositions(self):
        es, eng = _make_engine()
        for i, disp in enumerate(SurfaceDisposition):
            s = eng.register_surface(f"s-{i}", "t-001", f"Surface {i}", disposition=disp)
            assert s.disposition == disp

    def test_duplicate_surface_id_raises(self):
        es, eng, s = _engine_with_surface()
        with pytest.raises(RuntimeCoreInvariantError, match="surface already registered"):
            eng.register_surface("surf-001", "t-001", "Duplicate")

    def test_multiple_surfaces(self):
        es, eng = _make_engine()
        eng.register_surface("s1", "t-001", "S1")
        eng.register_surface("s2", "t-001", "S2")
        eng.register_surface("s3", "t-002", "S3")
        assert eng.surface_count == 3

    def test_register_surface_returns_frozen(self):
        es, eng, s = _engine_with_surface()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            s.surface_id = "new"


class TestGetSurface:
    def test_get_existing(self):
        es, eng, s = _engine_with_surface()
        got = eng.get_surface("surf-001")
        assert got.surface_id == "surf-001"
        assert got.tenant_id == "t-001"

    def test_get_unknown_raises(self):
        es, eng = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="unknown surface"):
            eng.get_surface("missing")


class TestSurfacesForTenant:
    def test_filters_by_tenant(self):
        es, eng = _make_engine()
        eng.register_surface("s1", "t-001", "S1")
        eng.register_surface("s2", "t-001", "S2")
        eng.register_surface("s3", "t-002", "S3")
        result = eng.surfaces_for_tenant("t-001")
        assert len(result) == 2
        assert all(s.tenant_id == "t-001" for s in result)

    def test_empty_for_unknown_tenant(self):
        es, eng, s = _engine_with_surface()
        result = eng.surfaces_for_tenant("t-999")
        assert result == ()

    def test_returns_tuple(self):
        es, eng, s = _engine_with_surface()
        result = eng.surfaces_for_tenant("t-001")
        assert isinstance(result, tuple)


class TestSuspendSurface:
    def test_suspend_active_surface(self):
        es, eng, s = _engine_with_surface()
        updated = eng.suspend_surface("surf-001")
        assert updated.status == ConsoleStatus.SUSPENDED
        assert eng.get_surface("surf-001").status == ConsoleStatus.SUSPENDED

    def test_suspend_emits_event(self):
        es, eng, s = _engine_with_surface()
        count_before = es.event_count
        eng.suspend_surface("surf-001")
        assert es.event_count > count_before

    def test_suspend_unknown_raises(self):
        es, eng = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="unknown surface"):
            eng.suspend_surface("missing")

    def test_suspend_closed_raises(self):
        es, eng, s = _engine_with_surface()
        eng.close_surface("surf-001")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal state"):
            eng.suspend_surface("surf-001")

    def test_suspend_active_is_idempotent_status(self):
        # Suspending an active surface works
        es, eng, s = _engine_with_surface()
        updated = eng.suspend_surface("surf-001")
        assert updated.status == ConsoleStatus.SUSPENDED


class TestCloseSurface:
    def test_close_active_surface(self):
        es, eng, s = _engine_with_surface()
        updated = eng.close_surface("surf-001")
        assert updated.status == ConsoleStatus.CLOSED

    def test_close_suspended_surface(self):
        es, eng, s = _engine_with_surface()
        eng.suspend_surface("surf-001")
        updated = eng.close_surface("surf-001")
        assert updated.status == ConsoleStatus.CLOSED

    def test_close_already_closed_raises(self):
        es, eng, s = _engine_with_surface()
        eng.close_surface("surf-001")
        with pytest.raises(RuntimeCoreInvariantError, match="already closed"):
            eng.close_surface("surf-001")

    def test_close_unknown_raises(self):
        es, eng = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="unknown surface"):
            eng.close_surface("missing")

    def test_close_emits_event(self):
        es, eng, s = _engine_with_surface()
        count_before = es.event_count
        eng.close_surface("surf-001")
        assert es.event_count > count_before

    def test_close_is_terminal(self):
        es, eng, s = _engine_with_surface()
        eng.close_surface("surf-001")
        with pytest.raises(RuntimeCoreInvariantError):
            eng.suspend_surface("surf-001")
        with pytest.raises(RuntimeCoreInvariantError):
            eng.activate_surface("surf-001")


class TestActivateSurface:
    def test_activate_suspended_surface(self):
        es, eng, s = _engine_with_surface()
        eng.suspend_surface("surf-001")
        updated = eng.activate_surface("surf-001")
        assert updated.status == ConsoleStatus.ACTIVE

    def test_activate_active_raises(self):
        es, eng, s = _engine_with_surface()
        with pytest.raises(RuntimeCoreInvariantError, match="activate_surface requires SUSPENDED"):
            eng.activate_surface("surf-001")

    def test_activate_closed_raises(self):
        es, eng, s = _engine_with_surface()
        eng.close_surface("surf-001")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal state"):
            eng.activate_surface("surf-001")

    def test_activate_unknown_raises(self):
        es, eng = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="unknown surface"):
            eng.activate_surface("missing")

    def test_activate_emits_event(self):
        es, eng, s = _engine_with_surface()
        eng.suspend_surface("surf-001")
        count_before = es.event_count
        eng.activate_surface("surf-001")
        assert es.event_count > count_before


# ====================================================================
# NAVIGATION NODE TESTS
# ====================================================================


class TestRegisterNavigationNode:
    def test_register_basic(self):
        es, eng = _make_engine()
        eng.register_surface("surf-001", "t-001", "S1")
        n = eng.register_navigation_node("node-001", "t-001", "surf-001", "Dashboard")
        assert n.node_id == "node-001"
        assert n.tenant_id == "t-001"
        assert n.surface_ref == "surf-001"
        assert n.label == "Dashboard"
        assert n.scope == NavigationScope.TENANT
        assert n.parent_ref == "root"
        assert n.order == 0
        assert eng.node_count == 1

    def test_register_custom_scope(self):
        es, eng = _make_engine()
        eng.register_surface("surf-001", "t-001", "S1")
        n = eng.register_navigation_node("n1", "t-001", "surf-001", "WS", scope=NavigationScope.WORKSPACE)
        assert n.scope == NavigationScope.WORKSPACE

    def test_register_custom_parent(self):
        es, eng = _make_engine()
        eng.register_surface("surf-001", "t-001", "S1")
        n = eng.register_navigation_node("n1", "t-001", "surf-001", "Child", parent_ref="parent-node")
        assert n.parent_ref == "parent-node"

    def test_register_custom_order(self):
        es, eng = _make_engine()
        eng.register_surface("surf-001", "t-001", "S1")
        n = eng.register_navigation_node("n1", "t-001", "surf-001", "Last", order=99)
        assert n.order == 99

    def test_duplicate_node_raises(self):
        es, eng = _make_engine()
        eng.register_surface("surf-001", "t-001", "S1")
        eng.register_navigation_node("n1", "t-001", "surf-001", "First")
        with pytest.raises(RuntimeCoreInvariantError, match="node already registered"):
            eng.register_navigation_node("n1", "t-001", "surf-001", "Dup")

    def test_register_emits_event(self):
        es, eng = _make_engine()
        eng.register_surface("surf-001", "t-001", "S1")
        count_before = es.event_count
        eng.register_navigation_node("n1", "t-001", "surf-001", "Nav")
        assert es.event_count > count_before

    def test_all_scopes(self):
        es, eng = _make_engine()
        eng.register_surface("surf-001", "t-001", "S1")
        for i, scope in enumerate(NavigationScope):
            n = eng.register_navigation_node(f"n-{i}", "t-001", "surf-001", f"S{i}", scope=scope)
            assert n.scope == scope


class TestGetNode:
    def test_get_existing(self):
        es, eng = _make_engine()
        eng.register_surface("surf-001", "t-001", "S1")
        eng.register_navigation_node("n1", "t-001", "surf-001", "Nav")
        got = eng.get_node("n1")
        assert got.node_id == "n1"

    def test_get_unknown_raises(self):
        es, eng = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="unknown node"):
            eng.get_node("missing")


class TestNodesForSurface:
    def test_returns_sorted_by_order(self):
        es, eng = _make_engine()
        eng.register_surface("surf-001", "t-001", "S1")
        eng.register_navigation_node("n3", "t-001", "surf-001", "Third", order=3)
        eng.register_navigation_node("n1", "t-001", "surf-001", "First", order=1)
        eng.register_navigation_node("n2", "t-001", "surf-001", "Second", order=2)
        result = eng.nodes_for_surface("surf-001")
        assert len(result) == 3
        assert result[0].order == 1
        assert result[1].order == 2
        assert result[2].order == 3

    def test_empty_for_unknown_surface(self):
        es, eng = _make_engine()
        result = eng.nodes_for_surface("missing")
        assert result == ()

    def test_returns_tuple(self):
        es, eng = _make_engine()
        result = eng.nodes_for_surface("surf-001")
        assert isinstance(result, tuple)


# ====================================================================
# PANEL TESTS
# ====================================================================


class TestRegisterPanel:
    def test_register_basic(self):
        es, eng, s, p = _engine_with_panel()
        assert p.panel_id == "panel-001"
        assert p.tenant_id == "t-001"
        assert p.surface_ref == "surf-001"
        assert p.display_name == "Panel"
        assert p.target_runtime == "runtime_a"
        assert p.view_mode == ViewMode.FULL
        assert eng.panel_count == 1

    def test_register_custom_view_mode(self):
        es, eng, s = _engine_with_surface()
        p = eng.register_panel("p1", "t-001", "surf-001", "P", "rt", view_mode=ViewMode.READ_ONLY)
        assert p.view_mode == ViewMode.READ_ONLY

    def test_all_view_modes(self):
        es, eng, s = _engine_with_surface()
        for i, vm in enumerate(ViewMode):
            p = eng.register_panel(f"p-{i}", "t-001", "surf-001", f"P{i}", "rt", view_mode=vm)
            assert p.view_mode == vm

    def test_duplicate_panel_raises(self):
        es, eng, s, p = _engine_with_panel()
        with pytest.raises(RuntimeCoreInvariantError, match="panel already registered"):
            eng.register_panel("panel-001", "t-001", "surf-001", "Dup", "rt")

    def test_register_emits_event(self):
        es, eng, s = _engine_with_surface()
        count_before = es.event_count
        eng.register_panel("p1", "t-001", "surf-001", "P", "rt")
        assert es.event_count > count_before


class TestGetPanel:
    def test_get_existing(self):
        es, eng, s, p = _engine_with_panel()
        got = eng.get_panel("panel-001")
        assert got.panel_id == "panel-001"

    def test_get_unknown_raises(self):
        es, eng = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="unknown panel"):
            eng.get_panel("missing")


class TestPanelsForSurface:
    def test_filters_by_surface(self):
        es, eng = _make_engine()
        eng.register_surface("s1", "t-001", "S1")
        eng.register_surface("s2", "t-001", "S2")
        eng.register_panel("p1", "t-001", "s1", "P1", "rt")
        eng.register_panel("p2", "t-001", "s1", "P2", "rt")
        eng.register_panel("p3", "t-001", "s2", "P3", "rt")
        result = eng.panels_for_surface("s1")
        assert len(result) == 2
        assert all(p.surface_ref == "s1" for p in result)

    def test_empty_for_unknown(self):
        es, eng = _make_engine()
        result = eng.panels_for_surface("missing")
        assert result == ()

    def test_returns_tuple(self):
        es, eng, s, p = _engine_with_panel()
        result = eng.panels_for_surface("surf-001")
        assert isinstance(result, tuple)


# ====================================================================
# SESSION TESTS
# ====================================================================


class TestStartConsoleSession:
    def test_start_basic(self):
        es, eng, s, sess = _engine_with_session()
        assert sess.session_id == "sess-001"
        assert sess.tenant_id == "t-001"
        assert sess.identity_ref == "id-001"
        assert sess.surface_ref == "surf-001"
        assert sess.status == ConsoleStatus.ACTIVE
        assert eng.session_count == 1

    def test_start_emits_event(self):
        es, eng, s = _engine_with_surface()
        count_before = es.event_count
        eng.start_console_session("sess-001", "t-001", "id-001", "surf-001")
        assert es.event_count > count_before

    def test_duplicate_session_raises(self):
        es, eng, s, sess = _engine_with_session()
        with pytest.raises(RuntimeCoreInvariantError, match="session already registered"):
            eng.start_console_session("sess-001", "t-001", "id-002", "surf-001")

    def test_unknown_surface_raises(self):
        es, eng = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="unknown surface"):
            eng.start_console_session("sess-001", "t-001", "id-001", "missing-surface")

    def test_closed_surface_blocks_session(self):
        es, eng, s = _engine_with_surface()
        eng.close_surface("surf-001")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal state"):
            eng.start_console_session("sess-001", "t-001", "id-001", "surf-001")

    def test_cross_tenant_session_denied(self):
        es, eng, s = _engine_with_surface()  # surface tenant is t-001
        with pytest.raises(RuntimeCoreInvariantError, match="^cross-tenant access denied$") as exc_info:
            eng.start_console_session("sess-001", "t-002", "id-001", "surf-001")
        assert "sess-001" not in str(exc_info.value)
        assert "t-002" not in str(exc_info.value)
        assert "t-001" not in str(exc_info.value)

    def test_cross_tenant_session_creates_violation(self):
        es, eng, s = _engine_with_surface()
        try:
            eng.start_console_session("sess-001", "t-002", "id-001", "surf-001")
        except RuntimeCoreInvariantError:
            pass
        assert eng.violation_count >= 1
        assert any(v.reason == "cross-tenant access denied" for v in eng._violations.values())

    def test_cross_tenant_session_emits_denial_event(self):
        es, eng, s = _engine_with_surface()
        count_before = es.event_count
        try:
            eng.start_console_session("sess-001", "t-002", "id-001", "surf-001")
        except RuntimeCoreInvariantError:
            pass
        assert es.event_count > count_before

    def test_multiple_sessions_same_surface(self):
        es, eng, s = _engine_with_surface()
        eng.start_console_session("s1", "t-001", "id-001", "surf-001")
        eng.start_console_session("s2", "t-001", "id-002", "surf-001")
        assert eng.session_count == 2

    def test_suspended_surface_allows_session(self):
        es, eng, s = _engine_with_surface()
        eng.suspend_surface("surf-001")
        # SUSPENDED is not terminal
        sess = eng.start_console_session("sess-001", "t-001", "id-001", "surf-001")
        assert sess.status == ConsoleStatus.ACTIVE


class TestEndSession:
    def test_end_active_session(self):
        es, eng, s, sess = _engine_with_session()
        updated = eng.end_session("sess-001")
        assert updated.status == ConsoleStatus.CLOSED

    def test_end_unknown_raises(self):
        es, eng = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="^unknown session$") as exc_info:
            eng.end_session("missing")
        assert "missing" not in str(exc_info.value)

    def test_end_already_closed_raises(self):
        es, eng, s, sess = _engine_with_session()
        eng.end_session("sess-001")
        with pytest.raises(RuntimeCoreInvariantError, match="session not active"):
            eng.end_session("sess-001")

    def test_end_emits_event(self):
        es, eng, s, sess = _engine_with_session()
        count_before = es.event_count
        eng.end_session("sess-001")
        assert es.event_count > count_before

    def test_end_suspended_raises(self):
        es, eng, s, sess = _engine_with_session()
        eng.lock_session("sess-001")
        with pytest.raises(RuntimeCoreInvariantError, match="session not active"):
            eng.end_session("sess-001")


class TestLockSession:
    def test_lock_active_session(self):
        es, eng, s, sess = _engine_with_session()
        updated = eng.lock_session("sess-001")
        assert updated.status == ConsoleStatus.SUSPENDED

    def test_lock_unknown_raises(self):
        es, eng = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="^unknown session$") as exc_info:
            eng.lock_session("missing")
        assert "missing" not in str(exc_info.value)

    def test_lock_closed_raises(self):
        es, eng, s, sess = _engine_with_session()
        eng.end_session("sess-001")
        with pytest.raises(RuntimeCoreInvariantError, match="session not active"):
            eng.lock_session("sess-001")

    def test_lock_emits_event(self):
        es, eng, s, sess = _engine_with_session()
        count_before = es.event_count
        eng.lock_session("sess-001")
        assert es.event_count > count_before


# ====================================================================
# ADMIN ACTION TESTS
# ====================================================================


class TestRecordAdminAction:
    def test_record_basic(self):
        es, eng, act = _engine_with_action()
        assert act.action_id == "act-001"
        assert act.tenant_id == "t-001"
        assert act.session_ref == "sess-001"
        assert act.panel_ref == "panel-001"
        assert act.operation == "update_config"
        assert act.status == AdminActionStatus.PENDING
        assert eng.action_count == 1

    def test_record_emits_event(self):
        es, eng, s = _engine_with_surface()
        eng.register_panel("p1", "t-001", "surf-001", "P", "rt")
        eng.start_console_session("sess-001", "t-001", "id-001", "surf-001")
        count_before = es.event_count
        eng.record_admin_action("act-001", "t-001", "sess-001", "p1", "op")
        assert es.event_count > count_before

    def test_duplicate_action_raises(self):
        es, eng, act = _engine_with_action()
        with pytest.raises(RuntimeCoreInvariantError, match="action already registered"):
            eng.record_admin_action("act-001", "t-001", "sess-001", "panel-001", "op2")

    def test_unknown_session_raises_and_creates_violation(self):
        es, eng, s = _engine_with_surface()
        eng.register_panel("p1", "t-001", "surf-001", "P", "rt")
        with pytest.raises(RuntimeCoreInvariantError, match="^unknown session$") as exc_info:
            eng.record_admin_action("act-001", "t-001", "missing-sess", "p1", "op")
        assert eng.violation_count >= 1
        assert "missing-sess" not in str(exc_info.value)
        assert any(v.reason == "action has no active session" for v in eng._violations.values())
        assert all("missing-sess" not in v.reason for v in eng._violations.values())

    def test_closed_session_raises(self):
        es, eng, act = _engine_with_action()
        eng.end_session("sess-001")
        with pytest.raises(RuntimeCoreInvariantError, match="session not active"):
            eng.record_admin_action("act-002", "t-001", "sess-001", "panel-001", "op2")

    def test_cross_tenant_action_denied(self):
        es, eng, s = _engine_with_surface()
        eng.register_panel("p1", "t-001", "surf-001", "P", "rt")
        eng.start_console_session("sess-001", "t-001", "id-001", "surf-001")
        # Try to record action with different tenant than session
        with pytest.raises(RuntimeCoreInvariantError, match="^cross-tenant access denied$") as exc_info:
            eng.record_admin_action("act-001", "t-002", "sess-001", "p1", "op")
        assert "act-001" not in str(exc_info.value)
        assert "t-002" not in str(exc_info.value)
        assert "t-001" not in str(exc_info.value)

    def test_cross_tenant_action_creates_violation(self):
        es, eng, s = _engine_with_surface()
        eng.register_panel("p1", "t-001", "surf-001", "P", "rt")
        eng.start_console_session("sess-001", "t-001", "id-001", "surf-001")
        try:
            eng.record_admin_action("act-001", "t-002", "sess-001", "p1", "op")
        except RuntimeCoreInvariantError:
            pass
        assert eng.violation_count >= 1
        assert any(v.reason == "cross-tenant access denied" for v in eng._violations.values())

    def test_cross_tenant_action_emits_event(self):
        es, eng, s = _engine_with_surface()
        eng.register_panel("p1", "t-001", "surf-001", "P", "rt")
        eng.start_console_session("sess-001", "t-001", "id-001", "surf-001")
        count_before = es.event_count
        try:
            eng.record_admin_action("act-001", "t-002", "sess-001", "p1", "op")
        except RuntimeCoreInvariantError:
            pass
        assert es.event_count > count_before

    def test_multiple_actions_on_session(self):
        es, eng, act = _engine_with_action()
        act2 = eng.record_admin_action("act-002", "t-001", "sess-001", "panel-001", "delete")
        assert eng.action_count == 2


class TestExecuteAction:
    def test_execute_pending(self):
        es, eng, act = _engine_with_action()
        updated = eng.execute_action("act-001")
        assert updated.status == AdminActionStatus.EXECUTED

    def test_execute_unknown_raises(self):
        es, eng = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="unknown action"):
            eng.execute_action("missing")

    def test_execute_non_pending_raises(self):
        es, eng, act = _engine_with_action()
        eng.execute_action("act-001")
        with pytest.raises(RuntimeCoreInvariantError, match="action not pending"):
            eng.execute_action("act-001")

    def test_execute_denied_raises(self):
        es, eng, act = _engine_with_action()
        eng.deny_action("act-001")
        with pytest.raises(RuntimeCoreInvariantError, match="action not pending"):
            eng.execute_action("act-001")

    def test_execute_emits_event(self):
        es, eng, act = _engine_with_action()
        count_before = es.event_count
        eng.execute_action("act-001")
        assert es.event_count > count_before


class TestDenyAction:
    def test_deny_pending(self):
        es, eng, act = _engine_with_action()
        updated = eng.deny_action("act-001")
        assert updated.status == AdminActionStatus.DENIED

    def test_deny_unknown_raises(self):
        es, eng = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="unknown action"):
            eng.deny_action("missing")

    def test_deny_non_pending_raises(self):
        es, eng, act = _engine_with_action()
        eng.deny_action("act-001")
        with pytest.raises(RuntimeCoreInvariantError, match="action not pending"):
            eng.deny_action("act-001")

    def test_deny_executed_raises(self):
        es, eng, act = _engine_with_action()
        eng.execute_action("act-001")
        with pytest.raises(RuntimeCoreInvariantError, match="action not pending"):
            eng.deny_action("act-001")

    def test_deny_emits_event(self):
        es, eng, act = _engine_with_action()
        count_before = es.event_count
        eng.deny_action("act-001")
        assert es.event_count > count_before


class TestRollbackAction:
    def test_rollback_executed(self):
        es, eng, act = _engine_with_action()
        eng.execute_action("act-001")
        updated = eng.rollback_action("act-001")
        assert updated.status == AdminActionStatus.ROLLED_BACK

    def test_rollback_unknown_raises(self):
        es, eng = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="unknown action"):
            eng.rollback_action("missing")

    def test_rollback_pending_raises(self):
        es, eng, act = _engine_with_action()
        with pytest.raises(RuntimeCoreInvariantError, match="action not executed"):
            eng.rollback_action("act-001")

    def test_rollback_denied_raises(self):
        es, eng, act = _engine_with_action()
        eng.deny_action("act-001")
        with pytest.raises(RuntimeCoreInvariantError, match="action not executed"):
            eng.rollback_action("act-001")

    def test_rollback_already_rolled_back_raises(self):
        es, eng, act = _engine_with_action()
        eng.execute_action("act-001")
        eng.rollback_action("act-001")
        with pytest.raises(RuntimeCoreInvariantError, match="action not executed"):
            eng.rollback_action("act-001")

    def test_rollback_emits_event(self):
        es, eng, act = _engine_with_action()
        eng.execute_action("act-001")
        count_before = es.event_count
        eng.rollback_action("act-001")
        assert es.event_count > count_before


class TestAdminActionStatusTransitions:
    """Validate the allowed state transitions for admin actions."""

    def test_pending_to_executed(self):
        es, eng, act = _engine_with_action()
        updated = eng.execute_action("act-001")
        assert updated.status == AdminActionStatus.EXECUTED

    def test_pending_to_denied(self):
        es, eng, act = _engine_with_action()
        updated = eng.deny_action("act-001")
        assert updated.status == AdminActionStatus.DENIED

    def test_executed_to_rolled_back(self):
        es, eng, act = _engine_with_action()
        eng.execute_action("act-001")
        updated = eng.rollback_action("act-001")
        assert updated.status == AdminActionStatus.ROLLED_BACK

    def test_denied_cannot_execute(self):
        es, eng, act = _engine_with_action()
        eng.deny_action("act-001")
        with pytest.raises(RuntimeCoreInvariantError):
            eng.execute_action("act-001")

    def test_denied_cannot_rollback(self):
        es, eng, act = _engine_with_action()
        eng.deny_action("act-001")
        with pytest.raises(RuntimeCoreInvariantError):
            eng.rollback_action("act-001")

    def test_rolled_back_cannot_execute(self):
        es, eng, act = _engine_with_action()
        eng.execute_action("act-001")
        eng.rollback_action("act-001")
        with pytest.raises(RuntimeCoreInvariantError):
            eng.execute_action("act-001")

    def test_rolled_back_cannot_deny(self):
        es, eng, act = _engine_with_action()
        eng.execute_action("act-001")
        eng.rollback_action("act-001")
        with pytest.raises(RuntimeCoreInvariantError):
            eng.deny_action("act-001")

    def test_rolled_back_cannot_rollback_again(self):
        es, eng, act = _engine_with_action()
        eng.execute_action("act-001")
        eng.rollback_action("act-001")
        with pytest.raises(RuntimeCoreInvariantError):
            eng.rollback_action("act-001")


# ====================================================================
# DECISION TESTS
# ====================================================================


class TestResolveConsoleDecision:
    def test_resolve_basic(self):
        es, eng, act = _engine_with_action()
        d = eng.resolve_console_decision("dec-001", "t-001", "act-001", "approved", "Policy ok")
        assert d.decision_id == "dec-001"
        assert d.tenant_id == "t-001"
        assert d.action_ref == "act-001"
        assert d.disposition == "approved"
        assert d.reason == "Policy ok"
        assert eng.decision_count == 1

    def test_duplicate_decision_raises(self):
        es, eng, act = _engine_with_action()
        eng.resolve_console_decision("dec-001", "t-001", "act-001", "approved", "ok")
        with pytest.raises(RuntimeCoreInvariantError, match="decision already registered"):
            eng.resolve_console_decision("dec-001", "t-001", "act-001", "denied", "dup")

    def test_resolve_emits_event(self):
        es, eng, act = _engine_with_action()
        count_before = es.event_count
        eng.resolve_console_decision("dec-001", "t-001", "act-001", "approved", "ok")
        assert es.event_count > count_before

    def test_multiple_decisions(self):
        es, eng, act = _engine_with_action()
        eng.resolve_console_decision("d1", "t-001", "act-001", "approved", "ok")
        eng.resolve_console_decision("d2", "t-001", "act-001", "reviewed", "second look")
        assert eng.decision_count == 2


# ====================================================================
# ASSESSMENT TESTS
# ====================================================================


class TestConsoleAssessment:
    def test_assessment_basic(self):
        es, eng, act = _engine_with_action()
        a = eng.console_assessment("assess-001", "t-001")
        assert a.assessment_id == "assess-001"
        assert a.tenant_id == "t-001"
        assert isinstance(a, ConsoleAssessment)

    def test_assessment_counts_surfaces(self):
        es, eng = _make_engine()
        eng.register_surface("s1", "t-001", "S1")
        eng.register_surface("s2", "t-001", "S2")
        eng.register_surface("s3", "t-002", "S3")
        a = eng.console_assessment("assess-001", "t-001")
        assert a.total_surfaces == 2

    def test_assessment_counts_active_sessions(self):
        es, eng = _make_engine()
        eng.register_surface("s1", "t-001", "S1")
        eng.start_console_session("sess-a", "t-001", "id-1", "s1")
        eng.start_console_session("sess-b", "t-001", "id-2", "s1")
        eng.end_session("sess-b")
        a = eng.console_assessment("assess-001", "t-001")
        assert a.total_active_sessions == 1

    def test_assessment_success_rate_all_executed(self):
        es, eng, act = _engine_with_action()
        eng.execute_action("act-001")
        a = eng.console_assessment("assess-001", "t-001")
        assert a.action_success_rate == 1.0

    def test_assessment_success_rate_mixed(self):
        es, eng, s = _engine_with_surface()
        eng.register_panel("p1", "t-001", "surf-001", "P", "rt")
        eng.start_console_session("sess-001", "t-001", "id-001", "surf-001")
        eng.record_admin_action("a1", "t-001", "sess-001", "p1", "op1")
        eng.record_admin_action("a2", "t-001", "sess-001", "p1", "op2")
        eng.execute_action("a1")
        eng.deny_action("a2")
        a = eng.console_assessment("assess-001", "t-001")
        assert a.action_success_rate == 0.5

    def test_assessment_success_rate_no_completed_actions(self):
        es, eng, s = _engine_with_surface()
        a = eng.console_assessment("assess-001", "t-001")
        # No actions completed -> default rate 1.0
        assert a.action_success_rate == 1.0

    def test_assessment_success_rate_is_unit_float(self):
        es, eng, act = _engine_with_action()
        eng.execute_action("act-001")
        a = eng.console_assessment("assess-001", "t-001")
        assert 0.0 <= a.action_success_rate <= 1.0

    def test_assessment_emits_event(self):
        es, eng = _make_engine()
        eng.register_surface("s1", "t-001", "S1")
        count_before = es.event_count
        eng.console_assessment("assess-001", "t-001")
        assert es.event_count > count_before

    def test_assessment_with_rollbacks(self):
        es, eng, s = _engine_with_surface()
        eng.register_panel("p1", "t-001", "surf-001", "P", "rt")
        eng.start_console_session("sess-001", "t-001", "id-001", "surf-001")
        eng.record_admin_action("a1", "t-001", "sess-001", "p1", "op1")
        eng.record_admin_action("a2", "t-001", "sess-001", "p1", "op2")
        eng.record_admin_action("a3", "t-001", "sess-001", "p1", "op3")
        eng.execute_action("a1")
        eng.execute_action("a2")
        eng.rollback_action("a2")
        eng.deny_action("a3")
        # executed=1 (a1), denied=1 (a3), rolled_back=1 (a2), denom=3
        a = eng.console_assessment("assess-001", "t-001")
        assert abs(a.action_success_rate - 1.0 / 3.0) < 0.01


# ====================================================================
# SNAPSHOT TESTS
# ====================================================================


class TestConsoleSnapshotEngine:
    def test_snapshot_basic(self):
        es, eng, act = _engine_with_action()
        snap = eng.console_snapshot("snap-001", "t-001")
        assert snap.snapshot_id == "snap-001"
        assert snap.tenant_id == "t-001"
        assert isinstance(snap, ConsoleSnapshot)

    def test_snapshot_counts(self):
        es, eng, s = _engine_with_surface()
        eng.register_panel("p1", "t-001", "surf-001", "P", "rt")
        eng.start_console_session("sess-001", "t-001", "id-001", "surf-001")
        eng.record_admin_action("a1", "t-001", "sess-001", "p1", "op")
        snap = eng.console_snapshot("snap-001", "t-001")
        assert snap.total_surfaces == 1
        assert snap.total_panels == 1
        assert snap.total_sessions == 1
        assert snap.total_actions == 1
        assert snap.total_violations == 0

    def test_snapshot_filters_by_tenant(self):
        es, eng = _make_engine()
        eng.register_surface("s1", "t-001", "S1")
        eng.register_surface("s2", "t-002", "S2")
        snap = eng.console_snapshot("snap-001", "t-001")
        assert snap.total_surfaces == 1

    def test_snapshot_emits_event(self):
        es, eng, s = _engine_with_surface()
        count_before = es.event_count
        eng.console_snapshot("snap-001", "t-001")
        assert es.event_count > count_before


# ====================================================================
# VIOLATION DETECTION TESTS
# ====================================================================


class TestDetectConsoleViolations:
    def test_no_violations_clean_state(self):
        es, eng, s, sess = _engine_with_session()
        result = eng.detect_console_violations("t-001")
        assert len(result) == 0

    def test_session_on_closed_surface_detected(self):
        es, eng, s = _engine_with_surface()
        eng.start_console_session("sess-001", "t-001", "id-001", "surf-001")
        eng.close_surface("surf-001")
        # Now active session on closed surface
        result = eng.detect_console_violations("t-001")
        assert len(result) >= 1
        assert any(v.reason == "active session on closed surface" for v in result)
        assert all("sess-001" not in v.reason for v in result)
        assert all("surf-001" not in v.reason for v in result)

    def test_action_no_session_detected(self):
        es, eng, act = _engine_with_action()
        eng.end_session("sess-001")
        result = eng.detect_console_violations("t-001")
        assert len(result) >= 1
        assert any(v.reason == "action has no active session" for v in result)
        assert all("act-001" not in v.reason for v in result)
        assert all("sess-001" not in v.reason for v in result)

    def test_idempotent_detection(self):
        es, eng, s = _engine_with_surface()
        eng.start_console_session("sess-001", "t-001", "id-001", "surf-001")
        eng.close_surface("surf-001")
        r1 = eng.detect_console_violations("t-001")
        r2 = eng.detect_console_violations("t-001")
        # Second call returns empty since violations already recorded
        assert len(r2) == 0
        # But violation count is still there
        assert eng.violation_count >= 1

    def test_violations_scoped_to_tenant(self):
        es, eng = _make_engine()
        eng.register_surface("s1", "t-001", "S1")
        eng.register_surface("s2", "t-002", "S2")
        eng.start_console_session("sess-001", "t-001", "id-001", "s1")
        eng.close_surface("s1")
        # detect for t-002 should not find t-001's violations
        result = eng.detect_console_violations("t-002")
        assert len(result) == 0

    def test_returns_tuple(self):
        es, eng, s = _engine_with_surface()
        result = eng.detect_console_violations("t-001")
        assert isinstance(result, tuple)


# ====================================================================
# CLOSURE REPORT TESTS
# ====================================================================


class TestConsoleClosureReportEngine:
    def test_closure_report_basic(self):
        es, eng, act = _engine_with_action()
        r = eng.console_closure_report("rpt-001", "t-001")
        assert r.report_id == "rpt-001"
        assert r.tenant_id == "t-001"
        assert isinstance(r, ConsoleClosureReport)

    def test_closure_report_counts(self):
        es, eng, s = _engine_with_surface()
        eng.register_panel("p1", "t-001", "surf-001", "P", "rt")
        eng.start_console_session("sess-001", "t-001", "id-001", "surf-001")
        eng.record_admin_action("a1", "t-001", "sess-001", "p1", "op")
        r = eng.console_closure_report("rpt-001", "t-001")
        assert r.total_surfaces == 1
        assert r.total_panels == 1
        assert r.total_sessions == 1
        assert r.total_actions == 1

    def test_closure_report_filters_by_tenant(self):
        es, eng = _make_engine()
        eng.register_surface("s1", "t-001", "S1")
        eng.register_surface("s2", "t-002", "S2")
        r = eng.console_closure_report("rpt-001", "t-001")
        assert r.total_surfaces == 1


# ====================================================================
# PERSISTENCE PROTOCOL TESTS
# ====================================================================


class TestPersistenceProtocol:
    def test_snapshot_returns_dict(self):
        es, eng, act = _engine_with_action()
        snap = eng.snapshot()
        assert isinstance(snap, dict)
        assert "surfaces" in snap
        assert "nodes" in snap
        assert "panels" in snap
        assert "sessions" in snap
        assert "actions" in snap
        assert "decisions" in snap
        assert "violations" in snap

    def test_snapshot_surfaces_serialized(self):
        es, eng, s = _engine_with_surface()
        snap = eng.snapshot()
        assert "surf-001" in snap["surfaces"]
        assert snap["surfaces"]["surf-001"]["surface_id"] == "surf-001"

    def test_state_hash_deterministic(self):
        es, eng, act = _engine_with_action()
        h1 = eng.state_hash()
        h2 = eng.state_hash()
        assert h1 == h2

    def test_state_hash_changes_on_mutation(self):
        es, eng, s = _engine_with_surface()
        h1 = eng.state_hash()
        eng.register_surface("s2", "t-001", "S2")
        h2 = eng.state_hash()
        assert h1 != h2

    def test_state_hash_is_hex_sha256(self):
        es, eng, s = _engine_with_surface()
        h = eng.state_hash()
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_empty_engine_state_hash(self):
        es, eng = _make_engine()
        h = eng.state_hash()
        assert isinstance(h, str)
        assert len(h) == 64


# ====================================================================
# FIXED CLOCK / REPLAY TESTS
# ====================================================================


class TestFixedClockReplay:
    def test_fixed_clock_surface_timestamp(self):
        clk = FixedClock("2026-06-15T10:00:00+00:00")
        es, eng = _make_engine(clock=clk)
        s = eng.register_surface("s1", "t-001", "S1")
        assert s.created_at == "2026-06-15T10:00:00+00:00"

    def test_fixed_clock_session_timestamp(self):
        clk = FixedClock("2026-06-15T10:00:00+00:00")
        es, eng = _make_engine(clock=clk)
        eng.register_surface("s1", "t-001", "S1")
        sess = eng.start_console_session("sess-001", "t-001", "id-001", "s1")
        assert sess.started_at == "2026-06-15T10:00:00+00:00"

    def test_replay_same_ops_same_state_hash(self):
        """Same operations with same clock produce identical state_hash."""
        def run_ops():
            clk = FixedClock("2026-01-01T00:00:00+00:00")
            es = EventSpineEngine()
            eng = ProductConsoleEngine(es, clock=clk)
            eng.register_surface("s1", "t-001", "S1")
            eng.register_panel("p1", "t-001", "s1", "P1", "rt")
            eng.register_navigation_node("n1", "t-001", "s1", "Nav")
            eng.start_console_session("sess-001", "t-001", "id-001", "s1")
            eng.record_admin_action("a1", "t-001", "sess-001", "p1", "op")
            eng.execute_action("a1")
            eng.resolve_console_decision("d1", "t-001", "a1", "ok", "reason")
            return eng.state_hash()

        h1 = run_ops()
        h2 = run_ops()
        assert h1 == h2

    def test_clock_advance(self):
        clk = FixedClock("2026-01-01T00:00:00+00:00")
        es, eng = _make_engine(clock=clk)
        s1 = eng.register_surface("s1", "t-001", "S1")
        assert s1.created_at == "2026-01-01T00:00:00+00:00"

        clk.advance("2026-06-01T12:00:00+00:00")
        s2 = eng.register_surface("s2", "t-001", "S2")
        assert s2.created_at == "2026-06-01T12:00:00+00:00"


# ====================================================================
# GOLDEN SCENARIOS
# ====================================================================


class TestGoldenScenarioTenantAdmin:
    """Tenant admin sees only tenant-scoped surfaces."""

    def test_tenant_admin_sees_only_own_surfaces(self):
        es, eng = _make_engine()
        eng.register_surface("s1", "t-001", "Tenant 1 Admin")
        eng.register_surface("s2", "t-001", "Tenant 1 Ops")
        eng.register_surface("s3", "t-002", "Tenant 2 Admin")
        result = eng.surfaces_for_tenant("t-001")
        assert len(result) == 2
        assert all(s.tenant_id == "t-001" for s in result)

    def test_tenant_cannot_see_other_tenant_surfaces(self):
        es, eng = _make_engine()
        eng.register_surface("s1", "t-001", "Tenant 1")
        eng.register_surface("s2", "t-002", "Tenant 2")
        result = eng.surfaces_for_tenant("t-001")
        assert len(result) == 1
        assert result[0].tenant_id == "t-001"


class TestGoldenScenarioWorkspaceAdmin:
    """Workspace admin manages allowed panels."""

    def test_workspace_admin_manages_panels(self):
        es, eng = _make_engine()
        eng.register_surface("s1", "t-001", "Workspace Console",
                             role=ConsoleRole.WORKSPACE_ADMIN)
        eng.register_panel("p1", "t-001", "s1", "User Mgmt", "workforce_runtime")
        eng.register_panel("p2", "t-001", "s1", "Settings", "workforce_runtime")
        panels = eng.panels_for_surface("s1")
        assert len(panels) == 2
        assert all(p.surface_ref == "s1" for p in panels)

    def test_workspace_admin_surface_role(self):
        es, eng = _make_engine()
        s = eng.register_surface("s1", "t-001", "WS Admin",
                                 role=ConsoleRole.WORKSPACE_ADMIN)
        assert s.role == ConsoleRole.WORKSPACE_ADMIN


class TestGoldenScenarioCrossTenantDenied:
    """Cross-tenant admin action denied fail-closed."""

    def test_cross_tenant_session_denied_fail_closed(self):
        es, eng = _make_engine()
        eng.register_surface("s1", "t-001", "Tenant 1 Surface")
        with pytest.raises(RuntimeCoreInvariantError, match="cross-tenant"):
            eng.start_console_session("sess-001", "t-002", "id-001", "s1")
        assert eng.session_count == 0
        assert eng.violation_count >= 1

    def test_cross_tenant_action_denied_fail_closed(self):
        es, eng = _make_engine()
        eng.register_surface("s1", "t-001", "S1")
        eng.register_panel("p1", "t-001", "s1", "P", "rt")
        eng.start_console_session("sess-001", "t-001", "id-001", "s1")
        with pytest.raises(RuntimeCoreInvariantError, match="cross-tenant"):
            eng.record_admin_action("act-001", "t-002", "sess-001", "p1", "op")
        assert eng.action_count == 0
        assert eng.violation_count >= 1


class TestGoldenScenarioBillingAdmin:
    """Billing admin surface shows financial actions."""

    def test_billing_admin_surface(self):
        es, eng = _make_engine()
        s = eng.register_surface("billing-s1", "t-001", "Billing Console",
                                 role=ConsoleRole.TENANT_ADMIN)
        p = eng.register_panel("billing-p1", "t-001", "billing-s1",
                               "Financial Actions", "billing_settlement")
        assert p.target_runtime == "billing_settlement"
        assert s.role == ConsoleRole.TENANT_ADMIN

    def test_billing_admin_session_and_action(self):
        es, eng = _make_engine()
        eng.register_surface("bs", "t-001", "Billing", role=ConsoleRole.TENANT_ADMIN)
        eng.register_panel("bp", "t-001", "bs", "Financial", "billing_settlement")
        eng.start_console_session("bsess", "t-001", "admin-id", "bs")
        act = eng.record_admin_action("bact", "t-001", "bsess", "bp", "approve_invoice")
        assert act.operation == "approve_invoice"
        eng.execute_action("bact")
        assert eng.action_count == 1


class TestGoldenScenarioGovernanceAdmin:
    """Governance admin panel exposes constitutional state."""

    def test_governance_admin_surface(self):
        es, eng = _make_engine()
        s = eng.register_surface("gov-s1", "t-001", "Governance Console",
                                 role=ConsoleRole.COMPLIANCE_VIEWER)
        p = eng.register_panel("gov-p1", "t-001", "gov-s1",
                               "Constitution", "constitutional_governance",
                               view_mode=ViewMode.READ_ONLY)
        assert s.role == ConsoleRole.COMPLIANCE_VIEWER
        assert p.view_mode == ViewMode.READ_ONLY
        assert p.target_runtime == "constitutional_governance"

    def test_governance_session_read_only(self):
        es, eng = _make_engine()
        eng.register_surface("gs", "t-001", "Gov", role=ConsoleRole.COMPLIANCE_VIEWER)
        eng.register_panel("gp", "t-001", "gs", "Policy",
                           "constitutional_governance", view_mode=ViewMode.READ_ONLY)
        sess = eng.start_console_session("gsess", "t-001", "viewer-id", "gs")
        act = eng.record_admin_action("gact", "t-001", "gsess", "gp", "view_policies")
        assert act.operation == "view_policies"


class TestGoldenScenarioReplayDeterminism:
    """Replay with FixedClock: same ops produce same state_hash."""

    def test_full_scenario_replay(self):
        def scenario():
            clk = FixedClock("2026-01-01T00:00:00+00:00")
            es = EventSpineEngine()
            eng = ProductConsoleEngine(es, clock=clk)
            # Register surfaces for two tenants
            eng.register_surface("s1", "t-001", "Tenant 1 Admin")
            eng.register_surface("s2", "t-001", "Tenant 1 Ops")
            eng.register_surface("s3", "t-002", "Tenant 2 Admin")
            # Register panels
            eng.register_panel("p1", "t-001", "s1", "Config", "runtime_a")
            eng.register_panel("p2", "t-002", "s3", "Config", "runtime_b")
            # Register nav nodes
            eng.register_navigation_node("n1", "t-001", "s1", "Dashboard")
            eng.register_navigation_node("n2", "t-001", "s1", "Settings", order=1)
            # Sessions
            eng.start_console_session("sess-001", "t-001", "admin-1", "s1")
            eng.start_console_session("sess-002", "t-002", "admin-2", "s3")
            # Actions
            eng.record_admin_action("a1", "t-001", "sess-001", "p1", "update")
            eng.record_admin_action("a2", "t-002", "sess-002", "p2", "create")
            eng.execute_action("a1")
            eng.deny_action("a2")
            # Decision
            eng.resolve_console_decision("d1", "t-001", "a1", "approved", "ok")
            return eng.state_hash()

        h1 = scenario()
        h2 = scenario()
        assert h1 == h2

    def test_different_ops_different_hash(self):
        clk1 = FixedClock("2026-01-01T00:00:00+00:00")
        es1 = EventSpineEngine()
        eng1 = ProductConsoleEngine(es1, clock=clk1)
        eng1.register_surface("s1", "t-001", "S1")

        clk2 = FixedClock("2026-01-01T00:00:00+00:00")
        es2 = EventSpineEngine()
        eng2 = ProductConsoleEngine(es2, clock=clk2)
        eng2.register_surface("s1", "t-001", "S1")
        eng2.register_surface("s2", "t-001", "S2")

        assert eng1.state_hash() != eng2.state_hash()


# ====================================================================
# TERMINAL STATE ENFORCEMENT
# ====================================================================


class TestTerminalStateEnforcement:
    def test_closed_surface_blocks_new_sessions(self):
        es, eng, s = _engine_with_surface()
        eng.close_surface("surf-001")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal state"):
            eng.start_console_session("sess-001", "t-001", "id-001", "surf-001")

    def test_closed_surface_blocks_suspend(self):
        es, eng, s = _engine_with_surface()
        eng.close_surface("surf-001")
        with pytest.raises(RuntimeCoreInvariantError):
            eng.suspend_surface("surf-001")

    def test_closed_surface_blocks_activate(self):
        es, eng, s = _engine_with_surface()
        eng.close_surface("surf-001")
        with pytest.raises(RuntimeCoreInvariantError):
            eng.activate_surface("surf-001")

    def test_closed_surface_blocks_close_again(self):
        es, eng, s = _engine_with_surface()
        eng.close_surface("surf-001")
        with pytest.raises(RuntimeCoreInvariantError):
            eng.close_surface("surf-001")


# ====================================================================
# MULTI-TENANT ISOLATION
# ====================================================================


class TestMultiTenantIsolation:
    def test_surfaces_isolated_by_tenant(self):
        es, eng = _make_engine()
        eng.register_surface("s1", "t-001", "T1 Surface")
        eng.register_surface("s2", "t-002", "T2 Surface")
        assert len(eng.surfaces_for_tenant("t-001")) == 1
        assert len(eng.surfaces_for_tenant("t-002")) == 1
        assert len(eng.surfaces_for_tenant("t-003")) == 0

    def test_snapshot_isolated_by_tenant(self):
        es, eng = _make_engine()
        eng.register_surface("s1", "t-001", "T1")
        eng.register_surface("s2", "t-002", "T2")
        snap1 = eng.console_snapshot("snap-1", "t-001")
        snap2 = eng.console_snapshot("snap-2", "t-002")
        assert snap1.total_surfaces == 1
        assert snap2.total_surfaces == 1

    def test_assessment_isolated_by_tenant(self):
        es, eng = _make_engine()
        eng.register_surface("s1", "t-001", "T1")
        eng.register_surface("s2", "t-002", "T2")
        a1 = eng.console_assessment("a1", "t-001")
        a2 = eng.console_assessment("a2", "t-002")
        assert a1.total_surfaces == 1
        assert a2.total_surfaces == 1

    def test_closure_report_isolated_by_tenant(self):
        es, eng = _make_engine()
        eng.register_surface("s1", "t-001", "T1")
        eng.register_surface("s2", "t-002", "T2")
        r1 = eng.console_closure_report("r1", "t-001")
        r2 = eng.console_closure_report("r2", "t-002")
        assert r1.total_surfaces == 1
        assert r2.total_surfaces == 1

    def test_violation_detection_isolated(self):
        es, eng = _make_engine()
        eng.register_surface("s1", "t-001", "S1")
        eng.start_console_session("sess-001", "t-001", "id-001", "s1")
        eng.close_surface("s1")
        v1 = eng.detect_console_violations("t-001")
        v2 = eng.detect_console_violations("t-002")
        assert len(v1) >= 1
        assert len(v2) == 0


# ====================================================================
# EVENT EMISSION COUNTS
# ====================================================================


class TestEventEmission:
    def test_register_surface_emits(self):
        es = EventSpineEngine()
        eng = ProductConsoleEngine(es, clock=FixedClock())
        eng.register_surface("s1", "t-001", "S1")
        assert es.event_count >= 1

    def test_multiple_ops_accumulate_events(self):
        es = EventSpineEngine()
        eng = ProductConsoleEngine(es, clock=FixedClock())
        eng.register_surface("s1", "t-001", "S1")
        eng.register_panel("p1", "t-001", "s1", "P", "rt")
        eng.register_navigation_node("n1", "t-001", "s1", "N")
        eng.start_console_session("sess-001", "t-001", "id-001", "s1")
        eng.record_admin_action("a1", "t-001", "sess-001", "p1", "op")
        eng.execute_action("a1")
        eng.resolve_console_decision("d1", "t-001", "a1", "ok", "reason")
        # Each operation emits at least 1 event
        assert es.event_count >= 7


# ====================================================================
# PROPERTY COUNT TESTS
# ====================================================================


class TestPropertyCounts:
    def test_surface_count_tracks(self):
        es, eng = _make_engine()
        assert eng.surface_count == 0
        eng.register_surface("s1", "t-001", "S1")
        assert eng.surface_count == 1
        eng.register_surface("s2", "t-001", "S2")
        assert eng.surface_count == 2

    def test_node_count_tracks(self):
        es, eng = _make_engine()
        assert eng.node_count == 0
        eng.register_surface("s1", "t-001", "S1")
        eng.register_navigation_node("n1", "t-001", "s1", "N")
        assert eng.node_count == 1

    def test_panel_count_tracks(self):
        es, eng = _make_engine()
        assert eng.panel_count == 0
        eng.register_surface("s1", "t-001", "S1")
        eng.register_panel("p1", "t-001", "s1", "P", "rt")
        assert eng.panel_count == 1

    def test_session_count_tracks(self):
        es, eng = _make_engine()
        assert eng.session_count == 0
        eng.register_surface("s1", "t-001", "S1")
        eng.start_console_session("sess-001", "t-001", "id-001", "s1")
        assert eng.session_count == 1

    def test_action_count_tracks(self):
        es, eng, act = _engine_with_action()
        assert eng.action_count == 1

    def test_decision_count_tracks(self):
        es, eng, act = _engine_with_action()
        assert eng.decision_count == 0
        eng.resolve_console_decision("d1", "t-001", "act-001", "ok", "reason")
        assert eng.decision_count == 1

    def test_violation_count_tracks(self):
        es, eng, s = _engine_with_surface()
        assert eng.violation_count == 0
        try:
            eng.start_console_session("sess-001", "t-002", "id-001", "surf-001")
        except RuntimeCoreInvariantError:
            pass
        assert eng.violation_count >= 1


# ====================================================================
# EDGE CASES
# ====================================================================


class TestEdgeCases:
    def test_suspend_then_close(self):
        es, eng, s = _engine_with_surface()
        eng.suspend_surface("surf-001")
        eng.close_surface("surf-001")
        assert eng.get_surface("surf-001").status == ConsoleStatus.CLOSED

    def test_activate_then_suspend_cycle(self):
        es, eng, s = _engine_with_surface()
        eng.suspend_surface("surf-001")
        eng.activate_surface("surf-001")
        eng.suspend_surface("surf-001")
        eng.activate_surface("surf-001")
        assert eng.get_surface("surf-001").status == ConsoleStatus.ACTIVE

    def test_many_surfaces_same_tenant(self):
        es, eng = _make_engine()
        for i in range(20):
            eng.register_surface(f"s-{i}", "t-001", f"Surface {i}")
        assert eng.surface_count == 20
        assert len(eng.surfaces_for_tenant("t-001")) == 20

    def test_many_panels_same_surface(self):
        es, eng, s = _engine_with_surface()
        for i in range(15):
            eng.register_panel(f"p-{i}", "t-001", "surf-001", f"Panel {i}", "rt")
        assert eng.panel_count == 15
        assert len(eng.panels_for_surface("surf-001")) == 15

    def test_session_on_suspended_surface_allowed(self):
        es, eng, s = _engine_with_surface()
        eng.suspend_surface("surf-001")
        sess = eng.start_console_session("sess-001", "t-001", "id-001", "surf-001")
        assert sess.status == ConsoleStatus.ACTIVE

    def test_locked_session_cannot_record_action(self):
        es, eng, s = _engine_with_surface()
        eng.register_panel("p1", "t-001", "surf-001", "P", "rt")
        eng.start_console_session("sess-001", "t-001", "id-001", "surf-001")
        eng.lock_session("sess-001")
        with pytest.raises(RuntimeCoreInvariantError, match="session not active"):
            eng.record_admin_action("act-001", "t-001", "sess-001", "p1", "op")

    def test_state_hash_empty_engine(self):
        es, eng = _make_engine()
        h = eng.state_hash()
        assert isinstance(h, str)
        assert len(h) == 64

    def test_snapshot_empty_engine(self):
        es, eng = _make_engine()
        snap = eng.snapshot()
        assert snap["surfaces"] == {}
        assert snap["nodes"] == {}
        assert snap["panels"] == {}
        assert snap["sessions"] == {}
        assert snap["actions"] == {}
        assert snap["decisions"] == {}
        assert snap["violations"] == {}


class TestBoundedContracts:
    def test_activate_surface_message_hides_current_status(self):
        es, eng, s = _engine_with_surface()
        with pytest.raises(RuntimeCoreInvariantError, match="activate_surface requires SUSPENDED state") as exc_info:
            eng.activate_surface("surf-001")
        assert "ACTIVE" not in str(exc_info.value)

    def test_unknown_action_message_hides_action_id(self):
        es, eng = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="unknown action") as exc_info:
            eng.execute_action("action-secret")
        assert "action-secret" not in str(exc_info.value)
