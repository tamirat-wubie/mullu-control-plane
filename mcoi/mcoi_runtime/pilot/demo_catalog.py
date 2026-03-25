"""Phase 133B — Demo Catalog for all 4 products."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from mcoi_runtime.pilot.demo_generator import DemoTenantGenerator
from mcoi_runtime.pilot.enterprise_service_pack import EnterpriseServiceDemoGenerator
from mcoi_runtime.pilot.financial_control_pack import FinancialControlDemoGenerator
from mcoi_runtime.pilot.factory_quality_pack import FactoryQualityDemoGenerator

@dataclass(frozen=True)
class DemoFlow:
    product: str
    quick_flow_minutes: int
    deep_flow_minutes: int
    key_moments: tuple[str, ...]
    roi_narrative: str
    top_objections: tuple[str, ...]

DEMO_FLOWS = (
    DemoFlow("Regulated Operations Control Tower", 5, 20,
        ("Intake a compliance issue", "Show evidence retrieval", "Generate reporting packet", "Copilot explains finding"),
        "Reduce compliance cycle time by 40%, evidence completeness from 60% to 95%, report generation from days to minutes",
        ("How does this integrate with our existing GRC?", "What about data residency?", "Can we customize governance rules?")),
    DemoFlow("Enterprise Service / IT Control Tower", 5, 20,
        ("Log a service incident", "Show SLA tracking", "Customer impact view", "Copilot drafts resolution"),
        "Reduce mean time to resolution by 35%, SLA breach rate from 15% to 3%, visibility from quarterly to real-time",
        ("How does this compare to ServiceNow?", "Can it handle our ticket volume?", "What about ITIL alignment?")),
    DemoFlow("Financial Control / Settlement", 5, 20,
        ("Show invoice dispute flow", "Settlement tracking board", "Delinquency detection", "Executive finance dashboard"),
        "Reduce DSO by 20%, dispute resolution time from 30 days to 10, audit prep from weeks to hours",
        ("How does this integrate with our ERP?", "What about SOX compliance?", "Can it handle multi-currency?")),
    DemoFlow("Factory Quality / Downtime / Throughput", 5, 20,
        ("Work order on line", "Downtime capture", "Quality failure → rework flow", "Digital twin view", "Process deviation alert"),
        "Reduce unplanned downtime by 30%, quality escape rate by 50%, maintenance response from hours to minutes",
        ("How does this connect to our MES/SCADA?", "What about OT network isolation?", "Can it handle our production volume?")),
)

class DemoCatalog:
    """One-click demo generation for all 4 products."""

    GENERATORS = {
        "regulated_ops": DemoTenantGenerator,
        "enterprise_service": EnterpriseServiceDemoGenerator,
        "financial_control": FinancialControlDemoGenerator,
        "factory_quality": FactoryQualityDemoGenerator,
    }

    def generate_demo(self, pack_domain: str, tenant_id: str | None = None) -> dict[str, Any]:
        if pack_domain not in self.GENERATORS:
            raise ValueError(f"Unknown pack: {pack_domain}. Available: {list(self.GENERATORS.keys())}")
        gen = self.GENERATORS[pack_domain]()
        tid = tenant_id or f"demo-{pack_domain}-001"
        return gen.generate(tid)

    def generate_all(self) -> dict[str, dict[str, Any]]:
        return {domain: self.generate_demo(domain) for domain in self.GENERATORS}
