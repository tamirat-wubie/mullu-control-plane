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
    result = validate_gateway_deployment_env({
        "MULLU_ENV": "pilot",
        "MULLU_GATEWAY_DEFER_APPROVED_EXECUTION": "true",
        "MULLU_COMMAND_LEDGER_BACKEND": "postgresql",
        "MULLU_TENANT_IDENTITY_BACKEND": "postgresql",
        "MULLU_REQUIRE_PERSISTENT_TENANT_IDENTITY": "true",
        "MULLU_REQUIRE_COMMAND_ANCHOR": "true",
        "MULLU_COMMAND_ANCHOR_SECRET": "anchor-secret",
        "MULLU_RUNTIME_WITNESS_SECRET": "witness-secret",
    })

    assert result.ok is False
    assert "MULLU_CAPABILITY_WORKER_URL is required" in result.errors
    assert "MULLU_CAPABILITY_WORKER_SECRET is required" in result.errors


def test_production_gateway_env_passes_with_worker_and_witness() -> None:
    result = validate_gateway_deployment_env({
        "MULLU_ENV": "production",
        "MULLU_GATEWAY_DEFER_APPROVED_EXECUTION": "1",
        "MULLU_COMMAND_LEDGER_BACKEND": "postgresql",
        "MULLU_TENANT_IDENTITY_BACKEND": "postgresql",
        "MULLU_REQUIRE_PERSISTENT_TENANT_IDENTITY": "true",
        "MULLU_REQUIRE_COMMAND_ANCHOR": "true",
        "MULLU_COMMAND_ANCHOR_SECRET": "anchor-secret",
        "MULLU_RUNTIME_WITNESS_SECRET": "witness-secret",
        "MULLU_CAPABILITY_WORKER_URL": "https://capability-worker.mullusi.com/capability/execute",
        "MULLU_CAPABILITY_WORKER_SECRET": "worker-secret",
    })

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
    result = validate_gateway_deployment_env({
        "MULLU_ENV": "pilot",
        "MULLU_GATEWAY_DEFER_APPROVED_EXECUTION": "true",
        "MULLU_COMMAND_LEDGER_BACKEND": "postgresql",
        "MULLU_TENANT_IDENTITY_BACKEND": "postgresql",
        "MULLU_REQUIRE_PERSISTENT_TENANT_IDENTITY": "true",
        "MULLU_REQUIRE_COMMAND_ANCHOR": "true",
        "MULLU_COMMAND_ANCHOR_SECRET": "anchor-secret",
        "MULLU_RUNTIME_WITNESS_SECRET": "witness-secret",
        "MULLU_CAPABILITY_WORKER_URL": "https://capability-worker.mullusi.com/capability/execute",
        "MULLU_CAPABILITY_WORKER_SECRET": "worker-secret",
        "MULLU_BROWSER_WORKER_URL": "https://browser-worker.mullusi.com/browser/execute",
        "MULLU_BROWSER_WORKER_SECRET": "browser-secret",
        "MULLU_EMAIL_CALENDAR_WORKER_URL": "https://communication-worker.mullusi.com/email-calendar/execute",
        "MULLU_EMAIL_CALENDAR_WORKER_SECRET": "email-calendar-secret",
    })

    assert result.ok is True
    assert result.errors == ()
    assert result.warnings == ()
    assert result.profile == "pilot"
