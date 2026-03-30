"""Phase 195B — Governed Execution Bridge for Operator Loop.

Purpose: Provides a governed dispatch wrapper that operator code can call
    with minimal interface change, bridging the operator model to governed execution.
Governance scope: operator skill/workflow/goal execution paths.
Dependencies: governed_dispatcher, dispatcher.
Invariants: all operator dispatches flow through governed spine.
"""
from __future__ import annotations
from mcoi_runtime.core.dispatcher import DispatchRequest
from mcoi_runtime.core.governed_dispatcher import (
    GovernedDispatcher, GovernedDispatchContext,
)
from mcoi_runtime.contracts.execution import ExecutionResult

# Module-level counter for unique intent IDs (avoids collision with fixed clocks)
_intent_counter: list[int] = [0]


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
