"""Tests for the deployment-gate reference benchmark (workflow_automation)."""

from __future__ import annotations

from gateway.candidate_composer import CandidatePipeline
from gateway.solver_forge_benchmarks import (
    DEPLOY_FIXTURE,
    DEPLOYMENT_GATE_SIGNATURE,
    _gate_metrics,
    deployment_evaluator,
    gate_safety_policy,
    gate_tests_only,
    gate_throughput,
    get_benchmark,
    list_benchmarks,
    run_benchmark,
)
from gateway.solver_forge_bridge import forge_input_for_winner, is_winner


def _pipeline_for(capsule_id: str) -> CandidatePipeline:
    return CandidatePipeline(
        pipeline_id=f"pipeline:{capsule_id}",
        method_families=("x",),
        capsule_ids=(capsule_id,),
    )


def _score_of(run, metric_id: str) -> float:
    return next(s.value for s in run.scores if s.metric_id == metric_id)


def _preds(gate):
    return {req.id: gate(req) for req in DEPLOY_FIXTURE}


def test_gate_ground_truth_accuracies_and_unsafe_rates():
    assert _gate_metrics(_preds(gate_tests_only))["decision_accuracy"] == 0.8
    assert _gate_metrics(_preds(gate_safety_policy))["decision_accuracy"] == 0.9
    assert _gate_metrics(_preds(gate_throughput))["decision_accuracy"] == 0.7
    # The full safety policy approves nothing unsafe; the throughput gate does.
    assert _gate_metrics(_preds(gate_safety_policy))["unsafe_approval_rate"] == 0.0
    assert _gate_metrics(_preds(gate_throughput))["unsafe_approval_rate"] == 0.6


def test_evaluator_deterministic_and_skips_unknown():
    pipe = _pipeline_for("capsule:simulation_check.deploy_dryrun.v1")
    a = deployment_evaluator(DEPLOYMENT_GATE_SIGNATURE, pipe, "s")
    b = deployment_evaluator(DEPLOYMENT_GATE_SIGNATURE, pipe, "s")
    assert a.scores == b.scores and a.outcome == "passed"
    skipped = deployment_evaluator(DEPLOYMENT_GATE_SIGNATURE, _pipeline_for("capsule:unknown"), "s")
    assert skipped.outcome == "skipped"


def test_signature_primary_is_decision_accuracy():
    assert DEPLOYMENT_GATE_SIGNATURE.success_metrics()[0].metric_id == "decision_accuracy"


def test_run_selects_safety_policy_and_refuses_throughput():
    report, ledger = run_benchmark("deployment_gate_decision.v1")
    runs = {r.method_families: r for r in ledger.for_signature(report.signature_hash)}
    baseline = runs[("search_planner",)]
    policy = runs[("simulation_check",)]
    throughput = runs[("constraint_solver",)]

    assert _score_of(baseline, "decision_accuracy") == 0.8
    assert _score_of(policy, "decision_accuracy") == 0.9
    assert _score_of(throughput, "decision_accuracy") == 0.7

    # The full safety policy is the sole winner.
    assert len(report.winner_record_hashes) == 1
    assert policy.record_hash in report.winner_record_hashes
    assert policy.baseline_delta["decision_accuracy"] > 0

    # The throughput gate ran and passed the floor, but lost on accuracy -> refused.
    assert throughput.outcome == "passed"
    assert throughput.record_hash in report.candidate_record_hashes
    assert throughput.record_hash not in report.winner_record_hashes
    assert throughput.baseline_delta["decision_accuracy"] < 0

    assert report.negative_record_hashes == ()
    assert report.baseline_compromised is False


def test_winner_crosses_bridge():
    report, ledger = run_benchmark("deployment_gate_decision.v1")
    runs = {r.method_families: r for r in ledger.for_signature(report.signature_hash)}
    policy = runs[("simulation_check",)]
    sig = get_benchmark("deployment_gate_decision.v1").signature

    assert is_winner(policy, sig) is True
    forge_input = forge_input_for_winner(
        winner=policy,
        signature=sig,
        capability_id="ops.deployment_gate.v1",
        version="0.1.0",
        api_docs_ref="docs/api/deploy_gate.md",
        input_schema_ref="schemas/deploy_gate.input.schema.json",
        output_schema_ref="schemas/deploy_gate.output.schema.json",
        owner_team="release-engineering",
    )
    assert forge_input.domain == "workflow_automation"
    assert forge_input.metadata["solver_forge"]["primary_metric_id"] == "decision_accuracy"


def test_catalog_includes_all_three_first_domains():
    ids = {b.benchmark_id for b in list_benchmarks()}
    # Subset check so future benchmarks don't break this.
    assert {
        "invoice_duplicate_detection.v1",
        "task_scheduling_with_deadlines.v1",
        "deployment_gate_decision.v1",
    } <= ids
