"""Physical-action boundary tests.

Purpose: verify physical-world action requests are receipt-gated before worker
dispatch.
Governance scope: simulation, operator approval, manual override, emergency
stop, sensor confirmation, sandbox no-effect guarantees, and schema parity.
Dependencies: gateway.physical_action_boundary and physical_action_receipt schema.
Invariants:
  - Sandbox receipts preserve no-effect state.
  - Live effects require production certification.
  - Missing simulation fails closed.
"""

from __future__ import annotations

import json
from pathlib import Path

from gateway.physical_action_boundary import (
    PhysicalActionBoundary,
    PhysicalActionPolicy,
    PhysicalActionRequest,
)
from scripts.validate_schemas import _validate_schema_instance


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "physical_action_receipt.schema.json"


def test_physical_boundary_allows_sandbox_replay_with_full_controls() -> None:
    receipt = PhysicalActionBoundary().evaluate(_request())

    assert receipt.status == "allowed"
    assert receipt.reason == "physical_action_allowed"
    assert receipt.no_physical_effect_applied is True
    assert receipt.terminal_closure_required is True
    assert receipt.receipt_id.startswith("physical-action-receipt-")


def test_physical_boundary_blocks_without_simulation() -> None:
    receipt = PhysicalActionBoundary().evaluate(_request(simulation_passed=False))

    assert receipt.status == "blocked"
    assert receipt.reason == "simulation_pass_required"
    assert "simulation_pass_required" in receipt.blocked_reasons
    assert receipt.manual_override_required is True
    assert receipt.emergency_stop_required is True


def test_physical_boundary_blocks_live_effects_without_certification() -> None:
    receipt = PhysicalActionBoundary().evaluate(_request(effect_mode="live"))

    assert receipt.status == "blocked"
    assert "live_physical_effect_not_allowed" in receipt.blocked_reasons
    assert "production_certification_required" in receipt.blocked_reasons
    assert "production_certification" in receipt.required_controls


def test_physical_boundary_requires_operator_review_when_approval_missing() -> None:
    policy = PhysicalActionPolicy(
        policy_id="physical-action-policy:test",
        allowed_actions=("sandbox_replay",),
        sensor_confirmation_required=False,
    )
    receipt = PhysicalActionBoundary(policy).evaluate(_request(operator_approval_ref=""))

    assert receipt.status == "requires_review"
    assert receipt.reason == "operator_approval_ref_required"
    assert "operator_approval_ref_required" in receipt.review_reasons
    assert "operator_approval" in receipt.required_controls


def test_physical_action_receipt_matches_schema() -> None:
    receipt = PhysicalActionBoundary().evaluate(_request())
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    errors = _validate_schema_instance(schema, receipt.to_json_dict())

    assert errors == []
    assert schema["$id"] == "urn:mullusi:schema:physical-action-receipt:1"
    assert schema["properties"]["terminal_closure_required"]["const"] is True
    assert schema["properties"]["physical_worker_receipt_required"]["const"] is True


def _request(**overrides: object) -> PhysicalActionRequest:
    payload = {
        "request_id": "physical-action-test",
        "tenant_id": "tenant-physical",
        "command_id": "cmd-physical",
        "actuator_id": "actuator:sandbox-1",
        "action": "sandbox_replay",
        "effect_mode": "sandbox",
        "safety_envelope_ref": "safety-envelope:test",
        "environment_ref": "environment:sandbox",
        "risk_level": "high",
        "simulation_passed": True,
        "operator_approval_ref": "approval:test",
        "manual_override_ref": "manual-override:test",
        "emergency_stop_ref": "emergency-stop:test",
        "sensor_confirmation_ref": "sensor:test",
        "evidence_refs": (
            "proof://physical/simulation",
            "proof://physical/manual-override",
            "proof://physical/emergency-stop",
        ),
    }
    payload.update(overrides)
    return PhysicalActionRequest(**payload)
