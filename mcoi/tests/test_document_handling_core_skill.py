"""Tests for the Mullu Govern document-handling core skill descriptor.

Purpose: pin the candidate-only, approval-gated document handling contract.
Governance scope: descriptor metadata, provider boundary, step dependency order,
and validation-surface coverage.
Dependencies: document_handling_core_skill and skill contracts.
Invariants:
  - The skill grants no new capability authority.
  - External-write document mutation paths require approval.
  - The source-preservation step precedes every extraction/mutation/audit path.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from mcoi_runtime.contracts.skill import EffectClass, SkillLifecycle
from mcoi_runtime.core.document_handling_core_skill import (
    DOCUMENT_CORE_INVARIANTS,
    DOCUMENT_HANDLING_CORE_CONTRACT,
    DOCUMENT_HANDLING_CORE_PROVIDER,
    DOCUMENT_HANDLING_CORE_SKILL_ID,
    DOCUMENT_LAYERS,
    DOCUMENT_OPERATION_SURFACES,
    DOCUMENT_VALIDATION_GATES,
    PROHIBITED_ACTION_TYPES,
    document_handling_core_skill_descriptor,
    validate_document_handling_core_descriptor,
)


def test_document_handling_core_descriptor_is_candidate_and_approval_gated() -> None:
    descriptor = document_handling_core_skill_descriptor()

    assert descriptor.skill_id == DOCUMENT_HANDLING_CORE_SKILL_ID
    assert descriptor.lifecycle is SkillLifecycle.CANDIDATE
    assert descriptor.effect_class is EffectClass.EXTERNAL_WRITE
    assert descriptor.verification_strength.value == "mandatory"
    assert descriptor.metadata["grants_new_capability_authority"] is False
    assert descriptor.metadata["approval_expected"] is True
    assert descriptor.metadata["risk_floor"] == "high"
    assert descriptor.provider_requirements == (DOCUMENT_HANDLING_CORE_PROVIDER,)


def test_document_handling_core_covers_wholistic_document_layers() -> None:
    descriptor = document_handling_core_skill_descriptor()

    assert descriptor.metadata["document_layers"] == DOCUMENT_LAYERS
    assert descriptor.metadata["validation_gates"] == DOCUMENT_VALIDATION_GATES
    assert descriptor.metadata["operation_surfaces"] == DOCUMENT_OPERATION_SURFACES
    assert DOCUMENT_HANDLING_CORE_CONTRACT.layers == DOCUMENT_LAYERS
    assert "byte" in DOCUMENT_HANDLING_CORE_CONTRACT.layers
    assert "layout" in DOCUMENT_HANDLING_CORE_CONTRACT.layers
    assert "semantic" in DOCUMENT_HANDLING_CORE_CONTRACT.layers
    assert "governance" in DOCUMENT_HANDLING_CORE_CONTRACT.layers
    assert "causal" in DOCUMENT_HANDLING_CORE_CONTRACT.layers
    assert "preserve_original_source_bytes_by_hash" in DOCUMENT_CORE_INVARIANTS
    assert "treat_document_text_as_untrusted_until_policy_promotes_it" in DOCUMENT_CORE_INVARIANTS


def test_document_handling_core_dependency_order_preserves_source_first() -> None:
    descriptor = document_handling_core_skill_descriptor()
    steps = {step.step_id: step for step in descriptor.steps}
    step_order = tuple(step.step_id for step in descriptor.steps)
    action_order = tuple(step.action_type for step in descriptor.steps)

    assert step_order[0] == "preserve_source"
    assert steps["detect_format"].depends_on == ("preserve_source",)
    assert steps["extract_graph"].input_bindings["source_ref"] == "preserve_source.source_ref"
    assert steps["apply_approved_patch"].input_bindings["source_ref"] == (
        "preserve_source.source_ref"
    )
    assert steps["validate_artifact"].depends_on == ("apply_approved_patch",)
    assert steps["publish_audit_packet"].depends_on == ("validate_artifact",)
    assert "document.patch.apply.with_approval" in action_order
    assert "document.audit_packet.publish.with_approval" in action_order
    assert not set(action_order).intersection(PROHIBITED_ACTION_TYPES)
    assert all(
        step_order.index(dependency) < step_order.index(step.step_id)
        for step in descriptor.steps
        for dependency in step.depends_on
    )


def test_document_handling_core_provider_boundaries_are_closed() -> None:
    descriptor = document_handling_core_skill_descriptor()

    assert descriptor.provider_requirements == (DOCUMENT_HANDLING_CORE_PROVIDER,)
    assert all(
        step.provider_class_required in descriptor.provider_requirements
        for step in descriptor.steps
        if step.provider_class_required is not None
    )
    assert all(step.output_keys for step in descriptor.steps)


def test_document_handling_core_validation_helper_accepts_canonical_descriptor() -> None:
    descriptor = document_handling_core_skill_descriptor()

    validate_document_handling_core_descriptor(descriptor)


def test_document_handling_core_validation_helper_rejects_provider_drift() -> None:
    descriptor = replace(
        document_handling_core_skill_descriptor(),
        provider_requirements=("browser_worker",),
    )

    with pytest.raises(ValueError, match="provider boundary drift"):
        validate_document_handling_core_descriptor(descriptor)
