"""Comprehensive tests for mcoi.mcoi_runtime.core.regulatory_reporting_integration."""

from __future__ import annotations

import pytest

from mcoi_runtime.core.regulatory_reporting import RegulatoryReportingEngine
from mcoi_runtime.core.regulatory_reporting_integration import (
    RegulatoryReportingIntegration,
)
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


def _setup():
    es = EventSpineEngine()
    re = RegulatoryReportingEngine(es)
    mm = MemoryMeshEngine()
    ri = RegulatoryReportingIntegration(re, es, mm)
    return ri, re, es, mm


def _setup_with_requirement():
    """Setup with a pre-registered requirement for package assembly tests."""
    ri, re, es, mm = _setup()
    re.register_requirement("req-1", "tenant-1", "Test Requirement")
    return ri, re, es, mm


# ===================================================================
# 1. TestConstructorValidation
# ===================================================================


class TestConstructorValidation:
    """Wrong types for all 3 constructor params."""

    def test_reject_wrong_reporting_engine_none(self):
        es = EventSpineEngine()
        mm = MemoryMeshEngine()
        with pytest.raises(RuntimeCoreInvariantError):
            RegulatoryReportingIntegration(None, es, mm)

    def test_reject_wrong_reporting_engine_string(self):
        es = EventSpineEngine()
        mm = MemoryMeshEngine()
        with pytest.raises(RuntimeCoreInvariantError):
            RegulatoryReportingIntegration("bad", es, mm)

    def test_reject_wrong_event_spine_none(self):
        es = EventSpineEngine()
        re = RegulatoryReportingEngine(es)
        mm = MemoryMeshEngine()
        with pytest.raises(RuntimeCoreInvariantError):
            RegulatoryReportingIntegration(re, None, mm)

    def test_reject_wrong_event_spine_string(self):
        es = EventSpineEngine()
        re = RegulatoryReportingEngine(es)
        mm = MemoryMeshEngine()
        with pytest.raises(RuntimeCoreInvariantError):
            RegulatoryReportingIntegration(re, "bad", mm)

    def test_reject_wrong_memory_engine_none(self):
        es = EventSpineEngine()
        re = RegulatoryReportingEngine(es)
        with pytest.raises(RuntimeCoreInvariantError):
            RegulatoryReportingIntegration(re, es, None)

    def test_reject_wrong_memory_engine_string(self):
        es = EventSpineEngine()
        re = RegulatoryReportingEngine(es)
        with pytest.raises(RuntimeCoreInvariantError):
            RegulatoryReportingIntegration(re, es, "bad")

    def test_valid_construction(self):
        ri, re, es, mm = _setup()
        assert ri is not None


# ===================================================================
# 2. TestPackageFromAssurance
# ===================================================================


class TestPackageFromAssurance:
    """Test package_from_assurance method."""

    def test_returns_dict(self):
        ri, re, es, mm = _setup_with_requirement()
        result = ri.package_from_assurance("pkg-1", "tenant-1", "req-1", ("e1", "e2"))
        assert isinstance(result, dict)

    def test_dict_shape(self):
        ri, re, es, mm = _setup_with_requirement()
        result = ri.package_from_assurance("pkg-1", "tenant-1", "req-1", ("e1", "e2"))
        assert set(result.keys()) == {
            "package_id", "tenant_id", "completeness",
            "total_evidence_items", "source_type",
        }

    def test_source_type(self):
        ri, re, es, mm = _setup_with_requirement()
        result = ri.package_from_assurance("pkg-1", "tenant-1", "req-1", ("e1",))
        assert result["source_type"] == "assurance"

    def test_completeness_incomplete(self):
        ri, re, es, mm = _setup_with_requirement()
        result = ri.package_from_assurance("pkg-1", "tenant-1", "req-1", ())
        assert result["completeness"] == "incomplete"
        assert result["total_evidence_items"] == 0

    def test_completeness_partial(self):
        ri, re, es, mm = _setup_with_requirement()
        result = ri.package_from_assurance("pkg-1", "tenant-1", "req-1", ("e1",))
        assert result["completeness"] == "partial"
        assert result["total_evidence_items"] == 1

    def test_completeness_complete(self):
        ri, re, es, mm = _setup_with_requirement()
        result = ri.package_from_assurance("pkg-1", "tenant-1", "req-1", ("e1", "e2"))
        assert result["completeness"] == "complete"
        assert result["total_evidence_items"] == 2

    def test_completeness_verified(self):
        ri, re, es, mm = _setup_with_requirement()
        result = ri.package_from_assurance(
            "pkg-1", "tenant-1", "req-1", ("e1", "e2", "e3", "e4"),
        )
        assert result["completeness"] == "verified"
        assert result["total_evidence_items"] == 4


# ===================================================================
# 3. TestPackageFromCaseClosure
# ===================================================================


