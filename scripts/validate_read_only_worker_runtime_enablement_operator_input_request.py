#!/usr/bin/env python3
"""Validate read-only worker runtime enablement operator input requests.

Purpose: prove runtime enablement operator input requests are schema-backed,
truthful about blocked authority, redacted, and non-executing.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/read_only_worker_runtime_enablement_operator_input_request.schema.json.
Invariants:
  - Runtime enablement remains denied.
  - Blocked requests list missing evidence and blocked actions.
  - Secret values and live execution claims are rejected.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.emit_read_only_worker_runtime_enablement_operator_input_request import (  # noqa: E402
    BLOCKED_ACTIONS,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


DEFAULT_REQUEST = (
    REPO_ROOT
    / ".change_assurance"
    / "read_only_worker_runtime_enablement_operator_input_request.json"
)
DEFAULT_SCHEMA = (
    REPO_ROOT
    / "schemas"
    / "read_only_worker_runtime_enablement_operator_input_request.schema.json"
)
DEFAULT_OUTPUT = (
    REPO_ROOT
    / ".change_assurance"
    / "read_only_worker_runtime_enablement_operator_input_request_validation.json"
)
REQUEST_ID_PATTERN = re.compile(
    r"^read-only-worker-runtime-enablement-input-request-[0-9a-f]{16}$"
)
INPUT_ID_PATTERN = re.compile(
    r"^read-only-worker-runtime-enablement-input-[0-9a-f]{12}$"
)
SECRET_VALUE_MARKERS = (
    "client_secret",
    "access_token",
    "refresh_token",
    "private_key",
    "secret-value",
    "ghp_",
    "gho_",
    "sk-",
)


@dataclass(frozen=True, slots=True)
class RuntimeEnablementOperatorInputRequestValidation:
    """Validation result for one runtime enablement operator input request."""

    valid: bool
    runtime_enablement_allowed: bool
    request_path: str
    schema_path: str
    errors: tuple[str, ...]
    next_action: str

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-ready validation result."""

        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_runtime_enablement_operator_input_request(
    *,
    request_path: Path = DEFAULT_REQUEST,
    schema_path: Path = DEFAULT_SCHEMA,
    require_blocked: bool = False,
) -> RuntimeEnablementOperatorInputRequestValidation:
    """Validate one runtime enablement operator input request."""

    errors: list[str] = []
    try:
        schema = _load_schema(schema_path)
    except OSError:
        schema = {}
        errors.append("runtime enablement operator input request schema file missing")
    request = _load_json_object(request_path, "runtime enablement operator input request", errors)
    if schema and request:
        errors.extend(_validate_schema_instance(schema, request))
        _validate_semantics(request, errors)
        if require_blocked and request.get("runtime_enablement_allowed") is not False:
            errors.append("require blocked: runtime enablement allowed")
    runtime_enablement_allowed = request.get("runtime_enablement_allowed") is True if request else False
    return RuntimeEnablementOperatorInputRequestValidation(
        valid=not errors,
        runtime_enablement_allowed=runtime_enablement_allowed,
        request_path=_path_label(request_path),
        schema_path=_path_label(schema_path),
        errors=tuple(errors),
        next_action=_next_action(request) if request else "emit runtime enablement operator input request",
    )


