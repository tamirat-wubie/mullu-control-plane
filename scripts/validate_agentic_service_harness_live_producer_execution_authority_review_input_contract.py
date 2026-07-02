#!/usr/bin/env python3
"""Validate Agentic Service Harness live producer execution authority review input contract.

Purpose: define future review input requirements for live producer execution
authority while keeping review submission and live execution denied.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: review input contract schema, fixture, source execution authority
evidence packet fixture, and scripts.validate_schemas.
Invariants: no live execution, connector call, receipt append, runtime write,
secret access, provider call, mutation route, review submission, or terminal
closure is authorized.
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

from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = (
    REPO_ROOT
    / "schemas"
    / "agentic_service_harness_live_producer_execution_authority_review_input_contract.schema.json"
)
DEFAULT_FIXTURE = (
    REPO_ROOT
    / "examples"
    / "agentic_service_harness_live_producer_execution_authority_review_input_contract.awaiting_evidence.json"
)
SOURCE_EVIDENCE_PACKET_FIXTURE = (
    REPO_ROOT
    / "examples"
    / "agentic_service_harness_live_producer_execution_authority_evidence_packet.awaiting_evidence.json"
)
CONTRACT_ID = "agentic-service-harness-live-producer-execution-authority-review-input-contract"
CONTRACT_STATUS = "blocked_awaiting_live_authority_review_inputs"
SOURCE_PACKET_ID = "agentic-service-harness-live-producer-execution-authority-evidence-packet"
PACKET_STATUS = "blocked_awaiting_live_execution_authority_evidence"
REVIEW_INPUT_IDS = (
    "admission_gate_review_input",
    "operator_approval_review_input",
    "effect_receipt_review_input",
    "external_adapter_review_input",
    "secret_handoff_review_input",
    "rollback_proof_review_input",
    "uao_admission_review_input",
    "life_meaning_judgment_review_input",
    "temporal_lease_review_input",
)
FALSE_REVIEW_FLAGS = (
    "review_route_admitted",
    "review_submitted",
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
ALLOWED_SECRET_KEYS = {"secret_handoff_review_input", "secret_mutation_enabled", "secret_values_allowed"}
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
    r"\b(?:accepted_for_review|review_route_admitted|review_submitted|"
    r"live_execution_authorized|authority_granted|live_producer_implemented|"
    r"receipt_store_append_enabled|connector_call_enabled)=true\b",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class LiveProducerExecutionAuthorityReviewInputContractValidation:
    """Validation result for the live producer execution authority review input contract."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    fixture_path: str
    contract_id: str
    contract_status: str
    review_input_count: int
    missing_review_input_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_live_producer_execution_authority_review_input_contract(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    fixture_path: Path = DEFAULT_FIXTURE,
) -> tuple[LiveProducerExecutionAuthorityReviewInputContractValidation, dict[str, Any]]:
    """Validate the checked-in live producer execution authority review input contract."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "execution authority review input contract schema", errors)
    fixture = _load_json_object(fixture_path, "execution authority review input contract fixture", errors)
    source_packet = _load_json_object(
        SOURCE_EVIDENCE_PACKET_FIXTURE,
        "source execution authority evidence packet fixture",
        errors,
    )
    if source_packet:
        _validate_source_packet_artifact(source_packet, errors, _path_label(SOURCE_EVIDENCE_PACKET_FIXTURE))

    if schema and fixture:
        errors.extend(f"{_path_label(fixture_path)}: {error}" for error in _validate_schema_instance(schema, fixture))
        _validate_contract_semantics(fixture, errors, _path_label(fixture_path))

    review_inputs = fixture.get("review_inputs")
    missing_review_inputs = fixture.get("missing_review_inputs")
    validation = LiveProducerExecutionAuthorityReviewInputContractValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        fixture_path=_path_label(fixture_path),
        contract_id=str(fixture.get("contract_id", "")),
        contract_status=str(fixture.get("contract_status", "")),
        review_input_count=len(review_inputs) if isinstance(review_inputs, list) else 0,
        missing_review_input_count=len(missing_review_inputs) if isinstance(missing_review_inputs, list) else 0,
    )
    return validation, fixture


def _validate_contract_semantics(contract: Mapping[str, Any], errors: list[str], label: str) -> None:
    for field_name, expected in (
        ("contract_id", CONTRACT_ID),
        ("solver_outcome", "AwaitingEvidence"),
        ("contract_status", CONTRACT_STATUS),
        ("source_evidence_packet_status", PACKET_STATUS),
        ("planning_only", True),
        ("read_only", True),
        ("input_collection_started", False),
        ("input_collection_complete", False),
        ("review_route_admitted", False),
        ("review_submitted", False),
        ("live_producer_implemented", False),
        ("live_execution_authorized", False),
        ("authority_granted", False),
        ("terminal_closure", False),
    ):
        if contract.get(field_name) != expected:
            errors.append(f"{label}: {field_name} must be {expected!r}")
    if contract.get("source_evidence_packet_ref") != (
        "examples/agentic_service_harness_live_producer_execution_authority_evidence_packet.awaiting_evidence.json"
    ):
        errors.append(f"{label}: source_evidence_packet_ref mismatch")
    _validate_source_packet_binding(contract, errors, label)
    _validate_review_input_collection(contract.get("review_inputs"), True, errors, label)
    _validate_review_input_collection(contract.get("missing_review_inputs"), False, errors, label)
    _validate_review_denials(_mapping(contract.get("review_denials")), errors, label)
    _validate_effect_boundary(_mapping(contract.get("effect_boundary")), errors, label)
    _validate_validator_ref(contract, errors, label)
    _validate_secret_surface(contract, errors, label)
    _validate_no_mutation_routes(contract, errors, label)
    _validate_no_live_claims(contract, errors, label)


def _validate_source_packet_artifact(packet: Mapping[str, Any], errors: list[str], label: str) -> None:
    """Validate the source packet identity without re-entering its validator graph."""
    for field_name, expected in (
        ("packet_id", SOURCE_PACKET_ID),
        ("solver_outcome", "AwaitingEvidence"),
        ("packet_status", PACKET_STATUS),
        ("planning_only", True),
        ("read_only", True),
        ("live_execution_authorized", False),
        ("authority_granted", False),
        ("terminal_closure", False),
    ):
        if packet.get(field_name) != expected:
            errors.append(f"{label}: {field_name} must be {expected!r}")


def _validate_source_packet_binding(contract: Mapping[str, Any], errors: list[str], label: str) -> None:
    binding = _mapping(contract.get("source_evidence_packet_binding"))
    if not binding:
        errors.append(f"{label}: source_evidence_packet_binding must be an object")
        return
    for field_name, expected in (
        ("source_packet_id", "agentic-service-harness-live-producer-execution-authority-evidence-packet"),
        (
            "source_packet_ref",
            "examples/agentic_service_harness_live_producer_execution_authority_evidence_packet.awaiting_evidence.json",
        ),
        (
            "source_validator_command",
            "python scripts/validate_agentic_service_harness_live_producer_execution_authority_evidence_packet.py",
        ),
        ("source_status", PACKET_STATUS),
        ("source_blocks_live_execution", True),
        ("source_authority_granted", False),
    ):
        if binding.get(field_name) != expected:
            errors.append(f"{label}: source_evidence_packet_binding.{field_name} must be {expected!r}")


def _validate_review_input_collection(value: Any, require_future_ref: bool, errors: list[str], label: str) -> None:
    if not isinstance(value, list):
        errors.append(f"{label}: review input collection must be a list")
        return
    observed_ids = tuple(item.get("input_id") for item in value if isinstance(item, Mapping))
    if observed_ids != REVIEW_INPUT_IDS:
        errors.append(f"{label}: review input order mismatch")
        missing_ids = [input_id for input_id in REVIEW_INPUT_IDS if input_id not in observed_ids]
        if missing_ids:
            errors.append(f"{label}: missing review input values: {', '.join(missing_ids)}")
    for item in value:
        if not isinstance(item, Mapping):
            errors.append(f"{label}: review input entries must be objects")
            continue
        input_id = str(item.get("input_id", ""))
        if item.get("status") != "AwaitingEvidence":
            errors.append(f"{label}: {input_id} status must be AwaitingEvidence")
        if item.get("blocks_live_execution") is not True:
            errors.append(f"{label}: {input_id} must block live execution")
        if item.get("accepted_for_review", False) is not False:
            errors.append(f"{label}: {input_id} must not be accepted for review")
        if require_future_ref and not str(item.get("required_input_ref", "")).startswith("future://"):
            errors.append(f"{label}: {input_id} required_input_ref must stay future://")


def _validate_review_denials(value: Mapping[str, Any], errors: list[str], label: str) -> None:
    if not value:
        errors.append(f"{label}: review_denials must be an object")
        return
    for flag in FALSE_REVIEW_FLAGS:
        if value.get(flag) is not False:
            errors.append(f"{label}: review_denials.{flag} must be false")


def _validate_effect_boundary(value: Mapping[str, Any], errors: list[str], label: str) -> None:
    if not value:
        errors.append(f"{label}: effect_boundary must be an object")
        return
    if value.get("network_policy") != "none":
        errors.append(f"{label}: effect_boundary.network_policy must be none")
    for flag in FALSE_EFFECT_FLAGS:
        if value.get(flag) is not False:
            errors.append(f"{label}: effect_boundary.{flag} must be false")


def _validate_validator_ref(contract: Mapping[str, Any], errors: list[str], label: str) -> None:
    validators = contract.get("validators")
    validator = validators[0] if isinstance(validators, list) and validators and isinstance(validators[0], Mapping) else {}
    if validator.get("validator_id") != CONTRACT_ID:
        errors.append(f"{label}: validator_id mismatch")
    if validator.get("command") != (
        "python scripts/validate_agentic_service_harness_live_producer_execution_authority_review_input_contract.py"
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
    """Run the live producer execution authority review input contract validator."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    validation, _fixture = validate_live_producer_execution_authority_review_input_contract(
        schema_path=args.schema,
        fixture_path=args.fixture,
    )
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("AGENTIC SERVICE HARNESS LIVE PRODUCER EXECUTION AUTHORITY REVIEW INPUT CONTRACT VALID")
    else:
        for error in validation.errors:
            print(f"ERROR: {error}", file=sys.stderr)
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
