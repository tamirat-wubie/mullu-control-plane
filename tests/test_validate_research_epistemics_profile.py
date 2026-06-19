from __future__ import annotations

from copy import deepcopy

from scripts.validate_research_epistemics_profile import (
    DEFAULT_PROFILE_PATH,
    DEFAULT_SCHEMA_PATH,
    build_mutated_research_epistemics_profile,
    load_json_object,
    validate_research_epistemics_profile,
    validate_research_epistemics_profile_record,
    validate_schema_artifact,
)
from scripts.validate_schemas import _load_schema


def _schema() -> dict:
    return _load_schema(DEFAULT_SCHEMA_PATH)


def _profile() -> dict:
    return load_json_object(DEFAULT_PROFILE_PATH, "profile")


def test_default_profile_passes() -> None:
    assert validate_research_epistemics_profile() == []


def test_schema_artifact_passes() -> None:
    assert validate_schema_artifact(_schema()) == []


def test_runtime_execution_authority_fails_closed() -> None:
    profile = build_mutated_research_epistemics_profile(
        authority_boundary__runtime_research_execution_allowed=True
    )
    errors = validate_research_epistemics_profile_record(profile, _schema())
    assert any("runtime_research_execution_allowed" in error for error in errors)


def test_memory_write_authority_fails_closed() -> None:
    profile = build_mutated_research_epistemics_profile(
        authority_boundary__memory_write_allowed=True
    )
    errors = validate_research_epistemics_profile_record(profile, _schema())
    assert any("memory_write_allowed" in error for error in errors)


def test_truth_mutation_authority_fails_closed() -> None:
    profile = build_mutated_research_epistemics_profile(
        authority_boundary__truth_mutation_allowed=True
    )
    errors = validate_research_epistemics_profile_record(profile, _schema())
    assert any("truth_mutation_allowed" in error for error in errors)


def test_medical_authority_fails_closed() -> None:
    profile = build_mutated_research_epistemics_profile(
        authority_boundary__medical_decision_authority=True
    )
    errors = validate_research_epistemics_profile_record(profile, _schema())
    assert any("medical_decision_authority" in error for error in errors)


def test_scalar_confidence_cannot_be_canonical() -> None:
    profile = build_mutated_research_epistemics_profile(
        epistemic_contract__scalar_confidence_is_canonical=True
    )
    errors = validate_research_epistemics_profile_record(profile, _schema())
    assert any("scalar_confidence_is_canonical" in error for error in errors)


def test_truth_kernel_auto_promotion_is_denied() -> None:
    profile = build_mutated_research_epistemics_profile(
        epistemic_contract__truth_kernel_auto_promotion=True
    )
    errors = validate_research_epistemics_profile_record(profile, _schema())
    assert any("truth_kernel_auto_promotion" in error for error in errors)


def test_claim_type_sequence_drift_is_rejected() -> None:
    profile = _profile()
    profile["epistemic_contract"]["claim_types"].reverse()
    errors = validate_research_epistemics_profile_record(profile, _schema())
    assert any("claim_types must match the canonical sequence" in error for error in errors)


def test_compatibility_drift_is_rejected() -> None:
    profile = build_mutated_research_epistemics_profile(
        compatibility__research_runtime_ref="parallel/wre_engine.py"
    )
    errors = validate_research_epistemics_profile_record(profile, _schema())
    assert any("compatibility refs" in error for error in errors)


def test_runtime_contract_gate_remains_closed() -> None:
    profile = build_mutated_research_epistemics_profile(
        next_gate__runtime_contracts_allowed=True
    )
    errors = validate_research_epistemics_profile_record(profile, _schema())
    assert any("PR #1960" in error for error in errors)


def test_required_evidence_ref_is_enforced() -> None:
    profile = deepcopy(_profile())
    profile["evidence_refs"].remove("docs/WRE_A2_RESEARCH_EPISTEMICS_PROFILE.md")
    errors = validate_research_epistemics_profile_record(profile, _schema())
    assert any("docs/WRE_A2_RESEARCH_EPISTEMICS_PROFILE.md" in error for error in errors)


def test_unknown_top_level_field_is_rejected_by_schema() -> None:
    profile = _profile()
    profile["unexpected"] = True
    errors = validate_research_epistemics_profile_record(profile, _schema())
    assert errors
