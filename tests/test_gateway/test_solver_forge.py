"""Gateway solver-forge tests.

Purpose: verify the Problem Signature → Candidate Composer → Comparison Ledger
    triple that closes the capability-forge loop.
Governance scope: signature validation, append-only ledger semantics, fair
    composition (same conditions across candidates), baseline-required
    winner claims, negative-result preservation, and promotion isolation
    (composer never mutates the capability registry).
Invariants tested:
  - Signatures hash deterministically; equal-content signatures share a hash.
  - Non-low risk signatures reject missing budget/timeout.
  - Physical risk requires physical-safety evidence.
  - Append-only ledger rejects duplicate record hashes.
  - Negative results are first-class records.
  - Composer runs every admissible candidate under the same seed for the same
    pipeline; baseline_delta is computed against the recorded baseline.
  - Winners are only claimed when baseline_delta on the primary metric beats
    the baseline; otherwise a candidate is *not* a winner even if it passed.
  - Composer never promotes — no maturity, registry, or certification mutation.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from gateway.candidate_composer import (
    CandidateComposer,
    CandidateEvaluation,
    CandidatePipeline,
    MethodCapsule,
)
from gateway.candidate_ledger import (
    CandidateLedger,
    CandidateScore,
    InMemoryCandidateLedgerStore,
    JsonFileCandidateLedgerStore,
)
from gateway.problem_signature import (
    ProblemEvidenceRequirement,
    ProblemMetric,
    ProblemSignature,
    compute_signature_hash,
    signature_from_mapping,
)


def _success_metric(metric_id: str = "precision", direction: str = "maximize") -> ProblemMetric:
    return ProblemMetric(
        metric_id=metric_id,
        metric_kind="success",
        direction=direction,
        threshold=0.5,
        description=f"{metric_id} success criterion",
    )


def _signature(
    *,
    risk: str = "low",
    metrics: tuple[ProblemMetric, ...] = (),
    required_evidence: tuple[ProblemEvidenceRequirement, ...] = (),
    allowed: tuple[str, ...] = (),
    forbidden: tuple[str, ...] = (),
    baseline: str = "rule_based",
    budget: float = 0.0,
    timeout: float = 0.0,
) -> ProblemSignature:
    if risk != "low":
        budget = budget or 100.0
        timeout = timeout or 5.0
    return ProblemSignature(
        problem_id="invoice_duplicate_detection.v1",
        domain="finance_ops",
        goal="detect duplicate invoice before payment",
        inputs=("invoice", "vendor_record", "payment_history"),
        constraints=("no payment decision without vendor match",),
        risk=risk,
        metrics=metrics or (_success_metric(),),
        required_evidence=required_evidence,
        budget_units=budget,
        timeout_seconds=timeout,
        allowed_method_families=allowed,
        forbidden_method_families=forbidden,
        baseline_method_family=baseline,
    )


# --- Problem signature -------------------------------------------------------


def test_signature_hash_is_deterministic_for_equal_content() -> None:
    a = _signature()
    b = _signature()
    assert a.signature_hash == b.signature_hash
    assert a.signature_hash == compute_signature_hash(a)


def test_signature_rejects_non_low_risk_without_budget_or_timeout() -> None:
    with pytest.raises(ValueError, match="non_low_risk_requires_explicit_budget_and_timeout"):
        ProblemSignature(
            problem_id="p",
            domain="d",
            goal="g",
            inputs=(),
            constraints=(),
            risk="medium",
            metrics=(_success_metric(),),
            required_evidence=(),
            budget_units=0.0,
            timeout_seconds=0.0,
            baseline_method_family="rule_based",
        )


def test_signature_rejects_physical_risk_without_physical_safety_evidence() -> None:
    with pytest.raises(ValueError, match="physical_risk_requires_physical_safety_evidence"):
        _signature(risk="physical", required_evidence=())


def test_signature_accepts_physical_risk_with_physical_safety_evidence() -> None:
    evidence = (
        ProblemEvidenceRequirement(
            requirement_id="phys-1",
            evidence_type="physical_safety",
            description="actuator simulation receipt",
        ),
    )
    signature = _signature(risk="physical", required_evidence=evidence)
    assert signature.risk == "physical"
    assert signature.signature_hash


def test_signature_rejects_overlapping_allowed_and_forbidden_families() -> None:
    with pytest.raises(ValueError, match="method_family_in_both_lists"):
        _signature(allowed=("rule_based",), forbidden=("rule_based",))


def test_signature_rejects_baseline_in_forbidden_list() -> None:
    with pytest.raises(ValueError, match="baseline_method_family_in_forbidden_list"):
        _signature(forbidden=("rule_based",), baseline="rule_based")


def test_signature_requires_at_least_one_success_metric() -> None:
    failure_only = (
        ProblemMetric(
            metric_id="error_rate",
            metric_kind="failure",
            direction="minimize",
        ),
    )
    with pytest.raises(ValueError, match="at_least_one_success_metric_required"):
        _signature(metrics=failure_only)


def test_signature_round_trips_through_mapping() -> None:
    signature = _signature()
    payload = {
        "problem_id": signature.problem_id,
        "domain": signature.domain,
        "goal": signature.goal,
        "inputs": list(signature.inputs),
        "constraints": list(signature.constraints),
        "risk": signature.risk,
        "metrics": [
            {
                "metric_id": m.metric_id,
                "metric_kind": m.metric_kind,
                "direction": m.direction,
                "threshold": m.threshold,
                "description": m.description,
            }
            for m in signature.metrics
        ],
        "required_evidence": [],
        "budget_units": signature.budget_units,
        "timeout_seconds": signature.timeout_seconds,
        "allowed_method_families": list(signature.allowed_method_families),
        "forbidden_method_families": list(signature.forbidden_method_families),
        "baseline_method_family": signature.baseline_method_family,
        "signature_hash": signature.signature_hash,
    }
    restored = signature_from_mapping(payload)
    assert restored.signature_hash == signature.signature_hash


# --- Candidate ledger --------------------------------------------------------


def _make_ledger() -> CandidateLedger:
    return CandidateLedger(InMemoryCandidateLedgerStore())


def test_ledger_rejects_duplicate_record_hash() -> None:
    ledger = _make_ledger()
    ledger.record(
        signature_hash="sig",
        problem_id="p",
        candidate_pipeline_id="pipe-1",
        method_families=("rule_based",),
        outcome="passed",
        scores=(CandidateScore(metric_id="precision", value=0.9, direction="maximize"),),
        baseline_delta={},
        run_seed="seed-1",
        is_baseline=True,
    )
    with pytest.raises(ValueError, match="duplicate_record_hash"):
        ledger.record(
            signature_hash="sig",
            problem_id="p",
            candidate_pipeline_id="pipe-1",
            method_families=("rule_based",),
            outcome="passed",
            scores=(CandidateScore(metric_id="precision", value=0.9, direction="maximize"),),
            baseline_delta={},
            run_seed="seed-1",
            is_baseline=True,
        )


def test_ledger_preserves_negative_results_alongside_winners() -> None:
    ledger = _make_ledger()
    ledger.record(
        signature_hash="sig",
        problem_id="p",
        candidate_pipeline_id="baseline",
        method_families=("rule_based",),
        outcome="passed",
        scores=(CandidateScore(metric_id="precision", value=0.5, direction="maximize"),),
        baseline_delta={},
        run_seed="seed-base",
        is_baseline=True,
    )
    ledger.record(
        signature_hash="sig",
        problem_id="p",
        candidate_pipeline_id="winner",
        method_families=("graph_match",),
        outcome="passed",
        scores=(CandidateScore(metric_id="precision", value=0.8, direction="maximize"),),
        baseline_delta={"precision": 0.3},
        run_seed="seed-win",
    )
    ledger.record(
        signature_hash="sig",
        problem_id="p",
        candidate_pipeline_id="loser",
        method_families=("llm_only",),
        outcome="failed",
        scores=(CandidateScore(metric_id="precision", value=0.2, direction="maximize"),),
        baseline_delta={"precision": -0.3},
        run_seed="seed-lose",
        failure_modes=("hallucinated_vendor",),
    )

    negatives = ledger.negative_results_for("sig")
    assert len(negatives) == 1
    assert negatives[0].candidate_pipeline_id == "loser"
    assert negatives[0].failure_modes == ("hallucinated_vendor",)

    winners = ledger.winners_for("sig", primary_metric_id="precision")
    assert len(winners) == 1
    assert winners[0].candidate_pipeline_id == "winner"


def test_ledger_winners_excludes_candidates_without_baseline_delta() -> None:
    ledger = _make_ledger()
    ledger.record(
        signature_hash="sig",
        problem_id="p",
        candidate_pipeline_id="lonely-passer",
        method_families=("graph_match",),
        outcome="passed",
        scores=(CandidateScore(metric_id="precision", value=0.9, direction="maximize"),),
        baseline_delta={},
        run_seed="seed-lonely",
    )
    assert ledger.winners_for("sig", primary_metric_id="precision") == ()


def test_json_file_ledger_persists_records(tmp_path: Path) -> None:
    path = tmp_path / "ledger.json"
    store = JsonFileCandidateLedgerStore(path)
    ledger = CandidateLedger(store)
    ledger.record(
        signature_hash="sig",
        problem_id="p",
        candidate_pipeline_id="pipe-1",
        method_families=("rule_based",),
        outcome="passed",
        scores=(CandidateScore(metric_id="precision", value=0.9, direction="maximize"),),
        baseline_delta={},
        run_seed="seed-1",
        is_baseline=True,
    )
    reread = CandidateLedger(JsonFileCandidateLedgerStore(path))
    assert len(reread.for_signature("sig")) == 1


# --- Composer ---------------------------------------------------------------


def _capsule(
    method_family: str,
    *,
    capsule_id: str | None = None,
    risk_ceiling: str = "low",
) -> MethodCapsule:
    return MethodCapsule(
        capsule_id=capsule_id or f"capsule:{method_family}",
        method_family=method_family,
        declared_inputs=("invoice",),
        declared_outputs=("duplicate_flag",),
        declared_assumptions=(),
        declared_failure_modes=(),
        risk_ceiling=risk_ceiling,
    )


def _make_evaluator(
    scores_by_family: dict[str, float],
    *,
    outcomes_by_family: dict[str, str] | None = None,
):
    seeds_seen: dict[str, str] = {}

    def evaluator(signature, pipeline, seed):
        seeds_seen[pipeline.pipeline_id] = seed
        family = pipeline.method_families[0]
        outcome = (outcomes_by_family or {}).get(family, "passed")
        return CandidateEvaluation(
            outcome=outcome,
            scores=(
                CandidateScore(
                    metric_id="precision",
                    value=scores_by_family[family],
                    direction="maximize",
                ),
            ),
            failure_modes=("simulated",) if outcome != "passed" else (),
            cost_units=1.0,
            duration_seconds=0.01,
        )

    return evaluator, seeds_seen


def test_composer_runs_baseline_and_candidates_under_same_seed_per_pipeline() -> None:
    ledger = _make_ledger()
    composer = CandidateComposer(
        ledger,
        capsules=(
            _capsule("rule_based"),
            _capsule("graph_match"),
            _capsule("llm_only"),
        ),
    )
    evaluator, seeds_seen = _make_evaluator(
        {"rule_based": 0.5, "graph_match": 0.8, "llm_only": 0.6}
    )
    signature = _signature()

    report = composer.run(signature, evaluator)

    # Each pipeline must receive the same deterministic seed across runs.
    composer2 = CandidateComposer(
        CandidateLedger(InMemoryCandidateLedgerStore()),
        capsules=(
            _capsule("rule_based"),
            _capsule("graph_match"),
            _capsule("llm_only"),
        ),
    )
    evaluator2, seeds_seen2 = _make_evaluator(
        {"rule_based": 0.5, "graph_match": 0.8, "llm_only": 0.6}
    )
    composer2.run(signature, evaluator2)

    assert seeds_seen == seeds_seen2
    assert report.baseline_record_hash
    assert len(report.candidate_record_hashes) == 2


def test_composer_marks_only_beating_candidates_as_winners() -> None:
    ledger = _make_ledger()
    composer = CandidateComposer(
        ledger,
        capsules=(
            _capsule("rule_based"),
            _capsule("graph_match"),
            _capsule("llm_only"),
        ),
    )
    evaluator, _ = _make_evaluator(
        {"rule_based": 0.5, "graph_match": 0.8, "llm_only": 0.4}
    )
    report = composer.run(_signature(), evaluator)

    winners = ledger.winners_for(report.signature_hash, primary_metric_id="precision")
    assert {w.method_families[0] for w in winners} == {"graph_match"}
    assert len(report.winner_record_hashes) == 1


def test_composer_preserves_failed_candidates_in_ledger() -> None:
    ledger = _make_ledger()
    composer = CandidateComposer(
        ledger,
        capsules=(
            _capsule("rule_based"),
            _capsule("graph_match"),
            _capsule("llm_only"),
        ),
    )
    evaluator, _ = _make_evaluator(
        {"rule_based": 0.5, "graph_match": 0.8, "llm_only": 0.9},
        outcomes_by_family={"llm_only": "failed"},
    )
    report = composer.run(_signature(), evaluator)

    negatives = ledger.negative_results_for(report.signature_hash)
    assert any(n.method_families == ("llm_only",) for n in negatives)
    # llm_only had the highest raw score but failed — must not be a winner.
    winner_hashes = {h for h in report.winner_record_hashes}
    for negative in negatives:
        assert negative.record_hash not in winner_hashes


def test_composer_skips_capsules_outside_admissible_set() -> None:
    ledger = _make_ledger()
    composer = CandidateComposer(
        ledger,
        capsules=(
            _capsule("rule_based"),
            _capsule("graph_match"),
            _capsule("forbidden_family"),
        ),
    )
    evaluator, _ = _make_evaluator(
        {"rule_based": 0.5, "graph_match": 0.8, "forbidden_family": 0.99}
    )
    signature = _signature(forbidden=("forbidden_family",))
    report = composer.run(signature, evaluator)
    assert "capsule:forbidden_family" in report.skipped_capsule_ids
    assert report.skipped_reasons["capsule:forbidden_family"] == "method_family_not_admissible"


def test_composer_skips_capsules_below_risk_ceiling() -> None:
    ledger = _make_ledger()
    composer = CandidateComposer(
        ledger,
        capsules=(
            _capsule("rule_based", risk_ceiling="high"),
            _capsule("graph_match", risk_ceiling="low"),
        ),
    )
    evaluator, _ = _make_evaluator({"rule_based": 0.5, "graph_match": 0.9})
    signature = _signature(
        risk="high",
        budget=100.0,
        timeout=5.0,
    )
    report = composer.run(signature, evaluator)
    assert "capsule:graph_match" in report.skipped_capsule_ids
    assert report.skipped_reasons["capsule:graph_match"] == "risk_ceiling_below_signature_risk"


def test_composer_emits_no_winners_without_baseline_capsule() -> None:
    ledger = _make_ledger()
    composer = CandidateComposer(
        ledger,
        capsules=(_capsule("graph_match"), _capsule("llm_only")),
    )
    evaluator, _ = _make_evaluator({"graph_match": 0.8, "llm_only": 0.7})
    report = composer.run(_signature(), evaluator)
    assert report.baseline_record_hash == ""
    assert report.winner_record_hashes == ()
    assert "baseline_method_family declared on signature but no matching capsule" in report.notes


def test_composer_never_mutates_capability_registry() -> None:
    """The composer's surface is the ledger and the report.

    The capability registry, maturity ladder, and certification status all
    live elsewhere; this test asserts that nothing the composer exposes can
    be used to install or promote a capability.
    """
    ledger = _make_ledger()
    composer = CandidateComposer(
        ledger,
        capsules=(_capsule("rule_based"), _capsule("graph_match")),
    )
    evaluator, _ = _make_evaluator({"rule_based": 0.5, "graph_match": 0.9})
    report = composer.run(_signature(), evaluator)

    public_attrs = {name for name in dir(composer) if not name.startswith("_")}
    forbidden = {"install", "promote", "certify", "deploy", "register_capability"}
    assert public_attrs.isdisjoint(forbidden)

    report_attrs = {name for name in dir(report) if not name.startswith("_")}
    assert report_attrs.isdisjoint(forbidden)
