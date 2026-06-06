"""Tests for the Phi-GPS to InceptaDive advisory bridge.

Purpose: verify read-only structural dive reports from governed ProblemStar
objects.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: mcoi_runtime.core.phi_gps and phi_inceptadive_bridge.
Invariants: the bridge emits traceable structure, never approves execution,
and routes proof gaps back to governed solver modes.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.phi_gps import (
    CompiledProblem,
    CompilerAssumption,
    CompilerContradiction,
    CompilerProofRequirement,
    CompilerRisk,
    CompilerUnknown,
    PlatformTrace,
    ProblemFieldStatus,
    ProblemStar,
    ProblemStarField,
    PolicyHint,
    ProofState,
    SolverMode,
    build_problem_star,
)
from mcoi_runtime.core.phi_inceptadive_bridge import (
    PhiInceptaDiveReport,
    build_compiled_problem_dive_report,
    build_phi_inceptadive_report,
    problem_star_to_concept_boxes,
)


def _layered_problem() -> ProblemStar:
    return build_problem_star(
        problem_id="problem-deep-structure",
        values={
            "W": {"repo": "local"},
            "B": {"hypothesis": "test gap"},
            "G": {"target": "verified closure"},
            "Lambda": ("no silent failure",),
            "N": ("foundation mode",),
            "A_e": ("inspect", "test"),
            "A_w": ("patch",),
            "Pi": ("receipt",),
        },
        statuses={
            "B": ProblemFieldStatus.HYPOTHESIZED,
            "T": ProblemFieldStatus.UNKNOWN,
            "A_w": ProblemFieldStatus.HYPOTHESIZED,
            "Pi": ProblemFieldStatus.PARTIAL,
        },
        evidence_refs={
            "W": ("repo-status",),
            "G": ("user-request",),
            "Lambda": ("agents-policy",),
            "N": ("foundation-mode",),
            "Pi": ("receipt-contract",),
        },
        input_hash="sha256:deep-structure",
    )


def test_problem_star_projects_to_concept_boxes_without_execution_authority() -> None:
    problem = _layered_problem()
    boxes = problem_star_to_concept_boxes(problem)
    report = build_phi_inceptadive_report(problem)
    payload = report.to_dict()

    assert len(boxes) == len(problem.fields)
    assert len({box.box_id for box in boxes}) == len(boxes)
    assert all(box.to_dict()["projection_only"] is True for box in boxes)
    assert payload["execution_approval"] is False
    assert report.execution_approval is False
    assert "InceptaDive-M" in report.lineage


def test_report_detects_hidden_assumptions_and_proof_gaps() -> None:
    report = build_phi_inceptadive_report(_layered_problem())

    assert "B:hypothesized" in report.hidden_assumptions
    assert "A_w:hypothesized" in report.hidden_assumptions
    assert "T:unknown" in report.proof_gaps
    assert any(gap.startswith("Pi:") for gap in report.proof_gaps)
    assert report.requires_repair is True
    assert SolverMode.DIAGNOSIS in report.suggested_solver_modes
    assert SolverMode.PROOF_CONSTRUCTION in report.suggested_solver_modes


def test_report_scores_findings_and_preserves_traceable_layers() -> None:
    report = build_phi_inceptadive_report(_layered_problem(), max_findings=18)

    assert len(report.layers) == len(report.concept_boxes)
    assert len(report.axis_findings) <= 18
    assert report.scores
    assert all(score.to_dict()["execution_approval"] is False for score in report.scores)
    assert all(layer.concept_box_id for layer in report.layers)
    assert all(layer.layer_id.startswith("phi-inceptadive-layer-") for layer in report.layers)


def test_compiled_problem_report_adds_compiler_assumptions_and_contradictions() -> None:
    problem = _layered_problem()
    compiled = CompiledProblem(
        kernel_draft=problem,
        symbols=(),
        assumptions=(
            CompilerAssumption(
                assumption_id="assumption-1",
                statement="transition model can be sensed locally",
                source="test-fixture",
                confidence=0.4,
            ),
        ),
        unknowns=(
            CompilerUnknown(
                unknown_id="unknown-1",
                dimension="transition_model",
                question="which state transition is valid",
                impact="critical",
                resolution="observe",
            ),
        ),
        contradictions=(
            CompilerContradiction(
                contradiction_id="contradiction-1",
                claims_in_conflict=("world action requested", "world action authority missing"),
                severity="high",
                scope="action-authority",
                possible_repairs=("request authority",),
            ),
        ),
        risks=(
            CompilerRisk(
                risk_id="risk-1",
                description="world action may be unsafe",
                severity="high",
                mitigation="simulate first",
            ),
        ),
        proof_requirements=(
            CompilerProofRequirement(
                requirement_id="proof-1",
                description="prove action remains local and reversible",
                required_state=ProofState.UNKNOWN,
            ),
        ),
        confidence_map={"transition_model": 0.2},
        required_clarifications=("transition evidence",),
        safe_default_policy=PolicyHint.PROOF_FIRST,
        trace=PlatformTrace(problem_id=problem.problem_id),
    )
    report = build_compiled_problem_dive_report(compiled)

    assert "compiler_assumption:assumption-1" in report.hidden_assumptions
    assert "compiler_unknown:transition_model" in report.proof_gaps
    assert "compiler_contradiction:contradiction-1" in report.proof_gaps
    assert any("resolve compiler_contradiction" in repair for repair in report.repair_recommendations)
    assert report.to_dict()["execution_approval"] is False


def test_report_rejects_execution_approval() -> None:
    report = build_phi_inceptadive_report(_layered_problem(), max_findings=4)

    with pytest.raises(RuntimeCoreInvariantError, match="cannot approve execution"):
        PhiInceptaDiveReport(
            report_id="report-bad",
            problem_id=report.problem_id,
            layers=report.layers,
            concept_boxes=report.concept_boxes,
            axis_findings=report.axis_findings,
            scores=report.scores,
            suggested_solver_modes=report.suggested_solver_modes,
            proof_gaps=report.proof_gaps,
            hidden_assumptions=report.hidden_assumptions,
            repair_recommendations=report.repair_recommendations,
            execution_approval=True,
        )


def test_bridge_rejects_invalid_runtime_bounds() -> None:
    with pytest.raises(RuntimeCoreInvariantError, match="max_findings must be positive"):
        build_phi_inceptadive_report(_layered_problem(), max_findings=0)

    with pytest.raises(ValueError, match="canonical P\\* field order"):
        ProblemStar(
            problem_id="bad",
            fields=tuple(
                ProblemStarField(name=field_name, status=ProblemFieldStatus.UNKNOWN)
                for field_name in ("W", "B")
            ),
        )
