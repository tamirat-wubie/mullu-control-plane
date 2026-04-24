"""Phase 134B+C — Sales Motion Pack and Demo-to-Pilot Engine."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from datetime import datetime, timezone

@dataclass(frozen=True)
class SalesPlaybook:
    pack_domain: str
    outbound_narrative: str
    discovery_questions: tuple[str, ...]
    demo_script_steps: tuple[str, ...]
    objections: tuple[tuple[str, str], ...]  # (objection, response)
    pilot_proposal_template: str
    roi_levers: tuple[str, ...]

PLAYBOOKS = {
    "regulated_ops": SalesPlaybook(
        "regulated_ops",
        "Your compliance team spends weeks on evidence gathering and report generation. Our Control Tower reduces that to minutes with governed symbolic intelligence.",
        ("How do you track remediation items today?", "How long does evidence collection take?", "How many audit cycles per year?", "What tools do you use for reporting?"),
        ("Show intake queue", "Create a case", "Retrieve evidence bundle", "Generate reporting packet", "Copilot explains a finding"),
        (("How is this different from our GRC tool?", "We augment, not replace. We add symbolic intelligence-driven evidence retrieval, governed copilot, and automated reporting on top of your existing data."),
         ("What about data residency?", "Fully tenant-isolated. Data stays in your environment. We support on-prem and private cloud."),
         ("Can we customize governance rules?", "Yes. Constitutional governance is fully configurable per tenant with precedence levels.")),
        "Dear [Sponsor], Following our discussion, I'd like to propose a 6-week pilot of the Regulated Operations Control Tower...",
        ("40% reduction in compliance cycle time", "95% evidence completeness (from ~60%)", "Report generation in minutes (from days)", "Fewer audit findings"),
    ),
    "enterprise_service": SalesPlaybook(
        "enterprise_service",
        "Your service desk resolves thousands of incidents but lacks real-time visibility into SLA compliance and customer impact. Our IT Control Tower changes that.",
        ("What's your current MTTR?", "How do you track SLA compliance?", "What's your escalation process?", "How visible are service issues to executives?"),
        ("Log an incident", "Show SLA tracking", "Customer impact view", "Copilot drafts resolution summary"),
        (("How does this compare to ServiceNow?", "We complement ITSM tools with symbolic intelligence-driven case management, evidence retrieval, and governed copilot."),
         ("Can it handle our ticket volume?", "Yes. The distributed execution fabric handles scale. We've tested with thousands of concurrent operations.")),
        "Dear [Sponsor], I'd like to propose a 6-week pilot of the Enterprise Service Control Tower...",
        ("35% reduction in MTTR", "SLA breach rate from 15% to 3%", "Real-time executive visibility", "Faster incident resolution"),
    ),
    "financial_control": SalesPlaybook(
        "financial_control",
        "Your finance team spends days on dispute resolution and weeks preparing for audits. Our Financial Control Tower automates settlement tracking and evidence assembly.",
        ("What's your current DSO?", "How do you handle invoice disputes?", "How long does audit prep take?", "What's your collections process?"),
        ("Show dispute flow", "Settlement tracking board", "Delinquency detection", "Executive finance dashboard"),
        (("How does this integrate with our ERP?", "Via standard connectors. We integrate with major ERPs through API and file-based interfaces."),
         ("What about SOX compliance?", "Built-in constitutional governance with audit trails. Every action is traceable and evidence-backed.")),
        "Dear [Sponsor], I'd like to propose a 6-week pilot of the Financial Control Tower...",
        ("20% reduction in DSO", "Dispute resolution from 30 days to 10", "Audit prep from weeks to hours", "Reduced revenue leakage"),
    ),
    "factory_quality": SalesPlaybook(
        "factory_quality",
        "Your plant loses production hours to unplanned downtime and quality escapes. Our Factory Quality Tower provides digital twin visibility and governed process control.",
        ("What's your unplanned downtime rate?", "How do you track quality nonconformances?", "What's your maintenance response time?", "How do you measure OEE?"),
        ("Work order on line", "Downtime capture", "Quality failure → rework", "Digital twin view", "Process deviation alert"),
        (("How does this connect to our MES/SCADA?", "Via standard connectors. We integrate with industrial systems through OPC-UA, MQTT, and REST APIs."),
         ("What about OT network isolation?", "Fully supported. Edge deployment with air-gapped OT network integration.")),
        "Dear [Sponsor], I'd like to propose an 8-week pilot of the Factory Quality Tower...",
        ("30% reduction in unplanned downtime", "50% reduction in quality escape rate", "Maintenance response from hours to minutes", "Improved OEE visibility"),
    ),
}

@dataclass
class FunnelStageEntry:
    account_id: str
    pack: str
    stage: str  # "outreach", "meeting", "demo", "pilot_proposed", "pilot_accepted", "pilot_completed", "converted"
    entered_at: str = ""

    def __post_init__(self):
        if not self.entered_at:
            object.__setattr__(self, "entered_at", datetime.now(timezone.utc).isoformat())

class DemoToPilotEngine:
    """Tracks the real sales funnel from outreach to conversion."""

    def __init__(self):
        self._entries: list[FunnelStageEntry] = []

    def record(self, account_id: str, pack: str, stage: str) -> FunnelStageEntry:
        entry = FunnelStageEntry(account_id, pack, stage)
        self._entries.append(entry)
        return entry

    def stage_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for e in self._entries:
            counts[e.stage] = counts.get(e.stage, 0) + 1
        return counts

    def by_pack(self, pack: str) -> list[FunnelStageEntry]:
        return [e for e in self._entries if e.pack == pack]

    def conversion_rate(self, from_stage: str, to_stage: str) -> float:
        from_count = sum(1 for e in self._entries if e.stage == from_stage)
        to_count = sum(1 for e in self._entries if e.stage == to_stage)
        return to_count / from_count if from_count else 0.0

    @property
    def total_entries(self) -> int:
        return len(self._entries)

    def summary(self) -> dict[str, Any]:
        return {
            "total_entries": self.total_entries,
            "stage_counts": self.stage_counts(),
            "demo_to_pilot": round(self.conversion_rate("demo", "pilot_proposed"), 3),
            "pilot_to_paid": round(self.conversion_rate("pilot_completed", "converted"), 3),
        }
