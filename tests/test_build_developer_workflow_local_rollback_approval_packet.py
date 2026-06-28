"""Tests for Developer Workflow local rollback approval packet building.

Purpose: prove rollback approval packets are derived from rollback summaries
without executing rollback or granting external effects.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.build_developer_workflow_local_rollback_approval_packet.
Invariants: builder output is deterministic, local-only, and evidence-bound.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.build_developer_workflow_local_rollback_approval_packet import (
    build_developer_workflow_local_rollback_approval_packet,
    main,
    write_developer_workflow_local_rollback_approval_packet,
)
from scripts.validate_developer_workflow_local_rollback_approval_packet import (
    validate_developer_workflow_local_rollback_approval_packet,
)


ROOT = Path(__file__).resolve().parents[1]


def _summary_fixture() -> dict[str, object]:
    return json.loads(
        (ROOT / "examples" / "developer_workflow_local_rollback_summary_packet.foundation.json").read_text(
            encoding="utf-8"
        )
    )


def test_rollback_approval_builder_defaults_to_pending_without_execution(tmp_path: Path) -> None:
    rollback_summary_path = ROOT / "examples" / "developer_workflow_local_rollback_summary_packet.foundation.json"

    packet = build_developer_workflow_local_rollback_approval_packet(
        local_rollback_summary_packet=_summary_fixture(),
        local_rollback_summary_packet_path=rollback_summary_path,
    )
    packet_path = write_developer_workflow_local_rollback_approval_packet(packet, tmp_path / "approval.json")
    validation = validate_developer_workflow_local_rollback_approval_packet(
        packet_path=packet_path,
        rollback_summary_path=rollback_summary_path,
    )

    assert validation.ok is True
    assert packet["packet_status"] == "awaiting_operator_approval"
    assert packet["approval_status"] == "pending"
    assert packet["approval_scope"] == "none"
    assert packet["selected_artifact_count"] == 0
    assert packet["delete_execution_allowed"] is False
    assert packet["rollback_execution_performed"] is False
    assert packet["authorized_artifacts"] == []


def test_rollback_approval_builder_records_approved_selected_artifact(tmp_path: Path) -> None:
    rollback_summary_path = ROOT / "examples" / "developer_workflow_local_rollback_summary_packet.foundation.json"

    packet = build_developer_workflow_local_rollback_approval_packet(
        local_rollback_summary_packet=_summary_fixture(),
        local_rollback_summary_packet_path=rollback_summary_path,
        approval_status="approved",
        selected_artifact_ids=("operator_receipt",),
        approved_by="operator",
        approved_at="2026-05-01T12:00:00+00:00",
        approval_evidence_ref="approval://local/rollback/operator-receipt",
        approval_note="Approve deletion of generated operator receipt artifact only.",
    )
    packet_path = write_developer_workflow_local_rollback_approval_packet(packet, tmp_path / "approval.json")
    validation = validate_developer_workflow_local_rollback_approval_packet(
        packet_path=packet_path,
        rollback_summary_path=rollback_summary_path,
    )

    assert validation.ok is True
    assert packet["packet_status"] == "approval_recorded"
    assert packet["approval_status"] == "approved"
    assert packet["approval_scope"] == "selected_artifacts"
    assert packet["selected_artifact_count"] == 1
    assert packet["selected_artifact_ids"] == ["operator_receipt"]
    assert packet["delete_execution_allowed"] is True
    assert packet["authorized_artifacts"][0]["execution_allowed"] is True  # type: ignore[index]
    assert packet["authorized_artifacts"][0]["required_confirmation"] is True  # type: ignore[index]


def test_rollback_approval_builder_cli_writes_json(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "rollback-approval.json"

    exit_code = main(["--output", str(output_path), "--json"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert output_path.exists()
    assert "developer_workflow_local_rollback_approval_packet.v1" in captured.out
