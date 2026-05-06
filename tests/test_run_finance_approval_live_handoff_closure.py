"""Tests for finance approval live handoff closure dry-run.

Purpose: prove the live handoff closure runner emits a governed command
sequence without executing live email/calendar effects.
Governance scope: binding readiness gate, live connector touchpoint marking,
artifact writer behavior, and strict CLI blocking.
Dependencies: scripts.run_finance_approval_live_handoff_closure.
Invariants:
  - Default runner mode is dry-run.
  - Binding validation precedes live receipt collection.
  - Only the read-only email/calendar receipt command can touch a live connector.
  - Blocked current state remains machine-readable.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.emit_finance_approval_email_calendar_binding_receipt import (
    emit_finance_approval_email_calendar_binding_receipt,
    write_finance_email_calendar_binding_receipt,
)
from scripts.run_finance_approval_live_handoff_closure import (
    main,
    run_finance_approval_live_handoff_closure,
    write_finance_live_handoff_closure_run,
)


def test_current_finance_live_handoff_closure_dry_run_blocks_absent_token() -> None:
    run = run_finance_approval_live_handoff_closure()

    assert run.mode == "dry-run"
    assert run.status == "blocked"
    assert run.ready_to_execute_live is False
    assert run.command_count == 16
    assert "finance_email_calendar_binding_receipt_not_ready" in run.blockers
    assert "finance_approval_pilot_readiness_not_ready" in run.blockers


def test_finance_live_handoff_closure_orders_binding_before_live_receipt() -> None:
    run = run_finance_approval_live_handoff_closure()
    step_ids = [command.step_id for command in run.commands]
    live_commands = [command for command in run.commands if command.live_effect_possible]

    assert step_ids.index("02_validate_binding_receipt") < step_ids.index("03_collect_read_only_live_receipt")
    assert step_ids.index("03_collect_read_only_live_receipt") < step_ids.index("04_validate_read_only_live_receipt")
    assert step_ids.index("04_validate_read_only_live_receipt") < step_ids.index("05_collect_adapter_evidence")
    assert step_ids.index("09_run_preflight") < step_ids.index("10_validate_preflight_schema")
    assert step_ids.index("10_validate_preflight_schema") < step_ids.index("11_produce_handoff_packet")
    assert step_ids.index("12_validate_handoff_packet_schema") < step_ids.index("13_validate_handoff_chain")
    assert step_ids.index("13_validate_handoff_chain") < step_ids.index("14_validate_handoff_chain_schema")
    assert step_ids.index("14_validate_handoff_chain_schema") < step_ids.index("15_produce_operator_summary")
    assert step_ids.index("15_produce_operator_summary") < step_ids.index("16_validate_operator_summary_schema")
    assert len(live_commands) == 1
    assert live_commands[0].step_id == "03_collect_read_only_live_receipt"
    assert "--target email-calendar" in live_commands[0].command
    assert "produce_capability_adapter_live_receipts.py" in live_commands[0].command


def test_finance_live_handoff_closure_accepts_ready_local_evidence(tmp_path: Path) -> None:
    binding_receipt = tmp_path / "finance_binding_receipt.json"
    receipt, errors = emit_finance_approval_email_calendar_binding_receipt(
        env_reader=lambda name: "present" if name == "GMAIL_ACCESS_TOKEN" else "",
    )
    adapter_evidence = _write_closed_adapter_evidence(tmp_path)
    write_finance_email_calendar_binding_receipt(receipt, binding_receipt)

    run = run_finance_approval_live_handoff_closure(
        binding_receipt_path=binding_receipt,
        adapter_evidence_path=adapter_evidence,
    )

    assert errors == ()
    assert run.status == "ready"
    assert run.ready_to_execute_live is True
    assert run.blockers == ()
    assert run.command_count == 16


def test_finance_live_handoff_closure_writer_and_cli_honor_strict(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "finance_closure_run.json"
    run = run_finance_approval_live_handoff_closure()

    written = write_finance_live_handoff_closure_run(run, output_path)
    exit_code = main(["--output", str(output_path), "--strict", "--json"])
    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(captured.out)

    assert written == output_path
    assert exit_code == 2
    assert payload["status"] == "blocked"
    assert stdout_payload["status"] == "blocked"
    assert "finance_email_calendar_binding_receipt_not_ready" in payload["blockers"]


def _write_closed_adapter_evidence(tmp_path: Path) -> Path:
    adapter_evidence = tmp_path / "capability_adapter_evidence.json"
    adapter_evidence.write_text(
        json.dumps(
            {
                "adapters": [
                    {
                        "adapter_id": "document.production_parsers",
                        "status": "closed",
                        "blockers": [],
                        "evidence_refs": ["document_live_receipt.json"],
                    },
                    {
                        "adapter_id": "communication.email_calendar_worker",
                        "status": "closed",
                        "blockers": [],
                        "evidence_refs": ["email_calendar_live_receipt.json"],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    return adapter_evidence
