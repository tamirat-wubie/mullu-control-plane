"""Purpose: verify MIL contracts and static verification gates.
Governance scope: MIL remains immutable pre-execution structure and fails closed before dispatch.
Dependencies: MIL contracts, policy contracts, and MIL static verifier.
Invariants: allow policy, ordered dependencies, effect verification, and terminal proof are required.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.mil import MILInstruction, MILOpcode, MILProgram
from mcoi_runtime.contracts.policy import DecisionReason, PolicyDecision, PolicyDecisionStatus
from mcoi_runtime.core.mil_static_verifier import verify_mil_program


ISSUED_AT = "2026-05-05T10:00:00Z"


def _policy(status: PolicyDecisionStatus) -> PolicyDecision:
    return PolicyDecision(
        decision_id=f"whqr:goal:{status.value}",
        subject_id="operator",
        goal_id="goal",
        status=status,
        reasons=(DecisionReason(status.value, f"whqr_{status.value}"),),
        issued_at=ISSUED_AT,
    )


def _valid_program() -> MILProgram:
    return MILProgram(
        program_id="mil:goal",
        goal_id="goal",
        whqr_decision=_policy(PolicyDecisionStatus.ALLOW),
        instructions=(
            MILInstruction("check", MILOpcode.CHECK_POLICY, "goal"),
            MILInstruction("call", MILOpcode.CALL_CAPABILITY, "shell_command", depends_on=("check",)),
            MILInstruction("verify", MILOpcode.VERIFY_EFFECT, "goal", depends_on=("call",)),
            MILInstruction("proof", MILOpcode.EMIT_PROOF, "goal", depends_on=("verify",)),
        ),
        issued_at=ISSUED_AT,
    )


def test_mil_contract_freezes_and_serializes_program() -> None:
    program = _valid_program()
    payload = program.to_json_dict()

    assert program.whqr_allowed is True
    assert isinstance(program.instructions, tuple)
    assert payload["whqr_decision"]["status"] == "allow"
    assert payload["instructions"][1]["opcode"] == "call_capability"


def test_mil_static_verifier_accepts_ordered_allow_program() -> None:
    report = verify_mil_program(_valid_program())
    codes = {issue.code for issue in report.issues}

    assert report.passed is True
    assert report.issues == ()
    assert codes == set()
    assert len(report.issues) == 0


def test_mil_static_verifier_rejects_non_allow_and_missing_call() -> None:
    program = MILProgram(
        program_id="mil:goal",
        goal_id="goal",
        whqr_decision=_policy(PolicyDecisionStatus.DENY),
        instructions=(
            MILInstruction("check", MILOpcode.CHECK_POLICY, "goal"),
            MILInstruction("verify", MILOpcode.VERIFY_EFFECT, "goal", depends_on=("check",)),
            MILInstruction("proof", MILOpcode.EMIT_PROOF, "goal", depends_on=("verify",)),
        ),
        issued_at=ISSUED_AT,
    )
    report = verify_mil_program(program)
    codes = {issue.code for issue in report.issues}

    assert report.passed is False
    assert "whqr_not_allowed" in codes
    assert "call_capability_count" in codes
    assert "verify_missing_call_dependency" not in codes


def test_mil_static_verifier_rejects_bad_order_and_missing_terminal_proof() -> None:
    program = MILProgram(
        program_id="mil:goal",
        goal_id="goal",
        whqr_decision=_policy(PolicyDecisionStatus.ALLOW),
        instructions=(
            MILInstruction("call", MILOpcode.CALL_CAPABILITY, "shell_command", depends_on=("missing",)),
            MILInstruction("check", MILOpcode.CHECK_POLICY, "goal"),
            MILInstruction("verify", MILOpcode.VERIFY_EFFECT, "goal"),
        ),
        issued_at=ISSUED_AT,
    )
    report = verify_mil_program(program)
    codes = {issue.code for issue in report.issues}

    assert report.passed is False
    assert "unsatisfied_dependency" in codes
    assert "missing_policy_check" in codes
    assert "emit_proof_count" in codes
    assert "verify_missing_call_dependency" in codes


def test_mil_instruction_rejects_invalid_dependency_shape() -> None:
    with pytest.raises(ValueError, match="depends_on"):
        MILInstruction(
            instruction_id="bad",
            opcode=MILOpcode.CHECK_POLICY,
            subject="goal",
            depends_on=["not-a-tuple"],  # type: ignore[arg-type]
        )

    assert MILOpcode.CHECK_POLICY.value == "check_policy"
    assert MILOpcode.EMIT_PROOF.value == "emit_proof"
    assert MILOpcode.CALL_CAPABILITY.value == "call_capability"
