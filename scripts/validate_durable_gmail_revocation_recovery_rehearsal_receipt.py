#!/usr/bin/env python3
"""Validate durable Gmail revocation recovery rehearsal receipts.

Purpose: verify that Gmail OAuth revocation recovery has a fresh,
non-destructive invalid-grant rehearsal before recovery claims are reused.
Governance scope: Gmail OAuth failed-refresh handling, revocation recovery,
secret redaction, freshness, and production-claim blocking.
Dependencies: scripts.validate_durable_gmail_oauth_runtime_preflight.
Invariants:
  - Secret-shaped material is never serialized in the validation report.
  - Rehearsal never claims a live destructive provider revocation.
  - Ready rehearsal requires invalid-grant to halt for reauthorization.
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


DEFAULT_RECEIPT_PATH = WORKSPACE_ROOT / ".change_assurance" / "durable_gmail_revocation_recovery_rehearsal_receipt.json"
DEFAULT_MAX_AGE_DAYS = 14
DEFAULT_MAX_FUTURE_SKEW_MINUTES = 5


def validate_revocation_recovery_rehearsal_receipt(
    receipt_path: Path = DEFAULT_RECEIPT_PATH,
    *,
    now: str | None = None,
    max_age_days: int = DEFAULT_MAX_AGE_DAYS,
    max_future_skew_minutes: int = DEFAULT_MAX_FUTURE_SKEW_MINUTES,
) -> dict[str, Any]:
    """Build a redacted validation report for a revocation recovery rehearsal."""

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
            blockers.append("revocation_rehearsal_checked_at_exceeds_future_skew")
        elif age_seconds > max_age_seconds:
            freshness_status = "stale"
            blockers.append("revocation_rehearsal_age_exceeds_max_age")
        else:
            freshness_status = "fresh"
            fresh = True
    elif errors:
        blockers.append("revocation_rehearsal_invalid")

    if receipt and (
        str(receipt.get("status", "")).strip() != "passed"
        or str(receipt.get("solver_outcome", "")).strip() != "SolvedVerified"
    ):
        fresh = False
        blockers.append("revocation_rehearsal_not_passing")

    report = {
        "receipt_id": "durable_gmail_revocation_recovery_rehearsal_validation",
        "validated_receipt_id": str(receipt.get("receipt_id", "")) if receipt else "",
        "validated_adapter_id": str(receipt.get("adapter_id", "")) if receipt else "",
        "receipt_path": _path_label(receipt_path),
        "valid": not errors,
        "fresh": fresh,
        "ready_for_recovery_rehearsal": fresh and not blockers and not errors,
        "freshness_status": freshness_status,
        "checked_at": checked_at_text,
        "now": _timestamp_text(now_dt) if now_dt else "",
        "clock_source": now_source,
        "age_seconds": age_seconds,
        "max_age_seconds": max_age_seconds,
        "max_future_skew_seconds": max_future_skew_seconds,
        "production_ready_claimed": False,
        "destructive_revocation_performed": False,
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
        blockers.append("revocation_rehearsal_receipt_unavailable")
        return {}
    if matched_secret_marker(raw_text):
        errors.append("receipt contains prohibited secret-shaped material")
        blockers.append("revocation_rehearsal_contains_secret_marker")
        return {}
    try:
        payload = json.loads(raw_text, parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError) as exc:
        errors.append(f"receipt JSON invalid: {_safe_error(str(exc))}")
        blockers.append("revocation_rehearsal_json_invalid")
        return {}
    if not isinstance(payload, dict):
        errors.append("receipt must be a JSON object")
        blockers.append("revocation_rehearsal_shape_invalid")
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
        "refresh_failure_case",
        "classified_refresh_status",
        "requires_reauthorization",
        "retryable",
        "recovery_action",
        "refresh_token_storage_ref",
        "revocation_recovery_ref",
        "external_provider_call_performed",
        "destructive_revocation_performed",
        "external_mailbox_write_performed",
        "credential_values_disclosed",
        "production_ready_claimed",
    )
    for field_name in expected_fields:
        if field_name not in receipt:
            errors.append(f"revocation rehearsal receipt missing field: {field_name}")
    if receipt.get("receipt_id") != "durable_gmail_revocation_recovery_rehearsal_receipt":
        errors.append("revocation rehearsal receipt_id mismatch")
    if receipt.get("adapter_id") != "communication.gmail_oauth":
        errors.append("revocation rehearsal adapter_id must be communication.gmail_oauth")
    if receipt.get("connector_id") != "gmail":
        errors.append("revocation rehearsal connector_id must be gmail")
    if receipt.get("mode") != "foundation-local":
        errors.append("revocation rehearsal mode must be foundation-local")
    if receipt.get("refresh_failure_case") != "invalid_grant":
        errors.append("revocation rehearsal refresh_failure_case must be invalid_grant")
    if receipt.get("classified_refresh_status") != "refresh_token_revoked_or_expired":
        errors.append("revocation rehearsal must classify invalid_grant as refresh_token_revoked_or_expired")
    if receipt.get("requires_reauthorization") is not True:
        errors.append("revocation rehearsal must require reauthorization")
    if receipt.get("retryable") is not False:
        errors.append("revocation rehearsal invalid_grant path must not be retryable")
    if receipt.get("recovery_action") != "halt_for_reauthorization":
        errors.append("revocation rehearsal recovery_action must halt for reauthorization")
    if not _is_ref(receipt.get("refresh_token_storage_ref")):
        errors.append("revocation rehearsal refresh_token_storage_ref must be a reference")
    if not _is_ref(receipt.get("revocation_recovery_ref")):
        errors.append("revocation rehearsal revocation_recovery_ref must be a reference")
    if receipt.get("external_provider_call_performed") is not False:
        errors.append("revocation rehearsal must not perform an external provider call")
    if receipt.get("destructive_revocation_performed") is not False:
        errors.append("revocation rehearsal must not claim destructive revocation")
    if receipt.get("external_mailbox_write_performed") is not False:
        errors.append("revocation rehearsal must not perform mailbox writes")
    if receipt.get("credential_values_disclosed") is not False:
        errors.append("revocation rehearsal must not disclose credential values")
    if receipt.get("production_ready_claimed") is not False:
        errors.append("revocation rehearsal must not claim production readiness")
    return errors


def _is_ref(value: object) -> bool:
    return isinstance(value, str) and value.startswith(("receipt:", "witness:", "secret:", "github-actions:"))


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
    if matched_secret_marker(serialized):
        return {
            "receipt_id": "durable_gmail_revocation_recovery_rehearsal_validation",
            "valid": False,
            "fresh": False,
            "ready_for_recovery_rehearsal": False,
            "freshness_status": "invalid",
            "credential_values_disclosed": False,
            "error_count": 1,
            "blocker_count": 1,
            "errors": ["revocation rehearsal validation report contains prohibited material"],
            "blockers": ["revocation_rehearsal_report_contains_prohibited_material"],
        }
    return dict(report)


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(WORKSPACE_ROOT).as_posix()
    except ValueError:
        return path.name


def _safe_error(message: str) -> str:
    marker = matched_secret_marker(message)
    if marker:
        return "redacted parse error"
    return message[:240]


def _safe_os_error(exc: OSError) -> str:
    reason = exc.strerror or exc.__class__.__name__
    return reason[:160]


def main(argv: Sequence[str] | None = None) -> int:
    """Run durable Gmail revocation recovery rehearsal validation."""

    parser = argparse.ArgumentParser(description="Validate durable Gmail revocation recovery rehearsal receipt.")
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT_PATH)
    parser.add_argument("--now", help="ISO-8601 validation time; defaults to env timestamp or UTC now")
    parser.add_argument("--max-age-days", type=int, default=DEFAULT_MAX_AGE_DAYS)
    parser.add_argument("--max-future-skew-minutes", type=int, default=DEFAULT_MAX_FUTURE_SKEW_MINUTES)
    parser.add_argument("--require-ready", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)

    report = validate_revocation_recovery_rehearsal_receipt(
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
    if args.require_ready and not report["ready_for_recovery_rehearsal"]:
        return 1
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
