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
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]

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
        "[`docs/FOUNDATION_SOURCE_CONTROL_BOUNDARY.md`](docs/FOUNDATION_SOURCE_CONTROL_BOUNDARY.md)",
        "[`docs/FOUNDATION_LOCAL_PROOF_THREAD.md`](docs/FOUNDATION_LOCAL_PROOF_THREAD.md)",
        "[`docs/FOUNDATION_SECRETS_CREDENTIALS_BOUNDARY.md`](docs/FOUNDATION_SECRETS_CREDENTIALS_BOUNDARY.md)",
        "[`docs/FOUNDATION_COST_BUDGET_BOUNDARY.md`](docs/FOUNDATION_COST_BUDGET_BOUNDARY.md)",
        "[`docs/FOUNDATION_RUNTIME_ENVIRONMENT_BOUNDARY.md`](docs/FOUNDATION_RUNTIME_ENVIRONMENT_BOUNDARY.md)",
        "[`docs/FOUNDATION_BACKUP_EXPORT_BOUNDARY.md`](docs/FOUNDATION_BACKUP_EXPORT_BOUNDARY.md)",
        "[`docs/FOUNDATION_PRODUCT_SCOPE_BOUNDARY.md`](docs/FOUNDATION_PRODUCT_SCOPE_BOUNDARY.md)",
        "[`docs/FOUNDATION_SUPPORT_READINESS_BOUNDARY.md`](docs/FOUNDATION_SUPPORT_READINESS_BOUNDARY.md)",
        "[`docs/FOUNDATION_INTAKE_ONBOARDING_BOUNDARY.md`](docs/FOUNDATION_INTAKE_ONBOARDING_BOUNDARY.md)",
        "[`docs/FOUNDATION_PRIVACY_DATA_BOUNDARY.md`](docs/FOUNDATION_PRIVACY_DATA_BOUNDARY.md)",
        "[`docs/FOUNDATION_PRIVATE_RECOVERY_BOUNDARY.md`](docs/FOUNDATION_PRIVATE_RECOVERY_BOUNDARY.md)",
        "[`docs/FOUNDATION_DOMAIN_EMAIL_BOUNDARY.md`](docs/FOUNDATION_DOMAIN_EMAIL_BOUNDARY.md)",
        "[`docs/FOUNDATION_LEGAL_BUSINESS_BOUNDARY.md`](docs/FOUNDATION_LEGAL_BUSINESS_BOUNDARY.md)",
    ),
    "docs/FOUNDATION_MODE.md": (
        "Foundation Mode means the project is being prepared carefully",
        "before deployment, company formation, customer access, or paid infrastructure",
        "For the step-by-step prerequisite ledger",
        "[Foundation Prerequisites](FOUNDATION_PREREQUISITES.md)",
        "[Foundation Source Control Boundary](FOUNDATION_SOURCE_CONTROL_BOUNDARY.md)",
        "[Foundation Secrets Credentials Boundary](FOUNDATION_SECRETS_CREDENTIALS_BOUNDARY.md)",
        "[Foundation Cost Budget Boundary](FOUNDATION_COST_BUDGET_BOUNDARY.md)",
        "[Foundation Runtime Environment Boundary](FOUNDATION_RUNTIME_ENVIRONMENT_BOUNDARY.md)",
        "[Foundation Backup Export Boundary](FOUNDATION_BACKUP_EXPORT_BOUNDARY.md)",
        "[Foundation Private Recovery Boundary](FOUNDATION_PRIVATE_RECOVERY_BOUNDARY.md)",
        "[Foundation Domain Email Boundary](FOUNDATION_DOMAIN_EMAIL_BOUNDARY.md)",
        "[Foundation Product Scope Boundary](FOUNDATION_PRODUCT_SCOPE_BOUNDARY.md)",
        "[Foundation Support Readiness Boundary](FOUNDATION_SUPPORT_READINESS_BOUNDARY.md)",
        "[Foundation Intake Onboarding Boundary](FOUNDATION_INTAKE_ONBOARDING_BOUNDARY.md)",
        "[Foundation Privacy Data Boundary](FOUNDATION_PRIVACY_DATA_BOUNDARY.md)",
        "[Foundation Legal Business Boundary](FOUNDATION_LEGAL_BUSINESS_BOUNDARY.md)",
        "Do not push toward deployment, public launch, customers, LLC formation",
    ),
    "docs/FOUNDATION_PREREQUISITES.md": (
        "this is the checklist for preparing the foundation before",
        "Atomic Prerequisite Ledger",
        "[Foundation Source Control Boundary](FOUNDATION_SOURCE_CONTROL_BOUNDARY.md)",
        "[Foundation Local Proof Thread](FOUNDATION_LOCAL_PROOF_THREAD.md)",
        "[Foundation Private Recovery Boundary](FOUNDATION_PRIVATE_RECOVERY_BOUNDARY.md)",
        "[Foundation Secrets Credentials Boundary](FOUNDATION_SECRETS_CREDENTIALS_BOUNDARY.md)",
        "[Foundation Cost Budget Boundary](FOUNDATION_COST_BUDGET_BOUNDARY.md)",
        "[Foundation Runtime Environment Boundary](FOUNDATION_RUNTIME_ENVIRONMENT_BOUNDARY.md)",
        "[Foundation Backup Export Boundary](FOUNDATION_BACKUP_EXPORT_BOUNDARY.md)",
        "[Foundation Domain Email Boundary](FOUNDATION_DOMAIN_EMAIL_BOUNDARY.md)",
        "[Foundation Product Scope Boundary](FOUNDATION_PRODUCT_SCOPE_BOUNDARY.md)",
        "[Foundation Support Readiness Boundary](FOUNDATION_SUPPORT_READINESS_BOUNDARY.md)",
        "[Foundation Intake Onboarding Boundary](FOUNDATION_INTAKE_ONBOARDING_BOUNDARY.md)",
        "[Foundation Privacy Data Boundary](FOUNDATION_PRIVACY_DATA_BOUNDARY.md)",
        "[Foundation Legal Business Boundary](FOUNDATION_LEGAL_BUSINESS_BOUNDARY.md)",
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
    "docs/FOUNDATION_LEGAL_BUSINESS_BOUNDARY.md": (
        "Foundation Legal Business Boundary",
        "Question packet: [`../examples/foundation_legal_business_questions.awaiting_review.json`]",
        "Rule: Legal and business readiness stays `AwaitingEvidence` until qualified",
        "No legal clearance, company readiness, patent protection, trademark clearance,",
        "paid_launch_allowed=false",
        "money_movement_allowed=false",
    ),
    "docs/START_HERE.md": (
        "[Foundation Prerequisites](FOUNDATION_PREREQUISITES.md)",
        "[Foundation Source Control Boundary](FOUNDATION_SOURCE_CONTROL_BOUNDARY.md)",
        "[Foundation Local Proof Thread](FOUNDATION_LOCAL_PROOF_THREAD.md)",
        "[Foundation Secrets Credentials Boundary](FOUNDATION_SECRETS_CREDENTIALS_BOUNDARY.md)",
        "[Foundation Cost Budget Boundary](FOUNDATION_COST_BUDGET_BOUNDARY.md)",
        "[Foundation Runtime Environment Boundary](FOUNDATION_RUNTIME_ENVIRONMENT_BOUNDARY.md)",
        "[Foundation Backup Export Boundary](FOUNDATION_BACKUP_EXPORT_BOUNDARY.md)",
        "[Foundation Private Recovery Boundary](FOUNDATION_PRIVATE_RECOVERY_BOUNDARY.md)",
        "[Foundation Domain Email Boundary](FOUNDATION_DOMAIN_EMAIL_BOUNDARY.md)",
        "[Foundation Product Scope Boundary](FOUNDATION_PRODUCT_SCOPE_BOUNDARY.md)",
        "[Foundation Support Readiness Boundary](FOUNDATION_SUPPORT_READINESS_BOUNDARY.md)",
        "[Foundation Intake Onboarding Boundary](FOUNDATION_INTAKE_ONBOARDING_BOUNDARY.md)",
        "[Foundation Privacy Data Boundary](FOUNDATION_PRIVACY_DATA_BOUNDARY.md)",
        "[Foundation Legal Business Boundary](FOUNDATION_LEGAL_BUSINESS_BOUNDARY.md)",
        "what to prepare now, what to delay, and what evidence to keep",
    ),
    "docs/CURRENT_READINESS_SNAPSHOT.md": (
        "Prerequisite ledger",
        "`docs/FOUNDATION_PREREQUISITES.md`",
        "`docs/FOUNDATION_SECRETS_CREDENTIALS_BOUNDARY.md`",
        "`docs/FOUNDATION_COST_BUDGET_BOUNDARY.md`",
        "`docs/FOUNDATION_RUNTIME_ENVIRONMENT_BOUNDARY.md`",
        "`docs/FOUNDATION_BACKUP_EXPORT_BOUNDARY.md`",
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


def validate_required_phrases(repo_root: Path = REPO_ROOT) -> list[FoundationModeFinding]:
    """Return findings for missing current-posture anchor phrases."""

    findings: list[FoundationModeFinding] = []
    for relative_path, required_phrases in REQUIRED_PHRASES_BY_FILE.items():
        try:
            text = read_required_text(repo_root, relative_path)
        except OSError as exc:
            findings.append(FoundationModeFinding("foundation_file_missing", str(exc)))
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


def validate_foundation_mode(repo_root: Path = REPO_ROOT) -> list[FoundationModeFinding]:
    """Validate the repository Foundation Mode posture and return findings."""

    return [
        *validate_required_phrases(repo_root),
        *validate_forbidden_forward_phrases(repo_root),
    ]


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
