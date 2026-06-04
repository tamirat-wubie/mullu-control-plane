"""Purpose: verify SDLC PR enforcement validation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.validate_sdlc_pr_enforcement.
Invariants:
  - PR evidence requirements remain present.
  - CI exposes a stable SDLC Governance Gate.
  - Build Verification depends on the SDLC gate.
  - Branch protection witness retains required status contexts.
  - Release policy links rollback, incidents, and closure.
"""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from dataclasses import replace
from pathlib import Path

import pytest
from scripts import validate_sdlc_pr_enforcement as validator


def test_current_sdlc_pr_enforcement_contract_passes() -> None:
    texts = validator.load_enforcement_texts()
    errors = validator.validate_contract(texts)

    assert errors == []
    assert "## SDLC / SDLD evidence" in texts.pr_template
    assert "name: SDLC Governance Gate" in texts.ci_workflow
    assert "SDLC route used" in texts.pr_template
    assert "python scripts/route_sdlc.py" in texts.pr_template
    assert "python scripts/validate_sdlc_route.py" in texts.pr_template
    assert "Gate decision envelope" in texts.pr_template
    assert "Implementation receipt" in texts.pr_template
    assert "Transition receipt" in texts.pr_template
    assert "Recovery handoff receipt" in texts.pr_template
    assert "Inventory closure" in texts.pr_template
    assert "Workspace preflight receipt" in texts.pr_template
    assert "Branch protection witness" in texts.pr_template
    assert "rollback_or_incident_handoff" in texts.enforcement_doc
    assert "sdlc_inventory_closure proves canonical schema and example coverage" in texts.enforcement_doc
    assert "sdlc_branch_ruleset_witness proves `main-protection`" in texts.enforcement_doc
    assert "sdlc_workspace_preflight_closure proves workspace preflight command" in texts.enforcement_doc
    assert "SDLC route used" in texts.enforcement_doc
    assert "recovery handoff has `sdlc_recovery_handoff_receipt` evidence" in texts.enforcement_doc
    assert texts.ruleset_witness["ruleset_name"] == "main-protection"


def test_ci_workflow_requires_sdlc_gate_before_build_verification() -> None:
    texts = validator.load_enforcement_texts()
    errors = validator.validate_ci_workflow(texts.ci_workflow)

    assert errors == []
    assert texts.ci_workflow.find("sdlc-governance-gate:") < texts.ci_workflow.find("build-verification:")
    assert "sdlc-governance-gate" in texts.ci_workflow
    assert "tests/test_validate_sdlc_pr_enforcement.py" in texts.ci_workflow
    assert "python scripts/validate_sdlc_route.py" in texts.ci_workflow
    assert "tests/test_validate_sdlc_route.py" in texts.ci_workflow
    assert "python scripts/run_workspace_governance_checks.py --json --receipt-path .tmp/workspace-governance-preflight-receipt.json" in texts.ci_workflow
    assert all(context in texts.ci_workflow for context in validator.REQUIRED_RULESET_STATUS_CONTEXTS)


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


def test_missing_gate_decision_envelope_evidence_is_rejected() -> None:
    texts = validator.load_enforcement_texts()
    invalid_template = texts.pr_template.replace("Gate decision envelope", "Gate refs")
    invalid_doc = texts.enforcement_doc.replace(
        "gate_decision_envelopes are retained through terminal closure",
        "gate refs exist",
    )

    template_errors = validator.validate_pr_template(invalid_template)
    doc_errors = validator.validate_enforcement_document(invalid_doc)

    assert "pull_request_template missing required term: Gate decision envelope" in template_errors
    assert any("gate_decision_envelopes are retained" in error for error in doc_errors)
    assert len(template_errors) + len(doc_errors) >= 2


def test_missing_transition_receipt_evidence_is_rejected() -> None:
    texts = validator.load_enforcement_texts()
    invalid_template = texts.pr_template.replace("Transition receipt", "State movement note")
    invalid_doc = texts.enforcement_doc.replace(
        "state transitions have `sdlc_transition_receipt` evidence",
        "state transitions have notes",
    )

    template_errors = validator.validate_pr_template(invalid_template)
    doc_errors = validator.validate_enforcement_document(invalid_doc)

    assert "pull_request_template missing required term: Transition receipt" in template_errors
    assert any("sdlc_transition_receipt" in error for error in doc_errors)
    assert len(template_errors) + len(doc_errors) >= 2


