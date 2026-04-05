"""Comprehensive tests for AssuranceRuntimeIntegration bridge."""

from __future__ import annotations

import pytest

from mcoi_runtime.core.assurance_runtime import AssuranceRuntimeEngine
from mcoi_runtime.core.assurance_runtime_integration import AssuranceRuntimeIntegration
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def event_spine() -> EventSpineEngine:
    return EventSpineEngine()


@pytest.fixture()
def assurance_engine(event_spine: EventSpineEngine) -> AssuranceRuntimeEngine:
    return AssuranceRuntimeEngine(event_spine)


@pytest.fixture()
def memory_engine() -> MemoryMeshEngine:
    return MemoryMeshEngine()


@pytest.fixture()
def bridge(
    assurance_engine: AssuranceRuntimeEngine,
    event_spine: EventSpineEngine,
    memory_engine: MemoryMeshEngine,
) -> AssuranceRuntimeIntegration:
    return AssuranceRuntimeIntegration(assurance_engine, event_spine, memory_engine)


# ===================================================================
# Constructor validation (3 tests)
# ===================================================================


class TestConstructorValidation:
    """Rejects wrong types for each constructor argument."""

    def test_rejects_wrong_assurance_engine(
        self, event_spine: EventSpineEngine, memory_engine: MemoryMeshEngine
    ) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            AssuranceRuntimeIntegration("not-an-engine", event_spine, memory_engine)

    def test_rejects_wrong_event_spine(
        self, assurance_engine: AssuranceRuntimeEngine, memory_engine: MemoryMeshEngine
    ) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            AssuranceRuntimeIntegration(assurance_engine, "not-a-spine", memory_engine)

    def test_rejects_wrong_memory_engine(
        self,
        assurance_engine: AssuranceRuntimeEngine,
        event_spine: EventSpineEngine,
    ) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            AssuranceRuntimeIntegration(assurance_engine, event_spine, 42)


# ===================================================================
# Attestation creation (3 methods x 2 tests = 6 tests)
# ===================================================================


class TestAssuranceFromControlTests:
    """assurance_from_control_tests: scope=control, source_type=control_test."""

    def test_dict_shape(self, bridge: AssuranceRuntimeIntegration) -> None:
        result = bridge.assurance_from_control_tests(
            "att-ct-1", "tenant-1", "ctrl-100"
        )
        assert result["attestation_id"] == "att-ct-1"
        assert result["tenant_id"] == "tenant-1"
        assert result["scope"] == "control"
        assert result["scope_ref_id"] == "ctrl-100"
        assert result["source_type"] == "control_test"

    def test_attestation_count_increments(
        self,
        bridge: AssuranceRuntimeIntegration,
        assurance_engine: AssuranceRuntimeEngine,
    ) -> None:
        assert assurance_engine.attestation_count == 0
        bridge.assurance_from_control_tests("att-ct-2", "tenant-1", "ctrl-200")
        assert assurance_engine.attestation_count == 1
        bridge.assurance_from_control_tests("att-ct-3", "tenant-1", "ctrl-201")
        assert assurance_engine.attestation_count == 2


class TestAssuranceFromCaseClosure:
    """assurance_from_case_closure: scope=control, source_type=case_closure."""

    def test_dict_shape(self, bridge: AssuranceRuntimeIntegration) -> None:
        result = bridge.assurance_from_case_closure(
            "att-cc-1", "tenant-2", "case-500"
        )
        assert result["attestation_id"] == "att-cc-1"
        assert result["tenant_id"] == "tenant-2"
        assert result["scope"] == "control"
        assert result["scope_ref_id"] == "case-500"
        assert result["source_type"] == "case_closure"

    def test_attestation_count_increments(
        self,
        bridge: AssuranceRuntimeIntegration,
        assurance_engine: AssuranceRuntimeEngine,
    ) -> None:
        assert assurance_engine.attestation_count == 0
        bridge.assurance_from_case_closure("att-cc-2", "tenant-2", "case-501")
        assert assurance_engine.attestation_count == 1


