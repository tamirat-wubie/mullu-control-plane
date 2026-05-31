"""Tests for the task-scheduling reference benchmark (engineering_puzzle)."""

from __future__ import annotations

from gateway.candidate_composer import CandidatePipeline
from gateway.solver_forge_benchmarks import (
    SCHEDULING_FIXTURE,
    SCHEDULING_SIGNATURE,
    _key_earliest_deadline,
    _key_in_order,
    _key_longest_first,
    _schedule_metrics,
    _simulate,
    get_benchmark,
    list_benchmarks,
    run_benchmark,
    scheduling_evaluator,
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


def test_schedulers_ground_truth():
    naive, _ = _simulate(SCHEDULING_FIXTURE, _key_in_order)
    edf, _ = _simulate(SCHEDULING_FIXTURE, _key_earliest_deadline)
    lpt, _ = _simulate(SCHEDULING_FIXTURE, _key_longest_first)
    assert _schedule_metrics(naive)["on_time_rate"] == 0.5
    assert _schedule_metrics(edf)["on_time_rate"] == 1.0
    assert _schedule_metrics(edf)["deadline_miss_count"] == 0.0
    assert _schedule_metrics(lpt)["on_time_rate"] == round(2 / 6, 4)  # 0.3333


def test_evaluator_deterministic_and_skips_unknown():
    pipe = _pipeline_for("capsule:constraint_solver.scheduling.v1")
    a = scheduling_evaluator(SCHEDULING_SIGNATURE, pipe, "s")
    b = scheduling_evaluator(SCHEDULING_SIGNATURE, pipe, "s")
    assert a.scores == b.scores and a.outcome == "passed"
    skipped = scheduling_evaluator(SCHEDULING_SIGNATURE, _pipeline_for("capsule:unknown"), "s")
    assert skipped.outcome == "skipped"


def test_signature_primary_is_on_time_rate():
    assert SCHEDULING_SIGNATURE.success_metrics()[0].metric_id == "on_time_rate"


def test_run_selects_edf_and_refuses_longest_first():
    report, ledger = run_benchmark("task_scheduling_with_deadlines.v1")
    runs = {r.method_families: r for r in ledger.for_signature(report.signature_hash)}
    baseline = runs[("search_planner",)]
    edf = runs[("constraint_solver",)]
    lpt = runs[("optimization_solver",)]

    assert _score_of(baseline, "on_time_rate") == 0.5
    assert _score_of(edf, "on_time_rate") == 1.0
    assert _score_of(lpt, "on_time_rate") < _score_of(baseline, "on_time_rate")

    # EDF is the sole winner.
    assert len(report.winner_record_hashes) == 1
    assert edf.record_hash in report.winner_record_hashes
    assert edf.baseline_delta["on_time_rate"] > 0

    # The longest-first anti-pattern ran and passed the floor, but did NOT beat
    # the baseline on the primary metric, so it is recorded yet refused.
    assert lpt.outcome == "passed"
    assert lpt.record_hash in report.candidate_record_hashes
    assert lpt.record_hash not in report.winner_record_hashes
    assert lpt.baseline_delta["on_time_rate"] < 0

    assert report.negative_record_hashes == ()
    assert report.baseline_compromised is False


def test_winner_crosses_bridge():
    report, ledger = run_benchmark("task_scheduling_with_deadlines.v1")
    runs = {r.method_families: r for r in ledger.for_signature(report.signature_hash)}
    edf = runs[("constraint_solver",)]
    sig = get_benchmark("task_scheduling_with_deadlines.v1").signature

    assert is_winner(edf, sig) is True
    forge_input = forge_input_for_winner(
        winner=edf,
        signature=sig,
        capability_id="ops.deadline_scheduler.v1",
        version="0.1.0",
        api_docs_ref="docs/api/sched.md",
        input_schema_ref="schemas/sched.input.schema.json",
        output_schema_ref="schemas/sched.output.schema.json",
        owner_team="ops-platform",
    )
    assert forge_input.domain == "engineering_puzzle"
    assert forge_input.metadata["solver_forge"]["primary_metric_id"] == "on_time_rate"


def test_catalog_now_has_two_benchmarks():
    ids = {b.benchmark_id for b in list_benchmarks()}
    assert ids == {"invoice_duplicate_detection.v1", "task_scheduling_with_deadlines.v1"}
