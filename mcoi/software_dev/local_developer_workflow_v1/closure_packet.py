"""Build Local Developer Workflow v1 closure packets.

Purpose: summarize Local Developer Workflow v1 preview artifacts into one
operator handoff packet with current gate, missing evidence, next proof step,
rollback boundary, approval boundary, and command preview references.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: Local Developer Workflow v1 artifacts and optional operator
workflow dashboard projection.
Invariants:
  - Closure packets are projection-only and never execution authority.
  - File write, test execution, branch push, PR creation, merge, deployment,
    connector calls, external writes, and live execution remain disabled.
  - Packet hashes cover every causal input summarized by the packet.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from software_dev.local_developer_workflow_v1.runner import (
    ARTIFACT_FILENAMES,
    FORBIDDEN_EFFECTS,
    WORKFLOW_ID,
    validate_local_developer_workflow_v1_artifacts,
)


SCHEMA_VERSION = 1
CLOSURE_PACKET_ID = "local_developer_workflow_v1.closure_packet.foundation.v1"
CLOSURE_PACKET_FILENAME = "local_developer_workflow_v1_closure_packet.json"
VALIDATOR_COMMANDS = (
    "python scripts/validate_local_developer_workflow_closure_packet.py --strict",
    "python -m pytest tests/test_local_developer_workflow_v1.py -q",
)


class LocalDeveloperWorkflowClosurePacketError(ValueError):
    """Raised when a closure packet cannot be built or validated."""


@dataclass(frozen=True, slots=True)
class LocalDeveloperWorkflowClosurePacketValidation:
    """Validation report for a Local Developer Workflow closure packet."""

    ok: bool
    errors: tuple[str, ...]
    packet_id: str
    status: str
    next_required_proof_step: str
    packet_path: str

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-ready validation report."""

        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def build_local_developer_workflow_closure_packet(
    *,
    artifacts: Mapping[str, Mapping[str, Any]],
    artifact_paths: Mapping[str, Path] | None = None,
    operator_dashboard: Mapping[str, Any] | None = None,
    operator_dashboard_source_ref: str = "absent",
) -> dict[str, Any]:
    """Return one projection-only closure packet for workflow handoff.

    Input contract: canonical Local Developer Workflow v1 artifacts and
    optional dashboard read model.
    Output contract: JSON-serializable closure packet with hash.
    Error contract: raises LocalDeveloperWorkflowClosurePacketError if source
    artifacts are invalid or required handoff references are absent.
    """

    validation = validate_local_developer_workflow_v1_artifacts(
        artifacts=artifacts,
        artifact_paths=artifact_paths,
    )
    if not validation.ok:
        raise LocalDeveloperWorkflowClosurePacketError(
            f"local_developer_workflow_artifacts_invalid:{list(validation.errors)}"
        )

    _validate_dashboard_boundary(operator_dashboard)
    receipt = _mapping(artifacts.get("receipt"))
    approval_request = _mapping(artifacts.get("approval_request"))
    pr_command_preview = _mapping(artifacts.get("pr_command_preview"))
    diff_proposal = _mapping(artifacts.get("diff_proposal"))
    test_plan = _mapping(artifacts.get("test_plan"))
    dashboard_row = _dashboard_row(operator_dashboard)
    current_gate = _current_gate(approval_request=approval_request, dashboard_row=dashboard_row)
    missing_evidence_refs = _missing_evidence_refs(
        receipt=receipt,
        approval_request=approval_request,
        pr_command_preview=pr_command_preview,
        dashboard_row=dashboard_row,
    )
    next_required_proof_step = _next_required_proof_step(
        approval_request=approval_request,
        missing_evidence_refs=missing_evidence_refs,
    )
    packet = {
        "schema_version": SCHEMA_VERSION,
        "packet_id": CLOSURE_PACKET_ID,
        "workflow_id": WORKFLOW_ID,
        "workflow_run_id": validation.workflow_run_id,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "projection_only": True,
        "packet_is_not_execution_authority": True,
        "execution_performed": False,
        "external_effects_allowed": False,
        "live_execution_enabled": False,
        "current_gate": current_gate,
        "missing_evidence_refs": missing_evidence_refs,
        "next_required_proof_step": next_required_proof_step,
        "approval_boundary": _approval_boundary(approval_request),
        "rollback": _rollback(diff_proposal),
        "receipts": _receipts(receipt, artifact_paths),
        "test_plan": _test_plan_summary(test_plan),
        "command_preview": _command_preview(pr_command_preview),
        "operator_dashboard": {
            "source_ref": operator_dashboard_source_ref,
            "linked": operator_dashboard is not None,
            "projection_only": True,
            "execution_performed": False,
        },
        "blocked_effects": list(FORBIDDEN_EFFECTS),
        "effect_boundary": dict(FORBIDDEN_EFFECTS),
        "validators": list(VALIDATOR_COMMANDS),
        "source_refs": _source_refs(artifacts, artifact_paths),
        "causal_trace": [
            "validated Local Developer Workflow v1 preview artifacts",
            "summarized current approval gate and missing evidence refs",
            "bound rollback and command previews as non-executed artifacts",
            "emitted closure packet with no live execution authority",
        ],
        "packet_hash": "",
    }
    packet["packet_hash"] = _digest(packet)
    return packet


