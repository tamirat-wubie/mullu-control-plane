"""Tests for the shared integration-paths helper.

Purpose: lock in the validator + env-flag contract that every
``app/*_integration.py`` module delegates to.
Governance scope: precondition-contract single source of truth.
Dependencies: _integration_paths helper.
Invariants: env_flag truthy set is exactly {1,true,yes,on,enabled}
(case-insensitive, trimmed); validate_hosted_store_path enforces absolute
path, kind-appropriate target type, optional suffix, existing+writable
parent, and writable target.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mcoi_runtime.app._integration_paths import (
    env_flag,
    validate_hosted_store_path,
)


_ENV = "MULLU_TEST_STORE_PATH"


def test_env_flag_accepts_truthy_values_case_insensitive() -> None:
    for raw in ("1", "true", "TRUE", "yes", "  yes  ", "on", "enabled", "ENABLED"):
        assert env_flag(raw) is True, raw


def test_env_flag_rejects_falsy_or_unknown_values() -> None:
    for raw in (None, "", "  ", "0", "false", "no", "off", "disabled", "maybe"):
        assert env_flag(raw) is False, raw


def test_validate_rejects_relative_path() -> None:
    with pytest.raises(RuntimeError, match="absolute file path"):
        validate_hosted_store_path(
            "relative/x.json",
            env_name=_ENV,
            kind="file",
            required_suffix=".json",
        )


def test_validate_rejects_relative_directory_path() -> None:
    with pytest.raises(RuntimeError, match="absolute directory path"):
        validate_hosted_store_path(
            "relative/dir",
            env_name=_ENV,
            kind="directory",
        )


def test_validate_rejects_directory_target_for_file_kind(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="JSON file, not a directory"):
        validate_hosted_store_path(
            tmp_path,
            env_name=_ENV,
            kind="file",
            required_suffix=".json",
        )


def test_validate_rejects_file_target_for_directory_kind(tmp_path: Path) -> None:
    target = tmp_path / "store.txt"
    target.write_text("blob", encoding="utf-8")

    with pytest.raises(RuntimeError, match="not a regular file"):
        validate_hosted_store_path(
            target,
            env_name=_ENV,
            kind="directory",
        )


def test_validate_rejects_wrong_suffix(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match=".jsonl file extension"):
        validate_hosted_store_path(
            tmp_path / "x.log",
            env_name=_ENV,
            kind="file",
            required_suffix=".jsonl",
        )


def test_validate_rejects_missing_parent(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="parent directory must already exist"):
        validate_hosted_store_path(
            tmp_path / "missing" / "x.json",
            env_name=_ENV,
            kind="file",
            required_suffix=".json",
        )


def test_validate_accepts_nonexistent_file_under_existing_parent(tmp_path: Path) -> None:
    target = tmp_path / "x.json"

    resolved = validate_hosted_store_path(
        target,
        env_name=_ENV,
        kind="file",
        required_suffix=".json",
    )

    assert resolved == target.expanduser()
    assert not target.exists()


def test_validate_accepts_nonexistent_dir_under_existing_parent(tmp_path: Path) -> None:
    target = tmp_path / "store"

    resolved = validate_hosted_store_path(
        target,
        env_name=_ENV,
        kind="directory",
    )

    assert resolved == target.expanduser()
    assert not target.exists()


def test_validate_rejects_required_suffix_without_leading_dot() -> None:
    with pytest.raises(ValueError, match="required_suffix must start with '.'"):
        validate_hosted_store_path(
            "/tmp/x.json",
            env_name=_ENV,
            kind="file",
            required_suffix="json",
        )
