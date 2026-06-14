"""Purpose: verify SNet episode replay schema and validator behavior.
Governance scope: deterministic SNet episode replay, answer-binding bounds,
    receipt drift rejection, and execution-authority denial.
Dependencies: scripts.validate_snet_episode_replay and SNet read model
contracts.
Invariants:
  - SNet episodes replay to their expected receipt.
  - Answer drift changes replay evidence and is rejected.
  - Episode replay grants no authority.
"""

from __future__ import annotations

import json

from scripts import validate_snet_episode_replay as validator


EXAMPLE_EPISODE_PATH = validator.WORKSPACE_ROOT / "examples" / "snet_episode_seed_dependency.json"


def test_snet_episode_replay_contract_passes() -> None:
    errors = validator.validate_contract()
    sample_episode = validator.build_sample_episode()
    schema = validator._load_schema(validator.DEFAULT_SCHEMA_PATH)

    assert errors == []
    assert sample_episode["surface"] == "snet_episode_replay"
    assert sample_episode["replay_mode"] == "deterministic_local"
    assert sample_episode["tick_scope"] == "root_single_tick"
    assert sample_episode["raw_answers_bounded"] is True
    assert sample_episode["raw_answers_exposed"] is False
    assert sample_episode["execution_authority_granted"] is False
    assert validator.validate_episode(sample_episode, schema) == []


def test_snet_episode_replay_is_deterministic() -> None:
    first_episode = validator.build_sample_episode()
    second_episode = validator.build_sample_episode()
    first_replay = validator.replay_episode(first_episode).to_json_dict()
    second_replay = validator.replay_episode(second_episode).to_json_dict()

    assert first_episode["episode_id"] == second_episode["episode_id"]
    assert first_episode["input_digest"] == second_episode["input_digest"]
    assert first_replay["mesh_digest"] == second_replay["mesh_digest"]
    assert first_replay["receipt_id"] == second_replay["receipt_id"]


def test_snet_episode_rejects_answer_drift() -> None:
    episode = validator.build_sample_episode()
    schema = validator._load_schema(validator.DEFAULT_SCHEMA_PATH)
    original_digest = episode["expected_mesh_digest"]
    episode["answer_bindings"]["depends_on"] = "Sunlight"

    errors = validator.validate_episode(episode, schema)
    replay_digest = validator.replay_episode(episode).mesh_digest

    assert any("input_digest" in error for error in errors)
    assert any("expected_mesh_digest" in error for error in errors)
    assert replay_digest != original_digest


def test_snet_episode_rejects_authority_and_raw_field_mutations() -> None:
    schema = validator._load_schema(validator.DEFAULT_SCHEMA_PATH)
    raw_episode = validator.build_sample_episode()
    raw_episode["raw_answers"] = ["Water"]
    authority_episodes = {
        field_name: validator.build_sample_episode()
        for field_name in (
            "execution_authority_granted",
            "connector_authority_granted",
            "route_authority_granted",
            "filesystem_authority_granted",
        )
    }
    for field_name, episode in authority_episodes.items():
        episode[field_name] = True

    raw_errors = validator.validate_episode(raw_episode, schema)
    authority_errors = {
        field_name: validator.validate_episode(episode, schema)
        for field_name, episode in authority_episodes.items()
    }

    assert any("raw_answers" in error for error in raw_errors)
    assert all(any(field_name in error for error in errors) for field_name, errors in authority_errors.items())
    assert raw_episode["expected_receipt"]["receipt_is_not_terminal_closure"] is True


def test_snet_episode_rejects_expected_count_drift() -> None:
    episode = validator.build_sample_episode()
    schema = validator._load_schema(validator.DEFAULT_SCHEMA_PATH)
    episode["expected_counts"]["symbol_count"] = episode["expected_counts"]["symbol_count"] + 1

    errors = validator.validate_episode(episode, schema)

    assert any("expected_counts.symbol_count" in error for error in errors)
    assert episode["expected_receipt"]["symbol_count"] != episode["expected_counts"]["symbol_count"]
    assert episode["expected_receipt"]["mesh_digest"] == episode["expected_mesh_digest"]


def test_snet_episode_malformed_answer_bindings_report_errors() -> None:
    episode = validator.build_sample_episode()
    schema = validator._load_schema(validator.DEFAULT_SCHEMA_PATH)
    episode["answer_bindings"] = ["Water"]

    errors = validator.validate_episode(episode, schema)

    assert any("answer_bindings" in error for error in errors)
    assert any("replay failed" in error for error in errors)
    assert episode["raw_answers_exposed"] is False


def test_snet_episode_non_json_replay_inputs_report_errors() -> None:
    schema = validator._load_schema(validator.DEFAULT_SCHEMA_PATH)
    non_finite_episode = validator.build_sample_episode()
    non_finite_episode["confidence"] = float("nan")
    non_json_episode = validator.build_sample_episode()
    non_json_episode["answer_bindings"]["depends_on"] = object()

    non_finite_errors = validator.validate_episode(non_finite_episode, schema)
    non_json_errors = validator.validate_episode(non_json_episode, schema)

    assert any("replay input digest failed" in error for error in non_finite_errors)
    assert any("Out of range float values" in error for error in non_finite_errors)
    assert any("not JSON serializable" in error for error in non_json_errors)
    assert non_finite_episode["raw_answers_exposed"] is False


def test_snet_episode_malformed_expected_receipt_report_errors() -> None:
    schema = validator._load_schema(validator.DEFAULT_SCHEMA_PATH)
    non_object_episode = validator.build_sample_episode()
    non_object_episode["expected_receipt"] = None

    errors = validator.validate_episode(non_object_episode, schema)

    assert any("expected_receipt must be a JSON object" in error for error in errors)
    assert any("expected_receipt must match replay receipt" in error for error in errors)
    assert non_object_episode["execution_authority_granted"] is False


def test_snet_episode_saved_file_validation(tmp_path) -> None:
    episode_path = tmp_path / "snet_episode.json"
    episode_path.write_text(json.dumps(validator.build_sample_episode()), encoding="utf-8")

    episode = validator.load_json_object(episode_path, "SNet episode")
    errors = validator.validate_episode(episode)

    assert errors == []
    assert episode["episode_id"].startswith("snet-episode-")
    assert episode["expected_receipt_id"].startswith("snet-mesh-")
    assert episode["evidence_refs"]


def test_committed_snet_episode_example_replays_to_expected_receipt() -> None:
    episode = validator.load_json_object(EXAMPLE_EPISODE_PATH, "SNet episode example")
    errors = validator.validate_episode(episode)
    replay_receipt = validator.replay_episode(episode).to_json_dict()

    assert errors == []
    assert episode["expected_receipt"] == replay_receipt
    assert episode["expected_mesh_digest"] == replay_receipt["mesh_digest"]
    assert episode["expected_receipt_id"] == replay_receipt["receipt_id"]
