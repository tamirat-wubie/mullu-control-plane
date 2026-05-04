#!/usr/bin/env python3
"""Provision the runtime witness secret for deployment evidence.

Purpose: create or accept one runtime witness HMAC secret and bind it to the
GitHub Actions repository secret used by the deployment witness workflow.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: Python secrets module and GitHub CLI.
Invariants:
  - Generated secrets use operating-system entropy.
  - Supplied secrets are read from stdin, not command-line arguments.
  - Secret values are never printed.
  - Generated secrets require an explicit ignored runtime env output path.
  - GitHub secret updates are performed through gh secret set with stdin input.
"""

from __future__ import annotations

import argparse
import os
import secrets
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Protocol

DEFAULT_REPOSITORY = "tamirat-wubie/mullu-control-plane"
DEFAULT_SECRET_NAME = "MULLU_RUNTIME_WITNESS_SECRET"
DEFAULT_SECRET_BYTES = 32


class CommandRunner(Protocol):
    """Subprocess-compatible command execution contract."""

    def __call__(
        self,
        command: list[str],
        *,
        input: str | None,
        check: bool,
        capture_output: bool,
        text: bool,
    ) -> subprocess.CompletedProcess[str]:
        """Run one command and return its completed process."""


@dataclass(frozen=True, slots=True)
class ProvisionResult:
    """Observed result of one runtime witness secret provisioning action."""

    repository: str
    secret_name: str
    secret_source: str
    fingerprint: str
    provisioned_at: str
    github_secret_set: bool
    runtime_env_output: Path | None
    runtime_export_hint: str


def provision_runtime_witness_secret(
    *,
    repository: str = DEFAULT_REPOSITORY,
    secret_name: str = DEFAULT_SECRET_NAME,
    supplied_secret: str | None = None,
    set_github_secret: bool = True,
    secret_bytes: int = DEFAULT_SECRET_BYTES,
    runtime_env_output: Path | None = None,
    runner: CommandRunner | None = None,
    clock: Callable[[], str] | None = None,
) -> ProvisionResult:
    """Provision one runtime witness secret without printing its value."""
    command_runner = runner or subprocess.run
    secret_value, secret_source = _resolve_secret(
        supplied_secret=supplied_secret,
        secret_bytes=secret_bytes,
    )
    if secret_source == "generated" and runtime_env_output is None:
        raise RuntimeError(
            "generated runtime witness secret requires --runtime-env-output; "
            "use --secret-stdin when the runtime already has a secret"
        )
    if runtime_env_output is not None:
        _write_runtime_env_output(
            output_path=runtime_env_output,
            secret_name=secret_name,
            secret_value=secret_value,
        )
    if set_github_secret:
        _set_github_secret(
            repository=repository,
            secret_name=secret_name,
            secret_value=secret_value,
            runner=command_runner,
        )

    return ProvisionResult(
        repository=repository,
        secret_name=secret_name,
        secret_source=secret_source,
        fingerprint=_fingerprint(secret_value),
        provisioned_at=(clock or _utc_now)(),
        github_secret_set=set_github_secret,
        runtime_env_output=runtime_env_output,
        runtime_export_hint=f"Set the same value in the gateway runtime as {secret_name}.",
    )


def _resolve_secret(
    *,
    supplied_secret: str | None,
    secret_bytes: int,
) -> tuple[str, str]:
    if supplied_secret is not None:
        secret_value = supplied_secret.strip()
        if not secret_value:
            raise RuntimeError("supplied runtime witness secret is empty")
        if len(secret_value) < 32:
            raise RuntimeError("supplied runtime witness secret must be at least 32 characters")
        return secret_value, "stdin"

    if secret_bytes < 32:
        raise RuntimeError("generated runtime witness secret must use at least 32 bytes")
    return secrets.token_urlsafe(secret_bytes), "generated"


def _set_github_secret(
    *,
    repository: str,
    secret_name: str,
    secret_value: str,
    runner: CommandRunner,
) -> None:
    command = ["gh", "secret", "set", secret_name, "--repo", repository]
    try:
        runner(command, input=secret_value, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise RuntimeError("GitHub CLI executable 'gh' was not found") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"failed to set GitHub secret {secret_name}: exit_code={exc.returncode}") from exc


def _write_runtime_env_output(
    *,
    output_path: Path,
    secret_name: str,
    secret_value: str,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(f"{secret_name}={secret_value}\n", encoding="utf-8")
    try:
        output_path.chmod(0o600)
    except OSError:
        pass


def _fingerprint(secret_value: str) -> str:
    import hashlib

    return hashlib.sha256(secret_value.encode("utf-8")).hexdigest()[:16]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse runtime witness secret provisioning CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Provision the runtime witness secret for deployment evidence."
    )
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", DEFAULT_REPOSITORY))
    parser.add_argument("--secret-name", default=DEFAULT_SECRET_NAME)
    parser.add_argument("--secret-stdin", action="store_true")
    parser.add_argument("--generated-bytes", type=int, default=DEFAULT_SECRET_BYTES)
    parser.add_argument("--runtime-env-output", default="")
    parser.add_argument("--no-github-secret", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for runtime witness secret provisioning."""
    args = parse_args(argv)
    supplied_secret = sys.stdin.read() if args.secret_stdin else None
    try:
        result = provision_runtime_witness_secret(
            repository=args.repo,
            secret_name=args.secret_name,
            supplied_secret=supplied_secret,
            set_github_secret=not args.no_github_secret,
            secret_bytes=args.generated_bytes,
            runtime_env_output=Path(args.runtime_env_output) if args.runtime_env_output else None,
        )
    except RuntimeError as exc:
        print(f"runtime witness secret provisioning failed: {exc}")
        return 1

    print(f"repository: {result.repository}")
    print(f"secret_name: {result.secret_name}")
    print(f"secret_source: {result.secret_source}")
    print(f"secret_fingerprint: {result.fingerprint}")
    print(f"provisioned_at: {result.provisioned_at}")
    print(f"github_secret_set: {str(result.github_secret_set).lower()}")
    print(f"runtime_env_output: {result.runtime_env_output or 'not-written'}")
    print(result.runtime_export_hint)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
