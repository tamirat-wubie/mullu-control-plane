"""Tests for skill durability: persistence, round-trip, linkage, and promotion.

Proves that skill execution records survive save/load cycles and
carry provenance through to runbook admission.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mcoi_runtime.contracts.skill import (
    DeterminismClass,
    EffectClass,
    SkillClass,
    SkillExecutionRecord,
    SkillLifecycle,
    SkillOutcome,
    SkillOutcomeStatus,
    SkillSelectionDecision,
    SkillStepOutcome,
    TrustClass,
    VerificationStrength,
)
from mcoi_runtime.persistence.skill_store import SkillStore
from mcoi_runtime.persistence.errors import CorruptedDataError, PersistenceError


# --- Helpers ---


def _make_step_outcome(step_id="s1", status=SkillOutcomeStatus.SUCCEEDED):
    return SkillStepOutcome(step_id=step_id, status=status, outputs={"result": "ok"})


def _make_outcome(skill_id="sk-1", status=SkillOutcomeStatus.SUCCEEDED, steps=()):
    return SkillOutcome(
        skill_id=skill_id,
        status=status,
        step_outcomes=steps or (_make_step_outcome(),),
    )


def _make_selection(skill_id="sk-1"):
    return SkillSelectionDecision(
        selected_skill_id=skill_id,
        candidates_considered=(skill_id, "sk-alt"),
        selection_reasons=("lifecycle:verified", "confidence:0.9000"),
        rejected_reasons={"sk-alt": "blocked"},
    )


def _make_record(record_id="rec-001", skill_id="sk-1", **kw):
    defaults = dict(
        record_id=record_id,
        skill_id=skill_id,
        outcome=_make_outcome(skill_id),
        selection=_make_selection(skill_id),
        started_at="2025-01-15T10:00:00+00:00",
        finished_at="2025-01-15T10:00:01+00:00",
    )
    defaults.update(kw)
    return SkillExecutionRecord(**defaults)


# --- SkillStore ---


class TestSkillStore:
    def test_save_and_load_round_trip(self, tmp_path: Path):
        store = SkillStore(tmp_path / "skills")
        record = _make_record()
        store.save(record)
        loaded = store.load("rec-001")

        assert loaded.record_id == record.record_id
        assert loaded.skill_id == record.skill_id
        assert loaded.outcome.status is SkillOutcomeStatus.SUCCEEDED
        assert loaded.outcome.skill_id == "sk-1"

    def test_step_outcomes_preserved(self, tmp_path: Path):
        store = SkillStore(tmp_path / "skills")
        steps = (
            _make_step_outcome("s1", SkillOutcomeStatus.SUCCEEDED),
            _make_step_outcome("s2", SkillOutcomeStatus.FAILED),
        )
        record = _make_record(outcome=_make_outcome(steps=steps))
        store.save(record)
        loaded = store.load("rec-001")

        assert len(loaded.outcome.step_outcomes) == 2
        assert loaded.outcome.step_outcomes[0].step_id == "s1"
        assert loaded.outcome.step_outcomes[0].status is SkillOutcomeStatus.SUCCEEDED
        assert loaded.outcome.step_outcomes[1].step_id == "s2"
        assert loaded.outcome.step_outcomes[1].status is SkillOutcomeStatus.FAILED

    def test_selection_preserved(self, tmp_path: Path):
        store = SkillStore(tmp_path / "skills")
        record = _make_record()
        store.save(record)
        loaded = store.load("rec-001")

        assert loaded.selection is not None
        assert loaded.selection.selected_skill_id == "sk-1"
        assert loaded.selection.rejected_reasons["sk-alt"] == "blocked"

    def test_selection_none_preserved(self, tmp_path: Path):
        store = SkillStore(tmp_path / "skills")
        record = _make_record(selection=None)
        store.save(record)
        loaded = store.load("rec-001")

        assert loaded.selection is None

    def test_timestamps_preserved(self, tmp_path: Path):
        store = SkillStore(tmp_path / "skills")
        record = _make_record()
        store.save(record)
        loaded = store.load("rec-001")

        assert loaded.started_at == "2025-01-15T10:00:00+00:00"
        assert loaded.finished_at == "2025-01-15T10:00:01+00:00"

    def test_provenance_ids_preserved(self, tmp_path: Path):
        store = SkillStore(tmp_path / "skills")
        record = _make_record(
            trace_id="trace-001",
            replay_id="replay-001",
            runbook_id="rb-001",
        )
        store.save(record)
        loaded = store.load("rec-001")

        assert loaded.trace_id == "trace-001"
        assert loaded.replay_id == "replay-001"
        assert loaded.runbook_id == "rb-001"

    def test_provenance_ids_none_preserved(self, tmp_path: Path):
        store = SkillStore(tmp_path / "skills")
        record = _make_record()
        store.save(record)
        loaded = store.load("rec-001")

        assert loaded.trace_id is None
        assert loaded.replay_id is None
        assert loaded.runbook_id is None

    def test_list_records(self, tmp_path: Path):
        store = SkillStore(tmp_path / "skills")
        store.save(_make_record("rec-b"))
        store.save(_make_record("rec-a"))
        store.save(_make_record("rec-c"))

        ids = store.list_records()
        assert ids == ("rec-a", "rec-b", "rec-c")

    def test_list_records_empty(self, tmp_path: Path):
        store = SkillStore(tmp_path / "skills")
        assert store.list_records() == ()

    def test_load_all(self, tmp_path: Path):
        store = SkillStore(tmp_path / "skills")
        store.save(_make_record("rec-b"))
        store.save(_make_record("rec-a"))

        records = store.load_all()
        assert len(records) == 2
        assert records[0].record_id == "rec-a"
        assert records[1].record_id == "rec-b"

    def test_load_nonexistent_raises(self, tmp_path: Path):
        store = SkillStore(tmp_path / "skills")
        with pytest.raises(PersistenceError, match="not found"):
            store.load("missing")

    def test_malformed_file_fails_closed(self, tmp_path: Path):
        store = SkillStore(tmp_path / "skills")
        (tmp_path / "skills").mkdir(parents=True, exist_ok=True)
        (tmp_path / "skills" / "bad.json").write_text("not json!!")
        with pytest.raises(CorruptedDataError, match=r"^malformed JSON \(JSONDecodeError\)$"):
            store.load("bad")

    def test_invalid_type_rejected(self, tmp_path: Path):
        store = SkillStore(tmp_path / "skills")
        with pytest.raises(PersistenceError, match="SkillExecutionRecord"):
            store.save("not a record")

    def test_overwrite_same_id(self, tmp_path: Path):
        store = SkillStore(tmp_path / "skills")
        record1 = _make_record("rec-001", outcome=_make_outcome(status=SkillOutcomeStatus.SUCCEEDED))
        record2 = _make_record("rec-001", outcome=_make_outcome(status=SkillOutcomeStatus.FAILED))
        store.save(record1)
        store.save(record2)
        loaded = store.load("rec-001")
        assert loaded.outcome.status is SkillOutcomeStatus.FAILED


class TestSkillExecutionRecordLinkage:
    """Prove that linkage fields work correctly on the contract."""

    def test_record_with_all_linkage(self):
        record = _make_record(
            trace_id="t-1",
            replay_id="r-1",
            runbook_id="rb-1",
        )
        assert record.trace_id == "t-1"
        assert record.replay_id == "r-1"
        assert record.runbook_id == "rb-1"

    def test_record_without_linkage(self):
        record = _make_record()
        assert record.trace_id is None
        assert record.replay_id is None
        assert record.runbook_id is None

    def test_step_outputs_in_round_trip(self, tmp_path: Path):
        store = SkillStore(tmp_path / "skills")
        step = SkillStepOutcome(
            step_id="s1",
            status=SkillOutcomeStatus.SUCCEEDED,
            execution_id="exec-001",
            outputs={"path": "/tmp/out", "size": 42},
        )
        outcome = SkillOutcome(
            skill_id="sk-1",
            status=SkillOutcomeStatus.SUCCEEDED,
            step_outcomes=(step,),
        )
        record = _make_record(outcome=outcome)
        store.save(record)
        loaded = store.load("rec-001")

        loaded_step = loaded.outcome.step_outcomes[0]
        assert loaded_step.execution_id == "exec-001"
        assert loaded_step.outputs["path"] == "/tmp/out"
        assert loaded_step.outputs["size"] == 42
