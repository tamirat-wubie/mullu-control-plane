"""Phase 133A — Product Portfolio Matrix and Buyer Mapping."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

@dataclass(frozen=True)
class ProductLine:
    pack_id: str
    name: str
    domain: str
    tagline: str
    buyer_personas: tuple[str, ...]
    core_capabilities: tuple[str, ...]
    optional_addons: tuple[str, ...]
    adjacent_upsell: tuple[str, ...]
    deployment_days: int
    demo_seeded_items: int

PORTFOLIO = (
    ProductLine(
        "regulated_ops", "Regulated Operations Control Tower", "regulated_ops",
        "Governed intake, case management, evidence, and reporting for regulated enterprises",
        ("Chief Compliance Officer", "VP Audit", "Compliance Manager", "Internal Audit Lead"),
        ("intake", "case_management", "approvals", "evidence", "reporting", "dashboards", "copilot", "governance", "observability", "continuity"),
        ("multimodal_voice", "self_tuning", "blockchain_settlement"),
        ("financial_control", "enterprise_service"),
        21, 23,
    ),
    ProductLine(
        "enterprise_service", "Enterprise Service / IT Control Tower", "enterprise_service",
        "Service intake, incident resolution, SLA tracking, and customer impact for IT operations",
        ("CIO", "VP IT Operations", "Service Desk Manager", "IT Governance Lead"),
        ("service_intake", "incident_handling", "remediation", "approvals", "evidence", "dashboards", "observability", "continuity", "customer_impact", "copilot"),
        ("multimodal_voice", "self_tuning"),
        ("regulated_ops", "financial_control"),
        21, 18,
    ),
    ProductLine(
        "financial_control", "Financial Control / Settlement", "financial_control",
        "Billing, settlement, dispute, and collections management for finance operations",
        ("CFO", "VP Finance", "Revenue Controller", "Billing Operations Manager"),
        ("billing_intake", "invoice_management", "dispute_handling", "settlement_tracking", "delinquency_detection", "exception_approvals", "evidence_audit", "financial_dashboard", "executive_finance", "copilot"),
        ("blockchain_settlement", "self_tuning"),
        ("regulated_ops", "enterprise_service"),
        21, 18,
    ),
    ProductLine(
        "factory_quality", "Factory Quality / Downtime / Throughput", "factory_quality",
        "Work orders, quality, downtime, yield, and digital twin for manufacturing operations",
        ("VP Manufacturing", "Plant Manager", "Quality Director", "Operations Excellence Lead"),
        ("work_order_intake", "batch_tracking", "downtime_tracking", "quality_inspection", "nonconformance", "rework_yield", "maintenance_escalation", "digital_twin", "process_deviation", "factory_dashboard", "copilot"),
        ("multimodal_voice", "robotics_control", "process_simulation"),
        ("financial_control", "enterprise_service"),
        28, 23,
    ),
)

def capabilities_to_buyer_map() -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for p in PORTFOLIO:
        for cap in p.core_capabilities:
            result.setdefault(cap, []).append(p.name)
    return result

def comparison_sheet() -> list[dict[str, Any]]:
    return [
        {
            "product": p.name,
            "domain": p.domain,
            "capabilities": len(p.core_capabilities),
            "addons": len(p.optional_addons),
            "deployment_days": p.deployment_days,
            "buyer_count": len(p.buyer_personas),
            "upsell_paths": len(p.adjacent_upsell),
        }
        for p in PORTFOLIO
    ]
