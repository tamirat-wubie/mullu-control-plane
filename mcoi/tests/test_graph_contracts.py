"""Tests for operational graph contracts."""

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


TS = "2025-06-01T12:00:00+00:00"
TS2 = "2025-06-01T13:00:00+00:00"


# --- Helpers ---


def _node(**overrides):
    defaults = dict(
        node_id="node-001",
        node_type=NodeType.GOAL,
        label="test goal",
        created_at=TS,
    )
    defaults.update(overrides)
    return OperationalNode(**defaults)


def _edge(**overrides):
    defaults = dict(
        edge_id="edge-001",
        edge_type=EdgeType.CAUSED_BY,
        source_node_id="node-001",
        target_node_id="node-002",
        label="caused by incident",
        created_at=TS,
    )
    defaults.update(overrides)
    return OperationalEdge(**defaults)


def _evidence(**overrides):
    defaults = dict(
        edge_id="ev-001",
        source_node_id="node-001",
        target_node_id="node-002",
        evidence_type="log_correlation",
        confidence=0.85,
        created_at=TS,
    )
    defaults.update(overrides)
    return EvidenceLink(**defaults)


def _decision(**overrides):
    defaults = dict(
        edge_id="dec-001",
        source_node_id="node-001",
        target_node_id="node-002",
        decision="approved",
        decided_by_id="person-001",
        created_at=TS,
    )
    defaults.update(overrides)
    return DecisionLink(**defaults)


def _obligation(**overrides):
    defaults = dict(
        edge_id="obl-001",
        source_node_id="node-001",
        target_node_id="node-002",
        obligation="must remediate within SLA",
        fulfilled=False,
        created_at=TS,
    )
    defaults.update(overrides)
    return ObligationLink(**defaults)


def _state_delta(**overrides):
    defaults = dict(
        delta_id="delta-001",
        node_id="node-001",
        field_name="status",
        old_value="open",
        new_value="closed",
        changed_at=TS,
    )
    defaults.update(overrides)
    return StateDelta(**defaults)


def _causal_path(**overrides):
    defaults = dict(
        path_id="path-001",
        node_ids=("node-001", "node-002"),
        edge_ids=("edge-001",),
        description="incident caused goal failure",
    )
    defaults.update(overrides)
    return CausalPath(**defaults)


def _snapshot(**overrides):
    defaults = dict(
        snapshot_id="snap-001",
        node_count=10,
        edge_count=15,
        captured_at=TS,
    )
    defaults.update(overrides)
    return GraphSnapshot(**defaults)


def _query_result(**overrides):
    defaults = dict(
        query_id="q-001",
        matched_nodes=(),
        matched_edges=(),
        executed_at=TS,
    )
    defaults.update(overrides)
    return GraphQueryResult(**defaults)


# ========== NodeType enum ==========


class TestNodeType:
    def test_all_node_types_exist(self):
        expected = {
            "goal", "workflow", "skill", "job", "incident", "approval",
            "review", "runbook", "provider_action", "verification",
            "communication_thread", "document", "function", "person", "team",
        }
        assert {m.value for m in NodeType} == expected

    def test_node_type_count(self):
        assert len(NodeType) == 15

    def test_node_type_is_str(self):
        assert isinstance(NodeType.GOAL, str)
        assert NodeType.GOAL == "goal"


# ========== EdgeType enum ==========


class TestEdgeType:
    def test_all_edge_types_exist(self):
        expected = {
            "caused_by", "depends_on", "owns", "obligated_to", "decided_by",
            "blocked_by", "escalated_to", "produced", "verified_by",
            "assigned_to", "communicates_via",
        }
        assert {m.value for m in EdgeType} == expected

    def test_edge_type_count(self):
        assert len(EdgeType) == 11

    def test_edge_type_is_str(self):
        assert isinstance(EdgeType.CAUSED_BY, str)
        assert EdgeType.CAUSED_BY == "caused_by"


# ========== OperationalNode ==========


class TestOperationalNode:
    def test_valid_construction(self):
        n = _node()
        assert n.node_id == "node-001"
        assert n.node_type == NodeType.GOAL
        assert n.label == "test goal"
        assert n.created_at == TS

    def test_empty_node_id_rejected(self):
        with pytest.raises(ValueError, match="node_id"):
            _node(node_id="")

    def test_whitespace_node_id_rejected(self):
        with pytest.raises(ValueError, match="node_id"):
            _node(node_id="   ")

    def test_invalid_node_type_rejected(self):
        with pytest.raises(ValueError, match="node_type"):
            _node(node_type="bogus")

    def test_empty_label_rejected(self):
        with pytest.raises(ValueError, match="label"):
            _node(label="")

    def test_invalid_created_at_rejected(self):
        with pytest.raises(ValueError, match="created_at"):
            _node(created_at="not-a-date")

    def test_metadata_frozen(self):
        n = _node(metadata={"key": "value"})
        with pytest.raises(TypeError):
            n.metadata["new"] = "item"

    def test_to_dict(self):
        n = _node()
        d = n.to_dict()
        assert d["node_id"] == "node-001"
        assert d["node_type"] == "goal"

    def test_to_json(self):
        n = _node()
        j = n.to_json()
        assert '"node_id":"node-001"' in j

    def test_frozen(self):
        n = _node()
        with pytest.raises(AttributeError):
            n.node_id = "changed"

    def test_all_node_types_accepted(self):
        for nt in NodeType:
            n = _node(node_type=nt)
            assert n.node_type == nt


