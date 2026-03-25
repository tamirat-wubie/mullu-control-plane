"""Tests for data governance contracts: DataRecord, DataPolicy, ResidencyConstraint,
PrivacyRule, RedactionRule, RetentionRule, HandlingDecision, DataViolation,
DataGovernanceSnapshot, DataClosureReport, and all associated enums."""

from __future__ import annotations

from types import MappingProxyType

import pytest

from mcoi_runtime.contracts.data_governance import (
    DataClassification,
    DataClosureReport,
    DataGovernanceSnapshot,
    DataPolicy,
    DataRecord,
    DataViolation,
    GovernanceDecision,
    HandlingDecision,
    HandlingDisposition,
    PrivacyBasis,
    PrivacyRule,
    RedactionLevel,
    RedactionRule,
    ResidencyConstraint,
    ResidencyRegion,
    RetentionDisposition,
    RetentionRule,
)


TS = "2025-06-01T12:00:00+00:00"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_data_record(**overrides) -> DataRecord:
    defaults = dict(
        data_id="dr-1",
        tenant_id="t-1",
        created_at=TS,
    )
    defaults.update(overrides)
    return DataRecord(**defaults)


def _make_data_policy(**overrides) -> DataPolicy:
    defaults = dict(
        policy_id="pol-1",
        tenant_id="t-1",
        created_at=TS,
    )
    defaults.update(overrides)
    return DataPolicy(**defaults)


def _make_residency_constraint(**overrides) -> ResidencyConstraint:
    defaults = dict(
        constraint_id="rc-1",
        tenant_id="t-1",
        created_at=TS,
    )
    defaults.update(overrides)
    return ResidencyConstraint(**defaults)


def _make_privacy_rule(**overrides) -> PrivacyRule:
    defaults = dict(
        rule_id="priv-1",
        tenant_id="t-1",
        created_at=TS,
    )
    defaults.update(overrides)
    return PrivacyRule(**defaults)


def _make_redaction_rule(**overrides) -> RedactionRule:
    defaults = dict(
        rule_id="red-1",
        tenant_id="t-1",
        created_at=TS,
    )
    defaults.update(overrides)
    return RedactionRule(**defaults)


def _make_retention_rule(**overrides) -> RetentionRule:
    defaults = dict(
        rule_id="ret-1",
        tenant_id="t-1",
        created_at=TS,
    )
    defaults.update(overrides)
    return RetentionRule(**defaults)


def _make_handling_decision(**overrides) -> HandlingDecision:
    defaults = dict(
        decision_id="hd-1",
        data_id="dr-1",
        tenant_id="t-1",
        operation="read",
        decided_at=TS,
    )
    defaults.update(overrides)
    return HandlingDecision(**defaults)


def _make_data_violation(**overrides) -> DataViolation:
    defaults = dict(
        violation_id="vio-1",
        data_id="dr-1",
        tenant_id="t-1",
        operation="export",
        detected_at=TS,
    )
    defaults.update(overrides)
    return DataViolation(**defaults)


def _make_governance_snapshot(**overrides) -> DataGovernanceSnapshot:
    defaults = dict(
        snapshot_id="snap-1",
        captured_at=TS,
    )
    defaults.update(overrides)
    return DataGovernanceSnapshot(**defaults)


def _make_closure_report(**overrides) -> DataClosureReport:
    defaults = dict(
        report_id="rpt-1",
        tenant_id="t-1",
        closed_at=TS,
    )
    defaults.update(overrides)
    return DataClosureReport(**defaults)


# ===================================================================
# Enum tests
# ===================================================================


class TestDataClassificationEnum:
    def test_member_count(self):
        assert len(DataClassification) == 7

    def test_all_members(self):
        expected = {"PUBLIC", "INTERNAL", "CONFIDENTIAL", "SENSITIVE", "RESTRICTED", "PII", "SECRET"}
        assert {m.name for m in DataClassification} == expected

    def test_values(self):
        assert DataClassification.PUBLIC.value == "public"
        assert DataClassification.PII.value == "pii"
        assert DataClassification.SECRET.value == "secret"


class TestResidencyRegionEnum:
    def test_member_count(self):
        assert len(ResidencyRegion) == 6

    def test_all_members(self):
        expected = {"US", "EU", "UK", "APAC", "GLOBAL", "RESTRICTED"}
        assert {m.name for m in ResidencyRegion} == expected

    def test_values(self):
        assert ResidencyRegion.US.value == "us"
        assert ResidencyRegion.GLOBAL.value == "global"


class TestHandlingDispositionEnum:
    def test_member_count(self):
        assert len(HandlingDisposition) == 5

    def test_all_members(self):
        expected = {"ALLOW", "REDACT", "DENY", "ENCRYPT", "AUDIT_ONLY"}
        assert {m.name for m in HandlingDisposition} == expected

    def test_values(self):
        assert HandlingDisposition.DENY.value == "deny"
        assert HandlingDisposition.AUDIT_ONLY.value == "audit_only"


