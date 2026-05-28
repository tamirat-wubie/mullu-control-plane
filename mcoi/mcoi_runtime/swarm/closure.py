"""Closure certificate factory for governed swarm goals.

Purpose: emit proof-of-resolution stamps after verifier approval.
Governance scope: PRS terminal closure and memory admission boundary.
Dependencies: hashlib and swarm contracts.
Invariants: closure requires a passed decision, receipts, and traces.
"""

from __future__ import annotations

from hashlib import sha256

from .contracts import SwarmClosureCertificate, SwarmDecision, SwarmReceipt, SwarmTraceEntry
from .verifier import VerificationResult


class SwarmClosureFactory:
    """Create terminal closure certificates."""

    def close(
        self,
        *,
        decision: SwarmDecision,
        verification: VerificationResult,
        receipts: tuple[SwarmReceipt, ...],
        traces: tuple[SwarmTraceEntry, ...],
    ) -> SwarmClosureCertificate:
        """Return a closure certificate when verification passes."""

        if not verification.passed:
            raise ValueError(f"cannot close failed verification: {verification.reason}")
        receipt_ids = tuple(receipt.receipt_id for receipt in receipts)
        trace_ids = tuple(trace.trace_id for trace in traces)
        proof_material = "|".join((decision.goal_id, decision.decision_id, *receipt_ids, *trace_ids))
        proof_stamp = sha256(proof_material.encode("utf-8")).hexdigest()
        return SwarmClosureCertificate(
            certificate_id=f"{decision.goal_id}_closure",
            goal_id=decision.goal_id,
            decision_id=decision.decision_id,
            receipt_ids=receipt_ids,
            trace_ids=trace_ids,
            status="closed",
            proof_stamp=proof_stamp,
        )
