#!/usr/bin/env python3
"""Build the compact Developer Workflow operator status read model.

Purpose: turn a generated Developer Workflow operator receipt into the
one-row dashboard read model used by the operator control tower.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/operator_developer_workflow_status_read_model.schema.json
and scripts.build_developer_workflow_operator_receipt.
Invariants:
  - This script is projection-only and never executes workflow stages.
  - External effects, branch push, PR creation, merge, deployment, and
    connector calls remain disabled.
  - Source receipts and emitted read models are schema validated.
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
    DEFAULT_OUTPUT as DEFAULT_OPERATOR_RECEIPT,
    validate_developer_workflow_operator_receipt,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "operator_developer_workflow_status_read_model.schema.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "operator_developer_workflow_status_read_model.generated.json"


@dataclass(frozen=True, slots=True)
class OperatorDeveloperWorkflowStatusValidation:
    """Validation report for the compact Developer Workflow status read model."""

    ok: bool
    errors: tuple[str, ...]
    read_model_path: str
    status: str
    next_unlock: str

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def build_operator_developer_workflow_status_read_model(
    *,
    receipt: Mapping[str, Any],
    source_ref: str,
) -> dict[str, Any]:
    """Return a projection-only Developer Workflow status read model."""

    operator_status = _developer_workflow_operator_status(receipt)
    readiness_status = str(operator_status["readiness_status"])
    first_next_evidence = str(operator_status["first_next_evidence"])
    control_summary = _developer_workflow_control_summary(operator_status)
    action_banner = str(control_summary["action_banner"])
    capability_summary = control_summary["capability_summary"]
    return {
        "read_model_id": "operator_developer_workflow_status.read_model",
        "projection_only": True,
        "external_effects_allowed": False,
        "task": "Governed Developer Workflow v1",
        "status": readiness_status,
        "reason": _developer_workflow_status_reason(readiness_status, first_next_evidence),
        "next_unlock": first_next_evidence,
        "risk": _developer_workflow_status_risk(readiness_status),
        "action_needed": _developer_workflow_status_action(readiness_status, first_next_evidence),
        "summary": {
            "solver_outcome": operator_status["solver_outcome"],
            "workflow_run_id": operator_status["workflow_run_id"],
            "sandbox_receipts_completed": operator_status["sandbox_receipts_completed"],
            "sandbox_receipts_required": operator_status["sandbox_receipts_required"],
            "local_candidate_ready": operator_status["local_candidate_ready"],
            "pr_tool_admitted": operator_status["pr_tool_admitted"],
            "external_approval_status": operator_status["external_approval_status"],
            "action_banner": action_banner,
            "rollback_required": operator_status["rollback_required"],
            "rollback_command_count": operator_status["rollback_command_count"],
            "command_preview_rendered": operator_status["command_preview_rendered"],
            "execution_performed": False,
            "receipt_hash": operator_status["receipt_hash"],
        },
        "capability_summary": capability_summary,
        "control_summary": {
            key: value
            for key, value in control_summary.items()
            if key != "capability_summary"
        },
        "source_ref": source_ref,
    }


def validate_operator_developer_workflow_status_read_model(
    *,
    read_model: Mapping[str, Any],
    schema_path: Path = DEFAULT_SCHEMA,
    read_model_path: Path = Path("<generated>"),
) -> OperatorDeveloperWorkflowStatusValidation:
    """Validate schema and no-effect semantics for a status read model."""

    schema = _load_json_object(schema_path)
    errors = [str(error) for error in _validate_schema_instance(schema, dict(read_model))]
    if read_model.get("projection_only") is not True:
        errors.append("projection_only_must_be_true")
    if read_model.get("external_effects_allowed") is not False:
        errors.append("external_effects_must_be_false")
    summary = read_model.get("summary", {})
    if not isinstance(summary, Mapping):
        errors.append("summary_must_be_object")
    elif summary.get("execution_performed") is not False:
        errors.append("execution_performed_must_be_false")
    capability_summary = read_model.get("capability_summary", {})
    if not isinstance(capability_summary, Mapping):
        errors.append("capability_summary_must_be_object")
    elif capability_summary.get("external_effects_allowed") is not False:
        errors.append("capability_external_effects_must_be_false")
    return OperatorDeveloperWorkflowStatusValidation(
        ok=not errors,
        errors=tuple(errors),
        read_model_path=_path_label(read_model_path),
        status=str(read_model.get("status") or ""),
        next_unlock=str(read_model.get("next_unlock") or ""),
    )


def write_operator_developer_workflow_status_read_model(read_model: Mapping[str, Any], output_path: Path) -> Path:
    """Write a deterministic compact status read model."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(read_model, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _developer_workflow_operator_status(receipt: Mapping[str, Any]) -> dict[str, Any]:
    external_handoff = _mapping(receipt.get("external_handoff"))
    approvals = _mapping(receipt.get("approvals"))
    external_approval = _mapping(approvals.get("external_pr_execution"))
    local_candidate = _mapping(receipt.get("local_pr_candidate"))
    rollback = _mapping(receipt.get("rollback"))
    sandbox_receipts = _mapping(receipt.get("sandbox_receipts"))
    source_refs = _mapping(receipt.get("source_refs"))
    rollback_commands = rollback.get("commands", ())
    if not isinstance(rollback_commands, list):
        rollback_commands = []
    next_evidence = receipt.get("next_evidence", ())
    if not isinstance(next_evidence, list):
        next_evidence = []
    normalized_next_evidence = [str(item) for item in next_evidence if str(item).strip()][:8]
    return {
        "workflow_run_id": str(receipt.get("workflow_run_id") or "developer_workflow_v1_foundation_run"),
        "solver_outcome": str(receipt.get("solver_outcome") or "AwaitingEvidence"),
        "readiness_status": str(receipt.get("readiness_status") or "awaiting_sandbox_receipts"),
        "ready_for_external_pr_execution": external_handoff.get("ready_for_external_pr_execution") is True,
        "external_approval_status": str(external_approval.get("status") or "pending"),
        "local_candidate_ready": local_candidate.get("candidate_ready") is True,
        "pr_tool_admitted": local_candidate.get("pr_tool_admitted") is True,
        "sandbox_receipts_completed": int(sandbox_receipts.get("completed_count", 0) or 0),
        "sandbox_receipts_required": int(sandbox_receipts.get("required_count", 0) or 0),
        "rollback_required": rollback.get("required") is True,
        "rollback_command_count": len([command for command in rollback_commands if str(command).strip()]),
        "command_preview_rendered": external_handoff.get("command_preview_rendered") is True,
        "next_evidence": normalized_next_evidence,
        "first_next_evidence": normalized_next_evidence[0] if normalized_next_evidence else "none",
        "source_refs": dict(source_refs),
        "receipt_hash": str(receipt.get("receipt_hash") or ""),
    }


