"""General-agent promotion environment binding validation tests."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_general_agent_promotion_environment_bindings import (
    main,
    validate_general_agent_promotion_environment_bindings,
)


CONTRACT_PATH = Path("examples") / "general_agent_promotion_environment_bindings.json"


def test_validate_environment_bindings_accepts_example() -> None:
    result = validate_general_agent_promotion_environment_bindings()

    assert result.valid is True
    assert result.contract_id == "general-agent-promotion-environment-bindings-v1"
    assert result.binding_count == 7
    assert "MULLU_GATEWAY_URL" in result.required_names
    assert "MULLU_DEPLOYMENT_WITNESS_SECRET" in result.required_names
    assert result.errors == ()


def test_validate_environment_bindings_rejects_serialized_secret(tmp_path: Path) -> None:
    contract_path = tmp_path / "environment-bindings.json"
    payload = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    for binding in payload["bindings"]:
        if binding["name"] == "MULLU_RUNTIME_WITNESS_SECRET":
            binding["may_serialize_value"] = True
    contract_path.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_general_agent_promotion_environment_bindings(contract_path=contract_path)

    assert result.valid is False
    assert result.binding_count == 7
    assert any("may_serialize_value" in error for error in result.errors)


def test_validate_environment_bindings_rejects_checklist_drift(tmp_path: Path) -> None:
    checklist_path = tmp_path / "checklist.json"
    checklist_payload = {
        "required_environment_variables": [
            "MULLU_GATEWAY_URL",
            "MULLU_RUNTIME_WITNESS_SECRET",
        ]
    }
    checklist_path.write_text(json.dumps(checklist_payload), encoding="utf-8")

    result = validate_general_agent_promotion_environment_bindings(checklist_path=checklist_path)

    assert result.valid is False
    assert result.binding_count == 7
    assert any("binding names must match checklist" in error for error in result.errors)


def test_validate_environment_bindings_cli_outputs_json(capsys) -> None:
    exit_code = main(["--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["valid"] is True
    assert payload["binding_count"] == 7
    assert "MULLU_AUTHORITY_OPERATOR_SECRET" in payload["required_names"]
    assert "MULLU_DEPLOYMENT_WITNESS_SECRET" in payload["required_names"]


def test_validate_environment_bindings_missing_file_error_is_bounded(tmp_path: Path) -> None:
    contract_path = tmp_path / "secret-contract-path.json"

    result = validate_general_agent_promotion_environment_bindings(contract_path=contract_path)
    serialized_errors = json.dumps(result.errors, sort_keys=True)

    assert result.valid is False
    assert "environment binding contract could not be read" in result.errors
    assert "secret-contract-path" not in serialized_errors


def test_validate_environment_bindings_json_parse_error_is_bounded(tmp_path: Path) -> None:
    contract_path = tmp_path / "environment-bindings.json"
    contract_path.write_text('{"contract_id": "secret-json-token"', encoding="utf-8")

    result = validate_general_agent_promotion_environment_bindings(contract_path=contract_path)
    serialized_errors = json.dumps(result.errors, sort_keys=True)

    assert result.valid is False
    assert "environment binding contract must be JSON" in result.errors
    assert "secret-json-token" not in serialized_errors
