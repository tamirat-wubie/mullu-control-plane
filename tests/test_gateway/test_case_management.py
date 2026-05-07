"""Gateway operational case management tests.

Purpose: verify authority mesh records project into operator case read models.
Governance scope: approval cases, obligation cases, incident cases, schema
    compatibility, source evidence, and read-model-only safety metadata.
Dependencies: gateway.case_management and schemas/operational_case.schema.json.
Invariants:
  - Pending approval chains become awaiting-approval cases.
  - Unresolved obligations retain owners, deadlines, and closure conditions.
  - Escalation events become incident cases with stable source evidence.
  - Case projections never grant execution authority.
"""

from __future__ import annotations

from pathlib import Path

from gateway.authority_obligation_mesh import (
    ApprovalChain,
    ApprovalChainStatus,
    Obligation,
    ObligationStatus,
)
from gateway.case_management import OperationalCase, build_operational_case_read_model
from gateway.server import create_gateway_app
from scripts.validate_schemas import _load_schema, _validate_schema_instance
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "operational_case.schema.json"


def test_operational_case_read_model_projects_authority_records() -> None:
    read_model = build_operational_case_read_model(
        approval_chains=(_approval_chain(),),
        obligations=(_obligation(),),
        escalation_events=(_escalation_event(),),
    )
    cases = {case["case_type"]: case for case in read_model["cases"]}

    approval_case = cases["approval_case"]
    review_case = cases["requires_review_closure_case"]
    incident_case = cases["incident_case"]

    assert read_model["case_count"] == 3
    assert read_model["open_case_count"] == 3
    assert read_model["case_counts_by_type"]["approval_case"] == 1
    assert read_model["case_counts_by_status"]["awaiting_approval"] == 1
    assert approval_case["status"] == "awaiting_approval"
    assert approval_case["owner"] == "finance_manager"
    assert approval_case["closure_condition"] == "required approval count satisfied"
    assert "authority:approval_chain:chain-1" in approval_case["evidence_refs"]
    assert review_case["owner"] == "finance-admin"
    assert review_case["obligations"] == ["obl-1"]
    assert review_case["metadata"]["does_not_grant_execution_authority"] is True
    assert incident_case["status"] == "escalated"
    assert incident_case["severity"] == "critical"
    assert incident_case["source_refs"][0].startswith("authority:escalation_event:")


def test_operational_case_schema_accepts_case_projection() -> None:
    payload = build_operational_case_read_model(
        approval_chains=(_satisfied_approval_chain(),),
        obligations=(),
        escalation_events=(),
    )["cases"][0]
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), payload)

    assert errors == []
    assert payload["status"] == "closed"
    assert payload["decision_history"][0]["actor"] == "finance_manager"
    assert payload["metadata"]["read_model_only"] is True


def test_operational_case_rejects_undefined_case_symbols() -> None:
    try:
        OperationalCase(
            case_id="case-1",
            case_type="undefined_case",
            tenant_id="tenant-a",
            severity="high",
            status="open",
            owner="owner-1",
            approver="",
            requested_by="requester-1",
            action="review",
            deadline="2026-05-05T18:00:00+00:00",
            evidence_refs=("proof://case",),
            decision_history=(),
            obligations=(),
            escalation_path=(),
            closure_condition="review complete",
            source_refs=("source://case",),
        )
    except ValueError as exc:
        error = str(exc)
    else:
        error = ""

    assert error == "case_type_invalid"
    assert error
    assert "invalid" in error


def test_operational_case_endpoint_exposes_filtered_operator_read_model() -> None:
    app = create_gateway_app(platform=None)
    app.state.authority_mesh_store.save_approval_chain(_approval_chain())
    app.state.authority_mesh_store.save_obligation(_obligation())
    client = TestClient(app)

    response = client.get("/cases/read-model?tenant_id=tenant-a&case_type=approval_case")
    payload = response.json()

    assert response.status_code == 200
    assert payload["case_count"] == 1
    assert payload["total_case_count"] == 1
    assert payload["cases"][0]["case_type"] == "approval_case"
    assert payload["cases"][0]["status"] == "awaiting_approval"
    assert "authority:approval_chains_read_model" in payload["evidence_refs"]


def _approval_chain() -> ApprovalChain:
    return ApprovalChain(
        chain_id="chain-1",
        command_id="cmd-1",
        tenant_id="tenant-a",
        policy_id="policy-finance-high",
        required_roles=("finance_manager",),
        required_approver_count=1,
        approvals_received=(),
        status=ApprovalChainStatus.PENDING,
        due_at="2026-05-05T18:00:00+00:00",
    )


def _satisfied_approval_chain() -> ApprovalChain:
    return ApprovalChain(
        chain_id="chain-2",
        command_id="cmd-2",
        tenant_id="tenant-a",
        policy_id="policy-finance-high",
        required_roles=("finance_manager",),
        required_approver_count=1,
        approvals_received=("finance_manager",),
        status=ApprovalChainStatus.SATISFIED,
        due_at="2026-05-05T18:00:00+00:00",
    )


def _obligation() -> Obligation:
    return Obligation(
        obligation_id="obl-1",
        command_id="cmd-1",
        tenant_id="tenant-a",
        owner_id="finance-admin",
        owner_team="finance-ops",
        obligation_type="requires_review_closure",
        due_at="2026-05-05T19:00:00+00:00",
        status=ObligationStatus.OPEN,
        evidence_required=("proof://terminal-certificate",),
        escalation_policy_id="esc-finance",
        terminal_certificate_id="terminal-1",
    )


def _escalation_event() -> dict[str, str]:
    return {
        "tenant_id": "tenant-a",
        "command_id": "cmd-1",
        "obligation_id": "obl-1",
        "owner_id": "finance-admin",
        "escalation_policy_id": "esc-finance",
        "severity": "critical",
        "reason": "obligation_overdue",
        "due_at": "2026-05-05T20:00:00+00:00",
    }
