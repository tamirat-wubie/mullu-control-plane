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


def test_protocol_manifest_indexes_promotion_closure_plan() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    plan_entry = entries["general-agent-promotion-closure-plan"]

    assert validate_protocol_manifest(manifest) == []
    assert plan_entry["path"] == "schemas/general_agent_promotion_closure_plan.schema.json"
    assert plan_entry["urn"] == "urn:mullusi:schema:general-agent-promotion-closure-plan:1"
    assert plan_entry["surface"] == "promotion"


def test_protocol_manifest_indexes_capability_adapter_closure_plan() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    plan_entry = entries["capability-adapter-closure-plan"]

    assert validate_protocol_manifest(manifest) == []
    assert plan_entry["path"] == "schemas/capability_adapter_closure_plan.schema.json"
    assert plan_entry["urn"] == "urn:mullusi:schema:capability-adapter-closure-plan:1"
    assert plan_entry["surface"] == "promotion"


def test_protocol_manifest_indexes_promotion_environment_bindings() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    binding_entry = entries["general-agent-promotion-environment-bindings"]

    assert validate_protocol_manifest(manifest) == []
    assert binding_entry["path"] == "schemas/general_agent_promotion_environment_bindings.schema.json"
    assert binding_entry["urn"] == "urn:mullusi:schema:general-agent-promotion-environment-bindings:1"
    assert binding_entry["surface"] == "promotion"


def test_protocol_manifest_indexes_promotion_environment_binding_receipt() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    receipt_entry = entries["general-agent-promotion-environment-binding-receipt"]

    assert validate_protocol_manifest(manifest) == []
    assert receipt_entry["path"] == "schemas/general_agent_promotion_environment_binding_receipt.schema.json"
    assert receipt_entry["urn"] == "urn:mullusi:schema:general-agent-promotion-environment-binding-receipt:1"
    assert receipt_entry["surface"] == "promotion"


def test_protocol_manifest_indexes_promotion_handoff_packet() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    packet_entry = entries["general-agent-promotion-handoff-packet"]

    assert validate_protocol_manifest(manifest) == []
    assert packet_entry["path"] == "schemas/general_agent_promotion_handoff_packet.schema.json"
    assert packet_entry["urn"] == "urn:mullusi:schema:general-agent-promotion-handoff-packet:1"
    assert packet_entry["surface"] == "promotion"


def test_protocol_manifest_indexes_terminal_closure_certificate() -> None:
    manifest = load_manifest()
    entries = {entry["schema_id"]: entry for entry in manifest["schemas"]}
    closure_entry = entries["terminal-closure-certificate"]

    assert validate_protocol_manifest(manifest) == []
    assert closure_entry["path"] == "schemas/terminal_closure_certificate.schema.json"
    assert closure_entry["urn"] == "urn:mullusi:schema:terminal-closure-certificate:1"
    assert closure_entry["surface"] == "closure"


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


def test_protocol_manifest_rejects_missing_promotion_closure_plan_entry() -> None:
    manifest = load_manifest()
    manifest["schemas"] = [
        entry
        for entry in manifest["schemas"]
        if entry["schema_id"] != "general-agent-promotion-closure-plan"
    ]

    errors = validate_protocol_manifest(manifest)

    assert len(errors) == 1
    assert "manifest missing public schemas" in errors[0]
    assert "general_agent_promotion_closure_plan.schema.json" in errors[0]
    assert "schemas/" in errors[0]


def test_protocol_manifest_rejects_missing_capability_adapter_closure_plan_entry() -> None:
    manifest = load_manifest()
    manifest["schemas"] = [
        entry
        for entry in manifest["schemas"]
        if entry["schema_id"] != "capability-adapter-closure-plan"
    ]

    errors = validate_protocol_manifest(manifest)

    assert len(errors) == 1
    assert "manifest missing public schemas" in errors[0]
    assert "capability_adapter_closure_plan.schema.json" in errors[0]
    assert "schemas/" in errors[0]


def test_protocol_manifest_rejects_missing_promotion_environment_bindings_entry() -> None:
    manifest = load_manifest()
    manifest["schemas"] = [
        entry
        for entry in manifest["schemas"]
        if entry["schema_id"] != "general-agent-promotion-environment-bindings"
    ]

    errors = validate_protocol_manifest(manifest)

    assert len(errors) == 1
    assert "manifest missing public schemas" in errors[0]
    assert "general_agent_promotion_environment_bindings.schema.json" in errors[0]
    assert "schemas/" in errors[0]


def test_protocol_manifest_rejects_missing_promotion_environment_binding_receipt_entry() -> None:
    manifest = load_manifest()
    manifest["schemas"] = [
        entry
        for entry in manifest["schemas"]
        if entry["schema_id"] != "general-agent-promotion-environment-binding-receipt"
    ]

    errors = validate_protocol_manifest(manifest)

    assert len(errors) == 1
    assert "manifest missing public schemas" in errors[0]
    assert "general_agent_promotion_environment_binding_receipt.schema.json" in errors[0]
    assert "schemas/" in errors[0]


def test_protocol_manifest_rejects_missing_promotion_handoff_packet_entry() -> None:
    manifest = load_manifest()
    manifest["schemas"] = [
        entry
        for entry in manifest["schemas"]
        if entry["schema_id"] != "general-agent-promotion-handoff-packet"
    ]

    errors = validate_protocol_manifest(manifest)

    assert len(errors) == 1
    assert "manifest missing public schemas" in errors[0]
    assert "general_agent_promotion_handoff_packet.schema.json" in errors[0]
    assert "schemas/" in errors[0]


def test_protocol_manifest_rejects_missing_terminal_closure_certificate_entry() -> None:
    manifest = load_manifest()
    manifest["schemas"] = [
        entry
        for entry in manifest["schemas"]
        if entry["schema_id"] != "terminal-closure-certificate"
    ]

    errors = validate_protocol_manifest(manifest)

    assert len(errors) == 1
    assert "manifest missing public schemas" in errors[0]
    assert "terminal_closure_certificate.schema.json" in errors[0]
    assert "schemas/" in errors[0]
