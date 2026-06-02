"""Tests for the Foundation Mode posture validator.

Purpose: lock current solo-founder Foundation Mode guidance into the test suite.
Governance scope: Foundation Mode, access-language blocking, and current public
copy boundaries.
Dependencies: scripts.validate_foundation_mode.
Invariants: Foundation Mode remains local-proof-first and does not authorize
customer access, pilot access, beta invitation, waitlist, or deployment claims.
"""

from __future__ import annotations

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_foundation_mode import (  # noqa: E402
    REQUIRED_PHRASES_BY_FILE,
    validate_forward_text_boundary,
    validate_foundation_mode,
    validate_required_phrases,
)


def test_foundation_mode_posture_passes() -> None:
    assert validate_foundation_mode() == []


def test_required_phrase_map_covers_current_guidance_surfaces() -> None:
    assert "docs/FOUNDATION_MODE.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_PREREQUISITES.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_OPERATOR_READINESS_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_LEARNING_PATH_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_ARCHITECTURE_MAP_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_SYSTEM_BOUNDARY_INVENTORY_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_MODULE_INVENTORY_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_COMPONENT_CONTRACT_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_INTERFACE_MAP_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_DEPENDENCY_GRAPH_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_INVARIANT_MAP_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_HAZARD_MAP_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_PROOF_REFERENCE_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_GAP_REGISTER_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_DIFF_REVIEW_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_CHANGE_HANDOFF_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_LOCAL_WORKSTATION_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_DOCUMENTATION_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_PLAIN_LANGUAGE_STATUS_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_CLAIM_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_WEBSITE_POSTURE_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_RESEARCH_NOTEBOOK_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_EVIDENCE_LEDGER_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_DECISION_JOURNAL_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_NEXT_ACTION_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_TEST_EVIDENCE_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_SOURCE_CONTROL_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_LOCAL_PROOF_THREAD.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_SECRETS_CREDENTIALS_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_SECURITY_BASELINE_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_COST_BUDGET_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_PAYMENT_PROVIDER_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_RUNTIME_ENVIRONMENT_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_BACKUP_EXPORT_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_DEPLOYMENT_DEFERRAL_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_EXTERNAL_INFRASTRUCTURE_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_PILOT_DEFERRAL_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_PRIVATE_RECOVERY_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_DOMAIN_EMAIL_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_PRODUCT_SCOPE_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_SUPPORT_READINESS_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_INTAKE_ONBOARDING_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_PRIVACY_DATA_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/FOUNDATION_LEGAL_BUSINESS_BOUNDARY.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/explain/PLAIN_ENGLISH.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/START_HERE.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/WEBSITE_UPDATE_CHECKLIST.md" in REQUIRED_PHRASES_BY_FILE
    assert "docs/PUBLIC_NAMING_REVIEW_PACKET.md" in REQUIRED_PHRASES_BY_FILE
    assert "site/mullu/index.html" in REQUIRED_PHRASES_BY_FILE


def test_required_phrase_validator_rejects_missing_foundation_doc(tmp_path: Path) -> None:
    findings = validate_required_phrases(tmp_path)

    assert findings
    assert any(finding.rule_id == "foundation_file_missing" for finding in findings)


def test_forward_text_boundary_rejects_access_invitation() -> None:
    findings = validate_forward_text_boundary(
        "docs/example.md",
        "Primary action: Request access when ready.",
    )

    assert findings
    assert findings[0].rule_id == "foundation_forbidden_forward_phrase"


def test_forward_text_boundary_allows_blocking_waitlist_language() -> None:
    findings = validate_forward_text_boundary(
        "docs/example.md",
        "Current copy must be foundation-stage with no access, waitlist, or beta invitation.",
    )

    assert findings == []
