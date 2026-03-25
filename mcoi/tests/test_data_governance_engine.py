"""Purpose: comprehensive tests for the DataGovernanceEngine.
Governance scope: runtime-core data governance tests only.
Dependencies: DataGovernanceEngine, EventSpineEngine, data_governance contracts, invariants.
Invariants:
  - Governance is fail-closed: default decision is DENY.
  - RESTRICTED/SECRET data cannot leave tenant without explicit ALLOW policy.
  - Residency constraints are checked before any transfer.
  - Privacy rules enforce basis requirements.
  - Every mutation emits an event.
  - All returns are immutable.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.data_governance import DataGovernanceEngine
from mcoi_runtime.contracts.data_governance import (
    DataClassification,
    ResidencyRegion,
    HandlingDisposition,
    PrivacyBasis,
    RedactionLevel,
    RetentionDisposition,
    GovernanceDecision,
    DataRecord,
    DataPolicy,
    ResidencyConstraint,
    PrivacyRule,
    RedactionRule,
    RetentionRule,
    HandlingDecision,
    DataViolation,
    DataGovernanceSnapshot,
    DataClosureReport,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_engine() -> DataGovernanceEngine:
    return DataGovernanceEngine(EventSpineEngine())


def _engine_with_record(
    data_id: str = "d-1",
    tenant_id: str = "t-1",
    classification: DataClassification = DataClassification.INTERNAL,
    residency: ResidencyRegion = ResidencyRegion.GLOBAL,
    privacy_basis: PrivacyBasis = PrivacyBasis.LEGITIMATE_INTEREST,
) -> DataGovernanceEngine:
    eng = _make_engine()
    eng.classify_data(
        data_id, tenant_id,
        classification=classification,
        residency=residency,
        privacy_basis=privacy_basis,
    )
    return eng


# ===================================================================
# 1. Constructor
# ===================================================================


class TestConstructor:
    def test_accepts_event_spine(self) -> None:
        eng = DataGovernanceEngine(EventSpineEngine())
        assert eng.record_count == 0

    def test_rejects_none(self) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            DataGovernanceEngine(None)  # type: ignore[arg-type]

    def test_rejects_string(self) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            DataGovernanceEngine("not-an-engine")  # type: ignore[arg-type]

    def test_rejects_other_types(self) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            DataGovernanceEngine({})  # type: ignore[arg-type]


# ===================================================================
# 2. Properties (fresh engine)
# ===================================================================


class TestPropertiesFresh:
    def test_record_count_zero(self) -> None:
        assert _make_engine().record_count == 0

    def test_policy_count_zero(self) -> None:
        assert _make_engine().policy_count == 0

    def test_residency_constraint_count_zero(self) -> None:
        assert _make_engine().residency_constraint_count == 0

    def test_privacy_rule_count_zero(self) -> None:
        assert _make_engine().privacy_rule_count == 0

    def test_redaction_rule_count_zero(self) -> None:
        assert _make_engine().redaction_rule_count == 0

    def test_retention_rule_count_zero(self) -> None:
        assert _make_engine().retention_rule_count == 0

    def test_decision_count_zero(self) -> None:
        assert _make_engine().decision_count == 0

    def test_violation_count_zero(self) -> None:
        assert _make_engine().violation_count == 0


# ===================================================================
# 3. classify_data
# ===================================================================


class TestClassifyData:
    def test_returns_data_record(self) -> None:
        eng = _make_engine()
        rec = eng.classify_data("d-1", "t-1")
        assert isinstance(rec, DataRecord)

    def test_record_fields(self) -> None:
        eng = _make_engine()
        rec = eng.classify_data(
            "d-1", "t-1",
            classification=DataClassification.SENSITIVE,
            residency=ResidencyRegion.EU,
            privacy_basis=PrivacyBasis.CONSENT,
            domain="finance",
            source_id="src-1",
        )
        assert rec.data_id == "d-1"
        assert rec.tenant_id == "t-1"
        assert rec.classification == DataClassification.SENSITIVE
        assert rec.residency == ResidencyRegion.EU
        assert rec.privacy_basis == PrivacyBasis.CONSENT
        assert rec.domain == "finance"
        assert rec.source_id == "src-1"
        assert rec.created_at != ""

    def test_defaults(self) -> None:
        eng = _make_engine()
        rec = eng.classify_data("d-1", "t-1")
        assert rec.classification == DataClassification.INTERNAL
        assert rec.residency == ResidencyRegion.GLOBAL
        assert rec.privacy_basis == PrivacyBasis.LEGITIMATE_INTEREST
        assert rec.domain == ""
        assert rec.source_id == ""

    def test_increments_record_count(self) -> None:
        eng = _make_engine()
        eng.classify_data("d-1", "t-1")
        assert eng.record_count == 1
        eng.classify_data("d-2", "t-1")
        assert eng.record_count == 2

    def test_duplicate_raises(self) -> None:
        eng = _make_engine()
        eng.classify_data("d-1", "t-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate data_id"):
            eng.classify_data("d-1", "t-1")

    def test_classify_with_secret(self) -> None:
        eng = _make_engine()
        rec = eng.classify_data("d-1", "t-1", classification=DataClassification.SECRET)
        assert rec.classification == DataClassification.SECRET

    def test_classify_with_eu_residency(self) -> None:
        eng = _make_engine()
        rec = eng.classify_data("d-1", "t-1", residency=ResidencyRegion.EU)
        assert rec.residency == ResidencyRegion.EU

    def test_classify_with_consent_basis(self) -> None:
        eng = _make_engine()
        rec = eng.classify_data("d-1", "t-1", privacy_basis=PrivacyBasis.CONSENT)
        assert rec.privacy_basis == PrivacyBasis.CONSENT


# ===================================================================
# 4. get_record
# ===================================================================


class TestGetRecord:
    def test_retrieves_existing(self) -> None:
        eng = _make_engine()
        original = eng.classify_data("d-1", "t-1")
        fetched = eng.get_record("d-1")
        assert fetched.data_id == original.data_id

    def test_unknown_raises(self) -> None:
        eng = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown data_id"):
            eng.get_record("no-such")

    def test_frozen(self) -> None:
        eng = _make_engine()
        eng.classify_data("d-1", "t-1")
        rec = eng.get_record("d-1")
        with pytest.raises(AttributeError):
            rec.data_id = "changed"  # type: ignore[misc]


# ===================================================================
# 5. records_for_tenant
# ===================================================================


class TestRecordsForTenant:
    def test_returns_tuple(self) -> None:
        eng = _make_engine()
        assert eng.records_for_tenant("t-1") == ()

    def test_filters_by_tenant(self) -> None:
        eng = _make_engine()
        eng.classify_data("d-1", "t-1")
        eng.classify_data("d-2", "t-2")
        eng.classify_data("d-3", "t-1")
        recs = eng.records_for_tenant("t-1")
        assert len(recs) == 2
        assert all(r.tenant_id == "t-1" for r in recs)

    def test_empty_for_unknown_tenant(self) -> None:
        eng = _make_engine()
        eng.classify_data("d-1", "t-1")
        assert eng.records_for_tenant("t-99") == ()


# ===================================================================
# 6. register_policy
# ===================================================================


class TestRegisterPolicy:
    def test_returns_data_policy(self) -> None:
        eng = _make_engine()
        pol = eng.register_policy("pol-1", "t-1")
        assert isinstance(pol, DataPolicy)

    def test_policy_fields(self) -> None:
        eng = _make_engine()
        pol = eng.register_policy(
            "pol-1", "t-1",
            classification=DataClassification.CONFIDENTIAL,
            disposition=HandlingDisposition.REDACT,
            residency=ResidencyRegion.EU,
            scope_ref_id="scope-1",
            description="test policy",
        )
        assert pol.policy_id == "pol-1"
        assert pol.tenant_id == "t-1"
        assert pol.classification == DataClassification.CONFIDENTIAL
        assert pol.disposition == HandlingDisposition.REDACT
        assert pol.residency == ResidencyRegion.EU
        assert pol.scope_ref_id == "scope-1"
        assert pol.description == "test policy"

    def test_defaults(self) -> None:
        eng = _make_engine()
        pol = eng.register_policy("pol-1", "t-1")
        assert pol.classification == DataClassification.INTERNAL
        assert pol.disposition == HandlingDisposition.DENY
        assert pol.residency == ResidencyRegion.GLOBAL

    def test_increments_policy_count(self) -> None:
        eng = _make_engine()
        eng.register_policy("pol-1", "t-1")
        assert eng.policy_count == 1

    def test_duplicate_raises(self) -> None:
        eng = _make_engine()
        eng.register_policy("pol-1", "t-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate policy_id"):
            eng.register_policy("pol-1", "t-1")

    def test_redact_disposition(self) -> None:
        eng = _make_engine()
        pol = eng.register_policy("pol-r", "t-1", disposition=HandlingDisposition.REDACT)
        assert pol.disposition == HandlingDisposition.REDACT


# ===================================================================
# 7. register_residency_constraint
# ===================================================================


class TestRegisterResidencyConstraint:
    def test_returns_constraint(self) -> None:
        eng = _make_engine()
        c = eng.register_residency_constraint("rc-1", "t-1", allowed_regions=["eu"])
        assert isinstance(c, ResidencyConstraint)

    def test_fields(self) -> None:
        eng = _make_engine()
        c = eng.register_residency_constraint(
            "rc-1", "t-1",
            allowed_regions=["eu", "uk"],
            denied_regions=["us"],
        )
        assert c.constraint_id == "rc-1"
        assert c.tenant_id == "t-1"
        assert "eu" in c.allowed_regions
        assert "us" in c.denied_regions

    def test_defaults_empty_regions(self) -> None:
        eng = _make_engine()
        c = eng.register_residency_constraint("rc-1", "t-1")
        assert c.allowed_regions == ()
        assert c.denied_regions == ()

    def test_increments_count(self) -> None:
        eng = _make_engine()
        eng.register_residency_constraint("rc-1", "t-1")
        assert eng.residency_constraint_count == 1

    def test_duplicate_raises(self) -> None:
        eng = _make_engine()
        eng.register_residency_constraint("rc-1", "t-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate constraint_id"):
            eng.register_residency_constraint("rc-1", "t-1")


# ===================================================================
# 8. register_privacy_rule
# ===================================================================


class TestRegisterPrivacyRule:
    def test_returns_privacy_rule(self) -> None:
        eng = _make_engine()
        r = eng.register_privacy_rule("pr-1", "t-1")
        assert isinstance(r, PrivacyRule)

    def test_fields(self) -> None:
        eng = _make_engine()
        r = eng.register_privacy_rule(
            "pr-1", "t-1",
            classification=DataClassification.SENSITIVE,
            required_basis=PrivacyBasis.CONTRACT,
            scope_ref_id="scope-x",
            description="require contract basis",
        )
        assert r.rule_id == "pr-1"
        assert r.classification == DataClassification.SENSITIVE
        assert r.required_basis == PrivacyBasis.CONTRACT

    def test_defaults(self) -> None:
        eng = _make_engine()
        r = eng.register_privacy_rule("pr-1", "t-1")
        assert r.classification == DataClassification.PII
        assert r.required_basis == PrivacyBasis.CONSENT

    def test_increments_count(self) -> None:
        eng = _make_engine()
        eng.register_privacy_rule("pr-1", "t-1")
        assert eng.privacy_rule_count == 1

    def test_duplicate_raises(self) -> None:
        eng = _make_engine()
        eng.register_privacy_rule("pr-1", "t-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate privacy rule_id"):
            eng.register_privacy_rule("pr-1", "t-1")


# ===================================================================
# 9. register_redaction_rule
# ===================================================================


class TestRegisterRedactionRule:
    def test_returns_redaction_rule(self) -> None:
        eng = _make_engine()
        r = eng.register_redaction_rule("rr-1", "t-1")
        assert isinstance(r, RedactionRule)

    def test_fields(self) -> None:
        eng = _make_engine()
        r = eng.register_redaction_rule(
            "rr-1", "t-1",
            classification=DataClassification.PII,
            redaction_level=RedactionLevel.PARTIAL,
            scope_ref_id="scope-y",
            field_patterns=["email", "phone"],
        )
        assert r.rule_id == "rr-1"
        assert r.classification == DataClassification.PII
        assert r.redaction_level == RedactionLevel.PARTIAL
        assert "email" in r.field_patterns

    def test_defaults(self) -> None:
        eng = _make_engine()
        r = eng.register_redaction_rule("rr-1", "t-1")
        assert r.classification == DataClassification.SENSITIVE
        assert r.redaction_level == RedactionLevel.FULL

    def test_increments_count(self) -> None:
        eng = _make_engine()
        eng.register_redaction_rule("rr-1", "t-1")
        assert eng.redaction_rule_count == 1

    def test_duplicate_raises(self) -> None:
        eng = _make_engine()
        eng.register_redaction_rule("rr-1", "t-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate redaction rule_id"):
            eng.register_redaction_rule("rr-1", "t-1")

    def test_tokenize_redaction_level(self) -> None:
        eng = _make_engine()
        r = eng.register_redaction_rule("rr-tok", "t-1", redaction_level=RedactionLevel.TOKENIZE)
        assert r.redaction_level == RedactionLevel.TOKENIZE


# ===================================================================
# 10. register_retention_rule
# ===================================================================


class TestRegisterRetentionRule:
    def test_returns_retention_rule(self) -> None:
        eng = _make_engine()
        r = eng.register_retention_rule("ret-1", "t-1")
        assert isinstance(r, RetentionRule)

    def test_fields(self) -> None:
        eng = _make_engine()
        r = eng.register_retention_rule(
            "ret-1", "t-1",
            classification=DataClassification.CONFIDENTIAL,
            retention_days=90,
            disposition=RetentionDisposition.ARCHIVE,
            scope_ref_id="scope-z",
        )
        assert r.rule_id == "ret-1"
        assert r.retention_days == 90
        assert r.disposition == RetentionDisposition.ARCHIVE

    def test_defaults(self) -> None:
        eng = _make_engine()
        r = eng.register_retention_rule("ret-1", "t-1")
        assert r.classification == DataClassification.INTERNAL
        assert r.retention_days == 365
        assert r.disposition == RetentionDisposition.DELETE

    def test_increments_count(self) -> None:
        eng = _make_engine()
        eng.register_retention_rule("ret-1", "t-1")
        assert eng.retention_rule_count == 1

    def test_duplicate_raises(self) -> None:
        eng = _make_engine()
        eng.register_retention_rule("ret-1", "t-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate retention rule_id"):
            eng.register_retention_rule("ret-1", "t-1")

    def test_archive_disposition(self) -> None:
        eng = _make_engine()
        r = eng.register_retention_rule("ret-a", "t-1", disposition=RetentionDisposition.ARCHIVE)
        assert r.disposition == RetentionDisposition.ARCHIVE


# ===================================================================
# 11. evaluate_handling - basic
# ===================================================================


class TestEvaluateHandlingBasic:
    def test_returns_handling_decision(self) -> None:
        eng = _engine_with_record()
        dec = eng.evaluate_handling("d-1", "read")
        assert isinstance(dec, HandlingDecision)

    def test_unknown_data_id_raises(self) -> None:
        eng = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown data_id"):
            eng.evaluate_handling("no-such", "read")

    def test_decision_fields_populated(self) -> None:
        eng = _engine_with_record()
        dec = eng.evaluate_handling("d-1", "read")
        assert dec.data_id == "d-1"
        assert dec.tenant_id == "t-1"
        assert dec.operation == "read"
        assert dec.decision_id != ""
        assert dec.decided_at != ""

    def test_increments_decision_count(self) -> None:
        eng = _engine_with_record()
        eng.evaluate_handling("d-1", "read")
        assert eng.decision_count == 1

    def test_low_classification_no_policy_allowed(self) -> None:
        eng = _engine_with_record(classification=DataClassification.PUBLIC)
        dec = eng.evaluate_handling("d-1", "read")
        assert dec.decision == GovernanceDecision.ALLOWED

    def test_internal_no_policy_allowed(self) -> None:
        eng = _engine_with_record(classification=DataClassification.INTERNAL)
        dec = eng.evaluate_handling("d-1", "read")
        assert dec.decision == GovernanceDecision.ALLOWED

    def test_pii_no_policy_allowed(self) -> None:
        # PII is below RESTRICTED in _CLASSIFICATION_ORDER
        eng = _engine_with_record(classification=DataClassification.PII)
        dec = eng.evaluate_handling("d-1", "read")
        assert dec.decision == GovernanceDecision.ALLOWED


# ===================================================================
# 12. evaluate_handling - fail-closed for RESTRICTED/SECRET
# ===================================================================


class TestFailClosed:
    def test_restricted_no_policy_denied(self) -> None:
        eng = _engine_with_record(classification=DataClassification.RESTRICTED)
        dec = eng.evaluate_handling("d-1", "read")
        assert dec.decision == GovernanceDecision.DENIED
        assert "no policy" in dec.reason

    def test_secret_no_policy_denied(self) -> None:
        eng = _engine_with_record(classification=DataClassification.SECRET)
        dec = eng.evaluate_handling("d-1", "write")
        assert dec.decision == GovernanceDecision.DENIED
        assert "no policy" in dec.reason

    def test_restricted_with_allow_policy_allowed(self) -> None:
        eng = _engine_with_record(classification=DataClassification.RESTRICTED)
        eng.register_policy(
            "pol-1", "t-1",
            classification=DataClassification.RESTRICTED,
            disposition=HandlingDisposition.ALLOW,
        )
        dec = eng.evaluate_handling("d-1", "read")
        assert dec.decision == GovernanceDecision.ALLOWED

    def test_secret_with_allow_policy_allowed(self) -> None:
        eng = _engine_with_record(classification=DataClassification.SECRET)
        eng.register_policy(
            "pol-1", "t-1",
            classification=DataClassification.SECRET,
            disposition=HandlingDisposition.ALLOW,
        )
        dec = eng.evaluate_handling("d-1", "read")
        assert dec.decision == GovernanceDecision.ALLOWED



# ===================================================================
# 13. evaluate_handling - policy dispositions
# ===================================================================


class TestPolicyDispositions:
    def test_deny_policy(self) -> None:
        eng = _engine_with_record()
        eng.register_policy("pol-1", "t-1", disposition=HandlingDisposition.DENY)
        dec = eng.evaluate_handling("d-1", "op")
        assert dec.decision == GovernanceDecision.DENIED
        assert dec.disposition == HandlingDisposition.DENY

    def test_allow_policy(self) -> None:
        eng = _engine_with_record()
        eng.register_policy("pol-1", "t-1", disposition=HandlingDisposition.ALLOW)
        dec = eng.evaluate_handling("d-1", "op")
        assert dec.decision == GovernanceDecision.ALLOWED
        assert dec.disposition == HandlingDisposition.ALLOW

    def test_redact_policy(self) -> None:
        eng = _engine_with_record()
        eng.register_policy("pol-1", "t-1", disposition=HandlingDisposition.REDACT)
        dec = eng.evaluate_handling("d-1", "op")
        assert dec.decision == GovernanceDecision.REDACTED
        assert dec.disposition == HandlingDisposition.REDACT

    def test_redact_policy_defaults_full_when_no_redaction_rule(self) -> None:
        eng = _engine_with_record()
        eng.register_policy("pol-1", "t-1", disposition=HandlingDisposition.REDACT)
        dec = eng.evaluate_handling("d-1", "op")
        assert dec.redaction_level == RedactionLevel.FULL

    def test_redact_policy_uses_redaction_rule_level(self) -> None:
        eng = _engine_with_record(classification=DataClassification.SENSITIVE)
        eng.register_policy(
            "pol-1", "t-1",
            classification=DataClassification.SENSITIVE,
            disposition=HandlingDisposition.REDACT,
        )
        eng.register_redaction_rule(
            "rr-1", "t-1",
            classification=DataClassification.SENSITIVE,
            redaction_level=RedactionLevel.PARTIAL,
        )
        dec = eng.evaluate_handling("d-1", "op")
        assert dec.redaction_level == RedactionLevel.PARTIAL

    def test_audit_only_policy(self) -> None:
        eng = _engine_with_record()
        eng.register_policy("pol-1", "t-1", disposition=HandlingDisposition.AUDIT_ONLY)
        dec = eng.evaluate_handling("d-1", "op")
        assert dec.decision == GovernanceDecision.ALLOWED
        assert dec.disposition == HandlingDisposition.AUDIT_ONLY

    def test_encrypt_policy(self) -> None:
        eng = _engine_with_record()
        eng.register_policy("pol-1", "t-1", disposition=HandlingDisposition.ENCRYPT)
        dec = eng.evaluate_handling("d-1", "op")
        assert dec.decision == GovernanceDecision.ALLOWED
        assert dec.disposition == HandlingDisposition.ENCRYPT


# ===================================================================
# 14. evaluate_handling - policy matching by classification
# ===================================================================


class TestPolicyMatching:
    def test_policy_at_lower_classification_matches(self) -> None:
        eng = _engine_with_record(classification=DataClassification.SENSITIVE)
        eng.register_policy(
            "pol-1", "t-1",
            classification=DataClassification.INTERNAL,
            disposition=HandlingDisposition.ALLOW,
        )
        dec = eng.evaluate_handling("d-1", "op")
        assert dec.decision == GovernanceDecision.ALLOWED

    def test_policy_at_higher_classification_does_not_match(self) -> None:
        eng = _engine_with_record(classification=DataClassification.PUBLIC)
        eng.register_policy(
            "pol-1", "t-1",
            classification=DataClassification.SENSITIVE,
            disposition=HandlingDisposition.DENY,
        )
        # No matching policy, PUBLIC is low → ALLOWED
        dec = eng.evaluate_handling("d-1", "op")
        assert dec.decision == GovernanceDecision.ALLOWED

    def test_highest_matching_policy_selected(self) -> None:
        eng = _engine_with_record(classification=DataClassification.SECRET)
        eng.register_policy(
            "pol-low", "t-1",
            classification=DataClassification.INTERNAL,
            disposition=HandlingDisposition.ALLOW,
        )
        eng.register_policy(
            "pol-high", "t-1",
            classification=DataClassification.RESTRICTED,
            disposition=HandlingDisposition.DENY,
        )
        dec = eng.evaluate_handling("d-1", "op")
        # The RESTRICTED policy is the highest match → DENY
        assert dec.decision == GovernanceDecision.DENIED

    def test_policy_other_tenant_not_matched(self) -> None:
        eng = _engine_with_record()
        eng.register_policy(
            "pol-1", "t-other",
            classification=DataClassification.INTERNAL,
            disposition=HandlingDisposition.DENY,
        )
        dec = eng.evaluate_handling("d-1", "op")
        assert dec.decision == GovernanceDecision.ALLOWED

    def test_exact_classification_match(self) -> None:
        eng = _engine_with_record(classification=DataClassification.CONFIDENTIAL)
        eng.register_policy(
            "pol-1", "t-1",
            classification=DataClassification.CONFIDENTIAL,
            disposition=HandlingDisposition.ENCRYPT,
        )
        dec = eng.evaluate_handling("d-1", "op")
        assert dec.disposition == HandlingDisposition.ENCRYPT


# ===================================================================
# 15. evaluate_handling - privacy rules
# ===================================================================


class TestPrivacyRules:
    def test_privacy_basis_mismatch_denies(self) -> None:
        eng = _engine_with_record(
            classification=DataClassification.PII,
            privacy_basis=PrivacyBasis.LEGITIMATE_INTEREST,
        )
        eng.register_privacy_rule(
            "pr-1", "t-1",
            classification=DataClassification.PII,
            required_basis=PrivacyBasis.CONSENT,
        )
        dec = eng.evaluate_handling("d-1", "op")
        assert dec.decision == GovernanceDecision.DENIED
        assert "privacy basis mismatch" in dec.reason

    def test_privacy_basis_match_passes(self) -> None:
        eng = _engine_with_record(
            classification=DataClassification.PII,
            privacy_basis=PrivacyBasis.CONSENT,
        )
        eng.register_privacy_rule(
            "pr-1", "t-1",
            classification=DataClassification.PII,
            required_basis=PrivacyBasis.CONSENT,
        )
        dec = eng.evaluate_handling("d-1", "op")
        # No policy, PII is below RESTRICTED → ALLOWED
        assert dec.decision == GovernanceDecision.ALLOWED

    def test_privacy_rule_lower_classification_applies(self) -> None:
        # Rule at INTERNAL, data at PII → rule classification <= data classification
        eng = _engine_with_record(
            classification=DataClassification.PII,
            privacy_basis=PrivacyBasis.LEGITIMATE_INTEREST,
        )
        eng.register_privacy_rule(
            "pr-1", "t-1",
            classification=DataClassification.INTERNAL,
            required_basis=PrivacyBasis.CONSENT,
        )
        dec = eng.evaluate_handling("d-1", "op")
        assert dec.decision == GovernanceDecision.DENIED

    def test_privacy_rule_higher_classification_skipped(self) -> None:
        # Rule at SECRET, data at INTERNAL → rule classification > data → skipped
        eng = _engine_with_record(
            classification=DataClassification.INTERNAL,
            privacy_basis=PrivacyBasis.LEGITIMATE_INTEREST,
        )
        eng.register_privacy_rule(
            "pr-1", "t-1",
            classification=DataClassification.SECRET,
            required_basis=PrivacyBasis.CONSENT,
        )
        dec = eng.evaluate_handling("d-1", "op")
        assert dec.decision == GovernanceDecision.ALLOWED

    def test_privacy_rule_other_tenant_ignored(self) -> None:
        eng = _engine_with_record(
            classification=DataClassification.PII,
            privacy_basis=PrivacyBasis.LEGITIMATE_INTEREST,
        )
        eng.register_privacy_rule(
            "pr-1", "t-other",
            classification=DataClassification.PII,
            required_basis=PrivacyBasis.CONSENT,
        )
        dec = eng.evaluate_handling("d-1", "op")
        assert dec.decision == GovernanceDecision.ALLOWED

    def test_privacy_checked_before_residency(self) -> None:
        # Both privacy and residency would deny; privacy wins (checked first)
        eng = _engine_with_record(
            classification=DataClassification.PII,
            privacy_basis=PrivacyBasis.LEGITIMATE_INTEREST,
            residency=ResidencyRegion.US,
        )
        eng.register_privacy_rule("pr-1", "t-1", required_basis=PrivacyBasis.CONSENT)
        eng.register_residency_constraint("rc-1", "t-1", denied_regions=["us"])
        dec = eng.evaluate_handling("d-1", "op")
        assert dec.decision == GovernanceDecision.DENIED
        assert "privacy" in dec.reason

    def test_privacy_checked_before_policy(self) -> None:
        eng = _engine_with_record(
            classification=DataClassification.PII,
            privacy_basis=PrivacyBasis.LEGITIMATE_INTEREST,
        )
        eng.register_privacy_rule("pr-1", "t-1", required_basis=PrivacyBasis.CONSENT)
        eng.register_policy(
            "pol-1", "t-1",
            classification=DataClassification.PII,
            disposition=HandlingDisposition.ALLOW,
        )
        dec = eng.evaluate_handling("d-1", "op")
        assert dec.decision == GovernanceDecision.DENIED
        assert "privacy" in dec.reason


# ===================================================================
# 16. evaluate_handling - residency constraints
# ===================================================================


class TestResidencyConstraints:
    def test_denied_region_blocks(self) -> None:
        eng = _engine_with_record(residency=ResidencyRegion.US)
        eng.register_residency_constraint("rc-1", "t-1", denied_regions=["us"])
        dec = eng.evaluate_handling("d-1", "op")
        assert dec.decision == GovernanceDecision.DENIED
        assert "residency" in dec.reason

    def test_allowed_region_passes(self) -> None:
        eng = _engine_with_record(residency=ResidencyRegion.EU)
        eng.register_residency_constraint("rc-1", "t-1", allowed_regions=["eu"])
        dec = eng.evaluate_handling("d-1", "op")
        assert dec.decision == GovernanceDecision.ALLOWED

    def test_not_in_allowed_region_blocks(self) -> None:
        eng = _engine_with_record(residency=ResidencyRegion.US)
        eng.register_residency_constraint("rc-1", "t-1", allowed_regions=["eu"])
        dec = eng.evaluate_handling("d-1", "op")
        assert dec.decision == GovernanceDecision.DENIED

    def test_target_region_overrides_data_residency(self) -> None:
        eng = _engine_with_record(residency=ResidencyRegion.EU)
        eng.register_residency_constraint("rc-1", "t-1", denied_regions=["us"])
        # Data is EU, but target_region is US → denied
        dec = eng.evaluate_handling("d-1", "transfer", target_region=ResidencyRegion.US)
        assert dec.decision == GovernanceDecision.DENIED

    def test_no_constraints_allows(self) -> None:
        eng = _engine_with_record(residency=ResidencyRegion.US)
        dec = eng.evaluate_handling("d-1", "op")
        assert dec.decision == GovernanceDecision.ALLOWED

    def test_global_region_in_allowed(self) -> None:
        eng = _engine_with_record(residency=ResidencyRegion.GLOBAL)
        eng.register_residency_constraint("rc-1", "t-1", allowed_regions=["global"])
        dec = eng.evaluate_handling("d-1", "op")
        assert dec.decision == GovernanceDecision.ALLOWED

    def test_constraint_other_tenant_ignored(self) -> None:
        eng = _engine_with_record(residency=ResidencyRegion.US)
        eng.register_residency_constraint("rc-1", "t-other", denied_regions=["us"])
        dec = eng.evaluate_handling("d-1", "op")
        assert dec.decision == GovernanceDecision.ALLOWED

    def test_residency_checked_before_fail_closed(self) -> None:
        # RESTRICTED data + residency violation → residency denial (checked before fail-closed)
        eng = _engine_with_record(
            classification=DataClassification.RESTRICTED,
            residency=ResidencyRegion.US,
        )
        eng.register_residency_constraint("rc-1", "t-1", denied_regions=["us"])
        dec = eng.evaluate_handling("d-1", "op")
        assert dec.decision == GovernanceDecision.DENIED
        assert "residency" in dec.reason

    def test_multiple_constraints_all_must_pass(self) -> None:
        eng = _engine_with_record(residency=ResidencyRegion.EU)
        eng.register_residency_constraint("rc-1", "t-1", allowed_regions=["eu", "uk"])
        eng.register_residency_constraint("rc-2", "t-1", denied_regions=["eu"])
        dec = eng.evaluate_handling("d-1", "op")
        assert dec.decision == GovernanceDecision.DENIED


# ===================================================================
# 17. evaluate_handling - redaction rules (no policy)
# ===================================================================


class TestRedactionNoPolicy:
    def test_redaction_rule_applies_without_policy(self) -> None:
        eng = _engine_with_record(classification=DataClassification.SENSITIVE)
        eng.register_redaction_rule(
            "rr-1", "t-1",
            classification=DataClassification.SENSITIVE,
            redaction_level=RedactionLevel.PARTIAL,
        )
        dec = eng.evaluate_handling("d-1", "op")
        assert dec.decision == GovernanceDecision.REDACTED
        assert dec.redaction_level == RedactionLevel.PARTIAL

    def test_no_redaction_rule_no_policy_allowed(self) -> None:
        eng = _engine_with_record(classification=DataClassification.INTERNAL)
        dec = eng.evaluate_handling("d-1", "op")
        assert dec.decision == GovernanceDecision.ALLOWED
        assert dec.redaction_level == RedactionLevel.NONE

    def test_redaction_lower_classification_applies(self) -> None:
        eng = _engine_with_record(classification=DataClassification.PII)
        eng.register_redaction_rule(
            "rr-1", "t-1",
            classification=DataClassification.INTERNAL,
            redaction_level=RedactionLevel.HASH,
        )
        dec = eng.evaluate_handling("d-1", "op")
        assert dec.decision == GovernanceDecision.REDACTED
        assert dec.redaction_level == RedactionLevel.HASH

    def test_redaction_higher_classification_does_not_apply(self) -> None:
        eng = _engine_with_record(classification=DataClassification.PUBLIC)
        eng.register_redaction_rule(
            "rr-1", "t-1",
            classification=DataClassification.SENSITIVE,
            redaction_level=RedactionLevel.FULL,
        )
        dec = eng.evaluate_handling("d-1", "op")
        assert dec.decision == GovernanceDecision.ALLOWED
        assert dec.redaction_level == RedactionLevel.NONE

    def test_highest_redaction_level_wins(self) -> None:
        eng = _engine_with_record(classification=DataClassification.PII)
        eng.register_redaction_rule(
            "rr-1", "t-1",
            classification=DataClassification.INTERNAL,
            redaction_level=RedactionLevel.PARTIAL,
        )
        eng.register_redaction_rule(
            "rr-2", "t-1",
            classification=DataClassification.SENSITIVE,
            redaction_level=RedactionLevel.FULL,
        )
        dec = eng.evaluate_handling("d-1", "op")
        assert dec.redaction_level == RedactionLevel.FULL

    def test_redaction_other_tenant_ignored(self) -> None:
        eng = _engine_with_record(classification=DataClassification.SENSITIVE)
        eng.register_redaction_rule(
            "rr-1", "t-other",
            classification=DataClassification.SENSITIVE,
            redaction_level=RedactionLevel.FULL,
        )
        dec = eng.evaluate_handling("d-1", "op")
        assert dec.decision == GovernanceDecision.ALLOWED


# ===================================================================
# 18. evaluate_connector_transfer
# ===================================================================


class TestEvaluateConnectorTransfer:
    def test_returns_handling_decision(self) -> None:
        eng = _engine_with_record()
        dec = eng.evaluate_connector_transfer("d-1", ResidencyRegion.EU)
        assert isinstance(dec, HandlingDecision)

    def test_uses_connector_region(self) -> None:
        eng = _engine_with_record()
        eng.register_residency_constraint("rc-1", "t-1", denied_regions=["eu"])
        dec = eng.evaluate_connector_transfer("d-1", ResidencyRegion.EU)
        assert dec.decision == GovernanceDecision.DENIED

    def test_operation_is_connector_transfer(self) -> None:
        eng = _engine_with_record()
        dec = eng.evaluate_connector_transfer("d-1", ResidencyRegion.US)
        assert dec.operation == "connector_transfer"

    def test_allowed_region_passes(self) -> None:
        eng = _engine_with_record()
        eng.register_residency_constraint("rc-1", "t-1", allowed_regions=["us", "eu"])
        dec = eng.evaluate_connector_transfer("d-1", ResidencyRegion.US)
        assert dec.decision == GovernanceDecision.ALLOWED


# ===================================================================
# 19. evaluate_memory_storage
# ===================================================================


class TestEvaluateMemoryStorage:
    def test_returns_handling_decision(self) -> None:
        eng = _engine_with_record()
        dec = eng.evaluate_memory_storage("d-1")
        assert isinstance(dec, HandlingDecision)

    def test_operation_is_memory_storage(self) -> None:
        eng = _engine_with_record()
        dec = eng.evaluate_memory_storage("d-1")
        assert dec.operation == "memory_storage"

    def test_restricted_no_policy_denied(self) -> None:
        eng = _engine_with_record(classification=DataClassification.RESTRICTED)
        dec = eng.evaluate_memory_storage("d-1")
        assert dec.decision == GovernanceDecision.DENIED

    def test_internal_allowed(self) -> None:
        eng = _engine_with_record(classification=DataClassification.INTERNAL)
        dec = eng.evaluate_memory_storage("d-1")
        assert dec.decision == GovernanceDecision.ALLOWED


# ===================================================================
# 20. evaluate_artifact_storage
# ===================================================================


class TestEvaluateArtifactStorage:
    def test_returns_handling_decision(self) -> None:
        eng = _engine_with_record()
        dec = eng.evaluate_artifact_storage("d-1")
        assert isinstance(dec, HandlingDecision)

    def test_operation_is_artifact_storage(self) -> None:
        eng = _engine_with_record()
        dec = eng.evaluate_artifact_storage("d-1")
        assert dec.operation == "artifact_storage"

    def test_secret_no_policy_denied(self) -> None:
        eng = _engine_with_record(classification=DataClassification.SECRET)
        dec = eng.evaluate_artifact_storage("d-1")
        assert dec.decision == GovernanceDecision.DENIED

    def test_public_allowed(self) -> None:
        eng = _engine_with_record(classification=DataClassification.PUBLIC)
        dec = eng.evaluate_artifact_storage("d-1")
        assert dec.decision == GovernanceDecision.ALLOWED


# ===================================================================
# 21. detect_violations
# ===================================================================


class TestDetectViolations:
    def test_empty_when_no_decisions(self) -> None:
        eng = _make_engine()
        assert eng.detect_violations() == ()

    def test_empty_when_only_allowed(self) -> None:
        eng = _engine_with_record(classification=DataClassification.PUBLIC)
        eng.evaluate_handling("d-1", "read")
        viols = eng.detect_violations()
        assert viols == ()

    def test_finds_denied_decisions(self) -> None:
        eng = _engine_with_record(classification=DataClassification.RESTRICTED)
        eng.evaluate_handling("d-1", "read")
        viols = eng.detect_violations()
        assert len(viols) == 1
        assert isinstance(viols[0], DataViolation)

    def test_violation_fields(self) -> None:
        eng = _engine_with_record(classification=DataClassification.RESTRICTED)
        eng.evaluate_handling("d-1", "read")
        viols = eng.detect_violations()
        v = viols[0]
        assert v.data_id == "d-1"
        assert v.tenant_id == "t-1"
        assert v.operation == "read"
        assert v.classification == DataClassification.RESTRICTED
        assert v.detected_at != ""
        assert v.violation_id != ""

    def test_increments_violation_count(self) -> None:
        eng = _engine_with_record(classification=DataClassification.RESTRICTED)
        eng.evaluate_handling("d-1", "read")
        eng.detect_violations()
        assert eng.violation_count == 1

    def test_deduplication(self) -> None:
        eng = _engine_with_record(classification=DataClassification.RESTRICTED)
        eng.evaluate_handling("d-1", "read")
        first = eng.detect_violations()
        second = eng.detect_violations()
        assert len(first) == 1
        assert len(second) == 0
        assert eng.violation_count == 1

    def test_multiple_denied_decisions(self) -> None:
        eng = _engine_with_record(classification=DataClassification.RESTRICTED)
        eng.classify_data("d-2", "t-1", classification=DataClassification.SECRET)
        eng.evaluate_handling("d-1", "op1")
        eng.evaluate_handling("d-2", "op2")
        viols = eng.detect_violations()
        assert len(viols) == 2

    def test_redacted_not_a_violation(self) -> None:
        eng = _engine_with_record(classification=DataClassification.SENSITIVE)
        eng.register_redaction_rule("rr-1", "t-1", redaction_level=RedactionLevel.FULL)
        eng.evaluate_handling("d-1", "op")
        viols = eng.detect_violations()
        assert len(viols) == 0


# ===================================================================
# 22. violations_for_tenant
# ===================================================================


class TestViolationsForTenant:
    def test_empty_initially(self) -> None:
        eng = _make_engine()
        assert eng.violations_for_tenant("t-1") == ()

    def test_filters_by_tenant(self) -> None:
        eng = _make_engine()
        eng.classify_data("d-1", "t-1", classification=DataClassification.RESTRICTED)
        eng.classify_data("d-2", "t-2", classification=DataClassification.RESTRICTED)
        eng.evaluate_handling("d-1", "op")
        eng.evaluate_handling("d-2", "op")
        eng.detect_violations()
        viols_t1 = eng.violations_for_tenant("t-1")
        viols_t2 = eng.violations_for_tenant("t-2")
        assert len(viols_t1) == 1
        assert len(viols_t2) == 1
        assert viols_t1[0].tenant_id == "t-1"
        assert viols_t2[0].tenant_id == "t-2"



# ===================================================================
# 23. governance_snapshot
# ===================================================================


class TestGovernanceSnapshot:
    def test_returns_snapshot(self) -> None:
        eng = _make_engine()
        snap = eng.governance_snapshot("snap-1")
        assert isinstance(snap, DataGovernanceSnapshot)

    def test_snapshot_fields_empty_engine(self) -> None:
        eng = _make_engine()
        snap = eng.governance_snapshot("snap-1")
        assert snap.snapshot_id == "snap-1"
        assert snap.total_records == 0
        assert snap.total_policies == 0
        assert snap.total_residency_constraints == 0
        assert snap.total_privacy_rules == 0
        assert snap.total_redaction_rules == 0
        assert snap.total_retention_rules == 0
        assert snap.total_decisions == 0
        assert snap.total_violations == 0
        assert snap.captured_at != ""

    def test_snapshot_reflects_current_state(self) -> None:
        eng = _make_engine()
        eng.classify_data("d-1", "t-1", classification=DataClassification.RESTRICTED)
        eng.register_policy("pol-1", "t-1", disposition=HandlingDisposition.DENY)
        eng.register_residency_constraint("rc-1", "t-1")
        eng.register_privacy_rule("pr-1", "t-1")
        eng.register_redaction_rule("rr-1", "t-1")
        eng.register_retention_rule("ret-1", "t-1")
        eng.evaluate_handling("d-1", "op")
        eng.detect_violations()
        snap = eng.governance_snapshot("snap-1")
        assert snap.total_records == 1
        assert snap.total_policies == 1
        assert snap.total_residency_constraints == 1
        assert snap.total_privacy_rules == 1
        assert snap.total_redaction_rules == 1
        assert snap.total_retention_rules == 1
        assert snap.total_decisions == 1
        assert snap.total_violations == 1

    def test_scope_ref_id(self) -> None:
        eng = _make_engine()
        snap = eng.governance_snapshot("snap-1", scope_ref_id="scope-abc")
        assert snap.scope_ref_id == "scope-abc"

    def test_duplicate_snapshot_id_raises(self) -> None:
        eng = _make_engine()
        eng.governance_snapshot("snap-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate snapshot_id"):
            eng.governance_snapshot("snap-1")

    def test_frozen(self) -> None:
        eng = _make_engine()
        snap = eng.governance_snapshot("snap-1")
        with pytest.raises(AttributeError):
            snap.snapshot_id = "changed"  # type: ignore[misc]


# ===================================================================
# 24. state_hash
# ===================================================================


class TestStateHash:
    def test_returns_16_char_hex(self) -> None:
        eng = _make_engine()
        h = eng.state_hash()
        assert isinstance(h, str)
        assert len(h) == 64
        int(h, 16)  # valid hex

    def test_deterministic(self) -> None:
        eng = _make_engine()
        assert eng.state_hash() == eng.state_hash()

    def test_changes_after_classify(self) -> None:
        eng = _make_engine()
        h1 = eng.state_hash()
        eng.classify_data("d-1", "t-1")
        h2 = eng.state_hash()
        assert h1 != h2

    def test_changes_after_policy(self) -> None:
        eng = _make_engine()
        h1 = eng.state_hash()
        eng.register_policy("pol-1", "t-1")
        assert eng.state_hash() != h1

    def test_changes_after_decision(self) -> None:
        eng = _engine_with_record()
        h1 = eng.state_hash()
        eng.evaluate_handling("d-1", "op")
        assert eng.state_hash() != h1

    def test_changes_after_violation(self) -> None:
        eng = _engine_with_record(classification=DataClassification.RESTRICTED)
        eng.evaluate_handling("d-1", "op")
        h1 = eng.state_hash()
        eng.detect_violations()
        assert eng.state_hash() != h1


# ===================================================================
# 25. Classification ordering
# ===================================================================


class TestClassificationOrdering:
    """Verify the ordering: PUBLIC < INTERNAL < CONFIDENTIAL < SENSITIVE < PII < RESTRICTED < SECRET."""

    def test_public_is_lowest(self) -> None:
        eng = _engine_with_record(classification=DataClassification.PUBLIC)
        eng.register_policy(
            "pol-1", "t-1",
            classification=DataClassification.PUBLIC,
            disposition=HandlingDisposition.DENY,
        )
        dec = eng.evaluate_handling("d-1", "op")
        assert dec.decision == GovernanceDecision.DENIED

    def test_pii_below_restricted(self) -> None:
        # PII data with RESTRICTED policy should not match (RESTRICTED > PII)
        eng = _engine_with_record(classification=DataClassification.PII)
        eng.register_policy(
            "pol-1", "t-1",
            classification=DataClassification.RESTRICTED,
            disposition=HandlingDisposition.DENY,
        )
        dec = eng.evaluate_handling("d-1", "op")
        # RESTRICTED policy doesn't match PII data → no policy, PII allowed
        assert dec.decision == GovernanceDecision.ALLOWED

    def test_secret_is_highest(self) -> None:
        eng = _engine_with_record(classification=DataClassification.SECRET)
        eng.register_policy(
            "pol-1", "t-1",
            classification=DataClassification.SECRET,
            disposition=HandlingDisposition.DENY,
        )
        dec = eng.evaluate_handling("d-1", "op")
        assert dec.decision == GovernanceDecision.DENIED

    def test_sensitive_below_restricted_allowed(self) -> None:
        eng = _engine_with_record(classification=DataClassification.SENSITIVE)
        dec = eng.evaluate_handling("d-1", "op")
        assert dec.decision == GovernanceDecision.ALLOWED

    def test_restricted_above_pii_denied(self) -> None:
        eng = _engine_with_record(classification=DataClassification.RESTRICTED)
        dec = eng.evaluate_handling("d-1", "op")
        assert dec.decision == GovernanceDecision.DENIED


# ===================================================================
# 26. Event emission
# ===================================================================


class TestEventEmission:
    def test_classify_emits_event(self) -> None:
        es = EventSpineEngine()
        eng = DataGovernanceEngine(es)
        initial = es.event_count
        eng.classify_data("d-1", "t-1")
        assert es.event_count > initial

    def test_policy_registration_emits_event(self) -> None:
        es = EventSpineEngine()
        eng = DataGovernanceEngine(es)
        initial = es.event_count
        eng.register_policy("pol-1", "t-1")
        assert es.event_count > initial

    def test_evaluate_handling_emits_event(self) -> None:
        es = EventSpineEngine()
        eng = DataGovernanceEngine(es)
        eng.classify_data("d-1", "t-1")
        count_after_classify = es.event_count
        eng.evaluate_handling("d-1", "op")
        assert es.event_count > count_after_classify

    def test_detect_violations_emits_event_when_found(self) -> None:
        es = EventSpineEngine()
        eng = DataGovernanceEngine(es)
        eng.classify_data("d-1", "t-1", classification=DataClassification.RESTRICTED)
        eng.evaluate_handling("d-1", "op")
        count_before = es.event_count
        eng.detect_violations()
        assert es.event_count > count_before

    def test_snapshot_emits_event(self) -> None:
        es = EventSpineEngine()
        eng = DataGovernanceEngine(es)
        count_before = es.event_count
        eng.governance_snapshot("snap-1")
        assert es.event_count > count_before

    def test_rule_registrations_emit_events(self) -> None:
        es = EventSpineEngine()
        eng = DataGovernanceEngine(es)
        c0 = es.event_count
        eng.register_residency_constraint("rc-1", "t-1")
        eng.register_privacy_rule("pr-1", "t-1")
        eng.register_redaction_rule("rr-1", "t-1")
        eng.register_retention_rule("ret-1", "t-1")
        assert es.event_count == c0 + 4


# ===================================================================
# 27. Immutability
# ===================================================================


class TestImmutability:
    def test_data_record_frozen(self) -> None:
        eng = _make_engine()
        rec = eng.classify_data("d-1", "t-1")
        with pytest.raises(AttributeError):
            rec.classification = DataClassification.SECRET  # type: ignore[misc]

    def test_policy_frozen(self) -> None:
        eng = _make_engine()
        pol = eng.register_policy("pol-1", "t-1")
        with pytest.raises(AttributeError):
            pol.disposition = HandlingDisposition.ALLOW  # type: ignore[misc]

    def test_handling_decision_frozen(self) -> None:
        eng = _engine_with_record()
        dec = eng.evaluate_handling("d-1", "op")
        with pytest.raises(AttributeError):
            dec.decision = GovernanceDecision.ALLOWED  # type: ignore[misc]

    def test_violation_frozen(self) -> None:
        eng = _engine_with_record(classification=DataClassification.RESTRICTED)
        eng.evaluate_handling("d-1", "op")
        viols = eng.detect_violations()
        with pytest.raises(AttributeError):
            viols[0].reason = "changed"  # type: ignore[misc]



# ===================================================================
# GOLDEN SCENARIOS
# ===================================================================


class TestGoldenScenario1RestrictedArtifactDeniedForConnector:
    """Restricted artifact denied for external connector transfer.
    Setup: Classify data as RESTRICTED, no ALLOW policy.
    Expected: connector transfer → DENIED.
    """

    def test_restricted_artifact_denied_connector(self) -> None:
        eng = _make_engine()
        eng.classify_data(
            "artifact-001", "tenant-acme",
            classification=DataClassification.RESTRICTED,
            residency=ResidencyRegion.US,
        )
        dec = eng.evaluate_connector_transfer("artifact-001", ResidencyRegion.EU)
        assert dec.decision == GovernanceDecision.DENIED
        assert dec.disposition == HandlingDisposition.DENY
        assert dec.data_id == "artifact-001"
        assert dec.tenant_id == "tenant-acme"
        assert dec.operation == "connector_transfer"

    def test_restricted_artifact_allowed_with_policy(self) -> None:
        eng = _make_engine()
        eng.classify_data(
            "artifact-001", "tenant-acme",
            classification=DataClassification.RESTRICTED,
        )
        eng.register_policy(
            "pol-allow", "tenant-acme",
            classification=DataClassification.RESTRICTED,
            disposition=HandlingDisposition.ALLOW,
        )
        dec = eng.evaluate_connector_transfer("artifact-001", ResidencyRegion.EU)
        assert dec.decision == GovernanceDecision.ALLOWED


class TestGoldenScenario2CommunicationPayloadRedacted:
    """Communication payload redacted before send.
    Setup: REDACT policy + redaction rule → REDACTED with level.
    """

    def test_payload_redacted_with_level(self) -> None:
        eng = _make_engine()
        eng.classify_data(
            "msg-payload-001", "tenant-beta",
            classification=DataClassification.CONFIDENTIAL,
        )
        eng.register_policy(
            "pol-redact", "tenant-beta",
            classification=DataClassification.CONFIDENTIAL,
            disposition=HandlingDisposition.REDACT,
        )
        eng.register_redaction_rule(
            "rr-msg", "tenant-beta",
            classification=DataClassification.CONFIDENTIAL,
            redaction_level=RedactionLevel.PARTIAL,
        )
        dec = eng.evaluate_handling("msg-payload-001", "send_message")
        assert dec.decision == GovernanceDecision.REDACTED
        assert dec.disposition == HandlingDisposition.REDACT
        assert dec.redaction_level == RedactionLevel.PARTIAL
        assert "redaction" in dec.reason



class TestGoldenScenario3MemoryBlockedByPrivacy:
    """Memory write blocked by tenant privacy rule.
    Setup: PII data with LEGITIMATE_INTEREST basis, privacy rule requires CONSENT.
    Expected: memory_storage → DENIED.
    """

    def test_memory_blocked_by_privacy(self) -> None:
        eng = _make_engine()
        eng.classify_data(
            "user-profile-001", "tenant-gamma",
            classification=DataClassification.PII,
            privacy_basis=PrivacyBasis.LEGITIMATE_INTEREST,
        )
        eng.register_privacy_rule(
            "pr-pii", "tenant-gamma",
            classification=DataClassification.PII,
            required_basis=PrivacyBasis.CONSENT,
        )
        dec = eng.evaluate_memory_storage("user-profile-001")
        assert dec.decision == GovernanceDecision.DENIED
        assert "privacy basis mismatch" in dec.reason
        assert "consent" in dec.reason
        assert dec.operation == "memory_storage"

    def test_memory_allowed_with_correct_basis(self) -> None:
        eng = _make_engine()
        eng.classify_data(
            "user-profile-002", "tenant-gamma",
            classification=DataClassification.PII,
            privacy_basis=PrivacyBasis.CONSENT,
        )
        eng.register_privacy_rule(
            "pr-pii", "tenant-gamma",
            classification=DataClassification.PII,
            required_basis=PrivacyBasis.CONSENT,
        )
        dec = eng.evaluate_memory_storage("user-profile-002")
        # PII is below RESTRICTED, so no fail-closed; no deny policy → ALLOWED
        assert dec.decision == GovernanceDecision.ALLOWED


class TestGoldenScenario4ResidencyMismatchBlocksConnector:
    """Residency mismatch blocks connector usage.
    Setup: Data in US, constraint allows only EU.
    Expected: connector_transfer to US → DENIED.
    """

    def test_residency_blocks_connector(self) -> None:
        eng = _make_engine()
        eng.classify_data(
            "financial-001", "tenant-delta",
            classification=DataClassification.CONFIDENTIAL,
            residency=ResidencyRegion.US,
        )
        eng.register_residency_constraint(
            "rc-eu-only", "tenant-delta",
            allowed_regions=["eu"],
        )
        # Data residency is US, not in allowed list → DENIED
        dec = eng.evaluate_connector_transfer("financial-001", ResidencyRegion.US)
        assert dec.decision == GovernanceDecision.DENIED
        assert "residency" in dec.reason

    def test_residency_allows_eu_connector(self) -> None:
        eng = _make_engine()
        eng.classify_data(
            "financial-002", "tenant-delta",
            classification=DataClassification.CONFIDENTIAL,
            residency=ResidencyRegion.EU,
        )
        eng.register_residency_constraint(
            "rc-eu-only", "tenant-delta",
            allowed_regions=["eu"],
        )
        dec = eng.evaluate_connector_transfer("financial-002", ResidencyRegion.EU)
        assert dec.decision == GovernanceDecision.ALLOWED


class TestGoldenScenario5ReportRedactedForWorkspace:
    """Report output redacted for workspace scope.
    Setup: SENSITIVE data + redaction rule → REDACTED.
    """

    def test_report_redacted(self) -> None:
        eng = _make_engine()
        eng.classify_data(
            "report-output-001", "tenant-epsilon",
            classification=DataClassification.SENSITIVE,
        )
        eng.register_redaction_rule(
            "rr-report", "tenant-epsilon",
            classification=DataClassification.SENSITIVE,
            redaction_level=RedactionLevel.TOKENIZE,
            scope_ref_id="workspace-main",
        )
        dec = eng.evaluate_handling("report-output-001", "publish_report")
        assert dec.decision == GovernanceDecision.REDACTED
        assert dec.redaction_level == RedactionLevel.TOKENIZE



class TestGoldenScenario6ViolationDetection:
    """Violation detection produces correct violations from denied decisions."""

    def test_violations_from_denied_decisions(self) -> None:
        eng = _make_engine()
        # Set up multiple denial scenarios
        eng.classify_data("d-restricted", "t-1", classification=DataClassification.RESTRICTED)
        eng.classify_data("d-secret", "t-1", classification=DataClassification.SECRET)
        eng.classify_data("d-normal", "t-1", classification=DataClassification.INTERNAL)

        # These will be denied (fail-closed)
        dec1 = eng.evaluate_handling("d-restricted", "export")
        dec2 = eng.evaluate_handling("d-secret", "transfer")
        # This will be allowed
        dec3 = eng.evaluate_handling("d-normal", "read")

        assert dec1.decision == GovernanceDecision.DENIED
        assert dec2.decision == GovernanceDecision.DENIED
        assert dec3.decision == GovernanceDecision.ALLOWED

        viols = eng.detect_violations()
        assert len(viols) == 2
        assert eng.violation_count == 2

        data_ids = {v.data_id for v in viols}
        assert "d-restricted" in data_ids
        assert "d-secret" in data_ids
        assert "d-normal" not in data_ids

    def test_violations_include_correct_classification(self) -> None:
        eng = _make_engine()
        eng.classify_data("d-1", "t-1", classification=DataClassification.SECRET)
        eng.evaluate_handling("d-1", "op")
        viols = eng.detect_violations()
        assert viols[0].classification == DataClassification.SECRET

    def test_violations_include_reason(self) -> None:
        eng = _make_engine()
        eng.classify_data("d-1", "t-1", classification=DataClassification.RESTRICTED)
        eng.evaluate_handling("d-1", "op")
        viols = eng.detect_violations()
        assert viols[0].reason != ""

    def test_privacy_violation_detected(self) -> None:
        eng = _make_engine()
        eng.classify_data(
            "d-pii", "t-1",
            classification=DataClassification.PII,
            privacy_basis=PrivacyBasis.LEGITIMATE_INTEREST,
        )
        eng.register_privacy_rule("pr-1", "t-1", required_basis=PrivacyBasis.CONSENT)
        eng.evaluate_handling("d-pii", "op")
        viols = eng.detect_violations()
        assert len(viols) == 1
        assert "privacy" in viols[0].reason

    def test_residency_violation_detected(self) -> None:
        eng = _make_engine()
        eng.classify_data("d-us", "t-1", residency=ResidencyRegion.US)
        eng.register_residency_constraint("rc-1", "t-1", denied_regions=["us"])
        eng.evaluate_handling("d-us", "op")
        viols = eng.detect_violations()
        assert len(viols) == 1
        assert "residency" in viols[0].reason

    def test_violation_dedup_across_calls(self) -> None:
        eng = _make_engine()
        eng.classify_data("d-1", "t-1", classification=DataClassification.RESTRICTED)
        eng.evaluate_handling("d-1", "op1")
        first_viols = eng.detect_violations()
        assert len(first_viols) == 1

        # New denied decision
        eng.classify_data("d-2", "t-1", classification=DataClassification.SECRET)
        eng.evaluate_handling("d-2", "op2")
        second_viols = eng.detect_violations()
        # Only the new violation
        assert len(second_viols) == 1
        assert second_viols[0].data_id == "d-2"
        assert eng.violation_count == 2


# ===================================================================
# 28. Edge cases and integration
# ===================================================================


class TestEdgeCases:
    def test_multiple_tenants_isolated(self) -> None:
        eng = _make_engine()
        eng.classify_data("d-1", "t-1", classification=DataClassification.INTERNAL)
        eng.classify_data("d-2", "t-2", classification=DataClassification.RESTRICTED)
        eng.register_policy(
            "pol-1", "t-1",
            classification=DataClassification.INTERNAL,
            disposition=HandlingDisposition.DENY,
        )
        # t-1: has deny policy → DENIED
        dec1 = eng.evaluate_handling("d-1", "op")
        assert dec1.decision == GovernanceDecision.DENIED
        # t-2: no policy, RESTRICTED → fail-closed DENIED
        dec2 = eng.evaluate_handling("d-2", "op")
        assert dec2.decision == GovernanceDecision.DENIED

    def test_multiple_evaluations_same_data(self) -> None:
        eng = _engine_with_record()
        dec1 = eng.evaluate_handling("d-1", "read")
        dec2 = eng.evaluate_handling("d-1", "write")
        assert dec1.operation == "read"
        assert dec2.operation == "write"
        assert eng.decision_count == 2

    def test_all_convenience_methods_work(self) -> None:
        eng = _engine_with_record()
        d1 = eng.evaluate_connector_transfer("d-1", ResidencyRegion.US)
        d2 = eng.evaluate_memory_storage("d-1")
        d3 = eng.evaluate_artifact_storage("d-1")
        assert d1.operation == "connector_transfer"
        assert d2.operation == "memory_storage"
        assert d3.operation == "artifact_storage"
        assert eng.decision_count == 3

    def test_detect_violations_no_event_when_empty(self) -> None:
        es = EventSpineEngine()
        eng = DataGovernanceEngine(es)
        eng.classify_data("d-1", "t-1")
        eng.evaluate_handling("d-1", "op")  # ALLOWED
        count_before = es.event_count
        eng.detect_violations()  # no violations → no event
        assert es.event_count == count_before

    def test_redaction_level_ordering_none_partial_hash_tokenize_full(self) -> None:
        """Verify that FULL > TOKENIZE > HASH > PARTIAL > NONE."""
        eng = _make_engine()
        eng.classify_data("d-1", "t-1", classification=DataClassification.PII)
        eng.register_redaction_rule(
            "rr-1", "t-1",
            classification=DataClassification.INTERNAL,
            redaction_level=RedactionLevel.PARTIAL,
        )
        eng.register_redaction_rule(
            "rr-2", "t-1",
            classification=DataClassification.INTERNAL,
            redaction_level=RedactionLevel.TOKENIZE,
        )
        dec = eng.evaluate_handling("d-1", "op")
        # TOKENIZE > PARTIAL → TOKENIZE wins
        assert dec.redaction_level == RedactionLevel.TOKENIZE

    def test_policy_with_redaction_and_redaction_rule(self) -> None:
        """REDACT policy with an existing redaction rule uses the rule's level."""
        eng = _make_engine()
        eng.classify_data("d-1", "t-1", classification=DataClassification.CONFIDENTIAL)
        eng.register_policy(
            "pol-1", "t-1",
            classification=DataClassification.CONFIDENTIAL,
            disposition=HandlingDisposition.REDACT,
        )
        eng.register_redaction_rule(
            "rr-1", "t-1",
            classification=DataClassification.CONFIDENTIAL,
            redaction_level=RedactionLevel.HASH,
        )
        dec = eng.evaluate_handling("d-1", "op")
        assert dec.decision == GovernanceDecision.REDACTED
        assert dec.redaction_level == RedactionLevel.HASH

    def test_allow_policy_passes_redaction_level_through(self) -> None:
        """ALLOW policy still reports the redaction level from rules."""
        eng = _make_engine()
        eng.classify_data("d-1", "t-1", classification=DataClassification.SENSITIVE)
        eng.register_policy(
            "pol-1", "t-1",
            classification=DataClassification.SENSITIVE,
            disposition=HandlingDisposition.ALLOW,
        )
        eng.register_redaction_rule(
            "rr-1", "t-1",
            classification=DataClassification.SENSITIVE,
            redaction_level=RedactionLevel.PARTIAL,
        )
        dec = eng.evaluate_handling("d-1", "op")
        assert dec.decision == GovernanceDecision.ALLOWED
        assert dec.redaction_level == RedactionLevel.PARTIAL

    def test_full_lifecycle(self) -> None:
        """Full lifecycle: classify, register rules, evaluate, detect, snapshot."""
        eng = _make_engine()
        eng.classify_data("d-1", "t-1", classification=DataClassification.RESTRICTED)
        eng.classify_data("d-2", "t-1", classification=DataClassification.INTERNAL, residency=ResidencyRegion.US)
        eng.register_policy(
            "pol-1", "t-1",
            classification=DataClassification.INTERNAL,
            disposition=HandlingDisposition.ALLOW,
        )
        eng.register_residency_constraint("rc-1", "t-1", allowed_regions=["us", "eu"])
        eng.register_privacy_rule("pr-1", "t-1")
        eng.register_redaction_rule("rr-1", "t-1")
        eng.register_retention_rule("ret-1", "t-1")

        dec1 = eng.evaluate_handling("d-1", "export")  # RESTRICTED denied: privacy rule (PII requires CONSENT, data has LEGITIMATE_INTEREST)
        assert dec1.decision == GovernanceDecision.DENIED

        dec2 = eng.evaluate_handling("d-2", "read")
        assert dec2.decision == GovernanceDecision.ALLOWED

        viols = eng.detect_violations()
        snap = eng.governance_snapshot("snap-lifecycle")
        assert snap.total_records == 2
        assert snap.total_policies == 1
        assert snap.total_decisions == 2

        h = eng.state_hash()
        assert len(h) == 64
