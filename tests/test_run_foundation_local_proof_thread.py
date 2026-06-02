"""Tests for the Foundation Mode local proof-thread runner.

Purpose: prove the first local proof-thread runner emits bounded local result
and receipt evidence without external effects.
Governance scope: Foundation Mode, local-only execution, approval gate, receipt
evidence, rollback note, and no deployment/customer exposure.
Dependencies: scripts.run_foundation_local_proof_thread.
Invariants: runner output is local, approval-gated, rollback-named, and rejects
network, credential, money, message, DNS, deployment, or customer-access flags.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.run_foundation_local_proof_thread import (  # noqa: E402
    DEFAULT_APPROVAL_REF,
    run_foundation_local_proof_thread,
    validate_local_proof_run_receipt,
)


FIXED_NOW = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)


def test_runner_writes_local_result_and_receipt(tmp_path: Path) -> None:
    result_output = tmp_path / "foundation_local_result.json"
    receipt_output = tmp_path / "foundation_local_receipt.json"

    run = run_foundation_local_proof_thread(
        result_output=result_output,
        receipt_output=receipt_output,
        now_utc=FIXED_NOW,
    )

    result = json.loads(result_output.read_text(encoding="utf-8"))
    receipt = json.loads(receipt_output.read_text(encoding="utf-8"))
    assert run.result == result
    assert run.receipt == receipt
    assert receipt["status"] == "passed"
    assert receipt["proof_state"] == "Pass"
    assert receipt["approval_ref"] == DEFAULT_APPROVAL_REF
    assert receipt["verification"]["approval_before_local_result"] is True
    assert receipt["rollback"]["safe_to_delete"] is True
    assert all(value is False for value in receipt["external_effects"].values())


def test_runner_dry_run_does_not_write(tmp_path: Path) -> None:
    result_output = tmp_path / "result.json"
    receipt_output = tmp_path / "receipt.json"

    run = run_foundation_local_proof_thread(
        result_output=result_output,
        receipt_output=receipt_output,
        now_utc=FIXED_NOW,
        dry_run=True,
    )

    assert run.receipt["status"] == "passed"
    assert run.result["result_type"] == "foundation_local_proof_thread_result"
    assert not result_output.exists()
    assert not receipt_output.exists()


def test_receipt_validator_rejects_external_effect_flag() -> None:
    run = run_foundation_local_proof_thread(now_utc=FIXED_NOW, dry_run=True)
    candidate_receipt = deepcopy(run.receipt)
    candidate_receipt["external_effects"]["network_used"] = True

    errors = validate_local_proof_run_receipt(receipt=candidate_receipt, result=run.result)

    assert errors
    assert "external_effects.network_used must be false" in errors


def test_receipt_validator_rejects_missing_rollback_safety() -> None:
    run = run_foundation_local_proof_thread(now_utc=FIXED_NOW, dry_run=True)
    candidate_receipt = deepcopy(run.receipt)
    candidate_receipt["rollback"]["safe_to_delete"] = False

    errors = validate_local_proof_run_receipt(receipt=candidate_receipt, result=run.result)

    assert errors
    assert "rollback.safe_to_delete must be true" in errors
