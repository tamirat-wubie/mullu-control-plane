"""Tests for finance approval handoff packet schema validation.

Purpose: prove finance handoff packets are schema-compatible and preserve
proof and claim-boundary protections.
Governance scope: packet schema, artifact coverage, status consistency, proof
summary, and must-not-claim enforcement.
Dependencies: scripts.validate_finance_approval_handoff_packet_schema.
Invariants:
  - Current generated packet passes schema and semantic validation.
  - Missing artifacts and missing claim boundaries fail closed.
  - Ready/status/blocker drift fails closed.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.produce_finance_approval_handoff_packet import produce_finance_approval_handoff_packet
from scripts.validate_finance_approval_handoff_packet_schema import (
    main,
    validate_finance_approval_handoff_packet_schema,
    write_finance_handoff_packet_schema_validation,
)

_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = _ROOT / "schemas" / "finance_approval_handoff_packet.schema.json"


def test_finance_handoff_packet_schema_accepts_current_packet(tmp_path: Path) -> None:
    packet_path = tmp_path / "finance_handoff_packet.json"
    packet_path.write_text(json.dumps(produce_finance_approval_handoff_packet()), encoding="utf-8")

    validation = validate_finance_approval_handoff_packet_schema(
        packet_path=packet_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.artifact_count == 5
    assert validation.blocker_count >= 1
    assert validation.readiness_level in {"not-ready", "proof-pilot-ready"}


def test_finance_handoff_packet_schema_rejects_status_drift(tmp_path: Path) -> None:
    packet_path = tmp_path / "finance_handoff_packet.json"
    packet = produce_finance_approval_handoff_packet()
    packet["status"] = "ready"
    packet_path.write_text(json.dumps(packet), encoding="utf-8")

    validation = validate_finance_approval_handoff_packet_schema(
        packet_path=packet_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.ok is False
    assert "status=ready requires ready=true" in validation.errors


def test_finance_handoff_packet_schema_rejects_promotion_boundary_ready_drift(tmp_path: Path) -> None:
    packet_path = tmp_path / "finance_handoff_packet.json"
    packet = produce_finance_approval_handoff_packet()
    packet["promotion_boundary"]["ready"] = True
    packet["promotion_boundary"]["mode"] = "live-email-handoff"
    packet["promotion_boundary"]["readiness_blockers"] = []
    packet_path.write_text(json.dumps(packet), encoding="utf-8")

    validation = validate_finance_approval_handoff_packet_schema(
        packet_path=packet_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.ok is False
    assert "promotion_boundary.ready must match packet ready" in validation.errors


def test_finance_handoff_packet_schema_rejects_missing_promotion_command_token(tmp_path: Path) -> None:
    packet_path = tmp_path / "finance_handoff_packet.json"
    packet = produce_finance_approval_handoff_packet()
    packet["promotion_boundary"]["strict_promotion_command"] = "python scripts/validate_finance_approval_live_handoff_chain.py"
    packet_path.write_text(json.dumps(packet), encoding="utf-8")

    validation = validate_finance_approval_handoff_packet_schema(
        packet_path=packet_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.ok is False
    assert any("--require-ready" in error for error in validation.errors)


def test_finance_handoff_packet_schema_rejects_missing_artifact(tmp_path: Path) -> None:
    packet_path = tmp_path / "finance_handoff_packet.json"
    packet = produce_finance_approval_handoff_packet()
    packet["artifacts"] = packet["artifacts"][:3]
    packet_path.write_text(json.dumps(packet), encoding="utf-8")

    validation = validate_finance_approval_handoff_packet_schema(
        packet_path=packet_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.ok is False
    assert any("artifact names must match" in error for error in validation.errors)


def test_finance_handoff_packet_schema_rejects_invalid_closure_run_artifact(tmp_path: Path) -> None:
    packet_path = tmp_path / "finance_handoff_packet.json"
    closure_run_path = tmp_path / "finance_closure_run.json"
    packet = produce_finance_approval_handoff_packet()
    closure_run_path.write_text(
        json.dumps(
            {
                "run_id": "finance-live-handoff-closure-run-0123456789abcdef",
                "checked_at": "2026-05-01T12:00:00+00:00",
                "mode": "dry-run",
                "status": "blocked",
                "ready_to_execute_live": False,
                "command_count": 0,
                "blockers": ["finance_email_calendar_binding_receipt_not_ready"],
                "commands": [],
            }
        ),
        encoding="utf-8",
    )
    for artifact in packet["artifacts"]:
        if artifact["name"] == "live_handoff_closure_run":
            artifact["path"] = str(closure_run_path)
            artifact["status"] = "blocked"
    packet_path.write_text(json.dumps(packet), encoding="utf-8")

    validation = validate_finance_approval_handoff_packet_schema(
        packet_path=packet_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.ok is False
    assert any("live_handoff_closure_run schema invalid" in error for error in validation.errors)


def test_finance_handoff_packet_schema_rejects_invalid_handoff_plan_artifact(tmp_path: Path) -> None:
    packet_path = tmp_path / "finance_handoff_packet.json"
    plan_path = tmp_path / "finance_handoff_plan.json"
    packet = produce_finance_approval_handoff_packet()
    plan_path.write_text(
        json.dumps(
            {
                "plan_id": "finance-live-handoff-plan-0123456789abcdef",
                "readiness_level": "proof-pilot-ready",
                "ready": False,
                "action_count": 0,
                "blockers": ["email_calendar_live_evidence_missing"],
                "actions": [],
            }
        ),
        encoding="utf-8",
    )
    for artifact in packet["artifacts"]:
        if artifact["name"] == "live_handoff_plan":
            artifact["path"] = str(plan_path)
            artifact["status"] = "proof-pilot-ready"
    packet_path.write_text(json.dumps(packet), encoding="utf-8")

    validation = validate_finance_approval_handoff_packet_schema(
        packet_path=packet_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.ok is False
    assert any("live_handoff_plan schema invalid" in error for error in validation.errors)


def test_finance_handoff_packet_schema_rejects_invalid_binding_receipt_artifact(tmp_path: Path) -> None:
    packet_path = tmp_path / "finance_handoff_packet.json"
    receipt_path = tmp_path / "finance_binding_receipt.json"
    packet = produce_finance_approval_handoff_packet()
    receipt_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "receipt_id": "finance-email-calendar-binding-receipt-0123456789abcdef",
                "checked_at": "2026-05-01T12:00:00+00:00",
                "ready": False,
                "accepted_binding_names": ["GMAIL_ACCESS_TOKEN"],
                "present_binding_names": [],
                "binding_count": 0,
                "secret_serialization": "allowed",
                "bindings": [],
            }
        ),
        encoding="utf-8",
    )
    for artifact in packet["artifacts"]:
        if artifact["name"] == "email_calendar_binding_receipt":
            artifact["path"] = str(receipt_path)
            artifact["status"] = "blocked"
    packet_path.write_text(json.dumps(packet), encoding="utf-8")

    validation = validate_finance_approval_handoff_packet_schema(
        packet_path=packet_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.ok is False
    assert any("email_calendar_binding_receipt schema invalid" in error for error in validation.errors)


def test_finance_handoff_packet_schema_rejects_invalid_preflight_artifact(tmp_path: Path) -> None:
    packet_path = tmp_path / "finance_handoff_packet.json"
    preflight_path = tmp_path / "finance_preflight.json"
    packet = produce_finance_approval_handoff_packet()
    preflight_path.write_text(
        json.dumps(
            {
                "ready": False,
                "checked_at": "2026-05-01T12:00:00+00:00",
                "readiness_level": "proof-pilot-ready",
                "step_count": 0,
                "steps": [],
                "blockers": [],
            }
        ),
        encoding="utf-8",
    )
    for artifact in packet["artifacts"]:
        if artifact["name"] == "live_handoff_preflight":
            artifact["path"] = str(preflight_path)
            artifact["status"] = "blocked"
    packet_path.write_text(json.dumps(packet), encoding="utf-8")

    validation = validate_finance_approval_handoff_packet_schema(
        packet_path=packet_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.ok is False
    assert any("live_handoff_preflight schema invalid" in error for error in validation.errors)


def test_finance_handoff_packet_schema_rejects_proof_summary_drift(tmp_path: Path) -> None:
    packet_path = tmp_path / "finance_handoff_packet.json"
    packet = produce_finance_approval_handoff_packet()
    packet["proof_summary"]["successful_effect_refs"] = []
    packet_path.write_text(json.dumps(packet), encoding="utf-8")

    validation = validate_finance_approval_handoff_packet_schema(
        packet_path=packet_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.ok is False
    assert "proof_summary.successful_effect_refs must be non-empty" in validation.errors


def test_finance_handoff_packet_schema_rejects_missing_must_not_claim(tmp_path: Path) -> None:
    packet_path = tmp_path / "finance_handoff_packet.json"
    packet = produce_finance_approval_handoff_packet()
    packet["claim_boundary"]["must_not_claim"].remove("live email delivery")
    packet_path.write_text(json.dumps(packet), encoding="utf-8")

    validation = validate_finance_approval_handoff_packet_schema(
        packet_path=packet_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.ok is False
    assert any("live email delivery" in error for error in validation.errors)


def test_finance_handoff_packet_schema_writer_and_cli_honor_strict(tmp_path: Path, capsys) -> None:
    packet_path = tmp_path / "finance_handoff_packet.json"
    output_path = tmp_path / "schema_validation.json"
    packet_path.write_text(json.dumps(produce_finance_approval_handoff_packet()), encoding="utf-8")
    validation = validate_finance_approval_handoff_packet_schema(
        packet_path=packet_path,
        schema_path=SCHEMA_PATH,
    )

    written = write_finance_handoff_packet_schema_validation(validation, output_path)
    exit_code = main(
        [
            "--packet",
            str(packet_path),
            "--schema",
            str(SCHEMA_PATH),
            "--output",
            str(output_path),
            "--strict",
            "--json",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(captured.out)

    assert written == output_path
    assert exit_code == 0
    assert payload["ok"] is True
    assert stdout_payload["artifact_count"] == 5
