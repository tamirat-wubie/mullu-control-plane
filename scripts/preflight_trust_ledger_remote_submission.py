#!/usr/bin/env python3
"""Preflight trust-ledger remote anchor submission readiness.

Purpose: verify the operator, export, ledger, and remote configuration surface
before any HTTPS transparency-log submission or local submission-ledger append.
Governance scope: read-only anchor export replay, operator authority checks,
remote endpoint admission, and schema-backed readiness receipts.
Dependencies: trust-ledger anchor verifier, submission ledger verifier, and
remote submission receipt schema validation.
Invariants:
  - Preflight never appends to the local submission ledger.
  - Preflight never posts to the remote transparency log.
  - Secret values are never emitted; only presence is witnessed.
  - Tampered exports and invalid ledgers block as GovernanceBlocked.
  - Missing live credentials remain explicit as AwaitingEvidence.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.submit_trust_ledger_anchor_export import (  # noqa: E402
    MAX_REMOTE_TIMEOUT_SECONDS,
    _authority_ref_allowed,
    _operator_id_allowed,
    _stable_hash,
    _validate_remote_submit_url,
    verify_submission_ledger,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402
from scripts.verify_anchor_receipt import verify_anchor_receipt_files  # noqa: E402


PREFLIGHT_SCHEMA_PATH = REPO_ROOT / "schemas" / "trust_ledger_remote_submission_preflight.schema.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "trust_ledger_remote_submission_preflight.json"


@dataclass(frozen=True, slots=True)
class TrustLedgerRemoteSubmissionPreflightStep:
    """One read-only trust-ledger remote submission preflight check."""

    name: str
    passed: bool
    detail: str

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable preflight step."""
        return asdict(self)


