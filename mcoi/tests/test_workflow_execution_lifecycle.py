"""Purpose: bind workflow execution lifecycle proof witnesses to exact anchors.
Governance scope: workflow, traced workflow, pipeline, template, session, and
    ledger execution/read-model surfaces.
Dependencies: FastAPI server, workflow core, traced workflow core, request
    tracing, gateway workflow orchestration, and Effect Assurance.
Invariants:
  - Execution endpoints return bounded action proofs where required.
  - Bad capabilities and recorder failures stay sanitized.
  - Read models expose bounded fields.
  - Workflow mutation receipts redact raw sensitive values.
"""

from __future__ import annotations

from typing import Any

import pytest

from mcoi_runtime.adapters.llm_adapter import StubLLMBackend
from mcoi_runtime.contracts.effect_assurance import ExpectedEffect, ReconciliationStatus
from mcoi_runtime.contracts.execution import ExecutionOutcome, ExecutionResult
from mcoi_runtime.contracts.llm import LLMBudget
from mcoi_runtime.core.agent_protocol import AgentCapability, AgentDescriptor, AgentRegistry, TaskManager
from mcoi_runtime.core.agent_workflow import AgentWorkflowEngine
from mcoi_runtime.core.effect_assurance import EffectAssuranceGate
from mcoi_runtime.core.execution_replay import ReplayRecorder
from mcoi_runtime.core.llm_integration import LLMIntegrationBridge
from mcoi_runtime.core.traced_workflow import TracedWorkflowEngine
from mcoi_runtime.governance.audit.trail import AuditTrail
from mcoi_runtime.governance.network.webhook import WebhookManager, WebhookSubscription

from gateway.workflow_orchestration import (
    WorkflowOrchestrator,
    WorkflowTaskSpec,
    WorkflowTaskType,
    workflow_effect_records,
    workflow_mutation_receipts,
)

FIXED_CLOCK_VALUE = "2026-05-15T12:00:00Z"


def _fixed_clock() -> str:
    return FIXED_CLOCK_VALUE


def _workflow_api_payload(task_id: str, capability: str = "llm.completion") -> dict[str, Any]:
    return {
        "task_id": task_id,
        "description": "bounded workflow lifecycle anchor",
        "capability": capability,
        "tenant_id": "tenant-workflow-anchor",
        "actor_id": "actor-workflow-anchor",
        "payload": {"prompt": "summarize governed workflow state"},
    }


def _legacy_execute_payload() -> dict[str, Any]:
    return {
        "goal_id": "goal-legacy-anchor",
        "action": "legacy.execute",
        "tenant_id": "tenant-workflow-anchor",
        "actor_id": "actor-workflow-anchor",
        "body": {"request": "bounded execution"},
    }


def _workflow_engine(
    *,
    llm_complete_fn: Any | None = None,
    with_webhook: bool = True,
    with_audit: bool = True,
) -> tuple[AgentWorkflowEngine, AuditTrail | None, WebhookManager | None]:
    registry = AgentRegistry()
    registry.register(
        AgentDescriptor(
            agent_id="llm-agent",
            name="LLM Agent",
            capabilities=(AgentCapability.LLM_COMPLETION, AgentCapability.TOOL_USE),
        )
    )
    registry.register(
        AgentDescriptor(
            agent_id="code-agent",
            name="Code Agent",
            capabilities=(AgentCapability.CODE_EXECUTION,),
        )
    )
    task_manager = TaskManager(clock=_fixed_clock, registry=registry)

    resolved_llm_complete_fn = llm_complete_fn
    if resolved_llm_complete_fn is None:
        bridge = LLMIntegrationBridge(clock=_fixed_clock, default_backend=StubLLMBackend())
        bridge.register_budget(LLMBudget(budget_id="default", tenant_id="system", max_cost=100.0))

        def resolved_llm_complete_fn(prompt: str, budget_id: str) -> object:
            return bridge.complete(prompt, budget_id=budget_id)

    webhook_manager: WebhookManager | None = None
    if with_webhook:
        webhook_manager = WebhookManager(clock=_fixed_clock)
        webhook_manager.subscribe(
            WebhookSubscription(
                subscription_id="workflow-anchor-subscription",
                tenant_id="tenant-workflow-anchor",
                url="https://example.com/workflow",
                events=("task.completed", "task.failed"),
            )
        )

    audit_trail = AuditTrail(clock=_fixed_clock) if with_audit else None
    return (
        AgentWorkflowEngine(
            clock=_fixed_clock,
            task_manager=task_manager,
            llm_complete_fn=resolved_llm_complete_fn,
            webhook_manager=webhook_manager,
            audit_trail=audit_trail,
        ),
        audit_trail,
        webhook_manager,
    )