def test_missing_implementation_receipt_evidence_is_rejected() -> None:
    texts = validator.load_enforcement_texts()
    invalid_template = texts.pr_template.replace("Implementation receipt", "Delta note")
    invalid_doc = texts.enforcement_doc.replace(
        "implementation deltas have `sdlc_implementation_receipt` evidence",
        "implementation deltas have notes",
    )

    template_errors = validator.validate_pr_template(invalid_template)
    doc_errors = validator.validate_enforcement_document(invalid_doc)

    assert "pull_request_template missing required term: Implementation receipt" in template_errors
    assert any("sdlc_implementation_receipt" in error for error in doc_errors)
    assert len(template_errors) + len(doc_errors) >= 2


def test_missing_recovery_handoff_receipt_evidence_is_rejected() -> None:
    texts = validator.load_enforcement_texts()
    invalid_template = texts.pr_template.replace("Recovery handoff receipt", "Recovery note")
    invalid_doc = texts.enforcement_doc.replace(
        "recovery handoff has `sdlc_recovery_handoff_receipt` evidence",
        "recovery handoff has notes",
    )

    template_errors = validator.validate_pr_template(invalid_template)
    doc_errors = validator.validate_enforcement_document(invalid_doc)

    assert "pull_request_template missing required term: Recovery handoff receipt" in template_errors
    assert any("sdlc_recovery_handoff_receipt" in error for error in doc_errors)
    assert len(template_errors) + len(doc_errors) >= 2


def test_missing_inventory_closure_evidence_is_rejected() -> None:
    texts = validator.load_enforcement_texts()
    invalid_template = texts.pr_template.replace("Inventory closure", "Inventory note")
    invalid_doc = texts.enforcement_doc.replace(
        "sdlc_inventory_closure proves canonical schema and example coverage",
        "inventory notes exist",
    )

    template_errors = validator.validate_pr_template(invalid_template)
    doc_errors = validator.validate_enforcement_document(invalid_doc)

    assert "pull_request_template missing required term: Inventory closure" in template_errors
    assert any("sdlc_inventory_closure" in error for error in doc_errors)
    assert len(template_errors) + len(doc_errors) >= 2


def test_missing_workspace_preflight_closure_evidence_is_rejected() -> None:
    texts = validator.load_enforcement_texts()
    invalid_template = texts.pr_template.replace("Workspace preflight receipt", "Workspace preflight note")
    invalid_doc = texts.enforcement_doc.replace(
        "sdlc_workspace_preflight_closure proves workspace preflight command, receipt artifact, validator output, and closure retention",
        "workspace preflight is mentioned",
    )

    template_errors = validator.validate_pr_template(invalid_template)
    doc_errors = validator.validate_enforcement_document(invalid_doc)

    assert "pull_request_template missing required term: Workspace preflight receipt" in template_errors
    assert any("sdlc_workspace_preflight_closure" in error for error in doc_errors)
    assert len(template_errors) + len(doc_errors) >= 2


def test_missing_branch_ruleset_evidence_is_rejected() -> None:
    texts = validator.load_enforcement_texts()
    invalid_template = texts.pr_template.replace("Branch protection witness", "Branch note")
    invalid_doc = texts.enforcement_doc.replace(
        "sdlc_branch_ruleset_witness proves `main-protection` requires SDLC-critical status contexts",
        "branch protection exists",
    )

    template_errors = validator.validate_pr_template(invalid_template)
    doc_errors = validator.validate_enforcement_document(invalid_doc)

    assert "pull_request_template missing required term: Branch protection witness" in template_errors
    assert any("sdlc_branch_ruleset_witness" in error for error in doc_errors)
    assert len(template_errors) + len(doc_errors) >= 2


def test_ruleset_witness_requires_exact_sdlc_status_contexts() -> None:
    witness = validator.load_enforcement_texts().ruleset_witness

    errors = validator.validate_ruleset_witness(witness)

    observed_rule_types = {rule["type"] for rule in witness["rules"]}
    status_rule = next(rule for rule in witness["rules"] if rule["type"] == "required_status_checks")
    observed_contexts = {check["context"] for check in status_rule["required_status_checks"]}
    assert errors == []
    assert set(validator.REQUIRED_RULESET_TYPES).issubset(observed_rule_types)
    assert observed_contexts == set(validator.REQUIRED_RULESET_STATUS_CONTEXTS)
    assert witness["current_user_can_bypass"] == "never"