def _developer_workflow_control_summary(operator_status: Mapping[str, Any]) -> dict[str, Any]:
    next_evidence = operator_status.get("next_evidence", ())
    if not isinstance(next_evidence, list):
        next_evidence = []
    normalized_next_evidence = [str(item) for item in next_evidence if str(item).strip()][:8]
    next_unlock = str(operator_status.get("first_next_evidence") or "")
    if not next_unlock:
        next_unlock = normalized_next_evidence[0] if normalized_next_evidence else "none"
    evidence_text = ", ".join(normalized_next_evidence) or "none"
    action_banner = _developer_workflow_operator_action_banner(
        external_ready=operator_status.get("ready_for_external_pr_execution") is True,
        external_approval_status=str(operator_status.get("external_approval_status") or "pending"),
        command_preview_rendered=operator_status.get("command_preview_rendered") is True,
        next_unlock=next_unlock,
        evidence_text=evidence_text,
    )
    capability_summary = _developer_workflow_capability_summary(operator_status)
    return {
        "contract_id": "operator_dashboard_control_summary.v1",
        "summary_id": "developer_workflow_control_summary.v1",
        "operator_message": action_banner,
        "action_banner": action_banner,
        "capability_id": capability_summary["capability_id"],
        "mode": capability_summary["mode"],
        "current_level": capability_summary["current_level"],
        "next_level": capability_summary["next_level"],
        "status": capability_summary["status"],
        "blocked_reason": capability_summary["blocked_reason"],
        "next_unlock": next_unlock,
        "next_evidence_count": capability_summary["next_evidence_count"],
        "external_effects_allowed": False,
        "rollback_required": capability_summary["rollback_required"],
        "capability_summary": capability_summary,
    }


