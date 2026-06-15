"""Tests for Component Harness request simulation validation.

Purpose: prove request simulation schema, example, and runtime projection stay
aligned with the non-executing Component Harness posture.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_component_request_simulation and foundation
fixtures.
Invariants: example matches runtime projection, live authority is false, and
drift fails closed.
"""

from __future__ import annotations

import json
from pathlib import Path

from mcoi_runtime.app.component_request_simulator import simulate_component_request
from scripts.validate_component_request_simulation import (
    DEFAULT_EXAMPLE,
    DEFAULT_OUTPUT,
    validate_component_request_simulation,
    write_component_request_simulation_validation,
)


def _default_payload() -> dict[str, object]:
    return json.loads(DEFAULT_EXAMPLE.read_text(encoding="utf-8"))


def _write_payload(tmp_path: Path, payload: dict[str, object]) -> Path:
    example_path = tmp_path / "component_request_simulation.json"
    example_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return example_path


def test_component_request_simulation_schema_valid(tmp_path: Path) -> None:
    validation = validate_component_request_simulation()
    output_path = tmp_path / "component-request-simulation-validation.json"

    written_path = write_component_request_simulation_validation(validation, output_path)
    written_payload = json.loads(written_path.read_text(encoding="utf-8"))

    assert validation.ok is True
    assert validation.scenario_count == 6
    assert validation.blocked_scenario_count == 3
    assert written_payload["errors"] == []
    assert written_payload["ok"] is True
    assert DEFAULT_OUTPUT.name == "component_request_simulation_validation.json"


def test_component_request_simulation_example_matches_runtime_projection() -> None:
    example = _default_payload()
    projection = simulate_component_request(str(example["request_text"]))

    assert example == projection
    assert example["simulation_is_not_execution_authority"] is True
    assert example["live_execution_enabled"] is False
    assert example["outcome"] == "GovernanceBlocked"


def test_component_request_simulation_rejects_live_authority_drift(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["live_execution_enabled"] = True
    payload["can_execute"] = True
    payload["blocked_actions"] = ["send_email"]

    validation = validate_component_request_simulation(example_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "live_execution_enabled" in serialized_errors
    assert "can_execute" in serialized_errors
    assert "terminal_closure" in serialized_errors
    assert "example does not match runtime projection" in serialized_errors
