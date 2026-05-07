"""MIL audit runbook workflow preflight tests.

Tests: checklist-gated MIL audit replay, admission, persistence, and CLI report writing.
"""

from __future__ import annotations

import json
from pathlib import Path

from mcoi_runtime.contracts.mil import MILInstruction, MILOpcode, MILProgram
from mcoi_runtime.contracts.policy import DecisionReason, PolicyDecision, PolicyDecisionStatus
from mcoi_runtime.core.mil_static_verifier import verify_mil_program
from mcoi_runtime.persistence.mil_audit_store import MILAuditStore
from scripts.preflight_mil_audit_runbook_workflow import (
    main,
    preflight_mil_audit_runbook_workflow,
    write_mil_audit_runbook_preflight_report,
)


def test_mil_audit_runbook_preflight_accepts_valid_local_state(tmp_path: Path) -> None:
    paths = _seed_mil_audit_record(tmp_path)

    report = preflight_mil_audit_runbook_workflow(**paths)

    assert report.ready is True
    assert report.blockers == ()
    assert report.step_count == 7
    assert report.record_id == paths["record_id"]
    assert report.runbook_id == paths["runbook_id"]
    assert report.replay_id.startswith("mil-audit-replay-")
    assert report.trace_id.startswith("mil-audit-record-trace-")
    assert report.runbook_persisted is True
    assert {step.name for step in report.steps} == {
        "operator checklist validation",
        "MIL audit record load",
        "observation replay projection",
        "trace and replay persistence",
        "persisted replay validation",
        "runbook learning admission",
        "durable runbook readback",
    }


def test_mil_audit_runbook_preflight_blocks_missing_record(tmp_path: Path) -> None:
    paths = _seed_mil_audit_record(tmp_path)
    paths["record_id"] = "missing-record"

    report = preflight_mil_audit_runbook_workflow(**paths)

    assert report.ready is False
    assert report.blockers == ("MIL audit record load",)
    assert report.step_count == 2
    assert any("record load failed" in step.detail for step in report.steps)
    assert report.runbook_persisted is False


def test_mil_audit_runbook_preflight_blocks_invalid_checklist(tmp_path: Path) -> None:
    paths = _seed_mil_audit_record(tmp_path)
    checklist_path = tmp_path / "bad-checklist.json"
    checklist_path.write_text(json.dumps({"schema_version": 1}), encoding="utf-8")
    paths["checklist_path"] = checklist_path

    report = preflight_mil_audit_runbook_workflow(**paths)

    assert report.ready is False
    assert report.blockers == ("operator checklist validation",)
    assert report.step_count == 1
    assert "checklist_id must be mil-audit-runbook-operator-v1" in report.steps[0].detail


def test_mil_audit_runbook_preflight_writer_and_cli_honor_strict(tmp_path: Path, capsys) -> None:
    paths = _seed_mil_audit_record(tmp_path)
    output_path = tmp_path / "preflight.json"
    report = preflight_mil_audit_runbook_workflow(**paths)
    written = write_mil_audit_runbook_preflight_report(report, output_path)

    exit_code = main(
        [
            "--audit-store",
            str(paths["audit_store_path"]),
            "--trace-store",
            str(paths["trace_store_path"]),
            "--replay-store",
            str(paths["replay_store_path"]),
            "--runbook-store",
            str(paths["runbook_store_path"]),
            "--record-id",
            paths["record_id"],
            "--runbook-id",
            "runbook-workflow-cli-001",
            "--name",
            "MIL Workflow CLI Runbook",
            "--description",
            "Replay-backed runbook admitted from a verified MIL audit record.",
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
    assert payload["ready"] is True
    assert stdout_payload["ready"] is True
    assert payload["runbook_id"] == "runbook-workflow-cli-001"
    assert payload["runbook_persisted"] is True


def test_mil_audit_runbook_preflight_cli_strict_fails_blocked(tmp_path: Path, capsys) -> None:
    paths = _seed_mil_audit_record(tmp_path)
    output_path = tmp_path / "blocked-preflight.json"

    exit_code = main(
        [
            "--audit-store",
            str(paths["audit_store_path"]),
            "--trace-store",
            str(paths["trace_store_path"]),
            "--replay-store",
            str(paths["replay_store_path"]),
            "--runbook-store",
            str(paths["runbook_store_path"]),
            "--record-id",
            "missing-record",
            "--runbook-id",
            paths["runbook_id"],
            "--name",
            "MIL Workflow CLI Runbook",
            "--description",
            "Replay-backed runbook admitted from a verified MIL audit record.",
            "--output",
            str(output_path),
            "--strict",
            "--json",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 2
    assert payload["ready"] is False
    assert payload["blockers"] == ["MIL audit record load"]
    assert output_path.exists()


def _seed_mil_audit_record(tmp_path: Path) -> dict:
    audit_store_path = tmp_path / "mil-audit"
    decision = PolicyDecision(
        "policy:allow:workflow-preflight",
        "operator",
        "goal-workflow-preflight",
        PolicyDecisionStatus.ALLOW,
        (DecisionReason("allowed", "allow"),),
        "2026-05-06T12:00:00Z",
    )
    program = MILProgram(
        "mil:goal-workflow-preflight:shell_command",
        "goal-workflow-preflight",
        decision,
        (
            MILInstruction("check", MILOpcode.CHECK_POLICY, "goal-workflow-preflight"),
            MILInstruction("call", MILOpcode.CALL_CAPABILITY, "shell_command", depends_on=("check",)),
            MILInstruction("verify", MILOpcode.VERIFY_EFFECT, "shell_command", depends_on=("call",)),
            MILInstruction("proof", MILOpcode.EMIT_PROOF, "goal-workflow-preflight", depends_on=("verify",)),
        ),
        "2026-05-06T12:00:01Z",
    )
    result = MILAuditStore(audit_store_path).append(
        program=program,
        verification=verify_mil_program(program),
        execution_id="exec-workflow-preflight",
        instruction_trace=("proof:emit_proof:goal-workflow-preflight",),
        recorded_at="2026-05-06T12:00:02Z",
    )
    return {
        "audit_store_path": audit_store_path,
        "trace_store_path": tmp_path / "mil-traces",
        "replay_store_path": tmp_path / "mil-replays",
        "runbook_store_path": tmp_path / "mil-runbooks",
        "record_id": result.record.record_id,
        "runbook_id": "runbook-workflow-preflight-001",
        "name": "MIL Workflow Preflight Runbook",
        "description": "Replay-backed runbook admitted from a verified MIL audit record.",
    }
