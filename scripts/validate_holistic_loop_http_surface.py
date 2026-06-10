#!/usr/bin/env python3
"""Validate holistic loop read-model HTTP exposure.

Purpose: prove the default HTTP app exposes the holistic loop registry as a
read-only bounded read model.
Governance scope: route method boundary, blocker preservation, non-terminal
closure fields, and bounded request handling.
Dependencies: FastAPI TestClient, MCOI default router mounting, and holistic
loop router.
Invariants:
  - The loop read-model route has no mutation companion.
  - Missing evidence is reported as blockers.
  - The endpoint is not a terminal closure certificate.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
MCOI_ROOT = WORKSPACE_ROOT / "mcoi"
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))
if str(MCOI_ROOT) not in sys.path:
    sys.path.insert(0, str(MCOI_ROOT))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from mcoi_runtime.app.server_http import include_default_routers  # noqa: E402


LOOP_READ_MODEL_PATH = "/api/v1/loops/read-model"
ALLOWED_METHODS = frozenset({"GET", "HEAD"})
MUTATION_METHODS = ("POST", "PUT", "PATCH", "DELETE")
LOOP_MODES = ("real", "dry_run", "shadow", "simulation", "replay")
REQUIRED_PAYLOAD_FIELDS = (
    "read_model_id",
    "read_model_version",
    "generated_at",
    "status",
    "loops",
    "total_count",
    "returned_count",
    "blocked_count",
    "verified_count",
    "truncated",
    "governed",
    "read_only",
    "report_is_not_terminal_closure",
    "terminal_closure_required",
)


def build_default_app() -> FastAPI:
    """Build the default app router set for HTTP surface validation."""

    app = FastAPI()
    include_default_routers(app)
    return app


def validate_route_methods(app: FastAPI) -> list[str]:
    """Validate that the loop read-model route is read-only."""

    methods: set[str] = set()
    for route in app.routes:
        if getattr(route, "path", "") == LOOP_READ_MODEL_PATH:
            methods.update(str(method) for method in getattr(route, "methods", set()))
    errors: list[str] = []
    if "GET" not in methods:
        errors.append("loop read-model route is missing GET")
    mutation_methods = sorted(method for method in methods if method not in ALLOWED_METHODS)
    if mutation_methods:
        errors.append(f"loop read-model route exposes mutation methods: {mutation_methods}")
    return errors


def validate_payload(payload: dict[str, Any]) -> list[str]:
    """Validate one loop read-model HTTP payload."""

    errors: list[str] = []
    missing_fields = [field_name for field_name in REQUIRED_PAYLOAD_FIELDS if field_name not in payload]
    errors.extend(f"payload missing field: {field_name}" for field_name in missing_fields)
    if missing_fields:
        return errors
    if payload["read_model_id"] != "holistic_loop_read_model":
        errors.append("read_model_id is invalid")
    if payload["read_model_version"] != "holistic_loop_kernel.v1":
        errors.append("read_model_version is invalid")
    if payload["governed"] is not True:
        errors.append("governed must be true")
    if payload["read_only"] is not True:
        errors.append("read_only must be true")
    if payload["report_is_not_terminal_closure"] is not True:
        errors.append("report_is_not_terminal_closure must be true")
    if payload["terminal_closure_required"] is not True:
        errors.append("terminal_closure_required must be true")
    loops = payload["loops"]
    if not isinstance(loops, list):
        errors.append("loops must be a list")
        return errors
    blocked_count = sum(1 for loop in loops if isinstance(loop, dict) and bool(loop.get("open_blockers")))
    verified_count = sum(1 for loop in loops if isinstance(loop, dict) and loop.get("status") == "verified")
    expected_status = "blocked" if blocked_count else "verified"
    if payload["returned_count"] != len(loops):
        errors.append("returned_count does not match loop count")
    if payload["blocked_count"] != blocked_count:
        errors.append("blocked_count does not match loop blockers")
    if payload["verified_count"] != verified_count:
        errors.append("verified_count does not match verified loops")
    if payload["status"] != expected_status:
        errors.append(f"status must be {expected_status} for observed blockers")
    for index, loop in enumerate(loops):
        errors.extend(_validate_loop_payload(loop, index))
    return errors


def validate_http_surface(app: FastAPI | None = None) -> list[str]:
    """Validate default HTTP route methods, payload, and mutation rejection."""

    surface_app = app or build_default_app()
    client = TestClient(surface_app)
    errors = validate_route_methods(surface_app)
    response = client.get(LOOP_READ_MODEL_PATH, params={"limit": 4})
    if response.status_code != 200:
        errors.append(f"GET loop read-model returned status {response.status_code}")
        return errors
    try:
        payload = response.json()
    except json.JSONDecodeError as exc:
        errors.append(f"GET loop read-model did not return JSON: {type(exc).__name__}")
        return errors
    if not isinstance(payload, dict):
        errors.append("GET loop read-model payload must be an object")
        return errors
    errors.extend(validate_payload(payload))
    limited_response = client.get(LOOP_READ_MODEL_PATH, params={"limit": 2})
    if limited_response.status_code != 200:
        errors.append(f"bounded GET loop read-model returned status {limited_response.status_code}")
    else:
        limited_payload = limited_response.json()
        if limited_payload.get("returned_count") != 2 or limited_payload.get("truncated") is not True:
            errors.append("bounded GET loop read-model did not truncate at limit")
    invalid_response = client.get(LOOP_READ_MODEL_PATH, params={"limit": 0})
    if invalid_response.status_code >= 500:
        errors.append("invalid limit produced server error")
    for method_name in MUTATION_METHODS:
        method = getattr(client, method_name.lower())
        mutation_response = method(LOOP_READ_MODEL_PATH)
        if mutation_response.status_code != 405:
            errors.append(f"{method_name} loop read-model must return 405")
    return errors


def _validate_loop_payload(loop: Any, index: int) -> list[str]:
    if not isinstance(loop, dict):
        return [f"loop {index} must be an object"]
    errors: list[str] = []
    for field_name in (
        "loop_id",
        "status",
        "status_binding",
        "transition_bindings",
        "mode",
        "mode_binding",
        "risk_class",
        "risk_binding",
        "required_authority",
        "authority_bindings",
        "missing_authority",
        "required_evidence",
        "evidence_bindings",
        "step_receipts",
        "receipt_lineage_bindings",
        "missing_evidence",
        "open_blockers",
        "closure_conditions",
        "closure_condition_bindings",
        "closure_report",
        "rollback_policy",
        "rollback_binding",
        "learning_policy",
        "learning_binding",
    ):
        if field_name not in loop:
            errors.append(f"loop {index} missing field: {field_name}")
    if errors:
        return errors
    if loop.get("missing_evidence") and loop.get("status") != "blocked":
        errors.append(f"loop {index} with missing evidence must be blocked")
    for evidence_name in loop.get("missing_evidence", ()):
        expected_blocker = f"missing_evidence:{evidence_name}"
        if expected_blocker not in loop.get("open_blockers", ()):
            errors.append(f"loop {index} missing evidence lacks blocker: {evidence_name}")
    for authority_name in loop.get("missing_authority", ()):
        expected_blocker = f"missing_authority:{authority_name}"
        if expected_blocker not in loop.get("open_blockers", ()):
            errors.append(f"loop {index} missing authority lacks blocker: {authority_name}")
    if not loop.get("closure_conditions"):
        errors.append(f"loop {index} must expose closure conditions")
    if not loop.get("required_authority"):
        errors.append(f"loop {index} must expose required authority")
    if not loop.get("required_evidence"):
        errors.append(f"loop {index} must expose required evidence")
    if loop.get("mode") not in LOOP_MODES:
        errors.append(f"loop {index} mode is invalid")
    errors.extend(_validate_status_binding(loop.get("status_binding"), loop, index))
    errors.extend(_validate_transition_bindings(loop.get("transition_bindings"), loop, index))
    errors.extend(_validate_mode_binding(loop.get("mode_binding"), loop, index))
    errors.extend(_validate_risk_binding(loop.get("risk_binding"), loop, index))
    errors.extend(_validate_closure_report(loop.get("closure_report"), loop, index))
    errors.extend(
        _validate_authority_bindings(
            loop.get("authority_bindings"),
            loop.get("required_authority"),
            index,
        )
    )
    errors.extend(
        _validate_evidence_bindings(
            loop.get("evidence_bindings"),
            loop.get("required_evidence"),
            index,
        )
    )
    errors.extend(_validate_closure_condition_bindings(loop.get("closure_condition_bindings"), loop, index))
    errors.extend(_validate_rollback_binding(loop.get("rollback_binding"), loop, index))
    errors.extend(_validate_learning_binding(loop.get("learning_binding"), loop, index))
    errors.extend(_validate_step_receipts(loop.get("step_receipts"), loop, index))
    errors.extend(_validate_receipt_lineage_bindings(loop.get("receipt_lineage_bindings"), loop, index))
    return errors


def _validate_status_binding(status_binding: Any, loop: dict[str, Any], index: int) -> list[str]:
    if not isinstance(status_binding, dict):
        return [f"loop {index} status_binding must be an object"]
    errors: list[str] = []
    if status_binding.get("projected_status") != loop.get("status"):
        errors.append(f"loop {index} status_binding projected_status must match status")
    if not isinstance(status_binding.get("status_reason"), str) or not status_binding.get("status_reason"):
        errors.append(f"loop {index} status_binding status_reason must be non-empty")
    blocker_refs = status_binding.get("blocker_refs")
    if not isinstance(blocker_refs, list):
        errors.append(f"loop {index} status_binding blocker_refs must be a list")
    elif set(blocker_refs) != set(loop.get("open_blockers", ())):
        errors.append(f"loop {index} status_binding blocker_refs must match open blockers")
    if loop.get("status") in {"verified", "closed"} and blocker_refs:
        errors.append(f"loop {index} verified or closed status_binding cannot carry blockers")
    for field_name in (
        "verification_refs",
        "closure_gate_refs",
        "source_refs",
        "validator_refs",
        "proof_surface_refs",
    ):
        refs = status_binding.get(field_name)
        if not isinstance(refs, list) or not refs or not all(isinstance(ref, str) and ref for ref in refs):
            errors.append(f"loop {index} status_binding {field_name} must be non-empty")
    if status_binding.get("read_only") is not True:
        errors.append(f"loop {index} status_binding read_only must be true")
    if status_binding.get("status_transition") is not False:
        errors.append(f"loop {index} status_binding status_transition must be false")
    if status_binding.get("terminal_closure") is not False:
        errors.append(f"loop {index} status_binding terminal_closure must be false")
    return errors


def _validate_transition_bindings(transition_bindings: Any, loop: dict[str, Any], index: int) -> list[str]:
    if not isinstance(transition_bindings, list):
        return [f"loop {index} transition_bindings must be a list"]
    if not transition_bindings:
        return [f"loop {index} transition_bindings must not be empty"]
    errors: list[str] = []
    transition_refs: list[str] = []
    required_authority = set(loop.get("required_authority", ()))
    required_evidence = set(loop.get("required_evidence", ()))
    for binding_index, binding in enumerate(transition_bindings):
        if not isinstance(binding, dict):
            errors.append(f"loop {index} transition binding {binding_index} must be an object")
            continue
        transition_ref = binding.get("transition_ref")
        if not isinstance(transition_ref, str) or not transition_ref:
            errors.append(f"loop {index} transition binding {binding_index} transition_ref must be non-empty")
        else:
            transition_refs.append(transition_ref)
        if binding.get("from_status") not in {"open", "blocked", "verified", "closed"}:
            errors.append(f"loop {index} transition binding {binding_index} from_status is invalid")
        if binding.get("to_status") not in {"open", "blocked", "verified", "closed"}:
            errors.append(f"loop {index} transition binding {binding_index} to_status is invalid")
        if not isinstance(binding.get("from_step"), str) or not binding.get("from_step"):
            errors.append(f"loop {index} transition binding {binding_index} from_step must be non-empty")
        if not isinstance(binding.get("to_step"), str) or not binding.get("to_step"):
            errors.append(f"loop {index} transition binding {binding_index} to_step must be non-empty")
        for field_name in (
            "required_authority_refs",
            "required_evidence_refs",
            "receipt_refs",
            "rollback_refs",
            "source_refs",
            "validator_refs",
            "proof_surface_refs",
        ):
            refs = binding.get(field_name)
            if not isinstance(refs, list) or not refs or not all(isinstance(ref, str) and ref for ref in refs):
                errors.append(f"loop {index} transition binding {binding_index} {field_name} must be non-empty")
        blocker_refs = binding.get("blocker_refs")
        if not isinstance(blocker_refs, list):
            errors.append(f"loop {index} transition binding {binding_index} blocker_refs must be a list")
        elif set(blocker_refs) != set(loop.get("open_blockers", ())):
            errors.append(f"loop {index} transition binding {binding_index} blocker_refs must match open blockers")
        for authority_ref in binding.get("required_authority_refs", ()) if isinstance(binding.get("required_authority_refs"), list) else ():
            if authority_ref not in required_authority:
                errors.append(
                    f"loop {index} transition binding {binding_index} unexpected authority ref: {authority_ref}"
                )
        for evidence_ref in binding.get("required_evidence_refs", ()) if isinstance(binding.get("required_evidence_refs"), list) else ():
            if evidence_ref not in required_evidence:
                errors.append(
                    f"loop {index} transition binding {binding_index} unexpected evidence ref: {evidence_ref}"
                )
        rollback_refs = binding.get("rollback_refs")
        if isinstance(rollback_refs, list) and loop.get("rollback_policy") not in rollback_refs:
            errors.append(f"loop {index} transition binding {binding_index} rollback_refs must include rollback_policy")
        if binding.get("read_only") is not True:
            errors.append(f"loop {index} transition binding {binding_index} read_only must be true")
        if binding.get("executes_transition") is not False:
            errors.append(f"loop {index} transition binding {binding_index} executes_transition must be false")
        if binding.get("terminal_closure") is not False:
            errors.append(f"loop {index} transition binding {binding_index} terminal_closure must be false")
    if len(transition_refs) != len(set(transition_refs)):
        errors.append(f"loop {index} transition bindings must not contain duplicates")
    return errors


def _validate_mode_binding(mode_binding: Any, loop: dict[str, Any], index: int) -> list[str]:
    if not isinstance(mode_binding, dict):
        return [f"loop {index} mode_binding must be an object"]
    errors: list[str] = []
    if mode_binding.get("projected_mode") != loop.get("mode"):
        errors.append(f"loop {index} mode_binding projected_mode must match mode")
    allowed_modes = mode_binding.get("allowed_modes")
    if not isinstance(allowed_modes, list) or not allowed_modes:
        errors.append(f"loop {index} mode_binding allowed_modes must be non-empty")
    else:
        if mode_binding.get("projected_mode") not in allowed_modes:
            errors.append(f"loop {index} mode_binding projected_mode must be allowed")
        for mode in allowed_modes:
            if mode not in LOOP_MODES:
                errors.append(f"loop {index} mode_binding allowed_modes item is invalid: {mode!r}")
    for field_name in (
        "separation_refs",
        "real_execution_guard_refs",
        "source_refs",
        "validator_refs",
        "proof_surface_refs",
    ):
        refs = mode_binding.get(field_name)
        if not isinstance(refs, list) or not refs or not all(isinstance(ref, str) and ref for ref in refs):
            errors.append(f"loop {index} mode_binding {field_name} must be non-empty")
    if mode_binding.get("read_only") is not True:
        errors.append(f"loop {index} mode_binding read_only must be true")
    if mode_binding.get("mode_transition") is not False:
        errors.append(f"loop {index} mode_binding mode_transition must be false")
    if mode_binding.get("terminal_closure") is not False:
        errors.append(f"loop {index} mode_binding terminal_closure must be false")
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
    closure_conditions = set(loop.get("closure_conditions", ()))
    required_evidence = set(loop.get("required_evidence", ()))
    required_authority = set(loop.get("required_authority", ()))
    for binding_index, binding in enumerate(closure_condition_bindings):
        if not isinstance(binding, dict):
            errors.append(f"loop {index} closure condition binding {binding_index} must be an object")
            continue
        closure_ref = binding.get("closure_ref")
        if not isinstance(closure_ref, str) or not closure_ref:
            errors.append(f"loop {index} closure condition binding {binding_index} closure_ref must be non-empty")
        else:
            binding_refs.append(closure_ref)
        for field_name in (
            "required_evidence_refs",
            "required_authority_refs",
            "source_refs",
            "validator_refs",
            "proof_surface_refs",
        ):
            refs = binding.get(field_name)
            if not isinstance(refs, list) or not refs or not all(isinstance(ref, str) and ref for ref in refs):
                errors.append(f"loop {index} closure condition binding {binding_index} {field_name} must be non-empty")
        for evidence_ref in binding.get("required_evidence_refs", ()) if isinstance(binding.get("required_evidence_refs"), list) else ():
            if evidence_ref not in required_evidence:
                errors.append(
                    f"loop {index} closure condition binding {binding_index} unexpected evidence ref: {evidence_ref}"
                )
        for authority_ref in binding.get("required_authority_refs", ()) if isinstance(binding.get("required_authority_refs"), list) else ():
            if authority_ref not in required_authority:
                errors.append(
                    f"loop {index} closure condition binding {binding_index} unexpected authority ref: {authority_ref}"
                )
        if binding.get("read_only") is not True:
            errors.append(f"loop {index} closure condition binding {binding_index} read_only must be true")
        if binding.get("terminal_closure") is not False:
            errors.append(f"loop {index} closure condition binding {binding_index} terminal_closure must be false")
    duplicate_refs = sorted({ref for ref in binding_refs if binding_refs.count(ref) > 1})
    errors.extend(f"loop {index} duplicate closure condition binding: {ref}" for ref in duplicate_refs)
    binding_ref_set = set(binding_refs)
    for closure_ref in sorted(closure_conditions - binding_ref_set):
        errors.append(f"loop {index} missing closure condition binding: {closure_ref}")
    for closure_ref in sorted(binding_ref_set - closure_conditions):
        errors.append(f"loop {index} unexpected closure condition binding: {closure_ref}")
    return errors


def _validate_learning_binding(learning_binding: Any, loop: dict[str, Any], index: int) -> list[str]:
    if not isinstance(learning_binding, dict):
        return [f"loop {index} learning_binding must be an object"]
    errors: list[str] = []
    if learning_binding.get("learning_ref") != loop.get("learning_policy"):
        errors.append(f"loop {index} learning_binding learning_ref must match learning_policy")
    for field_name in (
        "evidence_input_refs",
        "admission_refs",
        "retention_refs",
        "source_refs",
        "validator_refs",
        "proof_surface_refs",
    ):
        refs = learning_binding.get(field_name)
        if not isinstance(refs, list) or not refs or not all(isinstance(ref, str) and ref for ref in refs):
            errors.append(f"loop {index} learning_binding {field_name} must be non-empty")
    if learning_binding.get("read_only") is not True:
        errors.append(f"loop {index} learning_binding read_only must be true")
    if learning_binding.get("terminal_closure") is not False:
        errors.append(f"loop {index} learning_binding terminal_closure must be false")
    return errors


def _validate_risk_binding(risk_binding: Any, loop: dict[str, Any], index: int) -> list[str]:
    if not isinstance(risk_binding, dict):
        return [f"loop {index} risk_binding must be an object"]
    errors: list[str] = []
    if risk_binding.get("risk_ref") != loop.get("risk_class"):
        errors.append(f"loop {index} risk_binding risk_ref must match risk_class")
    for field_name in (
        "hazard_refs",
        "mitigation_refs",
        "monitor_refs",
        "source_refs",
        "validator_refs",
        "proof_surface_refs",
    ):
        refs = risk_binding.get(field_name)
        if not isinstance(refs, list) or not refs or not all(isinstance(ref, str) and ref for ref in refs):
            errors.append(f"loop {index} risk_binding {field_name} must be non-empty")
    if risk_binding.get("read_only") is not True:
        errors.append(f"loop {index} risk_binding read_only must be true")
    if risk_binding.get("terminal_closure") is not False:
        errors.append(f"loop {index} risk_binding terminal_closure must be false")
    return errors


def _validate_rollback_binding(rollback_binding: Any, loop: dict[str, Any], index: int) -> list[str]:
    if not isinstance(rollback_binding, dict):
        return [f"loop {index} rollback_binding must be an object"]
    errors: list[str] = []
    if rollback_binding.get("rollback_ref") != loop.get("rollback_policy"):
        errors.append(f"loop {index} rollback_binding rollback_ref must match rollback_policy")
    for field_name in ("source_refs", "validator_refs", "proof_surface_refs"):
        refs = rollback_binding.get(field_name)
        if not isinstance(refs, list) or not refs or not all(isinstance(ref, str) and ref for ref in refs):
            errors.append(f"loop {index} rollback_binding {field_name} must be non-empty")
    if rollback_binding.get("read_only") is not True:
        errors.append(f"loop {index} rollback_binding read_only must be true")
    if rollback_binding.get("terminal_closure") is not False:
        errors.append(f"loop {index} rollback_binding terminal_closure must be false")
    return errors


def _validate_authority_bindings(authority_bindings: Any, required_authority: Any, index: int) -> list[str]:
    if not isinstance(authority_bindings, list):
        return [f"loop {index} authority_bindings must be a list"]
    if not isinstance(required_authority, list):
        return [f"loop {index} required_authority must be a list before binding validation"]
    errors: list[str] = []
    binding_refs: list[str] = []
    for binding_index, binding in enumerate(authority_bindings):
        if not isinstance(binding, dict):
            errors.append(f"loop {index} authority binding {binding_index} must be an object")
            continue
        authority_ref = binding.get("authority_ref")
        if not isinstance(authority_ref, str) or not authority_ref:
            errors.append(f"loop {index} authority binding {binding_index} authority_ref must be non-empty")
        else:
            binding_refs.append(authority_ref)
        for field_name in ("source_refs", "validator_refs", "proof_surface_refs"):
            refs = binding.get(field_name)
            if not isinstance(refs, list) or not refs or not all(isinstance(ref, str) and ref for ref in refs):
                errors.append(f"loop {index} authority binding {binding_index} {field_name} must be non-empty")
        if binding.get("read_only") is not True:
            errors.append(f"loop {index} authority binding {binding_index} read_only must be true")
        if binding.get("terminal_closure") is not False:
            errors.append(f"loop {index} authority binding {binding_index} terminal_closure must be false")
    required_refs = set(required_authority)
    binding_ref_set = set(binding_refs)
    for authority_name in sorted(required_refs - binding_ref_set):
        errors.append(f"loop {index} missing authority binding: {authority_name}")
    for authority_name in sorted(binding_ref_set - required_refs):
        errors.append(f"loop {index} unexpected authority binding: {authority_name}")
    if len(binding_refs) != len(binding_ref_set):
        errors.append(f"loop {index} authority bindings must not contain duplicates")
    return errors


def _validate_step_receipts(step_receipts: Any, loop: dict[str, Any], index: int) -> list[str]:
    if not isinstance(step_receipts, list):
        return [f"loop {index} step_receipts must be a list"]
    if not step_receipts:
        return [f"loop {index} step_receipts must not be empty"]
    errors: list[str] = []
    seen_steps: list[str] = []
    for receipt_index, receipt in enumerate(step_receipts):
        if not isinstance(receipt, dict):
            errors.append(f"loop {index} step receipt {receipt_index} must be an object")
            continue
        if receipt.get("loop_id") != loop.get("loop_id"):
            errors.append(f"loop {index} step receipt {receipt_index} loop_id must match loop_id")
        step = receipt.get("step")
        if not isinstance(step, str) or not step:
            errors.append(f"loop {index} step receipt {receipt_index} step must be non-empty")
        else:
            seen_steps.append(step)
        for field_name in ("input_hash", "output_hash"):
            value = receipt.get(field_name)
            if (
                not isinstance(value, str)
                or len(value) != 71
                or not value.startswith("sha256:")
            ):
                errors.append(
                    f"loop {index} step receipt {receipt_index} {field_name} must be sha256"
                )
        if not isinstance(receipt.get("decision"), str) or not receipt.get("decision"):
            errors.append(f"loop {index} step receipt {receipt_index} decision must be non-empty")
        evidence_refs = receipt.get("evidence_refs")
        if not isinstance(evidence_refs, list):
            errors.append(f"loop {index} step receipt {receipt_index} evidence_refs must be a list")
        if receipt.get("status") not in {"open", "blocked", "verified"}:
            errors.append(f"loop {index} step receipt {receipt_index} status is invalid")
        errors_field = receipt.get("errors")
        if not isinstance(errors_field, list):
            errors.append(f"loop {index} step receipt {receipt_index} errors must be a list")
        elif set(errors_field) != set(loop.get("open_blockers", ())):
            errors.append(f"loop {index} step receipt {receipt_index} errors must match open blockers")
        metadata = receipt.get("metadata")
        if not isinstance(metadata, dict):
            errors.append(f"loop {index} step receipt {receipt_index} metadata must be an object")
            continue
        if metadata.get("read_only") is not True:
            errors.append(f"loop {index} step receipt {receipt_index} read_only must be true")
        if metadata.get("synthetic_projection") is not True:
            errors.append(f"loop {index} step receipt {receipt_index} synthetic_projection must be true")
        if metadata.get("terminal_closure") is not False:
            errors.append(f"loop {index} step receipt {receipt_index} terminal_closure must be false")
        if metadata.get("behavior_rewrite") is not False:
            errors.append(f"loop {index} step receipt {receipt_index} behavior_rewrite must be false")
    if len(seen_steps) != len(set(seen_steps)):
        errors.append(f"loop {index} step receipts must not contain duplicates")
    return errors


def _validate_receipt_lineage_bindings(lineage_bindings: Any, loop: dict[str, Any], index: int) -> list[str]:
    if not isinstance(lineage_bindings, list):
        return [f"loop {index} receipt_lineage_bindings must be a list"]
    if not lineage_bindings:
        return [f"loop {index} receipt_lineage_bindings must not be empty"]
    errors: list[str] = []
    lineage_refs: list[str] = []
    lineage_steps: list[str] = []
    step_receipts = {
        receipt.get("step"): receipt
        for receipt in loop.get("step_receipts", [])
        if isinstance(receipt, dict)
    }
    required_evidence = set(loop.get("required_evidence", ()))
    for binding_index, binding in enumerate(lineage_bindings):
        if not isinstance(binding, dict):
            errors.append(f"loop {index} receipt lineage binding {binding_index} must be an object")
            continue
        lineage_ref = binding.get("lineage_ref")
        if not isinstance(lineage_ref, str) or not lineage_ref:
            errors.append(f"loop {index} receipt lineage binding {binding_index} lineage_ref must be non-empty")
        else:
            lineage_refs.append(lineage_ref)
        step = binding.get("step")
        if not isinstance(step, str) or not step:
            errors.append(f"loop {index} receipt lineage binding {binding_index} step must be non-empty")
        else:
            lineage_steps.append(step)
            receipt = step_receipts.get(step)
            if receipt is None:
                errors.append(f"loop {index} receipt lineage binding {binding_index} step lacks receipt")
            elif binding.get("receipt_hash") != receipt.get("output_hash"):
                errors.append(
                    f"loop {index} receipt lineage binding {binding_index} receipt_hash must match step receipt"
                )
        receipt_ref = binding.get("receipt_ref")
        if not isinstance(receipt_ref, str) or not receipt_ref:
            errors.append(f"loop {index} receipt lineage binding {binding_index} receipt_ref must be non-empty")
        receipt_hash = binding.get("receipt_hash")
        if (
            not isinstance(receipt_hash, str)
            or len(receipt_hash) != 71
            or not receipt_hash.startswith("sha256:")
        ):
            errors.append(f"loop {index} receipt lineage binding {binding_index} receipt_hash must be sha256")
        for field_name in (
            "required_evidence_refs",
            "source_receipt_refs",
            "source_refs",
            "validator_refs",
            "proof_surface_refs",
        ):
            refs = binding.get(field_name)
            if not isinstance(refs, list) or not refs or not all(isinstance(ref, str) and ref for ref in refs):
                errors.append(f"loop {index} receipt lineage binding {binding_index} {field_name} must be non-empty")
        observed_refs = binding.get("observed_evidence_refs")
        if not isinstance(observed_refs, list):
            errors.append(f"loop {index} receipt lineage binding {binding_index} observed_evidence_refs must be a list")
        elif set(observed_refs) != set(loop.get("evidence_refs", ())):
            errors.append(
                f"loop {index} receipt lineage binding {binding_index} observed_evidence_refs must match evidence_refs"
            )
        blocker_refs = binding.get("blocker_refs")
        if not isinstance(blocker_refs, list):
            errors.append(f"loop {index} receipt lineage binding {binding_index} blocker_refs must be a list")
        elif set(blocker_refs) != set(loop.get("open_blockers", ())):
            errors.append(f"loop {index} receipt lineage binding {binding_index} blocker_refs must match open blockers")
        for evidence_ref in binding.get("required_evidence_refs", ()) if isinstance(binding.get("required_evidence_refs"), list) else ():
            if evidence_ref not in required_evidence:
                errors.append(
                    f"loop {index} receipt lineage binding {binding_index} unexpected evidence ref: {evidence_ref}"
                )
        source_receipt_refs = binding.get("source_receipt_refs")
        if isinstance(source_receipt_refs, list) and receipt_ref not in source_receipt_refs:
            errors.append(
                f"loop {index} receipt lineage binding {binding_index} source_receipt_refs must include receipt_ref"
            )
        if binding.get("read_only") is not True:
            errors.append(f"loop {index} receipt lineage binding {binding_index} read_only must be true")
        if binding.get("emits_receipt") is not False:
            errors.append(f"loop {index} receipt lineage binding {binding_index} emits_receipt must be false")
        if binding.get("terminal_closure") is not False:
            errors.append(f"loop {index} receipt lineage binding {binding_index} terminal_closure must be false")
    if len(lineage_refs) != len(set(lineage_refs)):
        errors.append(f"loop {index} receipt lineage bindings must not contain duplicates")
    if set(lineage_steps) != set(step_receipts):
        errors.append(f"loop {index} receipt lineage bindings must cover step receipts exactly")
    return errors


def _validate_closure_report(closure_report: Any, loop: dict[str, Any], index: int) -> list[str]:
    if not isinstance(closure_report, dict):
        return [f"loop {index} closure_report must be an object"]
    errors: list[str] = []
    if closure_report.get("loop_id") != loop.get("loop_id"):
        errors.append(f"loop {index} closure_report loop_id must match loop_id")
    if closure_report.get("closed") is not False:
        errors.append(f"loop {index} closure_report closed must be false")
    expected_evidence_complete = not bool(loop.get("missing_evidence"))
    if closure_report.get("evidence_complete") is not expected_evidence_complete:
        errors.append(f"loop {index} closure_report evidence_complete does not match missing evidence")
    unresolved_gaps = closure_report.get("unresolved_gaps")
    if not isinstance(unresolved_gaps, list):
        errors.append(f"loop {index} closure_report unresolved_gaps must be a list")
    elif set(unresolved_gaps) != set(loop.get("open_blockers", ())):
        errors.append(f"loop {index} closure_report unresolved_gaps must match open blockers")
    if not isinstance(closure_report.get("rollback_available"), bool):
        errors.append(f"loop {index} closure_report rollback_available must be boolean")
    metadata = closure_report.get("metadata")
    if not isinstance(metadata, dict):
        errors.append(f"loop {index} closure_report metadata must be an object")
        return errors
    if metadata.get("read_only") is not True:
        errors.append(f"loop {index} closure_report metadata read_only must be true")
    if metadata.get("terminal_closure") is not False:
        errors.append(f"loop {index} closure_report metadata terminal_closure must be false")
    closure_conditions = metadata.get("closure_conditions")
    if not isinstance(closure_conditions, list) or not closure_conditions:
        errors.append(f"loop {index} closure_report metadata closure_conditions must be non-empty")
    return errors


def _validate_evidence_bindings(evidence_bindings: Any, required_evidence: Any, index: int) -> list[str]:
    if not isinstance(evidence_bindings, list):
        return [f"loop {index} evidence_bindings must be a list"]
    if not isinstance(required_evidence, list):
        return [f"loop {index} required_evidence must be a list before binding validation"]
    errors: list[str] = []
    binding_refs: list[str] = []
    for binding_index, binding in enumerate(evidence_bindings):
        if not isinstance(binding, dict):
            errors.append(f"loop {index} evidence binding {binding_index} must be an object")
            continue
        evidence_ref = binding.get("evidence_ref")
        if not isinstance(evidence_ref, str) or not evidence_ref:
            errors.append(f"loop {index} evidence binding {binding_index} evidence_ref must be non-empty")
        else:
            binding_refs.append(evidence_ref)
        for field_name in ("source_refs", "validator_refs", "proof_surface_refs"):
            refs = binding.get(field_name)
            if not isinstance(refs, list) or not refs or not all(isinstance(ref, str) and ref for ref in refs):
                errors.append(f"loop {index} evidence binding {binding_index} {field_name} must be non-empty")
        if binding.get("read_only") is not True:
            errors.append(f"loop {index} evidence binding {binding_index} read_only must be true")
        if binding.get("terminal_closure") is not False:
            errors.append(f"loop {index} evidence binding {binding_index} terminal_closure must be false")
    required_refs = set(required_evidence)
    binding_ref_set = set(binding_refs)
    for evidence_name in sorted(required_refs - binding_ref_set):
        errors.append(f"loop {index} missing evidence binding: {evidence_name}")
    for evidence_name in sorted(binding_ref_set - required_refs):
        errors.append(f"loop {index} unexpected evidence binding: {evidence_name}")
    if len(binding_refs) != len(binding_ref_set):
        errors.append(f"loop {index} evidence bindings must not contain duplicates")
    return errors


def main(argv: list[str] | None = None) -> int:
    """Validate holistic loop HTTP surface."""

    parser = argparse.ArgumentParser(description="Validate holistic loop read-model HTTP surface.")
    parser.add_argument("--json", action="store_true", help="emit a machine-readable validation receipt")
    args = parser.parse_args(argv)

    try:
        errors = validate_http_surface()
    except Exception as exc:  # pragma: no cover - defensive CLI boundary.
        errors = [f"load-holistic-loop-http-surface: {type(exc).__name__}"]

    report = {
        "receipt_id": "holistic_loop_http_surface_validation",
        "valid": not errors,
        "status": "passed" if not errors else "blocked",
        "route_path": LOOP_READ_MODEL_PATH,
        "receipt_is_not_terminal_closure": True,
        "terminal_closure_required": True,
        "errors": errors,
    }
    if args.json:
        sys.stdout.write(json.dumps(report, indent=2, sort_keys=True) + "\n")
        return 0 if report["valid"] else 1
    if errors:
        for error in errors:
            sys.stderr.write(f"[BLOCKED] holistic-loop-http-surface: {error}\n")
        sys.stderr.write("STATUS: blocked\n")
        return 1
    sys.stdout.write("[PASS] holistic_loop_http_route_methods\n")
    sys.stdout.write("[PASS] holistic_loop_http_read_model_payload\n")
    sys.stdout.write("[PASS] holistic_loop_http_no_mutation_methods\n")
    sys.stdout.write("STATUS: passed\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
