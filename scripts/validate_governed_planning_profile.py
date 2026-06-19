#!/usr/bin/env python3
"""Validate the reference-only GovernedPlanningProfile Foundation contract.

Purpose: bind existing Mullu planning lineages without registering a planner or
changing execution authority. Governance: OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS.
The validator is deterministic, read-only, fail-closed, and Mfidel-safe.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402

DEFAULT_SCHEMA_PATH = ROOT / "schemas/governed_planning_profile.schema.json"
DEFAULT_PROFILE_PATH = ROOT / "examples/governed_planning_profile.foundation.json"
TRUE_SCOPE = ("read_only", "foundation_profile_only", "planning_projection_defined", "existing_lineages_preserved", "mfidel_atomicity_preserved")
FALSE_SCOPE = ("runtime_registration_claimed", "planner_replacement_claimed", "parallel_execution_spine_allowed", "execution_authority_granted", "dispatch_allowed", "connector_authority_granted", "filesystem_write_allowed", "external_network_allowed", "memory_write_allowed", "system_of_record_migration_allowed", "runtime_replanning_allowed", "terminal_closure_allowed", "success_claim_allowed")
TRUE_ADAPT = ("local_repair_first", "hysteresis_required", "cooldown_required", "change_budget_required", "goal_rewrite_requires_phi_gov", "policy_rewrite_requires_phi_gov", "authority_expansion_requires_phi_gov")
FALSE_ADAPT = ("live_replanning_enabled", "automatic_goal_rewrite_allowed", "automatic_policy_rewrite_allowed", "automatic_authority_expansion_allowed")
REPAIR_ORDER = ("observe", "retry_safely", "adjust_parameters", "reallocate_resources", "activate_contingency", "repair_local_branch", "replan_phase", "replan_mission", "suspend_or_terminate")
PLAN_LISTS = ("goal_refs", "constraint_refs", "evidence_refs", "assumption_refs", "unknown_refs", "contradiction_refs", "candidate_plan_refs", "risk_refs", "budget_refs", "authority_refs", "approval_refs", "rollback_refs", "compensation_refs", "safe_stop_refs", "closure_condition_refs", "learning_refs")
BINDINGS = (
    ("problem_star_compilation", "docs/75_problem_star_compilation_receipt.md", "problem_compilation"),
    ("phi_gps_solver", "mcoi/mcoi_runtime/core/phi_gps.py", "solver_profile"),
    ("goal_plan_compilation", "gateway/goal_compiler.py", "planning_simulation_compiler"),
    ("causal_simulation", "gateway/causal_simulator.py", "causal_simulation"),
    ("capability_plan_contract", "gateway/plan.py", "capability_plan"),
    ("bounded_plan_execution", "gateway/plan_executor.py", "bounded_plan_execution"),
    ("plan_closure_recovery", "gateway/plan_ledger.py", "plan_closure_recovery"),
    ("organization_case_governance", "mcoi/mcoi_runtime/core/organization_kernel.py", "organization_case_governance"),
    ("whqr_mil_execution", "mcoi/mcoi_runtime/core/whqr_mil_orchestrator.py", "live_execution_spine"),
    ("holistic_governed_loop", "mcoi/mcoi_runtime/contracts/holistic_loop.py", "governed_control_loop"),
    ("universal_action_orchestration", "docs/UNIVERSAL_ACTION_ORCHESTRATION.md", "effect_governance"),
    ("closure_learning_admission", "docs/38_closure_learning_admission.md", "learning_admission"),
)


def load_json_object(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"missing {label}: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _check_flags(value: Any, yes: tuple[str, ...], no: tuple[str, ...], label: str, errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append(f"{label} must be an object")
        return
    errors.extend(f"{label}.{name} must be true" for name in yes if value.get(name) is not True)
    errors.extend(f"{label}.{name} must be false" for name in no if value.get(name) is not False)


def _check_ref(ref: Any, label: str, errors: list[str]) -> None:
    if not isinstance(ref, str) or not ref:
        errors.append(f"{label} must be a non-empty string")
        return
    if "://" not in ref and not (ROOT / ref.split("#", 1)[0]).is_file():
        errors.append(f"{label} references missing repository file: {ref.split('#', 1)[0]}")


def _plan_count(plan: Any) -> int:
    if not isinstance(plan, dict):
        return 0
    return sum(len(plan.get(name, ())) for name in PLAN_LISTS if isinstance(plan.get(name), list)) + sum(bool(plan.get(name)) for name in ("selected_plan_ref", "plan_dag_ref"))


def validate_governed_planning_profile_record(record: Any, schema: dict[str, Any] | None = None) -> list[str]:
    schema = schema or _load_schema(DEFAULT_SCHEMA_PATH)
    errors: list[str] = []
    if schema.get("$id") != "urn:mullusi:schema:governed-planning-profile:1":
        errors.append("schema $id is invalid")
    if not isinstance(record, dict):
        return errors + ["GovernedPlanningProfile must be object"]
    errors.extend(_validate_schema_instance(schema, record))
    if record.get("profile_version") != "governed_planning_profile.v1":
        errors.append("profile_version is invalid")
    if record.get("status") != "AwaitingEvidence" or record.get("solver_outcome") != "AwaitingEvidence":
        errors.append("status and solver_outcome must remain AwaitingEvidence")
    _check_flags(record.get("profile_scope"), TRUE_SCOPE, FALSE_SCOPE, "profile_scope", errors)

    raw = record.get("source_bindings")
    raw = raw if isinstance(raw, list) else []
    by_id = {item.get("binding_id"): item for item in raw if isinstance(item, dict)}
    ids = [item.get("binding_id") for item in raw if isinstance(item, dict)]
    refs = [item.get("source_ref") for item in raw if isinstance(item, dict)]
    if len(ids) != len(set(ids)):
        errors.append("source_bindings binding_id values must be unique")
    if len(refs) != len(set(refs)):
        errors.append("source_bindings source_ref values must be unique")
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            errors.append(f"source_bindings[{index}] must be an object")
            continue
        _check_ref(item.get("source_ref"), f"source_bindings[{index}].source_ref", errors)
        if (item.get("binding_mode"), item.get("authority_effect"), item.get("read_only"), item.get("execution_allowed")) != ("reference_only", "none", True, False):
            errors.append(f"source_bindings[{index}] must remain reference-only and non-executable")
    for binding_id, source_ref, role in BINDINGS:
        item = by_id.get(binding_id)
        if item is None:
            errors.append(f"source_bindings missing required binding: {binding_id}")
        elif (item.get("source_ref"), item.get("target_role")) != (source_ref, role):
            errors.append(f"source_bindings.{binding_id} source or role is invalid")

    plan = record.get("planning_contract")
    if not isinstance(plan, dict):
        errors.append("planning_contract must be an object")
    else:
        for name in PLAN_LISTS:
            values = plan.get(name)
            if not isinstance(values, list) or not values:
                errors.append(f"planning_contract.{name} must be a non-empty list")
            else:
                for index, ref in enumerate(values):
                    _check_ref(ref, f"planning_contract.{name}[{index}]", errors)
        if plan.get("selected_plan_ref") != "awaiting://governed-planning-profile/selected-plan":
            errors.append("planning_contract.selected_plan_ref must remain awaiting")
        if plan.get("plan_dag_ref") != "gateway/goal_compiler.py#PlanDAG":
            errors.append("planning_contract.plan_dag_ref is invalid")
        _check_ref(plan.get("plan_dag_ref"), "planning_contract.plan_dag_ref", errors)
        needed = {"AGENTS.md#universal-action-orchestration", "AGENTS.md#phi-traversal-spine"}
        if not needed.issubset(set(plan.get("authority_refs", ()))):
            errors.append("planning_contract.authority_refs missing UAO or Phi_gov reference")

    adaptation = record.get("adaptation_policy")
    _check_flags(adaptation, TRUE_ADAPT, FALSE_ADAPT, "adaptation_policy", errors)
    if isinstance(adaptation, dict):
        if tuple(adaptation.get("repair_order", ())) != REPAIR_ORDER:
            errors.append("adaptation_policy.repair_order is invalid")
        if adaptation.get("enter_threshold_ref") == adaptation.get("exit_threshold_ref"):
            errors.append("adaptation_policy enter and exit threshold refs must differ")

    for name in ("validation_refs", "governance_refs", "evidence_refs"):
        values = record.get(name)
        if isinstance(values, list):
            for index, ref in enumerate(values):
                _check_ref(ref, f"{name}[{index}]", errors)

    summary = record.get("profile_summary")
    expected = {
        "source_binding_count": len(raw), "planning_reference_count": _plan_count(plan),
        "repair_stage_count": len(adaptation.get("repair_order", ())) if isinstance(adaptation, dict) else 0,
        "validation_ref_count": len(record.get("validation_refs", ())),
        "governance_ref_count": len(record.get("governance_refs", ())),
        "evidence_ref_count": len(record.get("evidence_refs", ())),
        "scope_true_guard_count": len(TRUE_SCOPE), "scope_denied_guard_count": len(FALSE_SCOPE),
        "adaptation_true_guard_count": len(TRUE_ADAPT), "adaptation_denied_guard_count": len(FALSE_ADAPT),
    }
    if not isinstance(summary, dict):
        errors.append("profile_summary must be an object")
    else:
        errors.extend(f"profile_summary.{name} must match observed count" for name, value in expected.items() if summary.get(name) != value)

    envelope = record.get("receipt_envelope")
    prefixes = (("uao_ref", "uao://governed-planning-profile/"), ("causal_decision_trace_ref", "trace://governed-planning-profile/"), ("receipt_ref", "receipt://governed-planning-profile/"))
    if not isinstance(envelope, dict):
        errors.append("receipt_envelope must be an object")
    else:
        errors.extend(f"receipt_envelope.{name} is invalid" for name, prefix in prefixes if not isinstance(envelope.get(name), str) or not envelope[name].startswith(prefix))
    return sorted(set(errors))


def validate_governed_planning_profile(*, schema_path: Path = DEFAULT_SCHEMA_PATH, profile_path: Path = DEFAULT_PROFILE_PATH) -> list[str]:
    return validate_governed_planning_profile_record(load_json_object(profile_path, "governed planning profile"), _load_schema(schema_path))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE_PATH)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()
    try:
        errors = validate_governed_planning_profile(schema_path=args.schema, profile_path=args.profile)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors = [str(exc)]
    relative = lambda path: str(path.resolve().relative_to(ROOT.resolve())) if path.resolve().is_relative_to(ROOT.resolve()) else str(path)
    payload = {"status": "passed" if not errors else "failed", "schema_path": relative(args.schema), "profile_path": relative(args.profile), "errors": errors}
    if args.as_json:
        print(json.dumps(payload, sort_keys=True))
    elif errors:
        print("GovernedPlanningProfile validation failed:")
        print("\n".join(f"- {error}" for error in errors))
    else:
        print("GovernedPlanningProfile validation passed")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
