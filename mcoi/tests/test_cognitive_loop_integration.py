"""Tests for the cognitive loop integration wiring.

Covers: default-OFF returns None and leaves the existing dispatch untouched,
enabled wiring returns a CognitiveLoop built from runtime engines, malformed
flag is a hard validation error, and the bootstrap exposes decision_learning.
"""
from __future__ import annotations

import pytest

from mcoi_runtime.app.bootstrap import bootstrap_runtime
from mcoi_runtime.app.cognitive_loop_integration import (
    COGNITIVE_LOOP_ENABLED_ENV,
    CognitiveLoopConfigReport,
    build_cognitive_loop,
    validate_cognitive_loop_config,
)
from mcoi_runtime.core.cognitive_loop import CognitiveLoop
from mcoi_runtime.core.decision_learning import DecisionLearningEngine


def _clock() -> str:
    return "2026-01-01T00:00:00Z"


def test_validate_disabled_by_default():
    report = validate_cognitive_loop_config({})
    assert isinstance(report, CognitiveLoopConfigReport)
    assert report.enabled is False
    assert report.error is None


def test_validate_accepts_truthy():
    report = validate_cognitive_loop_config({COGNITIVE_LOOP_ENABLED_ENV: "1"})
    assert report.enabled is True
    assert report.error is None


def test_validate_rejects_unknown_value():
    report = validate_cognitive_loop_config({COGNITIVE_LOOP_ENABLED_ENV: "maybe"})
    assert report.enabled is False
    assert report.error is not None
    assert COGNITIVE_LOOP_ENABLED_ENV in report.error


def test_build_disabled_by_default_returns_none():
    runtime = bootstrap_runtime(clock=_clock)
    loop = build_cognitive_loop({}, runtime)
    # Default-OFF: nothing is attached and the runtime is left intact.
    assert loop is None
    assert runtime.governed_dispatcher is not None
    assert isinstance(runtime.decision_learning, DecisionLearningEngine)


def test_build_malformed_flag_raises():
    runtime = bootstrap_runtime(clock=_clock)
    with pytest.raises(ValueError):
        build_cognitive_loop({COGNITIVE_LOOP_ENABLED_ENV: "perhaps"}, runtime)


def test_build_enabled_returns_wired_loop():
    runtime = bootstrap_runtime(clock=_clock)
    loop = build_cognitive_loop({COGNITIVE_LOOP_ENABLED_ENV: "true"}, runtime)
    assert isinstance(loop, CognitiveLoop)
    # Idempotent: a second build yields an independent, equivalent handle.
    loop_again = build_cognitive_loop({COGNITIVE_LOOP_ENABLED_ENV: "true"}, runtime)
    assert isinstance(loop_again, CognitiveLoop)
    assert loop_again is not loop


def test_bootstrap_exposes_decision_learning():
    # The bootstrap touch must instantiate DecisionLearningEngine (was nowhere).
    runtime = bootstrap_runtime(clock=_clock)
    assert isinstance(runtime.decision_learning, DecisionLearningEngine)
    assert runtime.decision_learning.outcome_count == 0
    assert runtime.meta_reasoning is not None
