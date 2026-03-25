"""Tests for adversarial runtime integration bridge (~50 tests).

Covers: AdversarialRuntimeIntegration constructor, bridge methods for
    constitutional, copilot, external_execution, self_tuning, public_api,
    identity, memory mesh attachment, and graph attachment.
"""

import pytest

from mcoi_runtime.contracts.memory_mesh import MemoryRecord
from mcoi_runtime.core.adversarial_runtime import AdversarialRuntimeEngine
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine
from mcoi_runtime.core.engine_protocol import FixedClock
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.adversarial_runtime_integration import AdversarialRuntimeIntegration

_T1 = "t1"
_T2 = "t2"


def _make_integration(clock=None):
    es = EventSpineEngine()
    clk = clock or FixedClock()
    adv = AdversarialRuntimeEngine(es, clock=clk)
    mem = MemoryMeshEngine()
    integ = AdversarialRuntimeIntegration(adv, es, mem)
    return integ, adv, es, mem


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------


class TestIntegrationConstructor:
    def test_valid(self):
        integ, _, _, _ = _make_integration()
        assert integ is not None

    def test_invalid_adversarial_engine(self):
        es = EventSpineEngine()
        mem = MemoryMeshEngine()
        with pytest.raises(RuntimeCoreInvariantError):
            AdversarialRuntimeIntegration("bad", es, mem)

    def test_invalid_event_spine(self):
        es = EventSpineEngine()
        adv = AdversarialRuntimeEngine(es)
        mem = MemoryMeshEngine()
        with pytest.raises(RuntimeCoreInvariantError):
            AdversarialRuntimeIntegration(adv, "bad", mem)

    def test_invalid_memory_engine(self):
        es = EventSpineEngine()
        adv = AdversarialRuntimeEngine(es)
        with pytest.raises(RuntimeCoreInvariantError):
            AdversarialRuntimeIntegration(adv, es, "bad")

    def test_none_args(self):
        with pytest.raises(RuntimeCoreInvariantError):
            AdversarialRuntimeIntegration(None, None, None)


# ---------------------------------------------------------------------------
# Bridge methods
# ---------------------------------------------------------------------------


class TestBridgeMethods:
    def test_adversarial_from_constitutional(self):
        integ, adv, _, _ = _make_integration()
        result = integ.adversarial_from_constitutional(_T1)
        assert result["tenant_id"] == _T1
        assert result["source_type"] == "constitutional"
        assert result["scenario_status"] == "planned"
        assert result["vulnerability_status"] == "open"
        assert adv.scenario_count == 1
        assert adv.vulnerability_count == 1

    def test_adversarial_from_copilot(self):
        integ, _, _, _ = _make_integration()
        result = integ.adversarial_from_copilot(_T1)
        assert result["source_type"] == "copilot"

    def test_adversarial_from_external_execution(self):
        integ, _, _, _ = _make_integration()
        result = integ.adversarial_from_external_execution(_T1)
        assert result["source_type"] == "external_execution"

    def test_adversarial_from_self_tuning(self):
        integ, _, _, _ = _make_integration()
        result = integ.adversarial_from_self_tuning(_T1)
        assert result["source_type"] == "self_tuning"

    def test_adversarial_from_public_api(self):
        integ, _, _, _ = _make_integration()
        result = integ.adversarial_from_public_api(_T1)
        assert result["source_type"] == "public_api"

    def test_adversarial_from_identity(self):
        integ, _, _, _ = _make_integration()
        result = integ.adversarial_from_identity(_T1)
        assert result["source_type"] == "identity"

    def test_all_bridges_unique_ids(self):
        integ, adv, _, _ = _make_integration()
        integ.adversarial_from_constitutional(_T1)
        integ.adversarial_from_copilot(_T1)
        integ.adversarial_from_external_execution(_T1)
        assert adv.scenario_count == 3
        assert adv.vulnerability_count == 3

    def test_bridge_emits_events(self):
        integ, _, es, _ = _make_integration()
        before = es.event_count
        integ.adversarial_from_constitutional(_T1)
        assert es.event_count > before

    def test_bridge_result_keys(self):
        integ, _, _, _ = _make_integration()
        result = integ.adversarial_from_constitutional(_T1)
        expected = {"scenario_id", "vulnerability_id", "tenant_id",
                    "scenario_status", "vulnerability_status", "source_type"}
        assert set(result.keys()) == expected

    def test_multiple_same_bridge(self):
        integ, adv, _, _ = _make_integration()
        for _ in range(5):
            integ.adversarial_from_constitutional(_T1)
        assert adv.scenario_count == 5

    def test_cross_tenant(self):
        integ, adv, _, _ = _make_integration()
        integ.adversarial_from_constitutional(_T1)
        integ.adversarial_from_constitutional(_T2)
        assert adv.scenario_count == 2


