"""Minimal MIL action gate for governed swarm outcomes.

Purpose: represent post-quorum action intent as bounded MIL instructions and
statically reject unauthorized side effects.
Governance scope: agents may produce claims, while only the governed runtime
may execute approved side-effect instructions.
Dependencies: dataclasses, enums, and swarm decisions.
Invariants: confidence is not permission, approval is explicit, and rejected
programs carry a causal reason.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .contracts import SwarmDecision, SwarmDecisionVerdict, SwarmInvariantViolation


class MILInstructionKind(str, Enum):
    """Allowed minimal instruction kinds for invoice swarm closure."""

    CHECK_BUDGET = "CHECK_BUDGET"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    VERIFY_EFFECT = "VERIFY_EFFECT"
    CALL_CAPABILITY = "CALL_CAPABILITY"


@dataclass(frozen=True)
class MILInstruction:
    """One bounded action instruction."""

    kind: MILInstructionKind
    capability: str
    side_effect: bool = False
    requires_human_approval: bool = False

    def __post_init__(self) -> None:
        if not self.capability or not self.capability.strip():
            raise SwarmInvariantViolation("MIL capability must be non-empty")
        if self.side_effect and self.kind is not MILInstructionKind.CALL_CAPABILITY:
            raise SwarmInvariantViolation("only CALL_CAPABILITY can be a side-effect instruction")


@dataclass(frozen=True)
class MILProgram:
    """Bounded MIL program compiled from a swarm decision."""

    program_id: str
    goal_id: str
    instructions: tuple[MILInstruction, ...]

    def __post_init__(self) -> None:
        if not self.program_id or not self.program_id.strip():
            raise SwarmInvariantViolation("program_id must be non-empty")
        if not self.goal_id or not self.goal_id.strip():
            raise SwarmInvariantViolation("goal_id must be non-empty")
        if not self.instructions:
            raise SwarmInvariantViolation("MIL program requires at least one instruction")


@dataclass(frozen=True)
class MILVerification:
    """Static verification result for a MIL program."""

    passed: bool
    reason: str


class MILStaticVerifier:
    """Verify that a MIL program cannot bypass swarm governance."""

    def verify(self, *, program: MILProgram, decision: SwarmDecision, human_approved: bool) -> MILVerification:
        """Return whether the program may be offered to the governed runtime."""

        if decision.verdict is not SwarmDecisionVerdict.PASSED:
            return MILVerification(False, "decision_not_passed")
        for instruction in program.instructions:
            if instruction.side_effect and not human_approved:
                return MILVerification(False, f"side_effect_requires_approval:{instruction.capability}")
            if instruction.requires_human_approval and not human_approved:
                return MILVerification(False, f"approval_missing:{instruction.capability}")
        return MILVerification(True, "mil_static_checks_passed")


def compile_invoice_mil(goal_id: str, *, request_payment: bool, human_approved: bool) -> MILProgram:
    """Compile invoice closure intent into a minimal MIL program."""

    instructions: list[MILInstruction] = [
        MILInstruction(MILInstructionKind.CHECK_BUDGET, "budget.check"),
        MILInstruction(MILInstructionKind.VERIFY_EFFECT, "invoice.audit_export"),
    ]
    if request_payment:
        instructions.append(
            MILInstruction(
                MILInstructionKind.CALL_CAPABILITY,
                "payment.dispatch",
                side_effect=True,
                requires_human_approval=not human_approved,
            )
        )
    else:
        instructions.append(MILInstruction(MILInstructionKind.REQUIRE_APPROVAL, "approval.manager"))
    return MILProgram(
        program_id=f"{goal_id}_mil",
        goal_id=goal_id,
        instructions=tuple(instructions),
    )
