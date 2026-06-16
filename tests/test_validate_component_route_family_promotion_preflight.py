"""Tests for Component Harness route-family promotion preflight validation.

Purpose: prove blocked route-family promotion attempts fail closed with exact
missing evidence and no execution or terminal-closure authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_component_route_family_promotion_preflight and
promotion preflight runtime.
Invariants: governed connector framework remains unpromoted until route-binding,
lifecycle, authority, and product-specific evidence exists.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcoi_runtime.app.component_route_family_promotion_preflight import (
    ComponentRouteFamilyPromotionPreflightError,
    build_component_route_family_promotion_preflight,
)
from scripts.validate_component_route_family_promotion_preflight import (
    DEFAULT_EXAMPLE,
    DEFAULT_OUTPUT,
    validate_component_route_family_promotion_preflight,
    write_component_route_family_promotion_preflight_validation,
)


def _default_payload() -> dict[str, object]:
    return json.loads(DEFAULT_EXAMPLE.read_text(encoding="utf-8"))


def _write_payload(tmp_path: Path, payload: dict[str, object]) -> Path:
    example_path = tmp_path / "component_route_family_promotion_preflight.json"
    example_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return example_path


def test_component_route_family_promotion_preflight_schema_valid_and_write(
    tmp_path: Path,
) -> None:
    validation = validate_component_route_family_promotion_preflight()
    output_path = tmp_path / "component-route-family-promotion-preflight-validation.json"

    written_path = write_component_route_family_promotion_preflight_validation(validation, output_path)
    written_payload = json.loads(written_path.read_text(encoding="utf-8"))

    assert validation.ok is True
    assert validation.target_surface_id == "governed_connector_framework"
    assert validation.target_component_id == "gmail_account_binding_gate"
    assert validation.decision == "blocked"
    assert validation.failed_gate_count == 4
    assert validation.missing_evidence_count == 4
    assert written_payload["errors"] == []
    assert DEFAULT_OUTPUT.name == "component_route_family_promotion_preflight_validation.json"


def test_component_route_family_promotion_preflight_example_matches_runtime_projection() -> None:
    example = _default_payload()
    projection = build_component_route_family_promotion_preflight()
    gates = {gate["gate_id"]: gate for gate in example["gate_results"]}

    assert example == projection
    assert example["decision"] == "blocked"
    assert example["outcome"] == "GovernanceBlocked"
    assert example["can_call_connector"] is False
    assert gates["proof_binding_gate"]["proof_state"] == "Pass"
    assert gates["current_authority_envelope_gate"]["proof_state"] == "Pass"
    assert gates["authority_upgrade_gate"]["proof_state"] == "Fail"
    assert gates["product_specific_boundary_gate"]["proof_state"] == "Fail"
    assert "generic_connector_surface_not_product_specific_authority" in example["missing_evidence"]


def test_component_route_family_promotion_preflight_rejects_authority_overclaim(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    payload["decision"] = "approved"
    payload["outcome"] = "SolvedUnverified"
    payload["can_call_connector"] = True
    payload["blocked_actions"].remove("terminal_closure")

    validation = validate_component_route_family_promotion_preflight(example_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "decision must remain blocked" in serialized_errors
    assert "outcome must be GovernanceBlocked" in serialized_errors
    assert "can_call_connector" in serialized_errors
    assert "blocked_actions must include terminal_closure" in serialized_errors


def test_component_route_family_promotion_preflight_rejects_gate_drift(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    gates = {gate["gate_id"]: gate for gate in payload["gate_results"] if isinstance(gate, dict)}
    gates["lifecycle_gate"]["proof_state"] = "Pass"
    payload["missing_evidence"].remove("missing_lifecycle_transition_receipt")

    validation = validate_component_route_family_promotion_preflight(example_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "missing_evidence omits required blockers" in serialized_errors
    assert "example does not match runtime report" in serialized_errors
    assert "missing_lifecycle_transition_receipt" in serialized_errors


def test_component_route_family_promotion_preflight_rejects_selected_bound_target() -> None:
    with pytest.raises(ComponentRouteFamilyPromotionPreflightError) as exc_info:
        build_component_route_family_promotion_preflight(
            surface_id="component_harness_read_model",
            component_id="governance_core",
        )

    assert "already has selected component ownership" in str(exc_info.value)
