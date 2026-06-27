"""Purpose: verify reusable capability unlock ladder contracts.
Governance scope: local capability maturity ladder, gate-template reuse,
workflow descriptor topology, approval boundary placement, and skill bindings.
Dependencies: capability unlock ladder module, workflow validator, and default
skill catalog.
Invariants:
  - Unlock levels remain consecutive and non-authoritative.
  - Effect-bearing levels require approval, receipts, and rollback where needed.
  - The local developer workflow uses registered default skill descriptors.
  - PR evidence preparation cannot bypass operator review.
"""

from __future__ import annotations

from dataclasses import replace

from mcoi_runtime.contracts.skill import EffectClass
from mcoi_runtime.contracts.workflow import StageType
from mcoi_runtime.core.capability_unlock_ladder import (
    GATE_APPROVAL,
    GATE_CONNECTOR_LEASE,
    GATE_EXECUTION_RECEIPT,
    GATE_OPERATOR_REVIEW,
    GATE_ROLLBACK,
    GATE_VERIFIER,
    GATE_WORKSPACE_WRITE,
    LOCAL_DEVELOPER_WORKFLOW_ID,
    UNLOCK_LADDER_ID,
    build_local_developer_workflow_read_model,
    capability_unlock_admission_profile,
    capability_unlock_profile_errors,
    default_capability_unlock_ladder,
    default_gate_template_ids,
    mullu_local_developer_workflow_v1_descriptor,
    validate_capability_unlock_ladder,
    validate_local_developer_workflow_descriptor,
)
from mcoi_runtime.core.default_skill_catalog import default_skill_descriptors
from mcoi_runtime.core.workflow import WorkflowValidator


def test_capability_unlock_ladder_is_consecutive_and_gate_valid() -> None:
    levels = default_capability_unlock_ladder()
    gate_ids = set(default_gate_template_ids())

    assert validate_capability_unlock_ladder(levels) == ()
    assert tuple(level.level for level in levels) == tuple(range(10))
    assert all(set(level.required_gate_ids) <= gate_ids for level in levels)
    assert levels[0].requires_receipt is False
    assert all(level.requires_receipt for level in levels[1:])


def test_capability_unlock_ladder_effect_boundaries_are_not_unreviewed() -> None:
    levels = {level.level: level for level in default_capability_unlock_ladder()}
    file_write = levels[3]
    pr_creation = levels[5]
    live_probe = levels[7]
    live_action = levels[8]

    assert GATE_WORKSPACE_WRITE in file_write.required_gate_ids
    assert GATE_ROLLBACK in file_write.required_gate_ids
    assert file_write.requires_operator_approval is True
    assert GATE_APPROVAL in pr_creation.required_gate_ids
    assert "pull_request_opened_without_approval" in pr_creation.forbidden_effects
    assert GATE_CONNECTOR_LEASE in live_probe.required_gate_ids
    assert live_probe.requires_live_witness is True
    assert GATE_EXECUTION_RECEIPT in live_action.required_gate_ids
    assert live_action.requires_rollback is True


def test_local_developer_workflow_descriptor_is_structurally_valid() -> None:
    descriptor = mullu_local_developer_workflow_v1_descriptor()
    stage_ids = tuple(stage.stage_id for stage in descriptor.stages)
    stage_types = {stage.stage_id: stage.stage_type for stage in descriptor.stages}

    assert descriptor.workflow_id == LOCAL_DEVELOPER_WORKFLOW_ID
    assert WorkflowValidator().validate(descriptor) == []
    assert stage_ids == (
        "plan_local_change",
        "run_local_change_chain",
        "verify_local_receipt",
        "operator_review_gate",
        "prepare_pr_evidence",
    )
    assert stage_types["operator_review_gate"] is StageType.APPROVAL_GATE
    assert descriptor.stages[-1].predecessors == ("operator_review_gate",)


def test_local_developer_workflow_uses_registered_default_skills() -> None:
    descriptor = mullu_local_developer_workflow_v1_descriptor()
    skill_ids = {descriptor.skill_id for descriptor in default_skill_descriptors()}
    workflow_skill_ids = {
        stage.skill_id
        for stage in descriptor.stages
        if stage.stage_type is StageType.SKILL_EXECUTION
    }

    assert workflow_skill_ids == {
        "agentic_control.coding_governor.v1",
        "software_dev.change_closure.v1",
        "agentic_control.quality_governor.v1",
        "agentic_control.release_governor.v1",
    }
    assert workflow_skill_ids <= skill_ids
    assert None not in workflow_skill_ids


