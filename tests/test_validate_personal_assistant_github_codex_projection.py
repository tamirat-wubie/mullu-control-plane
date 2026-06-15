"""Tests for Personal Assistant GitHub/Codex projection validation.

Purpose: prove GitHub/Codex review planning evidence remains schema-backed and
no-effect.
Governance scope: no GitHub call, no repository or PR mutation, no branch push,
no review submission, no deployment, no raw diff storage, no secret
serialization, and receipt continuity.
Dependencies: personal-assistant GitHub/Codex projection validator and fixture.
Invariants:
  - GitHub/Codex review projections are not live GitHub operations.
  - Review-ready evidence still cannot merge, push, review, or deploy.
  - Receipts must record actions taken and actions not taken.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.validate_personal_assistant_github_codex_projection import (
    build_runtime_github_codex_projection_evidence,
    validate_personal_assistant_github_codex_projection,
)


def test_personal_assistant_github_codex_projection_fixture_validates() -> None:
    result = validate_personal_assistant_github_codex_projection()

    assert result.valid is True
    assert result.projection_count == 2
    assert result.receipt_count == 2
    assert result.runtime_validated is True
    assert result.assurance_outcome == "AwaitingEvidence"
    assert result.errors == ()


def test_runtime_github_codex_projection_blocks_effect_boundaries() -> None:
    envelope = build_runtime_github_codex_projection_evidence()
    effect_boundary = envelope["effect_boundary"]
    ready_projection = envelope["projections"][1]
    ready_plan = ready_projection["plan"]
    ready_receipt = ready_projection["receipt"]

    assert effect_boundary["github_codex_review_records_allowed"] is True
    assert effect_boundary["execution_allowed"] is False
    assert effect_boundary["live_connector_execution_allowed"] is False
    assert effect_boundary["github_call_allowed"] is False
    assert effect_boundary["repository_mutation_allowed"] is False
    assert effect_boundary["pull_request_mutation_allowed"] is False
    assert effect_boundary["deployment_mutation_allowed"] is False
    assert ready_plan["evidence_gate"]["operator_supplied_evidence_complete"] is True
    assert ready_plan["evidence_gate"]["github_call_performed"] is False
    assert ready_plan["evidence_gate"]["repository_write_performed"] is False
    assert "github_not_called" in ready_receipt["actions_not_taken"]
    assert "pull_request_not_merged" in ready_receipt["actions_not_taken"]


def test_github_codex_projection_validator_rejects_live_execution_authority(tmp_path: Path) -> None:
    candidate = build_runtime_github_codex_projection_evidence()
    candidate["effect_boundary"]["execution_allowed"] = True
    candidate["effect_boundary"]["github_call_allowed"] = True
    candidate["projections"][0]["plan"]["github_call_allowed"] = True
    candidate["projections"][0]["plan"]["evidence_gate"]["github_call_performed"] = True
    candidate_path = tmp_path / "github_codex_projection.json"
    candidate_path.write_text(json.dumps(candidate), encoding="utf-8")

    result = validate_personal_assistant_github_codex_projection(projection_path=candidate_path)

    assert result.valid is False
    assert any("execution_allowed" in error for error in result.errors)
    assert any("github_call_allowed" in error for error in result.errors)
    assert any("github_call_performed" in error for error in result.errors)
    assert not any("private" in error.lower() and "summary" in error.lower() for error in result.errors)


def test_github_codex_projection_validator_rejects_receipt_drift(tmp_path: Path) -> None:
    candidate = build_runtime_github_codex_projection_evidence()
    receipt = candidate["projections"][0]["receipt"]
    receipt["actions_not_taken"].remove("github_not_called")
    receipt["metadata"]["repository_mutation_allowed"] = True
    candidate["receipt_ids"] = ["pa_receipt_wrong"]
    candidate_path = tmp_path / "github_codex_projection.json"
    candidate_path.write_text(json.dumps(candidate), encoding="utf-8")

    result = validate_personal_assistant_github_codex_projection(projection_path=candidate_path)

    assert result.valid is False
    assert any("github_not_called" in error for error in result.errors)
    assert any("repository_mutation_allowed" in error for error in result.errors)
    assert any("receipt_ids must match" in error for error in result.errors)


def test_github_codex_projection_validator_rejects_raw_diff_and_secret(tmp_path: Path) -> None:
    candidate = build_runtime_github_codex_projection_evidence()
    candidate["projections"][0]["plan"]["raw_diff"] = "diff --git private payload"
    candidate["projections"][1]["plan"]["codex_instruction"] = "Use Bearer secret-token-value"
    candidate_path = tmp_path / "github_codex_projection.json"
    candidate_path.write_text(json.dumps(candidate), encoding="utf-8")

    result = validate_personal_assistant_github_codex_projection(projection_path=candidate_path)
    serialized_errors = "\n".join(result.errors)

    assert result.valid is False
    assert "raw_diff" in serialized_errors
    assert "secret-like value" in serialized_errors
    assert "diff --git private payload" not in serialized_errors


def test_github_codex_projection_validator_requires_ready_and_blocked_items(tmp_path: Path) -> None:
    candidate = build_runtime_github_codex_projection_evidence()
    ready_only = copy.deepcopy(candidate)
    ready_only["projections"] = [candidate["projections"][1]]
    ready_only["projection_count"] = 1
    ready_only["projection_ids"] = [candidate["projection_ids"][1]]
    ready_only["receipt_ids"] = [candidate["receipt_ids"][1]]
    candidate_path = tmp_path / "github_codex_projection.json"
    candidate_path.write_text(json.dumps(ready_only), encoding="utf-8")

    result = validate_personal_assistant_github_codex_projection(projection_path=candidate_path)

    assert result.valid is False
    assert any("blocked projection" in error for error in result.errors)
    assert not any("review-ready projection" in error for error in result.errors)
