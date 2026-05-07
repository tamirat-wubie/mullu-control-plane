"""Gateway capability capsule installer tests.

Purpose: verify the shortcut installer composes handoff evidence, capsule
    compilation, registry admission, and receipt stamping without bypassing
    governed registry authority.
Governance scope: certification handoff coverage, capsule compilation,
    registry admission, rejected-admission receipts, and causal receipt hashes.
Dependencies: gateway.capability_capsule_installer, gateway.capability_forge,
    governed capability fabric fixtures, and governed capability registry.
Invariants:
  - Installed receipts point at the registry admission record and evidence manifest.
  - Rejected strict admissions return receipts without mutating the registry.
  - Production-ready physical capsule admission runs the physical promotion preflight.
  - The receipt is an audit witness, not admission authority.
"""

from __future__ import annotations

import json
from dataclasses import asdict, replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from gateway.capability_capsule_installer import (
    CapabilityCapsuleInstallationOutcome,
    install_certified_capsule_with_handoff_evidence,
)
from gateway.capability_fabric import MaturityProjectingCapabilityAdmissionGate
from gateway.capability_forge import CapabilityCertificationHandoff, CapabilityForge, CapabilityForgeInput
from gateway.server import create_gateway_app
from mcoi_runtime.contracts.governed_capability_fabric import (
    CapabilityCertificationStatus,
    CapabilityRegistryEntry,
    CapsuleAdmissionStatus,
    DomainCapsule,
    DomainCapsuleCertificationStatus,
)
from mcoi_runtime.core.governed_capability_registry import GovernedCapabilityRegistry


ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = ROOT / "integration" / "governed_capability_fabric" / "fixtures"
PHYSICAL_CAPSULE_PATH = ROOT / "capsules" / "physical.json"
PHYSICAL_CAPABILITY_PACK_PATH = ROOT / "capabilities" / "physical" / "capability_pack.json"


class StubPlatform:
    """Minimal platform fixture for gateway app construction."""

    def process_message(self, message, tenant_id: str, identity_id: str):  # noqa: ANN001
        return {
            "response": "ok",
            "tenant_id": tenant_id,
            "identity_id": identity_id,
        }


def test_capsule_installer_admits_certified_handoff_batch_with_receipt() -> None:
    registry = GovernedCapabilityRegistry(clock=_clock)
    entry = _certified_entry()
    handoff = _certification_handoff_for(entry)

    outcome = install_certified_capsule_with_handoff_evidence(
        capsule=_certified_capsule(),
        registry_entries=(entry,),
        handoffs=(handoff,),
        registry=registry,
        clock=_clock,
        require_production_ready=True,
    )
    manifest_artifact = next(
        artifact
        for artifact in outcome.compilation_result.artifacts
        if artifact.artifact_type == "capability_certification_evidence_manifest"
    )

    assert isinstance(outcome, CapabilityCapsuleInstallationOutcome)
    assert outcome.installation_record.status is CapsuleAdmissionStatus.INSTALLED
    assert outcome.receipt.admission_status == "installed"
    assert outcome.receipt.batch_hash == outcome.evidence_batch.batch_hash
    assert outcome.receipt.compilation_id == outcome.compilation_result.compilation_id
    assert outcome.receipt.installation_id == outcome.installation_record.installation_id
    assert outcome.receipt.certification_evidence_manifest_id == manifest_artifact.artifact_id
    assert outcome.receipt.receipt_is_not_admission_authority is True
    assert outcome.receipt.admission_authority == "GovernedCapabilityRegistry.install"
    assert outcome.receipt.receipt_hash
    assert registry.capability_count == 1
    assert registry.artifact_count == 11


def test_capsule_installer_returns_rejected_receipt_without_registry_mutation() -> None:
    registry = GovernedCapabilityRegistry(clock=_clock)
    entry = _certified_entry()
    handoff = _certification_handoff_for(entry)

    outcome = install_certified_capsule_with_handoff_evidence(
        capsule=_capsule(),
        registry_entries=(entry,),
        handoffs=(handoff,),
        registry=registry,
        clock=_clock,
        require_production_ready=True,
    )

    assert outcome.installation_record.status is CapsuleAdmissionStatus.REJECTED
    assert outcome.receipt.admission_status == "rejected"
    assert outcome.receipt.installed_capability_ids == (entry.capability_id,)
    assert outcome.receipt.certification_evidence_manifest_id
    assert "capsule is not certified: draft" in outcome.receipt.warnings
    assert "strict admission requires certified capsule and capabilities" in outcome.receipt.errors
    assert outcome.receipt.registry_capability_count == 0
    assert outcome.receipt.registry_artifact_count == 0
    assert registry.capability_count == 0
    assert registry.artifact_count == 0
    assert outcome.receipt.receipt_hash


