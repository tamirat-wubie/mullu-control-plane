"""Purpose: verify software-change receipt persistence.
Governance scope: append/query/replay behavior for lifecycle receipts.
Dependencies: pytest and software-change receipt store implementations.
Invariants:
  - Appends preserve receipt order.
  - Duplicate matching receipt ids are idempotent.
  - File-backed stores reload deterministic JSON into typed receipts.
  - Replay requires a terminal closure receipt.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcoi_runtime.contracts.software_dev_loop import (
    SoftwareChangeReceipt,
    SoftwareChangeReceiptStage,
)
from mcoi_runtime.persistence.errors import CorruptedDataError, PersistenceError
from mcoi_runtime.persistence.software_change_receipt_store import (
    FileSoftwareChangeReceiptStore,
    SoftwareChangeReceiptStore,
)


T0 = "2025-01-15T10:00:00+00:00"
T1 = "2025-01-15T10:00:05+00:00"


def _receipt(
    *,
    receipt_id: str,
    request_id: str = "request-1",
    stage: SoftwareChangeReceiptStage = SoftwareChangeReceiptStage.REQUEST_ADMITTED,
    created_at: str = T0,
) -> SoftwareChangeReceipt:
    return SoftwareChangeReceipt(
        receipt_id=receipt_id,
        request_id=request_id,
        stage=stage,
        cause=f"{stage.value} cause",
        outcome="ok",
        target_refs=(f"target:{stage.value}",),
        constraint_refs=("constraint:software_change_lifecycle_v1",),
        evidence_refs=(f"evidence:{stage.value}",),
        created_at=created_at,
        metadata={"stage": stage.value},
    )


def _terminal(receipt_id: str = "receipt-terminal") -> SoftwareChangeReceipt:
    return _receipt(
        receipt_id=receipt_id,
        stage=SoftwareChangeReceiptStage.TERMINAL_CLOSED,
        created_at=T1,
    )


def test_memory_store_appends_queries_and_replays_ordered_receipts() -> None:
    store = SoftwareChangeReceiptStore()
    admitted = _receipt(receipt_id="receipt-admitted")
    gate = _receipt(
        receipt_id="receipt-gate",
        stage=SoftwareChangeReceiptStage.GATE_EVALUATED,
    )
    terminal = _terminal()

    appended = store.append_many((admitted, gate, terminal))
    replayed = store.replay_request("request-1")

    assert appended == (admitted, gate, terminal)
    assert store.get("receipt-gate") == gate
    assert store.list_receipts(stage=SoftwareChangeReceiptStage.GATE_EVALUATED) == (gate,)
    assert replayed == (admitted, gate, terminal)
    assert store.list_receipts(limit=2) == (gate, terminal)


def test_store_summary_reports_lifecycle_health() -> None:
    store = SoftwareChangeReceiptStore()
    store.append_many((
        _receipt(receipt_id="receipt-admitted"),
        _receipt(
            receipt_id="receipt-gate",
            stage=SoftwareChangeReceiptStage.GATE_EVALUATED,
        ),
        _terminal(),
        _receipt(receipt_id="receipt-open", request_id="request-open"),
    ))

    summary = store.summary()

    assert summary["total_receipts"] == 4
    assert summary["request_count"] == 2
    assert summary["terminal_request_count"] == 1
    assert summary["open_request_count"] == 1
    assert summary["requires_operator_review"] is True
    assert summary["review_signal_count"] == 1
    assert summary["review_signals"] == [
        {
            "request_id": "request-open",
            "latest_receipt_id": "receipt-open",
            "latest_stage": "request_admitted",
            "latest_outcome": "ok",
            "reason": "software_change_receipt_chain_open",
        }
    ]
    assert summary["by_stage"]["request_admitted"] == 2
    assert summary["by_stage"]["gate_evaluated"] == 1
    assert summary["by_stage"]["terminal_closed"] == 1
    assert summary["latest_receipt_id"] == "receipt-open"
    assert summary["latest_request_id"] == "request-open"
    assert summary["latest_stage"] == "request_admitted"
    assert summary["governed"] is True


def test_empty_store_summary_is_dashboard_safe() -> None:
    summary = SoftwareChangeReceiptStore().summary()

    assert summary["total_receipts"] == 0
    assert summary["request_count"] == 0
    assert summary["terminal_request_count"] == 0
    assert summary["open_request_count"] == 0
    assert summary["requires_operator_review"] is False
    assert summary["review_signal_count"] == 0
    assert summary["review_signals"] == []
    assert summary["latest_receipt_id"] is None
    assert summary["by_stage"]["terminal_closed"] == 0
    assert summary["governed"] is True


def test_store_summary_bounds_review_signals() -> None:
    store = SoftwareChangeReceiptStore()
    for index in range(12):
        store.append(_receipt(
            receipt_id=f"receipt-open-{index}",
            request_id=f"request-open-{index}",
        ))

    summary = store.summary()

    assert summary["open_request_count"] == 12
    assert summary["review_signal_count"] == 12
    assert len(summary["review_signals"]) == 10
    assert summary["review_signals"][0]["request_id"] == "request-open-0"
    assert summary["review_signals"][-1]["request_id"] == "request-open-9"
    assert all(
        signal["reason"] == "software_change_receipt_chain_open"
        for signal in summary["review_signals"]
    )


def test_review_receipts_returns_latest_open_request_receipts() -> None:
    store = SoftwareChangeReceiptStore()
    first_open = _receipt(receipt_id="receipt-open-first", request_id="request-1")
    second_open = _receipt(receipt_id="receipt-open-second", request_id="request-open-second")
    terminal = _terminal()
    store.append_many((first_open, terminal, second_open))

    review_receipts = store.review_receipts()

    assert review_receipts == (second_open,)
    assert store.review_receipts(limit=1) == (second_open,)
    assert store.review_receipts(limit=None) == (second_open,)


def test_review_receipts_rejects_invalid_limit() -> None:
    store = SoftwareChangeReceiptStore()

    with pytest.raises(PersistenceError):
        store.review_receipts(limit=0)


def test_duplicate_matching_receipt_is_idempotent() -> None:
    store = SoftwareChangeReceiptStore()
    receipt = _receipt(receipt_id="receipt-1")

    first = store.append(receipt)
    second = store.append(receipt)

    assert first == receipt
    assert second == receipt
    assert store.list_receipts() == (receipt,)


def test_duplicate_receipt_id_with_different_payload_fails_closed() -> None:
    store = SoftwareChangeReceiptStore()
    store.append(_receipt(receipt_id="receipt-1"))

    with pytest.raises(PersistenceError):
        store.append(_receipt(
            receipt_id="receipt-1",
            stage=SoftwareChangeReceiptStage.PATCH_APPLIED,
        ))


def test_replay_requires_terminal_closure_receipt() -> None:
    store = SoftwareChangeReceiptStore()
    store.append(_receipt(receipt_id="receipt-1"))

    with pytest.raises(PersistenceError):
        store.replay_request("request-1")

    with pytest.raises(PersistenceError):
        store.replay_request("missing-request")


def test_file_store_persists_and_reloads_typed_receipts(tmp_path: Path) -> None:
    path = tmp_path / "software_receipts.json"
    store = FileSoftwareChangeReceiptStore(path)
    admitted = _receipt(receipt_id="receipt-admitted")
    terminal = _terminal()

    store.append_many((admitted, terminal))
    reloaded = FileSoftwareChangeReceiptStore(path)

    assert path.exists()
    assert reloaded.list_receipts() == (admitted, terminal)
    assert reloaded.replay_request("request-1")[-1].stage is SoftwareChangeReceiptStage.TERMINAL_CLOSED


def test_file_store_rejects_malformed_payload(tmp_path: Path) -> None:
    path = tmp_path / "software_receipts.json"
    path.write_text(json.dumps({"receipts": [{"receipt_id": "incomplete"}]}), encoding="utf-8")

    with pytest.raises(CorruptedDataError):
        FileSoftwareChangeReceiptStore(path)
