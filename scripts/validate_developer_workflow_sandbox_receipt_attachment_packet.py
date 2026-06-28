#!/usr/bin/env python3
"""Validate the Developer Workflow sandbox receipt attachment packet.

Purpose: prove each sandbox receipt attachment row is canonical, source-bound,
and projection-only before local PR preparation can depend on it.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: attachment packet schema, sandbox-to-PR packet fixture, sandbox
receipt bundle fixture, and schema validator.
Invariants:
  - Attachment packet never grants external effects.
  - Attachment status is derived from the sandbox receipt bundle.
  - Action hints match the sandbox-to-PR packet.
  - Required input names are deterministic and ordered.
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

from scripts.validate_developer_workflow_sandbox_receipt_bundle import (  # noqa: E402
    EXPECTED_RECEIPTS,
    PENDING_PLACEHOLDER_FIELDS,
)
from scripts.validate_sandbox_to_pr_preparation_packet import EXPECTED_NEXT_EVIDENCE_ACTIONS  # noqa: E402
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "developer_workflow_sandbox_receipt_attachment_packet.schema.json"
DEFAULT_PACKET = REPO_ROOT / "examples" / "developer_workflow_sandbox_receipt_attachment_packet.foundation.json"
DEFAULT_SANDBOX_TO_PR_PACKET = REPO_ROOT / "examples" / "sandbox_to_pr_preparation_packet.foundation.json"
DEFAULT_SANDBOX_RECEIPT_BUNDLE = REPO_ROOT / "examples" / "developer_workflow_sandbox_receipt_bundle.foundation.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "developer_workflow_sandbox_receipt_attachment_packet_validation.json"
REQUIRED_INPUTS = (
    "before_state_hash",
    "after_state_hash",
    "diff_hash",
    "command",
    "rollback_command",
    "evidence_refs",
)


@dataclass(frozen=True, slots=True)
class DeveloperWorkflowSandboxReceiptAttachmentPacketValidation:
    """Validation report for the sandbox receipt attachment packet."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    packet_path: str
    packet_status: str
    completed_count: int
    required_count: int
    next_attachment: str

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_developer_workflow_sandbox_receipt_attachment_packet(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    packet_path: Path = DEFAULT_PACKET,
    sandbox_to_pr_packet_path: Path = DEFAULT_SANDBOX_TO_PR_PACKET,
    sandbox_receipt_bundle_path: Path = DEFAULT_SANDBOX_RECEIPT_BUNDLE,
) -> DeveloperWorkflowSandboxReceiptAttachmentPacketValidation:
    """Validate schema and semantic consistency for an attachment packet."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "sandbox receipt attachment packet schema", errors)
    packet = _load_json_object(packet_path, "sandbox receipt attachment packet", errors)
    sandbox_to_pr_packet = _load_json_object(sandbox_to_pr_packet_path, "sandbox-to-PR packet", errors)
    sandbox_receipt_bundle = _load_json_object(sandbox_receipt_bundle_path, "sandbox receipt bundle", errors)
    if schema and packet:
        errors.extend(f"{_path_label(packet_path)}: {error}" for error in _validate_schema_instance(schema, packet))
        _validate_packet_semantics(
            packet,
            sandbox_to_pr_packet=sandbox_to_pr_packet,
            sandbox_receipt_bundle=sandbox_receipt_bundle,
            errors=errors,
            label=_path_label(packet_path),
        )
    next_attachment = packet.get("next_attachment", {}) if isinstance(packet, Mapping) else {}
    return DeveloperWorkflowSandboxReceiptAttachmentPacketValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        packet_path=_path_label(packet_path),
        packet_status=str(packet.get("packet_status", "")) if isinstance(packet, Mapping) else "",
        completed_count=int(packet.get("completed_count", 0) or 0) if isinstance(packet, Mapping) else 0,
        required_count=int(packet.get("required_count", 0) or 0) if isinstance(packet, Mapping) else 0,
        next_attachment=str(next_attachment.get("receipt_id", "")) if isinstance(next_attachment, Mapping) else "",
    )


def write_developer_workflow_sandbox_receipt_attachment_packet_validation(
    validation: DeveloperWorkflowSandboxReceiptAttachmentPacketValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic attachment packet validation report."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_packet_semantics(
    packet: Mapping[str, Any],
    *,
    sandbox_to_pr_packet: Mapping[str, Any],
    sandbox_receipt_bundle: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    if packet.get("external_effects_allowed") is not False:
        errors.append(f"{label}: external_effects_allowed must remain false")
    if packet.get("execution_boundary") != "local_lab_only":
        errors.append(f"{label}: execution_boundary must be local_lab_only")
    attachments = packet.get("attachments")
    if not isinstance(attachments, list):
        errors.append(f"{label}: attachments must be a list")
        return
    _validate_attachment_rows(
        attachments,
        sandbox_to_pr_packet=sandbox_to_pr_packet,
        sandbox_receipt_bundle=sandbox_receipt_bundle,
        errors=errors,
        label=label,
    )
    completed_count = sum(
        1
        for attachment in attachments
        if isinstance(attachment, Mapping) and attachment.get("status") == "attached"
    )
    if int(packet.get("completed_count", -1) or 0) != completed_count:
        errors.append(f"{label}: completed_count must match attached rows")
    expected_packet_status = "attachments_complete" if completed_count == len(EXPECTED_RECEIPTS) else "awaiting_attachments"
    if packet.get("packet_status") != expected_packet_status:
        errors.append(f"{label}: packet_status must be {expected_packet_status!r}")
    _validate_next_attachment(packet, attachments, errors, label)


def _validate_attachment_rows(
    attachments: list[object],
    *,
    sandbox_to_pr_packet: Mapping[str, Any],
    sandbox_receipt_bundle: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    expected_ids = tuple(item[0] for item in EXPECTED_RECEIPTS)
    observed_ids = tuple(str(item.get("receipt_id", "")) for item in attachments if isinstance(item, Mapping))
    if observed_ids != expected_ids:
        errors.append(f"{label}: attachments must list canonical receipt ids in order")
    bundle_by_id = _items_by_id(sandbox_receipt_bundle.get("receipts"), "receipt_id")
    packet_by_id = _items_by_id(sandbox_to_pr_packet.get("next_evidence"), "evidence_id")
    expected_by_id = {receipt_id: (expected_label, stage) for receipt_id, expected_label, stage in EXPECTED_RECEIPTS}
    for attachment in attachments:
        if not isinstance(attachment, Mapping):
            errors.append(f"{label}: attachment rows must be objects")
            continue
        receipt_id = str(attachment.get("receipt_id") or "")
        expected = expected_by_id.get(receipt_id)
        if expected is None:
            errors.append(f"{label}: unknown attachment receipt_id {receipt_id!r}")
            continue
        expected_label, expected_stage = expected
        bundle_receipt = bundle_by_id.get(receipt_id, {})
        packet_evidence = packet_by_id.get(receipt_id, {})
        _validate_attachment_row(
            attachment,
            receipt_id=receipt_id,
            expected_label=expected_label,
            expected_stage=expected_stage,
            bundle_receipt=bundle_receipt,
            packet_evidence=packet_evidence,
            errors=errors,
            label=label,
        )


def _validate_attachment_row(
    attachment: Mapping[str, Any],
    *,
    receipt_id: str,
    expected_label: str,
    expected_stage: str,
    bundle_receipt: Mapping[str, Any],
    packet_evidence: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    if attachment.get("label") != expected_label:
        errors.append(f"{label}: {receipt_id} label must be {expected_label!r}")
    if attachment.get("stage") != expected_stage:
        errors.append(f"{label}: {receipt_id} stage must be {expected_stage!r}")
    expected_source = f"workflow_monitor.metadata.developer_workflow_run.receipt_checklist.{receipt_id}"
    if attachment.get("source") != expected_source:
        errors.append(f"{label}: {receipt_id} source must be {expected_source!r}")
    expected_action = EXPECTED_NEXT_EVIDENCE_ACTIONS.get(receipt_id)
    if attachment.get("action") != expected_action or packet_evidence.get("action") != expected_action:
        errors.append(f"{label}: {receipt_id} action must match sandbox-to-PR packet")
    if tuple(attachment.get("required_inputs", ())) != REQUIRED_INPUTS:
        errors.append(f"{label}: {receipt_id} required_inputs must be canonical")
    bundle_status = str(bundle_receipt.get("status") or "pending")
    expected_status = "attached" if bundle_status == "complete" else "awaiting_attachment"
    if attachment.get("bundle_receipt_status") != bundle_status:
        errors.append(f"{label}: {receipt_id} bundle_receipt_status must match sandbox bundle")
    if attachment.get("status") != expected_status:
        errors.append(f"{label}: {receipt_id} status must derive from sandbox bundle")
    observed_inputs = attachment.get("observed_inputs")
    if not isinstance(observed_inputs, Mapping):
        errors.append(f"{label}: {receipt_id} observed_inputs must be an object")
    else:
        for field_name in PENDING_PLACEHOLDER_FIELDS:
            if observed_inputs.get(field_name) != bundle_receipt.get(field_name, "pending"):
                errors.append(f"{label}: {receipt_id}.{field_name} must match sandbox bundle")
    evidence_refs = attachment.get("evidence_refs")
    if not isinstance(evidence_refs, list):
        errors.append(f"{label}: {receipt_id} evidence_refs must be a list")
    elif evidence_refs != bundle_receipt.get("evidence_refs", []):
        errors.append(f"{label}: {receipt_id} evidence_refs must match sandbox bundle")


def _validate_next_attachment(
    packet: Mapping[str, Any],
    attachments: Sequence[object],
    errors: list[str],
    label: str,
) -> None:
    next_attachment = packet.get("next_attachment")
    if not isinstance(next_attachment, Mapping):
        errors.append(f"{label}: next_attachment must be an object")
        return
    expected = None
    for attachment in attachments:
        if isinstance(attachment, Mapping) and attachment.get("status") != "attached":
            expected = attachment
            break
    if expected is None:
        if next_attachment.get("receipt_id") != "none" or next_attachment.get("status") != "complete":
            errors.append(f"{label}: next_attachment must close when all attachments are complete")
        return
    if next_attachment.get("receipt_id") != expected.get("receipt_id"):
        errors.append(f"{label}: next_attachment must identify first pending attachment")
    if next_attachment.get("action") != expected.get("action"):
        errors.append(f"{label}: next_attachment action must match first pending attachment")


def _items_by_id(items: object, key: str) -> dict[str, Mapping[str, Any]]:
    if not isinstance(items, list):
        return {}
    return {
        str(item.get(key) or ""): item
        for item in items
        if isinstance(item, Mapping)
    }


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
    """Parse attachment packet validation arguments."""

    parser = argparse.ArgumentParser(description="Validate Developer Workflow sandbox receipt attachment packet.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--packet", default=str(DEFAULT_PACKET))
    parser.add_argument("--sandbox-to-pr-packet", default=str(DEFAULT_SANDBOX_TO_PR_PACKET))
    parser.add_argument("--sandbox-receipt-bundle", default=str(DEFAULT_SANDBOX_RECEIPT_BUNDLE))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for attachment packet validation."""

    args = parse_args(argv)
    validation = validate_developer_workflow_sandbox_receipt_attachment_packet(
        schema_path=Path(args.schema),
        packet_path=Path(args.packet),
        sandbox_to_pr_packet_path=Path(args.sandbox_to_pr_packet),
        sandbox_receipt_bundle_path=Path(args.sandbox_receipt_bundle),
    )
    write_developer_workflow_sandbox_receipt_attachment_packet_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("DEVELOPER WORKFLOW SANDBOX RECEIPT ATTACHMENT PACKET VALID")
    else:
        print(f"DEVELOPER WORKFLOW SANDBOX RECEIPT ATTACHMENT PACKET INVALID errors={list(validation.errors)}")
    return 0 if validation.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
