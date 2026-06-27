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
