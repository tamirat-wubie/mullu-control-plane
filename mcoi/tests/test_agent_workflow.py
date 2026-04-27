"""Phase 204B — Agent workflow end-to-end tests."""

import pytest
from mcoi_runtime.core.agent_workflow import AgentWorkflowEngine, WorkflowResult
from mcoi_runtime.core.agent_protocol import (
    AgentCapability, AgentDescriptor, AgentRegistry, TaskManager,
)
from mcoi_runtime.core.audit_trail import AuditTrail
from mcoi_runtime.core.webhook_system import WebhookManager, WebhookSubscription
from mcoi_runtime.core.llm_integration import LLMIntegrationBridge
from mcoi_runtime.adapters.llm_adapter import StubLLMBackend
from mcoi_runtime.contracts.llm import LLMBudget

FIXED_CLOCK = lambda: "2026-03-26T12:00:00Z"


def _setup(with_llm=True, with_webhook=True, with_audit=True, llm_fn_override=None):
    reg = AgentRegistry()
    reg.register(AgentDescriptor(
        agent_id="llm-agent", name="LLM Agent",
        capabilities=(AgentCapability.LLM_COMPLETION, AgentCapability.TOOL_USE),
    ))
    reg.register(AgentDescriptor(
        agent_id="code-agent", name="Code Agent",
        capabilities=(AgentCapability.CODE_EXECUTION,),
    ))
    task_mgr = TaskManager(clock=FIXED_CLOCK, registry=reg)

    llm_fn = None
    if with_llm:
        bridge = LLMIntegrationBridge(clock=FIXED_CLOCK, default_backend=StubLLMBackend())
        bridge.register_budget(LLMBudget(budget_id="default", tenant_id="system", max_cost=100.0))
        llm_fn = lambda prompt, budget_id: bridge.complete(prompt, budget_id=budget_id)
    if llm_fn_override is not None:
        llm_fn = llm_fn_override

    webhook_mgr = None
    if with_webhook:
        webhook_mgr = WebhookManager(clock=FIXED_CLOCK)
        webhook_mgr.subscribe(WebhookSubscription(
            subscription_id="s1", tenant_id="t1",
            url="https://example.com/hook", events=("task.completed", "task.failed"),
        ))

    audit = AuditTrail(clock=FIXED_CLOCK) if with_audit else None

    engine = AgentWorkflowEngine(
        clock=FIXED_CLOCK,
        task_manager=task_mgr,
        llm_complete_fn=llm_fn,
        webhook_manager=webhook_mgr,
        audit_trail=audit,
    )
    return engine, audit, webhook_mgr


