"""Purpose: verify the read-only SDLC dashboard summary.

Governance scope: SDLC change, stage, blocker, evidence, receipt, and closure
read-model projection.
Dependencies: FastAPI test client, software receipt router, SDLC dashboard core.
Invariants:
  - The dashboard is read-only.
  - Stage summaries preserve UAO, causal trace, and receipt refs.
  - Blockers are explicit records.
  - HTTP access requires the MUSIA read dependency path.
"""

from __future__ import annotations

from copy import deepcopy

from fastapi import FastAPI
from fastapi.testclient import TestClient

from mcoi_runtime.app.routers.musia_auth import (
    configure_musia_auth,
    configure_musia_dev_mode,
    configure_musia_jwt,
)
from mcoi_runtime.app.routers.software_receipts import router
from mcoi_runtime.core.sdlc_dashboard import (
    build_sdlc_dashboard_summary,
    load_sdlc_dashboard_records,
)


def _client() -> TestClient:
    configure_musia_auth(None)
    configure_musia_jwt(None)
    configure_musia_dev_mode(True)
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_sdlc_dashboard_summary_preserves_change_to_closure_chain() -> None:
    summary = build_sdlc_dashboard_summary()
    non_closure_stages = [
        stage for stage in summary["stages"] if stage["stage_key"] != "closure_receipt"
    ]

    assert summary["read_model_version"] == "sdlc_dashboard.v1"
    assert summary["read_only"] is True
    assert summary["change"]["request_id"] == "sdlc_req_uao_validator_001"
    assert summary["stage_count"] == 11
    assert summary["stages"][0]["stage_key"] == "change_request"
    assert summary["stages"][-1]["stage_key"] == "closure_receipt"
    assert summary["closure"]["terminal_state"] == "closed_success"
    assert summary["closure"]["outcome"] == "SolvedVerified"
    assert summary["blocker_count"] == 0
    assert all(stage["receipt_ref"] for stage in non_closure_stages)
    assert all(stage["uao_ref"] for stage in non_closure_stages)
    assert all(stage["causal_decision_trace_ref"] for stage in non_closure_stages)


def test_sdlc_dashboard_projects_security_blockers_explicitly() -> None:
    records = deepcopy(load_sdlc_dashboard_records())
    records["security_review"]["release_blocked"] = True
    records["security_review"]["required_checks"][0]["status"] = "failed"
    records["security_review"]["findings"] = [
        {
            "finding_id": "finding-open-high",
            "severity": "high",
            "status": "open",
            "description": "open release blocker",
        }
    ]

    summary = build_sdlc_dashboard_summary(records)
    security_stage = next(
        stage for stage in summary["stages"] if stage["stage_key"] == "security_review"
    )

    assert security_stage["status"] == "blocked"
    assert security_stage["blocker_count"] == 3
    assert summary["blocker_count"] == 3
    assert {blocker["blocker_id"] for blocker in security_stage["blockers"]} == {
        "policy bypass test",
        "finding-open-high",
        "release_blocked",
    }
    assert all(blocker["stage_key"] == "security_review" for blocker in security_stage["blockers"])


def test_sdlc_dashboard_route_returns_read_only_summary() -> None:
    client = _client()

    response = client.get(
        "/software/receipts/sdlc/dashboard",
        headers={"X-Tenant-ID": "tenant-dashboard"},
    )
    body = response.json()

    assert response.status_code == 200
    assert body["operation"] == "sdlc_dashboard"
    assert body["tenant_id"] == "tenant-dashboard"
    assert body["governed"] is True
    assert body["stage_count"] == body["dashboard"]["stage_count"]
    assert body["blocker_count"] == body["dashboard"]["blocker_count"]
    assert body["dashboard"]["read_only"] is True
    assert body["dashboard"]["change"]["request_id"] == "sdlc_req_uao_validator_001"
    assert body["dashboard"]["stages"][0]["stage_key"] == "change_request"
