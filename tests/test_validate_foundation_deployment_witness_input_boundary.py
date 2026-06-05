"""Tests for the Foundation Mode deployment witness input boundary validator.

Purpose: prove issue #330 deployment witness input preparation stays local and
does not authorize live values, DNS mutation, endpoint readiness, workflow
dispatch, artifact publication, deployment status promotion, customer access,
personal-data collection, money movement, legal/business claims, publication,
or deployment.
Governance scope: Foundation Mode, issue #330, deployment witness inputs,
public-safe input names, endpoint contract labels, private-value exclusion,
external-action blocking, and deployment restraint.
Dependencies: scripts.validate_foundation_deployment_witness_input_boundary.
Invariants: deployment witness input surfaces remain AwaitingEvidence and
reject live value drift, readiness drift, dispatch drift, and promotion drift.
"""

from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_foundation_deployment_witness_input_boundary import (  # noqa: E402
    DEFAULT_DOC_PATH,
    DEFAULT_PACKET_PATH,
    EXPECTED_DOC_SURFACE_LABELS,
    EXPECTED_ENDPOINT_LABELS,
    EXPECTED_NEXT_ACTION,
    EXPECTED_PUBLIC_SAFE_NAMES,
    EXPECTED_SURFACE_NOTES,
    EXPECTED_SURFACES,
    EXPECTED_WITNESS_ID,
    load_json_object,
    load_text,
    validate_doc_text,
    validate_foundation_deployment_witness_input_boundary,
    validate_packet,
)


def test_foundation_deployment_witness_input_boundary_artifacts_pass() -> None:
    assert validate_foundation_deployment_witness_input_boundary() == []


def test_deployment_witness_input_witness_has_expected_identity_and_surfaces() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "deployment witness input witness")

    assert payload["witness_id"] == EXPECTED_WITNESS_ID
    assert tuple(
        (surface["surface_id"], surface["surface_type"], surface["state"])
        for surface in payload["surfaces"]
    ) == EXPECTED_SURFACES
    assert payload["runtime_witness_secret_value_allowed"] is False
    assert payload["runtime_conformance_secret_value_allowed"] is False
    assert payload["gateway_url_value_allowed"] is False
    assert payload["workflow_dispatch_allowed"] is False
    assert payload["deployment_allowed"] is False
    assert tuple(payload["public_safe_names"]) == EXPECTED_PUBLIC_SAFE_NAMES
    assert tuple(payload["endpoint_labels"]) == EXPECTED_ENDPOINT_LABELS
    assert payload["next_action"] == EXPECTED_NEXT_ACTION
    assert set(EXPECTED_SURFACE_NOTES) == {surface["surface_id"] for surface in payload["surfaces"]}
    assert all(
        surface["public_safe_note"] == EXPECTED_SURFACE_NOTES[surface["surface_id"]]
        for surface in payload["surfaces"]
    )


def test_doc_contains_public_safe_names_and_endpoint_labels() -> None:
    doc_text = load_text(DEFAULT_DOC_PATH, "deployment witness input doc")

    for public_safe_name in EXPECTED_PUBLIC_SAFE_NAMES:
        assert public_safe_name in doc_text
    for endpoint_label in EXPECTED_ENDPOINT_LABELS:
        assert endpoint_label in doc_text
    for surface_label in EXPECTED_DOC_SURFACE_LABELS:
        assert surface_label in doc_text


def test_witness_rejects_secret_url_variable_and_environment_values() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "deployment witness input witness")
    candidate = deepcopy(payload)
    candidate["runtime_witness_secret_value_allowed"] = True
    candidate["runtime_conformance_secret_value_allowed"] = True
    candidate["gateway_url_value_allowed"] = True
    candidate["expected_runtime_env_value_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "deployment_witness_input_root_value_invalid" for finding in findings)


def test_witness_rejects_public_safe_name_or_endpoint_label_drift() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "deployment witness input witness")
    candidate = deepcopy(payload)
    candidate["public_safe_names"] = list(reversed(candidate["public_safe_names"]))
    candidate["endpoint_labels"] = ["/health"]

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "deployment_witness_input_public_safe_names_invalid" for finding in findings)
    assert any(finding.rule_id == "deployment_witness_input_endpoint_labels_invalid" for finding in findings)


