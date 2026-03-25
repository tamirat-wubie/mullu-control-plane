"""Purpose: golden scenarios validating end-to-end graph integration paths.
Governance scope: graph golden scenario tests only.
Dependencies: graph_integration, contracts.graph, operational_graph (real modules).
Invariants:
  - Full causal paths are findable through causal edges (CAUSED_BY, PRODUCED, DEPENDS_ON).
  - Obligation lifecycle (create, fulfil) works correctly.
  - Provenance and decision links are preserved across multi-hop chains.
  - Organisational context (thread -> job -> function) is connected.
  - Multi-path graphs return correct connected subgraphs.
"""

from __future__ import annotations

from mcoi_runtime.contracts.graph import (
    CausalPath,
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
# Scenario 1: Goal -> Workflow -> Skill -> Provider (causal chain)
#              Full causal path findable through DEPENDS_ON edges
# ===================================================================


class TestGoalToProviderCausalChain:
    """Full execution chain using DEPENDS_ON edges: goal -> workflow -> skill -> provider.
    These are all causal edges, so find_causal_path can traverse them.
    VERIFIED_BY (action -> verification) is NOT a causal edge type, so the
    causal path stops at the provider action node.
    """

    def _build_chain(self) -> OperationalGraph:
        g = _new_graph()
        GraphBridge.link_goal_to_workflow(g, "g-1", "wf-1")
        GraphBridge.link_workflow_to_skill(g, "wf-1", "sk-1")
        GraphBridge.link_skill_to_provider(g, "sk-1", "pa-1")
        GraphBridge.link_action_to_verification(g, "pa-1", "v-1")
        return g

    def test_causal_path_from_goal_to_provider(self) -> None:
        g = self._build_chain()
        path = g.find_causal_path("g-1", "pa-1")
        assert path is not None
        assert isinstance(path, CausalPath)
        assert path.node_ids == ("g-1", "wf-1", "sk-1", "pa-1")

    def test_no_causal_path_to_verification(self) -> None:
        """VERIFIED_BY is not a causal edge, so no causal path reaches v-1."""
        g = self._build_chain()
        path = g.find_causal_path("g-1", "v-1")
        assert path is None

    def test_all_five_nodes_present(self) -> None:
        g = self._build_chain()
        assert len(g.all_nodes()) == 5

    def test_four_edges_present(self) -> None:
        g = self._build_chain()
        assert len(g.all_edges()) == 4

    def test_no_reverse_causal_path(self) -> None:
        g = self._build_chain()
        path = g.find_causal_path("pa-1", "g-1")
        assert path is None


# ===================================================================
# Scenario 2: Job -> Owner obligation -- created and fulfillable
# ===================================================================


class TestJobOwnerObligation:
    def test_obligation_created(self) -> None:
        g = _new_graph()
        obl = GraphBridge.add_obligation_for_job(
            g, "j-1", "owner-1", "complete deployment",
        )
        assert obl.fulfilled is False
        assert obl.obligation == "complete deployment"

    def test_obligation_fulfillable(self) -> None:
        g = _new_graph()
        obl = GraphBridge.add_obligation_for_job(
            g, "j-1", "owner-1", "complete deployment",
        )
        fulfilled = g.fulfill_obligation(obl.edge_id)
        assert fulfilled.fulfilled is True
        view = GraphSummaryView.from_graph(g)
        assert view.unfulfilled_obligations == 0

    def test_obligation_with_deadline(self) -> None:
        g = _new_graph()
        obl = GraphBridge.add_obligation_for_job(
            g, "j-1", "owner-1", "deploy by EOD",
            deadline="2026-03-20T17:00:00Z",
        )
        assert obl.deadline == "2026-03-20T17:00:00Z"

    def test_job_and_owner_nodes_exist(self) -> None:
        g = _new_graph()
        GraphBridge.add_obligation_for_job(g, "j-1", "owner-1", "desc")
        assert g.get_node("j-1") is not None
        assert g.get_node("j-1").node_type == NodeType.JOB
        assert g.get_node("owner-1") is not None
        assert g.get_node("owner-1").node_type == NodeType.PERSON


# ===================================================================
# Scenario 3: Incident -> Escalation chain
#              Provenance traceable via causal edges
# ===================================================================


class TestIncidentEscalationChain:
    def _build_chain(self) -> OperationalGraph:
        g = _new_graph()
        # action -> verification (VERIFIED_BY, non-causal)
        GraphBridge.link_action_to_verification(g, "pa-1", "v-1")
        # verification -> incident (CAUSED_BY, causal)
        GraphBridge.link_verification_to_incident(g, "v-1", "inc-1")
        # incident -> escalation (ESCALATED_TO, non-causal)
        GraphBridge.link_incident_to_escalation(g, "inc-1", "esc-1")
        return g

    def test_causal_path_from_verification_to_incident(self) -> None:
        """CAUSED_BY is a causal edge type, so verification -> incident is traversable."""
        g = self._build_chain()
        path = g.find_causal_path("v-1", "inc-1")
        assert path is not None
        assert path.node_ids == ("v-1", "inc-1")

    def test_no_causal_path_across_non_causal_edges(self) -> None:
        """No causal path from pa-1 to esc-1 because VERIFIED_BY and ESCALATED_TO are non-causal."""
        g = self._build_chain()
        path = g.find_causal_path("pa-1", "esc-1")
        assert path is None

    def test_incident_node_type(self) -> None:
        g = self._build_chain()
        node = g.get_node("inc-1")
        assert node is not None
        assert node.node_type == NodeType.INCIDENT

    def test_escalation_target_type(self) -> None:
        g = self._build_chain()
        node = g.get_node("esc-1")
        assert node is not None
        assert node.node_type == NodeType.PERSON


# ===================================================================
# Scenario 4: Approval -> Action -> Verification
#              Decision link preserved, connected query works
# ===================================================================


class TestApprovalActionVerification:
    def _build_chain(self) -> OperationalGraph:
        g = _new_graph()
        GraphBridge.link_approval_to_action(g, "apr-1", "pa-1")
        GraphBridge.link_action_to_verification(g, "pa-1", "v-1")
        return g

    def test_approval_edge_type(self) -> None:
        g = self._build_chain()
        edges = g.all_edges()
        first_edge = edges[0]
        assert isinstance(first_edge, OperationalEdge)
        assert first_edge.edge_type == EdgeType.DECIDED_BY

    def test_decision_provenance_traceable_via_query_connected(self) -> None:
        """Verification node is reachable from the approval via outgoing edge traversal."""
        g = self._build_chain()
        result = g.query_connected("apr-1")
        node_ids = {n.node_id for n in result.matched_nodes}
        # apr-1 -> pa-1 -> v-1 (all via outgoing directed edges)
        assert "v-1" in node_ids

    def test_three_nodes_present(self) -> None:
        g = self._build_chain()
        assert len(g.all_nodes()) == 3


# ===================================================================
# Scenario 5: Thread -> Job -> Function
#              Organisational context connected
# ===================================================================


class TestThreadJobFunction:
    def _build_chain(self) -> OperationalGraph:
        g = _new_graph()
        GraphBridge.link_thread_to_job(g, "thr-1", "j-1")
        GraphBridge.link_job_to_function(g, "j-1", "fn-1")
        return g

    def test_connected_query_from_thread(self) -> None:
        """Thread -> Job -> Function reachable via outgoing directed edges."""
        g = self._build_chain()
        result = g.query_connected("thr-1")
        node_ids = {n.node_id for n in result.matched_nodes}
        assert node_ids == {"thr-1", "j-1", "fn-1"}

    def test_thread_type(self) -> None:
        g = self._build_chain()
        node = g.get_node("thr-1")
        assert node is not None
        assert node.node_type == NodeType.COMMUNICATION_THREAD

    def test_function_type(self) -> None:
        g = self._build_chain()
        node = g.get_node("fn-1")
        assert node is not None
        assert node.node_type == NodeType.FUNCTION

    def test_job_is_shared_node(self) -> None:
        g = self._build_chain()
        node = g.get_node("j-1")
        assert node is not None
        assert node.node_type == NodeType.JOB


# ===================================================================
# Scenario 6: Multi-path graph
#              query_connected returns correct subgraph
# ===================================================================


class TestMultiPathGraph:
    def _build_graph(self) -> OperationalGraph:
        """Build two disjoint subgraphs:
        Subgraph A: g-1 -> wf-1 -> sk-1  (via DEPENDS_ON)
        Subgraph B: j-1 -> owner-1 (OWNS), j-1 -> fn-1 (PRODUCED)
        """
        g = _new_graph()
        # Subgraph A
        GraphBridge.link_goal_to_workflow(g, "g-1", "wf-1")
        GraphBridge.link_workflow_to_skill(g, "wf-1", "sk-1")
        # Subgraph B
        GraphBridge.link_job_to_owner(g, "j-1", "owner-1")
        GraphBridge.link_job_to_function(g, "j-1", "fn-1")
        return g

    def test_subgraph_a_from_goal(self) -> None:
        """query_connected from g-1 follows outgoing edges to wf-1 and sk-1."""
        g = self._build_graph()
        result = g.query_connected("g-1")
        node_ids = {n.node_id for n in result.matched_nodes}
        assert node_ids == {"g-1", "wf-1", "sk-1"}

    def test_subgraph_b_from_job(self) -> None:
        """query_connected from j-1 follows outgoing edges to owner-1 and fn-1."""
        g = self._build_graph()
        result = g.query_connected("j-1")
        node_ids = {n.node_id for n in result.matched_nodes}
        assert node_ids == {"j-1", "owner-1", "fn-1"}

    def test_subgraph_a_edges(self) -> None:
        g = self._build_graph()
        result = g.query_connected("g-1")
        assert len(result.matched_edges) == 2

    def test_subgraph_b_edges(self) -> None:
        g = self._build_graph()
        result = g.query_connected("j-1")
        assert len(result.matched_edges) == 2

    def test_no_cross_subgraph_leak(self) -> None:
        g = self._build_graph()
        result_a = g.query_connected("g-1")
        node_ids_a = {n.node_id for n in result_a.matched_nodes}
        assert "j-1" not in node_ids_a
        assert "owner-1" not in node_ids_a

    def test_full_graph_node_count(self) -> None:
        g = self._build_graph()
        assert len(g.all_nodes()) == 6

    def test_full_graph_view_model(self) -> None:
        g = self._build_graph()
        view = GraphSummaryView.from_graph(g)
        assert view.total_nodes == 6
        assert view.total_edges == 4

    def test_full_graph_console_render(self) -> None:
        g = self._build_graph()
        view = GraphSummaryView.from_graph(g)
        text = render_graph_summary(view)
        assert "total_nodes:" in text
        assert "total_edges:" in text
        assert "goal:" in text
