"""Comprehensive tests for the MemoryConsolidationEngine.

Tests cover: construction, candidate registration, importance scoring,
batch consolidation, conflict resolution, retention rules, personalization
profiles, assessments, snapshots, violation detection, state_hash,
deterministic replay, edge cases, and golden scenarios.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.memory_consolidation import (
    ConflictResolutionMode,
    ConsolidationAssessment,
    ConsolidationBatch,
    ConsolidationDecision,
    ConsolidationStatus,
    MemoryCandidate,
    MemoryConflict,
    MemoryConsolidationSnapshot,
    MemoryConsolidationViolation,
    MemoryImportance,
    MemoryRiskLevel,
    PersonalizationProfile,
    PersonalizationScope,
    RetentionDisposition,
    RetentionRule,
)
from mcoi_runtime.core.engine_protocol import FixedClock
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.memory_consolidation import MemoryConsolidationEngine


# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture()
def es():
    return EventSpineEngine()


@pytest.fixture()
def clock():
    return FixedClock("2026-01-01T00:00:00+00:00")


@pytest.fixture()
def engine(es, clock):
    return MemoryConsolidationEngine(es, clock=clock)


# ===================================================================
# Construction
# ===================================================================


class TestEngineConstruction:
    def test_valid_construction(self, es, clock):
        eng = MemoryConsolidationEngine(es, clock=clock)
        assert eng.candidate_count == 0

    def test_construction_without_clock(self, es):
        eng = MemoryConsolidationEngine(es)
        assert eng.candidate_count == 0

    def test_invalid_event_spine_type(self):
        with pytest.raises(RuntimeCoreInvariantError):
            MemoryConsolidationEngine("not-an-engine")

    def test_invalid_event_spine_none(self):
        with pytest.raises(RuntimeCoreInvariantError):
            MemoryConsolidationEngine(None)

    def test_initial_candidate_count(self, engine):
        assert engine.candidate_count == 0

    def test_initial_decision_count(self, engine):
        assert engine.decision_count == 0

    def test_initial_rule_count(self, engine):
        assert engine.rule_count == 0

    def test_initial_profile_count(self, engine):
        assert engine.profile_count == 0

    def test_initial_conflict_count(self, engine):
        assert engine.conflict_count == 0

    def test_initial_batch_count(self, engine):
        assert engine.batch_count == 0

    def test_initial_violation_count(self, engine):
        assert engine.violation_count == 0


# ===================================================================
# Memory Candidate Registration
# ===================================================================


class TestRegisterMemoryCandidate:
    def test_register_basic(self, engine, es):
        c = engine.register_memory_candidate("c-1", "t-1", "src-1", "summary")
        assert isinstance(c, MemoryCandidate)
        assert c.candidate_id == "c-1"
        assert c.tenant_id == "t-1"
        assert c.source_ref == "src-1"
        assert c.content_summary == "summary"
        assert c.status is ConsolidationStatus.CANDIDATE

    def test_register_increments_count(self, engine, es):
        engine.register_memory_candidate("c-1", "t-1", "s-1", "s")
        assert engine.candidate_count == 1
        engine.register_memory_candidate("c-2", "t-1", "s-2", "s")
        assert engine.candidate_count == 2

    def test_register_emits_event(self, engine, es):
        initial = es.event_count
        engine.register_memory_candidate("c-1", "t-1", "s-1", "s")
        assert es.event_count > initial

    def test_register_default_importance(self, engine):
        c = engine.register_memory_candidate("c-1", "t-1", "s-1", "s")
        assert c.importance is MemoryImportance.MEDIUM

    def test_register_custom_importance(self, engine):
        c = engine.register_memory_candidate("c-1", "t-1", "s-1", "s", importance=MemoryImportance.CRITICAL)
        assert c.importance is MemoryImportance.CRITICAL

    def test_register_custom_occurrence_count(self, engine):
        c = engine.register_memory_candidate("c-1", "t-1", "s-1", "s", occurrence_count=10)
        assert c.occurrence_count == 10

    def test_register_default_occurrence_count(self, engine):
        c = engine.register_memory_candidate("c-1", "t-1", "s-1", "s")
        assert c.occurrence_count == 1

    def test_register_duplicate_raises(self, engine):
        engine.register_memory_candidate("c-1", "t-1", "s-1", "s")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate candidate_id"):
            engine.register_memory_candidate("c-1", "t-1", "s-1", "s")

    def test_register_sets_timestamps(self, engine, clock):
        c = engine.register_memory_candidate("c-1", "t-1", "s-1", "s")
        assert c.first_seen_at == "2026-01-01T00:00:00+00:00"
        assert c.last_seen_at == "2026-01-01T00:00:00+00:00"

    def test_register_all_importance_levels(self, engine):
        for i, imp in enumerate(MemoryImportance):
            c = engine.register_memory_candidate(f"c-{i}", "t-1", f"s-{i}", "s", importance=imp)
            assert c.importance is imp

    def test_register_multiple_tenants(self, engine):
        engine.register_memory_candidate("c-1", "t-1", "s-1", "s")
        engine.register_memory_candidate("c-2", "t-2", "s-2", "s")
        assert engine.candidate_count == 2


class TestGetCandidate:
    def test_get_existing(self, engine):
        engine.register_memory_candidate("c-1", "t-1", "s-1", "s")
        c = engine.get_candidate("c-1")
        assert c.candidate_id == "c-1"

    def test_get_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown candidate_id"):
            engine.get_candidate("nonexistent")


class TestCandidatesForTenant:
    def test_empty_result(self, engine):
        result = engine.candidates_for_tenant("t-1")
        assert result == ()

    def test_filters_by_tenant(self, engine):
        engine.register_memory_candidate("c-1", "t-1", "s-1", "s")
        engine.register_memory_candidate("c-2", "t-2", "s-2", "s")
        engine.register_memory_candidate("c-3", "t-1", "s-3", "s")
        result = engine.candidates_for_tenant("t-1")
        assert len(result) == 2
        assert all(c.tenant_id == "t-1" for c in result)

    def test_returns_tuple(self, engine):
        engine.register_memory_candidate("c-1", "t-1", "s-1", "s")
        result = engine.candidates_for_tenant("t-1")
        assert isinstance(result, tuple)


# ===================================================================
# Importance Scoring
# ===================================================================


class TestScoreMemoryImportance:
    def test_count_10_is_critical(self, engine):
        engine.register_memory_candidate("c-1", "t-1", "s-1", "s", occurrence_count=10)
        imp = engine.score_memory_importance("c-1")
        assert imp is MemoryImportance.CRITICAL

    def test_count_15_is_critical(self, engine):
        engine.register_memory_candidate("c-1", "t-1", "s-1", "s", occurrence_count=15)
        imp = engine.score_memory_importance("c-1")
        assert imp is MemoryImportance.CRITICAL

    def test_count_100_is_critical(self, engine):
        engine.register_memory_candidate("c-1", "t-1", "s-1", "s", occurrence_count=100)
        imp = engine.score_memory_importance("c-1")
        assert imp is MemoryImportance.CRITICAL

    def test_count_5_is_high(self, engine):
        engine.register_memory_candidate("c-1", "t-1", "s-1", "s", occurrence_count=5)
        imp = engine.score_memory_importance("c-1")
        assert imp is MemoryImportance.HIGH

    def test_count_9_is_high(self, engine):
        engine.register_memory_candidate("c-1", "t-1", "s-1", "s", occurrence_count=9)
        imp = engine.score_memory_importance("c-1")
        assert imp is MemoryImportance.HIGH

    def test_count_2_is_medium(self, engine):
        engine.register_memory_candidate("c-1", "t-1", "s-1", "s", occurrence_count=2)
        imp = engine.score_memory_importance("c-1")
        assert imp is MemoryImportance.MEDIUM

    def test_count_4_is_medium(self, engine):
        engine.register_memory_candidate("c-1", "t-1", "s-1", "s", occurrence_count=4)
        imp = engine.score_memory_importance("c-1")
        assert imp is MemoryImportance.MEDIUM

    def test_count_1_is_low(self, engine):
        engine.register_memory_candidate("c-1", "t-1", "s-1", "s", occurrence_count=1)
        imp = engine.score_memory_importance("c-1")
        assert imp is MemoryImportance.LOW

    def test_count_0_is_low(self, engine):
        engine.register_memory_candidate("c-1", "t-1", "s-1", "s", occurrence_count=0)
        imp = engine.score_memory_importance("c-1")
        assert imp is MemoryImportance.LOW

    def test_scoring_updates_candidate(self, engine):
        engine.register_memory_candidate("c-1", "t-1", "s-1", "s", occurrence_count=10)
        engine.score_memory_importance("c-1")
        c = engine.get_candidate("c-1")
        assert c.importance is MemoryImportance.CRITICAL

    def test_scoring_emits_event(self, engine, es):
        engine.register_memory_candidate("c-1", "t-1", "s-1", "s", occurrence_count=5)
        before = es.event_count
        engine.score_memory_importance("c-1")
        assert es.event_count > before

    def test_scoring_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError):
            engine.score_memory_importance("nonexistent")

    def test_boundary_10_critical(self, engine):
        engine.register_memory_candidate("c-1", "t-1", "s-1", "s", occurrence_count=10)
        assert engine.score_memory_importance("c-1") is MemoryImportance.CRITICAL

    def test_boundary_5_high(self, engine):
        engine.register_memory_candidate("c-1", "t-1", "s-1", "s", occurrence_count=5)
        assert engine.score_memory_importance("c-1") is MemoryImportance.HIGH

    def test_boundary_2_medium(self, engine):
        engine.register_memory_candidate("c-1", "t-1", "s-1", "s", occurrence_count=2)
        assert engine.score_memory_importance("c-1") is MemoryImportance.MEDIUM

    def test_boundary_1_low(self, engine):
        engine.register_memory_candidate("c-1", "t-1", "s-1", "s", occurrence_count=1)
        assert engine.score_memory_importance("c-1") is MemoryImportance.LOW


# ===================================================================
# Batch Consolidation
# ===================================================================


class TestConsolidateBatch:
    def test_empty_batch(self, engine):
        batch = engine.consolidate_batch("b-1", "t-1")
        assert isinstance(batch, ConsolidationBatch)
        assert batch.candidate_count == 0
        assert batch.promoted_count == 0
        assert batch.demoted_count == 0

    def test_critical_promoted(self, engine):
        engine.register_memory_candidate("c-1", "t-1", "s-1", "s", importance=MemoryImportance.CRITICAL)
        batch = engine.consolidate_batch("b-1", "t-1")
        assert batch.promoted_count == 1

    def test_high_promoted(self, engine):
        engine.register_memory_candidate("c-1", "t-1", "s-1", "s", importance=MemoryImportance.HIGH)
        batch = engine.consolidate_batch("b-1", "t-1")
        assert batch.promoted_count == 1

    def test_low_single_occurrence_demoted(self, engine):
        engine.register_memory_candidate("c-1", "t-1", "s-1", "s", importance=MemoryImportance.LOW, occurrence_count=1)
        batch = engine.consolidate_batch("b-1", "t-1")
        assert batch.demoted_count == 1

    def test_low_multiple_occurrences_not_demoted(self, engine):
        engine.register_memory_candidate("c-1", "t-1", "s-1", "s", importance=MemoryImportance.LOW, occurrence_count=2)
        batch = engine.consolidate_batch("b-1", "t-1")
        assert batch.demoted_count == 0

    def test_medium_stays_candidate(self, engine):
        engine.register_memory_candidate("c-1", "t-1", "s-1", "s", importance=MemoryImportance.MEDIUM)
        batch = engine.consolidate_batch("b-1", "t-1")
        assert batch.promoted_count == 0
        assert batch.demoted_count == 0
        c = engine.get_candidate("c-1")
        assert c.status is ConsolidationStatus.CANDIDATE

    def test_ephemeral_stays_candidate(self, engine):
        engine.register_memory_candidate("c-1", "t-1", "s-1", "s", importance=MemoryImportance.EPHEMERAL)
        batch = engine.consolidate_batch("b-1", "t-1")
        assert batch.promoted_count == 0
        assert batch.demoted_count == 0

    def test_batch_creates_decisions(self, engine):
        engine.register_memory_candidate("c-1", "t-1", "s-1", "s", importance=MemoryImportance.CRITICAL)
        engine.consolidate_batch("b-1", "t-1")
        assert engine.decision_count >= 1

    def test_batch_updates_candidate_status_promoted(self, engine):
        engine.register_memory_candidate("c-1", "t-1", "s-1", "s", importance=MemoryImportance.HIGH)
        engine.consolidate_batch("b-1", "t-1")
        c = engine.get_candidate("c-1")
        assert c.status is ConsolidationStatus.PROMOTED

    def test_batch_updates_candidate_status_demoted(self, engine):
        engine.register_memory_candidate("c-1", "t-1", "s-1", "s", importance=MemoryImportance.LOW, occurrence_count=1)
        engine.consolidate_batch("b-1", "t-1")
        c = engine.get_candidate("c-1")
        assert c.status is ConsolidationStatus.DEMOTED

    def test_duplicate_batch_id_raises(self, engine):
        engine.consolidate_batch("b-1", "t-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate batch_id"):
            engine.consolidate_batch("b-1", "t-1")

    def test_batch_filters_by_tenant(self, engine):
        engine.register_memory_candidate("c-1", "t-1", "s-1", "s", importance=MemoryImportance.CRITICAL)
        engine.register_memory_candidate("c-2", "t-2", "s-2", "s", importance=MemoryImportance.CRITICAL)
        batch = engine.consolidate_batch("b-1", "t-1")
        assert batch.candidate_count == 1
        assert batch.promoted_count == 1

    def test_batch_only_processes_candidate_status(self, engine):
        engine.register_memory_candidate("c-1", "t-1", "s-1", "s", importance=MemoryImportance.CRITICAL)
        engine.consolidate_batch("b-1", "t-1")
        # c-1 is now PROMOTED, second batch should skip it
        engine.register_memory_candidate("c-2", "t-1", "s-2", "s", importance=MemoryImportance.HIGH)
        batch2 = engine.consolidate_batch("b-2", "t-1")
        assert batch2.candidate_count == 1  # only c-2

    def test_batch_emits_event(self, engine, es):
        before = es.event_count
        engine.consolidate_batch("b-1", "t-1")
        assert es.event_count > before

    def test_batch_merged_count_always_zero(self, engine):
        engine.register_memory_candidate("c-1", "t-1", "s-1", "s", importance=MemoryImportance.CRITICAL)
        batch = engine.consolidate_batch("b-1", "t-1")
        assert batch.merged_count == 0

    def test_mixed_batch(self, engine):
        engine.register_memory_candidate("c-1", "t-1", "s-1", "s1", importance=MemoryImportance.CRITICAL)
        engine.register_memory_candidate("c-2", "t-1", "s-2", "s2", importance=MemoryImportance.HIGH)
        engine.register_memory_candidate("c-3", "t-1", "s-3", "s3", importance=MemoryImportance.MEDIUM)
        engine.register_memory_candidate("c-4", "t-1", "s-4", "s4", importance=MemoryImportance.LOW, occurrence_count=1)
        engine.register_memory_candidate("c-5", "t-1", "s-5", "s5", importance=MemoryImportance.LOW, occurrence_count=3)
        batch = engine.consolidate_batch("b-1", "t-1")
        assert batch.candidate_count == 5
        assert batch.promoted_count == 2  # CRITICAL + HIGH
        assert batch.demoted_count == 1  # LOW with count==1

    def test_batch_increments_batch_count(self, engine):
        assert engine.batch_count == 0
        engine.consolidate_batch("b-1", "t-1")
        assert engine.batch_count == 1
        engine.consolidate_batch("b-2", "t-1")
        assert engine.batch_count == 2


# ===================================================================
# Conflict Resolution
# ===================================================================


class TestResolveMemoryConflict:
    def test_register_conflict(self, engine):
        mc = engine.resolve_memory_conflict("cf-1", "t-1", "c-1", "c-2")
        assert isinstance(mc, MemoryConflict)
        assert mc.conflict_id == "cf-1"
        assert mc.resolved is False

    def test_register_conflict_default_mode(self, engine):
        mc = engine.resolve_memory_conflict("cf-1", "t-1", "c-1", "c-2")
        assert mc.resolution_mode is ConflictResolutionMode.NEWER_WINS

    def test_register_conflict_custom_mode(self, engine):
        mc = engine.resolve_memory_conflict(
            "cf-1", "t-1", "c-1", "c-2",
            resolution_mode=ConflictResolutionMode.MERGE,
        )
        assert mc.resolution_mode is ConflictResolutionMode.MERGE

    def test_all_resolution_modes(self, engine):
        for i, mode in enumerate(ConflictResolutionMode):
            mc = engine.resolve_memory_conflict(f"cf-{i}", "t-1", f"a-{i}", f"b-{i}", resolution_mode=mode)
            assert mc.resolution_mode is mode

    def test_duplicate_conflict_id_raises(self, engine):
        engine.resolve_memory_conflict("cf-1", "t-1", "c-1", "c-2")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate conflict_id"):
            engine.resolve_memory_conflict("cf-1", "t-1", "c-3", "c-4")

    def test_conflict_increments_count(self, engine):
        assert engine.conflict_count == 0
        engine.resolve_memory_conflict("cf-1", "t-1", "c-1", "c-2")
        assert engine.conflict_count == 1

    def test_conflict_emits_event(self, engine, es):
        before = es.event_count
        engine.resolve_memory_conflict("cf-1", "t-1", "c-1", "c-2")
        assert es.event_count > before


class TestCompleteConflictResolution:
    def test_complete_sets_resolved_true(self, engine):
        engine.resolve_memory_conflict("cf-1", "t-1", "c-1", "c-2")
        resolved = engine.complete_conflict_resolution("cf-1")
        assert resolved.resolved is True

    def test_complete_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown conflict_id"):
            engine.complete_conflict_resolution("nonexistent")

    def test_complete_already_resolved_raises(self, engine):
        engine.resolve_memory_conflict("cf-1", "t-1", "c-1", "c-2")
        engine.complete_conflict_resolution("cf-1")
        with pytest.raises(RuntimeCoreInvariantError, match="already resolved"):
            engine.complete_conflict_resolution("cf-1")

    def test_complete_emits_event(self, engine, es):
        engine.resolve_memory_conflict("cf-1", "t-1", "c-1", "c-2")
        before = es.event_count
        engine.complete_conflict_resolution("cf-1")
        assert es.event_count > before

    def test_complete_preserves_fields(self, engine):
        engine.resolve_memory_conflict("cf-1", "t-1", "c-1", "c-2", resolution_mode=ConflictResolutionMode.MERGE)
        resolved = engine.complete_conflict_resolution("cf-1")
        assert resolved.tenant_id == "t-1"
        assert resolved.candidate_a_ref == "c-1"
        assert resolved.candidate_b_ref == "c-2"
        assert resolved.resolution_mode is ConflictResolutionMode.MERGE


# ===================================================================
# Retention Rules
# ===================================================================


class TestApplyRetentionRule:
    def test_apply_basic(self, engine):
        rule = engine.apply_retention_rule(
            "r-1", "t-1", PersonalizationScope.USER, RetentionDisposition.RETAIN, 90,
        )
        assert isinstance(rule, RetentionRule)
        assert rule.rule_id == "r-1"
        assert rule.max_age_days == 90

    def test_all_scopes(self, engine):
        for i, scope in enumerate(PersonalizationScope):
            rule = engine.apply_retention_rule(
                f"r-{i}", "t-1", scope, RetentionDisposition.RETAIN, 30,
            )
            assert rule.scope is scope

    def test_all_dispositions(self, engine):
        for i, disp in enumerate(RetentionDisposition):
            rule = engine.apply_retention_rule(
                f"r-{i}", "t-1", PersonalizationScope.USER, disp, 30,
            )
            assert rule.disposition is disp

    def test_duplicate_rule_id_raises(self, engine):
        engine.apply_retention_rule("r-1", "t-1", PersonalizationScope.USER, RetentionDisposition.RETAIN)
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate rule_id"):
            engine.apply_retention_rule("r-1", "t-1", PersonalizationScope.USER, RetentionDisposition.RETAIN)

    def test_rule_increments_count(self, engine):
        assert engine.rule_count == 0
        engine.apply_retention_rule("r-1", "t-1", PersonalizationScope.USER, RetentionDisposition.RETAIN)
        assert engine.rule_count == 1

    def test_rule_emits_event(self, engine, es):
        before = es.event_count
        engine.apply_retention_rule("r-1", "t-1", PersonalizationScope.USER, RetentionDisposition.RETAIN)
        assert es.event_count > before

    def test_default_max_age_days(self, engine):
        rule = engine.apply_retention_rule("r-1", "t-1", PersonalizationScope.USER, RetentionDisposition.RETAIN)
        assert rule.max_age_days == 90

    def test_custom_max_age_days(self, engine):
        rule = engine.apply_retention_rule("r-1", "t-1", PersonalizationScope.USER, RetentionDisposition.RETAIN, 365)
        assert rule.max_age_days == 365

    def test_zero_max_age_days(self, engine):
        rule = engine.apply_retention_rule("r-1", "t-1", PersonalizationScope.USER, RetentionDisposition.EXPIRE, 0)
        assert rule.max_age_days == 0


class TestGetRule:
    def test_get_existing_rule(self, engine):
        engine.apply_retention_rule("r-1", "t-1", PersonalizationScope.USER, RetentionDisposition.RETAIN)
        rule = engine.get_rule("r-1")
        assert rule.rule_id == "r-1"

    def test_get_unknown_rule_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown rule_id"):
            engine.get_rule("nonexistent")


class TestRulesForTenant:
    def test_empty_result(self, engine):
        result = engine.rules_for_tenant("t-1")
        assert result == ()

    def test_filters_by_tenant(self, engine):
        engine.apply_retention_rule("r-1", "t-1", PersonalizationScope.USER, RetentionDisposition.RETAIN)
        engine.apply_retention_rule("r-2", "t-2", PersonalizationScope.USER, RetentionDisposition.RETAIN)
        result = engine.rules_for_tenant("t-1")
        assert len(result) == 1
        assert result[0].tenant_id == "t-1"

    def test_returns_tuple(self, engine):
        engine.apply_retention_rule("r-1", "t-1", PersonalizationScope.USER, RetentionDisposition.RETAIN)
        result = engine.rules_for_tenant("t-1")
        assert isinstance(result, tuple)


# ===================================================================
# Personalization Profiles
# ===================================================================


class TestBuildPersonalizationProfile:
    def test_build_profile_no_candidates(self, engine):
        profile = engine.build_personalization_profile("p-1", "t-1", "user-1")
        assert isinstance(profile, PersonalizationProfile)
        assert profile.preference_count == 0
        assert profile.confidence == 1.0  # no promoted/demoted => default 1.0

    def test_build_profile_with_promoted(self, engine):
        engine.register_memory_candidate("c-1", "t-1", "s-1", "s", importance=MemoryImportance.CRITICAL)
        engine.consolidate_batch("b-1", "t-1")
        profile = engine.build_personalization_profile("p-1", "t-1", "user-1")
        assert profile.preference_count == 1
        assert profile.confidence == 1.0  # 1/(1+0) = 1.0

    def test_build_profile_with_mixed(self, engine):
        engine.register_memory_candidate("c-1", "t-1", "s-1", "s", importance=MemoryImportance.CRITICAL)
        engine.register_memory_candidate("c-2", "t-1", "s-2", "s", importance=MemoryImportance.LOW, occurrence_count=1)
        engine.consolidate_batch("b-1", "t-1")
        profile = engine.build_personalization_profile("p-1", "t-1", "user-1")
        assert profile.preference_count == 1  # 1 promoted
        assert profile.confidence == 0.5  # 1/(1+1)

    def test_profile_all_scopes(self, engine):
        for i, scope in enumerate(PersonalizationScope):
            profile = engine.build_personalization_profile(f"p-{i}", "t-1", f"u-{i}", scope=scope)
            assert profile.scope is scope

    def test_duplicate_profile_id_raises(self, engine):
        engine.build_personalization_profile("p-1", "t-1", "user-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate profile_id"):
            engine.build_personalization_profile("p-1", "t-1", "user-1")

    def test_profile_increments_count(self, engine):
        assert engine.profile_count == 0
        engine.build_personalization_profile("p-1", "t-1", "user-1")
        assert engine.profile_count == 1

    def test_profile_emits_event(self, engine, es):
        before = es.event_count
        engine.build_personalization_profile("p-1", "t-1", "user-1")
        assert es.event_count > before

    def test_profile_filters_by_tenant(self, engine):
        engine.register_memory_candidate("c-1", "t-1", "s-1", "s", importance=MemoryImportance.CRITICAL)
        engine.register_memory_candidate("c-2", "t-2", "s-2", "s", importance=MemoryImportance.CRITICAL)
        engine.consolidate_batch("b-1", "t-1")
        engine.consolidate_batch("b-2", "t-2")
        profile = engine.build_personalization_profile("p-1", "t-1", "user-1")
        assert profile.preference_count == 1  # only t-1 promoted

    def test_profile_default_scope(self, engine):
        profile = engine.build_personalization_profile("p-1", "t-1", "user-1")
        assert profile.scope is PersonalizationScope.USER


class TestGetProfile:
    def test_get_existing_profile(self, engine):
        engine.build_personalization_profile("p-1", "t-1", "user-1")
        p = engine.get_profile("p-1")
        assert p.profile_id == "p-1"

    def test_get_unknown_profile_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown profile_id"):
            engine.get_profile("nonexistent")


class TestProfilesForTenant:
    def test_empty_result(self, engine):
        assert engine.profiles_for_tenant("t-1") == ()

    def test_filters_by_tenant(self, engine):
        engine.build_personalization_profile("p-1", "t-1", "u-1")
        engine.build_personalization_profile("p-2", "t-2", "u-2")
        result = engine.profiles_for_tenant("t-1")
        assert len(result) == 1

    def test_returns_tuple(self, engine):
        engine.build_personalization_profile("p-1", "t-1", "u-1")
        assert isinstance(engine.profiles_for_tenant("t-1"), tuple)


# ===================================================================
# Consolidation Assessment
# ===================================================================


class TestConsolidationAssessment:
    def test_empty_assessment(self, engine):
        asm = engine.consolidation_assessment("a-1", "t-1")
        assert isinstance(asm, ConsolidationAssessment)
        assert asm.total_candidates == 0
        assert asm.consolidation_rate == 1.0

    def test_assessment_with_data(self, engine):
        engine.register_memory_candidate("c-1", "t-1", "s-1", "s", importance=MemoryImportance.CRITICAL)
        engine.register_memory_candidate("c-2", "t-1", "s-2", "s", importance=MemoryImportance.LOW, occurrence_count=1)
        engine.consolidate_batch("b-1", "t-1")
        asm = engine.consolidation_assessment("a-1", "t-1")
        assert asm.total_candidates == 2
        assert asm.total_promoted == 1
        assert asm.total_demoted == 1
        assert asm.consolidation_rate == 0.5

    def test_assessment_all_promoted(self, engine):
        engine.register_memory_candidate("c-1", "t-1", "s-1", "s", importance=MemoryImportance.CRITICAL)
        engine.consolidate_batch("b-1", "t-1")
        asm = engine.consolidation_assessment("a-1", "t-1")
        assert asm.consolidation_rate == 1.0

    def test_assessment_emits_event(self, engine, es):
        before = es.event_count
        engine.consolidation_assessment("a-1", "t-1")
        assert es.event_count > before

    def test_assessment_filters_by_tenant(self, engine):
        engine.register_memory_candidate("c-1", "t-1", "s-1", "s", importance=MemoryImportance.CRITICAL)
        engine.register_memory_candidate("c-2", "t-2", "s-2", "s", importance=MemoryImportance.HIGH)
        engine.consolidate_batch("b-1", "t-1")
        engine.consolidate_batch("b-2", "t-2")
        asm = engine.consolidation_assessment("a-1", "t-1")
        assert asm.total_candidates == 1


# ===================================================================
# Snapshot
# ===================================================================


class TestConsolidationSnapshot:
    def test_empty_snapshot(self, engine):
        snap = engine.consolidation_snapshot("s-1", "t-1")
        assert isinstance(snap, MemoryConsolidationSnapshot)
        assert snap.total_candidates == 0
        assert snap.total_decisions == 0

    def test_snapshot_counts(self, engine):
        engine.register_memory_candidate("c-1", "t-1", "s-1", "s", importance=MemoryImportance.CRITICAL)
        engine.consolidate_batch("b-1", "t-1")
        engine.resolve_memory_conflict("cf-1", "t-1", "c-1", "c-2")
        engine.build_personalization_profile("p-1", "t-1", "u-1")
        snap = engine.consolidation_snapshot("s-1", "t-1")
        assert snap.total_candidates == 1
        assert snap.total_decisions >= 1
        assert snap.total_profiles == 1
        assert snap.total_conflicts == 1
        assert snap.total_batches == 1

    def test_snapshot_filters_by_tenant(self, engine):
        engine.register_memory_candidate("c-1", "t-1", "s-1", "s")
        engine.register_memory_candidate("c-2", "t-2", "s-2", "s")
        snap = engine.consolidation_snapshot("s-1", "t-1")
        assert snap.total_candidates == 1


# ===================================================================
# Violation Detection
# ===================================================================


class TestDetectConsolidationViolations:
    def test_no_violations_empty(self, engine):
        violations = engine.detect_consolidation_violations("t-1")
        assert violations == ()

    def test_unresolved_conflict_violation(self, engine):
        engine.resolve_memory_conflict("cf-1", "t-1", "c-1", "c-2")
        violations = engine.detect_consolidation_violations("t-1")
        assert len(violations) == 1
        assert violations[0].operation == "unresolved_conflict"

    def test_resolved_conflict_no_violation(self, engine):
        engine.resolve_memory_conflict("cf-1", "t-1", "c-1", "c-2")
        engine.complete_conflict_resolution("cf-1")
        violations = engine.detect_consolidation_violations("t-1")
        assert all(v.operation != "unresolved_conflict" for v in violations)

    def test_candidate_no_decision_violation(self, engine):
        engine.register_memory_candidate("c-1", "t-1", "s-1", "s", occurrence_count=10)
        violations = engine.detect_consolidation_violations("t-1")
        has_no_decision = any(v.operation == "candidate_no_decision" for v in violations)
        assert has_no_decision

    def test_candidate_with_decision_no_violation(self, engine):
        engine.register_memory_candidate("c-1", "t-1", "s-1", "s", importance=MemoryImportance.CRITICAL, occurrence_count=10)
        engine.consolidate_batch("b-1", "t-1")  # creates decision
        violations = engine.detect_consolidation_violations("t-1")
        has_no_decision = any(v.operation == "candidate_no_decision" for v in violations)
        assert not has_no_decision

    def test_low_confidence_profile_violation(self, engine):
        # Create profile with confidence < 0.3
        # Need 1 promoted and 4+ demoted: confidence = 1/5 = 0.2
        engine.register_memory_candidate("c-1", "t-1", "s-1", "s", importance=MemoryImportance.HIGH)
        for i in range(4):
            engine.register_memory_candidate(f"c-d{i}", "t-1", f"sd-{i}", "s", importance=MemoryImportance.LOW, occurrence_count=1)
        engine.consolidate_batch("b-1", "t-1")
        engine.build_personalization_profile("p-1", "t-1", "u-1")
        violations = engine.detect_consolidation_violations("t-1")
        has_low_conf = any(v.operation == "profile_low_confidence" for v in violations)
        assert has_low_conf

    def test_idempotent_first_call_returns_violations(self, engine):
        engine.resolve_memory_conflict("cf-1", "t-1", "c-1", "c-2")
        v1 = engine.detect_consolidation_violations("t-1")
        assert len(v1) > 0

    def test_idempotent_second_call_returns_empty(self, engine):
        engine.resolve_memory_conflict("cf-1", "t-1", "c-1", "c-2")
        engine.detect_consolidation_violations("t-1")
        v2 = engine.detect_consolidation_violations("t-1")
        assert len(v2) == 0

    def test_idempotent_third_call_still_empty(self, engine):
        engine.resolve_memory_conflict("cf-1", "t-1", "c-1", "c-2")
        engine.detect_consolidation_violations("t-1")
        engine.detect_consolidation_violations("t-1")
        v3 = engine.detect_consolidation_violations("t-1")
        assert len(v3) == 0

    def test_violations_increment_count(self, engine):
        assert engine.violation_count == 0
        engine.resolve_memory_conflict("cf-1", "t-1", "c-1", "c-2")
        engine.detect_consolidation_violations("t-1")
        assert engine.violation_count >= 1

    def test_violations_filter_by_tenant(self, engine):
        engine.resolve_memory_conflict("cf-1", "t-1", "c-1", "c-2")
        engine.resolve_memory_conflict("cf-2", "t-2", "c-3", "c-4")
        v = engine.detect_consolidation_violations("t-1")
        assert all(vi.tenant_id == "t-1" for vi in v)

    def test_multiple_violation_types(self, engine):
        engine.resolve_memory_conflict("cf-1", "t-1", "c-1", "c-2")
        engine.register_memory_candidate("c-1", "t-1", "s-1", "s", occurrence_count=10)
        violations = engine.detect_consolidation_violations("t-1")
        operations = {v.operation for v in violations}
        assert "unresolved_conflict" in operations
        assert "candidate_no_decision" in operations


# ===================================================================
# State Hash and Snapshot
# ===================================================================


class TestStateHash:
    def test_empty_state_hash(self, engine):
        h = engine.state_hash()
        assert isinstance(h, str)
        assert len(h) == 64

    def test_state_hash_changes_on_mutation(self, engine):
        h1 = engine.state_hash()
        engine.register_memory_candidate("c-1", "t-1", "s-1", "s")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_state_hash_deterministic(self, es, clock):
        eng1 = MemoryConsolidationEngine(EventSpineEngine(), clock=FixedClock())
        eng2 = MemoryConsolidationEngine(EventSpineEngine(), clock=FixedClock())
        eng1.register_memory_candidate("c-1", "t-1", "s-1", "s")
        eng2.register_memory_candidate("c-1", "t-1", "s-1", "s")
        assert eng1.state_hash() == eng2.state_hash()


class TestEngineSnapshot:
    def test_snapshot_returns_dict(self, engine):
        snap = engine.snapshot()
        assert isinstance(snap, dict)

    def test_snapshot_has_state_hash(self, engine):
        snap = engine.snapshot()
        assert "_state_hash" in snap

    def test_snapshot_keys(self, engine):
        snap = engine.snapshot()
        expected = {"candidates", "decisions", "rules", "profiles", "conflicts", "batches", "violations", "_state_hash"}
        assert set(snap.keys()) == expected

    def test_snapshot_reflects_state(self, engine):
        engine.register_memory_candidate("c-1", "t-1", "s-1", "s")
        snap = engine.snapshot()
        assert "c-1" in snap["candidates"]

    def test_snapshot_after_batch(self, engine):
        engine.register_memory_candidate("c-1", "t-1", "s-1", "s", importance=MemoryImportance.CRITICAL)
        engine.consolidate_batch("b-1", "t-1")
        snap = engine.snapshot()
        assert len(snap["batches"]) == 1
        assert len(snap["decisions"]) >= 1


# ===================================================================
# FixedClock and Replay Determinism
# ===================================================================


class TestFixedClockReplay:
    def test_fixed_clock_timestamps(self):
        clock = FixedClock("2026-06-15T12:00:00+00:00")
        es = EventSpineEngine()
        eng = MemoryConsolidationEngine(es, clock=clock)
        c = eng.register_memory_candidate("c-1", "t-1", "s-1", "s")
        assert c.first_seen_at == "2026-06-15T12:00:00+00:00"

    def test_clock_advance(self):
        clock = FixedClock("2026-01-01T00:00:00+00:00")
        es = EventSpineEngine()
        eng = MemoryConsolidationEngine(es, clock=clock)
        eng.register_memory_candidate("c-1", "t-1", "s-1", "s")
        clock.advance("2026-06-01T00:00:00+00:00")
        eng.register_memory_candidate("c-2", "t-1", "s-2", "s")
        c2 = eng.get_candidate("c-2")
        assert c2.first_seen_at == "2026-06-01T00:00:00+00:00"

    def test_replay_same_ops_same_hash(self):
        def run():
            clk = FixedClock("2026-01-01T00:00:00+00:00")
            es = EventSpineEngine()
            eng = MemoryConsolidationEngine(es, clock=clk)
            eng.register_memory_candidate("c-1", "t-1", "s-1", "preference dark mode", importance=MemoryImportance.CRITICAL, occurrence_count=10)
            eng.register_memory_candidate("c-2", "t-1", "s-2", "preference light mode", importance=MemoryImportance.LOW, occurrence_count=1)
            eng.consolidate_batch("b-1", "t-1")
            eng.resolve_memory_conflict("cf-1", "t-1", "c-1", "c-2")
            eng.complete_conflict_resolution("cf-1")
            eng.apply_retention_rule("r-1", "t-1", PersonalizationScope.USER, RetentionDisposition.RETAIN)
            eng.build_personalization_profile("p-1", "t-1", "u-1")
            return eng.state_hash()

        h1 = run()
        h2 = run()
        assert h1 == h2

    def test_replay_different_ops_different_hash(self):
        clk1 = FixedClock()
        es1 = EventSpineEngine()
        eng1 = MemoryConsolidationEngine(es1, clock=clk1)
        eng1.register_memory_candidate("c-1", "t-1", "s-1", "s")

        clk2 = FixedClock()
        es2 = EventSpineEngine()
        eng2 = MemoryConsolidationEngine(es2, clock=clk2)
        eng2.register_memory_candidate("c-1", "t-1", "s-1", "s")
        eng2.register_memory_candidate("c-2", "t-1", "s-2", "s")

        assert eng1.state_hash() != eng2.state_hash()


# ===================================================================
# Golden Scenarios
# ===================================================================


class TestGoldenScenarios:
    def test_repeated_preference_critical_promoted(self, engine, es):
        """Golden 1: Repeated preference (count=10) scored CRITICAL and promoted."""
        c = engine.register_memory_candidate(
            "c-pref", "t-1", "session-123", "User prefers dark mode",
            occurrence_count=10,
        )
        imp = engine.score_memory_importance("c-pref")
        assert imp is MemoryImportance.CRITICAL
        batch = engine.consolidate_batch("b-1", "t-1")
        assert batch.promoted_count == 1
        updated = engine.get_candidate("c-pref")
        assert updated.status is ConsolidationStatus.PROMOTED

    def test_contradictory_memories_conflict_resolution(self, engine, es):
        """Golden 2: Contradictory memories create conflict and resolution."""
        engine.register_memory_candidate("c-dark", "t-1", "s-1", "Prefers dark mode", occurrence_count=5)
        engine.register_memory_candidate("c-light", "t-1", "s-2", "Prefers light mode", occurrence_count=3)
        conflict = engine.resolve_memory_conflict("cf-1", "t-1", "c-dark", "c-light", ConflictResolutionMode.NEWER_WINS)
        assert conflict.resolved is False
        resolved = engine.complete_conflict_resolution("cf-1")
        assert resolved.resolved is True

    def test_expired_retention_safe_demotion(self, engine, es):
        """Golden 3: Expired retention rule leads to safe demotion."""
        engine.register_memory_candidate("c-old", "t-1", "s-1", "Old preference", importance=MemoryImportance.LOW, occurrence_count=1)
        rule = engine.apply_retention_rule("r-expire", "t-1", PersonalizationScope.USER, RetentionDisposition.EXPIRE, 0)
        assert rule.disposition is RetentionDisposition.EXPIRE
        batch = engine.consolidate_batch("b-1", "t-1")
        assert batch.demoted_count == 1

    def test_customer_history_scoped_profile(self, engine, es):
        """Golden 4: Customer history builds scoped personalization profile with confidence."""
        for i in range(3):
            engine.register_memory_candidate(
                f"c-hist-{i}", "t-1", f"history-{i}", f"Customer preference {i}",
                importance=MemoryImportance.HIGH, occurrence_count=5,
            )
        engine.register_memory_candidate(
            "c-hist-low", "t-1", "history-low", "Ephemeral pref",
            importance=MemoryImportance.LOW, occurrence_count=1,
        )
        engine.consolidate_batch("b-1", "t-1")
        profile = engine.build_personalization_profile(
            "p-customer", "t-1", "customer-abc",
            scope=PersonalizationScope.ACCOUNT,
        )
        assert profile.preference_count == 3
        assert profile.confidence == 0.75  # 3/(3+1)
        assert profile.scope is PersonalizationScope.ACCOUNT

    def test_cross_tenant_consolidation_denied(self, engine, es):
        """Golden 5: Cross-tenant consolidation denied fail-closed."""
        engine.register_memory_candidate("c-1", "t-1", "s-1", "s", importance=MemoryImportance.CRITICAL)
        engine.register_memory_candidate("c-2", "t-2", "s-2", "s", importance=MemoryImportance.CRITICAL)
        batch = engine.consolidate_batch("b-1", "t-1")
        assert batch.promoted_count == 1  # only t-1
        assert batch.candidate_count == 1

    def test_replay_determinism_golden(self):
        """Golden 6: Replay with FixedClock: same ops -> same state_hash."""
        def replay():
            clk = FixedClock("2026-03-01T10:00:00+00:00")
            es = EventSpineEngine()
            eng = MemoryConsolidationEngine(es, clock=clk)
            eng.register_memory_candidate("c-1", "t-1", "s-1", "dark mode", importance=MemoryImportance.CRITICAL, occurrence_count=10)
            eng.score_memory_importance("c-1")
            eng.consolidate_batch("b-1", "t-1")
            eng.resolve_memory_conflict("cf-1", "t-1", "c-1", "c-x")
            eng.complete_conflict_resolution("cf-1")
            eng.apply_retention_rule("r-1", "t-1", PersonalizationScope.USER, RetentionDisposition.RETAIN)
            eng.build_personalization_profile("p-1", "t-1", "u-1")
            eng.detect_consolidation_violations("t-1")
            return eng.state_hash()

        assert replay() == replay()


# ===================================================================
# Edge Cases and Error Paths
# ===================================================================


class TestEdgeCases:
    def test_many_candidates_same_tenant(self, engine):
        for i in range(50):
            engine.register_memory_candidate(f"c-{i}", "t-1", f"s-{i}", f"summary-{i}")
        assert engine.candidate_count == 50

    def test_batch_with_no_matching_tenant(self, engine):
        engine.register_memory_candidate("c-1", "t-1", "s-1", "s")
        batch = engine.consolidate_batch("b-1", "t-99")
        assert batch.candidate_count == 0

    def test_score_then_batch(self, engine):
        engine.register_memory_candidate("c-1", "t-1", "s-1", "s", occurrence_count=10)
        engine.score_memory_importance("c-1")
        batch = engine.consolidate_batch("b-1", "t-1")
        assert batch.promoted_count == 1

    def test_multiple_batches_same_tenant(self, engine):
        engine.register_memory_candidate("c-1", "t-1", "s-1", "s", importance=MemoryImportance.CRITICAL)
        engine.consolidate_batch("b-1", "t-1")
        engine.register_memory_candidate("c-2", "t-1", "s-2", "s", importance=MemoryImportance.HIGH)
        engine.consolidate_batch("b-2", "t-1")
        assert engine.batch_count == 2

    def test_conflict_then_violation_detection(self, engine):
        engine.resolve_memory_conflict("cf-1", "t-1", "c-1", "c-2")
        v = engine.detect_consolidation_violations("t-1")
        assert len(v) == 1
        engine.complete_conflict_resolution("cf-1")
        # New detection should find no new violations
        v2 = engine.detect_consolidation_violations("t-1")
        assert len(v2) == 0

    def test_assessment_without_batch(self, engine):
        engine.register_memory_candidate("c-1", "t-1", "s-1", "s")
        asm = engine.consolidation_assessment("a-1", "t-1")
        assert asm.total_candidates == 1
        assert asm.total_promoted == 0
        assert asm.consolidation_rate == 1.0

    def test_profile_confidence_zero(self, engine):
        # All demoted, none promoted => confidence = 0/demoted = 0.0
        for i in range(3):
            engine.register_memory_candidate(
                f"c-{i}", "t-1", f"s-{i}", "s",
                importance=MemoryImportance.LOW, occurrence_count=1,
            )
        engine.consolidate_batch("b-1", "t-1")
        profile = engine.build_personalization_profile("p-1", "t-1", "u-1")
        assert profile.confidence == 0.0  # 0/(0+3)

    def test_snapshot_captures_violations(self, engine):
        engine.resolve_memory_conflict("cf-1", "t-1", "c-1", "c-2")
        engine.detect_consolidation_violations("t-1")
        snap = engine.consolidation_snapshot("s-1", "t-1")
        assert snap.total_violations >= 1

    def test_multiple_conflicts_multiple_violations(self, engine):
        engine.resolve_memory_conflict("cf-1", "t-1", "c-1", "c-2")
        engine.resolve_memory_conflict("cf-2", "t-1", "c-3", "c-4")
        v = engine.detect_consolidation_violations("t-1")
        assert len(v) == 2

    def test_low_occurrence_count_below_10_no_no_decision_violation(self, engine):
        engine.register_memory_candidate("c-1", "t-1", "s-1", "s", occurrence_count=9)
        v = engine.detect_consolidation_violations("t-1")
        has_no_decision = any(vi.operation == "candidate_no_decision" for vi in v)
        assert not has_no_decision

    def test_collections_returns_dict(self, engine):
        cols = engine._collections()
        assert isinstance(cols, dict)
        assert "candidates" in cols

    def test_batch_timestamp(self, engine, clock):
        engine.consolidate_batch("b-1", "t-1")
        snap = engine.snapshot()
        batch_data = snap["batches"]["b-1"]
        assert batch_data["processed_at"] == "2026-01-01T00:00:00+00:00"


# ===================================================================
# Parametric importance scoring
# ===================================================================


class TestImportanceScoringParametric:
    @pytest.mark.parametrize("count,expected", [
        (0, MemoryImportance.LOW),
        (1, MemoryImportance.LOW),
        (2, MemoryImportance.MEDIUM),
        (3, MemoryImportance.MEDIUM),
        (4, MemoryImportance.MEDIUM),
        (5, MemoryImportance.HIGH),
        (6, MemoryImportance.HIGH),
        (7, MemoryImportance.HIGH),
        (8, MemoryImportance.HIGH),
        (9, MemoryImportance.HIGH),
        (10, MemoryImportance.CRITICAL),
        (11, MemoryImportance.CRITICAL),
        (50, MemoryImportance.CRITICAL),
        (100, MemoryImportance.CRITICAL),
        (1000, MemoryImportance.CRITICAL),
    ])
    def test_scoring_thresholds(self, count, expected, es):
        clock = FixedClock()
        eng = MemoryConsolidationEngine(es, clock=clock)
        eng.register_memory_candidate("c-1", "t-1", "s-1", "s", occurrence_count=count)
        result = eng.score_memory_importance("c-1")
        assert result is expected


# ===================================================================
# Parametric batch consolidation outcomes
# ===================================================================


class TestBatchOutcomesParametric:
    @pytest.mark.parametrize("importance,count,expected_status", [
        (MemoryImportance.CRITICAL, 1, ConsolidationStatus.PROMOTED),
        (MemoryImportance.CRITICAL, 10, ConsolidationStatus.PROMOTED),
        (MemoryImportance.HIGH, 1, ConsolidationStatus.PROMOTED),
        (MemoryImportance.HIGH, 5, ConsolidationStatus.PROMOTED),
        (MemoryImportance.MEDIUM, 1, ConsolidationStatus.CANDIDATE),
        (MemoryImportance.MEDIUM, 5, ConsolidationStatus.CANDIDATE),
        (MemoryImportance.LOW, 1, ConsolidationStatus.DEMOTED),
        (MemoryImportance.LOW, 2, ConsolidationStatus.CANDIDATE),
        (MemoryImportance.LOW, 10, ConsolidationStatus.CANDIDATE),
        (MemoryImportance.EPHEMERAL, 1, ConsolidationStatus.CANDIDATE),
        (MemoryImportance.EPHEMERAL, 10, ConsolidationStatus.CANDIDATE),
    ])
    def test_batch_outcome(self, importance, count, expected_status, es):
        clock = FixedClock()
        eng = MemoryConsolidationEngine(es, clock=clock)
        eng.register_memory_candidate("c-1", "t-1", "s-1", "s", importance=importance, occurrence_count=count)
        eng.consolidate_batch("b-1", "t-1")
        c = eng.get_candidate("c-1")
        assert c.status is expected_status


# ===================================================================
# Additional engine tests for coverage
# ===================================================================


class TestAdditionalEngineCoverage:
    def test_register_with_zero_occurrence_count(self, engine):
        c = engine.register_memory_candidate("c-1", "t-1", "s-1", "s", occurrence_count=0)
        assert c.occurrence_count == 0

    def test_score_updates_but_preserves_other_fields(self, engine):
        engine.register_memory_candidate("c-1", "t-1", "src-original", "summary-original", occurrence_count=10)
        engine.score_memory_importance("c-1")
        c = engine.get_candidate("c-1")
        assert c.source_ref == "src-original"
        assert c.content_summary == "summary-original"
        assert c.importance is MemoryImportance.CRITICAL

    def test_batch_does_not_re_promote(self, engine):
        engine.register_memory_candidate("c-1", "t-1", "s-1", "s", importance=MemoryImportance.CRITICAL)
        b1 = engine.consolidate_batch("b-1", "t-1")
        assert b1.promoted_count == 1
        b2 = engine.consolidate_batch("b-2", "t-1")
        assert b2.candidate_count == 0  # c-1 already promoted

    def test_assessment_consolidation_rate_precision(self, engine):
        # 2 promoted, 1 demoted => rate = 2/3 ~ 0.6667
        engine.register_memory_candidate("c-1", "t-1", "s-1", "s", importance=MemoryImportance.CRITICAL)
        engine.register_memory_candidate("c-2", "t-1", "s-2", "s", importance=MemoryImportance.HIGH)
        engine.register_memory_candidate("c-3", "t-1", "s-3", "s", importance=MemoryImportance.LOW, occurrence_count=1)
        engine.consolidate_batch("b-1", "t-1")
        asm = engine.consolidation_assessment("a-1", "t-1")
        assert abs(asm.consolidation_rate - 2/3) < 0.001

    def test_empty_engine_snapshot_all_empty(self, engine):
        snap = engine.snapshot()
        for key in ["candidates", "decisions", "rules", "profiles", "conflicts", "batches", "violations"]:
            assert snap[key] == {}

    def test_violation_detection_does_not_double_count(self, engine):
        engine.resolve_memory_conflict("cf-1", "t-1", "c-1", "c-2")
        engine.resolve_memory_conflict("cf-2", "t-1", "c-3", "c-4")
        v1 = engine.detect_consolidation_violations("t-1")
        assert len(v1) == 2
        assert engine.violation_count == 2
        v2 = engine.detect_consolidation_violations("t-1")
        assert len(v2) == 0
        assert engine.violation_count == 2  # unchanged

    def test_all_count_properties(self, engine):
        engine.register_memory_candidate("c-1", "t-1", "s-1", "s", importance=MemoryImportance.CRITICAL)
        engine.consolidate_batch("b-1", "t-1")
        engine.resolve_memory_conflict("cf-1", "t-1", "c-1", "c-2")
        engine.apply_retention_rule("r-1", "t-1", PersonalizationScope.USER, RetentionDisposition.RETAIN)
        engine.build_personalization_profile("p-1", "t-1", "u-1")
        engine.detect_consolidation_violations("t-1")

        assert engine.candidate_count == 1
        assert engine.decision_count >= 1
        assert engine.batch_count == 1
        assert engine.conflict_count == 1
        assert engine.rule_count == 1
        assert engine.profile_count == 1
        assert engine.violation_count >= 1

    def test_many_tenants_isolated(self, engine):
        for i in range(10):
            tid = f"t-{i}"
            engine.register_memory_candidate(f"c-{i}", tid, f"s-{i}", "s", importance=MemoryImportance.CRITICAL)
            engine.consolidate_batch(f"b-{i}", tid)
        for i in range(10):
            cs = engine.candidates_for_tenant(f"t-{i}")
            assert len(cs) == 1
            assert cs[0].status is ConsolidationStatus.PROMOTED

    def test_state_hash_consistent_across_calls(self, engine):
        engine.register_memory_candidate("c-1", "t-1", "s-1", "s")
        h1 = engine.state_hash()
        h2 = engine.state_hash()
        assert h1 == h2

    def test_snapshot_state_hash_matches(self, engine):
        engine.register_memory_candidate("c-1", "t-1", "s-1", "s")
        snap = engine.snapshot()
        assert snap["_state_hash"] == engine.state_hash()