class TestAgentWorkflowEngine:
    def test_successful_workflow(self):
        engine, audit, webhook = _setup()
        result = engine.execute(
            task_id="t1", description="test prompt",
            capability=AgentCapability.LLM_COMPLETION,
            payload={"prompt": "hello"},
            tenant_id="t1",
        )
        assert result.status == "completed"
        assert result.agent_id == "llm-agent"
        assert result.output["content"]
        assert len(result.steps) >= 5

    def test_workflow_without_llm(self):
        engine, _, _ = _setup(with_llm=False)
        result = engine.execute(
            task_id="t1", description="test",
            capability=AgentCapability.LLM_COMPLETION,
            payload={}, tenant_id="t1",
        )
        assert result.status == "completed"
        assert result.output["content"] == "stub result"
        assert "test" not in result.output["content"]
        assert any(s.step_name == "llm_invoke" and s.status == "skipped" for s in result.steps)

    def test_workflow_no_capable_agent(self):
        engine, audit, webhook = _setup()
        result = engine.execute(
            task_id="t1", description="test",
            capability=AgentCapability.WEB_SEARCH,  # No agent has this
            payload={}, tenant_id="t1",
        )
        assert result.status == "failed"
        assert result.error == "no capable agent available"
        assert AgentCapability.WEB_SEARCH.value not in result.error
        assert audit.query(action="workflow.failed")[-1].detail["error"] == "no capable agent available"
        assert webhook.delivery_history()[-1].payload["error"] == "no capable agent available"

    def test_workflow_runtime_error_redacted(self):
        engine, audit, webhook = _setup(
            llm_fn_override=lambda prompt, budget_id: (_ for _ in ()).throw(RuntimeError("secret llm detail")),
        )
        result = engine.execute(
            task_id="t1", description="test",
            capability=AgentCapability.LLM_COMPLETION,
            payload={"prompt": "hello"}, tenant_id="t1",
        )
        assert result.status == "failed"
        assert result.error == "workflow execution error (RuntimeError)"
        assert "secret llm detail" not in result.error
        assert audit.query(action="workflow.failed")[-1].detail["error"] == "workflow execution error (RuntimeError)"
        assert webhook.delivery_history()[-1].payload["error"] == "workflow execution error (RuntimeError)"
        assert "secret llm detail" not in webhook.delivery_history()[-1].payload["error"]

    def test_plain_value_error_does_not_trigger_no_capable_classification(self):
        engine, audit, webhook = _setup(
            llm_fn_override=lambda prompt, budget_id: (_ for _ in ()).throw(ValueError("no capable agent secret detail")),
        )
        result = engine.execute(
            task_id="t1", description="test",
            capability=AgentCapability.LLM_COMPLETION,
            payload={"prompt": "hello"}, tenant_id="t1",
        )
        assert result.status == "failed"
        assert result.error == "workflow validation error (ValueError)"
        assert audit.query(action="workflow.failed")[-1].detail["error"] == "workflow validation error (ValueError)"
        assert webhook.delivery_history()[-1].payload["error"] == "workflow validation error (ValueError)"
        assert "no capable agent secret detail" not in webhook.delivery_history()[-1].payload["error"]

    def test_audit_on_success(self):
        engine, audit, _ = _setup()
        engine.execute(
            task_id="t1", description="test",
            capability=AgentCapability.LLM_COMPLETION,
            payload={}, tenant_id="t1",
        )
        entries = audit.query(action="workflow.complete")
        assert len(entries) >= 1

    def test_audit_on_failure(self):
        engine, audit, _ = _setup()
        engine.execute(
            task_id="t1", description="test",
            capability=AgentCapability.WEB_SEARCH,
            payload={}, tenant_id="t1",
        )
        entries = audit.query(action="workflow.failed")
        assert len(entries) >= 1

    def test_webhook_on_success(self):
        engine, _, webhook = _setup()
        engine.execute(
            task_id="t1", description="test",
            capability=AgentCapability.LLM_COMPLETION,
            payload={}, tenant_id="t1",
        )
        assert webhook.delivery_count >= 1

    def test_webhook_on_failure(self):
        engine, _, webhook = _setup()
        engine.execute(
            task_id="t1", description="test",
            capability=AgentCapability.WEB_SEARCH,
            payload={}, tenant_id="t1",
        )
        history = webhook.delivery_history()
        assert any(d.event == "task.failed" for d in history)

    def test_workflow_history(self):
        engine, _, _ = _setup()
        engine.execute(task_id="t1", description="a", capability=AgentCapability.LLM_COMPLETION, payload={}, tenant_id="t1")
        engine.execute(task_id="t2", description="b", capability=AgentCapability.LLM_COMPLETION, payload={}, tenant_id="t1")
        assert engine.total_workflows == 2
        assert len(engine.history()) == 2

    def test_workflow_summary(self):
        engine, _, _ = _setup()
        engine.execute(task_id="t1", description="ok", capability=AgentCapability.LLM_COMPLETION, payload={}, tenant_id="t1")
        engine.execute(task_id="t2", description="fail", capability=AgentCapability.WEB_SEARCH, payload={}, tenant_id="t1")
        summary = engine.summary()
        assert summary["total"] == 2
        assert summary["completed"] == 1
        assert summary["failed"] == 1

    def test_step_details(self):
        engine, _, _ = _setup()
        result = engine.execute(
            task_id="t1", description="test",
            capability=AgentCapability.LLM_COMPLETION,
            payload={"prompt": "hello"}, tenant_id="t1",
        )
        step_names = [s.step_name for s in result.steps]
        assert "submit" in step_names
        assert "assign" in step_names
        assert "start" in step_names
        assert "complete" in step_names

    def test_without_webhook_or_audit(self):
        engine, _, _ = _setup(with_webhook=False, with_audit=False)
        result = engine.execute(
            task_id="t1", description="test",
            capability=AgentCapability.LLM_COMPLETION,
            payload={}, tenant_id="t1",
        )
        assert result.status == "completed"