def _traced_workflow(recorder: ReplayRecorder | None = None) -> tuple[TracedWorkflowEngine, ReplayRecorder]:
    workflow_engine, _, _ = _workflow_engine(with_webhook=False, with_audit=False)
    replay_recorder = recorder or ReplayRecorder(clock=_fixed_clock)
    return TracedWorkflowEngine(workflow_engine=workflow_engine, replay_recorder=replay_recorder), replay_recorder


def _invoice_tasks() -> tuple[WorkflowTaskSpec, ...]:
    return (
        WorkflowTaskSpec(
            task_id="manager-approval",
            task_type=WorkflowTaskType.APPROVAL_TASK,
            action="request_manager_approval",
            approval_required=True,
            evidence_required=("approval://case-001",),
        ),
        WorkflowTaskSpec(
            task_id="budget-check",
            task_type=WorkflowTaskType.TASK,
            action="check_budget",
            depends_on=("manager-approval",),
            verification_required=True,
            evidence_required=("evidence://budget-001",),
        ),
        WorkflowTaskSpec(
            task_id="payment-dispatch",
            task_type=WorkflowTaskType.TASK,
            action="payment.dispatch",
            depends_on=("budget-check",),
            verification_required=True,
            compensation_task_id="close-certificate",
        ),
        WorkflowTaskSpec(
            task_id="close-certificate",
            task_type=WorkflowTaskType.CLOSE_CERTIFICATE,
            action="emit_terminal_certificate",
            depends_on=("payment-dispatch",),
        ),
    )


def test_workflow_execute_emits_action_proof(test_client) -> None:
    response = test_client.post("/api/v1/workflow/execute", json=_workflow_api_payload("wfl-anchor-execute"))

    body = response.json()
    proof = body["action_proof"]
    assert response.status_code == 200
    assert body["status"] == "completed"
    assert proof["endpoint"] == "/api/v1/workflow/execute"
    assert proof["action"] == "workflow.execute"
    assert proof["succeeded"] is True
    assert proof["proof_receipt_id"]
    assert proof["proof_hash"]


def test_workflow_invalid_capability_bounded(test_client) -> None:
    response = test_client.post(
        "/api/v1/workflow/execute",
        json=_workflow_api_payload("wfl-anchor-invalid", capability="secret.unregistered.capability"),
    )

    body = response.json()
    assert response.status_code == 400
    assert body["detail"]["error"] == "invalid capability"
    assert body["detail"]["error_code"] == "invalid_capability"
    assert body["detail"]["governed"] is True
    assert "secret.unregistered.capability" not in str(body)


def test_workflow_history_bounded(test_client) -> None:
    test_client.post("/api/v1/workflow/execute", json=_workflow_api_payload("wfl-anchor-history"))

    response = test_client.get("/api/v1/workflow/history", params={"limit": 1})
    zero_response = test_client.get("/api/v1/workflow/history", params={"limit": 0})
    body = response.json()
    workflow = body["workflows"][0]
    assert response.status_code == 200
    assert zero_response.status_code == 200
    assert len(body["workflows"]) <= 1
    assert zero_response.json()["workflows"] == []
    assert set(workflow) == {"id", "task", "agent", "status"}
    assert body["summary"]["total"] >= len(body["workflows"])


