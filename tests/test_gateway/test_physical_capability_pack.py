"""Tests for the fixture-only physical capability pack.

Purpose: verify checked-in physical capability fixtures remain sandbox-only
    unless live physical safety evidence is explicitly certified.
Governance scope: physical-action boundary fixtures, capability fabric
    admission, production-ready gating, and production evidence projection.
Dependencies: gateway capability fabric loader and gateway production evidence
    endpoint.
Invariants:
  - Physical fixture capabilities are not part of default pack loading.
  - Sandbox replay can be admitted only when production readiness is not
    required.
  - Live physical action is rejected by production-ready admission by default.
  - Gateway evidence projection does not create a live physical production
    claim for the fixture pack.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from gateway.capability_fabric import (
    build_capability_admission_gate,
    load_default_capability_entries,
    load_default_domain_capsules,
)
from gateway.server import create_gateway_app
from mcoi_runtime.contracts.governed_capability_fabric import CapabilityRegistryEntry, DomainCapsule
from scripts.collect_deployment_witness import _evaluate_physical_capability_policy
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent.parent
PHYSICAL_CAPSULE_PATH = ROOT / "capsules" / "physical.json"
PHYSICAL_CAPABILITY_PACK_PATH = ROOT / "capabilities" / "physical" / "capability_pack.json"
CAPABILITY_EVIDENCE_SCHEMA = ROOT / "schemas" / "capability_evidence_endpoint.schema.json"


class StubPlatform:
    """Minimal governed platform fixture for gateway app construction."""

    def connect(self, *, identity_id: str, tenant_id: str):
        return StubSession()


class StubSession:
    """Minimal governed session fixture."""

    def llm(self, prompt: str, **kwargs):
        return type("Result", (), {"content": "ok", "succeeded": True, "error": "", "cost": 0.0})()

    def close(self) -> None:
        return None


def test_physical_fixture_pack_is_not_loaded_by_default() -> None:
    default_capsules = load_default_domain_capsules()
    default_capabilities = load_default_capability_entries()

    assert all(capsule.domain != "physical" for capsule in default_capsules)
    assert all(entry.domain != "physical" for entry in default_capabilities)
    assert PHYSICAL_CAPSULE_PATH.exists()
    assert PHYSICAL_CAPABILITY_PACK_PATH.exists()


def test_physical_fixture_pack_allows_sandbox_replay_when_production_gate_disabled() -> None:
    gate = _physical_gate(require_production_ready=False)
    sandbox_decision = gate.admit(command_id="cmd-physical-sandbox", intent_name="physical.sandbox_replay")
    live_decision = gate.admit(command_id="cmd-physical-live", intent_name="physical.unlock_door")
    read_model = gate.read_model()
    capabilities = {item["capability_id"]: item for item in read_model["capabilities"]}

    assert sandbox_decision.status.value == "accepted"
    assert sandbox_decision.capability_id == "physical.sandbox_replay"
    assert sandbox_decision.owner_team == "physical-safety"
    assert live_decision.status.value == "accepted"
    assert live_decision.capability_id == "physical.unlock_door"
    assert read_model["capability_count"] == 2
    assert capabilities["physical.sandbox_replay"]["maturity_assessment"]["maturity_level"] == "C3"
    assert capabilities["physical.sandbox_replay"]["maturity_assessment"]["production_ready"] is False
    assert capabilities["physical.unlock_door"]["maturity_assessment"]["maturity_level"] == "C4"
    assert capabilities["physical.unlock_door"]["maturity_assessment"]["production_ready"] is False


def test_physical_fixture_pack_blocks_live_promotion_when_production_gate_enabled() -> None:
    gate = _physical_gate(require_production_ready=True)
    sandbox_decision = gate.admit(command_id="cmd-physical-sandbox", intent_name="physical.sandbox_replay")
    live_decision = gate.admit(command_id="cmd-physical-live", intent_name="physical.unlock_door")

    assert sandbox_decision.status.value == "rejected"
    assert sandbox_decision.capability_id == "physical.sandbox_replay"
    assert "capability is not production-ready" in sandbox_decision.reason
    assert "sandbox_receipt_missing" in sandbox_decision.reason
    assert live_decision.status.value == "rejected"
    assert live_decision.capability_id == "physical.unlock_door"
    assert "capability is not production-ready" in live_decision.reason
    assert "effect_bearing_production_requires_live_write" in live_decision.reason
    assert "worker_deployment_evidence_missing" in live_decision.reason
    assert "recovery_evidence_missing" in live_decision.reason


def test_physical_fixture_pack_projects_sandbox_only_gateway_evidence() -> None:
    gate = _physical_gate(require_production_ready=False)
    app = create_gateway_app(
        platform=StubPlatform(),
        capability_admission_gate_override=gate,
    )
    payload = TestClient(app).get("/capabilities/evidence").json()
    policy = _evaluate_physical_capability_policy(payload)

    assert payload["enabled"] is True
    assert payload["capability_count"] == 2
    assert payload["capability_evidence"]["physical.sandbox_replay"] == "sandbox"
    assert payload["capability_evidence"]["physical.unlock_door"] == "pilot"
    assert payload["sandbox_only_capabilities"] == ["physical.sandbox_replay"]
    assert payload["live_capabilities"] == []
    assert policy.passed is True
    assert policy.live_physical_capabilities == ()
    assert policy.sandbox_physical_capabilities == ("physical.sandbox_replay",)
    assert _validate_schema_instance(_load_schema(CAPABILITY_EVIDENCE_SCHEMA), payload) == []


def _physical_gate(*, require_production_ready: bool):
    capsule = DomainCapsule.from_mapping(_load_json(PHYSICAL_CAPSULE_PATH))
    capabilities = tuple(
        CapabilityRegistryEntry.from_mapping(item)
        for item in _load_json(PHYSICAL_CAPABILITY_PACK_PATH)["capabilities"]
    )
    return build_capability_admission_gate(
        capsules=(capsule,),
        capabilities=capabilities,
        require_certified=True,
        require_production_ready=require_production_ready,
        clock=lambda: "2026-05-06T00:00:00+00:00",
    )


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
