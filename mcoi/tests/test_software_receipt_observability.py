"""Purpose: verify software receipt observability source wiring.
Governance scope: dashboard registration for receipt lifecycle summaries.
Dependencies: observability registration helper and receipt store.
Invariants:
  - Source name remains stable.
  - Registered source is read-only and dashboard-safe.
  - Invalid bootstrap wiring fails explicitly.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.app.software_receipt_observability import (
    SOFTWARE_RECEIPT_OBSERVABILITY_SOURCE,
    register_software_receipt_observability,
)
from mcoi_runtime.contracts.software_dev_loop import (
    SoftwareChangeReceipt,
    SoftwareChangeReceiptStage,
)
from mcoi_runtime.persistence.software_change_receipt_store import (
    SoftwareChangeReceiptStore,
)


class FakeObservability:
    def __init__(self) -> None:
        self.sources: dict[str, object] = {}

    def register_source(self, name, source) -> None:
        self.sources[name] = source


def _receipt() -> SoftwareChangeReceipt:
    return SoftwareChangeReceipt(
        receipt_id="receipt-observable",
        request_id="request-observable",
        stage=SoftwareChangeReceiptStage.TERMINAL_CLOSED,
        cause="terminal closure cause",
        outcome="ok",
        target_refs=("target:observable",),
        constraint_refs=("constraint:software_change_lifecycle_v1",),
        evidence_refs=("evidence:observable",),
        created_at="2025-01-15T10:00:00+00:00",
    )


def test_registers_dashboard_safe_receipt_summary() -> None:
    observability = FakeObservability()
    receipt_store = SoftwareChangeReceiptStore()
    receipt_store.append(_receipt())

    register_software_receipt_observability(
        observability=observability,
        receipt_store=receipt_store,
    )
    source = observability.sources[SOFTWARE_RECEIPT_OBSERVABILITY_SOURCE]
    summary = source()

    assert SOFTWARE_RECEIPT_OBSERVABILITY_SOURCE == "software_receipts"
    assert summary["total_receipts"] == 1
    assert summary["terminal_request_count"] == 1
    assert summary["open_request_count"] == 0
    assert summary["requires_operator_review"] is False
    assert summary["review_signals"] == []
    assert summary["latest_stage"] == "terminal_closed"
    assert summary["governed"] is True


def test_registration_rejects_invalid_observability_surface() -> None:
    with pytest.raises(TypeError):
        register_software_receipt_observability(
            observability=object(),
            receipt_store=SoftwareChangeReceiptStore(),
        )


def test_registration_rejects_invalid_receipt_store() -> None:
    with pytest.raises(TypeError):
        register_software_receipt_observability(
            observability=FakeObservability(),
            receipt_store=object(),  # type: ignore[arg-type]
        )
