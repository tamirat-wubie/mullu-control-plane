"""Gateway workflow orchestration tests.

Purpose: verify durable workflow run state transitions for governed operations.
Governance scope: approvals, verification evidence, compensation, terminal
closure, DAG validation, and public schema anchoring.
Dependencies: gateway.workflow_orchestration and schemas/workflow_run.schema.json.
Invariants:
  - High-risk work waits for approval before commitment.
  - Side effects require verification evidence before commitment.
  - Failures move to review until compensation evidence closes them.
  - Invalid workflow graphs fail closed before run creation.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcoi_runtime.contracts.effect_assurance import ExpectedEffect, ReconciliationStatus
from mcoi_runtime.contracts.execution import ExecutionOutcome, ExecutionResult
from mcoi_runtime.core.effect_assurance import EffectAssuranceGate

from gateway.workflow_orchestration import (
    TaskRunStatus,
    WorkflowOrchestrator,
    WorkflowRunStatus,
    WorkflowTaskSpec,
    WorkflowTaskType,
    workflow_effect_records,
    workflow_mutation_receipts,
    workflow_run_to_json_dict,
)

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "workflow_run.schema.json"


def test_invoice_workflow_waits_for_approval_then_closes_with_terminal_certificate() -> None:
    orchestrator = WorkflowOrchestrator()
    run = orchestrator.start_run(
        workflow_id="invoice-approval",
        tenant_id="tenant-a",
        actor_id="ap-clerk",
        goal="pay approved invoice",
        tasks=_invoice_tasks(),
        workflow_run_id="workflow-run-001",
    )

    assert run.status == WorkflowRunStatus.WAITING_FOR_APPROVAL
    assert _status(run, "manager-approval") == TaskRunStatus.WAITING_FOR_APPROVAL
    assert run.metadata["life_meaning_judgment_required"] is True
    assert run.metadata["life_meaning_judgment_ref"] == "life-meaning:workflow-run:workflow-run-001"
    assert run.task_runs[0].task_hash

    run = orchestrator.approve_task(run, task_id="manager-approval", approval_ref="approval://case-001")
    run = orchestrator.commit_task(run, task_id="manager-approval", evidence_refs=("approval://case-001",))
    run = orchestrator.commit_task(run, task_id="budget-check", evidence_refs=("evidence://budget-001",))
    run = orchestrator.commit_task(run, task_id="payment-dispatch", evidence_refs=("receipt://payment-001",))
    run = orchestrator.commit_task(
        run,
        task_id="close-certificate",
        evidence_refs=("proof://terminal-certificate/tcc-001",),
        terminal_certificate_id="tcc-001",
    )

    assert run.status == WorkflowRunStatus.COMMITTED
    assert run.terminal_certificate_id == "tcc-001"
    assert _status(run, "payment-dispatch") == TaskRunStatus.COMMITTED
    assert run.run_hash


def test_workflow_lifecycle_records_bounded_mutation_receipts() -> None:
    orchestrator = WorkflowOrchestrator()
    run = orchestrator.start_run(
        workflow_id="invoice-approval",
        tenant_id="tenant-a",
        actor_id="secret-actor",
        goal="secret goal",
        tasks=_invoice_tasks(),
        workflow_run_id="workflow-run-001",
    )
    run = orchestrator.approve_task(run, task_id="manager-approval", approval_ref="approval://case-001")
    run = orchestrator.mark_executing(run, task_id="manager-approval")
    run = orchestrator.commit_task(run, task_id="manager-approval", evidence_refs=("approval://case-001",))
    run = orchestrator.commit_task(run, task_id="budget-check", evidence_refs=("evidence://budget-001",))

    receipts = workflow_mutation_receipts(run)

    assert tuple(receipt.effect_name for receipt in receipts) == (
        "workflow_run_started",
        "workflow_task_approved",
        "workflow_task_executing",
        "workflow_task_committed",
        "workflow_task_committed",
    )
    assert receipts[0].previous_workflow_status is None
    assert receipts[0].new_workflow_status == "waiting_for_approval"
    assert receipts[0].metadata["life_meaning_judgment_required"] is True
    assert receipts[0].metadata["life_meaning_judgment_ref"] == run.metadata["life_meaning_judgment_ref"]
    assert receipts[1].task_id == "manager-approval"
    assert receipts[1].previous_task_status == "waiting_for_approval"
    assert receipts[1].new_task_status == "approved"
    assert receipts[2].metadata["attempts"] == 1
    assert receipts[3].metadata["evidence_ref_hashes"]
    assert all(receipt.metadata["life_meaning_judgment_ref"] == run.metadata["life_meaning_judgment_ref"] for receipt in receipts)
    assert "secret-actor" not in str(receipts[0].to_dict())
    assert "secret goal" not in str(receipts[0].to_dict())
    assert "approval://case-001" not in str(receipts[1].to_dict())
    assert "evidence://budget-001" not in str(receipts[4].to_dict())


def test_workflow_failure_and_compensation_receipts_are_bounded() -> None:
    orchestrator = WorkflowOrchestrator()
    run = orchestrator.start_run(
        workflow_id="invoice-approval",
        tenant_id="tenant-a",
        actor_id="ap-clerk",
        goal="pay approved invoice",
        tasks=_invoice_tasks(),
    )

    run = orchestrator.fail_task(run, task_id="payment-dispatch", reason="secret provider timeout")
    run = orchestrator.compensate_task(
        run,
        task_id="payment-dispatch",
        evidence_refs=("receipt://payment-reversal-001",),
    )
    receipts = workflow_mutation_receipts(run)

    assert tuple(receipt.effect_name for receipt in receipts) == (
        "workflow_run_started",
        "workflow_task_failed",
        "workflow_task_compensated",
    )
    assert receipts[1].new_workflow_status == "requires_review"
    assert receipts[1].metadata["failure_reason_hash"]
    assert receipts[2].new_task_status == "compensated"
    assert receipts[2].metadata["evidence_ref_hashes"]
    assert "secret provider timeout" not in str(receipts[1].to_dict())
    assert "receipt://payment-reversal-001" not in str(receipts[2].to_dict())


def test_workflow_receipts_convert_to_effect_records() -> None:
    run = WorkflowOrchestrator().start_run(
        workflow_id="invoice-approval",
        tenant_id="tenant-a",
        actor_id="ap-clerk",
        goal="pay approved invoice",
        tasks=_invoice_tasks(),
    )

    effect = workflow_effect_records(run, limit=1)[0]

    assert effect.name == "workflow_run_started"
    assert effect.details["source"] == "workflow_orchestrator"
    assert effect.details["workflow_run_id"] == run.workflow_run_id
    assert effect.details["evidence_ref"].startswith("workflow-receipt:")
    assert effect.details["new_workflow_status"] == "waiting_for_approval"
    assert effect.details["metadata"]["life_meaning_judgment_required"] is True
    assert effect.details["metadata"]["life_meaning_judgment_ref"] == run.metadata["life_meaning_judgment_ref"]


def test_workflow_mutation_receipt_closes_effect_assurance() -> None:
    gate = EffectAssuranceGate(clock=lambda: "2026-05-01T00:00:00Z")
    plan = gate.create_plan(
        command_id="cmd-workflow-start",
        tenant_id="tenant-a",
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
        tenant_id="tenant-a",
        actor_id="ap-clerk",
        goal="pay approved invoice",
        tasks=_invoice_tasks(),
    )
    execution = ExecutionResult(
        execution_id="exec-workflow-start",
        goal_id="goal-workflow-start",
        status=ExecutionOutcome.SUCCEEDED,
        actual_effects=workflow_effect_records(run, limit=1),
        assumed_effects=(),
        started_at="2026-05-01T00:00:00Z",
        finished_at="2026-05-01T00:00:01Z",
    )

    observed = gate.observe(execution)
    verification = gate.verify(plan=plan, execution_result=execution, observed_effects=observed)
    reconciliation = gate.reconcile(plan=plan, observed_effects=observed, verification_result=verification)

    assert reconciliation.status is ReconciliationStatus.MATCH
    assert reconciliation.matched_effects == ("workflow_run_started",)
    assert reconciliation.missing_effects == ()
    assert verification.evidence[0].uri.startswith("workflow-receipt:")


def test_effect_verification_required_blocks_commit_without_evidence() -> None:
    orchestrator = WorkflowOrchestrator()
    run = orchestrator.start_run(
        workflow_id="invoice-approval",
        tenant_id="tenant-a",
        actor_id="ap-clerk",
        goal="pay approved invoice",
        tasks=_invoice_tasks(),
    )
    run = orchestrator.approve_task(run, task_id="manager-approval", approval_ref="approval://case-001")
    run = orchestrator.commit_task(run, task_id="manager-approval", evidence_refs=("approval://case-001",))
    run = orchestrator.commit_task(run, task_id="budget-check", evidence_refs=("evidence://budget-001",))

    with pytest.raises(ValueError, match="verification_evidence_required_before_commit"):
        orchestrator.commit_task(run, task_id="payment-dispatch")

    assert _status(run, "payment-dispatch") == TaskRunStatus.CREATED
    assert run.status in {WorkflowRunStatus.PLANNED, WorkflowRunStatus.APPROVED}


def test_failed_effect_task_requires_compensation_before_compensated_closure() -> None:
    orchestrator = WorkflowOrchestrator()
    run = orchestrator.start_run(
        workflow_id="invoice-approval",
        tenant_id="tenant-a",
        actor_id="ap-clerk",
        goal="pay approved invoice",
        tasks=_invoice_tasks(),
    )

    run = orchestrator.fail_task(run, task_id="payment-dispatch", reason="provider timeout after debit ambiguity")

    assert run.status == WorkflowRunStatus.REQUIRES_REVIEW
    assert _status(run, "payment-dispatch") == TaskRunStatus.REQUIRES_REVIEW

    run = orchestrator.compensate_task(
        run,
        task_id="payment-dispatch",
        evidence_refs=("receipt://payment-reversal-001",),
    )
    run = orchestrator.approve_task(run, task_id="manager-approval", approval_ref="approval://case-001")
    run = orchestrator.commit_task(run, task_id="manager-approval", evidence_refs=("approval://case-001",))
    run = orchestrator.commit_task(run, task_id="budget-check", evidence_refs=("evidence://budget-001",))
    run = orchestrator.commit_task(
        run,
        task_id="close-certificate",
        evidence_refs=("proof://terminal-certificate/tcc-002",),
        terminal_certificate_id="tcc-002",
    )

    assert run.status == WorkflowRunStatus.COMPENSATED
    assert _status(run, "payment-dispatch") == TaskRunStatus.COMPENSATED
    assert "receipt://payment-reversal-001" in _task(run, "payment-dispatch").evidence_refs


def test_cycle_or_missing_dependency_fails_closed() -> None:
    orchestrator = WorkflowOrchestrator()

    with pytest.raises(ValueError, match="missing_task_dependency:missing"):
        orchestrator.start_run(
            workflow_id="bad-workflow",
            tenant_id="tenant-a",
            actor_id="operator",
            goal="reject invalid graph",
            tasks=(WorkflowTaskSpec("task-a", WorkflowTaskType.TASK, "work", depends_on=("missing",)),),
        )

    with pytest.raises(ValueError, match="workflow_dependency_cycle"):
        orchestrator.start_run(
            workflow_id="bad-workflow",
            tenant_id="tenant-a",
            actor_id="operator",
            goal="reject cyclic graph",
            tasks=(
                WorkflowTaskSpec("task-a", WorkflowTaskType.TASK, "work-a", depends_on=("task-b",)),
                WorkflowTaskSpec("task-b", WorkflowTaskType.TASK, "work-b", depends_on=("task-a",)),
            ),
        )


def test_reserved_receipt_metadata_fails_closed_before_run_creation() -> None:
    with pytest.raises(ValueError, match="workflow_metadata_reserved_mutation_receipts"):
        WorkflowOrchestrator().start_run(
            workflow_id="bad-workflow",
            tenant_id="tenant-a",
            actor_id="operator",
            goal="reject spoofed receipt metadata",
            tasks=_invoice_tasks(),
            metadata={"mutation_receipts": []},
        )


def test_workflow_run_schema_exposes_runtime_contract() -> None:
    run = WorkflowOrchestrator().start_run(
        workflow_id="invoice-approval",
        tenant_id="tenant-a",
        actor_id="ap-clerk",
        goal="pay approved invoice",
        tasks=_invoice_tasks(),
    )
    payload = workflow_run_to_json_dict(run)
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    assert set(schema["required"]).issubset(payload)
    assert schema["$id"] == "urn:mullusi:schema:workflow-run:1"
    assert payload["metadata"]["life_meaning_judgment_required"] is True
    assert payload["metadata"]["life_meaning_judgment_ref"] == run.metadata["life_meaning_judgment_ref"]
    assert schema["$defs"]["task_spec"]["properties"]["task_type"]["enum"] == [
        "task",
        "approval_task",
        "human_review_task",
        "wait_until",
        "retry",
        "compensate",
        "verify_effect",
        "close_certificate",
    ]
    assert payload["task_runs"][0]["task_hash"]


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


def _status(run: object, task_id: str) -> TaskRunStatus:
    return _task(run, task_id).status


def _task(run: object, task_id: str) -> object:
    for task_run in run.task_runs:
        if task_run.task_id == task_id:
            return task_run
    raise AssertionError(f"missing task_run: {task_id}")
