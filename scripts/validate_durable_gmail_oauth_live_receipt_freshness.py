#!/usr/bin/env python3
"""Validate durable Gmail OAuth live receipt freshness.

Purpose: verify that Gmail OAuth live evidence is recent enough to support a
bounded read-only live-probe claim without reusing stale or skewed receipts.
Governance scope: Gmail OAuth evidence freshness, read-only authority,
secret-redaction, clock skew, and production-claim blocking.
Dependencies: scripts.validate_durable_gmail_oauth_runtime_preflight.
Invariants:
  - Secret-shaped material is never serialized in the validation report.
  - Freshness never promotes write, calendar, customer, or production authority.
  - Missing, stale, future-skewed, or non-passing receipts are explicit blockers.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta
import json
import os
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from scripts.validate_durable_gmail_oauth_runtime_preflight import matched_secret_marker  # noqa: E402


DEFAULT_RECEIPT_PATH = WORKSPACE_ROOT / ".change_assurance" / "durable_gmail_oauth_live_receipt.json"
DEFAULT_MAX_AGE_DAYS = 14
DEFAULT_MAX_FUTURE_SKEW_MINUTES = 5
DURABLE_GMAIL_RECEIPT_ID = "durable_gmail_oauth_live_receipt"
DURABLE_GMAIL_ADAPTER_ID = "communication.gmail_oauth"
EMAIL_CALENDAR_ADAPTER_ID = "communication.email_calendar_worker"


def validate_live_receipt_freshness(
    receipt_path: Path = DEFAULT_RECEIPT_PATH,
    *,
    now: str | None = None,
    max_age_days: int = DEFAULT_MAX_AGE_DAYS,
    max_future_skew_minutes: int = DEFAULT_MAX_FUTURE_SKEW_MINUTES,
) -> dict[str, Any]:
    """Build a bounded freshness validation report for a Gmail evidence receipt."""

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
        errors.extend(_validate_receipt_authority(receipt))

    max_age_seconds = max_age_days * 24 * 60 * 60
    max_future_skew_seconds = max_future_skew_minutes * 60
    age_seconds: int | None = None
    freshness_status = "invalid"
    fresh = False
    if checked_at and now_dt and not errors:
        age_delta = now_dt - checked_at
        age_seconds = int(age_delta.total_seconds())
        allowed_future_time = now_dt + timedelta(seconds=max_future_skew_seconds)
        if checked_at > allowed_future_time:
            freshness_status = "future_clock_skew"
            blockers.append("receipt_checked_at_exceeds_future_skew")
        elif age_seconds > max_age_seconds:
            freshness_status = "stale"
            blockers.append("receipt_age_exceeds_max_age")
        else:
            freshness_status = "fresh"
            fresh = True
    elif errors:
        blockers.append("receipt_freshness_invalid")

    if receipt and _receipt_status_blocks_readiness(receipt):
        fresh = False
        blockers.append("receipt_not_passing_read_only_boundary")

    report = {
        "receipt_id": "durable_gmail_oauth_live_receipt_freshness_validation",
        "validated_receipt_id": str(receipt.get("receipt_id", "")) if receipt else "",
        "validated_adapter_id": str(receipt.get("adapter_id", "")) if receipt else "",
        "receipt_path": _path_label(receipt_path),
        "valid": not errors,
        "fresh": fresh,
        "ready": fresh and not blockers and not errors,
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
        blockers.append("receipt_unavailable")
        return {}
    marker = matched_secret_marker(raw_text)
    if marker:
        errors.append("receipt contains prohibited secret-shaped material")
        blockers.append("receipt_contains_secret_marker")
        return {}
    try:
        payload = json.loads(raw_text, parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError) as exc:
        errors.append(f"receipt JSON invalid: {_safe_error(str(exc))}")
        blockers.append("receipt_json_invalid")
        return {}
    if not isinstance(payload, dict):
        errors.append("receipt must be a JSON object")
        blockers.append("receipt_shape_invalid")
        return {}
    return payload


def _validate_receipt_authority(receipt: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    receipt_id = str(receipt.get("receipt_id", "")).strip()
    adapter_id = str(receipt.get("adapter_id", "")).strip()
    if receipt_id == DURABLE_GMAIL_RECEIPT_ID or adapter_id == DURABLE_GMAIL_ADAPTER_ID:
        if receipt_id != DURABLE_GMAIL_RECEIPT_ID:
            errors.append("durable Gmail receipt_id mismatch")
        if adapter_id != DURABLE_GMAIL_ADAPTER_ID:
            errors.append("durable Gmail adapter_id mismatch")
        if receipt.get("connector_id") != "gmail":
            errors.append("durable Gmail receipt connector_id must be gmail")
        if receipt.get("operation_family") != "read_only_search":
            errors.append("durable Gmail receipt operation_family must be read_only_search")
        if receipt.get("external_mailbox_write_performed") is not False:
            errors.append("durable Gmail receipt must prove no external mailbox write")
        if receipt.get("credential_values_disclosed") is not False:
            errors.append("durable Gmail receipt must prove credential values were not disclosed")
    elif adapter_id == EMAIL_CALENDAR_ADAPTER_ID:
        if receipt.get("external_write") is not False and receipt.get("external_mailbox_write_performed") is not False:
            errors.append("email/calendar receipt must prove no external write")
    else:
        errors.append("receipt is not a recognized Gmail live evidence receipt")
    return errors


def _receipt_status_blocks_readiness(receipt: Mapping[str, Any]) -> bool:
    adapter_id = str(receipt.get("adapter_id", "")).strip()
    if str(receipt.get("status", "")).strip() != "passed":
        return True
    if adapter_id == DURABLE_GMAIL_ADAPTER_ID:
        return str(receipt.get("solver_outcome", "")).strip() != "SolvedVerified"
    if adapter_id == EMAIL_CALENDAR_ADAPTER_ID:
        return str(receipt.get("verification_status", "passed")).strip() != "passed"
    return True


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
    marker = matched_secret_marker(serialized)
    if marker:
        return {
            "receipt_id": "durable_gmail_oauth_live_receipt_freshness_validation",
            "valid": False,
            "fresh": False,
            "ready": False,
            "freshness_status": "invalid",
            "credential_values_disclosed": False,
            "error_count": 1,
            "blocker_count": 1,
            "errors": ["freshness validation report contains prohibited secret-shaped material"],
            "blockers": ["freshness_report_contains_secret_marker"],
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
    marker = matched_secret_marker(safe_message)
    if marker:
        safe_message = safe_message.replace(marker, "<redacted-secret-marker>")
    return safe_message[:240]


def _safe_os_error(exc: OSError) -> str:
    reason = exc.strerror or exc.__class__.__name__
    return reason[:160]


def main(argv: Sequence[str] | None = None) -> int:
    """Run durable Gmail OAuth live receipt freshness validation."""

    parser = argparse.ArgumentParser(description="Validate durable Gmail OAuth live receipt freshness.")
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT_PATH)
    parser.add_argument("--now", help="ISO-8601 validation time; defaults to env timestamp or UTC now")
    parser.add_argument("--max-age-days", type=int, default=DEFAULT_MAX_AGE_DAYS)
    parser.add_argument("--max-future-skew-minutes", type=int, default=DEFAULT_MAX_FUTURE_SKEW_MINUTES)
    parser.add_argument("--require-fresh", action="store_true", help="return non-zero unless receipt is fresh and ready")
    parser.add_argument("--json", action="store_true", help="emit a machine-readable validation receipt")
    args = parser.parse_args(list(argv) if argv is not None else None)

    report = validate_live_receipt_freshness(
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

    if args.require_fresh and not report["ready"]:
        return 1
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
