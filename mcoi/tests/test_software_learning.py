"""Purpose: verify software-outcome learning admission contracts.
Governance scope: sanitized software evidence, raw-log exclusion, procedural
and risk memory targets, and planning projection after admission.
Dependencies: software dev loop contracts, software learning contracts, and
learning admission contracts.
Invariants:
  - Raw logs are never admitted into planning memory.
  - Passed gates may become procedural-memory candidates.
  - Failed gates may become hashed risk-memory signatures.
  - Planning projection requires LearningAdmissionDecision(status=admit).
"""

from __future__ import annotations

import json

import pytest

from mcoi_runtime.contracts.code import PatchApplicationResult, PatchStatus
from mcoi_runtime.contracts.learning import (
    LearningAdmissionDecision,
    LearningAdmissionStatus,
)
from mcoi_runtime.contracts.policy import DecisionReason
from mcoi_runtime.contracts.software_dev_loop import (
    AttemptRecord,
    AttemptStatus,
    AutonomyEvidence,
    QualityGateResult,
)
from mcoi_runtime.contracts.software_learning import (
    SoftwareLearningKind,
    SoftwareMemoryTarget,
    SoftwareOutcomeLearningCandidate,
)
from mcoi_runtime.core.planning_boundary import KnowledgeLifecycle
from mcoi_runtime.core.software_learning import (
    decide_software_outcome_learning,
    derive_software_outcome_learning_candidates,
    planning_knowledge_from_software_candidate,
)


T0 = "2025-01-15T10:00:00+00:00"
T1 = "2025-01-15T10:00:05+00:00"


def _gate(
    *,
    gate: str = "unit_tests",
    passed: bool,
    evidence_id: str,
    summary: str,
    exit_code: int = 0,
) -> QualityGateResult:
    return QualityGateResult(
        gate=gate,
        passed=passed,
        evidence_id=evidence_id,
        summary=summary,
        exit_code=exit_code,
    )


def _attempt(
    *,
    attempt_index: int,
    status: AttemptStatus,
    gate_results: tuple[QualityGateResult, ...],
    rolled_back: bool = False,
) -> AttemptRecord:
    return AttemptRecord(
        attempt_index=attempt_index,
        snapshot_id=f"snapshot-{attempt_index}",
        patch_id=f"patch-{attempt_index}",
        status=status,
        patch_result=PatchApplicationResult(
            patch_id=f"patch-{attempt_index}",
            status=PatchStatus.APPLIED,
            target_file="main.py",
        ),
        gate_results=gate_results,
        rolled_back=rolled_back,
    )


def _evidence(
    *,
    attempts: tuple[AttemptRecord, ...],
    request_id: str = "sw-req-1",
    ucja_accepted: bool = True,
    rollback_succeeded: bool | None = True,
) -> AutonomyEvidence:
    return AutonomyEvidence(
        request_id=request_id,
        ucja_job_id="ucja-sw-1",
        ucja_accepted=ucja_accepted,
        ucja_halted_at_layer=None if ucja_accepted else "L0_purpose",
        ucja_reason="" if ucja_accepted else "purpose rejected",
        initial_snapshot_id="snapshot-initial",
        plan_id="plan-sw-1",
        attempts=attempts,
        review_record_id=None,
        rollback_succeeded=rollback_succeeded,
        rollback_evidence_id="rollback-1" if rollback_succeeded else None,
        started_at=T0,
        completed_at=T1,
    )


def _procedural_candidate(**overrides: object) -> SoftwareOutcomeLearningCandidate:
    values = {
        "knowledge_id": "software-learning-procedural-fixture",
        "kind": SoftwareLearningKind.PROCEDURAL_FIX_PATTERN,
        "memory_target": SoftwareMemoryTarget.PROCEDURAL_MEMORY,
        "request_id": "sw-req-1",
        "repository": "repo-main",
        "summary": "Passed unit test gate",
        "pattern": "Reuse bounded patch pattern",
        "affected_files": ("main.py",),
        "receipt_refs": ("receipt:terminal",),
        "gate_refs": ("gate-pass-1",),
        "evidence_refs": ("software_request:sw-req-1", "receipt:terminal", "gate-pass-1"),
    }
    values.update(overrides)
    return SoftwareOutcomeLearningCandidate(**values)


