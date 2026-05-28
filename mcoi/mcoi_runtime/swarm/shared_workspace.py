"""Shared workspace for governed swarm coordination.

Purpose: store structured task outputs for supervisor review without granting
unrestricted memory access.
Governance scope: tenant-safe shared claims and receipts.
Dependencies: swarm contracts.
Invariants: workspace records are append-only and message identifiers are
unique within a goal.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .contracts import SwarmInvariantViolation, SwarmMessage, SwarmReceipt


@dataclass
class SharedWorkspace:
    """Append-only workspace for one or more governed goals."""

    _messages: list[SwarmMessage] = field(default_factory=list)
    _receipts: list[SwarmReceipt] = field(default_factory=list)

    def append_message(self, message: SwarmMessage) -> None:
        """Append a structured message."""

        if any(existing.message_id == message.message_id for existing in self._messages):
            raise SwarmInvariantViolation(f"duplicate workspace message_id: {message.message_id}")
        self._messages.append(message)

    def append_receipt(self, receipt: SwarmReceipt) -> None:
        """Append a task receipt."""

        if any(existing.receipt_id == receipt.receipt_id for existing in self._receipts):
            raise SwarmInvariantViolation(f"duplicate receipt_id: {receipt.receipt_id}")
        self._receipts.append(receipt)

    def messages_for_goal(self, goal_id: str) -> tuple[SwarmMessage, ...]:
        """Return goal messages in deterministic order."""

        return tuple(message for message in self._messages if message.goal_id == goal_id)

    def receipts_for_goal(self, goal_id: str) -> tuple[SwarmReceipt, ...]:
        """Return goal receipts in deterministic order."""

        return tuple(receipt for receipt in self._receipts if receipt.goal_id == goal_id)
