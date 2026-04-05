"""Integration tests for MemoryMeshIntegration bridge."""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.memory_mesh import (
    MemoryScope,
    MemoryTrustLevel,
    MemoryType,
)
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine
from mcoi_runtime.core.memory_mesh_integration import MemoryMeshIntegration
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


class TestMemoryMeshIntegration:
    def _make(self) -> tuple[MemoryMeshEngine, MemoryMeshIntegration]:
        engine = MemoryMeshEngine()
        bridge = MemoryMeshIntegration(engine)
        return engine, bridge

    def test_invalid_engine_rejected(self):
        with pytest.raises(RuntimeCoreInvariantError):
            MemoryMeshIntegration("not an engine")

    # -- remember_event --

    def test_remember_event(self):
        engine, bridge = self._make()
        rec = bridge.remember_event(
            event_id="evt-1",
            event_type="order_placed",
            scope=MemoryScope.DOMAIN,
            scope_ref_id="domain-1",
            content={"order_id": "ord-1"},
        )
        assert rec.memory_type == MemoryType.OBSERVATION
        assert engine.memory_count == 1

    def test_remember_event_custom_trust(self):
        _, bridge = self._make()
        rec = bridge.remember_event(
            event_id="evt-2",
            event_type="test",
            scope=MemoryScope.GLOBAL,
            scope_ref_id="global",
            content={},
            trust_level=MemoryTrustLevel.OPERATOR_CONFIRMED,
            confidence=0.95,
        )
        assert rec.trust_level == MemoryTrustLevel.OPERATOR_CONFIRMED
        assert rec.confidence == 0.95

    # -- remember_obligation --

    def test_remember_obligation(self):
        engine, bridge = self._make()
        rec = bridge.remember_obligation(
            obligation_id="obl-1",
            state="created",
            scope=MemoryScope.FUNCTION,
            scope_ref_id="fn-1",
            content={"type": "followup"},
        )
        assert rec.memory_type == MemoryType.DECISION
        assert rec.trust_level == MemoryTrustLevel.VERIFIED
        assert engine.memory_count == 1

    # -- remember_job --

    def test_remember_job(self):
        engine, bridge = self._make()
        rec = bridge.remember_job(
            job_id="job-1",
            job_state="completed",
            scope=MemoryScope.TEAM,
            scope_ref_id="team-1",
            content={"result": "success"},
        )
        assert rec.memory_type == MemoryType.EPISODIC
        assert engine.memory_count == 1

    # -- remember_workflow --

    def test_remember_workflow(self):
        engine, bridge = self._make()
        rec = bridge.remember_workflow(
            workflow_id="wfl-1",
            stage="validation",
            scope=MemoryScope.WORKFLOW,
            scope_ref_id="wfl-1",
            content={"stage": "validation"},
        )
        assert rec.memory_type == MemoryType.PROCEDURAL
        assert engine.memory_count == 1

    # -- remember_simulation --

    def test_remember_simulation(self):
        engine, bridge = self._make()
        rec = bridge.remember_simulation(
            simulation_id="sim-1",
            verdict="proceed",
            scope=MemoryScope.GOAL,
            scope_ref_id="goal-1",
            content={"risk": "low"},
        )
        assert rec.memory_type == MemoryType.OUTCOME
        assert rec.trust_level == MemoryTrustLevel.DERIVED
        assert engine.memory_count == 1

    # -- remember_utility --

    def test_remember_utility(self):
        engine, bridge = self._make()
        rec = bridge.remember_utility(
            decision_id="dec-1",
            chosen_option="option_a",
            scope=MemoryScope.FUNCTION,
            scope_ref_id="fn-1",
            content={"utility": 0.8},
        )
        assert rec.memory_type == MemoryType.DECISION
        assert engine.memory_count == 1

    # -- remember_meta_snapshot --

    def test_remember_meta_snapshot(self):
        engine, bridge = self._make()
        rec = bridge.remember_meta_snapshot(
            snapshot_id="snap-1",
            scope=MemoryScope.GLOBAL,
            scope_ref_id="runtime",
            content={"health": "ok"},
        )
        assert rec.memory_type == MemoryType.STRATEGIC
        assert engine.memory_count == 1

    # -- remember_operator_override --

    def test_remember_operator_override(self):
        engine, bridge = self._make()
        rec = bridge.remember_operator_override(
            override_id="ovr-1",
            action="force_halt",
            scope=MemoryScope.OPERATOR,
            scope_ref_id="op-1",
            content={"reason": "emergency"},
        )
        assert rec.memory_type == MemoryType.COMMUNICATION
        assert rec.trust_level == MemoryTrustLevel.OPERATOR_CONFIRMED
        assert rec.confidence == 1.0
        assert engine.memory_count == 1

    # -- remember_benchmark --

    def test_remember_benchmark(self):
        engine, bridge = self._make()
        rec = bridge.remember_benchmark(
            run_id="bench-1",
            category="adversarial",
            scope=MemoryScope.GLOBAL,
            scope_ref_id="runtime",
            content={"score": 0.95},
        )
        assert rec.memory_type == MemoryType.ARTIFACT
        assert engine.memory_count == 1

    # -- retrieve_for_goal --

    def test_retrieve_for_goal(self):
        engine, bridge = self._make()
        bridge.remember_event(
            event_id="e1", event_type="test",
            scope=MemoryScope.GOAL, scope_ref_id="g1",
            content={},
        )
        bridge.remember_event(
            event_id="e2", event_type="test",
            scope=MemoryScope.WORKFLOW, scope_ref_id="w1",
            content={},
        )
        result = bridge.retrieve_for_goal("g1")
        assert result.total == 1

    # -- retrieve_for_workflow --

    def test_retrieve_for_workflow(self):
        engine, bridge = self._make()
        bridge.remember_workflow(
            workflow_id="wfl-1", stage="init",
            scope=MemoryScope.WORKFLOW, scope_ref_id="wfl-1",
            content={},
        )
        result = bridge.retrieve_for_workflow("wfl-1")
        assert result.total == 1

    # -- retrieve_for_recovery --

    def test_retrieve_for_recovery(self):
        engine, bridge = self._make()
        # Add incident-type memory directly
        from mcoi_runtime.contracts.memory_mesh import MemoryRecord
        engine.add_memory(MemoryRecord(
            memory_id="inc-1",
            memory_type=MemoryType.INCIDENT,
            scope=MemoryScope.GLOBAL,
            scope_ref_id="runtime",
            trust_level=MemoryTrustLevel.VERIFIED,
            title="Incident",
            content={"error": "timeout"},
            source_ids=("src-1",),
            confidence=0.9,
            created_at="2026-03-20T12:00:00+00:00",
            updated_at="2026-03-20T12:00:00+00:00",
        ))
        # Add non-matching type
        bridge.remember_event(
            event_id="e1", event_type="test",
            scope=MemoryScope.GLOBAL, scope_ref_id="runtime",
            content={},
        )
        result = bridge.retrieve_for_recovery()
        assert result.total == 1

    # -- retrieve_for_provider_routing --

    def test_retrieve_for_provider_routing(self):
        engine, bridge = self._make()
        bridge.remember_event(
            event_id="e1", event_type="provider_result",
            scope=MemoryScope.PROVIDER, scope_ref_id="prov-1",
            content={"latency_ms": 120},
        )
        result = bridge.retrieve_for_provider_routing("prov-1")
        assert result.total == 1

    # -- retrieve_for_supervisor_tick --

    def test_retrieve_for_supervisor_tick(self):
        engine, bridge = self._make()
        bridge.remember_meta_snapshot(
            snapshot_id="snap-1",
            scope=MemoryScope.GLOBAL,
            scope_ref_id="runtime",
            content={"tick": 42},
        )
        bridge.remember_event(
            event_id="e1", event_type="noise",
            scope=MemoryScope.GLOBAL, scope_ref_id="runtime",
            content={},
        )
        result = bridge.retrieve_for_supervisor_tick(42)
        # Strategic type matches
        assert result.total == 1

    # -- tags flow through --

    def test_tags_preserved(self):
        _, bridge = self._make()
        rec = bridge.remember_event(
            event_id="e1", event_type="test",
            scope=MemoryScope.GLOBAL, scope_ref_id="global",
            content={}, tags=("crm", "sales"),
        )
        assert "crm" in rec.tags
        assert "sales" in rec.tags

    # -- multiple records unique ids --

    def test_multiple_records_unique_ids(self):
        engine, bridge = self._make()
        r1 = bridge.remember_event(
            event_id="e1", event_type="a",
            scope=MemoryScope.GLOBAL, scope_ref_id="g",
            content={},
        )
        r2 = bridge.remember_event(
            event_id="e2", event_type="b",
            scope=MemoryScope.GLOBAL, scope_ref_id="g",
            content={},
        )
        assert r1.memory_id != r2.memory_id
        assert engine.memory_count == 2


