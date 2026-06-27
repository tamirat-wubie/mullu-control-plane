"""Tests for capability passport validation.

Purpose: prove capability passports mirror capability pack state while exposing
unlock level, gate, receipt, and rollback obligations.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_capability_passports and foundation capability
pack fixtures.
Invariants: every governed capability has one passport; passports remain
read-model evidence and do not grant execution authority.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcoi_runtime.app.capability_passports import (
    CapabilityPassportError,
    build_capability_passports,
)
from scripts.validate_capability_passports import (
    DEFAULT_OUTPUT,
    DEFAULT_PASSPORTS,
    validate_capability_passports,
    write_capability_passport_validation,
)


def _default_payload() -> dict[str, object]:
    return json.loads(DEFAULT_PASSPORTS.read_text(encoding="utf-8"))


def _write_payload(tmp_path: Path, payload: dict[str, object]) -> Path:
    passport_path = tmp_path / "capability_passports.json"
    passport_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return passport_path


def _passports(payload: dict[str, object]) -> list[dict[str, object]]:
    passports = payload["passports"]
    assert isinstance(passports, list)
    return passports


def _passport_by_capability(payload: dict[str, object], capability_id: str) -> dict[str, object]:
    for passport in _passports(payload):
        if passport.get("capability_id") == capability_id:
            return passport
    raise AssertionError(f"missing passport {capability_id}")


def test_capability_passports_validate_and_write(tmp_path: Path) -> None:
    validation = validate_capability_passports()
    output_path = tmp_path / "capability-passports-validation.json"

    written_path = write_capability_passport_validation(validation, output_path)
    written_payload = json.loads(written_path.read_text(encoding="utf-8"))

    assert validation.ok is True
    assert validation.passport_count == validation.capability_count
    assert validation.passport_count > 20
    assert written_payload["errors"] == []
    assert written_payload["ok"] is True
    assert DEFAULT_OUTPUT.name == "capability_passports_validation.json"


def test_capability_passports_project_email_draft_and_send_gates() -> None:
    payload = build_capability_passports()
    draft = _passport_by_capability(payload, "email.draft")
    send = _passport_by_capability(payload, "email.send.with_approval")

    assert draft["operator_status"] == "Live action disabled"
    assert "prepare_draft" in draft["allowed_actions"]
    assert "gate.receipt.append" in draft["required_gates"]
    assert "terminal_closure_certificate" in draft["required_receipts"]
    assert send["operator_status"] == "Live action disabled"
    assert "gate.approval.required" in send["required_gates"]
    assert "execute_without_approval" in send["blocked_actions"]
    assert "connector_call_without_lease" in send["blocked_actions"]


def test_capability_passports_project_financial_maturity_status() -> None:
    payload = build_capability_passports()
    balance = _passport_by_capability(payload, "financial.balance_check")
    payment = _passport_by_capability(payload, "financial.send_payment")

    assert balance["current_unlock_level"] in {"C3", "C4", "C5", "C6", "C7"}
    assert balance["passport_is_not_execution_authority"] is True
    assert payment["current_unlock_level"] == "C6"
    assert payment["production_ready"] is True
    assert payment["operator_status"] == "Needs approval"
    assert payment["rollback_status"]["status"] == "compensation_only"
    assert "gate.approval.required" in payment["required_gates"]


def test_capability_passports_reject_missing_capability_passport(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["passports"] = [
        passport for passport in _passports(payload) if passport.get("capability_id") != "financial.send_payment"
    ]
    summary = payload["summary"]
    assert isinstance(summary, dict)
    summary["passport_count"] = int(summary["passport_count"]) - 1

    validation = validate_capability_passports(passport_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "registered capabilities missing passports ['financial.send_payment']" in serialized_errors
    assert "example does not match runtime projection" in serialized_errors
    assert validation.passport_count == validation.capability_count - 1


def test_capability_passports_reject_authority_overclaim(tmp_path: Path) -> None:
    payload = _default_payload()
    passport = _passport_by_capability(payload, "email.send.with_approval")
    passport["passport_is_not_execution_authority"] = False
    passport["blocked_actions"] = ["message_sent_without_approval"]
    passport["required_gates"] = ["gate.receipt.append"]

    validation = validate_capability_passports(passport_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "passport_is_not_execution_authority must be true" in serialized_errors
    assert "missing base gates" in serialized_errors
    assert "must block terminal success overclaim" in serialized_errors


def test_capability_passports_reject_non_production_without_gate(tmp_path: Path) -> None:
    payload = _default_payload()
    passport = _passport_by_capability(payload, "email.draft")
    gates = passport["required_gates"]
    assert isinstance(gates, list)
    passport["required_gates"] = [gate for gate in gates if gate != "gate.production.evidence"]

    validation = validate_capability_passports(passport_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "non-production passport must require gate.production.evidence" in serialized_errors
    assert "example does not match runtime projection" in serialized_errors
    assert passport["production_ready"] is False


def test_capability_passports_reject_duplicate_capability_ids(tmp_path: Path) -> None:
    capability_pack = {
        "capabilities": [
            {
                "capability_id": "demo.read",
                "domain": "demo",
                "version": "0.1.0",
                "input_schema_ref": "schemas/demo/read.input.schema.json",
                "output_schema_ref": "schemas/demo/read.output.schema.json",
                "effect_model": {
                    "expected_effects": ["demo_read"],
                    "forbidden_effects": ["demo_write"],
                    "reconciliation_required": True,
                },
                "evidence_model": {
                    "required_evidence": ["receipt_status"],
                    "terminal_certificate_required": True,
                },
                "authority_policy": {
                    "required_roles": ["demo_reader"],
                    "approval_chain": [],
                    "separation_of_duty": False,
                },
                "isolation_profile": {
                    "execution_plane": "gateway_process",
                    "network_allowlist": [],
                    "secret_scope": "demo_read",
                },
                "recovery_plan": {
                    "rollback_capability": "",
                    "compensation_capability": "",
                    "review_required_on_failure": True,
                },
                "cost_model": {
                    "budget_class": "standard",
                    "max_estimated_cost": 0.0,
                },
                "obligation_model": {
                    "owner_team": "demo",
                    "failure_due_seconds": 60,
                    "escalation_route": "demo",
                },
                "certification_status": "certified",
                "metadata": {
                    "risk_tier": "low"
                },
                "extensions": {
                    "governed_record": {
                        "read_only": True,
                        "world_mutating": False,
                        "requires_approval": False,
                        "requires_sandbox": False,
                        "allowed_tools": ["demo.read"],
                    }
                },
            }
        ]
    }
    first_pack = tmp_path / "first_capability_pack.json"
    second_pack = tmp_path / "second_capability_pack.json"
    first_pack.write_text(json.dumps(capability_pack), encoding="utf-8")
    second_pack.write_text(json.dumps(capability_pack), encoding="utf-8")

    with pytest.raises(CapabilityPassportError, match="duplicate capability_id demo.read"):
        build_capability_passports(capability_pack_paths=(first_pack, second_pack))
