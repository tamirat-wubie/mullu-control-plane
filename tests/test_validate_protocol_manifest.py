"""Tests for the public governance protocol manifest.

Purpose: prove deployment orchestration receipts and effect assurance records
are indexed as public handoff contracts.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.validate_protocol_manifest and schema manifest JSON.
Invariants:
  - Every public top-level schema is listed in the protocol manifest.
  - Deployment orchestration receipts have a stable schema id and URN.
  - Effect assurance has a stable schema id and URN.
  - Missing public handoff schema entries fail closed.
"""

from __future__ import annotations

from scripts.validate_protocol_manifest import load_manifest, validate_protocol_manifest


def test_protocol_manifest_indexes_deployment_orchestration_receipt() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    receipt_entry = entries["deployment-orchestration-receipt"]

    assert validate_protocol_manifest(manifest) == []
    assert receipt_entry["path"] == "schemas/deployment_orchestration_receipt.schema.json"
    assert receipt_entry["urn"] == "urn:mullusi:schema:deployment-orchestration-receipt:1"
    assert receipt_entry["surface"] == "deployment"


def test_protocol_manifest_indexes_effect_assurance_record() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    effect_entry = entries["effect-assurance"]

    assert validate_protocol_manifest(manifest) == []
    assert effect_entry["path"] == "schemas/effect_assurance.schema.json"
    assert effect_entry["urn"] == "urn:mullusi:schema:effect-assurance:1"
    assert effect_entry["surface"] == "effect_assurance"


def test_protocol_manifest_rejects_missing_deployment_receipt_entry() -> None:
    manifest = load_manifest()
    manifest["schemas"] = [
        entry
        for entry in manifest["schemas"]
        if entry["schema_id"] != "deployment-orchestration-receipt"
    ]

    errors = validate_protocol_manifest(manifest)

    assert len(errors) == 1
    assert "manifest missing public schemas" in errors[0]
    assert "deployment_orchestration_receipt.schema.json" in errors[0]
    assert "schemas/" in errors[0]


def test_protocol_manifest_rejects_missing_effect_assurance_entry() -> None:
    manifest = load_manifest()
    manifest["schemas"] = [
        entry
        for entry in manifest["schemas"]
        if entry["schema_id"] != "effect-assurance"
    ]

    errors = validate_protocol_manifest(manifest)

    assert len(errors) == 1
    assert "manifest missing public schemas" in errors[0]
    assert "effect_assurance.schema.json" in errors[0]
    assert "schemas/" in errors[0]
