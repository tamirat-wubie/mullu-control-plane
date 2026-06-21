"""Purpose: read-only Governed Work Assistant dashboard projection route.

Governance scope: operator dashboard read model projection only.
Dependencies: FastAPI and the checked-in dashboard fixture.
Invariants:
  - The route is read-only and fixture-backed.
  - No connector, mailbox, calendar, repository, worker, or receipt effect is executed.
  - Every effect boundary flag remains false.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

router = APIRouter()

_REPO_ROOT = Path(__file__).resolve().parents[4]
_DASHBOARD_FIXTURE = _REPO_ROOT / "examples" / "governed_work_assistant_operator_dashboard.json"
_FALSE_EFFECT_FIELDS = frozenset(
    {
        "live_connector_execution_allowed",
        "mailbox_read_allowed",
        "mailbox_mutation_allowed",
        "external_send_allowed",
        "calendar_write_allowed",
        "repository_write_allowed",
        "worker_dispatch_allowed",
        "live_receipt_append_allowed",
        "production_readiness_claim_allowed",
        "customer_readiness_claim_allowed",
        "autonomous_execution_authority_allowed",
    }
)


def _load_dashboard_fixture() -> dict[str, Any]:
    try:
        payload = json.loads(_DASHBOARD_FIXTURE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        raise HTTPException(
            500,
            detail={
                "error": "work assistant dashboard fixture unavailable",
                "error_code": "work_assistant_dashboard_fixture_unavailable",
                "governed": True,
                "execution_allowed": False,
                "live_connector_execution_allowed": False,
            },
        ) from exc
    if not isinstance(payload, dict):
        raise HTTPException(
            500,
            detail={
                "error": "work assistant dashboard fixture invalid",
                "error_code": "work_assistant_dashboard_fixture_invalid",
                "governed": True,
                "execution_allowed": False,
                "live_connector_execution_allowed": False,
            },
        )
    _require_no_effect(payload)
    return payload


def _require_no_effect(payload: dict[str, Any]) -> None:
    if payload.get("read_only") is not True or payload.get("fixture_backed") is not True:
        raise HTTPException(
            500,
            detail={
                "error": "work assistant dashboard fixture violates read-only boundary",
                "error_code": "work_assistant_dashboard_not_read_only",
                "governed": True,
                "execution_allowed": False,
                "live_connector_execution_allowed": False,
            },
        )
    effect_boundary = payload.get("effect_boundary")
    if not isinstance(effect_boundary, dict):
        raise HTTPException(
            500,
            detail={
                "error": "work assistant dashboard effect boundary missing",
                "error_code": "work_assistant_dashboard_effect_boundary_missing",
                "governed": True,
                "execution_allowed": False,
                "live_connector_execution_allowed": False,
            },
        )
    drifted = sorted(field for field in _FALSE_EFFECT_FIELDS if effect_boundary.get(field) is not False)
    if drifted:
        raise HTTPException(
            500,
            detail={
                "error": "work assistant dashboard effect boundary drift",
                "error_code": "work_assistant_dashboard_effect_boundary_drift",
                "governed": True,
                "execution_allowed": False,
                "live_connector_execution_allowed": False,
                "drifted_fields": drifted,
            },
        )


@router.get("/api/v1/personal-assistant/work-assistant/dashboard/read-model")
def governed_work_assistant_operator_dashboard_read_model() -> dict[str, Any]:
    """Return the no-effect Governed Work Assistant operator dashboard projection."""
    dashboard = dict(_load_dashboard_fixture())
    dashboard["route_boundary"] = {
        "route_id": "governed_work_assistant_operator_dashboard_read_model",
        "method": "GET",
        "read_only": True,
        "fixture_backed": True,
        "execution_allowed": False,
        "live_connector_execution_allowed": False,
        "external_send_allowed": False,
        "repository_write_allowed": False,
        "worker_dispatch_allowed": False,
        "live_receipt_append_allowed": False,
    }
    return dashboard
