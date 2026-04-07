"""Workflow DAG Executor Tests."""

import pytest
from mcoi_runtime.core.workflow_dag import (
    StepStatus,
    WorkflowEngine,
    WorkflowStep,
    detect_cycle,
    topological_order,
)


def _engine():
    return WorkflowEngine(clock=lambda: "2026-04-07T12:00:00Z")


def _executor(action, params):
    return {"executed": action, "params": params}


class TestCycleDetection:
    def test_no_cycle(self):
        steps = [
            WorkflowStep(step_id="a", name="A", action="a"),
            WorkflowStep(step_id="b", name="B", action="b", depends_on=frozenset({"a"})),
        ]
        assert detect_cycle(steps) is None

    def test_direct_cycle(self):
        steps = [
            WorkflowStep(step_id="a", name="A", action="a", depends_on=frozenset({"b"})),
            WorkflowStep(step_id="b", name="B", action="b", depends_on=frozenset({"a"})),
        ]
        assert detect_cycle(steps) is not None

    def test_indirect_cycle(self):
        steps = [
            WorkflowStep(step_id="a", name="A", action="a", depends_on=frozenset({"c"})),
            WorkflowStep(step_id="b", name="B", action="b", depends_on=frozenset({"a"})),
            WorkflowStep(step_id="c", name="C", action="c", depends_on=frozenset({"b"})),
        ]
        assert detect_cycle(steps) is not None

    def test_no_deps(self):
        steps = [
            WorkflowStep(step_id="a", name="A", action="a"),
            WorkflowStep(step_id="b", name="B", action="b"),
        ]
        assert detect_cycle(steps) is None


class TestTopologicalOrder:
    def test_linear_chain(self):
        steps = [
            WorkflowStep(step_id="a", name="A", action="a"),
            WorkflowStep(step_id="b", name="B", action="b", depends_on=frozenset({"a"})),
            WorkflowStep(step_id="c", name="C", action="c", depends_on=frozenset({"b"})),
        ]
        levels = topological_order(steps)
        assert levels == [["a"], ["b"], ["c"]]

    def test_parallel_steps(self):
        steps = [
            WorkflowStep(step_id="a", name="A", action="a"),
            WorkflowStep(step_id="b", name="B", action="b"),
            WorkflowStep(step_id="c", name="C", action="c", depends_on=frozenset({"a", "b"})),
        ]
        levels = topological_order(steps)
        assert levels[0] == ["a", "b"]  # Both at level 0
        assert levels[1] == ["c"]

    def test_diamond_dag(self):
        steps = [
            WorkflowStep(step_id="start", name="S", action="s"),
            WorkflowStep(step_id="left", name="L", action="l", depends_on=frozenset({"start"})),
            WorkflowStep(step_id="right", name="R", action="r", depends_on=frozenset({"start"})),
            WorkflowStep(step_id="end", name="E", action="e", depends_on=frozenset({"left", "right"})),
        ]
        levels = topological_order(steps)
        assert len(levels) == 3


class TestWorkflowDefinition:
    def test_define_valid(self):
        e = _engine()
        wf = e.define(
            tenant_id="t1", name="test",
            steps=[WorkflowStep(step_id="s1", name="A", action="a")],
        )
        assert wf.name == "test"
        assert wf.step_count == 1

    def test_define_with_cycle_rejected(self):
        e = _engine()
        with pytest.raises(ValueError, match="cycle"):
            e.define(tenant_id="t1", name="bad", steps=[
                WorkflowStep(step_id="a", name="A", action="a", depends_on=frozenset({"b"})),
                WorkflowStep(step_id="b", name="B", action="b", depends_on=frozenset({"a"})),
            ])

    def test_duplicate_step_ids_rejected(self):
        e = _engine()
        with pytest.raises(ValueError, match="duplicate"):
            e.define(tenant_id="t1", name="bad", steps=[
                WorkflowStep(step_id="a", name="A", action="a"),
                WorkflowStep(step_id="a", name="B", action="b"),
            ])

    def test_unknown_dependency_rejected(self):
        e = _engine()
        with pytest.raises(ValueError, match="unknown"):
            e.define(tenant_id="t1", name="bad", steps=[
                WorkflowStep(step_id="a", name="A", action="a", depends_on=frozenset({"nonexistent"})),
            ])


