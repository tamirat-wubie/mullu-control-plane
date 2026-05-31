"""Tests for the bounded cognitive loop.

Covers happy path (verified terminal + learning admitted), boundary
(max_steps/budget + determinism), constraint violation (degraded/low-confidence
=> replan/SafeHalt and unknown-hard-constraint => no dispatch), rollback
(DEFER/REJECT leave episodic memory clean), and determinism (identical inputs =>
identical report). Engines are real where cheap; the governed dispatch is a
deterministic stub so the loop's own logic is exercised without re-running the
whole governed spine.
"""
from __future__ import annotations

from dataclasses import dataclass

from mcoi_runtime.contracts.execution import EffectRecord, ExecutionOutcome, ExecutionResult
from mcoi_runtime.contracts.meta_reasoning import CapabilityConfidence
from mcoi_runtime.contracts.policy import DecisionReason, PolicyDecision, PolicyDecisionStatus
from mcoi_runtime.contracts.solver_outcome import SolverOutcome
from mcoi_runtime.core.cognitive_loop import (
    CognitiveLoop,
    CognitiveLoopReport,
    CognitiveStepRequest,
    DecisionVerdict,
    HardConstraint,
    ProofState,
)
from mcoi_runtime.core.decision_learning import DecisionLearningEngine
from mcoi_runtime.core.memory import EpisodicMemory
from mcoi_runtime.core.meta_reasoning import MetaReasoningEngine
from mcoi_runtime.core.world_state import WorldStateEngine


def _clock() -> str:
    return "2026-01-01T00:00:00Z"


@dataclass(frozen=True)
class _StubVerification:
    passed: bool


@dataclass(frozen=True)
class _StubDispatchResult:
    execution_result: ExecutionResult
    verification: _StubVerification


def _execution_result(
    status: ExecutionOutcome,
    execution_id: str = "exec-1",
    *,
    governance_blocked: bool = False,
) -> ExecutionResult:
    effects = (
        (EffectRecord(name="governance_blocked", details={"gate": "policy"}),)
        if governance_blocked
        else ()
    )
    metadata = {"gates_failed": ["policy"]} if governance_blocked else {}
    return ExecutionResult(
        execution_id=execution_id,
        goal_id="goal-1",
        status=status,
        actual_effects=effects,
        assumed_effects=(),
        started_at="2026-01-01T00:00:00Z",
        finished_at="2026-01-01T00:00:01Z",
        metadata=metadata,
    )


def _make_dispatch_fn(
    status: ExecutionOutcome,
    verification_passed: bool,
    *,
    governance_blocked: bool = False,
):
    """Deterministic stub for governed_operator_mil_dispatch_with_trace."""
    calls: list[int] = []

    def _dispatch(governed, request, *, policy_decision, issued_at, actor_id):
        calls.append(1)
        return _StubDispatchResult(
            execution_result=_execution_result(
                status,
                execution_id=f"exec-{len(calls)}",
                governance_blocked=governance_blocked,
            ),
            verification=_StubVerification(passed=verification_passed),
        )

    _dispatch.calls = calls  # type: ignore[attr-defined]
    return _dispatch


def _policy_decision() -> PolicyDecision:
    return PolicyDecision(
        decision_id="dec-1",
        subject_id="subject-1",
        goal_id="goal-1",
        status=PolicyDecisionStatus.ALLOW,
        reasons=(DecisionReason(message="allowed", code="ok"),),
        issued_at="2026-01-01T00:00:00Z",
    )


def _request(**overrides) -> CognitiveStepRequest:
    base = dict(
        goal_id="goal-1",
        capability_id="noop",
        template={"action_type": "noop"},
        policy_decision=_policy_decision(),
        bindings={},
        hard_constraints=(),
    )
    base.update(overrides)
    return CognitiveStepRequest(**base)


def _make_loop(dispatch_fn, *, episodic=None, meta=None, learning=None, **kwargs) -> CognitiveLoop:
    return CognitiveLoop(
        governed_dispatcher=object(),
        world_state=WorldStateEngine(),
        episodic_memory=episodic or EpisodicMemory(),
        meta_reasoning=meta or MetaReasoningEngine(clock=_clock),
        decision_learning=learning or DecisionLearningEngine(clock=_clock),
        clock=_clock,
        dispatch_fn=dispatch_fn,
        **kwargs,
    )


