"""Phase 128A — Production Offer / Conversion Terms."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

@dataclass(frozen=True)
class ProductionOffer:
    offer_id: str
    customer_id: str
    product_name: str = "Regulated Operations Control Tower"
    version: str = "1.0.0"
    tier: str = "standard"  # "pilot", "standard", "enterprise"
    monthly_price: float = 2500.0
    contract_months: int = 12
    included_workspaces: int = 3
    included_operator_seats: int = 25
    included_connectors: int = 5
    sla_uptime_percent: float = 99.5
    support_level: str = "standard"  # "community", "standard", "premium", "dedicated"

    @property
    def annual_value(self) -> float:
        return self.monthly_price * self.contract_months

SCOPE_DOCUMENT = {
    "included": [
        "Intake queue management",
        "Case lifecycle and remediation tracking",
        "Approval workflows (single/quorum/unanimous/override)",
        "Evidence retrieval and bundle assembly",
        "Regulatory and executive reporting packet generation",
        "Operator dashboard with queues and worklists",
        "Executive dashboard with KPIs and risk summary",
        "Governed AI copilot (explain, draft, escalate)",
        "Constitutional governance policy enforcement",
        "Observability (metrics, traces, anomalies)",
    ],
    "excluded": [
        "Voice/multimodal interaction (available as add-on)",
        "Automated self-tuning (available as add-on)",
        "Factory/production quality management",
        "Research/lab workflow management",
        "Blockchain/ledger settlement proofs",
        "Custom industry pack development",
    ],
}

SUPPORT_SLA = {
    "standard": {
        "response_time_critical": "4 hours",
        "response_time_high": "8 hours",
        "response_time_medium": "24 hours",
        "response_time_low": "48 hours",
        "availability": "99.5%",
        "support_hours": "Business hours (Mon-Fri 8am-6pm)",
        "dedicated_csm": False,
    },
    "premium": {
        "response_time_critical": "1 hour",
        "response_time_high": "4 hours",
        "response_time_medium": "8 hours",
        "response_time_low": "24 hours",
        "availability": "99.9%",
        "support_hours": "24/7",
        "dedicated_csm": True,
    },
}