@dataclass(frozen=True, slots=True)
class TrustLedgerRemoteSubmissionPreflightReport:
    """Full trust-ledger remote submission preflight report."""

    schema_version: int
    receipt_id: str
    checked_at: str
    ready: bool
    outcome: str
    operator_id: str
    authority_ref: str
    remote_submit_url: str
    remote_submit_host: str
    remote_timeout_seconds: float
    remote_api_token_present: bool
    verification_secret_present: bool
    submission_secret_present: bool
    signature_key_id_present: bool
    ledger_path: str
    step_count: int
    steps: tuple[TrustLedgerRemoteSubmissionPreflightStep, ...]
    blockers: tuple[str, ...]
    hard_blockers: tuple[str, ...]
    anchor_verification: dict[str, Any]
    ledger_state: dict[str, Any]
    metadata: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable preflight report."""
        return {
            "schema_version": self.schema_version,
            "receipt_id": self.receipt_id,
            "checked_at": self.checked_at,
            "ready": self.ready,
            "outcome": self.outcome,
            "operator_id": self.operator_id,
            "authority_ref": self.authority_ref,
            "remote_submit_url": self.remote_submit_url,
            "remote_submit_host": self.remote_submit_host,
            "remote_timeout_seconds": self.remote_timeout_seconds,
            "remote_api_token_present": self.remote_api_token_present,
            "verification_secret_present": self.verification_secret_present,
            "submission_secret_present": self.submission_secret_present,
            "signature_key_id_present": self.signature_key_id_present,
            "ledger_path": self.ledger_path,
            "step_count": self.step_count,
            "steps": [step.as_dict() for step in self.steps],
            "blockers": list(self.blockers),
            "hard_blockers": list(self.hard_blockers),
            "anchor_verification": self.anchor_verification,
            "ledger_state": self.ledger_state,
            "metadata": self.metadata,
        }


def preflight_trust_ledger_remote_submission(
    *,
    bundle_path: Path,
    receipt_path: Path,
    artifacts_path: Path,
    package_path: Path,
    ledger_path: Path,
    operator_id: str,
    authority_ref: str,
    submitted_at: str,
    verification_secret: str,
    submission_secret: str,
    signature_key_id: str,
    remote_submit_url: str,
    remote_api_token: str,
    remote_timeout_seconds: float = 10.0,
    checked_at: str = "2026-05-05T12:20:00+00:00",
    strict: bool = False,
) -> TrustLedgerRemoteSubmissionPreflightReport:
    """Return read-only readiness for a future remote anchor submission."""
    steps: list[TrustLedgerRemoteSubmissionPreflightStep] = []
    hard_blockers: list[str] = []

    def add_step(name: str, passed: bool, detail: str, *, hard_block: bool = False) -> None:
        steps.append(TrustLedgerRemoteSubmissionPreflightStep(name=name, passed=passed, detail=detail))
        if not passed and hard_block:
            hard_blockers.append(name)

    operator_valid = _operator_id_allowed(operator_id)
    add_step(
        "operator_identity",
        operator_valid,
        "operator_id_present=true" if operator_valid else "operator_id_missing_or_unbounded",
    )

    authority_valid = _authority_ref_allowed(authority_ref)
    add_step(
        "authority_ref",
        authority_valid,
        "authority_ref_valid=true" if authority_valid else "authority_ref_invalid",
        hard_block=bool(authority_ref),
    )

    submitted_at_valid = _date_time_valid(submitted_at)
    add_step(
        "submitted_at",
        submitted_at_valid,
        "submitted_at_valid=true" if submitted_at_valid else "submitted_at_missing_or_invalid",
        hard_block=bool(submitted_at),
    )

    remote_url_reason = _validate_remote_submit_url(remote_submit_url) if remote_submit_url else "remote_submit_url_required"
    remote_url_valid = remote_url_reason == ""
    add_step(
        "remote_submit_url",
        remote_url_valid,
        "remote_submit_url_valid=true" if remote_url_valid else remote_url_reason,
        hard_block=bool(remote_submit_url),
    )

    remote_token_present = bool(remote_api_token)
    add_step(
        "remote_api_token",
        remote_token_present,
        "remote_api_token_present=true" if remote_token_present else "remote_api_token_required",
    )

    timeout_valid = 0 < remote_timeout_seconds <= MAX_REMOTE_TIMEOUT_SECONDS
    add_step(
        "remote_timeout_seconds",
        timeout_valid,
        (
            f"remote_timeout_seconds={remote_timeout_seconds}"
            if timeout_valid
            else f"remote_timeout_seconds_invalid max={MAX_REMOTE_TIMEOUT_SECONDS}"
        ),
        hard_block=True,
    )

    verification_secret_present = bool(verification_secret)
    add_step(
        "verification_secret",
        verification_secret_present,
        "verification_secret_present=true" if verification_secret_present else "verification_secret_required",
    )

    submission_secret_present = bool(submission_secret)
    add_step(
        "submission_secret",
        submission_secret_present,
        "submission_secret_present=true" if submission_secret_present else "submission_secret_required",
    )

    signature_key_id_present = bool(signature_key_id)
    add_step(
        "signature_key_id",
        signature_key_id_present,
        "signature_key_id_present=true" if signature_key_id_present else "signature_key_id_required",
    )

    anchor_verification = verify_anchor_receipt_files(
        bundle_path=bundle_path,
        receipt_path=receipt_path,
        artifacts_path=artifacts_path,
        package_path=package_path,
        signing_secret=verification_secret,
        strict=strict,
    )
    anchor_ready = (
        anchor_verification.get("valid") is True
        and anchor_verification.get("package_present") is True
        and anchor_verification.get("package_valid") is True
    )
    add_step(
        "anchor_export_verification",
        anchor_ready,
        (
            "anchor_export_verified=true "
            f"bundle_id={anchor_verification.get('bundle_id', '')} "
            f"anchor_receipt_id={anchor_verification.get('anchor_receipt_id', '')}"
            if anchor_ready
            else f"anchor_export_verification_failed:{anchor_verification.get('reason', 'unknown')}"
        ),
        hard_block=verification_secret_present,
    )

    ledger_state = verify_submission_ledger(ledger_path=ledger_path, signing_secret=submission_secret)
    ledger_ready = ledger_state.get("valid") is True
    add_step(
        "submission_ledger_replay",
        ledger_ready,
        (
            f"ledger_replay_valid=true submission_count={ledger_state.get('submission_count', 0)}"
            if ledger_ready
            else f"ledger_replay_failed:{ledger_state.get('reason', 'unknown')}"
        ),
        hard_block=True,
    )

    blockers = tuple(step.name for step in steps if not step.passed)
    ready = not blockers
    outcome = _outcome(ready=ready, hard_blockers=tuple(hard_blockers))
    remote_submit_host = _remote_submit_host(remote_submit_url) if remote_url_valid else ""
    metadata = {
        "preflight_only": True,
        "remote_submit_executed": False,
        "ledger_append_executed": False,
        "requires_operator_confirmation_for_submit": True,
    }
    unsigned_report = {
        "schema_version": 1,
        "checked_at": checked_at,
        "ready": ready,
        "outcome": outcome,
        "operator_id": operator_id,
        "authority_ref": authority_ref,
        "remote_submit_url": remote_submit_url,
        "remote_submit_host": remote_submit_host,
        "remote_timeout_seconds": remote_timeout_seconds,
        "ledger_path": str(ledger_path),
        "blockers": list(blockers),
        "hard_blockers": list(hard_blockers),
        "anchor_verification_reason": str(anchor_verification.get("reason", "")),
        "ledger_state_reason": str(ledger_state.get("reason", "")),
    }
    receipt_id = f"trust-ledger-remote-submission-preflight-{_stable_hash(unsigned_report)[:16]}"
    return TrustLedgerRemoteSubmissionPreflightReport(
        schema_version=1,
        receipt_id=receipt_id,
        checked_at=checked_at,
        ready=ready,
        outcome=outcome,
        operator_id=operator_id,
        authority_ref=authority_ref,
        remote_submit_url=remote_submit_url,
        remote_submit_host=remote_submit_host,
        remote_timeout_seconds=remote_timeout_seconds,
        remote_api_token_present=remote_token_present,
        verification_secret_present=verification_secret_present,
        submission_secret_present=submission_secret_present,
        signature_key_id_present=signature_key_id_present,
        ledger_path=str(ledger_path),
        step_count=len(steps),
        steps=tuple(steps),
        blockers=blockers,
        hard_blockers=tuple(hard_blockers),
        anchor_verification=anchor_verification,
        ledger_state=ledger_state,
        metadata=metadata,
    )


def write_trust_ledger_remote_submission_preflight_report(
    report: TrustLedgerRemoteSubmissionPreflightReport,
    output_path: Path,
) -> Path:
    """Write one schema-checked remote submission preflight report."""
    payload = report.as_dict()
    schema_errors = _validate_schema_instance(_load_schema(PREFLIGHT_SCHEMA_PATH), payload)
    if schema_errors:
        raise RuntimeError(
            "trust_ledger_remote_submission_preflight_schema_validation_failed:"
            + ";".join(schema_errors[:10])
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _date_time_valid(value: str) -> bool:
    if not value:
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _remote_submit_host(value: str) -> str:
    try:
        return urllib.parse.urlparse(value).hostname or ""
    except ValueError:
        return ""


def _outcome(*, ready: bool, hard_blockers: tuple[str, ...]) -> str:
    if ready:
        return "SolvedVerified"
    if hard_blockers:
        return "GovernanceBlocked"
    return "AwaitingEvidence"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse remote submission preflight arguments."""
    parser = argparse.ArgumentParser(description="Preflight trust-ledger remote submission readiness.")
    parser.add_argument("--bundle", required=True, type=Path, help="Path to trust-ledger bundle JSON")
    parser.add_argument("--receipt", required=True, type=Path, help="Path to external anchor receipt JSON")
    parser.add_argument("--artifacts", required=True, type=Path, help="Path to evidence artifact array JSON")
    parser.add_argument("--package", required=True, type=Path, help="Path to trust-ledger export package JSON")
    parser.add_argument("--ledger-path", required=True, type=Path, help="Append-only submission ledger JSONL path")
    parser.add_argument("--operator-id", default=os.environ.get("MULLU_OPERATOR_ID", ""))
    parser.add_argument(
        "--authority-ref",
        default=os.environ.get("MULLU_TRUST_LEDGER_SUBMISSION_AUTHORITY_REF", ""),
    )
    parser.add_argument("--submitted-at", default=os.environ.get("MULLU_TRUST_LEDGER_SUBMITTED_AT", ""))
    parser.add_argument(
        "--verification-secret",
        default=os.environ.get("MULLU_TRUST_LEDGER_ANCHOR_SECRET", ""),
    )
    parser.add_argument(
        "--submission-secret",
        default=os.environ.get("MULLU_TRUST_LEDGER_SUBMISSION_SECRET", ""),
    )
    parser.add_argument(
        "--signature-key-id",
        default=os.environ.get("MULLU_TRUST_LEDGER_SUBMISSION_KEY_ID", "anchor-submission-key"),
    )
    parser.add_argument(
        "--remote-submit-url",
        default=os.environ.get("MULLU_TRUST_LEDGER_REMOTE_SUBMISSION_URL", ""),
    )
    parser.add_argument(
        "--remote-api-token",
        default=os.environ.get("MULLU_TRUST_LEDGER_REMOTE_SUBMISSION_TOKEN", ""),
    )
    parser.add_argument("--remote-timeout-seconds", type=float, default=10.0)
    parser.add_argument("--checked-at", default="2026-05-05T12:20:00+00:00")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when preflight is not ready")
    parser.add_argument("--json", action="store_true", help="Print JSON report")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for remote submission preflight."""
    args = parse_args(argv)
    report = preflight_trust_ledger_remote_submission(
        bundle_path=args.bundle,
        receipt_path=args.receipt,
        artifacts_path=args.artifacts,
        package_path=args.package,
        ledger_path=args.ledger_path,
        operator_id=args.operator_id,
        authority_ref=args.authority_ref,
        submitted_at=args.submitted_at,
        verification_secret=args.verification_secret,
        submission_secret=args.submission_secret,
        signature_key_id=args.signature_key_id,
        remote_submit_url=args.remote_submit_url,
        remote_api_token=args.remote_api_token,
        remote_timeout_seconds=args.remote_timeout_seconds,
        checked_at=args.checked_at,
        strict=args.strict,
    )
    write_trust_ledger_remote_submission_preflight_report(report, args.output)
    if args.json:
        print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
    elif report.ready:
        print("TRUST LEDGER REMOTE SUBMISSION PREFLIGHT READY")
    else:
        print(f"TRUST LEDGER REMOTE SUBMISSION PREFLIGHT BLOCKED blockers={list(report.blockers)}")
    return 0 if report.ready or not args.strict else 2


if __name__ == "__main__":
    raise SystemExit(main())