def test_capsule_installer_runs_physical_preflight_before_registry_mutation() -> None:
    registry = GovernedCapabilityRegistry(clock=_clock)
    entry = _physical_entry("physical.unlock_door")
    handoff = _certification_handoff_for(entry)

    with pytest.raises(ValueError) as exc_info:
        install_certified_capsule_with_handoff_evidence(
            capsule=_physical_capsule(("physical.unlock_door",)),
            registry_entries=(entry,),
            handoffs=(handoff,),
            registry=registry,
            clock=_clock,
            require_production_ready=True,
        )

    error = str(exc_info.value)
    assert error.startswith("physical_capability_promotion_preflight_failed:")
    assert "live_physical_safety_evidence_complete" in error
    assert "physical_production_evidence_projection" in error
    assert registry.capability_count == 0
    assert registry.artifact_count == 0


def test_capsule_installer_admits_physical_capsule_when_preflight_passes() -> None:
    registry = GovernedCapabilityRegistry(clock=_clock)
    entry = _physical_entry("physical.unlock_door", physical_safety_evidence=True)
    handoff = _certification_handoff_for(entry)

    outcome = install_certified_capsule_with_handoff_evidence(
        capsule=_physical_capsule(("physical.unlock_door",)),
        registry_entries=(entry,),
        handoffs=(handoff,),
        registry=registry,
        clock=_clock,
        require_production_ready=True,
    )

    assert outcome.installation_record.status is CapsuleAdmissionStatus.INSTALLED
    assert outcome.receipt.admission_status == "installed"
    assert outcome.receipt.installed_capability_ids == ("physical.unlock_door",)
    assert outcome.receipt.certification_evidence_manifest_id
    assert registry.capability_count == 1
    assert registry.artifact_count > 0


def test_capsule_admission_operator_endpoint_installs_and_lists_receipt() -> None:
    registry = GovernedCapabilityRegistry(clock=_clock)
    gate = MaturityProjectingCapabilityAdmissionGate(registry=registry, clock=_clock)
    app = create_gateway_app(platform=StubPlatform(), capability_admission_gate_override=gate)
    client = TestClient(app)
    entry = _certified_entry()
    handoff = _certification_handoff_for(entry)

    response = client.post(
        "/capability-fabric/capsule-admissions",
        json={
            "capsule": _certified_capsule().to_json_dict(),
            "registry_entries": [entry.to_json_dict()],
            "handoffs": [asdict(handoff)],
            "require_production_ready": True,
        },
    )
    receipts = client.get("/capability-fabric/capsule-admission-receipts?status=installed")
    read_model = client.get("/capability-fabric/read-model")

    assert response.status_code == 200
    assert response.json()["admission_receipt"]["admission_status"] == "installed"
    assert response.json()["admission_receipt"]["receipt_is_not_admission_authority"] is True
    assert response.json()["admission_receipt"]["admission_authority"] == "GovernedCapabilityRegistry.install"
    assert response.json()["installation_record"]["status"] == "installed"
    assert response.json()["evidence_batch"]["batch_hash"]
    assert response.json()["compilation_result"]["status"] == "success"
    assert receipts.status_code == 200
    assert receipts.json()["count"] == 1
    assert receipts.json()["capsule_admission_receipts"][0]["capsule_id"] == _certified_capsule().capsule_id
    assert read_model.json()["capability_count"] == 1
    assert read_model.json()["artifact_count"] == 11


def test_capsule_admission_operator_endpoint_rejects_invalid_payload() -> None:
    registry = GovernedCapabilityRegistry(clock=_clock)
    gate = MaturityProjectingCapabilityAdmissionGate(registry=registry, clock=_clock)
    app = create_gateway_app(platform=StubPlatform(), capability_admission_gate_override=gate)
    client = TestClient(app)

    response = client.post(
        "/capability-fabric/capsule-admissions",
        json={"capsule": {}, "registry_entries": [], "handoffs": [], "require_production_ready": "yes"},
    )
    receipts = client.get("/capability-fabric/capsule-admission-receipts")

    assert response.status_code == 400
    assert response.json()["detail"] == "capsule_admission_registry_entries_required"
    assert receipts.status_code == 200
    assert receipts.json()["count"] == 0
    assert registry.capability_count == 0
    assert registry.artifact_count == 0


def test_capsule_admission_operator_endpoint_blocks_physical_preflight_failure() -> None:
    registry = GovernedCapabilityRegistry(clock=_clock)
    gate = MaturityProjectingCapabilityAdmissionGate(registry=registry, clock=_clock)
    app = create_gateway_app(platform=StubPlatform(), capability_admission_gate_override=gate)
    client = TestClient(app)
    entry = _physical_entry("physical.unlock_door")
    handoff = _certification_handoff_for(entry)

    response = client.post(
        "/capability-fabric/capsule-admissions",
        json={
            "capsule": _physical_capsule(("physical.unlock_door",)).to_json_dict(),
            "registry_entries": [entry.to_json_dict()],
            "handoffs": [asdict(handoff)],
            "require_production_ready": True,
        },
    )
    receipts = client.get("/capability-fabric/capsule-admission-receipts")

    assert response.status_code == 400
    assert response.json()["detail"].startswith("physical_capability_promotion_preflight_failed:")
    assert receipts.status_code == 200
    assert receipts.json()["count"] == 0
    assert registry.capability_count == 0
    assert registry.artifact_count == 0


