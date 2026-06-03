"""Tests for mounting the cognitive organs into the served runtime.

Verifies the organs are constructed, optionally rehydrated from the D1 cognitive
outcome ledger, and registered on the deps container. The no-ledger path remains
pure/in-memory and byte-identical to the original Slice 1 bootstrap.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from mcoi_runtime.app.cognitive_live_integration import (
    COGNITIVE_LOOP_LEDGER_ENV,
    COGNITIVE_LOOP_LEDGER_PATH_ENV,
)
from mcoi_runtime.app.cognitive_runtime_integration import (
    CognitiveRuntime,
    CognitiveRuntimeRehydrateReport,
    bootstrap_cognitive_runtime,
    build_rehydrate_ledger,
    rehydrate_cognitive_runtime_from_ledger,
    register_cognitive_runtime,
)
from mcoi_runtime.core.cognitive_live import CognitiveLearner
from mcoi_runtime.core.decision_learning import DecisionLearningEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, stable_identifier
from mcoi_runtime.core.memory import EpisodicMemory, WorkingMemory
from mcoi_runtime.core.meta_reasoning import MetaReasoningEngine
from mcoi_runtime.core.world_state import WorldStateEngine
from mcoi_runtime.persistence.cognitive_outcome_ledger import (
    CognitiveOutcomeEntry,
    CognitiveOutcomeEvent,
    FileBackedCognitiveOutcomeLedger,
)


def _clock() -> str:
    return "2026-06-03T00:00:00Z"


class _FakeDeps:
    def __init__(self) -> None:
        self.store: dict = {}

    def set(self, name: str, value) -> None:
        self.store[name] = value


def _seed_ledger(tmp_path, *, tenant_id: str = "system") -> FileBackedCognitiveOutcomeLedger:
    ledger = FileBackedCognitiveOutcomeLedger(base_path=tmp_path, tenant_id=tenant_id)
    learner = CognitiveLearner(
        meta_reasoning=MetaReasoningEngine(clock=_clock),
        episodic_memory=EpisodicMemory(),
        clock=_clock,
        ledger=ledger,
        tenant_id=tenant_id,
    )
    learner.learn(
        capability_id="llm.completion",
        succeeded=True,
        verified=True,
        source_ref="wf-success",
    )
    learner.learn(
        capability_id="llm.completion",
        succeeded=False,
        verified=True,
        source_ref="wf-fail",
    )
    return ledger


@dataclass(frozen=True)
class _FakeLedger:
    entries: tuple[CognitiveOutcomeEntry, ...]
    latest: int | None = None
    validate_error: Exception | None = None

    def append(self, event):  # pragma: no cover - Protocol filler
        raise NotImplementedError

    def replay(self):
        return iter(self.entries)

    def validate(self):
        if self.validate_error is not None:
            raise self.validate_error
        return None

    def latest_sequence(self):
        return self.latest


class _SlowLedger:
    def append(self, event):  # pragma: no cover - Protocol filler
        raise NotImplementedError

    def replay(self):
        return iter(())

    def validate(self):
        import time

        time.sleep(0.05)

    def latest_sequence(self):
        return None


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


def test_build_rehydrate_ledger_default_off_returns_none(tmp_path):
    assert build_rehydrate_ledger({COGNITIVE_LOOP_LEDGER_PATH_ENV: str(tmp_path)}) is None


def test_build_rehydrate_ledger_enabled_requires_path():
    with pytest.raises(RuntimeCoreInvariantError):
        build_rehydrate_ledger({COGNITIVE_LOOP_LEDGER_ENV: "1"})


def test_build_rehydrate_ledger_malformed_flag_fails_closed():
    with pytest.raises(RuntimeCoreInvariantError):
        build_rehydrate_ledger({COGNITIVE_LOOP_LEDGER_ENV: "maybe"})


def test_build_rehydrate_ledger_enabled_builds_file_backed(tmp_path):
    ledger = build_rehydrate_ledger(
        {
            COGNITIVE_LOOP_LEDGER_ENV: "1",
            COGNITIVE_LOOP_LEDGER_PATH_ENV: str(tmp_path),
        },
        tenant_id="tenant-A",
    )
    assert isinstance(ledger, FileBackedCognitiveOutcomeLedger)


def test_bootstrap_with_ledger_rehydrates_before_return(tmp_path):
    ledger = _seed_ledger(tmp_path, tenant_id="system")
    runtime = bootstrap_cognitive_runtime(clock=_clock, ledger=ledger)
    confidence = runtime.meta_reasoning.get_confidence("llm.completion")
    assert confidence is not None
    assert confidence.sample_count == 2
    outcomes = runtime.episodic_memory.list_entries(category="cognitive_loop_outcome")
    assert len(outcomes) == 1
    assert outcomes[0].content["source_ref"] == "wf-success"


def test_rehydrate_returns_report(tmp_path):
    ledger = _seed_ledger(tmp_path, tenant_id="system")
    runtime = bootstrap_cognitive_runtime(clock=_clock)
    report = rehydrate_cognitive_runtime_from_ledger(runtime, ledger)
    assert isinstance(report, CognitiveRuntimeRehydrateReport)
    assert report.events_seen == 2
    assert report.events_applied == 2
    assert report.duplicate_events_skipped == 0
    assert report.last_sequence == 1


def test_rehydrate_prior_confidence_mismatch_fails_closed():
    admitted_id = stable_identifier(
        "cognitive-live-outcome",
        {"capability_id": "cap.A", "source_ref": "wf-1"},
    )
    bad_event = CognitiveOutcomeEvent(
        tenant_id="system",
        capability_id="cap.A",
        succeeded=True,
        verified=True,
        admitted_entry_id=admitted_id,
        source_ref="wf-1",
        learned_at=_clock(),
        prior_confidence=0.7,  # first event must start from neutral 0.5
        next_confidence=1.0,
    )
    entry = CognitiveOutcomeEntry(
        sequence=0,
        event=bad_event,
        content_hash="a" * 64,
        chain_hash="b" * 64,
        previous_chain_hash="0" * 64,
        recorded_at=_clock(),
    )
    runtime = bootstrap_cognitive_runtime(clock=_clock)
    with pytest.raises(RuntimeCoreInvariantError):
        rehydrate_cognitive_runtime_from_ledger(runtime, _FakeLedger((entry,), latest=0))
    assert runtime.meta_reasoning.get_confidence("cap.A") is None
    assert runtime.episodic_memory.size == 0


def test_rehydrate_admitted_entry_mismatch_fails_closed():
    bad_event = CognitiveOutcomeEvent(
        tenant_id="system",
        capability_id="cap.A",
        succeeded=True,
        verified=True,
        admitted_entry_id="wrong-id",
        source_ref="wf-1",
        learned_at=_clock(),
        prior_confidence=0.5,
        next_confidence=1.0,
    )
    entry = CognitiveOutcomeEntry(
        sequence=0,
        event=bad_event,
        content_hash="a" * 64,
        chain_hash="b" * 64,
        previous_chain_hash="0" * 64,
        recorded_at=_clock(),
    )
    runtime = bootstrap_cognitive_runtime(clock=_clock)
    with pytest.raises(RuntimeCoreInvariantError):
        rehydrate_cognitive_runtime_from_ledger(runtime, _FakeLedger((entry,), latest=0))
    assert runtime.meta_reasoning.get_confidence("cap.A") is None
    assert runtime.episodic_memory.size == 0


def test_rehydrate_validation_error_fails_before_mutation():
    runtime = bootstrap_cognitive_runtime(clock=_clock)
    with pytest.raises(RuntimeCoreInvariantError):
        rehydrate_cognitive_runtime_from_ledger(
            runtime,
            _FakeLedger((), validate_error=RuntimeCoreInvariantError("bad chain")),
        )
    assert runtime.episodic_memory.size == 0


def test_rehydrate_timeout_fails_closed_before_mutation():
    runtime = bootstrap_cognitive_runtime(clock=_clock)
    with pytest.raises(RuntimeCoreInvariantError):
        rehydrate_cognitive_runtime_from_ledger(
            runtime,
            _SlowLedger(),
            timeout_seconds=0.001,
        )
    assert runtime.episodic_memory.size == 0


def test_rehydrate_duplicate_identical_event_is_skipped(tmp_path):
    ledger = _seed_ledger(tmp_path, tenant_id="system")
    entries = tuple(ledger.replay())
    runtime = bootstrap_cognitive_runtime(clock=_clock)
    report = rehydrate_cognitive_runtime_from_ledger(
        runtime,
        _FakeLedger(entries=(entries[0], entries[0]), latest=0),
    )
    assert report.events_seen == 2
    assert report.events_applied == 1
    assert report.duplicate_events_skipped == 1
    assert runtime.episodic_memory.size == 1
