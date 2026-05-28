"""Quorum engine for governed swarm decisions.

Purpose: decide whether claim evidence is sufficient to proceed, fail, or
escalate.
Governance scope: quorum cannot override proof or policy; unknown states
escalate instead of becoming permission.
Dependencies: swarm contracts.
Invariants: all required task messages must pass before a goal can pass.
"""

from __future__ import annotations

from .contracts import SwarmDecision, SwarmDecisionVerdict, SwarmMessage, WHQRGate


class QuorumEngine:
    """Deterministic S2 quorum for supervisor-led work."""

    def decide(self, goal_id: str, messages: tuple[SwarmMessage, ...]) -> SwarmDecision:
        """Return a decision from message gates."""

        message_ids = tuple(message.message_id for message in messages)
        if not messages:
            return SwarmDecision(
                decision_id=f"{goal_id}_decision",
                goal_id=goal_id,
                verdict=SwarmDecisionVerdict.ESCALATE,
                reason="no_messages",
                message_ids=(),
                requires_human_approval=True,
            )
        gates = {message.claim.gate for message in messages}
        if WHQRGate.FAIL in gates:
            return SwarmDecision(
                decision_id=f"{goal_id}_decision",
                goal_id=goal_id,
                verdict=SwarmDecisionVerdict.FAILED,
                reason="failed_claim_present",
                message_ids=message_ids,
            )
        if WHQRGate.UNKNOWN in gates or WHQRGate.BUDGET_UNKNOWN in gates:
            return SwarmDecision(
                decision_id=f"{goal_id}_decision",
                goal_id=goal_id,
                verdict=SwarmDecisionVerdict.ESCALATE,
                reason="unknown_claim_present",
                message_ids=message_ids,
                requires_human_approval=True,
            )
        return SwarmDecision(
            decision_id=f"{goal_id}_decision",
            goal_id=goal_id,
            verdict=SwarmDecisionVerdict.PASSED,
            reason="all_claims_passed",
            message_ids=message_ids,
        )
