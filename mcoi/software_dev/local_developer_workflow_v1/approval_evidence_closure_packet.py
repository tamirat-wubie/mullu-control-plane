"""Build Local Developer Workflow v1 approval evidence closure packets.

Purpose: turn a blocked Local Developer Workflow v1 PR admission packet into a
concrete missing-evidence closure plan.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: Local Developer Workflow v1 artifacts, command preview packet,
closure packet, and PR admission packet.
Invariants:
  - Approval evidence closure packets do not grant execution authority.
  - Every required external witness remains absent in Foundation Mode.
  - Branch write, PR creation, merge, deployment, connector calls, external
    writes, and live execution remain blocked.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from software_dev.local_developer_workflow_v1.pr_admission_packet import (
    PR_ADMISSION_PACKET_ID,
    validate_local_developer_workflow_pr_admission_packet,
)
from software_dev.local_developer_workflow_v1.runner import (
    FORBIDDEN_EFFECTS,
    WORKFLOW_ID,
    validate_local_developer_workflow_v1_artifacts,
)


SCHEMA_VERSION = 1
APPROVAL_EVIDENCE_CLOSURE_PACKET_ID = (
    "local_developer_workflow_v1.approval_evidence_closure_packet.foundation.v1"
)
APPROVAL_EVIDENCE_CLOSURE_PACKET_FILENAME = (
    "local_developer_workflow_v1_approval_evidence_closure_packet.json"
)
MISSING_EVIDENCE_REF_IDS = (
    "external_pr_execution_approval_witness",
    "branch_write_authority_witness",
    "pull_request_creation_admission_witness",
    "rollback_effect_witness",
    "uao_execution_admission_receipt",
    "post_execution_effect_reconciliation_witness",
)
VALIDATOR_COMMANDS = (
    "python scripts/validate_local_developer_workflow_approval_evidence_closure_packet.py --strict",
    "python -m pytest tests/test_local_developer_workflow_v1.py -q",
)


class LocalDeveloperWorkflowApprovalEvidenceClosurePacketError(ValueError):
    """Raised when an approval evidence closure packet cannot be built or validated."""


@dataclass(frozen=True, slots=True)
class LocalDeveloperWorkflowApprovalEvidenceClosurePacketValidation:
    """Validation report for an approval evidence closure packet."""

    ok: bool
    errors: tuple[str, ...]
    packet_id: str
    closure_status: str
    missing_evidence_count: int
    packet_path: str

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-ready validation report."""

        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def build_local_developer_workflow_approval_evidence_closure_packet(
    *,
    artifacts: Mapping[str, Mapping[str, Any]],
    command_preview_packet: Mapping[str, Any],
    pr_admission_packet: Mapping[str, Any],
    closure_packet: Mapping[str, Any] | None = None,
    artifact_paths: Mapping[str, Path] | None = None,
    command_preview_packet_path: Path = Path("<generated>"),
    pr_admission_packet_path: Path = Path("<generated>"),
    closure_packet_path: Path = Path("<generated>"),
) -> dict[str, Any]:
    """Return a no-effect approval evidence closure packet."""

    artifact_validation = validate_local_developer_workflow_v1_artifacts(
        artifacts=artifacts,
        artifact_paths=artifact_paths,
    )
    if not artifact_validation.ok:
        raise LocalDeveloperWorkflowApprovalEvidenceClosurePacketError(
            f"local_developer_workflow_artifacts_invalid:{list(artifact_validation.errors)}"
        )
    admission_validation = validate_local_developer_workflow_pr_admission_packet(
        packet=pr_admission_packet,
        artifacts=artifacts,
        command_preview_packet=command_preview_packet,
        closure_packet=closure_packet,
        artifact_paths=artifact_paths,
        packet_path=pr_admission_packet_path,
        command_preview_packet_path=command_preview_packet_path,
        closure_packet_path=closure_packet_path,
    )
    if not admission_validation.ok:
        raise LocalDeveloperWorkflowApprovalEvidenceClosurePacketError(
            f"pr_admission_packet_invalid:{list(admission_validation.errors)}"
        )

    evidence_refs = [_missing_evidence_ref(ref_id) for ref_id in MISSING_EVIDENCE_REF_IDS]
    packet = {
        "schema_version": SCHEMA_VERSION,
        "packet_id": APPROVAL_EVIDENCE_CLOSURE_PACKET_ID,
        "workflow_id": WORKFLOW_ID,
        "workflow_run_id": artifact_validation.workflow_run_id,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "projection_only": True,
        "packet_is_not_execution_authority": True,
        "execution_performed": False,
        "approval_performed": False,
        "external_effects_allowed": False,
        "branch_write_allowed": False,
        "pr_creation_allowed": False,
        "merge_allowed": False,
        "live_execution_enabled": False,
        "source_admission": {
            "packet_id": str(pr_admission_packet.get("packet_id") or ""),
            "packet_path": _path_label(pr_admission_packet_path),
            "admission_decision": str(pr_admission_packet.get("admission_decision") or ""),
            "admission_remains_blocked": True,
        },
        "required_evidence_refs": evidence_refs,
        "missing_evidence_refs": list(MISSING_EVIDENCE_REF_IDS),
        "next_required_proof_step": (
            "collect external_pr_execution_approval_witness as a signed operator evidence ref; "
            "do not execute branch write or pull-request creation"
        ),
        "closure_receipt": {
            "closure_status": "blocked_waiting_evidence",
            "missing_evidence_count": len(evidence_refs),
            "approval_evidence_complete": False,
            "execution_ready": False,
        },
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
            pr_admission_packet=pr_admission_packet,
            pr_admission_packet_path=pr_admission_packet_path,
            closure_packet=closure_packet,
            closure_packet_path=closure_packet_path,
            artifact_paths=artifact_paths,
        ),
        "validators": list(VALIDATOR_COMMANDS),
        "causal_trace": [
            "validated Local Developer Workflow v1 preview artifacts",
            "validated local command review packet through PR admission validator",
            "confirmed PR admission remains blocked",
            "enumerated missing approval and evidence refs before external effects",
            "selected the next proof step without granting execution authority",
        ],
        "packet_hash": "",
    }
    packet["packet_hash"] = _digest(packet)
    return packet


