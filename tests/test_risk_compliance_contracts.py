"""Purpose: comprehensive contract tests for the risk_compliance module.
Governance scope: validate enums, frozen dataclasses, field constraints,
    to_dict round-trips, and immutability for all risk/compliance contracts.
Dependencies: pytest and the mcoi_runtime risk_compliance contract layer.
Invariants:
  - All dataclasses are frozen and reject mutation.
  - Enum fields reject non-enum values.
  - Required text fields reject empty strings.
  - Datetime fields reject non-ISO-8601 strings.
  - Numeric fields respect their range constraints.
  - freeze_value produces tuples and MappingProxyType.
"""

from types import MappingProxyType

import pytest

from mcoi_runtime.contracts.risk_compliance import (
    AssuranceReport,
    ComplianceDisposition,
    ComplianceRequirement,
    ComplianceSnapshot,
    ControlBinding,
    ControlFailure,
    ControlRecord,
    ControlStatus,
    ControlTestRecord,
    ControlTestStatus,
    EvidenceSourceKind,
    ExceptionRequest,
    ExceptionStatus,
    RiskAssessment,
    RiskCategory,
    RiskRecord,
    RiskSeverity,
)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

DT = "2026-03-18T12:00:00+00:00"
DT2 = "2026-03-18T13:00:00+00:00"


# ===================================================================
# Enum tests
# ===================================================================


class TestRiskSeverityEnum:
    def test_members_count(self) -> None:
        assert len(RiskSeverity) == 5

    def test_member_values(self) -> None:
        assert RiskSeverity.CRITICAL.value == "critical"
        assert RiskSeverity.HIGH.value == "high"
        assert RiskSeverity.MEDIUM.value == "medium"
        assert RiskSeverity.LOW.value == "low"
        assert RiskSeverity.INFORMATIONAL.value == "informational"


class TestRiskCategoryEnum:
    def test_members_count(self) -> None:
        assert len(RiskCategory) == 7

    def test_member_values(self) -> None:
        assert RiskCategory.OPERATIONAL.value == "operational"
        assert RiskCategory.FINANCIAL.value == "financial"
        assert RiskCategory.COMPLIANCE.value == "compliance"
        assert RiskCategory.SECURITY.value == "security"
        assert RiskCategory.REPUTATIONAL.value == "reputational"
        assert RiskCategory.STRATEGIC.value == "strategic"
        assert RiskCategory.TECHNICAL.value == "technical"


class TestControlStatusEnum:
    def test_members_count(self) -> None:
        assert len(ControlStatus) == 6

    def test_member_values(self) -> None:
        assert ControlStatus.ACTIVE.value == "active"
        assert ControlStatus.INACTIVE.value == "inactive"
        assert ControlStatus.TESTING.value == "testing"
        assert ControlStatus.FAILED.value == "failed"
        assert ControlStatus.REMEDIATION.value == "remediation"
        assert ControlStatus.RETIRED.value == "retired"


class TestControlTestStatusEnum:
    def test_members_count(self) -> None:
        assert len(ControlTestStatus) == 5

    def test_member_values(self) -> None:
        assert ControlTestStatus.PASSED.value == "passed"
        assert ControlTestStatus.FAILED.value == "failed"
        assert ControlTestStatus.PARTIAL.value == "partial"
        assert ControlTestStatus.SKIPPED.value == "skipped"
        assert ControlTestStatus.ERROR.value == "error"


class TestExceptionStatusEnum:
    def test_members_count(self) -> None:
        assert len(ExceptionStatus) == 5

    def test_member_values(self) -> None:
        assert ExceptionStatus.REQUESTED.value == "requested"
        assert ExceptionStatus.APPROVED.value == "approved"
        assert ExceptionStatus.DENIED.value == "denied"
        assert ExceptionStatus.EXPIRED.value == "expired"
        assert ExceptionStatus.REVOKED.value == "revoked"


class TestComplianceDispositionEnum:
    def test_members_count(self) -> None:
        assert len(ComplianceDisposition) == 5

    def test_member_values(self) -> None:
        assert ComplianceDisposition.COMPLIANT.value == "compliant"
        assert ComplianceDisposition.NON_COMPLIANT.value == "non_compliant"
        assert ComplianceDisposition.PARTIALLY_COMPLIANT.value == "partially_compliant"
        assert ComplianceDisposition.EXCEPTION_GRANTED.value == "exception_granted"
        assert ComplianceDisposition.NOT_ASSESSED.value == "not_assessed"


class TestEvidenceSourceKindEnum:
    def test_members_count(self) -> None:
        assert len(EvidenceSourceKind) == 6

    def test_member_values(self) -> None:
        assert EvidenceSourceKind.ARTIFACT.value == "artifact"
        assert EvidenceSourceKind.EVENT.value == "event"
        assert EvidenceSourceKind.MEMORY.value == "memory"
        assert EvidenceSourceKind.TEST_RESULT.value == "test_result"
        assert EvidenceSourceKind.MANUAL_ATTESTATION.value == "manual_attestation"
        assert EvidenceSourceKind.AUDIT_LOG.value == "audit_log"


# ===================================================================
# RiskRecord tests
# ===================================================================


