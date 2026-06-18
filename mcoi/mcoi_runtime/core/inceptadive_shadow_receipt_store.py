"""Receipt and result store for InceptaDive Shadow Pass.

Purpose: persist and replay bounded shadow results/receipts for console posture,
audit inspection, and operator read models.
Governance scope: append/read metadata only; stores cannot approve, execute,
mutate candidate actions, retrieve private memory, or expose raw request text.
Dependencies: shared shadow types, JSONL, pathlib, and runtime invariant helpers.
Invariants: only redacted result and receipt records are stored; context payloads
and raw request text are never persisted here.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Deque, Iterable, Protocol

from mcoi_runtime.core.inceptadive_shadow_types import ShadowPassResult, ShadowReceipt
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


class ShadowReceiptStore(Protocol):
    """Small append/read protocol for shadow observability stores."""

    def append_result(self, result: ShadowPassResult) -> None:
        """Append one redacted shadow result."""

    def append_receipt(self, receipt: ShadowReceipt) -> None:
        """Append one redacted shadow receipt."""

    def recent_results(self, *, limit: int = 25) -> tuple[ShadowPassResult, ...]:
        """Return recent result objects for in-process console summaries."""

    def recent_receipts(self, *, limit: int = 25) -> tuple[ShadowReceipt, ...]:
        """Return recent receipt objects for in-process console summaries."""


@dataclass
class InMemoryShadowReceiptStore:
    """Bounded in-memory result/receipt store for tests and local runtime."""

    max_items: int = 200

    def __post_init__(self) -> None:
        if self.max_items < 1:
            raise RuntimeCoreInvariantError("max_items must be positive")
        self._results: Deque[ShadowPassResult] = deque(maxlen=self.max_items)
        self._receipts: Deque[ShadowReceipt] = deque(maxlen=self.max_items)

    def append_result(self, result: ShadowPassResult) -> None:
        self._results.append(result.with_integrity())

    def append_receipt(self, receipt: ShadowReceipt) -> None:
        self._receipts.append(receipt.with_integrity())

    def recent_results(self, *, limit: int = 25) -> tuple[ShadowPassResult, ...]:
        return _tail(self._results, limit)

    def recent_receipts(self, *, limit: int = 25) -> tuple[ShadowReceipt, ...]:
        return _tail(self._receipts, limit)


@dataclass
class JsonlShadowReceiptStore:
    """JSONL-backed append store with an in-process redacted recent cache."""

    root_path: str | Path
    max_items: int = 200

    def __post_init__(self) -> None:
        if self.max_items < 1:
            raise RuntimeCoreInvariantError("max_items must be positive")
        self.root_path = Path(self.root_path)
        self._memory = InMemoryShadowReceiptStore(max_items=self.max_items)

    def append_result(self, result: ShadowPassResult) -> None:
        checked = result.with_integrity()
        self._memory.append_result(checked)
        self._append_jsonl("shadow-results.jsonl", checked.to_dict())

    def append_receipt(self, receipt: ShadowReceipt) -> None:
        checked = receipt.with_integrity()
        self._memory.append_receipt(checked)
        self._append_jsonl("shadow-receipts.jsonl", checked.to_dict())

    def recent_results(self, *, limit: int = 25) -> tuple[ShadowPassResult, ...]:
        return self._memory.recent_results(limit=limit)

    def recent_receipts(self, *, limit: int = 25) -> tuple[ShadowReceipt, ...]:
        return self._memory.recent_receipts(limit=limit)

    def _append_jsonl(self, filename: str, payload: dict[str, object]) -> None:
        self.root_path.mkdir(parents=True, exist_ok=True)
        path = self.root_path / filename
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str))
            handle.write("\n")


def _tail(values: Iterable[object], limit: int) -> tuple:
    if limit < 1:
        raise RuntimeCoreInvariantError("limit must be positive")
    materialized = tuple(values)
    return materialized[-limit:]
