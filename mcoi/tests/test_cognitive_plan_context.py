"""Stage D - organ READ-back into routers (CognitivePlanContext + endpoint).

Covers:
  * CognitivePlanContext invariants (range/non-negative/sorted/static fields).
  * build_plan_context with full organs, missing organs, partial organs, and
    organs whose methods raise -- fail-OPEN per organ to a safe default.
  * Determinism: identical organ state yields identical snapshots (hashable).
  * validate_read_config / read_plan_context wrappers (flag parsing + deps
    lookup + wholesale fail-OPEN at the wrapper boundary).
  * GET /api/v1/cognitive-loop/plan-context/{capability_id}:
      - flag off => 503 with stable disabled detail (route discoverable).
      - flag on, no cognitive_runtime mounted => 200 with available=false +
        safe defaults (no 500).
      - flag on, populated organs => 200 with the snapshot fields.
"""

from __future__ import annotations

import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mcoi_runtime.app.cognitive_live_integration import (
    COGNITIVE_LOOP_READ_ENV,
    COGNITIVE_RUNTIME_DEP,
    plan_context_disabled_detail,
    read_plan_context,
    validate_read_config,
)
from mcoi_runtime.app.routers.cognitive_state import router as cognitive_state_router
from mcoi_runtime.app.routers.deps import deps
from mcoi_runtime.core.cognitive_live import (
    CognitivePlanContext,
    build_plan_context,
)
from mcoi_runtime.core.decision_learning import DecisionLearningEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.memory import EpisodicMemory, MemoryEntry, MemoryTier
from mcoi_runtime.core.meta_reasoning import MetaReasoningEngine
from mcoi_runtime.core.world_state import WorldStateEngine


def _clock() -> str:
    return "2026-06-03T12:00:00+00:00"


class _MetricsStub:
    def __init__(self) -> None:
        self.counts: dict[str, int] = {}

    def inc(self, name: str, value: int = 1) -> None:
        self.counts[name] = self.counts.get(name, 0) + value


# ---------- CognitivePlanContext invariants ----------


def test_plan_context_rejects_invalid_capability_id():
    with pytest.raises(RuntimeCoreInvariantError):
        CognitivePlanContext(
            capability_id="   ",
            confidence=0.5,
            degraded=False,
            prior_outcomes_count=0,
            prior_success_count=0,
            learned_factor_adjustments=(),
            learned_adjustment_count=0,
            world_entity_count=0,
            world_snapshot_hash=None,
        )


def test_plan_context_rejects_out_of_range_confidence():
    with pytest.raises(RuntimeCoreInvariantError):
        CognitivePlanContext(
            capability_id="llm.completion",
            confidence=1.5,
            degraded=False,
            prior_outcomes_count=0,
            prior_success_count=0,
            learned_factor_adjustments=(),
            learned_adjustment_count=0,
            world_entity_count=0,
            world_snapshot_hash=None,
        )


def test_plan_context_rejects_success_count_above_outcomes():
    with pytest.raises(RuntimeCoreInvariantError):
        CognitivePlanContext(
            capability_id="llm.completion",
            confidence=0.5,
            degraded=False,
            prior_outcomes_count=2,
            prior_success_count=5,
            learned_factor_adjustments=(),
            learned_adjustment_count=0,
            world_entity_count=0,
            world_snapshot_hash=None,
        )


def test_plan_context_is_hashable_and_deterministic():
    a = CognitivePlanContext(
        capability_id="llm.completion",
        confidence=0.72,
        degraded=False,
        prior_outcomes_count=3,
        prior_success_count=2,
        learned_factor_adjustments=(("factor.a", 0.5), ("factor.b", -0.25)),
        learned_adjustment_count=2,
        world_entity_count=4,
        world_snapshot_hash="abc",
    )
    b = CognitivePlanContext(
        capability_id="llm.completion",
        confidence=0.72,
        degraded=False,
        prior_outcomes_count=3,
        prior_success_count=2,
        learned_factor_adjustments=(("factor.a", 0.5), ("factor.b", -0.25)),
        learned_adjustment_count=2,
        world_entity_count=4,
        world_snapshot_hash="abc",
    )
    assert a == b
    assert hash(a) == hash(b)


