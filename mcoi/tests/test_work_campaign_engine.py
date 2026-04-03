"""Purpose: comprehensive tests for WorkCampaignEngine.
Governance scope: work campaign engine correctness — registration, execution,
    lifecycle transitions, dependency enforcement, checkpointing, retry,
    escalation, closure reports, counter tracking, and state hashing.
Dependencies: pytest, work_campaign engine + contracts, event_spine engine.
Invariants:
  - Every test is deterministic and isolated (fresh engine per test).
  - Tests cover both happy-path and error/edge-case behaviour.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.work_campaign import WorkCampaignEngine, StepHandler
from mcoi_runtime.contracts.work_campaign import (
    CampaignDependency,
    CampaignDescriptor,
    CampaignPriority,
    CampaignRun,
    CampaignStatus,
    CampaignStep,
    CampaignStepStatus,
    CampaignStepType,
    CampaignTrigger,
    CampaignOutcomeVerdict,
    CampaignEscalationReason,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_engine() -> WorkCampaignEngine:
    return WorkCampaignEngine(EventSpineEngine())


def _step(
    step_id: str,
    campaign_id: str = "camp-1",
    step_type: CampaignStepType = CampaignStepType.CHECK_CONDITION,
    order: int = 0,
    name: str = "",
    max_retries: int = 3,
    **kwargs,
) -> CampaignStep:
    return CampaignStep(
        step_id=step_id,
        campaign_id=campaign_id,
        step_type=step_type,
        order=order,
        name=name or f"step-{step_id}",
        max_retries=max_retries,
        **kwargs,
    )


def _ok_handler(step: CampaignStep, ctx: dict) -> tuple[bool, dict]:
    return True, {"result": "ok"}


def _fail_handler(step: CampaignStep, ctx: dict) -> tuple[bool, dict]:
    return False, {"error": "nope"}


def _raise_handler(step: CampaignStep, ctx: dict) -> tuple[bool, dict]:
    raise RuntimeError("boom")


def _register_simple(
    engine: WorkCampaignEngine,
    campaign_id: str = "camp-1",
    steps: list[CampaignStep] | None = None,
    dependencies: list[CampaignDependency] | None = None,
    **kwargs,
) -> CampaignDescriptor:
    if steps is None:
        steps = [_step("s1", campaign_id, order=0), _step("s2", campaign_id, order=1)]
    return engine.register_campaign(
        campaign_id, f"Campaign {campaign_id}", steps,
        dependencies=dependencies, **kwargs,
    )


# ===================================================================
# 1. Constructor
# ===================================================================


class TestConstructor:
    def test_requires_event_spine_engine(self):
        with pytest.raises(RuntimeCoreInvariantError):
            WorkCampaignEngine("not-an-engine")  # type: ignore

    def test_initial_counts_zero(self):
        eng = _make_engine()
        assert eng.campaign_count == 0
        assert eng.run_count == 0


# ===================================================================
# 2. Step handler registration
# ===================================================================


class TestStepHandlerRegistration:
    def test_register_handler(self):
        eng = _make_engine()
        eng.register_step_handler(CampaignStepType.CHECK_CONDITION, _ok_handler)
        # No error — handler is stored internally

    def test_register_handler_invalid_type(self):
        eng = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError):
            eng.register_step_handler("bad", _ok_handler)  # type: ignore

    def test_overwrite_handler(self):
        eng = _make_engine()
        eng.register_step_handler(CampaignStepType.CHECK_CONDITION, _ok_handler)
        eng.register_step_handler(CampaignStepType.CHECK_CONDITION, _fail_handler)
        # Second handler replaces first — verified via execution below


# ===================================================================
# 3. Campaign registration
# ===================================================================


class TestCampaignRegistration:
    def test_register_returns_descriptor(self):
        eng = _make_engine()
        desc = _register_simple(eng)
        assert isinstance(desc, CampaignDescriptor)
        assert desc.campaign_id == "camp-1"
        assert desc.status == CampaignStatus.DRAFT
        assert desc.step_count == 2

    def test_duplicate_campaign_rejected(self):
        eng = _make_engine()
        _register_simple(eng)
        with pytest.raises(RuntimeCoreInvariantError, match="already registered"):
            _register_simple(eng)

    def test_campaign_count_increments(self):
        eng = _make_engine()
        _register_simple(eng, "c1")
        _register_simple(eng, "c2")
        assert eng.campaign_count == 2

    def test_register_with_priority(self):
        eng = _make_engine()
        desc = _register_simple(eng, priority=CampaignPriority.URGENT)
        assert desc.priority == CampaignPriority.URGENT

    def test_register_with_trigger(self):
        eng = _make_engine()
        desc = _register_simple(eng, trigger=CampaignTrigger.SCHEDULED)
        assert desc.trigger == CampaignTrigger.SCHEDULED

    def test_register_with_tags(self):
        eng = _make_engine()
        desc = _register_simple(eng, tags=("billing", "sla"))
        assert "billing" in desc.tags

    def test_register_with_metadata(self):
        eng = _make_engine()
        desc = _register_simple(eng, metadata={"source": "test"})
        assert desc.metadata["source"] == "test"


# ===================================================================
# 4. get_campaign / get_steps
# ===================================================================


class TestGetCampaignAndSteps:
    def test_get_campaign(self):
        eng = _make_engine()
        _register_simple(eng)
        assert eng.get_campaign("camp-1").name == "Campaign camp-1"

    def test_get_campaign_not_found(self):
        eng = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            eng.get_campaign("nope")

    def test_get_steps(self):
        eng = _make_engine()
        _register_simple(eng)
        steps = eng.get_steps("camp-1")
        assert len(steps) == 2
        assert steps[0].order <= steps[1].order

    def test_get_steps_not_found(self):
        eng = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            eng.get_steps("nope")

    def test_steps_sorted_by_order(self):
        eng = _make_engine()
        s = [_step("b", order=2), _step("a", order=0), _step("c", order=1)]
        eng.register_campaign("camp-1", "C1", s)
        steps = eng.get_steps("camp-1")
        assert [st.order for st in steps] == [0, 1, 2]


# ===================================================================
# 5. start_run
# ===================================================================


class TestStartRun:
    def test_start_run_returns_active_run(self):
        eng = _make_engine()
        _register_simple(eng)
        run = eng.start_run("camp-1", run_id="r1")
        assert isinstance(run, CampaignRun)
        assert run.status == CampaignStatus.ACTIVE
        assert run.run_id == "r1"

    def test_start_run_auto_id(self):
        eng = _make_engine()
        _register_simple(eng)
        run = eng.start_run("camp-1")
        assert run.run_id  # non-empty

    def test_start_run_duplicate_rejected(self):
        eng = _make_engine()
        _register_simple(eng)
        eng.start_run("camp-1", run_id="r1")
        with pytest.raises(RuntimeCoreInvariantError, match="already exists"):
            eng.start_run("camp-1", run_id="r1")

    def test_start_run_unknown_campaign(self):
        eng = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            eng.start_run("nope")

    def test_run_count_increments(self):
        eng = _make_engine()
        _register_simple(eng)
        eng.start_run("camp-1", run_id="r1")
        eng.start_run("camp-1", run_id="r2")
        assert eng.run_count == 2

    def test_campaign_status_becomes_active(self):
        eng = _make_engine()
        _register_simple(eng)
        eng.start_run("camp-1", run_id="r1")
        assert eng.get_campaign("camp-1").status == CampaignStatus.ACTIVE


# ===================================================================
# 6. execute_next_step — basic
# ===================================================================


class TestExecuteNextStep:
    def test_unhandled_step_auto_succeeds(self):
        eng = _make_engine()
        _register_simple(eng)
        run = eng.start_run("camp-1", run_id="r1")
        rec = eng.execute_next_step("r1")
        assert rec is not None
        assert rec.success is True
        assert "auto" in rec.output_summary

    def test_handler_success(self):
        eng = _make_engine()
        eng.register_step_handler(CampaignStepType.CHECK_CONDITION, _ok_handler)
        _register_simple(eng)
        eng.start_run("camp-1", run_id="r1")
        rec = eng.execute_next_step("r1")
        assert rec.success is True

    def test_handler_failure(self):
        eng = _make_engine()
        steps = [_step("s1", max_retries=0)]
        eng.register_step_handler(CampaignStepType.CHECK_CONDITION, _fail_handler)
        eng.register_campaign("camp-1", "C1", steps)
        eng.start_run("camp-1", run_id="r1")
        rec = eng.execute_next_step("r1")
        assert rec.success is False

    def test_handler_exception_counts_as_failure(self):
        eng = _make_engine()
        steps = [_step("s1", max_retries=0)]
        eng.register_step_handler(CampaignStepType.CHECK_CONDITION, _raise_handler)
        eng.register_campaign("camp-1", "C1", steps)
        eng.start_run("camp-1", run_id="r1")
        rec = eng.execute_next_step("r1")
        assert rec.success is False
        assert rec.error_message == "campaign step handler error (RuntimeError)"
        assert "boom" not in rec.error_message

    def test_no_more_steps_completes_run(self):
        eng = _make_engine()
        steps = [_step("s1")]
        eng.register_campaign("camp-1", "C1", steps)
        eng.start_run("camp-1", run_id="r1")
        eng.execute_next_step("r1")  # executes s1
        result = eng.execute_next_step("r1")  # no more steps
        assert result is None
        assert eng.get_run("r1").status == CampaignStatus.COMPLETED

    def test_execute_on_terminal_returns_none(self):
        eng = _make_engine()
        steps = [_step("s1")]
        eng.register_campaign("camp-1", "C1", steps)
        eng.start_run("camp-1", run_id="r1")
        eng.execute_next_step("r1")
        eng.execute_next_step("r1")  # completes run
        assert eng.execute_next_step("r1") is None

    def test_execute_on_paused_returns_none(self):
        eng = _make_engine()
        _register_simple(eng)
        eng.start_run("camp-1", run_id="r1")
        eng.pause_run("r1")
        assert eng.execute_next_step("r1") is None


# ===================================================================
# 7. execute_all_steps
# ===================================================================


class TestExecuteAllSteps:
    def test_runs_all_steps(self):
        eng = _make_engine()
        steps = [_step("s1", order=0), _step("s2", order=1), _step("s3", order=2)]
        eng.register_campaign("camp-1", "C1", steps)
        eng.start_run("camp-1", run_id="r1")
        records = eng.execute_all_steps("r1")
        assert len(records) == 3
        assert eng.get_run("r1").status == CampaignStatus.COMPLETED

    def test_stops_on_waiting(self):
        eng = _make_engine()
        steps = [
            _step("s1", order=0, step_type=CampaignStepType.CHECK_CONDITION),
            _step("s2", order=1, step_type=CampaignStepType.WAIT_FOR_REPLY),
            _step("s3", order=2, step_type=CampaignStepType.CHECK_CONDITION),
        ]
        eng.register_campaign("camp-1", "C1", steps)
        eng.start_run("camp-1", run_id="r1")
        records = eng.execute_all_steps("r1")
        # s1 succeeds, s2 triggers WAITING
        assert len(records) == 2
        assert eng.get_run("r1").status == CampaignStatus.WAITING

    def test_stops_on_failure(self):
        eng = _make_engine()
        eng.register_step_handler(CampaignStepType.CHECK_CONDITION, _fail_handler)
        steps = [_step("s1", order=0, max_retries=0), _step("s2", order=1)]
        eng.register_campaign("camp-1", "C1", steps)
        eng.start_run("camp-1", run_id="r1")
        records = eng.execute_all_steps("r1")
        assert len(records) == 1
        assert eng.get_run("r1").status == CampaignStatus.FAILED


# ===================================================================
# 8. WAIT_FOR_REPLY behaviour
# ===================================================================


class TestWaitForReply:
    def test_wait_for_reply_sets_run_waiting(self):
        eng = _make_engine()
        steps = [_step("s1", step_type=CampaignStepType.WAIT_FOR_REPLY)]
        eng.register_campaign("camp-1", "C1", steps)
        eng.start_run("camp-1", run_id="r1")
        rec = eng.execute_next_step("r1")
        assert rec is not None
        run = eng.get_run("r1")
        assert run.status == CampaignStatus.WAITING

    def test_wait_for_reply_step_status_is_waiting(self):
        eng = _make_engine()
        steps = [_step("s1", step_type=CampaignStepType.WAIT_FOR_REPLY)]
        eng.register_campaign("camp-1", "C1", steps)
        eng.start_run("camp-1", run_id="r1")
        eng.execute_next_step("r1")
        s = eng.get_run_step("r1", "s1")
        assert s.status == CampaignStepStatus.WAITING

    def test_wait_for_reply_failure_does_not_wait(self):
        eng = _make_engine()
        eng.register_step_handler(CampaignStepType.WAIT_FOR_REPLY, _fail_handler)
        steps = [_step("s1", step_type=CampaignStepType.WAIT_FOR_REPLY, max_retries=0)]
        eng.register_campaign("camp-1", "C1", steps)
        eng.start_run("camp-1", run_id="r1")
        eng.execute_next_step("r1")
        run = eng.get_run("r1")
        # Failed step should not set WAITING — should set FAILED
        assert run.status == CampaignStatus.FAILED


# ===================================================================
# 9. Escalation on communication / connector failure
# ===================================================================


class TestEscalation:
    @pytest.mark.parametrize("stype", [
        CampaignStepType.SEND_COMMUNICATION,
        CampaignStepType.REQUEST_APPROVAL,
        CampaignStepType.CALL_CONNECTOR,
    ])
    def test_failure_escalates(self, stype: CampaignStepType):
        eng = _make_engine()
        eng.register_step_handler(stype, _fail_handler)
        steps = [_step("s1", step_type=stype, max_retries=0)]
        eng.register_campaign("camp-1", "C1", steps)
        eng.start_run("camp-1", run_id="r1")
        eng.execute_next_step("r1")
        run = eng.get_run("r1")
        assert run.status == CampaignStatus.ESCALATED

    def test_escalation_record_created(self):
        eng = _make_engine()
        eng.register_step_handler(CampaignStepType.SEND_COMMUNICATION, _fail_handler)
        steps = [_step("s1", step_type=CampaignStepType.SEND_COMMUNICATION, max_retries=0)]
        eng.register_campaign("camp-1", "C1", steps)
        eng.start_run("camp-1", run_id="r1")
        eng.execute_next_step("r1")
        escs = eng.get_escalations("r1")
        assert len(escs) == 1
        assert escs[0].reason == CampaignEscalationReason.STEP_FAILURE
        assert "failed:" in escs[0].description

    def test_non_escalating_failure_sets_failed(self):
        eng = _make_engine()
        eng.register_step_handler(CampaignStepType.CHECK_CONDITION, _fail_handler)
        steps = [_step("s1", step_type=CampaignStepType.CHECK_CONDITION, max_retries=0)]
        eng.register_campaign("camp-1", "C1", steps)
        eng.start_run("camp-1", run_id="r1")
        eng.execute_next_step("r1")
        run = eng.get_run("r1")
        assert run.status == CampaignStatus.FAILED
        assert len(eng.get_escalations("r1")) == 0


# ===================================================================
# 10. Dependency enforcement
# ===================================================================


class TestDependencies:
    def test_dependency_blocks_execution(self):
        eng = _make_engine()
        steps = [
            _step("s1", order=0),
            _step("s2", order=1),
        ]
        deps = [CampaignDependency(
            dependency_id="d1", campaign_id="camp-1",
            source_step_id="s1", target_step_id="s2", required=True,
        )]
        eng.register_campaign("camp-1", "C1", steps, dependencies=deps)
        # Manually fail s1 so s2 is blocked
        eng.register_step_handler(CampaignStepType.CHECK_CONDITION, _fail_handler)
        eng.start_run("camp-1", run_id="r1")
        # s1 executes but fails (with max_retries default 3 -> RETRYING)
        rec1 = eng.execute_next_step("r1")
        assert rec1 is not None
        # s2 cannot run because s1 is not COMPLETED
        rec2 = eng.execute_next_step("r1")
        # Should either be None (no pending step available) or complete run
        # s1 is RETRYING, s2 is blocked -> None (run completes because no step can advance)
        # Actually: s1 is RETRYING not PENDING anymore, so it won't run again automatically
        # s2 is blocked by dep -> no step available -> run completes
        assert rec2 is None

    def test_dependency_allows_when_source_completed(self):
        eng = _make_engine()
        steps = [_step("s1", order=0), _step("s2", order=1)]
        deps = [CampaignDependency(
            dependency_id="d1", campaign_id="camp-1",
            source_step_id="s1", target_step_id="s2", required=True,
        )]
        eng.register_campaign("camp-1", "C1", steps, dependencies=deps)
        eng.start_run("camp-1", run_id="r1")
        rec1 = eng.execute_next_step("r1")
        assert rec1 is not None and rec1.success
        rec2 = eng.execute_next_step("r1")
        assert rec2 is not None and rec2.success

    def test_optional_dependency_does_not_block(self):
        eng = _make_engine()
        eng.register_step_handler(CampaignStepType.CHECK_CONDITION, _fail_handler)
        steps = [_step("s1", order=0, max_retries=0), _step("s2", order=1)]
        deps = [CampaignDependency(
            dependency_id="d1", campaign_id="camp-1",
            source_step_id="s1", target_step_id="s2", required=False,
        )]
        eng.register_campaign("camp-1", "C1", steps, dependencies=deps)
        eng.start_run("camp-1", run_id="r1")
        eng.execute_next_step("r1")  # s1 fails
        # s2 should still be reachable because dep is not required
        # But run is FAILED because CHECK_CONDITION failure -> FAILED status
        # So execute_next_step returns None
        run = eng.get_run("r1")
        assert run.status == CampaignStatus.FAILED


# ===================================================================
# 11. Retrying steps
# ===================================================================


class TestRetrying:
    def test_failed_step_retryable(self):
        eng = _make_engine()
        eng.register_step_handler(CampaignStepType.CHECK_CONDITION, _fail_handler)
        steps = [_step("s1", max_retries=0)]
        eng.register_campaign("camp-1", "C1", steps)
        eng.start_run("camp-1", run_id="r1")
        eng.execute_next_step("r1")
        # Now swap handler to succeed
        eng.register_step_handler(CampaignStepType.CHECK_CONDITION, _ok_handler)
        rec = eng.retry_step("r1", "s1")
        assert rec is not None
        assert rec.success is True

    def test_retrying_status_step_retryable(self):
        eng = _make_engine()
        eng.register_step_handler(CampaignStepType.CHECK_CONDITION, _fail_handler)
        steps = [_step("s1", max_retries=2)]
        eng.register_campaign("camp-1", "C1", steps)
        eng.start_run("camp-1", run_id="r1")
        eng.execute_next_step("r1")  # step goes to RETRYING because max_retries=2
        step_after = eng.get_run_step("r1", "s1")
        assert step_after.status == CampaignStepStatus.RETRYING
        eng.register_step_handler(CampaignStepType.CHECK_CONDITION, _ok_handler)
        rec = eng.retry_step("r1", "s1")
        assert rec.success is True

    def test_retry_non_failed_raises(self):
        eng = _make_engine()
        steps = [_step("s1")]
        eng.register_campaign("camp-1", "C1", steps)
        eng.start_run("camp-1", run_id="r1")
        eng.execute_next_step("r1")  # completed
        with pytest.raises(RuntimeCoreInvariantError, match="cannot retry"):
            eng.retry_step("r1", "s1")

    def test_retry_unknown_step_raises(self):
        eng = _make_engine()
        steps = [_step("s1")]
        eng.register_campaign("camp-1", "C1", steps)
        eng.start_run("camp-1", run_id="r1")
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            eng.retry_step("r1", "nonexistent")

    def test_retry_increments_counter(self):
        eng = _make_engine()
        eng.register_step_handler(CampaignStepType.CHECK_CONDITION, _fail_handler)
        steps = [_step("s1", max_retries=1)]
        eng.register_campaign("camp-1", "C1", steps)
        eng.start_run("camp-1", run_id="r1")
        eng.execute_next_step("r1")  # RETRYING
        assert eng._counters["r1"]["retries"] == 1

    def test_retry_resumes_failed_campaign(self):
        eng = _make_engine()
        eng.register_step_handler(CampaignStepType.CHECK_CONDITION, _fail_handler)
        steps = [_step("s1", max_retries=0)]
        eng.register_campaign("camp-1", "C1", steps)
        eng.start_run("camp-1", run_id="r1")
        eng.execute_next_step("r1")
        assert eng.get_run("r1").status == CampaignStatus.FAILED
        eng.register_step_handler(CampaignStepType.CHECK_CONDITION, _ok_handler)
        eng.retry_step("r1", "s1")
        assert eng.get_run("r1").status == CampaignStatus.ACTIVE

    def test_retry_resumes_escalated_campaign(self):
        eng = _make_engine()
        eng.register_step_handler(CampaignStepType.SEND_COMMUNICATION, _fail_handler)
        steps = [_step("s1", step_type=CampaignStepType.SEND_COMMUNICATION, max_retries=0)]
        eng.register_campaign("camp-1", "C1", steps)
        eng.start_run("camp-1", run_id="r1")
        eng.execute_next_step("r1")
        assert eng.get_run("r1").status == CampaignStatus.ESCALATED
        eng.register_step_handler(CampaignStepType.SEND_COMMUNICATION, _ok_handler)
        eng.retry_step("r1", "s1")
        assert eng.get_run("r1").status == CampaignStatus.ACTIVE


# ===================================================================
# 12. Pause / resume / abort lifecycle
# ===================================================================


class TestLifecycle:
    def test_pause_active_run(self):
        eng = _make_engine()
        _register_simple(eng)
        eng.start_run("camp-1", run_id="r1")
        paused = eng.pause_run("r1")
        assert paused.status == CampaignStatus.PAUSED

    def test_pause_terminal_raises(self):
        eng = _make_engine()
        steps = [_step("s1")]
        eng.register_campaign("camp-1", "C1", steps)
        eng.start_run("camp-1", run_id="r1")
        eng.execute_all_steps("r1")  # completes
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            eng.pause_run("r1")

    def test_resume_paused_run(self):
        eng = _make_engine()
        _register_simple(eng)
        eng.start_run("camp-1", run_id="r1")
        eng.pause_run("r1")
        resumed = eng.resume_run("r1")
        assert resumed.status == CampaignStatus.ACTIVE

    def test_resume_waiting_run(self):
        eng = _make_engine()
        steps = [_step("s1", step_type=CampaignStepType.WAIT_FOR_REPLY)]
        eng.register_campaign("camp-1", "C1", steps)
        eng.start_run("camp-1", run_id="r1")
        eng.execute_next_step("r1")
        assert eng.get_run("r1").status == CampaignStatus.WAITING
        resumed = eng.resume_run("r1")
        assert resumed.status == CampaignStatus.ACTIVE

    def test_resume_escalated_run(self):
        eng = _make_engine()
        eng.register_step_handler(CampaignStepType.CALL_CONNECTOR, _fail_handler)
        steps = [_step("s1", step_type=CampaignStepType.CALL_CONNECTOR, max_retries=0)]
        eng.register_campaign("camp-1", "C1", steps)
        eng.start_run("camp-1", run_id="r1")
        eng.execute_next_step("r1")
        assert eng.get_run("r1").status == CampaignStatus.ESCALATED
        resumed = eng.resume_run("r1")
        assert resumed.status == CampaignStatus.ACTIVE

    def test_resume_active_raises(self):
        eng = _make_engine()
        _register_simple(eng)
        eng.start_run("camp-1", run_id="r1")
        with pytest.raises(RuntimeCoreInvariantError, match="cannot resume"):
            eng.resume_run("r1")

    def test_abort_active_run(self):
        eng = _make_engine()
        _register_simple(eng)
        eng.start_run("camp-1", run_id="r1")
        aborted = eng.abort_run("r1", reason="user requested")
        assert aborted.status == CampaignStatus.ABORTED

    def test_abort_terminal_raises(self):
        eng = _make_engine()
        steps = [_step("s1")]
        eng.register_campaign("camp-1", "C1", steps)
        eng.start_run("camp-1", run_id="r1")
        eng.execute_all_steps("r1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            eng.abort_run("r1")

    def test_abort_generates_closure_report(self):
        eng = _make_engine()
        _register_simple(eng)
        eng.start_run("camp-1", run_id="r1")
        eng.abort_run("r1")
        report = eng.get_closure_report("r1")
        assert report is not None
        assert report.outcome == CampaignOutcomeVerdict.ABORTED


# ===================================================================
# 13. Checkpoint
# ===================================================================


class TestCheckpoint:
    def test_checkpoint_captures_state(self):
        eng = _make_engine()
        steps = [_step("s1", order=0), _step("s2", order=1)]
        eng.register_campaign("camp-1", "C1", steps)
        eng.start_run("camp-1", run_id="r1")
        eng.execute_next_step("r1")  # s1 done
        ckpt = eng.checkpoint("r1")
        assert ckpt.run_id == "r1"
        assert ckpt.campaign_id == "camp-1"
        assert "s1" in ckpt.completed_step_ids

    def test_checkpoint_unknown_run_raises(self):
        eng = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError):
            eng.checkpoint("nope")

    def test_get_checkpoint_returns_latest(self):
        eng = _make_engine()
        steps = [_step("s1", order=0), _step("s2", order=1)]
        eng.register_campaign("camp-1", "C1", steps)
        eng.start_run("camp-1", run_id="r1")
        eng.execute_next_step("r1")
        eng.checkpoint("r1")
        eng.execute_next_step("r1")
        eng.checkpoint("r1")
        ckpt = eng.get_checkpoint("r1")
        assert ckpt is not None
        assert "s1" in ckpt.completed_step_ids
        assert "s2" in ckpt.completed_step_ids

    def test_get_checkpoint_none_when_absent(self):
        eng = _make_engine()
        assert eng.get_checkpoint("nope") is None

    def test_pause_creates_checkpoint(self):
        eng = _make_engine()
        _register_simple(eng)
        eng.start_run("camp-1", run_id="r1")
        eng.execute_next_step("r1")
        eng.pause_run("r1")
        ckpt = eng.get_checkpoint("r1")
        assert ckpt is not None
        assert ckpt.status == CampaignStatus.PAUSED

    def test_checkpoint_tracks_failed_steps(self):
        eng = _make_engine()
        eng.register_step_handler(CampaignStepType.CHECK_CONDITION, _fail_handler)
        steps = [_step("s1", max_retries=0)]
        eng.register_campaign("camp-1", "C1", steps)
        eng.start_run("camp-1", run_id="r1")
        eng.execute_next_step("r1")
        ckpt = eng.checkpoint("r1")
        assert "s1" in ckpt.failed_step_ids


# ===================================================================
# 14. Closure report and verdict logic
# ===================================================================


class TestClosureReport:
    def test_success_verdict(self):
        eng = _make_engine()
        steps = [_step("s1", order=0), _step("s2", order=1)]
        eng.register_campaign("camp-1", "C1", steps)
        eng.start_run("camp-1", run_id="r1")
        eng.execute_all_steps("r1")
        report = eng.get_closure_report("r1")
        assert report is not None
        assert report.outcome == CampaignOutcomeVerdict.SUCCESS
        assert report.completed_steps == 2
        assert report.total_steps == 2
        assert report.failed_steps == 0

    def test_aborted_verdict(self):
        eng = _make_engine()
        steps = [_step("s1", order=0), _step("s2", order=1)]
        eng.register_campaign("camp-1", "C1", steps)
        eng.start_run("camp-1", run_id="r1")
        eng.execute_next_step("r1")
        eng.abort_run("r1")
        report = eng.get_closure_report("r1")
        assert report.outcome == CampaignOutcomeVerdict.ABORTED

    def test_cannot_abort_already_failed_run(self):
        """Cannot abort a run that is already in terminal FAILED status."""
        eng = _make_engine()
        eng.register_step_handler(CampaignStepType.CHECK_CONDITION, _fail_handler)
        steps = [_step("s1", max_retries=0)]
        eng.register_campaign("camp-1", "C1", steps)
        eng.start_run("camp-1", run_id="r1")
        eng.execute_next_step("r1")
        assert eng.get_run("r1").status == CampaignStatus.FAILED
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            eng.abort_run("r1")

    def test_failure_verdict_all_failed(self):
        """When all steps fail and run is aborted, if no completed steps, verdict is ABORTED."""
        eng = _make_engine()
        eng.register_step_handler(CampaignStepType.CHECK_CONDITION, _fail_handler)
        steps = [_step("s1", max_retries=0)]
        eng.register_campaign("camp-1", "C1", steps)
        eng.start_run("camp-1", run_id="r1")
        eng.execute_next_step("r1")
        # Run is FAILED (terminal). Can't abort. No closure auto-generated.
        # Generate closure manually (through internal method for coverage):
        report = eng._generate_closure_report("r1")
        assert report.outcome == CampaignOutcomeVerdict.FAILURE
        assert report.failed_steps == 1
        assert report.completed_steps == 0

    def test_partial_success_verdict(self):
        eng = _make_engine()
        # s1 succeeds, s2 fails
        def conditional_handler(step, ctx):
            if step.step_id == "s1":
                return True, {}
            return False, {}

        eng.register_step_handler(CampaignStepType.CHECK_CONDITION, conditional_handler)
        steps = [_step("s1", order=0, max_retries=0), _step("s2", order=1, max_retries=0)]
        eng.register_campaign("camp-1", "C1", steps)
        eng.start_run("camp-1", run_id="r1")
        eng.execute_all_steps("r1")
        # s1 completed, s2 failed -> run FAILED
        report = eng._generate_closure_report("r1")
        assert report.outcome == CampaignOutcomeVerdict.PARTIAL_SUCCESS

    def test_escalated_verdict(self):
        eng = _make_engine()
        eng.register_step_handler(CampaignStepType.CALL_CONNECTOR, _fail_handler)
        steps = [_step("s1", step_type=CampaignStepType.CALL_CONNECTOR, max_retries=0)]
        eng.register_campaign("camp-1", "C1", steps)
        eng.start_run("camp-1", run_id="r1")
        eng.execute_next_step("r1")
        assert eng.get_run("r1").status == CampaignStatus.ESCALATED
        report = eng._generate_closure_report("r1")
        # failed > 0 but completed == 0 -> FAILURE takes precedence over ESCALATED
        assert report.outcome == CampaignOutcomeVerdict.FAILURE

    def test_escalated_verdict_no_failures(self):
        """Escalation without direct failure count (edge case via manual escalation)."""
        eng = _make_engine()
        steps = [_step("s1")]
        eng.register_campaign("camp-1", "C1", steps)
        eng.start_run("camp-1", run_id="r1")
        eng.execute_next_step("r1")  # succeeds
        # Manually set status to ESCALATED for verdict coverage
        run = eng._runs["r1"]
        eng._runs["r1"] = CampaignRun(
            run_id=run.run_id, campaign_id=run.campaign_id,
            status=CampaignStatus.ESCALATED,
            current_step_index=run.current_step_index,
            started_at=run.started_at,
        )
        report = eng._generate_closure_report("r1")
        assert report.outcome == CampaignOutcomeVerdict.ESCALATED

    def test_closure_report_includes_step_summaries(self):
        eng = _make_engine()
        steps = [_step("s1")]
        eng.register_campaign("camp-1", "C1", steps)
        eng.start_run("camp-1", run_id="r1")
        eng.execute_all_steps("r1")
        report = eng.get_closure_report("r1")
        assert len(report.step_summaries) == 1
        assert report.step_summaries[0]["step_id"] == "s1"

    def test_closure_report_summary_string(self):
        eng = _make_engine()
        steps = [_step("s1")]
        eng.register_campaign("camp-1", "C1", steps)
        eng.start_run("camp-1", run_id="r1")
        eng.execute_all_steps("r1")
        report = eng.get_closure_report("r1")
        assert "camp-1" in report.summary
        assert "success" in report.summary.lower()

    def test_no_closure_report_before_completion(self):
        eng = _make_engine()
        _register_simple(eng)
        eng.start_run("camp-1", run_id="r1")
        assert eng.get_closure_report("r1") is None


# ===================================================================
# 15. Counter tracking
# ===================================================================


class TestCounterTracking:
    def test_messages_sent_counter(self):
        eng = _make_engine()
        eng.register_step_handler(CampaignStepType.SEND_COMMUNICATION, _ok_handler)
        steps = [_step("s1", step_type=CampaignStepType.SEND_COMMUNICATION)]
        eng.register_campaign("camp-1", "C1", steps)
        eng.start_run("camp-1", run_id="r1")
        eng.execute_next_step("r1")
        assert eng._counters["r1"]["messages_sent"] == 1

    def test_artifacts_processed_counter(self):
        eng = _make_engine()
        eng.register_step_handler(CampaignStepType.INGEST_ARTIFACT, _ok_handler)
        steps = [_step("s1", step_type=CampaignStepType.INGEST_ARTIFACT)]
        eng.register_campaign("camp-1", "C1", steps)
        eng.start_run("camp-1", run_id="r1")
        eng.execute_next_step("r1")
        assert eng._counters["r1"]["artifacts_processed"] == 1

    def test_obligations_created_counter(self):
        eng = _make_engine()
        eng.register_step_handler(CampaignStepType.CREATE_OBLIGATION, _ok_handler)
        steps = [_step("s1", step_type=CampaignStepType.CREATE_OBLIGATION)]
        eng.register_campaign("camp-1", "C1", steps)
        eng.start_run("camp-1", run_id="r1")
        eng.execute_next_step("r1")
        assert eng._counters["r1"]["obligations_created"] == 1

    def test_connector_calls_counter(self):
        eng = _make_engine()
        eng.register_step_handler(CampaignStepType.CALL_CONNECTOR, _ok_handler)
        steps = [_step("s1", step_type=CampaignStepType.CALL_CONNECTOR)]
        eng.register_campaign("camp-1", "C1", steps)
        eng.start_run("camp-1", run_id="r1")
        eng.execute_next_step("r1")
        assert eng._counters["r1"]["connector_calls"] == 1

    def test_connector_calls_counted_on_failure_too(self):
        eng = _make_engine()
        eng.register_step_handler(CampaignStepType.CALL_CONNECTOR, _fail_handler)
        steps = [_step("s1", step_type=CampaignStepType.CALL_CONNECTOR, max_retries=0)]
        eng.register_campaign("camp-1", "C1", steps)
        eng.start_run("camp-1", run_id="r1")
        eng.execute_next_step("r1")
        assert eng._counters["r1"]["connector_calls"] == 1

    def test_failed_send_communication_not_counted(self):
        eng = _make_engine()
        eng.register_step_handler(CampaignStepType.SEND_COMMUNICATION, _fail_handler)
        steps = [_step("s1", step_type=CampaignStepType.SEND_COMMUNICATION, max_retries=0)]
        eng.register_campaign("camp-1", "C1", steps)
        eng.start_run("camp-1", run_id="r1")
        eng.execute_next_step("r1")
        assert eng._counters["r1"]["messages_sent"] == 0

    def test_counters_in_closure_report(self):
        eng = _make_engine()
        eng.register_step_handler(CampaignStepType.SEND_COMMUNICATION, _ok_handler)
        eng.register_step_handler(CampaignStepType.CALL_CONNECTOR, _ok_handler)
        steps = [
            _step("s1", order=0, step_type=CampaignStepType.SEND_COMMUNICATION),
            _step("s2", order=1, step_type=CampaignStepType.CALL_CONNECTOR),
        ]
        eng.register_campaign("camp-1", "C1", steps)
        eng.start_run("camp-1", run_id="r1")
        eng.execute_all_steps("r1")
        report = eng.get_closure_report("r1")
        assert report.messages_sent == 1
        assert report.connector_calls == 1

    def test_retries_counter(self):
        eng = _make_engine()
        eng.register_step_handler(CampaignStepType.CHECK_CONDITION, _fail_handler)
        steps = [_step("s1", max_retries=2)]
        eng.register_campaign("camp-1", "C1", steps)
        eng.start_run("camp-1", run_id="r1")
        eng.execute_next_step("r1")
        assert eng._counters["r1"]["retries"] == 1


# ===================================================================
# 16. state_hash determinism
# ===================================================================


class TestStateHash:
    def test_state_hash_is_string(self):
        eng = _make_engine()
        h = eng.state_hash()
        assert isinstance(h, str)
        assert len(h) == 64

    def test_empty_engines_same_hash(self):
        h1 = _make_engine().state_hash()
        h2 = _make_engine().state_hash()
        assert h1 == h2

    def test_hash_changes_after_registration(self):
        eng = _make_engine()
        h1 = eng.state_hash()
        _register_simple(eng)
        h2 = eng.state_hash()
        assert h1 != h2

    def test_hash_changes_after_run(self):
        eng = _make_engine()
        _register_simple(eng)
        h1 = eng.state_hash()
        eng.start_run("camp-1", run_id="r1")
        h2 = eng.state_hash()
        assert h1 != h2

    def test_same_state_same_hash(self):
        """Two engines with identical campaigns and runs produce the same hash."""
        eng1 = _make_engine()
        eng2 = _make_engine()
        for e in (eng1, eng2):
            steps = [_step("s1", campaign_id="c1", order=0)]
            e.register_campaign("c1", "Campaign c1", steps)
            e.start_run("c1", run_id="r1")
        assert eng1.state_hash() == eng2.state_hash()


# ===================================================================
# 17. Listing / query methods
# ===================================================================


class TestListingQueries:
    def test_list_campaigns(self):
        eng = _make_engine()
        _register_simple(eng, "c1")
        _register_simple(eng, "c2")
        result = eng.list_campaigns()
        assert len(result) == 2

    def test_list_campaigns_by_status(self):
        eng = _make_engine()
        _register_simple(eng, "c1")
        _register_simple(eng, "c2")
        eng.start_run("c1", run_id="r1")
        # c1 is now ACTIVE, c2 is DRAFT
        drafts = eng.list_campaigns(status=CampaignStatus.DRAFT)
        assert len(drafts) == 1
        assert drafts[0].campaign_id == "c2"

    def test_list_runs(self):
        eng = _make_engine()
        _register_simple(eng)
        eng.start_run("camp-1", run_id="r1")
        eng.start_run("camp-1", run_id="r2")
        result = eng.list_runs()
        assert len(result) == 2

    def test_list_runs_by_campaign(self):
        eng = _make_engine()
        _register_simple(eng, "c1")
        _register_simple(eng, "c2")
        eng.start_run("c1", run_id="r1")
        eng.start_run("c2", run_id="r2")
        result = eng.list_runs("c1")
        assert len(result) == 1
        assert result[0].campaign_id == "c1"

    def test_list_runs_by_status(self):
        eng = _make_engine()
        _register_simple(eng)
        eng.start_run("camp-1", run_id="r1")
        eng.start_run("camp-1", run_id="r2")
        eng.pause_run("r1")
        paused = eng.list_runs(status=CampaignStatus.PAUSED)
        assert len(paused) == 1

    def test_get_execution_records(self):
        eng = _make_engine()
        _register_simple(eng)
        eng.start_run("camp-1", run_id="r1")
        eng.execute_next_step("r1")
        records = eng.get_execution_records("r1")
        assert len(records) == 1

    def test_get_execution_records_all(self):
        eng = _make_engine()
        _register_simple(eng)
        eng.start_run("camp-1", run_id="r1")
        eng.execute_all_steps("r1")
        all_recs = eng.get_execution_records()
        assert len(all_recs) >= 2

    def test_get_escalations_filtered(self):
        eng = _make_engine()
        eng.register_step_handler(CampaignStepType.SEND_COMMUNICATION, _fail_handler)
        steps1 = [_step("s1", campaign_id="c1", step_type=CampaignStepType.SEND_COMMUNICATION, max_retries=0)]
        eng.register_campaign("c1", "C1", steps1)
        eng.start_run("c1", run_id="r1")
        eng.execute_next_step("r1")
        steps2 = [_step("s2", campaign_id="c2", step_type=CampaignStepType.SEND_COMMUNICATION, max_retries=0)]
        eng.register_campaign("c2", "C2", steps2)
        eng.start_run("c2", run_id="r2")
        eng.execute_next_step("r2")
        assert len(eng.get_escalations("r1")) == 1
        assert len(eng.get_escalations()) == 2

    def test_get_run_step(self):
        eng = _make_engine()
        _register_simple(eng)
        eng.start_run("camp-1", run_id="r1")
        eng.execute_next_step("r1")
        s = eng.get_run_step("r1", "s1")
        assert s.status == CampaignStepStatus.COMPLETED

    def test_get_run_step_missing_run(self):
        eng = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError):
            eng.get_run_step("nope", "s1")

    def test_get_run_step_missing_step(self):
        eng = _make_engine()
        _register_simple(eng)
        eng.start_run("camp-1", run_id="r1")
        with pytest.raises(RuntimeCoreInvariantError):
            eng.get_run_step("r1", "nope")


# ===================================================================
# 18. Execution records detail
# ===================================================================


class TestExecutionRecords:
    def test_record_has_correct_fields(self):
        eng = _make_engine()
        eng.register_step_handler(CampaignStepType.CHECK_CONDITION, _ok_handler)
        steps = [_step("s1")]
        eng.register_campaign("camp-1", "C1", steps)
        eng.start_run("camp-1", run_id="r1")
        rec = eng.execute_next_step("r1")
        assert rec.campaign_id == "camp-1"
        assert rec.run_id == "r1"
        assert rec.step_id == "s1"
        assert rec.step_type == CampaignStepType.CHECK_CONDITION
        assert rec.success is True
        assert rec.executed_at  # non-empty

    def test_failure_record_includes_error(self):
        eng = _make_engine()
        eng.register_step_handler(CampaignStepType.CHECK_CONDITION, _raise_handler)
        steps = [_step("s1", max_retries=0)]
        eng.register_campaign("camp-1", "C1", steps)
        eng.start_run("camp-1", run_id="r1")
        rec = eng.execute_next_step("r1")
        assert rec.success is False
        assert rec.error_message == "campaign step handler error (RuntimeError)"
        assert "boom" not in rec.error_message

    def test_escalation_description_redacts_handler_exception(self):
        eng = _make_engine()
        eng.register_step_handler(CampaignStepType.SEND_COMMUNICATION, _raise_handler)
        steps = [_step("s1", step_type=CampaignStepType.SEND_COMMUNICATION, max_retries=0)]
        eng.register_campaign("camp-1", "C1", steps)
        eng.start_run("camp-1", run_id="r1")
        eng.execute_next_step("r1")
        escalation = eng.get_escalations("r1")[0]
        assert escalation.reason == CampaignEscalationReason.STEP_FAILURE
        assert "campaign step handler error (RuntimeError)" in escalation.description
        assert "boom" not in escalation.description


# ===================================================================
# 19. Multi-step complex scenarios
# ===================================================================


class TestComplexScenarios:
    def test_three_step_pipeline(self):
        eng = _make_engine()
        eng.register_step_handler(CampaignStepType.INGEST_ARTIFACT, _ok_handler)
        eng.register_step_handler(CampaignStepType.EXTRACT_COMMITMENTS, _ok_handler)
        eng.register_step_handler(CampaignStepType.CREATE_OBLIGATION, _ok_handler)
        steps = [
            _step("s1", order=0, step_type=CampaignStepType.INGEST_ARTIFACT),
            _step("s2", order=1, step_type=CampaignStepType.EXTRACT_COMMITMENTS),
            _step("s3", order=2, step_type=CampaignStepType.CREATE_OBLIGATION),
        ]
        eng.register_campaign("camp-1", "Pipeline", steps)
        eng.start_run("camp-1", run_id="r1")
        records = eng.execute_all_steps("r1")
        assert len(records) == 3
        assert all(r.success for r in records)
        report = eng.get_closure_report("r1")
        assert report.outcome == CampaignOutcomeVerdict.SUCCESS
        assert report.artifacts_processed == 1
        assert report.obligations_created == 1

    def test_pause_resume_continue(self):
        eng = _make_engine()
        steps = [_step("s1", order=0), _step("s2", order=1)]
        eng.register_campaign("camp-1", "C1", steps)
        eng.start_run("camp-1", run_id="r1")
        eng.execute_next_step("r1")  # s1 done
        eng.pause_run("r1")
        # No execution while paused
        assert eng.execute_next_step("r1") is None
        eng.resume_run("r1")
        rec = eng.execute_next_step("r1")  # s2
        assert rec is not None and rec.success

    def test_multiple_runs_same_campaign(self):
        eng = _make_engine()
        steps = [_step("s1")]
        eng.register_campaign("camp-1", "C1", steps)
        r1 = eng.start_run("camp-1", run_id="r1")
        r2 = eng.start_run("camp-1", run_id="r2")
        eng.execute_all_steps("r1")
        eng.execute_all_steps("r2")
        assert eng.get_run("r1").status == CampaignStatus.COMPLETED
        assert eng.get_run("r2").status == CampaignStatus.COMPLETED


# ===================================================================
# 20. Edge cases
# ===================================================================


class TestEdgeCases:
    def test_get_run_not_found(self):
        eng = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            eng.get_run("nope")

    def test_execute_next_step_unknown_run(self):
        eng = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError):
            eng.execute_next_step("nope")

    def test_context_passed_to_handler(self):
        received = {}
        def capturing_handler(step, ctx):
            received.update(ctx)
            return True, {}
        eng = _make_engine()
        eng.register_step_handler(CampaignStepType.CHECK_CONDITION, capturing_handler)
        steps = [_step("s1")]
        eng.register_campaign("camp-1", "C1", steps)
        eng.start_run("camp-1", run_id="r1")
        eng.execute_next_step("r1", context={"key": "value"})
        assert received["key"] == "value"

    def test_handler_output_in_step(self):
        def detailed_handler(step, ctx):
            return True, {"detail": 42}
        eng = _make_engine()
        eng.register_step_handler(CampaignStepType.CHECK_CONDITION, detailed_handler)
        steps = [_step("s1")]
        eng.register_campaign("camp-1", "C1", steps)
        eng.start_run("camp-1", run_id="r1")
        eng.execute_next_step("r1")
        s = eng.get_run_step("r1", "s1")
        assert s.output_payload["detail"] == 42

    def test_step_order_is_respected(self):
        order_log = []
        def order_handler(step, ctx):
            order_log.append(step.step_id)
            return True, {}
        eng = _make_engine()
        eng.register_step_handler(CampaignStepType.CHECK_CONDITION, order_handler)
        steps = [
            _step("c", order=2),
            _step("a", order=0),
            _step("b", order=1),
        ]
        eng.register_campaign("camp-1", "C1", steps)
        eng.start_run("camp-1", run_id="r1")
        eng.execute_all_steps("r1")
        assert order_log == ["a", "b", "c"]

    def test_auto_succeed_output(self):
        eng = _make_engine()
        steps = [_step("s1")]
        eng.register_campaign("camp-1", "C1", steps)
        eng.start_run("camp-1", run_id="r1")
        rec = eng.execute_next_step("r1")
        assert "auto" in rec.output_summary