class TestPrivacyBasisEnum:
    def test_member_count(self):
        assert len(PrivacyBasis) == 6

    def test_all_members(self):
        expected = {
            "CONSENT", "CONTRACT", "LEGAL_OBLIGATION",
            "VITAL_INTEREST", "PUBLIC_INTEREST", "LEGITIMATE_INTEREST",
        }
        assert {m.name for m in PrivacyBasis} == expected

    def test_values(self):
        assert PrivacyBasis.CONSENT.value == "consent"
        assert PrivacyBasis.LEGITIMATE_INTEREST.value == "legitimate_interest"


class TestRedactionLevelEnum:
    def test_member_count(self):
        assert len(RedactionLevel) == 5

    def test_all_members(self):
        expected = {"NONE", "PARTIAL", "FULL", "TOKENIZE", "HASH"}
        assert {m.name for m in RedactionLevel} == expected

    def test_values(self):
        assert RedactionLevel.NONE.value == "none"
        assert RedactionLevel.HASH.value == "hash"


class TestRetentionDispositionEnum:
    def test_member_count(self):
        assert len(RetentionDisposition) == 4

    def test_all_members(self):
        expected = {"DELETE", "ARCHIVE", "ANONYMIZE", "REVIEW"}
        assert {m.name for m in RetentionDisposition} == expected

    def test_values(self):
        assert RetentionDisposition.DELETE.value == "delete"
        assert RetentionDisposition.REVIEW.value == "review"


class TestGovernanceDecisionEnum:
    def test_member_count(self):
        assert len(GovernanceDecision) == 5

    def test_all_members(self):
        expected = {"ALLOWED", "DENIED", "REDACTED", "REQUIRES_REVIEW", "VIOLATION"}
        assert {m.name for m in GovernanceDecision} == expected

    def test_values(self):
        assert GovernanceDecision.ALLOWED.value == "allowed"
        assert GovernanceDecision.REQUIRES_REVIEW.value == "requires_review"


# ===================================================================
# DataRecord
# ===================================================================


class TestDataRecord:
    def test_valid_defaults(self):
        rec = _make_data_record()
        assert rec.data_id == "dr-1"
        assert rec.tenant_id == "t-1"
        assert rec.classification is DataClassification.INTERNAL
        assert rec.residency is ResidencyRegion.GLOBAL
        assert rec.privacy_basis is PrivacyBasis.LEGITIMATE_INTEREST
        assert rec.domain == ""
        assert rec.source_id == ""
        assert rec.created_at == TS

    def test_all_fields_set(self):
        rec = _make_data_record(
            classification=DataClassification.PII,
            residency=ResidencyRegion.EU,
            privacy_basis=PrivacyBasis.CONSENT,
            domain="finance",
            source_id="src-99",
            metadata={"tag": "gdpr"},
        )
        assert rec.classification is DataClassification.PII
        assert rec.residency is ResidencyRegion.EU
        assert rec.privacy_basis is PrivacyBasis.CONSENT
        assert rec.domain == "finance"
        assert rec.source_id == "src-99"
        assert rec.metadata["tag"] == "gdpr"

    def test_empty_data_id_rejected(self):
        with pytest.raises(ValueError, match="data_id"):
            _make_data_record(data_id="")

    def test_whitespace_data_id_rejected(self):
        with pytest.raises(ValueError, match="data_id"):
            _make_data_record(data_id="   ")

    def test_empty_tenant_id_rejected(self):
        with pytest.raises(ValueError, match="tenant_id"):
            _make_data_record(tenant_id="")

    def test_invalid_classification_rejected(self):
        with pytest.raises(ValueError, match="classification"):
            _make_data_record(classification="public")  # type: ignore[arg-type]

    def test_invalid_residency_rejected(self):
        with pytest.raises(ValueError, match="residency"):
            _make_data_record(residency="us")  # type: ignore[arg-type]

    def test_invalid_privacy_basis_rejected(self):
        with pytest.raises(ValueError, match="privacy_basis"):
            _make_data_record(privacy_basis="consent")  # type: ignore[arg-type]

    def test_empty_created_at_rejected(self):
        with pytest.raises(ValueError, match="created_at"):
            _make_data_record(created_at="")

    def test_invalid_created_at_rejected(self):
        with pytest.raises(ValueError, match="created_at"):
            _make_data_record(created_at="not-a-date")

    def test_metadata_frozen(self):
        rec = _make_data_record(metadata={"k": "v"})
        assert isinstance(rec.metadata, MappingProxyType)
        with pytest.raises(TypeError):
            rec.metadata["new"] = "nope"  # type: ignore[index]

    def test_frozen_immutable(self):
        rec = _make_data_record()
        with pytest.raises(AttributeError):
            rec.data_id = "changed"  # type: ignore[misc]

    def test_to_dict_preserves_enums(self):
        rec = _make_data_record()
        d = rec.to_dict()
        assert d["classification"] is DataClassification.INTERNAL
        assert d["residency"] is ResidencyRegion.GLOBAL
        assert d["privacy_basis"] is PrivacyBasis.LEGITIMATE_INTEREST

    def test_to_dict_returns_plain_dict_metadata(self):
        rec = _make_data_record(metadata={"a": 1})
        d = rec.to_dict()
        assert isinstance(d["metadata"], dict)

    def test_each_classification_variant(self):
        for cls in DataClassification:
            rec = _make_data_record(classification=cls)
            assert rec.classification is cls


