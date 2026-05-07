"""Purpose: derive and admit software outcome learning candidates.
Governance scope: structured software evidence, admission decisions, raw-log
    exclusion, procedural-memory candidates, and risk-memory candidates.
Dependencies: hashlib, json, learning contracts, planning boundary contracts,
    policy reasons, software evidence contracts, and software learning records.
Invariants:
  - Raw logs never become candidate content or planning knowledge.
  - Successful closure may yield procedural memory only after admitted gates.
  - Failed gates may yield risk signatures only as hashed summaries.
  - Planning projection requires LearningAdmissionDecision(status=admit).
"""

from __future__ import annotations

import json
from dataclasses import asdict
from hashlib import sha256
from typing import Any

from mcoi_runtime.contracts.learning import LearningAdmissionDecision, LearningAdmissionStatus
from mcoi_runtime.contracts.policy import DecisionReason
from mcoi_runtime.contracts.software_dev_loop import AttemptStatus, AutonomyEvidence, QualityGateResult
from mcoi_runtime.contracts.software_learning import (
    SoftwareLearningKind,
    SoftwareMemoryTarget,
    SoftwareOutcomeLearningCandidate,
)
from mcoi_runtime.core.planning_boundary import KnowledgeLifecycle, PlanningKnowledge


def derive_software_outcome_learning_candidates(
    evidence: AutonomyEvidence,
    *,
    repository: str,
    affected_files: tuple[str, ...],
    receipt_refs: tuple[str, ...],
) -> tuple[SoftwareOutcomeLearningCandidate, ...]:
    """Derive sanitized learning candidates from software autonomy evidence."""
    if not isinstance(evidence, AutonomyEvidence):
        raise ValueError("evidence must be an AutonomyEvidence")
    repository_name = repository.strip()
    if not repository_name:
        raise ValueError("repository must be non-empty")
    if not receipt_refs:
        raise ValueError("receipt_refs must contain at least one item")

    candidates: list[SoftwareOutcomeLearningCandidate] = []
    passed_attempt = _last_passed_attempt(evidence)
    if passed_attempt is not None:
        gate_refs = tuple(gate.evidence_id for gate in passed_attempt.gate_results if gate.passed)
        candidates.append(
            SoftwareOutcomeLearningCandidate(
                knowledge_id=_knowledge_id("procedural", evidence.request_id, gate_refs),
                kind=SoftwareLearningKind.PROCEDURAL_FIX_PATTERN,
                memory_target=SoftwareMemoryTarget.PROCEDURAL_MEMORY,
                request_id=evidence.request_id,
                repository=repository_name,
                summary=f"Software change {evidence.request_id} passed requested gates",
                pattern=_procedural_pattern(evidence, passed_attempt.gate_results),
                affected_files=affected_files,
                receipt_refs=receipt_refs,
                gate_refs=gate_refs,
                evidence_refs=_candidate_evidence_refs(evidence, receipt_refs, gate_refs),
                raw_log_included=False,
                metadata={
                    "attempt_count": len(evidence.attempts),
                    "plan_id": evidence.plan_id,
                    "raw_log_policy": "excluded",
                },
            )
        )
    for failed_gate in _failed_gates(evidence):
        signature = _failure_signature(failed_gate)
        candidates.append(
            SoftwareOutcomeLearningCandidate(
                knowledge_id=_knowledge_id("risk", evidence.request_id, (signature, failed_gate.evidence_id)),
                kind=SoftwareLearningKind.RISK_FAILURE_SIGNATURE,
                memory_target=SoftwareMemoryTarget.RISK_MEMORY,
                request_id=evidence.request_id,
                repository=repository_name,
                summary=f"Gate {failed_gate.gate} failed during governed software change",
                pattern=f"Treat {failed_gate.gate} exit {failed_gate.exit_code} as a prior risk signal",
                affected_files=affected_files,
                receipt_refs=receipt_refs,
                gate_refs=(failed_gate.evidence_id,),
                evidence_refs=_candidate_evidence_refs(evidence, receipt_refs, (failed_gate.evidence_id,)),
                error_signature=signature,
                raw_log_included=False,
                metadata={
                    "gate": failed_gate.gate,
                    "exit_code": failed_gate.exit_code,
                    "summary_hash": _hash_payload(failed_gate.summary),
                    "raw_log_policy": "summary_hashed_not_stored",
                },
            )
        )
    return tuple(candidates)


def decide_software_outcome_learning(
    candidate: SoftwareOutcomeLearningCandidate,
    evidence: AutonomyEvidence,
    *,
    issued_at: str,
) -> LearningAdmissionDecision:
    """Issue a canonical learning admission decision for one software candidate."""
    if not isinstance(candidate, SoftwareOutcomeLearningCandidate):
        raise ValueError("candidate must be a SoftwareOutcomeLearningCandidate")
    if not isinstance(evidence, AutonomyEvidence):
        raise ValueError("evidence must be an AutonomyEvidence")

    status, reason = _classify_candidate(candidate, evidence)
    return LearningAdmissionDecision(
        admission_id=_admission_id(candidate, status, issued_at),
        knowledge_id=candidate.knowledge_id,
        status=status,
        reasons=(reason,),
        issued_at=issued_at,
        metadata={
            "request_id": candidate.request_id,
            "repository": candidate.repository,
            "learning_kind": candidate.kind.value,
            "memory_target": candidate.memory_target.value,
            "raw_log_included": candidate.raw_log_included,
            "evidence_refs": candidate.evidence_refs,
        },
    )


