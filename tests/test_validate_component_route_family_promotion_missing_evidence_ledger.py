"""Tests for Component Harness promotion missing-evidence ledgers.

Purpose: prove terminal-closure denial can feed one blocked missing-evidence
ledger while all required promotion artifacts remain absent.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_component_route_family_promotion_missing_evidence_ledger
and promotion missing-evidence ledger runtime.
Invariants: missing-evidence ledger records are not witnesses, evidence,
terminal certificates, terminal closure, promotion approval, or authority
grants.
"""

from __future__ import annotations

import json
from pathlib import Path

from mcoi_runtime.app.component_route_family_promotion_missing_evidence_ledger import (
    build_component_route_family_promotion_missing_evidence_ledger,
)
from scripts.validate_component_route_family_promotion_missing_evidence_ledger import (
    DEFAULT_EXAMPLE,
    DEFAULT_OUTPUT,
    validate_component_route_family_promotion_missing_evidence_ledger,
    write_component_route_family_promotion_missing_evidence_ledger_validation,
)


def _default_payload() -> dict[str, object]:
    return json.loads(DEFAULT_EXAMPLE.read_text(encoding="utf-8"))


def _write_payload(tmp_path: Path, payload: dict[str, object]) -> Path:
    example_path = tmp_path / "component_route_family_promotion_missing_evidence_ledger.json"
    example_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return example_path


def _records(payload: dict[str, object]) -> list[dict[str, object]]:
    records = payload["missing_evidence_records"]
    assert isinstance(records, list)
    assert len(records) == 6
    assert all(isinstance(record, dict) for record in records)
    return records


def test_component_route_family_promotion_missing_evidence_ledger_schema_valid_and_write(
    tmp_path: Path,
) -> None:
    validation = validate_component_route_family_promotion_missing_evidence_ledger()
    output_path = tmp_path / "component-route-family-promotion-missing-evidence-ledger-validation.json"

    written_path = write_component_route_family_promotion_missing_evidence_ledger_validation(
        validation,
        output_path,
    )
    written_payload = json.loads(written_path.read_text(encoding="utf-8"))

    assert validation.ok is True
    assert validation.target_surface_id == "governed_connector_framework"
    assert validation.target_component_id == "gmail_account_binding_gate"
    assert validation.target_product_bundle_id == "personal_assistant_v0"
    assert validation.decision == "blocked"
    assert validation.missing_evidence_record_count == 6
    assert validation.present_evidence_count == 0
    assert validation.unknown_proof_state_count == 6
    assert validation.witness_emission_count == 0
    assert written_payload["errors"] == []
    assert DEFAULT_OUTPUT.name == "component_route_family_promotion_missing_evidence_ledger_validation.json"


def test_component_route_family_promotion_missing_evidence_ledger_match_runtime_projection() -> None:
    example = _default_payload()
    projection = build_component_route_family_promotion_missing_evidence_ledger()
    records = _records(example)

    assert example == projection
    assert example["evidence_status"] == "missing_required_witnesses"
    assert example["promotion_decision"] == "blocked_missing_required_evidence"
    assert example["evidence_ledger_issued"] is True
    assert example["missing_evidence_ledger_is_not_evidence"] is True
    assert example["missing_evidence_ledger_is_not_witness"] is True
    assert example["terminal_certificate_minted"] is False
    assert example["terminal_closure_claimed"] is False
    assert example["promotion_approved"] is False
    assert example["summary"]["missing_evidence_record_count"] == 6
    assert example["summary"]["present_evidence_count"] == 0
    assert example["summary"]["unknown_proof_state_count"] == 6
    assert example["summary"]["authority_fuse_blocking_count"] == 6
    assert example["authority_fuse_refs"] == ["component_authority_fuse.gmail_account_binding_gate.foundation.v1"]
    assert example["authority_fuse_blocking_refs"] == example["authority_fuse_refs"]
    assert records[0]["artifact_id"] == "selected_component_bound_router_inventory_delta"
    assert records[0]["authority_fuse_blocks_promotion"] is True
    assert records[0]["authority_fuse_refs"] == example["authority_fuse_refs"]
    assert records[0]["authority_fuse_blocking_refs"] == example["authority_fuse_refs"]
    assert records[-1]["artifact_id"] == "terminal_closure_certificate"


