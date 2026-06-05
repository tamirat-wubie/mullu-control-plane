"""Tests for the Foundation Mode deployment witness dispatch rehearsal validator.

Purpose: prove issue #330 manual workflow dispatch preparation stays local and
does not authorize workflow dispatch, GitHub mutation, live input values, secret
handling, repository variable binding, workflow-run claims, artifact
publication, deployment-claim publication, status promotion, operator approval,
customer access, personal-data collection, money movement, legal/business
claims, publication, or deployment.
Governance scope: Foundation Mode, issue #330, deployment witness dispatch
rehearsal, public-safe dispatch labels, private-value exclusion,
external-action blocking, and deployment restraint.
Dependencies: scripts.validate_foundation_deployment_witness_dispatch_rehearsal_boundary.
Invariants: dispatch rehearsal surfaces remain AwaitingEvidence and reject live
value drift, workflow mutation drift, receipt drift, and promotion drift.
"""

from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_foundation_deployment_witness_dispatch_rehearsal_boundary import (  # noqa: E402
    DEFAULT_DOC_PATH,
    DEFAULT_PACKET_PATH,
    EXPECTED_DISPATCH_LABELS,
    EXPECTED_DOC_SURFACE_LABELS,
    EXPECTED_NEXT_ACTION,
    EXPECTED_SURFACE_NOTES,
    EXPECTED_SURFACES,
    EXPECTED_WITNESS_ID,
    load_json_object,
    load_text,
    validate_doc_text,
    validate_foundation_deployment_witness_dispatch_rehearsal_boundary,
    validate_packet,
)


def test_foundation_deployment_witness_dispatch_rehearsal_artifacts_pass() -> None:
    assert validate_foundation_deployment_witness_dispatch_rehearsal_boundary() == []


def test_dispatch_rehearsal_witness_has_expected_identity_and_surfaces() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "deployment witness dispatch rehearsal witness")

    assert payload["witness_id"] == EXPECTED_WITNESS_ID
    assert tuple(
        (surface["surface_id"], surface["surface_type"], surface["state"])
        for surface in payload["surfaces"]
    ) == EXPECTED_SURFACES
    assert tuple(payload["dispatch_labels"]) == EXPECTED_DISPATCH_LABELS
    assert payload["next_action"] == EXPECTED_NEXT_ACTION
    assert payload["workflow_dispatch_allowed"] is False
    assert payload["github_api_mutation_allowed"] is False
    assert payload["manual_workflow_execution_allowed"] is False
    assert payload["workflow_run_claimed"] is False
    assert payload["deployment_allowed"] is False
    assert set(EXPECTED_SURFACE_NOTES) == {surface["surface_id"] for surface in payload["surfaces"]}
    assert all(
        surface["public_safe_note"] == EXPECTED_SURFACE_NOTES[surface["surface_id"]]
        for surface in payload["surfaces"]
    )


def test_doc_contains_dispatch_labels_and_surface_labels() -> None:
    doc_text = load_text(DEFAULT_DOC_PATH, "deployment witness dispatch rehearsal doc")

    for dispatch_label in EXPECTED_DISPATCH_LABELS:
        assert dispatch_label in doc_text
    for surface_label in EXPECTED_DOC_SURFACE_LABELS:
        assert surface_label in doc_text


def test_witness_rejects_workflow_dispatch_github_mutation_and_manual_execution() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "deployment witness dispatch rehearsal witness")
    candidate = deepcopy(payload)
    candidate["workflow_dispatch_allowed"] = True
    candidate["github_api_mutation_allowed"] = True
    candidate["manual_workflow_execution_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "deployment_witness_dispatch_rehearsal_root_value_invalid" for finding in findings)


def test_witness_rejects_live_input_ref_run_and_receipt_values() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "deployment witness dispatch rehearsal witness")
    candidate = deepcopy(payload)
    candidate["gateway_url_value_allowed"] = True
    candidate["expected_environment_value_recorded"] = True
    candidate["workflow_ref_value_recorded"] = True
    candidate["workflow_run_id_recorded"] = True
    candidate["dispatch_receipt_recorded"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "deployment_witness_dispatch_rehearsal_root_value_invalid" for finding in findings)


