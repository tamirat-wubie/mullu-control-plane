"""Purpose: test governed code-change loop closure gates.
Governance scope: UAO-style refs, code-worker lease dispatch, SDLC receipt
    requirements, and non-terminal worker receipt boundaries.
Dependencies: pytest, governed_code_change_loop, and sandboxed code worker.
Invariants:
  - Successful worker execution does not imply terminal closure.
  - Missing SDLC receipts block closure with explicit reasons.
  - Worker policy denial remains blocked even when SDLC refs are present.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from mcoi_runtime.contracts.code_worker import CodeWorkerReceiptStatus
from mcoi_runtime.core.governed_code_change_loop import (
    GovernedCodeChangeRequest,
    build_code_worker_lease,
    run_governed_code_change_loop,
)
from mcoi_runtime.workers.code_worker import SandboxedCodeWorker


NOW = "2026-05-07T12:00:00+00:00"


def _request(**overrides: object) -> GovernedCodeChangeRequest:
    values = {
        "action_id": "change-loop-1",
        "tenant_id": "tenant-a",
        "actor_id": "operator-a",
        "repository": "repo-a",
        "commit_sha": "abc123",
        "command_id": "cmd-1",
        "argv": ("python", "-m", "task"),
        "cwd": "src",
        "allowed_paths": ("src",),
        "allowed_commands": (("python", "-m", "task"),),
        "expires_at": "2026-05-08T12:00:00+00:00",
    }
    values.update(overrides)
    return GovernedCodeChangeRequest(**values)


def _worker(tmp_path: Path, *, runner=None) -> SandboxedCodeWorker:
    (tmp_path / "src").mkdir(exist_ok=True)
    if runner is None:
        runner = _successful_runner(tmp_path)
    return SandboxedCodeWorker(
        workspace_root=str(tmp_path),
        clock=lambda: NOW,
        runner=runner,
        platform_system=lambda: "Linux",
    )


def _successful_runner(tmp_path: Path):
    def fake_runner(argv, **kwargs):  # noqa: ANN001, ANN202, ARG001
        (tmp_path / "src" / "result.txt").write_text("changed\n", encoding="utf-8")
        return subprocess.CompletedProcess(argv, 0, stdout="ok\n", stderr="")

    return fake_runner


def test_successful_code_worker_still_blocks_without_sdlc_receipts(tmp_path: Path) -> None:
    result = run_governed_code_change_loop(_request(), _worker(tmp_path))

    assert result.command_result.status is CodeWorkerReceiptStatus.SUCCEEDED
    assert result.closure_allowed is False
    assert result.solver_outcome == "AwaitingEvidence"
    assert result.missing_sdlc_receipt_kinds == (
        "implementation_receipt",
        "verification_receipt",
        "recovery_handoff",
    )
    assert "missing_sdlc_verification_receipt" in result.closure_blockers
    assert result.metadata["worker_receipt_not_terminal_closure"] is True


def test_all_required_sdlc_receipts_allow_terminal_closure_review(tmp_path: Path) -> None:
    result = run_governed_code_change_loop(
        _request(
            observed_sdlc_receipt_refs={
                "implementation_receipt": "receipt://sdlc/implementation/1",
                "verification_receipt": "receipt://sdlc/verification/1",
                "recovery_handoff": "receipt://sdlc/recovery/1",
            },
        ),
        _worker(tmp_path),
    )

    assert result.command_result.status is CodeWorkerReceiptStatus.SUCCEEDED
    assert result.closure_allowed is True
    assert result.solver_outcome == "SolvedVerified"
    assert result.missing_sdlc_receipt_kinds == ()
    assert result.closure_blockers == ()
    assert result.next_action == "prepare_terminal_closure_review"
    assert result.code_worker_receipt_ref.startswith("receipt://code-worker-receipt-")


def test_blocked_code_worker_denies_closure_even_with_sdlc_receipts(tmp_path: Path) -> None:
    dispatched = False

    def fake_runner(argv, **kwargs):  # noqa: ANN001, ANN202
        nonlocal dispatched
        dispatched = True
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    result = run_governed_code_change_loop(
        _request(
            argv=("bash", "src/task.sh"),
            allowed_commands=(("bash", "src/task.sh"),),
            observed_sdlc_receipt_refs={
                "implementation_receipt": "receipt://sdlc/implementation/1",
                "verification_receipt": "receipt://sdlc/verification/1",
                "recovery_handoff": "receipt://sdlc/recovery/1",
            },
        ),
        _worker(tmp_path, runner=fake_runner),
    )

    assert dispatched is False
    assert result.command_result.status is CodeWorkerReceiptStatus.BLOCKED
    assert result.closure_allowed is False
    assert result.solver_outcome == "GovernanceBlocked"
    assert result.next_action == "repair_or_reduce_code_worker_lease"
    assert result.closure_blockers == ("code_worker_status_blocked",)
    assert result.command_result.receipt.violation_reasons == ("denied_executable:bash",)


def test_code_worker_lease_binds_request_identity_and_uao_ref() -> None:
    lease = build_code_worker_lease(_request())

    assert lease.tenant_id == "tenant-a"
    assert lease.repository == "repo-a"
    assert lease.commit_sha == "abc123"
    assert lease.allowed_paths == ("src",)
    assert lease.allowed_commands == (("python", "-m", "task"),)
    assert lease.network_enabled is False
    assert lease.metadata["uao_ref"] == "uao://governed-code-change/change-loop-1"


def test_observed_sdlc_receipts_require_receipt_refs() -> None:
    with pytest.raises(ValueError, match="receipt:// refs"):
        _request(
            observed_sdlc_receipt_refs={
                "implementation_receipt": "sdlc/implementation/1",
            },
        )
