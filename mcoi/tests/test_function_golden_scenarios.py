"""Golden scenario tests for the function runtime engine.

Each scenario exercises an end-to-end path through FunctionRegistry, FunctionEngine,
and FunctionPlaybook to validate real-world usage patterns.
"""

import pytest

from mcoi_runtime.contracts.function import (
    CommunicationStyle,
    FunctionMetricsSnapshot,
    FunctionOutcomeRecord,
    FunctionPolicyBinding,
    FunctionQueueProfile,
    FunctionSlaProfile,
    FunctionStatus,
    FunctionType,
    ServiceFunctionTemplate,
)
from mcoi_runtime.contracts.job import (
    DeadlineRecord,
    JobDescriptor,
    JobPriority,
    SlaStatus,
    WorkQueueEntry,
)
from mcoi_runtime.core.function_runtime import (
    FunctionEngine,
    FunctionPlaybook,
    FunctionRegistry,
    PlaybookDescriptor,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


# --- Timestamps ---

_T0 = "2025-06-01T09:00:00+00:00"
_T1 = "2025-06-01T09:01:00+00:00"
_T2 = "2025-06-01T09:02:00+00:00"
_T3 = "2025-06-01T09:03:00+00:00"
_T4 = "2025-06-01T09:04:00+00:00"
_T5 = "2025-06-01T09:05:00+00:00"
_T_20MIN = "2025-06-01T09:20:00+00:00"
_T_25MIN = "2025-06-01T09:25:00+00:00"
_T_35MIN = "2025-06-01T09:35:00+00:00"
_T_45MIN = "2025-06-01T09:45:00+00:00"
_T_50MIN = "2025-06-01T09:50:00+00:00"
_T_1H = "2025-06-01T10:00:00+00:00"
_T_1H10 = "2025-06-01T10:10:00+00:00"
_T_2H = "2025-06-01T11:00:00+00:00"
_T_3H = "2025-06-01T12:00:00+00:00"


def _make_clock(times: list[str]):
    it = iter(times)
    return lambda: next(it)


def _fixed_clock(t: str = _T0):
    return lambda: t


# ============================================================
# Scenario 1: Incident response function — full lifecycle
# ============================================================


class TestIncidentResponseScenario:
    """Register an incident response function, activate it, submit a job,
    evaluate SLA, record outcome, and compute metrics."""

    def test_full_incident_response_lifecycle(self) -> None:
        # Step 1: Register function
        reg = FunctionRegistry(clock=_fixed_clock(_T0))
        fn = ServiceFunctionTemplate(
            function_id="fn-ir",
            name="Incident Response",
            function_type=FunctionType.INCIDENT_RESPONSE,
            description="Production incident handling",
            created_at=_T0,
        )
        reg.register_function(fn)
        assert reg.get_function_status("fn-ir") == FunctionStatus.DRAFT

        # Step 2: Add SLA profile
        sla = FunctionSlaProfile(
            function_id="fn-ir",
            target_completion_minutes=30,
            approval_latency_minutes=5,
            escalation_threshold_minutes=20,
        )
        reg.register_sla_profile(sla)

        # Step 3: Activate
        reg.activate_function("fn-ir")
        assert reg.get_function_status("fn-ir") == FunctionStatus.ACTIVE

        # Step 4: Submit job
        engine = FunctionEngine(registry=reg, clock=_fixed_clock(_T1))
        job = JobDescriptor(
            job_id="job-outage-1",
            name="Database outage",
            description="Primary DB is unreachable",
            priority=JobPriority.CRITICAL,
            created_at=_T0,
        )
        entry = engine.submit_job_to_function("fn-ir", job)
        assert entry.job_id == "job-outage-1"
        assert entry.priority == JobPriority.CRITICAL

        # Step 5: Evaluate SLA at 20 minutes (on track: 20/30 = 67%)
        records = engine.evaluate_function_sla("fn-ir", [(job, _T0)], _T_20MIN)
        assert records[0].sla_status == SlaStatus.ON_TRACK

        # Step 6: Evaluate SLA at 25 minutes (at risk: 25/30 = 83%)
        records = engine.evaluate_function_sla("fn-ir", [(job, _T0)], _T_25MIN)
        assert records[0].sla_status == SlaStatus.AT_RISK

        # Step 7: Record outcome (completed in 28 minutes)
        outcome_engine = FunctionEngine(registry=reg, clock=_fixed_clock(_T2))
        outcome = outcome_engine.record_outcome(
            "fn-ir", "job-outage-1",
            completed=True, completion_minutes=28,
        )
        assert outcome.completed is True
        assert outcome.completion_minutes == 28

        # Step 8: Compute metrics
        metrics_engine = FunctionEngine(registry=reg, clock=_fixed_clock(_T3))
        metrics = metrics_engine.compute_metrics("fn-ir", [outcome], _T0, _T3)
        assert metrics.total_jobs == 1
        assert metrics.completed_jobs == 1
        assert metrics.failed_jobs == 0
        assert metrics.avg_completion_minutes == 28.0

    def test_incident_with_escalation(self) -> None:
        reg = FunctionRegistry(clock=_fixed_clock(_T0))
        fn = ServiceFunctionTemplate(
            function_id="fn-ir-esc",
            name="IR Escalation",
            function_type=FunctionType.INCIDENT_RESPONSE,
            description="Escalated incidents",
            created_at=_T0,
        )
        reg.register_function(fn)
        reg.register_sla_profile(FunctionSlaProfile(
            function_id="fn-ir-esc",
            target_completion_minutes=30,
            approval_latency_minutes=5,
            escalation_threshold_minutes=20,
        ))
        reg.activate_function("fn-ir-esc")

        engine = FunctionEngine(registry=reg, clock=_fixed_clock(_T1))
        job = JobDescriptor(
            job_id="job-esc-1", name="Esc job", description="Escalated",
            priority=JobPriority.CRITICAL, created_at=_T0,
        )
        engine.submit_job_to_function("fn-ir-esc", job)

        # SLA breached at 35 minutes
        records = engine.evaluate_function_sla("fn-ir-esc", [(job, _T0)], _T_35MIN)
        assert records[0].sla_status == SlaStatus.BREACHED

        # Record as escalated
        out_engine = FunctionEngine(registry=reg, clock=_fixed_clock(_T2))
        outcome = out_engine.record_outcome(
            "fn-ir-esc", "job-esc-1",
            completed=True, completion_minutes=35, escalated=True,
        )
        assert outcome.escalated is True


# ============================================================
# Scenario 2: Document intake function with queue profile
# ============================================================


class TestDocumentIntakeScenario:
    """Register a document intake function with a queue profile,
    submit a job, and verify assignment routing."""

    def test_document_intake_with_queue_routing(self) -> None:
        reg = FunctionRegistry(clock=_fixed_clock(_T0))
        fn = ServiceFunctionTemplate(
            function_id="fn-doc",
            name="Document Intake",
            function_type=FunctionType.DOCUMENT_INTAKE,
            description="Processes incoming documents",
            created_at=_T0,
        )
        reg.register_function(fn)

        # Add queue profile with team assignment
        queue = FunctionQueueProfile(
            function_id="fn-doc",
            team_id="team-doc-review",
            default_role_id="role-reviewer",
            communication_style=CommunicationStyle.STANDARD,
            max_concurrent_jobs=10,
        )
        reg.register_queue_profile(queue)
        reg.activate_function("fn-doc")

        engine = FunctionEngine(registry=reg, clock=_fixed_clock(_T1))
        job = JobDescriptor(
            job_id="job-doc-1", name="Invoice processing",
            description="Process incoming invoice", priority=JobPriority.NORMAL,
            created_at=_T0,
        )
        entry = engine.submit_job_to_function("fn-doc", job)
        assert entry.assigned_to_team_id == "team-doc-review"
        assert entry.priority == JobPriority.NORMAL

    def test_document_intake_with_policy_binding(self) -> None:
        reg = FunctionRegistry(clock=_fixed_clock(_T0))
        fn = ServiceFunctionTemplate(
            function_id="fn-doc-pb",
            name="Doc Intake PB",
            function_type=FunctionType.DOCUMENT_INTAKE,
            description="Policy bound intake",
            created_at=_T0,
        )
        reg.register_function(fn)
        binding = FunctionPolicyBinding(
            binding_id="bind-doc",
            function_id="fn-doc-pb",
            policy_pack_id="pack-compliance",
            autonomy_mode="supervised",
            review_required=True,
        )
        reg.register_policy_binding(binding)
        bindings = reg.get_bindings_for_function("fn-doc-pb")
        assert len(bindings) == 1
        assert bindings[0].review_required is True


# ============================================================
# Scenario 3: Retired function rejects new jobs
# ============================================================


class TestRetiredFunctionScenario:
    """A retired function must reject all new job submissions."""

    def test_retired_function_rejects_submission(self) -> None:
        reg = FunctionRegistry(clock=_fixed_clock(_T0))
        fn = ServiceFunctionTemplate(
            function_id="fn-legacy",
            name="Legacy Process",
            function_type=FunctionType.CUSTOM,
            description="Deprecated function",
            created_at=_T0,
        )
        reg.register_function(fn)
        reg.activate_function("fn-legacy")
        reg.retire_function("fn-legacy")

        engine = FunctionEngine(registry=reg, clock=_fixed_clock(_T1))
        job = JobDescriptor(
            job_id="job-late", name="Late submission",
            description="Should be rejected", priority=JobPriority.LOW,
            created_at=_T1,
        )
        with pytest.raises(RuntimeCoreInvariantError, match="not active"):
            engine.submit_job_to_function("fn-legacy", job)

    def test_retired_function_cannot_be_reactivated(self) -> None:
        reg = FunctionRegistry(clock=_fixed_clock(_T0))
        fn = ServiceFunctionTemplate(
            function_id="fn-retired",
            name="Retired",
            function_type=FunctionType.CUSTOM,
            description="Done",
            created_at=_T0,
        )
        reg.register_function(fn)
        reg.retire_function("fn-retired")
        with pytest.raises(RuntimeCoreInvariantError, match="cannot activate"):
            reg.activate_function("fn-retired")


# ============================================================
# Scenario 4: SLA breach detection across multiple jobs
# ============================================================


class TestSlaBulkDetection:
    """Evaluate SLA across many jobs to detect breaches."""

    def test_mixed_sla_statuses_across_jobs(self) -> None:
        reg = FunctionRegistry(clock=_fixed_clock(_T0))
        fn = ServiceFunctionTemplate(
            function_id="fn-sla",
            name="SLA Test",
            function_type=FunctionType.CODE_REVIEW,
            description="Code review with SLA",
            created_at=_T0,
        )
        reg.register_function(fn)
        reg.register_sla_profile(FunctionSlaProfile(
            function_id="fn-sla",
            target_completion_minutes=60,
            approval_latency_minutes=10,
            escalation_threshold_minutes=30,
        ))

        engine = FunctionEngine(registry=reg, clock=_fixed_clock())

        # 5 jobs created at different times
        jobs = [
            (JobDescriptor(job_id=f"j-{i}", name=f"J{i}", description=f"Job {i}",
                           priority=JobPriority.NORMAL, created_at=t), t)
            for i, t in enumerate([_T0, _T_20MIN, _T_45MIN, _T_50MIN, _T_1H])
        ]

        # Evaluate at T+1h10m
        records = engine.evaluate_function_sla("fn-sla", jobs, _T_1H10)

        # j-0: created T0, elapsed 70min > 60 => BREACHED
        assert records[0].sla_status == SlaStatus.BREACHED
        # j-1: created T+20, elapsed 50min, 50/60=83% => AT_RISK
        assert records[1].sla_status == SlaStatus.AT_RISK
        # j-2: created T+45, elapsed 25min, 25/60=42% => ON_TRACK
        assert records[2].sla_status == SlaStatus.ON_TRACK
        # j-3: created T+50, elapsed 20min, 20/60=33% => ON_TRACK
        assert records[3].sla_status == SlaStatus.ON_TRACK
        # j-4: created T+1h, elapsed 10min, 10/60=17% => ON_TRACK
        assert records[4].sla_status == SlaStatus.ON_TRACK

    def test_all_jobs_breached(self) -> None:
        reg = FunctionRegistry(clock=_fixed_clock(_T0))
        fn = ServiceFunctionTemplate(
            function_id="fn-breach",
            name="Breach Test",
            function_type=FunctionType.APPROVAL_DESK,
            description="All breached",
            created_at=_T0,
        )
        reg.register_function(fn)
        reg.register_sla_profile(FunctionSlaProfile(
            function_id="fn-breach",
            target_completion_minutes=10,
            approval_latency_minutes=5,
            escalation_threshold_minutes=8,
        ))
        engine = FunctionEngine(registry=reg, clock=_fixed_clock())
        jobs = [
            (JobDescriptor(job_id=f"jb-{i}", name=f"B{i}", description=f"Breach {i}",
                           priority=JobPriority.HIGH, created_at=_T0), _T0)
            for i in range(3)
        ]
        # Evaluate at T+1h (all 3 breach the 10-minute SLA)
        records = engine.evaluate_function_sla("fn-breach", jobs, _T_1H)
        assert all(r.sla_status == SlaStatus.BREACHED for r in records)
        assert len(records) == 3


# ============================================================
# Scenario 5: Metrics aggregation correctness
# ============================================================


class TestMetricsAggregationScenario:
    """Verify correct metric aggregation over a mixed set of outcomes."""

    def test_mixed_outcomes_produce_correct_aggregation(self) -> None:
        timestamps = [_T1, _T2, _T3, _T4, _T5, _T_20MIN]
        clock = _make_clock(timestamps)
        reg = FunctionRegistry(clock=_fixed_clock())
        engine = FunctionEngine(registry=reg, clock=clock)

        # 5 outcomes: 3 completed, 2 failed (1 escalated, 1 with drift)
        outcomes = [
            engine.record_outcome("fn-m", "j1", completed=True, completion_minutes=10),
            engine.record_outcome("fn-m", "j2", completed=True, completion_minutes=20),
            engine.record_outcome("fn-m", "j3", completed=False, completion_minutes=0, escalated=True),
            engine.record_outcome("fn-m", "j4", completed=True, completion_minutes=30),
            engine.record_outcome("fn-m", "j5", completed=False, completion_minutes=0, drift_detected=True),
        ]

        metrics_engine = FunctionEngine(registry=reg, clock=_fixed_clock(_T_1H))
        metrics = metrics_engine.compute_metrics("fn-m", outcomes, _T0, _T_1H)

        assert metrics.total_jobs == 5
        assert metrics.completed_jobs == 3
        assert metrics.failed_jobs == 2
        assert metrics.avg_completion_minutes == 20.0  # (10+20+30)/3
        assert metrics.escalation_count == 1
        assert metrics.drift_count == 1
        assert metrics.captured_at == _T_1H

    def test_all_failed_outcomes(self) -> None:
        clock = _make_clock([_T1, _T2, _T3])
        reg = FunctionRegistry(clock=_fixed_clock())
        engine = FunctionEngine(registry=reg, clock=clock)

        outcomes = [
            engine.record_outcome("fn-f", "j1", completed=False, completion_minutes=0),
            engine.record_outcome("fn-f", "j2", completed=False, completion_minutes=0, escalated=True),
        ]

        metrics_engine = FunctionEngine(registry=reg, clock=_fixed_clock(_T_1H))
        metrics = metrics_engine.compute_metrics("fn-f", outcomes, _T0, _T_1H)

        assert metrics.total_jobs == 2
        assert metrics.completed_jobs == 0
        assert metrics.failed_jobs == 2
        assert metrics.avg_completion_minutes == 0.0
        assert metrics.escalation_count == 1

    def test_period_filtering_excludes_outside_outcomes(self) -> None:
        clock = _make_clock([_T1, _T_2H])
        reg = FunctionRegistry(clock=_fixed_clock())
        engine = FunctionEngine(registry=reg, clock=clock)

        o_in = engine.record_outcome("fn-p", "j1", completed=True, completion_minutes=15)
        o_out = engine.record_outcome("fn-p", "j2", completed=True, completion_minutes=25)

        metrics_engine = FunctionEngine(registry=reg, clock=_fixed_clock(_T_3H))
        # Period T0..T_1H includes o_in (T1) but excludes o_out (T_2H)
        metrics = metrics_engine.compute_metrics("fn-p", [o_in, o_out], _T0, _T_1H)
        assert metrics.total_jobs == 1
        assert metrics.avg_completion_minutes == 15.0


# ============================================================
# Scenario 6: Playbook binding and execution
# ============================================================


class TestPlaybookScenario:
    """Playbook lifecycle: register, bind to function, execute."""

    def test_playbook_bound_to_function(self) -> None:
        pb = FunctionPlaybook()
        desc = PlaybookDescriptor(
            playbook_id="pb-ir",
            function_id="fn-incident",
            name="Incident Triage Playbook",
            workflow_id="wf-triage",
            skill_ids=("skill-detect", "skill-classify", "skill-mitigate"),
            description="Standard incident triage sequence",
        )
        pb.register_playbook(desc)

        # Verify lookup
        result = pb.get_playbook("pb-ir")
        assert result is not None
        assert result.function_id == "fn-incident"
        assert result.workflow_id == "wf-triage"
        assert len(result.skill_ids) == 3

    def test_playbook_execution_returns_descriptor(self) -> None:
        pb = FunctionPlaybook()
        desc = PlaybookDescriptor(
            playbook_id="pb-exec",
            function_id="fn-doc",
            name="Doc Processing",
            skill_ids=("skill-parse", "skill-validate"),
        )
        pb.register_playbook(desc)
        result = pb.execute_playbook("pb-exec", "job-doc-42")
        assert result.playbook_id == "pb-exec"
        assert result.skill_ids == ("skill-parse", "skill-validate")

    def test_multiple_playbooks_per_function(self) -> None:
        pb = FunctionPlaybook()
        pb.register_playbook(PlaybookDescriptor(
            playbook_id="pb-a", function_id="fn-1", name="PB A", skill_ids=("sk-1",),
        ))
        pb.register_playbook(PlaybookDescriptor(
            playbook_id="pb-b", function_id="fn-1", name="PB B", skill_ids=("sk-2",),
        ))
        pb.register_playbook(PlaybookDescriptor(
            playbook_id="pb-c", function_id="fn-2", name="PB C", workflow_id="wf-1",
        ))
        fn1_playbooks = pb.list_playbooks_for_function("fn-1")
        assert len(fn1_playbooks) == 2
        fn2_playbooks = pb.list_playbooks_for_function("fn-2")
        assert len(fn2_playbooks) == 1


# ============================================================
# Scenario 7: End-to-end with playbook and metrics
# ============================================================


class TestEndToEndWithPlaybook:
    """Full E2E: register function, set SLA, create playbook, submit job,
    run playbook, record outcome, compute metrics."""

    def test_complete_workflow(self) -> None:
        clock = _make_clock([_T0, _T1, _T2, _T3, _T4, _T5])
        reg = FunctionRegistry(clock=_fixed_clock(_T0))

        # Register function
        fn = ServiceFunctionTemplate(
            function_id="fn-e2e",
            name="E2E Function",
            function_type=FunctionType.DEPLOYMENT_REVIEW,
            description="End-to-end test function",
            created_at=_T0,
        )
        reg.register_function(fn)
        reg.register_sla_profile(FunctionSlaProfile(
            function_id="fn-e2e",
            target_completion_minutes=60,
            approval_latency_minutes=10,
            escalation_threshold_minutes=30,
        ))
        reg.activate_function("fn-e2e")

        # Create playbook
        pb = FunctionPlaybook()
        pb.register_playbook(PlaybookDescriptor(
            playbook_id="pb-e2e",
            function_id="fn-e2e",
            name="Deploy Review Playbook",
            workflow_id="wf-deploy-check",
            skill_ids=("skill-lint", "skill-test", "skill-approve"),
        ))

        # Submit job
        engine = FunctionEngine(registry=reg, clock=clock)
        job = JobDescriptor(
            job_id="job-e2e", name="Deploy v2.0",
            description="Review deployment v2.0",
            priority=JobPriority.HIGH, created_at=_T0,
        )
        entry = engine.submit_job_to_function("fn-e2e", job)
        assert entry.job_id == "job-e2e"

        # Execute playbook (returns descriptor)
        desc = pb.execute_playbook("pb-e2e", "job-e2e")
        assert desc.workflow_id == "wf-deploy-check"

        # Record outcome
        outcome = engine.record_outcome(
            "fn-e2e", "job-e2e",
            completed=True, completion_minutes=42,
        )

        # Compute metrics
        metrics = engine.compute_metrics("fn-e2e", [outcome], _T0, _T5)
        assert metrics.total_jobs == 1
        assert metrics.completed_jobs == 1
        assert metrics.avg_completion_minutes == 42.0