class TestAssuranceFromRemediation:
    """assurance_from_remediation: scope=control, source_type=remediation."""

    def test_dict_shape(self, bridge: AssuranceRuntimeIntegration) -> None:
        result = bridge.assurance_from_remediation(
            "att-rem-1", "tenant-3", "rem-700"
        )
        assert result["attestation_id"] == "att-rem-1"
        assert result["tenant_id"] == "tenant-3"
        assert result["scope"] == "control"
        assert result["scope_ref_id"] == "rem-700"
        assert result["source_type"] == "remediation"

    def test_attestation_count_increments(
        self,
        bridge: AssuranceRuntimeIntegration,
        assurance_engine: AssuranceRuntimeEngine,
    ) -> None:
        assert assurance_engine.attestation_count == 0
        bridge.assurance_from_remediation("att-rem-2", "tenant-3", "rem-701")
        assert assurance_engine.attestation_count == 1


# ===================================================================
# Certification creation (2 methods x 2 tests = 4 tests)
# ===================================================================


class TestAssuranceFromProgramHealth:
    """assurance_from_program_health: scope=program, source_type=program_health."""

    def test_dict_shape(self, bridge: AssuranceRuntimeIntegration) -> None:
        result = bridge.assurance_from_program_health(
            "cert-ph-1", "tenant-4", "prog-10"
        )
        assert result["certification_id"] == "cert-ph-1"
        assert result["tenant_id"] == "tenant-4"
        assert result["scope"] == "program"
        assert result["scope_ref_id"] == "prog-10"
        assert result["source_type"] == "program_health"

    def test_certification_count_increments(
        self,
        bridge: AssuranceRuntimeIntegration,
        assurance_engine: AssuranceRuntimeEngine,
    ) -> None:
        assert assurance_engine.certification_count == 0
        bridge.assurance_from_program_health("cert-ph-2", "tenant-4", "prog-11")
        assert assurance_engine.certification_count == 1
        bridge.assurance_from_program_health("cert-ph-3", "tenant-4", "prog-12")
        assert assurance_engine.certification_count == 2


class TestAssuranceFromConnectorStability:
    """assurance_from_connector_stability: scope=connector, source_type=connector_stability."""

    def test_dict_shape(self, bridge: AssuranceRuntimeIntegration) -> None:
        result = bridge.assurance_from_connector_stability(
            "cert-cs-1", "tenant-5", "conn-20"
        )
        assert result["certification_id"] == "cert-cs-1"
        assert result["tenant_id"] == "tenant-5"
        assert result["scope"] == "connector"
        assert result["scope_ref_id"] == "conn-20"
        assert result["source_type"] == "connector_stability"

    def test_certification_count_increments(
        self,
        bridge: AssuranceRuntimeIntegration,
        assurance_engine: AssuranceRuntimeEngine,
    ) -> None:
        assert assurance_engine.certification_count == 0
        bridge.assurance_from_connector_stability("cert-cs-2", "tenant-5", "conn-21")
        assert assurance_engine.certification_count == 1


# ===================================================================
# Evidence binding (3 methods x 2 tests = 6 tests)
# ===================================================================


class TestBindRecordEvidence:
    """bind_record_evidence: source_type=record."""

    def test_dict_shape(self, bridge: AssuranceRuntimeIntegration) -> None:
        result = bridge.bind_record_evidence(
            "bind-r-1", "att-1", "attestation", "rec-100"
        )
        assert result["binding_id"] == "bind-r-1"
        assert result["target_id"] == "att-1"
        assert result["source_type"] == "record"
        assert result["source_id"] == "rec-100"

    def test_binding_count_increments(
        self,
        bridge: AssuranceRuntimeIntegration,
        assurance_engine: AssuranceRuntimeEngine,
    ) -> None:
        assert assurance_engine.binding_count == 0
        bridge.bind_record_evidence("bind-r-2", "att-1", "attestation", "rec-101")
        assert assurance_engine.binding_count == 1
        bridge.bind_record_evidence("bind-r-3", "att-1", "attestation", "rec-102")
        assert assurance_engine.binding_count == 2


