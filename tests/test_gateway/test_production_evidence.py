"""Production evidence plane endpoint tests.

Purpose: verify public production evidence endpoints expose bounded runtime,
    capability, audit, and proof claims without upgrading missing evidence.
Governance scope: deployment witnesses, capability maturity projections,
    audit-anchor verification, and proof verification closure.
Dependencies: FastAPI TestClient and gateway server.
Invariants:
  - Deployment witnesses are signed and identify version, commit, environment, and gaps.
  - Capability evidence reports an absent registry as missing evidence.
  - Proof verification binds conformance, deployment witness, and audit anchor status.
"""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gateway.server import create_gateway_app  # noqa: E402
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


PRODUCTION_EVIDENCE_SCHEMA = _ROOT / "schemas" / "production_evidence_witness.schema.json"
CAPABILITY_EVIDENCE_SCHEMA = _ROOT / "schemas" / "capability_evidence_endpoint.schema.json"
AUDIT_VERIFICATION_SCHEMA = _ROOT / "schemas" / "audit_verification_endpoint.schema.json"
PROOF_VERIFICATION_SCHEMA = _ROOT / "schemas" / "proof_verification_endpoint.schema.json"


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


def test_deployment_witness_is_signed_and_reports_missing_runtime_evidence(monkeypatch) -> None:
    monkeypatch.setenv("MULLU_DEPLOYMENT_ID", "dep_test_001")
    monkeypatch.setenv("MULLU_DEPLOYED_COMMIT_SHA", "abc123")
    monkeypatch.setenv("MULLU_DEPLOYMENT_WITNESS_SECRET", "deployment-secret")
    app = create_gateway_app(platform=StubPlatform())
    client = TestClient(app)

    response = client.get("/deployment/witness")
    payload = response.json()

    assert response.status_code == 200
    assert payload["deployment_id"] == "dep_test_001"
    assert payload["commit_sha"] == "abc123"
    assert payload["runtime_env"] == "local_dev"
    assert payload["version"] == "1.0.0"
    assert payload["signature"].startswith("hmac-sha256:")
    assert payload["claim_hash"]
    assert "capability_registry" in payload["checks_missing"]
    assert "audit_anchor" in payload["checks_missing"]
    assert "proof_store" in payload["checks_missing"]
    assert _validate_schema_instance(_load_schema(PRODUCTION_EVIDENCE_SCHEMA), payload) == []


def test_capabilities_evidence_reports_disabled_registry() -> None:
    app = create_gateway_app(platform=StubPlatform())
    client = TestClient(app)

    payload = client.get("/capabilities/evidence").json()

    assert payload["enabled"] is False
    assert payload["capability_count"] == 0
    assert payload["capability_evidence"] == {}
    assert payload["live_capabilities"] == []
    assert payload["sandbox_only_capabilities"] == []
    assert payload["checks"][0]["check_id"] == "capability_registry_configured"
    assert payload["checks"][0]["passed"] is False
    assert _validate_schema_instance(_load_schema(CAPABILITY_EVIDENCE_SCHEMA), payload) == []


def test_audit_and_proof_verify_surface_anchor_gap(monkeypatch) -> None:
    monkeypatch.setenv("MULLU_RUNTIME_CONFORMANCE_SECRET", "conformance-secret")
    monkeypatch.setenv("MULLU_DEPLOYMENT_WITNESS_SECRET", "deployment-secret")
    app = create_gateway_app(platform=StubPlatform())
    client = TestClient(app)

    audit_payload = client.get("/audit/verify").json()
    proof_payload = client.get("/proof/verify").json()

    assert audit_payload["valid"] is False
    assert audit_payload["reason"] == "anchor_not_found"
    assert audit_payload["entries_checked"] == 0
    assert proof_payload["valid"] is False
    assert proof_payload["terminal_status"] == "verification_gaps"
    assert "runtime_conformance_signature" in proof_payload["checks_passed"]
    assert "deployment_witness_signature" in proof_payload["checks_passed"]
    assert "audit_anchor_verification" in proof_payload["checks_missing"]
    assert _validate_schema_instance(_load_schema(AUDIT_VERIFICATION_SCHEMA), audit_payload) == []
    assert _validate_schema_instance(_load_schema(PROOF_VERIFICATION_SCHEMA), proof_payload) == []
