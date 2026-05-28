"""Tests for operational mathematics receipt-store control-plane integration.

Purpose: verify that the receipt-store selection helper picks between the
in-memory and file-backed stores deterministically and validates any hosted
persistence path before constructing the file store.
Governance scope: file-vs-in-memory selection boundary and hosted-store path
validation.
Dependencies: operational_math_integration helper and persistence stores.
Invariants: unset env yields a non-persistent in-memory store; set env yields
a file-backed store at the validated path; invalid paths fail closed at
mount.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mcoi_runtime.app.operational_math_integration import (
    OPERATIONAL_MATH_RECEIPT_STORE_PATH_ENV,
    OperationalMathReceiptStoreBootstrap,
    select_operational_math_receipt_store,
    validate_operational_math_receipt_store_path,
)
from mcoi_runtime.persistence.operational_math_receipt_store import (
    FileOperationalMathReceiptStore,
    OperationalMathReceiptStore,
)


def test_select_returns_in_memory_store_when_env_unset() -> None:
    bootstrap = select_operational_math_receipt_store({})

    assert isinstance(bootstrap, OperationalMathReceiptStoreBootstrap)
    assert isinstance(bootstrap.store, OperationalMathReceiptStore)
    assert not isinstance(bootstrap.store, FileOperationalMathReceiptStore)
    assert bootstrap.persistent is False
    assert bootstrap.path == ""


def test_select_returns_in_memory_store_when_env_blank() -> None:
    bootstrap = select_operational_math_receipt_store(
        {OPERATIONAL_MATH_RECEIPT_STORE_PATH_ENV: "   "}
    )

    assert bootstrap.persistent is False
    assert bootstrap.path == ""


def test_select_returns_file_store_when_env_points_to_jsonl(tmp_path: Path) -> None:
    target = tmp_path / "operational-math-receipts.jsonl"

    bootstrap = select_operational_math_receipt_store(
        {OPERATIONAL_MATH_RECEIPT_STORE_PATH_ENV: str(target)}
    )

    assert isinstance(bootstrap.store, FileOperationalMathReceiptStore)
    assert bootstrap.persistent is True
    assert bootstrap.path == str(target.expanduser())


def test_validate_rejects_relative_path() -> None:
    with pytest.raises(RuntimeError, match="absolute file path"):
        validate_operational_math_receipt_store_path("relative/receipts.jsonl")


def test_validate_rejects_directory(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="not a directory"):
        validate_operational_math_receipt_store_path(tmp_path)


def test_validate_rejects_wrong_extension(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match=".jsonl file extension"):
        validate_operational_math_receipt_store_path(tmp_path / "receipts.log")


def test_validate_rejects_missing_parent(tmp_path: Path) -> None:
    missing_parent = tmp_path / "missing" / "receipts.jsonl"

    with pytest.raises(RuntimeError, match="parent directory must already exist"):
        validate_operational_math_receipt_store_path(missing_parent)

    assert not missing_parent.parent.exists()
