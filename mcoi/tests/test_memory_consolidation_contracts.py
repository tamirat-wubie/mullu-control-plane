"""Comprehensive tests for memory consolidation / long-horizon personalization contracts.

Tests cover: enum membership, dataclass construction, validation failures,
frozen immutability, metadata freezing, to_dict() serialization, to_json_dict(),
to_json(), edge cases, boundary values, and enum-object preservation.
"""

from __future__ import annotations

import dataclasses
import json
import math
from dataclasses import FrozenInstanceError
from types import MappingProxyType

import pytest

from mcoi_runtime.contracts.memory_consolidation import (
    ConflictResolutionMode,
    ConsolidationAssessment,
    ConsolidationBatch,
    ConsolidationDecision,
    ConsolidationStatus,
    MemoryCandidate,
    MemoryConflict,
    MemoryConsolidationClosureReport,
    MemoryConsolidationSnapshot,
    MemoryConsolidationViolation,
    MemoryImportance,
    MemoryRiskLevel,
    PersonalizationProfile,
    PersonalizationScope,
    RetentionDisposition,
    RetentionRule,
)


# ===================================================================
# Helpers: valid kwargs for each dataclass
# ===================================================================


def _candidate_kw(**overrides):
    base = dict(
        candidate_id="cand-1", tenant_id="t-1", source_ref="src-1",
        content_summary="User prefers dark mode",
        importance=MemoryImportance.MEDIUM,
        status=ConsolidationStatus.CANDIDATE,
        occurrence_count=1,
        first_seen_at="2025-06-01T00:00:00+00:00",
        last_seen_at="2025-06-01T00:00:00+00:00",
    )
    base.update(overrides)
    return base


def _decision_kw(**overrides):
    base = dict(
        decision_id="dec-1", tenant_id="t-1", candidate_ref="cand-1",
        disposition=ConsolidationStatus.PROMOTED,
        reason="High importance qualifies for promotion",
        decided_at="2025-06-01T00:00:00+00:00",
    )
    base.update(overrides)
    return base


def _rule_kw(**overrides):
    base = dict(
        rule_id="rule-1", tenant_id="t-1",
        scope=PersonalizationScope.USER,
        disposition=RetentionDisposition.RETAIN,
        max_age_days=90,
        created_at="2025-06-01T00:00:00+00:00",
    )
    base.update(overrides)
    return base


def _profile_kw(**overrides):
    base = dict(
        profile_id="prof-1", tenant_id="t-1", identity_ref="user-1",
        scope=PersonalizationScope.USER,
        preference_count=5,
        confidence=0.8,
        updated_at="2025-06-01T00:00:00+00:00",
    )
    base.update(overrides)
    return base


def _conflict_kw(**overrides):
    base = dict(
        conflict_id="conf-1", tenant_id="t-1",
        candidate_a_ref="cand-1", candidate_b_ref="cand-2",
        resolution_mode=ConflictResolutionMode.NEWER_WINS,
        resolved=False,
        detected_at="2025-06-01T00:00:00+00:00",
    )
    base.update(overrides)
    return base


def _batch_kw(**overrides):
    base = dict(
        batch_id="batch-1", tenant_id="t-1",
        candidate_count=10, promoted_count=5,
        demoted_count=2, merged_count=1,
        processed_at="2025-06-01T00:00:00+00:00",
    )
    base.update(overrides)
    return base


def _assessment_kw(**overrides):
    base = dict(
        assessment_id="asm-1", tenant_id="t-1",
        total_candidates=20, total_promoted=10,
        total_demoted=5, consolidation_rate=0.67,
        assessed_at="2025-06-01T00:00:00+00:00",
    )
    base.update(overrides)
    return base


def _violation_kw(**overrides):
    base = dict(
        violation_id="viol-1", tenant_id="t-1",
        operation="unresolved_conflict",
        reason="Conflict conf-1 is not resolved",
        detected_at="2025-06-01T00:00:00+00:00",
    )
    base.update(overrides)
    return base


def _snapshot_kw(**overrides):
    base = dict(
        snapshot_id="snap-1", tenant_id="t-1",
        total_candidates=10, total_decisions=5,
        total_profiles=2, total_conflicts=1,
        total_batches=3, total_violations=0,
        captured_at="2025-06-01T00:00:00+00:00",
    )
    base.update(overrides)
    return base


def _closure_report_kw(**overrides):
    base = dict(
        report_id="rpt-1", tenant_id="t-1",
        total_candidates=20, total_decisions=15,
        total_profiles=5, total_conflicts=2,
        total_violations=1,
        created_at="2025-06-01T00:00:00+00:00",
    )
    base.update(overrides)
    return base


# ===================================================================
# ConsolidationStatus enum
# ===================================================================


class TestConsolidationStatus:
    def test_candidate_value(self):
        assert ConsolidationStatus.CANDIDATE.value == "candidate"

    def test_promoted_value(self):
        assert ConsolidationStatus.PROMOTED.value == "promoted"

    def test_demoted_value(self):
        assert ConsolidationStatus.DEMOTED.value == "demoted"

    def test_merged_value(self):
        assert ConsolidationStatus.MERGED.value == "merged"

    def test_expired_value(self):
        assert ConsolidationStatus.EXPIRED.value == "expired"

    def test_rejected_value(self):
        assert ConsolidationStatus.REJECTED.value == "rejected"

    def test_member_count(self):
        assert len(ConsolidationStatus) == 6

    def test_from_value(self):
        assert ConsolidationStatus("candidate") is ConsolidationStatus.CANDIDATE

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            ConsolidationStatus("unknown")


# ===================================================================
# MemoryImportance enum
# ===================================================================


class TestMemoryImportance:
    def test_critical_value(self):
        assert MemoryImportance.CRITICAL.value == "critical"

    def test_high_value(self):
        assert MemoryImportance.HIGH.value == "high"

    def test_medium_value(self):
        assert MemoryImportance.MEDIUM.value == "medium"

    def test_low_value(self):
        assert MemoryImportance.LOW.value == "low"

    def test_ephemeral_value(self):
        assert MemoryImportance.EPHEMERAL.value == "ephemeral"

    def test_member_count(self):
        assert len(MemoryImportance) == 5

    def test_from_value(self):
        assert MemoryImportance("critical") is MemoryImportance.CRITICAL

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            MemoryImportance("unknown")


# ===================================================================
# RetentionDisposition enum
# ===================================================================


