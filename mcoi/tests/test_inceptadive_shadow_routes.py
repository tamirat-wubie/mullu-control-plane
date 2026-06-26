"""Focused tests for read-only InceptaDive Shadow Pass posture routes."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from mcoi_runtime.app.inceptadive_shadow_integration import build_inceptadive_shadow_runtime
from mcoi_runtime.app.routers.deps import deps
from mcoi_runtime.app.routers.shadow import router
from mcoi_runtime.app.server_http import include_default_routers
from mcoi_runtime.core.inceptadive_shadow_types import ShadowContext, ShadowSeverity, ShadowStage

_FIXTURES = Path(__file__).resolve().parent / "fixtures"


class _Metrics:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def inc(self, name: str, val: int = 1) -> None:
        del val
        self.calls.append(name)


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_shadow_health_route_returns_redacted_read_model() -> None:
    previous_store = dict(deps._store)
    metrics = _Metrics()
    deps._store.clear()
    deps.set("metrics", metrics)
    deps.set("inceptadive_shadow_runtime", build_inceptadive_shadow_runtime({}))
    try:
        response = _client().get("/api/v1/health/shadow")
    finally:
        deps._store.clear()
        deps._store.update(previous_store)

    payload = response.json()
    shadow = payload["shadow"]
    assert response.status_code == 200
    assert payload["governed"] is True
    assert payload["registered"] is True
    assert payload["execution_authority"] is False
    assert payload["raw_request_text_exposed"] is False
    assert payload["private_memory_exposed"] is False
    assert shadow["status"] == "ready"
    assert shadow["execution_authority"] is False
    assert shadow["raw_request_text_exposed"] is False
    assert shadow["private_memory_exposed"] is False
    assert "requests_governed" in metrics.calls


def test_shadow_console_route_returns_counts_without_raw_text() -> None:
    previous_store = dict(deps._store)
    deps._store.clear()
    deps.set("inceptadive_shadow_runtime", build_inceptadive_shadow_runtime({}))
    try:
        response = _client().get("/api/v1/console/shadow")
    finally:
        deps._store.clear()
        deps._store.update(previous_store)

    payload = response.json()
    summary = payload["summary"]
    assert response.status_code == 200
    assert payload["governed"] is True
    assert payload["registered"] is True
    assert payload["status"] == "ready"
    assert payload["execution_authority"] is False
    assert payload["raw_request_text_exposed"] is False
    assert payload["private_memory_exposed"] is False
    assert summary["recent_result_count"] == 0
    assert summary["receipt_count"] == 0
    assert summary["execution_authority"] is False
    assert summary["raw_request_text_exposed"] is False
    assert summary["private_memory_exposed"] is False
    assert "deploy it" not in str(payload)
    assert "delete production logs" not in str(payload)


def test_shadow_console_evidence_route_returns_redacted_recent_evidence() -> None:
    previous_store = dict(deps._store)
    deps._store.clear()
    deps.set(
        "inceptadive_shadow_runtime",
        build_inceptadive_shadow_runtime({"MULLU_INCEPTADIVE_SHADOW_DEEP_ENGINE_AVAILABLE": "1"}),
    )
    try:
        client = _client()
        inspect_response = client.post(
            "/api/v1/shadow/inspect",
            json={
                "request_id": "shadow-route-evidence-001",
                "stage": "interpretation",
                "user_input": "deploy it with evidence-secret-token",
                "risk_level": "high",
                "external_side_effect": True,
                "created_at": "2026-06-22T00:00:00+00:00",
            },
        )
        advisory_response = client.post(
            "/api/v1/shadow/external-effect/advisory",
            json={
                "request_id": "shadow-route-evidence-advisory-001",
                "stage": "preflight",
                "user_input": "deploy it with obligation-secret-token",
                "candidate_action": "deploy it with obligation-secret-token",
                "risk_level": "high",
                "external_side_effect": True,
                "required_evidence_refs": ["raw-evidence-secret-ref"],
                "created_at": "2026-06-22T00:02:00+00:00",
            },
        )
        response = client.get("/api/v1/console/shadow/evidence")
    finally:
        deps._store.clear()
        deps._store.update(previous_store)

    payload = response.json()
    recent_result = payload["recent_results"][0]
    recent_receipt = payload["recent_receipts"][0]
    recent_advisory = payload["recent_external_effect_advisories"][0]
    assert inspect_response.status_code == 200
    assert advisory_response.status_code == 200
    assert response.status_code == 200
    assert payload["governed"] is True
    assert payload["registered"] is True
    assert payload["status"] == "ready"
    assert payload["recent_result_count"] == 1
    assert payload["receipt_count"] == 1
    assert payload["mode_counts"] == {"deep": 1}
    assert payload["execution_authority"] is False
    assert payload["connector_dispatch_authority"] is False
    assert payload["memory_write_authority"] is False
    assert payload["governance_verdict_authority"] is False
    assert payload["raw_request_text_exposed"] is False
    assert payload["private_memory_exposed"] is False
    assert payload["raw_evidence_refs_exposed"] is False
    assert payload["obligation_history_available"] is True
    assert payload["obligation_history_unavailable_reason"] == ""
    assert payload["recent_advisory_count"] == 1
    assert payload["missing_authority_obligation_count"] == 1
    assert payload["missing_evidence_obligation_count"] == 0
    assert recent_result["result_id"].startswith("shadow-result-")
    assert recent_result["request_id"] == "shadow-route-evidence-001"
    assert recent_result["mode"] == "deep"
    assert recent_result["finding_count"] >= 1
    assert recent_result["execution_authority"] is False
    assert recent_receipt["receipt_id"].startswith("shadow-receipt-")
    assert recent_receipt["request_id"] == "shadow-route-evidence-001"
    assert recent_receipt["retrieval_receipt_count"] == 0
    assert recent_receipt["execution_authority"] is False
    assert recent_advisory["advisory_id"].startswith("inceptadive-external-effect-advisory-")
    assert recent_advisory["request_id"] == "shadow-route-evidence-advisory-001"
    assert recent_advisory["missing_authority_obligation_count"] == 1
    assert recent_advisory["missing_evidence_obligation_count"] == 0
    assert recent_advisory["required_evidence_ref_count"] == 1
    assert recent_advisory["authority_receipt_count"] == 0
    assert recent_advisory["execution_authority"] is False
    assert recent_advisory["connector_dispatch_authority"] is False
    assert "deploy it with evidence-secret-token" not in str(payload)
    assert "deploy it with obligation-secret-token" not in str(payload)
    assert "evidence-secret-token" not in str(payload)
    assert "obligation-secret-token" not in str(payload)
    assert "raw-evidence-secret-ref" not in str(payload)


def test_shadow_inspect_route_runs_runtime_and_redacts_raw_text() -> None:
    previous_store = dict(deps._store)
    deps._store.clear()
    deps.set(
        "inceptadive_shadow_runtime",
        build_inceptadive_shadow_runtime({"MULLU_INCEPTADIVE_SHADOW_DEEP_ENGINE_AVAILABLE": "1"}),
    )
    try:
        response = _client().post(
            "/api/v1/shadow/inspect",
            json={
                "request_id": "shadow-route-redaction-001",
                "stage": "interpretation",
                "user_input": "deploy it with secret-token",
                "risk_level": "high",
                "external_side_effect": True,
                "created_at": "2026-06-19T00:00:00+00:00",
            },
        )
    finally:
        deps._store.clear()
        deps._store.update(previous_store)

    payload = response.json()
    result = payload["result"]
    receipt = payload["receipt"]
    assert response.status_code == 200
    assert payload["governed"] is True
    assert payload["registered"] is True
    assert payload["execution_authority"] is False
    assert payload["raw_request_text_exposed"] is False
    assert payload["private_memory_exposed"] is False
    assert result["mode"] == "deep"
    assert result["execution_authority"] is False
    assert result["finding_count"] >= 1
    assert receipt["receipt_id"].startswith("shadow-receipt-")
    assert receipt["execution_authority"] is False
    assert payload["recent_activity"]["result_count"] == 1
    assert payload["recent_activity"]["receipt_count"] == 1
    assert "deploy it with secret-token" not in str(payload)
    assert "secret-token" not in str(payload)


def test_shadow_inspect_route_redacts_context_refs_before_jsonl_persistence(tmp_path: Path) -> None:
    previous_store = dict(deps._store)
    raw_target = "operator-secret-target-001"
    raw_scope = "tenant-private-scope-001"
    raw_retrieval_ref = "retrieval-secret-ref-001"
    raw_evidence_ref = "approval-secret-evidence-001"
    store_path = tmp_path / "shadow-store"
    deps._store.clear()
    deps.set(
        "inceptadive_shadow_runtime",
        build_inceptadive_shadow_runtime(
            {
                "MULLU_INCEPTADIVE_SHADOW_DEEP_ENGINE_AVAILABLE": "1",
                "MULLU_INCEPTADIVE_SHADOW_STORE_PATH": str(store_path),
            }
        ),
    )
    request_payload = {
        "request_id": "shadow-route-context-redaction-001",
        "stage": "preflight",
        "user_input": "deploy approved receipt with rollback",
        "candidate_action": "deploy approved receipt with rollback",
        "explicit_target": raw_target,
        "scope": raw_scope,
        "risk_level": "high",
        "external_side_effect": True,
        "retrieval_receipt_ids": [raw_retrieval_ref],
        "required_evidence_refs": [raw_evidence_ref],
        "created_at": "2026-06-26T00:00:00+00:00",
    }
    try:
        response = _client().post("/api/v1/shadow/inspect", json=request_payload)
    finally:
        deps._store.clear()
        deps._store.update(previous_store)

    payload = response.json()
    raw_context_hash = ShadowContext(
        request_id=request_payload["request_id"],
        stage=ShadowStage.PREFLIGHT,
        user_input=request_payload["user_input"],
        candidate_action=request_payload["candidate_action"],
        explicit_target=raw_target,
        scope=raw_scope,
        risk_level=ShadowSeverity.HIGH,
        external_side_effect=True,
        retrieval_receipt_ids=(raw_retrieval_ref,),
        created_at=request_payload["created_at"],
    ).with_integrity().context_hash
    persisted_results = (store_path / "shadow-results.jsonl").read_text(encoding="utf-8")
    persisted_receipts = (store_path / "shadow-receipts.jsonl").read_text(encoding="utf-8")
    persisted_payload = persisted_results + persisted_receipts
    assert response.status_code == 200
    assert payload["receipt"]["context_hash"] != raw_context_hash
    assert payload["receipt"]["retrieval_receipt_count"] == 1
    assert raw_target not in str(payload)
    assert raw_scope not in str(payload)
    assert raw_retrieval_ref not in str(payload)
    assert raw_evidence_ref not in str(payload)
    assert raw_target not in persisted_payload
    assert raw_scope not in persisted_payload
    assert raw_retrieval_ref not in persisted_payload
    assert raw_evidence_ref not in persisted_payload
    assert "shadow_retrieval_receipt_" in persisted_receipts
    assert "shadow_required_evidence_" in persisted_results


def test_shadow_inspect_route_redacts_secret_shaped_request_id() -> None:
    previous_store = dict(deps._store)
    raw_request_id = "operator-secret-token-001"
    deps._store.clear()
    deps.set("inceptadive_shadow_runtime", build_inceptadive_shadow_runtime({}))
    try:
        response = _client().post(
            "/api/v1/shadow/inspect",
            json={
                "request_id": raw_request_id,
                "stage": "interpretation",
                "user_input": "inspect bounded request id handling",
                "created_at": "2026-06-26T00:00:00+00:00",
            },
        )
    finally:
        deps._store.clear()
        deps._store.update(previous_store)

    payload = response.json()
    result = payload["result"]
    receipt = payload["receipt"]
    assert response.status_code == 200
    assert result["request_id"].startswith("shadow_request_")
    assert receipt["request_id"] == result["request_id"]
    assert raw_request_id not in str(payload)
    assert payload["raw_request_text_exposed"] is False
    assert payload["execution_authority"] is False


def test_shadow_inspect_route_matches_replay_contract_fixture() -> None:
    fixture = json.loads(
        (_FIXTURES / "inceptadive_shadow_inspect_replay.json").read_text(encoding="utf-8")
    )
    previous_store = dict(deps._store)
    deps._store.clear()
    deps.set(
        "inceptadive_shadow_runtime",
        build_inceptadive_shadow_runtime(fixture["runtime_env"]),
    )
    try:
        response = _client().post(fixture["route"], json=fixture["request"])
    finally:
        deps._store.clear()
        deps._store.update(previous_store)

    payload = response.json()
    expected = fixture["expected_response"]
    result = payload["result"]
    receipt = payload["receipt"]
    assert response.status_code == 200
    assert payload["governed"] == expected["governed"]
    assert payload["registered"] == expected["registered"]
    assert payload["execution_authority"] == expected["execution_authority"]
    assert payload["raw_request_text_exposed"] == expected["raw_request_text_exposed"]
    assert payload["private_memory_exposed"] == expected["private_memory_exposed"]
    assert payload["recent_activity"] == expected["recent_activity"]
    assert result["request_id"] == expected["result"]["request_id"]
    assert result["result_id"] == expected["result"]["result_id"]
    assert result["mode"] == expected["result"]["mode"]
    assert result["stage"] == expected["result"]["stage"]
    assert result["verdict"] == expected["result"]["verdict"]
    assert result["finding_count"] == expected["result"]["finding_count"]
    assert result["fracture_delta_count"] == expected["result"]["fracture_delta_count"]
    assert result["needs_repair"] == expected["result"]["needs_repair"]
    assert result["needs_deep_pass"] == expected["result"]["needs_deep_pass"]
    assert result["block_recommended"] == expected["result"]["block_recommended"]
    assert result["execution_authority"] == expected["result"]["execution_authority"]
    assert [finding["kind"] for finding in result["findings"]] == expected["result"]["finding_kinds"]
    assert [finding["evidence_ref_count"] for finding in result["findings"]] == (
        expected["result"]["finding_evidence_ref_counts"]
    )
    assert receipt["receipt_id"] == expected["receipt"]["receipt_id"]
    assert receipt["context_hash"] == expected["receipt"]["context_hash"]
    assert receipt["mode"] == expected["receipt"]["mode"]
    assert receipt["stage"] == expected["receipt"]["stage"]
    assert receipt["retrieval_receipt_count"] == expected["receipt"]["retrieval_receipt_count"]
    assert receipt["shadow_verdict"] == expected["receipt"]["shadow_verdict"]
    assert receipt["governance_verdict"] == expected["receipt"]["governance_verdict"]
    assert receipt["execution_authority"] == expected["receipt"]["execution_authority"]
    assert "secret-token" in fixture["request"]["user_input"]
    for token in fixture["absent_tokens"]:
        assert token not in str(payload)


def test_shadow_inspect_route_rejects_invalid_request_bounded() -> None:
    previous_store = dict(deps._store)
    deps._store.clear()
    deps.set("inceptadive_shadow_runtime", build_inceptadive_shadow_runtime({}))
    try:
        response = _client().post(
            "/api/v1/shadow/inspect",
            json={
                "stage": "unknown-stage",
                "user_input": "",
                "candidate_action": "",
            },
        )
    finally:
        deps._store.clear()
        deps._store.update(previous_store)

    detail = response.json()["detail"]
    assert response.status_code == 400
    assert detail["error"] == "invalid shadow inspect request"
    assert detail["error_code"] == "invalid_shadow_inspect_request"
    assert detail["governed"] is True
    assert "unknown-stage" not in str(response.json())


def test_shadow_inspect_route_rejects_validation_errors_without_raw_echo() -> None:
    previous_store = dict(deps._store)
    raw_marker = "validation-secret-token"
    deps._store.clear()
    deps.set("inceptadive_shadow_runtime", build_inceptadive_shadow_runtime({}))
    try:
        array_response = _client().post("/api/v1/shadow/inspect", json=[raw_marker])
        type_response = _client().post(
            "/api/v1/shadow/inspect",
            json={
                "request_id": "shadow-route-validation-001",
                "stage": "interpretation",
                "user_input": {"secret": raw_marker},
            },
        )
    finally:
        deps._store.clear()
        deps._store.update(previous_store)

    for response in (array_response, type_response):
        detail = response.json()["detail"]
        assert response.status_code == 400
        assert detail["error"] == "invalid shadow inspect request"
        assert detail["error_code"] == "invalid_shadow_inspect_request"
        assert detail["governed"] is True
        assert raw_marker not in str(response.json())


def test_shadow_inspect_route_rejects_unknown_fields_without_silent_acceptance() -> None:
    previous_store = dict(deps._store)
    raw_marker = "unknown-field-secret-token"
    deps._store.clear()
    deps.set("inceptadive_shadow_runtime", build_inceptadive_shadow_runtime({}))
    try:
        response = _client().post(
            "/api/v1/shadow/inspect",
            json={
                "request_id": "shadow-route-extra-field-001",
                "stage": "interpretation",
                "user_input": "inspect bounded request",
                "unexpected_secret": raw_marker,
            },
        )
    finally:
        deps._store.clear()
        deps._store.update(previous_store)

    detail = response.json()["detail"]
    assert response.status_code == 400
    assert detail["error"] == "invalid shadow inspect request"
    assert detail["error_code"] == "invalid_shadow_inspect_request"
    assert detail["governed"] is True
    assert raw_marker not in str(response.json())


def test_shadow_routes_fallback_when_runtime_unregistered() -> None:
    previous_store = dict(deps._store)
    deps._store.clear()
    try:
        health_response = _client().get("/api/v1/health/shadow")
        console_response = _client().get("/api/v1/console/shadow")
    finally:
        deps._store.clear()
        deps._store.update(previous_store)

    health_payload = health_response.json()
    console_payload = console_response.json()
    assert health_response.status_code == 200
    assert console_response.status_code == 200
    assert health_payload["registered"] is False
    assert console_payload["registered"] is False
    assert health_payload["shadow"]["execution_authority"] is False
    assert console_payload["summary"]["execution_authority"] is False


def test_shadow_routes_respect_disabled_runtime_posture() -> None:
    previous_store = dict(deps._store)
    deps._store.clear()
    deps.set(
        "inceptadive_shadow_runtime",
        build_inceptadive_shadow_runtime({"MULLU_INCEPTADIVE_SHADOW_ENABLED": "0"}),
    )
    try:
        health_response = _client().get("/api/v1/health/shadow")
        console_response = _client().get("/api/v1/console/shadow")
    finally:
        deps._store.clear()
        deps._store.update(previous_store)

    health_payload = health_response.json()
    console_payload = console_response.json()
    assert health_payload["shadow"]["status"] == "disabled"
    assert health_payload["shadow"]["enabled"] is False
    assert console_payload["status"] == "disabled"
    assert console_payload["summary"]["enabled"] is False
    assert health_payload["execution_authority"] is False
    assert console_payload["execution_authority"] is False


def test_shadow_inspect_route_respects_disabled_runtime_posture() -> None:
    previous_store = dict(deps._store)
    deps._store.clear()
    deps.set(
        "inceptadive_shadow_runtime",
        build_inceptadive_shadow_runtime({"MULLU_INCEPTADIVE_SHADOW_ENABLED": "0"}),
    )
    try:
        response = _client().post(
            "/api/v1/shadow/inspect",
            json={
                "request_id": "shadow-route-disabled-001",
                "stage": "interpretation",
                "user_input": "deploy it with disabled-secret-token",
                "risk_level": "high",
                "external_side_effect": True,
                "created_at": "2026-06-19T00:00:00+00:00",
            },
        )
    finally:
        deps._store.clear()
        deps._store.update(previous_store)

    payload = response.json()
    result = payload["result"]
    receipt = payload["receipt"]
    assert response.status_code == 200
    assert payload["governed"] is True
    assert payload["registered"] is True
    assert payload["execution_authority"] is False
    assert payload["raw_request_text_exposed"] is False
    assert payload["private_memory_exposed"] is False
    assert result["mode"] == "off"
    assert result["verdict"] == "clear"
    assert result["execution_authority"] is False
    assert result["finding_count"] == 1
    assert receipt["mode"] == "off"
    assert receipt["shadow_verdict"] == "clear"
    assert receipt["execution_authority"] is False
    assert payload["recent_activity"]["result_count"] == 1
    assert payload["recent_activity"]["receipt_count"] == 1
    assert "deploy it with disabled-secret-token" not in str(payload)
    assert "disabled-secret-token" not in str(payload)


def test_external_effect_advisory_route_returns_missing_obligations_redacted() -> None:
    previous_store = dict(deps._store)
    deps._store.clear()
    deps.set("inceptadive_shadow_runtime", build_inceptadive_shadow_runtime({}))
    try:
        response = _client().post(
            "/api/v1/shadow/external-effect/advisory",
            json={
                "request_id": "shadow-route-external-effect-001",
                "stage": "preflight",
                "user_input": "deploy it with secret-token",
                "candidate_action": "deploy it with secret-token",
                "risk_level": "high",
                "external_side_effect": True,
                "created_at": "2026-06-21T00:00:00+00:00",
            },
        )
    finally:
        deps._store.clear()
        deps._store.update(previous_store)

    payload = response.json()
    advisory = payload["advisory"]
    assert response.status_code == 200
    assert payload["governed"] is True
    assert payload["registered"] is True
    assert payload["execution_authority"] is False
    assert payload["connector_dispatch_authority"] is False
    assert payload["memory_write_authority"] is False
    assert payload["governance_verdict_authority"] is False
    assert advisory["recommended_outcome"] == "AwaitingEvidence"
    assert advisory["awaiting_evidence"] is True
    assert "deployment:governance_verdict" in advisory["missing_authority_obligations"]
    assert "deployment:evidence_ref" in advisory["missing_evidence_obligations"]
    assert advisory["execution_authority"] is False
    assert "deploy it with secret-token" not in str(payload)
    assert "secret-token" not in str(payload)


def test_external_effect_advisory_route_closes_refs_without_exposing_refs() -> None:
    previous_store = dict(deps._store)
    deps._store.clear()
    deps.set("inceptadive_shadow_runtime", build_inceptadive_shadow_runtime({}))
    try:
        response = _client().post(
            "/api/v1/shadow/external-effect/advisory",
            json={
                "request_id": "shadow-route-external-effect-002",
                "stage": "preflight",
                "user_input": "send approved receipt",
                "candidate_action": "send approved receipt",
                "explicit_target": "operator-review-inbox",
                "scope": "support-workflow",
                "risk_level": "high",
                "external_side_effect": True,
                "required_evidence_refs": ["approval-secret-ref"],
                "authority_receipt_refs": ["authority-secret-ref"],
                "created_at": "2026-06-21T00:00:00+00:00",
            },
        )
    finally:
        deps._store.clear()
        deps._store.update(previous_store)

    payload = response.json()
    advisory = payload["advisory"]
    assert response.status_code == 200
    assert advisory["recommended_outcome"] == "SolvedUnverified"
    assert advisory["missing_authority_obligations"] == []
    assert advisory["missing_evidence_obligations"] == []
    assert advisory["required_evidence_ref_count"] == 1
    assert advisory["authority_receipt_count"] == 1
    assert advisory["connector_dispatch_authority"] is False
    assert payload["raw_request_text_exposed"] is False
    assert "approval-secret-ref" not in str(payload)
    assert "authority-secret-ref" not in str(payload)


def test_external_effect_advisory_route_redacts_secret_shaped_request_id() -> None:
    previous_store = dict(deps._store)
    raw_request_id = "advisory-private-token-001"
    deps._store.clear()
    deps.set("inceptadive_shadow_runtime", build_inceptadive_shadow_runtime({}))
    try:
        response = _client().post(
            "/api/v1/shadow/external-effect/advisory",
            json={
                "request_id": raw_request_id,
                "stage": "preflight",
                "user_input": "inspect external-effect request id handling",
                "candidate_action": "inspect only",
                "created_at": "2026-06-26T00:00:00+00:00",
            },
        )
    finally:
        deps._store.clear()
        deps._store.update(previous_store)

    payload = response.json()
    advisory = payload["advisory"]
    assert response.status_code == 200
    assert advisory["request_id"].startswith("shadow_request_")
    assert raw_request_id not in str(payload)
    assert payload["raw_request_text_exposed"] is False
    assert payload["execution_authority"] is False
    assert advisory["execution_authority"] is False


def test_external_effect_advisory_route_rejects_invalid_request_bounded() -> None:
    previous_store = dict(deps._store)
    deps._store.clear()
    deps.set("inceptadive_shadow_runtime", build_inceptadive_shadow_runtime({}))
    try:
        response = _client().post(
            "/api/v1/shadow/external-effect/advisory",
            json={
                "stage": "preflight",
                "user_input": "send notice",
                "risk_level": "not-a-severity",
            },
        )
    finally:
        deps._store.clear()
        deps._store.update(previous_store)

    detail = response.json()["detail"]
    assert response.status_code == 400
    assert detail["error"] == "invalid external-effect advisory request"
    assert detail["error_code"] == "invalid_external_effect_advisory_request"
    assert detail["governed"] is True
    assert "not-a-severity" not in str(response.json())


def test_external_effect_advisory_route_rejects_validation_errors_without_raw_echo() -> None:
    previous_store = dict(deps._store)
    raw_marker = "advisory-validation-secret-token"
    deps._store.clear()
    deps.set("inceptadive_shadow_runtime", build_inceptadive_shadow_runtime({}))
    try:
        response = _client().post(
            "/api/v1/shadow/external-effect/advisory",
            json={
                "request_id": "shadow-route-advisory-validation-001",
                "stage": "preflight",
                "user_input": "inspect external effect",
                "unexpected_secret": raw_marker,
            },
        )
    finally:
        deps._store.clear()
        deps._store.update(previous_store)

    detail = response.json()["detail"]
    assert response.status_code == 400
    assert detail["error"] == "invalid external-effect advisory request"
    assert detail["error_code"] == "invalid_external_effect_advisory_request"
    assert detail["governed"] is True
    assert raw_marker not in str(response.json())


def test_default_routers_include_shadow_inspect_path() -> None:
    app = FastAPI()
    include_default_routers(app)
    paths = set(app.openapi()["paths"])

    assert "/api/v1/health/shadow" in paths
    assert "/api/v1/console/shadow" in paths
    assert "/api/v1/console/shadow/evidence" in paths
    assert "/api/v1/shadow/inspect" in paths
    assert "/api/v1/shadow/external-effect/advisory" in paths
