"""Purpose: verify assistant kernel HTTP planning routes.
Governance scope: profile read models, FinanceOps and TeamOps plan compilation, consent
    evidence, non-execution, default router mounting, and bounded failures.
Dependencies: FastAPI TestClient and mcoi_runtime.app.routers.assistant.
Invariants:
  - Assistant routes compile plans only and never grant execution authority.
  - FinanceOps external payment effects require active consent evidence.
  - TeamOps external message effects require active consent evidence.
  - Ready plans still require governed dispatch outside the assistant route.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from mcoi_runtime.app.inceptadive_shadow_integration import build_inceptadive_shadow_runtime
from mcoi_runtime.app.routers import assistant as assistant_router_module
from mcoi_runtime.app.routers.assistant import router
from mcoi_runtime.app.routers.deps import deps
from mcoi_runtime.app.server_http import include_default_routers


class MetricsStub:
    def __init__(self) -> None:
        self.counts: dict[str, int] = {}

    def inc(self, name: str, value: int = 1) -> None:
        self.counts[name] = self.counts.get(name, 0) + value


class FixedClock:
    def __call__(self) -> str:
        return "2026-05-13T10:00:00+00:00"


def _client() -> TestClient:
    deps.set("clock", FixedClock())
    deps.set("metrics", MetricsStub())
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _plan_request(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "tenant_id": "tenant-finance",
        "owner_id": "finance-owner",
        "invoice_ref": "invoice:1001",
        "vendor_ref": "vendor:acme",
        "created_at": "2026-05-13T10:00:00+00:00",
    }
    payload.update(overrides)
    return payload


def _active_consent_plan_request() -> dict[str, object]:
    return _plan_request(
        consent_granted_by="finance-owner",
        consent_expires_at="2026-05-13T12:00:00+00:00",
        consent_evidence_refs=["approval:finance-owner"],
    )


def _team_ops_plan_request(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "tenant_id": "tenant-team",
        "owner_id": "ops-owner",
        "inbox_ref": "shared-inbox:support",
        "request_ref": "shared-request:1001",
        "created_at": "2026-05-13T10:00:00+00:00",
    }
    payload.update(overrides)
    return payload


def _active_team_ops_consent_plan_request() -> dict[str, object]:
    return _team_ops_plan_request(
        consent_granted_by="ops-owner",
        consent_expires_at="2026-05-13T12:00:00+00:00",
        consent_evidence_refs=["approval:ops-owner"],
    )


def test_assistant_profiles_read_model_exposes_finance_ops_profile() -> None:
    client = _client()

    response = client.get("/api/v1/assistant/profiles")
    body = response.json()
    finance_profile = next(profile for profile in body["profiles"] if profile["assistant_id"] == "finance_ops.default")
    team_profile = next(profile for profile in body["profiles"] if profile["assistant_id"] == "team_ops.default")

    assert response.status_code == 200
    assert body["count"] == 6
    assert body["governed"] is True
    assert "payment.execute.with_approval" in finance_profile["allowed_capabilities"]
    assert "payment.execute" in finance_profile["forbidden_capabilities"]
    assert "signed_evidence_bundle" in finance_profile["evidence_required"]
    assert "email.send.with_approval" in team_profile["allowed_capabilities"]
    assert "task.assign" in team_profile["allowed_capabilities"]
    assert team_profile["external_send_policy"] == "approval_required"


def test_personal_assistant_skill_read_model_is_deployed_read_only() -> None:
    client = _client()

    response = client.get("/api/v1/personal-assistant/skills")
    body = response.json()

    assert response.status_code == 200
    assert body["governed"] is True
    assert body["execution_allowed"] is False
    assert body["live_connector_execution_allowed"] is False
    assert body["registry"]["skill_count"] >= 14
    assert "personal_assistant.clarification.request" in body["registry"]["skill_ids"]


def test_personal_assistant_pilot_read_model_is_no_effect_demo() -> None:
    client = _client()

    response = client.get("/api/v1/personal-assistant/pilot/read-model")
    post_response = client.post("/api/v1/personal-assistant/pilot/read-model", json={})
    body = response.json()

    assert response.status_code == 200
    assert post_response.status_code == 405
    assert body["pilot_id"] == "governed_team_assistant_pilot_v0"
    assert body["stage"] == "controlled_demo_productization"
    assert body["dashboard_projection"]["read_only"] is True
    assert body["dashboard_projection"]["repository_write_allowed"] is False
    assert body["demo_scenario"]["dry_run_receipt_trail"]["actions_not_taken_recorded"] is True
    assert body["pr_2058_review_decision"]["decision"] == "hold_open_do_not_merge"
    assert body["pr_2058_review_decision"]["merge_allowed"] is False
    assert body["inceptadive_advisory_panel"]["advisory_only"] is True
    assert body["deterministic_replay"]["external_calls_allowed"] is False
    assert body["approval_authority_next_phase"]["execution_authority_granted_by_demo"] is False
    assert body["execution_allowed"] is False
    assert body["repository_write_allowed"] is False
    assert body["worker_dispatch_allowed"] is False
    assert body["live_receipt_append_allowed"] is False


def test_personal_assistant_preview_compiles_inbox_request_without_execution() -> None:
    client = _client()

    response = client.post(
        "/api/v1/personal-assistant/requests/preview",
        json={
            "user_request": "Check important inbox items and prepare response drafts only.",
            "request_id": "pa_request_router_inbox_001",
            "submitted_at": "2026-05-13T10:00:00+00:00",
            "connector_refs": [
                {
                    "connector_id": "connector:gmail:operator",
                    "connector_name": "gmail",
                    "proof_state": "Pass",
                    "private_data_allowed": True,
                    "scopes": ["gmail.readonly"],
                }
            ],
            "include_console_read_model": True,
        },
    )
    body = response.json()

    assert response.status_code == 200
    assert body["governed"] is True
    assert body["request"]["execution_mode"] == "read_and_draft_only"
    assert body["plan"]["execution_allowed"] is False
    assert body["receipt"]["decision"] == "allowed"
    assert body["receipt"]["private_payload_policy"]["secret_values_serialized"] is False
    assert body["clarification_bundle"]["clarification_count"] == 0
    assert body["effect_boundary"]["external_send_allowed"] is False
    assert body["console_read_model"]["effect_boundary"]["execution_allowed"] is False
    assert body["inceptadive_shadow_advisory"]["execution_authority"] is False
    assert body["inceptadive_shadow_advisory"]["raw_request_text_exposed"] is False
    assert body["inceptadive_shadow_advisory"]["private_memory_exposed"] is False


def test_personal_assistant_preview_blocks_unknown_request_with_whqr_step() -> None:
    client = _client()

    response = client.post(
        "/api/v1/personal-assistant/requests/preview",
        json={
            "user_request": "Handle this for me.",
            "request_id": "pa_request_router_unknown_001",
            "submitted_at": "2026-05-13T10:00:00+00:00",
        },
    )
    body = response.json()

    assert response.status_code == 200
    assert body["outcome"] == "AwaitingEvidence"
    assert body["request"]["execution_mode"] == "blocked"
    assert body["clarification_bundle"]["clarification_count"] == 1
    assert body["plan"]["steps"][0]["skill_id"] == "personal_assistant.clarification.request"
    assert body["receipt"]["decision"] == "blocked"
    assert "plan_execution_blocked_until_clarification" in body["receipt"]["actions_not_taken"]
    assert body["inceptadive_shadow_advisory"]["stage"] == "planning"
    assert body["inceptadive_shadow_advisory"]["governance_required"] is True
    assert body["inceptadive_shadow_advisory"]["execution_authority"] is False


def test_personal_assistant_preview_fails_closed_on_invalid_request() -> None:
    client = _client()

    response = client.post(
        "/api/v1/personal-assistant/requests/preview",
        json={
            "user_request": "",
            "request_id": "pa_request_router_invalid_001",
            "submitted_at": "2026-05-13T10:00:00+00:00",
        },
    )
    detail = response.json()["detail"]

    assert response.status_code == 400
    assert detail["error"] == "invalid personal assistant preview"
    assert detail["error_code"] == "invalid_personal_assistant_preview"
    assert detail["governed"] is True


def test_finance_ops_plan_blocks_without_active_payment_consent() -> None:
    client = _client()

    response = client.post("/api/v1/assistant/finance-ops/plans", json=_plan_request())
    body = response.json()

    assert response.status_code == 200
    assert body["outcome"] == "AwaitingEvidence"
    assert body["plan"]["blocked"] is True
    assert "active_consent_required:payment.execute.with_approval" in body["plan"]["blocked_reasons"]
    assert body["operator_queue_item"]["state"] == "blocked"
    assert body["operator_queue_item"]["execution_authority_granted"] is False
    assert body["operator_queue_item"]["life_meaning_judgment_required"] is True
    assert body["operator_queue_item"]["life_meaning_judgment_ref"] == body["plan"]["metadata"]["life_meaning_judgment_ref"]
    assert body["plan"]["steps"] == []


def test_finance_ops_plan_with_consent_projects_dispatch_ready_controls() -> None:
    client = _client()

    response = client.post(
        "/api/v1/assistant/finance-ops/plans",
        json=_active_consent_plan_request(),
    )
    body = response.json()

    assert response.status_code == 200
    assert body["outcome"] == "SolvedUnverified"
    assert body["plan"]["blocked"] is False
    assert body["operator_queue_item"]["state"] == "ready_for_governed_dispatch"
    assert body["operator_queue_item"]["execution_authority_granted"] is False
    assert body["operator_queue_item"]["life_meaning_judgment_required"] is True
    assert body["operator_queue_item"]["life_meaning_judgment_ref"] == body["plan"]["metadata"]["life_meaning_judgment_ref"]
    assert "active_consent" in body["plan"]["required_controls"]
    assert "temporal_idempotency" in body["plan"]["required_controls"]
    assert "effect_reconciliation" in body["plan"]["required_controls"]
    assert body["plan"]["closure_contract"]["two_confirmation_required"] is True
    assert "signed_evidence_bundle_exists" in body["goal"]["required_closure_predicates"]
    assert any(step["capability_id"] == "payment.execute.with_approval" for step in body["plan"]["steps"])
    assert body["inceptadive_shadow_advisory"]["execution_authority"] is False
    assert body["inceptadive_shadow_advisory"]["governance_required"] is True
    assert body["inceptadive_shadow_advisory"]["receipt_id"].startswith("shadow-receipt-")
    assert "approval:finance-owner" not in str(body["inceptadive_shadow_advisory"])


def test_finance_ops_plan_records_inceptadive_shadow_advisory_history() -> None:
    client = _client()
    runtime = build_inceptadive_shadow_runtime({"MULLU_INCEPTADIVE_SHADOW_DEEP_ENGINE_AVAILABLE": "1"})
    deps.set("inceptadive_shadow_runtime", runtime)

    response = client.post(
        "/api/v1/assistant/finance-ops/plans",
        json=_active_consent_plan_request(),
    )
    body = response.json()
    results, receipts = runtime.recent_activity(limit=5)

    assert response.status_code == 200
    assert body["inceptadive_shadow_advisory"]["status"] in {
        "advisory",
        "block_recommended",
        "deep_required",
        "repair_required",
    }
    assert len(results) == 1
    assert len(receipts) == 1
    assert results[0].to_dict()["execution_authority"] is False
    assert receipts[0].to_dict()["execution_authority"] is False
    assert "approval:finance-owner" not in str(body["inceptadive_shadow_advisory"])


def test_team_ops_plan_blocks_without_active_external_send_consent() -> None:
    client = _client()

    response = client.post("/api/v1/assistant/team-ops/plans", json=_team_ops_plan_request())
    body = response.json()

    assert response.status_code == 200
    assert body["outcome"] == "AwaitingEvidence"
    assert body["plan"]["blocked"] is True
    assert "active_consent_required:email.send.with_approval" in body["plan"]["blocked_reasons"]
    assert body["operator_queue_item"]["state"] == "blocked"
    assert body["operator_queue_item"]["execution_authority_granted"] is False
    assert body["operator_queue_item"]["life_meaning_judgment_required"] is True
    assert body["operator_queue_item"]["life_meaning_judgment_ref"] == body["plan"]["metadata"]["life_meaning_judgment_ref"]
    assert body["plan"]["steps"] == []


def test_team_ops_plan_with_consent_projects_dispatch_ready_controls() -> None:
    client = _client()

    response = client.post(
        "/api/v1/assistant/team-ops/plans",
        json=_active_team_ops_consent_plan_request(),
    )
    body = response.json()

    assert response.status_code == 200
    assert body["outcome"] == "SolvedUnverified"
    assert body["profile"]["assistant_id"] == "team_ops.default"
    assert body["plan"]["blocked"] is False
    assert body["operator_queue_item"]["state"] == "ready_for_governed_dispatch"
    assert body["operator_queue_item"]["execution_authority_granted"] is False
    assert body["operator_queue_item"]["life_meaning_judgment_required"] is True
    assert body["operator_queue_item"]["life_meaning_judgment_ref"] == body["plan"]["metadata"]["life_meaning_judgment_ref"]
    assert "active_consent" in body["plan"]["required_controls"]
    assert "temporal_idempotency" in body["plan"]["required_controls"]
    assert "effect_reconciliation" in body["plan"]["required_controls"]
    assert body["plan"]["closure_contract"]["two_confirmation_required"] is True
    assert "message_send_receipt_exists" in body["goal"]["required_closure_predicates"]
    assert any(step["capability_id"] == "email.send.with_approval" for step in body["plan"]["steps"])


def test_invalid_finance_ops_plan_fails_closed() -> None:
    client = _client()

    response = client.post(
        "/api/v1/assistant/finance-ops/plans",
        json=_plan_request(invoice_ref=""),
    )

    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "invalid assistant plan"
    assert response.json()["detail"]["error_code"] == "invalid_assistant_plan"
    assert response.json()["detail"]["governed"] is True


def test_invalid_team_ops_plan_fails_closed() -> None:
    client = _client()

    response = client.post(
        "/api/v1/assistant/team-ops/plans",
        json=_team_ops_plan_request(inbox_ref=""),
    )

    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "invalid assistant plan"
    assert response.json()["detail"]["error_code"] == "invalid_assistant_plan"
    assert response.json()["detail"]["governed"] is True


def test_finance_ops_plan_error_detail_is_bounded(monkeypatch) -> None:
    client = _client()

    def fail_goal(*args: object, **kwargs: object) -> object:
        raise assistant_router_module.RuntimeCoreInvariantError("secret-token-from-assistant")

    monkeypatch.setattr(assistant_router_module, "finance_ops_invoice_payment_goal", fail_goal)

    response = client.post("/api/v1/assistant/finance-ops/plans", json=_active_consent_plan_request())
    detail = response.json()["detail"]

    assert response.status_code == 400
    assert detail["error"] == "invalid assistant plan"
    assert detail["error_code"] == "invalid_assistant_plan"
    assert detail["governed"] is True
    assert "secret-token-from-assistant" not in response.text
    assert "approval:finance-owner" not in response.text


def test_team_ops_plan_error_detail_is_bounded(monkeypatch) -> None:
    client = _client()

    def fail_goal(*args: object, **kwargs: object) -> object:
        raise assistant_router_module.RuntimeCoreInvariantError("secret-token-from-teamops")

    monkeypatch.setattr(assistant_router_module, "team_ops_shared_inbox_goal", fail_goal)

    response = client.post("/api/v1/assistant/team-ops/plans", json=_active_team_ops_consent_plan_request())
    detail = response.json()["detail"]

    assert response.status_code == 400
    assert detail["error"] == "invalid assistant plan"
    assert detail["error_code"] == "invalid_assistant_plan"
    assert detail["governed"] is True
    assert "secret-token-from-teamops" not in response.text
    assert "approval:ops-owner" not in response.text


def test_default_routers_include_assistant_kernel_paths() -> None:
    deps.set("clock", FixedClock())
    deps.set("metrics", MetricsStub())
    app = FastAPI()
    include_default_routers(app)
    paths = set(app.openapi()["paths"])

    assert "/api/v1/assistant/profiles" in paths
    assert "/api/v1/assistant/finance-ops/plans" in paths
    assert "/api/v1/assistant/team-ops/plans" in paths
    assert "/api/v1/personal-assistant/skills" in paths
    assert "/api/v1/personal-assistant/pilot/read-model" in paths
    assert "/api/v1/personal-assistant/requests/preview" in paths
