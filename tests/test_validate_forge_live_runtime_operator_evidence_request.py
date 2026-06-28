"""Forge live-runtime operator evidence request validator tests.

Purpose: verify the Forge live-runtime operator evidence request stays
non-executing, redacted, and aligned with the evidence-chain read model.
Governance scope: operator evidence refs, secret exclusion, execution denial,
authority denial, source read-model binding, and fixture drift rejection.
Dependencies: scripts.validate_forge_live_runtime_operator_evidence_request.
Invariants:
  - The Foundation fixture is deterministic and schema-backed.
  - The request never executes live probes.
  - Secret values are not serialized.
  - Runtime, production, commit, external-effect, and terminal closure
    authority remain false.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gateway.forge_state_write_admission import build_foundation_forge_live_runtime_operator_evidence_request
from scripts.validate_forge_live_runtime_operator_evidence_request import (
    DEFAULT_REQUEST,
    DEFAULT_SCHEMA,
    validate_forge_live_runtime_operator_evidence_request,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


def test_checked_in_forge_live_runtime_operator_evidence_request_is_valid() -> None:
    validation, produced_request = validate_forge_live_runtime_operator_evidence_request()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.request_id == "forge-live-runtime-operator-evidence-request.v1"
    assert validation.request_status == "blocked_awaiting_operator_live_evidence_refs"
    assert validation.required_input_count == 10
    assert validation.blocked_reason_count == 10
    assert produced_request["execution_allowed"] is False
    assert produced_request["secret_values_serialized"] is False


def test_produced_operator_evidence_request_matches_schema() -> None:
    request = build_foundation_forge_live_runtime_operator_evidence_request()
    errors = _validate_schema_instance(_load_schema(DEFAULT_SCHEMA), request)

    assert errors == []
    assert request["request_mode"] == "operator_live_evidence_refs_required"
    assert len(request["required_inputs"]) == 10
    assert all(item["current_state"] == "missing" for item in request["required_inputs"])
    assert all(item["secret_values_allowed"] is False for item in request["required_inputs"])


def test_validator_rejects_execution_and_secret_overclaim(tmp_path: Path) -> None:
    request = _load_request()
    request["execution_allowed"] = True
    request["external_effect_performed"] = True
    request["secret_values_serialized"] = True
    request_path = _write_request(tmp_path, request)

    validation, _produced_request = validate_forge_live_runtime_operator_evidence_request(
        schema_path=DEFAULT_SCHEMA,
        request_path=request_path,
    )

    assert validation.ok is False
    assert any("execution_allowed" in error for error in validation.errors)
    assert any("external_effect_performed" in error for error in validation.errors)
    assert any("secret_values_serialized" in error for error in validation.errors)


def test_validator_rejects_required_input_overclaim(tmp_path: Path) -> None:
    request = _load_request()
    item = request["required_inputs"][0]
    item["current_state"] = "present"
    item["secret_values_allowed"] = True
    item["execution_allowed_after_input"] = True
    item["required_evidence_classes"] = ["operator_approval_ref"]
    request_path = _write_request(tmp_path, request)

    validation, _produced_request = validate_forge_live_runtime_operator_evidence_request(
        schema_path=DEFAULT_SCHEMA,
        request_path=request_path,
    )

    assert validation.ok is False
    assert any("managed_key_custody.current_state" in error for error in validation.errors)
    assert any("managed_key_custody.secret_values_allowed" in error for error in validation.errors)
    assert any("managed_key_custody.execution_allowed_after_input" in error for error in validation.errors)
    assert any("managed_key_custody.required_evidence_classes" in error for error in validation.errors)


def test_validator_rejects_order_and_count_drift(tmp_path: Path) -> None:
    request = _load_request()
    items = request["required_inputs"]
    request["required_inputs"] = [items[1], items[0], *items[2:]]
    request["required_input_count"] = 9
    request["blocked_reasons"] = request["blocked_reasons"][1:]
    request_path = _write_request(tmp_path, request)

    validation, _produced_request = validate_forge_live_runtime_operator_evidence_request(
        schema_path=DEFAULT_SCHEMA,
        request_path=request_path,
    )

    assert validation.ok is False
    assert any("required_inputs order drift" in error for error in validation.errors)
    assert any("required_input_count drift" in error for error in validation.errors)
    assert any("blocked_reasons drift" in error for error in validation.errors)


def test_validator_rejects_runtime_authority_overclaim(tmp_path: Path) -> None:
    request = _load_request()
    request["disallowed_authority"]["state_write_runtime_registered"] = True
    request["disallowed_authority"]["production_authorized"] = True
    request["disallowed_authority"]["terminal_closure"] = True
    request_path = _write_request(tmp_path, request)

    validation, _produced_request = validate_forge_live_runtime_operator_evidence_request(
        schema_path=DEFAULT_SCHEMA,
        request_path=request_path,
    )

    assert validation.ok is False
    assert any("state_write_runtime_registered" in error for error in validation.errors)
    assert any("production_authorized" in error for error in validation.errors)
    assert any("terminal_closure" in error for error in validation.errors)


def test_validator_rejects_source_read_model_hash_drift(tmp_path: Path) -> None:
    request = _load_request()
    request["source_evidence_chain_read_model_hash"] = "0" * 64
    request_path = _write_request(tmp_path, request)

    validation, _produced_request = validate_forge_live_runtime_operator_evidence_request(
        schema_path=DEFAULT_SCHEMA,
        request_path=request_path,
    )

    assert validation.ok is False
    assert any("source_evidence_chain_read_model_hash mismatch" in error for error in validation.errors)
    assert any("fixture does not match deterministic" in error for error in validation.errors)


def _load_request() -> dict[str, Any]:
    return json.loads(DEFAULT_REQUEST.read_text(encoding="utf-8"))


def _write_request(tmp_path: Path, request: dict[str, Any]) -> Path:
    request_path = tmp_path / "forge_live_runtime_operator_evidence_request.foundation.json"
    request_path.write_text(json.dumps(request, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return request_path
