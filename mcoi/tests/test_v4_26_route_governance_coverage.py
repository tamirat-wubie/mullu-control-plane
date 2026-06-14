"""v4.26.0 — every non-GET route is gated by middleware OR an auth dependency.

This is the structural fix for audit fracture F1 (and the underlying
class of bug that produced F14: a POST endpoint added with no
``Depends(require_*)`` slipped into production unnoticed).

The invariant: a route that mutates state, runs heavy CPU, or returns
governance-shaped artifacts MUST be gated. There are exactly two ways
to gate:

1. Live under the ``/api/`` prefix → ``GovernanceMiddleware`` runs the
   guard chain (auth + tenant + RBAC + content safety + rate limit + budget).
2. Live elsewhere AND declare a FastAPI ``Depends(require_read |
   require_write | require_admin | resolve_musia_auth)`` dependency,
   so ``musia_auth`` enforces auth + scope.

Anything else — a POST/PUT/DELETE route at a non-``/api/`` path with no
``Depends(require_*)`` — slipped through the cracks. Pre-v4.26 this
class included:

- ``POST /ucja/qualify`` and ``POST /ucja/define-job`` (F14)
- All six ``POST /domains/*/process`` endpoints (F13: wrong scope; F1:
  bypassed middleware. Fix: scope split + cursor on ``persist_run``.)

This test walks every router mounted by ``include_default_routers``
and asserts the invariant. New routers added without proper gating
will fail this test on the PR.

A small allow-list exists for endpoints that are deliberately
unauthenticated (health checks, public Mfidel grid reads, OpenAPI
docs). Each entry is annotated with WHY it's exempt.
"""
from __future__ import annotations

import inspect
from collections.abc import Iterable
from typing import Any

from fastapi import FastAPI

from mcoi_runtime.app.server_http import include_default_routers, iter_effective_app_routes


# Endpoints that are deliberately unauthenticated. Each entry must
# carry a justification — anything new added here is a documented
# decision, not a forgotten gating step.
_INTENTIONALLY_OPEN: dict[tuple[str, str], str] = {
    # Health endpoints — operational liveness/readiness probes
    ("GET", "/health"): "Liveness probe; returns no tenant data.",
    ("GET", "/health/ready"): "Readiness probe; returns no tenant data.",
    ("GET", "/health/live"): "Liveness probe variant.",
    ("GET", "/healthz"): "K8s-style liveness alias.",

    # Public Mfidel reads — the substrate grid is a published constant
    ("GET", "/mfidel/grid"): "Public Mfidel grid; no per-tenant data.",
    ("GET", "/mfidel/atom/{row}/{col}"): "Public atom lookup.",
    ("GET", "/mfidel/overlay/{row}/{col}"): "Public overlay lookup.",
    ("GET", "/mfidel/stats"): "Public soak counters; no per-tenant data.",

    # Domain index — lists the six adapter names, no tenant data
    ("GET", "/domains"): "Lists adapter names; no tenant data.",

    # Platform-level operational probes (pre-MUSIA, deliberately open)
    ("GET", "/ready"): "Readiness probe; no tenant data.",
    ("GET", "/metrics"): (
        "Platform-wide Prometheus exposition; no per-tenant labels. "
        "If per-tenant data ever lands here, gate at musia.read."
    ),

    # Public trust boundary — the verification key is deliberately
    # unauthenticated: its entire purpose is to let an external party
    # verify signed receipts WITHOUT trusting/authenticating to this
    # process. Exposes only the Ed25519 public key + key_id (or an
    # honest unsigned marker); no secret, no per-tenant data, no state.
    ("GET", "/trust/verification-key"): (
        "Public Ed25519 verification key; intentionally open so third "
        "parties can independently verify receipts. No secret/tenant "
        "data — publishing the public half is the point."
    ),

    # OpenAPI / schema introspection (FastAPI defaults; not from our routers)
    # — noted here for completeness; FastAPI mounts these automatically.
    ("GET", "/openapi.json"): "OpenAPI schema; FastAPI default, no tenant data.",
    ("GET", "/docs"): "Swagger UI; FastAPI default, no tenant data.",
    ("GET", "/docs/oauth2-redirect"): "Swagger OAuth redirect; FastAPI default.",
    ("GET", "/redoc"): "ReDoc UI; FastAPI default, no tenant data.",
}


# Auth dependencies that count as "gated" for the purpose of this test.
# Add new ``require_*`` factories here as they're introduced.
_AUTH_DEPENDENCY_NAMES: frozenset[str] = frozenset({
    "require_read",
    "require_write",
    "require_admin",
    "resolve_musia_auth",
    "resolve_musia_tenant",
    "_resolve_domain_auth",  # domains.py helper that wraps resolve_musia_auth
})


def _gather_routes() -> Iterable[Any]:
    """Build the assembled app and yield every effective route it mounts."""
    app = FastAPI()
    include_default_routers(app)
    for route in iter_effective_app_routes(app):
        if (
            hasattr(route, "path")
            and hasattr(route, "methods")
            and hasattr(route, "endpoint")
        ):
            yield route