class TestRetentionDisposition:
    def test_retain_value(self):
        assert RetentionDisposition.RETAIN.value == "retain"

    def test_demote_value(self):
        assert RetentionDisposition.DEMOTE.value == "demote"

    def test_expire_value(self):
        assert RetentionDisposition.EXPIRE.value == "expire"

    def test_archive_value(self):
        assert RetentionDisposition.ARCHIVE.value == "archive"

    def test_delete_value(self):
        assert RetentionDisposition.DELETE.value == "delete"

    def test_member_count(self):
        assert len(RetentionDisposition) == 5

    def test_from_value(self):
        assert RetentionDisposition("retain") is RetentionDisposition.RETAIN

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            RetentionDisposition("unknown")


# ===================================================================
# PersonalizationScope enum
# ===================================================================


class TestPersonalizationScope:
    def test_user_value(self):
        assert PersonalizationScope.USER.value == "user"

    def test_account_value(self):
        assert PersonalizationScope.ACCOUNT.value == "account"

    def test_tenant_value(self):
        assert PersonalizationScope.TENANT.value == "tenant"

    def test_organization_value(self):
        assert PersonalizationScope.ORGANIZATION.value == "organization"

    def test_global_value(self):
        assert PersonalizationScope.GLOBAL.value == "global"

    def test_member_count(self):
        assert len(PersonalizationScope) == 5

    def test_from_value(self):
        assert PersonalizationScope("user") is PersonalizationScope.USER

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            PersonalizationScope("unknown")


# ===================================================================
# ConflictResolutionMode enum
# ===================================================================


class TestConflictResolutionMode:
    def test_newer_wins_value(self):
        assert ConflictResolutionMode.NEWER_WINS.value == "newer_wins"

    def test_older_wins_value(self):
        assert ConflictResolutionMode.OLDER_WINS.value == "older_wins"

    def test_merge_value(self):
        assert ConflictResolutionMode.MERGE.value == "merge"

    def test_manual_value(self):
        assert ConflictResolutionMode.MANUAL.value == "manual"

    def test_reject_value(self):
        assert ConflictResolutionMode.REJECT.value == "reject"

    def test_member_count(self):
        assert len(ConflictResolutionMode) == 5

    def test_from_value(self):
        assert ConflictResolutionMode("newer_wins") is ConflictResolutionMode.NEWER_WINS

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            ConflictResolutionMode("unknown")


# ===================================================================
# MemoryRiskLevel enum
# ===================================================================


class TestMemoryRiskLevel:
    def test_low_value(self):
        assert MemoryRiskLevel.LOW.value == "low"

    def test_medium_value(self):
        assert MemoryRiskLevel.MEDIUM.value == "medium"

    def test_high_value(self):
        assert MemoryRiskLevel.HIGH.value == "high"

    def test_critical_value(self):
        assert MemoryRiskLevel.CRITICAL.value == "critical"

    def test_member_count(self):
        assert len(MemoryRiskLevel) == 4

    def test_from_value(self):
        assert MemoryRiskLevel("low") is MemoryRiskLevel.LOW

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            MemoryRiskLevel("unknown")


# ===================================================================
# MemoryCandidate
# ===================================================================


class TestMemoryCandidateConstruction:
    def test_valid_construction(self):
        mc = MemoryCandidate(**_candidate_kw())
        assert mc.candidate_id == "cand-1"
        assert mc.tenant_id == "t-1"
        assert mc.source_ref == "src-1"
        assert mc.content_summary == "User prefers dark mode"
        assert mc.importance is MemoryImportance.MEDIUM
        assert mc.status is ConsolidationStatus.CANDIDATE
        assert mc.occurrence_count == 1

    def test_all_importance_levels(self):
        for imp in MemoryImportance:
            mc = MemoryCandidate(**_candidate_kw(importance=imp))
            assert mc.importance is imp

    def test_all_status_values(self):
        for st in ConsolidationStatus:
            mc = MemoryCandidate(**_candidate_kw(status=st))
            assert mc.status is st

    def test_zero_occurrence_count(self):
        mc = MemoryCandidate(**_candidate_kw(occurrence_count=0))
        assert mc.occurrence_count == 0

    def test_large_occurrence_count(self):
        mc = MemoryCandidate(**_candidate_kw(occurrence_count=10000))
        assert mc.occurrence_count == 10000

    def test_metadata_dict(self):
        mc = MemoryCandidate(**_candidate_kw(metadata={"key": "val"}))
        assert mc.metadata["key"] == "val"

    def test_metadata_frozen(self):
        mc = MemoryCandidate(**_candidate_kw(metadata={"k": "v"}))
        assert isinstance(mc.metadata, MappingProxyType)

    def test_metadata_default_empty(self):
        mc = MemoryCandidate(**_candidate_kw())
        assert len(mc.metadata) == 0

    def test_nested_metadata_frozen(self):
        mc = MemoryCandidate(**_candidate_kw(metadata={"a": {"b": "c"}}))
        assert isinstance(mc.metadata["a"], MappingProxyType)

    def test_has_slots(self):
        assert hasattr(MemoryCandidate, "__slots__")

    def test_is_frozen(self):
        mc = MemoryCandidate(**_candidate_kw())
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(mc, "candidate_id", "x")


class TestMemoryCandidateValidation:
    def test_empty_candidate_id(self):
        with pytest.raises(ValueError):
            MemoryCandidate(**_candidate_kw(candidate_id=""))

    def test_whitespace_candidate_id(self):
        with pytest.raises(ValueError):
            MemoryCandidate(**_candidate_kw(candidate_id="   "))

    def test_empty_tenant_id(self):
        with pytest.raises(ValueError):
            MemoryCandidate(**_candidate_kw(tenant_id=""))

    def test_empty_source_ref(self):
        with pytest.raises(ValueError):
            MemoryCandidate(**_candidate_kw(source_ref=""))

    def test_empty_content_summary(self):
        with pytest.raises(ValueError):
            MemoryCandidate(**_candidate_kw(content_summary=""))

    def test_invalid_importance_type(self):
        with pytest.raises(ValueError, match="importance must be a MemoryImportance"):
            MemoryCandidate(**_candidate_kw(importance="high"))

    def test_invalid_status_type(self):
        with pytest.raises(ValueError, match="status must be a ConsolidationStatus"):
            MemoryCandidate(**_candidate_kw(status="candidate"))

    def test_negative_occurrence_count(self):
        with pytest.raises(ValueError):
            MemoryCandidate(**_candidate_kw(occurrence_count=-1))

    def test_bool_occurrence_count_rejected(self):
        with pytest.raises(ValueError):
            MemoryCandidate(**_candidate_kw(occurrence_count=True))

    def test_float_occurrence_count_rejected(self):
        with pytest.raises((ValueError, TypeError)):
            MemoryCandidate(**_candidate_kw(occurrence_count=1.5))

    def test_invalid_first_seen_at(self):
        with pytest.raises(ValueError):
            MemoryCandidate(**_candidate_kw(first_seen_at="not-a-date"))

    def test_invalid_last_seen_at(self):
        with pytest.raises(ValueError):
            MemoryCandidate(**_candidate_kw(last_seen_at="not-a-date"))

    def test_empty_first_seen_at(self):
        with pytest.raises(ValueError):
            MemoryCandidate(**_candidate_kw(first_seen_at=""))

    def test_empty_last_seen_at(self):
        with pytest.raises(ValueError):
            MemoryCandidate(**_candidate_kw(last_seen_at=""))


