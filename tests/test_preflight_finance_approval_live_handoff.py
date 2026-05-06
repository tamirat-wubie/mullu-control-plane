"""Tests for finance approval live handoff preflight.

Purpose: prove finance live handoff preflight reports readiness blockers
without executing live email/calendar effects.
Governance scope: handoff plan validation, binding receipt readiness, closure
run validation, finance pilot readiness, and strict CLI behavior.
Dependencies: scripts.preflight_finance_approval_live_handoff.
Invariants:
  - Current local state is blocked while connector token evidence is absent.
  - Closed adapter evidence and ready binding receipt produce a ready preflight.
  - CLI strict mode fails for blocked preflight.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.emit_finance_approval_email_calendar_binding_receipt import (
    emit_finance_approval_email_calendar_binding_receipt,
    write_finance_email_calendar_binding_receipt,
)
from scripts.plan_finance_approval_live_handoff import (
    plan_finance_approval_live_handoff,
    write_finance_live_handoff_plan,
)
from scripts.preflight_finance_approval_live_handoff import (
    main,
    preflight_finance_approval_live_handoff,
    write_finance_live_handoff_preflight_report,
)
from scripts.run_finance_approval_live_handoff_closure import (
    run_finance_approval_live_handoff_closure,
    write_finance_live_handoff_closure_run,
)


def test_current_finance_live_handoff_preflight_blocks_absent_token() -> None:
    report = preflight_finance_approval_live_handoff()

    assert report.ready is False
    assert report.readiness_level == "proof-pilot-ready"
    assert report.step_count == 4
    assert "finance email/calendar binding receipt ready" in report.blockers
    assert "finance approval pilot readiness" in report.blockers


def test_finance_live_handoff_preflight_accepts_ready_local_evidence(tmp_path: Path) -> None:
    adapter_evidence = _write_closed_adapter_evidence(tmp_path)
    handoff_plan = _write_plan_for_adapter_evidence(tmp_path, adapter_evidence)
    binding_receipt = tmp_path / "finance_binding_receipt.json"
    receipt, errors = emit_finance_approval_email_calendar_binding_receipt(
        env_reader=lambda name: "present" if name == "GMAIL_ACCESS_TOKEN" else "",
    )
    write_finance_email_calendar_binding_receipt(receipt, binding_receipt)
    closure_run = _write_closure_run_for_ready_evidence(tmp_path, binding_receipt, adapter_evidence)

    report = preflight_finance_approval_live_handoff(
        handoff_plan_path=handoff_plan,
        binding_receipt_path=binding_receipt,
        closure_run_path=closure_run,
        adapter_evidence_path=adapter_evidence,
    )

    assert errors == ()
    assert report.ready is True
    assert report.blockers == ()
    assert report.readiness_level == "live-email-handoff-ready"
    assert {step.name for step in report.steps} == {
        "finance handoff plan schema validation",
        "finance email/calendar binding receipt ready",
        "finance live handoff closure run schema validation",
        "finance approval pilot readiness",
    }


def test_finance_live_handoff_preflight_blocks_invalid_closure_run(tmp_path: Path) -> None:
    adapter_evidence = _write_closed_adapter_evidence(tmp_path)
    handoff_plan = _write_plan_for_adapter_evidence(tmp_path, adapter_evidence)
    binding_receipt = tmp_path / "finance_binding_receipt.json"
    closure_run = tmp_path / "finance_closure_run.json"
    receipt, errors = emit_finance_approval_email_calendar_binding_receipt(
        env_reader=lambda name: "present" if name == "GMAIL_ACCESS_TOKEN" else "",
    )
    write_finance_email_calendar_binding_receipt(receipt, binding_receipt)
    closure_run.write_text(
        json.dumps(
            {
                "run_id": "finance-live-handoff-closure-run-0123456789abcdef",
                "checked_at": "2026-05-01T12:00:00+00:00",
                "mode": "dry-run",
                "status": "ready",
                "ready_to_execute_live": True,
                "command_count": 0,
                "blockers": [],
                "commands": [],
            }
        ),
        encoding="utf-8",
    )

    report = preflight_finance_approval_live_handoff(
        handoff_plan_path=handoff_plan,
        binding_receipt_path=binding_receipt,
        closure_run_path=closure_run,
        adapter_evidence_path=adapter_evidence,
    )

    assert errors == ()
    assert report.ready is False
    assert "finance live handoff closure run schema validation" in report.blockers
    assert any("closure run" in step.name for step in report.steps)


def test_finance_live_handoff_preflight_writer_and_cli_honor_strict(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "finance_preflight.json"
    report = preflight_finance_approval_live_handoff()

    written = write_finance_live_handoff_preflight_report(report, output_path)
    exit_code = main(["--output", str(output_path), "--strict", "--json"])
    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(captured.out)

    assert written == output_path
    assert exit_code == 2
    assert payload["ready"] is False
    assert stdout_payload["ready"] is False
    assert "finance email/calendar binding receipt ready" in payload["blockers"]


def _write_plan_for_adapter_evidence(tmp_path: Path, adapter_evidence: Path) -> Path:
    handoff_plan = tmp_path / "finance_handoff_plan.json"
    plan = plan_finance_approval_live_handoff(adapter_evidence_path=adapter_evidence)
    write_finance_live_handoff_plan(plan, handoff_plan)
    return handoff_plan


def _write_closure_run_for_ready_evidence(tmp_path: Path, binding_receipt: Path, adapter_evidence: Path) -> Path:
    closure_run_path = tmp_path / "finance_closure_run.json"
    closure_run = run_finance_approval_live_handoff_closure(
        binding_receipt_path=binding_receipt,
        adapter_evidence_path=adapter_evidence,
    )
    write_finance_live_handoff_closure_run(closure_run, closure_run_path)
    return closure_run_path


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
