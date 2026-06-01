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
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Mapping
from mcoi_runtime.core.dispatcher import DispatchRequest
from mcoi_runtime.core.command_capability_admission import (
    CommandCapabilityAdmissionGate,
)
from mcoi_runtime.core.governed_dispatcher import (
    GovernedDispatcher,
    GovernedDispatchContext,
)
from mcoi_runtime.core.invariants import stable_identifier
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
    build_universal_action_orchestration_record,
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


@dataclass(frozen=True, slots=True)
class UniversalCommandProofView:
    """Replayable read model for a command's universal action proof chain."""

    command_id: str
    action_id: str
    blocked: bool
    block_reason: str
    action_envelope: Mapping[str, Any]
    trace_ref: str
    admission_receipt_ref: str
    execution_receipt_ref: str | None
    closure_state: str
    proof_hash: str
    capability_id: str
    dispatch_ledger_hash: str
    terminal_certificate_id: str
    terminal_disposition: str
    learning_admission_id: str
    learning_status: str
    event_hashes: tuple[str, ...]
    state_sequence: tuple[str, ...]


_UAO_REPLAY_EVENT_CAUSES = frozenset(
    {
        "universal_action_kernel_dispatched",
        "universal_action_kernel_blocked",
    }
)
_UAO_DECISION_STATUSES = frozenset({"allow", "block", "defer", "escalate", "simulate"})
_UAO_CLOSURE_BY_DECISION = {
    "allow": "closed_allowed",
    "block": "closed_blocked",
    "defer": "closed_deferred",
    "escalate": "closed_escalated",
    "simulate": "closed_simulated",
}
_UAO_RECEIPT_KINDS = frozenset(
    {
        "admission",
        "trace",
        "execution",
        "provider",
        "reconciliation",
        "closure",
        "simulation",
    }
)
_UAO_BASE_REQUIRED_RECEIPT_KINDS = frozenset({"trace", "admission", "closure"})
_UAO_ALLOW_REQUIRED_RECEIPT_KINDS = _UAO_BASE_REQUIRED_RECEIPT_KINDS | frozenset(
    {"execution", "reconciliation"}
)
_UAO_RECEIPT_TIER_BY_KIND = {
    "trace": frozenset({"R1"}),
    "admission": frozenset({"R1"}),
    "execution": frozenset({"R2"}),
    "reconciliation": frozenset({"R2", "R3"}),
    "closure": frozenset({"R1", "R3"}),
}
_PROHIBITED_UAO_PRIVATE_REASONING_FIELDS = frozenset(
    {
        "chain_of_thought",
        "raw_chain_of_thought",
        "private_reasoning",
        "hidden_reasoning",
        "scratchpad",
    }
)


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
        from mcoi_runtime.adapters.executor_base import (
            build_failure_result,
            ExecutionFailure,
            utc_now_text,
        )

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
    actor_roles: tuple[str, ...] = (),
    approval_refs: tuple[str, ...] = (),
    evidence_refs: tuple[str, ...] = (),
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
    action_request = _build_universal_action_request(
        actor_id=actor_id,
        tenant_id=tenant_id,
        intent_id=intent_id,
        objective=objective,
        request=request,
        risk_level=risk_level,
        estimated_cost=estimated_cost,
        estimated_duration_seconds=estimated_duration_seconds,
        success_probability=success_probability,
        mode=mode,
        actor_roles=actor_roles,
        approval_refs=approval_refs,
        evidence_refs=evidence_refs,
    )
    return kernel.run(action_request)


