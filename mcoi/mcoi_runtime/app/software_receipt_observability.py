"""Purpose: wire software-change receipt summaries into observability.
Governance scope: read-only dashboard source registration only.
Dependencies: observability-compatible register_source and receipt store summary.
Invariants:
  - Registration never mutates receipt state.
  - Source name is stable for dashboard consumers.
  - Invalid wiring fails explicitly at bootstrap.
"""

from __future__ import annotations

from typing import Any

from mcoi_runtime.persistence.software_change_receipt_store import (
    SoftwareChangeReceiptStore,
)


SOFTWARE_RECEIPT_OBSERVABILITY_SOURCE = "software_receipts"


def register_software_receipt_observability(
    *,
    observability: Any,
    receipt_store: SoftwareChangeReceiptStore,
) -> None:
    """Register dashboard-ready software receipt lifecycle health."""
    register_source = getattr(observability, "register_source", None)
    if not callable(register_source):
        raise TypeError("observability must provide register_source")
    if not isinstance(receipt_store, SoftwareChangeReceiptStore):
        raise TypeError("receipt_store must be a SoftwareChangeReceiptStore")
    register_source(
        SOFTWARE_RECEIPT_OBSERVABILITY_SOURCE,
        lambda: receipt_store.summary(),
    )
