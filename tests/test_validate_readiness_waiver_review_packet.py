"""Purpose: verify ReadinessWaiverReviewPacket validation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_readiness_waiver_review_packet and SDLC validator.
Invariants:
  - Readiness waiver review is a non-executing packet.
  - Foundation Mode does not grant waiver, deployment, or terminal closure authority.
  - Expiry, approval, compensating controls, rollback, and incident evidence remain explicit.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_readiness_waiver_review_packet as validator
from scripts import validate_sdlc_artifact as sdlc_validator


def test_readiness_waiver_review_packet_passes() -> None:
    errors = validator.validate_readiness_waiver_review_packet()
    packet = validator.load_json_object(validator.DEFAULT_PACKET_PATH, "ReadinessWaiverReviewPacket")

    assert errors == []
    assert packet["receipt_version"] == validator.EXPECTED_RECEIPT_VERSION
    assert packet["waiver_scope"]["target_environment"] == "foundation_local"
    assert packet["waiver_scope"]["phi_gov_ref"] is None
    assert packet["review_controls"]["operator_approval_present"] is False
    assert packet["review_controls"]["expiry_required"] is True
    assert packet["gate_decision"]["waiver_granted"] is False
    assert packet["gate_decision"]["deployment_mutation_allowed"] is False
    assert validator.validate_readiness_waiver_review_packet_record(packet) == []


def test_readiness_waiver_review_packet_rejects_authority_drift() -> None:
    mutated = validator.build_mutated_readiness_waiver_review_packet(
        waiver_scope__target_environment="production",
        waiver_scope__requested_disposition="temporary_waiver",
        waiver_scope__phi_gov_ref="phi-gov://authorized",
        review_controls__operator_approval_present=True,
        review_controls__approval_refs=["approval://operator/readiness-waiver"],
        review_controls__accepted_risk_ref_present=True,
        review_controls__rollback_recovery_ref_present=True,
        review_controls__incident_handoff_ref_present=True,
        gate_decision__decision="WAIVER_GRANTED_TEMPORARY",
        gate_decision__waiver_granted=True,
        gate_decision__deployment_mutation_allowed=True,
        gate_decision__production_promotion_allowed=True,
        gate_decision__terminal_closure_allowed=True,
        gate_decision__readiness_success_claim_allowed=True,
        gate_decision__external_exposure_allowed=True,
        gate_decision__raw_secret_material_included=True,
    )

    errors = validator.validate_readiness_waiver_review_packet_record(mutated)

    assert any("target_environment" in error for error in errors)
    assert any("requested_disposition" in error for error in errors)
    assert any("Phi_gov authorization" in error for error in errors)
    assert any("operator_approval_present" in error for error in errors)
    assert any("approval_refs" in error for error in errors)
    assert any("accepted_risk_ref_present" in error for error in errors)
    assert any("rollback_recovery_ref_present" in error for error in errors)
    assert any("incident_handoff_ref_present" in error for error in errors)
    assert any("gate_decision.decision" in error for error in errors)
    assert any("gate_decision.deployment_mutation_allowed" in error for error in errors)
    assert any("gate_decision.raw_secret_material_included" in error for error in errors)


def test_readiness_waiver_review_packet_rejects_expiry_and_control_drift() -> None:
    mutated = validator.build_mutated_readiness_waiver_review_packet(
        generated_at="2026-06-16T00:00:00Z",
        review_controls__expiry_at="2026-06-15T00:00:00Z",
        review_controls__expiry_required=False,
        review_controls__compensating_controls=[],
        review_controls__mfidel_atomicity_preserved=False,
        gate_decision__expiry_required=False,
    )

    errors = validator.validate_readiness_waiver_review_packet_record(mutated)

    assert any("expiry_at must be later than generated_at" in error for error in errors)
    assert any("review_controls.expiry_required" in error for error in errors)
    assert any("compensating_controls" in error for error in errors)
    assert any("mfidel_atomicity_preserved" in error for error in errors)
    assert any("gate_decision.expiry_required" in error for error in errors)


def test_readiness_waiver_review_packet_rejects_missing_refs_and_count_drift() -> None:
    mutated = validator.build_mutated_readiness_waiver_review_packet(
        receipt_refs__readiness_waiver_review_packet_schema="schemas/other.schema.json",
        gate_decision__required_evidence_refs=["evidence://readiness-waiver/operator-approval"],
        gate_decision__blocked_reason_refs=["blocked://readiness-waiver/operator-approval-missing"],
        evidence_refs=["schemas/readiness_waiver_review_packet.schema.json"],
        contract_summary__waiver_granted=True,
        contract_summary__required_evidence_ref_count=99,
        contract_summary__blocked_reason_ref_count=99,
        contract_summary__approval_ref_count=1,
        contract_summary__compensating_control_count=1,
        contract_summary__receipt_ref_count=1,
        contract_summary__evidence_ref_count=1,
    )

    errors = validator.validate_readiness_waiver_review_packet_record(mutated)

    assert any("receipt_refs.readiness_waiver_review_packet_schema" in error for error in errors)
    assert any("required_evidence_refs missing required ref" in error for error in errors)
    assert any("blocked_reason_refs missing required ref" in error for error in errors)
    assert any("evidence_refs missing required ref" in error for error in errors)
    assert any("contract_summary.waiver_granted" in error for error in errors)
    assert any("contract_summary.required_evidence_ref_count" in error for error in errors)
    assert any("contract_summary.receipt_ref_count" in error for error in errors)


def test_cli_json_accepts_relative_paths(capsys) -> None:
    exit_code = validator.main(
        [
            "--schema",
            "schemas/readiness_waiver_review_packet.schema.json",
            "--packet",
            "examples/readiness_waiver_review_packet.foundation.json",
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "passed"
    assert Path(payload["schema_path"]).as_posix() == "schemas/readiness_waiver_review_packet.schema.json"
    assert Path(payload["packet_path"]).as_posix() == "examples/readiness_waiver_review_packet.foundation.json"
    assert payload["errors"] == []


def test_malformed_readiness_waiver_review_packet_reports_errors() -> None:
    schema = validator._load_schema(validator.DEFAULT_SCHEMA_PATH)

    none_errors = validator.validate_readiness_waiver_review_packet_record(None, schema)
    list_errors = validator.validate_readiness_waiver_review_packet_record([], schema)

    assert any("readiness waiver review packet must be a JSON object" in error for error in none_errors)
    assert any("readiness waiver review packet must be a JSON object" in error for error in list_errors)
    assert any("expected object" in error for error in none_errors + list_errors)


def test_sdlc_requirement_and_design_validate_for_readiness_waiver_review_packet() -> None:
    requirement_path = Path("examples/sdlc/requirement_readiness_waiver_review_packet_20260616.json")
    design_path = Path("examples/sdlc/design_readiness_waiver_review_packet_20260616.json")
    requirement = sdlc_validator.load_json_object(requirement_path, "readiness waiver requirement")
    design = sdlc_validator.load_json_object(design_path, "readiness waiver design")

    requirement_errors = sdlc_validator.validate_artifact_record("requirement", requirement)
    design_errors = sdlc_validator.validate_artifact_record("design_decision", design)

    assert requirement_errors == []
    assert design_errors == []
    assert design["requirement_id"] == requirement["requirement_id"]
    assert "schemas/readiness_waiver_review_packet.schema.json" in requirement["affected_surfaces"]
    assert "schemas/readiness_waiver_review_packet.schema.json" in design["schema_changes"]
    assert "scripts/validate_readiness_waiver_review_packet.py" in design["validator_changes"]
    assert "tests/test_validate_readiness_waiver_review_packet.py" in design["validator_changes"]
    assert "no deployment mutation" in requirement["non_goals"]
    assert design["security_model"]["effect_bearing_requires_receipt"] is True
