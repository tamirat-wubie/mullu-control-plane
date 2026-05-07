"""Gateway capability forge tests.

Purpose: verify that candidate capability packages remain candidate-only,
    schema-backed, and promotion-blocked until governed certification.
Governance scope: capability candidate generation, validation, schema contract,
    sandbox evidence, approval controls, physical safety evidence requirements,
    and recovery coverage.
Dependencies: gateway.capability_forge and schemas/capability_candidate.schema.json.
Invariants:
  - Candidate packages validate against the public schema.
  - Effect-bearing candidates require sandbox, receipt, and recovery evidence.
  - Physical live-effect candidates declare live safety evidence requirements.
  - High-risk candidates require approval policy and injection evals.
  - Candidates cannot claim certified status or unblock their own promotion.
"""

from __future__ import annotations

import json
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from gateway.capability_forge import (
    CapabilityCertificationHandoff,
    CapabilityForge,
    CapabilityForgeInput,
    CapabilityHandoffEvidenceInstallBatch,
    install_certification_handoff_evidence_batch,
    install_certification_handoff_evidence,
)
from gateway.capability_maturity import CapabilityMaturityEvidenceSynthesizer, CapabilityRegistryMaturityProjector
from mcoi_runtime.contracts.governed_capability_fabric import (
    CapabilityCertificationStatus,
    CapabilityRegistryEntry,
)


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "capability_candidate.schema.json"
REGISTRY_FIXTURE_PATH = ROOT / "integration" / "governed_capability_fabric" / "fixtures" / "capability_registry_entry.json"


def test_capability_forge_creates_schema_valid_candidate_package() -> None:
    candidate = CapabilityForge().create_candidate(_forge_input())
    payload = asdict(candidate)
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    assert set(schema["required"]).issubset(payload)

    assert schema["$id"] == "urn:mullusi:schema:capability-candidate:1"
    assert schema["properties"]["certification_status"]["const"] == "candidate"
    assert schema["properties"]["promotion_blocked"]["const"] is True
    assert "promotion_evidence_requirements" in schema["required"]
    assert candidate.certification_status == "candidate"
    assert candidate.promotion_blocked is True
    assert candidate.package_hash


def test_capability_forge_projects_high_risk_controls() -> None:
    candidate = CapabilityForge().create_candidate(_forge_input())
    policy_types = {rule.rule_type for rule in candidate.policy_rules if rule.required}
    eval_types = {eval_case.eval_type for eval_case in candidate.evals}

    assert "approval" in policy_types
    assert "tenant_binding" in policy_types
    assert "prompt_injection" in eval_types
    assert candidate.adapter.sandbox_required is True
    assert candidate.receipt_contract.terminal_certificate_required is True
    assert candidate.rollback_path.review_required is True


def test_capability_forge_generates_physical_safety_evidence_requirements() -> None:
    candidate = CapabilityForge().create_candidate(_physical_forge_input())
    validation = CapabilityForge().validate(candidate)
    requirements = {
        requirement.evidence_key: requirement
        for requirement in candidate.promotion_evidence_requirements
        if requirement.evidence_type == "physical_live_safety"
    }

    assert validation.accepted is True
    assert candidate.schemas.receipt_schema_ref == "urn:mullusi:schema:physical-action-receipt:1"
    assert set(requirements) == set(_physical_live_safety_evidence_refs())
    assert all(requirement.required is True for requirement in requirements.values())
    assert all(
        requirement.schema_ref == "urn:mullusi:schema:physical-action-receipt:1"
        for requirement in requirements.values()
    )
    assert "physical_action_receipt_ref" in requirements
    assert "emergency_stop_ref" in requirements


def test_capability_forge_rejects_physical_candidate_missing_safety_requirement() -> None:
    candidate = CapabilityForge().create_candidate(_physical_forge_input())
    unsafe = replace(
        candidate,
        promotion_evidence_requirements=[
            requirement
            for requirement in candidate.promotion_evidence_requirements
            if requirement.evidence_key != "simulation_ref"
        ],
    )
    validation = CapabilityForge().validate(unsafe)

    assert validation.accepted is False
    assert validation.reason == "candidate_invalid"
    assert "missing_physical_safety_evidence_requirement:simulation_ref" in validation.errors


