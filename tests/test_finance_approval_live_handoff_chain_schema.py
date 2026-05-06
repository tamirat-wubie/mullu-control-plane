"""Tests for finance approval live handoff chain schema validation.

Purpose: prove aggregate finance chain validation reports are schema-compatible
and preserve check ordering, blocker derivation, and ok consistency.
Governance scope: chain validation schema, check order, blocker derivation,
strict CLI behavior, and ok/blocker consistency.
Dependencies: scripts.validate_finance_approval_live_handoff_chain_schema.
Invariants:
  - Current generated chain validation passes schema and semantic validation.
  - Check reordering fails closed.
  - Blocker drift fails closed.
  - ok/blocker drift fails closed.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_finance_approval_live_handoff_chain import validate_finance_approval_live_handoff_chain
from scripts.validate_finance_approval_live_handoff_chain_schema import (
    main,
    validate_finance_approval_live_handoff_chain_schema,
    write_finance_live_handoff_chain_schema_validation,
)

_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = _ROOT / "schemas" / "finance_approval_live_handoff_chain_validation.schema.json"


def test_finance_chain_schema_accepts_current_report(tmp_path: Path) -> None:
    chain_path = tmp_path / "finance_chain.json"
    chain_path.write_text(json.dumps(validate_finance_approval_live_handoff_chain().as_dict()), encoding="utf-8")

    validation = validate_finance_approval_live_handoff_chain_schema(
        chain_path=chain_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.check_count == 5
    assert validation.blocker_count == 0


def test_finance_chain_schema_rejects_check_reordering(tmp_path: Path) -> None:
    chain_path = tmp_path / "finance_chain.json"
    report = validate_finance_approval_live_handoff_chain().as_dict()
    report["checks"][0], report["checks"][1] = report["checks"][1], report["checks"][0]
    chain_path.write_text(json.dumps(report), encoding="utf-8")

    validation = validate_finance_approval_live_handoff_chain_schema(
        chain_path=chain_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.ok is False
    assert any("check names must match expected finance chain order" in error for error in validation.errors)


def test_finance_chain_schema_rejects_blocker_drift(tmp_path: Path) -> None:
    chain_path = tmp_path / "finance_chain.json"
    report = validate_finance_approval_live_handoff_chain().as_dict()
    report["checks"][0]["passed"] = False
    report["blockers"] = []
    chain_path.write_text(json.dumps(report), encoding="utf-8")

    validation = validate_finance_approval_live_handoff_chain_schema(
        chain_path=chain_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.ok is False
    assert any("blockers must match failed finance chain check names" in error for error in validation.errors)


def test_finance_chain_schema_rejects_ok_blocker_drift(tmp_path: Path) -> None:
    chain_path = tmp_path / "finance_chain.json"
    report = validate_finance_approval_live_handoff_chain().as_dict()
    report["ok"] = True
    report["checks"][0]["passed"] = False
    report["blockers"] = ["finance closure run schema validation"]
    chain_path.write_text(json.dumps(report), encoding="utf-8")

    validation = validate_finance_approval_live_handoff_chain_schema(
        chain_path=chain_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.ok is False
    assert "ok chain validation must not contain blockers" in validation.errors


def test_finance_chain_schema_writer_and_cli_honor_strict(tmp_path: Path, capsys) -> None:
    chain_path = tmp_path / "finance_chain.json"
    output_path = tmp_path / "schema_validation.json"
    chain_path.write_text(json.dumps(validate_finance_approval_live_handoff_chain().as_dict()), encoding="utf-8")
    validation = validate_finance_approval_live_handoff_chain_schema(
        chain_path=chain_path,
        schema_path=SCHEMA_PATH,
    )

    written = write_finance_live_handoff_chain_schema_validation(validation, output_path)
    exit_code = main(
        [
            "--chain",
            str(chain_path),
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
    assert stdout_payload["check_count"] == 5
