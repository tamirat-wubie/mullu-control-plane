"""Purpose: verify WHQR policy decisions compile into verifier-ready MIL programs.
Governance scope: WHQR policy output must become explicit policy, capability, effect, and proof instructions.
Dependencies: WHQR MIL compiler, policy contracts, and MIL static verifier.
Invariants: allow decisions compile to accepted MIL; deny decisions compile but fail static execution admission.
"""

from __future__ import annotations

from mcoi_runtime.contracts.mil import MILOpcode
from mcoi_runtime.contracts.policy import DecisionReason, PolicyDecision, PolicyDecisionStatus
from mcoi_runtime.whqr.mil_compiler import (
    compile_and_verify_mil_from_policy_decision,
    compile_mil_from_policy_decision,
)


ISSUED_AT = "2026-05-06T09:00:00Z"


def _decision(status: PolicyDecisionStatus) -> PolicyDecision:
    return PolicyDecision(
        decision_id=f"whqr:goal-invoice:{status.value}",
        subject_id="operator",
        goal_id="goal-invoice",
        status=status,
        reasons=(DecisionReason(status.value, f"whqr_{status.value}"),),
        issued_at=ISSUED_AT,
    )


def test_compiler_emits_ordered_mil_for_allow_decision() -> None:
    program, report = compile_and_verify_mil_from_policy_decision(
        decision=_decision(PolicyDecisionStatus.ALLOW),
        program_id="mil:goal-invoice",
        capability="financial.send_payment",
        issued_at=ISSUED_AT,
        effect_subject="payment_settlement",
    )
    opcodes = tuple(instruction.opcode for instruction in program.instructions)

    assert report.passed is True
    assert report.issues == ()
    assert opcodes == (
        MILOpcode.CHECK_POLICY,
        MILOpcode.CALL_CAPABILITY,
        MILOpcode.VERIFY_EFFECT,
        MILOpcode.EMIT_PROOF,
    )
    assert program.instructions[1].depends_on == ("check-policy",)
    assert program.instructions[2].depends_on == ("call-capability",)


def test_compiler_preserves_denied_policy_for_fail_closed_verification() -> None:
    program, report = compile_and_verify_mil_from_policy_decision(
        decision=_decision(PolicyDecisionStatus.DENY),
        program_id="mil:goal-invoice-denied",
        capability="financial.send_payment",
        issued_at=ISSUED_AT,
    )
    codes = {issue.code for issue in report.issues}

    assert program.whqr_allowed is False
    assert report.passed is False
    assert "whqr_not_allowed" in codes
    assert program.instructions[1].subject == "financial.send_payment"


def test_compiler_records_capability_and_effect_subject() -> None:
    program = compile_mil_from_policy_decision(
        decision=_decision(PolicyDecisionStatus.ALLOW),
        program_id="mil:goal-message",
        capability="enterprise.notification_send",
        issued_at=ISSUED_AT,
        effect_subject="message_sent",
    )

    assert program.metadata["compiler"] == "whqr_policy_mil_compiler"
    assert program.metadata["capability"] == "enterprise.notification_send"
    assert program.instructions[2].subject == "message_sent"
    assert program.instructions[3].arguments["effect_subject"] == "message_sent"
