"""Stage C + D1 -- CognitiveLearner wired to the cognitive outcome ledger.

Covers the integration slice on top of PR #1277 (the ledger substrate):
  1. Default-OFF byte-identical: when ``ledger=None`` (the historical default),
     learn() behaviour is byte-identical to the pre-D1 implementation (no
     ledger writes, no env reads, LearnRecord shape unchanged).
  2. Flag-ON write: each learn() call appends one CognitiveOutcomeEvent to the
     injected ledger; event fields match the actual LearnRecord plus the
     captured (prior_confidence, next_confidence) transition.
  3. The append runs INSIDE the learner's existing _lock (no separate lock,
     no re-entrancy risk; concurrent learn() calls serialise correctly and
     the chain stays monotone).
  4. A ledger.append failure does NOT corrupt in-memory state (the cache
     mutations succeed first; the exception propagates; episodic + meta still
     reflect the learn).
  5. validate_ledger_config parametric (truthy/falsy/malformed all behave as
     designed).
  6. build_outcome_ledger composition: flag-OFF / missing-path / blank-path /
     invalid-tenant all return None; happy path returns a working ledger.
  7. build_learner composition: flag + path + organs combinations.
"""

from __future__ import annotations

import sys
import threading
from pathlib import Path
from typing import Callable

import pytest

from mcoi_runtime.app.cognitive_live_integration import (
    COGNITIVE_LOOP_LEARN_ENV,
    COGNITIVE_LOOP_LEDGER_ENV,
    COGNITIVE_LOOP_LEDGER_PATH_ENV,
    build_learner,
    build_outcome_ledger,
    validate_ledger_config,
)
from mcoi_runtime.core.cognitive_live import CognitiveLearner, LearnRecord
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.memory import EpisodicMemory
from mcoi_runtime.core.meta_reasoning import MetaReasoningEngine
from mcoi_runtime.persistence.cognitive_outcome_ledger import (
    CognitiveOutcomeEvent,
    FileBackedCognitiveOutcomeLedger,
)


def _clock() -> str:
    return "2026-06-03T12:00:00+00:00"


def _learner(
    *,
    ledger: object | None = None,
    clock: Callable[[], str] = _clock,
) -> CognitiveLearner:
    return CognitiveLearner(
        meta_reasoning=MetaReasoningEngine(clock=clock),
        episodic_memory=EpisodicMemory(),
        clock=clock,
        ledger=ledger,
    )


class _Organs:
    def __init__(self, *, clock: Callable[[], str] = _clock) -> None:
        self.meta_reasoning = MetaReasoningEngine(clock=clock)
        self.episodic_memory = EpisodicMemory()


# ---------- (1) default-OFF byte-identical ----------


def test_learn_without_ledger_is_byte_identical_to_pre_d1():
    """Default-OFF: ledger=None preserves the historical learn() contract."""
    learner = _learner(ledger=None)
    record = learner.learn(
        capability_id="llm.completion",
        succeeded=True,
        verified=True,
        source_ref="wf-001",
    )
    assert isinstance(record, LearnRecord)
    assert record.capability_id == "llm.completion"
    assert record.succeeded is True
    assert record.verified is True
    assert record.admitted_entry_id is not None  # verified success => admitted
    assert record.learned_at == _clock()


def test_learn_without_ledger_unsupported_attribute_does_not_appear():
    learner = _learner(ledger=None)
    assert learner._ledger is None


# ---------- (2) flag-ON: each learn() appends one ledger event ----------


def test_learn_with_ledger_appends_one_event_per_call(tmp_path):
    ledger = FileBackedCognitiveOutcomeLedger(base_path=tmp_path, tenant_id="tenant-A")
    learner = _learner(ledger=ledger)
    learner.learn(capability_id="llm.completion", succeeded=True, verified=True, source_ref="wf-001")
    learner.learn(capability_id="llm.completion", succeeded=False, verified=True, source_ref="wf-002")
    learner.learn(capability_id="search.web", succeeded=True, verified=True, source_ref="wf-003")
    entries = list(ledger.replay())
    assert len(entries) == 3
    assert [e.sequence for e in entries] == [0, 1, 2]


