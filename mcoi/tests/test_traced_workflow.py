"""Phase 208B — Traced workflow tests."""

from mcoi_runtime.core.traced_workflow import TracedWorkflowEngine
from mcoi_runtime.core.agent_workflow import AgentWorkflowEngine
from mcoi_runtime.core.agent_protocol import (
    AgentCapability, AgentDescriptor, AgentRegistry, TaskManager,
)
from mcoi_runtime.core.execution_replay import ReplayRecorder
from mcoi_runtime.core.llm_integration import LLMIntegrationBridge
from mcoi_runtime.adapters.llm_adapter import StubLLMBackend
from mcoi_runtime.contracts.llm import LLMBudget

def FIXED_CLOCK():
    return "2026-03-26T12:00:00Z"


def _setup():
    reg = AgentRegistry()
    reg.register(AgentDescriptor(
        agent_id="llm-agent", name="LLM",
        capabilities=(AgentCapability.LLM_COMPLETION,),
    ))
    task_mgr = TaskManager(clock=FIXED_CLOCK, registry=reg)
    bridge = LLMIntegrationBridge(clock=FIXED_CLOCK, default_backend=StubLLMBackend())
    bridge.register_budget(LLMBudget(budget_id="default", tenant_id="system", max_cost=100.0))

    workflow = AgentWorkflowEngine(
        clock=FIXED_CLOCK, task_manager=task_mgr,
        llm_complete_fn=lambda p, b: bridge.complete(p, budget_id=b),
    )
    recorder = ReplayRecorder(clock=FIXED_CLOCK)
    traced = TracedWorkflowEngine(workflow_engine=workflow, replay_recorder=recorder)
    return traced, recorder


def _setup_with_recorder(recorder):
    traced, _ = _setup()
    return (
        TracedWorkflowEngine(
            workflow_engine=traced.workflow_engine,
            replay_recorder=recorder,
        ),
        recorder,
    )


class StartFailingReplayRecorder(ReplayRecorder):
    def start_trace(self, trace_id):
        raise RuntimeError("raw-start-secret")


class FrameFailingReplayRecorder(ReplayRecorder):
    def record_frame(self, *args, **kwargs):
        raise RuntimeError("raw-frame-secret")


class CompleteFailingReplayRecorder(ReplayRecorder):
    def complete_trace(self, trace_id):
        raise RuntimeError("raw-complete-secret")


class TestTracedWorkflow:
    def test_execute_produces_trace(self):
        traced, recorder = _setup()
        result, trace = traced.execute(
            task_id="t1", description="test",
            capability=AgentCapability.LLM_COMPLETION, payload={},
        )
        assert result.status == "completed"
        assert trace is not None
        assert trace.trace_id == "trace-t1"
        assert len(trace.frames) >= 3  # input + steps + output

    def test_trace_has_frames(self):
        traced, recorder = _setup()
        _, trace = traced.execute(
            task_id="t1", description="test",
            capability=AgentCapability.LLM_COMPLETION, payload={},
        )
        ops = [f.operation for f in trace.frames]
        assert "workflow.input" in ops
        assert "workflow.output" in ops

    def test_trace_stored_in_recorder(self):
        traced, recorder = _setup()
        traced.execute(
            task_id="t1", description="test",
            capability=AgentCapability.LLM_COMPLETION, payload={},
        )
        assert recorder.completed_count == 1

    def test_failed_workflow_still_traced(self):
        traced, recorder = _setup()
        result, trace = traced.execute(
            task_id="t1", description="test",
            capability=AgentCapability.WEB_SEARCH, payload={},
        )
        assert result.status == "failed"
        assert trace is not None

    def test_multiple_traces(self):
        traced, recorder = _setup()
        traced.execute(task_id="t1", description="a", capability=AgentCapability.LLM_COMPLETION, payload={})
        traced.execute(task_id="t2", description="b", capability=AgentCapability.LLM_COMPLETION, payload={})
        assert recorder.completed_count == 2

    def test_start_trace_failure_is_counted_and_workflow_runs(self):
        traced, recorder = _setup_with_recorder(StartFailingReplayRecorder(clock=FIXED_CLOCK))
        result, trace = traced.execute(
            task_id="t1", description="test",
            capability=AgentCapability.LLM_COMPLETION, payload={},
        )
        assert result.status == "completed"
        assert trace is None
        assert traced.trace_recording_failures == 1
        assert traced.last_trace_recording_error == "trace recording failed (RuntimeError)"
        assert "raw-start-secret" not in traced.last_trace_recording_error
        assert recorder.active_count == 0

    def test_frame_failure_is_counted_and_partial_trace_discarded(self):
        traced, recorder = _setup_with_recorder(FrameFailingReplayRecorder(clock=FIXED_CLOCK))
        result, trace = traced.execute(
            task_id="t1", description="test",
            capability=AgentCapability.LLM_COMPLETION, payload={},
        )
        assert result.status == "completed"
        assert trace is None
        assert traced.trace_recording_failures == 1
        assert traced.last_trace_recording_error == "trace recording failed (RuntimeError)"
        assert recorder.active_count == 0
        assert recorder.completed_count == 0

    def test_complete_failure_is_counted_and_partial_trace_discarded(self):
        traced, recorder = _setup_with_recorder(CompleteFailingReplayRecorder(clock=FIXED_CLOCK))
        result, trace = traced.execute(
            task_id="t1", description="test",
            capability=AgentCapability.LLM_COMPLETION, payload={},
        )
        assert result.status == "completed"
        assert trace is None
        assert traced.trace_recording_failures == 1
        assert traced.last_trace_recording_error == "trace recording failed (RuntimeError)"
        assert recorder.active_count == 0
        assert recorder.completed_count == 0
