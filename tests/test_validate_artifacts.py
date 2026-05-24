"""Tests for shipped artifact validation bounded errors.

Purpose: prove artifact validation reports stable failure categories without
reflecting raw JSON, OS, or template exception text.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.validate_artifacts.
Invariants:
  - Malformed JSON details are categorical.
  - Filesystem read failures do not echo OS exception text.
  - Template validation reports expose stable codes, not exception bodies.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import scripts.validate_artifacts as artifact_validator
from scripts.validate_artifacts import (
    _load_json_object,
    validate_config_artifact,
    validate_request_artifact,
)


def test_load_json_object_bounds_malformed_json_detail(tmp_path: Path) -> None:
    artifact_path = tmp_path / "request.json"
    artifact_path.write_text('{"secret": "secret-json-token",', encoding="utf-8")

    with pytest.raises(ValueError) as exc_info:
        _load_json_object(artifact_path, kind="request")

    message = str(exc_info.value)
    assert message.endswith("invalid request JSON")
    assert "secret-json-token" not in message
    assert "Expecting" not in message


def test_validate_config_artifact_bounds_read_error_detail(tmp_path: Path) -> None:
    directory_path = tmp_path / "config.json"
    directory_path.mkdir()

    errors = validate_config_artifact(directory_path)

    assert len(errors) == 1
    assert errors[0].endswith("cannot read config artifact")
    assert "Permission" not in errors[0]
    assert "denied" not in errors[0].lower()


def test_validate_request_artifact_bounds_template_error_detail(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request_path = tmp_path / "request.json"
    request_path.write_text(
        json.dumps(
            {
                "request_id": "bounded-template-error",
                "subject_id": "operator",
                "goal_id": "run-print",
                "template": {
                    "template_id": "python-print-tpl",
                    "action_type": "shell_command",
                    "command_argv": ["python", "-c", "print('ok')"],
                },
                "bindings": {},
            }
        ),
        encoding="utf-8",
    )

    class RaisingTemplateValidator:
        def validate(self, _template, _bindings):
            raise artifact_validator.TemplateValidationError(
                "malformed_template",
                "secret-template-body",
            )

    monkeypatch.setattr(artifact_validator, "TemplateValidator", RaisingTemplateValidator)

    errors = validate_request_artifact(request_path)

    assert errors == [f"{request_path.as_posix()}: invalid request template malformed_template"]
    assert all("secret-template-body" not in error for error in errors)


def test_mcoi_contract_runtime_fixture_inventory_is_registered() -> None:
    inventory = artifact_validator.discover_example_inventory()
    actual_names = {path.name for path in inventory.mcoi_runtime_fixture_paths}
    contract_fixture_names = set(artifact_validator.MCOI_CONTRACT_RUNTIME_FIXTURE_TYPES)

    assert len(contract_fixture_names) == 68
    assert contract_fixture_names <= actual_names
    assert actual_names == set(artifact_validator.MCOI_RUNTIME_FIXTURE_VALIDATORS)


def test_mcoi_contract_runtime_fixture_validator_accepts_imported_fixture() -> None:
    fixture_path = Path("integration/contracts_compat/fixtures/mcoi_runtime/access_audit_record.json")

    errors = artifact_validator.validate_mcoi_runtime_fixture(fixture_path)

    assert errors == []
    assert fixture_path.name in artifact_validator.MCOI_CONTRACT_RUNTIME_FIXTURE_TYPES
    assert fixture_path.name in artifact_validator.MCOI_RUNTIME_FIXTURE_VALIDATORS


def test_mcoi_contract_runtime_fixture_validator_bounds_enum_errors(tmp_path: Path) -> None:
    fixture_path = Path("integration/contracts_compat/fixtures/mcoi_runtime/access_audit_record.json")
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    payload["decision"] = "secret-invalid-decision"
    invalid_fixture_path = tmp_path / fixture_path.name
    invalid_fixture_path.write_text(json.dumps(payload), encoding="utf-8")

    errors = artifact_validator.validate_mcoi_runtime_fixture(invalid_fixture_path)

    assert errors == [f"{invalid_fixture_path.as_posix()}: field 'decision' has invalid enum value"]
    assert "secret-invalid-decision" not in errors[0]
    assert "AccessDecision" not in errors[0]
