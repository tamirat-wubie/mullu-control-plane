"""Tests for Component Harness claim firewall validation.

Purpose: prove product and public claims remain bounded by component evidence.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_component_claim_firewall and foundation
Component Harness fixtures.
Invariants: blocked claims stay blocked; allowed bounded claims remain
non-terminal and non-executing.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_component_claim_firewall import (
    DEFAULT_FIREWALL,
    DEFAULT_OUTPUT,
    validate_component_claim_firewall,
    write_component_claim_firewall_validation,
)


def _default_payload() -> dict[str, object]:
    return json.loads(DEFAULT_FIREWALL.read_text(encoding="utf-8"))


def _write_payload(tmp_path: Path, payload: dict[str, object]) -> Path:
    firewall_path = tmp_path / "component_claim_firewall.json"
    firewall_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return firewall_path


def _claim_checks(payload: dict[str, object]) -> list[dict[str, object]]:
    claim_checks = payload["claim_checks"]
    assert isinstance(claim_checks, list)
    return claim_checks


def test_component_claim_firewall_validate_and_write(tmp_path: Path) -> None:
    validation = validate_component_claim_firewall()
    output_path = tmp_path / "component-claim-firewall-validation.json"

    written_path = write_component_claim_firewall_validation(validation, output_path)
    written_payload = json.loads(written_path.read_text(encoding="utf-8"))

    assert validation.ok is True
    assert validation.claim_check_count == 12
    assert validation.blocked_claim_count == 7
    assert validation.allowed_bounded_claim_count == 5
    assert written_payload["errors"] == []
    assert written_payload["ok"] is True
    assert DEFAULT_OUTPUT.name == "component_claim_firewall_validation.json"


def test_component_claim_firewall_reject_blocked_claim_allowed(tmp_path: Path) -> None:
    payload = _default_payload()
    claim_check = _claim_checks(payload)[0]
    claim_check["decision"] = "allowed_bounded"
    claim_check["outcome"] = "SolvedVerified"
    claim_check["terminal_closure_allowed"] = True
    claim_check["claim_is_not_execution_authority"] = False

    validation = validate_component_claim_firewall(firewall_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "decision must be blocked" in serialized_errors
    assert "outcome must be GovernanceBlocked" in serialized_errors
    assert "terminal_closure_allowed must be false" in serialized_errors
    assert "claim_is_not_execution_authority must be true" in serialized_errors


def test_component_claim_firewall_reject_missing_blocked_claim(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["claim_checks"] = [
        claim_check
        for claim_check in _claim_checks(payload)
        if claim_check.get("claim_text") != "customer ready"
    ]
    summary = payload["summary"]
    assert isinstance(summary, dict)
    summary["claim_check_count"] = 11
    summary["blocked_claim_count"] = 6

    validation = validate_component_claim_firewall(firewall_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert validation.claim_check_count == 11
    assert "missing blocked claims ['customer ready']" in serialized_errors


def test_component_claim_firewall_reject_allowed_claim_without_evidence(tmp_path: Path) -> None:
    payload = _default_payload()
    allowed_claim = next(
        claim_check
        for claim_check in _claim_checks(payload)
        if claim_check.get("claim_text") == "read-only projection exists"
    )
    allowed_claim["decision"] = "blocked"
    allowed_claim["outcome"] = "GovernanceBlocked"
    allowed_claim["blocking_component_ids"] = ["snet"]
    allowed_claim["evidence_refs"] = []

    validation = validate_component_claim_firewall(firewall_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "decision must be allowed_bounded" in serialized_errors
    assert "outcome must be SolvedVerified" in serialized_errors
    assert "must not name blocking components" in serialized_errors
    assert "must carry evidence_refs" in serialized_errors


def test_component_claim_firewall_reject_missing_validator_ref(tmp_path: Path) -> None:
    payload = _default_payload()
    claim_check = _claim_checks(payload)[1]
    claim_check["required_validator_refs"] = ["component_passports_validator"]

    validation = validate_component_claim_firewall(firewall_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "must require component_authority_fuse_validator" in serialized_errors
    assert "must require component_claim_firewall_validator" in serialized_errors
