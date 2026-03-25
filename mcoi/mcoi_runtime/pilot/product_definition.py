"""Phase 125A — Product Definition for Regulated Operations Control Tower v1."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

PRODUCT_NAME = "Regulated Operations Control Tower"
PRODUCT_VERSION = "1.0.0"
PRODUCT_TAGLINE = "Governed intake, case management, evidence, reporting, and AI-assisted operations for regulated enterprises."

@dataclass(frozen=True)
class CapabilityEntry:
    name: str
    description: str
    in_scope: bool
    category: str  # "core", "premium", "add_on"

V1_CAPABILITIES = (
    CapabilityEntry("intake", "Service request intake and queue management", True, "core"),
    CapabilityEntry("case_management", "Case lifecycle, investigation, and remediation tracking", True, "core"),
    CapabilityEntry("approvals", "Human workflow approvals with quorum/unanimous/override modes", True, "core"),
    CapabilityEntry("evidence", "Evidence retrieval, bundles, and knowledge query", True, "core"),
    CapabilityEntry("reporting", "Regulatory and executive reporting packet generation", True, "core"),
    CapabilityEntry("operator_dashboard", "Operator workspace with queues, worklists, and panels", True, "core"),
    CapabilityEntry("executive_dashboard", "Executive summary, KPIs, and risk overview", True, "core"),
    CapabilityEntry("governed_copilot", "AI assistant with persona, evidence-backed answers, governance guardrails", True, "core"),
    CapabilityEntry("constitutional_governance", "Platform-wide policy rules, emergency modes, override tracking", True, "core"),
    CapabilityEntry("observability", "Metrics, traces, anomaly detection across all operations", True, "core"),
    # Out of scope for v1
    CapabilityEntry("multimodal_voice", "Voice/streaming interaction with the copilot", False, "add_on"),
    CapabilityEntry("self_tuning", "Automated parameter and policy improvement proposals", False, "premium"),
    CapabilityEntry("factory_quality", "Factory/production quality management", False, "add_on"),
    CapabilityEntry("research_workflows", "Research hypothesis/experiment management", False, "add_on"),
    CapabilityEntry("blockchain_settlement", "Verifiable settlement proofs on ledger", False, "premium"),
)

IN_SCOPE = tuple(c for c in V1_CAPABILITIES if c.in_scope)
OUT_OF_SCOPE = tuple(c for c in V1_CAPABILITIES if not c.in_scope)

DEPLOYMENT_PREREQUISITES = (
    "Python 3.11+",
    "Network access to connector endpoints (email, SSO, storage, ticketing, reporting)",
    "Tenant administrator credentials",
    "Initial data export from source systems (CSV/JSON)",
)

INTEGRATION_PREREQUISITES = (
    "Email: SMTP/IMAP endpoint with service account",
    "Identity/SSO: SAML or OIDC provider with metadata URL",
    "Document Storage: S3-compatible or Azure Blob endpoint with API key",
    "Ticketing: REST API endpoint with OAuth2 credentials",
    "Reporting Export: SFTP or REST API endpoint",
)