class TestRiskRecord:
    def test_valid_defaults(self) -> None:
        r = RiskRecord(risk_id="r-1", title="Risk A", created_at=DT)
        assert r.risk_id == "r-1"
        assert r.title == "Risk A"
        assert r.severity is RiskSeverity.MEDIUM
        assert r.category is RiskCategory.OPERATIONAL
        assert r.likelihood == 0.0
        assert r.impact == 0.0
        assert r.scope_ref_id == ""
        assert r.owner == ""
        assert r.mitigations == ()
        assert r.created_at == DT
        assert r.updated_at == ""
        assert isinstance(r.metadata, MappingProxyType)

    def test_valid_all_fields(self) -> None:
        r = RiskRecord(
            risk_id="r-2",
            title="Risk B",
            description="desc",
            severity=RiskSeverity.CRITICAL,
            category=RiskCategory.SECURITY,
            likelihood=0.8,
            impact=0.9,
            scope_ref_id="scope-1",
            owner="alice",
            mitigations=("m1", "m2"),
            created_at=DT,
            updated_at=DT2,
            metadata={"key": "val"},
        )
        assert r.severity is RiskSeverity.CRITICAL
        assert r.category is RiskCategory.SECURITY
        assert r.likelihood == 0.8
        assert r.impact == 0.9
        assert r.mitigations == ("m1", "m2")
        assert r.metadata["key"] == "val"

    def test_to_dict_preserves_enums(self) -> None:
        r = RiskRecord(risk_id="r-1", title="Risk A", created_at=DT)
        d = r.to_dict()
        assert d["risk_id"] == "r-1"
        assert d["severity"] is RiskSeverity.MEDIUM
        assert d["category"] is RiskCategory.OPERATIONAL

    def test_frozen_immutability(self) -> None:
        r = RiskRecord(risk_id="r-1", title="Risk A", created_at=DT)
        with pytest.raises(AttributeError):
            r.risk_id = "changed"  # type: ignore[misc]

    def test_invalid_risk_id_empty(self) -> None:
        with pytest.raises(ValueError):
            RiskRecord(risk_id="", title="Risk A", created_at=DT)

    def test_invalid_title_empty(self) -> None:
        with pytest.raises(ValueError):
            RiskRecord(risk_id="r-1", title="", created_at=DT)

    def test_invalid_created_at_bad_datetime(self) -> None:
        with pytest.raises(ValueError):
            RiskRecord(risk_id="r-1", title="Risk A", created_at="not-a-date")

    def test_invalid_created_at_empty(self) -> None:
        with pytest.raises(ValueError):
            RiskRecord(risk_id="r-1", title="Risk A", created_at="")

    def test_invalid_likelihood_too_high(self) -> None:
        with pytest.raises(ValueError):
            RiskRecord(risk_id="r-1", title="Risk A", created_at=DT, likelihood=1.5)

    def test_invalid_likelihood_negative(self) -> None:
        with pytest.raises(ValueError):
            RiskRecord(risk_id="r-1", title="Risk A", created_at=DT, likelihood=-0.1)

    def test_invalid_impact_too_high(self) -> None:
        with pytest.raises(ValueError):
            RiskRecord(risk_id="r-1", title="Risk A", created_at=DT, impact=2.0)

    def test_invalid_impact_negative(self) -> None:
        with pytest.raises(ValueError):
            RiskRecord(risk_id="r-1", title="Risk A", created_at=DT, impact=-0.5)

    def test_invalid_severity_type(self) -> None:
        with pytest.raises(ValueError):
            RiskRecord(risk_id="r-1", title="Risk A", created_at=DT, severity="high")  # type: ignore[arg-type]

    def test_invalid_category_type(self) -> None:
        with pytest.raises(ValueError):
            RiskRecord(risk_id="r-1", title="Risk A", created_at=DT, category="security")  # type: ignore[arg-type]

    def test_mitigations_frozen_as_tuple(self) -> None:
        r = RiskRecord(risk_id="r-1", title="Risk A", created_at=DT, mitigations=["a", "b"])  # type: ignore[arg-type]
        assert isinstance(r.mitigations, tuple)
        assert r.mitigations == ("a", "b")

    def test_metadata_frozen_as_mapping_proxy(self) -> None:
        r = RiskRecord(risk_id="r-1", title="Risk A", created_at=DT, metadata={"k": "v"})
        assert isinstance(r.metadata, MappingProxyType)

    def test_invalid_risk_id_whitespace_only(self) -> None:
        with pytest.raises(ValueError):
            RiskRecord(risk_id="   ", title="Risk A", created_at=DT)

    def test_invalid_title_whitespace_only(self) -> None:
        with pytest.raises(ValueError):
            RiskRecord(risk_id="r-1", title="  ", created_at=DT)

    def test_created_at_accepts_z_suffix(self) -> None:
        r = RiskRecord(risk_id="r-1", title="Risk A", created_at="2026-03-18T12:00:00Z")
        assert r.created_at == "2026-03-18T12:00:00Z"

    def test_likelihood_boundary_zero(self) -> None:
        r = RiskRecord(risk_id="r-1", title="Risk A", created_at=DT, likelihood=0.0)
        assert r.likelihood == 0.0

    def test_likelihood_boundary_one(self) -> None:
        r = RiskRecord(risk_id="r-1", title="Risk A", created_at=DT, likelihood=1.0)
        assert r.likelihood == 1.0

    def test_impact_boundary_one(self) -> None:
        r = RiskRecord(risk_id="r-1", title="Risk A", created_at=DT, impact=1.0)
        assert r.impact == 1.0

    def test_to_dict_contains_all_fields(self) -> None:
        r = RiskRecord(risk_id="r-1", title="Risk A", created_at=DT)
        d = r.to_dict()
        expected_keys = {
            "risk_id", "title", "description", "severity", "category",
            "likelihood", "impact", "scope_ref_id", "owner", "mitigations",
            "created_at", "updated_at", "metadata",
        }
        assert set(d.keys()) == expected_keys

    def test_metadata_nested_dict_frozen(self) -> None:
        r = RiskRecord(risk_id="r-1", title="Risk A", created_at=DT, metadata={"nested": {"a": 1}})
        assert isinstance(r.metadata["nested"], MappingProxyType)


# ===================================================================
# ControlRecord tests
# ===================================================================


