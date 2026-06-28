"""Tests for Developer Workflow local rollback summary packet building.

Purpose: prove rollback summaries are projected from local proof reports
without executing rollback or granting external effects.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.build_developer_workflow_local_rollback_summary_packet.
Invariants: builder output is deterministic, local-only, and confirmation-bound.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.build_developer_workflow_local_rollback_summary_packet import (
    build_developer_workflow_local_rollback_summary_packet,
    main,
    write_developer_workflow_local_rollback_summary_packet,
)
from scripts.validate_developer_workflow_local_rollback_summary_packet import (
    validate_developer_workflow_local_rollback_summary_packet,
)


ROOT = Path(__file__).resolve().parents[1]


def _fixture() -> dict[str, object]:
    return json.loads(
        (ROOT / "examples" / "developer_workflow_local_sandbox_proof_report.foundation.json").read_text(
            encoding="utf-8"
        )
    )


def test_rollback_summary_builder_projects_fixture_artifacts(tmp_path: Path) -> None:
    proof_report_path = ROOT / "examples" / "developer_workflow_local_sandbox_proof_report.foundation.json"

    packet = build_developer_workflow_local_rollback_summary_packet(
        local_sandbox_proof_report=_fixture(),
        local_sandbox_proof_report_path=proof_report_path,
    )
    packet_path = write_developer_workflow_local_rollback_summary_packet(packet, tmp_path / "rollback.json")
    validation = validate_developer_workflow_local_rollback_summary_packet(
        packet_path=packet_path,
        proof_report_path=proof_report_path,
    )

    assert validation.ok is True
    assert packet["packet_status"] == "rollback_ready"
    assert packet["external_effects_allowed"] is False
    assert packet["rollback_execution_performed"] is False
    assert packet["generated_artifact_count"] == 10
    assert len(packet["artifacts"]) == 10  # type: ignore[arg-type]
    assert packet["rollback_command_preview"][0].startswith("Remove-Item -LiteralPath")  # type: ignore[index]
    assert all(item["required_confirmation"] is True for item in packet["artifacts"])  # type: ignore[index]


def test_rollback_summary_builder_handles_empty_artifact_report(tmp_path: Path) -> None:
    proof_report = _fixture()
    proof_report["generated_artifacts"] = {}
    proof_report_path = tmp_path / "proof-report.json"
    proof_report_path.write_text(json.dumps(proof_report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    packet = build_developer_workflow_local_rollback_summary_packet(
        local_sandbox_proof_report=proof_report,
        local_sandbox_proof_report_path=proof_report_path,
    )

    assert packet["packet_status"] == "rollback_unavailable"
    assert packet["generated_artifact_count"] == 0
    assert packet["artifacts"] == []
    assert packet["rollback_command_preview"] == []
    assert packet["rollback_execution_performed"] is False


def test_rollback_summary_builder_cli_writes_json(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "rollback-summary.json"

    exit_code = main(["--output", str(output_path), "--json"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert output_path.exists()
    assert "developer_workflow_local_rollback_summary_packet.v1" in captured.out
