"""Purpose: verify ReadinessWaiverReviewPacket validation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_readiness_waiver_review_packet and SDLC validator.
Invariants:
  - Readiness waiver review is non-executing.
  - Foundation Mode does not grant waiver, readiness, deployment, or terminal authority.
  - Expiry and compensating controls remain explicit and auditable.
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
    assert packet["packet_version"] == validator.EXPECTED_PACKET_VERSION
    assert packet["waiver_scope"]["readiness_surface"] == "deployment"
    assert packet["review_chain"]["operator_review_required"] is True
    assert packet["review_chain"]["operator_approval_present"] is False
    assert packet["waiver_decision"]["waiver_granted"] is False
    assert packet["waiver_decision"]["deployment_authority_allowed"] is False
    assert validator.validate_readiness_waiver_review_packet_record(packet) == []


def test_readiness_waiver_review_packet_rejects_authority_drift() -> None:
    mutated = validator.build_mutated_readiness_waiver_review_packet(
        waiver_scope__phi_gov_ref="phi-gov://authorized",
        review_chain__operator_approval_present=True,
        review_chain__phi_gov_authorization_present=True,
        review_chain__accepted_risk_ref="accepted-risk://waiver/granted",
        waiver_decision__decision="WAIVER_GRANTED",
        waiver_decision__waiver_granted=True,
        waiver_decision__readiness_claim_allowed=True,
        waiver_decision__deployment_authority_allowed=True,
        waiver_decision__runtime_promotion_allowed=True,
        waiver_decision__external_publication_allowed=True,
        waiver_decision__terminal_closure_allowed=True,
        waiver_decision__success_claim_allowed=True,
    )

    errors = validator.validate_readiness_waiver_review_packet_record(mutated)

    assert any("Phi_gov authorization" in error for error in errors)
    assert any("operator_approval_present" in error for error in errors)
    assert any("phi_gov_authorization_present" in error for error in errors)
    assert any("accepted risk ref" in error for error in errors)
    assert any("waiver_decision.decision" in error for error in errors)
    assert any("waiver_decision.waiver_granted" in error for error in errors)
    assert any("waiver_decision.deployment_authority_allowed" in error for error in errors)
    assert any("waiver_decision.terminal_closure_allowed" in error for error in errors)


def test_readiness_waiver_review_packet_rejects_missing_refs() -> None:
    mutated = validator.build_mutated_readiness_waiver_review_packet(
        waiver_decision__required_evidence_refs=["evidence://readiness-waiver/operator-approval"],
        waiver_decision__blocked_reason_refs=["blocked://operator-approval/missing"],
        evidence_refs=["schemas/readiness_waiver_review_packet.schema.json"],
    )

    errors = validator.validate_readiness_waiver_review_packet_record(mutated)

    assert any("required_evidence_refs missing required ref" in error for error in errors)
    assert any("blocked_reason_refs missing required ref" in error for error in errors)
    assert any("evidence_refs missing required ref" in error for error in errors)


def test_readiness_waiver_review_packet_rejects_expiry_drift() -> None:
    expired = validator.build_mutated_readiness_waiver_review_packet(
        expiry_policy__expired=True,
        expiry_policy__renewal_requires_operator_approval=False,
        expiry_policy__max_duration_days=30,
        expiry_policy__expires_at="2026-06-15T00:00:00Z",
        expiry_policy__expiry_receipt_ref="schemas/other.schema.json",
    )

    errors = validator.validate_readiness_waiver_review_packet_record(expired)

    assert any("expiry_policy.expired" in error for error in errors)
    assert any("renewal_requires_operator_approval" in error for error in errors)
    assert any("max_duration_days" in error for error in errors)
    assert any("expiry_receipt_ref" in error for error in errors)
    assert any("expires_at must be after generated_at" in error for error in errors)


def test_readiness_waiver_review_packet_rejects_compensating_control_drift() -> None:
    packet = validator.build_mutated_readiness_waiver_review_packet()
    packet["compensating_controls"][0]["active"] = False
    packet["compensating_controls"][1]["control_id"] = packet["compensating_controls"][0]["control_id"]
    packet["compensating_controls"][1]["verification_ref"] = ""

    errors = validator.validate_readiness_waiver_review_packet_record(packet)

    assert any("compensating_controls[0].active" in error for error in errors)
    assert any("compensating_controls[1].control_id must be unique" in error for error in errors)
    assert any("compensating_controls[1].verification_ref" in error for error in errors)


def test_readiness_waiver_review_packet_rejects_receipt_ref_and_count_drift() -> None:
    mutated = validator.build_mutated_readiness_waiver_review_packet(
        receipt_refs__readiness_waiver_review_packet_schema="schemas/other.schema.json",
        receipt_refs__sdlc_deployment_candidate_schema="schemas/other_deployment.schema.json",
        contract_summary__waiver_granted=True,
        contract_summary__compensating_control_count=1,
        contract_summary__required_evidence_ref_count=1,
        contract_summary__blocked_reason_ref_count=1,
        contract_summary__receipt_ref_count=1,
        contract_summary__evidence_ref_count=1,
    )

    errors = validator.validate_readiness_waiver_review_packet_record(mutated)

    assert any("receipt_refs.readiness_waiver_review_packet_schema" in error for error in errors)
    assert any("receipt_refs.sdlc_deployment_candidate_schema" in error for error in errors)
    assert any("contract_summary.waiver_granted" in error for error in errors)
    assert any("contract_summary.compensating_control_count" in error for error in errors)
    assert any("contract_summary.required_evidence_ref_count" in error for error in errors)
    assert any("contract_summary.evidence_ref_count" in error for error in errors)


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
    requirement = sdlc_validator.load_json_object(requirement_path, "readiness waiver review packet requirement")
    design = sdlc_validator.load_json_object(design_path, "readiness waiver review packet design")

    requirement_errors = sdlc_validator.validate_artifact_record("requirement", requirement)
    design_errors = sdlc_validator.validate_artifact_record("design_decision", design)

    assert requirement_errors == []
    assert design_errors == []
    assert design["requirement_id"] == requirement["requirement_id"]
    assert "schemas/readiness_waiver_review_packet.schema.json" in requirement["affected_surfaces"]
    assert "schemas/readiness_waiver_review_packet.schema.json" in design["schema_changes"]
    assert "scripts/validate_readiness_waiver_review_packet.py" in design["validator_changes"]
    assert "tests/test_validate_readiness_waiver_review_packet.py" in design["validator_changes"]
    assert "no deployment authority" in requirement["non_goals"]
    assert design["security_model"]["effect_bearing_requires_receipt"] is True
