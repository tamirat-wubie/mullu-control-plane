"""Tests for the function runtime core engine — FunctionRegistry, FunctionEngine, and FunctionPlaybook."""

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


# --- Helpers ---

_T0 = "2025-06-01T12:00:00+00:00"
_T1 = "2025-06-01T12:00:01+00:00"
_T2 = "2025-06-01T12:00:02+00:00"
_T3 = "2025-06-01T12:00:03+00:00"
_T4 = "2025-06-01T12:00:04+00:00"
_T5 = "2025-06-01T12:00:05+00:00"
_T_30MIN = "2025-06-01T12:30:00+00:00"
_T_50MIN = "2025-06-01T12:50:00+00:00"
_T_70MIN = "2025-06-01T13:10:00+00:00"
_T_1H = "2025-06-01T13:00:00+00:00"
_T_2H = "2025-06-01T14:00:00+00:00"


def _make_clock(times: list[str]):
    """Return a clock function that yields successive timestamps."""
    it = iter(times)

    def clock() -> str:
        return next(it)

    return clock


def _fixed_clock(t: str = _T0):
    """Return a clock that always returns the same time."""
    return lambda: t


def _make_function(
    function_id: str = "fn-incident",
    name: str = "Incident Response",
    function_type: FunctionType = FunctionType.INCIDENT_RESPONSE,
    description: str = "Handles production incidents",
    created_at: str = _T0,
) -> ServiceFunctionTemplate:
    return ServiceFunctionTemplate(
        function_id=function_id,
        name=name,
        function_type=function_type,
        description=description,
        created_at=created_at,
    )


def _make_job(
    job_id: str = "job-1",
    name: str = "Fix outage",
    description: str = "Resolve the production outage",
    priority: JobPriority = JobPriority.HIGH,
    created_at: str = _T0,
    deadline: str | None = None,
    sla_target_minutes: int | None = None,
) -> JobDescriptor:
    return JobDescriptor(
        job_id=job_id,
        name=name,
        description=description,
        priority=priority,
        created_at=created_at,
        deadline=deadline,
        sla_target_minutes=sla_target_minutes,
    )


def _make_sla_profile(
    function_id: str = "fn-incident",
    target_completion_minutes: int = 60,
    approval_latency_minutes: int = 10,
    escalation_threshold_minutes: int = 30,
) -> FunctionSlaProfile:
    return FunctionSlaProfile(
        function_id=function_id,
        target_completion_minutes=target_completion_minutes,
        approval_latency_minutes=approval_latency_minutes,
        escalation_threshold_minutes=escalation_threshold_minutes,
    )


def _make_queue_profile(
    function_id: str = "fn-incident",
    team_id: str = "team-ops",
    default_role_id: str = "role-responder",
    communication_style: CommunicationStyle = CommunicationStyle.URGENT,
    max_concurrent_jobs: int = 5,
) -> FunctionQueueProfile:
    return FunctionQueueProfile(
        function_id=function_id,
        team_id=team_id,
        default_role_id=default_role_id,
        communication_style=communication_style,
        max_concurrent_jobs=max_concurrent_jobs,
    )


def _make_policy_binding(
    binding_id: str = "bind-1",
    function_id: str = "fn-incident",
    policy_pack_id: str = "pack-prod",
    autonomy_mode: str = "supervised",
    review_required: bool = True,
) -> FunctionPolicyBinding:
    return FunctionPolicyBinding(
        binding_id=binding_id,
        function_id=function_id,
        policy_pack_id=policy_pack_id,
        autonomy_mode=autonomy_mode,
        review_required=review_required,
    )


# ============================================================
# FunctionRegistry tests
# ============================================================


class TestFunctionRegistration:
    """Function registration and lookup."""

    def test_register_and_get_function(self) -> None:
        reg = FunctionRegistry(clock=_fixed_clock())
        tmpl = _make_function()
        result = reg.register_function(tmpl)
        assert result.function_id == "fn-incident"
        assert reg.get_function("fn-incident") is tmpl

    def test_register_duplicate_function_rejected(self) -> None:
        reg = FunctionRegistry(clock=_fixed_clock())
        reg.register_function(_make_function())
        with pytest.raises(RuntimeCoreInvariantError, match="already registered"):
            reg.register_function(_make_function())

    def test_get_missing_function_returns_none(self) -> None:
        reg = FunctionRegistry(clock=_fixed_clock())
        assert reg.get_function("nonexistent") is None

    def test_initial_status_is_draft(self) -> None:
        reg = FunctionRegistry(clock=_fixed_clock())
        reg.register_function(_make_function())
        assert reg.get_function_status("fn-incident") == FunctionStatus.DRAFT

    def test_missing_status_returns_none(self) -> None:
        reg = FunctionRegistry(clock=_fixed_clock())
        assert reg.get_function_status("nonexistent") is None


