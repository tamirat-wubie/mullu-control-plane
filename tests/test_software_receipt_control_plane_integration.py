"""Tests for software-change receipt-store control-plane integration.

Purpose: verify that the receipt-store selection helper picks between the
in-memory and file-backed stores deterministically and validates any hosted
persistence path before constructing the file store.
Governance scope: file-vs-in-memory selection boundary and hosted-store path
validation.
Dependencies: software_receipt_integration helper and persistence stores.
Invariants: unset env yields a non-persistent in-memory store; set env yields
a file-backed store at the validated path; invalid paths fail closed at
mount.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mcoi_runtime.app.software_receipt_integration import (
    SOFTWARE_RECEIPT_STORE_PATH_ENV,
    SoftwareReceiptStoreBootstrap,
    select_software_receipt_store,
    validate_software_receipt_store_path,
)
from mcoi_runtime.persistence.software_change_receipt_store import (
    FileSoftwareChangeReceiptStore,
    SoftwareChangeReceiptStore,
)


def test_select_returns_in_memory_store_when_env_unset() -> None:
    bootstrap = select_software_receipt_store({})

    assert isinstance(bootstrap, SoftwareReceiptStoreBootstrap)
    assert isinstance(bootstrap.store, SoftwareChangeReceiptStore)
    assert not isinstance(bootstrap.store, FileSoftwareChangeReceiptStore)
    assert bootstrap.persistent is False
    assert bootstrap.path == ""


def test_select_returns_in_memory_store_when_env_blank() -> None:
    bootstrap = select_software_receipt_store(
        {SOFTWARE_RECEIPT_STORE_PATH_ENV: "   "}
    )

    assert bootstrap.persistent is False
    assert bootstrap.path == ""


def test_select_returns_file_store_when_env_points_to_json(tmp_path: Path) -> None:
    target = tmp_path / "software-change-receipts.json"

    bootstrap = select_software_receipt_store(
        {SOFTWARE_RECEIPT_STORE_PATH_ENV: str(target)}
    )

    assert isinstance(bootstrap.store, FileSoftwareChangeReceiptStore)
    assert bootstrap.persistent is True
    assert bootstrap.path == str(target.expanduser())


def test_validate_rejects_relative_path() -> None:
    with pytest.raises(RuntimeError, match="absolute file path"):
        validate_software_receipt_store_path("relative/receipts.json")


def test_validate_rejects_directory(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="not a directory"):
        validate_software_receipt_store_path(tmp_path)


def test_validate_rejects_wrong_extension(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match=".json file extension"):
        validate_software_receipt_store_path(tmp_path / "receipts.log")


def test_validate_rejects_missing_parent(tmp_path: Path) -> None:
    missing_parent = tmp_path / "missing" / "receipts.json"

    with pytest.raises(RuntimeError, match="parent directory must already exist"):
        validate_software_receipt_store_path(missing_parent)

    assert not missing_parent.parent.exists()