def write_local_developer_workflow_closure_packet(packet: Mapping[str, Any], output_path: Path) -> Path:
    """Write a closure packet to a deterministic JSON file."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(dict(packet), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def validate_local_developer_workflow_closure_packet(
    *,
    packet: Mapping[str, Any],
    artifacts: Mapping[str, Mapping[str, Any]],
    artifact_paths: Mapping[str, Path] | None = None,
    packet_path: Path = Path("<generated>"),
) -> LocalDeveloperWorkflowClosurePacketValidation:
    """Validate closure packet topology, no-effect claims, and hash."""

    errors: list[str] = []
    artifact_validation = validate_local_developer_workflow_v1_artifacts(
        artifacts=artifacts,
        artifact_paths=artifact_paths,
    )
    if not artifact_validation.ok:
        errors.extend(f"source_artifacts:{error}" for error in artifact_validation.errors)
    if packet.get("packet_id") != CLOSURE_PACKET_ID:
        errors.append("packet_id_mismatch")
    if packet.get("workflow_id") != WORKFLOW_ID:
        errors.append("workflow_id_mismatch")
    if packet.get("workflow_run_id") != artifact_validation.workflow_run_id:
        errors.append("workflow_run_id_mismatch")
    for field_name in ("projection_only", "packet_is_not_execution_authority"):
        if packet.get(field_name) is not True:
            errors.append(f"{field_name}_must_be_true")
    for field_name in ("execution_performed", "external_effects_allowed", "live_execution_enabled"):
        if packet.get(field_name) is not False:
            errors.append(f"{field_name}_must_be_false")
    boundary = _mapping(packet.get("effect_boundary"))
    for effect_name, expected in FORBIDDEN_EFFECTS.items():
        if boundary.get(effect_name) is not expected:
            errors.append(f"effect_boundary_mismatch:{effect_name}")
    blocked_effects = packet.get("blocked_effects")
    if not isinstance(blocked_effects, list):
        errors.append("blocked_effects_must_be_list")
    else:
        for effect_name in FORBIDDEN_EFFECTS:
            if effect_name not in blocked_effects:
                errors.append(f"blocked_effect_missing:{effect_name}")
    if not _mapping(packet.get("current_gate")).get("gate_id"):
        errors.append("current_gate_missing_gate_id")
    if not _list_of_text(packet.get("missing_evidence_refs")):
        errors.append("missing_evidence_refs_must_be_non_empty_text_list")
    if not str(packet.get("next_required_proof_step") or "").strip():
        errors.append("next_required_proof_step_required")
    approval = _mapping(packet.get("approval_boundary"))
    if approval.get("approval_performed") is not False:
        errors.append("approval_performed_must_be_false")
    if approval.get("approval_does_not_authorize_execution") is not True:
        errors.append("approval_must_not_authorize_execution")
    rollback = _mapping(packet.get("rollback"))
    if rollback.get("rollback_executed") is not False:
        errors.append("rollback_executed_must_be_false")
    command_preview = packet.get("command_preview")
    if not isinstance(command_preview, list) or not command_preview:
        errors.append("command_preview_must_be_non_empty_list")
    else:
        for index, command in enumerate(command_preview):
            if not isinstance(command, Mapping):
                errors.append(f"command_preview[{index}]_must_be_object")
            elif command.get("execution_allowed") is not False:
                errors.append(f"command_preview[{index}]_execution_allowed_must_be_false")
    expected_hash = dict(packet)
    expected_hash["packet_hash"] = ""
    if packet.get("packet_hash") != _digest(expected_hash):
        errors.append("packet_hash_mismatch")
    return LocalDeveloperWorkflowClosurePacketValidation(
        ok=not errors,
        errors=tuple(errors),
        packet_id=str(packet.get("packet_id") or ""),
        status=str(packet.get("status") or ""),
        next_required_proof_step=str(packet.get("next_required_proof_step") or ""),
        packet_path=_path_label(packet_path),
    )


def _current_gate(
    *,
    approval_request: Mapping[str, Any],
    dashboard_row: Mapping[str, Any],
) -> dict[str, Any]:
    dashboard_gate = _mapping(dashboard_row.get("current_gate"))
    if dashboard_gate.get("stage_id"):
        gate_id = str(dashboard_gate.get("stage_id"))
        gate_type = str(dashboard_gate.get("stage_type") or "approval_gate")
        gate_status = str(dashboard_gate.get("status") or "pending")
    else:
        gate_id = str(approval_request.get("approval_request_id") or "approval_request_missing")
        gate_type = "approval_gate"
        gate_status = str(approval_request.get("approval_status") or "pending")
    return {
        "gate_id": gate_id,
        "gate_type": gate_type,
        "status": gate_status,
        "projection_only": True,
        "execution_performed": False,
    }


def _missing_evidence_refs(
    *,
    receipt: Mapping[str, Any],
    approval_request: Mapping[str, Any],
    pr_command_preview: Mapping[str, Any],
    dashboard_row: Mapping[str, Any],
) -> list[str]:
    refs: list[str] = []
    dashboard_missing = dashboard_row.get("missing_evidence")
    if isinstance(dashboard_missing, list):
        refs.extend(str(item) for item in dashboard_missing if str(item).strip())
    if approval_request.get("approval_status") != "approved":
        refs.append(str(approval_request.get("approval_request_id") or "approval_request_ref"))
    if pr_command_preview.get("execution_performed") is False:
        refs.append(str(pr_command_preview.get("preview_id") or "pr_command_preview_ref"))
    receipt_refs = _mapping(receipt.get("source_refs"))
    for key in ("diff_proposal", "test_plan", "approval_request", "pr_command_preview"):
        value = str(receipt_refs.get(key) or "").strip()
        if value:
            refs.append(value)
    return list(dict.fromkeys(refs))


def _next_required_proof_step(
    *,
    approval_request: Mapping[str, Any],
    missing_evidence_refs: list[str],
) -> str:
    if approval_request.get("approval_status") != "approved":
        return (
            "collect review-only operator decision for "
            f"{approval_request.get('approval_request_id')}; execution remains blocked"
        )
    if missing_evidence_refs:
        return f"collect missing evidence refs: {', '.join(missing_evidence_refs[:3])}"
    return "retain packet as preview closure evidence; request separate authority before execution"


def _approval_boundary(approval_request: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "approval_request_id": str(approval_request.get("approval_request_id") or ""),
        "approval_required": approval_request.get("approval_required") is True,
        "approval_status": str(approval_request.get("approval_status") or "pending"),
        "approval_performed": False,
        "approval_does_not_authorize_execution": True,
        "allowed_decisions": list(approval_request.get("allowed_decisions") or ()),
        "blocked_after_approval": list(approval_request.get("effects_still_forbidden_after_approval") or ()),
    }


def _rollback(diff_proposal: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "required": True,
        "strategy": str(diff_proposal.get("rollback_plan") or "discard preview artifacts; no source mutation occurred"),
        "rollback_executed": False,
        "execution_performed": False,
    }


def _receipts(receipt: Mapping[str, Any], artifact_paths: Mapping[str, Path] | None) -> dict[str, Any]:
    return {
        "receipt_id": str(receipt.get("receipt_id") or ""),
        "receipt_hash": str(receipt.get("receipt_hash") or ""),
        "status": str(receipt.get("status") or ""),
        "artifact_paths": {
            key: _path_label(path)
            for key, path in (artifact_paths or {}).items()
        },
        "execution_performed": False,
    }


def _test_plan_summary(test_plan: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "test_plan_id": str(test_plan.get("test_plan_id") or ""),
        "tests_executed": test_plan.get("tests_executed") is True,
        "commands": list(test_plan.get("commands") or ()),
        "test_plan_is_not_execution_authority": test_plan.get("test_plan_is_not_execution_authority") is True,
    }


def _command_preview(pr_command_preview: Mapping[str, Any]) -> list[dict[str, Any]]:
    commands = pr_command_preview.get("command_preview")
    if not isinstance(commands, list):
        return []
    return [
        {
            "command_id": str(command.get("command_id") or ""),
            "effect": str(command.get("effect") or ""),
            "command": str(command.get("command") or ""),
            "execution_allowed": False,
        }
        for command in commands
        if isinstance(command, Mapping)
    ]


def _source_refs(
    artifacts: Mapping[str, Mapping[str, Any]],
    artifact_paths: Mapping[str, Path] | None,
) -> dict[str, str]:
    refs: dict[str, str] = {}
    for artifact_name in ARTIFACT_FILENAMES:
        artifact = _mapping(artifacts.get(artifact_name))
        refs[artifact_name] = str(
            artifact.get("artifact_id")
            or artifact.get("diff_proposal_id")
            or artifact.get("test_plan_id")
            or artifact.get("approval_request_id")
            or artifact.get("preview_id")
            or artifact.get("receipt_id")
            or artifact_name
        )
    for artifact_name, path in (artifact_paths or {}).items():
        refs[f"{artifact_name}_path"] = _path_label(path)
    return refs


def _dashboard_row(operator_dashboard: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if not isinstance(operator_dashboard, Mapping):
        return {}
    rows = operator_dashboard.get("rows")
    if not isinstance(rows, list) or not rows or not isinstance(rows[0], Mapping):
        return {}
    return rows[0]


def _validate_dashboard_boundary(operator_dashboard: Mapping[str, Any] | None) -> None:
    if operator_dashboard is None:
        return
    if not isinstance(operator_dashboard, Mapping):
        raise LocalDeveloperWorkflowClosurePacketError("operator_dashboard_must_be_object")
    if operator_dashboard.get("projection_only") is not True:
        raise LocalDeveloperWorkflowClosurePacketError("operator_dashboard_projection_only_required")
    if operator_dashboard.get("execution_performed") is not False:
        raise LocalDeveloperWorkflowClosurePacketError("operator_dashboard_execution_must_be_false")
    if operator_dashboard.get("external_effects_allowed") is not False:
        raise LocalDeveloperWorkflowClosurePacketError("operator_dashboard_external_effects_must_be_false")
    rows = operator_dashboard.get("rows")
    if rows is not None and (not isinstance(rows, list) or any(not isinstance(row, Mapping) for row in rows)):
        raise LocalDeveloperWorkflowClosurePacketError("operator_dashboard_rows_must_be_objects")


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _list_of_text(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _digest(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(dict(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(Path.cwd().resolve(strict=False)).as_posix()
    except ValueError:
        return str(path)
