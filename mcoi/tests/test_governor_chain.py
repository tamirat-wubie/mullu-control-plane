"""Purpose: verify read-only governor-chain cohesion.

Governance scope: policy, decision, design, coding, quality, release, and
runtime governor workflow composition.
Dependencies: governor-chain core, default skill catalog, and workflow runtime.
Invariants:
  - The chain uses existing read-only governor skills only.
  - Stage order and handoff bindings are explicit and deterministic.
  - Writable, missing, blocked, or reordered governors fail validation.
  - Runtime execution passes the governed packet through declared bindings.
"""

from __future__ import annotations

from dataclasses import replace

from mcoi_runtime.contracts.skill import EffectClass
from mcoi_runtime.contracts.workflow import (
    StageExecutionResult,
    StageStatus,
    StageType,
    WorkflowDescriptor,
    WorkflowStatus,
)
from mcoi_runtime.core.default_skill_catalog import default_skill_descriptors
from mcoi_runtime.core.governor_chain import (
    CANONICAL_GOVERNOR_CHAIN,
    GOVERNOR_CHAIN_INPUT_KEY,
    GOVERNOR_CHAIN_OUTPUT_KEY,
    GOVERNOR_CHAIN_WORKFLOW_ID,
    build_governor_chain_descriptor,
    build_governor_chain_read_model,
    canonical_governor_chain_skill_ids,
    validate_governor_chain_descriptor,
)
from mcoi_runtime.core.workflow import WorkflowEngine


NOW = "2026-06-01T00:00:00+00:00"


class RecordingGovernorExecutor:
    """Minimal read-only executor used to prove workflow handoff behavior."""

    def __init__(self) -> None:
        self.executed: list[str] = []
        self.inputs_by_stage: dict[str, dict[str, object]] = {}

    def execute_stage(
        self,
        stage_id: str,
        stage_type: str,
        skill_id: str | None,
        inputs: dict[str, object],
    ) -> StageExecutionResult:
        self.executed.append(stage_id)
        self.inputs_by_stage[stage_id] = dict(inputs)
        return StageExecutionResult(
            stage_id=stage_id,
            status=StageStatus.COMPLETED,
            output={
                GOVERNOR_CHAIN_OUTPUT_KEY: f"{stage_id}:governance-packet",
                "skill_id": skill_id,
                "stage_type": stage_type,
            },
            started_at=NOW,
            completed_at=NOW,
        )


def test_governor_chain_descriptor_orders_existing_read_only_governors() -> None:
    descriptor = build_governor_chain_descriptor(created_at=NOW)
    stage_skill_ids = tuple(stage.skill_id for stage in descriptor.stages)
    stage_ids = tuple(stage.stage_id for stage in descriptor.stages)

    assert descriptor.workflow_id == GOVERNOR_CHAIN_WORKFLOW_ID
    assert descriptor.created_at == NOW
    assert stage_skill_ids == canonical_governor_chain_skill_ids()
    assert stage_ids == tuple(stage.stage_id for stage in CANONICAL_GOVERNOR_CHAIN)
    assert all(stage.stage_type is StageType.SKILL_EXECUTION for stage in descriptor.stages)
    assert descriptor.stages[0].predecessors == ()
    assert descriptor.stages[-1].predecessors == ("release_governor",)
    assert len(descriptor.bindings) == len(descriptor.stages) - 1
    assert validate_governor_chain_descriptor(descriptor) == ()


def test_governor_chain_read_model_preserves_handoff_and_authority_boundary() -> None:
    read_model = build_governor_chain_read_model(created_at=NOW)

    assert read_model["read_only"] is True
    assert read_model["governed"] is True
    assert read_model["valid"] is True
    assert read_model["violations"] == ()
    assert read_model["stage_count"] == 7
    assert read_model["binding_count"] == 6
    assert read_model["handoff"] == "governance_packet_ref -> upstream_governance_packet_ref"
    assert read_model["stages"][0]["input_key"] == ""
    assert read_model["stages"][1]["input_key"] == GOVERNOR_CHAIN_INPUT_KEY
    assert all(stage["effect_class"] == EffectClass.EXTERNAL_READ.value for stage in read_model["stages"])
    assert all(stage["grants_new_capability_authority"] is False for stage in read_model["stages"])


def test_governor_chain_validation_fails_closed_for_missing_or_writable_skill() -> None:
    descriptors = list(default_skill_descriptors())
    descriptor_by_id = {descriptor.skill_id: descriptor for descriptor in descriptors}
    descriptor_by_id.pop("agentic_control.release_governor.v1")
    descriptor_by_id["agentic_control.decision_governor.v1"] = replace(
        descriptor_by_id["agentic_control.decision_governor.v1"],
        effect_class=EffectClass.EXTERNAL_WRITE,
    )

    violations = validate_governor_chain_descriptor(
        build_governor_chain_descriptor(created_at=NOW),
        descriptor_by_id,
    )

    assert len(violations) == 2
    assert "agentic_control.release_governor.v1 missing from skill catalog" in violations
    assert "agentic_control.decision_governor.v1 must remain read-only" in violations


def test_governor_chain_validation_rejects_reordered_stage_graph() -> None:
    descriptor = build_governor_chain_descriptor(created_at=NOW)
    reordered = WorkflowDescriptor(
        workflow_id=descriptor.workflow_id,
        name=descriptor.name,
        description=descriptor.description,
        stages=(
            descriptor.stages[1],
            descriptor.stages[0],
            *descriptor.stages[2:],
        ),
        bindings=descriptor.bindings,
        created_at=descriptor.created_at,
    )

    violations = validate_governor_chain_descriptor(reordered)

    assert "governor chain stage order changed" in violations
    assert "policy_governor stage identifier changed" in violations
    assert "decision_governor stage identifier changed" in violations
    assert "policy_governor predecessor binding changed" in violations


def test_governor_chain_runtime_passes_governance_packet_by_binding() -> None:
    descriptor = build_governor_chain_descriptor(created_at=NOW)
    engine = WorkflowEngine(clock=lambda: NOW)
    executor = RecordingGovernorExecutor()

    record = engine.start_workflow(descriptor)
    while record.status is WorkflowStatus.RUNNING:
        record = engine.execute_next_stage(descriptor, record, executor)

    expected_stage_ids = [stage.stage_id for stage in CANONICAL_GOVERNOR_CHAIN]
    assert record.status is WorkflowStatus.COMPLETED
    assert executor.executed == expected_stage_ids
    assert len(record.stage_results) == len(expected_stage_ids)
    assert GOVERNOR_CHAIN_INPUT_KEY not in executor.inputs_by_stage["policy_governor"]
    assert executor.inputs_by_stage["decision_governor"][GOVERNOR_CHAIN_INPUT_KEY] == (
        "policy_governor:governance-packet"
    )
    assert executor.inputs_by_stage["runtime_governor"][GOVERNOR_CHAIN_INPUT_KEY] == (
        "release_governor:governance-packet"
    )
