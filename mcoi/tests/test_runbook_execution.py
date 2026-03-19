"""Tests for runbook execution, drift detection, and policy context binding."""

from __future__ import annotations

from typing import Any, Mapping
from unittest.mock import MagicMock

import pytest

from mcoi_runtime.contracts.runbook_execution import (
    DriftRecord,
    DriftType,
    RunbookExecutionContext,
    RunbookExecutionRecord,
    RunbookExecutionRequest,
    RunbookExecutionStatus,
    RunbookStepResult,
)
from mcoi_runtime.core.runbook import RunbookEntry, RunbookLibrary, RunbookProvenance
from mcoi_runtime.core.runbook_executor import RunbookExecutor
from mcoi_runtime.core.persisted_replay import PersistedReplayValidator
from mcoi_runtime.core.replay_engine import ReplayVerdict


FIXED_CLOCK = "2025-01-15T10:00:00+00:00"


def _context(operator_id="op-1", autonomy_mode="bounded_autonomous", **kw):
    return RunbookExecutionContext(
        operator_id=operator_id,
        autonomy_mode=autonomy_mode,
        **kw,
    )


def _request(runbook_id="rb-1", request_id="req-1", **kw):
    return RunbookExecutionRequest(
        request_id=request_id,
        runbook_id=runbook_id,
        context=kw.pop("context", _context()),
        **kw,
    )


def _make_entry(runbook_id="rb-1", template=None):
    return RunbookEntry(
        runbook_id=runbook_id,
        name="test-runbook",
        description="test procedure",
        template=template or {"step_check": "check disk", "step_clean": "clean temp"},
        bindings_schema={"target": "string"},
        provenance=RunbookProvenance(
            execution_id="exec-1",
            verification_id="verif-1",
            replay_id="replay-1",
            trace_id="trace-1",
        ),
    )


def _mock_library(entries: dict[str, RunbookEntry] | None = None) -> RunbookLibrary:
    """Create a mock library with pre-populated entries."""
    mock_validator = MagicMock(spec=PersistedReplayValidator)
    lib = RunbookLibrary(replay_validator=mock_validator)
    # Directly populate entries
    if entries:
        lib._entries = dict(entries)
    return lib


def _success_step(step_name: str, params: Mapping[str, Any]) -> RunbookStepResult:
    return RunbookStepResult(step_index=0, step_name=step_name, succeeded=True)


def _fail_step(step_name: str, params: Mapping[str, Any]) -> RunbookStepResult:
    return RunbookStepResult(step_index=0, step_name=step_name, succeeded=False, error_message="step failed")


# --- Contracts ---


class TestRunbookExecutionContracts:
    def test_context_valid(self):
        ctx = _context()
        assert ctx.operator_id == "op-1"
        assert ctx.autonomy_mode == "bounded_autonomous"

    def test_context_empty_operator_rejected(self):
        with pytest.raises(ValueError):
            RunbookExecutionContext(operator_id="", autonomy_mode="x")

    def test_request_valid(self):
        req = _request()
        assert req.runbook_id == "rb-1"

    def test_step_result_valid(self):
        r = RunbookStepResult(step_index=0, step_name="check", succeeded=True)
        assert r.succeeded

    def test_step_result_negative_index_rejected(self):
        with pytest.raises(ValueError):
            RunbookStepResult(step_index=-1, step_name="x", succeeded=True)

    def test_drift_record_valid(self):
        d = DriftRecord(
            drift_type=DriftType.AUTONOMY_MISMATCH,
            field_name="autonomy_mode",
            baseline_value="observe_only",
            current_value="bounded_autonomous",
        )
        assert d.drift_type is DriftType.AUTONOMY_MISMATCH

    def test_execution_record_properties(self):
        r = RunbookExecutionRecord(
            record_id="r-1", runbook_id="rb-1", request_id="req-1",
            status=RunbookExecutionStatus.SUCCEEDED, context=_context(),
        )
        assert r.succeeded is True
        assert r.has_drift is False

    def test_execution_record_with_drift(self):
        drift = DriftRecord(
            drift_type=DriftType.AUTONOMY_MISMATCH,
            field_name="mode", baseline_value="a", current_value="b",
        )
        r = RunbookExecutionRecord(
            record_id="r-1", runbook_id="rb-1", request_id="req-1",
            status=RunbookExecutionStatus.DRIFT_DETECTED, context=_context(),
            drift_records=(drift,),
        )
        assert r.has_drift is True
        assert r.succeeded is False


# --- Executor ---


