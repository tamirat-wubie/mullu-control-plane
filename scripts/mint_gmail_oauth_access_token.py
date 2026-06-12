"""Mint a Gmail OAuth access token for GitHub Actions runtime use.

Purpose: exchange a governed Gmail OAuth refresh token for a short-lived
    access token and write only redacted lifecycle evidence.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: gateway.gmail_oauth_lifecycle and Google's OAuth token endpoint.
Invariants:
  - Client secret, refresh token, and access token are never printed.
  - Public receipts include only redacted status, digest, and recovery data.
  - The minted access token is written only to the requested env file.
"""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any
import urllib.error
import urllib.parse
import urllib.request

from gateway.gmail_oauth_lifecycle import (
    GMAIL_OAUTH_TOKEN_ENDPOINT,
    GMAIL_READONLY_SCOPE,
    GmailOAuthLifecycleConfig,
    GmailOAuthSecretRefs,
    GmailOAuthWitnessRefs,
    assert_no_secret_values,
    classify_refresh_response,
)

DEFAULT_OUTPUT = Path(".change_assurance/gmail_oauth_refresh_receipt.json")
TOKEN_REQUEST_TIMEOUT_SECONDS = 15.0


def mint_gmail_oauth_access_token(
    *,
    env: Mapping[str, str] | None = None,
    output_path: Path = DEFAULT_OUTPUT,
    github_env_path: Path | None = None,
    urlopen: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Mint a Gmail OAuth access token and write a redacted receipt."""

    resolved_env = env or os.environ
    config = _config_from_env(resolved_env)
    status_code, payload = _request_access_token(resolved_env, urlopen or urllib.request.urlopen)
    outcome = classify_refresh_response(status_code=status_code, response_payload=payload, config=config)
    access_token = payload.get("access_token") if outcome.succeeded else ""
    if outcome.succeeded and isinstance(access_token, str) and access_token.strip():
        if github_env_path is not None:
            _append_github_env(github_env_path, "EMAIL_CALENDAR_CONNECTOR_TOKEN", access_token)
        _mask_for_github_logs(access_token)
    receipt = {
        "receipt_id": "gmail-oauth-refresh-runtime",
        "adapter_id": "communication.email_calendar_worker",
        "status": "passed" if outcome.succeeded else "failed",
        "verification_status": "passed" if outcome.succeeded else "failed",
        "connector_id": "gmail",
        "provider_operation": "oauth.refresh_token",
        "oauth_outcome": outcome.as_redacted_dict(),
        "token_endpoint": GMAIL_OAUTH_TOKEN_ENDPOINT,
        "scope_ids": [GMAIL_READONLY_SCOPE],
        "secret_values_disclosed": False,
        "blockers": [] if outcome.succeeded else ["gmail_oauth_refresh_failed"],
    }
    serialized = json.dumps(receipt, sort_keys=True, separators=(",", ":"))
    assert_no_secret_values(serialized)
    _write_json(output_path, receipt)
    return receipt


def _config_from_env(env: Mapping[str, str]) -> GmailOAuthLifecycleConfig:
    _require_env(env, "GMAIL_OAUTH_CLIENT_ID")
    _require_env(env, "GMAIL_OAUTH_CLIENT_SECRET")
    _require_env(env, "GMAIL_REFRESH_TOKEN")
    return GmailOAuthLifecycleConfig(
        connector_id="gmail",
        operation_family="read_only_search",
        scope_ids=(GMAIL_READONLY_SCOPE,),
        secret_refs=GmailOAuthSecretRefs(
            client_id_ref="secret-ref:GMAIL_OAUTH_CLIENT_ID",
            client_secret_ref="secret-ref:GMAIL_OAUTH_CLIENT_SECRET",
            refresh_token_ref="secret-ref:GMAIL_REFRESH_TOKEN",
        ),
        witness_refs=GmailOAuthWitnessRefs(
            consent_screen_ref=env.get("MULLU_GMAIL_OAUTH_CONSENT_WITNESS_REF", "github-actions:gmail-oauth-consent"),
            oauth_client_ref=env.get("MULLU_GMAIL_OAUTH_CLIENT_WITNESS_REF", "github-actions:gmail-oauth-client"),
            least_privilege_scope_ref=env.get(
                "MULLU_GMAIL_LEAST_PRIVILEGE_SCOPE_RECEIPT_REF",
                "github-actions:gmail-readonly-scope",
            ),
            refresh_token_storage_ref=env.get(
                "MULLU_GMAIL_REFRESH_TOKEN_STORAGE_RECEIPT_REF",
                "github-actions:gmail-refresh-token-secret",
            ),
            revocation_recovery_ref=env.get(
                "MULLU_GMAIL_REVOCATION_RECOVERY_RECEIPT_REF",
                "github-actions:gmail-revocation-recovery",
            ),
        ),
    )


def _request_access_token(env: Mapping[str, str], urlopen: Callable[..., Any]) -> tuple[int, dict[str, Any]]:
    form = {
        "grant_type": "refresh_token",
        "client_id": _require_env(env, "GMAIL_OAUTH_CLIENT_ID"),
        "client_secret": _require_env(env, "GMAIL_OAUTH_CLIENT_SECRET"),
        "refresh_token": _require_env(env, "GMAIL_REFRESH_TOKEN"),
    }
    request = urllib.request.Request(
        GMAIL_OAUTH_TOKEN_ENDPOINT,
        data=urllib.parse.urlencode(form).encode("utf-8"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        response = urlopen(request, timeout=TOKEN_REQUEST_TIMEOUT_SECONDS)
        try:
            body = response.read()
        finally:
            close = getattr(response, "close", None)
            if callable(close):
                close()
        return _response_status(response), _json_payload(body)
    except urllib.error.HTTPError as exc:
        return int(exc.code), _json_payload(_read_error_body(exc))
    except (TimeoutError, OSError, urllib.error.URLError):
        return 503, {"error": "transport_error"}


def _require_env(env: Mapping[str, str], key: str) -> str:
    value = env.get(key, "").strip()
    if not value:
        raise ValueError(f"{key} is required")
    return value


def _response_status(response: Any) -> int:
    status = getattr(response, "status", None)
    if isinstance(status, int):
        return status
    code = getattr(response, "code", None)
    if isinstance(code, int):
        return code
    getcode = getattr(response, "getcode", None)
    if callable(getcode):
        resolved = getcode()
        if isinstance(resolved, int):
            return resolved
    return 200


def _read_error_body(error: urllib.error.HTTPError) -> bytes:
    try:
        body = error.read()
    except OSError:
        return b""
    return body if isinstance(body, bytes) else b""


def _json_payload(body: bytes) -> dict[str, Any]:
    if not body:
        return {}
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _append_github_env(path: Path, key: str, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"{key}={value}\n")


def _mask_for_github_logs(value: str) -> None:
    if os.environ.get("GITHUB_ACTIONS") == "true":
        print(f"::add-mask::{value}")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--github-env", default="")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    receipt = mint_gmail_oauth_access_token(
        output_path=Path(args.output),
        github_env_path=Path(args.github_env) if args.github_env else None,
    )
    if args.json:
        print(json.dumps(receipt, indent=2, sort_keys=True))
    elif receipt["status"] == "passed":
        print("GMAIL OAUTH ACCESS TOKEN MINT PASSED")
    else:
        print(f"GMAIL OAUTH ACCESS TOKEN MINT FAILED blockers={receipt['blockers']}")
    return 0 if receipt["status"] == "passed" or not args.strict else 2


if __name__ == "__main__":
    raise SystemExit(main())
