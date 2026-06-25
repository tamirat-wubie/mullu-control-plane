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
import json
from typing import Any, Mapping
from mcoi_runtime.core.dispatcher import DispatchRequest
from mcoi_runtime.core.command_capability_admission import (
    CommandCapabilityAdmissionGate,
)
from mcoi_runtime.core.governed_dispatcher import (
    GovernedDispatcher,
    GovernedDispatchContext,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, stable_identifier
from mcoi_runtime.contracts.execution import ExecutionResult
from mcoi_runtime.contracts.mil import MILProgram
from mcoi_runtime.contracts.policy import PolicyDecision
from mcoi_runtime.contracts.simulation import RiskLevel
from mcoi_runtime.contracts.whqr import WHQRDocument
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
    reconciliation_ref: str
    memory_ref: str
    life_meaning_judgment: Mapping[str, Any]
    whqr_replay_binding: Mapping[str, Any]
    proof_hash: str
    capability_id: str
    dispatch_ledger_hash: str
    terminal_certificate_id: str
    terminal_disposition: str
    learning_admission_id: str
    learning_status: str
    event_hashes: tuple[str, ...]
    state_sequence: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _CommandReplayBinding:
    command_id: str
    tenant_id: str
    actor_id: str
    source_channel: str
    idempotency_key: str
    policy_version: str
    trace_id: str


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
_WHQR_REPLAY_BINDING_FIELDS = frozenset(
    {"replay_ref", "canonical_hash", "semantics_hash", "version"}
)
_UAO_RECEIPT_TIER_BY_KIND = {
    "trace": frozenset({"R1"}),
    "admission": frozenset({"R1"}),
    "execution": frozenset({"R2"}),
    "reconciliation": frozenset({"R2", "R3"}),
    "closure": frozenset({"R1", "R3"}),
}
_UAO_CANONICAL_PIPELINE_STAGE_KINDS = (
    "action",
    "evidence",
    "trace",
    "admission",
    "capability",
    "fracture",
    "execution",
    "receipt",
    "reconciliation",
    "memory",
    "closure",
)
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
    approval_actor_ids: tuple[str, ...] = (),
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
        approval_actor_ids=approval_actor_ids,
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
    approval_actor_ids: tuple[str, ...] = (),
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
        approval_actor_ids=approval_actor_ids,
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
    whqr_replay_binding = _normalized_whqr_replay_binding(
        universal_detail.get("whqr_replay_binding")
    )
    if whqr_replay_binding is None:
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
        reconciliation_ref=_text_detail(universal_detail.get("reconciliation_ref")),
        memory_ref=_text_detail(universal_detail.get("memory_ref")),
        life_meaning_judgment=_mapping_detail(
            universal_detail.get("life_meaning_judgment")
        ),
        whqr_replay_binding=whqr_replay_binding,
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
    events = command_ledger.events_for(command_id)
    for event in reversed(events):
        if not _event_binds_command_replay(
            event,
            binding=command_binding,
        ):
            continue
        if not _event_hash_binds_payload(event):
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
            command_id=command_binding.command_id,
            tenant_id=command_binding.tenant_id,
            actor_id=command_binding.actor_id,
        ):
            return deepcopy(dict(candidate))
    return None


def _command_replay_binding(
    command_ledger: object,
    command_id: str,
) -> _CommandReplayBinding | None:
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
    source_channel = getattr(command, "source", "")
    idempotency_key = getattr(command, "idempotency_key", "")
    policy_version = getattr(command, "policy_version", "")
    trace_id = getattr(command, "trace_id", "")
    if bound_command_id != command_id:
        return None
    for value in (
        tenant_id,
        actor_id,
        source_channel,
        idempotency_key,
        policy_version,
        trace_id,
    ):
        if not _non_empty_text(value):
            return None
    return _CommandReplayBinding(
        command_id=command_id,
        tenant_id=tenant_id,
        actor_id=actor_id,
        source_channel=source_channel,
        idempotency_key=idempotency_key,
        policy_version=policy_version,
        trace_id=trace_id,
    )


