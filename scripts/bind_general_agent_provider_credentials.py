#!/usr/bin/env python3
"""Bind general-agent provider credentials without serializing secret values.

Purpose: consume operator-supplied provider credentials from the process
environment and optionally install them as GitHub Actions secrets.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: local environment variables and optional GitHub CLI.
Invariants:
  - Provider credential values are never printed, persisted, or compared.
  - Receipts record credential names, presence, and installation status only.
  - GitHub secret installation is opt-in and fails closed per secret.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Callable, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "general_agent_provider_credential_binding_receipt.json"
REQUIRED_PROVIDER_CREDENTIALS = ("OPENAI_API_KEY", "EMAIL_CALENDAR_CONNECTOR_TOKEN")
SECRET_VALUE_MARKERS = ("sk-", "ya29.", "refresh_token=", "client_secret=")

EnvReader = Callable[[str], str | None]
SecretInstaller = Callable[[str, str, str], tuple[bool, str]]


@dataclass(frozen=True, slots=True)
class ProviderCredentialBinding:
    """Presence-only binding status for one provider credential."""

    name: str
    present: bool
    required: bool
    value_serialized: bool
    github_secret_install_attempted: bool
    github_secret_installed: bool
    blocker: str

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-ready binding payload."""

        return asdict(self)


@dataclass(frozen=True, slots=True)
class ProviderCredentialBindingReceipt:
    """Redacted provider credential binding receipt."""

    receipt_id: str
    checked_at: str
    ready: bool
    github_repo: str
    install_github_secrets: bool
    secret_values_serialized: bool
    external_provider_call_performed: bool
    missing_credentials: tuple[str, ...]
    bindings: tuple[ProviderCredentialBinding, ...]
    next_action: str

    def as_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-ready receipt."""

        return {
            "receipt_id": self.receipt_id,
            "checked_at": self.checked_at,
            "ready": self.ready,
            "github_repo": self.github_repo,
            "install_github_secrets": self.install_github_secrets,
            "secret_values_serialized": self.secret_values_serialized,
            "external_provider_call_performed": self.external_provider_call_performed,
            "missing_credentials": list(self.missing_credentials),
            "bindings": [binding.as_dict() for binding in self.bindings],
            "next_action": self.next_action,
        }


def bind_general_agent_provider_credentials(
    *,
    env_reader: EnvReader | None = None,
    github_repo: str = "",
    install_github_secrets: bool = False,
    secret_installer: SecretInstaller | None = None,
    checked_at: str | None = None,
) -> ProviderCredentialBindingReceipt:
    """Build a redacted provider credential binding receipt."""

    resolved_env_reader = env_reader or os.environ.get
    resolved_installer = secret_installer or install_github_secret
    bindings: list[ProviderCredentialBinding] = []
    for name in REQUIRED_PROVIDER_CREDENTIALS:
        value = (resolved_env_reader(name) or "").strip()
        present = bool(value)
        attempted = bool(install_github_secrets and present)
        installed = False
        blocker = "" if present else f"credential_missing:{name}"
        if attempted:
            installed, install_error = resolved_installer(github_repo, name, value)
            if not installed:
                blocker = f"github_secret_install_failed:{name}:{_safe_error(install_error)}"
        bindings.append(
            ProviderCredentialBinding(
                name=name,
                present=present,
                required=True,
                value_serialized=False,
                github_secret_install_attempted=attempted,
                github_secret_installed=installed,
                blocker=blocker,
            )
        )
    missing = tuple(binding.name for binding in bindings if not binding.present)
    failed_installs = tuple(binding.blocker for binding in bindings if binding.blocker.startswith("github_secret_install_failed:"))
    ready = not missing and not failed_installs
    receipt = ProviderCredentialBindingReceipt(
        receipt_id="general-agent-provider-credential-binding-receipt-v1",
        checked_at=checked_at or _validation_clock(),
        ready=ready,
        github_repo=github_repo if install_github_secrets else "",
        install_github_secrets=install_github_secrets,
        secret_values_serialized=False,
        external_provider_call_performed=False,
        missing_credentials=missing,
        bindings=tuple(bindings),
        next_action=_next_action(missing=missing, failed_installs=failed_installs),
    )
    _assert_receipt_redacted(receipt)
    return receipt


def install_github_secret(github_repo: str, name: str, value: str) -> tuple[bool, str]:
    """Install one GitHub Actions secret without exposing its value."""

    repo = github_repo.strip()
    if not repo:
        return False, "github_repo_missing"
    completed = subprocess.run(
        ("gh", "secret", "set", name, "--repo", repo),
        input=value,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    if completed.returncode == 0:
        return True, ""
    return False, f"gh_secret_set_failed_returncode_{completed.returncode}"


def write_provider_credential_binding_receipt(
    receipt: ProviderCredentialBindingReceipt,
    output_path: Path,
) -> Path:
    """Write a redacted provider credential binding receipt."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(receipt.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _assert_receipt_redacted(receipt: ProviderCredentialBindingReceipt) -> None:
    serialized = json.dumps(receipt.as_dict(), sort_keys=True)
    for marker in SECRET_VALUE_MARKERS:
        if marker.lower() in serialized.lower():
            raise ValueError("provider credential binding receipt contains secret-shaped material")


def _safe_error(raw_error: str) -> str:
    first_line = next((line.strip() for line in raw_error.splitlines() if line.strip()), "")
    if first_line == "github_repo_missing":
        return first_line
    if first_line.startswith("gh_secret_set_failed_returncode_"):
        return first_line[:80]
    return "secret_install_error" if first_line else "unknown_error"


def _next_action(*, missing: tuple[str, ...], failed_installs: tuple[str, ...]) -> str:
    if missing:
        return "bind missing provider credentials in the process environment, then rerun this receipt"
    if failed_installs:
        return "repair GitHub secret installation and rerun this receipt"
    return "rerun environment binding receipt, live evidence queue, and adapter live receipts"


def _validation_clock() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse provider credential binding arguments."""

    parser = argparse.ArgumentParser(description="Bind general-agent provider credentials without value serialization.")
    parser.add_argument("--github-repo", default="")
    parser.add_argument("--install-github-secrets", action="store_true")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for provider credential binding."""

    args = parse_args(argv)
    receipt = bind_general_agent_provider_credentials(
        github_repo=str(args.github_repo),
        install_github_secrets=bool(args.install_github_secrets),
    )
    write_provider_credential_binding_receipt(receipt, Path(args.output))
    if args.json:
        print(json.dumps(receipt.as_dict(), indent=2, sort_keys=True))
    elif receipt.ready:
        print("general-agent provider credential binding ready")
    else:
        print(f"general-agent provider credential binding blocked missing={list(receipt.missing_credentials)}")
    return 0 if receipt.ready or not args.strict else 2


if __name__ == "__main__":
    raise SystemExit(main())
