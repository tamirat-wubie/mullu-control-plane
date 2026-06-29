"""Tests for Component Harness route-family ownership readiness validation.

Purpose: prove route-family ownership readiness exposes promotion blockers
without granting route execution or terminal closure authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_component_route_family_ownership and ownership
readiness runtime.
Invariants: platform-classified route families remain blocked until proof,
lifecycle, route-binding, and authority witnesses exist.
"""

from __future__ import annotations

import json
from pathlib import Path

from mcoi_runtime.app.component_route_family_ownership import (
    build_component_route_family_ownership_report,
)
from scripts.validate_component_route_family_ownership import (
    DEFAULT_EXAMPLE,
    DEFAULT_OUTPUT,
    validate_component_route_family_ownership,
    write_component_route_family_ownership_validation,
)


def _default_payload() -> dict[str, object]:
    return json.loads(DEFAULT_EXAMPLE.read_text(encoding="utf-8"))


def _write_payload(tmp_path: Path, payload: dict[str, object]) -> Path:
    example_path = tmp_path / "component_route_family_ownership.json"
    example_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return example_path


def test_component_route_family_ownership_schema_valid_and_write(tmp_path: Path) -> None:
    validation = validate_component_route_family_ownership()
    output_path = tmp_path / "component-route-family-ownership-validation.json"

    written_path = write_component_route_family_ownership_validation(validation, output_path)
    written_payload = json.loads(written_path.read_text(encoding="utf-8"))

    assert validation.route_family_count == 81
    assert validation.declared_route_count == 456
    assert validation.selected_component_bound_count == 13
    assert validation.promotion_blocked_count == 68
    assert validation.proof_binding_gap_count == 66
    assert written_payload["errors"] == []
    assert DEFAULT_OUTPUT.name == "component_route_family_ownership_validation.json"


def test_component_route_family_ownership_example_matches_runtime_projection() -> None:
    example = _default_payload()
    projection = build_component_route_family_ownership_report()
    records = {record["surface_id"]: record for record in example["ownership_records"]}

    assert example == projection
    assert example["ownership_readiness_is_not_execution_authority"] is True
    assert example["live_execution_enabled"] is False
    assert records["component_harness_read_model"]["readiness_state"] == "selected_component_bound"
    assert records["component_harness_read_model"]["promotion_blockers"] == []
    assert records["governed_connector_framework"]["readiness_state"] == (
        "blocked_needs_route_binding_witness"
    )
    assert "generic_connector_surface_not_product_specific_authority" in (
        records["governed_connector_framework"]["promotion_blockers"]
    )


def test_component_route_family_ownership_rejects_authority_and_summary_drift(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    payload["can_call_connector"] = True
    payload["summary"]["promotion_blocked_count"] = 0

    validation = validate_component_route_family_ownership(example_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "can_call_connector" in serialized_errors
    assert "summary.promotion_blocked_count" in serialized_errors
    assert "example does not match runtime report" in serialized_errors


def test_component_route_family_ownership_rejects_platform_promotion_overclaim(
    tmp_path: Path,
) -> None:
    payload = _default_payload()
    records = {
        record["surface_id"]: record
        for record in payload["ownership_records"]
        if isinstance(record, dict)
    }
    record = records["agent_adapter_protocol"]
    record["readiness_state"] = "selected_component_bound"
    record["selected_bound_component_ids"] = ["agentic_service_harness"]
    record["promotion_blockers"] = []
    record["can_enable_live_action"] = True
    record["blocked_actions"].remove("terminal_closure")

    validation = validate_component_route_family_ownership(example_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "selected readiness requires selected binding level" in serialized_errors
    assert "cannot enable live action" in serialized_errors
    assert "must block terminal_closure" in serialized_errors
    assert "summary.promotion_blocked_count" in serialized_errors
