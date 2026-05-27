"""Mullu OrgOS API tests.

Purpose: verify the minimal organization-kernel API binds organizations,
    cases, plan gates, evidence events, and closure decisions without exposing
    a worker execution surface.
Governance scope: FastAPI entrypoints for OrgGraph, WorkGraph, AuthorityGraph,
    EvidenceGraph, and append-only case events.
Dependencies: gateway.server and gateway.orgos_kernel.
Invariants:
  - API calls create governed records only; they do not dispatch workers.
  - Authority decisions must bind to local authority rules before a case can
    advance toward closure.
  - Closure requires effect reconciliation evidence and terminal disposition.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from gateway.server import create_gateway_app


NOW = "2026-05-05T12:00:00+00:00"


def test_orgos_api_runs_launch_gateway_case_control_loop() -> None:
    client = TestClient(create_gateway_app(platform=None))

    org_response = client.post("/api/v1/orgs", json=_org_payload())
    case_response = client.post("/api/v1/cases", json=_case_payload())
    event_response = client.post(
        "/api/v1/cases/case-launch-gateway/events",
        json={
            "event_type": "evidence_added",
            "actor_id": "engineering_owner",
            "payload": {"evidence_ref": "world:runtime-target-bound"},
            "evidence_refs": ["world:runtime-target-bound"],
        },
    )
    plan_response = client.post(
        "/api/v1/cases/case-launch-gateway/plan",
        json={
            "actor_id": "engineering_owner",
            "step": _step_payload(),
            "gate": _gate_payload(),
        },
    )
    close_response = client.post(
        "/api/v1/cases/case-launch-gateway/close",
        json={
            "actor_id": "engineering_owner",
            "closure": _closure_payload(),
            "terminal_certificate": _terminal_certificate_payload(),
        },
    )
    get_response = client.get("/api/v1/cases/case-launch-gateway")

    assert org_response.status_code == 200
    assert case_response.status_code == 200
    assert event_response.status_code == 200
    assert plan_response.status_code == 200
    assert close_response.status_code == 200
    assert get_response.status_code == 200
    assert org_response.json()["organization"]["organization_hash"]
    assert case_response.json()["case"]["status"] == "open"
    assert event_response.json()["event"]["prev_event_hash"]
    assert event_response.json()["event"]["receipt"]["signature"].startswith("hmac-sha256:")
    assert event_response.json()["event"]["receipt"]["receipt_hash"]
    assert plan_response.json()["gate_decision"]["verdict"] == "allow"
    assert close_response.json()["closure_decision"]["verdict"] == "allow"
    assert close_response.json()["closure_decision"]["resulting_status"] == "closed"
    assert get_response.json()["case"]["status"] == "closed"
    assert get_response.json()["events"]["total"] == 6


def test_orgos_api_denies_unbound_authority_gate() -> None:
    client = TestClient(create_gateway_app(platform=None))
    client.post("/api/v1/orgs", json=_org_payload())
    client.post("/api/v1/cases", json=_case_payload())

    response = client.post(
        "/api/v1/cases/case-launch-gateway/plan",
        json={
            "actor_id": "engineering_owner",
            "step": _step_payload(),
            "gate": {
                **_gate_payload(),
                "authority_decision": {
                    **_authority_decision_payload(),
                    "matched_grant_ids": ["unknown-rule"],
                },
            },
        },
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["step"]["step_id"] == "step-gateway-health"
    assert payload["gate_decision"]["verdict"] == "deny"
    assert "authority_rule_not_bound_to_step" in payload["gate_decision"]["reasons"]
    assert "authority_rule_binding" in payload["gate_decision"]["required_controls"]


def test_orgos_api_org_registration_rolls_back_invalid_authority_bundle() -> None:
    client = TestClient(create_gateway_app(platform=None))
    invalid = _org_payload()
    invalid["authority_rules"] = [
        {
            **invalid["authority_rules"][0],
            "action": "payment.prepare",
        }
    ]

    rejected = client.post("/api/v1/orgs", json=invalid)
    accepted = client.post("/api/v1/orgs", json=_org_payload())
    case_response = client.post("/api/v1/cases", json=_case_payload())

    assert rejected.status_code == 400
    assert rejected.json()["detail"] == "authority_rule_action_outside_role_permissions"
    assert accepted.status_code == 200
    assert accepted.json()["organization"]["org_id"] == "org-mullusi"
    assert case_response.status_code == 200
    assert case_response.json()["case"]["case_id"] == "case-launch-gateway"


def test_orgos_api_replays_projection_from_jsonl_event_log(tmp_path, monkeypatch) -> None:
    event_log_path = tmp_path / "orgos-events.jsonl"
    monkeypatch.setenv("MULLU_ORGOS_CASE_EVENT_LOG_PATH", str(event_log_path))
    first_client = TestClient(create_gateway_app(platform=None))

    first_client.post("/api/v1/orgs", json=_org_payload())
    first_client.post("/api/v1/cases", json=_case_payload())
    first_client.post(
        "/api/v1/cases/case-launch-gateway/events",
        json={
            "event_type": "evidence_added",
            "actor_id": "engineering_owner",
            "payload": {"evidence_ref": "world:runtime-target-bound"},
            "evidence_refs": ["world:runtime-target-bound"],
        },
    )
    first_client.post(
        "/api/v1/cases/case-launch-gateway/plan",
        json={"actor_id": "engineering_owner", "step": _step_payload(), "gate": _gate_payload()},
    )
    first_client.post(
        "/api/v1/cases/case-launch-gateway/close",
        json={
            "actor_id": "engineering_owner",
            "closure": _closure_payload(),
            "terminal_certificate": _terminal_certificate_payload(),
        },
    )

    second_client = TestClient(create_gateway_app(platform=None))
    replayed_case = second_client.get("/api/v1/cases/case-launch-gateway")
    replay_response = second_client.post("/api/v1/orgos/replay")
    read_model = second_client.get("/api/v1/orgos/read-model")

    assert event_log_path.exists()
    assert replayed_case.status_code == 200
    assert replayed_case.json()["case"]["status"] == "closed"
    assert replayed_case.json()["case"]["closure_certificate_ref"] == "terminal-gateway-1"
    assert replay_response.status_code == 200
    assert replay_response.json()["event_count"] == 7
    assert read_model.status_code == 200
    assert read_model.json()["orgos"]["case_loop"]["closed_case_count"] == 1
    assert read_model.json()["events"]["total"] == 7


def _org_payload() -> dict[str, object]:
    return {
        "org_id": "org-mullusi",
        "tenant_id": "tenant-a",
        "name": "Mullusi",
        "owner_role_id": "executive_owner",
        "evidence_refs": ["org:evidence:charter"],
        "owner_role": {
            "role_id": "executive_owner",
            "department_id": "executive",
            "permissions": ["objective.freeze", "approval.grant"],
            "approval_limit_risk": "critical",
            "evidence_refs": ["role:evidence:executive"],
        },
        "roles": [
            {
                "role_id": "engineering_owner",
                "department_id": "engineering",
                "permissions": ["gateway.health.check", "runtime.conformance.collect"],
                "approval_limit_risk": "high",
                "evidence_refs": ["role:evidence:engineering"],
            }
        ],
        "authority_rules": [
            {
                "rule_id": "rule-engineering-gateway",
                "role_id": "engineering_owner",
                "action": "gateway.health.check",
                "resource_type": "gateway_runtime",
                "max_risk": "high",
                "requires_dual_control": True,
                "separation_of_duty": ["executive_owner"],
                "evidence_refs": ["authority:evidence:engineering-rule"],
            }
        ],
    }


def _case_payload() -> dict[str, object]:
    return {
        "case_id": "case-launch-gateway",
        "org_id": "org-mullusi",
        "tenant_id": "tenant-a",
        "department_id": "engineering",
        "case_type": "launch_gateway_pilot",
        "goal": "Launch Gateway Pilot",
        "risk_tier": "high",
        "owner_role_id": "engineering_owner",
        "status": "open",
        "evidence_refs": ["case:intake:launch-gateway"],
    }


def _step_payload() -> dict[str, object]:
    return {
        "step_id": "step-gateway-health",
        "department_id": "engineering",
        "capability_id": "gateway.health.check",
        "risk_tier": "high",
        "preconditions": ["world:runtime-target-bound"],
        "postconditions": ["gateway_published"],
        "evidence_required": ["runtime_health_ref", "gateway_witness_ref", "runtime_conformance_ref"],
        "approvals_required": ["approval:engineering_owner"],
        "expected_effects": ["gateway_published"],
        "forbidden_effects": ["secret_exposed", "unverified_public_claim"],
        "rollback_plan_id": "rollback:gateway-pilot",
    }


def _gate_payload() -> dict[str, object]:
    return {
        "authority_decision": _authority_decision_payload(),
        "policy_allowed": True,
        "world_refs": ["world:runtime-target-bound"],
        "certified_capabilities": ["gateway.health.check"],
        "evidence_refs": ["runtime_health_ref", "gateway_witness_ref", "runtime_conformance_ref"],
        "approval_refs": ["approval:engineering_owner"],
    }


def _authority_decision_payload() -> dict[str, object]:
    return {
        "decision_id": "authority-decision-gateway-1",
        "request_id": "authority-request-gateway-1",
        "actor_id": "engineering_owner",
        "tenant_id": "tenant-a",
        "verdict": "allow",
        "reason": "authority_grant_satisfied",
        "required_controls": ["terminal_closure"],
        "matched_grant_ids": ["rule-engineering-gateway"],
        "evidence_refs": ["authority:evidence:engineering-rule"],
    }


def _closure_payload() -> dict[str, object]:
    return {
        "expected_effects": ["gateway_published"],
        "observed_effects": ["gateway_published"],
        "forbidden_effects_checked": True,
        "evidence_refs": ["evidence:gateway-witness", "evidence:runtime-conformance"],
        "effect_reconciliation_ref": "recon-gateway-1",
        "terminal_disposition": "committed",
    }


def _terminal_certificate_payload() -> dict[str, object]:
    return {
        "certificate_id": "terminal-gateway-1",
        "command_id": "command-gateway-1",
        "execution_id": "execution-gateway-1",
        "disposition": "committed",
        "verification_result_id": "verification-gateway-1",
        "effect_reconciliation_id": "recon-gateway-1",
        "evidence_refs": ["evidence:gateway-witness", "evidence:runtime-conformance"],
        "closed_at": NOW,
    }
