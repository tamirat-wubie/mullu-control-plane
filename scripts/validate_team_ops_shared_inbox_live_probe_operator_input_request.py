#!/usr/bin/env python3
"""Validate TeamOps shared inbox live-probe operator input requests.

Purpose: prove a TeamOps read-only live-probe operator request is schema-valid,
truthful about authority readiness, redacted, and non-executing.
Governance scope: TeamOps probe authority, missing-input closure, external
effect separation, and secret redaction.
Dependencies: schemas/team_ops_shared_inbox_live_probe_operator_input_request.schema.json.
Invariants:
  - Probe allowance must equal ready authority with no required inputs or
    blocked actions.
  - Blocked requests must explain missing inputs and blocked actions.
  - No request may claim a connector call, mailbox write, draft, send, or
    provider mutation occurred.
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

from scripts.produce_team_ops_shared_inbox_operator_handoff import SECRET_VALUE_MARKERS  # noqa: E402
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


DEFAULT_REQUEST = REPO_ROOT / ".change_assurance" / "team_ops_shared_inbox_live_probe_operator_input_request.json"
DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "team_ops_shared_inbox_live_probe_operator_input_request.schema.json"
DEFAULT_OUTPUT = (
    REPO_ROOT / ".change_assurance" / "team_ops_shared_inbox_live_probe_operator_input_request_validation.json"
)
REQUEST_ID_PATTERN = re.compile(r"^teamops-shared-inbox-live-probe-input-request-[0-9a-f]{16}$")
INPUT_ID_PATTERN = re.compile(r"^teamops-live-probe-input-[0-9a-f]{12}$")
REQUIRED_BLOCKED_ACTIONS = {
    "team_ops_shared_inbox_live_probe",
    "external_provider_call",
    "shared_inbox_message_read",
    "external_message_send",
    "team_ops_production_readiness_claim",
}


@dataclass(frozen=True, slots=True)
class TeamOpsLiveProbeOperatorInputRequestValidation:
    """Validation result for one TeamOps live-probe operator input request."""

    valid: bool
    probe_allowed: bool
    request_path: str
    schema_path: str
    errors: tuple[str, ...]
    next_action: str

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-ready validation receipt."""

        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_team_ops_live_probe_operator_input_request(
    *,
    request_path: Path = DEFAULT_REQUEST,
    schema_path: Path = DEFAULT_SCHEMA,
    require_blocked: bool = False,
    require_ready: bool = False,
) -> TeamOpsLiveProbeOperatorInputRequestValidation:
    """Validate one TeamOps shared inbox live-probe operator input request."""

    errors: list[str] = []
    try:
        schema = _load_schema(schema_path)
    except OSError:
        schema = {}
        errors.append("TeamOps live-probe operator input request schema file missing")
    request = _load_json_object(request_path, "TeamOps live-probe operator input request", errors)
    if schema and request:
        errors.extend(_validate_schema_instance(schema, request))
        _validate_semantics(request, errors)
        if require_blocked and request.get("probe_allowed") is not False:
            errors.append("require blocked: TeamOps live probe is allowed")
        if require_ready and request.get("probe_allowed") is not True:
            errors.append("require ready: TeamOps live probe is not allowed")
    probe_allowed = request.get("probe_allowed") is True if request else False
    return TeamOpsLiveProbeOperatorInputRequestValidation(
        valid=not errors,
        probe_allowed=probe_allowed,
        request_path=_path_label(request_path),
        schema_path=_path_label(schema_path),
        errors=tuple(errors),
        next_action=_next_action(request) if request else "emit TeamOps live-probe operator input request",
    )