def test_workflow_success_records_audit() -> None:
    engine, audit_trail, _ = _workflow_engine()
    result = engine.execute(
        task_id="wfl-anchor-audit-success",
        description="audit success",
        capability=AgentCapability.LLM_COMPLETION,
        payload={"prompt": "audit success"},
        tenant_id="tenant-workflow-anchor",
    )

    entries = audit_trail.query(action="workflow.complete") if audit_trail else []
    assert result.status == "completed"
    assert len(entries) == 1
    assert entries[0].outcome == "success"
    assert entries[0].detail["workflow_id"] == result.workflow_id
    assert entries[0].tenant_id == "tenant-workflow-anchor"


def test_workflow_failure_records_audit() -> None:
    engine, audit_trail, _ = _workflow_engine()
    result = engine.execute(
        task_id="wfl-anchor-audit-failure",
        description="audit failure",
        capability=AgentCapability.WEB_SEARCH,
        payload={},
        tenant_id="tenant-workflow-anchor",
    )

    entries = audit_trail.query(action="workflow.failed") if audit_trail else []
    assert result.status == "failed"
    assert result.error == "no capable agent available"
    assert len(entries) == 1
    assert entries[0].outcome == "error"
    assert entries[0].detail["error"] == "no capable agent available"


def test_workflow_errors_sanitized() -> None:
    def failing_llm(_prompt: str, _budget_id: str) -> object:
        raise RuntimeError("raw workflow provider secret")

    engine, audit_trail, webhook_manager = _workflow_engine(llm_complete_fn=failing_llm)
    result = engine.execute(
        task_id="wfl-anchor-sanitized-error",
        description="sanitize runtime failure",
        capability=AgentCapability.LLM_COMPLETION,
        payload={"prompt": "trigger bounded error"},
        tenant_id="tenant-workflow-anchor",
    )

    audit_error = audit_trail.query(action="workflow.failed")[-1].detail["error"] if audit_trail else ""
    webhook_error = webhook_manager.delivery_history()[-1].payload["error"] if webhook_manager else ""
    assert result.status == "failed"
    assert result.error == "workflow execution error (RuntimeError)"
    assert audit_error == result.error
    assert webhook_error == result.error
    assert "raw workflow provider secret" not in str((result.error, audit_error, webhook_error))


def test_workflow_lifecycle_mutation_receipts_emitted() -> None:
    orchestrator = WorkflowOrchestrator()
    run = orchestrator.start_run(
        workflow_id="invoice-approval",
        tenant_id="tenant-workflow-anchor",
        actor_id="secret-actor",
        goal="secret payment goal",
        tasks=_invoice_tasks(),
        workflow_run_id="workflow-run-anchor-success",
    )
    run = orchestrator.approve_task(run, task_id="manager-approval", approval_ref="approval://case-001")
    run = orchestrator.mark_executing(run, task_id="manager-approval")
    run = orchestrator.commit_task(run, task_id="manager-approval", evidence_refs=("approval://case-001",))
    run = orchestrator.commit_task(run, task_id="budget-check", evidence_refs=("evidence://budget-001",))

    receipts = workflow_mutation_receipts(run)
    serialized = str([receipt.to_dict() for receipt in receipts])
    assert tuple(receipt.effect_name for receipt in receipts) == (
        "workflow_run_started",
        "workflow_task_approved",
        "workflow_task_executing",
        "workflow_task_committed",
        "workflow_task_committed",
    )
    assert receipts[0].new_workflow_status == "waiting_for_approval"
    assert receipts[3].metadata["evidence_ref_hashes"]
    assert "secret-actor" not in serialized
    assert "secret payment goal" not in serialized
    assert "approval://case-001" not in serialized


