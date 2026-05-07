"""Purpose: persistent storage for software-change lifecycle receipts.
Governance scope: append/query/replay of SoftwareChangeReceipt records only.
Dependencies: software-dev loop contracts and persistence errors.
Invariants:
  - Receipt order is append-only within each request.
  - Duplicate receipt ids are idempotent when payloads match.
  - File persistence writes deterministic JSON atomically.
  - Load fails closed on malformed receipt payloads.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Iterable

from mcoi_runtime.contracts.software_dev_loop import (
    SoftwareChangeReceipt,
    SoftwareChangeReceiptStage,
)

from .errors import CorruptedDataError, PersistenceError, PersistenceWriteError


def _bounded_store_error(summary: str, exc: BaseException) -> str:
    return f"{summary} ({type(exc).__name__})"


def _deterministic_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


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
            _bounded_store_error("software receipt store write failed", exc),
        ) from exc


def _receipt_from_json(raw: dict[str, Any]) -> SoftwareChangeReceipt:
    if not isinstance(raw, dict):
        raise CorruptedDataError("software receipt payload must be an object")
    try:
        return SoftwareChangeReceipt(
            receipt_id=raw["receipt_id"],
            request_id=raw["request_id"],
            stage=SoftwareChangeReceiptStage(raw["stage"]),
            cause=raw["cause"],
            outcome=raw["outcome"],
            target_refs=tuple(raw["target_refs"]),
            constraint_refs=tuple(raw["constraint_refs"]),
            evidence_refs=tuple(raw["evidence_refs"]),
            created_at=raw["created_at"],
            metadata=raw.get("metadata", {}),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise CorruptedDataError(
            _bounded_store_error("invalid software receipt payload", exc),
        ) from exc


class SoftwareChangeReceiptStore:
    """In-memory append/query store for SoftwareChangeReceipt records."""

    def __init__(self) -> None:
        self._receipts: list[SoftwareChangeReceipt] = []
        self._by_id: dict[str, SoftwareChangeReceipt] = {}

    def append(self, receipt: SoftwareChangeReceipt) -> SoftwareChangeReceipt:
        if not isinstance(receipt, SoftwareChangeReceipt):
            raise PersistenceError("receipt must be a SoftwareChangeReceipt")
        existing = self._by_id.get(receipt.receipt_id)
        if existing is not None:
            if existing.to_json_dict() != receipt.to_json_dict():
                raise PersistenceError("receipt id collision")
            return existing
        self._receipts.append(receipt)
        self._by_id[receipt.receipt_id] = receipt
        return receipt

    def append_many(
        self,
        receipts: Iterable[SoftwareChangeReceipt],
    ) -> tuple[SoftwareChangeReceipt, ...]:
        appended: list[SoftwareChangeReceipt] = []
        for receipt in receipts:
            appended.append(self.append(receipt))
        return tuple(appended)

    def get(self, receipt_id: str) -> SoftwareChangeReceipt | None:
        return self._by_id.get(receipt_id)

    def list_receipts(
        self,
        *,
        request_id: str | None = None,
        stage: SoftwareChangeReceiptStage | str | None = None,
        limit: int | None = None,
    ) -> tuple[SoftwareChangeReceipt, ...]:
        if limit is not None and (not isinstance(limit, int) or limit < 1):
            raise PersistenceError("limit must be a positive integer")
        stage_filter = SoftwareChangeReceiptStage(stage) if stage is not None else None
        matches = [
            receipt for receipt in self._receipts
            if (request_id is None or receipt.request_id == request_id)
            and (stage_filter is None or receipt.stage is stage_filter)
        ]
        if limit is not None:
            matches = matches[-limit:]
        return tuple(matches)

    def replay_request(self, request_id: str) -> tuple[SoftwareChangeReceipt, ...]:
        receipts = self.list_receipts(request_id=request_id)
        if not receipts:
            raise PersistenceError("request receipts not found")
        if receipts[-1].stage is not SoftwareChangeReceiptStage.TERMINAL_CLOSED:
            raise PersistenceError("request receipt chain is not terminally closed")
        return receipts

    def review_receipts(self, *, limit: int | None = 10) -> tuple[SoftwareChangeReceipt, ...]:
        """Return latest receipts for non-terminal request chains."""
        if limit is not None and (not isinstance(limit, int) or limit < 1):
            raise PersistenceError("limit must be a positive integer")
        requests: dict[str, SoftwareChangeReceipt] = {}
        for receipt in self._receipts:
            requests[receipt.request_id] = receipt
        open_receipts = tuple(
            receipt
            for receipt in requests.values()
            if receipt.stage is not SoftwareChangeReceiptStage.TERMINAL_CLOSED
        )
        if limit is not None:
            return open_receipts[:limit]
        return open_receipts

    def summary(self) -> dict[str, Any]:
        """Return dashboard-ready receipt lifecycle counts without mutation."""
        by_stage = {
            stage.value: 0
            for stage in SoftwareChangeReceiptStage
        }
        latest_receipt = self._receipts[-1] if self._receipts else None
        requests: dict[str, SoftwareChangeReceipt] = {}
        for receipt in self._receipts:
            by_stage[receipt.stage.value] += 1
            requests[receipt.request_id] = receipt
        terminal_request_count = sum(
            1
            for receipt in requests.values()
            if receipt.stage is SoftwareChangeReceiptStage.TERMINAL_CLOSED
        )
        open_receipts = tuple(
            receipt
            for receipt in requests.values()
            if receipt.stage is not SoftwareChangeReceiptStage.TERMINAL_CLOSED
        )
        review_signals = [
            {
                "request_id": receipt.request_id,
                "latest_receipt_id": receipt.receipt_id,
                "latest_stage": receipt.stage.value,
                "latest_outcome": receipt.outcome,
                "reason": "software_change_receipt_chain_open",
            }
            for receipt in open_receipts[:10]
        ]
        return {
            "total_receipts": len(self._receipts),
            "request_count": len(requests),
            "terminal_request_count": terminal_request_count,
            "open_request_count": len(requests) - terminal_request_count,
            "requires_operator_review": bool(open_receipts),
            "review_signal_count": len(open_receipts),
            "review_signals": review_signals,
            "by_stage": by_stage,
            "latest_receipt_id": latest_receipt.receipt_id if latest_receipt else None,
            "latest_request_id": latest_receipt.request_id if latest_receipt else None,
            "latest_stage": latest_receipt.stage.value if latest_receipt else None,
            "governed": True,
        }


class FileSoftwareChangeReceiptStore(SoftwareChangeReceiptStore):
    """JSON-file backed receipt store.

    The file stores one deterministic JSON object with an ordered ``receipts``
    list. The whole file is rewritten atomically on append to keep the store
    simple, local, and easy to inspect.
    """

    def __init__(self, path: Path) -> None:
        if not isinstance(path, Path):
            raise PersistenceError("path must be a Path instance")
        self._path = path
        super().__init__()
        self._load_if_present()

    def append(self, receipt: SoftwareChangeReceipt) -> SoftwareChangeReceipt:
        appended = super().append(receipt)
        self._persist()
        return appended

    def append_many(
        self,
        receipts: Iterable[SoftwareChangeReceipt],
    ) -> tuple[SoftwareChangeReceipt, ...]:
        appended: list[SoftwareChangeReceipt] = []
        changed = False
        for receipt in receipts:
            before_count = len(self._receipts)
            appended.append(super().append(receipt))
            changed = changed or len(self._receipts) != before_count
        if changed:
            self._persist()
        return tuple(appended)

    def _persist(self) -> None:
        payload = {
            "receipts": [
                receipt.to_json_dict()
                for receipt in self._receipts
            ],
        }
        _atomic_write(self._path, _deterministic_json(payload))

    def _load_if_present(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise CorruptedDataError(
                _bounded_store_error("malformed software receipt store file", exc),
            ) from exc
        if not isinstance(raw, dict):
            raise CorruptedDataError("software receipt store payload must be an object")
        receipts_raw = raw.get("receipts")
        if not isinstance(receipts_raw, list):
            raise CorruptedDataError("software receipt store entries must be a list")
        for item in receipts_raw:
            super().append(_receipt_from_json(item))