def test_capability_forge_builds_certification_handoff_for_maturity_synthesis() -> None:
    candidate = CapabilityForge().create_candidate(_forge_input())
    handoff = _certification_handoff(candidate)
    extension = CapabilityMaturityEvidenceSynthesizer().materialize_extension(
        _registry_entry_for_candidate(candidate),
        handoff.maturity_evidence_bundle,
        require_production_ready=True,
    )

    assert isinstance(handoff, CapabilityCertificationHandoff)
    assert handoff.package_id == candidate.package_id
    assert handoff.package_hash == candidate.package_hash
    assert handoff.maturity_evidence_bundle.certification_ref == candidate.documentation.promotion_evidence_ref
    assert handoff.maturity_evidence_bundle.sandbox_receipt_ref == "sandbox/payments.send/receipt.json"
    assert extension["live_write_receipt_valid"] is True
    assert "proof://payments.send/worker" in handoff.required_evidence_refs
    assert handoff.handoff_hash


def test_capability_forge_installs_physical_safety_refs_from_handoff() -> None:
    candidate = CapabilityForge().create_candidate(_physical_forge_input())
    handoff = _physical_certification_handoff(candidate)
    entry = _registry_entry_for_candidate(candidate)

    installed = install_certification_handoff_evidence(entry, handoff, require_production_ready=True)
    physical_evidence = installed.extensions["physical_live_safety_evidence"]

    assert physical_evidence["physical_action_receipt_schema_ref"] == "urn:mullusi:schema:physical-action-receipt:1"
    assert physical_evidence["simulation_ref"] == "proof://physical.unlock_door/simulation"
    assert physical_evidence["emergency_stop_ref"] == "proof://physical.unlock_door/emergency-stop"
    assert "proof://physical.unlock_door/sensor-confirmation" in handoff.required_evidence_refs
    assert "capability_certification_evidence" in installed.extensions
    assert "capability_maturity_evidence" not in installed.extensions


def test_capability_forge_installs_handoff_as_certification_evidence_only() -> None:
    candidate = CapabilityForge().create_candidate(_forge_input())
    handoff = _certification_handoff(candidate)
    entry = _registry_entry_for_candidate(candidate)

    installed = install_certification_handoff_evidence(entry, handoff, require_production_ready=True)
    extension = installed.extensions["capability_certification_evidence"]
    assessment = CapabilityRegistryMaturityProjector().assess_entry(installed)

    assert installed is not entry
    assert installed.capability_id == entry.capability_id
    assert "capability_certification_evidence" not in entry.extensions
    assert "capability_maturity_evidence" not in installed.extensions
    assert extension["capability_id"] == candidate.capability_id
    assert extension["source_package_hash"] == candidate.package_hash
    assert extension["source_handoff_hash"] == handoff.handoff_hash
    assert extension["installed_by"] == "install_certification_handoff_evidence"
    assert extension["certification_evidence_hash"]
    assert assessment.maturity_level == "C6"
    assert assessment.production_ready is True
    assert assessment.autonomy_ready is False


def test_capability_forge_installs_handoff_evidence_batch_with_audit_hash() -> None:
    candidate = CapabilityForge().create_candidate(_forge_input())
    handoff = _certification_handoff(candidate)
    entry = _registry_entry_for_candidate(candidate)

    batch = install_certification_handoff_evidence_batch((entry,), (handoff,), require_production_ready=True)
    installed = batch.registry_entries[0]
    extension = installed.extensions["capability_certification_evidence"]

    assert isinstance(batch, CapabilityHandoffEvidenceInstallBatch)
    assert batch.registry_entries == (installed,)
    assert batch.installed_capability_ids == (entry.capability_id,)
    assert batch.handoff_hashes == (handoff.handoff_hash,)
    assert batch.batch_hash
    assert installed is not entry
    assert extension["source_handoff_hash"] == handoff.handoff_hash
    assert "capability_maturity_evidence" not in installed.extensions


