"""Purpose: tests for the operational graph core engine.
Governance scope: graph construction, traversal, causal path finding, obligation lifecycle.
Dependencies: operational graph engine, graph contracts.
Invariants:
  - Append-only: no deletion methods exist.
  - Clock determinism: identical clock produces identical results.
  - Both endpoints validated before edge creation.
  - Confidence clamped to [0.0, 1.0].
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.graph import (
    CausalPath,
    DecisionLink,
    EdgeType,
    EvidenceLink,
    GraphQueryResult,
    GraphSnapshot,
    NodeType,
    ObligationLink,
    OperationalEdge,
    OperationalNode,
    StateDelta,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.operational_graph import OperationalGraph


# --- Helpers ---

def _make_clock(start: str = "2025-01-15T10:00:00Z") -> callable:
    """Return a deterministic clock that increments by 1 second each call."""
    counter = [0]
    base = "2025-01-15T10:00:"

    def clock() -> str:
        val = counter[0]
        counter[0] += 1
        return f"{base}{val:02d}Z"

    return clock


def _make_graph(**kwargs) -> OperationalGraph:
    if "clock" not in kwargs:
        kwargs["clock"] = _make_clock()
    return OperationalGraph(**kwargs)


def _two_node_graph() -> OperationalGraph:
    g = _make_graph()
    g.add_node("n1", NodeType.GOAL, "Goal A")
    g.add_node("n2", NodeType.JOB, "Job B")
    return g


# === Node Tests ===


class TestAddNode:
    def test_add_node_returns_operational_node(self):
        g = _make_graph()
        node = g.add_node("n1", NodeType.GOAL, "My Goal")
        assert isinstance(node, OperationalNode)
        assert node.node_id == "n1"
        assert node.node_type == NodeType.GOAL
        assert node.label == "My Goal"

    def test_add_node_created_at_uses_clock(self):
        g = _make_graph()
        node = g.add_node("n1", NodeType.GOAL, "Goal")
        assert node.created_at == "2025-01-15T10:00:00Z"

    def test_add_duplicate_node_raises(self):
        g = _make_graph()
        g.add_node("n1", NodeType.GOAL, "Goal")
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate node"):
            g.add_node("n1", NodeType.JOB, "Job")

    def test_add_node_empty_id_raises(self):
        g = _make_graph()
        with pytest.raises(RuntimeCoreInvariantError):
            g.add_node("", NodeType.GOAL, "Goal")

    def test_add_node_empty_label_raises(self):
        g = _make_graph()
        with pytest.raises(RuntimeCoreInvariantError):
            g.add_node("n1", NodeType.GOAL, "")


class TestGetNode:
    def test_get_existing_node(self):
        g = _make_graph()
        g.add_node("n1", NodeType.GOAL, "Goal")
        result = g.get_node("n1")
        assert result is not None
        assert result.node_id == "n1"

    def test_get_missing_node_returns_none(self):
        g = _make_graph()
        assert g.get_node("nonexistent") is None


class TestQueryByType:
    def test_query_by_type_filters_correctly(self):
        g = _make_graph()
        g.add_node("n1", NodeType.GOAL, "Goal A")
        g.add_node("n2", NodeType.JOB, "Job B")
        g.add_node("n3", NodeType.GOAL, "Goal C")
        goals = g.query_by_type(NodeType.GOAL)
        assert len(goals) == 2
        assert all(n.node_type == NodeType.GOAL for n in goals)

    def test_query_by_type_empty_result(self):
        g = _make_graph()
        g.add_node("n1", NodeType.GOAL, "Goal")
        assert g.query_by_type(NodeType.INCIDENT) == ()


# === Edge Tests ===


class TestAddEdge:
    def test_add_edge_returns_operational_edge(self):
        g = _two_node_graph()
        edge = g.add_edge(EdgeType.CAUSED_BY, "n1", "n2", "cause link")
        assert isinstance(edge, OperationalEdge)
        assert edge.edge_type == EdgeType.CAUSED_BY
        assert edge.source_node_id == "n1"
        assert edge.target_node_id == "n2"
        assert edge.label == "cause link"

    def test_add_edge_default_label_uses_edge_type(self):
        g = _two_node_graph()
        edge = g.add_edge(EdgeType.PRODUCED, "n1", "n2")
        assert edge.label == "produced"

    def test_add_edge_missing_source_raises(self):
        g = _make_graph()
        g.add_node("n2", NodeType.JOB, "Job")
        with pytest.raises(RuntimeCoreInvariantError, match="source node not found"):
            g.add_edge(EdgeType.CAUSED_BY, "missing", "n2")

    def test_add_edge_missing_target_raises(self):
        g = _make_graph()
        g.add_node("n1", NodeType.GOAL, "Goal")
        with pytest.raises(RuntimeCoreInvariantError, match="target node not found"):
            g.add_edge(EdgeType.CAUSED_BY, "n1", "missing")

    def test_add_edge_both_missing_raises(self):
        g = _make_graph()
        with pytest.raises(RuntimeCoreInvariantError):
            g.add_edge(EdgeType.CAUSED_BY, "a", "b")


# === Evidence Link Tests ===


class TestEvidenceLink:
    def test_add_evidence_link(self):
        g = _two_node_graph()
        link = g.add_evidence_link("n1", "n2", "log_correlation", 0.85)
        assert isinstance(link, EvidenceLink)
        assert link.source_node_id == "n1"
        assert link.target_node_id == "n2"
        assert link.evidence_type == "log_correlation"
        assert link.confidence == 0.85

    def test_evidence_confidence_clamped_above(self):
        g = _two_node_graph()
        link = g.add_evidence_link("n1", "n2", "test", 1.5)
        assert link.confidence == 1.0

    def test_evidence_confidence_clamped_below(self):
        g = _two_node_graph()
        link = g.add_evidence_link("n1", "n2", "test", -0.5)
        assert link.confidence == 0.0

    def test_evidence_confidence_at_bounds(self):
        g = _two_node_graph()
        link_zero = g.add_evidence_link("n1", "n2", "test", 0.0)
        assert link_zero.confidence == 0.0
        g2 = _two_node_graph()
        link_one = g2.add_evidence_link("n1", "n2", "test", 1.0)
        assert link_one.confidence == 1.0

    def test_evidence_missing_node_raises(self):
        g = _make_graph()
        g.add_node("n1", NodeType.GOAL, "Goal")
        with pytest.raises(RuntimeCoreInvariantError):
            g.add_evidence_link("n1", "missing", "test", 0.5)

    def test_evidence_empty_type_raises(self):
        g = _two_node_graph()
        with pytest.raises(RuntimeCoreInvariantError):
            g.add_evidence_link("n1", "n2", "", 0.5)


# === Decision Link Tests ===


class TestDecisionLink:
    def test_add_decision_link(self):
        g = _two_node_graph()
        link = g.add_decision_link("n1", "n2", "approved migration", "person-42")
        assert isinstance(link, DecisionLink)
        assert link.decision == "approved migration"
        assert link.decided_by_id == "person-42"

    def test_decision_link_empty_decision_raises(self):
        g = _two_node_graph()
        with pytest.raises(RuntimeCoreInvariantError):
            g.add_decision_link("n1", "n2", "", "person-42")

    def test_decision_link_empty_decided_by_raises(self):
        g = _two_node_graph()
        with pytest.raises(RuntimeCoreInvariantError):
            g.add_decision_link("n1", "n2", "decision", "")

    def test_decision_link_missing_nodes_raises(self):
        g = _make_graph()
        with pytest.raises(RuntimeCoreInvariantError):
            g.add_decision_link("a", "b", "decision", "person")


# === Obligation Tests ===


class TestObligation:
    def test_add_obligation(self):
        g = _two_node_graph()
        link = g.add_obligation("n1", "n2", "deliver report")
        assert isinstance(link, ObligationLink)
        assert link.obligation == "deliver report"
        assert link.fulfilled is False
        assert link.deadline is None

    def test_add_obligation_with_deadline(self):
        g = _two_node_graph()
        link = g.add_obligation("n1", "n2", "deliver", deadline="2025-02-01T00:00:00Z")
        assert link.deadline == "2025-02-01T00:00:00Z"

    def test_fulfill_obligation(self):
        g = _two_node_graph()
        link = g.add_obligation("n1", "n2", "deliver report")
        fulfilled = g.fulfill_obligation(link.edge_id)
        assert fulfilled.fulfilled is True
        assert fulfilled.edge_id == link.edge_id

    def test_fulfill_already_fulfilled_raises(self):
        g = _two_node_graph()
        link = g.add_obligation("n1", "n2", "deliver")
        g.fulfill_obligation(link.edge_id)
        with pytest.raises(RuntimeCoreInvariantError, match="already fulfilled"):
            g.fulfill_obligation(link.edge_id)

    def test_fulfill_nonexistent_edge_raises(self):
        g = _make_graph()
        with pytest.raises(RuntimeCoreInvariantError, match="edge not found"):
            g.fulfill_obligation("no-such-edge")

    def test_fulfill_non_obligation_raises(self):
        g = _two_node_graph()
        edge = g.add_edge(EdgeType.CAUSED_BY, "n1", "n2", "cause")
        with pytest.raises(RuntimeCoreInvariantError, match="not an obligation"):
            g.fulfill_obligation(edge.edge_id)

    def test_find_obligations_all(self):
        g = _two_node_graph()
        g.add_obligation("n1", "n2", "obligation A")
        g.add_obligation("n1", "n2", "obligation B")
        result = g.find_obligations("n1")
        assert len(result) == 2

    def test_find_obligations_filter_fulfilled(self):
        g = _two_node_graph()
        o1 = g.add_obligation("n1", "n2", "obligation A")
        g.add_obligation("n1", "n2", "obligation B")
        g.fulfill_obligation(o1.edge_id)
        unfulfilled = g.find_obligations("n1", fulfilled=False)
        assert len(unfulfilled) == 1
        fulfilled_list = g.find_obligations("n1", fulfilled=True)
        assert len(fulfilled_list) == 1

    def test_find_obligations_empty(self):
        g = _two_node_graph()
        assert g.find_obligations("n1") == ()


# === State Delta Tests ===


class TestStateDelta:
    def test_record_state_delta(self):
        g = _make_graph()
        g.add_node("n1", NodeType.GOAL, "Goal")
        delta = g.record_state_delta("n1", "status", "active", "completed")
        assert isinstance(delta, StateDelta)
        assert delta.node_id == "n1"
        assert delta.field_name == "status"
        assert delta.old_value == "active"
        assert delta.new_value == "completed"

    def test_record_delta_missing_node_raises(self):
        g = _make_graph()
        with pytest.raises(RuntimeCoreInvariantError, match="node not found"):
            g.record_state_delta("missing", "field", "old", "new")

    def test_record_delta_empty_field_raises(self):
        g = _make_graph()
        g.add_node("n1", NodeType.GOAL, "Goal")
        with pytest.raises(RuntimeCoreInvariantError):
            g.record_state_delta("n1", "", "old", "new")


# === Edge Query Tests ===


class TestEdgeQueries:
    def test_outgoing_edges(self):
        g = _two_node_graph()
        g.add_edge(EdgeType.CAUSED_BY, "n1", "n2", "cause")
        edges = g.get_outgoing_edges("n1")
        assert len(edges) == 1
        assert edges[0].source_node_id == "n1"

    def test_incoming_edges(self):
        g = _two_node_graph()
        g.add_edge(EdgeType.CAUSED_BY, "n1", "n2", "cause")
        edges = g.get_incoming_edges("n2")
        assert len(edges) == 1
        assert edges[0].target_node_id == "n2"

    def test_outgoing_edges_filter_by_type(self):
        g = _two_node_graph()
        g.add_edge(EdgeType.CAUSED_BY, "n1", "n2", "cause")
        g.add_edge(EdgeType.PRODUCED, "n1", "n2", "produce")
        caused = g.get_outgoing_edges("n1", EdgeType.CAUSED_BY)
        assert len(caused) == 1
        assert caused[0].edge_type == EdgeType.CAUSED_BY

    def test_incoming_edges_filter_by_type(self):
        g = _two_node_graph()
        g.add_edge(EdgeType.CAUSED_BY, "n1", "n2", "cause")
        g.add_edge(EdgeType.PRODUCED, "n1", "n2", "produce")
        produced = g.get_incoming_edges("n2", EdgeType.PRODUCED)
        assert len(produced) == 1

    def test_outgoing_edges_empty(self):
        g = _two_node_graph()
        assert g.get_outgoing_edges("n1") == ()

    def test_get_neighbors(self):
        g = _two_node_graph()
        g.add_node("n3", NodeType.SKILL, "Skill C")
        g.add_edge(EdgeType.CAUSED_BY, "n1", "n2", "cause")
        g.add_edge(EdgeType.PRODUCED, "n1", "n3", "produce")
        neighbors = g.get_neighbors("n1")
        assert set(neighbors) == {"n2", "n3"}

    def test_get_neighbors_filtered(self):
        g = _two_node_graph()
        g.add_node("n3", NodeType.SKILL, "Skill C")
        g.add_edge(EdgeType.CAUSED_BY, "n1", "n2", "cause")
        g.add_edge(EdgeType.PRODUCED, "n1", "n3", "produce")
        neighbors = g.get_neighbors("n1", EdgeType.PRODUCED)
        assert neighbors == ("n3",)


# === Causal Path Tests ===


class TestCausalPath:
    def test_find_causal_path_simple(self):
        g = _make_graph()
        g.add_node("a", NodeType.GOAL, "A")
        g.add_node("b", NodeType.JOB, "B")
        g.add_node("c", NodeType.SKILL, "C")
        g.add_edge(EdgeType.CAUSED_BY, "a", "b", "cause 1")
        g.add_edge(EdgeType.PRODUCED, "b", "c", "produce 1")
        path = g.find_causal_path("a", "c")
        assert path is not None
        assert isinstance(path, CausalPath)
        assert path.node_ids[0] == "a"
        assert path.node_ids[-1] == "c"
        assert len(path.edge_ids) == 2

    def test_find_causal_path_direct(self):
        g = _make_graph()
        g.add_node("a", NodeType.GOAL, "A")
        g.add_node("b", NodeType.JOB, "B")
        g.add_edge(EdgeType.DEPENDS_ON, "a", "b", "depends")
        path = g.find_causal_path("a", "b")
        assert path is not None
        assert path.node_ids == ("a", "b")
        assert len(path.edge_ids) == 1

    def test_find_causal_path_none_when_no_path(self):
        g = _make_graph()
        g.add_node("a", NodeType.GOAL, "A")
        g.add_node("b", NodeType.JOB, "B")
        # No causal edges
        result = g.find_causal_path("a", "b")
        assert result is None

    def test_find_causal_path_ignores_non_causal_edges(self):
        g = _make_graph()
        g.add_node("a", NodeType.GOAL, "A")
        g.add_node("b", NodeType.JOB, "B")
        g.add_edge(EdgeType.ASSIGNED_TO, "a", "b", "assigned")
        result = g.find_causal_path("a", "b")
        assert result is None

    def test_find_causal_path_same_node_returns_none(self):
        g = _make_graph()
        g.add_node("a", NodeType.GOAL, "A")
        result = g.find_causal_path("a", "a")
        assert result is None  # CausalPath requires non-empty edge_ids

    def test_find_causal_path_missing_node_returns_none(self):
        g = _make_graph()
        g.add_node("a", NodeType.GOAL, "A")
        assert g.find_causal_path("a", "missing") is None
        assert g.find_causal_path("missing", "a") is None

    def test_find_causal_path_long_chain(self):
        g = _make_graph()
        for i in range(5):
            g.add_node(f"n{i}", NodeType.JOB, f"Node {i}")
        for i in range(4):
            g.add_edge(EdgeType.PRODUCED, f"n{i}", f"n{i+1}", f"step {i}")
        path = g.find_causal_path("n0", "n4")
        assert path is not None
        assert len(path.node_ids) == 5
        assert len(path.edge_ids) == 4


# === Snapshot Tests ===


class TestSnapshot:
    def test_capture_snapshot_empty_graph(self):
        g = _make_graph()
        snap = g.capture_snapshot()
        assert isinstance(snap, GraphSnapshot)
        assert snap.node_count == 0
        assert snap.edge_count == 0

    def test_capture_snapshot_counts(self):
        g = _two_node_graph()
        g.add_edge(EdgeType.CAUSED_BY, "n1", "n2", "cause")
        snap = g.capture_snapshot()
        assert snap.node_count == 2
        assert snap.edge_count == 1

    def test_snapshot_includes_all_edge_types(self):
        g = _two_node_graph()
        g.add_edge(EdgeType.CAUSED_BY, "n1", "n2", "cause")
        g.add_evidence_link("n1", "n2", "test", 0.5)
        g.add_obligation("n1", "n2", "deliver")
        snap = g.capture_snapshot()
        assert snap.edge_count == 3


# === Query Connected Tests ===


class TestQueryConnected:
    def test_query_connected_basic(self):
        g = _make_graph()
        g.add_node("a", NodeType.GOAL, "A")
        g.add_node("b", NodeType.JOB, "B")
        g.add_node("c", NodeType.SKILL, "C")
        g.add_edge(EdgeType.CAUSED_BY, "a", "b", "cause")
        g.add_edge(EdgeType.PRODUCED, "b", "c", "produce")
        result = g.query_connected("a", max_depth=3)
        assert isinstance(result, GraphQueryResult)
        node_ids = [n.node_id for n in result.matched_nodes]
        assert "a" in node_ids
        assert "b" in node_ids
        assert "c" in node_ids

    def test_query_connected_respects_max_depth(self):
        g = _make_graph()
        g.add_node("a", NodeType.GOAL, "A")
        g.add_node("b", NodeType.JOB, "B")
        g.add_node("c", NodeType.SKILL, "C")
        g.add_edge(EdgeType.CAUSED_BY, "a", "b", "cause")
        g.add_edge(EdgeType.PRODUCED, "b", "c", "produce")
        result = g.query_connected("a", max_depth=1)
        node_ids = [n.node_id for n in result.matched_nodes]
        assert "a" in node_ids
        assert "b" in node_ids
        assert "c" not in node_ids  # depth 2, beyond max_depth=1

    def test_query_connected_depth_zero(self):
        g = _make_graph()
        g.add_node("a", NodeType.GOAL, "A")
        g.add_node("b", NodeType.JOB, "B")
        g.add_edge(EdgeType.CAUSED_BY, "a", "b", "cause")
        result = g.query_connected("a", max_depth=0)
        node_ids = [n.node_id for n in result.matched_nodes]
        assert node_ids == ["a"]

    def test_query_connected_missing_node_raises(self):
        g = _make_graph()
        with pytest.raises(RuntimeCoreInvariantError, match="node not found"):
            g.query_connected("nonexistent")

    def test_query_connected_isolated_node(self):
        g = _make_graph()
        g.add_node("lonely", NodeType.GOAL, "Lonely")
        result = g.query_connected("lonely")
        assert len(result.matched_nodes) == 1
        assert result.matched_nodes[0].node_id == "lonely"
        assert len(result.matched_edges) == 0


# === Append-Only Invariant Tests ===


class TestAppendOnly:
    def test_no_delete_node_method(self):
        g = _make_graph()
        assert not hasattr(g, "delete_node")
        assert not hasattr(g, "remove_node")

    def test_no_delete_edge_method(self):
        g = _make_graph()
        assert not hasattr(g, "delete_edge")
        assert not hasattr(g, "remove_edge")


# === Clock Determinism Tests ===


class TestClockDeterminism:
    def test_same_clock_produces_same_timestamps(self):
        clock1 = _make_clock()
        clock2 = _make_clock()
        g1 = OperationalGraph(clock=clock1)
        g2 = OperationalGraph(clock=clock2)
        n1 = g1.add_node("x", NodeType.GOAL, "Goal")
        n2 = g2.add_node("x", NodeType.GOAL, "Goal")
        assert n1.created_at == n2.created_at

    def test_clock_advances(self):
        g = _make_graph()
        n1 = g.add_node("a", NodeType.GOAL, "A")
        n2 = g.add_node("b", NodeType.JOB, "B")
        assert n1.created_at != n2.created_at

    def test_custom_clock_used_in_edges(self):
        fixed = lambda: "2099-12-31T23:59:59Z"
        g = OperationalGraph(clock=fixed)
        g.add_node("a", NodeType.GOAL, "A")
        g.add_node("b", NodeType.JOB, "B")
        edge = g.add_edge(EdgeType.CAUSED_BY, "a", "b", "cause")
        assert edge.created_at == "2099-12-31T23:59:59Z"

    def test_custom_clock_used_in_snapshot(self):
        fixed = lambda: "2099-12-31T23:59:59Z"
        g = OperationalGraph(clock=fixed)
        snap = g.capture_snapshot()
        assert snap.captured_at == "2099-12-31T23:59:59Z"


# === Mixed Edge Type Queries ===


class TestMixedEdgeTypeQueries:
    def test_evidence_link_appears_in_outgoing(self):
        g = _two_node_graph()
        g.add_evidence_link("n1", "n2", "log", 0.9)
        edges = g.get_outgoing_edges("n1")
        assert len(edges) == 1
        assert isinstance(edges[0], EvidenceLink)

    def test_decision_link_appears_in_incoming(self):
        g = _two_node_graph()
        g.add_decision_link("n1", "n2", "approved", "person-1")
        edges = g.get_incoming_edges("n2")
        assert len(edges) == 1
        assert isinstance(edges[0], DecisionLink)

    def test_obligation_appears_in_edges(self):
        g = _two_node_graph()
        g.add_obligation("n1", "n2", "deliver report")
        outgoing = g.get_outgoing_edges("n1")
        incoming = g.get_incoming_edges("n2")
        assert len(outgoing) == 1
        assert len(incoming) == 1
        assert isinstance(outgoing[0], ObligationLink)

    def test_filter_excludes_non_matching_specialized_links(self):
        g = _two_node_graph()
        g.add_evidence_link("n1", "n2", "log", 0.9)
        g.add_edge(EdgeType.CAUSED_BY, "n1", "n2", "cause")
        # Evidence links are typed as VERIFIED_BY internally
        caused = g.get_outgoing_edges("n1", EdgeType.CAUSED_BY)
        assert len(caused) == 1
        assert isinstance(caused[0], OperationalEdge)


# === Comprehensive Integration Test ===


class TestIntegration:
    def test_full_graph_workflow(self):
        """Build a realistic graph and exercise all major operations."""
        g = _make_graph()

        # Add nodes
        goal = g.add_node("goal-1", NodeType.GOAL, "Deploy v2")
        job = g.add_node("job-1", NodeType.JOB, "Run migration")
        skill = g.add_node("skill-1", NodeType.SKILL, "DB migration skill")
        person = g.add_node("person-1", NodeType.PERSON, "Alice")

        # Add edges
        g.add_edge(EdgeType.DEPENDS_ON, "goal-1", "job-1", "goal depends on job")
        g.add_edge(EdgeType.PRODUCED, "job-1", "skill-1", "job uses skill")

        # Evidence
        g.add_evidence_link("skill-1", "goal-1", "success_metric", 0.95)

        # Decision
        g.add_decision_link("goal-1", "job-1", "proceed with migration", "person-1")

        # Obligation
        obl = g.add_obligation("person-1", "job-1", "complete by Friday",
                                deadline="2025-01-20T00:00:00Z")

        # Delta
        g.record_state_delta("job-1", "status", "pending", "in_progress")

        # Snapshot
        snap = g.capture_snapshot()
        assert snap.node_count == 4
        assert snap.edge_count == 5

        # Causal path
        path = g.find_causal_path("goal-1", "skill-1")
        assert path is not None
        assert path.node_ids[0] == "goal-1"
        assert path.node_ids[-1] == "skill-1"

        # Fulfill obligation
        fulfilled = g.fulfill_obligation(obl.edge_id)
        assert fulfilled.fulfilled is True

        # Query connected
        result = g.query_connected("goal-1", max_depth=2)
        node_ids = [n.node_id for n in result.matched_nodes]
        assert "goal-1" in node_ids
        assert "job-1" in node_ids
