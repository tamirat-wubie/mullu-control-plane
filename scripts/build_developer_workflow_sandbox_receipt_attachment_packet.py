#!/usr/bin/env python3
"""Build the Developer Workflow sandbox receipt attachment packet.

Purpose: summarize the four sandbox receipt slots into operator-attachable
evidence rows without collecting files or executing commands.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: sandbox-to-PR packet, sandbox receipt bundle, and attachment
packet validator.
Invariants:
  - Builder is projection-only and never performs writes, tests, PR actions, or
    connector calls.
  - Attachment rows preserve canonical receipt order and action hints.
  - Attached status is derived only from the validated sandbox receipt bundle.
"""

from __future__ import annotations

import argparse
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
from scripts.validate_developer_workflow_sandbox_receipt_attachment_packet import (  # noqa: E402
    validate_developer_workflow_sandbox_receipt_attachment_packet,
)
from scripts.validate_sandbox_to_pr_preparation_packet import EXPECTED_NEXT_EVIDENCE_ACTIONS  # noqa: E402


DEFAULT_SANDBOX_TO_PR_PACKET = REPO_ROOT / "examples" / "sandbox_to_pr_preparation_packet.foundation.json"
DEFAULT_SANDBOX_RECEIPT_BUNDLE = REPO_ROOT / "examples" / "developer_workflow_sandbox_receipt_bundle.foundation.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "developer_workflow_sandbox_receipt_attachment_packet.generated.json"
REQUIRED_INPUTS = (
    "before_state_hash",
    "after_state_hash",
    "diff_hash",
    "command",
    "rollback_command",
    "evidence_refs",
)


def build_developer_workflow_sandbox_receipt_attachment_packet(
    *,
    sandbox_to_pr_packet: Mapping[str, Any],
    sandbox_to_pr_packet_path: Path,
    sandbox_receipt_bundle: Mapping[str, Any],
    sandbox_receipt_bundle_path: Path,
) -> dict[str, Any]:
    """Return a projection-only receipt attachment packet."""

    workflow_run_id = str(sandbox_receipt_bundle.get("workflow_run_id") or "developer_workflow_v1_foundation_run")
    bundle_receipts = sandbox_receipt_bundle.get("receipts", ())
    bundle_by_id = {
        str(receipt.get("receipt_id") or ""): receipt
        for receipt in bundle_receipts
        if isinstance(bundle_receipts, list) and isinstance(receipt, Mapping)
    }
    packet_evidence = sandbox_to_pr_packet.get("next_evidence", ())
    packet_by_id = {
        str(evidence.get("evidence_id") or ""): evidence
        for evidence in packet_evidence
        if isinstance(packet_evidence, list) and isinstance(evidence, Mapping)
    }
    attachments = [
        _attachment_row(
            receipt_id=receipt_id,
            label=label,
            stage=stage,
            bundle_receipt=bundle_by_id.get(receipt_id, {}),
            packet_evidence=packet_by_id.get(receipt_id, {}),
        )
        for receipt_id, label, stage in EXPECTED_RECEIPTS
    ]
    completed_count = sum(1 for item in attachments if item["status"] == "attached")
    return {
        "packet_id": "developer_workflow_sandbox_receipt_attachment_packet.v1",
        "workflow_id": "mullu_developer_workflow.v1",
        "workflow_run_id": workflow_run_id,
        "packet_status": "attachments_complete" if completed_count == len(EXPECTED_RECEIPTS) else "awaiting_attachments",
        "execution_boundary": "local_lab_only",
        "external_effects_allowed": False,
        "required_count": len(EXPECTED_RECEIPTS),
        "completed_count": completed_count,
        "next_attachment": _next_attachment(attachments),
        "source_refs": {
            "sandbox_to_pr_packet": _path_label(sandbox_to_pr_packet_path),
            "sandbox_receipt_bundle": _path_label(sandbox_receipt_bundle_path),
            "builder": "python scripts/build_developer_workflow_sandbox_receipt_attachment_packet.py",
            "validator": "python scripts/validate_developer_workflow_sandbox_receipt_attachment_packet.py",
        },
        "attachments": attachments,
    }


