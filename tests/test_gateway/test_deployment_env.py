"""Gateway deployment environment validation tests.

Tests: pilot/production closure, witness, ledger, and capability-worker
configuration checks.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.validate_gateway_deployment_env import validate_gateway_deployment_env  # noqa: E402


def test_pilot_requires_capability_worker_pairing() -> None:
    env = _strict_env()
    del env["MULLU_CAPABILITY_WORKER_URL"]
    del env["MULLU_CAPABILITY_WORKER_SECRET"]
    result = validate_gateway_deployment_env(env)

    assert result.ok is False
    assert "MULLU_CAPABILITY_WORKER_URL is required" in result.errors
    assert "MULLU_CAPABILITY_WORKER_SECRET is required" in result.errors


def test_production_gateway_env_passes_with_worker_and_witness() -> None:
    result = validate_gateway_deployment_env(_strict_env(MULLU_ENV="production"))

    assert result.ok is True
    assert result.errors == ()
    assert result.warnings == ()


def test_local_worker_partial_pairing_fails() -> None:
    result = validate_gateway_deployment_env({
        "MULLU_ENV": "local_dev",
        "MULLU_CAPABILITY_WORKER_URL": "http://localhost:8010/capability/execute",
    })

    assert result.ok is False
    assert result.errors == ("MULLU_CAPABILITY_WORKER_SECRET is required when worker URL is set",)


def test_local_adapter_worker_partial_pairing_fails() -> None:
    result = validate_gateway_deployment_env({
        "MULLU_ENV": "local_dev",
        "MULLU_BROWSER_WORKER_URL": "http://localhost:8020/browser/execute",
    })

    assert result.ok is False
    assert result.profile == "local_dev"
    assert result.errors == ("MULLU_BROWSER_WORKER_SECRET is required when worker URL is set",)
    assert result.warnings == ()


def test_local_email_calendar_worker_partial_pairing_fails() -> None:
    result = validate_gateway_deployment_env({
        "MULLU_ENV": "local_dev",
        "MULLU_EMAIL_CALENDAR_WORKER_SECRET": "email-calendar-secret",
    })

    assert result.ok is False
    assert result.profile == "local_dev"
    assert result.errors == ("MULLU_EMAIL_CALENDAR_WORKER_URL is required when worker secret is set",)
    assert result.warnings == ()


def test_pilot_adapter_worker_pairing_accepts_complete_signed_endpoint() -> None:
    result = validate_gateway_deployment_env(
        _strict_env(
            MULLU_BROWSER_WORKER_URL="https://browser-worker.mullusi.com/browser/execute",
            MULLU_BROWSER_WORKER_SECRET=_secret("browser"),
            MULLU_EMAIL_CALENDAR_WORKER_URL=(
                "https://communication-worker.mullusi.com/email-calendar/execute"
            ),
            MULLU_EMAIL_CALENDAR_WORKER_SECRET=_secret("email-calendar"),
        )
    )

    assert result.ok is True
    assert result.errors == ()
    assert result.warnings == ()
    assert result.profile == "pilot"


def test_pilot_requires_primary_postgres_api_auth_and_conformance_secret() -> None:
    env = _strict_env()
    del env["MULLU_DB_URL"]
    del env["MULLU_RUNTIME_CONFORMANCE_SECRET"]
    env["MULLU_DB_BACKEND"] = "memory"
    env["MULLU_API_AUTH_REQUIRED"] = "false"

    result = validate_gateway_deployment_env(env)

    assert result.ok is False
    assert "MULLU_DB_BACKEND must be postgresql" in result.errors
    assert "MULLU_DB_URL is required" in result.errors
    assert "MULLU_API_AUTH_REQUIRED must be true" in result.errors
    assert "MULLU_RUNTIME_CONFORMANCE_SECRET is required" in result.errors


def test_pilot_rejects_wildcard_cors_origin() -> None:
    env = _strict_env(MULLU_CORS_ORIGINS="*")

    result = validate_gateway_deployment_env(env)

    assert result.ok is False
    assert result.profile == "pilot"
    assert "MULLU_CORS_ORIGINS must not contain wildcard origins" in result.errors


def test_pilot_allows_private_cluster_http_worker_url_without_warning() -> None:
    env = _strict_env(
        MULLU_CAPABILITY_WORKER_URL="http://capability-worker:8010/capability/execute",
        MULLU_BROWSER_WORKER_URL="http://browser-worker:8020/browser/execute",
        MULLU_BROWSER_WORKER_SECRET=_secret("browser"),
    )

    result = validate_gateway_deployment_env(env)

    assert result.ok is True
    assert result.errors == ()
    assert result.warnings == ()


def test_pilot_warns_on_public_http_worker_url() -> None:
    env = _strict_env(
        MULLU_CAPABILITY_WORKER_URL="http://capability-worker.example.com/capability/execute",
    )

    result = validate_gateway_deployment_env(env)

    assert result.ok is True
    assert result.errors == ()
    assert "MULLU_CAPABILITY_WORKER_URL should use https outside a private cluster" in result.warnings


def test_pilot_warns_on_short_secret_material() -> None:
    env = _strict_env(MULLU_COMMAND_ANCHOR_SECRET="short")

    result = validate_gateway_deployment_env(env)

    assert result.ok is True
    assert result.errors == ()
    assert "MULLU_COMMAND_ANCHOR_SECRET should be generated with at least 32 bytes of entropy" in result.warnings


def _strict_env(**overrides: str) -> dict[str, str]:
    env = {
        "MULLU_ENV": "pilot",
        "MULLU_GATEWAY_DEFER_APPROVED_EXECUTION": "true",
        "MULLU_API_AUTH_REQUIRED": "true",
        "MULLU_DB_BACKEND": "postgresql",
        "MULLU_DB_URL": "postgresql://mullu:secret@postgres:5432/mullu",
        "MULLU_CORS_ORIGINS": "https://dashboard.mullusi.com,http://localhost:3000",
        "MULLU_ENCRYPTION_KEY": _secret("encryption"),
        "MULLU_STATE_DIR": "/var/lib/mullu/state",
        "MULLU_COMMAND_LEDGER_BACKEND": "postgresql",
        "MULLU_COMMAND_LEDGER_DB_URL": "postgresql://mullu:secret@postgres:5432/mullu",
        "MULLU_TENANT_IDENTITY_BACKEND": "postgresql",
        "MULLU_REQUIRE_PERSISTENT_TENANT_IDENTITY": "true",
        "MULLU_REQUIRE_COMMAND_ANCHOR": "true",
        "MULLU_COMMAND_ANCHOR_SECRET": _secret("anchor"),
        "MULLU_COMMAND_ANCHOR_KEY_ID": "pilot-command-anchor-v1",
        "MULLU_GATEWAY_APPROVAL_SECRET": _secret("approval"),
        "MULLU_RUNTIME_WITNESS_SECRET": _secret("runtime-witness"),
        "MULLU_RUNTIME_CONFORMANCE_SECRET": _secret("runtime-conformance"),
        "MULLU_CAPABILITY_WORKER_URL": "https://capability-worker.mullusi.com/capability/execute",
        "MULLU_CAPABILITY_WORKER_SECRET": _secret("worker"),
    }
    env.update(overrides)
    return env


def _secret(label: str) -> str:
    return f"{label}-" + "0" * 64
