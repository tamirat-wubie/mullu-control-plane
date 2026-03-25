"""Phase 144 — Multi-Bundle Delivery Automation / Implementation Orchestrator."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from datetime import datetime, timezone

# 144A — Deployment Orchestration
@dataclass
class DeploymentStep:
    step: int
    name: str
    category: str  # "connector", "persona", "dashboard", "import", "validation", "golive"
    estimated_hours: float
    completed: bool = False

BUNDLE_DEPLOYMENT_PLANS = {
    "single_pack": [
        DeploymentStep(1, "tenant_bootstrap", "setup", 2.0),
        DeploymentStep(2, "connector_activation", "connector", 4.0),
        DeploymentStep(3, "persona_provisioning", "persona", 1.0),
        DeploymentStep(4, "governance_configuration", "setup", 2.0),
        DeploymentStep(5, "data_import", "import", 8.0),
        DeploymentStep(6, "dashboard_activation", "dashboard", 2.0),
        DeploymentStep(7, "validation_dry_run", "validation", 4.0),
        DeploymentStep(8, "go_live_gate", "golive", 1.0),
    ],
    "regulated_financial_bundle": [
        DeploymentStep(1, "tenant_bootstrap", "setup", 2.0),
        DeploymentStep(2, "regulated_pack_install", "setup", 2.0),
        DeploymentStep(3, "financial_pack_install", "setup", 2.0),
        DeploymentStep(4, "shared_connector_activation", "connector", 6.0),
        DeploymentStep(5, "cross_pack_persona_provisioning", "persona", 2.0),
        DeploymentStep(6, "governance_configuration", "setup", 3.0),
        DeploymentStep(7, "regulatory_data_import", "import", 8.0),
        DeploymentStep(8, "financial_data_import", "import", 6.0),
        DeploymentStep(9, "stitched_workflow_validation", "validation", 4.0),
        DeploymentStep(10, "cross_pack_dashboard_activation", "dashboard", 3.0),
        DeploymentStep(11, "bundle_dry_run", "validation", 4.0),
        DeploymentStep(12, "go_live_gate", "golive", 1.0),
    ],
    "industrial_suite_bundle": [
        DeploymentStep(1, "tenant_bootstrap", "setup", 2.0),
        DeploymentStep(2, "factory_pack_install", "setup", 3.0),
        DeploymentStep(3, "supply_chain_pack_install", "setup", 2.0),
        DeploymentStep(4, "industrial_connector_activation", "connector", 8.0),
        DeploymentStep(5, "industrial_persona_provisioning", "persona", 2.0),
        DeploymentStep(6, "governance_configuration", "setup", 3.0),
        DeploymentStep(7, "factory_data_import", "import", 10.0),
        DeploymentStep(8, "supply_chain_data_import", "import", 8.0),
        DeploymentStep(9, "digital_twin_setup", "setup", 4.0),
        DeploymentStep(10, "stitched_workflow_validation", "validation", 6.0),
        DeploymentStep(11, "industrial_dashboard_activation", "dashboard", 4.0),
        DeploymentStep(12, "bundle_dry_run", "validation", 4.0),
        DeploymentStep(13, "go_live_gate", "golive", 1.0),
    ],
}

class DeploymentOrchestrator:
    """Orchestrates multi-bundle deployments from templates."""

    def __init__(self):
        self._active: dict[str, list[DeploymentStep]] = {}

    def start_deployment(self, customer_id: str, bundle_type: str) -> list[DeploymentStep]:
        if bundle_type not in BUNDLE_DEPLOYMENT_PLANS:
            raise ValueError(f"Unknown bundle: {bundle_type}")
        # Deep copy steps
        steps = [DeploymentStep(s.step, s.name, s.category, s.estimated_hours) for s in BUNDLE_DEPLOYMENT_PLANS[bundle_type]]
        self._active[customer_id] = steps
        return steps

    def complete_step(self, customer_id: str, step_num: int) -> DeploymentStep:
        if customer_id not in self._active:
            raise ValueError(f"No active deployment for {customer_id}")
        for s in self._active[customer_id]:
            if s.step == step_num:
                s.completed = True
                return s
        raise ValueError(f"Step {step_num} not found")

    def progress(self, customer_id: str) -> dict[str, Any]:
        steps = self._active.get(customer_id, [])
        done = sum(1 for s in steps if s.completed)
        total = len(steps)
        hours_done = sum(s.estimated_hours for s in steps if s.completed)
        hours_remaining = sum(s.estimated_hours for s in steps if not s.completed)
        return {
            "customer_id": customer_id,
            "steps_completed": done,
            "steps_total": total,
            "percent": round(done / total * 100, 1) if total else 0,
            "hours_completed": hours_done,
            "hours_remaining": hours_remaining,
            "next_step": next((s.name for s in steps if not s.completed), "all_complete"),
            "is_live": done == total,
        }

    @property
    def active_deployments(self) -> int:
        return len(self._active)

# 144B — Implementation Capacity
@dataclass
class CapacitySnapshot:
    team_size: int
    active_implementations: int
    total_hours_committed: float
    total_hours_available: float  # team_size * 40 * weeks
    specialist_bottlenecks: list[str] = field(default_factory=list)

    @property
    def utilization(self) -> float:
        return self.total_hours_committed / self.total_hours_available if self.total_hours_available else 0.0

    @property
    def status(self) -> str:
        u = self.utilization
        if u >= 0.9: return "overloaded"
        if u >= 0.7: return "busy"
        if u >= 0.4: return "healthy"
        return "underutilized"

# 144C — Support Automation
BUNDLE_INCIDENT_TEMPLATES = {
    "regulated_financial_bundle": {
        "connector_failure": "Check shared connector health → verify auth → restart → escalate if persistent",
        "cross_pack_workflow_break": "Verify stitched workflow config → check event spine → validate governance rules",
        "data_quality_issue": "Run import audit → check mapping → reconcile affected records",
    },
    "industrial_suite_bundle": {
        "connector_failure": "Check industrial connector health → verify OT network → restart → escalate",
        "production_line_halt": "Check factory engine state → verify supply chain impact → trigger continuity",
        "quality_hold": "Freeze affected batches → trace vendor materials → escalate quality review",
    },
}

# 144D — Margin Protection
@dataclass
class MarginRisk:
    customer_id: str
    bundle: str
    risk_type: str  # "underpriced", "over_customized", "high_hypercare", "connector_heavy", "support_mismatch"
    severity: str  # "low", "medium", "high"
    detail: str

class MarginProtector:
    """Flags margin-eroding deployments before go-live."""

    def __init__(self):
        self._risks: list[MarginRisk] = []

    def evaluate(self, customer_id: str, bundle: str, deal_price: float, estimated_hours: float, connector_count: int, customizations: int) -> list[MarginRisk]:
        risks = []

        # Underpriced check
        min_prices = {"regulated_financial_bundle": 4500.0, "industrial_suite_bundle": 6500.0, "single_pack": 2500.0}
        min_price = min_prices.get(bundle, 2500.0)
        if deal_price < min_price * 0.8:
            risks.append(MarginRisk(customer_id, bundle, "underpriced", "high", f"Deal at ${deal_price}/mo vs floor ${min_price*0.8}"))

        # Over-customized
        if customizations > 5:
            risks.append(MarginRisk(customer_id, bundle, "over_customized", "high" if customizations > 10 else "medium", f"{customizations} customizations requested"))

        # High hypercare
        if estimated_hours > 80:
            risks.append(MarginRisk(customer_id, bundle, "high_hypercare", "medium", f"{estimated_hours} estimated implementation hours"))

        # Connector heavy
        if connector_count > 7:
            risks.append(MarginRisk(customer_id, bundle, "connector_heavy", "medium", f"{connector_count} connectors requested"))

        self._risks.extend(risks)
        return risks

    @property
    def total_risks(self) -> int:
        return len(self._risks)

    def high_risks(self) -> list[MarginRisk]:
        return [r for r in self._risks if r.severity == "high"]

# 144E — Executive Delivery Dashboard
def delivery_dashboard(orchestrator: DeploymentOrchestrator, capacity: CapacitySnapshot, protector: MarginProtector) -> dict[str, Any]:
    return {
        "active_deployments": orchestrator.active_deployments,
        "capacity_status": capacity.status,
        "capacity_utilization": round(capacity.utilization, 3),
        "specialist_bottlenecks": capacity.specialist_bottlenecks,
        "margin_risks_total": protector.total_risks,
        "margin_risks_high": len(protector.high_risks()),
        "bundle_templates_available": len(BUNDLE_DEPLOYMENT_PLANS),
        "incident_templates_available": sum(len(v) for v in BUNDLE_INCIDENT_TEMPLATES.values()),
    }
