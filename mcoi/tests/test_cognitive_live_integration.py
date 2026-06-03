"""Tests for the live-acting cognitive server integration (Stage B + Stage C).

Verifies default-OFF gating (fail-safe on a malformed flag), and that the live
entrypoints are safe: the gate FAILS OPEN (a gate error => allow, never a spurious
block) and the learner entrypoint NEVER raises into the caller.
"""

from __future__ import annotations

from mcoi_runtime.app.cognitive_runtime_integration import bootstrap_cognitive_runtime
from mcoi_runtime.app.cognitive_live_integration import (
    COGNITIVE_LOOP_ENFORCE_ENV,
    COGNITIVE_LOOP_LEARN_ENV,
    EXECUTION_GATE_DEP,
    LEARNER_DEP,
    build_execution_gate,
    build_learner,
    evaluate_execution_gate,
    record_execution_learning,
    validate_enforce_config,
    validate_learn_config,
)
from mcoi_runtime.core.cognitive_live import CognitiveExecutionGate, CognitiveLearner


def _clock() -> str:
    return "2026-06-03T00:00:00Z"


class _Deps:
    """Mirrors the real deps container: get() raises on missing/None."""

    def __init__(self, store: dict) -> None:
        self._store = dict(store)

    def get(self, name: str):
        value = self._store.get(name)
        if value is None:
            raise RuntimeError("dependency not registered")
        return value


# ---------------- build / flags ----------------

def test_enforce_flag_off_builds_no_gate():
    organs = bootstrap_cognitive_runtime(clock=_clock)
    assert build_execution_gate({}, organs) is None
    assert build_execution_gate({COGNITIVE_LOOP_ENFORCE_ENV: "off"}, organs) is None


def test_enforce_flag_on_builds_gate():
    organs = bootstrap_cognitive_runtime(clock=_clock)
    assert isinstance(build_execution_gate({COGNITIVE_LOOP_ENFORCE_ENV: "1"}, organs), CognitiveExecutionGate)


def test_enforce_malformed_flag_fails_safe():
    report = validate_enforce_config({COGNITIVE_LOOP_ENFORCE_ENV: "perhaps"})
    assert report.enabled is False
    assert report.error is not None
    organs = bootstrap_cognitive_runtime(clock=_clock)
    assert build_execution_gate({COGNITIVE_LOOP_ENFORCE_ENV: "perhaps"}, organs) is None


def test_learn_flag_off_builds_no_learner():
    organs = bootstrap_cognitive_runtime(clock=_clock)
    assert build_learner({}, organs, clock=_clock) is None


def test_learn_flag_on_builds_learner():
    organs = bootstrap_cognitive_runtime(clock=_clock)
    learner = build_learner({COGNITIVE_LOOP_LEARN_ENV: "1"}, organs, clock=_clock)
    assert isinstance(learner, CognitiveLearner)


def test_learn_malformed_flag_fails_safe():
    report = validate_learn_config({COGNITIVE_LOOP_LEARN_ENV: "maybe"})
    assert report.enabled is False
    assert report.error is not None


# ---------------- gate entrypoint (fail-open) ----------------

def test_evaluate_gate_none_when_absent():
    assert evaluate_execution_gate(_Deps({}), capability_id="research") is None


def test_evaluate_gate_none_when_disabled():
    assert evaluate_execution_gate(_Deps({EXECUTION_GATE_DEP: None}), capability_id="research") is None


def test_evaluate_gate_returns_decision_when_present():
    organs = bootstrap_cognitive_runtime(clock=_clock)
    gate = build_execution_gate({COGNITIVE_LOOP_ENFORCE_ENV: "1"}, organs)
    decision = evaluate_execution_gate(_Deps({EXECUTION_GATE_DEP: gate}), capability_id="research")
    assert decision is not None
    # Fresh organs => neutral confidence => proceed, not blocked.
    assert decision.blocked is False


def test_evaluate_gate_fails_open_on_error():
    class _BoomGate:
        def evaluate(self, **kwargs):
            raise RuntimeError("boom")

    # fail-OPEN: a gate error degrades to None (=allow), never raises, never blocks.
    assert evaluate_execution_gate(_Deps({EXECUTION_GATE_DEP: _BoomGate()}), capability_id="research") is None


# ---------------- learn entrypoint (exception-isolated) ----------------

def test_record_learning_noop_when_absent():
    record_execution_learning(_Deps({}), capability_id="research", succeeded=True, verified=True, source_ref="wf-1")


def test_record_learning_noop_when_none():
    record_execution_learning(_Deps({LEARNER_DEP: None}), capability_id="research", succeeded=True, verified=True, source_ref="wf-1")


def test_record_learning_learns_when_present():
    organs = bootstrap_cognitive_runtime(clock=_clock)
    learner = build_learner({COGNITIVE_LOOP_LEARN_ENV: "1"}, organs, clock=_clock)
    deps = _Deps({LEARNER_DEP: learner})
    record_execution_learning(deps, capability_id="research", succeeded=True, verified=True, source_ref="wf-1")
    assert len(organs.episodic_memory.list_entries()) == 1


def test_record_learning_swallows_errors():
    class _BoomLearner:
        def learn(self, **kwargs):
            raise RuntimeError("boom")

    # Must never raise into the caller, even if the learner blows up.
    record_execution_learning(
        _Deps({LEARNER_DEP: _BoomLearner()}), capability_id="research", succeeded=False, verified=False, source_ref="wf-1"
    )
