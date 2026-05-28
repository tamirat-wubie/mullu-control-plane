"""Tests for finance approval-packet store control-plane integration.

Purpose: verify that the approval-packet store selection helper picks between
the in-memory and file-backed stores deterministically and validates any
hosted persistence path before constructing the file store.
Governance scope: file-vs-in-memory selection boundary and hosted-store path
validation.
Dependencies: finance_approval_integration helper and persistence stores.
Invariants: unset env yields a non-persistent in-memory store; set env yields
a file-backed store at the validated path; invalid paths fail closed at
mount.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mcoi_runtime.app.finance_approval_integration import (
    FINANCE_APPROVAL_STORE_PATH_ENV,
    FinanceApprovalStoreBootstrap,
    select_finance_approval_store,
    validate_finance_approval_store_path,
)
from mcoi_runtime.persistence.finance_approval_store import (
    FileFinanceApprovalPacketStore,
    FinanceApprovalPacketStore,
)


def test_select_returns_in_memory_store_when_env_unset() -> None:
    bootstrap = select_finance_approval_store({})

    assert isinstance(bootstrap, FinanceApprovalStoreBootstrap)
    assert isinstance(bootstrap.store, FinanceApprovalPacketStore)
    assert not isinstance(bootstrap.store, FileFinanceApprovalPacketStore)
    assert bootstrap.persistent is False
    assert bootstrap.path == ""


def test_select_returns_in_memory_store_when_env_blank() -> None:
    bootstrap = select_finance_approval_store(
        {FINANCE_APPROVAL_STORE_PATH_ENV: "   "}
    )

    assert bootstrap.persistent is False
    assert bootstrap.path == ""


def test_select_returns_file_store_when_env_points_to_json(tmp_path: Path) -> None:
    target = tmp_path / "finance-approval-packets.json"

    bootstrap = select_finance_approval_store(
        {FINANCE_APPROVAL_STORE_PATH_ENV: str(target)}
    )

    assert isinstance(bootstrap.store, FileFinanceApprovalPacketStore)
    assert bootstrap.persistent is True
    assert bootstrap.path == str(target.expanduser())


def test_validate_rejects_relative_path() -> None:
    with pytest.raises(RuntimeError, match="absolute file path"):
        validate_finance_approval_store_path("relative/packets.json")


def test_validate_rejects_directory(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="not a directory"):
        validate_finance_approval_store_path(tmp_path)


def test_validate_rejects_wrong_extension(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match=".json file extension"):
        validate_finance_approval_store_path(tmp_path / "packets.log")


def test_validate_rejects_missing_parent(tmp_path: Path) -> None:
    missing_parent = tmp_path / "missing" / "packets.json"

    with pytest.raises(RuntimeError, match="parent directory must already exist"):
        validate_finance_approval_store_path(missing_parent)

    assert not missing_parent.parent.exists()
