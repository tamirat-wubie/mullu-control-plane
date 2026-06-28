#!/usr/bin/env python3
"""Validate the sandbox-to-PR preparation packet.

Purpose: prove the local Developer Workflow v1 PR-preparation packet is a
read-only, local-lab projection with explicit evidence and blocker state.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: sandbox-to-PR packet schema, example packet, and schema validator.
Invariants:
  - The packet never grants execution authority or external effects.
  - Required evidence is explicit, unique, and source-bound.
  - The blocker is causally consistent with policy, receipt, approval, and PR
    candidate state.
  - PR candidate readiness requires completed receipts and operator approval.
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

from scripts.validate_schemas import _validate_schema_instance  # noqa: E402

DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "sandbox_to_pr_preparation_packet.schema.json"
DEFAULT_PACKET = REPO_ROOT / "examples" / "sandbox_to_pr_preparation_packet.foundation.json"
DEFAULT_FRICTION_CONTROL = REPO_ROOT / "examples" / "capability_friction_control.foundation.json"
DEFAULT_RECEIPT_BUNDLE = REPO_ROOT / "examples" / "developer_workflow_sandbox_receipt_bundle.foundation.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "sandbox_to_pr_preparation_packet_validation.json"
EXPECTED_EVIDENCE_IDS = (
    "capability_passports",
    "sandbox_receipts",
    "operator_approval",
    "pr_candidate",
)
EXPECTED_NEXT_EVIDENCE_IDS = (
    "sandbox_patch_receipt",
    "test_gate_receipt",
    "diff_review_receipt",
    "terminal_receipt",
)
EXPECTED_NEXT_EVIDENCE_ACTIONS = {
    "sandbox_patch_receipt": "attach before state, after state, diff, command, and rollback receipt",
    "test_gate_receipt": "attach bounded local test command receipt and observed result",
    "diff_review_receipt": "attach reviewed diff hash and reviewer evidence reference",
    "terminal_receipt": "attach final local receipt summary and no-external-effect witness",
}
STATUS_BLOCKER = {
    "awaiting_receipts": "sandbox_receipts_incomplete",
    "awaiting_operator_approval": "operator_approval_missing",
    "ready_to_prepare_pr": "pr_candidate_not_prepared",
    "pr_candidate_ready": "none",
}


@dataclass(frozen=True, slots=True)
class SandboxToPrPacketValidation:
    """Validation report for the sandbox-to-PR preparation packet."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    packet_path: str
    packet_status: str
    blocker: str
    evidence_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_sandbox_to_pr_preparation_packet(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    packet_path: Path = DEFAULT_PACKET,
    friction_control_path: Path = DEFAULT_FRICTION_CONTROL,
    receipt_bundle_path: Path = DEFAULT_RECEIPT_BUNDLE,
) -> SandboxToPrPacketValidation:
    """Validate packet schema and local-lab semantic consistency."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "sandbox-to-PR packet schema", errors)
    packet = _load_json_object(packet_path, "sandbox-to-PR packet", errors)
    friction_control = _load_json_object(friction_control_path, "capability friction-control read model", errors)
    receipt_bundle = _load_json_object(receipt_bundle_path, "sandbox receipt bundle", errors)
    if schema and packet:
        errors.extend(f"{_path_label(packet_path)}: {error}" for error in _validate_schema_instance(schema, packet))
        _validate_packet_semantics(packet, errors, _path_label(packet_path))
        if friction_control:
            _validate_friction_control_no_drift(
                packet,
                friction_control,
                errors,
                _path_label(packet_path),
                _path_label(friction_control_path),
            )
        if receipt_bundle:
            _validate_receipt_bundle_ref(
                packet,
                receipt_bundle,
                errors,
                _path_label(packet_path),
                _path_label(receipt_bundle_path),
            )
    required_evidence = packet.get("required_evidence", ()) if isinstance(packet, Mapping) else ()
    return SandboxToPrPacketValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        packet_path=_path_label(packet_path),
        packet_status=str(packet.get("status", "")) if isinstance(packet, Mapping) else "",
        blocker=str(packet.get("blocker", "")) if isinstance(packet, Mapping) else "",
        evidence_count=len(required_evidence) if isinstance(required_evidence, list) else 0,
    )


def write_sandbox_to_pr_preparation_packet_validation(
    validation: SandboxToPrPacketValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic validation report for the packet."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_packet_semantics(packet: Mapping[str, Any], errors: list[str], label: str) -> None:
    if packet.get("external_effects_allowed") is not False:
        errors.append(f"{label}: external_effects_allowed must remain false")
    if packet.get("execution_boundary") != "local_lab_only":
        errors.append(f"{label}: execution_boundary must be local_lab_only")
    _validate_required_evidence(packet, errors, label)
    _validate_next_evidence(packet, errors, label)
    _validate_receipt_bundle_reference(packet, errors, label)
    _validate_blocker(packet, errors, label)
    _validate_state_consistency(packet, errors, label)


def _validate_required_evidence(packet: Mapping[str, Any], errors: list[str], label: str) -> None:
    evidence = packet.get("required_evidence")
    if not isinstance(evidence, list):
        errors.append(f"{label}: required_evidence must be a list")
        return
    evidence_ids = tuple(str(item.get("evidence_id", "")) for item in evidence if isinstance(item, Mapping))
    if evidence_ids != EXPECTED_EVIDENCE_IDS:
        errors.append(f"{label}: required_evidence must list canonical evidence ids in order")
    if len(set(evidence_ids)) != len(evidence_ids):
        errors.append(f"{label}: required_evidence ids must be unique")
    by_id = {str(item.get("evidence_id", "")): item for item in evidence if isinstance(item, Mapping)}
    policy = packet.get("policy", {})
    receipts = packet.get("receipts", {})
    approval = packet.get("approval", {})
    pr_candidate = packet.get("pr_candidate", {})
    if isinstance(policy, Mapping) and by_id.get("capability_passports", {}).get("status") != (
        "complete" if policy.get("ready") is True else "pending"
    ):
        errors.append(f"{label}: capability_passports evidence status must match policy.ready")
    if isinstance(receipts, Mapping) and by_id.get("sandbox_receipts", {}).get("status") != (
        "complete" if receipts.get("ready") is True else "pending"
    ):
        errors.append(f"{label}: sandbox_receipts evidence status must match receipts.ready")
    if isinstance(approval, Mapping) and by_id.get("operator_approval", {}).get("status") != approval.get("status"):
        errors.append(f"{label}: operator_approval evidence status must match approval.status")
    if isinstance(pr_candidate, Mapping) and by_id.get("pr_candidate", {}).get("status") != pr_candidate.get("status"):
        errors.append(f"{label}: pr_candidate evidence status must match pr_candidate.status")


def _validate_next_evidence(packet: Mapping[str, Any], errors: list[str], label: str) -> None:
    next_evidence = packet.get("next_evidence")
    if not isinstance(next_evidence, list):
        errors.append(f"{label}: next_evidence must be a list")
        return
    evidence_ids = tuple(
        str(item.get("evidence_id", ""))
        for item in next_evidence
        if isinstance(item, Mapping)
    )
    if evidence_ids != EXPECTED_NEXT_EVIDENCE_IDS:
        errors.append(f"{label}: next_evidence must list canonical receipt evidence in order")
    receipts = packet.get("receipts", {})
    expected_status = "complete" if isinstance(receipts, Mapping) and receipts.get("ready") is True else "pending"
    for evidence in next_evidence:
        if not isinstance(evidence, Mapping):
            errors.append(f"{label}: next_evidence entries must be objects")
            continue
        evidence_id = str(evidence.get("evidence_id", ""))
        if evidence.get("status") != expected_status:
            errors.append(f"{label}: next_evidence.{evidence_id} status must be {expected_status}")
        expected_action = EXPECTED_NEXT_EVIDENCE_ACTIONS.get(evidence_id)
        if expected_action is None or evidence.get("action") != expected_action:
            errors.append(f"{label}: next_evidence.{evidence_id} action must be canonical")
        expected_source = f"workflow_monitor.metadata.developer_workflow_run.receipt_checklist.{evidence_id}"
        if evidence.get("source") != expected_source:
            errors.append(f"{label}: next_evidence.{evidence_id} source must be {expected_source!r}")


def _validate_friction_control_no_drift(
    packet: Mapping[str, Any],
    friction_control: Mapping[str, Any],
    errors: list[str],
    packet_label: str,
    friction_label: str,
) -> None:
    sandbox_to_pr = friction_control.get("sandbox_to_pr_now")
    if not isinstance(sandbox_to_pr, Mapping):
        errors.append(f"{packet_label}: cannot compare next_evidence because {friction_label} lacks sandbox_to_pr_now")
        return
    packet_evidence = packet.get("next_evidence")
    friction_evidence = sandbox_to_pr.get("next_evidence")
    if not isinstance(packet_evidence, list) or not isinstance(friction_evidence, list):
        errors.append(f"{packet_label}: next_evidence cannot be compared with {friction_label}")
        return
    if _queue_evidence_signature(packet_evidence) != _queue_evidence_signature(friction_evidence):
        errors.append(f"{packet_label}: next_evidence drifts from {friction_label}")


def _validate_receipt_bundle_reference(packet: Mapping[str, Any], errors: list[str], label: str) -> None:
    receipt_bundle_ref = packet.get("receipt_bundle_ref")
    if not isinstance(receipt_bundle_ref, Mapping):
        errors.append(f"{label}: receipt_bundle_ref must be an object")
        return
    if receipt_bundle_ref.get("schema_ref") != "schemas/developer_workflow_sandbox_receipt_bundle.schema.json":
        errors.append(f"{label}: receipt_bundle_ref.schema_ref must point to sandbox receipt bundle schema")
    if receipt_bundle_ref.get("example_path") != "examples/developer_workflow_sandbox_receipt_bundle.foundation.json":
        errors.append(f"{label}: receipt_bundle_ref.example_path must point to sandbox receipt bundle fixture")
    if receipt_bundle_ref.get("validator") != "python scripts/validate_developer_workflow_sandbox_receipt_bundle.py":
        errors.append(f"{label}: receipt_bundle_ref.validator must point to sandbox receipt bundle validator")
    if receipt_bundle_ref.get("builder") != "python scripts/build_developer_workflow_sandbox_receipt_bundle.py":
        errors.append(f"{label}: receipt_bundle_ref.builder must point to sandbox receipt bundle builder")


def _validate_receipt_bundle_ref(
    packet: Mapping[str, Any],
    receipt_bundle: Mapping[str, Any],
    errors: list[str],
    packet_label: str,
    bundle_label: str,
) -> None:
    receipts = packet.get("receipts")
    bundle_receipts = receipt_bundle.get("receipts")
    if not isinstance(receipts, Mapping) or not isinstance(bundle_receipts, list):
        errors.append(f"{packet_label}: cannot compare receipts with {bundle_label}")
        return
    bundle_completed_count = sum(
        1
        for receipt in bundle_receipts
        if isinstance(receipt, Mapping) and receipt.get("status") == "complete"
    )
    declared_bundle_completed_count = int(receipt_bundle.get("completed_count", -1) or 0)
    if declared_bundle_completed_count != bundle_completed_count:
        errors.append(f"{packet_label}: {bundle_label} completed_count does not match bundle receipts")
    if int(receipts.get("completed_count", -1) or 0) != declared_bundle_completed_count:
        errors.append(f"{packet_label}: receipts.completed_count drifts from {bundle_label}")
    if (receipts.get("ready") is True) != (receipt_bundle.get("bundle_status") == "receipts_complete"):
        errors.append(f"{packet_label}: receipts.ready drifts from {bundle_label}")
    packet_signature = _receipt_evidence_signature(packet.get("next_evidence", []) if isinstance(packet.get("next_evidence"), list) else [])
    bundle_signature = tuple(
        (
            str(item.get("receipt_id", "")),
            str(item.get("label", "")),
            str(item.get("source", "")),
        )
        for item in bundle_receipts
        if isinstance(item, Mapping)
    )
    if packet_signature != bundle_signature:
        errors.append(f"{packet_label}: next_evidence drifts from {bundle_label}")


def _queue_evidence_signature(evidence_items: list[object]) -> tuple[tuple[str, str, str, str], ...]:
    signature: list[tuple[str, str, str, str]] = []
    for item in evidence_items:
        if not isinstance(item, Mapping):
            continue
        signature.append((
            str(item.get("evidence_id", "")),
            str(item.get("label", "")),
            str(item.get("action", "")),
            str(item.get("source", "")),
        ))
    return tuple(signature)


def _receipt_evidence_signature(evidence_items: list[object]) -> tuple[tuple[str, str, str], ...]:
    signature: list[tuple[str, str, str]] = []
    for item in evidence_items:
        if not isinstance(item, Mapping):
            continue
        signature.append((
            str(item.get("evidence_id", "")),
            str(item.get("label", "")),
            str(item.get("source", "")),
        ))
    return tuple(signature)


def _validate_blocker(packet: Mapping[str, Any], errors: list[str], label: str) -> None:
    policy = packet.get("policy", {})
    receipts = packet.get("receipts", {})
    approval = packet.get("approval", {})
    pr_candidate = packet.get("pr_candidate", {})
    if not isinstance(policy, Mapping) or not isinstance(receipts, Mapping):
        return
    if not isinstance(approval, Mapping) or not isinstance(pr_candidate, Mapping):
        return
    observed_blocker = str(packet.get("blocker", ""))
    if policy.get("ready") is not True:
        expected_blocker = "capability_policy_incomplete"
    elif receipts.get("ready") is not True:
        expected_blocker = "sandbox_receipts_incomplete"
    elif approval.get("status") != "complete":
        expected_blocker = "operator_approval_missing"
    elif pr_candidate.get("status") != "complete":
        expected_blocker = "pr_candidate_not_prepared"
    else:
        expected_blocker = "none"
    if observed_blocker != expected_blocker:
        errors.append(f"{label}: blocker must be {expected_blocker!r} for observed packet state")
    expected_status_blocker = STATUS_BLOCKER.get(str(packet.get("status", "")))
    if expected_status_blocker and observed_blocker != expected_status_blocker:
        errors.append(f"{label}: status and blocker are inconsistent")


def _validate_state_consistency(packet: Mapping[str, Any], errors: list[str], label: str) -> None:
    receipts = packet.get("receipts", {})
    approval = packet.get("approval", {})
    pr_candidate = packet.get("pr_candidate", {})
    if isinstance(receipts, Mapping):
        completed_count = int(receipts.get("completed_count", -1) or 0)
        if receipts.get("ready") is True and completed_count != 4:
            errors.append(f"{label}: receipts.ready requires completed_count 4")
        if receipts.get("ready") is False and completed_count >= 4:
            errors.append(f"{label}: receipts.ready cannot be false when completed_count is 4")
    if isinstance(approval, Mapping) and approval.get("required") is not True:
        errors.append(f"{label}: operator approval must remain required")
    if isinstance(pr_candidate, Mapping):
        prepared = pr_candidate.get("prepared") is True
        status_complete = pr_candidate.get("status") == "complete"
        if prepared != status_complete:
            errors.append(f"{label}: pr_candidate.prepared must match complete status")


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    if not path.exists():
        errors.append(f"{label} file missing: {_path_label(path)}")
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError):
        errors.append(f"{label} JSON parse failed")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{label} JSON root must be an object")
        return {}
    return payload


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse sandbox-to-PR packet validation arguments."""

    parser = argparse.ArgumentParser(description="Validate sandbox-to-PR preparation packet.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--packet", default=str(DEFAULT_PACKET))
    parser.add_argument("--friction-control", default=str(DEFAULT_FRICTION_CONTROL))
    parser.add_argument("--receipt-bundle", default=str(DEFAULT_RECEIPT_BUNDLE))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for sandbox-to-PR packet validation."""

    args = parse_args(argv)
    validation = validate_sandbox_to_pr_preparation_packet(
        schema_path=Path(args.schema),
        packet_path=Path(args.packet),
        friction_control_path=Path(args.friction_control),
        receipt_bundle_path=Path(args.receipt_bundle),
    )
    write_sandbox_to_pr_preparation_packet_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("SANDBOX TO PR PREPARATION PACKET VALID")
    else:
        print(f"SANDBOX TO PR PREPARATION PACKET INVALID errors={list(validation.errors)}")
    return 0 if validation.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
