"""Tests for read-only worker runtime enablement operator input validation.

Purpose: prove runtime enablement operator input requests are schema-backed,
truthful about blocked authority, redacted, and non-executing.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_read_only_worker_runtime_enablement_operator_input_request.
Invariants:
  - Runtime enablement remains denied.
  - Blocked requests preserve missing evidence and blocked actions.
  - Secret marker and live-effect drift fail validation.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.emit_read_only_worker_runtime_enablement_operator_input_request import (  # noqa: E402
    emit_runtime_enablement_operator_input_request,
    write_runtime_enablement_operator_input_request,
)
from scripts.validate_read_only_worker_runtime_enablement_operator_input_request import (  # noqa: E402
    main,
    validate_runtime_enablement_operator_input_request,
    write_runtime_enablement_operator_input_request_validation,
)


SCHEMA_PATH = (
    _ROOT
    / "schemas"
    / "read_only_worker_runtime_enablement_operator_input_request.schema.json"
)


def test_validate_runtime_enablement_operator_input_request_accepts_blocked_request(
    tmp_path: Path,
) -> None:
    request_path = _write_request(tmp_path)

    validation = validate_runtime_enablement_operator_input_request(
        request_path=request_path,
        schema_path=SCHEMA_PATH,
        require_blocked=True,
    )

    assert validation.valid is True
    assert validation.runtime_enablement_allowed is False
    assert validation.errors == ()
    assert validation.next_action


def test_validate_runtime_enablement_operator_input_request_rejects_authority_drift(
    tmp_path: Path,
) -> None:
    request_path = _write_request(tmp_path)
    request = json.loads(request_path.read_text(encoding="utf-8"))
    request["runtime_enablement_allowed"] = True
    request["runtime_enablement_executed"] = True
    request["runtime_enablement_summary"]["runtime_dispatch_allowed"] = True
    request_path.write_text(json.dumps(request), encoding="utf-8")

    validation = validate_runtime_enablement_operator_input_request(
        request_path=request_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert any("runtime_enablement_allowed" in error for error in validation.errors)
    assert any("runtime_enablement_executed" in error for error in validation.errors)
    assert "runtime_enablement_summary.runtime_dispatch_allowed is invalid" in validation.errors


def test_validate_runtime_enablement_operator_input_request_rejects_secret_marker(
    tmp_path: Path,
) -> None:
    request_path = _write_request(tmp_path)
    request = json.loads(request_path.read_text(encoding="utf-8"))
    request["next_action"] = "bind client_secret=must-not-serialize"
    request_path.write_text(json.dumps(request), encoding="utf-8")

    validation = validate_runtime_enablement_operator_input_request(
        request_path=request_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert any("secret marker" in error for error in validation.errors)


def test_validate_runtime_enablement_operator_input_request_rejects_witness_state_drift(
    tmp_path: Path,
) -> None:
    request_path = _write_request(tmp_path)
    request = json.loads(request_path.read_text(encoding="utf-8"))
    request["witness_validation_ok"] = False
    request["solver_outcome"] = "GovernanceBlocked"
    request["proof_state"] = "Fail"
    request_path.write_text(json.dumps(request), encoding="utf-8")

    validation = validate_runtime_enablement_operator_input_request(
        request_path=request_path,
        schema_path=SCHEMA_PATH,
    )

    assert validation.valid is False
    assert "invalid witness requests must ask for valid_runtime_enablement_witness" in validation.errors


def test_validate_runtime_enablement_operator_input_request_cli_writes_receipt(
    tmp_path: Path,
    capsys,
) -> None:
    request_path = _write_request(tmp_path)
    output_path = tmp_path / "runtime_enablement_operator_input_request_validation.json"
    validation = validate_runtime_enablement_operator_input_request(
        request_path=request_path,
        schema_path=SCHEMA_PATH,
        require_blocked=True,
    )

    written = write_runtime_enablement_operator_input_request_validation(
        validation,
        output_path,
    )
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
    assert payload["runtime_enablement_allowed"] is False
    assert stdout_payload["next_action"] == payload["next_action"]
    assert captured.err == ""


def _write_request(tmp_path: Path) -> Path:
    request_path = tmp_path / "read_only_worker_runtime_enablement_operator_input_request.json"
    request = emit_runtime_enablement_operator_input_request(schema_path=SCHEMA_PATH)
    write_runtime_enablement_operator_input_request(request, request_path)
    return request_path