def _developer_workflow_capability_summary(operator_status: Mapping[str, Any]) -> dict[str, Any]:
    next_evidence = operator_status.get("next_evidence", ())
    if not isinstance(next_evidence, list):
        next_evidence = []
    normalized_next_evidence = [str(item) for item in next_evidence if str(item).strip()][:8]
    local_candidate_ready = operator_status.get("local_candidate_ready") is True
    pr_tool_admitted = operator_status.get("pr_tool_admitted") is True
    external_ready = operator_status.get("ready_for_external_pr_execution") is True
    external_approval_status = str(operator_status.get("external_approval_status") or "pending")
    sandbox_complete = int(operator_status.get("sandbox_receipts_completed", 0) or 0) >= int(
        operator_status.get("sandbox_receipts_required", 0) or 0
    )
    if external_ready and external_approval_status == "approved":
        capability_status = "preflight_ready"
        blocked_reason = "dashboard execution disabled"
    elif external_approval_status != "approved" and local_candidate_ready and pr_tool_admitted:
        capability_status = "approval_required"
        blocked_reason = "external approval pending"
    elif not sandbox_complete:
        capability_status = "evidence_required"
        blocked_reason = "sandbox receipt evidence incomplete"
    else:
        capability_status = "prepare_only"
        blocked_reason = "local candidate or PR tool admission incomplete"
    allowed_actions = ["prepare diff", "validate evidence", "write sandbox files", "run tests"]
    if local_candidate_ready and pr_tool_admitted:
        allowed_actions.append("prepare PR candidate")
    return {
        "capability_id": "mullu_developer_workflow.v1",
        "current_level": "L4" if sandbox_complete else "L2",
        "next_level": "L5",
        "status": capability_status,
        "mode": "lab",
        "allowed_actions": allowed_actions,
        "blocked_actions": ["create PR", "push branch", "connector call", "merge", "deploy"],
        "blocked_reason": blocked_reason,
        "next_evidence": normalized_next_evidence,
        "next_evidence_count": len(normalized_next_evidence),
        "external_effects_allowed": False,
        "rollback_required": operator_status.get("rollback_required") is True,
    }


def _developer_workflow_operator_action_banner(
    *,
    external_ready: bool,
    external_approval_status: str,
    command_preview_rendered: bool,
    next_unlock: str,
    evidence_text: str,
) -> str:
    normalized_approval = external_approval_status or "pending"
    normalized_next_unlock = next_unlock or "none"
    normalized_evidence = evidence_text or "none"
    if external_ready and normalized_approval == "approved":
        return "PR execution remains disabled in this dashboard; use the approved external path only."
    if normalized_approval != "approved":
        return (
            f"Action needed before PR execution: provide {normalized_next_unlock}; "
            "external approval is pending."
        )
    if not command_preview_rendered:
        return "Action needed before PR execution: render command preview."
    return f"Action needed before PR execution: complete {normalized_evidence}."


def _developer_workflow_status_reason(readiness_status: str, next_evidence: str) -> str:
    if readiness_status == "awaiting_external_pr_approval":
        return "operator external PR approval missing"
    if readiness_status == "awaiting_operator_approval":
        return "local PR candidate approval missing"
    if readiness_status == "awaiting_sandbox_receipts":
        return "sandbox receipt evidence incomplete"
    if readiness_status == "ready_for_external_pr_execution":
        return "external PR execution evidence is prepared but not executed by this read model"
    return f"next evidence required: {next_evidence}"


def _developer_workflow_status_risk(readiness_status: str) -> str:
    if readiness_status in {"awaiting_external_pr_approval", "ready_for_external_pr_execution"}:
        return "external repository write"
    return "low, local lab only"


def _developer_workflow_status_action(readiness_status: str, next_evidence: str) -> str:
    if readiness_status == "awaiting_external_pr_approval":
        return "approve or defer external PR execution"
    if readiness_status == "awaiting_operator_approval":
        return "approve local PR candidate preparation"
    if readiness_status == "awaiting_sandbox_receipts":
        return "complete sandbox receipt bundle"
    if readiness_status == "ready_for_external_pr_execution":
        return "execute external PR commands only through explicit approved path"
    return f"provide {next_evidence}"


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
    """Parse compact Developer Workflow status read-model arguments."""

    parser = argparse.ArgumentParser(description="Build Developer Workflow status read model.")
    parser.add_argument("--receipt", default=str(DEFAULT_OPERATOR_RECEIPT))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for compact Developer Workflow status read-model building."""

    args = parse_args(argv)
    receipt_path = Path(args.receipt)
    schema_path = Path(args.schema)
    output_path = Path(args.output)
    try:
        receipt = _load_json_object(receipt_path)
        receipt_validation = validate_developer_workflow_operator_receipt(receipt=receipt, receipt_path=receipt_path)
        if not receipt_validation.ok:
            print(f"OPERATOR DEVELOPER WORKFLOW STATUS INVALID source_errors={list(receipt_validation.errors)}")
            return 2
        read_model = build_operator_developer_workflow_status_read_model(
            receipt=receipt,
            source_ref=_path_label(receipt_path),
        )
        written_path = write_operator_developer_workflow_status_read_model(read_model, output_path)
        validation = validate_operator_developer_workflow_status_read_model(
            read_model=read_model,
            schema_path=schema_path,
            read_model_path=written_path,
        )
    except ValueError as exc:
        print(f"OPERATOR DEVELOPER WORKFLOW STATUS INVALID error={exc}")
        return 2
    if not validation.ok:
        print(f"OPERATOR DEVELOPER WORKFLOW STATUS INVALID errors={list(validation.errors)}")
        return 2
    if args.json:
        print(json.dumps(read_model, indent=2, sort_keys=True))
    else:
        print(f"OPERATOR DEVELOPER WORKFLOW STATUS BUILT path={written_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
