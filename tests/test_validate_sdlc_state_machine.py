"""Purpose: verify governed SDLC state machine validation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.validate_sdlc_state_machine.
Invariants:
  - Canonical transitions remain present.
  - Terminal states cannot have outgoing transitions.
  - Closure receipts bind terminal state and receipt evidence.
"""

from __future__ import annotations

import copy
import io
import json
from contextlib import redirect_stdout
from pathlib import Path

from scripts import validate_sdlc_artifact
from scripts import validate_sdlc_state_machine as validator


def test_current_sdlc_state_machine_contract_passes() -> None:
    errors = validator.validate_contract()

    assert errors == []
    assert validator.ACTIVE_STATES[0] == "proposed"
    assert validator.TERMINAL_STATES[-1] == "closed_failed_with_receipt"
    assert ("closed", "closed_success") in validator.CANONICAL_TRANSITIONS
    assert validator.TRANSITION_RECEIPT_SPEC.example_path.exists()


def test_terminal_outgoing_transition_is_rejected() -> None:
    transitions = validator.DEFAULT_TRANSITIONS + (("closed_success", "proposed"),)

    errors = validator.validate_state_machine_graph(transitions)

    assert "terminal state has outgoing transition: closed_success" in errors
    assert len(errors) >= 1
    assert ("closed_success", "proposed") in transitions


def test_missing_canonical_transition_is_rejected() -> None:
    transitions = tuple(
        transition
        for transition in validator.DEFAULT_TRANSITIONS
        if transition != ("requirements_defined", "design_ready")
    )

    errors = validator.validate_state_machine_graph(transitions)

    assert "missing canonical transition: requirements_defined -> design_ready" in errors
    assert len(errors) >= 1
    assert ("requirements_defined", "design_ready") not in transitions


def test_closure_open_blocker_blocks_success(tmp_path: Path) -> None:
    closure = copy.deepcopy(validate_sdlc_artifact.load_example_records()["closure_receipt"])
    closure["known_remaining_blockers"] = [
        {
            "blocker_id": "blocker-open",
            "status": "open",
            "reason": "unclassified blocker",
        }
    ]
    closure_path = tmp_path / "closure.json"
    closure_path.write_text(json.dumps(closure), encoding="utf-8")

    errors = validator.validate_closure_state(closure_path)

    assert any("closed_success cannot carry" in error for error in errors)
    assert len(errors) >= 1
    assert closure_path.exists()


def test_transition_receipt_rejects_unknown_edge(tmp_path: Path) -> None:
    transition = copy.deepcopy(validate_sdlc_artifact.load_example_records()["transition_receipt"])
    transition["from_state"] = "proposed"
    transition["to_state"] = "deployment_candidate"
    transition_path = tmp_path / "transition.json"
    transition_path.write_text(json.dumps(transition), encoding="utf-8")

    errors = validator.validate_transition_receipt(transition_path)

    assert "transition_receipt: transition is not allowed: proposed -> deployment_candidate" in errors
    assert len(errors) >= 1
    assert transition_path.exists()


def test_allowed_transition_rejects_blockers(tmp_path: Path) -> None:
    transition = copy.deepcopy(validate_sdlc_artifact.load_example_records()["transition_receipt"])
    transition["blockers"] = [
        {
            "blocker_id": "blocker-transition",
            "reason": "verification receipt missing",
            "evidence_ref": "examples/sdlc/verification_uao_validator.json",
        }
    ]
    transition_path = tmp_path / "transition-with-blocker.json"
    transition_path.write_text(json.dumps(transition), encoding="utf-8")

    errors = validator.validate_transition_receipt(transition_path)

    assert "transition_receipt: allowed transition cannot carry blockers" in errors
    assert len(errors) >= 1
    assert transition["decision"] == "allowed"


def test_blocked_transition_requires_blocker_and_blocked_decision(tmp_path: Path) -> None:
    transition = copy.deepcopy(validate_sdlc_artifact.load_example_records()["transition_receipt"])
    transition["from_state"] = "security_review"
    transition["to_state"] = "blocked_security"
    transition["decision"] = "allowed"
    transition["blockers"] = []
    transition_path = tmp_path / "blocked-transition.json"
    transition_path.write_text(json.dumps(transition), encoding="utf-8")

    errors = validator.validate_transition_receipt(transition_path)

    assert "transition_receipt: blocked target state requires blocked decision" in errors
    assert "transition_receipt: allowed transition cannot target blocked state" in errors
    assert len(errors) >= 2


def test_transition_receipt_requires_receipt_ref_prefix(tmp_path: Path) -> None:
    transition = copy.deepcopy(validate_sdlc_artifact.load_example_records()["transition_receipt"])
    transition["required_receipt_refs"] = ["trace://not-a-receipt"]
    transition_path = tmp_path / "transition-bad-receipt-ref.json"
    transition_path.write_text(json.dumps(transition), encoding="utf-8")

    errors = validator.validate_transition_receipt(transition_path)

    assert "transition_receipt: required_receipt_refs must use receipt:// prefix" in errors
    assert len(errors) >= 1
    assert transition["required_receipt_refs"] == ["trace://not-a-receipt"]


def test_closure_must_retain_transition_receipt(tmp_path: Path) -> None:
    closure = copy.deepcopy(validate_sdlc_artifact.load_example_records()["closure_receipt"])
    transition_receipt_ref = validate_sdlc_artifact.load_example_records()["transition_receipt"]["receipt_ref"]
    closure["receipts"].remove(transition_receipt_ref)
    closure_path = tmp_path / "closure-missing-transition.json"
    closure_path.write_text(json.dumps(closure), encoding="utf-8")

    errors = validator.validate_closure_state(closure_path)

    assert "closure must retain transition receipt" in errors
    assert len(errors) >= 1
    assert transition_receipt_ref not in closure["receipts"]


def test_state_machine_cli_reports_passed() -> None:
    stdout_buffer = io.StringIO()

    with redirect_stdout(stdout_buffer):
        exit_code = validator.main([])

    output = stdout_buffer.getvalue()
    assert exit_code == 0
    assert "sdlc_state_machine_document" in output
    assert "sdlc_transition_receipt" in output
    assert "STATUS: passed" in output
