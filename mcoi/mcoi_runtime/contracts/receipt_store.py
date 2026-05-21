"""ReceiptStore — pluggable backend for ProofBridge receipt state.

Closes the architectural-shape half of the "Receipts not persisted" gap
documented in `docs/MAF_RECEIPT_COVERAGE.md`. Defines the seam at which a
durable backend (JSONL, PostgreSQL, ledger-hashed append table, etc.) can
plug in without touching ProofBridge's core logic.

Mirrors the `AuditStore` optional-backend pattern in
`mcoi/mcoi_runtime/governance/audit/trail.py`:

    base class with no-op / minimal defaults
    InMemory*Store provides the default working implementation
    durable subclasses override only the methods they care about

The base class is NOT abstract on purpose — a downstream caller that
wants to disable lineage entirely can pass a bare `ReceiptStore()` and
get safe no-op semantics. This matches AuditStore's design rationale
("degraded gracefully — the in-process anchor still works for single-
process integrity").

What this module does NOT decide:
  * Production database schema. A future PostgresReceiptStore picks its
    own table layout; this module only specifies the operations every
    backend must support.
  * Hash-chain integrity. That belongs to LEDGER_SPEC.md and the
    audit ledger; receipt-chain integrity is a separate spec.

Migration note (read carefully if writing a durable subclass):
  ProofBridge previously held lineages in `_lineage: dict[str, CausalLineage]`
  with simple FIFO-by-insertion-order eviction. Subclasses targeting durable
  storage should preserve that eviction discipline OR document explicitly
  that they don't (because then the bridge's MAX_LINEAGE_ENTRIES bound is
  no longer load-bearing for that backend).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from mcoi_runtime.contracts.proof import CausalLineage, GuardVerdict, TransitionReceipt
from mcoi_runtime.contracts.state_machine import TransitionVerdict


def _require_entity_id(entity_id: object) -> str:
    if not isinstance(entity_id, str) or not entity_id.strip():
        raise ValueError("entity_id must be a non-empty string")
    return entity_id


def _require_lineage(lineage: object) -> CausalLineage:
    if not isinstance(lineage, CausalLineage):
        raise ValueError("lineage must be a CausalLineage instance")
    return lineage


def _require_receipt(receipt: object) -> TransitionReceipt:
    if not isinstance(receipt, TransitionReceipt):
        raise ValueError("receipt must be a TransitionReceipt instance")
    return receipt


def _require_receipt_id(receipt_id: object) -> str:
    if not isinstance(receipt_id, str) or not receipt_id.strip():
        raise ValueError("receipt_id must be a non-empty string")
    return receipt_id


def _require_positive_int(value: object, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer")
    if value < 1:
        raise ValueError(f"{field_name} must be >= 1")
    return value


class ReceiptStore:
    """Base class for causal-lineage storage backends. Defaults are
    no-ops; subclasses override only the operations they support.

    A bare `ReceiptStore()` instance produces a bridge that emits
    receipts but persists no lineage — useful for tests or surfaces
    where lineage tracking is intentionally disabled.

    For the default in-memory behavior matching pre-Protocol
    ProofBridge, use `InMemoryReceiptStore`.
    """

    def get_lineage(self, entity_id: str) -> CausalLineage | None:
        """Return the lineage for an entity, or None if absent."""
        _require_entity_id(entity_id)
        return None

    def record_lineage(self, entity_id: str, lineage: CausalLineage) -> None:
        """Persist (or replace) the lineage for an entity."""
        _require_entity_id(entity_id)
        _require_lineage(lineage)
        return None

    def record_receipt(self, receipt: TransitionReceipt) -> None:
        """Persist an emitted transition receipt."""
        _require_receipt(receipt)
        return None

    def get_receipt(self, receipt_id: str) -> TransitionReceipt | None:
        """Return a persisted transition receipt, or None if absent."""
        _require_receipt_id(receipt_id)
        return None

    @property
    def receipt_count(self) -> int:
        """Number of receipts tracked by this store."""
        return 0

    @property
    def latest_receipt_hash(self) -> str:
        """Most recent persisted receipt hash, or genesis if empty."""
        return "genesis"

    def evict_oldest(self) -> None:
        """Remove the oldest entity's lineage to free capacity.

        Called by ProofBridge before recording a new lineage when
        `len(self) >= max_entries`. The default no-op is safe — backends
        that don't bound capacity simply ignore the request.
        """
        return None

    def has_lineage(self, entity_id: str) -> bool:
        """Whether a lineage currently exists for an entity."""
        _require_entity_id(entity_id)
        return False

    def __len__(self) -> int:
        """Number of lineages tracked."""
        return 0

    @property
    def max_entries(self) -> int:
        """Capacity bound. ProofBridge calls evict_oldest() when len(self)
        reaches this. A backend that doesn't bound capacity should return
        a number large enough that the bridge never triggers eviction."""
        return 10_000


class InMemoryReceiptStore(ReceiptStore):
    """Default in-memory implementation. Bounded by max_entries with
    FIFO eviction matching pre-Protocol ProofBridge behavior.

    Insertion order is preserved by Python dict semantics (3.7+
    guarantee), so `next(iter(self._lineage))` returns the oldest
    inserted entity_id — same eviction discipline as the dict ProofBridge
    held directly before this refactor.
    """

    DEFAULT_MAX_ENTRIES = 10_000

    def __init__(self, *, max_entries: int = DEFAULT_MAX_ENTRIES) -> None:
        self._max_entries = _require_positive_int(max_entries, "max_entries")
        self._lineage: dict[str, CausalLineage] = {}
        self._receipts: dict[str, TransitionReceipt] = {}

    def get_lineage(self, entity_id: str) -> CausalLineage | None:
        entity_id = _require_entity_id(entity_id)
        return self._lineage.get(entity_id)

    def record_lineage(self, entity_id: str, lineage: CausalLineage) -> None:
        entity_id = _require_entity_id(entity_id)
        lineage = _require_lineage(lineage)
        if lineage.entity_id != entity_id:
            raise ValueError("lineage entity_id must match entity_id")
        self._lineage[entity_id] = lineage

    def record_receipt(self, receipt: TransitionReceipt) -> None:
        receipt = _require_receipt(receipt)
        self._receipts[receipt.receipt_id] = receipt

    def get_receipt(self, receipt_id: str) -> TransitionReceipt | None:
        receipt_id = _require_receipt_id(receipt_id)
        return self._receipts.get(receipt_id)

    @property
    def receipt_count(self) -> int:
        return len(self._receipts)

    @property
    def latest_receipt_hash(self) -> str:
        if not self._receipts:
            return "genesis"
        return next(reversed(self._receipts.values())).receipt_hash

    def evict_oldest(self) -> None:
        if not self._lineage:
            return
        oldest_key = next(iter(self._lineage))
        del self._lineage[oldest_key]

    def has_lineage(self, entity_id: str) -> bool:
        entity_id = _require_entity_id(entity_id)
        return entity_id in self._lineage

    def __len__(self) -> int:
        return len(self._lineage)

    @property
    def max_entries(self) -> int:
        return self._max_entries


class JsonlReceiptStore(InMemoryReceiptStore):
    """Append-only JSONL receipt store for durable local persistence.

    Purpose: persist emitted receipts and lineage mutations without changing
    ProofBridge callers.
    Governance scope: local durable proof storage only; it does not claim
    database-level transactional guarantees or external anchoring.
    Dependencies: Python filesystem JSONL, CausalLineage, TransitionReceipt.
    Invariants:
      - Every persisted line is a typed JSON event.
      - Startup replays the full file and rejects malformed records.
      - Runtime writes append only; in-memory indexes are derived state.
    """

    def __init__(
        self,
        path: str | Path,
        *,
        max_entries: int = InMemoryReceiptStore.DEFAULT_MAX_ENTRIES,
        sync_on_write: bool = False,
    ) -> None:
        if not isinstance(sync_on_write, bool):
            raise ValueError("sync_on_write must be a boolean")
        self._path = Path(path)
        self._sync_on_write = sync_on_write
        super().__init__(max_entries=max_entries)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if self._path.exists():
            self._replay()

    @property
    def path(self) -> Path:
        return self._path

    @property
    def sync_on_write(self) -> bool:
        return self._sync_on_write

    def record_lineage(self, entity_id: str, lineage: CausalLineage) -> None:
        super().record_lineage(entity_id, lineage)
        self._append_event({
            "type": "lineage_upsert",
            "entity_id": entity_id,
            "lineage": lineage.to_json_dict(),
        })

    def record_receipt(self, receipt: TransitionReceipt) -> None:
        super().record_receipt(receipt)
        self._append_event({
            "type": "receipt_record",
            "receipt_id": receipt.receipt_id,
            "receipt": receipt.to_json_dict(),
        })

    def evict_oldest(self) -> None:
        if not self._lineage:
            return
        oldest_key = next(iter(self._lineage))
        super().evict_oldest()
        self._append_event({
            "type": "lineage_evict",
            "entity_id": oldest_key,
        })

    def _append_event(self, event: dict[str, Any]) -> None:
        line = json.dumps(event, sort_keys=True, separators=(",", ":"))
        with self._path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(line + "\n")
            handle.flush()
            if self._sync_on_write:
                os.fsync(handle.fileno())

    def _replay(self) -> None:
        for line_number, raw_line in enumerate(self._path.read_text(encoding="utf-8").splitlines(), start=1):
            if not raw_line.strip():
                continue
            try:
                event = json.loads(raw_line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"receipt store JSONL line {line_number} is malformed") from exc
            if not isinstance(event, dict):
                raise ValueError(f"receipt store JSONL line {line_number} must be an object")
            self._apply_replayed_event(event, line_number=line_number)

    def _apply_replayed_event(self, event: dict[str, Any], *, line_number: int) -> None:
        event_type = event.get("type")
        if event_type == "lineage_upsert":
            entity_id = _require_entity_id(event.get("entity_id"))
            lineage_payload = event.get("lineage")
            if not isinstance(lineage_payload, dict):
                raise ValueError(f"receipt store JSONL line {line_number} lineage must be an object")
            lineage = _lineage_from_json(lineage_payload)
            InMemoryReceiptStore.record_lineage(self, entity_id, lineage)
            return
        if event_type == "receipt_record":
            receipt_payload = event.get("receipt")
            if not isinstance(receipt_payload, dict):
                raise ValueError(f"receipt store JSONL line {line_number} receipt must be an object")
            receipt = _receipt_from_json(receipt_payload)
            InMemoryReceiptStore.record_receipt(self, receipt)
            return
        if event_type == "lineage_evict":
            entity_id = _require_entity_id(event.get("entity_id"))
            self._lineage.pop(entity_id, None)
            return
        raise ValueError(f"receipt store JSONL line {line_number} has unsupported event type")


def _lineage_from_json(payload: dict[str, Any]) -> CausalLineage:
    return CausalLineage(
        lineage_id=str(payload.get("lineage_id", "")),
        entity_id=str(payload.get("entity_id", "")),
        receipt_chain=tuple(payload.get("receipt_chain", ())),
        root_receipt_id=str(payload.get("root_receipt_id", "")),
        current_state=str(payload.get("current_state", "")),
        depth=int(payload.get("depth", -1)),
    )


def _receipt_from_json(payload: dict[str, Any]) -> TransitionReceipt:
    guard_payloads = payload.get("guard_verdicts", ())
    if not isinstance(guard_payloads, list):
        raise ValueError("receipt guard_verdicts must be an array")
    guard_records: list[GuardVerdict] = []
    for index, item in enumerate(guard_payloads):
        if not isinstance(item, dict):
            raise ValueError(f"receipt guard_verdicts[{index}] must be an object")
        passed = item.get("passed", False)
        if not isinstance(passed, bool):
            raise ValueError(f"receipt guard_verdicts[{index}].passed must be a boolean")
        detail = item.get("detail", {})
        if not isinstance(detail, dict):
            raise ValueError(f"receipt guard_verdicts[{index}].detail must be an object")
        guard_records.append(GuardVerdict(
            guard_id=str(item.get("guard_id", "")),
            passed=passed,
            reason=str(item.get("reason", "")),
            detail=detail,
        ))
    return TransitionReceipt(
        receipt_id=str(payload.get("receipt_id", "")),
        machine_id=str(payload.get("machine_id", "")),
        entity_id=str(payload.get("entity_id", "")),
        from_state=str(payload.get("from_state", "")),
        to_state=str(payload.get("to_state", "")),
        action=str(payload.get("action", "")),
        before_state_hash=str(payload.get("before_state_hash", "")),
        after_state_hash=str(payload.get("after_state_hash", "")),
        guard_verdicts=tuple(guard_records),
        verdict=TransitionVerdict(str(payload.get("verdict", ""))),
        replay_token=str(payload.get("replay_token", "")),
        causal_parent=str(payload.get("causal_parent", "")),
        issued_at=str(payload.get("issued_at", "")),
        receipt_hash=str(payload.get("receipt_hash", "")),
        signature=str(payload.get("signature", "")),
        signing_key_id=str(payload.get("signing_key_id", "")),
    )