class TestMemoryCandidateSerialization:
    def test_to_dict_preserves_enum_objects(self):
        mc = MemoryCandidate(**_candidate_kw())
        d = mc.to_dict()
        assert d["importance"] is MemoryImportance.MEDIUM
        assert d["status"] is ConsolidationStatus.CANDIDATE

    def test_to_dict_keys(self):
        mc = MemoryCandidate(**_candidate_kw())
        d = mc.to_dict()
        expected = {
            "candidate_id", "tenant_id", "source_ref", "content_summary",
            "importance", "status", "occurrence_count", "first_seen_at",
            "last_seen_at", "metadata",
        }
        assert set(d.keys()) == expected

    def test_to_json_dict_enum_values(self):
        mc = MemoryCandidate(**_candidate_kw())
        d = mc.to_json_dict()
        assert d["importance"] == "medium"
        assert d["status"] == "candidate"

    def test_to_json_roundtrip(self):
        mc = MemoryCandidate(**_candidate_kw())
        j = mc.to_json()
        parsed = json.loads(j)
        assert parsed["candidate_id"] == "cand-1"

    def test_metadata_thawed_to_dict(self):
        mc = MemoryCandidate(**_candidate_kw(metadata={"k": "v"}))
        d = mc.to_dict()
        assert isinstance(d["metadata"], dict)


# ===================================================================
# ConsolidationDecision
# ===================================================================


class TestConsolidationDecisionConstruction:
    def test_valid_construction(self):
        cd = ConsolidationDecision(**_decision_kw())
        assert cd.decision_id == "dec-1"
        assert cd.disposition is ConsolidationStatus.PROMOTED

    def test_all_dispositions(self):
        for st in ConsolidationStatus:
            cd = ConsolidationDecision(**_decision_kw(disposition=st))
            assert cd.disposition is st

    def test_metadata_frozen(self):
        cd = ConsolidationDecision(**_decision_kw(metadata={"a": "b"}))
        assert isinstance(cd.metadata, MappingProxyType)

    def test_has_slots(self):
        assert hasattr(ConsolidationDecision, "__slots__")

    def test_is_frozen(self):
        cd = ConsolidationDecision(**_decision_kw())
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(cd, "decision_id", "x")


class TestConsolidationDecisionValidation:
    def test_empty_decision_id(self):
        with pytest.raises(ValueError):
            ConsolidationDecision(**_decision_kw(decision_id=""))

    def test_empty_tenant_id(self):
        with pytest.raises(ValueError):
            ConsolidationDecision(**_decision_kw(tenant_id=""))

    def test_empty_candidate_ref(self):
        with pytest.raises(ValueError):
            ConsolidationDecision(**_decision_kw(candidate_ref=""))

    def test_invalid_disposition_type(self):
        with pytest.raises(ValueError, match="disposition must be a ConsolidationStatus"):
            ConsolidationDecision(**_decision_kw(disposition="promoted"))

    def test_empty_reason(self):
        with pytest.raises(ValueError):
            ConsolidationDecision(**_decision_kw(reason=""))

    def test_invalid_decided_at(self):
        with pytest.raises(ValueError):
            ConsolidationDecision(**_decision_kw(decided_at="bad-date"))


class TestConsolidationDecisionSerialization:
    def test_to_dict_preserves_enum(self):
        cd = ConsolidationDecision(**_decision_kw())
        d = cd.to_dict()
        assert d["disposition"] is ConsolidationStatus.PROMOTED

    def test_to_json_dict_enum_to_value(self):
        cd = ConsolidationDecision(**_decision_kw())
        d = cd.to_json_dict()
        assert d["disposition"] == "promoted"

    def test_to_json_roundtrip(self):
        cd = ConsolidationDecision(**_decision_kw())
        parsed = json.loads(cd.to_json())
        assert parsed["decision_id"] == "dec-1"


# ===================================================================
# RetentionRule
# ===================================================================


class TestRetentionRuleConstruction:
    def test_valid_construction(self):
        rr = RetentionRule(**_rule_kw())
        assert rr.rule_id == "rule-1"
        assert rr.scope is PersonalizationScope.USER
        assert rr.disposition is RetentionDisposition.RETAIN
        assert rr.max_age_days == 90

    def test_all_scopes(self):
        for sc in PersonalizationScope:
            rr = RetentionRule(**_rule_kw(scope=sc))
            assert rr.scope is sc

    def test_all_dispositions(self):
        for d in RetentionDisposition:
            rr = RetentionRule(**_rule_kw(disposition=d))
            assert rr.disposition is d

    def test_zero_max_age_days(self):
        rr = RetentionRule(**_rule_kw(max_age_days=0))
        assert rr.max_age_days == 0

    def test_large_max_age_days(self):
        rr = RetentionRule(**_rule_kw(max_age_days=36500))
        assert rr.max_age_days == 36500

    def test_metadata_frozen(self):
        rr = RetentionRule(**_rule_kw(metadata={"x": "y"}))
        assert isinstance(rr.metadata, MappingProxyType)

    def test_has_slots(self):
        assert hasattr(RetentionRule, "__slots__")

    def test_is_frozen(self):
        rr = RetentionRule(**_rule_kw())
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(rr, "rule_id", "x")


class TestRetentionRuleValidation:
    def test_empty_rule_id(self):
        with pytest.raises(ValueError):
            RetentionRule(**_rule_kw(rule_id=""))

    def test_empty_tenant_id(self):
        with pytest.raises(ValueError):
            RetentionRule(**_rule_kw(tenant_id=""))

    def test_invalid_scope_type(self):
        with pytest.raises(ValueError, match="scope must be a PersonalizationScope"):
            RetentionRule(**_rule_kw(scope="user"))

    def test_invalid_disposition_type(self):
        with pytest.raises(ValueError, match="disposition must be a RetentionDisposition"):
            RetentionRule(**_rule_kw(disposition="retain"))

    def test_negative_max_age_days(self):
        with pytest.raises(ValueError):
            RetentionRule(**_rule_kw(max_age_days=-1))

    def test_bool_max_age_days_rejected(self):
        with pytest.raises(ValueError):
            RetentionRule(**_rule_kw(max_age_days=True))

    def test_invalid_created_at(self):
        with pytest.raises(ValueError):
            RetentionRule(**_rule_kw(created_at="not-a-date"))


