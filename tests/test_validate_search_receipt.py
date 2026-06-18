"""Purpose: verify SearchReceipt validation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_search_receipt and SDLC validator.
Invariants:
  - Search receipts record evidence metadata after a search decision.
  - Current claims require fresh evidence and citations.
  - Retrieved content bodies and source-provided instruction authority are rejected.
  - The SDLC requirement and design artifacts validate.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_sdlc_artifact as sdlc_validator
from scripts import validate_search_receipt as validator


def test_search_receipt_passes() -> None:
    errors = validator.validate_receipt()
    receipt = validator.load_json_object(validator.DEFAULT_RECEIPT_PATH, "SearchReceipt")

    assert errors == []
    assert receipt["receipt_version"] == validator.EXPECTED_RECEIPT_VERSION
    assert receipt["receipt_state"] == "RETRIEVAL_BLOCKED"
    assert receipt["solver_outcome"] == "AwaitingEvidence"
    assert receipt["evidence_summary"]["evidence_count"] == 0
    assert receipt["source_plan_result"]["external_retrieval_performed"] is False
    assert receipt["budget_result"]["budget_binding_state"] == "budget_unknown_blocked"
    assert receipt["budget_result"]["budget_decision_ref"] == receipt["search_decision_ref"]
    assert validator.validate_receipt_record(receipt) == []


def test_receipt_rejects_count_drift_and_content_body() -> None:
    mutated = validator.build_mutated_receipt(
        evidence_summary__retrieval_error_count=0,
        evidence_summary__content_body_included=True,
    )

    errors = validator.validate_receipt_record(mutated)

    assert any("retrieval_error_count" in error for error in errors)
    assert any("retrieved content body must not be included" in error for error in errors)
    assert mutated["retrieval_errors"]
    assert mutated["evidence_summary"]["content_body_included"] is True


def test_receipt_rejects_blocked_state_without_errors_or_evidence_zero() -> None:
    mutated = validator.build_mutated_receipt(
        receipt_state="RETRIEVAL_BLOCKED",
        retrieval_errors=[],
        evidence_summary__evidence_count=1,
    )

    errors = validator.validate_receipt_record(mutated)

    assert any("blocked or failed retrieval must include retrieval_errors" in error for error in errors)
    assert any("blocked or failed retrieval cannot claim evidence_count" in error for error in errors)
    assert mutated["receipt_state"] == "RETRIEVAL_BLOCKED"
    assert mutated["evidence_summary"]["evidence_count"] == 1


def test_receipt_rejects_current_claim_without_fresh_pass_evidence() -> None:
    mutated = validator.build_mutated_receipt(
        freshness_result__current_info_claim_allowed=True,
        freshness_result__freshness_status="unknown_blocked",
        freshness_result__proof_state="Unknown",
        governance_guards__answer_claim_authority_granted=True,
    )

    errors = validator.validate_receipt_record(mutated)

    assert any("current_info_claim_allowed requires fresh Pass evidence" in error for error in errors)
    assert any("answer claim authority requires citation_refs" in error for error in errors)
    assert mutated["governance_guards"]["answer_claim_authority_granted"] is True
    assert mutated["citation_refs"] == []


def test_receipt_accepts_fresh_evidence_with_citation_metadata_only() -> None:
    mutated = validator.build_mutated_receipt(
        solver_outcome="SolvedVerified",
        receipt_state="EVIDENCE_AVAILABLE",
        search_state="LOCAL_SEARCH",
        freshness_result__freshness_status="fresh",
        freshness_result__current_info_claim_allowed=True,
        freshness_result__proof_state="Pass",
        source_plan_result__selected_sources=["local_docs"],
        source_plan_result__attempted_sources=["local_docs"],
        budget_result__state="within_budget",
        budget_result__actual_cost_class="none",
        budget_result__proof_state="Pass",
        budget_result__budget_decision_ref="receipt://search-decision/foundation-current-status/20260614",
        budget_result__decision_budget_state="allowed",
        budget_result__decision_estimated_cost_units=0.1,
        budget_result__decision_budget_limit_units=1.0,
        budget_result__decision_budget_remaining_units=0.9,
        budget_result__budget_binding_state="bound_to_search_decision",
        evidence_summary__evidence_count=1,
        evidence_summary__citation_count=1,
        evidence_summary__retrieval_error_count=0,
        governance_guards__answer_claim_authority_granted=True,
    )
    mutated["retrieval_errors"] = []
    mutated["citation_refs"] = ["citation://local-docs/search-receipt-contract"]
    mutated["evidence_items"] = [
        {
            "evidence_ref": "evidence://local-docs/search-receipt-contract",
            "source_type": "local_docs",
            "source_ref": "docs/78_search_receipt_contract.md",
            "citation_ref": "citation://local-docs/search-receipt-contract",
            "observed_at": "2026-06-14T09:06:00Z",
            "fresh_until": "2026-06-14T10:06:00Z",
            "freshness_status": "fresh",
            "trust_tier": "local_governed",
            "content_hash_ref": "hash://sha256/search-receipt-contract",
            "content_body": None,
        }
    ]

    errors = validator.validate_receipt_record(mutated)

    assert errors == []
    assert mutated["evidence_items"][0]["content_body"] is None
    assert mutated["freshness_result"]["current_info_claim_allowed"] is True
    assert mutated["governance_guards"]["answer_claim_authority_granted"] is True


def test_receipt_rejects_budget_decision_binding_drift() -> None:
    mutated = validator.build_mutated_receipt(
        budget_result__budget_decision_ref="receipt://search-decision/different",
        budget_result__decision_budget_state="allowed",
        budget_result__decision_estimated_cost_units=0.1,
        budget_result__decision_budget_limit_units=1.0,
        budget_result__decision_budget_remaining_units=0.8,
        budget_result__budget_binding_state="bound_to_search_decision",
        budget_result__state="approval_required",
        budget_result__proof_state="BudgetUnknown",
    )

    errors = validator.validate_receipt_record(mutated)

    assert any("budget_decision_ref must match search_decision_ref" in error for error in errors)
    assert any("bound search budget requires allowed decision" in error for error in errors)
    assert any("remaining_units must match" in error for error in errors)
    assert mutated["budget_result"]["budget_decision_ref"] != mutated["search_decision_ref"]


def test_receipt_rejects_evidence_item_with_unlisted_citation_or_body() -> None:
    mutated = validator.build_mutated_receipt(
        receipt_state="EVIDENCE_AVAILABLE",
        evidence_summary__evidence_count=1,
        evidence_summary__citation_count=1,
    )
    mutated["citation_refs"] = ["citation://listed"]
    mutated["evidence_items"] = [
        {
            "evidence_ref": "evidence://item",
            "source_type": "web",
            "source_ref": "https://example.invalid",
            "citation_ref": "citation://missing",
            "observed_at": None,
            "fresh_until": None,
            "freshness_status": "unknown",
            "trust_tier": "unknown",
            "content_hash_ref": "hash://sha256/item",
            "content_body": "retrieved body",
        }
    ]

    errors = validator.validate_receipt_record(mutated)

    assert any("content_body" in error for error in errors)
    assert any("citation_ref must be listed in citation_refs" in error for error in errors)
    assert any("content_body: expected null" in error for error in errors)
    assert mutated["evidence_items"][0]["content_body"] == "retrieved body"


def test_receipt_rejects_instruction_authority_and_guard_drift() -> None:
    mutated = validator.build_mutated_receipt(
        retrieval_safety_result__retrieved_content_authority="instruction",
        retrieval_safety_result__prompt_injection_guard_applied=False,
        retrieval_safety_result__source_instruction_authority_granted=True,
        retrieval_safety_result__tool_instruction_from_source_allowed=True,
        retrieval_safety_result__policy_instruction_from_source_allowed=True,
        governance_guards__retrieved_instruction_authority_granted=True,
        governance_guards__raw_secret_material_included=True,
    )

    errors = validator.validate_receipt_record(mutated)

    assert any("retrieved content authority must remain evidence_only" in error for error in errors)
    assert any("prompt_injection_guard_applied" in error for error in errors)
    assert any("source_instruction_authority_granted" in error for error in errors)
    assert any("tool_instruction_from_source_allowed" in error for error in errors)
    assert any("policy_instruction_from_source_allowed" in error for error in errors)
    assert any("retrieved_instruction_authority_granted" in error for error in errors)
    assert any("raw_secret_material_included" in error for error in errors)


def test_cli_json_accepts_relative_paths(capsys) -> None:
    exit_code = validator.main(
        [
            "--schema",
            "schemas/search_receipt.schema.json",
            "--receipt",
            "examples/search_receipt.foundation.json",
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "passed"
    assert Path(payload["schema_path"]).as_posix() == "schemas/search_receipt.schema.json"
    assert Path(payload["receipt_path"]).as_posix() == "examples/search_receipt.foundation.json"
    assert payload["errors"] == []


def test_malformed_receipt_payload_reports_errors() -> None:
    schema = validator._load_schema(validator.DEFAULT_SCHEMA_PATH)

    none_errors = validator.validate_receipt_record(None, schema)
    list_errors = validator.validate_receipt_record([], schema)

    assert any("search receipt must be a JSON object" in error for error in none_errors)
    assert any("search receipt must be a JSON object" in error for error in list_errors)
    assert any("expected object" in error for error in none_errors + list_errors)


def test_sdlc_requirement_and_design_validate_for_search_receipt() -> None:
    requirement_path = Path("examples/sdlc/requirement_search_receipt_contract_20260614.json")
    design_path = Path("examples/sdlc/design_search_receipt_contract_20260614.json")
    requirement = sdlc_validator.load_json_object(requirement_path, "SearchReceipt requirement")
    design = sdlc_validator.load_json_object(design_path, "SearchReceipt design")

    requirement_errors = sdlc_validator.validate_artifact_record("requirement", requirement)
    design_errors = sdlc_validator.validate_artifact_record("design_decision", design)

    assert requirement_errors == []
    assert design_errors == []
    assert design["requirement_id"] == requirement["requirement_id"]
    assert "schemas/search_receipt.schema.json" in design["schema_changes"]
    assert "scripts/validate_search_receipt.py" in design["validator_changes"]
    assert "no live search execution" in requirement["non_goals"]
    assert "SearchReceipt records retrieval errors without claiming current facts" in requirement["success_criteria"]
    assert design["security_model"]["effect_bearing_requires_receipt"] is True
    assert any("run_workspace_governance_checks.py" in command for command in design["test_plan"])
