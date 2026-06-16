"""Purpose: persistent storage for operational mathematics loop receipts.
Governance scope: append/query/replay of JSON operational math receipts only.
Dependencies: persistence errors and strict JSON serialization helpers.
Invariants:
  - Receipt order is append-only.
  - Duplicate receipt ids are idempotent when payloads match.
  - File persistence writes deterministic JSON atomically.
  - Load fails closed on malformed receipt payloads.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from ._serialization import loads_strict_json
from .errors import CorruptedDataError, PersistenceError, PersistenceWriteError


OperationalMathReceipt = dict[str, Any]

_REQUIRED_FIELDS = (
    "receipt_id",
    "status",
    "solver_outcome",
    "target_id",
    "event_count",
    "iteration_count",
    "applied_principle_ids",
    "unresolved_principle_ids",
    "result",
)


def _bounded_store_error(summary: str, exc: BaseException) -> str:
    return f"{summary} ({type(exc).__name__})"


def _deterministic_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False)


def _json_clone(payload: Mapping[str, Any]) -> OperationalMathReceipt:
    try:
        return json.loads(_deterministic_json(payload))
    except (TypeError, ValueError) as exc:
        raise PersistenceError(
            _bounded_store_error("operational math receipt must be JSON-safe", exc),
        ) from exc


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
            _bounded_store_error("operational math receipt store write failed", exc),
        ) from exc


def _text_field(receipt: Mapping[str, Any], field_name: str) -> str:
    value = receipt.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise CorruptedDataError(f"operational math receipt {field_name} must be a non-empty string")
    return value


def _status_value(value: Any) -> str:
    if value not in {"passed", "failed"}:
        raise CorruptedDataError("operational math receipt status must be passed or failed")
    return str(value)


def _status_filter(value: str | None) -> str | None:
    if value is None:
        return None
    if value not in {"passed", "failed"}:
        raise PersistenceError("status must be passed or failed")
    return value


def _non_negative_int_field(receipt: Mapping[str, Any], field_name: str) -> int:
    value = receipt.get(field_name)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise CorruptedDataError(f"operational math receipt {field_name} must be a non-negative integer")
    return value


def _text_list_field(receipt: Mapping[str, Any], field_name: str) -> list[str]:
    value = receipt.get(field_name)
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise CorruptedDataError(f"operational math receipt {field_name} must be a list of non-empty strings")
    return list(value)


def _optional_result_text_list_field(result: Mapping[str, Any], field_name: str) -> list[str]:
    if field_name not in result:
        return []
    value = result.get(field_name)
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise CorruptedDataError(
            f"operational math receipt result.{field_name} must be a list of non-empty strings"
        )
    return list(value)


def _validated_receipt(raw_receipt: Mapping[str, Any]) -> OperationalMathReceipt:
    if not isinstance(raw_receipt, Mapping):
        raise CorruptedDataError("operational math receipt payload must be an object")
    for field_name in _REQUIRED_FIELDS:
        if field_name not in raw_receipt:
            raise CorruptedDataError(f"operational math receipt missing {field_name}")
    receipt = _json_clone(raw_receipt)
    _text_field(receipt, "receipt_id")
    _status_value(receipt.get("status"))
    _text_field(receipt, "solver_outcome")
    _text_field(receipt, "target_id")
    _non_negative_int_field(receipt, "event_count")
    _non_negative_int_field(receipt, "iteration_count")
    _text_list_field(receipt, "applied_principle_ids")
    _text_list_field(receipt, "unresolved_principle_ids")
    if not isinstance(receipt["result"], dict):
        raise CorruptedDataError("operational math receipt result must be an object")
    _optional_result_text_list_field(receipt["result"], "unverified_control_ids")
    return receipt


def _requires_review(receipt: Mapping[str, Any]) -> bool:
    return (
        receipt["status"] != "passed"
        or receipt["solver_outcome"] != "SolvedVerified"
        or bool(receipt["unresolved_principle_ids"])
        or bool(_unverified_control_ids(receipt))
    )


def _review_reason(receipt: Mapping[str, Any]) -> str:
    if receipt["status"] != "passed":
        return "operational_math_receipt_not_passed"
    if _unverified_control_ids(receipt):
        return "operational_math_unverified_controls"
    if receipt["solver_outcome"] != "SolvedVerified":
        return "operational_math_solver_not_verified"
    return "operational_math_unresolved_principles"


def _unverified_control_ids(receipt: Mapping[str, Any]) -> list[str]:
    result = receipt.get("result")
    if not isinstance(result, Mapping):
        return []
    value = result.get("unverified_control_ids")
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item.strip()]


class OperationalMathReceiptStore:
    """In-memory append/query store for operational math JSON receipts."""

    def __init__(self) -> None:
        self._receipts: list[OperationalMathReceipt] = []
        self._by_id: dict[str, OperationalMathReceipt] = {}

    def append(self, receipt: Mapping[str, Any]) -> OperationalMathReceipt:
        validated_receipt = _validated_receipt(receipt)
        receipt_id = validated_receipt["receipt_id"]
        existing = self._by_id.get(receipt_id)
        if existing is not None:
            if existing != validated_receipt:
                raise PersistenceError("operational math receipt id collision")
            return _json_clone(existing)
        self._receipts.append(validated_receipt)
        self._by_id[receipt_id] = validated_receipt
        return _json_clone(validated_receipt)

    def append_many(self, receipts: Iterable[Mapping[str, Any]]) -> tuple[OperationalMathReceipt, ...]:
        appended: list[OperationalMathReceipt] = []
        for receipt in receipts:
            appended.append(self.append(receipt))
        return tuple(appended)

    def get(self, receipt_id: str) -> OperationalMathReceipt | None:
        if not isinstance(receipt_id, str) or not receipt_id.strip():
            raise PersistenceError("receipt_id must be a non-empty string")
        receipt = self._by_id.get(receipt_id)
        return _json_clone(receipt) if receipt is not None else None

    def latest_receipt(self) -> OperationalMathReceipt | None:
        if not self._receipts:
            return None
        return _json_clone(self._receipts[-1])

    def list_receipts(
        self,
        *,
        target_id: str | None = None,
        status: str | None = None,
        limit: int | None = None,
    ) -> tuple[OperationalMathReceipt, ...]:
        if limit is not None and (not isinstance(limit, int) or isinstance(limit, bool) or limit < 1):
            raise PersistenceError("limit must be a positive integer")
        status_filter = _status_filter(status)
        matches = [
            receipt
            for receipt in self._receipts
            if (target_id is None or receipt["target_id"] == target_id)
            and (status_filter is None or receipt["status"] == status_filter)
        ]
        if limit is not None:
            matches = matches[-limit:]
        return tuple(_json_clone(receipt) for receipt in matches)

    def review_receipts(self, *, limit: int | None = 10) -> tuple[OperationalMathReceipt, ...]:
        if limit is not None and (not isinstance(limit, int) or isinstance(limit, bool) or limit < 1):
            raise PersistenceError("limit must be a positive integer")
        review_receipts = [
            receipt
            for receipt in self._receipts
            if _requires_review(receipt)
        ]
        if limit is not None:
            review_receipts = review_receipts[:limit]
        return tuple(_json_clone(receipt) for receipt in review_receipts)

    def summary(self) -> dict[str, Any]:
        """Return dashboard-ready receipt posture without mutating stored state."""

        by_status: dict[str, int] = {"passed": 0, "failed": 0}
        targets: set[str] = set()
        for receipt in self._receipts:
            by_status[receipt["status"]] = by_status.get(receipt["status"], 0) + 1
            targets.add(receipt["target_id"])
        review_receipts = self.review_receipts(limit=None)
        review_signals = [
            {
                "receipt_id": receipt["receipt_id"],
                "target_id": receipt["target_id"],
                "status": receipt["status"],
                "solver_outcome": receipt["solver_outcome"],
                "unresolved_principle_count": len(receipt["unresolved_principle_ids"]),
                "unverified_control_count": len(_unverified_control_ids(receipt)),
                "unverified_control_ids": _unverified_control_ids(receipt),
                "reason": _review_reason(receipt),
            }
            for receipt in review_receipts[:10]
        ]
        latest_receipt = self._receipts[-1] if self._receipts else None
        return {
            "source": "operational_math",
            "total_receipts": len(self._receipts),
            "target_count": len(targets),
            "passed_receipt_count": by_status.get("passed", 0),
            "failed_receipt_count": sum(
                count for status, count in by_status.items() if status != "passed"
            ),
            "requires_operator_review": bool(review_receipts),
            "review_signal_count": len(review_receipts),
            "review_signals": review_signals,
            "by_status": by_status,
            "latest_receipt_id": latest_receipt["receipt_id"] if latest_receipt else None,
            "latest_target_id": latest_receipt["target_id"] if latest_receipt else None,
            "latest_status": latest_receipt["status"] if latest_receipt else None,
            "latest_solver_outcome": latest_receipt["solver_outcome"] if latest_receipt else None,
            "latest_iteration_count": latest_receipt["iteration_count"] if latest_receipt else None,
            "latest_event_count": latest_receipt["event_count"] if latest_receipt else None,
            "governed": True,
        }


class FileOperationalMathReceiptStore(OperationalMathReceiptStore):
    """JSON-file backed operational math receipt store."""

    def __init__(self, path: Path) -> None:
        if not isinstance(path, Path):
            raise PersistenceError("path must be a Path instance")
        self._path = path
        super().__init__()
        self._load_if_present()

    def append(self, receipt: Mapping[str, Any]) -> OperationalMathReceipt:
        before_count = len(self._receipts)
        appended = super().append(receipt)
        if len(self._receipts) != before_count:
            self._persist()
        return appended

    def append_many(self, receipts: Iterable[Mapping[str, Any]]) -> tuple[OperationalMathReceipt, ...]:
        appended: list[OperationalMathReceipt] = []
        changed = False
        for receipt in receipts:
            before_count = len(self._receipts)
            appended.append(OperationalMathReceiptStore.append(self, receipt))
            changed = changed or len(self._receipts) != before_count
        if changed:
            self._persist()
        return tuple(appended)

    def _persist(self) -> None:
        payload = {"receipts": [_json_clone(receipt) for receipt in self._receipts]}
        _atomic_write(self._path, _deterministic_json(payload))

    def _load_if_present(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = loads_strict_json(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, ValueError) as exc:
            raise CorruptedDataError(
                _bounded_store_error("malformed operational math receipt store file", exc),
            ) from exc
        if not isinstance(raw, dict):
            raise CorruptedDataError("operational math receipt store payload must be an object")
        receipts_raw = raw.get("receipts")
        if not isinstance(receipts_raw, list):
            raise CorruptedDataError("operational math receipt store entries must be a list")
        for item in receipts_raw:
            OperationalMathReceiptStore.append(self, _validated_receipt(item))
