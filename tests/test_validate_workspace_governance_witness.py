"""Purpose: verify workspace governance witness contract validation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.validate_workspace_governance_witness.
Invariants:
  - The live witness references repository-local files only.
  - Witness artifact count, names, paths, and governance scopes are explicit.
  - Missing or unexpected canonical artifacts fail closed.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts import validate_workspace_governance_witness as validator


def test_current_witness_contract_passes() -> None:
    witness = validator.load_json_object(validator.DEFAULT_WITNESS_PATH, "witness")
    schema = validator.load_json_object(validator.DEFAULT_SCHEMA_PATH, "schema")
    errors = validator.validate_contract()
    artifact_names = {artifact["name"] for artifact in witness["artifacts"]}

    assert errors == []
    assert schema["title"] == "Workspace Governance Witness"
    assert schema["$id"] == "urn:mullusi:schema:workspace-governance-witness:1"
    assert witness["artifact_count"] == len(witness["artifacts"])
    assert len(validator.REQUIRED_ARTIFACT_NAMES) == witness["artifact_count"]
    assert validator.REQUIRED_ARTIFACT_NAMES == artifact_names
    assert "workspace_governance_witness_validator" in artifact_names
    assert "governance_normalization_map_document" in artifact_names
    assert "governance_normalization_map_validator" in artifact_names
    assert "governance_normalization_map_tests" in artifact_names
    assert "life_continuity_conflict_doctrine_document" in artifact_names
    assert "life_meaning_governance_kernel_document" in artifact_names
    assert "life_meaning_judgment_schema" in artifact_names
    assert "life_meaning_governance_kernel_runtime" in artifact_names
    assert "life_meaning_governance_validator" in artifact_names
    assert "life_meaning_governance_tests" in artifact_names
    assert "universal_action_orchestration_document" in artifact_names
    assert "universal_action_orchestration_allowed_example" in artifact_names
    assert "universal_action_orchestration_gateway_replay_tests" in artifact_names
    assert "sdlc_route_helper" in artifact_names
    assert "sdlc_route_validator" in artifact_names
    assert "sdlc_route_tests" in artifact_names
    assert "governed_code_change_loop_windows_readiness_assessor" in artifact_names
    assert "governed_code_change_loop_windows_readiness_assessor_tests" in artifact_names
    assert "governed_code_change_loop_wsl_strict_probe_launcher" in artifact_names
    assert "governed_code_change_loop_wsl_strict_probe_launcher_tests" in artifact_names
    assert "universal_action_orchestration" in witness["governance_scope"]
    assert (
        "workspace governance witness omits Universal Action Orchestration artifacts"
        in witness["block_conditions"]
    )
    assert (
        "workspace governance witness omits governance normalization map artifacts"
        in witness["block_conditions"]
    )
    assert (
        "workspace governance witness omits Life-Meaning Governance Kernel artifacts"
        in witness["block_conditions"]
    )
    assert (
        "governed code-change loop Windows readiness assessor contract is missing or drifted"
        in witness["block_conditions"]
    )
    assert (
        "governed code-change loop WSL launcher contract is missing or drifted"
        in witness["block_conditions"]
    )
    assert (
        "governance integrity report omits a digest for an existing artifact"
        in witness["block_conditions"]
    )


def test_artifact_count_mismatch_is_reported() -> None:
    witness = validator.load_json_object(validator.DEFAULT_WITNESS_PATH, "witness")
    invalid_witness = copy.deepcopy(witness)
    invalid_witness["artifact_count"] += 1

    errors = validator.validate_witness(invalid_witness)

    assert "artifact_count must match artifacts length" in errors
    assert invalid_witness["artifact_count"] == witness["artifact_count"] + 1
    assert len(errors) >= 1


def test_duplicate_artifact_name_and_path_are_reported() -> None:
    witness = validator.load_json_object(validator.DEFAULT_WITNESS_PATH, "witness")
    invalid_witness = copy.deepcopy(witness)
    invalid_witness["artifacts"][1]["name"] = invalid_witness["artifacts"][0]["name"]
    invalid_witness["artifacts"][1]["path"] = invalid_witness["artifacts"][0]["path"]

    errors = validator.validate_witness(invalid_witness)

    assert any("duplicate artifact name" in error for error in errors)
    assert any("duplicate artifact path" in error for error in errors)
    assert len(errors) >= 2


def test_unsafe_artifact_path_is_reported() -> None:
    witness = validator.load_json_object(validator.DEFAULT_WITNESS_PATH, "witness")
    invalid_witness = copy.deepcopy(witness)
    invalid_witness["artifacts"][0]["path"] = "../AGENTS.md"

    errors = validator.validate_witness(invalid_witness)

    assert any("path invalid" in error for error in errors)
    assert any("path segments must be explicit repository-local names" in error for error in errors)
    assert invalid_witness["artifacts"][0]["path"] == "../AGENTS.md"


def test_missing_required_scope_is_reported() -> None:
    witness = validator.load_json_object(validator.DEFAULT_WITNESS_PATH, "witness")
    invalid_witness = copy.deepcopy(witness)
    invalid_witness["governance_scope"] = [
        scope for scope in invalid_witness["governance_scope"] if scope != "governance_artifact_integrity"
    ]

    errors = validator.validate_witness(invalid_witness)

    assert any("governance_scope missing required value" in error for error in errors)
    assert any("governance_artifact_integrity" in error for error in errors)
    assert len(invalid_witness["governance_scope"]) == len(witness["governance_scope"]) - 1


def test_unexpected_governance_scope_is_reported() -> None:
    witness = validator.load_json_object(validator.DEFAULT_WITNESS_PATH, "witness")
    invalid_witness = copy.deepcopy(witness)
    invalid_witness["governance_scope"].append("unbounded_external_governance")

    errors = validator.validate_witness(invalid_witness)

    assert any("governance_scope has unexpected value" in error for error in errors)
    assert any("unbounded_external_governance" in error for error in errors)
    assert len(invalid_witness["governance_scope"]) == len(witness["governance_scope"]) + 1


def test_unexpected_block_condition_is_reported() -> None:
    witness = validator.load_json_object(validator.DEFAULT_WITNESS_PATH, "witness")
    invalid_witness = copy.deepcopy(witness)
    invalid_witness["block_conditions"].append("unbounded silent witness bypass")

    errors = validator.validate_witness(invalid_witness)

    assert any("block_conditions has unexpected value" in error for error in errors)
    assert any("unbounded silent witness bypass" in error for error in errors)
    assert len(invalid_witness["block_conditions"]) == len(witness["block_conditions"]) + 1


def test_missing_universal_action_orchestration_scope_is_reported() -> None:
    witness = validator.load_json_object(validator.DEFAULT_WITNESS_PATH, "witness")
    invalid_witness = copy.deepcopy(witness)
    invalid_witness["governance_scope"] = [
        scope
        for scope in invalid_witness["governance_scope"]
        if scope != "universal_action_orchestration"
    ]

    errors = validator.validate_witness(invalid_witness)

    assert any("governance_scope missing required value" in error for error in errors)
    assert any("universal_action_orchestration" in error for error in errors)
    assert len(invalid_witness["governance_scope"]) == len(witness["governance_scope"]) - 1


def test_missing_required_artifact_name_is_reported() -> None:
    witness = validator.load_json_object(validator.DEFAULT_WITNESS_PATH, "witness")
    invalid_witness = copy.deepcopy(witness)
    invalid_witness["artifacts"] = [
        artifact for artifact in invalid_witness["artifacts"] if artifact["name"] != "workspace_governance_witness_tests"
    ]
    invalid_witness["artifact_count"] = len(invalid_witness["artifacts"])

    errors = validator.validate_witness(invalid_witness)

    assert any("witness missing required artifact name" in error for error in errors)
    assert any("workspace_governance_witness_tests" in error for error in errors)
    assert invalid_witness["artifact_count"] == witness["artifact_count"] - 1


def test_missing_canonical_artifact_fails_with_adjusted_count() -> None:
    witness = validator.load_json_object(validator.DEFAULT_WITNESS_PATH, "witness")
    invalid_witness = copy.deepcopy(witness)
    invalid_witness["artifacts"] = [
        artifact for artifact in invalid_witness["artifacts"] if artifact["name"] != "agents_policy"
    ]
    invalid_witness["artifact_count"] = len(invalid_witness["artifacts"])

    errors = validator.validate_witness(invalid_witness)

    assert "artifact_count must match artifacts length" not in errors
    assert any("witness missing required artifact name" in error for error in errors)
    assert any("agents_policy" in error for error in errors)
    assert invalid_witness["artifact_count"] == witness["artifact_count"] - 1


def test_missing_universal_action_orchestration_artifact_name_is_reported() -> None:
    witness = validator.load_json_object(validator.DEFAULT_WITNESS_PATH, "witness")
    invalid_witness = copy.deepcopy(witness)
    invalid_witness["artifacts"] = [
        artifact
        for artifact in invalid_witness["artifacts"]
        if artifact["name"] != "universal_action_orchestration_document"
    ]
    invalid_witness["artifact_count"] = len(invalid_witness["artifacts"])

    errors = validator.validate_witness(invalid_witness)

    assert any("witness missing required artifact name" in error for error in errors)
    assert any("universal_action_orchestration_document" in error for error in errors)
    assert invalid_witness["artifact_count"] == witness["artifact_count"] - 1


def test_unexpected_canonical_artifact_fails_with_adjusted_count() -> None:
    witness = validator.load_json_object(validator.DEFAULT_WITNESS_PATH, "witness")
    invalid_witness = copy.deepcopy(witness)
    invalid_witness["artifacts"].append(
        {
            "name": "unexpected_governance_artifact",
            "path": "README.md",
            "purpose": "unexpected artifact outside the canonical witness contract",
        }
    )
    invalid_witness["artifact_count"] = len(invalid_witness["artifacts"])

    errors = validator.validate_witness(invalid_witness)

    assert "artifact_count must match artifacts length" not in errors
    assert not any("witness missing required artifact name" in error for error in errors)
    assert any("witness has unexpected artifact name" in error for error in errors)
    assert any("unexpected_governance_artifact" in error for error in errors)


def test_schema_artifact_rejects_missing_required_field() -> None:
    schema = validator.load_json_object(validator.DEFAULT_SCHEMA_PATH, "schema")
    invalid_schema = copy.deepcopy(schema)
    invalid_schema["required"] = [field for field in invalid_schema["required"] if field != "block_conditions"]

    errors = validator.validate_schema_artifact(invalid_schema)

    assert any("schema missing required witness field: block_conditions" in error for error in errors)
    assert "block_conditions" not in invalid_schema["required"]
    assert len(errors) >= 1


def test_cli_passes(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = validator.main([])
    streams = capsys.readouterr()

    assert exit_code == 0
    assert "[PASS] workspace_governance_witness_artifacts" in streams.out
    assert streams.err == ""


def test_load_json_object_rejects_non_object_json(tmp_path: Path) -> None:
    json_path = tmp_path / "payload.json"
    json_path.write_text(json.dumps(["not", "object"]), encoding="utf-8")

    with pytest.raises(ValueError):
        validator.load_json_object(json_path, "payload")

    assert json_path.exists()
    assert json_path.name == "payload.json"
