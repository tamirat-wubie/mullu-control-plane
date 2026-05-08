"""Purpose: verify governed persisted coordination recovery across runtime stores.
Governance scope: bundled coordination recovery integration only.
Dependencies: app bootstrap/operator facade, persistence stores, and autonomy enforcement.
Invariants:
  - bundled recovery restores in explicit fixed order only after preflight passes.
  - cross-store identity mismatches fail closed before mutation.
  - workflow runtime restore is explicit and occurs before dependent job restore.
"""

from __future__ import annotations

import json
from pathlib import Path

from mcoi_runtime.app.bootstrap import bootstrap_runtime
from mcoi_runtime.app.config import AppConfig
from mcoi_runtime.app.operator_loop import CoordinationRecoveryRequest, OperatorLoop
from mcoi_runtime.contracts.goal import GoalDescriptor, GoalExecutionState, GoalPlan, GoalPriority, GoalStatus, SubGoal
from mcoi_runtime.contracts.job import JobDescriptor, JobPriority, JobState, JobStatus, SlaStatus, WorkQueueEntry
from mcoi_runtime.contracts.roles import TeamQueueState
from mcoi_runtime.contracts.workflow import (
    StageExecutionResult,
    StageStatus,
    StageType,
    WorkflowDescriptor,
    WorkflowExecutionRecord,
    WorkflowStage,
    WorkflowStatus,
)
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.workforce_runtime import WorkforceRuntimeEngine
from mcoi_runtime.persistence.job_store import JobStore
from mcoi_runtime.persistence.goal_store import GoalStore
from mcoi_runtime.persistence.team_queue_store import TeamQueueStore
from mcoi_runtime.persistence.work_queue_store import WorkQueueStore
from mcoi_runtime.persistence.workforce_store import WorkforceStore
from mcoi_runtime.persistence.workflow_store import WorkflowStore


def _seed_job_store(base_path: Path) -> JobStore:
    store = JobStore(base_path)
    runtime = bootstrap_runtime(clock=lambda: "2026-03-18T12:00:00+00:00")
    runtime.job_engine.restore_job(
        JobDescriptor(
            job_id="job-1",
            name="Recovered Job",
            description="Persisted coordination job",
            priority=JobPriority.HIGH,
            created_at="2026-03-18T12:00:00+00:00",
            goal_id="goal-1",
            workflow_id="workflow-1",
        ),
        JobState(
            job_id="job-1",
            status=JobStatus.IN_PROGRESS,
            sla_status=SlaStatus.ON_TRACK,
            goal_id="goal-1",
            workflow_id="workflow-1",
            started_at="2026-03-18T12:00:01+00:00",
            updated_at="2026-03-18T12:00:01+00:00",
        ),
    )
    store.save_state(runtime.job_engine)
    return store


def _seed_goal_store(base_path: Path) -> GoalStore:
    store = GoalStore(base_path)
    descriptor = GoalDescriptor(
        goal_id="goal-1",
        description="Recovered Goal",
        priority=GoalPriority.NORMAL,
        created_at="2026-03-18T12:00:00+00:00",
    )
    plan = GoalPlan(
        plan_id="goal-plan-1",
        goal_id="goal-1",
        sub_goals=(
            SubGoal(
                sub_goal_id="sg-1",
                goal_id="goal-1",
                description="Recovered sub-goal",
            ),
        ),
        created_at="2026-03-18T12:00:00+00:00",
    )
    state = GoalExecutionState(
        goal_id="goal-1",
        status=GoalStatus.EXECUTING,
        current_plan_id="goal-plan-1",
        updated_at="2026-03-18T12:00:01+00:00",
    )
    store.save_goal_descriptor(descriptor)
    store.save_plan(plan)
    store.save_goal_state(state)
    return store


def _seed_work_queue_store(base_path: Path) -> WorkQueueStore:
    store = WorkQueueStore(base_path)
    runtime = bootstrap_runtime(clock=lambda: "2026-03-18T12:00:00+00:00")
    runtime.work_queue.restore_entry(
        WorkQueueEntry(
            entry_id="entry-1",
            job_id="job-1",
            priority=JobPriority.HIGH,
            enqueued_at="2026-03-18T12:00:00+00:00",
        )
    )
    store.save_state(runtime.work_queue)
    return store


def _seed_team_queue_store(base_path: Path) -> TeamQueueStore:
    store = TeamQueueStore(base_path)
    runtime = bootstrap_runtime(clock=lambda: "2026-03-18T12:00:00+00:00")
    runtime.team_engine.restore_queue_state(
        TeamQueueState(
            team_id="team-a",
            queued_jobs=1,
            assigned_jobs=1,
            waiting_jobs=0,
            overloaded_workers=0,
            captured_at="2026-03-18T12:00:00+00:00",
        )
    )
    store.save_queue_states(runtime.team_engine)
    return store


