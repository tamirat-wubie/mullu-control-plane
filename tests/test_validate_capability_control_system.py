"""Tests for capability control-system validation.

Purpose: prove the master capability control-system read model organizes
capability status without granting execution authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_capability_control_system, capability packs,
capability passports, and unlock ladder projection.
Invariants: L0-L9 is complete, Fast Mode is lab-bounded, safe zones and
dangerous zones are disjoint, and registry rows expose next evidence.
"""

from __future__ import annotations

import json
from pathlib import Path

from mcoi_runtime.app.capability_control_system import build_capability_control_system
from scripts.validate_capability_control_system import (
    DEFAULT_CONTROL_SYSTEM,
    DEFAULT_OUTPUT,
    validate_capability_control_system,
    write_capability_control_system_validation,
)


def _default_payload() -> dict[str, object]:
    return json.loads(DEFAULT_CONTROL_SYSTEM.read_text(encoding="utf-8"))


def _write_payload(tmp_path: Path, payload: dict[str, object]) -> Path:
    control_system_path = tmp_path / "capability_control_system.json"
    control_system_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return control_system_path


def test_capability_control_system_validates_and_writes(tmp_path: Path) -> None:
    validation = validate_capability_control_system()
    output_path = tmp_path / "capability-control-system-validation.json"

    written_path = write_capability_control_system_validation(validation, output_path)
    written_payload = json.loads(written_path.read_text(encoding="utf-8"))

    assert validation.ok is True
    assert validation.capability_count > 20
    assert validation.unlock_level_count == 10
    assert validation.friction_mode_count == 3
    assert written_payload["errors"] == []
    assert DEFAULT_OUTPUT.name == "capability_control_system_validation.json"


def test_capability_control_system_projects_l0_l9_and_modes() -> None:
    control_system = build_capability_control_system()
    level_ids = tuple(level["level_id"] for level in control_system["unlock_levels"])
    mode_ids = tuple(mode["mode_id"] for mode in control_system["friction_modes"])
    boundary_ids = tuple(boundary["boundary_id"] for boundary in control_system["operating_boundaries"])

    assert level_ids == tuple(f"L{index}" for index in range(10))
    assert mode_ids == ("strict", "balanced", "fast")
    assert boundary_ids == ("lab", "real_world")
    assert control_system["control_system_is_not_execution_authority"] is True
    assert control_system["live_execution_enabled"] is False


def test_capability_control_system_fast_mode_is_lab_bounded() -> None:
    control_system = build_capability_control_system()
    modes = {mode["mode_id"]: mode for mode in control_system["friction_modes"]}
    safe_zones = set(control_system["safe_automatic_zones"])
    dangerous_zones = set(control_system["dangerous_zones"])
    fast_ready_rows = [row for row in control_system["registry"] if row["fast_mode_lab_ready"]]

    assert modes["fast"]["default_boundary"] == "lab"
    assert set(modes["fast"]["automatic_zones"]) == safe_zones
    assert safe_zones.isdisjoint(dangerous_zones)
    assert fast_ready_rows
    assert all(row["requires_live_witness"] is False for row in fast_ready_rows)
    assert all(row["unlock_level_number"] <= 4 for row in fast_ready_rows)


def test_capability_control_system_registry_answers_control_questions() -> None:
    control_system = build_capability_control_system()
    registry = control_system["registry"]
    software_change = next(row for row in registry if row["capability_id"] == "software_dev.change.run")
    pr_candidate = next(row for row in registry if row["capability_id"] == "software_dev.pr_candidate.prepare")

    assert software_change["unlock_level"] == "L4"
    assert software_change["requires_rollback"] is True
    assert "rollback_gate" in software_change["required_before_unlock"]
    assert software_change["next_evidence_needed"]
    assert pr_candidate["unlock_level"] == "L5"
    assert pr_candidate["requires_operator_approval"] is True
    assert "pull_request_opened_without_approval" in pr_candidate["blocked_actions"]


def test_capability_control_system_rejects_authority_overclaim(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["control_system_is_not_execution_authority"] = False
    payload["live_execution_enabled"] = True

    validation = validate_capability_control_system(control_system_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "control_system_is_not_execution_authority must be true" in serialized_errors
    assert "live_execution_enabled must be false" in serialized_errors
    assert "example does not match runtime projection" in serialized_errors


def test_capability_control_system_rejects_fast_mode_live_witness(tmp_path: Path) -> None:
    payload = _default_payload()
    registry = payload["registry"]
    assert isinstance(registry, list)
    first_row = registry[0]
    assert isinstance(first_row, dict)
    first_row["fast_mode_lab_ready"] = True
    first_row["requires_live_witness"] = True

    validation = validate_capability_control_system(control_system_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "fast mode cannot require live witness" in serialized_errors
    assert "example does not match runtime projection" in serialized_errors
