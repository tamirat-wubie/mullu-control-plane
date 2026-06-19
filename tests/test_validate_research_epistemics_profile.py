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


def test_default_profile_passes_with_canonical_identity() -> None:
    profile = _profile()

    assert validate_research_epistemics_profile() == []
    assert profile["profile_version"] == "research_epistemics_profile.v1"
    assert profile["canonical_names"]["epistemic_configuration"] == "Research Epistemics Profile v1"
    assert profile["canonical_names"]["internal_architecture"] == "MCOI Governed Research Architecture"


def test_schema_artifact_passes_with_canonical_title() -> None:
    schema = _schema()

    assert validate_schema_artifact(schema) == []
    assert schema["title"] == "Research Epistemics Profile v1"
    assert schema["$id"] == "urn:mullusi:schema:research-epistemics-profile:1"
    assert schema["additionalProperties"] is False


def test_mcoi_research_tuple_is_enforced() -> None:
    profile = build_mutated_research_epistemics_profile(
        mcoi_research_tuple__E="evidence_only"
    )
    errors = validate_research_epistemics_profile_record(profile, _schema())

    assert any("mcoi_research_tuple" in error for error in errors)
    assert any("$.mcoi_research_tuple.E" in error for error in errors)
    assert not any("authority_boundary" in error for error in errors)


def test_legacy_migration_name_cannot_become_canonical_profile_identity() -> None:
    profile = build_mutated_research_epistemics_profile(
        profile_version="wre_a2_research_epistemics.v1",
        canonical_names__epistemic_configuration="WRE-A2",
        canonical_names__legacy_migration_status="canonical",
    )
    errors = validate_research_epistemics_profile_record(profile, _schema())

    assert any("profile_version" in error for error in errors)
    assert any("canonical_names" in error for error in errors)
    assert any("legacy_migration_status" in error for error in errors)


def test_runtime_execution_authority_fails_closed() -> None:
    profile = build_mutated_research_epistemics_profile(
        authority_boundary__runtime_research_execution_allowed=True
    )
    errors = validate_research_epistemics_profile_record(profile, _schema())

    assert any("runtime_research_execution_allowed" in error for error in errors)
    assert any("$.authority_boundary.runtime_research_execution_allowed" in error for error in errors)
    assert not any("memory_write_allowed" in error for error in errors)


def test_memory_truth_and_medical_authority_fail_closed() -> None:
    profile = build_mutated_research_epistemics_profile(
        authority_boundary__memory_write_allowed=True,
        authority_boundary__truth_mutation_allowed=True,
        authority_boundary__medical_decision_authority=True,
    )
    errors = validate_research_epistemics_profile_record(profile, _schema())

    assert any("memory_write_allowed" in error for error in errors)
    assert any("truth_mutation_allowed" in error for error in errors)
    assert any("medical_decision_authority" in error for error in errors)


def test_scalar_confidence_projection_is_allowed_but_not_canonical() -> None:
    profile = build_mutated_research_epistemics_profile(
        epistemic_contract__scalar_confidence_projection_allowed=False,
        epistemic_contract__scalar_confidence_is_canonical=True,
    )
    errors = validate_research_epistemics_profile_record(profile, _schema())

    assert any("scalar_confidence_projection_allowed" in error for error in errors)
    assert any("scalar_confidence_is_canonical" in error for error in errors)
    assert not any("truth_kernel_auto_promotion" in error for error in errors)


def test_epistemic_claim_type_sequence_drift_is_rejected() -> None:
    profile = _profile()
    profile["epistemic_contract"]["epistemic_claim_types"].reverse()
    errors = validate_research_epistemics_profile_record(profile, _schema())

    assert any("epistemic_claim_types must match the canonical sequence" in error for error in errors)
    assert not any("$.epistemic_contract.epistemic_claim_types" in error for error in errors)
    assert "EMPIRICAL" in profile["epistemic_contract"]["epistemic_claim_types"]


def test_disposition_sequence_drift_is_rejected() -> None:
    profile = _profile()
    profile["epistemic_contract"]["dispositions"].remove("ABSTENTION")
    errors = validate_research_epistemics_profile_record(profile, _schema())

    assert any("dispositions must match the canonical sequence" in error for error in errors)
    assert any("$.epistemic_contract.dispositions" in error for error in errors)
    assert len(profile["epistemic_contract"]["dispositions"]) == 7


