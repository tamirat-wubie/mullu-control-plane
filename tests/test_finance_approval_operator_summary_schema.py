"""Tests for finance approval operator summary schema validation.

Purpose: prove finance operator summaries are schema-compatible and preserve
promotion safety semantics.
Governance scope: summary schema, ok/ready consistency, strict promotion
command, artifact status coverage, and claim-boundary preservation.
Dependencies: scripts.validate_finance_approval_operator_summary_schema.
Invariants:
  - Current generated summary validates.
  - Ready drift fails closed.
  - Missing command tokens fail closed.
  - Missing artifact status coverage fails closed.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.produce_finance_approval_operator_summary import produce_finance_approval_operator_summary
from scripts.validate_finance_approval_operator_summary_schema import (
    main,
    validate_finance_approval_operator_summary_schema,
    write_finance_operator_summary_schema_validation,
)

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schemas" / "finance_approval_operator_summary.schema.json"


def test_finance_operator_summary_schema_accepts_current_summary(tmp_path: Path) -> None:
    summary_path = tmp_path / "finance_operator_summary.json"
    summary, errors = produce_finance_approval_operator_summary()
    summary_path.write_text(json.dumps(summary), encoding="utf-8")

    validation = validate_finance_approval_operator_summary_schema(
        summary_path=summary_path,
        schema_path=SCHEMA_PATH,
    )

    assert errors == ()
    assert validation.ok is True
    assert validation.errors == ()
    assert validation.packet_ready is False
    assert validation.chain_ready is False
    assert validation.readiness_blocker_count >= 1


def test_finance_operator_summary_schema_rejects_ready_drift(tmp_path: Path) -> None:
    summary_path = tmp_path / "finance_operator_summary.json"
    summary, errors = produce_finance_approval_operator_summary()
    summary["packet_ready"] = True
    summary["promotion_mode"] = "live-email-handoff"
    summary_path.write_text(json.dumps(summary), encoding="utf-8")

    validation = validate_finance_approval_operator_summary_schema(
        summary_path=summary_path,
        schema_path=SCHEMA_PATH,
    )

    assert errors == ()
    assert validation.ok is False
    assert "packet_ready and chain_ready must match" in validation.errors


def test_finance_operator_summary_schema_rejects_missing_promotion_command_token(tmp_path: Path) -> None:
    summary_path = tmp_path / "finance_operator_summary.json"
    summary, errors = produce_finance_approval_operator_summary()
    summary["strict_promotion_command"] = "python scripts/validate_finance_approval_live_handoff_chain.py"
    summary_path.write_text(json.dumps(summary), encoding="utf-8")

    validation = validate_finance_approval_operator_summary_schema(
        summary_path=summary_path,
        schema_path=SCHEMA_PATH,
    )

    assert errors == ()
    assert validation.ok is False
    assert any("--require-ready" in error for error in validation.errors)


def test_finance_operator_summary_schema_rejects_missing_promotion_json_token(tmp_path: Path) -> None:
    summary_path = tmp_path / "finance_operator_summary.json"
    summary, errors = produce_finance_approval_operator_summary()
    summary["strict_promotion_command"] = (
        "python scripts/validate_finance_approval_live_handoff_chain.py --strict --require-ready"
    )
    summary_path.write_text(json.dumps(summary), encoding="utf-8")

    validation = validate_finance_approval_operator_summary_schema(
        summary_path=summary_path,
        schema_path=SCHEMA_PATH,
    )

    assert errors == ()
    assert validation.ok is False
    assert any("--json" in error for error in validation.errors)


def test_finance_operator_summary_schema_rejects_missing_artifact_status(tmp_path: Path) -> None:
    summary_path = tmp_path / "finance_operator_summary.json"
    summary, errors = produce_finance_approval_operator_summary()
    del summary["artifact_statuses"]["live_handoff_closure_run"]
    summary_path.write_text(json.dumps(summary), encoding="utf-8")

    validation = validate_finance_approval_operator_summary_schema(
        summary_path=summary_path,
        schema_path=SCHEMA_PATH,
    )

    assert errors == ()
    assert validation.ok is False
    assert any("live_handoff_closure_run" in error for error in validation.errors)


def test_finance_operator_summary_schema_rejects_missing_full_claim_boundary(tmp_path: Path) -> None:
    summary_path = tmp_path / "finance_operator_summary.json"
    summary, errors = produce_finance_approval_operator_summary()
    summary["must_not_claim"].remove("bank settlement")
    summary_path.write_text(json.dumps(summary), encoding="utf-8")

    validation = validate_finance_approval_operator_summary_schema(
        summary_path=summary_path,
        schema_path=SCHEMA_PATH,
    )

    assert errors == ()
    assert validation.ok is False
    assert any("bank settlement" in error for error in validation.errors)


def test_finance_operator_summary_schema_writer_and_cli_honor_strict(tmp_path: Path, capsys) -> None:
    summary_path = tmp_path / "finance_operator_summary.json"
    output_path = tmp_path / "summary_schema_validation.json"
    summary, errors = produce_finance_approval_operator_summary()
    summary_path.write_text(json.dumps(summary), encoding="utf-8")
    validation = validate_finance_approval_operator_summary_schema(
        summary_path=summary_path,
        schema_path=SCHEMA_PATH,
    )

    written = write_finance_operator_summary_schema_validation(validation, output_path)
    exit_code = main(
        [
            "--summary",
            str(summary_path),
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

    assert errors == ()
    assert written == output_path
    assert exit_code == 0
    assert payload["ok"] is True
    assert stdout_payload["readiness_blocker_count"] == validation.readiness_blocker_count
