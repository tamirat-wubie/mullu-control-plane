"""Tests for deployment orchestration receipt validation.

Purpose: verify orchestration receipts can be used as deterministic handoff
gates after deployment witness orchestration runs.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.validate_deployment_orchestration_receipt.
Invariants:
  - Missing required receipt fields fail validation.
  - MCP checklist, preflight, dispatch, and success gates fail closed.
  - Validation reports are persisted as structured JSON.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import scripts.validate_deployment_orchestration_receipt as orchestration_validator
from scripts.provision_deployment_target import DEFAULT_REPOSITORY
from scripts.validate_deployment_orchestration_receipt import (
    ORCHESTRATION_RECEIPT_SCHEMA_PATH,
    _check_schema_contract,
    main,
    validate_deployment_orchestration_receipt,
    write_orchestration_receipt_validation_report,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


def test_valid_orchestration_receipt_satisfies_handoff_policy(tmp_path: Path) -> None:
    receipt_path = tmp_path / "orchestration.json"
    output_path = tmp_path / "validation.json"
    _write_receipt(receipt_path, preflight_ready=True, mcp_checklist_valid=True)

    validation = validate_deployment_orchestration_receipt(
        receipt_path=receipt_path,
        require_preflight=True,
        require_mcp_operator_checklist=True,
        expected_gateway_host="gateway.mullusi.com",
    )
    write_orchestration_receipt_validation_report(validation, output_path)
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert validation.valid is True
    assert validation.receipt_id.startswith("deployment-witness-orchestration-")
    assert payload["valid"] is True
    assert _step(validation, "require preflight").passed is True
    assert _step(validation, "require mcp operator checklist").passed is True


def test_orchestration_receipt_rejects_missing_mcp_checklist_gate(tmp_path: Path) -> None:
    receipt_path = tmp_path / "orchestration.json"
    _write_receipt(receipt_path, mcp_checklist_required=False, mcp_checklist_valid=None)

    validation = validate_deployment_orchestration_receipt(
        receipt_path=receipt_path,
        require_mcp_operator_checklist=True,
    )
    checklist_step = _step(validation, "require mcp operator checklist")

    assert validation.valid is False
    assert checklist_step.passed is False
    assert "required=False" in checklist_step.detail
    assert "valid=None" in checklist_step.detail


def test_orchestration_receipt_rejects_dispatch_success_policy(tmp_path: Path) -> None:
    receipt_path = tmp_path / "orchestration.json"
    _write_receipt(
        receipt_path,
        dispatch_requested=True,
        dispatch_run_id=5678,
        dispatch_conclusion="failure",
    )

    validation = validate_deployment_orchestration_receipt(
        receipt_path=receipt_path,
        require_dispatch=True,
        require_success=True,
    )
    dispatch_step = _step(validation, "require dispatch")
    success_step = _step(validation, "require success")

    assert validation.valid is False
    assert dispatch_step.passed is True
    assert success_step.passed is False
    assert "conclusion=failure" in success_step.detail


def test_orchestration_receipt_rejects_missing_evidence_refs(tmp_path: Path) -> None:
    receipt_path = tmp_path / "orchestration.json"
    _write_receipt(receipt_path)
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    payload["evidence_refs"] = ["ingress_render:rendered.yaml"]
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_deployment_orchestration_receipt(receipt_path=receipt_path)
    evidence_step = _step(validation, "evidence refs")

    assert validation.valid is False
    assert evidence_step.passed is False
    assert "deployment_target:" in evidence_step.detail
    assert "mcp_operator_checklist:" in evidence_step.detail


def test_orchestration_receipt_rejects_missing_nullable_contract_field(tmp_path: Path) -> None:
    receipt_path = tmp_path / "orchestration.json"
    _write_receipt(receipt_path)
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    payload.pop("dispatch_run_id")
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_deployment_orchestration_receipt(receipt_path=receipt_path)
    required_step = _step(validation, "required fields")

    assert validation.valid is False
    assert required_step.passed is False
    assert "dispatch_run_id" in required_step.detail
    assert "missing=" in required_step.detail


def test_orchestration_receipt_rejects_schema_contract_violation(tmp_path: Path) -> None:
    receipt_path = tmp_path / "orchestration.json"
    _write_receipt(receipt_path)
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    payload["unexpected_authority_gap"] = "unowned"
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_deployment_orchestration_receipt(receipt_path=receipt_path)
    schema_step = _step(validation, "schema contract")

    assert validation.valid is False
    assert schema_step.passed is False
    assert "unexpected_authority_gap" in schema_step.detail
    assert "unexpected property" in schema_step.detail


def test_expected_value_mismatch_detail_is_bounded(tmp_path: Path) -> None:
    receipt_path = tmp_path / "orchestration.json"
    _write_receipt(receipt_path)

    validation = validate_deployment_orchestration_receipt(
        receipt_path=receipt_path,
        expected_gateway_url="https://private-gateway-token.mullusi.com/private-path",
    )
    expected_step = _step(validation, "expected gateway_url")

    assert validation.valid is False
    assert expected_step.passed is False
    assert expected_step.detail == "mismatched"
    assert "private-gateway-token" not in json.dumps(validation.to_json_dict(), sort_keys=True)
    assert "gateway.mullusi.com" not in expected_step.detail


def test_orchestration_receipt_schema_rejects_invalid_receipt_id_pattern(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "orchestration.json"
    _write_receipt(receipt_path)
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    payload["receipt_id"] = "deployment-witness-orchestration-not-hex"
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_deployment_orchestration_receipt(receipt_path=receipt_path)
    schema_step = _step(validation, "schema contract")
    receipt_id_step = _step(validation, "receipt id")

    assert validation.valid is False
    assert schema_step.passed is False
    assert receipt_id_step.passed is False
    assert "$.receipt_id" in schema_step.detail
    assert "pattern" in schema_step.detail


def test_orchestration_receipt_schema_rejects_missing_evidence_prefix(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "orchestration.json"
    _write_receipt(receipt_path)
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    payload["evidence_refs"] = [
        "ingress_render:.change_assurance/rendered-ingress.yaml",
        f"deployment_target:{DEFAULT_REPOSITORY}",
        "preflight:ready:true",
        "mcp_operator_checklist:valid:true",
        "mcp_operator_checklist:reviewed:true",
    ]
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_deployment_orchestration_receipt(receipt_path=receipt_path)
    schema_step = _step(validation, "schema contract")
    evidence_step = _step(validation, "evidence refs")

    assert validation.valid is False
    assert schema_step.passed is False
    assert evidence_step.passed is False
    assert "$.evidence_refs" in schema_step.detail
    assert "contains" in schema_step.detail
    assert "dispatch:" in evidence_step.detail


def test_orchestration_receipt_schema_accepts_canonical_fixture(tmp_path: Path) -> None:
    receipt_path = tmp_path / "orchestration.json"
    _write_receipt(receipt_path)
    schema = _load_schema(ORCHESTRATION_RECEIPT_SCHEMA_PATH)
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))

    errors = _validate_schema_instance(schema, payload)

    assert errors == []
    assert schema["title"] == "Deployment Orchestration Receipt"
    assert "mcp_operator_checklist_valid" in schema["required"]
    assert schema["properties"]["evidence_refs"]["minItems"] == 5


def test_cli_writes_validation_report_and_returns_nonzero(tmp_path: Path, capsys) -> None:
    receipt_path = tmp_path / "orchestration.json"
    output_path = tmp_path / "validation.json"
    _write_receipt(receipt_path, preflight_ready=False)

    exit_code = main([
        "--receipt",
        str(receipt_path),
        "--output",
        str(output_path),
        "--require-preflight",
    ])
    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 1
    assert output_path.exists()
    assert payload["valid"] is False
    assert "valid: false" in captured.out
    assert "preflight_ready=False" in captured.out


def test_missing_orchestration_receipt_file_error_is_bounded(tmp_path: Path) -> None:
    receipt_path = tmp_path / "secret-orchestration-path.json"

    with pytest.raises(RuntimeError) as exc_info:
        validate_deployment_orchestration_receipt(receipt_path=receipt_path)

    message = str(exc_info.value)
    assert message == "failed to read deployment orchestration receipt"
    assert "secret-orchestration-path" not in message


def test_invalid_orchestration_receipt_json_error_is_bounded(tmp_path: Path) -> None:
    receipt_path = tmp_path / "orchestration.json"
    receipt_path.write_text('{"receipt_id": "secret-json-token"', encoding="utf-8")

    with pytest.raises(RuntimeError) as exc_info:
        validate_deployment_orchestration_receipt(receipt_path=receipt_path)

    message = str(exc_info.value)
    assert message == "deployment orchestration receipt returned invalid JSON"
    assert "secret-json-token" not in message


def test_schema_read_failure_detail_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise_secret_path(_path: Path):
        raise OSError("secret-schema-path")

    monkeypatch.setattr(orchestration_validator, "_load_schema", _raise_secret_path)

    step = _check_schema_contract({})

    assert step.passed is False
    assert step.detail == "schema-read-failed"
    assert "secret-schema-path" not in step.detail


def _write_receipt(
    receipt_path: Path,
    *,
    preflight_required: bool = True,
    preflight_ready: bool | None = True,
    mcp_checklist_required: bool = True,
    mcp_checklist_valid: bool | None = True,
    dispatch_requested: bool = False,
    dispatch_run_id: int | None = None,
    dispatch_conclusion: str = "",
) -> None:
    payload = {
        "receipt_id": "deployment-witness-orchestration-0123456789abcdef",
        "gateway_host": "gateway.mullusi.com",
        "gateway_url": "https://gateway.mullusi.com",
        "expected_environment": "pilot",
        "repository": DEFAULT_REPOSITORY,
        "rendered_ingress_output": ".change_assurance/rendered-ingress.yaml",
        "ingress_applied": False,
        "preflight_required": preflight_required,
        "preflight_ready": preflight_ready,
        "dispatch_requested": dispatch_requested,
        "dispatch_run_id": dispatch_run_id,
        "dispatch_conclusion": dispatch_conclusion,
        "mcp_operator_checklist_required": mcp_checklist_required,
        "mcp_operator_checklist_valid": mcp_checklist_valid,
        "mcp_operator_checklist_path": "examples/mcp_operator_handoff_checklist.json",
        "evidence_refs": [
            "ingress_render:.change_assurance/rendered-ingress.yaml",
            f"deployment_target:{DEFAULT_REPOSITORY}",
            f"preflight:ready:{str(preflight_ready).lower()}",
            "dispatch:requested" if dispatch_requested else "dispatch:skipped",
            (
                f"mcp_operator_checklist:valid:{str(mcp_checklist_valid).lower()}"
                if mcp_checklist_required
                else "mcp_operator_checklist:skipped"
            ),
        ],
    }
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")


def _step(validation, name: str):
    return next(step for step in validation.steps if step.name == name)
