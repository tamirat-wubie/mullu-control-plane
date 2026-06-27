"""Tests for evidence passport validation.

Purpose: prove evidence passports standardize proof packets across capability
families without granting execution authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_evidence_passports, capability passports, and
gate template registry fixtures.
Invariants: every capability passport has one evidence passport; missing
evidence, approval, replay, rollback, and blocked actions remain explicit.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcoi_runtime.app.evidence_passports import (
    EvidencePassportError,
    build_evidence_passports,
)
from scripts.validate_evidence_passports import (
    DEFAULT_EVIDENCE_PASSPORTS,
    DEFAULT_OUTPUT,
    validate_evidence_passports,
    write_evidence_passport_validation,
)


def _default_payload() -> dict[str, object]:
    return json.loads(DEFAULT_EVIDENCE_PASSPORTS.read_text(encoding="utf-8"))


def _write_payload(tmp_path: Path, payload: dict[str, object]) -> Path:
    evidence_path = tmp_path / "evidence_passports.json"
    evidence_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return evidence_path


def _evidence_passports(payload: dict[str, object]) -> list[dict[str, object]]:
    passports = payload["evidence_passports"]
    assert isinstance(passports, list)
    return passports


def _passport_by_capability(payload: dict[str, object], capability_id: str) -> dict[str, object]:
    for passport in _evidence_passports(payload):
        if passport.get("capability_id") == capability_id:
            return passport
    raise AssertionError(f"missing evidence passport {capability_id}")


def test_evidence_passports_validate_and_write(tmp_path: Path) -> None:
    validation = validate_evidence_passports()
    output_path = tmp_path / "evidence-passports-validation.json"

    written_path = write_evidence_passport_validation(validation, output_path)
    written_payload = json.loads(written_path.read_text(encoding="utf-8"))

    assert validation.ok is True
    assert validation.evidence_passport_count == validation.capability_count
    assert validation.evidence_passport_count > 20
    assert validation.missing_evidence_count > 0
    assert written_payload["errors"] == []
    assert DEFAULT_OUTPUT.name == "evidence_passports_validation.json"


def test_evidence_passports_answer_core_proof_questions() -> None:
    payload = build_evidence_passports()
    email = _passport_by_capability(payload, "email.draft")

    assert email["evidence_exists"]["present_evidence_count"] >= 0
    assert email["approval"]["approval_required"] is False
    assert email["missing_evidence"]
    assert email["blocked"]["blocked_action_count"] >= 1
    assert email["replay"]["replay_required"] is True
    assert email["rollback"]["rollback_status"] in {"review_only", "missing"}
    assert email["rollback"]["rollback_or_compensation_available"] is False
    assert email["continuation"]["safe_to_continue"] is True
    assert email["continuation"]["safe_for_live_action"] is False


def test_evidence_passports_project_approval_and_rollback_state() -> None:
    payload = build_evidence_passports()
    payment = _passport_by_capability(payload, "financial.send_payment")

    assert payment["approval"]["approval_required"] is True
    assert payment["approval"]["missing_approval"] is True
    assert payment["approval"]["approval_state"] == "required_missing"
    assert payment["rollback"]["rollback_status"] == "compensation_only"
    assert payment["rollback"]["can_compensate"] is True
    assert payment["outcome"] == "AwaitingEvidence"
    assert payment["proof_state"] == "Unknown"
    assert payment["continuation"]["continuation_mode"] == "approval_required"


def test_evidence_passports_reject_authority_overclaim(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["evidence_passport_set_is_not_execution_authority"] = False
    payload["live_execution_enabled"] = True
    passport = _passport_by_capability(payload, "email.draft")
    passport["evidence_passport_is_not_execution_authority"] = False

    validation = validate_evidence_passports(evidence_passports_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "evidence_passport_set_is_not_execution_authority must be true" in serialized_errors
    assert "live_execution_enabled must be false" in serialized_errors
    assert "evidence_passport_is_not_execution_authority must be true" in serialized_errors
    assert "example does not match runtime projection" in serialized_errors


def test_evidence_passports_reject_missing_capability_packet(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["evidence_passports"] = [
        passport
        for passport in _evidence_passports(payload)
        if passport.get("capability_id") != "financial.send_payment"
    ]
    summary = payload["summary"]
    assert isinstance(summary, dict)
    summary["evidence_passport_count"] = int(summary["evidence_passport_count"]) - 1

    validation = validate_evidence_passports(evidence_passports_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "registered capabilities missing evidence passports ['financial.send_payment']" in serialized_errors
    assert "example does not match runtime projection" in serialized_errors


def test_evidence_passports_reject_inconsistent_missing_evidence_outcome(tmp_path: Path) -> None:
    payload = _default_payload()
    passport = _passport_by_capability(payload, "email.draft")
    passport["outcome"] = "SolvedVerified"
    passport["proof_state"] = "Pass"

    validation = validate_evidence_passports(evidence_passports_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "missing evidence must produce AwaitingEvidence" in serialized_errors
    assert "example does not match runtime projection" in serialized_errors


def test_evidence_passports_reject_unresolved_gate_template() -> None:
    passport_set = {
        "passport_set_id": "demo.passports",
        "passports": [
            {
                "capability_id": "demo.read",
                "capability_name": "Demo Read",
                "family": "demo",
                "operator_status": "Live action disabled",
                "current_unlock_level": "C1",
                "allowed_actions": ["read"],
                "blocked_actions": ["claim_production_ready"],
                "required_receipts": ["terminal_closure_certificate"],
                "required_gates": ["gate.demo.missing"],
                "rollback_status": {
                    "status": "not_required",
                    "rollback_capability": "",
                    "compensation_capability": "",
                    "review_required_on_failure": False,
                },
                "next_unlock_step": "add demo evidence",
                "evidence_refs": [],
                "production_ready": False,
            }
        ],
    }
    gate_registry = {
        "registry_id": "demo.gates",
        "templates": [
            {
                "gate_id": "gate.uao.admission",
                "required_receipts": ["universal_action_orchestration_validation_receipt"],
                "blocks_when_missing": ["unorchestrated_effect"],
            }
        ],
    }

    with pytest.raises(EvidencePassportError, match="unresolved gate templates"):
        build_evidence_passports(passports=passport_set, gate_registry=gate_registry)
