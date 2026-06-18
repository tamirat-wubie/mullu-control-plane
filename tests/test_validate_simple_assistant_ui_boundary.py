"""Tests for the simple assistant UI boundary validator.

Purpose: prove normal-user assistant projections stay simple while audit and
proof depth remains available behind explicit visibility levels.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.validate_simple_assistant_ui_boundary.
Invariants:
  - The foundation example validates.
  - Normal-user copy cannot leak internal proof terms.
  - The projection grants no execution authority.
  - The simple status allowlist cannot drift.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.validate_simple_assistant_ui_boundary import (
    DEFAULT_BOUNDARY,
    validate_simple_assistant_ui_boundary,
)


def test_simple_assistant_ui_boundary_fixture_validates() -> None:
    result = validate_simple_assistant_ui_boundary()

    assert result.valid is True
    assert result.boundary_path == "examples/simple_assistant_ui_boundary.foundation.json"
    assert result.example_count == 2
    assert result.assurance_outcome == "SolvedVerified"
    assert result.errors == ()


def test_simple_assistant_ui_boundary_rejects_normal_user_internal_term_leak(tmp_path: Path) -> None:
    payload = _load_fixture()
    payload["normal_user_examples"][0]["title"] = "Draft ready with proof matrix attached."
    candidate = tmp_path / "leaky_simple_assistant_ui_boundary.json"
    candidate.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_simple_assistant_ui_boundary(boundary_path=candidate)

    assert result.valid is False
    assert "normal_user_examples[0].title: normal-user copy leaks forbidden term 'proof matrix'" in result.errors
    assert result.example_count == 2
    assert result.assurance_outcome == "SolvedVerified"


def test_simple_assistant_ui_boundary_rejects_execution_authority(tmp_path: Path) -> None:
    payload = _load_fixture()
    payload["effect_boundary"]["execution_authority_granted"] = True
    payload["effect_boundary"]["external_send_allowed"] = True
    candidate = tmp_path / "authority_drift_simple_assistant_ui_boundary.json"
    candidate.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_simple_assistant_ui_boundary(boundary_path=candidate)

    assert result.valid is False
    assert "effect_boundary.execution_authority_granted must be false" in result.errors
    assert "effect_boundary.external_send_allowed must be false" in result.errors
    assert result.example_count == 2


def test_simple_assistant_ui_boundary_rejects_status_allowlist_drift(tmp_path: Path) -> None:
    payload = _load_fixture()
    payload["normal_user_allowed_statuses"].remove("Evidence saved")
    payload["normal_user_allowed_statuses"].append("Temporal retention certificate hash valid")
    candidate = tmp_path / "status_drift_simple_assistant_ui_boundary.json"
    candidate.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_simple_assistant_ui_boundary(boundary_path=candidate)

    assert result.valid is False
    assert (
        "normal_user_allowed_statuses must exactly match the approved simple status allowlist"
        in result.errors
    )
    assert result.assurance_outcome == "SolvedVerified"
    assert result.example_count == 2


def test_simple_assistant_ui_boundary_rejects_visible_audit_details_by_default(tmp_path: Path) -> None:
    payload = _load_fixture()
    payload["audit_details"]["default_visibility"] = "visible"
    payload["audit_details"]["normal_user_default_hidden"] = False
    payload["effect_boundary"]["proof_details_hidden_by_default"] = False
    candidate = tmp_path / "visible_audit_simple_assistant_ui_boundary.json"
    candidate.write_text(json.dumps(payload), encoding="utf-8")

    result = validate_simple_assistant_ui_boundary(boundary_path=candidate)

    assert result.valid is False
    assert "audit_details.default_visibility must be hidden" in result.errors
    assert "audit_details.normal_user_default_hidden must be true" in result.errors
    assert "effect_boundary.proof_details_hidden_by_default must be true" in result.errors


def _load_fixture() -> dict[str, object]:
    return copy.deepcopy(json.loads(DEFAULT_BOUNDARY.read_text(encoding="utf-8")))
