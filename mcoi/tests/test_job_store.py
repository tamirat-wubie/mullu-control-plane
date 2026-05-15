"""Purpose: verify deterministic persistence for governed job runtime carriers.
Governance scope: job descriptor/state persistence tests only.
Dependencies: job engine, job store, and job contracts.
Invariants:
  - save/load preserves descriptor and state identifiers exactly.
  - malformed persisted payloads fail closed before restore.
  - restore never overwrites existing job carriers silently.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcoi_runtime.contracts.job import JobPriority, JobStatus
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.jobs import JobEngine
from mcoi_runtime.persistence.errors import CorruptedDataError
from mcoi_runtime.persistence.job_store import JobStore


def _seed_job_engine() -> JobEngine:
    engine = JobEngine(
        clock=iter(
            (
                "2026-03-18T12:00:00+00:00",
                "2026-03-18T12:00:00+00:00",
                "2026-03-18T12:00:01+00:00",
                "2026-03-18T12:00:02+00:00",
                "2026-03-18T12:00:02+00:00",
                "2026-03-18T12:00:03+00:00",
            )
        ).__next__
    )
    first, _first_state = engine.create_job(
        "Job One",
        "Persisted job one",
        JobPriority.HIGH,
    )
    second, _second_state = engine.create_job(
        "Job Two",
        "Persisted job two",
        JobPriority.NORMAL,
    )
    engine.start_job(first.job_id)
    return engine


def test_job_store_round_trip_preserves_descriptor_and_state_pairs(tmp_path: Path) -> None:
    store = JobStore(tmp_path / "jobs")
    engine = _seed_job_engine()

    content = store.save_state(engine)
    restored = store.load_state()

    assert "\"descriptors\"" in content
    assert tuple(descriptor.name for descriptor in restored.descriptors) == (
        "Job One",
        "Job Two",
    )
    assert tuple(state.status for state in restored.states) == (
        JobStatus.IN_PROGRESS,
        JobStatus.CREATED,
    )


def test_job_store_fails_closed_on_mismatched_descriptor_and_state_sets(tmp_path: Path) -> None:
    store = JobStore(tmp_path / "jobs")
    payload_path = tmp_path / "jobs" / "job_runtime.json"
    payload_path.parent.mkdir(parents=True, exist_ok=True)
    payload_path.write_text(
        json.dumps(
            {
                "descriptors": [
                    {
                        "job_id": "job-1",
                        "name": "Job One",
                        "description": "Persisted job one",
                        "priority": "high",
                        "created_at": "2026-03-18T12:00:00+00:00",
                        "metadata": {},
                    }
                ],
                "states": [],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    with pytest.raises(CorruptedDataError, match="must cover the same job_ids"):
        store.load_state()

    assert store.exists() is True
    assert payload_path.exists() is True


def test_job_store_rejects_non_standard_json_constants(tmp_path: Path) -> None:
    store = JobStore(tmp_path / "jobs")
    payload_path = tmp_path / "jobs" / "job_runtime.json"
    payload_path.parent.mkdir(parents=True, exist_ok=True)
    payload_path.write_text(
        '{"descriptors":[],"states":[],"secret_metric":NaN}',
        encoding="utf-8",
    )

    with pytest.raises(CorruptedDataError, match=r"^malformed job runtime file \(ValueError\)$") as excinfo:
        store.load_state()

    message = str(excinfo.value)
    assert "secret_metric" not in message
    assert "NaN" not in message


def test_job_store_missing_file_error_is_bounded(tmp_path: Path) -> None:
    store = JobStore(tmp_path / "jobs")

    with pytest.raises(CorruptedDataError, match=r"^job runtime file not found$") as excinfo:
        store.load_state()

    assert str(tmp_path) not in str(excinfo.value)


def test_job_store_read_error_is_bounded(tmp_path: Path, monkeypatch) -> None:
    store = JobStore(tmp_path / "jobs")
    payload_path = tmp_path / "jobs" / "job_runtime.json"
    payload_path.parent.mkdir(parents=True, exist_ok=True)
    payload_path.write_text("{}", encoding="utf-8")

    def _raise_os_error(*_args, **_kwargs):
        raise OSError("secret path detail")

    monkeypatch.setattr(Path, "read_text", _raise_os_error)

    with pytest.raises(CorruptedDataError, match=r"^malformed job runtime file \(OSError\)$") as excinfo:
        store.load_state()

    assert "secret path detail" not in str(excinfo.value)
    assert str(payload_path) not in str(excinfo.value)


def test_job_store_restore_fails_closed_when_job_already_exists(tmp_path: Path) -> None:
    store = JobStore(tmp_path / "jobs")
    source_engine = _seed_job_engine()
    store.save_state(source_engine)

    target_engine = _seed_job_engine()
    with pytest.raises(RuntimeCoreInvariantError, match="job already restored"):
        store.restore_state(target_engine)

    assert len(target_engine.list_job_descriptors()) == 2
    assert target_engine.get_job_state(target_engine.list_job_descriptors()[0].job_id) is not None
    assert target_engine.list_job_states()[0].status is JobStatus.IN_PROGRESS