# ---------- build_plan_context: fail-OPEN per organ ----------


def test_build_plan_context_with_all_organs_missing_returns_defaults():
    context = build_plan_context(
        capability_id="llm.completion",
        meta_reasoning=None,
        episodic_memory=None,
        decision_learning=None,
        world_state=None,
    )
    assert context.capability_id == "llm.completion"
    assert context.confidence == 0.5
    assert context.degraded is False
    assert context.prior_outcomes_count == 0
    assert context.prior_success_count == 0
    assert context.learned_factor_adjustments == ()
    assert context.learned_adjustment_count == 0
    assert context.world_entity_count == 0
    assert context.world_snapshot_hash is None


class _RaisingMetaReasoning:
    def get_confidence(self, capability_id: str):
        raise RuntimeError("synthetic-meta-failure")

    def is_degraded(self, capability_id: str) -> bool:
        raise RuntimeError("synthetic-meta-failure")


class _RaisingEpisodic:
    def list_entries(self, *, category=None):
        raise RuntimeError("synthetic-episodic-failure")


class _RaisingDecisionLearning:
    @property
    def adjustment_count(self) -> int:
        raise RuntimeError("synthetic-dl-failure")

    def get_learned_factor_adjustments(self):
        raise RuntimeError("synthetic-dl-failure")


class _RaisingWorld:
    def list_entities(self, *, entity_type=None):
        raise RuntimeError("synthetic-world-failure")

    def snapshot_hash(self) -> str:
        raise RuntimeError("synthetic-world-failure")


def test_build_plan_context_swallows_per_organ_failures():
    context = build_plan_context(
        capability_id="llm.completion",
        meta_reasoning=_RaisingMetaReasoning(),
        episodic_memory=_RaisingEpisodic(),
        decision_learning=_RaisingDecisionLearning(),
        world_state=_RaisingWorld(),
    )
    assert context.confidence == 0.5
    assert context.degraded is False
    assert context.prior_outcomes_count == 0
    assert context.prior_success_count == 0
    assert context.learned_factor_adjustments == ()
    assert context.learned_adjustment_count == 0
    assert context.world_entity_count == 0
    assert context.world_snapshot_hash is None


def test_build_plan_context_with_populated_organs_returns_snapshot():
    meta = MetaReasoningEngine(clock=_clock)
    decision_learning = DecisionLearningEngine(clock=_clock)
    episodic = EpisodicMemory()
    world = WorldStateEngine()

    # Admit two prior outcomes for the SAME capability_id; one success.
    episodic.admit(
        MemoryEntry(
            entry_id="e1",
            tier=MemoryTier.EPISODIC,
            category="cognitive_loop_outcome",
            content={"capability_id": "llm.completion", "succeeded": True, "verified": True},
            source_ids=("e1",),
        )
    )
    episodic.admit(
        MemoryEntry(
            entry_id="e2",
            tier=MemoryTier.EPISODIC,
            category="cognitive_loop_outcome",
            content={"capability_id": "llm.completion", "succeeded": False, "verified": True},
            source_ids=("e2",),
        )
    )
    # An entry for a DIFFERENT capability must not be counted.
    episodic.admit(
        MemoryEntry(
            entry_id="e3",
            tier=MemoryTier.EPISODIC,
            category="cognitive_loop_outcome",
            content={"capability_id": "other.cap", "succeeded": True, "verified": True},
            source_ids=("e3",),
        )
    )
    # An entry in a DIFFERENT category must not be counted (filter scoped).
    episodic.admit(
        MemoryEntry(
            entry_id="e4",
            tier=MemoryTier.EPISODIC,
            category="other_category",
            content={"capability_id": "llm.completion", "succeeded": True, "verified": True},
            source_ids=("e4",),
        )
    )

    context = build_plan_context(
        capability_id="llm.completion",
        meta_reasoning=meta,
        episodic_memory=episodic,
        decision_learning=decision_learning,
        world_state=world,
    )
    assert context.capability_id == "llm.completion"
    assert context.prior_outcomes_count == 2
    assert context.prior_success_count == 1
    # Decision-learning starts empty; just confirm fields are populated by the read.
    assert context.learned_adjustment_count == 0
    # World snapshot hash is whatever the engine returns; not None for a real engine.
    assert isinstance(context.world_snapshot_hash, str)