class TestControlRecord:
    def test_valid_defaults(self) -> None:
        c = ControlRecord(control_id="c-1", title="Ctrl A", created_at=DT)
        assert c.control_id == "c-1"
        assert c.title == "Ctrl A"
        assert c.status is ControlStatus.ACTIVE
        assert c.requirement_id == ""
        assert c.test_frequency_seconds == 86400.0
        assert c.last_tested_at == ""
        assert c.owner == ""
        assert isinstance(c.metadata, MappingProxyType)

    def test_valid_all_fields(self) -> None:
        c = ControlRecord(
            control_id="c-2",
            title="Ctrl B",
            description="d",
            status=ControlStatus.TESTING,
            requirement_id="req-1",
            test_frequency_seconds=3600.0,
            last_tested_at=DT,
            owner="bob",
            created_at=DT,
            metadata={"x": 1},
        )
        assert c.status is ControlStatus.TESTING
        assert c.test_frequency_seconds == 3600.0

    def test_to_dict_preserves_enums(self) -> None:
        c = ControlRecord(control_id="c-1", title="Ctrl A", created_at=DT)
        d = c.to_dict()
        assert d["status"] is ControlStatus.ACTIVE

    def test_frozen_immutability(self) -> None:
        c = ControlRecord(control_id="c-1", title="Ctrl A", created_at=DT)
        with pytest.raises(AttributeError):
            c.control_id = "x"  # type: ignore[misc]

    def test_invalid_control_id_empty(self) -> None:
        with pytest.raises(ValueError):
            ControlRecord(control_id="", title="Ctrl A", created_at=DT)

    def test_invalid_title_empty(self) -> None:
        with pytest.raises(ValueError):
            ControlRecord(control_id="c-1", title="", created_at=DT)

    def test_invalid_created_at_bad_datetime(self) -> None:
        with pytest.raises(ValueError):
            ControlRecord(control_id="c-1", title="Ctrl A", created_at="not-a-date")

    def test_invalid_created_at_empty(self) -> None:
        with pytest.raises(ValueError):
            ControlRecord(control_id="c-1", title="Ctrl A", created_at="")

    def test_invalid_status_type(self) -> None:
        with pytest.raises(ValueError):
            ControlRecord(control_id="c-1", title="Ctrl A", created_at=DT, status="active")  # type: ignore[arg-type]

    def test_invalid_test_frequency_negative(self) -> None:
        with pytest.raises(ValueError):
            ControlRecord(control_id="c-1", title="Ctrl A", created_at=DT, test_frequency_seconds=-1.0)

    def test_metadata_frozen_as_mapping_proxy(self) -> None:
        c = ControlRecord(control_id="c-1", title="Ctrl A", created_at=DT, metadata={"a": "b"})
        assert isinstance(c.metadata, MappingProxyType)

    def test_invalid_control_id_whitespace_only(self) -> None:
        with pytest.raises(ValueError):
            ControlRecord(control_id="   ", title="Ctrl A", created_at=DT)

    def test_invalid_title_whitespace_only(self) -> None:
        with pytest.raises(ValueError):
            ControlRecord(control_id="c-1", title="  ", created_at=DT)

    def test_test_frequency_seconds_zero(self) -> None:
        c = ControlRecord(control_id="c-1", title="Ctrl A", created_at=DT, test_frequency_seconds=0.0)
        assert c.test_frequency_seconds == 0.0

    def test_to_dict_contains_all_fields(self) -> None:
        c = ControlRecord(control_id="c-1", title="Ctrl A", created_at=DT)
        d = c.to_dict()
        expected_keys = {
            "control_id", "title", "description", "status", "requirement_id",
            "test_frequency_seconds", "last_tested_at", "owner", "created_at", "metadata",
        }
        assert set(d.keys()) == expected_keys


# ===================================================================
# ControlBinding tests
# ===================================================================


class TestControlBinding:
    def test_valid_defaults(self) -> None:
        b = ControlBinding(binding_id="b-1", control_id="c-1", bound_at=DT)
        assert b.binding_id == "b-1"
        assert b.control_id == "c-1"
        assert b.scope_ref_id == ""
        assert b.scope_type == ""
        assert b.enforced is True
        assert b.bound_at == DT

    def test_valid_all_fields(self) -> None:
        b = ControlBinding(
            binding_id="b-2",
            control_id="c-2",
            scope_ref_id="scope-1",
            scope_type="agent",
            enforced=False,
            bound_at=DT,
        )
        assert b.enforced is False
        assert b.scope_type == "agent"

    def test_to_dict_round_trip(self) -> None:
        b = ControlBinding(binding_id="b-1", control_id="c-1", bound_at=DT)
        d = b.to_dict()
        assert d["binding_id"] == "b-1"
        assert d["control_id"] == "c-1"
        assert d["enforced"] is True

    def test_frozen_immutability(self) -> None:
        b = ControlBinding(binding_id="b-1", control_id="c-1", bound_at=DT)
        with pytest.raises(AttributeError):
            b.binding_id = "x"  # type: ignore[misc]

    def test_invalid_binding_id_empty(self) -> None:
        with pytest.raises(ValueError):
            ControlBinding(binding_id="", control_id="c-1", bound_at=DT)

    def test_invalid_control_id_empty(self) -> None:
        with pytest.raises(ValueError):
            ControlBinding(binding_id="b-1", control_id="", bound_at=DT)

    def test_invalid_bound_at_bad_datetime(self) -> None:
        with pytest.raises(ValueError):
            ControlBinding(binding_id="b-1", control_id="c-1", bound_at="not-a-date")

    def test_invalid_bound_at_empty(self) -> None:
        with pytest.raises(ValueError):
            ControlBinding(binding_id="b-1", control_id="c-1", bound_at="")

    def test_invalid_enforced_non_bool(self) -> None:
        with pytest.raises(ValueError):
            ControlBinding(binding_id="b-1", control_id="c-1", bound_at=DT, enforced=1)  # type: ignore[arg-type]

    def test_invalid_enforced_string(self) -> None:
        with pytest.raises(ValueError):
            ControlBinding(binding_id="b-1", control_id="c-1", bound_at=DT, enforced="yes")  # type: ignore[arg-type]

    def test_to_dict_contains_all_fields(self) -> None:
        b = ControlBinding(binding_id="b-1", control_id="c-1", bound_at=DT)
        d = b.to_dict()
        expected_keys = {"binding_id", "control_id", "scope_ref_id", "scope_type", "enforced", "bound_at"}
        assert set(d.keys()) == expected_keys


# ===================================================================
# ControlTestRecord tests
# ===================================================================


