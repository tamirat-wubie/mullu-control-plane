"""Tests for Component Harness authority fuse validation.

Purpose: prove authority fuse records block component self-upgrade and live
authority changes.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_component_authority_fuse and foundation
Component Harness fixtures.
Invariants: every passport has one fuse; all fuses remain blocked, denial-only,
and non-terminal.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_component_authority_fuse import (
    DEFAULT_FUSE,
    DEFAULT_OUTPUT,
    validate_component_authority_fuse,
    write_component_authority_fuse_validation,
)


def _default_payload() -> dict[str, object]:
    return json.loads(DEFAULT_FUSE.read_text(encoding="utf-8"))


def _write_payload(tmp_path: Path, payload: dict[str, object]) -> Path:
    fuse_path = tmp_path / "component_authority_fuse.json"
    fuse_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return fuse_path


def _fuses(payload: dict[str, object]) -> list[dict[str, object]]:
    fuses = payload["fuses"]
    assert isinstance(fuses, list)
    return fuses


def test_component_authority_fuse_validate_and_write(tmp_path: Path) -> None:
    validation = validate_component_authority_fuse()
    output_path = tmp_path / "component-authority-fuse-validation.json"

    written_path = write_component_authority_fuse_validation(validation, output_path)
    written_payload = json.loads(written_path.read_text(encoding="utf-8"))

    assert validation.ok is True
    assert validation.fuse_count == 10
    assert validation.passport_count == 10
    assert written_payload["errors"] == []
    assert written_payload["ok"] is True
    assert DEFAULT_OUTPUT.name == "component_authority_fuse_validation.json"


def test_component_authority_fuse_reject_missing_component_fuse(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["fuses"] = [fuse for fuse in _fuses(payload) if fuse.get("component_id") != "snet"]
    summary = payload["summary"]
    assert isinstance(summary, dict)
    summary["fuse_count"] = 9

    validation = validate_component_authority_fuse(fuse_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert validation.fuse_count == 9
    assert "passports missing authority fuses ['snet']" in serialized_errors


def test_component_authority_fuse_reject_self_upgrade_drift(tmp_path: Path) -> None:
    payload = _default_payload()
    fuse = _fuses(payload)[0]
    fuse["self_upgrade_allowed"] = True
    fuse["can_upgrade_authority"] = True
    fuse["can_enable_live_action"] = True
    fuse["fuse_is_not_execution_authority"] = False

    validation = validate_component_authority_fuse(fuse_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "self_upgrade_allowed must be false" in serialized_errors
    assert "can_upgrade_authority must be false" in serialized_errors
    assert "can_enable_live_action must be false" in serialized_errors
    assert "fuse_is_not_execution_authority must be true" in serialized_errors


def test_component_authority_fuse_reject_authority_level_drift(tmp_path: Path) -> None:
    payload = _default_payload()
    fuse = _fuses(payload)[1]
    fuse["current_authority_level"] = "approved_live_action"
    fuse["terminal_closure_allowed"] = True
    fuse["decision"] = "approved"
    fuse["outcome"] = "SolvedVerified"

    validation = validate_component_authority_fuse(fuse_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "current_authority_level must match passport" in serialized_errors
    assert "terminal_closure_allowed must be false" in serialized_errors
    assert "decision must be blocked" in serialized_errors
    assert "outcome must be GovernanceBlocked" in serialized_errors


def test_component_authority_fuse_reject_missing_fuse_requirement(tmp_path: Path) -> None:
    payload = _default_payload()
    fuse = _fuses(payload)[2]
    assert isinstance(fuse["required_evidence"], list)
    assert isinstance(fuse["missing_evidence"], list)
    fuse["required_evidence"].remove("component_ci_gate")
    fuse["missing_evidence"].remove("component_ci_gate")
    fuse["required_validator_refs"] = ["component_passports_validator"]

    validation = validate_component_authority_fuse(fuse_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "required_evidence must match fuse requirements" in serialized_errors
    assert "missing_evidence must match fuse requirements" in serialized_errors
    assert "must require component_authority_fuse_validator" in serialized_errors
