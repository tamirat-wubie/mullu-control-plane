"""Tests for Personal Assistant research projection validation.

Purpose: prove research source-compare planning evidence remains schema-backed
and no-effect.
Governance scope: no web search, no source contact, no external submission, no
public posting, no paid action, no memory write, no raw source body storage, no
secret serialization, and receipt continuity.
Dependencies: personal-assistant research projection validator and fixture.
Invariants:
  - Research projections are not live retrieval operations.
  - Citation-ready evidence still cannot post, submit, contact sources, or pay.
  - Receipts must record actions taken and actions not taken.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.validate_personal_assistant_research_projection import (
    build_runtime_research_projection_evidence,
    validate_personal_assistant_research_projection,
)


def test_personal_assistant_research_projection_fixture_validates() -> None:
    result = validate_personal_assistant_research_projection()

    assert result.valid is True
    assert result.projection_count == 2
    assert result.receipt_count == 2
    assert result.runtime_validated is True
    assert result.assurance_outcome == "AwaitingEvidence"
    assert result.errors == ()


def test_runtime_research_projection_blocks_effect_boundaries() -> None:
    envelope = build_runtime_research_projection_evidence()
    effect_boundary = envelope["effect_boundary"]
    ready_projection = envelope["projections"][1]
    ready_plan = ready_projection["plan"]
    ready_receipt = ready_projection["receipt"]

    assert effect_boundary["research_compare_records_allowed"] is True
    assert effect_boundary["execution_allowed"] is False
    assert effect_boundary["web_search_allowed"] is False
    assert effect_boundary["source_contact_allowed"] is False
    assert effect_boundary["external_submission_allowed"] is False
    assert effect_boundary["public_post_allowed"] is False
    assert effect_boundary["paid_subscription_allowed"] is False
    assert effect_boundary["memory_write_allowed"] is False
    assert ready_plan["evidence_gate"]["operator_supplied_evidence_complete"] is True
    assert ready_plan["evidence_gate"]["web_search_performed"] is False
    assert ready_plan["answer_claim_authority"] == "citation_backed_summary_only"
    assert "web_search_not_performed" in ready_receipt["actions_not_taken"]
    assert "public_post_not_created" in ready_receipt["actions_not_taken"]


def test_research_projection_validator_rejects_live_execution_authority(tmp_path: Path) -> None:
    candidate = build_runtime_research_projection_evidence()
    candidate["effect_boundary"]["execution_allowed"] = True
    candidate["effect_boundary"]["web_search_allowed"] = True
    candidate["projections"][0]["plan"]["web_search_allowed"] = True
    candidate["projections"][0]["plan"]["evidence_gate"]["web_search_performed"] = True
    candidate_path = tmp_path / "research_projection.json"
    candidate_path.write_text(json.dumps(candidate), encoding="utf-8")

    result = validate_personal_assistant_research_projection(projection_path=candidate_path)

    assert result.valid is False
    assert any("execution_allowed" in error for error in result.errors)
    assert any("web_search_allowed" in error for error in result.errors)
    assert any("web_search_performed" in error for error in result.errors)
    assert not any("secret-like" in error.lower() for error in result.errors)


def test_research_projection_validator_rejects_receipt_drift(tmp_path: Path) -> None:
    candidate = build_runtime_research_projection_evidence()
    receipt = candidate["projections"][0]["receipt"]
    receipt["actions_not_taken"].remove("web_search_not_performed")
    receipt["metadata"]["memory_write_allowed"] = True
    candidate["receipt_ids"] = ["pa_receipt_wrong"]
    candidate_path = tmp_path / "research_projection.json"
    candidate_path.write_text(json.dumps(candidate), encoding="utf-8")

    result = validate_personal_assistant_research_projection(projection_path=candidate_path)

    assert result.valid is False
    assert any("web_search_not_performed" in error for error in result.errors)
    assert any("memory_write_allowed" in error for error in result.errors)
    assert any("receipt_ids must match" in error for error in result.errors)


def test_research_projection_validator_rejects_raw_body_and_secret(tmp_path: Path) -> None:
    candidate = build_runtime_research_projection_evidence()
    candidate["projections"][0]["plan"]["source_summaries"].append(
        {
            "source_ref": "source://private",
            "title": "Private body",
            "publisher": "operator",
            "published_at": "",
            "summary": "bounded",
            "trust_tier": "operator_supplied",
            "citation_ref": "citation://private",
            "raw_source_body": "full retrieved page text",
        }
    )
    candidate["projections"][1]["plan"]["source_compare"] = "Use Bearer secret-token-value"
    candidate_path = tmp_path / "research_projection.json"
    candidate_path.write_text(json.dumps(candidate), encoding="utf-8")

    result = validate_personal_assistant_research_projection(projection_path=candidate_path)
    serialized_errors = "\n".join(result.errors)

    assert result.valid is False
    assert "raw_source_body" in serialized_errors
    assert "secret-like value" in serialized_errors
    assert "full retrieved page text" not in serialized_errors


def test_research_projection_validator_requires_ready_and_blocked_items(tmp_path: Path) -> None:
    candidate = build_runtime_research_projection_evidence()
    ready_only = copy.deepcopy(candidate)
    ready_only["projections"] = [candidate["projections"][1]]
    ready_only["projection_count"] = 1
    ready_only["projection_ids"] = [candidate["projection_ids"][1]]
    ready_only["receipt_ids"] = [candidate["receipt_ids"][1]]
    candidate_path = tmp_path / "research_projection.json"
    candidate_path.write_text(json.dumps(ready_only), encoding="utf-8")

    result = validate_personal_assistant_research_projection(projection_path=candidate_path)

    assert result.valid is False
    assert any("blocked projection" in error for error in result.errors)
    assert not any("citation-ready projection" in error for error in result.errors)