def write_team_ops_live_probe_operator_input_request_validation(
    validation: TeamOpsLiveProbeOperatorInputRequestValidation,
    output_path: Path,
) -> Path:
    """Write one TeamOps live-probe operator input request validation receipt."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_semantics(request: dict[str, Any], errors: list[str]) -> None:
    serialized = json.dumps(request, sort_keys=True)
    for marker in SECRET_VALUE_MARKERS:
        if marker.lower() in serialized.lower():
            errors.append(f"request must not serialize secret marker: {marker}")

    if not REQUEST_ID_PATTERN.fullmatch(str(request.get("request_id", ""))):
        errors.append("request_id must match TeamOps live-probe input request pattern")
    for field_name in (
        "no_secret_values_serialized",
        "live_probe_executed",
        "external_provider_call_performed",
        "external_mailbox_write_performed",
        "external_message_sent",
        "provider_mutation_performed",
    ):
        expected = True if field_name == "no_secret_values_serialized" else False
        if request.get(field_name) is not expected:
            errors.append(f"{field_name} must be {str(expected).lower()}")

    ready = request.get("ready") is True
    authority_validation_ok = request.get("authority_validation_ok") is True
    required_inputs = request.get("required_inputs", [])
    blocked_actions = request.get("blocked_actions", [])
    required_inputs_empty = isinstance(required_inputs, list) and not required_inputs
    blocked_actions_empty = isinstance(blocked_actions, list) and not blocked_actions
    expected_probe_allowed = ready and authority_validation_ok and required_inputs_empty and blocked_actions_empty
    if request.get("probe_allowed") is not expected_probe_allowed:
        errors.append("probe_allowed must equal ready authority with no inputs or blocked actions")
    expected_solver_outcome = "SolvedVerified" if expected_probe_allowed else (
        "GovernanceBlocked" if not authority_validation_ok else "AwaitingEvidence"
    )
    expected_proof_state = "Pass" if expected_probe_allowed else ("Fail" if not authority_validation_ok else "Unknown")
    if request.get("solver_outcome") != expected_solver_outcome:
        errors.append("solver_outcome must align with authority readiness")
    if request.get("proof_state") != expected_proof_state:
        errors.append("proof_state must align with authority readiness")
    if not expected_probe_allowed:
        if required_inputs_empty:
            errors.append("blocked request must list required inputs")
        if set(blocked_actions) != REQUIRED_BLOCKED_ACTIONS:
            errors.append("blocked request must list the TeamOps live-probe blocked actions")
    if ready and (required_inputs or blocked_actions):
        errors.append("ready request must not list required inputs or blocked actions")
    _validate_required_inputs(required_inputs, errors)
    _validate_allowed_probe_summary(request.get("allowed_probe_summary", {}), errors)
    source_artifacts = request.get("source_artifacts", {})
    if (
        not isinstance(source_artifacts, dict)
        or "team_ops_shared_inbox_live_probe_authority" not in source_artifacts
    ):
        errors.append("source_artifacts must include team_ops_shared_inbox_live_probe_authority")


def _validate_required_inputs(required_inputs: Any, errors: list[str]) -> None:
    if not isinstance(required_inputs, list):
        errors.append("required_inputs must be a list")
        return
    input_ids = [str(item.get("input_id", "")) for item in required_inputs if isinstance(item, dict)]
    if len(input_ids) != len(set(input_ids)):
        errors.append("required input ids must be unique")
    if any(not INPUT_ID_PATTERN.fullmatch(input_id) for input_id in input_ids):
        errors.append("required input ids must match TeamOps live-probe input pattern")


def _validate_allowed_probe_summary(summary: Any, errors: list[str]) -> None:
    if not isinstance(summary, dict):
        errors.append("allowed_probe_summary must be an object")
        return
    if summary.get("probe_id") != "team_ops.shared_inbox.read_only_probe":
        errors.append("allowed_probe_summary.probe_id must be team_ops.shared_inbox.read_only_probe")
    capabilities = set(summary.get("capabilities_used", []))
    if not capabilities or not capabilities <= {"email.read", "messaging.thread.read"}:
        errors.append("allowed_probe_summary.capabilities_used must stay within read-only TeamOps capabilities")
    for field_name in ("read_only",):
        if summary.get(field_name) is not True:
            errors.append(f"allowed_probe_summary.{field_name} must be true")
    for field_name in ("draft_allowed", "external_send_allowed"):
        if summary.get(field_name) is not False:
            errors.append(f"allowed_probe_summary.{field_name} must be false")
    if not isinstance(summary.get("max_message_count"), int) or summary["max_message_count"] > 50:
        errors.append("allowed_probe_summary.max_message_count must be an integer <= 50")


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
    if request.get("probe_allowed") is True:
        return "run the TeamOps shared inbox read-only live probe and validate its receipt"
    required_inputs = request.get("required_inputs", [])
    if isinstance(required_inputs, list) and required_inputs:
        first = required_inputs[0]
        if isinstance(first, dict) and str(first.get("next_action", "")).strip():
            return str(first["next_action"])
    return "inspect TeamOps live-probe operator input request"


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse TeamOps live-probe operator input request validation arguments."""

    parser = argparse.ArgumentParser(description="Validate TeamOps live-probe operator input request.")
    parser.add_argument("--request", default=str(DEFAULT_REQUEST))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--require-blocked", action="store_true")
    parser.add_argument("--require-ready", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for TeamOps live-probe operator input request validation."""

    args = parse_args(argv)
    validation = validate_team_ops_live_probe_operator_input_request(
        request_path=Path(args.request),
        schema_path=Path(args.schema),
        require_blocked=args.require_blocked,
        require_ready=args.require_ready,
    )
    write_team_ops_live_probe_operator_input_request_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.valid:
        print("TeamOps live-probe operator input request valid")
    else:
        print(f"TeamOps live-probe operator input request invalid errors={list(validation.errors)}")
    return 0 if validation.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
