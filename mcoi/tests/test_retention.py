"""Tests for retention contracts and evaluator."""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.retention import (
    ArtifactClass,
    PruneCandidate,
    PruneResult,
    PruneStatus,
    RetentionPolicy,
    RetentionStatus,
)
from mcoi_runtime.core.retention import RetentionEvaluator


def _policy(artifact_class=ArtifactClass.TRACE, max_age=30, max_count=100, compliance=False):
    return RetentionPolicy(
        policy_id=f"pol-{artifact_class.value}",
        artifact_class=artifact_class,
        max_age_days=max_age,
        max_count=max_count,
        compliance_hold=compliance,
    )


def _candidate(aid="art-1", cls=ArtifactClass.TRACE, age=10, referenced=False, compliance=False):
    return PruneCandidate(
        artifact_id=aid,
        artifact_class=cls,
        age_days=age,
        is_referenced=referenced,
        compliance_hold=compliance,
    )


class TestRetentionPolicy:
    def test_valid(self):
        p = _policy()
        assert p.max_age_days == 30

    def test_negative_age_rejected(self):
        with pytest.raises(ValueError):
            RetentionPolicy(policy_id="p", artifact_class=ArtifactClass.TRACE, max_age_days=-1, max_count=10)


class TestRetentionEvaluator:
    def test_within_bounds_kept(self):
        ev = RetentionEvaluator()
        ev.set_policy(_policy(max_age=30, max_count=100))
        status = ev.evaluate((_candidate(age=10),))
        assert status.pruned_count == 0
        assert status.skipped_count == 1

    def test_age_exceeded_pruned(self):
        ev = RetentionEvaluator()
        ev.set_policy(_policy(max_age=30))
        status = ev.evaluate((_candidate(age=60),))
        assert status.pruned_count == 1
        assert status.results[0].status is PruneStatus.PRUNED
        assert status.results[0].reason == "age exceeds retention limit"
        assert "60" not in status.results[0].reason
        assert "30" not in status.results[0].reason

    def test_compliance_hold_never_pruned(self):
        ev = RetentionEvaluator()
        ev.set_policy(_policy(max_age=1))
        status = ev.evaluate((_candidate(age=365, compliance=True),))
        assert status.pruned_count == 0
        assert status.results[0].status is PruneStatus.SKIPPED_COMPLIANCE

    def test_referenced_never_pruned(self):
        ev = RetentionEvaluator()
        ev.set_policy(_policy(max_age=1))
        status = ev.evaluate((_candidate(age=365, referenced=True),))
        assert status.pruned_count == 0
        assert status.results[0].status is PruneStatus.SKIPPED_REFERENCED

    def test_policy_compliance_hold(self):
        ev = RetentionEvaluator()
        ev.set_policy(_policy(max_age=1, compliance=True))
        status = ev.evaluate((_candidate(age=365),))
        assert status.pruned_count == 0
        assert status.results[0].status is PruneStatus.SKIPPED_COMPLIANCE

    def test_no_policy_skipped(self):
        ev = RetentionEvaluator()
        # No policy set for REPLAY
        status = ev.evaluate((_candidate(cls=ArtifactClass.REPLAY, age=999),))
        assert status.pruned_count == 0
        assert status.results[0].reason == "no retention policy"
        assert "replay" not in status.results[0].reason.lower()

    def test_count_exceeded_prunes_oldest(self):
        ev = RetentionEvaluator()
        ev.set_policy(_policy(max_age=0, max_count=2))
        candidates = (
            _candidate("old", age=30),
            _candidate("mid", age=20),
            _candidate("new", age=10),
        )
        status = ev.evaluate(candidates)
        assert status.pruned_count == 1
        pruned_ids = [r.artifact_id for r in status.results if r.status is PruneStatus.PRUNED]
        assert "old" in pruned_ids
        pruned = [r for r in status.results if r.status is PruneStatus.PRUNED][0]
        assert pruned.reason == "count exceeds retention limit"
        assert "3" not in pruned.reason
        assert "2" not in pruned.reason

    def test_mixed_classes(self):
        ev = RetentionEvaluator()
        ev.set_policy(_policy(ArtifactClass.TRACE, max_age=10))
        ev.set_policy(_policy(ArtifactClass.REPLAY, max_age=5))
        candidates = (
            _candidate("t1", ArtifactClass.TRACE, age=15),
            _candidate("r1", ArtifactClass.REPLAY, age=3),
        )
        status = ev.evaluate(candidates)
        assert status.pruned_count == 1  # Only trace exceeds
        assert status.results[0].status is PruneStatus.PRUNED  # trace
        assert status.results[1].status is not PruneStatus.PRUNED  # replay within bounds

    def test_empty_candidates(self):
        ev = RetentionEvaluator()
        status = ev.evaluate(())
        assert status.evaluated_count == 0
        assert status.pruned_count == 0

    def test_deterministic_for_same_inputs(self):
        ev = RetentionEvaluator()
        ev.set_policy(_policy(max_age=5))
        candidates = (
            _candidate("a", age=10),
            _candidate("b", age=3),
        )
        s1 = ev.evaluate(candidates)
        s2 = ev.evaluate(candidates)
        assert s1.pruned_count == s2.pruned_count
        for r1, r2 in zip(s1.results, s2.results):
            assert r1.status == r2.status