def _route_uses_auth_dependency(route: Any) -> bool:
    """Return True if the route's signature names any known auth dependency.

    We inspect the *handler function's source* (substring match for any
    ``require_read``, ``require_write``, etc.). This is approximate but
    catches the cases that matter: handlers that explicitly opt into
    musia_auth via ``Depends(require_*)`` or ``Depends(resolve_musia_*)``.
    A handler that imports a different module-level helper that wraps
    one of these (like the domains.py ``_resolve_domain_auth``) is
    covered as long as the helper name is in ``_AUTH_DEPENDENCY_NAMES``.
    """
    try:
        src = inspect.getsource(route.endpoint)
    except (OSError, TypeError):
        return False
    return any(dep in src for dep in _AUTH_DEPENDENCY_NAMES)


def _route_under_api_prefix(route: Any) -> bool:
    """True if the route is gated by GovernanceMiddleware (path under /api/)."""
    return route.path.startswith("/api/")


def _is_intentionally_open(route: Any) -> bool:
    for method in route.methods:
        if (method, route.path) in _INTENTIONALLY_OPEN:
            return True
    return False


def _is_gated(route: Any) -> bool:
    return (
        _route_under_api_prefix(route)
        or _route_uses_auth_dependency(route)
        or _is_intentionally_open(route)
    )


# ============================================================
# The invariant test
# ============================================================


def test_every_non_get_route_is_gated():
    """Every POST/PUT/PATCH/DELETE route must either be under /api/
    (middleware-gated) or carry a Depends(require_*) auth dependency.

    Pre-v4.26 violators included:
      - POST /ucja/qualify, POST /ucja/define-job (F14)
      - POST /domains/*/process with the wrong scope (F13)
      - 7 router prefixes that bypass the /api/ middleware (F1)

    The first two are fixed in v4.26. F1 (router-prefix bypass) is
    not a regression of THIS test (musia_auth on the same routers
    closes the gap), but the test prevents future routers added with
    neither gating mechanism.
    """
    violations: list[str] = []
    for route in _gather_routes():
        write_methods = route.methods - {"GET", "HEAD", "OPTIONS"}
        if not write_methods:
            continue
        if _is_gated(route):
            continue
        violations.append(
            f"  {sorted(write_methods)} {route.path} "
            f"(handler={route.endpoint.__module__}.{route.endpoint.__name__})"
        )

    assert not violations, (
        "Found ungated mutating route(s). Each must either:\n"
        "  - live under /api/ (middleware-gated), OR\n"
        "  - declare a Depends(require_read|require_write|require_admin|"
        "resolve_musia_auth) dependency, OR\n"
        "  - be added to _INTENTIONALLY_OPEN with a written justification.\n"
        "Violators:\n" + "\n".join(violations)
    )


def test_get_routes_are_all_either_gated_or_intentionally_open():
    """GET routes that return per-tenant data must be gated. GETs that
    return public/operational data (health, mfidel grid) must appear
    in ``_INTENTIONALLY_OPEN`` so the decision is explicit rather than
    accidental.

    This test is more permissive than the non-GET test because read-only
    health/probe endpoints are normal. The point is to surface
    *unintentionally* open GETs by forcing each to be either gated
    or annotated.
    """
    unannotated_open: list[str] = []
    for route in _gather_routes():
        if "GET" not in route.methods:
            continue
        if _is_gated(route):
            continue
        # Not gated, not annotated — surface for review
        unannotated_open.append(
            f"  GET {route.path} "
            f"(handler={route.endpoint.__module__}.{route.endpoint.__name__})"
        )
    assert not unannotated_open, (
        "Found unannotated open GET route(s). Each should either:\n"
        "  - declare an auth dependency, OR\n"
        "  - be added to _INTENTIONALLY_OPEN with a written justification.\n"
        "Violators:\n" + "\n".join(unannotated_open)
    )


def test_intentionally_open_table_is_documented():
    """Every entry in the allow-list must have a non-empty justification."""
    for key, why in _INTENTIONALLY_OPEN.items():
        method, path = key
        assert isinstance(why, str) and why.strip(), (
            f"_INTENTIONALLY_OPEN[{method} {path}] has empty justification"
        )


def test_auth_dependency_names_includes_known_factories():
    """Sanity: the allow-list of dependency names contains the
    standard musia_auth factories. Catches typos/renames."""
    expected = {"require_read", "require_write", "require_admin", "resolve_musia_auth"}
    missing = expected - _AUTH_DEPENDENCY_NAMES
    assert not missing, f"missing standard auth dep names: {missing}"


def test_no_duplicate_route_registrations():
    """No two routes may register the same ``(method, path)`` pair.

    Walks the assembled app's ``APIRoute`` list directly (via
    ``_gather_routes``), NOT the generated OpenAPI spec: FastAPI collapses
    two same-``(method, path)`` registrations into a single
    ``paths[path][method]`` entry, so a spec walk is blind to a genuine
    double-registration. The route list keeps both physical registrations.

    Regression guard for ``GET /api/v1/traces/summary``, which was defined
    in both ``routers/agent.py`` (load-bearing -- must register before the
    sibling ``/api/v1/traces/{trace_id}`` param route, else "summary" is
    captured as a trace_id) and ``routers/ops/summaries.py`` (dead
    duplicate, removed). The duplicate raised a FastAPI "Duplicate
    Operation ID" warning at OpenAPI generation.
    """
    seen: dict[tuple[str, str], int] = {}
    for route in _gather_routes():
        for method in route.methods - {"HEAD", "OPTIONS"}:
            key = (method, route.path)
            seen[key] = seen.get(key, 0) + 1
    duplicates = sorted(pair for pair, count in seen.items() if count > 1)
    assert not duplicates, f"Duplicate route registration(s): {duplicates}"
