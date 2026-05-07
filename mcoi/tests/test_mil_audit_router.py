"""Purpose: verify HTTP admission of MIL audit replay bundles into runbooks.
Governance scope: MIL audit replay persistence, runbook learning admission, and bounded HTTP errors.
Dependencies: FastAPI, MIL audit router, MIL static verifier, and MIL audit store.
Invariants:
  - Replay-backed runbook admission returns governed provenance.
  - Missing audit stores fail closed without leaking local paths.
  - Persisted replay output is written before runbook admission.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from mcoi_runtime.app.routers.mil_audit import router
from mcoi_runtime.contracts.mil import MILInstruction, MILOpcode, MILProgram
from mcoi_runtime.contracts.policy import DecisionReason, PolicyDecision, PolicyDecisionStatus
from mcoi_runtime.core.mil_static_verifier import verify_mil_program
from mcoi_runtime.persistence.mil_audit_store import MILAuditStore


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _record_id(tmp_path) -> tuple[str, str]:
    decision = PolicyDecision(
        "policy:allow:goal-router",
        "operator",
        "goal-router",
        PolicyDecisionStatus.ALLOW,
        (DecisionReason("allowed", "allow"),),
        "2026-05-06T12:00:00Z",
    )
    program = MILProgram(
        "mil:goal-router:shell_command",
        "goal-router",
        decision,
        (
            MILInstruction("check", MILOpcode.CHECK_POLICY, "goal-router"),
            MILInstruction("call", MILOpcode.CALL_CAPABILITY, "shell_command", depends_on=("check",)),
            MILInstruction("verify", MILOpcode.VERIFY_EFFECT, "shell_command", depends_on=("call",)),
            MILInstruction("proof", MILOpcode.EMIT_PROOF, "goal-router", depends_on=("verify",)),
        ),
        "2026-05-06T12:00:01Z",
    )
    store_path = tmp_path / "mil-audit"
    result = MILAuditStore(store_path).append(
        program=program,
        verification=verify_mil_program(program),
        execution_id="exec-router",
        instruction_trace=("proof:emit_proof:goal-router",),
        recorded_at="2026-05-06T12:00:02Z",
    )
    return str(store_path), result.record.record_id


def test_mil_audit_router_admits_replay_backed_runbook(tmp_path) -> None:
    store_path, record_id = _record_id(tmp_path)
    trace_store = tmp_path / "traces"
    replay_store = tmp_path / "replays"
    runbook_store = tmp_path / "runbooks"

    response = _client().post(
        "/api/v1/mil-audit/admit-runbook",
        json={
            "record_id": record_id,
            "mil_audit_store_path": store_path,
            "trace_store_path": str(trace_store),
            "replay_store_path": str(replay_store),
            "runbook_store_path": str(runbook_store),
            "runbook_id": "runbook-router-1",
            "name": "Router MIL Runbook",
            "description": "Runbook admitted from a persisted MIL audit replay.",
        },
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["operation"] == "admit-runbook"
    assert payload["runbook_status"] == "admitted"
    assert payload["runbook_persisted"] is True
    assert payload["runbook_id"] == "runbook-router-1"
    assert payload["provenance"]["replay_id"] == payload["replay_id"]
    assert len(payload["trace_ids"]) == 6
    assert (replay_store / f"{payload['replay_id']}.json").exists()
    assert (runbook_store / "runbook-router-1.json").exists()


def test_mil_audit_router_gets_and_lists_persisted_runbooks(tmp_path) -> None:
    store_path, record_id = _record_id(tmp_path)
    trace_store = tmp_path / "traces"
    replay_store = tmp_path / "replays"
    runbook_store = tmp_path / "runbooks"
    client = _client()
    admission = client.post(
        "/api/v1/mil-audit/admit-runbook",
        json={
            "record_id": record_id,
            "mil_audit_store_path": store_path,
            "trace_store_path": str(trace_store),
            "replay_store_path": str(replay_store),
            "runbook_store_path": str(runbook_store),
            "runbook_id": "runbook-router-1",
            "name": "Router MIL Runbook",
            "description": "Runbook admitted from a persisted MIL audit replay.",
        },
    )
    assert admission.status_code == 200

    get_response = client.get(
        "/api/v1/mil-audit/runbooks/runbook-router-1",
        params={"runbook_store_path": str(runbook_store)},
    )
    list_response = client.get(
        "/api/v1/mil-audit/runbooks",
        params={"runbook_store_path": str(runbook_store)},
    )
    get_payload = get_response.json()
    list_payload = list_response.json()

    assert get_response.status_code == 200
    assert get_payload["operation"] == "runbook-get"
    assert get_payload["found"] is True
    assert get_payload["runbooks"][0]["runbook_id"] == "runbook-router-1"
    assert get_payload["runbooks"][0]["provenance"]["verification_id"] == record_id
    assert list_response.status_code == 200
    assert list_payload["operation"] == "runbook-list"
    assert list_payload["count"] == 1
    assert list_payload["runbooks"][0]["provenance"]["replay_id"] == get_payload["runbooks"][0]["provenance"]["replay_id"]


def test_mil_audit_router_missing_store_fails_closed(tmp_path) -> None:
    response = _client().post(
        "/api/v1/mil-audit/admit-runbook",
        json={
            "record_id": "record-missing",
            "mil_audit_store_path": str(tmp_path / "missing"),
            "trace_store_path": str(tmp_path / "traces"),
            "replay_store_path": str(tmp_path / "replays"),
            "runbook_id": "runbook-router-1",
            "name": "Router MIL Runbook",
            "description": "Runbook admitted from a persisted MIL audit replay.",
        },
    )
    payload = response.json()

    assert response.status_code == 404
    assert payload["detail"]["error"] == "MIL audit store unavailable"
    assert payload["detail"]["type"] == "FileNotFoundError"
    assert payload["detail"]["governed"] is True


def test_mil_audit_router_missing_runbook_fails_closed(tmp_path) -> None:
    response = _client().get(
        "/api/v1/mil-audit/runbooks/missing-runbook",
        params={"runbook_store_path": str(tmp_path / "runbooks")},
    )
    payload = response.json()

    assert response.status_code == 404
    assert payload["detail"]["error"] == "MIL audit runbook unavailable"
    assert payload["detail"]["type"] == "PersistenceError"
    assert payload["detail"]["governed"] is True
