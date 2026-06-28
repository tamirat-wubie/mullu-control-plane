"""Tests for Developer Workflow local rollback execution receipt validation.

Purpose: prove execution receipts fail closed on execution overclaim, count
drift, and missing boundary evidence.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_developer_workflow_local_rollback_execution_receipt.
Invariants: execution claims must match artifact outcome rows.
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from scripts.validate_developer_workflow_local_rollback_execution_receipt import (
    DEFAULT_OUTPUT,
    validate_developer_workflow_local_rollback_execution_receipt,
    write_developer_workflow_local_rollback_execution_receipt_validation,
)


ROOT = Path(__file__).resolve().parents[1]


def _fixture() -> dict[str, object]:
    return json.loads(
        (ROOT / "examples" / "developer_workflow_local_rollback_execution_receipt.foundation.json").read_text(
            encoding="utf-8"
        )
    )


def _write_payload(tmp_path: Path, payload: dict[str, object]) -> Path:
    receipt_path = tmp_path / "rollback-execution-receipt.json"
    receipt_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt_path


def test_rollback_execution_receipt_fixture_validates_and_writes(tmp_path: Path) -> None:
    validation = validate_developer_workflow_local_rollback_execution_receipt()
    output_path = tmp_path / "rollback-execution-validation.json"

    written_path = write_developer_workflow_local_rollback_execution_receipt_validation(validation, output_path)
    written_payload = json.loads(written_path.read_text(encoding="utf-8"))

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.execution_status == "blocked_no_approval"
    assert validation.execution_mode == "dry_run"
    assert validation.executed_artifact_count == 0
    assert written_payload["errors"] == []
    assert DEFAULT_OUTPUT.name == "developer_workflow_local_rollback_execution_receipt_validation.json"


def test_rollback_execution_receipt_rejects_execution_overclaim(tmp_path: Path) -> None:
    receipt = _fixture()
    receipt["rollback_execution_performed"] = True
    receipt["execution_mode"] = "dry_run"
    receipt["execution_status"] = "rollback_executed"

    validation = validate_developer_workflow_local_rollback_execution_receipt(
        receipt_path=_write_payload(tmp_path, receipt)
    )
    errors = "\n".join(validation.errors)

    assert validation.ok is False
    assert "rollback_execution_performed requires execute mode" in errors
    assert "rollback_execution_performed requires approved deletion authority" in errors
    assert "execution_status must match observed artifact outcomes" in errors


def test_rollback_execution_receipt_rejects_count_and_boundary_drift(tmp_path: Path) -> None:
    receipt = _fixture()
    receipt["approval_status"] = "approved"
    receipt["delete_execution_allowed"] = True
    receipt["selected_artifact_count"] = 1
    receipt["executed_artifact_count"] = 1
    receipt["execution_status"] = "rollback_executed"
    receipt["execution_mode"] = "execute"
    receipt["artifacts"] = [
        {
            "artifact_id": "generated",
            "path": "generated.json",
            "resolved_path": "C:/outside/generated.json",
            "rollback_command": "Remove-Item -LiteralPath 'generated.json' -Force",
            "approval_status": "approved",
            "execution_allowed": True,
            "required_confirmation": True,
            "path_within_workspace": False,
            "pre_exists": True,
            "post_exists": True,
            "action_status": "deleted",
            "error_message": "",
        }
    ]

    validation = validate_developer_workflow_local_rollback_execution_receipt(
        receipt_path=_write_payload(tmp_path, receipt)
    )
    errors = "\n".join(validation.errors)

    assert validation.ok is False
    assert "outside workspace must be blocked or skipped" in errors
    assert "deleted row must have post_exists false" in errors


def test_rollback_execution_receipt_cli_writes_report(tmp_path: Path) -> None:
    output_path = tmp_path / "rollback-execution-validation.json"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/validate_developer_workflow_local_rollback_execution_receipt.py",
            "--output",
            str(output_path),
            "--json",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert result.returncode == 0
    assert payload["ok"] is True
    assert payload["execution_status"] == "blocked_no_approval"
    assert output_path.exists()