class TestControlTestRecord:
    def test_valid_defaults(self) -> None:
        t = ControlTestRecord(test_id="t-1", control_id="c-1", tested_at=DT)
        assert t.test_id == "t-1"
        assert t.control_id == "c-1"
        assert t.status is ControlTestStatus.PASSED
        assert t.evidence_refs == ()
        assert t.tester == ""
        assert t.notes == ""
        assert isinstance(t.metadata, MappingProxyType)

    def test_valid_all_fields(self) -> None:
        t = ControlTestRecord(
            test_id="t-2",
            control_id="c-2",
            status=ControlTestStatus.FAILED,
            evidence_refs=("e1", "e2"),
            tester="alice",
            notes="failed check",
            tested_at=DT,
            metadata={"run": 1},
        )
        assert t.status is ControlTestStatus.FAILED
        assert t.evidence_refs == ("e1", "e2")
        assert t.tester == "alice"

    def test_to_dict_preserves_enums(self) -> None:
        t = ControlTestRecord(test_id="t-1", control_id="c-1", tested_at=DT)
        d = t.to_dict()
        assert d["status"] is ControlTestStatus.PASSED

    def test_frozen_immutability(self) -> None:
        t = ControlTestRecord(test_id="t-1", control_id="c-1", tested_at=DT)
        with pytest.raises(AttributeError):
            t.test_id = "x"  # type: ignore[misc]

    def test_invalid_test_id_empty(self) -> None:
        with pytest.raises(ValueError):
            ControlTestRecord(test_id="", control_id="c-1", tested_at=DT)

    def test_invalid_control_id_empty(self) -> None:
        with pytest.raises(ValueError):
            ControlTestRecord(test_id="t-1", control_id="", tested_at=DT)

    def test_invalid_tested_at_bad_datetime(self) -> None:
        with pytest.raises(ValueError):
            ControlTestRecord(test_id="t-1", control_id="c-1", tested_at="not-a-date")

    def test_invalid_tested_at_empty(self) -> None:
        with pytest.raises(ValueError):
            ControlTestRecord(test_id="t-1", control_id="c-1", tested_at="")

    def test_invalid_status_type(self) -> None:
        with pytest.raises(ValueError):
            ControlTestRecord(test_id="t-1", control_id="c-1", tested_at=DT, status="passed")  # type: ignore[arg-type]

    def test_evidence_refs_frozen_as_tuple(self) -> None:
        t = ControlTestRecord(test_id="t-1", control_id="c-1", tested_at=DT, evidence_refs=["a", "b"])  # type: ignore[arg-type]
        assert isinstance(t.evidence_refs, tuple)
        assert t.evidence_refs == ("a", "b")

    def test_metadata_frozen_as_mapping_proxy(self) -> None:
        t = ControlTestRecord(test_id="t-1", control_id="c-1", tested_at=DT, metadata={"k": "v"})
        assert isinstance(t.metadata, MappingProxyType)

    def test_invalid_test_id_whitespace_only(self) -> None:
        with pytest.raises(ValueError):
            ControlTestRecord(test_id="   ", control_id="c-1", tested_at=DT)

    def test_to_dict_evidence_refs_as_list(self) -> None:
        t = ControlTestRecord(test_id="t-1", control_id="c-1", tested_at=DT, evidence_refs=("e1",))
        d = t.to_dict()
        # thaw_value converts tuples to lists
        assert d["evidence_refs"] == ["e1"]


# ===================================================================
# ComplianceRequirement tests
# ===================================================================


class TestComplianceRequirement:
    def test_valid_defaults(self) -> None:
        cr = ComplianceRequirement(requirement_id="req-1", title="Req A", created_at=DT)
        assert cr.requirement_id == "req-1"
        assert cr.title == "Req A"
        assert cr.category is RiskCategory.COMPLIANCE
        assert cr.mandatory is True
        assert cr.control_ids == ()
        assert cr.evidence_source_kinds == ()
        assert isinstance(cr.metadata, MappingProxyType)

    def test_valid_all_fields(self) -> None:
        cr = ComplianceRequirement(
            requirement_id="req-2",
            title="Req B",
            description="detail",
            category=RiskCategory.FINANCIAL,
            mandatory=False,
            control_ids=("c-1", "c-2"),
            evidence_source_kinds=("artifact", "event"),
            created_at=DT,
            metadata={"src": "audit"},
        )
        assert cr.category is RiskCategory.FINANCIAL
        assert cr.mandatory is False
        assert cr.control_ids == ("c-1", "c-2")
        assert cr.evidence_source_kinds == ("artifact", "event")

    def test_to_dict_preserves_enums(self) -> None:
        cr = ComplianceRequirement(requirement_id="req-1", title="Req A", created_at=DT)
        d = cr.to_dict()
        assert d["category"] is RiskCategory.COMPLIANCE

    def test_frozen_immutability(self) -> None:
        cr = ComplianceRequirement(requirement_id="req-1", title="Req A", created_at=DT)
        with pytest.raises(AttributeError):
            cr.requirement_id = "x"  # type: ignore[misc]

    def test_invalid_requirement_id_empty(self) -> None:
        with pytest.raises(ValueError):
            ComplianceRequirement(requirement_id="", title="Req A", created_at=DT)

    def test_invalid_title_empty(self) -> None:
        with pytest.raises(ValueError):
            ComplianceRequirement(requirement_id="req-1", title="", created_at=DT)

    def test_invalid_created_at_bad_datetime(self) -> None:
        with pytest.raises(ValueError):
            ComplianceRequirement(requirement_id="req-1", title="Req A", created_at="not-a-date")

    def test_invalid_created_at_empty(self) -> None:
        with pytest.raises(ValueError):
            ComplianceRequirement(requirement_id="req-1", title="Req A", created_at="")

    def test_invalid_category_type(self) -> None:
        with pytest.raises(ValueError):
            ComplianceRequirement(requirement_id="req-1", title="Req A", created_at=DT, category="compliance")  # type: ignore[arg-type]

    def test_invalid_mandatory_non_bool(self) -> None:
        with pytest.raises(ValueError):
            ComplianceRequirement(requirement_id="req-1", title="Req A", created_at=DT, mandatory=1)  # type: ignore[arg-type]

    def test_control_ids_frozen_as_tuple(self) -> None:
        cr = ComplianceRequirement(requirement_id="req-1", title="Req A", created_at=DT, control_ids=["c-1"])  # type: ignore[arg-type]
        assert isinstance(cr.control_ids, tuple)
        assert cr.control_ids == ("c-1",)

    def test_evidence_source_kinds_frozen_as_tuple(self) -> None:
        cr = ComplianceRequirement(
            requirement_id="req-1",
            title="Req A",
            created_at=DT,
            evidence_source_kinds=["artifact"],  # type: ignore[arg-type]
        )
        assert isinstance(cr.evidence_source_kinds, tuple)
        assert cr.evidence_source_kinds == ("artifact",)

    def test_metadata_frozen_as_mapping_proxy(self) -> None:
        cr = ComplianceRequirement(requirement_id="req-1", title="Req A", created_at=DT, metadata={"a": 1})
        assert isinstance(cr.metadata, MappingProxyType)

    def test_invalid_mandatory_string(self) -> None:
        with pytest.raises(ValueError):
            ComplianceRequirement(requirement_id="req-1", title="Req A", created_at=DT, mandatory="yes")  # type: ignore[arg-type]

    def test_to_dict_contains_all_fields(self) -> None:
        cr = ComplianceRequirement(requirement_id="req-1", title="Req A", created_at=DT)
        d = cr.to_dict()
        expected_keys = {
            "requirement_id", "title", "description", "category", "mandatory",
            "control_ids", "evidence_source_kinds", "created_at", "metadata",
        }
        assert set(d.keys()) == expected_keys


