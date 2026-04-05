"""Tests for OperatorWorkspaceIntegration bridge.

Covers constructor validation, all 7 workspace methods, memory mesh attachment,
graph attachment, event emission, return-shape invariants, and golden-path
lifecycle scenarios.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine
from mcoi_runtime.core.operator_workspace import OperatorWorkspaceEngine
from mcoi_runtime.core.operator_workspace_integration import OperatorWorkspaceIntegration
from mcoi_runtime.contracts.memory_mesh import MemoryRecord


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def event_spine() -> EventSpineEngine:
    return EventSpineEngine()


@pytest.fixture()
def workspace_engine(event_spine: EventSpineEngine) -> OperatorWorkspaceEngine:
    return OperatorWorkspaceEngine(event_spine)


@pytest.fixture()
def memory_engine() -> MemoryMeshEngine:
    return MemoryMeshEngine()


@pytest.fixture()
def integration(
    workspace_engine: OperatorWorkspaceEngine,
    event_spine: EventSpineEngine,
    memory_engine: MemoryMeshEngine,
) -> OperatorWorkspaceIntegration:
    return OperatorWorkspaceIntegration(workspace_engine, event_spine, memory_engine)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

WORKSPACE_KEYS = frozenset(
    {"view_id", "panel_id", "tenant_id", "operator_ref", "panel_kind",
     "target_runtime", "source_type"}
)

GRAPH_KEYS = frozenset(
    {"scope_ref_id", "total_views", "active_views", "total_panels",
     "total_queue_items", "pending_queue_items", "total_worklist_items",
     "total_actions"}
)

MEMORY_CONTENT_KEYS = frozenset(
    {"total_views", "active_views", "total_panels",
     "total_queue_items", "pending_queue_items", "total_worklist_items",
     "total_actions"}
)

MEMORY_TAGS = ("operator_workspace", "ui", "queues")


def _uid(prefix: str, n: int = 1) -> str:
    return f"{prefix}-{n}"


# ---------------------------------------------------------------------------
# Constructor validation
# ---------------------------------------------------------------------------


class TestConstructorValidation:
    """Constructor must reject wrong types for all three dependencies."""

    def test_reject_none_workspace_engine(
        self, event_spine: EventSpineEngine, memory_engine: MemoryMeshEngine,
    ) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            OperatorWorkspaceIntegration(None, event_spine, memory_engine)  # type: ignore[arg-type]

    def test_reject_string_workspace_engine(
        self, event_spine: EventSpineEngine, memory_engine: MemoryMeshEngine,
    ) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            OperatorWorkspaceIntegration("bad", event_spine, memory_engine)  # type: ignore[arg-type]

    def test_reject_none_event_spine(
        self, workspace_engine: OperatorWorkspaceEngine, memory_engine: MemoryMeshEngine,
    ) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            OperatorWorkspaceIntegration(workspace_engine, None, memory_engine)  # type: ignore[arg-type]

    def test_reject_int_event_spine(
        self, workspace_engine: OperatorWorkspaceEngine, memory_engine: MemoryMeshEngine,
    ) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            OperatorWorkspaceIntegration(workspace_engine, 42, memory_engine)  # type: ignore[arg-type]

    def test_reject_none_memory_engine(
        self, workspace_engine: OperatorWorkspaceEngine, event_spine: EventSpineEngine,
    ) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            OperatorWorkspaceIntegration(workspace_engine, event_spine, None)  # type: ignore[arg-type]

    def test_reject_dict_memory_engine(
        self, workspace_engine: OperatorWorkspaceEngine, event_spine: EventSpineEngine,
    ) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            OperatorWorkspaceIntegration(workspace_engine, event_spine, {})  # type: ignore[arg-type]

    def test_valid_construction(
        self,
        workspace_engine: OperatorWorkspaceEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        bridge = OperatorWorkspaceIntegration(workspace_engine, event_spine, memory_engine)
        assert bridge is not None


# ---------------------------------------------------------------------------
# workspace_from_service_requests
# ---------------------------------------------------------------------------


class TestWorkspaceFromServiceRequests:

    def test_returns_dict_with_correct_keys(
        self, integration: OperatorWorkspaceIntegration,
    ) -> None:
        result = integration.workspace_from_service_requests(
            "v1", "p1", "t1", "op1",
        )
        assert set(result.keys()) == WORKSPACE_KEYS

    def test_panel_kind_is_queue(self, integration: OperatorWorkspaceIntegration) -> None:
        result = integration.workspace_from_service_requests("v1", "p1", "t1", "op1")
        assert result["panel_kind"] == "queue"

    def test_target_runtime_is_service_catalog(self, integration: OperatorWorkspaceIntegration) -> None:
        result = integration.workspace_from_service_requests("v1", "p1", "t1", "op1")
        assert result["target_runtime"] == "service_catalog"

    def test_source_type_is_service_requests(self, integration: OperatorWorkspaceIntegration) -> None:
        result = integration.workspace_from_service_requests("v1", "p1", "t1", "op1")
        assert result["source_type"] == "service_requests"

    def test_echoes_back_ids(self, integration: OperatorWorkspaceIntegration) -> None:
        result = integration.workspace_from_service_requests("v1", "p1", "t1", "op1")
        assert result["view_id"] == "v1"
        assert result["panel_id"] == "p1"
        assert result["tenant_id"] == "t1"
        assert result["operator_ref"] == "op1"

    def test_increments_view_and_panel_counts(
        self,
        integration: OperatorWorkspaceIntegration,
        workspace_engine: OperatorWorkspaceEngine,
    ) -> None:
        v0, p0 = workspace_engine.view_count, workspace_engine.panel_count
        integration.workspace_from_service_requests("v1", "p1", "t1", "op1")
        assert workspace_engine.view_count == v0 + 1
        assert workspace_engine.panel_count == p0 + 1

    def test_emits_event(
        self,
        integration: OperatorWorkspaceIntegration,
        event_spine: EventSpineEngine,
    ) -> None:
        before = event_spine.event_count
        integration.workspace_from_service_requests("v1", "p1", "t1", "op1")
        assert event_spine.event_count > before


# ---------------------------------------------------------------------------
# workspace_from_case_reviews
# ---------------------------------------------------------------------------


class TestWorkspaceFromCaseReviews:

    def test_returns_dict_with_correct_keys(self, integration: OperatorWorkspaceIntegration) -> None:
        result = integration.workspace_from_case_reviews("v1", "p1", "t1", "op1")
        assert set(result.keys()) == WORKSPACE_KEYS

    def test_panel_kind_is_investigation(self, integration: OperatorWorkspaceIntegration) -> None:
        result = integration.workspace_from_case_reviews("v1", "p1", "t1", "op1")
        assert result["panel_kind"] == "investigation"

    def test_target_runtime_is_case(self, integration: OperatorWorkspaceIntegration) -> None:
        result = integration.workspace_from_case_reviews("v1", "p1", "t1", "op1")
        assert result["target_runtime"] == "case"

    def test_source_type_is_case_reviews(self, integration: OperatorWorkspaceIntegration) -> None:
        result = integration.workspace_from_case_reviews("v1", "p1", "t1", "op1")
        assert result["source_type"] == "case_reviews"

    def test_echoes_back_ids(self, integration: OperatorWorkspaceIntegration) -> None:
        result = integration.workspace_from_case_reviews("v1", "p1", "t1", "op1")
        assert result["view_id"] == "v1"
        assert result["panel_id"] == "p1"
        assert result["tenant_id"] == "t1"
        assert result["operator_ref"] == "op1"

    def test_increments_counts(
        self,
        integration: OperatorWorkspaceIntegration,
        workspace_engine: OperatorWorkspaceEngine,
    ) -> None:
        v0, p0 = workspace_engine.view_count, workspace_engine.panel_count
        integration.workspace_from_case_reviews("v1", "p1", "t1", "op1")
        assert workspace_engine.view_count == v0 + 1
        assert workspace_engine.panel_count == p0 + 1

    def test_emits_event(
        self,
        integration: OperatorWorkspaceIntegration,
        event_spine: EventSpineEngine,
    ) -> None:
        before = event_spine.event_count
        integration.workspace_from_case_reviews("v1", "p1", "t1", "op1")
        assert event_spine.event_count > before


# ---------------------------------------------------------------------------
# workspace_from_remediations
# ---------------------------------------------------------------------------


class TestWorkspaceFromRemediations:

    def test_returns_dict_with_correct_keys(self, integration: OperatorWorkspaceIntegration) -> None:
        result = integration.workspace_from_remediations("v1", "p1", "t1", "op1")
        assert set(result.keys()) == WORKSPACE_KEYS

    def test_panel_kind_is_queue(self, integration: OperatorWorkspaceIntegration) -> None:
        result = integration.workspace_from_remediations("v1", "p1", "t1", "op1")
        assert result["panel_kind"] == "queue"

    def test_target_runtime_is_remediation(self, integration: OperatorWorkspaceIntegration) -> None:
        result = integration.workspace_from_remediations("v1", "p1", "t1", "op1")
        assert result["target_runtime"] == "remediation"

    def test_source_type_is_remediations(self, integration: OperatorWorkspaceIntegration) -> None:
        result = integration.workspace_from_remediations("v1", "p1", "t1", "op1")
        assert result["source_type"] == "remediations"

    def test_echoes_back_ids(self, integration: OperatorWorkspaceIntegration) -> None:
        result = integration.workspace_from_remediations("v1", "p1", "t1", "op1")
        assert result["view_id"] == "v1"
        assert result["panel_id"] == "p1"

    def test_increments_counts(
        self,
        integration: OperatorWorkspaceIntegration,
        workspace_engine: OperatorWorkspaceEngine,
    ) -> None:
        v0, p0 = workspace_engine.view_count, workspace_engine.panel_count
        integration.workspace_from_remediations("v1", "p1", "t1", "op1")
        assert workspace_engine.view_count == v0 + 1
        assert workspace_engine.panel_count == p0 + 1

    def test_emits_event(
        self,
        integration: OperatorWorkspaceIntegration,
        event_spine: EventSpineEngine,
    ) -> None:
        before = event_spine.event_count
        integration.workspace_from_remediations("v1", "p1", "t1", "op1")
        assert event_spine.event_count > before


# ---------------------------------------------------------------------------
# workspace_from_reporting
# ---------------------------------------------------------------------------


class TestWorkspaceFromReporting:

    def test_returns_dict_with_correct_keys(self, integration: OperatorWorkspaceIntegration) -> None:
        result = integration.workspace_from_reporting("v1", "p1", "t1", "op1")
        assert set(result.keys()) == WORKSPACE_KEYS

    def test_panel_kind_is_dashboard(self, integration: OperatorWorkspaceIntegration) -> None:
        result = integration.workspace_from_reporting("v1", "p1", "t1", "op1")
        assert result["panel_kind"] == "dashboard"

    def test_target_runtime_is_reporting(self, integration: OperatorWorkspaceIntegration) -> None:
        result = integration.workspace_from_reporting("v1", "p1", "t1", "op1")
        assert result["target_runtime"] == "reporting"

    def test_source_type_is_reporting(self, integration: OperatorWorkspaceIntegration) -> None:
        result = integration.workspace_from_reporting("v1", "p1", "t1", "op1")
        assert result["source_type"] == "reporting"

    def test_echoes_back_ids(self, integration: OperatorWorkspaceIntegration) -> None:
        result = integration.workspace_from_reporting("v1", "p1", "t1", "op1")
        assert result["view_id"] == "v1"
        assert result["panel_id"] == "p1"
        assert result["tenant_id"] == "t1"
        assert result["operator_ref"] == "op1"

    def test_increments_counts(
        self,
        integration: OperatorWorkspaceIntegration,
        workspace_engine: OperatorWorkspaceEngine,
    ) -> None:
        v0, p0 = workspace_engine.view_count, workspace_engine.panel_count
        integration.workspace_from_reporting("v1", "p1", "t1", "op1")
        assert workspace_engine.view_count == v0 + 1
        assert workspace_engine.panel_count == p0 + 1

    def test_emits_event(
        self,
        integration: OperatorWorkspaceIntegration,
        event_spine: EventSpineEngine,
    ) -> None:
        before = event_spine.event_count
        integration.workspace_from_reporting("v1", "p1", "t1", "op1")
        assert event_spine.event_count > before


# ---------------------------------------------------------------------------
# workspace_from_settlement
# ---------------------------------------------------------------------------


class TestWorkspaceFromSettlement:

    def test_returns_dict_with_correct_keys(self, integration: OperatorWorkspaceIntegration) -> None:
        result = integration.workspace_from_settlement("v1", "p1", "t1", "op1")
        assert set(result.keys()) == WORKSPACE_KEYS

    def test_panel_kind_is_review(self, integration: OperatorWorkspaceIntegration) -> None:
        result = integration.workspace_from_settlement("v1", "p1", "t1", "op1")
        assert result["panel_kind"] == "review"

    def test_target_runtime_is_settlement(self, integration: OperatorWorkspaceIntegration) -> None:
        result = integration.workspace_from_settlement("v1", "p1", "t1", "op1")
        assert result["target_runtime"] == "settlement"

    def test_source_type_is_settlement(self, integration: OperatorWorkspaceIntegration) -> None:
        result = integration.workspace_from_settlement("v1", "p1", "t1", "op1")
        assert result["source_type"] == "settlement"

    def test_echoes_back_ids(self, integration: OperatorWorkspaceIntegration) -> None:
        result = integration.workspace_from_settlement("v1", "p1", "t1", "op1")
        assert result["view_id"] == "v1"
        assert result["panel_id"] == "p1"
        assert result["tenant_id"] == "t1"
        assert result["operator_ref"] == "op1"

    def test_increments_counts(
        self,
        integration: OperatorWorkspaceIntegration,
        workspace_engine: OperatorWorkspaceEngine,
    ) -> None:
        v0, p0 = workspace_engine.view_count, workspace_engine.panel_count
        integration.workspace_from_settlement("v1", "p1", "t1", "op1")
        assert workspace_engine.view_count == v0 + 1
        assert workspace_engine.panel_count == p0 + 1

    def test_emits_event(
        self,
        integration: OperatorWorkspaceIntegration,
        event_spine: EventSpineEngine,
    ) -> None:
        before = event_spine.event_count
        integration.workspace_from_settlement("v1", "p1", "t1", "op1")
        assert event_spine.event_count > before


# ---------------------------------------------------------------------------
# workspace_from_continuity
# ---------------------------------------------------------------------------


class TestWorkspaceFromContinuity:

    def test_returns_dict_with_correct_keys(self, integration: OperatorWorkspaceIntegration) -> None:
        result = integration.workspace_from_continuity("v1", "p1", "t1", "op1")
        assert set(result.keys()) == WORKSPACE_KEYS

    def test_panel_kind_is_queue(self, integration: OperatorWorkspaceIntegration) -> None:
        result = integration.workspace_from_continuity("v1", "p1", "t1", "op1")
        assert result["panel_kind"] == "queue"

    def test_target_runtime_is_continuity(self, integration: OperatorWorkspaceIntegration) -> None:
        result = integration.workspace_from_continuity("v1", "p1", "t1", "op1")
        assert result["target_runtime"] == "continuity"

    def test_source_type_is_continuity(self, integration: OperatorWorkspaceIntegration) -> None:
        result = integration.workspace_from_continuity("v1", "p1", "t1", "op1")
        assert result["source_type"] == "continuity"

    def test_echoes_back_ids(self, integration: OperatorWorkspaceIntegration) -> None:
        result = integration.workspace_from_continuity("v1", "p1", "t1", "op1")
        assert result["view_id"] == "v1"
        assert result["panel_id"] == "p1"
        assert result["tenant_id"] == "t1"
        assert result["operator_ref"] == "op1"

    def test_increments_counts(
        self,
        integration: OperatorWorkspaceIntegration,
        workspace_engine: OperatorWorkspaceEngine,
    ) -> None:
        v0, p0 = workspace_engine.view_count, workspace_engine.panel_count
        integration.workspace_from_continuity("v1", "p1", "t1", "op1")
        assert workspace_engine.view_count == v0 + 1
        assert workspace_engine.panel_count == p0 + 1

    def test_emits_event(
        self,
        integration: OperatorWorkspaceIntegration,
        event_spine: EventSpineEngine,
    ) -> None:
        before = event_spine.event_count
        integration.workspace_from_continuity("v1", "p1", "t1", "op1")
        assert event_spine.event_count > before


# ---------------------------------------------------------------------------
# workspace_from_executive_control
# ---------------------------------------------------------------------------


class TestWorkspaceFromExecutiveControl:

    def test_returns_dict_with_correct_keys(self, integration: OperatorWorkspaceIntegration) -> None:
        result = integration.workspace_from_executive_control("v1", "p1", "t1", "op1")
        assert set(result.keys()) == WORKSPACE_KEYS

    def test_panel_kind_is_approval(self, integration: OperatorWorkspaceIntegration) -> None:
        result = integration.workspace_from_executive_control("v1", "p1", "t1", "op1")
        assert result["panel_kind"] == "approval"

    def test_target_runtime_is_executive_control(self, integration: OperatorWorkspaceIntegration) -> None:
        result = integration.workspace_from_executive_control("v1", "p1", "t1", "op1")
        assert result["target_runtime"] == "executive_control"

    def test_source_type_is_executive_control(self, integration: OperatorWorkspaceIntegration) -> None:
        result = integration.workspace_from_executive_control("v1", "p1", "t1", "op1")
        assert result["source_type"] == "executive_control"

    def test_echoes_back_ids(self, integration: OperatorWorkspaceIntegration) -> None:
        result = integration.workspace_from_executive_control("v1", "p1", "t1", "op1")
        assert result["view_id"] == "v1"
        assert result["panel_id"] == "p1"
        assert result["tenant_id"] == "t1"
        assert result["operator_ref"] == "op1"

    def test_increments_counts(
        self,
        integration: OperatorWorkspaceIntegration,
        workspace_engine: OperatorWorkspaceEngine,
    ) -> None:
        v0, p0 = workspace_engine.view_count, workspace_engine.panel_count
        integration.workspace_from_executive_control("v1", "p1", "t1", "op1")
        assert workspace_engine.view_count == v0 + 1
        assert workspace_engine.panel_count == p0 + 1

    def test_emits_event(
        self,
        integration: OperatorWorkspaceIntegration,
        event_spine: EventSpineEngine,
    ) -> None:
        before = event_spine.event_count
        integration.workspace_from_executive_control("v1", "p1", "t1", "op1")
        assert event_spine.event_count > before


# ---------------------------------------------------------------------------
# attach_workspace_state_to_memory_mesh
# ---------------------------------------------------------------------------


class TestAttachWorkspaceStateToMemoryMesh:

    def test_returns_memory_record(self, integration: OperatorWorkspaceIntegration) -> None:
        mem = integration.attach_workspace_state_to_memory_mesh("scope-1")
        assert isinstance(mem, MemoryRecord)

    def test_memory_has_correct_tags(self, integration: OperatorWorkspaceIntegration) -> None:
        mem = integration.attach_workspace_state_to_memory_mesh("scope-1")
        assert set(mem.tags) == set(MEMORY_TAGS)

    def test_memory_content_has_7_keys(self, integration: OperatorWorkspaceIntegration) -> None:
        mem = integration.attach_workspace_state_to_memory_mesh("scope-1")
        assert set(mem.content.keys()) == MEMORY_CONTENT_KEYS

    def test_memory_scope_ref_id_matches(self, integration: OperatorWorkspaceIntegration) -> None:
        mem = integration.attach_workspace_state_to_memory_mesh("scope-1")
        assert mem.scope_ref_id == "scope-1"

    def test_memory_title_is_bounded(self, integration: OperatorWorkspaceIntegration) -> None:
        mem = integration.attach_workspace_state_to_memory_mesh("scope-1")
        assert mem.title == "Operator workspace state"
        assert "scope-1" not in mem.title
        assert mem.scope_ref_id == "scope-1"

    def test_memory_added_to_engine(
        self,
        integration: OperatorWorkspaceIntegration,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        before = memory_engine.memory_count
        integration.attach_workspace_state_to_memory_mesh("scope-1")
        assert memory_engine.memory_count == before + 1

    def test_emits_event(
        self,
        integration: OperatorWorkspaceIntegration,
        event_spine: EventSpineEngine,
    ) -> None:
        before = event_spine.event_count
        integration.attach_workspace_state_to_memory_mesh("scope-1")
        assert event_spine.event_count > before

    def test_content_values_are_ints(self, integration: OperatorWorkspaceIntegration) -> None:
        mem = integration.attach_workspace_state_to_memory_mesh("scope-1")
        for key in MEMORY_CONTENT_KEYS:
            assert isinstance(mem.content[key], int)

    def test_empty_workspace_zeros(self, integration: OperatorWorkspaceIntegration) -> None:
        mem = integration.attach_workspace_state_to_memory_mesh("scope-1")
        assert mem.content["total_views"] == 0
        assert mem.content["total_panels"] == 0

    def test_after_creating_workspace_views_nonzero(
        self, integration: OperatorWorkspaceIntegration,
    ) -> None:
        integration.workspace_from_service_requests("v1", "p1", "tenant-x", "op1")
        mem = integration.attach_workspace_state_to_memory_mesh("tenant-x")
        assert mem.content["total_views"] == 1
        assert mem.content["active_views"] == 1
        assert mem.content["total_panels"] == 1


# ---------------------------------------------------------------------------
# attach_workspace_state_to_graph
# ---------------------------------------------------------------------------


class TestAttachWorkspaceStateToGraph:

    def test_returns_dict(self, integration: OperatorWorkspaceIntegration) -> None:
        result = integration.attach_workspace_state_to_graph("scope-1")
        assert isinstance(result, dict)

    def test_has_8_keys(self, integration: OperatorWorkspaceIntegration) -> None:
        result = integration.attach_workspace_state_to_graph("scope-1")
        assert set(result.keys()) == GRAPH_KEYS

    def test_scope_ref_id_matches(self, integration: OperatorWorkspaceIntegration) -> None:
        result = integration.attach_workspace_state_to_graph("scope-1")
        assert result["scope_ref_id"] == "scope-1"

    def test_empty_workspace_zeros(self, integration: OperatorWorkspaceIntegration) -> None:
        result = integration.attach_workspace_state_to_graph("scope-1")
        assert result["total_views"] == 0
        assert result["total_panels"] == 0
        assert result["total_queue_items"] == 0

    def test_after_workspace_creation(
        self, integration: OperatorWorkspaceIntegration,
    ) -> None:
        integration.workspace_from_reporting("v1", "p1", "tenant-y", "op1")
        result = integration.attach_workspace_state_to_graph("tenant-y")
        assert result["total_views"] == 1
        assert result["active_views"] == 1
        assert result["total_panels"] == 1

    def test_values_are_ints(self, integration: OperatorWorkspaceIntegration) -> None:
        result = integration.attach_workspace_state_to_graph("scope-1")
        for key in GRAPH_KEYS - {"scope_ref_id"}:
            assert isinstance(result[key], int)


# ---------------------------------------------------------------------------
# Cross-method event counting
# ---------------------------------------------------------------------------


class TestEventEmission:

    def test_each_workspace_method_emits_events(
        self, integration: OperatorWorkspaceIntegration, event_spine: EventSpineEngine,
    ) -> None:
        """Each workspace method registers a view + panel (2 engine events) plus
        1 integration event.  We check total event_count grows by at least 1
        per call."""
        counts = []
        methods = [
            ("workspace_from_service_requests", ("v1", "p1", "t1", "op1")),
            ("workspace_from_case_reviews", ("v2", "p2", "t1", "op1")),
            ("workspace_from_remediations", ("v3", "p3", "t1", "op1")),
            ("workspace_from_reporting", ("v4", "p4", "t1", "op1")),
            ("workspace_from_settlement", ("v5", "p5", "t1", "op1")),
            ("workspace_from_continuity", ("v6", "p6", "t1", "op1")),
            ("workspace_from_executive_control", ("v7", "p7", "t1", "op1")),
        ]
        for method_name, args in methods:
            before = event_spine.event_count
            getattr(integration, method_name)(*args)
            counts.append(event_spine.event_count - before)
        assert all(c >= 1 for c in counts)

    def test_memory_attachment_emits_event(
        self, integration: OperatorWorkspaceIntegration, event_spine: EventSpineEngine,
    ) -> None:
        before = event_spine.event_count
        integration.attach_workspace_state_to_memory_mesh("scope-1")
        # snapshot emits 1 event in workspace engine + 1 in integration
        assert event_spine.event_count > before


# ---------------------------------------------------------------------------
# Duplicate ID rejection (via underlying engine)
# ---------------------------------------------------------------------------


class TestDuplicateIdRejection:

    def test_duplicate_view_id_raises(
        self, integration: OperatorWorkspaceIntegration,
    ) -> None:
        integration.workspace_from_service_requests("v1", "p1", "t1", "op1")
        with pytest.raises(RuntimeCoreInvariantError):
            integration.workspace_from_case_reviews("v1", "p2", "t1", "op1")

    def test_duplicate_panel_id_raises(
        self, integration: OperatorWorkspaceIntegration,
    ) -> None:
        integration.workspace_from_service_requests("v1", "p1", "t1", "op1")
        with pytest.raises(RuntimeCoreInvariantError):
            integration.workspace_from_remediations("v2", "p1", "t1", "op1")


# ---------------------------------------------------------------------------
# Golden-path lifecycle
# ---------------------------------------------------------------------------


class TestGoldenPathLifecycle:

    def test_create_all_seven_then_snapshot(
        self,
        integration: OperatorWorkspaceIntegration,
        workspace_engine: OperatorWorkspaceEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        """Create all 7 workspace types, then attach to memory and graph."""
        integration.workspace_from_service_requests("v1", "p1", "t1", "op1")
        integration.workspace_from_case_reviews("v2", "p2", "t1", "op1")
        integration.workspace_from_remediations("v3", "p3", "t1", "op1")
        integration.workspace_from_reporting("v4", "p4", "t1", "op1")
        integration.workspace_from_settlement("v5", "p5", "t1", "op1")
        integration.workspace_from_continuity("v6", "p6", "t1", "op1")
        integration.workspace_from_executive_control("v7", "p7", "t1", "op1")

        assert workspace_engine.view_count == 7
        assert workspace_engine.panel_count == 7

        mem = integration.attach_workspace_state_to_memory_mesh("t1")
        assert mem.content["total_views"] == 7
        assert mem.content["active_views"] == 7
        assert mem.content["total_panels"] == 7

        graph = integration.attach_workspace_state_to_graph("t1")
        assert graph["total_views"] == 7
        assert graph["total_panels"] == 7

        assert memory_engine.memory_count == 1
        assert event_spine.event_count > 0

    def test_multi_tenant_isolation(
        self, integration: OperatorWorkspaceIntegration,
    ) -> None:
        """Workspaces from different tenants stay isolated in snapshots."""
        integration.workspace_from_service_requests("v-a1", "p-a1", "tenant-a", "op1")
        integration.workspace_from_case_reviews("v-b1", "p-b1", "tenant-b", "op2")

        graph_a = integration.attach_workspace_state_to_graph("tenant-a")
        graph_b = integration.attach_workspace_state_to_graph("tenant-b")
        assert graph_a["total_views"] == 1
        assert graph_b["total_views"] == 1

    def test_graph_and_memory_agree(
        self, integration: OperatorWorkspaceIntegration,
    ) -> None:
        """Memory mesh content and graph dict should report same counts."""
        integration.workspace_from_reporting("v1", "p1", "t1", "op1")
        integration.workspace_from_settlement("v2", "p2", "t1", "op1")

        mem = integration.attach_workspace_state_to_memory_mesh("t1")
        graph = integration.attach_workspace_state_to_graph("t1")

        for key in MEMORY_CONTENT_KEYS:
            assert mem.content[key] == graph[key], f"mismatch on {key}"
