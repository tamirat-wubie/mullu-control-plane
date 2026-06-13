"""Purpose: verify SNet mesh receipt schema and validator behavior.
Governance scope: schema-backed SNet receipt evidence, non-terminal closure,
    raw-answer suppression, and execution-authority denial.
Dependencies: scripts.validate_snet_mesh_receipt and SNet read model contracts.
Invariants:
  - SNet receipt payloads validate against the schema.
  - Raw-answer exposure is rejected.
  - Execution authority is rejected.
"""

from __future__ import annotations

import json

from scripts import validate_snet_mesh_receipt as validator


def test_snet_mesh_receipt_contract_passes() -> None:
    errors = validator.validate_contract()
    sample_receipt = validator.build_sample_receipt()
    schema = validator._load_schema(validator.DEFAULT_SCHEMA_PATH)

    assert errors == []
    assert sample_receipt["surface"] == "read_only_snet_recursive_mesh"
    assert sample_receipt["mesh_digest"].startswith("sha256:")
    assert sample_receipt["terminal_closure_required"] is True
    assert sample_receipt["receipt_is_not_terminal_closure"] is True
    assert sample_receipt["raw_answers_exposed"] is False
    assert sample_receipt["execution_authority_granted"] is False
    assert sample_receipt["connector_authority_granted"] is False
    assert sample_receipt["route_authority_granted"] is False
    assert sample_receipt["filesystem_authority_granted"] is False
    assert validator.validate_receipt(sample_receipt, schema) == []


def test_snet_mesh_receipt_rejects_raw_answer_and_authority_mutations() -> None:
    schema = validator._load_schema(validator.DEFAULT_SCHEMA_PATH)
    raw_answer_receipt = validator.build_sample_receipt()
    authority_receipts = {
        field_name: validator.build_sample_receipt()
        for field_name in (
            "execution_authority_granted",
            "connector_authority_granted",
            "route_authority_granted",
            "filesystem_authority_granted",
        )
    }
    raw_answer_receipt["raw_answers_exposed"] = True
    for field_name, receipt in authority_receipts.items():
        receipt[field_name] = True

    raw_answer_errors = validator.validate_receipt(raw_answer_receipt, schema)
    authority_errors = {
        field_name: validator.validate_receipt(receipt, schema)
        for field_name, receipt in authority_receipts.items()
    }

    assert any("raw_answers_exposed" in error for error in raw_answer_errors)
    assert all(any(field_name in error for error in errors) for field_name, errors in authority_errors.items())
    assert raw_answer_receipt["receipt_is_not_terminal_closure"] is True
    assert all(receipt["terminal_closure_required"] is True for receipt in authority_receipts.values())


def test_snet_mesh_receipt_saved_file_validation(tmp_path) -> None:
    receipt_path = tmp_path / "snet_mesh_receipt.json"
    receipt_path.write_text(json.dumps(validator.build_sample_receipt()), encoding="utf-8")

    receipt = validator.load_json_object(receipt_path, "SNet mesh receipt")
    errors = validator.validate_receipt(receipt)

    assert errors == []
    assert receipt["receipt_id"].startswith("snet-mesh-")
    assert receipt["mesh_digest"].startswith("sha256:")
    assert receipt["evidence_refs"]


def test_snet_mesh_receipt_rejects_settlement_count_drift() -> None:
    receipt = validator.build_sample_receipt()
    schema = validator._load_schema(validator.DEFAULT_SCHEMA_PATH)
    receipt["settlement_counts"]["active"] = receipt["settlement_counts"]["active"] + 1

    errors = validator.validate_receipt(receipt, schema)

    assert any("settlement_counts total" in error for error in errors)
    assert receipt["terminal_closure_required"] is True
    assert receipt["receipt_is_not_terminal_closure"] is True


def test_snet_mesh_receipt_requires_digest_evidence_ref() -> None:
    receipt = validator.build_sample_receipt()
    schema = validator._load_schema(validator.DEFAULT_SCHEMA_PATH)
    receipt["evidence_refs"] = [ref for ref in receipt["evidence_refs"] if not ref.startswith("snet:mesh_digest:")]

    errors = validator.validate_receipt(receipt, schema)

    assert any("snet:mesh_digest:" in error for error in errors)
    assert receipt["mesh_digest"].startswith("sha256:")
    assert receipt["receipt_is_not_terminal_closure"] is True


def test_snet_mesh_receipt_rejects_identity_drift() -> None:
    schema = validator._load_schema(validator.DEFAULT_SCHEMA_PATH)
    bad_receipts = {
        "receipt_id": {**validator.build_sample_receipt(), "receipt_id": "snet-mesh-nothex"},
        "mesh_digest": {**validator.build_sample_receipt(), "mesh_digest": "sha256:nothex"},
        "surface": {**validator.build_sample_receipt(), "surface": "unsafe_surface"},
        "snet_version": {**validator.build_sample_receipt(), "snet_version": "0.0.0"},
        "semantics_hash": {**validator.build_sample_receipt(), "semantics_hash": "sha256:wrong"},
    }

    errors = {
        field_name: validator.validate_receipt(receipt, schema)
        for field_name, receipt in bad_receipts.items()
    }

    assert all(errors.values())
    assert any("receipt_id" in error for error in errors["receipt_id"])
    assert any("mesh_digest" in error for error in errors["mesh_digest"])
