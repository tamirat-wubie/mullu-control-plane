"""Tests for the reusable causal repair service.

Purpose: prove workflow failure classification emits proof-only repair plans
without mutation or repair execution authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: mcoi.causal_repair.service and causal repair receipt schema.
Invariants: every default failure class is covered, evidence obligations are
explicit, and repair execution overclaims fail validation.
"""

from __future__ import annotations

import json
from pathlib import Path

from causal_repair.service import (
    CAPABILITY_ID,
    DEFAULT_FAILURE_IDS,
    FORBIDDEN_EFFECTS,
    build_causal_repair_service_receipt,
    classify_failure,
    run_causal_repair_service,
    validate_causal_repair_service_receipt,
)
from scripts.run_causal_repair_service import main as run_main
from scripts.validate_causal_repair_service_receipt import main as validate_main


def test_causal_repair_service_receipt_covers_default_failures() -> None:
    receipt = build_causal_repair_service_receipt()
    validation = validate_causal_repair_service_receipt(receipt=receipt)
    case_ids = {case["failure_id"] for case in receipt["cases"]}

    assert validation.ok is True
    assert receipt["capability_id"] == CAPABILITY_ID
    assert receipt["service_status"] == "planned_no_effect"
    assert receipt["live_execution_enabled"] is False
    assert receipt["repair_execution_performed"] is False
    assert case_ids == set(DEFAULT_FAILURE_IDS)
    assert receipt["case_count"] == len(DEFAULT_FAILURE_IDS)


def test_causal_repair_service_classifies_governance_blocked_rollback_gap() -> None:
    repair_case = classify_failure("rollback_impossible")
    proof = repair_case["rollback_or_compensation_proof"]
    proposal = repair_case["proposal"]

    assert repair_case["effect_class"] == "public_irreversible"
    assert repair_case["reversibility_class"] == "forbidden"
    assert repair_case["repair_strategy"] == "forbid"
    assert proof["execution_performed"] is False
    assert proof["rollback_claim_allowed"] is False
    assert proposal["approval_required"] is True
    assert proposal["operator_outcome"] == "GovernanceBlocked"


def test_causal_repair_service_blocks_execution_overclaims() -> None:
    receipt = build_causal_repair_service_receipt()
    receipt["live_execution_enabled"] = True
    receipt["repair_execution_performed"] = True
    receipt["cases"][0]["rollback_or_compensation_proof"]["execution_performed"] = True
    receipt["blocked_effects"].remove("live_execution")

    validation = validate_causal_repair_service_receipt(receipt=receipt)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "live_execution_enabled_must_be_false" in serialized_errors
    assert "repair_execution_performed_must_be_false" in serialized_errors
    assert "cases[0].execution_performed_must_be_false" in serialized_errors
    assert "blocked_effect_missing:live_execution" in serialized_errors


def test_causal_repair_service_rejects_missing_case_and_hash_drift() -> None:
    receipt = build_causal_repair_service_receipt()
    receipt["cases"] = [
        repair_case
        for repair_case in receipt["cases"]
        if repair_case["failure_id"] != "unsafe_browser_evidence"
    ]
    receipt["receipt_hash"] = "0" * 64

    validation = validate_causal_repair_service_receipt(receipt=receipt)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "required_case_missing:unsafe_browser_evidence" in serialized_errors
    assert "receipt_hash_mismatch" in serialized_errors
    assert "expected at least 7 item(s)" in serialized_errors


def test_causal_repair_service_run_writes_receipt(tmp_path: Path) -> None:
    output_path = tmp_path / "causal-repair-service.json"

    receipt, validation = run_causal_repair_service(output_path=output_path)

    assert validation.ok is True
    assert output_path.exists()
    assert receipt["receipt_id"] == "causal_repair_service.foundation.v1"
    assert json.loads(output_path.read_text(encoding="utf-8"))["repair_execution_performed"] is False


def test_causal_repair_service_cli_and_validator(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "causal-repair-service.json"

    run_exit = run_main(["--output", str(output_path), "--json"])
    run_output = capsys.readouterr().out
    validate_exit = validate_main(["--receipt", str(output_path), "--json"])
    validate_output = capsys.readouterr().out

    assert run_exit == 0
    assert validate_exit == 0
    assert '"govern.causal_repair.service"' in run_output
    assert '"ok": true' in validate_output
    assert all(effect in run_output for effect in FORBIDDEN_EFFECTS)
