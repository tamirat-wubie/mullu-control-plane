"""Phase 125D — Onboarding Flow Definition."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class OnboardingStep:
    step_number: int
    title: str
    description: str
    category: str  # "setup", "connect", "import", "activate", "verify"
    estimated_minutes: int

ONBOARDING_FLOW = (
    OnboardingStep(1, "Create Tenant", "Set up your organization's tenant with name, domain, and admin credentials", "setup", 5),
    OnboardingStep(2, "Configure Workspaces", "Create workspaces for teams/departments that will use the system", "setup", 10),
    OnboardingStep(3, "Set Up Identity/SSO", "Connect your identity provider (SAML/OIDC) for single sign-on", "connect", 15),
    OnboardingStep(4, "Connect Email", "Configure email integration for intake notifications and approvals", "connect", 10),
    OnboardingStep(5, "Connect Document Storage", "Link document/file storage for evidence and reporting", "connect", 10),
    OnboardingStep(6, "Connect Ticketing", "Integrate with your helpdesk/ticketing system for case sync", "connect", 15),
    OnboardingStep(7, "Configure Reporting Export", "Set up export destination for regulatory reporting packets", "connect", 10),
    OnboardingStep(8, "Import Historical Data", "Load existing cases, remediations, and evidence from source systems", "import", 30),
    OnboardingStep(9, "Assign Roles and Personas", "Configure operator, executive, investigator, and compliance personas", "activate", 15),
    OnboardingStep(10, "Configure Governance Rules", "Set up constitutional policies for your organization", "activate", 20),
    OnboardingStep(11, "Activate Dashboards", "Enable operator and executive dashboards with your data", "activate", 10),
    OnboardingStep(12, "Run First Case", "Walk through creating a case, adding evidence, and generating a report", "verify", 20),
    OnboardingStep(13, "Verify Copilot", "Test the governed copilot with real questions about your data", "verify", 10),
    OnboardingStep(14, "Go-Live Checklist", "Review all SLOs, runbooks, and acceptance criteria before go-live", "verify", 15),
)

TOTAL_ESTIMATED_MINUTES = sum(s.estimated_minutes for s in ONBOARDING_FLOW)

def onboarding_summary() -> dict[str, Any]:
    return {
        "total_steps": len(ONBOARDING_FLOW),
        "total_estimated_minutes": TOTAL_ESTIMATED_MINUTES,
        "categories": {
            "setup": sum(1 for s in ONBOARDING_FLOW if s.category == "setup"),
            "connect": sum(1 for s in ONBOARDING_FLOW if s.category == "connect"),
            "import": sum(1 for s in ONBOARDING_FLOW if s.category == "import"),
            "activate": sum(1 for s in ONBOARDING_FLOW if s.category == "activate"),
            "verify": sum(1 for s in ONBOARDING_FLOW if s.category == "verify"),
        },
    }
