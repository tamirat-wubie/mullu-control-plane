"""Verifier for governed swarm closure readiness.

Purpose: validate that a swarm decision has receipt and trace support before
terminal closure.
Governance scope: PRS, CDCV, and no side-effect execution by agents.
Dependencies: swarm contracts.
Invariants: passed decisions require all task receipts.
"""

from __future__ import annotations

from dataclasses import dataclass

from .contracts import SwarmDecision, SwarmDecisionVerdict, SwarmReceipt, SwarmTask, SwarmTraceEntry


@dataclass(frozen=True)
class VerificationResult:
    """Verification outcome with explicit reason."""

    passed: bool
    reason: str


class VerifierAgent:
    """Deterministic verifier for S2 swarm proof readiness."""

    def verify(
        self,
        *,
        tasks: tuple[SwarmTask, ...],
        decision: SwarmDecision,
        receipts: tuple[SwarmReceipt, ...],
        traces: tuple[SwarmTraceEntry, ...],
    ) -> VerificationResult:
        """Verify terminal proof obligations."""

        if decision.verdict is not SwarmDecisionVerdict.PASSED:
            return VerificationResult(False, "decision_not_passed")
        receipt_task_ids = {receipt.task_id for receipt in receipts}
        required_task_ids = {task.task_id for task in tasks if task.requires_receipt}
        missing = sorted(required_task_ids.difference(receipt_task_ids))
        if missing:
            return VerificationResult(False, f"missing_receipts:{','.join(missing)}")
        if not traces:
            return VerificationResult(False, "missing_trace")
        return VerificationResult(True, "proof_obligations_satisfied")
