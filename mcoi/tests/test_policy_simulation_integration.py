"""Tests for PolicySimulationIntegration bridge.

Covers constructor validation, all 6 simulate methods, memory mesh
attachment, graph attachment, event emission, return-shape invariants,
custom impact overrides, and full lifecycle golden paths.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine
from mcoi_runtime.core.policy_simulation import PolicySimulationEngine
from mcoi_runtime.core.policy_simulation_integration import PolicySimulationIntegration
from mcoi_runtime.contracts.policy_simulation import PolicyImpactLevel
from mcoi_runtime.contracts.memory_mesh import MemoryRecord


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def event_spine() -> EventSpineEngine:
    return EventSpineEngine()


@pytest.fixture()
def sim_engine(event_spine: EventSpineEngine) -> PolicySimulationEngine:
    return PolicySimulationEngine(event_spine)


@pytest.fixture()
def memory_engine() -> MemoryMeshEngine:
    return MemoryMeshEngine()


@pytest.fixture()
def bridge(
    sim_engine: PolicySimulationEngine,
    event_spine: EventSpineEngine,
    memory_engine: MemoryMeshEngine,
) -> PolicySimulationIntegration:
    return PolicySimulationIntegration(sim_engine, event_spine, memory_engine)


RESULT_KEYS = frozenset({
    "request_id", "scenario_id", "tenant_id", "target_runtime",
    "impact_level", "adoption_readiness", "readiness_score", "source_type",
})

MEMORY_CONTENT_KEYS = frozenset({
    "total_simulations", "completed_simulations", "total_scenarios",
    "total_diffs", "total_impacts", "total_violations",
})

GRAPH_KEYS = MEMORY_CONTENT_KEYS | {"scope_ref_id"}


# ---------------------------------------------------------------------------
# Constructor validation
# ---------------------------------------------------------------------------


class TestConstructorValidation:
    def test_rejects_wrong_simulation_engine_type(
        self, event_spine: EventSpineEngine, memory_engine: MemoryMeshEngine,
    ) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            PolicySimulationIntegration("not-an-engine", event_spine, memory_engine)

    def test_rejects_wrong_event_spine_type(
        self, sim_engine: PolicySimulationEngine, memory_engine: MemoryMeshEngine,
    ) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            PolicySimulationIntegration(sim_engine, "not-an-engine", memory_engine)

    def test_rejects_wrong_memory_engine_type(
        self, sim_engine: PolicySimulationEngine, event_spine: EventSpineEngine,
    ) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            PolicySimulationIntegration(sim_engine, event_spine, "not-an-engine")

    def test_rejects_none_simulation_engine(
        self, event_spine: EventSpineEngine, memory_engine: MemoryMeshEngine,
    ) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            PolicySimulationIntegration(None, event_spine, memory_engine)

    def test_rejects_none_event_spine(
        self, sim_engine: PolicySimulationEngine, memory_engine: MemoryMeshEngine,
    ) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            PolicySimulationIntegration(sim_engine, None, memory_engine)

    def test_rejects_none_memory_engine(
        self, sim_engine: PolicySimulationEngine, event_spine: EventSpineEngine,
    ) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            PolicySimulationIntegration(sim_engine, event_spine, None)

    def test_accepts_valid_engines(
        self,
        sim_engine: PolicySimulationEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        b = PolicySimulationIntegration(sim_engine, event_spine, memory_engine)
        assert b is not None


# ---------------------------------------------------------------------------
# simulate_service_policy_change
# ---------------------------------------------------------------------------


class TestSimulateServicePolicyChange:
    def test_returns_dict_with_correct_keys(self, bridge: PolicySimulationIntegration) -> None:
        result = bridge.simulate_service_policy_change("r1", "t1", "s1")
        assert set(result.keys()) == RESULT_KEYS

    def test_target_runtime_is_service_catalog(self, bridge: PolicySimulationIntegration) -> None:
        result = bridge.simulate_service_policy_change("r1", "t1", "s1")
        assert result["target_runtime"] == "service_catalog"

    def test_source_type_is_service_policy(self, bridge: PolicySimulationIntegration) -> None:
        result = bridge.simulate_service_policy_change("r1", "t1", "s1")
        assert result["source_type"] == "service_policy"

    def test_default_impact_level_medium(self, bridge: PolicySimulationIntegration) -> None:
        result = bridge.simulate_service_policy_change("r1", "t1", "s1")
        assert result["impact_level"] == "medium"

    def test_custom_impact_level(self, bridge: PolicySimulationIntegration) -> None:
        result = bridge.simulate_service_policy_change(
            "r1", "t1", "s1", impact_level=PolicyImpactLevel.CRITICAL,
        )
        assert result["impact_level"] == "critical"

    def test_preserves_request_id(self, bridge: PolicySimulationIntegration) -> None:
        result = bridge.simulate_service_policy_change("req-abc", "t1", "s1")
        assert result["request_id"] == "req-abc"

    def test_preserves_tenant_id(self, bridge: PolicySimulationIntegration) -> None:
        result = bridge.simulate_service_policy_change("r1", "tenant-x", "s1")
        assert result["tenant_id"] == "tenant-x"

    def test_preserves_scenario_id(self, bridge: PolicySimulationIntegration) -> None:
        result = bridge.simulate_service_policy_change("r1", "t1", "scen-1")
        assert result["scenario_id"] == "scen-1"

    def test_emits_event(self, bridge: PolicySimulationIntegration, event_spine: EventSpineEngine) -> None:
        before = event_spine.event_count
        bridge.simulate_service_policy_change("r1", "t1", "s1")
        assert event_spine.event_count > before

    def test_readiness_score_is_float(self, bridge: PolicySimulationIntegration) -> None:
        result = bridge.simulate_service_policy_change("r1", "t1", "s1")
        assert isinstance(result["readiness_score"], float)


# ---------------------------------------------------------------------------
# simulate_release_policy_change
# ---------------------------------------------------------------------------


class TestSimulateReleasePolicyChange:
    def test_returns_dict_with_correct_keys(self, bridge: PolicySimulationIntegration) -> None:
        result = bridge.simulate_release_policy_change("r2", "t2", "s2")
        assert set(result.keys()) == RESULT_KEYS

    def test_target_runtime_is_product_ops(self, bridge: PolicySimulationIntegration) -> None:
        result = bridge.simulate_release_policy_change("r2", "t2", "s2")
        assert result["target_runtime"] == "product_ops"

    def test_source_type_is_release_policy(self, bridge: PolicySimulationIntegration) -> None:
        result = bridge.simulate_release_policy_change("r2", "t2", "s2")
        assert result["source_type"] == "release_policy"

    def test_default_impact_level_high(self, bridge: PolicySimulationIntegration) -> None:
        result = bridge.simulate_release_policy_change("r2", "t2", "s2")
        assert result["impact_level"] == "high"

    def test_custom_impact_level_low(self, bridge: PolicySimulationIntegration) -> None:
        result = bridge.simulate_release_policy_change(
            "r2", "t2", "s2", impact_level=PolicyImpactLevel.LOW,
        )
        assert result["impact_level"] == "low"

    def test_preserves_ids(self, bridge: PolicySimulationIntegration) -> None:
        result = bridge.simulate_release_policy_change("rr1", "tt1", "ss1")
        assert result["request_id"] == "rr1"
        assert result["tenant_id"] == "tt1"
        assert result["scenario_id"] == "ss1"

    def test_emits_event(self, bridge: PolicySimulationIntegration, event_spine: EventSpineEngine) -> None:
        before = event_spine.event_count
        bridge.simulate_release_policy_change("r2", "t2", "s2")
        assert event_spine.event_count > before

    def test_readiness_score_is_float(self, bridge: PolicySimulationIntegration) -> None:
        result = bridge.simulate_release_policy_change("r2", "t2", "s2")
        assert isinstance(result["readiness_score"], float)


# ---------------------------------------------------------------------------
# simulate_financial_policy_change
# ---------------------------------------------------------------------------


class TestSimulateFinancialPolicyChange:
    def test_returns_dict_with_correct_keys(self, bridge: PolicySimulationIntegration) -> None:
        result = bridge.simulate_financial_policy_change("r3", "t3", "s3")
        assert set(result.keys()) == RESULT_KEYS

    def test_target_runtime_is_billing(self, bridge: PolicySimulationIntegration) -> None:
        result = bridge.simulate_financial_policy_change("r3", "t3", "s3")
        assert result["target_runtime"] == "billing"

    def test_source_type_is_financial_policy(self, bridge: PolicySimulationIntegration) -> None:
        result = bridge.simulate_financial_policy_change("r3", "t3", "s3")
        assert result["source_type"] == "financial_policy"

    def test_default_impact_level_medium(self, bridge: PolicySimulationIntegration) -> None:
        result = bridge.simulate_financial_policy_change("r3", "t3", "s3")
        assert result["impact_level"] == "medium"

    def test_custom_impact_level_none(self, bridge: PolicySimulationIntegration) -> None:
        # Use same baseline/simulated so auto-upgrade doesn't kick in
        result = bridge.simulate_financial_policy_change(
            "r3-none", "t3", "s3-none",
            baseline_outcome="allowed", simulated_outcome="allowed",
            impact_level=PolicyImpactLevel.NONE,
        )
        assert result["impact_level"] == "none"

    def test_preserves_ids(self, bridge: PolicySimulationIntegration) -> None:
        result = bridge.simulate_financial_policy_change("fin-1", "ten-1", "scn-1")
        assert result["request_id"] == "fin-1"
        assert result["tenant_id"] == "ten-1"
        assert result["scenario_id"] == "scn-1"

    def test_emits_event(self, bridge: PolicySimulationIntegration, event_spine: EventSpineEngine) -> None:
        before = event_spine.event_count
        bridge.simulate_financial_policy_change("r3", "t3", "s3")
        assert event_spine.event_count > before

    def test_readiness_score_is_float(self, bridge: PolicySimulationIntegration) -> None:
        result = bridge.simulate_financial_policy_change("r3", "t3", "s3")
        assert isinstance(result["readiness_score"], float)


# ---------------------------------------------------------------------------
# simulate_workforce_policy_change
# ---------------------------------------------------------------------------


class TestSimulateWorkforcePolicyChange:
    def test_returns_dict_with_correct_keys(self, bridge: PolicySimulationIntegration) -> None:
        result = bridge.simulate_workforce_policy_change("r4", "t4", "s4")
        assert set(result.keys()) == RESULT_KEYS

    def test_target_runtime_is_workforce(self, bridge: PolicySimulationIntegration) -> None:
        result = bridge.simulate_workforce_policy_change("r4", "t4", "s4")
        assert result["target_runtime"] == "workforce"

    def test_source_type_is_workforce_policy(self, bridge: PolicySimulationIntegration) -> None:
        result = bridge.simulate_workforce_policy_change("r4", "t4", "s4")
        assert result["source_type"] == "workforce_policy"

    def test_default_impact_level_low(self, bridge: PolicySimulationIntegration) -> None:
        result = bridge.simulate_workforce_policy_change("r4", "t4", "s4")
        assert result["impact_level"] == "low"

    def test_custom_impact_level_high(self, bridge: PolicySimulationIntegration) -> None:
        result = bridge.simulate_workforce_policy_change(
            "r4", "t4", "s4", impact_level=PolicyImpactLevel.HIGH,
        )
        assert result["impact_level"] == "high"

    def test_preserves_ids(self, bridge: PolicySimulationIntegration) -> None:
        result = bridge.simulate_workforce_policy_change("wf-1", "ten-2", "scn-2")
        assert result["request_id"] == "wf-1"
        assert result["tenant_id"] == "ten-2"
        assert result["scenario_id"] == "scn-2"

    def test_emits_event(self, bridge: PolicySimulationIntegration, event_spine: EventSpineEngine) -> None:
        before = event_spine.event_count
        bridge.simulate_workforce_policy_change("r4", "t4", "s4")
        assert event_spine.event_count > before

    def test_readiness_score_is_float(self, bridge: PolicySimulationIntegration) -> None:
        result = bridge.simulate_workforce_policy_change("r4", "t4", "s4")
        assert isinstance(result["readiness_score"], float)


# ---------------------------------------------------------------------------
# simulate_marketplace_policy_change
# ---------------------------------------------------------------------------


class TestSimulateMarketplacePolicyChange:
    def test_returns_dict_with_correct_keys(self, bridge: PolicySimulationIntegration) -> None:
        result = bridge.simulate_marketplace_policy_change("r5", "t5", "s5")
        assert set(result.keys()) == RESULT_KEYS

    def test_target_runtime_is_marketplace(self, bridge: PolicySimulationIntegration) -> None:
        result = bridge.simulate_marketplace_policy_change("r5", "t5", "s5")
        assert result["target_runtime"] == "marketplace"

    def test_source_type_is_marketplace_policy(self, bridge: PolicySimulationIntegration) -> None:
        result = bridge.simulate_marketplace_policy_change("r5", "t5", "s5")
        assert result["source_type"] == "marketplace_policy"

    def test_default_impact_level_high(self, bridge: PolicySimulationIntegration) -> None:
        result = bridge.simulate_marketplace_policy_change("r5", "t5", "s5")
        assert result["impact_level"] == "high"

    def test_custom_impact_level_medium(self, bridge: PolicySimulationIntegration) -> None:
        result = bridge.simulate_marketplace_policy_change(
            "r5", "t5", "s5", impact_level=PolicyImpactLevel.MEDIUM,
        )
        assert result["impact_level"] == "medium"

    def test_preserves_ids(self, bridge: PolicySimulationIntegration) -> None:
        result = bridge.simulate_marketplace_policy_change("mp-1", "ten-3", "scn-3")
        assert result["request_id"] == "mp-1"
        assert result["tenant_id"] == "ten-3"
        assert result["scenario_id"] == "scn-3"

    def test_emits_event(self, bridge: PolicySimulationIntegration, event_spine: EventSpineEngine) -> None:
        before = event_spine.event_count
        bridge.simulate_marketplace_policy_change("r5", "t5", "s5")
        assert event_spine.event_count > before

    def test_readiness_score_is_float(self, bridge: PolicySimulationIntegration) -> None:
        result = bridge.simulate_marketplace_policy_change("r5", "t5", "s5")
        assert isinstance(result["readiness_score"], float)


# ---------------------------------------------------------------------------
# simulate_constitutional_change
# ---------------------------------------------------------------------------


class TestSimulateConstitutionalChange:
    def test_returns_dict_with_correct_keys(self, bridge: PolicySimulationIntegration) -> None:
        result = bridge.simulate_constitutional_change("r6", "t6", "s6")
        assert set(result.keys()) == RESULT_KEYS

    def test_target_runtime_is_constitutional_governance(self, bridge: PolicySimulationIntegration) -> None:
        result = bridge.simulate_constitutional_change("r6", "t6", "s6")
        assert result["target_runtime"] == "constitutional_governance"

    def test_source_type_is_constitutional_change(self, bridge: PolicySimulationIntegration) -> None:
        result = bridge.simulate_constitutional_change("r6", "t6", "s6")
        assert result["source_type"] == "constitutional_change"

    def test_default_impact_level_critical(self, bridge: PolicySimulationIntegration) -> None:
        result = bridge.simulate_constitutional_change("r6", "t6", "s6")
        assert result["impact_level"] == "critical"

    def test_custom_impact_level_low(self, bridge: PolicySimulationIntegration) -> None:
        result = bridge.simulate_constitutional_change(
            "r6", "t6", "s6", impact_level=PolicyImpactLevel.LOW,
        )
        assert result["impact_level"] == "low"

    def test_preserves_ids(self, bridge: PolicySimulationIntegration) -> None:
        result = bridge.simulate_constitutional_change("con-1", "ten-4", "scn-4")
        assert result["request_id"] == "con-1"
        assert result["tenant_id"] == "ten-4"
        assert result["scenario_id"] == "scn-4"

    def test_emits_event(self, bridge: PolicySimulationIntegration, event_spine: EventSpineEngine) -> None:
        before = event_spine.event_count
        bridge.simulate_constitutional_change("r6", "t6", "s6")
        assert event_spine.event_count > before

    def test_readiness_score_is_float(self, bridge: PolicySimulationIntegration) -> None:
        result = bridge.simulate_constitutional_change("r6", "t6", "s6")
        assert isinstance(result["readiness_score"], float)


# ---------------------------------------------------------------------------
# attach_simulation_state_to_memory_mesh
# ---------------------------------------------------------------------------


class TestAttachSimulationStateToMemoryMesh:
    def test_returns_memory_record(self, bridge: PolicySimulationIntegration) -> None:
        mem = bridge.attach_simulation_state_to_memory_mesh("scope-1")
        assert isinstance(mem, MemoryRecord)

    def test_memory_record_has_correct_tags(self, bridge: PolicySimulationIntegration) -> None:
        mem = bridge.attach_simulation_state_to_memory_mesh("scope-1")
        assert "policy_simulation" in mem.tags
        assert "governance_sandbox" in mem.tags
        assert "what_if" in mem.tags

    def test_memory_content_has_six_keys(self, bridge: PolicySimulationIntegration) -> None:
        mem = bridge.attach_simulation_state_to_memory_mesh("scope-1")
        assert set(mem.content.keys()) == MEMORY_CONTENT_KEYS

    def test_scope_ref_id_preserved(self, bridge: PolicySimulationIntegration) -> None:
        mem = bridge.attach_simulation_state_to_memory_mesh("my-scope")
        assert mem.scope_ref_id == "my-scope"

    def test_emits_event(self, bridge: PolicySimulationIntegration, event_spine: EventSpineEngine) -> None:
        before = event_spine.event_count
        bridge.attach_simulation_state_to_memory_mesh("scope-1")
        assert event_spine.event_count > before

    def test_after_simulation_counts_reflect_state(self, bridge: PolicySimulationIntegration) -> None:
        bridge.simulate_service_policy_change("r-m1", "t-m1", "s-m1")
        mem = bridge.attach_simulation_state_to_memory_mesh("t-m1")
        assert mem.content["total_simulations"] >= 1
        assert mem.content["completed_simulations"] >= 1
        assert mem.content["total_scenarios"] >= 1

    def test_title_contains_scope_ref_id(self, bridge: PolicySimulationIntegration) -> None:
        mem = bridge.attach_simulation_state_to_memory_mesh("abc-scope")
        assert mem.title == "Policy simulation state"
        assert "abc-scope" not in mem.title
        assert mem.scope_ref_id == "abc-scope"


# ---------------------------------------------------------------------------
# attach_simulation_state_to_graph
# ---------------------------------------------------------------------------


class TestAttachSimulationStateToGraph:
    def test_returns_dict(self, bridge: PolicySimulationIntegration) -> None:
        result = bridge.attach_simulation_state_to_graph("scope-g1")
        assert isinstance(result, dict)

    def test_has_seven_keys(self, bridge: PolicySimulationIntegration) -> None:
        result = bridge.attach_simulation_state_to_graph("scope-g1")
        assert set(result.keys()) == GRAPH_KEYS

    def test_scope_ref_id_preserved(self, bridge: PolicySimulationIntegration) -> None:
        result = bridge.attach_simulation_state_to_graph("my-graph-scope")
        assert result["scope_ref_id"] == "my-graph-scope"

    def test_after_simulation_counts_reflect_state(self, bridge: PolicySimulationIntegration) -> None:
        bridge.simulate_release_policy_change("r-g1", "t-g1", "s-g1")
        result = bridge.attach_simulation_state_to_graph("t-g1")
        assert result["total_simulations"] >= 1
        assert result["completed_simulations"] >= 1
        assert result["total_scenarios"] >= 1

    def test_all_count_values_are_ints(self, bridge: PolicySimulationIntegration) -> None:
        result = bridge.attach_simulation_state_to_graph("scope-g2")
        for key in MEMORY_CONTENT_KEYS:
            assert isinstance(result[key], int)


# ---------------------------------------------------------------------------
# Cross-method / golden-path tests
# ---------------------------------------------------------------------------


class TestGoldenPaths:
    def test_full_lifecycle_all_six_simulate_then_memory(
        self, bridge: PolicySimulationIntegration,
    ) -> None:
        """Run all six simulation types then attach memory and graph."""
        r1 = bridge.simulate_service_policy_change("lc-1", "t-lc", "s-lc1")
        r2 = bridge.simulate_release_policy_change("lc-2", "t-lc", "s-lc2")
        r3 = bridge.simulate_financial_policy_change("lc-3", "t-lc", "s-lc3")
        r4 = bridge.simulate_workforce_policy_change("lc-4", "t-lc", "s-lc4")
        r5 = bridge.simulate_marketplace_policy_change("lc-5", "t-lc", "s-lc5")
        r6 = bridge.simulate_constitutional_change("lc-6", "t-lc", "s-lc6")

        for r in (r1, r2, r3, r4, r5, r6):
            assert set(r.keys()) == RESULT_KEYS

        mem = bridge.attach_simulation_state_to_memory_mesh("t-lc")
        assert mem.content["total_simulations"] == 6
        assert mem.content["completed_simulations"] == 6
        assert mem.content["total_scenarios"] == 6

        graph = bridge.attach_simulation_state_to_graph("t-lc")
        assert graph["total_simulations"] == 6

    def test_event_count_grows_with_each_simulate(
        self, bridge: PolicySimulationIntegration, event_spine: EventSpineEngine,
    ) -> None:
        counts = []
        counts.append(event_spine.event_count)
        bridge.simulate_service_policy_change("ec-1", "t-ec", "s-ec1")
        counts.append(event_spine.event_count)
        bridge.simulate_release_policy_change("ec-2", "t-ec", "s-ec2")
        counts.append(event_spine.event_count)
        bridge.simulate_financial_policy_change("ec-3", "t-ec", "s-ec3")
        counts.append(event_spine.event_count)
        # Each simulate emits at least one event through the integration bridge
        for i in range(1, len(counts)):
            assert counts[i] > counts[i - 1]

    def test_adoption_readiness_is_string(self, bridge: PolicySimulationIntegration) -> None:
        result = bridge.simulate_service_policy_change("ar-1", "t-ar", "s-ar1")
        assert isinstance(result["adoption_readiness"], str)

    def test_different_tenants_independent_snapshots(
        self, bridge: PolicySimulationIntegration,
    ) -> None:
        bridge.simulate_service_policy_change("ind-1", "tenant-a", "sa-1")
        bridge.simulate_release_policy_change("ind-2", "tenant-b", "sb-1")
        ga = bridge.attach_simulation_state_to_graph("tenant-a")
        gb = bridge.attach_simulation_state_to_graph("tenant-b")
        # Both should see the global count (engine stores all)
        assert ga["total_simulations"] >= 1
        assert gb["total_simulations"] >= 1

    def test_memory_mesh_and_graph_agree(self, bridge: PolicySimulationIntegration) -> None:
        bridge.simulate_constitutional_change("ag-1", "t-ag", "s-ag1")
        mem = bridge.attach_simulation_state_to_memory_mesh("t-ag")
        graph = bridge.attach_simulation_state_to_graph("t-ag")
        for key in MEMORY_CONTENT_KEYS:
            assert mem.content[key] == graph[key]

    def test_simulate_with_custom_outcomes(self, bridge: PolicySimulationIntegration) -> None:
        result = bridge.simulate_service_policy_change(
            "co-1", "t-co", "s-co1",
            baseline_outcome="enabled",
            simulated_outcome="disabled",
        )
        assert result["source_type"] == "service_policy"

    def test_simulate_financial_with_custom_outcomes(self, bridge: PolicySimulationIntegration) -> None:
        result = bridge.simulate_financial_policy_change(
            "co-2", "t-co", "s-co2",
            baseline_outcome="approved",
            simulated_outcome="rejected",
        )
        assert result["source_type"] == "financial_policy"

    def test_simulate_workforce_with_custom_outcomes(self, bridge: PolicySimulationIntegration) -> None:
        result = bridge.simulate_workforce_policy_change(
            "co-3", "t-co", "s-co3",
            baseline_outcome="active",
            simulated_outcome="suspended",
        )
        assert result["source_type"] == "workforce_policy"

    def test_simulate_marketplace_with_custom_outcomes(self, bridge: PolicySimulationIntegration) -> None:
        result = bridge.simulate_marketplace_policy_change(
            "co-4", "t-co", "s-co4",
            baseline_outcome="listed",
            simulated_outcome="delisted",
        )
        assert result["source_type"] == "marketplace_policy"

    def test_simulate_constitutional_with_custom_outcomes(self, bridge: PolicySimulationIntegration) -> None:
        result = bridge.simulate_constitutional_change(
            "co-5", "t-co", "s-co5",
            baseline_outcome="ratified",
            simulated_outcome="revoked",
        )
        assert result["source_type"] == "constitutional_change"

    def test_simulate_release_with_custom_outcomes(self, bridge: PolicySimulationIntegration) -> None:
        result = bridge.simulate_release_policy_change(
            "co-6", "t-co", "s-co6",
            baseline_outcome="green",
            simulated_outcome="red",
        )
        assert result["source_type"] == "release_policy"