# --------------------------------------------------------------------------
# Happy path
# --------------------------------------------------------------------------


def test_happy_path_solved_verified_and_learns():
    dispatch_fn = _make_dispatch_fn(ExecutionOutcome.SUCCEEDED, verification_passed=True)
    episodic = EpisodicMemory()
    meta = MetaReasoningEngine(clock=_clock)
    loop = _make_loop(dispatch_fn, episodic=episodic, meta=meta)

    report = loop.run(_request())

    assert report.terminal_outcome is SolverOutcome.SOLVED_VERIFIED
    assert len(report.steps) == 1
    assert report.steps[0].dispatched is True
    assert report.steps[0].verification_passed is True
    # LEARN closed the loop: episodic anchor admitted + confidence recorded.
    assert report.learning_admission_count == 1
    assert episodic.size == 1
    assert meta.get_confidence("noop") is not None


def test_happy_path_solved_unverified_when_verification_fails():
    dispatch_fn = _make_dispatch_fn(ExecutionOutcome.SUCCEEDED, verification_passed=False)
    episodic = EpisodicMemory()
    loop = _make_loop(dispatch_fn, episodic=episodic)

    report = loop.run(_request())

    assert report.terminal_outcome is SolverOutcome.SOLVED_UNVERIFIED
    assert report.learning_admission_count == 0  # not verified => not admitted
    assert episodic.size == 0  # rollback-safe: DEFER leaves memory clean


# --------------------------------------------------------------------------
# Boundary: max_steps / budget / determinism
# --------------------------------------------------------------------------


def test_budget_bounds_failed_dispatch_attempts():
    # Failing dispatch never reaches a success terminal and is bounded by
    # max_steps. The first failure feeds back into confidence, so a second
    # iteration may SafeHalt on the now-degraded capability instead of
    # re-dispatching - either terminal is a safe, bounded closure.
    dispatch_fn = _make_dispatch_fn(ExecutionOutcome.FAILED, verification_passed=False)
    loop = _make_loop(dispatch_fn, max_steps=2, step_budget=2)

    report = loop.run(_request())

    assert report.terminal_outcome in (
        SolverOutcome.AWAITING_EVIDENCE,
        SolverOutcome.SAFE_HALT,
    )
    assert len(report.steps) <= 2  # bounded by max_steps
    assert dispatch_fn.calls  # at least one dispatch occurred
    assert len(dispatch_fn.calls) <= 2  # never exceeds the step bound


def test_budget_exhausted_when_budget_below_steps():
    dispatch_fn = _make_dispatch_fn(ExecutionOutcome.FAILED, verification_passed=False)
    # step_budget smaller than what a single attempt needs is rejected; instead
    # exercise the budget cap by allowing one unit only.
    loop = _make_loop(dispatch_fn, max_steps=3, step_budget=1)

    report = loop.run(_request())

    # One budget unit => exactly one attempt; failed => awaiting evidence.
    assert report.terminal_outcome is SolverOutcome.AWAITING_EVIDENCE
    assert len(dispatch_fn.calls) == 1


def test_determinism_identical_inputs_identical_report():
    report_a = _make_loop(
        _make_dispatch_fn(ExecutionOutcome.SUCCEEDED, verification_passed=True)
    ).run(_request())
    report_b = _make_loop(
        _make_dispatch_fn(ExecutionOutcome.SUCCEEDED, verification_passed=True)
    ).run(_request())

    assert report_a.report_hash == report_b.report_hash
    assert report_a.terminal_outcome == report_b.terminal_outcome
    assert len(report_a.steps) == len(report_b.steps)


# --------------------------------------------------------------------------
# Constraint violation: ProofState + degraded/low-confidence
# --------------------------------------------------------------------------


def test_unknown_hard_constraint_blocks_without_dispatch():
    dispatch_fn = _make_dispatch_fn(ExecutionOutcome.SUCCEEDED, verification_passed=True)
    loop = _make_loop(dispatch_fn)
    request = _request(
        hard_constraints=(
            HardConstraint(
                constraint_id="safety-1",
                description="hard safety law",
                proof_state=ProofState.UNKNOWN,
            ),
        ),
    )

    report = loop.run(request)

    assert report.terminal_outcome is SolverOutcome.GOVERNANCE_BLOCKED
    assert report.steps[0].dispatched is False
    assert report.steps[0].decision_verdict is DecisionVerdict.BLOCK_UNKNOWN_CONSTRAINT
    # ProofState discipline: never dispatched on unknown hard constraint.
    assert dispatch_fn.calls == []


