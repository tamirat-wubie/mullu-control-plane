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

MCOI_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = MCOI_ROOT.parent

for import_root in (REPO_ROOT, MCOI_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))


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


# Many router tests register stub subsystems (MetricsStub, FixedClock, etc.)
# into the module-global ``deps`` container. Without isolation, a stub from
# one test leaks into the next test's ``mcoi_runtime.app.server.app`` import
# path, and a real handler then calls a method the stub does not implement
# (e.g. MetricsStub.to_dict).
#
# server.py registers real subsystems at import time. We import it once at
# session start so the baseline snapshot contains the production wiring,
# then restore that baseline after each test — stubs added by the test are
# discarded, but real subsystems remain available for tests that exercise
# the production app.
@pytest.fixture(scope="session")
def _router_deps_baseline():
    os.environ.setdefault("MULLU_ENV", "local_dev")
    os.environ.setdefault("MULLU_DB_BACKEND", "memory")
    os.environ.setdefault("MULLU_CERT_INTERVAL", "0")
    import mcoi_runtime.app.server  # noqa: F401 — triggers deps registration
    from mcoi_runtime.app.routers.deps import deps
    llm_bridge = deps._store.get("llm_bridge")
    return {
        "store": dict(deps._store),
        "llm_bridge_complete": getattr(llm_bridge, "complete", None),
        "llm_bridge_chat": getattr(llm_bridge, "chat", None),
    }


@pytest.fixture(autouse=True)
def _isolate_router_deps(_router_deps_baseline):
    from mcoi_runtime.app.routers.deps import deps
    _restore_router_deps_baseline(deps, _router_deps_baseline)
    yield
    _restore_router_deps_baseline(deps, _router_deps_baseline)


def _restore_router_deps_baseline(deps, baseline: dict[str, object]) -> None:
    baseline_store = baseline["store"]
    if not isinstance(baseline_store, dict):
        raise TypeError("router deps baseline store must be a dict")
    deps._store.clear()
    deps._store.update(baseline_store)
    llm_bridge = deps._store.get("llm_bridge")
    if llm_bridge is not None:
        llm_complete = baseline.get("llm_bridge_complete")
        llm_chat = baseline.get("llm_bridge_chat")
        if llm_complete is not None:
            llm_bridge.complete = llm_complete
        if llm_chat is not None:
            llm_bridge.chat = llm_chat
    # Singletons in the baseline carry their own internal state (replay
    # traces, audit ledger entries, etc.). Reset the ones tests depend on.
    recorder = deps._store.get("replay_recorder")
    if recorder is not None:
        recorder._traces.clear()
        recorder._completed.clear()
        recorder._frame_counter = 0


# god_mode_engine and god_mode_registry both expose a process-wide
# singleton (set_engine / set_registry) that test fixtures install fresh
# instances into via _client(). Without explicit teardown, an engine/
# registry installed by one test persists across tests until the next
# test calls set_engine() — meaning tests that assume "fresh state on
# import" silently inherit prior state. Two failures in PR #578 trace
# directly to this: test_health_endpoint_after_arm_and_issue and
# test_list_receipts_after_consumption pass alone but fail intermittently
# when the suite runs in certain orders.
#
# This autouse fixture clears both god_mode singletons after every test
# so each test starts from None and must call _client() (or its own
# fixture) to set up state explicitly.
@pytest.fixture(autouse=True)
def _isolate_god_mode_state():
    yield
    try:
        from mcoi_runtime.core.god_mode_engine import set_engine
        from mcoi_runtime.core.god_mode_registry import set_registry
    except ImportError:
        return
    set_engine(None)
    set_registry(None)


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
    from mcoi_runtime.governance.guards.content_safety import build_default_safety_chain
    return build_default_safety_chain()


@pytest.fixture
def tenant_gating_registry(clock):
    """Tenant gating registry with in-memory store."""
    from mcoi_runtime.governance.guards.tenant_gating import TenantGatingRegistry
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
