#!/usr/bin/env python3
"""Validate deployment publication operator input requests.

Purpose: prove a deployment publication operator input request is schema-valid
and semantically safe before operators rely on it.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/deployment_publication_operator_input_request.schema.json
and emitted deployment publication operator input request JSON.
Invariants:
  - Publication allowance is consistent with readiness and missing inputs.
  - Blocked reports preserve blocked actions and next actions.
  - Secret serialization remains explicitly denied.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402

DEFAULT_REQUEST = (
    REPO_ROOT / ".change_assurance" / "deployment_publication_operator_input_request.json"
)
DEFAULT_SCHEMA = (
    REPO_ROOT / "schemas" / "deployment_publication_operator_input_request.schema.json"
)
DEFAULT_OUTPUT = (
    REPO_ROOT
    / ".change_assurance"
    / "deployment_publication_operator_input_request_validation.json"
)
REQUEST_ID_PATTERN = re.compile(
    r"^deployment-publication-operator-input-request-[0-9a-f]{16}$"
)
INPUT_ID_PATTERN = re.compile(r"^deployment-publication-input-[0-9a-f]{12}$")


@dataclass(frozen=True, slots=True)
class DeploymentPublicationOperatorInputRequestValidation:
    """Validation result for one deployment publication operator input request."""

    valid: bool
    publication_allowed: bool
    request_path: str
    schema_path: str
    errors: tuple[str, ...]
    next_action: str

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-ready validation result."""
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_deployment_publication_operator_input_request(
    *,
    request_path: Path = DEFAULT_REQUEST,
    schema_path: Path = DEFAULT_SCHEMA,
    require_blocked: bool = False,
) -> DeploymentPublicationOperatorInputRequestValidation:
    """Validate one deployment publication operator input request."""
    errors: list[str] = []
    try:
        schema = _load_schema(schema_path)
    except OSError:
        schema = {}
        errors.append("deployment publication operator input request schema file missing")
    request = _load_json_object(request_path, "deployment publication operator input request", errors)
    if schema and request:
        errors.extend(_validate_schema_instance(schema, request))
        _validate_semantics(request, errors)
        if require_blocked and request.get("publication_allowed") is not False:
            errors.append("require blocked: publication allowed")
    publication_allowed = bool(request.get("publication_allowed") is True) if request else False
    return DeploymentPublicationOperatorInputRequestValidation(
        valid=not errors,
        publication_allowed=publication_allowed,
        request_path=_path_label(request_path),
        schema_path=_path_label(schema_path),
        errors=tuple(errors),
        next_action=_next_action(request) if request else "emit deployment publication operator input request",
    )


def write_deployment_publication_operator_input_request_validation(
    validation: DeploymentPublicationOperatorInputRequestValidation,
    output_path: Path,
) -> Path:
    """Write one operator input request validation report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_semantics(request: dict[str, Any], errors: list[str]) -> None:
    if not REQUEST_ID_PATTERN.fullmatch(str(request.get("request_id", ""))):
        errors.append("request_id must match deployment-publication-operator-input-request pattern")
    ready = request.get("ready") is True
    required_inputs = request.get("required_inputs", [])
    blocked_actions = request.get("blocked_actions", [])
    required_inputs_empty = isinstance(required_inputs, list) and not required_inputs
    blocked_actions_empty = isinstance(blocked_actions, list) and not blocked_actions
    expected_publication_allowed = ready and required_inputs_empty and blocked_actions_empty
    if request.get("publication_allowed") is not expected_publication_allowed:
        errors.append("publication_allowed must equal ready with no required inputs or blocked actions")
    expected_solver_outcome = "SolvedVerified" if ready else "AwaitingEvidence"
    expected_proof_state = "Pass" if ready else "Unknown"
    if request.get("solver_outcome") != expected_solver_outcome:
        errors.append("solver_outcome must align with ready state")
    if request.get("proof_state") != expected_proof_state:
        errors.append("proof_state must align with ready state")
    if request.get("no_secret_values_serialized") is not True:
        errors.append("no_secret_values_serialized must be true")
    if isinstance(required_inputs, list):
        input_ids = [str(item.get("input_id", "")) for item in required_inputs if isinstance(item, dict)]
        if len(input_ids) != len(set(input_ids)):
            errors.append("required input ids must be unique")
        if any(not INPUT_ID_PATTERN.fullmatch(input_id) for input_id in input_ids):
            errors.append("required input ids must match deployment-publication-input pattern")
    if not ready and required_inputs_empty:
        errors.append("blocked request must list required inputs")
    if not ready and blocked_actions_empty:
        errors.append("blocked request must list blocked actions")
    source_artifacts = request.get("source_artifacts", {})
    if not isinstance(source_artifacts, dict) or "deployment_publication_evidence_packet" not in source_artifacts:
        errors.append("source_artifacts must include deployment_publication_evidence_packet")


def _next_action(request: dict[str, Any]) -> str:
    if request.get("publication_allowed") is True:
        return "run deployment witness preflight before approved publication dispatch"
    required_inputs = request.get("required_inputs", [])
    if isinstance(required_inputs, list) and required_inputs:
        first = required_inputs[0]
        if isinstance(first, dict) and str(first.get("next_action", "")).strip():
            return str(first["next_action"])
    return "inspect deployment publication operator input request"


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


def _path_label(path: Path) -> str:
    """Return a validation report path label without host-local ancestry."""
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse operator input request validation arguments."""
    parser = argparse.ArgumentParser(
        description="Validate deployment publication operator input request."
    )
    parser.add_argument("--request", default=str(DEFAULT_REQUEST))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--require-blocked", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for operator input request validation."""
    args = parse_args(argv)
    validation = validate_deployment_publication_operator_input_request(
        request_path=Path(args.request),
        schema_path=Path(args.schema),
        require_blocked=args.require_blocked,
    )
    write_deployment_publication_operator_input_request_validation(
        validation,
        Path(args.output),
    )
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.valid:
        print("deployment publication operator input request valid")
    else:
        print(f"deployment publication operator input request invalid errors={list(validation.errors)}")
    return 0 if validation.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
