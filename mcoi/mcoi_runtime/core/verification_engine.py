"""Purpose: provide deterministic verification closure for executed runtime actions.
Governance scope: verification-core closure only.
Dependencies: canonical execution and verification contracts.
Invariants: verification stays explicit, mismatches fail closed, and completion is never inferred from dispatch alone.
"""

from __future__ import annotations

from dataclasses import dataclass

from mcoi_runtime.contracts.execution import ExecutionOutcome, ExecutionResult
from mcoi_runtime.contracts.verification import VerificationResult, VerificationStatus


@dataclass(frozen=True, slots=True)
class VerificationClosure:
    verification_closed: bool
    completed: bool
    error: str | None = None


class VerificationEngine:
    """Evaluate explicit verification input against an execution result."""

    def evaluate(
        self,
        execution_result: ExecutionResult,
        verification_result: VerificationResult | None,
    ) -> VerificationClosure:
        if verification_result is None:
            return VerificationClosure(
                verification_closed=False,
                completed=False,
                error=None,
            )

        if verification_result.execution_id != execution_result.execution_id:
            return VerificationClosure(
                verification_closed=False,
                completed=False,
                error="verification_execution_mismatch",
            )

        if verification_result.status is VerificationStatus.PASS:
            if execution_result.status is ExecutionOutcome.SUCCEEDED:
                return VerificationClosure(
                    verification_closed=True,
                    completed=True,
                    error=None,
                )
            return VerificationClosure(
                verification_closed=True,
                completed=False,
                error="execution_outcome_not_completable",
            )

        return VerificationClosure(
            verification_closed=True,
            completed=False,
            error=None,
        )
