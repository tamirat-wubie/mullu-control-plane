"""Phase 126A — Pilot Customer Profile and Selection Criteria."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

@dataclass(frozen=True)
class PilotCustomerProfile:
    customer_id: str
    organization_name: str
    industry: str
    team_type: str  # "compliance", "audit", "service_governance", "remediation"
    operator_count: int
    executive_sponsor: str
    operator_lead: str
    historical_case_count: int
    pain_points: tuple[str, ...] = ()
    connector_surface: tuple[str, ...] = ()

SELECTION_CRITERIA = {
    "clear_pain": "Team has visible pain around approvals, remediation tracking, evidence gathering, or reporting",
    "manageable_connectors": "Needs <= 5 connector types for the pilot",
    "sponsoring_operator": "Has one named operator lead who will drive daily adoption",
    "executive_stakeholder": "Has one executive who cares about the outcome",
    "historical_data": "Has >= 20 historical cases/remediations available for backfill",
    "pilot_tolerance": "Willing to run a bounded 4-12 week pilot",
}

def evaluate_fit(profile: PilotCustomerProfile) -> dict[str, Any]:
    score = 0
    checks = {}
    checks["has_pain"] = len(profile.pain_points) >= 2
    if checks["has_pain"]: score += 1
    checks["manageable_connectors"] = len(profile.connector_surface) <= 5
    if checks["manageable_connectors"]: score += 1
    checks["has_operator_lead"] = bool(profile.operator_lead)
    if checks["has_operator_lead"]: score += 1
    checks["has_executive_sponsor"] = bool(profile.executive_sponsor)
    if checks["has_executive_sponsor"]: score += 1
    checks["has_history"] = profile.historical_case_count >= 20
    if checks["has_history"]: score += 1
    checks["adequate_team"] = profile.operator_count >= 3
    if checks["adequate_team"]: score += 1
    return {"score": score, "max": 6, "fit": "strong" if score >= 5 else "moderate" if score >= 3 else "weak", "checks": checks}
