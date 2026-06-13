#!/usr/bin/env python3
"""Validate durable Gmail account binding receipts.

Purpose: verify that a Gmail OAuth live evidence path is bound to the expected
tenant and mailbox account without serializing mailbox addresses or secrets.
Governance scope: Gmail account binding, tenant boundary, profile-probe
evidence, secret redaction, freshness, and production-claim blocking.
Dependencies: scripts.validate_durable_gmail_oauth_runtime_preflight.
Invariants:
  - Raw mailbox addresses and token-shaped values are never serialized.
  - Binding requires matching expected and observed account hashes.
  - Account binding never promotes Gmail write, Calendar, customer, or
    production authority.
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


DEFAULT_RECEIPT_PATH = WORKSPACE_ROOT / ".change_assurance" / "durable_gmail_account_binding_receipt.json"
DEFAULT_MAX_AGE_DAYS = 14
DEFAULT_MAX_FUTURE_SKEW_MINUTES = 5
ACCOUNT_BINDING_RECEIPT_ID = "durable_gmail_account_binding_receipt"
GMAIL_OAUTH_ADAPTER_ID = "communication.gmail_oauth"
SHA256_HEX_RE = re.compile(r"^[a-f0-9]{64}$")
EMAIL_ADDRESS_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)


def validate_account_binding_receipt(
    receipt_path: Path = DEFAULT_RECEIPT_PATH,
    *,
    now: str | None = None,
    max_age_days: int = DEFAULT_MAX_AGE_DAYS,
    max_future_skew_minutes: int = DEFAULT_MAX_FUTURE_SKEW_MINUTES,
) -> dict[str, Any]:
    """Build a redacted account-binding validation report."""

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
        errors.extend(_validate_binding_shape(receipt))

    max_age_seconds = max_age_days * 24 * 60 * 60
    max_future_skew_seconds = max_future_skew_minutes * 60
    age_seconds: int | None = None
    freshness_status = "invalid"
    fresh = False
    if checked_at and now_dt and not errors:
        age_seconds = int((now_dt - checked_at).total_seconds())
        if checked_at > now_dt + timedelta(seconds=max_future_skew_seconds):
            freshness_status = "future_clock_skew"
            blockers.append("account_binding_checked_at_exceeds_future_skew")
        elif age_seconds > max_age_seconds:
            freshness_status = "stale"
            blockers.append("account_binding_age_exceeds_max_age")
        else:
            freshness_status = "fresh"
            fresh = True
    elif errors:
        blockers.append("account_binding_invalid")

    if receipt and _receipt_status_blocks_readiness(receipt):
        fresh = False
        blockers.append("account_binding_not_passing")
    if receipt and receipt.get("expected_account_hash") != receipt.get("observed_account_hash"):
        fresh = False
        blockers.append("account_hash_mismatch")

    report = {
        "receipt_id": "durable_gmail_account_binding_validation",
        "validated_receipt_id": str(receipt.get("receipt_id", "")) if receipt else "",
        "validated_adapter_id": str(receipt.get("adapter_id", "")) if receipt else "",
        "receipt_path": _path_label(receipt_path),
        "valid": not errors,
        "fresh": fresh,
        "ready_for_tenant_binding": fresh and not blockers and not errors,
        "freshness_status": freshness_status,
        "checked_at": checked_at_text,
        "now": _timestamp_text(now_dt) if now_dt else "",
        "clock_source": now_source,
        "age_seconds": age_seconds,
        "max_age_seconds": max_age_seconds,
        "max_future_skew_seconds": max_future_skew_seconds,
        "production_ready_claimed": False,
        "write_authority_claimed": False,
        "calendar_authority_claimed": False,
        "credential_values_disclosed": False,
        "raw_mailbox_address_disclosed": False,
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
        blockers.append("account_binding_receipt_unavailable")
        return {}
    if matched_secret_marker(raw_text):
        errors.append("receipt contains prohibited secret-shaped material")
        blockers.append("account_binding_contains_secret_marker")
        return {}
    if EMAIL_ADDRESS_RE.search(raw_text):
        errors.append("receipt contains raw mailbox address material")
        blockers.append("account_binding_contains_raw_mailbox_address")
        return {}
    try:
        payload = json.loads(raw_text, parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError) as exc:
        errors.append(f"receipt JSON invalid: {_safe_error(str(exc))}")
        blockers.append("account_binding_json_invalid")
        return {}
    if not isinstance(payload, dict):
        errors.append("receipt must be a JSON object")
        blockers.append("account_binding_shape_invalid")
        return {}
    return payload


def _validate_binding_shape(receipt: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    expected_fields = (
        "receipt_id",
        "adapter_id",
        "connector_id",
        "tenant_ref",
        "expected_account_hash",
        "observed_account_hash",
        "hash_algorithm",
        "hash_salt_ref",
        "source_receipt_ref",
        "account_profile_probe_performed",
        "external_provider_call_performed",
        "external_mailbox_write_performed",
        "credential_values_disclosed",
        "checked_at",
        "status",
        "solver_outcome",
    )
    for field_name in expected_fields:
        if field_name not in receipt:
            errors.append(f"account binding receipt missing field: {field_name}")
    if receipt.get("receipt_id") != ACCOUNT_BINDING_RECEIPT_ID:
        errors.append("account binding receipt_id mismatch")
    if receipt.get("adapter_id") != GMAIL_OAUTH_ADAPTER_ID:
        errors.append("account binding adapter_id must be communication.gmail_oauth")
    if receipt.get("connector_id") != "gmail":
        errors.append("account binding connector_id must be gmail")
    if not str(receipt.get("tenant_ref", "")).strip():
        errors.append("account binding tenant_ref is required")
    for field_name in ("expected_account_hash", "observed_account_hash"):
        value = str(receipt.get(field_name, "")).strip()
        if not SHA256_HEX_RE.fullmatch(value):
            errors.append(f"{field_name} must be lowercase sha256 hex")
    if receipt.get("hash_algorithm") != "sha256":
        errors.append("account binding hash_algorithm must be sha256")
    if not str(receipt.get("hash_salt_ref", "")).startswith(("secret:", "witness:", "receipt:")):
        errors.append("account binding hash_salt_ref must be a ref, not a salt value")
    if not str(receipt.get("source_receipt_ref", "")).strip():
        errors.append("account binding source_receipt_ref is required")
    if receipt.get("account_profile_probe_performed") is not True:
        errors.append("account binding must prove profile probe was performed")
    if receipt.get("external_provider_call_performed") is not True:
        errors.append("account binding must prove provider profile call was performed")
    if receipt.get("external_mailbox_write_performed") is not False:
        errors.append("account binding must prove no external mailbox write")
    if receipt.get("credential_values_disclosed") is not False:
        errors.append("account binding must prove credential values were not disclosed")
    return errors


def _receipt_status_blocks_readiness(receipt: Mapping[str, Any]) -> bool:
    return (
        str(receipt.get("status", "")).strip() != "passed"
        or str(receipt.get("solver_outcome", "")).strip() != "SolvedVerified"
    )


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
            "receipt_id": "durable_gmail_account_binding_validation",
            "valid": False,
            "fresh": False,
            "ready_for_tenant_binding": False,
            "freshness_status": "invalid",
            "credential_values_disclosed": False,
            "raw_mailbox_address_disclosed": False,
            "error_count": 1,
            "blocker_count": 1,
            "errors": ["account binding validation report contains prohibited material"],
            "blockers": ["account_binding_report_contains_prohibited_material"],
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
    """Run durable Gmail account binding receipt validation."""

    parser = argparse.ArgumentParser(description="Validate durable Gmail account binding receipt.")
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT_PATH)
    parser.add_argument("--now", help="ISO-8601 validation time; defaults to env timestamp or UTC now")
    parser.add_argument("--max-age-days", type=int, default=DEFAULT_MAX_AGE_DAYS)
    parser.add_argument("--max-future-skew-minutes", type=int, default=DEFAULT_MAX_FUTURE_SKEW_MINUTES)
    parser.add_argument("--require-bound", action="store_true", help="return non-zero unless account binding is ready")
    parser.add_argument("--json", action="store_true", help="emit a machine-readable validation receipt")
    args = parser.parse_args(list(argv) if argv is not None else None)

    report = validate_account_binding_receipt(
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

    if args.require_bound and not report["ready_for_tenant_binding"]:
        return 1
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
