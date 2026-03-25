"""Purpose: verify GraphBridge wiring and GraphSummaryView projections.
Governance scope: graph integration tests only.
Dependencies: graph_integration, contracts.graph, operational_graph (real modules).
Invariants:
  - Each link method creates the correct edge type.
  - Nodes are auto-created with the correct NodeType.
  - Duplicate links are idempotent (no crash).
  - Obligation creation honours deadline.
  - View model accurately projects graph state.
  - Console rendering is deterministic.
"""

from __future__ import annotations

from mcoi_runtime.contracts.graph import (
    EdgeType,
    NodeType,
    ObligationLink,
    OperationalEdge,
    OperationalNode,
)
from mcoi_runtime.core.operational_graph import OperationalGraph
from mcoi_runtime.core.graph_integration import GraphBridge
from mcoi_runtime.app.view_models import GraphSummaryView
from mcoi_runtime.app.console import render_graph_summary


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_clock() -> callable:
    """Return a deterministic clock for test graphs."""
    counter = {"t": 0}

    def _clock() -> str:
        counter["t"] += 1
        return f"2026-01-01T00:00:{counter['t']:02d}Z"

    return _clock


def _new_graph() -> OperationalGraph:
    return OperationalGraph(clock=_make_clock())


# ===================================================================
# Tests -- link methods create correct edge type
# ===================================================================


class TestLinkGoalToWorkflow:
    def test_creates_depends_on_edge(self) -> None:
        g = _new_graph()
        edge = GraphBridge.link_goal_to_workflow(g, "g-1", "wf-1")
        assert isinstance(edge, OperationalEdge)
        assert edge.edge_type == EdgeType.DEPENDS_ON
        assert edge.source_node_id == "g-1"
        assert edge.target_node_id == "wf-1"

    def test_auto_creates_goal_node(self) -> None:
        g = _new_graph()
        GraphBridge.link_goal_to_workflow(g, "g-1", "wf-1")
        node = g.get_node("g-1")
        assert node is not None
        assert node.node_type == NodeType.GOAL

    def test_auto_creates_workflow_node(self) -> None:
        g = _new_graph()
        GraphBridge.link_goal_to_workflow(g, "g-1", "wf-1")
        node = g.get_node("wf-1")
        assert node is not None
        assert node.node_type == NodeType.WORKFLOW


class TestLinkWorkflowToSkill:
    def test_creates_depends_on_edge(self) -> None:
        g = _new_graph()
        edge = GraphBridge.link_workflow_to_skill(g, "wf-1", "sk-1")
        assert edge.edge_type == EdgeType.DEPENDS_ON

    def test_auto_creates_skill_node(self) -> None:
        g = _new_graph()
        GraphBridge.link_workflow_to_skill(g, "wf-1", "sk-1")
        node = g.get_node("sk-1")
        assert node is not None
        assert node.node_type == NodeType.SKILL


class TestLinkSkillToProvider:
    def test_creates_depends_on_edge(self) -> None:
        g = _new_graph()
        edge = GraphBridge.link_skill_to_provider(g, "sk-1", "pa-1")
        assert edge.edge_type == EdgeType.DEPENDS_ON

    def test_auto_creates_provider_action_node(self) -> None:
        g = _new_graph()
        GraphBridge.link_skill_to_provider(g, "sk-1", "pa-1")
        node = g.get_node("pa-1")
        assert node is not None
        assert node.node_type == NodeType.PROVIDER_ACTION


class TestLinkActionToVerification:
    def test_creates_verified_by_edge(self) -> None:
        g = _new_graph()
        edge = GraphBridge.link_action_to_verification(g, "pa-1", "v-1")
        assert edge.edge_type == EdgeType.VERIFIED_BY

    def test_auto_creates_verification_node(self) -> None:
        g = _new_graph()
        GraphBridge.link_action_to_verification(g, "pa-1", "v-1")
        node = g.get_node("v-1")
        assert node is not None
        assert node.node_type == NodeType.VERIFICATION


class TestLinkVerificationToIncident:
    def test_creates_caused_by_edge(self) -> None:
        g = _new_graph()
        edge = GraphBridge.link_verification_to_incident(g, "v-1", "inc-1")
        assert edge.edge_type == EdgeType.CAUSED_BY


class TestLinkIncidentToEscalation:
    def test_creates_escalated_to_edge(self) -> None:
        g = _new_graph()
        edge = GraphBridge.link_incident_to_escalation(g, "inc-1", "esc-1")
        assert edge.edge_type == EdgeType.ESCALATED_TO

    def test_auto_creates_person_node(self) -> None:
        g = _new_graph()
        GraphBridge.link_incident_to_escalation(g, "inc-1", "esc-1")
        node = g.get_node("esc-1")
        assert node is not None
        assert node.node_type == NodeType.PERSON


class TestLinkJobToOwner:
    def test_creates_owns_edge(self) -> None:
        g = _new_graph()
        edge = GraphBridge.link_job_to_owner(g, "j-1", "id-1")
        assert edge.edge_type == EdgeType.OWNS

    def test_auto_creates_person_node(self) -> None:
        g = _new_graph()
        GraphBridge.link_job_to_owner(g, "j-1", "id-1")
        node = g.get_node("id-1")
        assert node is not None
        assert node.node_type == NodeType.PERSON


class TestLinkJobToFunction:
    def test_creates_produced_edge(self) -> None:
        g = _new_graph()
        edge = GraphBridge.link_job_to_function(g, "j-1", "fn-1")
        assert edge.edge_type == EdgeType.PRODUCED

    def test_auto_creates_function_node(self) -> None:
        g = _new_graph()
        GraphBridge.link_job_to_function(g, "j-1", "fn-1")
        node = g.get_node("fn-1")
        assert node is not None
        assert node.node_type == NodeType.FUNCTION


