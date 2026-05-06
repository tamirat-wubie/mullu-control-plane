"""Purpose: verify CLI inspection for persisted MIL audit records.
Governance scope: local operator CLI read paths for MIL audit persistence.
Dependencies: CLI main, MIL contracts, static verifier, and MIL audit store.
Invariants: CLI reads are explicit; replay output is observation-only; missing store fails closed.
"""

from __future__ import annotations

import json

from mcoi_runtime.app.cli import main
from mcoi_runtime.contracts.mil import MILInstruction, MILOpcode, MILProgram
from mcoi_runtime.contracts.policy import DecisionReason, PolicyDecision, PolicyDecisionStatus
from mcoi_runtime.core.mil_static_verifier import verify_mil_program
from mcoi_runtime.persistence.mil_audit_store import MILAuditStore


def _record_id(tmp_path) -> tuple[str, str]:
    decision = PolicyDecision(
        "policy:allow:goal-cli",
        "operator",
        "goal-cli",
        PolicyDecisionStatus.ALLOW,
        (DecisionReason("allowed", "allow"),),
        "2026-05-06T12:00:00Z",
    )
    program = MILProgram(
        "mil:goal-cli:shell_command",
        "goal-cli",
        decision,
        (
            MILInstruction("check", MILOpcode.CHECK_POLICY, "goal-cli"),
            MILInstruction("call", MILOpcode.CALL_CAPABILITY, "shell_command", depends_on=("check",)),
            MILInstruction("verify", MILOpcode.VERIFY_EFFECT, "shell_command", depends_on=("call",)),
            MILInstruction("proof", MILOpcode.EMIT_PROOF, "goal-cli", depends_on=("verify",)),
        ),
        "2026-05-06T12:00:01Z",
    )
    store_path = tmp_path / "mil-audit"
    result = MILAuditStore(store_path).append(
        program=program,
        verification=verify_mil_program(program),
        execution_id="exec-cli",
        instruction_trace=("proof:emit_proof:goal-cli",),
        recorded_at="2026-05-06T12:00:02Z",
    )
    return str(store_path), result.record.record_id


def test_mil_audit_get_cli_outputs_record_json(tmp_path, capsys) -> None:
    store_path, record_id = _record_id(tmp_path)

    rc = main(["mil-audit", "get", "--store", store_path, "--json", record_id])
    output = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert output["operation"] == "get"
    assert output["record_id"] == record_id
    assert output["program_id"] == "mil:goal-cli:shell_command"


def test_mil_audit_replay_cli_outputs_observation_replay(tmp_path, capsys) -> None:
    store_path, record_id = _record_id(tmp_path)

    rc = main(["mil-audit", "replay", "--store", store_path, "--json", record_id])
    output = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert output["operation"] == "replay"
    assert output["replay_mode"] == "observation_only"
    assert output["replay_record"]["metadata"]["record_id"] == record_id
    assert [entry["event_type"] for entry in output["trace_entries"]] == [
        "whqr_policy_decision",
        "policy_decision",
        "mil_program",
        "mil_static_verification",
        "dispatch_execution",
        "mil_audit_record",
    ]
    assert output["trace_entries"][-1]["parent_trace_id"] == output["trace_entries"][-2]["trace_id"]


def test_mil_audit_cli_missing_store_fails_closed(tmp_path, capsys) -> None:
    rc = main(["mil-audit", "get", "--store", str(tmp_path / "missing"), "record-1"])
    output = capsys.readouterr().out

    assert rc == 1
    assert "MIL audit store access failed" in output
    assert "missing" not in output
