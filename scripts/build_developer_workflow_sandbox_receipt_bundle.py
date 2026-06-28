#!/usr/bin/env python3
"""Build a Developer Workflow v1 sandbox receipt bundle from local evidence.

Purpose: convert explicit local lab receipt evidence into the canonical
Developer Workflow v1 sandbox receipt bundle.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: developer workflow sandbox receipt bundle validator and JSON
evidence supplied by the operator or local workflow runtime.
Invariants:
  - The builder does not run writes, tests, diffs, PR operations, or connectors.
  - Missing receipt evidence remains pending.
  - Complete receipts require concrete state hashes, diff hash, command,
    rollback command, and evidence references.
  - Output is validated before the command exits successfully.
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
    validate_developer_workflow_sandbox_receipt_bundle,
)


DEFAULT_EVIDENCE = REPO_ROOT / "examples" / "developer_workflow_sandbox_receipt_evidence.partial.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "developer_workflow_sandbox_receipt_bundle.generated.json"
DEFAULT_WORKFLOW_RUN_ID = "developer_workflow_v1_foundation_run"


def build_developer_workflow_sandbox_receipt_bundle(evidence: Mapping[str, Any]) -> dict[str, Any]:
    """Build a canonical receipt bundle from explicit evidence."""

    workflow_run_id = _text_or_default(evidence.get("workflow_run_id"), DEFAULT_WORKFLOW_RUN_ID)
    evidence_by_receipt = _evidence_by_receipt(evidence.get("receipts", {}))
    receipts: list[dict[str, Any]] = []
    completed_count = 0
    for receipt_id, label, stage in EXPECTED_RECEIPTS:
        receipt_evidence = evidence_by_receipt.get(receipt_id)
        if receipt_evidence is None:
            receipts.append(_pending_receipt(receipt_id=receipt_id, label=label, stage=stage))
            continue
        completed_receipt = _completed_receipt(
            receipt_id=receipt_id,
            label=label,
            stage=stage,
            evidence=receipt_evidence,
        )
        receipts.append(completed_receipt)
        completed_count += 1
    return {
        "bundle_id": "developer_workflow_sandbox_receipt_bundle.v1",
        "workflow_id": "mullu_developer_workflow.v1",
        "workflow_run_id": workflow_run_id,
        "bundle_status": "receipts_complete" if completed_count == len(EXPECTED_RECEIPTS) else "awaiting_receipts",
        "execution_boundary": "local_lab_only",
        "external_effects_allowed": False,
        "rollback_default": True,
        "required_count": len(EXPECTED_RECEIPTS),
        "completed_count": completed_count,
        "receipts": receipts,
    }


def write_developer_workflow_sandbox_receipt_bundle(bundle: Mapping[str, Any], output_path: Path) -> Path:
    """Write a deterministic generated receipt bundle."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _evidence_by_receipt(raw_receipts: object) -> dict[str, Mapping[str, Any]]:
    if isinstance(raw_receipts, Mapping):
        items = raw_receipts.items()
    elif isinstance(raw_receipts, list):
        items = ((str(item.get("receipt_id", "")), item) for item in raw_receipts if isinstance(item, Mapping))
    else:
        raise ValueError("receipts_must_be_object_or_list")
    result: dict[str, Mapping[str, Any]] = {}
    expected_ids = {receipt_id for receipt_id, _, _ in EXPECTED_RECEIPTS}
    for receipt_id, raw_evidence in items:
        normalized_id = str(receipt_id)
        if normalized_id not in expected_ids:
            raise ValueError(f"unknown_receipt_id:{normalized_id}")
        if normalized_id in result:
            raise ValueError(f"duplicate_receipt_id:{normalized_id}")
        if not isinstance(raw_evidence, Mapping):
            raise ValueError(f"receipt_evidence_must_be_object:{normalized_id}")
        result[normalized_id] = raw_evidence
    return result


def _pending_receipt(*, receipt_id: str, label: str, stage: str) -> dict[str, Any]:
    receipt = {
        "receipt_id": receipt_id,
        "label": label,
        "status": "pending",
        "stage": stage,
        "required": True,
        "source": _source(receipt_id),
        "evidence_refs": [],
    }
    for field_name in PENDING_PLACEHOLDER_FIELDS:
        receipt[field_name] = "pending"
    return receipt


def _completed_receipt(
    *,
    receipt_id: str,
    label: str,
    stage: str,
    evidence: Mapping[str, Any],
) -> dict[str, Any]:
    receipt = {
        "receipt_id": receipt_id,
        "label": label,
        "status": "complete",
        "stage": stage,
        "required": True,
        "source": _source(receipt_id),
        "evidence_refs": _required_text_list(evidence.get("evidence_refs"), receipt_id, "evidence_refs"),
    }
    for field_name in PENDING_PLACEHOLDER_FIELDS:
        receipt[field_name] = _required_text(evidence.get(field_name), receipt_id, field_name)
    return receipt


def _required_text(value: object, receipt_id: str, field_name: str) -> str:
    normalized = str(value or "").strip()
    if not normalized or normalized == "pending":
        raise ValueError(f"{receipt_id}.{field_name}_required")
    return normalized


def _required_text_list(value: object, receipt_id: str, field_name: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{receipt_id}.{field_name}_must_be_list")
    normalized = [str(item).strip() for item in value if str(item).strip()]
    if not normalized:
        raise ValueError(f"{receipt_id}.{field_name}_required")
    return normalized


def _text_or_default(value: object, default: str) -> str:
    normalized = str(value or "").strip()
    return normalized or default


def _source(receipt_id: str) -> str:
    return f"workflow_monitor.metadata.developer_workflow_run.receipt_checklist.{receipt_id}"


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"evidence_json_parse_failed:{path}") from exc
    if not isinstance(payload, dict):
        raise ValueError("evidence_json_root_must_be_object")
    return payload


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse builder arguments."""

    parser = argparse.ArgumentParser(description="Build Developer Workflow sandbox receipt bundle.")
    parser.add_argument("--evidence", default=str(DEFAULT_EVIDENCE))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for the receipt bundle builder."""

    args = parse_args(argv)
    try:
        evidence = _load_json_object(Path(args.evidence))
        bundle = build_developer_workflow_sandbox_receipt_bundle(evidence)
        output_path = write_developer_workflow_sandbox_receipt_bundle(bundle, Path(args.output))
        validation = validate_developer_workflow_sandbox_receipt_bundle(bundle_path=output_path)
    except ValueError as exc:
        print(f"DEVELOPER WORKFLOW SANDBOX RECEIPT BUNDLE BUILD INVALID error={exc}")
        return 2
    if not validation.ok:
        print(f"DEVELOPER WORKFLOW SANDBOX RECEIPT BUNDLE BUILD INVALID errors={list(validation.errors)}")
        return 2
    if args.json:
        print(json.dumps(bundle, indent=2, sort_keys=True))
    else:
        print(f"DEVELOPER WORKFLOW SANDBOX RECEIPT BUNDLE BUILT path={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
