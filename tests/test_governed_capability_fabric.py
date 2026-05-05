"""Purpose: validate governed capability fabric schema fixtures and failure modes.
Governance scope: universal capability registry entries and domain capsule contracts.
Dependencies: schema validation helper and canonical fabric fixtures.
Invariants:
  - Registry entries declare authority, evidence, recovery, cost, and obligations.
  - Domain capsules declare owner, policies, evidence rules, recovery rules, tests, and views.
  - Incomplete governed action packages fail schema validation before execution.
"""

from __future__ import annotations

import copy
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from scripts.validate_schemas import _validate_schema_instance
from mcoi_runtime.contracts.governed_capability_fabric import (
    CapsuleAdmissionStatus,
    CapsuleCompilationResult,
    CapabilityCertificationStatus,
    CapabilityRegistryEntry,
    CapsuleCompilationStatus,
    CapsuleCompilerArtifact,
    CommandCapabilityAdmissionStatus,
    DomainCapsule,
    DomainCapsuleCertificationStatus,
)
from mcoi_runtime.core.command_capability_admission import CommandCapabilityAdmissionGate
from mcoi_runtime.core.domain_capsule_compiler import DomainCapsuleCompiler
from mcoi_runtime.core.governed_capability_registry import GovernedCapabilityRegistry
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from gateway.capability_forge import (
    CapabilityForge,
    CapabilityForgeInput,
    install_certification_handoff_evidence_batch,
)
from gateway.capability_maturity import CapabilityRegistryMaturityProjector
from gateway.command_spine import CommandLedger, InMemoryCommandLedgerStore, compile_typed_intent


REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = REPO_ROOT / "schemas"
FIXTURE_DIR = REPO_ROOT / "integration" / "governed_capability_fabric" / "fixtures"