class TestFunctionLifecycle:
    """Activate and retire lifecycle."""

    def test_activate_function(self) -> None:
        reg = FunctionRegistry(clock=_fixed_clock())
        reg.register_function(_make_function())
        status = reg.activate_function("fn-incident")
        assert status == FunctionStatus.ACTIVE
        assert reg.get_function_status("fn-incident") == FunctionStatus.ACTIVE

    def test_retire_function(self) -> None:
        reg = FunctionRegistry(clock=_fixed_clock())
        reg.register_function(_make_function())
        reg.activate_function("fn-incident")
        status = reg.retire_function("fn-incident")
        assert status == FunctionStatus.RETIRED
        assert reg.get_function_status("fn-incident") == FunctionStatus.RETIRED

    def test_activate_retired_function_rejected(self) -> None:
        reg = FunctionRegistry(clock=_fixed_clock())
        reg.register_function(_make_function())
        reg.retire_function("fn-incident")
        with pytest.raises(RuntimeCoreInvariantError, match="cannot activate a retired"):
            reg.activate_function("fn-incident")

    def test_activate_missing_function_rejected(self) -> None:
        reg = FunctionRegistry(clock=_fixed_clock())
        with pytest.raises(RuntimeCoreInvariantError, match="function not found"):
            reg.activate_function("nonexistent")

    def test_retire_missing_function_rejected(self) -> None:
        reg = FunctionRegistry(clock=_fixed_clock())
        with pytest.raises(RuntimeCoreInvariantError, match="function not found"):
            reg.retire_function("nonexistent")

    def test_list_active_functions_filters_correctly(self) -> None:
        reg = FunctionRegistry(clock=_fixed_clock())
        fn1 = _make_function(function_id="fn-1", name="Fn One")
        fn2 = _make_function(function_id="fn-2", name="Fn Two")
        fn3 = _make_function(function_id="fn-3", name="Fn Three")
        reg.register_function(fn1)
        reg.register_function(fn2)
        reg.register_function(fn3)
        reg.activate_function("fn-1")
        reg.activate_function("fn-2")
        # fn-3 stays draft
        active = reg.list_active_functions()
        active_ids = {f.function_id for f in active}
        assert active_ids == {"fn-1", "fn-2"}

    def test_list_active_empty_when_none_active(self) -> None:
        reg = FunctionRegistry(clock=_fixed_clock())
        reg.register_function(_make_function())
        assert reg.list_active_functions() == []

    def test_retire_removes_from_active_list(self) -> None:
        reg = FunctionRegistry(clock=_fixed_clock())
        reg.register_function(_make_function())
        reg.activate_function("fn-incident")
        assert len(reg.list_active_functions()) == 1
        reg.retire_function("fn-incident")
        assert len(reg.list_active_functions()) == 0


class TestPolicyBindingRegistration:
    """Policy binding registration and lookup."""

    def test_register_and_get_policy_binding(self) -> None:
        reg = FunctionRegistry(clock=_fixed_clock())
        binding = _make_policy_binding()
        result = reg.register_policy_binding(binding)
        assert result.binding_id == "bind-1"
        assert reg.get_policy_binding("bind-1") is binding

    def test_duplicate_policy_binding_rejected(self) -> None:
        reg = FunctionRegistry(clock=_fixed_clock())
        reg.register_policy_binding(_make_policy_binding())
        with pytest.raises(RuntimeCoreInvariantError, match="already registered"):
            reg.register_policy_binding(_make_policy_binding())

    def test_get_bindings_for_function(self) -> None:
        reg = FunctionRegistry(clock=_fixed_clock())
        b1 = _make_policy_binding(binding_id="b-1", function_id="fn-1")
        b2 = _make_policy_binding(binding_id="b-2", function_id="fn-1")
        b3 = _make_policy_binding(binding_id="b-3", function_id="fn-2")
        reg.register_policy_binding(b1)
        reg.register_policy_binding(b2)
        reg.register_policy_binding(b3)
        bindings = reg.get_bindings_for_function("fn-1")
        assert len(bindings) == 2
        assert all(b.function_id == "fn-1" for b in bindings)