def test_witness_rejects_secret_variable_workflow_artifact_and_status_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "deployment witness dispatch rehearsal witness")
    candidate = deepcopy(payload)
    candidate["secret_value_allowed"] = True
    candidate["secret_presence_claimed"] = True
    candidate["repository_variable_binding_allowed"] = True
    candidate["workflow_run_claimed"] = True
    candidate["artifact_publication_allowed"] = True
    candidate["deployment_claim_published_claimed"] = True
    candidate["deployment_status_promotion_allowed"] = True
    candidate["operator_approval_claimed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "deployment_witness_dispatch_rehearsal_root_value_invalid" for finding in findings)


def test_witness_rejects_customer_money_legal_company_patent_and_deployment_claims() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "deployment witness dispatch rehearsal witness")
    candidate = deepcopy(payload)
    candidate["customer_access_allowed"] = True
    candidate["personal_data_collection_allowed"] = True
    candidate["money_movement_allowed"] = True
    candidate["legal_clearance_claimed"] = True
    candidate["company_formation_claimed"] = True
    candidate["patent_claimed"] = True
    candidate["deployment_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "deployment_witness_dispatch_rehearsal_root_value_invalid" for finding in findings)


def test_witness_rejects_dispatch_label_drift() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "deployment witness dispatch rehearsal witness")
    candidate = deepcopy(payload)
    candidate["dispatch_labels"] = list(reversed(candidate["dispatch_labels"]))

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "deployment_witness_dispatch_rehearsal_dispatch_labels_invalid" for finding in findings)


def test_witness_rejects_surface_state_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "deployment witness dispatch rehearsal witness")
    candidate = deepcopy(payload)
    candidate["surfaces"][0]["state"] = "Ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "deployment_witness_dispatch_rehearsal_surface_inventory_invalid" for finding in findings)
    assert any(finding.rule_id == "deployment_witness_dispatch_rehearsal_surface_state_invalid" for finding in findings)


def test_witness_rejects_weakened_surface_note() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "deployment witness dispatch rehearsal witness")
    candidate = deepcopy(payload)
    candidate["surfaces"][0]["public_safe_note"] = "Preflight dependency label is listed."

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "deployment_witness_dispatch_rehearsal_surface_note_invalid" for finding in findings)


def test_witness_rejects_live_url_or_assignment_shape() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "deployment witness dispatch rehearsal witness")
    candidate = deepcopy(payload)
    candidate["surfaces"][0]["public_safe_note"] = "gateway_url=https://example.invalid"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "deployment_witness_dispatch_rehearsal_forbidden_value_pattern" for finding in findings)


def test_witness_rejects_dispatch_or_publication_phrase() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "deployment witness dispatch rehearsal witness")
    candidate = deepcopy(payload)
    candidate["next_action"] = "workflow dispatched and artifact is published"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "deployment_witness_dispatch_rehearsal_forbidden_promotion_phrase" for finding in findings)


def test_witness_rejects_extra_next_action_text() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "deployment witness dispatch rehearsal witness")
    candidate = deepcopy(payload)
    candidate["next_action"] = f"{EXPECTED_NEXT_ACTION}; then dispatch workflow"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "deployment_witness_dispatch_rehearsal_next_action_invalid" for finding in findings)


def test_doc_rejects_live_url_or_assignment_shape() -> None:
    doc_text = load_text(DEFAULT_DOC_PATH, "deployment witness dispatch rehearsal doc")
    candidate = f"{doc_text}\ngateway_url=https://example.invalid\n"

    findings = validate_doc_text(candidate)

    assert findings
    assert any(finding.rule_id == "deployment_witness_dispatch_rehearsal_forbidden_value_pattern" for finding in findings)


def test_doc_requires_every_surface_label() -> None:
    doc_text = load_text(DEFAULT_DOC_PATH, "deployment witness dispatch rehearsal doc")
    candidate = doc_text.replace("Dispatch receipt slot", "Dispatch slot", 1)

    findings = validate_doc_text(candidate)

    assert "Dispatch receipt slot" in EXPECTED_DOC_SURFACE_LABELS
    assert findings
    assert any(
        finding.rule_id == "foundation_deployment_witness_dispatch_rehearsal_doc_surface_missing"
        for finding in findings
    )


def test_doc_rejects_dispatch_or_publication_phrase() -> None:
    doc_text = load_text(DEFAULT_DOC_PATH, "deployment witness dispatch rehearsal doc")
    candidate = f"{doc_text}\nWorkflow dispatched and deployment is ready.\n"

    findings = validate_doc_text(candidate)

    assert findings
    assert any(finding.rule_id == "deployment_witness_dispatch_rehearsal_forbidden_promotion_phrase" for finding in findings)
