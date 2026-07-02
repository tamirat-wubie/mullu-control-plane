"""Operator workflow dashboard projection.

Purpose: unify local workflow receipt, workflow status, and safe-local action
    projections into one operator-facing read model, including the local
    workflow closure packet, rehearsal receipt, and causal repair receipt when
    present.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: gateway command-spine hashing, local Developer Workflow receipt
    read-model builder, capability promotion ladder, and JSON schema
    validation helpers.
Invariants:
  - This module is projection-only and never executes workflow stages.
  - File writes are limited to the explicit generated dashboard artifact.
  - External effects, PR creation, branch push, merge, deployment, connector
    calls, email sends, money movement, and production writes remain disabled.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
MCOI_ROOT = REPO_ROOT / "mcoi"
if str(MCOI_ROOT) not in sys.path:
    sys.path.insert(0, str(MCOI_ROOT))

from gateway.command_spine import canonical_hash  # noqa: E402
from scripts.build_operator_local_developer_workflow_receipt_read_model import (  # noqa: E402
    FORBIDDEN_EFFECTS,
    _load_control_tower_status_receipt,
    _load_operator_receipt,
    build_operator_local_developer_workflow_receipt_read_model,
    validate_operator_local_developer_workflow_receipt_read_model,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402
from capability_levels.ladder import (  # noqa: E402
    CAPABILITY_PROMOTION_LADDER_ID,
    default_capability_promotion_ladder,
)
from software_dev.local_developer_workflow_v1.closure_packet import CLOSURE_PACKET_FILENAME  # noqa: E402
from mcoi_runtime.app.capability_passports import build_capability_passports  # noqa: E402


SCHEMA_REF = "urn:mullusi:schema:operator-workflow-dashboard-read-model:1"
READ_MODEL_ID = "operator_workflow_dashboard.read_model"
DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "operator_workflow_dashboard_read_model.schema.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "operator_workflow_dashboard.read_model.generated.json"
DEFAULT_CLOSURE_PACKET = REPO_ROOT / ".change_assurance" / CLOSURE_PACKET_FILENAME
DEFAULT_REHEARSAL_RECEIPT = REPO_ROOT / ".change_assurance" / "safe_local_action_rehearsal_receipt.json"
DEFAULT_CAUSAL_REPAIR_RECEIPT = REPO_ROOT / ".change_assurance" / "causal_repair_service_receipt.json"


@dataclass(frozen=True, slots=True)
class OperatorWorkflowDashboardValidation:
    """Validation report for the unified operator workflow dashboard."""

    ok: bool
    errors: tuple[str, ...]
    dashboard_path: str
    status: str
    current_gate: str

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def build_operator_workflow_dashboard_read_model(
    *,
    local_workflow_receipt: Mapping[str, Any],
    local_workflow_source_ref: str,
    closure_packet: Mapping[str, Any] | None = None,
    closure_packet_source_ref: str = "absent",
    rehearsal_receipt: Mapping[str, Any] | None = None,
    rehearsal_receipt_source_ref: str = "absent",
    causal_repair_receipt: Mapping[str, Any] | None = None,
    causal_repair_receipt_source_ref: str = "absent",
    capability_passports: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a projection-only operator workflow dashboard read model."""

    local_validation = validate_operator_local_developer_workflow_receipt_read_model(
        read_model=local_workflow_receipt
    )
    if not local_validation.ok:
        raise ValueError(f"local_workflow_receipt_invalid:{list(local_validation.errors)}")

    workflow_status = _mapping(local_workflow_receipt.get("workflow_status"))
    capability_summary = _mapping(workflow_status.get("capability_summary"))
    receipt_card = _mapping(local_workflow_receipt.get("receipt_card"))
    safe_local_action = _mapping(local_workflow_receipt.get("safe_local_action"))
    operator_controls = _mapping(local_workflow_receipt.get("operator_controls"))
    stage_plan = _stage_plan(local_workflow_receipt.get("stage_plan"))
    current_gate = _current_gate(stage_plan)
    missing_evidence = _missing_evidence(
        next_unlock=str(local_workflow_receipt.get("next_unlock") or "none"),
        capability_summary=capability_summary,
        current_gate=current_gate,
    )
    approval = _approval_summary(local_workflow_receipt, workflow_status, current_gate, operator_controls)
    rollback = _rollback_summary(receipt_card)
    receipts = _receipt_summary(receipt_card, local_workflow_source_ref)
    closure_packet_summary = _closure_packet_summary(
        closure_packet=closure_packet,
        source_ref=closure_packet_source_ref,
    )
    rehearsal_summary = _rehearsal_summary(
        rehearsal_receipt=rehearsal_receipt,
        source_ref=rehearsal_receipt_source_ref,
    )
    causal_repair_summary = _causal_repair_summary(
        causal_repair_receipt=causal_repair_receipt,
        source_ref=causal_repair_receipt_source_ref,
    )
    readiness_lane = _readiness_lane(
        current_gate=current_gate,
        missing_evidence=missing_evidence,
        approval=approval,
        closure_packet=closure_packet_summary,
        rehearsal=rehearsal_summary,
        causal_repair=causal_repair_summary,
    )
    row = {
        "task": str(local_workflow_receipt.get("task") or "Mullu Developer Workflow v1"),
        "status": str(local_workflow_receipt.get("status") or "AwaitingEvidence"),
        "current_gate": current_gate,
        "missing_evidence": missing_evidence,
        "next_action": str(local_workflow_receipt.get("action_needed") or safe_local_action.get("primary_action") or ""),
        "risk": str(local_workflow_receipt.get("risk") or "low, local lab only"),
        "receipts": receipts,
        "rollback": rollback,
        "approval_needed": approval["needed"],
        "approval": approval,
        "closure_packet": closure_packet_summary,
        "safe_local_action_rehearsal": rehearsal_summary,
        "causal_repair": causal_repair_summary,
        "readiness_lane": readiness_lane,
        "source_ref": local_workflow_source_ref,
    }
    dashboard = {
        "schema_ref": SCHEMA_REF,
        "read_model_id": READ_MODEL_ID,
        "projection_only": True,
        "execution_performed": False,
        "external_effects_allowed": False,
        "dashboard_id": "operator_workflow_dashboard.foundation.v1",
        "mode": "local_lab",
        "task_count": 1,
        "blocked_effects": list(FORBIDDEN_EFFECTS),
        "rows": [row],
        "promotion_filters": _promotion_filters(capability_passports),
        "source_projections": {
            "local_workflow_receipt": local_workflow_source_ref,
            "workflow_status": "operator_developer_workflow_status.read_model",
            "safe_local_action": "operator_safe_local_action.read_model",
            "capability_passports": "capability_passports.foundation.v1",
            "closure_packet": "local_developer_workflow_v1.closure_packet",
            "safe_local_action_rehearsal": "safe_local_action_rehearsal.foundation.v1",
            "causal_repair": "causal_repair_service.foundation.v1",
        },
        "source_refs": {
            "builder": "gateway/operator_workflow_dashboard.py",
            "local_workflow_receipt": local_workflow_source_ref,
            "closure_packet": closure_packet_source_ref,
            "safe_local_action_rehearsal": rehearsal_receipt_source_ref,
            "causal_repair": causal_repair_receipt_source_ref,
        },
        "dashboard_hash": "",
    }
    dashboard["dashboard_hash"] = canonical_hash(dashboard)
    return dashboard


