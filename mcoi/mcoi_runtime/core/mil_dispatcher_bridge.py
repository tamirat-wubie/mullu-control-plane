"""Purpose: dispatch statically verified MIL programs through the governed dispatcher.
Governance scope: MIL may request execution only after WHQR allow, static MIL verification, and governed dispatch gates pass.
Dependencies: MIL contracts, MIL static verifier, dispatcher, and governed dispatcher.
Invariants: this bridge never executes directly; it only builds governed dispatch context for the certified dispatcher boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from mcoi_runtime.contracts.mil import MILInstruction, MILOpcode, MILProgram
from mcoi_runtime.core.dispatcher import DispatchRequest
from mcoi_runtime.core.governed_dispatcher import GovernedDispatchContext, GovernedDispatchResult, GovernedDispatcher
from mcoi_runtime.core.mil_static_verifier import MILStaticReport, verify_mil_program


@dataclass(frozen=True, slots=True)
class MILDispatchPreparation:
    program: MILProgram
    verification: MILStaticReport
    context: GovernedDispatchContext | None
    ready: bool
    reason: str


def prepare_mil_dispatch(
    program: MILProgram,
    *,
    actor_id: str,
    intent_id: str,
    template: Mapping[str, Any],
    bindings: Mapping[str, str],
    mode: str = "simulation",
) -> MILDispatchPreparation:
    report = verify_mil_program(program)
    if not report.passed:
        return MILDispatchPreparation(program, report, None, False, "mil_static_verification_failed")
    call_instruction = _single_call_instruction(program)
    if call_instruction is None:
        return MILDispatchPreparation(program, report, None, False, "missing_call_capability")
    request = DispatchRequest(
        goal_id=program.goal_id,
        route=call_instruction.subject,
        template=template,
        bindings=bindings,
    )
    context = GovernedDispatchContext(
        actor_id=actor_id,
        intent_id=intent_id,
        request=request,
        mode=mode,
    )
    return MILDispatchPreparation(program, report, context, True, "ready")


def dispatch_verified_mil(
    program: MILProgram,
    governed: GovernedDispatcher,
    *,
    actor_id: str,
    intent_id: str,
    template: Mapping[str, Any],
    bindings: Mapping[str, str],
    mode: str = "simulation",
) -> GovernedDispatchResult:
    prepared = prepare_mil_dispatch(
        program,
        actor_id=actor_id,
        intent_id=intent_id,
        template=template,
        bindings=bindings,
        mode=mode,
    )
    if not prepared.ready or prepared.context is None:
        raise ValueError(prepared.reason)
    return governed.governed_dispatch(prepared.context)


def _single_call_instruction(program: MILProgram) -> MILInstruction | None:
    calls = tuple(instruction for instruction in program.instructions if instruction.opcode is MILOpcode.CALL_CAPABILITY)
    if len(calls) != 1:
        return None
    return calls[0]