def test_capsule_admission_operator_endpoint_accepts_physical_safety_refs_from_handoff() -> None:
    registry = GovernedCapabilityRegistry(clock=_clock)
    gate = MaturityProjectingCapabilityAdmissionGate(registry=registry, clock=_clock)
    app = create_gateway_app(platform=StubPlatform(), capability_admission_gate_override=gate)
    client = TestClient(app)
    entry = _physical_entry("physical.unlock_door")
    handoff = _certification_handoff_for(entry, physical_safety_evidence=True)

    response = client.post(
        "/capability-fabric/capsule-admissions",
        json={
            "capsule": _physical_capsule(("physical.unlock_door",)).to_json_dict(),
            "registry_entries": [entry.to_json_dict()],
            "handoffs": [asdict(handoff)],
            "require_production_ready": True,
        },
    )
    evidence_entry = response.json()["evidence_batch"]["registry_entries"][0]
    physical_evidence = evidence_entry["extensions"]["physical_live_safety_evidence"]

    assert response.status_code == 200
    assert response.json()["admission_receipt"]["admission_status"] == "installed"
    assert physical_evidence["simulation_ref"] == "proof://physical/simulation-pass"
    assert physical_evidence["emergency_stop_ref"] == "emergency-stop:physical-live"
    assert registry.capability_count == 1
    assert registry.artifact_count > 0


def _registry_entry() -> CapabilityRegistryEntry:
    return CapabilityRegistryEntry.from_mapping(_fixture("capability_registry_entry.json"))


def _certified_entry() -> CapabilityRegistryEntry:
    return replace(_registry_entry(), certification_status=CapabilityCertificationStatus.CERTIFIED)


def _capsule() -> DomainCapsule:
    return DomainCapsule.from_mapping(_fixture("domain_capsule.json"))


def _certified_capsule() -> DomainCapsule:
    return replace(_capsule(), certification_status=DomainCapsuleCertificationStatus.CERTIFIED)


def _physical_capsule(capability_refs: tuple[str, ...]) -> DomainCapsule:
    return replace(
        DomainCapsule.from_mapping(_load_json(PHYSICAL_CAPSULE_PATH)),
        capability_refs=capability_refs,
    )


def _physical_entry(
    capability_id: str,
    *,
    physical_safety_evidence: bool = False,
) -> CapabilityRegistryEntry:
    pack = _load_json(PHYSICAL_CAPABILITY_PACK_PATH)
    for raw_entry in pack["capabilities"]:
        if raw_entry["capability_id"] != capability_id:
            continue
        entry = CapabilityRegistryEntry.from_mapping(raw_entry)
        extensions = dict(entry.extensions)
        extensions.pop("capability_maturity_evidence", None)
        if not physical_safety_evidence:
            return replace(entry, extensions=extensions)
        return replace(
            entry,
            extensions={
                **extensions,
                "physical_live_safety_evidence": _full_live_safety_evidence(),
            },
        )
    raise AssertionError(f"physical fixture capability not found: {capability_id}")


def _certification_handoff_for(
    entry: CapabilityRegistryEntry,
    *,
    physical_safety_evidence: bool = False,
) -> CapabilityCertificationHandoff:
    candidate = CapabilityForge().create_candidate(_forge_input_for_entry(entry))
    return CapabilityForge().build_certification_handoff(
        candidate,
        live_read_receipt_ref=f"proof://{entry.capability_id}/live-read",
        live_write_receipt_ref=f"proof://{entry.capability_id}/live-write",
        worker_deployment_ref=f"proof://{entry.capability_id}/worker",
        recovery_evidence_ref=f"proof://{entry.capability_id}/recovery",
        physical_live_safety_evidence_refs=_full_live_safety_evidence() if physical_safety_evidence else None,
    )


def _forge_input_for_entry(entry: CapabilityRegistryEntry) -> CapabilityForgeInput:
    return CapabilityForgeInput(
        capability_id=entry.capability_id,
        version=entry.version,
        domain=entry.domain,
        risk="high",
        side_effects=("external_write",),
        api_docs_ref=f"docs/providers/{entry.domain}.md",
        input_schema_ref=entry.input_schema_ref,
        output_schema_ref=entry.output_schema_ref,
        owner_team=entry.obligation_model.owner_team,
        network_allowlist=tuple(entry.isolation_profile.network_allowlist),
        secret_scope=entry.isolation_profile.secret_scope,
        requires_approval=True,
    )


def _fixture(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _full_live_safety_evidence() -> dict[str, str]:
    return {
        "physical_action_receipt_ref": "physical-action-receipt-0123456789abcdef",
        "simulation_ref": "proof://physical/simulation-pass",
        "operator_approval_ref": "approval:physical-live",
        "manual_override_ref": "manual-override:physical-live",
        "emergency_stop_ref": "emergency-stop:physical-live",
        "sensor_confirmation_ref": "sensor-confirmation:physical-live",
        "deployment_witness_ref": "deployment-witness:physical-live",
    }


def _clock() -> str:
    return "2026-04-24T12:00:00+00:00"
