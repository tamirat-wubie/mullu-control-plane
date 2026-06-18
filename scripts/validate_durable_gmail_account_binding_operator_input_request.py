#!/usr/bin/env python3
"""Validate durable Gmail account-binding operator input requests.

Purpose: prove Gmail account-binding operator input requests are schema-valid,
redacted, truthful about missing evidence, and non-executing.
Governance scope: Gmail account binding, source live receipt refs, tenant refs,
expected hash refs, external-effect separation, and production overclaim
blocking.
Dependencies: schemas/durable_gmail_account_binding_operator_input_request.schema.json.
Invariants:
  - Account-binding operator input requests never authorize Gmail profile probes.
  - External provider calls, mailbox writes, profile probes, and account-binding
    claims remain false in every request.
  - Ready operator-review packets still require a separate live profile-probe
    evidence workflow before any account-binding claim.
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

from scripts.validate_durable_gmail_oauth_runtime_preflight import matched_secret_marker  # noqa: E402
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


DEFAULT_REQUEST = REPO_ROOT / ".change_assurance" / "durable_gmail_account_binding_operator_input_request.json"
DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "durable_gmail_account_binding_operator_input_request.schema.json"
DEFAULT_OUTPUT = (
    REPO_ROOT / ".change_assurance" / "durable_gmail_account_binding_operator_input_request_validation.json"
)
REQUEST_ID_PATTERN = re.compile(r"^durable-gmail-account-binding-input-request-[0-9a-f]{16}$")
INPUT_ID_PATTERN = re.compile(r"^durable-gmail-account-binding-input-[0-9a-f]{12}$")
EMAIL_ADDRESS_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
REQUIRED_BLOCKED_ACTIONS = {
    "account_binding_claim",
    "calendar_authority_claim",
    "external_provider_call",
    "gmail_profile_probe",
    "mailbox_write",
    "production_readiness_claim",
    "write_authority_claim",
}


@dataclass(frozen=True, slots=True)
class DurableGmailAccountBindingOperatorInputRequestValidation:
    """Validation result for one durable Gmail account-binding operator input request."""

    valid: bool
    ready_for_operator_review: bool
    profile_probe_allowed: bool
    account_binding_claim_allowed: bool
    request_path: str
    schema_path: str
    errors: tuple[str, ...]
    next_action: str

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-ready validation receipt."""

        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_durable_gmail_account_binding_operator_input_request(
    *,
    request_path: Path = DEFAULT_REQUEST,
    schema_path: Path = DEFAULT_SCHEMA,
    require_blocked: bool = False,
    require_ready_for_operator_review: bool = False,
) -> DurableGmailAccountBindingOperatorInputRequestValidation:
    """Validate one durable Gmail account-binding operator input request."""

    errors: list[str] = []
    try:
        schema = _load_schema(schema_path)
    except OSError:
        schema = {}
        errors.append("durable Gmail account-binding operator input request schema file missing")
    request = _load_json_object(request_path, "durable Gmail account-binding operator input request", errors)
    if schema and request:
        errors.extend(_validate_schema_instance(schema, request))
        _validate_semantics(request, errors)
        if require_blocked and (
            request.get("profile_probe_allowed") is not False
            or request.get("account_binding_claim_allowed") is not False
        ):
            errors.append("require blocked: Gmail profile probe or account-binding claim is allowed")
        if require_ready_for_operator_review and request.get("ready_for_operator_review") is not True:
            errors.append("require ready: Gmail account-binding operator input request is not ready for review")
    return DurableGmailAccountBindingOperatorInputRequestValidation(
        valid=not errors,
        ready_for_operator_review=request.get("ready_for_operator_review") is True if request else False,
        profile_probe_allowed=request.get("profile_probe_allowed") is True if request else False,
        account_binding_claim_allowed=request.get("account_binding_claim_allowed") is True if request else False,
        request_path=_path_label(request_path),
        schema_path=_path_label(schema_path),
        errors=tuple(errors),
        next_action=_next_action(request) if request else "emit durable Gmail account-binding operator input request",
    )


