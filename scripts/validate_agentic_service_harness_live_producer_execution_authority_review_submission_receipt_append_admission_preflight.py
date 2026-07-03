#!/usr/bin/env python3
"""Validate live producer review submission receipt append admission preflight.

Purpose: define the no-effect preflight for future receipt append admission after the
review submission receipt emission preflight without admitting append.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: receipt append admission preflight schema, fixture, source receipt
emission preflight validator, and scripts.validate_schemas.
Invariants: no review submission, receipt emission, receipt append admission,
receipt append, live execution, connector call, runtime write, secret access, provider call,
mutation route, digest collection, input collection, or terminal closure is
authorized.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import sys
from typing import Any, Iterable, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_agentic_service_harness_live_producer_execution_authority_review_input_contract import (  # noqa: E402
    REVIEW_INPUT_IDS,
)
from scripts.validate_agentic_service_harness_live_producer_execution_authority_review_submission_receipt_emission_preflight import (  # noqa: E402
    PREFLIGHT_STATUS as SOURCE_EMISSION_PREFLIGHT_STATUS,
    validate_live_producer_execution_authority_review_submission_receipt_emission_preflight,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = (
    REPO_ROOT
    / "schemas"
    / "agentic_service_harness_live_producer_execution_authority_review_submission_receipt_append_admission_preflight.schema.json"
)
DEFAULT_FIXTURE = (
    REPO_ROOT
    / "examples"
    / "agentic_service_harness_live_producer_execution_authority_review_submission_receipt_append_admission_preflight.awaiting_evidence.json"
)
PREFLIGHT_ID = "agentic-service-harness-live-producer-execution-authority-review-submission-receipt-append-admission-preflight"
PREFLIGHT_STATUS = "blocked_awaiting_review_submission_receipt_append_admission_evidence"
SOURCE_PREFLIGHT_ID = "agentic-service-harness-live-producer-execution-authority-review-submission-receipt-emission-preflight"
SOURCE_PREFLIGHT_REF = (
    "examples/agentic_service_harness_live_producer_execution_authority_review_submission_receipt_emission_preflight.awaiting_evidence.json"
)
SOURCE_PREFLIGHT_VALIDATOR = (
    "python scripts/validate_agentic_service_harness_live_producer_execution_authority_review_submission_receipt_emission_preflight.py"
)
FALSE_AUTHORITY_FLAGS = (
    "review_route_admitted",
    "review_submission_admitted",
    "review_submitted",
    "digest_collection_started",
    "digest_collection_complete",
    "input_collection_started",
    "input_collection_complete",
    "ui_created",
    "mutation_endpoints_admitted",
    "external_adapter_integrated",
    "connector_call_enabled",
    "branch_write_enabled",
    "pull_request_creation_enabled",
    "deployment_enabled",
    "dns_mutation_enabled",
    "secret_mutation_enabled",
    "destructive_operation_enabled",
    "runtime_state_written",
    "receipt_store_append_enabled",
    "review_submission_receipt_emission_admitted",
    "review_submission_receipt_emitted",
    "review_submission_receipt_append_admission_admitted",
    "review_submission_receipt_append_admitted",
    "review_submission_receipt_appended",
    "live_execution_authorized",
)
FALSE_EFFECT_FLAGS = (
    "provider_calls_allowed",
    "mutation_routes_admitted",
    "external_state_writes_allowed",
    "runtime_state_writes_allowed",
    "receipt_store_append_allowed",
    "receipt_append_allowed",
    "receipt_emission_allowed",
    "secret_values_allowed",
    "raw_payload_retention_allowed",
)
ALLOWED_SECRET_KEYS = {
    "credential_values_allowed",
    "secret_handoff_review_input",
    "secret_mutation_enabled",
    "secret_values_allowed",
}
FORBIDDEN_SECRET_KEY_TOKENS = (
    "access_token",
    "api_key",
    "credential",
    "password",
    "private_key",
    "refresh_token",
    "secret",
    "token",
)
FORBIDDEN_CREDENTIAL_VALUE_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]+PRIVATE KEY-----"),
    re.compile(r"\bghp_[A-Za-z0-9_]+\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]+\b"),
    re.compile(r"\bsk-[A-Za-z0-9_=-]{8,}\b"),
    re.compile(r"\b(access_token|api_key|password|private_key|refresh_token)="),
)
FORBIDDEN_MUTATION_ROUTE = re.compile(r"\b(?:POST|PUT|PATCH|DELETE)\s+/api\b", re.IGNORECASE)
FORBIDDEN_LIVE_CLAIM = re.compile(
    r"\b(?:review_route_admitted|review_submission_admitted|review_submitted|"
    r"review_submission_receipt_emission_admitted|review_submission_receipt_emitted|"
    r"review_submission_receipt_append_admission_admitted|review_submission_receipt_append_admitted|"
    r"review_submission_receipt_appended|digest_collection_complete|"
    r"live_execution_authorized|authority_granted|live_producer_implemented|"
    r"receipt_store_append_enabled|connector_call_enabled)=true\b",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class LiveProducerExecutionAuthorityReviewSubmissionReceiptAppendAdmissionPreflightValidation:
    """Validation result for the review submission receipt append admission preflight."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    fixture_path: str
    preflight_id: str
    preflight_status: str
    append_admission_requirement_count: int
    missing_append_admission_requirement_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_live_producer_execution_authority_review_submission_receipt_append_admission_preflight(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    fixture_path: Path = DEFAULT_FIXTURE,
) -> tuple[LiveProducerExecutionAuthorityReviewSubmissionReceiptAppendAdmissionPreflightValidation, dict[str, Any]]:
    """Validate the checked-in review submission receipt append admission preflight."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "review submission receipt append admission preflight schema", errors)
    fixture = _load_json_object(fixture_path, "review submission receipt append admission preflight fixture", errors)
    source_validation, _source = validate_live_producer_execution_authority_review_submission_receipt_emission_preflight()
    errors.extend(f"source review submission receipt emission preflight: {error}" for error in source_validation.errors)
    if source_validation.preflight_status != SOURCE_EMISSION_PREFLIGHT_STATUS:
        errors.append("source review submission receipt emission preflight must remain blocked AwaitingEvidence")

    if schema and fixture:
        errors.extend(f"{_path_label(fixture_path)}: {error}" for error in _validate_schema_instance(schema, fixture))
        _validate_preflight_semantics(fixture, errors, _path_label(fixture_path))

    requirements = fixture.get("receipt_append_admission_requirements")
    missing_requirements = fixture.get("missing_receipt_append_admission_requirements")
    validation = LiveProducerExecutionAuthorityReviewSubmissionReceiptAppendAdmissionPreflightValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        fixture_path=_path_label(fixture_path),
        preflight_id=str(fixture.get("preflight_id", "")),
        preflight_status=str(fixture.get("preflight_status", "")),
        append_admission_requirement_count=len(requirements) if isinstance(requirements, list) else 0,
        missing_append_admission_requirement_count=len(missing_requirements) if isinstance(missing_requirements, list) else 0,
    )
    return validation, fixture


def _validate_preflight_semantics(preflight: Mapping[str, Any], errors: list[str], label: str) -> None:
    for field_name, expected in (
        ("preflight_id", PREFLIGHT_ID),
        ("solver_outcome", "AwaitingEvidence"),
        ("preflight_status", PREFLIGHT_STATUS),
        ("source_review_submission_receipt_emission_preflight_status", SOURCE_EMISSION_PREFLIGHT_STATUS),
        ("planning_only", True),
        ("read_only", True),
        ("receipt_append_admission_preflight_ready", True),
        ("digest_collection_started", False),
        ("digest_collection_complete", False),
        ("review_route_admitted", False),
        ("review_submission_admitted", False),
        ("review_submitted", False),
        ("review_submission_receipt_emission_admitted", False),
        ("review_submission_receipt_emitted", False),
        ("review_submission_receipt_append_admission_admitted", False),
        ("review_submission_receipt_append_admitted", False),
        ("review_submission_receipt_appended", False),
        ("input_collection_started", False),
        ("input_collection_complete", False),
        ("live_producer_implemented", False),
        ("live_execution_authorized", False),
        ("authority_granted", False),
        ("terminal_closure", False),
    ):
        if preflight.get(field_name) != expected:
            errors.append(f"{label}: {field_name} must be {expected!r}")
    _validate_source_binding(preflight, errors, label)
    _validate_requirement_collection(preflight.get("receipt_append_admission_requirements"), True, errors, label)
    _validate_requirement_collection(preflight.get("missing_receipt_append_admission_requirements"), False, errors, label)
    _validate_emission_policy(_mapping(preflight.get("receipt_append_admission_policy")), errors, label)
    _validate_false_flags(_mapping(preflight.get("authority_denials")), FALSE_AUTHORITY_FLAGS, "authority_denials", errors, label)
    _validate_false_flags(_mapping(preflight.get("effect_boundary")), FALSE_EFFECT_FLAGS, "effect_boundary", errors, label)
    if _mapping(preflight.get("effect_boundary")).get("network_policy") != "none":
        errors.append(f"{label}: effect_boundary.network_policy must be none")
    _validate_validator_ref(preflight, errors, label)
    _validate_secret_surface(preflight, errors, label)
    _validate_no_mutation_routes(preflight, errors, label)
    _validate_no_live_claims(preflight, errors, label)


def _validate_source_binding(preflight: Mapping[str, Any], errors: list[str], label: str) -> None:
    binding = _mapping(preflight.get("source_review_submission_receipt_emission_preflight_binding"))
    expected = {
        "source_preflight_id": SOURCE_PREFLIGHT_ID,
        "source_preflight_ref": SOURCE_PREFLIGHT_REF,
        "source_validator_command": SOURCE_PREFLIGHT_VALIDATOR,
        "source_status": SOURCE_EMISSION_PREFLIGHT_STATUS,
        "source_blocks_receipt_append_admission": True,
        "source_blocks_receipt_append": True,
        "source_blocks_review_submission": True,
        "source_blocks_live_execution": True,
        "source_receipt_emitted": False,
        "source_review_submitted": False,
    }
    for field_name, expected_value in expected.items():
        if binding.get(field_name) != expected_value:
            errors.append(f"{label}: source_review_submission_receipt_emission_preflight_binding.{field_name} must be {expected_value!r}")


def _validate_requirement_collection(value: Any, require_future_refs: bool, errors: list[str], label: str) -> None:
    if not isinstance(value, list):
        errors.append(f"{label}: receipt append admission requirement collection must be a list")
        return
    observed_ids = tuple(item.get("input_id") for item in value if isinstance(item, Mapping))
    if observed_ids != REVIEW_INPUT_IDS:
        errors.append(f"{label}: receipt append admission requirement order mismatch")
        missing_ids = [input_id for input_id in REVIEW_INPUT_IDS if input_id not in observed_ids]
        if missing_ids:
            errors.append(f"{label}: missing receipt append admission inputs: {', '.join(missing_ids)}")
    for item in value:
        if not isinstance(item, Mapping):
            errors.append(f"{label}: receipt append admission requirement entries must be objects")
            continue
        input_id = str(item.get("input_id", ""))
        if item.get("status") != "AwaitingEvidence":
            errors.append(f"{label}: {input_id} status must be AwaitingEvidence")
        if item.get("blocks_receipt_append_admission") is not True:
            errors.append(f"{label}: {input_id} must block receipt append admission")
        if item.get("blocks_receipt_append") is not True:
            errors.append(f"{label}: {input_id} must block receipt append")
        if item.get("blocks_receipt_emission") is not True:
            errors.append(f"{label}: {input_id} must block receipt emission")
        if item.get("blocks_review_submission") is not True:
            errors.append(f"{label}: {input_id} must block review submission")
        if item.get("blocks_live_execution") is not True:
            errors.append(f"{label}: {input_id} must block live execution")
        if item.get("receipt_append_admission_admissible", False) is not False:
            errors.append(f"{label}: {input_id} must not be admissible for receipt append admission")
        if require_future_refs:
            for ref_field in ("required_receipt_ref", "required_receipt_digest_ref", "required_receipt_store_path_ref", "required_append_authority_ref"):
                if not str(item.get(ref_field, "")).startswith("future://"):
                    errors.append(f"{label}: {input_id} {ref_field} must stay future://")


def _validate_emission_policy(policy: Mapping[str, Any], errors: list[str], label: str) -> None:
    expected = {
        "policy_id": "agentic-service-harness-live-producer-review-submission-receipt-append-admission-preflight-policy",
        "all_receipt_refs_required": True,
        "all_receipt_digest_refs_required": True,
        "all_receipt_store_path_refs_required": True,
        "append_authority_ref_required": True,
        "uao_receipt_append_required": True,
        "life_meaning_review_required": True,
        "temporal_lease_required": True,
        "rollback_link_required": True,
        "raw_payload_allowed": False,
        "raw_payload_retention_allowed": False,
        "secret_values_allowed": False,
        "credential_values_allowed": False,
        "mutation_routes_allowed": False,
        "receipt_append_admission_allowed": False,
        "receipt_append_allowed": False,
        "receipt_store_append_allowed": False,
        "receipt_emission_allowed": False,
        "submission_allowed": False,
    }
    for field_name, expected_value in expected.items():
        if policy.get(field_name) != expected_value:
            errors.append(f"{label}: receipt_append_admission_policy.{field_name} must be {expected_value!r}")


def _validate_false_flags(
    value: Mapping[str, Any],
    false_flags: tuple[str, ...],
    object_name: str,
    errors: list[str],
    label: str,
) -> None:
    if not value:
        errors.append(f"{label}: {object_name} must be an object")
        return
    for flag in false_flags:
        if value.get(flag) is not False:
            errors.append(f"{label}: {object_name}.{flag} must be false")


def _validate_validator_ref(preflight: Mapping[str, Any], errors: list[str], label: str) -> None:
    validators = preflight.get("validators")
    validator = validators[0] if isinstance(validators, list) and validators and isinstance(validators[0], Mapping) else {}
    if validator.get("validator_id") != PREFLIGHT_ID:
        errors.append(f"{label}: validator_id mismatch")
    if validator.get("command") != (
        "python scripts/validate_agentic_service_harness_live_producer_execution_authority_review_submission_receipt_append_admission_preflight.py"
    ):
        errors.append(f"{label}: validator command mismatch")
    if validator.get("required_for_closure") is not True:
        errors.append(f"{label}: validator must be required for closure")


def _validate_secret_surface(payload: Any, errors: list[str], label: str) -> None:
    for path, key, value in _walk_json(payload):
        key_lower = key.lower()
        if any(token in key_lower for token in FORBIDDEN_SECRET_KEY_TOKENS) and key_lower not in ALLOWED_SECRET_KEYS:
            errors.append(f"{label}: forbidden secret-bearing key at {path}")
        if isinstance(value, str) and any(pattern.search(value) for pattern in FORBIDDEN_CREDENTIAL_VALUE_PATTERNS):
            errors.append(f"{label}: credential-like value at {path}")


def _validate_no_mutation_routes(payload: Any, errors: list[str], label: str) -> None:
    for path, value in _walk_strings(payload):
        if FORBIDDEN_MUTATION_ROUTE.search(value):
            errors.append(f"{label}: mutation route string at {path}")


def _validate_no_live_claims(payload: Any, errors: list[str], label: str) -> None:
    for path, value in _walk_strings(payload):
        if FORBIDDEN_LIVE_CLAIM.search(value):
            errors.append(f"{label}: live authority claim denied at {path}")


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except (OSError, json.JSONDecodeError, ValueError):
        errors.append(f"{label} JSON load failed: {_path_label(path)}")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{label} JSON root must be an object: {_path_label(path)}")
        return {}
    return payload


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError(f"non-finite JSON constants are not permitted: {raw_constant}")


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _walk_json(payload: Any, path: str = "$") -> Iterable[tuple[str, str, Any]]:
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            child_path = f"{path}.{key}"
            yield child_path, str(key), value
            yield from _walk_json(value, child_path)
    elif isinstance(payload, list):
        for index, item in enumerate(payload):
            child_path = f"{path}[{index}]"
            yield child_path, f"[{index}]", item
            yield from _walk_json(item, child_path)


def _walk_strings(payload: Any, path: str = "$") -> Iterable[tuple[str, str]]:
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            yield from _walk_strings(value, f"{path}.{key}")
    elif isinstance(payload, list):
        for index, item in enumerate(payload):
            yield from _walk_strings(item, f"{path}[{index}]")
    elif isinstance(payload, str):
        yield path, payload


def _path_label(path: Path) -> str:
    resolved = path.resolve(strict=False)
    try:
        return resolved.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def main(argv: list[str] | None = None) -> int:
    """Run the live producer authority review submission receipt append admission preflight validator."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    validation, _fixture = validate_live_producer_execution_authority_review_submission_receipt_append_admission_preflight(
        schema_path=args.schema,
        fixture_path=args.fixture,
    )
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("AGENTIC SERVICE HARNESS LIVE PRODUCER EXECUTION AUTHORITY REVIEW SUBMISSION RECEIPT APPEND ADMISSION PREFLIGHT VALID")
    else:
        for error in validation.errors:
            print(f"ERROR: {error}", file=sys.stderr)
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