# ===================================================================
# DataPolicy
# ===================================================================


class TestDataPolicy:
    def test_valid_defaults(self):
        pol = _make_data_policy()
        assert pol.policy_id == "pol-1"
        assert pol.tenant_id == "t-1"
        assert pol.classification is DataClassification.INTERNAL
        assert pol.disposition is HandlingDisposition.DENY
        assert pol.residency is ResidencyRegion.GLOBAL
        assert pol.scope_ref_id == ""
        assert pol.description == ""

    def test_all_fields_set(self):
        pol = _make_data_policy(
            classification=DataClassification.CONFIDENTIAL,
            disposition=HandlingDisposition.ENCRYPT,
            residency=ResidencyRegion.UK,
            scope_ref_id="scope-5",
            description="UK encrypt policy",
            metadata={"priority": "high"},
        )
        assert pol.disposition is HandlingDisposition.ENCRYPT
        assert pol.residency is ResidencyRegion.UK
        assert pol.description == "UK encrypt policy"

    def test_empty_policy_id_rejected(self):
        with pytest.raises(ValueError, match="policy_id"):
            _make_data_policy(policy_id="")

    def test_empty_tenant_id_rejected(self):
        with pytest.raises(ValueError, match="tenant_id"):
            _make_data_policy(tenant_id="")

    def test_invalid_classification_rejected(self):
        with pytest.raises(ValueError, match="classification"):
            _make_data_policy(classification="internal")  # type: ignore[arg-type]

    def test_invalid_disposition_rejected(self):
        with pytest.raises(ValueError, match="disposition"):
            _make_data_policy(disposition="allow")  # type: ignore[arg-type]

    def test_invalid_residency_rejected(self):
        with pytest.raises(ValueError, match="residency"):
            _make_data_policy(residency="eu")  # type: ignore[arg-type]

    def test_invalid_created_at_rejected(self):
        with pytest.raises(ValueError, match="created_at"):
            _make_data_policy(created_at="bad")

    def test_metadata_frozen(self):
        pol = _make_data_policy(metadata={"x": 1})
        assert isinstance(pol.metadata, MappingProxyType)

    def test_frozen_immutable(self):
        pol = _make_data_policy()
        with pytest.raises(AttributeError):
            pol.policy_id = "changed"  # type: ignore[misc]

    def test_to_dict_preserves_enums(self):
        pol = _make_data_policy()
        d = pol.to_dict()
        assert d["classification"] is DataClassification.INTERNAL
        assert d["disposition"] is HandlingDisposition.DENY
        assert d["residency"] is ResidencyRegion.GLOBAL

    def test_each_disposition_variant(self):
        for disp in HandlingDisposition:
            pol = _make_data_policy(disposition=disp)
            assert pol.disposition is disp


# ===================================================================
# ResidencyConstraint
# ===================================================================


class TestResidencyConstraint:
    def test_valid_defaults(self):
        rc = _make_residency_constraint()
        assert rc.constraint_id == "rc-1"
        assert rc.tenant_id == "t-1"
        assert rc.allowed_regions == ()
        assert rc.denied_regions == ()
        assert rc.created_at == TS

    def test_with_regions(self):
        rc = _make_residency_constraint(
            allowed_regions=["us", "eu"],
            denied_regions=["cn"],
        )
        assert rc.allowed_regions == ("us", "eu")
        assert rc.denied_regions == ("cn",)

    def test_list_regions_frozen_to_tuple(self):
        rc = _make_residency_constraint(allowed_regions=["us"])
        assert isinstance(rc.allowed_regions, tuple)

    def test_empty_constraint_id_rejected(self):
        with pytest.raises(ValueError, match="constraint_id"):
            _make_residency_constraint(constraint_id="")

    def test_empty_tenant_id_rejected(self):
        with pytest.raises(ValueError, match="tenant_id"):
            _make_residency_constraint(tenant_id="")

    def test_invalid_created_at_rejected(self):
        with pytest.raises(ValueError, match="created_at"):
            _make_residency_constraint(created_at="nope")

    def test_metadata_frozen(self):
        rc = _make_residency_constraint(metadata={"region": "us"})
        assert isinstance(rc.metadata, MappingProxyType)

    def test_frozen_immutable(self):
        rc = _make_residency_constraint()
        with pytest.raises(AttributeError):
            rc.constraint_id = "changed"  # type: ignore[misc]

    def test_to_dict_regions_as_lists(self):
        rc = _make_residency_constraint(allowed_regions=["us", "eu"])
        d = rc.to_dict()
        assert d["allowed_regions"] == ["us", "eu"]
        assert isinstance(d["allowed_regions"], list)

    def test_to_dict_metadata_plain_dict(self):
        rc = _make_residency_constraint(metadata={"k": "v"})
        d = rc.to_dict()
        assert isinstance(d["metadata"], dict)


# ===================================================================
# PrivacyRule
# ===================================================================


