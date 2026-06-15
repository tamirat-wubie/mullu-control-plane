"""Tests for Component Harness dead-component detector validation.

Purpose: prove detector examples, runtime projections, and validation
guardrails classify dead-candidate drift without granting authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_component_dead_detector and detector runtime.
Invariants: blocked governed components remain explicit and live authority
stays false.
"""

from __future__ import annotations

import json
from pathlib import Path

from mcoi_runtime.app.component_dead_detector import build_component_dead_component_report
from scripts.validate_component_dead_detector import (
    DEFAULT_EXAMPLE,
    DEFAULT_OUTPUT,
    validate_component_dead_detector,
    write_component_dead_detector_validation,
)


def _default_payload() -> dict[str, object]:
    return json.loads(DEFAULT_EXAMPLE.read_text(encoding="utf-8"))


def _write_payload(tmp_path: Path, payload: dict[str, object]) -> Path:
    example_path = tmp_path / "component_dead_detector.json"
    example_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return example_path


def test_component_dead_detector_schema_valid_and_write(tmp_path: Path) -> None:
    validation = validate_component_dead_detector()
    output_path = tmp_path / "component-dead-detector-validation.json"

    written_path = write_component_dead_detector_validation(validation, output_path)
    written_payload = json.loads(written_path.read_text(encoding="utf-8"))

    assert validation.ok is True
    assert validation.component_count == 10
    assert validation.dead_candidate_count == 0
    assert validation.blocked_governed_count == 5
    assert written_payload["errors"] == []
    assert DEFAULT_OUTPUT.name == "component_dead_detector_validation.json"


def test_component_dead_detector_example_matches_runtime_projection() -> None:
    example = _default_payload()
    projection = build_component_dead_component_report()
    detections = {detection["component_id"]: detection for detection in example["detections"]}

    assert example == projection
    assert example["detector_is_not_execution_authority"] is True
    assert example["live_execution_enabled"] is False
    assert example["dead_component_candidates"] == []
    assert detections["nested_mind_bridge"]["classification"] == "blocked_governed"
    assert detections["snet"]["classification"] == "governed_watch"


def test_component_dead_detector_rejects_authority_and_summary_drift(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["can_call_connector"] = True
    payload["summary"]["dead_candidate_count"] = 1

    validation = validate_component_dead_detector(example_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "can_call_connector" in serialized_errors
    assert "summary.dead_candidate_count" in serialized_errors
    assert "example does not match runtime report" in serialized_errors


def test_component_dead_detector_keeps_blocked_governed_separate_from_dead_candidate() -> None:
    report = build_component_dead_component_report()
    detections = {detection["component_id"]: detection for detection in report["detections"]}

    assert report["summary"]["dead_candidate_count"] == 0
    assert "nested_mind_bridge" not in report["dead_component_candidates"]
    assert "nested_mind_bridge" in report["blocked_governed_components"]
    assert "proof_binding_missing" in detections["nested_mind_bridge"]["signals"]
