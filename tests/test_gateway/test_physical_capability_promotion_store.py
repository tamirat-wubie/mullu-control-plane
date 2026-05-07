"""Tests for physical promotion receipt persistence.

Purpose: verify bounded in-memory and JSONL replay stores for physical
    promotion receipts.
Governance scope: physical promotion receipt ledger persistence, filtering,
    bounded read models, and fail-closed corrupt record handling.
Dependencies: gateway.physical_capability_promotion_store.
Invariants:
  - Stored receipts remain append-only evidence records.
  - Read models are newest-first and bounded.
  - Capability/status filters are explicit.
  - Corrupt persisted records fail closed with line-level context.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gateway.physical_capability_promotion_store import (
    InMemoryPhysicalCapabilityPromotionReceiptStore,
    JsonlPhysicalCapabilityPromotionReceiptStore,
    build_physical_capability_promotion_receipt_store_from_env,
)


def test_in_memory_physical_promotion_store_bounds_and_filters() -> None:
    store = InMemoryPhysicalCapabilityPromotionReceiptStore(max_records=2)
    store.append(_receipt("receipt-1", capability_id="physical.unlock_door", status="ready"))
    store.append(_receipt("receipt-2", capability_id="physical.open_gate", status="blocked"))
    store.append(_receipt("receipt-3", capability_id="physical.unlock_door", status="ready"))

    page = store.list(capability_id="physical.unlock_door", status="ready", limit=5)

    assert page.total == 1
    assert len(page.receipts) == 1
    assert page.receipts[0]["receipt_id"] == "receipt-3"
    assert page.next_offset is None


def test_jsonl_physical_promotion_store_replays_newest_first(tmp_path: Path) -> None:
    store_path = tmp_path / "physical-promotions.jsonl"
    store = JsonlPhysicalCapabilityPromotionReceiptStore(store_path)
    store.append(_receipt("receipt-1", status="ready"))
    store.append(_receipt("receipt-2", status="blocked"))

    replayed = JsonlPhysicalCapabilityPromotionReceiptStore(store_path).list(limit=1)

    assert replayed.total == 2
    assert len(replayed.receipts) == 1
    assert replayed.receipts[0]["receipt_id"] == "receipt-2"
    assert replayed.next_offset == 1
    assert store_path.read_text(encoding="utf-8").count("\n") == 2


def test_jsonl_physical_promotion_store_fails_closed_on_invalid_record(tmp_path: Path) -> None:
    store_path = tmp_path / "physical-promotions.jsonl"
    store_path.write_text(json.dumps(_receipt("receipt-1")) + "\n{}\n", encoding="utf-8")
    store = JsonlPhysicalCapabilityPromotionReceiptStore(store_path)

    with pytest.raises(ValueError, match="invalid physical promotion receipt JSONL record"):
        store.list()

    assert store.path == store_path
    assert store_path.exists()
    assert store_path.read_text(encoding="utf-8").count("\n") == 2


def test_physical_promotion_store_env_selects_jsonl_or_memory(tmp_path: Path) -> None:
    store_path = tmp_path / "physical-promotions.jsonl"
    jsonl_store = build_physical_capability_promotion_receipt_store_from_env(
        {"MULLU_PHYSICAL_PROMOTION_RECEIPT_LOG_PATH": str(store_path)}
    )
    memory_store = build_physical_capability_promotion_receipt_store_from_env(
        {"MULLU_PHYSICAL_PROMOTION_RECEIPT_MEMORY_LIMIT": "1"}
    )

    assert isinstance(jsonl_store, JsonlPhysicalCapabilityPromotionReceiptStore)
    assert isinstance(memory_store, InMemoryPhysicalCapabilityPromotionReceiptStore)
    assert jsonl_store.path == store_path


def _receipt(
    receipt_id: str,
    *,
    capability_id: str = "physical.unlock_door",
    status: str = "ready",
) -> dict[str, str]:
    return {
        "receipt_id": receipt_id,
        "receipt_hash": f"hash-{receipt_id}",
        "capability_id": capability_id,
        "promotion_status": status,
        "recorded_at": "2026-05-06T12:00:00+00:00",
    }