class TestSlaProfileRegistration:
    """SLA profile registration and lookup."""

    def test_register_and_get_sla_profile(self) -> None:
        reg = FunctionRegistry(clock=_fixed_clock())
        profile = _make_sla_profile()
        result = reg.register_sla_profile(profile)
        assert result.function_id == "fn-incident"
        assert reg.get_sla_profile("fn-incident") is profile

    def test_duplicate_sla_profile_rejected(self) -> None:
        reg = FunctionRegistry(clock=_fixed_clock())
        reg.register_sla_profile(_make_sla_profile())
        with pytest.raises(RuntimeCoreInvariantError, match="already registered"):
            reg.register_sla_profile(_make_sla_profile())

    def test_get_sla_for_function(self) -> None:
        reg = FunctionRegistry(clock=_fixed_clock())
        profile = _make_sla_profile()
        reg.register_sla_profile(profile)
        assert reg.get_sla_for_function("fn-incident") is profile
        assert reg.get_sla_for_function("nonexistent") is None


class TestQueueProfileRegistration:
    """Queue profile registration and lookup."""

    def test_register_and_get_queue_profile(self) -> None:
        reg = FunctionRegistry(clock=_fixed_clock())
        profile = _make_queue_profile()
        result = reg.register_queue_profile(profile)
        assert result.function_id == "fn-incident"
        assert reg.get_queue_profile("fn-incident") is profile

    def test_duplicate_queue_profile_rejected(self) -> None:
        reg = FunctionRegistry(clock=_fixed_clock())
        reg.register_queue_profile(_make_queue_profile())
        with pytest.raises(RuntimeCoreInvariantError, match="already registered"):
            reg.register_queue_profile(_make_queue_profile())

    def test_get_queue_for_function(self) -> None:
        reg = FunctionRegistry(clock=_fixed_clock())
        profile = _make_queue_profile()
        reg.register_queue_profile(profile)
        assert reg.get_queue_for_function("fn-incident") is profile
        assert reg.get_queue_for_function("nonexistent") is None


# ============================================================
# FunctionEngine tests
# ============================================================


class TestSubmitJobToFunction:
    """Submit job to active function."""

    def test_submit_to_active_function(self) -> None:
        reg = FunctionRegistry(clock=_fixed_clock())
        reg.register_function(_make_function())
        reg.activate_function("fn-incident")
        engine = FunctionEngine(registry=reg, clock=_fixed_clock(_T1))
        job = _make_job()
        entry = engine.submit_job_to_function("fn-incident", job)
        assert isinstance(entry, WorkQueueEntry)
        assert entry.job_id == "job-1"
        assert entry.priority == JobPriority.HIGH
        assert entry.enqueued_at == _T1

    def test_submit_to_retired_function_rejected(self) -> None:
        reg = FunctionRegistry(clock=_fixed_clock())
        reg.register_function(_make_function())
        reg.activate_function("fn-incident")
        reg.retire_function("fn-incident")
        engine = FunctionEngine(registry=reg, clock=_fixed_clock(_T1))
        job = _make_job()
        with pytest.raises(RuntimeCoreInvariantError, match="not active"):
            engine.submit_job_to_function("fn-incident", job)

    def test_submit_to_draft_function_rejected(self) -> None:
        reg = FunctionRegistry(clock=_fixed_clock())
        reg.register_function(_make_function())
        engine = FunctionEngine(registry=reg, clock=_fixed_clock(_T1))
        job = _make_job()
        with pytest.raises(RuntimeCoreInvariantError, match="not active"):
            engine.submit_job_to_function("fn-incident", job)

    def test_submit_to_nonexistent_function_rejected(self) -> None:
        reg = FunctionRegistry(clock=_fixed_clock())
        engine = FunctionEngine(registry=reg, clock=_fixed_clock(_T1))
        job = _make_job()
        with pytest.raises(RuntimeCoreInvariantError, match="function not found"):
            engine.submit_job_to_function("nonexistent", job)

    def test_submit_with_queue_profile_assigns_team(self) -> None:
        reg = FunctionRegistry(clock=_fixed_clock())
        reg.register_function(_make_function())
        reg.activate_function("fn-incident")
        reg.register_queue_profile(_make_queue_profile(team_id="team-alpha"))
        engine = FunctionEngine(registry=reg, clock=_fixed_clock(_T1))
        job = _make_job()
        entry = engine.submit_job_to_function("fn-incident", job)
        assert entry.assigned_to_team_id == "team-alpha"

    def test_submit_without_queue_profile_no_team(self) -> None:
        reg = FunctionRegistry(clock=_fixed_clock())
        reg.register_function(_make_function())
        reg.activate_function("fn-incident")
        engine = FunctionEngine(registry=reg, clock=_fixed_clock(_T1))
        job = _make_job()
        entry = engine.submit_job_to_function("fn-incident", job)
        assert entry.assigned_to_team_id is None


