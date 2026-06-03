"""Tests for mounting the cognitive organs into the served runtime (Slice 1).

Verifies the organs are constructed (mirroring the CLI bootstrap) and registered
on the deps container. This wiring is additive: it only makes the engines
available; nothing on the live path reads them in this slice.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.app.cognitive_runtime_integration import (
    CognitiveRuntime,
    bootstrap_cognitive_runtime,
    register_cognitive_runtime,
)
from mcoi_runtime.core.decision_learning import DecisionLearningEngine
from mcoi_runtime.core.memory import EpisodicMemory, WorkingMemory
from mcoi_runtime.core.meta_reasoning import MetaReasoningEngine
from mcoi_runtime.core.world_state import WorldStateEngine


def _clock() -> str:
    return "2026-06-03T00:00:00Z"


class _FakeDeps:
    def __init__(self) -> None:
        self.store: dict = {}

    def set(self, name: str, value) -> None:
        self.store[name] = value


def test_bootstrap_constructs_all_organs():
    runtime = bootstrap_cognitive_runtime(clock=_clock)
    assert isinstance(runtime, CognitiveRuntime)
    assert isinstance(runtime.world_state, WorldStateEngine)
    assert isinstance(runtime.meta_reasoning, MetaReasoningEngine)
    assert isinstance(runtime.decision_learning, DecisionLearningEngine)
    assert isinstance(runtime.episodic_memory, EpisodicMemory)
    assert isinstance(runtime.working_memory, WorkingMemory)


def test_bootstrap_requires_clock():
    with pytest.raises(ValueError):
        bootstrap_cognitive_runtime(clock=None)


def test_register_exposes_each_organ_on_deps():
    runtime = bootstrap_cognitive_runtime(clock=_clock)
    deps = _FakeDeps()
    register_cognitive_runtime(deps, runtime)
    for key in (
        "cognitive_runtime",
        "world_state",
        "meta_reasoning",
        "decision_learning",
        "episodic_memory",
        "working_memory",
    ):
        assert key in deps.store, f"expected {key} registered on deps"
    assert deps.store["meta_reasoning"] is runtime.meta_reasoning
    assert deps.store["world_state"] is runtime.world_state
