"""Purpose: verify WorldSubstrateReplayWitness validation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_world_substrate_replay_witness and SDLC validator.
Invariants:
  - SWEWS-style world evidence remains witness-only.
  - Foundation Mode grants no live service calls, SQLite access, world mutation,
    replay, planner/executor execution, external endpoint, write, terminal, or
    success authority.
  - Raw world snapshots and raw replay traces are not stored.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_sdlc_artifact as sdlc_validator
from scripts import validate_world_substrate_replay_witness as validator


def test_world_substrate_replay_witness_passes() -> None:
    errors = validator.validate_world_substrate_replay_witness()
    witness = validator.load_json_object(validator.DEFAULT_WITNESS_PATH, "WorldSubstrateReplayWitness")

    assert errors == []
    assert witness["witness_version"] == validator.EXPECTED_WITNESS_VERSION
    assert witness["replay_scope"]["source_family"] == "external/swews-core"
    assert witness["replay_scope"]["borrowed_concept"] == "world-substrate-replay-witness"
    assert witness["replay_scope"]["tenant_scope"] == "foundation-local-only"
    assert witness["authority_boundary"]["live_world_service_call_performed"] is False
    assert witness["authority_boundary"]["world_mutation_performed"] is False
    assert witness["authority_boundary"]["replay_execution_performed"] is False
    assert witness["safety_guards"]["sparse_cache_truth_required"] is True
    assert witness["safety_guards"]["raw_world_snapshot_retained"] is False
    assert validator.validate_world_substrate_replay_witness_record(witness) == []


def test_world_substrate_replay_witness_rejects_authority_drift() -> None:
    mutated = validator.build_mutated_world_substrate_replay_witness(
        authority_boundary__live_world_service_call_performed=True,
        authority_boundary__sqlite_read_performed=True,
        authority_boundary__sqlite_write_performed=True,
        authority_boundary__world_mutation_performed=True,
        authority_boundary__replay_execution_performed=True,
        authority_boundary__planner_execution_performed=True,
        authority_boundary__executor_execution_performed=True,
        authority_boundary__branch_unquarantined=True,
        authority_boundary__external_endpoint_called=True,
        authority_boundary__filesystem_write_performed=True,
        authority_boundary__terminal_closure_allowed=True,
        authority_boundary__success_claim_allowed=True,
    )

    errors = validator.validate_world_substrate_replay_witness_record(mutated)

    assert any("authority_boundary.live_world_service_call_performed" in error for error in errors)
    assert any("authority_boundary.sqlite_read_performed" in error for error in errors)
    assert any("authority_boundary.sqlite_write_performed" in error for error in errors)
    assert any("authority_boundary.world_mutation_performed" in error for error in errors)
    assert any("authority_boundary.replay_execution_performed" in error for error in errors)
    assert any("authority_boundary.planner_execution_performed" in error for error in errors)
    assert any("authority_boundary.executor_execution_performed" in error for error in errors)
    assert any("authority_boundary.terminal_closure_allowed" in error for error in errors)


def test_world_substrate_replay_witness_rejects_raw_payload_retention() -> None:
    mutated = validator.build_mutated_world_substrate_replay_witness(
        authority_boundary__raw_world_snapshot_stored=True,
        authority_boundary__raw_replay_trace_stored=True,
        authority_boundary__secret_access_performed=True,
        safety_guards__raw_world_snapshot_retained=True,
        safety_guards__raw_replay_trace_retained=True,
        safety_guards__operator_review_required=False,
        safety_guards__incident_handoff_required_if_live=False,
    )

    errors = validator.validate_world_substrate_replay_witness_record(mutated)

    assert any("authority_boundary.raw_world_snapshot_stored" in error for error in errors)
    assert any("authority_boundary.raw_replay_trace_stored" in error for error in errors)
    assert any("authority_boundary.secret_access_performed" in error for error in errors)
    assert any("safety_guards.raw_world_snapshot_retained" in error for error in errors)
    assert any("safety_guards.raw_replay_trace_retained" in error for error in errors)
    assert any("operator_review_required" in error for error in errors)
    assert any("incident_handoff_required_if_live" in error for error in errors)


def test_world_substrate_replay_witness_rejects_digest_and_scope_drift() -> None:
    mutated = validator.build_mutated_world_substrate_replay_witness(
        replay_artifacts__world_snapshot_digest_ref="https://example.com/world.json",
        replay_artifacts__replay_trace_digest_ref="file://trace.json",
        replay_artifacts__sparse_cache_digest_ref="sparse://cache",
        planner_executor_parity__planner_trace_ref="planner://raw",
        planner_executor_parity__executor_trace_ref="executor://raw",
        replay_scope__source_family="external/other",
        replay_scope__borrowed_concept="other-witness",
        replay_scope__foundation_mode=False,
        replay_scope__tenant_scope="public",
        replay_scope__world_substrate_mode="witness_only_digest_replay",
        replay_scope__life_meaning_judgment_ref="schemas/other.schema.json",
    )

    errors = validator.validate_world_substrate_replay_witness_record(mutated)

    assert any("world_snapshot_digest_ref must use hash://sha256/" in error for error in errors)
    assert any("world_snapshot_digest_ref must not store raw world URL" in error for error in errors)
    assert any("replay_trace_digest_ref must use hash://sha256/" in error for error in errors)
    assert any("sparse_cache_digest_ref must use hash://sha256/" in error for error in errors)
    assert any("planner_trace_ref must use hash://sha256/" in error for error in errors)
    assert any("executor_trace_ref must use hash://sha256/" in error for error in errors)
    assert any("source_family" in error for error in errors)
    assert any("world_substrate_mode" in error for error in errors)


def test_world_substrate_replay_witness_rejects_invariant_control_gaps() -> None:
    mutated = validator.build_mutated_world_substrate_replay_witness(
        invariant_controls__invariant_refs=[],
        invariant_controls__sparse_cache_truth_refs=[],
        invariant_controls__legal_geometry_refs=[],
        invariant_controls__field_derivation_refs=[],
        invariant_controls__branch_quarantine_refs=[],
        invariant_controls__replay_probe_refs=["proof://swews/runtime-replay-probe/digest-only", "proof://swews/runtime-replay-probe/digest-only"],
        safety_guards__sparse_cache_truth_required=False,
        safety_guards__legal_geometry_required=False,
        safety_guards__invariant_registry_required=False,
        safety_guards__branch_quarantine_required=False,
    )

    errors = validator.validate_world_substrate_replay_witness_record(mutated)

    assert any("invariant_controls.invariant_refs" in error for error in errors)
    assert any("invariant_controls.sparse_cache_truth_refs" in error for error in errors)
    assert any("invariant_controls.legal_geometry_refs" in error for error in errors)
    assert any("invariant_controls.field_derivation_refs" in error for error in errors)
    assert any("invariant_controls.branch_quarantine_refs" in error for error in errors)
    assert any("invariant_controls.replay_probe_refs must not contain duplicates" in error for error in errors)
    assert any("safety_guards.sparse_cache_truth_required" in error for error in errors)
    assert any("safety_guards.branch_quarantine_required" in error for error in errors)


def test_world_substrate_replay_witness_rejects_parity_drift() -> None:
    mutated = validator.build_mutated_world_substrate_replay_witness(
        planner_executor_parity__parity_verified=False,
        planner_executor_parity__divergence_count=2,
        planner_executor_parity__planner_executor_mismatch_count=1,
        safety_guards__planner_executor_parity_required=False,
        replay_artifacts__branch_quarantine_digest_ref="branch://unquarantined",
    )

    errors = validator.validate_world_substrate_replay_witness_record(mutated)

    assert any("planner_executor_parity.parity_verified" in error for error in errors)
    assert any("planner_executor_parity.divergence_count" in error for error in errors)
    assert any("planner_executor_parity.planner_executor_mismatch_count" in error for error in errors)
    assert any("safety_guards.planner_executor_parity_required" in error for error in errors)
    assert any("branch_quarantine_digest_ref must use hash://sha256/" in error for error in errors)


def test_world_substrate_replay_witness_rejects_receipt_ref_and_count_drift() -> None:
    mutated = validator.build_mutated_world_substrate_replay_witness(
        receipt_refs__world_substrate_replay_witness_schema="schemas/other.schema.json",
        receipt_refs__world_state_schema="schemas/other_world_state.schema.json",
        receipt_refs__simulation_receipt_schema="schemas/other_simulation.schema.json",
        contract_summary__witness_only=False,
        contract_summary__world_mutation_denied=False,
        contract_summary__replay_execution_denied=False,
        contract_summary__authority_denial_count=1,
        contract_summary__receipt_ref_count=1,
        contract_summary__evidence_ref_count=1,
        evidence_refs=["schemas/world_substrate_replay_witness.schema.json"],
    )

    errors = validator.validate_world_substrate_replay_witness_record(mutated)

    assert any("receipt_refs.world_substrate_replay_witness_schema" in error for error in errors)
    assert any("receipt_refs.world_state_schema" in error for error in errors)
    assert any("receipt_refs.simulation_receipt_schema" in error for error in errors)
    assert any("contract_summary.witness_only" in error for error in errors)
    assert any("contract_summary.world_mutation_denied" in error for error in errors)
    assert any("contract_summary.replay_execution_denied" in error for error in errors)
    assert any("contract_summary.authority_denial_count" in error for error in errors)
    assert any("evidence_refs missing required ref" in error for error in errors)


def test_cli_json_accepts_relative_paths(capsys) -> None:
    exit_code = validator.main(
        [
            "--schema",
            "schemas/world_substrate_replay_witness.schema.json",
            "--witness",
            "examples/world_substrate_replay_witness.foundation.json",
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "passed"
    assert Path(payload["schema_path"]).as_posix() == "schemas/world_substrate_replay_witness.schema.json"
    assert Path(payload["witness_path"]).as_posix() == "examples/world_substrate_replay_witness.foundation.json"
    assert payload["errors"] == []


def test_malformed_world_substrate_replay_witness_reports_errors() -> None:
    schema = validator._load_schema(validator.DEFAULT_SCHEMA_PATH)

    none_errors = validator.validate_world_substrate_replay_witness_record(None, schema)
    list_errors = validator.validate_world_substrate_replay_witness_record([], schema)

    assert any("world substrate replay witness must be a JSON object" in error for error in none_errors)
    assert any("world substrate replay witness must be a JSON object" in error for error in list_errors)
    assert any("expected object" in error for error in none_errors + list_errors)


def test_sdlc_requirement_and_design_validate_for_world_substrate_replay_witness() -> None:
    requirement_path = Path("examples/sdlc/requirement_world_substrate_replay_witness_20260617.json")
    design_path = Path("examples/sdlc/design_world_substrate_replay_witness_20260617.json")
    requirement = sdlc_validator.load_json_object(requirement_path, "world substrate replay witness requirement")
    design = sdlc_validator.load_json_object(design_path, "world substrate replay witness design")

    requirement_errors = sdlc_validator.validate_artifact_record("requirement", requirement)
    design_errors = sdlc_validator.validate_artifact_record("design_decision", design)

    assert requirement_errors == []
    assert design_errors == []
    assert design["requirement_id"] == requirement["requirement_id"]
    assert "schemas/world_substrate_replay_witness.schema.json" in requirement["affected_surfaces"]
    assert "schemas/world_substrate_replay_witness.schema.json" in design["schema_changes"]
    assert "scripts/validate_world_substrate_replay_witness.py" in design["validator_changes"]
    assert "tests/test_validate_world_substrate_replay_witness.py" in design["validator_changes"]
    assert "no live world service call" in requirement["non_goals"]
    assert design["security_model"]["effect_bearing_requires_receipt"] is True
