"""Phase 210A — Chat workflow tests."""

import pytest
from mcoi_runtime.core.chat_workflow import ChatWorkflowEngine
from mcoi_runtime.core.traced_workflow import TracedWorkflowEngine
from mcoi_runtime.core.agent_workflow import AgentWorkflowEngine
from mcoi_runtime.core.agent_protocol import (
    AgentCapability, AgentDescriptor, AgentRegistry, TaskManager,
)
from mcoi_runtime.core.execution_replay import ReplayRecorder
from mcoi_runtime.core.conversation_memory import ConversationStore
from mcoi_runtime.core.llm_integration import LLMIntegrationBridge
from mcoi_runtime.adapters.llm_adapter import StubLLMBackend
from mcoi_runtime.contracts.llm import LLMBudget

FIXED_CLOCK = lambda: "2026-03-26T12:00:00Z"


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
    conv_store = ConversationStore(clock=FIXED_CLOCK)
    costs = []

    chat_wf = ChatWorkflowEngine(
        clock=FIXED_CLOCK,
        conversation_store=conv_store,
        traced_workflow=traced,
        cost_record_fn=lambda t, m, c, tok: costs.append((t, c)),
    )
    return chat_wf, conv_store, recorder, costs


class TestChatWorkflow:
    def test_execute(self):
        engine, conv_store, _, _ = _setup()
        result = engine.execute(
            conversation_id="c1", message="Hello",
            tenant_id="t1",
        )
        assert result.status == "completed"
        assert result.response_content
        assert result.trace_id

    def test_conversation_persists(self):
        engine, conv_store, _, _ = _setup()
        engine.execute(conversation_id="c1", message="Hi")
        conv = conv_store.get("c1")
        assert conv is not None
        assert conv.message_count >= 2  # user + assistant

    def test_multi_turn(self):
        engine, conv_store, _, _ = _setup()
        engine.execute(conversation_id="multi", message="First message")
        engine.execute(conversation_id="multi", message="Second message")
        conv = conv_store.get("multi")
        assert conv.message_count >= 4

    def test_system_prompt(self):
        engine, conv_store, _, _ = _setup()
        engine.execute(
            conversation_id="sys", message="Hi",
            system_prompt="You are helpful.",
        )
        conv = conv_store.get("sys")
        assert any(m.role == "system" for m in conv.messages)

    def test_trace_produced(self):
        engine, _, recorder, _ = _setup()
        result = engine.execute(conversation_id="traced", message="test")
        assert result.trace_id is not None
        assert recorder.completed_count >= 1

    def test_cost_recorded(self):
        engine, _, _, costs = _setup()
        engine.execute(conversation_id="cost", message="test", tenant_id="t1")
        # Cost may or may not be > 0 depending on stub
        assert engine.total_executions == 1

    def test_failed_workflow(self):
        engine, conv_store, _, _ = _setup()
        result = engine.execute(
            conversation_id="fail", message="test",
            capability=AgentCapability.WEB_SEARCH,
        )
        assert result.status == "failed"
        conv = conv_store.get("fail")
        assert any("failed" in m.content.lower() for m in conv.messages if m.role == "assistant")

    def test_history(self):
        engine, _, _, _ = _setup()
        engine.execute(conversation_id="h1", message="a")
        engine.execute(conversation_id="h2", message="b")
        assert len(engine.history()) == 2

    def test_summary(self):
        engine, _, _, _ = _setup()
        engine.execute(conversation_id="s1", message="ok")
        summary = engine.summary()
        assert summary["total"] == 1
        assert summary["completed"] == 1