def _seed_workforce_store(base_path: Path) -> WorkforceStore:
    store = WorkforceStore(base_path)
    engine = WorkforceRuntimeEngine(
        EventSpineEngine(clock=lambda: "2026-03-18T12:00:00+00:00")
    )
    engine.register_worker(
        worker_id="worker-1",
        tenant_id="tenant-1",
        role_ref="ops",
        team_ref="team-a",
        display_name="Worker One",
    )
    engine.request_assignment(
        request_id="request-1",
        tenant_id="tenant-1",
        scope_ref_id="scope-1",
        role_ref="ops",
    )
    engine.decide_assignment(
        decision_id="decision-1",
        request_id="request-1",
        worker_id="worker-1",
    )
    store.save_state(engine)
    return store


def _seed_workflow_store(base_path: Path) -> WorkflowStore:
    store = WorkflowStore(base_path)
    descriptor = WorkflowDescriptor(
        workflow_id="workflow-1",
        name="Recovered Workflow",
        stages=(
            WorkflowStage(
                stage_id="stage-1",
                stage_type=StageType.SKILL_EXECUTION,
                skill_id="skill-1",
            ),
        ),
        created_at="2026-03-18T12:00:00+00:00",
    )
    execution = WorkflowExecutionRecord(
        workflow_id="workflow-1",
        execution_id="wf-exec-1",
        status=WorkflowStatus.SUSPENDED,
        stage_results=(
            StageExecutionResult(
                stage_id="stage-1",
                status=StageStatus.COMPLETED,
                output={"result": "ok"},
                started_at="2026-03-18T12:00:01+00:00",
                completed_at="2026-03-18T12:00:02+00:00",
            ),
        ),
        started_at="2026-03-18T12:00:00+00:00",
        completed_at="2026-03-18T12:00:02+00:00",
    )
    store.save_descriptor(descriptor)
    store.save_execution_record(execution)
    return store


def test_recover_coordination_state_restores_all_selected_components(tmp_path: Path) -> None:
    goal_store = _seed_goal_store(tmp_path / "goals")
    job_store = _seed_job_store(tmp_path / "jobs")
    work_queue_store = _seed_work_queue_store(tmp_path / "work-queue")
    team_queue_store = _seed_team_queue_store(tmp_path / "team-queue")
    workforce_store = _seed_workforce_store(tmp_path / "workforce")
    workflow_store = _seed_workflow_store(tmp_path / "workflows")
    runtime = bootstrap_runtime(
        clock=lambda: "2026-03-18T12:00:00+00:00",
        goal_store=goal_store,
        job_store=job_store,
        work_queue_store=work_queue_store,
        team_queue_store=team_queue_store,
        workforce_store=workforce_store,
        workflow_store=workflow_store,
    )
    loop = OperatorLoop(runtime)

    report = loop.recover_coordination_state(
        CoordinationRecoveryRequest(
            request_id="coordination-recovery-1",
            subject_id="subject-1",
            restore_goals=True,
            restore_workflows=True,
            restore_jobs=True,
            restore_work_queue=True,
            restore_team_queue=True,
            restore_workforce=True,
            inspect_workflow_store=True,
        )
    )

    assert report.restored_components == (
        "goals",
        "workflows",
        "jobs",
        "work_queue",
        "team_queue",
        "workforce",
    )
    assert report.inspected_components == (
        "goals",
        "workflow_store",
        "jobs",
        "work_queue",
        "team_queue",
        "workforce",
    )
    assert report.policy_status == "allow"
    assert report.cross_store_checks_passed is True
    assert report.goal_descriptor_count == 1
    assert report.goal_state_count == 1
    assert report.goal_plan_count == 1
    assert report.goal_replan_count == 0
    assert report.job_count == 1
    assert report.work_queue_entry_count == 1
    assert report.team_queue_state_count == 1
    assert report.workforce_worker_count == 1
    assert report.workforce_request_count == 1
    assert report.workforce_decision_count == 1
    assert report.workflow_descriptor_count == 1
    assert report.workflow_execution_count == 1
    assert report.errors == ()
    assert runtime.goal_reasoning_engine.get_goal_descriptor("goal-1") is not None
    assert runtime.goal_reasoning_engine.get_goal_state("goal-1") is not None
    assert runtime.goal_reasoning_engine.get_plan("goal-plan-1") is not None
    assert runtime.workflow_engine.get_workflow_descriptor("workflow-1") is not None
    assert runtime.workflow_engine.get_execution_record("wf-exec-1") is not None
    assert runtime.job_engine.get_job_descriptor("job-1") is not None
    assert runtime.work_queue.get("entry-1") is not None
    assert runtime.team_engine.get_queue_state("team-a") is not None
    assert runtime.workforce_engine.get_worker("worker-1") is not None


