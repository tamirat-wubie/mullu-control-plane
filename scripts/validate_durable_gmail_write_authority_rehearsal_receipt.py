#!/usr/bin/env python3
"""Validate durable Gmail write-authority rehearsal receipts.

Purpose: verify that Gmail write authority remains approval-gated and
tenant-bound before any external draft or send claim can be reused.
Governance scope: Gmail write authority, draft/send split, approval evidence,
tenant-binding references, secret redaction, freshness, and production blocking.
Dependencies: scripts.validate_durable_gmail_oauth_runtime_preflight.
Invariants:
  - Rehearsal never performs or claims a Gmail draft or send.
  - Send authority is blocked in the no-approval rehearsal case.
  - Ready rehearsal never promotes write, Calendar, customer, or production authority.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Mapping, Sequence


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from scripts.validate_durable_gmail_oauth_runtime_preflight import matched_secret_marker  # noqa: E402


DEFAULT_RECEIPT_PATH = WORKSPACE_ROOT / ".change_assurance" / "durable_gmail_write_authority_rehearsal_receipt.json"
DEFAULT_MAX_AGE_DAYS = 14
DEFAULT_MAX_FUTURE_SKEW_MINUTES = 5
EMAIL_ADDRESS_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
SUPPORTED_WRITE_OPERATION_FAMILIES = frozenset({"draft_create", "send_with_approval"})


def validate_write_authority_rehearsal_receipt(
    receipt_path: Path = DEFAULT_RECEIPT_PATH,
    *,
    now: str | None = None,
    max_age_days: int = DEFAULT_MAX_AGE_DAYS,
    max_future_skew_minutes: int = DEFAULT_MAX_FUTURE_SKEW_MINUTES,
) -> dict[str, Any]:
    """Build a redacted validation report for a Gmail write-authority rehearsal."""

    errors: list[str] = []
    blockers: list[str] = []
    receipt: dict[str, Any] = {}
    checked_at_text = ""
    checked_at: datetime | None = None
    now_source = "argument" if now is not None else "runtime_utc_now"
    if now is None and os.environ.get("MULLU_VALIDATION_TIMESTAMP", "").strip():
        now = os.environ["MULLU_VALIDATION_TIMESTAMP"].strip()
        now_source = "MULLU_VALIDATION_TIMESTAMP"

    if max_age_days < 1:
        errors.append("max_age_days must be at least 1")
    if max_future_skew_minutes < 0:
        errors.append("max_future_skew_minutes must be non-negative")

    now_dt = _load_now(now, errors)
    receipt = _load_receipt(receipt_path, errors, blockers)
    if receipt:
        checked_at_text = str(receipt.get("checked_at", "")).strip()
        checked_at = _parse_timestamp(checked_at_text, "checked_at", errors)
        errors.extend(_validate_rehearsal_shape(receipt))

    max_age_seconds = max_age_days * 24 * 60 * 60
    max_future_skew_seconds = max_future_skew_minutes * 60
    age_seconds: int | None = None
    freshness_status = "invalid"
    fresh = False
    if checked_at and now_dt and not errors:
        age_seconds = int((now_dt - checked_at).total_seconds())
        if checked_at > now_dt + timedelta(seconds=max_future_skew_seconds):
            freshness_status = "future_clock_skew"
            blockers.append("gmail_write_rehearsal_checked_at_exceeds_future_skew")
        elif age_seconds > max_age_seconds:
            freshness_status = "stale"
            blockers.append("gmail_write_rehearsal_age_exceeds_max_age")
        else:
            freshness_status = "fresh"
            fresh = True
    elif errors:
        blockers.append("gmail_write_rehearsal_invalid")

    if receipt and (
        str(receipt.get("status", "")).strip() != "passed"
        or str(receipt.get("solver_outcome", "")).strip() != "SolvedVerified"
    ):
        fresh = False
        blockers.append("gmail_write_rehearsal_not_passing")

    report = {
        "receipt_id": "durable_gmail_write_authority_rehearsal_validation",
        "validated_receipt_id": str(receipt.get("receipt_id", "")) if receipt else "",
        "validated_adapter_id": str(receipt.get("adapter_id", "")) if receipt else "",
        "receipt_path": _path_label(receipt_path),
        "valid": not errors,
        "fresh": fresh,
        "ready_for_write_rehearsal": fresh and not blockers and not errors,
        "ready_for_write_authority": False,
        "freshness_status": freshness_status,
        "checked_at": checked_at_text,
        "now": _timestamp_text(now_dt) if now_dt else "",
        "clock_source": now_source,
        "age_seconds": age_seconds,
        "max_age_seconds": max_age_seconds,
        "max_future_skew_seconds": max_future_skew_seconds,
        "approval_required": bool(receipt.get("approval_required")) if receipt else False,
        "draft_send_split_enforced": bool(receipt.get("draft_send_split_enforced")) if receipt else False,
        "production_ready_claimed": False,
        "write_authority_claimed": False,
        "calendar_authority_claimed": False,
        "credential_values_disclosed": False,
        "raw_mailbox_address_disclosed": False,
        "external_draft_created": False,
        "external_send_performed": False,
        "error_count": len(errors),
        "blocker_count": len(blockers),
        "errors": errors,
        "blockers": blockers,
    }
    return _redacted_report(report)


def _load_now(now: str | None, errors: list[str]) -> datetime | None:
    if now is None:
        return datetime.now(UTC)
    return _parse_timestamp(now, "now", errors)


def _load_receipt(path: Path, errors: list[str], blockers: list[str]) -> dict[str, Any]:
    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as exc:
        errors.append(f"receipt load failed: {path.name}: {_safe_os_error(exc)}")
        blockers.append("gmail_write_rehearsal_receipt_unavailable")
        return {}
    if matched_secret_marker(raw_text):
        errors.append("receipt contains prohibited secret-shaped material")
        blockers.append("gmail_write_rehearsal_contains_secret_marker")
        return {}
    if EMAIL_ADDRESS_RE.search(raw_text):
        errors.append("receipt contains raw mailbox address material")
        blockers.append("gmail_write_rehearsal_contains_raw_mailbox_address")
        return {}
    try:
        payload = json.loads(raw_text, parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError) as exc:
        errors.append(f"receipt JSON invalid: {_safe_error(str(exc))}")
        blockers.append("gmail_write_rehearsal_json_invalid")
        return {}
    if not isinstance(payload, dict):
        errors.append("receipt must be a JSON object")
        blockers.append("gmail_write_rehearsal_shape_invalid")
        return {}
    return payload


def _validate_rehearsal_shape(receipt: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    expected_fields = (
        "receipt_id",
        "adapter_id",
        "connector_id",
        "mode",
        "checked_at",
        "status",
        "solver_outcome",
        "operation_family",
        "rehearsal_case",
        "approval_required",
        "approval_gate_result",
        "approval_receipt_ref",
        "account_binding_receipt_ref",
        "source_live_receipt_ref",
        "required_scope_ref",
        "draft_send_split_enforced",
        "send_requires_approval",
        "external_provider_call_performed",
        "external_mailbox_write_performed",
        "external_draft_created",
        "external_send_performed",
        "credential_values_disclosed",
        "production_ready_claimed",
        "write_authority_claimed",
        "calendar_authority_claimed",
    )
    for field_name in expected_fields:
        if field_name not in receipt:
            errors.append(f"Gmail write rehearsal receipt missing field: {field_name}")
    if receipt.get("receipt_id") != "durable_gmail_write_authority_rehearsal_receipt":
        errors.append("Gmail write rehearsal receipt_id mismatch")
    if receipt.get("adapter_id") != "communication.gmail_oauth":
        errors.append("Gmail write rehearsal adapter_id must be communication.gmail_oauth")
    if receipt.get("connector_id") != "gmail":
        errors.append("Gmail write rehearsal connector_id must be gmail")
    if receipt.get("mode") != "foundation-local":
        errors.append("Gmail write rehearsal mode must be foundation-local")
    if receipt.get("operation_family") not in SUPPORTED_WRITE_OPERATION_FAMILIES:
        errors.append("Gmail write rehearsal operation_family must be draft_create or send_with_approval")
    if receipt.get("rehearsal_case") != "send_without_approval_blocked":
        errors.append("Gmail write rehearsal case must be send_without_approval_blocked")
    if receipt.get("approval_required") is not True:
        errors.append("Gmail write rehearsal must require approval")
    if receipt.get("approval_gate_result") != "blocked_without_approval":
        errors.append("Gmail write rehearsal approval gate must block without approval")
    if str(receipt.get("approval_receipt_ref", "")).strip():
        errors.append("Gmail write rehearsal must not attach an approval receipt in the no-approval blocked case")
    if not _is_receipt_ref(receipt.get("account_binding_receipt_ref")):
        errors.append("Gmail write rehearsal account_binding_receipt_ref must be a receipt reference")
    if not _is_receipt_ref(receipt.get("source_live_receipt_ref")):
        errors.append("Gmail write rehearsal source_live_receipt_ref must be a receipt reference")
    if not str(receipt.get("required_scope_ref", "")).startswith("oauth:gmail."):
        errors.append("Gmail write rehearsal required_scope_ref must be a Gmail OAuth scope reference")
    if receipt.get("draft_send_split_enforced") is not True:
        errors.append("Gmail write rehearsal must enforce draft/send split")
    if receipt.get("send_requires_approval") is not True:
        errors.append("Gmail write rehearsal must require approval before send")
    for field_name in (
        "external_provider_call_performed",
        "external_mailbox_write_performed",
        "external_draft_created",
        "external_send_performed",
        "credential_values_disclosed",
        "production_ready_claimed",
        "write_authority_claimed",
        "calendar_authority_claimed",
    ):
        if receipt.get(field_name) is not False:
            errors.append(f"Gmail write rehearsal must keep {field_name} false")
    return errors


def _is_receipt_ref(value: object) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip()
    if not text:
        return False
    if text.startswith(("receipt:", "witness:", "github-actions:")):
        return True
    candidate = Path(text)
    return not candidate.is_absolute() and ".." not in candidate.parts


def _parse_timestamp(value: str, field_name: str, errors: list[str]) -> datetime | None:
    if not value:
        errors.append(f"{field_name} timestamp is required")
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        errors.append(f"{field_name} timestamp must be ISO-8601")
        return None
    if parsed.tzinfo is None:
        errors.append(f"{field_name} timestamp must include timezone")
        return None
    return parsed.astimezone(UTC)


def _timestamp_text(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _reject_json_constant(constant: str) -> None:
    raise ValueError(f"non-finite JSON constant is not allowed: {constant}")


def _redacted_report(report: Mapping[str, Any]) -> dict[str, Any]:
    serialized = json.dumps(report, sort_keys=True)
    if matched_secret_marker(serialized) or EMAIL_ADDRESS_RE.search(serialized):
        return {
            "receipt_id": "durable_gmail_write_authority_rehearsal_validation",
            "valid": False,
            "fresh": False,
            "ready_for_write_rehearsal": False,
            "ready_for_write_authority": False,
            "freshness_status": "invalid",
            "credential_values_disclosed": False,
            "raw_mailbox_address_disclosed": False,
            "error_count": 1,
            "blocker_count": 1,
            "errors": ["Gmail write rehearsal validation report contains prohibited material"],
            "blockers": ["gmail_write_rehearsal_report_contains_prohibited_material"],
        }
    return dict(report)


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(WORKSPACE_ROOT).as_posix()
    except ValueError:
        return path.name


def _safe_error(message: str) -> str:
    safe_message = message
    for path in (WORKSPACE_ROOT, DEFAULT_RECEIPT_PATH):
        safe_message = safe_message.replace(str(path), _path_label(path))
        safe_message = safe_message.replace(str(path.resolve(strict=False)), _path_label(path))
    if matched_secret_marker(safe_message) or EMAIL_ADDRESS_RE.search(safe_message):
        return "redacted parse error"
    return safe_message[:240]


def _safe_os_error(exc: OSError) -> str:
    reason = exc.strerror or exc.__class__.__name__
    return reason[:160]


def main(argv: Sequence[str] | None = None) -> int:
    """Run durable Gmail write-authority rehearsal validation."""

    parser = argparse.ArgumentParser(description="Validate durable Gmail write-authority rehearsal receipt.")
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT_PATH)
    parser.add_argument("--now", help="ISO-8601 validation time; defaults to env timestamp or UTC now")
    parser.add_argument("--max-age-days", type=int, default=DEFAULT_MAX_AGE_DAYS)
    parser.add_argument("--max-future-skew-minutes", type=int, default=DEFAULT_MAX_FUTURE_SKEW_MINUTES)
    parser.add_argument("--require-ready", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)

    report = validate_write_authority_rehearsal_receipt(
        args.receipt,
        now=args.now,
        max_age_days=args.max_age_days,
        max_future_skew_minutes=args.max_future_skew_minutes,
    )
    if args.json:
        sys.stdout.write(json.dumps(report, indent=2, sort_keys=True) + "\n")
    else:
        for blocker in report["blockers"]:
            sys.stderr.write(f"[BLOCKER] {blocker}\n")
        for error in report["errors"]:
            sys.stderr.write(f"[ERROR] {error}\n")
        sys.stdout.write(f"STATUS: {report['freshness_status']}\n")
    if args.require_ready and not report["ready_for_write_rehearsal"]:
        return 1
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
