"""Operator workflow dashboard projection.

Purpose: unify local workflow receipt, workflow status, and safe-local action
    projections into one operator-facing read model.
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
from mcoi_runtime.app.capability_passports import build_capability_passports  # noqa: E402


SCHEMA_REF = "urn:mullusi:schema:operator-workflow-dashboard-read-model:1"
READ_MODEL_ID = "operator_workflow_dashboard.read_model"
DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "operator_workflow_dashboard_read_model.schema.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "operator_workflow_dashboard.read_model.generated.json"


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
        },
        "source_refs": {
            "builder": "gateway/operator_workflow_dashboard.py",
            "local_workflow_receipt": local_workflow_source_ref,
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
        if receipts.get("execution_performed") is not False:
            errors.append(f"rows[{index}].receipts_execution_performed_must_be_false")
        if rollback.get("executed") is not False:
            errors.append(f"rows[{index}].rollback_executed_must_be_false")
        if approval.get("performed") is not False:
            errors.append(f"rows[{index}].approval_performed_must_be_false")
        if current_gate.get("execution_performed") is not False:
            errors.append(f"rows[{index}].current_gate_execution_performed_must_be_false")
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


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


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
        dashboard = build_operator_workflow_dashboard_read_model(
            local_workflow_receipt=local_workflow_receipt,
            local_workflow_source_ref=source_ref,
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
