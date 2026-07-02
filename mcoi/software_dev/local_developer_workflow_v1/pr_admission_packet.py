"""Build Local Developer Workflow v1 PR admission packets.

Purpose: bind Local Developer Workflow v1 command review evidence to a
projection-only branch-write and pull-request creation admission decision.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: Local Developer Workflow v1 artifacts, closure packet, and local
command preview packet.
Invariants:
  - Admission packets do not grant branch-write or PR-creation authority.
  - Local command review evidence can be present while external execution
    remains blocked.
  - Branch push, pull-request creation, merge, deployment, connector calls,
    external writes, and live execution remain disabled.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from software_dev.local_developer_workflow_v1.closure_packet import (
    validate_local_developer_workflow_closure_packet,
)
from software_dev.local_developer_workflow_v1.command_preview_packet import (
    validate_local_developer_workflow_pr_command_preview_packet,
)
from software_dev.local_developer_workflow_v1.runner import (
    FORBIDDEN_EFFECTS,
    WORKFLOW_ID,
    validate_local_developer_workflow_v1_artifacts,
)


SCHEMA_VERSION = 1
PR_ADMISSION_PACKET_ID = "local_developer_workflow_v1.pr_admission_packet.foundation.v1"
PR_ADMISSION_PACKET_FILENAME = "local_developer_workflow_v1_pr_admission_packet.json"
VALIDATOR_COMMANDS = (
    "python scripts/validate_local_developer_workflow_pr_admission_packet.py --strict",
    "python -m pytest tests/test_local_developer_workflow_v1.py -q",
)


class LocalDeveloperWorkflowPrAdmissionPacketError(ValueError):
    """Raised when a PR admission packet cannot be built or validated."""


@dataclass(frozen=True, slots=True)
class LocalDeveloperWorkflowPrAdmissionPacketValidation:
    """Validation report for a Local Developer Workflow PR admission packet."""

    ok: bool
    errors: tuple[str, ...]
    packet_id: str
    admission_decision: str
    packet_path: str

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-ready validation report."""

        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def build_local_developer_workflow_pr_admission_packet(
    *,
    artifacts: Mapping[str, Mapping[str, Any]],
    command_preview_packet: Mapping[str, Any],
    closure_packet: Mapping[str, Any] | None = None,
    artifact_paths: Mapping[str, Path] | None = None,
    command_preview_packet_path: Path = Path("<generated>"),
    closure_packet_path: Path = Path("<generated>"),
) -> dict[str, Any]:
    """Return a projection-only branch-write and PR-creation admission packet."""

    artifact_validation = validate_local_developer_workflow_v1_artifacts(
        artifacts=artifacts,
        artifact_paths=artifact_paths,
    )
    if not artifact_validation.ok:
        raise LocalDeveloperWorkflowPrAdmissionPacketError(
            f"local_developer_workflow_artifacts_invalid:{list(artifact_validation.errors)}"
        )
    command_validation = validate_local_developer_workflow_pr_command_preview_packet(
        packet=command_preview_packet,
        artifacts=artifacts,
        closure_packet=closure_packet,
        artifact_paths=artifact_paths,
        packet_path=command_preview_packet_path,
        closure_packet_path=closure_packet_path,
    )
    if not command_validation.ok:
        raise LocalDeveloperWorkflowPrAdmissionPacketError(
            f"command_preview_packet_invalid:{list(command_validation.errors)}"
        )
    if closure_packet is not None:
        closure_validation = validate_local_developer_workflow_closure_packet(
            packet=closure_packet,
            artifacts=artifacts,
            artifact_paths=artifact_paths,
            packet_path=closure_packet_path,
        )
        if not closure_validation.ok:
            raise LocalDeveloperWorkflowPrAdmissionPacketError(
                f"closure_packet_invalid:{list(closure_validation.errors)}"
            )

    workflow_pr_preview = _mapping(artifacts.get("pr_command_preview"))
    packet = {
        "schema_version": SCHEMA_VERSION,
        "packet_id": PR_ADMISSION_PACKET_ID,
        "workflow_id": WORKFLOW_ID,
        "workflow_run_id": artifact_validation.workflow_run_id,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "projection_only": True,
        "packet_is_not_execution_authority": True,
        "local_command_review_evidence_present": True,
        "admission_decision": "blocked_waiting_external_execution_approval",
        "execution_performed": False,
        "external_effects_allowed": False,
        "branch_write_allowed": False,
        "pr_creation_allowed": False,
        "merge_allowed": False,
        "live_execution_enabled": False,
        "candidate": {
            "candidate_branch": str(workflow_pr_preview.get("candidate_branch") or ""),
            "target_branch": str(workflow_pr_preview.get("target_branch") or ""),
            "approval_request_id": str(workflow_pr_preview.get("approval_request_id") or ""),
            "command_preview_packet_id": str(command_preview_packet.get("packet_id") or ""),
            "command_count": int(command_preview_packet.get("command_count") or 0),
        },
        "required_before_execution": [
            "external PR execution approval witness",
            "branch-write authority witness",
            "pull-request creation admission witness",
            "rollback effect witness",
            "UAO execution admission receipt",
            "post-execution effect reconciliation witness",
        ],
        "blocked_effects": [
            "branch_write",
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
            command_preview_packet=command_preview_packet,
            command_preview_packet_path=command_preview_packet_path,
            closure_packet=closure_packet,
            closure_packet_path=closure_packet_path,
            artifact_paths=artifact_paths,
        ),
        "validators": list(VALIDATOR_COMMANDS),
        "causal_trace": [
            "validated Local Developer Workflow v1 preview artifacts",
            "validated local command preview packet",
            "admitted local review evidence only",
            "blocked branch-write and pull-request creation pending external authority proofs",
        ],
        "packet_hash": "",
    }
    packet["packet_hash"] = _digest(packet)
    return packet


