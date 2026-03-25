"""Tests for RecordsRuntimeIntegration bridge.

Covers constructor validation, all seven record_from_* methods (kind,
source_type, evidence_grade, return shape, auto-link creation), memory
mesh attachment, graph attachment, event emission, and an end-to-end
golden path.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine
from mcoi_runtime.core.records_runtime import RecordsRuntimeEngine
from mcoi_runtime.core.records_runtime_integration import RecordsRuntimeIntegration
from mcoi_runtime.contracts.records_runtime import (
    RecordKind,
    EvidenceGrade,
    RecordAuthority,
)
from mcoi_runtime.contracts.memory_mesh import MemoryRecord
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


# -----------------------------------------------------------------------
# Fixture
# -----------------------------------------------------------------------


@pytest.fixture()
def bridge():
    """Create a fully wired RecordsRuntimeIntegration."""
    es = EventSpineEngine()
    mm = MemoryMeshEngine()
    eng = RecordsRuntimeEngine(es)
    b = RecordsRuntimeIntegration(eng, es, mm)
    return b, eng, es, mm


# -----------------------------------------------------------------------
# Constructor validation (3 tests)
# -----------------------------------------------------------------------


class TestConstructorValidation:
    """Constructor must reject wrong types."""

    def test_rejects_non_records_engine(self):
        es = EventSpineEngine()
        mm = MemoryMeshEngine()
        with pytest.raises(RuntimeCoreInvariantError, match="RecordsRuntimeEngine"):
            RecordsRuntimeIntegration("not-an-engine", es, mm)

    def test_rejects_non_event_spine(self):
        es = EventSpineEngine()
        mm = MemoryMeshEngine()
        eng = RecordsRuntimeEngine(es)
        with pytest.raises(RuntimeCoreInvariantError, match="EventSpineEngine"):
            RecordsRuntimeIntegration(eng, "not-a-spine", mm)

    def test_rejects_non_memory_engine(self):
        es = EventSpineEngine()
        eng = RecordsRuntimeEngine(es)
        with pytest.raises(RuntimeCoreInvariantError, match="MemoryMeshEngine"):
            RecordsRuntimeIntegration(eng, es, "not-a-mesh")


# -----------------------------------------------------------------------
# Return-shape helper
# -----------------------------------------------------------------------

EXPECTED_KEYS = {"record_id", "tenant_id", "kind", "source_type", "source_id", "evidence_grade"}


# -----------------------------------------------------------------------
# record_from_campaign (2 tests: kind/source_type/evidence_grade + shape)
# -----------------------------------------------------------------------


class TestRecordFromCampaign:

    def test_kind_source_type_evidence_grade(self, bridge):
        b, *_ = bridge
        result = b.record_from_campaign("r1", "t1", "camp-1")
        assert result["kind"] == RecordKind.OPERATIONAL.value
        assert result["source_type"] == "campaign"
        assert result["evidence_grade"] == EvidenceGrade.PRIMARY.value

    def test_return_shape(self, bridge):
        b, *_ = bridge
        result = b.record_from_campaign("r1", "t1", "camp-1")
        assert set(result.keys()) == EXPECTED_KEYS
        assert result["record_id"] == "r1"
        assert result["tenant_id"] == "t1"
        assert result["source_id"] == "camp-1"


# -----------------------------------------------------------------------
# record_from_program (2 tests)
# -----------------------------------------------------------------------


class TestRecordFromProgram:

    def test_kind_source_type_evidence_grade(self, bridge):
        b, *_ = bridge
        result = b.record_from_program("r2", "t1", "prog-1")
        assert result["kind"] == RecordKind.OPERATIONAL.value
        assert result["source_type"] == "program"
        assert result["evidence_grade"] == EvidenceGrade.PRIMARY.value

    def test_return_shape(self, bridge):
        b, *_ = bridge
        result = b.record_from_program("r2", "t1", "prog-1")
        assert set(result.keys()) == EXPECTED_KEYS
        assert result["source_id"] == "prog-1"


# -----------------------------------------------------------------------
# record_from_control_test (2 tests)
# -----------------------------------------------------------------------


class TestRecordFromControlTest:

    def test_kind_source_type_evidence_grade(self, bridge):
        b, *_ = bridge
        result = b.record_from_control_test("r3", "t1", "ct-1")
        assert result["kind"] == RecordKind.COMPLIANCE.value
        assert result["source_type"] == "control_test"
        assert result["evidence_grade"] == EvidenceGrade.PRIMARY.value

    def test_return_shape(self, bridge):
        b, *_ = bridge
        result = b.record_from_control_test("r3", "t1", "ct-1")
        assert set(result.keys()) == EXPECTED_KEYS
        assert result["source_id"] == "ct-1"


# -----------------------------------------------------------------------
# record_from_change (2 tests)
# -----------------------------------------------------------------------


class TestRecordFromChange:

    def test_kind_source_type_evidence_grade(self, bridge):
        b, *_ = bridge
        result = b.record_from_change("r4", "t1", "chg-1")
        assert result["kind"] == RecordKind.AUDIT.value
        assert result["source_type"] == "change"
        assert result["evidence_grade"] == EvidenceGrade.PRIMARY.value

    def test_return_shape(self, bridge):
        b, *_ = bridge
        result = b.record_from_change("r4", "t1", "chg-1")
        assert set(result.keys()) == EXPECTED_KEYS
        assert result["source_id"] == "chg-1"


# -----------------------------------------------------------------------
# record_from_approval (2 tests)
# -----------------------------------------------------------------------


class TestRecordFromApproval:

    def test_kind_source_type_evidence_grade(self, bridge):
        b, *_ = bridge
        result = b.record_from_approval("r5", "t1", "appr-1")
        assert result["kind"] == RecordKind.AUDIT.value
        assert result["source_type"] == "approval"
        assert result["evidence_grade"] == EvidenceGrade.PRIMARY.value

    def test_return_shape(self, bridge):
        b, *_ = bridge
        result = b.record_from_approval("r5", "t1", "appr-1")
        assert set(result.keys()) == EXPECTED_KEYS
        assert result["source_id"] == "appr-1"


# -----------------------------------------------------------------------
# record_from_connector_activity (2 tests)
# -----------------------------------------------------------------------


class TestRecordFromConnectorActivity:

    def test_kind_source_type_evidence_grade(self, bridge):
        b, *_ = bridge
        result = b.record_from_connector_activity("r6", "t1", "conn-1")
        assert result["kind"] == RecordKind.OPERATIONAL.value
        assert result["source_type"] == "connector"
        assert result["evidence_grade"] == EvidenceGrade.SECONDARY.value

    def test_return_shape(self, bridge):
        b, *_ = bridge
        result = b.record_from_connector_activity("r6", "t1", "conn-1")
        assert set(result.keys()) == EXPECTED_KEYS
        assert result["source_id"] == "conn-1"


# -----------------------------------------------------------------------
# record_from_fault_campaign (2 tests)
# -----------------------------------------------------------------------


class TestRecordFromFaultCampaign:

    def test_kind_source_type_evidence_grade(self, bridge):
        b, *_ = bridge
        result = b.record_from_fault_campaign("r7", "t1", "fc-1")
        assert result["kind"] == RecordKind.EVIDENCE.value
        assert result["source_type"] == "fault_campaign"
        assert result["evidence_grade"] == EvidenceGrade.PRIMARY.value

    def test_return_shape(self, bridge):
        b, *_ = bridge
        result = b.record_from_fault_campaign("r7", "t1", "fc-1")
        assert set(result.keys()) == EXPECTED_KEYS
        assert result["source_id"] == "fc-1"


# -----------------------------------------------------------------------
# Auto-link creation (1 test)
# -----------------------------------------------------------------------


class TestAutoLinkCreation:

    def test_each_method_creates_a_link(self, bridge):
        b, eng, *_ = bridge
        assert eng.link_count == 0

        b.record_from_campaign("r1", "t1", "camp-1")
        assert eng.link_count == 1

        b.record_from_program("r2", "t1", "prog-1")
        assert eng.link_count == 2

        b.record_from_control_test("r3", "t1", "ct-1")
        assert eng.link_count == 3

        b.record_from_change("r4", "t1", "chg-1")
        assert eng.link_count == 4

        b.record_from_approval("r5", "t1", "appr-1")
        assert eng.link_count == 5

        b.record_from_connector_activity("r6", "t1", "conn-1")
        assert eng.link_count == 6

        b.record_from_fault_campaign("r7", "t1", "fc-1")
        assert eng.link_count == 7


# -----------------------------------------------------------------------
# Memory mesh attachment (1 test)
# -----------------------------------------------------------------------


class TestMemoryMeshAttachment:

    def test_attach_returns_memory_record_with_correct_tags(self, bridge):
        b, eng, es, mm = bridge
        b.record_from_campaign("r1", "t1", "camp-1")

        mem = b.attach_records_to_memory_mesh("scope-1")

        assert isinstance(mem, MemoryRecord)
        assert "records" in mem.tags
        assert "retention" in mem.tags
        assert "legal_hold" in mem.tags


# -----------------------------------------------------------------------
# Graph attachment (1 test)
# -----------------------------------------------------------------------


class TestGraphAttachment:

    def test_attach_returns_dict_with_expected_keys(self, bridge):
        b, *_ = bridge
        b.record_from_campaign("r1", "t1", "camp-1")

        graph = b.attach_records_to_graph("scope-1")

        expected_keys = {
            "scope_ref_id",
            "total_records",
            "total_schedules",
            "total_holds",
            "active_holds",
            "total_links",
            "total_disposals",
            "total_violations",
        }
        assert set(graph.keys()) == expected_keys
        assert graph["scope_ref_id"] == "scope-1"
        assert graph["total_records"] >= 1
        assert graph["total_links"] >= 1


# -----------------------------------------------------------------------
# Events emitted (1 test)
# -----------------------------------------------------------------------


class TestEventsEmitted:

    def test_event_count_increases_per_record(self, bridge):
        b, eng, es, mm = bridge
        initial = es.event_count

        b.record_from_campaign("r1", "t1", "camp-1")
        # RecordsRuntimeEngine emits its own event for register_record and
        # add_link; the integration bridge emits one more.
        after_one = es.event_count
        assert after_one > initial

        b.record_from_program("r2", "t1", "prog-1")
        after_two = es.event_count
        assert after_two > after_one


# -----------------------------------------------------------------------
# End-to-end golden path (1 test)
# -----------------------------------------------------------------------


class TestEndToEndGoldenPath:

    def test_create_all_seven_then_memory_and_graph(self, bridge):
        b, eng, es, mm = bridge

        # Create all 7 record types.
        b.record_from_campaign("r1", "t1", "camp-1")
        b.record_from_program("r2", "t1", "prog-1")
        b.record_from_control_test("r3", "t1", "ct-1")
        b.record_from_change("r4", "t1", "chg-1")
        b.record_from_approval("r5", "t1", "appr-1")
        b.record_from_connector_activity("r6", "t1", "conn-1")
        b.record_from_fault_campaign("r7", "t1", "fc-1")

        # Verify counts.
        assert eng.record_count == 7
        assert eng.link_count == 7

        # Attach to memory mesh.
        mem = b.attach_records_to_memory_mesh("golden-scope")
        assert isinstance(mem, MemoryRecord)
        assert set(mem.tags) == {"records", "retention", "legal_hold"}

        # Attach to graph.
        graph = b.attach_records_to_graph("golden-scope")
        assert graph["total_records"] == 7
        assert graph["total_links"] == 7
        assert graph["total_schedules"] == 0
        assert graph["total_holds"] == 0
        assert graph["active_holds"] == 0
        assert graph["total_disposals"] == 0
        assert graph["total_violations"] == 0

        # Events were emitted for all operations.
        assert es.event_count > 0
