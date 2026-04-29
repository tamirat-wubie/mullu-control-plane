"""Gateway capability plan tests.

Purpose: verify deterministic capability planning and execution summaries.
Governance scope: capability passport validation, dependency ordering, risk
aggregation, evidence projection, and terminal certificate enforcement.
Dependencies: gateway.plan and gateway.plan_executor.
Invariants:
  - Every plan step names a registered capability passport.
  - Dependencies must reference earlier declared steps.
  - Plan execution halts on dependency or step failure.
  - Plan success requires terminal certificates for all executed steps.
"""

from __future__ import annotations

import pytest

from gateway.plan import (
    CapabilityPlan,
    CapabilityPlanBuilder,
    CapabilityPlanStep,
    _validate_steps,
    one_step_plan,
)
from gateway.plan_executor import (
    CapabilityPlanExecutor,
    CapabilityPlanStepResult,
)
from gateway.plan_ledger import CapabilityPlanLedger


def test_one_step_plan_projects_risk_and_evidence() -> None:
    plan = one_step_plan(
        capability_id="financial.send_payment",
        params={"amount": "50"},
        tenant_id="t1",
        identity_id="u1",
        goal="send payment",
    )

    assert plan.plan_id.startswith("plan-")
    assert plan.risk_tier == "high"
    assert plan.approval_required is True
    assert plan.steps[0].capability_id == "financial.send_payment"
    assert "transaction_id" in plan.evidence_required
    assert "ledger_hash" in plan.evidence_required


def test_builder_creates_one_step_plan_from_explicit_capability() -> None:
    builder = CapabilityPlanBuilder()

    plan = builder.build(
        message='/run enterprise.task_schedule {"title": "Review report"}',
        tenant_id="tenant-1",
        identity_id="identity-1",
    )

    assert plan is not None
    assert plan.plan_id.startswith("plan-")
    assert plan.steps[0].capability_id == "enterprise.task_schedule"
    assert plan.steps[0].params["title"] == "Review report"
    assert plan.risk_tier == "medium"
    assert plan.approval_required is True
    assert plan.evidence_required == ("task_id",)


def test_builder_decomposes_compound_goal_with_dependencies() -> None:
    builder = CapabilityPlanBuilder()

    plan = builder.build(
        message="search knowledge docs and send message to team",
        tenant_id="t1",
        identity_id="u1",
    )

    assert plan is not None
    assert plan.metadata["step_count"] == 2
    assert [step.capability_id for step in plan.steps] == [
        "enterprise.knowledge_search",
        "enterprise.notification_send",
    ]
    assert plan.steps[1].depends_on == ("step-1",)
    assert plan.steps[1].params["source"] == "step-1.output"
    assert plan.risk_tier == "medium"


def test_builder_decomposes_longer_compound_goal_into_ordered_steps() -> None:
    builder = CapabilityPlanBuilder()

    plan = builder.build(
        message="Analyze data csv and write a report and notify the team and schedule review",
        tenant_id="tenant-1",
        identity_id="identity-1",
    )

    assert plan is not None
    assert [step.capability_id for step in plan.steps] == [
        "creative.data_analyze",
        "creative.document_generate",
        "enterprise.notification_send",
        "enterprise.task_schedule",
    ]
    assert plan.steps[1].depends_on == ("step-1",)
    assert plan.steps[2].depends_on == ("step-2",)
    assert plan.steps[3].depends_on == ("step-3",)
    assert plan.risk_tier == "medium"
    assert "row_count" in plan.evidence_required
    assert "task_id" in plan.evidence_required


def test_plan_builder_returns_none_for_conversation() -> None:
    builder = CapabilityPlanBuilder()

    assert builder.build(message="hello there", tenant_id="t1", identity_id="u1") is None
    assert builder.build(message="", tenant_id="t1", identity_id="u1") is None
    assert builder.build(message="please be kind", tenant_id="t1", identity_id="u1") is None


def test_plan_validation_rejects_unknown_dependency() -> None:
    with pytest.raises(ValueError) as excinfo:
        _validate_steps((
            CapabilityPlanStep(
                step_id="step-1",
                capability_id="enterprise.notification_send",
                params={"body": "notify"},
                depends_on=("missing-step",),
            ),
        ))

    assert "unknown dependency" in str(excinfo.value)
    assert "step-1" in str(excinfo.value)
    assert "missing-step" in str(excinfo.value)


