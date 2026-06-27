"""Receipt and result store for InceptaDive Shadow Pass.

Purpose: persist and replay bounded shadow results/receipts for console posture,
audit inspection, and operator read models.
Governance scope: append/read metadata only; stores cannot approve, execute,
mutate candidate actions, retrieve private memory, or expose raw request text.
Dependencies: shared shadow types, JSONL, pathlib, and runtime invariant helpers.
Invariants: only redacted result, receipt, and advisory records are stored;
context payloads and raw request text are never persisted here; corrupt replay
records fail closed with explicit invariant errors.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Deque, Iterable, Protocol, TypeVar

from mcoi_runtime.core.inceptadive_external_effect_boundary import ExternalEffectBoundaryAdvisory
from mcoi_runtime.core.inceptadive_shadow_types import ShadowPassResult, ShadowReceipt
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError

LoadedRecordT = TypeVar("LoadedRecordT")


class ShadowReceiptStore(Protocol):
    """Small append/read protocol for shadow observability stores."""

    def append_result(self, result: ShadowPassResult) -> None:
        """Append one redacted shadow result."""

    def append_receipt(self, receipt: ShadowReceipt) -> None:
        """Append one redacted shadow receipt."""

    def append_external_effect_advisory(self, advisory: ExternalEffectBoundaryAdvisory) -> None:
        """Append one redacted external-effect advisory."""

    def recent_results(self, *, limit: int = 25) -> tuple[ShadowPassResult, ...]:
        """Return recent result objects for in-process console summaries."""

    def recent_receipts(self, *, limit: int = 25) -> tuple[ShadowReceipt, ...]:
        """Return recent receipt objects for in-process console summaries."""

    def recent_external_effect_advisories(
        self,
        *,
        limit: int = 25,
    ) -> tuple[ExternalEffectBoundaryAdvisory, ...]:
        """Return recent advisory objects for obligation evidence summaries."""


@dataclass
class InMemoryShadowReceiptStore:
    """Bounded in-memory result/receipt store for tests and local runtime."""

    max_items: int = 200

    def __post_init__(self) -> None:
        if self.max_items < 1:
            raise RuntimeCoreInvariantError("max_items must be positive")
        self._results: Deque[ShadowPassResult] = deque(maxlen=self.max_items)
        self._receipts: Deque[ShadowReceipt] = deque(maxlen=self.max_items)
        self._external_effect_advisories: Deque[ExternalEffectBoundaryAdvisory] = deque(maxlen=self.max_items)

    def append_result(self, result: ShadowPassResult) -> None:
        self._results.append(result.with_integrity())

    def append_receipt(self, receipt: ShadowReceipt) -> None:
        self._receipts.append(receipt.with_integrity())

    def append_external_effect_advisory(self, advisory: ExternalEffectBoundaryAdvisory) -> None:
        self._external_effect_advisories.append(advisory)

    def recent_results(self, *, limit: int = 25) -> tuple[ShadowPassResult, ...]:
        return _tail(self._results, limit)

    def recent_receipts(self, *, limit: int = 25) -> tuple[ShadowReceipt, ...]:
        return _tail(self._receipts, limit)

    def recent_external_effect_advisories(
        self,
        *,
        limit: int = 25,
    ) -> tuple[ExternalEffectBoundaryAdvisory, ...]:
        return _tail(self._external_effect_advisories, limit)


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
        self._hydrate_recent_cache()

    def append_result(self, result: ShadowPassResult) -> None:
        checked = result.with_integrity()
        self._memory.append_result(checked)
        self._append_jsonl("shadow-results.jsonl", checked.to_dict())

    def append_receipt(self, receipt: ShadowReceipt) -> None:
        checked = receipt.with_integrity()
        self._memory.append_receipt(checked)
        self._append_jsonl("shadow-receipts.jsonl", checked.to_dict())

    def append_external_effect_advisory(self, advisory: ExternalEffectBoundaryAdvisory) -> None:
        self._memory.append_external_effect_advisory(advisory)
        self._append_jsonl("external-effect-advisories.jsonl", advisory.to_dict())

    def recent_results(self, *, limit: int = 25) -> tuple[ShadowPassResult, ...]:
        return self._memory.recent_results(limit=limit)

    def recent_receipts(self, *, limit: int = 25) -> tuple[ShadowReceipt, ...]:
        return self._memory.recent_receipts(limit=limit)

    def recent_external_effect_advisories(
        self,
        *,
        limit: int = 25,
    ) -> tuple[ExternalEffectBoundaryAdvisory, ...]:
        return self._memory.recent_external_effect_advisories(limit=limit)

    def _append_jsonl(self, filename: str, payload: dict[str, object]) -> None:
        self.root_path.mkdir(parents=True, exist_ok=True)
        path = self.root_path / filename
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str))
            handle.write("\n")

    def _hydrate_recent_cache(self) -> None:
        for result in _read_jsonl_tail(
            self.root_path / "shadow-results.jsonl",
            limit=self.max_items,
            parser=ShadowPassResult.from_dict,
        ):
            self._memory.append_result(result)
        for receipt in _read_jsonl_tail(
            self.root_path / "shadow-receipts.jsonl",
            limit=self.max_items,
            parser=ShadowReceipt.from_dict,
        ):
            self._memory.append_receipt(receipt)
        for advisory in _read_jsonl_tail(
            self.root_path / "external-effect-advisories.jsonl",
            limit=self.max_items,
            parser=ExternalEffectBoundaryAdvisory.from_dict,
        ):
            self._memory.append_external_effect_advisory(advisory)


def _tail(values: Iterable[object], limit: int) -> tuple:
    if limit < 1:
        raise RuntimeCoreInvariantError("limit must be positive")
    materialized = tuple(values)
    return materialized[-limit:]


def _read_jsonl_tail(
    path: Path,
    *,
    limit: int,
    parser: Callable[[Mapping[str, object]], LoadedRecordT],
) -> tuple[LoadedRecordT, ...]:
    if limit < 1:
        raise RuntimeCoreInvariantError("limit must be positive")
    if not path.exists():
        return ()
    loaded: Deque[LoadedRecordT] = deque(maxlen=limit)
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise RuntimeCoreInvariantError(f"invalid JSONL record in {path.name} at line {line_number}") from exc
            if not isinstance(payload, Mapping):
                raise RuntimeCoreInvariantError(f"JSONL record in {path.name} at line {line_number} must be an object")
            try:
                loaded.append(parser(payload))
            except RuntimeCoreInvariantError as exc:
                raise RuntimeCoreInvariantError(f"invalid JSONL record in {path.name} at line {line_number}") from exc
    return tuple(loaded)
