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

import pytest

from mcoi_runtime.app.bootstrap import bootstrap_runtime
from mcoi_runtime.contracts.skill import EffectClass, SkillLifecycle
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
    assert descriptors["software_dev.change_closure.v1"].metadata["approval_expected"] is True


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


def test_bootstrap_installs_default_skill_catalog() -> None:
    runtime = bootstrap_runtime(clock=lambda: "2026-05-27T00:00:00+00:00")

    listed_ids = tuple(descriptor.skill_id for descriptor in runtime.skill_registry.list_skills())

    assert listed_ids == tuple(sorted(EXPECTED_SKILL_IDS))
    assert runtime.skill_registry.size == len(EXPECTED_SKILL_IDS)
    assert runtime.skill_registry.get("software_dev.change_closure.v1").metadata["risk_floor"] == "high"
    assert runtime.skill_registry.get("finance.approval_packet.v1").metadata["grants_new_capability_authority"] is False