def test_ruleset_witness_rejects_missing_sdlc_gate_and_bypass_actor() -> None:
    witness = json.loads(json.dumps(validator.load_enforcement_texts().ruleset_witness))
    witness["bypass_actors"] = [{"actor_type": "Team", "actor_id": 1}]
    status_rule = next(rule for rule in witness["rules"] if rule["type"] == "required_status_checks")
    status_rule["required_status_checks"] = [
        check for check in status_rule["required_status_checks"] if check["context"] != "SDLC Governance Gate"
    ]

    errors = validator.validate_ruleset_witness(witness)

    assert "sdlc_ruleset_witness: bypass_actors must be empty" in errors
    assert any("SDLC Governance Gate" in error for error in errors)
    assert len(errors) >= 2


def test_release_policy_without_incident_linkage_is_rejected() -> None:
    texts = validator.load_enforcement_texts()
    invalid_policy = texts.release_policy.replace("incident_recovery_path_if_rollback_fails", "fallback_path")

    errors = validator.validate_release_policy_links(invalid_policy)

    assert "sdlc_release_policy missing required term: incident_recovery_path_if_rollback_fails" in errors
    assert len(errors) >= 1
    assert "## Rollback And Incident Linkage" in invalid_policy


def test_release_policy_without_recovery_handoff_schema_is_rejected() -> None:
    texts = validator.load_enforcement_texts()
    invalid_policy = texts.release_policy.replace("sdlc_recovery_handoff_receipt", "recovery_handoff_note")

    errors = validator.validate_release_policy_links(invalid_policy)

    assert "sdlc_release_policy missing required term: sdlc_recovery_handoff_receipt" in errors
    assert len(errors) >= 1
    assert "incident_recovery_path_if_rollback_fails" in invalid_policy


def test_cli_json_receipt_reports_passed_contract() -> None:
    stdout_buffer = io.StringIO()

    with redirect_stdout(stdout_buffer):
        exit_code = validator.main(["--json"])

    report = json.loads(stdout_buffer.getvalue())
    assert exit_code == 0
    assert report["receipt_id"] == "sdlc_pr_enforcement_validation_receipt"
    assert report["valid"] is True
    assert report["status"] == "passed"
    assert report["check_count"] == 5
    assert any(check["name"] == "sdlc_branch_ruleset_witness" for check in report["checks"])
    assert "docs/main-protection-ruleset-witness.json" in report["document_paths"]


def test_cli_text_output_reports_ruleset_witness_check() -> None:
    stdout_buffer = io.StringIO()

    with redirect_stdout(stdout_buffer):
        exit_code = validator.main([])

    output = stdout_buffer.getvalue()
    assert exit_code == 0
    assert "[PASS] sdlc_branch_ruleset_witness" in output
    assert output.count("[PASS]") == validator.build_validation_report()["check_count"]
    assert output.endswith("STATUS: passed\n")


def test_receipt_path_rejects_escape_and_non_json() -> None:
    with pytest.raises(ValueError):
        validator.resolve_receipt_path(Path("../sdlc_pr_enforcement_receipt.json"))
    with pytest.raises(ValueError):
        validator.resolve_receipt_path(Path(".change_assurance/sdlc_pr_enforcement_receipt.txt"))
    resolved_path = validator.resolve_receipt_path(Path(".change_assurance/sdlc_pr_enforcement_receipt.json"))

    assert resolved_path.suffix == ".json"
    assert validator.WORKSPACE_ROOT.resolve() in resolved_path.parents
    assert resolved_path.name == "sdlc_pr_enforcement_receipt.json"


def test_validate_contract_uses_injected_texts_for_drift_detection() -> None:
    texts = validator.load_enforcement_texts()
    invalid_texts = replace(texts, enforcement_doc=texts.enforcement_doc.replace("SDLC Governance Gate", "Gate"))

    errors = validator.validate_contract(invalid_texts)

    assert any("sdlc_pr_enforcement_doc missing required term: SDLC Governance Gate" in error for error in errors)
    assert len(errors) >= 1
    assert invalid_texts.pr_template == texts.pr_template