def planning_knowledge_from_software_candidate(
    candidate: SoftwareOutcomeLearningCandidate,
    decision: LearningAdmissionDecision,
) -> PlanningKnowledge:
    """Project admitted software learning into PlanningKnowledge."""
    if decision.knowledge_id != candidate.knowledge_id:
        raise ValueError("learning_admission_knowledge_mismatch")
    if decision.status is not LearningAdmissionStatus.ADMIT:
        raise ValueError("software_learning_candidate_not_admitted")
    return PlanningKnowledge(
        knowledge_id=candidate.knowledge_id,
        knowledge_class=candidate.memory_target.value,
        lifecycle=KnowledgeLifecycle.ADMITTED,
        admission_id=decision.admission_id,
    )


def _classify_candidate(
    candidate: SoftwareOutcomeLearningCandidate,
    evidence: AutonomyEvidence,
) -> tuple[LearningAdmissionStatus, DecisionReason]:
    details = {"knowledge_id": candidate.knowledge_id, "request_id": evidence.request_id}
    if candidate.raw_log_included:
        return LearningAdmissionStatus.REJECT, DecisionReason("raw software logs cannot be admitted to planning memory", "software_learning.raw_log_rejected", details)
    if candidate.request_id != evidence.request_id:
        return LearningAdmissionStatus.REJECT, DecisionReason("candidate request does not match software evidence", "software_learning.request_mismatch", details)
    if not evidence.ucja_accepted:
        return LearningAdmissionStatus.REJECT, DecisionReason("rejected software request cannot produce learning admission", "software_learning.ucja_rejected", details)
    if not candidate.receipt_refs or not candidate.gate_refs:
        return LearningAdmissionStatus.REJECT, DecisionReason("software learning requires receipts and gate evidence", "software_learning.evidence_missing", details)
    if candidate.kind is SoftwareLearningKind.PROCEDURAL_FIX_PATTERN and _last_passed_attempt(evidence) is None:
        return LearningAdmissionStatus.REJECT, DecisionReason("procedural software learning requires a gates-passed attempt", "software_learning.no_success_attempt", details)
    if candidate.kind is SoftwareLearningKind.RISK_FAILURE_SIGNATURE and not candidate.error_signature:
        return LearningAdmissionStatus.REJECT, DecisionReason("risk learning requires a sanitized failure signature", "software_learning.signature_missing", details)
    if evidence.rollback_succeeded is False:
        return LearningAdmissionStatus.DEFER, DecisionReason("rollback failure defers software learning admission", "software_learning.rollback_deferred", details)
    return LearningAdmissionStatus.ADMIT, DecisionReason("software outcome learning candidate is admissible", "software_learning.admitted", details)


def _last_passed_attempt(evidence: AutonomyEvidence):
    for attempt in reversed(evidence.attempts):
        if attempt.status is AttemptStatus.GATES_PASSED:
            return attempt
    return None


def _failed_gates(evidence: AutonomyEvidence) -> tuple[QualityGateResult, ...]:
    failures: list[QualityGateResult] = []
    seen: set[str] = set()
    for attempt in evidence.attempts:
        for gate in attempt.gate_results:
            if not gate.passed and gate.evidence_id not in seen:
                failures.append(gate)
                seen.add(gate.evidence_id)
    return tuple(failures)


def _procedural_pattern(evidence: AutonomyEvidence, gates: tuple[QualityGateResult, ...]) -> str:
    gate_names = ", ".join(gate.gate for gate in gates if gate.passed) or "requested gates"
    return f"Reuse bounded plan {evidence.plan_id or 'unavailable'} with successful gates: {gate_names}"


def _failure_signature(gate: QualityGateResult) -> str:
    return f"{gate.gate}:exit_{gate.exit_code}:summary_sha256_{_hash_payload(gate.summary)[:12]}"


def _candidate_evidence_refs(
    evidence: AutonomyEvidence,
    receipt_refs: tuple[str, ...],
    gate_refs: tuple[str, ...],
) -> tuple[str, ...]:
    refs = (
        f"software_request:{evidence.request_id}",
        f"ucja_job:{evidence.ucja_job_id}",
        f"snapshot:{evidence.initial_snapshot_id}",
        *receipt_refs,
        *gate_refs,
    )
    return tuple(dict.fromkeys(refs))


def _knowledge_id(prefix: str, request_id: str, refs: tuple[str, ...]) -> str:
    return f"software-learning-{prefix}-{_hash_payload({'request_id': request_id, 'refs': refs})[:16]}"


def _admission_id(candidate: SoftwareOutcomeLearningCandidate, status: LearningAdmissionStatus, issued_at: str) -> str:
    return f"software-learning-admission-{_hash_payload({'knowledge_id': candidate.knowledge_id, 'status': status.value, 'issued_at': issued_at})[:16]}"


def _hash_payload(payload: Any) -> str:
    return sha256(json.dumps(_json_ready(payload), sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _json_ready(value: Any) -> Any:
    if hasattr(value, "to_json_dict"):
        return value.to_json_dict()
    if hasattr(value, "__dataclass_fields__"):
        return _json_ready(asdict(value))
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    return value