class TestPrivacyRule:
    def test_valid_defaults(self):
        rule = _make_privacy_rule()
        assert rule.rule_id == "priv-1"
        assert rule.tenant_id == "t-1"
        assert rule.classification is DataClassification.PII
        assert rule.required_basis is PrivacyBasis.CONSENT
        assert rule.scope_ref_id == ""
        assert rule.description == ""

    def test_all_fields_set(self):
        rule = _make_privacy_rule(
            classification=DataClassification.SENSITIVE,
            required_basis=PrivacyBasis.CONTRACT,
            scope_ref_id="scope-2",
            description="contract basis for sensitive data",
        )
        assert rule.classification is DataClassification.SENSITIVE
        assert rule.required_basis is PrivacyBasis.CONTRACT
        assert rule.description == "contract basis for sensitive data"

    def test_empty_rule_id_rejected(self):
        with pytest.raises(ValueError, match="rule_id"):
            _make_privacy_rule(rule_id="")

    def test_empty_tenant_id_rejected(self):
        with pytest.raises(ValueError, match="tenant_id"):
            _make_privacy_rule(tenant_id="")

    def test_invalid_classification_rejected(self):
        with pytest.raises(ValueError, match="classification"):
            _make_privacy_rule(classification="pii")  # type: ignore[arg-type]

    def test_invalid_required_basis_rejected(self):
        with pytest.raises(ValueError, match="required_basis"):
            _make_privacy_rule(required_basis="consent")  # type: ignore[arg-type]

    def test_invalid_created_at_rejected(self):
        with pytest.raises(ValueError, match="created_at"):
            _make_privacy_rule(created_at="bad-date")

    def test_frozen_immutable(self):
        rule = _make_privacy_rule()
        with pytest.raises(AttributeError):
            rule.rule_id = "changed"  # type: ignore[misc]

    def test_to_dict_preserves_enums(self):
        rule = _make_privacy_rule()
        d = rule.to_dict()
        assert d["classification"] is DataClassification.PII
        assert d["required_basis"] is PrivacyBasis.CONSENT

    def test_each_privacy_basis_variant(self):
        for basis in PrivacyBasis:
            rule = _make_privacy_rule(required_basis=basis)
            assert rule.required_basis is basis


# ===================================================================
# RedactionRule
# ===================================================================


class TestRedactionRule:
    def test_valid_defaults(self):
        rule = _make_redaction_rule()
        assert rule.rule_id == "red-1"
        assert rule.tenant_id == "t-1"
        assert rule.classification is DataClassification.SENSITIVE
        assert rule.redaction_level is RedactionLevel.FULL
        assert rule.scope_ref_id == ""
        assert rule.field_patterns == ()

    def test_with_field_patterns(self):
        rule = _make_redaction_rule(field_patterns=["ssn", "email", "phone"])
        assert rule.field_patterns == ("ssn", "email", "phone")

    def test_list_field_patterns_frozen_to_tuple(self):
        rule = _make_redaction_rule(field_patterns=["ssn"])
        assert isinstance(rule.field_patterns, tuple)

    def test_all_fields_set(self):
        rule = _make_redaction_rule(
            classification=DataClassification.PII,
            redaction_level=RedactionLevel.TOKENIZE,
            scope_ref_id="scope-7",
            field_patterns=["name", "address"],
        )
        assert rule.redaction_level is RedactionLevel.TOKENIZE
        assert rule.scope_ref_id == "scope-7"
        assert len(rule.field_patterns) == 2

    def test_empty_rule_id_rejected(self):
        with pytest.raises(ValueError, match="rule_id"):
            _make_redaction_rule(rule_id="")

    def test_empty_tenant_id_rejected(self):
        with pytest.raises(ValueError, match="tenant_id"):
            _make_redaction_rule(tenant_id="")

    def test_invalid_classification_rejected(self):
        with pytest.raises(ValueError, match="classification"):
            _make_redaction_rule(classification="sensitive")  # type: ignore[arg-type]

    def test_invalid_redaction_level_rejected(self):
        with pytest.raises(ValueError, match="redaction_level"):
            _make_redaction_rule(redaction_level="full")  # type: ignore[arg-type]

    def test_invalid_created_at_rejected(self):
        with pytest.raises(ValueError, match="created_at"):
            _make_redaction_rule(created_at="xyz")

    def test_frozen_immutable(self):
        rule = _make_redaction_rule()
        with pytest.raises(AttributeError):
            rule.rule_id = "changed"  # type: ignore[misc]

    def test_to_dict_preserves_enums(self):
        rule = _make_redaction_rule()
        d = rule.to_dict()
        assert d["classification"] is DataClassification.SENSITIVE
        assert d["redaction_level"] is RedactionLevel.FULL

    def test_to_dict_field_patterns_as_list(self):
        rule = _make_redaction_rule(field_patterns=["ssn", "dob"])
        d = rule.to_dict()
        assert d["field_patterns"] == ["ssn", "dob"]
        assert isinstance(d["field_patterns"], list)

    def test_each_redaction_level_variant(self):
        for level in RedactionLevel:
            rule = _make_redaction_rule(redaction_level=level)
            assert rule.redaction_level is level


# ===================================================================
# RetentionRule
# ===================================================================