def test_workflow_failure_compensation_receipts_emitted() -> None:
    orchestrator = WorkflowOrchestrator()
    run = orchestrator.start_run(
        workflow_id="invoice-approval",
        tenant_id="tenant-workflow-anchor",
        actor_id="ap-clerk",
        goal="pay approved invoice",
        tasks=_invoice_tasks(),
        workflow_run_id="workflow-run-anchor-compensate",
    )
    run = orchestrator.fail_task(run, task_id="payment-dispatch", reason="raw provider timeout secret")
    run = orchestrator.compensate_task(
        run,
        task_id="payment-dispatch",
        evidence_refs=("receipt://payment-reversal-secret",),
    )

    receipts = workflow_mutation_receipts(run)
    serialized = str([receipt.to_dict() for receipt in receipts])
    assert tuple(receipt.effect_name for receipt in receipts) == (
        "workflow_run_started",
        "workflow_task_failed",
        "workflow_task_compensated",
    )
    assert receipts[1].new_workflow_status == "requires_review"
    assert receipts[2].new_task_status == "compensated"
    assert receipts[1].metadata["failure_reason_hash"]
    assert "raw provider timeout secret" not in serialized
    assert "receipt://payment-reversal-secret" not in serialized


def test_workflow_mutation_receipt_closes_effect_assurance() -> None:
    gate = EffectAssuranceGate(clock=_fixed_clock)
    plan = gate.create_plan(
        command_id="cmd-workflow-start-anchor",
        tenant_id="tenant-workflow-anchor",
        capability_id="workflow.start",
        expected_effects=(
            ExpectedEffect(
                effect_id="workflow_run_started",
                name="workflow_run_started",
                target_ref="workflow:invoice-approval",
                required=True,
                verification_method="workflow_mutation_receipt",
            ),
        ),
        forbidden_effects=("workflow_invalid_transition_committed",),
    )
    run = WorkflowOrchestrator().start_run(
        workflow_id="invoice-approval",
        tenant_id="tenant-workflow-anchor",
        actor_id="ap-clerk",
        goal="pay approved invoice",
        tasks=_invoice_tasks(),
        workflow_run_id="workflow-run-anchor-effect",
    )
    execution = ExecutionResult(
        execution_id="exec-workflow-start-anchor",
        goal_id="goal-workflow-start-anchor",
        status=ExecutionOutcome.SUCCEEDED,
        actual_effects=workflow_effect_records(run, limit=1),
        assumed_effects=(),
        started_at=FIXED_CLOCK_VALUE,
        finished_at=FIXED_CLOCK_VALUE,
    )

    observed = gate.observe(execution)
    verification = gate.verify(plan=plan, execution_result=execution, observed_effects=observed)
    reconciliation = gate.reconcile(plan=plan, observed_effects=observed, verification_result=verification)
    assert reconciliation.status is ReconciliationStatus.MATCH
    assert reconciliation.matched_effects == ("workflow_run_started",)
    assert reconciliation.missing_effects == ()
    assert verification.evidence[0].uri.startswith("workflow-receipt:")


def test_traced_workflow_emits_replay_trace(test_client) -> None:
    response = test_client.post("/api/v1/workflow/traced", json=_workflow_api_payload("wfl-anchor-traced"))

    body = response.json()
    proof = body["action_proof"]
    assert response.status_code == 200
    assert body["status"] == "completed"
    assert body["trace_id"] == "trace-wfl-anchor-traced"
    assert body["trace_frames"] >= 3
    assert body["trace_hash"]
    assert proof["endpoint"] == "/api/v1/workflow/traced"


class _StartFailingReplayRecorder(ReplayRecorder):
    def start_trace(self, trace_id: str):
        raise RuntimeError("raw trace start secret")


class _FrameFailingReplayRecorder(ReplayRecorder):
    def record_frame(self, *args: object, **kwargs: object) -> None:
        raise RuntimeError("raw trace frame secret")


class _CompleteFailingReplayRecorder(ReplayRecorder):
    def complete_trace(self, trace_id: str):
        raise RuntimeError("raw trace complete secret")


