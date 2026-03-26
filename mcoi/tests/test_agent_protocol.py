"""Phase 203A — Agent protocol tests."""

import pytest
from mcoi_runtime.core.agent_protocol import (
    AgentCapability, AgentDescriptor, AgentRegistry,
    TaskManager, TaskSpec, TaskResult, TaskStatus,
)

FIXED_CLOCK = lambda: "2026-03-26T12:00:00Z"


class TestAgentRegistry:
    def test_register(self):
        reg = AgentRegistry()
        agent = AgentDescriptor(agent_id="a1", name="Agent 1", capabilities=(AgentCapability.LLM_COMPLETION,))
        reg.register(agent)
        assert reg.count == 1

    def test_duplicate_register_raises(self):
        reg = AgentRegistry()
        agent = AgentDescriptor(agent_id="a1", name="A1", capabilities=(AgentCapability.LLM_COMPLETION,))
        reg.register(agent)
        with pytest.raises(ValueError, match="already registered"):
            reg.register(agent)

    def test_find_capable(self):
        reg = AgentRegistry()
        reg.register(AgentDescriptor(agent_id="a1", name="A1", capabilities=(AgentCapability.LLM_COMPLETION,)))
        reg.register(AgentDescriptor(agent_id="a2", name="A2", capabilities=(AgentCapability.CODE_EXECUTION,)))
        result = reg.find_capable(AgentCapability.LLM_COMPLETION)
        assert len(result) == 1
        assert result[0].agent_id == "a1"

    def test_disabled_not_found(self):
        reg = AgentRegistry()
        reg.register(AgentDescriptor(agent_id="a1", name="A1", capabilities=(AgentCapability.LLM_COMPLETION,), enabled=False))
        assert reg.find_capable(AgentCapability.LLM_COMPLETION) == []

    def test_unregister(self):
        reg = AgentRegistry()
        reg.register(AgentDescriptor(agent_id="a1", name="A1", capabilities=(AgentCapability.LLM_COMPLETION,)))
        assert reg.unregister("a1") is True
        assert reg.count == 0

    def test_list_agents(self):
        reg = AgentRegistry()
        reg.register(AgentDescriptor(agent_id="a2", name="A2", capabilities=(AgentCapability.LLM_COMPLETION,)))
        reg.register(AgentDescriptor(agent_id="a1", name="A1", capabilities=(AgentCapability.CODE_EXECUTION,)))
        agents = reg.list_agents()
        assert agents[0].agent_id == "a1"  # Sorted


class TestTaskManager:
    def _setup(self):
        reg = AgentRegistry()
        reg.register(AgentDescriptor(
            agent_id="llm-agent", name="LLM Agent",
            capabilities=(AgentCapability.LLM_COMPLETION, AgentCapability.TOOL_USE),
        ))
        reg.register(AgentDescriptor(
            agent_id="code-agent", name="Code Agent",
            capabilities=(AgentCapability.CODE_EXECUTION,),
        ))
        mgr = TaskManager(clock=FIXED_CLOCK, registry=reg)
        return mgr

    def test_submit_task(self):
        mgr = self._setup()
        task = TaskSpec(task_id="t1", description="test", required_capability=AgentCapability.LLM_COMPLETION, payload={})
        mgr.submit(task)
        assert mgr.get_status("t1") == TaskStatus.PENDING

    def test_duplicate_submit_raises(self):
        mgr = self._setup()
        task = TaskSpec(task_id="t1", description="test", required_capability=AgentCapability.LLM_COMPLETION, payload={})
        mgr.submit(task)
        with pytest.raises(ValueError):
            mgr.submit(task)

    def test_assign_valid(self):
        mgr = self._setup()
        mgr.submit(TaskSpec(task_id="t1", description="test", required_capability=AgentCapability.LLM_COMPLETION, payload={}))
        assert mgr.assign("t1", "llm-agent") is True
        assert mgr.get_status("t1") == TaskStatus.ASSIGNED

    def test_assign_wrong_capability(self):
        mgr = self._setup()
        mgr.submit(TaskSpec(task_id="t1", description="test", required_capability=AgentCapability.LLM_COMPLETION, payload={}))
        with pytest.raises(ValueError, match="lacks capability"):
            mgr.assign("t1", "code-agent")

    def test_auto_assign(self):
        mgr = self._setup()
        mgr.submit(TaskSpec(task_id="t1", description="test", required_capability=AgentCapability.CODE_EXECUTION, payload={}))
        agent_id = mgr.auto_assign("t1")
        assert agent_id == "code-agent"
        assert mgr.get_status("t1") == TaskStatus.ASSIGNED

    def test_start(self):
        mgr = self._setup()
        mgr.submit(TaskSpec(task_id="t1", description="test", required_capability=AgentCapability.LLM_COMPLETION, payload={}))
        mgr.assign("t1", "llm-agent")
        assert mgr.start("t1") is True
        assert mgr.get_status("t1") == TaskStatus.RUNNING

    def test_complete(self):
        mgr = self._setup()
        mgr.submit(TaskSpec(task_id="t1", description="test", required_capability=AgentCapability.LLM_COMPLETION, payload={}))
        mgr.assign("t1", "llm-agent")
        mgr.start("t1")
        result = mgr.complete("t1", {"answer": "42"}, duration_ms=150.0)
        assert result.status == TaskStatus.COMPLETED
        assert result.output["answer"] == "42"
        assert result.result_hash

    def test_fail(self):
        mgr = self._setup()
        mgr.submit(TaskSpec(task_id="t1", description="test", required_capability=AgentCapability.LLM_COMPLETION, payload={}))
        result = mgr.fail("t1", "timeout")
        assert result.status == TaskStatus.FAILED
        assert result.error == "timeout"

    def test_cancel(self):
        mgr = self._setup()
        mgr.submit(TaskSpec(task_id="t1", description="test", required_capability=AgentCapability.LLM_COMPLETION, payload={}))
        assert mgr.cancel("t1") is True
        assert mgr.get_status("t1") == TaskStatus.CANCELLED

    def test_cannot_cancel_running(self):
        mgr = self._setup()
        mgr.submit(TaskSpec(task_id="t1", description="test", required_capability=AgentCapability.LLM_COMPLETION, payload={}))
        mgr.assign("t1", "llm-agent")
        mgr.start("t1")
        assert mgr.cancel("t1") is False

    def test_pending_tasks(self):
        mgr = self._setup()
        mgr.submit(TaskSpec(task_id="t1", description="a", required_capability=AgentCapability.LLM_COMPLETION, payload={}))
        mgr.submit(TaskSpec(task_id="t2", description="b", required_capability=AgentCapability.CODE_EXECUTION, payload={}))
        assert len(mgr.pending_tasks()) == 2

    def test_summary(self):
        mgr = self._setup()
        mgr.submit(TaskSpec(task_id="t1", description="a", required_capability=AgentCapability.LLM_COMPLETION, payload={}))
        summary = mgr.summary()
        assert summary["total_tasks"] == 1
        assert summary["agents"] == 2
