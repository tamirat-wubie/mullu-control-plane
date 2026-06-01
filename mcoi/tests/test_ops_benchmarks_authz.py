"""Operator-gating for the expensive governance-benchmark endpoint.

POST /api/v1/ops/benchmarks runs the full governance benchmark suite (several
seconds of CPU per call). Ungated, it is a denial-of-service amplifier -- any
caller could repeatedly trigger multi-second benchmark runs. It now requires the
musia.admin scope (it is an operator diagnostic). In dev mode the check is a
no-op, so existing suites are unaffected; in auth mode a non-admin caller is
rejected with 403 before the suite runs.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import NoReturn

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mcoi_runtime.app.routers.musia_auth import configure_musia_auth
from mcoi_runtime.app.routers.ops.diagnostics import router as diagnostics_router
from mcoi_runtime.governance.auth.api_key import APIKeyManager


@pytest.fixture
def auth_client() -> Iterator[tuple[TestClient, APIKeyManager]]:
    manager = APIKeyManager()
    configure_musia_auth(manager)
    app = FastAPI()
    app.include_router(diagnostics_router)
    try:
        yield TestClient(app), manager
    finally:
        configure_musia_auth(None)


def _key(manager: APIKeyManager, scopes: set[str]) -> str:
    raw, _ = manager.create_key(tenant_id="tenant-a", scopes=frozenset(scopes))
    return raw


def test_run_benchmarks_rejects_non_admin_before_suite_runs(
    auth_client: tuple[TestClient, APIKeyManager],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import mcoi_runtime.core.governance_bench as governance_bench

    def fail_if_called() -> NoReturn:
        raise AssertionError("benchmark suite ran before admin scope was verified")

    monkeypatch.setattr(governance_bench, "run_governance_benchmarks", fail_if_called)
    client, manager = auth_client
    resp = client.post(
        "/api/v1/ops/benchmarks",
        headers={"Authorization": f"Bearer {_key(manager, {'musia.write'})}"},
    )
    detail = resp.json()["detail"]
    assert resp.status_code == 403
    assert detail["error"] == "missing scope: musia.admin"
    assert detail["granted_scopes"] == ["musia.write"]


def test_run_benchmarks_allows_admin(
    auth_client: tuple[TestClient, APIKeyManager],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Stub the expensive suite so the test stays fast -- only the gate is asserted.
    import mcoi_runtime.core.governance_bench as governance_bench

    class _Suite:
        def summary(self) -> dict:
            return {"ran": True}

    monkeypatch.setattr(governance_bench, "run_governance_benchmarks", lambda: _Suite())
    client, manager = auth_client
    resp = client.post(
        "/api/v1/ops/benchmarks",
        headers={"Authorization": f"Bearer {_key(manager, {'musia.admin'})}"},
    )
    assert resp.status_code == 200
    assert resp.json()["governed"] is True
    assert resp.json()["ran"] is True