# ===================================================================
# ExceptionRequest tests
# ===================================================================


class TestExceptionRequest:
    def test_valid_defaults(self) -> None:
        e = ExceptionRequest(exception_id="ex-1", control_id="c-1", requested_at=DT)
        assert e.exception_id == "ex-1"
        assert e.control_id == "c-1"
        assert e.status is ExceptionStatus.REQUESTED
        assert e.reason == ""
        assert e.requested_by == ""
        assert e.approved_by == ""
        assert e.expires_at == ""
        assert e.resolved_at == ""
        assert isinstance(e.metadata, MappingProxyType)

    def test_valid_all_fields(self) -> None:
        e = ExceptionRequest(
            exception_id="ex-2",
            control_id="c-2",
            scope_ref_id="scope-1",
            status=ExceptionStatus.APPROVED,
            reason="business need",
            requested_by="alice",
            approved_by="bob",
            expires_at=DT2,
            requested_at=DT,
            resolved_at=DT2,
            metadata={"ticket": "T-1"},
        )
        assert e.status is ExceptionStatus.APPROVED
        assert e.reason == "business need"
        assert e.approved_by == "bob"

    def test_to_dict_preserves_enums(self) -> None:
        e = ExceptionRequest(exception_id="ex-1", control_id="c-1", requested_at=DT)
        d = e.to_dict()
        assert d["status"] is ExceptionStatus.REQUESTED

    def test_frozen_immutability(self) -> None:
        e = ExceptionRequest(exception_id="ex-1", control_id="c-1", requested_at=DT)
        with pytest.raises(AttributeError):
            e.exception_id = "x"  # type: ignore[misc]

    def test_invalid_exception_id_empty(self) -> None:
        with pytest.raises(ValueError):
            ExceptionRequest(exception_id="", control_id="c-1", requested_at=DT)

    def test_invalid_control_id_empty(self) -> None:
        with pytest.raises(ValueError):
            ExceptionRequest(exception_id="ex-1", control_id="", requested_at=DT)

    def test_invalid_requested_at_bad_datetime(self) -> None:
        with pytest.raises(ValueError):
            ExceptionRequest(exception_id="ex-1", control_id="c-1", requested_at="not-a-date")

    def test_invalid_requested_at_empty(self) -> None:
        with pytest.raises(ValueError):
            ExceptionRequest(exception_id="ex-1", control_id="c-1", requested_at="")

    def test_invalid_status_type(self) -> None:
        with pytest.raises(ValueError):
            ExceptionRequest(exception_id="ex-1", control_id="c-1", requested_at=DT, status="approved")  # type: ignore[arg-type]

    def test_metadata_frozen_as_mapping_proxy(self) -> None:
        e = ExceptionRequest(exception_id="ex-1", control_id="c-1", requested_at=DT, metadata={"k": "v"})
        assert isinstance(e.metadata, MappingProxyType)

    def test_resolved_at_accepts_empty(self) -> None:
        e = ExceptionRequest(exception_id="ex-1", control_id="c-1", requested_at=DT, resolved_at="")
        assert e.resolved_at == ""

    def test_to_dict_contains_all_fields(self) -> None:
        e = ExceptionRequest(exception_id="ex-1", control_id="c-1", requested_at=DT)
        d = e.to_dict()
        expected_keys = {
            "exception_id", "control_id", "scope_ref_id", "status", "reason",
            "requested_by", "approved_by", "expires_at", "requested_at",
            "resolved_at", "metadata",
        }
        assert set(d.keys()) == expected_keys

    def test_invalid_exception_id_whitespace_only(self) -> None:
        with pytest.raises(ValueError):
            ExceptionRequest(exception_id="   ", control_id="c-1", requested_at=DT)


# ===================================================================
# RiskAssessment tests
# ===================================================================