class TestRunbookExecutor:
    def test_execute_success(self):
        lib = _mock_library({"rb-1": _make_entry()})
        executor = RunbookExecutor(library=lib, clock=lambda: FIXED_CLOCK)
        result = executor.execute(_request())
        assert result.status is RunbookExecutionStatus.SUCCEEDED
        assert len(result.step_results) == 2
        assert all(s.succeeded for s in result.step_results)

    def test_runbook_not_found(self):
        lib = _mock_library()
        executor = RunbookExecutor(library=lib, clock=lambda: FIXED_CLOCK)
        result = executor.execute(_request(runbook_id="missing"))
        assert result.status is RunbookExecutionStatus.BLOCKED_LIFECYCLE
        assert "not found" in result.error_message

    def test_step_failure_stops_execution(self):
        lib = _mock_library({"rb-1": _make_entry()})
        call_count = 0

        def fail_second(name, params):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                return RunbookStepResult(step_index=1, step_name=name, succeeded=False, error_message="fail")
            return RunbookStepResult(step_index=call_count - 1, step_name=name, succeeded=True)

        executor = RunbookExecutor(library=lib, clock=lambda: FIXED_CLOCK, step_executor=fail_second)
        result = executor.execute(_request())
        assert result.status is RunbookExecutionStatus.STEP_FAILED
        assert len(result.step_results) == 2

    def test_all_steps_fail_first(self):
        lib = _mock_library({"rb-1": _make_entry()})
        executor = RunbookExecutor(library=lib, clock=lambda: FIXED_CLOCK, step_executor=_fail_step)
        result = executor.execute(_request())
        assert result.status is RunbookExecutionStatus.STEP_FAILED
        assert len(result.step_results) == 1  # Stops after first failure

    def test_bindings_substituted(self):
        lib = _mock_library({"rb-1": _make_entry(template={"step_run": "clean {target}"})})
        captured = {}

        def capture(name, params):
            captured.update(params)
            return RunbookStepResult(step_index=0, step_name=name, succeeded=True)

        executor = RunbookExecutor(library=lib, clock=lambda: FIXED_CLOCK, step_executor=capture)
        executor.execute(_request(bindings={"target": "/tmp/data"}))
        assert captured["value"] == "clean /tmp/data"

    def test_record_has_timestamps(self):
        lib = _mock_library({"rb-1": _make_entry()})
        executor = RunbookExecutor(library=lib, clock=lambda: FIXED_CLOCK)
        result = executor.execute(_request())
        assert result.started_at == FIXED_CLOCK
        assert result.finished_at == FIXED_CLOCK

    def test_record_has_context(self):
        ctx = _context(operator_id="admin-1", autonomy_mode="approval_required", policy_pack_id="pack-v2")
        lib = _mock_library({"rb-1": _make_entry()})
        executor = RunbookExecutor(library=lib, clock=lambda: FIXED_CLOCK)
        result = executor.execute(_request(context=ctx))
        assert result.context.operator_id == "admin-1"
        assert result.context.autonomy_mode == "approval_required"
        assert result.context.policy_pack_id == "pack-v2"


# --- Drift detection ---


class TestDriftDetection:
    def test_no_drift_without_baseline(self):
        lib = _mock_library({"rb-1": _make_entry()})
        executor = RunbookExecutor(library=lib, clock=lambda: FIXED_CLOCK)
        result = executor.execute(_request())
        assert not result.has_drift

    def test_autonomy_drift_detected(self):
        lib = _mock_library({"rb-1": _make_entry()})
        executor = RunbookExecutor(library=lib, clock=lambda: FIXED_CLOCK)
        baseline = _context(autonomy_mode="observe_only")
        result = executor.execute(
            _request(context=_context(autonomy_mode="bounded_autonomous")),
            baseline_context=baseline,
        )
        assert result.has_drift
        assert result.status is RunbookExecutionStatus.DRIFT_DETECTED
        drifts = [d for d in result.drift_records if d.drift_type is DriftType.AUTONOMY_MISMATCH]
        assert len(drifts) == 1
        assert drifts[0].baseline_value == "observe_only"
        assert drifts[0].current_value == "bounded_autonomous"

    def test_policy_pack_drift_detected(self):
        lib = _mock_library({"rb-1": _make_entry()})
        executor = RunbookExecutor(library=lib, clock=lambda: FIXED_CLOCK)
        baseline = _context(policy_pack_id="pack-v1")
        current = _context(policy_pack_id="pack-v2")
        result = executor.execute(_request(context=current), baseline_context=baseline)
        drifts = [d for d in result.drift_records if d.drift_type is DriftType.POLICY_PACK_MISMATCH]
        assert len(drifts) == 1

    def test_step_count_drift_detected(self):
        lib = _mock_library({"rb-1": _make_entry()})
        executor = RunbookExecutor(library=lib, clock=lambda: FIXED_CLOCK)
        result = executor.execute(
            _request(),
            baseline_context=_context(),
            baseline_step_count=5,  # Template has 2 steps
        )
        drifts = [d for d in result.drift_records if d.drift_type is DriftType.STEP_COUNT_MISMATCH]
        assert len(drifts) == 1

    def test_no_drift_when_contexts_match(self):
        lib = _mock_library({"rb-1": _make_entry()})
        executor = RunbookExecutor(library=lib, clock=lambda: FIXED_CLOCK)
        ctx = _context()
        result = executor.execute(
            _request(context=ctx),
            baseline_context=ctx,
            baseline_step_count=2,
        )
        assert not result.has_drift
        assert result.status is RunbookExecutionStatus.SUCCEEDED

    def test_multiple_drifts_detected(self):
        lib = _mock_library({"rb-1": _make_entry()})
        executor = RunbookExecutor(library=lib, clock=lambda: FIXED_CLOCK)
        baseline = _context(autonomy_mode="observe_only", policy_pack_id="pack-v1")
        current = _context(autonomy_mode="bounded_autonomous", policy_pack_id="pack-v2")
        result = executor.execute(
            _request(context=current),
            baseline_context=baseline,
            baseline_step_count=10,
        )
        assert len(result.drift_records) == 3  # autonomy + policy + step count