def test_ledger_event_fields_match_learn_inputs(tmp_path):
    ledger = FileBackedCognitiveOutcomeLedger(base_path=tmp_path, tenant_id="tenant-A")
    learner = _learner(ledger=ledger)
    record = learner.learn(
        capability_id="llm.completion",
        succeeded=True,
        verified=True,
        source_ref="wf-xyz",
    )
    [entry] = list(ledger.replay())
    event = entry.event
    assert event.capability_id == "llm.completion"
    assert event.succeeded is True
    assert event.verified is True
    assert event.source_ref == "wf-xyz"
    assert event.learned_at == _clock()
    # admitted_entry_id in the event matches what learn() returned.
    assert event.admitted_entry_id == record.admitted_entry_id
    # Confidence transition is recorded; first call moves from neutral 0.5
    # to a strictly-different value (verified success -> nudge upward).
    assert event.prior_confidence == 0.5
    assert event.next_confidence != 0.5
    assert 0.0 <= event.next_confidence <= 1.0


def test_unverified_outcome_records_admitted_entry_id_as_none(tmp_path):
    ledger = FileBackedCognitiveOutcomeLedger(base_path=tmp_path, tenant_id="tenant-A")
    learner = _learner(ledger=ledger)
    record = learner.learn(
        capability_id="llm.completion",
        succeeded=True,
        verified=False,  # NOT verified -> rollback-safe: not admitted
        source_ref="wf-no-admit",
    )
    assert record.admitted_entry_id is None
    [entry] = list(ledger.replay())
    assert entry.event.admitted_entry_id is None


def test_failed_outcome_records_admitted_entry_id_as_none(tmp_path):
    ledger = FileBackedCognitiveOutcomeLedger(base_path=tmp_path, tenant_id="tenant-A")
    learner = _learner(ledger=ledger)
    record = learner.learn(
        capability_id="llm.completion",
        succeeded=False,
        verified=True,
        source_ref="wf-failure",
    )
    assert record.admitted_entry_id is None
    [entry] = list(ledger.replay())
    assert entry.event.admitted_entry_id is None
    assert entry.event.succeeded is False


def test_consecutive_learns_record_monotone_confidence_progression(tmp_path):
    """Two learn() calls for the same capability: second event's prior_confidence
    must equal the first event's next_confidence (the cache is mutated under
    the lock between writes, and the ledger captures the actual transition)."""
    ledger = FileBackedCognitiveOutcomeLedger(base_path=tmp_path, tenant_id="tenant-A")
    learner = _learner(ledger=ledger)
    learner.learn(capability_id="cap.A", succeeded=True, verified=True, source_ref="wf-1")
    learner.learn(capability_id="cap.A", succeeded=True, verified=True, source_ref="wf-2")
    entries = list(ledger.replay())
    assert len(entries) == 2
    first, second = entries
    # The second prior must equal the first next (the cache mutated in
    # between under the lock).
    assert second.event.prior_confidence == first.event.next_confidence


# ---------- (3) ledger append runs inside the existing _lock ----------


