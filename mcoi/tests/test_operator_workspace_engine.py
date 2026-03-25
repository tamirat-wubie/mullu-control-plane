"""Comprehensive tests for OperatorWorkspaceEngine.

Covers: views, panels, queues, worklist, operator actions, decisions,
snapshots, assessments, violation detection, closure reports, state hash,
count properties, and 6+ golden end-to-end scenarios.

Target: ~350 tests.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.operator_workspace import OperatorWorkspaceEngine
from mcoi_runtime.contracts.operator_workspace import (
    OperatorAction,
    OperatorActionStatus,
    PanelKind,
    QueueRecord,
    QueueStatus,
    ViewDisposition,
    WorklistItem,
    WorkspaceAssessment,
    WorkspaceClosureReport,
    WorkspaceDecision,
    WorkspacePanel,
    WorkspaceScope,
    WorkspaceSnapshot,
    WorkspaceStatus,
    WorkspaceView,
    WorkspaceViolation,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture()
def es() -> EventSpineEngine:
    return EventSpineEngine()


@pytest.fixture()
def engine(es: EventSpineEngine) -> OperatorWorkspaceEngine:
    return OperatorWorkspaceEngine(es)


@pytest.fixture()
def engine_with_view(engine: OperatorWorkspaceEngine) -> OperatorWorkspaceEngine:
    """Engine pre-loaded with one active view."""
    engine.register_view("v1", "t1", "op1", "Main View", WorkspaceScope.PERSONAL)
    return engine


@pytest.fixture()
def engine_with_panel(engine_with_view: OperatorWorkspaceEngine) -> OperatorWorkspaceEngine:
    """Engine pre-loaded with one view and one panel."""
    engine_with_view.register_panel("p1", "v1", "t1", "Queue Panel", PanelKind.QUEUE, "rt1")
    return engine_with_view


@pytest.fixture()
def engine_with_queue_item(engine_with_panel: OperatorWorkspaceEngine) -> OperatorWorkspaceEngine:
    """Engine pre-loaded with view, panel, and one queue item."""
    engine_with_panel.enqueue_item("q1", "p1", "t1", "src1", "rt1", "assignee1", 3)
    return engine_with_panel


# ===================================================================
# Construction
# ===================================================================


class TestConstruction:
    def test_requires_event_spine(self):
        with pytest.raises(RuntimeCoreInvariantError):
            OperatorWorkspaceEngine("not-an-engine")

    def test_requires_event_spine_none(self):
        with pytest.raises(RuntimeCoreInvariantError):
            OperatorWorkspaceEngine(None)

    def test_requires_event_spine_int(self):
        with pytest.raises(RuntimeCoreInvariantError):
            OperatorWorkspaceEngine(42)

    def test_initial_counts_zero(self, engine: OperatorWorkspaceEngine):
        assert engine.view_count == 0
        assert engine.panel_count == 0
        assert engine.queue_count == 0
        assert engine.worklist_count == 0
        assert engine.action_count == 0
        assert engine.decision_count == 0
        assert engine.violation_count == 0
        assert engine.assessment_count == 0

    def test_accepts_valid_event_spine(self, es: EventSpineEngine):
        eng = OperatorWorkspaceEngine(es)
        assert eng.view_count == 0


# ===================================================================
# Views — register_view
# ===================================================================


class TestRegisterView:
    def test_register_returns_view(self, engine: OperatorWorkspaceEngine):
        v = engine.register_view("v1", "t1", "op1", "View One", WorkspaceScope.PERSONAL)
        assert isinstance(v, WorkspaceView)

    def test_register_view_fields(self, engine: OperatorWorkspaceEngine):
        v = engine.register_view("v1", "t1", "op1", "View One", WorkspaceScope.PERSONAL)
        assert v.view_id == "v1"
        assert v.tenant_id == "t1"
        assert v.operator_ref == "op1"
        assert v.display_name == "View One"
        assert v.scope == WorkspaceScope.PERSONAL

    def test_register_view_status_active(self, engine: OperatorWorkspaceEngine):
        v = engine.register_view("v1", "t1", "op1", "V", WorkspaceScope.PERSONAL)
        assert v.status == WorkspaceStatus.ACTIVE

    def test_register_view_disposition_open(self, engine: OperatorWorkspaceEngine):
        v = engine.register_view("v1", "t1", "op1", "V", WorkspaceScope.PERSONAL)
        assert v.disposition == ViewDisposition.OPEN

    def test_register_view_panel_count_zero(self, engine: OperatorWorkspaceEngine):
        v = engine.register_view("v1", "t1", "op1", "V", WorkspaceScope.PERSONAL)
        assert v.panel_count == 0

    def test_register_view_increments_count(self, engine: OperatorWorkspaceEngine):
        engine.register_view("v1", "t1", "op1", "V", WorkspaceScope.PERSONAL)
        assert engine.view_count == 1

    def test_register_view_duplicate_raises(self, engine: OperatorWorkspaceEngine):
        engine.register_view("v1", "t1", "op1", "V", WorkspaceScope.PERSONAL)
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate"):
            engine.register_view("v1", "t1", "op1", "V2", WorkspaceScope.PERSONAL)

    def test_register_view_different_ids(self, engine: OperatorWorkspaceEngine):
        engine.register_view("v1", "t1", "op1", "V1", WorkspaceScope.PERSONAL)
        engine.register_view("v2", "t1", "op1", "V2", WorkspaceScope.TEAM)
        assert engine.view_count == 2

    def test_register_view_tenant_scope(self, engine: OperatorWorkspaceEngine):
        v = engine.register_view("v1", "t1", "op1", "V", WorkspaceScope.TENANT)
        assert v.scope == WorkspaceScope.TENANT

    def test_register_view_executive_scope(self, engine: OperatorWorkspaceEngine):
        v = engine.register_view("v1", "t1", "op1", "V", WorkspaceScope.EXECUTIVE)
        assert v.scope == WorkspaceScope.EXECUTIVE

    def test_register_view_global_scope(self, engine: OperatorWorkspaceEngine):
        v = engine.register_view("v1", "t1", "op1", "V", WorkspaceScope.GLOBAL)
        assert v.scope == WorkspaceScope.GLOBAL

    def test_register_view_workspace_scope(self, engine: OperatorWorkspaceEngine):
        v = engine.register_view("v1", "t1", "op1", "V", WorkspaceScope.WORKSPACE)
        assert v.scope == WorkspaceScope.WORKSPACE

    def test_register_view_team_scope(self, engine: OperatorWorkspaceEngine):
        v = engine.register_view("v1", "t1", "op1", "V", WorkspaceScope.TEAM)
        assert v.scope == WorkspaceScope.TEAM

    def test_register_view_has_created_at(self, engine: OperatorWorkspaceEngine):
        v = engine.register_view("v1", "t1", "op1", "V", WorkspaceScope.PERSONAL)
        assert v.created_at  # non-empty

    def test_register_view_emits_event(self, es: EventSpineEngine, engine: OperatorWorkspaceEngine):
        engine.register_view("v1", "t1", "op1", "V", WorkspaceScope.PERSONAL)
        assert es.event_count >= 1

    def test_register_multiple_views(self, engine: OperatorWorkspaceEngine):
        for i in range(10):
            engine.register_view(f"v{i}", "t1", "op1", f"V{i}", WorkspaceScope.PERSONAL)
        assert engine.view_count == 10

    def test_register_view_default_scope(self, engine: OperatorWorkspaceEngine):
        v = engine.register_view("v1", "t1", "op1", "V")
        assert v.scope == WorkspaceScope.PERSONAL


# ===================================================================
# Views — get_view
# ===================================================================


class TestGetView:
    def test_get_existing_view(self, engine_with_view: OperatorWorkspaceEngine):
        v = engine_with_view.get_view("v1")
        assert v.view_id == "v1"

    def test_get_unknown_view_raises(self, engine: OperatorWorkspaceEngine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown"):
            engine.get_view("nonexist")

    def test_get_view_returns_same_data(self, engine_with_view: OperatorWorkspaceEngine):
        v = engine_with_view.get_view("v1")
        assert v.tenant_id == "t1"
        assert v.operator_ref == "op1"

    def test_get_view_frozen(self, engine_with_view: OperatorWorkspaceEngine):
        v = engine_with_view.get_view("v1")
        with pytest.raises(AttributeError):
            v.view_id = "changed"


# ===================================================================
# Views — suspend_view
# ===================================================================


class TestSuspendView:
    def test_suspend_active_view(self, engine_with_view: OperatorWorkspaceEngine):
        v = engine_with_view.suspend_view("v1")
        assert v.status == WorkspaceStatus.SUSPENDED

    def test_suspend_unknown_raises(self, engine: OperatorWorkspaceEngine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown"):
            engine.suspend_view("nonexist")

    def test_suspend_retired_raises(self, engine_with_view: OperatorWorkspaceEngine):
        engine_with_view.retire_view("v1")
        with pytest.raises(RuntimeCoreInvariantError, match="retired"):
            engine_with_view.suspend_view("v1")

    def test_suspend_preserves_fields(self, engine_with_view: OperatorWorkspaceEngine):
        v = engine_with_view.suspend_view("v1")
        assert v.tenant_id == "t1"
        assert v.operator_ref == "op1"
        assert v.display_name == "Main View"

    def test_suspend_emits_event(self, es: EventSpineEngine, engine: OperatorWorkspaceEngine):
        engine.register_view("v1", "t1", "op1", "V", WorkspaceScope.PERSONAL)
        before = es.event_count
        engine.suspend_view("v1")
        assert es.event_count > before

    def test_double_suspend_ok(self, engine_with_view: OperatorWorkspaceEngine):
        engine_with_view.suspend_view("v1")
        v = engine_with_view.suspend_view("v1")
        assert v.status == WorkspaceStatus.SUSPENDED


# ===================================================================
# Views — retire_view
# ===================================================================


class TestRetireView:
    def test_retire_active_view(self, engine_with_view: OperatorWorkspaceEngine):
        v = engine_with_view.retire_view("v1")
        assert v.status == WorkspaceStatus.RETIRED

    def test_retire_sets_archived_disposition(self, engine_with_view: OperatorWorkspaceEngine):
        v = engine_with_view.retire_view("v1")
        assert v.disposition == ViewDisposition.ARCHIVED

    def test_retire_unknown_raises(self, engine: OperatorWorkspaceEngine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown"):
            engine.retire_view("nonexist")

    def test_retire_already_retired_raises(self, engine_with_view: OperatorWorkspaceEngine):
        engine_with_view.retire_view("v1")
        with pytest.raises(RuntimeCoreInvariantError, match="already retired"):
            engine_with_view.retire_view("v1")

    def test_retire_suspended_view_ok(self, engine_with_view: OperatorWorkspaceEngine):
        engine_with_view.suspend_view("v1")
        v = engine_with_view.retire_view("v1")
        assert v.status == WorkspaceStatus.RETIRED

    def test_retire_emits_event(self, es: EventSpineEngine, engine: OperatorWorkspaceEngine):
        engine.register_view("v1", "t1", "op1", "V", WorkspaceScope.PERSONAL)
        before = es.event_count
        engine.retire_view("v1")
        assert es.event_count > before

    def test_retire_preserves_fields(self, engine_with_view: OperatorWorkspaceEngine):
        v = engine_with_view.retire_view("v1")
        assert v.tenant_id == "t1"
        assert v.operator_ref == "op1"


# ===================================================================
# Views — views_for_tenant, views_for_operator
# ===================================================================


class TestViewQueries:
    def test_views_for_tenant_empty(self, engine: OperatorWorkspaceEngine):
        assert engine.views_for_tenant("t1") == ()

    def test_views_for_tenant_returns_tuple(self, engine_with_view: OperatorWorkspaceEngine):
        result = engine_with_view.views_for_tenant("t1")
        assert isinstance(result, tuple)
        assert len(result) == 1

    def test_views_for_tenant_filters(self, engine: OperatorWorkspaceEngine):
        engine.register_view("v1", "t1", "op1", "V1")
        engine.register_view("v2", "t2", "op2", "V2")
        assert len(engine.views_for_tenant("t1")) == 1
        assert len(engine.views_for_tenant("t2")) == 1

    def test_views_for_tenant_multiple(self, engine: OperatorWorkspaceEngine):
        engine.register_view("v1", "t1", "op1", "V1")
        engine.register_view("v2", "t1", "op2", "V2")
        assert len(engine.views_for_tenant("t1")) == 2

    def test_views_for_operator_empty(self, engine: OperatorWorkspaceEngine):
        assert engine.views_for_operator("t1", "op1") == ()

    def test_views_for_operator_returns_tuple(self, engine_with_view: OperatorWorkspaceEngine):
        result = engine_with_view.views_for_operator("t1", "op1")
        assert isinstance(result, tuple)
        assert len(result) == 1

    def test_views_for_operator_filters_tenant(self, engine: OperatorWorkspaceEngine):
        engine.register_view("v1", "t1", "op1", "V1")
        engine.register_view("v2", "t2", "op1", "V2")
        assert len(engine.views_for_operator("t1", "op1")) == 1

    def test_views_for_operator_filters_operator(self, engine: OperatorWorkspaceEngine):
        engine.register_view("v1", "t1", "op1", "V1")
        engine.register_view("v2", "t1", "op2", "V2")
        assert len(engine.views_for_operator("t1", "op1")) == 1

    def test_views_for_operator_multiple(self, engine: OperatorWorkspaceEngine):
        engine.register_view("v1", "t1", "op1", "V1")
        engine.register_view("v2", "t1", "op1", "V2")
        assert len(engine.views_for_operator("t1", "op1")) == 2

    def test_views_for_nonexistent_tenant(self, engine_with_view: OperatorWorkspaceEngine):
        assert engine_with_view.views_for_tenant("t999") == ()


# ===================================================================
# Panels — register_panel
# ===================================================================


class TestRegisterPanel:
    def test_register_returns_panel(self, engine_with_view: OperatorWorkspaceEngine):
        p = engine_with_view.register_panel("p1", "v1", "t1", "Panel", PanelKind.QUEUE, "rt1")
        assert isinstance(p, WorkspacePanel)

    def test_register_panel_fields(self, engine_with_view: OperatorWorkspaceEngine):
        p = engine_with_view.register_panel("p1", "v1", "t1", "Panel", PanelKind.QUEUE, "rt1")
        assert p.panel_id == "p1"
        assert p.view_id == "v1"
        assert p.tenant_id == "t1"
        assert p.display_name == "Panel"
        assert p.kind == PanelKind.QUEUE
        assert p.target_runtime == "rt1"

    def test_register_panel_item_count_zero(self, engine_with_view: OperatorWorkspaceEngine):
        p = engine_with_view.register_panel("p1", "v1", "t1", "Panel", PanelKind.QUEUE, "rt1")
        assert p.item_count == 0

    def test_register_panel_increments_view_panel_count(self, engine_with_view: OperatorWorkspaceEngine):
        engine_with_view.register_panel("p1", "v1", "t1", "P1", PanelKind.QUEUE, "rt1")
        v = engine_with_view.get_view("v1")
        assert v.panel_count == 1

    def test_register_panel_increments_count(self, engine_with_view: OperatorWorkspaceEngine):
        engine_with_view.register_panel("p1", "v1", "t1", "P", PanelKind.QUEUE, "rt1")
        assert engine_with_view.panel_count == 1

    def test_register_panel_duplicate_raises(self, engine_with_view: OperatorWorkspaceEngine):
        engine_with_view.register_panel("p1", "v1", "t1", "P", PanelKind.QUEUE, "rt1")
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate"):
            engine_with_view.register_panel("p1", "v1", "t1", "P2", PanelKind.QUEUE, "rt1")

    def test_register_panel_unknown_view_raises(self, engine: OperatorWorkspaceEngine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown view"):
            engine.register_panel("p1", "vX", "t1", "P", PanelKind.QUEUE, "rt1")

    def test_register_panel_retired_view_raises(self, engine_with_view: OperatorWorkspaceEngine):
        engine_with_view.retire_view("v1")
        with pytest.raises(RuntimeCoreInvariantError, match="retired"):
            engine_with_view.register_panel("p1", "v1", "t1", "P", PanelKind.QUEUE, "rt1")

    def test_register_panel_cross_tenant_raises(self, engine_with_view: OperatorWorkspaceEngine):
        with pytest.raises(RuntimeCoreInvariantError, match="cross-tenant"):
            engine_with_view.register_panel("p1", "v1", "t_other", "P", PanelKind.QUEUE, "rt1")

    def test_register_panel_dashboard_kind(self, engine_with_view: OperatorWorkspaceEngine):
        p = engine_with_view.register_panel("p1", "v1", "t1", "P", PanelKind.DASHBOARD, "rt1")
        assert p.kind == PanelKind.DASHBOARD

    def test_register_panel_review_kind(self, engine_with_view: OperatorWorkspaceEngine):
        p = engine_with_view.register_panel("p1", "v1", "t1", "P", PanelKind.REVIEW, "rt1")
        assert p.kind == PanelKind.REVIEW

    def test_register_panel_approval_kind(self, engine_with_view: OperatorWorkspaceEngine):
        p = engine_with_view.register_panel("p1", "v1", "t1", "P", PanelKind.APPROVAL, "rt1")
        assert p.kind == PanelKind.APPROVAL

    def test_register_panel_investigation_kind(self, engine_with_view: OperatorWorkspaceEngine):
        p = engine_with_view.register_panel("p1", "v1", "t1", "P", PanelKind.INVESTIGATION, "rt1")
        assert p.kind == PanelKind.INVESTIGATION

    def test_register_multiple_panels(self, engine_with_view: OperatorWorkspaceEngine):
        for i in range(5):
            engine_with_view.register_panel(f"p{i}", "v1", "t1", f"P{i}", PanelKind.QUEUE, "rt1")
        assert engine_with_view.panel_count == 5
        v = engine_with_view.get_view("v1")
        assert v.panel_count == 5

    def test_register_panel_emits_event(self, es: EventSpineEngine, engine: OperatorWorkspaceEngine):
        engine.register_view("v1", "t1", "op1", "V")
        before = es.event_count
        engine.register_panel("p1", "v1", "t1", "P", PanelKind.QUEUE, "rt1")
        assert es.event_count > before

    def test_register_panel_has_created_at(self, engine_with_view: OperatorWorkspaceEngine):
        p = engine_with_view.register_panel("p1", "v1", "t1", "P", PanelKind.QUEUE, "rt1")
        assert p.created_at

    def test_register_panel_suspended_view_ok(self, engine_with_view: OperatorWorkspaceEngine):
        """Suspended views are not terminal — panels can still be added."""
        engine_with_view.suspend_view("v1")
        p = engine_with_view.register_panel("p1", "v1", "t1", "P", PanelKind.QUEUE, "rt1")
        assert p.panel_id == "p1"


# ===================================================================
# Panels — get_panel, panels_for_view
# ===================================================================


class TestPanelQueries:
    def test_get_existing_panel(self, engine_with_panel: OperatorWorkspaceEngine):
        p = engine_with_panel.get_panel("p1")
        assert p.panel_id == "p1"

    def test_get_unknown_panel_raises(self, engine: OperatorWorkspaceEngine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown"):
            engine.get_panel("nonexist")

    def test_panels_for_view_empty(self, engine_with_view: OperatorWorkspaceEngine):
        assert engine_with_view.panels_for_view("v1") == ()

    def test_panels_for_view_returns_tuple(self, engine_with_panel: OperatorWorkspaceEngine):
        result = engine_with_panel.panels_for_view("v1")
        assert isinstance(result, tuple)
        assert len(result) == 1

    def test_panels_for_view_filters(self, engine: OperatorWorkspaceEngine):
        engine.register_view("v1", "t1", "op1", "V1")
        engine.register_view("v2", "t1", "op1", "V2")
        engine.register_panel("p1", "v1", "t1", "P1", PanelKind.QUEUE, "rt1")
        engine.register_panel("p2", "v2", "t1", "P2", PanelKind.QUEUE, "rt1")
        assert len(engine.panels_for_view("v1")) == 1
        assert len(engine.panels_for_view("v2")) == 1

    def test_panels_for_nonexistent_view(self, engine: OperatorWorkspaceEngine):
        assert engine.panels_for_view("vX") == ()

    def test_get_panel_frozen(self, engine_with_panel: OperatorWorkspaceEngine):
        p = engine_with_panel.get_panel("p1")
        with pytest.raises(AttributeError):
            p.panel_id = "changed"


# ===================================================================
# Queues — enqueue_item
# ===================================================================


class TestEnqueueItem:
    def test_enqueue_returns_record(self, engine_with_panel: OperatorWorkspaceEngine):
        q = engine_with_panel.enqueue_item("q1", "p1", "t1", "src1", "rt1")
        assert isinstance(q, QueueRecord)

    def test_enqueue_fields(self, engine_with_panel: OperatorWorkspaceEngine):
        q = engine_with_panel.enqueue_item("q1", "p1", "t1", "src1", "rt1", "a1", 5)
        assert q.queue_id == "q1"
        assert q.panel_id == "p1"
        assert q.tenant_id == "t1"
        assert q.source_ref == "src1"
        assert q.source_runtime == "rt1"
        assert q.assignee_ref == "a1"
        assert q.priority == 5

    def test_enqueue_status_pending(self, engine_with_panel: OperatorWorkspaceEngine):
        q = engine_with_panel.enqueue_item("q1", "p1", "t1", "src1", "rt1")
        assert q.status == QueueStatus.PENDING

    def test_enqueue_default_assignee(self, engine_with_panel: OperatorWorkspaceEngine):
        q = engine_with_panel.enqueue_item("q1", "p1", "t1", "src1", "rt1")
        assert q.assignee_ref == "unassigned"

    def test_enqueue_default_priority(self, engine_with_panel: OperatorWorkspaceEngine):
        q = engine_with_panel.enqueue_item("q1", "p1", "t1", "src1", "rt1")
        assert q.priority == 0

    def test_enqueue_increments_panel_item_count(self, engine_with_panel: OperatorWorkspaceEngine):
        engine_with_panel.enqueue_item("q1", "p1", "t1", "src1", "rt1")
        p = engine_with_panel.get_panel("p1")
        assert p.item_count == 1

    def test_enqueue_increments_queue_count(self, engine_with_panel: OperatorWorkspaceEngine):
        engine_with_panel.enqueue_item("q1", "p1", "t1", "src1", "rt1")
        assert engine_with_panel.queue_count == 1

    def test_enqueue_duplicate_raises(self, engine_with_panel: OperatorWorkspaceEngine):
        engine_with_panel.enqueue_item("q1", "p1", "t1", "src1", "rt1")
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate"):
            engine_with_panel.enqueue_item("q1", "p1", "t1", "src2", "rt1")

    def test_enqueue_unknown_panel_raises(self, engine: OperatorWorkspaceEngine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown panel"):
            engine.enqueue_item("q1", "pX", "t1", "src1", "rt1")

    def test_enqueue_cross_tenant_raises(self, engine_with_panel: OperatorWorkspaceEngine):
        with pytest.raises(RuntimeCoreInvariantError, match="cross-tenant"):
            engine_with_panel.enqueue_item("q1", "p1", "t_other", "src1", "rt1")

    def test_enqueue_multiple(self, engine_with_panel: OperatorWorkspaceEngine):
        for i in range(10):
            engine_with_panel.enqueue_item(f"q{i}", "p1", "t1", f"src{i}", "rt1", priority=i)
        assert engine_with_panel.queue_count == 10
        p = engine_with_panel.get_panel("p1")
        assert p.item_count == 10

    def test_enqueue_emits_event(self, es: EventSpineEngine, engine: OperatorWorkspaceEngine):
        engine.register_view("v1", "t1", "op1", "V")
        engine.register_panel("p1", "v1", "t1", "P", PanelKind.QUEUE, "rt1")
        before = es.event_count
        engine.enqueue_item("q1", "p1", "t1", "src1", "rt1")
        assert es.event_count > before

    def test_enqueue_has_created_at(self, engine_with_panel: OperatorWorkspaceEngine):
        q = engine_with_panel.enqueue_item("q1", "p1", "t1", "src1", "rt1")
        assert q.created_at


# ===================================================================
# Queues — assign_queue_item
# ===================================================================


class TestAssignQueueItem:
    def test_assign_returns_record(self, engine_with_queue_item: OperatorWorkspaceEngine):
        q = engine_with_queue_item.assign_queue_item("q1", "agent1")
        assert isinstance(q, QueueRecord)

    def test_assign_sets_status(self, engine_with_queue_item: OperatorWorkspaceEngine):
        q = engine_with_queue_item.assign_queue_item("q1", "agent1")
        assert q.status == QueueStatus.ASSIGNED

    def test_assign_sets_assignee(self, engine_with_queue_item: OperatorWorkspaceEngine):
        q = engine_with_queue_item.assign_queue_item("q1", "agent1")
        assert q.assignee_ref == "agent1"

    def test_assign_unknown_raises(self, engine: OperatorWorkspaceEngine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown"):
            engine.assign_queue_item("qX", "agent1")

    def test_assign_completed_raises(self, engine_with_queue_item: OperatorWorkspaceEngine):
        engine_with_queue_item.complete_queue_item("q1")
        with pytest.raises(RuntimeCoreInvariantError, match="completed"):
            engine_with_queue_item.assign_queue_item("q1", "agent1")

    def test_assign_preserves_priority(self, engine_with_queue_item: OperatorWorkspaceEngine):
        q = engine_with_queue_item.assign_queue_item("q1", "agent1")
        assert q.priority == 3

    def test_assign_emits_event(self, es: EventSpineEngine, engine_with_queue_item: OperatorWorkspaceEngine):
        before = es.event_count
        engine_with_queue_item.assign_queue_item("q1", "agent1")
        assert es.event_count > before

    def test_reassign(self, engine_with_queue_item: OperatorWorkspaceEngine):
        engine_with_queue_item.assign_queue_item("q1", "agent1")
        q = engine_with_queue_item.assign_queue_item("q1", "agent2")
        assert q.assignee_ref == "agent2"


# ===================================================================
# Queues — start_queue_item
# ===================================================================


class TestStartQueueItem:
    def test_start_returns_record(self, engine_with_queue_item: OperatorWorkspaceEngine):
        q = engine_with_queue_item.start_queue_item("q1")
        assert isinstance(q, QueueRecord)

    def test_start_sets_in_progress(self, engine_with_queue_item: OperatorWorkspaceEngine):
        q = engine_with_queue_item.start_queue_item("q1")
        assert q.status == QueueStatus.IN_PROGRESS

    def test_start_unknown_raises(self, engine: OperatorWorkspaceEngine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown"):
            engine.start_queue_item("qX")

    def test_start_completed_raises(self, engine_with_queue_item: OperatorWorkspaceEngine):
        engine_with_queue_item.complete_queue_item("q1")
        with pytest.raises(RuntimeCoreInvariantError, match="completed"):
            engine_with_queue_item.start_queue_item("q1")

    def test_start_preserves_fields(self, engine_with_queue_item: OperatorWorkspaceEngine):
        q = engine_with_queue_item.start_queue_item("q1")
        assert q.source_ref == "src1"
        assert q.priority == 3

    def test_start_emits_event(self, es: EventSpineEngine, engine_with_queue_item: OperatorWorkspaceEngine):
        before = es.event_count
        engine_with_queue_item.start_queue_item("q1")
        assert es.event_count > before


# ===================================================================
# Queues — complete_queue_item
# ===================================================================


class TestCompleteQueueItem:
    def test_complete_returns_record(self, engine_with_queue_item: OperatorWorkspaceEngine):
        q = engine_with_queue_item.complete_queue_item("q1")
        assert isinstance(q, QueueRecord)

    def test_complete_sets_completed(self, engine_with_queue_item: OperatorWorkspaceEngine):
        q = engine_with_queue_item.complete_queue_item("q1")
        assert q.status == QueueStatus.COMPLETED

    def test_complete_unknown_raises(self, engine: OperatorWorkspaceEngine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown"):
            engine.complete_queue_item("qX")

    def test_complete_already_completed_raises(self, engine_with_queue_item: OperatorWorkspaceEngine):
        engine_with_queue_item.complete_queue_item("q1")
        with pytest.raises(RuntimeCoreInvariantError, match="already completed"):
            engine_with_queue_item.complete_queue_item("q1")

    def test_complete_preserves_fields(self, engine_with_queue_item: OperatorWorkspaceEngine):
        q = engine_with_queue_item.complete_queue_item("q1")
        assert q.queue_id == "q1"
        assert q.source_ref == "src1"

    def test_complete_emits_event(self, es: EventSpineEngine, engine_with_queue_item: OperatorWorkspaceEngine):
        before = es.event_count
        engine_with_queue_item.complete_queue_item("q1")
        assert es.event_count > before

    def test_complete_from_assigned(self, engine_with_queue_item: OperatorWorkspaceEngine):
        engine_with_queue_item.assign_queue_item("q1", "agent1")
        q = engine_with_queue_item.complete_queue_item("q1")
        assert q.status == QueueStatus.COMPLETED

    def test_complete_from_in_progress(self, engine_with_queue_item: OperatorWorkspaceEngine):
        engine_with_queue_item.start_queue_item("q1")
        q = engine_with_queue_item.complete_queue_item("q1")
        assert q.status == QueueStatus.COMPLETED

    def test_complete_from_escalated(self, engine_with_queue_item: OperatorWorkspaceEngine):
        engine_with_queue_item.escalate_queue_item("q1")
        q = engine_with_queue_item.complete_queue_item("q1")
        assert q.status == QueueStatus.COMPLETED


# ===================================================================
# Queues — escalate_queue_item
# ===================================================================


class TestEscalateQueueItem:
    def test_escalate_returns_record(self, engine_with_queue_item: OperatorWorkspaceEngine):
        q = engine_with_queue_item.escalate_queue_item("q1")
        assert isinstance(q, QueueRecord)

    def test_escalate_sets_status(self, engine_with_queue_item: OperatorWorkspaceEngine):
        q = engine_with_queue_item.escalate_queue_item("q1")
        assert q.status == QueueStatus.ESCALATED

    def test_escalate_unknown_raises(self, engine: OperatorWorkspaceEngine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown"):
            engine.escalate_queue_item("qX")

    def test_escalate_completed_raises(self, engine_with_queue_item: OperatorWorkspaceEngine):
        engine_with_queue_item.complete_queue_item("q1")
        with pytest.raises(RuntimeCoreInvariantError, match="completed"):
            engine_with_queue_item.escalate_queue_item("q1")

    def test_escalate_emits_event(self, es: EventSpineEngine, engine_with_queue_item: OperatorWorkspaceEngine):
        before = es.event_count
        engine_with_queue_item.escalate_queue_item("q1")
        assert es.event_count > before

    def test_escalate_preserves_fields(self, engine_with_queue_item: OperatorWorkspaceEngine):
        q = engine_with_queue_item.escalate_queue_item("q1")
        assert q.priority == 3
        assert q.source_ref == "src1"


# ===================================================================
# Queues — queue_items_for_panel, pending_queue_items
# ===================================================================


class TestQueueQueries:
    def test_queue_items_for_panel_empty(self, engine_with_panel: OperatorWorkspaceEngine):
        assert engine_with_panel.queue_items_for_panel("p1") == ()

    def test_queue_items_for_panel_returns_tuple(self, engine_with_queue_item: OperatorWorkspaceEngine):
        result = engine_with_queue_item.queue_items_for_panel("p1")
        assert isinstance(result, tuple)
        assert len(result) == 1

    def test_queue_items_sorted_by_priority_desc(self, engine_with_panel: OperatorWorkspaceEngine):
        engine_with_panel.enqueue_item("q1", "p1", "t1", "s1", "rt1", priority=1)
        engine_with_panel.enqueue_item("q2", "p1", "t1", "s2", "rt1", priority=5)
        engine_with_panel.enqueue_item("q3", "p1", "t1", "s3", "rt1", priority=3)
        items = engine_with_panel.queue_items_for_panel("p1")
        priorities = [i.priority for i in items]
        assert priorities[0] == 5
        assert priorities[1] == 3
        assert priorities[2] == 1

    def test_queue_items_same_priority_sorted_by_created(self, engine_with_panel: OperatorWorkspaceEngine):
        engine_with_panel.enqueue_item("q1", "p1", "t1", "s1", "rt1", priority=3)
        engine_with_panel.enqueue_item("q2", "p1", "t1", "s2", "rt1", priority=3)
        items = engine_with_panel.queue_items_for_panel("p1")
        assert items[0].created_at <= items[1].created_at

    def test_queue_items_for_nonexistent_panel(self, engine: OperatorWorkspaceEngine):
        assert engine.queue_items_for_panel("pX") == ()

    def test_pending_queue_items_empty(self, engine: OperatorWorkspaceEngine):
        assert engine.pending_queue_items("t1") == ()

    def test_pending_queue_items_returns_tuple(self, engine_with_queue_item: OperatorWorkspaceEngine):
        result = engine_with_queue_item.pending_queue_items("t1")
        assert isinstance(result, tuple)
        assert len(result) == 1

    def test_pending_excludes_completed(self, engine_with_queue_item: OperatorWorkspaceEngine):
        engine_with_queue_item.complete_queue_item("q1")
        assert len(engine_with_queue_item.pending_queue_items("t1")) == 0

    def test_pending_excludes_assigned(self, engine_with_queue_item: OperatorWorkspaceEngine):
        engine_with_queue_item.assign_queue_item("q1", "a1")
        assert len(engine_with_queue_item.pending_queue_items("t1")) == 0

    def test_pending_filters_by_tenant(self, engine: OperatorWorkspaceEngine):
        engine.register_view("v1", "t1", "op1", "V1")
        engine.register_view("v2", "t2", "op2", "V2")
        engine.register_panel("p1", "v1", "t1", "P1", PanelKind.QUEUE, "rt1")
        engine.register_panel("p2", "v2", "t2", "P2", PanelKind.QUEUE, "rt1")
        engine.enqueue_item("q1", "p1", "t1", "s1", "rt1")
        engine.enqueue_item("q2", "p2", "t2", "s2", "rt1")
        assert len(engine.pending_queue_items("t1")) == 1
        assert len(engine.pending_queue_items("t2")) == 1

    def test_pending_includes_only_pending_status(self, engine_with_panel: OperatorWorkspaceEngine):
        engine_with_panel.enqueue_item("q1", "p1", "t1", "s1", "rt1")
        engine_with_panel.enqueue_item("q2", "p1", "t1", "s2", "rt1")
        engine_with_panel.start_queue_item("q2")
        assert len(engine_with_panel.pending_queue_items("t1")) == 1


# ===================================================================
# Worklist — add_worklist_item
# ===================================================================


class TestAddWorklistItem:
    def test_add_returns_item(self, engine: OperatorWorkspaceEngine):
        w = engine.add_worklist_item("w1", "t1", "op1", "src1", "rt1", "Task One")
        assert isinstance(w, WorklistItem)

    def test_add_worklist_fields(self, engine: OperatorWorkspaceEngine):
        w = engine.add_worklist_item("w1", "t1", "op1", "src1", "rt1", "Task One", 5)
        assert w.item_id == "w1"
        assert w.tenant_id == "t1"
        assert w.operator_ref == "op1"
        assert w.source_ref == "src1"
        assert w.source_runtime == "rt1"
        assert w.title == "Task One"
        assert w.priority == 5

    def test_add_worklist_status_pending(self, engine: OperatorWorkspaceEngine):
        w = engine.add_worklist_item("w1", "t1", "op1", "src1", "rt1", "T")
        assert w.status == QueueStatus.PENDING

    def test_add_worklist_default_priority(self, engine: OperatorWorkspaceEngine):
        w = engine.add_worklist_item("w1", "t1", "op1", "src1", "rt1", "T")
        assert w.priority == 0

    def test_add_worklist_increments_count(self, engine: OperatorWorkspaceEngine):
        engine.add_worklist_item("w1", "t1", "op1", "src1", "rt1", "T")
        assert engine.worklist_count == 1

    def test_add_worklist_duplicate_raises(self, engine: OperatorWorkspaceEngine):
        engine.add_worklist_item("w1", "t1", "op1", "src1", "rt1", "T")
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate"):
            engine.add_worklist_item("w1", "t1", "op1", "src2", "rt1", "T2")

    def test_add_worklist_emits_event(self, es: EventSpineEngine, engine: OperatorWorkspaceEngine):
        before = es.event_count
        engine.add_worklist_item("w1", "t1", "op1", "src1", "rt1", "T")
        assert es.event_count > before

    def test_add_worklist_has_created_at(self, engine: OperatorWorkspaceEngine):
        w = engine.add_worklist_item("w1", "t1", "op1", "src1", "rt1", "T")
        assert w.created_at

    def test_add_multiple_worklist_items(self, engine: OperatorWorkspaceEngine):
        for i in range(10):
            engine.add_worklist_item(f"w{i}", "t1", "op1", f"src{i}", "rt1", f"T{i}")
        assert engine.worklist_count == 10


# ===================================================================
# Worklist — complete_worklist_item
# ===================================================================


class TestCompleteWorklistItem:
    def test_complete_returns_item(self, engine: OperatorWorkspaceEngine):
        engine.add_worklist_item("w1", "t1", "op1", "src1", "rt1", "T")
        w = engine.complete_worklist_item("w1")
        assert isinstance(w, WorklistItem)

    def test_complete_sets_completed(self, engine: OperatorWorkspaceEngine):
        engine.add_worklist_item("w1", "t1", "op1", "src1", "rt1", "T")
        w = engine.complete_worklist_item("w1")
        assert w.status == QueueStatus.COMPLETED

    def test_complete_unknown_raises(self, engine: OperatorWorkspaceEngine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown"):
            engine.complete_worklist_item("wX")

    def test_complete_already_completed_raises(self, engine: OperatorWorkspaceEngine):
        engine.add_worklist_item("w1", "t1", "op1", "src1", "rt1", "T")
        engine.complete_worklist_item("w1")
        with pytest.raises(RuntimeCoreInvariantError, match="already completed"):
            engine.complete_worklist_item("w1")

    def test_complete_preserves_fields(self, engine: OperatorWorkspaceEngine):
        engine.add_worklist_item("w1", "t1", "op1", "src1", "rt1", "T", 7)
        w = engine.complete_worklist_item("w1")
        assert w.title == "T"
        assert w.priority == 7

    def test_complete_emits_event(self, es: EventSpineEngine, engine: OperatorWorkspaceEngine):
        engine.add_worklist_item("w1", "t1", "op1", "src1", "rt1", "T")
        before = es.event_count
        engine.complete_worklist_item("w1")
        assert es.event_count > before


# ===================================================================
# Worklist — worklist_for_operator
# ===================================================================


class TestWorklistForOperator:
    def test_empty(self, engine: OperatorWorkspaceEngine):
        assert engine.worklist_for_operator("t1", "op1") == ()

    def test_returns_tuple(self, engine: OperatorWorkspaceEngine):
        engine.add_worklist_item("w1", "t1", "op1", "src1", "rt1", "T")
        result = engine.worklist_for_operator("t1", "op1")
        assert isinstance(result, tuple)
        assert len(result) == 1

    def test_filters_by_tenant(self, engine: OperatorWorkspaceEngine):
        engine.add_worklist_item("w1", "t1", "op1", "src1", "rt1", "T")
        engine.add_worklist_item("w2", "t2", "op1", "src1", "rt1", "T")
        assert len(engine.worklist_for_operator("t1", "op1")) == 1

    def test_filters_by_operator(self, engine: OperatorWorkspaceEngine):
        engine.add_worklist_item("w1", "t1", "op1", "src1", "rt1", "T")
        engine.add_worklist_item("w2", "t1", "op2", "src1", "rt1", "T")
        assert len(engine.worklist_for_operator("t1", "op1")) == 1

    def test_sorted_by_priority_desc(self, engine: OperatorWorkspaceEngine):
        engine.add_worklist_item("w1", "t1", "op1", "src1", "rt1", "T1", 1)
        engine.add_worklist_item("w2", "t1", "op1", "src2", "rt1", "T2", 5)
        engine.add_worklist_item("w3", "t1", "op1", "src3", "rt1", "T3", 3)
        items = engine.worklist_for_operator("t1", "op1")
        priorities = [i.priority for i in items]
        assert priorities == [5, 3, 1]

    def test_sorted_by_created_within_priority(self, engine: OperatorWorkspaceEngine):
        engine.add_worklist_item("w1", "t1", "op1", "src1", "rt1", "T1", 3)
        engine.add_worklist_item("w2", "t1", "op1", "src2", "rt1", "T2", 3)
        items = engine.worklist_for_operator("t1", "op1")
        assert items[0].created_at <= items[1].created_at

    def test_includes_completed_items(self, engine: OperatorWorkspaceEngine):
        engine.add_worklist_item("w1", "t1", "op1", "src1", "rt1", "T")
        engine.complete_worklist_item("w1")
        assert len(engine.worklist_for_operator("t1", "op1")) == 1


# ===================================================================
# Actions — record_action
# ===================================================================


class TestRecordAction:
    def test_record_returns_action(self, engine: OperatorWorkspaceEngine):
        a = engine.record_action("a1", "t1", "op1", "tgt1", "rt1", "approve")
        assert isinstance(a, OperatorAction)

    def test_record_action_fields(self, engine: OperatorWorkspaceEngine):
        a = engine.record_action("a1", "t1", "op1", "tgt1", "rt1", "approve")
        assert a.action_id == "a1"
        assert a.tenant_id == "t1"
        assert a.operator_ref == "op1"
        assert a.target_ref == "tgt1"
        assert a.target_runtime == "rt1"
        assert a.action_name == "approve"

    def test_record_action_status_initiated(self, engine: OperatorWorkspaceEngine):
        a = engine.record_action("a1", "t1", "op1", "tgt1", "rt1", "approve")
        assert a.status == OperatorActionStatus.INITIATED

    def test_record_action_increments_count(self, engine: OperatorWorkspaceEngine):
        engine.record_action("a1", "t1", "op1", "tgt1", "rt1", "approve")
        assert engine.action_count == 1

    def test_record_action_duplicate_raises(self, engine: OperatorWorkspaceEngine):
        engine.record_action("a1", "t1", "op1", "tgt1", "rt1", "approve")
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate"):
            engine.record_action("a1", "t1", "op1", "tgt1", "rt1", "approve")

    def test_record_action_emits_event(self, es: EventSpineEngine, engine: OperatorWorkspaceEngine):
        before = es.event_count
        engine.record_action("a1", "t1", "op1", "tgt1", "rt1", "approve")
        assert es.event_count > before

    def test_record_action_has_created_at(self, engine: OperatorWorkspaceEngine):
        a = engine.record_action("a1", "t1", "op1", "tgt1", "rt1", "approve")
        assert a.created_at

    def test_record_multiple_actions(self, engine: OperatorWorkspaceEngine):
        for i in range(10):
            engine.record_action(f"a{i}", "t1", "op1", f"tgt{i}", "rt1", "approve")
        assert engine.action_count == 10


# ===================================================================
# Actions — complete_action
# ===================================================================


class TestCompleteAction:
    def test_complete_returns_action(self, engine: OperatorWorkspaceEngine):
        engine.record_action("a1", "t1", "op1", "tgt1", "rt1", "approve")
        a = engine.complete_action("a1")
        assert isinstance(a, OperatorAction)

    def test_complete_sets_completed(self, engine: OperatorWorkspaceEngine):
        engine.record_action("a1", "t1", "op1", "tgt1", "rt1", "approve")
        a = engine.complete_action("a1")
        assert a.status == OperatorActionStatus.COMPLETED

    def test_complete_unknown_raises(self, engine: OperatorWorkspaceEngine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown"):
            engine.complete_action("aX")

    def test_complete_already_completed_raises(self, engine: OperatorWorkspaceEngine):
        engine.record_action("a1", "t1", "op1", "tgt1", "rt1", "approve")
        engine.complete_action("a1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine.complete_action("a1")

    def test_complete_failed_raises(self, engine: OperatorWorkspaceEngine):
        engine.record_action("a1", "t1", "op1", "tgt1", "rt1", "approve")
        engine.fail_action("a1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine.complete_action("a1")

    def test_complete_preserves_fields(self, engine: OperatorWorkspaceEngine):
        engine.record_action("a1", "t1", "op1", "tgt1", "rt1", "approve")
        a = engine.complete_action("a1")
        assert a.action_name == "approve"
        assert a.operator_ref == "op1"

    def test_complete_emits_event(self, es: EventSpineEngine, engine: OperatorWorkspaceEngine):
        engine.record_action("a1", "t1", "op1", "tgt1", "rt1", "approve")
        before = es.event_count
        engine.complete_action("a1")
        assert es.event_count > before


# ===================================================================
# Actions — fail_action
# ===================================================================


class TestFailAction:
    def test_fail_returns_action(self, engine: OperatorWorkspaceEngine):
        engine.record_action("a1", "t1", "op1", "tgt1", "rt1", "approve")
        a = engine.fail_action("a1")
        assert isinstance(a, OperatorAction)

    def test_fail_sets_failed(self, engine: OperatorWorkspaceEngine):
        engine.record_action("a1", "t1", "op1", "tgt1", "rt1", "approve")
        a = engine.fail_action("a1")
        assert a.status == OperatorActionStatus.FAILED

    def test_fail_unknown_raises(self, engine: OperatorWorkspaceEngine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown"):
            engine.fail_action("aX")

    def test_fail_already_failed_raises(self, engine: OperatorWorkspaceEngine):
        engine.record_action("a1", "t1", "op1", "tgt1", "rt1", "approve")
        engine.fail_action("a1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine.fail_action("a1")

    def test_fail_completed_raises(self, engine: OperatorWorkspaceEngine):
        engine.record_action("a1", "t1", "op1", "tgt1", "rt1", "approve")
        engine.complete_action("a1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine.fail_action("a1")

    def test_fail_preserves_fields(self, engine: OperatorWorkspaceEngine):
        engine.record_action("a1", "t1", "op1", "tgt1", "rt1", "approve")
        a = engine.fail_action("a1")
        assert a.action_name == "approve"

    def test_fail_emits_event(self, es: EventSpineEngine, engine: OperatorWorkspaceEngine):
        engine.record_action("a1", "t1", "op1", "tgt1", "rt1", "approve")
        before = es.event_count
        engine.fail_action("a1")
        assert es.event_count > before


# ===================================================================
# Actions — actions_for_operator
# ===================================================================


class TestActionsForOperator:
    def test_empty(self, engine: OperatorWorkspaceEngine):
        assert engine.actions_for_operator("t1", "op1") == ()

    def test_returns_tuple(self, engine: OperatorWorkspaceEngine):
        engine.record_action("a1", "t1", "op1", "tgt1", "rt1", "approve")
        result = engine.actions_for_operator("t1", "op1")
        assert isinstance(result, tuple)
        assert len(result) == 1

    def test_filters_by_tenant(self, engine: OperatorWorkspaceEngine):
        engine.record_action("a1", "t1", "op1", "tgt1", "rt1", "approve")
        engine.record_action("a2", "t2", "op1", "tgt1", "rt1", "approve")
        assert len(engine.actions_for_operator("t1", "op1")) == 1

    def test_filters_by_operator(self, engine: OperatorWorkspaceEngine):
        engine.record_action("a1", "t1", "op1", "tgt1", "rt1", "approve")
        engine.record_action("a2", "t1", "op2", "tgt1", "rt1", "approve")
        assert len(engine.actions_for_operator("t1", "op1")) == 1

    def test_includes_all_statuses(self, engine: OperatorWorkspaceEngine):
        engine.record_action("a1", "t1", "op1", "tgt1", "rt1", "approve")
        engine.record_action("a2", "t1", "op1", "tgt2", "rt1", "reject")
        engine.complete_action("a1")
        engine.fail_action("a2")
        assert len(engine.actions_for_operator("t1", "op1")) == 2


# ===================================================================
# Decisions — record_decision
# ===================================================================


class TestRecordDecision:
    def test_record_returns_decision(self, engine: OperatorWorkspaceEngine):
        d = engine.record_decision("d1", "t1", "op1", "a1", "approved", "reason")
        assert isinstance(d, WorkspaceDecision)

    def test_record_decision_fields(self, engine: OperatorWorkspaceEngine):
        d = engine.record_decision("d1", "t1", "op1", "a1", "approved", "good reason")
        assert d.decision_id == "d1"
        assert d.tenant_id == "t1"
        assert d.operator_ref == "op1"
        assert d.action_id == "a1"
        assert d.disposition == "approved"
        assert d.reason == "good reason"

    def test_record_decision_defaults(self, engine: OperatorWorkspaceEngine):
        d = engine.record_decision("d1", "t1", "op1", "a1")
        assert d.disposition == "approved"
        assert d.reason == "operator decision"

    def test_record_decision_increments_count(self, engine: OperatorWorkspaceEngine):
        engine.record_decision("d1", "t1", "op1", "a1")
        assert engine.decision_count == 1

    def test_record_decision_duplicate_raises(self, engine: OperatorWorkspaceEngine):
        engine.record_decision("d1", "t1", "op1", "a1")
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate"):
            engine.record_decision("d1", "t1", "op1", "a1")

    def test_record_decision_emits_event(self, es: EventSpineEngine, engine: OperatorWorkspaceEngine):
        before = es.event_count
        engine.record_decision("d1", "t1", "op1", "a1")
        assert es.event_count > before

    def test_record_decision_has_decided_at(self, engine: OperatorWorkspaceEngine):
        d = engine.record_decision("d1", "t1", "op1", "a1")
        assert d.decided_at

    def test_record_multiple_decisions(self, engine: OperatorWorkspaceEngine):
        for i in range(10):
            engine.record_decision(f"d{i}", "t1", "op1", f"a{i}")
        assert engine.decision_count == 10

    def test_record_decision_rejected_disposition(self, engine: OperatorWorkspaceEngine):
        d = engine.record_decision("d1", "t1", "op1", "a1", "rejected", "bad reason")
        assert d.disposition == "rejected"


# ===================================================================
# Snapshots — workspace_snapshot
# ===================================================================


class TestWorkspaceSnapshot:
    def test_snapshot_returns_snapshot(self, engine: OperatorWorkspaceEngine):
        s = engine.workspace_snapshot("snap1", "t1")
        assert isinstance(s, WorkspaceSnapshot)

    def test_snapshot_fields_empty(self, engine: OperatorWorkspaceEngine):
        s = engine.workspace_snapshot("snap1", "t1")
        assert s.snapshot_id == "snap1"
        assert s.tenant_id == "t1"
        assert s.total_views == 0
        assert s.active_views == 0
        assert s.total_panels == 0
        assert s.total_queue_items == 0
        assert s.pending_queue_items == 0
        assert s.total_worklist_items == 0
        assert s.total_actions == 0

    def test_snapshot_with_data(self, engine: OperatorWorkspaceEngine):
        engine.register_view("v1", "t1", "op1", "V1")
        engine.register_panel("p1", "v1", "t1", "P1", PanelKind.QUEUE, "rt1")
        engine.enqueue_item("q1", "p1", "t1", "src1", "rt1")
        engine.add_worklist_item("w1", "t1", "op1", "src1", "rt1", "T")
        engine.record_action("a1", "t1", "op1", "tgt1", "rt1", "approve")
        s = engine.workspace_snapshot("snap1", "t1")
        assert s.total_views == 1
        assert s.active_views == 1
        assert s.total_panels == 1
        assert s.total_queue_items == 1
        assert s.pending_queue_items == 1
        assert s.total_worklist_items == 1
        assert s.total_actions == 1

    def test_snapshot_filters_by_tenant(self, engine: OperatorWorkspaceEngine):
        engine.register_view("v1", "t1", "op1", "V1")
        engine.register_view("v2", "t2", "op2", "V2")
        s = engine.workspace_snapshot("snap1", "t1")
        assert s.total_views == 1

    def test_snapshot_active_vs_retired(self, engine: OperatorWorkspaceEngine):
        engine.register_view("v1", "t1", "op1", "V1")
        engine.register_view("v2", "t1", "op1", "V2")
        engine.retire_view("v2")
        s = engine.workspace_snapshot("snap1", "t1")
        assert s.total_views == 2
        assert s.active_views == 1

    def test_snapshot_pending_vs_completed(self, engine: OperatorWorkspaceEngine):
        engine.register_view("v1", "t1", "op1", "V1")
        engine.register_panel("p1", "v1", "t1", "P1", PanelKind.QUEUE, "rt1")
        engine.enqueue_item("q1", "p1", "t1", "s1", "rt1")
        engine.enqueue_item("q2", "p1", "t1", "s2", "rt1")
        engine.complete_queue_item("q1")
        s = engine.workspace_snapshot("snap1", "t1")
        assert s.total_queue_items == 2
        assert s.pending_queue_items == 1

    def test_snapshot_emits_event(self, es: EventSpineEngine, engine: OperatorWorkspaceEngine):
        before = es.event_count
        engine.workspace_snapshot("snap1", "t1")
        assert es.event_count > before

    def test_snapshot_has_captured_at(self, engine: OperatorWorkspaceEngine):
        s = engine.workspace_snapshot("snap1", "t1")
        assert s.captured_at

    def test_snapshot_can_be_created_multiple_times(self, engine: OperatorWorkspaceEngine):
        s1 = engine.workspace_snapshot("snap1", "t1")
        s2 = engine.workspace_snapshot("snap2", "t1")
        assert s1.snapshot_id != s2.snapshot_id


# ===================================================================
# Assessment — workspace_assessment
# ===================================================================


class TestWorkspaceAssessment:
    def test_assessment_returns_assessment(self, engine: OperatorWorkspaceEngine):
        a = engine.workspace_assessment("assess1", "t1")
        assert isinstance(a, WorkspaceAssessment)

    def test_assessment_fields_empty(self, engine: OperatorWorkspaceEngine):
        a = engine.workspace_assessment("assess1", "t1")
        assert a.assessment_id == "assess1"
        assert a.tenant_id == "t1"
        assert a.total_views == 0
        assert a.active_views == 0
        assert a.queue_depth == 0
        assert a.pending_rate == 0.0
        assert a.total_violations == 0

    def test_assessment_pending_rate(self, engine: OperatorWorkspaceEngine):
        engine.register_view("v1", "t1", "op1", "V")
        engine.register_panel("p1", "v1", "t1", "P", PanelKind.QUEUE, "rt1")
        engine.enqueue_item("q1", "p1", "t1", "s1", "rt1")
        engine.enqueue_item("q2", "p1", "t1", "s2", "rt1")
        engine.complete_queue_item("q1")
        a = engine.workspace_assessment("assess1", "t1")
        assert a.queue_depth == 2
        assert a.pending_rate == 0.5

    def test_assessment_pending_rate_all_pending(self, engine: OperatorWorkspaceEngine):
        engine.register_view("v1", "t1", "op1", "V")
        engine.register_panel("p1", "v1", "t1", "P", PanelKind.QUEUE, "rt1")
        engine.enqueue_item("q1", "p1", "t1", "s1", "rt1")
        a = engine.workspace_assessment("assess1", "t1")
        assert a.pending_rate == 1.0

    def test_assessment_pending_rate_none_pending(self, engine: OperatorWorkspaceEngine):
        engine.register_view("v1", "t1", "op1", "V")
        engine.register_panel("p1", "v1", "t1", "P", PanelKind.QUEUE, "rt1")
        engine.enqueue_item("q1", "p1", "t1", "s1", "rt1")
        engine.complete_queue_item("q1")
        a = engine.workspace_assessment("assess1", "t1")
        assert a.pending_rate == 0.0

    def test_assessment_duplicate_raises(self, engine: OperatorWorkspaceEngine):
        engine.workspace_assessment("assess1", "t1")
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate"):
            engine.workspace_assessment("assess1", "t1")

    def test_assessment_increments_count(self, engine: OperatorWorkspaceEngine):
        engine.workspace_assessment("assess1", "t1")
        assert engine.assessment_count == 1

    def test_assessment_emits_event(self, es: EventSpineEngine, engine: OperatorWorkspaceEngine):
        before = es.event_count
        engine.workspace_assessment("assess1", "t1")
        assert es.event_count > before

    def test_assessment_has_assessed_at(self, engine: OperatorWorkspaceEngine):
        a = engine.workspace_assessment("assess1", "t1")
        assert a.assessed_at

    def test_assessment_includes_violations(self, engine: OperatorWorkspaceEngine):
        engine.register_view("v1", "t1", "op1", "V")
        engine.register_panel("p1", "v1", "t1", "P", PanelKind.QUEUE, "rt1")
        # empty panel generates a violation
        engine.detect_workspace_violations("t1")
        a = engine.workspace_assessment("assess1", "t1")
        assert a.total_violations >= 1


# ===================================================================
# Violations — detect_workspace_violations
# ===================================================================


class TestDetectViolations:
    def test_no_violations_empty(self, engine: OperatorWorkspaceEngine):
        result = engine.detect_workspace_violations("t1")
        assert result == ()

    def test_returns_tuple(self, engine: OperatorWorkspaceEngine):
        result = engine.detect_workspace_violations("t1")
        assert isinstance(result, tuple)

    def test_empty_panel_violation(self, engine: OperatorWorkspaceEngine):
        engine.register_view("v1", "t1", "op1", "V")
        engine.register_panel("p1", "v1", "t1", "P", PanelKind.QUEUE, "rt1")
        viols = engine.detect_workspace_violations("t1")
        assert len(viols) == 1
        assert viols[0].operation == "empty_panel"

    def test_no_empty_panel_if_items(self, engine: OperatorWorkspaceEngine):
        engine.register_view("v1", "t1", "op1", "V")
        engine.register_panel("p1", "v1", "t1", "P", PanelKind.QUEUE, "rt1")
        engine.enqueue_item("q1", "p1", "t1", "s1", "rt1")
        viols = engine.detect_workspace_violations("t1")
        empty_panel_viols = [v for v in viols if v.operation == "empty_panel"]
        assert len(empty_panel_viols) == 0

    def test_no_empty_panel_if_retired_view(self, engine: OperatorWorkspaceEngine):
        engine.register_view("v1", "t1", "op1", "V")
        engine.register_panel("p1", "v1", "t1", "P", PanelKind.QUEUE, "rt1")
        engine.retire_view("v1")
        viols = engine.detect_workspace_violations("t1")
        empty_panel_viols = [v for v in viols if v.operation == "empty_panel"]
        assert len(empty_panel_viols) == 0

    def test_high_priority_pending_violation(self, engine: OperatorWorkspaceEngine):
        engine.register_view("v1", "t1", "op1", "V")
        engine.register_panel("p1", "v1", "t1", "P", PanelKind.QUEUE, "rt1")
        engine.enqueue_item("q1", "p1", "t1", "s1", "rt1", priority=5)
        viols = engine.detect_workspace_violations("t1")
        hpp = [v for v in viols if v.operation == "high_priority_pending"]
        assert len(hpp) == 1

    def test_no_high_priority_if_priority_below_5(self, engine: OperatorWorkspaceEngine):
        engine.register_view("v1", "t1", "op1", "V")
        engine.register_panel("p1", "v1", "t1", "P", PanelKind.QUEUE, "rt1")
        engine.enqueue_item("q1", "p1", "t1", "s1", "rt1", priority=4)
        viols = engine.detect_workspace_violations("t1")
        hpp = [v for v in viols if v.operation == "high_priority_pending"]
        assert len(hpp) == 0

    def test_no_high_priority_if_completed(self, engine: OperatorWorkspaceEngine):
        engine.register_view("v1", "t1", "op1", "V")
        engine.register_panel("p1", "v1", "t1", "P", PanelKind.QUEUE, "rt1")
        engine.enqueue_item("q1", "p1", "t1", "s1", "rt1", priority=5)
        engine.complete_queue_item("q1")
        viols = engine.detect_workspace_violations("t1")
        hpp = [v for v in viols if v.operation == "high_priority_pending"]
        assert len(hpp) == 0

    def test_high_priority_at_boundary(self, engine: OperatorWorkspaceEngine):
        engine.register_view("v1", "t1", "op1", "V")
        engine.register_panel("p1", "v1", "t1", "P", PanelKind.QUEUE, "rt1")
        engine.enqueue_item("q1", "p1", "t1", "s1", "rt1", priority=5)
        viols = engine.detect_workspace_violations("t1")
        hpp = [v for v in viols if v.operation == "high_priority_pending"]
        assert len(hpp) == 1

    def test_high_priority_above_boundary(self, engine: OperatorWorkspaceEngine):
        engine.register_view("v1", "t1", "op1", "V")
        engine.register_panel("p1", "v1", "t1", "P", PanelKind.QUEUE, "rt1")
        engine.enqueue_item("q1", "p1", "t1", "s1", "rt1", priority=10)
        viols = engine.detect_workspace_violations("t1")
        hpp = [v for v in viols if v.operation == "high_priority_pending"]
        assert len(hpp) == 1

    def test_failed_no_decision_violation(self, engine: OperatorWorkspaceEngine):
        engine.record_action("a1", "t1", "op1", "tgt1", "rt1", "approve")
        engine.fail_action("a1")
        viols = engine.detect_workspace_violations("t1")
        fnd = [v for v in viols if v.operation == "failed_no_decision"]
        assert len(fnd) == 1

    def test_no_failed_no_decision_if_decision_exists(self, engine: OperatorWorkspaceEngine):
        engine.record_action("a1", "t1", "op1", "tgt1", "rt1", "approve")
        engine.fail_action("a1")
        engine.record_decision("d1", "t1", "op1", "a1", "rejected", "bad")
        viols = engine.detect_workspace_violations("t1")
        fnd = [v for v in viols if v.operation == "failed_no_decision"]
        assert len(fnd) == 0

    def test_no_failed_no_decision_if_initiated(self, engine: OperatorWorkspaceEngine):
        engine.record_action("a1", "t1", "op1", "tgt1", "rt1", "approve")
        viols = engine.detect_workspace_violations("t1")
        fnd = [v for v in viols if v.operation == "failed_no_decision"]
        assert len(fnd) == 0

    def test_no_failed_no_decision_if_completed(self, engine: OperatorWorkspaceEngine):
        engine.record_action("a1", "t1", "op1", "tgt1", "rt1", "approve")
        engine.complete_action("a1")
        viols = engine.detect_workspace_violations("t1")
        fnd = [v for v in viols if v.operation == "failed_no_decision"]
        assert len(fnd) == 0

    def test_idempotent_violations(self, engine: OperatorWorkspaceEngine):
        engine.register_view("v1", "t1", "op1", "V")
        engine.register_panel("p1", "v1", "t1", "P", PanelKind.QUEUE, "rt1")
        v1 = engine.detect_workspace_violations("t1")
        v2 = engine.detect_workspace_violations("t1")
        assert len(v1) == 1
        assert len(v2) == 0  # idempotent — no new violations

    def test_idempotent_high_priority(self, engine: OperatorWorkspaceEngine):
        engine.register_view("v1", "t1", "op1", "V")
        engine.register_panel("p1", "v1", "t1", "P", PanelKind.QUEUE, "rt1")
        engine.enqueue_item("q1", "p1", "t1", "s1", "rt1", priority=5)
        v1 = engine.detect_workspace_violations("t1")
        v2 = engine.detect_workspace_violations("t1")
        hpp1 = [v for v in v1 if v.operation == "high_priority_pending"]
        hpp2 = [v for v in v2 if v.operation == "high_priority_pending"]
        assert len(hpp1) == 1
        assert len(hpp2) == 0

    def test_violations_filtered_by_tenant(self, engine: OperatorWorkspaceEngine):
        engine.register_view("v1", "t1", "op1", "V1")
        engine.register_panel("p1", "v1", "t1", "P1", PanelKind.QUEUE, "rt1")
        engine.register_view("v2", "t2", "op2", "V2")
        engine.register_panel("p2", "v2", "t2", "P2", PanelKind.QUEUE, "rt1")
        t1_viols = engine.detect_workspace_violations("t1")
        t2_viols = engine.detect_workspace_violations("t2")
        for v in t1_viols:
            assert v.tenant_id == "t1"
        for v in t2_viols:
            assert v.tenant_id == "t2"

    def test_violation_increments_count(self, engine: OperatorWorkspaceEngine):
        engine.register_view("v1", "t1", "op1", "V")
        engine.register_panel("p1", "v1", "t1", "P", PanelKind.QUEUE, "rt1")
        engine.detect_workspace_violations("t1")
        assert engine.violation_count >= 1

    def test_violation_emits_event_when_new(self, es: EventSpineEngine, engine: OperatorWorkspaceEngine):
        engine.register_view("v1", "t1", "op1", "V")
        engine.register_panel("p1", "v1", "t1", "P", PanelKind.QUEUE, "rt1")
        before = es.event_count
        engine.detect_workspace_violations("t1")
        assert es.event_count > before

    def test_violation_no_event_when_idempotent(self, es: EventSpineEngine, engine: OperatorWorkspaceEngine):
        engine.register_view("v1", "t1", "op1", "V")
        engine.register_panel("p1", "v1", "t1", "P", PanelKind.QUEUE, "rt1")
        engine.detect_workspace_violations("t1")
        before = es.event_count
        engine.detect_workspace_violations("t1")
        assert es.event_count == before

    def test_violations_for_tenant(self, engine: OperatorWorkspaceEngine):
        engine.register_view("v1", "t1", "op1", "V")
        engine.register_panel("p1", "v1", "t1", "P", PanelKind.QUEUE, "rt1")
        engine.detect_workspace_violations("t1")
        result = engine.violations_for_tenant("t1")
        assert isinstance(result, tuple)
        assert len(result) >= 1

    def test_violations_for_tenant_empty(self, engine: OperatorWorkspaceEngine):
        assert engine.violations_for_tenant("t1") == ()

    def test_multiple_violation_types(self, engine: OperatorWorkspaceEngine):
        engine.register_view("v1", "t1", "op1", "V")
        engine.register_panel("p1", "v1", "t1", "P", PanelKind.QUEUE, "rt1")
        engine.enqueue_item("q1", "p1", "t1", "s1", "rt1", priority=7)
        engine.record_action("a1", "t1", "op1", "tgt1", "rt1", "act")
        engine.fail_action("a1")
        # empty_panel won't fire because p1 has items
        viols = engine.detect_workspace_violations("t1")
        ops = {v.operation for v in viols}
        assert "high_priority_pending" in ops
        assert "failed_no_decision" in ops


# ===================================================================
# Closure report
# ===================================================================


class TestClosureReport:
    def test_closure_returns_report(self, engine: OperatorWorkspaceEngine):
        r = engine.closure_report("rep1", "t1")
        assert isinstance(r, WorkspaceClosureReport)

    def test_closure_fields_empty(self, engine: OperatorWorkspaceEngine):
        r = engine.closure_report("rep1", "t1")
        assert r.report_id == "rep1"
        assert r.tenant_id == "t1"
        assert r.total_views == 0
        assert r.total_panels == 0
        assert r.total_queue_items == 0
        assert r.total_worklist_items == 0
        assert r.total_actions == 0
        assert r.total_violations == 0

    def test_closure_with_data(self, engine: OperatorWorkspaceEngine):
        engine.register_view("v1", "t1", "op1", "V")
        engine.register_panel("p1", "v1", "t1", "P", PanelKind.QUEUE, "rt1")
        engine.enqueue_item("q1", "p1", "t1", "s1", "rt1")
        engine.add_worklist_item("w1", "t1", "op1", "s1", "rt1", "T")
        engine.record_action("a1", "t1", "op1", "tgt1", "rt1", "act")
        r = engine.closure_report("rep1", "t1")
        assert r.total_views == 1
        assert r.total_panels == 1
        assert r.total_queue_items == 1
        assert r.total_worklist_items == 1
        assert r.total_actions == 1

    def test_closure_includes_violations(self, engine: OperatorWorkspaceEngine):
        engine.register_view("v1", "t1", "op1", "V")
        engine.register_panel("p1", "v1", "t1", "P", PanelKind.QUEUE, "rt1")
        engine.detect_workspace_violations("t1")
        r = engine.closure_report("rep1", "t1")
        assert r.total_violations >= 1

    def test_closure_filters_by_tenant(self, engine: OperatorWorkspaceEngine):
        engine.register_view("v1", "t1", "op1", "V1")
        engine.register_view("v2", "t2", "op2", "V2")
        r = engine.closure_report("rep1", "t1")
        assert r.total_views == 1

    def test_closure_emits_event(self, es: EventSpineEngine, engine: OperatorWorkspaceEngine):
        before = es.event_count
        engine.closure_report("rep1", "t1")
        assert es.event_count > before

    def test_closure_has_created_at(self, engine: OperatorWorkspaceEngine):
        r = engine.closure_report("rep1", "t1")
        assert r.created_at


# ===================================================================
# State hash
# ===================================================================


class TestStateHash:
    def test_state_hash_returns_string(self, engine: OperatorWorkspaceEngine):
        h = engine.state_hash()
        assert isinstance(h, str)
        assert len(h) > 0

    def test_state_hash_deterministic(self, engine: OperatorWorkspaceEngine):
        h1 = engine.state_hash()
        h2 = engine.state_hash()
        assert h1 == h2

    def test_state_hash_changes_with_view(self, engine: OperatorWorkspaceEngine):
        h1 = engine.state_hash()
        engine.register_view("v1", "t1", "op1", "V")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_state_hash_changes_with_panel(self, engine_with_view: OperatorWorkspaceEngine):
        h1 = engine_with_view.state_hash()
        engine_with_view.register_panel("p1", "v1", "t1", "P", PanelKind.QUEUE, "rt1")
        h2 = engine_with_view.state_hash()
        assert h1 != h2

    def test_state_hash_changes_with_queue(self, engine_with_panel: OperatorWorkspaceEngine):
        h1 = engine_with_panel.state_hash()
        engine_with_panel.enqueue_item("q1", "p1", "t1", "s1", "rt1")
        h2 = engine_with_panel.state_hash()
        assert h1 != h2

    def test_state_hash_changes_with_status_transition(self, engine_with_queue_item: OperatorWorkspaceEngine):
        h1 = engine_with_queue_item.state_hash()
        engine_with_queue_item.complete_queue_item("q1")
        h2 = engine_with_queue_item.state_hash()
        assert h1 != h2

    def test_state_hash_changes_with_worklist(self, engine: OperatorWorkspaceEngine):
        h1 = engine.state_hash()
        engine.add_worklist_item("w1", "t1", "op1", "s1", "rt1", "T")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_state_hash_changes_with_action(self, engine: OperatorWorkspaceEngine):
        h1 = engine.state_hash()
        engine.record_action("a1", "t1", "op1", "tgt1", "rt1", "act")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_state_hash_changes_with_violation(self, engine: OperatorWorkspaceEngine):
        engine.register_view("v1", "t1", "op1", "V")
        engine.register_panel("p1", "v1", "t1", "P", PanelKind.QUEUE, "rt1")
        h1 = engine.state_hash()
        engine.detect_workspace_violations("t1")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_state_hash_sha256_hex(self, engine: OperatorWorkspaceEngine):
        h = engine.state_hash()
        # SHA-256 hex is 64 chars
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_same_operations_same_hash(self, es: EventSpineEngine):
        """Two engines with identical operations produce the same state hash."""
        e1 = OperatorWorkspaceEngine(EventSpineEngine())
        e2 = OperatorWorkspaceEngine(EventSpineEngine())
        e1.register_view("v1", "t1", "op1", "V")
        e2.register_view("v1", "t1", "op1", "V")
        assert e1.state_hash() == e2.state_hash()


# ===================================================================
# Count properties
# ===================================================================


class TestCountProperties:
    def test_view_count(self, engine: OperatorWorkspaceEngine):
        assert engine.view_count == 0
        engine.register_view("v1", "t1", "op1", "V")
        assert engine.view_count == 1

    def test_panel_count(self, engine_with_view: OperatorWorkspaceEngine):
        assert engine_with_view.panel_count == 0
        engine_with_view.register_panel("p1", "v1", "t1", "P", PanelKind.QUEUE, "rt1")
        assert engine_with_view.panel_count == 1

    def test_queue_count(self, engine_with_panel: OperatorWorkspaceEngine):
        assert engine_with_panel.queue_count == 0
        engine_with_panel.enqueue_item("q1", "p1", "t1", "s1", "rt1")
        assert engine_with_panel.queue_count == 1

    def test_worklist_count(self, engine: OperatorWorkspaceEngine):
        assert engine.worklist_count == 0
        engine.add_worklist_item("w1", "t1", "op1", "s1", "rt1", "T")
        assert engine.worklist_count == 1

    def test_action_count(self, engine: OperatorWorkspaceEngine):
        assert engine.action_count == 0
        engine.record_action("a1", "t1", "op1", "tgt1", "rt1", "act")
        assert engine.action_count == 1

    def test_decision_count(self, engine: OperatorWorkspaceEngine):
        assert engine.decision_count == 0
        engine.record_decision("d1", "t1", "op1", "a1")
        assert engine.decision_count == 1

    def test_violation_count(self, engine: OperatorWorkspaceEngine):
        assert engine.violation_count == 0

    def test_assessment_count(self, engine: OperatorWorkspaceEngine):
        assert engine.assessment_count == 0
        engine.workspace_assessment("assess1", "t1")
        assert engine.assessment_count == 1


# ===================================================================
# Golden scenario 1: Service request in fulfillment queue
# ===================================================================


class TestGoldenServiceRequest:
    """Full lifecycle: register view + panel, enqueue, assign, start, complete."""

    def test_register_view(self, engine: OperatorWorkspaceEngine):
        v = engine.register_view("fulfillment-view", "tenant-acme", "op-jane", "Fulfillment", WorkspaceScope.TEAM)
        assert v.status == WorkspaceStatus.ACTIVE
        assert v.disposition == ViewDisposition.OPEN

    def test_register_panel(self, engine: OperatorWorkspaceEngine):
        engine.register_view("fv", "ta", "oj", "Fulfillment", WorkspaceScope.TEAM)
        p = engine.register_panel("fp", "fv", "ta", "Service Queue", PanelKind.QUEUE, "fulfillment-rt")
        assert p.kind == PanelKind.QUEUE
        assert p.item_count == 0

    def test_enqueue_service_request(self, engine: OperatorWorkspaceEngine):
        engine.register_view("fv", "ta", "oj", "Fulfillment", WorkspaceScope.TEAM)
        engine.register_panel("fp", "fv", "ta", "Service Queue", PanelKind.QUEUE, "fulfillment-rt")
        q = engine.enqueue_item("sr-001", "fp", "ta", "case-123", "case-rt", "unassigned", 3)
        assert q.status == QueueStatus.PENDING

    def test_full_lifecycle(self, engine: OperatorWorkspaceEngine):
        engine.register_view("fv", "ta", "oj", "Fulfillment", WorkspaceScope.TEAM)
        engine.register_panel("fp", "fv", "ta", "Service Queue", PanelKind.QUEUE, "fulfillment-rt")
        engine.enqueue_item("sr-001", "fp", "ta", "case-123", "case-rt", "unassigned", 3)
        q = engine.assign_queue_item("sr-001", "op-jane")
        assert q.status == QueueStatus.ASSIGNED
        assert q.assignee_ref == "op-jane"
        q = engine.start_queue_item("sr-001")
        assert q.status == QueueStatus.IN_PROGRESS
        q = engine.complete_queue_item("sr-001")
        assert q.status == QueueStatus.COMPLETED

    def test_completed_blocks_further_transitions(self, engine: OperatorWorkspaceEngine):
        engine.register_view("fv", "ta", "oj", "Fulfillment", WorkspaceScope.TEAM)
        engine.register_panel("fp", "fv", "ta", "SQ", PanelKind.QUEUE, "rt")
        engine.enqueue_item("sr", "fp", "ta", "c", "rt")
        engine.complete_queue_item("sr")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.assign_queue_item("sr", "op")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.start_queue_item("sr")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.escalate_queue_item("sr")

    def test_snapshot_after_lifecycle(self, engine: OperatorWorkspaceEngine):
        engine.register_view("fv", "ta", "oj", "Fulfillment", WorkspaceScope.TEAM)
        engine.register_panel("fp", "fv", "ta", "SQ", PanelKind.QUEUE, "rt")
        engine.enqueue_item("sr", "fp", "ta", "c", "rt")
        engine.complete_queue_item("sr")
        snap = engine.workspace_snapshot("s1", "ta")
        assert snap.total_queue_items == 1
        assert snap.pending_queue_items == 0


# ===================================================================
# Golden scenario 2: Case review in investigator queue
# ===================================================================


class TestGoldenCaseReview:
    """Case review in INVESTIGATION panel."""

    def test_investigation_panel(self, engine: OperatorWorkspaceEngine):
        engine.register_view("inv-view", "t-bank", "inv-ops", "Investigations", WorkspaceScope.TEAM)
        p = engine.register_panel("inv-panel", "inv-view", "t-bank", "Fraud Review", PanelKind.INVESTIGATION, "fraud-rt")
        assert p.kind == PanelKind.INVESTIGATION

    def test_enqueue_case_review(self, engine: OperatorWorkspaceEngine):
        engine.register_view("iv", "tb", "io", "Inv", WorkspaceScope.TEAM)
        engine.register_panel("ip", "iv", "tb", "Fraud", PanelKind.INVESTIGATION, "frt")
        q = engine.enqueue_item("cr-001", "ip", "tb", "case-456", "case-rt", "unassigned", 7)
        assert q.status == QueueStatus.PENDING
        assert q.priority == 7

    def test_case_review_lifecycle(self, engine: OperatorWorkspaceEngine):
        engine.register_view("iv", "tb", "io", "Inv", WorkspaceScope.TEAM)
        engine.register_panel("ip", "iv", "tb", "Fraud", PanelKind.INVESTIGATION, "frt")
        engine.enqueue_item("cr-001", "ip", "tb", "case-456", "case-rt", "unassigned", 7)
        engine.assign_queue_item("cr-001", "inv-agent")
        engine.start_queue_item("cr-001")
        engine.record_action("act-inv", "tb", "io", "case-456", "case-rt", "investigate")
        engine.complete_action("act-inv")
        engine.record_decision("dec-inv", "tb", "io", "act-inv", "escalated", "suspicious pattern")
        q = engine.complete_queue_item("cr-001")
        assert q.status == QueueStatus.COMPLETED

    def test_high_priority_violation_detected(self, engine: OperatorWorkspaceEngine):
        engine.register_view("iv", "tb", "io", "Inv", WorkspaceScope.TEAM)
        engine.register_panel("ip", "iv", "tb", "Fraud", PanelKind.INVESTIGATION, "frt")
        engine.enqueue_item("cr-001", "ip", "tb", "case-456", "case-rt", "unassigned", 8)
        viols = engine.detect_workspace_violations("tb")
        hpp = [v for v in viols if v.operation == "high_priority_pending"]
        assert len(hpp) == 1


# ===================================================================
# Golden scenario 3: Remediation overdue in operator worklist
# ===================================================================


class TestGoldenRemediationOverdue:
    """Worklist item with high priority for remediation."""

    def test_add_high_priority_worklist(self, engine: OperatorWorkspaceEngine):
        w = engine.add_worklist_item("rem-001", "t-ops", "op-admin", "rem-ref", "rem-rt", "Fix outage", 5)
        assert w.priority == 5
        assert w.status == QueueStatus.PENDING

    def test_worklist_sorted_high_first(self, engine: OperatorWorkspaceEngine):
        engine.add_worklist_item("rem-lo", "t-ops", "op-admin", "r1", "rt", "Low task", 1)
        engine.add_worklist_item("rem-hi", "t-ops", "op-admin", "r2", "rt", "High task", 5)
        engine.add_worklist_item("rem-mid", "t-ops", "op-admin", "r3", "rt", "Mid task", 3)
        items = engine.worklist_for_operator("t-ops", "op-admin")
        assert items[0].priority == 5
        assert items[1].priority == 3
        assert items[2].priority == 1

    def test_complete_remediation(self, engine: OperatorWorkspaceEngine):
        engine.add_worklist_item("rem-001", "t-ops", "op-admin", "r1", "rt", "Fix outage", 5)
        w = engine.complete_worklist_item("rem-001")
        assert w.status == QueueStatus.COMPLETED

    def test_completed_blocks_double_complete(self, engine: OperatorWorkspaceEngine):
        engine.add_worklist_item("rem-001", "t-ops", "op-admin", "r1", "rt", "Fix outage", 5)
        engine.complete_worklist_item("rem-001")
        with pytest.raises(RuntimeCoreInvariantError, match="already completed"):
            engine.complete_worklist_item("rem-001")


# ===================================================================
# Golden scenario 4: Executive issue in control panel
# ===================================================================


class TestGoldenExecutiveControl:
    """Executive scope view with APPROVAL panel."""

    def test_executive_view(self, engine: OperatorWorkspaceEngine):
        v = engine.register_view("exec-view", "t-corp", "cfo", "Board Review", WorkspaceScope.EXECUTIVE)
        assert v.scope == WorkspaceScope.EXECUTIVE

    def test_approval_panel(self, engine: OperatorWorkspaceEngine):
        engine.register_view("ev", "tc", "cfo", "Board", WorkspaceScope.EXECUTIVE)
        p = engine.register_panel("ap", "ev", "tc", "Budget Approval", PanelKind.APPROVAL, "finance-rt")
        assert p.kind == PanelKind.APPROVAL

    def test_executive_full_lifecycle(self, engine: OperatorWorkspaceEngine):
        engine.register_view("ev", "tc", "cfo", "Board", WorkspaceScope.EXECUTIVE)
        engine.register_panel("ap", "ev", "tc", "Budget Approval", PanelKind.APPROVAL, "fin-rt")
        engine.enqueue_item("budg-001", "ap", "tc", "budget-ref", "fin-rt", "cfo", 9)
        engine.record_action("act-budg", "tc", "cfo", "budget-ref", "fin-rt", "approve_budget")
        engine.complete_action("act-budg")
        engine.record_decision("dec-budg", "tc", "cfo", "act-budg", "approved", "within limits")
        q = engine.complete_queue_item("budg-001")
        assert q.status == QueueStatus.COMPLETED

    def test_executive_snapshot(self, engine: OperatorWorkspaceEngine):
        engine.register_view("ev", "tc", "cfo", "Board", WorkspaceScope.EXECUTIVE)
        engine.register_panel("ap", "ev", "tc", "BA", PanelKind.APPROVAL, "rt")
        engine.enqueue_item("b1", "ap", "tc", "br", "rt", "cfo", 9)
        snap = engine.workspace_snapshot("s-exec", "tc")
        assert snap.total_views == 1
        assert snap.total_panels == 1
        assert snap.total_queue_items == 1


# ===================================================================
# Golden scenario 5: Cross-tenant access denied fail-closed
# ===================================================================


class TestGoldenCrossTenantDenied:
    """All cross-tenant operations must raise."""

    def test_cross_tenant_panel_creation(self, engine: OperatorWorkspaceEngine):
        engine.register_view("v1", "t1", "op1", "V")
        with pytest.raises(RuntimeCoreInvariantError, match="cross-tenant"):
            engine.register_panel("p1", "v1", "t-evil", "P", PanelKind.QUEUE, "rt")

    def test_cross_tenant_enqueue(self, engine: OperatorWorkspaceEngine):
        engine.register_view("v1", "t1", "op1", "V")
        engine.register_panel("p1", "v1", "t1", "P", PanelKind.QUEUE, "rt")
        with pytest.raises(RuntimeCoreInvariantError, match="cross-tenant"):
            engine.enqueue_item("q1", "p1", "t-evil", "src", "rt")

    def test_cross_tenant_views_isolated(self, engine: OperatorWorkspaceEngine):
        engine.register_view("v1", "t1", "op1", "V1")
        engine.register_view("v2", "t2", "op2", "V2")
        assert len(engine.views_for_tenant("t1")) == 1
        assert len(engine.views_for_tenant("t2")) == 1

    def test_cross_tenant_pending_isolated(self, engine: OperatorWorkspaceEngine):
        engine.register_view("v1", "t1", "op1", "V1")
        engine.register_panel("p1", "v1", "t1", "P1", PanelKind.QUEUE, "rt")
        engine.enqueue_item("q1", "p1", "t1", "s1", "rt")
        assert len(engine.pending_queue_items("t2")) == 0

    def test_cross_tenant_violations_isolated(self, engine: OperatorWorkspaceEngine):
        engine.register_view("v1", "t1", "op1", "V")
        engine.register_panel("p1", "v1", "t1", "P", PanelKind.QUEUE, "rt")
        engine.detect_workspace_violations("t1")
        assert len(engine.violations_for_tenant("t2")) == 0

    def test_cross_tenant_snapshot_isolated(self, engine: OperatorWorkspaceEngine):
        engine.register_view("v1", "t1", "op1", "V")
        snap = engine.workspace_snapshot("s1", "t2")
        assert snap.total_views == 0

    def test_cross_tenant_closure_isolated(self, engine: OperatorWorkspaceEngine):
        engine.register_view("v1", "t1", "op1", "V")
        r = engine.closure_report("r1", "t2")
        assert r.total_views == 0

    def test_cross_tenant_worklist_isolated(self, engine: OperatorWorkspaceEngine):
        engine.add_worklist_item("w1", "t1", "op1", "s1", "rt", "T")
        assert len(engine.worklist_for_operator("t2", "op1")) == 0

    def test_cross_tenant_actions_isolated(self, engine: OperatorWorkspaceEngine):
        engine.record_action("a1", "t1", "op1", "tgt", "rt", "act")
        assert len(engine.actions_for_operator("t2", "op1")) == 0

    def test_cross_tenant_assessment_isolated(self, engine: OperatorWorkspaceEngine):
        engine.register_view("v1", "t1", "op1", "V")
        a = engine.workspace_assessment("assess1", "t2")
        assert a.total_views == 0


# ===================================================================
# Golden scenario 6: Replay/restore preserves state hash
# ===================================================================


class TestGoldenReplayRestore:
    """State hash determinism across identical operation sequences."""

    def _build_workspace(self, es: EventSpineEngine) -> OperatorWorkspaceEngine:
        eng = OperatorWorkspaceEngine(es)
        eng.register_view("v1", "t1", "op1", "V", WorkspaceScope.TEAM)
        eng.register_panel("p1", "v1", "t1", "P", PanelKind.QUEUE, "rt1")
        eng.enqueue_item("q1", "p1", "t1", "src", "rt1", "a", 3)
        eng.enqueue_item("q2", "p1", "t1", "src2", "rt1", "b", 7)
        eng.assign_queue_item("q1", "op1")
        eng.start_queue_item("q1")
        eng.complete_queue_item("q1")
        eng.add_worklist_item("w1", "t1", "op1", "s1", "rt1", "T", 5)
        eng.record_action("act1", "t1", "op1", "tgt", "rt1", "approve")
        eng.complete_action("act1")
        eng.record_decision("dec1", "t1", "op1", "act1", "approved", "ok")
        return eng

    def test_same_sequence_same_hash(self):
        e1 = self._build_workspace(EventSpineEngine())
        e2 = self._build_workspace(EventSpineEngine())
        assert e1.state_hash() == e2.state_hash()

    def test_hash_changes_with_extra_operation(self):
        e1 = self._build_workspace(EventSpineEngine())
        e2 = self._build_workspace(EventSpineEngine())
        e2.complete_worklist_item("w1")
        assert e1.state_hash() != e2.state_hash()

    def test_hash_stable_across_reads(self):
        eng = self._build_workspace(EventSpineEngine())
        h1 = eng.state_hash()
        _ = eng.views_for_tenant("t1")
        _ = eng.pending_queue_items("t1")
        _ = eng.worklist_for_operator("t1", "op1")
        h2 = eng.state_hash()
        assert h1 == h2

    def test_snapshot_reflects_state(self):
        eng = self._build_workspace(EventSpineEngine())
        snap = eng.workspace_snapshot("s1", "t1")
        assert snap.total_views == 1
        assert snap.total_panels == 1
        assert snap.total_queue_items == 2
        assert snap.pending_queue_items == 1  # q2 still pending
        assert snap.total_worklist_items == 1
        assert snap.total_actions == 1

    def test_closure_report_reflects_state(self):
        eng = self._build_workspace(EventSpineEngine())
        r = eng.closure_report("r1", "t1")
        assert r.total_views == 1
        assert r.total_panels == 1
        assert r.total_queue_items == 2
        assert r.total_worklist_items == 1
        assert r.total_actions == 1

    def test_assessment_reflects_state(self):
        eng = self._build_workspace(EventSpineEngine())
        a = eng.workspace_assessment("a1", "t1")
        assert a.total_views == 1
        assert a.active_views == 1
        assert a.queue_depth == 2
        assert a.pending_rate == 0.5  # 1 pending out of 2 total


# ===================================================================
# Golden scenario 7: Failed action + decision lifecycle
# ===================================================================


class TestGoldenFailedActionDecision:
    """Failed action with decision resolves violation."""

    def test_failed_without_decision_generates_violation(self, engine: OperatorWorkspaceEngine):
        engine.record_action("a1", "t1", "op1", "tgt", "rt", "deploy")
        engine.fail_action("a1")
        viols = engine.detect_workspace_violations("t1")
        fnd = [v for v in viols if v.operation == "failed_no_decision"]
        assert len(fnd) == 1

    def test_decision_resolves_violation(self, engine: OperatorWorkspaceEngine):
        engine.record_action("a1", "t1", "op1", "tgt", "rt", "deploy")
        engine.fail_action("a1")
        engine.record_decision("d1", "t1", "op1", "a1", "rejected", "deploy failed")
        viols = engine.detect_workspace_violations("t1")
        fnd = [v for v in viols if v.operation == "failed_no_decision"]
        assert len(fnd) == 0

    def test_complete_lifecycle_with_closure(self, engine: OperatorWorkspaceEngine):
        engine.record_action("a1", "t1", "op1", "tgt", "rt", "deploy")
        engine.fail_action("a1")
        engine.record_decision("d1", "t1", "op1", "a1", "rejected", "bad deploy")
        engine.detect_workspace_violations("t1")
        r = engine.closure_report("r1", "t1")
        assert r.total_actions == 1
        assert r.total_violations == 0


# ===================================================================
# Golden scenario 8: Multi-operator multi-panel workspace
# ===================================================================


class TestGoldenMultiOperator:
    """Multiple operators with multiple panels in one tenant."""

    def test_multi_operator_views(self, engine: OperatorWorkspaceEngine):
        engine.register_view("v-alice", "t1", "alice", "Alice View", WorkspaceScope.PERSONAL)
        engine.register_view("v-bob", "t1", "bob", "Bob View", WorkspaceScope.PERSONAL)
        assert len(engine.views_for_operator("t1", "alice")) == 1
        assert len(engine.views_for_operator("t1", "bob")) == 1
        assert len(engine.views_for_tenant("t1")) == 2

    def test_multi_panel_workspace(self, engine: OperatorWorkspaceEngine):
        engine.register_view("v1", "t1", "op1", "V", WorkspaceScope.TEAM)
        engine.register_panel("p-q", "v1", "t1", "Queue", PanelKind.QUEUE, "rt")
        engine.register_panel("p-d", "v1", "t1", "Dashboard", PanelKind.DASHBOARD, "rt")
        engine.register_panel("p-r", "v1", "t1", "Review", PanelKind.REVIEW, "rt")
        v = engine.get_view("v1")
        assert v.panel_count == 3
        assert len(engine.panels_for_view("v1")) == 3

    def test_multi_operator_worklist(self, engine: OperatorWorkspaceEngine):
        engine.add_worklist_item("w-a1", "t1", "alice", "s1", "rt", "Alice task 1", 3)
        engine.add_worklist_item("w-a2", "t1", "alice", "s2", "rt", "Alice task 2", 7)
        engine.add_worklist_item("w-b1", "t1", "bob", "s3", "rt", "Bob task 1", 5)
        alice_items = engine.worklist_for_operator("t1", "alice")
        bob_items = engine.worklist_for_operator("t1", "bob")
        assert len(alice_items) == 2
        assert len(bob_items) == 1
        assert alice_items[0].priority == 7  # highest first

    def test_multi_operator_actions(self, engine: OperatorWorkspaceEngine):
        engine.record_action("a-alice", "t1", "alice", "tgt1", "rt", "act1")
        engine.record_action("a-bob", "t1", "bob", "tgt2", "rt", "act2")
        assert len(engine.actions_for_operator("t1", "alice")) == 1
        assert len(engine.actions_for_operator("t1", "bob")) == 1


# ===================================================================
# Edge cases and additional coverage
# ===================================================================


class TestEdgeCases:
    def test_view_retire_is_terminal(self, engine_with_view: OperatorWorkspaceEngine):
        """RETIRED is terminal for views — cannot suspend after retire."""
        engine_with_view.retire_view("v1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine_with_view.suspend_view("v1")

    def test_queue_completed_is_terminal(self, engine_with_queue_item: OperatorWorkspaceEngine):
        engine_with_queue_item.complete_queue_item("q1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine_with_queue_item.complete_queue_item("q1")

    def test_action_completed_then_fail_raises(self, engine: OperatorWorkspaceEngine):
        engine.record_action("a1", "t1", "op1", "tgt", "rt", "act")
        engine.complete_action("a1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.fail_action("a1")

    def test_action_failed_then_complete_raises(self, engine: OperatorWorkspaceEngine):
        engine.record_action("a1", "t1", "op1", "tgt", "rt", "act")
        engine.fail_action("a1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.complete_action("a1")

    def test_empty_state_hash(self, engine: OperatorWorkspaceEngine):
        h = engine.state_hash()
        assert isinstance(h, str)
        assert len(h) == 64

    def test_queue_items_sorted_many(self, engine_with_panel: OperatorWorkspaceEngine):
        for i in range(20):
            engine_with_panel.enqueue_item(f"q{i}", "p1", "t1", f"s{i}", "rt1", priority=i % 10)
        items = engine_with_panel.queue_items_for_panel("p1")
        for a, b in zip(items, items[1:]):
            assert a.priority >= b.priority
            if a.priority == b.priority:
                assert a.created_at <= b.created_at

    def test_worklist_sorted_many(self, engine: OperatorWorkspaceEngine):
        for i in range(20):
            engine.add_worklist_item(f"w{i}", "t1", "op1", f"s{i}", "rt", f"T{i}", i % 10)
        items = engine.worklist_for_operator("t1", "op1")
        for a, b in zip(items, items[1:]):
            assert a.priority >= b.priority
            if a.priority == b.priority:
                assert a.created_at <= b.created_at

    def test_snapshot_no_id_collision(self, engine: OperatorWorkspaceEngine):
        """Snapshots are not deduplicated by ID (no dup check)."""
        s1 = engine.workspace_snapshot("s1", "t1")
        s2 = engine.workspace_snapshot("s2", "t1")
        assert s1.snapshot_id != s2.snapshot_id

    def test_violation_has_reason(self, engine: OperatorWorkspaceEngine):
        engine.register_view("v1", "t1", "op1", "V")
        engine.register_panel("p1", "v1", "t1", "P", PanelKind.QUEUE, "rt1")
        viols = engine.detect_workspace_violations("t1")
        assert viols[0].reason  # non-empty

    def test_violation_has_detected_at(self, engine: OperatorWorkspaceEngine):
        engine.register_view("v1", "t1", "op1", "V")
        engine.register_panel("p1", "v1", "t1", "P", PanelKind.QUEUE, "rt1")
        viols = engine.detect_workspace_violations("t1")
        assert viols[0].detected_at

    def test_panel_default_kind(self, engine_with_view: OperatorWorkspaceEngine):
        p = engine_with_view.register_panel("p1", "v1", "t1", "P")
        assert p.kind == PanelKind.QUEUE

    def test_panel_default_target_runtime(self, engine_with_view: OperatorWorkspaceEngine):
        p = engine_with_view.register_panel("p1", "v1", "t1", "P")
        assert p.target_runtime == "unknown"

    def test_decision_frozen(self, engine: OperatorWorkspaceEngine):
        d = engine.record_decision("d1", "t1", "op1", "a1")
        with pytest.raises(AttributeError):
            d.decision_id = "changed"

    def test_action_frozen(self, engine: OperatorWorkspaceEngine):
        a = engine.record_action("a1", "t1", "op1", "tgt", "rt", "act")
        with pytest.raises(AttributeError):
            a.action_id = "changed"

    def test_worklist_frozen(self, engine: OperatorWorkspaceEngine):
        w = engine.add_worklist_item("w1", "t1", "op1", "s1", "rt", "T")
        with pytest.raises(AttributeError):
            w.item_id = "changed"

    def test_queue_record_frozen(self, engine_with_panel: OperatorWorkspaceEngine):
        q = engine_with_panel.enqueue_item("q1", "p1", "t1", "s1", "rt1")
        with pytest.raises(AttributeError):
            q.queue_id = "changed"

    def test_snapshot_frozen(self, engine: OperatorWorkspaceEngine):
        s = engine.workspace_snapshot("s1", "t1")
        with pytest.raises(AttributeError):
            s.snapshot_id = "changed"

    def test_assessment_frozen(self, engine: OperatorWorkspaceEngine):
        a = engine.workspace_assessment("a1", "t1")
        with pytest.raises(AttributeError):
            a.assessment_id = "changed"

    def test_closure_report_frozen(self, engine: OperatorWorkspaceEngine):
        r = engine.closure_report("r1", "t1")
        with pytest.raises(AttributeError):
            r.report_id = "changed"

    def test_violation_frozen(self, engine: OperatorWorkspaceEngine):
        engine.register_view("v1", "t1", "op1", "V")
        engine.register_panel("p1", "v1", "t1", "P", PanelKind.QUEUE, "rt1")
        viols = engine.detect_workspace_violations("t1")
        with pytest.raises(AttributeError):
            viols[0].violation_id = "changed"


# ===================================================================
# Bulk and stress scenarios
# ===================================================================


class TestBulkScenarios:
    def test_many_views(self, engine: OperatorWorkspaceEngine):
        for i in range(50):
            engine.register_view(f"v{i}", "t1", f"op{i}", f"V{i}")
        assert engine.view_count == 50

    def test_many_panels_per_view(self, engine: OperatorWorkspaceEngine):
        engine.register_view("v1", "t1", "op1", "V")
        for i in range(30):
            engine.register_panel(f"p{i}", "v1", "t1", f"P{i}", PanelKind.QUEUE, "rt")
        v = engine.get_view("v1")
        assert v.panel_count == 30

    def test_many_queue_items(self, engine: OperatorWorkspaceEngine):
        engine.register_view("v1", "t1", "op1", "V")
        engine.register_panel("p1", "v1", "t1", "P", PanelKind.QUEUE, "rt")
        for i in range(100):
            engine.enqueue_item(f"q{i}", "p1", "t1", f"s{i}", "rt", priority=i % 10)
        assert engine.queue_count == 100
        items = engine.queue_items_for_panel("p1")
        assert len(items) == 100

    def test_many_worklist_items(self, engine: OperatorWorkspaceEngine):
        for i in range(50):
            engine.add_worklist_item(f"w{i}", "t1", "op1", f"s{i}", "rt", f"T{i}", i)
        assert engine.worklist_count == 50

    def test_many_actions(self, engine: OperatorWorkspaceEngine):
        for i in range(50):
            engine.record_action(f"a{i}", "t1", "op1", f"tgt{i}", "rt", f"act{i}")
        assert engine.action_count == 50

    def test_many_decisions(self, engine: OperatorWorkspaceEngine):
        for i in range(50):
            engine.record_decision(f"d{i}", "t1", "op1", f"a{i}")
        assert engine.decision_count == 50

    def test_many_tenants(self, engine: OperatorWorkspaceEngine):
        for i in range(20):
            engine.register_view(f"v{i}", f"t{i}", f"op{i}", f"V{i}")
        for i in range(20):
            assert len(engine.views_for_tenant(f"t{i}")) == 1

    def test_concurrent_state_hash(self, engine: OperatorWorkspaceEngine):
        """State hash after multiple operations is deterministic."""
        engine.register_view("v1", "t1", "op1", "V")
        engine.register_panel("p1", "v1", "t1", "P", PanelKind.QUEUE, "rt")
        engine.enqueue_item("q1", "p1", "t1", "s1", "rt", priority=3)
        engine.add_worklist_item("w1", "t1", "op1", "s1", "rt", "T", 5)
        engine.record_action("a1", "t1", "op1", "tgt", "rt", "act")
        h1 = engine.state_hash()
        h2 = engine.state_hash()
        assert h1 == h2


# ===================================================================
# Queue transition matrix
# ===================================================================


class TestQueueTransitionMatrix:
    """Exhaustive queue status transition tests."""

    def test_pending_to_assigned(self, engine_with_queue_item: OperatorWorkspaceEngine):
        q = engine_with_queue_item.assign_queue_item("q1", "a")
        assert q.status == QueueStatus.ASSIGNED

    def test_pending_to_in_progress(self, engine_with_queue_item: OperatorWorkspaceEngine):
        q = engine_with_queue_item.start_queue_item("q1")
        assert q.status == QueueStatus.IN_PROGRESS

    def test_pending_to_completed(self, engine_with_queue_item: OperatorWorkspaceEngine):
        q = engine_with_queue_item.complete_queue_item("q1")
        assert q.status == QueueStatus.COMPLETED

    def test_pending_to_escalated(self, engine_with_queue_item: OperatorWorkspaceEngine):
        q = engine_with_queue_item.escalate_queue_item("q1")
        assert q.status == QueueStatus.ESCALATED

    def test_assigned_to_in_progress(self, engine_with_queue_item: OperatorWorkspaceEngine):
        engine_with_queue_item.assign_queue_item("q1", "a")
        q = engine_with_queue_item.start_queue_item("q1")
        assert q.status == QueueStatus.IN_PROGRESS

    def test_assigned_to_completed(self, engine_with_queue_item: OperatorWorkspaceEngine):
        engine_with_queue_item.assign_queue_item("q1", "a")
        q = engine_with_queue_item.complete_queue_item("q1")
        assert q.status == QueueStatus.COMPLETED

    def test_assigned_to_escalated(self, engine_with_queue_item: OperatorWorkspaceEngine):
        engine_with_queue_item.assign_queue_item("q1", "a")
        q = engine_with_queue_item.escalate_queue_item("q1")
        assert q.status == QueueStatus.ESCALATED

    def test_in_progress_to_completed(self, engine_with_queue_item: OperatorWorkspaceEngine):
        engine_with_queue_item.start_queue_item("q1")
        q = engine_with_queue_item.complete_queue_item("q1")
        assert q.status == QueueStatus.COMPLETED

    def test_in_progress_to_escalated(self, engine_with_queue_item: OperatorWorkspaceEngine):
        engine_with_queue_item.start_queue_item("q1")
        q = engine_with_queue_item.escalate_queue_item("q1")
        assert q.status == QueueStatus.ESCALATED

    def test_escalated_to_completed(self, engine_with_queue_item: OperatorWorkspaceEngine):
        engine_with_queue_item.escalate_queue_item("q1")
        q = engine_with_queue_item.complete_queue_item("q1")
        assert q.status == QueueStatus.COMPLETED

    def test_completed_to_assigned_raises(self, engine_with_queue_item: OperatorWorkspaceEngine):
        engine_with_queue_item.complete_queue_item("q1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine_with_queue_item.assign_queue_item("q1", "a")

    def test_completed_to_in_progress_raises(self, engine_with_queue_item: OperatorWorkspaceEngine):
        engine_with_queue_item.complete_queue_item("q1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine_with_queue_item.start_queue_item("q1")

    def test_completed_to_escalated_raises(self, engine_with_queue_item: OperatorWorkspaceEngine):
        engine_with_queue_item.complete_queue_item("q1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine_with_queue_item.escalate_queue_item("q1")

    def test_completed_to_completed_raises(self, engine_with_queue_item: OperatorWorkspaceEngine):
        engine_with_queue_item.complete_queue_item("q1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine_with_queue_item.complete_queue_item("q1")


# ===================================================================
# Action terminal state matrix
# ===================================================================


class TestActionTerminalMatrix:
    """All terminal action states block further transitions."""

    def test_completed_blocks_complete(self, engine: OperatorWorkspaceEngine):
        engine.record_action("a1", "t1", "op1", "tgt", "rt", "act")
        engine.complete_action("a1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.complete_action("a1")

    def test_completed_blocks_fail(self, engine: OperatorWorkspaceEngine):
        engine.record_action("a1", "t1", "op1", "tgt", "rt", "act")
        engine.complete_action("a1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.fail_action("a1")

    def test_failed_blocks_complete(self, engine: OperatorWorkspaceEngine):
        engine.record_action("a1", "t1", "op1", "tgt", "rt", "act")
        engine.fail_action("a1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.complete_action("a1")

    def test_failed_blocks_fail(self, engine: OperatorWorkspaceEngine):
        engine.record_action("a1", "t1", "op1", "tgt", "rt", "act")
        engine.fail_action("a1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.fail_action("a1")
