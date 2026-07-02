"""Build Local Developer Workflow v1 PR command preview packets.

Purpose: summarize the Local Developer Workflow v1 PR command preview into a
schema-backed local review packet before any branch push or pull-request
creation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: Local Developer Workflow v1 preview artifacts and closure
packet references.
Invariants:
  - Command text is review-only and never execution authority.
  - Every preview command has execution_allowed=false.
  - Branch push, pull-request creation, merge, deployment, connector calls,
    external writes, and live execution remain blocked.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from software_dev.local_developer_workflow_v1.closure_packet import (
    CLOSURE_PACKET_ID,
    validate_local_developer_workflow_closure_packet,
)
from software_dev.local_developer_workflow_v1.runner import (
    FORBIDDEN_EFFECTS,
    WORKFLOW_ID,
    validate_local_developer_workflow_v1_artifacts,
)


SCHEMA_VERSION = 1
COMMAND_PREVIEW_PACKET_ID = "local_developer_workflow_v1.pr_command_preview_packet.foundation.v1"
COMMAND_PREVIEW_PACKET_FILENAME = "local_developer_workflow_v1_pr_command_preview_packet.json"
VALIDATOR_COMMANDS = (
    "python scripts/validate_local_developer_workflow_pr_command_preview_packet.py --strict",
    "python -m pytest tests/test_local_developer_workflow_v1.py -q",
)


class LocalDeveloperWorkflowCommandPreviewPacketError(ValueError):
    """Raised when a command preview packet cannot be built or validated."""


@dataclass(frozen=True, slots=True)
class LocalDeveloperWorkflowCommandPreviewPacketValidation:
    """Validation report for a Local Developer Workflow command preview packet."""

    ok: bool
    errors: tuple[str, ...]
    packet_id: str
    status: str
    command_count: int
    packet_path: str

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-ready validation report."""

        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def build_local_developer_workflow_pr_command_preview_packet(
    *,
    artifacts: Mapping[str, Mapping[str, Any]],
    closure_packet: Mapping[str, Any] | None = None,
    artifact_paths: Mapping[str, Path] | None = None,
    closure_packet_path: Path = Path("<generated>"),
) -> dict[str, Any]:
    """Return a projection-only local PR command preview packet.

    Input contract: canonical Local Developer Workflow v1 artifacts plus an
    optional validated closure packet.
    Output contract: JSON-serializable packet with a deterministic hash.
    Error contract: raises LocalDeveloperWorkflowCommandPreviewPacketError when
    source artifacts or closure packet references are invalid.
    """

    artifact_validation = validate_local_developer_workflow_v1_artifacts(
        artifacts=artifacts,
        artifact_paths=artifact_paths,
    )
    if not artifact_validation.ok:
        raise LocalDeveloperWorkflowCommandPreviewPacketError(
            f"local_developer_workflow_artifacts_invalid:{list(artifact_validation.errors)}"
        )
    if closure_packet is not None:
        closure_validation = validate_local_developer_workflow_closure_packet(
            packet=closure_packet,
            artifacts=artifacts,
            artifact_paths=artifact_paths,
            packet_path=closure_packet_path,
        )
        if not closure_validation.ok:
            raise LocalDeveloperWorkflowCommandPreviewPacketError(
                f"closure_packet_invalid:{list(closure_validation.errors)}"
            )

    pr_command_preview = _mapping(artifacts.get("pr_command_preview"))
    approval_request = _mapping(artifacts.get("approval_request"))
    receipt = _mapping(artifacts.get("receipt"))
    commands = _review_commands(pr_command_preview)
    packet = {
        "schema_version": SCHEMA_VERSION,
        "packet_id": COMMAND_PREVIEW_PACKET_ID,
        "workflow_id": WORKFLOW_ID,
        "workflow_run_id": artifact_validation.workflow_run_id,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "projection_only": True,
        "packet_is_not_execution_authority": True,
        "command_preview_is_review_only": True,
        "execution_performed": False,
        "external_effects_allowed": False,
        "live_execution_enabled": False,
        "commands_rendered": bool(commands),
        "command_count": len(commands),
        "approval": _approval_summary(approval_request),
        "command_preview": commands,
        "required_before_execution": [
            "operator external PR execution approval witness",
            "branch-write authority witness",
            "pull-request creation admission witness",
            "rollback effect witness",
            "UAO execution admission receipt",
        ],
        "blocked_effects": [
            "branch_push",
            "pull_request_create",
            "merge",
            "deploy",
            "connector_call",
            "external_write",
            "live_execution",
        ],
        "effect_boundary": dict(FORBIDDEN_EFFECTS),
        "source_refs": _source_refs(
            pr_command_preview=pr_command_preview,
            approval_request=approval_request,
            receipt=receipt,
            closure_packet=closure_packet,
            artifact_paths=artifact_paths,
            closure_packet_path=closure_packet_path,
        ),
        "validators": list(VALIDATOR_COMMANDS),
        "causal_trace": [
            "validated Local Developer Workflow v1 preview artifacts",
            "copied blocked PR command preview for local operator review",
            "bound approval and closure packet refs without collecting approval",
            "emitted command preview packet with execution blocked",
        ],
        "packet_hash": "",
    }
    packet["packet_hash"] = _digest(packet)
    return packet