def write_durable_gmail_account_binding_operator_input_request_validation(
    validation: DurableGmailAccountBindingOperatorInputRequestValidation,
    output_path: Path,
) -> Path:
    """Write one durable Gmail account-binding operator input request validation receipt."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_semantics(request: dict[str, Any], errors: list[str]) -> None:
    serialized = json.dumps(request, sort_keys=True)
    if matched_secret_marker(serialized) or EMAIL_ADDRESS_RE.search(serialized):
        errors.append("request must not serialize secret-shaped values or raw mailbox addresses")
    if not REQUEST_ID_PATTERN.fullmatch(str(request.get("request_id", ""))):
        errors.append("request_id must match durable Gmail account-binding input request pattern")

    for field_name in (
        "no_secret_values_serialized",
        "profile_probe_allowed",
        "account_binding_claim_allowed",
        "raw_mailbox_address_disclosed",
        "raw_hash_material_disclosed",
        "external_provider_call_performed",
        "external_mailbox_write_performed",
        "provider_mutation_performed",
        "production_ready_claimed",
        "write_authority_claimed",
        "calendar_authority_claimed",
    ):
        expected = True if field_name == "no_secret_values_serialized" else False
        if request.get(field_name) is not expected:
            errors.append(f"{field_name} must be {str(expected).lower()}")

    required_inputs = request.get("required_inputs", [])
    required_inputs_empty = isinstance(required_inputs, list) and not required_inputs
    source_artifacts = request.get("source_artifacts", {})
    source_ref_valid = _source_ref_valid(source_artifacts, errors)
    summary_valid = _account_binding_summary_valid(request.get("account_binding_summary", {}), errors)
    expected_ready = required_inputs_empty and source_ref_valid and summary_valid
    if request.get("ready_for_operator_review") is not expected_ready:
        errors.append("ready_for_operator_review must equal complete refs and no required inputs")
    expected_solver_outcome = "SolvedVerified" if expected_ready else "AwaitingEvidence"
    expected_proof_state = "Pass" if expected_ready else "Unknown"
    if request.get("solver_outcome") != expected_solver_outcome:
        errors.append("solver_outcome must align with operator input readiness")
    if request.get("proof_state") != expected_proof_state:
        errors.append("proof_state must align with operator input readiness")
    if set(request.get("blocked_actions", [])) != REQUIRED_BLOCKED_ACTIONS:
        errors.append("blocked_actions must preserve all durable Gmail account-binding blocks")
    _validate_required_inputs(required_inputs, errors)


def _validate_required_inputs(required_inputs: Any, errors: list[str]) -> None:
    if not isinstance(required_inputs, list):
        errors.append("required_inputs must be a list")
        return
    input_ids = [str(item.get("input_id", "")) for item in required_inputs if isinstance(item, dict)]
    if len(input_ids) != len(set(input_ids)):
        errors.append("required input ids must be unique")
    if any(not INPUT_ID_PATTERN.fullmatch(input_id) for input_id in input_ids):
        errors.append("required input ids must match durable Gmail account-binding input pattern")
    for item in required_inputs:
        if not isinstance(item, dict):
            errors.append("required input item must be an object")
            continue
        if item.get("evidence_source") != "durable_gmail_account_binding_operator_input_request":
            errors.append("required input evidence_source mismatch")


def _source_ref_valid(source_artifacts: Any, errors: list[str]) -> bool:
    if not isinstance(source_artifacts, dict):
        errors.append("source_artifacts must be an object")
        return False
    return _is_public_ref(source_artifacts.get("source_live_receipt_ref", ""))


def _account_binding_summary_valid(account_binding_summary: Any, errors: list[str]) -> bool:
    if not isinstance(account_binding_summary, dict):
        errors.append("account_binding_summary must be an object")
        return False
    valid = True
    for field_name in (
        "profile_probe_required",
        "source_live_receipt_required",
        "tenant_binding_required",
        "expected_hash_required",
    ):
        if account_binding_summary.get(field_name) is not True:
            errors.append(f"account_binding_summary.{field_name} must be true")
            valid = False
    return valid


def _is_public_ref(value: object) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip()
    if not text or matched_secret_marker(text) or EMAIL_ADDRESS_RE.search(text):
        return False
    if text.startswith(("receipt:", "witness:", "github-actions:", "tenant://")):
        return True
    candidate = Path(text)
    return not candidate.is_absolute() and ".." not in candidate.parts


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
    return "inspect durable Gmail account-binding operator input request"


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse durable Gmail account-binding operator input request validation arguments."""

    parser = argparse.ArgumentParser(description="Validate durable Gmail account-binding operator input request.")
    parser.add_argument("--request", default=str(DEFAULT_REQUEST))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--require-blocked", action="store_true")
    parser.add_argument("--require-ready-for-operator-review", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for durable Gmail account-binding operator input request validation."""

    args = parse_args(argv)
    validation = validate_durable_gmail_account_binding_operator_input_request(
        request_path=Path(args.request),
        schema_path=Path(args.schema),
        require_blocked=args.require_blocked,
        require_ready_for_operator_review=args.require_ready_for_operator_review,
    )
    write_durable_gmail_account_binding_operator_input_request_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.valid:
        print("durable Gmail account-binding operator input request valid")
    else:
        print(f"durable Gmail account-binding operator input request invalid errors={list(validation.errors)}")
    return 0 if validation.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