class TestLinkApprovalToAction:
    def test_creates_decided_by_edge(self) -> None:
        g = _new_graph()
        edge = GraphBridge.link_approval_to_action(g, "apr-1", "pa-1")
        assert edge.edge_type == EdgeType.DECIDED_BY

    def test_auto_creates_approval_node(self) -> None:
        g = _new_graph()
        GraphBridge.link_approval_to_action(g, "apr-1", "pa-1")
        node = g.get_node("apr-1")
        assert node is not None
        assert node.node_type == NodeType.APPROVAL


class TestLinkThreadToJob:
    def test_creates_communicates_via_edge(self) -> None:
        g = _new_graph()
        edge = GraphBridge.link_thread_to_job(g, "thr-1", "j-1")
        assert edge.edge_type == EdgeType.COMMUNICATES_VIA

    def test_auto_creates_thread_node(self) -> None:
        g = _new_graph()
        GraphBridge.link_thread_to_job(g, "thr-1", "j-1")
        node = g.get_node("thr-1")
        assert node is not None
        assert node.node_type == NodeType.COMMUNICATION_THREAD


# ===================================================================
# Tests -- idempotency
# ===================================================================


class TestIdempotency:
    def test_duplicate_link_does_not_crash(self) -> None:
        g = _new_graph()
        GraphBridge.link_goal_to_workflow(g, "g-1", "wf-1")
        GraphBridge.link_goal_to_workflow(g, "g-1", "wf-1")
        # Two edges (edges are append-only), but no exception.
        assert len(g.all_edges()) == 2

    def test_shared_node_keeps_original_type(self) -> None:
        g = _new_graph()
        GraphBridge.link_goal_to_workflow(g, "g-1", "wf-1")
        GraphBridge.link_workflow_to_skill(g, "wf-1", "sk-1")
        # wf-1 was first created as WORKFLOW and stays WORKFLOW.
        node = g.get_node("wf-1")
        assert node is not None
        assert node.node_type == NodeType.WORKFLOW


# ===================================================================
# Tests -- obligation creation
# ===================================================================


class TestObligationCreation:
    def test_creates_obligation_without_deadline(self) -> None:
        g = _new_graph()
        obl = GraphBridge.add_obligation_for_job(g, "j-1", "id-1", "do the thing")
        assert isinstance(obl, ObligationLink)
        assert obl.source_node_id == "j-1"
        assert obl.target_node_id == "id-1"
        assert obl.obligation == "do the thing"
        assert obl.deadline is None
        assert obl.fulfilled is False

    def test_creates_obligation_with_deadline(self) -> None:
        g = _new_graph()
        obl = GraphBridge.add_obligation_for_job(
            g, "j-2", "id-2", "urgent task", deadline="2026-04-01T00:00:00Z",
        )
        assert obl.deadline == "2026-04-01T00:00:00Z"

    def test_obligation_nodes_auto_created(self) -> None:
        g = _new_graph()
        GraphBridge.add_obligation_for_job(g, "j-3", "id-3", "desc")
        assert g.get_node("j-3") is not None
        assert g.get_node("j-3").node_type == NodeType.JOB
        assert g.get_node("id-3") is not None
        assert g.get_node("id-3").node_type == NodeType.PERSON


# ===================================================================
# Tests -- GraphSummaryView
# ===================================================================


class TestGraphSummaryView:
    def test_from_empty_graph(self) -> None:
        g = _new_graph()
        view = GraphSummaryView.from_graph(g)
        assert view.total_nodes == 0
        assert view.total_edges == 0
        assert view.unfulfilled_obligations == 0
        assert dict(view.node_types) == {}

    def test_from_populated_graph(self) -> None:
        g = _new_graph()
        GraphBridge.link_goal_to_workflow(g, "g-1", "wf-1")
        GraphBridge.add_obligation_for_job(g, "j-1", "id-1", "do it")
        view = GraphSummaryView.from_graph(g)
        # Nodes: g-1, wf-1, j-1, id-1
        assert view.total_nodes == 4
        # Edges: 1 OperationalEdge + 1 ObligationLink
        assert view.total_edges == 2
        assert view.unfulfilled_obligations == 1
        assert view.node_types["goal"] == 1
        assert view.node_types["workflow"] == 1

    def test_fulfilled_obligation_not_counted(self) -> None:
        g = _new_graph()
        obl = GraphBridge.add_obligation_for_job(g, "j-1", "id-1", "done")
        g.fulfill_obligation(obl.edge_id)
        view = GraphSummaryView.from_graph(g)
        assert view.unfulfilled_obligations == 0


# ===================================================================
# Tests -- console rendering
# ===================================================================


class TestRenderGraphSummary:
    def test_render_empty(self) -> None:
        view = GraphSummaryView(
            total_nodes=0,
            total_edges=0,
            node_types={},
            unfulfilled_obligations=0,
        )
        text = render_graph_summary(view)
        assert "=== Graph Summary ===" in text
        assert "total_nodes:" in text

    def test_render_with_types(self) -> None:
        view = GraphSummaryView(
            total_nodes=5,
            total_edges=3,
            node_types={"goal": 2, "workflow": 3},
            unfulfilled_obligations=1,
        )
        text = render_graph_summary(view)
        assert "goal: 2" in text
        assert "workflow: 3" in text
        assert "unfulfilled_obligations:" in text
