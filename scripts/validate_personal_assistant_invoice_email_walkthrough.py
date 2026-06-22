#!/usr/bin/env python3
"""Validate the governed invoice/email draft-only walkthrough fixture."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURE = REPO_ROOT / "examples" / "personal_assistant_invoice_email_walkthrough.json"
REQUIRED_FALSE_EFFECT_FIELDS = (
    "execution_allowed",
    "live_connector_execution_allowed",
    "mailbox_read_allowed",
    "mailbox_mutation_allowed",
    "external_send_allowed",
    "provider_draft_creation_allowed",
    "invoice_payment_allowed",
    "money_movement_allowed",
    "connector_mutation_allowed",
    "memory_write_allowed",
    "deployment_mutation_allowed",
    "customer_readiness_claim_allowed",
    "public_launch_claim_allowed",
)
REQUIRED_FALSE_CLAIM_FIELDS = (
    "draft_preview_is_send_authority",
    "approval_review_is_execution",
    "invoice_context_is_payment_authority",
    "console_visibility_is_customer_readiness",
)
REQUIRED_ACTIONS_NOT_TAKEN = (
    "email_not_sent",
    "provider_draft_not_created",
    "connector_state_not_mutated",
    "invoice_not_paid",
    "memory_not_written",
    "deployment_not_mutated",
    "customer_readiness_not_claimed",
)
FORBIDDEN_ACTIONS_TAKEN = (
    "email_sent",
    "provider_draft_created",
    "connector_state_mutated",
    "invoice_paid",
    "memory_written",
    "deployment_mutated",
    "customer_readiness_claimed",
)
SECRET_LIKE_MARKERS = ("sk_live_", "ghp_", "github_pat_", "xoxb-", "Bearer ")


def validate_invoice_email_walkthrough(path: Path = DEFAULT_FIXTURE) -> dict[str, Any]:
    payload = _load_json(path)
    errors: list[str] = []
    if payload.get("schema_version") != "personal_assistant.invoice_email_walkthrough.v1":
        errors.append("schema_version must be personal_assistant.invoice_email_walkthrough.v1")
    for field in ("foundation_only", "governed", "fixture_backed", "read_only"):
        if payload.get(field) is not True:
            errors.append(f"{field} must be true")
    if payload.get("source_demo_packet_id") != "first_usable_demo_packet_v1":
        errors.append("source_demo_packet_id must bind to first_usable_demo_packet_v1")

    effect_boundary = _mapping(payload.get("effect_boundary"))
    for field in REQUIRED_FALSE_EFFECT_FIELDS:
        if effect_boundary.get(field) is not False:
            errors.append(f"effect_boundary.{field} must be false")

    claim_boundary = _mapping(payload.get("claim_boundary"))
    for field in REQUIRED_FALSE_CLAIM_FIELDS:
        if claim_boundary.get(field) is not False:
            errors.append(f"claim_boundary.{field} must be false")

    draft = _mapping(payload.get("draft_projection"))
    if draft.get("skill_id") != "email.response.draft":
        errors.append("draft_projection.skill_id must be email.response.draft")
    if draft.get("status") != "draft_preview_only":
        errors.append("draft_projection.status must be draft_preview_only")
    if draft.get("approval_required_before_send") is not True:
        errors.append("draft_projection.approval_required_before_send must be true")
    for field in (
        "external_send_allowed",
        "mailbox_mutation_allowed",
        "connector_mutation_allowed",
        "provider_draft_creation_allowed",
        "execution_allowed",
    ):
        if draft.get(field) is not False:
            errors.append(f"draft_projection.{field} must be false")

    approval = _mapping(payload.get("approval_review"))
    if approval.get("approval_required") is not True:
        errors.append("approval_review.approval_required must be true")
    if approval.get("approval_is_execution") is not False:
        errors.append("approval_review.approval_is_execution must be false")

    receipt = _mapping(payload.get("receipt_projection"))
    actions_taken = set(_sequence_of_text(receipt.get("actions_taken")))
    actions_not_taken = set(_sequence_of_text(receipt.get("actions_not_taken")))
    for action in REQUIRED_ACTIONS_NOT_TAKEN:
        if action not in actions_not_taken:
            errors.append(f"receipt_projection.actions_not_taken missing {action}")
    for action in FORBIDDEN_ACTIONS_TAKEN:
        if action in actions_taken:
            errors.append(f"receipt_projection.actions_taken must not include {action}")
    if receipt.get("success_claim_allowed") is not False:
        errors.append("receipt_projection.success_claim_allowed must be false")
    if receipt.get("terminal_closure_allowed") is not False:
        errors.append("receipt_projection.terminal_closure_allowed must be false")

    input_projection = _mapping(payload.get("input_projection"))
    if input_projection.get("private_payload_serialized") is not False:
        errors.append("input_projection.private_payload_serialized must be false")
    if input_projection.get("raw_private_payload_serialized") is not False:
        errors.append("input_projection.raw_private_payload_serialized must be false")

    _scan_secret_like_values(payload, errors, path="walkthrough")
    return {
        "path": str(path),
        "valid": not errors,
        "error_count": len(errors),
        "errors": errors,
        "walkthrough_id": payload.get("walkthrough_id", ""),
    }


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("walkthrough fixture must be a JSON object")
    return payload


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _sequence_of_text(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _scan_secret_like_values(value: object, errors: list[str], *, path: str) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            _scan_secret_like_values(child, errors, path=f"{path}.{key}")
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            _scan_secret_like_values(child, errors, path=f"{path}[{index}]")
        return
    if isinstance(value, str) and any(marker in value for marker in SECRET_LIKE_MARKERS):
        errors.append(f"{path} contains a secret-like marker")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = validate_invoice_email_walkthrough(args.path)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        status = "PASS" if result["valid"] else "FAIL"
        print(f"{status} personal-assistant-invoice-email-walkthrough {args.path}")
        for error in result["errors"]:
            print(f"- {error}")
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