def write_developer_workflow_sandbox_receipt_attachment_packet(packet: Mapping[str, Any], output_path: Path) -> Path:
    """Write a deterministic attachment packet."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _attachment_row(
    *,
    receipt_id: str,
    label: str,
    stage: str,
    bundle_receipt: Mapping[str, Any],
    packet_evidence: Mapping[str, Any],
) -> dict[str, Any]:
    bundle_status = str(bundle_receipt.get("status") or "pending")
    status = "attached" if bundle_status == "complete" else "awaiting_attachment"
    return {
        "receipt_id": receipt_id,
        "label": str(bundle_receipt.get("label") or packet_evidence.get("label") or label),
        "stage": str(bundle_receipt.get("stage") or stage),
        "status": status,
        "action": str(packet_evidence.get("action") or EXPECTED_NEXT_EVIDENCE_ACTIONS[receipt_id]),
        "source": str(bundle_receipt.get("source") or packet_evidence.get("source") or _source(receipt_id)),
        "bundle_receipt_status": bundle_status,
        "required_inputs": list(REQUIRED_INPUTS),
        "observed_inputs": {
            field_name: str(bundle_receipt.get(field_name) or "pending")
            for field_name in PENDING_PLACEHOLDER_FIELDS
        },
        "evidence_refs": [
            str(item)
            for item in bundle_receipt.get("evidence_refs", ())
            if str(item).strip()
        ] if isinstance(bundle_receipt.get("evidence_refs", ()), list) else [],
    }


def _next_attachment(attachments: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    for attachment in attachments:
        if attachment.get("status") != "attached":
            return {
                "receipt_id": str(attachment.get("receipt_id") or ""),
                "label": str(attachment.get("label") or ""),
                "status": str(attachment.get("status") or "awaiting_attachment"),
                "action": str(attachment.get("action") or ""),
            }
    return {
        "receipt_id": "none",
        "label": "All sandbox receipts attached",
        "status": "complete",
        "action": "review sandbox receipt bundle before PR preparation approval",
    }


def _source(receipt_id: str) -> str:
    return f"workflow_monitor.metadata.developer_workflow_run.receipt_checklist.{receipt_id}"


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"json_parse_failed:{path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"json_root_must_be_object:{path}")
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
    """Parse attachment packet builder arguments."""

    parser = argparse.ArgumentParser(description="Build Developer Workflow sandbox receipt attachment packet.")
    parser.add_argument("--sandbox-to-pr-packet", default=str(DEFAULT_SANDBOX_TO_PR_PACKET))
    parser.add_argument("--sandbox-receipt-bundle", default=str(DEFAULT_SANDBOX_RECEIPT_BUNDLE))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for attachment packet building."""

    args = parse_args(argv)
    try:
        sandbox_to_pr_packet_path = Path(args.sandbox_to_pr_packet)
        sandbox_receipt_bundle_path = Path(args.sandbox_receipt_bundle)
        packet = build_developer_workflow_sandbox_receipt_attachment_packet(
            sandbox_to_pr_packet=_load_json_object(sandbox_to_pr_packet_path),
            sandbox_to_pr_packet_path=sandbox_to_pr_packet_path,
            sandbox_receipt_bundle=_load_json_object(sandbox_receipt_bundle_path),
            sandbox_receipt_bundle_path=sandbox_receipt_bundle_path,
        )
        output_path = write_developer_workflow_sandbox_receipt_attachment_packet(packet, Path(args.output))
        validation = validate_developer_workflow_sandbox_receipt_attachment_packet(
            packet_path=output_path,
            sandbox_to_pr_packet_path=sandbox_to_pr_packet_path,
            sandbox_receipt_bundle_path=sandbox_receipt_bundle_path,
        )
    except ValueError as exc:
        print(f"DEVELOPER WORKFLOW SANDBOX RECEIPT ATTACHMENT PACKET BUILD INVALID error={exc}")
        return 2
    if not validation.ok:
        print(f"DEVELOPER WORKFLOW SANDBOX RECEIPT ATTACHMENT PACKET BUILD INVALID errors={list(validation.errors)}")
        return 2
    if args.json:
        print(json.dumps(packet, indent=2, sort_keys=True))
    else:
        print(f"DEVELOPER WORKFLOW SANDBOX RECEIPT ATTACHMENT PACKET BUILT path={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
