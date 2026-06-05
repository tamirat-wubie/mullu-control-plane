"""Purpose: persistent storage for deterministic replay reports.
Governance scope: replay determinism report append/query persistence only.
Dependencies: replay determinism contracts and persistence errors.
Invariants:
  - Duplicate replay ids are idempotent when payloads match.
  - File persistence writes deterministic JSON atomically.
  - Load fails closed on malformed or tampered report payloads.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from mcoi_runtime.core.replay_determinism_harness import (
    ReplayDeterminismReport,
    ReplayFrameCheck,
)

from ._serialization import loads_strict_json
from .errors import CorruptedDataError, PersistenceError, PersistenceWriteError


_REPLAY_REASON_CODES = frozenset({
    "replay_match",
    "empty_trace",
    "frame_sequence_gap",
    "unknown_operation",
    "output_hash_mismatch",
    "operation_error",
})


def _bounded_store_error(summary: str, exc: BaseException) -> str:
    return f"{summary} ({type(exc).__name__})"


def _deterministic_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False)


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
        try:
            os.write(fd, content.encode("utf-8"))
            os.close(fd)
            fd = -1
            os.replace(tmp_path, str(path))
        except BaseException:
            if fd >= 0:
                os.close(fd)
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise
    except OSError as exc:
        raise PersistenceWriteError(
            _bounded_store_error("replay report store write failed", exc),
        ) from exc


def _require_dict_list(raw: dict[str, Any], field_name: str) -> list[dict[str, Any]]:
    value = raw.get(field_name, [])
    if not isinstance(value, list):
        raise CorruptedDataError(f"replay report {field_name} must be a JSON array")
    if not all(isinstance(item, dict) for item in value):
        raise CorruptedDataError(f"replay report {field_name} entries must be JSON objects")
    return value


def _frame_check_from_json(raw: dict[str, Any]) -> ReplayFrameCheck:
    try:
        reason_code = raw.get("reason_code", "replay_match")
        if reason_code not in _REPLAY_REASON_CODES:
            raise ValueError("unknown replay reason code")
        return ReplayFrameCheck(
            frame_id=raw["frame_id"],
            sequence=int(raw["sequence"]),
            operation=raw["operation"],
            matched=bool(raw["matched"]),
            expected_hash=raw["expected_hash"],
            actual_hash=raw.get("actual_hash", ""),
            reason_code=reason_code,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise CorruptedDataError(
            _bounded_store_error("invalid replay frame check", exc),
        ) from exc


def _report_from_json(raw: dict[str, Any]) -> ReplayDeterminismReport:
    if not isinstance(raw, dict):
        raise CorruptedDataError("replay report payload must be an object")
    try:
        reason_codes = raw.get("reason_codes", [])
        if not isinstance(reason_codes, list):
            raise ValueError("reason_codes must be a list")
        if any(reason_code not in _REPLAY_REASON_CODES for reason_code in reason_codes):
            raise ValueError("unknown replay reason code")
        metadata = raw.get("metadata", {})
        if not isinstance(metadata, dict):
            raise ValueError("metadata must be an object")
        report = ReplayDeterminismReport(
            replay_id=raw["replay_id"],
            trace_id=raw["trace_id"],
            trace_hash=raw["trace_hash"],
            deterministic=bool(raw["deterministic"]),
            checked_frames=int(raw["checked_frames"]),
            matched_frames=int(raw["matched_frames"]),
            mismatched_frames=int(raw["mismatched_frames"]),
            reason_codes=tuple(reason_codes),
            frame_checks=tuple(
                _frame_check_from_json(item)
                for item in _require_dict_list(raw, "frame_checks")
            ),
            metadata=metadata,
        )
    except CorruptedDataError:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        raise CorruptedDataError(
            _bounded_store_error("invalid replay report payload", exc),
        ) from exc
    if raw.get("report_hash") != report.report_hash:
        raise CorruptedDataError("replay report hash mismatch")
    return report


class ReplayReportStore:
    """In-memory append/query store for ReplayDeterminismReport records."""

    def __init__(self) -> None:
        self._reports: list[ReplayDeterminismReport] = []
        self._by_id: dict[str, ReplayDeterminismReport] = {}

    def append(self, report: ReplayDeterminismReport) -> ReplayDeterminismReport:
        if not isinstance(report, ReplayDeterminismReport):
            raise PersistenceError("report must be a ReplayDeterminismReport")
        existing = self._by_id.get(report.replay_id)
        if existing is not None:
            if existing.to_dict() != report.to_dict():
                raise PersistenceError("replay report id collision")
            return existing
        self._reports.append(report)
        self._by_id[report.replay_id] = report
        return report

    def get(self, replay_id: str) -> ReplayDeterminismReport | None:
        if not isinstance(replay_id, str) or not replay_id.strip():
            raise PersistenceError("replay_id must be a non-empty string")
        return self._by_id.get(replay_id)

    def list_reports(self, *, limit: int | None = None) -> tuple[ReplayDeterminismReport, ...]:
        if limit is not None and (not isinstance(limit, int) or limit < 1):
            raise PersistenceError("limit must be a positive integer")
        if limit is None:
            return tuple(self._reports)
        return tuple(self._reports[-limit:])


class FileReplayReportStore(ReplayReportStore):
    """JSON-file backed replay report store.

    The file stores one deterministic JSON object with an ordered ``reports``
    list. The whole file is rewritten atomically on append to keep the operator
    history inspectable and tamper-evident through deterministic report hashes.
    """

    def __init__(self, path: Path) -> None:
        if not isinstance(path, Path):
            raise PersistenceError("path must be a Path instance")
        self._path = path
        super().__init__()
        self._load_if_present()

    def append(self, report: ReplayDeterminismReport) -> ReplayDeterminismReport:
        appended = super().append(report)
        self._persist()
        return appended

    def _persist(self) -> None:
        payload = {
            "reports": [
                report.to_dict()
                for report in self._reports
            ],
        }
        _atomic_write(self._path, _deterministic_json(payload))

    def _load_if_present(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = loads_strict_json(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, ValueError) as exc:
            raise CorruptedDataError(
                _bounded_store_error("malformed replay report store file", exc),
            ) from exc
        if not isinstance(raw, dict):
            raise CorruptedDataError("replay report store payload must be an object")
        reports_raw = raw.get("reports")
        if not isinstance(reports_raw, list):
            raise CorruptedDataError("replay report store entries must be a list")
        for item in reports_raw:
            super().append(_report_from_json(item))