def test_local_developer_workflow_bindings_match_declared_skill_outputs() -> None:
    descriptor = mullu_local_developer_workflow_v1_descriptor()
    skill_outputs = _default_skill_output_keys_by_skill_id()
    stages_by_id = {stage.stage_id: stage for stage in descriptor.stages}
    bindings_by_id = {binding.binding_id: binding for binding in descriptor.bindings}

    for binding in descriptor.bindings:
        source_stage = stages_by_id[binding.source_stage_id]
        if source_stage.stage_type is not StageType.SKILL_EXECUTION:
            continue
        assert source_stage.skill_id is not None
        assert binding.source_output_key in skill_outputs[source_stage.skill_id]

    approval_binding = bindings_by_id["approval_to_pr_evidence"]
    assert approval_binding.source_stage_id == "operator_review_gate"
    assert approval_binding.target_stage_id == "prepare_pr_evidence"
    assert approval_binding.source_output_key == "approval_decision_ref"
    assert GATE_OPERATOR_REVIEW in default_gate_template_ids()


def test_local_developer_workflow_validator_and_read_model_are_valid() -> None:
    descriptor = mullu_local_developer_workflow_v1_descriptor()
    read_model = build_local_developer_workflow_read_model()

    assert validate_local_developer_workflow_descriptor(descriptor) == ()
    assert read_model["read_model_id"] == LOCAL_DEVELOPER_WORKFLOW_ID
    assert read_model["valid"] is True
    assert read_model["approval_stage_id"] == "operator_review_gate"
    assert read_model["external_mutation_allowed"] is False
    assert read_model["stage_count"] == 5
    assert read_model["binding_count"] == 4
    assert read_model["violations"] == ()
    assert read_model["stages"][1]["effect_class"] == "external_write"
    assert read_model["stages"][1]["grants_new_capability_authority"] is False


def test_local_developer_workflow_validation_rejects_topology_drift() -> None:
    descriptor = mullu_local_developer_workflow_v1_descriptor()
    stages = list(descriptor.stages)
    stages[-1] = replace(stages[-1], predecessors=("verify_local_receipt",))
    drifted = replace(descriptor, stages=tuple(stages))

    violations = validate_local_developer_workflow_descriptor(drifted)

    assert "prepare_pr_evidence predecessor binding changed" in violations
    assert "local developer workflow handoff bindings changed" not in violations
    assert len(violations) == 1


def test_local_developer_workflow_validation_rejects_skill_authority_drift() -> None:
    skills = {descriptor.skill_id: descriptor for descriptor in default_skill_descriptors()}
    write_skill = skills["software_dev.change_closure.v1"]
    skills["software_dev.change_closure.v1"] = replace(
        write_skill,
        effect_class=EffectClass.EXTERNAL_READ,
        metadata={**write_skill.metadata, "approval_expected": False},
    )

    violations = validate_local_developer_workflow_descriptor(
        mullu_local_developer_workflow_v1_descriptor(),
        skills,
    )

    assert "run_local_change_chain must remain the only write-bearing skill stage" in violations
    assert "run_local_change_chain approval expectation missing" in violations
    assert len(violations) == 2


def test_unlock_admission_profile_resolves_default_capability_metadata() -> None:
    from gateway.capability_fabric import load_default_capability_entries

    entries = {entry.capability_id: entry for entry in load_default_capability_entries()}
    payment_profile = capability_unlock_admission_profile(entries["financial.send_payment"])
    document_profile = capability_unlock_admission_profile(entries["document.extract_text"])

    assert payment_profile is not None
    assert payment_profile.ladder_id == UNLOCK_LADDER_ID
    assert payment_profile.level == 8
    assert payment_profile.level_id == "L8"
    assert payment_profile.gate_template_ids == (
        GATE_CONNECTOR_LEASE,
        GATE_APPROVAL,
        GATE_VERIFIER,
        GATE_EXECUTION_RECEIPT,
        GATE_ROLLBACK,
    )
    assert payment_profile.requires_operator_approval is True
    assert payment_profile.requires_live_witness is True
    assert document_profile is not None
    assert document_profile.level == 0
    assert document_profile.requires_receipt is False


def test_unlock_profile_errors_detect_gate_mismatch() -> None:
    from dataclasses import replace

    from gateway.capability_fabric import load_default_capability_entries

    payment_entry = next(
        entry for entry in load_default_capability_entries() if entry.capability_id == "financial.send_payment"
    )
    malformed_entry = replace(
        payment_entry,
        metadata={
            **payment_entry.metadata,
            "unlock_ladder": {
                "ladder_id": UNLOCK_LADDER_ID,
                "level": 8,
                "level_id": "L8",
                "gate_template_ids": ("evidence_intake_gate",),
            },
        },
    )

    assert capability_unlock_profile_errors(malformed_entry) == (
        "unlock_ladder_gate_template_ids_mismatch",
    )


def _default_skill_output_keys_by_skill_id() -> dict[str, set[str]]:
    output_keys_by_skill_id: dict[str, set[str]] = {}
    for descriptor in default_skill_descriptors():
        output_keys: set[str] = set()
        for step in descriptor.steps:
            output_keys.update(step.output_keys)
        output_keys_by_skill_id[descriptor.skill_id] = output_keys
    return output_keys_by_skill_id
