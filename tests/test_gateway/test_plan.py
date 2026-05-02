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
from gateway.plan_ledger import (
    CapabilityPlanLedger,
    JsonFileCapabilityPlanLedgerStore,
    build_capability_plan_ledger_from_env,
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


def test_plan_executor_resumes_from_certified_checkpoint() -> None:
    plan = CapabilityPlan(
        plan_id="plan-resume",
        tenant_id="tenant-1",
        identity_id="identity-1",
        goal="search then notify",
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
    calls: list[str] = []

    def execute_step(step: CapabilityPlanStep, completed):
        calls.append(step.step_id)
        return CapabilityPlanStepResult(
            step_id=step.step_id,
            capability_id=step.capability_id,
            succeeded=True,
            command_id="cmd-step-2",
            terminal_certificate_id="terminal-step-2",
            output={"completed_dependencies": tuple(completed)},
        )

    result = CapabilityPlanExecutor(execute_step).execute(
        plan,
        initial_results=(
            CapabilityPlanStepResult(
                step_id="step-1",
                capability_id="enterprise.knowledge_search",
                succeeded=True,
                command_id="cmd-step-1",
                terminal_certificate_id="terminal-step-1",
                output={"total_chunks_searched": 1},
            ),
        ),
    )

    assert calls == ["step-2"]
    assert result.succeeded is True
    assert result.terminal_certificate_ids == ("terminal-step-1", "terminal-step-2")
    assert result.step_results[1].output["completed_dependencies"] == ("step-1",)


def test_plan_executor_rejects_checkpoint_missing_terminal_certificate() -> None:
    plan = one_step_plan(
        capability_id="enterprise.knowledge_search",
        params={"query": "policy"},
        tenant_id="tenant-1",
        identity_id="identity-1",
        goal="search policy",
    )
    executed = False

    def execute_step(step: CapabilityPlanStep, completed):
        nonlocal executed
        executed = True
        return CapabilityPlanStepResult(step.step_id, step.capability_id, True)

    result = CapabilityPlanExecutor(execute_step).execute(
        plan,
        initial_results=(
            CapabilityPlanStepResult(
                step_id="step-1",
                capability_id="enterprise.knowledge_search",
                succeeded=True,
                command_id="cmd-step-1",
            ),
        ),
    )

    assert result.succeeded is False
    assert result.error == "checkpoint_missing_terminal_certificate:step-1"
    assert executed is False
    assert result.terminal_certificate_ids == ()


def test_plan_executor_rejects_checkpoint_out_of_dependency_order() -> None:
    plan = CapabilityPlan(
        plan_id="plan-resume-order",
        tenant_id="tenant-1",
        identity_id="identity-1",
        goal="search then notify",
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

    result = CapabilityPlanExecutor(lambda step, completed: CapabilityPlanStepResult(step.step_id, step.capability_id, True)).execute(
        plan,
        initial_results=(
            CapabilityPlanStepResult(
                step_id="step-2",
                capability_id="enterprise.notification_send",
                succeeded=True,
                command_id="cmd-step-2",
                terminal_certificate_id="terminal-step-2",
            ),
        ),
    )

    assert result.succeeded is False
    assert result.error == "checkpoint_dependency_not_satisfied:step-2:step-1"
    assert result.step_results[0].step_id == "step-2"


def test_plan_executor_rejects_checkpoint_capability_mismatch() -> None:
    plan = one_step_plan(
        capability_id="enterprise.knowledge_search",
        params={"query": "policy"},
        tenant_id="tenant-1",
        identity_id="identity-1",
        goal="search policy",
    )

    result = CapabilityPlanExecutor(lambda step, completed: CapabilityPlanStepResult(step.step_id, step.capability_id, True)).execute(
        plan,
        initial_results=(
            CapabilityPlanStepResult(
                step_id="step-1",
                capability_id="enterprise.notification_send",
                succeeded=True,
                command_id="cmd-step-1",
                terminal_certificate_id="terminal-step-1",
            ),
        ),
    )

    assert result.succeeded is False
    assert result.error == "checkpoint_capability_mismatch:step-1"
    assert result.terminal_certificate_ids == ("terminal-step-1",)


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
    bundle = ledger.export_evidence_bundle(plan_id=plan.plan_id)
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
    assert bundle.bundle_id.startswith("plan-evidence-bundle-")
    assert bundle.plan_id == plan.plan_id
    assert bundle.certificate_id == certificate.certificate_id
    assert bundle.step_command_ids == certificate.step_command_ids
    assert bundle.step_terminal_certificate_ids == certificate.step_terminal_certificate_ids
    assert bundle.plan_evidence_hash == execution.evidence_hash
    assert bundle.witness_ids == (witnesses[0].witness_id,)
    assert f"plan_terminal_certificate:{certificate.certificate_id}" in bundle.evidence_refs
    assert "step_command:cmd-step-1" in bundle.evidence_refs
    assert "step_terminal_certificate:terminal-step-1" in bundle.evidence_refs
    assert ledger.certificate_for(plan.plan_id) == certificate
    assert read_model["plan_certificate_count"] == 1
    assert read_model["plan_witness_count"] == 1
    assert witnesses[0].certificate_id == certificate.certificate_id
    assert witnesses[0].detail["cause"] == "plan_terminal_certificate_issued"


def test_plan_ledger_rejects_missing_evidence_bundle() -> None:
    ledger = CapabilityPlanLedger(clock=lambda: "2026-04-29T12:00:00+00:00")

    with pytest.raises(KeyError, match="plan terminal certificate not found"):
        ledger.export_evidence_bundle(plan_id="missing-plan")

    with pytest.raises(ValueError, match="plan_id is required"):
        ledger.export_evidence_bundle(plan_id="")

    assert ledger.witnesses_for() == ()


def test_json_plan_ledger_store_survives_recreation(tmp_path) -> None:
    plan = one_step_plan(
        capability_id="enterprise.knowledge_search",
        params={"query": "policy"},
        tenant_id="tenant-1",
        identity_id="identity-1",
        goal="search policy",
    )

    def execute_step(step: CapabilityPlanStep, completed):
        return CapabilityPlanStepResult(
            step_id=step.step_id,
            capability_id=step.capability_id,
            succeeded=True,
            command_id="cmd-1",
            terminal_certificate_id="terminal-1",
            output={"total_chunks_searched": 1},
        )

    execution = CapabilityPlanExecutor(execute_step).execute(plan)
    path = tmp_path / "plan-ledger.json"
    first_ledger = CapabilityPlanLedger(
        clock=lambda: "2026-04-29T12:00:00+00:00",
        store=JsonFileCapabilityPlanLedgerStore(path),
    )

    certificate = first_ledger.certify(plan=plan, execution=execution)
    second_ledger = CapabilityPlanLedger(
        clock=lambda: "2026-04-29T12:00:01+00:00",
        store=JsonFileCapabilityPlanLedgerStore(path),
    )
    reloaded = second_ledger.certificate_for(plan.plan_id)
    witnesses = second_ledger.witnesses_for(plan.plan_id)
    read_model = second_ledger.read_model()

    assert reloaded == certificate
    assert witnesses[0].certificate_id == certificate.certificate_id
    assert witnesses[0].detail["cause"] == "plan_terminal_certificate_issued"
    assert read_model["plan_certificate_count"] == 1
    assert read_model["plan_witness_count"] == 1
    assert read_model["store"]["backend"] == "json_file"


def test_plan_ledger_records_recovery_attempts_in_read_model() -> None:
    ledger = CapabilityPlanLedger(clock=lambda: "2026-04-29T12:00:00+00:00")

    blocked_attempt = ledger.record_recovery_attempt(
        plan_id="plan-1",
        recovery_action="wait_for_approval",
        status="blocked",
        reason="approval_wait_command_not_terminal",
        witness_id="plan-witness-1",
        detail={"command_id": "cmd-1"},
    )
    succeeded_attempt = ledger.record_recovery_attempt(
        plan_id="plan-1",
        recovery_action="wait_for_approval",
        status="succeeded",
        reason="plan_recovered",
        witness_id="plan-witness-1",
        terminal_certificate_id="plan-cert-1",
        detail={"command_id": "cmd-1"},
    )
    read_model = ledger.read_model()
    filtered = ledger.read_model(recovery_attempt_status="blocked")
    paged = ledger.read_model(recovery_attempt_limit=1, recovery_attempt_offset=1)

    assert blocked_attempt.attempt_id.startswith("plan-recovery-attempt-")
    assert blocked_attempt.plan_id == "plan-1"
    assert blocked_attempt.recovery_action == "wait_for_approval"
    assert blocked_attempt.status == "blocked"
    assert blocked_attempt.detail["command_id"] == "cmd-1"
    assert ledger.recovery_attempts_for("plan-1") == (blocked_attempt, succeeded_attempt)
    assert read_model["recovery_attempt_count"] == 2
    assert read_model["recovery_attempt_status_counts"] == {"blocked": 1, "succeeded": 1}
    assert read_model["recovery_attempt_status_filter"] == ""
    assert [attempt["attempt_id"] for attempt in read_model["recovery_attempts"]] == [
        blocked_attempt.attempt_id,
        succeeded_attempt.attempt_id,
    ]
    assert filtered["recovery_attempt_count"] == 2
    assert filtered["recovery_attempt_status_filter"] == "blocked"
    assert filtered["recovery_attempt_status_counts"] == {"blocked": 1, "succeeded": 1}
    assert len(filtered["recovery_attempts"]) == 1
    assert filtered["recovery_attempts"][0]["attempt_id"] == blocked_attempt.attempt_id
    assert paged["recovery_attempt_count"] == 2
    assert paged["recovery_attempt_page"] == {
        "total": 2,
        "limit": 1,
        "offset": 1,
        "next_offset": None,
    }
    assert len(paged["recovery_attempts"]) == 1
    assert paged["recovery_attempts"][0]["attempt_id"] == succeeded_attempt.attempt_id


def test_json_plan_ledger_store_survives_recovery_attempt_recreation(tmp_path) -> None:
    path = tmp_path / "plan-ledger-recovery-attempts.json"
    first_ledger = CapabilityPlanLedger(
        clock=lambda: "2026-04-29T12:00:00+00:00",
        store=JsonFileCapabilityPlanLedgerStore(path),
    )

    attempt = first_ledger.record_recovery_attempt(
        plan_id="plan-1",
        recovery_action="wait_for_approval",
        status="succeeded",
        reason="plan_recovered",
        witness_id="plan-witness-1",
        terminal_certificate_id="plan-cert-1",
    )
    second_ledger = CapabilityPlanLedger(
        clock=lambda: "2026-04-29T12:00:01+00:00",
        store=JsonFileCapabilityPlanLedgerStore(path),
    )
    attempts = second_ledger.recovery_attempts_for("plan-1")
    read_model = second_ledger.read_model()

    assert attempts == (attempt,)
    assert attempts[0].terminal_certificate_id == "plan-cert-1"
    assert read_model["recovery_attempt_count"] == 1
    assert read_model["recovery_attempt_status_counts"] == {"succeeded": 1}
    assert read_model["store"]["recovery_attempts"] == 1


def test_plan_ledger_env_builder_uses_json_path(monkeypatch, tmp_path) -> None:
    path = tmp_path / "plan-ledger-env.json"
    monkeypatch.setenv("MULLU_PLAN_LEDGER_BACKEND", "json_file")
    monkeypatch.setenv("MULLU_PLAN_LEDGER_PATH", str(path))

    ledger = build_capability_plan_ledger_from_env(clock=lambda: "2026-04-29T12:00:00+00:00")
    read_model = ledger.read_model()

    assert path.exists()
    assert read_model["store"]["backend"] == "json_file"
    assert read_model["store"]["path"] == str(path)
    assert read_model["plan_certificate_count"] == 0


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
    assert witness.detail["recovery_decision"]["recovery_action"] == "retry_or_review"
    assert witness.detail["recovery_decision"]["retry_allowed"] is True
    assert witness.detail["recovery_decision"]["review_required"] is True
    assert ledger.certificate_for(plan.plan_id) is None
    assert ledger.witnesses_for(plan.plan_id) == (witness,)
    assert read_model["plan_certificate_count"] == 0
    assert read_model["plan_witness_count"] == 1
    assert read_model["failed_plan_witness_count"] == 1
    assert read_model["recovery_action_counts"] == {"retry_or_review": 1}
    assert read_model["failed_plan_witnesses"][0]["witness_id"] == witness.witness_id


def test_plan_ledger_read_model_filters_failed_witnesses_by_recovery_action() -> None:
    retry_plan = one_step_plan(
        capability_id="creative.data_analyze",
        params={"csv": "a,b\n1,2\n"},
        tenant_id="tenant-1",
        identity_id="identity-1",
        goal="analyze",
    )
    approval_plan = one_step_plan(
        capability_id="enterprise.task_schedule",
        params={"title": "Review report"},
        tenant_id="tenant-1",
        identity_id="identity-1",
        goal="schedule review",
    )
    ledger = CapabilityPlanLedger(clock=lambda: "2026-04-29T12:00:00+00:00")
    retry_execution = CapabilityPlanExecutor(
        lambda step, completed: CapabilityPlanStepResult(
            step_id=step.step_id,
            capability_id=step.capability_id,
            succeeded=False,
            command_id="cmd-retry",
            error="analysis_failed",
        )
    ).execute(retry_plan)
    approval_execution = CapabilityPlanExecutor(
        lambda step, completed: CapabilityPlanStepResult(
            step_id=step.step_id,
            capability_id=step.capability_id,
            succeeded=False,
            command_id="cmd-approval",
            error="approval_required:apr-1",
        )
    ).execute(approval_plan)

    retry_witness = ledger.record_failure(plan=retry_plan, execution=retry_execution)
    approval_witness = ledger.record_failure(plan=approval_plan, execution=approval_execution)
    filtered = ledger.read_model(recovery_action="wait_for_approval")
    paged = ledger.read_model(failed_witness_limit=1, failed_witness_offset=1)
    unfiltered = ledger.read_model()

    assert unfiltered["failed_plan_witness_count"] == 2
    assert unfiltered["failed_plan_witness_page"] == {
        "total": 2,
        "limit": 2,
        "offset": 0,
        "next_offset": None,
    }
    assert unfiltered["recovery_action_counts"] == {
        "retry_or_review": 1,
        "wait_for_approval": 1,
    }
    assert filtered["recovery_action_filter"] == "wait_for_approval"
    assert filtered["failed_plan_witness_count"] == 2
    assert filtered["failed_plan_witness_page"] == {
        "total": 1,
        "limit": 1,
        "offset": 0,
        "next_offset": None,
    }
    assert len(filtered["failed_plan_witnesses"]) == 1
    assert filtered["failed_plan_witnesses"][0]["witness_id"] == approval_witness.witness_id
    assert filtered["failed_plan_witnesses"][0]["witness_id"] != retry_witness.witness_id
    assert paged["failed_plan_witness_count"] == 2
    assert paged["failed_plan_witness_page"] == {
        "total": 2,
        "limit": 1,
        "offset": 1,
        "next_offset": None,
    }
    assert len(paged["failed_plan_witnesses"]) == 1
    assert paged["failed_plan_witnesses"][0]["witness_id"] == approval_witness.witness_id


def test_plan_ledger_classifies_approval_wait_recovery() -> None:
    plan = one_step_plan(
        capability_id="enterprise.task_schedule",
        params={"title": "Review report"},
        tenant_id="tenant-1",
        identity_id="identity-1",
        goal="schedule review",
    )
    execution = CapabilityPlanExecutor(
        lambda step, completed: CapabilityPlanStepResult(
            step_id=step.step_id,
            capability_id=step.capability_id,
            succeeded=False,
            command_id="cmd-1",
            error="approval_required:apr-1",
        )
    ).execute(plan)
    ledger = CapabilityPlanLedger(clock=lambda: "2026-04-29T12:00:00+00:00")

    witness = ledger.record_failure(plan=plan, execution=execution)
    decision = witness.detail["recovery_decision"]

    assert decision["recovery_action"] == "wait_for_approval"
    assert decision["approval_required"] is True
    assert decision["retry_allowed"] is True
    assert decision["review_required"] is False
    assert decision["failed_capability_id"] == "enterprise.task_schedule"


def test_plan_ledger_classifies_compensation_after_mutating_step() -> None:
    plan = CapabilityPlan(
        plan_id="plan-mutating-failure",
        tenant_id="tenant-1",
        identity_id="identity-1",
        goal="notify then search",
        steps=(
            CapabilityPlanStep(
                step_id="step-1",
                capability_id="enterprise.notification_send",
                params={"body": "notify"},
            ),
            CapabilityPlanStep(
                step_id="step-2",
                capability_id="enterprise.knowledge_search",
                params={"query": "policy"},
                depends_on=("step-1",),
            ),
        ),
        risk_tier="medium",
        approval_required=True,
        evidence_required=("receipt_status", "total_chunks_searched"),
    )
    execution = CapabilityPlanExecutor(
        lambda step, completed: CapabilityPlanStepResult(
            step_id=step.step_id,
            capability_id=step.capability_id,
            succeeded=step.step_id == "step-1",
            command_id=f"cmd-{step.step_id}",
            terminal_certificate_id=f"terminal-{step.step_id}" if step.step_id == "step-1" else "",
            error="" if step.step_id == "step-1" else "search_failed",
        )
    ).execute(plan)
    ledger = CapabilityPlanLedger(clock=lambda: "2026-04-29T12:00:00+00:00")

    witness = ledger.record_failure(plan=plan, execution=execution)
    decision = witness.detail["recovery_decision"]

    assert decision["recovery_action"] == "compensate_or_review"
    assert decision["compensation_required"] is True
    assert decision["review_required"] is True
    assert decision["retry_allowed"] is False
    assert decision["completed_mutating_capabilities"] == ("enterprise.notification_send",)


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