def write_local_developer_workflow_approval_evidence_closure_packet(
    packet: Mapping[str, Any],
    output_path: Path,
) -> Path:
    """Write a deterministic approval evidence closure packet."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(dict(packet), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def validate_local_developer_workflow_approval_evidence_closure_packet(
    *,
    packet: Mapping[str, Any],
    artifacts: Mapping[str, Mapping[str, Any]],
    command_preview_packet: Mapping[str, Any],
    pr_admission_packet: Mapping[str, Any],
    closure_packet: Mapping[str, Any] | None = None,
    artifact_paths: Mapping[str, Path] | None = None,
    packet_path: Path = Path("<generated>"),
    command_preview_packet_path: Path = Path("<generated>"),
    pr_admission_packet_path: Path = Path("<generated>"),
    closure_packet_path: Path = Path("<generated>"),
) -> LocalDeveloperWorkflowApprovalEvidenceClosurePacketValidation:
    """Validate approval evidence closure packet no-effect semantics."""

    errors: list[str] = []
    artifact_validation = validate_local_developer_workflow_v1_artifacts(
        artifacts=artifacts,
        artifact_paths=artifact_paths,
    )
    if not artifact_validation.ok:
        errors.extend(f"source_artifacts:{error}" for error in artifact_validation.errors)
    admission_validation = validate_local_developer_workflow_pr_admission_packet(
        packet=pr_admission_packet,
        artifacts=artifacts,
        command_preview_packet=command_preview_packet,
        closure_packet=closure_packet,
        artifact_paths=artifact_paths,
        packet_path=pr_admission_packet_path,
        command_preview_packet_path=command_preview_packet_path,
        closure_packet_path=closure_packet_path,
    )
    if not admission_validation.ok:
        errors.extend(f"pr_admission_packet:{error}" for error in admission_validation.errors)
    if packet.get("packet_id") != APPROVAL_EVIDENCE_CLOSURE_PACKET_ID:
        errors.append("packet_id_mismatch")
    if packet.get("workflow_id") != WORKFLOW_ID:
        errors.append("workflow_id_mismatch")
    if packet.get("workflow_run_id") != artifact_validation.workflow_run_id:
        errors.append("workflow_run_id_mismatch")
    for field_name in ("projection_only", "packet_is_not_execution_authority"):
        if packet.get(field_name) is not True:
            errors.append(f"{field_name}_must_be_true")
    for field_name in (
        "execution_performed",
        "approval_performed",
        "external_effects_allowed",
        "branch_write_allowed",
        "pr_creation_allowed",
        "merge_allowed",
        "live_execution_enabled",
    ):
        if packet.get(field_name) is not False:
            errors.append(f"{field_name}_must_be_false")
    source_admission = _mapping(packet.get("source_admission"))
    if source_admission.get("packet_id") != PR_ADMISSION_PACKET_ID:
        errors.append("source_admission_packet_id_mismatch")
    if source_admission.get("admission_decision") != "blocked_waiting_external_execution_approval":
        errors.append("source_admission_decision_must_remain_blocked")
    if source_admission.get("admission_remains_blocked") is not True:
        errors.append("source_admission_remains_blocked_must_be_true")
    evidence_refs = packet.get("required_evidence_refs")
    if not isinstance(evidence_refs, list) or len(evidence_refs) != len(MISSING_EVIDENCE_REF_IDS):
        errors.append("required_evidence_refs_must_match_canonical_count")
    else:
        seen_ref_ids: list[str] = []
        for index, evidence_ref in enumerate(evidence_refs):
            if not isinstance(evidence_ref, Mapping):
                errors.append(f"required_evidence_refs[{index}]_must_be_object")
                continue
            ref_id = str(evidence_ref.get("evidence_ref_id") or "")
            seen_ref_ids.append(ref_id)
            if evidence_ref.get("required") is not True:
                errors.append(f"required_evidence_refs[{index}]_required_must_be_true")
            if evidence_ref.get("present") is not False:
                errors.append(f"required_evidence_refs[{index}]_present_must_be_false")
            if evidence_ref.get("blocks_execution") is not True:
                errors.append(f"required_evidence_refs[{index}]_blocks_execution_must_be_true")
        if tuple(seen_ref_ids) != MISSING_EVIDENCE_REF_IDS:
            errors.append("required_evidence_refs_order_mismatch")
    missing_refs = tuple(str(item) for item in packet.get("missing_evidence_refs", ()))
    if missing_refs != MISSING_EVIDENCE_REF_IDS:
        errors.append("missing_evidence_refs_must_match_required_refs")
    closure_receipt = _mapping(packet.get("closure_receipt"))
    if closure_receipt.get("closure_status") != "blocked_waiting_evidence":
        errors.append("closure_status_must_block_waiting_evidence")
    if closure_receipt.get("approval_evidence_complete") is not False:
        errors.append("approval_evidence_complete_must_be_false")
    if closure_receipt.get("execution_ready") is not False:
        errors.append("execution_ready_must_be_false")
    if closure_receipt.get("missing_evidence_count") != len(MISSING_EVIDENCE_REF_IDS):
        errors.append("missing_evidence_count_mismatch")
    boundary = _mapping(packet.get("effect_boundary"))
    for effect_name, expected in FORBIDDEN_EFFECTS.items():
        if boundary.get(effect_name) is not expected:
            errors.append(f"effect_boundary_mismatch:{effect_name}")
    expected_hash = dict(packet)
    expected_hash["packet_hash"] = ""
    if packet.get("packet_hash") != _digest(expected_hash):
        errors.append("packet_hash_mismatch")
    return LocalDeveloperWorkflowApprovalEvidenceClosurePacketValidation(
        ok=not errors,
        errors=tuple(errors),
        packet_id=str(packet.get("packet_id") or ""),
        closure_status=str(closure_receipt.get("closure_status") or ""),
        missing_evidence_count=int(closure_receipt.get("missing_evidence_count") or 0),
        packet_path=_path_label(packet_path),
    )


def _missing_evidence_ref(ref_id: str) -> dict[str, Any]:
    return {
        "evidence_ref_id": ref_id,
        "witness_type": ref_id,
        "required": True,
        "present": False,
        "blocks_execution": True,
    }


def _source_refs(
    *,
    command_preview_packet: Mapping[str, Any],
    command_preview_packet_path: Path,
    pr_admission_packet: Mapping[str, Any],
    pr_admission_packet_path: Path,
    closure_packet: Mapping[str, Any] | None,
    closure_packet_path: Path,
    artifact_paths: Mapping[str, Path] | None,
) -> dict[str, str]:
    refs = {
        "command_preview_packet_id": str(command_preview_packet.get("packet_id") or ""),
        "command_preview_packet_path": _path_label(command_preview_packet_path),
        "pr_admission_packet_id": str(pr_admission_packet.get("packet_id") or ""),
        "pr_admission_packet_path": _path_label(pr_admission_packet_path),
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
