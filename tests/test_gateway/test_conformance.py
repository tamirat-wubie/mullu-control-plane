"""Runtime conformance endpoint tests.

Purpose: verify that the gateway exposes signed conformance certificates
without hiding missing runtime evidence.
Governance scope: runtime witness binding, conformance gaps, and schema
compatibility.
Dependencies: FastAPI TestClient, gateway server, schema validator.
Invariants:
  - `/runtime/conformance` is read-only and signed.
  - Missing closure or fabric evidence is surfaced as a named gap.
  - The endpoint payload conforms to the shared certificate schema.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gateway.server import create_gateway_app  # noqa: E402
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


class StubPlatform:
    """Minimal governed platform fixture for gateway app construction."""

    def connect(self, *, identity_id: str, tenant_id: str):
        return StubSession()


class StubSession:
    """Minimal governed session fixture."""

    def llm(self, prompt: str, **kwargs):
        return type("Result", (), {"content": "ok", "succeeded": True, "error": "", "cost": 0.0})()

    def close(self) -> None:
        return None


def test_runtime_conformance_endpoint_returns_signed_gap_certificate(monkeypatch) -> None:
    monkeypatch.setenv("MULLU_RUNTIME_CONFORMANCE_SECRET", "conformance-secret")
    monkeypatch.setenv("MULLU_RUNTIME_WITNESS_SECRET", "witness-secret")
    app = create_gateway_app(platform=StubPlatform())
    client = TestClient(app)

    response = client.get("/runtime/conformance")
    payload = response.json()

    assert response.status_code == 200
    assert payload["certificate_id"].startswith("conf-")
    assert payload["gateway_witness_valid"] is True
    assert payload["runtime_witness_valid"] is True
    assert payload["terminal_status"] == "degraded"
    assert "command_closure_canary_missing_terminal_success" in payload["open_conformance_gaps"]
    assert "capability_fabric_admission_not_live" in payload["open_conformance_gaps"]
    assert payload["signature"].startswith("hmac-sha256:")
    assert _signature_valid(payload, "conformance-secret") is True


def test_runtime_conformance_certificate_matches_schema(monkeypatch) -> None:
    monkeypatch.setenv("MULLU_RUNTIME_CONFORMANCE_SECRET", "conformance-secret")
    app = create_gateway_app(platform=StubPlatform())
    client = TestClient(app)
    payload = client.get("/runtime/conformance").json()
    schema_path = _ROOT / "schemas" / "runtime_conformance_certificate.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    errors = _validate_schema_instance(schema, payload)

    assert errors == []
    assert payload["checks"]
    assert all(check["evidence_ref"] for check in payload["checks"])


def _signature_valid(payload: dict, secret: str) -> bool:
    signature = payload["signature"].removeprefix("hmac-sha256:")
    unsigned = dict(payload)
    unsigned.pop("signature", None)
    canonical = json.dumps(unsigned, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    digest = hashlib.sha256(canonical).hexdigest()
    expected = hmac.new(secret.encode("utf-8"), digest.encode("utf-8"), hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected)
