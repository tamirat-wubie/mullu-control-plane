#!/usr/bin/env python3
"""Validate general-agent live evidence operator input requests.

Purpose: prove the live-evidence operator input request is schema-valid,
redacted, non-executing, and aligned with its source queue.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/general_agent_promotion_live_evidence_operator_input_request.schema.json
and .change_assurance/general_agent_promotion_live_evidence_operator_input_request.json.
Invariants:
  - The request never executes queue actions or claims production readiness.
  - Missing bindings, manual parameters, and dependency blockers remain visible.
  - Execution status mirrors the source live evidence queue readiness.
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

from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402

DEFAULT_REQUEST = (
    REPO_ROOT / ".change_assurance" / "general_agent_promotion_live_evidence_operator_input_request.json"
)
DEFAULT_QUEUE = REPO_ROOT / ".change_assurance" / "general_agent_promotion_live_evidence_queue.json"
DEFAULT_SCHEMA = (
    REPO_ROOT / "schemas" / "general_agent_promotion_live_evidence_operator_input_request.schema.json"
)
DEFAULT_OUTPUT = (
    REPO_ROOT
    / ".change_assurance"
    / "general_agent_promotion_live_evidence_operator_input_request_validation.json"
)
REQUEST_ID_PATTERN = re.compile(
    r"^general-agent-promotion-live-evidence-operator-input-request-[0-9a-f]{16}$"
)
INPUT_ID_PATTERN = re.compile(r"^general-agent-live-evidence-input-[0-9a-f]{12}$")


@dataclass(frozen=True, slots=True)
class GeneralAgentLiveEvidenceOperatorInputRequestValidation:
    """Validation result for one operator input request."""

    valid: bool
    ready_to_execute: bool
    execution_allowed: bool
    request_path: str
    queue_path: str
    schema_path: str
    errors: tuple[str, ...]
    next_action: str

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-ready validation receipt."""
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_general_agent_live_evidence_operator_input_request(
    *,
    request_path: Path = DEFAULT_REQUEST,
    queue_path: Path = DEFAULT_QUEUE,
    schema_path: Path = DEFAULT_SCHEMA,
    require_blocked: bool = False,
) -> GeneralAgentLiveEvidenceOperatorInputRequestValidation:
    """Validate one live-evidence operator input request."""
    errors: list[str] = []
    try:
        schema = _load_schema(schema_path)
    except OSError:
        schema = {}
        errors.append("general-agent live evidence operator input request schema file missing")
    request = _load_json_object(request_path, "general-agent live evidence operator input request", errors)
    queue = _load_json_object(queue_path, "general-agent live evidence queue", errors)
    if schema and request:
        errors.extend(_validate_schema_instance(schema, request))
    if request:
        _validate_request_semantics(request, errors, require_blocked=require_blocked)
    if request and queue:
        _validate_queue_alignment(request, queue, errors)
    return GeneralAgentLiveEvidenceOperatorInputRequestValidation(
        valid=not errors,
        ready_to_execute=request.get("ready_to_execute") is True if request else False,
        execution_allowed=request.get("execution_allowed") is True if request else False,
        request_path=_path_label(request_path),
        queue_path=_path_label(queue_path),
        schema_path=_path_label(schema_path),
        errors=tuple(errors),
        next_action=_next_action(request) if request else "emit general-agent live evidence operator input request",
    )