def test_component_route_family_promotion_missing_evidence_ledger_reject_evidence_overclaim(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    record = _records(payload)[0]
    payload["decision"] = "approved"
    payload["outcome"] = "SolvedVerified"
    payload["ready_for_promotion"] = True
    payload["promotion_approved"] = True
    payload["accepted_evidence_refs"] = ["evidence://router-delta"]
    record["evidence_state"] = "present"
    record["proof_state"] = "Pass"
    record["evidence_present"] = True
    record["blocks_promotion"] = False
    record["accepted_evidence_refs"] = ["evidence://router-delta"]

    validation = validate_component_route_family_promotion_missing_evidence_ledger(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "decision must be blocked" in serialized_errors
    assert "outcome must be AwaitingEvidence" in serialized_errors
    assert "ready_for_promotion must be false" in serialized_errors
    assert "promotion_approved must be false" in serialized_errors
    assert "accepted_evidence_refs must remain empty" in serialized_errors
    assert "missing record evidence_state must be missing" in serialized_errors
    assert "missing record proof_state must be Unknown" in serialized_errors
    assert "missing record evidence_present must be false" in serialized_errors
    assert "missing record blocks_promotion must be true" in serialized_errors


def test_component_route_family_promotion_missing_evidence_ledger_reject_missing_record(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    payload["missing_evidence_records"] = _records(payload)[:-1]

    validation = validate_component_route_family_promotion_missing_evidence_ledger(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "missing_evidence_records must contain six records" in serialized_errors
    assert "example does not match runtime ledger" in serialized_errors


def test_component_route_family_promotion_missing_evidence_ledger_reject_source_ref_drift(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    record = _records(payload)[0]
    payload["source_terminal_closure_decision_refs"] = []
    record["source_terminal_closure_decision_denied"] = False
    record["source_terminal_closure_decision_refs"] = []
    record["required_stage"] = "authority_upgrade"
    record["product_bundle_id"] = "other_bundle"

    validation = validate_component_route_family_promotion_missing_evidence_ledger(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "source_terminal_closure_decision_refs must contain one terminal decision" in serialized_errors
    assert "source_terminal_closure_decision_refs must match ledger source terminal ref" in serialized_errors
    assert "missing record source_terminal_closure_decision_denied must be true" in serialized_errors
    assert "missing record required_stage must match artifact_id" in serialized_errors
    assert "missing record product_bundle_id must be personal_assistant_v0" in serialized_errors


def test_component_route_family_promotion_missing_evidence_ledger_reject_authority_fuse_drift(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    record = _records(payload)[0]
    payload["authority_fuse_refs"] = []
    payload["authority_fuse_blocking_refs"] = ["component_authority_fuse.gmail_account_binding_gate.foundation.v1"]
    payload["summary"]["authority_fuse_blocking_count"] = 0
    record["authority_fuse_blocks_promotion"] = False
    record["authority_fuse_refs"] = ["component_authority_fuse.drifted.v1"]
    record["authority_fuse_blocking_refs"] = []

    validation = validate_component_route_family_promotion_missing_evidence_ledger(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "authority_fuse_refs must contain exactly one component authority-fuse ref" in serialized_errors
    assert "authority_fuse_blocking_refs must match authority_fuse_refs" in serialized_errors
    assert "missing record authority_fuse_blocks_promotion must be true" in serialized_errors
    assert "missing record authority_fuse_refs must match ledger authority_fuse_refs" in serialized_errors
    assert "summary.authority_fuse_blocking_count" in serialized_errors


def test_component_route_family_promotion_missing_evidence_ledger_reject_witness_drift(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    record = _records(payload)[0]
    payload["terminal_closure_certificate_refs"] = ["terminal-certificate://governed_connector_framework"]
    payload["authority_grant_refs"] = ["authority-grant://governed_connector_framework"]
    payload["missing_evidence_ledger_is_not_witness"] = False
    record["witness_emitted"] = True
    record["authority_granted"] = True
    record["terminal_certificate_minted"] = True
    record["record_is_not_witness"] = False
    record["witness_refs"] = ["receipt://router-delta"]
    record["authority_grant_refs"] = ["authority-grant://governed_connector_framework"]

    validation = validate_component_route_family_promotion_missing_evidence_ledger(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "terminal_closure_certificate_refs must remain empty" in serialized_errors
    assert "authority_grant_refs must remain empty" in serialized_errors
    assert "missing_evidence_ledger_is_not_witness must be true" in serialized_errors
    assert "missing record witness_emitted must be false" in serialized_errors
    assert "missing record authority_granted must be false" in serialized_errors
    assert "missing record terminal_certificate_minted must be false" in serialized_errors
    assert "missing record record_is_not_witness must be true" in serialized_errors
    assert "missing record witness_refs must remain empty" in serialized_errors
    assert "summary.witness_emission_count" in serialized_errors
