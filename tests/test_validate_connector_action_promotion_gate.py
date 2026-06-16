"""Purpose: verify ConnectorActionPromotionGate validation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_connector_action_promotion_gate and SDLC validator.
Invariants:
  - Connector action promotion is a non-executing gate.
  - Foundation Mode does not admit live connector calls.
  - Promotion remains blocked until UAO, Phi_gov, approval, secret, worker, and rollback evidence exists.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_connector_action_promotion_gate as validator
from scripts import validate_sdlc_artifact as sdlc_validator


def test_connector_action_promotion_gate_passes() -> None:
    errors = validator.validate_connector_action_promotion_gate()
    gate = validator.load_json_object(validator.DEFAULT_GATE_PATH, "ConnectorActionPromotionGate")

    assert errors == []
    assert gate["receipt_version"] == validator.EXPECTED_RECEIPT_VERSION
    assert gate["promotion_scope"]["connector_id"] == "connector-github-read"
    assert gate["authority_preflight"]["connector_descriptor_bound"] is True
    assert gate["authority_preflight"]["phi_gov_authorization_present"] is False
    assert gate["gate_decision"]["promotion_allowed"] is False
    assert gate["gate_decision"]["live_connector_call_allowed"] is False
    assert validator.validate_connector_action_promotion_gate_record(gate) == []


def test_connector_action_promotion_gate_rejects_authority_drift() -> None:
    mutated = validator.build_mutated_connector_action_promotion_gate(
        promotion_scope__phi_gov_ref="phi-gov://authorized",
        authority_preflight__phi_gov_authorization_present=True,
        authority_preflight__operator_approval_present=True,
        authority_preflight__rollback_recovery_ref_present=True,
        authority_preflight__secret_access_receipt_present=True,
        authority_preflight__connector_worker_execution_receipt_present=True,
        gate_decision__decision="PROMOTION_ADMITTED",
        gate_decision__promotion_allowed=True,
        gate_decision__live_connector_call_allowed=True,
        gate_decision__external_write_allowed=True,
        gate_decision__secret_access_allowed=True,
        gate_decision__runtime_dispatch_allowed=True,
        gate_decision__deployment_mutation_allowed=True,
        gate_decision__terminal_closure_allowed=True,
        gate_decision__success_claim_allowed=True,
        gate_decision__raw_secret_material_included=True,
    )

    errors = validator.validate_connector_action_promotion_gate_record(mutated)

    assert any("Phi_gov authorization" in error for error in errors)
    assert any("phi_gov_authorization_present" in error for error in errors)
    assert any("operator_approval_present" in error for error in errors)
    assert any("rollback_recovery_ref_present" in error for error in errors)
    assert any("secret_access_receipt_present" in error for error in errors)
    assert any("connector_worker_execution_receipt_present" in error for error in errors)
    assert any("gate_decision.decision" in error for error in errors)
    assert any("gate_decision.promotion_allowed" in error for error in errors)
    assert any("gate_decision.live_connector_call_allowed" in error for error in errors)
    assert any("gate_decision.raw_secret_material_included" in error for error in errors)


def test_connector_action_promotion_gate_rejects_source_mismatch() -> None:
    descriptor = validator.load_json_object(validator.DEFAULT_CONNECTOR_DESCRIPTOR_PATH, "ConnectorDescriptor")
    result = validator.load_json_object(validator.DEFAULT_CONNECTOR_RESULT_PATH, "ConnectorResult")
    descriptor["effect_class"] = "external_write"
    descriptor["enabled"] = False
    result["connector_id"] = "other-connector"
    mutated = validator.build_mutated_connector_action_promotion_gate(
        source_connector_descriptor_ref="examples/other_descriptor.json",
        source_connector_result_ref="examples/other_result.json",
        promotion_scope__connector_id="other-connector",
        promotion_scope__requested_effect_class="external_read",
    )

    errors = validator.validate_connector_action_promotion_gate_record(mutated, connector_descriptor=descriptor, connector_result=result)

    assert any("source_connector_descriptor_ref" in error for error in errors)
    assert any("source_connector_result_ref" in error for error in errors)
    assert any("connector result connector_id" in error for error in errors)
    assert any("requested_effect_class" in error for error in errors)
    assert any("connector descriptor must be enabled" in error for error in errors)


def test_connector_action_promotion_gate_rejects_missing_refs() -> None:
    mutated = validator.build_mutated_connector_action_promotion_gate(
        gate_decision__required_live_evidence_refs=["evidence://connector-action/uao-admission"],
        gate_decision__blocked_reason_refs=["blocked://phi-gov/authorization-missing"],
        evidence_refs=["schemas/connector_action_promotion_gate.schema.json"],
    )

    errors = validator.validate_connector_action_promotion_gate_record(mutated)

    assert any("required_live_evidence_refs missing required ref" in error for error in errors)
    assert any("blocked_reason_refs missing required ref" in error for error in errors)
    assert any("evidence_refs missing required ref" in error for error in errors)


def test_connector_action_promotion_gate_rejects_receipt_ref_and_count_drift() -> None:
    mutated = validator.build_mutated_connector_action_promotion_gate(
        receipt_refs__connector_action_promotion_gate_schema="schemas/other.schema.json",
        receipt_refs__connector_result_schema="schemas/other_connector_result.schema.json",
        contract_summary__promotion_allowed=True,
        contract_summary__required_live_evidence_ref_count=1,
        contract_summary__blocked_reason_ref_count=1,
        contract_summary__receipt_ref_count=1,
        contract_summary__evidence_ref_count=1,
    )

    errors = validator.validate_connector_action_promotion_gate_record(mutated)

    assert any("receipt_refs.connector_action_promotion_gate_schema" in error for error in errors)
    assert any("receipt_refs.connector_result_schema" in error for error in errors)
    assert any("contract_summary.promotion_allowed" in error for error in errors)
    assert any("contract_summary.required_live_evidence_ref_count" in error for error in errors)
    assert any("contract_summary.blocked_reason_ref_count" in error for error in errors)
    assert any("contract_summary.receipt_ref_count" in error for error in errors)
    assert any("contract_summary.evidence_ref_count" in error for error in errors)


def test_cli_json_accepts_relative_paths(capsys) -> None:
    exit_code = validator.main(
        [
            "--schema",
            "schemas/connector_action_promotion_gate.schema.json",
            "--gate",
            "examples/connector_action_promotion_gate.foundation.json",
            "--connector-descriptor",
            "integration/contracts_compat/fixtures/connector_descriptor.json",
            "--connector-result",
            "integration/contracts_compat/fixtures/connector_result.json",
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "passed"
    assert Path(payload["schema_path"]).as_posix() == "schemas/connector_action_promotion_gate.schema.json"
    assert Path(payload["gate_path"]).as_posix() == "examples/connector_action_promotion_gate.foundation.json"
    assert payload["errors"] == []


def test_malformed_connector_action_promotion_gate_reports_errors() -> None:
    schema = validator._load_schema(validator.DEFAULT_SCHEMA_PATH)

    none_errors = validator.validate_connector_action_promotion_gate_record(None, schema)
    list_errors = validator.validate_connector_action_promotion_gate_record([], schema)

    assert any("connector action promotion gate must be a JSON object" in error for error in none_errors)
    assert any("connector action promotion gate must be a JSON object" in error for error in list_errors)
    assert any("expected object" in error for error in none_errors + list_errors)


def test_sdlc_requirement_and_design_validate_for_connector_action_promotion_gate() -> None:
    requirement_path = Path("examples/sdlc/requirement_connector_action_promotion_gate_20260616.json")
    design_path = Path("examples/sdlc/design_connector_action_promotion_gate_20260616.json")
    requirement = sdlc_validator.load_json_object(requirement_path, "connector action promotion gate requirement")
    design = sdlc_validator.load_json_object(design_path, "connector action promotion gate design")

    requirement_errors = sdlc_validator.validate_artifact_record("requirement", requirement)
    design_errors = sdlc_validator.validate_artifact_record("design_decision", design)

    assert requirement_errors == []
    assert design_errors == []
    assert design["requirement_id"] == requirement["requirement_id"]
    assert "schemas/connector_action_promotion_gate.schema.json" in requirement["affected_surfaces"]
    assert "schemas/connector_action_promotion_gate.schema.json" in design["schema_changes"]
    assert "scripts/validate_connector_action_promotion_gate.py" in design["validator_changes"]
    assert "tests/test_validate_connector_action_promotion_gate.py" in design["validator_changes"]
    assert "no live connector invocation" in requirement["non_goals"]
    assert design["security_model"]["effect_bearing_requires_receipt"] is True