def validate_operator_workflow_dashboard_read_model(
    *,
    dashboard: Mapping[str, Any],
    schema_path: Path = DEFAULT_SCHEMA,
    dashboard_path: Path = Path("<generated>"),
) -> OperatorWorkflowDashboardValidation:
    """Validate dashboard schema, topology projection, and no-effect claims."""

    errors = [str(error) for error in _validate_schema_instance(_load_json_object(schema_path), dict(dashboard))]
    if dashboard.get("projection_only") is not True:
        errors.append("projection_only_must_be_true")
    if dashboard.get("execution_performed") is not False:
        errors.append("execution_performed_must_be_false")
    if dashboard.get("external_effects_allowed") is not False:
        errors.append("external_effects_must_be_false")
    blocked_effects = dashboard.get("blocked_effects", ())
    if not isinstance(blocked_effects, list):
        errors.append("blocked_effects_must_be_list")
        blocked_effects = []
    for forbidden_effect in FORBIDDEN_EFFECTS:
        if forbidden_effect not in blocked_effects:
            errors.append(f"blocked_effect_missing:{forbidden_effect}")
    rows = dashboard.get("rows", ())
    if not isinstance(rows, list) or not rows:
        errors.append("rows_must_be_non_empty_list")
        rows = []
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            errors.append(f"rows[{index}]_must_be_object")
            continue
        receipts = _mapping(row.get("receipts"))
        rollback = _mapping(row.get("rollback"))
        approval = _mapping(row.get("approval"))
        current_gate = _mapping(row.get("current_gate"))
        closure_packet = _mapping(row.get("closure_packet"))
        rehearsal = _mapping(row.get("safe_local_action_rehearsal"))
        causal_repair = _mapping(row.get("causal_repair"))
        readiness_lane = _mapping(row.get("readiness_lane"))
        if receipts.get("execution_performed") is not False:
            errors.append(f"rows[{index}].receipts_execution_performed_must_be_false")
        if rollback.get("executed") is not False:
            errors.append(f"rows[{index}].rollback_executed_must_be_false")
        if approval.get("performed") is not False:
            errors.append(f"rows[{index}].approval_performed_must_be_false")
        if current_gate.get("execution_performed") is not False:
            errors.append(f"rows[{index}].current_gate_execution_performed_must_be_false")
        if closure_packet.get("execution_performed") is not False:
            errors.append(f"rows[{index}].closure_packet_execution_performed_must_be_false")
        if closure_packet.get("external_effects_allowed") is not False:
            errors.append(f"rows[{index}].closure_packet_external_effects_must_be_false")
        closure_gate = _mapping(closure_packet.get("current_gate"))
        closure_approval = _mapping(closure_packet.get("approval_boundary"))
        closure_rollback = _mapping(closure_packet.get("rollback"))
        if closure_gate.get("execution_performed") is not False:
            errors.append(f"rows[{index}].closure_packet_current_gate_execution_must_be_false")
        if closure_approval.get("approval_performed") is not False:
            errors.append(f"rows[{index}].closure_packet_approval_performed_must_be_false")
        if closure_rollback.get("rollback_executed") is not False:
            errors.append(f"rows[{index}].closure_packet_rollback_executed_must_be_false")
        raw_command_preview_refs = closure_packet.get("command_preview_refs", ())
        if isinstance(raw_command_preview_refs, list):
            for command_index, command_ref in enumerate(raw_command_preview_refs):
                if isinstance(command_ref, Mapping) and command_ref.get("execution_allowed") is not False:
                    errors.append(
                        f"rows[{index}].closure_packet_command_preview[{command_index}]_execution_must_be_false"
                    )
        if rehearsal.get("execution_performed") is not False:
            errors.append(f"rows[{index}].rehearsal_execution_performed_must_be_false")
        if rehearsal.get("external_effects_allowed") is not False:
            errors.append(f"rows[{index}].rehearsal_external_effects_must_be_false")
        if rehearsal.get("live_execution_enabled") is not False:
            errors.append(f"rows[{index}].rehearsal_live_execution_must_be_false")
        if _mapping(rehearsal.get("approval")).get("approval_performed") is not False:
            errors.append(f"rows[{index}].rehearsal_approval_performed_must_be_false")
        raw_rehearsal_scenarios = rehearsal.get("scenario_refs", ())
        if isinstance(raw_rehearsal_scenarios, list):
            for scenario_index, scenario_ref in enumerate(raw_rehearsal_scenarios):
                if isinstance(scenario_ref, Mapping) and scenario_ref.get("mutation_performed") is not False:
                    errors.append(f"rows[{index}].rehearsal_scenario[{scenario_index}]_mutation_must_be_false")
        if causal_repair.get("repair_execution_performed") is not False:
            errors.append(f"rows[{index}].causal_repair_execution_performed_must_be_false")
        if causal_repair.get("live_execution_enabled") is not False:
            errors.append(f"rows[{index}].causal_repair_live_execution_must_be_false")
        raw_repair_actions = causal_repair.get("next_actions", ())
        if isinstance(raw_repair_actions, list):
            for action_index, action_ref in enumerate(raw_repair_actions):
                if isinstance(action_ref, Mapping) and action_ref.get("execution_performed") is not False:
                    errors.append(f"rows[{index}].causal_repair_next_action[{action_index}]_execution_must_be_false")
        if readiness_lane.get("projection_only") is not True:
            errors.append(f"rows[{index}].readiness_lane_projection_only_must_be_true")
        if readiness_lane.get("execution_authority_granted") is not False:
            errors.append(f"rows[{index}].readiness_lane_must_not_grant_execution_authority")
        if readiness_lane.get("live_execution_enabled") is not False:
            errors.append(f"rows[{index}].readiness_lane_live_execution_must_be_false")
        if readiness_lane.get("external_effects_allowed") is not False:
            errors.append(f"rows[{index}].readiness_lane_external_effects_must_be_false")
        linked_receipts = _mapping(readiness_lane.get("linked_receipts"))
        if linked_receipts.get("closure_packet") != closure_packet.get("linked"):
            errors.append(f"rows[{index}].readiness_lane_closure_link_mismatch")
        if linked_receipts.get("safe_local_action_rehearsal") != rehearsal.get("linked"):
            errors.append(f"rows[{index}].readiness_lane_rehearsal_link_mismatch")
        if linked_receipts.get("causal_repair") != causal_repair.get("linked"):
            errors.append(f"rows[{index}].readiness_lane_causal_repair_link_mismatch")
    promotion_filters = _mapping(dashboard.get("promotion_filters"))
    if promotion_filters.get("filter_is_not_execution_authority") is not True:
        errors.append("promotion_filters_must_not_be_execution_authority")
    if promotion_filters.get("live_execution_enabled") is not False:
        errors.append("promotion_filters_live_execution_must_be_false")
    if promotion_filters.get("external_effects_allowed") is not False:
        errors.append("promotion_filters_external_effects_must_be_false")
    if promotion_filters.get("ladder_id") != CAPABILITY_PROMOTION_LADDER_ID:
        errors.append("promotion_filters_ladder_id_mismatch")
    level_filters = promotion_filters.get("levels", ())
    if not isinstance(level_filters, list) or len(level_filters) != 10:
        errors.append("promotion_filters_must_expose_L0_through_L9")
        level_filters = []
    observed_level_ids: list[str] = []
    for level_filter in level_filters:
        if not isinstance(level_filter, Mapping):
            errors.append("promotion_filter_levels_must_be_objects")
            continue
        observed_level_ids.append(str(level_filter.get("level_id") or ""))
        if level_filter.get("filter_is_not_execution_authority") is not True:
            errors.append(f"promotion_filter[{level_filter.get('level_id')}].must_not_be_execution_authority")
        if level_filter.get("live_execution_enabled") is not False:
            errors.append(f"promotion_filter[{level_filter.get('level_id')}].live_execution_must_be_false")
    if observed_level_ids and observed_level_ids != [f"L{level}" for level in range(10)]:
        errors.append("promotion_filters_level_order_must_be_L0_through_L9")
    expected_hash = dict(dashboard)
    expected_hash["dashboard_hash"] = ""
    if dashboard.get("dashboard_hash") != canonical_hash(expected_hash):
        errors.append("dashboard_hash_mismatch")
    first_row = _mapping(rows[0]) if rows else {}
    first_gate = _mapping(first_row.get("current_gate"))
    return OperatorWorkflowDashboardValidation(
        ok=not errors,
        errors=tuple(errors),
        dashboard_path=_path_label(dashboard_path),
        status=str(first_row.get("status") or ""),
        current_gate=str(first_gate.get("stage_id") or ""),
    )


