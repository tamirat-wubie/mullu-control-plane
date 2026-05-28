"""Organization kernel integration for the control-plane app.

Purpose: build the governed organization kernel and, when configured, restore
it from a hosted persistence file before exposing it via the dependency
container.
Governance scope: kernel construction boundary, hosted-store path validation,
and restore-on-startup ordering.
Dependencies: OrganizationKernel runtime, FileOrganizationKernelStore
persistence, and standard filesystem access primitives.
Invariants: an unset env path means a fresh in-memory kernel and no store;
when set the path must be absolute, must not be a directory, must use a .json
extension, and the parent directory must already exist and be writable;
``restore_kernel`` is called exactly once before the kernel is published.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping

from mcoi_runtime.app._integration_paths import validate_hosted_store_path
from mcoi_runtime.core.organization_kernel import OrganizationKernel
from mcoi_runtime.persistence.organization_kernel_store import (
    FileOrganizationKernelStore,
)


ORGANIZATION_KERNEL_STORE_PATH_ENV = "MULLU_ORGANIZATION_KERNEL_STORE_PATH"


@dataclass(frozen=True)
class OrganizationKernelBootstrap:
    """Startup posture for the governed organization kernel integration."""

    kernel: OrganizationKernel
    store: FileOrganizationKernelStore | None
    path: str
    restored: bool


def bootstrap_organization_kernel(
    runtime_env: Mapping[str, str],
    *,
    clock: Callable[[], str],
) -> OrganizationKernelBootstrap:
    """Build the organization kernel and restore from disk when configured."""

    kernel = OrganizationKernel(clock=clock)
    raw_value = runtime_env.get(ORGANIZATION_KERNEL_STORE_PATH_ENV)
    if raw_value is None or not str(raw_value).strip():
        return OrganizationKernelBootstrap(
            kernel=kernel,
            store=None,
            path="",
            restored=False,
        )

    path = validate_organization_kernel_store_path(str(raw_value).strip())
    store = FileOrganizationKernelStore(path)
    restored = store.exists()
    store.restore_kernel(kernel)
    return OrganizationKernelBootstrap(
        kernel=kernel,
        store=store,
        path=str(path),
        restored=restored,
    )


def validate_organization_kernel_store_path(store_path: str | Path) -> Path:
    """Validate the hosted organization kernel store path before use."""

    return validate_hosted_store_path(
        store_path,
        env_name=ORGANIZATION_KERNEL_STORE_PATH_ENV,
        kind="file",
        required_suffix=".json",
    )