def write_general_agent_live_evidence_operator_input_request_validation(
    validation: GeneralAgentLiveEvidenceOperatorInputRequestValidation,
    output_path: Path,
) -> Path:
    """Write one operator input request validation receipt."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_request_semantics(
    request: dict[str, Any],
    errors: list[str],
    *,
    require_blocked: bool,
) -> None:
    if not REQUEST_ID_PATTERN.fullmatch(str(request.get("request_id", ""))):
        errors.append("request_id must match general-agent live evidence operator input request pattern")
    for field_name, expected_value in (
        ("no_secret_values_serialized", True),
        ("queue_is_not_execution", True),
        ("external_effect_performed", False),
        ("production_ready_claimed", False),
    ):
        if request.get(field_name) is not expected_value:
            errors.append(f"{field_name} must be {str(expected_value).lower()}")
    required_inputs = request.get("required_inputs", [])
    if not isinstance(required_inputs, list):
        errors.append("required_inputs must be a list")
        return
    input_ids = [str(item.get("input_id", "")) for item in required_inputs if isinstance(item, dict)]
    if len(input_ids) != len(set(input_ids)):
        errors.append("required input ids must be unique")
    if any(not INPUT_ID_PATTERN.fullmatch(input_id) for input_id in input_ids):
        errors.append("required input ids must match general-agent live evidence input pattern")
    for item in required_inputs:
        if not isinstance(item, dict):
            errors.append("required input item must be an object")
            continue
        if item.get("evidence_source") != "general_agent_promotion_live_evidence_queue":
            errors.append("required input evidence_source mismatch")
        required_names = item.get("required_names", [])
        if not isinstance(required_names, list) or not required_names:
            errors.append("required input required_names must be non-empty")
    execution_allowed = request.get("execution_allowed") is True
    expected_solver_outcome = "SolvedVerified" if execution_allowed else "AwaitingEvidence"
    expected_proof_state = "Pass" if execution_allowed else "Unknown"
    if request.get("solver_outcome") != expected_solver_outcome:
        errors.append("solver_outcome must align with execution_allowed")
    if request.get("proof_state") != expected_proof_state:
        errors.append("proof_state must align with execution_allowed")
    if require_blocked and execution_allowed:
        errors.append("require blocked: execution_allowed is true")


def _validate_queue_alignment(
    request: dict[str, Any],
    queue: dict[str, Any],
    errors: list[str],
) -> None:
    if request.get("queue_id") != queue.get("queue_id"):
        errors.append("queue_id does not match source queue")
    queue_ready = queue.get("ready_to_execute") is True
    required_inputs = request.get("required_inputs", [])
    expected_execution_allowed = queue_ready and isinstance(required_inputs, list) and not required_inputs
    if request.get("ready_to_execute") is not queue_ready:
        errors.append("ready_to_execute does not match source queue")
    if request.get("execution_allowed") is not expected_execution_allowed:
        errors.append("execution_allowed must equal source readiness and no required inputs")
    expected_blocked_actions = _expected_blocked_actions(queue)
    if set(request.get("blocked_actions", [])) != expected_blocked_actions:
        errors.append("blocked_actions do not match non-runnable source queue actions")


def _expected_blocked_actions(queue: dict[str, Any]) -> set[str]:
    actions = queue.get("actions", [])
    if not isinstance(actions, list):
        return set()
    return {
        str(action.get("source_action_id", "")).strip()
        for action in actions
        if isinstance(action, dict)
        and str(action.get("execution_class", "")).strip() != "runnable_local"
        and str(action.get("source_action_id", "")).strip()
    }


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
    next_action = str(request.get("next_action", "")).strip()
    if next_action:
        return next_action
    return "inspect general-agent live evidence operator input request"


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse operator input request validation arguments."""
    parser = argparse.ArgumentParser(
        description="Validate general-agent live evidence operator input request."
    )
    parser.add_argument("--request", default=str(DEFAULT_REQUEST))
    parser.add_argument("--queue", default=str(DEFAULT_QUEUE))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--require-blocked", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for operator input request validation."""
    args = parse_args(argv)
    validation = validate_general_agent_live_evidence_operator_input_request(
        request_path=Path(args.request),
        queue_path=Path(args.queue),
        schema_path=Path(args.schema),
        require_blocked=args.require_blocked,
    )
    write_general_agent_live_evidence_operator_input_request_validation(
        validation,
        Path(args.output),
    )
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    else:
        status = "passed" if validation.valid else "failed"
        print(f"general-agent live evidence operator input request validation {status}")
    return 0 if validation.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