def test_build_plan_context_is_deterministic_for_identical_state():
    """Two builds against the same engine state must produce identical snapshots."""
    meta = MetaReasoningEngine(clock=_clock)
    episodic = EpisodicMemory()
    decision_learning = DecisionLearningEngine(clock=_clock)
    world = WorldStateEngine()

    episodic.admit(
        MemoryEntry(
            entry_id="e1",
            tier=MemoryTier.EPISODIC,
            category="cognitive_loop_outcome",
            content={"capability_id": "cap.x", "succeeded": True, "verified": True},
            source_ids=("e1",),
        )
    )

    first = build_plan_context(
        capability_id="cap.x",
        meta_reasoning=meta,
        episodic_memory=episodic,
        decision_learning=decision_learning,
        world_state=world,
    )
    second = build_plan_context(
        capability_id="cap.x",
        meta_reasoning=meta,
        episodic_memory=episodic,
        decision_learning=decision_learning,
        world_state=world,
    )
    assert first == second
    assert hash(first) == hash(second)


# ---------- validate_read_config ----------


def test_validate_read_config_default_off():
    report = validate_read_config({})
    assert report.enabled is False
    assert report.error is None


@pytest.mark.parametrize("raw", ["1", "true", "yes", "on", "TRUE", "  on  "])
def test_validate_read_config_accepts_truthy_values(raw):
    assert validate_read_config({COGNITIVE_LOOP_READ_ENV: raw}).enabled is True


@pytest.mark.parametrize("raw", ["0", "false", "no", "off", ""])
def test_validate_read_config_accepts_falsy_values(raw):
    assert validate_read_config({COGNITIVE_LOOP_READ_ENV: raw}).enabled is False


def test_validate_read_config_rejects_malformed_value_fail_safe():
    report = validate_read_config({COGNITIVE_LOOP_READ_ENV: "maybe"})
    assert report.enabled is False  # disabled, not raising
    assert report.error is not None  # error surfaced for startup logging


# ---------- read_plan_context wrapper (deps) ----------


class _MiniRuntime:
    def __init__(self) -> None:
        self.meta_reasoning = None
        self.episodic_memory = None
        self.decision_learning = None
        self.world_state = None


class _DepsStub:
    def __init__(self, values: dict[str, object]) -> None:
        self._values = values

    def get(self, key: str):
        return self._values.get(key)


def test_read_plan_context_returns_none_when_runtime_absent():
    assert read_plan_context(_DepsStub({}), capability_id="llm.completion") is None


def test_read_plan_context_returns_none_when_runtime_is_none():
    assert read_plan_context(_DepsStub({COGNITIVE_RUNTIME_DEP: None}), capability_id="llm.completion") is None


def test_read_plan_context_returns_context_with_empty_runtime():
    runtime = _MiniRuntime()
    context = read_plan_context(_DepsStub({COGNITIVE_RUNTIME_DEP: runtime}), capability_id="llm.completion")
    assert context is not None
    assert context.confidence == 0.5
    assert context.prior_outcomes_count == 0


def test_read_plan_context_swallows_internal_error():
    class _ExplodingRuntime:
        def __getattr__(self, _name):
            raise RuntimeError("synthetic")

    # build_plan_context will iterate attributes; the wrapper must NEVER raise.
    assert read_plan_context(_DepsStub({COGNITIVE_RUNTIME_DEP: _ExplodingRuntime()}), capability_id="llm.completion") is None


# ---------- HTTP endpoint (integration) ----------


def _client_with_runtime(runtime: object | None) -> TestClient:
    deps.set("metrics", _MetricsStub())
    if runtime is not None:
        deps.set(COGNITIVE_RUNTIME_DEP, runtime)
    app = FastAPI()
    app.include_router(cognitive_state_router)
    return TestClient(app)


@pytest.fixture(autouse=True)
def _reset_read_env(monkeypatch):
    monkeypatch.delenv(COGNITIVE_LOOP_READ_ENV, raising=False)
    yield


