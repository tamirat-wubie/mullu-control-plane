#!/usr/bin/env python3
"""Provision deployment witness target variables.

Purpose: bind the live gateway URL and expected runtime environment into
GitHub repository variables used by deployment witness dispatch.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: GitHub CLI repository variable support.
Invariants:
  - Gateway URL is explicit and scheme-qualified.
  - Expected runtime environment is bounded to pilot or production.
  - Repository variables are written through GitHub CLI, not local files.
"""

from __future__ import annotations

import argparse
import os
import subprocess
from dataclasses import dataclass
from typing import Protocol

DEFAULT_REPOSITORY = "tamirat-wubie/mullu-control-plane"
GATEWAY_URL_VARIABLE = "MULLU_GATEWAY_URL"
EXPECTED_ENVIRONMENT_VARIABLE = "MULLU_EXPECTED_RUNTIME_ENV"
VALID_ENVIRONMENTS = ("pilot", "production")


class CommandRunner(Protocol):
    """Subprocess-compatible command execution contract."""

    def __call__(
        self,
        command: list[str],
        *,
        check: bool,
        capture_output: bool,
        text: bool,
    ) -> subprocess.CompletedProcess[str]:
        """Run one command and return its completed process."""


@dataclass(frozen=True, slots=True)
class DeploymentTarget:
    """Repository variable binding for one deployment witness target."""

    repository: str
    gateway_url: str
    expected_environment: str


def provision_deployment_target(
    *,
    gateway_url: str,
    expected_environment: str,
    repository: str = DEFAULT_REPOSITORY,
    runner: CommandRunner = subprocess.run,
) -> DeploymentTarget:
    """Set repository variables for deployment witness dispatch."""
    normalized_gateway_url = _require_gateway_url(gateway_url)
    _require_expected_environment(expected_environment)
    _set_variable(
        repository=repository,
        variable_name=GATEWAY_URL_VARIABLE,
        value=normalized_gateway_url,
        runner=runner,
    )
    _set_variable(
        repository=repository,
        variable_name=EXPECTED_ENVIRONMENT_VARIABLE,
        value=expected_environment,
        runner=runner,
    )
    return DeploymentTarget(
        repository=repository,
        gateway_url=normalized_gateway_url,
        expected_environment=expected_environment,
    )


def _require_gateway_url(gateway_url: str) -> str:
    normalized = gateway_url.strip().rstrip("/")
    if not normalized:
        raise RuntimeError("gateway URL is required")
    if not normalized.startswith(("https://", "http://")):
        raise RuntimeError("gateway URL must start with http:// or https://")
    return normalized


def _require_expected_environment(expected_environment: str) -> None:
    if expected_environment not in VALID_ENVIRONMENTS:
        raise RuntimeError(
            f"expected environment must be one of {list(VALID_ENVIRONMENTS)}"
        )


def _set_variable(
    *,
    repository: str,
    variable_name: str,
    value: str,
    runner: CommandRunner,
) -> None:
    command = ["gh", "variable", "set", variable_name, "--repo", repository, "--body", value]
    try:
        runner(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise RuntimeError("GitHub CLI executable 'gh' was not found") from exc
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() if exc.stderr else ""
        stdout = exc.stdout.strip() if exc.stdout else ""
        detail = stderr or stdout or f"exit code {exc.returncode}"
        raise RuntimeError(f"failed to set GitHub variable {variable_name}: {detail}") from exc


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse deployment target provisioning CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Provision deployment witness target repository variables."
    )
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", DEFAULT_REPOSITORY))
    parser.add_argument("--gateway-url", default=os.environ.get("MULLU_GATEWAY_URL", ""))
    parser.add_argument(
        "--expected-environment",
        choices=VALID_ENVIRONMENTS,
        default=os.environ.get("MULLU_EXPECTED_RUNTIME_ENV", "pilot"),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for deployment target provisioning."""
    args = parse_args(argv)
    try:
        target = provision_deployment_target(
            repository=args.repo,
            gateway_url=args.gateway_url,
            expected_environment=args.expected_environment,
        )
    except RuntimeError as exc:
        print(f"deployment target provisioning failed: {exc}")
        return 1

    print(f"repository: {target.repository}")
    print(f"gateway_url: {target.gateway_url}")
    print(f"expected_environment: {target.expected_environment}")
    print("deployment target variables set")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
