"""Comprehensive tests for CaseRuntimeIntegration bridge.

Covers constructor validation, case creation methods, evidence attachment,
memory mesh and graph attachment, event emission, and end-to-end golden path.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine
from mcoi_runtime.core.case_runtime import CaseRuntimeEngine
from mcoi_runtime.core.case_runtime_integration import CaseRuntimeIntegration
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture()
def spine() -> EventSpineEngine:
    return EventSpineEngine()


@pytest.fixture()
def memory() -> MemoryMeshEngine:
    return MemoryMeshEngine()


@pytest.fixture()
def case_engine(spine: EventSpineEngine) -> CaseRuntimeEngine:
    return CaseRuntimeEngine(spine)


@pytest.fixture()
def bridge(
    case_engine: CaseRuntimeEngine,
    spine: EventSpineEngine,
    memory: MemoryMeshEngine,
) -> CaseRuntimeIntegration:
    return CaseRuntimeIntegration(case_engine, spine, memory)


# ==================================================================
# Constructor validation (3 tests)
# ==================================================================

class TestConstructorValidation:
    """CaseRuntimeIntegration rejects wrong types for each argument."""

    def test_rejects_wrong_type_for_case_engine(
        self, spine: EventSpineEngine, memory: MemoryMeshEngine
    ) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="case_engine"):
            CaseRuntimeIntegration("not-an-engine", spine, memory)  # type: ignore[arg-type]

    def test_rejects_wrong_type_for_event_spine(
        self, case_engine: CaseRuntimeEngine, memory: MemoryMeshEngine
    ) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="event_spine"):
            CaseRuntimeIntegration(case_engine, "not-a-spine", memory)  # type: ignore[arg-type]

    def test_rejects_wrong_type_for_memory_engine(
        self, case_engine: CaseRuntimeEngine, spine: EventSpineEngine
    ) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="memory_engine"):
            CaseRuntimeIntegration(case_engine, spine, 42)  # type: ignore[arg-type]


# ==================================================================
# Case creation methods (4 methods x 2 tests = 8 tests)
# ==================================================================

class TestCaseFromRecord:
    """case_from_record -> kind=AUDIT, severity=MEDIUM, source_type=record."""

    def test_returned_dict_shape(self, bridge: CaseRuntimeIntegration) -> None:
        result = bridge.case_from_record("c1", "t1", "rec-001")
        assert result["case_id"] == "c1"
        assert result["tenant_id"] == "t1"
        assert result["kind"] == "audit"
        assert result["severity"] == "medium"
        assert result["source_type"] == "record"
        assert result["source_id"] == "rec-001"
        assert "evidence_id" in result

    def test_auto_creates_evidence(
        self, bridge: CaseRuntimeIntegration, case_engine: CaseRuntimeEngine
    ) -> None:
        result = bridge.case_from_record("c1", "t1", "rec-001")
        evidence = case_engine.evidence_for_case("c1")
        assert len(evidence) == 1
        assert evidence[0].evidence_id == result["evidence_id"]
        assert evidence[0].source_type == "record"
        assert evidence[0].source_id == "rec-001"


class TestCaseFromFaultCampaign:
    """case_from_fault_campaign -> kind=FAULT_ANALYSIS, severity=HIGH, source_type=fault_campaign."""

    def test_returned_dict_shape(self, bridge: CaseRuntimeIntegration) -> None:
        result = bridge.case_from_fault_campaign("c2", "t1", "fc-001")
        assert result["case_id"] == "c2"
        assert result["kind"] == "fault_analysis"
        assert result["severity"] == "high"
        assert result["source_type"] == "fault_campaign"
        assert result["source_id"] == "fc-001"
        assert "evidence_id" in result

    def test_auto_creates_evidence(
        self, bridge: CaseRuntimeIntegration, case_engine: CaseRuntimeEngine
    ) -> None:
        bridge.case_from_fault_campaign("c2", "t1", "fc-001")
        evidence = case_engine.evidence_for_case("c2")
        assert len(evidence) == 1
        assert evidence[0].source_type == "fault_campaign"


class TestCaseFromControlFailure:
    """case_from_control_failure -> kind=COMPLIANCE, severity=HIGH, source_type=control_failure."""

    def test_returned_dict_shape(self, bridge: CaseRuntimeIntegration) -> None:
        result = bridge.case_from_control_failure("c3", "t1", "ctrl-001")
        assert result["case_id"] == "c3"
        assert result["kind"] == "compliance"
        assert result["severity"] == "high"
        assert result["source_type"] == "control_failure"
        assert result["source_id"] == "ctrl-001"
        assert "evidence_id" in result

    def test_auto_creates_evidence(
        self, bridge: CaseRuntimeIntegration, case_engine: CaseRuntimeEngine
    ) -> None:
        bridge.case_from_control_failure("c3", "t1", "ctrl-001")
        evidence = case_engine.evidence_for_case("c3")
        assert len(evidence) == 1
        assert evidence[0].source_type == "control_failure"


class TestCaseFromProgramRisk:
    """case_from_program_risk -> kind=OPERATIONAL, severity=MEDIUM, source_type=program_risk."""

    def test_returned_dict_shape(self, bridge: CaseRuntimeIntegration) -> None:
        result = bridge.case_from_program_risk("c4", "t1", "prog-001")
        assert result["case_id"] == "c4"
        assert result["kind"] == "operational"
        assert result["severity"] == "medium"
        assert result["source_type"] == "program_risk"
        assert result["source_id"] == "prog-001"
        assert "evidence_id" in result

    def test_auto_creates_evidence(
        self, bridge: CaseRuntimeIntegration, case_engine: CaseRuntimeEngine
    ) -> None:
        bridge.case_from_program_risk("c4", "t1", "prog-001")
        evidence = case_engine.evidence_for_case("c4")
        assert len(evidence) == 1
        assert evidence[0].source_type == "program_risk"


# ==================================================================
# Evidence attachment methods (4 methods x 2 tests = 8 tests)
# ==================================================================

class TestAttachMemoryAsEvidence:
    """attach_memory_as_evidence -> source_type=memory."""

    def test_returned_dict_shape(self, bridge: CaseRuntimeIntegration) -> None:
        bridge.case_from_record("c1", "t1", "rec-001")
        result = bridge.attach_memory_as_evidence("ev-m1", "c1", "mem-001")
        assert result["evidence_id"] == "ev-m1"
        assert result["case_id"] == "c1"
        assert result["source_type"] == "memory"
        assert result["source_id"] == "mem-001"

    def test_evidence_count_increments(
        self, bridge: CaseRuntimeIntegration, case_engine: CaseRuntimeEngine
    ) -> None:
        bridge.case_from_record("c1", "t1", "rec-001")
        before = case_engine.evidence_count
        bridge.attach_memory_as_evidence("ev-m1", "c1", "mem-001")
        assert case_engine.evidence_count == before + 1


class TestAttachArtifactAsEvidence:
    """attach_artifact_as_evidence -> source_type=artifact."""

    def test_returned_dict_shape(self, bridge: CaseRuntimeIntegration) -> None:
        bridge.case_from_record("c1", "t1", "rec-001")
        result = bridge.attach_artifact_as_evidence("ev-a1", "c1", "art-001")
        assert result["evidence_id"] == "ev-a1"
        assert result["case_id"] == "c1"
        assert result["source_type"] == "artifact"
        assert result["source_id"] == "art-001"

    def test_evidence_count_increments(
        self, bridge: CaseRuntimeIntegration, case_engine: CaseRuntimeEngine
    ) -> None:
        bridge.case_from_record("c1", "t1", "rec-001")
        before = case_engine.evidence_count
        bridge.attach_artifact_as_evidence("ev-a1", "c1", "art-001")
        assert case_engine.evidence_count == before + 1


class TestAttachEventAsEvidence:
    """attach_event_as_evidence -> source_type=event."""

    def test_returned_dict_shape(self, bridge: CaseRuntimeIntegration) -> None:
        bridge.case_from_record("c1", "t1", "rec-001")
        result = bridge.attach_event_as_evidence("ev-e1", "c1", "evt-001")
        assert result["evidence_id"] == "ev-e1"
        assert result["case_id"] == "c1"
        assert result["source_type"] == "event"
        assert result["source_id"] == "evt-001"

    def test_evidence_count_increments(
        self, bridge: CaseRuntimeIntegration, case_engine: CaseRuntimeEngine
    ) -> None:
        bridge.case_from_record("c1", "t1", "rec-001")
        before = case_engine.evidence_count
        bridge.attach_event_as_evidence("ev-e1", "c1", "evt-001")
        assert case_engine.evidence_count == before + 1


class TestAttachRecordAsEvidence:
    """attach_record_as_evidence -> source_type=record."""

    def test_returned_dict_shape(self, bridge: CaseRuntimeIntegration) -> None:
        bridge.case_from_record("c1", "t1", "rec-001")
        result = bridge.attach_record_as_evidence("ev-r1", "c1", "rec-002")
        assert result["evidence_id"] == "ev-r1"
        assert result["case_id"] == "c1"
        assert result["source_type"] == "record"
        assert result["source_id"] == "rec-002"

    def test_evidence_count_increments(
        self, bridge: CaseRuntimeIntegration, case_engine: CaseRuntimeEngine
    ) -> None:
        bridge.case_from_record("c1", "t1", "rec-001")
        before = case_engine.evidence_count
        bridge.attach_record_as_evidence("ev-r1", "c1", "rec-002")
        assert case_engine.evidence_count == before + 1


# ==================================================================
# Memory mesh and graph (3 tests)
# ==================================================================

class TestMemoryMeshAndGraph:
    """Memory mesh attachment and graph data extraction."""

    def test_attach_case_state_to_memory_mesh_creates_record_with_tags(
        self, bridge: CaseRuntimeIntegration
    ) -> None:
        bridge.case_from_record("c1", "t1", "rec-001")
        mem = bridge.attach_case_state_to_memory_mesh("scope-1")
        assert mem.memory_id  # non-empty
        assert mem.title == "Case state: scope-1"
        assert "case" in mem.tags
        assert "investigation" in mem.tags
        assert "evidence" in mem.tags
        assert mem.scope_ref_id == "scope-1"

    def test_attach_case_state_to_graph_returns_expected_keys(
        self, bridge: CaseRuntimeIntegration
    ) -> None:
        bridge.case_from_record("c1", "t1", "rec-001")
        graph = bridge.attach_case_state_to_graph("scope-1")
        expected_keys = {
            "scope_ref_id",
            "total_cases",
            "open_cases",
            "total_evidence",
            "total_reviews",
            "total_findings",
            "total_decisions",
            "total_violations",
        }
        assert set(graph.keys()) == expected_keys
        assert graph["scope_ref_id"] == "scope-1"

    def test_graph_data_matches_engine_state(
        self,
        bridge: CaseRuntimeIntegration,
        case_engine: CaseRuntimeEngine,
    ) -> None:
        bridge.case_from_record("c1", "t1", "rec-001")
        bridge.attach_memory_as_evidence("ev-m1", "c1", "mem-001")
        graph = bridge.attach_case_state_to_graph("scope-1")
        assert graph["total_cases"] == case_engine.case_count
        assert graph["open_cases"] == case_engine.open_case_count
        assert graph["total_evidence"] == case_engine.evidence_count
        assert graph["total_reviews"] == case_engine.review_count
        assert graph["total_findings"] == case_engine.finding_count
        assert graph["total_decisions"] == case_engine.decision_count
        assert graph["total_violations"] == case_engine.violation_count


# ==================================================================
# Events (1 test)
# ==================================================================

class TestEventEmission:
    """Events are emitted by bridge operations."""

    def test_event_count_increases_after_bridge_operations(
        self, spine: EventSpineEngine, bridge: CaseRuntimeIntegration
    ) -> None:
        before = spine.event_count
        bridge.case_from_record("c1", "t1", "rec-001")
        after_case = spine.event_count
        assert after_case > before, "case creation must emit events"

        bridge.attach_memory_as_evidence("ev-m1", "c1", "mem-001")
        after_attach = spine.event_count
        assert after_attach > after_case, "evidence attachment must emit events"

        bridge.attach_case_state_to_memory_mesh("scope-1")
        after_mesh = spine.event_count
        assert after_mesh > after_attach, "memory mesh attachment must emit events"


# ==================================================================
# Golden path (1 test)
# ==================================================================

class TestGoldenPath:
    """End-to-end: all 4 case types, all 4 evidence types, memory mesh, graph."""

    def test_full_lifecycle(
        self,
        spine: EventSpineEngine,
        case_engine: CaseRuntimeEngine,
        memory: MemoryMeshEngine,
    ) -> None:
        bridge = CaseRuntimeIntegration(case_engine, spine, memory)

        # --- Create all 4 case types ---
        r1 = bridge.case_from_record("c-rec", "t1", "rec-001")
        assert r1["kind"] == "audit"
        assert r1["severity"] == "medium"
        assert r1["source_type"] == "record"

        r2 = bridge.case_from_fault_campaign("c-fc", "t1", "fc-001")
        assert r2["kind"] == "fault_analysis"
        assert r2["severity"] == "high"
        assert r2["source_type"] == "fault_campaign"

        r3 = bridge.case_from_control_failure("c-ctrl", "t1", "ctrl-001")
        assert r3["kind"] == "compliance"
        assert r3["severity"] == "high"
        assert r3["source_type"] == "control_failure"

        r4 = bridge.case_from_program_risk("c-prog", "t1", "prog-001")
        assert r4["kind"] == "operational"
        assert r4["severity"] == "medium"
        assert r4["source_type"] == "program_risk"

        assert case_engine.case_count == 4
        # Each case auto-creates 1 evidence item
        assert case_engine.evidence_count == 4

        # --- Attach all 4 evidence types to the first case ---
        bridge.attach_memory_as_evidence("ev-mem", "c-rec", "mem-001")
        bridge.attach_artifact_as_evidence("ev-art", "c-rec", "art-001")
        bridge.attach_event_as_evidence("ev-evt", "c-rec", "evt-001")
        bridge.attach_record_as_evidence("ev-rec", "c-rec", "rec-002")

        # 4 auto-created + 4 manually attached
        assert case_engine.evidence_count == 8

        # Evidence for c-rec: 1 auto + 4 manual = 5
        rec_evidence = case_engine.evidence_for_case("c-rec")
        assert len(rec_evidence) == 5

        # --- Memory mesh ---
        mem_record = bridge.attach_case_state_to_memory_mesh("golden-scope")
        assert mem_record.memory_id
        assert "case" in mem_record.tags
        assert mem_record.content["total_cases"] == 4
        assert mem_record.content["total_evidence"] == 8

        # --- Graph ---
        graph = bridge.attach_case_state_to_graph("golden-scope")
        assert graph["total_cases"] == 4
        assert graph["open_cases"] == 4
        assert graph["total_evidence"] == 8
        assert graph["total_reviews"] == 0
        assert graph["total_findings"] == 0
        assert graph["total_decisions"] == 0
        assert graph["total_violations"] == 0

        # --- Events were emitted throughout ---
        assert spine.event_count > 0
