"""Tests for the safe-local action read-model builder.

Purpose: prove the operator can get one safe local-lab next action without
running the gateway server or receiving external execution authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.build_operator_safe_local_action_read_model.
Invariants: safe-local action projections are no-effect, local-lab only, and
block PR creation, branch push, merge, deployment, and connector calls.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.build_operator_safe_local_action_read_model import (
    build_operator_safe_local_action_read_model,
    main,
    validate_operator_safe_local_action_read_model,
)
from scripts.validate_operator_control_tower_status_receipt import build_default_operator_control_tower_status_receipt


def test_safe_local_action_read_model_selects_first_candidate() -> None:
    receipt = build_default_operator_control_tower_status_receipt()
    read_model = build_operator_safe_local_action_read_model(
        status_receipt=receipt,
        source_ref="<generated-control-tower-status-receipt>",
    )
    validation = validate_operator_safe_local_action_read_model(read_model=read_model)

    assert validation.ok is True
    assert read_model["read_model_id"] == "operator_safe_local_action.read_model"
    assert read_model["projection_only"] is True
    assert read_model["execution_performed"] is False
    assert read_model["external_effects_allowed"] is False
    assert read_model["queue_status"] == "ready"
    assert read_model["candidate"]["candidate_id"] == "safe_zone.write_docs"
    assert read_model["candidate"]["zone"] == "write_docs"
    assert read_model["candidate"]["approval_required"] is False
    assert read_model["candidate"]["execution_boundary"] == "local_lab_only"
    assert read_model["action_contract"]["allowed_effect"] == "prepare_local_lab_artifact"


def test_safe_local_action_read_model_forbids_real_world_effects() -> None:
    receipt = build_default_operator_control_tower_status_receipt()
    read_model = build_operator_safe_local_action_read_model(status_receipt=receipt, source_ref="receipt.json")
    forbidden_effects = read_model["action_contract"]["forbidden_effects"]

    assert "create_pr" in forbidden_effects
    assert "push_branch" in forbidden_effects
    assert "merge" in forbidden_effects
    assert "deploy" in forbidden_effects
    assert "connector_call" in forbidden_effects
    assert read_model["action_contract"]["approval_required"] is False
    assert read_model["action_contract"]["execution_performed"] is False
    assert read_model["action_contract"]["external_effects_allowed"] is False


def test_safe_local_action_validator_rejects_execution_overclaim() -> None:
    receipt = build_default_operator_control_tower_status_receipt()
    read_model = build_operator_safe_local_action_read_model(status_receipt=receipt, source_ref="receipt.json")
    read_model["execution_performed"] = True
    read_model["candidate"]["external_effects_allowed"] = True
    read_model["action_contract"]["forbidden_effects"].remove("deploy")

    validation = validate_operator_safe_local_action_read_model(read_model=read_model)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "execution_performed_must_be_false" in serialized_errors
    assert "candidate_external_effects_must_be_false" in serialized_errors
    assert "forbidden_effect_missing:deploy" in serialized_errors


def test_safe_local_action_cli_writes_json(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "safe-local-action.json"

    exit_code = main(["--output", str(output_path), "--json"])
    captured = capsys.readouterr()
    read_model = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert read_model["read_model_id"] == "operator_safe_local_action.read_model"
    assert read_model["candidate"]["candidate_id"] == "safe_zone.write_docs"
    assert read_model["external_effects_allowed"] is False
    assert '"safe_zone.write_docs"' in captured.out


def test_safe_local_action_cli_rejects_invalid_receipt(tmp_path: Path, capsys) -> None:
    receipt_path = tmp_path / "bad-status-receipt.json"
    receipt_path.write_text('{"projection_only": false}\n', encoding="utf-8")
    output_path = tmp_path / "safe-local-action.json"

    exit_code = main(["--receipt", str(receipt_path), "--output", str(output_path), "--json"])
    captured = capsys.readouterr()

    assert exit_code == 2
    assert not output_path.exists()
    assert "OPERATOR SAFE LOCAL ACTION INVALID" in captured.out
