"""Tests for default governed skill descriptor catalog.

Purpose: verify bootstrap-admitted workflow descriptors do not create raw authority.
Governance scope: default SkillDescriptor catalog, registry admission, and bootstrap binding.
Dependencies: default skill catalog, skill contracts, bootstrap runtime.
Invariants:
  - Default skills are candidate descriptors only.
  - Default skills compose existing capability ids and grant no new capability authority.
  - Bootstrap installs the catalog deterministically.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from mcoi_runtime.app.bootstrap import bootstrap_runtime
from mcoi_runtime.contracts.skill import EffectClass, SkillLifecycle
from mcoi_runtime.core import default_skill_catalog as catalog_module
from mcoi_runtime.core.default_skill_catalog import (
    default_skill_descriptors,
    register_default_skill_descriptors,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.skills import SkillRegistry


EXPECTED_SKILL_IDS = (
    "finance.approval_packet.v1",
    "document.intake_summary.v1",
    "software_dev.change_closure.v1",
    "deployment.witness_publication.v1",
    "adapter.evidence_closure.v1",
    "workflow.governed_composition.v1",
    "incident.rollback_recovery.v1",
    "release.pr_handoff_closure.v1",
    "telemetry.monitoring_triage.v1",
    "agentic_control.autonomous_operations.v1",
)


def test_default_skill_catalog_names_required_workflows() -> None:
    descriptors = default_skill_descriptors()
    skill_ids = tuple(descriptor.skill_id for descriptor in descriptors)

    assert skill_ids == EXPECTED_SKILL_IDS
    assert all(descriptor.lifecycle is SkillLifecycle.CANDIDATE for descriptor in descriptors)
    assert all(descriptor.metadata["grants_new_capability_authority"] is False for descriptor in descriptors)
    assert all(descriptor.verification_strength.value == "mandatory" for descriptor in descriptors)


def test_default_skill_descriptors_have_governed_boundaries() -> None:
    descriptors = default_skill_descriptors()

    assert all(descriptor.preconditions for descriptor in descriptors)
    assert all(descriptor.postconditions for descriptor in descriptors)
    assert all(descriptor.steps for descriptor in descriptors)
    assert all(descriptor.provider_requirements for descriptor in descriptors)
    assert all(step.action_type for descriptor in descriptors for step in descriptor.steps)


def test_default_skill_effect_classes_match_strongest_workflow_effect() -> None:
    descriptors = {descriptor.skill_id: descriptor for descriptor in default_skill_descriptors()}

    assert descriptors["finance.approval_packet.v1"].effect_class is EffectClass.EXTERNAL_READ
    assert descriptors["document.intake_summary.v1"].effect_class is EffectClass.EXTERNAL_READ
    assert descriptors["software_dev.change_closure.v1"].effect_class is EffectClass.EXTERNAL_WRITE
    assert descriptors["deployment.witness_publication.v1"].effect_class is EffectClass.EXTERNAL_WRITE
    assert descriptors["adapter.evidence_closure.v1"].effect_class is EffectClass.EXTERNAL_READ
    assert descriptors["workflow.governed_composition.v1"].effect_class is EffectClass.EXTERNAL_WRITE
    assert descriptors["incident.rollback_recovery.v1"].effect_class is EffectClass.EXTERNAL_WRITE
    assert descriptors["release.pr_handoff_closure.v1"].effect_class is EffectClass.EXTERNAL_WRITE
    assert descriptors["telemetry.monitoring_triage.v1"].effect_class is EffectClass.EXTERNAL_READ
    assert descriptors["agentic_control.autonomous_operations.v1"].effect_class is EffectClass.EXTERNAL_WRITE
    assert all(
        descriptor.metadata["approval_expected"] is True
        for descriptor in descriptors.values()
        if descriptor.effect_class is EffectClass.EXTERNAL_WRITE
    )


def test_default_skill_provider_requirements_match_step_boundaries() -> None:
    descriptors = default_skill_descriptors()

    assert descriptors
    assert all(
        tuple(
            sorted(
                {
                    step.provider_class_required
                    for step in descriptor.steps
                    if step.provider_class_required is not None
                }
            )
        )
        == tuple(sorted(descriptor.provider_requirements))
        for descriptor in descriptors
    )
    assert all(
        step.provider_class_required in descriptor.provider_requirements
        for descriptor in descriptors
        for step in descriptor.steps
        if step.provider_class_required is not None
    )


def test_agentic_control_skill_plans_telemetry_triage_before_code_release_and_evidence() -> None:
    descriptor = next(
        descriptor
        for descriptor in default_skill_descriptors()
        if descriptor.skill_id == "agentic_control.autonomous_operations.v1"
    )
    steps = {step.step_id: step for step in descriptor.steps}
    action_order = tuple(step.action_type for step in descriptor.steps)
    step_order = tuple(step.step_id for step in descriptor.steps)

    assert "agentic_control.code_change.plan" in action_order
    assert "agentic_control.telemetry_triage.plan" in action_order
    assert "agentic_control.interrogation.plan" in action_order
    assert "agentic_control.self_audit.refine" in action_order
    assert "agentic_control.memory_admission.plan" in action_order
    assert "agentic_control.incident_recovery.plan" in action_order
    assert "agentic_control.release_handoff.plan" in action_order
    assert all(
        step_order.index(dependency) < step_order.index(step.step_id)
        for step in descriptor.steps
        for dependency in step.depends_on
    )
    assert action_order.index("agentic_control.verification.plan") < action_order.index(
        "agentic_control.interrogation.plan"
    )
    assert action_order.index("agentic_control.interrogation.plan") < action_order.index(
        "agentic_control.self_audit.refine"
    )
    assert action_order.index("agentic_control.self_audit.refine") < action_order.index(
        "agentic_control.memory_admission.plan"
    )
    assert action_order.index("agentic_control.memory_admission.plan") < action_order.index(
        "agentic_control.incident_recovery.plan"
    )
    assert action_order.index("agentic_control.incident_recovery.plan") < action_order.index(
        "agentic_control.telemetry_triage.plan"
    )
    assert action_order.index("agentic_control.telemetry_triage.plan") < action_order.index(
        "agentic_control.code_change.plan"
    )
    assert action_order.index("agentic_control.code_change.plan") < action_order.index(
        "agentic_control.release_handoff.plan"
    )
    assert action_order.index("agentic_control.release_handoff.plan") < action_order.index(
        "agentic_control.evidence.append"
    )
    assert steps["plan_interrogation"].depends_on == ("plan_verification",)
    assert steps["refine_weakness_gaps"].depends_on == ("plan_interrogation",)
    assert steps["plan_memory_admission"].depends_on == ("refine_weakness_gaps",)
    assert steps["plan_incident_recovery"].depends_on == ("refine_weakness_gaps", "plan_memory_admission")
    assert steps["plan_telemetry_triage"].depends_on == (
        "plan_verification",
        "refine_weakness_gaps",
        "plan_incident_recovery",
    )
    assert steps["plan_code_change"].depends_on == ("plan_verification", "plan_telemetry_triage")
    assert steps["plan_release_handoff"].depends_on == ("plan_code_change",)
    assert steps["append_evidence"].depends_on == ("plan_release_handoff",)
    assert steps["plan_interrogation"].input_bindings["verification_plan_ref"] == (
        "plan_verification.verification_plan_ref"
    )
    assert steps["refine_weakness_gaps"].input_bindings["verification_plan_ref"] == (
        "plan_verification.verification_plan_ref"
    )
    assert steps["refine_weakness_gaps"].input_bindings["interrogation_plan_ref"] == (
        "plan_interrogation.interrogation_plan_ref"
    )
    assert steps["plan_memory_admission"].input_bindings["refinement_plan_ref"] == (
        "refine_weakness_gaps.refinement_plan_ref"
    )
    assert steps["plan_incident_recovery"].input_bindings["refinement_plan_ref"] == (
        "refine_weakness_gaps.refinement_plan_ref"
    )
    assert steps["plan_incident_recovery"].input_bindings["memory_admission_plan_ref"] == (
        "plan_memory_admission.memory_admission_plan_ref"
    )
    assert steps["plan_telemetry_triage"].input_bindings["verification_plan_ref"] == (
        "plan_verification.verification_plan_ref"
    )
    assert steps["plan_telemetry_triage"].input_bindings["refinement_plan_ref"] == (
        "refine_weakness_gaps.refinement_plan_ref"
    )
    assert steps["plan_telemetry_triage"].input_bindings["incident_recovery_plan_ref"] == (
        "plan_incident_recovery.incident_recovery_plan_ref"
    )
    assert steps["plan_code_change"].input_bindings["telemetry_triage_plan_ref"] == (
        "plan_telemetry_triage.telemetry_triage_plan_ref"
    )
    assert steps["plan_release_handoff"].input_bindings["code_change_plan_ref"] == (
        "plan_code_change.code_change_plan_ref"
    )
    assert steps["append_evidence"].input_bindings["code_change_plan_ref"] == (
        "plan_code_change.code_change_plan_ref"
    )
    assert steps["append_evidence"].input_bindings["interrogation_plan_ref"] == (
        "plan_interrogation.interrogation_plan_ref"
    )
    assert steps["append_evidence"].input_bindings["refinement_plan_ref"] == (
        "refine_weakness_gaps.refinement_plan_ref"
    )
    assert steps["append_evidence"].input_bindings["memory_admission_plan_ref"] == (
        "plan_memory_admission.memory_admission_plan_ref"
    )
    assert steps["append_evidence"].input_bindings["incident_recovery_plan_ref"] == (
        "plan_incident_recovery.incident_recovery_plan_ref"
    )
    assert steps["append_evidence"].input_bindings["telemetry_triage_plan_ref"] == (
        "plan_telemetry_triage.telemetry_triage_plan_ref"
    )
    assert steps["append_evidence"].input_bindings["release_handoff_plan_ref"] == (
        "plan_release_handoff.release_handoff_plan_ref"
    )


def test_register_default_skill_descriptors_is_idempotent_for_identical_catalog() -> None:
    registry = SkillRegistry()

    first = register_default_skill_descriptors(registry)
    second = register_default_skill_descriptors(registry)

    assert tuple(descriptor.skill_id for descriptor in first) == EXPECTED_SKILL_IDS
    assert tuple(descriptor.skill_id for descriptor in second) == EXPECTED_SKILL_IDS
    assert registry.size == len(EXPECTED_SKILL_IDS)
    assert first == second


def test_register_default_skill_descriptors_rejects_conflicting_existing_id() -> None:
    registry = SkillRegistry()
    conflicting = default_skill_descriptors()[0]
    registry.register(
        conflicting.__class__(
            skill_id=conflicting.skill_id,
            name="Conflicting descriptor",
            skill_class=conflicting.skill_class,
            effect_class=conflicting.effect_class,
            determinism_class=conflicting.determinism_class,
            trust_class=conflicting.trust_class,
            verification_strength=conflicting.verification_strength,
            lifecycle=conflicting.lifecycle,
            preconditions=conflicting.preconditions,
            postconditions=conflicting.postconditions,
            steps=conflicting.steps,
            provider_requirements=conflicting.provider_requirements,
            description=conflicting.description,
            confidence=conflicting.confidence,
            metadata=conflicting.metadata,
        )
    )

    with pytest.raises(RuntimeCoreInvariantError, match="default skill descriptor conflict"):
        register_default_skill_descriptors(registry)

    assert registry.size == 1
    assert registry.get("finance.approval_packet.v1").name == "Conflicting descriptor"
    assert registry.get("document.intake_summary.v1") is None


def test_register_default_skill_descriptors_rejects_provider_boundary_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    broken = replace(default_skill_descriptors()[0], provider_requirements=())
    monkeypatch.setattr(catalog_module, "default_skill_descriptors", lambda: (broken,))
    registry = SkillRegistry()

    with pytest.raises(RuntimeCoreInvariantError, match="provider boundary mismatch"):
        register_default_skill_descriptors(registry)

    assert registry.size == 0
    assert registry.get("finance.approval_packet.v1") is None
    assert broken.skill_id == "finance.approval_packet.v1"


def test_register_default_skill_descriptors_rejects_external_write_without_approval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    descriptor = next(
        descriptor
        for descriptor in default_skill_descriptors()
        if descriptor.skill_id == "incident.rollback_recovery.v1"
    )
    broken = replace(
        descriptor,
        metadata={**descriptor.metadata, "approval_expected": False},
    )
    monkeypatch.setattr(catalog_module, "default_skill_descriptors", lambda: (broken,))
    registry = SkillRegistry()

    with pytest.raises(RuntimeCoreInvariantError, match="approval boundary missing"):
        register_default_skill_descriptors(registry)

    assert registry.size == 0
    assert registry.get("incident.rollback_recovery.v1") is None
    assert broken.effect_class is EffectClass.EXTERNAL_WRITE


def test_bootstrap_installs_default_skill_catalog() -> None:
    runtime = bootstrap_runtime(clock=lambda: "2026-05-27T00:00:00+00:00")

    listed_ids = tuple(descriptor.skill_id for descriptor in runtime.skill_registry.list_skills())

    assert listed_ids == tuple(sorted(EXPECTED_SKILL_IDS))
    assert runtime.skill_registry.size == len(EXPECTED_SKILL_IDS)
    assert runtime.skill_registry.get("software_dev.change_closure.v1").metadata["risk_floor"] == "high"
    assert runtime.skill_registry.get("finance.approval_packet.v1").metadata["grants_new_capability_authority"] is False
    assert runtime.skill_registry.get("deployment.witness_publication.v1").metadata["approval_expected"] is True
    assert runtime.skill_registry.get("workflow.governed_composition.v1").metadata["approval_expected"] is True
    assert runtime.skill_registry.get("incident.rollback_recovery.v1").metadata["risk_floor"] == "critical"
    assert runtime.skill_registry.get("release.pr_handoff_closure.v1").metadata["approval_expected"] is True
    assert runtime.skill_registry.get("telemetry.monitoring_triage.v1").metadata["risk_floor"] == "medium"
    assert runtime.skill_registry.get("agentic_control.autonomous_operations.v1").metadata["risk_floor"] == "high"
