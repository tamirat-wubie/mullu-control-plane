"""Promotion-witness endpoint test lane.

Proves `POST /api/v1/health/witness` is:
  - disabled by default (404) so it is not an open ledger-write vector;
  - when enabled, issues a real synthetic governed decision and verifies both
    the proof receipt and the audit hash-chain (the promotion-grade proof);
  - bounded — each call produces a distinct, verified receipt.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

try:
    from fastapi.testclient import TestClient

    FASTAPI_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency guard
    FASTAPI_AVAILABLE = False

_FLAG = "MULLU_HEALTH_WITNESS_ENABLED"


@pytest.fixture
def client() -> Iterator[TestClient]:
    if not FASTAPI_AVAILABLE:
        pytest.skip("FastAPI not installed")
    os.environ["MULLU_ENV"] = "local_dev"
    os.environ["MULLU_DB_BACKEND"] = "memory"
    os.environ["MULLU_CERT_INTERVAL"] = "0"
    from mcoi_runtime.app.server import app

    yield TestClient(app)


def test_witness_disabled_by_default(client: TestClient) -> None:
    os.environ.pop(_FLAG, None)
    resp = client.post("/api/v1/health/witness")
    assert resp.status_code == 404


def test_witness_verified_when_enabled(client: TestClient) -> None:
    os.environ[_FLAG] = "true"
    try:
        resp = client.post("/api/v1/health/witness")
    finally:
        os.environ.pop(_FLAG, None)

    assert resp.status_code == 200
    body = resp.json()
    assert body["outcome"] == "verified"
    assert body["governed"] is True
    assert body["proof"]["receipt_id"]
    assert body["proof"]["receipt_hash"]
    assert body["proof"]["verified"] is True
    assert body["audit"]["entry_id"]
    assert body["audit"]["chain_valid"] is True
    assert body["errors"] == []


def test_witness_produces_distinct_verified_receipts(client: TestClient) -> None:
    os.environ[_FLAG] = "true"
    try:
        first = client.post("/api/v1/health/witness").json()
        second = client.post("/api/v1/health/witness").json()
    finally:
        os.environ.pop(_FLAG, None)

    assert first["proof"]["receipt_id"] != second["proof"]["receipt_id"]
    assert first["audit"]["entry_id"] != second["audit"]["entry_id"]
    # The audit chain grew and stayed verifiable across calls.
    assert second["audit"]["chain_length"] > first["audit"]["chain_length"]
    assert second["audit"]["chain_valid"] is True
