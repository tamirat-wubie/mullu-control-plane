"""Tests for finance approval live handoff preflight schema validation.

Purpose: prove finance preflight reports are schema-compatible and preserve
four-step ordering, blocker derivation, and readiness consistency.
Governance scope: preflight schema, step order, blocker derivation, strict CLI
behavior, and ready/readiness consistency.
Dependencies: scripts.validate_finance_approval_live_handoff_preflight_schema.
Invariants:
  - Current generated preflight passes schema and semantic validation.
  - Step reordering fails closed.
  - Blocker drift fails closed.
  - Ready/readiness drift fails closed.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.preflight_finance_approval_live_handoff import preflight_finance_approval_live_handoff
from scripts.validate_finance_approval_live_handoff_preflight_schema import (
    main,
    validate_finance_approval_live_handoff_preflight_schema,
    write_finance_live_handoff_preflight_schema_validation,
)

_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = _ROOT / "schemas" / "finance_approval_live_handoff_preflight.schema.json"


def test_finance_preflight_schema_accepts_current_report(tmp_path: Path) -> None:
    preflight_path = tmp_path / "finance_preflight.json"
    preflight_path.write_text(json.dumps(preflight_finance_approval_live_handoff().as_dict()), encoding="utf-8")

    validation = validate_finance_approval_live_handoff_preflight_schema(
        preflight_path=preflight_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.step_count == 4
    assert validation.blocker_count >= 1
    assert validation.readiness_level == "proof-pilot-ready"


def test_finance_preflight_schema_rejects_step_reordering(tmp_path: Path) -> None:
    preflight_path = tmp_path / "finance_preflight.json"
    report = preflight_finance_approval_live_handoff().as_dict()
    report["steps"][0], report["steps"][1] = report["steps"][1], report["steps"][0]
    preflight_path.write_text(json.dumps(report), encoding="utf-8")

    validation = validate_finance_approval_live_handoff_preflight_schema(
        preflight_path=preflight_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.ok is False
    assert any("step names must match expected finance preflight order" in error for error in validation.errors)


def test_finance_preflight_schema_rejects_blocker_drift(tmp_path: Path) -> None:
    preflight_path = tmp_path / "finance_preflight.json"
    report = preflight_finance_approval_live_handoff().as_dict()
    report["blockers"] = []
    preflight_path.write_text(json.dumps(report), encoding="utf-8")

    validation = validate_finance_approval_live_handoff_preflight_schema(
        preflight_path=preflight_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.ok is False
    assert any("blockers must match failed preflight step names" in error for error in validation.errors)
    assert "blocked preflight must contain blockers" in validation.errors


def test_finance_preflight_schema_rejects_ready_readiness_drift(tmp_path: Path) -> None:
    preflight_path = tmp_path / "finance_preflight.json"
    report = preflight_finance_approval_live_handoff().as_dict()
    for step in report["steps"]:
        step["passed"] = True
    report["blockers"] = []
    report["ready"] = True
    report["readiness_level"] = "proof-pilot-ready"
    preflight_path.write_text(json.dumps(report), encoding="utf-8")

    validation = validate_finance_approval_live_handoff_preflight_schema(
        preflight_path=preflight_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.ok is False
    assert "ready preflight requires readiness_level=live-email-handoff-ready" in validation.errors


def test_finance_preflight_schema_writer_and_cli_honor_strict(tmp_path: Path, capsys) -> None:
    preflight_path = tmp_path / "finance_preflight.json"
    output_path = tmp_path / "schema_validation.json"
    preflight_path.write_text(json.dumps(preflight_finance_approval_live_handoff().as_dict()), encoding="utf-8")
    validation = validate_finance_approval_live_handoff_preflight_schema(
        preflight_path=preflight_path,
        schema_path=SCHEMA_PATH,
    )

    written = write_finance_live_handoff_preflight_schema_validation(validation, output_path)
    exit_code = main(
        [
            "--preflight",
            str(preflight_path),
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
    assert stdout_payload["step_count"] == 4
