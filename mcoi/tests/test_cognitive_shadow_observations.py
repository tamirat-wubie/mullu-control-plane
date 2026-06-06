"""Tests for the shadow-observations reader: summary() + read_shadow_observations.

These cover the previously-missing READER half of Stage A: the observer recorded
divergence evidence but nothing surfaced it. Verifies the aggregate Stage-B
signal (observed / would_have_blocked / diverged / divergence_rate) and the
deps-resolving, disabled-safe read helper that the GET endpoint returns verbatim.
>=3 assertions per test.
"""

from __future__ import annotations

from mcoi_runtime.app.cognitive_runtime_integration import bootstrap_cognitive_runtime
from mcoi_runtime.app.cognitive_shadow_integration import (
    COGNITIVE_LOOP_SHADOW_ENV,
    SHADOW_OBSERVER_DEP,
    build_shadow_observer,
    read_shadow_observations,
)
from mcoi_runtime.contracts.meta_reasoning import CapabilityConfidence
from mcoi_runtime.core.cognitive_shadow import CognitiveShadowSummary, ShadowCognitiveObserver


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


def _degrade(organs, capability_id: str) -> None:
    """Drive a capability into degraded/low-confidence so DECIDE would block."""
    organs.meta_reasoning.update_confidence(
        CapabilityConfidence(
            capability_id=capability_id,
            success_rate=0.05,
            verification_pass_rate=0.05,
            timeout_rate=0.0,
            error_rate=0.9,
            sample_count=20,
            assessed_at=_clock(),
        )
    )


# --------------------------------------------------------------------------
# summary() aggregation
# --------------------------------------------------------------------------


def test_summary_empty_observer_is_all_zero():
    organs = bootstrap_cognitive_runtime(clock=_clock)
    observer = build_shadow_observer({COGNITIVE_LOOP_SHADOW_ENV: "1"}, organs, clock=_clock)

    summary = observer.summary()

    assert isinstance(summary, CognitiveShadowSummary)
    assert summary.observed == 0
    assert summary.diverged == 0
    assert summary.divergence_rate == 0.0
    assert summary.diverged_capabilities == ()


def test_summary_counts_divergence_when_degraded_capability_succeeds_live():
    organs = bootstrap_cognitive_runtime(clock=_clock)
    observer = build_shadow_observer({COGNITIVE_LOOP_SHADOW_ENV: "1"}, organs, clock=_clock)
    _degrade(organs, "research")

    # Degraded capability, but the LIVE path succeeded -> divergence (Stage-B signal).
    observer.observe(capability_id="research", live_succeeded=True)
    # A healthy capability that also succeeded -> no divergence.
    observer.observe(capability_id="healthy", live_succeeded=True)

    summary = observer.summary()
    assert summary.observed == 2
    assert summary.diverged == 1
    assert summary.would_have_blocked == 1
    assert "research" in summary.diverged_capabilities
    assert 0.0 < summary.divergence_rate <= 1.0


def test_summary_no_divergence_when_degraded_capability_also_failed_live():
    organs = bootstrap_cognitive_runtime(clock=_clock)
    observer = build_shadow_observer({COGNITIVE_LOOP_SHADOW_ENV: "1"}, organs, clock=_clock)
    _degrade(organs, "research")

    # Would-have-blocked, and the live path ALSO failed -> agreement, not divergence.
    observer.observe(capability_id="research", live_succeeded=False)

    summary = observer.summary()
    assert summary.observed == 1
    assert summary.would_have_blocked == 1
    assert summary.diverged == 0  # both agree it should not have proceeded
    assert summary.divergence_rate == 0.0


# --------------------------------------------------------------------------
# read_shadow_observations (deps-resolving, disabled-safe)
# --------------------------------------------------------------------------


def test_read_disabled_when_observer_absent():
    view = read_shadow_observations(_Deps({}))
    assert view["enabled"] is False
    assert view["observations"] == []
    assert view["summary"]["observed"] == 0


def test_read_disabled_when_observer_none():
    view = read_shadow_observations(_Deps({SHADOW_OBSERVER_DEP: None}))
    assert view["enabled"] is False
    assert view["summary"]["diverged"] == 0
    assert view["observations"] == []


def test_read_surfaces_observations_and_summary_when_enabled():
    organs = bootstrap_cognitive_runtime(clock=_clock)
    observer = build_shadow_observer({COGNITIVE_LOOP_SHADOW_ENV: "1"}, organs, clock=_clock)
    _degrade(organs, "research")
    observer.observe(capability_id="research", live_succeeded=True)
    deps = _Deps({SHADOW_OBSERVER_DEP: observer})

    view = read_shadow_observations(deps, limit=10)

    assert view["enabled"] is True
    assert view["summary"]["observed"] == 1
    assert view["summary"]["diverged"] == 1
    assert "research" in view["summary"]["diverged_capabilities"]
    assert len(view["observations"]) == 1
    obs = view["observations"][0]
    assert obs["capability_id"] == "research"
    assert obs["diverged"] is True
    assert obs["decision_verdict"]  # serialized enum value (non-empty string)


def test_read_respects_limit():
    organs = bootstrap_cognitive_runtime(clock=_clock)
    observer = build_shadow_observer({COGNITIVE_LOOP_SHADOW_ENV: "1"}, organs, clock=_clock)
    for i in range(5):
        observer.observe(capability_id=f"cap-{i}", live_succeeded=True)
    deps = _Deps({SHADOW_OBSERVER_DEP: observer})

    view = read_shadow_observations(deps, limit=2)
    assert view["enabled"] is True
    assert len(view["observations"]) == 2  # capped to the most recent 2
    assert view["summary"]["observed"] == 5  # summary still reflects all retained


def test_read_zero_limit_returns_no_enabled_observations():
    organs = bootstrap_cognitive_runtime(clock=_clock)
    observer = build_shadow_observer({COGNITIVE_LOOP_SHADOW_ENV: "1"}, organs, clock=_clock)
    for i in range(3):
        observer.observe(capability_id=f"cap-{i}", live_succeeded=True)
    deps = _Deps({SHADOW_OBSERVER_DEP: observer})

    view = read_shadow_observations(deps, limit=0)

    assert view["enabled"] is True
    assert view["observations"] == []
    assert view["summary"]["observed"] == 3
