#!/usr/bin/env python3
"""Validate terminal approval receipts for general-agent promotion.

Purpose: certify that approval-bound terminal certificate gate items use
explicit approval refs without serializing secret or approval values.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: schemas/general_agent_promotion_terminal_approvals.schema.json.
Invariants:
  - Approval receipts are evidence refs, not execution grants.
  - Approval refs are scoped to terminal_certificate_gate.
  - Serialized secret or approval values fail closed.
  - Duplicate source action approvals fail closed.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402

DEFAULT_RECEIPT = REPO_ROOT / ".change_assurance" / "general_agent_promotion_terminal_approvals.json"
DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "general_agent_promotion_terminal_approvals.schema.json"
RECEIPT_ID = "general-agent-promotion-terminal-approvals-v1"
TERMINAL_CERTIFICATE_GATE_SCHEMA_ID = (
    "urn:mullusi:schema:general-agent-promotion-terminal-certificate-gate:1"
)


@dataclass(frozen=True, slots=True)
class TerminalApprovalReceiptValidation:
    """Validation result and approved-ref projection for terminal approvals."""

    valid: bool
    present: bool
    receipt_path: str
    schema_path: str
    receipt_id: str
    approval_count: int
    approved_count: int
    approved_refs_by_action: dict[str, str]
    duplicate_source_action_ids: tuple[str, ...]
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        """Return deterministic JSON-ready validation output."""
        payload = asdict(self)
        payload["duplicate_source_action_ids"] = list(self.duplicate_source_action_ids)
        payload["errors"] = list(self.errors)
        return payload


def validate_general_agent_promotion_terminal_approvals(
    *,
    receipt_path: Path = DEFAULT_RECEIPT,
    schema_path: Path = DEFAULT_SCHEMA,
    allow_missing: bool = False,
) -> TerminalApprovalReceiptValidation:
    """Validate one terminal approval receipt and return approved refs by action."""
    if not receipt_path.exists():
        return TerminalApprovalReceiptValidation(
            valid=False,
            present=False,
            receipt_path=str(receipt_path),
            schema_path=str(schema_path),
            receipt_id="",
            approval_count=0,
            approved_count=0,
            approved_refs_by_action={},
            duplicate_source_action_ids=(),
            errors=() if allow_missing else ("approval_receipt_missing",),
        )

    payload = _load_json_object(receipt_path)
    if payload is None:
        return TerminalApprovalReceiptValidation(
            valid=False,
            present=True,
            receipt_path=str(receipt_path),
            schema_path=str(schema_path),
            receipt_id="",
            approval_count=0,
            approved_count=0,
            approved_refs_by_action={},
            duplicate_source_action_ids=(),
            errors=("approval_receipt_invalid",),
        )

    schema = _load_schema(schema_path)
    schema_errors = tuple(
        f"approval_receipt_schema:{error}" for error in _validate_schema_instance(schema, payload)
    )
    semantic_errors, approved_refs, duplicate_ids = _semantic_validation(payload)
    errors = schema_errors + semantic_errors
    if errors:
        approved_refs = {}
    return TerminalApprovalReceiptValidation(
        valid=not errors,
        present=True,
        receipt_path=str(receipt_path),
        schema_path=str(schema_path),
        receipt_id=str(payload.get("receipt_id", "")),
        approval_count=_approval_count(payload),
        approved_count=len(approved_refs),
        approved_refs_by_action=approved_refs,
        duplicate_source_action_ids=duplicate_ids,
        errors=errors,
    )


def _semantic_validation(payload: dict[str, Any]) -> tuple[tuple[str, ...], dict[str, str], tuple[str, ...]]:
    errors: list[str] = []
    approved_refs: dict[str, str] = {}
    duplicate_ids: list[str] = []
    seen_action_ids: set[str] = set()
    if payload.get("schema_version") != 1:
        errors.append("approval_receipt_schema_version_must_be_1")
    if payload.get("receipt_id") != RECEIPT_ID:
        errors.append("approval_receipt_id_invalid")
    if payload.get("secret_serialization") != "forbidden":
        errors.append("approval_receipt_secret_serialization_must_be_forbidden")
    metadata = payload.get("metadata", {})
    if not isinstance(metadata, dict):
        errors.append("approval_receipt_metadata_must_be_object")
    else:
        if metadata.get("secret_values_serialized") is not False:
            errors.append("approval_receipt_metadata_secret_values_serialized_must_be_false")
        if metadata.get("approval_values_are_refs") is not True:
            errors.append("approval_receipt_metadata_approval_values_are_refs_must_be_true")
        if metadata.get("terminal_certificate_gate_schema_id") != TERMINAL_CERTIFICATE_GATE_SCHEMA_ID:
            errors.append("approval_receipt_metadata_terminal_gate_schema_id_invalid")

    approval_items = payload.get("approvals", ())
    if not isinstance(approval_items, list):
        errors.append("approval_receipt_approvals_must_be_list")
        return tuple(errors), {}, ()
    for index, item in enumerate(approval_items, start=1):
        if not isinstance(item, dict):
            errors.append(f"approval_receipt_entry_{index}_must_be_object")
            continue
        source_action_id = str(item.get("source_action_id", "")).strip()
        approval_ref = str(item.get("approval_ref", "")).strip()
        if not source_action_id:
            errors.append(f"approval_receipt_entry_{index}_missing_source_action_id")
            continue
        if source_action_id in seen_action_ids:
            duplicate_ids.append(source_action_id)
            errors.append(f"approval_receipt_entry_{index}_duplicate_source_action_id:{source_action_id}")
            continue
        seen_action_ids.add(source_action_id)
        if item.get("scope") != "terminal_certificate_gate":
            errors.append(f"approval_receipt_entry_{index}_scope_must_be_terminal_certificate_gate")
            continue
        if item.get("value_serialized") is not False:
            errors.append(f"approval_receipt_entry_{index}_value_serialized_must_be_false")
            continue
        if item.get("approved") is not True:
            errors.append(f"approval_receipt_entry_{index}_not_approved")
            continue
        if not approval_ref:
            errors.append(f"approval_receipt_entry_{index}_missing_approval_ref")
            continue
        if not approval_ref.startswith("approval://"):
            errors.append(f"approval_receipt_entry_{index}_approval_ref_must_use_approval_uri")
            continue
        approved_refs[source_action_id] = approval_ref
    return tuple(errors), approved_refs, tuple(sorted(set(duplicate_ids)))


def _approval_count(payload: dict[str, Any]) -> int:
    approvals = payload.get("approvals", ())
    return len(approvals) if isinstance(approvals, list) else 0


def _load_json_object(path: Path) -> dict[str, Any] | None:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse terminal approval receipt validation arguments."""
    parser = argparse.ArgumentParser(description="Validate general-agent promotion terminal approvals.")
    parser.add_argument("--receipt", default=str(DEFAULT_RECEIPT))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--allow-missing", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for terminal approval receipt validation."""
    args = parse_args(argv)
    result = validate_general_agent_promotion_terminal_approvals(
        receipt_path=Path(args.receipt),
        schema_path=Path(args.schema),
        allow_missing=args.allow_missing,
    )
    if args.json:
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    elif result.valid:
        print(f"general-agent promotion terminal approvals ok approvals={result.approved_count}")
    elif args.allow_missing and not result.present:
        print("general-agent promotion terminal approvals absent")
    else:
        for error in result.errors:
            print(f"error: {error}")
    return 0 if result.valid or (args.allow_missing and not result.present) else 2


if __name__ == "__main__":
    raise SystemExit(main())