class TestRetentionRuleSerialization:
    def test_to_dict_preserves_enums(self):
        rr = RetentionRule(**_rule_kw())
        d = rr.to_dict()
        assert d["scope"] is PersonalizationScope.USER
        assert d["disposition"] is RetentionDisposition.RETAIN

    def test_to_json_dict_converts_enums(self):
        rr = RetentionRule(**_rule_kw())
        d = rr.to_json_dict()
        assert d["scope"] == "user"
        assert d["disposition"] == "retain"

    def test_to_json_roundtrip(self):
        rr = RetentionRule(**_rule_kw())
        parsed = json.loads(rr.to_json())
        assert parsed["rule_id"] == "rule-1"


# ===================================================================
# PersonalizationProfile
# ===================================================================


class TestPersonalizationProfileConstruction:
    def test_valid_construction(self):
        pp = PersonalizationProfile(**_profile_kw())
        assert pp.profile_id == "prof-1"
        assert pp.identity_ref == "user-1"
        assert pp.confidence == 0.8
        assert pp.preference_count == 5

    def test_all_scopes(self):
        for sc in PersonalizationScope:
            pp = PersonalizationProfile(**_profile_kw(scope=sc))
            assert pp.scope is sc

    def test_confidence_zero(self):
        pp = PersonalizationProfile(**_profile_kw(confidence=0.0))
        assert pp.confidence == 0.0

    def test_confidence_one(self):
        pp = PersonalizationProfile(**_profile_kw(confidence=1.0))
        assert pp.confidence == 1.0

    def test_confidence_midpoint(self):
        pp = PersonalizationProfile(**_profile_kw(confidence=0.5))
        assert pp.confidence == 0.5

    def test_zero_preference_count(self):
        pp = PersonalizationProfile(**_profile_kw(preference_count=0))
        assert pp.preference_count == 0

    def test_metadata_frozen(self):
        pp = PersonalizationProfile(**_profile_kw(metadata={"a": 1}))
        assert isinstance(pp.metadata, MappingProxyType)

    def test_has_slots(self):
        assert hasattr(PersonalizationProfile, "__slots__")

    def test_is_frozen(self):
        pp = PersonalizationProfile(**_profile_kw())
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(pp, "profile_id", "x")


class TestPersonalizationProfileValidation:
    def test_empty_profile_id(self):
        with pytest.raises(ValueError):
            PersonalizationProfile(**_profile_kw(profile_id=""))

    def test_empty_tenant_id(self):
        with pytest.raises(ValueError):
            PersonalizationProfile(**_profile_kw(tenant_id=""))

    def test_empty_identity_ref(self):
        with pytest.raises(ValueError):
            PersonalizationProfile(**_profile_kw(identity_ref=""))

    def test_invalid_scope_type(self):
        with pytest.raises(ValueError, match="scope must be a PersonalizationScope"):
            PersonalizationProfile(**_profile_kw(scope="user"))

    def test_negative_preference_count(self):
        with pytest.raises(ValueError):
            PersonalizationProfile(**_profile_kw(preference_count=-1))

    def test_bool_preference_count_rejected(self):
        with pytest.raises(ValueError):
            PersonalizationProfile(**_profile_kw(preference_count=True))

    def test_confidence_below_zero(self):
        with pytest.raises(ValueError):
            PersonalizationProfile(**_profile_kw(confidence=-0.1))

    def test_confidence_above_one(self):
        with pytest.raises(ValueError):
            PersonalizationProfile(**_profile_kw(confidence=1.1))

    def test_confidence_nan(self):
        with pytest.raises(ValueError):
            PersonalizationProfile(**_profile_kw(confidence=float("nan")))

    def test_confidence_inf(self):
        with pytest.raises(ValueError):
            PersonalizationProfile(**_profile_kw(confidence=float("inf")))

    def test_confidence_bool_rejected(self):
        with pytest.raises(ValueError):
            PersonalizationProfile(**_profile_kw(confidence=True))

    def test_confidence_string_rejected(self):
        with pytest.raises(ValueError):
            PersonalizationProfile(**_profile_kw(confidence="0.5"))

    def test_invalid_updated_at(self):
        with pytest.raises(ValueError):
            PersonalizationProfile(**_profile_kw(updated_at="not-a-date"))


class TestPersonalizationProfileSerialization:
    def test_to_dict_preserves_enum(self):
        pp = PersonalizationProfile(**_profile_kw())
        d = pp.to_dict()
        assert d["scope"] is PersonalizationScope.USER

    def test_to_json_dict_converts_enum(self):
        pp = PersonalizationProfile(**_profile_kw())
        d = pp.to_json_dict()
        assert d["scope"] == "user"

    def test_to_json_roundtrip(self):
        pp = PersonalizationProfile(**_profile_kw())
        parsed = json.loads(pp.to_json())
        assert parsed["confidence"] == 0.8


# ===================================================================
# MemoryConflict
# ===================================================================


class TestMemoryConflictConstruction:
    def test_valid_construction(self):
        mc = MemoryConflict(**_conflict_kw())
        assert mc.conflict_id == "conf-1"
        assert mc.resolved is False

    def test_resolved_true(self):
        mc = MemoryConflict(**_conflict_kw(resolved=True))
        assert mc.resolved is True

    def test_all_resolution_modes(self):
        for mode in ConflictResolutionMode:
            mc = MemoryConflict(**_conflict_kw(resolution_mode=mode))
            assert mc.resolution_mode is mode

    def test_metadata_frozen(self):
        mc = MemoryConflict(**_conflict_kw(metadata={"x": 1}))
        assert isinstance(mc.metadata, MappingProxyType)

    def test_has_slots(self):
        assert hasattr(MemoryConflict, "__slots__")

    def test_is_frozen(self):
        mc = MemoryConflict(**_conflict_kw())
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(mc, "conflict_id", "x")