def test_traced_workflow_recorder_errors_sanitized() -> None:
    for recorder in (
        _StartFailingReplayRecorder(clock=_fixed_clock),
        _FrameFailingReplayRecorder(clock=_fixed_clock),
        _CompleteFailingReplayRecorder(clock=_fixed_clock),
    ):
        traced, _ = _traced_workflow(recorder)
        result, trace = traced.execute(
            task_id=f"wfl-anchor-trace-fail-{type(recorder).__name__}",
            description="trace failure remains non-fatal",
            capability=AgentCapability.LLM_COMPLETION,
            payload={},
            tenant_id="tenant-workflow-anchor",
        )

        assert result.status == "completed"
        assert trace is None
        assert traced.trace_recording_failures >= 1
        assert traced.last_trace_recording_error == "trace recording failed (RuntimeError)"
        assert "raw trace" not in traced.last_trace_recording_error


def test_legacy_execute_emits_action_proof(test_client) -> None:
    response = test_client.post("/api/v1/execute", json=_legacy_execute_payload())

    body = response.json()
    proof = body["action_proof"]
    assert response.status_code == 200
    assert body["governed"] is True
    assert body["trace_id"]
    assert proof["endpoint"] == "/api/v1/execute"
    assert proof["action"] == "legacy.execute"
    assert proof["succeeded"] is True
    assert proof["proof_hash"]


def test_legacy_execute_uses_request_unique_trace_witness(test_client) -> None:
    first = test_client.post("/api/v1/execute", json=_legacy_execute_payload())
    second = test_client.post("/api/v1/execute", json=_legacy_execute_payload())

    first_body = first.json()
    second_body = second.json()
    assert first.status_code == 200
    assert second.status_code == 200
    assert first_body["trace_id"].startswith("http-")
    assert second_body["trace_id"].startswith("http-")
    assert first_body["trace_id"] != second_body["trace_id"]
    assert "goal-legacy-anchor" not in first_body["trace_id"]


def test_session_read_model_bounded(test_client) -> None:
    response = test_client.post(
        "/api/v1/session",
        params={"actor_id": "actor-session-anchor", "tenant_id": "tenant-session-anchor"},
    )

    body = response.json()
    assert response.status_code == 200
    assert set(body) == {"session_id", "actor_id", "tenant_id"}
    assert body["session_id"].startswith("sess-")
    assert body["actor_id"] == "actor-session-anchor"
    assert body["tenant_id"] == "tenant-session-anchor"


def test_ledger_read_model_bounded(test_client) -> None:
    response = test_client.get("/api/v1/ledger", params={"tenant_id": "tenant-workflow-anchor", "limit": 5})

    body = response.json()
    assert response.status_code == 200
    assert set(body) == {"entries", "count", "governed"}
    assert body["governed"] is True
    assert body["count"] == len(body["entries"])
    assert len(body["entries"]) <= 5


def test_local_developer_workflow_read_model_is_selectable_and_read_only(test_client) -> None:
    response = test_client.get("/api/v1/workflow/local-developer/read-model")

    body = response.json()
    read_model = body["read_model"]
    assert response.status_code == 200
    assert body["workflow_id"] == "mullu.local_developer_workflow.v1"
    assert body["selectable"] is True
    assert body["execution_authority_granted"] is False
    assert body["governed"] is True
    assert read_model["valid"] is True
    assert read_model["external_mutation_allowed"] is False
    assert read_model["approval_stage_id"] == "operator_review_gate"
    assert read_model["stage_count"] == 5
    assert read_model["binding_count"] == 4
    assert read_model["stages"][1]["effect_class"] == "external_write"
    assert read_model["stages"][1]["grants_new_capability_authority"] is False
    assert read_model["workflow"]["workflow_id"] == body["workflow_id"]


