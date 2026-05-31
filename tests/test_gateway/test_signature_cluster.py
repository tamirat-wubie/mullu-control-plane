"""Tests for cross-signature clustering."""

from __future__ import annotations

import pytest

from gateway.candidate_ledger import CandidateLedger, CandidateScore
from gateway.problem_signature import ProblemMetric, ProblemSignature
from gateway.signature_cluster import (
    SignatureClusterIndex,
    signature_similarity,
)


def _sig(
    problem_id: str,
    *,
    domain: str = "document_verification",
    goal: str = "detect duplicate invoices before payment",
    metrics: tuple[str, ...] = ("f1_score", "precision"),
    families: tuple[str, ...] = ("rule_based", "graph_match"),
    risk: str = "medium",
    budget: float = 100.0,
) -> ProblemSignature:
    return ProblemSignature(
        problem_id=problem_id,
        domain=domain,
        goal=goal,
        inputs=("records",),
        constraints=(),
        risk=risk,
        metrics=tuple(
            ProblemMetric(metric_id=m, metric_kind="success", direction="maximize")
            for m in metrics
        ),
        required_evidence=(),
        budget_units=budget,
        timeout_seconds=1.0,
        allowed_method_families=families,
        baseline_method_family=families[0] if families else "",
    )


_DUP_A = _sig("dup.v1")
_DUP_B = _sig("dup.v2", budget=200.0)  # same problem class, different hash
_DUP_C = _sig("dup.v3", families=("rule_based",))  # related but a bit less so
_SCHED = _sig(
    "sched.v1",
    domain="engineering_puzzle",
    goal="schedule tasks to meet deadlines",
    metrics=("on_time_rate",),
    families=("search_planner", "constraint_solver"),
)


def test_similarity_identical_is_one_and_symmetric():
    assert signature_similarity(_DUP_A, _DUP_A) == 1.0
    idx = SignatureClusterIndex()
    assert idx.similarity(_DUP_A, _DUP_B) == idx.similarity(_DUP_B, _DUP_A)


def test_variant_signatures_are_related_unrelated_ones_are_not():
    idx = SignatureClusterIndex()
    # Same domain/goal/metrics/families, different hash -> identical features.
    assert idx.similarity(_DUP_A, _DUP_B) == 1.0
    # Different domain/goal/metrics/families -> below threshold.
    assert idx.similarity(_DUP_A, _SCHED) < idx._threshold


def test_related_excludes_self_and_sorts_by_score():
    idx = SignatureClusterIndex()
    idx.add_all((_DUP_A, _DUP_B, _DUP_C, _SCHED))
    related = idx.related(_DUP_A)
    ids = [sig.problem_id for sig, _ in related]
    # _DUP_A excluded (same hash); _SCHED below threshold; B and C present.
    assert "dup.v1" not in ids
    assert "sched.v1" not in ids
    assert set(ids) == {"dup.v2", "dup.v3"}
    # B (identical features, 1.0) ranks ahead of C (fewer shared families).
    assert ids[0] == "dup.v2"
    scores = [score for _, score in related]
    assert scores == sorted(scores, reverse=True)


def test_clusters_group_problem_classes():
    idx = SignatureClusterIndex()
    idx.add_all((_DUP_A, _DUP_B, _SCHED))
    clusters = idx.clusters()
    by_size = sorted(clusters, key=len)
    assert len(by_size) == 2
    assert by_size[0] == frozenset({_SCHED.signature_hash})  # the singleton
    assert by_size[1] == frozenset({_DUP_A.signature_hash, _DUP_B.signature_hash})


def test_prior_winning_families_reads_evidence_from_related_signatures():
    idx = SignatureClusterIndex()
    idx.add_all((_DUP_B, _SCHED))  # _DUP_A is the new (unregistered) query
    ledger = CandidateLedger()
    # A winner recorded under the related signature _DUP_B.
    ledger.record(
        signature_hash=_DUP_B.signature_hash,
        problem_id=_DUP_B.problem_id,
        candidate_pipeline_id="pipe",
        method_families=("graph_match",),
        outcome="passed",
        scores=(CandidateScore(metric_id="f1_score", value=0.9, direction="maximize"),),
        baseline_delta={"f1_score": 0.3},
        run_seed="s1",
    )
    tally = idx.prior_winning_families(_DUP_A, ledger)
    assert tally == {"graph_match": 1}


def test_prior_winning_families_ignores_unrelated_signatures():
    idx = SignatureClusterIndex()
    idx.add(_SCHED)  # unrelated to _DUP_A
    ledger = CandidateLedger()
    ledger.record(
        signature_hash=_SCHED.signature_hash,
        problem_id=_SCHED.problem_id,
        candidate_pipeline_id="pipe",
        method_families=("constraint_solver",),
        outcome="passed",
        scores=(CandidateScore(metric_id="on_time_rate", value=1.0, direction="maximize"),),
        baseline_delta={"on_time_rate": 0.5},
        run_seed="s1",
    )
    assert idx.prior_winning_families(_DUP_A, ledger) == {}


def test_threshold_must_be_in_range():
    with pytest.raises(ValueError, match="threshold_must_be_between"):
        SignatureClusterIndex(threshold=1.5)


def test_index_has_no_promotion_surface():
    idx = SignatureClusterIndex()
    for attr in ("promote", "install", "certify", "deploy", "register_capability", "run", "record"):
        assert not hasattr(idx, attr)
