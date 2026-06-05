"""Tests for the Foundation Mode gateway DNS publication rehearsal validator.

Purpose: prove issue #330 DNS publication preparation stays local and does not
authorize provider accounts, DNS zone values, record values, TTL values, DNS
mutation, proof claims, approval, readiness, external publication, or
deployment.
Governance scope: Foundation Mode, issue #330, gateway DNS publication
rehearsal, public-safe gate labels, private-value exclusion, external-action
blocking, promotion blocking, approval blocking, and deployment restraint.
Dependencies: scripts.validate_foundation_gateway_dns_publication_rehearsal_boundary.
Invariants: rehearsal surfaces remain AwaitingEvidence and reject provider
drift, DNS value drift, mutation drift, approval drift, publication drift, and
deployment drift.
"""

from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_foundation_gateway_dns_publication_rehearsal_boundary import (  # noqa: E402
    DEFAULT_DOC_PATH,
    DEFAULT_PACKET_PATH,
    EXPECTED_DOC_SURFACE_LABELS,
    EXPECTED_NEXT_ACTION,
    EXPECTED_QUESTION_LABELS,
    EXPECTED_SURFACE_NOTES,
    EXPECTED_SURFACES,
    EXPECTED_WITNESS_ID,
    load_json_object,
    load_text,
    validate_doc_text,
    validate_foundation_gateway_dns_publication_rehearsal_boundary,
    validate_packet,
)


def test_foundation_gateway_dns_publication_rehearsal_artifacts_pass() -> None:
    assert validate_foundation_gateway_dns_publication_rehearsal_boundary() == []


def test_gateway_dns_publication_rehearsal_witness_has_expected_identity_and_surfaces() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "gateway DNS publication rehearsal witness")

    assert payload["witness_id"] == EXPECTED_WITNESS_ID
    assert tuple(
        (surface["surface_id"], surface["surface_type"], surface["state"])
        for surface in payload["surfaces"]
    ) == EXPECTED_SURFACES
    assert tuple(payload["question_labels"]) == EXPECTED_QUESTION_LABELS
    assert payload["next_action"] == EXPECTED_NEXT_ACTION
    assert payload["dns_provider_account_recorded"] is False
    assert payload["dns_zone_value_recorded"] is False
    assert payload["dns_record_value_recorded"] is False
    assert payload["dns_mutation_allowed"] is False
    assert payload["deployment_allowed"] is False
    assert set(EXPECTED_SURFACE_NOTES) == {surface["surface_id"] for surface in payload["surfaces"]}
    assert all(
        surface["public_safe_note"] == EXPECTED_SURFACE_NOTES[surface["surface_id"]]
        for surface in payload["surfaces"]
    )


def test_doc_contains_gate_labels_and_surface_labels() -> None:
    doc_text = load_text(DEFAULT_DOC_PATH, "gateway DNS publication rehearsal doc")

    for question_label in EXPECTED_QUESTION_LABELS:
        assert question_label in doc_text
    for surface_label in EXPECTED_DOC_SURFACE_LABELS:
        assert surface_label in doc_text


def test_witness_rejects_provider_zone_record_ttl_and_mutation_claims() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "gateway DNS publication rehearsal witness")
    candidate = deepcopy(payload)
    candidate["dns_provider_account_recorded"] = True
    candidate["dns_zone_value_recorded"] = True
    candidate["dns_record_name_recorded"] = True
    candidate["dns_record_type_value_recorded"] = True
    candidate["dns_record_value_recorded"] = True
    candidate["ttl_value_recorded"] = True
    candidate["dns_mutation_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "gateway_dns_publication_rehearsal_root_value_invalid" for finding in findings)


def test_witness_rejects_proof_approval_readiness_and_deployment_claims() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "gateway DNS publication rehearsal witness")
    candidate = deepcopy(payload)
    candidate["dns_propagation_claimed"] = True
    candidate["dns_rollback_claimed"] = True
    candidate["dns_resolution_claimed"] = True
    candidate["endpoint_reachability_claimed"] = True
    candidate["operator_approval_claimed"] = True
    candidate["readiness_claimed"] = True
    candidate["external_publication_allowed"] = True
    candidate["deployment_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "gateway_dns_publication_rehearsal_root_value_invalid" for finding in findings)


def test_witness_rejects_label_surface_and_note_drift() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "gateway DNS publication rehearsal witness")
    candidate = deepcopy(payload)
    candidate["question_labels"] = list(reversed(candidate["question_labels"]))
    candidate["surfaces"][0]["state"] = "Ready"
    candidate["surfaces"][0]["public_safe_note"] = "DNS publication can continue."

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "gateway_dns_publication_rehearsal_root_value_invalid" for finding in findings)
    assert any(finding.rule_id == "gateway_dns_publication_rehearsal_surface_state_invalid" for finding in findings)
    assert any(finding.rule_id == "gateway_dns_publication_rehearsal_surface_note_invalid" for finding in findings)


def test_witness_rejects_live_url_host_ip_or_assignment_shape() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "gateway DNS publication rehearsal witness")
    candidate = deepcopy(payload)
    candidate["surfaces"][0]["public_safe_note"] = "dns_record_value=192.0.2.10 gateway.example.com"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "gateway_dns_publication_rehearsal_forbidden_value_pattern" for finding in findings)


def test_witness_rejects_dns_publication_or_deployment_phrase() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "gateway DNS publication rehearsal witness")
    candidate = deepcopy(payload)
    candidate["next_action"] = "dns record is published and deployment is ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "gateway_dns_publication_rehearsal_forbidden_promotion_phrase" for finding in findings)


def test_doc_rejects_live_value_and_promotion_drift() -> None:
    doc_text = load_text(DEFAULT_DOC_PATH, "gateway DNS publication rehearsal doc")
    candidate = f"{doc_text}\ndns_record_value=https://gateway.example.com\nDNS record is published.\n"

    findings = validate_doc_text(candidate)

    assert findings
    assert any(finding.rule_id == "gateway_dns_publication_rehearsal_forbidden_value_pattern" for finding in findings)
    assert any(finding.rule_id == "gateway_dns_publication_rehearsal_forbidden_promotion_phrase" for finding in findings)