class TestRiskAssessment:
    def test_valid_defaults(self) -> None:
        a = RiskAssessment(assessment_id="a-1", assessed_at=DT)
        assert a.assessment_id == "a-1"
        assert a.overall_severity is RiskSeverity.LOW
        assert a.risk_count == 0
        assert a.critical_risks == 0
        assert a.high_risks == 0
        assert a.unmitigated_risks == 0
        assert a.risk_score == 0.0
        assert isinstance(a.metadata, MappingProxyType)

    def test_valid_all_fields(self) -> None:
        a = RiskAssessment(
            assessment_id="a-2",
            scope_ref_id="scope-1",
            overall_severity=RiskSeverity.HIGH,
            risk_count=10,
            critical_risks=2,
            high_risks=3,
            unmitigated_risks=1,
            risk_score=0.75,
            assessed_at=DT,
            metadata={"ver": 2},
        )
        assert a.overall_severity is RiskSeverity.HIGH
        assert a.risk_count == 10
        assert a.risk_score == 0.75

    def test_to_dict_preserves_enums(self) -> None:
        a = RiskAssessment(assessment_id="a-1", assessed_at=DT)
        d = a.to_dict()
        assert d["overall_severity"] is RiskSeverity.LOW

    def test_frozen_immutability(self) -> None:
        a = RiskAssessment(assessment_id="a-1", assessed_at=DT)
        with pytest.raises(AttributeError):
            a.assessment_id = "x"  # type: ignore[misc]

    def test_invalid_assessment_id_empty(self) -> None:
        with pytest.raises(ValueError):
            RiskAssessment(assessment_id="", assessed_at=DT)

    def test_invalid_assessed_at_bad_datetime(self) -> None:
        with pytest.raises(ValueError):
            RiskAssessment(assessment_id="a-1", assessed_at="not-a-date")

    def test_invalid_assessed_at_empty(self) -> None:
        with pytest.raises(ValueError):
            RiskAssessment(assessment_id="a-1", assessed_at="")

    def test_invalid_overall_severity_type(self) -> None:
        with pytest.raises(ValueError):
            RiskAssessment(assessment_id="a-1", assessed_at=DT, overall_severity="high")  # type: ignore[arg-type]

    def test_invalid_risk_count_negative(self) -> None:
        with pytest.raises(ValueError):
            RiskAssessment(assessment_id="a-1", assessed_at=DT, risk_count=-1)

    def test_invalid_critical_risks_negative(self) -> None:
        with pytest.raises(ValueError):
            RiskAssessment(assessment_id="a-1", assessed_at=DT, critical_risks=-1)

    def test_invalid_high_risks_negative(self) -> None:
        with pytest.raises(ValueError):
            RiskAssessment(assessment_id="a-1", assessed_at=DT, high_risks=-1)

    def test_invalid_unmitigated_risks_negative(self) -> None:
        with pytest.raises(ValueError):
            RiskAssessment(assessment_id="a-1", assessed_at=DT, unmitigated_risks=-1)

    def test_invalid_risk_score_too_high(self) -> None:
        with pytest.raises(ValueError):
            RiskAssessment(assessment_id="a-1", assessed_at=DT, risk_score=1.5)

    def test_invalid_risk_score_negative(self) -> None:
        with pytest.raises(ValueError):
            RiskAssessment(assessment_id="a-1", assessed_at=DT, risk_score=-0.1)

    def test_metadata_frozen_as_mapping_proxy(self) -> None:
        a = RiskAssessment(assessment_id="a-1", assessed_at=DT, metadata={"k": "v"})
        assert isinstance(a.metadata, MappingProxyType)

    def test_risk_score_boundary_one(self) -> None:
        a = RiskAssessment(assessment_id="a-1", assessed_at=DT, risk_score=1.0)
        assert a.risk_score == 1.0

    def test_risk_score_boundary_zero(self) -> None:
        a = RiskAssessment(assessment_id="a-1", assessed_at=DT, risk_score=0.0)
        assert a.risk_score == 0.0

    def test_invalid_risk_count_bool(self) -> None:
        with pytest.raises(ValueError):
            RiskAssessment(assessment_id="a-1", assessed_at=DT, risk_count=True)  # type: ignore[arg-type]

    def test_to_dict_contains_all_fields(self) -> None:
        a = RiskAssessment(assessment_id="a-1", assessed_at=DT)
        d = a.to_dict()
        expected_keys = {
            "assessment_id", "scope_ref_id", "overall_severity", "risk_count",
            "critical_risks", "high_risks", "unmitigated_risks", "risk_score",
            "assessed_at", "metadata",
        }
        assert set(d.keys()) == expected_keys


# ===================================================================
# ComplianceSnapshot tests
# ===================================================================


class TestComplianceSnapshot:
    def test_valid_defaults(self) -> None:
        s = ComplianceSnapshot(snapshot_id="s-1", captured_at=DT)
        assert s.snapshot_id == "s-1"
        assert s.disposition is ComplianceDisposition.NOT_ASSESSED
        assert s.total_controls == 0
        assert s.passing_controls == 0
        assert s.failing_controls == 0
        assert s.exceptions_active == 0
        assert s.compliance_pct == 0.0
        assert isinstance(s.metadata, MappingProxyType)

    def test_valid_all_fields(self) -> None:
        s = ComplianceSnapshot(
            snapshot_id="s-2",
            scope_ref_id="scope-1",
            disposition=ComplianceDisposition.COMPLIANT,
            total_controls=20,
            passing_controls=18,
            failing_controls=2,
            exceptions_active=1,
            compliance_pct=90.0,
            captured_at=DT,
            metadata={"src": "daily"},
        )
        assert s.disposition is ComplianceDisposition.COMPLIANT
        assert s.total_controls == 20
        assert s.compliance_pct == 90.0

    def test_to_dict_preserves_enums(self) -> None:
        s = ComplianceSnapshot(snapshot_id="s-1", captured_at=DT)
        d = s.to_dict()
        assert d["disposition"] is ComplianceDisposition.NOT_ASSESSED

    def test_frozen_immutability(self) -> None:
        s = ComplianceSnapshot(snapshot_id="s-1", captured_at=DT)
        with pytest.raises(AttributeError):
            s.snapshot_id = "x"  # type: ignore[misc]

    def test_invalid_snapshot_id_empty(self) -> None:
        with pytest.raises(ValueError):
            ComplianceSnapshot(snapshot_id="", captured_at=DT)

    def test_invalid_captured_at_bad_datetime(self) -> None:
        with pytest.raises(ValueError):
            ComplianceSnapshot(snapshot_id="s-1", captured_at="not-a-date")

    def test_invalid_captured_at_empty(self) -> None:
        with pytest.raises(ValueError):
            ComplianceSnapshot(snapshot_id="s-1", captured_at="")

    def test_invalid_disposition_type(self) -> None:
        with pytest.raises(ValueError):
            ComplianceSnapshot(snapshot_id="s-1", captured_at=DT, disposition="compliant")  # type: ignore[arg-type]

    def test_invalid_total_controls_negative(self) -> None:
        with pytest.raises(ValueError):
            ComplianceSnapshot(snapshot_id="s-1", captured_at=DT, total_controls=-1)

    def test_invalid_passing_controls_negative(self) -> None:
        with pytest.raises(ValueError):
            ComplianceSnapshot(snapshot_id="s-1", captured_at=DT, passing_controls=-1)

    def test_invalid_failing_controls_negative(self) -> None:
        with pytest.raises(ValueError):
            ComplianceSnapshot(snapshot_id="s-1", captured_at=DT, failing_controls=-1)

    def test_invalid_exceptions_active_negative(self) -> None:
        with pytest.raises(ValueError):
            ComplianceSnapshot(snapshot_id="s-1", captured_at=DT, exceptions_active=-1)

    def test_invalid_compliance_pct_negative(self) -> None:
        with pytest.raises(ValueError):
            ComplianceSnapshot(snapshot_id="s-1", captured_at=DT, compliance_pct=-1.0)

    def test_metadata_frozen_as_mapping_proxy(self) -> None:
        s = ComplianceSnapshot(snapshot_id="s-1", captured_at=DT, metadata={"k": "v"})
        assert isinstance(s.metadata, MappingProxyType)

    def test_invalid_total_controls_bool(self) -> None:
        with pytest.raises(ValueError):
            ComplianceSnapshot(snapshot_id="s-1", captured_at=DT, total_controls=True)  # type: ignore[arg-type]

    def test_compliance_pct_accepts_large_value(self) -> None:
        s = ComplianceSnapshot(snapshot_id="s-1", captured_at=DT, compliance_pct=100.0)
        assert s.compliance_pct == 100.0

    def test_to_dict_contains_all_fields(self) -> None:
        s = ComplianceSnapshot(snapshot_id="s-1", captured_at=DT)
        d = s.to_dict()
        expected_keys = {
            "snapshot_id", "scope_ref_id", "disposition", "total_controls",
            "passing_controls", "failing_controls", "exceptions_active",
            "compliance_pct", "captured_at", "metadata",
        }
        assert set(d.keys()) == expected_keys