class TestMemoryConflictValidation:
    def test_empty_conflict_id(self):
        with pytest.raises(ValueError):
            MemoryConflict(**_conflict_kw(conflict_id=""))

    def test_empty_tenant_id(self):
        with pytest.raises(ValueError):
            MemoryConflict(**_conflict_kw(tenant_id=""))

    def test_empty_candidate_a_ref(self):
        with pytest.raises(ValueError):
            MemoryConflict(**_conflict_kw(candidate_a_ref=""))

    def test_empty_candidate_b_ref(self):
        with pytest.raises(ValueError):
            MemoryConflict(**_conflict_kw(candidate_b_ref=""))

    def test_invalid_resolution_mode_type(self):
        with pytest.raises(ValueError, match="resolution_mode must be a ConflictResolutionMode"):
            MemoryConflict(**_conflict_kw(resolution_mode="merge"))

    def test_resolved_int_zero_rejected(self):
        with pytest.raises(ValueError, match="resolved must be a bool"):
            MemoryConflict(**_conflict_kw(resolved=0))

    def test_resolved_int_one_rejected(self):
        with pytest.raises(ValueError, match="resolved must be a bool"):
            MemoryConflict(**_conflict_kw(resolved=1))

    def test_resolved_string_rejected(self):
        with pytest.raises(ValueError, match="resolved must be a bool"):
            MemoryConflict(**_conflict_kw(resolved="false"))

    def test_resolved_none_rejected(self):
        with pytest.raises(ValueError, match="resolved must be a bool"):
            MemoryConflict(**_conflict_kw(resolved=None))

    def test_invalid_detected_at(self):
        with pytest.raises(ValueError):
            MemoryConflict(**_conflict_kw(detected_at="not-a-date"))


class TestMemoryConflictSerialization:
    def test_to_dict_preserves_enum(self):
        mc = MemoryConflict(**_conflict_kw())
        d = mc.to_dict()
        assert d["resolution_mode"] is ConflictResolutionMode.NEWER_WINS

    def test_to_json_dict_converts_enum(self):
        mc = MemoryConflict(**_conflict_kw())
        d = mc.to_json_dict()
        assert d["resolution_mode"] == "newer_wins"

    def test_to_json_roundtrip(self):
        mc = MemoryConflict(**_conflict_kw())
        parsed = json.loads(mc.to_json())
        assert parsed["resolved"] is False


# ===================================================================
# ConsolidationBatch
# ===================================================================


class TestConsolidationBatchConstruction:
    def test_valid_construction(self):
        cb = ConsolidationBatch(**_batch_kw())
        assert cb.batch_id == "batch-1"
        assert cb.candidate_count == 10
        assert cb.promoted_count == 5
        assert cb.demoted_count == 2
        assert cb.merged_count == 1

    def test_all_zeros(self):
        cb = ConsolidationBatch(**_batch_kw(
            candidate_count=0, promoted_count=0, demoted_count=0, merged_count=0,
        ))
        assert cb.candidate_count == 0

    def test_large_counts(self):
        cb = ConsolidationBatch(**_batch_kw(candidate_count=100000))
        assert cb.candidate_count == 100000

    def test_metadata_frozen(self):
        cb = ConsolidationBatch(**_batch_kw(metadata={"key": "val"}))
        assert isinstance(cb.metadata, MappingProxyType)

    def test_has_slots(self):
        assert hasattr(ConsolidationBatch, "__slots__")

    def test_is_frozen(self):
        cb = ConsolidationBatch(**_batch_kw())
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(cb, "batch_id", "x")


class TestConsolidationBatchValidation:
    def test_empty_batch_id(self):
        with pytest.raises(ValueError):
            ConsolidationBatch(**_batch_kw(batch_id=""))

    def test_empty_tenant_id(self):
        with pytest.raises(ValueError):
            ConsolidationBatch(**_batch_kw(tenant_id=""))

    def test_negative_candidate_count(self):
        with pytest.raises(ValueError):
            ConsolidationBatch(**_batch_kw(candidate_count=-1))

    def test_negative_promoted_count(self):
        with pytest.raises(ValueError):
            ConsolidationBatch(**_batch_kw(promoted_count=-1))

    def test_negative_demoted_count(self):
        with pytest.raises(ValueError):
            ConsolidationBatch(**_batch_kw(demoted_count=-1))

    def test_negative_merged_count(self):
        with pytest.raises(ValueError):
            ConsolidationBatch(**_batch_kw(merged_count=-1))

    def test_bool_candidate_count_rejected(self):
        with pytest.raises(ValueError):
            ConsolidationBatch(**_batch_kw(candidate_count=True))

    def test_invalid_processed_at(self):
        with pytest.raises(ValueError):
            ConsolidationBatch(**_batch_kw(processed_at="bad"))


class TestConsolidationBatchSerialization:
    def test_to_dict_keys(self):
        cb = ConsolidationBatch(**_batch_kw())
        d = cb.to_dict()
        expected = {
            "batch_id", "tenant_id", "candidate_count", "promoted_count",
            "demoted_count", "merged_count", "processed_at", "metadata",
        }
        assert set(d.keys()) == expected

    def test_to_json_roundtrip(self):
        cb = ConsolidationBatch(**_batch_kw())
        parsed = json.loads(cb.to_json())
        assert parsed["promoted_count"] == 5


# ===================================================================
# ConsolidationAssessment
# ===================================================================


class TestConsolidationAssessmentConstruction:
    def test_valid_construction(self):
        ca = ConsolidationAssessment(**_assessment_kw())
        assert ca.assessment_id == "asm-1"
        assert ca.consolidation_rate == 0.67

    def test_consolidation_rate_zero(self):
        ca = ConsolidationAssessment(**_assessment_kw(consolidation_rate=0.0))
        assert ca.consolidation_rate == 0.0

    def test_consolidation_rate_one(self):
        ca = ConsolidationAssessment(**_assessment_kw(consolidation_rate=1.0))
        assert ca.consolidation_rate == 1.0

    def test_all_zeros(self):
        ca = ConsolidationAssessment(**_assessment_kw(
            total_candidates=0, total_promoted=0, total_demoted=0, consolidation_rate=0.0,
        ))
        assert ca.total_candidates == 0

    def test_metadata_frozen(self):
        ca = ConsolidationAssessment(**_assessment_kw(metadata={"a": 1}))
        assert isinstance(ca.metadata, MappingProxyType)

    def test_has_slots(self):
        assert hasattr(ConsolidationAssessment, "__slots__")

    def test_is_frozen(self):
        ca = ConsolidationAssessment(**_assessment_kw())
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(ca, "assessment_id", "x")


