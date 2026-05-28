"""Finance approval-packet store integration for the control-plane app.

Purpose: select the finance approval-packet store from runtime environment
and validate any hosted persistence path before construction.
Governance scope: file-vs-in-memory selection boundary, hosted-store path
validation, and fail-closed misconfiguration handling.
Dependencies: persistence stores from mcoi_runtime.persistence.finance_approval
_store and standard filesystem access primitives.
Invariants: no env path means a non-persistent in-memory store; an env path
must be absolute, must use a .json extension, must not point to a directory,
and the parent directory must already exist and be writable.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Mapping

from mcoi_runtime.persistence.finance_approval_store import (
    FileFinanceApprovalPacketStore,
    FinanceApprovalPacketStore,
)


FINANCE_APPROVAL_STORE_PATH_ENV = "MULLU_FINANCE_APPROVAL_STORE_PATH"


@dataclass(frozen=True)
class FinanceApprovalStoreBootstrap:
    """Startup posture for the finance approval-packet store."""

    store: FinanceApprovalPacketStore
    path: str
    persistent: bool


def select_finance_approval_store(
    runtime_env: Mapping[str, str],
) -> FinanceApprovalStoreBootstrap:
    """Return the approval-packet store that matches the runtime environment.

    When the env path is unset, an in-memory ``FinanceApprovalPacketStore`` is
    used. When set, the path is validated and a ``FileFinanceApprovalPacketStore``
    is constructed (auto-loading any existing persisted state).
    """

    raw_value = runtime_env.get(FINANCE_APPROVAL_STORE_PATH_ENV)
    if raw_value is None or not str(raw_value).strip():
        return FinanceApprovalStoreBootstrap(
            store=FinanceApprovalPacketStore(),
            path="",
            persistent=False,
        )

    path = validate_finance_approval_store_path(str(raw_value).strip())
    return FinanceApprovalStoreBootstrap(
        store=FileFinanceApprovalPacketStore(path),
        path=str(path),
        persistent=True,
    )


def validate_finance_approval_store_path(store_path: str | Path) -> Path:
    """Validate the hosted finance approval-packet store path before use."""

    path = Path(store_path).expanduser()
    if not path.is_absolute():
        raise RuntimeError(
            f"{FINANCE_APPROVAL_STORE_PATH_ENV} must be an absolute file path"
        )
    if path.exists() and path.is_dir():
        raise RuntimeError(
            f"{FINANCE_APPROVAL_STORE_PATH_ENV} must point to a JSON file, not a directory"
        )
    if path.suffix.lower() != ".json":
        raise RuntimeError(
            f"{FINANCE_APPROVAL_STORE_PATH_ENV} must use a .json file extension"
        )
    parent = path.parent
    if not parent.exists():
        raise RuntimeError(
            f"{FINANCE_APPROVAL_STORE_PATH_ENV} parent directory must already exist"
        )
    if not parent.is_dir():
        raise RuntimeError(
            f"{FINANCE_APPROVAL_STORE_PATH_ENV} parent must be a directory"
        )
    if path.exists() and not path.is_file():
        raise RuntimeError(
            f"{FINANCE_APPROVAL_STORE_PATH_ENV} must point to a regular file"
        )
    writable_target = path if path.exists() else parent
    if not os.access(writable_target, os.W_OK):
        raise RuntimeError(
            f"{FINANCE_APPROVAL_STORE_PATH_ENV} must be writable by the control-plane process"
        )
    return path