def test_endpoint_returns_503_when_flag_off(monkeypatch):
    monkeypatch.delenv(COGNITIVE_LOOP_READ_ENV, raising=False)
    client = _client_with_runtime(None)
    response = client.get("/api/v1/cognitive-loop/plan-context/llm.completion")
    assert response.status_code == 503
    body = response.json()
    assert body["detail"] == plan_context_disabled_detail()


def test_endpoint_returns_200_available_false_when_runtime_missing(monkeypatch):
    monkeypatch.setenv(COGNITIVE_LOOP_READ_ENV, "1")
    # Explicitly clear the runtime dep so we exercise the "available=False" path.
    deps.set(COGNITIVE_RUNTIME_DEP, None)
    client = _client_with_runtime(None)
    response = client.get("/api/v1/cognitive-loop/plan-context/llm.completion")
    assert response.status_code == 200
    body = response.json()
    assert body["available"] is False
    assert body["governed"] is True
    assert body["execution_authority"] is False
    assert body["capability_id"] == "llm.completion"
    assert body["confidence"] == 0.5
    assert body["prior_outcomes_count"] == 0
    assert body["learned_factor_adjustments"] == []


def test_endpoint_returns_populated_context_when_runtime_present(monkeypatch):
    monkeypatch.setenv(COGNITIVE_LOOP_READ_ENV, "1")
    runtime = _MiniRuntime()
    runtime.meta_reasoning = MetaReasoningEngine(clock=_clock)
    runtime.decision_learning = DecisionLearningEngine(clock=_clock)
    runtime.episodic_memory = EpisodicMemory()
    runtime.world_state = WorldStateEngine()
    runtime.episodic_memory.admit(
        MemoryEntry(
            entry_id="ep-1",
            tier=MemoryTier.EPISODIC,
            category="cognitive_loop_outcome",
            content={"capability_id": "llm.completion", "succeeded": True, "verified": True},
            source_ids=("ep-1",),
        )
    )
    client = _client_with_runtime(runtime)
    response = client.get("/api/v1/cognitive-loop/plan-context/llm.completion")
    assert response.status_code == 200
    body = response.json()
    assert body["available"] is True
    assert body["governed"] is True
    assert body["execution_authority"] is False
    assert body["capability_id"] == "llm.completion"
    assert body["prior_outcomes_count"] == 1
    assert body["prior_success_count"] == 1
    assert isinstance(body["world_snapshot_hash"], str)


def test_endpoint_swallows_organ_failures(monkeypatch):
    monkeypatch.setenv(COGNITIVE_LOOP_READ_ENV, "1")

    class _Brittle:
        meta_reasoning = _RaisingMetaReasoning()
        episodic_memory = _RaisingEpisodic()
        decision_learning = _RaisingDecisionLearning()
        world_state = _RaisingWorld()

    runtime = _Brittle()
    client = _client_with_runtime(runtime)
    response = client.get("/api/v1/cognitive-loop/plan-context/llm.completion")
    assert response.status_code == 200
    body = response.json()
    # Per-organ fail-OPEN to safe defaults; route stays 200 (never 500).
    assert body["available"] is True
    assert body["confidence"] == 0.5
    assert body["prior_outcomes_count"] == 0


def test_endpoint_static_disabled_detail_matches_helper():
    """The 503 detail body must come from the shared static helper.

    Guards against a future drift where a router-local string starts to
    interpolate caller text and trips the reflective-contract guard.
    """
    detail = plan_context_disabled_detail()
    assert detail["error_code"] == "cognitive_loop_read_disabled"
    assert detail["error"] == "cognitive plan-context read is disabled"
    assert detail["governed"] is True


def test_environ_flag_is_read_from_real_os_environ(monkeypatch):
    """End-to-end: the router actually consults os.environ at call time.

    Toggles the env var between two requests and verifies the responses change
    accordingly (no caching of the flag inside the router on import).
    """
    monkeypatch.delenv(COGNITIVE_LOOP_READ_ENV, raising=False)
    client = _client_with_runtime(None)
    assert client.get("/api/v1/cognitive-loop/plan-context/c1").status_code == 503
    os.environ[COGNITIVE_LOOP_READ_ENV] = "1"
    try:
        assert client.get("/api/v1/cognitive-loop/plan-context/c1").status_code == 200
    finally:
        os.environ.pop(COGNITIVE_LOOP_READ_ENV, None)