class TestConsolidationAssessmentValidation:
    def test_empty_assessment_id(self):
        with pytest.raises(ValueError):
            ConsolidationAssessment(**_assessment_kw(assessment_id=""))

    def test_empty_tenant_id(self):
        with pytest.raises(ValueError):
            ConsolidationAssessment(**_assessment_kw(tenant_id=""))

    def test_negative_total_candidates(self):
        with pytest.raises(ValueError):
            ConsolidationAssessment(**_assessment_kw(total_candidates=-1))

    def test_negative_total_promoted(self):
        with pytest.raises(ValueError):
            ConsolidationAssessment(**_assessment_kw(total_promoted=-1))

    def test_negative_total_demoted(self):
        with pytest.raises(ValueError):
            ConsolidationAssessment(**_assessment_kw(total_demoted=-1))

    def test_consolidation_rate_above_one(self):
        with pytest.raises(ValueError):
            ConsolidationAssessment(**_assessment_kw(consolidation_rate=1.1))

    def test_consolidation_rate_below_zero(self):
        with pytest.raises(ValueError):
            ConsolidationAssessment(**_assessment_kw(consolidation_rate=-0.1))

    def test_consolidation_rate_nan(self):
        with pytest.raises(ValueError):
            ConsolidationAssessment(**_assessment_kw(consolidation_rate=float("nan")))

    def test_consolidation_rate_inf(self):
        with pytest.raises(ValueError):
            ConsolidationAssessment(**_assessment_kw(consolidation_rate=float("inf")))

    def test_consolidation_rate_bool_rejected(self):
        with pytest.raises(ValueError):
            ConsolidationAssessment(**_assessment_kw(consolidation_rate=True))

    def test_invalid_assessed_at(self):
        with pytest.raises(ValueError):
            ConsolidationAssessment(**_assessment_kw(assessed_at="bad"))


class TestConsolidationAssessmentSerialization:
    def test_to_dict_keys(self):
        ca = ConsolidationAssessment(**_assessment_kw())
        d = ca.to_dict()
        assert "consolidation_rate" in d
        assert "assessment_id" in d

    def test_to_json_roundtrip(self):
        ca = ConsolidationAssessment(**_assessment_kw())
        parsed = json.loads(ca.to_json())
        assert parsed["consolidation_rate"] == 0.67


# ===================================================================
# MemoryConsolidationViolation
# ===================================================================


class TestMemoryConsolidationViolationConstruction:
    def test_valid_construction(self):
        v = MemoryConsolidationViolation(**_violation_kw())
        assert v.violation_id == "viol-1"
        assert v.operation == "unresolved_conflict"

    def test_metadata_frozen(self):
        v = MemoryConsolidationViolation(**_violation_kw(metadata={"k": "v"}))
        assert isinstance(v.metadata, MappingProxyType)

    def test_has_slots(self):
        assert hasattr(MemoryConsolidationViolation, "__slots__")

    def test_is_frozen(self):
        v = MemoryConsolidationViolation(**_violation_kw())
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(v, "violation_id", "x")


class TestMemoryConsolidationViolationValidation:
    def test_empty_violation_id(self):
        with pytest.raises(ValueError):
            MemoryConsolidationViolation(**_violation_kw(violation_id=""))

    def test_empty_tenant_id(self):
        with pytest.raises(ValueError):
            MemoryConsolidationViolation(**_violation_kw(tenant_id=""))

    def test_empty_operation(self):
        with pytest.raises(ValueError):
            MemoryConsolidationViolation(**_violation_kw(operation=""))

    def test_empty_reason(self):
        with pytest.raises(ValueError):
            MemoryConsolidationViolation(**_violation_kw(reason=""))

    def test_invalid_detected_at(self):
        with pytest.raises(ValueError):
            MemoryConsolidationViolation(**_violation_kw(detected_at="bad"))


class TestMemoryConsolidationViolationSerialization:
    def test_to_dict_keys(self):
        v = MemoryConsolidationViolation(**_violation_kw())
        d = v.to_dict()
        expected = {"violation_id", "tenant_id", "operation", "reason", "detected_at", "metadata"}
        assert set(d.keys()) == expected

    def test_to_json_roundtrip(self):
        v = MemoryConsolidationViolation(**_violation_kw())
        parsed = json.loads(v.to_json())
        assert parsed["operation"] == "unresolved_conflict"


# ===================================================================
# MemoryConsolidationSnapshot
# ===================================================================


class TestMemoryConsolidationSnapshotConstruction:
    def test_valid_construction(self):
        s = MemoryConsolidationSnapshot(**_snapshot_kw())
        assert s.snapshot_id == "snap-1"
        assert s.total_candidates == 10

    def test_all_zeros(self):
        s = MemoryConsolidationSnapshot(**_snapshot_kw(
            total_candidates=0, total_decisions=0, total_profiles=0,
            total_conflicts=0, total_batches=0, total_violations=0,
        ))
        assert s.total_candidates == 0

    def test_large_totals(self):
        s = MemoryConsolidationSnapshot(**_snapshot_kw(total_candidates=999999))
        assert s.total_candidates == 999999

    def test_metadata_frozen(self):
        s = MemoryConsolidationSnapshot(**_snapshot_kw(metadata={"a": "b"}))
        assert isinstance(s.metadata, MappingProxyType)

    def test_has_slots(self):
        assert hasattr(MemoryConsolidationSnapshot, "__slots__")

    def test_is_frozen(self):
        s = MemoryConsolidationSnapshot(**_snapshot_kw())
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(s, "snapshot_id", "x")


class TestMemoryConsolidationSnapshotValidation:
    def test_empty_snapshot_id(self):
        with pytest.raises(ValueError):
            MemoryConsolidationSnapshot(**_snapshot_kw(snapshot_id=""))

    def test_empty_tenant_id(self):
        with pytest.raises(ValueError):
            MemoryConsolidationSnapshot(**_snapshot_kw(tenant_id=""))

    def test_negative_total_candidates(self):
        with pytest.raises(ValueError):
            MemoryConsolidationSnapshot(**_snapshot_kw(total_candidates=-1))

    def test_negative_total_decisions(self):
        with pytest.raises(ValueError):
            MemoryConsolidationSnapshot(**_snapshot_kw(total_decisions=-1))

    def test_negative_total_profiles(self):
        with pytest.raises(ValueError):
            MemoryConsolidationSnapshot(**_snapshot_kw(total_profiles=-1))

    def test_negative_total_conflicts(self):
        with pytest.raises(ValueError):
            MemoryConsolidationSnapshot(**_snapshot_kw(total_conflicts=-1))

    def test_negative_total_batches(self):
        with pytest.raises(ValueError):
            MemoryConsolidationSnapshot(**_snapshot_kw(total_batches=-1))

    def test_negative_total_violations(self):
        with pytest.raises(ValueError):
            MemoryConsolidationSnapshot(**_snapshot_kw(total_violations=-1))

    def test_bool_total_rejected(self):
        with pytest.raises(ValueError):
            MemoryConsolidationSnapshot(**_snapshot_kw(total_candidates=True))

    def test_invalid_captured_at(self):
        with pytest.raises(ValueError):
            MemoryConsolidationSnapshot(**_snapshot_kw(captured_at="bad"))