def _load_json(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as handle:
        payload = json.load(handle)
    assert isinstance(payload, dict)
    return payload


def _schema(name: str) -> dict[str, Any]:
    return _load_json(SCHEMA_DIR / name)


def _fixture(name: str) -> dict[str, Any]:
    return _load_json(FIXTURE_DIR / name)


def _registry_entry() -> CapabilityRegistryEntry:
    return CapabilityRegistryEntry.from_mapping(_fixture("capability_registry_entry.json"))


def _capsule() -> DomainCapsule:
    return DomainCapsule.from_mapping(_fixture("domain_capsule.json"))


def _clock() -> str:
    return "2026-04-24T12:00:00+00:00"


def _certified_entry() -> CapabilityRegistryEntry:
    entry = _registry_entry()
    return CapabilityRegistryEntry(
        capability_id=entry.capability_id,
        domain=entry.domain,
        version=entry.version,
        input_schema_ref=entry.input_schema_ref,
        output_schema_ref=entry.output_schema_ref,
        effect_model=entry.effect_model,
        evidence_model=entry.evidence_model,
        authority_policy=entry.authority_policy,
        isolation_profile=entry.isolation_profile,
        recovery_plan=entry.recovery_plan,
        cost_model=entry.cost_model,
        obligation_model=entry.obligation_model,
        certification_status=CapabilityCertificationStatus.CERTIFIED,
        metadata=entry.metadata,
        extensions=entry.extensions,
    )


def _certified_capsule() -> DomainCapsule:
    capsule = _capsule()
    return DomainCapsule(
        capsule_id=capsule.capsule_id,
        domain=capsule.domain,
        version=capsule.version,
        ontology_refs=capsule.ontology_refs,
        capability_refs=capsule.capability_refs,
        policy_refs=capsule.policy_refs,
        evidence_rules=capsule.evidence_rules,
        approval_rules=capsule.approval_rules,
        recovery_rules=capsule.recovery_rules,
        test_fixture_refs=capsule.test_fixture_refs,
        read_model_refs=capsule.read_model_refs,
        operator_view_refs=capsule.operator_view_refs,
        owner_team=capsule.owner_team,
        certification_status=DomainCapsuleCertificationStatus.CERTIFIED,
        metadata=capsule.metadata,
        extensions=capsule.extensions,
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


def test_capability_registry_entry_fixture_is_governed() -> None:
    schema = _schema("capability_registry_entry.schema.json")
    fixture = _fixture("capability_registry_entry.json")
    errors = _validate_schema_instance(schema, fixture)

    assert errors == []
    assert fixture["evidence_model"]["terminal_certificate_required"] is True
    assert fixture["obligation_model"]["owner_team"] == "customer_ops"
    assert fixture["isolation_profile"]["execution_plane"] == "connector_worker"


def test_capability_registry_entry_rejects_missing_authority() -> None:
    schema = _schema("capability_registry_entry.schema.json")
    fixture = _fixture("capability_registry_entry.json")
    invalid = copy.deepcopy(fixture)
    del invalid["authority_policy"]

    errors = _validate_schema_instance(schema, invalid)

    assert errors
    assert any("authority_policy" in error for error in errors)
    assert invalid["evidence_model"]["required_evidence"] == ["crm_update_receipt", "before_after_record_hash"]
    assert invalid["certification_status"] == "candidate"


def test_capability_registry_entry_rejects_unproven_effect_model() -> None:
    schema = _schema("capability_registry_entry.schema.json")
    fixture = _fixture("capability_registry_entry.json")
    invalid = copy.deepcopy(fixture)
    invalid["effect_model"]["expected_effects"] = []

    errors = _validate_schema_instance(schema, invalid)

    assert errors
    assert any("expected_effects" in error for error in errors)
    assert invalid["effect_model"]["forbidden_effects"] == [
        "billing_account_modified",
        "unrelated_customer_modified",
    ]
    assert invalid["evidence_model"]["terminal_certificate_required"] is True


def test_domain_capsule_fixture_is_compiler_ready() -> None:
    schema = _schema("domain_capsule.schema.json")
    fixture = _fixture("domain_capsule.json")
    errors = _validate_schema_instance(schema, fixture)

    assert errors == []
    assert fixture["owner_team"] == "customer_ops"
    assert fixture["capability_refs"] == ["crm.update_customer_address"]
    assert fixture["read_model_refs"] == ["read_models/customer_ops/command_closure"]


def test_domain_capsule_rejects_missing_owner_team() -> None:
    schema = _schema("domain_capsule.schema.json")
    fixture = _fixture("domain_capsule.json")
    invalid = copy.deepcopy(fixture)
    invalid["owner_team"] = ""

    errors = _validate_schema_instance(schema, invalid)

    assert errors
    assert any("owner_team" in error for error in errors)
    assert invalid["capability_refs"] == ["crm.update_customer_address"]
    assert invalid["certification_status"] == "draft"


def test_domain_capsule_rejects_missing_recovery_rules() -> None:
    schema = _schema("domain_capsule.schema.json")
    fixture = _fixture("domain_capsule.json")
    invalid = copy.deepcopy(fixture)
    invalid["recovery_rules"] = []

    errors = _validate_schema_instance(schema, invalid)

    assert errors
    assert any("recovery_rules" in error for error in errors)
    assert invalid["evidence_rules"] == ["crm_update_receipt_required", "before_after_hash_required"]
    assert invalid["operator_view_refs"] == ["views/customer_ops/effects", "views/customer_ops/obligations"]


def test_fabric_fixtures_round_trip_into_contracts() -> None:
    entry = _registry_entry()
    capsule = _capsule()

    assert entry.capability_id == "crm.update_customer_address"
    assert entry.evidence_model.required_evidence == ("crm_update_receipt", "before_after_record_hash")
    assert capsule.capability_refs == (entry.capability_id,)
    assert capsule.owner_team == entry.obligation_model.owner_team


def test_domain_capsule_compiler_emits_governed_artifacts() -> None:
    compiler = DomainCapsuleCompiler(clock=_clock)
    result = compiler.compile(_capsule(), [_registry_entry()])
    artifact_types = [artifact.artifact_type for artifact in result.artifacts]

    assert result.status is CapsuleCompilationStatus.SUCCESS_WITH_WARNINGS
    assert result.errors == ()
    assert "capability_registry_manifest" in artifact_types
    assert "certification_report" in artifact_types
    assert len(result.artifacts) == 10


def test_domain_capsule_compiler_blocks_missing_capability_ref() -> None:
    compiler = DomainCapsuleCompiler(clock=_clock)
    result = compiler.compile(_capsule(), [])

    assert result.status is CapsuleCompilationStatus.FAILED
    assert result.artifacts == ()
    assert result.warnings == ()
    assert result.errors == ("missing capability registry entry: crm.update_customer_address",)


def test_domain_capsule_compiler_blocks_domain_mismatch() -> None:
    compiler = DomainCapsuleCompiler(clock=_clock)
    entry = _registry_entry()
    mismatched = CapabilityRegistryEntry(
        capability_id=entry.capability_id,
        domain="finance_ops",
        version=entry.version,
        input_schema_ref=entry.input_schema_ref,
        output_schema_ref=entry.output_schema_ref,
        effect_model=entry.effect_model,
        evidence_model=entry.evidence_model,
        authority_policy=entry.authority_policy,
        isolation_profile=entry.isolation_profile,
        recovery_plan=entry.recovery_plan,
        cost_model=entry.cost_model,
        obligation_model=entry.obligation_model,
        certification_status=entry.certification_status,
        metadata=entry.metadata,
        extensions=entry.extensions,
    )

    result = compiler.compile(_capsule(), [mismatched])

    assert result.status is CapsuleCompilationStatus.FAILED
    assert result.artifacts == ()
    assert len(result.errors) == 1
    assert "capability domain mismatch" in result.errors[0]


def test_domain_capsule_compiler_success_for_certified_inputs() -> None:
    compiler = DomainCapsuleCompiler(clock=_clock)
    certified_entry = _certified_entry()
    certified_capsule = _certified_capsule()

    result = compiler.compile(certified_capsule, [certified_entry])

    assert result.status is CapsuleCompilationStatus.SUCCESS
    assert result.warnings == ()
    assert result.errors == ()
    assert result.succeeded is True


def test_governed_capability_registry_installs_certified_compilation() -> None:
    compiler = DomainCapsuleCompiler(clock=_clock)
    registry = GovernedCapabilityRegistry(clock=_clock)
    entry = _certified_entry()
    result = compiler.compile(_certified_capsule(), [entry])

    installation = registry.install(result, (entry,))
    domain_capabilities = registry.capabilities_for_domain("customer_ops")

    assert installation.status is CapsuleAdmissionStatus.INSTALLED
    assert installation.capability_ids == ("crm.update_customer_address",)
    assert registry.capability_count == 1
    assert registry.artifact_count == 10
    assert domain_capabilities == (entry,)


def test_handoff_evidence_batch_preserves_capsule_registry_admission() -> None:
    compiler = DomainCapsuleCompiler(clock=_clock)
    registry = GovernedCapabilityRegistry(clock=_clock)
    entry = _certified_entry()
    candidate = CapabilityForge().create_candidate(_forge_input_for_entry(entry))
    handoff = CapabilityForge().build_certification_handoff(
        candidate,
        live_read_receipt_ref="proof://crm.update_customer_address/live-read",
        live_write_receipt_ref="proof://crm.update_customer_address/live-write",
        worker_deployment_ref="proof://crm.update_customer_address/worker",
        recovery_evidence_ref="proof://crm.update_customer_address/recovery",
    )
    batch = install_certification_handoff_evidence_batch((entry,), (handoff,), require_production_ready=True)

    result = compiler.compile(_certified_capsule(), batch.registry_entries)
    installation = registry.install(result, batch.registry_entries)
    installed = registry.get_capability(entry.capability_id)
    assessment = CapabilityRegistryMaturityProjector().assess_entry(installed)

    assert installation.status is CapsuleAdmissionStatus.INSTALLED
    assert installation.capability_ids == (entry.capability_id,)
    assert registry.capability_count == 1
    assert installed.extensions["capability_certification_evidence"]["source_handoff_hash"] == handoff.handoff_hash
    assert "capability_maturity_evidence" not in installed.extensions
    assert assessment.production_ready is True
    assert assessment.maturity_level == "C6"
    assert batch.batch_hash


def test_governed_capability_registry_rejects_uncertified_strict_install() -> None:
    compiler = DomainCapsuleCompiler(clock=_clock)
    registry = GovernedCapabilityRegistry(clock=_clock)
    entry = _registry_entry()
    result = compiler.compile(_capsule(), [entry])

    installation = registry.install(result, (entry,))

    assert installation.status is CapsuleAdmissionStatus.REJECTED
    assert registry.capability_count == 0
    assert registry.artifact_count == 0
    assert installation.errors == ("strict admission requires certified capsule and capabilities",)


def test_governed_capability_registry_allows_uncertified_when_configured() -> None:
    compiler = DomainCapsuleCompiler(clock=_clock)
    registry = GovernedCapabilityRegistry(clock=_clock, require_certified=False)
    entry = _registry_entry()
    result = compiler.compile(_capsule(), [entry])

    installation = registry.install(result, (entry,))

    assert installation.status is CapsuleAdmissionStatus.INSTALLED
    assert installation.warnings == (
        "capsule is not certified: draft",
        "capability is not certified: crm.update_customer_address=candidate",
    )
    assert registry.capsule_for_capability(entry.capability_id) == _capsule().capsule_id
    assert registry.installation_for_capsule(_capsule().capsule_id).installation_id == installation.installation_id


def test_governed_capability_registry_rejects_failed_compilation() -> None:
    compiler = DomainCapsuleCompiler(clock=_clock)
    registry = GovernedCapabilityRegistry(clock=_clock)
    failed = compiler.compile(_capsule(), [])

    installation = registry.install(failed, ())

    assert installation.status is CapsuleAdmissionStatus.REJECTED
    assert registry.capsule_count == 0
    assert registry.capability_count == 0
    assert "compilation did not succeed" in installation.errors


def test_governed_capability_registry_rejects_duplicate_capability() -> None:
    compiler = DomainCapsuleCompiler(clock=_clock)
    registry = GovernedCapabilityRegistry(clock=_clock)
    entry = _certified_entry()
    result = compiler.compile(_certified_capsule(), [entry])
    first = registry.install(result, (entry,))

    second = registry.install(result, (entry,))

    assert first.status is CapsuleAdmissionStatus.INSTALLED
    assert second.status is CapsuleAdmissionStatus.REJECTED
    assert f"capsule already installed: {_certified_capsule().capsule_id}" in second.errors
    assert "capability already installed: crm.update_customer_address" in second.errors


def test_governed_capability_registry_rejects_manifest_mismatch() -> None:
    compiler = DomainCapsuleCompiler(clock=_clock)
    registry = GovernedCapabilityRegistry(clock=_clock, require_certified=False)
    result = compiler.compile(_capsule(), [_registry_entry()])

    installation = registry.install(result, ())

    assert installation.status is CapsuleAdmissionStatus.REJECTED
    assert installation.capability_ids == ()
    assert installation.artifact_ids
    assert "install request capability ids do not match compilation manifest" in installation.errors


def test_governed_capability_registry_rejects_artifact_source_capsule_mismatch() -> None:
    compiler = DomainCapsuleCompiler(clock=_clock)
    registry = GovernedCapabilityRegistry(clock=_clock, require_certified=False)
    entry = _registry_entry()
    result = compiler.compile(_capsule(), [entry])
    malformed_artifacts = (
        replace(result.artifacts[0], source_capsule_id="capsule/forged"),
        *result.artifacts[1:],
    )
    malformed = CapsuleCompilationResult(
        compilation_id=result.compilation_id,
        capsule_id=result.capsule_id,
        status=result.status,
        artifacts=malformed_artifacts,
        warnings=result.warnings,
        errors=result.errors,
        compiled_at=result.compiled_at,
    )

    installation = registry.install(malformed, (entry,))

    assert installation.status is CapsuleAdmissionStatus.REJECTED
    assert registry.capability_count == 0
    assert registry.artifact_count == 0
    assert any("artifact source capsule mismatch" in error for error in installation.errors)


def test_governed_capability_registry_rejects_manifest_domain_mismatch() -> None:
    compiler = DomainCapsuleCompiler(clock=_clock)
    registry = GovernedCapabilityRegistry(clock=_clock, require_certified=False)
    entry = _registry_entry()
    result = compiler.compile(_capsule(), [entry])
    manifest = result.artifacts[0]
    payload = dict(manifest.payload)
    registry_entries = [dict(payload["registry_entries"][0])]
    registry_entries[0]["domain"] = "forged_ops"
    payload["registry_entries"] = registry_entries
    malformed_artifacts = (
        CapsuleCompilerArtifact(
            artifact_id=manifest.artifact_id,
            artifact_type=manifest.artifact_type,
            source_capsule_id=manifest.source_capsule_id,
            payload=payload,
        ),
        *result.artifacts[1:],
    )
    malformed = CapsuleCompilationResult(
        compilation_id=result.compilation_id,
        capsule_id=result.capsule_id,
        status=result.status,
        artifacts=malformed_artifacts,
        warnings=result.warnings,
        errors=result.errors,
        compiled_at=result.compiled_at,
    )

    installation = registry.install(malformed, (entry,))

    assert installation.status is CapsuleAdmissionStatus.REJECTED
    assert registry.capability_count == 0
    assert any("capability registry manifest domain mismatch" in error for error in installation.errors)


def test_governed_capability_registry_rejects_owner_team_mismatch() -> None:
    compiler = DomainCapsuleCompiler(clock=_clock)
    registry = GovernedCapabilityRegistry(clock=_clock, require_certified=False)
    entry = _registry_entry()
    result = compiler.compile(_capsule(), [entry])
    obligation_index = next(
        index
        for index, artifact in enumerate(result.artifacts)
        if artifact.artifact_type == "obligation_template_manifest"
    )
    obligation = result.artifacts[obligation_index]
    payload = dict(obligation.payload)
    payload["owner_team"] = "forged_owner"
    malformed_artifacts = tuple(
        CapsuleCompilerArtifact(
            artifact_id=artifact.artifact_id,
            artifact_type=artifact.artifact_type,
            source_capsule_id=artifact.source_capsule_id,
            payload=payload,
        )
        if index == obligation_index
        else artifact
        for index, artifact in enumerate(result.artifacts)
    )
    malformed = CapsuleCompilationResult(
        compilation_id=result.compilation_id,
        capsule_id=result.capsule_id,
        status=result.status,
        artifacts=malformed_artifacts,
        warnings=result.warnings,
        errors=result.errors,
        compiled_at=result.compiled_at,
    )

    installation = registry.install(malformed, (entry,))

    assert installation.status is CapsuleAdmissionStatus.REJECTED
    assert registry.capability_count == 0
    assert "capability owner team mismatch: crm.update_customer_address has customer_ops, expected forged_owner" in installation.errors


def test_governed_capability_registry_unknown_queries_fail_explicitly() -> None:
    registry = GovernedCapabilityRegistry(clock=_clock)

    try:
        registry.get_capability("missing")
    except RuntimeCoreInvariantError as exc:
        assert str(exc) == "Unknown capability_id"
    else:
        raise AssertionError("missing capability query should fail")

    try:
        registry.installation_for_capsule("missing")
    except RuntimeCoreInvariantError as exc:
        assert str(exc) == "Unknown capsule_id"
    else:
        raise AssertionError("missing capsule query should fail")


def test_command_capability_admission_accepts_installed_typed_intent() -> None:
    compiler = DomainCapsuleCompiler(clock=_clock)
    registry = GovernedCapabilityRegistry(clock=_clock)
    entry = _certified_entry()
    result = compiler.compile(_certified_capsule(), [entry])
    registry.install(result, (entry,))
    gate = CommandCapabilityAdmissionGate(registry=registry, clock=_clock)
    ledger = CommandLedger(clock=_clock, store=InMemoryCommandLedgerStore())
    command = ledger.create_command(
        tenant_id="tenant-1",
        actor_id="identity-1",
        source="web",
        conversation_id="conversation-1",
        idempotency_key="idem-fabric-admit",
        intent="crm.update_customer_address",
        payload={
            "body": "update customer address",
            "skill_intent": {
                "skill": "crm",
                "action": "update_customer_address",
                "params": {"customer_id": "cus-1", "address_id": "addr-1"},
            },
        },
    )
    typed_intent = compile_typed_intent(command)

    decision = gate.admit(command_id=command.command_id, intent_name=typed_intent.name)

    assert typed_intent.name == "crm.update_customer_address"
    assert decision.status is CommandCapabilityAdmissionStatus.ACCEPTED
    assert decision.capability_id == entry.capability_id
    assert decision.domain == "customer_ops"
    assert decision.owner_team == "customer_ops"
    assert decision.evidence_required == ("crm_update_receipt", "before_after_record_hash")


def test_command_capability_admission_audit_survives_store_reload_for_acceptance() -> None:
    compiler = DomainCapsuleCompiler(clock=_clock)
    registry = GovernedCapabilityRegistry(clock=_clock)
    entry = _certified_entry()
    result = compiler.compile(_certified_capsule(), [entry])
    registry.install(result, (entry,))
    gate = CommandCapabilityAdmissionGate(registry=registry, clock=_clock)
    store = InMemoryCommandLedgerStore()
    ledger = CommandLedger(clock=_clock, store=store, capability_admission_gate=gate)
    command = ledger.create_command(
        tenant_id="tenant-1",
        actor_id="identity-1",
        source="web",
        conversation_id="conversation-1",
        idempotency_key="idem-fabric-reload-accepted",
        intent="crm.update_customer_address",
        payload={
            "body": "update customer address",
            "skill_intent": {
                "skill": "crm",
                "action": "update_customer_address",
                "params": {"customer_id": "cus-1", "address_id": "addr-1"},
            },
        },
    )

    ledger.bind_governed_action(command.command_id)
    reloaded = CommandLedger(clock=_clock, store=store)
    audit = reloaded.capability_admission_audit_for(command.command_id)

    assert audit is not None
    assert audit["fabric_configured"] is True
    assert audit["status"] == "accepted"
    assert audit["intent_name"] == "crm.update_customer_address"
    assert audit["capability_id"] == "crm.update_customer_address"
    assert audit["capability_registry_entry"]["capability_id"] == "crm.update_customer_address"
    assert audit["admission_event_hash"]
    assert audit["registry_event_hash"]
    audits = reloaded.capability_admission_audits(tenant_id="tenant-1", status="accepted")
    assert len(audits) == 1
    assert audits[0]["command_id"] == command.command_id


def test_command_capability_admission_rejects_uninstalled_typed_intent() -> None:
    registry = GovernedCapabilityRegistry(clock=_clock)
    gate = CommandCapabilityAdmissionGate(registry=registry, clock=_clock)
    ledger = CommandLedger(clock=_clock, store=InMemoryCommandLedgerStore())
    command = ledger.create_command(
        tenant_id="tenant-1",
        actor_id="identity-1",
        source="web",
        conversation_id="conversation-1",
        idempotency_key="idem-fabric-reject",
        intent="crm.update_customer_address",
        payload={
            "body": "update customer address",
            "skill_intent": {
                "skill": "crm",
                "action": "update_customer_address",
                "params": {"customer_id": "cus-1"},
            },
        },
    )
    typed_intent = compile_typed_intent(command)

    decision = gate.admit(command_id=command.command_id, intent_name=typed_intent.name)

    assert decision.status is CommandCapabilityAdmissionStatus.REJECTED
    assert decision.capability_id == ""
    assert decision.evidence_required == ()
    assert decision.reason == "no installed capability for typed intent"


def test_command_capability_admission_audit_survives_store_reload_for_rejection() -> None:
    registry = GovernedCapabilityRegistry(clock=_clock)
    gate = CommandCapabilityAdmissionGate(registry=registry, clock=_clock)
    store = InMemoryCommandLedgerStore()
    ledger = CommandLedger(clock=_clock, store=store, capability_admission_gate=gate)
    command = ledger.create_command(
        tenant_id="tenant-1",
        actor_id="identity-1",
        source="web",
        conversation_id="conversation-1",
        idempotency_key="idem-fabric-reload-rejected",
        intent="crm.update_customer_address",
        payload={
            "body": "update customer address",
            "skill_intent": {
                "skill": "crm",
                "action": "update_customer_address",
                "params": {"customer_id": "cus-1"},
            },
        },
    )

    try:
        ledger.bind_governed_action(command.command_id)
    except ValueError as exc:
        assert str(exc).startswith("capability fabric admission rejected:")
    else:
        raise AssertionError("uninstalled capability should reject during binding")
    reloaded = CommandLedger(clock=_clock, store=store)
    audit = reloaded.capability_admission_audit_for(command.command_id)

    assert audit is not None
    assert audit["fabric_configured"] is True
    assert audit["command_state"] == "denied"
    assert audit["status"] == "rejected"
    assert audit["intent_name"] == "crm.update_customer_address"
    assert audit["reason"] == "no installed capability for typed intent"
    assert audit["capability_registry_entry"] is None
    assert audit["admission_event_hash"]
    audits = reloaded.capability_admission_audits(tenant_id="tenant-1", status="rejected")
    assert len(audits) == 1
    assert audits[0]["command_id"] == command.command_id


def test_domain_capsule_compiler_is_deterministic_for_fixed_clock() -> None:
    compiler = DomainCapsuleCompiler(clock=_clock)
    first = compiler.compile(_capsule(), [_registry_entry()])
    second = compiler.compile(_capsule(), [_registry_entry()])

    assert first.compilation_id == second.compilation_id
    assert [artifact.artifact_id for artifact in first.artifacts] == [
        artifact.artifact_id for artifact in second.artifacts
    ]
    assert first.to_json_dict() == second.to_json_dict()