# ========== OperationalEdge ==========


class TestOperationalEdge:
    def test_valid_construction(self):
        e = _edge()
        assert e.edge_id == "edge-001"
        assert e.edge_type == EdgeType.CAUSED_BY
        assert e.source_node_id == "node-001"
        assert e.target_node_id == "node-002"

    def test_empty_edge_id_rejected(self):
        with pytest.raises(ValueError, match="edge_id"):
            _edge(edge_id="")

    def test_invalid_edge_type_rejected(self):
        with pytest.raises(ValueError, match="edge_type"):
            _edge(edge_type="bogus")

    def test_empty_source_rejected(self):
        with pytest.raises(ValueError, match="source_node_id"):
            _edge(source_node_id="")

    def test_empty_target_rejected(self):
        with pytest.raises(ValueError, match="target_node_id"):
            _edge(target_node_id="")

    def test_empty_label_rejected(self):
        with pytest.raises(ValueError, match="label"):
            _edge(label="")

    def test_invalid_created_at_rejected(self):
        with pytest.raises(ValueError, match="created_at"):
            _edge(created_at="bad")

    def test_metadata_frozen(self):
        e = _edge(metadata={"k": "v"})
        with pytest.raises(TypeError):
            e.metadata["x"] = "y"

    def test_to_dict(self):
        e = _edge()
        d = e.to_dict()
        assert d["source_node_id"] == "node-001"
        assert d["edge_type"] == "caused_by"

    def test_frozen(self):
        e = _edge()
        with pytest.raises(AttributeError):
            e.edge_id = "changed"

    def test_all_edge_types_accepted(self):
        for et in EdgeType:
            e = _edge(edge_type=et)
            assert e.edge_type == et


# ========== EvidenceLink ==========


class TestEvidenceLink:
    def test_valid_construction(self):
        ev = _evidence()
        assert ev.confidence == 0.85
        assert ev.evidence_type == "log_correlation"

    def test_confidence_zero(self):
        ev = _evidence(confidence=0.0)
        assert ev.confidence == 0.0

    def test_confidence_one(self):
        ev = _evidence(confidence=1.0)
        assert ev.confidence == 1.0

    def test_confidence_negative_rejected(self):
        with pytest.raises(ValueError, match="confidence"):
            _evidence(confidence=-0.1)

    def test_confidence_above_one_rejected(self):
        with pytest.raises(ValueError, match="confidence"):
            _evidence(confidence=1.1)

    def test_empty_evidence_type_rejected(self):
        with pytest.raises(ValueError, match="evidence_type"):
            _evidence(evidence_type="")

    def test_empty_edge_id_rejected(self):
        with pytest.raises(ValueError, match="edge_id"):
            _evidence(edge_id="")

    def test_empty_source_rejected(self):
        with pytest.raises(ValueError, match="source_node_id"):
            _evidence(source_node_id="")

    def test_empty_target_rejected(self):
        with pytest.raises(ValueError, match="target_node_id"):
            _evidence(target_node_id="")

    def test_to_dict(self):
        ev = _evidence()
        d = ev.to_dict()
        assert d["confidence"] == 0.85

    def test_frozen(self):
        ev = _evidence()
        with pytest.raises(AttributeError):
            ev.confidence = 0.5

    def test_int_confidence_coerced_to_float(self):
        ev = _evidence(confidence=1)
        assert ev.confidence == 1.0
        assert isinstance(ev.confidence, float)


# ========== DecisionLink ==========


class TestDecisionLink:
    def test_valid_construction(self):
        d = _decision()
        assert d.decision == "approved"
        assert d.decided_by_id == "person-001"

    def test_empty_decision_rejected(self):
        with pytest.raises(ValueError, match="decision"):
            _decision(decision="")

    def test_empty_decided_by_rejected(self):
        with pytest.raises(ValueError, match="decided_by_id"):
            _decision(decided_by_id="")

    def test_empty_edge_id_rejected(self):
        with pytest.raises(ValueError, match="edge_id"):
            _decision(edge_id="")

    def test_empty_source_rejected(self):
        with pytest.raises(ValueError, match="source_node_id"):
            _decision(source_node_id="")

    def test_empty_target_rejected(self):
        with pytest.raises(ValueError, match="target_node_id"):
            _decision(target_node_id="")

    def test_to_dict(self):
        d = _decision()
        assert d.to_dict()["decided_by_id"] == "person-001"

    def test_frozen(self):
        d = _decision()
        with pytest.raises(AttributeError):
            d.decision = "rejected"


