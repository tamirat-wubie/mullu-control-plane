"""Purpose: shared test infrastructure — path setup and reusable fixtures.
Governance scope: test support only.
Dependencies: Python standard library, pytest, governance modules.
Invariants: test imports remain explicit and deterministic across environments.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

TEST_ROOT = Path(__file__).resolve().parent.parent
if str(TEST_ROOT) not in sys.path:
    sys.path.insert(0, str(TEST_ROOT))


# v4.26.0 (audit P0): the production resolver now fails closed when no
# auth is configured. Tests that call ``configure_musia_auth(None)`` to
# reset state would otherwise hit the fail-closed path. This autouse
# fixture restores the legacy "tests run in dev mode" default.
# Individual tests that want to verify the fail-closed behavior can call
# ``configure_musia_dev_mode(False)`` inside their body.
@pytest.fixture(autouse=True)
def _allow_musia_dev_mode_in_tests():
    from mcoi_runtime.app.routers.musia_auth import configure_musia_dev_mode
    configure_musia_dev_mode(True)
    yield
    configure_musia_dev_mode(True)


# ═══ Shared Fixtures ═══


def _test_clock() -> str:
    return "2026-01-01T00:00:00Z"


@pytest.fixture
def clock():
    """Deterministic clock for governance tests."""
    return _test_clock


@pytest.fixture
def pii_scanner():
    """Pre-configured PII scanner for tests."""
    from mcoi_runtime.core.pii_scanner import PIIScanner
    return PIIScanner()


@pytest.fixture
def content_safety_chain():
    """Default content safety chain for tests."""
    from mcoi_runtime.core.content_safety import build_default_safety_chain
    return build_default_safety_chain()


@pytest.fixture
def tenant_gating_registry(clock):
    """Tenant gating registry with in-memory store."""
    from mcoi_runtime.core.tenant_gating import TenantGatingRegistry
    from mcoi_runtime.persistence.postgres_governance_stores import InMemoryTenantGatingStore
    return TenantGatingRegistry(clock=clock, store=InMemoryTenantGatingStore())


@pytest.fixture
def governance_stores():
    """In-memory governance store bundle for tests."""
    from mcoi_runtime.persistence.postgres_governance_stores import create_governance_stores
    return create_governance_stores("memory")


@pytest.fixture
def test_client():
    """FastAPI TestClient with local_dev config."""
    os.environ["MULLU_ENV"] = "local_dev"
    os.environ["MULLU_DB_BACKEND"] = "memory"
    from fastapi.testclient import TestClient
    from mcoi_runtime.app.server import app
    return TestClient(app)