class TestRetentionRule:
    def test_valid_defaults(self):
        rule = _make_retention_rule()
        assert rule.rule_id == "ret-1"
        assert rule.tenant_id == "t-1"
        assert rule.classification is DataClassification.INTERNAL
        assert rule.retention_days == 0
        assert rule.disposition is RetentionDisposition.DELETE
        assert rule.scope_ref_id == ""

    def test_all_fields_set(self):
        rule = _make_retention_rule(
            classification=DataClassification.CONFIDENTIAL,
            retention_days=365,
            disposition=RetentionDisposition.ARCHIVE,
            scope_ref_id="scope-3",
        )
        assert rule.retention_days == 365
        assert rule.disposition is RetentionDisposition.ARCHIVE

    def test_empty_rule_id_rejected(self):
        with pytest.raises(ValueError, match="rule_id"):
            _make_retention_rule(rule_id="")

    def test_empty_tenant_id_rejected(self):
        with pytest.raises(ValueError, match="tenant_id"):
            _make_retention_rule(tenant_id="")

    def test_invalid_classification_rejected(self):
        with pytest.raises(ValueError, match="classification"):
            _make_retention_rule(classification="internal")  # type: ignore[arg-type]

    def test_negative_retention_days_rejected(self):
        with pytest.raises(ValueError, match="retention_days"):
            _make_retention_rule(retention_days=-1)

    def test_bool_retention_days_rejected(self):
        with pytest.raises(ValueError, match="retention_days"):
            _make_retention_rule(retention_days=True)  # type: ignore[arg-type]

    def test_float_retention_days_rejected(self):
        with pytest.raises(ValueError, match="retention_days"):
            _make_retention_rule(retention_days=1.5)  # type: ignore[arg-type]

    def test_invalid_disposition_rejected(self):
        with pytest.raises(ValueError, match="disposition"):
            _make_retention_rule(disposition="delete")  # type: ignore[arg-type]

    def test_invalid_created_at_rejected(self):
        with pytest.raises(ValueError, match="created_at"):
            _make_retention_rule(created_at="")

    def test_frozen_immutable(self):
        rule = _make_retention_rule()
        with pytest.raises(AttributeError):
            rule.retention_days = 100  # type: ignore[misc]

    def test_to_dict_preserves_enums(self):
        rule = _make_retention_rule()
        d = rule.to_dict()
        assert d["classification"] is DataClassification.INTERNAL
        assert d["disposition"] is RetentionDisposition.DELETE

    def test_zero_retention_days_accepted(self):
        rule = _make_retention_rule(retention_days=0)
        assert rule.retention_days == 0

    def test_each_retention_disposition_variant(self):
        for disp in RetentionDisposition:
            rule = _make_retention_rule(disposition=disp)
            assert rule.disposition is disp


# ===================================================================
# HandlingDecision
# ===================================================================


class TestHandlingDecision:
    def test_valid_defaults(self):
        hd = _make_handling_decision()
        assert hd.decision_id == "hd-1"
        assert hd.data_id == "dr-1"
        assert hd.tenant_id == "t-1"
        assert hd.operation == "read"
        assert hd.decision is GovernanceDecision.DENIED
        assert hd.disposition is HandlingDisposition.DENY
        assert hd.redaction_level is RedactionLevel.NONE
        assert hd.reason == ""
        assert hd.decided_at == TS

    def test_all_fields_set(self):
        hd = _make_handling_decision(
            decision=GovernanceDecision.REDACTED,
            disposition=HandlingDisposition.REDACT,
            redaction_level=RedactionLevel.PARTIAL,
            reason="PII detected",
            metadata={"source": "scanner"},
        )
        assert hd.decision is GovernanceDecision.REDACTED
        assert hd.disposition is HandlingDisposition.REDACT
        assert hd.redaction_level is RedactionLevel.PARTIAL
        assert hd.reason == "PII detected"
        assert hd.metadata["source"] == "scanner"

    def test_empty_decision_id_rejected(self):
        with pytest.raises(ValueError, match="decision_id"):
            _make_handling_decision(decision_id="")

    def test_empty_data_id_rejected(self):
        with pytest.raises(ValueError, match="data_id"):
            _make_handling_decision(data_id="")

    def test_empty_tenant_id_rejected(self):
        with pytest.raises(ValueError, match="tenant_id"):
            _make_handling_decision(tenant_id="")

    def test_empty_operation_rejected(self):
        with pytest.raises(ValueError, match="operation"):
            _make_handling_decision(operation="")

    def test_whitespace_operation_rejected(self):
        with pytest.raises(ValueError, match="operation"):
            _make_handling_decision(operation="   ")

    def test_invalid_decision_enum_rejected(self):
        with pytest.raises(ValueError, match="decision"):
            _make_handling_decision(decision="denied")  # type: ignore[arg-type]

    def test_invalid_disposition_rejected(self):
        with pytest.raises(ValueError, match="disposition"):
            _make_handling_decision(disposition="deny")  # type: ignore[arg-type]

    def test_invalid_redaction_level_rejected(self):
        with pytest.raises(ValueError, match="redaction_level"):
            _make_handling_decision(redaction_level="none")  # type: ignore[arg-type]

    def test_invalid_decided_at_rejected(self):
        with pytest.raises(ValueError, match="decided_at"):
            _make_handling_decision(decided_at="not-a-date")

    def test_metadata_frozen(self):
        hd = _make_handling_decision(metadata={"k": "v"})
        assert isinstance(hd.metadata, MappingProxyType)

    def test_frozen_immutable(self):
        hd = _make_handling_decision()
        with pytest.raises(AttributeError):
            hd.decision_id = "changed"  # type: ignore[misc]

    def test_to_dict_preserves_enums(self):
        hd = _make_handling_decision()
        d = hd.to_dict()
        assert d["decision"] is GovernanceDecision.DENIED
        assert d["disposition"] is HandlingDisposition.DENY
        assert d["redaction_level"] is RedactionLevel.NONE

    def test_each_governance_decision_variant(self):
        for dec in GovernanceDecision:
            hd = _make_handling_decision(decision=dec)
            assert hd.decision is dec

    def test_fail_closed_default_is_deny(self):
        """Governance default is fail-closed: DENIED + DENY."""
        hd = _make_handling_decision()
        assert hd.decision is GovernanceDecision.DENIED
        assert hd.disposition is HandlingDisposition.DENY


