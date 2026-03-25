"""Phase 127B — Pilot Charter Document."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from mcoi_runtime.pilot.customer_profile import PilotCustomerProfile

@dataclass(frozen=True)
class PilotCharter:
    charter_id: str
    customer: PilotCustomerProfile
    scope: tuple[str, ...] = ("intake", "case_management", "approvals", "evidence", "reporting", "operator_dashboard", "executive_dashboard", "copilot")
    excluded_scope: tuple[str, ...] = ("multimodal_voice", "self_tuning", "factory", "research", "blockchain")
    duration_weeks: int = 6
    success_metrics: tuple[str, ...] = (
        "connector_uptime >= 99%",
        "cases_completed >= 10",
        "evidence_bundles_generated >= 5",
        "reports_generated >= 3",
        "operator_satisfaction >= 7/10",
        "executive_satisfaction >= 7/10",
    )
    conversion_criteria: tuple[str, ...] = (
        "operators_actively_using",
        "executive_sees_value",
        "evidence_and_reporting_trusted",
        "support_burden_acceptable",
        "connectors_stable",
    )
    reporting_cadence: str = "weekly"

    def stakeholder_list(self) -> dict[str, str]:
        return {
            "executive_sponsor": self.customer.executive_sponsor,
            "operator_lead": self.customer.operator_lead,
            "organization": self.customer.organization_name,
        }

    def kickoff_agenda(self) -> tuple[str, ...]:
        return (
            "1. Welcome and introductions",
            "2. Pilot scope and boundaries",
            "3. Success metrics walkthrough",
            "4. Timeline and milestones",
            "5. Connector setup plan",
            "6. Data migration plan",
            "7. Weekly review schedule",
            "8. Support and escalation paths",
            "9. Go-live criteria",
            "10. Q&A",
        )

    def weekly_review_template(self) -> dict[str, Any]:
        return {
            "sections": [
                "KPI dashboard review",
                "Connector health status",
                "Workflow completion metrics",
                "Open issues and blockers",
                "Operator feedback highlights",
                "Next week priorities",
            ],
            "attendees": ["operator_lead", "executive_sponsor", "platform_team"],
            "duration_minutes": 30,
        }
