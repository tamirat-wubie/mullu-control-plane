"""Production evidence plane endpoint tests.

Purpose: verify public production evidence endpoints expose bounded runtime,
    capability, audit, and proof claims without upgrading missing evidence.
Governance scope: deployment witnesses, capability maturity projections,
    audit-anchor verification, and proof verification closure.
Dependencies: FastAPI TestClient and gateway server.
Invariants:
  - Deployment witnesses are signed and identify version, commit, environment, and gaps.
  - Capability evidence reports an absent registry as missing evidence.
  - Proof verification binds conformance, deployment witness, and audit anchor status.
"""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gateway.server import create_gateway_app  # noqa: E402
from scripts.collect_deployment_witness import _evaluate_physical_capability_policy  # noqa: E402
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


PRODUCTION_EVIDENCE_SCHEMA = _ROOT / "schemas" / "production_evidence_witness.schema.json"
CAPABILITY_EVIDENCE_SCHEMA = _ROOT / "schemas" / "capability_evidence_endpoint.schema.json"
AUDIT_VERIFICATION_SCHEMA = _ROOT / "schemas" / "audit_verification_endpoint.schema.json"
PROOF_VERIFICATION_SCHEMA = _ROOT / "schemas" / "proof_verification_endpoint.schema.json"


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


class StubCapabilityAdmissionGate:
    """Minimal capability gate fixture exposing a registry read model."""

    def __init__(self, capabilities: tuple[dict, ...]) -> None:
        self._capabilities = capabilities

    def read_model(self) -> dict:
        return {
            "require_certified": True,
            "capsule_count": 1,
            "capability_count": len(self._capabilities),
            "artifact_count": 0,
            "installations": (),
            "capabilities": self._capabilities,
            "domains": (),
            "governed_capability_records": (),
            "capability_maturity_assessments": (),
        }


def test_deployment_witness_is_signed_and_reports_missing_runtime_evidence(monkeypatch) -> None:
    monkeypatch.setenv("MULLU_DEPLOYMENT_ID", "dep_test_001")
    monkeypatch.setenv("MULLU_DEPLOYED_COMMIT_SHA", "abc123")
    monkeypatch.setenv("MULLU_DEPLOYMENT_WITNESS_SECRET", "deployment-secret")
    app = create_gateway_app(platform=StubPlatform())
    client = TestClient(app)

    response = client.get("/deployment/witness")
    payload = response.json()

    assert response.status_code == 200
    assert payload["deployment_id"] == "dep_test_001"
    assert payload["commit_sha"] == "abc123"
    assert payload["runtime_env"] == "local_dev"
    assert payload["version"] == "1.0.0"
    assert payload["signature"].startswith("hmac-sha256:")
    assert payload["claim_hash"]
    assert "capability_registry" in payload["checks_missing"]
    assert "audit_anchor" in payload["checks_missing"]
    assert "proof_store" in payload["checks_missing"]
    assert _validate_schema_instance(_load_schema(PRODUCTION_EVIDENCE_SCHEMA), payload) == []


def test_capabilities_evidence_reports_disabled_registry() -> None:
    app = create_gateway_app(platform=StubPlatform())
    client = TestClient(app)

    payload = client.get("/capabilities/evidence").json()

    assert payload["enabled"] is False
    assert payload["capability_count"] == 0
    assert payload["capability_evidence"] == {}
    assert payload["live_capabilities"] == []
    assert payload["sandbox_only_capabilities"] == []
    assert payload["checks"][0]["check_id"] == "capability_registry_configured"
    assert payload["checks"][0]["passed"] is False
    assert _validate_schema_instance(_load_schema(CAPABILITY_EVIDENCE_SCHEMA), payload) == []


def test_live_physical_capability_evidence_is_derived_from_registry_extension(monkeypatch) -> None:
    monkeypatch.setenv("MULLU_DEPLOYMENT_ID", "dep_test_001")
    monkeypatch.setenv("MULLU_DEPLOYED_COMMIT_SHA", "abc123")
    monkeypatch.setenv("MULLU_DEPLOYMENT_WITNESS_SECRET", "deployment-secret")
    capability_gate = StubCapabilityAdmissionGate(
        (
            _physical_capability(
                maturity_assessment={"maturity_level": "C6", "production_ready": True},
                physical_safety_evidence=_physical_safety_evidence(),
            ),
        )
    )
    app = create_gateway_app(
        platform=StubPlatform(),
        capability_admission_gate_override=capability_gate,
    )
    client = TestClient(app)

    capability_payload = client.get("/capabilities/evidence").json()
    deployment_payload = client.get("/deployment/witness").json()
    physical_evidence = capability_payload["capability_evidence"]["physical.unlock_door"]
    capability_policy = _evaluate_physical_capability_policy(capability_payload)
    deployment_policy = _evaluate_physical_capability_policy(deployment_payload)

    assert capability_payload["enabled"] is True
    assert capability_payload["live_capabilities"] == ["physical.unlock_door"]
    assert physical_evidence["maturity"] == "production"
    assert physical_evidence["effect_mode"] == "live"
    assert physical_evidence["production_admissible"] is True
    assert physical_evidence["physical_action_receipt_ref"] == "physical-action-receipt-0123456789abcdef"
    assert deployment_payload["capability_evidence"]["physical.unlock_door"] == physical_evidence
    assert capability_policy.passed is True
    assert deployment_policy.passed is True
    assert _validate_schema_instance(_load_schema(CAPABILITY_EVIDENCE_SCHEMA), capability_payload) == []
    assert _validate_schema_instance(_load_schema(PRODUCTION_EVIDENCE_SCHEMA), deployment_payload) == []