# ===================================================================
# DataViolation
# ===================================================================


class TestDataViolation:
    def test_valid_defaults(self):
        v = _make_data_violation()
        assert v.violation_id == "vio-1"
        assert v.data_id == "dr-1"
        assert v.tenant_id == "t-1"
        assert v.operation == "export"
        assert v.reason == ""
        assert v.classification is DataClassification.INTERNAL
        assert v.detected_at == TS

    def test_all_fields_set(self):
        v = _make_data_violation(
            reason="unauthorized cross-region transfer",
            classification=DataClassification.RESTRICTED,
            metadata={"region": "cn"},
        )
        assert v.reason == "unauthorized cross-region transfer"
        assert v.classification is DataClassification.RESTRICTED
        assert v.metadata["region"] == "cn"

    def test_empty_violation_id_rejected(self):
        with pytest.raises(ValueError, match="violation_id"):
            _make_data_violation(violation_id="")

    def test_empty_data_id_rejected(self):
        with pytest.raises(ValueError, match="data_id"):
            _make_data_violation(data_id="")

    def test_empty_tenant_id_rejected(self):
        with pytest.raises(ValueError, match="tenant_id"):
            _make_data_violation(tenant_id="")

    def test_empty_operation_rejected(self):
        with pytest.raises(ValueError, match="operation"):
            _make_data_violation(operation="")

    def test_invalid_classification_rejected(self):
        with pytest.raises(ValueError, match="classification"):
            _make_data_violation(classification="internal")  # type: ignore[arg-type]

    def test_invalid_detected_at_rejected(self):
        with pytest.raises(ValueError, match="detected_at"):
            _make_data_violation(detected_at="bad")

    def test_metadata_frozen(self):
        v = _make_data_violation(metadata={"a": "b"})
        assert isinstance(v.metadata, MappingProxyType)

    def test_frozen_immutable(self):
        v = _make_data_violation()
        with pytest.raises(AttributeError):
            v.violation_id = "changed"  # type: ignore[misc]

    def test_to_dict_preserves_enums(self):
        v = _make_data_violation()
        d = v.to_dict()
        assert d["classification"] is DataClassification.INTERNAL

    def test_to_dict_metadata_plain_dict(self):
        v = _make_data_violation(metadata={"x": 1})
        d = v.to_dict()
        assert isinstance(d["metadata"], dict)


# ===================================================================
# DataGovernanceSnapshot
# ===================================================================


