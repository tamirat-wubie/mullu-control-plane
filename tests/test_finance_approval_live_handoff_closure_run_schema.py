"""Tests for finance approval live handoff closure run schema validation.

Purpose: prove finance closure run records are schema-compatible and preserve
dry-run, ordering, and live-touchpoint protections.
Governance scope: closure run schema, command sequence, dry-run enforcement,
live connector boundary, and strict CLI behavior.
Dependencies: scripts.validate_finance_approval_live_handoff_closure_run_schema.
Invariants:
  - Current generated closure run passes schema and semantic validation.
  - Live receipt collection cannot move before binding validation.
  - Only one live connector touchpoint is allowed.
  - Ready/status/blocker drift fails closed.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.run_finance_approval_live_handoff_closure import run_finance_approval_live_handoff_closure
from scripts.validate_finance_approval_live_handoff_closure_run_schema import (
    main,
    validate_finance_approval_live_handoff_closure_run_schema,
    write_finance_live_handoff_closure_run_schema_validation,
)

_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = _ROOT / "schemas" / "finance_approval_live_handoff_closure_run.schema.json"


def test_finance_closure_run_schema_accepts_current_run(tmp_path: Path) -> None:
    closure_run_path = tmp_path / "finance_closure_run.json"
    closure_run_path.write_text(json.dumps(run_finance_approval_live_handoff_closure().as_dict()), encoding="utf-8")

    validation = validate_finance_approval_live_handoff_closure_run_schema(
        closure_run_path=closure_run_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.command_count == 11
    assert validation.live_command_count == 1
    assert validation.status == "blocked"


def test_finance_closure_run_schema_rejects_live_receipt_before_binding(tmp_path: Path) -> None:
    closure_run_path = tmp_path / "finance_closure_run.json"
    closure_run = run_finance_approval_live_handoff_closure().as_dict()
    closure_run["commands"][1], closure_run["commands"][2] = closure_run["commands"][2], closure_run["commands"][1]
    closure_run_path.write_text(json.dumps(closure_run), encoding="utf-8")

    validation = validate_finance_approval_live_handoff_closure_run_schema(
        closure_run_path=closure_run_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.ok is False
    assert any("step_ids must match expected finance closure order" in error for error in validation.errors)


def test_finance_closure_run_schema_rejects_multiple_live_touchpoints(tmp_path: Path) -> None:
    closure_run_path = tmp_path / "finance_closure_run.json"
    closure_run = run_finance_approval_live_handoff_closure().as_dict()
    closure_run["commands"][0]["live_effect_possible"] = True
    closure_run_path.write_text(json.dumps(closure_run), encoding="utf-8")

    validation = validate_finance_approval_live_handoff_closure_run_schema(
        closure_run_path=closure_run_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.ok is False
    assert validation.live_command_count == 2
    assert any("live_effect_possible must be true only" in error for error in validation.errors)


def test_finance_closure_run_schema_rejects_status_drift(tmp_path: Path) -> None:
    closure_run_path = tmp_path / "finance_closure_run.json"
    closure_run = run_finance_approval_live_handoff_closure().as_dict()
    closure_run["status"] = "ready"
    closure_run_path.write_text(json.dumps(closure_run), encoding="utf-8")

    validation = validate_finance_approval_live_handoff_closure_run_schema(
        closure_run_path=closure_run_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.ok is False
    assert "status=ready requires ready_to_execute_live=true" in validation.errors


def test_finance_closure_run_schema_writer_and_cli_honor_strict(tmp_path: Path, capsys) -> None:
    closure_run_path = tmp_path / "finance_closure_run.json"
    output_path = tmp_path / "schema_validation.json"
    closure_run_path.write_text(json.dumps(run_finance_approval_live_handoff_closure().as_dict()), encoding="utf-8")
    validation = validate_finance_approval_live_handoff_closure_run_schema(
        closure_run_path=closure_run_path,
        schema_path=SCHEMA_PATH,
    )

    written = write_finance_live_handoff_closure_run_schema_validation(validation, output_path)
    exit_code = main(
        [
            "--closure-run",
            str(closure_run_path),
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
    assert stdout_payload["command_count"] == 11