def write_runtime_enablement_operator_input_request_validation(
    validation: RuntimeEnablementOperatorInputRequestValidation,
    output_path: Path,
) -> Path:
    """Write one runtime enablement operator input request validation receipt."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_semantics(request: dict[str, Any], errors: list[str]) -> None:
    serialized = json.dumps(request, sort_keys=True)
    for marker in SECRET_VALUE_MARKERS:
        if marker.lower() in serialized.lower():
            errors.append(f"request must not serialize secret marker: {marker}")

    if not REQUEST_ID_PATTERN.fullmatch(str(request.get("request_id", ""))):
        errors.append("request_id must match runtime enablement input request pattern")

    expected_false_fields = (
        "runtime_enablement_allowed",
        "runtime_enablement_executed",
        "runtime_dispatch_performed",
        "worker_invocation_performed",
        "runtime_receipt_emitted",
        "receipt_append_performed",
        "terminal_closure_performed",
    )
    for field_name in expected_false_fields:
        if request.get(field_name) is not False:
            errors.append(f"{field_name} must be false")
    if request.get("ready") is not False:
        errors.append("ready must be false for operator input requests")
    if request.get("no_secret_values_serialized") is not True:
        errors.append("no_secret_values_serialized must be true")

    witness_validation_ok = request.get("witness_validation_ok") is True
    expected_solver_outcome = "AwaitingEvidence" if witness_validation_ok else "GovernanceBlocked"
    expected_proof_state = "Unknown" if witness_validation_ok else "Fail"
    if request.get("solver_outcome") != expected_solver_outcome:
        errors.append("solver_outcome must align with witness validation")
    if request.get("proof_state") != expected_proof_state:
        errors.append("proof_state must align with witness validation")

    required_inputs = request.get("required_inputs", [])
    blocked_actions = request.get("blocked_actions", [])
    if not isinstance(required_inputs, list) or not required_inputs:
        errors.append("blocked request must list required inputs")
    if set(blocked_actions) != set(BLOCKED_ACTIONS):
        errors.append("blocked request must list runtime enablement blocked actions")
    _validate_required_inputs(required_inputs, witness_validation_ok, errors)
    _validate_summary(request.get("runtime_enablement_summary", {}), errors)
    source_artifacts = request.get("source_artifacts", {})
    if (
        not isinstance(source_artifacts, dict)
        or "read_only_worker_runtime_enablement_witness" not in source_artifacts
    ):
        errors.append("source_artifacts must include read_only_worker_runtime_enablement_witness")


def _validate_required_inputs(
    required_inputs: Any,
    witness_validation_ok: bool,
    errors: list[str],
) -> None:
    if not isinstance(required_inputs, list):
        errors.append("required_inputs must be a list")
        return
    input_ids = [str(item.get("input_id", "")) for item in required_inputs if isinstance(item, dict)]
    if len(input_ids) != len(set(input_ids)):
        errors.append("required input ids must be unique")
    if any(not INPUT_ID_PATTERN.fullmatch(input_id) for input_id in input_ids):
        errors.append("required input ids must match runtime enablement input pattern")
    input_kinds = {str(item.get("input_kind", "")) for item in required_inputs if isinstance(item, dict)}
    if witness_validation_ok and "valid_runtime_enablement_witness" in input_kinds:
        errors.append("valid witness requests must not ask for valid_runtime_enablement_witness")
    if not witness_validation_ok and "valid_runtime_enablement_witness" not in input_kinds:
        errors.append("invalid witness requests must ask for valid_runtime_enablement_witness")
    for item in required_inputs:
        if not isinstance(item, dict):
            errors.append("required_inputs entries must be objects")
            continue
        if item.get("evidence_source") != "read_only_worker_runtime_enablement_witness":
            errors.append("required input evidence_source is invalid")
        names = item.get("required_names", [])
        if not isinstance(names, list) or not names:
            errors.append("required input required_names must be non-empty")
        if item.get("current_state") not in {"awaiting_evidence", "present_invalid"}:
            errors.append("required input current_state is invalid")


def _validate_summary(summary: Any, errors: list[str]) -> None:
    if not isinstance(summary, dict):
        errors.append("runtime_enablement_summary must be an object")
        return
    expected_values: dict[str, Any] = {
        "worker_id": "worker_local_read_only_repo_inspection",
        "capability": "read_only_repo_inspection",
        "operation_family": "local_repo_inspection",
        "witness_mode": "RUNTIME_ENABLEMENT_WITNESS_ONLY",
        "read_only": True,
        "runtime_enablement_allowed": False,
        "dispatch_admission_allowed": False,
        "runtime_dispatch_allowed": False,
        "worker_invocation_allowed": False,
        "external_network_allowed": False,
        "secret_access_allowed": False,
        "filesystem_write_allowed": False,
        "connector_authority_allowed": False,
        "success_claim_allowed": False,
    }
    for field_name, expected_value in expected_values.items():
        if summary.get(field_name) != expected_value:
            errors.append(f"runtime_enablement_summary.{field_name} is invalid")


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    if not path.exists():
        errors.append(f"{label} file missing")
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError):
        errors.append(f"{label} JSON parse failed")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{label} JSON root must be an object")
        return {}
    return payload


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


def _next_action(request: dict[str, Any]) -> str:
    required_inputs = request.get("required_inputs", [])
    if isinstance(required_inputs, list) and required_inputs:
        first = required_inputs[0]
        if isinstance(first, dict) and str(first.get("next_action", "")).strip():
            return str(first["next_action"])
    return "inspect runtime enablement operator input request"


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse runtime enablement operator input request validation arguments."""

    parser = argparse.ArgumentParser(
        description="Validate read-only worker runtime enablement operator input request."
    )
    parser.add_argument("--request", default=str(DEFAULT_REQUEST))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--require-blocked", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for runtime enablement operator input request validation."""

    args = parse_args(argv)
    validation = validate_runtime_enablement_operator_input_request(
        request_path=Path(args.request),
        schema_path=Path(args.schema),
        require_blocked=args.require_blocked,
    )
    write_runtime_enablement_operator_input_request_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.valid:
        print("runtime enablement operator input request valid")
    else:
        print(f"runtime enablement operator input request invalid errors={list(validation.errors)}")
    return 0 if validation.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
