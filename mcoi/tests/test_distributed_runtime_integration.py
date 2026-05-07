"""Tests for DistributedRuntimeIntegration bridge.

Covers constructor validation, all 6 bridge methods (orchestration,
service_catalog, external_execution, llm_runtime, factory, research),
memory mesh attachment, graph attachment, event emission, sequential
bridges, multi-tenant isolation, and bridge sequence numbering.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine
from mcoi_runtime.core.distributed_runtime import DistributedRuntimeEngine
from mcoi_runtime.core.distributed_runtime_integration import DistributedRuntimeIntegration
from mcoi_runtime.contracts.memory_mesh import MemoryRecord


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def engines():
    """Return (EventSpineEngine, MemoryMeshEngine, DistributedRuntimeEngine)."""
    es = EventSpineEngine()
    mm = MemoryMeshEngine()
    dr = DistributedRuntimeEngine(es)
    return es, mm, dr


@pytest.fixture()
def integration(engines):
    """Return a DistributedRuntimeIntegration ready to use."""
    es, mm, dr = engines
    return DistributedRuntimeIntegration(dr, es, mm), es, mm, dr


# ===================================================================
# 1. Constructor validation
# ===================================================================


class TestConstructorValidation:
    def test_wrong_distributed_engine_type(self, engines):
        es, mm, _ = engines
        with pytest.raises(RuntimeCoreInvariantError, match="distributed_engine"):
            DistributedRuntimeIntegration("not-an-engine", es, mm)

    def test_wrong_event_spine_type(self, engines):
        es, mm, dr = engines
        with pytest.raises(RuntimeCoreInvariantError, match="event_spine"):
            DistributedRuntimeIntegration(dr, "not-a-spine", mm)

    def test_wrong_memory_engine_type(self, engines):
        es, _, dr = engines
        with pytest.raises(RuntimeCoreInvariantError, match="memory_engine"):
            DistributedRuntimeIntegration(dr, es, "not-a-memory")

    def test_none_distributed_engine(self, engines):
        es, mm, _ = engines
        with pytest.raises(RuntimeCoreInvariantError):
            DistributedRuntimeIntegration(None, es, mm)

    def test_none_event_spine(self, engines):
        es, mm, dr = engines
        with pytest.raises(RuntimeCoreInvariantError):
            DistributedRuntimeIntegration(dr, None, mm)

    def test_none_memory_engine(self, engines):
        es, _, dr = engines
        with pytest.raises(RuntimeCoreInvariantError):
            DistributedRuntimeIntegration(dr, es, None)

    def test_valid_construction(self, integration):
        di, _, _, _ = integration
        assert di is not None

    def test_int_distributed_engine(self, engines):
        es, mm, _ = engines
        with pytest.raises(RuntimeCoreInvariantError):
            DistributedRuntimeIntegration(42, es, mm)

    def test_dict_event_spine(self, engines):
        _, mm, dr = engines
        with pytest.raises(RuntimeCoreInvariantError):
            DistributedRuntimeIntegration(dr, {}, mm)

    def test_list_memory_engine(self, engines):
        es, _, dr = engines
        with pytest.raises(RuntimeCoreInvariantError):
            DistributedRuntimeIntegration(dr, es, [])


# ===================================================================
# 2. Bridge method: distribute_for_orchestration
# ===================================================================


class TestDistributeForOrchestration:
    def test_returns_dict(self, integration):
        di, _, _, _ = integration
        result = di.distribute_for_orchestration("t1")
        assert isinstance(result, dict)

    def test_contains_worker_id(self, integration):
        di, _, _, _ = integration
        result = di.distribute_for_orchestration("t1")
        assert "worker_id" in result
        assert isinstance(result["worker_id"], str)

    def test_contains_queue_id(self, integration):
        di, _, _, _ = integration
        result = di.distribute_for_orchestration("t1")
        assert "queue_id" in result

    def test_source_type_orchestration(self, integration):
        di, _, _, _ = integration
        result = di.distribute_for_orchestration("t1")
        assert result["source_type"] == "orchestration"

    def test_worker_status_idle(self, integration):
        di, _, _, _ = integration
        result = di.distribute_for_orchestration("t1")
        assert result["worker_status"] == "idle"

    def test_queue_status_active(self, integration):
        di, _, _, _ = integration
        result = di.distribute_for_orchestration("t1")
        assert result["queue_status"] == "active"

    def test_tenant_id_matches(self, integration):
        di, _, _, _ = integration
        result = di.distribute_for_orchestration("t1")
        assert result["tenant_id"] == "t1"

    def test_creates_worker_in_engine(self, integration):
        di, _, _, dr = integration
        before = dr.worker_count
        di.distribute_for_orchestration("t1")
        assert dr.worker_count == before + 1

    def test_creates_queue_in_engine(self, integration):
        di, _, _, dr = integration
        before = dr.queue_count
        di.distribute_for_orchestration("t1")
        assert dr.queue_count == before + 1

    def test_emits_event(self, integration):
        di, es, _, _ = integration
        before = es.event_count
        di.distribute_for_orchestration("t1")
        assert es.event_count > before


# ===================================================================
# 3. Bridge method: distribute_for_service_catalog
# ===================================================================


class TestDistributeForServiceCatalog:
    def test_returns_dict(self, integration):
        di, _, _, _ = integration
        result = di.distribute_for_service_catalog("t1")
        assert isinstance(result, dict)

    def test_source_type(self, integration):
        di, _, _, _ = integration
        result = di.distribute_for_service_catalog("t1")
        assert result["source_type"] == "service_catalog"

    def test_creates_worker(self, integration):
        di, _, _, dr = integration
        before = dr.worker_count
        di.distribute_for_service_catalog("t1")
        assert dr.worker_count == before + 1

    def test_creates_queue(self, integration):
        di, _, _, dr = integration
        before = dr.queue_count
        di.distribute_for_service_catalog("t1")
        assert dr.queue_count == before + 1


# ===================================================================
# 4. Bridge method: distribute_for_external_execution
# ===================================================================


class TestDistributeForExternalExecution:
    def test_returns_dict(self, integration):
        di, _, _, _ = integration
        result = di.distribute_for_external_execution("t1")
        assert isinstance(result, dict)

    def test_source_type(self, integration):
        di, _, _, _ = integration
        result = di.distribute_for_external_execution("t1")
        assert result["source_type"] == "external_execution"

    def test_creates_worker(self, integration):
        di, _, _, dr = integration
        before = dr.worker_count
        di.distribute_for_external_execution("t1")
        assert dr.worker_count == before + 1


# ===================================================================
# 5. Bridge method: distribute_for_llm_runtime
# ===================================================================


class TestDistributeForLlmRuntime:
    def test_returns_dict(self, integration):
        di, _, _, _ = integration
        result = di.distribute_for_llm_runtime("t1")
        assert isinstance(result, dict)

    def test_source_type(self, integration):
        di, _, _, _ = integration
        result = di.distribute_for_llm_runtime("t1")
        assert result["source_type"] == "llm_runtime"

    def test_creates_worker(self, integration):
        di, _, _, dr = integration
        before = dr.worker_count
        di.distribute_for_llm_runtime("t1")
        assert dr.worker_count == before + 1


# ===================================================================
# 6. Bridge method: distribute_for_factory
# ===================================================================


class TestDistributeForFactory:
    def test_returns_dict(self, integration):
        di, _, _, _ = integration
        result = di.distribute_for_factory("t1")
        assert isinstance(result, dict)

    def test_source_type(self, integration):
        di, _, _, _ = integration
        result = di.distribute_for_factory("t1")
        assert result["source_type"] == "factory"

    def test_creates_worker(self, integration):
        di, _, _, dr = integration
        before = dr.worker_count
        di.distribute_for_factory("t1")
        assert dr.worker_count == before + 1


# ===================================================================
# 7. Bridge method: distribute_for_research
# ===================================================================


class TestDistributeForResearch:
    def test_returns_dict(self, integration):
        di, _, _, _ = integration
        result = di.distribute_for_research("t1")
        assert isinstance(result, dict)

    def test_source_type(self, integration):
        di, _, _, _ = integration
        result = di.distribute_for_research("t1")
        assert result["source_type"] == "research"

    def test_creates_worker(self, integration):
        di, _, _, dr = integration
        before = dr.worker_count
        di.distribute_for_research("t1")
        assert dr.worker_count == before + 1


# ===================================================================
# 8. Memory mesh attachment
# ===================================================================


class TestMemoryMeshAttachment:
    def test_returns_memory_record(self, integration):
        di, _, _, _ = integration
        mr = di.attach_distributed_state_to_memory_mesh("scope-1")
        assert isinstance(mr, MemoryRecord)

    def test_memory_record_title(self, integration):
        di, _, _, _ = integration
        mr = di.attach_distributed_state_to_memory_mesh("scope-1")
        assert mr.title == "Distributed runtime state"
        assert "scope-1" not in mr.title
        assert mr.scope_ref_id == "scope-1"

    def test_memory_record_content_keys(self, integration):
        di, _, _, _ = integration
        mr = di.attach_distributed_state_to_memory_mesh("scope-1")
        content = mr.to_dict()["content"]
        assert "total_workers" in content
        assert "total_queues" in content
        assert "total_leases" in content
        assert "total_shards" in content
        assert "total_checkpoints" in content
        assert "total_violations" in content

    def test_increments_memory_count(self, integration):
        di, _, mm, _ = integration
        before = mm.memory_count
        di.attach_distributed_state_to_memory_mesh("scope-1")
        assert mm.memory_count == before + 1

    def test_emits_event(self, integration):
        di, es, _, _ = integration
        before = es.event_count
        di.attach_distributed_state_to_memory_mesh("scope-1")
        assert es.event_count > before

    def test_reflects_engine_state(self, integration):
        di, _, _, dr = integration
        dr.register_worker("w1", "t1", "W1")
        dr.create_queue("q1", "t1", "Q1")
        mr = di.attach_distributed_state_to_memory_mesh("scope-1")
        content = mr.to_dict()["content"]
        assert content["total_workers"] == 1
        assert content["total_queues"] == 1

    def test_tags_include_distributed(self, integration):
        di, _, _, _ = integration
        mr = di.attach_distributed_state_to_memory_mesh("scope-1")
        assert "distributed" in mr.tags


# ===================================================================
# 9. Graph attachment
# ===================================================================


class TestGraphAttachment:
    def test_returns_dict(self, integration):
        di, _, _, _ = integration
        result = di.attach_distributed_state_to_graph("scope-1")
        assert isinstance(result, dict)

    def test_contains_scope_ref(self, integration):
        di, _, _, _ = integration
        result = di.attach_distributed_state_to_graph("scope-1")
        assert result["scope_ref_id"] == "scope-1"

    def test_contains_counts(self, integration):
        di, _, _, _ = integration
        result = di.attach_distributed_state_to_graph("scope-1")
        assert "total_workers" in result
        assert "total_queues" in result
        assert "total_leases" in result
        assert "total_shards" in result
        assert "total_checkpoints" in result
        assert "total_violations" in result

    def test_reflects_engine_state(self, integration):
        di, _, _, dr = integration
        dr.register_worker("w1", "t1", "W1")
        dr.register_worker("w2", "t1", "W2")
        result = di.attach_distributed_state_to_graph("scope-1")
        assert result["total_workers"] == 2


# ===================================================================
# 10. Sequential bridge calls
# ===================================================================


class TestSequentialBridges:
    def test_multiple_bridges_same_tenant(self, integration):
        di, _, _, dr = integration
        di.distribute_for_orchestration("t1")
        di.distribute_for_service_catalog("t1")
        di.distribute_for_factory("t1")
        assert dr.worker_count == 3
        assert dr.queue_count == 3

    def test_bridge_ids_unique(self, integration):
        di, _, _, dr = integration
        r1 = di.distribute_for_orchestration("t1")
        r2 = di.distribute_for_service_catalog("t1")
        assert r1["worker_id"] != r2["worker_id"]
        assert r1["queue_id"] != r2["queue_id"]

    def test_all_six_bridges(self, integration):
        di, _, _, dr = integration
        di.distribute_for_orchestration("t1")
        di.distribute_for_service_catalog("t1")
        di.distribute_for_external_execution("t1")
        di.distribute_for_llm_runtime("t1")
        di.distribute_for_factory("t1")
        di.distribute_for_research("t1")
        assert dr.worker_count == 6
        assert dr.queue_count == 6


# ===================================================================
# 11. Multi-tenant isolation via bridge
# ===================================================================


class TestMultiTenantBridge:
    def test_different_tenants(self, integration):
        di, _, _, dr = integration
        r1 = di.distribute_for_orchestration("t1")
        r2 = di.distribute_for_orchestration("t2")
        assert r1["tenant_id"] == "t1"
        assert r2["tenant_id"] == "t2"
        assert r1["worker_id"] != r2["worker_id"]

    def test_tenant_isolation_in_workers(self, integration):
        di, _, _, dr = integration
        di.distribute_for_orchestration("t1")
        di.distribute_for_orchestration("t2")
        assert len(dr.workers_for_tenant("t1")) == 1
        assert len(dr.workers_for_tenant("t2")) == 1

    def test_tenant_isolation_in_queues(self, integration):
        di, _, _, dr = integration
        di.distribute_for_orchestration("t1")
        di.distribute_for_orchestration("t2")
        assert len(dr.queues_for_tenant("t1")) == 1
        assert len(dr.queues_for_tenant("t2")) == 1