class TestBindMemoryEvidence:
    """bind_memory_evidence: source_type=memory."""

    def test_dict_shape(self, bridge: AssuranceRuntimeIntegration) -> None:
        result = bridge.bind_memory_evidence(
            "bind-m-1", "att-2", "attestation", "mem-200"
        )
        assert result["binding_id"] == "bind-m-1"
        assert result["target_id"] == "att-2"
        assert result["source_type"] == "memory"
        assert result["source_id"] == "mem-200"

    def test_binding_count_increments(
        self,
        bridge: AssuranceRuntimeIntegration,
        assurance_engine: AssuranceRuntimeEngine,
    ) -> None:
        assert assurance_engine.binding_count == 0
        bridge.bind_memory_evidence("bind-m-2", "cert-1", "certification", "mem-201")
        assert assurance_engine.binding_count == 1


class TestBindEventEvidence:
    """bind_event_evidence: source_type=event."""

    def test_dict_shape(self, bridge: AssuranceRuntimeIntegration) -> None:
        result = bridge.bind_event_evidence(
            "bind-e-1", "cert-3", "certification", "evt-300"
        )
        assert result["binding_id"] == "bind-e-1"
        assert result["target_id"] == "cert-3"
        assert result["source_type"] == "event"
        assert result["source_id"] == "evt-300"

    def test_binding_count_increments(
        self,
        bridge: AssuranceRuntimeIntegration,
        assurance_engine: AssuranceRuntimeEngine,
    ) -> None:
        assert assurance_engine.binding_count == 0
        bridge.bind_event_evidence("bind-e-2", "att-5", "attestation", "evt-301")
        assert assurance_engine.binding_count == 1


# ===================================================================
# Memory mesh and graph (3 tests)
# ===================================================================


class TestMemoryMeshAndGraph:
    """Memory mesh attachment and graph output."""

    def test_attach_assurance_to_memory_mesh_creates_record_with_tags(
        self, bridge: AssuranceRuntimeIntegration
    ) -> None:
        bridge.assurance_from_control_tests("att-mm-1", "t1", "ctrl-mm")
        mem = bridge.attach_assurance_to_memory_mesh("ctrl-mm")
        assert mem.title == "Assurance state"
        assert "ctrl-mm" not in mem.title
        assert "assurance" in mem.tags
        assert "attestation" in mem.tags
        assert "certification" in mem.tags
        assert mem.scope_ref_id == "ctrl-mm"

    def test_attach_assurance_to_graph_returns_expected_keys(
        self, bridge: AssuranceRuntimeIntegration
    ) -> None:
        result = bridge.attach_assurance_to_graph("ref-g-1")
        expected_keys = {
            "scope_ref_id",
            "total_attestations",
            "granted_attestations",
            "total_certifications",
            "active_certifications",
            "total_assessments",
            "total_evidence_bindings",
            "total_violations",
        }
        assert set(result.keys()) == expected_keys

    def test_graph_data_matches_engine_state(
        self,
        bridge: AssuranceRuntimeIntegration,
        assurance_engine: AssuranceRuntimeEngine,
    ) -> None:
        bridge.assurance_from_control_tests("att-g-1", "t1", "ctrl-g")
        bridge.assurance_from_program_health("cert-g-1", "t1", "prog-g")
        bridge.bind_record_evidence("bind-g-1", "att-g-1", "attestation", "rec-g")

        result = bridge.attach_assurance_to_graph("scope-g")
        assert result["scope_ref_id"] == "scope-g"
        assert result["total_attestations"] == assurance_engine.attestation_count
        assert result["granted_attestations"] == assurance_engine.granted_attestation_count
        assert result["total_certifications"] == assurance_engine.certification_count
        assert result["active_certifications"] == assurance_engine.active_certification_count
        assert result["total_assessments"] == assurance_engine.assessment_count
        assert result["total_evidence_bindings"] == assurance_engine.binding_count
        assert result["total_violations"] == assurance_engine.violation_count


