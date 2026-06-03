"""Tests for the plan-time cognitive context server integration (#3a).

Verifies default-OFF gating (fail-safe on a malformed flag) and that the
planning_context_for entrypoint returns None when disabled/absent and NEVER raises
into the caller (so the advisory read-back can never break plan compilation).
"""

from __future__ import annotations

from mcoi_runtime.app.cognitive_runtime_integration import bootstrap_cognitive_runtime
from mcoi_runtime.app.cognitive_planning_integration import (
    COGNITIVE_LOOP_PLAN_CONTEXT_ENV,
    PLANNING_READER_DEP,
    build_planning_reader,
    planning_context_for,
    validate_planning_context_config,
)
from mcoi_runtime.core.cognitive_planning import CognitivePlanningReader


def _clock() -> str:
    return "2026-06-03T00:00:00Z"


class _Deps:
    def __init__(self, store: dict) -> None:
        self._store = dict(store)

    def get(self, name: str):
        value = self._store.get(name)
        if value is None:
            raise RuntimeError("dependency not registered")
        return value


def test_flag_off_builds_no_reader():
    organs = bootstrap_cognitive_runtime(clock=_clock)
    assert build_planning_reader({}, organs) is None
    assert build_planning_reader({COGNITIVE_LOOP_PLAN_CONTEXT_ENV: "off"}, organs) is None


def test_flag_on_builds_reader():
    organs = bootstrap_cognitive_runtime(clock=_clock)
    reader = build_planning_reader({COGNITIVE_LOOP_PLAN_CONTEXT_ENV: "1"}, organs)
    assert isinstance(reader, CognitivePlanningReader)


def test_malformed_flag_fails_safe():
    report = validate_planning_context_config({COGNITIVE_LOOP_PLAN_CONTEXT_ENV: "maybe"})
    assert report.enabled is False
    assert report.error is not None
    organs = bootstrap_cognitive_runtime(clock=_clock)
    assert build_planning_reader({COGNITIVE_LOOP_PLAN_CONTEXT_ENV: "maybe"}, organs) is None


def test_context_none_when_absent():
    assert planning_context_for(_Deps({}), ("pay",)) is None


def test_context_none_when_disabled():
    assert planning_context_for(_Deps({PLANNING_READER_DEP: None}), ("pay",)) is None


def test_context_dict_when_present():
    organs = bootstrap_cognitive_runtime(clock=_clock)
    reader = build_planning_reader({COGNITIVE_LOOP_PLAN_CONTEXT_ENV: "1"}, organs)
    ctx = planning_context_for(_Deps({PLANNING_READER_DEP: reader}), ("pay", "review"))
    assert ctx is not None
    assert ctx["has_caution"] is False  # fresh organs => neutral => proceed
    assert len(ctx["capabilities"]) == 2


def test_context_swallows_reader_errors():
    class _BoomReader:
        def read(self, _capability_ids):
            raise RuntimeError("boom")

    # Advisory read-back must never break planning: error => None, never raises.
    assert planning_context_for(_Deps({PLANNING_READER_DEP: _BoomReader()}), ("pay",)) is None