def test_ready_now_record_fields_are_enforced() -> None:
    profile = build_mutated_research_epistemics_profile(
        epistemic_contract__abstention_record_fields__0="claim_ref",
        epistemic_contract__source_lineage_record_fields__0="source_ref",
        epistemic_contract__contradiction_record_fields__0="conflict_id",
    )
    errors = validate_research_epistemics_profile_record(profile, _schema())

    assert any("abstention_record_fields" in error for error in errors)
    assert any("source_lineage_record_fields" in error for error in errors)
    assert any("contradiction_record_fields" in error for error in errors)


def test_source_lineage_independence_rule_is_enforced() -> None:
    profile = build_mutated_research_epistemics_profile(
        epistemic_contract__source_identity_independence_rule=(
            "distinct_source_ids_are_independent"
        )
    )
    errors = validate_research_epistemics_profile_record(profile, _schema())

    assert any("source_identity_independence_rule" in error for error in errors)
    assert any("$.epistemic_contract.source_identity_independence_rule" in error for error in errors)
    assert not any("source_lineage_record_fields" in error for error in errors)


def test_contradiction_classes_and_failed_experiment_rule_are_enforced() -> None:
    profile = _profile()
    profile["epistemic_contract"]["contradiction_classes"][0] = "FAILED_EXPERIMENT"
    profile["epistemic_contract"]["failed_experiment_is_factual_contradiction"] = True
    errors = validate_research_epistemics_profile_record(profile, _schema())

    assert any("contradiction_classes must match the canonical sequence" in error for error in errors)
    assert any("failed_experiment_is_factual_contradiction" in error for error in errors)
    assert any("$.epistemic_contract.contradiction_classes[0]" in error for error in errors)


def test_truth_kernel_auto_promotion_is_denied() -> None:
    profile = build_mutated_research_epistemics_profile(
        epistemic_contract__truth_kernel_auto_promotion=True
    )
    errors = validate_research_epistemics_profile_record(profile, _schema())

    assert any("truth_kernel_auto_promotion" in error for error in errors)
    assert any("$.epistemic_contract.truth_kernel_auto_promotion" in error for error in errors)
    assert not any("scalar_confidence_is_canonical" in error for error in errors)


def test_compatibility_drift_is_rejected() -> None:
    profile = build_mutated_research_epistemics_profile(
        compatibility__research_runtime_ref="parallel/research_engine.py"
    )
    errors = validate_research_epistemics_profile_record(profile, _schema())

    assert any("compatibility refs" in error for error in errors)
    assert not any("$.compatibility.research_runtime_ref" in error for error in errors)
    assert not any("canonical_names" in error for error in errors)


def test_runtime_contract_gate_remains_closed() -> None:
    profile = build_mutated_research_epistemics_profile(
        next_gate__runtime_contracts_allowed=True
    )
    errors = validate_research_epistemics_profile_record(profile, _schema())

    assert any("CDG-RCCM" in error for error in errors)
    assert any("$.next_gate.runtime_contracts_allowed" in error for error in errors)
    assert not any("operator_review_required" in error for error in errors)


def test_required_evidence_ref_is_enforced() -> None:
    profile = deepcopy(_profile())
    profile["evidence_refs"].remove("docs/RESEARCH_EPISTEMICS_PROFILE_V1.md")
    errors = validate_research_epistemics_profile_record(profile, _schema())

    assert any("docs/RESEARCH_EPISTEMICS_PROFILE_V1.md" in error for error in errors)
    assert any("evidence_refs missing required ref" in error for error in errors)
    assert "docs/WRE_A2_RESEARCH_EPISTEMICS_PROFILE.md" not in profile["evidence_refs"]


def test_unknown_top_level_field_is_rejected_by_schema() -> None:
    profile = _profile()
    profile["unexpected"] = True
    errors = validate_research_epistemics_profile_record(profile, _schema())

    assert errors
    assert any("unexpected" in error for error in errors)
    assert not any("profile_version" in error for error in errors)