# ===================================================================
# Events (1 test)
# ===================================================================


class TestEvents:
    """Event emission after operations."""

    def test_event_count_increases_after_operations(
        self,
        bridge: AssuranceRuntimeIntegration,
        event_spine: EventSpineEngine,
    ) -> None:
        initial = event_spine.event_count
        bridge.assurance_from_control_tests("att-ev-1", "t1", "ctrl-ev")
        after_att = event_spine.event_count
        assert after_att > initial

        bridge.bind_record_evidence("bind-ev-1", "att-ev-1", "attestation", "rec-ev")
        after_bind = event_spine.event_count
        assert after_bind > after_att

        bridge.attach_assurance_to_memory_mesh("ctrl-ev")
        after_mem = event_spine.event_count
        assert after_mem > after_bind


# ===================================================================
# Golden path (1 test)
# ===================================================================


class TestGoldenPath:
    """End-to-end: all creation + binding + memory + graph."""

    def test_full_lifecycle(
        self,
        bridge: AssuranceRuntimeIntegration,
        assurance_engine: AssuranceRuntimeEngine,
        event_spine: EventSpineEngine,
    ) -> None:
        # --- Attestation creation (all three flavours) ---
        att_ct = bridge.assurance_from_control_tests("att-gp-1", "t-gp", "ctrl-gp")
        assert att_ct["source_type"] == "control_test"
        assert att_ct["scope"] == "control"

        att_cc = bridge.assurance_from_case_closure("att-gp-2", "t-gp", "case-gp")
        assert att_cc["source_type"] == "case_closure"

        att_rem = bridge.assurance_from_remediation("att-gp-3", "t-gp", "rem-gp")
        assert att_rem["source_type"] == "remediation"

        assert assurance_engine.attestation_count == 3

        # --- Certification creation (both flavours) ---
        cert_ph = bridge.assurance_from_program_health("cert-gp-1", "t-gp", "prog-gp")
        assert cert_ph["source_type"] == "program_health"
        assert cert_ph["scope"] == "program"

        cert_cs = bridge.assurance_from_connector_stability("cert-gp-2", "t-gp", "conn-gp")
        assert cert_cs["source_type"] == "connector_stability"
        assert cert_cs["scope"] == "connector"

        assert assurance_engine.certification_count == 2

        # --- Evidence binding (all three flavours) ---
        br = bridge.bind_record_evidence("bind-gp-1", "att-gp-1", "attestation", "rec-gp")
        assert br["source_type"] == "record"

        bm = bridge.bind_memory_evidence("bind-gp-2", "att-gp-2", "attestation", "mem-gp")
        assert bm["source_type"] == "memory"

        be = bridge.bind_event_evidence("bind-gp-3", "cert-gp-1", "certification", "evt-gp")
        assert be["source_type"] == "event"

        assert assurance_engine.binding_count == 3

        # --- Memory mesh attachment ---
        mem = bridge.attach_assurance_to_memory_mesh("scope-gp")
        assert "assurance" in mem.tags
        assert mem.content["total_attestations"] == 3
        assert mem.content["total_certifications"] == 2
        assert mem.content["total_evidence_bindings"] == 3

        # --- Graph attachment ---
        graph = bridge.attach_assurance_to_graph("scope-gp")
        assert graph["total_attestations"] == 3
        assert graph["total_certifications"] == 2
        assert graph["total_evidence_bindings"] == 3

        # --- Events were emitted throughout ---
        assert event_spine.event_count > 0
