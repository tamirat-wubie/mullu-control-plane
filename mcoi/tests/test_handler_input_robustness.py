"""Robustness regression: governed handlers must not crash (500) on bad input.

A governed control plane must turn malformed / edge-case input into a bounded
governed error, never an unhandled 500 (a reliability failure and an internal-
detail leak). These tests were added after a fuzz sweep of the full route surface
found two robustness defects:

- GET /api/v1/config/history?limit=-1 -> 500: the handler passed a negative limit
  straight to config_manager.history, which (correctly) rejects it, but the
  handler did not guard the input so the ValueError became an Internal Server
  Error. Now rejected with a governed 422.
- GET /api/v1/ops/imports re-ran a full-tree AST import analysis on every call
  (~30s on the current tree) -- an unauthenticated DoS amplifier. The source tree
  is immutable for the process, so the result is now computed once and cached.

The broad test guards the whole GET surface against the negative-limit class so a
future handler with the same defect fails CI.
"""

from __future__ import annotations

import re

from fastapi.testclient import TestClient

from mcoi_runtime.app.routers.ops import diagnostics
from mcoi_runtime.app.server import app
from mcoi_runtime.app.server_http import iter_inspectable_routes

client = TestClient(app, raise_server_exceptions=False)

# Endpoints that legitimately perform heavy work; excluded from the broad fuzz
# (each is exercised for robustness individually). Keeping them here documents
# the cost rather than silently truncating coverage.
_EXPENSIVE_PATHS = {"/api/v1/ops/imports", "/api/v1/ops/benchmarks"}


def _get_paths() -> list[str]:
    paths: list[str] = []
    for route in iter_inspectable_routes(app):
        methods = getattr(route, "methods", None)
        path = getattr(route, "path", "")
        if methods and "GET" in methods and path.startswith("/api/") and path not in _EXPENSIVE_PATHS:
            paths.append(path)
    return sorted(set(paths))


def test_no_get_handler_returns_500_on_negative_limit_or_offset():
    """No governed GET handler may 500 on a negative limit/offset."""
    failures: list[tuple[str, dict, int]] = []
    for path in _get_paths():
        url = re.sub(r"\{[^}]+\}", "fuzz-id", path)
        for params in ({"limit": "-1"}, {"offset": "-1"}, {"limit": "-1", "offset": "-1"}):
            resp = client.get(url, params=params)
            if resp.status_code == 500:
                failures.append((path, params, resp.status_code))
    assert not failures, f"handlers returned 500 on adversarial query params: {failures}"


def test_config_history_negative_limit_is_bounded():
    assert client.get("/api/v1/config/history", params={"limit": "-1"}).status_code != 500
    assert client.get("/api/v1/config/history", params={"limit": "-99999"}).status_code != 500
    assert client.get("/api/v1/config/history", params={"limit": "0"}).status_code == 200


def test_ops_imports_analysis_is_computed_once_and_cached(monkeypatch):
    """The expensive import analysis must be cached, not recomputed per request."""
    monkeypatch.setattr(diagnostics, "_import_analysis_cache", None)
    calls = {"n": 0}

    def _stub() -> dict:
        calls["n"] += 1
        return {"module_count": 0, "cycles": []}

    monkeypatch.setattr(diagnostics, "_compute_import_analysis", _stub)
    r1 = client.get("/api/v1/ops/imports")
    r2 = client.get("/api/v1/ops/imports")
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json().get("governed") is True
    assert calls["n"] == 1, "import analysis recomputed on every call (DoS amplifier)"
    monkeypatch.setattr(diagnostics, "_import_analysis_cache", None)
