"""Tests for read-only worker runtime enablement operator input emission.

Purpose: prove runtime enablement witness blockers become public-safe operator
input requests.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.emit_read_only_worker_runtime_enablement_operator_input_request.
Invariants:
  - Runtime enablement remains blocked.
  - Missing evidence names are explicit.
  - Secret values and runtime execution claims are not serialized.
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
    main,
    write_runtime_enablement_operator_input_request,
)


SCHEMA_PATH = (
    _ROOT
    / "schemas"
    / "read_only_worker_runtime_enablement_operator_input_request.schema.json"
)


def test_runtime_enablement_operator_input_request_reports_missing_evidence() -> None:
    request = emit_runtime_enablement_operator_input_request(schema_path=SCHEMA_PATH)
    required_names = {
        name
        for item in request.required_inputs
        for name in item.required_names
    }
    input_kinds = {item.input_kind for item in request.required_inputs}
    rendered = json.dumps(request.as_dict(), sort_keys=True)

    assert request.request_id.startswith("read-only-worker-runtime-enablement-input-request-")
    assert request.ready is False
    assert request.runtime_enablement_allowed is False
    assert request.witness_validation_ok is True
    assert request.solver_outcome == "AwaitingEvidence"
    assert request.proof_state == "Unknown"
    assert request.no_secret_values_serialized is True
    assert request.runtime_enablement_executed is False
    assert request.runtime_dispatch_performed is False
    assert request.worker_invocation_performed is False
    assert request.runtime_receipt_emitted is False
    assert request.receipt_append_performed is False
    assert request.terminal_closure_performed is False
    assert {
        "read_only_worker_terminal_closure_certificate",
        "read_only_worker_runtime_runner_registration_receipt",
        "read_only_worker_runtime_dispatch_endpoint_registration_receipt",
        "read_only_worker_runtime_receipt_emitter_registration_receipt",
        "read_only_worker_runtime_receipt_store_activation_receipt",
        "MULLU_READ_ONLY_WORKER_RUNTIME_ENABLEMENT_APPROVAL_REF",
        "read_only_worker_active_runtime_lease_observation",
        "read_only_worker_uao_dispatch_authorization_receipt",
        "read_only_worker_phi_gov_dispatch_authorization_receipt",
        "read_only_worker_runtime_dispatch_admission_receipt",
        "read_only_worker_runtime_disablement_rollback_plan",
        "read_only_worker_trusted_runtime_clock_receipt",
    } <= required_names
    assert {
        "terminal_closure_certificate",
        "runtime_runner_registration",
        "runtime_dispatch_endpoint_registration",
        "runtime_receipt_emitter_registration",
        "runtime_receipt_store_activation",
        "operator_runtime_enablement_approval",
        "active_runtime_lease_observation",
        "uao_dispatch_authorization",
        "phi_gov_dispatch_authorization",
        "runtime_dispatch_admission",
        "runtime_disablement_rollback_plan",
        "trusted_runtime_clock",
    } <= input_kinds
    assert "client_secret" not in rendered
    assert "secret-value" not in rendered


def test_runtime_enablement_operator_input_request_cli_writes_report(
    tmp_path: Path,
    capsys,
) -> None:
    output_path = tmp_path / "runtime_enablement_operator_input_request.json"
    request = emit_runtime_enablement_operator_input_request(schema_path=SCHEMA_PATH)

    written = write_runtime_enablement_operator_input_request(request, output_path)
    exit_code = main(
        [
            "--schema",
            str(SCHEMA_PATH),
            "--output",
            str(output_path),
            "--json",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(captured.out)

    assert written == output_path
    assert exit_code == 0
    assert payload["runtime_enablement_allowed"] is False
    assert payload["required_inputs"]
    assert stdout_payload["next_action"] == payload["next_action"]
    assert captured.err == ""


def test_runtime_enablement_operator_input_request_handles_invalid_witness(
    tmp_path: Path,
) -> None:
    witness_path = tmp_path / "read_only_worker_runtime_enablement_witness.json"
    witness = json.loads(
        (
            _ROOT
            / "examples"
            / "read_only_worker_runtime_enablement_witness.foundation.json"
        ).read_text(encoding="utf-8")
    )
    witness["authority_scope"]["runtime_enablement_performed"] = True
    witness_path.write_text(json.dumps(witness), encoding="utf-8")

    request = emit_runtime_enablement_operator_input_request(
        witness_path=witness_path,
        schema_path=SCHEMA_PATH,
    )

    assert request.witness_validation_ok is False
    assert request.solver_outcome == "GovernanceBlocked"
    assert request.proof_state == "Fail"
    assert request.required_inputs[0].input_kind == "valid_runtime_enablement_witness"