def universal_command_dispatch(
    command_ledger: object,
    kernel: UniversalActionKernel,
    command_id: str,
    *,
    template: Mapping[str, Any],
    bindings: Mapping[str, str] | None = None,
    dispatch_route: str = "",
    mode: str = "simulation",
    actor_roles: tuple[str, ...] = (),
    approval_refs: tuple[str, ...] = (),
    evidence_refs: tuple[str, ...] = (),
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

    dispatch_request = DispatchRequest(
        goal_id=command.command_id,
        route=dispatch_route or action.capability,
        template=template,
        bindings=dict(bindings or {}),
    )
    action_request = _build_universal_action_request(
        actor_id=command.actor_id,
        tenant_id=command.tenant_id,
        intent_id=command.command_id,
        objective=f"Execute command {command.intent} through the universal action kernel.",
        request=dispatch_request,
        risk_level=_risk_level_from_tier(action.risk_tier),
        mode=mode,
        actor_roles=actor_roles,
        approval_refs=approval_refs,
        evidence_refs=evidence_refs,
    )
    result = kernel.run(action_request)
    orchestration_record = build_universal_action_orchestration_record(
        request=action_request,
        result=result,
    )
    command_ledger.transition(
        command.command_id,
        CommandState.DISPATCHED if result.dispatched else CommandState.REQUIRES_REVIEW,
        risk_tier=action.risk_tier,
        tool_name=action.capability,
        output={"universal_action_proof": result.proof_hash},
        detail={
            "cause": "universal_action_kernel_dispatched"
            if result.dispatched
            else "universal_action_kernel_blocked",
            "universal_action": _universal_action_transition_detail(result),
            "universal_action_orchestration": orchestration_record,
        },
    )
    if result.terminal_certificate is not None:
        command_ledger.transition(
            command.command_id,
            CommandState.TERMINALLY_CERTIFIED,
            risk_tier=action.risk_tier,
            tool_name=action.capability,
            output={
                "terminal_certificate_id": result.terminal_certificate.certificate_id
            },
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


def universal_command_proof_view(
    command_ledger: object,
    command_id: str,
) -> UniversalCommandProofView | None:
    """Reconstruct the universal action proof chain from command events.

    The read model intentionally relies only on persisted command events. It can
    therefore answer audit/read-path questions after a process restart without
    requiring the in-memory UniversalActionResult object.
    """
    events = command_ledger.events_for(command_id)
    if not events:
        return None

    universal_detail: Mapping[str, Any] | None = None
    terminal_certificate_id = ""
    terminal_disposition = ""
    learning_admission_id = ""
    learning_status = ""
    event_hashes: list[str] = []
    state_sequence: list[str] = []

    for event in events:
        event_hash = str(getattr(event, "event_hash", ""))
        if event_hash:
            event_hashes.append(event_hash)
        next_state = getattr(event, "next_state", "")
        state_value = str(getattr(next_state, "value", next_state))
        if state_value:
            state_sequence.append(state_value)
        detail = getattr(event, "detail", {})
        if not isinstance(detail, Mapping):
            continue
        candidate = detail.get("universal_action")
        if isinstance(candidate, Mapping):
            universal_detail = candidate
        if isinstance(detail.get("terminal_certificate_id"), str):
            terminal_certificate_id = str(detail["terminal_certificate_id"])
            terminal_disposition = str(detail.get("terminal_disposition", ""))
        if isinstance(detail.get("learning_admission_id"), str):
            learning_admission_id = str(detail["learning_admission_id"])
            learning_status = str(detail.get("learning_status", ""))

    if universal_detail is None:
        return None

    return UniversalCommandProofView(
        command_id=command_id,
        action_id=str(universal_detail.get("action_id", "")),
        blocked=bool(universal_detail.get("blocked", False)),
        block_reason=str(universal_detail.get("block_reason", "")),
        action_envelope=_mapping_detail(universal_detail.get("action_envelope")),
        trace_ref=str(universal_detail.get("trace_ref", "")),
        admission_receipt_ref=str(universal_detail.get("admission_receipt_ref", "")),
        execution_receipt_ref=_optional_text_detail(
            universal_detail.get("execution_receipt_ref")
        ),
        closure_state=str(universal_detail.get("closure_state", "")),
        proof_hash=str(universal_detail.get("proof_hash", "")),
        capability_id=str(universal_detail.get("capability_id", "")),
        dispatch_ledger_hash=str(universal_detail.get("dispatch_ledger_hash", "")),
        terminal_certificate_id=terminal_certificate_id
        or str(universal_detail.get("terminal_certificate_id", "")),
        terminal_disposition=terminal_disposition,
        learning_admission_id=learning_admission_id
        or str(universal_detail.get("learning_admission_id", "")),
        learning_status=learning_status,
        event_hashes=tuple(event_hashes),
        state_sequence=tuple(state_sequence),
    )


def universal_command_orchestration_record_view(
    command_ledger: object,
    command_id: str,
) -> Mapping[str, Any] | None:
    """Replay one validated persisted UAO v1 orchestration record for a command."""
    command_binding = _command_replay_binding(command_ledger, command_id)
    if command_binding is None:
        return None
    bound_command_id, bound_tenant_id, bound_actor_id = command_binding
    events = command_ledger.events_for(command_id)
    for event in reversed(events):
        if not _event_binds_command_replay(
            event,
            command_id=bound_command_id,
            tenant_id=bound_tenant_id,
            actor_id=bound_actor_id,
        ):
            continue
        detail = getattr(event, "detail", {})
        if not isinstance(detail, Mapping):
            continue
        if detail.get("cause") not in _UAO_REPLAY_EVENT_CAUSES:
            continue
        universal_detail = detail.get("universal_action")
        candidate = detail.get("universal_action_orchestration")
        if _is_replayable_universal_action_orchestration_record(
            candidate,
            universal_detail=universal_detail,
            command_id=bound_command_id,
            tenant_id=bound_tenant_id,
            actor_id=bound_actor_id,
        ):
            return deepcopy(dict(candidate))
    return None


def _command_replay_binding(
    command_ledger: object,
    command_id: str,
) -> tuple[str, str, str] | None:
    if not _non_empty_text(command_id):
        return None
    get_command = getattr(command_ledger, "get", None)
    if not callable(get_command):
        return None
    command = get_command(command_id)
    if command is None:
        return None
    bound_command_id = getattr(command, "command_id", "")
    tenant_id = getattr(command, "tenant_id", "")
    actor_id = getattr(command, "actor_id", "")
    if bound_command_id != command_id:
        return None
    if not _non_empty_text(tenant_id) or not _non_empty_text(actor_id):
        return None
    return command_id, tenant_id, actor_id


def _event_binds_command_replay(
    event: Any,
    *,
    command_id: str,
    tenant_id: str,
    actor_id: str,
) -> bool:
    return (
        getattr(event, "command_id", "") == command_id
        and getattr(event, "tenant_id", "") == tenant_id
        and getattr(event, "actor_id", "") == actor_id
    )


def _is_replayable_universal_action_orchestration_record(
    value: Any,
    *,
    universal_detail: Any,
    command_id: str,
    tenant_id: str,
    actor_id: str,
) -> bool:
    """Return true when a persisted UAO record is safe for read-model replay."""

    if not isinstance(value, Mapping):
        return False
    if _has_private_reasoning_field(value):
        return False
    if value.get("uao_schema_version") != "uao.v1":
        return False
    if value.get("raw_reasoning_included") is not False:
        return False
    if value.get("tenant_id") != tenant_id:
        return False
    if value.get("actor_id") != actor_id:
        return False
    for field_name in (
        "orchestration_id",
        "action_id",
        "tenant_id",
        "actor_id",
        "created_at",
        "trace_ref",
        "causal_decision_trace_ref",
        "admission_receipt_ref",
        "closure_state",
    ):
        if not _non_empty_text(value.get(field_name)):
            return False
    if value.get("trace_ref") != value.get("causal_decision_trace_ref"):
        return False
    action_envelope = value.get("action_envelope")
    if not isinstance(action_envelope, Mapping):
        return False
    if action_envelope.get("actor") != value.get("actor_id"):
        return False
    if action_envelope.get("tenant") != value.get("tenant_id"):
        return False
    if action_envelope.get("intent") != command_id:
        return False
    if action_envelope.get("requested_at") != value.get("created_at"):
        return False
    for field_name in (
        "source",
        "actor",
        "tenant",
        "intent",
        "target",
        "risk",
        "requested_at",
    ):
        if not _non_empty_text(action_envelope.get(field_name)):
            return False
    decision = value.get("decision")
    if not isinstance(decision, Mapping):
        return False
    decision_status = decision.get("status")
    if decision_status not in _UAO_DECISION_STATUSES:
        return False
    if not isinstance(decision.get("execution_allowed"), bool):
        return False
    if decision_status == "allow" and decision.get("execution_allowed") is not True:
        return False
    if decision_status != "allow" and decision.get("execution_allowed") is not False:
        return False
    closure_state = value.get("closure_state")
    if closure_state != _UAO_CLOSURE_BY_DECISION.get(str(decision_status)):
        return False
    closure = value.get("closure")
    if not isinstance(closure, Mapping) or closure.get("status") != closure_state:
        return False
    if not _uao_record_binds_universal_detail(value, universal_detail):
        return False
    stages_by_kind = _uao_stage_records_by_kind(value.get("pipeline_stages"))
    if stages_by_kind is None:
        return False
    receipts = value.get("receipts")
    receipts_by_kind = _uao_receipt_records_by_kind(receipts)
    if receipts_by_kind is None:
        return False
    required_receipt_kinds = (
        _UAO_ALLOW_REQUIRED_RECEIPT_KINDS
        if decision_status == "allow"
        else _UAO_BASE_REQUIRED_RECEIPT_KINDS
    )
    if not required_receipt_kinds.issubset(receipts_by_kind):
        return False
    if not _uao_receipt_binds_stage(
        receipts_by_kind=receipts_by_kind,
        stages_by_kind=stages_by_kind,
        kind="trace",
        expected_receipt_id=None,
        expected_output_ref=value.get("trace_ref"),
    ):
        return False
    if not _uao_receipt_binds_stage(
        receipts_by_kind=receipts_by_kind,
        stages_by_kind=stages_by_kind,
        kind="admission",
        expected_receipt_id=value.get("admission_receipt_ref"),
    ):
        return False
    if not _uao_receipt_binds_stage(
        receipts_by_kind=receipts_by_kind,
        stages_by_kind=stages_by_kind,
        kind="closure",
        expected_receipt_id=closure.get("closure_receipt_ref"),
    ):
        return False
    execution_receipt_ref = value.get("execution_receipt_ref")
    if decision_status == "allow":
        return (
            _non_empty_text(execution_receipt_ref)
            and _uao_receipt_binds_stage(
                receipts_by_kind=receipts_by_kind,
                stages_by_kind=stages_by_kind,
                kind="execution",
                expected_receipt_id=execution_receipt_ref,
            )
            and _uao_receipt_binds_stage(
                receipts_by_kind=receipts_by_kind,
                stages_by_kind=stages_by_kind,
                kind="reconciliation",
                expected_receipt_id=None,
            )
        )
    if execution_receipt_ref is not None:
        return False
    for skipped_kind in ("execution", "reconciliation"):
        stage = stages_by_kind.get(skipped_kind)
        if isinstance(stage, Mapping) and stage.get("receipt_ref") is not None:
            return False
        if skipped_kind in receipts_by_kind:
            return False
    return True


def _uao_record_binds_universal_detail(
    record: Mapping[str, Any], universal_detail: Any
) -> bool:
    if not isinstance(universal_detail, Mapping):
        return False
    for field_name in (
        "action_id",
        "trace_ref",
        "admission_receipt_ref",
        "execution_receipt_ref",
        "closure_state",
    ):
        if record.get(field_name) != universal_detail.get(field_name):
            return False
    universal_envelope = universal_detail.get("action_envelope")
    record_envelope = record.get("action_envelope")
    if not isinstance(universal_envelope, Mapping) or not isinstance(
        record_envelope, Mapping
    ):
        return False
    for field_name in (
        "source",
        "actor",
        "tenant",
        "intent",
        "target",
        "risk",
        "requested_at",
        "approval_ref",
    ):
        if record_envelope.get(field_name) != universal_envelope.get(field_name):
            return False
    if _text_tuple(record_envelope.get("evidence_refs")) != _text_tuple(
        universal_envelope.get("evidence_refs")
    ):
        return False
    universal_capability_refs = set(
        _text_tuple(universal_envelope.get("capability_refs"))
    )
    record_capability_refs = set(_text_tuple(record_envelope.get("capability_refs")))
    if not universal_capability_refs.issubset(record_capability_refs):
        return False
    proof_hash = universal_detail.get("proof_hash")
    if not _non_empty_text(proof_hash):
        return False
    expected_orchestration_id = stable_identifier(
        "universal-action-orchestration",
        {
            "action_id": record.get("action_id"),
            "proof_hash": proof_hash,
            "trace_ref": record.get("trace_ref"),
        },
    )
    if record.get("orchestration_id") != expected_orchestration_id:
        return False
    lineage = record.get("lineage")
    if not isinstance(lineage, Mapping):
        return False
    expected_delta_ref = stable_identifier(
        "universal-action-delta",
        {
            "action_id": record.get("action_id"),
            "proof_hash": proof_hash,
            "closure_state": record.get("closure_state"),
        },
    )
    if lineage.get("delta_ref") != expected_delta_ref:
        return False
    accepted_deltas = lineage.get("accepted_deltas")
    rejected_deltas = lineage.get("rejected_deltas")
    if not isinstance(accepted_deltas, list) or not isinstance(rejected_deltas, list):
        return False
    decision = record.get("decision")
    decision_status = decision.get("status") if isinstance(decision, Mapping) else ""
    if decision_status == "allow" and not accepted_deltas:
        return False
    if decision_status != "allow" and not rejected_deltas:
        return False
    for delta in [*accepted_deltas, *rejected_deltas]:
        if (
            not isinstance(delta, Mapping)
            or delta.get("delta_id") != expected_delta_ref
        ):
            return False
    return True


def _uao_stage_records_by_kind(value: Any) -> dict[str, Mapping[str, Any]] | None:
    if not isinstance(value, list):
        return None
    stages_by_kind: dict[str, Mapping[str, Any]] = {}
    for stage in value:
        if not isinstance(stage, Mapping):
            return None
        stage_kind = stage.get("stage_kind")
        stage_id = stage.get("stage_id")
        if not _non_empty_text(stage_kind) or not _non_empty_text(stage_id):
            return None
        if stage_kind in stages_by_kind:
            return None
        receipt_ref = stage.get("receipt_ref")
        if receipt_ref is not None and not _non_empty_text(receipt_ref):
            return None
        stages_by_kind[str(stage_kind)] = stage
    return stages_by_kind


def _uao_receipt_records_by_kind(value: Any) -> dict[str, Mapping[str, Any]] | None:
    if not isinstance(value, list):
        return None
    receipts_by_kind: dict[str, Mapping[str, Any]] = {}
    for receipt in value:
        if not isinstance(receipt, Mapping):
            return None
        receipt_id = receipt.get("receipt_id")
        kind = receipt.get("kind")
        stage_id = receipt.get("stage_id")
        if not _non_empty_text(receipt_id):
            return None
        if kind not in _UAO_RECEIPT_KINDS or not _non_empty_text(stage_id):
            return None
        if kind in receipts_by_kind:
            return None
        if not _non_empty_text(receipt.get("tier")):
            return None
        if not _non_empty_text(receipt.get("confirms")):
            return None
        if not isinstance(receipt.get("external_state_confirmed"), bool):
            return None
        receipts_by_kind[str(kind)] = receipt
    return receipts_by_kind


def _uao_receipt_binds_stage(
    *,
    receipts_by_kind: Mapping[str, Mapping[str, Any]],
    stages_by_kind: Mapping[str, Mapping[str, Any]],
    kind: str,
    expected_receipt_id: str | None,
    expected_output_ref: str | None = None,
) -> bool:
    receipt = receipts_by_kind.get(kind)
    stage = stages_by_kind.get(kind)
    if receipt is None or stage is None:
        return False
    receipt_id = receipt.get("receipt_id")
    if expected_receipt_id is not None and receipt_id != expected_receipt_id:
        return False
    if receipt.get("stage_id") != stage.get("stage_id"):
        return False
    if stage.get("receipt_ref") != receipt_id:
        return False
    if receipt.get("tier") not in _UAO_RECEIPT_TIER_BY_KIND.get(kind, frozenset()):
        return False
    if expected_output_ref is not None:
        output_refs = stage.get("output_refs")
        if not isinstance(output_refs, list) or expected_output_ref not in output_refs:
            return False
    return True


def _has_private_reasoning_field(value: Any) -> bool:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if key in _PROHIBITED_UAO_PRIVATE_REASONING_FIELDS:
                return True
            if _has_private_reasoning_field(child):
                return True
    elif isinstance(value, list):
        return any(_has_private_reasoning_field(child) for child in value)
    return False


def _non_empty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _text_tuple(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        stripped = value.strip()
        return (stripped,) if stripped else ()
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(
        item.strip() for item in value if isinstance(item, str) and item.strip()
    )


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
        TerminalClosureCertifier(clock=clock) if terminal_closure_enabled else None
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


def _build_universal_action_request(
    *,
    actor_id: str,
    tenant_id: str,
    intent_id: str,
    objective: str,
    request: DispatchRequest,
    risk_level: RiskLevel,
    estimated_cost: float = 100.0,
    estimated_duration_seconds: float = 1.0,
    success_probability: float = 0.9,
    mode: str = "simulation",
    actor_roles: tuple[str, ...] = (),
    approval_refs: tuple[str, ...] = (),
    evidence_refs: tuple[str, ...] = (),
) -> UniversalActionRequest:
    return UniversalActionRequest(
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
        metadata={
            "actor_roles": actor_roles,
            "approval_refs": approval_refs,
            "evidence_refs": evidence_refs,
        },
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


def _universal_action_transition_detail(
    result: UniversalActionResult,
) -> dict[str, Any]:
    return {
        "action_id": result.action_id,
        "blocked": result.blocked,
        "block_reason": result.block_reason,
        "action_envelope": dict(result.action_envelope),
        "trace_ref": result.trace_ref,
        "admission_receipt_ref": result.admission_receipt_ref,
        "execution_receipt_ref": result.execution_receipt_ref,
        "closure_state": result.closure_state,
        "proof_hash": result.proof_hash,
        "goal_certificate_id": result.goal_certificate.certificate_id,
        "world_certificate_id": result.world_certificate.certificate_id,
        "plan_certificate_id": result.plan_certificate.certificate_id
        if result.plan_certificate
        else "",
        "simulation_certificate_id": (
            result.simulation_certificate.certificate_id
            if result.simulation_certificate
            else ""
        ),
        "capability_status": result.capability_decision.status.value
        if result.capability_decision
        else "",
        "capability_id": result.capability_decision.capability_id
        if result.capability_decision
        else "",
        "governed_action_id": result.governed_action.governed_action_id
        if result.governed_action
        else "",
        "dispatch_ledger_hash": result.dispatch_result.ledger_hash
        if result.dispatch_result
        else "",
        "terminal_certificate_id": (
            result.terminal_certificate.certificate_id
            if result.terminal_certificate
            else ""
        ),
        "learning_admission_id": result.learning_decision.admission_id
        if result.learning_decision
        else "",
    }


def _mapping_detail(value: Any) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return dict(value)


def _optional_text_detail(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)


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
        return OperatorMILDispatchResult(
            execution_result, program, verification, instruction_trace
        )
    if result.blocked:
        execution_result = _blocked_execution_result(
            request,
            intent_id=intent_id,
            code="governed_dispatch_blocked",
            message=result.block_reason,
            gates_failed=tuple(gate.gate_name for gate in result.gates_failed),
        )
        return OperatorMILDispatchResult(
            execution_result, program, verification, instruction_trace
        )
    return OperatorMILDispatchResult(
        result.execution_result, program, verification, instruction_trace
    )


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
    from mcoi_runtime.adapters.executor_base import (
        build_failure_result,
        ExecutionFailure,
        utc_now_text,
    )

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
