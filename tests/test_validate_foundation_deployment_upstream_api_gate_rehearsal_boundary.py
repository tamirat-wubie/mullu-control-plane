"""Tests for the Foundation Mode deployment upstream API gate rehearsal validator.

Purpose: prove issue #330 upstream API gate preparation stays local and does
not authorize upstream readiness, reporter execution, live target values,
production dependency values, DNS target selection, publication, workflow
dispatch, readiness claims, or deployment.
Governance scope: Foundation Mode, issue #330 upstream API gate rehearsal,
public-safe gate labels, external-value exclusion, promotion blocking,
workflow blocking, publication blocking, and deployment restraint.
Dependencies: scripts.validate_foundation_deployment_upstream_api_gate_rehearsal_boundary.
Invariants: rehearsal surfaces remain AwaitingEvidence and reject upstream
readiness drift, value drift, DNS publication drift, workflow drift, and
deployment drift.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_foundation_deployment_upstream_api_gate_rehearsal_boundary import (  # noqa: E402
    DEFAULT_DOC_PATH,
    DEFAULT_PACKET_PATH,
    EXPECTED_FIELD_LABELS,
    EXPECTED_SURFACE_NOTES,
    EXPECTED_SURFACES,
    EXPECTED_WITNESS_ID,
    load_json_object,
    load_text,
    validate_doc_text,
    validate_foundation_deployment_upstream_api_gate_rehearsal_boundary,
    validate_packet,
)


def test_foundation_deployment_upstream_api_gate_rehearsal_artifacts_pass() -> None:
    assert validate_foundation_deployment_upstream_api_gate_rehearsal_boundary() == []


def test_upstream_api_gate_witness_has_expected_identity_labels_and_surfaces() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "deployment upstream API gate rehearsal witness")

    assert payload["witness_id"] == EXPECTED_WITNESS_ID
    assert tuple(payload["field_labels"]) == EXPECTED_FIELD_LABELS
    assert tuple(
        (surface["surface_id"], surface["surface_type"], surface["state"])
        for surface in payload["surfaces"]
    ) == EXPECTED_SURFACES
    assert payload["upstream_api_ready_claimed"] is False
    assert payload["require_ready_pass_claimed"] is False
    assert payload["dns_target_selection_allowed"] is False
    assert payload["deployment_allowed"] is False
    assert set(EXPECTED_SURFACE_NOTES) == {surface["surface_id"] for surface in payload["surfaces"]}
    assert all(
        surface["public_safe_note"] == EXPECTED_SURFACE_NOTES[surface["surface_id"]]
        for surface in payload["surfaces"]
    )


def test_doc_contains_every_upstream_gate_label() -> None:
    doc_text = load_text(DEFAULT_DOC_PATH, "deployment upstream API gate rehearsal doc")

    for field_label in EXPECTED_FIELD_LABELS:
        assert field_label in doc_text
    assert "API provisioning stop rule" in doc_text
    assert "DNS publication stop rule" in doc_text


def test_witness_rejects_upstream_readiness_and_reporter_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "deployment upstream API gate rehearsal witness")
    candidate = deepcopy(payload)
    candidate["upstream_api_ready_claimed"] = True
    candidate["upstream_reporter_executed"] = True
    candidate["require_ready_pass_claimed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "deployment_upstream_api_gate_rehearsal_root_value_invalid" for finding in findings)
    assert candidate["deployment_allowed"] is False


def test_witness_rejects_external_values_dns_publication_workflow_and_deployment() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "deployment upstream API gate rehearsal witness")
    candidate = deepcopy(payload)
    candidate["target_gateway_url_value_recorded"] = True
    candidate["production_image_value_recorded"] = True
    candidate["runtime_host_value_recorded"] = True
    candidate["dns_publication_allowed"] = True
    candidate["dns_target_selection_allowed"] = True
    candidate["workflow_dispatch_allowed"] = True
    candidate["deployment_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "deployment_upstream_api_gate_rehearsal_root_value_invalid" for finding in findings)
    assert candidate["readiness_claimed"] is False


def test_witness_rejects_field_label_drift_and_surface_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "deployment upstream API gate rehearsal witness")
    candidate = deepcopy(payload)
    candidate["field_labels"] = list(reversed(candidate["field_labels"]))
    candidate["surfaces"][0]["state"] = "Ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "deployment_upstream_api_gate_rehearsal_root_value_invalid" for finding in findings)
    assert any(
        finding.rule_id == "deployment_upstream_api_gate_rehearsal_surface_inventory_invalid"
        for finding in findings
    )
    assert any(finding.rule_id == "deployment_upstream_api_gate_rehearsal_surface_state_invalid" for finding in findings)


def test_witness_rejects_forbidden_url_and_promotion_phrase() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "deployment upstream API gate rehearsal witness")
    candidate = deepcopy(payload)
    candidate["surfaces"][0]["public_safe_note"] = "target https://api.example.com upstream API is ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(
        finding.rule_id == "deployment_upstream_api_gate_rehearsal_forbidden_value_pattern"
        for finding in findings
    )
    assert any(
        finding.rule_id == "deployment_upstream_api_gate_rehearsal_forbidden_promotion_phrase"
        for finding in findings
    )


def test_doc_requires_gate_labels_and_rejects_promotion_phrase() -> None:
    doc_text = load_text(DEFAULT_DOC_PATH, "deployment upstream API gate rehearsal doc")
    candidate = doc_text.replace("runtime_witness_closure_gate_label", "runtime_witness_gate_label", 1)
    candidate = f"{candidate}\nDNS target is selected and deployment is ready.\n"

    findings = validate_doc_text(candidate)

    assert findings
    assert any(
        finding.rule_id == "foundation_deployment_upstream_api_gate_rehearsal_doc_label_missing"
        for finding in findings
    )
    assert any(
        finding.rule_id == "deployment_upstream_api_gate_rehearsal_forbidden_promotion_phrase"
        for finding in findings
    )