# ===================================================================
# ControlFailure tests
# ===================================================================


class TestControlFailure:
    def test_valid_defaults(self) -> None:
        f = ControlFailure(failure_id="f-1", control_id="c-1", recorded_at=DT)
        assert f.failure_id == "f-1"
        assert f.control_id == "c-1"
        assert f.severity is RiskSeverity.MEDIUM
        assert f.action_taken == ""
        assert f.escalated is False
        assert f.blocked is False
        assert isinstance(f.metadata, MappingProxyType)

    def test_valid_all_fields(self) -> None:
        f = ControlFailure(
            failure_id="f-2",
            control_id="c-2",
            test_id="t-1",
            scope_ref_id="scope-1",
            severity=RiskSeverity.CRITICAL,
            action_taken="escalated to on-call",
            escalated=True,
            blocked=True,
            recorded_at=DT,
            metadata={"alert": "yes"},
        )
        assert f.severity is RiskSeverity.CRITICAL
        assert f.escalated is True
        assert f.blocked is True

    def test_to_dict_preserves_enums(self) -> None:
        f = ControlFailure(failure_id="f-1", control_id="c-1", recorded_at=DT)
        d = f.to_dict()
        assert d["severity"] is RiskSeverity.MEDIUM

    def test_frozen_immutability(self) -> None:
        f = ControlFailure(failure_id="f-1", control_id="c-1", recorded_at=DT)
        with pytest.raises(AttributeError):
            f.failure_id = "x"  # type: ignore[misc]

    def test_invalid_failure_id_empty(self) -> None:
        with pytest.raises(ValueError):
            ControlFailure(failure_id="", control_id="c-1", recorded_at=DT)

    def test_invalid_control_id_empty(self) -> None:
        with pytest.raises(ValueError):
            ControlFailure(failure_id="f-1", control_id="", recorded_at=DT)

    def test_invalid_recorded_at_bad_datetime(self) -> None:
        with pytest.raises(ValueError):
            ControlFailure(failure_id="f-1", control_id="c-1", recorded_at="not-a-date")

    def test_invalid_recorded_at_empty(self) -> None:
        with pytest.raises(ValueError):
            ControlFailure(failure_id="f-1", control_id="c-1", recorded_at="")

    def test_invalid_severity_type(self) -> None:
        with pytest.raises(ValueError):
            ControlFailure(failure_id="f-1", control_id="c-1", recorded_at=DT, severity="high")  # type: ignore[arg-type]

    def test_invalid_escalated_non_bool(self) -> None:
        with pytest.raises(ValueError):
            ControlFailure(failure_id="f-1", control_id="c-1", recorded_at=DT, escalated=1)  # type: ignore[arg-type]

    def test_invalid_blocked_non_bool(self) -> None:
        with pytest.raises(ValueError):
            ControlFailure(failure_id="f-1", control_id="c-1", recorded_at=DT, blocked=1)  # type: ignore[arg-type]

    def test_invalid_escalated_string(self) -> None:
        with pytest.raises(ValueError):
            ControlFailure(failure_id="f-1", control_id="c-1", recorded_at=DT, escalated="true")  # type: ignore[arg-type]

    def test_invalid_blocked_string(self) -> None:
        with pytest.raises(ValueError):
            ControlFailure(failure_id="f-1", control_id="c-1", recorded_at=DT, blocked="false")  # type: ignore[arg-type]

    def test_metadata_frozen_as_mapping_proxy(self) -> None:
        f = ControlFailure(failure_id="f-1", control_id="c-1", recorded_at=DT, metadata={"k": "v"})
        assert isinstance(f.metadata, MappingProxyType)

    def test_to_dict_contains_all_fields(self) -> None:
        f = ControlFailure(failure_id="f-1", control_id="c-1", recorded_at=DT)
        d = f.to_dict()
        expected_keys = {
            "failure_id", "control_id", "test_id", "scope_ref_id", "severity",
            "action_taken", "escalated", "blocked", "recorded_at", "metadata",
        }
        assert set(d.keys()) == expected_keys

    def test_invalid_failure_id_whitespace_only(self) -> None:
        with pytest.raises(ValueError):
            ControlFailure(failure_id="   ", control_id="c-1", recorded_at=DT)


# ===================================================================
# AssuranceReport tests
# ===================================================================