def test_witness_rejects_dns_endpoint_workflow_artifact_and_status_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "deployment witness input witness")
    candidate = deepcopy(payload)
    candidate["dns_mutation_allowed"] = True
    candidate["endpoint_reachability_claimed"] = True
    candidate["workflow_dispatch_allowed"] = True
    candidate["witness_artifact_publication_allowed"] = True
    candidate["deployment_status_promotion_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "deployment_witness_input_root_value_invalid" for finding in findings)


def test_witness_rejects_customer_money_legal_company_patent_and_deployment_claims() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "deployment witness input witness")
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
    assert any(finding.rule_id == "deployment_witness_input_root_value_invalid" for finding in findings)


def test_witness_rejects_surface_state_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "deployment witness input witness")
    candidate = deepcopy(payload)
    candidate["surfaces"][0]["state"] = "Ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "deployment_witness_input_surface_inventory_invalid" for finding in findings)
    assert any(finding.rule_id == "deployment_witness_input_surface_state_invalid" for finding in findings)


def test_witness_rejects_weakened_surface_note() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "deployment witness input witness")
    candidate = deepcopy(payload)
    candidate["surfaces"][0]["public_safe_note"] = "Runtime witness secret name is listed."

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "deployment_witness_input_surface_note_invalid" for finding in findings)


def test_witness_rejects_live_url_or_assignment_shape() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "deployment witness input witness")
    candidate = deepcopy(payload)
    candidate["surfaces"][2]["public_safe_note"] = "gateway_url=https://example.invalid"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "deployment_witness_input_forbidden_value_pattern" for finding in findings)


def test_witness_rejects_readiness_or_dispatch_phrase() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "deployment witness input witness")
    candidate = deepcopy(payload)
    candidate["next_action"] = "workflow dispatched and endpoint reachable"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "deployment_witness_input_forbidden_promotion_phrase" for finding in findings)


def test_witness_rejects_extra_next_action_text() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "deployment witness input witness")
    candidate = deepcopy(payload)
    candidate["next_action"] = f"{EXPECTED_NEXT_ACTION}; then dispatch workflow"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "deployment_witness_input_next_action_invalid" for finding in findings)


def test_doc_rejects_live_url_or_assignment_shape() -> None:
    doc_text = load_text(DEFAULT_DOC_PATH, "deployment witness input boundary doc")
    candidate = f"{doc_text}\ngateway_url=https://example.invalid\n"

    findings = validate_doc_text(candidate)

    assert findings
    assert any(finding.rule_id == "deployment_witness_input_forbidden_value_pattern" for finding in findings)


def test_doc_requires_every_surface_label() -> None:
    doc_text = load_text(DEFAULT_DOC_PATH, "deployment witness input boundary doc")
    candidate = doc_text.replace("Artifact publication gate", "Artifact gate", 1)

    findings = validate_doc_text(candidate)

    assert "Artifact publication gate" in EXPECTED_DOC_SURFACE_LABELS
    assert findings
    assert any(finding.rule_id == "foundation_deployment_witness_input_doc_surface_missing" for finding in findings)


def test_doc_rejects_readiness_or_dispatch_phrase() -> None:
    doc_text = load_text(DEFAULT_DOC_PATH, "deployment witness input boundary doc")
    candidate = f"{doc_text}\nEndpoint reachable and deployment is ready.\n"

    findings = validate_doc_text(candidate)

    assert findings
    assert any(finding.rule_id == "deployment_witness_input_forbidden_promotion_phrase" for finding in findings)
