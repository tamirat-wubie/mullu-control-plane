#!/usr/bin/env python3
"""Build the local Developer Workflow receipt card read model.

Purpose: compose the Developer Workflow operator receipt, compact workflow
status projection, and safe-local action queue into one operator-facing card.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: Developer Workflow operator receipt builder, status read-model
builder, and safe-local action read-model builder.
Invariants:
  - This script is projection-only and never executes workflow stages.
  - External effects, PR creation, branch push, merge, deployment, connector
    calls, email sends, money movement, and production writes remain disabled.
  - Stage topology is explicit and acyclic.
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

from scripts.build_developer_workflow_operator_receipt import (  # noqa: E402
    DEFAULT_APPROVAL_PACKET,
    DEFAULT_COMMAND_PREVIEW,
    DEFAULT_EXTERNAL_WITNESS,
    DEFAULT_LOCAL_CANDIDATE,
    DEFAULT_METADATA,
    DEFAULT_OUTPUT as DEFAULT_OPERATOR_RECEIPT,
    DEFAULT_PR_READINESS,
    DEFAULT_PR_TOOL_ADMISSION,
    DEFAULT_SANDBOX_RECEIPTS,
    build_developer_workflow_operator_receipt,
    validate_developer_workflow_operator_receipt,
)
from scripts.build_operator_developer_workflow_status_read_model import (  # noqa: E402
    build_operator_developer_workflow_status_read_model,
    validate_operator_developer_workflow_status_read_model,
)
from scripts.build_operator_safe_local_action_read_model import (  # noqa: E402
    build_operator_safe_local_action_read_model,
    validate_operator_safe_local_action_read_model,
)
from scripts.validate_operator_control_tower_status_receipt import (  # noqa: E402
    build_default_operator_control_tower_status_receipt,
    validate_operator_control_tower_status_receipt,
)


DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "operator_local_developer_workflow_receipt_read_model.generated.json"
FORBIDDEN_EFFECTS = (
    "create_pr",
    "push_branch",
    "merge",
    "deploy",
    "connector_call",
    "send_email",
    "move_money",
    "write_production_data",
)


@dataclass(frozen=True, slots=True)
class OperatorLocalDeveloperWorkflowReceiptValidation:
    """Validation report for the local Developer Workflow receipt card."""

    ok: bool
    errors: tuple[str, ...]
    read_model_path: str
    status: str
    next_unlock: str

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def build_operator_local_developer_workflow_receipt_read_model(
    *,
    operator_receipt: Mapping[str, Any],
    operator_receipt_source_ref: str,
    control_tower_status_receipt: Mapping[str, Any],
    control_tower_source_ref: str,
) -> dict[str, Any]:
    """Return one projection-only local Developer Workflow operator card."""

    status_read_model = build_operator_developer_workflow_status_read_model(
        receipt=operator_receipt,
        source_ref=operator_receipt_source_ref,
    )
    safe_action = build_operator_safe_local_action_read_model(
        status_receipt=control_tower_status_receipt,
        source_ref=control_tower_source_ref,
    )
    stage_plan = _local_workflow_stage_plan(status_read_model, safe_action)
    next_unlock = str(status_read_model.get("next_unlock") or "none")
    return {
        "read_model_id": "operator_local_developer_workflow_receipt.read_model",
        "projection_only": True,
        "execution_performed": False,
        "external_effects_allowed": False,
        "task": "Mullu Developer Workflow v1",
        "mode": "fast_lab",
        "status": str(status_read_model.get("status") or "awaiting_sandbox_receipts"),
        "reason": str(status_read_model.get("reason") or "sandbox receipt evidence incomplete"),
        "next_unlock": next_unlock,
        "risk": "low, local lab only" if next_unlock != "external_approval_witness" else "external repository write",
        "action_needed": str(status_read_model.get("action_needed") or f"provide {next_unlock}"),
        "receipt_card": {
            "title": "Local Developer Workflow Receipt",
            "workflow_run_id": str(_mapping(status_read_model.get("summary")).get("workflow_run_id") or ""),
            "solver_outcome": str(_mapping(status_read_model.get("summary")).get("solver_outcome") or "AwaitingEvidence"),
            "receipt_hash": str(_mapping(status_read_model.get("summary")).get("receipt_hash") or ""),
            "sandbox_receipts_completed": int(
                _mapping(status_read_model.get("summary")).get("sandbox_receipts_completed", 0) or 0
            ),
            "sandbox_receipts_required": int(
                _mapping(status_read_model.get("summary")).get("sandbox_receipts_required", 0) or 0
            ),
            "rollback_required": _mapping(status_read_model.get("summary")).get("rollback_required") is True,
            "rollback_command_count": int(
                _mapping(status_read_model.get("summary")).get("rollback_command_count", 0) or 0
            ),
            "execution_performed": False,
            "external_effects_allowed": False,
        },
        "safe_local_action": _safe_local_action_summary(safe_action),
        "stage_plan": stage_plan,
        "operator_controls": {
            "recommended_mode": "fast",
            "lab_mode": True,
            "real_world_mode": False,
            "primary_action": str(_mapping(safe_action.get("candidate")).get("primary_action") or ""),
            "approval_required_for_primary_action": False,
            "approval_required_before_external_pr": True,
            "blocked_effects": list(FORBIDDEN_EFFECTS),
            "projection_only": True,
            "execution_performed": False,
            "external_effects_allowed": False,
        },
        "workflow_status": status_read_model,
        "source_refs": {
            "developer_workflow_operator_receipt": operator_receipt_source_ref,
            "control_tower_status_receipt": control_tower_source_ref,
            "status_read_model": "scripts/build_operator_developer_workflow_status_read_model.py",
            "safe_local_action_read_model": "scripts/build_operator_safe_local_action_read_model.py",
        },
    }


def validate_operator_local_developer_workflow_receipt_read_model(
    *,
    read_model: Mapping[str, Any],
    read_model_path: Path = Path("<generated>"),
) -> OperatorLocalDeveloperWorkflowReceiptValidation:
    """Validate no-effect semantics and topology for the composed card."""

    errors: list[str] = []
    if read_model.get("read_model_id") != "operator_local_developer_workflow_receipt.read_model":
        errors.append("read_model_id_invalid")
    if read_model.get("projection_only") is not True:
        errors.append("projection_only_must_be_true")
    if read_model.get("execution_performed") is not False:
        errors.append("execution_performed_must_be_false")
    if read_model.get("external_effects_allowed") is not False:
        errors.append("external_effects_must_be_false")
    receipt_card = _mapping(read_model.get("receipt_card"))
    if receipt_card.get("execution_performed") is not False:
        errors.append("receipt_card_execution_performed_must_be_false")
    if receipt_card.get("external_effects_allowed") is not False:
        errors.append("receipt_card_external_effects_must_be_false")
    safe_action = _mapping(read_model.get("safe_local_action"))
    if safe_action.get("approval_required") is not False:
        errors.append("safe_action_approval_required_must_be_false")
    if safe_action.get("external_effects_allowed") is not False:
        errors.append("safe_action_external_effects_must_be_false")
    if safe_action.get("execution_boundary") != "local_lab_only":
        errors.append("safe_action_boundary_must_be_local_lab_only")
    controls = _mapping(read_model.get("operator_controls"))
    if controls.get("projection_only") is not True:
        errors.append("controls_projection_only_must_be_true")
    if controls.get("execution_performed") is not False:
        errors.append("controls_execution_performed_must_be_false")
    if controls.get("external_effects_allowed") is not False:
        errors.append("controls_external_effects_must_be_false")
    blocked_effects = controls.get("blocked_effects", ())
    if not isinstance(blocked_effects, list):
        errors.append("blocked_effects_must_be_list")
        blocked_effects = []
    for forbidden_effect in FORBIDDEN_EFFECTS:
        if forbidden_effect not in blocked_effects:
            errors.append(f"blocked_effect_missing:{forbidden_effect}")
    _validate_stage_plan(read_model.get("stage_plan"), errors)
    workflow_status = _mapping(read_model.get("workflow_status"))
    workflow_validation = validate_operator_developer_workflow_status_read_model(read_model=workflow_status)
    if not workflow_validation.ok:
        errors.extend(f"workflow_status:{error}" for error in workflow_validation.errors)
    return OperatorLocalDeveloperWorkflowReceiptValidation(
        ok=not errors,
        errors=tuple(errors),
        read_model_path=_path_label(read_model_path),
        status=str(read_model.get("status") or ""),
        next_unlock=str(read_model.get("next_unlock") or ""),
    )


def write_operator_local_developer_workflow_receipt_read_model(
    read_model: Mapping[str, Any],
    output_path: Path,
) -> Path:
    """Write a deterministic composed operator read model."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(read_model, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _local_workflow_stage_plan(
    status_read_model: Mapping[str, Any],
    safe_action: Mapping[str, Any],
) -> list[dict[str, Any]]:
    summary = _mapping(status_read_model.get("summary"))
    sandbox_complete = int(summary.get("sandbox_receipts_completed", 0) or 0) >= int(
        summary.get("sandbox_receipts_required", 0) or 0
    )
    safe_candidate_ready = str(safe_action.get("queue_status") or "") == "ready"
    return [
        _stage("request_intake", (), "complete", "operator request captured", "observation"),
        _stage(
            "safe_local_action_selected",
            ("request_intake",),
            "ready" if safe_candidate_ready else "pending",
            "safe local action candidate selected",
            "observation",
        ),
        _stage(
            "sandbox_receipts",
            ("safe_local_action_selected",),
            "complete" if sandbox_complete else "pending",
            "before state, after state, diff, command, and rollback receipts",
            "local_lab_receipt",
        ),
        _stage("test_gate", ("sandbox_receipts",), "pending", "bounded local test receipt", "local_lab_receipt"),
        _stage("diff_review", ("test_gate",), "pending", "reviewed diff hash", "observation"),
        _stage("terminal_receipt", ("diff_review",), "pending", "no-external-effect terminal receipt", "observation"),
        _stage("approval_handoff", ("terminal_receipt",), "blocked", "external PR approval boundary", "approval_gate"),
    ]