class TestSlaEvaluation:
    """SLA evaluation."""

    def test_sla_on_track(self) -> None:
        reg = FunctionRegistry(clock=_fixed_clock())
        reg.register_function(_make_function())
        reg.register_sla_profile(_make_sla_profile(target_completion_minutes=60))
        engine = FunctionEngine(registry=reg, clock=_fixed_clock())
        job = _make_job(created_at=_T0)
        records = engine.evaluate_function_sla("fn-incident", [(job, _T0)], _T_30MIN)
        assert len(records) == 1
        assert records[0].sla_status == SlaStatus.ON_TRACK

    def test_sla_at_risk(self) -> None:
        reg = FunctionRegistry(clock=_fixed_clock())
        reg.register_function(_make_function())
        reg.register_sla_profile(_make_sla_profile(target_completion_minutes=60))
        engine = FunctionEngine(registry=reg, clock=_fixed_clock())
        job = _make_job(created_at=_T0)
        records = engine.evaluate_function_sla("fn-incident", [(job, _T0)], _T_50MIN)
        assert records[0].sla_status == SlaStatus.AT_RISK

    def test_sla_breached(self) -> None:
        reg = FunctionRegistry(clock=_fixed_clock())
        reg.register_function(_make_function())
        reg.register_sla_profile(_make_sla_profile(target_completion_minutes=60))
        engine = FunctionEngine(registry=reg, clock=_fixed_clock())
        job = _make_job(created_at=_T0)
        records = engine.evaluate_function_sla("fn-incident", [(job, _T0)], _T_70MIN)
        assert records[0].sla_status == SlaStatus.BREACHED

    def test_sla_not_applicable_without_profile(self) -> None:
        reg = FunctionRegistry(clock=_fixed_clock())
        reg.register_function(_make_function())
        engine = FunctionEngine(registry=reg, clock=_fixed_clock())
        job = _make_job(created_at=_T0)
        records = engine.evaluate_function_sla("fn-incident", [(job, _T0)], _T_30MIN)
        assert records[0].sla_status == SlaStatus.NOT_APPLICABLE

    def test_sla_multiple_jobs(self) -> None:
        reg = FunctionRegistry(clock=_fixed_clock())
        reg.register_function(_make_function())
        reg.register_sla_profile(_make_sla_profile(target_completion_minutes=60))
        engine = FunctionEngine(registry=reg, clock=_fixed_clock())
        job1 = _make_job(job_id="j1", name="J1", created_at=_T0)
        job2 = _make_job(job_id="j2", name="J2", created_at=_T_30MIN)
        # Evaluate at T+70min from T0; j1 is breached, j2 is on_track (40min from creation)
        records = engine.evaluate_function_sla(
            "fn-incident",
            [(job1, _T0), (job2, _T_30MIN)],
            _T_70MIN,
        )
        assert records[0].sla_status == SlaStatus.BREACHED
        assert records[1].sla_status == SlaStatus.ON_TRACK


class TestOutcomeRecording:
    """Outcome recording."""

    def test_record_completed_outcome(self) -> None:
        reg = FunctionRegistry(clock=_fixed_clock())
        engine = FunctionEngine(registry=reg, clock=_fixed_clock(_T1))
        outcome = engine.record_outcome(
            "fn-incident", "job-1",
            completed=True, completion_minutes=45,
        )
        assert isinstance(outcome, FunctionOutcomeRecord)
        assert outcome.function_id == "fn-incident"
        assert outcome.job_id == "job-1"
        assert outcome.completed is True
        assert outcome.completion_minutes == 45
        assert outcome.escalated is False
        assert outcome.drift_detected is False
        assert outcome.recorded_at == _T1

    def test_record_failed_outcome(self) -> None:
        reg = FunctionRegistry(clock=_fixed_clock())
        engine = FunctionEngine(registry=reg, clock=_fixed_clock(_T2))
        outcome = engine.record_outcome(
            "fn-incident", "job-2",
            completed=False, completion_minutes=0,
            escalated=True, drift_detected=True,
        )
        assert outcome.completed is False
        assert outcome.escalated is True
        assert outcome.drift_detected is True

    def test_record_outcome_unique_ids(self) -> None:
        clock = _make_clock([_T1, _T2])
        reg = FunctionRegistry(clock=_fixed_clock())
        engine = FunctionEngine(registry=reg, clock=clock)
        o1 = engine.record_outcome("fn-1", "j-1", completed=True, completion_minutes=10)
        o2 = engine.record_outcome("fn-1", "j-2", completed=True, completion_minutes=20)
        assert o1.outcome_id != o2.outcome_id


