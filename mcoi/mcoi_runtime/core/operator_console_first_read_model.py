"""Purpose: project Operator Console First episodes into console panels.
Governance scope: OCF panel read models, approval visibility, side-effect
    visibility, verification summaries, receipt visibility, and control states.
Dependencies: operator-console contracts and pure OCF runtime helpers.
Invariants:
  - Projection is read-only and never dispatches actions.
  - Receipt data must belong to the projected episode.
  - Tool success and independent verification remain separate surfaces.
  - Controls are advisory UI affordances, not execution authority.
"""

from __future__ import annotations

from typing import Any

from mcoi_runtime.contracts.operator_console_first import (
    ApprovalMode,
    ConsoleEpisodeStatus,
    ConsoleFinalStatus,
    ConsolePlannedAction,
    OperatorConsoleEpisode,
    OperatorConsoleReceipt,
    RecoveryClass,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, stable_identifier
from mcoi_runtime.core.operator_console_first import (
    approval_mode_for_action,
    compute_plan_hash,
)


PANEL_KEYS: tuple[str, ...] = (
    "current_task",
    "state_snapshot",
    "proposed_plan",
    "risk_and_side_effects",
    "approval_lease",
    "controlled_execution_log",
    "verification_result",
    "receipt_bundle",
    "controls",
)

_RETRYABLE_FINAL_STATUSES = frozenset(
    {
        ConsoleFinalStatus.UNVERIFIED_SUCCESS,
        ConsoleFinalStatus.PARTIAL_SUCCESS,
        ConsoleFinalStatus.BLOCKED,
        ConsoleFinalStatus.FAILED_RECOVERABLE,
        ConsoleFinalStatus.ABORTED,
        ConsoleFinalStatus.QUARANTINED,
    }
)
_RETRYABLE_EPISODE_STATUSES = frozenset(
    {
        ConsoleEpisodeStatus.BLOCKED,
        ConsoleEpisodeStatus.PAUSED,
        ConsoleEpisodeStatus.APPROVAL_EXPIRED,
        ConsoleEpisodeStatus.STALE_STATE,
        ConsoleEpisodeStatus.POLICY_DENIED,
        ConsoleEpisodeStatus.ABORTED,
        ConsoleEpisodeStatus.QUARANTINED,
    }
)
_ABORTABLE_STATUSES = frozenset(
    {
        ConsoleEpisodeStatus.PLANNED,
        ConsoleEpisodeStatus.WAITING_APPROVAL,
        ConsoleEpisodeStatus.APPROVED,
        ConsoleEpisodeStatus.DISPATCHING,
        ConsoleEpisodeStatus.VERIFYING,
        ConsoleEpisodeStatus.PAUSED,
    }
)
_PAUSABLE_STATUSES = frozenset(
    {
        ConsoleEpisodeStatus.PLANNED,
        ConsoleEpisodeStatus.APPROVED,
        ConsoleEpisodeStatus.DISPATCHING,
        ConsoleEpisodeStatus.VERIFYING,
    }
)


def build_operator_console_read_model(
    episode: OperatorConsoleEpisode,
    *,
    receipt: OperatorConsoleReceipt | None = None,
    generated_at: str,
) -> dict[str, Any]:
    """Return the deterministic minimum-product OCF console projection.

    Input contract: an immutable OCF episode and optional terminal receipt for
    the same episode. Output contract: JSON-compatible panel dictionary for the
    operator console. Error contract: raises RuntimeCoreInvariantError if the
    receipt belongs to a different episode.
    """

    if receipt is not None and receipt.episode_id != episode.episode_id:
        raise RuntimeCoreInvariantError("operator console receipt episode_id mismatch")

    plan_hash = compute_plan_hash(episode.plan) if episode.plan else ""
    attention = _attention_items(episode, receipt)
    read_model_id = stable_identifier(
        "ocf-console-read-model",
        {
            "episode_id": episode.episode_id,
            "status": episode.status.value,
            "receipt_id": receipt.receipt_id if receipt is not None else "",
            "generated_at": generated_at,
        },
    )
    panels = {
        "current_task": _current_task_panel(episode),
        "state_snapshot": _state_snapshot_panel(episode),
        "proposed_plan": _proposed_plan_panel(episode, plan_hash),
        "risk_and_side_effects": _risk_panel(episode),
        "approval_lease": _approval_panel(episode, plan_hash),
        "controlled_execution_log": _execution_log_panel(episode),
        "verification_result": _verification_panel(receipt),
        "receipt_bundle": _receipt_panel(receipt),
        "controls": _controls_panel(episode, receipt),
    }
    return {
        "read_model_id": read_model_id,
        "generated_at": generated_at,
        "episode_id": episode.episode_id,
        "operator_id": episode.operator_id,
        "status": episode.status.value,
        "final_status": receipt.final_status.value if receipt is not None else None,
        "panel_keys": list(PANEL_KEYS),
        "panels": panels,
        "attention": attention,
        "projection_only": True,
        "execution_authority": False,
        "receipt_attached": receipt is not None,
    }


def _current_task_panel(episode: OperatorConsoleEpisode) -> dict[str, Any]:
    return {
        "episode_id": episode.episode_id,
        "operator_id": episode.operator_id,
        "raw_request": episode.raw_request,
        "intent_class": episode.intent_class.value,
        "governed_goal": dict(episode.governed_goal),
        "scope": dict(episode.scope),
        "status": episode.status.value,
        "limits": episode.limits.to_json_dict(),
    }


def _state_snapshot_panel(episode: OperatorConsoleEpisode) -> dict[str, Any]:
    if episode.snapshot is None:
        return {
            "present": False,
            "source": "",
            "captured_at": "",
            "expires_at": "",
            "state_hash": "",
            "trust_level": 0.0,
            "missing_fields": [],
        }
    return {
        "present": True,
        "source": episode.snapshot.source,
        "captured_at": episode.snapshot.captured_at,
        "expires_at": episode.snapshot.expires_at,
        "state_hash": episode.snapshot.state_hash,
        "trust_level": episode.snapshot.trust_level,
        "missing_fields": list(episode.snapshot.missing_fields),
    }


def _proposed_plan_panel(episode: OperatorConsoleEpisode, plan_hash: str) -> dict[str, Any]:
    actions = [_action_card(action) for action in episode.plan]
    approval_modes = _approval_modes(episode.plan)
    approval_needed = any(
        mode in {ApprovalMode.EXPLICIT.value, ApprovalMode.STRONG.value}
        for mode in approval_modes
    )
    return {
        "present": bool(episode.plan),
        "plan_hash": plan_hash,
        "action_count": len(actions),
        "approval_needed": approval_needed,
        "approval_modes": approval_modes,
        "actions": actions,
    }


def _risk_panel(episode: OperatorConsoleEpisode) -> dict[str, Any]:
    action_risks = []
    for action in episode.plan:
        action_risks.append(
            {
                "action_id": action.action_id,
                "capability_id": action.capability_id,
                "risk_score": action.risk_score,
                "approval_mode": approval_mode_for_action(action).value,
                "intent_class": action.intent_class.value,
                "side_effects_declared": action.side_effects_declared,
                "side_effects": action.side_effects.to_json_dict(),
                "effect_bearing": action.side_effects.effect_bearing,
                "recovery_class": action.recovery_class.value,
                "recovery_plan_ref": action.recovery_plan_ref,
                "recovery_declared": action.recovery_declared,
                "hostile_input_boundary": action.hostile_input_boundary.to_json_dict(),
                "hostile_input_blocks_dispatch": action.hostile_input_boundary.blocks_dispatch,
            }
        )
    return {
        "max_risk_score": max((action.risk_score for action in episode.plan), default=0),
        "approval_modes": _approval_modes(episode.plan),
        "effect_bearing_action_count": sum(
            1 for action in episode.plan if action.side_effects.effect_bearing
        ),
        "undeclared_side_effect_action_ids": [
            action.action_id for action in episode.plan if not action.side_effects_declared
        ],
        "missing_recovery_action_ids": [
            action.action_id
            for action in episode.plan
            if action.side_effects.effect_bearing and not action.recovery_declared
        ],
        "hostile_input_action_ids": [
            action.action_id for action in episode.plan if action.hostile_input_boundary.blocks_dispatch
        ],
        "actions": action_risks,
    }


def _approval_panel(episode: OperatorConsoleEpisode, plan_hash: str) -> dict[str, Any]:
    if episode.approval_lease is None:
        return {
            "present": False,
            "operator_id": "",
            "plan_hash": "",
            "plan_hash_matches_current_plan": False,
            "target_state_hash": "",
            "target_state_matches_snapshot": False,
            "risk_ceiling": None,
            "scope": {},
            "issued_at": "",
            "expires_at": "",
            "allowed_actions": [],
        }
    target_state_hash = episode.snapshot.state_hash if episode.snapshot is not None else ""
    return {
        "present": True,
        "operator_id": episode.approval_lease.operator_id,
        "plan_hash": episode.approval_lease.plan_hash,
        "plan_hash_matches_current_plan": episode.approval_lease.plan_hash == plan_hash,
        "target_state_hash": episode.approval_lease.target_state_hash,
        "target_state_matches_snapshot": episode.approval_lease.target_state_hash == target_state_hash,
        "risk_ceiling": episode.approval_lease.risk_ceiling,
        "scope": dict(episode.approval_lease.scope),
        "issued_at": episode.approval_lease.issued_at,
        "expires_at": episode.approval_lease.expires_at,
        "allowed_actions": list(episode.approval_lease.allowed_actions),
    }


def _execution_log_panel(episode: OperatorConsoleEpisode) -> dict[str, Any]:
    return {
        "event_count": len(episode.events),
        "events": [
            {
                "event_type": event.event_type,
                "occurred_at": event.occurred_at,
                "details": dict(event.details),
            }
            for event in episode.events
        ],
    }


def _verification_panel(receipt: OperatorConsoleReceipt | None) -> dict[str, Any]:
    if receipt is None:
        return {
            "present": False,
            "verified_count": 0,
            "unverified_count": 0,
            "missing_effect_count": 0,
            "mismatch_count": 0,
            "records": [],
        }
    records = [
        {
            "action_id": record.action_id,
            "tool_reported_success": record.tool_reported_success,
            "independently_verified": record.independently_verified,
            "observed_effects": list(record.observed_effects),
            "missing_effects": list(record.missing_effects),
            "mismatch_reasons": list(record.mismatch_reasons),
            "verified_at": record.verified_at,
        }
        for record in receipt.verification_records
    ]
    return {
        "present": True,
        "verified_count": sum(
            1 for record in receipt.verification_records if record.independently_verified
        ),
        "unverified_count": sum(
            1 for record in receipt.verification_records if not record.independently_verified
        ),
        "missing_effect_count": sum(
            len(record.missing_effects) for record in receipt.verification_records
        ),
        "mismatch_count": sum(
            len(record.mismatch_reasons) for record in receipt.verification_records
        ),
        "records": records,
    }


def _receipt_panel(receipt: OperatorConsoleReceipt | None) -> dict[str, Any]:
    if receipt is None:
        return {
            "present": False,
            "receipt_id": "",
            "final_status": None,
            "actions_attempted": [],
            "actions_blocked": [],
            "evidence_refs": [],
            "unverified_claims": [],
            "issued_at": "",
            "receipt_hash": "",
        }
    return {
        "present": True,
        "receipt_id": receipt.receipt_id,
        "final_status": receipt.final_status.value,
        "actions_attempted": list(receipt.actions_attempted),
        "actions_blocked": list(receipt.actions_blocked),
        "evidence_refs": list(receipt.evidence_refs),
        "unverified_claims": list(receipt.unverified_claims),
        "issued_at": receipt.issued_at,
        "receipt_hash": receipt.receipt_hash,
    }


def _controls_panel(
    episode: OperatorConsoleEpisode,
    receipt: OperatorConsoleReceipt | None,
) -> dict[str, Any]:
    final_status = receipt.final_status if receipt is not None else None
    attempted_actions = set(receipt.actions_attempted if receipt is not None else ())
    recovery_action_ids = [
        action.action_id
        for action in episode.plan
        if action.action_id in attempted_actions and action.recovery_class is not RecoveryClass.R0_NONE
    ]
    return {
        "can_approve": (
            receipt is None
            and episode.status is ConsoleEpisodeStatus.WAITING_APPROVAL
            and episode.approval_lease is None
        ),
        "can_abort": receipt is None and episode.status in _ABORTABLE_STATUSES,
        "can_pause": receipt is None and episode.status in _PAUSABLE_STATUSES,
        "can_resume": receipt is None and episode.status is ConsoleEpisodeStatus.PAUSED,
        "can_retry": (
            (final_status in _RETRYABLE_FINAL_STATUSES if final_status is not None else False)
            or episode.status in _RETRYABLE_EPISODE_STATUSES
        ),
        "can_rollback": bool(recovery_action_ids),
        "rollback_action_ids": recovery_action_ids,
        "control_execution_authority": False,
    }


def _action_card(action: ConsolePlannedAction) -> dict[str, Any]:
    return {
        "action_id": action.action_id,
        "capability_id": action.capability_id,
        "intent_class": action.intent_class.value,
        "risk_score": action.risk_score,
        "approval_mode": approval_mode_for_action(action).value,
        "expected_effects": list(action.expected_effects),
        "evidence_required": list(action.evidence_required),
        "estimated_cost": action.estimated_cost,
    }


def _approval_modes(actions: tuple[ConsolePlannedAction, ...]) -> list[str]:
    modes = {approval_mode_for_action(action).value for action in actions}
    return sorted(modes)


def _attention_items(
    episode: OperatorConsoleEpisode,
    receipt: OperatorConsoleReceipt | None,
) -> list[str]:
    items: list[str] = []
    if episode.snapshot is None:
        items.append("missing_state_snapshot")
    elif episode.snapshot.missing_fields:
        items.append("state_snapshot_has_missing_fields")
    if not episode.plan:
        items.append("missing_plan")
    if episode.status is ConsoleEpisodeStatus.WAITING_APPROVAL:
        items.append("approval_required")
    if any(
        approval_mode_for_action(action) in {ApprovalMode.EXPLICIT, ApprovalMode.STRONG}
        for action in episode.plan
    ) and episode.approval_lease is None:
        items.append("approval_lease_missing")
    for action in episode.plan:
        if not action.side_effects_declared:
            items.append("undeclared_side_effects")
        if action.side_effects.effect_bearing and not action.recovery_declared:
            items.append("missing_recovery_plan")
        if action.hostile_input_boundary.blocks_dispatch:
            items.append("hostile_input_authority_violation")
    if episode.status is ConsoleEpisodeStatus.PAUSED:
        items.append("episode_paused")
    if episode.status is ConsoleEpisodeStatus.QUARANTINED:
        items.append("episode_quarantined")
    if receipt is not None:
        items.extend(receipt.unverified_claims)
        if receipt.final_status is ConsoleFinalStatus.UNVERIFIED_SUCCESS:
            items.append("independent_evidence_missing")
        if receipt.final_status is ConsoleFinalStatus.PARTIAL_SUCCESS:
            items.append("partial_success")
        if receipt.final_status is ConsoleFinalStatus.QUARANTINED:
            items.append("quarantined")
        if receipt.final_status is ConsoleFinalStatus.BLOCKED:
            items.append("blocked")
    return _unique_sorted(items)


def _unique_sorted(values: list[str]) -> list[str]:
    return sorted({value for value in values if value})
