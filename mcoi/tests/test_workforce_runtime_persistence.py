"""Purpose: verify explicit persistence and restore for workforce assignment state.
Governance scope: worker, assignment-request, and assignment-decision persistence only.
Dependencies: workforce runtime, workforce store, persistence errors.
Invariants:
  - Workforce serialization is deterministic for the same input.
  - Restore preserves exact worker assignment load and queue carriers.
  - Malformed payloads fail closed.
  - Restore preconditions reject broken worker/request/decision relationships before mutation.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcoi_runtime.contracts.workforce_runtime import AssignmentDisposition
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.workforce_runtime import WorkforceRuntimeEngine
from mcoi_runtime.persistence.errors import CorruptedDataError
from mcoi_runtime.persistence.workforce_store import WorkforceStore


_TS_0 = "2026-05-01T12:00:00+00:00"
_TS_1 = "2026-05-01T12:00:01+00:00"


def _build_engine() -> WorkforceRuntimeEngine:
    engine = WorkforceRuntimeEngine(EventSpineEngine())
    engine.register_worker("worker-b", "tenant-1", "reviewer", "alpha", "Worker B", 3)
    engine.register_worker("worker-a", "tenant-1", "reviewer", "alpha", "Worker A", 3)
    engine.request_assignment("request-b", "tenant-1", "scope-b", "reviewer")
    engine.request_assignment("request-a", "tenant-1", "scope-a", "reviewer")
    engine.decide_assignment("decision-a", "request-a", "worker-a")
    engine.decide_assignment(
        "decision-b",
        "request-b",
        worker_id="escalation",
        disposition=AssignmentDisposition.ESCALATED,
    )
    return engine


def test_workforce_store_round_trip_preserves_live_assignment_state(tmp_path: Path) -> None:
    store = WorkforceStore(tmp_path / "workforce")
    source = _build_engine()

    saved = store.save_state(source)
    restored = WorkforceRuntimeEngine(EventSpineEngine())
    state = store.restore_state(restored)

    assert "\"decisions\"" in saved
    assert tuple(worker.worker_id for worker in state.workers) == ("worker-a", "worker-b")
    assert tuple(request.request_id for request in state.requests) == ("request-a", "request-b")
    assert tuple(decision.decision_id for decision in state.decisions) == ("decision-a", "decision-b")
    assert restored.worker_count == 2
    assert restored.request_count == 2
    assert restored.decision_count == 2
    assert restored.get_worker("worker-a").current_assignments == 1
    assert restored.get_worker("worker-b").current_assignments == 0
    assert restored.decisions_for_request("request-a")[0].worker_id == "worker-a"
    assert restored.decisions_for_request("request-b")[0].disposition is AssignmentDisposition.ESCALATED


def test_workforce_store_serialization_is_stable_for_same_input(tmp_path: Path) -> None:
    store = WorkforceStore(tmp_path / "workforce")
    engine = _build_engine()

    first = store.save_state(engine)
    second = store.save_state(engine)
    persisted = (tmp_path / "workforce" / "workforce_runtime.json").read_text(encoding="utf-8")

    assert first == second
    assert persisted == first
    assert store.exists() is True


def test_workforce_store_fails_closed_on_malformed_payload(tmp_path: Path) -> None:
    base_path = tmp_path / "workforce"
    base_path.mkdir(parents=True, exist_ok=True)
    payload_path = base_path / "workforce_runtime.json"
    payload_path.write_text(
        json.dumps({"workers": {}, "requests": [], "decisions": []}),
        encoding="utf-8",
    )
    store = WorkforceStore(base_path)

    assert payload_path.exists() is True
    with pytest.raises(CorruptedDataError, match="workers must be a JSON array"):
        store.load_state()


def test_workforce_store_missing_file_error_is_bounded(tmp_path: Path) -> None:
    store = WorkforceStore(tmp_path / "workforce")

    with pytest.raises(CorruptedDataError, match=r"^workforce runtime file not found$") as excinfo:
        store.load_state()

    assert str(tmp_path) not in str(excinfo.value)


def test_workforce_store_read_error_is_bounded(tmp_path: Path, monkeypatch) -> None:
    base_path = tmp_path / "workforce"
    base_path.mkdir(parents=True, exist_ok=True)
    payload_path = base_path / "workforce_runtime.json"
    payload_path.write_text("{}", encoding="utf-8")
    store = WorkforceStore(base_path)

    def _raise_os_error(*_args, **_kwargs):
        raise OSError("secret path detail")

    monkeypatch.setattr(Path, "read_text", _raise_os_error)

    with pytest.raises(CorruptedDataError, match=r"^malformed workforce runtime file \(OSError\)$") as excinfo:
        store.load_state()

    assert "secret path detail" not in str(excinfo.value)
    assert str(payload_path) not in str(excinfo.value)


def test_restore_state_fails_closed_when_assigned_worker_is_missing(tmp_path: Path) -> None:
    base_path = tmp_path / "workforce"
    base_path.mkdir(parents=True, exist_ok=True)
    payload_path = base_path / "workforce_runtime.json"
    payload_path.write_text(
        json.dumps(
            {
                "workers": [],
                "requests": [
                    {
                        "request_id": "request-1",
                        "tenant_id": "tenant-1",
                        "scope_ref_id": "scope-1",
                        "role_ref": "reviewer",
                        "priority": 1,
                        "source_type": "manual",
                        "requested_at": _TS_0,
                        "metadata": {},
                    }
                ],
                "decisions": [
                    {
                        "decision_id": "decision-1",
                        "request_id": "request-1",
                        "worker_id": "worker-missing",
                        "disposition": "assigned",
                        "reason": "assigned",
                        "decided_at": _TS_1,
                        "metadata": {},
                    }
                ],
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    store = WorkforceStore(base_path)
    engine = WorkforceRuntimeEngine(EventSpineEngine())

    with pytest.raises(RuntimeCoreInvariantError, match="unknown worker: worker-missing"):
        store.restore_state(engine)
    assert engine.worker_count == 0
    assert engine.request_count == 0
    assert engine.decision_count == 0


def test_restore_state_fails_closed_when_assignment_counts_do_not_match(tmp_path: Path) -> None:
    base_path = tmp_path / "workforce"
    base_path.mkdir(parents=True, exist_ok=True)
    payload_path = base_path / "workforce_runtime.json"
    payload_path.write_text(
        json.dumps(
            {
                "workers": [
                    {
                        "worker_id": "worker-1",
                        "tenant_id": "tenant-1",
                        "role_ref": "reviewer",
                        "team_ref": "alpha",
                        "display_name": "Worker One",
                        "status": "active",
                        "max_assignments": 3,
                        "current_assignments": 0,
                        "created_at": _TS_0,
                        "metadata": {},
                    }
                ],
                "requests": [
                    {
                        "request_id": "request-1",
                        "tenant_id": "tenant-1",
                        "scope_ref_id": "scope-1",
                        "role_ref": "reviewer",
                        "priority": 1,
                        "source_type": "manual",
                        "requested_at": _TS_0,
                        "metadata": {},
                    }
                ],
                "decisions": [
                    {
                        "decision_id": "decision-1",
                        "request_id": "request-1",
                        "worker_id": "worker-1",
                        "disposition": "assigned",
                        "reason": "assigned",
                        "decided_at": _TS_1,
                        "metadata": {},
                    }
                ],
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    store = WorkforceStore(base_path)
    engine = WorkforceRuntimeEngine(EventSpineEngine())

    with pytest.raises(
        RuntimeCoreInvariantError,
        match="current_assignments does not match persisted assigned decisions",
    ):
        store.restore_state(engine)
    assert engine.worker_count == 0
    assert engine.request_count == 0
    assert engine.decision_count == 0
