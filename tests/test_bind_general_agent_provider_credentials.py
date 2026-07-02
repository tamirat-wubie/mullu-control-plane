"""Tests for general-agent provider credential binding bootstrap.

Purpose: prove provider credential binding receipts remain redacted and
GitHub secret installation is explicit.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.bind_general_agent_provider_credentials.
Invariants:
  - Secret values are never serialized.
  - Missing provider credentials remain explicit blockers.
  - GitHub secret installation is opt-in and records only status.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from datetime import datetime

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.bind_general_agent_provider_credentials import (  # noqa: E402
    bind_general_agent_provider_credentials,
    main,
    write_provider_credential_binding_receipt,
)


def test_binding_receipt_blocks_missing_provider_credentials() -> None:
    receipt = bind_general_agent_provider_credentials(env_reader=lambda _name: "")
    payload = receipt.as_dict()

    assert receipt.ready is False
    assert receipt.missing_credentials == ("OPENAI_API_KEY", "EMAIL_CALENDAR_CONNECTOR_TOKEN")
    assert payload["secret_values_serialized"] is False
    assert payload["external_provider_call_performed"] is False
    assert all(binding["value_serialized"] is False for binding in payload["bindings"])


def test_binding_receipt_redacts_present_provider_values() -> None:
    secrets = {
        "OPENAI_API_KEY": "sk-test-secret-value",
        "EMAIL_CALENDAR_CONNECTOR_TOKEN": "ya29.secret-token-value",
    }

    receipt = bind_general_agent_provider_credentials(env_reader=secrets.get)
    rendered = json.dumps(receipt.as_dict(), sort_keys=True)

    assert receipt.ready is True
    assert receipt.missing_credentials == ()
    assert "sk-test-secret-value" not in rendered
    assert "ya29.secret-token-value" not in rendered
    assert "sk-" not in rendered
    assert "ya29." not in rendered


def test_github_secret_installation_is_opt_in_and_redacted() -> None:
    calls: list[tuple[str, str, str]] = []
    secrets = {
        "OPENAI_API_KEY": "plain-openai-token",
        "EMAIL_CALENDAR_CONNECTOR_TOKEN": "plain-email-token",
    }

    def install(repo: str, name: str, value: str) -> tuple[bool, str]:
        calls.append((repo, name, value))
        return True, ""

    without_install = bind_general_agent_provider_credentials(
        env_reader=secrets.get,
        github_repo="owner/repo",
        install_github_secrets=False,
        secret_installer=install,
    )
    assert calls == []

    with_install = bind_general_agent_provider_credentials(
        env_reader=secrets.get,
        github_repo="owner/repo",
        install_github_secrets=True,
        secret_installer=install,
    )
    rendered = json.dumps(with_install.as_dict(), sort_keys=True)

    assert without_install.ready is True
    assert calls == [
        ("owner/repo", "OPENAI_API_KEY", "plain-openai-token"),
        ("owner/repo", "EMAIL_CALENDAR_CONNECTOR_TOKEN", "plain-email-token"),
    ]
    assert with_install.ready is True
    assert all(binding.github_secret_installed for binding in with_install.bindings)
    assert "plain-openai-token" not in rendered
    assert "plain-email-token" not in rendered


def test_failed_github_secret_installation_error_is_sanitized() -> None:
    secrets = {
        "OPENAI_API_KEY": "sk-test-secret-value",
        "EMAIL_CALENDAR_CONNECTOR_TOKEN": "ya29.secret-token-value",
    }

    def install(_repo: str, _name: str, value: str) -> tuple[bool, str]:
        return False, f"provider echoed {value}"

    receipt = bind_general_agent_provider_credentials(
        env_reader=secrets.get,
        github_repo="owner/repo",
        install_github_secrets=True,
        secret_installer=install,
    )
    rendered = json.dumps(receipt.as_dict(), sort_keys=True)

    assert receipt.ready is False
    assert receipt.missing_credentials == ()
    assert "secret_install_error" in rendered
    assert "provider echoed" not in rendered
    assert "sk-test-secret-value" not in rendered
    assert "ya29.secret-token-value" not in rendered
    assert "sk-" not in rendered
    assert "ya29." not in rendered


def test_binding_receipt_checked_at_is_iso_timestamp() -> None:
    receipt = bind_general_agent_provider_credentials(
        env_reader=lambda _name: "",
        checked_at="2026-07-02T00:00:00+00:00",
    )

    parsed = datetime.fromisoformat(receipt.checked_at)

    assert parsed.isoformat() == "2026-07-02T00:00:00+00:00"
    assert receipt.checked_at.endswith("+00:00")
    assert receipt.ready is False


def test_cli_writes_redacted_receipt(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "plain-openai-token")
    monkeypatch.setenv("EMAIL_CALENDAR_CONNECTOR_TOKEN", "plain-email-token")
    output_path = tmp_path / "provider_credential_binding.json"

    exit_code = main(["--output", str(output_path), "--json"])
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert payload["ready"] is True
    assert payload["missing_credentials"] == []
    assert "plain-openai-token" not in json.dumps(payload, sort_keys=True)
    assert "plain-email-token" not in json.dumps(payload, sort_keys=True)


def test_writer_returns_output_path(tmp_path: Path) -> None:
    receipt = bind_general_agent_provider_credentials(env_reader=lambda _name: "")
    output_path = tmp_path / "receipt.json"

    written = write_provider_credential_binding_receipt(receipt, output_path)

    assert written == output_path
    assert json.loads(output_path.read_text(encoding="utf-8"))["ready"] is False
