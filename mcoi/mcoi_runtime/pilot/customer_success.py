"""Phase 128C — Customer Success / Support Operating Motion."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

ADMIN_ONBOARDING_CHECKLIST = (
    "Tenant created and verified",
    "Workspaces configured per team structure",
    "Admin users provisioned with SSO",
    "Constitutional governance rules reviewed and activated",
    "Regulated ops pack deployed and validated",
    "Connector credentials configured and health-checked",
    "Data migration completed and audit report reviewed",
    "Backup/restore procedure verified",
    "Escalation contacts documented",
    "Go-live checklist signed off",
)

OPERATOR_ENABLEMENT_CHECKLIST = (
    "Account provisioned and persona assigned",
    "Dashboard walkthrough completed",
    "Intake queue workflow practiced",
    "Case creation and remediation flow practiced",
    "Approval workflow practiced",
    "Evidence retrieval and bundle assembly practiced",
    "Reporting packet generation practiced",
    "Copilot interaction practiced (explain, draft, escalate)",
    "Escalation procedure reviewed",
    "First real case completed with supervision",
)

WEEKLY_SUCCESS_REVIEW = {
    "sections": [
        "KPI dashboard review (cases, remediations, approvals, evidence, reports)",
        "Connector health and reliability",
        "Operator adoption metrics (dashboard views, copilot queries)",
        "Open issues and friction points",
        "Support ticket summary",
        "Feedback highlights (operator + executive)",
        "Action items for next week",
    ],
    "attendees": ["customer_operator_lead", "customer_executive_sponsor", "platform_csm", "platform_engineering_if_needed"],
    "cadence": "weekly",
    "duration_minutes": 30,
}

INCIDENT_WORKFLOW = (
    "1. Operator reports issue via support channel",
    "2. Support team triages and assigns severity (critical/high/medium/low)",
    "3. SLA timer starts per support tier",
    "4. Platform team investigates (connector health, engine state, logs)",
    "5. Workaround applied if available",
    "6. Root cause identified and fix deployed",
    "7. Customer notified of resolution",
    "8. Post-incident review if severity >= high",
)

ESCALATION_PATH = (
    "Level 1: Platform support team (all issues)",
    "Level 2: Platform engineering (connector failures, data issues)",
    "Level 3: Platform architecture (governance, engine, performance)",
    "Level 4: Executive escalation (SLA breach, customer satisfaction)",
)

RENEWAL_REVIEW = {
    "timing": "60 days before contract renewal",
    "review_items": [
        "Usage metrics vs expectations",
        "SLA compliance history",
        "Support ticket volume and resolution quality",
        "Operator and executive satisfaction scores",
        "Feature requests and roadmap alignment",
        "Expansion opportunities (more workspaces, add-ons, second pack)",
        "Pricing review and adjustment if needed",
    ],
    "decision_options": ["renew_same_tier", "upgrade_tier", "add_capabilities", "churn_risk_intervention"],
}