def test_plan_validation_rejects_unknown_capability() -> None:
    with pytest.raises(ValueError) as excinfo:
        one_step_plan(
            capability_id="missing.capability",
            params={},
            tenant_id="t1",
            identity_id="u1",
            goal="missing capability",
        )

    assert "missing capability passport" in str(excinfo.value)
    assert "missing.capability" in str(excinfo.value)
    assert excinfo.type is ValueError


def test_plan_executor_requires_terminal_certificates() -> None:
    plan = one_step_plan(
        capability_id="enterprise.notification_send",
        params={"body": "notify"},
        tenant_id="t1",
        identity_id="u1",
        goal="notify team",
    )
    executor = CapabilityPlanExecutor(
        lambda step, completed: CapabilityPlanStepResult(
            step_id=step.step_id,
            capability_id=step.capability_id,
            succeeded=True,
            command_id="cmd-1",
        )
    )

    result = executor.execute(plan)

    assert result.succeeded is False
    assert result.error == "missing_terminal_certificate:step-1"
    assert result.step_results[0].succeeded is True
    assert result.terminal_certificate_ids == ()
    assert result.evidence_hash


def test_plan_executor_halts_on_failed_step() -> None:
    plan = one_step_plan(
        capability_id="creative.data_analyze",
        params={"csv": "a,b\n1,2\n"},
        tenant_id="tenant-1",
        identity_id="identity-1",
        goal="analyze",
    )
    calls: list[str] = []

    def execute_step(step: CapabilityPlanStep, completed):
        calls.append(step.step_id)
        return CapabilityPlanStepResult(
            step_id=step.step_id,
            capability_id=step.capability_id,
            succeeded=False,
            command_id="cmd-1",
            error="effect_reconciliation_failed",
        )

    result = CapabilityPlanExecutor(execute_step).execute(plan)

    assert calls == ["step-1"]
    assert result.succeeded is False
    assert result.error == "effect_reconciliation_failed"
    assert result.terminal_certificate_ids == ()


def test_plan_executor_halts_on_failed_dependency() -> None:
    plan = CapabilityPlan(
        plan_id="plan-dependent",
        tenant_id="t1",
        identity_id="u1",
        goal="dependent plan",
        steps=(
            CapabilityPlanStep(
                step_id="step-1",
                capability_id="enterprise.knowledge_search",
                params={"query": "policy"},
            ),
            CapabilityPlanStep(
                step_id="step-2",
                capability_id="enterprise.notification_send",
                params={"body": "notify"},
                depends_on=("step-1",),
            ),
        ),
        risk_tier="medium",
        approval_required=True,
        evidence_required=("total_chunks_searched", "receipt_status"),
    )

    def execute_step(step: CapabilityPlanStep, completed):
        if step.step_id == "step-1":
            return CapabilityPlanStepResult(
                step_id=step.step_id,
                capability_id=step.capability_id,
                succeeded=False,
                error="search_failed",
            )
        raise AssertionError("dependent step must not execute")

    result = CapabilityPlanExecutor(execute_step).execute(plan)

    assert result.succeeded is False
    assert result.error == "search_failed"
    assert len(result.step_results) == 1
    assert result.step_results[0].step_id == "step-1"
    assert result.terminal_certificate_ids == ()


def test_plan_executor_succeeds_with_step_terminal_certificate() -> None:
    plan = one_step_plan(
        capability_id="creative.data_analyze",
        params={"csv": "a,b\n1,2\n"},
        tenant_id="tenant-1",
        identity_id="identity-1",
        goal="analyze",
    )

    def execute_step(step: CapabilityPlanStep, completed):
        return CapabilityPlanStepResult(
            step_id=step.step_id,
            capability_id=step.capability_id,
            succeeded=True,
            command_id="cmd-1",
            terminal_certificate_id="cert-1",
            output={"row_count": 1, "column_count": 2},
        )

    result = CapabilityPlanExecutor(execute_step).execute(plan)

    assert result.succeeded is True
    assert result.error == ""
    assert result.terminal_certificate_ids == ("cert-1",)
    assert result.evidence_hash


