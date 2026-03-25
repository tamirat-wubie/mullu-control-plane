"""Smoke tests for Phase 109: Causal / Counterfactual Runtime.

Covers: contracts, engine lifecycle, edge validation, interventions,
counterfactual scenarios, BFS propagation, attribution, violation detection,
assessment, snapshot, closure report, integration bridge, memory mesh, and graph.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.engine_protocol import FixedClock
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine
from mcoi_runtime.core.causal_runtime import CausalRuntimeEngine
from mcoi_runtime.core.causal_runtime_integration import CausalRuntimeIntegration
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.contracts.causal_runtime import (
    AttributionStrength,
    CausalAssessment,
    CausalAttribution,
    CausalClosureReport,
    CausalDecision,
    CausalEdge,
    CausalEdgeKind,
    CausalNode,
    CausalRiskLevel,
    CausalSnapshot,
    CausalStatus,
    CounterfactualScenario,
    CounterfactualStatus,
    InterventionDisposition,
    InterventionRecord,
    PropagationRecord,
)


# =====================================================================
# Fixtures
# =====================================================================

TS = "2026-01-01T00:00:00+00:00"


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(TS)


@pytest.fixture
def spine() -> EventSpineEngine:
    return EventSpineEngine()


@pytest.fixture
def engine(spine: EventSpineEngine, clock: FixedClock) -> CausalRuntimeEngine:
    return CausalRuntimeEngine(spine, clock=clock)


@pytest.fixture
def memory() -> MemoryMeshEngine:
    return MemoryMeshEngine()


# =====================================================================
# 1. Contract smoke tests
# =====================================================================


class TestContracts:
    def test_causal_node_valid(self):
        n = CausalNode(
            node_id="n1", tenant_id="t1", display_name="Temperature",
            status=CausalStatus.ACTIVE, created_at=TS,
        )
        assert n.node_id == "n1"

    def test_causal_node_empty_id_raises(self):
        with pytest.raises(ValueError):
            CausalNode(
                node_id="", tenant_id="t1", display_name="X", created_at=TS,
            )

    def test_causal_edge_valid(self):
        e = CausalEdge(
            edge_id="e1", tenant_id="t1", cause_ref="n1", effect_ref="n2",
            kind=CausalEdgeKind.DIRECT, strength=AttributionStrength.STRONG,
            created_at=TS,
        )
        assert e.kind == CausalEdgeKind.DIRECT

    def test_intervention_valid(self):
        i = InterventionRecord(
            intervention_id="i1", tenant_id="t1", target_node_ref="n1",
            disposition=InterventionDisposition.PROPOSED,
            expected_effect="reduce temperature", created_at=TS,
        )
        assert i.disposition == InterventionDisposition.PROPOSED

    def test_counterfactual_valid(self):
        cf = CounterfactualScenario(
            scenario_id="cf1", tenant_id="t1", intervention_ref="i1",
            premise="What if temperature lowered?",
            status=CounterfactualStatus.PENDING, created_at=TS,
        )
        assert cf.status == CounterfactualStatus.PENDING

    def test_attribution_valid(self):
        a = CausalAttribution(
            attribution_id="a1", tenant_id="t1", outcome_ref="n2", cause_ref="n1",
            strength=AttributionStrength.MODERATE, evidence_count=3, created_at=TS,
        )
        assert a.evidence_count == 3

    def test_propagation_valid(self):
        p = PropagationRecord(
            propagation_id="p1", tenant_id="t1", source_ref="n1", target_ref="n3",
            hop_count=2, created_at=TS,
        )
        assert p.hop_count == 2

    def test_causal_decision_valid(self):
        d = CausalDecision(
            decision_id="d1", tenant_id="t1", attribution_ref="a1",
            disposition="accepted", reason="strong evidence", decided_at=TS,
        )
        assert d.disposition == "accepted"

    def test_causal_assessment_valid(self):
        a = CausalAssessment(
            assessment_id="ca1", tenant_id="t1",
            total_nodes=5, total_edges=4, total_interventions=2,
            attribution_coverage=0.8, assessed_at=TS,
        )
        assert a.attribution_coverage == 0.8

    def test_causal_snapshot_valid(self):
        s = CausalSnapshot(
            snapshot_id="cs1", tenant_id="t1",
            total_nodes=5, total_edges=4, total_interventions=2,
            total_counterfactuals=1, total_attributions=3, total_violations=0,
            captured_at=TS,
        )
        assert s.total_counterfactuals == 1

    def test_causal_closure_report_valid(self):
        r = CausalClosureReport(
            report_id="ccr1", tenant_id="t1",
            total_nodes=5, total_edges=4, total_interventions=2,
            total_attributions=3, total_violations=0, created_at=TS,
        )
        assert r.total_attributions == 3

    def test_all_enums_have_correct_counts(self):
        assert len(CausalStatus) == 4
        assert len(CausalEdgeKind) == 5
        assert len(InterventionDisposition) == 4
        assert len(CounterfactualStatus) == 4
        assert len(AttributionStrength) == 4
        assert len(CausalRiskLevel) == 4

    def test_to_dict_roundtrip(self):
        n = CausalNode(
            node_id="n1", tenant_id="t1", display_name="X",
            created_at=TS,
        )
        d = n.to_dict()
        assert d["node_id"] == "n1"

    def test_to_json_dict(self):
        n = CausalNode(
            node_id="n1", tenant_id="t1", display_name="X",
            created_at=TS,
        )
        d = n.to_json_dict()
        assert d["status"] == "active"


# =====================================================================
# 2. Engine constructor
# =====================================================================


class TestEngineConstructor:
    def test_valid(self, spine, clock):
        eng = CausalRuntimeEngine(spine, clock=clock)
        assert eng.node_count == 0

    def test_none_raises(self):
        with pytest.raises(RuntimeCoreInvariantError):
            CausalRuntimeEngine(None)

    def test_string_raises(self):
        with pytest.raises(RuntimeCoreInvariantError):
            CausalRuntimeEngine("bad")


# =====================================================================
# 3. Engine lifecycle
# =====================================================================


class TestEngineLifecycle:
    def test_register_node(self, engine):
        node = engine.register_causal_node("n1", "t1", "Temperature")
        assert node.display_name == "Temperature"
        assert engine.node_count == 1

    def test_duplicate_node_raises(self, engine):
        engine.register_causal_node("n1", "t1", "Temperature")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.register_causal_node("n1", "t1", "Temperature")

    def test_register_edge(self, engine):
        engine.register_causal_node("n1", "t1", "Cause")
        engine.register_causal_node("n2", "t1", "Effect")
        edge = engine.register_causal_edge("e1", "t1", "n1", "n2")
        assert edge.cause_ref == "n1"
        assert engine.edge_count == 1

    def test_edge_missing_cause_raises(self, engine):
        engine.register_causal_node("n2", "t1", "Effect")
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown cause"):
            engine.register_causal_edge("e1", "t1", "n1", "n2")

    def test_edge_missing_effect_raises(self, engine):
        engine.register_causal_node("n1", "t1", "Cause")
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown effect"):
            engine.register_causal_edge("e1", "t1", "n1", "n2")

    def test_register_intervention(self, engine):
        intv = engine.register_intervention("i1", "t1", "n1", "reduce noise")
        assert intv.disposition == InterventionDisposition.PROPOSED
        assert engine.intervention_count == 1

    def test_run_counterfactual(self, engine):
        engine.register_intervention("i1", "t1", "n1", "reduce noise")
        cf = engine.run_counterfactual("cf1", "t1", "i1", "What if no noise?")
        assert cf.status == CounterfactualStatus.EVALUATED
        assert engine.counterfactual_count == 1

    def test_confirm_counterfactual(self, engine):
        engine.register_intervention("i1", "t1", "n1", "reduce noise")
        engine.run_counterfactual("cf1", "t1", "i1", "What if no noise?")
        confirmed = engine.confirm_counterfactual("cf1")
        assert confirmed.status == CounterfactualStatus.CONFIRMED

    def test_reject_counterfactual(self, engine):
        engine.register_intervention("i1", "t1", "n1", "reduce noise")
        engine.run_counterfactual("cf1", "t1", "i1", "What if no noise?")
        rejected = engine.reject_counterfactual("cf1")
        assert rejected.status == CounterfactualStatus.REJECTED

    def test_trace_propagation_bfs(self, engine):
        engine.register_causal_node("n1", "t1", "Root")
        engine.register_causal_node("n2", "t1", "Mid")
        engine.register_causal_node("n3", "t1", "Leaf")
        engine.register_causal_edge("e1", "t1", "n1", "n2")
        engine.register_causal_edge("e2", "t1", "n2", "n3")
        records = engine.trace_propagation("t1", "n1")
        assert len(records) == 2
        hops = sorted([r.hop_count for r in records])
        assert hops == [1, 2]
        assert engine.propagation_count == 2

    def test_trace_propagation_no_edges(self, engine):
        engine.register_causal_node("n1", "t1", "Isolated")
        records = engine.trace_propagation("t1", "n1")
        assert len(records) == 0

    def test_attribute_outcome(self, engine):
        attr = engine.attribute_outcome("a1", "t1", "outcome-1", "cause-1", AttributionStrength.STRONG, 5)
        assert attr.strength == AttributionStrength.STRONG
        assert engine.attribution_count == 1

    def test_causal_assessment(self, engine):
        engine.register_causal_node("n1", "t1", "Node")
        asm = engine.causal_assessment("ca1", "t1")
        assert asm.total_nodes == 1
        assert asm.attribution_coverage == 0.0

    def test_causal_snapshot(self, engine):
        engine.register_causal_node("n1", "t1", "Node")
        snap = engine.causal_snapshot("cs1", "t1")
        assert snap.total_nodes == 1

    def test_causal_closure_report(self, engine):
        engine.register_causal_node("n1", "t1", "Node")
        report = engine.causal_closure_report("ccr1", "t1")
        assert report.total_nodes == 1


# =====================================================================
# 4. Violation detection
# =====================================================================


class TestViolationDetection:
    def test_unresolved_intervention(self, engine):
        engine.register_intervention("i1", "t1", "n1", "effect")
        viols = engine.detect_causal_violations("t1")
        ops = [v["operation"] for v in viols]
        assert "unresolved_intervention" in ops

    def test_violations_idempotent(self, engine):
        engine.register_intervention("i1", "t1", "n1", "effect")
        engine.detect_causal_violations("t1")
        viols2 = engine.detect_causal_violations("t1")
        assert len(viols2) == 0

    def test_no_cycle_no_violation(self, engine):
        engine.register_causal_node("n1", "t1", "A")
        engine.register_causal_node("n2", "t1", "B")
        engine.register_causal_edge("e1", "t1", "n1", "n2")
        viols = engine.detect_causal_violations("t1")
        ops = [v["operation"] for v in viols]
        assert "cycle_in_graph" not in ops


# =====================================================================
# 5. State hash & snapshot
# =====================================================================


class TestStateHash:
    def test_hash_is_64_hex(self, engine):
        h = engine.state_hash()
        assert len(h) == 64
        int(h, 16)

    def test_hash_changes_on_mutation(self, engine):
        h1 = engine.state_hash()
        engine.register_causal_node("n1", "t1", "Node")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_snapshot_has_hash(self, engine):
        snap = engine.snapshot()
        assert "_state_hash" in snap


# =====================================================================
# 6. Integration bridge
# =====================================================================


class TestIntegration:
    def test_constructor_validation(self, spine, clock, memory):
        eng = CausalRuntimeEngine(spine, clock=clock)
        integ = CausalRuntimeIntegration(eng, spine, memory)
        assert integ is not None

    def test_bad_engine_raises(self, spine, memory):
        with pytest.raises(RuntimeCoreInvariantError):
            CausalRuntimeIntegration("bad", spine, memory)

    def test_causal_from_remediation(self, spine, clock, memory):
        eng = CausalRuntimeEngine(spine, clock=clock)
        integ = CausalRuntimeIntegration(eng, spine, memory)
        result = integ.causal_from_remediation("t1", "rem-ref-1")
        assert result["source_type"] == "remediation"
        assert eng.node_count == 2
        assert eng.edge_count == 1

    def test_causal_from_continuity(self, spine, clock, memory):
        eng = CausalRuntimeEngine(spine, clock=clock)
        integ = CausalRuntimeIntegration(eng, spine, memory)
        result = integ.causal_from_continuity("t1", "cont-ref-1")
        assert result["source_type"] == "continuity"

    def test_causal_from_forecasting(self, spine, clock, memory):
        eng = CausalRuntimeEngine(spine, clock=clock)
        integ = CausalRuntimeIntegration(eng, spine, memory)
        result = integ.causal_from_forecasting("t1", "forecast-ref-1")
        assert result["source_type"] == "forecasting"

    def test_causal_from_observability(self, spine, clock, memory):
        eng = CausalRuntimeEngine(spine, clock=clock)
        integ = CausalRuntimeIntegration(eng, spine, memory)
        result = integ.causal_from_observability("t1", "obs-ref-1")
        assert result["source_type"] == "observability"

    def test_causal_from_executive_control(self, spine, clock, memory):
        eng = CausalRuntimeEngine(spine, clock=clock)
        integ = CausalRuntimeIntegration(eng, spine, memory)
        result = integ.causal_from_executive_control("t1", "ctrl-ref-1")
        assert result["source_type"] == "executive_control"

    def test_causal_from_process_simulation(self, spine, clock, memory):
        eng = CausalRuntimeEngine(spine, clock=clock)
        integ = CausalRuntimeIntegration(eng, spine, memory)
        result = integ.causal_from_process_simulation("t1", "psim-ref-1")
        assert result["source_type"] == "process_simulation"

    def test_attach_to_memory_mesh(self, spine, clock, memory):
        eng = CausalRuntimeEngine(spine, clock=clock)
        integ = CausalRuntimeIntegration(eng, spine, memory)
        rec = integ.attach_causal_state_to_memory_mesh("scope-1")
        assert rec.memory_id
        assert memory.memory_count >= 1

    def test_attach_to_graph(self, spine, clock, memory):
        eng = CausalRuntimeEngine(spine, clock=clock)
        integ = CausalRuntimeIntegration(eng, spine, memory)
        result = integ.attach_causal_state_to_graph("scope-1")
        assert "total_nodes" in result