def _event_binds_command_replay(
    event: Any,
    *,
    binding: _CommandReplayBinding,
) -> bool:
    return (
        getattr(event, "command_id", "") == binding.command_id
        and getattr(event, "tenant_id", "") == binding.tenant_id
        and getattr(event, "actor_id", "") == binding.actor_id
        and getattr(event, "source_channel", "") == binding.source_channel
        and getattr(event, "idempotency_key", "") == binding.idempotency_key
        and getattr(event, "policy_version", "") == binding.policy_version
        and getattr(event, "trace_id", "") == binding.trace_id
    )


def _event_hash_binds_payload(event: Any) -> bool:
    event_hash = getattr(event, "event_hash", "")
    event_id = getattr(event, "event_id", "")
    if not _non_empty_text(event_hash) or event_id != f"evt-{event_hash[:16]}":
        return False
    detail = getattr(event, "detail", {})
    if not isinstance(detail, Mapping):
        return False
    try:
        from gateway.command_spine import canonical_hash

        recomputed = canonical_hash(
            {
                "command_id": getattr(event, "command_id", ""),
                "previous_state": _state_text(getattr(event, "previous_state", "")),
                "next_state": _state_text(getattr(event, "next_state", "")),
                "policy_version": getattr(event, "policy_version", ""),
                "risk_tier": getattr(event, "risk_tier", ""),
                "budget_decision": getattr(event, "budget_decision", ""),
                "approval_id": getattr(event, "approval_id", ""),
                "tool_name": getattr(event, "tool_name", ""),
                "input_hash": getattr(event, "input_hash", ""),
                "output_hash": getattr(event, "output_hash", ""),
                "trace_id": getattr(event, "trace_id", ""),
                "prev_event_hash": getattr(event, "prev_event_hash", ""),
                "timestamp": getattr(event, "timestamp", ""),
                "detail": detail,
            }
        )
    except (TypeError, ValueError, ImportError):
        return False
    return recomputed == event_hash


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
    effect_mismatch_escalation = _uao_record_is_effect_mismatch_escalation(value)
    closure = value.get("closure")
    if not isinstance(closure, Mapping) or closure.get("status") != closure_state:
        return False
    if not _uao_record_binds_universal_detail(value, universal_detail):
        return False
    stages_by_kind = _uao_stage_records_by_kind(value.get("pipeline_stages"))
    if stages_by_kind is None:
        return False
    if not _uao_record_binds_fracture_report(
        value,
        stages_by_kind=stages_by_kind,
        decision_status=str(decision_status),
        effect_mismatch_escalation=effect_mismatch_escalation,
    ):
        return False
    receipts = value.get("receipts")
    receipts_by_kind = _uao_receipt_records_by_kind(receipts)
    if receipts_by_kind is None:
        return False
    required_receipt_kinds = (
        _UAO_ALLOW_REQUIRED_RECEIPT_KINDS
        if decision_status == "allow" or effect_mismatch_escalation
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
    if not _uao_record_binds_closure_refs(
        value,
        stages_by_kind=stages_by_kind,
        receipts_by_kind=receipts_by_kind,
        decision_status=str(decision_status),
    ):
        return False
    execution_receipt_ref = value.get("execution_receipt_ref")
    if decision_status == "allow" or effect_mismatch_escalation:
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
    if _recomputed_universal_action_proof_hash(universal_detail) != proof_hash:
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
    closure = record.get("closure")
    if not isinstance(closure, Mapping):
        return False
    if closure.get("reconciliation_ref") != (
        universal_detail.get("reconciliation_ref") or None
    ):
        return False
    if closure.get("memory_ref") != (universal_detail.get("memory_ref") or None):
        return False
    if (closure.get("whqr_replay_binding") or {}) != (
        universal_detail.get("whqr_replay_binding") or {}
    ):
        return False
    return True


def _uao_record_binds_fracture_report(
    record: Mapping[str, Any],
    *,
    stages_by_kind: Mapping[str, Mapping[str, Any]],
    decision_status: str,
    effect_mismatch_escalation: bool,
) -> bool:
    fracture_report = record.get("fracture_report")
    if not isinstance(fracture_report, Mapping):
        return False
    report_ref = fracture_report.get("report_ref")
    if not _non_empty_text(report_ref):
        return False
    fracture_stage = stages_by_kind.get("fracture")
    if not isinstance(fracture_stage, Mapping):
        return False
    if fracture_stage.get("receipt_ref") is not None:
        return False
    if _uao_stage_single_output_ref(fracture_stage) != report_ref:
        return False
    status = fracture_report.get("status")
    if status not in {"passed", "failed"}:
        return False
    checks = fracture_report.get("checks")
    blocking_check_ids = fracture_report.get("blocking_check_ids")
    if not isinstance(checks, list) or not checks:
        return False
    if not isinstance(blocking_check_ids, list):
        return False
    observed_blocking_ids: set[str] = set()
    seen_check_ids: set[str] = set()
    for check in checks:
        if not isinstance(check, Mapping):
            return False
        check_id = check.get("check_id")
        if not _non_empty_text(check_id) or str(check_id) in seen_check_ids:
            return False
        seen_check_ids.add(str(check_id))
        check_status = check.get("status")
        if check_status not in {"passed", "failed"}:
            return False
        if not isinstance(check.get("blocking"), bool):
            return False
        if check.get("blocking") is True:
            if check_status != "failed":
                return False
            observed_blocking_ids.add(str(check_id))
    declared_blocking_ids = set(_text_tuple(blocking_check_ids))
    if declared_blocking_ids != observed_blocking_ids:
        return False
    if status == "passed" and declared_blocking_ids:
        return False
    if status == "failed" and not declared_blocking_ids:
        return False
    if decision_status == "allow" or effect_mismatch_escalation:
        if status != "passed" or declared_blocking_ids:
            return False
        return fracture_stage.get("status") == "completed"
    if status == "failed":
        return fracture_stage.get("status") == "blocked"
    return fracture_stage.get("status") in {"completed", "skipped"}


def _recomputed_universal_action_proof_hash(
    universal_detail: Mapping[str, Any],
) -> str | None:
    action_envelope = universal_detail.get("action_envelope")
    if not isinstance(action_envelope, Mapping):
        return None
    if not isinstance(universal_detail.get("blocked"), bool):
        return None
    execution_receipt_ref = universal_detail.get("execution_receipt_ref")
    if execution_receipt_ref is not None and not isinstance(execution_receipt_ref, str):
        return None
    text_fields = (
        "action_id",
        "block_reason",
        "trace_ref",
        "admission_receipt_ref",
        "closure_state",
        "goal_certificate_id",
        "world_certificate_id",
        "plan_certificate_id",
        "simulation_certificate_id",
        "effect_prediction_certificate_id",
        "effect_plan_id",
        "recovery_plan_certificate_id",
        "recovery_plan_id",
        "intent_certificate_id",
        "intent_hash",
        "operating_substrate_certificate_id",
        "operating_substrate_projection_id",
        "operating_substrate_reason",
        "capability_status",
        "capability_id",
        "governed_action_id",
        "dispatch_ledger_hash",
        "terminal_certificate_id",
        "learning_admission_id",
        "reconciliation_ref",
        "memory_ref",
    )
    if any(
        not isinstance(universal_detail.get(field_name), str)
        for field_name in text_fields
    ):
        return None
    if not _string_tuple_like(universal_detail.get("world_support_evidence_refs")):
        return None
    if not _string_tuple_like(
        universal_detail.get("operating_substrate_evidence_refs")
    ):
        return None
    whqr_replay_binding = _normalized_whqr_replay_binding(
        universal_detail.get("whqr_replay_binding")
    )
    if whqr_replay_binding is None:
        return None
    life_meaning_judgment = universal_detail.get("life_meaning_judgment")
    if not isinstance(life_meaning_judgment, Mapping):
        return None
    payload = {
        "action_id": universal_detail["action_id"],
        "blocked": universal_detail["blocked"],
        "block_reason": universal_detail["block_reason"],
        "action_envelope": dict(action_envelope),
        "trace_ref": universal_detail["trace_ref"],
        "admission_receipt_ref": universal_detail["admission_receipt_ref"],
        "execution_receipt_ref": execution_receipt_ref,
        "closure_state": universal_detail["closure_state"],
        "goal_certificate_id": universal_detail["goal_certificate_id"],
        "world_certificate_id": universal_detail["world_certificate_id"],
        "plan_certificate_id": universal_detail["plan_certificate_id"],
        "simulation_certificate_id": universal_detail["simulation_certificate_id"],
        "effect_prediction_certificate_id": universal_detail[
            "effect_prediction_certificate_id"
        ],
        "effect_plan_id": universal_detail["effect_plan_id"],
        "recovery_plan_certificate_id": universal_detail[
            "recovery_plan_certificate_id"
        ],
        "recovery_plan_id": universal_detail["recovery_plan_id"],
        "intent_certificate_id": universal_detail["intent_certificate_id"],
        "intent_hash": universal_detail["intent_hash"],
        "operating_substrate_certificate_id": universal_detail[
            "operating_substrate_certificate_id"
        ],
        "operating_substrate_projection_id": universal_detail[
            "operating_substrate_projection_id"
        ],
        "operating_substrate_reason": universal_detail["operating_substrate_reason"],
        "world_support_evidence_refs": tuple(
            universal_detail["world_support_evidence_refs"]
        ),
        "operating_substrate_evidence_refs": tuple(
            universal_detail["operating_substrate_evidence_refs"]
        ),
        "capability_status": universal_detail["capability_status"],
        "capability_id": universal_detail["capability_id"],
        "governed_action_id": universal_detail["governed_action_id"],
        "dispatch_ledger_hash": universal_detail["dispatch_ledger_hash"],
        "terminal_certificate_id": universal_detail["terminal_certificate_id"],
        "whqr_replay_binding": dict(whqr_replay_binding),
        "learning_admission_id": universal_detail["learning_admission_id"],
        "reconciliation_ref": universal_detail["reconciliation_ref"],
        "memory_ref": universal_detail["memory_ref"],
        "life_meaning_judgment": dict(life_meaning_judgment),
    }
    try:
        encoded = json.dumps(
            payload, sort_keys=True, ensure_ascii=True, separators=(",", ":")
        )
    except (TypeError, ValueError):
        return None
    return stable_identifier("universal-action-proof", {"payload": encoded})


def _uao_record_binds_closure_refs(
    record: Mapping[str, Any],
    *,
    stages_by_kind: Mapping[str, Mapping[str, Any]],
    receipts_by_kind: Mapping[str, Mapping[str, Any]],
    decision_status: str,
) -> bool:
    closure = record.get("closure")
    reconciliation = record.get("reconciliation")
    memory_update = record.get("memory_update")
    if (
        not isinstance(closure, Mapping)
        or not isinstance(reconciliation, Mapping)
        or not isinstance(memory_update, Mapping)
    ):
        return False
    for field_name in ("reconciliation_ref", "memory_ref"):
        if field_name not in closure:
            return False
        value = closure.get(field_name)
        if value is not None and not _non_empty_text(value):
            return False
    memory_ref = memory_update.get("memory_ref")
    if memory_ref is not None and not _non_empty_text(memory_ref):
        return False
    if closure.get("memory_ref") != memory_ref:
        return False
    reconciliation_ref = closure.get("reconciliation_ref")
    stage_reconciliation_ref = _uao_stage_single_output_ref(
        stages_by_kind.get("reconciliation")
    )
    if reconciliation_ref != stage_reconciliation_ref:
        return False
    if memory_ref is not None:
        if memory_ref != _uao_stage_single_output_ref(stages_by_kind.get("memory")):
            return False
        closure_stage = stages_by_kind.get("closure")
        if memory_ref not in _text_tuple(
            closure_stage.get("input_refs")
            if isinstance(closure_stage, Mapping)
            else ()
        ):
            return False
    if decision_status == "allow":
        if reconciliation_ref is None:
            return False
        if reconciliation.get("status") != "matched":
            return False
        if reconciliation.get("required_for_closure") is not True:
            return False
        observed_outcome_ref = reconciliation.get("observed_outcome_ref")
        if not _non_empty_text(observed_outcome_ref):
            return False
        execution_stage = stages_by_kind.get("execution")
        if observed_outcome_ref not in _text_tuple(
            execution_stage.get("output_refs")
            if isinstance(execution_stage, Mapping)
            else ()
        ):
            return False
    elif _uao_record_is_effect_mismatch_escalation(record):
        if reconciliation_ref is None:
            return False
        if reconciliation.get("status") != "mismatched":
            return False
        if reconciliation.get("required_for_closure") is not True:
            return False
        observed_outcome_ref = reconciliation.get("observed_outcome_ref")
        if not _non_empty_text(observed_outcome_ref):
            return False
        execution_stage = stages_by_kind.get("execution")
        if observed_outcome_ref not in _text_tuple(
            execution_stage.get("output_refs")
            if isinstance(execution_stage, Mapping)
            else ()
        ):
            return False
    elif reconciliation.get("required_for_closure") is not False:
        return False
    closure_receipt = receipts_by_kind.get("closure")
    if not isinstance(closure_receipt, Mapping):
        return False
    return closure_receipt.get("confirms") == _uao_closure_confirmation(
        closure_state=str(record.get("closure_state", "")),
        reconciliation_ref=reconciliation_ref,
        memory_ref=memory_ref,
        whqr_replay_binding=closure.get("whqr_replay_binding"),
    )


def _uao_record_is_effect_mismatch_escalation(record: Mapping[str, Any]) -> bool:
    decision = record.get("decision")
    reconciliation = record.get("reconciliation")
    if not isinstance(decision, Mapping) or not isinstance(reconciliation, Mapping):
        return False
    return (
        decision.get("status") == "escalate"
        and decision.get("reason_code") == "effect_reconciliation_mismatch"
        and decision.get("execution_allowed") is False
        and record.get("closure_state") == "closed_escalated"
        and reconciliation.get("status") == "mismatched"
        and reconciliation.get("required_for_closure") is True
        and _non_empty_text(reconciliation.get("observed_outcome_ref"))
    )


def _uao_stage_single_output_ref(stage: Mapping[str, Any] | None) -> str | None:
    if not isinstance(stage, Mapping):
        return None
    output_refs = _text_tuple(stage.get("output_refs"))
    if not output_refs:
        return None
    if len(output_refs) != 1:
        return None
    return output_refs[0]


def _uao_closure_confirmation(
    *,
    closure_state: str,
    reconciliation_ref: str | None,
    memory_ref: str | None,
    whqr_replay_binding: Any = None,
) -> str:
    payload = {
        "closure_state": closure_state,
        "reconciliation_ref": reconciliation_ref or "",
        "memory_ref": memory_ref or "",
    }
    payload.update(_whqr_replay_confirmation_payload(whqr_replay_binding))
    return stable_identifier("universal-action-closure-confirmation", payload)


def _whqr_replay_confirmation_payload(binding: Any) -> dict[str, str]:
    if not isinstance(binding, Mapping):
        return {}
    return {
        "whqr_replay_ref": str(binding.get("replay_ref") or ""),
        "whqr_canonical_hash": str(binding.get("canonical_hash") or ""),
        "whqr_semantics_hash": str(binding.get("semantics_hash") or ""),
        "whqr_version": str(binding.get("version") or ""),
    }


def _uao_stage_records_by_kind(value: Any) -> dict[str, Mapping[str, Any]] | None:
    if not isinstance(value, list):
        return None
    if len(value) != len(_UAO_CANONICAL_PIPELINE_STAGE_KINDS):
        return None
    stages_by_kind: dict[str, Mapping[str, Any]] = {}
    stage_ids: set[str] = set()
    for expected_order, (expected_kind, stage) in enumerate(
        zip(_UAO_CANONICAL_PIPELINE_STAGE_KINDS, value, strict=True),
        start=1,
    ):
        if not isinstance(stage, Mapping):
            return None
        stage_kind = stage.get("stage_kind")
        stage_id = stage.get("stage_id")
        if not _non_empty_text(stage_kind) or stage_kind != expected_kind:
            return None
        if not _non_empty_text(stage_id):
            return None
        if stage.get("stage_order") != expected_order:
            return None
        if str(stage_id) in stage_ids:
            return None
        stage_ids.add(str(stage_id))
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


def _string_tuple_like(value: Any) -> bool:
    if not isinstance(value, (list, tuple)):
        return False
    return all(isinstance(item, str) for item in value)


def _state_text(value: Any) -> str:
    state_value = getattr(value, "value", value)
    return state_value if isinstance(state_value, str) else str(state_value)


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
    approval_actor_ids: tuple[str, ...] = (),
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
            "approval_actor_ids": approval_actor_ids,
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
        "effect_prediction_certificate_id": (
            result.effect_prediction_certificate.certificate_id
            if result.effect_prediction_certificate
            else ""
        ),
        "effect_plan_id": (
            result.effect_prediction_certificate.plan.effect_plan_id
            if result.effect_prediction_certificate
            else ""
        ),
        "recovery_plan_certificate_id": (
            result.recovery_plan_certificate.certificate_id
            if result.recovery_plan_certificate
            else ""
        ),
        "recovery_plan_id": (
            result.recovery_plan_certificate.recovery_plan_id
            if result.recovery_plan_certificate
            else ""
        ),
        "intent_certificate_id": result.intent_certificate.certificate_id
        if result.intent_certificate
        else "",
        "intent_hash": result.intent_certificate.intent_hash
        if result.intent_certificate
        else "",
        "operating_substrate_certificate_id": (
            result.operating_substrate_certificate.certificate_id
            if result.operating_substrate_certificate
            else ""
        ),
        "operating_substrate_projection_id": (
            result.operating_substrate_certificate.projection.projection_id
            if result.operating_substrate_certificate is not None
            and result.operating_substrate_certificate.projection is not None
            else ""
        ),
        "operating_substrate_reason": (
            result.operating_substrate_certificate.reason
            if result.operating_substrate_certificate
            else ""
        ),
        "world_support_evidence_refs": result.world_certificate.evidence_refs,
        "operating_substrate_evidence_refs": (
            result.operating_substrate_certificate.evidence_refs
            if result.operating_substrate_certificate
            else ()
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
        "whqr_replay_binding": _universal_action_whqr_replay_binding(result) or {},
        "learning_admission_id": result.learning_decision.admission_id
        if result.learning_decision
        else "",
        "reconciliation_ref": _universal_action_reconciliation_ref(result),
        "memory_ref": _universal_action_memory_ref(result),
        "life_meaning_judgment": (
            result.life_meaning_judgment.as_dict()
            if result.life_meaning_judgment is not None
            else {}
        ),
    }


def _universal_action_whqr_replay_binding(
    result: UniversalActionResult,
) -> dict[str, str] | None:
    certificate = result.terminal_certificate
    if certificate is None:
        return None
    metadata = certificate.metadata
    canonical_json = metadata.get("whqr_canonical_json")
    canonical_hash = metadata.get("whqr_canonical_hash")
    semantics_hash = metadata.get("whqr_semantics_hash")
    whqr_version = metadata.get("whqr_version")
    if (
        canonical_json is None
        and canonical_hash is None
        and semantics_hash is None
        and whqr_version is None
    ):
        return None
    if not isinstance(canonical_json, str) or not canonical_json:
        raise RuntimeCoreInvariantError(
            "universal action detail requires WHQR canonical replay document"
        )
    if not isinstance(canonical_hash, str) or not canonical_hash:
        raise RuntimeCoreInvariantError(
            "universal action detail requires WHQR canonical hash"
        )
    try:
        document = WHQRDocument.from_canonical_json(
            canonical_json,
            expected_canonical_hash=canonical_hash,
        )
    except ValueError as exc:
        raise RuntimeCoreInvariantError(
            "universal action detail WHQR replay document is invalid"
        ) from exc
    if semantics_hash is not None and semantics_hash != document.semantics_hash:
        raise RuntimeCoreInvariantError(
            "universal action detail WHQR semantics hash mismatch"
        )
    if whqr_version is not None and whqr_version != document.whqr_version:
        raise RuntimeCoreInvariantError(
            "universal action detail WHQR version mismatch"
        )
    return {
        "replay_ref": f"whqr://replay/{canonical_hash}",
        "canonical_hash": canonical_hash,
        "semantics_hash": document.semantics_hash,
        "version": document.whqr_version,
    }


def _universal_action_reconciliation_ref(result: UniversalActionResult) -> str:
    if not result.dispatched:
        return ""
    return f"reconciliation://{result.action_id}"


def _universal_action_memory_ref(result: UniversalActionResult) -> str:
    if (
        result.terminal_certificate is not None
        and result.terminal_certificate.memory_entry_id is not None
    ):
        return f"memory://{result.terminal_certificate.memory_entry_id}"
    if result.learning_decision is not None:
        return f"memory://{result.learning_decision.knowledge_id}"
    return ""


def _mapping_detail(value: Any) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return dict(value)


def _valid_whqr_semver(version: str) -> bool:
    parts = version.split(".")
    return len(parts) == 3 and all(_valid_semver_core_identifier(part) for part in parts)


def _valid_semver_core_identifier(value: str) -> bool:
    if not value.isascii() or not value.isdecimal():
        return False
    return value == "0" or not value.startswith("0")


def _valid_sha256_digest_ref(value: str) -> bool:
    prefix = "sha256:"
    return value.startswith(prefix) and _valid_sha256_hex_suffix(value, prefix)


def _valid_whqr_replay_ref(value: str) -> bool:
    prefix = "whqr://replay/sha256:"
    return value.startswith(prefix) and _valid_sha256_hex_suffix(value, prefix)


def _valid_sha256_hex_suffix(value: str, prefix: str) -> bool:
    suffix = value[len(prefix):]
    return len(suffix) == 64 and all(char in "0123456789abcdef" for char in suffix)


def _normalized_whqr_replay_binding(value: Any) -> dict[str, str] | None:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        return None
    if not value:
        return {}
    if set(value) != _WHQR_REPLAY_BINDING_FIELDS:
        return None
    replay_ref = value.get("replay_ref")
    canonical_hash = value.get("canonical_hash")
    semantics_hash = value.get("semantics_hash")
    version = value.get("version")
    if not (
        isinstance(replay_ref, str)
        and isinstance(canonical_hash, str)
        and isinstance(semantics_hash, str)
        and isinstance(version, str)
        and replay_ref
        and canonical_hash
        and semantics_hash
        and version
    ):
        return None
    if not (
        _valid_whqr_replay_ref(replay_ref)
        and _valid_sha256_digest_ref(canonical_hash)
        and _valid_sha256_digest_ref(semantics_hash)
        and replay_ref == f"whqr://replay/{canonical_hash}"
        and _valid_whqr_semver(version)
    ):
        return None
    return {
        "replay_ref": replay_ref,
        "canonical_hash": canonical_hash,
        "semantics_hash": semantics_hash,
        "version": version,
    }


def _text_detail(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


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
