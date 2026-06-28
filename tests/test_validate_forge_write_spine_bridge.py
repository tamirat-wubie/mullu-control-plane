"""Tests for Forge write-spine bridge validation.

Purpose: prove the Forge dev3 bridge remains reference-only, ordered, and
blocked from production state-changing authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_forge_write_spine_bridge and the bridge
schema/example pair.
Invariants: commit follows attestation, certificate fields remain complete,
service credentials remain development-bound, and production state writes stay
blocked.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_forge_write_spine_bridge import (
    DEFAULT_BRIDGE,
    DEFAULT_OUTPUT,
    validate_forge_write_spine_bridge,
    write_forge_write_spine_bridge_validation,
)


def _default_payload() -> dict[str, object]:
    return json.loads(DEFAULT_BRIDGE.read_text(encoding="utf-8"))


def _write_payload(tmp_path: Path, payload: dict[str, object]) -> Path:
    bridge_path = tmp_path / "forge_write_spine_bridge.json"
    bridge_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return bridge_path


def test_forge_write_spine_bridge_validates_and_writes_report(tmp_path: Path) -> None:
    validation = validate_forge_write_spine_bridge()
    output_path = tmp_path / "forge-write-spine-bridge-validation.json"

    written_path = write_forge_write_spine_bridge_validation(validation, output_path)
    written_payload = json.loads(written_path.read_text(encoding="utf-8"))

    assert validation.ok is True
    assert validation.stage_count == 7
    assert validation.invariant_count == 10
    assert validation.production_state_changing == "NO_GO"
    assert written_payload["errors"] == []
    assert DEFAULT_OUTPUT.name == "forge_write_spine_bridge_validation.json"
    payload = _default_payload()
    assert payload["application_mode"] == "reference_contract_only"
    assert payload["state_write_runtime_registered"] is False
    assert payload["service_boundary"]["production_authorized"] is False  # type: ignore[index]


def test_forge_write_spine_bridge_rejects_production_overclaim(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["external_effects_allowed"] = True
    payload["state_write_runtime_registered"] = True
    deployment = payload["deployment_boundary"]
    assert isinstance(deployment, dict)
    deployment["production_state_changing"] = "GO"

    validation = validate_forge_write_spine_bridge(bridge_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "external_effects_allowed must remain false" in serialized_errors
    assert "state_write_runtime_registered must remain false" in serialized_errors
    assert "production_state_changing" in serialized_errors


def test_forge_write_spine_bridge_rejects_stage_reorder(tmp_path: Path) -> None:
    payload = _default_payload()
    stages = payload["write_spine"]
    assert isinstance(stages, list)
    stages[4], stages[5] = stages[5], stages[4]

    validation = validate_forge_write_spine_bridge(bridge_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "write_spine stage order must match the canonical Forge bridge" in serialized_errors
    assert "order fields must be contiguous" in serialized_errors
    assert "fenced commit must occur after lineage authorization attestation" in serialized_errors


def test_forge_write_spine_bridge_rejects_certificate_field_drift(tmp_path: Path) -> None:
    payload = _default_payload()
    certificate = payload["certificate_contract"]
    assert isinstance(certificate, dict)
    required_fields = certificate["required_fields"]
    assert isinstance(required_fields, list)
    required_fields.remove("nonce")

    validation = validate_forge_write_spine_bridge(bridge_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "certificate_contract.required_fields must preserve canonical field order" in serialized_errors
    assert "certificate_contract must bind nonce and signature" in serialized_errors


def test_forge_write_spine_bridge_rejects_service_boundary_overclaim(tmp_path: Path) -> None:
    payload = _default_payload()
    service = payload["service_boundary"]
    assert isinstance(service, dict)
    service["transport_confidentiality"] = True
    service["production_authorized"] = True
    service["persistent_nonce_replay_guard"] = False

    validation = validate_forge_write_spine_bridge(bridge_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "transport_confidentiality must remain false" in serialized_errors
    assert "production_authorized must remain false" in serialized_errors
    assert "persistent_nonce_replay_guard must remain true" in serialized_errors


def test_forge_write_spine_bridge_rejects_workspace_mapping_drift(tmp_path: Path) -> None:
    payload = _default_payload()
    mappings = payload["workspace_mapping"]
    assert isinstance(mappings, list)
    mappings.pop()
    schema_mapping = next(
        item
        for item in mappings
        if isinstance(item, dict) and item.get("workspace_surface") == "schemas/forge_write_spine_bridge.schema.json"
    )
    schema_mapping["status"] = "mapped"

    validation = validate_forge_write_spine_bridge(bridge_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "workspace_mapping missing docs/FOUNDATION_MODE.md" in serialized_errors
    assert "bridge schema mapping must remain reference_only" in serialized_errors


def test_forge_write_spine_bridge_rejects_invariant_order_drift(tmp_path: Path) -> None:
    payload = _default_payload()
    invariants = payload["required_invariants"]
    assert isinstance(invariants, list)
    invariants.reverse()

    validation = validate_forge_write_spine_bridge(bridge_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "required_invariants must preserve canonical order" in serialized_errors
