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
  - The receipt is an audit witness, not admission authority.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from gateway.capability_capsule_installer import (
    CapabilityCapsuleInstallationOutcome,
    install_certified_capsule_with_handoff_evidence,
)
from gateway.capability_forge import CapabilityCertificationHandoff, CapabilityForge, CapabilityForgeInput
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


def _registry_entry() -> CapabilityRegistryEntry:
    return CapabilityRegistryEntry.from_mapping(_fixture("capability_registry_entry.json"))


def _certified_entry() -> CapabilityRegistryEntry:
    return replace(_registry_entry(), certification_status=CapabilityCertificationStatus.CERTIFIED)


def _capsule() -> DomainCapsule:
    return DomainCapsule.from_mapping(_fixture("domain_capsule.json"))


def _certified_capsule() -> DomainCapsule:
    return replace(_capsule(), certification_status=DomainCapsuleCertificationStatus.CERTIFIED)


def _certification_handoff_for(entry: CapabilityRegistryEntry) -> CapabilityCertificationHandoff:
    candidate = CapabilityForge().create_candidate(_forge_input_for_entry(entry))
    return CapabilityForge().build_certification_handoff(
        candidate,
        live_read_receipt_ref=f"proof://{entry.capability_id}/live-read",
        live_write_receipt_ref=f"proof://{entry.capability_id}/live-write",
        worker_deployment_ref=f"proof://{entry.capability_id}/worker",
        recovery_evidence_ref=f"proof://{entry.capability_id}/recovery",
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


def _clock() -> str:
    return "2026-04-24T12:00:00+00:00"
