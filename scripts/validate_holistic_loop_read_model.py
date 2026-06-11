#!/usr/bin/env python3
"""Validate holistic loop read-model report contract.

Purpose: verify that the holistic loop report has a stable machine-readable
shape and blocker/status consistency.
Governance scope: schema artifact, current read-model output, blocker
derivation, non-terminal closure boundary, and bounded count fields.
Dependencies: Python standard library and scripts/report_holistic_loop_read_model.py.
Invariants:
  - Validation is read-only and deterministic.
  - Report status derives from loop blockers.
  - Missing evidence must appear as blockers before closure can be claimed.
  - The report is not a terminal closure certificate.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    from report_holistic_loop_read_model import build_report
except ModuleNotFoundError:  # pragma: no cover - exercised when imported as a package.
    from scripts.report_holistic_loop_read_model import build_report


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA_PATH = WORKSPACE_ROOT / "schemas" / "holistic_loop_read_model.schema.json"
REQUIRED_REPORT_FIELDS = (
    "report_id",
    "status",
    "generated_at",
    "loop_count",
    "returned_count",
    "blocked_count",
    "verified_count",
    "truncated",
    "report_is_not_terminal_closure",
    "terminal_closure_required",
    "loops",
)
REQUIRED_LOOP_FIELDS = (
    "loop_id",
    "name",
    "purpose",
    "owner",
    "risk_class",
    "risk_binding",
    "status",
    "status_binding",
    "transition_bindings",
    "mode",
    "mode_binding",
    "current_step",
    "required_authority",
    "authority_bindings",
    "authority_refs",
    "missing_authority",
    "required_evidence",
    "evidence_bindings",
    "step_receipts",
    "receipt_lineage_bindings",
    "evidence_refs",
    "missing_evidence",
    "closure_conditions",
    "closure_condition_bindings",
    "closure_report",
    "closure_evidence_pack",
    "operator_closure_readiness_view",
    "proof_obligation_view",
    "audit_evolution_view",
    "open_blockers",
    "rollback_policy",
    "rollback_binding",
    "learning_policy",
    "learning_binding",
    "updated_at",
)
REPORT_STATUSES = ("blocked", "verified")
LOOP_STATUSES = ("open", "blocked", "verified", "closed")
LOOP_MODES = ("real", "dry_run", "shadow", "simulation", "replay")
LOOP_STEPS = (
    "observe",
    "decide",
    "act",
    "verify",
    "record_receipt",
    "update_state",
    "learn",
    "audit",
    "close",
)


class HolisticLoopReadModelContractError(ValueError):
    """Raised when the holistic loop read-model contract is invalid."""


def load_json_object(json_path: Path, label: str) -> dict[str, Any]:
    """Load one JSON object with explicit artifact identity."""

    if not json_path.exists():
        raise FileNotFoundError(f"missing {label}: {json_path}")
    if not json_path.is_file():
        raise IsADirectoryError(f"{label} path is not a file: {json_path}")
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise HolisticLoopReadModelContractError(f"{label} must be a JSON object")
    return payload


def validate_schema_artifact(schema: dict[str, Any]) -> list[str]:
    """Return deterministic schema validation errors."""

    errors: list[str] = []
    if schema.get("title") != "Holistic Loop Read Model":
        errors.append("schema title does not identify holistic loop read model")
    if schema.get("type") != "object":
        errors.append("schema root type must be object")
    required_fields = schema.get("required")
    if not isinstance(required_fields, list):
        errors.append("schema required field must be a list")
    else:
        for field_name in REQUIRED_REPORT_FIELDS:
            if field_name not in required_fields:
                errors.append(f"schema missing required report field: {field_name}")
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        errors.append("schema properties must be an object")
    else:
        for field_name in REQUIRED_REPORT_FIELDS:
            if field_name not in properties:
                errors.append(f"schema missing report property: {field_name}")
    loop_required = schema.get("$defs", {}).get("loop_summary", {}).get("required", [])
    if not isinstance(loop_required, list):
        errors.append("schema loop_summary.required must be a list")
    else:
        for field_name in REQUIRED_LOOP_FIELDS:
            if field_name not in loop_required:
                errors.append(f"schema missing required loop field: {field_name}")
    return errors


def validate_report(report: dict[str, Any]) -> list[str]:
    """Return deterministic validation errors for one loop read-model report."""

    errors: list[str] = []
    missing_fields = [field_name for field_name in REQUIRED_REPORT_FIELDS if field_name not in report]
    errors.extend(f"report missing field: {field_name}" for field_name in missing_fields)
    extra_fields = sorted(set(report) - set(REQUIRED_REPORT_FIELDS))
    errors.extend(f"report has unexpected field: {field_name}" for field_name in extra_fields)
    if missing_fields:
        return errors

    if report["report_id"] != "holistic_loop_read_model":
        errors.append("report_id is invalid")
    if report["status"] not in REPORT_STATUSES:
        errors.append(f"report status is invalid: {report['status']}")
    if report["report_is_not_terminal_closure"] is not True:
        errors.append("report_is_not_terminal_closure must be true")
    if report["terminal_closure_required"] is not True:
        errors.append("terminal_closure_required must be true")
    for field_name in ("loop_count", "returned_count", "blocked_count", "verified_count"):
        if isinstance(report[field_name], bool) or not isinstance(report[field_name], int):
            errors.append(f"{field_name} must be an integer")
        elif report[field_name] < 0:
            errors.append(f"{field_name} must be non-negative")
    if not isinstance(report["truncated"], bool):
        errors.append("truncated must be boolean")

    loops = report["loops"]
    if not isinstance(loops, list):
        errors.append("loops must be a list")
        return errors
    errors.extend(_validate_report_counts(report, loops))
    for index, loop in enumerate(loops):
        errors.extend(_validate_loop_summary(loop, index))
    return errors


def validate_contract(schema_path: Path = DEFAULT_SCHEMA_PATH) -> list[str]:
    """Validate schema and current reporter output."""

    schema = load_json_object(schema_path, "holistic loop read-model schema")
    current_report = build_report()
    errors = validate_schema_artifact(schema)
    errors.extend(f"current report: {error}" for error in validate_report(current_report))
    return errors


def _validate_report_counts(report: dict[str, Any], loops: list[Any]) -> list[str]:
    errors: list[str] = []
    loop_count = len(loops)
    blocked_count = sum(
        1 for loop in loops if isinstance(loop, dict) and bool(loop.get("open_blockers"))
    )
    verified_count = sum(
        1 for loop in loops if isinstance(loop, dict) and loop.get("status") == "verified"
    )
    expected_status = "blocked" if blocked_count else "verified"
    if report.get("returned_count") != loop_count:
        errors.append("returned_count does not match loop summaries length")
    if report.get("loop_count") < report.get("returned_count", 0):
        errors.append("loop_count cannot be lower than returned_count")
    if report.get("blocked_count") != blocked_count:
        errors.append("blocked_count does not match loop blockers")
    if report.get("verified_count") != verified_count:
        errors.append("verified_count does not match verified loops")
    if report.get("status") != expected_status:
        errors.append(f"report status must be {expected_status} for observed blockers")
    return errors


def _validate_loop_summary(loop: Any, index: int) -> list[str]:
    if not isinstance(loop, dict):
        return [f"loop {index} must be an object"]
    errors: list[str] = []
    missing_fields = [field_name for field_name in REQUIRED_LOOP_FIELDS if field_name not in loop]
    errors.extend(f"loop {index} missing field: {field_name}" for field_name in missing_fields)
    extra_fields = sorted(set(loop) - set(REQUIRED_LOOP_FIELDS))
    errors.extend(f"loop {index} has unexpected field: {field_name}" for field_name in extra_fields)
    if missing_fields:
        return errors
    for field_name in (
        "loop_id",
        "name",
        "purpose",
        "owner",
        "risk_class",
        "rollback_policy",
        "learning_policy",
        "updated_at",
    ):
        if not isinstance(loop[field_name], str) or not loop[field_name]:
            errors.append(f"loop {index} {field_name} must be a non-empty string")
    if loop["status"] not in LOOP_STATUSES:
        errors.append(f"loop {index} status is invalid")
    if loop["mode"] not in LOOP_MODES:
        errors.append(f"loop {index} mode is invalid")
    if loop["current_step"] not in LOOP_STEPS:
        errors.append(f"loop {index} current_step is invalid")
    for field_name in (
        "required_authority",
        "authority_refs",
        "missing_authority",
        "required_evidence",
        "evidence_refs",
        "missing_evidence",
        "closure_conditions",
        "open_blockers",
    ):
        errors.extend(_validate_text_list(loop[field_name], f"loop {index} {field_name}"))
    errors.extend(_validate_evidence_bindings(loop["evidence_bindings"], loop["required_evidence"], index))
    errors.extend(_validate_authority_bindings(loop["authority_bindings"], loop["required_authority"], index))
    errors.extend(_validate_status_binding(loop["status_binding"], loop, index))
    errors.extend(_validate_transition_bindings(loop["transition_bindings"], loop, index))
    errors.extend(_validate_mode_binding(loop["mode_binding"], loop, index))
    errors.extend(_validate_risk_binding(loop["risk_binding"], loop, index))
    errors.extend(_validate_closure_condition_bindings(loop["closure_condition_bindings"], loop, index))
    errors.extend(_validate_step_receipts(loop["step_receipts"], loop, index))
    errors.extend(_validate_receipt_lineage_bindings(loop["receipt_lineage_bindings"], loop, index))
    errors.extend(_validate_closure_evidence_pack(loop["closure_evidence_pack"], loop, index))
    errors.extend(
        _validate_operator_closure_readiness_view(
            loop["operator_closure_readiness_view"],
            loop,
            index,
        )
    )
    errors.extend(_validate_proof_obligation_view(loop["proof_obligation_view"], loop, index))
    errors.extend(_validate_audit_evolution_view(loop["audit_evolution_view"], loop, index))
    if loop["open_blockers"] and loop["status"] != "blocked":
        errors.append(f"loop {index} with blockers must be blocked")
    if loop["status"] in {"verified", "closed"} and loop["missing_evidence"]:
        errors.append(f"loop {index} verified or closed loop cannot miss evidence")
    for evidence_name in loop["missing_evidence"]:
        expected_blocker = f"missing_evidence:{evidence_name}"
        if expected_blocker not in loop["open_blockers"]:
            errors.append(f"loop {index} missing evidence lacks blocker: {evidence_name}")
    if loop["status"] in {"verified", "closed"} and loop["missing_authority"]:
        errors.append(f"loop {index} verified or closed loop cannot miss authority")
    for authority_name in loop["missing_authority"]:
        expected_blocker = f"missing_authority:{authority_name}"
        if expected_blocker not in loop["open_blockers"]:
            errors.append(f"loop {index} missing authority lacks blocker: {authority_name}")
    errors.extend(_validate_rollback_binding(loop["rollback_binding"], loop, index))
    errors.extend(_validate_learning_binding(loop["learning_binding"], loop, index))
    errors.extend(_validate_closure_report(loop["closure_report"], loop, index))
    return errors


def _validate_status_binding(status_binding: Any, loop: dict[str, Any], index: int) -> list[str]:
    if not isinstance(status_binding, dict):
        return [f"loop {index} status_binding must be an object"]
    errors: list[str] = []
    required_fields = {
        "projected_status",
        "status_reason",
        "blocker_refs",
        "verification_refs",
        "closure_gate_refs",
        "source_refs",
        "validator_refs",
        "proof_surface_refs",
        "read_only",
        "status_transition",
        "terminal_closure",
    }
    missing = sorted(required_fields - set(status_binding))
    errors.extend(f"loop {index} status_binding missing field: {field_name}" for field_name in missing)
    extra = sorted(set(status_binding) - required_fields)
    errors.extend(f"loop {index} status_binding has unexpected field: {field_name}" for field_name in extra)
    if missing:
        return errors
    if status_binding["projected_status"] != loop["status"]:
        errors.append(f"loop {index} status_binding projected_status must match status")
    if not isinstance(status_binding["status_reason"], str) or not status_binding["status_reason"]:
        errors.append(f"loop {index} status_binding status_reason must be non-empty")
    for field_name in (
        "blocker_refs",
        "verification_refs",
        "closure_gate_refs",
        "source_refs",
        "validator_refs",
        "proof_surface_refs",
    ):
        errors.extend(
            _validate_text_list(
                status_binding[field_name],
                f"loop {index} status_binding {field_name}",
            )
        )
        if field_name != "blocker_refs" and isinstance(status_binding[field_name], list) and not status_binding[field_name]:
            errors.append(f"loop {index} status_binding {field_name} must be non-empty")
    if isinstance(status_binding["blocker_refs"], list) and set(status_binding["blocker_refs"]) != set(loop["open_blockers"]):
        errors.append(f"loop {index} status_binding blocker_refs must match open blockers")
    if loop["status"] in {"verified", "closed"} and status_binding["blocker_refs"]:
        errors.append(f"loop {index} verified or closed status_binding cannot carry blockers")
    if status_binding["read_only"] is not True:
        errors.append(f"loop {index} status_binding read_only must be true")
    if status_binding["status_transition"] is not False:
        errors.append(f"loop {index} status_binding status_transition must be false")
    if status_binding["terminal_closure"] is not False:
        errors.append(f"loop {index} status_binding terminal_closure must be false")
    return errors


def _validate_transition_bindings(
    transition_bindings: Any,
    loop: dict[str, Any],
    index: int,
) -> list[str]:
    if not isinstance(transition_bindings, list):
        return [f"loop {index} transition_bindings must be a list"]
    if not transition_bindings:
        return [f"loop {index} transition_bindings must not be empty"]
    errors: list[str] = []
    transition_refs: list[str] = []
    required_fields = {
        "transition_ref",
        "from_status",
        "to_status",
        "from_step",
        "to_step",
        "required_authority_refs",
        "required_evidence_refs",
        "blocker_refs",
        "receipt_refs",
        "rollback_refs",
        "source_refs",
        "validator_refs",
        "proof_surface_refs",
        "read_only",
        "executes_transition",
        "terminal_closure",
    }
    required_authority = set(loop["required_authority"])
    required_evidence = set(loop["required_evidence"])
    for binding_index, binding in enumerate(transition_bindings):
        if not isinstance(binding, dict):
            errors.append(f"loop {index} transition binding {binding_index} must be an object")
            continue
        missing = sorted(required_fields - set(binding))
        errors.extend(
            f"loop {index} transition binding {binding_index} missing field: {field_name}"
            for field_name in missing
        )
        extra = sorted(set(binding) - required_fields)
        errors.extend(
            f"loop {index} transition binding {binding_index} has unexpected field: {field_name}"
            for field_name in extra
        )
        if missing:
            continue
        transition_ref = binding["transition_ref"]
        if not isinstance(transition_ref, str) or not transition_ref:
            errors.append(f"loop {index} transition binding {binding_index} transition_ref must be non-empty")
        else:
            transition_refs.append(transition_ref)
        if binding["from_status"] not in LOOP_STATUSES:
            errors.append(f"loop {index} transition binding {binding_index} from_status is invalid")
        if binding["to_status"] not in LOOP_STATUSES:
            errors.append(f"loop {index} transition binding {binding_index} to_status is invalid")
        if binding["from_step"] not in LOOP_STEPS:
            errors.append(f"loop {index} transition binding {binding_index} from_step is invalid")
        if binding["to_step"] not in LOOP_STEPS:
            errors.append(f"loop {index} transition binding {binding_index} to_step is invalid")
        for field_name in (
            "required_authority_refs",
            "required_evidence_refs",
            "blocker_refs",
            "receipt_refs",
            "rollback_refs",
            "source_refs",
            "validator_refs",
            "proof_surface_refs",
        ):
            errors.extend(
                _validate_text_list(
                    binding[field_name],
                    f"loop {index} transition binding {binding_index} {field_name}",
                )
            )
            if field_name != "blocker_refs" and isinstance(binding[field_name], list) and not binding[field_name]:
                errors.append(f"loop {index} transition binding {binding_index} {field_name} must be non-empty")
        if isinstance(binding["required_authority_refs"], list):
            for authority_ref in binding["required_authority_refs"]:
                if authority_ref not in required_authority:
                    errors.append(
                        f"loop {index} transition binding {binding_index} unexpected authority ref: {authority_ref}"
                    )
        if isinstance(binding["required_evidence_refs"], list):
            for evidence_ref in binding["required_evidence_refs"]:
                if evidence_ref not in required_evidence:
                    errors.append(
                        f"loop {index} transition binding {binding_index} unexpected evidence ref: {evidence_ref}"
                    )
        if isinstance(binding["blocker_refs"], list) and set(binding["blocker_refs"]) != set(loop["open_blockers"]):
            errors.append(f"loop {index} transition binding {binding_index} blocker_refs must match open blockers")
        if isinstance(binding["rollback_refs"], list) and loop["rollback_policy"] not in binding["rollback_refs"]:
            errors.append(f"loop {index} transition binding {binding_index} rollback_refs must include rollback_policy")
        if binding["read_only"] is not True:
            errors.append(f"loop {index} transition binding {binding_index} read_only must be true")
        if binding["executes_transition"] is not False:
            errors.append(f"loop {index} transition binding {binding_index} executes_transition must be false")
        if binding["terminal_closure"] is not False:
            errors.append(f"loop {index} transition binding {binding_index} terminal_closure must be false")
    duplicate_refs = sorted({ref for ref in transition_refs if transition_refs.count(ref) > 1})
    errors.extend(f"loop {index} duplicate transition binding: {ref}" for ref in duplicate_refs)
    return errors


def _validate_closure_condition_bindings(
    closure_condition_bindings: Any,
    loop: dict[str, Any],
    index: int,
) -> list[str]:
    if not isinstance(closure_condition_bindings, list):
        return [f"loop {index} closure_condition_bindings must be a list"]
    errors: list[str] = []
    binding_refs: list[str] = []
    required_fields = {
        "closure_ref",
        "purpose",
        "required_evidence_refs",
        "required_authority_refs",
        "source_refs",
        "validator_refs",
        "proof_surface_refs",
        "read_only",
        "terminal_closure",
    }
    required_evidence = set(loop["required_evidence"])
    required_authority = set(loop["required_authority"])
    for binding_index, binding in enumerate(closure_condition_bindings):
        if not isinstance(binding, dict):
            errors.append(f"loop {index} closure condition binding {binding_index} must be an object")
            continue
        missing = sorted(required_fields - set(binding))
        errors.extend(
            f"loop {index} closure condition binding {binding_index} missing field: {field_name}"
            for field_name in missing
        )
        extra = sorted(set(binding) - required_fields)
        errors.extend(
            f"loop {index} closure condition binding {binding_index} has unexpected field: {field_name}"
            for field_name in extra
        )
        if missing:
            continue
        closure_ref = binding["closure_ref"]
        if not isinstance(closure_ref, str) or not closure_ref:
            errors.append(f"loop {index} closure condition binding {binding_index} closure_ref must be non-empty")
        else:
            binding_refs.append(closure_ref)
        if not isinstance(binding["purpose"], str) or not binding["purpose"]:
            errors.append(f"loop {index} closure condition binding {binding_index} purpose must be non-empty")
        for field_name in (
            "required_evidence_refs",
            "required_authority_refs",
            "source_refs",
            "validator_refs",
            "proof_surface_refs",
        ):
            errors.extend(
                _validate_text_list(
                    binding[field_name],
                    f"loop {index} closure condition binding {binding_index} {field_name}",
                )
            )
            if isinstance(binding[field_name], list) and not binding[field_name]:
                errors.append(
                    f"loop {index} closure condition binding {binding_index} {field_name} must be non-empty"
                )
        if isinstance(binding["required_evidence_refs"], list):
            for evidence_ref in binding["required_evidence_refs"]:
                if evidence_ref not in required_evidence:
                    errors.append(
                        f"loop {index} closure condition binding {binding_index} unexpected evidence ref: {evidence_ref}"
                    )
        if isinstance(binding["required_authority_refs"], list):
            for authority_ref in binding["required_authority_refs"]:
                if authority_ref not in required_authority:
                    errors.append(
                        f"loop {index} closure condition binding {binding_index} unexpected authority ref: {authority_ref}"
                    )
        if binding["read_only"] is not True:
            errors.append(f"loop {index} closure condition binding {binding_index} read_only must be true")
        if binding["terminal_closure"] is not False:
            errors.append(f"loop {index} closure condition binding {binding_index} terminal_closure must be false")
    duplicate_refs = sorted({ref for ref in binding_refs if binding_refs.count(ref) > 1})
    errors.extend(f"loop {index} duplicate closure condition binding: {ref}" for ref in duplicate_refs)
    closure_conditions = set(loop["closure_conditions"])
    binding_ref_set = set(binding_refs)
    for closure_ref in sorted(closure_conditions - binding_ref_set):
        errors.append(f"loop {index} missing closure condition binding: {closure_ref}")
    for closure_ref in sorted(binding_ref_set - closure_conditions):
        errors.append(f"loop {index} unexpected closure condition binding: {closure_ref}")
    return errors


def _validate_mode_binding(mode_binding: Any, loop: dict[str, Any], index: int) -> list[str]:
    if not isinstance(mode_binding, dict):
        return [f"loop {index} mode_binding must be an object"]
    errors: list[str] = []
    required_fields = {
        "projected_mode",
        "allowed_modes",
        "purpose",
        "separation_refs",
        "real_execution_guard_refs",
        "source_refs",
        "validator_refs",
        "proof_surface_refs",
        "read_only",
        "mode_transition",
        "terminal_closure",
    }
    missing = sorted(required_fields - set(mode_binding))
    errors.extend(f"loop {index} mode_binding missing field: {field_name}" for field_name in missing)
    extra = sorted(set(mode_binding) - required_fields)
    errors.extend(f"loop {index} mode_binding has unexpected field: {field_name}" for field_name in extra)
    if missing:
        return errors
    if mode_binding["projected_mode"] != loop["mode"]:
        errors.append(f"loop {index} mode_binding projected_mode must match mode")
    errors.extend(_validate_mode_list(mode_binding["allowed_modes"], f"loop {index} mode_binding allowed_modes"))
    if isinstance(mode_binding["allowed_modes"], list) and mode_binding["projected_mode"] not in mode_binding["allowed_modes"]:
        errors.append(f"loop {index} mode_binding projected_mode must be allowed")
    if not isinstance(mode_binding["purpose"], str) or not mode_binding["purpose"]:
        errors.append(f"loop {index} mode_binding purpose must be non-empty")
    for field_name in (
        "separation_refs",
        "real_execution_guard_refs",
        "source_refs",
        "validator_refs",
        "proof_surface_refs",
    ):
        errors.extend(
            _validate_text_list(
                mode_binding[field_name],
                f"loop {index} mode_binding {field_name}",
            )
        )
        if isinstance(mode_binding[field_name], list) and not mode_binding[field_name]:
            errors.append(f"loop {index} mode_binding {field_name} must be non-empty")
    if mode_binding["read_only"] is not True:
        errors.append(f"loop {index} mode_binding read_only must be true")
    if mode_binding["mode_transition"] is not False:
        errors.append(f"loop {index} mode_binding mode_transition must be false")
    if mode_binding["terminal_closure"] is not False:
        errors.append(f"loop {index} mode_binding terminal_closure must be false")
    return errors


def _validate_learning_binding(learning_binding: Any, loop: dict[str, Any], index: int) -> list[str]:
    if not isinstance(learning_binding, dict):
        return [f"loop {index} learning_binding must be an object"]
    errors: list[str] = []
    required_fields = {
        "learning_ref",
        "purpose",
        "evidence_input_refs",
        "admission_refs",
        "retention_refs",
        "source_refs",
        "validator_refs",
        "proof_surface_refs",
        "read_only",
        "terminal_closure",
    }
    missing = sorted(required_fields - set(learning_binding))
    errors.extend(f"loop {index} learning_binding missing field: {field_name}" for field_name in missing)
    extra = sorted(set(learning_binding) - required_fields)
    errors.extend(f"loop {index} learning_binding has unexpected field: {field_name}" for field_name in extra)
    if missing:
        return errors
    if learning_binding["learning_ref"] != loop["learning_policy"]:
        errors.append(f"loop {index} learning_binding learning_ref must match learning_policy")
    if not isinstance(learning_binding["purpose"], str) or not learning_binding["purpose"]:
        errors.append(f"loop {index} learning_binding purpose must be non-empty")
    for field_name in (
        "evidence_input_refs",
        "admission_refs",
        "retention_refs",
        "source_refs",
        "validator_refs",
        "proof_surface_refs",
    ):
        errors.extend(
            _validate_text_list(
                learning_binding[field_name],
                f"loop {index} learning_binding {field_name}",
            )
        )
        if isinstance(learning_binding[field_name], list) and not learning_binding[field_name]:
            errors.append(f"loop {index} learning_binding {field_name} must be non-empty")
    if learning_binding["read_only"] is not True:
        errors.append(f"loop {index} learning_binding read_only must be true")
    if learning_binding["terminal_closure"] is not False:
        errors.append(f"loop {index} learning_binding terminal_closure must be false")
    return errors


def _validate_risk_binding(risk_binding: Any, loop: dict[str, Any], index: int) -> list[str]:
    if not isinstance(risk_binding, dict):
        return [f"loop {index} risk_binding must be an object"]
    errors: list[str] = []
    required_fields = {
        "risk_ref",
        "purpose",
        "hazard_refs",
        "mitigation_refs",
        "monitor_refs",
        "source_refs",
        "validator_refs",
        "proof_surface_refs",
        "read_only",
        "terminal_closure",
    }
    missing = sorted(required_fields - set(risk_binding))
    errors.extend(f"loop {index} risk_binding missing field: {field_name}" for field_name in missing)
    extra = sorted(set(risk_binding) - required_fields)
    errors.extend(f"loop {index} risk_binding has unexpected field: {field_name}" for field_name in extra)
    if missing:
        return errors
    if risk_binding["risk_ref"] != loop["risk_class"]:
        errors.append(f"loop {index} risk_binding risk_ref must match risk_class")
    if not isinstance(risk_binding["purpose"], str) or not risk_binding["purpose"]:
        errors.append(f"loop {index} risk_binding purpose must be non-empty")
    for field_name in (
        "hazard_refs",
        "mitigation_refs",
        "monitor_refs",
        "source_refs",
        "validator_refs",
        "proof_surface_refs",
    ):
        errors.extend(
            _validate_text_list(
                risk_binding[field_name],
                f"loop {index} risk_binding {field_name}",
            )
        )
        if isinstance(risk_binding[field_name], list) and not risk_binding[field_name]:
            errors.append(f"loop {index} risk_binding {field_name} must be non-empty")
    if risk_binding["read_only"] is not True:
        errors.append(f"loop {index} risk_binding read_only must be true")
    if risk_binding["terminal_closure"] is not False:
        errors.append(f"loop {index} risk_binding terminal_closure must be false")
    return errors


def _validate_rollback_binding(rollback_binding: Any, loop: dict[str, Any], index: int) -> list[str]:
    if not isinstance(rollback_binding, dict):
        return [f"loop {index} rollback_binding must be an object"]
    errors: list[str] = []
    required_fields = {
        "rollback_ref",
        "purpose",
        "source_refs",
        "validator_refs",
        "proof_surface_refs",
        "read_only",
        "terminal_closure",
    }
    missing = sorted(required_fields - set(rollback_binding))
    errors.extend(f"loop {index} rollback_binding missing field: {field_name}" for field_name in missing)
    extra = sorted(set(rollback_binding) - required_fields)
    errors.extend(f"loop {index} rollback_binding has unexpected field: {field_name}" for field_name in extra)
    if missing:
        return errors
    if rollback_binding["rollback_ref"] != loop["rollback_policy"]:
        errors.append(f"loop {index} rollback_binding rollback_ref must match rollback_policy")
    if not isinstance(rollback_binding["purpose"], str) or not rollback_binding["purpose"]:
        errors.append(f"loop {index} rollback_binding purpose must be non-empty")
    for field_name in ("source_refs", "validator_refs", "proof_surface_refs"):
        errors.extend(
            _validate_text_list(
                rollback_binding[field_name],
                f"loop {index} rollback_binding {field_name}",
            )
        )
    if rollback_binding["read_only"] is not True:
        errors.append(f"loop {index} rollback_binding read_only must be true")
    if rollback_binding["terminal_closure"] is not False:
        errors.append(f"loop {index} rollback_binding terminal_closure must be false")
    return errors


def _validate_authority_bindings(
    authority_bindings: Any,
    required_authority: Any,
    index: int,
) -> list[str]:
    if not isinstance(authority_bindings, list):
        return [f"loop {index} authority_bindings must be a list"]
    if not isinstance(required_authority, list):
        return [f"loop {index} required_authority must be a list before binding validation"]
    errors: list[str] = []
    binding_refs: list[str] = []
    required_binding_fields = {
        "authority_ref",
        "purpose",
        "source_refs",
        "validator_refs",
        "proof_surface_refs",
        "read_only",
        "terminal_closure",
    }
    for binding_index, binding in enumerate(authority_bindings):
        if not isinstance(binding, dict):
            errors.append(f"loop {index} authority binding {binding_index} must be an object")
            continue
        missing = sorted(required_binding_fields - set(binding))
        errors.extend(
            f"loop {index} authority binding {binding_index} missing field: {field_name}"
            for field_name in missing
        )
        extra = sorted(set(binding) - required_binding_fields)
        errors.extend(
            f"loop {index} authority binding {binding_index} has unexpected field: {field_name}"
            for field_name in extra
        )
        if missing:
            continue
        authority_ref = binding["authority_ref"]
        if not isinstance(authority_ref, str) or not authority_ref:
            errors.append(f"loop {index} authority binding {binding_index} authority_ref must be non-empty")
        else:
            binding_refs.append(authority_ref)
        if not isinstance(binding["purpose"], str) or not binding["purpose"]:
            errors.append(f"loop {index} authority binding {binding_index} purpose must be non-empty")
        for field_name in ("source_refs", "validator_refs", "proof_surface_refs"):
            errors.extend(
                _validate_text_list(
                    binding[field_name],
                    f"loop {index} authority binding {binding_index} {field_name}",
                )
            )
        if binding["read_only"] is not True:
            errors.append(f"loop {index} authority binding {binding_index} read_only must be true")
        if binding["terminal_closure"] is not False:
            errors.append(
                f"loop {index} authority binding {binding_index} terminal_closure must be false"
            )
    duplicate_refs = sorted({ref for ref in binding_refs if binding_refs.count(ref) > 1})
    errors.extend(f"loop {index} duplicate authority binding: {ref}" for ref in duplicate_refs)
    required_refs = set(required_authority)
    binding_ref_set = set(binding_refs)
    for authority_name in sorted(required_refs - binding_ref_set):
        errors.append(f"loop {index} missing authority binding: {authority_name}")
    for authority_name in sorted(binding_ref_set - required_refs):
        errors.append(f"loop {index} unexpected authority binding: {authority_name}")
    return errors


def _validate_step_receipts(step_receipts: Any, loop: dict[str, Any], index: int) -> list[str]:
    if not isinstance(step_receipts, list):
        return [f"loop {index} step_receipts must be a list"]
    if not step_receipts:
        return [f"loop {index} step_receipts must not be empty"]
    errors: list[str] = []
    seen_steps: list[str] = []
    required_fields = {
        "loop_id",
        "step",
        "input_hash",
        "output_hash",
        "decision",
        "evidence_refs",
        "status",
        "errors",
        "timestamp",
        "metadata",
    }
    for receipt_index, receipt in enumerate(step_receipts):
        if not isinstance(receipt, dict):
            errors.append(f"loop {index} step receipt {receipt_index} must be an object")
            continue
        missing = sorted(required_fields - set(receipt))
        errors.extend(
            f"loop {index} step receipt {receipt_index} missing field: {field_name}"
            for field_name in missing
        )
        extra = sorted(set(receipt) - required_fields)
        errors.extend(
            f"loop {index} step receipt {receipt_index} has unexpected field: {field_name}"
            for field_name in extra
        )
        if missing:
            continue
        if receipt["loop_id"] != loop["loop_id"]:
            errors.append(f"loop {index} step receipt {receipt_index} loop_id must match loop_id")
        step = receipt["step"]
        if step not in LOOP_STEPS:
            errors.append(f"loop {index} step receipt {receipt_index} step is invalid")
        else:
            seen_steps.append(step)
        for field_name in ("input_hash", "output_hash"):
            value = receipt[field_name]
            if (
                not isinstance(value, str)
                or len(value) != 71
                or not value.startswith("sha256:")
            ):
                errors.append(
                    f"loop {index} step receipt {receipt_index} {field_name} must be sha256"
                )
        if not isinstance(receipt["decision"], str) or not receipt["decision"]:
            errors.append(f"loop {index} step receipt {receipt_index} decision must be non-empty")
        errors.extend(
            _validate_text_list(
                receipt["evidence_refs"],
                f"loop {index} step receipt {receipt_index} evidence_refs",
            )
        )
        if receipt["status"] not in {"open", "blocked", "verified"}:
            errors.append(f"loop {index} step receipt {receipt_index} status is invalid")
        if receipt["status"] == "blocked" and not loop["open_blockers"]:
            errors.append(f"loop {index} step receipt {receipt_index} blocked without loop blockers")
        errors.extend(
            _validate_text_list(
                receipt["errors"],
                f"loop {index} step receipt {receipt_index} errors",
            )
        )
        if set(receipt["errors"]) != set(loop["open_blockers"]):
            errors.append(f"loop {index} step receipt {receipt_index} errors must match open blockers")
        if not isinstance(receipt["timestamp"], str) or not receipt["timestamp"]:
            errors.append(f"loop {index} step receipt {receipt_index} timestamp must be non-empty")
        metadata = receipt["metadata"]
        if not isinstance(metadata, dict):
            errors.append(f"loop {index} step receipt {receipt_index} metadata must be an object")
            continue
        if metadata.get("read_only") is not True:
            errors.append(f"loop {index} step receipt {receipt_index} read_only must be true")
        if metadata.get("synthetic_projection") is not True:
            errors.append(
                f"loop {index} step receipt {receipt_index} synthetic_projection must be true"
            )
        if metadata.get("terminal_closure") is not False:
            errors.append(f"loop {index} step receipt {receipt_index} terminal_closure must be false")
        if metadata.get("behavior_rewrite") is not False:
            errors.append(f"loop {index} step receipt {receipt_index} behavior_rewrite must be false")
    duplicate_steps = sorted({step for step in seen_steps if seen_steps.count(step) > 1})
    errors.extend(f"loop {index} duplicate step receipt: {step}" for step in duplicate_steps)
    return errors


def _validate_receipt_lineage_bindings(
    lineage_bindings: Any,
    loop: dict[str, Any],
    index: int,
) -> list[str]:
    if not isinstance(lineage_bindings, list):
        return [f"loop {index} receipt_lineage_bindings must be a list"]
    if not lineage_bindings:
        return [f"loop {index} receipt_lineage_bindings must not be empty"]
    errors: list[str] = []
    required_fields = {
        "lineage_ref",
        "step",
        "receipt_ref",
        "receipt_hash",
        "required_evidence_refs",
        "observed_evidence_refs",
        "blocker_refs",
        "source_receipt_refs",
        "source_refs",
        "validator_refs",
        "proof_surface_refs",
        "read_only",
        "emits_receipt",
        "terminal_closure",
    }
    lineage_refs: list[str] = []
    lineage_steps: list[str] = []
    step_receipts = {
        receipt.get("step"): receipt
        for receipt in loop.get("step_receipts", [])
        if isinstance(receipt, dict)
    }
    required_evidence = set(loop["required_evidence"])
    for binding_index, binding in enumerate(lineage_bindings):
        if not isinstance(binding, dict):
            errors.append(f"loop {index} receipt lineage binding {binding_index} must be an object")
            continue
        missing = sorted(required_fields - set(binding))
        errors.extend(
            f"loop {index} receipt lineage binding {binding_index} missing field: {field_name}"
            for field_name in missing
        )
        extra = sorted(set(binding) - required_fields)
        errors.extend(
            f"loop {index} receipt lineage binding {binding_index} has unexpected field: {field_name}"
            for field_name in extra
        )
        if missing:
            continue
        lineage_ref = binding["lineage_ref"]
        if not isinstance(lineage_ref, str) or not lineage_ref:
            errors.append(f"loop {index} receipt lineage binding {binding_index} lineage_ref must be non-empty")
        else:
            lineage_refs.append(lineage_ref)
        step = binding["step"]
        if step not in LOOP_STEPS:
            errors.append(f"loop {index} receipt lineage binding {binding_index} step is invalid")
        else:
            lineage_steps.append(step)
            receipt = step_receipts.get(step)
            if receipt is None:
                errors.append(f"loop {index} receipt lineage binding {binding_index} step lacks receipt")
            elif binding["receipt_hash"] != receipt.get("output_hash"):
                errors.append(
                    f"loop {index} receipt lineage binding {binding_index} receipt_hash must match step receipt"
                )
        receipt_ref = binding["receipt_ref"]
        if not isinstance(receipt_ref, str) or not receipt_ref:
            errors.append(f"loop {index} receipt lineage binding {binding_index} receipt_ref must be non-empty")
        receipt_hash = binding["receipt_hash"]
        if (
            not isinstance(receipt_hash, str)
            or len(receipt_hash) != 71
            or not receipt_hash.startswith("sha256:")
        ):
            errors.append(f"loop {index} receipt lineage binding {binding_index} receipt_hash must be sha256")
        for field_name in (
            "required_evidence_refs",
            "observed_evidence_refs",
            "blocker_refs",
            "source_receipt_refs",
            "source_refs",
            "validator_refs",
            "proof_surface_refs",
        ):
            errors.extend(
                _validate_text_list(
                    binding[field_name],
                    f"loop {index} receipt lineage binding {binding_index} {field_name}",
                )
            )
            if field_name not in {"observed_evidence_refs", "blocker_refs"} and isinstance(binding[field_name], list) and not binding[field_name]:
                errors.append(f"loop {index} receipt lineage binding {binding_index} {field_name} must be non-empty")
        if isinstance(binding["required_evidence_refs"], list):
            for evidence_ref in binding["required_evidence_refs"]:
                if evidence_ref not in required_evidence:
                    errors.append(
                        f"loop {index} receipt lineage binding {binding_index} unexpected evidence ref: {evidence_ref}"
                    )
        if isinstance(binding["observed_evidence_refs"], list) and set(binding["observed_evidence_refs"]) != set(loop["evidence_refs"]):
            errors.append(
                f"loop {index} receipt lineage binding {binding_index} observed_evidence_refs must match evidence_refs"
            )
        if isinstance(binding["blocker_refs"], list) and set(binding["blocker_refs"]) != set(loop["open_blockers"]):
            errors.append(f"loop {index} receipt lineage binding {binding_index} blocker_refs must match open blockers")
        if isinstance(binding["source_receipt_refs"], list) and receipt_ref not in binding["source_receipt_refs"]:
            errors.append(
                f"loop {index} receipt lineage binding {binding_index} source_receipt_refs must include receipt_ref"
            )
        if binding["read_only"] is not True:
            errors.append(f"loop {index} receipt lineage binding {binding_index} read_only must be true")
        if binding["emits_receipt"] is not False:
            errors.append(f"loop {index} receipt lineage binding {binding_index} emits_receipt must be false")
        if binding["terminal_closure"] is not False:
            errors.append(f"loop {index} receipt lineage binding {binding_index} terminal_closure must be false")
    duplicate_refs = sorted({ref for ref in lineage_refs if lineage_refs.count(ref) > 1})
    errors.extend(f"loop {index} duplicate receipt lineage binding: {ref}" for ref in duplicate_refs)
    receipt_steps = set(step_receipts)
    lineage_step_set = set(lineage_steps)
    if lineage_step_set != receipt_steps:
        errors.append(f"loop {index} receipt lineage bindings must cover step receipts exactly")
    return errors


def _validate_closure_evidence_pack(
    evidence_pack: Any,
    loop: dict[str, Any],
    index: int,
) -> list[str]:
    if not isinstance(evidence_pack, dict):
        return [f"loop {index} closure_evidence_pack must be an object"]
    errors: list[str] = []
    required_fields = {
        "pack_ref",
        "loop_id",
        "required_evidence_refs",
        "observed_evidence_refs",
        "missing_evidence_refs",
        "required_authority_refs",
        "observed_authority_refs",
        "missing_authority_refs",
        "blocker_refs",
        "closure_condition_refs",
        "receipt_lineage_refs",
        "closure_report_ref",
        "rollback_ref",
        "validator_refs",
        "proof_surface_refs",
        "evidence_complete",
        "authority_complete",
        "closure_blocked",
        "rollback_available",
        "read_only",
        "emits_receipt",
        "terminal_closure",
    }
    missing = sorted(required_fields - set(evidence_pack))
    errors.extend(f"loop {index} closure_evidence_pack missing field: {field_name}" for field_name in missing)
    extra = sorted(set(evidence_pack) - required_fields)
    errors.extend(f"loop {index} closure_evidence_pack has unexpected field: {field_name}" for field_name in extra)
    if missing:
        return errors
    for field_name in ("pack_ref", "loop_id", "closure_report_ref", "rollback_ref"):
        if not isinstance(evidence_pack[field_name], str) or not evidence_pack[field_name]:
            errors.append(f"loop {index} closure_evidence_pack {field_name} must be non-empty")
    for field_name in (
        "required_evidence_refs",
        "observed_evidence_refs",
        "missing_evidence_refs",
        "required_authority_refs",
        "observed_authority_refs",
        "missing_authority_refs",
        "blocker_refs",
        "closure_condition_refs",
        "receipt_lineage_refs",
        "validator_refs",
        "proof_surface_refs",
    ):
        errors.extend(
            _validate_text_list(
                evidence_pack[field_name],
                f"loop {index} closure_evidence_pack {field_name}",
            )
        )
        if (
            field_name
            in {
                "required_evidence_refs",
                "required_authority_refs",
                "closure_condition_refs",
                "receipt_lineage_refs",
                "validator_refs",
                "proof_surface_refs",
            }
            and isinstance(evidence_pack[field_name], list)
            and not evidence_pack[field_name]
        ):
            errors.append(f"loop {index} closure_evidence_pack {field_name} must be non-empty")
    if evidence_pack["loop_id"] != loop["loop_id"]:
        errors.append(f"loop {index} closure_evidence_pack loop_id must match loop_id")
    if set(evidence_pack["required_evidence_refs"]) != set(loop["required_evidence"]):
        errors.append(f"loop {index} closure_evidence_pack required_evidence_refs must match required_evidence")
    if set(evidence_pack["observed_evidence_refs"]) != set(loop["evidence_refs"]):
        errors.append(f"loop {index} closure_evidence_pack observed_evidence_refs must match evidence_refs")
    if set(evidence_pack["missing_evidence_refs"]) != set(loop["missing_evidence"]):
        errors.append(f"loop {index} closure_evidence_pack missing_evidence_refs must match missing_evidence")
    if set(evidence_pack["required_authority_refs"]) != set(loop["required_authority"]):
        errors.append(f"loop {index} closure_evidence_pack required_authority_refs must match required_authority")
    if set(evidence_pack["observed_authority_refs"]) != set(loop["authority_refs"]):
        errors.append(f"loop {index} closure_evidence_pack observed_authority_refs must match authority_refs")
    if set(evidence_pack["missing_authority_refs"]) != set(loop["missing_authority"]):
        errors.append(f"loop {index} closure_evidence_pack missing_authority_refs must match missing_authority")
    if set(evidence_pack["blocker_refs"]) != set(loop["open_blockers"]):
        errors.append(f"loop {index} closure_evidence_pack blocker_refs must match open_blockers")
    if set(evidence_pack["closure_condition_refs"]) != set(loop["closure_conditions"]):
        errors.append(f"loop {index} closure_evidence_pack closure_condition_refs must match closure_conditions")
    lineage_refs = {
        binding.get("lineage_ref")
        for binding in loop["receipt_lineage_bindings"]
        if isinstance(binding, dict)
    }
    if set(evidence_pack["receipt_lineage_refs"]) != lineage_refs:
        errors.append(f"loop {index} closure_evidence_pack receipt_lineage_refs must match receipt lineage bindings")
    closure_report = loop["closure_report"]
    if not isinstance(closure_report, dict):
        errors.append(f"loop {index} closure_evidence_pack requires closure_report object")
        closure_report = {}
    if evidence_pack["closure_report_ref"] != "closure_report":
        errors.append(f"loop {index} closure_evidence_pack closure_report_ref must be closure_report")
    if evidence_pack["rollback_ref"] != loop["rollback_policy"]:
        errors.append(f"loop {index} closure_evidence_pack rollback_ref must match rollback_policy")
    if evidence_pack["evidence_complete"] != closure_report.get("evidence_complete"):
        errors.append(f"loop {index} closure_evidence_pack evidence_complete must match closure_report")
    if evidence_pack["authority_complete"] != (not loop["missing_authority"]):
        errors.append(f"loop {index} closure_evidence_pack authority_complete must match missing_authority")
    if evidence_pack["closure_blocked"] != bool(loop["open_blockers"]):
        errors.append(f"loop {index} closure_evidence_pack closure_blocked must match open_blockers")
    if evidence_pack["rollback_available"] != closure_report.get("rollback_available"):
        errors.append(f"loop {index} closure_evidence_pack rollback_available must match closure_report")
    if evidence_pack["read_only"] is not True:
        errors.append(f"loop {index} closure_evidence_pack read_only must be true")
    if evidence_pack["emits_receipt"] is not False:
        errors.append(f"loop {index} closure_evidence_pack emits_receipt must be false")
    if evidence_pack["terminal_closure"] is not False:
        errors.append(f"loop {index} closure_evidence_pack terminal_closure must be false")
    return errors


def _validate_operator_closure_readiness_view(
    readiness_view: Any,
    loop: dict[str, Any],
    index: int,
) -> list[str]:
    if not isinstance(readiness_view, dict):
        return [f"loop {index} operator_closure_readiness_view must be an object"]
    errors: list[str] = []
    required_fields = {
        "view_ref",
        "loop_id",
        "projected_status",
        "readiness_state",
        "blocker_refs",
        "evidence_gap_refs",
        "authority_gap_refs",
        "closure_condition_refs",
        "rollback_ref",
        "rollback_available",
        "next_proof_action",
        "next_proof_refs",
        "read_only",
        "mutation_route",
        "terminal_closure",
    }
    missing = sorted(required_fields - set(readiness_view))
    errors.extend(
        f"loop {index} operator_closure_readiness_view missing field: {field_name}"
        for field_name in missing
    )
    extra = sorted(set(readiness_view) - required_fields)
    errors.extend(
        f"loop {index} operator_closure_readiness_view has unexpected field: {field_name}"
        for field_name in extra
    )
    if missing:
        return errors
    for field_name in ("view_ref", "loop_id", "readiness_state", "rollback_ref", "next_proof_action"):
        if not isinstance(readiness_view[field_name], str) or not readiness_view[field_name]:
            errors.append(
                f"loop {index} operator_closure_readiness_view {field_name} must be non-empty"
            )
    if readiness_view["projected_status"] != loop["status"]:
        errors.append(
            f"loop {index} operator_closure_readiness_view projected_status must match status"
        )
    if readiness_view["loop_id"] != loop["loop_id"]:
        errors.append(f"loop {index} operator_closure_readiness_view loop_id must match loop_id")
    for field_name in (
        "blocker_refs",
        "evidence_gap_refs",
        "authority_gap_refs",
        "closure_condition_refs",
        "next_proof_refs",
    ):
        errors.extend(
            _validate_text_list(
                readiness_view[field_name],
                f"loop {index} operator_closure_readiness_view {field_name}",
            )
        )
        if field_name in {"closure_condition_refs", "next_proof_refs"} and not readiness_view[field_name]:
            errors.append(
                f"loop {index} operator_closure_readiness_view {field_name} must be non-empty"
            )
    if set(readiness_view["blocker_refs"]) != set(loop["open_blockers"]):
        errors.append(
            f"loop {index} operator_closure_readiness_view blocker_refs must match open_blockers"
        )
    if set(readiness_view["evidence_gap_refs"]) != set(loop["missing_evidence"]):
        errors.append(
            f"loop {index} operator_closure_readiness_view evidence_gap_refs must match missing_evidence"
        )
    if set(readiness_view["authority_gap_refs"]) != set(loop["missing_authority"]):
        errors.append(
            f"loop {index} operator_closure_readiness_view authority_gap_refs must match missing_authority"
        )
    if set(readiness_view["closure_condition_refs"]) != set(loop["closure_conditions"]):
        errors.append(
            f"loop {index} operator_closure_readiness_view closure_condition_refs must match closure_conditions"
        )
    if readiness_view["rollback_ref"] != loop["rollback_policy"]:
        errors.append(
            f"loop {index} operator_closure_readiness_view rollback_ref must match rollback_policy"
        )
    closure_report = loop["closure_report"]
    if not isinstance(closure_report, dict):
        errors.append(f"loop {index} operator_closure_readiness_view requires closure_report object")
        closure_report = {}
    if readiness_view["rollback_available"] != closure_report.get("rollback_available"):
        errors.append(
            f"loop {index} operator_closure_readiness_view rollback_available must match closure_report"
        )
    expected_readiness_state = (
        "blocked_by_unresolved_gaps"
        if loop["open_blockers"]
        else "ready_for_terminal_closure_review"
    )
    if readiness_view["readiness_state"] != expected_readiness_state:
        errors.append(
            f"loop {index} operator_closure_readiness_view readiness_state must match blockers"
        )
    expected_next_action = (
        "resolve_blockers_before_terminal_closure_review"
        if loop["open_blockers"]
        else "run_loop_specific_terminal_closure_workflow"
    )
    if readiness_view["next_proof_action"] != expected_next_action:
        errors.append(
            f"loop {index} operator_closure_readiness_view next_proof_action must match blockers"
        )
    if "closure_evidence_pack" not in readiness_view["next_proof_refs"]:
        errors.append(
            f"loop {index} operator_closure_readiness_view next_proof_refs must include closure_evidence_pack"
        )
    if "closure_report" not in readiness_view["next_proof_refs"]:
        errors.append(
            f"loop {index} operator_closure_readiness_view next_proof_refs must include closure_report"
        )
    if readiness_view["read_only"] is not True:
        errors.append(f"loop {index} operator_closure_readiness_view read_only must be true")
    if readiness_view["mutation_route"] is not False:
        errors.append(f"loop {index} operator_closure_readiness_view mutation_route must be false")
    if readiness_view["terminal_closure"] is not False:
        errors.append(f"loop {index} operator_closure_readiness_view terminal_closure must be false")
    return errors


def _validate_proof_obligation_view(
    proof_view: Any,
    loop: dict[str, Any],
    index: int,
) -> list[str]:
    if not isinstance(proof_view, dict):
        return [f"loop {index} proof_obligation_view must be an object"]
    errors: list[str] = []
    required_fields = {
        "obligation_ref",
        "loop_id",
        "obligation_state",
        "required_evidence_refs",
        "satisfied_evidence_refs",
        "missing_evidence_refs",
        "required_authority_refs",
        "satisfied_authority_refs",
        "missing_authority_refs",
        "closure_condition_refs",
        "validator_refs",
        "proof_surface_refs",
        "blocker_refs",
        "read_only",
        "executes_validator",
        "terminal_closure",
    }
    missing = sorted(required_fields - set(proof_view))
    errors.extend(f"loop {index} proof_obligation_view missing field: {field_name}" for field_name in missing)
    extra = sorted(set(proof_view) - required_fields)
    errors.extend(f"loop {index} proof_obligation_view has unexpected field: {field_name}" for field_name in extra)
    if missing:
        return errors
    for field_name in ("obligation_ref", "loop_id", "obligation_state"):
        if not isinstance(proof_view[field_name], str) or not proof_view[field_name]:
            errors.append(f"loop {index} proof_obligation_view {field_name} must be non-empty")
    for field_name in (
        "required_evidence_refs",
        "satisfied_evidence_refs",
        "missing_evidence_refs",
        "required_authority_refs",
        "satisfied_authority_refs",
        "missing_authority_refs",
        "closure_condition_refs",
        "validator_refs",
        "proof_surface_refs",
        "blocker_refs",
    ):
        errors.extend(
            _validate_text_list(
                proof_view[field_name],
                f"loop {index} proof_obligation_view {field_name}",
            )
        )
        if (
            field_name
            in {
                "required_evidence_refs",
                "required_authority_refs",
                "closure_condition_refs",
                "validator_refs",
                "proof_surface_refs",
            }
            and isinstance(proof_view[field_name], list)
            and not proof_view[field_name]
        ):
            errors.append(f"loop {index} proof_obligation_view {field_name} must be non-empty")
    if proof_view["loop_id"] != loop["loop_id"]:
        errors.append(f"loop {index} proof_obligation_view loop_id must match loop_id")
    if set(proof_view["required_evidence_refs"]) != set(loop["required_evidence"]):
        errors.append(f"loop {index} proof_obligation_view required_evidence_refs must match required_evidence")
    if set(proof_view["satisfied_evidence_refs"]) != set(loop["evidence_refs"]):
        errors.append(f"loop {index} proof_obligation_view satisfied_evidence_refs must match evidence_refs")
    if set(proof_view["missing_evidence_refs"]) != set(loop["missing_evidence"]):
        errors.append(f"loop {index} proof_obligation_view missing_evidence_refs must match missing_evidence")
    if set(proof_view["required_authority_refs"]) != set(loop["required_authority"]):
        errors.append(f"loop {index} proof_obligation_view required_authority_refs must match required_authority")
    if set(proof_view["satisfied_authority_refs"]) != set(loop["authority_refs"]):
        errors.append(f"loop {index} proof_obligation_view satisfied_authority_refs must match authority_refs")
    if set(proof_view["missing_authority_refs"]) != set(loop["missing_authority"]):
        errors.append(f"loop {index} proof_obligation_view missing_authority_refs must match missing_authority")
    if set(proof_view["closure_condition_refs"]) != set(loop["closure_conditions"]):
        errors.append(f"loop {index} proof_obligation_view closure_condition_refs must match closure_conditions")
    closure_evidence_pack = loop["closure_evidence_pack"]
    if not isinstance(closure_evidence_pack, dict):
        errors.append(f"loop {index} proof_obligation_view requires closure_evidence_pack object")
        closure_evidence_pack = {}
    if set(proof_view["validator_refs"]) != set(closure_evidence_pack.get("validator_refs", ())):
        errors.append(f"loop {index} proof_obligation_view validator_refs must match closure_evidence_pack")
    if set(proof_view["proof_surface_refs"]) != set(closure_evidence_pack.get("proof_surface_refs", ())):
        errors.append(f"loop {index} proof_obligation_view proof_surface_refs must match closure_evidence_pack")
    if set(proof_view["blocker_refs"]) != set(loop["open_blockers"]):
        errors.append(f"loop {index} proof_obligation_view blocker_refs must match open_blockers")
    expected_obligation_state = (
        "blocked_by_missing_proof"
        if loop["open_blockers"]
        else "proof_obligations_satisfied_terminal_review_required"
    )
    if proof_view["obligation_state"] != expected_obligation_state:
        errors.append(f"loop {index} proof_obligation_view obligation_state must match blockers")
    if proof_view["read_only"] is not True:
        errors.append(f"loop {index} proof_obligation_view read_only must be true")
    if proof_view["executes_validator"] is not False:
        errors.append(f"loop {index} proof_obligation_view executes_validator must be false")
    if proof_view["terminal_closure"] is not False:
        errors.append(f"loop {index} proof_obligation_view terminal_closure must be false")
    return errors


def _validate_audit_evolution_view(
    audit_view: Any,
    loop: dict[str, Any],
    index: int,
) -> list[str]:
    if not isinstance(audit_view, dict):
        return [f"loop {index} audit_evolution_view must be an object"]
    errors: list[str] = []
    required_fields = {
        "view_ref",
        "loop_id",
        "audit_state",
        "receipt_refs",
        "receipt_lineage_refs",
        "audit_blocker_refs",
        "learning_policy_ref",
        "learning_candidate_refs",
        "learning_evidence_input_refs",
        "learning_admission_refs",
        "learning_retention_refs",
        "proof_surface_refs",
        "read_only",
        "emits_receipt",
        "admits_learning",
        "terminal_closure",
    }
    missing = sorted(required_fields - set(audit_view))
    errors.extend(f"loop {index} audit_evolution_view missing field: {field_name}" for field_name in missing)
    extra = sorted(set(audit_view) - required_fields)
    errors.extend(f"loop {index} audit_evolution_view has unexpected field: {field_name}" for field_name in extra)
    if missing:
        return errors
    for field_name in ("view_ref", "loop_id", "audit_state", "learning_policy_ref"):
        if not isinstance(audit_view[field_name], str) or not audit_view[field_name]:
            errors.append(f"loop {index} audit_evolution_view {field_name} must be non-empty")
    for field_name in (
        "receipt_refs",
        "receipt_lineage_refs",
        "audit_blocker_refs",
        "learning_candidate_refs",
        "learning_evidence_input_refs",
        "learning_admission_refs",
        "learning_retention_refs",
        "proof_surface_refs",
    ):
        errors.extend(
            _validate_text_list(
                audit_view[field_name],
                f"loop {index} audit_evolution_view {field_name}",
            )
        )
        if (
            field_name
            in {
                "receipt_refs",
                "receipt_lineage_refs",
                "learning_evidence_input_refs",
                "learning_admission_refs",
                "learning_retention_refs",
                "proof_surface_refs",
            }
            and isinstance(audit_view[field_name], list)
            and not audit_view[field_name]
        ):
            errors.append(f"loop {index} audit_evolution_view {field_name} must be non-empty")
    if audit_view["loop_id"] != loop["loop_id"]:
        errors.append(f"loop {index} audit_evolution_view loop_id must match loop_id")
    if set(audit_view["receipt_refs"]) != {
        receipt.get("output_hash")
        for receipt in loop["step_receipts"]
        if isinstance(receipt, dict)
    }:
        errors.append(f"loop {index} audit_evolution_view receipt_refs must match step_receipts")
    if set(audit_view["receipt_lineage_refs"]) != {
        binding.get("lineage_ref")
        for binding in loop["receipt_lineage_bindings"]
        if isinstance(binding, dict)
    }:
        errors.append(f"loop {index} audit_evolution_view receipt_lineage_refs must match lineage bindings")
    if set(audit_view["audit_blocker_refs"]) != set(loop["open_blockers"]):
        errors.append(f"loop {index} audit_evolution_view audit_blocker_refs must match open_blockers")
    if audit_view["learning_policy_ref"] != loop["learning_policy"]:
        errors.append(f"loop {index} audit_evolution_view learning_policy_ref must match learning_policy")
    closure_report = loop["closure_report"] if isinstance(loop["closure_report"], dict) else {}
    if set(audit_view["learning_candidate_refs"]) != set(closure_report.get("learning_candidates", ())):
        errors.append(f"loop {index} audit_evolution_view learning_candidate_refs must match closure_report")
    learning_binding = loop["learning_binding"] if isinstance(loop["learning_binding"], dict) else {}
    if set(audit_view["learning_evidence_input_refs"]) != set(learning_binding.get("evidence_input_refs", ())):
        errors.append(f"loop {index} audit_evolution_view learning_evidence_input_refs must match learning_binding")
    if set(audit_view["learning_admission_refs"]) != set(learning_binding.get("admission_refs", ())):
        errors.append(f"loop {index} audit_evolution_view learning_admission_refs must match learning_binding")
    if set(audit_view["learning_retention_refs"]) != set(learning_binding.get("retention_refs", ())):
        errors.append(f"loop {index} audit_evolution_view learning_retention_refs must match learning_binding")
    closure_evidence_pack = loop["closure_evidence_pack"] if isinstance(loop["closure_evidence_pack"], dict) else {}
    expected_proof_surfaces = set(closure_evidence_pack.get("proof_surface_refs", ())) | set(
        learning_binding.get("proof_surface_refs", ())
    )
    if set(audit_view["proof_surface_refs"]) != expected_proof_surfaces:
        errors.append(f"loop {index} audit_evolution_view proof_surface_refs must match closure and learning surfaces")
    expected_audit_state = (
        "audit_blocked_by_unresolved_gaps"
        if loop["open_blockers"]
        else "audit_ready_for_terminal_review"
    )
    if audit_view["audit_state"] != expected_audit_state:
        errors.append(f"loop {index} audit_evolution_view audit_state must match blockers")
    if loop["open_blockers"] and loop["learning_policy"] not in audit_view["learning_candidate_refs"]:
        errors.append(f"loop {index} audit_evolution_view learning candidates must include learning_policy")
    if not loop["open_blockers"] and audit_view["learning_candidate_refs"]:
        errors.append(f"loop {index} audit_evolution_view learning candidates must be empty when audit is ready")
    if audit_view["read_only"] is not True:
        errors.append(f"loop {index} audit_evolution_view read_only must be true")
    if audit_view["emits_receipt"] is not False:
        errors.append(f"loop {index} audit_evolution_view emits_receipt must be false")
    if audit_view["admits_learning"] is not False:
        errors.append(f"loop {index} audit_evolution_view admits_learning must be false")
    if audit_view["terminal_closure"] is not False:
        errors.append(f"loop {index} audit_evolution_view terminal_closure must be false")
    return errors


def _validate_closure_report(closure_report: Any, loop: dict[str, Any], index: int) -> list[str]:
    if not isinstance(closure_report, dict):
        return [f"loop {index} closure_report must be an object"]
    errors: list[str] = []
    required_fields = {
        "loop_id",
        "closed",
        "closure_reason",
        "evidence_complete",
        "unresolved_gaps",
        "rollback_available",
        "learning_candidates",
        "metadata",
    }
    missing = sorted(required_fields - set(closure_report))
    errors.extend(f"loop {index} closure_report missing field: {field_name}" for field_name in missing)
    extra = sorted(set(closure_report) - required_fields)
    errors.extend(f"loop {index} closure_report has unexpected field: {field_name}" for field_name in extra)
    if missing:
        return errors
    if closure_report["loop_id"] != loop["loop_id"]:
        errors.append(f"loop {index} closure_report loop_id must match loop_id")
    if closure_report["closed"] is not False:
        errors.append(f"loop {index} closure_report closed must be false")
    if not isinstance(closure_report["closure_reason"], str) or not closure_report["closure_reason"]:
        errors.append(f"loop {index} closure_report closure_reason must be non-empty")
    expected_evidence_complete = not bool(loop["missing_evidence"])
    if closure_report["evidence_complete"] is not expected_evidence_complete:
        errors.append(f"loop {index} closure_report evidence_complete does not match missing evidence")
    errors.extend(
        _validate_text_list(
            closure_report["unresolved_gaps"],
            f"loop {index} closure_report unresolved_gaps",
        )
    )
    if set(closure_report["unresolved_gaps"]) != set(loop["open_blockers"]):
        errors.append(f"loop {index} closure_report unresolved_gaps must match open blockers")
    if not isinstance(closure_report["rollback_available"], bool):
        errors.append(f"loop {index} closure_report rollback_available must be boolean")
    errors.extend(
        _validate_text_list(
            closure_report["learning_candidates"],
            f"loop {index} closure_report learning_candidates",
        )
    )
    metadata = closure_report["metadata"]
    if not isinstance(metadata, dict):
        errors.append(f"loop {index} closure_report metadata must be an object")
        return errors
    if metadata.get("read_only") is not True:
        errors.append(f"loop {index} closure_report metadata read_only must be true")
    if metadata.get("terminal_closure") is not False:
        errors.append(f"loop {index} closure_report metadata terminal_closure must be false")
    errors.extend(
        _validate_text_list(
            metadata.get("closure_conditions"),
            f"loop {index} closure_report metadata closure_conditions",
        )
    )
    return errors


def _validate_evidence_bindings(
    evidence_bindings: Any,
    required_evidence: Any,
    index: int,
) -> list[str]:
    if not isinstance(evidence_bindings, list):
        return [f"loop {index} evidence_bindings must be a list"]
    if not isinstance(required_evidence, list):
        return [f"loop {index} required_evidence must be a list before binding validation"]
    errors: list[str] = []
    binding_refs: list[str] = []
    required_binding_fields = {
        "evidence_ref",
        "purpose",
        "source_refs",
        "validator_refs",
        "proof_surface_refs",
        "read_only",
        "terminal_closure",
    }
    for binding_index, binding in enumerate(evidence_bindings):
        if not isinstance(binding, dict):
            errors.append(f"loop {index} evidence binding {binding_index} must be an object")
            continue
        missing = sorted(required_binding_fields - set(binding))
        errors.extend(
            f"loop {index} evidence binding {binding_index} missing field: {field_name}"
            for field_name in missing
        )
        extra = sorted(set(binding) - required_binding_fields)
        errors.extend(
            f"loop {index} evidence binding {binding_index} has unexpected field: {field_name}"
            for field_name in extra
        )
        if missing:
            continue
        evidence_ref = binding["evidence_ref"]
        if not isinstance(evidence_ref, str) or not evidence_ref:
            errors.append(f"loop {index} evidence binding {binding_index} evidence_ref must be non-empty")
        else:
            binding_refs.append(evidence_ref)
        if not isinstance(binding["purpose"], str) or not binding["purpose"]:
            errors.append(f"loop {index} evidence binding {binding_index} purpose must be non-empty")
        for field_name in ("source_refs", "validator_refs", "proof_surface_refs"):
            errors.extend(
                _validate_text_list(
                    binding[field_name],
                    f"loop {index} evidence binding {binding_index} {field_name}",
                )
            )
        if binding["read_only"] is not True:
            errors.append(f"loop {index} evidence binding {binding_index} read_only must be true")
        if binding["terminal_closure"] is not False:
            errors.append(
                f"loop {index} evidence binding {binding_index} terminal_closure must be false"
            )
    duplicate_refs = sorted({ref for ref in binding_refs if binding_refs.count(ref) > 1})
    errors.extend(f"loop {index} duplicate evidence binding: {ref}" for ref in duplicate_refs)
    required_refs = set(required_evidence)
    binding_ref_set = set(binding_refs)
    for evidence_name in sorted(required_refs - binding_ref_set):
        errors.append(f"loop {index} missing evidence binding: {evidence_name}")
    for evidence_name in sorted(binding_ref_set - required_refs):
        errors.append(f"loop {index} unexpected evidence binding: {evidence_name}")
    return errors


def _validate_text_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list):
        return [f"{label} must be a list"]
    errors: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item:
            errors.append(f"{label} must contain only non-empty strings")
            break
    return errors


def _validate_mode_list(value: Any, label: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, list):
        return [f"{label} must be a list"]
    if not value:
        errors.append(f"{label} must be non-empty")
    valid_modes = set(LOOP_MODES)
    for item in value:
        if item not in valid_modes:
            errors.append(f"{label} item is invalid: {item!r}")
    return errors


def main(argv: list[str] | None = None) -> int:
    """Validate the holistic loop read-model report contract."""

    parser = argparse.ArgumentParser(description="Validate holistic loop read-model report.")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH, help="schema JSON path")
    args = parser.parse_args(argv)

    try:
        errors = validate_contract(args.schema)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"[BLOCKED] load-holistic-loop-contract: {exc}\n")
        sys.stderr.write("STATUS: blocked\n")
        return 1

    if errors:
        for error in errors:
            sys.stderr.write(f"[BLOCKED] holistic-loop-contract: {error}\n")
        sys.stderr.write("STATUS: blocked\n")
        return 1

    sys.stdout.write("[PASS] holistic_loop_read_model_schema\n")
    sys.stdout.write("[PASS] holistic_loop_read_model_current_output\n")
    sys.stdout.write("STATUS: passed\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
