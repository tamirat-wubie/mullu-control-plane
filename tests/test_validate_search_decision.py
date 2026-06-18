"""Purpose: verify SearchDecision validation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_search_decision and SDLC validator.
Invariants:
  - Search decisions classify retrieval need before retrieval.
  - BudgetUnknown blocks deep search until approval.
  - Retrieved content remains evidence only, never instruction authority.
  - The SDLC requirement and design artifacts validate.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_sdlc_artifact as sdlc_validator
from scripts import validate_search_decision as validator


def test_search_decision_passes() -> None:
    errors = validator.validate_decision()
    decision = validator.load_json_object(validator.DEFAULT_DECISION_PATH, "SearchDecision")

    assert errors == []
    assert decision["decision_version"] == validator.EXPECTED_DECISION_VERSION
    assert decision["decision_state"] == "WEB_SEARCH_DEEP_APPROVAL_REQUIRED"
    assert decision["solver_outcome"] == "AwaitingEvidence"
    assert decision["budget_decision"]["proof_state"] == "BudgetUnknown"
    assert decision["source_plan"]["external_retrieval_allowed"] is False
    assert validator.validate_decision_record(decision) == []


def test_decision_rejects_authority_and_retrieval_claims() -> None:
    mutated = validator.build_mutated_decision(
        governance_guards__execution_authority_granted=True,
        governance_guards__connector_authority_granted=True,
        governance_guards__external_retrieval_performed=True,
        governance_guards__terminal_closure=True,
        governance_guards__raw_secret_material_included=True,
        governance_guards__retrieved_instruction_authority_granted=True,
    )

    errors = validator.validate_decision_record(mutated)

    assert any("execution_authority_granted" in error for error in errors)
    assert any("connector_authority_granted" in error for error in errors)
    assert any("external_retrieval_performed" in error for error in errors)
    assert any("terminal_closure" in error for error in errors)
    assert any("raw_secret_material_included" in error for error in errors)
    assert any("retrieved_instruction_authority_granted" in error for error in errors)
    assert mutated["governance_guards"]["mfidel_atomicity_preserved"] is True


def test_decision_rejects_state_budget_and_source_drift() -> None:
    mutated = validator.build_mutated_decision(
        decision_state="WEB_SEARCH_DEEP_APPROVAL_REQUIRED",
        budget_decision__state="within_budget",
        budget_decision__approval_required=False,
        budget_decision__proof_state="BudgetUnknown",
        source_plan__external_retrieval_allowed=True,
    )

    errors = validator.validate_decision_record(mutated)

    assert any("deep web search must require budget approval" in error for error in errors)
    assert any("BudgetUnknown requires approval_required true" in error for error in errors)
    assert any("cannot allow external retrieval" in error for error in errors)
    assert mutated["decision_state"] == "WEB_SEARCH_DEEP_APPROVAL_REQUIRED"
    assert "web" in mutated["source_plan"]["selected_sources"]


def test_decision_rejects_freshness_and_instruction_authority_drift() -> None:
    mutated = validator.build_mutated_decision(
        freshness__state="required",
        freshness__freshness_required=False,
        freshness__current_info_claim_allowed=True,
        retrieval_safety__retrieved_content_authority="instruction",
        retrieval_safety__prompt_injection_guard=False,
        retrieval_safety__tool_instruction_from_source_allowed=True,
        retrieval_safety__policy_instruction_from_source_allowed=True,
    )

    errors = validator.validate_decision_record(mutated)

    assert any("freshness_required must be true" in error for error in errors)
    assert any("current_info_claim_allowed must be false" in error for error in errors)
    assert any("retrieved content authority must remain evidence_only" in error for error in errors)
    assert any("prompt_injection_guard" in error for error in errors)
    assert any("tool_instruction_from_source_allowed" in error for error in errors)
    assert any("policy_instruction_from_source_allowed" in error for error in errors)


def test_decision_rejects_bad_prefix_and_evidence_drift() -> None:
    mutated = validator.build_mutated_decision(
        receipt_envelope__uao_ref="trace://wrong/search",
        receipt_envelope__causal_decision_trace_ref="receipt://wrong/search",
        receipt_envelope__receipt_ref="uao://wrong/search",
    )
    mutated["evidence_refs"] = [
        ref for ref in mutated["evidence_refs"] if ref != "tests/test_validate_search_decision.py"
    ]

    errors = validator.validate_decision_record(mutated)

    assert any("receipt_envelope.uao_ref" in error for error in errors)
    assert any("receipt_envelope.causal_decision_trace_ref" in error for error in errors)
    assert any("receipt_envelope.receipt_ref" in error for error in errors)
    assert any("evidence_refs missing required ref" in error for error in errors)
    assert mutated["governance_guards"]["external_retrieval_performed"] is False


def test_saved_decision_file_validation(tmp_path: Path) -> None:
    decision_path = tmp_path / "search_decision.json"
    decision = validator.load_json_object(validator.DEFAULT_DECISION_PATH, "SearchDecision")
    decision_path.write_text(json.dumps(decision), encoding="utf-8")

    loaded = validator.load_json_object(decision_path, "saved SearchDecision")
    errors = validator.validate_decision_record(loaded)

    assert errors == []
    assert loaded["decision_id"] == "search-decision-foundation-current-status-20260614"
    assert loaded["receipt_envelope"]["uao_ref"].startswith("uao://")
    assert loaded["receipt_envelope"]["causal_decision_trace_ref"].startswith("trace://")
    assert loaded["receipt_envelope"]["receipt_ref"].startswith("receipt://")


def test_cli_json_accepts_relative_paths(capsys) -> None:
    exit_code = validator.main(
        [
            "--schema",
            "schemas/search_decision.schema.json",
            "--decision",
            "examples/search_decision.foundation.json",
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "passed"
    assert Path(payload["schema_path"]).as_posix() == "schemas/search_decision.schema.json"
    assert Path(payload["decision_path"]).as_posix() == "examples/search_decision.foundation.json"
    assert payload["errors"] == []


def test_malformed_decision_payload_reports_errors() -> None:
    schema = validator._load_schema(validator.DEFAULT_SCHEMA_PATH)

    none_errors = validator.validate_decision_record(None, schema)
    list_errors = validator.validate_decision_record([], schema)

    assert any("search decision must be a JSON object" in error for error in none_errors)
    assert any("search decision must be a JSON object" in error for error in list_errors)
    assert any("expected object" in error for error in none_errors + list_errors)


def test_sdlc_requirement_and_design_validate_for_search_decision() -> None:
    requirement_path = Path("examples/sdlc/requirement_search_decision_contract_20260614.json")
    design_path = Path("examples/sdlc/design_search_decision_contract_20260614.json")
    requirement = sdlc_validator.load_json_object(requirement_path, "SearchDecision requirement")
    design = sdlc_validator.load_json_object(design_path, "SearchDecision design")

    requirement_errors = sdlc_validator.validate_artifact_record("requirement", requirement)
    design_errors = sdlc_validator.validate_artifact_record("design_decision", design)

    assert requirement_errors == []
    assert design_errors == []
    assert design["requirement_id"] == requirement["requirement_id"]
    assert "schemas/search_decision.schema.json" in design["schema_changes"]
    assert "scripts/validate_search_decision.py" in design["validator_changes"]
    assert "no live search execution" in requirement["non_goals"]
    assert "BudgetUnknown blocks deep retrieval until approval evidence exists" in requirement["success_criteria"]
    assert design["security_model"]["effect_bearing_requires_receipt"] is True
    assert any("run_workspace_governance_checks.py" in command for command in design["test_plan"])
