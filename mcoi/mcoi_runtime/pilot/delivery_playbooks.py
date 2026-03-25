"""Phase 135D — Pack-Specific Delivery Playbooks."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class PlaybookChecklist:
    phase: str
    items: tuple[str, ...]

@dataclass(frozen=True)
class DeliveryPlaybook:
    pack_domain: str
    pack_name: str
    total_phases: int
    phases: tuple[PlaybookChecklist, ...]

PLAYBOOKS = {
    "regulated_ops": DeliveryPlaybook("regulated_ops", "Regulated Operations Control Tower", 6, (
        PlaybookChecklist("connector_activation", ("Configure email SMTP/IMAP", "Set up SSO/SAML", "Connect document storage", "Connect ticketing system", "Configure reporting export", "Health-check all connectors")),
        PlaybookChecklist("data_import", ("Export historical cases from source", "Map fields to schema", "Run import with validation", "Review audit report", "Resolve conflicts", "Verify record counts")),
        PlaybookChecklist("training", ("Admin walkthrough (2 hours)", "Operator dashboard training (1 hour)", "Case/remediation workflow practice", "Evidence retrieval practice", "Copilot interaction practice", "Escalation procedure review")),
        PlaybookChecklist("go_live", ("All connectors green", "Data import complete", "All operators trained", "Governance rules reviewed", "SLOs configured", "Runbooks distributed", "Go-live sign-off from sponsor")),
        PlaybookChecklist("hypercare", ("Daily connector health check", "Daily intake queue review", "Weekly KPI review with operator lead", "Escalation on any blocker", "Copilot feedback collection")),
        PlaybookChecklist("first_30_days", ("Weekly success review", "Adoption metrics trending up", "Evidence completeness >= 80%", "Report generation tested", "Executive dashboard reviewed", "Feedback collected and triaged")),
    )),
    "enterprise_service": DeliveryPlaybook("enterprise_service", "Enterprise Service / IT Control Tower", 6, (
        PlaybookChecklist("connector_activation", ("Configure email", "Set up SSO", "Connect document storage", "Connect ITSM/ticketing", "Configure reporting export", "Health-check all")),
        PlaybookChecklist("data_import", ("Export incident history", "Map severity/priority fields", "Import with validation", "Verify SLA data", "Resolve duplicates")),
        PlaybookChecklist("training", ("Service desk operator training", "Manager dashboard walkthrough", "SLA tracking practice", "Customer impact view training", "Copilot practice")),
        PlaybookChecklist("go_live", ("All connectors green", "Import verified", "Operators trained", "SLOs configured", "Go-live approved")),
        PlaybookChecklist("hypercare", ("Daily SLA compliance check", "Incident volume monitoring", "Weekly review", "Escalation support")),
        PlaybookChecklist("first_30_days", ("MTTR trending down", "SLA breach rate monitored", "Dashboard adoption measured", "Feedback collected")),
    )),
    "financial_control": DeliveryPlaybook("financial_control", "Financial Control / Settlement", 6, (
        PlaybookChecklist("connector_activation", ("Configure email", "Set up SSO", "Connect document storage", "Connect billing/ERP", "Configure reporting export", "Health-check all")),
        PlaybookChecklist("data_import", ("Export invoice/billing history", "Map financial entities", "Import settlements", "Verify balances", "Resolve discrepancies")),
        PlaybookChecklist("training", ("Billing operator training", "Settlement analyst walkthrough", "Dispute handling practice", "Executive finance dashboard", "Copilot practice")),
        PlaybookChecklist("go_live", ("All connectors green", "Financial data verified", "Operators trained", "Governance rules active", "Go-live approved")),
        PlaybookChecklist("hypercare", ("Daily settlement reconciliation", "Dispute queue monitoring", "Weekly review", "Delinquency alerts verified")),
        PlaybookChecklist("first_30_days", ("DSO trending down", "Dispute resolution time measured", "Collections aging monitored", "Feedback collected")),
    )),
    "factory_quality": DeliveryPlaybook("factory_quality", "Factory Quality / Downtime / Throughput", 6, (
        PlaybookChecklist("connector_activation", ("Configure email", "Set up SSO", "Connect document storage", "Connect MES/SCADA if applicable", "Configure reporting export", "Health-check all")),
        PlaybookChecklist("data_import", ("Export work order history", "Map line/station/machine structure", "Import quality records", "Import downtime logs", "Verify yield data")),
        PlaybookChecklist("training", ("Line operator training", "Shift supervisor walkthrough", "Quality engineer workflow", "Maintenance lead procedures", "Plant manager dashboard", "Copilot practice")),
        PlaybookChecklist("go_live", ("All connectors green", "Production data verified", "Operators trained per shift", "Governance rules active", "Go-live approved by plant manager")),
        PlaybookChecklist("hypercare", ("Daily line status check", "Downtime event capture verified", "Quality check flow verified", "Weekly review with shift leads")),
        PlaybookChecklist("first_30_days", ("OEE baseline established", "Downtime tracking active", "Quality escape rate measured", "Maintenance response time tracked", "Feedback collected")),
    )),
}