def write_local_developer_workflow_pr_admission_packet(packet: Mapping[str, Any], output_path: Path) -> Path:
    """Write a deterministic PR admission packet."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(dict(packet), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def validate_local_developer_workflow_pr_admission_packet(
    *,
    packet: Mapping[str, Any],
    artifacts: Mapping[str, Mapping[str, Any]],
    command_preview_packet: Mapping[str, Any],
    closure_packet: Mapping[str, Any] | None = None,
    artifact_paths: Mapping[str, Path] | None = None,
    packet_path: Path = Path("<generated>"),
    command_preview_packet_path: Path = Path("<generated>"),
    closure_packet_path: Path = Path("<generated>"),
) -> LocalDeveloperWorkflowPrAdmissionPacketValidation:
    """Validate PR admission packet no-effect semantics."""

    errors: list[str] = []
    artifact_validation = validate_local_developer_workflow_v1_artifacts(
        artifacts=artifacts,
        artifact_paths=artifact_paths,
    )
    if not artifact_validation.ok:
        errors.extend(f"source_artifacts:{error}" for error in artifact_validation.errors)
    command_validation = validate_local_developer_workflow_pr_command_preview_packet(
        packet=command_preview_packet,
        artifacts=artifacts,
        closure_packet=closure_packet,
        artifact_paths=artifact_paths,
        packet_path=command_preview_packet_path,
        closure_packet_path=closure_packet_path,
    )
    if not command_validation.ok:
        errors.extend(f"command_preview_packet:{error}" for error in command_validation.errors)
    if packet.get("packet_id") != PR_ADMISSION_PACKET_ID:
        errors.append("packet_id_mismatch")
    if packet.get("workflow_id") != WORKFLOW_ID:
        errors.append("workflow_id_mismatch")
    if packet.get("workflow_run_id") != artifact_validation.workflow_run_id:
        errors.append("workflow_run_id_mismatch")
    for field_name in ("projection_only", "packet_is_not_execution_authority", "local_command_review_evidence_present"):
        if packet.get(field_name) is not True:
            errors.append(f"{field_name}_must_be_true")
    for field_name in (
        "execution_performed",
        "external_effects_allowed",
        "branch_write_allowed",
        "pr_creation_allowed",
        "merge_allowed",
        "live_execution_enabled",
    ):
        if packet.get(field_name) is not False:
            errors.append(f"{field_name}_must_be_false")
    if packet.get("admission_decision") != "blocked_waiting_external_execution_approval":
        errors.append("admission_decision_must_block_external_execution")
    boundary = _mapping(packet.get("effect_boundary"))
    for effect_name, expected in FORBIDDEN_EFFECTS.items():
        if boundary.get(effect_name) is not expected:
            errors.append(f"effect_boundary_mismatch:{effect_name}")
    candidate = _mapping(packet.get("candidate"))
    if not candidate.get("candidate_branch"):
        errors.append("candidate_branch_required")
    if candidate.get("command_preview_packet_id") != command_preview_packet.get("packet_id"):
        errors.append("command_preview_packet_ref_mismatch")
    if candidate.get("command_count") != command_preview_packet.get("command_count"):
        errors.append("command_count_mismatch")
    blocked_effects = tuple(str(item) for item in packet.get("blocked_effects", ()) if str(item).strip())
    for expected_effect in ("branch_write", "branch_push", "pull_request_create", "external_write"):
        if expected_effect not in blocked_effects:
            errors.append(f"blocked_effect_missing:{expected_effect}")
    expected_hash = dict(packet)
    expected_hash["packet_hash"] = ""
    if packet.get("packet_hash") != _digest(expected_hash):
        errors.append("packet_hash_mismatch")
    return LocalDeveloperWorkflowPrAdmissionPacketValidation(
        ok=not errors,
        errors=tuple(errors),
        packet_id=str(packet.get("packet_id") or ""),
        admission_decision=str(packet.get("admission_decision") or ""),
        packet_path=_path_label(packet_path),
    )


def _source_refs(
    *,
    command_preview_packet: Mapping[str, Any],
    command_preview_packet_path: Path,
    closure_packet: Mapping[str, Any] | None,
    closure_packet_path: Path,
    artifact_paths: Mapping[str, Path] | None,
) -> dict[str, str]:
    refs = {
        "command_preview_packet_id": str(command_preview_packet.get("packet_id") or ""),
        "command_preview_packet_path": _path_label(command_preview_packet_path),
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
