#!/usr/bin/env python3
"""Validate gateway deployment environment for terminal closure operations.

Purpose: Checks that pilot/production gateway deployments have the command
worker, runtime witness, and restricted capability worker configuration needed
for certified closure.
Governance scope: gateway deployment configuration only.
Dependencies: standard-library environment mapping.
Invariants:
  - Pilot/production require explicit API auth and durable primary storage.
  - Pilot/production require deferred command execution.
  - Pilot/production require durable command and tenant identity stores.
  - Pilot/production require command anchor, approval, and runtime witness secrets.
  - Pilot/production require restricted capability worker URL and secret.
  - Pilot/production CORS origins must be explicit and non-wildcard.
  - Optional adapter worker URLs and secrets must be configured as pairs.
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from typing import Mapping
from urllib.parse import urlparse


STRICT_PROFILES = {"pilot", "pilot_prod", "prod", "production"}
STRICT_SECRET_NAMES = (
    "MULLU_ENCRYPTION_KEY",
    "MULLU_COMMAND_ANCHOR_SECRET",
    "MULLU_GATEWAY_APPROVAL_SECRET",
    "MULLU_RUNTIME_WITNESS_SECRET",
    "MULLU_RUNTIME_CONFORMANCE_SECRET",
    "MULLU_CAPABILITY_WORKER_SECRET",
)


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

    _require_worker_pair(env, "MULLU_BROWSER_WORKER_URL", "MULLU_BROWSER_WORKER_SECRET", errors)
    _require_worker_pair(env, "MULLU_DOCUMENT_WORKER_URL", "MULLU_DOCUMENT_WORKER_SECRET", errors)
    _require_worker_pair(env, "MULLU_VOICE_WORKER_URL", "MULLU_VOICE_WORKER_SECRET", errors)
    _require_worker_pair(env, "MULLU_EMAIL_CALENDAR_WORKER_URL", "MULLU_EMAIL_CALENDAR_WORKER_SECRET", errors)

    if profile not in STRICT_PROFILES:
        _require_worker_pair(env, "MULLU_CAPABILITY_WORKER_URL", "MULLU_CAPABILITY_WORKER_SECRET", errors)
        return GatewayDeploymentCheck(profile=profile, errors=tuple(errors), warnings=tuple(warnings))

    _require_truthy(env, "MULLU_GATEWAY_DEFER_APPROVED_EXECUTION", errors)
    _require_truthy(env, "MULLU_API_AUTH_REQUIRED", errors)
    _require_value(env, "MULLU_DB_BACKEND", "postgresql", errors)
    _require_present(env, "MULLU_DB_URL", errors)
    _require_present(env, "MULLU_ENCRYPTION_KEY", errors)
    _require_present(env, "MULLU_STATE_DIR", errors)
    _require_explicit_cors_origins(env, errors)
    _require_value(env, "MULLU_COMMAND_LEDGER_BACKEND", "postgresql", errors)
    _require_present(env, "MULLU_COMMAND_LEDGER_DB_URL", errors)
    _require_value(env, "MULLU_TENANT_IDENTITY_BACKEND", "postgresql", errors)
    _require_truthy(env, "MULLU_REQUIRE_PERSISTENT_TENANT_IDENTITY", errors)
    _require_truthy(env, "MULLU_REQUIRE_COMMAND_ANCHOR", errors)
    _require_present(env, "MULLU_COMMAND_ANCHOR_SECRET", errors)
    _require_present(env, "MULLU_COMMAND_ANCHOR_KEY_ID", errors)
    _require_present(env, "MULLU_GATEWAY_APPROVAL_SECRET", errors)
    _require_present(env, "MULLU_RUNTIME_WITNESS_SECRET", errors)
    _require_present(env, "MULLU_RUNTIME_CONFORMANCE_SECRET", errors)
    _require_present(env, "MULLU_CAPABILITY_WORKER_URL", errors)
    _require_present(env, "MULLU_CAPABILITY_WORKER_SECRET", errors)
    _warn_short_secrets(env, warnings)

    if _is_public_http_url(env.get("MULLU_CAPABILITY_WORKER_URL", "")):
        warnings.append("MULLU_CAPABILITY_WORKER_URL should use https outside a private cluster")
    for adapter_url_name in (
        "MULLU_BROWSER_WORKER_URL",
        "MULLU_DOCUMENT_WORKER_URL",
        "MULLU_VOICE_WORKER_URL",
        "MULLU_EMAIL_CALENDAR_WORKER_URL",
    ):
        if _is_public_http_url(env.get(adapter_url_name, "")):
            warnings.append(f"{adapter_url_name} should use https outside a private cluster")
    if env.get("MULLU_COMMAND_LEDGER_BACKEND") == "memory":
        errors.append("MULLU_COMMAND_LEDGER_BACKEND must not be memory in pilot/production")
    if env.get("MULLU_TENANT_IDENTITY_BACKEND") == "memory":
        errors.append("MULLU_TENANT_IDENTITY_BACKEND must not be memory in pilot/production")
    if env.get("MULLU_DB_BACKEND") == "memory":
        errors.append("MULLU_DB_BACKEND must not be memory in pilot/production")

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


def _require_worker_pair(env: Mapping[str, str], url_name: str, secret_name: str, errors: list[str]) -> None:
    has_url = bool(env.get(url_name, "").strip())
    has_secret = bool(env.get(secret_name, "").strip())
    if not has_url and has_secret:
        errors.append(f"{url_name} is required when worker secret is set")
    if has_url and not has_secret:
        errors.append(f"{secret_name} is required when worker URL is set")


def _require_explicit_cors_origins(env: Mapping[str, str], errors: list[str]) -> None:
    origins = [origin.strip() for origin in env.get("MULLU_CORS_ORIGINS", "").split(",") if origin.strip()]
    if not origins:
        errors.append("MULLU_CORS_ORIGINS is required")
        return
    if "*" in origins:
        errors.append("MULLU_CORS_ORIGINS must not contain wildcard origins")


def _require_truthy(env: Mapping[str, str], name: str, errors: list[str]) -> None:
    value = env.get(name, "")
    if value.strip().lower() not in {"1", "true", "yes", "on"}:
        errors.append(f"{name} must be true")


def _require_value(env: Mapping[str, str], name: str, expected: str, errors: list[str]) -> None:
    value = env.get(name, "").strip().lower()
    if value != expected:
        errors.append(f"{name} must be {expected}")


def _is_public_http_url(value: str) -> bool:
    parsed = urlparse(value)
    if parsed.scheme != "http":
        return False
    hostname = (parsed.hostname or "").lower()
    if hostname in {"localhost", "127.0.0.1", "::1"}:
        return False
    if hostname.endswith(".svc") or ".svc." in hostname:
        return False
    if "." not in hostname:
        return False
    return True


def _warn_short_secrets(env: Mapping[str, str], warnings: list[str]) -> None:
    for name in STRICT_SECRET_NAMES:
        value = env.get(name, "").strip()
        if value and len(value) < 32:
            warnings.append(f"{name} should be generated with at least 32 bytes of entropy")


if __name__ == "__main__":
    raise SystemExit(main())