def _stage(
    stage_id: str,
    predecessors: Sequence[str],
    status: str,
    evidence: str,
    stage_type: str,
) -> dict[str, Any]:
    return {
        "stage_id": stage_id,
        "stage_type": stage_type,
        "predecessors": list(predecessors),
        "status": status,
        "evidence": evidence,
        "projection_only": True,
        "execution_performed": False,
        "external_effects_allowed": False,
    }


def _safe_local_action_summary(safe_action: Mapping[str, Any]) -> dict[str, Any]:
    candidate = _mapping(safe_action.get("candidate"))
    return {
        "queue_status": str(safe_action.get("queue_status") or ""),
        "candidate_count": int(safe_action.get("candidate_count", 0) or 0),
        "candidate_id": str(candidate.get("candidate_id") or ""),
        "zone": str(candidate.get("zone") or ""),
        "title": str(candidate.get("title") or ""),
        "primary_action": str(candidate.get("primary_action") or ""),
        "primary_href": str(candidate.get("primary_href") or ""),
        "approval_required": False,
        "execution_boundary": "local_lab_only",
        "external_effects_allowed": False,
    }


def _validate_stage_plan(stage_plan: Any, errors: list[str]) -> None:
    if not isinstance(stage_plan, list) or not stage_plan:
        errors.append("stage_plan_must_be_non_empty_list")
        return
    seen: set[str] = set()
    for index, stage in enumerate(stage_plan):
        if not isinstance(stage, Mapping):
            errors.append(f"stage_plan[{index}]_must_be_object")
            continue
        stage_id = str(stage.get("stage_id") or "")
        if not stage_id:
            errors.append(f"stage_plan[{index}]_missing_stage_id")
        if stage_id in seen:
            errors.append(f"stage_plan_duplicate_stage:{stage_id}")
        predecessors = stage.get("predecessors", ())
        if not isinstance(predecessors, list):
            errors.append(f"stage_plan[{stage_id}].predecessors_must_be_list")
            predecessors = []
        for predecessor in predecessors:
            if str(predecessor) not in seen:
                errors.append(f"stage_plan[{stage_id}].dangling_or_cyclic_predecessor:{predecessor}")
        if stage.get("projection_only") is not True:
            errors.append(f"stage_plan[{stage_id}].projection_only_must_be_true")
        if stage.get("execution_performed") is not False:
            errors.append(f"stage_plan[{stage_id}].execution_performed_must_be_false")
        if stage.get("external_effects_allowed") is not False:
            errors.append(f"stage_plan[{stage_id}].external_effects_must_be_false")
        seen.add(stage_id)


