#!/usr/bin/env python3
"""Produce a durable Gmail OAuth live evidence receipt.

Purpose: refresh a Gmail OAuth access token from governed secret inputs and run
the existing read-only email/calendar live probe without persisting token values.
Governance scope: OAuth refresh, Gmail readonly scope, live adapter evidence,
secret redaction, revocation recovery, and no external mailbox writes.
Dependencies: gateway.gmail_oauth_lifecycle,
scripts.produce_capability_adapter_live_receipts, and Google OAuth token endpoint.
Invariants:
  - Refresh, client-secret, and access-token values are never serialized.
  - Gmail live evidence remains read-only and blocks on observed external write.
  - Failed refresh outcomes emit explicit recovery actions.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping
from dataclasses import dataclass
import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from gateway.gmail_oauth_lifecycle import (  # noqa: E402
    GMAIL_READONLY_SCOPE,
    GmailOAuthLifecycleConfig,
    GmailOAuthSecretRefs,
    GmailOAuthWitnessRefs,
    assert_no_secret_values,
    build_refresh_request_plan,
    classify_refresh_response,
)
from scripts.produce_capability_adapter_live_receipts import (  # noqa: E402
    DEFAULT_EMAIL_CALENDAR_RECEIPT,
    LiveReceiptWrite,
    produce_email_calendar_live_receipt,
)
from scripts.validate_durable_gmail_oauth_runtime_preflight import build_preflight_report  # noqa: E402


DEFAULT_OUTPUT = WORKSPACE_ROOT / ".change_assurance" / "durable_gmail_oauth_live_receipt.json"
DEFAULT_TIMEOUT_SECONDS = 20

RefreshExchange = Callable[[str, Mapping[str, str], int], "TokenRefreshExchange"]
EmailCalendarReceiptProducer = Callable[..., LiveReceiptWrite]


@dataclass(frozen=True, slots=True)
class TokenRefreshExchange:
    """Provider token-refresh response with token retained only in memory."""

    status_code: int
    response_payload: Mapping[str, Any]
    access_token: str


def produce_durable_gmail_oauth_live_receipt(
    *,
    environment: Mapping[str, str] | None = None,
    output_path: Path = DEFAULT_OUTPUT,
    email_calendar_output_path: Path = DEFAULT_EMAIL_CALENDAR_RECEIPT,
    query: str = "newer_than:1d",
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    clock: Callable[[], str] | None = None,
    refresh_exchange: RefreshExchange | None = None,
    email_calendar_receipt_producer: EmailCalendarReceiptProducer = produce_email_calendar_live_receipt,
) -> dict[str, Any]:
    """Produce a redacted durable Gmail OAuth live receipt."""

    env = dict(os.environ if environment is None else environment)
    checked_at = (clock or _validation_clock)()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    email_calendar_output_path.parent.mkdir(parents=True, exist_ok=True)

    preflight_report = build_preflight_report(env)
    blockers: list[str] = []

    if not preflight_report["ready_for_live_probe"]:
        blockers.append("gmail_oauth_preflight_not_ready")
        payload = _receipt_payload(
            checked_at=checked_at,
            status="failed",
            solver_outcome="AwaitingEvidence",
            preflight_report=preflight_report,
            refresh_plan={},
            refresh_outcome={},
            email_calendar_output_path=email_calendar_output_path,
            email_calendar_write=None,
            blockers=blockers,
        )
        _write_redacted_json(output_path, payload)
        return payload

    config = _build_lifecycle_config(env)
    refresh_plan = build_refresh_request_plan(config)
    exchange = (refresh_exchange or _exchange_refresh_token)(
        config.token_endpoint,
        _refresh_form(env),
        timeout_seconds,
    )
    refresh_outcome = classify_refresh_response(
        status_code=exchange.status_code,
        response_payload=exchange.response_payload,
        config=config,
    )
    if not refresh_outcome.succeeded:
        blockers.append(f"gmail_oauth_refresh_failed:{refresh_outcome.status}")
        payload = _receipt_payload(
            checked_at=checked_at,
            status="failed",
            solver_outcome="AwaitingEvidence",
            preflight_report=preflight_report,
            refresh_plan=refresh_plan.as_redacted_dict(),
            refresh_outcome=refresh_outcome.as_redacted_dict(),
            email_calendar_output_path=email_calendar_output_path,
            email_calendar_write=None,
            blockers=blockers,
        )
        _write_redacted_json(output_path, payload)
        return payload

    probe_env = dict(env)
    probe_env["GMAIL_ACCESS_TOKEN"] = exchange.access_token
    probe_env["GMAIL_SCOPE_ID"] = GMAIL_READONLY_SCOPE
    probe_env["EMAIL_CALENDAR_CONNECTOR_ID"] = "gmail"
    probe_env["MULLU_EMAIL_CALENDAR_WORKER_ADAPTER"] = probe_env.get(
        "MULLU_EMAIL_CALENDAR_WORKER_ADAPTER",
        "production",
    )

    previous_values = _replace_process_environment(probe_env)
    try:
        email_calendar_write = email_calendar_receipt_producer(
            output_path=email_calendar_output_path,
            connector_id="gmail",
            query=query,
        )
    finally:
        _restore_process_environment(previous_values)

    blockers.extend(email_calendar_write.blockers)
    status = "passed" if not blockers else "failed"
    payload = _receipt_payload(
        checked_at=checked_at,
        status=status,
        solver_outcome="SolvedVerified" if status == "passed" else "AwaitingEvidence",
        preflight_report=preflight_report,
        refresh_plan=refresh_plan.as_redacted_dict(),
        refresh_outcome=refresh_outcome.as_redacted_dict(),
        email_calendar_output_path=email_calendar_output_path,
        email_calendar_write=email_calendar_write,
        blockers=blockers,
    )
    _write_redacted_json(output_path, payload)
    return payload


def _build_lifecycle_config(environment: Mapping[str, str]) -> GmailOAuthLifecycleConfig:
    """Build a secret-reference-only Gmail OAuth lifecycle config."""

    return GmailOAuthLifecycleConfig(
        connector_id="gmail",
        operation_family=environment.get("MULLU_GMAIL_CONNECTOR_OPERATION_FAMILY", "read_only_search"),
        scope_ids=(environment.get("GMAIL_SCOPE_ID", GMAIL_READONLY_SCOPE),),
        secret_refs=GmailOAuthSecretRefs(
            client_id_ref="secret:GMAIL_OAUTH_CLIENT_ID",
            client_secret_ref="secret:GMAIL_OAUTH_CLIENT_SECRET",
            refresh_token_ref="secret:GMAIL_REFRESH_TOKEN",
        ),
        witness_refs=GmailOAuthWitnessRefs(
            consent_screen_ref=environment.get("MULLU_GMAIL_OAUTH_CONSENT_WITNESS_REF", ""),
            oauth_client_ref=environment.get("MULLU_GMAIL_OAUTH_CLIENT_WITNESS_REF", ""),
            least_privilege_scope_ref=environment.get("MULLU_GMAIL_LEAST_PRIVILEGE_SCOPE_RECEIPT_REF", ""),
            refresh_token_storage_ref=environment.get("MULLU_GMAIL_REFRESH_TOKEN_STORAGE_RECEIPT_REF", ""),
            revocation_recovery_ref=environment.get("MULLU_GMAIL_REVOCATION_RECOVERY_RECEIPT_REF", ""),
        ),
    )


def _refresh_form(environment: Mapping[str, str]) -> dict[str, str]:
    """Return provider form fields from runtime secrets."""

    return {
        "client_id": _required_secret(environment, "GMAIL_OAUTH_CLIENT_ID"),
        "client_secret": _required_secret(environment, "GMAIL_OAUTH_CLIENT_SECRET"),
        "refresh_token": _required_secret(environment, "GMAIL_REFRESH_TOKEN"),
        "grant_type": "refresh_token",
    }


def _exchange_refresh_token(
    token_endpoint: str,
    form_fields: Mapping[str, str],
    timeout_seconds: int,
) -> TokenRefreshExchange:
    """Exchange a refresh token for an access token without logging secrets."""

    encoded_body = urllib.parse.urlencode(form_fields).encode("utf-8")
    request = urllib.request.Request(
        token_endpoint,
        data=encoded_body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
            response_body = response.read()
            status_code = int(response.status)
    except urllib.error.HTTPError as exc:
        response_body = exc.read()
        status_code = int(exc.code)
    except (TimeoutError, OSError, urllib.error.URLError):
        return TokenRefreshExchange(
            status_code=503,
            response_payload={"error": "transport_error"},
            access_token="",
        )
    payload = _json_object(response_body)
    access_token = payload.get("access_token") if isinstance(payload.get("access_token"), str) else ""
    return TokenRefreshExchange(status_code=status_code, response_payload=payload, access_token=access_token)


def _receipt_payload(
    *,
    checked_at: str,
    status: str,
    solver_outcome: str,
    preflight_report: Mapping[str, Any],
    refresh_plan: Mapping[str, Any],
    refresh_outcome: Mapping[str, Any],
    email_calendar_output_path: Path,
    email_calendar_write: LiveReceiptWrite | None,
    blockers: list[str],
) -> dict[str, Any]:
    """Build a redacted live receipt payload."""

    return {
        "receipt_id": "durable_gmail_oauth_live_receipt",
        "adapter_id": "communication.gmail_oauth",
        "status": status,
        "solver_outcome": solver_outcome,
        "checked_at": checked_at,
        "connector_id": "gmail",
        "operation_family": "read_only_search",
        "scope_ids": [GMAIL_READONLY_SCOPE],
        "external_provider_call_performed": bool(refresh_outcome),
        "external_mailbox_write_performed": False,
        "credential_values_disclosed": False,
        "preflight_status": preflight_report.get("status", "unknown"),
        "refresh_request_plan": dict(refresh_plan),
        "refresh_outcome": dict(refresh_outcome),
        "email_calendar_live_receipt_ref": _workspace_ref(email_calendar_output_path),
        "email_calendar_live_write": _live_write_dict(email_calendar_write),
        "blockers": list(blockers),
    }


def _live_write_dict(write: LiveReceiptWrite | None) -> dict[str, Any]:
    if write is None:
        return {}
    return {
        "adapter_id": write.adapter_id,
        "status": write.status,
        "output_path": _workspace_ref(Path(write.output_path)),
        "blockers": list(write.blockers),
    }


def _replace_process_environment(new_values: Mapping[str, str]) -> dict[str, str | None]:
    """Temporarily replace process environment values needed by the adapter."""

    keys = (
        "GMAIL_ACCESS_TOKEN",
        "GMAIL_SCOPE_ID",
        "EMAIL_CALENDAR_CONNECTOR_ID",
        "MULLU_EMAIL_CALENDAR_WORKER_ADAPTER",
    )
    previous = {key: os.environ.get(key) for key in keys}
    for key in keys:
        os.environ[key] = new_values[key]
    return previous


def _restore_process_environment(previous_values: Mapping[str, str | None]) -> None:
    """Restore process environment after the transient token probe."""

    for key, value in previous_values.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def _required_secret(environment: Mapping[str, str], name: str) -> str:
    value = environment.get(name, "").strip()
    if not value:
        raise ValueError(f"{name} is required")
    return value


def _json_object(response_body: bytes) -> dict[str, Any]:
    try:
        payload = json.loads(response_body.decode("utf-8"), parse_constant=_reject_json_constant)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return {"error": "invalid_json_response"}
    return payload if isinstance(payload, dict) else {"error": "non_object_response"}


def _reject_json_constant(constant: str) -> None:
    raise ValueError("non-finite JSON constant is not allowed")


def _write_redacted_json(path: Path, payload: Mapping[str, Any]) -> None:
    serialized = json.dumps(payload, indent=2, sort_keys=True)
    assert_no_secret_values(serialized)
    path.write_text(serialized + "\n", encoding="utf-8")


def _workspace_ref(path: Path) -> str:
    resolved = path if path.is_absolute() else WORKSPACE_ROOT / path
    try:
        return resolved.resolve().relative_to(WORKSPACE_ROOT).as_posix()
    except ValueError:
        return resolved.name


def _validation_clock() -> str:
    return os.environ.get("MULLU_VALIDATION_TIMESTAMP", "1970-01-01T00:00:00Z")


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for durable Gmail OAuth live evidence."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--email-calendar-output", type=Path, default=DEFAULT_EMAIL_CALENDAR_RECEIPT)
    parser.add_argument("--email-calendar-query", default="newer_than:1d")
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    payload = produce_durable_gmail_oauth_live_receipt(
        output_path=args.output,
        email_calendar_output_path=args.email_calendar_output,
        query=args.email_calendar_query,
        timeout_seconds=args.timeout_seconds,
    )
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    return 1 if args.strict and payload["status"] != "passed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
