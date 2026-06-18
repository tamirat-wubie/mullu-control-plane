"""Purpose: wire software-change receipt summaries into observability.
Governance scope: read-only dashboard source registration and symbol projection.
Dependencies: observability-compatible register_source, receipt store summary,
and Foundation Mode UniversalSymbol skill adapter.
Invariants:
  - Registration never mutates receipt state.
  - Source names are stable for dashboard consumers.
  - Symbol projection is read-only and never grants runtime authority.
  - Invalid wiring fails explicitly at bootstrap.
"""

from __future__ import annotations

from typing import Any

from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.symbol_skill_adapter import (
    AUTHORITY_DENIAL_FIELDS,
    SymbolAdapterSurface,
    universal_symbol_from_record,
)
from mcoi_runtime.persistence.software_change_receipt_store import (
    SoftwareChangeReceiptStore,
)


SOFTWARE_RECEIPT_OBSERVABILITY_SOURCE = "software_receipts"
SOFTWARE_RECEIPT_SYMBOL_OBSERVABILITY_SOURCE = "software_receipt_symbols"
DEFAULT_SOFTWARE_RECEIPT_SYMBOL_LIMIT = 25
MAX_SOFTWARE_RECEIPT_SYMBOL_LIMIT = 100


def software_receipt_symbol_read_model(
    *,
    receipt_store: SoftwareChangeReceiptStore,
    limit: int = DEFAULT_SOFTWARE_RECEIPT_SYMBOL_LIMIT,
) -> dict[str, Any]:
    """Project stored software receipts into read-only UniversalSymbol records."""
    if not isinstance(receipt_store, SoftwareChangeReceiptStore):
        raise TypeError("receipt_store must be a SoftwareChangeReceiptStore")
    if not isinstance(limit, int) or isinstance(limit, bool):
        raise RuntimeCoreInvariantError("limit must be an integer")
    if limit < 1 or limit > MAX_SOFTWARE_RECEIPT_SYMBOL_LIMIT:
        raise RuntimeCoreInvariantError("limit must be between 1 and 100")

    receipts = receipt_store.list_receipts(limit=limit)
    symbols = [
        universal_symbol_from_record(
            receipt,
            SymbolAdapterSurface.SOFTWARE_DEV_RECEIPT,
            generated_at=receipt.created_at,
        )
        for receipt in receipts
    ]
    return {
        "operation": "software_receipt_symbol_read_model",
        "governed": True,
        "read_model_is_not_execution_authority": True,
        "symbol_projection_is_read_only": True,
        "raw_private_payload_stored": False,
        "raw_secret_value_stored": False,
        "runtime_dispatch_performed": False,
        "connector_call_performed": False,
        "external_write_performed": False,
        "filesystem_write_performed": False,
        "state_mutation_performed": False,
        "terminal_closure_allowed": False,
        "success_claim_allowed": False,
        "source_receipt_count": len(receipts),
        "symbol_count": len(symbols),
        "limit": limit,
        "authority_denial_fields": list(AUTHORITY_DENIAL_FIELDS),
        "symbols": symbols,
    }


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
    register_source(
        SOFTWARE_RECEIPT_SYMBOL_OBSERVABILITY_SOURCE,
        lambda: software_receipt_symbol_read_model(receipt_store=receipt_store),
    )
