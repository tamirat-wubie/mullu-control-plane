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
from pathlib import Path
from typing import Mapping

from mcoi_runtime.app._integration_paths import validate_hosted_store_path
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

    return validate_hosted_store_path(
        store_path,
        env_name=FINANCE_APPROVAL_STORE_PATH_ENV,
        kind="file",
        required_suffix=".json",
    )
