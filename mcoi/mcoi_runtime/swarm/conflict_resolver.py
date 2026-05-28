"""Conflict resolver for governed swarm claims.

Purpose: detect incompatible WHQR proof states for the same role and target.
Governance scope: conflict visibility before quorum or action compilation.
Dependencies: swarm contracts.
Invariants: pass and fail claims on the same WHQR key cannot silently merge.
"""

from __future__ import annotations

from dataclasses import dataclass

from .contracts import SwarmMessage, WHQRGate


@dataclass(frozen=True)
class SwarmConflict:
    """Detected conflict between structured claims."""

    conflict_id: str
    goal_id: str
    whqr_key: tuple[str, str]
    message_ids: tuple[str, ...]
    reason: str


class ConflictResolver:
    """Detect claim conflicts for supervisor escalation."""

    def detect(self, messages: tuple[SwarmMessage, ...]) -> tuple[SwarmConflict, ...]:
        """Return conflicts for pass/fail contradictions."""

        grouped: dict[tuple[str, str], list[SwarmMessage]] = {}
        for message in messages:
            grouped.setdefault((message.claim.role, message.claim.target), []).append(message)
        conflicts: list[SwarmConflict] = []
        for index, (whqr_key, grouped_messages) in enumerate(sorted(grouped.items()), start=1):
            gates = {message.claim.gate for message in grouped_messages}
            if WHQRGate.PASS in gates and WHQRGate.FAIL in gates:
                conflicts.append(
                    SwarmConflict(
                        conflict_id=f"conflict_{index:06d}",
                        goal_id=grouped_messages[0].goal_id,
                        whqr_key=whqr_key,
                        message_ids=tuple(message.message_id for message in grouped_messages),
                        reason="contradictory_whqr_gates",
                    )
                )
        return tuple(conflicts)
