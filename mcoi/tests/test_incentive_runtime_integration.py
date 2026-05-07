"""Tests for incentive runtime integration bridge (Phase 115).

Covers: IncentiveRuntimeIntegration cross-domain creation, memory mesh
        attachment, and graph attachment.
"""

import pytest

from mcoi_runtime.core.engine_protocol import FixedClock
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.incentive_runtime import IncentiveRuntimeEngine
from mcoi_runtime.core.incentive_runtime_integration import IncentiveRuntimeIntegration
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine


FIXED_TS = "2026-01-01T00:00:00+00:00"


def _make_integration():
    es = EventSpineEngine()
    clk = FixedClock(FIXED_TS)
    eng = IncentiveRuntimeEngine(es, clock=clk)
    mem = MemoryMeshEngine()
    integ = IncentiveRuntimeIntegration(eng, es, mem)
    return integ, eng, es, mem


# ===================================================================
# Constructor validation
# ===================================================================

class TestConstructorValidation:
    def test_valid_construction(self):
        integ, _, _, _ = _make_integration()
        assert integ is not None

    def test_invalid_incentive_engine(self):
        es = EventSpineEngine()
        mem = MemoryMeshEngine()
        with pytest.raises(RuntimeCoreInvariantError):
            IncentiveRuntimeIntegration("bad", es, mem)

    def test_invalid_event_spine(self):
        es = EventSpineEngine()
        eng = IncentiveRuntimeEngine(es, clock=FixedClock(FIXED_TS))
        mem = MemoryMeshEngine()
        with pytest.raises(RuntimeCoreInvariantError):
            IncentiveRuntimeIntegration(eng, "bad", mem)

    def test_invalid_memory_engine(self):
        es = EventSpineEngine()
        eng = IncentiveRuntimeEngine(es, clock=FixedClock(FIXED_TS))
        with pytest.raises(RuntimeCoreInvariantError):
            IncentiveRuntimeIntegration(eng, es, "bad")


# ===================================================================
# Cross-domain incentive creation
# ===================================================================

class TestIncentiveFromMarketplace:
    def test_creates_incentive(self):
        integ, eng, _, _ = _make_integration()
        result = integ.incentive_from_marketplace("i1", "t1", "Discount A", "mkt1")
        assert result["incentive_id"] == "i1"
        assert result["source_type"] == "marketplace"
        assert eng.incentive_count == 1

    def test_emits_event(self):
        integ, _, es, _ = _make_integration()
        before = es.event_count
        integ.incentive_from_marketplace("i1", "t1", "Discount A", "mkt1")
        assert es.event_count > before

    def test_duplicate_rejected(self):
        integ, _, _, _ = _make_integration()
        integ.incentive_from_marketplace("i1", "t1", "Discount A", "mkt1")
        with pytest.raises(RuntimeCoreInvariantError):
            integ.incentive_from_marketplace("i1", "t1", "Discount A", "mkt1")

    def test_result_fields(self):
        integ, _, _, _ = _make_integration()
        result = integ.incentive_from_marketplace("i1", "t1", "Discount A", "mkt1")
        assert result["tenant_id"] == "t1"
        assert result["marketplace_ref"] == "mkt1"
        assert result["kind"] == "discount"
        assert result["status"] == "active"


class TestIncentiveFromPartner:
    def test_creates_incentive(self):
        integ, eng, _, _ = _make_integration()
        result = integ.incentive_from_partner("i1", "t1", "Commission A", "partner1")
        assert result["source_type"] == "partner"
        assert result["partner_ref"] == "partner1"
        assert eng.incentive_count == 1


class TestIncentiveFromWorkforce:
    def test_creates_incentive(self):
        integ, eng, _, _ = _make_integration()
        result = integ.incentive_from_workforce("i1", "t1", "Bonus A", "wf1")
        assert result["source_type"] == "workforce"
        assert result["workforce_ref"] == "wf1"


class TestIncentiveFromCustomer:
    def test_creates_incentive(self):
        integ, eng, _, _ = _make_integration()
        result = integ.incentive_from_customer("i1", "t1", "Reward A", "cust1")
        assert result["source_type"] == "customer"
        assert result["customer_ref"] == "cust1"


class TestIncentiveFromBilling:
    def test_creates_incentive(self):
        integ, eng, _, _ = _make_integration()
        result = integ.incentive_from_billing("i1", "t1", "Discount B", "bill1")
        assert result["source_type"] == "billing"
        assert result["billing_ref"] == "bill1"


class TestIncentiveFromContract:
    def test_creates_incentive(self):
        integ, eng, _, _ = _make_integration()
        result = integ.incentive_from_contract("i1", "t1", "Threshold A", "con1")
        assert result["source_type"] == "contract"
        assert result["contract_ref"] == "con1"


# ===================================================================
# Memory mesh attachment
# ===================================================================

class TestMemoryMeshAttachment:
    def test_attach_to_memory(self):
        integ, eng, _, mem = _make_integration()
        eng.register_incentive("i1", "t1", "Reward A")
        record = integ.attach_incentive_to_memory_mesh("scope-1")
        assert record.memory_id
        assert mem.memory_count >= 1

    def test_memory_title_is_bounded(self):
        integ, eng, _, _ = _make_integration()
        eng.register_incentive("i1", "t1", "Reward A")
        record = integ.attach_incentive_to_memory_mesh("scope-1")
        assert record.title == "Incentive state"
        assert "scope-1" not in record.title
        assert record.scope_ref_id == "scope-1"

    def test_emits_event(self):
        integ, eng, es, _ = _make_integration()
        eng.register_incentive("i1", "t1", "Reward A")
        before = es.event_count
        integ.attach_incentive_to_memory_mesh("scope-1")
        assert es.event_count > before


# ===================================================================
# Graph attachment
# ===================================================================

class TestGraphAttachment:
    def test_attach_to_graph(self):
        integ, eng, _, _ = _make_integration()
        eng.register_incentive("i1", "t1", "Reward A")
        result = integ.attach_incentive_to_graph("scope-1")
        assert result["scope_ref_id"] == "scope-1"
        assert result["total_incentives"] == 1

    def test_graph_reflects_violations(self):
        integ, eng, _, _ = _make_integration()
        eng.record_policy_effect("e1", "t1", "pol1", kind=PolicyEffectKind.PERVERSE)
        eng.detect_incentive_violations()
        result = integ.attach_incentive_to_graph("scope-1")
        assert result["total_violations"] > 0


# ===================================================================
# End-to-end integration
# ===================================================================

class TestEndToEnd:
    def test_full_workflow(self):
        integ, eng, es, mem = _make_integration()
        integ.incentive_from_marketplace("i1", "t1", "Discount A", "mkt1")
        eng.suspend_incentive("i1")
        integ.attach_incentive_to_memory_mesh("scope-1")
        assert mem.memory_count >= 1
        graph = integ.attach_incentive_to_graph("scope-1")
        assert graph["total_incentives"] == 1
        assert es.event_count >= 3

    def test_multiple_sources(self):
        integ, eng, _, _ = _make_integration()
        integ.incentive_from_marketplace("i1", "t1", "Discount A", "mkt1")
        integ.incentive_from_partner("i2", "t1", "Commission A", "partner1")
        integ.incentive_from_workforce("i3", "t1", "Bonus A", "wf1")
        assert eng.incentive_count == 3


# Need to import for one test
from mcoi_runtime.contracts.incentive_runtime import PolicyEffectKind
