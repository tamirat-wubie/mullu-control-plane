"""Tests for assurance / attestation / certification runtime contracts."""

from __future__ import annotations

import dataclasses
from types import MappingProxyType

import pytest

from mcoi_runtime.contracts.assurance_runtime import (
    AssuranceAssessment,
    AssuranceClosureReport,
    AssuranceDecision,
    AssuranceEvidenceBinding,
    AssuranceFinding,
    AssuranceLevel,
    AssuranceScope,
    AssuranceSnapshot,
    AssuranceViolation,
    AttestationRecord,
    AttestationStatus,
    CertificationRecord,
    CertificationStatus,
    EvidenceSufficiency,
    RecertificationStatus,
    RecertificationWindow,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TS = "2025-06-01T12:00:00+00:00"
TS2 = "2025-06-15T09:00:00+00:00"


def _attestation(**overrides) -> AttestationRecord:
    defaults = dict(
        attestation_id="att-001",
        tenant_id="t-001",
        scope=AssuranceScope.CONTROL,
        scope_ref_id="ref-001",
        level=AssuranceLevel.HIGH,
        status=AttestationStatus.GRANTED,
        attested_by="auditor-1",
        attested_at=TS,
        expires_at=TS2,
    )
    defaults.update(overrides)
    return AttestationRecord(**defaults)


def _certification(**overrides) -> CertificationRecord:
    defaults = dict(
        certification_id="cert-001",
        tenant_id="t-001",
        scope=AssuranceScope.PROGRAM,
        scope_ref_id="ref-001",
        status=CertificationStatus.ACTIVE,
        level=AssuranceLevel.MODERATE,
        certified_by="certifier-1",
        certified_at=TS,
        expires_at=TS2,
    )
    defaults.update(overrides)
    return CertificationRecord(**defaults)


def _assessment(**overrides) -> AssuranceAssessment:
    defaults = dict(
        assessment_id="assess-001",
        tenant_id="t-001",
        scope=AssuranceScope.WORKSPACE,
        scope_ref_id="ref-001",
        level=AssuranceLevel.LOW,
        sufficiency=EvidenceSufficiency.SUFFICIENT,
        confidence=0.85,
        assessed_by="assessor-1",
        assessed_at=TS,
    )
    defaults.update(overrides)
    return AssuranceAssessment(**defaults)


def _evidence_binding(**overrides) -> AssuranceEvidenceBinding:
    defaults = dict(
        binding_id="bind-001",
        target_id="att-001",
        target_type="attestation",
        source_type="document",
        source_id="doc-001",
        bound_at=TS,
    )
    defaults.update(overrides)
    return AssuranceEvidenceBinding(**defaults)


def _recertification_window(**overrides) -> RecertificationWindow:
    defaults = dict(
        window_id="win-001",
        certification_id="cert-001",
        status=RecertificationStatus.SCHEDULED,
        starts_at=TS,
        ends_at=TS2,
        completed_at=TS2,
    )
    defaults.update(overrides)
    return RecertificationWindow(**defaults)


def _finding(**overrides) -> AssuranceFinding:
    defaults = dict(
        finding_id="find-001",
        target_id="att-001",
        target_type="attestation",
        description="gap found",
        impact_level=AssuranceLevel.MODERATE,
        detected_at=TS,
    )
    defaults.update(overrides)
    return AssuranceFinding(**defaults)


def _decision(**overrides) -> AssuranceDecision:
    defaults = dict(
        decision_id="dec-001",
        target_id="att-001",
        target_type="attestation",
        level=AssuranceLevel.HIGH,
        decided_by="decider-1",
        reason="all checks passed",
        decided_at=TS,
    )
    defaults.update(overrides)
    return AssuranceDecision(**defaults)


def _snapshot(**overrides) -> AssuranceSnapshot:
    defaults = dict(
        snapshot_id="snap-001",
        scope_ref_id="ref-001",
        total_attestations=10,
        granted_attestations=8,
        total_certifications=5,
        active_certifications=3,
        total_assessments=7,
        total_evidence_bindings=20,
        total_violations=1,
        captured_at=TS,
    )
    defaults.update(overrides)
    return AssuranceSnapshot(**defaults)


def _violation(**overrides) -> AssuranceViolation:
    defaults = dict(
        violation_id="viol-001",
        target_id="att-001",
        target_type="attestation",
        tenant_id="t-001",
        operation="revoke",
        reason="policy breach",
        detected_at=TS,
    )
    defaults.update(overrides)
    return AssuranceViolation(**defaults)


def _closure_report(**overrides) -> AssuranceClosureReport:
    defaults = dict(
        report_id="rep-001",
        target_id="att-001",
        target_type="attestation",
        tenant_id="t-001",
        final_level=AssuranceLevel.FULL,
        total_evidence_bindings=15,
        total_assessments=4,
        total_findings=2,
        total_violations=0,
        closed_at=TS,
    )
    defaults.update(overrides)
    return AssuranceClosureReport(**defaults)


# ===================================================================
# Enum tests
# ===================================================================


class TestAttestationStatus:
    def test_member_count(self):
        assert len(AttestationStatus) == 5

    def test_names(self):
        assert {m.name for m in AttestationStatus} == {
            "PENDING", "GRANTED", "DENIED", "REVOKED", "EXPIRED",
        }

    def test_values(self):
        assert AttestationStatus.PENDING.value == "pending"
        assert AttestationStatus.GRANTED.value == "granted"
        assert AttestationStatus.DENIED.value == "denied"
        assert AttestationStatus.REVOKED.value == "revoked"
        assert AttestationStatus.EXPIRED.value == "expired"

    def test_fail_closed_default(self):
        """Fail-closed: default is PENDING (not GRANTED)."""
        assert AttestationStatus.PENDING.value == "pending"


class TestCertificationStatus:
    def test_member_count(self):
        assert len(CertificationStatus) == 6

    def test_names(self):
        assert {m.name for m in CertificationStatus} == {
            "PENDING", "ACTIVE", "SUSPENDED", "REVOKED", "EXPIRED",
            "RECERTIFICATION_REQUIRED",
        }

    def test_values(self):
        assert CertificationStatus.PENDING.value == "pending"
        assert CertificationStatus.ACTIVE.value == "active"
        assert CertificationStatus.SUSPENDED.value == "suspended"
        assert CertificationStatus.REVOKED.value == "revoked"
        assert CertificationStatus.EXPIRED.value == "expired"
        assert CertificationStatus.RECERTIFICATION_REQUIRED.value == "recertification_required"

    def test_fail_closed_default(self):
        assert CertificationStatus.PENDING.value == "pending"


class TestAssuranceLevel:
    def test_member_count(self):
        assert len(AssuranceLevel) == 5

    def test_names(self):
        assert {m.name for m in AssuranceLevel} == {
            "NONE", "LOW", "MODERATE", "HIGH", "FULL",
        }

    def test_values(self):
        assert AssuranceLevel.NONE.value == "none"
        assert AssuranceLevel.LOW.value == "low"
        assert AssuranceLevel.MODERATE.value == "moderate"
        assert AssuranceLevel.HIGH.value == "high"
        assert AssuranceLevel.FULL.value == "full"

    def test_fail_closed_default(self):
        assert AssuranceLevel.NONE.value == "none"


class TestAssuranceScope:
    def test_member_count(self):
        assert len(AssuranceScope) == 6

    def test_names(self):
        assert {m.name for m in AssuranceScope} == {
            "CONTROL", "PROGRAM", "WORKSPACE", "TENANT", "CONNECTOR", "CAMPAIGN",
        }

    def test_values(self):
        assert AssuranceScope.CONTROL.value == "control"
        assert AssuranceScope.PROGRAM.value == "program"
        assert AssuranceScope.WORKSPACE.value == "workspace"
        assert AssuranceScope.TENANT.value == "tenant"
        assert AssuranceScope.CONNECTOR.value == "connector"
        assert AssuranceScope.CAMPAIGN.value == "campaign"


class TestEvidenceSufficiency:
    def test_member_count(self):
        assert len(EvidenceSufficiency) == 4

    def test_names(self):
        assert {m.name for m in EvidenceSufficiency} == {
            "INSUFFICIENT", "PARTIAL", "SUFFICIENT", "COMPREHENSIVE",
        }

    def test_values(self):
        assert EvidenceSufficiency.INSUFFICIENT.value == "insufficient"
        assert EvidenceSufficiency.PARTIAL.value == "partial"
        assert EvidenceSufficiency.SUFFICIENT.value == "sufficient"
        assert EvidenceSufficiency.COMPREHENSIVE.value == "comprehensive"

    def test_fail_closed_default(self):
        assert EvidenceSufficiency.INSUFFICIENT.value == "insufficient"


class TestRecertificationStatus:
    def test_member_count(self):
        assert len(RecertificationStatus) == 5

    def test_names(self):
        assert {m.name for m in RecertificationStatus} == {
            "SCHEDULED", "IN_PROGRESS", "COMPLETED", "OVERDUE", "WAIVED",
        }

    def test_values(self):
        assert RecertificationStatus.SCHEDULED.value == "scheduled"
        assert RecertificationStatus.IN_PROGRESS.value == "in_progress"
        assert RecertificationStatus.COMPLETED.value == "completed"
        assert RecertificationStatus.OVERDUE.value == "overdue"
        assert RecertificationStatus.WAIVED.value == "waived"


# ===================================================================
# AttestationRecord
# ===================================================================


class TestAttestationRecord:
    def test_valid_construction(self):
        rec = _attestation()
        assert rec.attestation_id == "att-001"
        assert rec.tenant_id == "t-001"
        assert rec.scope is AssuranceScope.CONTROL
        assert rec.level is AssuranceLevel.HIGH
        assert rec.status is AttestationStatus.GRANTED
        assert rec.attested_by == "auditor-1"

    def test_empty_attestation_id_rejected(self):
        with pytest.raises(ValueError):
            _attestation(attestation_id="")

    def test_whitespace_attestation_id_rejected(self):
        with pytest.raises(ValueError):
            _attestation(attestation_id="   ")

    def test_empty_tenant_id_rejected(self):
        with pytest.raises(ValueError):
            _attestation(tenant_id="")

    def test_empty_scope_ref_id_rejected(self):
        with pytest.raises(ValueError):
            _attestation(scope_ref_id="")

    def test_empty_attested_by_rejected(self):
        with pytest.raises(ValueError):
            _attestation(attested_by="")

    def test_invalid_scope_rejected(self):
        with pytest.raises(ValueError):
            _attestation(scope="control")

    def test_invalid_level_rejected(self):
        with pytest.raises(ValueError):
            _attestation(level="high")

    def test_invalid_status_rejected(self):
        with pytest.raises(ValueError):
            _attestation(status="granted")

    def test_garbage_datetime_rejected(self):
        with pytest.raises(ValueError):
            _attestation(attested_at="not-a-date")

    def test_numeric_datetime_rejected(self):
        with pytest.raises(ValueError):
            _attestation(attested_at=12345)

    def test_metadata_frozen(self):
        rec = _attestation(metadata={"key": "val"})
        assert isinstance(rec.metadata, MappingProxyType)
        assert rec.metadata["key"] == "val"

    def test_nested_metadata_frozen(self):
        rec = _attestation(metadata={"inner": {"a": 1}})
        assert isinstance(rec.metadata["inner"], MappingProxyType)

    def test_immutability(self):
        rec = _attestation()
        with pytest.raises(dataclasses.FrozenInstanceError):
            rec.attestation_id = "other"

    def test_to_dict(self):
        rec = _attestation()
        d = rec.to_dict()
        assert d["attestation_id"] == "att-001"
        assert d["scope"] is AssuranceScope.CONTROL
        assert d["level"] is AssuranceLevel.HIGH
        assert d["status"] is AttestationStatus.GRANTED
        assert isinstance(d["metadata"], dict)

    def test_to_dict_preserves_enum_objects(self):
        rec = _attestation()
        d = rec.to_dict()
        assert isinstance(d["scope"], AssuranceScope)
        assert isinstance(d["level"], AssuranceLevel)
        assert isinstance(d["status"], AttestationStatus)


# ===================================================================
# CertificationRecord
# ===================================================================


class TestCertificationRecord:
    def test_valid_construction(self):
        rec = _certification()
        assert rec.certification_id == "cert-001"
        assert rec.scope is AssuranceScope.PROGRAM
        assert rec.status is CertificationStatus.ACTIVE
        assert rec.level is AssuranceLevel.MODERATE

    def test_empty_certification_id_rejected(self):
        with pytest.raises(ValueError):
            _certification(certification_id="")

    def test_whitespace_certification_id_rejected(self):
        with pytest.raises(ValueError):
            _certification(certification_id="  \t ")

    def test_empty_tenant_id_rejected(self):
        with pytest.raises(ValueError):
            _certification(tenant_id="")

    def test_empty_scope_ref_id_rejected(self):
        with pytest.raises(ValueError):
            _certification(scope_ref_id="")

    def test_empty_certified_by_rejected(self):
        with pytest.raises(ValueError):
            _certification(certified_by="")

    def test_invalid_scope_rejected(self):
        with pytest.raises(ValueError):
            _certification(scope="program")

    def test_invalid_status_rejected(self):
        with pytest.raises(ValueError):
            _certification(status="active")

    def test_invalid_level_rejected(self):
        with pytest.raises(ValueError):
            _certification(level="moderate")

    def test_garbage_datetime_rejected(self):
        with pytest.raises(ValueError):
            _certification(certified_at="xyz")

    def test_numeric_datetime_rejected(self):
        with pytest.raises(ValueError):
            _certification(certified_at=99999)

    def test_metadata_frozen(self):
        rec = _certification(metadata={"k": [1, 2]})
        assert isinstance(rec.metadata, MappingProxyType)
        assert rec.metadata["k"] == (1, 2)

    def test_immutability(self):
        rec = _certification()
        with pytest.raises(dataclasses.FrozenInstanceError):
            rec.certification_id = "other"

    def test_to_dict(self):
        rec = _certification()
        d = rec.to_dict()
        assert d["certification_id"] == "cert-001"
        assert d["scope"] is AssuranceScope.PROGRAM
        assert d["status"] is CertificationStatus.ACTIVE
        assert isinstance(d["metadata"], dict)

    def test_to_dict_preserves_enum_objects(self):
        d = _certification().to_dict()
        assert isinstance(d["scope"], AssuranceScope)
        assert isinstance(d["status"], CertificationStatus)
        assert isinstance(d["level"], AssuranceLevel)


# ===================================================================
# AssuranceAssessment
# ===================================================================


class TestAssuranceAssessment:
    def test_valid_construction(self):
        rec = _assessment()
        assert rec.assessment_id == "assess-001"
        assert rec.confidence == 0.85
        assert rec.sufficiency is EvidenceSufficiency.SUFFICIENT

    def test_empty_assessment_id_rejected(self):
        with pytest.raises(ValueError):
            _assessment(assessment_id="")

    def test_whitespace_assessment_id_rejected(self):
        with pytest.raises(ValueError):
            _assessment(assessment_id="   ")

    def test_empty_tenant_id_rejected(self):
        with pytest.raises(ValueError):
            _assessment(tenant_id="")

    def test_empty_scope_ref_id_rejected(self):
        with pytest.raises(ValueError):
            _assessment(scope_ref_id="")

    def test_empty_assessed_by_rejected(self):
        with pytest.raises(ValueError):
            _assessment(assessed_by="")

    def test_invalid_scope_rejected(self):
        with pytest.raises(ValueError):
            _assessment(scope="workspace")

    def test_invalid_level_rejected(self):
        with pytest.raises(ValueError):
            _assessment(level="low")

    def test_invalid_sufficiency_rejected(self):
        with pytest.raises(ValueError):
            _assessment(sufficiency="sufficient")

    def test_confidence_zero(self):
        rec = _assessment(confidence=0.0)
        assert rec.confidence == 0.0

    def test_confidence_one(self):
        rec = _assessment(confidence=1.0)
        assert rec.confidence == 1.0

    def test_confidence_negative_rejected(self):
        with pytest.raises(ValueError):
            _assessment(confidence=-0.01)

    def test_confidence_above_one_rejected(self):
        with pytest.raises(ValueError):
            _assessment(confidence=1.01)

    def test_confidence_nan_rejected(self):
        with pytest.raises(ValueError):
            _assessment(confidence=float("nan"))

    def test_confidence_inf_rejected(self):
        with pytest.raises(ValueError):
            _assessment(confidence=float("inf"))

    def test_confidence_bool_rejected(self):
        with pytest.raises(ValueError):
            _assessment(confidence=True)

    def test_confidence_string_rejected(self):
        with pytest.raises(ValueError):
            _assessment(confidence="0.5")

    def test_confidence_int_zero(self):
        rec = _assessment(confidence=0)
        assert rec.confidence == 0.0

    def test_confidence_int_one(self):
        rec = _assessment(confidence=1)
        assert rec.confidence == 1.0

    def test_garbage_datetime_rejected(self):
        with pytest.raises(ValueError):
            _assessment(assessed_at="nope")

    def test_numeric_datetime_rejected(self):
        with pytest.raises(ValueError):
            _assessment(assessed_at=42)

    def test_metadata_frozen(self):
        rec = _assessment(metadata={"x": {"y": "z"}})
        assert isinstance(rec.metadata, MappingProxyType)
        assert isinstance(rec.metadata["x"], MappingProxyType)

    def test_immutability(self):
        rec = _assessment()
        with pytest.raises(dataclasses.FrozenInstanceError):
            rec.confidence = 0.5

    def test_to_dict(self):
        d = _assessment().to_dict()
        assert d["assessment_id"] == "assess-001"
        assert d["confidence"] == 0.85
        assert d["sufficiency"] is EvidenceSufficiency.SUFFICIENT

    def test_to_dict_preserves_enum_objects(self):
        d = _assessment().to_dict()
        assert isinstance(d["scope"], AssuranceScope)
        assert isinstance(d["level"], AssuranceLevel)
        assert isinstance(d["sufficiency"], EvidenceSufficiency)


# ===================================================================
# AssuranceEvidenceBinding
# ===================================================================


class TestAssuranceEvidenceBinding:
    def test_valid_construction(self):
        rec = _evidence_binding()
        assert rec.binding_id == "bind-001"
        assert rec.target_id == "att-001"
        assert rec.target_type == "attestation"
        assert rec.source_type == "document"
        assert rec.source_id == "doc-001"

    def test_empty_binding_id_rejected(self):
        with pytest.raises(ValueError):
            _evidence_binding(binding_id="")

    def test_whitespace_binding_id_rejected(self):
        with pytest.raises(ValueError):
            _evidence_binding(binding_id="  ")

    def test_empty_target_id_rejected(self):
        with pytest.raises(ValueError):
            _evidence_binding(target_id="")

    def test_empty_target_type_rejected(self):
        with pytest.raises(ValueError):
            _evidence_binding(target_type="")

    def test_empty_source_type_rejected(self):
        with pytest.raises(ValueError):
            _evidence_binding(source_type="")

    def test_empty_source_id_rejected(self):
        with pytest.raises(ValueError):
            _evidence_binding(source_id="")

    def test_garbage_datetime_rejected(self):
        with pytest.raises(ValueError):
            _evidence_binding(bound_at="bad")

    def test_numeric_datetime_rejected(self):
        with pytest.raises(ValueError):
            _evidence_binding(bound_at=0)

    def test_metadata_frozen(self):
        rec = _evidence_binding(metadata={"a": "b"})
        assert isinstance(rec.metadata, MappingProxyType)

    def test_immutability(self):
        rec = _evidence_binding()
        with pytest.raises(dataclasses.FrozenInstanceError):
            rec.binding_id = "other"

    def test_to_dict(self):
        d = _evidence_binding().to_dict()
        assert d["binding_id"] == "bind-001"
        assert d["target_type"] == "attestation"
        assert isinstance(d["metadata"], dict)


# ===================================================================
# RecertificationWindow
# ===================================================================


class TestRecertificationWindow:
    def test_valid_construction(self):
        rec = _recertification_window()
        assert rec.window_id == "win-001"
        assert rec.certification_id == "cert-001"
        assert rec.status is RecertificationStatus.SCHEDULED

    def test_empty_window_id_rejected(self):
        with pytest.raises(ValueError):
            _recertification_window(window_id="")

    def test_whitespace_window_id_rejected(self):
        with pytest.raises(ValueError):
            _recertification_window(window_id="\n")

    def test_empty_certification_id_rejected(self):
        with pytest.raises(ValueError):
            _recertification_window(certification_id="")

    def test_invalid_status_rejected(self):
        with pytest.raises(ValueError):
            _recertification_window(status="scheduled")

    def test_garbage_starts_at_rejected(self):
        with pytest.raises(ValueError):
            _recertification_window(starts_at="never")

    def test_garbage_ends_at_rejected(self):
        with pytest.raises(ValueError):
            _recertification_window(ends_at="never")

    def test_numeric_datetime_rejected(self):
        with pytest.raises(ValueError):
            _recertification_window(starts_at=123)

    def test_metadata_frozen(self):
        rec = _recertification_window(metadata={"k": "v"})
        assert isinstance(rec.metadata, MappingProxyType)

    def test_immutability(self):
        rec = _recertification_window()
        with pytest.raises(dataclasses.FrozenInstanceError):
            rec.window_id = "other"

    def test_to_dict(self):
        d = _recertification_window().to_dict()
        assert d["window_id"] == "win-001"
        assert d["status"] is RecertificationStatus.SCHEDULED

    def test_to_dict_preserves_enum_objects(self):
        d = _recertification_window().to_dict()
        assert isinstance(d["status"], RecertificationStatus)

    def test_all_status_values_accepted(self):
        for s in RecertificationStatus:
            rec = _recertification_window(status=s)
            assert rec.status is s


# ===================================================================
# AssuranceFinding
# ===================================================================


class TestAssuranceFinding:
    def test_valid_construction(self):
        rec = _finding()
        assert rec.finding_id == "find-001"
        assert rec.target_type == "attestation"
        assert rec.impact_level is AssuranceLevel.MODERATE

    def test_empty_finding_id_rejected(self):
        with pytest.raises(ValueError):
            _finding(finding_id="")

    def test_whitespace_finding_id_rejected(self):
        with pytest.raises(ValueError):
            _finding(finding_id="\t")

    def test_empty_target_id_rejected(self):
        with pytest.raises(ValueError):
            _finding(target_id="")

    def test_empty_target_type_rejected(self):
        with pytest.raises(ValueError):
            _finding(target_type="")

    def test_invalid_impact_level_rejected(self):
        with pytest.raises(ValueError):
            _finding(impact_level="moderate")

    def test_garbage_datetime_rejected(self):
        with pytest.raises(ValueError):
            _finding(detected_at="garbage")

    def test_numeric_datetime_rejected(self):
        with pytest.raises(ValueError):
            _finding(detected_at=0)

    def test_metadata_frozen(self):
        rec = _finding(metadata={"a": [1]})
        assert isinstance(rec.metadata, MappingProxyType)
        assert rec.metadata["a"] == (1,)

    def test_immutability(self):
        rec = _finding()
        with pytest.raises(dataclasses.FrozenInstanceError):
            rec.finding_id = "other"

    def test_to_dict(self):
        d = _finding().to_dict()
        assert d["finding_id"] == "find-001"
        assert d["impact_level"] is AssuranceLevel.MODERATE

    def test_to_dict_preserves_enum_objects(self):
        d = _finding().to_dict()
        assert isinstance(d["impact_level"], AssuranceLevel)


# ===================================================================
# AssuranceDecision
# ===================================================================


class TestAssuranceDecision:
    def test_valid_construction(self):
        rec = _decision()
        assert rec.decision_id == "dec-001"
        assert rec.level is AssuranceLevel.HIGH
        assert rec.decided_by == "decider-1"

    def test_empty_decision_id_rejected(self):
        with pytest.raises(ValueError):
            _decision(decision_id="")

    def test_whitespace_decision_id_rejected(self):
        with pytest.raises(ValueError):
            _decision(decision_id="  ")

    def test_empty_target_id_rejected(self):
        with pytest.raises(ValueError):
            _decision(target_id="")

    def test_empty_target_type_rejected(self):
        with pytest.raises(ValueError):
            _decision(target_type="")

    def test_empty_decided_by_rejected(self):
        with pytest.raises(ValueError):
            _decision(decided_by="")

    def test_invalid_level_rejected(self):
        with pytest.raises(ValueError):
            _decision(level="high")

    def test_garbage_datetime_rejected(self):
        with pytest.raises(ValueError):
            _decision(decided_at="abc")

    def test_numeric_datetime_rejected(self):
        with pytest.raises(ValueError):
            _decision(decided_at=777)

    def test_metadata_frozen(self):
        rec = _decision(metadata={"z": {1: 2}})
        assert isinstance(rec.metadata, MappingProxyType)

    def test_immutability(self):
        rec = _decision()
        with pytest.raises(dataclasses.FrozenInstanceError):
            rec.level = AssuranceLevel.LOW

    def test_to_dict(self):
        d = _decision().to_dict()
        assert d["decision_id"] == "dec-001"
        assert d["level"] is AssuranceLevel.HIGH

    def test_to_dict_preserves_enum_objects(self):
        d = _decision().to_dict()
        assert isinstance(d["level"], AssuranceLevel)


# ===================================================================
# AssuranceSnapshot
# ===================================================================


class TestAssuranceSnapshot:
    def test_valid_construction(self):
        rec = _snapshot()
        assert rec.snapshot_id == "snap-001"
        assert rec.total_attestations == 10
        assert rec.granted_attestations == 8
        assert rec.total_certifications == 5
        assert rec.active_certifications == 3
        assert rec.total_assessments == 7
        assert rec.total_evidence_bindings == 20
        assert rec.total_violations == 1

    def test_empty_snapshot_id_rejected(self):
        with pytest.raises(ValueError):
            _snapshot(snapshot_id="")

    def test_whitespace_snapshot_id_rejected(self):
        with pytest.raises(ValueError):
            _snapshot(snapshot_id="  \n\t ")

    def test_negative_total_attestations_rejected(self):
        with pytest.raises(ValueError):
            _snapshot(total_attestations=-1)

    def test_negative_granted_attestations_rejected(self):
        with pytest.raises(ValueError):
            _snapshot(granted_attestations=-1)

    def test_negative_total_certifications_rejected(self):
        with pytest.raises(ValueError):
            _snapshot(total_certifications=-1)

    def test_negative_active_certifications_rejected(self):
        with pytest.raises(ValueError):
            _snapshot(active_certifications=-1)

    def test_negative_total_assessments_rejected(self):
        with pytest.raises(ValueError):
            _snapshot(total_assessments=-1)

    def test_negative_total_evidence_bindings_rejected(self):
        with pytest.raises(ValueError):
            _snapshot(total_evidence_bindings=-1)

    def test_negative_total_violations_rejected(self):
        with pytest.raises(ValueError):
            _snapshot(total_violations=-1)

    def test_zero_counts_accepted(self):
        rec = _snapshot(
            total_attestations=0,
            granted_attestations=0,
            total_certifications=0,
            active_certifications=0,
            total_assessments=0,
            total_evidence_bindings=0,
            total_violations=0,
        )
        assert rec.total_attestations == 0

    def test_bool_count_rejected(self):
        with pytest.raises(ValueError):
            _snapshot(total_attestations=True)

    def test_float_count_rejected(self):
        with pytest.raises(ValueError):
            _snapshot(total_attestations=1.5)

    def test_garbage_datetime_rejected(self):
        with pytest.raises(ValueError):
            _snapshot(captured_at="oops")

    def test_numeric_datetime_rejected(self):
        with pytest.raises(ValueError):
            _snapshot(captured_at=42)

    def test_metadata_frozen(self):
        rec = _snapshot(metadata={"m": "n"})
        assert isinstance(rec.metadata, MappingProxyType)

    def test_immutability(self):
        rec = _snapshot()
        with pytest.raises(dataclasses.FrozenInstanceError):
            rec.total_attestations = 99

    def test_to_dict(self):
        d = _snapshot().to_dict()
        assert d["snapshot_id"] == "snap-001"
        assert d["total_attestations"] == 10
        assert isinstance(d["metadata"], dict)


# ===================================================================
# AssuranceViolation
# ===================================================================


class TestAssuranceViolation:
    def test_valid_construction(self):
        rec = _violation()
        assert rec.violation_id == "viol-001"
        assert rec.operation == "revoke"
        assert rec.reason == "policy breach"

    def test_empty_violation_id_rejected(self):
        with pytest.raises(ValueError):
            _violation(violation_id="")

    def test_whitespace_violation_id_rejected(self):
        with pytest.raises(ValueError):
            _violation(violation_id="   ")

    def test_empty_target_id_rejected(self):
        with pytest.raises(ValueError):
            _violation(target_id="")

    def test_empty_target_type_rejected(self):
        with pytest.raises(ValueError):
            _violation(target_type="")

    def test_empty_tenant_id_rejected(self):
        with pytest.raises(ValueError):
            _violation(tenant_id="")

    def test_empty_operation_rejected(self):
        with pytest.raises(ValueError):
            _violation(operation="")

    def test_garbage_datetime_rejected(self):
        with pytest.raises(ValueError):
            _violation(detected_at="???")

    def test_numeric_datetime_rejected(self):
        with pytest.raises(ValueError):
            _violation(detected_at=1)

    def test_metadata_frozen(self):
        rec = _violation(metadata={"severity": "high"})
        assert isinstance(rec.metadata, MappingProxyType)

    def test_immutability(self):
        rec = _violation()
        with pytest.raises(dataclasses.FrozenInstanceError):
            rec.violation_id = "other"

    def test_to_dict(self):
        d = _violation().to_dict()
        assert d["violation_id"] == "viol-001"
        assert d["operation"] == "revoke"
        assert isinstance(d["metadata"], dict)


# ===================================================================
# AssuranceClosureReport
# ===================================================================


class TestAssuranceClosureReport:
    def test_valid_construction(self):
        rec = _closure_report()
        assert rec.report_id == "rep-001"
        assert rec.final_level is AssuranceLevel.FULL
        assert rec.total_evidence_bindings == 15
        assert rec.total_findings == 2

    def test_empty_report_id_rejected(self):
        with pytest.raises(ValueError):
            _closure_report(report_id="")

    def test_whitespace_report_id_rejected(self):
        with pytest.raises(ValueError):
            _closure_report(report_id="\t  ")

    def test_empty_target_id_rejected(self):
        with pytest.raises(ValueError):
            _closure_report(target_id="")

    def test_empty_target_type_rejected(self):
        with pytest.raises(ValueError):
            _closure_report(target_type="")

    def test_empty_tenant_id_rejected(self):
        with pytest.raises(ValueError):
            _closure_report(tenant_id="")

    def test_invalid_final_level_rejected(self):
        with pytest.raises(ValueError):
            _closure_report(final_level="full")

    def test_negative_total_evidence_bindings_rejected(self):
        with pytest.raises(ValueError):
            _closure_report(total_evidence_bindings=-1)

    def test_negative_total_assessments_rejected(self):
        with pytest.raises(ValueError):
            _closure_report(total_assessments=-1)

    def test_negative_total_findings_rejected(self):
        with pytest.raises(ValueError):
            _closure_report(total_findings=-1)

    def test_negative_total_violations_rejected(self):
        with pytest.raises(ValueError):
            _closure_report(total_violations=-1)

    def test_zero_counts_accepted(self):
        rec = _closure_report(
            total_evidence_bindings=0,
            total_assessments=0,
            total_findings=0,
            total_violations=0,
        )
        assert rec.total_evidence_bindings == 0

    def test_bool_count_rejected(self):
        with pytest.raises(ValueError):
            _closure_report(total_findings=False)

    def test_float_count_rejected(self):
        with pytest.raises(ValueError):
            _closure_report(total_assessments=2.0)

    def test_garbage_datetime_rejected(self):
        with pytest.raises(ValueError):
            _closure_report(closed_at="nah")

    def test_numeric_datetime_rejected(self):
        with pytest.raises(ValueError):
            _closure_report(closed_at=10)

    def test_metadata_frozen(self):
        rec = _closure_report(metadata={"final": True})
        assert isinstance(rec.metadata, MappingProxyType)

    def test_immutability(self):
        rec = _closure_report()
        with pytest.raises(dataclasses.FrozenInstanceError):
            rec.report_id = "other"

    def test_to_dict(self):
        d = _closure_report().to_dict()
        assert d["report_id"] == "rep-001"
        assert d["final_level"] is AssuranceLevel.FULL
        assert isinstance(d["metadata"], dict)

    def test_to_dict_preserves_enum_objects(self):
        d = _closure_report().to_dict()
        assert isinstance(d["final_level"], AssuranceLevel)


# ===================================================================
# Cross-cutting immutability
# ===================================================================


class TestCrossCuttingImmutability:
    """All dataclass instances must be immutable (frozen=True)."""

    def test_attestation_frozen(self):
        with pytest.raises(dataclasses.FrozenInstanceError):
            _attestation().status = AttestationStatus.REVOKED

    def test_certification_frozen(self):
        with pytest.raises(dataclasses.FrozenInstanceError):
            _certification().status = CertificationStatus.REVOKED

    def test_assessment_frozen(self):
        with pytest.raises(dataclasses.FrozenInstanceError):
            _assessment().confidence = 0.0

    def test_evidence_binding_frozen(self):
        with pytest.raises(dataclasses.FrozenInstanceError):
            _evidence_binding().source_id = "x"

    def test_recertification_window_frozen(self):
        with pytest.raises(dataclasses.FrozenInstanceError):
            _recertification_window().status = RecertificationStatus.COMPLETED

    def test_finding_frozen(self):
        with pytest.raises(dataclasses.FrozenInstanceError):
            _finding().impact_level = AssuranceLevel.HIGH

    def test_decision_frozen(self):
        with pytest.raises(dataclasses.FrozenInstanceError):
            _decision().decided_by = "other"

    def test_snapshot_frozen(self):
        with pytest.raises(dataclasses.FrozenInstanceError):
            _snapshot().total_violations = 0

    def test_violation_frozen(self):
        with pytest.raises(dataclasses.FrozenInstanceError):
            _violation().reason = "other"

    def test_closure_report_frozen(self):
        with pytest.raises(dataclasses.FrozenInstanceError):
            _closure_report().total_findings = 0


# ===================================================================
# Cross-cutting: metadata freeze produces MappingProxyType & tuples
# ===================================================================


class TestMetadataFreeze:
    """freeze_value returns MappingProxyType for dicts, tuples for lists."""

    def test_list_becomes_tuple(self):
        rec = _attestation(metadata={"items": [1, 2, 3]})
        assert rec.metadata["items"] == (1, 2, 3)
        assert isinstance(rec.metadata["items"], tuple)

    def test_nested_dict_becomes_mapping_proxy(self):
        rec = _certification(metadata={"nested": {"a": 1}})
        assert isinstance(rec.metadata["nested"], MappingProxyType)

    def test_deeply_nested_freeze(self):
        rec = _assessment(metadata={"a": {"b": [{"c": 1}]}})
        inner = rec.metadata["a"]["b"]
        assert isinstance(inner, tuple)
        assert isinstance(inner[0], MappingProxyType)

    def test_empty_metadata_frozen(self):
        rec = _finding(metadata={})
        assert isinstance(rec.metadata, MappingProxyType)
        assert len(rec.metadata) == 0


# ===================================================================
# Cross-cutting: fail-closed defaults on dataclass fields
# ===================================================================


class TestFailClosedDefaults:
    """Default enum values should be the most restrictive / safest option."""

    def test_attestation_default_status(self):
        assert AttestationRecord.__dataclass_fields__["status"].default is AttestationStatus.PENDING

    def test_attestation_default_level(self):
        assert AttestationRecord.__dataclass_fields__["level"].default is AssuranceLevel.NONE

    def test_certification_default_status(self):
        assert CertificationRecord.__dataclass_fields__["status"].default is CertificationStatus.PENDING

    def test_certification_default_level(self):
        assert CertificationRecord.__dataclass_fields__["level"].default is AssuranceLevel.NONE

    def test_assessment_default_level(self):
        assert AssuranceAssessment.__dataclass_fields__["level"].default is AssuranceLevel.NONE

    def test_assessment_default_sufficiency(self):
        assert AssuranceAssessment.__dataclass_fields__["sufficiency"].default is EvidenceSufficiency.INSUFFICIENT

    def test_finding_default_impact_level(self):
        assert AssuranceFinding.__dataclass_fields__["impact_level"].default is AssuranceLevel.NONE

    def test_decision_default_level(self):
        assert AssuranceDecision.__dataclass_fields__["level"].default is AssuranceLevel.NONE

    def test_closure_report_default_final_level(self):
        assert AssuranceClosureReport.__dataclass_fields__["final_level"].default is AssuranceLevel.NONE

    def test_recertification_window_default_status(self):
        assert RecertificationWindow.__dataclass_fields__["status"].default is RecertificationStatus.SCHEDULED


# ===================================================================
# Cross-cutting: slots=True on all dataclasses
# ===================================================================


class TestSlotsEnabled:
    def test_attestation_has_slots(self):
        assert hasattr(AttestationRecord, "__slots__")

    def test_certification_has_slots(self):
        assert hasattr(CertificationRecord, "__slots__")

    def test_assessment_has_slots(self):
        assert hasattr(AssuranceAssessment, "__slots__")

    def test_evidence_binding_has_slots(self):
        assert hasattr(AssuranceEvidenceBinding, "__slots__")

    def test_recertification_window_has_slots(self):
        assert hasattr(RecertificationWindow, "__slots__")

    def test_finding_has_slots(self):
        assert hasattr(AssuranceFinding, "__slots__")

    def test_decision_has_slots(self):
        assert hasattr(AssuranceDecision, "__slots__")

    def test_snapshot_has_slots(self):
        assert hasattr(AssuranceSnapshot, "__slots__")

    def test_violation_has_slots(self):
        assert hasattr(AssuranceViolation, "__slots__")

    def test_closure_report_has_slots(self):
        assert hasattr(AssuranceClosureReport, "__slots__")
