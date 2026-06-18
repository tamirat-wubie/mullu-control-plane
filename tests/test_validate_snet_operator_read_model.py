"""Purpose: verify SNet operator read-model schema and validator behavior.
Governance scope: schema-backed SNet operator visibility, raw-data
    suppression, bounded projection, and execution-authority denial.
Dependencies: scripts.validate_snet_operator_read_model and SNet read model
contracts.
Invariants:
  - SNet operator read models validate against the schema.
  - Raw answers and raw metadata values are rejected.
  - Execution authority is rejected.
"""

from __future__ import annotations

import json

from scripts import validate_snet_operator_read_model as validator


def test_snet_operator_read_model_contract_passes() -> None:
    errors = validator.validate_contract()
    sample_read_model = validator.build_sample_read_model()
    schema = validator._load_schema(validator.DEFAULT_SCHEMA_PATH)

    assert errors == []
    assert sample_read_model["enabled"] is True
    assert sample_read_model["surface"] == "read_only_snet_recursive_mesh"
    assert sample_read_model["raw_answers_exposed"] is False
    assert sample_read_model["raw_metadata_values_exposed"] is False
    assert sample_read_model["execution_authority_granted"] is False
    assert sample_read_model["connector_authority_granted"] is False
    assert sample_read_model["route_authority_granted"] is False
    assert sample_read_model["filesystem_authority_granted"] is False
    assert sample_read_model["episode_replay"]["surface"] == "snet_episode_replay"
    assert sample_read_model["episode_replay"]["mode"] == "deterministic_local"
    assert sample_read_model["episode_replay"]["live_execution_authority_granted"] is False
    assert sample_read_model["receipt_reconstruction"]["deterministic"] is True
    assert sample_read_model["receipt_reconstruction"]["receipt_id"] == sample_read_model["receipt"]["receipt_id"]
    assert sample_read_model["audit_explanation"]["terminal_closure_denied"] is True
    assert "snet_live_execution_authority" in sample_read_model["blocked_authorities"]
    assert validator.validate_read_model(sample_read_model, schema) == []


def test_snet_operator_read_model_rejects_raw_and_authority_mutations() -> None:
    schema = validator._load_schema(validator.DEFAULT_SCHEMA_PATH)
    raw_read_model = validator.build_sample_read_model()
    raw_field_read_model = validator.build_sample_read_model()
    authority_read_models = {
        field_name: validator.build_sample_read_model()
        for field_name in (
            "execution_authority_granted",
            "connector_authority_granted",
            "route_authority_granted",
            "filesystem_authority_granted",
        )
    }
    raw_read_model["raw_answers_exposed"] = True
    raw_field_read_model["answers"] = ["Water"]
    for field_name, read_model in authority_read_models.items():
        read_model[field_name] = True
    nested_authority_read_model = validator.build_sample_read_model()
    nested_authority_read_model["episode_replay"]["connector_authority_granted"] = True
    receipt_drift_read_model = validator.build_sample_read_model()
    receipt_drift_read_model["receipt_reconstruction"]["receipt_id"] = "snet-mesh-0000000000000000"

    raw_errors = validator.validate_read_model(raw_read_model, schema)
    raw_field_errors = validator.validate_read_model(raw_field_read_model, schema)
    authority_errors = {
        field_name: validator.validate_read_model(read_model, schema)
        for field_name, read_model in authority_read_models.items()
    }
    nested_authority_errors = validator.validate_read_model(nested_authority_read_model, schema)
    receipt_drift_errors = validator.validate_read_model(receipt_drift_read_model, schema)

    assert any("raw_answers_exposed" in error for error in raw_errors)
    assert any("answers" in error for error in raw_field_errors)
    assert all(any(field_name in error for error in errors) for field_name, errors in authority_errors.items())
    assert any("episode_replay.connector_authority_granted" in error for error in nested_authority_errors)
    assert any("receipt_reconstruction.receipt_id" in error for error in receipt_drift_errors)
    assert raw_read_model["receipt"]["receipt_is_not_terminal_closure"] is True


def test_snet_operator_read_model_saved_file_validation(tmp_path) -> None:
    read_model_path = tmp_path / "snet_operator_read_model.json"
    read_model_path.write_text(json.dumps(validator.build_sample_read_model()), encoding="utf-8")

    read_model = validator.load_json_object(read_model_path, "SNet operator read model")
    errors = validator.validate_read_model(read_model)

    assert errors == []
    assert read_model["receipt"]["receipt_id"].startswith("snet-mesh-")
    assert read_model["receipt"]["mesh_digest"].startswith("sha256:")
    assert read_model["selected_symbols"]


def test_snet_operator_read_model_rejects_count_drift() -> None:
    read_model = validator.build_sample_read_model()
    schema = validator._load_schema(validator.DEFAULT_SCHEMA_PATH)
    read_model["symbol_count"] = read_model["symbol_count"] + 1

    errors = validator.validate_read_model(read_model, schema)

    assert any("symbol_count must match receipt" in error for error in errors)
    assert any("selected symbol count" in error for error in errors)
    assert read_model["receipt"]["symbol_count"] != read_model["symbol_count"]


def test_snet_operator_read_model_rejects_symbol_raw_field() -> None:
    read_model = validator.build_sample_read_model()
    schema = validator._load_schema(validator.DEFAULT_SCHEMA_PATH)
    read_model["selected_symbols"][0]["metadata_values"] = {"why": "Seed"}

    errors = validator.validate_read_model(read_model, schema)

    assert any("metadata_values" in error for error in errors)
    assert read_model["raw_metadata_values_exposed"] is False
    assert read_model["selected_symbols"][0]["symbol_id"].startswith("snet-symbol:")


def test_snet_operator_read_model_zero_symbol_projection_is_valid() -> None:
    read_model = validator.build_sample_read_model(max_symbol_count=0)
    schema = validator._load_schema(validator.DEFAULT_SCHEMA_PATH)
    errors = validator.validate_read_model(read_model, schema)

    assert errors == []
    assert read_model["selected_symbols"] == []
    assert read_model["truncated_symbol_count"] == read_model["symbol_count"]
    assert read_model["receipt"]["symbol_count"] == read_model["symbol_count"]


def test_snet_operator_read_model_malformed_root_reports_errors() -> None:
    schema = validator._load_schema(validator.DEFAULT_SCHEMA_PATH)

    list_errors = validator.validate_read_model([{}], schema)
    string_errors = validator.validate_read_model("read-model", schema)

    assert any("read model must be a JSON object" in error for error in list_errors)
    assert any("read model must be a JSON object" in error for error in string_errors)
    assert any("expected object" in error for error in list_errors + string_errors)


def test_snet_operator_read_model_non_integer_truncation_reports_errors() -> None:
    read_model = validator.build_sample_read_model()
    schema = validator._load_schema(validator.DEFAULT_SCHEMA_PATH)
    read_model["truncated_symbol_count"] = "1"

    errors = validator.validate_read_model(read_model, schema)

    assert any("truncated_symbol_count" in error for error in errors)
    assert any("selected symbol count" in error for error in errors)
    assert read_model["raw_answers_exposed"] is False
