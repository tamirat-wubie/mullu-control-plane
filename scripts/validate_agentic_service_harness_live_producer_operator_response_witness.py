#!/usr/bin/env python3
"""Validate Agentic Service Harness live producer operator response witness.

Purpose: prove the operator response witness records missing explicit response
evidence and does not satisfy approval or authorize live producer execution.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: gateway.agentic_service_harness_live_producer_operator_response,
schemas/agentic_service_harness_live_producer_operator_response_witness.schema.json,
examples/agentic_service_harness_live_producer_operator_response_witness.local.json,
and scripts.validate_agentic_service_harness_live_producer_operator_approval_request.
Invariants:
  - Operator response witness remains `AwaitingEvidence`.
  - No response record is collected and approval is not satisfied.
  - Credential-like values, mutation routes, and live implementation claims
    fail closed.
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

from gateway.agentic_service_harness_live_producer_operator_approval import (  # noqa: E402
    ALLOWED_RESPONSE_KINDS,
    OPERATOR_APPROVAL_REQUEST_ID,
    OPERATOR_APPROVAL_WITNESS_KIND,
)
from gateway.agentic_service_harness_live_producer_operator_response import (  # noqa: E402
    OPERATOR_RESPONSE_MISSING_KIND,
    OPERATOR_RESPONSE_WITNESS_ID,
    project_operator_approval_request_to_operator_response_witness,
)
from gateway.agentic_service_harness_live_producer_witness_requirements import (  # noqa: E402
    FALSE_AUTHORITY_FLAGS,
    REQUIRED_WITNESS_KINDS,
)
from scripts.validate_agentic_service_harness_live_producer_operator_approval_request import (  # noqa: E402
    validate_live_producer_operator_approval_request,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = (
    REPO_ROOT / "schemas" / "agentic_service_harness_live_producer_operator_response_witness.schema.json"
)
DEFAULT_FIXTURE = (
    REPO_ROOT / "examples" / "agentic_service_harness_live_producer_operator_response_witness.local.json"
)
ALLOWED_SECRET_KEYS = {
    "secret_handoff",
    "secret_mutation_enabled",
}
FORBIDDEN_SECRET_KEY_TOKENS = (
    "access_token",
    "api_key",
    "password",
    "private_key",
    "refresh_token",
    "secret",
    "secret_value",
    "token",
)
FORBIDDEN_CREDENTIAL_VALUE_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]+PRIVATE KEY-----"),
    re.compile(r"\bghp_[A-Za-z0-9_]+\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]+\b"),
    re.compile(r"\bsk-[A-Za-z0-9_=-]{8,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{8,}\b"),
    re.compile(r"\b(access_token|api_key|password|private_key|refresh_token)="),
)
FORBIDDEN_MUTATION_ROUTE = re.compile(r"\b(?:POST|PUT|PATCH|DELETE)\s+/api\b", re.IGNORECASE)
FORBIDDEN_IMPLEMENTATION_CLAIM = re.compile(r"\blive_producer_implemented=true\b", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class LiveProducerOperatorResponseWitnessValidation:
    """Validation result for the live producer operator response witness."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    fixture_path: str
    response_witness_id: str
    response_kind: str
    witness_count: int
    authority_denial_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_live_producer_operator_response_witness(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    fixture_path: Path = DEFAULT_FIXTURE,
) -> tuple[LiveProducerOperatorResponseWitnessValidation, dict[str, Any]]:
    """Validate the checked-in response witness and produced packet."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "operator response witness schema", errors)
    fixture = _load_json_object(fixture_path, "operator response witness fixture", errors)
    request_validation, approval_request = validate_live_producer_operator_approval_request()
    errors.extend(f"source operator approval request: {error}" for error in request_validation.errors)

    produced_witness: dict[str, Any] = {}
    if approval_request:
        produced_witness = project_operator_approval_request_to_operator_response_witness(approval_request)

    if schema and fixture:
        errors.extend(f"{_path_label(fixture_path)}: {error}" for error in _validate_schema_instance(schema, fixture))
        _validate_response_witness_semantics(fixture, approval_request, errors, _path_label(fixture_path))
    if schema and produced_witness:
        errors.extend(
            f"produced operator response witness: {error}"
            for error in _validate_schema_instance(schema, produced_witness)
        )
        _validate_response_witness_semantics(
            produced_witness,
            approval_request,
            errors,
            "produced operator response witness",
        )
    if fixture and produced_witness:
        _validate_fixture_matches_produced(fixture, produced_witness, errors)

    observed = produced_witness or fixture
    witnesses = observed.get("witnesses_after_response")
    validation = LiveProducerOperatorResponseWitnessValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        fixture_path=_path_label(fixture_path),
        response_witness_id=str(observed.get("response_witness_id", "")),
        response_kind=str(observed.get("response_kind", "")),
        witness_count=len(witnesses) if isinstance(witnesses, list) else 0,
        authority_denial_count=len(FALSE_AUTHORITY_FLAGS) + 1,
    )
    return validation, produced_witness


def _validate_response_witness_semantics(
    witness: Mapping[str, Any],
    approval_request: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    if witness.get("response_witness_id") != OPERATOR_RESPONSE_WITNESS_ID:
        errors.append(f"{label}: response_witness_id mismatch")
    if witness.get("witness_kind") != OPERATOR_APPROVAL_WITNESS_KIND:
        errors.append(f"{label}: witness_kind must be operator_approval")
    for field_name, expected_value in (
        ("solver_outcome", "AwaitingEvidence"),
        ("response_status", "AwaitingEvidence"),
        ("response_kind", OPERATOR_RESPONSE_MISSING_KIND),
        ("response_record_collected", False),
        ("approval_satisfied", False),
        ("rejection_recorded", False),
        ("authority_granted", False),
        ("planning_only", True),
        ("read_only", True),
        ("live_producer_implemented", False),
        ("report_is_not_terminal_closure", True),
        ("terminal_closure", False),
    ):
        if witness.get(field_name) != expected_value:
            errors.append(f"{label}: {field_name} must be {expected_value!r}")
    if not witness.get("requested_evidence_ref"):
        errors.append(f"{label}: requested_evidence_ref required")
    _validate_approval_request_collection_binding(witness, approval_request, errors, label)
    _validate_scope(witness, errors, label)
    _validate_operator_response(witness, errors, label)
    _validate_witnesses_after_response(witness, errors, label)
    _validate_denials(witness, errors, label)
    _validate_secret_surface(witness, errors, label)
    _validate_no_mutation_routes(witness, errors, label)
    _validate_no_implementation_claim(witness, errors, label)


def _validate_scope(witness: Mapping[str, Any], errors: list[str], label: str) -> None:
    scope = _mapping(witness.get("scope"))
    if not scope:
        errors.append(f"{label}: scope must be an object")
        return
    if scope.get("read_only") is not True:
        errors.append(f"{label}: scope.read_only must be true")
    for field_name in ("tenant_id", "organization_id", "project_id", "repository_connection_id"):
        if not scope.get(field_name):
            errors.append(f"{label}: scope.{field_name} required")


def _validate_operator_response(witness: Mapping[str, Any], errors: list[str], label: str) -> None:
    operator_response = _mapping(witness.get("operator_response"))
    if not operator_response:
        errors.append(f"{label}: operator_response must be an object")
        return
    if operator_response.get("approver_role") != "operator":
        errors.append(f"{label}: operator_response.approver_role must be operator")
    if tuple(operator_response.get("required_response_kinds", ())) != ALLOWED_RESPONSE_KINDS:
        errors.append(f"{label}: operator_response.required_response_kinds mismatch")
    if operator_response.get("default_response_kind") != "record_operator_rejection_witness":
        errors.append(f"{label}: operator_response.default_response_kind must reject by default")
    if operator_response.get("observed_response_kind") != OPERATOR_RESPONSE_MISSING_KIND:
        errors.append(f"{label}: operator_response.observed_response_kind must be missing")
    if not operator_response.get("response_record_ref"):
        errors.append(f"{label}: operator_response.response_record_ref required")
    if operator_response.get("response_record_required") is not True:
        errors.append(f"{label}: operator_response.response_record_required must be true")
    if operator_response.get("response_record_collected") is not False:
        errors.append(f"{label}: operator_response.response_record_collected must be false")
    if operator_response.get("approval_effect") != "no_approval_effect_without_explicit_response":
        errors.append(f"{label}: operator_response.approval_effect must deny implicit approval")
    if operator_response.get("live_execution_authorized_after_response") is not False:
        errors.append(f"{label}: operator_response.live_execution_authorized_after_response must be false")


def _validate_witnesses_after_response(witness: Mapping[str, Any], errors: list[str], label: str) -> None:
    witnesses = witness.get("witnesses_after_response")
    if not isinstance(witnesses, list):
        errors.append(f"{label}: witnesses_after_response must be a list")
        return
    observed_kinds = [entry.get("witness_kind") for entry in witnesses if isinstance(entry, Mapping)]
    if tuple(observed_kinds) != REQUIRED_WITNESS_KINDS:
        errors.append(f"{label}: witness kinds must match required order")
    for entry in witnesses:
        if not isinstance(entry, Mapping):
            errors.append(f"{label}: witness entries must be objects")
            continue
        witness_kind = str(entry.get("witness_kind", ""))
        if entry.get("status") != "AwaitingEvidence":
            errors.append(f"{label}: {witness_kind} status must be AwaitingEvidence")
        if entry.get("blocks_live_producer") is not True:
            errors.append(f"{label}: {witness_kind} must block live producer")
        if entry.get("authority_granted") is not False:
            errors.append(f"{label}: {witness_kind} authority_granted must be false")
        if not entry.get("evidence_ref"):
            errors.append(f"{label}: {witness_kind} evidence_ref required")


def _validate_denials(witness: Mapping[str, Any], errors: list[str], label: str) -> None:
    authority_denials = _mapping(witness.get("authority_denials"))
    effect_boundary = _mapping(witness.get("effect_boundary"))
    if not authority_denials:
        errors.append(f"{label}: authority_denials must be an object")
    if not effect_boundary:
        errors.append(f"{label}: effect_boundary must be an object")
    for flag_name in FALSE_AUTHORITY_FLAGS:
        if authority_denials and authority_denials.get(flag_name) is not False:
            errors.append(f"{label}: authority_denials.{flag_name} must be false")
        if effect_boundary and effect_boundary.get(flag_name) is not False:
            errors.append(f"{label}: effect_boundary.{flag_name} must be false")
    if authority_denials and authority_denials.get("live_execution_authorized") is not False:
        errors.append(f"{label}: live execution authority must be false")
    if effect_boundary and effect_boundary.get("network_policy") != "none":
        errors.append(f"{label}: effect_boundary.network_policy must be none")


def _validate_fixture_matches_produced(
    fixture: Mapping[str, Any],
    produced_witness: Mapping[str, Any],
    errors: list[str],
) -> None:
    comparable_fields = (
        "response_witness_id",
        "solver_outcome",
        "source_approval_request_ref",
        "source_requirements_ref",
        "source_admission_gate_ref",
        "witness_kind",
        "requested_evidence_ref",
        "approval_request_collection_binding",
        "response_status",
        "response_kind",
        "response_record_collected",
        "approval_satisfied",
        "rejection_recorded",
        "authority_granted",
        "scope",
        "operator_response",
        "witnesses_after_response",
        "authority_denials",
        "effect_boundary",
        "validators",
    )
    for field_name in comparable_fields:
        if fixture.get(field_name) != produced_witness.get(field_name):
            errors.append(f"fixture does not match produced operator response witness field: {field_name}")


def _validate_approval_request_collection_binding(
    witness: Mapping[str, Any],
    approval_request: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    binding = _mapping(witness.get("approval_request_collection_binding"))
    source_binding = _mapping(approval_request.get("governed_collection_binding"))
    if not binding:
        errors.append(f"{label}: approval_request_collection_binding must be an object")
        return
    expected_values = {
        "binding_id": "binding.operator_response.approval_request_collection",
        "source_binding_id": source_binding.get("binding_id", ""),
        "source_collection_id": source_binding.get("collection_id", ""),
        "source_witness_kind": source_binding.get("witness_kind", ""),
        "source_requirements_evidence_ref": source_binding.get("requirements_evidence_ref", ""),
        "source_governed_artifact_ref": source_binding.get("governed_artifact_ref", ""),
        "source_validator_id": source_binding.get("validator_id", ""),
        "source_validator_command": source_binding.get("validator_command", ""),
        "source_approval_request_ref": f"approval-request://{OPERATOR_APPROVAL_REQUEST_ID}",
        "source_approval_request_id": OPERATOR_APPROVAL_REQUEST_ID,
        "source_request_artifact_ref": source_binding.get("request_artifact_ref", ""),
        "source_request_validator_id": source_binding.get("request_validator_id", ""),
        "source_request_validator_command": source_binding.get("request_validator_command", ""),
        "response_witness_id": OPERATOR_RESPONSE_WITNESS_ID,
        "response_witness_ref": "examples/agentic_service_harness_live_producer_operator_response_witness.local.json",
        "response_validator_id": OPERATOR_RESPONSE_WITNESS_ID,
        "response_validator_command": "python scripts/validate_agentic_service_harness_live_producer_operator_response_witness.py",
        "binding_status": "AwaitingEvidence",
        "source_binding_status": source_binding.get("binding_status", ""),
        "source_collection_status": source_binding.get("collection_status", ""),
        "response_status": "AwaitingEvidence",
        "approval_collected": False,
        "response_record_collected": False,
        "approval_satisfied": False,
        "authority_granted": False,
        "live_execution_authorized": False,
        "blocks_live_producer": True,
    }
    for field_name, expected_value in expected_values.items():
        if binding.get(field_name) != expected_value:
            errors.append(f"{label}: approval_request_collection_binding.{field_name} mismatch")
    for artifact_field in ("source_governed_artifact_ref", "source_request_artifact_ref", "response_witness_ref"):
        artifact_ref = binding.get(artifact_field)
        if isinstance(artifact_ref, str) and not (REPO_ROOT / artifact_ref).is_file():
            errors.append(f"{label}: approval_request_collection_binding.{artifact_field} must exist")


def _validate_secret_surface(payload: Any, errors: list[str], label: str) -> None:
    for path, key, value in _walk_json(payload):
        key_lower = key.lower()
        if (
            any(token in key_lower for token in FORBIDDEN_SECRET_KEY_TOKENS)
            and key_lower not in ALLOWED_SECRET_KEYS
        ):
            errors.append(f"{label}: forbidden secret-bearing key at {path}")
        if isinstance(value, str):
            for pattern in FORBIDDEN_CREDENTIAL_VALUE_PATTERNS:
                if pattern.search(value):
                    errors.append(f"{label}: credential-like value at {path}")
                    break


def _validate_no_mutation_routes(payload: Any, errors: list[str], label: str) -> None:
    for path, value in _walk_strings(payload):
        if FORBIDDEN_MUTATION_ROUTE.search(value):
            errors.append(f"{label}: mutation route string at {path}")


def _validate_no_implementation_claim(payload: Any, errors: list[str], label: str) -> None:
    for path, value in _walk_strings(payload):
        if FORBIDDEN_IMPLEMENTATION_CLAIM.search(value):
            errors.append(f"{label}: live implementation claim at {path}")


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
    if isinstance(value, Mapping):
        return value
    return {}


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
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the live producer operator response witness validator."""
    args = build_arg_parser().parse_args(argv)
    validation, produced_witness = validate_live_producer_operator_response_witness(
        schema_path=args.schema,
        fixture_path=args.fixture,
    )
    if args.json:
        payload = validation.as_dict()
        payload["produced_witness"] = produced_witness
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif validation.ok:
        print("AGENTIC SERVICE HARNESS LIVE PRODUCER OPERATOR RESPONSE WITNESS VALID")
    else:
        print(
            "AGENTIC SERVICE HARNESS LIVE PRODUCER OPERATOR RESPONSE WITNESS INVALID "
            f"errors={list(validation.errors)}"
        )
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
