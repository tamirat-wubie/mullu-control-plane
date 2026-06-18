"""Verify the Foundation CDG-RCCM component contract and fail-closed guards."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_cdg_rccm_component_contract import (
    DEFAULT_CONTRACT_PATH,
    DEFAULT_SCHEMA_PATH,
    REQUIRED_EVIDENCE_REFS,
    build_mutated_contract,
    validate_contract,
    validate_contract_record,
    validate_schema_artifact,
)
from scripts.validate_schemas import _load_schema


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_default_component_contract_validates() -> None:
    assert DEFAULT_SCHEMA_PATH == REPO_ROOT / "schemas" / "cdg_rccm_component_contract.schema.json"
    assert DEFAULT_CONTRACT_PATH == REPO_ROOT / "examples" / "cdg_rccm_component_contract.foundation.json"
    assert validate_contract() == []


def test_schema_is_closed_and_versioned() -> None:
    schema = _load_schema(DEFAULT_SCHEMA_PATH)

    assert validate_schema_artifact(schema) == []
    assert schema["additionalProperties"] is False
    assert schema["properties"]["contract_version"]["const"] == "cdg_rccm_component_contract.v1"
    assert schema["properties"]["protocol_version"]["const"] == "cdg-rccm.v1"
    assert schema["properties"]["surface"]["const"] == "foundation_cdg_rccm_component_contract"


def test_runtime_authority_guards_fail_closed() -> None:
    for guard_name in (
        "runtime_route_registration_claimed",
        "connector_authority_granted",
        "deployment_claimed",
    ):
        record = build_mutated_contract(**{f"runtime_guards__{guard_name}": True})
        errors = validate_contract_record(record)
        assert any(f"runtime_guards.{guard_name}" in error for error in errors)


def test_required_safety_guards_cannot_be_disabled() -> None:
    for guard_name in (
        "component_self_certification_denied",
        "hidden_dependency_reads_denied",
        "direct_external_effects_denied",
        "cross_epoch_reads_denied",
        "stale_certificate_consumption_denied",
    ):
        record = build_mutated_contract(**{f"runtime_guards__{guard_name}": False})
        errors = validate_contract_record(record)
        assert any(f"runtime_guards.{guard_name}" in error for error in errors)


def test_convergence_budget_and_oscillation_guards_are_required() -> None:
    zero_iterations = build_mutated_contract(convergence_policy__maximum_iterations=0)
    no_oscillation_guard = build_mutated_contract(convergence_policy__oscillation_detection=False)
    zero_frames = build_mutated_contract(budgets__maximum_frames=0)

    assert any("maximum_iterations" in error for error in validate_contract_record(zero_iterations))
    assert any("oscillation_detection" in error for error in validate_contract_record(no_oscillation_guard))
    assert any("maximum_frames" in error for error in validate_contract_record(zero_frames))


def test_evidence_refs_cover_runtime_schema_tests_docs_and_sdlc() -> None:
    payload = json.loads(DEFAULT_CONTRACT_PATH.read_text(encoding="utf-8"))
    evidence_refs = set(payload["evidence_refs"])

    assert set(REQUIRED_EVIDENCE_REFS) <= evidence_refs
    assert all((REPO_ROOT / ref).exists() for ref in REQUIRED_EVIDENCE_REFS)


def test_receipt_prefixes_are_enforced() -> None:
    record = build_mutated_contract(receipt_envelope__receipt_ref="invalid")
    errors = validate_contract_record(record)

    assert any("receipt_envelope.receipt_ref" in error for error in errors)


def test_duplicate_projection_and_invariant_labels_are_rejected() -> None:
    payload = json.loads(DEFAULT_CONTRACT_PATH.read_text(encoding="utf-8"))
    payload["output_projections"] = ["component_result_projection", "component_result_projection"]
    payload["immutable_invariants"] = ["same", "same"]
    errors = validate_contract_record(payload)

    assert any("output_projections" in error for error in errors)
    assert any("immutable_invariants" in error for error in errors)
