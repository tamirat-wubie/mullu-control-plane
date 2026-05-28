"""Software-change receipt-store integration for the control-plane app.

Purpose: select the software-change receipt store from runtime environment
and validate any hosted persistence path before construction.
Governance scope: file-vs-in-memory selection boundary, hosted-store path
validation, and fail-closed misconfiguration handling.
Dependencies: persistence stores from mcoi_runtime.persistence.software_change
_receipt_store and standard filesystem access primitives.
Invariants: no env path means a non-persistent in-memory store; an env path
must be absolute, must use a .json extension, must not point to a directory,
and the parent directory must already exist and be writable.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from mcoi_runtime.app._integration_paths import validate_hosted_store_path
from mcoi_runtime.persistence.software_change_receipt_store import (
    FileSoftwareChangeReceiptStore,
    SoftwareChangeReceiptStore,
)


SOFTWARE_RECEIPT_STORE_PATH_ENV = "MULLU_SOFTWARE_RECEIPT_STORE_PATH"


@dataclass(frozen=True)
class SoftwareReceiptStoreBootstrap:
    """Startup posture for the software-change receipt store."""

    store: SoftwareChangeReceiptStore
    path: str
    persistent: bool


def select_software_receipt_store(
    runtime_env: Mapping[str, str],
) -> SoftwareReceiptStoreBootstrap:
    """Return the receipt store that matches the runtime environment.

    When the env path is unset, an in-memory ``SoftwareChangeReceiptStore`` is
    used. When set, the path is validated and a ``FileSoftwareChangeReceiptStore``
    is constructed (auto-loading any existing persisted state).
    """

    raw_value = runtime_env.get(SOFTWARE_RECEIPT_STORE_PATH_ENV)
    if raw_value is None or not str(raw_value).strip():
        return SoftwareReceiptStoreBootstrap(
            store=SoftwareChangeReceiptStore(),
            path="",
            persistent=False,
        )

    path = validate_software_receipt_store_path(str(raw_value).strip())
    return SoftwareReceiptStoreBootstrap(
        store=FileSoftwareChangeReceiptStore(path),
        path=str(path),
        persistent=True,
    )


def validate_software_receipt_store_path(store_path: str | Path) -> Path:
    """Validate the hosted software-change receipt-store path before use."""

    return validate_hosted_store_path(
        store_path,
        env_name=SOFTWARE_RECEIPT_STORE_PATH_ENV,
        kind="file",
        required_suffix=".json",
    )
