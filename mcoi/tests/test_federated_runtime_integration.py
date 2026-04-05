"""Tests for federated runtime integration bridge (~50 tests).

Covers: FederatedRuntimeIntegration constructor, bridge methods for
    distributed_runtime, partner, continuity, factory, epistemic, identity,
    memory mesh attachment, and graph attachment.
"""

import pytest

from mcoi_runtime.contracts.memory_mesh import MemoryRecord
from mcoi_runtime.core.federated_runtime import FederatedRuntimeEngine
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine
from mcoi_runtime.core.engine_protocol import FixedClock
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.federated_runtime_integration import FederatedRuntimeIntegration

_T1 = "t1"
_T2 = "t2"


def _make_integration(clock=None):
    es = EventSpineEngine()
    clk = clock or FixedClock()
    fed = FederatedRuntimeEngine(es, clock=clk)
    mem = MemoryMeshEngine()
    integ = FederatedRuntimeIntegration(fed, es, mem)
    return integ, fed, es, mem


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------


class TestIntegrationConstructor:
    def test_valid_construction(self):
        integ, _, _, _ = _make_integration()
        assert integ is not None

    def test_invalid_federated_engine_rejected(self):
        es = EventSpineEngine()
        mem = MemoryMeshEngine()
        with pytest.raises(RuntimeCoreInvariantError):
            FederatedRuntimeIntegration("not_engine", es, mem)

    def test_invalid_event_spine_rejected(self):
        es = EventSpineEngine()
        fed = FederatedRuntimeEngine(es)
        mem = MemoryMeshEngine()
        with pytest.raises(RuntimeCoreInvariantError):
            FederatedRuntimeIntegration(fed, "not_es", mem)

    def test_invalid_memory_engine_rejected(self):
        es = EventSpineEngine()
        fed = FederatedRuntimeEngine(es)
        with pytest.raises(RuntimeCoreInvariantError):
            FederatedRuntimeIntegration(fed, es, "not_mem")

    def test_none_args_rejected(self):
        with pytest.raises(RuntimeCoreInvariantError):
            FederatedRuntimeIntegration(None, None, None)


# ---------------------------------------------------------------------------
# Bridge methods
# ---------------------------------------------------------------------------


class TestBridgeMethods:
    def test_federated_from_distributed_runtime(self):
        integ, fed, _, _ = _make_integration()
        result = integ.federated_from_distributed_runtime(_T1)
        assert result["tenant_id"] == _T1
        assert result["source_type"] == "distributed_runtime"
        assert result["node_status"] == "connected"
        assert result["claim_sync"] == "pending"
        assert fed.node_count == 1
        assert fed.claim_count == 1

    def test_federated_from_partner(self):
        integ, _, _, _ = _make_integration()
        result = integ.federated_from_partner(_T1)
        assert result["source_type"] == "partner"

    def test_federated_from_continuity(self):
        integ, _, _, _ = _make_integration()
        result = integ.federated_from_continuity(_T1)
        assert result["source_type"] == "continuity"

    def test_federated_from_factory(self):
        integ, _, _, _ = _make_integration()
        result = integ.federated_from_factory(_T1)
        assert result["source_type"] == "factory"

    def test_federated_from_epistemic(self):
        integ, _, _, _ = _make_integration()
        result = integ.federated_from_epistemic(_T1)
        assert result["source_type"] == "epistemic"

    def test_federated_from_identity(self):
        integ, _, _, _ = _make_integration()
        result = integ.federated_from_identity(_T1)
        assert result["source_type"] == "identity"

    def test_all_bridges_produce_unique_ids(self):
        integ, fed, _, _ = _make_integration()
        integ.federated_from_distributed_runtime(_T1)
        integ.federated_from_partner(_T1)
        integ.federated_from_continuity(_T1)
        assert fed.node_count == 3
        assert fed.claim_count == 3

    def test_bridge_emits_events(self):
        integ, _, es, _ = _make_integration()
        before = es.event_count
        integ.federated_from_distributed_runtime(_T1)
        assert es.event_count > before

    def test_bridge_result_dict_keys(self):
        integ, _, _, _ = _make_integration()
        result = integ.federated_from_distributed_runtime(_T1)
        expected_keys = {"node_id", "claim_id", "tenant_id", "node_status", "claim_sync", "source_type"}
        assert set(result.keys()) == expected_keys

    def test_multiple_bridges_same_tenant(self):
        integ, fed, _, _ = _make_integration()
        for _ in range(5):
            integ.federated_from_distributed_runtime(_T1)
        assert fed.node_count == 5
        assert fed.claim_count == 5

    def test_cross_tenant_bridges(self):
        integ, fed, _, _ = _make_integration()
        integ.federated_from_distributed_runtime(_T1)
        integ.federated_from_distributed_runtime(_T2)
        assert fed.node_count == 2


