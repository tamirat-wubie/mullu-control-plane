"""Purpose: test governed code-change loop receipt validation.
Governance scope: non-terminal receipt flags, worker receipt binding, SDLC
    closure blockers, sample request fixture, and tamper rejection.
Dependencies: scripts.run_governed_code_change_loop and receipt validator.
Invariants:
  - Blocked evidence receipts can validate without claiming closure.
  - Closure-ready mode requires all SDLC refs and no blockers.
  - Tampered receipt boundaries fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import run_governed_code_change_loop
from scripts.validate_governed_code_change_loop_receipt import (
    validate_governed_code_change_loop_receipt,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_REQUEST = REPO_ROOT / "examples" / "governed_code_change_loop.blocked_request.json"


def test_sample_blocked_receipt_validates_without_closure_claim(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "src").mkdir(parents=True)
    receipt_path = tmp_path / "governed-code-change-receipt.json"

    result = run_governed_code_change_loop.run_from_file(
        request_path=SAMPLE_REQUEST,
        output_path=receipt_path,
        workspace_root=workspace,
    )
    validation = validate_governed_code_change_loop_receipt(receipt_path)
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))

    assert result.closure_allowed is False
    assert validation.valid is True
    assert validation.blockers == ()
    assert validation.closure_allowed is False
    assert payload["receipt_is_not_terminal_closure"] is True
    assert payload["terminal_closure_required"] is True
    assert payload["solver_outcome"] == "GovernanceBlocked"
    assert "code_worker_status_blocked" in payload["closure_blockers"]
    assert "missing_sdlc_implementation_receipt" in payload["closure_blockers"]


def test_require_closure_ready_rejects_blocked_receipt(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "src").mkdir(parents=True)
    receipt_path = tmp_path / "governed-code-change-receipt.json"
    run_governed_code_change_loop.run_from_file(
        request_path=SAMPLE_REQUEST,
        output_path=receipt_path,
        workspace_root=workspace,
    )

    validation = validate_governed_code_change_loop_receipt(
        receipt_path,
        require_closure_ready=True,
    )

    assert validation.valid is False
    assert validation.blockers == ("governed_code_change_loop_receipt_invalid",)
    assert "closure_ready_required" in validation.detail


def test_require_sandbox_execution_rejects_blocked_receipt(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "src").mkdir(parents=True)
    receipt_path = tmp_path / "governed-code-change-receipt.json"
    run_governed_code_change_loop.run_from_file(
        request_path=SAMPLE_REQUEST,
        output_path=receipt_path,
        workspace_root=workspace,
    )

    validation = validate_governed_code_change_loop_receipt(
        receipt_path,
        require_sandbox_execution=True,
    )

    assert validation.valid is False
    assert validation.blockers == ("governed_code_change_loop_receipt_invalid",)
    assert "sandbox_execution_required_status_not_succeeded" in validation.detail
    assert "sandbox_execution_required_verification_not_passed" in validation.detail


def test_require_sandbox_execution_accepts_sandbox_passed_receipt(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "src").mkdir(parents=True)
    receipt_path = tmp_path / "governed-code-change-receipt.json"
    request_path = tmp_path / "request.json"
    sample = json.loads(SAMPLE_REQUEST.read_text(encoding="utf-8"))
    sample["argv"] = ["python", "-m", "task"]
    sample["allowed_commands"] = [["python", "-m", "task"]]
    sample["observed_sdlc_receipt_refs"] = {
        "implementation_receipt": "receipt://sdlc/implementation/1",
        "verification_receipt": "receipt://sdlc/verification/1",
        "recovery_handoff": "receipt://sdlc/recovery/1",
    }
    request_path.write_text(json.dumps(sample), encoding="utf-8")

    run_governed_code_change_loop.run_from_file(
        request_path=request_path,
        output_path=receipt_path,
        workspace_root=workspace,
        runner=lambda argv, **kwargs: __import__("subprocess").CompletedProcess(
            argv,
            0,
            stdout="ok\n",
            stderr="",
        ),
        platform_system=lambda: "Linux",
    )

    validation = validate_governed_code_change_loop_receipt(
        receipt_path,
        require_closure_ready=True,
        require_sandbox_execution=True,
    )

    assert validation.valid is True
    assert validation.blockers == ()
    assert validation.closure_allowed is True
    assert validation.solver_outcome == "SolvedVerified"


def test_tampered_worker_receipt_ref_is_rejected(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "src").mkdir(parents=True)
    receipt_path = tmp_path / "governed-code-change-receipt.json"
    run_governed_code_change_loop.run_from_file(
        request_path=SAMPLE_REQUEST,
        output_path=receipt_path,
        workspace_root=workspace,
    )
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    payload["code_worker_receipt_ref"] = "receipt://code-worker-receipt-tampered"
    receipt_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    validation = validate_governed_code_change_loop_receipt(receipt_path)

    assert validation.valid is False
    assert "code_worker_receipt_ref_mismatch" in validation.detail


def test_closure_ready_receipt_requires_solved_verified(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "src").mkdir(parents=True)
    receipt_path = tmp_path / "governed-code-change-receipt.json"
    request_path = tmp_path / "request.json"
    sample = json.loads(SAMPLE_REQUEST.read_text(encoding="utf-8"))
    sample["argv"] = ["python", "-m", "task"]
    sample["allowed_commands"] = [["python", "-m", "task"]]
    sample["observed_sdlc_receipt_refs"] = {
        "implementation_receipt": "receipt://sdlc/implementation/1",
        "verification_receipt": "receipt://sdlc/verification/1",
        "recovery_handoff": "receipt://sdlc/recovery/1",
    }
    request_path.write_text(json.dumps(sample), encoding="utf-8")

    run_governed_code_change_loop.run_from_file(
        request_path=request_path,
        output_path=receipt_path,
        workspace_root=workspace,
        runner=lambda argv, **kwargs: __import__("subprocess").CompletedProcess(
            argv,
            0,
            stdout="ok\n",
            stderr="",
        ),
        platform_system=lambda: "Linux",
    )
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    payload["solver_outcome"] = "SolvedUnverified"
    receipt_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    validation = validate_governed_code_change_loop_receipt(
        receipt_path,
        require_closure_ready=True,
    )

    assert validation.valid is False
    assert "closure_ready_requires_solved_verified" in validation.detail


def test_receipt_validator_rejects_non_string_closure_blocker(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "src").mkdir(parents=True)
    receipt_path = tmp_path / "governed-code-change-receipt.json"
    run_governed_code_change_loop.run_from_file(
        request_path=SAMPLE_REQUEST,
        output_path=receipt_path,
        workspace_root=workspace,
    )
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    payload["closure_blockers"] = ["code_worker_status_blocked", 7]
    receipt_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    validation = validate_governed_code_change_loop_receipt(receipt_path)

    assert validation.valid is False
    assert "closure_blockers_not_string_list" in validation.detail


def test_receipt_validator_rejects_duplicate_required_receipt_kind(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "src").mkdir(parents=True)
    receipt_path = tmp_path / "governed-code-change-receipt.json"
    run_governed_code_change_loop.run_from_file(
        request_path=SAMPLE_REQUEST,
        output_path=receipt_path,
        workspace_root=workspace,
    )
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    payload["required_sdlc_receipt_kinds"].append("implementation_receipt")
    receipt_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    validation = validate_governed_code_change_loop_receipt(receipt_path)

    assert validation.valid is False
    assert "required_sdlc_receipt_kinds_duplicate" in validation.detail
