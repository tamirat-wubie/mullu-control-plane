"""Tests for TeamOps live-probe operator input request validation.

Purpose: prove TeamOps live-probe operator input requests are schema-backed,
truthful about readiness, redacted, and non-executing.
Governance scope: TeamOps live-probe readiness validation, blocked-action
binding, source artifact binding, and secret redaction.
Dependencies: scripts.validate_team_ops_shared_inbox_live_probe_operator_input_request.
Invariants:
  - Blocked requests explain missing inputs.
  - Ready requests have no required inputs or blocked actions.
  - External-effect drift and secret marker drift fail validation.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.emit_team_ops_shared_inbox_live_probe_operator_input_request import (
    emit_team_ops_live_probe_operator_input_request,
)
from scripts.produce_team_ops_shared_inbox_live_probe_authority import (
    produce_team_ops_shared_inbox_live_probe_authority,
    write_team_ops_shared_inbox_live_probe_authority,
)
from scripts.validate_team_ops_shared_inbox_live_probe_operator_input_request import (
    main,
    validate_team_ops_live_probe_operator_input_request,
    write_team_ops_live_probe_operator_input_request_validation,
)


ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schemas" / "team_ops_shared_inbox_live_probe_operator_input_request.schema.json"


def test_team_ops_live_probe_operator_input_request_validation_accepts_blocked_request(tmp_path: Path) -> None:
    request_path = _write_blocked_request(tmp_path)

    validation = validate_team_ops_live_probe_operator_input_request(
        request_path=request_path,
        schema_path=SCHEMA_PATH,
        require_blocked=True,
    )

    assert validation.valid is True
    assert validation.probe_allowed is False
    assert validation.errors == ()
    assert validation.next_action


def test_team_ops_live_probe_operator_input_request_validation_rejects_ready_drift(tmp_path: Path) -> None:
    request_path = _write_blocked_request(tmp_path)
    request = json.loads(request_path.read_text(encoding="utf-8"))
    request["ready"] = True
    request["probe_allowed"] = True
    request["solver_outcome"] = "SolvedVerified"
    request["proof_state"] = "Pass"
    request_path.write_text(json.dumps(request), encoding="utf-8")

    validation = validate_team_ops_live_probe_operator_input_request(
        request_path=request_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert "probe_allowed must equal ready authority with no inputs or blocked actions" in validation.errors
    assert "ready request must not list required inputs or blocked actions" in validation.errors
    assert "solver_outcome must align with authority readiness" in validation.errors


def test_team_ops_live_probe_operator_input_request_validation_rejects_effect_drift(tmp_path: Path) -> None:
    request_path = _write_blocked_request(tmp_path)
    request = json.loads(request_path.read_text(encoding="utf-8"))
    request["external_provider_call_performed"] = True
    request["allowed_probe_summary"]["external_send_allowed"] = True
    request_path.write_text(json.dumps(request), encoding="utf-8")

    validation = validate_team_ops_live_probe_operator_input_request(
        request_path=request_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert "external_provider_call_performed must be false" in validation.errors
    assert "allowed_probe_summary.external_send_allowed must be false" in validation.errors


def test_team_ops_live_probe_operator_input_request_validation_rejects_secret_marker(tmp_path: Path) -> None:
    request_path = _write_blocked_request(tmp_path)
    request = json.loads(request_path.read_text(encoding="utf-8"))
    request["next_action"] = "bind client_secret=must-not-serialize"
    request_path.write_text(json.dumps(request), encoding="utf-8")

    validation = validate_team_ops_live_probe_operator_input_request(
        request_path=request_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert any("secret marker" in error for error in validation.errors)


def test_team_ops_live_probe_operator_input_request_validation_cli_writes_receipt(tmp_path: Path, capsys) -> None:
    request_path = _write_blocked_request(tmp_path)
    output_path = tmp_path / "team_ops_live_probe_operator_input_request_validation.json"
    validation = validate_team_ops_live_probe_operator_input_request(
        request_path=request_path,
        schema_path=SCHEMA_PATH,
        require_blocked=True,
    )

    written = write_team_ops_live_probe_operator_input_request_validation(validation, output_path)
    exit_code = main(
        [
            "--request",
            str(request_path),
            "--schema",
            str(SCHEMA_PATH),
            "--output",
            str(output_path),
            "--require-blocked",
            "--json",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(captured.out)

    assert written == output_path
    assert exit_code == 0
    assert payload["valid"] is True
    assert payload["probe_allowed"] is False
    assert stdout_payload["next_action"] == payload["next_action"]
    assert captured.err == ""


def _write_blocked_request(tmp_path: Path) -> Path:
    authority_path = tmp_path / "team_ops_shared_inbox_live_probe_authority.json"
    request_path = tmp_path / "team_ops_shared_inbox_live_probe_operator_input_request.json"
    write_team_ops_shared_inbox_live_probe_authority(
        produce_team_ops_shared_inbox_live_probe_authority(handoff_path=tmp_path / "missing_handoff.json"),
        authority_path,
    )
    request = emit_team_ops_live_probe_operator_input_request(
        authority_path=authority_path,
        schema_path=SCHEMA_PATH,
    )
    request_path.write_text(json.dumps(request.as_dict()), encoding="utf-8")
    return request_path
