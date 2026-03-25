"""Phase 151 — Government / Sovereign Deployment Track."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

# 151A — Sovereign Deployment Profiles
@dataclass(frozen=True)
class SovereignProfile:
    profile_id: str
    name: str
    deployment_model: str  # "sovereign_cloud", "restricted_network", "on_prem", "partner_operated"
    data_residency: str
    allowed_connectors: tuple[str, ...]
    blocked_connectors: tuple[str, ...]
    export_restricted: bool
    break_glass_policy: str  # "dual_approval", "audit_only", "disabled"
    update_path: str  # "managed", "customer_controlled", "air_gapped"
    support_path: str  # "standard", "restricted", "on_site", "partner_only"

SOVEREIGN_PROFILES = {
    "sovereign_cloud": SovereignProfile(
        "sov-cloud", "Sovereign Cloud", "sovereign_cloud", "local_sovereign",
        ("email", "identity_sso", "document_storage", "ticketing", "reporting_export"),
        ("third_party_saas", "public_api_integrations"),
        True, "dual_approval", "managed", "restricted",
    ),
    "restricted_network": SovereignProfile(
        "sov-restricted", "Restricted Network", "restricted_network", "local_sovereign",
        ("email", "identity_sso", "document_storage"),
        ("ticketing", "reporting_export", "third_party_saas", "public_api_integrations", "chat", "voice"),
        True, "dual_approval", "air_gapped", "on_site",
    ),
    "on_prem": SovereignProfile(
        "sov-onprem", "On-Premises", "on_prem", "customer_controlled",
        ("email", "identity_sso", "document_storage", "ticketing", "reporting_export"),
        ("cloud_saas",),
        False, "audit_only", "customer_controlled", "on_site",
    ),
    "partner_operated": SovereignProfile(
        "sov-partner", "Partner-Operated Public Sector", "partner_operated", "partner_sovereign",
        ("email", "identity_sso", "document_storage", "ticketing", "reporting_export"),
        ("direct_cloud",),
        True, "dual_approval", "managed", "partner_only",
    ),
}

# 151B — Government Trust Bundle
@dataclass(frozen=True)
class GovernmentTrustBundle:
    bundle_id: str
    identity_mode: str  # "piv_cac", "saml_mfa", "oidc_mfa", "certificate_based"
    audit_export_format: str  # "json_signed", "xml_sealed", "pdf_certified"
    evidence_immutability: bool
    approval_minimum: str  # "dual_approval", "quorum_3", "unanimous"
    copilot_mode: str  # "full", "restricted_no_generation", "explain_only", "disabled"
    retention_override_days: int
    legal_hold_default: bool

TRUST_BUNDLES = {
    "standard_gov": GovernmentTrustBundle(
        "trust-std-gov", "saml_mfa", "json_signed", True, "dual_approval", "restricted_no_generation", 2555, True,
    ),
    "high_security": GovernmentTrustBundle(
        "trust-high-sec", "piv_cac", "xml_sealed", True, "unanimous", "explain_only", 3650, True,
    ),
    "classified_adjacent": GovernmentTrustBundle(
        "trust-classified", "certificate_based", "pdf_certified", True, "unanimous", "disabled", 3650, True,
    ),
    "partner_gov": GovernmentTrustBundle(
        "trust-partner-gov", "oidc_mfa", "json_signed", True, "quorum_3", "restricted_no_generation", 2555, False,
    ),
}

# 151C — Procurement/Compliance Artifacts
COMPLIANCE_ARTIFACTS = {
    "security_control_matrix": {
        "title": "Security and Access Control Matrix",
        "sections": ("identity_management", "access_control", "audit_logging", "encryption", "data_residency", "incident_response"),
    },
    "data_residency_statement": {
        "title": "Data Residency and Boundary Statement",
        "sections": ("storage_locations", "processing_boundaries", "cross_border_restrictions", "retention_policy", "deletion_guarantees"),
    },
    "deployment_architecture": {
        "title": "Deployment Architecture Variants",
        "sections": ("sovereign_cloud", "restricted_network", "on_premises", "partner_operated", "hybrid"),
    },
    "support_model": {
        "title": "Support and Escalation Model",
        "sections": ("tiers", "response_times", "escalation_path", "on_site_support", "break_glass_procedure"),
    },
    "audit_export": {
        "title": "Audit and Evidence Export Specification",
        "sections": ("export_formats", "signing_verification", "chain_of_custody", "retention_compliance", "legal_hold"),
    },
    "product_governance_summary": {
        "title": "Product Governance and Constitutional Controls",
        "sections": ("constitutional_rules", "policy_precedence", "emergency_modes", "override_tracking", "audit_trail"),
    },
}

# 151D — Restricted Connector Strategy
CONNECTOR_CLASSIFICATION = {
    "allowed_default": ("email", "identity_sso", "document_storage"),
    "requires_approval": ("ticketing", "reporting_export", "calendar"),
    "blocked_sovereign": ("third_party_saas", "public_api_integrations", "chat_saas", "voice_saas"),
    "offline_alternatives": {
        "ticketing": "manual_ticket_import",
        "reporting_export": "secure_file_transfer",
        "chat": "internal_messaging_only",
        "voice": "phone_bridge_manual",
    },
}

# 151E — Sovereign Pilot Path
SOVEREIGN_PILOT_STEPS = (
    {"step": 1, "name": "qualification", "description": "Verify sovereign eligibility and requirements"},
    {"step": 2, "name": "profile_selection", "description": "Select deployment profile (sovereign cloud, restricted, on-prem, partner)"},
    {"step": 3, "name": "trust_bundle_selection", "description": "Select government trust bundle"},
    {"step": 4, "name": "restricted_bootstrap", "description": "Bootstrap tenant with sovereign constraints"},
    {"step": 5, "name": "connector_verification", "description": "Verify only allowed connectors are active"},
    {"step": 6, "name": "data_boundary_verification", "description": "Verify data residency and boundary rules"},
    {"step": 7, "name": "case_workflow_validation", "description": "Run case workflow in restricted mode"},
    {"step": 8, "name": "audit_export_validation", "description": "Generate and verify audit/evidence export"},
    {"step": 9, "name": "security_review", "description": "Complete security and compliance review"},
    {"step": 10, "name": "go_live_readiness", "description": "Final sovereign go-live checklist"},
)

@dataclass
class SovereignPilotProgress:
    tenant_id: str
    profile_id: str
    trust_bundle_id: str
    completed_steps: list[int] = field(default_factory=list)

    def complete_step(self, step: int) -> None:
        if step not in self.completed_steps:
            self.completed_steps.append(step)

    @property
    def completion_rate(self) -> float:
        return len(self.completed_steps) / len(SOVEREIGN_PILOT_STEPS) if SOVEREIGN_PILOT_STEPS else 0.0

    @property
    def is_ready(self) -> bool:
        return len(self.completed_steps) == len(SOVEREIGN_PILOT_STEPS)

    @property
    def next_step(self) -> str:
        for s in SOVEREIGN_PILOT_STEPS:
            if s["step"] not in self.completed_steps:
                return s["name"]
        return "all_complete"
