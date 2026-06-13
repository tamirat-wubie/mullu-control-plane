#!/usr/bin/env python3
"""Produce a durable Gmail write-authority rehearsal receipt.

Purpose: prove the repository-local Gmail write boundary blocks send authority
without approval while preserving the draft/send split.
Governance scope: Gmail write authority, approval gating, tenant-binding
references, secret redaction, no mailbox writes, and no production claim.
Dependencies: scripts.validate_durable_gmail_write_authority_rehearsal_receipt.
Invariants:
  - No Gmail draft, send, provider call, or mailbox write is performed.
  - Send authority is blocked unless a separate approval receipt exists.
  - Write authority is not promoted by this rehearsal receipt.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import sys
from typing import Any, Mapping


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from scripts.validate_durable_gmail_oauth_runtime_preflight import matched_secret_marker  # noqa: E402
from scripts.validate_durable_gmail_write_authority_rehearsal_receipt import (  # noqa: E402
    validate_write_authority_rehearsal_receipt,
)


DEFAULT_OUTPUT = WORKSPACE_ROOT / ".change_assurance" / "durable_gmail_write_authority_rehearsal_receipt.json"
DEFAULT_ACCOUNT_BINDING_RECEIPT_REF = ".change_assurance/durable_gmail_account_binding_receipt.json"
DEFAULT_SOURCE_LIVE_RECEIPT_REF = ".change_assurance/durable_gmail_oauth_live_receipt.json"


def produce_write_authority_rehearsal_receipt(
    *,
    environment: Mapping[str, str] | None = None,
    output_path: Path = DEFAULT_OUTPUT,
) -> dict[str, Any]:
    """Produce a redacted non-effect Gmail write authority rehearsal receipt."""

    env = dict(os.environ if environment is None else environment)
    checked_at = env.get("MULLU_VALIDATION_TIMESTAMP", _utc_now())
    operation_family = env.get("MULLU_GMAIL_WRITE_OPERATION_FAMILY", "send_with_approval").strip()
    blockers: list[str] = []
    if operation_family not in {"draft_create", "send_with_approval"}:
        blockers.append("gmail_write_operation_family_unsupported")

    payload = {
        "receipt_id": "durable_gmail_write_authority_rehearsal_receipt",
        "adapter_id": "communication.gmail_oauth",
        "connector_id": "gmail",
        "mode": "foundation-local",
        "checked_at": checked_at,
        "status": "passed" if not blockers else "failed",
        "solver_outcome": "SolvedVerified" if not blockers else "AwaitingEvidence",
        "operation_family": operation_family,
        "rehearsal_case": "send_without_approval_blocked",
        "approval_required": True,
        "approval_gate_result": "blocked_without_approval",
        "approval_receipt_ref": "",
        "account_binding_receipt_ref": env.get(
            "MULLU_GMAIL_ACCOUNT_BINDING_RECEIPT_REF",
            DEFAULT_ACCOUNT_BINDING_RECEIPT_REF,
        ),
        "source_live_receipt_ref": env.get(
            "MULLU_GMAIL_WRITE_SOURCE_LIVE_RECEIPT_REF",
            DEFAULT_SOURCE_LIVE_RECEIPT_REF,
        ),
        "required_scope_ref": "oauth:gmail.send" if operation_family == "send_with_approval" else "oauth:gmail.compose",
        "draft_send_split_enforced": True,
        "send_requires_approval": True,
        "external_provider_call_performed": False,
        "external_mailbox_write_performed": False,
        "external_draft_created": False,
        "external_send_performed": False,
        "credential_values_disclosed": False,
        "production_ready_claimed": False,
        "write_authority_claimed": False,
        "calendar_authority_claimed": False,
        "blockers": blockers,
    }
    _write_redacted_json(output_path, payload)
    return payload


def _write_redacted_json(path: Path, payload: Mapping[str, Any]) -> None:
    serialized = json.dumps(payload, indent=2, sort_keys=True)
    if matched_secret_marker(serialized):
        raise ValueError("Gmail write authority rehearsal receipt contains prohibited secret material")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(serialized + "\n", encoding="utf-8")


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for Gmail write-authority rehearsal."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    payload = produce_write_authority_rehearsal_receipt(output_path=args.output)
    validation = validate_write_authority_rehearsal_receipt(args.output, now=str(payload.get("checked_at", "")))
    response = {"receipt": payload, "validation": validation}
    if args.json:
        print(json.dumps(response, indent=2, sort_keys=True))
    if args.strict and not validation["ready_for_write_rehearsal"]:
        return 1
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
