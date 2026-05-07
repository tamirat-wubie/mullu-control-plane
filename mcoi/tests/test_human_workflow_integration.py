"""Tests for HumanWorkflowIntegration bridge.

Covers constructor validation, all 6 workflow-creation methods,
memory mesh attachment, graph attachment, event emission, and
duplicate-ID guards.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.human_workflow_integration import HumanWorkflowIntegration
from mcoi_runtime.core.human_workflow import HumanWorkflowEngine
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.contracts.memory_mesh import MemoryRecord


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def event_spine() -> EventSpineEngine:
    return EventSpineEngine()


@pytest.fixture()
def workflow_engine(event_spine: EventSpineEngine) -> HumanWorkflowEngine:
    return HumanWorkflowEngine(event_spine)


@pytest.fixture()
def memory_engine() -> MemoryMeshEngine:
    return MemoryMeshEngine()


@pytest.fixture()
def integration(
    workflow_engine: HumanWorkflowEngine,
    event_spine: EventSpineEngine,
    memory_engine: MemoryMeshEngine,
) -> HumanWorkflowIntegration:
    return HumanWorkflowIntegration(workflow_engine, event_spine, memory_engine)


# ---------------------------------------------------------------------------
# Constructor validation
# ---------------------------------------------------------------------------


class TestConstructorValidation:
    """isinstance guards on all three constructor arguments."""

    def test_invalid_workflow_engine(
        self, event_spine: EventSpineEngine, memory_engine: MemoryMeshEngine
    ) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="workflow_engine"):
            HumanWorkflowIntegration("not-an-engine", event_spine, memory_engine)

    def test_invalid_event_spine(
        self, workflow_engine: HumanWorkflowEngine, memory_engine: MemoryMeshEngine
    ) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="event_spine"):
            HumanWorkflowIntegration(workflow_engine, "not-a-spine", memory_engine)

    def test_invalid_memory_engine(
        self, workflow_engine: HumanWorkflowEngine, event_spine: EventSpineEngine
    ) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="memory_engine"):
            HumanWorkflowIntegration(workflow_engine, event_spine, "not-a-mesh")


# ---------------------------------------------------------------------------
# workflow_from_change_request
# ---------------------------------------------------------------------------


class TestWorkflowFromChangeRequest:
    def test_returns_dict(self, integration: HumanWorkflowIntegration) -> None:
        result = integration.workflow_from_change_request("b1", "t1", "cr-001")
        assert isinstance(result, dict)

    def test_correct_source_type(self, integration: HumanWorkflowIntegration) -> None:
        result = integration.workflow_from_change_request("b2", "t1", "cr-002")
        assert result["source_type"] == "change_request"

    def test_correct_scope(self, integration: HumanWorkflowIntegration) -> None:
        result = integration.workflow_from_change_request("b3", "t1", "cr-003")
        assert result["scope"] == "change"

    def test_board_id_in_result(self, integration: HumanWorkflowIntegration) -> None:
        result = integration.workflow_from_change_request("b4", "t1", "cr-004")
        assert result["board_id"] == "b4"

    def test_tenant_id_in_result(self, integration: HumanWorkflowIntegration) -> None:
        result = integration.workflow_from_change_request("b5", "t1", "cr-005")
        assert result["tenant_id"] == "t1"

    def test_change_ref_in_result(self, integration: HumanWorkflowIntegration) -> None:
        result = integration.workflow_from_change_request("b6", "t1", "cr-006")
        assert result["change_ref"] == "cr-006"

    def test_creates_board_in_engine(
        self,
        integration: HumanWorkflowIntegration,
        workflow_engine: HumanWorkflowEngine,
    ) -> None:
        integration.workflow_from_change_request("b7", "t1", "cr-007")
        board = workflow_engine.get_board("b7")
        assert board.scope_ref_id == "cr-007"
        assert board.name == "Change approval"
        assert "cr-007" not in board.name

    def test_emits_event(
        self,
        integration: HumanWorkflowIntegration,
        event_spine: EventSpineEngine,
    ) -> None:
        before = event_spine.event_count
        integration.workflow_from_change_request("b8", "t1", "cr-008")
        assert event_spine.event_count > before

    def test_duplicate_board_id_raises(
        self, integration: HumanWorkflowIntegration
    ) -> None:
        integration.workflow_from_change_request("dup-b", "t1", "cr-dup")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate board_id"):
            integration.workflow_from_change_request("dup-b", "t1", "cr-dup2")

    def test_approval_mode_default(self, integration: HumanWorkflowIntegration) -> None:
        result = integration.workflow_from_change_request("b9", "t1", "cr-009")
        assert result["approval_mode"] == "quorum"


# ---------------------------------------------------------------------------
# workflow_from_case_review
# ---------------------------------------------------------------------------


class TestWorkflowFromCaseReview:
    def test_returns_dict(self, integration: HumanWorkflowIntegration) -> None:
        result = integration.workflow_from_case_review("p1", "t1", "case-001")
        assert isinstance(result, dict)

    def test_correct_source_type(self, integration: HumanWorkflowIntegration) -> None:
        result = integration.workflow_from_case_review("p2", "t1", "case-002")
        assert result["source_type"] == "case_review"

    def test_correct_scope(self, integration: HumanWorkflowIntegration) -> None:
        result = integration.workflow_from_case_review("p3", "t1", "case-003")
        assert result["scope"] == "case"

    def test_review_mode_default(self, integration: HumanWorkflowIntegration) -> None:
        result = integration.workflow_from_case_review("p4", "t1", "case-004")
        assert result["review_mode"] == "parallel"

    def test_creates_review_packet_in_engine(
        self,
        integration: HumanWorkflowIntegration,
        workflow_engine: HumanWorkflowEngine,
    ) -> None:
        integration.workflow_from_case_review("p5", "t1", "case-005")
        packet = workflow_engine.get_review_packet("p5")
        assert packet.scope_ref_id == "case-005"
        assert packet.title == "Case review"
        assert "case-005" not in packet.title

    def test_emits_event(
        self,
        integration: HumanWorkflowIntegration,
        event_spine: EventSpineEngine,
    ) -> None:
        before = event_spine.event_count
        integration.workflow_from_case_review("p6", "t1", "case-006")
        assert event_spine.event_count > before

    def test_duplicate_packet_id_raises(
        self, integration: HumanWorkflowIntegration
    ) -> None:
        integration.workflow_from_case_review("dup-p", "t1", "case-dup")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate packet_id"):
            integration.workflow_from_case_review("dup-p", "t1", "case-dup2")


# ---------------------------------------------------------------------------
# workflow_from_regulatory_submission
# ---------------------------------------------------------------------------


class TestWorkflowFromRegulatorySubmission:
    def test_returns_dict(self, integration: HumanWorkflowIntegration) -> None:
        result = integration.workflow_from_regulatory_submission("r1", "t1", "reg-001")
        assert isinstance(result, dict)

    def test_correct_source_type(self, integration: HumanWorkflowIntegration) -> None:
        result = integration.workflow_from_regulatory_submission("r2", "t1", "reg-002")
        assert result["source_type"] == "regulatory_submission"

    def test_correct_scope(self, integration: HumanWorkflowIntegration) -> None:
        result = integration.workflow_from_regulatory_submission("r3", "t1", "reg-003")
        assert result["scope"] == "regulatory"

    def test_review_mode_default(self, integration: HumanWorkflowIntegration) -> None:
        result = integration.workflow_from_regulatory_submission("r4", "t1", "reg-004")
        assert result["review_mode"] == "sequential"

    def test_creates_review_packet_in_engine(
        self,
        integration: HumanWorkflowIntegration,
        workflow_engine: HumanWorkflowEngine,
    ) -> None:
        integration.workflow_from_regulatory_submission("r5", "t1", "reg-005")
        packet = workflow_engine.get_review_packet("r5")
        assert packet.scope_ref_id == "reg-005"
        assert packet.title == "Regulatory review"
        assert "reg-005" not in packet.title

    def test_emits_event(
        self,
        integration: HumanWorkflowIntegration,
        event_spine: EventSpineEngine,
    ) -> None:
        before = event_spine.event_count
        integration.workflow_from_regulatory_submission("r6", "t1", "reg-006")
        assert event_spine.event_count > before

    def test_duplicate_packet_id_raises(
        self, integration: HumanWorkflowIntegration
    ) -> None:
        integration.workflow_from_regulatory_submission("dup-r", "t1", "reg-dup")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate packet_id"):
            integration.workflow_from_regulatory_submission("dup-r", "t1", "reg-dup2")


# ---------------------------------------------------------------------------
# workflow_from_procurement_request
# ---------------------------------------------------------------------------


class TestWorkflowFromProcurementRequest:
    def test_returns_dict(self, integration: HumanWorkflowIntegration) -> None:
        result = integration.workflow_from_procurement_request("pb1", "t1", "proc-001")
        assert isinstance(result, dict)

    def test_correct_source_type(self, integration: HumanWorkflowIntegration) -> None:
        result = integration.workflow_from_procurement_request("pb2", "t1", "proc-002")
        assert result["source_type"] == "procurement_request"

    def test_correct_scope(self, integration: HumanWorkflowIntegration) -> None:
        result = integration.workflow_from_procurement_request("pb3", "t1", "proc-003")
        assert result["scope"] == "procurement"

    def test_board_id_in_result(self, integration: HumanWorkflowIntegration) -> None:
        result = integration.workflow_from_procurement_request("pb4", "t1", "proc-004")
        assert result["board_id"] == "pb4"

    def test_procurement_ref_in_result(
        self, integration: HumanWorkflowIntegration
    ) -> None:
        result = integration.workflow_from_procurement_request("pb5", "t1", "proc-005")
        assert result["procurement_ref"] == "proc-005"

    def test_creates_board_in_engine(
        self,
        integration: HumanWorkflowIntegration,
        workflow_engine: HumanWorkflowEngine,
    ) -> None:
        integration.workflow_from_procurement_request("pb6", "t1", "proc-006")
        board = workflow_engine.get_board("pb6")
        assert board.scope_ref_id == "proc-006"
        assert board.name == "Procurement approval"
        assert "proc-006" not in board.name

    def test_emits_event(
        self,
        integration: HumanWorkflowIntegration,
        event_spine: EventSpineEngine,
    ) -> None:
        before = event_spine.event_count
        integration.workflow_from_procurement_request("pb7", "t1", "proc-007")
        assert event_spine.event_count > before

    def test_duplicate_board_id_raises(
        self, integration: HumanWorkflowIntegration
    ) -> None:
        integration.workflow_from_procurement_request("dup-pb", "t1", "proc-dup")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate board_id"):
            integration.workflow_from_procurement_request("dup-pb", "t1", "proc-dup2")

    def test_approval_mode_default(self, integration: HumanWorkflowIntegration) -> None:
        result = integration.workflow_from_procurement_request("pb8", "t1", "proc-008")
        assert result["approval_mode"] == "quorum"


# ---------------------------------------------------------------------------
# workflow_from_service_request
# ---------------------------------------------------------------------------


class TestWorkflowFromServiceRequest:
    def test_returns_dict(self, integration: HumanWorkflowIntegration) -> None:
        result = integration.workflow_from_service_request("h1", "t1", "svc-001")
        assert isinstance(result, dict)

    def test_correct_source_type(self, integration: HumanWorkflowIntegration) -> None:
        result = integration.workflow_from_service_request("h2", "t1", "svc-002")
        assert result["source_type"] == "service_request"

    def test_correct_scope(self, integration: HumanWorkflowIntegration) -> None:
        result = integration.workflow_from_service_request("h3", "t1", "svc-003")
        assert result["scope"] == "service"

    def test_direction_to_human(self, integration: HumanWorkflowIntegration) -> None:
        result = integration.workflow_from_service_request("h4", "t1", "svc-004")
        assert result["direction"] == "to_human"

    def test_handoff_id_in_result(self, integration: HumanWorkflowIntegration) -> None:
        result = integration.workflow_from_service_request("h5", "t1", "svc-005")
        assert result["handoff_id"] == "h5"

    def test_service_ref_in_result(self, integration: HumanWorkflowIntegration) -> None:
        result = integration.workflow_from_service_request("h6", "t1", "svc-006")
        assert result["service_ref"] == "svc-006"

    def test_creates_handoff_in_engine(
        self,
        integration: HumanWorkflowIntegration,
        workflow_engine: HumanWorkflowEngine,
    ) -> None:
        integration.workflow_from_service_request("h7", "t1", "svc-007")
        handoff = workflow_engine.get_handoff("h7")
        assert handoff.scope_ref_id == "svc-007"
        assert handoff.reason == "Service request requires human action"
        assert "svc-007" not in handoff.reason

    def test_emits_event(
        self,
        integration: HumanWorkflowIntegration,
        event_spine: EventSpineEngine,
    ) -> None:
        before = event_spine.event_count
        integration.workflow_from_service_request("h8", "t1", "svc-008")
        assert event_spine.event_count > before

    def test_duplicate_handoff_id_raises(
        self, integration: HumanWorkflowIntegration
    ) -> None:
        integration.workflow_from_service_request("dup-h", "t1", "svc-dup")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate handoff_id"):
            integration.workflow_from_service_request("dup-h", "t1", "svc-dup2")

    def test_custom_to_ref(self, integration: HumanWorkflowIntegration) -> None:
        result = integration.workflow_from_service_request(
            "h9", "t1", "svc-009", to_ref="ops_team"
        )
        assert result["source_type"] == "service_request"


# ---------------------------------------------------------------------------
# workflow_from_executive_decision
# ---------------------------------------------------------------------------


class TestWorkflowFromExecutiveDecision:
    def test_returns_dict(self, integration: HumanWorkflowIntegration) -> None:
        result = integration.workflow_from_executive_decision("e1", "t1", "dir-001")
        assert isinstance(result, dict)

    def test_correct_source_type(self, integration: HumanWorkflowIntegration) -> None:
        result = integration.workflow_from_executive_decision("e2", "t1", "dir-002")
        assert result["source_type"] == "executive_decision"

    def test_correct_scope(self, integration: HumanWorkflowIntegration) -> None:
        result = integration.workflow_from_executive_decision("e3", "t1", "dir-003")
        assert result["scope"] == "executive"

    def test_board_id_in_result(self, integration: HumanWorkflowIntegration) -> None:
        result = integration.workflow_from_executive_decision("e4", "t1", "dir-004")
        assert result["board_id"] == "e4"

    def test_directive_ref_in_result(
        self, integration: HumanWorkflowIntegration
    ) -> None:
        result = integration.workflow_from_executive_decision("e5", "t1", "dir-005")
        assert result["directive_ref"] == "dir-005"

    def test_creates_board_in_engine(
        self,
        integration: HumanWorkflowIntegration,
        workflow_engine: HumanWorkflowEngine,
    ) -> None:
        integration.workflow_from_executive_decision("e6", "t1", "dir-006")
        board = workflow_engine.get_board("e6")
        assert board.scope_ref_id == "dir-006"
        assert board.name == "Executive decision"
        assert "dir-006" not in board.name

    def test_emits_event(
        self,
        integration: HumanWorkflowIntegration,
        event_spine: EventSpineEngine,
    ) -> None:
        before = event_spine.event_count
        integration.workflow_from_executive_decision("e7", "t1", "dir-007")
        assert event_spine.event_count > before

    def test_duplicate_board_id_raises(
        self, integration: HumanWorkflowIntegration
    ) -> None:
        integration.workflow_from_executive_decision("dup-e", "t1", "dir-dup")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate board_id"):
            integration.workflow_from_executive_decision("dup-e", "t1", "dir-dup2")

    def test_approval_mode_default(self, integration: HumanWorkflowIntegration) -> None:
        result = integration.workflow_from_executive_decision("e8", "t1", "dir-008")
        assert result["approval_mode"] == "override"


# ---------------------------------------------------------------------------
# attach_human_workflow_to_memory_mesh
# ---------------------------------------------------------------------------


_COUNT_KEYS = (
    "total_tasks",
    "total_review_packets",
    "total_boards",
    "total_members",
    "total_votes",
    "total_decisions",
    "total_handoffs",
    "total_violations",
)


class TestAttachHumanWorkflowToMemoryMesh:
    def test_returns_memory_record(self, integration: HumanWorkflowIntegration) -> None:
        mem = integration.attach_human_workflow_to_memory_mesh("ref-001")
        assert isinstance(mem, MemoryRecord)
        assert mem.title == "Human workflow state"
        assert "ref-001" not in mem.title
        assert mem.scope_ref_id == "ref-001"

    def test_correct_tags(self, integration: HumanWorkflowIntegration) -> None:
        mem = integration.attach_human_workflow_to_memory_mesh("ref-002")
        assert set(mem.tags) == {"human_workflow", "approvals", "collaboration"}

    def test_content_has_all_count_fields(
        self, integration: HumanWorkflowIntegration
    ) -> None:
        mem = integration.attach_human_workflow_to_memory_mesh("ref-003")
        for key in _COUNT_KEYS:
            assert key in mem.content, f"Missing key: {key}"

    def test_content_scope_ref_id(self, integration: HumanWorkflowIntegration) -> None:
        mem = integration.attach_human_workflow_to_memory_mesh("ref-004")
        assert mem.content["scope_ref_id"] == "ref-004"

    def test_emits_event(
        self,
        integration: HumanWorkflowIntegration,
        event_spine: EventSpineEngine,
    ) -> None:
        before = event_spine.event_count
        integration.attach_human_workflow_to_memory_mesh("ref-005")
        assert event_spine.event_count > before

    def test_memory_stored_in_engine(
        self,
        integration: HumanWorkflowIntegration,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        mem = integration.attach_human_workflow_to_memory_mesh("ref-006")
        stored = memory_engine.get_memory(mem.memory_id)
        assert stored is not None
        assert stored.memory_id == mem.memory_id

    def test_counts_reflect_engine_state(
        self,
        integration: HumanWorkflowIntegration,
    ) -> None:
        # Create a board first so counts are non-zero
        integration.workflow_from_change_request("cnt-b", "t1", "cnt-ref")
        mem = integration.attach_human_workflow_to_memory_mesh("cnt-ref")
        assert mem.content["total_boards"] >= 1


# ---------------------------------------------------------------------------
# attach_human_workflow_to_graph
# ---------------------------------------------------------------------------


class TestAttachHumanWorkflowToGraph:
    def test_returns_dict(self, integration: HumanWorkflowIntegration) -> None:
        result = integration.attach_human_workflow_to_graph("g-001")
        assert isinstance(result, dict)

    def test_all_count_keys_present(
        self, integration: HumanWorkflowIntegration
    ) -> None:
        result = integration.attach_human_workflow_to_graph("g-002")
        for key in _COUNT_KEYS:
            assert key in result, f"Missing key: {key}"

    def test_scope_ref_id_in_result(
        self, integration: HumanWorkflowIntegration
    ) -> None:
        result = integration.attach_human_workflow_to_graph("g-003")
        assert result["scope_ref_id"] == "g-003"

    def test_values_match_engine_counts(
        self,
        integration: HumanWorkflowIntegration,
        workflow_engine: HumanWorkflowEngine,
    ) -> None:
        integration.workflow_from_change_request("gb", "t1", "g-ref")
        result = integration.attach_human_workflow_to_graph("g-ref")
        assert result["total_boards"] == workflow_engine.board_count
        assert result["total_tasks"] == workflow_engine.task_count
        assert result["total_handoffs"] == workflow_engine.handoff_count

    def test_graph_counts_zero_initially(
        self, integration: HumanWorkflowIntegration
    ) -> None:
        result = integration.attach_human_workflow_to_graph("g-004")
        assert result["total_boards"] == 0
        assert result["total_tasks"] == 0
        assert result["total_handoffs"] == 0
        assert result["total_violations"] == 0