# ---------------------------------------------------------------------------
# Memory mesh attachment
# ---------------------------------------------------------------------------


class TestMemoryMeshAttachment:
    def test_attach_to_memory_mesh(self):
        integ, _, _, mem = _make_integration()
        record = integ.attach_federated_state_to_memory_mesh("scope-1")
        assert isinstance(record, MemoryRecord)
        assert mem.memory_count == 1

    def test_memory_content_reflects_state(self):
        integ, fed, _, _ = _make_integration()
        integ.federated_from_distributed_runtime(_T1)
        record = integ.attach_federated_state_to_memory_mesh("scope-1")
        content = record.content
        assert content["total_nodes"] == 1
        assert content["total_claims"] == 1

    def test_memory_title_is_bounded(self):
        integ, _, _, _ = _make_integration()
        record = integ.attach_federated_state_to_memory_mesh("scope-1")
        assert record.title == "Federated runtime state"
        assert "scope-1" not in record.title
        assert record.scope_ref_id == "scope-1"

    def test_memory_tags(self):
        integ, _, _, _ = _make_integration()
        record = integ.attach_federated_state_to_memory_mesh("scope-1")
        assert "federated" in record.tags

    def test_multiple_attachments(self):
        integ, _, _, mem = _make_integration()
        integ.attach_federated_state_to_memory_mesh("scope-1")
        integ.attach_federated_state_to_memory_mesh("scope-2")
        assert mem.memory_count == 2

    def test_attachment_emits_event(self):
        integ, _, es, _ = _make_integration()
        before = es.event_count
        integ.attach_federated_state_to_memory_mesh("scope-1")
        assert es.event_count > before


# ---------------------------------------------------------------------------
# Graph attachment
# ---------------------------------------------------------------------------


class TestGraphAttachment:
    def test_attach_to_graph(self):
        integ, _, _, _ = _make_integration()
        result = integ.attach_federated_state_to_graph("scope-1")
        assert result["scope_ref_id"] == "scope-1"

    def test_graph_reflects_state(self):
        integ, _, _, _ = _make_integration()
        integ.federated_from_distributed_runtime(_T1)
        result = integ.attach_federated_state_to_graph("scope-1")
        assert result["total_nodes"] == 1
        assert result["total_claims"] == 1

    def test_graph_keys(self):
        integ, _, _, _ = _make_integration()
        result = integ.attach_federated_state_to_graph("scope-1")
        expected = {"scope_ref_id", "total_nodes", "total_claims", "total_syncs",
                    "total_reconciliations", "total_partitions", "total_violations"}
        assert set(result.keys()) == expected

    def test_graph_empty_state(self):
        integ, _, _, _ = _make_integration()
        result = integ.attach_federated_state_to_graph("scope-1")
        assert result["total_nodes"] == 0
        assert result["total_claims"] == 0
        assert result["total_syncs"] == 0


# ---------------------------------------------------------------------------
# Golden integration scenarios
# ---------------------------------------------------------------------------


class TestGoldenIntegration:
    def test_full_lifecycle(self):
        integ, fed, es, mem = _make_integration()
        # Bridge from multiple sources
        integ.federated_from_distributed_runtime(_T1)
        integ.federated_from_partner(_T1)
        integ.federated_from_continuity(_T1)
        # Attach state
        record = integ.attach_federated_state_to_memory_mesh("scope-1")
        assert record.content["total_nodes"] == 3
        assert record.content["total_claims"] == 3
        # Graph
        graph = integ.attach_federated_state_to_graph("scope-1")
        assert graph["total_nodes"] == 3
        # Events emitted
        assert es.event_count > 0

    def test_cross_tenant_isolation_integration(self):
        integ, fed, _, _ = _make_integration()
        integ.federated_from_distributed_runtime(_T1)
        integ.federated_from_distributed_runtime(_T2)
        snap1 = fed.federated_snapshot("s1", _T1)
        snap2 = fed.federated_snapshot("s2", _T2)
        assert snap1.total_nodes == 1
        assert snap2.total_nodes == 1