class TestMemoryConsolidationSnapshotSerialization:
    def test_to_dict_keys(self):
        s = MemoryConsolidationSnapshot(**_snapshot_kw())
        d = s.to_dict()
        expected = {
            "snapshot_id", "tenant_id", "total_candidates", "total_decisions",
            "total_profiles", "total_conflicts", "total_batches",
            "total_violations", "captured_at", "metadata",
        }
        assert set(d.keys()) == expected

    def test_to_json_roundtrip(self):
        s = MemoryConsolidationSnapshot(**_snapshot_kw())
        parsed = json.loads(s.to_json())
        assert parsed["total_candidates"] == 10


# ===================================================================
# MemoryConsolidationClosureReport
# ===================================================================


class TestMemoryConsolidationClosureReportConstruction:
    def test_valid_construction(self):
        r = MemoryConsolidationClosureReport(**_closure_report_kw())
        assert r.report_id == "rpt-1"
        assert r.total_candidates == 20

    def test_all_zeros(self):
        r = MemoryConsolidationClosureReport(**_closure_report_kw(
            total_candidates=0, total_decisions=0, total_profiles=0,
            total_conflicts=0, total_violations=0,
        ))
        assert r.total_candidates == 0

    def test_metadata_frozen(self):
        r = MemoryConsolidationClosureReport(**_closure_report_kw(metadata={"z": 1}))
        assert isinstance(r.metadata, MappingProxyType)

    def test_has_slots(self):
        assert hasattr(MemoryConsolidationClosureReport, "__slots__")

    def test_is_frozen(self):
        r = MemoryConsolidationClosureReport(**_closure_report_kw())
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(r, "report_id", "x")


class TestMemoryConsolidationClosureReportValidation:
    def test_empty_report_id(self):
        with pytest.raises(ValueError):
            MemoryConsolidationClosureReport(**_closure_report_kw(report_id=""))

    def test_empty_tenant_id(self):
        with pytest.raises(ValueError):
            MemoryConsolidationClosureReport(**_closure_report_kw(tenant_id=""))

    def test_negative_total_candidates(self):
        with pytest.raises(ValueError):
            MemoryConsolidationClosureReport(**_closure_report_kw(total_candidates=-1))

    def test_negative_total_decisions(self):
        with pytest.raises(ValueError):
            MemoryConsolidationClosureReport(**_closure_report_kw(total_decisions=-1))

    def test_negative_total_profiles(self):
        with pytest.raises(ValueError):
            MemoryConsolidationClosureReport(**_closure_report_kw(total_profiles=-1))

    def test_negative_total_conflicts(self):
        with pytest.raises(ValueError):
            MemoryConsolidationClosureReport(**_closure_report_kw(total_conflicts=-1))

    def test_negative_total_violations(self):
        with pytest.raises(ValueError):
            MemoryConsolidationClosureReport(**_closure_report_kw(total_violations=-1))

    def test_bool_total_rejected(self):
        with pytest.raises(ValueError):
            MemoryConsolidationClosureReport(**_closure_report_kw(total_candidates=True))

    def test_invalid_created_at(self):
        with pytest.raises(ValueError):
            MemoryConsolidationClosureReport(**_closure_report_kw(created_at="bad"))


class TestMemoryConsolidationClosureReportSerialization:
    def test_to_dict_keys(self):
        r = MemoryConsolidationClosureReport(**_closure_report_kw())
        d = r.to_dict()
        expected = {
            "report_id", "tenant_id", "total_candidates", "total_decisions",
            "total_profiles", "total_conflicts", "total_violations",
            "created_at", "metadata",
        }
        assert set(d.keys()) == expected

    def test_to_json_roundtrip(self):
        r = MemoryConsolidationClosureReport(**_closure_report_kw())
        parsed = json.loads(r.to_json())
        assert parsed["total_violations"] == 1


# ===================================================================
# Cross-cutting parametric tests
# ===================================================================


ALL_DATACLASSES = [
    (MemoryCandidate, _candidate_kw),
    (ConsolidationDecision, _decision_kw),
    (RetentionRule, _rule_kw),
    (PersonalizationProfile, _profile_kw),
    (MemoryConflict, _conflict_kw),
    (ConsolidationBatch, _batch_kw),
    (ConsolidationAssessment, _assessment_kw),
    (MemoryConsolidationViolation, _violation_kw),
    (MemoryConsolidationSnapshot, _snapshot_kw),
    (MemoryConsolidationClosureReport, _closure_report_kw),
]


class TestCrossCutting:
    @pytest.mark.parametrize("cls,kw_fn", ALL_DATACLASSES, ids=lambda x: x.__name__ if isinstance(x, type) else "")
    def test_is_dataclass(self, cls, kw_fn):
        assert dataclasses.is_dataclass(cls)

    @pytest.mark.parametrize("cls,kw_fn", ALL_DATACLASSES, ids=lambda x: x.__name__ if isinstance(x, type) else "")
    def test_is_frozen(self, cls, kw_fn):
        obj = cls(**kw_fn())
        first_field = dataclasses.fields(cls)[0].name
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(obj, first_field, "x")

    @pytest.mark.parametrize("cls,kw_fn", ALL_DATACLASSES, ids=lambda x: x.__name__ if isinstance(x, type) else "")
    def test_has_slots(self, cls, kw_fn):
        assert hasattr(cls, "__slots__")

    @pytest.mark.parametrize("cls,kw_fn", ALL_DATACLASSES, ids=lambda x: x.__name__ if isinstance(x, type) else "")
    def test_to_dict_returns_dict(self, cls, kw_fn):
        obj = cls(**kw_fn())
        assert isinstance(obj.to_dict(), dict)

    @pytest.mark.parametrize("cls,kw_fn", ALL_DATACLASSES, ids=lambda x: x.__name__ if isinstance(x, type) else "")
    def test_to_json_dict_returns_dict(self, cls, kw_fn):
        obj = cls(**kw_fn())
        assert isinstance(obj.to_json_dict(), dict)

    @pytest.mark.parametrize("cls,kw_fn", ALL_DATACLASSES, ids=lambda x: x.__name__ if isinstance(x, type) else "")
    def test_to_json_returns_string(self, cls, kw_fn):
        obj = cls(**kw_fn())
        j = obj.to_json()
        assert isinstance(j, str)
        json.loads(j)  # should not raise

    @pytest.mark.parametrize("cls,kw_fn", ALL_DATACLASSES, ids=lambda x: x.__name__ if isinstance(x, type) else "")
    def test_metadata_frozen_when_provided(self, cls, kw_fn):
        obj = cls(**kw_fn(metadata={"nested": {"deep": True}}))
        assert isinstance(obj.metadata, MappingProxyType)

    @pytest.mark.parametrize("cls,kw_fn", ALL_DATACLASSES, ids=lambda x: x.__name__ if isinstance(x, type) else "")
    def test_empty_tenant_id_rejects(self, cls, kw_fn):
        with pytest.raises(ValueError):
            cls(**kw_fn(tenant_id=""))

    @pytest.mark.parametrize("cls,kw_fn", ALL_DATACLASSES, ids=lambda x: x.__name__ if isinstance(x, type) else "")
    def test_whitespace_tenant_id_rejects(self, cls, kw_fn):
        with pytest.raises(ValueError):
            cls(**kw_fn(tenant_id="   "))


