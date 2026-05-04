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


DT = "2026-05-04T12:00:00+00:00"


def _certificate_payload() -> dict[str, object]:
    return {
        "certificate_id": "cert-001",
        "change_id": "chg-001",
        "schema_checks_passed": True,
        "tests_passed": True,
        "replay_passed": True,
        "invariant_checks_passed": True,
        "migration_safe": True,
        "rollback_plan_present": True,
        "approval_id": None,
        "evidence_refs": ["change_command.json", "release_certificate.json"],
        "certified_at": DT,
    }


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
    assert evaluate.json()["sandbox_bundle_count"] >= 1
    assert evaluate.json()["sandbox_bundles"][0]["mutation_applied"] is False
    assert "sandbox_result" in evaluate.json()["sandbox_bundles"][0]
    assert propose.status_code == 200
    assert propose.json()["mutation_applied"] is False
    assert propose.json()["candidate_count"] >= 1


def test_reflex_certify_returns_handoff_not_self_certificate() -> None:
    app = create_gateway_app(platform=StubPlatform())
    client = TestClient(app)
    candidate_id = client.post("/runtime/self/propose-upgrade").json()["candidates"][0]["candidate_id"]

    response = client.post(
        "/runtime/self/certify",
        json={
            "candidate_id": candidate_id,
            "base_ref": "main",
            "head_ref": "codex/reflex",
            "base_commit": "a" * 40,
            "head_commit": "b" * 40,
        },
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["status"] == "certification_required"
    assert payload["mutation_applied"] is False
    assert payload["change_command"]["metadata"]["reflex_candidate_id"] == candidate_id
    assert payload["change_command"]["requires_approval"] is True
    assert "scripts/certify_change.py" in payload["required_command"]
    assert "codex/reflex" in payload["required_command"]
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


def test_reflex_promote_accepts_sandbox_bundle_and_certificate_handoff() -> None:
    app = create_gateway_app(platform=StubPlatform())
    client = TestClient(app)
    candidate = client.post("/runtime/self/propose-upgrade").json()["candidates"][0]
    evaluation = client.post("/runtime/self/evaluate").json()
    sandbox_bundle = next(
        bundle
        for bundle in evaluation["sandbox_bundles"]
        if bundle["candidate_id"] == candidate["candidate_id"]
    )

    response = client.post(
        "/runtime/self/promote",
        json={
            "candidate_id": candidate["candidate_id"],
            "sandbox_bundle": sandbox_bundle,
            "certificate": _certificate_payload(),
        },
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["candidate_id"] == candidate["candidate_id"]
    assert payload["mutation_applied"] is False
    assert payload["deployment_witness_required"] is True
    assert payload["promotion_decision"]["candidate_id"] == candidate["candidate_id"]
    assert payload["disposition"] == payload["promotion_decision"]["disposition"]
    assert "attach_sandbox_bundle" in payload["canary_steps"]


def test_reflex_auto_canary_persists_signed_deployment_witness_when_authorized(
    monkeypatch,
) -> None:
    monkeypatch.setenv("MULLU_REFLEX_PREMIUM_MODEL_LOW_RISK_REQUESTS", "4")
    app = create_gateway_app(platform=StubPlatform())
    client = TestClient(app)
    candidates = client.post("/runtime/self/propose-upgrade").json()["candidates"]
    candidate = next(
        item
        for item in candidates
        if item["change_surface"] == "provider_routing"
    )
    evaluation = client.post("/runtime/self/evaluate").json()
    sandbox_bundle = next(
        bundle
        for bundle in evaluation["sandbox_bundles"]
        if bundle["candidate_id"] == candidate["candidate_id"]
    )

    response = client.post(
        "/runtime/self/promote",
        json={
            "candidate_id": candidate["candidate_id"],
            "sandbox_bundle": sandbox_bundle,
            "certificate": _certificate_payload(),
            "apply_canary": True,
            "target_environment": "canary",
        },
    )
    payload = response.json()
    witness = client.get("/runtime/self/witness").json()

    assert response.status_code == 200
    assert payload["disposition"] == "auto_canary_allowed"
    assert payload["requires_human_approval"] is False
    assert payload["deployment_witness_persisted"] is True
    assert payload["deployment_witness"]["signature"].startswith("hmac-sha256:")
    assert payload["deployment_witness"]["production_mutation_applied"] is False
    assert witness["deployment_witness_count"] == 1
    assert witness["deployment_witness_replay_passed"] is True
    assert witness["latest_deployment_witness_id"] == payload["deployment_witness"]["witness_id"]


def test_reflex_apply_canary_requires_backed_witness_log_in_production(monkeypatch) -> None:
    monkeypatch.setenv("MULLU_ENV", "production")
    monkeypatch.setenv("MULLU_REQUIRE_PERSISTENT_TENANT_IDENTITY", "false")
    monkeypatch.setenv("MULLU_REQUIRE_PERSISTENT_AUTHORITY_MESH", "false")
    monkeypatch.setenv("MULLU_AUTHORITY_OPERATOR_SECRET", "operator-secret")
    monkeypatch.setenv("MULLU_DEPLOYMENT_AUTHORITY_SECRET", "deployment-secret")
    monkeypatch.setenv("MULLU_REFLEX_PREMIUM_MODEL_LOW_RISK_REQUESTS", "4")
    monkeypatch.delenv("MULLU_ALLOW_EPHEMERAL_REFLEX_WITNESS_LOG", raising=False)
    app = create_gateway_app(platform=StubPlatform())
    client = TestClient(app)
    headers = {
        "X-Mullu-Authority-Secret": "operator-secret",
        "X-Mullu-Deployment-Secret": "deployment-secret",
    }
    candidate = next(
        item
        for item in client.post("/runtime/self/propose-upgrade", headers=headers).json()["candidates"]
        if item["change_surface"] == "provider_routing"
    )
    evaluation = client.post("/runtime/self/evaluate", headers=headers).json()
    sandbox_bundle = next(
        bundle
        for bundle in evaluation["sandbox_bundles"]
        if bundle["candidate_id"] == candidate["candidate_id"]
    )

    response = client.post(
        "/runtime/self/promote",
        headers=headers,
        json={
            "candidate_id": candidate["candidate_id"],
            "sandbox_bundle": sandbox_bundle,
            "certificate": _certificate_payload(),
            "apply_canary": True,
        },
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "Persistent Reflex deployment witness log required"


def test_reflex_deployment_witness_query_is_operator_read_model() -> None:
    app = create_gateway_app(platform=StubPlatform())
    client = TestClient(app)

    response = client.get("/runtime/self/deployment-witnesses?limit=3")
    payload = response.json()

    assert response.status_code == 200
    assert payload["records"] == []
    assert payload["record_count"] == 0
    assert payload["limit"] == 3
    assert payload["all_replay_passed"] is True
    assert payload["mutation_applied"] is False


def test_reflex_deployment_witness_query_requires_backed_log_in_production(monkeypatch) -> None:
    monkeypatch.setenv("MULLU_ENV", "production")
    monkeypatch.setenv("MULLU_REQUIRE_PERSISTENT_TENANT_IDENTITY", "false")
    monkeypatch.setenv("MULLU_REQUIRE_PERSISTENT_AUTHORITY_MESH", "false")
    monkeypatch.setenv("MULLU_AUTHORITY_OPERATOR_SECRET", "operator-secret")
    monkeypatch.delenv("MULLU_ALLOW_EPHEMERAL_REFLEX_WITNESS_LOG", raising=False)
    app = create_gateway_app(platform=StubPlatform())
    client = TestClient(app)

    response = client.get(
        "/runtime/self/deployment-witnesses",
        headers={"X-Mullu-Authority-Secret": "operator-secret"},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "Persistent Reflex deployment witness log required"


def test_reflex_deployment_witness_query_returns_replay_status(monkeypatch) -> None:
    monkeypatch.setenv("MULLU_REFLEX_PREMIUM_MODEL_LOW_RISK_REQUESTS", "4")
    app = create_gateway_app(platform=StubPlatform())
    client = TestClient(app)
    candidates = client.post("/runtime/self/propose-upgrade").json()["candidates"]
    candidate = next(
        item
        for item in candidates
        if item["change_surface"] == "provider_routing"
    )
    evaluation = client.post("/runtime/self/evaluate").json()
    sandbox_bundle = next(
        bundle
        for bundle in evaluation["sandbox_bundles"]
        if bundle["candidate_id"] == candidate["candidate_id"]
    )
    promote = client.post(
        "/runtime/self/promote",
        json={
            "candidate_id": candidate["candidate_id"],
            "sandbox_bundle": sandbox_bundle,
            "certificate": _certificate_payload(),
            "apply_canary": True,
        },
    ).json()

    response = client.get("/runtime/self/deployment-witnesses?limit=1")
    payload = response.json()

    assert response.status_code == 200
    assert payload["record_count"] == 1
    assert payload["all_replay_passed"] is True
    assert payload["records"][0]["replay_passed"] is True
    assert payload["records"][0]["witness"]["witness_id"] == promote["deployment_witness"]["witness_id"]
    assert payload["records"][0]["witness"]["production_mutation_applied"] is False


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
    assert payload["deployment_witness_log_backed"] is False
    assert payload["ephemeral_deployment_witness_log_allowed"] is True
    assert payload["candidate_count"] >= 1
    assert payload["deployment_witness_replay_passed"] is True
