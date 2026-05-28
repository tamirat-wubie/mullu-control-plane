"""Tests for governed organization-kernel control-plane integration.

Purpose: verify the kernel-bootstrap helper builds a fresh kernel when no
hosted store is configured, and restores the kernel from disk exactly once
when a store path is provided.
Governance scope: kernel construction boundary, hosted-store path validation,
and restore-on-startup ordering.
Dependencies: organization_kernel_integration helper, OrganizationKernel, and
FileOrganizationKernelStore.
Invariants: unset env yields a kernel with no backing store and no restore;
set env validates the path, constructs the store, and calls restore_kernel
exactly once before publication; invalid paths fail closed.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from mcoi_runtime.app.organization_kernel_integration import (
    ORGANIZATION_KERNEL_STORE_PATH_ENV,
    OrganizationKernelBootstrap,
    bootstrap_organization_kernel,
    validate_organization_kernel_store_path,
)
from mcoi_runtime.core.organization_kernel import OrganizationKernel
from mcoi_runtime.persistence.organization_kernel_store import (
    FileOrganizationKernelStore,
)


def _frozen_clock() -> str:
    return datetime(2026, 5, 28, 0, 0, 0, tzinfo=timezone.utc).isoformat()


def test_bootstrap_returns_fresh_kernel_when_env_unset() -> None:
    bootstrap = bootstrap_organization_kernel({}, clock=_frozen_clock)

    assert isinstance(bootstrap, OrganizationKernelBootstrap)
    assert isinstance(bootstrap.kernel, OrganizationKernel)
    assert bootstrap.store is None
    assert bootstrap.restored is False
    assert bootstrap.path == ""


def test_bootstrap_returns_fresh_kernel_when_env_blank() -> None:
    bootstrap = bootstrap_organization_kernel(
        {ORGANIZATION_KERNEL_STORE_PATH_ENV: "   "},
        clock=_frozen_clock,
    )

    assert bootstrap.store is None
    assert bootstrap.restored is False
    assert bootstrap.path == ""


def test_bootstrap_attaches_file_store_without_restoring_missing_file(
    tmp_path: Path,
) -> None:
    target = tmp_path / "organization-kernel.json"

    bootstrap = bootstrap_organization_kernel(
        {ORGANIZATION_KERNEL_STORE_PATH_ENV: str(target)},
        clock=_frozen_clock,
    )

    assert isinstance(bootstrap.store, FileOrganizationKernelStore)
    assert bootstrap.store.path == target.expanduser()
    assert bootstrap.restored is False
    assert bootstrap.path == str(target.expanduser())


def test_bootstrap_restores_when_state_file_present(tmp_path: Path) -> None:
    target = tmp_path / "organization-kernel.json"
    seed = OrganizationKernel(clock=_frozen_clock)
    seed_store = FileOrganizationKernelStore(target)
    seed_store.save_state(seed.snapshot_state())

    bootstrap = bootstrap_organization_kernel(
        {ORGANIZATION_KERNEL_STORE_PATH_ENV: str(target)},
        clock=_frozen_clock,
    )

    assert bootstrap.restored is True
    assert bootstrap.store is not None
    assert target.is_file()


def test_validate_rejects_relative_path() -> None:
    with pytest.raises(RuntimeError, match="absolute file path"):
        validate_organization_kernel_store_path("relative/state.json")


def test_validate_rejects_directory(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="not a directory"):
        validate_organization_kernel_store_path(tmp_path)


def test_validate_rejects_wrong_extension(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match=".json file extension"):
        validate_organization_kernel_store_path(tmp_path / "state.txt")


def test_validate_rejects_missing_parent(tmp_path: Path) -> None:
    missing_parent = tmp_path / "missing" / "state.json"

    with pytest.raises(RuntimeError, match="parent directory must already exist"):
        validate_organization_kernel_store_path(missing_parent)

    assert not missing_parent.parent.exists()