@pytest.mark.parametrize(
    ("endpoint", "params"),
    [
        ("/api/v1/ledger", {"tenant_id": "tenant-workflow-anchor", "limit": -1}),
        ("/api/v1/ledger", {"tenant_id": "tenant-workflow-anchor", "limit": "not-a-limit"}),
        ("/api/v1/ledger", {"tenant_id": "tenant-workflow-anchor", "limit": 501}),
        ("/api/v1/workflow/history", {"limit": -1}),
        ("/api/v1/workflow/history", {"limit": "not-a-limit"}),
        ("/api/v1/workflow/history", {"limit": 501}),
        ("/api/v1/cognitive/shadow/observations", {"limit": -1}),
        ("/api/v1/cognitive/shadow/observations", {"limit": "not-a-limit"}),
        ("/api/v1/cognitive/shadow/observations", {"limit": 501}),
        ("/api/v1/pipeline/history", {"limit": -1}),
        ("/api/v1/pipeline/history", {"limit": "not-a-limit"}),
        ("/api/v1/pipeline/history", {"limit": 501}),
    ],
)
def test_workflow_read_model_invalid_limits_are_bounded(test_client, endpoint, params) -> None:
    response = test_client.get(endpoint, params=params)

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["error"] == "invalid workflow read request"
    assert detail["error_code"] == "workflow_invalid_read_request"
    assert detail["governed"] is True
    assert "not-a-limit" not in str(response.json())
    assert "-1" not in str(response.json())
    assert "501" not in str(response.json())
    assert "limit" not in str(response.json())


def test_cognitive_shadow_observations_zero_limit_is_empty_read(test_client) -> None:
    response = test_client.get("/api/v1/cognitive/shadow/observations", params={"limit": 0})

    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is False
    assert body["observations"] == []


def test_pipeline_execution_emits_action_proof(test_client) -> None:
    response = test_client.post(
        "/api/v1/pipeline/execute",
        json={
            "steps": [
                {"step_id": "s1", "name": "Summarize", "prompt_template": "Summarize: {input}"},
                {"step_id": "s2", "name": "Refine", "prompt_template": "Refine: {input}"},
            ],
            "initial_input": "bounded pipeline input",
            "tenant_id": "tenant-workflow-anchor",
        },
    )

    body = response.json()
    proof = body["action_proof"]
    assert response.status_code == 200
    assert body["succeeded"] is True
    assert len(body["steps"]) == 2
    assert proof["endpoint"] == "/api/v1/pipeline/execute"
    assert proof["action"] == "pipeline.execute"
    assert proof["succeeded"] is True
    assert proof["proof_receipt_id"]


def test_pipeline_history_bounded(test_client) -> None:
    test_client.post(
        "/api/v1/pipeline/execute",
        json={
            "steps": [{"step_id": "s1", "name": "History", "prompt_template": "History: {input}"}],
            "initial_input": "bounded history input",
            "tenant_id": "tenant-workflow-anchor",
        },
    )

    response = test_client.get("/api/v1/pipeline/history", params={"limit": 1})
    zero_response = test_client.get("/api/v1/pipeline/history", params={"limit": 0})
    body = response.json()
    pipeline = body["pipelines"][0]
    assert response.status_code == 200
    assert zero_response.status_code == 200
    assert len(body["pipelines"]) <= 1
    assert zero_response.json()["pipelines"] == []
    assert set(pipeline) == {"id", "succeeded", "steps", "cost"}
    assert body["summary"]["total"] >= len(body["pipelines"])
    assert pipeline["steps"] >= 1


def test_template_read_models_bounded(test_client) -> None:
    response = test_client.get("/api/v1/templates")

    body = response.json()
    template = body["templates"][0]
    assert response.status_code == 200
    assert body["summary"]["total"] >= 2
    assert set(template) == {"id", "name", "description", "parameters", "category"}
    assert "summarize-refine" in {item["id"] for item in body["templates"]}
    assert all(isinstance(item["parameters"], list) for item in body["templates"])


def test_template_execution_governed(test_client) -> None:
    response = test_client.post(
        "/api/v1/templates/execute",
        json={
            "template_id": "summarize-refine",
            "params": {"topic": "workflow lifecycle", "audience": "operator"},
            "initial_input": "bounded template input",
            "tenant_id": "tenant-workflow-anchor",
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert body["template_id"] == "summarize-refine"
    assert body["succeeded"] is True
    assert body["steps"] == 2
    assert body["governed"] is True
    assert body["chain_id"].startswith("chain-")