class TestMetricsComputation:
    """Metrics computation."""

    def _make_outcomes(self, clock) -> list[FunctionOutcomeRecord]:
        reg = FunctionRegistry(clock=_fixed_clock())
        engine = FunctionEngine(registry=reg, clock=clock)
        outcomes = [
            engine.record_outcome("fn-1", "j-1", completed=True, completion_minutes=30),
            engine.record_outcome("fn-1", "j-2", completed=True, completion_minutes=60),
            engine.record_outcome("fn-1", "j-3", completed=False, completion_minutes=0, escalated=True),
            engine.record_outcome("fn-1", "j-4", completed=True, completion_minutes=45, drift_detected=True),
        ]
        return outcomes

    def test_metrics_total_jobs(self) -> None:
        clock = _make_clock([_T1, _T2, _T3, _T4, _T5])
        outcomes = self._make_outcomes(clock)
        reg = FunctionRegistry(clock=_fixed_clock())
        engine = FunctionEngine(registry=reg, clock=_fixed_clock(_T5))
        metrics = engine.compute_metrics("fn-1", outcomes, _T0, _T5)
        assert metrics.total_jobs == 4

    def test_metrics_completed_and_failed(self) -> None:
        clock = _make_clock([_T1, _T2, _T3, _T4, _T5])
        outcomes = self._make_outcomes(clock)
        reg = FunctionRegistry(clock=_fixed_clock())
        engine = FunctionEngine(registry=reg, clock=_fixed_clock(_T5))
        metrics = engine.compute_metrics("fn-1", outcomes, _T0, _T5)
        assert metrics.completed_jobs == 3
        assert metrics.failed_jobs == 1

    def test_metrics_avg_completion_minutes(self) -> None:
        clock = _make_clock([_T1, _T2, _T3, _T4, _T5])
        outcomes = self._make_outcomes(clock)
        reg = FunctionRegistry(clock=_fixed_clock())
        engine = FunctionEngine(registry=reg, clock=_fixed_clock(_T5))
        metrics = engine.compute_metrics("fn-1", outcomes, _T0, _T5)
        # avg of 30, 60, 45 = 45.0
        assert metrics.avg_completion_minutes == 45.0

    def test_metrics_escalation_count(self) -> None:
        clock = _make_clock([_T1, _T2, _T3, _T4, _T5])
        outcomes = self._make_outcomes(clock)
        reg = FunctionRegistry(clock=_fixed_clock())
        engine = FunctionEngine(registry=reg, clock=_fixed_clock(_T5))
        metrics = engine.compute_metrics("fn-1", outcomes, _T0, _T5)
        assert metrics.escalation_count == 1

    def test_metrics_drift_count(self) -> None:
        clock = _make_clock([_T1, _T2, _T3, _T4, _T5])
        outcomes = self._make_outcomes(clock)
        reg = FunctionRegistry(clock=_fixed_clock())
        engine = FunctionEngine(registry=reg, clock=_fixed_clock(_T5))
        metrics = engine.compute_metrics("fn-1", outcomes, _T0, _T5)
        assert metrics.drift_count == 1

    def test_metrics_empty_outcomes(self) -> None:
        reg = FunctionRegistry(clock=_fixed_clock())
        engine = FunctionEngine(registry=reg, clock=_fixed_clock(_T1))
        metrics = engine.compute_metrics("fn-1", [], _T0, _T5)
        assert metrics.total_jobs == 0
        assert metrics.completed_jobs == 0
        assert metrics.failed_jobs == 0
        assert metrics.avg_completion_minutes == 0.0

    def test_metrics_filters_by_period(self) -> None:
        # Only outcomes within period are counted
        clock = _make_clock([_T1, _T_1H])
        reg = FunctionRegistry(clock=_fixed_clock())
        engine = FunctionEngine(registry=reg, clock=clock)
        o1 = engine.record_outcome("fn-1", "j-1", completed=True, completion_minutes=10)
        o2 = engine.record_outcome("fn-1", "j-2", completed=True, completion_minutes=20)

        compute_engine = FunctionEngine(registry=reg, clock=_fixed_clock(_T_2H))
        # Period only covers T0..T2 (includes o1 at T1, excludes o2 at T+1h)
        metrics = compute_engine.compute_metrics("fn-1", [o1, o2], _T0, _T2)
        assert metrics.total_jobs == 1
        assert metrics.completed_jobs == 1


