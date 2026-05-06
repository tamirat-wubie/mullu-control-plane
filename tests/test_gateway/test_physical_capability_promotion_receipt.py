"""Tests for physical capability promotion receipts.

Purpose: prove physical promotion receipts bind Forge requirements, handoff
    refs, registry extension state, and physical preflight output without
    claiming admission authority or terminal closure.
Governance scope: physical capability promotion evidence, handoff provenance,
    registry extension witness, schema contract, and mismatch rejection.
Dependencies: gateway.physical_capability_promotion_receipt, capability forge,
    physical promotion preflight, governed capability fabric fixtures, and
    schemas/physical_capability_promotion_receipt.schema.json.
Invariants:
  - Receipts bind a ready preflight to Forge and registry evidence.
  - Receipts validate against the public schema.
  - Mismatched capability chains are rejected.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from gateway.capability_forge import (
    CapabilityForge,
    CapabilityForgeInput,
    install_certification_handoff_evidence,
)
from gateway.physical_capability_promotion_receipt import (
    PhysicalCapabilityPromotionReceipt,
    build_physical_capability_promotion_receipt,
)
from gateway.server import create_gateway_app
from mcoi_runtime.contracts.governed_capability_fabric import CapabilityRegistryEntry, DomainCapsule
from scripts.preflight_physical_capability_promotion import preflight_physical_capability_records
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parents[2]
REGISTRY_FIXTURE_PATH = ROOT / "integration" / "governed_capability_fabric" / "fixtures" / "capability_registry_entry.json"
PHYSICAL_CAPSULE_PATH = ROOT / "capsules" / "physical.json"
SCHEMA_PATH = ROOT / "schemas" / "physical_capability_promotion_receipt.schema.json"


class StubPlatform:
    """Minimal platform fixture for gateway app construction."""

    def process_message(self, message, tenant_id: str, identity_id: str):  # noqa: ANN001
        return {
            "response": "ok",
            "tenant_id": tenant_id,
            "identity_id": identity_id,
        }


def test_physical_capability_promotion_receipt_binds_ready_chain() -> None:
    candidate, handoff, installed_entry, preflight_report = _ready_physical_promotion_chain()

    receipt = build_physical_capability_promotion_receipt(
        candidate=candidate,
        handoff=handoff,
        installed_entry=installed_entry,
        preflight_report=preflight_report,
        recorded_at="2026-05-06T12:00:00+00:00",
    )
    payload = receipt.to_json_dict()

    assert isinstance(receipt, PhysicalCapabilityPromotionReceipt)
    assert receipt.promotion_status == "ready"
    assert receipt.preflight_ready is True
    assert receipt.preflight_readiness_level == "physical-production-ready"
    assert receipt.receipt_is_not_admission_authority is True
    assert receipt.receipt_is_not_terminal_closure is True
    assert "emergency_stop_ref" in receipt.forge_requirement_keys
    assert "sensor_confirmation_ref" in receipt.handoff_physical_safety_ref_keys
    assert "physical_action_receipt_schema_ref" in receipt.registry_physical_safety_evidence_keys
    assert receipt.registry_physical_safety_evidence_hash
    assert receipt.receipt_hash
    assert _validate_schema_instance(_load_schema(SCHEMA_PATH), payload) == []


def test_physical_capability_promotion_receipt_rejects_mismatched_handoff() -> None:
    candidate, handoff, installed_entry, preflight_report = _ready_physical_promotion_chain()
    mismatched_handoff = replace(handoff, capability_id="physical.lock_door")

    with pytest.raises(ValueError, match="^candidate_handoff_capability_mismatch$"):
        build_physical_capability_promotion_receipt(
            candidate=candidate,
            handoff=mismatched_handoff,
            installed_entry=installed_entry,
            preflight_report=preflight_report,
            recorded_at="2026-05-06T12:00:00+00:00",
        )

    assert candidate.capability_id == "physical.unlock_door"
    assert installed_entry.capability_id == candidate.capability_id
    assert preflight_report.ready is True


def test_operator_physical_promotion_receipt_endpoint_emits_ready_bundle() -> None:
    client = TestClient(create_gateway_app(platform=StubPlatform()))

    response = client.post(
        "/operator/physical-capability-promotion-receipts",
        json={
            "use_fixture_refs": True,
            "recorded_at": "2026-05-06T12:00:00+00:00",
        },
    )
    payload = response.json()
    ledger_response = client.get("/operator/physical-capability-promotion-receipts")
    ledger_payload = ledger_response.json()

    assert response.status_code == 200
    assert payload["ready"] is True
    assert payload["errors"] == []
    assert payload["receipt_id"] == payload["receipt"]["receipt_id"]
    assert payload["receipt"]["promotion_status"] == "ready"
    assert payload["receipt"]["receipt_is_not_admission_authority"] is True
    assert ledger_response.status_code == 200
    assert ledger_payload["count"] == 1
    assert ledger_payload["physical_capability_promotion_receipts"][0]["receipt_id"] == payload["receipt_id"]


def test_operator_physical_promotion_receipt_endpoint_blocks_missing_live_refs() -> None:
    client = TestClient(create_gateway_app(platform=StubPlatform()))

    response = client.post("/operator/physical-capability-promotion-receipts", json={})
    payload = response.json()["detail"]
    ledger_response = client.get("/operator/physical-capability-promotion-receipts")
    ledger_payload = ledger_response.json()

    assert response.status_code == 409
    assert payload["ready"] is False
    assert payload["capability_id"] == "physical.unlock_door"
    assert "live_read_receipt_ref_required" in payload["errors"]
    assert ledger_response.status_code == 200
    assert ledger_payload["count"] == 0
    assert ledger_payload["total"] == 0


def test_operator_physical_promotion_receipt_endpoint_rejects_invalid_payload_shape() -> None:
    client = TestClient(create_gateway_app(platform=StubPlatform()))

    response = client.post(
        "/operator/physical-capability-promotion-receipts",
        json={"physical_live_safety_evidence_refs": []},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "physical_promotion_receipt_physical_safety_refs_must_be_object"
    assert client.get("/operator/physical-capability-promotion-receipts").json()["count"] == 0


def _ready_physical_promotion_chain():
    candidate = CapabilityForge().create_candidate(_physical_forge_input())
    handoff = CapabilityForge().build_certification_handoff(
        candidate,
        live_read_receipt_ref="proof://physical.unlock_door/live-read",
        live_write_receipt_ref="proof://physical.unlock_door/live-write",
        worker_deployment_ref="proof://physical.unlock_door/worker",
        recovery_evidence_ref="proof://physical.unlock_door/recovery",
        physical_live_safety_evidence_refs=_physical_live_safety_evidence_refs(),
    )
    installed_entry = install_certification_handoff_evidence(
        _registry_entry_for_candidate(candidate),
        handoff,
        require_production_ready=True,
    )
    capsule = replace(
        DomainCapsule.from_mapping(_load_json(PHYSICAL_CAPSULE_PATH)),
        capability_refs=(candidate.capability_id,),
    )
    preflight_report = preflight_physical_capability_records(
        capsule=capsule,
        registry_entries=(installed_entry,),
    )
    return candidate, handoff, installed_entry, preflight_report


def _physical_forge_input() -> CapabilityForgeInput:
    return CapabilityForgeInput(
        capability_id="physical.unlock_door",
        version="0.1.0",
        domain="physical",
        risk="high",
        side_effects=("physical_actuator_command",),
        api_docs_ref="docs/providers/physical-control.md",
        input_schema_ref="schemas/physical/unlock_door.input.schema.json",
        output_schema_ref="urn:mullusi:schema:physical-action-receipt:1",
        owner_team="physical-safety",
        network_allowlist=("physical-control.internal",),
        secret_scope="physical_live_control",
        requires_approval=True,
    )


def _registry_entry_for_candidate(candidate) -> CapabilityRegistryEntry:
    payload = _load_json(REGISTRY_FIXTURE_PATH)
    payload["capability_id"] = candidate.capability_id
    payload["domain"] = candidate.domain
    payload["version"] = candidate.version
    payload["input_schema_ref"] = candidate.schemas.input_schema_ref
    payload["output_schema_ref"] = candidate.schemas.output_schema_ref
    payload["certification_status"] = "certified"
    return CapabilityRegistryEntry.from_mapping(payload)


def _physical_live_safety_evidence_refs() -> dict[str, str]:
    return {
        "physical_action_receipt_ref": "proof://physical.unlock_door/action-receipt",
        "simulation_ref": "proof://physical.unlock_door/simulation",
        "operator_approval_ref": "proof://physical.unlock_door/operator-approval",
        "manual_override_ref": "proof://physical.unlock_door/manual-override",
        "emergency_stop_ref": "proof://physical.unlock_door/emergency-stop",
        "sensor_confirmation_ref": "proof://physical.unlock_door/sensor-confirmation",
        "deployment_witness_ref": "proof://physical.unlock_door/deployment-witness",
    }


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
