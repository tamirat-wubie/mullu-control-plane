"""Purpose: verify durable persistence for replay-admitted runbook entries.
Governance scope: procedural memory persistence only.
Dependencies: runbook core records and RunbookStore.
Invariants: runbooks round-trip, identical saves are idempotent, collisions and path traversal fail closed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mcoi_runtime.core.runbook import RunbookEntry, RunbookProvenance
from mcoi_runtime.persistence.errors import PathTraversalError, PersistenceWriteError
from mcoi_runtime.persistence.runbook_store import RunbookStore


def _entry(runbook_id: str = "rb-store-1") -> RunbookEntry:
    return RunbookEntry(
        runbook_id=runbook_id,
        name="Stored Runbook",
        description="Verified replay-backed runbook.",
        template={"action_type": "mil_audit_replay", "program_id": "mil:store"},
        bindings_schema={"tenant_id": "str"},
        provenance=RunbookProvenance(
            execution_id="exec-store-1",
            verification_id="verify-store-1",
            replay_id="replay-store-1",
            trace_id="trace-store-1",
            learning_admission_id="admission-store-1",
        ),
        preconditions=("replay_validated",),
        postconditions=("terminal_certificate_emitted",),
    )


def test_runbook_store_round_trips_entry(tmp_path: Path) -> None:
    store = RunbookStore(tmp_path)
    entry = _entry()

    written = store.save(entry)
    loaded = store.load(entry.runbook_id)

    assert written is True
    assert loaded == entry
    assert loaded.provenance.replay_id == "replay-store-1"
    assert store.list_runbook_ids() == ("rb-store-1",)


def test_runbook_store_identical_save_is_idempotent(tmp_path: Path) -> None:
    store = RunbookStore(tmp_path)
    entry = _entry()

    first = store.save(entry)
    second = store.save(entry)

    assert first is True
    assert second is False
    assert store.load_all() == (entry,)


def test_runbook_store_rejects_id_collision(tmp_path: Path) -> None:
    store = RunbookStore(tmp_path)
    original = _entry()
    changed = RunbookEntry(
        runbook_id=original.runbook_id,
        name="Changed Runbook",
        description=original.description,
        template=original.template,
        bindings_schema=original.bindings_schema,
        provenance=original.provenance,
    )

    store.save(original)
    with pytest.raises(PersistenceWriteError, match="runbook id collision"):
        store.save(changed)

    assert store.load(original.runbook_id) == original


def test_runbook_store_rejects_path_traversal(tmp_path: Path) -> None:
    store = RunbookStore(tmp_path)

    with pytest.raises(PathTraversalError):
        store.load("../escape")

    assert store.list_runbook_ids() == ()
