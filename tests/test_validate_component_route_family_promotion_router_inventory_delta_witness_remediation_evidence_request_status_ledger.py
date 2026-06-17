"""Tests for router-inventory delta witness remediation evidence request status ledgers.

Purpose: prove remediation evidence request status ledgers remain read-only and
do not submit, accept, reject, or satisfy evidence; authorize minting; mint
witnesses; apply deltas; mutate router inventory; or grant authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: router-inventory delta witness remediation evidence request
status ledger validator and runtime projection.
Invariants: status ledgers are not evidence submissions, acceptances,
rejections, authorizations, witnesses, deltas, authority grants, approvals, or
closure claims.
"""

from __future__ import annotations

import json
from pathlib import Path

from mcoi_runtime.app.component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger import (
    build_component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger,
)
from scripts.validate_component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger import (
    DEFAULT_EXAMPLE,
    DEFAULT_OUTPUT,
    validate_component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger,
    write_component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger_validation,
)


def _default_payload() -> dict[str, object]:
    return json.loads(DEFAULT_EXAMPLE.read_text(encoding="utf-8"))


def _write_payload(tmp_path: Path, payload: dict[str, object]) -> Path:
    example_path = (
        tmp_path
        / "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger.json"
    )
    example_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return example_path


def _records(payload: dict[str, object]) -> list[dict[str, object]]:
    records = payload["status_records"]
    assert isinstance(records, list)
    assert len(records) == 6
    assert all(isinstance(record, dict) for record in records)
    return records


def test_component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger_schema_valid_and_write(
    tmp_path: Path,
) -> None:
    validation = (
        validate_component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger()
    )
    output_path = tmp_path / "router-inventory-delta-witness-remediation-evidence-request-status-ledger-validation.json"

    written_path = (
        write_component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger_validation(
            validation,
            output_path,
        )
    )
    written_payload = json.loads(written_path.read_text(encoding="utf-8"))

    assert validation.ok is True
    assert validation.target_surface_id == "governed_connector_framework"
    assert validation.target_component_id == "gmail_account_binding_gate"
    assert validation.target_product_bundle_id == "personal_assistant_v0"
    assert validation.decision == "blocked"
    assert validation.status_record_count == 6
    assert validation.awaiting_operator_evidence_count == 6
    assert validation.submitted_evidence_count == 0
    assert validation.accepted_evidence_count == 0
    assert validation.rejected_evidence_count == 0
    assert validation.witness_mint_count == 0
    assert written_payload["errors"] == []
    assert DEFAULT_OUTPUT.name == (
        "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger_validation.json"
    )


def test_component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger_match_runtime_projection() -> None:
    example = _default_payload()
    projection = (
        build_component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger()
    )
    records = _records(example)

    assert example == projection
    assert example["ledger_state"] == "request_status_only"
    assert example["status_ledger_is_not_submission"] is True
    assert example["status_ledger_is_not_acceptance"] is True
    assert example["status_ledger_is_not_rejection"] is True
    assert example["evidence_submitted"] is False
    assert example["evidence_accepted"] is False
    assert example["evidence_rejected"] is False
    assert example["witness_minted"] is False
    assert example["router_inventory_mutated"] is False
    assert example["summary"]["status_record_count"] == 6
    assert example["summary"]["awaiting_operator_evidence_count"] == 6
    assert records[0]["status"] == "awaiting_operator_evidence"


def test_component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger_reject_submission_overclaim(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    record = _records(payload)[0]
    payload["evidence_submitted"] = True
    payload["submitted_evidence_refs"] = ["evidence://submitted"]
    record["evidence_submitted"] = True
    record["submitted_evidence_refs"] = ["evidence://submitted"]

    validation = (
        validate_component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger(
            example_path=_write_payload(tmp_path, payload)
        )
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "evidence_submitted must be false" in serialized_errors
    assert "submitted_evidence_refs must remain empty" in serialized_errors
    assert "status record evidence_submitted must be false" in serialized_errors
    assert "status record submitted_evidence_refs must remain empty" in serialized_errors
    assert "summary.submitted_evidence_count" in serialized_errors


def test_component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger_reject_acceptance_and_rejection_overclaim(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    record = _records(payload)[0]
    payload["evidence_accepted"] = True
    payload["evidence_rejected"] = True
    payload["requirements_satisfied"] = True
    payload["accepted_evidence_refs"] = ["evidence://accepted"]
    payload["rejected_evidence_refs"] = ["evidence://rejected"]
    record["evidence_accepted"] = True
    record["evidence_rejected"] = True
    record["requirement_satisfied"] = True
    record["accepted_evidence_refs"] = ["evidence://accepted"]
    record["rejected_evidence_refs"] = ["evidence://rejected"]

    validation = (
        validate_component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger(
            example_path=_write_payload(tmp_path, payload)
        )
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "evidence_accepted must be false" in serialized_errors
    assert "evidence_rejected must be false" in serialized_errors
    assert "requirements_satisfied must be false" in serialized_errors
    assert "accepted_evidence_refs must remain empty" in serialized_errors
    assert "rejected_evidence_refs must remain empty" in serialized_errors
    assert "status record evidence_accepted must be false" in serialized_errors
    assert "status record evidence_rejected must be false" in serialized_errors
    assert "status record requirement_satisfied must be false" in serialized_errors


def test_component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger_reject_missing_status_record(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    payload["status_records"] = _records(payload)[:-1]

    validation = (
        validate_component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger(
            example_path=_write_payload(tmp_path, payload)
        )
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "status_records must contain six records" in serialized_errors
    assert "example does not match runtime report" in serialized_errors


def test_component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger_reject_mutation_drift(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    record = _records(payload)[0]
    payload["router_inventory_mutated"] = True
    payload["delta_applied"] = True
    payload["authority_granted"] = True
    payload["router_inventory_delta_refs"] = ["delta://router"]
    record["router_inventory_mutated"] = True
    record["delta_applied"] = True
    record["authority_granted"] = True
    record["router_inventory_delta_refs"] = ["delta://router"]
    record["authority_grant_refs"] = ["grant://authority"]

    validation = (
        validate_component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger(
            example_path=_write_payload(tmp_path, payload)
        )
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "router_inventory_mutated must be false" in serialized_errors
    assert "delta_applied must be false" in serialized_errors
    assert "authority_granted must be false" in serialized_errors
    assert "router_inventory_delta_refs must remain empty" in serialized_errors
    assert "status record router_inventory_mutated must be false" in serialized_errors
    assert "status record delta_applied must be false" in serialized_errors
    assert "status record authority_granted must be false" in serialized_errors
    assert "status record router_inventory_delta_refs must remain empty" in serialized_errors
    assert "summary.router_inventory_mutation_count" in serialized_errors
