"""Tests for the gateway self-improvement driver.

These lock the proposal-only contract and the four Solver-Forge invariants:
only-winner-on-metric, append-only negatives-preserved ledger, symmetric
adversarial review, and never-promote/never-edit-source.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from gateway.candidate_ledger import CandidateLedger, CandidateScore
from gateway.connector_self_healing import (
    ConnectorFailure,
    ConnectorFailureType,
    ConnectorRecoveryAction,
    ConnectorRecoveryPolicy,
)
from gateway.self_improvement_driver import (
    crawl_route_coverage,
    crawl_witness_integrity,
    run_cycle,
    select_winners,
    signature_hash_for,
)

_AT = "2026-05-23T00:00:00Z"
_REPO_ROOT = Path(__file__).resolve().parents[2]
_REAL_MATRIX = _REPO_ROOT / "tests" / "fixtures" / "proof_coverage_matrix.json"


def _write_matrix(tmp_path: Path, surfaces: list[dict], routes: list[dict] | None = None) -> Path:
    path = tmp_path / "matrix.json"
    payload: dict = {"witness_integrity": {"surfaces": surfaces}}
    if routes is not None:
        payload["route_coverage"] = {"routes": routes}
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _surface(surface_id: str, runtime: int, unanchored: int) -> dict:
    return {
        "surface_id": surface_id,
        "runtime_witness_count": runtime,
        "unanchored_witness_count": unanchored,
        "anchored_witnesses": [
            {"witness": f"{surface_id}_w", "anchors": [f"tests/test_{surface_id}.py::test_{surface_id}"]}
        ],
        "unanchored_witnesses": [{"witness": f"{surface_id}_u{i}"} for i in range(unanchored)],
    }


def test_crawl_ranks_largest_gap_first_with_alpha_tiebreak(tmp_path: Path) -> None:
    path = _write_matrix(
        tmp_path,
        [_surface("charlie", 8, 7), _surface("bravo", 5, 0), _surface("alpha", 10, 7)],
    )
    gaps = crawl_witness_integrity(path)
    assert [g.surface_id for g in gaps] == ["alpha", "charlie", "bravo"]
    assert gaps[0].anchored_witness_count == 3  # 10 runtime - 7 unanchored


def test_run_cycle_is_proposal_only_and_fully_blocked(tmp_path: Path) -> None:
    path = _write_matrix(tmp_path, [_surface("alpha", 10, 7), _surface("charlie", 8, 7), _surface("bravo", 5, 0)])
    ledger = CandidateLedger()
    report = run_cycle(path, generated_at=_AT, top_n=5, ledger=ledger)

    assert report.activation_blocked is True
    assert report.promotion_blocked is True
    assert report.metadata["promotes_capabilities"] is False
    assert report.metadata["edits_source"] is False
    assert report.report_hash

    # Two actionable gaps -> portfolio with two activation-blocked plans.
    assert report.actionable_gap_count == 2
    assert report.portfolio is not None
    assert report.portfolio.activation_blocked is True
    assert all(plan.activation_blocked and plan.candidate.promotion_blocked for plan in report.portfolio.plans)

    # Proposals are recorded as first-class non-winning evidence.
    assert len(report.recorded_proposals) == 2
    assert all(run.outcome == "skipped" and run.baseline_delta == {} for run in report.recorded_proposals)


def test_cycle_with_no_gaps_proposes_nothing_but_stays_blocked(tmp_path: Path) -> None:
    path = _write_matrix(tmp_path, [_surface("alpha", 10, 0), _surface("bravo", 5, 0)])
    report = run_cycle(path, generated_at=_AT)
    assert report.actionable_gap_count == 0
    assert report.portfolio is None
    assert report.recorded_proposals == ()
    assert report.activation_blocked and report.promotion_blocked


def test_proposals_never_count_as_winners(tmp_path: Path) -> None:
    path = _write_matrix(tmp_path, [_surface("alpha", 10, 7)])
    ledger = CandidateLedger()
    report = run_cycle(path, generated_at=_AT, ledger=ledger)
    proposal = report.recorded_proposals[0]
    winners = select_winners(ledger, proposal.signature_hash, primary_metric_id="accuracy")
    assert winners == ()


def _seed_signature(ledger: CandidateLedger, sig: str, *, baseline_findings: tuple[str, ...] = ()) -> None:
    ledger.record(
        signature_hash=sig,
        problem_id="cap",
        candidate_pipeline_id="baseline",
        method_families=("baseline",),
        outcome="passed",
        scores=(CandidateScore(metric_id="accuracy", value=0.8, direction="maximize"),),
        baseline_delta={},
        run_seed="b",
        is_baseline=True,
        adversarial_review_findings=baseline_findings,
    )
    ledger.record(
        signature_hash=sig,
        problem_id="cap",
        candidate_pipeline_id="winner",
        method_families=("search",),
        outcome="passed",
        scores=(CandidateScore(metric_id="accuracy", value=0.9, direction="maximize"),),
        baseline_delta={"accuracy": 0.1},
        run_seed="w",
    )
    ledger.record(
        signature_hash=sig,
        problem_id="cap",
        candidate_pipeline_id="loser",
        method_families=("search",),
        outcome="passed",
        scores=(CandidateScore(metric_id="accuracy", value=0.7, direction="maximize"),),
        baseline_delta={"accuracy": -0.1},
        run_seed="l",
    )
    ledger.record(
        signature_hash=sig,
        problem_id="cap",
        candidate_pipeline_id="flagged",
        method_families=("search",),
        outcome="passed",
        scores=(CandidateScore(metric_id="accuracy", value=0.95, direction="maximize"),),
        baseline_delta={"accuracy": 0.15},
        run_seed="f",
        adversarial_review_findings=("prompt_injection_bypass",),
    )


def test_only_baseline_beating_clean_runs_win() -> None:
    ledger = CandidateLedger()
    sig = signature_hash_for("cap")
    _seed_signature(ledger, sig)
    winners = select_winners(ledger, sig, primary_metric_id="accuracy")
    assert {w.candidate_pipeline_id for w in winners} == {"winner"}


def test_compromised_baseline_disqualifies_all_winners() -> None:
    ledger = CandidateLedger()
    sig = signature_hash_for("cap")
    _seed_signature(ledger, sig, baseline_findings=("baseline_data_leak",))
    assert select_winners(ledger, sig, primary_metric_id="accuracy") == ()


def test_negatives_are_preserved_alongside_winners() -> None:
    ledger = CandidateLedger()
    sig = signature_hash_for("cap")
    _seed_signature(ledger, sig)
    # loser/flagged are "passed" so not negatives; add an explicit failure run.
    ledger.record(
        signature_hash=sig,
        problem_id="cap",
        candidate_pipeline_id="boom",
        method_families=("search",),
        outcome="failed",
        scores=(),
        baseline_delta=None,
        run_seed="x",
    )
    assert "boom" in {n.candidate_pipeline_id for n in ledger.negative_results_for(sig)}
    # baseline-beating winner still selectable with negatives present.
    assert {w.candidate_pipeline_id for w in select_winners(ledger, sig, primary_metric_id="accuracy")} == {"winner"}


def test_runtime_safe_fixer_emits_non_terminal_receipt(tmp_path: Path) -> None:
    path = _write_matrix(tmp_path, [_surface("alpha", 10, 0)])
    failure = ConnectorFailure(
        failure_id="f1",
        connector_id="c1",
        provider="prov",
        operation="read",
        tenant_id="t1",
        failure_type=ConnectorFailureType.TIMEOUT,
        observed_at=_AT,
        retryable=True,
        evidence_refs=("evidence/f1",),
    )
    policy = ConnectorRecoveryPolicy(
        connector_id="c1",
        allowed_actions=(ConnectorRecoveryAction.RETRY,),
        max_retry_attempts=3,
    )
    report = run_cycle(path, generated_at=_AT, connector_failures=((failure, policy),))
    assert len(report.healing_receipts) == 1
    receipt = report.healing_receipts[0]
    assert receipt.receipt_is_terminal_closure is False
    assert receipt.action == ConnectorRecoveryAction.RETRY


def test_crawl_runs_on_the_real_matrix_fixture() -> None:
    gaps = crawl_witness_integrity(_REAL_MATRIX)
    assert len(gaps) > 0
    # Ranking is monotonic non-increasing in the unanchored gap.
    counts = [g.unanchored_witness_count for g in gaps]
    assert counts == sorted(counts, reverse=True)


def test_route_crawl_ranks_unproven_before_witnessed_and_skips_proven(tmp_path: Path) -> None:
    routes = [
        {"route": "/z", "surface_id": "s1", "coverage_state": "witnessed"},
        {"route": "/a", "surface_id": "s2", "coverage_state": "unproven"},
        {"route": "/b", "surface_id": "s3", "coverage_state": "proven"},
    ]
    path = _write_matrix(tmp_path, [_surface("alpha", 5, 0)], routes=routes)
    gaps = crawl_route_coverage(path)
    assert [(g.route, g.coverage_state) for g in gaps] == [("/a", "unproven"), ("/z", "witnessed")]


def test_run_cycle_includes_route_gaps_only_when_requested(tmp_path: Path) -> None:
    routes = [{"route": "/a", "surface_id": "s2", "coverage_state": "unproven"}]
    path = _write_matrix(tmp_path, [_surface("alpha", 10, 7)], routes=routes)
    without = run_cycle(path, generated_at=_AT)
    assert without.route_gaps == ()
    with_routes = run_cycle(path, generated_at=_AT, include_routes=True)
    assert [g.route for g in with_routes.route_gaps] == ["/a"]


def test_report_json_validates_against_published_schema(tmp_path: Path) -> None:
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(
        (_REPO_ROOT / "schemas" / "self_improvement_cycle_report.schema.json").read_text(encoding="utf-8")
    )
    report = run_cycle(_REAL_MATRIX, generated_at=_AT, top_n=5, include_routes=True)
    jsonschema.validate(instance=report.to_json_dict(), schema=schema)


def test_cli_runs_and_emits_blocked_json(tmp_path: Path) -> None:
    spec = importlib.util.spec_from_file_location(
        "run_self_improvement_cycle", _REPO_ROOT / "scripts" / "run_self_improvement_cycle.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    out = tmp_path / "report.json"
    rc = module.main(["--matrix", str(_REAL_MATRIX), "--top-n", "3", "--out", str(out)])
    assert rc == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["activation_blocked"] is True
    assert payload["promotion_blocked"] is True
    assert payload["metadata"]["promotes_capabilities"] is False
