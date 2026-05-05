"""Gateway capability maturity tests.

Purpose: verify maturity is derived from evidence flags and cannot overclaim
production or autonomy readiness.
Governance scope: readiness levels, live receipt requirements, production gates,
autonomy gates, non-promotion metadata, and schema contract.
Dependencies: gateway.capability_maturity and schemas/capability_maturity.schema.json.
Invariants:
  - Missing evidence projects explicit blockers.
  - Effect-bearing production readiness requires a live write receipt.
  - Production readiness does not require autonomy controls.
  - Autonomy readiness requires C7 plus production readiness.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pytest

from gateway.capability_maturity import (
    CapabilityMaturityAssessment,
    CapabilityMaturityAssessor,
    CapabilityMaturityEvidence,
)
from scripts.validate_schemas import _validate_schema_instance


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "capability_maturity.schema.json"


def test_missing_evidence_assesses_to_c0_with_blockers() -> None:
    assessment = CapabilityMaturityAssessor().assess(CapabilityMaturityEvidence(capability_id="payments.send"))

    assert assessment.maturity_level == "C0"
    assert assessment.production_ready is False
    assert assessment.autonomy_ready is False
    assert "schema_evidence_missing" in assessment.blockers
    assert "worker_deployment_evidence_missing" in assessment.blockers
    assert assessment.metadata["assessment_is_not_promotion"] is True


def test_effect_bearing_capability_requires_live_write_for_production() -> None:
    assessment = CapabilityMaturityAssessor().assess(
        _evidence(effect_bearing=True, live_write_receipt_valid=False),
    )

    assert assessment.maturity_level == "C4"
    assert assessment.production_ready is False
    assert assessment.autonomy_ready is False
    assert "effect_bearing_production_requires_live_write" in assessment.blockers
    assert "autonomy_controls_missing" in assessment.blockers
    assert assessment.metadata["effect_bearing"] is True


def test_complete_production_evidence_assesses_to_c6_without_autonomy() -> None:
    assessment = CapabilityMaturityAssessor().assess(
        _evidence(effect_bearing=True, live_write_receipt_valid=True),
    )

    assert assessment.maturity_level == "C6"
    assert assessment.production_ready is True
    assert assessment.autonomy_ready is False
    assert assessment.blockers == ("autonomy_controls_missing",)
    assert assessment.evidence_refs == ("proof://capabilities/payments.send",)
    assert assessment.assessment_id.startswith("capability-maturity-")
    assert assessment.assessment_hash


def test_autonomy_controls_assess_to_c7_when_production_ready() -> None:
    assessment = CapabilityMaturityAssessor().assess(
        _evidence(
            effect_bearing=True,
            live_write_receipt_valid=True,
            autonomy_controls_bounded=True,
        ),
    )

    assert assessment.maturity_level == "C7"
    assert assessment.production_ready is True
    assert assessment.autonomy_ready is True
    assert assessment.blockers == ()
    assert assessment.metadata["assessment_is_not_promotion"] is True


def test_autonomy_controls_do_not_override_production_blockers() -> None:
    assessment = CapabilityMaturityAssessor().assess(
        _evidence(
            effect_bearing=True,
            live_write_receipt_valid=False,
            autonomy_controls_bounded=True,
        ),
    )

    assert assessment.maturity_level == "C4"
    assert assessment.production_ready is False
    assert assessment.autonomy_ready is False
    assert "autonomy_requires_production_readiness" in assessment.blockers
    assert "effect_bearing_production_requires_live_write" in assessment.blockers


def test_capability_maturity_schema_accepts_assessment_contract() -> None:
    assessment = CapabilityMaturityAssessor().assess(
        _evidence(effect_bearing=True, live_write_receipt_valid=True),
    )
    payload = _json_payload(assessment)
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    errors = _validate_schema_instance(schema, payload)

    assert errors == []
    assert schema["$id"] == "urn:mullusi:schema:capability-maturity:1"
    assert "C7" in schema["properties"]["maturity_level"]["enum"]
    assert payload["maturity_level"] == "C6"
    assert payload["production_ready"] is True
    assert payload["metadata"]["assessment_is_not_promotion"] is True


def test_capability_maturity_schema_rejects_readiness_overclaim() -> None:
    assessment = CapabilityMaturityAssessor().assess(CapabilityMaturityEvidence(capability_id="payments.send"))
    payload = _json_payload(assessment)
    payload["production_ready"] = True
    payload["autonomy_ready"] = True
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    errors = _validate_schema_instance(schema, payload)

    assert any("$.maturity_level: expected one of ['C6', 'C7']" in error for error in errors)
    assert any("$.maturity_level: expected const 'C7'" in error for error in errors)
    assert payload["maturity_level"] == "C0"
    assert payload["production_ready"] is True
    assert payload["autonomy_ready"] is True


def test_capability_maturity_rejects_invalid_manual_claims() -> None:
    with pytest.raises(ValueError, match="^capability_id_required$"):
        CapabilityMaturityEvidence(capability_id="  ")
    with pytest.raises(ValueError, match="^production_requires_C6_or_C7$"):
        CapabilityMaturityAssessment(
            assessment_id="assessment-1",
            capability_id="payments.send",
            maturity_level="C5",
            production_ready=True,
            autonomy_ready=False,
            blockers=(),
            evidence_refs=(),
        )
    with pytest.raises(ValueError, match="^autonomy_requires_C7$"):
        CapabilityMaturityAssessment(
            assessment_id="assessment-1",
            capability_id="payments.send",
            maturity_level="C6",
            production_ready=True,
            autonomy_ready=True,
            blockers=(),
            evidence_refs=(),
        )


def _evidence(
    *,
    effect_bearing: bool,
    live_write_receipt_valid: bool,
    autonomy_controls_bounded: bool = False,
) -> CapabilityMaturityEvidence:
    return CapabilityMaturityEvidence(
        capability_id="payments.send",
        schema_valid=True,
        policy_bound=True,
        mock_eval_passed=True,
        sandbox_receipt_valid=True,
        live_read_receipt_valid=True,
        live_write_receipt_valid=live_write_receipt_valid,
        worker_deployment_bound=True,
        recovery_evidence_present=True,
        autonomy_controls_bounded=autonomy_controls_bounded,
        effect_bearing=effect_bearing,
        evidence_refs=("proof://capabilities/payments.send",),
    )


def _json_payload(assessment: CapabilityMaturityAssessment) -> dict:
    payload = asdict(assessment)
    payload["blockers"] = list(assessment.blockers)
    payload["evidence_refs"] = list(assessment.evidence_refs)
    return payload