def test_capability_forge_handoff_batch_rejects_coverage_drift() -> None:
    candidate = CapabilityForge().create_candidate(_forge_input())
    handoff = _certification_handoff(candidate)
    entry = _registry_entry_for_candidate(candidate)
    extra_handoff = replace(handoff, capability_id="payments.refund")

    with pytest.raises(ValueError, match="^capability_handoff_batch_entry_required$"):
        install_certification_handoff_evidence_batch((), ())
    with pytest.raises(ValueError, match="^capability_handoff_batch_duplicate_entry$"):
        install_certification_handoff_evidence_batch((entry, entry), (handoff,))
    with pytest.raises(ValueError, match="^capability_handoff_batch_duplicate_handoff$"):
        install_certification_handoff_evidence_batch((entry,), (handoff, handoff))
    with pytest.raises(ValueError, match="^capability_handoff_batch_missing_handoff:payments\\.send$"):
        install_certification_handoff_evidence_batch((entry,), ())
    with pytest.raises(ValueError, match="^capability_handoff_batch_extra_handoff:payments\\.refund$"):
        install_certification_handoff_evidence_batch((entry,), (handoff, extra_handoff))


def test_capability_forge_handoff_install_rejects_gate_bypasses() -> None:
    candidate = CapabilityForge().create_candidate(_forge_input())
    handoff = _certification_handoff(candidate)
    entry = _registry_entry_for_candidate(candidate)
    mismatched_entry = replace(entry, capability_id="payments.refund")
    uncertified_entry = replace(entry, certification_status=CapabilityCertificationStatus.CANDIDATE)
    maturity_claim_entry = replace(entry, extensions={"capability_maturity_evidence": {"generated_by": "test"}})
    unstamped_handoff = replace(handoff, handoff_hash="")
    tampered_handoff = replace(handoff, package_hash="tampered")

    with pytest.raises(ValueError, match="^capability_handoff_entry_mismatch$"):
        install_certification_handoff_evidence(mismatched_entry, handoff)
    with pytest.raises(ValueError, match="^capability_handoff_requires_certified_entry$"):
        install_certification_handoff_evidence(uncertified_entry, handoff)
    with pytest.raises(ValueError, match="^capability_handoff_hash_required$"):
        install_certification_handoff_evidence(entry, unstamped_handoff)
    with pytest.raises(ValueError, match="^capability_handoff_hash_mismatch$"):
        install_certification_handoff_evidence(entry, tampered_handoff)
    with pytest.raises(ValueError, match="^capability_handoff_refuses_maturity_override$"):
        install_certification_handoff_evidence(maturity_claim_entry, handoff)


def test_capability_forge_certification_handoff_rejects_missing_required_refs() -> None:
    candidate = CapabilityForge().create_candidate(_forge_input())
    unsafe_candidate = replace(candidate, promotion_blocked=False)

    with pytest.raises(ValueError, match="^effect_bearing_certification_requires_live_write_ref$"):
        CapabilityForge().build_certification_handoff(
            candidate,
            live_read_receipt_ref="proof://payments.send/live-read",
            worker_deployment_ref="proof://payments.send/worker",
            recovery_evidence_ref="proof://payments.send/recovery",
        )
    with pytest.raises(ValueError, match="^recovery_evidence_ref_required$"):
        CapabilityForge().build_certification_handoff(
            candidate,
            live_read_receipt_ref="proof://payments.send/live-read",
            live_write_receipt_ref="proof://payments.send/live-write",
            worker_deployment_ref="proof://payments.send/worker",
            recovery_evidence_ref="",
        )
    with pytest.raises(ValueError, match="^capability_candidate_invalid_for_certification_handoff$"):
        CapabilityForge().build_certification_handoff(
            unsafe_candidate,
            live_read_receipt_ref="proof://payments.send/live-read",
            live_write_receipt_ref="proof://payments.send/live-write",
            worker_deployment_ref="proof://payments.send/worker",
            recovery_evidence_ref="proof://payments.send/recovery",
        )
    with pytest.raises(
        ValueError,
        match="^physical_live_safety_evidence_refs_incomplete:physical_action_receipt_ref,simulation_ref,",
    ):
        CapabilityForge().build_certification_handoff(
            CapabilityForge().create_candidate(_physical_forge_input()),
            live_read_receipt_ref="proof://physical.unlock_door/live-read",
            live_write_receipt_ref="proof://physical.unlock_door/live-write",
            worker_deployment_ref="proof://physical.unlock_door/worker",
            recovery_evidence_ref="proof://physical.unlock_door/recovery",
        )


