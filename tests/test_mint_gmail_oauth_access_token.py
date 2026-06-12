"""Tests for Gmail OAuth runtime access-token minting.

Purpose: prove the workflow mint helper exchanges durable Gmail OAuth secrets
    without serializing access-token, refresh-token, or client-secret values.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.mint_gmail_oauth_access_token.
Invariants:
  - Access tokens may be written to the requested env file only.
  - Public receipts remain redacted and recovery-specific.
  - Provider failures do not create runtime connector tokens.
"""

from __future__ import annotations

import json
import subprocess
import sys
import urllib.error
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.mint_gmail_oauth_access_token import mint_gmail_oauth_access_token  # noqa: E402


def test_script_entrypoint_loads_gateway_imports_from_repo_root() -> None:
    result = subprocess.run(
        [sys.executable, str(_ROOT / "scripts" / "mint_gmail_oauth_access_token.py"), "--help"],
        cwd=_ROOT,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    assert result.returncode == 0
    assert "Mint a Gmail OAuth access token" in result.stdout
    assert "ModuleNotFoundError" not in result.stderr


def test_mint_writes_access_token_to_env_file_and_redacted_receipt(tmp_path: Path) -> None:
    output_path = tmp_path / "gmail_oauth_refresh_receipt.json"
    github_env_path = tmp_path / "github.env"
    transport = FakeTokenTransport(
        status=200,
        response_body={
            "access_token": "ya29.runtime-token-value",
            "token_type": "Bearer",
            "expires_in": 3600,
        },
    )

    receipt = mint_gmail_oauth_access_token(
        env=_env(),
        output_path=output_path,
        github_env_path=github_env_path,
        urlopen=transport,
    )
    serialized_receipt = output_path.read_text(encoding="utf-8")
    env_contents = github_env_path.read_text(encoding="utf-8")

    assert receipt["status"] == "passed"
    assert receipt["oauth_outcome"]["status"] == "refreshed"
    assert receipt["oauth_outcome"]["access_token_digest"]
    assert "EMAIL_CALENDAR_CONNECTOR_TOKEN=ya29.runtime-token-value" in env_contents
    assert "ya29.runtime-token-value" not in serialized_receipt
    assert "client-secret-value" not in serialized_receipt
    assert "refresh-token-value" not in serialized_receipt


def test_mint_classifies_invalid_grant_without_env_token(tmp_path: Path) -> None:
    output_path = tmp_path / "gmail_oauth_refresh_receipt.json"
    github_env_path = tmp_path / "github.env"
    transport = FakeTokenTransport(
        status=400,
        response_body={"error": "invalid_grant", "error_description": "expired"},
        raises_http_error=True,
    )

    receipt = mint_gmail_oauth_access_token(
        env=_env(),
        output_path=output_path,
        github_env_path=github_env_path,
        urlopen=transport,
    )
    serialized_receipt = output_path.read_text(encoding="utf-8")

    assert receipt["status"] == "failed"
    assert receipt["oauth_outcome"]["status"] == "refresh_token_revoked_or_expired"
    assert receipt["oauth_outcome"]["requires_reauthorization"] is True
    assert receipt["blockers"] == ["gmail_oauth_refresh_failed"]
    assert github_env_path.exists() is False
    assert "refresh-token-value" not in serialized_receipt
    assert "client-secret-value" not in serialized_receipt


def test_mint_rejects_missing_durable_secret_before_transport(tmp_path: Path) -> None:
    output_path = tmp_path / "gmail_oauth_refresh_receipt.json"
    env = _env()
    env.pop("GMAIL_REFRESH_TOKEN")
    transport = FakeTokenTransport(status=200, response_body={})

    try:
        mint_gmail_oauth_access_token(env=env, output_path=output_path, urlopen=transport)
    except ValueError as exc:
        error = str(exc)
    else:
        error = ""

    assert error == "GMAIL_REFRESH_TOKEN is required"
    assert transport.calls == []
    assert output_path.exists() is False


class FakeTokenTransport:
    """urllib-compatible token endpoint fixture."""

    def __init__(self, *, status: int, response_body: dict[str, Any], raises_http_error: bool = False) -> None:
        self._status = status
        self._response_body = response_body
        self._raises_http_error = raises_http_error
        self.calls: list[dict[str, Any]] = []

    def __call__(self, request: Any, *, timeout: float) -> "FakeResponse":
        body = request.data.decode("utf-8")
        self.calls.append(
            {
                "url": request.full_url,
                "method": request.get_method(),
                "body": body,
                "timeout": timeout,
            }
        )
        response = FakeResponse(status=self._status, body=self._response_body)
        if self._raises_http_error:
            raise urllib.error.HTTPError(
                url=request.full_url,
                code=self._status,
                msg="provider rejected refresh",
                hdrs={},
                fp=response,
            )
        return response


class FakeResponse:
    """Minimal urllib response fixture."""

    def __init__(self, *, status: int, body: dict[str, Any]) -> None:
        self.status = status
        self._body = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
        self.closed = False

    def read(self) -> bytes:
        return self._body

    def close(self) -> None:
        self.closed = True


def _env() -> dict[str, str]:
    return {
        "GMAIL_OAUTH_CLIENT_ID": "client-id-value",
        "GMAIL_OAUTH_CLIENT_SECRET": "client-secret-value",
        "GMAIL_REFRESH_TOKEN": "refresh-token-value",
        "MULLU_GMAIL_OAUTH_CONSENT_WITNESS_REF": "witness:gmail-consent",
        "MULLU_GMAIL_OAUTH_CLIENT_WITNESS_REF": "witness:gmail-client",
        "MULLU_GMAIL_LEAST_PRIVILEGE_SCOPE_RECEIPT_REF": "receipt:gmail-readonly-scope",
        "MULLU_GMAIL_REFRESH_TOKEN_STORAGE_RECEIPT_REF": "receipt:gmail-refresh-storage",
        "MULLU_GMAIL_REVOCATION_RECOVERY_RECEIPT_REF": "witness:gmail-revocation",
    }