# ===================================================================
# Date format edge cases
# ===================================================================


class TestDateFormats:
    """Test various ISO-8601 date-time format acceptance."""

    @pytest.mark.parametrize("dt", [
        "2025-06-01T00:00:00",
        "2025-06-01T00:00:00+00:00",
        "2025-06-01T00:00:00Z",
        "2025-06-01T12:30:45.123456+05:30",
        "2025-01-01",
    ])
    def test_candidate_accepts_valid_dates(self, dt):
        mc = MemoryCandidate(**_candidate_kw(first_seen_at=dt, last_seen_at=dt))
        assert mc.first_seen_at == dt

    @pytest.mark.parametrize("dt", [
        "not-a-date",
        "2025-13-01T00:00:00",
        "",
        "   ",
    ])
    def test_candidate_rejects_invalid_dates(self, dt):
        with pytest.raises(ValueError):
            MemoryCandidate(**_candidate_kw(first_seen_at=dt))


# ===================================================================
# Metadata edge cases
# ===================================================================


class TestMetadataEdgeCases:
    def test_empty_metadata_default(self):
        mc = MemoryCandidate(**_candidate_kw())
        assert len(mc.metadata) == 0
        assert isinstance(mc.metadata, MappingProxyType)

    def test_deeply_nested_metadata(self):
        mc = MemoryCandidate(**_candidate_kw(metadata={"a": {"b": {"c": "d"}}}))
        assert mc.metadata["a"]["b"]["c"] == "d"

    def test_list_in_metadata_becomes_tuple(self):
        mc = MemoryCandidate(**_candidate_kw(metadata={"items": [1, 2, 3]}))
        assert mc.metadata["items"] == (1, 2, 3)

    def test_metadata_mutation_blocked(self):
        mc = MemoryCandidate(**_candidate_kw(metadata={"k": "v"}))
        with pytest.raises(TypeError):
            mc.metadata["k"] = "new"

    def test_metadata_nested_mutation_blocked(self):
        mc = MemoryCandidate(**_candidate_kw(metadata={"a": {"b": "c"}}))
        with pytest.raises(TypeError):
            mc.metadata["a"]["b"] = "new"

    def test_original_dict_not_mutated(self):
        original = {"k": "v"}
        mc = MemoryCandidate(**_candidate_kw(metadata=original))
        original["k"] = "changed"
        assert mc.metadata["k"] == "v"


# ===================================================================
# Additional boundary and type tests
# ===================================================================


class TestAdditionalBoundaries:
    def test_candidate_occurrence_count_max_int(self):
        mc = MemoryCandidate(**_candidate_kw(occurrence_count=2**31))
        assert mc.occurrence_count == 2**31

    def test_batch_all_counts_equal(self):
        cb = ConsolidationBatch(**_batch_kw(
            candidate_count=5, promoted_count=5, demoted_count=5, merged_count=5,
        ))
        assert cb.candidate_count == cb.promoted_count

    def test_assessment_int_consolidation_rate(self):
        ca = ConsolidationAssessment(**_assessment_kw(consolidation_rate=1))
        assert ca.consolidation_rate == 1.0

    def test_profile_int_confidence(self):
        pp = PersonalizationProfile(**_profile_kw(confidence=0))
        assert pp.confidence == 0.0

    def test_conflict_different_candidates(self):
        mc = MemoryConflict(**_conflict_kw(
            candidate_a_ref="cand-A", candidate_b_ref="cand-B",
        ))
        assert mc.candidate_a_ref != mc.candidate_b_ref

    def test_snapshot_all_independent_counts(self):
        s = MemoryConsolidationSnapshot(**_snapshot_kw(
            total_candidates=1, total_decisions=2, total_profiles=3,
            total_conflicts=4, total_batches=5, total_violations=6,
        ))
        assert s.total_candidates == 1
        assert s.total_violations == 6

    def test_closure_report_independent_counts(self):
        r = MemoryConsolidationClosureReport(**_closure_report_kw(
            total_candidates=100, total_decisions=80,
            total_profiles=10, total_conflicts=5, total_violations=3,
        ))
        assert r.total_decisions == 80

    def test_decision_whitespace_reason_rejected(self):
        with pytest.raises(ValueError):
            ConsolidationDecision(**_decision_kw(reason="   "))

    def test_violation_whitespace_operation_rejected(self):
        with pytest.raises(ValueError):
            MemoryConsolidationViolation(**_violation_kw(operation="   "))

    def test_rule_float_max_age_rejected(self):
        with pytest.raises((ValueError, TypeError)):
            RetentionRule(**_rule_kw(max_age_days=90.5))

    def test_candidate_none_importance_rejected(self):
        with pytest.raises(ValueError):
            MemoryCandidate(**_candidate_kw(importance=None))

    def test_candidate_none_status_rejected(self):
        with pytest.raises(ValueError):
            MemoryCandidate(**_candidate_kw(status=None))

    def test_conflict_none_resolution_mode_rejected(self):
        with pytest.raises(ValueError):
            MemoryConflict(**_conflict_kw(resolution_mode=None))

    def test_rule_none_scope_rejected(self):
        with pytest.raises(ValueError):
            RetentionRule(**_rule_kw(scope=None))

    def test_rule_none_disposition_rejected(self):
        with pytest.raises(ValueError):
            RetentionRule(**_rule_kw(disposition=None))

    def test_profile_none_scope_rejected(self):
        with pytest.raises(ValueError):
            PersonalizationProfile(**_profile_kw(scope=None))
