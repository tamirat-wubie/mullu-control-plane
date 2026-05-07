"""Purpose: static verifier for WHQR-gated MIL programs.
Governance scope: block execution planning unless WHQR, dependency, and closure checks pass.
Dependencies: MIL and policy contracts.
Invariants: WHQR non-allow is terminal before execution; proof emission is terminal.
"""

from __future__ import annotations

from dataclasses import dataclass

from mcoi_runtime.contracts.mil import MILInstruction, MILOpcode, MILProgram
from mcoi_runtime.contracts.policy import PolicyDecisionStatus


@dataclass(frozen=True, slots=True)
class MILStaticIssue:
    code: str
    message: str
    target: str | None = None


@dataclass(frozen=True, slots=True)
class MILStaticReport:
    passed: bool
    issues: tuple[MILStaticIssue, ...]


def verify_mil_program(program: MILProgram) -> MILStaticReport:
    issues: list[MILStaticIssue] = []
    instructions = program.instructions
    instruction_ids = [instruction.instruction_id for instruction in instructions]

    if program.whqr_decision.status is not PolicyDecisionStatus.ALLOW:
        issues.append(
            MILStaticIssue(
                code="whqr_not_allowed",
                message="MIL program requires an allow WHQR policy decision",
                target=program.whqr_decision.decision_id,
            )
        )

    if len(instruction_ids) != len(set(instruction_ids)):
        issues.append(MILStaticIssue("duplicate_instruction", "MIL instruction ids must be unique"))

    known_instruction_ids: set[str] = set()
    for instruction in instructions:
        for dependency_id in instruction.depends_on:
            if dependency_id not in known_instruction_ids:
                issues.append(
                    MILStaticIssue(
                        code="unsatisfied_dependency",
                        message="MIL dependency must reference an earlier instruction",
                        target=instruction.instruction_id,
                    )
                )
        known_instruction_ids.add(instruction.instruction_id)

    opcodes = tuple(instruction.opcode for instruction in instructions)
    if opcodes[0] is not MILOpcode.CHECK_POLICY:
        issues.append(MILStaticIssue("missing_policy_check", "MIL program must begin with CHECK_POLICY"))

    call_instructions = _instructions_with_opcode(instructions, MILOpcode.CALL_CAPABILITY)
    verify_instructions = _instructions_with_opcode(instructions, MILOpcode.VERIFY_EFFECT)
    proof_instructions = _instructions_with_opcode(instructions, MILOpcode.EMIT_PROOF)

    if len(call_instructions) != 1:
        issues.append(
            MILStaticIssue(
                code="call_capability_count",
                message="MIL program must contain exactly one CALL_CAPABILITY instruction",
            )
        )
    if len(verify_instructions) != 1:
        issues.append(
            MILStaticIssue(
                code="verify_effect_count",
                message="MIL program must contain exactly one VERIFY_EFFECT instruction",
            )
        )
    if len(proof_instructions) != 1:
        issues.append(MILStaticIssue("emit_proof_count", "MIL program must contain exactly one EMIT_PROOF instruction"))
    elif instructions[-1].opcode is not MILOpcode.EMIT_PROOF:
        issues.append(MILStaticIssue("missing_terminal_proof", "MIL program must end with EMIT_PROOF"))

    if call_instructions and verify_instructions:
        _require_dependency(
            issues,
            dependent=verify_instructions[0],
            required=call_instructions[0],
            code="verify_missing_call_dependency",
            message="VERIFY_EFFECT must depend on CALL_CAPABILITY",
        )
    if verify_instructions and proof_instructions:
        _require_dependency(
            issues,
            dependent=proof_instructions[0],
            required=verify_instructions[0],
            code="proof_missing_verify_dependency",
            message="EMIT_PROOF must depend on VERIFY_EFFECT",
        )

    return MILStaticReport(passed=not issues, issues=tuple(issues))


def _instructions_with_opcode(
    instructions: tuple[MILInstruction, ...],
    opcode: MILOpcode,
) -> tuple[MILInstruction, ...]:
    return tuple(instruction for instruction in instructions if instruction.opcode is opcode)


def _require_dependency(
    issues: list[MILStaticIssue],
    *,
    dependent: MILInstruction,
    required: MILInstruction,
    code: str,
    message: str,
) -> None:
    if required.instruction_id not in dependent.depends_on:
        issues.append(MILStaticIssue(code, message, dependent.instruction_id))