# ========== ObligationLink ==========


class TestObligationLink:
    def test_valid_unfulfilled(self):
        o = _obligation()
        assert o.fulfilled is False
        assert o.deadline is None

    def test_valid_fulfilled(self):
        o = _obligation(fulfilled=True)
        assert o.fulfilled is True

    def test_with_deadline(self):
        o = _obligation(deadline=TS2)
        assert o.deadline == TS2

    def test_invalid_deadline_rejected(self):
        with pytest.raises(ValueError, match="deadline"):
            _obligation(deadline="not-a-date")

    def test_empty_obligation_rejected(self):
        with pytest.raises(ValueError, match="obligation"):
            _obligation(obligation="")

    def test_non_bool_fulfilled_rejected(self):
        with pytest.raises(ValueError, match="fulfilled"):
            _obligation(fulfilled="yes")

    def test_empty_edge_id_rejected(self):
        with pytest.raises(ValueError, match="edge_id"):
            _obligation(edge_id="")

    def test_to_dict(self):
        o = _obligation()
        d = o.to_dict()
        assert d["fulfilled"] is False

    def test_frozen(self):
        o = _obligation()
        with pytest.raises(AttributeError):
            o.fulfilled = True


# ========== StateDelta ==========


class TestStateDelta:
    def test_valid_construction(self):
        sd = _state_delta()
        assert sd.field_name == "status"
        assert sd.old_value == "open"
        assert sd.new_value == "closed"

    def test_empty_delta_id_rejected(self):
        with pytest.raises(ValueError, match="delta_id"):
            _state_delta(delta_id="")

    def test_empty_node_id_rejected(self):
        with pytest.raises(ValueError, match="node_id"):
            _state_delta(node_id="")

    def test_empty_field_name_rejected(self):
        with pytest.raises(ValueError, match="field_name"):
            _state_delta(field_name="")

    def test_non_string_old_value_rejected(self):
        with pytest.raises(ValueError, match="old_value"):
            _state_delta(old_value=42)

    def test_non_string_new_value_rejected(self):
        with pytest.raises(ValueError, match="new_value"):
            _state_delta(new_value=42)

    def test_empty_old_value_accepted(self):
        sd = _state_delta(old_value="")
        assert sd.old_value == ""

    def test_empty_new_value_accepted(self):
        sd = _state_delta(new_value="")
        assert sd.new_value == ""

    def test_invalid_changed_at_rejected(self):
        with pytest.raises(ValueError, match="changed_at"):
            _state_delta(changed_at="bad")

    def test_to_dict(self):
        sd = _state_delta()
        d = sd.to_dict()
        assert d["field_name"] == "status"

    def test_frozen(self):
        sd = _state_delta()
        with pytest.raises(AttributeError):
            sd.new_value = "other"


# ========== CausalPath ==========


class TestCausalPath:
    def test_valid_construction(self):
        cp = _causal_path()
        assert cp.node_ids == ("node-001", "node-002")
        assert cp.edge_ids == ("edge-001",)

    def test_empty_path_id_rejected(self):
        with pytest.raises(ValueError, match="path_id"):
            _causal_path(path_id="")

    def test_empty_node_ids_rejected(self):
        with pytest.raises(ValueError, match="node_ids"):
            _causal_path(node_ids=())

    def test_empty_edge_ids_rejected(self):
        with pytest.raises(ValueError, match="edge_ids"):
            _causal_path(edge_ids=())

    def test_empty_description_rejected(self):
        with pytest.raises(ValueError, match="description"):
            _causal_path(description="")

    def test_list_coerced_to_tuple(self):
        cp = _causal_path(node_ids=["a", "b"], edge_ids=["e1"])
        assert isinstance(cp.node_ids, tuple)
        assert isinstance(cp.edge_ids, tuple)

    def test_to_dict(self):
        cp = _causal_path()
        d = cp.to_dict()
        assert isinstance(d["node_ids"], list)

    def test_frozen(self):
        cp = _causal_path()
        with pytest.raises(AttributeError):
            cp.path_id = "changed"


# ========== GraphSnapshot ==========


