"""Tests for epistemic runtime integration bridge (~50 tests).

Covers: EpistemicRuntimeIntegration constructor, bridge methods for
    logic, causal, uncertainty, temporal, ontology, research,
    memory mesh attachment, and graph attachment.
"""

import pytest

from mcoi_runtime.contracts.memory_mesh import MemoryRecord
from mcoi_runtime.contracts.epistemic_runtime import KnowledgeStatus
from mcoi_runtime.core.epistemic_runtime import EpistemicRuntimeEngine
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine
from mcoi_runtime.core.engine_protocol import FixedClock
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.epistemic_runtime_integration import EpistemicRuntimeIntegration

_T1 = "t1"
_T2 = "t2"


def _make_integration(clock=None):
    es = EventSpineEngine()
    clk = clock or FixedClock()
    ep = EpistemicRuntimeEngine(es, clock=clk)
    mem = MemoryMeshEngine()
    integ = EpistemicRuntimeIntegration(ep, es, mem)
    return integ, ep, es, mem


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------


class TestIntegrationConstructor:
    def test_valid(self):
        integ, _, _, _ = _make_integration()
        assert integ is not None

    def test_invalid_epistemic_engine(self):
        es = EventSpineEngine()
        mem = MemoryMeshEngine()
        with pytest.raises(RuntimeCoreInvariantError):
            EpistemicRuntimeIntegration("bad", es, mem)

    def test_invalid_event_spine(self):
        es = EventSpineEngine()
        ep = EpistemicRuntimeEngine(es)
        mem = MemoryMeshEngine()
        with pytest.raises(RuntimeCoreInvariantError):
            EpistemicRuntimeIntegration(ep, "bad", mem)

    def test_invalid_memory_engine(self):
        es = EventSpineEngine()
        ep = EpistemicRuntimeEngine(es)
        with pytest.raises(RuntimeCoreInvariantError):
            EpistemicRuntimeIntegration(ep, es, "bad")

    def test_none_args(self):
        with pytest.raises(RuntimeCoreInvariantError):
            EpistemicRuntimeIntegration(None, None, None)


# ---------------------------------------------------------------------------
# Bridge methods
# ---------------------------------------------------------------------------


class TestBridgeMethods:
    def test_epistemic_from_logic(self):
        integ, ep, _, _ = _make_integration()
        result = integ.epistemic_from_logic(_T1, "logic-ref-1")
        assert result["tenant_id"] == _T1
        assert result["source_type"] == "logic"
        assert result["status"] == "proven"
        assert result["trust_level"] == "verified"
        assert ep.claim_count == 1

    def test_epistemic_from_causal(self):
        integ, _, _, _ = _make_integration()
        result = integ.epistemic_from_causal(_T1, "causal-ref-1")
        assert result["source_type"] == "causal"
        assert result["status"] == "inferred"

    def test_epistemic_from_uncertainty(self):
        integ, _, _, _ = _make_integration()
        result = integ.epistemic_from_uncertainty(_T1, "belief-ref-1", confidence=0.3)
        assert result["source_type"] == "uncertainty"
        assert result["status"] == "reported"

    def test_epistemic_from_temporal(self):
        integ, _, _, _ = _make_integration()
        result = integ.epistemic_from_temporal(_T1, "temporal-ref-1")
        assert result["source_type"] == "temporal"
        assert result["status"] == "observed"

    def test_epistemic_from_ontology(self):
        integ, _, _, _ = _make_integration()
        result = integ.epistemic_from_ontology(_T1, "concept-ref-1")
        assert result["source_type"] == "ontology"
        assert result["status"] == "reported"

    def test_epistemic_from_research_high(self):
        integ, _, _, _ = _make_integration()
        result = integ.epistemic_from_research(_T1, "research-ref-1", evidence_strength=0.9)
        assert result["source_type"] == "research"
        assert result["status"] == "proven"

    def test_epistemic_from_research_medium(self):
        integ, _, _, _ = _make_integration()
        result = integ.epistemic_from_research(_T1, "research-ref-1", evidence_strength=0.6)
        assert result["status"] == "inferred"

    def test_epistemic_from_research_low(self):
        integ, _, _, _ = _make_integration()
        result = integ.epistemic_from_research(_T1, "research-ref-1", evidence_strength=0.3)
        assert result["status"] == "reported"

    def test_all_bridges_unique_ids(self):
        integ, ep, _, _ = _make_integration()
        integ.epistemic_from_logic(_T1, "ref1")
        integ.epistemic_from_causal(_T1, "ref2")
        integ.epistemic_from_uncertainty(_T1, "ref3")
        integ.epistemic_from_temporal(_T1, "ref4")
        integ.epistemic_from_ontology(_T1, "ref5")
        integ.epistemic_from_research(_T1, "ref6")
        assert ep.claim_count == 6

    def test_bridge_emits_events(self):
        integ, _, es, _ = _make_integration()
        before = es.event_count
        integ.epistemic_from_logic(_T1, "ref1")
        assert es.event_count > before

    def test_bridge_result_keys(self):
        integ, _, _, _ = _make_integration()
        result = integ.epistemic_from_logic(_T1, "ref1")
        expected = {"claim_id", "source_type", "tenant_id", "status", "trust_level"}
        assert set(result.keys()) == expected

    def test_multiple_same_bridge(self):
        integ, ep, _, _ = _make_integration()
        for i in range(5):
            integ.epistemic_from_logic(_T1, f"ref{i}")
        assert ep.claim_count == 5

    def test_cross_tenant(self):
        integ, ep, _, _ = _make_integration()
        integ.epistemic_from_logic(_T1, "ref1")
        integ.epistemic_from_logic(_T2, "ref2")
        assert ep.claim_count == 2