def test_proven_hard_constraint_allows_dispatch():
    dispatch_fn = _make_dispatch_fn(ExecutionOutcome.SUCCEEDED, verification_passed=True)
    loop = _make_loop(dispatch_fn)
    request = _request(
        hard_constraints=(
            HardConstraint(
                constraint_id="safety-1",
                description="hard safety law",
                proof_state=ProofState.PROVEN,
            ),
        ),
    )

    report = loop.run(request)

    assert report.terminal_outcome is SolverOutcome.SOLVED_VERIFIED
    assert len(dispatch_fn.calls) == 1
    assert report.steps[-1].dispatched is True


def test_degraded_low_confidence_safe_halts_without_dispatch():
    dispatch_fn = _make_dispatch_fn(ExecutionOutcome.SUCCEEDED, verification_passed=True)
    meta = MetaReasoningEngine(clock=_clock)
    # Drive the capability into degraded mode with very low confidence.
    meta.update_confidence(
        CapabilityConfidence(
            capability_id="noop",
            success_rate=0.05,
            verification_pass_rate=0.05,
            timeout_rate=0.0,
            error_rate=0.9,
            sample_count=20,
            assessed_at=_clock(),
        )
    )
    assert meta.is_degraded("noop") is True
    loop = _make_loop(dispatch_fn, meta=meta)

    report = loop.run(_request())

    assert report.terminal_outcome is SolverOutcome.SAFE_HALT
    assert dispatch_fn.calls == []
    assert report.steps[0].decision_verdict is DecisionVerdict.DEFER_TO_REVIEW


def test_low_confidence_replans_then_halts_without_dispatch():
    dispatch_fn = _make_dispatch_fn(ExecutionOutcome.SUCCEEDED, verification_passed=True)
    meta = MetaReasoningEngine(clock=_clock)
    # Low confidence but NOT degraded: set a custom threshold so it stays just
    # above the degraded line while landing under the replan threshold.
    meta.set_threshold("noop", 0.0)  # never degraded
    meta.update_confidence(
        CapabilityConfidence(
            capability_id="noop",
            success_rate=0.2,
            verification_pass_rate=0.2,
            timeout_rate=0.0,
            error_rate=0.5,
            sample_count=10,
            assessed_at=_clock(),
        )
    )
    assert meta.is_degraded("noop") is False
    loop = _make_loop(dispatch_fn, meta=meta, max_steps=2, step_budget=2)

    report = loop.run(_request())

    assert report.replan_count >= 1
    assert report.terminal_outcome is SolverOutcome.SAFE_HALT
    assert dispatch_fn.calls == []  # replan never dispatches on its own


# --------------------------------------------------------------------------
# Rollback safety
# --------------------------------------------------------------------------


def test_blocked_execution_rejects_and_leaves_memory_clean():
    # Governed dispatch returns a FAILED result carrying a governance_blocked
    # effect + gates_failed metadata (ExecutionOutcome has no BLOCKED member).
    dispatch_fn = _make_dispatch_fn(
        ExecutionOutcome.FAILED,
        verification_passed=False,
        governance_blocked=True,
    )
    episodic = EpisodicMemory()
    loop = _make_loop(dispatch_fn, episodic=episodic, max_steps=1, step_budget=1)

    report = loop.run(_request())

    # REJECT admission must not pollute episodic memory.
    assert episodic.size == 0
    assert report.learning_admission_count == 0
    assert report.terminal_outcome is SolverOutcome.AWAITING_EVIDENCE
    assert report.steps[-1].admission_status.value == "reject"


def test_report_is_frozen_value_object():
    report = _make_loop(
        _make_dispatch_fn(ExecutionOutcome.SUCCEEDED, verification_passed=True)
    ).run(_request())
    assert isinstance(report, CognitiveLoopReport)
    import dataclasses

    assert dataclasses.is_dataclass(report)
    # Frozen: attribute assignment must fail.
    try:
        report.rationale = "mutated"  # type: ignore[misc]
        raised = False
    except dataclasses.FrozenInstanceError:
        raised = True
    assert raised is True
