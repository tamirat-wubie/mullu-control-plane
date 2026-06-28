"""Tests for the Developer Workflow local sandbox proof report validator.

Purpose: prove the local proof runner report has a named schema and semantic
guardrails before the control tower reads it.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_developer_workflow_local_sandbox_proof_report.
Invariants: reports remain local, no-execution, no-external-effect summaries.
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from scripts.validate_developer_workflow_local_sandbox_proof_report import (
    DEFAULT_OUTPUT,
    validate_developer_workflow_local_sandbox_proof_report,
    write_developer_workflow_local_sandbox_proof_report_validation,
)


ROOT = Path(__file__).resolve().parents[1]


def _fixture() -> dict[str, object]:
    return json.loads(
        (ROOT / "examples" / "developer_workflow_local_sandbox_proof_report.foundation.json").read_text(
            encoding="utf-8"
        )
    )


def _write_payload(tmp_path: Path, payload: dict[str, object]) -> Path:
    path = tmp_path / "local-proof-report.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def test_local_sandbox_proof_report_fixture_validates_and_writes(tmp_path: Path) -> None:
    validation = validate_developer_workflow_local_sandbox_proof_report()
    output_path = tmp_path / "validation.json"
    written_path = write_developer_workflow_local_sandbox_proof_report_validation(validation, output_path)

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.bundle_status == "awaiting_receipts"
    assert validation.attachment_packet_status == "awaiting_attachments"
    assert validation.completed_count == 1
    assert validation.required_count == 4
    assert written_path == output_path
    assert DEFAULT_OUTPUT.name == "developer_workflow_local_sandbox_proof_report_validation.json"


def test_local_sandbox_proof_report_rejects_execution_and_external_overclaim(tmp_path: Path) -> None:
    payload = _fixture()
    payload["execution_performed"] = True
    payload["external_effects_allowed"] = True

    validation = validate_developer_workflow_local_sandbox_proof_report(report_path=_write_payload(tmp_path, payload))

    assert validation.ok is False
    errors = "\n".join(validation.errors)
    assert "execution_performed must be false" in errors
    assert "external_effects_allowed must be false" in errors


def test_local_sandbox_proof_report_rejects_status_count_drift(tmp_path: Path) -> None:
    payload = _fixture()
    payload["completed_count"] = 4
    payload["bundle_status"] = "awaiting_receipts"
    payload["attachment_packet_status"] = "awaiting_attachments"
    payload["next_attachment_id"] = "test_gate_receipt"

    validation = validate_developer_workflow_local_sandbox_proof_report(report_path=_write_payload(tmp_path, payload))

    assert validation.ok is False
    errors = "\n".join(validation.errors)
    assert "bundle_status must match completed receipt count" in errors
    assert "attachment_packet_status must match completed receipt count" in errors
    assert "next_attachment_id must be 'none' when attachments are complete" in errors


def test_local_sandbox_proof_report_rejects_url_and_artifact_drift(tmp_path: Path) -> None:
    payload = _fixture()
    payload["control_tower_url"] = "/operator/control-tower"
    artifacts = payload["generated_artifacts"]
    assert isinstance(artifacts, dict)
    artifacts["operator_receipt"] = "https://example.invalid/operator-receipt.json"

    validation = validate_developer_workflow_local_sandbox_proof_report(report_path=_write_payload(tmp_path, payload))

    assert validation.ok is False
    errors = "\n".join(validation.errors)
    assert "control_tower_url must include local sandbox receipt opt-in" in errors
    assert "generated_artifacts.operator_receipt must be workspace-local" in errors


def test_local_sandbox_proof_report_cli_writes_report(tmp_path: Path) -> None:
    output_path = tmp_path / "validation.json"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/validate_developer_workflow_local_sandbox_proof_report.py",
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
    assert payload["completed_count"] == 1
    assert output_path.exists()