# ---------------------------------------------------------------------------
# Memory mesh attachment
# ---------------------------------------------------------------------------


class TestMemoryMeshAttachment:
    def test_attach(self):
        integ, _, _, mem = _make_integration()
        record = integ.attach_adversarial_state_to_memory_mesh("scope-1")
        assert isinstance(record, MemoryRecord)
        assert mem.memory_count == 1

    def test_content_reflects_state(self):
        integ, _, _, _ = _make_integration()
        integ.adversarial_from_constitutional(_T1)
        record = integ.attach_adversarial_state_to_memory_mesh("scope-1")
        assert record.content["total_scenarios"] == 1
        assert record.content["total_vulnerabilities"] == 1

    def test_title(self):
        integ, _, _, _ = _make_integration()
        record = integ.attach_adversarial_state_to_memory_mesh("scope-1")
        assert "scope-1" in record.title

    def test_tags(self):
        integ, _, _, _ = _make_integration()
        record = integ.attach_adversarial_state_to_memory_mesh("scope-1")
        assert "adversarial" in record.tags

    def test_multiple_attachments(self):
        integ, _, _, mem = _make_integration()
        integ.attach_adversarial_state_to_memory_mesh("scope-1")
        integ.attach_adversarial_state_to_memory_mesh("scope-2")
        assert mem.memory_count == 2


# ---------------------------------------------------------------------------
# Graph attachment
# ---------------------------------------------------------------------------


class TestGraphAttachment:
    def test_attach(self):
        integ, _, _, _ = _make_integration()
        result = integ.attach_adversarial_state_to_graph("scope-1")
        assert result["scope_ref_id"] == "scope-1"

    def test_reflects_state(self):
        integ, _, _, _ = _make_integration()
        integ.adversarial_from_constitutional(_T1)
        result = integ.attach_adversarial_state_to_graph("scope-1")
        assert result["total_scenarios"] == 1

    def test_keys(self):
        integ, _, _, _ = _make_integration()
        result = integ.attach_adversarial_state_to_graph("scope-1")
        expected = {"scope_ref_id", "total_scenarios", "total_vulnerabilities",
                    "total_exploits", "total_defenses", "total_stress_tests",
                    "total_violations"}
        assert set(result.keys()) == expected


# ---------------------------------------------------------------------------
# Golden integration scenarios
# ---------------------------------------------------------------------------


class TestGoldenIntegration:
    def test_full_lifecycle(self):
        integ, adv, es, mem = _make_integration()
        integ.adversarial_from_constitutional(_T1)
        integ.adversarial_from_copilot(_T1)
        record = integ.attach_adversarial_state_to_memory_mesh("scope-1")
        assert record.content["total_scenarios"] == 2
        graph = integ.attach_adversarial_state_to_graph("scope-1")
        assert graph["total_scenarios"] == 2
        assert es.event_count > 0

    def test_cross_tenant_isolation_integration(self):
        integ, adv, _, _ = _make_integration()
        integ.adversarial_from_constitutional(_T1)
        integ.adversarial_from_constitutional(_T2)
        snap1 = adv.adversarial_snapshot("s1", _T1)
        snap2 = adv.adversarial_snapshot("s2", _T2)
        assert snap1.total_scenarios == 1
        assert snap2.total_scenarios == 1
