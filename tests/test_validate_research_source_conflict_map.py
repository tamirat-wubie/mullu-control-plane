"""Purpose: verify ResearchSourceConflictMap validation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_research_source_conflict_map and SDLC validator.
Invariants:
  - Research source conflicts remain citation-bound.
  - Foundation Mode does not grant live search, source contact, connector,
    publication, memory-write, answer-synthesis, or terminal authority.
  - Raw source bodies and secret values are not stored.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_research_source_conflict_map as validator
from scripts import validate_sdlc_artifact as sdlc_validator


def test_research_source_conflict_map_passes() -> None:
    errors = validator.validate_research_source_conflict_map()
    conflict_map = validator.load_json_object(validator.DEFAULT_MAP_PATH, "ResearchSourceConflictMap")

    assert errors == []
    assert conflict_map["map_version"] == validator.EXPECTED_MAP_VERSION
    assert conflict_map["research_scope"]["source_mode"] == "operator_supplied_citation_refs"
    assert conflict_map["research_scope"]["tenant_scope"] == "foundation-local-only"
    assert conflict_map["authority_boundary"]["web_search_performed"] is False
    assert conflict_map["authority_boundary"]["answer_synthesis_allowed"] is False
    assert conflict_map["retention_policy"]["raw_source_bodies_retained"] is False
    assert validator.validate_research_source_conflict_map_record(conflict_map) == []


def test_research_source_conflict_map_rejects_authority_drift() -> None:
    mutated = validator.build_mutated_research_source_conflict_map(
        authority_boundary__external_retrieval_performed=True,
        authority_boundary__web_search_performed=True,
        authority_boundary__connector_call_performed=True,
        authority_boundary__source_contact_performed=True,
        authority_boundary__answer_synthesis_allowed=True,
        authority_boundary__current_claim_allowed=True,
        authority_boundary__memory_write_performed=True,
        authority_boundary__publication_allowed=True,
        authority_boundary__terminal_closure_allowed=True,
        authority_boundary__success_claim_allowed=True,
    )

    errors = validator.validate_research_source_conflict_map_record(mutated)

    assert any("authority_boundary.external_retrieval_performed" in error for error in errors)
    assert any("authority_boundary.web_search_performed" in error for error in errors)
    assert any("authority_boundary.connector_call_performed" in error for error in errors)
    assert any("authority_boundary.source_contact_performed" in error for error in errors)
    assert any("authority_boundary.answer_synthesis_allowed" in error for error in errors)
    assert any("authority_boundary.current_claim_allowed" in error for error in errors)
    assert any("authority_boundary.memory_write_performed" in error for error in errors)
    assert any("authority_boundary.terminal_closure_allowed" in error for error in errors)


def test_research_source_conflict_map_rejects_raw_body_and_digest_drift() -> None:
    mutated = validator.build_mutated_research_source_conflict_map(
        research_scope__research_question_hash="https://example.com/question",
        source_set__0__claim_digest_ref="claim://raw",
        source_set__0__source_summary_digest_ref="https://example.com/source-body",
        source_set__0__raw_source_body="raw body must not be retained",
        retention_policy__raw_source_bodies_retained=True,
        retention_policy__private_payload_redacted=False,
        retention_policy__operator_review_required=False,
    )

    errors = validator.validate_research_source_conflict_map_record(mutated)

    assert any("research_question_hash must use hash://sha256/" in error for error in errors)
    assert any("research_question_hash must not store raw source URL or body" in error for error in errors)
    assert any("source_set[0].claim_digest_ref must use hash://sha256/" in error for error in errors)
    assert any("source_set[0].source_summary_digest_ref must use hash://sha256/" in error for error in errors)
    assert any("source_set[0].raw_source_body must be null" in error for error in errors)
    assert any("raw_source_bodies_retained" in error for error in errors)
    assert any("private_payload_redacted" in error for error in errors)
    assert any("operator_review_required" in error for error in errors)


def test_research_source_conflict_map_rejects_conflict_citation_drift() -> None:
    mutated = validator.build_mutated_research_source_conflict_map(
        conflict_set__0__citation_refs=["citation://unknown-a", "citation://unknown-b"],
        conflict_set__0__current_claim_allowed=True,
        conflict_set__0__severity="high",
        conflict_set__0__freshness_impact="none",
    )

    errors = validator.validate_research_source_conflict_map_record(mutated)

    assert any("citation_refs must be drawn from source_set" in error for error in errors)
    assert any("conflict_set[0].current_claim_allowed must be false" in error for error in errors)
    assert any("high severity requires freshness impact" in error for error in errors)


def test_research_source_conflict_map_rejects_follow_up_sensing_drift() -> None:
    mutated = validator.build_mutated_research_source_conflict_map(
        follow_up_sensing__0__conflict_ref="conflict://missing",
        follow_up_sensing__0__approval_required=False,
        follow_up_sensing__0__live_search_allowed=True,
        follow_up_sensing__0__source_contact_allowed=True,
    )

    errors = validator.validate_research_source_conflict_map_record(mutated)

    assert any("follow_up_sensing[0].conflict_ref" in error for error in errors)
    assert any("follow_up_sensing[0].approval_required" in error for error in errors)
    assert any("follow_up_sensing[0].live_search_allowed" in error for error in errors)
    assert any("follow_up_sensing[0].source_contact_allowed" in error for error in errors)


def test_research_source_conflict_map_rejects_receipt_ref_and_count_drift() -> None:
    mutated = validator.build_mutated_research_source_conflict_map(
        receipt_refs__research_source_conflict_map_schema="schemas/other.schema.json",
        receipt_refs__search_receipt_schema="schemas/other_search_receipt.schema.json",
        contract_summary__source_count=1,
        contract_summary__conflict_count=2,
        contract_summary__follow_up_sensing_count=2,
        contract_summary__authority_denial_count=1,
        contract_summary__receipt_ref_count=1,
        contract_summary__evidence_ref_count=1,
        evidence_refs=["schemas/research_source_conflict_map.schema.json"],
    )

    errors = validator.validate_research_source_conflict_map_record(mutated)

    assert any("receipt_refs.research_source_conflict_map_schema" in error for error in errors)
    assert any("receipt_refs.search_receipt_schema" in error for error in errors)
    assert any("contract_summary.source_count" in error for error in errors)
    assert any("contract_summary.conflict_count" in error for error in errors)
    assert any("contract_summary.follow_up_sensing_count" in error for error in errors)
    assert any("contract_summary.authority_denial_count" in error for error in errors)
    assert any("evidence_refs missing required ref" in error for error in errors)


def test_cli_json_accepts_relative_paths(capsys) -> None:
    exit_code = validator.main(
        [
            "--schema",
            "schemas/research_source_conflict_map.schema.json",
            "--map",
            "examples/research_source_conflict_map.foundation.json",
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "passed"
    assert Path(payload["schema_path"]).as_posix() == "schemas/research_source_conflict_map.schema.json"
    assert Path(payload["map_path"]).as_posix() == "examples/research_source_conflict_map.foundation.json"
    assert payload["errors"] == []


def test_malformed_research_source_conflict_map_reports_errors() -> None:
    schema = validator._load_schema(validator.DEFAULT_SCHEMA_PATH)

    none_errors = validator.validate_research_source_conflict_map_record(None, schema)
    list_errors = validator.validate_research_source_conflict_map_record([], schema)

    assert any("research source conflict map must be a JSON object" in error for error in none_errors)
    assert any("research source conflict map must be a JSON object" in error for error in list_errors)
    assert any("expected object" in error for error in none_errors + list_errors)


def test_sdlc_requirement_and_design_validate_for_research_source_conflict_map() -> None:
    requirement_path = Path("examples/sdlc/requirement_research_source_conflict_map_20260616.json")
    design_path = Path("examples/sdlc/design_research_source_conflict_map_20260616.json")
    requirement = sdlc_validator.load_json_object(requirement_path, "research source conflict map requirement")
    design = sdlc_validator.load_json_object(design_path, "research source conflict map design")

    requirement_errors = sdlc_validator.validate_artifact_record("requirement", requirement)
    design_errors = sdlc_validator.validate_artifact_record("design_decision", design)

    assert requirement_errors == []
    assert design_errors == []
    assert design["requirement_id"] == requirement["requirement_id"]
    assert "schemas/research_source_conflict_map.schema.json" in requirement["affected_surfaces"]
    assert "schemas/research_source_conflict_map.schema.json" in design["schema_changes"]
    assert "scripts/validate_research_source_conflict_map.py" in design["validator_changes"]
    assert "tests/test_validate_research_source_conflict_map.py" in design["validator_changes"]
    assert "no live web search" in requirement["non_goals"]
    assert design["security_model"]["effect_bearing_requires_receipt"] is True