class TestDataGovernanceSnapshot:
    def test_valid_defaults(self):
        snap = _make_governance_snapshot()
        assert snap.snapshot_id == "snap-1"
        assert snap.scope_ref_id == ""
        assert snap.total_records == 0
        assert snap.total_policies == 0
        assert snap.total_residency_constraints == 0
        assert snap.total_privacy_rules == 0
        assert snap.total_redaction_rules == 0
        assert snap.total_retention_rules == 0
        assert snap.total_decisions == 0
        assert snap.total_violations == 0
        assert snap.captured_at == TS

    def test_all_fields_set(self):
        snap = _make_governance_snapshot(
            scope_ref_id="scope-10",
            total_records=100,
            total_policies=20,
            total_residency_constraints=5,
            total_privacy_rules=8,
            total_redaction_rules=3,
            total_retention_rules=4,
            total_decisions=50,
            total_violations=2,
            metadata={"env": "prod"},
        )
        assert snap.total_records == 100
        assert snap.total_policies == 20
        assert snap.total_residency_constraints == 5
        assert snap.total_privacy_rules == 8
        assert snap.total_redaction_rules == 3
        assert snap.total_retention_rules == 4
        assert snap.total_decisions == 50
        assert snap.total_violations == 2

    def test_empty_snapshot_id_rejected(self):
        with pytest.raises(ValueError, match="snapshot_id"):
            _make_governance_snapshot(snapshot_id="")

    def test_invalid_captured_at_rejected(self):
        with pytest.raises(ValueError, match="captured_at"):
            _make_governance_snapshot(captured_at="nope")

    def test_negative_total_records_rejected(self):
        with pytest.raises(ValueError, match="total_records"):
            _make_governance_snapshot(total_records=-1)

    def test_negative_total_policies_rejected(self):
        with pytest.raises(ValueError, match="total_policies"):
            _make_governance_snapshot(total_policies=-1)

    def test_negative_total_residency_constraints_rejected(self):
        with pytest.raises(ValueError, match="total_residency_constraints"):
            _make_governance_snapshot(total_residency_constraints=-1)

    def test_negative_total_privacy_rules_rejected(self):
        with pytest.raises(ValueError, match="total_privacy_rules"):
            _make_governance_snapshot(total_privacy_rules=-1)

    def test_negative_total_redaction_rules_rejected(self):
        with pytest.raises(ValueError, match="total_redaction_rules"):
            _make_governance_snapshot(total_redaction_rules=-1)

    def test_negative_total_retention_rules_rejected(self):
        with pytest.raises(ValueError, match="total_retention_rules"):
            _make_governance_snapshot(total_retention_rules=-1)

    def test_negative_total_decisions_rejected(self):
        with pytest.raises(ValueError, match="total_decisions"):
            _make_governance_snapshot(total_decisions=-1)

    def test_negative_total_violations_rejected(self):
        with pytest.raises(ValueError, match="total_violations"):
            _make_governance_snapshot(total_violations=-1)

    def test_bool_total_records_rejected(self):
        with pytest.raises(ValueError, match="total_records"):
            _make_governance_snapshot(total_records=True)  # type: ignore[arg-type]

    def test_float_total_records_rejected(self):
        with pytest.raises(ValueError, match="total_records"):
            _make_governance_snapshot(total_records=1.0)  # type: ignore[arg-type]

    def test_metadata_frozen(self):
        snap = _make_governance_snapshot(metadata={"x": 1})
        assert isinstance(snap.metadata, MappingProxyType)

    def test_frozen_immutable(self):
        snap = _make_governance_snapshot()
        with pytest.raises(AttributeError):
            snap.snapshot_id = "changed"  # type: ignore[misc]

    def test_to_dict_metadata_plain_dict(self):
        snap = _make_governance_snapshot(metadata={"a": "b"})
        d = snap.to_dict()
        assert isinstance(d["metadata"], dict)

    def test_zero_counts_accepted(self):
        snap = _make_governance_snapshot(
            total_records=0, total_policies=0, total_violations=0,
        )
        assert snap.total_records == 0
        assert snap.total_policies == 0
        assert snap.total_violations == 0


# ===================================================================
# DataClosureReport
# ===================================================================


class TestDataClosureReport:
    def test_valid_defaults(self):
        rpt = _make_closure_report()
        assert rpt.report_id == "rpt-1"
        assert rpt.tenant_id == "t-1"
        assert rpt.total_records == 0
        assert rpt.total_decisions == 0
        assert rpt.total_violations == 0
        assert rpt.total_redactions == 0
        assert rpt.total_denials == 0
        assert rpt.closed_at == TS

    def test_all_fields_set(self):
        rpt = _make_closure_report(
            total_records=500,
            total_decisions=400,
            total_violations=10,
            total_redactions=30,
            total_denials=20,
            metadata={"auditor": "sys"},
        )
        assert rpt.total_records == 500
        assert rpt.total_decisions == 400
        assert rpt.total_violations == 10
        assert rpt.total_redactions == 30
        assert rpt.total_denials == 20

    def test_empty_report_id_rejected(self):
        with pytest.raises(ValueError, match="report_id"):
            _make_closure_report(report_id="")

    def test_empty_tenant_id_rejected(self):
        with pytest.raises(ValueError, match="tenant_id"):
            _make_closure_report(tenant_id="")

    def test_invalid_closed_at_rejected(self):
        with pytest.raises(ValueError, match="closed_at"):
            _make_closure_report(closed_at="bad")

    def test_negative_total_records_rejected(self):
        with pytest.raises(ValueError, match="total_records"):
            _make_closure_report(total_records=-1)

    def test_negative_total_decisions_rejected(self):
        with pytest.raises(ValueError, match="total_decisions"):
            _make_closure_report(total_decisions=-1)

    def test_negative_total_violations_rejected(self):
        with pytest.raises(ValueError, match="total_violations"):
            _make_closure_report(total_violations=-1)

    def test_negative_total_redactions_rejected(self):
        with pytest.raises(ValueError, match="total_redactions"):
            _make_closure_report(total_redactions=-1)

    def test_negative_total_denials_rejected(self):
        with pytest.raises(ValueError, match="total_denials"):
            _make_closure_report(total_denials=-1)

    def test_bool_total_records_rejected(self):
        with pytest.raises(ValueError, match="total_records"):
            _make_closure_report(total_records=True)  # type: ignore[arg-type]

    def test_float_total_violations_rejected(self):
        with pytest.raises(ValueError, match="total_violations"):
            _make_closure_report(total_violations=2.0)  # type: ignore[arg-type]

    def test_metadata_frozen(self):
        rpt = _make_closure_report(metadata={"k": "v"})
        assert isinstance(rpt.metadata, MappingProxyType)

    def test_frozen_immutable(self):
        rpt = _make_closure_report()
        with pytest.raises(AttributeError):
            rpt.report_id = "changed"  # type: ignore[misc]

    def test_to_dict_metadata_plain_dict(self):
        rpt = _make_closure_report(metadata={"a": 1})
        d = rpt.to_dict()
        assert isinstance(d["metadata"], dict)

    def test_zero_counts_accepted(self):
        rpt = _make_closure_report(
            total_records=0, total_decisions=0, total_violations=0,
            total_redactions=0, total_denials=0,
        )
        assert rpt.total_records == 0