class TestClockDeterminism:
    """Clock determinism tests."""

    def test_submit_uses_clock(self) -> None:
        reg = FunctionRegistry(clock=_fixed_clock())
        reg.register_function(_make_function())
        reg.activate_function("fn-incident")
        engine = FunctionEngine(registry=reg, clock=_fixed_clock(_T3))
        job = _make_job()
        entry = engine.submit_job_to_function("fn-incident", job)
        assert entry.enqueued_at == _T3

    def test_outcome_uses_clock(self) -> None:
        reg = FunctionRegistry(clock=_fixed_clock())
        engine = FunctionEngine(registry=reg, clock=_fixed_clock(_T4))
        outcome = engine.record_outcome("fn-1", "j-1", completed=True, completion_minutes=10)
        assert outcome.recorded_at == _T4

    def test_metrics_uses_clock_for_captured_at(self) -> None:
        reg = FunctionRegistry(clock=_fixed_clock())
        engine = FunctionEngine(registry=reg, clock=_fixed_clock(_T5))
        metrics = engine.compute_metrics("fn-1", [], _T0, _T4)
        assert metrics.captured_at == _T5


# ============================================================
# FunctionPlaybook tests
# ============================================================


class TestPlaybookRegistration:
    """Playbook creation and lookup."""

    def test_register_and_get_playbook(self) -> None:
        pb = FunctionPlaybook()
        desc = PlaybookDescriptor(
            playbook_id="pb-1",
            function_id="fn-incident",
            name="Incident Playbook",
            workflow_id="wf-triage",
            skill_ids=("skill-detect", "skill-mitigate"),
            description="Standard incident response",
        )
        result = pb.register_playbook(desc)
        assert result.playbook_id == "pb-1"
        assert pb.get_playbook("pb-1") is desc

    def test_duplicate_playbook_rejected(self) -> None:
        pb = FunctionPlaybook()
        desc = PlaybookDescriptor(playbook_id="pb-1", function_id="fn-1", name="PB", skill_ids=("sk-1",))
        pb.register_playbook(desc)
        with pytest.raises(RuntimeCoreInvariantError, match="already registered"):
            pb.register_playbook(desc)

    def test_get_missing_playbook_returns_none(self) -> None:
        pb = FunctionPlaybook()
        assert pb.get_playbook("nonexistent") is None

    def test_list_playbooks_for_function(self) -> None:
        pb = FunctionPlaybook()
        pb.register_playbook(PlaybookDescriptor(playbook_id="pb-1", function_id="fn-1", name="PB1", skill_ids=("sk-1",)))
        pb.register_playbook(PlaybookDescriptor(playbook_id="pb-2", function_id="fn-1", name="PB2", skill_ids=("sk-2",)))
        pb.register_playbook(PlaybookDescriptor(playbook_id="pb-3", function_id="fn-2", name="PB3", workflow_id="wf-1"))
        results = pb.list_playbooks_for_function("fn-1")
        assert len(results) == 2
        assert all(p.function_id == "fn-1" for p in results)

    def test_execute_playbook_returns_descriptor(self) -> None:
        pb = FunctionPlaybook()
        desc = PlaybookDescriptor(playbook_id="pb-1", function_id="fn-1", name="PB", skill_ids=("sk-1",))
        pb.register_playbook(desc)
        result = pb.execute_playbook("pb-1", "job-1")
        assert result is desc

    def test_execute_missing_playbook_raises(self) -> None:
        pb = FunctionPlaybook()
        with pytest.raises(RuntimeCoreInvariantError, match="playbook not found"):
            pb.execute_playbook("nonexistent", "job-1")

    def test_execute_playbook_validates_inputs(self) -> None:
        pb = FunctionPlaybook()
        with pytest.raises(RuntimeCoreInvariantError):
            pb.execute_playbook("", "job-1")
        with pytest.raises(RuntimeCoreInvariantError):
            pb.execute_playbook("pb-1", "")
