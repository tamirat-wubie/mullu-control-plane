"""Purpose: verify foundational contract constructors match schema shape.

Governance scope: old shared plan, environment, and execution contracts.
Dependencies: mcoi_runtime.contracts foundational modules and pytest.
Invariants: runtime constructors reject shapes that shared JSON schemas reject.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.environment import (
    EnvironmentFingerprint,
    PlatformDescriptor,
    RuntimeDescriptor,
)
from mcoi_runtime.contracts.execution import EffectRecord, ExecutionOutcome, ExecutionResult
from mcoi_runtime.contracts.plan import Plan, PlanItem


def test_plan_item_dependencies_reject_scalar_shape() -> None:
    item = PlanItem(item_id="step-2", description="child", depends_on=["step-1"])  # type: ignore[arg-type]

    assert item.depends_on == ("step-1",)
    assert isinstance(item.depends_on, tuple)
    assert item.to_json_dict()["depends_on"] == ["step-1"]

    with pytest.raises(ValueError, match="depends_on must be an array"):
        PlanItem(item_id="step-2", description="child", depends_on="step-1")  # type: ignore[arg-type]


def test_plan_dependency_graph_rejects_invalid_edges() -> None:
    base = PlanItem(item_id="step-1", description="root")
    child = PlanItem(item_id="step-2", description="child", depends_on=("step-1",))

    plan = Plan(
        plan_id="plan-1",
        goal_id="goal-1",
        state_hash="state",
        registry_hash="registry",
        items=(base, child),
    )

    assert len(plan.items) == 2
    assert plan.items[1].depends_on == ("step-1",)
    assert plan.to_json_dict()["items"][1]["depends_on"] == ["step-1"]

    with pytest.raises(ValueError, match="unique item_id"):
        Plan(
            plan_id="plan-1",
            goal_id="goal-1",
            state_hash="state",
            registry_hash="registry",
            items=(base, PlanItem(item_id="step-1", description="duplicate")),
        )
    with pytest.raises(ValueError, match="declared item_id"):
        Plan(
            plan_id="plan-1",
            goal_id="goal-1",
            state_hash="state",
            registry_hash="registry",
            items=(PlanItem(item_id="step-2", description="child", depends_on=("missing",)),),
        )
    with pytest.raises(ValueError, match="dependency cycles"):
        Plan(
            plan_id="plan-1",
            goal_id="goal-1",
            state_hash="state",
            registry_hash="registry",
            items=(
                PlanItem(item_id="step-1", description="root", depends_on=("step-2",)),
                PlanItem(item_id="step-2", description="child", depends_on=("step-1",)),
            ),
        )


def test_environment_fingerprint_rejects_descriptor_shape_drift() -> None:
    fingerprint = EnvironmentFingerprint(
        fingerprint_id="env-1",
        captured_at="2026-05-13T12:00:00+00:00",
        digest="sha256:abc",
        platform=PlatformDescriptor(os="windows", architecture="x64"),
        runtime=RuntimeDescriptor(name="python", version="3.13"),
    )

    assert fingerprint.platform is not None
    assert fingerprint.runtime is not None
    assert fingerprint.to_json_dict()["platform"]["os"] == "windows"

    with pytest.raises(ValueError, match="PlatformDescriptor"):
        EnvironmentFingerprint(
            fingerprint_id="env-1",
            captured_at="2026-05-13T12:00:00+00:00",
            digest="sha256:abc",
            platform={"os": "windows"},  # type: ignore[arg-type]
        )
    with pytest.raises(ValueError, match="RuntimeDescriptor"):
        EnvironmentFingerprint(
            fingerprint_id="env-1",
            captured_at="2026-05-13T12:00:00+00:00",
            digest="sha256:abc",
            runtime={"name": "python"},  # type: ignore[arg-type]
        )


def test_execution_result_rejects_effect_shape_drift() -> None:
    result = ExecutionResult(
        execution_id="exec-1",
        goal_id="goal-1",
        status=ExecutionOutcome.SUCCEEDED,
        actual_effects=[EffectRecord(name="witness")],  # type: ignore[arg-type]
        assumed_effects=[],
        started_at="2026-05-13T12:00:00+00:00",
        finished_at="2026-05-13T12:00:01+00:00",
    )

    assert result.actual_effects == (EffectRecord(name="witness"),)
    assert result.assumed_effects == ()
    assert result.to_json_dict()["actual_effects"][0]["name"] == "witness"

    with pytest.raises(ValueError, match="actual_effects must be an array"):
        ExecutionResult(
            execution_id="exec-1",
            goal_id="goal-1",
            status=ExecutionOutcome.SUCCEEDED,
            actual_effects="witness",  # type: ignore[arg-type]
            assumed_effects=(),
            started_at="2026-05-13T12:00:00+00:00",
            finished_at="2026-05-13T12:00:01+00:00",
        )
    with pytest.raises(ValueError, match=r"actual_effects\[0\] must be an EffectRecord"):
        ExecutionResult(
            execution_id="exec-1",
            goal_id="goal-1",
            status=ExecutionOutcome.SUCCEEDED,
            actual_effects=("witness",),  # type: ignore[arg-type]
            assumed_effects=(),
            started_at="2026-05-13T12:00:00+00:00",
            finished_at="2026-05-13T12:00:01+00:00",
        )
    with pytest.raises(ValueError, match=r"assumed_effects\[0\] must be an EffectRecord"):
        ExecutionResult(
            execution_id="exec-1",
            goal_id="goal-1",
            status=ExecutionOutcome.SUCCEEDED,
            actual_effects=(),
            assumed_effects=("witness",),  # type: ignore[arg-type]
            started_at="2026-05-13T12:00:00+00:00",
            finished_at="2026-05-13T12:00:01+00:00",
        )
