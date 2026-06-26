"""Focused tests for InceptaDive learning candidates and Phi advisory."""

from __future__ import annotations

from mcoi_runtime.core.inceptadive_post_outcome_learning import OutcomeLearningKind, build_outcome_learning_candidate
from mcoi_runtime.core.inceptadive_shadow_light import run_light_shadow_pass
from mcoi_runtime.core.inceptadive_shadow_receipt import create_shadow_receipt
from mcoi_runtime.core.inceptadive_shadow_types import ShadowContext, ShadowStage
from mcoi_runtime.core.phi_gps import CompiledProblem, PlatformTrace, PolicyHint, ProblemFieldStatus, build_problem_star
from mcoi_runtime.core.phi_inceptadive_solver_advisory import build_phi_inceptadive_solver_advisory


def _receipt():
    context = ShadowContext(
        request_id="req-learning-1",
        stage=ShadowStage.INTERPRETATION,
        user_input="summarize release notes",
        explicit_target="release notes",
        scope="docs",
        created_at="2026-06-18T00:00:00+00:00",
    ).with_integrity()
    return create_shadow_receipt(context, run_light_shadow_pass(context))


def test_post_outcome_learning_candidate_stays_governance_pending() -> None:
    receipt = _receipt()
    raw_evidence_ref = "outcome-secret-evidence-1"
    candidate = build_outcome_learning_candidate(
        request_id="req-learning-1",
        expected_state={"status": "planned"},
        actual_state={"status": "completed"},
        shadow_receipts=(receipt,),
        evidence_refs=(raw_evidence_ref,),
    )
    payload = candidate.to_dict()

    assert candidate.kind == OutcomeLearningKind.EXPECTATION_MISMATCH
    assert candidate.evidence_refs[0].startswith("inceptadive_outcome_evidence_")
    assert raw_evidence_ref not in str(payload)
    assert payload["governance_pending"] is True
    assert payload["memory_write_authority"] is False
    assert payload["execution_authority"] is False
    assert receipt.receipt_id in payload["source_receipt_ids"]
    assert payload["evidence_refs"] == list(candidate.evidence_refs)


def test_post_outcome_learning_missing_evidence_uses_public_sentinel() -> None:
    receipt = _receipt()
    candidate = build_outcome_learning_candidate(
        request_id="req-learning-2",
        expected_state={"status": "planned"},
        actual_state={"status": "planned"},
        shadow_receipts=(receipt,),
        evidence_refs=("",),
    )
    payload = candidate.to_dict()

    assert candidate.kind == OutcomeLearningKind.MISSING_EVIDENCE
    assert payload["evidence_refs"] == ["missing-outcome-evidence"]
    assert payload["governance_pending"] is True
    assert payload["memory_write_authority"] is False
    assert payload["execution_authority"] is False


def test_phi_inceptadive_solver_advisory_has_repair_signal() -> None:
    raw_problem_id = "problem-secret-token-advisory-1"
    problem = build_problem_star(
        problem_id=raw_problem_id,
        values={"W": {"repo": "local"}, "G": {"target": "proof"}, "Pi": ("receipt",)},
        statuses={"T": ProblemFieldStatus.UNKNOWN, "Pi": ProblemFieldStatus.PARTIAL},
        evidence_refs={"W": ("repo",), "G": ("goal",), "Pi": ("proof",)},
        input_hash="sha256:advisory",
    )
    compiled = CompiledProblem(
        kernel_draft=problem,
        symbols=(),
        assumptions=(),
        unknowns=(),
        contradictions=(),
        risks=(),
        proof_requirements=(),
        confidence_map={},
        required_clarifications=(),
        safe_default_policy=PolicyHint.PROOF_FIRST,
        trace=PlatformTrace(problem_id=problem.problem_id),
    )
    advisory = build_phi_inceptadive_solver_advisory(compiled)

    assert advisory["execution_approval"] is False
    assert advisory["problem_id"].startswith("phi_inceptadive_problem_")
    assert advisory["problem_identifier_exposed"] is False
    assert advisory["lineage_ref_count"] >= 1
    assert advisory["lineage_identifiers_exposed"] is False
    assert raw_problem_id not in str(advisory)
    assert "Phi-GPS-v3" not in str(advisory)
    assert advisory["proof_gap_count"] >= 1
    assert advisory["requires_repair"] is True
    assert advisory["suggested_solver_modes"]