def test_derives_sanitized_procedural_and_risk_candidates() -> None:
    failed = _gate(
        passed=False,
        evidence_id="gate-fail-0",
        summary="secret stacktrace should be hashed only",
        exit_code=1,
    )
    passed = _gate(passed=True, evidence_id="gate-pass-1", summary="ok")
    evidence = _evidence(
        attempts=(
            _attempt(
                attempt_index=0,
                status=AttemptStatus.GATES_FAILED,
                gate_results=(failed,),
                rolled_back=True,
            ),
            _attempt(
                attempt_index=1,
                status=AttemptStatus.GATES_PASSED,
                gate_results=(passed,),
            ),
        )
    )

    candidates = derive_software_outcome_learning_candidates(
        evidence,
        repository="repo-main",
        affected_files=("main.py",),
        receipt_refs=("receipt:terminal",),
    )
    by_kind = {candidate.kind: candidate for candidate in candidates}
    risk_json = json.dumps(
        by_kind[SoftwareLearningKind.RISK_FAILURE_SIGNATURE].to_json_dict(),
        sort_keys=True,
    )

    assert len(candidates) == 2
    assert by_kind[SoftwareLearningKind.PROCEDURAL_FIX_PATTERN].memory_target is SoftwareMemoryTarget.PROCEDURAL_MEMORY
    assert by_kind[SoftwareLearningKind.RISK_FAILURE_SIGNATURE].memory_target is SoftwareMemoryTarget.RISK_MEMORY
    assert by_kind[SoftwareLearningKind.PROCEDURAL_FIX_PATTERN].raw_log_included is False
    assert "secret stacktrace" not in risk_json
    assert "receipt:terminal" in by_kind[SoftwareLearningKind.RISK_FAILURE_SIGNATURE].evidence_refs


def test_learning_decision_admits_and_projects_to_planning_knowledge() -> None:
    passed = _gate(passed=True, evidence_id="gate-pass-1", summary="ok")
    evidence = _evidence(
        attempts=(
            _attempt(
                attempt_index=0,
                status=AttemptStatus.GATES_PASSED,
                gate_results=(passed,),
            ),
        )
    )
    candidate = derive_software_outcome_learning_candidates(
        evidence,
        repository="repo-main",
        affected_files=("main.py",),
        receipt_refs=("receipt:terminal",),
    )[0]

    decision = decide_software_outcome_learning(candidate, evidence, issued_at=T1)
    knowledge = planning_knowledge_from_software_candidate(candidate, decision)

    assert decision.status is LearningAdmissionStatus.ADMIT
    assert decision.knowledge_id == candidate.knowledge_id
    assert knowledge.lifecycle is KnowledgeLifecycle.ADMITTED
    assert knowledge.knowledge_class == SoftwareMemoryTarget.PROCEDURAL_MEMORY.value
    assert knowledge.admission_id == decision.admission_id


def test_raw_log_candidate_is_rejected_before_planning_use() -> None:
    passed = _gate(passed=True, evidence_id="gate-pass-1", summary="ok")
    evidence = _evidence(
        attempts=(
            _attempt(
                attempt_index=0,
                status=AttemptStatus.GATES_PASSED,
                gate_results=(passed,),
            ),
        )
    )
    candidate = _procedural_candidate(raw_log_included=True)

    decision = decide_software_outcome_learning(candidate, evidence, issued_at=T1)

    assert decision.status is LearningAdmissionStatus.REJECT
    assert decision.reasons[0].code == "software_learning.raw_log_rejected"
    assert decision.metadata["raw_log_included"] is True
    with pytest.raises(ValueError, match="software_learning_candidate_not_admitted"):
        planning_knowledge_from_software_candidate(candidate, decision)


def test_rollback_failure_defers_learning_admission() -> None:
    passed = _gate(passed=True, evidence_id="gate-pass-1", summary="ok")
    evidence = _evidence(
        attempts=(
            _attempt(
                attempt_index=0,
                status=AttemptStatus.GATES_PASSED,
                gate_results=(passed,),
            ),
        ),
        rollback_succeeded=False,
    )
    candidate = derive_software_outcome_learning_candidates(
        evidence,
        repository="repo-main",
        affected_files=("main.py",),
        receipt_refs=("receipt:terminal",),
    )[0]

    decision = decide_software_outcome_learning(candidate, evidence, issued_at=T1)

    assert decision.status is LearningAdmissionStatus.DEFER
    assert decision.reasons[0].code == "software_learning.rollback_deferred"
    assert decision.metadata["request_id"] == evidence.request_id
    with pytest.raises(ValueError, match="software_learning_candidate_not_admitted"):
        planning_knowledge_from_software_candidate(candidate, decision)


def test_planning_projection_requires_matching_admission() -> None:
    candidate = _procedural_candidate()
    mismatched = LearningAdmissionDecision(
        admission_id="admission-other",
        knowledge_id="other-knowledge",
        status=LearningAdmissionStatus.ADMIT,
        reasons=(DecisionReason("admitted fixture"),),
        issued_at=T1,
    )

    with pytest.raises(ValueError, match="learning_admission_knowledge_mismatch"):
        planning_knowledge_from_software_candidate(candidate, mismatched)

    assert mismatched.status is LearningAdmissionStatus.ADMIT
    assert mismatched.knowledge_id != candidate.knowledge_id
    assert mismatched.admission_id == "admission-other"
