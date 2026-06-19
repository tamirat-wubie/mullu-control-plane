"""Verify GovernedPlanningProfile validation and fail-closed boundaries.

Governance: OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS. The profile remains
reference-only, non-executable, deterministic, read-only, and Mfidel-safe.
"""
from __future__ import annotations

from copy import deepcopy
import json
import subprocess
import sys
from pathlib import Path

from scripts import validate_sdlc_artifact as sdlc_validator
from scripts.validate_governed_planning_profile import (
    DEFAULT_PROFILE_PATH,
    DEFAULT_SCHEMA_PATH,
    load_json_object,
    validate_governed_planning_profile,
    validate_governed_planning_profile_record,
)
from scripts.validate_schemas import _load_schema


def _profile() -> dict:
    return deepcopy(load_json_object(DEFAULT_PROFILE_PATH, "governed planning profile"))


def test_governed_planning_profile_fixture_passes() -> None:
    assert validate_governed_planning_profile() == []
    assert DEFAULT_SCHEMA_PATH.exists()
    assert DEFAULT_PROFILE_PATH.exists()


def test_governed_planning_profile_rejects_authority_drift() -> None:
    schema = _load_schema(DEFAULT_SCHEMA_PATH)
    profile = _profile()
    profile["profile_scope"].update(
        planner_replacement_claimed=True,
        execution_authority_granted=True,
        dispatch_allowed=True,
        terminal_closure_allowed=True,
    )
    errors = validate_governed_planning_profile_record(profile, schema)
    assert "profile_scope.planner_replacement_claimed must be false" in errors
    assert "profile_scope.execution_authority_granted must be false" in errors
    assert "profile_scope.dispatch_allowed must be false" in errors
    assert "profile_scope.terminal_closure_allowed must be false" in errors


def test_governed_planning_profile_rejects_source_binding_drift() -> None:
    schema = _load_schema(DEFAULT_SCHEMA_PATH)
    profile = _profile()
    profile["source_bindings"][0]["source_ref"] = "docs/missing-planner.md"
    profile["source_bindings"][1]["binding_id"] = profile["source_bindings"][0]["binding_id"]
    profile["source_bindings"][2]["execution_allowed"] = True
    errors = validate_governed_planning_profile_record(profile, schema)
    assert "source_bindings.problem_star_compilation source or role is invalid" in errors
    assert "source_bindings binding_id values must be unique" in errors
    assert "source_bindings[2] must remain reference-only and non-executable" in errors
    assert any("references missing repository file" in error for error in errors)


def test_governed_planning_profile_requires_authority_refs_and_count_parity() -> None:
    schema = _load_schema(DEFAULT_SCHEMA_PATH)
    profile = _profile()
    profile["planning_contract"]["authority_refs"] = ["AGENTS.md#phi-traversal-spine"]
    profile["planning_contract"]["selected_plan_ref"] = "plan://selected"
    profile["profile_summary"]["planning_reference_count"] = 0
    errors = validate_governed_planning_profile_record(profile, schema)
    assert "planning_contract.authority_refs missing UAO or Phi_gov reference" in errors
    assert "planning_contract.selected_plan_ref must remain awaiting" in errors
    assert "profile_summary.planning_reference_count must match observed count" in errors


def test_governed_planning_profile_rejects_adaptation_drift() -> None:
    schema = _load_schema(DEFAULT_SCHEMA_PATH)
    profile = _profile()
    profile["adaptation_policy"].update(
        live_replanning_enabled=True,
        automatic_goal_rewrite_allowed=True,
        goal_rewrite_requires_phi_gov=False,
        exit_threshold_ref="policy://replanning/deviation-enter-threshold",
    )
    errors = validate_governed_planning_profile_record(profile, schema)
    assert "adaptation_policy.live_replanning_enabled must be false" in errors
    assert "adaptation_policy.automatic_goal_rewrite_allowed must be false" in errors
    assert "adaptation_policy.goal_rewrite_requires_phi_gov must be true" in errors
    assert "adaptation_policy enter and exit threshold refs must differ" in errors


def test_governed_planning_profile_rejects_summary_drift() -> None:
    schema = _load_schema(DEFAULT_SCHEMA_PATH)
    profile = _profile()
    profile["profile_summary"].update(
        source_binding_count=0,
        scope_denied_guard_count=0,
        adaptation_denied_guard_count=0,
    )
    errors = validate_governed_planning_profile_record(profile, schema)
    assert "profile_summary.source_binding_count must match observed count" in errors
    assert "profile_summary.scope_denied_guard_count must match observed count" in errors
    assert "profile_summary.adaptation_denied_guard_count must match observed count" in errors


def test_governed_planning_profile_cli_json_paths_are_workspace_relative() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_governed_planning_profile.py", "--json"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    assert payload["status"] == "passed"
    assert payload["schema_path"] in {
        "schemas\\governed_planning_profile.schema.json",
        "schemas/governed_planning_profile.schema.json",
    }
    assert payload["errors"] == []


def test_governed_planning_profile_rejects_malformed_payload() -> None:
    schema = _load_schema(DEFAULT_SCHEMA_PATH)
    errors = validate_governed_planning_profile_record([], schema)
    assert "GovernedPlanningProfile must be object" in errors
    assert len(errors) >= 1
    assert schema["$id"] == "urn:mullusi:schema:governed-planning-profile:1"


def test_governed_planning_profile_sdlc_artifacts_validate() -> None:
    requirement_path = Path("examples/sdlc/requirement_governed_planning_profile_20260619.json")
    design_path = Path("examples/sdlc/design_governed_planning_profile_20260619.json")
    requirement = sdlc_validator.load_json_object(requirement_path, "planning profile requirement")
    design = sdlc_validator.load_json_object(design_path, "planning profile design")
    assert sdlc_validator.validate_artifact_record("requirement", requirement) == []
    assert sdlc_validator.validate_artifact_record("design_decision", design) == []
    assert design["requirement_id"] == requirement["requirement_id"]
    assert DEFAULT_PROFILE_PATH.name == "governed_planning_profile.foundation.json"
