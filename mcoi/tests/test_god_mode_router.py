"""HTTP-surface tests for the god-mode router.

Covers the catalog/agreement/ticket/receipt endpoints. Each test runs
against a FastAPI app mounted only with the god_mode router and a fresh
process-wide registry+engine to keep state isolated.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from mcoi_runtime.app.routers.god_mode import router
from mcoi_runtime.core.god_mode_engine import GodModeEngine, set_engine
from mcoi_runtime.core.god_mode_integration import install_default_capabilities
from mcoi_runtime.core.god_mode_registry import GodModeRegistry, set_registry


_LONG = "x" * 60
_VERY_LONG = "x" * 130


def _client() -> TestClient:
    fresh_registry = GodModeRegistry()
    install_default_capabilities(fresh_registry)
    set_registry(fresh_registry)
    set_engine(GodModeEngine(registry=fresh_registry))
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _agree(client: TestClient, module: str, name: str, actor: str = "alice") -> str:
    resp = client.post(
        f"/api/v1/god-mode/capabilities/{module}/{name}/agree-to-register",
        json={"actor_id": actor, "justification": _VERY_LONG},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["agreement"]["agreement_id"]


def _issue_ticket(
    client: TestClient,
    module: str,
    name: str,
    actor: str = "alice",
) -> str:
    resp = client.post(
        f"/api/v1/god-mode/capabilities/{module}/{name}/issue-ticket",
        json={
            "actor_id": actor,
            "justification": _VERY_LONG,
            "target": {"tenant_id": "acme-7"},
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["ticket"]["ticket_id"]


# --- Catalog ---


def test_list_capabilities_seeds_default_proposals():
    client = _client()
    resp = client.get("/api/v1/god-mode/capabilities")
    assert resp.status_code == 200
    body = resp.json()
    assert body["governed"] is True
    assert body["count"] >= 10
    states = {c["state"] for c in body["capabilities"]}
    assert states == {"dormant"}


def test_list_capabilities_filter_by_module():
    client = _client()
    resp = client.get("/api/v1/god-mode/capabilities", params={"module": "data"})
    assert resp.status_code == 200
    body = resp.json()
    for cap in body["capabilities"]:
        assert cap["capability"]["module"] == "data"


def test_list_modules_returns_armed_count_zero_initially():
    client = _client()
    resp = client.get("/api/v1/god-mode/modules")
    assert resp.status_code == 200
    body = resp.json()
    by_name = {m["module"]: m for m in body["modules"]}
    assert "data" in by_name
    assert by_name["data"]["armed_count"] == 0


def test_get_unknown_capability_returns_404():
    client = _client()
    resp = client.get("/api/v1/god-mode/capabilities/ghost/missing")
    assert resp.status_code == 404


# --- Registration agreements ---


def test_agree_to_register_arms_capability():
    client = _client()
    resp = client.post(
        "/api/v1/god-mode/capabilities/replay/mutate_recorder/agree-to-register",
        json={"actor_id": "alice", "justification": _VERY_LONG},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["state"] == "armed"
    detail = client.get("/api/v1/god-mode/capabilities/replay/mutate_recorder").json()
    assert detail["state"] == "armed"
    assert len(detail["active_agreements"]) == 1


def test_agree_short_justification_rejected():
    # data/purge_tenant_now requires ≥120 chars; _LONG is 60. Short → reject.
    client = _client()
    resp = client.post(
        "/api/v1/god-mode/capabilities/data/purge_tenant_now/agree-to-register",
        json={"actor_id": "alice", "justification": _LONG},
    )
    assert resp.status_code == 400


def test_agree_unknown_capability_rejected():
    client = _client()
    resp = client.post(
        "/api/v1/god-mode/capabilities/ghost/missing/agree-to-register",
        json={"actor_id": "alice", "justification": _VERY_LONG},
    )
    assert resp.status_code == 400


def test_withdraw_agreement_reverts_state():
    client = _client()
    aid = _agree(client, "replay", "mutate_recorder")
    resp = client.post(
        f"/api/v1/god-mode/agreements/{aid}/withdraw",
        json={"actor_id": "auditor", "reason": "rotated"},
    )
    assert resp.status_code == 200
    assert resp.json()["state"] == "withdrawn"


def test_withdraw_unknown_agreement_400():
    client = _client()
    resp = client.post(
        "/api/v1/god-mode/agreements/god-reg-nope/withdraw",
        json={"actor_id": "auditor", "reason": "x"},
    )
    assert resp.status_code == 400


def test_suspend_and_resume_capability():
    client = _client()
    _agree(client, "replay", "mutate_recorder")
    susp = client.post(
        "/api/v1/god-mode/capabilities/replay/mutate_recorder/suspend",
        json={"actor_id": "auditor", "reason": "investigation"},
    )
    assert susp.status_code == 200
    assert susp.json()["state"] == "suspended"
    res = client.post(
        "/api/v1/god-mode/capabilities/replay/mutate_recorder/resume",
    )
    assert res.status_code == 200
    assert res.json()["state"] == "armed"


# --- Tickets ---


def test_issue_ticket_requires_armed():
    client = _client()
    resp = client.post(
        "/api/v1/god-mode/capabilities/replay/mutate_recorder/issue-ticket",
        json={
            "actor_id": "alice",
            "justification": _VERY_LONG,
            "target": {"tenant_id": "acme-7"},
        },
    )
    assert resp.status_code == 400


def test_issue_ticket_after_agree_succeeds():
    client = _client()
    _agree(client, "replay", "mutate_recorder")
    resp = client.post(
        "/api/v1/god-mode/capabilities/replay/mutate_recorder/issue-ticket",
        json={
            "actor_id": "alice",
            "justification": _VERY_LONG,
            "target": {"tenant_id": "acme-7"},
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ticket"]["state"] == "issued"
    assert body["ticket"]["actor_id"] == "alice"


def test_consume_ticket_emits_receipt():
    client = _client()
    _agree(client, "replay", "mutate_recorder")
    tid = _issue_ticket(client, "replay", "mutate_recorder")
    resp = client.post(
        f"/api/v1/god-mode/tickets/{tid}/consume",
        json={
            "outcome": "success",
            "pre_state": {"rows": 100},
            "post_state": {"rows": 0},
            "detail": {"reason": "gdpr"},
        },
    )
    assert resp.status_code == 200, resp.text
    receipt = resp.json()["receipt"]
    assert receipt["outcome"] == "success"
    assert receipt["pre_state_hash"].startswith("sha256:")


def test_consume_ticket_invalid_outcome_400():
    client = _client()
    _agree(client, "replay", "mutate_recorder")
    tid = _issue_ticket(client, "replay", "mutate_recorder")
    resp = client.post(
        f"/api/v1/god-mode/tickets/{tid}/consume",
        json={"outcome": "approved"},
    )
    assert resp.status_code == 400


def test_double_consume_rejected():
    client = _client()
    _agree(client, "replay", "mutate_recorder")
    tid = _issue_ticket(client, "replay", "mutate_recorder")
    first = client.post(
        f"/api/v1/god-mode/tickets/{tid}/consume",
        json={"outcome": "success"},
    )
    assert first.status_code == 200
    second = client.post(
        f"/api/v1/god-mode/tickets/{tid}/consume",
        json={"outcome": "success"},
    )
    assert second.status_code == 400


def test_revoke_ticket_blocks_consume():
    client = _client()
    _agree(client, "replay", "mutate_recorder")
    tid = _issue_ticket(client, "replay", "mutate_recorder")
    rev = client.post(
        f"/api/v1/god-mode/tickets/{tid}/revoke",
        json={"actor_id": "auditor", "reason": "false alarm"},
    )
    assert rev.status_code == 200
    assert rev.json()["ticket"]["state"] == "revoked"
    cons = client.post(
        f"/api/v1/god-mode/tickets/{tid}/consume",
        json={"outcome": "success"},
    )
    assert cons.status_code == 400


def test_get_ticket_404_for_unknown():
    client = _client()
    resp = client.get("/api/v1/god-mode/tickets/god-tkt-nope")
    assert resp.status_code == 404


def test_list_tickets_filters_by_actor():
    client = _client()
    _agree(client, "replay", "mutate_recorder")
    _issue_ticket(client, "replay", "mutate_recorder", actor="alice")
    _issue_ticket(client, "replay", "mutate_recorder", actor="bob")
    resp = client.get("/api/v1/god-mode/tickets", params={"actor_id": "alice"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    assert body["tickets"][0]["actor_id"] == "alice"


def test_list_receipts_after_consumption():
    client = _client()
    _agree(client, "replay", "mutate_recorder")
    tid = _issue_ticket(client, "replay", "mutate_recorder")
    client.post(
        f"/api/v1/god-mode/tickets/{tid}/consume",
        json={"outcome": "success"},
    )
    resp = client.get("/api/v1/god-mode/receipts")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    assert body["receipts"][0]["capability_module"] == "replay"


def test_list_receipts_filter_by_outcome():
    client = _client()
    _agree(client, "replay", "mutate_recorder")
    tid_ok = _issue_ticket(client, "replay", "mutate_recorder")
    client.post(
        f"/api/v1/god-mode/tickets/{tid_ok}/consume", json={"outcome": "success"}
    )
    tid_fail = _issue_ticket(client, "replay", "mutate_recorder")
    client.post(
        f"/api/v1/god-mode/tickets/{tid_fail}/consume",
        json={"outcome": "failure", "failure_reason": "boom"},
    )
    fails = client.get(
        "/api/v1/god-mode/receipts", params={"outcome": "failure"}
    ).json()
    assert fails["count"] == 1
    assert fails["receipts"][0]["failure_reason"] == "boom"


# --- End-to-end happy path ---


def test_end_to_end_consent_chain():
    client = _client()

    # 1. Browse the catalog — every capability dormant.
    listing = client.get("/api/v1/god-mode/capabilities").json()
    assert all(c["state"] == "dormant" for c in listing["capabilities"])

    # 2. Operator agrees to register one capability.
    aid = _agree(client, "rbac", "impersonate_user", actor="alice")
    detail = client.get("/api/v1/god-mode/capabilities/rbac/impersonate_user").json()
    assert detail["state"] == "armed"

    # 3. Operator issues a ticket and consumes it.
    tid = _issue_ticket(client, "rbac", "impersonate_user", actor="alice")
    consume = client.post(
        f"/api/v1/god-mode/tickets/{tid}/consume",
        json={
            "outcome": "success",
            "detail": {"impersonated_id": "user-42"},
        },
    )
    assert consume.status_code == 200

    # 4. Operator withdraws the registration; capability cannot issue more tickets.
    wd = client.post(
        f"/api/v1/god-mode/agreements/{aid}/withdraw",
        json={"actor_id": "alice", "reason": "incident closed"},
    )
    assert wd.status_code == 200
    refused = client.post(
        "/api/v1/god-mode/capabilities/rbac/impersonate_user/issue-ticket",
        json={"actor_id": "alice", "justification": _VERY_LONG},
    )
    assert refused.status_code == 400

    # 5. Receipt audit log preserved.
    receipts = client.get("/api/v1/god-mode/receipts").json()
    assert receipts["count"] == 1
    assert receipts["receipts"][0]["capability_name"] == "impersonate_user"