def _load_operator_receipt(operator_receipt_path: Path | None) -> tuple[dict[str, Any], str]:
    if operator_receipt_path is not None:
        receipt = _load_json_object(operator_receipt_path)
        validation = validate_developer_workflow_operator_receipt(
            receipt=receipt,
            receipt_path=operator_receipt_path,
        )
        if not validation.ok:
            raise ValueError(f"operator_receipt_invalid:{list(validation.errors)}")
        return receipt, _path_label(operator_receipt_path)
    paths = {
        "sandbox_receipts": DEFAULT_SANDBOX_RECEIPTS,
        "approval_packet": DEFAULT_APPROVAL_PACKET,
        "local_candidate": DEFAULT_LOCAL_CANDIDATE,
        "pr_tool_admission": DEFAULT_PR_TOOL_ADMISSION,
        "external_witness": DEFAULT_EXTERNAL_WITNESS,
        "command_preview": DEFAULT_COMMAND_PREVIEW,
        "metadata": DEFAULT_METADATA,
        "pr_readiness": DEFAULT_PR_READINESS,
    }
    payloads = {key: _load_json_object(path) for key, path in paths.items()}
    receipt = build_developer_workflow_operator_receipt(
        sandbox_receipts=payloads["sandbox_receipts"],
        sandbox_receipts_path=paths["sandbox_receipts"],
        approval_packet=payloads["approval_packet"],
        approval_packet_path=paths["approval_packet"],
        local_candidate=payloads["local_candidate"],
        local_candidate_path=paths["local_candidate"],
        pr_tool_admission=payloads["pr_tool_admission"],
        pr_tool_admission_path=paths["pr_tool_admission"],
        external_witness=payloads["external_witness"],
        external_witness_path=paths["external_witness"],
        command_preview=payloads["command_preview"],
        command_preview_path=paths["command_preview"],
        metadata=payloads["metadata"],
        metadata_path=paths["metadata"],
        pr_readiness=payloads["pr_readiness"],
        pr_readiness_path=paths["pr_readiness"],
    )
    return receipt, "<generated-developer-workflow-operator-receipt>"


