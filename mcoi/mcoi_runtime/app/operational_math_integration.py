"""Operational mathematics receipt-store integration for the control-plane app.

Purpose: select the operational mathematics receipt store from runtime
environment and validate any hosted persistence path before construction.
Governance scope: file-vs-in-memory selection boundary, hosted-store path
validation, and fail-closed misconfiguration handling.
Dependencies: persistence stores from mcoi_runtime.persistence.operational_math
_receipt_store and standard filesystem access primitives.
Invariants: no env path means a non-persistent in-memory store; an env path
must be absolute, must use a .jsonl extension, must not point to a directory,
and the parent directory must already exist and be writable.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Mapping

from mcoi_runtime.persistence.operational_math_receipt_store import (
    FileOperationalMathReceiptStore,
    OperationalMathReceiptStore,
)


OPERATIONAL_MATH_RECEIPT_STORE_PATH_ENV = "MULLU_OPERATIONAL_MATH_RECEIPT_STORE_PATH"


@dataclass(frozen=True)
class OperationalMathReceiptStoreBootstrap:
    """Startup posture for the operational mathematics receipt store."""

    store: OperationalMathReceiptStore
    path: str
    persistent: bool


def select_operational_math_receipt_store(
    runtime_env: Mapping[str, str],
) -> OperationalMathReceiptStoreBootstrap:
    """Return the receipt store that matches the runtime environment.

    When the env path is unset, an in-memory ``OperationalMathReceiptStore`` is
    used. When set, the path is validated and a ``FileOperationalMathReceiptStore``
    is constructed.
    """

    raw_value = runtime_env.get(OPERATIONAL_MATH_RECEIPT_STORE_PATH_ENV)
    if raw_value is None or not str(raw_value).strip():
        return OperationalMathReceiptStoreBootstrap(
            store=OperationalMathReceiptStore(),
            path="",
            persistent=False,
        )

    path = validate_operational_math_receipt_store_path(str(raw_value).strip())
    return OperationalMathReceiptStoreBootstrap(
        store=FileOperationalMathReceiptStore(path),
        path=str(path),
        persistent=True,
    )


def validate_operational_math_receipt_store_path(
    store_path: str | Path,
) -> Path:
    """Validate the hosted operational math receipt-store path before use."""

    path = Path(store_path).expanduser()
    if not path.is_absolute():
        raise RuntimeError(
            f"{OPERATIONAL_MATH_RECEIPT_STORE_PATH_ENV} must be an absolute file path"
        )
    if path.exists() and path.is_dir():
        raise RuntimeError(
            f"{OPERATIONAL_MATH_RECEIPT_STORE_PATH_ENV} must point to a JSONL file, not a directory"
        )
    if path.suffix.lower() != ".jsonl":
        raise RuntimeError(
            f"{OPERATIONAL_MATH_RECEIPT_STORE_PATH_ENV} must use a .jsonl file extension"
        )
    parent = path.parent
    if not parent.exists():
        raise RuntimeError(
            f"{OPERATIONAL_MATH_RECEIPT_STORE_PATH_ENV} parent directory must already exist"
        )
    if not parent.is_dir():
        raise RuntimeError(
            f"{OPERATIONAL_MATH_RECEIPT_STORE_PATH_ENV} parent must be a directory"
        )
    if path.exists() and not path.is_file():
        raise RuntimeError(
            f"{OPERATIONAL_MATH_RECEIPT_STORE_PATH_ENV} must point to a regular file"
        )
    writable_target = path if path.exists() else parent
    if not os.access(writable_target, os.W_OK):
        raise RuntimeError(
            f"{OPERATIONAL_MATH_RECEIPT_STORE_PATH_ENV} must be writable by the control-plane process"
        )
    return path
