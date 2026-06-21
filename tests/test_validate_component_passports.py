"""Tests for Component Harness passport validation.

Purpose: prove component passports mirror registry state while denying live
effects and terminal closure.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_component_passports and foundation Component
Harness fixtures.
Invariants: every registered component has one passport; passport authority,
lifecycle, evidence refs, and blocked actions remain registry-derived.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_component_passports import (
    DEFAULT_OUTPUT,
    DEFAULT_PASSPORTS,
    validate_component_passports,
    write_component_passport_validation,
)


def _default_payload() -> dict[str, object]:
    return json.loads(DEFAULT_PASSPORTS.read_text(encoding="utf-8"))


def _write_payload(tmp_path: Path, payload: dict[str, object]) -> Path:
    passport_path = tmp_path / "component_passports.json"
    passport_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return passport_path


def _passports(payload: dict[str, object]) -> list[dict[str, object]]:
    passports = payload["passports"]
    assert isinstance(passports, list)
    return passports


def test_component_passports_validate_and_write(tmp_path: Path) -> None:
    validation = validate_component_passports()
    output_path = tmp_path / "component-passports-validation.json"

    written_path = write_component_passport_validation(validation, output_path)
    written_payload = json.loads(written_path.read_text(encoding="utf-8"))

    assert validation.ok is True
    assert validation.passport_count == 10
    assert validation.component_count == 10
    assert written_payload["errors"] == []
    assert written_payload["ok"] is True
    assert DEFAULT_OUTPUT.name == "component_passports_validation.json"


def test_component_passports_reject_missing_component_passport(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["passports"] = [
        passport for passport in _passports(payload) if passport.get("component_id") != "snet"
    ]
    summary = payload["summary"]
    assert isinstance(summary, dict)
    summary["passport_count"] = 9

    validation = validate_component_passports(passport_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert validation.passport_count == 9
    assert "registered components missing passports ['snet']" in serialized_errors


def test_component_passports_reject_authority_drift(tmp_path: Path) -> None:
    payload = _default_payload()
    passport = _passports(payload)[0]
    authority = passport["authority"]
    assert isinstance(authority, dict)
    authority["can_execute"] = True
    passport["passport_is_not_execution_authority"] = False
    passport["blocked_actions"] = ["connector_call"]

    validation = validate_component_passports(passport_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "authority.can_execute" in serialized_errors
    assert "authority must match registry" in serialized_errors
    assert "passport_is_not_execution_authority must be true" in serialized_errors
    assert "blocked_actions must include terminal_closure" in serialized_errors


def test_component_passports_reject_lifecycle_drift(tmp_path: Path) -> None:
    payload = _default_payload()
    passport = _passports(payload)[1]
    lifecycle = passport["lifecycle"]
    assert isinstance(lifecycle, dict)
    lifecycle["authority_level"] = "approved_live_action"
    receipts = passport["receipts"]
    assert isinstance(receipts, dict)
    receipts["can_claim_terminal_closure"] = True

    validation = validate_component_passports(passport_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "lifecycle.authority_level must match registry" in serialized_errors
    assert "receipts.can_claim_terminal_closure must be false" in serialized_errors
    assert "example does not match runtime projection" in serialized_errors


def test_component_passports_reject_missing_evidence(tmp_path: Path) -> None:
    payload = _default_payload()
    passport = _passports(payload)[2]
    passport["evidence_refs"] = ["docs/missing-component-passport-evidence.md"]

    validation = validate_component_passports(passport_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "evidence_ref missing on disk" in serialized_errors
    assert "docs/missing-component-passport-evidence.md" in serialized_errors
