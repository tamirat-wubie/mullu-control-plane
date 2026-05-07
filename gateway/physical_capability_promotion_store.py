"""Physical capability promotion receipt store.

Purpose: persist operator-facing physical promotion receipts for durable replay.
Governance scope: receipt ledger storage only; receipt emission and admission
    authority remain owned by the physical promotion emitter and registry gates.
Dependencies: JSON serialization, filesystem path configuration, and receipt
    payloads emitted by gateway.physical_capability_promotion_receipt.
Invariants:
  - Stored records are append-only.
  - Listing is bounded, newest-first, and filterable by capability/status.
  - Invalid persisted records fail closed with line-level causal context.
  - The store never promotes or mutates physical capability authority.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol


REQUIRED_RECEIPT_FIELDS = (
    "receipt_id",
    "receipt_hash",
    "capability_id",
    "promotion_status",
    "recorded_at",
)


@dataclass(frozen=True, slots=True)
class PhysicalPromotionReceiptPage:
    """Bounded newest-first receipt page."""

    receipts: tuple[dict[str, Any], ...]
    total: int
    limit: int
    offset: int
    next_offset: int | None


class PhysicalCapabilityPromotionReceiptStore(Protocol):
    """Persistence contract for physical promotion receipt ledgers."""

    def append(self, receipt: Mapping[str, Any]) -> None:
        """Persist one schema-validated physical promotion receipt."""

    def list(
        self,
        *,
        capability_id: str = "",
        status: str = "",
        limit: int = 100,
        offset: int = 0,
    ) -> PhysicalPromotionReceiptPage:
        """Return a bounded newest-first receipt page."""


class InMemoryPhysicalCapabilityPromotionReceiptStore:
    """Bounded in-memory physical promotion receipt ledger."""

    def __init__(self, *, max_records: int = 500) -> None:
        self._max_records = _bounded_max_records(max_records)
        self._receipts: list[dict[str, Any]] = []

    def append(self, receipt: Mapping[str, Any]) -> None:
        """Append one receipt to memory after contract validation."""
        self._receipts.append(_receipt_payload(receipt))
        del self._receipts[:-self._max_records]

    def list(
        self,
        *,
        capability_id: str = "",
        status: str = "",
        limit: int = 100,
        offset: int = 0,
    ) -> PhysicalPromotionReceiptPage:
        """Return a bounded newest-first receipt page from memory."""
        return _page_receipts(
            tuple(reversed(self._receipts)),
            capability_id=capability_id,
            status=status,
            limit=limit,
            offset=offset,
        )


class JsonlPhysicalCapabilityPromotionReceiptStore:
    """Append-only JSONL physical promotion receipt ledger."""

    def __init__(self, path: str | Path) -> None:
        path_text = str(path).strip()
        if not path_text:
            raise ValueError("physical promotion receipt store path is required")
        resolved_path = Path(path_text)
        if resolved_path.exists() and resolved_path.is_dir():
            raise ValueError("physical promotion receipt store path must be a file path")
        self._path = resolved_path

    @property
    def path(self) -> Path:
        """Return the JSONL store path."""
        return self._path

    def append(self, receipt: Mapping[str, Any]) -> None:
        """Persist one receipt as a canonical JSONL line."""
        payload = _receipt_payload(receipt)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(f"{line}\n")

    def list(
        self,
        *,
        capability_id: str = "",
        status: str = "",
        limit: int = 100,
        offset: int = 0,
    ) -> PhysicalPromotionReceiptPage:
        """Return a bounded newest-first receipt page from disk."""
        if not self._path.exists():
            return _page_receipts((), capability_id=capability_id, status=status, limit=limit, offset=offset)
        receipts: list[dict[str, Any]] = []
        with self._path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    parsed = json.loads(stripped)
                    receipts.append(_receipt_payload(parsed))
                except (TypeError, ValueError, json.JSONDecodeError) as exc:
                    raise ValueError(
                        f"invalid physical promotion receipt JSONL record at {self._path}:{line_number}"
                    ) from exc
        return _page_receipts(
            tuple(reversed(receipts)),
            capability_id=capability_id,
            status=status,
            limit=limit,
            offset=offset,
        )


def build_physical_capability_promotion_receipt_store_from_env(
    env: Mapping[str, str] | None = None,
) -> PhysicalCapabilityPromotionReceiptStore:
    """Build the physical promotion receipt store declared by environment."""
    source = env if env is not None else os.environ
    path = str(source.get("MULLU_PHYSICAL_PROMOTION_RECEIPT_LOG_PATH", "")).strip()
    if path:
        return JsonlPhysicalCapabilityPromotionReceiptStore(path)
    return InMemoryPhysicalCapabilityPromotionReceiptStore(
        max_records=_int_env(source, "MULLU_PHYSICAL_PROMOTION_RECEIPT_MEMORY_LIMIT", 500)
    )


def _receipt_payload(receipt: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(receipt, Mapping):
        raise ValueError("physical promotion receipt must be an object")
    payload = dict(receipt)
    missing = tuple(
        field_name
        for field_name in REQUIRED_RECEIPT_FIELDS
        if not str(payload.get(field_name, "")).strip()
    )
    if missing:
        raise ValueError(f"physical promotion receipt missing required fields: {','.join(missing)}")
    return payload


def _page_receipts(
    receipts: tuple[dict[str, Any], ...],
    *,
    capability_id: str,
    status: str,
    limit: int,
    offset: int,
) -> PhysicalPromotionReceiptPage:
    filtered = receipts
    if capability_id:
        filtered = tuple(receipt for receipt in filtered if receipt.get("capability_id") == capability_id)
    if status:
        filtered = tuple(receipt for receipt in filtered if receipt.get("promotion_status") == status)
    bounded_limit = max(1, min(int(limit), 500))
    bounded_offset = max(0, int(offset))
    page = filtered[bounded_offset:bounded_offset + bounded_limit]
    next_offset = bounded_offset + len(page)
    return PhysicalPromotionReceiptPage(
        receipts=page,
        total=len(filtered),
        limit=bounded_limit,
        offset=bounded_offset,
        next_offset=next_offset if next_offset < len(filtered) else None,
    )


def _bounded_max_records(value: int) -> int:
    return max(1, min(int(value), 10000))


def _int_env(env: Mapping[str, str], name: str, default: int) -> int:
    try:
        return int(env.get(name, str(default)))
    except ValueError:
        return default