def write_operator_workflow_dashboard_read_model(dashboard: Mapping[str, Any], output_path: Path) -> Path:
    """Write a deterministic dashboard read model."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(dashboard, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _stage_plan(raw_stage_plan: Any) -> list[Mapping[str, Any]]:
    if not isinstance(raw_stage_plan, list):
        return []
    return [stage for stage in raw_stage_plan if isinstance(stage, Mapping)]


def _current_gate(stage_plan: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    selected = next(
        (stage for stage in stage_plan if str(stage.get("status") or "") not in {"complete", "ready"}),
        None,
    )
    if selected is None:
        selected = stage_plan[-1] if stage_plan else {}
    stage_type = str(selected.get("stage_type") or "observation")
    if stage_type not in {"skill_execution", "approval_gate", "observation", "communication", "wait_for_event"}:
        stage_type = "observation"
    return {
        "stage_id": str(selected.get("stage_id") or "unknown"),
        "stage_type": stage_type,
        "status": str(selected.get("status") or "pending"),
        "evidence": str(selected.get("evidence") or "none"),
        "projection_only": True,
        "execution_performed": False,
        "external_effects_allowed": False,
    }


def _missing_evidence(
    *,
    next_unlock: str,
    capability_summary: Mapping[str, Any],
    current_gate: Mapping[str, Any],
) -> list[str]:
    raw_next_evidence = capability_summary.get("next_evidence", ())
    if not isinstance(raw_next_evidence, list):
        raw_next_evidence = []
    evidence = [str(item) for item in raw_next_evidence if str(item).strip()]
    if next_unlock and next_unlock != "none":
        evidence.append(next_unlock)
    gate_evidence = str(current_gate.get("evidence") or "")
    if gate_evidence and str(current_gate.get("status") or "") != "complete":
        evidence.append(gate_evidence)
    return list(dict.fromkeys(evidence))[:8]


def _receipt_summary(receipt_card: Mapping[str, Any], source_ref: str) -> dict[str, Any]:
    completed = int(receipt_card.get("sandbox_receipts_completed", 0) or 0)
    required = int(receipt_card.get("sandbox_receipts_required", 0) or 0)
    return {
        "status": "complete" if required and completed >= required else "pending",
        "completed": completed,
        "required": required,
        "receipt_hash": str(receipt_card.get("receipt_hash") or ""),
        "receipt_groups": [
            "local_workflow_receipt",
            "workflow_status",
            "safe_local_action",
        ],
        "source_ref": source_ref,
        "execution_performed": False,
        "external_effects_allowed": False,
    }


def _rollback_summary(receipt_card: Mapping[str, Any]) -> dict[str, Any]:
    required = receipt_card.get("rollback_required") is True
    command_count = int(receipt_card.get("rollback_command_count", 0) or 0)
    return {
        "required": required,
        "status": "required_not_executed" if required else "not_required",
        "command_count": command_count,
        "executed": False,
        "execution_performed": False,
        "external_effects_allowed": False,
    }


def _promotion_filters(capability_passports: Mapping[str, Any] | None) -> dict[str, Any]:
    passport_set = dict(capability_passports or build_capability_passports())
    raw_passports = passport_set.get("passports")
    if not isinstance(raw_passports, list) or not raw_passports:
        raise ValueError("capability_passports_required_for_promotion_filters")
    promotion_counts = _promotion_level_counts(raw_passports)
    levels = []
    for level in default_capability_promotion_ladder():
        levels.append(
            {
                "level_id": level.level_id,
                "level_number": level.level,
                "level_name": level.name,
                "summary": level.summary,
                "capability_count": promotion_counts[level.level_id],
                "requires_operator_approval": level.requires_operator_approval,
                "requires_receipt": level.requires_receipt,
                "requires_rollback": level.requires_rollback,
                "requires_live_witness": level.requires_live_witness,
                "filter_query": f"current_promotion_level == '{level.level_id}'",
                "filter_is_not_execution_authority": True,
                "live_execution_enabled": False,
            }
        )
    return {
        "ladder_id": CAPABILITY_PROMOTION_LADDER_ID,
        "source_ref": str(passport_set.get("passport_set_id") or "capability_passports.foundation.v1"),
        "capability_count": sum(promotion_counts.values()),
        "level_counts": promotion_counts,
        "levels": levels,
        "filter_is_not_execution_authority": True,
        "live_execution_enabled": False,
        "external_effects_allowed": False,
    }


def _promotion_level_counts(raw_passports: Sequence[Any]) -> dict[str, int]:
    counts = {f"L{level}": 0 for level in range(10)}
    for raw_passport in raw_passports:
        if not isinstance(raw_passport, Mapping):
            raise ValueError("capability_passport_entries_must_be_objects")
        level_id = str(raw_passport.get("current_promotion_level") or "")
        if level_id not in counts:
            capability_id = str(raw_passport.get("capability_id") or "<unknown>")
            raise ValueError(f"unsupported_capability_promotion_level:{capability_id}:{level_id}")
        if raw_passport.get("promotion_level_is_not_execution_authority") is not True:
            capability_id = str(raw_passport.get("capability_id") or "<unknown>")
            raise ValueError(f"capability_promotion_level_claims_authority:{capability_id}")
        counts[level_id] += 1
    return counts


def _approval_summary(
    local_workflow_receipt: Mapping[str, Any],
    workflow_status: Mapping[str, Any],
    current_gate: Mapping[str, Any],
    operator_controls: Mapping[str, Any],
) -> dict[str, Any]:
    summary = _mapping(workflow_status.get("summary"))
    external_approval_status = str(summary.get("external_approval_status") or "pending")
    gate_requires_approval = str(current_gate.get("stage_type") or "") == "approval_gate"
    approval_required = (
        operator_controls.get("approval_required_before_external_pr") is True
        or gate_requires_approval
        or "approval" in str(local_workflow_receipt.get("status") or "")
    )
    return {
        "needed": approval_required,
        "status": external_approval_status,
        "gate": "approval_handoff" if approval_required else "none",
        "approval_boundary": "external_pr_execution" if approval_required else "none",
        "performed": False,
        "external_effects_allowed": False,
    }


def _readiness_lane(
    *,
    current_gate: Mapping[str, Any],
    missing_evidence: Sequence[str],
    approval: Mapping[str, Any],
    closure_packet: Mapping[str, Any],
    rehearsal: Mapping[str, Any],
    causal_repair: Mapping[str, Any],
) -> dict[str, Any]:
    required_evidence_refs = _readiness_required_evidence_refs(
        missing_evidence=missing_evidence,
        closure_packet=closure_packet,
        rehearsal=rehearsal,
        causal_repair=causal_repair,
    )
    blocked_repair_action = _first_governance_blocked_repair_action(causal_repair)
    if blocked_repair_action:
        lane_status = "blocked_by_causal_repair"
        proof_state = "Fail(repair_requires_governance)"
        operator_outcome = "GovernanceBlocked"
        primary_blocker = str(blocked_repair_action.get("failure_id") or "causal_repair")
        next_action = str(blocked_repair_action.get("next_action") or "inspect causal repair blocker")
    elif closure_packet.get("linked") is not True:
        lane_status = "awaiting_closure_packet"
        proof_state = "AwaitingEvidence"
        operator_outcome = "AwaitingEvidence"
        primary_blocker = "local_workflow_closure_packet"
        next_action = str(closure_packet.get("next_required_proof_step") or "run local workflow closure packet builder")
    elif rehearsal.get("linked") is not True:
        lane_status = "awaiting_rehearsal_receipt"
        proof_state = "AwaitingEvidence"
        operator_outcome = "AwaitingEvidence"
        primary_blocker = "safe_local_action_rehearsal_receipt"
        next_action = "run safe local action rehearsal"
    elif causal_repair.get("linked") is not True:
        lane_status = "awaiting_causal_repair_receipt"
        proof_state = "AwaitingEvidence"
        operator_outcome = "AwaitingEvidence"
        primary_blocker = "causal_repair_service_receipt"
        next_action = "run causal repair service receipt projection"
    elif approval.get("needed") is True and approval.get("performed") is not True:
        lane_status = "awaiting_approval_evidence"
        proof_state = "AwaitingEvidence"
        operator_outcome = "AwaitingEvidence"
        primary_blocker = str(approval.get("approval_boundary") or "approval_boundary")
        next_action = "collect approval receipt; approval display does not authorize execution"
    elif required_evidence_refs:
        lane_status = "awaiting_evidence"
        proof_state = "AwaitingEvidence"
        operator_outcome = "AwaitingEvidence"
        primary_blocker = required_evidence_refs[0]
        next_action = "collect missing evidence refs for the current gate"
    else:
        lane_status = "ready_for_review_only_handoff"
        proof_state = "SolvedUnverified"
        operator_outcome = "SolvedUnverified"
        primary_blocker = "none"
        next_action = "review dashboard lane; live execution remains blocked"

    return {
        "lane_id": "operator_workflow_dashboard.readiness_lane.foundation.v1",
        "lane_status": lane_status,
        "proof_state": proof_state,
        "operator_outcome": operator_outcome,
        "primary_blocker": primary_blocker,
        "current_gate_id": str(current_gate.get("stage_id") or "unknown"),
        "next_action": next_action,
        "required_evidence_refs": required_evidence_refs[:12],
        "linked_receipts": {
            "closure_packet": closure_packet.get("linked") is True,
            "safe_local_action_rehearsal": rehearsal.get("linked") is True,
            "causal_repair": causal_repair.get("linked") is True,
        },
        "readiness_is_not_execution_authority": True,
        "projection_only": True,
        "execution_authority_granted": False,
        "live_execution_enabled": False,
        "external_effects_allowed": False,
    }


def _readiness_required_evidence_refs(
    *,
    missing_evidence: Sequence[str],
    closure_packet: Mapping[str, Any],
    rehearsal: Mapping[str, Any],
    causal_repair: Mapping[str, Any],
) -> list[str]:
    evidence_refs: list[str] = []
    if closure_packet.get("linked") is not True:
        evidence_refs.append("local_workflow_closure_packet")
    if rehearsal.get("linked") is not True:
        evidence_refs.append("safe_local_action_rehearsal_receipt")
    if causal_repair.get("linked") is not True:
        evidence_refs.append("causal_repair_service_receipt")
    for repair_action in causal_repair.get("next_actions", ()):
        if isinstance(repair_action, Mapping):
            failure_id = str(repair_action.get("failure_id") or "")
            if failure_id:
                evidence_refs.append(f"causal_repair:{failure_id}")
    raw_closure_refs = closure_packet.get("missing_evidence_refs", ())
    if isinstance(raw_closure_refs, list):
        evidence_refs.extend(str(item) for item in raw_closure_refs if str(item).strip())
    evidence_refs.extend(str(item) for item in missing_evidence if str(item).strip())
    return list(dict.fromkeys(evidence_refs))


def _first_governance_blocked_repair_action(causal_repair: Mapping[str, Any]) -> Mapping[str, Any] | None:
    raw_actions = causal_repair.get("next_actions", ())
    if not isinstance(raw_actions, list):
        return None
    for action in raw_actions:
        if isinstance(action, Mapping) and action.get("operator_outcome") == "GovernanceBlocked":
            return action
    return None


def _closure_packet_summary(
    *,
    closure_packet: Mapping[str, Any] | None,
    source_ref: str,
) -> dict[str, Any]:
    if closure_packet is None:
        return {
            "linked": False,
            "source_ref": source_ref,
            "packet_id": "absent",
            "status": "absent",
            "solver_outcome": "AwaitingEvidence",
            "current_gate": {
                "gate_id": "closure_packet_absent",
                "gate_type": "observation",
                "status": "missing",
                "projection_only": True,
                "execution_performed": False,
            },
            "missing_evidence_refs": ["local_workflow_closure_packet"],
            "next_required_proof_step": "run local workflow closure packet builder",
            "approval_boundary": {
                "approval_request_id": "none",
                "approval_required": False,
                "approval_status": "not_requested",
                "approval_performed": False,
                "approval_does_not_authorize_execution": True,
            },
            "rollback": {
                "required": False,
                "strategy": "none",
                "rollback_executed": False,
                "execution_performed": False,
            },
            "command_preview_refs": [],
            "packet_hash": "",
            "projection_only": True,
            "execution_performed": False,
            "external_effects_allowed": False,
        }

    _validate_closure_packet_boundary(closure_packet)
    current_gate = _mapping(closure_packet.get("current_gate"))
    approval_boundary = _mapping(closure_packet.get("approval_boundary"))
    rollback = _mapping(closure_packet.get("rollback"))
    command_preview_refs = []
    raw_command_preview = closure_packet.get("command_preview", ())
    if isinstance(raw_command_preview, list):
        for command_preview in raw_command_preview:
            if not isinstance(command_preview, Mapping):
                continue
            command_preview_refs.append(
                {
                    "command_id": str(command_preview.get("command_id") or "unknown"),
                    "effect": str(command_preview.get("effect") or "unknown"),
                    "execution_allowed": False,
                }
            )
    raw_missing_evidence_refs = closure_packet.get("missing_evidence_refs", ())
    if not isinstance(raw_missing_evidence_refs, list):
        raw_missing_evidence_refs = []
    return {
        "linked": True,
        "source_ref": source_ref,
        "packet_id": str(closure_packet.get("packet_id") or "unknown"),
        "status": str(closure_packet.get("status") or "AwaitingEvidence"),
        "solver_outcome": str(closure_packet.get("solver_outcome") or "AwaitingEvidence"),
        "current_gate": {
            "gate_id": str(current_gate.get("gate_id") or "unknown"),
            "gate_type": str(current_gate.get("gate_type") or "observation"),
            "status": str(current_gate.get("status") or "AwaitingEvidence"),
            "projection_only": True,
            "execution_performed": False,
        },
        "missing_evidence_refs": [str(item) for item in raw_missing_evidence_refs if str(item).strip()][:8],
        "next_required_proof_step": str(
            closure_packet.get("next_required_proof_step") or "collect missing closure evidence"
        ),
        "approval_boundary": {
            "approval_request_id": str(approval_boundary.get("approval_request_id") or "unknown"),
            "approval_required": approval_boundary.get("approval_required") is True,
            "approval_status": str(approval_boundary.get("approval_status") or "pending"),
            "approval_performed": False,
            "approval_does_not_authorize_execution": True,
        },
        "rollback": {
            "required": rollback.get("required") is True,
            "strategy": str(rollback.get("strategy") or "none"),
            "rollback_executed": False,
            "execution_performed": False,
        },
        "command_preview_refs": command_preview_refs[:8],
        "packet_hash": str(closure_packet.get("packet_hash") or ""),
        "projection_only": True,
        "execution_performed": False,
        "external_effects_allowed": False,
    }


def _validate_closure_packet_boundary(closure_packet: Mapping[str, Any]) -> None:
    if closure_packet.get("projection_only") is not True:
        raise ValueError("closure_packet_projection_only_must_be_true")
    if closure_packet.get("packet_is_not_execution_authority") is not True:
        raise ValueError("closure_packet_must_not_be_execution_authority")
    if closure_packet.get("execution_performed") is not False:
        raise ValueError("closure_packet_execution_must_be_false")
    if closure_packet.get("external_effects_allowed") is not False:
        raise ValueError("closure_packet_external_effects_must_be_false")
    if closure_packet.get("live_execution_enabled") is not False:
        raise ValueError("closure_packet_live_execution_must_be_false")
    current_gate = _mapping(closure_packet.get("current_gate"))
    if current_gate.get("execution_performed") is not False:
        raise ValueError("closure_packet_current_gate_execution_must_be_false")
    approval_boundary = _mapping(closure_packet.get("approval_boundary"))
    if approval_boundary.get("approval_performed") is not False:
        raise ValueError("closure_packet_approval_performed_must_be_false")
    if approval_boundary.get("approval_does_not_authorize_execution") is not True:
        raise ValueError("closure_packet_approval_must_not_authorize_execution")
    rollback = _mapping(closure_packet.get("rollback"))
    if rollback.get("rollback_executed") is not False:
        raise ValueError("closure_packet_rollback_executed_must_be_false")
    if rollback.get("execution_performed") is not False:
        raise ValueError("closure_packet_rollback_execution_must_be_false")
    raw_command_preview = closure_packet.get("command_preview", ())
    if isinstance(raw_command_preview, list):
        for command_preview in raw_command_preview:
            if isinstance(command_preview, Mapping) and command_preview.get("execution_allowed") is not False:
                raise ValueError("closure_packet_command_preview_execution_must_be_false")


def _rehearsal_summary(
    *,
    rehearsal_receipt: Mapping[str, Any] | None,
    source_ref: str,
) -> dict[str, Any]:
    if rehearsal_receipt is None:
        return {
            "linked": False,
            "source_ref": source_ref,
            "receipt_id": "absent",
            "capability_id": "govern.safe_local_action.rehearsal",
            "rehearsal_status": "absent",
            "solver_outcome": "AwaitingEvidence",
            "selected_action": {
                "task": "Safe Local Action Rehearsal",
                "next_action": "run safe local action rehearsal",
                "current_gate": "rehearsal_receipt_absent",
            },
            "scenario_count": 0,
            "scenario_refs": [],
            "approval": {
                "required_for_live_execution": True,
                "approval_status": "not_requested",
                "approval_performed": False,
            },
            "proof_boundary": {
                "rehearsal_is_not_execution_proof": True,
                "post_execution_evidence_required": True,
            },
            "blocked_effects": [],
            "receipt_hash": "",
            "live_execution_enabled": False,
            "execution_performed": False,
            "external_effects_allowed": False,
        }

    _validate_rehearsal_receipt_boundary(rehearsal_receipt)
    selected_action = _mapping(rehearsal_receipt.get("selected_action"))
    approval = _mapping(rehearsal_receipt.get("approval"))
    raw_scenarios = rehearsal_receipt.get("scenarios", ())
    scenarios = raw_scenarios if isinstance(raw_scenarios, list) else []
    return {
        "linked": True,
        "source_ref": source_ref,
        "receipt_id": str(rehearsal_receipt.get("receipt_id") or "unknown"),
        "capability_id": str(rehearsal_receipt.get("capability_id") or "govern.safe_local_action.rehearsal"),
        "rehearsal_status": str(rehearsal_receipt.get("rehearsal_status") or "AwaitingEvidence"),
        "solver_outcome": str(rehearsal_receipt.get("solver_outcome") or "AwaitingEvidence"),
        "selected_action": {
            "task": str(selected_action.get("task") or "Safe Local Action Rehearsal"),
            "next_action": str(selected_action.get("next_action") or "inspect rehearsal receipt"),
            "current_gate": str(selected_action.get("current_gate") or "unknown"),
        },
        "scenario_count": len(scenarios),
        "scenario_refs": [
            {
                "scenario_id": str(scenario.get("scenario_id") or "unknown"),
                "status": str(scenario.get("status") or "unknown"),
                "mutation_performed": False,
            }
            for scenario in scenarios
            if isinstance(scenario, Mapping)
        ][:8],
        "approval": {
            "required_for_live_execution": approval.get("required_for_live_execution") is True,
            "approval_status": str(approval.get("approval_status") or "not_requested"),
            "approval_performed": False,
        },
        "proof_boundary": {
            "rehearsal_is_not_execution_proof": True,
            "post_execution_evidence_required": True,
        },
        "blocked_effects": _string_list(rehearsal_receipt.get("blocked_effects"))[:12],
        "receipt_hash": str(rehearsal_receipt.get("receipt_hash") or ""),
        "live_execution_enabled": False,
        "execution_performed": False,
        "external_effects_allowed": False,
    }


def _validate_rehearsal_receipt_boundary(rehearsal_receipt: Mapping[str, Any]) -> None:
    if rehearsal_receipt.get("rehearsal_is_not_execution_proof") is not True:
        raise ValueError("rehearsal_must_not_claim_execution_proof")
    if rehearsal_receipt.get("post_execution_evidence_required") is not True:
        raise ValueError("rehearsal_post_execution_evidence_required")
    if rehearsal_receipt.get("live_execution_enabled") is not False:
        raise ValueError("rehearsal_live_execution_must_be_false")
    effect_boundary = _mapping(rehearsal_receipt.get("effect_boundary"))
    for key, value in effect_boundary.items():
        if str(key).endswith("_allowed") and value is not False:
            raise ValueError(f"rehearsal_effect_boundary_must_be_false:{key}")
    approval = _mapping(rehearsal_receipt.get("approval"))
    if approval.get("approval_performed") is not False:
        raise ValueError("rehearsal_approval_performed_must_be_false")
    raw_scenarios = rehearsal_receipt.get("scenarios", ())
    if isinstance(raw_scenarios, list):
        for scenario in raw_scenarios:
            if not isinstance(scenario, Mapping):
                continue
            if scenario.get("proof_only") is not True:
                raise ValueError("rehearsal_scenario_proof_only_must_be_true")
            if scenario.get("mutation_performed") is not False:
                raise ValueError("rehearsal_scenario_mutation_must_be_false")
            if scenario.get("external_effects_allowed") is not False:
                raise ValueError("rehearsal_scenario_external_effects_must_be_false")


def _causal_repair_summary(
    *,
    causal_repair_receipt: Mapping[str, Any] | None,
    source_ref: str,
) -> dict[str, Any]:
    if causal_repair_receipt is None:
        return {
            "linked": False,
            "source_ref": source_ref,
            "receipt_id": "absent",
            "service_id": "mcoi.causal_repair.service",
            "service_status": "absent",
            "solver_outcome": "AwaitingEvidence",
            "case_count": 0,
            "high_severity_cases": [],
            "next_actions": [],
            "blocked_effects": [],
            "receipt_hash": "",
            "live_execution_enabled": False,
            "repair_execution_performed": False,
        }

    _validate_causal_repair_receipt_boundary(causal_repair_receipt)
    raw_cases = causal_repair_receipt.get("cases", ())
    cases = raw_cases if isinstance(raw_cases, list) else []
    high_severity_cases = [
        str(case.get("failure_id") or "unknown")
        for case in cases
        if isinstance(case, Mapping) and str(case.get("severity") or "") in {"high", "critical"}
    ]
    next_actions = []
    for case in cases:
        if not isinstance(case, Mapping):
            continue
        proposal = _mapping(case.get("proposal"))
        next_actions.append(
            {
                "failure_id": str(case.get("failure_id") or "unknown"),
                "operator_outcome": str(proposal.get("operator_outcome") or "AwaitingEvidence"),
                "next_action": str(proposal.get("next_action") or "inspect repair case"),
                "execution_performed": False,
            }
        )
    return {
        "linked": True,
        "source_ref": source_ref,
        "receipt_id": str(causal_repair_receipt.get("receipt_id") or "unknown"),
        "service_id": str(causal_repair_receipt.get("service_id") or "mcoi.causal_repair.service"),
        "service_status": str(causal_repair_receipt.get("service_status") or "AwaitingEvidence"),
        "solver_outcome": str(causal_repair_receipt.get("solver_outcome") or "AwaitingEvidence"),
        "case_count": len(cases),
        "high_severity_cases": high_severity_cases[:8],
        "next_actions": next_actions[:8],
        "blocked_effects": _string_list(causal_repair_receipt.get("blocked_effects"))[:12],
        "receipt_hash": str(causal_repair_receipt.get("receipt_hash") or ""),
        "live_execution_enabled": False,
        "repair_execution_performed": False,
    }


def _validate_causal_repair_receipt_boundary(causal_repair_receipt: Mapping[str, Any]) -> None:
    if causal_repair_receipt.get("live_execution_enabled") is not False:
        raise ValueError("causal_repair_live_execution_must_be_false")
    if causal_repair_receipt.get("repair_execution_performed") is not False:
        raise ValueError("causal_repair_execution_must_be_false")
    raw_cases = causal_repair_receipt.get("cases", ())
    if isinstance(raw_cases, list):
        for case in raw_cases:
            if not isinstance(case, Mapping):
                continue
            proof = _mapping(case.get("rollback_or_compensation_proof"))
            if proof.get("execution_performed") is not False:
                raise ValueError("causal_repair_case_execution_must_be_false")
            proposal = _mapping(case.get("proposal"))
            if case.get("failure_id") == "rollback_impossible" and proposal.get("operator_outcome") != "GovernanceBlocked":
                raise ValueError("causal_repair_rollback_impossible_must_be_blocked")


def _load_local_workflow_receipt(path: Path | None) -> tuple[dict[str, Any], str]:
    if path is not None:
        read_model = _load_json_object(path)
        validation = validate_operator_local_developer_workflow_receipt_read_model(
            read_model=read_model,
            read_model_path=path,
        )
        if not validation.ok:
            raise ValueError(f"local_workflow_receipt_invalid:{list(validation.errors)}")
        return read_model, _path_label(path)
    operator_receipt, operator_source_ref = _load_operator_receipt(None)
    control_tower_receipt, control_tower_source_ref = _load_control_tower_status_receipt(None)
    return build_operator_local_developer_workflow_receipt_read_model(
        operator_receipt=operator_receipt,
        operator_receipt_source_ref=operator_source_ref,
        control_tower_status_receipt=control_tower_receipt,
        control_tower_source_ref=control_tower_source_ref,
    ), "<generated-local-workflow-receipt-read-model>"


def _load_closure_packet(path: Path | None) -> tuple[dict[str, Any] | None, str]:
    if path is None or not path.exists():
        return None, "absent"
    closure_packet = _load_json_object(path)
    _validate_closure_packet_boundary(closure_packet)
    return closure_packet, _path_label(path)


def _load_rehearsal_receipt(path: Path | None) -> tuple[dict[str, Any] | None, str]:
    if path is None or not path.exists():
        return None, "absent"
    rehearsal_receipt = _load_json_object(path)
    _validate_rehearsal_receipt_boundary(rehearsal_receipt)
    return rehearsal_receipt, _path_label(path)


def _load_causal_repair_receipt(path: Path | None) -> tuple[dict[str, Any] | None, str]:
    if path is None or not path.exists():
        return None, "absent"
    causal_repair_receipt = _load_json_object(path)
    _validate_causal_repair_receipt_boundary(causal_repair_receipt)
    return causal_repair_receipt, _path_label(path)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"json_parse_failed:{path}") from exc
    if not isinstance(payload, dict):
        raise ValueError("json_root_must_be_object")
    return payload


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse operator workflow dashboard arguments."""

    parser = argparse.ArgumentParser(description="Build unified operator workflow dashboard.")
    parser.add_argument("--local-workflow-receipt", default="", help="Optional local workflow receipt read-model path.")
    parser.add_argument(
        "--closure-packet",
        default=str(DEFAULT_CLOSURE_PACKET),
        help="Optional local developer workflow closure packet path.",
    )
    parser.add_argument(
        "--safe-local-action-rehearsal",
        default=str(DEFAULT_REHEARSAL_RECEIPT),
        help="Optional safe local action rehearsal receipt path.",
    )
    parser.add_argument(
        "--causal-repair",
        default=str(DEFAULT_CAUSAL_REPAIR_RECEIPT),
        help="Optional causal repair service receipt path.",
    )
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for the operator workflow dashboard projection."""

    args = parse_args(argv)
    output_path = Path(args.output)
    schema_path = Path(args.schema)
    try:
        local_workflow_receipt, source_ref = _load_local_workflow_receipt(
            Path(args.local_workflow_receipt) if args.local_workflow_receipt else None
        )
        closure_packet, closure_packet_source_ref = _load_closure_packet(
            Path(args.closure_packet) if args.closure_packet else None
        )
        rehearsal_receipt, rehearsal_receipt_source_ref = _load_rehearsal_receipt(
            Path(args.safe_local_action_rehearsal) if args.safe_local_action_rehearsal else None
        )
        causal_repair_receipt, causal_repair_receipt_source_ref = _load_causal_repair_receipt(
            Path(args.causal_repair) if args.causal_repair else None
        )
        dashboard = build_operator_workflow_dashboard_read_model(
            local_workflow_receipt=local_workflow_receipt,
            local_workflow_source_ref=source_ref,
            closure_packet=closure_packet,
            closure_packet_source_ref=closure_packet_source_ref,
            rehearsal_receipt=rehearsal_receipt,
            rehearsal_receipt_source_ref=rehearsal_receipt_source_ref,
            causal_repair_receipt=causal_repair_receipt,
            causal_repair_receipt_source_ref=causal_repair_receipt_source_ref,
        )
        written_path = write_operator_workflow_dashboard_read_model(dashboard, output_path)
        validation = validate_operator_workflow_dashboard_read_model(
            dashboard=dashboard,
            schema_path=schema_path,
            dashboard_path=written_path,
        )
    except ValueError as exc:
        print(f"OPERATOR WORKFLOW DASHBOARD INVALID error={exc}")
        return 2
    if not validation.ok:
        print(f"OPERATOR WORKFLOW DASHBOARD INVALID errors={list(validation.errors)}")
        return 2
    if args.json:
        print(json.dumps(dashboard, indent=2, sort_keys=True))
    else:
        print(f"OPERATOR WORKFLOW DASHBOARD BUILT path={written_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
