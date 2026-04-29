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
