"""Gateway commercial metering tests.

Purpose: verify tenant metering, provider-cost accounting, plan limits, invoice
readiness, gross-margin review, and public snapshot schema behavior.
Governance scope: tenant-bound usage, pricing dimensions, plan-limit review,
margin evidence, invoice readiness, and manifest-ready public contracts.
Dependencies: gateway.commercial_metering and commercial metering schema.
Invariants:
  - Usage and provider costs are non-negative and tenant-bound.
  - Plan limit excess requires review before invoice readiness.
  - Margin below the plan floor requires commercial review.
  - Snapshot output is schema-valid and hash-bearing.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from gateway.commercial_metering import (
    CommercialMeteringLedger,
    CommercialVerdict,
    PlanLimit,
    PricingPlan,
    ProviderCostRecord,
    TenantCommercialAccount,
    UsageDimension,
    UsageRecord,
    commercial_metering_snapshot_to_json_dict,
)


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "commercial_metering_snapshot.schema.json"
NOW = "2026-05-05T12:00:00Z"


def test_invoice_ready_when_usage_and_margin_are_within_plan() -> None:
    ledger = _ledger()
    usage_decision = ledger.record_usage(_usage("usage-001", UsageDimension.GOVERNED_ACTION, "40"))
    cost_decision = ledger.record_provider_cost(_cost("cost-001", "20.00"))
    readiness = ledger.evaluate_invoice_readiness("tenant-a")
    snapshot = ledger.snapshot()
    summary = snapshot.tenant_summaries[0]

    assert usage_decision.verdict is CommercialVerdict.ALLOW
    assert cost_decision.reason == "invoice_ready"
    assert readiness.verdict is CommercialVerdict.ALLOW
    assert summary.invoice_ready is True
    assert summary.total_revenue_usd == Decimal("100.00")
    assert summary.provider_cost_usd == Decimal("20.00")
    assert summary.gross_margin_percent == Decimal("80.00")


def test_plan_limit_excess_requires_review_before_invoice() -> None:
    ledger = _ledger()
    usage_decision = ledger.record_usage(_usage("usage-001", UsageDimension.GOVERNED_ACTION, "150"))
    readiness = ledger.evaluate_invoice_readiness("tenant-a")
    summary = ledger.snapshot().tenant_summaries[0]

    assert usage_decision.verdict is CommercialVerdict.REVIEW
    assert usage_decision.reason == "plan_limit_exceeded"
    assert "upgrade_plan_or_approve_overage" in usage_decision.required_actions
    assert readiness.verdict is CommercialVerdict.REVIEW
    assert readiness.reason == "plan_limit_review_required"
    assert summary.invoice_ready is False
    assert UsageDimension.GOVERNED_ACTION in summary.exceeded_dimensions


def test_provider_cost_below_margin_floor_requires_review() -> None:
    ledger = _ledger()
    ledger.record_usage(_usage("usage-001", UsageDimension.GOVERNED_ACTION, "40"))
    decision = ledger.record_provider_cost(_cost("cost-001", "85.00"))
    readiness = ledger.evaluate_invoice_readiness("tenant-a")
    summary = ledger.snapshot().tenant_summaries[0]

    assert decision.verdict is CommercialVerdict.REVIEW
    assert decision.reason == "gross_margin_below_plan_floor"
    assert readiness.verdict is CommercialVerdict.REVIEW
    assert "review_provider_cost_or_price" in readiness.required_actions
    assert summary.gross_margin_percent == Decimal("15.00")
    assert summary.invoice_ready is False


def test_overage_revenue_is_computed_by_dimension() -> None:
    ledger = _ledger()
    ledger.record_usage(_usage("usage-001", UsageDimension.CONNECTOR_INVOCATION, "80"))
    ledger.record_provider_cost(_cost("cost-001", "10.00"))
    summary = ledger.snapshot().tenant_summaries[0]

    assert summary.usage_revenue_usd == Decimal("6.00")
    assert summary.base_revenue_usd == Decimal("100.00")
    assert summary.total_revenue_usd == Decimal("106.00")
    assert summary.invoice_ready is False
    assert UsageDimension.CONNECTOR_INVOCATION in summary.exceeded_dimensions


def test_negative_usage_and_provider_cost_are_rejected() -> None:
    ledger = _ledger()

    with pytest.raises(ValueError, match="quantity_non_negative"):
        ledger.record_usage(_usage("usage-001", UsageDimension.GOVERNED_ACTION, "-1"))
    with pytest.raises(ValueError, match="amount_usd_non_negative"):
        ledger.record_provider_cost(_cost("cost-001", "-0.01"))


def test_commercial_metering_snapshot_schema_exposes_operator_contract() -> None:
    ledger = _ledger()
    ledger.record_usage(_usage("usage-001", UsageDimension.GOVERNED_ACTION, "40"))
    ledger.record_provider_cost(_cost("cost-001", "20.00"))
    snapshot = ledger.snapshot()
    payload = commercial_metering_snapshot_to_json_dict(snapshot)
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    Draft202012Validator(schema).validate(payload)
    assert set(schema["required"]).issubset(payload)
    assert schema["$id"] == "urn:mullusi:schema:commercial-metering-snapshot:1"
    assert "governed_action" in schema["$defs"]["usage_dimension"]["enum"]
    assert payload["total_revenue_usd"] == "100.00"
    assert payload["total_provider_cost_usd"] == "20.00"
    assert snapshot.snapshot_hash


def _ledger() -> CommercialMeteringLedger:
    ledger = CommercialMeteringLedger()
    ledger.register_plan(_plan())
    ledger.register_account(
        TenantCommercialAccount(
            account_id="acct-tenant-a",
            tenant_id="tenant-a",
            plan_id="plan-standard",
            billing_currency="USD",
            billing_period_start="2026-05-01T00:00:00Z",
            billing_period_end="2026-06-01T00:00:00Z",
        )
    )
    return ledger


def _plan() -> PricingPlan:
    return PricingPlan(
        plan_id="plan-standard",
        name="Standard",
        base_price_monthly_usd=Decimal("100.00"),
        minimum_gross_margin_percent=Decimal("30.00"),
        limits=(
            PlanLimit(UsageDimension.GOVERNED_ACTION, Decimal("100.00"), Decimal("1.00")),
            PlanLimit(UsageDimension.CONNECTOR_INVOCATION, Decimal("50.00"), Decimal("0.20")),
            PlanLimit(UsageDimension.WORKFLOW_RUN, Decimal("20.00"), Decimal("3.00")),
        ),
        metadata={"invoice_terms": "net_30"},
    )


def _usage(usage_id: str, dimension: UsageDimension, quantity: str) -> UsageRecord:
    return UsageRecord(
        usage_id=usage_id,
        tenant_id="tenant-a",
        dimension=dimension,
        quantity=Decimal(quantity),
        source_ref=f"trace:{usage_id}",
        occurred_at=NOW,
    )


def _cost(cost_id: str, amount: str) -> ProviderCostRecord:
    return ProviderCostRecord(
        cost_id=cost_id,
        tenant_id="tenant-a",
        provider="provider-x",
        capability="rag.query",
        amount_usd=Decimal(amount),
        source_ref=f"receipt:{cost_id}",
        incurred_at=NOW,
    )
