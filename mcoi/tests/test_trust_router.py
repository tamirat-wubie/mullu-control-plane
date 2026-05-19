"""Tests for the public /trust/verification-key endpoint."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from mcoi_runtime.app.routers.trust import router
from mcoi_runtime.contracts.receipt_signing import (
    generate_keypair,
    reset_default_signer_cache,
)


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_verification_key_unsigned_mode(monkeypatch):
    monkeypatch.delenv("MCOI_RECEIPT_SIGNING_KEY", raising=False)
    reset_default_signer_cache()
    try:
        resp = _client().get("/trust/verification-key")
        assert resp.status_code == 200
        body = resp.json()
        assert body["mode"] == "unsigned"
        assert body["algorithm"] == "ed25519"
        assert body["public_key_hex"] == ""
    finally:
        reset_default_signer_cache()


def test_verification_key_signed_mode_exposes_public_half(monkeypatch):
    seed_hex, pub_hex, key_id = generate_keypair()
    monkeypatch.setenv("MCOI_RECEIPT_SIGNING_KEY", seed_hex)
    reset_default_signer_cache()
    try:
        body = _client().get("/trust/verification-key").json()
        assert body["mode"] == "signed"
        assert body["public_key_hex"] == pub_hex
        assert body["key_id"] == key_id
    finally:
        reset_default_signer_cache()


def test_endpoint_is_get_only():
    # State-mutating verbs must not exist on the trust surface — this is
    # what keeps it out of the receipt-coverage ratchet.
    client = _client()
    assert client.post("/trust/verification-key").status_code == 405
    assert client.delete("/trust/verification-key").status_code == 405