class TestPackageFromCaseClosure:
    """Test package_from_case_closure method."""

    def test_source_type(self):
        ri, re, es, mm = _setup_with_requirement()
        result = ri.package_from_case_closure("pkg-1", "tenant-1", "req-1", ("e1", "e2"))
        assert result["source_type"] == "case_closure"

    def test_dict_shape(self):
        ri, re, es, mm = _setup_with_requirement()
        result = ri.package_from_case_closure("pkg-1", "tenant-1", "req-1", ("e1",))
        assert set(result.keys()) == {
            "package_id", "tenant_id", "completeness",
            "total_evidence_items", "source_type",
        }

    def test_completeness_partial(self):
        ri, re, es, mm = _setup_with_requirement()
        result = ri.package_from_case_closure("pkg-1", "tenant-1", "req-1", ("e1",))
        assert result["completeness"] == "partial"


# ===================================================================
# 4. TestPackageFromRemediation
# ===================================================================


class TestPackageFromRemediation:
    """Test package_from_remediation method."""

    def test_source_type(self):
        ri, re, es, mm = _setup_with_requirement()
        result = ri.package_from_remediation("pkg-1", "tenant-1", "req-1", ("e1", "e2", "e3"))
        assert result["source_type"] == "remediation"

    def test_completeness_complete_three_items(self):
        ri, re, es, mm = _setup_with_requirement()
        result = ri.package_from_remediation("pkg-1", "tenant-1", "req-1", ("e1", "e2", "e3"))
        assert result["completeness"] == "complete"
        assert result["total_evidence_items"] == 3


# ===================================================================
# 5. TestPackageFromRecords
# ===================================================================


class TestPackageFromRecords:
    """Test package_from_records method."""

    def test_source_type(self):
        ri, re, es, mm = _setup_with_requirement()
        result = ri.package_from_records("pkg-1", "tenant-1", "req-1", ("e1",))
        assert result["source_type"] == "records"

    def test_completeness_verified(self):
        ri, re, es, mm = _setup_with_requirement()
        result = ri.package_from_records(
            "pkg-1", "tenant-1", "req-1", ("e1", "e2", "e3", "e4", "e5"),
        )
        assert result["completeness"] == "verified"
        assert result["total_evidence_items"] == 5


# ===================================================================
# 6. TestPackageFromControlHistory
# ===================================================================


class TestPackageFromControlHistory:
    """Test package_from_control_history method."""

    def test_source_type(self):
        ri, re, es, mm = _setup_with_requirement()
        result = ri.package_from_control_history("pkg-1", "tenant-1", "req-1", ("e1", "e2"))
        assert result["source_type"] == "control_history"

    def test_dict_shape(self):
        ri, re, es, mm = _setup_with_requirement()
        result = ri.package_from_control_history("pkg-1", "tenant-1", "req-1", ("e1",))
        assert set(result.keys()) == {
            "package_id", "tenant_id", "completeness",
            "total_evidence_items", "source_type",
        }

    def test_completeness_incomplete(self):
        ri, re, es, mm = _setup_with_requirement()
        result = ri.package_from_control_history("pkg-1", "tenant-1", "req-1", ())
        assert result["completeness"] == "incomplete"
        assert result["total_evidence_items"] == 0


# ===================================================================
# 7. TestMemoryMeshAttachment
# ===================================================================


class TestMemoryMeshAttachment:
    """Test attach_reporting_package_to_memory_mesh."""

    def test_returns_memory_record(self):
        ri, re, es, mm = _setup_with_requirement()
        from mcoi_runtime.contracts.memory_mesh import MemoryRecord
        mem = ri.attach_reporting_package_to_memory_mesh("scope-1")
        assert isinstance(mem, MemoryRecord)

    def test_tags(self):
        ri, re, es, mm = _setup_with_requirement()
        mem = ri.attach_reporting_package_to_memory_mesh("scope-1")
        assert mem.tags == ("regulatory", "reporting", "submission")

    def test_memory_stored_in_mesh(self):
        ri, re, es, mm = _setup_with_requirement()
        mem = ri.attach_reporting_package_to_memory_mesh("scope-1")
        stored = mm.get_memory(mem.memory_id)
        assert stored is not None
        assert stored.memory_id == mem.memory_id

    def test_scope_ref_id_in_content(self):
        ri, re, es, mm = _setup_with_requirement()
        mem = ri.attach_reporting_package_to_memory_mesh("scope-ref-42")
        assert mem.scope_ref_id == "scope-ref-42"


# ===================================================================
# 8. TestGraphAttachment
# ===================================================================