def test_capability_forge_rejects_candidate_self_promotion() -> None:
    candidate = CapabilityForge().create_candidate(_forge_input())
    promoted = replace(candidate, certification_status="production_certified", promotion_blocked=False)
    validation = CapabilityForge().validate(promoted)

    assert validation.accepted is False
    assert validation.reason == "candidate_invalid"
    assert "candidate_must_not_claim_certified_status" in validation.errors
    assert "candidate_promotion_must_be_blocked" in validation.errors


def test_capability_forge_rejects_effect_bearing_package_without_recovery() -> None:
    candidate = CapabilityForge().create_candidate(_forge_input())
    unsafe = replace(
        candidate,
        rollback_path=replace(candidate.rollback_path, rollback_type="none", review_required=False),
    )
    validation = CapabilityForge().validate(unsafe)

    assert validation.accepted is False
    assert validation.package_id == candidate.package_id
    assert "effect_bearing_candidate_requires_recovery_path" in validation.errors
    assert validation.package_hash == candidate.package_hash


def test_capability_forge_rejects_missing_required_eval() -> None:
    candidate = CapabilityForge().create_candidate(_forge_input())
    unsafe = replace(
        candidate,
        evals=[eval_case for eval_case in candidate.evals if eval_case.eval_type != "tenant_boundary"],
    )

    validation = CapabilityForge().validate(unsafe)

    assert validation.accepted is False
    assert validation.reason == "candidate_invalid"
    assert validation.errors == ("missing_eval:tenant_boundary",)


def test_capability_candidate_schema_rejects_unblocked_candidate() -> None:
    candidate = CapabilityForge().create_candidate(_forge_input())
    payload = asdict(candidate)
    payload["promotion_blocked"] = False
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    promotion_contract = schema["properties"]["promotion_blocked"]
    assert promotion_contract["type"] == "boolean"
    assert promotion_contract["const"] is True
    assert payload["promotion_blocked"] != promotion_contract["const"]


def _forge_input() -> CapabilityForgeInput:
    return CapabilityForgeInput(
        capability_id="payments.send",
        version="0.1.0",
        domain="finance",
        risk="high",
        side_effects=("payment_dispatch",),
        api_docs_ref="docs/providers/payments.md",
        input_schema_ref="schemas/payments_send.input.schema.json",
        output_schema_ref="schemas/payments_send.output.schema.json",
        owner_team="finance_ops",
        network_allowlist=("api.stripe.com",),
        secret_scope="payments/stripe",
        requires_approval=True,
    )


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


def _certification_handoff(candidate) -> CapabilityCertificationHandoff:
    return CapabilityForge().build_certification_handoff(
        candidate,
        live_read_receipt_ref="proof://payments.send/live-read",
        live_write_receipt_ref="proof://payments.send/live-write",
        worker_deployment_ref="proof://payments.send/worker",
        recovery_evidence_ref="proof://payments.send/recovery",
    )


def _physical_certification_handoff(candidate) -> CapabilityCertificationHandoff:
    return CapabilityForge().build_certification_handoff(
        candidate,
        live_read_receipt_ref="proof://physical.unlock_door/live-read",
        live_write_receipt_ref="proof://physical.unlock_door/live-write",
        worker_deployment_ref="proof://physical.unlock_door/worker",
        recovery_evidence_ref="proof://physical.unlock_door/recovery",
        physical_live_safety_evidence_refs=_physical_live_safety_evidence_refs(),
    )


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


def _registry_entry_for_candidate(candidate) -> CapabilityRegistryEntry:
    payload = json.loads(REGISTRY_FIXTURE_PATH.read_text(encoding="utf-8"))
    payload["capability_id"] = candidate.capability_id
    payload["domain"] = candidate.domain
    payload["version"] = candidate.version
    payload["input_schema_ref"] = candidate.schemas.input_schema_ref
    payload["output_schema_ref"] = candidate.schemas.output_schema_ref
    payload["certification_status"] = "certified"
    return CapabilityRegistryEntry.from_mapping(payload)
