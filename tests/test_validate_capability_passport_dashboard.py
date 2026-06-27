"""Tests for capability passport dashboard validation.

Purpose: prove the operator dashboard projects passports into simple status
lanes without granting authority or exposing gate/schema internals.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_capability_passport_dashboard, capability
passports, and gate template registry fixtures.
Invariants: every passport appears once, dashboard state is read-only, and
operator cards expose statuses rather than raw governance internals.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcoi_runtime.app.capability_passport_dashboard import (
    CapabilityPassportDashboardError,
    STATUS_ORDER,
    build_capability_passport_dashboard,
)
from scripts.validate_capability_passport_dashboard import (
    DEFAULT_DASHBOARD,
    DEFAULT_OUTPUT,
    validate_capability_passport_dashboard,
    write_capability_passport_dashboard_validation,
)


def _default_payload() -> dict[str, object]:
    return json.loads(DEFAULT_DASHBOARD.read_text(encoding="utf-8"))


def _write_payload(tmp_path: Path, payload: dict[str, object]) -> Path:
    dashboard_path = tmp_path / "capability_passport_dashboard.json"
    dashboard_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return dashboard_path


def _operator_view(payload: dict[str, object]) -> dict[str, object]:
    operator_view = payload["operator_view"]
    assert isinstance(operator_view, dict)
    return operator_view


def _status_lanes(payload: dict[str, object]) -> list[dict[str, object]]:
    lanes = _operator_view(payload)["status_lanes"]
    assert isinstance(lanes, list)
    return lanes


def _first_card(payload: dict[str, object]) -> dict[str, object]:
    for lane in _status_lanes(payload):
        cards = lane["capabilities"]
        assert isinstance(cards, list)
        if cards:
            card = cards[0]
            assert isinstance(card, dict)
            return card
    raise AssertionError("expected at least one dashboard card")


def test_capability_passport_dashboard_validates_and_writes(tmp_path: Path) -> None:
    validation = validate_capability_passport_dashboard()
    output_path = tmp_path / "capability-passport-dashboard-validation.json"

    written_path = write_capability_passport_dashboard_validation(validation, output_path)
    written_payload = json.loads(written_path.read_text(encoding="utf-8"))

    assert validation.ok is True
    assert validation.capability_count > 20
    assert validation.family_count > 5
    assert validation.unresolved_gate_count == 0
    assert written_payload["errors"] == []
    assert DEFAULT_OUTPUT.name == "capability_passport_dashboard_validation.json"


def test_capability_passport_dashboard_projects_simple_status_lanes() -> None:
    dashboard = build_capability_passport_dashboard()
    lanes = dashboard["operator_view"]["status_lanes"]
    tiles = dashboard["operator_view"]["status_tiles"]
    lane_labels = tuple(lane["label"] for lane in lanes)
    tile_labels = tuple(tile["label"] for tile in tiles)
    lane_total = sum(lane["count"] for lane in lanes)

    assert lane_labels == STATUS_ORDER
    assert tile_labels == STATUS_ORDER
    assert lane_total == dashboard["summary"]["capability_count"]
    assert dashboard["summary"]["status_counts"]["Live action disabled"] > 0
    assert dashboard["summary"]["attention_required_count"] >= dashboard["summary"]["status_counts"]["Needs approval"]


def test_capability_passport_dashboard_operator_cards_hide_internal_fields() -> None:
    dashboard = build_capability_passport_dashboard()
    card = _first_card(dashboard)

    assert "required_gates" not in card
    assert "source_ref" not in card
    assert "input_schema_ref" not in card
    assert "output_schema_ref" not in card
    assert "blocked_action_count" in card
    assert "required_receipt_count" in card
    assert dashboard["governance_health"]["operator_view_hides_internal_gate_ids"] is True
    assert dashboard["governance_health"]["operator_view_hides_schema_refs"] is True


def test_capability_passport_dashboard_rejects_authority_overclaim(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["dashboard_is_not_execution_authority"] = False
    payload["live_execution_enabled"] = True

    validation = validate_capability_passport_dashboard(dashboard_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "dashboard_is_not_execution_authority must be true" in serialized_errors
    assert "live_execution_enabled must be false" in serialized_errors
    assert "example does not match runtime projection" in serialized_errors


def test_capability_passport_dashboard_rejects_missing_lane_card(tmp_path: Path) -> None:
    payload = _default_payload()
    lanes = _status_lanes(payload)
    for lane in lanes:
        cards = lane["capabilities"]
        assert isinstance(cards, list)
        if cards:
            cards.pop()
            lane["count"] = len(cards)
            break

    validation = validate_capability_passport_dashboard(dashboard_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "status_lanes must contain every passport exactly once" in serialized_errors
    assert "example does not match runtime projection" in serialized_errors


def test_capability_passport_dashboard_rejects_internal_field_exposure(tmp_path: Path) -> None:
    payload = _default_payload()
    card = _first_card(payload)
    card["required_gates"] = ["gate.uao.admission"]

    validation = validate_capability_passport_dashboard(dashboard_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "operator card exposes internal fields ['required_gates']" in serialized_errors
    assert "example does not match runtime projection" in serialized_errors


def test_capability_passport_dashboard_rejects_unknown_status() -> None:
    passport_set = {
        "passports": [
            {
                "capability_id": "demo.read",
                "capability_name": "Demo Read",
                "family": "demo",
                "operator_status": "Investigating",
                "current_unlock_level": "C1",
                "allowed_actions": ["read"],
                "blocked_actions": ["demo_write"],
                "required_receipts": ["terminal_closure_certificate"],
                "required_gates": ["gate.uao.admission"],
                "rollback_status": {"status": "not_required"},
                "next_unlock_step": "add evidence",
            }
        ]
    }
    gate_registry = {
        "templates": [
            {
                "gate_id": "gate.uao.admission",
            }
        ]
    }

    with pytest.raises(CapabilityPassportDashboardError, match="unsupported operator_status"):
        build_capability_passport_dashboard(passports=passport_set, gate_registry=gate_registry)
