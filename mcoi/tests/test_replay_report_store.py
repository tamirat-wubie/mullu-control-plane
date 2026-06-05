"""Purpose: verify replay report persistence contracts.
Governance scope: deterministic replay report history append/query/file load.
Dependencies: pytest, replay determinism report contracts, replay report store.
Invariants: duplicate ids are idempotent, collisions fail closed, and tampered
file payloads are rejected through deterministic report hashes.
"""

from __future__ import annotations

import json

import pytest

from mcoi_runtime.app.replay_report_integration import (
    select_replay_report_store,
    validate_replay_report_store_path,
)
from mcoi_runtime.core.replay_determinism_harness import (
    ReplayDeterminismReport,
    ReplayFrameCheck,
)
from mcoi_runtime.persistence.errors import CorruptedDataError, PersistenceError
from mcoi_runtime.persistence.replay_report_store import (
    FileReplayReportStore,
    ReplayReportStore,
)


def _report(replay_id: str, *, matched_frames: int = 1) -> ReplayDeterminismReport:
    frame = ReplayFrameCheck(
        frame_id=f"{replay_id}-frame-1",
        sequence=1,
        operation="echo",
        matched=matched_frames == 1,
        expected_hash="expected-hash",
        actual_hash="expected-hash" if matched_frames == 1 else "actual-hash",
        reason_code="replay_match" if matched_frames == 1 else "output_hash_mismatch",
    )
    return ReplayDeterminismReport(
        replay_id=replay_id,
        trace_id="trace-1",
        trace_hash="trace-hash",
        deterministic=matched_frames == 1,
        checked_frames=1,
        matched_frames=matched_frames,
        mismatched_frames=1 - matched_frames,
        reason_codes=() if matched_frames == 1 else ("output_hash_mismatch",),
        frame_checks=(frame,),
    )


def test_replay_report_store_appends_lists_and_gets_reports() -> None:
    store = ReplayReportStore()
    report = _report("replay-1")
    appended = store.append(report)
    duplicate = store.append(report)
    listed = store.list_reports()

    assert appended is report
    assert duplicate is report
    assert listed == (report,)
    assert store.get("replay-1") == report


def test_replay_report_store_rejects_id_collision() -> None:
    store = ReplayReportStore()
    store.append(_report("replay-1", matched_frames=1))

    with pytest.raises(PersistenceError):
        store.append(_report("replay-1", matched_frames=0))

    assert len(store.list_reports()) == 1
    assert store.get("replay-1") is not None
    assert store.list_reports()[0].deterministic is True


def test_file_replay_report_store_persists_and_reloads(tmp_path) -> None:
    path = tmp_path / "reports.json"
    report = _report("replay-1")
    store = FileReplayReportStore(path)
    store.append(report)

    reloaded = FileReplayReportStore(path)
    loaded = reloaded.get("replay-1")

    assert path.exists()
    assert loaded is not None
    assert loaded.report_hash == report.report_hash
    assert reloaded.list_reports()[0].frame_checks[0].operation == "echo"


def test_file_replay_report_store_rejects_tampered_hash(tmp_path) -> None:
    path = tmp_path / "reports.json"
    store = FileReplayReportStore(path)
    store.append(_report("replay-1"))
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["reports"][0]["trace_hash"] = "tampered"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(CorruptedDataError):
        FileReplayReportStore(path)

    assert payload["reports"][0]["trace_hash"] == "tampered"
    assert payload["reports"][0]["report_hash"].startswith("replay-report-")


def test_replay_report_store_path_validation_requires_absolute_json_path(tmp_path) -> None:
    valid_path = tmp_path / "reports.json"
    selected_path = validate_replay_report_store_path(valid_path)

    with pytest.raises(RuntimeError):
        validate_replay_report_store_path("relative.json")
    with pytest.raises(RuntimeError):
        validate_replay_report_store_path(tmp_path / "reports.txt")

    assert selected_path == valid_path
    assert selected_path.suffix == ".json"
    assert selected_path.parent == tmp_path


def test_replay_report_store_integration_selects_memory_or_file(tmp_path) -> None:
    file_path = tmp_path / "reports.json"
    memory_bootstrap = select_replay_report_store({})
    file_bootstrap = select_replay_report_store({
        "MULLU_REPLAY_REPORT_STORE_PATH": str(file_path),
    })

    assert isinstance(memory_bootstrap.store, ReplayReportStore)
    assert memory_bootstrap.persistent is False
    assert isinstance(file_bootstrap.store, FileReplayReportStore)
    assert file_bootstrap.persistent is True
    assert file_bootstrap.path == str(file_path)