class TestGraphAttachment:
    """Test attach_reporting_package_to_graph."""

    EXPECTED_KEYS = {
        "scope_ref_id", "total_requirements", "total_windows",
        "total_packages", "total_submissions", "total_reviews",
        "total_auditor_requests", "total_auditor_responses",
        "total_violations",
    }

    def test_returns_dict(self):
        ri, re, es, mm = _setup_with_requirement()
        result = ri.attach_reporting_package_to_graph("scope-1")
        assert isinstance(result, dict)

    def test_dict_keys(self):
        ri, re, es, mm = _setup_with_requirement()
        result = ri.attach_reporting_package_to_graph("scope-1")
        assert set(result.keys()) == self.EXPECTED_KEYS

    def test_values_match_engine_state(self):
        ri, re, es, mm = _setup_with_requirement()
        ri.package_from_assurance("pkg-1", "tenant-1", "req-1", ("e1", "e2"))
        result = ri.attach_reporting_package_to_graph("scope-1")
        assert result["scope_ref_id"] == "scope-1"
        assert result["total_requirements"] == re.requirement_count
        assert result["total_windows"] == re.window_count
        assert result["total_packages"] == re.package_count
        assert result["total_submissions"] == re.submission_count
        assert result["total_reviews"] == re.review_count
        assert result["total_auditor_requests"] == re.auditor_request_count
        assert result["total_auditor_responses"] == re.auditor_response_count
        assert result["total_violations"] == re.violation_count

    def test_empty_engine_counts_zero(self):
        ri, re, es, mm = _setup()
        result = ri.attach_reporting_package_to_graph("scope-1")
        assert result["total_requirements"] == 0
        assert result["total_packages"] == 0
        assert result["total_submissions"] == 0


# ===================================================================
# 9. TestEventEmission
# ===================================================================


class TestEventEmission:
    """Test that bridge methods emit events to the event spine."""

    def test_package_emits_event(self):
        ri, re, es, mm = _setup_with_requirement()
        before = es.event_count
        ri.package_from_assurance("pkg-1", "tenant-1", "req-1", ("e1",))
        after = es.event_count
        assert after > before

    def test_case_closure_emits_event(self):
        ri, re, es, mm = _setup_with_requirement()
        before = es.event_count
        ri.package_from_case_closure("pkg-1", "tenant-1", "req-1", ("e1",))
        assert es.event_count > before

    def test_remediation_emits_event(self):
        ri, re, es, mm = _setup_with_requirement()
        before = es.event_count
        ri.package_from_remediation("pkg-1", "tenant-1", "req-1", ("e1",))
        assert es.event_count > before

    def test_records_emits_event(self):
        ri, re, es, mm = _setup_with_requirement()
        before = es.event_count
        ri.package_from_records("pkg-1", "tenant-1", "req-1", ("e1",))
        assert es.event_count > before

    def test_control_history_emits_event(self):
        ri, re, es, mm = _setup_with_requirement()
        before = es.event_count
        ri.package_from_control_history("pkg-1", "tenant-1", "req-1", ("e1",))
        assert es.event_count > before

    def test_memory_attach_emits_event(self):
        ri, re, es, mm = _setup_with_requirement()
        before = es.event_count
        ri.attach_reporting_package_to_memory_mesh("scope-1")
        assert es.event_count > before


# ===================================================================
# 10. TestGoldenPath
# ===================================================================


class TestGoldenPath:
    """Full lifecycle: register requirement, assemble packages via multiple
    source types, attach to memory mesh, attach to graph, verify counts."""

    def test_full_lifecycle(self):
        ri, re, es, mm = _setup()

        # Register a requirement
        re.register_requirement("req-gold", "tenant-gold", "Golden Requirement")

        # Assemble packages from all five source types
        pkg_assurance = ri.package_from_assurance(
            "pkg-a", "tenant-gold", "req-gold", ("ea1", "ea2"),
        )
        assert pkg_assurance["source_type"] == "assurance"
        assert pkg_assurance["completeness"] == "complete"

        pkg_case = ri.package_from_case_closure(
            "pkg-b", "tenant-gold", "req-gold", ("ec1",),
        )
        assert pkg_case["source_type"] == "case_closure"
        assert pkg_case["completeness"] == "partial"

        pkg_rem = ri.package_from_remediation(
            "pkg-c", "tenant-gold", "req-gold", ("er1", "er2", "er3", "er4"),
        )
        assert pkg_rem["source_type"] == "remediation"
        assert pkg_rem["completeness"] == "verified"

        pkg_rec = ri.package_from_records(
            "pkg-d", "tenant-gold", "req-gold", (),
        )
        assert pkg_rec["source_type"] == "records"
        assert pkg_rec["completeness"] == "incomplete"

        pkg_ctrl = ri.package_from_control_history(
            "pkg-e", "tenant-gold", "req-gold", ("ec1", "ec2", "ec3"),
        )
        assert pkg_ctrl["source_type"] == "control_history"
        assert pkg_ctrl["completeness"] == "complete"

        # Attach to memory mesh
        mem = ri.attach_reporting_package_to_memory_mesh("scope-gold")
        assert mem.tags == ("regulatory", "reporting", "submission")
        assert mm.get_memory(mem.memory_id) is not None

        # Attach to graph
        graph = ri.attach_reporting_package_to_graph("scope-gold")
        assert graph["scope_ref_id"] == "scope-gold"
        assert graph["total_requirements"] == 1
        assert graph["total_packages"] == 5

        # Events were emitted throughout
        assert es.event_count > 0
