"""Tests for Component Harness promotion witness requirements validation.

Purpose: prove blocked route-family promotion attempts have explicit witness
requirements before any router ownership state can change.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_component_route_family_promotion_witness_requirements
and promotion witness requirements runtime.
Invariants: witness requirements remain non-executing, missing hard witnesses
block promotion, and current authority evidence is not an upgrade witness.
"""

from __future__ import annotations

import json
from pathlib import Path

from mcoi_runtime.app.component_route_family_promotion_witness_requirements import (
    build_component_route_family_promotion_witness_requirements,
)
from scripts.validate_component_route_family_promotion_witness_requirements import (
    DEFAULT_EXAMPLE,
    DEFAULT_OUTPUT,
    validate_component_route_family_promotion_witness_requirements,
    write_component_route_family_promotion_witness_requirements_validation,
)


def _default_payload() -> dict[str, object]:
    return json.loads(DEFAULT_EXAMPLE.read_text(encoding="utf-8"))


def _write_payload(tmp_path: Path, payload: dict[str, object]) -> Path:
    example_path = tmp_path / "component_route_family_promotion_witness_requirements.json"
    example_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return example_path


def _requirements(payload: dict[str, object]) -> dict[str, dict[str, object]]:
    requirements = payload["promotion_witness_requirements"]
    assert isinstance(requirements, list)
    return {
        str(requirement["gate_id"]): requirement
        for requirement in requirements
        if isinstance(requirement, dict)
    }


def test_component_route_family_promotion_witness_requirements_schema_valid_and_write(
    tmp_path: Path,
) -> None:
    validation = validate_component_route_family_promotion_witness_requirements()
    output_path = tmp_path / "component-route-family-promotion-witness-requirements-validation.json"

    written_path = write_component_route_family_promotion_witness_requirements_validation(validation, output_path)
    written_payload = json.loads(written_path.read_text(encoding="utf-8"))

    assert validation.ok is True
    assert validation.target_surface_id == "governed_connector_framework"
    assert validation.target_component_id == "gmail_account_binding_gate"
    assert validation.decision == "blocked"
    assert validation.witness_requirement_count == 7
    assert validation.missing_witness_count == 4
    assert written_payload["errors"] == []
    assert DEFAULT_OUTPUT.name == "component_route_family_promotion_witness_requirements_validation.json"


def test_component_route_family_promotion_witness_requirements_example_matches_runtime_projection() -> None:
    example = _default_payload()
    projection = build_component_route_family_promotion_witness_requirements()
    requirements = _requirements(example)

    assert example == projection
    assert example["requirements_are_not_execution_authority"] is True
    assert example["ready_for_promotion"] is False
    assert requirements["current_authority_envelope_gate"]["requirement_state"] == "satisfied"
    assert requirements["authority_upgrade_gate"]["requirement_state"] == "missing"
    assert requirements["authority_upgrade_gate"]["witness_kind"] == "authority_upgrade"
    assert "missing_authority_upgrade_witness" in example["missing_evidence"]


def test_component_route_family_promotion_witness_requirements_rejects_authority_overclaim(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    payload["decision"] = "approved"
    payload["outcome"] = "SolvedUnverified"
    payload["can_execute"] = True
    payload["ready_for_promotion"] = True
    payload["blocked_actions"].remove("terminal_closure")

    validation = validate_component_route_family_promotion_witness_requirements(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "decision must remain blocked" in serialized_errors
    assert "outcome must be AwaitingEvidence" in serialized_errors
    assert "can_execute" in serialized_errors
    assert "blocked_actions must include terminal_closure" in serialized_errors


def test_component_route_family_promotion_witness_requirements_rejects_missing_requirement(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    requirements = payload["promotion_witness_requirements"]
    assert isinstance(requirements, list)
    payload["promotion_witness_requirements"] = [
        requirement
        for requirement in requirements
        if isinstance(requirement, dict) and requirement.get("gate_id") != "authority_upgrade_gate"
    ]

    validation = validate_component_route_family_promotion_witness_requirements(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "promotion witness requirements missing witness kinds" in serialized_errors
    assert "missing_evidence must match failed requirement evidence keys" in serialized_errors
    assert "summary.witness_requirement_count" in serialized_errors


def test_component_route_family_promotion_witness_requirements_rejects_blocker_drift(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    requirements = _requirements(payload)
    authority_requirement = requirements["authority_upgrade_gate"]
    authority_requirement["proof_state"] = "Pass"
    authority_requirement["requirement_state"] = "satisfied"
    authority_requirement["blocks_promotion"] = False
    payload["missing_evidence"].remove("missing_authority_upgrade_witness")

    validation = validate_component_route_family_promotion_witness_requirements(
        example_path=_write_payload(tmp_path, payload)
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "missing_evidence omits required blockers" in serialized_errors
    assert "summary.missing_witness_count" in serialized_errors
    assert "example does not match runtime report" in serialized_errors
