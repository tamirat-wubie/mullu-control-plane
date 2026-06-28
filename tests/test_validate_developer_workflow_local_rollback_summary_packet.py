"""Tests for Developer Workflow local rollback summary packet validation.

Purpose: prove rollback summaries fail closed on external effects, execution
overclaims, artifact drift, command drift, and missing confirmation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_developer_workflow_local_rollback_summary_packet.
Invariants: rollback summary packets are projection-only and proof-report bound.
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from scripts.validate_developer_workflow_local_rollback_summary_packet import (
    DEFAULT_OUTPUT,
    validate_developer_workflow_local_rollback_summary_packet,
    write_developer_workflow_local_rollback_summary_packet_validation,
)


ROOT = Path(__file__).resolve().parents[1]


def _fixture() -> dict[str, object]:
    return json.loads(
        (ROOT / "examples" / "developer_workflow_local_rollback_summary_packet.foundation.json").read_text(
            encoding="utf-8"
        )
    )


def _write_payload(tmp_path: Path, payload: dict[str, object]) -> Path:
    packet_path = tmp_path / "rollback-summary.json"
    packet_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return packet_path


def test_rollback_summary_fixture_validates_and_writes(tmp_path: Path) -> None:
    validation = validate_developer_workflow_local_rollback_summary_packet()
    output_path = tmp_path / "rollback-summary-validation.json"

    written_path = write_developer_workflow_local_rollback_summary_packet_validation(validation, output_path)
    written_payload = json.loads(written_path.read_text(encoding="utf-8"))

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.packet_status == "rollback_ready"
    assert validation.generated_artifact_count == 10
    assert validation.rollback_execution_performed is False
    assert written_payload["errors"] == []
    assert DEFAULT_OUTPUT.name == "developer_workflow_local_rollback_summary_packet_validation.json"


def test_rollback_summary_rejects_execution_and_external_overclaim(tmp_path: Path) -> None:
    packet = _fixture()
    packet["external_effects_allowed"] = True
    packet["rollback_execution_performed"] = True
    packet["execution_boundary"] = "production"

    validation = validate_developer_workflow_local_rollback_summary_packet(packet_path=_write_payload(tmp_path, packet))
    errors = "\n".join(validation.errors)

    assert validation.ok is False
    assert "external_effects_allowed must be false" in errors
    assert "rollback_execution_performed must be false" in errors
    assert "execution_boundary must be local_lab_only" in errors


def test_rollback_summary_rejects_artifact_path_drift(tmp_path: Path) -> None:
    packet = _fixture()
    artifacts = packet["artifacts"]
    assert isinstance(artifacts, list)
    artifacts[0]["path"] = "https://example.invalid/generated.json"  # type: ignore[index]

    validation = validate_developer_workflow_local_rollback_summary_packet(packet_path=_write_payload(tmp_path, packet))
    errors = "\n".join(validation.errors)

    assert validation.ok is False
    assert "path must match proof report" in errors
    assert "path must be workspace-local" in errors
    assert "artifact ids must match proof report generated_artifacts" in errors


def test_rollback_summary_rejects_command_and_confirmation_drift(tmp_path: Path) -> None:
    packet = _fixture()
    artifacts = packet["artifacts"]
    assert isinstance(artifacts, list)
    artifacts[0]["rollback_command"] = "Remove-Item -LiteralPath 'other.json' -Force"  # type: ignore[index]
    artifacts[0]["required_confirmation"] = False  # type: ignore[index]
    packet["rollback_command_preview"] = []

    validation = validate_developer_workflow_local_rollback_summary_packet(packet_path=_write_payload(tmp_path, packet))
    errors = "\n".join(validation.errors)

    assert validation.ok is False
    assert "required_confirmation must be true" in errors
    assert "rollback_command must match path preview" in errors
    assert "rollback_command_preview must match artifact rollback commands" in errors


def test_rollback_summary_cli_writes_report(tmp_path: Path) -> None:
    output_path = tmp_path / "rollback-summary-validation.json"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/validate_developer_workflow_local_rollback_summary_packet.py",
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
    assert payload["generated_artifact_count"] == 10
    assert output_path.exists()
