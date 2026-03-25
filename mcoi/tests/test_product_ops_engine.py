"""Comprehensive tests for ProductOpsEngine.

Covers: versions, releases, gates, promotions, rollbacks, assessments,
violations, snapshots, closure reports, state hashes, lifecycle milestones,
and golden end-to-end scenarios.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.product_ops import ProductOpsEngine
from mcoi_runtime.contracts.product_ops import (
    ReleaseStatus,
    ReleaseKind,
    PromotionDisposition,
    RollbackStatus,
    LifecycleStatus,
    ReleaseRiskLevel,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def spine() -> EventSpineEngine:
    return EventSpineEngine()


@pytest.fixture
def engine(spine: EventSpineEngine) -> ProductOpsEngine:
    return ProductOpsEngine(spine)


def _ver(engine: ProductOpsEngine, vid: str = "v1", pid: str = "p1",
         tid: str = "t1", label: str = "1.0.0",
         status: LifecycleStatus = LifecycleStatus.ACTIVE):
    return engine.register_version(vid, pid, tid, label, status)


def _rel(engine: ProductOpsEngine, rid: str = "r1", vid: str = "v1",
         tid: str = "t1", kind: ReleaseKind = ReleaseKind.MINOR,
         env: str = "staging"):
    return engine.create_release(rid, vid, tid, kind, env)


# ===========================================================================
# 1. CONSTRUCTOR
# ===========================================================================


class TestConstructor:
    def test_requires_event_spine(self):
        with pytest.raises(RuntimeCoreInvariantError):
            ProductOpsEngine("not_a_spine")

    def test_initial_counts_zero(self, engine: ProductOpsEngine):
        assert engine.version_count == 0
        assert engine.release_count == 0
        assert engine.gate_count == 0
        assert engine.promotion_count == 0
        assert engine.rollback_count == 0
        assert engine.milestone_count == 0
        assert engine.assessment_count == 0
        assert engine.violation_count == 0


# ===========================================================================
# 2. VERSIONS — register, get, list, lifecycle
# ===========================================================================


class TestRegisterVersion:
    def test_basic_register(self, engine: ProductOpsEngine):
        v = _ver(engine)
        assert v.version_id == "v1"
        assert v.product_id == "p1"
        assert v.tenant_id == "t1"
        assert v.version_label == "1.0.0"
        assert v.lifecycle_status == LifecycleStatus.ACTIVE
        assert engine.version_count == 1

    def test_register_with_custom_status(self, engine: ProductOpsEngine):
        v = _ver(engine, status=LifecycleStatus.DEPRECATED)
        assert v.lifecycle_status == LifecycleStatus.DEPRECATED

    def test_duplicate_raises(self, engine: ProductOpsEngine):
        _ver(engine)
        with pytest.raises(RuntimeCoreInvariantError, match="already registered"):
            _ver(engine)

    def test_register_multiple_versions(self, engine: ProductOpsEngine):
        _ver(engine, "v1")
        _ver(engine, "v2")
        _ver(engine, "v3")
        assert engine.version_count == 3

    def test_created_at_populated(self, engine: ProductOpsEngine):
        v = _ver(engine)
        assert v.created_at  # non-empty ISO string


class TestGetVersion:
    def test_get_existing(self, engine: ProductOpsEngine):
        _ver(engine)
        v = engine.get_version("v1")
        assert v.version_id == "v1"

    def test_get_unknown_raises(self, engine: ProductOpsEngine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown version"):
            engine.get_version("nope")


class TestVersionsForProduct:
    def test_empty(self, engine: ProductOpsEngine):
        assert engine.versions_for_product("p1") == ()

    def test_filters_correctly(self, engine: ProductOpsEngine):
        _ver(engine, "v1", pid="p1")
        _ver(engine, "v2", pid="p2")
        _ver(engine, "v3", pid="p1")
        result = engine.versions_for_product("p1")
        assert len(result) == 2
        assert all(v.product_id == "p1" for v in result)

    def test_returns_tuple(self, engine: ProductOpsEngine):
        _ver(engine)
        assert isinstance(engine.versions_for_product("p1"), tuple)


class TestVersionsForTenant:
    def test_empty(self, engine: ProductOpsEngine):
        assert engine.versions_for_tenant("t1") == ()

    def test_filters_correctly(self, engine: ProductOpsEngine):
        _ver(engine, "v1", tid="t1")
        _ver(engine, "v2", tid="t2")
        _ver(engine, "v3", tid="t1")
        result = engine.versions_for_tenant("t1")
        assert len(result) == 2
        assert all(v.tenant_id == "t1" for v in result)


# ===========================================================================
# 3. LIFECYCLE TRANSITIONS — deprecate, retire, end-of-life
# ===========================================================================


class TestDeprecateVersion:
    def test_active_to_deprecated(self, engine: ProductOpsEngine):
        _ver(engine)
        ms = engine.deprecate_version("v1")
        assert ms.from_status == LifecycleStatus.ACTIVE
        assert ms.to_status == LifecycleStatus.DEPRECATED
        assert ms.reason == "deprecated"
        assert engine.get_version("v1").lifecycle_status == LifecycleStatus.DEPRECATED
        assert engine.milestone_count == 1

    def test_custom_reason(self, engine: ProductOpsEngine):
        _ver(engine)
        ms = engine.deprecate_version("v1", reason="superseded by v2")
        assert ms.reason == "superseded by v2"

    def test_unknown_version_raises(self, engine: ProductOpsEngine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown version"):
            engine.deprecate_version("nope")

    def test_retired_version_raises(self, engine: ProductOpsEngine):
        _ver(engine)
        engine.retire_version("v1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal state"):
            engine.deprecate_version("v1")


class TestRetireVersion:
    def test_active_to_retired(self, engine: ProductOpsEngine):
        _ver(engine)
        ms = engine.retire_version("v1")
        assert ms.to_status == LifecycleStatus.RETIRED
        assert engine.get_version("v1").lifecycle_status == LifecycleStatus.RETIRED

    def test_deprecated_to_retired(self, engine: ProductOpsEngine):
        _ver(engine)
        engine.deprecate_version("v1")
        ms = engine.retire_version("v1")
        assert ms.from_status == LifecycleStatus.DEPRECATED
        assert ms.to_status == LifecycleStatus.RETIRED

    def test_double_retire_raises(self, engine: ProductOpsEngine):
        _ver(engine)
        engine.retire_version("v1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal state"):
            engine.retire_version("v1")


class TestEndOfLifeVersion:
    def test_active_to_eol(self, engine: ProductOpsEngine):
        _ver(engine)
        ms = engine.end_of_life_version("v1")
        assert ms.to_status == LifecycleStatus.END_OF_LIFE
        assert engine.get_version("v1").lifecycle_status == LifecycleStatus.END_OF_LIFE

    def test_eol_then_retire(self, engine: ProductOpsEngine):
        _ver(engine)
        engine.end_of_life_version("v1")
        ms = engine.retire_version("v1")
        assert ms.from_status == LifecycleStatus.END_OF_LIFE
        assert ms.to_status == LifecycleStatus.RETIRED

    def test_retired_raises(self, engine: ProductOpsEngine):
        _ver(engine)
        engine.retire_version("v1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal state"):
            engine.end_of_life_version("v1")

    def test_default_reason(self, engine: ProductOpsEngine):
        _ver(engine)
        ms = engine.end_of_life_version("v1")
        assert ms.reason == "end_of_life"


# ===========================================================================
# 4. RELEASES — create, get, status transitions, list
# ===========================================================================


class TestCreateRelease:
    def test_basic_create(self, engine: ProductOpsEngine):
        _ver(engine)
        r = _rel(engine)
        assert r.release_id == "r1"
        assert r.version_id == "v1"
        assert r.tenant_id == "t1"
        assert r.kind == ReleaseKind.MINOR
        assert r.status == ReleaseStatus.DRAFT
        assert r.target_environment == "staging"
        assert r.gate_count == 0
        assert r.gates_passed == 0
        assert engine.release_count == 1

    def test_duplicate_raises(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        with pytest.raises(RuntimeCoreInvariantError, match="already exists"):
            _rel(engine)

    def test_unknown_version_raises(self, engine: ProductOpsEngine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown version"):
            engine.create_release("r1", "nope", "t1")

    def test_retired_version_raises(self, engine: ProductOpsEngine):
        _ver(engine)
        engine.retire_version("v1")
        with pytest.raises(RuntimeCoreInvariantError, match="retired"):
            engine.create_release("r1", "v1", "t1")

    def test_custom_kind(self, engine: ProductOpsEngine):
        _ver(engine)
        r = engine.create_release("r1", "v1", "t1", kind=ReleaseKind.HOTFIX)
        assert r.kind == ReleaseKind.HOTFIX

    def test_custom_environment(self, engine: ProductOpsEngine):
        _ver(engine)
        r = engine.create_release("r1", "v1", "t1", target_environment="production")
        assert r.target_environment == "production"

    def test_major_kind(self, engine: ProductOpsEngine):
        _ver(engine)
        r = engine.create_release("r1", "v1", "t1", kind=ReleaseKind.MAJOR)
        assert r.kind == ReleaseKind.MAJOR

    def test_patch_kind(self, engine: ProductOpsEngine):
        _ver(engine)
        r = engine.create_release("r1", "v1", "t1", kind=ReleaseKind.PATCH)
        assert r.kind == ReleaseKind.PATCH

    def test_rollback_kind(self, engine: ProductOpsEngine):
        _ver(engine)
        r = engine.create_release("r1", "v1", "t1", kind=ReleaseKind.ROLLBACK)
        assert r.kind == ReleaseKind.ROLLBACK

    def test_deprecated_version_allowed(self, engine: ProductOpsEngine):
        _ver(engine)
        engine.deprecate_version("v1")
        r = engine.create_release("r1", "v1", "t1")
        assert r.release_id == "r1"

    def test_eol_version_allowed(self, engine: ProductOpsEngine):
        _ver(engine)
        engine.end_of_life_version("v1")
        r = engine.create_release("r1", "v1", "t1")
        assert r.release_id == "r1"


class TestGetRelease:
    def test_get_existing(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        r = engine.get_release("r1")
        assert r.release_id == "r1"

    def test_get_unknown_raises(self, engine: ProductOpsEngine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown release"):
            engine.get_release("nope")


class TestMarkReleaseReady:
    def test_draft_to_ready(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        r = engine.mark_release_ready("r1")
        assert r.status == ReleaseStatus.READY

    def test_completed_raises(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        engine.complete_release("r1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal state"):
            engine.mark_release_ready("r1")

    def test_failed_raises(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        engine.fail_release("r1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal state"):
            engine.mark_release_ready("r1")

    def test_rolled_back_raises(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        engine.rollback_release("rb1", "r1", "t1", "oops")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal state"):
            engine.mark_release_ready("r1")

    def test_unknown_raises(self, engine: ProductOpsEngine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown release"):
            engine.mark_release_ready("nope")


class TestStartRelease:
    def test_draft_to_in_progress(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        r = engine.start_release("r1")
        assert r.status == ReleaseStatus.IN_PROGRESS

    def test_ready_to_in_progress(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        engine.mark_release_ready("r1")
        r = engine.start_release("r1")
        assert r.status == ReleaseStatus.IN_PROGRESS

    def test_terminal_raises(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        engine.complete_release("r1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal state"):
            engine.start_release("r1")


class TestCompleteRelease:
    def test_draft_to_completed(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        r = engine.complete_release("r1")
        assert r.status == ReleaseStatus.COMPLETED

    def test_in_progress_to_completed(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        engine.start_release("r1")
        r = engine.complete_release("r1")
        assert r.status == ReleaseStatus.COMPLETED

    def test_terminal_raises(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        engine.complete_release("r1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal state"):
            engine.complete_release("r1")


class TestFailRelease:
    def test_draft_to_failed(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        r = engine.fail_release("r1")
        assert r.status == ReleaseStatus.FAILED

    def test_in_progress_to_failed(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        engine.start_release("r1")
        r = engine.fail_release("r1")
        assert r.status == ReleaseStatus.FAILED

    def test_completed_raises(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        engine.complete_release("r1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal state"):
            engine.fail_release("r1")

    def test_failed_raises(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        engine.fail_release("r1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal state"):
            engine.fail_release("r1")


class TestReleasesForVersion:
    def test_empty(self, engine: ProductOpsEngine):
        assert engine.releases_for_version("v1") == ()

    def test_filters(self, engine: ProductOpsEngine):
        _ver(engine, "v1")
        _ver(engine, "v2")
        engine.create_release("r1", "v1", "t1")
        engine.create_release("r2", "v2", "t1")
        engine.create_release("r3", "v1", "t1")
        result = engine.releases_for_version("v1")
        assert len(result) == 2
        assert all(r.version_id == "v1" for r in result)

    def test_returns_tuple(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        assert isinstance(engine.releases_for_version("v1"), tuple)


class TestReleasesForTenant:
    def test_empty(self, engine: ProductOpsEngine):
        assert engine.releases_for_tenant("t1") == ()

    def test_filters(self, engine: ProductOpsEngine):
        _ver(engine, "v1", tid="t1")
        _ver(engine, "v2", tid="t2")
        engine.create_release("r1", "v1", "t1")
        engine.create_release("r2", "v2", "t2")
        result = engine.releases_for_tenant("t1")
        assert len(result) == 1
        assert result[0].tenant_id == "t1"


# ===========================================================================
# 5. GATES — evaluate, list, all_gates_passed
# ===========================================================================


class TestEvaluateGate:
    def test_basic_pass(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        g = engine.evaluate_gate("g1", "r1", "t1", "security", True)
        assert g.gate_id == "g1"
        assert g.release_id == "r1"
        assert g.gate_name == "security"
        assert g.passed is True
        assert g.reason == "passed"
        assert engine.gate_count == 1

    def test_basic_fail(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        g = engine.evaluate_gate("g1", "r1", "t1", "security", False)
        assert g.passed is False
        assert g.reason == "failed"

    def test_custom_reason(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        g = engine.evaluate_gate("g1", "r1", "t1", "security", True, reason="all checks green")
        assert g.reason == "all checks green"

    def test_increments_gate_count(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        engine.evaluate_gate("g1", "r1", "t1", "security", True)
        r = engine.get_release("r1")
        assert r.gate_count == 1
        assert r.gates_passed == 1

    def test_failed_gate_no_increment_passed(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        engine.evaluate_gate("g1", "r1", "t1", "security", False)
        r = engine.get_release("r1")
        assert r.gate_count == 1
        assert r.gates_passed == 0

    def test_mixed_gates(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        engine.evaluate_gate("g1", "r1", "t1", "security", True)
        engine.evaluate_gate("g2", "r1", "t1", "perf", False)
        engine.evaluate_gate("g3", "r1", "t1", "qa", True)
        r = engine.get_release("r1")
        assert r.gate_count == 3
        assert r.gates_passed == 2

    def test_duplicate_raises(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        engine.evaluate_gate("g1", "r1", "t1", "security", True)
        with pytest.raises(RuntimeCoreInvariantError, match="already evaluated"):
            engine.evaluate_gate("g1", "r1", "t1", "security", True)

    def test_unknown_release_raises(self, engine: ProductOpsEngine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown release"):
            engine.evaluate_gate("g1", "nope", "t1", "security", True)

    def test_terminal_release_raises(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        engine.complete_release("r1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal state"):
            engine.evaluate_gate("g1", "r1", "t1", "security", True)

    def test_failed_release_raises(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        engine.fail_release("r1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal state"):
            engine.evaluate_gate("g1", "r1", "t1", "security", True)

    def test_rolled_back_release_raises(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        engine.rollback_release("rb1", "r1", "t1", "oops")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal state"):
            engine.evaluate_gate("g1", "r1", "t1", "security", True)


class TestGatesForRelease:
    def test_empty(self, engine: ProductOpsEngine):
        assert engine.gates_for_release("r1") == ()

    def test_filters(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine, "r1")
        _rel(engine, "r2")
        engine.evaluate_gate("g1", "r1", "t1", "sec", True)
        engine.evaluate_gate("g2", "r2", "t1", "sec", True)
        assert len(engine.gates_for_release("r1")) == 1
        assert len(engine.gates_for_release("r2")) == 1

    def test_returns_tuple(self, engine: ProductOpsEngine):
        assert isinstance(engine.gates_for_release("r1"), tuple)


class TestAllGatesPassed:
    def test_no_gates_false(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        assert engine.all_gates_passed("r1") is False

    def test_all_passed_true(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        engine.evaluate_gate("g1", "r1", "t1", "sec", True)
        engine.evaluate_gate("g2", "r1", "t1", "perf", True)
        assert engine.all_gates_passed("r1") is True

    def test_some_failed_false(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        engine.evaluate_gate("g1", "r1", "t1", "sec", True)
        engine.evaluate_gate("g2", "r1", "t1", "perf", False)
        assert engine.all_gates_passed("r1") is False

    def test_all_failed_false(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        engine.evaluate_gate("g1", "r1", "t1", "sec", False)
        assert engine.all_gates_passed("r1") is False

    def test_unknown_release_raises(self, engine: ProductOpsEngine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown release"):
            engine.all_gates_passed("nope")

    def test_single_gate_passed(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        engine.evaluate_gate("g1", "r1", "t1", "sec", True)
        assert engine.all_gates_passed("r1") is True


# ===========================================================================
# 6. PROMOTIONS
# ===========================================================================


class TestPromoteRelease:
    def test_promoted_when_all_gates_pass(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        engine.evaluate_gate("g1", "r1", "t1", "sec", True)
        p = engine.promote_release("p1", "r1", "t1", "staging", "production")
        assert p.disposition == PromotionDisposition.PROMOTED
        assert p.from_environment == "staging"
        assert p.to_environment == "production"
        assert engine.promotion_count == 1
        # release target updated
        r = engine.get_release("r1")
        assert r.target_environment == "production"

    def test_blocked_when_no_gates(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        p = engine.promote_release("p1", "r1", "t1", "staging", "prod")
        assert p.disposition == PromotionDisposition.BLOCKED
        # release target NOT updated
        r = engine.get_release("r1")
        assert r.target_environment == "staging"

    def test_blocked_when_gate_failed(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        engine.evaluate_gate("g1", "r1", "t1", "sec", True)
        engine.evaluate_gate("g2", "r1", "t1", "perf", False)
        p = engine.promote_release("p1", "r1", "t1", "staging", "prod")
        assert p.disposition == PromotionDisposition.BLOCKED

    def test_duplicate_raises(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        engine.evaluate_gate("g1", "r1", "t1", "sec", True)
        engine.promote_release("p1", "r1", "t1", "staging", "prod")
        with pytest.raises(RuntimeCoreInvariantError, match="already exists"):
            engine.promote_release("p1", "r1", "t1", "staging", "prod")

    def test_unknown_release_raises(self, engine: ProductOpsEngine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown release"):
            engine.promote_release("p1", "nope", "t1", "staging", "prod")

    def test_terminal_release_raises(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        engine.complete_release("r1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal state"):
            engine.promote_release("p1", "r1", "t1", "staging", "prod")

    def test_chained_promotions(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        engine.evaluate_gate("g1", "r1", "t1", "sec", True)
        engine.promote_release("p1", "r1", "t1", "staging", "uat")
        # after promote, target is uat; add another gate before next
        engine.promote_release("p2", "r1", "t1", "uat", "production")
        assert engine.get_release("r1").target_environment == "production"


class TestPromotionsForRelease:
    def test_empty(self, engine: ProductOpsEngine):
        assert engine.promotions_for_release("r1") == ()

    def test_filters(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine, "r1")
        _rel(engine, "r2")
        engine.evaluate_gate("g1", "r1", "t1", "sec", True)
        engine.evaluate_gate("g2", "r2", "t1", "sec", True)
        engine.promote_release("p1", "r1", "t1", "s", "p")
        engine.promote_release("p2", "r2", "t1", "s", "p")
        assert len(engine.promotions_for_release("r1")) == 1

    def test_returns_tuple(self, engine: ProductOpsEngine):
        assert isinstance(engine.promotions_for_release("r1"), tuple)


# ===========================================================================
# 7. ROLLBACKS
# ===========================================================================


class TestRollbackRelease:
    def test_basic_rollback(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        rb = engine.rollback_release("rb1", "r1", "t1", "critical bug")
        assert rb.rollback_id == "rb1"
        assert rb.status == RollbackStatus.INITIATED
        assert rb.reason == "critical bug"
        assert engine.rollback_count == 1
        # release is now rolled back
        r = engine.get_release("r1")
        assert r.status == ReleaseStatus.ROLLED_BACK

    def test_duplicate_raises(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        engine.rollback_release("rb1", "r1", "t1", "bug")
        with pytest.raises(RuntimeCoreInvariantError, match="already exists"):
            engine.rollback_release("rb1", "r1", "t1", "bug")

    def test_unknown_release_raises(self, engine: ProductOpsEngine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown release"):
            engine.rollback_release("rb1", "nope", "t1", "bug")

    def test_terminal_release_raises(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        engine.complete_release("r1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal state"):
            engine.rollback_release("rb1", "r1", "t1", "bug")

    def test_already_rolled_back_raises(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        engine.rollback_release("rb1", "r1", "t1", "bug")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal state"):
            engine.rollback_release("rb2", "r1", "t1", "bug again")


class TestCompleteRollback:
    def test_initiated_to_completed(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        engine.rollback_release("rb1", "r1", "t1", "bug")
        rb = engine.complete_rollback("rb1")
        assert rb.status == RollbackStatus.COMPLETED

    def test_completed_raises(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        engine.rollback_release("rb1", "r1", "t1", "bug")
        engine.complete_rollback("rb1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal state"):
            engine.complete_rollback("rb1")

    def test_failed_raises(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        engine.rollback_release("rb1", "r1", "t1", "bug")
        engine.fail_rollback("rb1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal state"):
            engine.complete_rollback("rb1")

    def test_unknown_raises(self, engine: ProductOpsEngine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown rollback"):
            engine.complete_rollback("nope")


class TestFailRollback:
    def test_initiated_to_failed(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        engine.rollback_release("rb1", "r1", "t1", "bug")
        rb = engine.fail_rollback("rb1")
        assert rb.status == RollbackStatus.FAILED

    def test_completed_raises(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        engine.rollback_release("rb1", "r1", "t1", "bug")
        engine.complete_rollback("rb1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal state"):
            engine.fail_rollback("rb1")

    def test_double_fail_raises(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        engine.rollback_release("rb1", "r1", "t1", "bug")
        engine.fail_rollback("rb1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal state"):
            engine.fail_rollback("rb1")


class TestRollbacksForRelease:
    def test_empty(self, engine: ProductOpsEngine):
        assert engine.rollbacks_for_release("r1") == ()

    def test_filters(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine, "r1")
        _rel(engine, "r2")
        engine.rollback_release("rb1", "r1", "t1", "bug")
        engine.rollback_release("rb2", "r2", "t1", "bug2")
        assert len(engine.rollbacks_for_release("r1")) == 1

    def test_returns_tuple(self, engine: ProductOpsEngine):
        assert isinstance(engine.rollbacks_for_release("r1"), tuple)


# ===========================================================================
# 8. ASSESSMENTS
# ===========================================================================


class TestAssessRelease:
    def test_default_scores_low_risk(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        a = engine.assess_release("a1", "r1", "t1")
        assert a.risk_level == ReleaseRiskLevel.LOW
        assert a.readiness_score == 1.0
        assert a.customer_impact_score == 0.0
        assert engine.assessment_count == 1

    def test_duplicate_raises(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        engine.assess_release("a1", "r1", "t1")
        with pytest.raises(RuntimeCoreInvariantError, match="already exists"):
            engine.assess_release("a1", "r1", "t1")

    def test_unknown_release_raises(self, engine: ProductOpsEngine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown release"):
            engine.assess_release("a1", "nope", "t1")

    # --- Risk level boundaries ---

    def test_critical_low_readiness(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        a = engine.assess_release("a1", "r1", "t1", readiness_score=0.2)
        assert a.risk_level == ReleaseRiskLevel.CRITICAL

    def test_critical_high_impact(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        a = engine.assess_release("a1", "r1", "t1", customer_impact_score=0.8)
        assert a.risk_level == ReleaseRiskLevel.CRITICAL

    def test_critical_impact_above_threshold(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        a = engine.assess_release("a1", "r1", "t1", customer_impact_score=0.9)
        assert a.risk_level == ReleaseRiskLevel.CRITICAL

    def test_high_readiness_below_half(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        a = engine.assess_release("a1", "r1", "t1", readiness_score=0.4)
        assert a.risk_level == ReleaseRiskLevel.HIGH

    def test_high_impact_at_half(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        a = engine.assess_release("a1", "r1", "t1", customer_impact_score=0.5)
        assert a.risk_level == ReleaseRiskLevel.HIGH

    def test_high_impact_above_half(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        a = engine.assess_release("a1", "r1", "t1", customer_impact_score=0.7)
        assert a.risk_level == ReleaseRiskLevel.HIGH

    def test_medium_readiness_below_0_8(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        a = engine.assess_release("a1", "r1", "t1", readiness_score=0.7)
        assert a.risk_level == ReleaseRiskLevel.MEDIUM

    def test_medium_impact_at_0_3(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        a = engine.assess_release("a1", "r1", "t1", customer_impact_score=0.3)
        assert a.risk_level == ReleaseRiskLevel.MEDIUM

    def test_low_high_readiness_low_impact(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        a = engine.assess_release("a1", "r1", "t1", readiness_score=0.9, customer_impact_score=0.1)
        assert a.risk_level == ReleaseRiskLevel.LOW

    def test_low_perfect_scores(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        a = engine.assess_release("a1", "r1", "t1", readiness_score=1.0, customer_impact_score=0.0)
        assert a.risk_level == ReleaseRiskLevel.LOW

    def test_boundary_readiness_0_3_is_high(self, engine: ProductOpsEngine):
        """readiness=0.3 is NOT <0.3 so should be HIGH (not CRITICAL)."""
        _ver(engine)
        _rel(engine)
        a = engine.assess_release("a1", "r1", "t1", readiness_score=0.3)
        assert a.risk_level == ReleaseRiskLevel.HIGH

    def test_boundary_readiness_0_5_is_medium(self, engine: ProductOpsEngine):
        """readiness=0.5 is NOT <0.5 so should be MEDIUM (not HIGH)."""
        _ver(engine)
        _rel(engine)
        a = engine.assess_release("a1", "r1", "t1", readiness_score=0.5)
        assert a.risk_level == ReleaseRiskLevel.MEDIUM

    def test_boundary_readiness_0_8_is_low(self, engine: ProductOpsEngine):
        """readiness=0.8 is NOT <0.8 so should be LOW (not MEDIUM)."""
        _ver(engine)
        _rel(engine)
        a = engine.assess_release("a1", "r1", "t1", readiness_score=0.8)
        assert a.risk_level == ReleaseRiskLevel.LOW

    def test_boundary_impact_0_29_is_low(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        a = engine.assess_release("a1", "r1", "t1", readiness_score=0.9, customer_impact_score=0.29)
        assert a.risk_level == ReleaseRiskLevel.LOW

    def test_boundary_impact_0_49_is_medium(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        a = engine.assess_release("a1", "r1", "t1", readiness_score=0.9, customer_impact_score=0.49)
        assert a.risk_level == ReleaseRiskLevel.MEDIUM

    def test_boundary_impact_0_79_is_high(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        a = engine.assess_release("a1", "r1", "t1", readiness_score=0.9, customer_impact_score=0.79)
        assert a.risk_level == ReleaseRiskLevel.HIGH


class TestAssessmentsForRelease:
    def test_empty(self, engine: ProductOpsEngine):
        assert engine.assessments_for_release("r1") == ()

    def test_filters(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine, "r1")
        _rel(engine, "r2")
        engine.assess_release("a1", "r1", "t1")
        engine.assess_release("a2", "r2", "t1")
        assert len(engine.assessments_for_release("r1")) == 1

    def test_multiple_assessments(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        engine.assess_release("a1", "r1", "t1", readiness_score=0.5)
        engine.assess_release("a2", "r1", "t1", readiness_score=0.9)
        assert len(engine.assessments_for_release("r1")) == 2


# ===========================================================================
# 9. SNAPSHOTS
# ===========================================================================


class TestReleaseSnapshot:
    def test_empty_snapshot(self, engine: ProductOpsEngine):
        snap = engine.release_snapshot("snap1")
        assert snap.snapshot_id == "snap1"
        assert snap.total_versions == 0
        assert snap.total_releases == 0
        assert snap.total_gates == 0
        assert snap.total_promotions == 0
        assert snap.total_rollbacks == 0
        assert snap.total_milestones == 0
        assert snap.total_assessments == 0
        assert snap.total_violations == 0
        assert snap.captured_at

    def test_populated_snapshot(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        engine.evaluate_gate("g1", "r1", "t1", "sec", True)
        engine.promote_release("p1", "r1", "t1", "staging", "prod")
        engine.assess_release("a1", "r1", "t1")
        snap = engine.release_snapshot("snap1")
        assert snap.total_versions == 1
        assert snap.total_releases == 1
        assert snap.total_gates == 1
        assert snap.total_promotions == 1
        assert snap.total_assessments == 1

    def test_snapshot_with_rollback(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        engine.rollback_release("rb1", "r1", "t1", "bug")
        snap = engine.release_snapshot("snap1")
        assert snap.total_rollbacks == 1

    def test_snapshot_with_milestones(self, engine: ProductOpsEngine):
        _ver(engine)
        engine.deprecate_version("v1")
        snap = engine.release_snapshot("snap1")
        assert snap.total_milestones == 1


# ===========================================================================
# 10. VIOLATIONS
# ===========================================================================


class TestDetectReleaseViolations:
    def test_no_violations_empty(self, engine: ProductOpsEngine):
        result = engine.detect_release_violations("t1")
        assert result == ()
        assert engine.violation_count == 0

    def test_failed_gate_in_progress(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        engine.evaluate_gate("g1", "r1", "t1", "sec", False)
        engine.start_release("r1")
        viols = engine.detect_release_violations("t1")
        assert len(viols) == 1
        assert viols[0].operation == "failed_gate_in_progress"
        assert engine.violation_count >= 1

    def test_no_gates_violation(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        viols = engine.detect_release_violations("t1")
        ops = [v.operation for v in viols]
        assert "no_gates" in ops

    def test_blocked_promotion_violation(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        engine.promote_release("p1", "r1", "t1", "staging", "prod")
        viols = engine.detect_release_violations("t1")
        ops = [v.operation for v in viols]
        assert "blocked_promotion" in ops

    def test_idempotent(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        v1 = engine.detect_release_violations("t1")
        v2 = engine.detect_release_violations("t1")
        # second call returns empty — already detected
        assert len(v2) == 0
        assert engine.violation_count == len(v1)

    def test_tenant_isolation(self, engine: ProductOpsEngine):
        _ver(engine, "v1", tid="t1")
        _ver(engine, "v2", tid="t2")
        engine.create_release("r1", "v1", "t1")
        engine.create_release("r2", "v2", "t2")
        viols_t1 = engine.detect_release_violations("t1")
        viols_t2 = engine.detect_release_violations("t2")
        # each tenant has its own no_gates violation
        assert all(v.tenant_id == "t1" for v in viols_t1)
        assert all(v.tenant_id == "t2" for v in viols_t2)

    def test_terminal_release_no_no_gates_violation(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        engine.complete_release("r1")
        viols = engine.detect_release_violations("t1")
        ops = [v.operation for v in viols]
        assert "no_gates" not in ops

    def test_multiple_violation_types(self, engine: ProductOpsEngine):
        _ver(engine)
        # release with no gates
        _rel(engine, "r1")
        # release in progress with failed gate
        _rel(engine, "r2")
        engine.evaluate_gate("g1", "r2", "t1", "sec", False)
        engine.start_release("r2")
        # blocked promotion on r1 (no gates)
        engine.promote_release("p1", "r1", "t1", "staging", "prod")
        viols = engine.detect_release_violations("t1")
        ops = {v.operation for v in viols}
        assert "no_gates" in ops
        assert "failed_gate_in_progress" in ops
        assert "blocked_promotion" in ops


class TestViolationsForTenant:
    def test_empty(self, engine: ProductOpsEngine):
        assert engine.violations_for_tenant("t1") == ()

    def test_filters(self, engine: ProductOpsEngine):
        _ver(engine, "v1", tid="t1")
        _ver(engine, "v2", tid="t2")
        engine.create_release("r1", "v1", "t1")
        engine.create_release("r2", "v2", "t2")
        engine.detect_release_violations("t1")
        engine.detect_release_violations("t2")
        t1_viols = engine.violations_for_tenant("t1")
        t2_viols = engine.violations_for_tenant("t2")
        assert all(v.tenant_id == "t1" for v in t1_viols)
        assert all(v.tenant_id == "t2" for v in t2_viols)


# ===========================================================================
# 11. CLOSURE REPORT
# ===========================================================================


class TestClosureReport:
    def test_empty(self, engine: ProductOpsEngine):
        cr = engine.closure_report("cr1", "t1")
        assert cr.report_id == "cr1"
        assert cr.tenant_id == "t1"
        assert cr.total_versions == 0
        assert cr.total_releases == 0
        assert cr.total_promotions == 0
        assert cr.total_rollbacks == 0
        assert cr.total_milestones == 0
        assert cr.total_violations == 0
        assert cr.closed_at

    def test_populated(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        engine.evaluate_gate("g1", "r1", "t1", "sec", True)
        engine.promote_release("p1", "r1", "t1", "staging", "prod")
        engine.deprecate_version("v1")
        cr = engine.closure_report("cr1", "t1")
        assert cr.total_versions == 1
        assert cr.total_releases == 1
        assert cr.total_promotions == 1
        assert cr.total_milestones == 1

    def test_tenant_scoped(self, engine: ProductOpsEngine):
        _ver(engine, "v1", tid="t1")
        _ver(engine, "v2", tid="t2")
        engine.create_release("r1", "v1", "t1")
        engine.create_release("r2", "v2", "t2")
        cr = engine.closure_report("cr1", "t1")
        assert cr.total_versions == 1
        assert cr.total_releases == 1

    def test_includes_rollbacks(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        engine.rollback_release("rb1", "r1", "t1", "bug")
        cr = engine.closure_report("cr1", "t1")
        assert cr.total_rollbacks == 1

    def test_includes_violations(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        engine.detect_release_violations("t1")
        cr = engine.closure_report("cr1", "t1")
        assert cr.total_violations >= 1


# ===========================================================================
# 12. STATE HASH
# ===========================================================================


class TestStateHash:
    def test_empty_hash(self, engine: ProductOpsEngine):
        h = engine.state_hash()
        assert isinstance(h, str)
        assert len(h) == 64  # sha256 hex

    def test_deterministic(self, engine: ProductOpsEngine):
        _ver(engine)
        h1 = engine.state_hash()
        h2 = engine.state_hash()
        assert h1 == h2

    def test_changes_on_version(self, engine: ProductOpsEngine):
        h1 = engine.state_hash()
        _ver(engine)
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_on_release(self, engine: ProductOpsEngine):
        _ver(engine)
        h1 = engine.state_hash()
        _rel(engine)
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_on_gate(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        h1 = engine.state_hash()
        engine.evaluate_gate("g1", "r1", "t1", "sec", True)
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_on_promotion(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        engine.evaluate_gate("g1", "r1", "t1", "sec", True)
        h1 = engine.state_hash()
        engine.promote_release("p1", "r1", "t1", "staging", "prod")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_on_rollback(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        h1 = engine.state_hash()
        engine.rollback_release("rb1", "r1", "t1", "bug")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_on_milestone(self, engine: ProductOpsEngine):
        _ver(engine)
        h1 = engine.state_hash()
        engine.deprecate_version("v1")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_on_assessment(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        h1 = engine.state_hash()
        engine.assess_release("a1", "r1", "t1")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_on_violation(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        h1 = engine.state_hash()
        engine.detect_release_violations("t1")
        h2 = engine.state_hash()
        assert h1 != h2


# ===========================================================================
# 13. PROPERTIES
# ===========================================================================


class TestProperties:
    def test_version_count(self, engine: ProductOpsEngine):
        assert engine.version_count == 0
        _ver(engine, "v1")
        assert engine.version_count == 1
        _ver(engine, "v2")
        assert engine.version_count == 2

    def test_release_count(self, engine: ProductOpsEngine):
        _ver(engine)
        assert engine.release_count == 0
        _rel(engine, "r1")
        assert engine.release_count == 1
        _rel(engine, "r2")
        assert engine.release_count == 2

    def test_gate_count(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        assert engine.gate_count == 0
        engine.evaluate_gate("g1", "r1", "t1", "sec", True)
        assert engine.gate_count == 1

    def test_promotion_count(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        assert engine.promotion_count == 0
        engine.promote_release("p1", "r1", "t1", "s", "p")
        assert engine.promotion_count == 1

    def test_rollback_count(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        assert engine.rollback_count == 0
        engine.rollback_release("rb1", "r1", "t1", "bug")
        assert engine.rollback_count == 1

    def test_milestone_count(self, engine: ProductOpsEngine):
        _ver(engine)
        assert engine.milestone_count == 0
        engine.deprecate_version("v1")
        assert engine.milestone_count == 1

    def test_assessment_count(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        assert engine.assessment_count == 0
        engine.assess_release("a1", "r1", "t1")
        assert engine.assessment_count == 1

    def test_violation_count(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        assert engine.violation_count == 0
        engine.detect_release_violations("t1")
        assert engine.violation_count >= 1


# ===========================================================================
# 14. EVENT EMISSION
# ===========================================================================


class TestEventEmission:
    def test_register_version_emits(self, spine: EventSpineEngine, engine: ProductOpsEngine):
        _ver(engine)
        assert spine.event_count > 0

    def test_create_release_emits(self, spine: EventSpineEngine, engine: ProductOpsEngine):
        _ver(engine)
        before = spine.event_count
        _rel(engine)
        assert spine.event_count > before

    def test_evaluate_gate_emits(self, spine: EventSpineEngine, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        before = spine.event_count
        engine.evaluate_gate("g1", "r1", "t1", "sec", True)
        assert spine.event_count > before

    def test_promote_release_emits(self, spine: EventSpineEngine, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        engine.evaluate_gate("g1", "r1", "t1", "sec", True)
        before = spine.event_count
        engine.promote_release("p1", "r1", "t1", "s", "p")
        assert spine.event_count > before

    def test_rollback_emits(self, spine: EventSpineEngine, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        before = spine.event_count
        engine.rollback_release("rb1", "r1", "t1", "bug")
        assert spine.event_count > before

    def test_lifecycle_transition_emits(self, spine: EventSpineEngine, engine: ProductOpsEngine):
        _ver(engine)
        before = spine.event_count
        engine.deprecate_version("v1")
        assert spine.event_count > before

    def test_assess_release_emits(self, spine: EventSpineEngine, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        before = spine.event_count
        engine.assess_release("a1", "r1", "t1")
        assert spine.event_count > before

    def test_detect_violations_emits(self, spine: EventSpineEngine, engine: ProductOpsEngine):
        before = spine.event_count
        engine.detect_release_violations("t1")
        assert spine.event_count > before

    def test_mark_ready_emits(self, spine: EventSpineEngine, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        before = spine.event_count
        engine.mark_release_ready("r1")
        assert spine.event_count > before

    def test_start_release_emits(self, spine: EventSpineEngine, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        before = spine.event_count
        engine.start_release("r1")
        assert spine.event_count > before

    def test_complete_release_emits(self, spine: EventSpineEngine, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        before = spine.event_count
        engine.complete_release("r1")
        assert spine.event_count > before

    def test_fail_release_emits(self, spine: EventSpineEngine, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        before = spine.event_count
        engine.fail_release("r1")
        assert spine.event_count > before

    def test_complete_rollback_emits(self, spine: EventSpineEngine, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        engine.rollback_release("rb1", "r1", "t1", "bug")
        before = spine.event_count
        engine.complete_rollback("rb1")
        assert spine.event_count > before

    def test_fail_rollback_emits(self, spine: EventSpineEngine, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        engine.rollback_release("rb1", "r1", "t1", "bug")
        before = spine.event_count
        engine.fail_rollback("rb1")
        assert spine.event_count > before


# ===========================================================================
# 15. IMMUTABILITY
# ===========================================================================


class TestImmutability:
    def test_version_record_frozen(self, engine: ProductOpsEngine):
        v = _ver(engine)
        with pytest.raises(AttributeError):
            v.version_id = "changed"

    def test_release_record_frozen(self, engine: ProductOpsEngine):
        _ver(engine)
        r = _rel(engine)
        with pytest.raises(AttributeError):
            r.status = ReleaseStatus.COMPLETED

    def test_gate_record_frozen(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        g = engine.evaluate_gate("g1", "r1", "t1", "sec", True)
        with pytest.raises(AttributeError):
            g.passed = False

    def test_promotion_record_frozen(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        engine.evaluate_gate("g1", "r1", "t1", "sec", True)
        p = engine.promote_release("p1", "r1", "t1", "s", "p")
        with pytest.raises(AttributeError):
            p.disposition = PromotionDisposition.BLOCKED

    def test_rollback_record_frozen(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        rb = engine.rollback_release("rb1", "r1", "t1", "bug")
        with pytest.raises(AttributeError):
            rb.status = RollbackStatus.COMPLETED

    def test_milestone_frozen(self, engine: ProductOpsEngine):
        _ver(engine)
        ms = engine.deprecate_version("v1")
        with pytest.raises(AttributeError):
            ms.reason = "changed"

    def test_assessment_frozen(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        a = engine.assess_release("a1", "r1", "t1")
        with pytest.raises(AttributeError):
            a.risk_level = ReleaseRiskLevel.CRITICAL

    def test_snapshot_frozen(self, engine: ProductOpsEngine):
        snap = engine.release_snapshot("snap1")
        with pytest.raises(AttributeError):
            snap.total_versions = 99

    def test_closure_report_frozen(self, engine: ProductOpsEngine):
        cr = engine.closure_report("cr1", "t1")
        with pytest.raises(AttributeError):
            cr.total_releases = 99


# ===========================================================================
# 16. RELEASE STATUS TRANSITION MATRIX
# ===========================================================================


class TestReleaseStatusTransitions:
    """Exhaust all valid and invalid status transition paths."""

    def test_draft_to_ready(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        r = engine.mark_release_ready("r1")
        assert r.status == ReleaseStatus.READY

    def test_draft_to_in_progress(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        r = engine.start_release("r1")
        assert r.status == ReleaseStatus.IN_PROGRESS

    def test_draft_to_completed(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        r = engine.complete_release("r1")
        assert r.status == ReleaseStatus.COMPLETED

    def test_draft_to_failed(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        r = engine.fail_release("r1")
        assert r.status == ReleaseStatus.FAILED

    def test_ready_to_in_progress(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        engine.mark_release_ready("r1")
        r = engine.start_release("r1")
        assert r.status == ReleaseStatus.IN_PROGRESS

    def test_ready_to_completed(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        engine.mark_release_ready("r1")
        r = engine.complete_release("r1")
        assert r.status == ReleaseStatus.COMPLETED

    def test_in_progress_to_completed(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        engine.start_release("r1")
        r = engine.complete_release("r1")
        assert r.status == ReleaseStatus.COMPLETED

    def test_in_progress_to_failed(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        engine.start_release("r1")
        r = engine.fail_release("r1")
        assert r.status == ReleaseStatus.FAILED

    def test_in_progress_to_rolled_back(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        engine.start_release("r1")
        engine.rollback_release("rb1", "r1", "t1", "oops")
        r = engine.get_release("r1")
        assert r.status == ReleaseStatus.ROLLED_BACK

    def test_completed_blocks_all(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        engine.complete_release("r1")
        for fn in [engine.mark_release_ready, engine.start_release,
                    engine.complete_release, engine.fail_release]:
            with pytest.raises(RuntimeCoreInvariantError, match="terminal state"):
                fn("r1")

    def test_failed_blocks_all(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        engine.fail_release("r1")
        for fn in [engine.mark_release_ready, engine.start_release,
                    engine.complete_release, engine.fail_release]:
            with pytest.raises(RuntimeCoreInvariantError, match="terminal state"):
                fn("r1")

    def test_rolled_back_blocks_all(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        engine.rollback_release("rb1", "r1", "t1", "oops")
        for fn in [engine.mark_release_ready, engine.start_release,
                    engine.complete_release, engine.fail_release]:
            with pytest.raises(RuntimeCoreInvariantError, match="terminal state"):
                fn("r1")


# ===========================================================================
# 17. MULTI-TENANT ISOLATION
# ===========================================================================


class TestMultiTenantIsolation:
    def test_versions_isolated(self, engine: ProductOpsEngine):
        _ver(engine, "v1", tid="t1")
        _ver(engine, "v2", tid="t2")
        assert len(engine.versions_for_tenant("t1")) == 1
        assert len(engine.versions_for_tenant("t2")) == 1

    def test_releases_isolated(self, engine: ProductOpsEngine):
        _ver(engine, "v1", tid="t1")
        _ver(engine, "v2", tid="t2")
        engine.create_release("r1", "v1", "t1")
        engine.create_release("r2", "v2", "t2")
        assert len(engine.releases_for_tenant("t1")) == 1
        assert len(engine.releases_for_tenant("t2")) == 1

    def test_violations_isolated(self, engine: ProductOpsEngine):
        _ver(engine, "v1", tid="t1")
        _ver(engine, "v2", tid="t2")
        engine.create_release("r1", "v1", "t1")
        engine.create_release("r2", "v2", "t2")
        engine.detect_release_violations("t1")
        engine.detect_release_violations("t2")
        assert all(v.tenant_id == "t1" for v in engine.violations_for_tenant("t1"))
        assert all(v.tenant_id == "t2" for v in engine.violations_for_tenant("t2"))

    def test_closure_reports_isolated(self, engine: ProductOpsEngine):
        _ver(engine, "v1", tid="t1")
        _ver(engine, "v2", tid="t2")
        engine.create_release("r1", "v1", "t1")
        engine.create_release("r2", "v2", "t2")
        cr1 = engine.closure_report("cr1", "t1")
        cr2 = engine.closure_report("cr2", "t2")
        assert cr1.total_versions == 1
        assert cr2.total_versions == 1
        assert cr1.total_releases == 1
        assert cr2.total_releases == 1


# ===========================================================================
# 18. GOLDEN SCENARIO 1 — Release blocked by failed assurance gate
# ===========================================================================


class TestGoldenBlockedByFailedGate:
    def test_full_scenario(self, engine: ProductOpsEngine):
        # Register version and create release
        _ver(engine, "v1", "product-a", "tenant-1", "2.0.0")
        _rel(engine, "rel-1", "v1", "tenant-1", ReleaseKind.MINOR, "staging")

        # Pass security gate
        engine.evaluate_gate("gate-sec", "rel-1", "tenant-1", "security-scan", True)

        # Fail performance gate
        engine.evaluate_gate("gate-perf", "rel-1", "tenant-1", "perf-test", False,
                             reason="latency exceeded threshold")

        # Not all gates passed
        assert engine.all_gates_passed("rel-1") is False

        # Attempt promotion — should be BLOCKED
        promo = engine.promote_release("promo-1", "rel-1", "tenant-1", "staging", "production")
        assert promo.disposition == PromotionDisposition.BLOCKED

        # Release target not updated
        assert engine.get_release("rel-1").target_environment == "staging"

        # Violation detection finds blocked promotion
        viols = engine.detect_release_violations("tenant-1")
        ops = {v.operation for v in viols}
        assert "blocked_promotion" in ops

        # Assessment shows risk
        a = engine.assess_release("assess-1", "rel-1", "tenant-1",
                                  readiness_score=0.4, customer_impact_score=0.6)
        assert a.risk_level == ReleaseRiskLevel.HIGH


# ===========================================================================
# 19. GOLDEN SCENARIO 2 — Release promoted after all gates pass
# ===========================================================================


class TestGoldenPromotedAfterGatesPass:
    def test_full_scenario(self, engine: ProductOpsEngine):
        _ver(engine, "v1", "product-b", "tenant-1", "3.0.0")
        _rel(engine, "rel-1", "v1", "tenant-1", ReleaseKind.MAJOR, "staging")

        # Pass all gates
        engine.evaluate_gate("g-sec", "rel-1", "tenant-1", "security", True)
        engine.evaluate_gate("g-perf", "rel-1", "tenant-1", "performance", True)
        engine.evaluate_gate("g-qa", "rel-1", "tenant-1", "qa", True)
        assert engine.all_gates_passed("rel-1") is True

        # Mark ready and start
        engine.mark_release_ready("rel-1")
        engine.start_release("rel-1")

        # Promote staging -> production
        promo = engine.promote_release("promo-1", "rel-1", "tenant-1", "staging", "production")
        assert promo.disposition == PromotionDisposition.PROMOTED
        assert engine.get_release("rel-1").target_environment == "production"

        # Complete release
        engine.complete_release("rel-1")
        assert engine.get_release("rel-1").status == ReleaseStatus.COMPLETED

        # Assessment shows low risk
        a = engine.assess_release("assess-1", "rel-1", "tenant-1",
                                  readiness_score=0.95, customer_impact_score=0.05)
        assert a.risk_level == ReleaseRiskLevel.LOW


# ===========================================================================
# 20. GOLDEN SCENARIO 3 — Continuity failure triggers rollback
# ===========================================================================


class TestGoldenContinuityFailureRollback:
    def test_full_scenario(self, engine: ProductOpsEngine):
        _ver(engine, "v1", "product-c", "tenant-1", "1.5.0")
        _rel(engine, "rel-1", "v1", "tenant-1", ReleaseKind.MINOR, "staging")

        # Pass gates and start release
        engine.evaluate_gate("g1", "rel-1", "tenant-1", "sec", True)
        engine.start_release("rel-1")

        # Simulate continuity failure — rollback
        rb = engine.rollback_release("rb-1", "rel-1", "tenant-1", "database migration failed")
        assert rb.status == RollbackStatus.INITIATED
        assert engine.get_release("rel-1").status == ReleaseStatus.ROLLED_BACK

        # Cannot modify release after rollback
        with pytest.raises(RuntimeCoreInvariantError, match="terminal state"):
            engine.start_release("rel-1")

        # Complete rollback
        rb_done = engine.complete_rollback("rb-1")
        assert rb_done.status == RollbackStatus.COMPLETED

        # Cannot complete again
        with pytest.raises(RuntimeCoreInvariantError, match="terminal state"):
            engine.complete_rollback("rb-1")

        # Snapshot captures state
        snap = engine.release_snapshot("snap-after-rb")
        assert snap.total_rollbacks == 1
        assert snap.total_releases == 1


# ===========================================================================
# 21. GOLDEN SCENARIO 4 — Customer-impact signal degrades assessment
# ===========================================================================


class TestGoldenCustomerImpactDegrades:
    def test_full_scenario(self, engine: ProductOpsEngine):
        _ver(engine, "v1", "product-d", "tenant-1", "4.0.0")
        _rel(engine, "rel-1", "v1", "tenant-1")

        # Initial assessment — low risk
        a1 = engine.assess_release("a-init", "rel-1", "tenant-1",
                                   readiness_score=0.95, customer_impact_score=0.1)
        assert a1.risk_level == ReleaseRiskLevel.LOW

        # Customer impact increases — medium
        a2 = engine.assess_release("a-mid", "rel-1", "tenant-1",
                                   readiness_score=0.9, customer_impact_score=0.35)
        assert a2.risk_level == ReleaseRiskLevel.MEDIUM

        # Customer impact spikes — high
        a3 = engine.assess_release("a-high", "rel-1", "tenant-1",
                                   readiness_score=0.85, customer_impact_score=0.6)
        assert a3.risk_level == ReleaseRiskLevel.HIGH

        # Critical customer impact
        a4 = engine.assess_release("a-crit", "rel-1", "tenant-1",
                                   readiness_score=0.8, customer_impact_score=0.85)
        assert a4.risk_level == ReleaseRiskLevel.CRITICAL

        # All 4 assessments recorded
        assert len(engine.assessments_for_release("rel-1")) == 4


# ===========================================================================
# 22. GOLDEN SCENARIO 5 — Deprecated product enters lifecycle milestone
# ===========================================================================


class TestGoldenDeprecatedLifecycle:
    def test_full_scenario(self, engine: ProductOpsEngine):
        _ver(engine, "v1", "product-e", "tenant-1", "1.0.0")

        # Deprecate
        ms1 = engine.deprecate_version("v1")
        assert ms1.from_status == LifecycleStatus.ACTIVE
        assert ms1.to_status == LifecycleStatus.DEPRECATED
        assert engine.get_version("v1").lifecycle_status == LifecycleStatus.DEPRECATED

        # Can still create release on deprecated version
        _rel(engine, "rel-1", "v1", "tenant-1")
        assert engine.get_release("rel-1").release_id == "rel-1"

        # End of life
        ms2 = engine.end_of_life_version("v1")
        assert ms2.from_status == LifecycleStatus.DEPRECATED
        assert ms2.to_status == LifecycleStatus.END_OF_LIFE

        # Can still create release on EOL version
        _rel(engine, "rel-2", "v1", "tenant-1")

        # Retire
        ms3 = engine.retire_version("v1")
        assert ms3.from_status == LifecycleStatus.END_OF_LIFE
        assert ms3.to_status == LifecycleStatus.RETIRED

        # Cannot create release on retired version
        with pytest.raises(RuntimeCoreInvariantError, match="retired"):
            engine.create_release("rel-3", "v1", "tenant-1")

        # Cannot transition from retired
        with pytest.raises(RuntimeCoreInvariantError, match="terminal state"):
            engine.deprecate_version("v1")

        # 3 milestones recorded
        assert engine.milestone_count == 3

        # Closure report
        cr = engine.closure_report("cr1", "tenant-1")
        assert cr.total_milestones == 3
        assert cr.total_versions == 1
        assert cr.total_releases == 2


# ===========================================================================
# 23. GOLDEN SCENARIO 6 — Replay/restore preserves release and rollback state
# ===========================================================================


class TestGoldenReplayRestore:
    def test_state_hash_reproduces(self, spine: EventSpineEngine):
        """Two engines given the same operations produce the same state hash."""
        e1 = ProductOpsEngine(spine)
        e2 = ProductOpsEngine(EventSpineEngine())

        ops = [
            lambda e: e.register_version("v1", "p1", "t1", "1.0"),
            lambda e: e.create_release("r1", "v1", "t1"),
            lambda e: e.evaluate_gate("g1", "r1", "t1", "sec", True),
            lambda e: e.evaluate_gate("g2", "r1", "t1", "perf", False),
            lambda e: e.promote_release("p1", "r1", "t1", "staging", "prod"),
            lambda e: e.rollback_release("rb1", "r1", "t1", "bug"),
            lambda e: e.complete_rollback("rb1"),
            lambda e: e.assess_release("a1", "r1", "t1", 0.5, 0.5),
            lambda e: e.deprecate_version("v1"),
        ]

        for op in ops:
            op(e1)
            op(e2)

        assert e1.state_hash() == e2.state_hash()

    def test_snapshot_after_replay(self, spine: EventSpineEngine):
        """After replaying the same ops, snapshot totals match."""
        e1 = ProductOpsEngine(spine)
        e2 = ProductOpsEngine(EventSpineEngine())

        for e in [e1, e2]:
            e.register_version("v1", "p1", "t1", "1.0")
            e.create_release("r1", "v1", "t1")
            e.evaluate_gate("g1", "r1", "t1", "sec", True)
            e.promote_release("p1", "r1", "t1", "staging", "prod")

        s1 = e1.release_snapshot("s1")
        s2 = e2.release_snapshot("s2")
        assert s1.total_versions == s2.total_versions
        assert s1.total_releases == s2.total_releases
        assert s1.total_gates == s2.total_gates
        assert s1.total_promotions == s2.total_promotions

    def test_rollback_state_preserved_across_replay(self):
        """Rollback status is preserved identically when replayed."""
        def build():
            e = ProductOpsEngine(EventSpineEngine())
            e.register_version("v1", "p1", "t1", "1.0")
            e.create_release("r1", "v1", "t1")
            e.start_release("r1")
            e.rollback_release("rb1", "r1", "t1", "failure detected")
            e.complete_rollback("rb1")
            return e

        e1 = build()
        e2 = build()
        assert e1.state_hash() == e2.state_hash()
        assert e1.get_release("r1").status == e2.get_release("r1").status == ReleaseStatus.ROLLED_BACK
        rb1 = [rb for rb in e1.rollbacks_for_release("r1")][0]
        rb2 = [rb for rb in e2.rollbacks_for_release("r1")][0]
        assert rb1.status == rb2.status == RollbackStatus.COMPLETED

    def test_violation_idempotency_across_replay(self):
        """Violations detected identically in two replayed engines."""
        def build():
            e = ProductOpsEngine(EventSpineEngine())
            e.register_version("v1", "p1", "t1", "1.0")
            e.create_release("r1", "v1", "t1")
            e.evaluate_gate("g1", "r1", "t1", "sec", False)
            e.start_release("r1")
            e.detect_release_violations("t1")
            return e

        e1 = build()
        e2 = build()
        assert e1.violation_count == e2.violation_count
        assert e1.state_hash() == e2.state_hash()


# ===========================================================================
# 24. EDGE CASES
# ===========================================================================


class TestEdgeCases:
    def test_many_versions_same_product(self, engine: ProductOpsEngine):
        for i in range(50):
            _ver(engine, f"v{i}", pid="p1", label=f"1.{i}.0")
        assert engine.version_count == 50
        assert len(engine.versions_for_product("p1")) == 50

    def test_many_releases_same_version(self, engine: ProductOpsEngine):
        _ver(engine)
        for i in range(30):
            _rel(engine, f"r{i}")
        assert engine.release_count == 30
        assert len(engine.releases_for_version("v1")) == 30

    def test_many_gates_same_release(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        for i in range(20):
            engine.evaluate_gate(f"g{i}", "r1", "t1", f"gate-{i}", True)
        assert engine.gate_count == 20
        r = engine.get_release("r1")
        assert r.gate_count == 20
        assert r.gates_passed == 20
        assert engine.all_gates_passed("r1") is True

    def test_many_assessments_different_risk(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        scores = [
            (1.0, 0.0, ReleaseRiskLevel.LOW),
            (0.7, 0.1, ReleaseRiskLevel.MEDIUM),
            (0.4, 0.2, ReleaseRiskLevel.HIGH),
            (0.2, 0.1, ReleaseRiskLevel.CRITICAL),
        ]
        for i, (r_score, c_score, expected) in enumerate(scores):
            a = engine.assess_release(f"a{i}", "r1", "t1",
                                      readiness_score=r_score,
                                      customer_impact_score=c_score)
            assert a.risk_level == expected

    def test_promote_after_blocked_with_new_gate(self, engine: ProductOpsEngine):
        """After a blocked promotion, adding a passing gate doesn't fix it
        because the failed gate is still counted."""
        _ver(engine)
        _rel(engine)
        engine.evaluate_gate("g1", "r1", "t1", "sec", False)
        p1 = engine.promote_release("p1", "r1", "t1", "staging", "prod")
        assert p1.disposition == PromotionDisposition.BLOCKED

        # Add another passing gate — still not all passed (1/2)
        engine.evaluate_gate("g2", "r1", "t1", "qa", True)
        assert engine.all_gates_passed("r1") is False

        p2 = engine.promote_release("p2", "r1", "t1", "staging", "prod")
        assert p2.disposition == PromotionDisposition.BLOCKED

    def test_rollback_preserves_gate_counts(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        engine.evaluate_gate("g1", "r1", "t1", "sec", True)
        engine.rollback_release("rb1", "r1", "t1", "oops")
        r = engine.get_release("r1")
        assert r.gate_count == 1
        assert r.gates_passed == 1

    def test_failed_rollback_does_not_change_release(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        engine.rollback_release("rb1", "r1", "t1", "oops")
        engine.fail_rollback("rb1")
        # Release is still rolled back
        r = engine.get_release("r1")
        assert r.status == ReleaseStatus.ROLLED_BACK

    def test_closure_report_different_id_same_tenant(self, engine: ProductOpsEngine):
        _ver(engine)
        cr1 = engine.closure_report("cr1", "t1")
        cr2 = engine.closure_report("cr2", "t1")
        assert cr1.report_id != cr2.report_id
        assert cr1.total_versions == cr2.total_versions

    def test_snapshot_different_id(self, engine: ProductOpsEngine):
        s1 = engine.release_snapshot("s1")
        s2 = engine.release_snapshot("s2")
        assert s1.snapshot_id != s2.snapshot_id

    def test_gate_default_reason_when_passed(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        g = engine.evaluate_gate("g1", "r1", "t1", "sec", True, reason="")
        assert g.reason == "passed"

    def test_gate_default_reason_when_failed(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine)
        g = engine.evaluate_gate("g1", "r1", "t1", "sec", False, reason="")
        assert g.reason == "failed"

    def test_promote_blocked_does_not_update_target(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine, env="staging")
        engine.evaluate_gate("g1", "r1", "t1", "sec", False)
        engine.promote_release("p1", "r1", "t1", "staging", "prod")
        assert engine.get_release("r1").target_environment == "staging"

    def test_multiple_products_multiple_tenants(self, engine: ProductOpsEngine):
        for t in ["t1", "t2", "t3"]:
            for p in ["p1", "p2"]:
                vid = f"v-{t}-{p}"
                _ver(engine, vid, pid=p, tid=t, label=f"{t}-{p}")
        assert engine.version_count == 6
        assert len(engine.versions_for_tenant("t1")) == 2
        assert len(engine.versions_for_product("p1")) == 3


# ===========================================================================
# 25. LIFECYCLE MILESTONE DETAILS
# ===========================================================================


class TestLifecycleMilestoneDetails:
    def test_milestone_has_tenant_id(self, engine: ProductOpsEngine):
        _ver(engine, tid="tenant-x")
        ms = engine.deprecate_version("v1")
        assert ms.tenant_id == "tenant-x"

    def test_milestone_has_version_id(self, engine: ProductOpsEngine):
        _ver(engine)
        ms = engine.deprecate_version("v1")
        assert ms.version_id == "v1"

    def test_milestone_recorded_at(self, engine: ProductOpsEngine):
        _ver(engine)
        ms = engine.deprecate_version("v1")
        assert ms.recorded_at

    def test_milestone_id_deterministic(self, engine: ProductOpsEngine):
        _ver(engine)
        ms = engine.deprecate_version("v1")
        assert ms.milestone_id  # non-empty


# ===========================================================================
# 26. COMBINED FLOW TESTS
# ===========================================================================


class TestCombinedFlows:
    def test_full_release_lifecycle(self, engine: ProductOpsEngine):
        """Version -> Release -> Gates -> Promote -> Complete -> Snapshot."""
        _ver(engine, "v1", "prod-1", "t1", "5.0.0")
        _rel(engine, "r1", "v1", "t1", ReleaseKind.MAJOR, "dev")

        # Gates
        engine.evaluate_gate("g1", "r1", "t1", "unit-tests", True)
        engine.evaluate_gate("g2", "r1", "t1", "integration", True)
        engine.evaluate_gate("g3", "r1", "t1", "security", True)
        assert engine.all_gates_passed("r1") is True

        # Progress
        engine.mark_release_ready("r1")
        engine.start_release("r1")

        # Promote through environments
        engine.promote_release("p1", "r1", "t1", "dev", "staging")
        assert engine.get_release("r1").target_environment == "staging"
        engine.promote_release("p2", "r1", "t1", "staging", "production")
        assert engine.get_release("r1").target_environment == "production"

        # Complete
        engine.complete_release("r1")
        assert engine.get_release("r1").status == ReleaseStatus.COMPLETED

        # Assess
        engine.assess_release("a1", "r1", "t1", 0.95, 0.05)

        # Snapshot
        snap = engine.release_snapshot("snap-final")
        assert snap.total_versions == 1
        assert snap.total_releases == 1
        assert snap.total_gates == 3
        assert snap.total_promotions == 2
        assert snap.total_assessments == 1

        # State hash stable
        h1 = engine.state_hash()
        h2 = engine.state_hash()
        assert h1 == h2

    def test_failed_release_then_new_release(self, engine: ProductOpsEngine):
        """Fail a release, create a new one for the same version."""
        _ver(engine)
        _rel(engine, "r1")
        engine.start_release("r1")
        engine.fail_release("r1")

        # New release for same version
        r2 = engine.create_release("r2", "v1", "t1")
        assert r2.status == ReleaseStatus.DRAFT
        assert engine.release_count == 2

    def test_rollback_then_new_release(self, engine: ProductOpsEngine):
        """Roll back, then create a new release."""
        _ver(engine)
        _rel(engine, "r1")
        engine.start_release("r1")
        engine.rollback_release("rb1", "r1", "t1", "crashed")
        engine.complete_rollback("rb1")

        r2 = engine.create_release("r2", "v1", "t1")
        assert r2.status == ReleaseStatus.DRAFT

    def test_version_with_multiple_releases_different_states(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine, "r1")
        _rel(engine, "r2")
        _rel(engine, "r3")

        engine.complete_release("r1")
        engine.fail_release("r2")
        engine.start_release("r3")

        assert engine.get_release("r1").status == ReleaseStatus.COMPLETED
        assert engine.get_release("r2").status == ReleaseStatus.FAILED
        assert engine.get_release("r3").status == ReleaseStatus.IN_PROGRESS

    def test_detect_violations_after_mixed_operations(self, engine: ProductOpsEngine):
        _ver(engine)
        # r1: no gates, not terminal
        _rel(engine, "r1")
        # r2: in progress with failed gate
        _rel(engine, "r2")
        engine.evaluate_gate("g1", "r2", "t1", "sec", False)
        engine.start_release("r2")
        # r3: completed (terminal, should not show no_gates)
        _rel(engine, "r3")
        engine.complete_release("r3")

        viols = engine.detect_release_violations("t1")
        ops = {v.operation for v in viols}
        assert "no_gates" in ops  # from r1
        assert "failed_gate_in_progress" in ops  # from r2

        # r3 is completed, so no no_gates violation for it
        r3_viols = [v for v in viols if v.release_id == "r3"]
        assert len(r3_viols) == 0

    def test_promotion_chain_with_assessment(self, engine: ProductOpsEngine):
        _ver(engine)
        _rel(engine, env="dev")
        engine.evaluate_gate("g1", "r1", "t1", "smoke", True)

        # Promote dev -> staging
        p1 = engine.promote_release("p1", "r1", "t1", "dev", "staging")
        assert p1.disposition == PromotionDisposition.PROMOTED
        a1 = engine.assess_release("a1", "r1", "t1", 0.85, 0.2)
        assert a1.risk_level == ReleaseRiskLevel.LOW

        # Promote staging -> prod
        p2 = engine.promote_release("p2", "r1", "t1", "staging", "prod")
        assert p2.disposition == PromotionDisposition.PROMOTED
        assert engine.get_release("r1").target_environment == "prod"
