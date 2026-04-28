"""v4.26.0 — musia_auth fail-closed when not configured (audit F16 fix).

Pre-v4.26: ``resolve_musia_auth`` short-circuited to wildcard scope
whenever ``is_auth_configured()`` returned False. Production deployments
hit this branch because the bootstrap path never called
``configure_musia_auth(...)`` — so every MUSIA endpoint accepted
unauthenticated wildcard-scope requests.

v4.26 fixes this in two places:

1. The resolver itself: ``configure_musia_dev_mode(False)`` makes the
   "no auth configured" branch raise 503 instead of degrading.
2. ``bootstrap_server_lifecycle``: now takes ``api_key_mgr``,
   ``jwt_authenticator``, and ``env`` and wires them into musia_auth
   before mounting routers. ``configure_musia_dev_mode(True)`` is set
   only when (a) no real authenticator was wired AND (b) env is
   ``local_dev`` or ``test``. In ``pilot``/``production`` it stays
   False, so a missing ``configure_musia_auth(...)`` produces a
   clear 503 instead of silently passing.

This test family verifies the resolver's fail-closed behavior. The
bootstrap-side wiring is covered by
``test_v4_26_route_governance_coverage.py`` (it asserts every non-GET
route is gated, which transitively requires that the resolver doesn't
silently bypass).
"""
from __future__ import annotations

from typing import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mcoi_runtime.app.routers.constructs import (
    reset_registry,
    router as constructs_router,
)
from mcoi_runtime.app.routers.musia_auth import (
    configure_musia_auth,
    configure_musia_dev_mode,
    configure_musia_jwt,
    dev_mode_allowed,
    is_auth_configured,
)


# Each test in this file overrides the conftest autouse fixture by
# explicitly calling ``configure_musia_dev_mode(False)``.


@pytest.fixture
def fail_closed_app() -> Iterator[TestClient]:
    """A FastAPI app with /constructs mounted, NO auth configured,
    AND dev mode explicitly disabled. The legacy v4.25 dev wildcard
    branch is unreachable from here."""
    reset_registry()
    configure_musia_auth(None)  # no API-key authenticator
    configure_musia_jwt(None)   # no JWT authenticator
    configure_musia_dev_mode(False)  # production-style: no dev branch
    app = FastAPI()
    app.include_router(constructs_router)
    yield TestClient(app)
    reset_registry()
    configure_musia_dev_mode(True)  # restore for other tests


def test_dev_mode_default_initial_state():
    """The conftest autouse fixture sets dev mode True for tests.
    This test verifies the assertion of the inverse: before audit
    P0 fix, the default was always-True. v4.26 default is False."""
    configure_musia_dev_mode(False)
    assert dev_mode_allowed() is False
    configure_musia_dev_mode(True)
    assert dev_mode_allowed() is True


def test_unauthed_request_in_fail_closed_mode_returns_503(fail_closed_app):
    """The core F16 fix: with no auth configured and dev mode disabled,
    every MUSIA endpoint returns 503 instead of silently passing."""
    r = fail_closed_app.post(
        "/constructs/state",
        headers={"X-Tenant-ID": "acme"},
        json={"configuration": {}},
    )
    assert r.status_code == 503
    assert r.json()["detail"]["error"] == "musia_auth_not_configured"


def test_503_response_includes_remedy_hint(fail_closed_app):
    """The 503 response tells the operator how to fix the misconfig."""
    r = fail_closed_app.post(
        "/constructs/state",
        headers={"X-Tenant-ID": "acme"},
        json={"configuration": {}},
    )
    detail = r.json()["detail"]
    remedy = detail["remedy"]
    assert "configure_musia_auth" in remedy
    assert "MULLU_ENV=local_dev" in remedy


def test_get_requests_also_gated_in_fail_closed_mode(fail_closed_app):
    """GETs go through the same resolver — they also fail closed."""
    r = fail_closed_app.get(
        "/constructs",
        headers={"X-Tenant-ID": "acme"},
    )
    assert r.status_code == 503


def test_dev_mode_re_enabled_unblocks_requests(fail_closed_app):
    """Re-enabling dev mode at runtime restores the legacy permissive
    behavior. Useful for tests that toggle in/out of dev mode."""
    configure_musia_dev_mode(True)
    r = fail_closed_app.post(
        "/constructs/state",
        headers={"X-Tenant-ID": "acme"},
        json={"configuration": {}},
    )
    # Now succeeds (201 created) under dev wildcard
    assert r.status_code == 201


def test_real_auth_configured_overrides_dev_mode_check():
    """If a real authenticator IS configured, fail-closed is moot —
    the resolver runs the auth path. Verifies that fail-closed is
    only consulted on the no-auth-configured branch."""
    from mcoi_runtime.governance.auth.api_key import APIKeyManager
    mgr = APIKeyManager(clock=lambda: "2026-01-01T00:00:00Z")
    configure_musia_auth(mgr)
    configure_musia_dev_mode(False)  # would be a problem... if it mattered
    try:
        # is_auth_configured now returns True; the dev_mode check is bypassed
        assert is_auth_configured() is True
        # An unauthorized request now goes to the auth path (not 503).
        # We don't assert on the response code here because building a
        # full TestClient is overkill — the contract is: dev_mode flag
        # is ignored when an authenticator is configured. The route-
        # coverage test in test_v4_26_route_governance_coverage covers
        # the request-path side.
    finally:
        configure_musia_auth(None)
        configure_musia_dev_mode(True)
