"""Phase 134E+F — Reference Customers and Revenue Forecasting."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

@dataclass(frozen=True)
class ReferenceCustomer:
    customer_id: str
    company_name: str
    pack: str
    deployment_summary: str
    before_metrics: dict[str, str]
    after_metrics: dict[str, str]
    roi_highlight: str
    maturity_stage: str  # "early", "growing", "mature", "champion"

REFERENCE_TEMPLATES = {
    "regulated_ops": ReferenceCustomer(
        "ref-reg-001", "[Customer Name]", "regulated_ops",
        "Deployed Regulated Ops Control Tower for 15 compliance operators across 3 workspaces",
        {"evidence_completeness": "62%", "report_generation": "5 days", "compliance_cycle": "45 days"},
        {"evidence_completeness": "96%", "report_generation": "15 minutes", "compliance_cycle": "22 days"},
        "51% reduction in compliance cycle time, 95%+ evidence completeness",
        "champion",
    ),
    "enterprise_service": ReferenceCustomer(
        "ref-es-001", "[Customer Name]", "enterprise_service",
        "Deployed Enterprise Service Tower for 25 service desk operators",
        {"mttr_hours": "8.5", "sla_breach_rate": "14%", "executive_visibility": "quarterly"},
        {"mttr_hours": "4.2", "sla_breach_rate": "3%", "executive_visibility": "real_time"},
        "50% reduction in MTTR, SLA breaches from 14% to 3%",
        "growing",
    ),
    "financial_control": ReferenceCustomer(
        "ref-fin-001", "[Customer Name]", "financial_control",
        "Deployed Financial Control Tower for 10 billing/settlement operators",
        {"dso_days": "52", "dispute_resolution_days": "28", "audit_prep_weeks": "3"},
        {"dso_days": "38", "dispute_resolution_days": "9", "audit_prep_weeks": "0.5"},
        "27% DSO reduction, dispute resolution 3x faster",
        "early",
    ),
    "factory_quality": ReferenceCustomer(
        "ref-fac-001", "[Customer Name]", "factory_quality",
        "Deployed Factory Quality Tower for 1 plant with 4 lines",
        {"unplanned_downtime_pct": "12%", "quality_escape_rate": "2.1%", "maintenance_response_hrs": "4"},
        {"unplanned_downtime_pct": "7%", "quality_escape_rate": "0.9%", "maintenance_response_hrs": "0.5"},
        "42% reduction in unplanned downtime, quality escapes halved",
        "early",
    ),
}

@dataclass
class RevenueForecastEntry:
    pack: str
    stage: str
    account_count: int
    avg_deal_value: float
    probability: float  # 0-1

    @property
    def weighted_value(self) -> float:
        return self.account_count * self.avg_deal_value * self.probability

class RevenueForecastEngine:
    """Forecasts revenue across the portfolio."""

    def __init__(self):
        self._entries: list[RevenueForecastEntry] = []

    def add_forecast(self, pack: str, stage: str, accounts: int, avg_value: float, probability: float) -> None:
        self._entries.append(RevenueForecastEntry(pack, stage, accounts, avg_value, probability))

    @property
    def total_pipeline(self) -> float:
        return sum(e.account_count * e.avg_deal_value for e in self._entries)

    @property
    def weighted_pipeline(self) -> float:
        return sum(e.weighted_value for e in self._entries)

    @property
    def expected_arr(self) -> float:
        return self.weighted_pipeline * 12

    def by_pack(self, pack: str) -> float:
        return sum(e.weighted_value for e in self._entries if e.pack == pack)

    def summary(self) -> dict[str, Any]:
        return {
            "total_pipeline_mrr": round(self.total_pipeline, 2),
            "weighted_pipeline_mrr": round(self.weighted_pipeline, 2),
            "expected_arr": round(self.expected_arr, 2),
            "by_pack": {p: round(self.by_pack(p), 2) for p in set(e.pack for e in self._entries)},
            "entries": len(self._entries),
        }