def test_plan_ledger_certifies_successful_multi_step_execution() -> None:
    plan = CapabilityPlanBuilder().build(
        message="Analyze data csv and write a report and notify the team and schedule review",
        tenant_id="tenant-1",
        identity_id="identity-1",
    )
    assert plan is not None

    def execute_step(step: CapabilityPlanStep, completed):
        return CapabilityPlanStepResult(
            step_id=step.step_id,
            capability_id=step.capability_id,
            succeeded=True,
            command_id=f"cmd-{step.step_id}",
            terminal_certificate_id=f"terminal-{step.step_id}",
            output={"completed_dependencies": tuple(completed)},
        )

    execution = CapabilityPlanExecutor(execute_step).execute(plan)
    ledger = CapabilityPlanLedger(clock=lambda: "2026-04-29T12:00:00+00:00")

    certificate = ledger.certify(plan=plan, execution=execution)
    read_model = ledger.read_model()
    witnesses = ledger.witnesses_for(plan.plan_id)

    assert execution.succeeded is True
    assert certificate.certificate_id.startswith("plan-cert-")
    assert certificate.disposition == "committed"
    assert certificate.step_count == 4
    assert certificate.step_command_ids == ("cmd-step-1", "cmd-step-2", "cmd-step-3", "cmd-step-4")
    assert certificate.step_terminal_certificate_ids == (
        "terminal-step-1",
        "terminal-step-2",
        "terminal-step-3",
        "terminal-step-4",
    )
    assert certificate.evidence_hash == execution.evidence_hash
    assert certificate.metadata["risk_tier"] == "medium"
    assert ledger.certificate_for(plan.plan_id) == certificate
    assert read_model["plan_certificate_count"] == 1
    assert read_model["plan_witness_count"] == 1
    assert witnesses[0].certificate_id == certificate.certificate_id
    assert witnesses[0].detail["cause"] == "plan_terminal_certificate_issued"


def test_plan_ledger_rejects_unsuccessful_execution() -> None:
    plan = one_step_plan(
        capability_id="creative.data_analyze",
        params={"csv": "a,b\n1,2\n"},
        tenant_id="tenant-1",
        identity_id="identity-1",
        goal="analyze",
    )
    execution = CapabilityPlanExecutor(
        lambda step, completed: CapabilityPlanStepResult(
            step_id=step.step_id,
            capability_id=step.capability_id,
            succeeded=False,
            command_id="cmd-1",
            error="reconciliation_failed",
        )
    ).execute(plan)
    ledger = CapabilityPlanLedger(clock=lambda: "2026-04-29T12:00:00+00:00")

    with pytest.raises(ValueError, match="plan execution is not certifiable"):
        ledger.certify(plan=plan, execution=execution)

    assert execution.succeeded is False
    assert ledger.certificate_for(plan.plan_id) is None
    assert ledger.witnesses_for(plan.plan_id) == ()


def test_plan_ledger_records_failure_witness_without_certificate() -> None:
    plan = one_step_plan(
        capability_id="creative.data_analyze",
        params={"csv": "a,b\n1,2\n"},
        tenant_id="tenant-1",
        identity_id="identity-1",
        goal="analyze",
    )
    execution = CapabilityPlanExecutor(
        lambda step, completed: CapabilityPlanStepResult(
            step_id=step.step_id,
            capability_id=step.capability_id,
            succeeded=False,
            command_id="cmd-1",
            error="reconciliation_failed",
        )
    ).execute(plan)
    ledger = CapabilityPlanLedger(clock=lambda: "2026-04-29T12:00:00+00:00")

    witness = ledger.record_failure(plan=plan, execution=execution)
    read_model = ledger.read_model()

    assert witness.witness_id.startswith("plan-witness-")
    assert witness.succeeded is False
    assert witness.certificate_id == ""
    assert witness.detail["cause"] == "plan_execution_failed"
    assert witness.detail["error"] == "reconciliation_failed"
    assert ledger.certificate_for(plan.plan_id) is None
    assert ledger.witnesses_for(plan.plan_id) == (witness,)
    assert read_model["plan_certificate_count"] == 0
    assert read_model["plan_witness_count"] == 1
    assert read_model["failed_plan_witness_count"] == 1


def test_plan_ledger_rejects_missing_step_command_id() -> None:
    plan = one_step_plan(
        capability_id="enterprise.notification_send",
        params={"body": "notify"},
        tenant_id="tenant-1",
        identity_id="identity-1",
        goal="notify",
    )
    execution = CapabilityPlanExecutor(
        lambda step, completed: CapabilityPlanStepResult(
            step_id=step.step_id,
            capability_id=step.capability_id,
            succeeded=True,
            terminal_certificate_id="terminal-1",
        )
    ).execute(plan)
    ledger = CapabilityPlanLedger(clock=lambda: "2026-04-29T12:00:00+00:00")

    with pytest.raises(ValueError, match="missing command id"):
        ledger.certify(plan=plan, execution=execution)

    assert execution.succeeded is True
    assert execution.terminal_certificate_ids == ("terminal-1",)
    assert ledger.read_model()["plan_certificate_count"] == 0
