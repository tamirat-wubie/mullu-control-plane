"""Purpose: verify software receipt observability source wiring.
Governance scope: dashboard registration for receipt lifecycle summaries and
read-only UniversalSymbol projection.
Dependencies: jsonschema, observability registration helper, symbol adapter,
and receipt store.
Invariants:
  - Source names remain stable.
  - Registered sources are read-only and dashboard-safe.
  - Symbol projection denies runtime authority.
  - Invalid bootstrap wiring fails explicitly.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from mcoi_runtime.app.software_receipt_observability import (
    SOFTWARE_RECEIPT_OBSERVABILITY_SOURCE,
    SOFTWARE_RECEIPT_SYMBOL_OBSERVABILITY_SOURCE,
    register_software_receipt_observability,
    software_receipt_symbol_read_model,
)
from mcoi_runtime.contracts.software_dev_loop import (
    SoftwareChangeReceipt,
    SoftwareChangeReceiptStage,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.symbol_skill_adapter import AUTHORITY_DENIAL_FIELDS
from mcoi_runtime.persistence.software_change_receipt_store import (
    SoftwareChangeReceiptStore,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


class FakeObservability:
    def __init__(self) -> None:
        self.sources: dict[str, object] = {}

    def register_source(self, name, source) -> None:
        self.sources[name] = source


def _validator() -> Draft202012Validator:
    schema = json.loads((REPO_ROOT / "schemas" / "universal_symbol.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


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
    symbol_source = observability.sources[SOFTWARE_RECEIPT_SYMBOL_OBSERVABILITY_SOURCE]
    summary = source()

    assert SOFTWARE_RECEIPT_OBSERVABILITY_SOURCE == "software_receipts"
    assert SOFTWARE_RECEIPT_SYMBOL_OBSERVABILITY_SOURCE == "software_receipt_symbols"
    assert callable(symbol_source)
    assert summary["total_receipts"] == 1
    assert summary["terminal_request_count"] == 1
    assert summary["open_request_count"] == 0
    assert summary["requires_operator_review"] is False
    assert summary["review_signals"] == []
    assert summary["latest_stage"] == "terminal_closed"
    assert summary["governed"] is True


def test_registers_read_only_symbol_projection_source() -> None:
    observability = FakeObservability()
    receipt_store = SoftwareChangeReceiptStore()
    receipt_store.append(_receipt())

    register_software_receipt_observability(
        observability=observability,
        receipt_store=receipt_store,
    )
    source = observability.sources[SOFTWARE_RECEIPT_SYMBOL_OBSERVABILITY_SOURCE]
    read_model = source()
    symbol = read_model["symbols"][0]

    _validator().validate(symbol)
    assert read_model["operation"] == "software_receipt_symbol_read_model"
    assert read_model["read_model_is_not_execution_authority"] is True
    assert read_model["symbol_projection_is_read_only"] is True
    assert read_model["raw_private_payload_stored"] is False
    assert read_model["raw_secret_value_stored"] is False
    assert read_model["runtime_dispatch_performed"] is False
    assert read_model["connector_call_performed"] is False
    assert read_model["external_write_performed"] is False
    assert read_model["filesystem_write_performed"] is False
    assert read_model["state_mutation_performed"] is False
    assert read_model["terminal_closure_allowed"] is False
    assert read_model["success_claim_allowed"] is False
    assert read_model["source_receipt_count"] == 1
    assert read_model["symbol_count"] == 1
    assert read_model["authority_denial_fields"] == list(AUTHORITY_DENIAL_FIELDS)
    assert symbol["symbol_identity"]["symbol_kind"] == "receipt"
    assert symbol["symbol_governance"]["governance_mode"] == "foundation"
    assert all(value is False for value in symbol["symbol_authority_boundary"].values())
    assert "evidence:observable" in symbol["evidence_refs"]


def test_symbol_read_model_rejects_invalid_limit() -> None:
    receipt_store = SoftwareChangeReceiptStore()
    receipt_store.append(_receipt())

    with pytest.raises(RuntimeCoreInvariantError, match="limit must be between 1 and 100"):
        software_receipt_symbol_read_model(receipt_store=receipt_store, limit=0)
    with pytest.raises(RuntimeCoreInvariantError, match="limit must be between 1 and 100"):
        software_receipt_symbol_read_model(receipt_store=receipt_store, limit=101)
    with pytest.raises(RuntimeCoreInvariantError, match="limit must be an integer"):
        software_receipt_symbol_read_model(receipt_store=receipt_store, limit=True)


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
