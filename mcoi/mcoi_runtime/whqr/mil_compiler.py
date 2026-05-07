"""Purpose: compile WHQR policy outputs into verifier-ready MIL programs.
Governance scope: side-effect-free MIL construction only.
Dependencies: MIL contracts, policy decisions, WHQR goal compiler, and MIL static verifier.
Invariants: compilation preserves policy status; generated instruction dependencies are explicit and ordered.
"""

from __future__ import annotations

from mcoi_runtime.contracts.mil import MILInstruction, MILOpcode, MILProgram
from mcoi_runtime.contracts.policy import PolicyDecision
from mcoi_runtime.core.mil_static_verifier import MILStaticReport, verify_mil_program
from mcoi_runtime.whqr.goal_compiler import WHQRGoalCompilation


def compile_mil_from_policy_decision(
    *,
    decision: PolicyDecision,
    program_id: str,
    capability: str,
    issued_at: str,
    effect_subject: str | None = None,
) -> MILProgram:
    if not isinstance(decision, PolicyDecision):
        raise ValueError("decision must be a PolicyDecision")
    effect = effect_subject or decision.goal_id
    instructions = (
        MILInstruction(
            "check-policy",
            MILOpcode.CHECK_POLICY,
            decision.goal_id,
            {"decision_id": decision.decision_id},
        ),
        MILInstruction(
            "call-capability",
            MILOpcode.CALL_CAPABILITY,
            capability,
            {"goal_id": decision.goal_id},
            depends_on=("check-policy",),
        ),
        MILInstruction(
            "verify-effect",
            MILOpcode.VERIFY_EFFECT,
            effect,
            {"capability": capability},
            depends_on=("call-capability",),
        ),
        MILInstruction(
            "emit-proof",
            MILOpcode.EMIT_PROOF,
            decision.goal_id,
            {"effect_subject": effect},
            depends_on=("verify-effect",),
        ),
    )
    return MILProgram(
        program_id,
        decision.goal_id,
        decision,
        instructions,
        issued_at,
        metadata={
            "compiler": "whqr_policy_mil_compiler",
            "capability": capability,
        },
    )


def compile_and_verify_mil_from_policy_decision(
    *,
    decision: PolicyDecision,
    program_id: str,
    capability: str,
    issued_at: str,
    effect_subject: str | None = None,
) -> tuple[MILProgram, MILStaticReport]:
    program = compile_mil_from_policy_decision(
        decision=decision,
        program_id=program_id,
        capability=capability,
        issued_at=issued_at,
        effect_subject=effect_subject,
    )
    return program, verify_mil_program(program)


def compile_mil_from_whqr_goal(
    compilation: WHQRGoalCompilation,
    *,
    issued_at: str,
    capability: str = "capability.pending",
) -> MILProgram:
    if not compilation.ready_for_mil:
        raise ValueError(f"WHQR goal is not ready for MIL compilation: {compilation.next_step}")
    return compile_mil_from_policy_decision(
        decision=compilation.policy_decision,
        program_id=f"mil:{compilation.goal.goal_id}",
        capability=capability,
        issued_at=issued_at,
        effect_subject=compilation.goal.goal_id,
    )
