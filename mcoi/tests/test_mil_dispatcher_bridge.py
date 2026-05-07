"""Purpose: verify statically approved MIL programs enter execution only through governed dispatch.
Governance scope: MIL dispatch bridge preserves WHQR allow, static verification, and governed dispatcher gates.
Dependencies: MIL dispatch bridge, governed dispatcher, dispatcher, and MIL verifier.
Invariants: no direct worker execution; malformed MIL fails before governed dispatch.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from mcoi_runtime.adapters.executor_base import ExecutionRequest
from mcoi_runtime.contracts.execution import EffectRecord, ExecutionOutcome, ExecutionResult
from mcoi_runtime.contracts.mil import MILInstruction, MILOpcode, MILProgram
from mcoi_runtime.contracts.policy import DecisionReason, PolicyDecision, PolicyDecisionStatus
from mcoi_runtime.core.dispatcher import Dispatcher
from mcoi_runtime.core.governed_dispatcher import GovernedDispatcher
from mcoi_runtime.core.mil_dispatcher_bridge import dispatch_verified_mil, prepare_mil_dispatch
from mcoi_runtime.core.system_stabilization import EquilibriumEngine
from mcoi_runtime.core.template_validator import TemplateValidator


VALID_TEMPLATE = {
    "template_id": "tpl-command",
    "action_type": "shell_command",
    "command_argv": ("echo", "{invoice}"),
    "required_parameters": ("invoice",),
}


def fixed_clock() -> str:
    return "2026-05-05T10:00:00+00:00"


@dataclass
class FakeExecutor:
    calls: int = 0

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        self.calls += 1
        return ExecutionResult(
            request.execution_id,
            request.goal_id,
            ExecutionOutcome.SUCCEEDED,
            (EffectRecord("command_dispatched", {"argv": list(request.argv)}),),
            (),
            "2026-05-05T10:00:00+00:00",
            "2026-05-05T10:00:01+00:00",
        )


def _governed() -> tuple[GovernedDispatcher, FakeExecutor]:
    executor = FakeExecutor()
    dispatcher = Dispatcher(TemplateValidator(), {"shell_command": executor}, fixed_clock)
    equilibrium = EquilibriumEngine()
    equilibrium.register_agent("operator")
    return GovernedDispatcher(dispatcher, equilibrium=equilibrium, clock=fixed_clock), executor


def _allowed_decision() -> PolicyDecision:
    return PolicyDecision(
        "whqr:goal-command:allow",
        "operator",
        "goal-command",
        PolicyDecisionStatus.ALLOW,
        (DecisionReason("allowed", "whqr_allow"),),
        "2026-05-05T10:00:00Z",
    )


def _program() -> MILProgram:
    return MILProgram(
        "mil:goal-command",
        "goal-command",
        _allowed_decision(),
        (
            MILInstruction("check", MILOpcode.CHECK_POLICY, "goal-command"),
            MILInstruction("call", MILOpcode.CALL_CAPABILITY, "shell_command", depends_on=("check",)),
            MILInstruction("verify", MILOpcode.VERIFY_EFFECT, "shell_command", depends_on=("call",)),
            MILInstruction("proof", MILOpcode.EMIT_PROOF, "goal-command", depends_on=("verify",)),
        ),
        "2026-05-05T10:00:01Z",
    )


def test_verified_mil_dispatches_through_governed_dispatcher() -> None:
    governed, executor = _governed()

    result = dispatch_verified_mil(
        _program(),
        governed,
        actor_id="operator",
        intent_id="intent-command",
        template=VALID_TEMPLATE,
        bindings={"invoice": "INV-1"},
    )

    assert result.blocked is False
    assert result.execution_result is not None
    assert result.execution_result.status is ExecutionOutcome.SUCCEEDED
    assert executor.calls == 1
    assert result.ledger_hash != ""


def test_prepare_mil_dispatch_fails_closed_on_static_failure() -> None:
    denied = PolicyDecision(
        "whqr:goal-command:deny",
        "operator",
        "goal-command",
        PolicyDecisionStatus.DENY,
        (DecisionReason("denied", "whqr_deny"),),
        "2026-05-05T10:00:00Z",
    )
    program = MILProgram(
        "mil:bad",
        "goal-command",
        denied,
        (MILInstruction("call", MILOpcode.CALL_CAPABILITY, "shell_command"),),
        "2026-05-05T10:00:01Z",
    )

    prepared = prepare_mil_dispatch(
        program,
        actor_id="operator",
        intent_id="intent-command",
        template=VALID_TEMPLATE,
        bindings={"invoice": "INV-1"},
    )

    assert prepared.ready is False
    assert prepared.context is None
    assert prepared.reason == "mil_static_verification_failed"
    assert prepared.verification.passed is False


def test_dispatch_verified_mil_rejects_program_without_call_capability() -> None:
    program = MILProgram(
        "mil:no-call",
        "goal-command",
        _allowed_decision(),
        (
            MILInstruction("check", MILOpcode.CHECK_POLICY, "goal-command"),
            MILInstruction("verify", MILOpcode.VERIFY_EFFECT, "goal-command", depends_on=("check",)),
            MILInstruction("proof", MILOpcode.EMIT_PROOF, "goal-command", depends_on=("verify",)),
        ),
        "2026-05-05T10:00:01Z",
    )
    governed, _executor = _governed()

    with pytest.raises(ValueError, match="mil_static_verification_failed"):
        dispatch_verified_mil(
            program,
            governed,
            actor_id="operator",
            intent_id="intent-command",
            template=VALID_TEMPLATE,
            bindings={"invoice": "INV-1"},
        )
