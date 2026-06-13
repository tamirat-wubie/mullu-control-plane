#!/usr/bin/env python3
"""Produce a durable Gmail account binding receipt.

Purpose: read the Gmail `users/me/profile` endpoint with a transient access
token, hash the observed mailbox account in memory, and persist only redacted
tenant/mailbox binding evidence.
Governance scope: Gmail profile probe, tenant binding, account hash matching,
secret redaction, no mailbox writes, and no production-claim promotion.
Dependencies: scripts.validate_durable_gmail_account_binding_receipt and Gmail
API profile endpoint.
Invariants:
  - Access tokens, raw mailbox addresses, and hash salt values are never
    serialized.
  - The provider call is read-only and targets only `users/me/profile`.
  - Mismatched account hashes fail closed.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import urllib.error
import urllib.request
from typing import Any


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from scripts.validate_durable_gmail_account_binding_receipt import validate_account_binding_receipt  # noqa: E402
from scripts.validate_durable_gmail_oauth_runtime_preflight import matched_secret_marker  # noqa: E402


DEFAULT_OUTPUT = WORKSPACE_ROOT / ".change_assurance" / "durable_gmail_account_binding_receipt.json"
DEFAULT_PROFILE_ENDPOINT = "https://gmail.googleapis.com/gmail/v1/users/me/profile"
DEFAULT_SOURCE_RECEIPT_REF = ".change_assurance/durable_gmail_oauth_live_receipt.json"
DEFAULT_TIMEOUT_SECONDS = 20
EMAIL_ADDRESS_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)

ProfileProbe = Callable[[str, str, int], "GmailProfileProbe"]


@dataclass(frozen=True, slots=True)
class GmailProfileProbe:
    """Redacted Gmail profile probe result with mailbox retained only in memory."""

    status_code: int
    response_payload: Mapping[str, Any]
    email_address: str


def produce_account_binding_receipt(
    *,
    environment: Mapping[str, str] | None = None,
    output_path: Path = DEFAULT_OUTPUT,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    clock: Callable[[], str] | None = None,
    profile_probe: ProfileProbe | None = None,
) -> dict[str, Any]:
    """Produce a redacted Gmail account binding receipt."""

    env = dict(os.environ if environment is None else environment)
    checked_at = (clock or _validation_clock)()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    blockers: list[str] = []

    config_errors = _validate_inputs(env)
    if config_errors:
        blockers.extend(config_errors)
        payload = _receipt_payload(
            env=env,
            checked_at=checked_at,
            status="failed",
            solver_outcome="AwaitingEvidence",
            observed_account_hash="",
            external_provider_call_performed=False,
            blockers=blockers,
        )
        _write_redacted_json(output_path, payload)
        return payload

    token = _access_token(env)
    if timeout_seconds <= 0:
        blockers.append("timeout_seconds_invalid")
        payload = _receipt_payload(
            env=env,
            checked_at=checked_at,
            status="failed",
            solver_outcome="AwaitingEvidence",
            observed_account_hash="",
            external_provider_call_performed=False,
            blockers=blockers,
        )
        _write_redacted_json(output_path, payload)
        return payload

    active_profile_probe = profile_probe or _probe_gmail_profile
    probe = active_profile_probe(
        env.get("MULLU_GMAIL_PROFILE_ENDPOINT", DEFAULT_PROFILE_ENDPOINT).strip() or DEFAULT_PROFILE_ENDPOINT,
        token,
        timeout_seconds,
    )
    observed_account_hash = ""
    if probe.status_code != 200 or not probe.email_address.strip():
        blockers.append("gmail_profile_probe_failed")
    else:
        observed_account_hash = _account_hash(
            salt=_required_env(env, "GMAIL_ACCOUNT_BINDING_HASH_SALT"),
            mailbox_address=probe.email_address,
        )
        if observed_account_hash != env["MULLU_GMAIL_EXPECTED_ACCOUNT_HASH"].strip():
            blockers.append("account_hash_mismatch")

    status = "passed" if not blockers else "failed"
    payload = _receipt_payload(
        env=env,
        checked_at=checked_at,
        status=status,
        solver_outcome="SolvedVerified" if status == "passed" else "AwaitingEvidence",
        observed_account_hash=observed_account_hash,
        external_provider_call_performed=True,
        blockers=blockers,
    )
    _write_redacted_json(output_path, payload)
    return payload


def _receipt_payload(
    *,
    env: Mapping[str, str],
    checked_at: str,
    status: str,
    solver_outcome: str,
    observed_account_hash: str,
    external_provider_call_performed: bool,
    blockers: list[str],
) -> dict[str, Any]:
    return {
        "receipt_id": "durable_gmail_account_binding_receipt",
        "adapter_id": "communication.gmail_oauth",
        "connector_id": "gmail",
        "tenant_ref": env.get("MULLU_GMAIL_ACCOUNT_BINDING_TENANT_REF", ""),
        "expected_account_hash": env.get("MULLU_GMAIL_EXPECTED_ACCOUNT_HASH", ""),
        "observed_account_hash": observed_account_hash,
        "hash_algorithm": "sha256",
        "hash_salt_ref": env.get("MULLU_GMAIL_ACCOUNT_BINDING_HASH_SALT_REF", "secret:GMAIL_ACCOUNT_BINDING_HASH_SALT"),
        "source_receipt_ref": env.get("MULLU_GMAIL_ACCOUNT_BINDING_SOURCE_RECEIPT_REF", DEFAULT_SOURCE_RECEIPT_REF),
        "account_profile_probe_performed": external_provider_call_performed,
        "external_provider_call_performed": external_provider_call_performed,
        "external_mailbox_write_performed": False,
        "credential_values_disclosed": False,
        "checked_at": checked_at,
        "status": status,
        "solver_outcome": solver_outcome,
        "blockers": list(blockers),
    }


def _validate_inputs(environment: Mapping[str, str]) -> list[str]:
    blockers: list[str] = []
    if not _access_token(environment):
        blockers.append("gmail_access_token_missing")
    for name in (
        "MULLU_GMAIL_EXPECTED_ACCOUNT_HASH",
        "GMAIL_ACCOUNT_BINDING_HASH_SALT",
        "MULLU_GMAIL_ACCOUNT_BINDING_TENANT_REF",
    ):
        if not _required_env(environment, name):
            blockers.append(f"{name.lower()}_missing")
    expected_hash = environment.get("MULLU_GMAIL_EXPECTED_ACCOUNT_HASH", "").strip()
    if expected_hash and not re.fullmatch(r"[a-f0-9]{64}", expected_hash):
        blockers.append("expected_account_hash_invalid")
    return blockers


def _probe_gmail_profile(profile_endpoint: str, access_token: str, timeout_seconds: int) -> GmailProfileProbe:
    request = urllib.request.Request(
        profile_endpoint,
        headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
            response_body = response.read()
            status_code = int(response.status)
    except urllib.error.HTTPError as exc:
        response_body = exc.read()
        status_code = int(exc.code)
    except (TimeoutError, OSError, urllib.error.URLError):
        return GmailProfileProbe(
            status_code=503,
            response_payload={"error": "transport_error"},
            email_address="",
        )
    payload = _json_object(response_body)
    email_address = payload.get("emailAddress") if isinstance(payload.get("emailAddress"), str) else ""
    return GmailProfileProbe(status_code=status_code, response_payload=payload, email_address=email_address)


def _json_object(response_body: bytes) -> dict[str, Any]:
    try:
        payload = json.loads(response_body.decode("utf-8"), parse_constant=_reject_json_constant)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return {"error": "invalid_json_response"}
    return payload if isinstance(payload, dict) else {"error": "non_object_response"}


def _reject_json_constant(constant: str) -> None:
    raise ValueError(f"non-finite JSON constant is not allowed: {constant}")


def _account_hash(*, salt: str, mailbox_address: str) -> str:
    normalized_address = mailbox_address.strip().lower()
    digest_input = f"{salt}:{normalized_address}".encode("utf-8")
    return hashlib.sha256(digest_input).hexdigest()


def _access_token(environment: Mapping[str, str]) -> str:
    return (
        environment.get("GMAIL_ACCESS_TOKEN", "").strip()
        or environment.get("EMAIL_CALENDAR_CONNECTOR_TOKEN", "").strip()
    )


def _required_env(environment: Mapping[str, str], name: str) -> str:
    return str(environment.get(name, "")).strip()


def _write_redacted_json(path: Path, payload: Mapping[str, Any]) -> None:
    serialized = json.dumps(payload, indent=2, sort_keys=True)
    if matched_secret_marker(serialized) or EMAIL_ADDRESS_RE.search(serialized):
        raise ValueError("Gmail account binding receipt contains prohibited material")
    path.write_text(serialized + "\n", encoding="utf-8")


def _validation_clock() -> str:
    return os.environ.get("MULLU_VALIDATION_TIMESTAMP", "1970-01-01T00:00:00Z")


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for Gmail account binding evidence."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    payload = produce_account_binding_receipt(
        output_path=args.output,
        timeout_seconds=args.timeout_seconds,
    )
    validation_report = validate_account_binding_receipt(args.output, now=str(payload.get("checked_at", "")))
    response = {"receipt": payload, "validation": validation_report}
    if args.json:
        print(json.dumps(response, indent=2, sort_keys=True))
    if args.strict and not validation_report["ready_for_tenant_binding"]:
        return 1
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
