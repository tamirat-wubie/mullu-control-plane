"""Phase 195B — Governed Execution Bridge for Operator Loop.

Purpose: Provides a governed dispatch wrapper that operator code can call
    with minimal interface change, bridging the operator model to governed execution.
Governance scope: operator skill/workflow/goal execution paths.
Dependencies: governed_dispatcher, dispatcher, universal action kernel, MIL
    compiler, and MIL dispatch bridge.
Invariants: all operator dispatches flow through governed spine or the universal
    action kernel when a configured kernel is supplied.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Mapping
from mcoi_runtime.core.dispatcher import DispatchRequest
from mcoi_runtime.core.command_capability_admission import CommandCapabilityAdmissionGate
from mcoi_runtime.core.governed_dispatcher import (
    GovernedDispatcher, GovernedDispatchContext,
)
from mcoi_runtime.contracts.execution import ExecutionResult
from mcoi_runtime.contracts.mil import MILProgram
from mcoi_runtime.contracts.policy import PolicyDecision
from mcoi_runtime.contracts.simulation import RiskLevel
from mcoi_runtime.core.mil_dispatcher_bridge import dispatch_verified_mil
from mcoi_runtime.core.mil_static_verifier import MILStaticReport, verify_mil_program
from mcoi_runtime.core.universal_action_kernel import (
    UniversalActionKernel,
    UniversalActionRequest,
    UniversalActionResult,
    build_universal_action_kernel,
)
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


def universal_operator_dispatch(
    kernel: UniversalActionKernel,
    request: DispatchRequest,
    *,
    actor_id: str = "operator",
    tenant_id: str = "operator",
    intent_id: str = "",
    objective: str = "",
    risk_level: RiskLevel = RiskLevel.LOW,
    estimated_cost: float = 100.0,
    estimated_duration_seconds: float = 1.0,
    success_probability: float = 0.9,
    mode: str = "simulation",
) -> UniversalActionResult:
    """Dispatch an operator request through the universal governed action path.

    This facade is the narrow runtime entry point for callers that have a
    configured UniversalActionKernel. It preserves the operator call shape while
    returning the full certificate chain instead of only ExecutionResult.
    """
    if not intent_id:
        intent_id = _derive_intent_id(actor_id, request)
    if not objective:
        objective = f"Execute {request.route} for goal {request.goal_id}"
    return kernel.run(
        UniversalActionRequest(
            actor_id=actor_id,
            tenant_id=tenant_id,
            intent_id=intent_id,
            objective=objective,
            dispatch_request=request,
            risk_level=risk_level,
            estimated_cost=estimated_cost,
            estimated_duration_seconds=estimated_duration_seconds,
            success_probability=success_probability,
            mode=mode,
        )
    )


def universal_command_dispatch(
    command_ledger: object,
    kernel: UniversalActionKernel,
    command_id: str,
    *,
    template: Mapping[str, Any],
    bindings: Mapping[str, str] | None = None,
    dispatch_route: str = "",
    mode: str = "simulation",
) -> UniversalActionResult:
    """Dispatch a command-ledger command through the universal action kernel.

    The command spine remains the causal source of tenant, actor, command, and
    intent identity. This function records command transitions around the
    universal kernel result without giving the kernel authority to create or
    mutate commands directly.
    """
    from gateway.command_spine import CommandState

    command = command_ledger.get(command_id)
    if command is None:
        raise KeyError(f"unknown command_id: {command_id}")
    action = command_ledger.governed_action_for(command_id)
    if action is None:
        action = command_ledger.bind_governed_action(command_id)

    request = DispatchRequest(
        goal_id=command.command_id,
        route=dispatch_route or action.capability,
        template=template,
        bindings=dict(bindings or {}),
    )
    result = universal_operator_dispatch(
        kernel,
        request,
        actor_id=command.actor_id,
        tenant_id=command.tenant_id,
        intent_id=command.command_id,
        objective=f"Execute command {command.intent} through the universal action kernel.",
        risk_level=_risk_level_from_tier(action.risk_tier),
        mode=mode,
    )
    command_ledger.transition(
        command.command_id,
        CommandState.DISPATCHED if result.dispatched else CommandState.REQUIRES_REVIEW,
        risk_tier=action.risk_tier,
        tool_name=action.capability,
        output={"universal_action_proof": result.proof_hash},
        detail={
            "cause": "universal_action_kernel_dispatched" if result.dispatched else "universal_action_kernel_blocked",
            "universal_action": _universal_action_transition_detail(result),
        },
    )
    if result.terminal_certificate is not None:
        command_ledger.transition(
            command.command_id,
            CommandState.TERMINALLY_CERTIFIED,
            risk_tier=action.risk_tier,
            tool_name=action.capability,
            output={"terminal_certificate_id": result.terminal_certificate.certificate_id},
            detail={
                "cause": "universal_action_terminal_certificate",
                "terminal_certificate_id": result.terminal_certificate.certificate_id,
                "terminal_disposition": result.terminal_certificate.disposition.value,
                "proof_hash": result.proof_hash,
            },
        )
    if result.learning_decision is not None:
        command_ledger.transition(
            command.command_id,
            CommandState.LEARNING_DECIDED,
            risk_tier=action.risk_tier,
            tool_name=action.capability,
            output={"learning_admission_id": result.learning_decision.admission_id},
            detail={
                "cause": "universal_action_learning_decided",
                "learning_admission_id": result.learning_decision.admission_id,
                "learning_status": result.learning_decision.status.value,
                "proof_hash": result.proof_hash,
            },
        )
    return result


def build_universal_operator_kernel(
    runtime: object,
    *,
    capability_admission_gate: CommandCapabilityAdmissionGate,
    terminal_closure_enabled: bool = True,
    learning_admission_enabled: bool = True,
) -> UniversalActionKernel:
    """Build a universal action kernel from a bootstrapped runtime.

    Capability admission is intentionally supplied by the caller. This prevents
    bootstrap from silently installing or authorizing capabilities.
    """
    from mcoi_runtime.core.closure_learning import ClosureLearningAdmissionGate
    from mcoi_runtime.core.operational_graph import OperationalGraph
    from mcoi_runtime.core.simulation import SimulationEngine
    from mcoi_runtime.core.terminal_closure import TerminalClosureCertifier

    world_state = getattr(runtime, "world_state", None)
    governed_dispatcher = getattr(runtime, "governed_dispatcher", None)
    clock = getattr(runtime, "clock", None)
    if world_state is None:
        raise ValueError("runtime must expose world_state")
    if governed_dispatcher is None:
        raise ValueError("runtime must expose governed_dispatcher")
    if clock is None:
        raise ValueError("runtime must expose clock")

    operational_graph = getattr(runtime, "operational_graph", None)
    if operational_graph is None:
        operational_graph = OperationalGraph(clock=clock)
    simulator = SimulationEngine(graph=operational_graph, clock=clock)
    terminal_closure = (
        TerminalClosureCertifier(clock=clock)
        if terminal_closure_enabled
        else None
    )
    learning_admission = (
        ClosureLearningAdmissionGate(clock=clock)
        if learning_admission_enabled
        else None
    )
    return build_universal_action_kernel(
        world_state=world_state,
        simulator=simulator,
        capability_admission=capability_admission_gate,
        governed_dispatcher=governed_dispatcher,
        terminal_closure=terminal_closure,
        learning_admission=learning_admission,
        clock=clock,
    )


def _risk_level_from_tier(risk_tier: str) -> RiskLevel:
    normalized = risk_tier.strip().lower()
    if normalized in {"critical", "max"}:
        return RiskLevel.CRITICAL
    if normalized == "high":
        return RiskLevel.HIGH
    if normalized in {"medium", "moderate"}:
        return RiskLevel.MODERATE
    if normalized == "minimal":
        return RiskLevel.MINIMAL
    return RiskLevel.LOW


def _universal_action_transition_detail(result: UniversalActionResult) -> dict[str, Any]:
    return {
        "action_id": result.action_id,
        "blocked": result.blocked,
        "block_reason": result.block_reason,
        "proof_hash": result.proof_hash,
        "goal_certificate_id": result.goal_certificate.certificate_id,
        "world_certificate_id": result.world_certificate.certificate_id,
        "plan_certificate_id": result.plan_certificate.certificate_id if result.plan_certificate else "",
        "simulation_certificate_id": (
            result.simulation_certificate.certificate_id if result.simulation_certificate else ""
        ),
        "capability_status": result.capability_decision.status.value if result.capability_decision else "",
        "capability_id": result.capability_decision.capability_id if result.capability_decision else "",
        "dispatch_ledger_hash": result.dispatch_result.ledger_hash if result.dispatch_result else "",
        "terminal_certificate_id": (
            result.terminal_certificate.certificate_id if result.terminal_certificate else ""
        ),
        "learning_admission_id": result.learning_decision.admission_id if result.learning_decision else "",
    }


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
