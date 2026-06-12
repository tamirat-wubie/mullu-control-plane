"""Tests for finance approval live handoff chain dry-run production.

Purpose: prove the local finance handoff chain dry run produces complete
artifact evidence while preserving blocked live-readiness status.
Governance scope: finance handoff chain dry run, schema validation, readiness
blockers, and strict CLI readiness behavior.
Dependencies: scripts.run_finance_approval_live_handoff_chain.
Invariants:
  - Default dry runs are valid but not live-ready.
  - Ready simulation requires closed adapter and live receipt evidence.
  - require-ready returns nonzero for blocked dry-run evidence.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.run_finance_approval_live_handoff_chain import (
    main,
    run_finance_approval_live_handoff_chain,
)


def test_finance_live_handoff_chain_dry_run_preserves_blocked_readiness(tmp_path: Path) -> None:
    dry_run = run_finance_approval_live_handoff_chain(output_dir=tmp_path)

    chain_path = tmp_path / "finance_approval_live_handoff_chain_validation.json"
    schema_path = tmp_path / "finance_approval_live_handoff_chain_schema_validation.json"
    operator_request_path = tmp_path / "finance_approval_email_calendar_operator_input_request.json"
    operator_validation_path = tmp_path / "finance_approval_email_calendar_operator_input_request_validation.json"
    chain = json.loads(chain_path.read_text(encoding="utf-8"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    operator_request = json.loads(operator_request_path.read_text(encoding="utf-8"))
    operator_validation = json.loads(operator_validation_path.read_text(encoding="utf-8"))

    assert dry_run.mode == "dry-run"
    assert dry_run.status == "passed_blocked"
    assert dry_run.chain_ok is True
    assert dry_run.schema_ok is True
    assert dry_run.ready is False
    assert dry_run.artifact_count == 12
    assert chain["ok"] is True
    assert chain["ready"] is False
    assert schema["ok"] is True
    assert operator_request["handoff_allowed"] is True
    assert operator_request["required_inputs"] == []
    assert operator_validation["valid"] is True
    assert any("finance email/calendar live receipt not ready" in blocker for blocker in dry_run.readiness_blockers)


def test_finance_live_handoff_chain_ready_simulation_has_no_readiness_blockers(tmp_path: Path) -> None:
    dry_run = run_finance_approval_live_handoff_chain(output_dir=tmp_path, live_ready=True)

    chain = json.loads((tmp_path / "finance_approval_live_handoff_chain_validation.json").read_text(encoding="utf-8"))

    assert dry_run.status == "ready"
    assert dry_run.ready is True
    assert dry_run.chain_ok is True
    assert dry_run.schema_ok is True
    assert dry_run.readiness_blockers == ()
    assert chain["ready"] is True
    assert chain["readiness_blockers"] == []


def test_finance_live_handoff_chain_cli_returns_nonzero_when_ready_required(
    tmp_path: Path,
    capsys,
) -> None:
    exit_code = main(["--output-dir", str(tmp_path), "--require-ready", "--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 2
    assert payload["mode"] == "dry-run"
    assert payload["status"] == "passed_blocked"
    assert payload["ready"] is False
    assert payload["chain_ok"] is True
    assert payload["schema_ok"] is True