def test_live_physical_capability_without_registry_safety_refs_remains_blocked() -> None:
    capability_gate = StubCapabilityAdmissionGate(
        (
            _physical_capability(
                maturity_assessment={"maturity_level": "C6", "production_ready": True},
                physical_safety_evidence={},
            ),
        )
    )
    app = create_gateway_app(
        platform=StubPlatform(),
        capability_admission_gate_override=capability_gate,
    )
    payload = TestClient(app).get("/capabilities/evidence").json()
    policy = _evaluate_physical_capability_policy(payload)

    assert payload["live_capabilities"] == ["physical.unlock_door"]
    assert payload["capability_evidence"]["physical.unlock_door"] == "production"
    assert policy.passed is False
    assert policy.blockers == ("physical.unlock_door:physical_live_safety_evidence_required",)
    assert _validate_schema_instance(_load_schema(CAPABILITY_EVIDENCE_SCHEMA), payload) == []


def test_audit_and_proof_verify_surface_anchor_gap(monkeypatch) -> None:
    monkeypatch.setenv("MULLU_RUNTIME_CONFORMANCE_SECRET", "conformance-secret")
    monkeypatch.setenv("MULLU_DEPLOYMENT_WITNESS_SECRET", "deployment-secret")
    app = create_gateway_app(platform=StubPlatform())
    client = TestClient(app)

    audit_payload = client.get("/audit/verify").json()
    proof_payload = client.get("/proof/verify").json()

    assert audit_payload["valid"] is False
    assert audit_payload["reason"] == "anchor_not_found"
    assert audit_payload["entries_checked"] == 0
    assert proof_payload["valid"] is False
    assert proof_payload["terminal_status"] == "verification_gaps"
    assert "runtime_conformance_signature" in proof_payload["checks_passed"]
    assert "deployment_witness_signature" in proof_payload["checks_passed"]
    assert "audit_anchor_verification" in proof_payload["checks_missing"]
    assert _validate_schema_instance(_load_schema(AUDIT_VERIFICATION_SCHEMA), audit_payload) == []
    assert _validate_schema_instance(_load_schema(PROOF_VERIFICATION_SCHEMA), proof_payload) == []


def _physical_capability(
    *,
    maturity_assessment: dict,
    physical_safety_evidence: dict,
) -> dict:
    return {
        "capability_id": "physical.unlock_door",
        "domain": "physical",
        "version": "1.0.0",
        "input_schema_ref": "urn:mullusi:schema:physical-command:1",
        "output_schema_ref": "urn:mullusi:schema:physical-receipt:1",
        "effect_model": {
            "expected_effects": ["door_unlocked"],
            "forbidden_effects": ["unlock_without_operator_approval"],
            "reconciliation_required": True,
        },
        "evidence_model": {
            "required_evidence": ["physical_action_receipt"],
            "terminal_certificate_required": True,
        },
        "authority_policy": {
            "required_roles": ["facility_operator"],
            "approval_chain": ["facility_admin"],
            "separation_of_duty": True,
        },
        "isolation_profile": {
            "execution_plane": "physical_worker",
            "network_allowlist": ["physical-control.internal"],
            "secret_scope": "physical-control",
        },
        "recovery_plan": {
            "rollback_capability": "physical.lock_door",
            "compensation_capability": "",
            "review_required_on_failure": True,
        },
        "cost_model": {
            "budget_class": "physical-ops",
            "max_estimated_cost": 1.0,
        },
        "obligation_model": {
            "owner_team": "facility-ops",
            "failure_due_seconds": 300,
            "escalation_route": "facility-ops-oncall",
        },
        "certification_status": "certified",
        "metadata": {"risk_tier": "critical"},
        "extensions": {
            "physical_live_safety_evidence": physical_safety_evidence,
        },
        "maturity_assessment": maturity_assessment,
    }


def _physical_safety_evidence() -> dict:
    return {
        "physical_action_receipt_ref": "physical-action-receipt-0123456789abcdef",
        "simulation_ref": "proof://physical/simulation-pass",
        "operator_approval_ref": "approval:physical-live",
        "manual_override_ref": "manual-override:physical-live",
        "emergency_stop_ref": "emergency-stop:physical-live",
        "sensor_confirmation_ref": "sensor-confirmation:physical-live",
        "deployment_witness_ref": "deployment-witness:physical-live",
    }
