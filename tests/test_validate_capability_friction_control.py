"""Tests for capability friction-control validation.

Purpose: prove the friction-control read model simplifies capability gates into
operator-safe levels and modes without granting authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_capability_friction_control and the software-dev
capability pack.
Invariants: every software-dev capability is projected once, lab readiness is
bounded, real-world effects are blocked, and internal registry fields stay
hidden.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_capability_friction_control import (
    DEFAULT_OUTPUT,
    DEFAULT_READ_MODEL,
    build_default_capability_friction_control_read_model,
    validate_capability_friction_control,
    write_capability_friction_control_validation,
)


def _default_payload() -> dict[str, object]:
    return json.loads(DEFAULT_READ_MODEL.read_text(encoding="utf-8"))


def _write_payload(tmp_path: Path, payload: dict[str, object]) -> Path:
    read_model_path = tmp_path / "capability_friction_control.json"
    read_model_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return read_model_path


def _capabilities(payload: dict[str, object]) -> list[dict[str, object]]:
    capabilities = payload["capabilities"]
    assert isinstance(capabilities, list)
    return [item for item in capabilities if isinstance(item, dict)]


def _capability(payload: dict[str, object], capability_id: str) -> dict[str, object]:
    for card in _capabilities(payload):
        if card.get("capability_id") == capability_id:
            return card
    raise AssertionError(f"missing capability card {capability_id}")


def test_capability_friction_control_validates_and_writes(tmp_path: Path) -> None:
    validation = validate_capability_friction_control()
    output_path = tmp_path / "capability-friction-control-validation.json"

    written_path = write_capability_friction_control_validation(validation, output_path)
    written_payload = json.loads(written_path.read_text(encoding="utf-8"))

    assert validation.ok is True
    assert validation.capability_count == 6
    assert validation.fast_mode_lab_ready_count == 2
    assert validation.developer_workflow_status == "preflight_ready"
    assert validation.errors == ()
    assert written_payload["errors"] == []
    assert DEFAULT_OUTPUT.name == "capability_friction_control_validation.json"


def test_capability_friction_control_runtime_projection_is_bounded() -> None:
    read_model = build_default_capability_friction_control_read_model()
    change_card = _capability(read_model, "software_dev.change.run")
    pr_card = _capability(read_model, "software_dev.pr_candidate.prepare")

    assert read_model["read_model_is_not_execution_authority"] is True
    assert read_model["live_execution_enabled"] is False
    assert read_model["summary"]["capability_count"] == 6
    assert read_model["summary"]["real_world_mode_allowed_count"] == 0
    assert read_model["developer_workflow_v1"]["status"] == "preflight_ready"
    assert read_model["sandbox_to_pr_now"]["status"] == "awaiting_sandbox_receipts"
    assert read_model["sandbox_to_pr_now"]["blocker"] == "sandbox_receipts_incomplete"
    assert read_model["sandbox_to_pr_now"]["next_action"] == "attach sandbox patch, test, diff, and terminal receipts"
    assert read_model["sandbox_to_pr_now"]["policy_ready"] is True
    assert read_model["sandbox_to_pr_now"]["workflow_ready"] is True
    assert read_model["sandbox_to_pr_now"]["external_effects_allowed"] is False
    assert read_model["sandbox_to_pr_now"]["packet_validator"] == (
        "python scripts/validate_sandbox_to_pr_preparation_packet.py"
    )
    assert [item["evidence_id"] for item in read_model["sandbox_to_pr_now"]["next_evidence"]] == [
        "sandbox_patch_receipt",
        "test_gate_receipt",
        "diff_review_receipt",
        "terminal_receipt",
    ]
    assert [item["action"] for item in read_model["sandbox_to_pr_now"]["next_evidence"]] == [
        "attach before state, after state, diff, command, and rollback receipt",
        "attach bounded local test command receipt and observed result",
        "attach reviewed diff hash and reviewer evidence reference",
        "attach final local receipt summary and no-external-effect witness",
    ]
    assert all(item["status"] == "pending" for item in read_model["sandbox_to_pr_now"]["next_evidence"])
    validators = {
        str(validator["validator_id"]): validator
        for validator in read_model["validators"]
        if isinstance(validator, dict)
    }
    assert validators["capability_friction_control_validator"]["command"] == (
        "python scripts/validate_capability_friction_control.py"
    )
    assert validators["sandbox_to_pr_preparation_packet_validator"]["command"] == (
        "python scripts/validate_sandbox_to_pr_preparation_packet.py"
    )
    assert validators["developer_workflow_sandbox_receipt_bundle_validator"]["command"] == (
        "python scripts/validate_developer_workflow_sandbox_receipt_bundle.py"
    )
    assert validators["developer_workflow_sandbox_receipt_attachment_packet_validator"]["command"] == (
        "python scripts/validate_developer_workflow_sandbox_receipt_attachment_packet.py"
    )
    assert validators["developer_workflow_local_sandbox_proof_report_validator"]["command"] == (
        "python scripts/validate_developer_workflow_local_sandbox_proof_report.py"
    )
    assert validators["developer_workflow_local_rollback_summary_packet_validator"]["command"] == (
        "python scripts/validate_developer_workflow_local_rollback_summary_packet.py"
    )
    assert validators["developer_workflow_local_rollback_approval_packet_validator"]["command"] == (
        "python scripts/validate_developer_workflow_local_rollback_approval_packet.py"
    )
    assert validators["developer_workflow_local_rollback_execution_receipt_validator"]["command"] == (
        "python scripts/validate_developer_workflow_local_rollback_execution_receipt.py"
    )
    assert validators["developer_workflow_local_rollback_flow_tests"]["command"] == (
        "python -m pytest tests/test_run_developer_workflow_local_rollback_flow.py -q"
    )
    assert validators["pr_preparation_approval_packet_validator"]["command"] == (
        "python scripts/validate_pr_preparation_approval_packet.py"
    )
    assert validators["local_pr_candidate_packet_validator"]["command"] == (
        "python scripts/validate_local_pr_candidate_packet.py"
    )
    assert validators["pr_tool_admission_packet_validator"]["command"] == (
        "python scripts/validate_pr_tool_admission_packet.py"
    )
    assert validators["external_pr_execution_approval_witness_validator"]["command"] == (
        "python scripts/validate_external_pr_execution_approval_witness.py"
    )
    assert validators["pr_command_preview_packet_validator"]["command"] == (
        "python scripts/validate_pr_command_preview_packet.py"
    )
    assert validators["pr_metadata_packet_validator"]["command"] == (
        "python scripts/validate_pr_metadata_packet.py"
    )
    assert validators["pr_readiness_bundle_validator"]["command"] == (
        "python scripts/validate_pr_readiness_bundle.py"
    )
    assert validators["developer_workflow_operator_receipt_validator"]["command"] == (
        "python scripts/build_developer_workflow_operator_receipt.py --json"
    )
    assert validators["operator_control_tower_status_receipt_validator"]["command"] == (
        "python scripts/validate_operator_control_tower_status_receipt.py"
    )
    assert validators["capability_friction_control_tests"]["command"] == (
        "python -m pytest tests/test_validate_capability_friction_control.py -q"
    )
    assert validators["sandbox_to_pr_preparation_packet_tests"]["command"] == (
        "python -m pytest tests/test_validate_sandbox_to_pr_preparation_packet.py -q"
    )
    assert validators["developer_workflow_sandbox_receipt_bundle_tests"]["command"] == (
        "python -m pytest tests/test_validate_developer_workflow_sandbox_receipt_bundle.py -q"
    )
    assert validators["developer_workflow_sandbox_receipt_attachment_packet_tests"]["command"] == (
        "python -m pytest tests/test_build_developer_workflow_sandbox_receipt_attachment_packet.py tests/test_validate_developer_workflow_sandbox_receipt_attachment_packet.py -q"
    )
    assert validators["developer_workflow_sandbox_receipt_evidence_collector_tests"]["command"] == (
        "python -m pytest tests/test_collect_developer_workflow_sandbox_receipt_evidence.py -q"
    )
    assert validators["developer_workflow_local_sandbox_proof_runner_tests"]["command"] == (
        "python -m pytest tests/test_run_developer_workflow_local_sandbox_proof.py -q"
    )
    assert validators["developer_workflow_local_sandbox_proof_report_tests"]["command"] == (
        "python -m pytest tests/test_validate_developer_workflow_local_sandbox_proof_report.py -q"
    )
    assert validators["developer_workflow_local_rollback_summary_packet_tests"]["command"] == (
        "python -m pytest tests/test_build_developer_workflow_local_rollback_summary_packet.py tests/test_validate_developer_workflow_local_rollback_summary_packet.py -q"
    )
    assert validators["developer_workflow_local_rollback_approval_packet_tests"]["command"] == (
        "python -m pytest tests/test_build_developer_workflow_local_rollback_approval_packet.py tests/test_validate_developer_workflow_local_rollback_approval_packet.py -q"
    )
    assert validators["developer_workflow_local_rollback_execution_tests"]["command"] == (
        "python -m pytest tests/test_execute_developer_workflow_local_rollback.py tests/test_validate_developer_workflow_local_rollback_execution_receipt.py -q"
    )
    assert validators["pr_preparation_approval_packet_tests"]["command"] == (
        "python -m pytest tests/test_build_pr_preparation_approval_packet.py -q"
    )
    assert validators["local_pr_candidate_packet_tests"]["command"] == (
        "python -m pytest tests/test_build_local_pr_candidate_packet.py tests/test_validate_local_pr_candidate_packet.py -q"
    )
    assert validators["pr_tool_admission_packet_tests"]["command"] == (
        "python -m pytest tests/test_build_pr_tool_admission_packet.py tests/test_validate_pr_tool_admission_packet.py -q"
    )
    assert validators["external_pr_execution_approval_witness_tests"]["command"] == (
        "python -m pytest tests/test_build_external_pr_execution_approval_witness.py tests/test_validate_external_pr_execution_approval_witness.py -q"
    )
    assert validators["pr_command_preview_packet_tests"]["command"] == (
        "python -m pytest tests/test_build_pr_command_preview_packet.py tests/test_validate_pr_command_preview_packet.py -q"
    )
    assert validators["pr_metadata_packet_tests"]["command"] == (
        "python -m pytest tests/test_build_pr_metadata_packet.py tests/test_validate_pr_metadata_packet.py -q"
    )
    assert validators["pr_readiness_bundle_tests"]["command"] == (
        "python -m pytest tests/test_build_pr_readiness_bundle.py tests/test_validate_pr_readiness_bundle.py -q"
    )
    assert validators["developer_workflow_operator_receipt_tests"]["command"] == (
        "python -m pytest tests/test_build_developer_workflow_operator_receipt.py -q"
    )
    assert validators["operator_control_tower_status_receipt_tests"]["command"] == (
        "python -m pytest tests/test_validate_operator_control_tower_status_receipt.py -q"
    )
    assert change_card["unlock_level"] == "L4"
    assert change_card["fast_mode_admission"] == "allowed_lab"
    assert change_card["rollback_default"] is True
    assert pr_card["unlock_level"] == "L5"
    assert pr_card["next_unlock"] == "approval"


def test_capability_friction_control_rejects_authority_overclaim(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["read_model_is_not_execution_authority"] = False
    payload["live_execution_enabled"] = True

    validation = validate_capability_friction_control(read_model_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "read_model_is_not_execution_authority must be true" in serialized_errors
    assert "live_execution_enabled must be false" in serialized_errors
    assert "example does not match runtime projection" in serialized_errors


def test_capability_friction_control_rejects_missing_capability_card(tmp_path: Path) -> None:
    payload = _default_payload()
    capabilities = payload["capabilities"]
    assert isinstance(capabilities, list)
    capabilities.pop()
    payload["summary"]["capability_count"] = len(capabilities)  # type: ignore[index]

    validation = validate_capability_friction_control(read_model_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "capabilities must match software_dev registry entries" in serialized_errors
    assert "example does not match runtime projection" in serialized_errors


def test_capability_friction_control_rejects_safe_dangerous_overlap(tmp_path: Path) -> None:
    payload = _default_payload()
    dangerous = payload["dangerous_zones"]
    assert isinstance(dangerous, list)
    dangerous.append("write_tests")

    validation = validate_capability_friction_control(read_model_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "safe and dangerous zones overlap" in serialized_errors
    assert "example does not match runtime projection" in serialized_errors


def test_capability_friction_control_rejects_internal_field_exposure(tmp_path: Path) -> None:
    payload = _default_payload()
    change_card = _capability(payload, "software_dev.change.run")
    change_card["allowed_tools"] = ["sandboxed_code_worker.execute_command"]

    validation = validate_capability_friction_control(read_model_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "exposes internal fields ['allowed_tools']" in serialized_errors
    assert "example does not match runtime projection" in serialized_errors


def test_capability_friction_control_rejects_workflow_stage_drift(tmp_path: Path) -> None:
    payload = _default_payload()
    workflow = payload["developer_workflow_v1"]
    assert isinstance(workflow, dict)
    stages = workflow["stages"]
    assert isinstance(stages, list)
    stages.reverse()

    validation = validate_capability_friction_control(read_model_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "developer workflow stages are not in canonical order" in serialized_errors
    assert "example does not match runtime projection" in serialized_errors


def test_capability_friction_control_rejects_sandbox_to_pr_blocker_drift(tmp_path: Path) -> None:
    payload = _default_payload()
    sandbox_to_pr = payload["sandbox_to_pr_now"]
    assert isinstance(sandbox_to_pr, dict)
    sandbox_to_pr["blocker"] = "capability_policy_incomplete"
    sandbox_to_pr["external_effects_allowed"] = True

    validation = validate_capability_friction_control(read_model_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "sandbox_to_pr_now.external_effects_allowed must be false" in serialized_errors
    assert "sandbox_to_pr_now.blocker must be 'sandbox_receipts_incomplete'" in serialized_errors
    assert "example does not match runtime projection" in serialized_errors


def test_capability_friction_control_rejects_sandbox_to_pr_evidence_drift(tmp_path: Path) -> None:
    payload = _default_payload()
    sandbox_to_pr = payload["sandbox_to_pr_now"]
    assert isinstance(sandbox_to_pr, dict)
    next_evidence = sandbox_to_pr["next_evidence"]
    assert isinstance(next_evidence, list)
    next_evidence.reverse()
    next_evidence[0]["status"] = "complete"  # type: ignore[index]
    next_evidence[0]["action"] = "do something else"  # type: ignore[index]

    validation = validate_capability_friction_control(read_model_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "sandbox_to_pr_now.next_evidence must list canonical receipt evidence in order" in serialized_errors
    assert "status must be pending" in serialized_errors
    assert "action must be canonical" in serialized_errors
    assert "example does not match runtime projection" in serialized_errors


def test_capability_friction_control_rejects_packet_fixture_evidence_drift(tmp_path: Path) -> None:
    packet = json.loads((Path("examples") / "sandbox_to_pr_preparation_packet.foundation.json").read_text(encoding="utf-8"))
    next_evidence = packet["next_evidence"]
    assert isinstance(next_evidence, list)
    next_evidence[0]["source"] = "workflow_monitor.metadata.developer_workflow_run.receipt_checklist.other"
    next_evidence[1]["action"] = "skip local evidence"
    packet_path = tmp_path / "sandbox_to_pr_packet.json"
    packet_path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    validation = validate_capability_friction_control(sandbox_to_pr_packet_path=packet_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "sandbox_to_pr_now.next_evidence drifts from" in serialized_errors
