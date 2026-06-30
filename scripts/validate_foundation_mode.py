#!/usr/bin/env python3
"""Validate the repository Foundation Mode posture.

Purpose: keep current public-copy and operator guidance aligned with the
solo-founder Foundation Mode boundary.
Governance scope: Foundation Mode, public copy, pilot/access claims, deployment
restraint, and current posture docs.
Dependencies: repository-local Markdown, HTML, and Python guidance files.
Invariants:
  - Current guidance remains local-proof-first.
  - Customer access, pilot access, beta invitation, waitlist, endpoint-readiness,
    and deployment claims remain blocked unless explicitly promoted by evidence.
  - Historical evidence files are not rewritten or treated as current guidance.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]

FOUNDATION_CORE_GUIDANCE_SURFACES = (
    "AGENTS.md",
    "README.md",
    "docs/START_HERE.md",
    "docs/CURRENT_READINESS_SNAPSHOT.md",
    "docs/FOUNDATION_MODE.md",
    "docs/FOUNDATION_PREREQUISITES.md",
    "docs/WEBSITE_UPDATE_CHECKLIST.md",
    "docs/PUBLIC_NAMING_REVIEW_PACKET.md",
    "docs/explain/PLAIN_ENGLISH.md",
    "site/mullu/index.html",
)

REQUIRED_PHRASES_BY_FILE = {
    "AGENTS.md": (
        "Assume `Foundation Mode` unless the user or a signed status witness explicitly",
        "before deployment, company formation, customer access",
        "Do not push toward public deployment, paid launch, LLC formation",
    ),
    "README.md": (
        "## Current Operating Posture: Foundation Mode",
        "private, local-first",
        "See [`docs/FOUNDATION_MODE.md`](docs/FOUNDATION_MODE.md)",
        "[`docs/FOUNDATION_PREREQUISITES.md`](docs/FOUNDATION_PREREQUISITES.md)",
        "[`docs/FOUNDATION_OPERATOR_READINESS_BOUNDARY.md`](docs/FOUNDATION_OPERATOR_READINESS_BOUNDARY.md)",
        "[`docs/FOUNDATION_SOLO_DAILY_LOOP_BOUNDARY.md`](docs/FOUNDATION_SOLO_DAILY_LOOP_BOUNDARY.md)",
        "[`docs/FOUNDATION_LEARNING_PATH_BOUNDARY.md`](docs/FOUNDATION_LEARNING_PATH_BOUNDARY.md)",
        "[`docs/FOUNDATION_COMMUNITY_NETWORK_BOUNDARY.md`](docs/FOUNDATION_COMMUNITY_NETWORK_BOUNDARY.md)",
        "[`docs/FOUNDATION_ARCHITECTURE_MAP_BOUNDARY.md`](docs/FOUNDATION_ARCHITECTURE_MAP_BOUNDARY.md)",
        "[`docs/FOUNDATION_SYSTEM_BOUNDARY_INVENTORY_BOUNDARY.md`](docs/FOUNDATION_SYSTEM_BOUNDARY_INVENTORY_BOUNDARY.md)",
        "[`docs/FOUNDATION_MODULE_INVENTORY_BOUNDARY.md`](docs/FOUNDATION_MODULE_INVENTORY_BOUNDARY.md)",
        "[`docs/FOUNDATION_COMPONENT_CONTRACT_BOUNDARY.md`](docs/FOUNDATION_COMPONENT_CONTRACT_BOUNDARY.md)",
        "[`docs/FOUNDATION_INTERFACE_MAP_BOUNDARY.md`](docs/FOUNDATION_INTERFACE_MAP_BOUNDARY.md)",
        "[`docs/FOUNDATION_DEPENDENCY_GRAPH_BOUNDARY.md`](docs/FOUNDATION_DEPENDENCY_GRAPH_BOUNDARY.md)",
        "[`docs/FOUNDATION_INVARIANT_MAP_BOUNDARY.md`](docs/FOUNDATION_INVARIANT_MAP_BOUNDARY.md)",
        "[`docs/FOUNDATION_HAZARD_MAP_BOUNDARY.md`](docs/FOUNDATION_HAZARD_MAP_BOUNDARY.md)",
        "[`docs/FOUNDATION_PROOF_REFERENCE_BOUNDARY.md`](docs/FOUNDATION_PROOF_REFERENCE_BOUNDARY.md)",
        "[`docs/FOUNDATION_GAP_REGISTER_BOUNDARY.md`](docs/FOUNDATION_GAP_REGISTER_BOUNDARY.md)",
        "[`docs/FOUNDATION_DIFF_REVIEW_BOUNDARY.md`](docs/FOUNDATION_DIFF_REVIEW_BOUNDARY.md)",
        "[`docs/FOUNDATION_CHANGE_HANDOFF_BOUNDARY.md`](docs/FOUNDATION_CHANGE_HANDOFF_BOUNDARY.md)",
        "[`docs/FOUNDATION_LOCAL_WORKSTATION_BOUNDARY.md`](docs/FOUNDATION_LOCAL_WORKSTATION_BOUNDARY.md)",
        "[`docs/FOUNDATION_DOCUMENTATION_BOUNDARY.md`](docs/FOUNDATION_DOCUMENTATION_BOUNDARY.md)",
        "[`docs/FOUNDATION_PLAIN_LANGUAGE_STATUS_BOUNDARY.md`](docs/FOUNDATION_PLAIN_LANGUAGE_STATUS_BOUNDARY.md)",
        "[`docs/FOUNDATION_ACCESSIBILITY_LANGUAGE_BOUNDARY.md`](docs/FOUNDATION_ACCESSIBILITY_LANGUAGE_BOUNDARY.md)",
        "[`docs/FOUNDATION_CAPABILITY_ROADMAP_BOUNDARY.md`](docs/FOUNDATION_CAPABILITY_ROADMAP_BOUNDARY.md)",
        "[`docs/FOUNDATION_AGENTIC_MANAGEMENT_BOUNDARY.md`](docs/FOUNDATION_AGENTIC_MANAGEMENT_BOUNDARY.md)",
        "[`docs/FOUNDATION_OPERATIONS_RUNBOOK_BOUNDARY.md`](docs/FOUNDATION_OPERATIONS_RUNBOOK_BOUNDARY.md)",
        "[`docs/FOUNDATION_CLAIM_BOUNDARY.md`](docs/FOUNDATION_CLAIM_BOUNDARY.md)",
        "[`docs/FOUNDATION_WEBSITE_POSTURE_BOUNDARY.md`](docs/FOUNDATION_WEBSITE_POSTURE_BOUNDARY.md)",
        "[`docs/FOUNDATION_RESEARCH_NOTEBOOK_BOUNDARY.md`](docs/FOUNDATION_RESEARCH_NOTEBOOK_BOUNDARY.md)",
        "[`docs/FOUNDATION_MARKET_RESEARCH_BOUNDARY.md`](docs/FOUNDATION_MARKET_RESEARCH_BOUNDARY.md)",
        "[`docs/FOUNDATION_EVIDENCE_LEDGER_BOUNDARY.md`](docs/FOUNDATION_EVIDENCE_LEDGER_BOUNDARY.md)",
        "[`docs/FOUNDATION_DECISION_JOURNAL_BOUNDARY.md`](docs/FOUNDATION_DECISION_JOURNAL_BOUNDARY.md)",
        "[`docs/FOUNDATION_NEXT_ACTION_BOUNDARY.md`](docs/FOUNDATION_NEXT_ACTION_BOUNDARY.md)",
        "[`docs/FOUNDATION_TEST_EVIDENCE_BOUNDARY.md`](docs/FOUNDATION_TEST_EVIDENCE_BOUNDARY.md)",
        "[`docs/FOUNDATION_SOURCE_CONTROL_BOUNDARY.md`](docs/FOUNDATION_SOURCE_CONTROL_BOUNDARY.md)",
        "[`docs/FOUNDATION_SOURCE_CONTROL_REVIEW_CHECKLIST_BOUNDARY.md`](docs/FOUNDATION_SOURCE_CONTROL_REVIEW_CHECKLIST_BOUNDARY.md)",
        "[`docs/FOUNDATION_LOCAL_PROOF_THREAD.md`](docs/FOUNDATION_LOCAL_PROOF_THREAD.md)",
        "[`docs/FOUNDATION_SECRETS_CREDENTIALS_BOUNDARY.md`](docs/FOUNDATION_SECRETS_CREDENTIALS_BOUNDARY.md)",
        "[`docs/FOUNDATION_SECURITY_BASELINE_BOUNDARY.md`](docs/FOUNDATION_SECURITY_BASELINE_BOUNDARY.md)",
        "[`docs/FOUNDATION_COST_BUDGET_BOUNDARY.md`](docs/FOUNDATION_COST_BUDGET_BOUNDARY.md)",
        "[`docs/FOUNDATION_PAYMENT_PROVIDER_BOUNDARY.md`](docs/FOUNDATION_PAYMENT_PROVIDER_BOUNDARY.md)",
        "[`docs/FOUNDATION_RUNTIME_ENVIRONMENT_BOUNDARY.md`](docs/FOUNDATION_RUNTIME_ENVIRONMENT_BOUNDARY.md)",
        "[`docs/FOUNDATION_BACKUP_EXPORT_BOUNDARY.md`](docs/FOUNDATION_BACKUP_EXPORT_BOUNDARY.md)",
        "[`docs/FOUNDATION_DEPLOYMENT_DEFERRAL_BOUNDARY.md`](docs/FOUNDATION_DEPLOYMENT_DEFERRAL_BOUNDARY.md)",
        "[`docs/FOUNDATION_EXTERNAL_INFRASTRUCTURE_BOUNDARY.md`](docs/FOUNDATION_EXTERNAL_INFRASTRUCTURE_BOUNDARY.md)",
        "[`docs/FOUNDATION_RUNTIME_SECRET_HANDOFF_REHEARSAL_BOUNDARY.md`](docs/FOUNDATION_RUNTIME_SECRET_HANDOFF_REHEARSAL_BOUNDARY.md)",
        "[`docs/FOUNDATION_RUNTIME_WITNESS_DEFERRAL_BOUNDARY.md`](docs/FOUNDATION_RUNTIME_WITNESS_DEFERRAL_BOUNDARY.md)",
        "[`docs/FOUNDATION_PRODUCTION_DEPENDENCY_EVIDENCE_REHEARSAL_BOUNDARY.md`](docs/FOUNDATION_PRODUCTION_DEPENDENCY_EVIDENCE_REHEARSAL_BOUNDARY.md)",
        "[`docs/FOUNDATION_EXTERNAL_EVIDENCE_ACCEPTANCE_REHEARSAL_BOUNDARY.md`](docs/FOUNDATION_EXTERNAL_EVIDENCE_ACCEPTANCE_REHEARSAL_BOUNDARY.md)",
        "[`docs/FOUNDATION_DEPLOYMENT_UPSTREAM_API_GATE_REHEARSAL_BOUNDARY.md`](docs/FOUNDATION_DEPLOYMENT_UPSTREAM_API_GATE_REHEARSAL_BOUNDARY.md)",
        "[`docs/FOUNDATION_GATEWAY_DNS_TARGET_BINDING_REHEARSAL_BOUNDARY.md`](docs/FOUNDATION_GATEWAY_DNS_TARGET_BINDING_REHEARSAL_BOUNDARY.md)",
        "[`docs/FOUNDATION_GATEWAY_DNS_PUBLICATION_REHEARSAL_BOUNDARY.md`](docs/FOUNDATION_GATEWAY_DNS_PUBLICATION_REHEARSAL_BOUNDARY.md)",
        "[`docs/FOUNDATION_GATEWAY_DNS_RESOLUTION_RECEIPT_REHEARSAL_BOUNDARY.md`](docs/FOUNDATION_GATEWAY_DNS_RESOLUTION_RECEIPT_REHEARSAL_BOUNDARY.md)",
        "[`docs/FOUNDATION_GATEWAY_ENDPOINT_REACHABILITY_REHEARSAL_BOUNDARY.md`](docs/FOUNDATION_GATEWAY_ENDPOINT_REACHABILITY_REHEARSAL_BOUNDARY.md)",
        "[`docs/FOUNDATION_GATEWAY_ENDPOINT_EVIDENCE_RECEIPT_REHEARSAL_BOUNDARY.md`](docs/FOUNDATION_GATEWAY_ENDPOINT_EVIDENCE_RECEIPT_REHEARSAL_BOUNDARY.md)",
        "[`docs/FOUNDATION_PUBLIC_HEALTH_DECLARATION_REHEARSAL_BOUNDARY.md`](docs/FOUNDATION_PUBLIC_HEALTH_DECLARATION_REHEARSAL_BOUNDARY.md)",
        "[`docs/FOUNDATION_DEPLOYMENT_WITNESS_INPUT_BOUNDARY.md`](docs/FOUNDATION_DEPLOYMENT_WITNESS_INPUT_BOUNDARY.md)",
        "[`docs/FOUNDATION_DEPLOYMENT_WITNESS_PREFLIGHT_REHEARSAL_BOUNDARY.md`](docs/FOUNDATION_DEPLOYMENT_WITNESS_PREFLIGHT_REHEARSAL_BOUNDARY.md)",
        "[`docs/FOUNDATION_DEPLOYMENT_WITNESS_DISPATCH_REHEARSAL_BOUNDARY.md`](docs/FOUNDATION_DEPLOYMENT_WITNESS_DISPATCH_REHEARSAL_BOUNDARY.md)",
        "[`docs/FOUNDATION_DEPLOYMENT_WITNESS_ARTIFACT_VALIDATION_REHEARSAL_BOUNDARY.md`](docs/FOUNDATION_DEPLOYMENT_WITNESS_ARTIFACT_VALIDATION_REHEARSAL_BOUNDARY.md)",
        "[`docs/FOUNDATION_DEPLOYMENT_WITNESS_EVIDENCE_HANDOFF_BOUNDARY.md`](docs/FOUNDATION_DEPLOYMENT_WITNESS_EVIDENCE_HANDOFF_BOUNDARY.md)",
        "[`docs/FOUNDATION_DEPLOYMENT_WITNESS_EVIDENCE_LEDGER_ROUTING_BOUNDARY.md`](docs/FOUNDATION_DEPLOYMENT_WITNESS_EVIDENCE_LEDGER_ROUTING_BOUNDARY.md)",
        "[`docs/FOUNDATION_GITHUB_APP_TOKEN_FORMAT_BOUNDARY.md`](docs/FOUNDATION_GITHUB_APP_TOKEN_FORMAT_BOUNDARY.md)",
        "[`docs/FOUNDATION_PILOT_DEFERRAL_BOUNDARY.md`](docs/FOUNDATION_PILOT_DEFERRAL_BOUNDARY.md)",
        "[`docs/FOUNDATION_REASSESSMENT_GATE_BOUNDARY.md`](docs/FOUNDATION_REASSESSMENT_GATE_BOUNDARY.md)",
        "[`docs/FOUNDATION_PILOT_DEFERRAL_REHEARSAL_BOUNDARY.md`](docs/FOUNDATION_PILOT_DEFERRAL_REHEARSAL_BOUNDARY.md)",
        "[`docs/FOUNDATION_LEARNING_LOOP_REHEARSAL_BOUNDARY.md`](docs/FOUNDATION_LEARNING_LOOP_REHEARSAL_BOUNDARY.md)",
        "[`docs/FOUNDATION_CONCEPT_GLOSSARY_REHEARSAL_BOUNDARY.md`](docs/FOUNDATION_CONCEPT_GLOSSARY_REHEARSAL_BOUNDARY.md)",
        "[`docs/FOUNDATION_LIFE_MEANING_DOCTRINE_REHEARSAL_BOUNDARY.md`](docs/FOUNDATION_LIFE_MEANING_DOCTRINE_REHEARSAL_BOUNDARY.md)",
        "[`docs/FOUNDATION_LOCAL_RELEASE_PACKET_REHEARSAL_BOUNDARY.md`](docs/FOUNDATION_LOCAL_RELEASE_PACKET_REHEARSAL_BOUNDARY.md)",
        "[`docs/FOUNDATION_PYTHON_DEPENDENCY_VISIBILITY_REHEARSAL_BOUNDARY.md`](docs/FOUNDATION_PYTHON_DEPENDENCY_VISIBILITY_REHEARSAL_BOUNDARY.md)",
        "[`docs/FOUNDATION_PRIVATE_RECOVERY_REHEARSAL_BOUNDARY.md`](docs/FOUNDATION_PRIVATE_RECOVERY_REHEARSAL_BOUNDARY.md)",
        "[`docs/FOUNDATION_SUPPORT_TRIAGE_REHEARSAL_BOUNDARY.md`](docs/FOUNDATION_SUPPORT_TRIAGE_REHEARSAL_BOUNDARY.md)",
        "[`docs/FOUNDATION_INTAKE_QUESTIONNAIRE_REHEARSAL_BOUNDARY.md`](docs/FOUNDATION_INTAKE_QUESTIONNAIRE_REHEARSAL_BOUNDARY.md)",
        "[`docs/FOUNDATION_CUSTOMER_ACCESS_POLICY_REHEARSAL_BOUNDARY.md`](docs/FOUNDATION_CUSTOMER_ACCESS_POLICY_REHEARSAL_BOUNDARY.md)",
        "[`docs/FOUNDATION_PRIVACY_MINIMIZATION_REHEARSAL_BOUNDARY.md`](docs/FOUNDATION_PRIVACY_MINIMIZATION_REHEARSAL_BOUNDARY.md)",
        "[`docs/FOUNDATION_LEGAL_BUSINESS_QUESTION_REHEARSAL_BOUNDARY.md`](docs/FOUNDATION_LEGAL_BUSINESS_QUESTION_REHEARSAL_BOUNDARY.md)",
        "[`docs/FOUNDATION_LEGAL_REVIEW_DEFERRAL_BOUNDARY.md`](docs/FOUNDATION_LEGAL_REVIEW_DEFERRAL_BOUNDARY.md)",
        "[`docs/FOUNDATION_COMPANY_FORMATION_DEFERRAL_BOUNDARY.md`](docs/FOUNDATION_COMPANY_FORMATION_DEFERRAL_BOUNDARY.md)",
        "[`docs/FOUNDATION_PATENT_DISCLOSURE_DEFERRAL_BOUNDARY.md`](docs/FOUNDATION_PATENT_DISCLOSURE_DEFERRAL_BOUNDARY.md)",
        "[`docs/FOUNDATION_FUNDING_TEAM_OBLIGATION_REHEARSAL_BOUNDARY.md`](docs/FOUNDATION_FUNDING_TEAM_OBLIGATION_REHEARSAL_BOUNDARY.md)",
        "[`docs/FOUNDATION_COMMUNITY_NETWORK_NO_OUTREACH_REHEARSAL_BOUNDARY.md`](docs/FOUNDATION_COMMUNITY_NETWORK_NO_OUTREACH_REHEARSAL_BOUNDARY.md)",
        "[`docs/FOUNDATION_PRODUCT_SCOPE_BOUNDARY.md`](docs/FOUNDATION_PRODUCT_SCOPE_BOUNDARY.md)",
        "[`docs/FOUNDATION_SUPPORT_READINESS_BOUNDARY.md`](docs/FOUNDATION_SUPPORT_READINESS_BOUNDARY.md)",
        "[`docs/FOUNDATION_INTAKE_ONBOARDING_BOUNDARY.md`](docs/FOUNDATION_INTAKE_ONBOARDING_BOUNDARY.md)",
        "[`docs/FOUNDATION_PRIVACY_DATA_BOUNDARY.md`](docs/FOUNDATION_PRIVACY_DATA_BOUNDARY.md)",
        "[`docs/FOUNDATION_CUSTOMER_ACCESS_BOUNDARY.md`](docs/FOUNDATION_CUSTOMER_ACCESS_BOUNDARY.md)",
        "[`docs/FOUNDATION_PRIVATE_RECOVERY_BOUNDARY.md`](docs/FOUNDATION_PRIVATE_RECOVERY_BOUNDARY.md)",
        "[`docs/FOUNDATION_DOMAIN_EMAIL_BOUNDARY.md`](docs/FOUNDATION_DOMAIN_EMAIL_BOUNDARY.md)",
        "[`docs/FOUNDATION_LEGAL_BUSINESS_BOUNDARY.md`](docs/FOUNDATION_LEGAL_BUSINESS_BOUNDARY.md)",
        "[`docs/FOUNDATION_FUNDING_TEAM_BOUNDARY.md`](docs/FOUNDATION_FUNDING_TEAM_BOUNDARY.md)",
    ),
    "docs/FOUNDATION_MODE.md": (
        "Foundation Mode means the project is being prepared carefully",
        "before deployment, company formation, customer access, or paid infrastructure",
        "For the step-by-step prerequisite ledger",
        "[Foundation Prerequisites](FOUNDATION_PREREQUISITES.md)",
        "[Foundation Operator Readiness Boundary](FOUNDATION_OPERATOR_READINESS_BOUNDARY.md)",
        "[Foundation Solo Daily Loop Boundary](FOUNDATION_SOLO_DAILY_LOOP_BOUNDARY.md)",
        "[Foundation Learning Path Boundary](FOUNDATION_LEARNING_PATH_BOUNDARY.md)",
        "[Foundation Learning Loop Rehearsal Boundary](FOUNDATION_LEARNING_LOOP_REHEARSAL_BOUNDARY.md)",
        "[Foundation Concept Glossary Rehearsal Boundary](FOUNDATION_CONCEPT_GLOSSARY_REHEARSAL_BOUNDARY.md)",
        "[Foundation Life Meaning Doctrine Rehearsal Boundary](FOUNDATION_LIFE_MEANING_DOCTRINE_REHEARSAL_BOUNDARY.md)",
        "[Foundation Local Release Packet Rehearsal Boundary](FOUNDATION_LOCAL_RELEASE_PACKET_REHEARSAL_BOUNDARY.md)",
        "[Foundation Python Dependency Visibility Rehearsal Boundary](FOUNDATION_PYTHON_DEPENDENCY_VISIBILITY_REHEARSAL_BOUNDARY.md)",
        "[Foundation Community Network Boundary](FOUNDATION_COMMUNITY_NETWORK_BOUNDARY.md)",
        "[Foundation Architecture Map Boundary](FOUNDATION_ARCHITECTURE_MAP_BOUNDARY.md)",
        "[Foundation System Boundary Inventory Boundary](FOUNDATION_SYSTEM_BOUNDARY_INVENTORY_BOUNDARY.md)",
        "[Foundation Module Inventory Boundary](FOUNDATION_MODULE_INVENTORY_BOUNDARY.md)",
        "[Foundation Component Contract Boundary](FOUNDATION_COMPONENT_CONTRACT_BOUNDARY.md)",
        "[Foundation Interface Map Boundary](FOUNDATION_INTERFACE_MAP_BOUNDARY.md)",
        "[Foundation Dependency Graph Boundary](FOUNDATION_DEPENDENCY_GRAPH_BOUNDARY.md)",
        "[Foundation Invariant Map Boundary](FOUNDATION_INVARIANT_MAP_BOUNDARY.md)",
        "[Foundation Hazard Map Boundary](FOUNDATION_HAZARD_MAP_BOUNDARY.md)",
        "[Foundation Proof Reference Boundary](FOUNDATION_PROOF_REFERENCE_BOUNDARY.md)",
        "[Foundation Gap Register Boundary](FOUNDATION_GAP_REGISTER_BOUNDARY.md)",
        "[Foundation Diff Review Boundary](FOUNDATION_DIFF_REVIEW_BOUNDARY.md)",
        "[Foundation Change Handoff Boundary](FOUNDATION_CHANGE_HANDOFF_BOUNDARY.md)",
        "[Foundation Local Workstation Boundary](FOUNDATION_LOCAL_WORKSTATION_BOUNDARY.md)",
        "[Foundation Documentation Boundary](FOUNDATION_DOCUMENTATION_BOUNDARY.md)",
        "[Foundation Plain-Language Status Boundary](FOUNDATION_PLAIN_LANGUAGE_STATUS_BOUNDARY.md)",
        "[Foundation Accessibility Language Boundary](FOUNDATION_ACCESSIBILITY_LANGUAGE_BOUNDARY.md)",
        "[Foundation Capability Roadmap Boundary](FOUNDATION_CAPABILITY_ROADMAP_BOUNDARY.md)",
        "[Foundation Agentic Management Boundary](FOUNDATION_AGENTIC_MANAGEMENT_BOUNDARY.md)",
        "[Foundation Operations Runbook Boundary](FOUNDATION_OPERATIONS_RUNBOOK_BOUNDARY.md)",
        "[Foundation Claim Boundary](FOUNDATION_CLAIM_BOUNDARY.md)",
        "[Foundation Website Posture Boundary](FOUNDATION_WEBSITE_POSTURE_BOUNDARY.md)",
        "[Foundation Research Notebook Boundary](FOUNDATION_RESEARCH_NOTEBOOK_BOUNDARY.md)",
        "[Foundation Market Research Boundary](FOUNDATION_MARKET_RESEARCH_BOUNDARY.md)",
        "[Foundation Evidence Ledger Boundary](FOUNDATION_EVIDENCE_LEDGER_BOUNDARY.md)",
        "[Foundation Decision Journal Boundary](FOUNDATION_DECISION_JOURNAL_BOUNDARY.md)",
        "[Foundation Next Action Boundary](FOUNDATION_NEXT_ACTION_BOUNDARY.md)",
        "[Foundation Test Evidence Boundary](FOUNDATION_TEST_EVIDENCE_BOUNDARY.md)",
        "[Foundation Source Control Boundary](FOUNDATION_SOURCE_CONTROL_BOUNDARY.md)",
        "[Foundation Source-Control Review Checklist Boundary](FOUNDATION_SOURCE_CONTROL_REVIEW_CHECKLIST_BOUNDARY.md)",
        "[Foundation Secrets Credentials Boundary](FOUNDATION_SECRETS_CREDENTIALS_BOUNDARY.md)",
        "[Foundation Security Baseline Boundary](FOUNDATION_SECURITY_BASELINE_BOUNDARY.md)",
        "[Foundation Cost Budget Boundary](FOUNDATION_COST_BUDGET_BOUNDARY.md)",
        "[Foundation Payment Provider Boundary](FOUNDATION_PAYMENT_PROVIDER_BOUNDARY.md)",
        "[Foundation Runtime Environment Boundary](FOUNDATION_RUNTIME_ENVIRONMENT_BOUNDARY.md)",
        "[Foundation Backup Export Boundary](FOUNDATION_BACKUP_EXPORT_BOUNDARY.md)",
        "[Foundation Deployment Deferral Boundary](FOUNDATION_DEPLOYMENT_DEFERRAL_BOUNDARY.md)",
        "[Foundation External Infrastructure Boundary](FOUNDATION_EXTERNAL_INFRASTRUCTURE_BOUNDARY.md)",
        "[Foundation Runtime Secret Handoff Rehearsal Boundary](FOUNDATION_RUNTIME_SECRET_HANDOFF_REHEARSAL_BOUNDARY.md)",
        "[Foundation Runtime Witness Deferral Boundary](FOUNDATION_RUNTIME_WITNESS_DEFERRAL_BOUNDARY.md)",
        "[Foundation Production Dependency Evidence Rehearsal Boundary](FOUNDATION_PRODUCTION_DEPENDENCY_EVIDENCE_REHEARSAL_BOUNDARY.md)",
        "[Foundation External Evidence Acceptance Rehearsal Boundary](FOUNDATION_EXTERNAL_EVIDENCE_ACCEPTANCE_REHEARSAL_BOUNDARY.md)",
        "[Foundation Deployment Upstream API Gate Rehearsal Boundary](FOUNDATION_DEPLOYMENT_UPSTREAM_API_GATE_REHEARSAL_BOUNDARY.md)",
        "[Foundation Gateway DNS Target Binding Rehearsal Boundary](FOUNDATION_GATEWAY_DNS_TARGET_BINDING_REHEARSAL_BOUNDARY.md)",
        "[Foundation Gateway DNS Publication Rehearsal Boundary](FOUNDATION_GATEWAY_DNS_PUBLICATION_REHEARSAL_BOUNDARY.md)",
        "[Foundation Gateway DNS Resolution Receipt Rehearsal Boundary](FOUNDATION_GATEWAY_DNS_RESOLUTION_RECEIPT_REHEARSAL_BOUNDARY.md)",
        "[Foundation Gateway Endpoint Reachability Rehearsal Boundary](FOUNDATION_GATEWAY_ENDPOINT_REACHABILITY_REHEARSAL_BOUNDARY.md)",
        "[Foundation Gateway Endpoint Evidence Receipt Rehearsal Boundary](FOUNDATION_GATEWAY_ENDPOINT_EVIDENCE_RECEIPT_REHEARSAL_BOUNDARY.md)",
        "[Foundation Public Health Declaration Rehearsal Boundary](FOUNDATION_PUBLIC_HEALTH_DECLARATION_REHEARSAL_BOUNDARY.md)",
        "[Foundation Deployment Witness Input Boundary](FOUNDATION_DEPLOYMENT_WITNESS_INPUT_BOUNDARY.md)",
        "[Foundation Deployment Witness Preflight Rehearsal Boundary](FOUNDATION_DEPLOYMENT_WITNESS_PREFLIGHT_REHEARSAL_BOUNDARY.md)",
        "[Foundation Deployment Witness Dispatch Rehearsal Boundary](FOUNDATION_DEPLOYMENT_WITNESS_DISPATCH_REHEARSAL_BOUNDARY.md)",
        "[Foundation Deployment Witness Artifact Validation Rehearsal Boundary](FOUNDATION_DEPLOYMENT_WITNESS_ARTIFACT_VALIDATION_REHEARSAL_BOUNDARY.md)",
        "[Foundation Deployment Witness Evidence Handoff Boundary](FOUNDATION_DEPLOYMENT_WITNESS_EVIDENCE_HANDOFF_BOUNDARY.md)",
        "[Foundation Deployment Witness Evidence Ledger Routing Boundary](FOUNDATION_DEPLOYMENT_WITNESS_EVIDENCE_LEDGER_ROUTING_BOUNDARY.md)",
        "Deployment-witness-preflight-rehearsal posture",
        "Deployment-witness-dispatch-rehearsal posture",
        "Deployment-witness-artifact-validation posture",
        "Deployment-witness-evidence-ledger-routing posture",
        "[Foundation GitHub App Token Format Boundary](FOUNDATION_GITHUB_APP_TOKEN_FORMAT_BOUNDARY.md)",
        "[Foundation Pilot Deferral Boundary](FOUNDATION_PILOT_DEFERRAL_BOUNDARY.md)",
        "[Foundation Reassessment Gate Boundary](FOUNDATION_REASSESSMENT_GATE_BOUNDARY.md)",
        "[Foundation Pilot Deferral Rehearsal Boundary](FOUNDATION_PILOT_DEFERRAL_REHEARSAL_BOUNDARY.md)",
        "[Foundation Private Recovery Rehearsal Boundary](FOUNDATION_PRIVATE_RECOVERY_REHEARSAL_BOUNDARY.md)",
        "[Foundation Support Triage Rehearsal Boundary](FOUNDATION_SUPPORT_TRIAGE_REHEARSAL_BOUNDARY.md)",
        "[Foundation Intake Questionnaire Rehearsal Boundary](FOUNDATION_INTAKE_QUESTIONNAIRE_REHEARSAL_BOUNDARY.md)",
        "[Foundation Customer Access Policy Rehearsal Boundary](FOUNDATION_CUSTOMER_ACCESS_POLICY_REHEARSAL_BOUNDARY.md)",
        "[Foundation Privacy Minimization Rehearsal Boundary](FOUNDATION_PRIVACY_MINIMIZATION_REHEARSAL_BOUNDARY.md)",
        "[Foundation Legal Business Question Rehearsal Boundary](FOUNDATION_LEGAL_BUSINESS_QUESTION_REHEARSAL_BOUNDARY.md)",
        "[Foundation Legal Review Deferral Boundary](FOUNDATION_LEGAL_REVIEW_DEFERRAL_BOUNDARY.md)",
        "[Foundation Company Formation Deferral Boundary](FOUNDATION_COMPANY_FORMATION_DEFERRAL_BOUNDARY.md)",
        "[Foundation Patent Disclosure Deferral Boundary](FOUNDATION_PATENT_DISCLOSURE_DEFERRAL_BOUNDARY.md)",
        "[Foundation Funding Team Obligation Rehearsal Boundary](FOUNDATION_FUNDING_TEAM_OBLIGATION_REHEARSAL_BOUNDARY.md)",
        "[Foundation Community Network No-Outreach Rehearsal Boundary](FOUNDATION_COMMUNITY_NETWORK_NO_OUTREACH_REHEARSAL_BOUNDARY.md)",
        "[Foundation Private Recovery Boundary](FOUNDATION_PRIVATE_RECOVERY_BOUNDARY.md)",
        "[Foundation Domain Email Boundary](FOUNDATION_DOMAIN_EMAIL_BOUNDARY.md)",
        "[Foundation Product Scope Boundary](FOUNDATION_PRODUCT_SCOPE_BOUNDARY.md)",
        "[Foundation Support Readiness Boundary](FOUNDATION_SUPPORT_READINESS_BOUNDARY.md)",
        "[Foundation Intake Onboarding Boundary](FOUNDATION_INTAKE_ONBOARDING_BOUNDARY.md)",
        "[Foundation Privacy Data Boundary](FOUNDATION_PRIVACY_DATA_BOUNDARY.md)",
        "[Foundation Customer Access Boundary](FOUNDATION_CUSTOMER_ACCESS_BOUNDARY.md)",
        "[Foundation Legal Business Boundary](FOUNDATION_LEGAL_BUSINESS_BOUNDARY.md)",
        "Do not push toward deployment, public launch, customers, LLC formation",
    ),
    "docs/FOUNDATION_PREREQUISITES.md": (
        "this is the checklist for preparing the foundation before",
        "Atomic Prerequisite Ledger",
        "[Foundation Operator Readiness Boundary](FOUNDATION_OPERATOR_READINESS_BOUNDARY.md)",
        "[Foundation Solo Daily Loop Boundary](FOUNDATION_SOLO_DAILY_LOOP_BOUNDARY.md)",
        "[Foundation Learning Path Boundary](FOUNDATION_LEARNING_PATH_BOUNDARY.md)",
        "[Foundation Learning Loop Rehearsal Boundary](FOUNDATION_LEARNING_LOOP_REHEARSAL_BOUNDARY.md)",
        "[Foundation Concept Glossary Rehearsal Boundary](FOUNDATION_CONCEPT_GLOSSARY_REHEARSAL_BOUNDARY.md)",
        "[Foundation Python Dependency Visibility Rehearsal Boundary](FOUNDATION_PYTHON_DEPENDENCY_VISIBILITY_REHEARSAL_BOUNDARY.md)",
        "[Foundation Community Network Boundary](FOUNDATION_COMMUNITY_NETWORK_BOUNDARY.md)",
        "[Foundation Architecture Map Boundary](FOUNDATION_ARCHITECTURE_MAP_BOUNDARY.md)",
        "[Foundation System Boundary Inventory Boundary](FOUNDATION_SYSTEM_BOUNDARY_INVENTORY_BOUNDARY.md)",
        "[Foundation Module Inventory Boundary](FOUNDATION_MODULE_INVENTORY_BOUNDARY.md)",
        "[Foundation Component Contract Boundary](FOUNDATION_COMPONENT_CONTRACT_BOUNDARY.md)",
        "[Foundation Interface Map Boundary](FOUNDATION_INTERFACE_MAP_BOUNDARY.md)",
        "[Foundation Dependency Graph Boundary](FOUNDATION_DEPENDENCY_GRAPH_BOUNDARY.md)",
        "[Foundation Invariant Map Boundary](FOUNDATION_INVARIANT_MAP_BOUNDARY.md)",
        "[Foundation Hazard Map Boundary](FOUNDATION_HAZARD_MAP_BOUNDARY.md)",
        "[Foundation Proof Reference Boundary](FOUNDATION_PROOF_REFERENCE_BOUNDARY.md)",
        "[Foundation Gap Register Boundary](FOUNDATION_GAP_REGISTER_BOUNDARY.md)",
        "[Foundation Diff Review Boundary](FOUNDATION_DIFF_REVIEW_BOUNDARY.md)",
        "[Foundation Change Handoff Boundary](FOUNDATION_CHANGE_HANDOFF_BOUNDARY.md)",
        "[Foundation Local Workstation Boundary](FOUNDATION_LOCAL_WORKSTATION_BOUNDARY.md)",
        "[Foundation Documentation Boundary](FOUNDATION_DOCUMENTATION_BOUNDARY.md)",
        "[Foundation Plain-Language Status Boundary](FOUNDATION_PLAIN_LANGUAGE_STATUS_BOUNDARY.md)",
        "[Foundation Accessibility Language Boundary](FOUNDATION_ACCESSIBILITY_LANGUAGE_BOUNDARY.md)",
        "[Foundation Capability Roadmap Boundary](FOUNDATION_CAPABILITY_ROADMAP_BOUNDARY.md)",
        "[Foundation Agentic Management Boundary](FOUNDATION_AGENTIC_MANAGEMENT_BOUNDARY.md)",
        "[Foundation Operations Runbook Boundary](FOUNDATION_OPERATIONS_RUNBOOK_BOUNDARY.md)",
        "[Foundation Claim Boundary](FOUNDATION_CLAIM_BOUNDARY.md)",
        "[Foundation Website Posture Boundary](FOUNDATION_WEBSITE_POSTURE_BOUNDARY.md)",
        "[Foundation Research Notebook Boundary](FOUNDATION_RESEARCH_NOTEBOOK_BOUNDARY.md)",
        "[Foundation Market Research Boundary](FOUNDATION_MARKET_RESEARCH_BOUNDARY.md)",
        "[Foundation Evidence Ledger Boundary](FOUNDATION_EVIDENCE_LEDGER_BOUNDARY.md)",
        "[Foundation Decision Journal Boundary](FOUNDATION_DECISION_JOURNAL_BOUNDARY.md)",
        "[Foundation Next Action Boundary](FOUNDATION_NEXT_ACTION_BOUNDARY.md)",
        "[Foundation Test Evidence Boundary](FOUNDATION_TEST_EVIDENCE_BOUNDARY.md)",
        "[Foundation Source Control Boundary](FOUNDATION_SOURCE_CONTROL_BOUNDARY.md)",
        "[Foundation Source-Control Review Checklist Boundary](FOUNDATION_SOURCE_CONTROL_REVIEW_CHECKLIST_BOUNDARY.md)",
        "[Foundation Local Proof Thread](FOUNDATION_LOCAL_PROOF_THREAD.md)",
        "[Foundation Private Recovery Boundary](FOUNDATION_PRIVATE_RECOVERY_BOUNDARY.md)",
        "[Foundation Secrets Credentials Boundary](FOUNDATION_SECRETS_CREDENTIALS_BOUNDARY.md)",
        "[Foundation Security Baseline Boundary](FOUNDATION_SECURITY_BASELINE_BOUNDARY.md)",
        "[Foundation Cost Budget Boundary](FOUNDATION_COST_BUDGET_BOUNDARY.md)",
        "[Foundation Payment Provider Boundary](FOUNDATION_PAYMENT_PROVIDER_BOUNDARY.md)",
        "[Foundation Runtime Environment Boundary](FOUNDATION_RUNTIME_ENVIRONMENT_BOUNDARY.md)",
        "[Foundation Backup Export Boundary](FOUNDATION_BACKUP_EXPORT_BOUNDARY.md)",
        "[Foundation Deployment Deferral Boundary](FOUNDATION_DEPLOYMENT_DEFERRAL_BOUNDARY.md)",
        "[Foundation External Infrastructure Boundary](FOUNDATION_EXTERNAL_INFRASTRUCTURE_BOUNDARY.md)",
        "[Foundation Deployment Upstream API Gate Rehearsal Boundary](FOUNDATION_DEPLOYMENT_UPSTREAM_API_GATE_REHEARSAL_BOUNDARY.md)",
        "[Foundation Gateway DNS Target Binding Rehearsal Boundary](FOUNDATION_GATEWAY_DNS_TARGET_BINDING_REHEARSAL_BOUNDARY.md)",
        "[Foundation Gateway DNS Publication Rehearsal Boundary](FOUNDATION_GATEWAY_DNS_PUBLICATION_REHEARSAL_BOUNDARY.md)",
        "gateway-DNS-publication-rehearsal evidence",
        "[Foundation Gateway DNS Resolution Receipt Rehearsal Boundary](FOUNDATION_GATEWAY_DNS_RESOLUTION_RECEIPT_REHEARSAL_BOUNDARY.md)",
        "[Foundation Gateway Endpoint Reachability Rehearsal Boundary](FOUNDATION_GATEWAY_ENDPOINT_REACHABILITY_REHEARSAL_BOUNDARY.md)",
        "[Foundation Gateway Endpoint Evidence Receipt Rehearsal Boundary](FOUNDATION_GATEWAY_ENDPOINT_EVIDENCE_RECEIPT_REHEARSAL_BOUNDARY.md)",
        "[Foundation Public Health Declaration Rehearsal Boundary](FOUNDATION_PUBLIC_HEALTH_DECLARATION_REHEARSAL_BOUNDARY.md)",
        "[Foundation Deployment Witness Input Boundary](FOUNDATION_DEPLOYMENT_WITNESS_INPUT_BOUNDARY.md)",
        "[Foundation Deployment Witness Preflight Rehearsal Boundary](FOUNDATION_DEPLOYMENT_WITNESS_PREFLIGHT_REHEARSAL_BOUNDARY.md)",
        "[Foundation Deployment Witness Dispatch Rehearsal Boundary](FOUNDATION_DEPLOYMENT_WITNESS_DISPATCH_REHEARSAL_BOUNDARY.md)",
        "[Foundation Deployment Witness Artifact Validation Rehearsal Boundary](FOUNDATION_DEPLOYMENT_WITNESS_ARTIFACT_VALIDATION_REHEARSAL_BOUNDARY.md)",
        "deployment-witness-artifact-validation-rehearsal evidence",
        "[Foundation Deployment Witness Evidence Handoff Boundary](FOUNDATION_DEPLOYMENT_WITNESS_EVIDENCE_HANDOFF_BOUNDARY.md)",
        "[Foundation Deployment Witness Evidence Ledger Routing Boundary](FOUNDATION_DEPLOYMENT_WITNESS_EVIDENCE_LEDGER_ROUTING_BOUNDARY.md)",
        "[Foundation GitHub App Token Format Boundary](FOUNDATION_GITHUB_APP_TOKEN_FORMAT_BOUNDARY.md)",
        "[Foundation Public CI Window Boundary](FOUNDATION_PUBLIC_CI_WINDOW_BOUNDARY.md)",
        "[Foundation Pilot Deferral Boundary](FOUNDATION_PILOT_DEFERRAL_BOUNDARY.md)",
        "[Foundation Domain Email Boundary](FOUNDATION_DOMAIN_EMAIL_BOUNDARY.md)",
        "[Foundation Product Scope Boundary](FOUNDATION_PRODUCT_SCOPE_BOUNDARY.md)",
        "[Foundation Support Readiness Boundary](FOUNDATION_SUPPORT_READINESS_BOUNDARY.md)",
        "[Foundation Intake Onboarding Boundary](FOUNDATION_INTAKE_ONBOARDING_BOUNDARY.md)",
        "[Foundation Privacy Data Boundary](FOUNDATION_PRIVACY_DATA_BOUNDARY.md)",
        "[Foundation Customer Access Boundary](FOUNDATION_CUSTOMER_ACCESS_BOUNDARY.md)",
        "[Foundation Legal Business Boundary](FOUNDATION_LEGAL_BUSINESS_BOUNDARY.md)",
        "[Foundation Funding Team Boundary](FOUNDATION_FUNDING_TEAM_BOUNDARY.md)",
        "Do not claim legal clearance, patent protection, or company readiness",
        "No customer access or deployment claim",
        "When a future request says \"continue,\" use this order",
    ),
    "docs/FOUNDATION_LOCAL_PROOF_THREAD.md": (
        "the first proof thread is one harmless local workflow",
        "Descriptor: [`../examples/foundation_local_proof_thread.workflow.json`]",
        "python scripts/run_foundation_local_proof_thread.py",
        "Rule: No customer access or deployment claim.",
        "The default receipt is local evidence only",
    ),
    "docs/FOUNDATION_SOURCE_CONTROL_BOUNDARY.md": (
        "Foundation Source Control Boundary",
        "Boundary packet: [`../examples/foundation_source_control_boundary.awaiting_commit.json`]",
        "Rule: Commit readiness is prepared locally, but commit execution requires an",
        "No staging, commit, push, pull request, release, deployment, customer access, or",
        "source_control_boundary_state=AwaitingEvidence",
        "commit_allowed=false",
        "pull_request_allowed=false",
        "Operations/runbook | Local runbook-inventory",
        "Agentic management | Local goal-intake",
        "python scripts/validate_foundation_agentic_management_boundary.py",
        "python scripts/validate_foundation_operations_runbook_boundary.py",
    ),
    "docs/FOUNDATION_SOURCE_CONTROL_REVIEW_CHECKLIST_BOUNDARY.md": (
        "Foundation Source-Control Review Checklist Boundary",
        "Witness packet: [`../examples/foundation_source_control_review_checklist_witness.awaiting_evidence.json`]",
        "Rule: Source-control review checklist preparation is a local planning boundary,",
        "No checklist completion, review-scope closure, staging approval, commit",
        "source_control_review_checklist_state=AwaitingEvidence",
        "checklist_complete_claimed=false",
        "review_scope_closed_claimed=false",
        "validation_complete_claimed=false",
        "staging_allowed=false",
        "commit_allowed=false",
        "pull_request_allowed=false",
        "external_publication_allowed=false",
        "deployment_allowed=false",
        "secret_publication_allowed=false",
        "python scripts/validate_foundation_source_control_review_checklist_boundary.py",
    ),
    "docs/FOUNDATION_OPERATOR_READINESS_BOUNDARY.md": (
        "Foundation Operator Readiness Boundary",
        "Witness packet: [`../examples/foundation_operator_readiness_witness.awaiting_evidence.json`]",
        "Rule: Operator-readiness preparation is a local planning boundary, not",
        "No solo-operator capacity verification, schedule-readiness claim,",
        "operator_readiness_boundary_state=AwaitingEvidence",
        "operator_capacity_verified=false",
        "schedule_readiness_claimed=false",
        "team_readiness_claimed=false",
        "deployment_allowed=false",
    ),
    "docs/FOUNDATION_SOLO_DAILY_LOOP_BOUNDARY.md": (
        "Foundation Solo Daily Loop Boundary",
        "Witness packet: [`../examples/foundation_solo_daily_loop_witness.awaiting_evidence.json`]",
        "Rule: Solo daily loop preparation is a public-safe local planning boundary, not",
        "No daily productivity readiness, schedule-readiness claim, private calendar",
        "solo_daily_loop_boundary_state=AwaitingEvidence",
        "daily_productivity_readiness_claimed=false",
        "schedule_readiness_claimed=false",
        "private_calendar_recording_allowed=false",
        "private_health_tracking_allowed=false",
        "task_completion_guaranteed=false",
        "source_control_publication_allowed=false",
        "deployment_allowed=false",
        "python scripts/validate_foundation_solo_daily_loop_boundary.py",
    ),
    "docs/FOUNDATION_LEARNING_PATH_BOUNDARY.md": (
        "Foundation Learning Path Boundary",
        "Witness packet: [`../examples/foundation_learning_path_witness.awaiting_evidence.json`]",
        "Rule: Learning-path preparation is a local planning boundary, not a skill,",
        "No skill-readiness claim, training-completion claim, certification claim,",
        "learning_path_boundary_state=AwaitingEvidence",
        "skill_readiness_claimed=false",
        "training_completion_claimed=false",
        "certification_claimed=false",
        "paid_course_allowed=false",
        "mentor_assignment_allowed=false",
        "external_account_use_allowed=false",
        "deployment_allowed=false",
        "python scripts/validate_foundation_learning_path_boundary.py",
    ),
    "docs/FOUNDATION_LEARNING_LOOP_REHEARSAL_BOUNDARY.md": (
        "Foundation Learning Loop Rehearsal Boundary",
        "Witness packet: [`../examples/foundation_learning_loop_rehearsal_witness.awaiting_evidence.json`]",
        "Rule: Learning-loop rehearsal is a local paper-and-command practice packet",
        "learning_loop_rehearsal_boundary_state=AwaitingEvidence",
        "loop_rehearsal_executed=false",
        "skill_readiness_claimed=false",
        "training_completion_claimed=false",
        "certification_claimed=false",
        "paid_course_allowed=false",
        "mentor_assignment_allowed=false",
        "external_account_use_allowed=false",
        "private_schedule_recording_allowed=false",
        "private_health_recording_allowed=false",
        "source_control_publication_allowed=false",
        "deployment_allowed=false",
        "python scripts/validate_foundation_learning_loop_rehearsal_boundary.py",
    ),
    "docs/FOUNDATION_CONCEPT_GLOSSARY_REHEARSAL_BOUNDARY.md": (
        "Foundation Concept Glossary Rehearsal Boundary",
        "Witness packet: [`../examples/foundation_concept_glossary_rehearsal_witness.awaiting_evidence.json`]",
        "Rule: Concept glossary rehearsal is a local vocabulary clarification packet",
        "concept_glossary_rehearsal_boundary_state=AwaitingEvidence",
        "glossary_entry_published=false",
        "canonical_definition_claimed=false",
        "glossary_complete_claimed=false",
        "concept_mastery_claimed=false",
        "technical_readiness_claimed=false",
        "training_completion_claimed=false",
        "comprehension_proven=false",
        "public_docs_readiness_claimed=false",
        "product_readiness_claimed=false",
        "customer_readiness_claimed=false",
        "private_value_recording_allowed=false",
        "legal_business_action_allowed=false",
        "spending_allowed=false",
        "money_movement_allowed=false",
        "source_control_publication_allowed=false",
        "external_publication_allowed=false",
        "deployment_allowed=false",
        "python scripts/validate_foundation_concept_glossary_rehearsal_boundary.py",
    ),
    "docs/FOUNDATION_LIFE_MEANING_DOCTRINE_REHEARSAL_BOUNDARY.md": (
        "Foundation Life Meaning Doctrine Rehearsal Boundary",
        "Witness packet: [`../examples/foundation_life_meaning_doctrine_rehearsal_witness.awaiting_evidence.json`]",
        "Rule: Life/meaning doctrine rehearsal is a local stop-rule label packet",
        "life_meaning_doctrine_rehearsal_boundary_state=AwaitingEvidence",
        "life_meaning_judgment_executed=false",
        "doctrine_complete_claimed=false",
        "life_impact_closure_claimed=false",
        "feeling_status_determined=false",
        "medical_claim_allowed=false",
        "mental_health_claim_allowed=false",
        "ethics_clearance_claimed=false",
        "legal_clearance_claimed=false",
        "safety_certification_claimed=false",
        "human_subjects_research_allowed=false",
        "observer_personhood_claimed=false",
        "product_readiness_claimed=false",
        "customer_readiness_claimed=false",
        "private_value_recording_allowed=false",
        "spending_allowed=false",
        "money_movement_allowed=false",
        "source_control_publication_allowed=false",
        "external_publication_allowed=false",
        "deployment_allowed=false",
        "python scripts/validate_foundation_life_meaning_doctrine_rehearsal_boundary.py",
    ),
    "docs/FOUNDATION_LOCAL_RELEASE_PACKET_REHEARSAL_BOUNDARY.md": (
        "Foundation Local Release Packet Rehearsal Boundary",
        "Witness packet: [`../examples/foundation_local_release_packet_rehearsal_witness.awaiting_evidence.json`]",
        "Rule: Local release-packet rehearsal is a private Foundation Mode planning",
        "local_release_packet_rehearsal_boundary_state=AwaitingEvidence",
        "release_packet_published=false",
        "release_readiness_claimed=false",
        "version_label_selected=false",
        "tag_creation_allowed=false",
        "github_release_allowed=false",
        "changelog_publication_allowed=false",
        "artifact_publication_allowed=false",
        "source_control_publication_allowed=false",
        "external_publication_allowed=false",
        "deployment_allowed=false",
        "customer_access_allowed=false",
        "legal_clearance_claimed=false",
        "company_formation_claimed=false",
        "patent_action_allowed=false",
        "money_movement_allowed=false",
        "secret_publication_allowed=false",
        "private_value_recording_allowed=false",
        "python scripts/validate_foundation_local_release_packet_rehearsal_boundary.py",
    ),
    "docs/FOUNDATION_PYTHON_DEPENDENCY_VISIBILITY_REHEARSAL_BOUNDARY.md": (
        "Foundation Python Dependency Visibility Rehearsal Boundary",
        "Witness packet: [`../examples/foundation_python_dependency_visibility_rehearsal_witness.awaiting_evidence.json`]",
        "Rule: Python dependency-visibility rehearsal is a local Foundation Mode",
        "python_dependency_visibility_rehearsal_boundary_state=AwaitingEvidence",
        "dependency_visibility_claimed=false",
        "dependency_install_allowed=false",
        "interpreter_path_recording_allowed=false",
        "private_path_recording_allowed=false",
        "package_install_allowed=false",
        "environment_mutation_allowed=false",
        "fastapi_readiness_claimed=false",
        "preflight_closure_claimed=false",
        "runtime_readiness_claimed=false",
        "source_control_publication_allowed=false",
        "external_publication_allowed=false",
        "deployment_allowed=false",
        "customer_access_allowed=false",
        "legal_clearance_claimed=false",
        "company_formation_claimed=false",
        "patent_action_allowed=false",
        "money_movement_allowed=false",
        "secret_publication_allowed=false",
        "python scripts/validate_foundation_python_dependency_visibility_rehearsal_boundary.py",
    ),
    "docs/FOUNDATION_ARCHITECTURE_MAP_BOUNDARY.md": (
        "Foundation Architecture Map Boundary",
        "Witness packet: [`../examples/foundation_architecture_map_witness.awaiting_evidence.json`]",
        "Rule: Architecture-map preparation is a local planning boundary, not an architecture-completion",
        "No architecture-completeness claim, module-inventory completeness claim,",
        "architecture_map_boundary_state=AwaitingEvidence",
        "architecture_complete_claimed=false",
        "module_inventory_complete_claimed=false",
        "interface_contract_ready_claimed=false",
        "integration_readiness_claimed=false",
        "deployment_allowed=false",
        "python scripts/validate_foundation_architecture_map_boundary.py",
    ),
    "docs/FOUNDATION_SYSTEM_BOUNDARY_INVENTORY_BOUNDARY.md": (
        "Foundation System Boundary Inventory Boundary",
        "Witness packet: [`../examples/foundation_system_boundary_inventory_witness.awaiting_evidence.json`]",
        "Rule: System-boundary inventory preparation is a local planning boundary, not a system-boundary-completion",
        "No system-boundary inventory completeness, ownership-boundary closure, trust-boundary closure,",
        "system_boundary_inventory_boundary_state=AwaitingEvidence",
        "system_boundary_inventory_complete_claimed=false",
        "ownership_boundary_closed_claimed=false",
        "trust_boundary_closed_claimed=false",
        "tenant_boundary_ready_claimed=false",
        "deployment_allowed=false",
        "python scripts/validate_foundation_system_boundary_inventory_boundary.py",
    ),
    "docs/FOUNDATION_MODULE_INVENTORY_BOUNDARY.md": (
        "Foundation Module Inventory Boundary",
        "Witness packet: [`../examples/foundation_module_inventory_witness.awaiting_evidence.json`]",
        "Rule: Module-inventory preparation is a local planning boundary, not a module-inventory-completion",
        "No module inventory completeness, module ownership assignment, module contract",
        "module_inventory_boundary_state=AwaitingEvidence",
        "module_inventory_complete_claimed=false",
        "module_ownership_assigned=false",
        "module_contract_ready_claimed=false",
        "implementation_approval_allowed=false",
        "deployment_allowed=false",
        "python scripts/validate_foundation_module_inventory_boundary.py",
    ),
    "docs/FOUNDATION_COMPONENT_CONTRACT_BOUNDARY.md": (
        "Foundation Component Contract Boundary",
        "Witness packet: [`../examples/foundation_component_contract_witness.awaiting_evidence.json`]",
        "Rule: Component-contract preparation is a local planning boundary, not a",
        "No component contract readiness, input contract readiness, output contract",
        "component_contract_boundary_state=AwaitingEvidence",
        "component_contract_ready_claimed=false",
        "input_contract_ready_claimed=false",
        "output_contract_ready_claimed=false",
        "owner_approval_assigned=false",
        "test_pass_claimed=false",
        "implementation_approval_allowed=false",
        "deployment_allowed=false",
        "python scripts/validate_foundation_component_contract_boundary.py",
    ),
    "docs/FOUNDATION_INTERFACE_MAP_BOUNDARY.md": (
        "Foundation Interface Map Boundary",
        "Witness packet: [`../examples/foundation_interface_map_witness.awaiting_evidence.json`]",
        "Rule: Interface-map preparation is a local planning boundary, not an",
        "No interface-map completeness, interface contract readiness, endpoint",
        "interface_map_boundary_state=AwaitingEvidence",
        "interface_map_complete_claimed=false",
        "interface_contract_ready_claimed=false",
        "endpoint_ready_claimed=false",
        "service_binding_claimed=false",
        "integration_ready_claimed=false",
        "implementation_approval_allowed=false",
        "deployment_allowed=false",
        "python scripts/validate_foundation_interface_map_boundary.py",
    ),
    "docs/FOUNDATION_DEPENDENCY_GRAPH_BOUNDARY.md": (
        "Foundation Dependency Graph Boundary",
        "Witness packet: [`../examples/foundation_dependency_graph_witness.awaiting_evidence.json`]",
        "Rule: Dependency-graph preparation is a local planning boundary, not a",
        "No dependency-graph completeness, dependency contract readiness, import",
        "dependency_graph_boundary_state=AwaitingEvidence",
        "dependency_graph_complete_claimed=false",
        "dependency_contract_ready_claimed=false",
        "import_boundary_ready_claimed=false",
        "package_install_allowed=false",
        "version_lock_ready_claimed=false",
        "service_dependency_bound=false",
        "external_provider_bound=false",
        "implementation_approval_allowed=false",
        "deployment_allowed=false",
        "python scripts/validate_foundation_dependency_graph_boundary.py",
    ),
    "docs/FOUNDATION_INVARIANT_MAP_BOUNDARY.md": (
        "Foundation Invariant Map Boundary",
        "Witness packet: [`../examples/foundation_invariant_map_witness.awaiting_evidence.json`]",
        "Rule: Invariant-map preparation is a local planning boundary, not an",
        "No invariant-map completeness, invariant proof readiness, invariant",
        "invariant_map_boundary_state=AwaitingEvidence",
        "invariant_map_complete_claimed=false",
        "invariant_proof_ready_claimed=false",
        "invariant_enforcement_ready_claimed=false",
        "invariant_monitor_ready_claimed=false",
        "runtime_invariant_ready_claimed=false",
        "implementation_approval_allowed=false",
        "deployment_allowed=false",
        "python scripts/validate_foundation_invariant_map_boundary.py",
    ),
    "docs/FOUNDATION_HAZARD_MAP_BOUNDARY.md": (
        "Foundation Hazard Map Boundary",
        "Witness packet: [`../examples/foundation_hazard_map_witness.awaiting_evidence.json`]",
        "Rule: Hazard-map preparation is a local planning boundary, not a",
        "No hazard-map completeness, hazard classification readiness, hazard severity",
        "hazard_map_boundary_state=AwaitingEvidence",
        "hazard_map_complete_claimed=false",
        "hazard_classification_ready_claimed=false",
        "hazard_severity_closed_claimed=false",
        "hazard_mitigation_ready_claimed=false",
        "safety_review_ready_claimed=false",
        "runtime_hazard_ready_claimed=false",
        "implementation_approval_allowed=false",
        "deployment_allowed=false",
        "python scripts/validate_foundation_hazard_map_boundary.py",
    ),
    "docs/FOUNDATION_PROOF_REFERENCE_BOUNDARY.md": (
        "Foundation Proof Reference Boundary",
        "Witness packet: [`../examples/foundation_proof_reference_witness.awaiting_evidence.json`]",
        "Rule: Proof-reference preparation is a local planning boundary, not a",
        "No proof-reference completeness, proof coverage closure, evidence",
        "proof_reference_boundary_state=AwaitingEvidence",
        "proof_reference_complete_claimed=false",
        "proof_coverage_closed_claimed=false",
        "evidence_promotion_allowed=false",
        "terminal_closure_claimed=false",
        "verification_pass_claimed=false",
        "proof_approval_assigned=false",
        "runtime_proof_ready_claimed=false",
        "implementation_approval_allowed=false",
        "deployment_allowed=false",
        "python scripts/validate_foundation_proof_reference_boundary.py",
    ),
    "docs/FOUNDATION_GAP_REGISTER_BOUNDARY.md": (
        "Foundation Gap Register Boundary",
        "Witness packet: [`../examples/foundation_gap_register_witness.awaiting_evidence.json`]",
        "Rule: Gap-register preparation is a local planning boundary, not a",
        "No gap-register completeness, gap closure, priority closure, owner",
        "gap_register_boundary_state=AwaitingEvidence",
        "gap_register_complete_claimed=false",
        "gap_closure_claimed=false",
        "gap_priority_closed_claimed=false",
        "gap_owner_assigned=false",
        "remediation_ready_claimed=false",
        "roadmap_commitment_allowed=false",
        "implementation_approval_allowed=false",
        "deployment_allowed=false",
        "python scripts/validate_foundation_gap_register_boundary.py",
    ),
    "docs/FOUNDATION_DIFF_REVIEW_BOUNDARY.md": (
        "Foundation Diff Review Boundary",
        "Witness packet: [`../examples/foundation_diff_review_witness.awaiting_evidence.json`]",
        "Rule: Diff-review preparation is a local planning boundary, not a",
        "No diff-review completeness, diff scope closure, ownership assignment, staging",
        "diff_review_boundary_state=AwaitingEvidence",
        "diff_review_complete_claimed=false",
        "diff_scope_closed_claimed=false",
        "diff_ownership_assigned=false",
        "staging_allowed=false",
        "commit_allowed=false",
        "push_allowed=false",
        "pull_request_allowed=false",
        "source_control_publication_allowed=false",
        "deployment_allowed=false",
        "python scripts/validate_foundation_diff_review_boundary.py",
    ),
    "docs/FOUNDATION_CHANGE_HANDOFF_BOUNDARY.md": (
        "Foundation Change Handoff Boundary",
        "Witness packet: [`../examples/foundation_change_handoff_witness.awaiting_evidence.json`]",
        "Rule: Change-handoff preparation is a local planning boundary, not a",
        "No change-handoff completeness, changed-file review completeness, diff scope",
        "change_handoff_boundary_state=AwaitingEvidence",
        "change_handoff_complete_claimed=false",
        "changed_file_review_complete_claimed=false",
        "diff_scope_closed_claimed=false",
        "change_ownership_assigned=false",
        "validation_complete_claimed=false",
        "secret_clearance_claimed=false",
        "staging_allowed=false",
        "commit_allowed=false",
        "push_allowed=false",
        "pull_request_allowed=false",
        "source_control_publication_allowed=false",
        "deployment_allowed=false",
        "python scripts/validate_foundation_change_handoff_boundary.py",
    ),
    "docs/FOUNDATION_LOCAL_WORKSTATION_BOUNDARY.md": (
        "Foundation Local Workstation Boundary",
        "Witness packet: [`../examples/foundation_local_workstation_witness.awaiting_evidence.json`]",
        "Rule: Local-workstation preparation is a local planning boundary, not",
        "No local workstation verification, Python toolchain verification, Node",
        "local_workstation_boundary_state=AwaitingEvidence",
        "local_workstation_verified=false",
        "python_toolchain_verified=false",
        "dependency_install_allowed=false",
        "deployment_allowed=false",
    ),
    "docs/FOUNDATION_DOCUMENTATION_BOUNDARY.md": (
        "Foundation Documentation Boundary",
        "Witness packet: [`../examples/foundation_documentation_witness.awaiting_evidence.json`]",
        "Rule: Documentation preparation is a local planning boundary, not a readiness certificate.",
        "No documentation completeness claim, canonical-docs claim, public-launch copy",
        "documentation_boundary_state=AwaitingEvidence",
        "documentation_complete_claimed=false",
        "canonical_docs_claimed=false",
        "public_launch_copy_claimed=false",
        "external_publication_allowed=false",
        "deployment_allowed=false",
    ),
    "docs/FOUNDATION_PLAIN_LANGUAGE_STATUS_BOUNDARY.md": (
        "Foundation Plain-Language Status Boundary",
        "Witness packet: [`../examples/foundation_plain_language_status_witness.awaiting_evidence.json`]",
        "Rule: Plain-language status preparation is a local planning boundary, not a",
        "No plain-language completeness, non-technical comprehension proof, product",
        "plain_language_status_boundary_state=AwaitingEvidence",
        "plain_language_complete_claimed=false",
        "nontechnical_comprehension_proven=false",
        "product_readiness_claimed=false",
        "capability_availability_claimed=false",
        "real_task_execution_ready=false",
        "customer_readiness_claimed=false",
        "paid_use_ready_claimed=false",
        "money_movement_ready_claimed=false",
        "canonical_docs_claimed=false",
        "external_publication_allowed=false",
        "deployment_allowed=false",
        "python scripts/validate_foundation_plain_language_status_boundary.py",
    ),
    "docs/FOUNDATION_ACCESSIBILITY_LANGUAGE_BOUNDARY.md": (
        "Foundation Accessibility Language Boundary",
        "Witness packet: [`../examples/foundation_accessibility_language_witness.awaiting_evidence.json`]",
        "Rule: Accessibility/language preparation is a local planning boundary, not an accessibility-compliance, translation-readiness, localization-readiness, language-support, user-testing, publication, or deployment certificate.",
        "No accessibility compliance, WCAG conformance, screen-reader verification,",
        "accessibility_language_boundary_state=AwaitingEvidence",
        "accessibility_compliance_claimed=false",
        "wcag_conformance_claimed=false",
        "screen_reader_verified=false",
        "keyboard_navigation_verified=false",
        "mobile_accessibility_verified=false",
        "contrast_compliance_claimed=false",
        "translation_readiness_claimed=false",
        "localization_readiness_claimed=false",
        "mfidel_support_claimed=false",
        "amharic_support_claimed=false",
        "public_accessibility_statement_allowed=false",
        "external_user_testing_allowed=false",
        "personal_data_collection_allowed=false",
        "customer_access_allowed=false",
        "external_publication_allowed=false",
        "deployment_allowed=false",
        "python scripts/validate_foundation_accessibility_language_boundary.py",
    ),
    "docs/FOUNDATION_CAPABILITY_ROADMAP_BOUNDARY.md": (
        "Foundation Capability Roadmap Boundary",
        "Witness packet: [`../examples/foundation_capability_roadmap_witness.awaiting_evidence.json`]",
        "Rule: Capability-roadmap preparation is a local planning boundary, not a capability-availability, roadmap-commitment, delivery-date, customer, pilot, support, pricing, publication, money-movement, or deployment certificate.",
        "No capability inventory completeness, capability availability, roadmap",
        "capability_roadmap_boundary_state=AwaitingEvidence",
        "capability_inventory_complete_claimed=false",
        "capability_availability_claimed=false",
        "roadmap_commitment_claimed=false",
        "delivery_date_promised=false",
        "sequencing_final_claimed=false",
        "dependency_activation_allowed=false",
        "customer_commitment_allowed=false",
        "support_commitment_allowed=false",
        "money_movement_allowed=false",
        "external_publication_allowed=false",
        "deployment_allowed=false",
        "python scripts/validate_foundation_capability_roadmap_boundary.py",
    ),
    "docs/FOUNDATION_AGENTIC_MANAGEMENT_BOUNDARY.md": (
        "Foundation Agentic Management Boundary",
        "Witness packet: [`../examples/foundation_agentic_management_witness.awaiting_evidence.json`]",
        "Rule: Agentic-management preparation is a local planning boundary, not an autonomous-management, task-execution, delegation, scheduling, resource-allocation, approval-bypass, customer, money-movement, publication, or deployment certificate.",
        "No autonomous management authority, task execution authority, delegation",
        "agentic_management_boundary_state=AwaitingEvidence",
        "agentic_management_claimed=false",
        "autonomous_management_authority_claimed=false",
        "task_execution_authority_allowed=false",
        "delegation_activation_allowed=false",
        "scheduling_commitment_allowed=false",
        "resource_allocation_approved=false",
        "budget_commitment_allowed=false",
        "priority_final_claimed=false",
        "approval_bypass_allowed=false",
        "live_monitoring_claimed=false",
        "operator_replacement_claimed=false",
        "customer_commitment_allowed=false",
        "money_movement_allowed=false",
        "external_publication_allowed=false",
        "deployment_allowed=false",
        "python scripts/validate_foundation_agentic_management_boundary.py",
    ),
    "docs/FOUNDATION_OPERATIONS_RUNBOOK_BOUNDARY.md": (
        "Foundation Operations Runbook Boundary",
        "Witness packet: [`../examples/foundation_operations_runbook_witness.awaiting_evidence.json`]",
        "Rule: Operations/runbook preparation is a local planning boundary, not a runbook-execution, incident-response, monitoring, on-call, SLO, recovery-readiness, customer-support, publication, or deployment certificate.",
        "No runbook execution, incident-response readiness, monitoring readiness,",
        "operations_runbook_boundary_state=AwaitingEvidence",
        "operations_runbook_claimed=false",
        "runbook_execution_allowed=false",
        "incident_response_ready=false",
        "monitoring_ready=false",
        "alerting_ready=false",
        "on_call_ready=false",
        "slo_claimed=false",
        "recovery_ready=false",
        "operational_graph_complete=false",
        "mil_runbook_admission_ready=false",
        "customer_support_operations_allowed=false",
        "external_publication_allowed=false",
        "deployment_allowed=false",
        "python scripts/validate_foundation_operations_runbook_boundary.py",
    ),
    "docs/FOUNDATION_CLAIM_BOUNDARY.md": (
        "Foundation Claim Boundary",
        "Witness packet: [`../examples/foundation_claim_boundary_witness.awaiting_evidence.json`]",
        "Rule: Claim-boundary preparation is a local planning boundary, not a claim-promotion certificate.",
        "No production-health claim, endpoint-readiness claim, customer-readiness claim,",
        "claim_boundary_state=AwaitingEvidence",
        "production_health_claimed=false",
        "endpoint_readiness_claimed=false",
        "customer_readiness_claimed=false",
        "external_publication_allowed=false",
        "deployment_allowed=false",
    ),
    "docs/FOUNDATION_WEBSITE_POSTURE_BOUNDARY.md": (
        "Foundation Website Posture Boundary",
        "Witness packet: [`../examples/foundation_website_posture_witness.awaiting_evidence.json`]",
        "Rule: Website-posture preparation is a local planning boundary, not a website publication or access-opening certificate.",
        "No website mutation, external website publication, access invitation, waitlist",
        "website_posture_boundary_state=AwaitingEvidence",
        "website_mutation_allowed=false",
        "access_invitation_allowed=false",
        "waitlist_open=false",
        "external_publication_allowed=false",
        "deployment_allowed=false",
    ),
    "docs/FOUNDATION_RESEARCH_NOTEBOOK_BOUNDARY.md": (
        "Foundation Research Notebook Boundary",
        "Witness packet: [`../examples/foundation_research_notebook_witness.awaiting_evidence.json`]",
        "Rule: Research-notebook preparation is a local planning boundary, not a patent, secrecy, validation, publication, market, or deployment certificate.",
        "No patent protection, trade-secret protection, scientific validation,",
        "research_notebook_boundary_state=AwaitingEvidence",
        "patent_protection_claimed=false",
        "trade_secret_protection_claimed=false",
        "scientific_validation_claimed=false",
        "secret_evidence_claimed=false",
        "deployment_allowed=false",
    ),
    "docs/FOUNDATION_MARKET_RESEARCH_BOUNDARY.md": (
        "Foundation Market Research Boundary",
        "Witness packet: [`../examples/foundation_market_research_witness.awaiting_evidence.json`]",
        "Rule: Market-research preparation is a local planning boundary, not customer research, product-market validation, competitor superiority, pricing readiness, public offer, investor material, or deployment evidence.",
        "No customer research, survey publication, waitlist opening, outreach, market",
        "market_research_boundary_state=AwaitingEvidence",
        "customer_research_allowed=false",
        "survey_publication_allowed=false",
        "waitlist_allowed=false",
        "market_validation_claimed=false",
        "product_market_fit_claimed=false",
        "competitor_superiority_claimed=false",
        "pricing_claim_allowed=false",
        "investor_material_allowed=false",
        "personal_data_collection_allowed=false",
        "customer_access_allowed=false",
        "money_movement_allowed=false",
        "deployment_allowed=false",
        "python scripts/validate_foundation_market_research_boundary.py",
    ),
    "docs/FOUNDATION_EVIDENCE_LEDGER_BOUNDARY.md": (
        "Foundation Evidence Ledger Boundary",
        "Witness packet: [`../examples/foundation_evidence_ledger_witness.awaiting_evidence.json`]",
        "Rule: Evidence-ledger preparation is a local planning boundary, not a terminal-closure, readiness, legal, patent, customer, publication, paid-launch, secret-evidence, or deployment certificate.",
        "No terminal closure, readiness promotion, legal clearance, patent protection,",
        "evidence_ledger_boundary_state=AwaitingEvidence",
        "evidence_promotion_allowed=false",
        "terminal_closure_claimed=false",
        "readiness_claimed=false",
        "secret_evidence_recorded=false",
        "deployment_allowed=false",
    ),
    "docs/FOUNDATION_DECISION_JOURNAL_BOUNDARY.md": (
        "Foundation Decision Journal Boundary",
        "Witness packet: [`../examples/foundation_decision_journal_witness.awaiting_evidence.json`]",
        "Rule: Decision-journal preparation is a local planning boundary, not a decision-execution, commitment, authority, legal, company, patent, spending, publication, or deployment certificate.",
        "No decision execution, irreversible action, roadmap commitment, deadline",
        "decision_journal_boundary_state=AwaitingEvidence",
        "decision_execution_allowed=false",
        "irreversible_action_allowed=false",
        "roadmap_commitment_claimed=false",
        "deadline_promise_claimed=false",
        "spending_allowed=false",
        "deployment_allowed=false",
    ),
    "docs/FOUNDATION_NEXT_ACTION_BOUNDARY.md": (
        "Foundation Next Action Boundary",
        "Witness packet: [`../examples/foundation_next_action_witness.awaiting_evidence.json`]",
        "Rule: Next-action preparation is a local continuation boundary, not permission",
        "No broad continuation execution, external action, deployment, external",
        "next_action_boundary_state=AwaitingEvidence",
        "broad_continuation_execution_allowed=false",
        "external_action_allowed=false",
        "deployment_allowed=false",
        "spending_allowed=false",
        "source_control_publication_allowed=false",
        "deadline_promise_claimed=false",
        "python scripts/validate_foundation_next_action_boundary.py",
    ),
    "docs/FOUNDATION_TEST_EVIDENCE_BOUNDARY.md": (
        "Foundation Test Evidence Boundary",
        "Witness packet: [`../examples/foundation_test_evidence_witness.awaiting_evidence.json`]",
        "Rule: Test-evidence preparation is a local planning boundary, not a full-test",
        "No full-test-pass, complete-coverage, CI-parity, release-readiness",
        "test_evidence_boundary_state=AwaitingEvidence",
        "full_test_pass_claimed=false",
        "complete_coverage_claimed=false",
        "ci_parity_claimed=false",
        "release_readiness_claimed=false",
        "deployment_readiness_claimed=false",
        "security_clearance_claimed=false",
        "secret_clearance_claimed=false",
        "customer_readiness_claimed=false",
        "legal_clearance_claimed=false",
        "terminal_closure_claimed=false",
        "external_publication_allowed=false",
        "deployment_allowed=false",
        "python scripts/validate_foundation_test_evidence_boundary.py",
    ),
    "docs/FOUNDATION_PRIVATE_RECOVERY_BOUNDARY.md": (
        "Foundation Private Recovery Boundary",
        "Descriptor: [`../examples/foundation_private_recovery_inventory.redacted.json`]",
        "No secret values are permitted in Git.",
        "Private inventory remains outside this repository.",
        "Do not store recovery codes, passwords, provider account IDs, DNS targets,",
        "Public-safe state is `AwaitingEvidence` until the operator completes the private",
    ),
    "docs/FOUNDATION_SECRETS_CREDENTIALS_BOUNDARY.md": (
        "Foundation Secrets Credentials Boundary",
        "Witness packet: [`../examples/foundation_secrets_credentials_witness.awaiting_evidence.json`]",
        "Rule: Secrets/credentials preparation is a local planning boundary, not permission to store or activate real credentials.",
        "No real-secret storage, credential activation, provider-account binding, API",
        "secrets_credentials_boundary_state=AwaitingEvidence",
        "real_secret_storage_allowed=false",
        "credential_activation_allowed=false",
        "api_key_creation_allowed=false",
        "deployment_allowed=false",
    ),
    "docs/FOUNDATION_SECURITY_BASELINE_BOUNDARY.md": (
        "Foundation Security Baseline Boundary",
        "Witness packet: [`../examples/foundation_security_baseline_witness.awaiting_evidence.json`]",
        "Rule: Security-baseline preparation is a local planning boundary, not",
        "No security baseline verification, secret scan pass, vulnerability scan pass,",
        "security_baseline_boundary_state=AwaitingEvidence",
        "security_baseline_verified=false",
        "secret_scan_pass_claimed=false",
        "vulnerability_scan_pass_claimed=false",
        "deployment_allowed=false",
    ),
    "docs/FOUNDATION_COST_BUDGET_BOUNDARY.md": (
        "Foundation Cost Budget Boundary",
        "Witness packet: [`../examples/foundation_cost_budget_witness.awaiting_evidence.json`]",
        "Rule: Cost/budget preparation is a local planning boundary, not permission to spend money.",
        "No spending authorization, paid infrastructure activation, provider billing",
        "cost_budget_boundary_state=AwaitingEvidence",
        "spending_allowed=false",
        "paid_infrastructure_allowed=false",
        "provider_billing_allowed=false",
        "deployment_allowed=false",
    ),
    "docs/FOUNDATION_PAYMENT_PROVIDER_BOUNDARY.md": (
        "Foundation Payment Provider Boundary",
        "Witness packet: [`../examples/foundation_payment_provider_witness.awaiting_evidence.json`]",
        "Rule: Payment-provider preparation is a local planning boundary, not permission",
        "No payment-provider activation, provider-account binding, merchant-onboarding",
        "payment_provider_boundary_state=AwaitingEvidence",
        "payment_provider_activation_allowed=false",
        "provider_account_binding_allowed=false",
        "merchant_onboarding_claimed=false",
        "kyc_readiness_claimed=false",
        "tax_readiness_claimed=false",
        "payment_method_collection_allowed=false",
        "live_charge_allowed=false",
        "refund_execution_allowed=false",
        "payout_settlement_allowed=false",
        "webhook_activation_allowed=false",
        "checkout_publication_allowed=false",
        "money_movement_allowed=false",
        "customer_payment_access_allowed=false",
        "external_publication_allowed=false",
        "deployment_allowed=false",
        "python scripts/validate_foundation_payment_provider_boundary.py",
    ),
    "docs/FOUNDATION_RUNTIME_ENVIRONMENT_BOUNDARY.md": (
        "Foundation Runtime Environment Boundary",
        "Witness packet: [`../examples/foundation_runtime_environment_witness.awaiting_evidence.json`]",
        "Rule: Runtime/environment preparation is a local planning boundary, not permission to claim runtime readiness.",
        "No local runtime verification, workstation repeatability verification,",
        "runtime_environment_boundary_state=AwaitingEvidence",
        "local_runtime_verified=false",
        "workstation_repeatability_verified=false",
        "dependency_install_verified=false",
        "deployment_allowed=false",
    ),
    "docs/FOUNDATION_BACKUP_EXPORT_BOUNDARY.md": (
        "Foundation Backup Export Boundary",
        "Witness packet: [`../examples/foundation_backup_export_witness.awaiting_evidence.json`]",
        "Rule: Backup/export preparation is a local planning boundary, not permission to move repository or private data.",
        "No backup execution, cloud backup activation, external export, public archive",
        "backup_export_boundary_state=AwaitingEvidence",
        "backup_execution_allowed=false",
        "cloud_backup_allowed=false",
        "external_export_allowed=false",
        "deployment_allowed=false",
    ),
    "docs/FOUNDATION_DEPLOYMENT_DEFERRAL_BOUNDARY.md": (
        "Foundation Deployment Deferral Boundary",
        "Witness packet: [`../examples/foundation_deployment_deferral_witness.awaiting_evidence.json`]",
        "Rule: Deployment deferral is a local planning boundary, not a deployment plan, production-health certificate, customer-access approval, spending approval, credential-use approval, publication approval, or readiness certificate.",
        "No deployment plan approval, cloud activation, public endpoint, production",
        "deployment_deferral_boundary_state=AwaitingEvidence",
        "deployment_plan_approved=false",
        "cloud_activation_allowed=false",
        "public_endpoint_allowed=false",
        "deployment_allowed=false",
    ),
    "docs/FOUNDATION_EXTERNAL_INFRASTRUCTURE_BOUNDARY.md": (
        "Foundation External Infrastructure Boundary",
        "Witness packet: [`../examples/foundation_external_infrastructure_witness.awaiting_evidence.json`]",
        "Rule: External-infrastructure preparation is a local planning boundary, not an",
        "No external-infrastructure completeness, DNS authority verification, DNS target",
        "external_infrastructure_boundary_state=AwaitingEvidence",
        "external_infrastructure_complete_claimed=false",
        "dns_authority_verified=false",
        "dns_target_bound=false",
        "dns_mutation_allowed=false",
        "runtime_host_provisioned=false",
        "managed_database_provisioned=false",
        "secret_placement_verified=false",
        "endpoint_reachability_claimed=false",
        "repository_variable_binding_allowed=false",
        "workflow_dispatch_allowed=false",
        "paid_infrastructure_allowed=false",
        "deployment_allowed=false",
        "python scripts/validate_foundation_external_infrastructure_boundary.py",
    ),
    "docs/FOUNDATION_RUNTIME_SECRET_HANDOFF_REHEARSAL_BOUNDARY.md": (
        "Foundation Runtime Secret Handoff Rehearsal Boundary",
        "Witness packet: [`../examples/foundation_runtime_secret_handoff_rehearsal_witness.awaiting_evidence.json`]",
        "Rule: Runtime secret handoff rehearsal is a local gate-label map",
        "No runtime witness secret-name claim, runtime conformance secret-name claim,",
        "runtime_secret_handoff_rehearsal_state=AwaitingEvidence",
        "runtime_witness_secret_name_recorded=false",
        "runtime_conformance_secret_name_recorded=false",
        "deployment_witness_secret_name_recorded=false",
        "secret_value_recorded=false",
        "ignored_local_handoff_path_recorded=false",
        "secret_manager_target_recorded=false",
        "operator_identity_recorded=false",
        "dual_control_verified=false",
        "secret_presence_attestation_claimed=false",
        "secret_rotation_claimed=false",
        "secret_revocation_claimed=false",
        "workflow_secret_mount_claimed=false",
        "runtime_env_binding_claimed=false",
        "preflight_secret_gate_pass_claimed=false",
        "repository_secret_binding_allowed=false",
        "runtime_secret_store_binding_allowed=false",
        "workflow_dispatch_allowed=false",
        "artifact_publication_allowed=false",
        "readiness_claimed=false",
        "customer_access_allowed=false",
        "personal_data_collection_allowed=false",
        "money_movement_allowed=false",
        "legal_clearance_claimed=false",
        "company_formation_claimed=false",
        "patent_claimed=false",
        "external_publication_allowed=false",
        "deployment_allowed=false",
        "python scripts/validate_foundation_runtime_secret_handoff_rehearsal_boundary.py",
    ),
    "docs/FOUNDATION_RUNTIME_WITNESS_DEFERRAL_BOUNDARY.md": (
        "Foundation Runtime Witness Deferral Boundary",
        "Witness packet: [`../examples/foundation_runtime_witness_deferral_witness.awaiting_evidence.json`]",
        "Rule: Runtime witness deferral is a local stop-rule packet",
        "No runtime witness creation, runtime witness secret binding, endpoint probe,",
        "runtime_witness_deferral_state=AwaitingEvidence",
        "runtime_witness_created=false",
        "runtime_witness_secret_bound=false",
        "runtime_witness_endpoint_probe_allowed=false",
        "runtime_witness_payload_recorded=false",
        "runtime_witness_signature_verified=false",
        "runtime_witness_publication_allowed=false",
        "runtime_conformance_claimed=false",
        "deployment_witness_collection_allowed=false",
        "evidence_ledger_append_allowed=false",
        "readiness_claimed=false",
        "customer_access_allowed=false",
        "personal_data_collection_allowed=false",
        "money_movement_allowed=false",
        "legal_clearance_claimed=false",
        "company_formation_claimed=false",
        "patent_claimed=false",
        "external_publication_allowed=false",
        "deployment_allowed=false",
        "python scripts/validate_foundation_runtime_witness_deferral_boundary.py",
    ),
    "docs/FOUNDATION_PRODUCTION_DEPENDENCY_EVIDENCE_REHEARSAL_BOUNDARY.md": (
        "Foundation Production Dependency Evidence Rehearsal Boundary",
        "Witness packet: [`../examples/foundation_production_dependency_evidence_rehearsal_witness.awaiting_evidence.json`]",
        "Rule: Production dependency evidence rehearsal is a local evidence-label map",
        "No recovery witness closure claim, production image value, runtime host value,",
        "production_dependency_evidence_rehearsal_state=AwaitingEvidence",
        "recovery_witness_closed_claimed=false",
        "production_image_value_recorded=false",
        "runtime_host_value_recorded=false",
        "managed_postgres_value_recorded=false",
        "schema_application_claimed=false",
        "secret_store_value_recorded=false",
        "deploy_env_value_recorded=false",
        "release_preflight_pass_claimed=false",
        "persistence_check_pass_claimed=false",
        "host_firewall_pass_claimed=false",
        "tls_certificate_value_recorded=false",
        "rollback_path_verified=false",
        "private_runtime_witness_value_recorded=false",
        "dns_authority_verified=false",
        "runtime_witness_registry_closure_claimed=false",
        "external_evidence_collected=false",
        "api_provisioning_allowed=false",
        "dns_publication_allowed=false",
        "dns_target_selection_allowed=false",
        "repository_variable_binding_allowed=false",
        "workflow_dispatch_allowed=false",
        "artifact_publication_allowed=false",
        "readiness_claimed=false",
        "customer_access_allowed=false",
        "personal_data_collection_allowed=false",
        "money_movement_allowed=false",
        "legal_clearance_claimed=false",
        "company_formation_claimed=false",
        "patent_claimed=false",
        "external_publication_allowed=false",
        "deployment_allowed=false",
        "python scripts/validate_foundation_production_dependency_evidence_rehearsal_boundary.py",
    ),
    "docs/FOUNDATION_EXTERNAL_EVIDENCE_ACCEPTANCE_REHEARSAL_BOUNDARY.md": (
        "Foundation External Evidence Acceptance Rehearsal Boundary",
        "Witness packet: [`../examples/foundation_external_evidence_acceptance_rehearsal_witness.awaiting_evidence.json`]",
        "Rule: External evidence acceptance rehearsal is a local gate-label map",
        "No external evidence collection, source-authority verification claim,",
        "external_evidence_acceptance_rehearsal_state=AwaitingEvidence",
        "external_evidence_collected=false",
        "source_authority_verified=false",
        "evidence_owner_verified=false",
        "redaction_pass_claimed=false",
        "freshness_pass_claimed=false",
        "chain_of_custody_verified=false",
        "schema_validation_pass_claimed=false",
        "contradiction_check_pass_claimed=false",
        "replay_pass_claimed=false",
        "acceptance_decision_recorded=false",
        "rejection_decision_recorded=false",
        "ledger_append_allowed=false",
        "readiness_promotion_allowed=false",
        "api_provisioning_allowed=false",
        "dns_publication_allowed=false",
        "workflow_dispatch_allowed=false",
        "artifact_publication_allowed=false",
        "public_health_declaration_allowed=false",
        "deployment_witness_publication_allowed=false",
        "customer_access_allowed=false",
        "personal_data_collection_allowed=false",
        "money_movement_allowed=false",
        "legal_clearance_claimed=false",
        "company_formation_claimed=false",
        "patent_claimed=false",
        "external_publication_allowed=false",
        "deployment_allowed=false",
        "python scripts/validate_foundation_external_evidence_acceptance_rehearsal_boundary.py",
    ),
    "docs/FOUNDATION_DEPLOYMENT_UPSTREAM_API_GATE_REHEARSAL_BOUNDARY.md": (
        "Foundation Deployment Upstream API Gate Rehearsal Boundary",
        "Witness packet: [`../examples/foundation_deployment_upstream_api_gate_rehearsal_witness.awaiting_evidence.json`]",
        "Rule: Deployment upstream API gate rehearsal is a local gate-label map",
        "No upstream API readiness claim, upstream reporter execution claim,",
        "deployment_upstream_api_gate_rehearsal_state=AwaitingEvidence",
        "upstream_api_ready_claimed=false",
        "upstream_reporter_executed=false",
        "require_ready_pass_claimed=false",
        "target_gateway_url_value_recorded=false",
        "production_image_value_recorded=false",
        "runtime_host_value_recorded=false",
        "managed_postgres_value_recorded=false",
        "schema_application_value_recorded=false",
        "secret_store_value_recorded=false",
        "deploy_env_value_recorded=false",
        "release_preflight_value_recorded=false",
        "persistence_check_value_recorded=false",
        "host_firewall_value_recorded=false",
        "tls_certificate_value_recorded=false",
        "rollback_path_value_recorded=false",
        "private_runtime_witness_value_recorded=false",
        "dns_authority_value_recorded=false",
        "runtime_witness_closure_claimed=false",
        "api_provisioning_allowed=false",
        "dns_publication_allowed=false",
        "dns_target_selection_allowed=false",
        "repository_variable_binding_allowed=false",
        "workflow_dispatch_allowed=false",
        "artifact_publication_allowed=false",
        "readiness_claimed=false",
        "customer_access_allowed=false",
        "personal_data_collection_allowed=false",
        "money_movement_allowed=false",
        "legal_clearance_claimed=false",
        "company_formation_claimed=false",
        "patent_claimed=false",
        "external_publication_allowed=false",
        "deployment_allowed=false",
        "upstream_reporter_command_label",
        "target_gateway_url_label",
        "runtime_witness_closure_gate_label",
        "api_provisioning_stop_rule_label",
        "dns_publication_stop_rule_label",
        "operator_reassessment_gate",
        "python scripts/validate_foundation_deployment_upstream_api_gate_rehearsal_boundary.py",
    ),
    "docs/FOUNDATION_DEPLOYMENT_WITNESS_INPUT_BOUNDARY.md": (
        "Foundation Deployment Witness Input Boundary",
        "Witness packet: [`../examples/foundation_deployment_witness_input_witness.awaiting_evidence.json`]",
        "Rule: Deployment witness inputs are local placeholders only.",
        "No secret value, repository variable value, DNS mutation",
        "deployment_witness_input_state=AwaitingEvidence",
        "runtime_witness_secret_value_allowed=false",
        "runtime_conformance_secret_value_allowed=false",
        "gateway_url_value_allowed=false",
        "expected_runtime_env_value_allowed=false",
        "repository_variable_binding_allowed=false",
        "dns_mutation_allowed=false",
        "endpoint_reachability_claimed=false",
        "workflow_dispatch_allowed=false",
        "witness_artifact_publication_allowed=false",
        "deployment_status_promotion_allowed=false",
        "customer_access_allowed=false",
        "personal_data_collection_allowed=false",
        "money_movement_allowed=false",
        "legal_clearance_claimed=false",
        "company_formation_claimed=false",
        "patent_claimed=false",
        "external_publication_allowed=false",
        "deployment_allowed=false",
        "python scripts/validate_foundation_deployment_witness_input_boundary.py",
    ),
    "docs/FOUNDATION_DEPLOYMENT_WITNESS_PREFLIGHT_REHEARSAL_BOUNDARY.md": (
        "Foundation Deployment Witness Preflight Rehearsal Boundary",
        "Witness packet: [`../examples/foundation_deployment_witness_preflight_rehearsal_witness.awaiting_evidence.json`]",
        "Rule: Preflight rehearsal is a local checklist",
        "No live preflight execution, live URL value, DNS probe",
        "deployment_witness_preflight_rehearsal_state=AwaitingEvidence",
        "live_preflight_execution_allowed=false",
        "live_gateway_url_value_allowed=false",
        "dns_probe_allowed=false",
        "endpoint_probe_allowed=false",
        "secret_value_allowed=false",
        "secret_presence_claimed=false",
        "repository_variable_binding_allowed=false",
        "workflow_dispatch_allowed=false",
        "readiness_report_claimed=false",
        "witness_artifact_publication_allowed=false",
        "deployment_status_promotion_allowed=false",
        "customer_access_allowed=false",
        "personal_data_collection_allowed=false",
        "money_movement_allowed=false",
        "legal_clearance_claimed=false",
        "company_formation_claimed=false",
        "patent_claimed=false",
        "external_publication_allowed=false",
        "deployment_allowed=false",
        "python scripts/validate_foundation_deployment_witness_preflight_rehearsal_boundary.py",
    ),
    "docs/FOUNDATION_DEPLOYMENT_WITNESS_DISPATCH_REHEARSAL_BOUNDARY.md": (
        "Foundation Deployment Witness Dispatch Rehearsal Boundary",
        "Witness packet: [`../examples/foundation_deployment_witness_dispatch_rehearsal_witness.awaiting_evidence.json`]",
        "Rule: Dispatch rehearsal is a local stop-rule map",
        "No workflow dispatch, GitHub API mutation, manual workflow execution",
        "deployment_witness_dispatch_rehearsal_state=AwaitingEvidence",
        "workflow_dispatch_allowed=false",
        "github_api_mutation_allowed=false",
        "manual_workflow_execution_allowed=false",
        "gateway_url_value_allowed=false",
        "expected_environment_value_recorded=false",
        "workflow_ref_value_recorded=false",
        "workflow_run_id_recorded=false",
        "dispatch_receipt_recorded=false",
        "secret_value_allowed=false",
        "secret_presence_claimed=false",
        "repository_variable_binding_allowed=false",
        "workflow_run_claimed=false",
        "artifact_publication_allowed=false",
        "deployment_claim_published_claimed=false",
        "deployment_status_promotion_allowed=false",
        "operator_approval_claimed=false",
        "customer_access_allowed=false",
        "personal_data_collection_allowed=false",
        "money_movement_allowed=false",
        "legal_clearance_claimed=false",
        "company_formation_claimed=false",
        "patent_claimed=false",
        "external_publication_allowed=false",
        "deployment_allowed=false",
        "python scripts/validate_foundation_deployment_witness_dispatch_rehearsal_boundary.py",
    ),
    "docs/FOUNDATION_DEPLOYMENT_WITNESS_ARTIFACT_VALIDATION_REHEARSAL_BOUNDARY.md": (
        "Foundation Deployment Witness Artifact Validation Rehearsal Boundary",
        "Witness packet: [`../examples/foundation_deployment_witness_artifact_validation_rehearsal_witness.awaiting_evidence.json`]",
        "Rule: Deployment witness artifact validation rehearsal is a local map",
        "No artifact download, artifact path value, artifact id value",
        "deployment_witness_artifact_validation_rehearsal_state=AwaitingEvidence",
        "artifact_download_allowed=false",
        "artifact_path_recorded=false",
        "artifact_id_recorded=false",
        "artifact_digest_recorded=false",
        "artifact_schema_validation_claimed=false",
        "deployment_claim_published_claimed=false",
        "runtime_hmac_verified=false",
        "conformance_hmac_verified=false",
        "public_health_endpoint_claimed=false",
        "closure_validation_claimed=false",
        "evidence_ledger_append_allowed=false",
        "workflow_run_claimed=false",
        "operator_approval_claimed=false",
        "customer_access_allowed=false",
        "personal_data_collection_allowed=false",
        "money_movement_allowed=false",
        "legal_clearance_claimed=false",
        "company_formation_claimed=false",
        "patent_claimed=false",
        "external_publication_allowed=false",
        "deployment_allowed=false",
        "python scripts/validate_foundation_deployment_witness_artifact_validation_rehearsal_boundary.py",
    ),
    "docs/FOUNDATION_DEPLOYMENT_WITNESS_EVIDENCE_HANDOFF_BOUNDARY.md": (
        "Foundation Deployment Witness Evidence Handoff Boundary",
        "Witness packet: [`../examples/foundation_deployment_witness_evidence_handoff_witness.awaiting_evidence.json`]",
        "Rule: Deployment witness evidence handoff is a local list of future evidence",
        "No live evidence receipt, live URL value, DNS proof",
        "deployment_witness_evidence_handoff_state=AwaitingEvidence",
        "live_evidence_receipt_recorded=false",
        "live_gateway_url_value_allowed=false",
        "dns_proof_claimed=false",
        "endpoint_proof_claimed=false",
        "secret_presence_claimed=false",
        "repository_variable_binding_allowed=false",
        "workflow_run_claimed=false",
        "witness_artifact_publication_allowed=false",
        "deployment_status_approval_claimed=false",
        "operator_approval_claimed=false",
        "customer_access_allowed=false",
        "personal_data_collection_allowed=false",
        "money_movement_allowed=false",
        "legal_clearance_claimed=false",
        "company_formation_claimed=false",
        "patent_claimed=false",
        "external_publication_allowed=false",
        "deployment_allowed=false",
        "python scripts/validate_foundation_deployment_witness_evidence_handoff_boundary.py",
    ),
    "docs/FOUNDATION_DEPLOYMENT_WITNESS_EVIDENCE_LEDGER_ROUTING_BOUNDARY.md": (
        "Foundation Deployment Witness Evidence Ledger Routing Boundary",
        "Witness packet: [`../examples/foundation_deployment_witness_evidence_ledger_routing_witness.awaiting_evidence.json`]",
        "Rule: Deployment witness evidence ledger routing is a local route map of future",
        "No evidence-ledger append, live evidence reference, ledger promotion",
        "deployment_witness_evidence_ledger_routing_state=AwaitingEvidence",
        "evidence_ledger_append_allowed=false",
        "live_evidence_reference_allowed=false",
        "ledger_promotion_allowed=false",
        "terminal_closure_claimed=false",
        "readiness_claimed=false",
        "dns_proof_claimed=false",
        "endpoint_proof_claimed=false",
        "secret_presence_claimed=false",
        "workflow_run_claimed=false",
        "artifact_publication_allowed=false",
        "deployment_status_approval_claimed=false",
        "operator_approval_claimed=false",
        "customer_access_allowed=false",
        "personal_data_collection_allowed=false",
        "money_movement_allowed=false",
        "legal_clearance_claimed=false",
        "company_formation_claimed=false",
        "patent_claimed=false",
        "external_publication_allowed=false",
        "deployment_allowed=false",
        "python scripts/validate_foundation_deployment_witness_evidence_ledger_routing_boundary.py",
    ),
    "docs/FOUNDATION_GATEWAY_DNS_TARGET_BINDING_REHEARSAL_BOUNDARY.md": (
        "Foundation Gateway DNS Target Binding Rehearsal Boundary",
        "Witness packet: [`../examples/foundation_gateway_dns_target_binding_rehearsal_witness.awaiting_evidence.json`]",
        "Rule: Gateway DNS target binding rehearsal is a local question map for a later",
        "No live DNS target value, gateway URL value, provider account value",
        "gateway_dns_target_binding_rehearsal_state=AwaitingEvidence",
        "candidate_target_value_recorded=false",
        "gateway_url_recorded=false",
        "provider_account_recorded=false",
        "repository_variable_bound=false",
        "dns_record_published=false",
        "dns_resolution_claimed=false",
        "endpoint_reachability_claimed=false",
        "secret_presence_claimed=false",
        "workflow_dispatch_allowed=false",
        "artifact_publication_allowed=false",
        "operator_approval_claimed=false",
        "readiness_claimed=false",
        "customer_access_allowed=false",
        "personal_data_collection_allowed=false",
        "money_movement_allowed=false",
        "legal_clearance_claimed=false",
        "company_formation_claimed=false",
        "patent_claimed=false",
        "external_publication_allowed=false",
        "deployment_allowed=false",
        "MULLU_GATEWAY_DNS_TARGET",
        "MULLU_GATEWAY_URL",
        "MULLU_EXPECTED_RUNTIME_ENV",
        "python scripts/validate_foundation_gateway_dns_target_binding_rehearsal_boundary.py",
    ),
    "docs/FOUNDATION_GATEWAY_DNS_PUBLICATION_REHEARSAL_BOUNDARY.md": (
        "Foundation Gateway DNS Publication Rehearsal Boundary",
        "Witness packet: [`../examples/foundation_gateway_dns_publication_rehearsal_witness.awaiting_evidence.json`]",
        "Rule: Gateway DNS publication rehearsal is a local stop-rule map for a later",
        "No DNS provider account value, DNS zone value, DNS record name value",
        "gateway_dns_publication_rehearsal_state=AwaitingEvidence",
        "dns_provider_account_recorded=false",
        "dns_zone_value_recorded=false",
        "dns_record_name_recorded=false",
        "dns_record_type_value_recorded=false",
        "dns_record_value_recorded=false",
        "ttl_value_recorded=false",
        "dns_mutation_allowed=false",
        "repository_variable_bound=false",
        "workflow_dispatch_allowed=false",
        "dns_propagation_claimed=false",
        "dns_rollback_claimed=false",
        "dns_resolution_claimed=false",
        "endpoint_reachability_claimed=false",
        "artifact_publication_allowed=false",
        "operator_approval_claimed=false",
        "readiness_claimed=false",
        "customer_access_allowed=false",
        "personal_data_collection_allowed=false",
        "money_movement_allowed=false",
        "legal_clearance_claimed=false",
        "company_formation_claimed=false",
        "patent_claimed=false",
        "external_publication_allowed=false",
        "deployment_allowed=false",
        "target_binding_receipt_dependency_label",
        "dns_provider_boundary_label",
        "dns_zone_boundary_label",
        "record_name_publication_label",
        "record_type_publication_label",
        "record_value_publication_label",
        "ttl_publication_label",
        "pre_publication_require_ready_gate_label",
        "dry_run_publication_command_label",
        "post_publication_resolution_gate_label",
        "dns_rollback_label",
        "operator_reassessment_gate",
        "python scripts/validate_foundation_gateway_dns_publication_rehearsal_boundary.py",
    ),
    "docs/FOUNDATION_GATEWAY_DNS_RESOLUTION_RECEIPT_REHEARSAL_BOUNDARY.md": (
        "Foundation Gateway DNS Resolution Receipt Rehearsal Boundary",
        "Witness packet: [`../examples/foundation_gateway_dns_resolution_receipt_rehearsal_witness.awaiting_evidence.json`]",
        "Rule: Gateway DNS resolution receipt rehearsal is a local question map for a",
        "No live DNS query, host value, gateway URL value, resolved address",
        "gateway_dns_resolution_receipt_rehearsal_state=AwaitingEvidence",
        "live_dns_query_allowed=false",
        "host_value_recorded=false",
        "gateway_url_recorded=false",
        "resolved_address_recorded=false",
        "resolver_error_proof_claimed=false",
        "dns_resolution_claimed=false",
        "dns_receipt_written=false",
        "endpoint_reachability_claimed=false",
        "repository_variable_bound=false",
        "secret_presence_claimed=false",
        "workflow_dispatch_allowed=false",
        "artifact_publication_allowed=false",
        "operator_approval_claimed=false",
        "readiness_claimed=false",
        "customer_access_allowed=false",
        "personal_data_collection_allowed=false",
        "money_movement_allowed=false",
        "legal_clearance_claimed=false",
        "company_formation_claimed=false",
        "patent_claimed=false",
        "external_publication_allowed=false",
        "deployment_allowed=false",
        "dns_query_scope_question",
        "resolver_context_question",
        "resolved_address_set_question",
        "resolver_error_state_question",
        "ttl_observation_question",
        "receipt_timestamp_question",
        "target_binding_dependency_question",
        "endpoint_preflight_dependency_question",
        "publication_stop_rule_question",
        "operator_reassessment_gate",
        "python scripts/validate_foundation_gateway_dns_resolution_receipt_rehearsal_boundary.py",
    ),
    "docs/FOUNDATION_GATEWAY_ENDPOINT_REACHABILITY_REHEARSAL_BOUNDARY.md": (
        "Foundation Gateway Endpoint Reachability Rehearsal Boundary",
        "Witness packet: [`../examples/foundation_gateway_endpoint_reachability_rehearsal_witness.awaiting_evidence.json`]",
        "Rule: Gateway endpoint reachability rehearsal is a local question map for a",
        "No endpoint probe, gateway URL value, HTTP status value, response digest",
        "gateway_endpoint_reachability_rehearsal_state=AwaitingEvidence",
        "live_endpoint_probe_allowed=false",
        "gateway_url_recorded=false",
        "http_status_recorded=false",
        "response_digest_recorded=false",
        "response_body_recorded=false",
        "runtime_witness_payload_recorded=false",
        "runtime_conformance_payload_recorded=false",
        "production_evidence_payload_recorded=false",
        "capability_evidence_payload_recorded=false",
        "audit_verification_payload_recorded=false",
        "proof_verification_payload_recorded=false",
        "deployment_witness_collected=false",
        "public_health_declared=false",
        "secret_presence_claimed=false",
        "workflow_dispatch_allowed=false",
        "artifact_publication_allowed=false",
        "operator_approval_claimed=false",
        "readiness_claimed=false",
        "customer_access_allowed=false",
        "personal_data_collection_allowed=false",
        "money_movement_allowed=false",
        "legal_clearance_claimed=false",
        "company_formation_claimed=false",
        "patent_claimed=false",
        "external_publication_allowed=false",
        "deployment_allowed=false",
        "health_endpoint_probe_question",
        "gateway_witness_endpoint_question",
        "runtime_conformance_endpoint_question",
        "endpoint_http_status_question",
        "endpoint_response_digest_question",
        "endpoint_body_shape_question",
        "production_evidence_dependency_question",
        "capability_evidence_dependency_question",
        "audit_proof_dependency_question",
        "publication_stop_rule_question",
        "operator_reassessment_gate",
        "python scripts/validate_foundation_gateway_endpoint_reachability_rehearsal_boundary.py",
    ),
    "docs/FOUNDATION_GATEWAY_ENDPOINT_EVIDENCE_RECEIPT_REHEARSAL_BOUNDARY.md": (
        "Foundation Gateway Endpoint Evidence Receipt Rehearsal Boundary",
        "Witness packet: [`../examples/foundation_gateway_endpoint_evidence_receipt_rehearsal_witness.awaiting_evidence.json`]",
        "Rule: Gateway endpoint evidence receipt rehearsal is a local receipt field",
        "No endpoint probe, gateway URL value, endpoint URL value, HTTP status value",
        "gateway_endpoint_evidence_receipt_rehearsal_state=AwaitingEvidence",
        "endpoint_probe_allowed=false",
        "gateway_url_value_allowed=false",
        "endpoint_url_value_allowed=false",
        "http_status_value_allowed=false",
        "response_digest_value_allowed=false",
        "response_body_value_allowed=false",
        "collection_timestamp_value_allowed=false",
        "collector_identity_value_allowed=false",
        "runtime_witness_payload_allowed=false",
        "runtime_conformance_payload_allowed=false",
        "production_evidence_payload_allowed=false",
        "capability_evidence_payload_allowed=false",
        "audit_verification_payload_allowed=false",
        "proof_verification_payload_allowed=false",
        "evidence_ledger_append_allowed=false",
        "deployment_witness_collection_allowed=false",
        "public_health_declaration_allowed=false",
        "secret_presence_claimed=false",
        "workflow_dispatch_allowed=false",
        "artifact_publication_allowed=false",
        "operator_approval_claimed=false",
        "readiness_claimed=false",
        "customer_access_allowed=false",
        "personal_data_collection_allowed=false",
        "money_movement_allowed=false",
        "legal_clearance_claimed=false",
        "company_formation_claimed=false",
        "patent_claimed=false",
        "external_publication_allowed=false",
        "deployment_allowed=false",
        "endpoint_evidence_receipt_id_label",
        "endpoint_evidence_source_boundary_label",
        "health_endpoint_observation_slot",
        "gateway_witness_observation_slot",
        "runtime_conformance_observation_slot",
        "endpoint_http_status_slot",
        "endpoint_response_digest_slot",
        "endpoint_body_schema_slot",
        "endpoint_collection_time_slot",
        "endpoint_collector_identity_slot",
        "endpoint_redaction_note_slot",
        "endpoint_validation_result_slot",
        "endpoint_evidence_ledger_route_slot",
        "operator_reassessment_gate",
        "python scripts/validate_foundation_gateway_endpoint_evidence_receipt_rehearsal_boundary.py",
    ),
    "docs/FOUNDATION_PUBLIC_HEALTH_DECLARATION_REHEARSAL_BOUNDARY.md": (
        "Foundation Public Health Declaration Rehearsal Boundary",
        "Witness packet: [`../examples/foundation_public_health_declaration_rehearsal_witness.awaiting_evidence.json`]",
        "Rule: Public health declaration rehearsal is a local field-label map",
        "No public health declaration, deployment status mutation, declaration receipt",
        "public_health_declaration_rehearsal_state=AwaitingEvidence",
        "public_health_declared=false",
        "deployment_status_mutation_allowed=false",
        "declaration_receipt_written=false",
        "deployment_witness_publication_claimed=false",
        "deployment_witness_state_value_recorded=false",
        "public_health_endpoint_value_recorded=false",
        "operator_approval_ref_value_recorded=false",
        "audited_date_value_recorded=false",
        "schema_validation_pass_claimed=false",
        "closure_validation_pass_claimed=false",
        "endpoint_match_claimed=false",
        "dry_run_result_recorded=false",
        "status_update_result_recorded=false",
        "evidence_ledger_append_allowed=false",
        "workflow_dispatch_allowed=false",
        "artifact_publication_allowed=false",
        "readiness_claimed=false",
        "customer_access_allowed=false",
        "personal_data_collection_allowed=false",
        "money_movement_allowed=false",
        "legal_clearance_claimed=false",
        "company_formation_claimed=false",
        "patent_claimed=false",
        "external_publication_allowed=false",
        "deployment_allowed=false",
        "deployment_status_path_label",
        "deployment_witness_path_label",
        "declaration_receipt_path_label",
        "dry_run_flag_label",
        "updated_flag_label",
        "deployment_witness_state_label",
        "public_health_endpoint_label",
        "operator_approval_ref_label",
        "audited_date_label",
        "schema_validation_result_label",
        "closure_validation_result_label",
        "endpoint_match_result_label",
        "evidence_ledger_route_label",
        "operator_reassessment_gate",
        "python scripts/validate_foundation_public_health_declaration_rehearsal_boundary.py",
    ),
    "docs/FOUNDATION_GITHUB_APP_TOKEN_FORMAT_BOUNDARY.md": (
        "Foundation GitHub App Token Format Boundary",
        "Witness packet: [`../examples/foundation_github_app_token_format_witness.awaiting_evidence.json`]",
        "GitHub App installation tokens are opaque bearer tokens.",
        "Do not require `len(token) == 40`, `len(token) == 36`, or any other exact length.",
        "Do not reject dot separators inside a `ghs_` token.",
        "Do not parse GitHub App installation tokens as JWTs",
        "minimum_storage_capacity_chars=520",
        "real_tokens_committed=false",
        "deployment_allowed=false",
        "python scripts/validate_foundation_github_app_token_format_boundary.py",
    ),
    "docs/FOUNDATION_PUBLIC_CI_WINDOW_BOUNDARY.md": (
        "Foundation Public CI Window Boundary",
        "The public CI window is a temporary CI execution surface.",
        "public visibility is not public readiness",
        "No raw secrets are printed or committed",
        "post-window receipt",
        "repo_visibility_before",
        "repo_visibility_after",
        "workflow_run_urls",
        "exposure_decision",
        "closure_decision",
        "python scripts/validate_foundation_public_ci_window_boundary.py",
    ),
    "docs/FOUNDATION_PILOT_DEFERRAL_BOUNDARY.md": (
        "Foundation Pilot Deferral Boundary",
        "Witness packet: [`../examples/foundation_pilot_deferral_witness.awaiting_evidence.json`]",
        "Rule: Pilot deferral is a local planning boundary, not a pilot-execution, participant-invitation, access-opening, market-validation, support-readiness, legal-clearance, paid-pilot, publication, or deployment certificate.",
        "No pilot execution, participant invitation, access channel opening, waitlist",
        "pilot_deferral_boundary_state=AwaitingEvidence",
        "pilot_execution_allowed=false",
        "participant_invitation_allowed=false",
        "access_channel_allowed=false",
        "deployment_allowed=false",
    ),
    "docs/FOUNDATION_REASSESSMENT_GATE_BOUNDARY.md": (
        "Foundation Reassessment Gate Boundary",
        "Witness packet: [`../examples/foundation_reassessment_gate_witness.awaiting_evidence.json`]",
        "Rule: Reassessment is a local gate",
        "No reassessment approval, prerequisite promotion, deployment start, pilot",
        "reassessment_gate_state=AwaitingEvidence",
        "reassessment_approved=false",
        "prerequisite_promotion_allowed=false",
        "deployment_start_allowed=false",
        "pilot_start_allowed=false",
        "external_action_allowed=false",
        "customer_access_allowed=false",
        "personal_data_collection_allowed=false",
        "legal_clearance_claimed=false",
        "company_formation_claimed=false",
        "patent_claimed=false",
        "money_movement_allowed=false",
        "secret_material_allowed=false",
        "external_publication_allowed=false",
        "deployment_allowed=false",
        "python scripts/validate_foundation_reassessment_gate_boundary.py",
    ),
    "docs/FOUNDATION_DOMAIN_EMAIL_BOUNDARY.md": (
        "Foundation Domain Email Boundary",
        "Witness packet: [`../examples/foundation_domain_email_witness.awaiting_evidence.json`]",
        "Rule: Public identity labels may be recorded, but DNS/email readiness remains",
        "No provider account IDs, private DNS target values, admin-console details,",
        "dns_mutation_allowed=false",
        "api_dns_publication_allowed=false",
        "endpoint_readiness_claimed=false",
        "email_deliverability_claimed=false",
    ),
    "docs/FOUNDATION_PRODUCT_SCOPE_BOUNDARY.md": (
        "Foundation Product Scope Boundary",
        "Witness packet: [`../examples/foundation_product_scope_witness.awaiting_evidence.json`]",
        "Rule: One narrow learning lane is a local proof lane, not a permanent platform restriction.",
        "No pilot access, customer access, market-validation, paid-launch, deployment-readiness,",
        "selected_learning_lane=local_governed_task_receipt",
        "long_term_platform_restricted=false",
        "pilot_access_allowed=false",
        "market_validation_claimed=false",
    ),
    "docs/FOUNDATION_SUPPORT_READINESS_BOUNDARY.md": (
        "Foundation Support Readiness Boundary",
        "Witness packet: [`../examples/foundation_support_readiness_witness.awaiting_evidence.json`]",
        "Rule: Support preparation is a local planning boundary, not a customer-support service.",
        "No customer support opening, support SLA, incident-response readiness, support",
        "customer_support_open=false",
        "support_sla_claimed=false",
        "incident_response_ready_claimed=false",
        "support_mailbox_deliverability_claimed=false",
    ),
    "docs/FOUNDATION_INTAKE_ONBOARDING_BOUNDARY.md": (
        "Foundation Intake Onboarding Boundary",
        "Witness packet: [`../examples/foundation_intake_onboarding_witness.awaiting_evidence.json`]",
        "Rule: Intake preparation is a local planning boundary, not an active intake channel.",
        "No active intake form, waitlist opening, pilot signup, customer onboarding, PII",
        "intake_open=false",
        "waitlist_open=false",
        "pilot_signup_open=false",
        "pii_collection_allowed=false",
    ),
    "docs/FOUNDATION_PRIVACY_DATA_BOUNDARY.md": (
        "Foundation Privacy Data Boundary",
        "Witness packet: [`../examples/foundation_privacy_data_witness.awaiting_evidence.json`]",
        "Rule: Privacy/data preparation is a local planning boundary, not permission to handle personal data.",
        "No personal-data collection, personal-data storage, retention-policy approval,",
        "personal_data_collection_allowed=false",
        "personal_data_storage_allowed=false",
        "retention_policy_approved=false",
        "privacy_notice_published=false",
    ),
    "docs/FOUNDATION_CUSTOMER_ACCESS_BOUNDARY.md": (
        "Foundation Customer Access Boundary",
        "Witness packet: [`../examples/foundation_customer_access_witness.awaiting_evidence.json`]",
        "Rule: Customer-access preparation is a local planning boundary, not an access approval.",
        "No customer access opening, customer invitation, account creation, access-channel",
        "customer_access_boundary_state=AwaitingEvidence",
        "customer_access_allowed=false",
        "customer_invitation_allowed=false",
        "account_creation_allowed=false",
        "access_channel_open_allowed=false",
        "onboarding_ready_claimed=false",
        "support_commitment_allowed=false",
        "terms_privacy_ready_claimed=false",
        "personal_data_collection_allowed=false",
        "paid_access_allowed=false",
        "pilot_access_allowed=false",
        "beta_access_allowed=false",
        "waitlist_open=false",
        "external_publication_allowed=false",
        "deployment_allowed=false",
        "python scripts/validate_foundation_customer_access_boundary.py",
    ),
    "docs/FOUNDATION_LEGAL_BUSINESS_BOUNDARY.md": (
        "Foundation Legal Business Boundary",
        "Question packet: [`../examples/foundation_legal_business_questions.awaiting_review.json`]",
        "Rule: Legal and business readiness stays `AwaitingEvidence` until qualified",
        "No legal clearance, company readiness, patent protection, trademark clearance,",
        "paid_launch_allowed=false",
        "money_movement_allowed=false",
    ),
    "docs/FOUNDATION_COMMUNITY_NETWORK_BOUNDARY.md": (
        "Foundation Community Network Boundary",
        "Witness packet: [`../examples/foundation_community_network_witness.awaiting_evidence.json`]",
        "Rule: Community/network preparation is a local planning boundary, not outreach, recruiting, public feedback, partnership, or publication.",
        "No community outreach, social post publication, forum post publication, direct",
        "community_network_boundary_state=AwaitingEvidence",
        "community_outreach_allowed=false",
        "social_post_publication_allowed=false",
        "forum_post_publication_allowed=false",
        "direct_message_allowed=false",
        "collaborator_recruitment_allowed=false",
        "partnership_outreach_allowed=false",
        "mentor_request_allowed=false",
        "public_feedback_request_allowed=false",
        "event_participation_allowed=false",
        "contact_list_recorded=false",
        "personal_data_collection_allowed=false",
        "external_account_use_allowed=false",
        "public_profile_claimed=false",
        "customer_access_allowed=false",
        "external_publication_allowed=false",
        "deployment_allowed=false",
        "python scripts/validate_foundation_community_network_boundary.py",
    ),
    "docs/FOUNDATION_FUNDING_TEAM_BOUNDARY.md": (
        "Foundation Funding Team Boundary",
        "Witness packet: [`../examples/foundation_funding_team_witness.awaiting_evidence.json`]",
        "Rule: Funding/team preparation is a local planning boundary, not fundraising, hiring, or team formation.",
        "No fundraising, investor outreach, grant application, pitch publication, hiring,",
        "funding_team_boundary_state=AwaitingEvidence",
        "fundraising_allowed=false",
        "investor_outreach_allowed=false",
        "grant_application_allowed=false",
        "pitch_deck_publication_allowed=false",
        "hiring_allowed=false",
        "contractor_engagement_allowed=false",
        "advisor_commitment_allowed=false",
        "compensation_commitment_allowed=false",
        "equity_promise_allowed=false",
        "payroll_setup_allowed=false",
        "budget_commitment_allowed=false",
        "company_formation_claimed=false",
        "legal_clearance_claimed=false",
        "money_movement_allowed=false",
        "external_publication_allowed=false",
        "deployment_allowed=false",
        "python scripts/validate_foundation_funding_team_boundary.py",
    ),
    "docs/FOUNDATION_PRIVATE_RECOVERY_REHEARSAL_BOUNDARY.md": (
        "Foundation Private Recovery Rehearsal Boundary",
        "Witness packet: [`../examples/foundation_private_recovery_rehearsal_witness.awaiting_evidence.json`]",
        "Rule: Private recovery rehearsal preparation is a local dry-run planning",
        "private_recovery_rehearsal_boundary_state=AwaitingEvidence",
        "recovery_rehearsal_executed=false",
        "credential_use_allowed=false",
        "backup_execution_allowed=false",
        "restore_execution_allowed=false",
        "deployment_allowed=false",
        "python scripts/validate_foundation_private_recovery_rehearsal_boundary.py",
    ),
    "docs/FOUNDATION_SUPPORT_TRIAGE_REHEARSAL_BOUNDARY.md": (
        "Foundation Support Triage Rehearsal Boundary",
        "Witness packet: [`../examples/foundation_support_triage_rehearsal_witness.awaiting_evidence.json`]",
        "Rule: Support triage rehearsal is a local paper exercise, not a customer-support",
        "support_triage_rehearsal_boundary_state=AwaitingEvidence",
        "support_triage_executed=false",
        "customer_support_open=false",
        "support_ticket_creation_allowed=false",
        "support_sla_claimed=false",
        "deployment_allowed=false",
        "python scripts/validate_foundation_support_triage_rehearsal_boundary.py",
    ),
    "docs/FOUNDATION_INTAKE_QUESTIONNAIRE_REHEARSAL_BOUNDARY.md": (
        "Foundation Intake Questionnaire Rehearsal Boundary",
        "Witness packet: [`../examples/foundation_intake_questionnaire_rehearsal_witness.awaiting_evidence.json`]",
        "Rule: Intake questionnaire rehearsal is a local paper exercise, not an intake",
        "intake_questionnaire_rehearsal_boundary_state=AwaitingEvidence",
        "questionnaire_rehearsal_executed=false",
        "form_publication_allowed=false",
        "waitlist_open=false",
        "personal_data_collection_allowed=false",
        "deployment_allowed=false",
        "python scripts/validate_foundation_intake_questionnaire_rehearsal_boundary.py",
    ),
    "docs/FOUNDATION_CUSTOMER_ACCESS_POLICY_REHEARSAL_BOUNDARY.md": (
        "Foundation Customer Access Policy Rehearsal Boundary",
        "Witness packet: [`../examples/foundation_customer_access_policy_rehearsal_witness.awaiting_evidence.json`]",
        "Rule: Customer access policy rehearsal is a local paper exercise, not an access",
        "customer_access_policy_rehearsal_boundary_state=AwaitingEvidence",
        "access_policy_rehearsal_executed=false",
        "customer_access_allowed=false",
        "customer_invitation_allowed=false",
        "account_creation_allowed=false",
        "deployment_allowed=false",
        "python scripts/validate_foundation_customer_access_policy_rehearsal_boundary.py",
    ),
    "docs/FOUNDATION_PRIVACY_MINIMIZATION_REHEARSAL_BOUNDARY.md": (
        "Foundation Privacy Minimization Rehearsal Boundary",
        "Witness packet: [`../examples/foundation_privacy_minimization_rehearsal_witness.awaiting_evidence.json`]",
        "Rule: Privacy minimization rehearsal is a local paper exercise, not permission",
        "privacy_minimization_rehearsal_boundary_state=AwaitingEvidence",
        "minimization_rehearsal_executed=false",
        "personal_data_collection_allowed=false",
        "consent_capture_allowed=false",
        "processor_activation_allowed=false",
        "deployment_allowed=false",
        "python scripts/validate_foundation_privacy_minimization_rehearsal_boundary.py",
    ),
    "docs/FOUNDATION_LEGAL_BUSINESS_QUESTION_REHEARSAL_BOUNDARY.md": (
        "Foundation Legal Business Question Rehearsal Boundary",
        "Witness packet: [`../examples/foundation_legal_business_question_rehearsal_witness.awaiting_evidence.json`]",
        "Rule: Legal/business question rehearsal is a local paper exercise, not a legal",
        "legal_business_question_rehearsal_boundary_state=AwaitingEvidence",
        "question_rehearsal_executed=false",
        "legal_conclusion_claimed=false",
        "qualified_review_completed=false",
        "deployment_allowed=false",
        "python scripts/validate_foundation_legal_business_question_rehearsal_boundary.py",
    ),
    "docs/FOUNDATION_LEGAL_REVIEW_DEFERRAL_BOUNDARY.md": (
        "Foundation Legal Review Deferral Boundary",
        "Witness packet: [`../examples/foundation_legal_review_deferral_witness.awaiting_evidence.json`]",
        "Rule: Legal-review deferral is a local stop-rule packet",
        "legal_review_deferral_state=AwaitingEvidence",
        "legal_review_complete_claimed=false",
        "qualified_reviewer_identity_recorded=false",
        "legal_conclusion_recorded=false",
        "legal_clearance_claimed=false",
        "company_formation_allowed=false",
        "payment_processing_allowed=false",
        "customer_access_allowed=false",
        "deployment_allowed=false",
        "python scripts/validate_foundation_legal_review_deferral_boundary.py",
    ),
    "docs/FOUNDATION_COMPANY_FORMATION_DEFERRAL_BOUNDARY.md": (
        "Foundation Company Formation Deferral Boundary",
        "Witness packet: [`../examples/foundation_company_formation_deferral_witness.awaiting_evidence.json`]",
        "Rule: Company-formation deferral is a local stop-rule packet",
        "company_formation_deferral_state=AwaitingEvidence",
        "company_formation_claimed=false",
        "entity_registration_allowed=false",
        "entity_name_reserved=false",
        "legal_entity_identifier_recorded=false",
        "tax_identifier_recorded=false",
        "business_bank_account_allowed=false",
        "payment_processor_account_allowed=false",
        "money_movement_allowed=false",
        "customer_access_allowed=false",
        "deployment_allowed=false",
        "python scripts/validate_foundation_company_formation_deferral_boundary.py",
    ),
    "docs/FOUNDATION_PATENT_DISCLOSURE_DEFERRAL_BOUNDARY.md": (
        "Foundation Patent Disclosure Deferral Boundary",
        "Witness packet: [`../examples/foundation_patent_disclosure_deferral_witness.awaiting_evidence.json`]",
        "Rule: Patent/disclosure deferral is a local stop-rule packet",
        "patent_disclosure_deferral_state=AwaitingEvidence",
        "patent_filing_allowed=false",
        "patent_protection_claimed=false",
        "invention_boundary_final_claimed=false",
        "invention_authorship_final_claimed=false",
        "ownership_claim_finalized=false",
        "prior_art_conclusion_recorded=false",
        "novelty_claimed=false",
        "patentability_claimed=false",
        "disclosure_approval_claimed=false",
        "public_research_publication_allowed=false",
        "external_publication_allowed=false",
        "secret_or_trade_secret_protection_claimed=false",
        "legal_clearance_claimed=false",
        "company_formation_claimed=false",
        "money_movement_allowed=false",
        "customer_access_allowed=false",
        "deployment_allowed=false",
        "python scripts/validate_foundation_patent_disclosure_deferral_boundary.py",
    ),
    "docs/FOUNDATION_FUNDING_TEAM_OBLIGATION_REHEARSAL_BOUNDARY.md": (
        "Foundation Funding Team Obligation Rehearsal Boundary",
        "Witness packet: [`../examples/foundation_funding_team_obligation_rehearsal_witness.awaiting_evidence.json`]",
        "Rule: Funding/team obligation rehearsal is a local paper exercise, not funding,",
        "funding_team_obligation_rehearsal_boundary_state=AwaitingEvidence",
        "obligation_rehearsal_executed=false",
        "funding_readiness_claimed=false",
        "team_readiness_claimed=false",
        "money_movement_allowed=false",
        "deployment_allowed=false",
        "python scripts/validate_foundation_funding_team_obligation_rehearsal_boundary.py",
    ),
    "docs/FOUNDATION_COMMUNITY_NETWORK_NO_OUTREACH_REHEARSAL_BOUNDARY.md": (
        "Foundation Community Network No-Outreach Rehearsal Boundary",
        "Witness packet: [`../examples/foundation_community_network_no_outreach_rehearsal_witness.awaiting_evidence.json`]",
        "Rule: Community/network no-outreach rehearsal is a local paper exercise,",
        "community_network_no_outreach_rehearsal_boundary_state=AwaitingEvidence",
        "no_outreach_rehearsal_executed=false",
        "public_feedback_request_allowed=false",
        "direct_message_allowed=false",
        "contact_list_recorded=false",
        "deployment_allowed=false",
        "python scripts/validate_foundation_community_network_no_outreach_rehearsal_boundary.py",
    ),
    "docs/FOUNDATION_PILOT_DEFERRAL_REHEARSAL_BOUNDARY.md": (
        "Foundation Pilot Deferral Rehearsal Boundary",
        "Witness packet: [`../examples/foundation_pilot_deferral_rehearsal_witness.awaiting_evidence.json`]",
        "Rule: Pilot-deferral rehearsal is a local paper exercise, not a pilot,",
        "pilot_deferral_rehearsal_boundary_state=AwaitingEvidence",
        "deferral_rehearsal_executed=false",
        "pilot_execution_allowed=false",
        "participant_invitation_allowed=false",
        "payment_enabled=false",
        "deployment_allowed=false",
        "python scripts/validate_foundation_pilot_deferral_rehearsal_boundary.py",
    ),
    "docs/START_HERE.md": (
        "[Foundation Prerequisites](FOUNDATION_PREREQUISITES.md)",
        "[Foundation Operator Readiness Boundary](FOUNDATION_OPERATOR_READINESS_BOUNDARY.md)",
        "[Foundation Learning Path Boundary](FOUNDATION_LEARNING_PATH_BOUNDARY.md)",
        "[Foundation Learning Loop Rehearsal Boundary](FOUNDATION_LEARNING_LOOP_REHEARSAL_BOUNDARY.md)",
        "[Foundation Concept Glossary Rehearsal Boundary](FOUNDATION_CONCEPT_GLOSSARY_REHEARSAL_BOUNDARY.md)",
        "[Foundation Life Meaning Doctrine Rehearsal Boundary](FOUNDATION_LIFE_MEANING_DOCTRINE_REHEARSAL_BOUNDARY.md)",
        "[Foundation Local Release Packet Rehearsal Boundary](FOUNDATION_LOCAL_RELEASE_PACKET_REHEARSAL_BOUNDARY.md)",
        "[Foundation Python Dependency Visibility Rehearsal Boundary](FOUNDATION_PYTHON_DEPENDENCY_VISIBILITY_REHEARSAL_BOUNDARY.md)",
        "[Foundation Architecture Map Boundary](FOUNDATION_ARCHITECTURE_MAP_BOUNDARY.md)",
        "[Foundation System Boundary Inventory Boundary](FOUNDATION_SYSTEM_BOUNDARY_INVENTORY_BOUNDARY.md)",
        "[Foundation Module Inventory Boundary](FOUNDATION_MODULE_INVENTORY_BOUNDARY.md)",
        "[Foundation Component Contract Boundary](FOUNDATION_COMPONENT_CONTRACT_BOUNDARY.md)",
        "[Foundation Interface Map Boundary](FOUNDATION_INTERFACE_MAP_BOUNDARY.md)",
        "[Foundation Dependency Graph Boundary](FOUNDATION_DEPENDENCY_GRAPH_BOUNDARY.md)",
        "[Foundation Invariant Map Boundary](FOUNDATION_INVARIANT_MAP_BOUNDARY.md)",
        "[Foundation Hazard Map Boundary](FOUNDATION_HAZARD_MAP_BOUNDARY.md)",
        "[Foundation Proof Reference Boundary](FOUNDATION_PROOF_REFERENCE_BOUNDARY.md)",
        "[Foundation Gap Register Boundary](FOUNDATION_GAP_REGISTER_BOUNDARY.md)",
        "[Foundation Diff Review Boundary](FOUNDATION_DIFF_REVIEW_BOUNDARY.md)",
        "[Foundation Change Handoff Boundary](FOUNDATION_CHANGE_HANDOFF_BOUNDARY.md)",
        "[Foundation Local Workstation Boundary](FOUNDATION_LOCAL_WORKSTATION_BOUNDARY.md)",
        "[Foundation Documentation Boundary](FOUNDATION_DOCUMENTATION_BOUNDARY.md)",
        "[Foundation Plain-Language Status Boundary](FOUNDATION_PLAIN_LANGUAGE_STATUS_BOUNDARY.md)",
        "[Foundation Accessibility Language Boundary](FOUNDATION_ACCESSIBILITY_LANGUAGE_BOUNDARY.md)",
        "[Foundation Capability Roadmap Boundary](FOUNDATION_CAPABILITY_ROADMAP_BOUNDARY.md)",
        "[Foundation Agentic Management Boundary](FOUNDATION_AGENTIC_MANAGEMENT_BOUNDARY.md)",
        "[Foundation Operations Runbook Boundary](FOUNDATION_OPERATIONS_RUNBOOK_BOUNDARY.md)",
        "[Foundation Claim Boundary](FOUNDATION_CLAIM_BOUNDARY.md)",
        "[Foundation Website Posture Boundary](FOUNDATION_WEBSITE_POSTURE_BOUNDARY.md)",
        "[Foundation Research Notebook Boundary](FOUNDATION_RESEARCH_NOTEBOOK_BOUNDARY.md)",
        "[Foundation Market Research Boundary](FOUNDATION_MARKET_RESEARCH_BOUNDARY.md)",
        "[Foundation Evidence Ledger Boundary](FOUNDATION_EVIDENCE_LEDGER_BOUNDARY.md)",
        "[Foundation Decision Journal Boundary](FOUNDATION_DECISION_JOURNAL_BOUNDARY.md)",
        "[Foundation Next Action Boundary](FOUNDATION_NEXT_ACTION_BOUNDARY.md)",
        "[Foundation Test Evidence Boundary](FOUNDATION_TEST_EVIDENCE_BOUNDARY.md)",
        "[Foundation Source Control Boundary](FOUNDATION_SOURCE_CONTROL_BOUNDARY.md)",
        "[Foundation Source-Control Review Checklist Boundary](FOUNDATION_SOURCE_CONTROL_REVIEW_CHECKLIST_BOUNDARY.md)",
        "[Foundation Local Proof Thread](FOUNDATION_LOCAL_PROOF_THREAD.md)",
        "[Foundation Secrets Credentials Boundary](FOUNDATION_SECRETS_CREDENTIALS_BOUNDARY.md)",
        "[Foundation Runtime Secret Handoff Rehearsal Boundary](FOUNDATION_RUNTIME_SECRET_HANDOFF_REHEARSAL_BOUNDARY.md)",
        "[Foundation Runtime Witness Deferral Boundary](FOUNDATION_RUNTIME_WITNESS_DEFERRAL_BOUNDARY.md)",
        "[Foundation Security Baseline Boundary](FOUNDATION_SECURITY_BASELINE_BOUNDARY.md)",
        "[Foundation Cost Budget Boundary](FOUNDATION_COST_BUDGET_BOUNDARY.md)",
        "[Foundation Payment Provider Boundary](FOUNDATION_PAYMENT_PROVIDER_BOUNDARY.md)",
        "[Foundation Runtime Environment Boundary](FOUNDATION_RUNTIME_ENVIRONMENT_BOUNDARY.md)",
        "[Foundation Backup Export Boundary](FOUNDATION_BACKUP_EXPORT_BOUNDARY.md)",
        "[Foundation Deployment Deferral Boundary](FOUNDATION_DEPLOYMENT_DEFERRAL_BOUNDARY.md)",
        "[Foundation External Infrastructure Boundary](FOUNDATION_EXTERNAL_INFRASTRUCTURE_BOUNDARY.md)",
        "[Foundation Production Dependency Evidence Rehearsal Boundary](FOUNDATION_PRODUCTION_DEPENDENCY_EVIDENCE_REHEARSAL_BOUNDARY.md)",
        "[Foundation External Evidence Acceptance Rehearsal Boundary](FOUNDATION_EXTERNAL_EVIDENCE_ACCEPTANCE_REHEARSAL_BOUNDARY.md)",
        "[Foundation Deployment Upstream API Gate Rehearsal Boundary](FOUNDATION_DEPLOYMENT_UPSTREAM_API_GATE_REHEARSAL_BOUNDARY.md)",
        "[Foundation Gateway DNS Target Binding Rehearsal Boundary](FOUNDATION_GATEWAY_DNS_TARGET_BINDING_REHEARSAL_BOUNDARY.md)",
        "[Foundation Gateway DNS Publication Rehearsal Boundary](FOUNDATION_GATEWAY_DNS_PUBLICATION_REHEARSAL_BOUNDARY.md)",
        "[Foundation Gateway DNS Resolution Receipt Rehearsal Boundary](FOUNDATION_GATEWAY_DNS_RESOLUTION_RECEIPT_REHEARSAL_BOUNDARY.md)",
        "[Foundation Gateway Endpoint Reachability Rehearsal Boundary](FOUNDATION_GATEWAY_ENDPOINT_REACHABILITY_REHEARSAL_BOUNDARY.md)",
        "[Foundation Gateway Endpoint Evidence Receipt Rehearsal Boundary](FOUNDATION_GATEWAY_ENDPOINT_EVIDENCE_RECEIPT_REHEARSAL_BOUNDARY.md)",
        "[Foundation Public Health Declaration Rehearsal Boundary](FOUNDATION_PUBLIC_HEALTH_DECLARATION_REHEARSAL_BOUNDARY.md)",
        "[Foundation Deployment Witness Input Boundary](FOUNDATION_DEPLOYMENT_WITNESS_INPUT_BOUNDARY.md)",
        "[Foundation Deployment Witness Preflight Rehearsal Boundary](FOUNDATION_DEPLOYMENT_WITNESS_PREFLIGHT_REHEARSAL_BOUNDARY.md)",
        "[Foundation Deployment Witness Dispatch Rehearsal Boundary](FOUNDATION_DEPLOYMENT_WITNESS_DISPATCH_REHEARSAL_BOUNDARY.md)",
        "[Foundation Deployment Witness Artifact Validation Rehearsal Boundary](FOUNDATION_DEPLOYMENT_WITNESS_ARTIFACT_VALIDATION_REHEARSAL_BOUNDARY.md)",
        "[Foundation Deployment Witness Evidence Handoff Boundary](FOUNDATION_DEPLOYMENT_WITNESS_EVIDENCE_HANDOFF_BOUNDARY.md)",
        "[Foundation Deployment Witness Evidence Ledger Routing Boundary](FOUNDATION_DEPLOYMENT_WITNESS_EVIDENCE_LEDGER_ROUTING_BOUNDARY.md)",
        "[Foundation GitHub App Token Format Boundary](FOUNDATION_GITHUB_APP_TOKEN_FORMAT_BOUNDARY.md)",
        "[Foundation Pilot Deferral Boundary](FOUNDATION_PILOT_DEFERRAL_BOUNDARY.md)",
        "[Foundation Private Recovery Boundary](FOUNDATION_PRIVATE_RECOVERY_BOUNDARY.md)",
        "[Foundation Pilot Deferral Rehearsal Boundary](FOUNDATION_PILOT_DEFERRAL_REHEARSAL_BOUNDARY.md)",
        "[Foundation Reassessment Gate Boundary](FOUNDATION_REASSESSMENT_GATE_BOUNDARY.md)",
        "[Foundation Private Recovery Rehearsal Boundary](FOUNDATION_PRIVATE_RECOVERY_REHEARSAL_BOUNDARY.md)",
        "[Foundation Support Triage Rehearsal Boundary](FOUNDATION_SUPPORT_TRIAGE_REHEARSAL_BOUNDARY.md)",
        "[Foundation Intake Questionnaire Rehearsal Boundary](FOUNDATION_INTAKE_QUESTIONNAIRE_REHEARSAL_BOUNDARY.md)",
        "[Foundation Customer Access Policy Rehearsal Boundary](FOUNDATION_CUSTOMER_ACCESS_POLICY_REHEARSAL_BOUNDARY.md)",
        "[Foundation Privacy Minimization Rehearsal Boundary](FOUNDATION_PRIVACY_MINIMIZATION_REHEARSAL_BOUNDARY.md)",
        "[Foundation Legal Business Question Rehearsal Boundary](FOUNDATION_LEGAL_BUSINESS_QUESTION_REHEARSAL_BOUNDARY.md)",
        "[Foundation Legal Review Deferral Boundary](FOUNDATION_LEGAL_REVIEW_DEFERRAL_BOUNDARY.md)",
        "[Foundation Company Formation Deferral Boundary](FOUNDATION_COMPANY_FORMATION_DEFERRAL_BOUNDARY.md)",
        "[Foundation Patent Disclosure Deferral Boundary](FOUNDATION_PATENT_DISCLOSURE_DEFERRAL_BOUNDARY.md)",
        "[Foundation Funding Team Obligation Rehearsal Boundary](FOUNDATION_FUNDING_TEAM_OBLIGATION_REHEARSAL_BOUNDARY.md)",
        "[Foundation Community Network No-Outreach Rehearsal Boundary](FOUNDATION_COMMUNITY_NETWORK_NO_OUTREACH_REHEARSAL_BOUNDARY.md)",
        "[Foundation Domain Email Boundary](FOUNDATION_DOMAIN_EMAIL_BOUNDARY.md)",
        "[Foundation Product Scope Boundary](FOUNDATION_PRODUCT_SCOPE_BOUNDARY.md)",
        "[Foundation Support Readiness Boundary](FOUNDATION_SUPPORT_READINESS_BOUNDARY.md)",
        "[Foundation Intake Onboarding Boundary](FOUNDATION_INTAKE_ONBOARDING_BOUNDARY.md)",
        "[Foundation Privacy Data Boundary](FOUNDATION_PRIVACY_DATA_BOUNDARY.md)",
        "[Foundation Customer Access Boundary](FOUNDATION_CUSTOMER_ACCESS_BOUNDARY.md)",
        "[Foundation Legal Business Boundary](FOUNDATION_LEGAL_BUSINESS_BOUNDARY.md)",
        "[Foundation Funding Team Boundary](FOUNDATION_FUNDING_TEAM_BOUNDARY.md)",
        "[Foundation Community Network Boundary](FOUNDATION_COMMUNITY_NETWORK_BOUNDARY.md)",
        "what to prepare now, what to delay, and what evidence to keep",
    ),
    "docs/CURRENT_READINESS_SNAPSHOT.md": (
        "Prerequisite ledger",
        "`docs/FOUNDATION_PREREQUISITES.md`",
        "`docs/FOUNDATION_OPERATOR_READINESS_BOUNDARY.md`",
        "`docs/FOUNDATION_SOLO_DAILY_LOOP_BOUNDARY.md`",
        "`docs/FOUNDATION_LEARNING_PATH_BOUNDARY.md`",
        "`docs/FOUNDATION_ARCHITECTURE_MAP_BOUNDARY.md`",
        "`docs/FOUNDATION_SYSTEM_BOUNDARY_INVENTORY_BOUNDARY.md`",
        "`docs/FOUNDATION_MODULE_INVENTORY_BOUNDARY.md`",
        "`docs/FOUNDATION_COMPONENT_CONTRACT_BOUNDARY.md`",
        "`docs/FOUNDATION_INTERFACE_MAP_BOUNDARY.md`",
        "`docs/FOUNDATION_DEPENDENCY_GRAPH_BOUNDARY.md`",
        "`docs/FOUNDATION_INVARIANT_MAP_BOUNDARY.md`",
        "`docs/FOUNDATION_HAZARD_MAP_BOUNDARY.md`",
        "`docs/FOUNDATION_PROOF_REFERENCE_BOUNDARY.md`",
        "`docs/FOUNDATION_GAP_REGISTER_BOUNDARY.md`",
        "`docs/FOUNDATION_DIFF_REVIEW_BOUNDARY.md`",
        "`docs/FOUNDATION_CHANGE_HANDOFF_BOUNDARY.md`",
        "`docs/FOUNDATION_LOCAL_WORKSTATION_BOUNDARY.md`",
        "`docs/FOUNDATION_DOCUMENTATION_BOUNDARY.md`",
        "`docs/FOUNDATION_PLAIN_LANGUAGE_STATUS_BOUNDARY.md`",
        "`docs/FOUNDATION_ACCESSIBILITY_LANGUAGE_BOUNDARY.md`",
        "`docs/FOUNDATION_CAPABILITY_ROADMAP_BOUNDARY.md`",
        "`docs/FOUNDATION_AGENTIC_MANAGEMENT_BOUNDARY.md`",
        "`docs/FOUNDATION_OPERATIONS_RUNBOOK_BOUNDARY.md`",
        "`docs/FOUNDATION_CLAIM_BOUNDARY.md`",
        "`docs/FOUNDATION_WEBSITE_POSTURE_BOUNDARY.md`",
        "`docs/FOUNDATION_RESEARCH_NOTEBOOK_BOUNDARY.md`",
        "`docs/FOUNDATION_MARKET_RESEARCH_BOUNDARY.md`",
        "`docs/FOUNDATION_EVIDENCE_LEDGER_BOUNDARY.md`",
        "`docs/FOUNDATION_DECISION_JOURNAL_BOUNDARY.md`",
        "`docs/FOUNDATION_NEXT_ACTION_BOUNDARY.md`",
        "`docs/FOUNDATION_TEST_EVIDENCE_BOUNDARY.md`",
        "`docs/FOUNDATION_SOURCE_CONTROL_BOUNDARY.md`",
        "`docs/FOUNDATION_SOURCE_CONTROL_REVIEW_CHECKLIST_BOUNDARY.md`",
        "`docs/FOUNDATION_SECRETS_CREDENTIALS_BOUNDARY.md`",
        "`docs/FOUNDATION_SECURITY_BASELINE_BOUNDARY.md`",
        "`docs/FOUNDATION_COST_BUDGET_BOUNDARY.md`",
        "`docs/FOUNDATION_PAYMENT_PROVIDER_BOUNDARY.md`",
        "`docs/FOUNDATION_RUNTIME_ENVIRONMENT_BOUNDARY.md`",
        "`docs/FOUNDATION_BACKUP_EXPORT_BOUNDARY.md`",
        "`docs/FOUNDATION_DEPLOYMENT_DEFERRAL_BOUNDARY.md`",
        "`docs/FOUNDATION_EXTERNAL_INFRASTRUCTURE_BOUNDARY.md`",
        "`docs/FOUNDATION_RUNTIME_SECRET_HANDOFF_REHEARSAL_BOUNDARY.md`",
        "`docs/FOUNDATION_RUNTIME_WITNESS_DEFERRAL_BOUNDARY.md`",
        "`docs/FOUNDATION_PRODUCTION_DEPENDENCY_EVIDENCE_REHEARSAL_BOUNDARY.md`",
        "`docs/FOUNDATION_EXTERNAL_EVIDENCE_ACCEPTANCE_REHEARSAL_BOUNDARY.md`",
        "`docs/FOUNDATION_DEPLOYMENT_UPSTREAM_API_GATE_REHEARSAL_BOUNDARY.md`",
        "`docs/FOUNDATION_GATEWAY_DNS_TARGET_BINDING_REHEARSAL_BOUNDARY.md`",
        "`docs/FOUNDATION_GATEWAY_DNS_PUBLICATION_REHEARSAL_BOUNDARY.md`",
        "`docs/FOUNDATION_GATEWAY_DNS_RESOLUTION_RECEIPT_REHEARSAL_BOUNDARY.md`",
        "`docs/FOUNDATION_GATEWAY_ENDPOINT_REACHABILITY_REHEARSAL_BOUNDARY.md`",
        "`docs/FOUNDATION_GATEWAY_ENDPOINT_EVIDENCE_RECEIPT_REHEARSAL_BOUNDARY.md`",
        "`docs/FOUNDATION_PUBLIC_HEALTH_DECLARATION_REHEARSAL_BOUNDARY.md`",
        "`docs/FOUNDATION_DEPLOYMENT_WITNESS_INPUT_BOUNDARY.md`",
        "`docs/FOUNDATION_DEPLOYMENT_WITNESS_PREFLIGHT_REHEARSAL_BOUNDARY.md`",
        "`docs/FOUNDATION_DEPLOYMENT_WITNESS_DISPATCH_REHEARSAL_BOUNDARY.md`",
        "`docs/FOUNDATION_DEPLOYMENT_WITNESS_ARTIFACT_VALIDATION_REHEARSAL_BOUNDARY.md`",
        "`docs/FOUNDATION_DEPLOYMENT_WITNESS_EVIDENCE_HANDOFF_BOUNDARY.md`",
        "`docs/FOUNDATION_DEPLOYMENT_WITNESS_EVIDENCE_LEDGER_ROUTING_BOUNDARY.md`",
        "`docs/FOUNDATION_GITHUB_APP_TOKEN_FORMAT_BOUNDARY.md`",
        "`docs/FOUNDATION_PUBLIC_CI_WINDOW_BOUNDARY.md`",
        "`docs/FOUNDATION_PILOT_DEFERRAL_BOUNDARY.md`",
        "`docs/FOUNDATION_PILOT_DEFERRAL_REHEARSAL_BOUNDARY.md`",
        "`docs/FOUNDATION_REASSESSMENT_GATE_BOUNDARY.md`",
        "`docs/FOUNDATION_LEARNING_LOOP_REHEARSAL_BOUNDARY.md`",
        "`docs/FOUNDATION_CONCEPT_GLOSSARY_REHEARSAL_BOUNDARY.md`",
        "`docs/FOUNDATION_LIFE_MEANING_DOCTRINE_REHEARSAL_BOUNDARY.md`",
        "`docs/FOUNDATION_LOCAL_RELEASE_PACKET_REHEARSAL_BOUNDARY.md`",
        "`docs/FOUNDATION_PYTHON_DEPENDENCY_VISIBILITY_REHEARSAL_BOUNDARY.md`",
        "`docs/FOUNDATION_PRIVATE_RECOVERY_BOUNDARY.md`",
        "`docs/FOUNDATION_PRIVATE_RECOVERY_REHEARSAL_BOUNDARY.md`",
        "`docs/FOUNDATION_DOMAIN_EMAIL_BOUNDARY.md`",
        "`docs/FOUNDATION_SUPPORT_TRIAGE_REHEARSAL_BOUNDARY.md`",
        "`docs/FOUNDATION_INTAKE_QUESTIONNAIRE_REHEARSAL_BOUNDARY.md`",
        "`docs/FOUNDATION_CUSTOMER_ACCESS_POLICY_REHEARSAL_BOUNDARY.md`",
        "`docs/FOUNDATION_PRIVACY_MINIMIZATION_REHEARSAL_BOUNDARY.md`",
        "`docs/FOUNDATION_LEGAL_BUSINESS_BOUNDARY.md`",
        "`docs/FOUNDATION_LEGAL_BUSINESS_QUESTION_REHEARSAL_BOUNDARY.md`",
        "`docs/FOUNDATION_LEGAL_REVIEW_DEFERRAL_BOUNDARY.md`",
        "`docs/FOUNDATION_COMPANY_FORMATION_DEFERRAL_BOUNDARY.md`",
        "`docs/FOUNDATION_PATENT_DISCLOSURE_DEFERRAL_BOUNDARY.md`",
        "`docs/FOUNDATION_FUNDING_TEAM_OBLIGATION_REHEARSAL_BOUNDARY.md`",
        "`docs/FOUNDATION_COMMUNITY_NETWORK_NO_OUTREACH_REHEARSAL_BOUNDARY.md`",
        "`docs/FOUNDATION_CUSTOMER_ACCESS_BOUNDARY.md`",
        "`docs/FOUNDATION_FUNDING_TEAM_BOUNDARY.md`",
        "`docs/FOUNDATION_COMMUNITY_NETWORK_BOUNDARY.md`",
    ),
    "docs/explain/PLAIN_ENGLISH.md": (
        "Current foundation posture",
        "[Foundation Mode](../FOUNDATION_MODE.md)",
        "[Foundation Plain-Language Status Boundary](../FOUNDATION_PLAIN_LANGUAGE_STATUS_BOUNDARY.md)",
        "future governed",
        "The safe work now is local proof",
        "Nothing on this page claims public launch, customer access, legal clearance,",
        "Those are product-direction examples, not current customer access claims.",
        "Foundation Mode keeps them local until the required witnesses exist.",
    ),
    "docs/WEBSITE_UPDATE_CHECKLIST.md": (
        "Foundation-stage proof-boundary action only until clearance and witness gates close",
        "foundation-stage with no access, waitlist, or beta invitation",
    ),
    "docs/WEBSITE_DEPLOYMENT_EVIDENCE_TEMPLATE.md": (
        "foundation_boundary_only",
        "foundation-stage with no access, waitlist, or beta invitation",
    ),
    "docs/PUBLIC_NAMING_REVIEW_PACKET.md": (
        "foundation-stage with no access, waitlist, or beta invitation",
        "Paid public launch allowed | false",
    ),
    "docs/PUBLIC_NAMING_READINESS.md": (
        "foundation-stage proof-boundary copy with no access, waitlist, or",
        "beta invitation, not a paid public launch page",
    ),
    "scripts/plan_public_naming_transition.py": (
        "foundation-stage proof-boundary copy with no access invitation",
    ),
    "site/mullu/index.html": (
        "foundation mode",
        "local proof first",
        "deployment and customer access are not claimed",
    ),
    "site/proof/index.html": (
        "Public deployment",
        "customer access are not claimed",
        "Public launch remains blocked",
        "runtime witness evidence close",
    ),
}

FORWARD_LOOKING_FILES = tuple(REQUIRED_PHRASES_BY_FILE)

CENTRAL_FOUNDATION_TABLE_FILES = (
    "docs/START_HERE.md",
    "docs/FOUNDATION_MODE.md",
    "docs/FOUNDATION_PREREQUISITES.md",
    "docs/CURRENT_READINESS_SNAPSHOT.md",
)

CENTRAL_FOUNDATION_DEPENDENCY_FILES = (
    "docs/FOUNDATION_MODE.md",
    "docs/FOUNDATION_PREREQUISITES.md",
)

FOUNDATION_BOUNDARY_ROUTE_FILES = (
    "README.md",
    "docs/START_HERE.md",
    "docs/FOUNDATION_MODE.md",
    "docs/CURRENT_READINESS_SNAPSHOT.md",
)

FOUNDATION_BOUNDARY_STATUS_FIELDS = (
    "STATUS:",
    "Completeness:",
    "Invariants verified:",
    "Open issues:",
    "Next action:",
)

FOUNDATION_NAVIGATION_LINK_FILES = (
    "README.md",
    "docs/START_HERE.md",
    "docs/FOUNDATION_MODE.md",
    "docs/FOUNDATION_PREREQUISITES.md",
    "docs/CURRENT_READINESS_SNAPSHOT.md",
)

QUIET_PUBLIC_README_REQUIRED_PHRASES = (
    "# Repository Notice",
    "Public documentation is intentionally minimized at this time.",
    "This repository is not accepting public use, issues, or external contributions.",
    "See `LICENSE` for usage terms.",
)

START_HERE_ORDER_START = '## 3. The "I\'m brand new" path (do these in order)'
START_HERE_ORDER_END = "Now you can wander into"
FOUNDATION_PREREQUISITE_ORDER_START = "## Recommended Order"
FOUNDATION_PREREQUISITE_ORDER_END = "## Narrow Local Proof Thread Definition"

FORBIDDEN_FORWARD_PHRASES = (
    "Request access",
    "request access until",
    "request-access until",
    "Start pilot",
    "pilot access is open",
    "private beta access",
    "foundation-stage, waitlist",
    "foundation-stage, private beta",
    "waitlist/private beta",
    "private_beta_only",
    "customer access is open",
    "production-ready",
    "live endpoint",
    "deployed runtime",
    "public sandbox is available",
)


@dataclass(frozen=True, slots=True)
class FoundationModeFinding:
    """One deterministic Foundation Mode validation finding."""

    rule_id: str
    message: str


def read_required_text(repo_root: Path, relative_path: str) -> str:
    """Read one required repository file with explicit path errors."""

    path = repo_root / relative_path
    if not path.exists():
        raise FileNotFoundError(f"missing Foundation Mode file: {relative_path}")
    if not path.is_file():
        raise IsADirectoryError(f"Foundation Mode path is not a file: {relative_path}")
    return path.read_text(encoding="utf-8")


def validate_core_guidance_surface_registration(
    repo_root: Path = REPO_ROOT,
    required_surfaces: tuple[str, ...] = FOUNDATION_CORE_GUIDANCE_SURFACES,
    phrase_map: dict[str, tuple[str, ...]] = REQUIRED_PHRASES_BY_FILE,
) -> list[FoundationModeFinding]:
    """Return findings when canonical Foundation guidance surfaces lose validation coverage."""

    findings: list[FoundationModeFinding] = []
    for relative_path in required_surfaces:
        if relative_path not in phrase_map:
            findings.append(
                FoundationModeFinding(
                    "foundation_core_guidance_surface_unregistered",
                    f"REQUIRED_PHRASES_BY_FILE missing core guidance surface: {relative_path}",
                )
            )
        path = repo_root / relative_path
        if not path.exists():
            findings.append(
                FoundationModeFinding(
                    "foundation_core_guidance_surface_missing",
                    f"missing core Foundation guidance surface: {relative_path}",
                )
            )
        elif not path.is_file():
            findings.append(
                FoundationModeFinding(
                    "foundation_core_guidance_surface_not_file",
                    f"core Foundation guidance surface is not a file: {relative_path}",
                )
            )
    return findings


def validate_required_phrases(repo_root: Path = REPO_ROOT) -> list[FoundationModeFinding]:
    """Return findings for missing current-posture anchor phrases."""

    findings: list[FoundationModeFinding] = []
    for relative_path, required_phrases in REQUIRED_PHRASES_BY_FILE.items():
        try:
            text = read_required_text(repo_root, relative_path)
        except OSError as exc:
            findings.append(FoundationModeFinding("foundation_file_missing", str(exc)))
            continue
        if is_quiet_public_readme(relative_path, text):
            for phrase in QUIET_PUBLIC_README_REQUIRED_PHRASES:
                if phrase not in text:
                    findings.append(
                        FoundationModeFinding(
                            "foundation_quiet_readme_phrase_missing",
                            f"{relative_path} missing quiet public README phrase: {phrase}",
                        )
                    )
            continue
        for phrase in required_phrases:
            if phrase not in text:
                findings.append(
                    FoundationModeFinding(
                        "foundation_phrase_missing",
                        f"{relative_path} missing required phrase: {phrase}",
                    )
                )
    return findings


def validate_forward_text_boundary(
    relative_path: str,
    text: str,
    forbidden_phrases: tuple[str, ...] = FORBIDDEN_FORWARD_PHRASES,
) -> list[FoundationModeFinding]:
    """Return findings when current guidance authorizes blocked access language."""

    lowered_text = text.casefold()
    findings: list[FoundationModeFinding] = []
    for phrase in forbidden_phrases:
        if phrase.casefold() in lowered_text:
            findings.append(
                FoundationModeFinding(
                    "foundation_forbidden_forward_phrase",
                    f"{relative_path} contains forward-looking blocked phrase: {phrase}",
                )
            )
    return findings


def validate_forbidden_forward_phrases(repo_root: Path = REPO_ROOT) -> list[FoundationModeFinding]:
    """Return findings for blocked phrases in current-posture files."""

    findings: list[FoundationModeFinding] = []
    for relative_path in FORWARD_LOOKING_FILES:
        try:
            text = read_required_text(repo_root, relative_path)
        except OSError as exc:
            findings.append(FoundationModeFinding("foundation_file_missing", str(exc)))
            continue
        findings.extend(validate_forward_text_boundary(relative_path, text))
    return findings


def validate_central_table_label_uniqueness(repo_root: Path = REPO_ROOT) -> list[FoundationModeFinding]:
    """Return findings for duplicate first-column labels in central Foundation tables."""

    findings: list[FoundationModeFinding] = []
    for relative_path in CENTRAL_FOUNDATION_TABLE_FILES:
        try:
            text = read_required_text(repo_root, relative_path)
        except OSError as exc:
            findings.append(FoundationModeFinding("foundation_file_missing", str(exc)))
            continue
        for table_index, table_lines in enumerate(_iter_markdown_tables(text), start=1):
            labels: list[str] = []
            for row_line in table_lines[2:]:
                cells = [cell.strip() for cell in row_line.strip("|").split("|")]
                if cells and cells[0]:
                    labels.append(cells[0])
            duplicate_labels = sorted({label for label in labels if labels.count(label) > 1})
            for duplicate_label in duplicate_labels:
                findings.append(
                    FoundationModeFinding(
                        "foundation_table_duplicate_label",
                        f"{relative_path} table {table_index} repeats first-column label: {duplicate_label}",
                    )
                )
    return findings


def validate_central_foundation_dependency_headers(repo_root: Path = REPO_ROOT) -> list[FoundationModeFinding]:
    """Return findings when central Foundation headers omit boundary dependencies."""

    boundary_doc_names = sorted(boundary_doc.name for boundary_doc in (repo_root / "docs").glob("FOUNDATION_*_BOUNDARY.md"))
    if not boundary_doc_names:
        return [
            FoundationModeFinding(
                "foundation_boundary_inventory_missing",
                "docs directory has no FOUNDATION_*_BOUNDARY.md files",
            )
        ]
    findings: list[FoundationModeFinding] = []
    for relative_path in CENTRAL_FOUNDATION_DEPENDENCY_FILES:
        try:
            text = read_required_text(repo_root, relative_path)
        except OSError as exc:
            findings.append(FoundationModeFinding("foundation_file_missing", str(exc)))
            continue
        if "-->" not in text:
            findings.append(
                FoundationModeFinding(
                    "foundation_central_dependency_header_missing",
                    f"{relative_path} missing leading metadata header",
                )
            )
            continue
        header = text.split("-->", 1)[0]
        missing_boundary_doc_names = [boundary_doc_name for boundary_doc_name in boundary_doc_names if boundary_doc_name not in header]
        if missing_boundary_doc_names:
            findings.append(
                FoundationModeFinding(
                    "foundation_central_dependency_missing",
                    f"{relative_path} header missing boundary dependencies: {', '.join(missing_boundary_doc_names)}",
                )
            )
    return findings


def validate_prerequisite_go_deeper_boundary_links(repo_root: Path = REPO_ROOT) -> list[FoundationModeFinding]:
    """Return findings when the operator navigation table omits a boundary doc."""

    relative_path = "docs/FOUNDATION_PREREQUISITES.md"
    try:
        text = read_required_text(repo_root, relative_path)
    except OSError as exc:
        return [FoundationModeFinding("foundation_file_missing", str(exc))]
    if "## Go deeper / where to go next" not in text:
        return [
            FoundationModeFinding(
                "foundation_prerequisite_navigation_missing",
                f"{relative_path} missing Go deeper navigation section",
            )
        ]
    section = text.split("## Go deeper / where to go next", 1)[1]
    observed_links = set(re.findall(r"\((FOUNDATION_[^)]+?_BOUNDARY\.md)\)", section))
    expected_links = {
        boundary_doc.name
        for boundary_doc in (repo_root / "docs").glob("FOUNDATION_*_BOUNDARY.md")
    }
    missing_links = sorted(expected_links - observed_links)
    if not missing_links:
        return []
    return [
        FoundationModeFinding(
            "foundation_prerequisite_navigation_boundary_missing",
            f"{relative_path} Go deeper navigation missing boundary links: {', '.join(missing_links)}",
        )
    ]


def validate_foundation_boundary_routing_surfaces(repo_root: Path = REPO_ROOT) -> list[FoundationModeFinding]:
    """Return findings when central route surfaces omit a Foundation boundary."""

    boundary_doc_names = sorted(boundary_doc.name for boundary_doc in (repo_root / "docs").glob("FOUNDATION_*_BOUNDARY.md"))
    if not boundary_doc_names:
        return [
            FoundationModeFinding(
                "foundation_boundary_inventory_missing",
                "docs directory has no FOUNDATION_*_BOUNDARY.md files",
            )
        ]
    findings: list[FoundationModeFinding] = []
    for boundary_doc_name in boundary_doc_names:
        required_key = f"docs/{boundary_doc_name}"
        if required_key not in REQUIRED_PHRASES_BY_FILE:
            findings.append(
                FoundationModeFinding(
                    "foundation_boundary_phrase_registration_missing",
                    f"REQUIRED_PHRASES_BY_FILE missing boundary key: {required_key}",
                )
            )
    for relative_path in FOUNDATION_BOUNDARY_ROUTE_FILES:
        try:
            text = read_required_text(repo_root, relative_path)
        except OSError as exc:
            findings.append(FoundationModeFinding("foundation_file_missing", str(exc)))
            continue
        if is_quiet_public_readme(relative_path, text):
            continue
        missing_boundary_doc_names = [boundary_doc_name for boundary_doc_name in boundary_doc_names if boundary_doc_name not in text]
        if missing_boundary_doc_names:
            findings.append(
                FoundationModeFinding(
                    "foundation_boundary_route_missing",
                    f"{relative_path} missing boundary links: {', '.join(missing_boundary_doc_names)}",
                )
            )
    return findings


def is_quiet_public_readme(relative_path: str, text: str) -> bool:
    """Return true when the top-level README is intentionally minimized."""
    return (
        relative_path == "README.md"
        and "Public documentation is intentionally minimized at this time." in text
    )


def validate_foundation_boundary_status_blocks(repo_root: Path = REPO_ROOT) -> list[FoundationModeFinding]:
    """Return findings when Foundation boundary docs lack terminal status context."""

    boundary_doc_paths = sorted((repo_root / "docs").glob("FOUNDATION_*_BOUNDARY.md"))
    if not boundary_doc_paths:
        return [
            FoundationModeFinding(
                "foundation_boundary_inventory_missing",
                "docs directory has no FOUNDATION_*_BOUNDARY.md files",
            )
        ]
    findings: list[FoundationModeFinding] = []
    for boundary_doc_path in boundary_doc_paths:
        relative_path = f"docs/{boundary_doc_path.name}"
        try:
            text = read_required_text(repo_root, relative_path)
        except OSError as exc:
            findings.append(FoundationModeFinding("foundation_file_missing", str(exc)))
            continue
        missing_status_fields = [field for field in FOUNDATION_BOUNDARY_STATUS_FIELDS if field not in text]
        if missing_status_fields:
            findings.append(
                FoundationModeFinding(
                    "foundation_boundary_status_field_missing",
                    f"{relative_path} missing status fields: {', '.join(missing_status_fields)}",
                )
            )
        if "AwaitingEvidence" not in text:
            findings.append(
                FoundationModeFinding(
                    "foundation_boundary_awaiting_evidence_missing",
                    f"{relative_path} missing AwaitingEvidence posture",
                )
            )
    return findings


def validate_foundation_navigation_links(repo_root: Path = REPO_ROOT) -> list[FoundationModeFinding]:
    """Return findings for broken or out-of-repository Foundation navigation links."""

    resolved_repo_root = repo_root.resolve()
    navigation_paths = [
        *(resolved_repo_root / relative_path for relative_path in FOUNDATION_NAVIGATION_LINK_FILES),
        *sorted((resolved_repo_root / "docs").glob("FOUNDATION_*_BOUNDARY.md")),
    ]
    link_pattern = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
    findings: list[FoundationModeFinding] = []
    for navigation_path in navigation_paths:
        try:
            relative_path = navigation_path.relative_to(resolved_repo_root).as_posix()
        except ValueError:
            findings.append(
                FoundationModeFinding(
                    "foundation_navigation_surface_outside_repo",
                    f"navigation surface is outside repository: {navigation_path}",
                )
            )
            continue
        try:
            text = read_required_text(resolved_repo_root, relative_path)
        except OSError as exc:
            findings.append(FoundationModeFinding("foundation_file_missing", str(exc)))
            continue
        for match in link_pattern.finditer(text):
            target = match.group(1).strip()
            if _is_external_or_anchor_link(target):
                continue
            target_path = target.split("#", 1)[0]
            if not target_path:
                continue
            resolved_target = (navigation_path.parent / target_path).resolve()
            if not resolved_target.is_relative_to(resolved_repo_root):
                findings.append(
                    FoundationModeFinding(
                        "foundation_navigation_link_outside_repo",
                        f"{relative_path} links outside repository: {target}",
                    )
                )
                continue
            if not resolved_target.exists():
                findings.append(
                    FoundationModeFinding(
                        "foundation_navigation_link_missing",
                        f"{relative_path} has missing local link target: {target}",
                    )
                )
    return findings


def validate_foundation_ordered_paths(repo_root: Path = REPO_ROOT) -> list[FoundationModeFinding]:
    """Return findings when ordered Foundation paths lose coverage or sequence."""

    boundary_targets = {
        boundary_doc.name
        for boundary_doc in (repo_root / "docs").glob("FOUNDATION_*_BOUNDARY.md")
    }
    if not boundary_targets:
        return [
            FoundationModeFinding(
                "foundation_boundary_inventory_missing",
                "docs directory has no FOUNDATION_*_BOUNDARY.md files",
            )
        ]
    findings: list[FoundationModeFinding] = []
    findings.extend(
        _validate_ordered_foundation_section(
            repo_root,
            "docs/START_HERE.md",
            START_HERE_ORDER_START,
            START_HERE_ORDER_END,
            re.compile(r"^(?P<number>\d+)\. \*\*\[[^\]]+\]\((?P<target>[^)]+)\)", re.MULTILINE),
            {
                *boundary_targets,
                "FOUNDATION_MODE.md",
                "FOUNDATION_PREREQUISITES.md",
                "FOUNDATION_LOCAL_PROOF_THREAD.md",
            },
            "foundation_start_here_order",
        )
    )
    findings.extend(
        _validate_ordered_foundation_section(
            repo_root,
            "docs/FOUNDATION_PREREQUISITES.md",
            FOUNDATION_PREREQUISITE_ORDER_START,
            FOUNDATION_PREREQUISITE_ORDER_END,
            re.compile(r"^(?P<number>\d+)\. .*?\[[^\]]+\]\((?P<target>FOUNDATION_[^)]+\.md)\)", re.MULTILINE),
            {
                *boundary_targets,
                "FOUNDATION_MODE.md",
                "FOUNDATION_LOCAL_PROOF_THREAD.md",
            },
            "foundation_prerequisite_order",
        )
    )
    return findings


def validate_foundation_mode(repo_root: Path = REPO_ROOT) -> list[FoundationModeFinding]:
    """Validate the repository Foundation Mode posture and return findings."""

    return [
        *validate_core_guidance_surface_registration(repo_root),
        *validate_required_phrases(repo_root),
        *validate_forbidden_forward_phrases(repo_root),
        *validate_central_table_label_uniqueness(repo_root),
        *validate_central_foundation_dependency_headers(repo_root),
        *validate_prerequisite_go_deeper_boundary_links(repo_root),
        *validate_foundation_boundary_routing_surfaces(repo_root),
        *validate_foundation_boundary_status_blocks(repo_root),
        *validate_foundation_navigation_links(repo_root),
        *validate_foundation_ordered_paths(repo_root),
    ]


def _is_external_or_anchor_link(target: str) -> bool:
    if not target or target.startswith("#"):
        return True
    return bool(re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", target))


def _validate_ordered_foundation_section(
    repo_root: Path,
    relative_path: str,
    start_marker: str,
    end_marker: str,
    entry_pattern: re.Pattern[str],
    expected_foundation_targets: set[str],
    rule_prefix: str,
) -> list[FoundationModeFinding]:
    findings: list[FoundationModeFinding] = []
    try:
        text = read_required_text(repo_root, relative_path)
    except OSError as exc:
        return [FoundationModeFinding("foundation_file_missing", str(exc))]
    if start_marker not in text:
        return [
            FoundationModeFinding(
                f"{rule_prefix}_section_missing",
                f"{relative_path} missing ordered section start: {start_marker}",
            )
        ]
    section = text.split(start_marker, 1)[1]
    if end_marker not in section:
        findings.append(
            FoundationModeFinding(
                f"{rule_prefix}_section_end_missing",
                f"{relative_path} missing ordered section end: {end_marker}",
            )
        )
    else:
        section = section.split(end_marker, 1)[0]
    numbered_line_pattern = re.compile(r"^(?P<number>\d+)\. .+$", re.MULTILINE)
    numbers = [int(match.group("number")) for match in numbered_line_pattern.finditer(section)]
    entries = [
        (int(match.group("number")), match.group("target"))
        for match in entry_pattern.finditer(section)
    ]
    entry_targets = [target for _, target in entries]
    foundation_targets = {target for target in entry_targets if target.startswith("FOUNDATION_")}
    if not numbers or not entries:
        findings.append(
            FoundationModeFinding(
                f"{rule_prefix}_entries_missing",
                f"{relative_path} ordered section has no numbered Foundation entries",
            )
        )
    elif numbers != list(range(1, len(numbers) + 1)):
        findings.append(
            FoundationModeFinding(
                f"{rule_prefix}_numbers_not_consecutive",
                f"{relative_path} ordered section numbers must be consecutive from 1",
            )
        )
    duplicate_targets = sorted({target for target in entry_targets if entry_targets.count(target) > 1})
    if duplicate_targets:
        findings.append(
            FoundationModeFinding(
                f"{rule_prefix}_duplicate_targets",
                f"{relative_path} ordered section repeats targets: {', '.join(duplicate_targets)}",
            )
        )
    missing_targets = sorted(expected_foundation_targets - foundation_targets)
    unexpected_targets = sorted(foundation_targets - expected_foundation_targets)
    if missing_targets or unexpected_targets:
        findings.append(
            FoundationModeFinding(
                f"{rule_prefix}_foundation_targets_invalid",
                f"{relative_path} ordered section target drift; missing: {', '.join(missing_targets) or 'none'}; unexpected: {', '.join(unexpected_targets) or 'none'}",
            )
        )
    return findings


def _iter_markdown_tables(text: str) -> list[list[str]]:
    tables: list[list[str]] = []
    current_table: list[str] = []
    for line in text.splitlines():
        if line.startswith("|") and line.endswith("|"):
            current_table.append(line)
            continue
        if current_table:
            tables.append(current_table)
            current_table = []
    if current_table:
        tables.append(current_table)
    return tables


def main(argv: list[str] | None = None) -> int:
    """Validate Foundation Mode and print a deterministic status."""

    parser = argparse.ArgumentParser(description="Validate Mullusi Foundation Mode posture.")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    args = parser.parse_args(argv)

    findings = validate_foundation_mode(args.repo_root.resolve())
    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