class TestAssuranceReport:
    def test_valid_defaults(self) -> None:
        r = AssuranceReport(report_id="rpt-1", generated_at=DT)
        assert r.report_id == "rpt-1"
        assert r.overall_disposition is ComplianceDisposition.NOT_ASSESSED
        assert r.overall_risk_severity is RiskSeverity.LOW
        assert r.total_requirements == 0
        assert r.met_requirements == 0
        assert r.total_controls == 0
        assert r.passing_controls == 0
        assert r.failing_controls == 0
        assert r.active_exceptions == 0
        assert r.total_failures == 0
        assert r.risk_score == 0.0
        assert r.compliance_pct == 0.0
        assert isinstance(r.metadata, MappingProxyType)

    def test_valid_all_fields(self) -> None:
        r = AssuranceReport(
            report_id="rpt-2",
            scope_ref_id="scope-1",
            overall_disposition=ComplianceDisposition.COMPLIANT,
            overall_risk_severity=RiskSeverity.HIGH,
            total_requirements=50,
            met_requirements=48,
            total_controls=100,
            passing_controls=95,
            failing_controls=5,
            active_exceptions=2,
            total_failures=3,
            risk_score=0.6,
            compliance_pct=95.0,
            generated_at=DT,
            metadata={"quarter": "Q1"},
        )
        assert r.overall_disposition is ComplianceDisposition.COMPLIANT
        assert r.overall_risk_severity is RiskSeverity.HIGH
        assert r.total_requirements == 50
        assert r.compliance_pct == 95.0

    def test_to_dict_preserves_enums(self) -> None:
        r = AssuranceReport(report_id="rpt-1", generated_at=DT)
        d = r.to_dict()
        assert d["overall_disposition"] is ComplianceDisposition.NOT_ASSESSED
        assert d["overall_risk_severity"] is RiskSeverity.LOW

    def test_frozen_immutability(self) -> None:
        r = AssuranceReport(report_id="rpt-1", generated_at=DT)
        with pytest.raises(AttributeError):
            r.report_id = "x"  # type: ignore[misc]

    def test_invalid_report_id_empty(self) -> None:
        with pytest.raises(ValueError):
            AssuranceReport(report_id="", generated_at=DT)

    def test_invalid_generated_at_bad_datetime(self) -> None:
        with pytest.raises(ValueError):
            AssuranceReport(report_id="rpt-1", generated_at="not-a-date")

    def test_invalid_generated_at_empty(self) -> None:
        with pytest.raises(ValueError):
            AssuranceReport(report_id="rpt-1", generated_at="")

    def test_invalid_overall_disposition_type(self) -> None:
        with pytest.raises(ValueError):
            AssuranceReport(report_id="rpt-1", generated_at=DT, overall_disposition="compliant")  # type: ignore[arg-type]

    def test_invalid_overall_risk_severity_type(self) -> None:
        with pytest.raises(ValueError):
            AssuranceReport(report_id="rpt-1", generated_at=DT, overall_risk_severity="low")  # type: ignore[arg-type]

    def test_invalid_total_requirements_negative(self) -> None:
        with pytest.raises(ValueError):
            AssuranceReport(report_id="rpt-1", generated_at=DT, total_requirements=-1)

    def test_invalid_met_requirements_negative(self) -> None:
        with pytest.raises(ValueError):
            AssuranceReport(report_id="rpt-1", generated_at=DT, met_requirements=-1)

    def test_invalid_total_controls_negative(self) -> None:
        with pytest.raises(ValueError):
            AssuranceReport(report_id="rpt-1", generated_at=DT, total_controls=-1)

    def test_invalid_passing_controls_negative(self) -> None:
        with pytest.raises(ValueError):
            AssuranceReport(report_id="rpt-1", generated_at=DT, passing_controls=-1)

    def test_invalid_failing_controls_negative(self) -> None:
        with pytest.raises(ValueError):
            AssuranceReport(report_id="rpt-1", generated_at=DT, failing_controls=-1)

    def test_invalid_active_exceptions_negative(self) -> None:
        with pytest.raises(ValueError):
            AssuranceReport(report_id="rpt-1", generated_at=DT, active_exceptions=-1)

    def test_invalid_total_failures_negative(self) -> None:
        with pytest.raises(ValueError):
            AssuranceReport(report_id="rpt-1", generated_at=DT, total_failures=-1)

    def test_invalid_risk_score_too_high(self) -> None:
        with pytest.raises(ValueError):
            AssuranceReport(report_id="rpt-1", generated_at=DT, risk_score=1.5)

    def test_invalid_risk_score_negative(self) -> None:
        with pytest.raises(ValueError):
            AssuranceReport(report_id="rpt-1", generated_at=DT, risk_score=-0.1)

    def test_invalid_compliance_pct_negative(self) -> None:
        with pytest.raises(ValueError):
            AssuranceReport(report_id="rpt-1", generated_at=DT, compliance_pct=-1.0)

    def test_metadata_frozen_as_mapping_proxy(self) -> None:
        r = AssuranceReport(report_id="rpt-1", generated_at=DT, metadata={"k": "v"})
        assert isinstance(r.metadata, MappingProxyType)

    def test_invalid_report_id_whitespace_only(self) -> None:
        with pytest.raises(ValueError):
            AssuranceReport(report_id="   ", generated_at=DT)

    def test_risk_score_boundary_one(self) -> None:
        r = AssuranceReport(report_id="rpt-1", generated_at=DT, risk_score=1.0)
        assert r.risk_score == 1.0

    def test_compliance_pct_accepts_large_value(self) -> None:
        r = AssuranceReport(report_id="rpt-1", generated_at=DT, compliance_pct=100.0)
        assert r.compliance_pct == 100.0

    def test_invalid_total_requirements_bool(self) -> None:
        with pytest.raises(ValueError):
            AssuranceReport(report_id="rpt-1", generated_at=DT, total_requirements=True)  # type: ignore[arg-type]

    def test_to_dict_contains_all_fields(self) -> None:
        r = AssuranceReport(report_id="rpt-1", generated_at=DT)
        d = r.to_dict()
        expected_keys = {
            "report_id", "scope_ref_id", "overall_disposition",
            "overall_risk_severity", "total_requirements", "met_requirements",
            "total_controls", "passing_controls", "failing_controls",
            "active_exceptions", "total_failures", "risk_score",
            "compliance_pct", "generated_at", "metadata",
        }
        assert set(d.keys()) == expected_keys
