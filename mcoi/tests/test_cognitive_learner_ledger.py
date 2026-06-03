"""Stage C + D1 -- CognitiveLearner wired to the cognitive outcome ledger.

Covers the integration slice on top of the D1 substrate:
  1. Default-OFF byte-identical behaviour.
  2. Flag-ON ledger events with explicit tenant_id and confidence transition.
  3. Concurrent learn() serialisation through the existing learner lock.
  4. Ledger append failure prevents partial in-memory promotion.
  5. Env/config composition stays fail-safe.
"""

from __future__ import annotations

import sys
import threading
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
    tenant_id: str = "tenant-A",
) -> CognitiveLearner:
    return CognitiveLearner(
        meta_reasoning=MetaReasoningEngine(clock=clock),
        episodic_memory=EpisodicMemory(),
        clock=clock,
        ledger=ledger,
        tenant_id=tenant_id,
    )


class _Organs:
    def __init__(self, *, clock: Callable[[], str] = _clock) -> None:
        self.meta_reasoning = MetaReasoningEngine(clock=clock)
        self.episodic_memory = EpisodicMemory()


# ---------- default-OFF byte-identical ----------


def test_learn_without_ledger_is_byte_identical_to_pre_d1():
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
    assert record.admitted_entry_id is not None
    assert record.learned_at == _clock()
    assert learner._ledger is None


# ---------- flag-ON: each learn() appends one tenant-scoped ledger event ----------


def test_learn_with_ledger_appends_one_event_per_call(tmp_path):
    ledger = FileBackedCognitiveOutcomeLedger(base_path=tmp_path, tenant_id="tenant-A")
    learner = _learner(ledger=ledger)
    learner.learn(capability_id="llm.completion", succeeded=True, verified=True, source_ref="wf-001")
    learner.learn(capability_id="llm.completion", succeeded=False, verified=True, source_ref="wf-002")
    learner.learn(capability_id="search.web", succeeded=True, verified=True, source_ref="wf-003")
    entries = list(ledger.replay())
    assert len(entries) == 3
    assert [e.sequence for e in entries] == [0, 1, 2]
    assert {e.event.tenant_id for e in entries} == {"tenant-A"}


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
    assert event.tenant_id == "tenant-A"
    assert event.capability_id == "llm.completion"
    assert event.succeeded is True
    assert event.verified is True
    assert event.source_ref == "wf-xyz"
    assert event.learned_at == _clock()
    assert event.admitted_entry_id == record.admitted_entry_id
    assert event.prior_confidence == 0.5
    assert 0.0 <= event.next_confidence <= 1.0
    assert event.next_confidence != 0.5


@pytest.mark.parametrize(
    ("succeeded", "verified"),
    [(True, False), (False, True), (False, False)],
)
def test_non_verified_success_records_admitted_entry_id_as_none(tmp_path, succeeded, verified):
    ledger = FileBackedCognitiveOutcomeLedger(base_path=tmp_path, tenant_id="tenant-A")
    learner = _learner(ledger=ledger)
    record = learner.learn(
        capability_id="llm.completion",
        succeeded=succeeded,
        verified=verified,
        source_ref=f"wf-{succeeded}-{verified}",
    )
    assert record.admitted_entry_id is None
    [entry] = list(ledger.replay())
    assert entry.event.admitted_entry_id is None


def test_consecutive_learns_record_confidence_progression(tmp_path):
    ledger = FileBackedCognitiveOutcomeLedger(base_path=tmp_path, tenant_id="tenant-A")
    learner = _learner(ledger=ledger)
    learner.learn(capability_id="cap.A", succeeded=True, verified=True, source_ref="wf-1")
    learner.learn(capability_id="cap.A", succeeded=True, verified=True, source_ref="wf-2")
    first, second = list(ledger.replay())
    assert second.event.prior_confidence == first.event.next_confidence


# ---------- lock / concurrency ----------


