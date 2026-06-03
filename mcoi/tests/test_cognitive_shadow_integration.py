"""Tests for the shadow-observer server integration (Slice 2).

Verifies the env-flag gating (default-OFF, fail-safe on a malformed value), that
the builder wires a real observer from the mounted organs when enabled, and that
the live recording entrypoint is a no-op when disabled and never raises into the
caller (so the shadow can never perturb the live request).
"""

from __future__ import annotations

from mcoi_runtime.app.cognitive_runtime_integration import bootstrap_cognitive_runtime
from mcoi_runtime.app.cognitive_shadow_integration import (
    COGNITIVE_LOOP_SHADOW_ENV,
    SHADOW_OBSERVER_DEP,
    build_shadow_observer,
    record_execution_shadow,
    validate_cognitive_shadow_config,
)
from mcoi_runtime.core.cognitive_shadow import ShadowCognitiveObserver


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


def test_flag_off_returns_no_observer():
    organs = bootstrap_cognitive_runtime(clock=_clock)
    assert build_shadow_observer({}, organs, clock=_clock) is None
    assert build_shadow_observer({COGNITIVE_LOOP_SHADOW_ENV: "off"}, organs, clock=_clock) is None
    assert build_shadow_observer({COGNITIVE_LOOP_SHADOW_ENV: "0"}, organs, clock=_clock) is None


def test_flag_on_builds_observer():
    organs = bootstrap_cognitive_runtime(clock=_clock)
    observer = build_shadow_observer({COGNITIVE_LOOP_SHADOW_ENV: "1"}, organs, clock=_clock)
    assert isinstance(observer, ShadowCognitiveObserver)


def test_malformed_flag_fails_safe_disabled():
    report = validate_cognitive_shadow_config({COGNITIVE_LOOP_SHADOW_ENV: "maybe"})
    assert report.enabled is False
    assert report.error is not None
    organs = bootstrap_cognitive_runtime(clock=_clock)
    # Fail-safe: a typo disables the observer rather than crashing startup.
    assert build_shadow_observer({COGNITIVE_LOOP_SHADOW_ENV: "maybe"}, organs, clock=_clock) is None


def test_record_is_noop_when_observer_absent():
    deps = _Deps({})  # nothing registered
    record_execution_shadow(deps, capability_id="research", succeeded=True)  # must not raise


def test_record_is_noop_when_observer_none():
    deps = _Deps({SHADOW_OBSERVER_DEP: None})
    record_execution_shadow(deps, capability_id="research", succeeded=True)  # must not raise


def test_record_observes_when_observer_present():
    organs = bootstrap_cognitive_runtime(clock=_clock)
    observer = build_shadow_observer({COGNITIVE_LOOP_SHADOW_ENV: "1"}, organs, clock=_clock)
    deps = _Deps({SHADOW_OBSERVER_DEP: observer})
    record_execution_shadow(deps, capability_id="research", succeeded=True)
    assert len(observer.recent_reports()) == 1
    assert observer.recent_reports()[0].capability_id == "research"


def test_record_swallows_observer_errors():
    class _BoomObserver:
        def observe(self, **kwargs):
            raise RuntimeError("boom")

    deps = _Deps({SHADOW_OBSERVER_DEP: _BoomObserver()})
    # The shadow must never perturb the live path: the error is swallowed.
    record_execution_shadow(deps, capability_id="research", succeeded=False)
