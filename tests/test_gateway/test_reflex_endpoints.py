"""Purpose: test internal Reflex Engine gateway endpoints.
Governance scope: verifies operator-only access, read/proposal surfaces,
    non-mutation guarantees, certification handoff, and signed witness output.
Dependencies: FastAPI TestClient and gateway server.
Invariants:
  - Reflex endpoints are guarded by authority-operator access.
  - Reflex proposal endpoints do not mutate production state.
  - Certification endpoint returns a handoff, not a self-issued certificate.
  - Reflex witness binds counts and signature metadata.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from gateway.server import create_gateway_app


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


def test_reflex_health_and_inspect_are_operator_guarded_local() -> None:
    app = create_gateway_app(platform=StubPlatform())
    client = TestClient(app)

    health = client.get("/runtime/self/health")
    inspect = client.get("/runtime/self/inspect")

    assert health.status_code == 200
    assert health.json()["snapshot_id"].startswith("reflex-snapshot-")
    assert health.json()["metrics"]["deployment_witness_missing"] == 1
    assert inspect.status_code == 200
    assert inspect.json()["anomaly_count"] >= 1


def test_reflex_endpoints_fail_closed_without_operator_in_production(monkeypatch) -> None:
    monkeypatch.setenv("MULLU_ENV", "production")
    monkeypatch.setenv("MULLU_REQUIRE_PERSISTENT_TENANT_IDENTITY", "false")
    monkeypatch.setenv("MULLU_REQUIRE_PERSISTENT_AUTHORITY_MESH", "false")
    monkeypatch.delenv("MULLU_AUTHORITY_OPERATOR_SECRET", raising=False)
    app = create_gateway_app(platform=StubPlatform())
    client = TestClient(app)

    denied = client.get("/runtime/self/health")

    assert denied.status_code == 403
    assert denied.json()["detail"] == "Authority operator access not authorized"


def test_reflex_diagnose_evaluate_and_propose_are_non_mutating() -> None:
    app = create_gateway_app(platform=StubPlatform())
    client = TestClient(app)

    diagnose = client.post("/runtime/self/diagnose")
    evaluate = client.post("/runtime/self/evaluate")
    propose = client.post("/runtime/self/propose-upgrade")

    assert diagnose.status_code == 200
    assert diagnose.json()["diagnosis_count"] >= 1
    assert evaluate.status_code == 200
    assert evaluate.json()["side_effects"] == "none"
    assert evaluate.json()["eval_count"] >= 1
    assert propose.status_code == 200
    assert propose.json()["mutation_applied"] is False
    assert propose.json()["candidate_count"] >= 1


def test_reflex_certify_returns_handoff_not_self_certificate() -> None:
    app = create_gateway_app(platform=StubPlatform())
    client = TestClient(app)

    response = client.post("/runtime/self/certify", json={"candidate_id": "ref-upg-1"})
    payload = response.json()

    assert response.status_code == 200
    assert payload["status"] == "certification_required"
    assert payload["mutation_applied"] is False
    assert "scripts/certify_change.py" in payload["required_command"]
    assert "release_certificate.json" in payload["required_artifacts"]


def test_reflex_promote_without_evidence_requires_human_approval() -> None:
    app = create_gateway_app(platform=StubPlatform())
    client = TestClient(app)
    candidate_id = client.post("/runtime/self/propose-upgrade").json()["candidates"][0][
        "candidate_id"
    ]

    response = client.post("/runtime/self/promote", json={"candidate_id": candidate_id})
    payload = response.json()

    assert response.status_code == 200
    assert payload["disposition"] == "human_approval_required"
    assert payload["requires_human_approval"] is True
    assert payload["mutation_applied"] is False


def test_reflex_witness_is_signed_and_binds_pipeline_counts() -> None:
    app = create_gateway_app(platform=StubPlatform())
    client = TestClient(app)

    response = client.get("/runtime/self/witness")
    payload = response.json()

    assert response.status_code == 200
    assert payload["witness_id"].startswith("reflex-witness-")
    assert payload["signature"].startswith("hmac-sha256:")
    assert payload["mutation_applied"] is False
    assert payload["protected_surfaces_auto_promote"] is False
    assert payload["candidate_count"] >= 1
