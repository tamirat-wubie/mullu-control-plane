"""Purpose: verify operational mathematics receipt store contracts.
Governance scope: append-only receipt persistence, replay, and dashboard summary.
Dependencies: operational math receipt store and persistence errors.
Invariants: receipt ids are idempotent, collisions fail closed, and malformed
    persisted payloads are rejected.
"""

from __future__ import annotations

import json

import pytest

from mcoi_runtime.persistence.errors import CorruptedDataError, PersistenceError
from mcoi_runtime.app.operational_math_integration import (
    OPERATIONAL_MATH_RECEIPT_STORE_PATH_ENV,
    select_operational_math_receipt_store,
    validate_operational_math_receipt_store_path,
)
from mcoi_runtime.persistence.operational_math_receipt_store import (
    FileOperationalMathReceiptStore,
    OperationalMathReceiptStore,
)


def _receipt(**overrides: object) -> dict[str, object]:
    receipt: dict[str, object] = {
        "receipt_id": "operational_math_loop_receipt:result-1",
        "status": "passed",
        "solver_outcome": "SolvedVerified",
        "target_id": "mullu-core-math",
        "event_count": 11,
        "iteration_count": 10,
        "applied_principle_ids": ["F1", "F2", "F3"],
        "unresolved_principle_ids": [],
        "result": {"result_id": "result-1"},
    }
    receipt.update(overrides)
    return receipt


def test_memory_store_appends_queries_and_summarizes_receipts() -> None:
    store = OperationalMathReceiptStore()
    passed = store.append(_receipt())
    failed = store.append(
        _receipt(
            receipt_id="operational_math_loop_receipt:result-2",
            status="failed",
            solver_outcome="AwaitingEvidence",
            target_id="bounded-math",
            unresolved_principle_ids=["F4"],
        )
    )
    summary = store.summary()

    assert passed["receipt_id"] == "operational_math_loop_receipt:result-1"
    assert failed["target_id"] == "bounded-math"
    assert store.get("operational_math_loop_receipt:result-1") == passed
    assert store.latest_receipt() == failed
    assert [receipt["receipt_id"] for receipt in store.list_receipts()] == [
        "operational_math_loop_receipt:result-1",
        "operational_math_loop_receipt:result-2",
    ]
    assert store.list_receipts(target_id="bounded-math") == (failed,)
    assert store.list_receipts(status="passed") == (passed,)
    assert store.review_receipts() == (failed,)
    assert summary["source"] == "operational_math"
    assert summary["total_receipts"] == 2
    assert summary["target_count"] == 2
    assert summary["passed_receipt_count"] == 1
    assert summary["failed_receipt_count"] == 1
    assert summary["requires_operator_review"] is True
    assert summary["review_signal_count"] == 1
    assert summary["latest_receipt_id"] == "operational_math_loop_receipt:result-2"
    assert summary["governed"] is True


def test_memory_store_is_idempotent_and_rejects_id_collision() -> None:
    store = OperationalMathReceiptStore()
    receipt = _receipt()

    first = store.append(receipt)
    second = store.append(dict(receipt))

    assert first == second
    assert len(store.list_receipts()) == 1
    assert store.summary()["total_receipts"] == 1
    with pytest.raises(PersistenceError, match="receipt id collision"):
        store.append(_receipt(status="failed"))


def test_memory_store_rejects_invalid_receipts_and_limits() -> None:
    store = OperationalMathReceiptStore()

    with pytest.raises(CorruptedDataError, match="missing receipt_id"):
        store.append({"status": "passed"})
    with pytest.raises(CorruptedDataError, match="event_count"):
        store.append(_receipt(event_count=-1))
    with pytest.raises(PersistenceError, match="limit must be a positive integer"):
        store.list_receipts(limit=0)
    with pytest.raises(PersistenceError, match="limit must be a positive integer"):
        store.review_receipts(limit=0)


def test_file_store_persists_and_reloads_receipts(tmp_path) -> None:
    store_path = tmp_path / "operational-math-receipts.json"
    receipt = _receipt()
    store = FileOperationalMathReceiptStore(store_path)

    appended = store.append(receipt)
    reloaded = FileOperationalMathReceiptStore(store_path)
    payload = json.loads(store_path.read_text(encoding="utf-8"))

    assert appended == receipt
    assert payload["receipts"] == [receipt]
    assert reloaded.get(receipt["receipt_id"]) == receipt
    assert reloaded.summary()["total_receipts"] == 1
    assert reloaded.summary()["passed_receipt_count"] == 1


def test_file_store_rejects_malformed_payload(tmp_path) -> None:
    store_path = tmp_path / "operational-math-receipts.json"
    store_path.write_text("{not-json}", encoding="utf-8")

    with pytest.raises(CorruptedDataError, match="malformed operational math receipt store file"):
        FileOperationalMathReceiptStore(store_path)


def test_hosted_store_path_requires_json_extension(tmp_path) -> None:
    valid_path = tmp_path / "operational-math-receipts.json"
    invalid_path = tmp_path / "operational-math-receipts.jsonl"

    validated = validate_operational_math_receipt_store_path(valid_path)

    assert validated == valid_path
    assert validated.suffix == ".json"
    with pytest.raises(RuntimeError, match="must use a .json file extension"):
        validate_operational_math_receipt_store_path(invalid_path)


def test_env_selection_wires_persistent_operational_math_store(tmp_path) -> None:
    store_path = tmp_path / "operational-math-receipts.json"

    bootstrap = select_operational_math_receipt_store(
        {OPERATIONAL_MATH_RECEIPT_STORE_PATH_ENV: str(store_path)}
    )
    appended = bootstrap.store.append(_receipt())
    reloaded = FileOperationalMathReceiptStore(store_path)

    assert bootstrap.persistent is True
    assert bootstrap.path == str(store_path)
    assert isinstance(bootstrap.store, FileOperationalMathReceiptStore)
    assert appended["receipt_id"] == "operational_math_loop_receipt:result-1"
    assert reloaded.summary()["total_receipts"] == 1
