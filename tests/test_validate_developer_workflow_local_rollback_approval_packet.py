"""Tests for Developer Workflow local rollback approval packet validation.

Purpose: prove rollback approval packets fail closed on missing evidence,
unknown artifacts, drift, and execution overclaims.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_developer_workflow_local_rollback_approval_packet.
Invariants: approval packets are local-only and rollback-summary bound.
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from scripts.validate_developer_workflow_local_rollback_approval_packet import (
    DEFAULT_OUTPUT,
    validate_developer_workflow_local_rollback_approval_packet,
    write_developer_workflow_local_rollback_approval_packet_validation,
)


ROOT = Path(__file__).resolve().parents[1]


def _fixture() -> dict[str, object]:
    return json.loads(
        (ROOT / "examples" / "developer_workflow_local_rollback_approval_packet.foundation.json").read_text(
            encoding="utf-8"
        )
    )


def _approved_fixture() -> dict[str, object]:
    packet = _fixture()
    packet["packet_status"] = "approval_recorded"
    packet["approval_status"] = "approved"
    packet["approval_scope"] = "selected_artifacts"
    packet["delete_execution_allowed"] = True
    packet["selected_artifact_count"] = 1
    packet["selected_artifact_ids"] = ["operator_receipt"]
    packet["operator_approval"] = {
        "approval_status": "approved",
        "approved_by": "operator",
        "approved_at": "2026-05-01T12:00:00+00:00",
        "approval_evidence_ref": "approval://local/rollback/operator-receipt",
        "approval_note": "Approve deletion of generated operator receipt artifact only.",
    }
    packet["authorized_artifacts"] = [
        {
            "artifact_id": "operator_receipt",
            "path": ".change_assurance/developer_workflow_operator_receipt.generated.json",
            "rollback_command": (
                "Remove-Item -LiteralPath "
                "'.change_assurance/developer_workflow_operator_receipt.generated.json' -Force"
            ),
            "approval_status": "approved",
            "execution_allowed": True,
            "required_confirmation": True,
        }
    ]
    return packet


def _write_payload(tmp_path: Path, payload: dict[str, object]) -> Path:
    packet_path = tmp_path / "rollback-approval.json"
    packet_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return packet_path


def test_rollback_approval_fixture_validates_and_writes(tmp_path: Path) -> None:
    validation = validate_developer_workflow_local_rollback_approval_packet()
    output_path = tmp_path / "rollback-approval-validation.json"

    written_path = write_developer_workflow_local_rollback_approval_packet_validation(validation, output_path)
    written_payload = json.loads(written_path.read_text(encoding="utf-8"))

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.packet_status == "awaiting_operator_approval"
    assert validation.approval_status == "pending"
    assert validation.selected_artifact_count == 0
    assert validation.delete_execution_allowed is False
    assert written_payload["errors"] == []
    assert DEFAULT_OUTPUT.name == "developer_workflow_local_rollback_approval_packet_validation.json"


def test_rollback_approval_rejects_approved_missing_evidence(tmp_path: Path) -> None:
    packet = _approved_fixture()
    operator_approval = packet["operator_approval"]
    assert isinstance(operator_approval, dict)
    operator_approval["approved_by"] = ""
    operator_approval["approval_evidence_ref"] = ""

    validation = validate_developer_workflow_local_rollback_approval_packet(
        packet_path=_write_payload(tmp_path, packet)
    )
    errors = "\n".join(validation.errors)

    assert validation.ok is False
    assert "approved rollback approval requires approved_by" in errors
    assert "approved rollback approval requires approval_evidence_ref" in errors


def test_rollback_approval_rejects_unknown_selected_artifact(tmp_path: Path) -> None:
    packet = _approved_fixture()
    packet["selected_artifact_ids"] = ["missing_artifact"]
    packet["authorized_artifacts"] = [
        {
            "artifact_id": "missing_artifact",
            "path": ".change_assurance/missing.json",
            "rollback_command": "Remove-Item -LiteralPath '.change_assurance/missing.json' -Force",
            "approval_status": "approved",
            "execution_allowed": True,
            "required_confirmation": True,
        }
    ]

    validation = validate_developer_workflow_local_rollback_approval_packet(
        packet_path=_write_payload(tmp_path, packet)
    )
    errors = "\n".join(validation.errors)

    assert validation.ok is False
    assert "selected artifact missing_artifact is not present in rollback summary" in errors
    assert "authorized artifact missing_artifact is not present in rollback summary" in errors


def test_rollback_approval_rejects_command_and_status_drift(tmp_path: Path) -> None:
    packet = _approved_fixture()
    artifacts = packet["authorized_artifacts"]
    assert isinstance(artifacts, list)
    artifacts[0]["path"] = ".change_assurance/other.json"  # type: ignore[index]
    artifacts[0]["rollback_command"] = "Remove-Item -LiteralPath '.change_assurance/other.json' -Force"  # type: ignore[index]
    artifacts[0]["approval_status"] = "pending"  # type: ignore[index]
    artifacts[0]["execution_allowed"] = False  # type: ignore[index]
    artifacts[0]["required_confirmation"] = False  # type: ignore[index]

    validation = validate_developer_workflow_local_rollback_approval_packet(
        packet_path=_write_payload(tmp_path, packet)
    )
    errors = "\n".join(validation.errors)

    assert validation.ok is False
    assert "path must match rollback summary" in errors
    assert "rollback_command must match rollback summary" in errors
    assert "approval_status must match packet" in errors
    assert "execution_allowed must match approval state" in errors
    assert "required_confirmation must be true" in errors


def test_rollback_approval_rejects_pending_execution_overclaim(tmp_path: Path) -> None:
    packet = _fixture()
    packet["delete_execution_allowed"] = True
    packet["external_effects_allowed"] = True
    packet["rollback_execution_performed"] = True

    validation = validate_developer_workflow_local_rollback_approval_packet(
        packet_path=_write_payload(tmp_path, packet)
    )
    errors = "\n".join(validation.errors)

    assert validation.ok is False
    assert "external_effects_allowed must be false" in errors
    assert "rollback_execution_performed must be false" in errors
    assert "delete_execution_allowed must match approval state and selection" in errors


def test_rollback_approval_cli_writes_report(tmp_path: Path) -> None:
    output_path = tmp_path / "rollback-approval-validation.json"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/validate_developer_workflow_local_rollback_approval_packet.py",
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
    assert payload["approval_status"] == "pending"
    assert output_path.exists()