class TestGraphSnapshot:
    def test_valid_construction(self):
        gs = _snapshot()
        assert gs.node_count == 10
        assert gs.edge_count == 15

    def test_zero_counts(self):
        gs = _snapshot(node_count=0, edge_count=0)
        assert gs.node_count == 0
        assert gs.edge_count == 0

    def test_negative_node_count_rejected(self):
        with pytest.raises(ValueError, match="node_count"):
            _snapshot(node_count=-1)

    def test_negative_edge_count_rejected(self):
        with pytest.raises(ValueError, match="edge_count"):
            _snapshot(edge_count=-1)

    def test_float_node_count_rejected(self):
        with pytest.raises(ValueError, match="node_count"):
            _snapshot(node_count=1.5)

    def test_float_edge_count_rejected(self):
        with pytest.raises(ValueError, match="edge_count"):
            _snapshot(edge_count=2.5)

    def test_empty_snapshot_id_rejected(self):
        with pytest.raises(ValueError, match="snapshot_id"):
            _snapshot(snapshot_id="")

    def test_invalid_captured_at_rejected(self):
        with pytest.raises(ValueError, match="captured_at"):
            _snapshot(captured_at="bad")

    def test_to_dict(self):
        gs = _snapshot()
        d = gs.to_dict()
        assert d["node_count"] == 10

    def test_frozen(self):
        gs = _snapshot()
        with pytest.raises(AttributeError):
            gs.node_count = 99


# ========== GraphQueryResult ==========


class TestGraphQueryResult:
    def test_valid_empty_result(self):
        qr = _query_result()
        assert qr.matched_nodes == ()
        assert qr.matched_edges == ()

    def test_with_nodes_and_edges(self):
        n = _node()
        e = _edge()
        qr = _query_result(matched_nodes=(n,), matched_edges=(e,))
        assert len(qr.matched_nodes) == 1
        assert len(qr.matched_edges) == 1

    def test_empty_query_id_rejected(self):
        with pytest.raises(ValueError, match="query_id"):
            _query_result(query_id="")

    def test_invalid_executed_at_rejected(self):
        with pytest.raises(ValueError, match="executed_at"):
            _query_result(executed_at="bad")

    def test_list_coerced_to_tuple(self):
        qr = _query_result(matched_nodes=[], matched_edges=[])
        assert isinstance(qr.matched_nodes, tuple)
        assert isinstance(qr.matched_edges, tuple)

    def test_to_dict(self):
        qr = _query_result()
        d = qr.to_dict()
        assert d["query_id"] == "q-001"

    def test_frozen(self):
        qr = _query_result()
        with pytest.raises(AttributeError):
            qr.query_id = "changed"


# ========== Serialization round-trips ==========


class TestSerialization:
    def test_node_json_round_trip(self):
        n = _node(metadata={"k": [1, 2]})
        j = n.to_json()
        assert '"node_id":"node-001"' in j
        assert '"k":[1,2]' in j

    def test_edge_json_round_trip(self):
        e = _edge(metadata={"reason": "test"})
        j = e.to_json()
        assert '"source_node_id":"node-001"' in j

    def test_evidence_json_round_trip(self):
        ev = _evidence()
        j = ev.to_json()
        assert '"confidence":0.85' in j

    def test_obligation_json_with_deadline(self):
        o = _obligation(deadline=TS2)
        j = o.to_json()
        assert TS2 in j

    def test_snapshot_json(self):
        gs = _snapshot()
        j = gs.to_json()
        assert '"node_count":10' in j


# ---------------------------------------------------------------------------
# Audit #10 — element validation in tuples
# ---------------------------------------------------------------------------


class TestGraphQueryResultElementValidation:
    """GraphQueryResult must reject non-OperationalNode/Edge elements."""

    def test_non_node_in_matched_nodes_rejected(self):
        with pytest.raises(ValueError, match="OperationalNode"):
            GraphQueryResult(
                query_id="q-1",
                matched_nodes=("not-a-node",),
                matched_edges=(),
                executed_at=TS,
            )

    def test_non_edge_in_matched_edges_rejected(self):
        with pytest.raises(ValueError, match="OperationalEdge"):
            GraphQueryResult(
                query_id="q-1",
                matched_nodes=(),
                matched_edges=("not-an-edge",),
                executed_at=TS,
            )


class TestCausalPathElementValidation:
    """CausalPath must reject empty-string IDs in node_ids and edge_ids."""

    def test_empty_node_id_rejected(self):
        with pytest.raises((ValueError, TypeError)):
            CausalPath(
                path_id="p-1",
                node_ids=("n1", ""),
                edge_ids=("e1",),
                description="test path",
            )

    def test_empty_edge_id_rejected(self):
        with pytest.raises((ValueError, TypeError)):
            CausalPath(
                path_id="p-1",
                node_ids=("n1",),
                edge_ids=("",),
                description="test path",
            )
