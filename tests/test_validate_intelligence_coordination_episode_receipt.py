"""Purpose: verify intelligence coordination episode receipt validation.
Governance scope: coordination episode schema, operator summary closure, and
private-reasoning exclusion.
Dependencies: scripts.validate_intelligence_coordination_episode_receipt.
Invariants:
  - The checked example validates and reconstructs the runtime episode contract.
  - Operator summaries cannot drift from the persisted episode.
  - Public receipts reject private reasoning fields.
"""

from __future__ import annotations

import copy

from scripts import validate_intelligence_coordination_episode_receipt as validator


def _example_payload() -> dict:
    return validator.load_json_object(validator.DEFAULT_EXAMPLE_PATH, "example")


def _schema() -> dict:
    return validator._load_schema(validator.DEFAULT_SCHEMA_PATH)


def test_current_intelligence_coordination_receipt_contract_passes() -> None:
    payload = _example_payload()
    schema = _schema()
    errors = validator.validate_contract()
    episode = validator.build_episode_from_payload(payload["episode"])

    assert errors == []
    assert schema["$id"] == "urn:mullusi:schema:intelligence-coordination-episode-receipt:1"
    assert payload["receipt_id"] == "intelligence_coordination_episode_receipt"
    assert episode.episode_id == payload["operator_summary"]["episode_id"]
    assert episode.selected_method_id == payload["operator_summary"]["selected_method_id"]
    assert episode.terminal_outcome.value == "SolvedVerified"


def test_operator_summary_method_drift_is_rejected() -> None:
    payload = _example_payload()
    invalid_payload = copy.deepcopy(payload)
    invalid_payload["operator_summary"]["selected_method_id"] = "method-causal-diagnosis"

    errors = validator.validate_receipt_payload(invalid_payload, _schema())

    assert "operator_summary.selected_method_id must match episode.selected_method_id" in errors
    assert invalid_payload["operator_summary"]["selected_method_id"] != payload["operator_summary"]["selected_method_id"]
    assert len(errors) == 1


def test_blocked_branch_count_drift_is_rejected() -> None:
    payload = _example_payload()
    invalid_payload = copy.deepcopy(payload)
    invalid_payload["operator_summary"]["blocked_branch_count"] = 0

    errors = validator.validate_receipt_payload(invalid_payload, _schema())

    assert "operator_summary.blocked_branch_count must match episode.metadata.blocked_branch_ids" in errors
    assert invalid_payload["operator_summary"]["blocked_branch_count"] == 0
    assert len(errors) == 1


def test_private_reasoning_field_is_rejected() -> None:
    payload = _example_payload()
    invalid_payload = copy.deepcopy(payload)
    invalid_payload["episode"]["metadata"]["private_reasoning"] = "not public receipt material"

    errors = validator.validate_receipt_payload(invalid_payload, _schema())

    assert any("prohibited private reasoning field: private_reasoning" in error for error in errors)
    assert invalid_payload["episode"]["metadata"]["private_reasoning"] == "not public receipt material"
    assert len(errors) >= 1


def test_cli_passes(capsys) -> None:
    exit_code = validator.main([])
    streams = capsys.readouterr()

    assert exit_code == 0
    assert "[PASS] intelligence_coordination_operator_summary" in streams.out
    assert streams.err == ""