# ===================================================================
# Cross-cutting: to_json round-trip, nested metadata freezing
# ===================================================================


class TestSerialization:
    def test_data_record_to_dict_preserves_enums(self):
        rec = _make_data_record()
        d = rec.to_dict()
        assert isinstance(d, dict)
        assert d["data_id"] == "dr-1"
        assert d["classification"] is DataClassification.INTERNAL

    def test_data_policy_to_dict_preserves_enums(self):
        pol = _make_data_policy()
        d = pol.to_dict()
        assert isinstance(d, dict)
        assert d["policy_id"] == "pol-1"
        assert d["disposition"] is HandlingDisposition.DENY

    def test_handling_decision_to_dict_preserves_enums(self):
        hd = _make_handling_decision()
        d = hd.to_dict()
        assert isinstance(d, dict)
        assert d["decision_id"] == "hd-1"
        assert d["decision"] is GovernanceDecision.DENIED

    def test_violation_to_dict_preserves_enums(self):
        v = _make_data_violation()
        d = v.to_dict()
        assert isinstance(d, dict)
        assert d["violation_id"] == "vio-1"
        assert d["classification"] is DataClassification.INTERNAL

    def test_snapshot_to_dict_returns_dict(self):
        snap = _make_governance_snapshot()
        d = snap.to_dict()
        assert isinstance(d, dict)
        assert d["snapshot_id"] == "snap-1"

    def test_closure_report_to_dict_returns_dict(self):
        rpt = _make_closure_report()
        d = rpt.to_dict()
        assert isinstance(d, dict)
        assert d["report_id"] == "rpt-1"

    def test_nested_metadata_frozen(self):
        rec = _make_data_record(metadata={"nested": {"a": [1, 2, 3]}})
        assert isinstance(rec.metadata["nested"], MappingProxyType)
        assert rec.metadata["nested"]["a"] == (1, 2, 3)

    def test_nested_metadata_thawed_in_to_dict(self):
        rec = _make_data_record(metadata={"nested": {"a": [1, 2]}})
        d = rec.to_dict()
        assert isinstance(d["metadata"]["nested"], dict)
        assert d["metadata"]["nested"]["a"] == [1, 2]


class TestDatetimeVariants:
    def test_z_suffix_accepted(self):
        rec = _make_data_record(created_at="2025-06-01T12:00:00Z")
        assert rec.created_at == "2025-06-01T12:00:00Z"

    def test_offset_accepted(self):
        rec = _make_data_record(created_at="2025-06-01T12:00:00+05:30")
        assert rec.created_at == "2025-06-01T12:00:00+05:30"

    def test_no_timezone_accepted(self):
        rec = _make_data_record(created_at="2025-06-01T12:00:00")
        assert rec.created_at == "2025-06-01T12:00:00"


class TestFreezeBehavior:
    def test_list_in_metadata_becomes_tuple(self):
        rec = _make_data_record(metadata={"tags": ["a", "b"]})
        assert rec.metadata["tags"] == ("a", "b")

    def test_set_in_metadata_becomes_frozenset(self):
        rec = _make_data_record(metadata={"ids": {1, 2, 3}})
        assert isinstance(rec.metadata["ids"], frozenset)
        assert rec.metadata["ids"] == frozenset({1, 2, 3})

    def test_original_dict_not_mutated(self):
        original = {"key": "value"}
        _make_data_record(metadata=original)
        assert isinstance(original, dict)
        assert "key" in original

    def test_residency_constraint_regions_from_list(self):
        rc = _make_residency_constraint(
            allowed_regions=["us", "eu"],
            denied_regions=["cn", "ru"],
        )
        assert isinstance(rc.allowed_regions, tuple)
        assert isinstance(rc.denied_regions, tuple)
        assert len(rc.allowed_regions) == 2
        assert len(rc.denied_regions) == 2

    def test_redaction_rule_field_patterns_from_list(self):
        rule = _make_redaction_rule(field_patterns=["ssn", "dob", "phone"])
        assert isinstance(rule.field_patterns, tuple)
        assert len(rule.field_patterns) == 3


class TestToDictFieldCompleteness:
    """to_dict returns all fields."""

    def test_data_record_all_fields(self):
        rec = _make_data_record()
        d = rec.to_dict()
        assert set(d.keys()) == {
            "data_id", "tenant_id", "classification", "residency",
            "privacy_basis", "domain", "source_id", "created_at", "metadata",
        }

    def test_handling_decision_all_fields(self):
        hd = _make_handling_decision()
        d = hd.to_dict()
        assert "decision_id" in d
        assert "disposition" in d
        assert "redaction_level" in d