def _load_control_tower_status_receipt(status_receipt_path: Path | None) -> tuple[dict[str, Any], str]:
    if status_receipt_path is None:
        return build_default_operator_control_tower_status_receipt(), "<generated-control-tower-status-receipt>"
    validation = validate_operator_control_tower_status_receipt(receipt_path=status_receipt_path)
    if not validation.ok:
        raise ValueError(f"control_tower_status_receipt_invalid:{list(validation.errors)}")
    return _load_json_object(status_receipt_path), _path_label(status_receipt_path)


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
    """Parse composed local Developer Workflow receipt arguments."""

    parser = argparse.ArgumentParser(description="Build local Developer Workflow receipt read model.")
    parser.add_argument("--operator-receipt", default="", help="Optional Developer Workflow operator receipt path.")
    parser.add_argument("--status-receipt", default="", help="Optional operator control tower status receipt path.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for the composed receipt card read model."""

    args = parse_args(argv)
    output_path = Path(args.output)
    try:
        operator_receipt, operator_source_ref = _load_operator_receipt(
            Path(args.operator_receipt) if args.operator_receipt else None
        )
        control_tower_status_receipt, control_tower_source_ref = _load_control_tower_status_receipt(
            Path(args.status_receipt) if args.status_receipt else None
        )
        read_model = build_operator_local_developer_workflow_receipt_read_model(
            operator_receipt=operator_receipt,
            operator_receipt_source_ref=operator_source_ref,
            control_tower_status_receipt=control_tower_status_receipt,
            control_tower_source_ref=control_tower_source_ref,
        )
        written_path = write_operator_local_developer_workflow_receipt_read_model(read_model, output_path)
        validation = validate_operator_local_developer_workflow_receipt_read_model(
            read_model=read_model,
            read_model_path=written_path,
        )
    except ValueError as exc:
        print(f"OPERATOR LOCAL DEVELOPER WORKFLOW RECEIPT INVALID error={exc}")
        return 2
    if not validation.ok:
        print(f"OPERATOR LOCAL DEVELOPER WORKFLOW RECEIPT INVALID errors={list(validation.errors)}")
        return 2
    if args.json:
        print(json.dumps(read_model, indent=2, sort_keys=True))
    else:
        print(f"OPERATOR LOCAL DEVELOPER WORKFLOW RECEIPT BUILT path={written_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
