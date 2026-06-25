"""Purpose: verify default autonomous capability catalog compilation.
Governance scope: MCOI app-layer local autonomous request capability metadata.
Dependencies: autonomous capability catalog, operator loop, local bootstrap.
Invariants: default catalog compiles deterministic local plans without per-step prompts.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from mcoi_runtime.adapters.executor_base import ExecutionRequest
from mcoi_runtime.app.autonomous_capabilities import (
    compile_default_autonomous_request_episode,
    default_autonomous_capability_catalog,
    default_autonomous_request_plan_compiler,
)
from mcoi_runtime.app.autonomous_request import (
    AutonomousRequestAutomationState,
    AutonomousRequestExecutor,
    AutonomousRequestIntent,
)
from mcoi_runtime.app.bootstrap import bootstrap_runtime
from mcoi_runtime.app.operator_loop import OperatorLoop
from mcoi_runtime.contracts.execution import EffectRecord, ExecutionOutcome, ExecutionResult
from mcoi_runtime.contracts.solver_outcome import SolverOutcome
from mcoi_runtime.contracts.workflow import StageType


@dataclass
class FakeExecutor:
    calls: int = 0
    argv_history: tuple[tuple[str, ...], ...] = ()

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        self.calls += 1
        self.argv_history = self.argv_history + (tuple(request.argv),)
        return ExecutionResult(
            execution_id=request.execution_id,
            goal_id=request.goal_id,
            status=ExecutionOutcome.SUCCEEDED,
            actual_effects=(EffectRecord(name="local_catalog_step", details={"argv": list(request.argv)}),),
            assumed_effects=(),
            started_at="2026-06-25T12:00:00+00:00",
            finished_at="2026-06-25T12:00:01+00:00",
            metadata={"adapter": "fake"},
        )


def _loop(executor: FakeExecutor) -> OperatorLoop:
    runtime = bootstrap_runtime(
        clock=lambda: "2026-06-25T12:00:00+00:00",
        executors={"shell_command": executor},
        observers={},
    )
    return OperatorLoop(runtime)


def _intent(*, bindings: dict[str, str] | None = None) -> AutonomousRequestIntent:
    return AutonomousRequestIntent(
        episode_id="episode-default-catalog",
        subject_id="operator-1",
        goal_id="goal-autonomous-request",
        capability_ids=("local.apply",),
        bindings={
            "target": "workspace",
            "objective": "prepare local change",
            "change": "apply local patch",
        }
        if bindings is None
        else bindings,
    )


def test_default_catalog_compiles_apply_dependency_chain_without_prompt() -> None:
    executor = FakeExecutor()
    loop = _loop(executor)
    episode = compile_default_autonomous_request_episode(_intent())

    receipt = AutonomousRequestExecutor(loop).run_episode(episode)

    assert episode.plan is not None
    assert tuple(step.stage_id for step in episode.plan.steps) == (
        "stage-local.inspect",
        "stage-local.plan",
        "stage-local.apply",
    )
    assert tuple(request.bindings for request in episode.requests) == (
        {"target": "workspace"},
        {"objective": "prepare local change"},
        {"change": "apply local patch"},
    )
    assert executor.calls == 3
    assert executor.argv_history[0][-1] == "workspace"
    assert executor.argv_history[1][-1] == "prepare local change"
    assert executor.argv_history[2][-1] == "apply local patch"
    assert executor.argv_history[0][-2] == "import sys; print('inspect:' + sys.argv[1])"
    assert executor.argv_history[1][-2] == "import sys; print('plan:' + sys.argv[1])"
    assert executor.argv_history[2][-2] == "import sys; print('apply:' + sys.argv[1])"
    assert receipt.solver_outcome == SolverOutcome.SOLVED_UNVERIFIED.value
    assert receipt.automation_state == AutonomousRequestAutomationState.SETTLED_WITHOUT_PROMPT.value
    assert receipt.prompt_count == 0
    assert receipt.planned_stage_count == 3
    assert receipt.blocked_dependency_count == 0

    descriptor = episode.to_workflow_descriptor(
        workflow_id="workflow-default-catalog",
        created_at="2026-06-25T12:00:00+00:00",
    )
    assert tuple(stage.stage_id for stage in descriptor.stages) == (
        "stage-local.inspect",
        "stage-local.plan",
        "stage-local.apply",
    )
    assert tuple(stage.stage_type for stage in descriptor.stages) == (
        StageType.SKILL_EXECUTION,
        StageType.SKILL_EXECUTION,
        StageType.SKILL_EXECUTION,
    )
    assert tuple(stage.predecessors for stage in descriptor.stages) == (
        (),
        ("stage-local.inspect",),
        ("stage-local.plan",),
    )


def test_default_catalog_passes_binding_values_as_arguments() -> None:
    executor = FakeExecutor()
    loop = _loop(executor)
    episode = compile_default_autonomous_request_episode(
        _intent(
            bindings={
                "target": "workspace's branch",
                "objective": "plan; do not execute",
                "change": "patch with \"quoted\" text",
            }
        )
    )

    receipt = AutonomousRequestExecutor(loop).run_episode(episode)

    assert executor.calls == 3
    assert executor.argv_history[0][-1] == "workspace's branch"
    assert executor.argv_history[1][-1] == "plan; do not execute"
    assert executor.argv_history[2][-1] == 'patch with "quoted" text'
    assert "workspace's branch" not in executor.argv_history[0][-2]
    assert "plan; do not execute" not in executor.argv_history[1][-2]
    assert 'patch with "quoted" text' not in executor.argv_history[2][-2]
    assert receipt.solver_outcome == SolverOutcome.SOLVED_UNVERIFIED.value


def test_default_catalog_returns_independent_catalog_mapping() -> None:
    first_catalog = dict(default_autonomous_capability_catalog())
    first_catalog.pop("local.inspect")

    second_catalog = default_autonomous_capability_catalog()

    assert "local.inspect" in second_catalog
    assert "local.plan" in second_catalog
    assert "local.apply" in second_catalog


def test_default_catalog_compiler_rejects_missing_required_binding() -> None:
    compiler = default_autonomous_request_plan_compiler()

    with pytest.raises(Exception, match="capability required bindings are missing"):
        compiler.compile_episode(
            _intent(
                bindings={
                    "target": "workspace",
                    "objective": "prepare local change",
                }
            )
        )
