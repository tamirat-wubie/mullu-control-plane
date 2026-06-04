"""Tests for the Foundation Mode evidence-ledger boundary validator.

Purpose: prove evidence-ledger preparation stays local and does not authorize
evidence-promotion, terminal-closure, readiness, legal-clearance,
patent-protection, customer-readiness, paid-launch, secret-evidence,
external-publication, or deployment claims.
Governance scope: Foundation Mode, local evidence index, witness references,
validator references, test references, receipt references, source-control
packet references, private-value exclusion, and claim-promotion blocking.
Dependencies: scripts.validate_foundation_evidence_ledger_boundary.
Invariants: evidence-ledger entries remain AwaitingEvidence and reject
promotion or private-value drift.
"""

from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_foundation_evidence_ledger_boundary import (  # noqa: E402
    DEFAULT_INDEX_PATH,
    DEFAULT_PACKET_PATH,
    EXPECTED_ENTRIES,
    EXPECTED_INDEX_ENTRIES,
    EXPECTED_INDEX_ID,
    EXPECTED_WITNESS_ID,
    load_json_object,
    validate_foundation_evidence_ledger_boundary,
    validate_index_packet,
    validate_packet,
)


def test_foundation_evidence_ledger_boundary_artifacts_pass() -> None:
    assert validate_foundation_evidence_ledger_boundary() == []


def test_evidence_ledger_witness_has_expected_identity_and_blockers() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "evidence-ledger witness")

    assert payload["witness_id"] == EXPECTED_WITNESS_ID
    assert tuple(
        (entry["entry_id"], entry["entry_type"], entry["state"])
        for entry in payload["evidence_ledger_entries"]
    ) == EXPECTED_ENTRIES
    assert payload["evidence_promotion_allowed"] is False
    assert payload["terminal_closure_claimed"] is False
    assert payload["readiness_claimed"] is False
    assert payload["legal_clearance_claimed"] is False
    assert payload["patent_protection_claimed"] is False
    assert payload["customer_readiness_claimed"] is False
    assert payload["secret_evidence_recorded"] is False
    assert payload["deployment_allowed"] is False


def test_evidence_index_has_expected_identity_and_public_paths() -> None:
    payload = load_json_object(DEFAULT_INDEX_PATH, "evidence index")

    assert payload["index_id"] == EXPECTED_INDEX_ID
    assert tuple(
        (entry["entry_id"], entry["entry_type"], entry["artifact_ref"], entry["state"])
        for entry in payload["evidence_index_entries"]
    ) == EXPECTED_INDEX_ENTRIES
    assert payload["evidence_promotion_allowed"] is False
    assert payload["terminal_closure_claimed"] is False
    assert payload["readiness_claimed"] is False
    assert payload["deployment_allowed"] is False


def test_witness_rejects_evidence_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "evidence-ledger witness")
    candidate = deepcopy(payload)
    candidate["evidence_promotion_allowed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "evidence_ledger_root_value_invalid" for finding in findings)


def test_witness_rejects_terminal_closure_claim() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "evidence-ledger witness")
    candidate = deepcopy(payload)
    candidate["terminal_closure_claimed"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "evidence_ledger_root_value_invalid" for finding in findings)


def test_witness_rejects_secret_evidence_recording() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "evidence-ledger witness")
    candidate = deepcopy(payload)
    candidate["secret_evidence_recorded"] = True

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "evidence_ledger_root_value_invalid" for finding in findings)


def test_witness_rejects_entry_state_promotion() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "evidence-ledger witness")
    candidate = deepcopy(payload)
    candidate["evidence_ledger_entries"][0]["state"] = "Ready"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "evidence_ledger_entry_inventory_invalid" for finding in findings)
    assert any(finding.rule_id == "evidence_ledger_entry_state_invalid" for finding in findings)


def test_witness_rejects_provider_value() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "evidence-ledger witness")
    candidate = deepcopy(payload)
    candidate["evidence_ledger_entries"][0]["public_safe_note"] = "provider id=value"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "evidence_ledger_forbidden_private_value_pattern" for finding in findings)


def test_witness_rejects_evidence_promotion_phrase() -> None:
    payload = load_json_object(DEFAULT_PACKET_PATH, "evidence-ledger witness")
    candidate = deepcopy(payload)
    candidate["next_action"] = "evidence is promoted and terminal closure complete"

    findings = validate_packet(candidate)

    assert findings
    assert any(finding.rule_id == "evidence_ledger_forbidden_promotion_phrase" for finding in findings)


def test_index_rejects_entry_state_promotion() -> None:
    payload = load_json_object(DEFAULT_INDEX_PATH, "evidence index")
    candidate = deepcopy(payload)
    candidate["evidence_index_entries"][0]["state"] = "Ready"

    findings = validate_index_packet(candidate)

    assert findings
    assert any(finding.rule_id == "evidence_index_entry_inventory_invalid" for finding in findings)
    assert any(finding.rule_id == "evidence_index_entry_state_invalid" for finding in findings)


def test_index_rejects_private_path_value() -> None:
    payload = load_json_object(DEFAULT_INDEX_PATH, "evidence index")
    candidate = deepcopy(payload)
    candidate["evidence_index_entries"][0]["artifact_ref"] = "C:/Users/example/private-evidence.json"

    findings = validate_index_packet(candidate)

    assert findings
    assert any(
        finding.rule_id
        in {
            "evidence_index_entry_artifact_invalid",
            "evidence_ledger_forbidden_private_value_pattern",
        }
        for finding in findings
    )


def test_index_rejects_duplicate_artifact_refs() -> None:
    payload = load_json_object(DEFAULT_INDEX_PATH, "evidence index")
    candidate = deepcopy(payload)
    candidate["evidence_index_entries"][1]["artifact_ref"] = candidate["evidence_index_entries"][0]["artifact_ref"]

    findings = validate_index_packet(candidate)

    assert findings
    assert any(finding.rule_id == "evidence_index_entry_inventory_invalid" for finding in findings)
    assert any(finding.rule_id == "evidence_index_entry_artifact_duplicate" for finding in findings)