def test_recover_coordination_state_fails_closed_on_missing_job_for_queue_entry(tmp_path: Path) -> None:
    work_queue_store = _seed_work_queue_store(tmp_path / "work-queue")
    runtime = bootstrap_runtime(
        clock=lambda: "2026-03-18T12:00:00+00:00",
        work_queue_store=work_queue_store,
    )
    loop = OperatorLoop(runtime)

    report = loop.recover_coordination_state(
        CoordinationRecoveryRequest(
            request_id="coordination-recovery-2",
            subject_id="subject-1",
            restore_work_queue=True,
        )
    )

    assert report.restored_components == ()
    assert report.cross_store_checks_passed is False
    assert report.work_queue_entry_count == 1
    assert report.errors[0].error_code == "recovery_missing_job_for_queue_entry"
    assert runtime.work_queue.list_entries() == ()


def test_recover_coordination_state_fails_closed_on_invalid_workflow_inventory(tmp_path: Path) -> None:
    workflow_store = _seed_workflow_store(tmp_path / "workflows")
    workflow_path = tmp_path / "workflows" / "workflow-descriptor--workflow-1.json"
    workflow_path.unlink()
    runtime = bootstrap_runtime(
        clock=lambda: "2026-03-18T12:00:00+00:00",
        workflow_store=workflow_store,
    )
    loop = OperatorLoop(runtime)

    report = loop.recover_coordination_state(
        CoordinationRecoveryRequest(
            request_id="coordination-recovery-3",
            subject_id="subject-1",
            inspect_workflow_store=True,
        )
    )

    assert report.restored_components == ()
    assert report.workflow_descriptor_count == 0
    assert report.cross_store_checks_passed is False
    assert report.errors[0].error_code in {
        "coordination_store_not_available",
        "workflow_store_invalid",
    }


def test_recover_coordination_state_restores_workflow_runtime_before_jobs(tmp_path: Path) -> None:
    goal_store = _seed_goal_store(tmp_path / "goals")
    job_store = _seed_job_store(tmp_path / "jobs")
    workflow_store = _seed_workflow_store(tmp_path / "workflows")
    runtime = bootstrap_runtime(
        clock=lambda: "2026-03-18T12:00:00+00:00",
        goal_store=goal_store,
        job_store=job_store,
        workflow_store=workflow_store,
    )
    loop = OperatorLoop(runtime)

    report = loop.recover_coordination_state(
        CoordinationRecoveryRequest(
            request_id="coordination-recovery-3b",
            subject_id="subject-1",
            restore_goals=True,
            restore_workflows=True,
            restore_jobs=True,
        )
    )

    assert report.restored_components == ("goals", "workflows", "jobs")
    assert report.cross_store_checks_passed is True
    assert runtime.goal_reasoning_engine.get_goal_descriptor("goal-1") is not None
    assert runtime.workflow_engine.get_workflow_descriptor("workflow-1") is not None
    assert runtime.workflow_engine.get_execution_record("wf-exec-1") is not None
    assert runtime.job_engine.get_job_descriptor("job-1") is not None


def test_recover_coordination_state_fails_closed_on_missing_goal_for_job(tmp_path: Path) -> None:
    job_store = _seed_job_store(tmp_path / "jobs")
    runtime = bootstrap_runtime(
        clock=lambda: "2026-03-18T12:00:00+00:00",
        job_store=job_store,
    )
    loop = OperatorLoop(runtime)

    report = loop.recover_coordination_state(
        CoordinationRecoveryRequest(
            request_id="coordination-recovery-goal-missing",
            subject_id="subject-1",
            restore_jobs=True,
        )
    )

    assert report.restored_components == ()
    assert report.cross_store_checks_passed is False
    assert report.goal_descriptor_count == 0
    assert report.job_count == 1
    assert report.errors[0].error_code == "recovery_missing_goal_for_job"


def test_recover_coordination_state_restore_is_blocked_when_approval_is_required(tmp_path: Path) -> None:
    job_store = _seed_job_store(tmp_path / "jobs")
    runtime = bootstrap_runtime(
        config=AppConfig(autonomy_mode="approval_required"),
        clock=lambda: "2026-03-18T12:00:00+00:00",
        job_store=job_store,
    )
    loop = OperatorLoop(runtime)

    report = loop.recover_coordination_state(
        CoordinationRecoveryRequest(
            request_id="coordination-recovery-4",
            subject_id="subject-1",
            restore_jobs=True,
        )
    )

    assert report.restored_components == ()
    assert report.policy_decision_id is None
    assert report.autonomy_decision == "blocked_pending_approval"
    assert report.errors[0].error_code == "autonomy_blocked"
    assert runtime.job_engine.list_job_descriptors() == ()
