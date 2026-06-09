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
        "required_evidence",
        "missing_evidence",
        "open_blockers",
        "closure_conditions",
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
    if not loop.get("closure_conditions"):
        errors.append(f"loop {index} must expose closure conditions")
    if not loop.get("required_evidence"):
        errors.append(f"loop {index} must expose required evidence")
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
