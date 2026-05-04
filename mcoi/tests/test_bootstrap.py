"""Purpose: verify side-effect-free operator-loop bootstrap wiring.
Governance scope: operator-loop tests only.
Dependencies: the local app bootstrap module and execution-slice adapters.
Invariants: bootstrap wires components and adapters explicitly without executing commands or observing the machine.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mcoi_runtime.adapters.filesystem_observer import FilesystemObserver
from mcoi_runtime.adapters.process_observer import ProcessObserver
from mcoi_runtime.adapters.shell_executor import ShellExecutor
from mcoi_runtime.app.bootstrap import bootstrap_runtime, build_policy_decision
from mcoi_runtime.app.config import AppConfig
from mcoi_runtime.contracts.job import JobDescriptor, JobPriority, JobStatus
from mcoi_runtime.contracts.policy import PolicyDecisionStatus
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.memory import EpisodicMemory, MemoryEntry, MemoryTier, WorkingMemory
from mcoi_runtime.core.policy_engine import PolicyInput
from mcoi_runtime.core.jobs import JobEngine
from mcoi_runtime.core.team_runtime import TeamEngine, WorkerRegistry
from mcoi_runtime.core.verification_engine import VerificationEngine
from mcoi_runtime.persistence.job_store import JobStore
from mcoi_runtime.persistence.memory_store import MemoryStore
from mcoi_runtime.persistence.team_queue_store import TeamQueueStore
from mcoi_runtime.persistence.work_queue_store import WorkQueueStore
from mcoi_runtime.persistence.workforce_store import WorkforceStore
from mcoi_runtime.persistence.workflow_store import WorkflowStore
from mcoi_runtime.core.workforce_runtime import WorkforceRuntimeEngine
from mcoi_runtime.contracts.workflow import (
    StageExecutionResult,
    StageStatus,
    StageType,
    WorkflowDescriptor,
    WorkflowExecutionRecord,
    WorkflowStage,
    WorkflowStatus,
)


def test_bootstrap_runtime_returns_wired_components_without_side_effects() -> None:
    runtime = bootstrap_runtime(
        config=AppConfig(),
        clock=lambda: "2026-03-18T12:00:00+00:00",
    )

    assert runtime.dispatcher.template_validator is runtime.template_validator
    assert runtime.runtime_kernel.registry_store is runtime.registry_store
    assert runtime.verification_engine.__class__ is VerificationEngine
    assert runtime.executors["shell_command"].__class__ is ShellExecutor
    assert runtime.observers["filesystem"].__class__ is FilesystemObserver
    assert runtime.observers["process"].__class__ is ProcessObserver
    assert runtime.job_engine.__class__ is JobEngine
    assert runtime.job_store is None
    assert runtime.work_queue.peek() is None
    assert runtime.work_queue_store is None
    assert runtime.team_registry.__class__ is WorkerRegistry
    assert runtime.team_engine.__class__ is TeamEngine
    assert runtime.team_queue_store is None
    assert runtime.workforce_engine.__class__ is WorkforceRuntimeEngine
    assert runtime.workforce_store is None


def test_bootstrap_runtime_respects_explicit_adapter_overrides() -> None:
    class FakeExecutor:
        def execute(self, request):  # pragma: no cover - execution is not allowed in bootstrap
            raise AssertionError("bootstrap must not execute adapters")

    class FakeObserver:
        def observe(self, request):  # pragma: no cover - observation is not allowed in bootstrap
            raise AssertionError("bootstrap must not observe during wiring")

    runtime = bootstrap_runtime(
        executors={"shell_command": FakeExecutor()},
        observers={"filesystem": FakeObserver()},
    )

    assert runtime.executors["shell_command"].__class__ is FakeExecutor
    assert runtime.observers["filesystem"].__class__ is FakeObserver
    assert runtime.verification_engine.__class__ is VerificationEngine
    assert runtime.clock() != ""


def test_bootstrap_runtime_wires_policy_pack_aware_engine() -> None:
    runtime = bootstrap_runtime(
        config=AppConfig(policy_pack_id="strict-approval", policy_pack_version="v0.1"),
        clock=lambda: "2026-03-18T12:00:00+00:00",
    )

    decision = runtime.runtime_kernel.evaluate_policy(
        PolicyInput(
            subject_id="subject-1",
            goal_id="goal-1",
            issued_at=runtime.clock(),
            policy_pack_id=runtime.config.policy_pack_id,
            policy_pack_version=runtime.config.policy_pack_version,
            has_write_effects=True,
        ),
        build_policy_decision,
    )

    assert runtime.config.policy_pack_id == "strict-approval"
    assert decision.status is PolicyDecisionStatus.ESCALATE
    assert decision.reasons[0].code == "escalate-all"


def test_bootstrap_runtime_does_not_restore_memory_implicitly(tmp_path: Path) -> None:
    memory_store = MemoryStore(tmp_path / "memory")
    working = WorkingMemory()
    episodic = EpisodicMemory()
    working.store(
        MemoryEntry(
            entry_id="w-1",
            tier=MemoryTier.WORKING,
            category="observation",
            content={"value": 1},
            source_ids=("src-1",),
        )
    )
    episodic.admit(
        MemoryEntry(
            entry_id="e-1",
            tier=MemoryTier.EPISODIC,
            category="trace",
            content={"value": 2},
            source_ids=("trace-1",),
        )
    )
    before_hashes = memory_store.save_all(working=working, episodic=episodic)

    runtime = bootstrap_runtime(memory_store=memory_store)

    after_hashes = memory_store.save_all(working=working, episodic=episodic)
    assert runtime.memory_store is memory_store
    assert runtime.working_memory.size == 0
    assert runtime.episodic_memory.size == 0
    assert before_hashes == after_hashes


def test_bootstrap_runtime_restores_memory_only_when_explicit(tmp_path: Path) -> None:
    memory_store = MemoryStore(tmp_path / "memory")
    working = WorkingMemory(max_entries=5)
    episodic = EpisodicMemory()
    working.store(
        MemoryEntry(
            entry_id="w-1",
            tier=MemoryTier.WORKING,
            category="observation",
            content={"value": 1},
            source_ids=("src-1",),
        )
    )
    episodic.admit(
        MemoryEntry(
            entry_id="e-1",
            tier=MemoryTier.EPISODIC,
            category="trace",
            content={"value": 2},
            source_ids=("trace-1",),
        )
    )
    memory_store.save_all(working=working, episodic=episodic)

    runtime = bootstrap_runtime(memory_store=memory_store, restore_memory=True)

    assert runtime.memory_store is memory_store
    assert runtime.working_memory.max_entries == 5
    assert runtime.working_memory.get("w-1") is not None
    assert runtime.episodic_memory.get("e-1") is not None


def test_bootstrap_runtime_rejects_restore_without_store() -> None:
    with pytest.raises(RuntimeCoreInvariantError, match="memory_store"):
        bootstrap_runtime(restore_memory=True)


def test_bootstrap_runtime_does_not_restore_jobs_implicitly(tmp_path: Path) -> None:
    job_store = JobStore(tmp_path / "jobs")
    source_engine = JobEngine(clock=iter(("2026-03-18T12:00:00+00:00",) * 6).__next__)
    descriptor, _state = source_engine.create_job(
        "Job One",
        "Persisted job",
        JobPriority.HIGH,
    )
    source_engine.start_job(descriptor.job_id)
    before = job_store.save_state(source_engine)

    runtime = bootstrap_runtime(job_store=job_store)

    after = job_store.save_state(source_engine)
    assert runtime.job_store is job_store
    assert runtime.job_engine.list_job_descriptors() == ()
    assert runtime.job_engine.list_job_states() == ()
    assert before == after


def test_bootstrap_runtime_restores_jobs_only_when_explicit(tmp_path: Path) -> None:
    job_store = JobStore(tmp_path / "jobs")
    source_engine = JobEngine(clock=iter(("2026-03-18T12:00:00+00:00",) * 6).__next__)
    descriptor, _state = source_engine.create_job(
        "Job One",
        "Persisted job",
        JobPriority.HIGH,
    )
    source_engine.start_job(descriptor.job_id)
    job_store.save_state(source_engine)

    runtime = bootstrap_runtime(
        clock=lambda: "2026-03-18T12:00:00+00:00",
        job_store=job_store,
        restore_jobs=True,
    )

    restored_descriptor = runtime.job_engine.get_job_descriptor(descriptor.job_id)
    restored_state = runtime.job_engine.get_job_state(descriptor.job_id)
    assert runtime.job_store is job_store
    assert restored_descriptor is not None
    assert restored_descriptor.priority is JobPriority.HIGH
    assert restored_state is not None
    assert restored_state.status is JobStatus.IN_PROGRESS


def test_bootstrap_runtime_rejects_job_restore_without_store() -> None:
    with pytest.raises(RuntimeCoreInvariantError, match="job_store"):
        bootstrap_runtime(restore_jobs=True)


def test_bootstrap_runtime_does_not_restore_workflows_implicitly(tmp_path: Path) -> None:
    workflow_store = WorkflowStore(tmp_path / "workflows")
    source_runtime = bootstrap_runtime(clock=lambda: "2026-03-18T12:00:00+00:00")
    descriptor = WorkflowDescriptor(
        workflow_id="workflow-1",
        name="Persisted Workflow",
        stages=(WorkflowStage(stage_id="stage-1", stage_type=StageType.OBSERVATION),),
        created_at="2026-03-18T12:00:00+00:00",
    )
    record = WorkflowExecutionRecord(
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
    source_runtime.workflow_engine.restore_descriptor(descriptor)
    source_runtime.workflow_engine.restore_execution_record(record)
    before = workflow_store.save_state(source_runtime.workflow_engine)

    runtime = bootstrap_runtime(workflow_store=workflow_store)

    after = workflow_store.save_state(source_runtime.workflow_engine)
    assert runtime.workflow_store is workflow_store
    assert runtime.workflow_engine.list_workflow_descriptors() == ()
    assert runtime.workflow_engine.list_execution_records() == ()
    assert before == after


def test_bootstrap_runtime_restores_workflows_only_when_explicit(tmp_path: Path) -> None:
    workflow_store = WorkflowStore(tmp_path / "workflows")
    source_runtime = bootstrap_runtime(clock=lambda: "2026-03-18T12:00:00+00:00")
    descriptor = WorkflowDescriptor(
        workflow_id="workflow-1",
        name="Persisted Workflow",
        stages=(WorkflowStage(stage_id="stage-1", stage_type=StageType.OBSERVATION),),
        created_at="2026-03-18T12:00:00+00:00",
    )
    record = WorkflowExecutionRecord(
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
    source_runtime.workflow_engine.restore_descriptor(descriptor)
    source_runtime.workflow_engine.restore_execution_record(record)
    workflow_store.save_state(source_runtime.workflow_engine)

    runtime = bootstrap_runtime(
        workflow_store=workflow_store,
        restore_workflows=True,
    )

    restored_descriptor = runtime.workflow_engine.get_workflow_descriptor("workflow-1")
    restored_record = runtime.workflow_engine.get_execution_record("wf-exec-1")
    assert runtime.workflow_store is workflow_store
    assert restored_descriptor is not None
    assert restored_descriptor.name == "Persisted Workflow"
    assert restored_record is not None
    assert restored_record.status is WorkflowStatus.SUSPENDED


def test_bootstrap_runtime_rejects_workflow_restore_without_store() -> None:
    with pytest.raises(RuntimeCoreInvariantError, match="workflow_store"):
        bootstrap_runtime(restore_workflows=True)


def test_bootstrap_runtime_does_not_restore_team_queue_implicitly(tmp_path: Path) -> None:
    team_queue_store = TeamQueueStore(tmp_path / "team-queue")
    source_runtime = bootstrap_runtime(clock=lambda: "2026-03-18T12:00:00+00:00")
    source_runtime.team_engine.capture_queue_state(
        "team-a",
        queued=5,
        assigned=3,
        waiting=2,
    )
    before = team_queue_store.save_queue_states(source_runtime.team_engine)

    runtime = bootstrap_runtime(team_queue_store=team_queue_store)

    after = team_queue_store.save_queue_states(source_runtime.team_engine)
    assert runtime.team_queue_store is team_queue_store
    assert runtime.team_engine.queue_state_count == 0
    assert before == after


def test_bootstrap_runtime_restores_team_queue_only_when_explicit(tmp_path: Path) -> None:
    team_queue_store = TeamQueueStore(tmp_path / "team-queue")
    source_runtime = bootstrap_runtime(clock=lambda: "2026-03-18T12:00:00+00:00")
    source_runtime.team_engine.capture_queue_state(
        "team-a",
        queued=5,
        assigned=3,
        waiting=2,
    )
    team_queue_store.save_queue_states(source_runtime.team_engine)

    runtime = bootstrap_runtime(
        clock=lambda: "2026-03-18T12:00:00+00:00",
        team_queue_store=team_queue_store,
        restore_team_queue=True,
    )

    state = runtime.team_engine.get_queue_state("team-a")
    assert runtime.team_queue_store is team_queue_store
    assert runtime.team_engine.queue_state_count == 1
    assert state is not None
    assert state.queued_jobs == 5
    assert state.assigned_jobs == 3
    assert state.waiting_jobs == 2


def test_bootstrap_runtime_rejects_team_queue_restore_without_store() -> None:
    with pytest.raises(RuntimeCoreInvariantError, match="team_queue_store"):
        bootstrap_runtime(restore_team_queue=True)


def test_bootstrap_runtime_does_not_restore_work_queue_implicitly(tmp_path: Path) -> None:
    work_queue_store = WorkQueueStore(tmp_path / "work-queue")
    source_runtime = bootstrap_runtime(clock=lambda: "2026-03-18T12:00:00+00:00")
    source_runtime.work_queue.enqueue(
        JobDescriptor(
            job_id="job-1",
            name="Job One",
            description="Queue item one",
            priority=JobPriority.HIGH,
            created_at="2026-03-18T12:00:00+00:00",
        )
    )
    before = work_queue_store.save_state(source_runtime.work_queue)

    runtime = bootstrap_runtime(work_queue_store=work_queue_store)

    after = work_queue_store.save_state(source_runtime.work_queue)
    assert runtime.work_queue_store is work_queue_store
    assert runtime.work_queue.list_entries() == ()
    assert before == after


def test_bootstrap_runtime_restores_work_queue_only_when_explicit(tmp_path: Path) -> None:
    work_queue_store = WorkQueueStore(tmp_path / "work-queue")
    source_runtime = bootstrap_runtime(clock=lambda: "2026-03-18T12:00:00+00:00")
    source_runtime.work_queue.enqueue(
        JobDescriptor(
            job_id="job-1",
            name="Job One",
            description="Queue item one",
            priority=JobPriority.HIGH,
            created_at="2026-03-18T12:00:00+00:00",
        )
    )
    work_queue_store.save_state(source_runtime.work_queue)

    runtime = bootstrap_runtime(
        clock=lambda: "2026-03-18T12:00:00+00:00",
        work_queue_store=work_queue_store,
        restore_work_queue=True,
    )

    restored = runtime.work_queue.peek()
    assert runtime.work_queue_store is work_queue_store
    assert restored is not None
    assert restored.job_id == "job-1"
    assert restored.priority is JobPriority.HIGH


def test_bootstrap_runtime_rejects_work_queue_restore_without_store() -> None:
    with pytest.raises(RuntimeCoreInvariantError, match="work_queue_store"):
        bootstrap_runtime(restore_work_queue=True)


def test_bootstrap_runtime_does_not_restore_workforce_implicitly(tmp_path: Path) -> None:
    workforce_store = WorkforceStore(tmp_path / "workforce")
    source_engine = WorkforceRuntimeEngine(
        EventSpineEngine(clock=lambda: "2026-03-18T12:00:00+00:00")
    )
    source_engine.register_worker(
        worker_id="worker-1",
        tenant_id="tenant-1",
        role_ref="ops",
        team_ref="team-1",
        display_name="Worker One",
    )
    source_engine.request_assignment(
        request_id="request-1",
        tenant_id="tenant-1",
        scope_ref_id="scope-1",
        role_ref="ops",
    )
    source_engine.decide_assignment(
        decision_id="decision-1",
        request_id="request-1",
        worker_id="worker-1",
    )
    before = workforce_store.save_state(source_engine)

    runtime = bootstrap_runtime(workforce_store=workforce_store)

    after = workforce_store.save_state(source_engine)
    assert runtime.workforce_store is workforce_store
    assert runtime.workforce_engine.worker_count == 0
    assert runtime.workforce_engine.request_count == 0
    assert runtime.workforce_engine.decision_count == 0
    assert before == after


def test_bootstrap_runtime_restores_workforce_only_when_explicit(tmp_path: Path) -> None:
    workforce_store = WorkforceStore(tmp_path / "workforce")
    source_engine = WorkforceRuntimeEngine(
        EventSpineEngine(clock=lambda: "2026-03-18T12:00:00+00:00")
    )
    source_engine.register_worker(
        worker_id="worker-1",
        tenant_id="tenant-1",
        role_ref="ops",
        team_ref="team-1",
        display_name="Worker One",
    )
    source_engine.request_assignment(
        request_id="request-1",
        tenant_id="tenant-1",
        scope_ref_id="scope-1",
        role_ref="ops",
    )
    source_engine.decide_assignment(
        decision_id="decision-1",
        request_id="request-1",
        worker_id="worker-1",
    )
    workforce_store.save_state(source_engine)

    runtime = bootstrap_runtime(
        workforce_store=workforce_store,
        restore_workforce=True,
    )

    assert runtime.workforce_store is workforce_store
    assert runtime.workforce_engine.worker_count == 1
    assert runtime.workforce_engine.request_count == 1
    assert runtime.workforce_engine.decision_count == 1
    assert runtime.workforce_engine.get_worker("worker-1").current_assignments == 1


def test_bootstrap_runtime_rejects_workforce_restore_without_store() -> None:
    with pytest.raises(RuntimeCoreInvariantError, match="workforce_store"):
        bootstrap_runtime(restore_workforce=True)
