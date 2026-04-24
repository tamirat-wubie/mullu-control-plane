#!/usr/bin/env python3
"""Validate gateway deployment environment for terminal closure operations.

Purpose: Checks that pilot/production gateway deployments have the command
worker, runtime witness, and restricted capability worker configuration needed
for certified closure.
Governance scope: gateway deployment configuration only.
Dependencies: standard-library environment mapping.
Invariants:
  - Pilot/production require deferred command execution.
  - Pilot/production require durable command and tenant identity stores.
  - Pilot/production require command anchor and runtime witness secrets.
  - Pilot/production require restricted capability worker URL and secret.
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from typing import Mapping


STRICT_PROFILES = {"pilot", "pilot_prod", "prod", "production"}


@dataclass(frozen=True, slots=True)
class GatewayDeploymentCheck:
    """Result of validating one gateway deployment environment."""

    profile: str
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        """Return whether deployment configuration satisfies hard checks."""
        return not self.errors


def validate_gateway_deployment_env(env: Mapping[str, str]) -> GatewayDeploymentCheck:
    """Validate gateway deployment variables for the selected profile."""
    profile = (env.get("MULLU_ENV", "local_dev") or "local_dev").strip().lower()
    errors: list[str] = []
    warnings: list[str] = []

    if profile not in STRICT_PROFILES:
        if not env.get("MULLU_CAPABILITY_WORKER_URL") and env.get("MULLU_CAPABILITY_WORKER_SECRET"):
            errors.append("MULLU_CAPABILITY_WORKER_URL is required when worker secret is set")
        if env.get("MULLU_CAPABILITY_WORKER_URL") and not env.get("MULLU_CAPABILITY_WORKER_SECRET"):
            errors.append("MULLU_CAPABILITY_WORKER_SECRET is required when worker URL is set")
        return GatewayDeploymentCheck(profile=profile, errors=tuple(errors), warnings=tuple(warnings))

    _require_truthy(env, "MULLU_GATEWAY_DEFER_APPROVED_EXECUTION", errors)
    _require_value(env, "MULLU_COMMAND_LEDGER_BACKEND", "postgresql", errors)
    _require_value(env, "MULLU_TENANT_IDENTITY_BACKEND", "postgresql", errors)
    _require_truthy(env, "MULLU_REQUIRE_PERSISTENT_TENANT_IDENTITY", errors)
    _require_truthy(env, "MULLU_REQUIRE_COMMAND_ANCHOR", errors)
    _require_present(env, "MULLU_COMMAND_ANCHOR_SECRET", errors)
    _require_present(env, "MULLU_RUNTIME_WITNESS_SECRET", errors)
    _require_present(env, "MULLU_CAPABILITY_WORKER_URL", errors)
    _require_present(env, "MULLU_CAPABILITY_WORKER_SECRET", errors)

    if env.get("MULLU_CAPABILITY_WORKER_URL", "").startswith("http://"):
        warnings.append("MULLU_CAPABILITY_WORKER_URL should use https outside a private cluster")
    if env.get("MULLU_COMMAND_LEDGER_BACKEND") == "memory":
        errors.append("MULLU_COMMAND_LEDGER_BACKEND must not be memory in pilot/production")
    if env.get("MULLU_TENANT_IDENTITY_BACKEND") == "memory":
        errors.append("MULLU_TENANT_IDENTITY_BACKEND must not be memory in pilot/production")

    return GatewayDeploymentCheck(profile=profile, errors=tuple(errors), warnings=tuple(warnings))


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for gateway deployment environment validation."""
    parser = argparse.ArgumentParser(description="Validate Mullu gateway deployment environment.")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as failures.")
    args = parser.parse_args(argv)
    result = validate_gateway_deployment_env(os.environ)
    if result.ok and (not args.strict or not result.warnings):
        print(f"gateway deployment env ok profile={result.profile}")
        for warning in result.warnings:
            print(f"warning: {warning}")
        return 0
    for error in result.errors:
        print(f"error: {error}", file=sys.stderr)
    if args.strict:
        for warning in result.warnings:
            print(f"warning: {warning}", file=sys.stderr)
    return 1


def _require_present(env: Mapping[str, str], name: str, errors: list[str]) -> None:
    if not env.get(name, "").strip():
        errors.append(f"{name} is required")


def _require_truthy(env: Mapping[str, str], name: str, errors: list[str]) -> None:
    value = env.get(name, "")
    if value.strip().lower() not in {"1", "true", "yes", "on"}:
        errors.append(f"{name} must be true")


def _require_value(env: Mapping[str, str], name: str, expected: str, errors: list[str]) -> None:
    value = env.get(name, "").strip().lower()
    if value != expected:
        errors.append(f"{name} must be {expected}")


if __name__ == "__main__":
    raise SystemExit(main())
