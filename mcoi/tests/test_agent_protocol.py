"""Phase 203A — Agent protocol tests."""

import threading
import time

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
        with pytest.raises(ValueError, match="^agent already registered$") as exc_info:
            reg.register(agent)
        assert "a1" not in str(exc_info.value)

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

    def test_list_agents_snapshot_stable_under_concurrent_register(self):
        iter_started = threading.Event()

        class _CoordinatedAgentDict(dict[str, AgentDescriptor]):
            def values(self):  # type: ignore[override]
                first = True
                for value in super().values():
                    if first:
                        first = False
                        iter_started.set()
                        time.sleep(0.05)
                    yield value

        reg = AgentRegistry()
        reg._agents = _CoordinatedAgentDict()
        reg.register(AgentDescriptor(agent_id="a1", name="A1", capabilities=(AgentCapability.LLM_COMPLETION,)))

        def _register() -> None:
            assert iter_started.wait(timeout=1.0)
            reg.register(AgentDescriptor(agent_id="a2", name="A2", capabilities=(AgentCapability.CODE_EXECUTION,)))

        worker = threading.Thread(target=_register)
        worker.start()
        snapshot = reg.list_agents()
        worker.join(timeout=1.0)

        assert not worker.is_alive()
        assert [agent.agent_id for agent in snapshot] == ["a1"]
        assert [agent.agent_id for agent in reg.list_agents()] == ["a1", "a2"]


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
        with pytest.raises(ValueError, match="^task already exists$") as exc_info:
            mgr.submit(task)
        assert "t1" not in str(exc_info.value)

    def test_assign_valid(self):
        mgr = self._setup()
        mgr.submit(TaskSpec(task_id="t1", description="test", required_capability=AgentCapability.LLM_COMPLETION, payload={}))
        assert mgr.assign("t1", "llm-agent") is True
        assert mgr.get_status("t1") == TaskStatus.ASSIGNED

    def test_assign_wrong_capability(self):
        mgr = self._setup()
        mgr.submit(TaskSpec(task_id="t1", description="test", required_capability=AgentCapability.LLM_COMPLETION, payload={}))
        with pytest.raises(ValueError, match="^assigned agent lacks required capability$") as exc_info:
            mgr.assign("t1", "code-agent")
        assert "code-agent" not in str(exc_info.value)
        assert AgentCapability.LLM_COMPLETION.value not in str(exc_info.value)

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

    def test_assign_unknown_task_is_bounded(self):
        mgr = self._setup()
        with pytest.raises(ValueError, match="^task unavailable$") as exc_info:
            mgr.assign("missing-task", "llm-agent")
        assert "missing-task" not in str(exc_info.value)

    def test_assign_unknown_agent_is_bounded(self):
        mgr = self._setup()
        mgr.submit(TaskSpec(task_id="t1", description="test", required_capability=AgentCapability.LLM_COMPLETION, payload={}))
        with pytest.raises(ValueError, match="^agent unavailable$") as exc_info:
            mgr.assign("t1", "ghost-agent")
        assert "ghost-agent" not in str(exc_info.value)

    def test_complete_unknown_task_is_bounded(self):
        mgr = self._setup()
        with pytest.raises(ValueError, match="^task unavailable$") as exc_info:
            mgr.complete("missing-task", {"answer": "42"})
        assert "missing-task" not in str(exc_info.value)

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

    def test_pending_tasks_snapshot_stable_under_concurrent_submit(self):
        iter_started = threading.Event()

        class _CoordinatedStatusDict(dict[str, TaskStatus]):
            def items(self):  # type: ignore[override]
                first = True
                for item in super().items():
                    if first:
                        first = False
                        iter_started.set()
                        time.sleep(0.05)
                    yield item

        mgr = self._setup()
        mgr._statuses = _CoordinatedStatusDict()
        mgr.submit(TaskSpec(task_id="t1", description="a", required_capability=AgentCapability.LLM_COMPLETION, payload={}))

        def _submit() -> None:
            assert iter_started.wait(timeout=1.0)
            mgr.submit(TaskSpec(task_id="t2", description="b", required_capability=AgentCapability.CODE_EXECUTION, payload={}))

        worker = threading.Thread(target=_submit)
        worker.start()
        snapshot = mgr.pending_tasks()
        worker.join(timeout=1.0)

        assert not worker.is_alive()
        assert [task.task_id for task in snapshot] == ["t1"]
        assert sorted(task.task_id for task in mgr.pending_tasks()) == ["t1", "t2"]
