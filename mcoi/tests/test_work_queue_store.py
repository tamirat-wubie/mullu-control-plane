"""Purpose: verify deterministic persistence for governed work-queue entry carriers.
Governance scope: persistence witness tests only.
Dependencies: work queue core, work queue store, and job contracts.
Invariants:
  - save/load preserves queue entry identifiers and dequeue order.
  - malformed persisted payloads fail closed before restore.
  - restore never overwrites existing queue entries silently.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcoi_runtime.contracts.job import JobDescriptor, JobPriority
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.jobs import WorkQueue
from mcoi_runtime.persistence.errors import CorruptedDataError
from mcoi_runtime.persistence.work_queue_store import WorkQueueStore


def _seed_queue() -> WorkQueue:
    queue = WorkQueue(
        clock=iter(
            (
                "2026-03-18T12:00:00+00:00",
                "2026-03-18T12:00:00+00:00",
                "2026-03-18T12:00:01+00:00",
                "2026-03-18T12:00:01+00:00",
                "2026-03-18T12:00:02+00:00",
                "2026-03-18T12:00:02+00:00",
            )
        ).__next__
    )
    queue.enqueue(
        JobDescriptor(
            job_id="job-low",
            name="Low job",
            description="Low priority queue item",
            priority=JobPriority.LOW,
            created_at="2026-03-18T12:00:00+00:00",
        )
    )
    queue.enqueue(
        JobDescriptor(
            job_id="job-high",
            name="High job",
            description="High priority queue item",
            priority=JobPriority.HIGH,
            created_at="2026-03-18T12:00:00+00:00",
        )
    )
    queue.enqueue(
        JobDescriptor(
            job_id="job-normal",
            name="Normal job",
            description="Normal priority queue item",
            priority=JobPriority.NORMAL,
            created_at="2026-03-18T12:00:00+00:00",
        )
    )
    return queue


def test_work_queue_store_round_trip_preserves_sorted_queue_order(tmp_path: Path) -> None:
    store = WorkQueueStore(tmp_path / "work-queue")
    queue = _seed_queue()

    content = store.save_state(queue)
    restored = store.load_state()

    assert "\"entries\"" in content
    assert tuple(entry.job_id for entry in restored.entries) == (
        "job-high",
        "job-normal",
        "job-low",
    )
    assert tuple(entry.priority.value for entry in restored.entries) == (
        "high",
        "normal",
        "low",
    )


def test_work_queue_store_fails_closed_on_malformed_payload(tmp_path: Path) -> None:
    store = WorkQueueStore(tmp_path / "work-queue")
    payload_path = tmp_path / "work-queue" / "work_queue.json"
    payload_path.parent.mkdir(parents=True, exist_ok=True)
    payload_path.write_text(
        json.dumps({"entries": [{"job_id": "missing-entry-id"}]}, sort_keys=True),
        encoding="utf-8",
    )

    with pytest.raises(CorruptedDataError, match="failed to construct WorkQueueEntry"):
        store.load_state()

    assert store.exists() is True
    assert payload_path.exists() is True


def test_work_queue_store_restore_fails_closed_when_entry_already_exists(tmp_path: Path) -> None:
    store = WorkQueueStore(tmp_path / "work-queue")
    source_queue = _seed_queue()
    store.save_state(source_queue)

    target_queue = _seed_queue()
    with pytest.raises(RuntimeCoreInvariantError, match="already restored"):
        store.restore_state(target_queue)

    assert len(target_queue.list_entries()) == 3
    assert target_queue.peek() is not None
    assert target_queue.peek().job_id == "job-high"