def write_local_developer_workflow_pr_command_preview_packet(
    packet: Mapping[str, Any],
    output_path: Path,
) -> Path:
    """Write a deterministic command preview packet."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(dict(packet), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def validate_local_developer_workflow_pr_command_preview_packet(
    *,
    packet: Mapping[str, Any],
    artifacts: Mapping[str, Mapping[str, Any]],
    closure_packet: Mapping[str, Any] | None = None,
    artifact_paths: Mapping[str, Path] | None = None,
    packet_path: Path = Path("<generated>"),
    closure_packet_path: Path = Path("<generated>"),
) -> LocalDeveloperWorkflowCommandPreviewPacketValidation:
    """Validate local PR command preview packet no-effect semantics."""

    errors: list[str] = []
    artifact_validation = validate_local_developer_workflow_v1_artifacts(
        artifacts=artifacts,
        artifact_paths=artifact_paths,
    )
    if not artifact_validation.ok:
        errors.extend(f"source_artifacts:{error}" for error in artifact_validation.errors)
    if closure_packet is not None:
        closure_validation = validate_local_developer_workflow_closure_packet(
            packet=closure_packet,
            artifacts=artifacts,
            artifact_paths=artifact_paths,
            packet_path=closure_packet_path,
        )
        if not closure_validation.ok:
            errors.extend(f"closure_packet:{error}" for error in closure_validation.errors)
    if packet.get("packet_id") != COMMAND_PREVIEW_PACKET_ID:
        errors.append("packet_id_mismatch")
    if packet.get("workflow_id") != WORKFLOW_ID:
        errors.append("workflow_id_mismatch")
    if packet.get("workflow_run_id") != artifact_validation.workflow_run_id:
        errors.append("workflow_run_id_mismatch")
    for field_name in ("projection_only", "packet_is_not_execution_authority", "command_preview_is_review_only"):
        if packet.get(field_name) is not True:
            errors.append(f"{field_name}_must_be_true")
    for field_name in ("execution_performed", "external_effects_allowed", "live_execution_enabled"):
        if packet.get(field_name) is not False:
            errors.append(f"{field_name}_must_be_false")
    boundary = _mapping(packet.get("effect_boundary"))
    for effect_name, expected in FORBIDDEN_EFFECTS.items():
        if boundary.get(effect_name) is not expected:
            errors.append(f"effect_boundary_mismatch:{effect_name}")
    commands = packet.get("command_preview")
    if not isinstance(commands, list) or len(commands) != 2:
        errors.append("command_preview_must_render_two_review_commands")
    else:
        for index, command in enumerate(commands):
            if not isinstance(command, Mapping):
                errors.append(f"command_preview[{index}]_must_be_object")
                continue
            if command.get("execution_allowed") is not False:
                errors.append(f"command_preview[{index}]_execution_allowed_must_be_false")
            if command.get("review_only") is not True:
                errors.append(f"command_preview[{index}]_review_only_must_be_true")
    if packet.get("commands_rendered") is not True:
        errors.append("commands_rendered_must_be_true_for_local_review")
    if packet.get("command_count") != 2:
        errors.append("command_count_must_be_two")
    approval = _mapping(packet.get("approval"))
    if approval.get("approval_performed") is not False:
        errors.append("approval_performed_must_be_false")
    if approval.get("approval_does_not_authorize_execution") is not True:
        errors.append("approval_does_not_authorize_execution_must_be_true")
    source_refs = _mapping(packet.get("source_refs"))
    if closure_packet is not None and source_refs.get("closure_packet_id") != CLOSURE_PACKET_ID:
        errors.append("closure_packet_ref_mismatch")
    expected_hash = dict(packet)
    expected_hash["packet_hash"] = ""
    if packet.get("packet_hash") != _digest(expected_hash):
        errors.append("packet_hash_mismatch")
    return LocalDeveloperWorkflowCommandPreviewPacketValidation(
        ok=not errors,
        errors=tuple(errors),
        packet_id=str(packet.get("packet_id") or ""),
        status=str(packet.get("status") or ""),
        command_count=int(packet.get("command_count") or 0),
        packet_path=_path_label(packet_path),
    )


def _review_commands(pr_command_preview: Mapping[str, Any]) -> list[dict[str, Any]]:
    commands = pr_command_preview.get("command_preview")
    if not isinstance(commands, list):
        return []
    return [
        {
            "command_id": str(command.get("command_id") or ""),
            "effect": str(command.get("effect") or ""),
            "command": str(command.get("command") or ""),
            "review_only": True,
            "execution_allowed": False,
        }
        for command in commands
        if isinstance(command, Mapping)
    ]


def _approval_summary(approval_request: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "approval_request_id": str(approval_request.get("approval_request_id") or ""),
        "approval_required": approval_request.get("approval_required") is True,
        "approval_status": str(approval_request.get("approval_status") or "pending"),
        "approval_performed": False,
        "approval_does_not_authorize_execution": True,
        "allowed_decisions": list(approval_request.get("allowed_decisions") or ()),
    }


def _source_refs(
    *,
    pr_command_preview: Mapping[str, Any],
    approval_request: Mapping[str, Any],
    receipt: Mapping[str, Any],
    closure_packet: Mapping[str, Any] | None,
    artifact_paths: Mapping[str, Path] | None,
    closure_packet_path: Path,
) -> dict[str, str]:
    refs = {
        "pr_command_preview_id": str(pr_command_preview.get("preview_id") or ""),
        "approval_request_id": str(approval_request.get("approval_request_id") or ""),
        "workflow_receipt_id": str(receipt.get("receipt_id") or ""),
    }
    if closure_packet is not None:
        refs["closure_packet_id"] = str(closure_packet.get("packet_id") or "")
        refs["closure_packet_path"] = _path_label(closure_packet_path)
    for artifact_name, path in (artifact_paths or {}).items():
        refs[f"{artifact_name}_path"] = _path_label(path)
    return refs


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


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