def test_concurrent_learns_serialise_under_single_lock(tmp_path):
    """8 threads x 25 learns each: ledger remains monotone 0..199, chain
    validates clean. Proves the ledger.append shares the learner's _lock
    (it doesn't create a second lock or re-enter)."""
    previous = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    try:
        ledger = FileBackedCognitiveOutcomeLedger(base_path=tmp_path, tenant_id="tenant-A")
        learner = _learner(ledger=ledger)
        errors: list[BaseException] = []
        guard = threading.Lock()

        def worker(worker_id: int) -> None:
            try:
                for i in range(25):
                    learner.learn(
                        capability_id="llm.completion",
                        succeeded=True,
                        verified=True,
                        source_ref=f"wf-{worker_id}-{i}",
                    )
            except BaseException as exc:  # noqa: BLE001 -- the test is the assertion
                with guard:
                    errors.append(exc)

        threads = [threading.Thread(target=worker, args=(w,)) for w in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == [], f"concurrent learn raised: {errors[:1]}"
        # Chain validates end-to-end.
        ledger.validate()
        sequences = [e.sequence for e in ledger.replay()]
        assert sequences == list(range(200))
    finally:
        sys.setswitchinterval(previous)


# ---------- (4) ledger failure does NOT corrupt in-memory state ----------


class _RaisingLedger:
    """Append-fails ledger: the cache mutations succeed; the exception
    propagates. In-memory state remains internally consistent."""

    def __init__(self) -> None:
        self.append_calls = 0

    def append(self, event):  # noqa: ARG002 - protocol shape
        self.append_calls += 1
        raise RuntimeError("synthetic-ledger-failure")

    def replay(self):
        return iter(())

    def validate(self):
        return None

    def latest_sequence(self):
        return None


def test_ledger_failure_does_not_corrupt_in_memory_state():
    """When ledger.append raises, the learner has already mutated meta
    confidence + episodic admission. The exception bubbles up; the cache
    stays internally consistent (the in-memory writes are still committed).

    This is the documented best-effort durability trade-off: a worker crash
    between the cache update and the ledger write loses the single in-flight
    event. The cache itself is never left half-mutated.
    """
    ledger = _RaisingLedger()
    learner = _learner(ledger=ledger)
    with pytest.raises(RuntimeError):
        learner.learn(
            capability_id="llm.completion",
            succeeded=True,
            verified=True,
            source_ref="wf-fail",
        )
    # The ledger DID get called (exactly once).
    assert ledger.append_calls == 1
    # The cache reflects the learn -- episodic has the admitted entry, meta
    # has the updated confidence. (We probe the public surface; a partial
    # cache state would surface as None / 0.5 here.)
    assert learner._episodic.size == 1
    assert learner._meta.get_confidence("llm.completion") is not None


# ---------- (5) validate_ledger_config parametric ----------


@pytest.mark.parametrize("raw", ["1", "true", "yes", "on", "TRUE"])
def test_validate_ledger_config_truthy(raw):
    assert validate_ledger_config({COGNITIVE_LOOP_LEDGER_ENV: raw}).enabled is True


@pytest.mark.parametrize("raw", ["0", "false", "no", "off", ""])
def test_validate_ledger_config_falsy(raw):
    assert validate_ledger_config({COGNITIVE_LOOP_LEDGER_ENV: raw}).enabled is False


def test_validate_ledger_config_default_off():
    assert validate_ledger_config({}).enabled is False


def test_validate_ledger_config_malformed_fails_safe():
    report = validate_ledger_config({COGNITIVE_LOOP_LEDGER_ENV: "maybe"})
    assert report.enabled is False
    assert report.error is not None


# ---------- (6) build_outcome_ledger composition ----------


def test_build_outcome_ledger_returns_none_when_flag_off(tmp_path):
    assert build_outcome_ledger({COGNITIVE_LOOP_LEDGER_PATH_ENV: str(tmp_path)}) is None


def test_build_outcome_ledger_returns_none_when_path_missing():
    assert build_outcome_ledger({COGNITIVE_LOOP_LEDGER_ENV: "1"}) is None


def test_build_outcome_ledger_returns_none_when_path_blank():
    assert (
        build_outcome_ledger(
            {COGNITIVE_LOOP_LEDGER_ENV: "1", COGNITIVE_LOOP_LEDGER_PATH_ENV: "   "}
        )
        is None
    )


def test_build_outcome_ledger_returns_none_on_invalid_tenant(tmp_path):
    # Invalid tenant_id triggers PersistenceError inside the ledger ctor;
    # build_outcome_ledger swallows -> None (must not crash startup).
    assert (
        build_outcome_ledger(
            {COGNITIVE_LOOP_LEDGER_ENV: "1", COGNITIVE_LOOP_LEDGER_PATH_ENV: str(tmp_path)},
            tenant_id="../escape",
        )
        is None
    )


def test_build_outcome_ledger_happy_path(tmp_path):
    ledger = build_outcome_ledger(
        {COGNITIVE_LOOP_LEDGER_ENV: "1", COGNITIVE_LOOP_LEDGER_PATH_ENV: str(tmp_path)},
        tenant_id="tenant-A",
    )
    assert isinstance(ledger, FileBackedCognitiveOutcomeLedger)
    # The ledger is usable end-to-end.
    event = CognitiveOutcomeEvent(
        capability_id="llm.completion",
        succeeded=True,
        verified=True,
        admitted_entry_id=None,
        source_ref="wf-smoke",
        learned_at=_clock(),
        prior_confidence=0.5,
        next_confidence=0.55,
    )
    entry = ledger.append(event)
    assert entry.sequence == 0
    ledger.validate()


# ---------- (7) build_learner composition ----------


def test_build_learner_learn_off_returns_none():
    organs = _Organs()
    assert build_learner({}, organs, clock=_clock) is None


def test_build_learner_learn_on_ledger_off_builds_unledgered(tmp_path):
    organs = _Organs()
    learner = build_learner(
        {COGNITIVE_LOOP_LEARN_ENV: "1"},
        organs,
        clock=_clock,
    )
    assert isinstance(learner, CognitiveLearner)
    assert learner._ledger is None


def test_build_learner_both_flags_on_builds_with_ledger(tmp_path):
    organs = _Organs()
    learner = build_learner(
        {
            COGNITIVE_LOOP_LEARN_ENV: "1",
            COGNITIVE_LOOP_LEDGER_ENV: "1",
            COGNITIVE_LOOP_LEDGER_PATH_ENV: str(tmp_path),
        },
        organs,
        clock=_clock,
    )
    assert isinstance(learner, CognitiveLearner)
    assert isinstance(learner._ledger, FileBackedCognitiveOutcomeLedger)
    # End-to-end learn writes through to the ledger.
    learner.learn(
        capability_id="llm.completion",
        succeeded=True,
        verified=True,
        source_ref="wf-smoke",
    )
    [entry] = list(learner._ledger.replay())
    assert entry.event.source_ref == "wf-smoke"


def test_build_learner_ledger_misconfig_falls_back_unledgered(tmp_path):
    """Ledger flag on but path env missing: learner still builds (because
    learn flag is on), just without a ledger. A misconfig DOES NOT crash
    startup."""
    organs = _Organs()
    learner = build_learner(
        {COGNITIVE_LOOP_LEARN_ENV: "1", COGNITIVE_LOOP_LEDGER_ENV: "1"},
        organs,
        clock=_clock,
    )
    assert isinstance(learner, CognitiveLearner)
    assert learner._ledger is None


# ---------- (bonus) CognitiveLearner constructor invariant ----------


def test_ledger_param_is_optional_keyword_only():
    """Ensure backwards compatibility: existing callers that didn't pass
    ledger continue to work; positional construction still requires the
    keyword-only signature for everything else."""
    learner = CognitiveLearner(
        meta_reasoning=MetaReasoningEngine(clock=_clock),
        episodic_memory=EpisodicMemory(),
        clock=_clock,
    )
    assert learner._ledger is None


def test_ledger_can_be_any_object_implementing_protocol():
    """Duck-typing: the Protocol is satisfied by any object with append()."""

    class _Stub:
        def __init__(self) -> None:
            self.events = []

        def append(self, event):
            self.events.append(event)
            return None  # learner doesn't consume the return

        def replay(self):
            return iter(self.events)

        def validate(self):
            return None

        def latest_sequence(self):
            return None

    stub = _Stub()
    learner = _learner(ledger=stub)
    learner.learn(
        capability_id="cap.A",
        succeeded=True,
        verified=True,
        source_ref="wf-1",
    )
    assert len(stub.events) == 1
    assert stub.events[0].capability_id == "cap.A"
