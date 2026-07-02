#!/usr/bin/env python3
"""Validate live producer execution authority review submission receipt contract.

Purpose: define the no-effect receipt contract for future review submission of
redacted live authority digest evidence without admitting receipt append.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: review submission receipt contract schema, fixture, source review
submission admission preflight validator, and scripts.validate_schemas.
Invariants: no review submission, live execution, connector call, receipt
append, runtime write, secret access, provider call, mutation route, digest
collection, input collection, or terminal closure is authorized.
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
from scripts.validate_agentic_service_harness_live_producer_execution_authority_review_submission_admission_preflight import (  # noqa: E402
    PREFLIGHT_STATUS as ADMISSION_PREFLIGHT_STATUS,
    validate_live_producer_execution_authority_review_submission_admission_preflight,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = (
    REPO_ROOT
    / "schemas"
    / "agentic_service_harness_live_producer_execution_authority_review_submission_receipt_contract.schema.json"
)
DEFAULT_FIXTURE = (
    REPO_ROOT
    / "examples"
    / "agentic_service_harness_live_producer_execution_authority_review_submission_receipt_contract.awaiting_evidence.json"
)
CONTRACT_ID = "agentic-service-harness-live-producer-execution-authority-review-submission-receipt-contract"
CONTRACT_STATUS = "blocked_awaiting_review_submission_receipt_contract_evidence"
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
    "review_submission_receipt_emitted",
    "review_submission_receipt_append_admitted",
    "live_execution_authorized",
)
FALSE_EFFECT_FLAGS = (
    "provider_calls_allowed",
    "mutation_routes_admitted",
    "external_state_writes_allowed",
    "runtime_state_writes_allowed",
    "receipt_store_append_allowed",
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
    r"review_submission_receipt_emitted|review_submission_receipt_append_admitted|"
    r"digest_collection_complete|live_execution_authorized|authority_granted|"
    r"live_producer_implemented|receipt_store_append_enabled|connector_call_enabled)=true\b",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class LiveProducerExecutionAuthorityReviewSubmissionReceiptContractValidation:
    """Validation result for the review submission receipt contract."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    fixture_path: str
    contract_id: str
    contract_status: str
    submission_requirement_count: int
    missing_submission_requirement_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_live_producer_execution_authority_review_submission_receipt_contract(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    fixture_path: Path = DEFAULT_FIXTURE,
) -> tuple[LiveProducerExecutionAuthorityReviewSubmissionReceiptContractValidation, dict[str, Any]]:
    """Validate the checked-in review submission receipt contract."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "review submission receipt contract schema", errors)
    fixture = _load_json_object(fixture_path, "review submission receipt contract fixture", errors)
    preflight_validation, _preflight = validate_live_producer_execution_authority_review_submission_admission_preflight()
    errors.extend(f"source review submission admission preflight: {error}" for error in preflight_validation.errors)
    if preflight_validation.preflight_status != ADMISSION_PREFLIGHT_STATUS:
        errors.append("source review submission admission preflight must remain blocked AwaitingEvidence")

    if schema and fixture:
        errors.extend(f"{_path_label(fixture_path)}: {error}" for error in _validate_schema_instance(schema, fixture))
        _validate_admission_semantics(fixture, errors, _path_label(fixture_path))

    requirements = fixture.get("submission_receipt_requirements")
    missing_requirements = fixture.get("missing_submission_receipt_requirements")
    validation = LiveProducerExecutionAuthorityReviewSubmissionReceiptContractValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        fixture_path=_path_label(fixture_path),
        contract_id=str(fixture.get("contract_id", "")),
        contract_status=str(fixture.get("contract_status", "")),
        submission_requirement_count=len(requirements) if isinstance(requirements, list) else 0,
        missing_submission_requirement_count=len(missing_requirements) if isinstance(missing_requirements, list) else 0,
    )
    return validation, fixture


def _validate_admission_semantics(admission: Mapping[str, Any], errors: list[str], label: str) -> None:
    for field_name, expected in (
        ("contract_id", CONTRACT_ID),
        ("solver_outcome", "AwaitingEvidence"),
        ("contract_status", CONTRACT_STATUS),
        ("source_review_submission_admission_preflight_status", ADMISSION_PREFLIGHT_STATUS),
        ("planning_only", True),
        ("read_only", True),
        ("submission_receipt_contract_ready", True),
        ("digest_collection_started", False),
        ("digest_collection_complete", False),
        ("review_route_admitted", False),
        ("review_submission_admitted", False),
        ("review_submitted", False),
        ("review_submission_receipt_emitted", False),
        ("review_submission_receipt_append_admitted", False),
        ("input_collection_started", False),
        ("input_collection_complete", False),
        ("live_producer_implemented", False),
        ("live_execution_authorized", False),
        ("authority_granted", False),
        ("terminal_closure", False),
    ):
        if admission.get(field_name) != expected:
            errors.append(f"{label}: {field_name} must be {expected!r}")
    _validate_source_binding(admission, errors, label)
    _validate_requirement_collection(admission.get("submission_receipt_requirements"), True, errors, label)
    _validate_requirement_collection(admission.get("missing_submission_receipt_requirements"), False, errors, label)
    _validate_submission_policy(_mapping(admission.get("submission_policy")), errors, label)
    _validate_false_flags(_mapping(admission.get("authority_denials")), FALSE_AUTHORITY_FLAGS, "authority_denials", errors, label)
    _validate_false_flags(_mapping(admission.get("effect_boundary")), FALSE_EFFECT_FLAGS, "effect_boundary", errors, label)
    if _mapping(admission.get("effect_boundary")).get("network_policy") != "none":
        errors.append(f"{label}: effect_boundary.network_policy must be none")
    _validate_validator_ref(admission, errors, label)
    _validate_secret_surface(admission, errors, label)
    _validate_no_mutation_routes(admission, errors, label)
    _validate_no_live_claims(admission, errors, label)


def _validate_source_binding(admission: Mapping[str, Any], errors: list[str], label: str) -> None:
    binding = _mapping(admission.get("source_review_submission_admission_preflight_binding"))
    expected = {
        "source_preflight_id": "agentic-service-harness-live-producer-execution-authority-review-submission-admission-preflight",
        "source_preflight_ref": (
            "examples/agentic_service_harness_live_producer_execution_authority_review_submission_admission_preflight.awaiting_evidence.json"
        ),
        "source_validator_command": (
            "python scripts/validate_agentic_service_harness_live_producer_execution_authority_review_submission_admission_preflight.py"
        ),
        "source_status": ADMISSION_PREFLIGHT_STATUS,
        "source_blocks_review_submission": True,
        "source_blocks_live_execution": True,
        "source_review_submission_admitted": False,
        "source_review_submitted": False,
    }
    for field_name, expected_value in expected.items():
        if binding.get(field_name) != expected_value:
            errors.append(f"{label}: source_review_submission_admission_preflight_binding.{field_name} must be {expected_value!r}")


def _validate_requirement_collection(value: Any, require_future_refs: bool, errors: list[str], label: str) -> None:
    if not isinstance(value, list):
        errors.append(f"{label}: submission requirement collection must be a list")
        return
    observed_ids = tuple(item.get("input_id") for item in value if isinstance(item, Mapping))
    if observed_ids != REVIEW_INPUT_IDS:
        errors.append(f"{label}: submission requirement order mismatch")
        missing_ids = [input_id for input_id in REVIEW_INPUT_IDS if input_id not in observed_ids]
        if missing_ids:
            errors.append(f"{label}: missing submission inputs: {', '.join(missing_ids)}")
    for item in value:
        if not isinstance(item, Mapping):
            errors.append(f"{label}: submission requirement entries must be objects")
            continue
        input_id = str(item.get("input_id", ""))
        if item.get("status") != "AwaitingEvidence":
            errors.append(f"{label}: {input_id} status must be AwaitingEvidence")
        if item.get("blocks_review_submission") is not True:
            errors.append(f"{label}: {input_id} must block review submission")
        if item.get("blocks_live_execution") is not True:
            errors.append(f"{label}: {input_id} must block live execution")
        if item.get("review_submission_admissible", False) is not False:
            errors.append(f"{label}: {input_id} must not be admissible for review submission")
        if require_future_refs:
            for ref_field in ("required_digest_ref", "required_redacted_summary_ref", "required_operator_scope_ref"):
                if not str(item.get(ref_field, "")).startswith("future://"):
                    errors.append(f"{label}: {input_id} {ref_field} must stay future://")


def _validate_submission_policy(policy: Mapping[str, Any], errors: list[str], label: str) -> None:
    expected = {
        "policy_id": "agentic-service-harness-live-producer-review-submission-receipt-contract-policy",
        "all_digest_refs_required": True,
        "all_redacted_summary_refs_required": True,
        "all_required_operator_scope_refs_required": True,
        "uao_review_route_required": True,
        "life_meaning_review_required": True,
        "temporal_lease_required": True,
        "rollback_link_required": True,
        "raw_payload_allowed": False,
        "raw_payload_retention_allowed": False,
        "secret_values_allowed": False,
        "credential_values_allowed": False,
        "mutation_routes_allowed": False,
        "submission_allowed": False,
        "receipt_append_allowed": False,
        "receipt_emission_allowed": False,
    }
    for field_name, expected_value in expected.items():
        if policy.get(field_name) != expected_value:
            errors.append(f"{label}: submission_policy.{field_name} must be {expected_value!r}")


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


def _validate_validator_ref(admission: Mapping[str, Any], errors: list[str], label: str) -> None:
    validators = admission.get("validators")
    validator = validators[0] if isinstance(validators, list) and validators and isinstance(validators[0], Mapping) else {}
    if validator.get("validator_id") != CONTRACT_ID:
        errors.append(f"{label}: validator_id mismatch")
    if validator.get("command") != (
        "python scripts/validate_agentic_service_harness_live_producer_execution_authority_review_submission_receipt_contract.py"
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
    """Run the live producer authority review submission receipt contract validator."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    validation, _fixture = validate_live_producer_execution_authority_review_submission_receipt_contract(
        schema_path=args.schema,
        fixture_path=args.fixture,
    )
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("AGENTIC SERVICE HARNESS LIVE PRODUCER EXECUTION AUTHORITY REVIEW SUBMISSION RECEIPT CONTRACT VALID")
    else:
        for error in validation.errors:
            print(f"ERROR: {error}", file=sys.stderr)
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
