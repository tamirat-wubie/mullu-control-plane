"""Purpose: verify CDG-RCCM Architecture Contract validation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_cdg_rccm_architecture_contract.
Invariants:
  - CDG-RCCM remains a Foundation Mode architecture contract.
  - Universal protocol compatibility does not claim universal convergence.
  - Components cannot self-certify.
  - Live runtime dispatch, external writes, production certificates, terminal
    closure, and success claims remain denied.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_cdg_rccm_architecture_contract as validator


def test_cdg_rccm_architecture_contract_passes() -> None:
    errors = validator.validate_cdg_rccm_architecture_contract()
    contract = validator.load_json_object(validator.DEFAULT_CONTRACT_PATH, "CDG-RCCM Architecture Contract")

    assert errors == []
    assert contract["contract_version"] == validator.EXPECTED_CONTRACT_VERSION
    assert contract["source_spec"]["canonical_name"] == "CDG-RCCM"
    assert contract["source_spec"]["universal_termination_claimed"] is False
    assert contract["foundation_boundary"]["foundation_mode"] is True
    assert contract["authority_boundary"]["no_component_self_certifies"] is True
    assert contract["authority_boundary"]["terminal_closure_allowed"] is False
    assert validator.validate_cdg_rccm_architecture_contract_record(contract) == []


def test_cdg_rccm_rejects_universal_and_live_runtime_drift() -> None:
    mutated = validator.build_mutated_cdg_rccm_architecture_contract(
        source_spec__standard_status="industry_standard",
        source_spec__universal_termination_claimed=True,
        source_spec__universal_profile_meaning="all_components_terminate",
        foundation_boundary__live_runtime_claimed=True,
        foundation_boundary__global_convergence_claimed=True,
        foundation_boundary__world_verification_claimed=True,
        foundation_boundary__runtime_certificate_issuer_claimed=True,
    )

    errors = validator.validate_cdg_rccm_architecture_contract_record(mutated)

    assert any("source_spec.standard_status" in error for error in errors)
    assert any("source_spec.universal_termination_claimed" in error for error in errors)
    assert any("source_spec.universal_profile_meaning" in error for error in errors)
    assert any("foundation_boundary.live_runtime_claimed" in error for error in errors)
    assert any("foundation_boundary.global_convergence_claimed" in error for error in errors)
    assert any("foundation_boundary.world_verification_claimed" in error for error in errors)
    assert any("foundation_boundary.runtime_certificate_issuer_claimed" in error for error in errors)


def test_cdg_rccm_rejects_topology_and_sequence_drift() -> None:
    mutated = validator.build_mutated_cdg_rccm_architecture_contract(
        mesh_model__containment_dependency_separated=False,
        mesh_model__containment_acyclic_required=False,
        mesh_model__dependency_edge_types=["REQUIRES"],
        execution_protocol__governing_sequence=["frame_component", "certify_root"],
        execution_protocol__step_outcomes=["Progress"],
        execution_protocol__independent_certificate_kernel_required=False,
    )

    errors = validator.validate_cdg_rccm_architecture_contract_record(mutated)

    assert any("mesh_model.containment_dependency_separated" in error for error in errors)
    assert any("mesh_model.containment_acyclic_required" in error for error in errors)
    assert any("mesh_model.dependency_edge_types" in error for error in errors)
    assert any("execution_protocol.governing_sequence" in error for error in errors)
    assert any("execution_protocol.step_outcomes" in error for error in errors)
    assert any("independent_certificate_kernel_required" in error for error in errors)


def test_cdg_rccm_rejects_request_convergence_and_cycle_drift() -> None:
    mutated = validator.build_mutated_cdg_rccm_architecture_contract(
        dependency_request_contract__required_fields=["requester", "provider"],
        dependency_request_contract__gates=["HARD"],
        convergence_contracts__declared_methods=["bounded_search"],
        convergence_contracts__budget_exhaustion_outcome="CERTIFIED",
        cycle_handling__cycle_classes=["SEMANTIC_FEEDBACK"],
        cycle_handling__structural_containment_rejected=False,
    )

    errors = validator.validate_cdg_rccm_architecture_contract_record(mutated)

    assert any("dependency_request_contract.required_fields" in error for error in errors)
    assert any("dependency_request_contract.gates" in error for error in errors)
    assert any("convergence_contracts.declared_methods" in error for error in errors)
    assert any("budget_exhaustion_outcome" in error for error in errors)
    assert any("cycle_handling.cycle_classes" in error for error in errors)
    assert any("structural_containment_rejected" in error for error in errors)


def test_cdg_rccm_rejects_closure_and_authority_drift() -> None:
    mutated = validator.build_mutated_cdg_rccm_architecture_contract(
        closure_certification__required_conditions=["all_consumed_information_is_dependency"],
        closure_certification__closure_outcomes=["CERTIFIED"],
        closure_certification__quiescence_is_not_correctness=False,
        closure_certification__world_claim_requires_evidence=False,
        authority_boundary__reasoning_only=False,
        authority_boundary__no_component_self_certifies=False,
        authority_boundary__live_runtime_dispatch_allowed=True,
        authority_boundary__external_write_allowed=True,
        authority_boundary__production_certificate_allowed=True,
        authority_boundary__terminal_closure_allowed=True,
        authority_boundary__success_claim_allowed=True,
    )

    errors = validator.validate_cdg_rccm_architecture_contract_record(mutated)

    assert any("closure_certification.required_conditions" in error for error in errors)
    assert any("closure_certification.closure_outcomes" in error for error in errors)
    assert any("quiescence_is_not_correctness" in error for error in errors)
    assert any("world_claim_requires_evidence" in error for error in errors)
    assert any("authority_boundary.reasoning_only" in error for error in errors)
    assert any("authority_boundary.no_component_self_certifies" in error for error in errors)
    assert any("authority_boundary.live_runtime_dispatch_allowed" in error for error in errors)
    assert any("authority_boundary.external_write_allowed" in error for error in errors)
    assert any("authority_boundary.production_certificate_allowed" in error for error in errors)
    assert any("authority_boundary.terminal_closure_allowed" in error for error in errors)
    assert any("authority_boundary.success_claim_allowed" in error for error in errors)


def test_cdg_rccm_rejects_summary_and_evidence_drift() -> None:
    mutated = validator.build_mutated_cdg_rccm_architecture_contract(
        contract_summary__dependency_gate_count=1,
        contract_summary__step_outcome_count=1,
        contract_summary__settlement_level_count=1,
        contract_summary__cycle_class_count=1,
        contract_summary__closure_outcome_count=1,
        contract_summary__authority_denied=False,
        evidence_refs=["docs/93_cdg_rccm_architecture_contract.md"],
    )

    errors = validator.validate_cdg_rccm_architecture_contract_record(mutated)

    assert any("contract_summary.dependency_gate_count" in error for error in errors)
    assert any("contract_summary.step_outcome_count" in error for error in errors)
    assert any("contract_summary.settlement_level_count" in error for error in errors)
    assert any("contract_summary.cycle_class_count" in error for error in errors)
    assert any("contract_summary.closure_outcome_count" in error for error in errors)
    assert any("contract_summary.authority_denied" in error for error in errors)
    assert any("evidence_refs missing required ref" in error for error in errors)


def test_cdg_rccm_cli_json_accepts_relative_paths(capsys) -> None:
    exit_code = validator.main(
        [
            "--schema",
            "schemas/cdg_rccm_architecture_contract.schema.json",
            "--contract",
            "examples/cdg_rccm_architecture_contract.foundation.json",
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "passed"
    assert Path(payload["schema_path"]).as_posix() == "schemas/cdg_rccm_architecture_contract.schema.json"
    assert Path(payload["contract_path"]).as_posix() == "examples/cdg_rccm_architecture_contract.foundation.json"
    assert payload["errors"] == []


def test_malformed_cdg_rccm_contract_reports_errors() -> None:
    schema = validator._load_schema(validator.DEFAULT_SCHEMA_PATH)

    none_errors = validator.validate_cdg_rccm_architecture_contract_record(None, schema)
    list_errors = validator.validate_cdg_rccm_architecture_contract_record([], schema)

    assert any("cdg-rccm architecture contract must be a JSON object" in error for error in none_errors)
    assert any("cdg-rccm architecture contract must be a JSON object" in error for error in list_errors)
    assert any("expected object" in error for error in none_errors + list_errors)
