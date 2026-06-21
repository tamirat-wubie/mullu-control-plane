"""Tests for Personal Assistant dry-run packet collection.

Purpose: prove the dry-run packet collector emits deterministic no-effect
workflow evidence without connector payloads or execution authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.collect_personal_assistant_dry_run_packet.
Invariants:
  - Packet collection is digest-only and local.
  - Stage topology is acyclic and approval-gated before P4/P5 paths.
  - Closure never grants live connector, memory, deployment, or customer readiness authority.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.collect_personal_assistant_dry_run_packet import (  # noqa: E402
    collect_personal_assistant_dry_run_packet,
    main,
    write_personal_assistant_dry_run_packet,
)

FIXED_NOW = datetime(2026, 6, 20, 9, 45, tzinfo=UTC)


def test_collect_dry_run_packet_closes_no_effect_workflow() -> None:
    packet = collect_personal_assistant_dry_run_packet(now_utc=FIXED_NOW)
    summary = packet["closure_summary"]

    assert packet["solver_outcome"] == "SolvedVerified"
    assert summary["dry_run_packet_closed"] is True  # type: ignore[index]
    assert summary["source_artifact_count"] == 11  # type: ignore[index]
    assert summary["stage_count"] == 12  # type: ignore[index]
    assert summary["no_effect_boundaries_clear"] is True  # type: ignore[index]
    assert summary["calendar_conflict_checked"] is True  # type: ignore[index]
    assert summary["task_intake_projected"] is True  # type: ignore[index]


def test_collect_dry_run_packet_records_approval_before_external_send() -> None:
    packet = collect_personal_assistant_dry_run_packet(now_utc=FIXED_NOW)
    stages = {stage["stage_id"]: stage for stage in packet["stages"]}  # type: ignore[index]

    assert stages["approval_gate_external_send"]["stage_type"] == "approval_gate"
    assert stages["approval_gate_external_send"]["approval_required"] is True
    assert stages["blocked_external_send"]["predecessor_ids"] == ["approval_gate_external_send"]
    assert stages["blocked_external_send"]["outcome"] == "AwaitingEvidence"
    assert "email_not_sent" in stages["blocked_external_send"]["actions_not_taken"]


def test_collect_dry_run_packet_records_calendar_task_and_memory_proofs() -> None:
    packet = collect_personal_assistant_dry_run_packet(now_utc=FIXED_NOW)
    stages = {stage["stage_id"]: stage for stage in packet["stages"]}  # type: ignore[index]
    summary = packet["closure_summary"]

    assert stages["calendar_conflict_reasoning"]["predecessor_ids"] == ["read_only_preview"]
    assert stages["calendar_conflict_reasoning"]["execution_allowed"] is False
    assert "calendar_not_written" in stages["calendar_conflict_reasoning"]["actions_not_taken"]
    assert stages["task_intake_projection"]["predecessor_ids"] == ["calendar_conflict_reasoning"]
    assert "task_not_written" in stages["task_intake_projection"]["actions_not_taken"]
    assert summary["draft_response_projected"] is True  # type: ignore[index]
    assert summary["approval_request_projected"] is True  # type: ignore[index]
    assert summary["no_send_proven"] is True  # type: ignore[index]
    assert summary["memory_admission_candidate_reviewed"] is True  # type: ignore[index]


def test_collect_dry_run_packet_uses_digest_only_source_artifacts() -> None:
    packet = collect_personal_assistant_dry_run_packet(now_utc=FIXED_NOW)
    source_artifacts = packet["source_artifacts"]
    source_kinds = {record["source_kind"] for record in source_artifacts}  # type: ignore[index]

    assert "skill_registry" in source_kinds
    assert "calendar_request" in source_kinds
    assert "planning_projection" in source_kinds
    assert "runtime_boundary" in source_kinds
    assert "foundation_closure_packet" not in source_kinds
    assert all(record["payload_digest_only"] is True for record in source_artifacts)  # type: ignore[index]
    assert all(record["source_sha256"] for record in source_artifacts)  # type: ignore[index]
    assert all(record["serialized_length"] > 0 for record in source_artifacts)  # type: ignore[index]


def test_collect_dry_run_packet_no_effect_boundary_denies_live_authority() -> None:
    packet = collect_personal_assistant_dry_run_packet(now_utc=FIXED_NOW)
    boundary = packet["no_effect_boundary"]

    assert packet["packet_is_not_execution_authority"] is True
    assert packet["packet_is_not_memory_admission"] is True
    assert packet["packet_is_not_customer_readiness"] is True
    assert all(value is False for value in boundary.values())  # type: ignore[union-attr]


def test_write_dry_run_packet_round_trips_json(tmp_path: Path) -> None:
    packet = collect_personal_assistant_dry_run_packet(now_utc=FIXED_NOW)
    output_path = tmp_path / "packet.json"

    written = write_personal_assistant_dry_run_packet(packet, output_path)
    parsed = json.loads(output_path.read_text(encoding="utf-8"))

    assert written == output_path
    assert parsed["packet_id"] == packet["packet_id"]
    assert parsed["closure_summary"]["dry_run_packet_closed"] is True
    assert parsed["topology_summary"]["acyclic"] is True


def test_collect_dry_run_packet_cli_writes_packet(tmp_path: Path, capsys: object) -> None:
    output_path = tmp_path / "packet.json"

    exit_code = main(["--output", str(output_path)])
    captured = capsys.readouterr()
    parsed = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert output_path.exists()
    assert "dry_run_packet_closed: True" in captured.out
    assert parsed["solver_outcome"] == "SolvedVerified"