def test_concurrent_learns_serialise_under_single_lock(tmp_path):
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
            except BaseException as exc:  # noqa: BLE001 -- test assertion
                with guard:
                    errors.append(exc)

        threads = [threading.Thread(target=worker, args=(w,)) for w in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert errors == [], f"concurrent learn raised: {errors[:1]}"
        ledger.validate()
        assert [e.sequence for e in ledger.replay()] == list(range(200))
    finally:
        sys.setswitchinterval(previous)


# ---------- ledger failure prevents partial promotion ----------


class _RaisingLedger:
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


def test_ledger_failure_aborts_before_in_memory_promotion():
    ledger = _RaisingLedger()
    learner = _learner(ledger=ledger)
    with pytest.raises(RuntimeError):
        learner.learn(
            capability_id="llm.completion",
            succeeded=True,
            verified=True,
            source_ref="wf-fail",
        )
    assert ledger.append_calls == 1
    assert learner._episodic.size == 0
    assert learner._meta.get_confidence("llm.completion") is None


# ---------- config validation ----------


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


# ---------- builder composition ----------


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
    event = CognitiveOutcomeEvent(
        tenant_id="tenant-A",
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


def test_build_learner_learn_off_returns_none():
    assert build_learner({}, _Organs(), clock=_clock) is None


def test_build_learner_learn_on_ledger_off_builds_unledgered():
    learner = build_learner({COGNITIVE_LOOP_LEARN_ENV: "1"}, _Organs(), clock=_clock)
    assert isinstance(learner, CognitiveLearner)
    assert learner._ledger is None


def test_build_learner_both_flags_on_builds_with_ledger(tmp_path):
    learner = build_learner(
        {
            COGNITIVE_LOOP_LEARN_ENV: "1",
            COGNITIVE_LOOP_LEDGER_ENV: "1",
            COGNITIVE_LOOP_LEDGER_PATH_ENV: str(tmp_path),
        },
        _Organs(),
        clock=_clock,
    )
    assert isinstance(learner, CognitiveLearner)
    assert isinstance(learner._ledger, FileBackedCognitiveOutcomeLedger)
    learner.learn(
        capability_id="llm.completion",
        succeeded=True,
        verified=True,
        source_ref="wf-smoke",
    )
    [entry] = list(learner._ledger.replay())
    assert entry.event.tenant_id == "system"
    assert entry.event.source_ref == "wf-smoke"


def test_build_learner_carries_tenant_id_into_event_body(tmp_path):
    learner = build_learner(
        {
            COGNITIVE_LOOP_LEARN_ENV: "1",
            COGNITIVE_LOOP_LEDGER_ENV: "1",
            COGNITIVE_LOOP_LEDGER_PATH_ENV: str(tmp_path),
        },
        _Organs(),
        clock=_clock,
        tenant_id="tenant-B",
    )
    assert isinstance(learner, CognitiveLearner)
    learner.learn(
        capability_id="llm.completion",
        succeeded=True,
        verified=True,
        source_ref="wf-tenant",
    )
    [entry] = list(learner._ledger.replay())
    assert entry.event.tenant_id == "tenant-B"


def test_build_learner_ledger_misconfig_falls_back_unledgered():
    learner = build_learner(
        {COGNITIVE_LOOP_LEARN_ENV: "1", COGNITIVE_LOOP_LEDGER_ENV: "1"},
        _Organs(),
        clock=_clock,
    )
    assert isinstance(learner, CognitiveLearner)
    assert learner._ledger is None


def test_ledger_param_is_optional_keyword_only():
    learner = CognitiveLearner(
        meta_reasoning=MetaReasoningEngine(clock=_clock),
        episodic_memory=EpisodicMemory(),
        clock=_clock,
    )
    assert learner._ledger is None
    assert learner._tenant_id == "system"


def test_ledger_can_be_any_object_implementing_protocol():
    class _Stub:
        def __init__(self) -> None:
            self.events = []

        def append(self, event):
            self.events.append(event)
            return None

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
    assert stub.events[0].tenant_id == "tenant-A"
    assert stub.events[0].capability_id == "cap.A"
