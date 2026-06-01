"""Purpose: verify SDLC PR enforcement validation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.validate_sdlc_pr_enforcement.
Invariants:
  - PR evidence requirements remain present.
  - CI exposes a stable SDLC Governance Gate.
  - Build Verification depends on the SDLC gate.
  - Release policy links rollback, incidents, and closure.
"""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from dataclasses import replace

from scripts import validate_sdlc_pr_enforcement as validator


def test_current_sdlc_pr_enforcement_contract_passes() -> None:
    texts = validator.load_enforcement_texts()
    errors = validator.validate_contract(texts)

    assert errors == []
    assert "## SDLC / SDLD evidence" in texts.pr_template
    assert "name: SDLC Governance Gate" in texts.ci_workflow
    assert "rollback_or_incident_handoff" in texts.enforcement_doc


def test_ci_workflow_requires_sdlc_gate_before_build_verification() -> None:
    texts = validator.load_enforcement_texts()
    errors = validator.validate_ci_workflow(texts.ci_workflow)

    assert errors == []
    assert texts.ci_workflow.find("sdlc-governance-gate:") < texts.ci_workflow.find("build-verification:")
    assert "sdlc-governance-gate" in texts.ci_workflow
    assert "tests/test_validate_sdlc_pr_enforcement.py" in texts.ci_workflow


def test_missing_build_verification_dependency_is_rejected() -> None:
    texts = validator.load_enforcement_texts()
    invalid_workflow = texts.ci_workflow.replace("schema-validation, sdlc-governance-gate,", "schema-validation,")

    errors = validator.validate_ci_workflow(invalid_workflow)

    assert "ci_workflow missing Build Verification dependency on sdlc-governance-gate" in errors
    assert len(errors) >= 1
    assert "name: SDLC Governance Gate" in invalid_workflow


def test_missing_pr_template_evidence_is_rejected() -> None:
    texts = validator.load_enforcement_texts()
    invalid_template = texts.pr_template.replace("Verification receipt", "Validation note")

    errors = validator.validate_pr_template(invalid_template)

    assert "pull_request_template missing required term: Verification receipt" in errors
    assert len(errors) >= 1
    assert "## SDLC / SDLD evidence" in invalid_template


def test_release_policy_without_incident_linkage_is_rejected() -> None:
    texts = validator.load_enforcement_texts()
    invalid_policy = texts.release_policy.replace("incident_recovery_path_if_rollback_fails", "fallback_path")

    errors = validator.validate_release_policy_links(invalid_policy)

    assert "sdlc_release_policy missing required term: incident_recovery_path_if_rollback_fails" in errors
    assert len(errors) >= 1
    assert "## Rollback And Incident Linkage" in invalid_policy


def test_cli_json_receipt_reports_passed_contract() -> None:
    stdout_buffer = io.StringIO()

    with redirect_stdout(stdout_buffer):
        exit_code = validator.main(["--json"])

    report = json.loads(stdout_buffer.getvalue())
    assert exit_code == 0
    assert report["receipt_id"] == "sdlc_pr_enforcement_validation_receipt"
    assert report["valid"] is True
    assert report["status"] == "passed"
    assert report["check_count"] == 4


def test_validate_contract_uses_injected_texts_for_drift_detection() -> None:
    texts = validator.load_enforcement_texts()
    invalid_texts = replace(texts, enforcement_doc=texts.enforcement_doc.replace("SDLC Governance Gate", "Gate"))

    errors = validator.validate_contract(invalid_texts)

    assert any("sdlc_pr_enforcement_doc missing required term: SDLC Governance Gate" in error for error in errors)
    assert len(errors) >= 1
    assert invalid_texts.pr_template == texts.pr_template
