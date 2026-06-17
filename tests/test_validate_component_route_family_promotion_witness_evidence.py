"""Tests for Component Harness promotion witness evidence validation.

Purpose: prove blocked promotion gates have concrete denial evidence
without granting route, connector, mutation, or terminal authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_component_route_family_promotion_witness_evidence
and promotion witness evidence runtime.
Invariants: evidence records remain non-mutating, non-authoritative, and
blocking until approval witnesses replace denial witnesses.
"""

from __future__ import annotations

import json
from pathlib import Path

from mcoi_runtime.app.component_route_family_promotion_witness_evidence import (
    build_component_route_family_promotion_witness_evidence,
)
from scripts.validate_component_route_family_promotion_witness_evidence import (
    DEFAULT_EXAMPLE,
    DEFAULT_OUTPUT,
    validate_component_route_family_promotion_witness_evidence,
    write_component_route_family_promotion_witness_evidence_validation,
)


def _default_payload() -> dict[str, object]:
    return json.loads(DEFAULT_EXAMPLE.read_text(encoding="utf-8"))


def _write_payload(tmp_path: Path, payload: dict[str, object]) -> Path:
    example_path = tmp_path / "component_route_family_promotion_witness_evidence.json"
    example_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return example_path


def _witness_records(payload: dict[str, object]) -> dict[str, dict[str, object]]:
    records = payload["witness_records"]
    assert isinstance(records, list)
    return {
        str(record["gate_id"]): record
        for record in records
        if isinstance(record, dict)
    }


def test_component_route_family_promotion_witness_evidence_schema_valid_and_write(
    tmp_path: Path,
) -> None:
    validation = validate_component_route_family_promotion_witness_evidence()
    output_path = tmp_path / "component-route-family-promotion-witness-evidence-validation.json"

    written_path = write_component_route_family_promotion_witness_evidence_validation(validation, output_path)
    written_payload = json.loads(written_path.read_text(encoding="utf-8"))

    assert validation.ok is True
    assert validation.target_surface_id == "governed_connector_framework"
    assert validation.target_component_id == "gmail_account_binding_gate"
    assert validation.decision == "blocked"
    assert validation.witness_record_count == 4
    assert validation.remaining_unwitnessed_blocker_count == 0
    assert validation.approval_evidence_required_count >= 4
    assert written_payload["errors"] == []
    assert DEFAULT_OUTPUT.name == "component_route_family_promotion_witness_evidence_validation.json"


def test_component_route_family_promotion_witness_evidence_example_matches_runtime_projection() -> None:
    example = _default_payload()
    projection = build_component_route_family_promotion_witness_evidence()
    records = _witness_records(example)

    assert example == projection
    assert example["witness_evidence_is_not_execution_authority"] is True
    assert example["ready_for_promotion"] is False
    assert example["mutates_router_inventory"] is False
    assert records["route_binding_gate"]["witness_state"] == "present_denial"
    assert records["route_binding_gate"]["satisfies_requirement"] is False
    assert records["authority_upgrade_gate"]["grants_connector_authority"] is False
    assert records["lifecycle_gate"]["witness_state"] == "present_denial"
    assert records["product_specific_boundary_gate"]["witness_kind"] == "product_specific_ownership"
    assert example["remaining_missing_evidence"] == []
    assert "product_specific_ownership_decision" in example["approval_evidence_required"]


def test_component_route_family_promotion_witness_evidence_rejects_authority_overclaim(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    records = _witness_records(payload)
    payload["decision"] = "approved"
    payload["outcome"] = "SolvedUnverified"
    payload["can_call_connector"] = True
    payload["ready_for_promotion"] = True
    records["authority_upgrade_gate"]["grants_execution_authority"] = True
    payload["blocked_actions"].remove("terminal_closure")

    validation = validate_component_route_family_promotion_witness_evidence(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "decision must remain blocked" in serialized_errors
    assert "outcome must be AwaitingEvidence" in serialized_errors
    assert "can_call_connector" in serialized_errors
    assert "grants_execution_authority must be false" in serialized_errors
    assert "blocked_actions must include terminal_closure" in serialized_errors


def test_component_route_family_promotion_witness_evidence_rejects_missing_route_binding_witness(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    records = payload["witness_records"]
    assert isinstance(records, list)
    payload["witness_records"] = [
        record
        for record in records
        if isinstance(record, dict) and record.get("gate_id") != "route_binding_gate"
    ]
    payload["witnessed_evidence_keys"].remove("missing_selected_component_route_binding")

    validation = validate_component_route_family_promotion_witness_evidence(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "witness_records must cover exactly" in serialized_errors
    assert "witnessed evidence keys must cover all hard blocker denials" in serialized_errors
    assert "summary.witness_record_count" in serialized_errors


def test_component_route_family_promotion_witness_evidence_rejects_satisfied_product_ownership_drift(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    records = _witness_records(payload)
    product_record = records["product_specific_boundary_gate"]
    product_record["proof_state"] = "Pass"
    product_record["witness_state"] = "approved"
    product_record["satisfies_requirement"] = True
    product_record["blocks_promotion"] = False

    validation = validate_component_route_family_promotion_witness_evidence(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "proof_state must remain Fail" in serialized_errors
    assert "must be present_denial" in serialized_errors
    assert "must not satisfy requirement" in serialized_errors
    assert "must block promotion" in serialized_errors
    assert "summary.satisfied_requirement_count" in serialized_errors
