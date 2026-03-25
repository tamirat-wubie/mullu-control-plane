"""Comprehensive tests for ObservabilityRuntimeIntegration bridge."""

from __future__ import annotations

import pytest

from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine
from mcoi_runtime.core.observability_runtime import ObservabilityRuntimeEngine
from mcoi_runtime.core.observability_runtime_integration import (
    ObservabilityRuntimeIntegration,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def event_spine() -> EventSpineEngine:
    return EventSpineEngine()


@pytest.fixture()
def obs_engine(event_spine: EventSpineEngine) -> ObservabilityRuntimeEngine:
    return ObservabilityRuntimeEngine(event_spine)


@pytest.fixture()
def memory_engine() -> MemoryMeshEngine:
    return MemoryMeshEngine()


@pytest.fixture()
def bridge(
    obs_engine: ObservabilityRuntimeEngine,
    event_spine: EventSpineEngine,
    memory_engine: MemoryMeshEngine,
) -> ObservabilityRuntimeIntegration:
    return ObservabilityRuntimeIntegration(obs_engine, event_spine, memory_engine)


# ===================================================================
# Constructor validation (6 tests)
# ===================================================================


class TestConstructorValidation:
    """Rejects wrong types for each constructor argument."""

    def test_reject_bad_observability_engine(
        self, event_spine: EventSpineEngine, memory_engine: MemoryMeshEngine
    ) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            ObservabilityRuntimeIntegration("bad", event_spine, memory_engine)

    def test_reject_bad_event_spine(
        self, obs_engine: ObservabilityRuntimeEngine, memory_engine: MemoryMeshEngine
    ) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            ObservabilityRuntimeIntegration(obs_engine, "bad", memory_engine)

    def test_reject_bad_memory_engine(
        self, obs_engine: ObservabilityRuntimeEngine, event_spine: EventSpineEngine
    ) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            ObservabilityRuntimeIntegration(obs_engine, event_spine, "bad")

    def test_reject_none_observability_engine(
        self, event_spine: EventSpineEngine, memory_engine: MemoryMeshEngine
    ) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            ObservabilityRuntimeIntegration(None, event_spine, memory_engine)

    def test_reject_none_event_spine(
        self, obs_engine: ObservabilityRuntimeEngine, memory_engine: MemoryMeshEngine
    ) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            ObservabilityRuntimeIntegration(obs_engine, None, memory_engine)

    def test_reject_none_memory_engine(
        self, obs_engine: ObservabilityRuntimeEngine, event_spine: EventSpineEngine
    ) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            ObservabilityRuntimeIntegration(obs_engine, event_spine, None)


# ===================================================================
# observe_api (8 tests)
# ===================================================================


class TestObserveApi:
    """Tests for observe_api method."""

    def test_returns_dict(self, bridge: ObservabilityRuntimeIntegration) -> None:
        result = bridge.observe_api("t1", "tenant-a", "m1", 10.0)
        assert isinstance(result, dict)

    def test_trace_id_matches(self, bridge: ObservabilityRuntimeIntegration) -> None:
        result = bridge.observe_api("t1", "tenant-a", "m1", 5.0)
        assert result["trace_id"] == "t1"

    def test_metric_id_matches(self, bridge: ObservabilityRuntimeIntegration) -> None:
        result = bridge.observe_api("t1", "tenant-a", "m1", 5.0)
        assert result["metric_id"] == "m1"

    def test_tenant_id_matches(self, bridge: ObservabilityRuntimeIntegration) -> None:
        result = bridge.observe_api("t1", "tenant-a", "m1", 5.0)
        assert result["tenant_id"] == "tenant-a"

    def test_source_runtime(self, bridge: ObservabilityRuntimeIntegration) -> None:
        result = bridge.observe_api("t1", "tenant-a", "m1", 5.0)
        assert result["source_runtime"] == "public_api"

    def test_source_type(self, bridge: ObservabilityRuntimeIntegration) -> None:
        result = bridge.observe_api("t1", "tenant-a", "m1", 5.0)
        assert result["source_type"] == "api"

    def test_metric_value(self, bridge: ObservabilityRuntimeIntegration) -> None:
        result = bridge.observe_api("t1", "tenant-a", "m1", 42.0)
        assert result["metric_value"] == 42.0

    def test_emits_events(
        self,
        bridge: ObservabilityRuntimeIntegration,
        event_spine: EventSpineEngine,
    ) -> None:
        before = event_spine.event_count
        bridge.observe_api("t1", "tenant-a", "m1", 1.0)
        assert event_spine.event_count > before

    def test_default_request_count(
        self, bridge: ObservabilityRuntimeIntegration
    ) -> None:
        result = bridge.observe_api("t-def", "tenant-a", "m-def")
        assert result["metric_value"] == 0.0


# ===================================================================
# observe_workspace (8 tests)
# ===================================================================


class TestObserveWorkspace:
    """Tests for observe_workspace method."""

    def test_returns_dict(self, bridge: ObservabilityRuntimeIntegration) -> None:
        result = bridge.observe_workspace("tw1", "tenant-b", "mw1", 3.0)
        assert isinstance(result, dict)

    def test_trace_id(self, bridge: ObservabilityRuntimeIntegration) -> None:
        result = bridge.observe_workspace("tw1", "tenant-b", "mw1", 3.0)
        assert result["trace_id"] == "tw1"

    def test_metric_id(self, bridge: ObservabilityRuntimeIntegration) -> None:
        result = bridge.observe_workspace("tw1", "tenant-b", "mw1", 3.0)
        assert result["metric_id"] == "mw1"

    def test_tenant_id(self, bridge: ObservabilityRuntimeIntegration) -> None:
        result = bridge.observe_workspace("tw1", "tenant-b", "mw1", 3.0)
        assert result["tenant_id"] == "tenant-b"

    def test_source_runtime(self, bridge: ObservabilityRuntimeIntegration) -> None:
        result = bridge.observe_workspace("tw1", "tenant-b", "mw1", 3.0)
        assert result["source_runtime"] == "operator_workspace"

    def test_source_type(self, bridge: ObservabilityRuntimeIntegration) -> None:
        result = bridge.observe_workspace("tw1", "tenant-b", "mw1", 3.0)
        assert result["source_type"] == "workspace"

    def test_metric_value(self, bridge: ObservabilityRuntimeIntegration) -> None:
        result = bridge.observe_workspace("tw1", "tenant-b", "mw1", 99.0)
        assert result["metric_value"] == 99.0

    def test_emits_events(
        self,
        bridge: ObservabilityRuntimeIntegration,
        event_spine: EventSpineEngine,
    ) -> None:
        before = event_spine.event_count
        bridge.observe_workspace("tw1", "tenant-b", "mw1", 1.0)
        assert event_spine.event_count > before

    def test_default_queue_depth(
        self, bridge: ObservabilityRuntimeIntegration
    ) -> None:
        result = bridge.observe_workspace("tw-def", "tenant-b", "mw-def")
        assert result["metric_value"] == 0.0


# ===================================================================
# observe_orchestration (8 tests)
# ===================================================================


class TestObserveOrchestration:
    """Tests for observe_orchestration method."""

    def test_returns_dict(self, bridge: ObservabilityRuntimeIntegration) -> None:
        result = bridge.observe_orchestration("to1", "tenant-c", "mo1", 7.0)
        assert isinstance(result, dict)

    def test_trace_id(self, bridge: ObservabilityRuntimeIntegration) -> None:
        result = bridge.observe_orchestration("to1", "tenant-c", "mo1", 7.0)
        assert result["trace_id"] == "to1"

    def test_metric_id(self, bridge: ObservabilityRuntimeIntegration) -> None:
        result = bridge.observe_orchestration("to1", "tenant-c", "mo1", 7.0)
        assert result["metric_id"] == "mo1"

    def test_tenant_id(self, bridge: ObservabilityRuntimeIntegration) -> None:
        result = bridge.observe_orchestration("to1", "tenant-c", "mo1", 7.0)
        assert result["tenant_id"] == "tenant-c"

    def test_source_runtime(self, bridge: ObservabilityRuntimeIntegration) -> None:
        result = bridge.observe_orchestration("to1", "tenant-c", "mo1", 7.0)
        assert result["source_runtime"] == "meta_orchestration"

    def test_source_type(self, bridge: ObservabilityRuntimeIntegration) -> None:
        result = bridge.observe_orchestration("to1", "tenant-c", "mo1", 7.0)
        assert result["source_type"] == "orchestration"

    def test_metric_value(self, bridge: ObservabilityRuntimeIntegration) -> None:
        result = bridge.observe_orchestration("to1", "tenant-c", "mo1", 15.0)
        assert result["metric_value"] == 15.0

    def test_emits_events(
        self,
        bridge: ObservabilityRuntimeIntegration,
        event_spine: EventSpineEngine,
    ) -> None:
        before = event_spine.event_count
        bridge.observe_orchestration("to1", "tenant-c", "mo1", 1.0)
        assert event_spine.event_count > before

    def test_default_active_plans(
        self, bridge: ObservabilityRuntimeIntegration
    ) -> None:
        result = bridge.observe_orchestration("to-def", "tenant-c", "mo-def")
        assert result["metric_value"] == 0.0


# ===================================================================
# observe_continuity (8 tests)
# ===================================================================


class TestObserveContinuity:
    """Tests for observe_continuity method."""

    def test_returns_dict(self, bridge: ObservabilityRuntimeIntegration) -> None:
        result = bridge.observe_continuity("tc1", "tenant-d", "mc1", 2.0)
        assert isinstance(result, dict)

    def test_trace_id(self, bridge: ObservabilityRuntimeIntegration) -> None:
        result = bridge.observe_continuity("tc1", "tenant-d", "mc1", 2.0)
        assert result["trace_id"] == "tc1"

    def test_metric_id(self, bridge: ObservabilityRuntimeIntegration) -> None:
        result = bridge.observe_continuity("tc1", "tenant-d", "mc1", 2.0)
        assert result["metric_id"] == "mc1"

    def test_tenant_id(self, bridge: ObservabilityRuntimeIntegration) -> None:
        result = bridge.observe_continuity("tc1", "tenant-d", "mc1", 2.0)
        assert result["tenant_id"] == "tenant-d"

    def test_source_runtime(self, bridge: ObservabilityRuntimeIntegration) -> None:
        result = bridge.observe_continuity("tc1", "tenant-d", "mc1", 2.0)
        assert result["source_runtime"] == "continuity"

    def test_source_type(self, bridge: ObservabilityRuntimeIntegration) -> None:
        result = bridge.observe_continuity("tc1", "tenant-d", "mc1", 2.0)
        assert result["source_type"] == "continuity"

    def test_metric_value(self, bridge: ObservabilityRuntimeIntegration) -> None:
        result = bridge.observe_continuity("tc1", "tenant-d", "mc1", 8.0)
        assert result["metric_value"] == 8.0

    def test_emits_events(
        self,
        bridge: ObservabilityRuntimeIntegration,
        event_spine: EventSpineEngine,
    ) -> None:
        before = event_spine.event_count
        bridge.observe_continuity("tc1", "tenant-d", "mc1", 1.0)
        assert event_spine.event_count > before

    def test_default_disruption_count(
        self, bridge: ObservabilityRuntimeIntegration
    ) -> None:
        result = bridge.observe_continuity("tc-def", "tenant-d", "mc-def")
        assert result["metric_value"] == 0.0


# ===================================================================
# observe_financials (8 tests)
# ===================================================================


class TestObserveFinancials:
    """Tests for observe_financials method."""

    def test_returns_dict(self, bridge: ObservabilityRuntimeIntegration) -> None:
        result = bridge.observe_financials("tf1", "tenant-e", "mf1", 100.0)
        assert isinstance(result, dict)

    def test_trace_id(self, bridge: ObservabilityRuntimeIntegration) -> None:
        result = bridge.observe_financials("tf1", "tenant-e", "mf1", 100.0)
        assert result["trace_id"] == "tf1"

    def test_metric_id(self, bridge: ObservabilityRuntimeIntegration) -> None:
        result = bridge.observe_financials("tf1", "tenant-e", "mf1", 100.0)
        assert result["metric_id"] == "mf1"

    def test_tenant_id(self, bridge: ObservabilityRuntimeIntegration) -> None:
        result = bridge.observe_financials("tf1", "tenant-e", "mf1", 100.0)
        assert result["tenant_id"] == "tenant-e"

    def test_source_runtime(self, bridge: ObservabilityRuntimeIntegration) -> None:
        result = bridge.observe_financials("tf1", "tenant-e", "mf1", 100.0)
        assert result["source_runtime"] == "settlement"

    def test_source_type(self, bridge: ObservabilityRuntimeIntegration) -> None:
        result = bridge.observe_financials("tf1", "tenant-e", "mf1", 100.0)
        assert result["source_type"] == "financials"

    def test_metric_value(self, bridge: ObservabilityRuntimeIntegration) -> None:
        result = bridge.observe_financials("tf1", "tenant-e", "mf1", 250.50)
        assert result["metric_value"] == 250.50

    def test_emits_events(
        self,
        bridge: ObservabilityRuntimeIntegration,
        event_spine: EventSpineEngine,
    ) -> None:
        before = event_spine.event_count
        bridge.observe_financials("tf1", "tenant-e", "mf1", 1.0)
        assert event_spine.event_count > before

    def test_default_outstanding_amount(
        self, bridge: ObservabilityRuntimeIntegration
    ) -> None:
        result = bridge.observe_financials("tf-def", "tenant-e", "mf-def")
        assert result["metric_value"] == 0.0


# ===================================================================
# observe_service_catalog (8 tests)
# ===================================================================


class TestObserveServiceCatalog:
    """Tests for observe_service_catalog method."""

    def test_returns_dict(self, bridge: ObservabilityRuntimeIntegration) -> None:
        result = bridge.observe_service_catalog("ts1", "tenant-f", "ms1", 4.0)
        assert isinstance(result, dict)

    def test_trace_id(self, bridge: ObservabilityRuntimeIntegration) -> None:
        result = bridge.observe_service_catalog("ts1", "tenant-f", "ms1", 4.0)
        assert result["trace_id"] == "ts1"

    def test_metric_id(self, bridge: ObservabilityRuntimeIntegration) -> None:
        result = bridge.observe_service_catalog("ts1", "tenant-f", "ms1", 4.0)
        assert result["metric_id"] == "ms1"

    def test_tenant_id(self, bridge: ObservabilityRuntimeIntegration) -> None:
        result = bridge.observe_service_catalog("ts1", "tenant-f", "ms1", 4.0)
        assert result["tenant_id"] == "tenant-f"

    def test_source_runtime(self, bridge: ObservabilityRuntimeIntegration) -> None:
        result = bridge.observe_service_catalog("ts1", "tenant-f", "ms1", 4.0)
        assert result["source_runtime"] == "service_catalog"

    def test_source_type(self, bridge: ObservabilityRuntimeIntegration) -> None:
        result = bridge.observe_service_catalog("ts1", "tenant-f", "ms1", 4.0)
        assert result["source_type"] == "service_catalog"

    def test_metric_value(self, bridge: ObservabilityRuntimeIntegration) -> None:
        result = bridge.observe_service_catalog("ts1", "tenant-f", "ms1", 33.0)
        assert result["metric_value"] == 33.0

    def test_emits_events(
        self,
        bridge: ObservabilityRuntimeIntegration,
        event_spine: EventSpineEngine,
    ) -> None:
        before = event_spine.event_count
        bridge.observe_service_catalog("ts1", "tenant-f", "ms1", 1.0)
        assert event_spine.event_count > before

    def test_default_pending_requests(
        self, bridge: ObservabilityRuntimeIntegration
    ) -> None:
        result = bridge.observe_service_catalog("ts-def", "tenant-f", "ms-def")
        assert result["metric_value"] == 0.0


# ===================================================================
# attach_observability_to_memory_mesh (9 tests)
# ===================================================================


class TestAttachToMemoryMesh:
    """Tests for attach_observability_to_memory_mesh method."""

    def test_returns_memory_record(
        self, bridge: ObservabilityRuntimeIntegration
    ) -> None:
        from mcoi_runtime.contracts.memory_mesh import MemoryRecord

        result = bridge.attach_observability_to_memory_mesh("scope-1")
        assert isinstance(result, MemoryRecord)

    def test_tags_include_observability(
        self, bridge: ObservabilityRuntimeIntegration
    ) -> None:
        result = bridge.attach_observability_to_memory_mesh("scope-2")
        assert "observability" in result.tags

    def test_tags_include_telemetry(
        self, bridge: ObservabilityRuntimeIntegration
    ) -> None:
        result = bridge.attach_observability_to_memory_mesh("scope-3")
        assert "telemetry" in result.tags

    def test_tags_include_debug(
        self, bridge: ObservabilityRuntimeIntegration
    ) -> None:
        result = bridge.attach_observability_to_memory_mesh("scope-4")
        assert "debug" in result.tags

    def test_content_has_seven_keys(
        self, bridge: ObservabilityRuntimeIntegration
    ) -> None:
        result = bridge.attach_observability_to_memory_mesh("scope-5")
        assert len(result.content) == 7

    def test_content_keys(self, bridge: ObservabilityRuntimeIntegration) -> None:
        result = bridge.attach_observability_to_memory_mesh("scope-6")
        expected_keys = {
            "total_metrics",
            "total_logs",
            "total_traces",
            "total_spans",
            "total_anomalies",
            "total_debug_sessions",
            "total_violations",
        }
        assert set(result.content.keys()) == expected_keys

    def test_memory_added_to_engine(
        self,
        bridge: ObservabilityRuntimeIntegration,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        before = memory_engine.memory_count
        bridge.attach_observability_to_memory_mesh("scope-7")
        assert memory_engine.memory_count == before + 1

    def test_emits_event(
        self,
        bridge: ObservabilityRuntimeIntegration,
        event_spine: EventSpineEngine,
    ) -> None:
        before = event_spine.event_count
        bridge.attach_observability_to_memory_mesh("scope-8")
        assert event_spine.event_count > before

    def test_scope_ref_id_on_record(
        self, bridge: ObservabilityRuntimeIntegration
    ) -> None:
        result = bridge.attach_observability_to_memory_mesh("scope-9")
        assert result.scope_ref_id == "scope-9"


# ===================================================================
# attach_observability_to_graph (9 tests)
# ===================================================================


class TestAttachToGraph:
    """Tests for attach_observability_to_graph method."""

    def test_returns_dict(self, bridge: ObservabilityRuntimeIntegration) -> None:
        result = bridge.attach_observability_to_graph("g-scope-1")
        assert isinstance(result, dict)

    def test_has_eight_keys(self, bridge: ObservabilityRuntimeIntegration) -> None:
        result = bridge.attach_observability_to_graph("g-scope-2")
        assert len(result) == 8

    def test_scope_ref_id_present(
        self, bridge: ObservabilityRuntimeIntegration
    ) -> None:
        result = bridge.attach_observability_to_graph("g-scope-3")
        assert result["scope_ref_id"] == "g-scope-3"

    def test_total_metrics_key(self, bridge: ObservabilityRuntimeIntegration) -> None:
        result = bridge.attach_observability_to_graph("g-scope-4")
        assert "total_metrics" in result

    def test_total_logs_key(self, bridge: ObservabilityRuntimeIntegration) -> None:
        result = bridge.attach_observability_to_graph("g-scope-5")
        assert "total_logs" in result

    def test_total_traces_key(self, bridge: ObservabilityRuntimeIntegration) -> None:
        result = bridge.attach_observability_to_graph("g-scope-6")
        assert "total_traces" in result

    def test_total_spans_key(self, bridge: ObservabilityRuntimeIntegration) -> None:
        result = bridge.attach_observability_to_graph("g-scope-7")
        assert "total_spans" in result

    def test_total_anomalies_key(
        self, bridge: ObservabilityRuntimeIntegration
    ) -> None:
        result = bridge.attach_observability_to_graph("g-scope-8")
        assert "total_anomalies" in result

    def test_all_expected_keys(self, bridge: ObservabilityRuntimeIntegration) -> None:
        result = bridge.attach_observability_to_graph("g-scope-9")
        expected_keys = {
            "scope_ref_id",
            "total_metrics",
            "total_logs",
            "total_traces",
            "total_spans",
            "total_anomalies",
            "total_debug_sessions",
            "total_violations",
        }
        assert set(result.keys()) == expected_keys


# ===================================================================
# Cross-cutting / integration (6 tests)
# ===================================================================


class TestCrossCutting:
    """Cross-cutting integration scenarios."""

    def test_observe_then_attach_reflects_counts(
        self, bridge: ObservabilityRuntimeIntegration
    ) -> None:
        bridge.observe_api("cc-t1", "tenant-cc", "cc-m1", 10.0)
        result = bridge.attach_observability_to_graph("tenant-cc")
        assert result["total_traces"] >= 1
        assert result["total_metrics"] >= 1

    def test_multiple_observe_methods_accumulate(
        self, bridge: ObservabilityRuntimeIntegration
    ) -> None:
        bridge.observe_api("cc-t2", "tenant-acc", "cc-m2", 1.0)
        bridge.observe_workspace("cc-t3", "tenant-acc", "cc-m3", 2.0)
        result = bridge.attach_observability_to_graph("tenant-acc")
        assert result["total_traces"] >= 2
        assert result["total_metrics"] >= 2

    def test_memory_mesh_reflects_accumulated_state(
        self, bridge: ObservabilityRuntimeIntegration
    ) -> None:
        bridge.observe_financials("cc-t4", "tenant-mem", "cc-m4", 50.0)
        bridge.observe_continuity("cc-t5", "tenant-mem", "cc-m5", 3.0)
        mem = bridge.attach_observability_to_memory_mesh("tenant-mem")
        assert mem.content["total_traces"] >= 2
        assert mem.content["total_metrics"] >= 2

    def test_return_keys_consistent_across_all_observe_methods(
        self, bridge: ObservabilityRuntimeIntegration
    ) -> None:
        expected = {"trace_id", "metric_id", "tenant_id", "source_runtime", "metric_value", "source_type"}
        r1 = bridge.observe_api("ck-t1", "ck-ten", "ck-m1", 1.0)
        r2 = bridge.observe_workspace("ck-t2", "ck-ten", "ck-m2", 1.0)
        r3 = bridge.observe_orchestration("ck-t3", "ck-ten", "ck-m3", 1.0)
        r4 = bridge.observe_continuity("ck-t4", "ck-ten", "ck-m4", 1.0)
        r5 = bridge.observe_financials("ck-t5", "ck-ten", "ck-m5", 1.0)
        r6 = bridge.observe_service_catalog("ck-t6", "ck-ten", "ck-m6", 1.0)
        for r in (r1, r2, r3, r4, r5, r6):
            assert set(r.keys()) == expected

    def test_event_count_increases_for_each_observe(
        self,
        bridge: ObservabilityRuntimeIntegration,
        event_spine: EventSpineEngine,
    ) -> None:
        before = event_spine.event_count
        bridge.observe_api("ev-t1", "ev-ten", "ev-m1", 1.0)
        after_one = event_spine.event_count
        bridge.observe_workspace("ev-t2", "ev-ten", "ev-m2", 1.0)
        after_two = event_spine.event_count
        assert after_one > before
        assert after_two > after_one

    def test_graph_snapshot_zero_when_no_observations(
        self, bridge: ObservabilityRuntimeIntegration
    ) -> None:
        result = bridge.attach_observability_to_graph("empty-tenant")
        assert result["total_metrics"] == 0
        assert result["total_traces"] == 0
        assert result["total_logs"] == 0
        assert result["total_spans"] == 0
        assert result["total_anomalies"] == 0
        assert result["total_debug_sessions"] == 0
        assert result["total_violations"] == 0
