"""Tests for Component Harness bundle compiler validation.

Purpose: prove bundle compilation schema, example, and runtime reports stay
aligned with preview-only Component Harness posture.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_component_bundle_compiler and foundation
fixtures.
Invariants: example matches runtime compilation, live authority is false, and
drift fails closed.
"""

from __future__ import annotations

import json
from pathlib import Path

from mcoi_runtime.app.component_bundle_compiler import compile_component_bundle
from scripts.validate_component_bundle_compiler import (
    DEFAULT_EXAMPLE,
    DEFAULT_OUTPUT,
    validate_component_bundle_compiler,
    write_component_bundle_compiler_validation,
)


def _default_payload() -> dict[str, object]:
    return json.loads(DEFAULT_EXAMPLE.read_text(encoding="utf-8"))


def _write_payload(tmp_path: Path, payload: dict[str, object]) -> Path:
    example_path = tmp_path / "component_bundle_compilation.json"
    example_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return example_path


def test_component_bundle_compilation_schema_valid(tmp_path: Path) -> None:
    validation = validate_component_bundle_compiler()
    output_path = tmp_path / "component-bundle-compiler-validation.json"

    written_path = write_component_bundle_compiler_validation(validation, output_path)
    written_payload = json.loads(written_path.read_text(encoding="utf-8"))

    assert validation.ok is True
    assert validation.bundle_count == 3
    assert validation.blocked_bundle_count == 2
    assert written_payload["errors"] == []
    assert written_payload["ok"] is True
    assert DEFAULT_OUTPUT.name == "component_bundle_compiler_validation.json"


def test_component_bundle_compilation_example_matches_runtime_projection() -> None:
    example = _default_payload()
    projection = compile_component_bundle(str(example["bundle_id"]))

    assert example == projection
    assert example["compiler_is_not_execution_authority"] is True
    assert example["live_execution_enabled"] is False
    assert example["summary"]["live_action_ready"] is False
    assert example["outcome"] == "GovernanceBlocked"


def test_component_bundle_compilation_rejects_live_authority_drift(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["live_execution_enabled"] = True
    payload["can_execute"] = True
    payload["blocked_actions"] = ["send_email"]
    summary = payload["summary"]
    assert isinstance(summary, dict)
    summary["live_action_ready"] = True

    validation = validate_component_bundle_compiler(example_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "live_execution_enabled" in serialized_errors
    assert "can_execute" in serialized_errors
    assert "terminal_closure" in serialized_errors
    assert "live_action_ready" in serialized_errors
    assert "example does not match runtime compilation" in serialized_errors
