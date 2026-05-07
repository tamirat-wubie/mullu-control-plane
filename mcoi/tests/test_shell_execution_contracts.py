"""Purpose: verify shell execution receipt contract invariants.
Governance scope: shell observation evidence typing only.
Dependencies: pytest and shell execution receipt contracts.
Invariants: receipts bind command/output hashes, bounded argv summaries, and policy verdict evidence.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.execution import ExecutionOutcome
from mcoi_runtime.contracts.shell_execution import ShellExecutionReceipt


def _receipt(**overrides: object) -> ShellExecutionReceipt:
    defaults = {
        "receipt_id": "shell-receipt-1",
        "execution_id": "execution-1",
        "goal_id": "goal-1",
        "outcome": ExecutionOutcome.SUCCEEDED,
        "command_hash": "command-hash",
        "argv_summary": ("python", "-c", "print('ok')", "extra"),
        "stdout_hash": "stdout-hash",
        "stderr_hash": "stderr-hash",
        "output_truncated": False,
        "started_at": "2026-03-18T12:00:00+00:00",
        "finished_at": "2026-03-18T12:00:01+00:00",
        "evidence_ref": "shell-receipt:execution-1:abc",
        "returncode": 0,
        "environment_keys": ("PATH", "HOME"),
    }
    defaults.update(overrides)
    return ShellExecutionReceipt(**defaults)


def test_shell_execution_receipt_bounds_audit_surface() -> None:
    receipt = _receipt(environment_keys=("ZED", "PATH"))

    assert receipt.argv_summary == ("python", "-c", "print('ok')")
    assert receipt.environment_keys == ("PATH", "ZED")
    assert receipt.outcome is ExecutionOutcome.SUCCEEDED
    assert receipt.returncode == 0


def test_shell_execution_receipt_rejects_missing_evidence_identity() -> None:
    with pytest.raises(ValueError, match="^evidence_ref must be a non-empty string$") as exc_info:
        _receipt(evidence_ref="")

    message = str(exc_info.value)
    assert "evidence_ref" in message
    assert "shell-receipt:execution-1:abc" not in message
    assert "non-empty" in message


def test_shell_execution_receipt_rejects_invalid_timeout() -> None:
    with pytest.raises(ValueError, match="^timeout_seconds must be greater than zero when provided$"):
        _receipt(timeout_seconds=0)

    valid = _receipt(timeout_seconds=1.5, policy_id="policy-1", policy_verdict="allow")
    assert valid.timeout_seconds == 1.5
    assert valid.policy_id == "policy-1"
    assert valid.policy_verdict == "allow"
