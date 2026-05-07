"""Gateway evidence bundle endpoint tests.

Purpose: verify terminal commands export signed trust-ledger evidence bundles.
Governance scope: operator evidence bundle read model and offline verifier.
Dependencies: FastAPI TestClient, gateway server, trust ledger verifier script.
Invariants:
  - Non-terminal commands cannot export evidence bundles.
  - Terminal bundles validate against the public schema.
  - Offline verifier detects valid and tampered bundle files.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gateway.router import GatewayMessage, TenantMapping  # noqa: E402
from gateway.server import create_gateway_app  # noqa: E402
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402
from scripts.verify_evidence_bundle import verify_bundle_file  # noqa: E402


TRUST_BUNDLE_SCHEMA = _ROOT / "schemas" / "trust_ledger_bundle.schema.json"


class StubPlatform:
    """Minimal governed platform fixture."""

    def connect(self, *, identity_id: str, tenant_id: str):
        return StubSession()


class StubSession:
    """Minimal governed session fixture."""

    def llm(self, prompt: str, **kwargs):
        return type("Result", (), {"content": "bundle ready", "succeeded": True, "error": ""})()

    def close(self) -> None:
        return None


def test_terminal_command_exports_signed_evidence_bundle(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MULLU_TRUST_LEDGER_SECRET", "trust-secret")
    monkeypatch.setenv("MULLU_TRUST_LEDGER_KEY_ID", "trust-key")
    monkeypatch.setenv("MULLU_DEPLOYMENT_ID", "dep-evidence-test")
    monkeypatch.setenv("MULLU_DEPLOYED_COMMIT_SHA", "commit-evidence-test")
    app = create_gateway_app(platform=StubPlatform())
    client = TestClient(app)
    router = app.state.router
    router.register_tenant_mapping(TenantMapping(
        channel="web",
        sender_id="user-1",
        tenant_id="tenant-1",
        identity_id="actor-1",
    ))
    response = router.handle_message(GatewayMessage(
        message_id="msg-evidence-1",
        channel="web",
        sender_id="user-1",
        body="prepare evidence bundle",
    ))

    bundle_response = client.get(f"/evidence/bundles/{response.metadata['command_id']}")
    bundle = bundle_response.json()
    bundle_path = tmp_path / "bundle.json"
    bundle_path.write_text(json.dumps(bundle), encoding="utf-8")
    verification = verify_bundle_file(bundle_path=bundle_path, signing_secret="trust-secret")

    assert bundle_response.status_code == 200
    assert bundle["bundle_id"].startswith("trust-bundle-")
    assert bundle["tenant_id"] == "tenant-1"
    assert bundle["command_id"] == response.metadata["command_id"]
    assert bundle["terminal_certificate_id"] == response.metadata["terminal_certificate_id"]
    assert bundle["deployment_id"] == "dep-evidence-test"
    assert bundle["commit_sha"] == "commit-evidence-test"
    assert bundle["signature"].startswith("hmac-sha256:")
    assert bundle["metadata"]["artifact_count"] >= 4
    assert "terminal_certificate" in bundle["metadata"]["artifact_types"]
    assert verification["valid"] is True
    assert verification["reason"] == "verified"
    assert _validate_schema_instance(_load_schema(TRUST_BUNDLE_SCHEMA), bundle) == []


def test_evidence_bundle_endpoint_rejects_non_terminal_command(monkeypatch) -> None:
    monkeypatch.setenv("MULLU_TRUST_LEDGER_SECRET", "trust-secret")
    app = create_gateway_app(platform=StubPlatform())
    client = TestClient(app)
    command = app.state.command_ledger.create_command(
        tenant_id="tenant-1",
        actor_id="actor-1",
        source="web",
        conversation_id="conversation-1",
        idempotency_key="idem-1",
        intent="llm_completion",
        payload={"body": "not terminal"},
    )

    response = client.get(f"/evidence/bundles/{command.command_id}")

    assert response.status_code == 409
    assert response.json()["detail"] == "terminal certificate required"


def test_offline_bundle_verifier_detects_tampering(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MULLU_TRUST_LEDGER_SECRET", "trust-secret")
    app = create_gateway_app(platform=StubPlatform())
    router = app.state.router
    router.register_tenant_mapping(TenantMapping(
        channel="web",
        sender_id="user-2",
        tenant_id="tenant-2",
        identity_id="actor-2",
    ))
    response = router.handle_message(GatewayMessage(
        message_id="msg-evidence-2",
        channel="web",
        sender_id="user-2",
        body="prepare tamper evidence",
    ))
    client = TestClient(app)
    bundle = client.get(f"/evidence/bundles/{response.metadata['command_id']}").json()
    bundle["evidence_refs"].append("proof://tampered")
    bundle_path = tmp_path / "tampered-bundle.json"
    bundle_path.write_text(json.dumps(bundle), encoding="utf-8")

    verification = verify_bundle_file(bundle_path=bundle_path, signing_secret="trust-secret")

    assert verification["valid"] is False
    assert verification["reason"] == "bundle_hash_mismatch"
    assert verification["expected_bundle_hash"] != verification["observed_bundle_hash"]