class TestWorkflowExecution:
    def test_simple_execution(self):
        e = _engine()
        wf = e.define(tenant_id="t1", name="simple", steps=[
            WorkflowStep(step_id="s1", name="A", action="greet"),
        ])
        result = e.execute(wf.workflow_id, executor=_executor)
        assert result.status == "completed"
        assert result.steps_completed == 1

    def test_chain_execution(self):
        e = _engine()
        wf = e.define(tenant_id="t1", name="chain", steps=[
            WorkflowStep(step_id="s1", name="Create", action="create"),
            WorkflowStep(step_id="s2", name="Notify", action="notify", depends_on=frozenset({"s1"})),
            WorkflowStep(step_id="s3", name="Activate", action="activate", depends_on=frozenset({"s2"})),
        ])
        result = e.execute(wf.workflow_id, executor=_executor)
        assert result.status == "completed"
        assert result.steps_completed == 3

    def test_failed_step_skips_dependents(self):
        def failing_executor(action, params):
            if action == "create":
                raise RuntimeError("db error")
            return {"ok": True}

        e = _engine()
        wf = e.define(tenant_id="t1", name="fail", steps=[
            WorkflowStep(step_id="s1", name="Create", action="create"),
            WorkflowStep(step_id="s2", name="Notify", action="notify", depends_on=frozenset({"s1"})),
        ])
        result = e.execute(wf.workflow_id, executor=failing_executor)
        assert result.status == "failed"
        assert result.steps_failed == 1
        assert result.steps_skipped == 1
        assert result.steps["s2"].status == StepStatus.SKIPPED

    def test_diamond_execution(self):
        e = _engine()
        wf = e.define(tenant_id="t1", name="diamond", steps=[
            WorkflowStep(step_id="start", name="Start", action="init"),
            WorkflowStep(step_id="left", name="Left", action="left", depends_on=frozenset({"start"})),
            WorkflowStep(step_id="right", name="Right", action="right", depends_on=frozenset({"start"})),
            WorkflowStep(step_id="end", name="End", action="finish", depends_on=frozenset({"left", "right"})),
        ])
        result = e.execute(wf.workflow_id, executor=_executor)
        assert result.status == "completed"
        assert result.steps_completed == 4

    def test_partial_failure(self):
        call_count = [0]
        def selective_executor(action, params):
            call_count[0] += 1
            if action == "left":
                raise ValueError("left failed")
            return {"ok": True}

        e = _engine()
        wf = e.define(tenant_id="t1", name="partial", steps=[
            WorkflowStep(step_id="start", name="S", action="init"),
            WorkflowStep(step_id="left", name="L", action="left", depends_on=frozenset({"start"})),
            WorkflowStep(step_id="right", name="R", action="right", depends_on=frozenset({"start"})),
            WorkflowStep(step_id="end", name="E", action="finish", depends_on=frozenset({"left", "right"})),
        ])
        result = e.execute(wf.workflow_id, executor=selective_executor)
        assert result.steps_failed == 1  # left
        assert result.steps_skipped == 1  # end (depends on left)
        assert result.steps_completed == 2  # start + right

    def test_nonexistent_workflow_raises(self):
        e = _engine()
        with pytest.raises(ValueError, match="not found"):
            e.execute("wf-nonexistent", executor=_executor)

    def test_stub_executor(self):
        e = _engine()
        wf = e.define(tenant_id="t1", name="stub", steps=[
            WorkflowStep(step_id="s1", name="A", action="test"),
        ])
        result = e.execute(wf.workflow_id)  # No executor — uses stub
        assert result.status == "completed"
        assert result.steps["s1"].result == {"action": "test", "status": "stub"}

    def test_to_dict(self):
        e = _engine()
        wf = e.define(tenant_id="t1", name="test", steps=[
            WorkflowStep(step_id="s1", name="A", action="a"),
        ])
        result = e.execute(wf.workflow_id)
        d = result.to_dict()
        assert d["status"] == "completed"
        assert len(d["steps"]) == 1


class TestEngineManagement:
    def test_get_definition(self):
        e = _engine()
        wf = e.define(tenant_id="t1", name="test", steps=[
            WorkflowStep(step_id="s1", name="A", action="a"),
        ])
        assert e.get_definition(wf.workflow_id) is not None
        assert e.get_definition("nonexistent") is None

    def test_list_definitions(self):
        e = _engine()
        e.define(tenant_id="t1", name="a", steps=[WorkflowStep(step_id="s1", name="A", action="a")])
        e.define(tenant_id="t2", name="b", steps=[WorkflowStep(step_id="s1", name="B", action="b")])
        assert len(e.list_definitions()) == 2
        assert len(e.list_definitions(tenant_id="t1")) == 1

    def test_summary(self):
        e = _engine()
        wf = e.define(tenant_id="t1", name="test", steps=[
            WorkflowStep(step_id="s1", name="A", action="a"),
        ])
        e.execute(wf.workflow_id)
        s = e.summary()
        assert s["definitions"] == 1
        assert s["executions"] == 1