# ---------------------------------------------------------------------------
# Memory mesh attachment
# ---------------------------------------------------------------------------


class TestMemoryMeshAttachment:
    def test_attach(self):
        integ, _, _, mem = _make_integration()
        record = integ.attach_epistemic_state_to_memory_mesh("scope-1")
        assert isinstance(record, MemoryRecord)
        assert mem.memory_count == 1

    def test_content_reflects_state(self):
        integ, _, _, _ = _make_integration()
        integ.epistemic_from_logic(_T1, "ref1")
        record = integ.attach_epistemic_state_to_memory_mesh("scope-1")
        assert record.content["total_claims"] == 1

    def test_title_is_bounded(self):
        integ, _, _, _ = _make_integration()
        record = integ.attach_epistemic_state_to_memory_mesh("scope-1")
        assert record.title == "Epistemic state"
        assert "scope-1" not in record.title
        assert record.scope_ref_id == "scope-1"

    def test_tags(self):
        integ, _, _, _ = _make_integration()
        record = integ.attach_epistemic_state_to_memory_mesh("scope-1")
        assert "epistemic" in record.tags

    def test_multiple_attachments(self):
        integ, _, _, mem = _make_integration()
        integ.attach_epistemic_state_to_memory_mesh("scope-1")
        integ.attach_epistemic_state_to_memory_mesh("scope-2")
        assert mem.memory_count == 2

    def test_attachment_emits_event(self):
        integ, _, es, _ = _make_integration()
        before = es.event_count
        integ.attach_epistemic_state_to_memory_mesh("scope-1")
        assert es.event_count > before


# ---------------------------------------------------------------------------
# Graph attachment
# ---------------------------------------------------------------------------


class TestGraphAttachment:
    def test_attach(self):
        integ, _, _, _ = _make_integration()
        result = integ.attach_epistemic_state_to_graph("scope-1")
        assert result["scope_ref_id"] == "scope-1"

    def test_reflects_state(self):
        integ, _, _, _ = _make_integration()
        integ.epistemic_from_logic(_T1, "ref1")
        result = integ.attach_epistemic_state_to_graph("scope-1")
        assert result["total_claims"] == 1

    def test_keys(self):
        integ, _, _, _ = _make_integration()
        result = integ.attach_epistemic_state_to_graph("scope-1")
        expected = {"scope_ref_id", "total_claims", "total_sources",
                    "total_assessments", "total_conflicts",
                    "total_reliability_updates", "total_violations"}
        assert set(result.keys()) == expected

    def test_empty_state(self):
        integ, _, _, _ = _make_integration()
        result = integ.attach_epistemic_state_to_graph("scope-1")
        assert result["total_claims"] == 0


# ---------------------------------------------------------------------------
# Golden integration scenarios
# ---------------------------------------------------------------------------


class TestGoldenIntegration:
    def test_full_lifecycle(self):
        integ, ep, es, mem = _make_integration()
        integ.epistemic_from_logic(_T1, "logic-1")
        integ.epistemic_from_causal(_T1, "causal-1")
        integ.epistemic_from_temporal(_T1, "temporal-1")
        record = integ.attach_epistemic_state_to_memory_mesh("scope-1")
        assert record.content["total_claims"] == 3
        graph = integ.attach_epistemic_state_to_graph("scope-1")
        assert graph["total_claims"] == 3
        assert es.event_count > 0

    def test_cross_tenant_isolation_integration(self):
        integ, ep, _, _ = _make_integration()
        integ.epistemic_from_logic(_T1, "ref1")
        integ.epistemic_from_logic(_T2, "ref2")
        snap1 = ep.epistemic_snapshot("es1", _T1)
        snap2 = ep.epistemic_snapshot("es2", _T2)
        assert snap1.total_claims == 1
        assert snap2.total_claims == 1

    def test_research_strength_mapping(self):
        integ, ep, _, _ = _make_integration()
        r1 = integ.epistemic_from_research(_T1, "r1", evidence_strength=0.9)
        r2 = integ.epistemic_from_research(_T1, "r2", evidence_strength=0.6)
        r3 = integ.epistemic_from_research(_T1, "r3", evidence_strength=0.3)
        assert r1["status"] == "proven"
        assert r2["status"] == "inferred"
        assert r3["status"] == "reported"
