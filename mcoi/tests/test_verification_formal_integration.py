"""Tests for formal verification runtime integration bridge (~50 tests).

Covers: FormalVerificationIntegration constructor, bridge methods for
    governance, orchestration, external_execution, workflow, financial,
    continuity, memory mesh attachment, and graph attachment.
"""

import pytest

from mcoi_runtime.contracts.memory_mesh import MemoryRecord
from mcoi_runtime.core.verification_formal_runtime import FormalVerificationEngine
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine
from mcoi_runtime.core.engine_protocol import FixedClock
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.verification_formal_runtime_integration import FormalVerificationIntegration

_T1 = "t1"
_T2 = "t2"


def _make_integration(clock=None):
    es = EventSpineEngine()
    clk = clock or FixedClock()
    ver = FormalVerificationEngine(es, clock=clk)
    mem = MemoryMeshEngine()
    integ = FormalVerificationIntegration(ver, es, mem)
    return integ, ver, es, mem


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------


class TestIntegrationConstructor:
    def test_valid(self):
        integ, _, _, _ = _make_integration()
        assert integ is not None

    def test_invalid_verification_engine(self):
        es = EventSpineEngine()
        mem = MemoryMeshEngine()
        with pytest.raises(RuntimeCoreInvariantError):
            FormalVerificationIntegration("bad", es, mem)

    def test_invalid_event_spine(self):
        es = EventSpineEngine()
        ver = FormalVerificationEngine(es)
        mem = MemoryMeshEngine()
        with pytest.raises(RuntimeCoreInvariantError):
            FormalVerificationIntegration(ver, "bad", mem)

    def test_invalid_memory_engine(self):
        es = EventSpineEngine()
        ver = FormalVerificationEngine(es)
        with pytest.raises(RuntimeCoreInvariantError):
            FormalVerificationIntegration(ver, es, "bad")

    def test_none_args(self):
        with pytest.raises(RuntimeCoreInvariantError):
            FormalVerificationIntegration(None, None, None)


# ---------------------------------------------------------------------------
# Bridge methods
# ---------------------------------------------------------------------------


class TestBridgeMethods:
    def test_verify_governance(self):
        integ, ver, _, _ = _make_integration()
        result = integ.verify_governance(_T1)
        assert result["tenant_id"] == _T1
        assert result["source_type"] == "governance"
        assert result["spec_status"] == "active"
        assert result["property_status"] == "unknown"
        assert ver.spec_count == 1
        assert ver.property_count == 1

    def test_verify_orchestration(self):
        integ, _, _, _ = _make_integration()
        result = integ.verify_orchestration(_T1)
        assert result["source_type"] == "orchestration"

    def test_verify_external_execution(self):
        integ, _, _, _ = _make_integration()
        result = integ.verify_external_execution(_T1)
        assert result["source_type"] == "external_execution"

    def test_verify_workflow(self):
        integ, _, _, _ = _make_integration()
        result = integ.verify_workflow(_T1)
        assert result["source_type"] == "workflow"

    def test_verify_financial(self):
        integ, _, _, _ = _make_integration()
        result = integ.verify_financial(_T1)
        assert result["source_type"] == "financial"

    def test_verify_continuity(self):
        integ, _, _, _ = _make_integration()
        result = integ.verify_continuity(_T1)
        assert result["source_type"] == "continuity"

    def test_all_bridges_unique_ids(self):
        integ, ver, _, _ = _make_integration()
        integ.verify_governance(_T1)
        integ.verify_orchestration(_T1)
        integ.verify_external_execution(_T1)
        assert ver.spec_count == 3
        assert ver.property_count == 3

    def test_bridge_emits_events(self):
        integ, _, es, _ = _make_integration()
        before = es.event_count
        integ.verify_governance(_T1)
        assert es.event_count > before

    def test_bridge_result_keys(self):
        integ, _, _, _ = _make_integration()
        result = integ.verify_governance(_T1)
        expected = {"spec_id", "property_id", "tenant_id",
                    "spec_status", "property_status", "source_type"}
        assert set(result.keys()) == expected

    def test_multiple_same_bridge(self):
        integ, ver, _, _ = _make_integration()
        for _ in range(5):
            integ.verify_governance(_T1)
        assert ver.spec_count == 5

    def test_cross_tenant(self):
        integ, ver, _, _ = _make_integration()
        integ.verify_governance(_T1)
        integ.verify_governance(_T2)
        assert ver.spec_count == 2


# ---------------------------------------------------------------------------
# Memory mesh attachment
# ---------------------------------------------------------------------------


class TestMemoryMeshAttachment:
    def test_attach(self):
        integ, _, _, mem = _make_integration()
        record = integ.attach_verification_state_to_memory_mesh("scope-1")
        assert isinstance(record, MemoryRecord)
        assert record.title == "Formal verification state"
        assert "scope-1" not in record.title
        assert record.scope_ref_id == "scope-1"
        assert mem.memory_count == 1

    def test_content_reflects_state(self):
        integ, _, _, _ = _make_integration()
        integ.verify_governance(_T1)
        record = integ.attach_verification_state_to_memory_mesh("scope-1")
        assert record.content["total_specs"] == 1
        assert record.content["total_properties"] == 1

    def test_title(self):
        integ, _, _, _ = _make_integration()
        record = integ.attach_verification_state_to_memory_mesh("scope-1")
        assert record.title == "Formal verification state"
        assert "scope-1" not in record.title

    def test_tags(self):
        integ, _, _, _ = _make_integration()
        record = integ.attach_verification_state_to_memory_mesh("scope-1")
        assert "formal_verification" in record.tags

    def test_multiple_attachments(self):
        integ, _, _, mem = _make_integration()
        integ.attach_verification_state_to_memory_mesh("scope-1")
        integ.attach_verification_state_to_memory_mesh("scope-2")
        assert mem.memory_count == 2


# ---------------------------------------------------------------------------
# Graph attachment
# ---------------------------------------------------------------------------


class TestGraphAttachment:
    def test_attach(self):
        integ, _, _, _ = _make_integration()
        result = integ.attach_verification_state_to_graph("scope-1")
        assert result["scope_ref_id"] == "scope-1"

    def test_reflects_state(self):
        integ, _, _, _ = _make_integration()
        integ.verify_governance(_T1)
        result = integ.attach_verification_state_to_graph("scope-1")
        assert result["total_specs"] == 1

    def test_keys(self):
        integ, _, _, _ = _make_integration()
        result = integ.attach_verification_state_to_graph("scope-1")
        expected = {"scope_ref_id", "total_specs", "total_properties",
                    "total_runs", "total_certificates", "total_counterexamples",
                    "total_invariants", "total_violations"}
        assert set(result.keys()) == expected


# ---------------------------------------------------------------------------
# Golden integration scenarios
# ---------------------------------------------------------------------------


class TestGoldenIntegration:
    def test_full_lifecycle(self):
        integ, ver, es, mem = _make_integration()
        integ.verify_governance(_T1)
        integ.verify_orchestration(_T1)
        record = integ.attach_verification_state_to_memory_mesh("scope-1")
        assert record.content["total_specs"] == 2
        graph = integ.attach_verification_state_to_graph("scope-1")
        assert graph["total_specs"] == 2
        assert es.event_count > 0

    def test_cross_tenant_isolation_integration(self):
        integ, ver, _, _ = _make_integration()
        integ.verify_governance(_T1)
        integ.verify_governance(_T2)
        snap1 = ver.verification_snapshot("vs1", _T1)
        snap2 = ver.verification_snapshot("vs2", _T2)
        assert snap1.total_specs == 1
        assert snap2.total_specs == 1