class TestBoundedContracts:
    def _make(self) -> MemoryMeshIntegration:
        return MemoryMeshIntegration(MemoryMeshEngine())

    def test_event_title_redacts_event_type(self):
        bridge = self._make()
        rec = bridge.remember_event(
            event_id="evt-secret",
            event_type="operator.secret.event",
            scope=MemoryScope.DOMAIN,
            scope_ref_id="domain-1",
            content={},
        )
        assert rec.title == "Event"
        assert "operator.secret.event" not in rec.title

    def test_obligation_title_redacts_state(self):
        bridge = self._make()
        rec = bridge.remember_obligation(
            obligation_id="obl-secret",
            state="escalated-secret",
            scope=MemoryScope.FUNCTION,
            scope_ref_id="fn-1",
            content={},
        )
        assert rec.title == "Obligation state"
        assert "escalated-secret" not in rec.title

    def test_job_title_redacts_state(self):
        bridge = self._make()
        rec = bridge.remember_job(
            job_id="job-secret",
            job_state="halted-secret",
            scope=MemoryScope.TEAM,
            scope_ref_id="team-1",
            content={},
        )
        assert rec.title == "Job state"
        assert "halted-secret" not in rec.title

    def test_workflow_title_redacts_stage(self):
        bridge = self._make()
        rec = bridge.remember_workflow(
            workflow_id="wfl-secret",
            stage="stage-secret",
            scope=MemoryScope.WORKFLOW,
            scope_ref_id="wfl-1",
            content={},
        )
        assert rec.title == "Workflow stage"
        assert "stage-secret" not in rec.title

    def test_simulation_title_redacts_verdict(self):
        bridge = self._make()
        rec = bridge.remember_simulation(
            simulation_id="sim-secret",
            verdict="reject-secret",
            scope=MemoryScope.GOAL,
            scope_ref_id="goal-1",
            content={},
        )
        assert rec.title == "Simulation outcome"
        assert "reject-secret" not in rec.title

    def test_utility_title_redacts_option(self):
        bridge = self._make()
        rec = bridge.remember_utility(
            decision_id="dec-secret",
            chosen_option="option-secret",
            scope=MemoryScope.FUNCTION,
            scope_ref_id="fn-1",
            content={},
        )
        assert rec.title == "Utility decision"
        assert "option-secret" not in rec.title

    def test_meta_snapshot_title_redacts_snapshot_id(self):
        bridge = self._make()
        rec = bridge.remember_meta_snapshot(
            snapshot_id="snap-secret",
            scope=MemoryScope.GLOBAL,
            scope_ref_id="runtime",
            content={},
        )
        assert rec.title == "Meta snapshot"
        assert "snap-secret" not in rec.title

    def test_operator_override_title_redacts_action(self):
        bridge = self._make()
        rec = bridge.remember_operator_override(
            override_id="ovr-secret",
            action="force-secret",
            scope=MemoryScope.OPERATOR,
            scope_ref_id="op-1",
            content={},
        )
        assert rec.title == "Operator override"
        assert "force-secret" not in rec.title

    def test_benchmark_title_redacts_category(self):
        bridge = self._make()
        rec = bridge.remember_benchmark(
            run_id="bench-secret",
            category="category-secret",
            scope=MemoryScope.GLOBAL,
            scope_ref_id="runtime",
            content={},
        )
        assert rec.title == "Benchmark"
        assert "category-secret" not in rec.title
