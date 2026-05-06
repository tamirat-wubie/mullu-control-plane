"""Phase 195B — Governed Execution Bridge for Operator Loop.

Purpose: Provides a governed dispatch wrapper that operator code can call
    with minimal interface change, bridging the operator model to governed execution.
Governance scope: operator skill/workflow/goal execution paths.
Dependencies: governed_dispatcher, dispatcher, MIL compiler, and MIL dispatch bridge.
Invariants: all operator dispatches flow through governed spine.
"""
from __future__ import annotations
from dataclasses import dataclass
from mcoi_runtime.core.dispatcher import DispatchRequest
from mcoi_runtime.core.governed_dispatcher import (
    GovernedDispatcher, GovernedDispatchContext,
)
from mcoi_runtime.contracts.execution import ExecutionResult
from mcoi_runtime.contracts.mil import MILProgram
from mcoi_runtime.contracts.policy import PolicyDecision
from mcoi_runtime.core.mil_dispatcher_bridge import dispatch_verified_mil
from mcoi_runtime.core.mil_static_verifier import MILStaticReport, verify_mil_program
from mcoi_runtime.whqr.mil_compiler import compile_mil_from_policy_decision

# Module-level counter for unique intent IDs (avoids collision with fixed clocks)
_intent_counter: list[int] = [0]


@dataclass(frozen=True, slots=True)
class OperatorMILDispatchResult:
    execution_result: ExecutionResult
    program: MILProgram
    verification: MILStaticReport
    instruction_trace: tuple[str, ...]


def governed_operator_dispatch(
    governed: GovernedDispatcher,
    request: DispatchRequest,
    *,
    actor_id: str = "operator",
    intent_id: str = "",
    mode: str = "simulation",
) -> ExecutionResult:
    """Drop-in replacement for raw dispatcher.dispatch() in operator code.

    Returns ExecutionResult for backward compatibility, but routes through
    the full governed pipeline (identity, prediction, economics, equilibrium,
    promotion, verification, ledger).
    """
    import hashlib
    from datetime import datetime, timezone

    if not intent_id:
        # Generate unique intent ID using counter to avoid collisions with fixed clocks
        _intent_counter[0] += 1
        raw = f"{actor_id}:{request.goal_id}:{request.route}:{_intent_counter[0]}:{datetime.now(timezone.utc).isoformat()}"
        intent_id = f"op-intent-{hashlib.sha256(raw.encode()).hexdigest()[:12]}"

    context = GovernedDispatchContext(
        actor_id=actor_id,
        intent_id=intent_id,
        request=request,
        mode=mode,
    )

    result = governed.governed_dispatch(context)

    if result.blocked:
        # Return a failure result that matches operator expectations
        from mcoi_runtime.adapters.executor_base import build_failure_result, ExecutionFailure, utc_now_text
        now = utc_now_text()
        return build_failure_result(
            execution_id=f"gov-blocked-{intent_id}",
            goal_id=request.goal_id,
            started_at=now,
            finished_at=now,
            failure=ExecutionFailure(
                code="governed_dispatch_blocked",
                message=result.block_reason,
            ),
            effect_name="governance_blocked",
            metadata={"gates_failed": [g.gate_name for g in result.gates_failed]},
        )

    return result.execution_result


def governed_operator_mil_dispatch(
    governed: GovernedDispatcher,
    request: DispatchRequest,
    *,
    policy_decision: PolicyDecision,
    issued_at: str,
    actor_id: str = "operator",
    intent_id: str = "",
    mode: str = "simulation",
) -> ExecutionResult:
    """Dispatch an operator request through MIL verification before governed execution."""
    return governed_operator_mil_dispatch_with_trace(
        governed,
        request,
        policy_decision=policy_decision,
        issued_at=issued_at,
        actor_id=actor_id,
        intent_id=intent_id,
        mode=mode,
    ).execution_result


def governed_operator_mil_dispatch_with_trace(
    governed: GovernedDispatcher,
    request: DispatchRequest,
    *,
    policy_decision: PolicyDecision,
    issued_at: str,
    actor_id: str = "operator",
    intent_id: str = "",
    mode: str = "simulation",
) -> OperatorMILDispatchResult:
    """Dispatch through MIL and return the compiled program plus verifier proof."""
    if not intent_id:
        intent_id = _derive_intent_id(actor_id, request)
    program = compile_mil_from_policy_decision(
        decision=policy_decision,
        program_id=f"mil:{request.goal_id}:{request.route}",
        capability=request.route,
        issued_at=issued_at,
        effect_subject=request.route,
    )
    verification = verify_mil_program(program)
    instruction_trace = _instruction_trace(program)
    try:
        result = dispatch_verified_mil(
            program,
            governed,
            actor_id=actor_id,
            intent_id=intent_id,
            template=request.template,
            bindings=request.bindings,
            mode=mode,
        )
    except ValueError as exc:
        execution_result = _blocked_execution_result(
            request,
            intent_id=intent_id,
            code="mil_static_verification_blocked",
            message=str(exc),
            gates_failed=("mil_static_verification",),
        )
        return OperatorMILDispatchResult(execution_result, program, verification, instruction_trace)
    if result.blocked:
        execution_result = _blocked_execution_result(
            request,
            intent_id=intent_id,
            code="governed_dispatch_blocked",
            message=result.block_reason,
            gates_failed=tuple(gate.gate_name for gate in result.gates_failed),
        )
        return OperatorMILDispatchResult(execution_result, program, verification, instruction_trace)
    return OperatorMILDispatchResult(result.execution_result, program, verification, instruction_trace)


def _derive_intent_id(actor_id: str, request: DispatchRequest) -> str:
    import hashlib
    from datetime import datetime, timezone

    _intent_counter[0] += 1
    raw = f"{actor_id}:{request.goal_id}:{request.route}:{_intent_counter[0]}:{datetime.now(timezone.utc).isoformat()}"
    return f"op-intent-{hashlib.sha256(raw.encode()).hexdigest()[:12]}"


def _blocked_execution_result(
    request: DispatchRequest,
    *,
    intent_id: str,
    code: str,
    message: str,
    gates_failed: tuple[str, ...],
) -> ExecutionResult:
    from mcoi_runtime.adapters.executor_base import build_failure_result, ExecutionFailure, utc_now_text

    now = utc_now_text()
    return build_failure_result(
        execution_id=f"gov-blocked-{intent_id}",
        goal_id=request.goal_id,
        started_at=now,
        finished_at=now,
        failure=ExecutionFailure(code=code, message=message),
        effect_name="governance_blocked",
        metadata={"gates_failed": list(gates_failed)},
    )


def _instruction_trace(program: MILProgram) -> tuple[str, ...]:
    return tuple(
        f"{instruction.instruction_id}:{instruction.opcode.value}:{instruction.subject}"
        for instruction in program.instructions
    )
