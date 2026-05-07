"""Purpose: promote verified closure outcomes into episodic memory.
Governance scope: execution, accepted-risk, failure, and compensation memory
admission only.
Dependencies: memory core, execution/verification contracts, accepted-risk and
compensation assurance contracts.
Invariants:
  - No successful execution memory without passing verification.
  - Inconclusive verification requires explicit active accepted risk.
  - Failed verification is stored only as a failure record.
  - Successful compensation can become episodic only with evidence.
  - This bridge never writes semantic or procedural memory.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Mapping

from mcoi_runtime.contracts.accepted_risk import AcceptedRiskDisposition, AcceptedRiskRecord
from mcoi_runtime.contracts.compensation import CompensationOutcome, CompensationStatus
from mcoi_runtime.contracts.execution import ExecutionResult
from mcoi_runtime.contracts.verification import VerificationResult, VerificationStatus

from .invariants import RuntimeCoreInvariantError, stable_identifier
from .memory import EpisodicMemory, MemoryEntry, MemoryTier


class ClosureMemoryPromoter:
    """Append verified closure records to episodic memory."""

    def __init__(
        self,
        *,
        episodic: EpisodicMemory,
        clock: Callable[[], str],
    ) -> None:
        self._episodic = episodic
        self._clock = clock

    def admit_execution_closure(
        self,
        *,
        execution_result: ExecutionResult,
        verification_result: VerificationResult,
        accepted_risk: AcceptedRiskRecord | None = None,
    ) -> MemoryEntry:
        """Admit a terminal execution closure into episodic memory."""
        if verification_result.execution_id != execution_result.execution_id:
            raise RuntimeCoreInvariantError("verification execution mismatch")
        status = verification_result.status
        if status is VerificationStatus.PASS:
            category = "execution_success"
            trust_class = "trusted"
        elif status is VerificationStatus.INCONCLUSIVE:
            if accepted_risk is None:
                raise RuntimeCoreInvariantError("inconclusive closure requires accepted risk")
            if accepted_risk.execution_id != execution_result.execution_id:
                raise RuntimeCoreInvariantError("accepted risk execution mismatch")
            if accepted_risk.disposition is not AcceptedRiskDisposition.ACTIVE:
                raise RuntimeCoreInvariantError("accepted risk must be active")
            category = "execution_accepted_risk"
            trust_class = "accepted_risk"
        elif status is VerificationStatus.FAIL:
            category = "execution_failure"
            trust_class = "failure_record"
        else:
            raise RuntimeCoreInvariantError("unsupported verification status")

        content = _execution_content(
            execution_result=execution_result,
            verification_result=verification_result,
            trust_class=trust_class,
            accepted_risk=accepted_risk,
            recorded_at=self._clock(),
        )
        entry = MemoryEntry(
            entry_id=stable_identifier(
                "episodic-closure",
                {
                    "execution": execution_result.execution_id,
                    "verification": verification_result.verification_id,
                    "category": category,
                },
            ),
            tier=MemoryTier.EPISODIC,
            category=category,
            content=content,
            source_ids=_source_ids(execution_result.execution_id, verification_result.verification_id, accepted_risk),
        )
        return self._episodic.admit(entry)

    def admit_compensation_outcome(self, outcome: CompensationOutcome) -> MemoryEntry:
        """Admit a successful compensation outcome into episodic memory."""
        if outcome.status is not CompensationStatus.SUCCEEDED:
            raise RuntimeCoreInvariantError("only successful compensation may enter trusted episodic memory")
        if not outcome.evidence_refs:
            raise RuntimeCoreInvariantError("compensation outcome requires evidence")
        content = {
            "trust_class": "trusted_compensation",
            "command_id": outcome.command_id,
            "compensation_plan_id": outcome.compensation_plan_id,
            "attempt_id": outcome.attempt_id,
            "verification_result_id": outcome.verification_result_id,
            "reconciliation_id": outcome.reconciliation_id,
            "evidence_refs": outcome.evidence_refs,
            "decided_at": outcome.decided_at,
            "recorded_at": self._clock(),
            "metadata": outcome.metadata,
        }
        entry = MemoryEntry(
            entry_id=stable_identifier(
                "episodic-compensation",
                {
                    "plan": outcome.compensation_plan_id,
                    "attempt": outcome.attempt_id,
                    "outcome": outcome.outcome_id,
                },
            ),
            tier=MemoryTier.EPISODIC,
            category="compensation_success",
            content=content,
            source_ids=(outcome.outcome_id, outcome.verification_result_id, outcome.reconciliation_id),
        )
        return self._episodic.admit(entry)


def _execution_content(
    *,
    execution_result: ExecutionResult,
    verification_result: VerificationResult,
    trust_class: str,
    accepted_risk: AcceptedRiskRecord | None,
    recorded_at: str,
) -> Mapping[str, Any]:
    content: dict[str, Any] = {
        "trust_class": trust_class,
        "execution_id": execution_result.execution_id,
        "goal_id": execution_result.goal_id,
        "execution_status": execution_result.status.value,
        "verification_id": verification_result.verification_id,
        "verification_status": verification_result.status.value,
        "actual_effects": tuple(effect.to_json_dict() for effect in execution_result.actual_effects),
        "assumed_effects": tuple(effect.to_json_dict() for effect in execution_result.assumed_effects),
        "evidence_refs": tuple(evidence.uri for evidence in verification_result.evidence),
        "started_at": execution_result.started_at,
        "finished_at": execution_result.finished_at,
        "closed_at": verification_result.closed_at,
        "recorded_at": recorded_at,
        "metadata": {
            "execution": execution_result.metadata,
            "verification": verification_result.metadata,
        },
    }
    if accepted_risk is not None:
        content["accepted_risk"] = {
            "risk_id": accepted_risk.risk_id,
            "case_id": accepted_risk.case_id,
            "owner_id": accepted_risk.owner_id,
            "expires_at": accepted_risk.expires_at,
            "review_obligation_id": accepted_risk.review_obligation_id,
            "evidence_refs": accepted_risk.evidence_refs,
        }
    return content


def _source_ids(
    execution_id: str,
    verification_id: str,
    accepted_risk: AcceptedRiskRecord | None,
) -> tuple[str, ...]:
    if accepted_risk is None:
        return (execution_id, verification_id)
    return (execution_id, verification_id, accepted_risk.risk_id)
