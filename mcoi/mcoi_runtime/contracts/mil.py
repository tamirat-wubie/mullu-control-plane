"""Purpose: MIL contracts for governed pre-execution action programs.
Governance scope: immutable instructions compiled only after WHQR and policy allow.
Dependencies: shared contract base helpers and canonical policy contracts.
Invariants: programs are non-empty, dependency-addressed, and anchored to a WHQR policy decision.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from ._base import (
    ContractRecord,
    freeze_value,
    require_datetime_text,
    require_non_empty_text,
    require_non_empty_tuple,
)
from .policy import PolicyDecision, PolicyDecisionStatus


class MILOpcode(StrEnum):
    CHECK_POLICY = "check_policy"
    CHECK_BUDGET = "check_budget"
    REQUIRE_APPROVAL = "require_approval"
    ASSERT_APPROVAL_VALID = "assert_approval_valid"
    CALL_CAPABILITY = "call_capability"
    VERIFY_EFFECT = "verify_effect"
    EMIT_PROOF = "emit_proof"


@dataclass(frozen=True, slots=True)
class MILInstruction(ContractRecord):
    instruction_id: str
    opcode: MILOpcode
    subject: str
    arguments: Mapping[str, Any] = field(default_factory=dict)
    depends_on: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "instruction_id",
            require_non_empty_text(self.instruction_id, "instruction_id"),
        )
        if not isinstance(self.opcode, MILOpcode):
            raise ValueError("opcode must be a MILOpcode value")
        object.__setattr__(self, "subject", require_non_empty_text(self.subject, "subject"))
        if not isinstance(self.arguments, Mapping):
            raise ValueError("arguments must be a mapping")
        object.__setattr__(self, "arguments", freeze_value(dict(self.arguments)))
        object.__setattr__(self, "depends_on", _freeze_text_tuple(self.depends_on, "depends_on"))


@dataclass(frozen=True, slots=True)
class MILProgram(ContractRecord):
    program_id: str
    goal_id: str
    whqr_decision: PolicyDecision
    instructions: tuple[MILInstruction, ...]
    issued_at: str
    metadata: Mapping[str, Any] = field(default_factory=dict)
    extensions: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "program_id", require_non_empty_text(self.program_id, "program_id"))
        object.__setattr__(self, "goal_id", require_non_empty_text(self.goal_id, "goal_id"))
        if not isinstance(self.whqr_decision, PolicyDecision):
            raise ValueError("whqr_decision must be a PolicyDecision")
        instructions = require_non_empty_tuple(self.instructions, "instructions")
        for index, instruction in enumerate(instructions):
            if not isinstance(instruction, MILInstruction):
                raise ValueError(f"instructions[{index}] must be a MILInstruction")
        object.__setattr__(self, "instructions", instructions)
        object.__setattr__(self, "issued_at", require_datetime_text(self.issued_at, "issued_at"))
        if not isinstance(self.metadata, Mapping):
            raise ValueError("metadata must be a mapping")
        if not isinstance(self.extensions, Mapping):
            raise ValueError("extensions must be a mapping")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
        object.__setattr__(self, "extensions", freeze_value(dict(self.extensions)))

    @property
    def whqr_allowed(self) -> bool:
        return self.whqr_decision.status is PolicyDecisionStatus.ALLOW


def _freeze_text_tuple(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    if not isinstance(values, tuple):
        raise ValueError(f"{field_name} must be a tuple")
    frozen = tuple(require_non_empty_text(value, f"{field_name}[{index}]") for index, value in enumerate(values))
    if len(set(frozen)) != len(frozen):
        raise ValueError(f"{field_name} must not contain duplicates")
    return frozen
