#!/usr/bin/env python3
"""Validate Agentic Service Harness live producer operator approval request.

Purpose: prove the first operator approval request is explicit, read-only,
uncollected, and non-authorizing before live producer implementation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: gateway.agentic_service_harness_live_producer_operator_approval,
schemas/agentic_service_harness_live_producer_operator_approval_request.schema.json,
examples/agentic_service_harness_live_producer_operator_approval_request.local.json,
and scripts.validate_agentic_service_harness_live_producer_witness_requirements.
Invariants:
  - Operator approval request remains `AwaitingEvidence`.
  - Approval is not collected and grants no live execution authority.
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
    REMAINING_WITNESS_KINDS,
    project_witness_requirements_to_operator_approval_request,
)
from gateway.agentic_service_harness_live_producer_witness_requirements import (  # noqa: E402
    FALSE_AUTHORITY_FLAGS,
    GOVERNED_WITNESS_COLLECTION,
    WITNESS_REQUIREMENTS_ID,
)
from scripts.validate_agentic_service_harness_live_producer_witness_requirements import (  # noqa: E402
    validate_live_producer_witness_requirements,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = (
    REPO_ROOT / "schemas" / "agentic_service_harness_live_producer_operator_approval_request.schema.json"
)
DEFAULT_FIXTURE = (
    REPO_ROOT / "examples" / "agentic_service_harness_live_producer_operator_approval_request.local.json"
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
class LiveProducerOperatorApprovalRequestValidation:
    """Validation result for the live producer operator approval request."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    fixture_path: str
    request_id: str
    witness_kind: str
    remaining_witness_count: int
    authority_denial_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_live_producer_operator_approval_request(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    fixture_path: Path = DEFAULT_FIXTURE,
) -> tuple[LiveProducerOperatorApprovalRequestValidation, dict[str, Any]]:
    """Validate the checked-in approval request and produced packet."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "operator approval request schema", errors)
    fixture = _load_json_object(fixture_path, "operator approval request fixture", errors)
    requirements_validation, witness_requirements = validate_live_producer_witness_requirements()
    errors.extend(f"source witness requirements: {error}" for error in requirements_validation.errors)

    produced_request: dict[str, Any] = {}
    if witness_requirements:
        produced_request = project_witness_requirements_to_operator_approval_request(witness_requirements)

    if schema and fixture:
        errors.extend(f"{_path_label(fixture_path)}: {error}" for error in _validate_schema_instance(schema, fixture))
        _validate_request_semantics(fixture, witness_requirements, errors, _path_label(fixture_path))
    if schema and produced_request:
        errors.extend(
            f"produced operator approval request: {error}"
            for error in _validate_schema_instance(schema, produced_request)
        )
        _validate_request_semantics(
            produced_request,
            witness_requirements,
            errors,
            "produced operator approval request",
        )
    if fixture and produced_request:
        _validate_fixture_matches_produced(fixture, produced_request, errors)

    observed = produced_request or fixture
    remaining_witnesses = observed.get("remaining_witnesses")
    validation = LiveProducerOperatorApprovalRequestValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        fixture_path=_path_label(fixture_path),
        request_id=str(observed.get("request_id", "")),
        witness_kind=str(observed.get("witness_kind", "")),
        remaining_witness_count=len(remaining_witnesses) if isinstance(remaining_witnesses, list) else 0,
        authority_denial_count=len(FALSE_AUTHORITY_FLAGS) + 1,
    )
    return validation, produced_request


def _validate_request_semantics(
    request: Mapping[str, Any],
    witness_requirements: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    if request.get("request_id") != OPERATOR_APPROVAL_REQUEST_ID:
        errors.append(f"{label}: request_id mismatch")
    if request.get("witness_kind") != OPERATOR_APPROVAL_WITNESS_KIND:
        errors.append(f"{label}: witness_kind must be operator_approval")
    if request.get("solver_outcome") != "AwaitingEvidence":
        errors.append(f"{label}: solver_outcome must be AwaitingEvidence")
    for field_name, expected_value in (
        ("approval_status", "AwaitingEvidence"),
        ("approval_collected", False),
        ("authority_granted", False),
        ("planning_only", True),
        ("read_only", True),
        ("live_producer_implemented", False),
        ("report_is_not_terminal_closure", True),
        ("terminal_closure", False),
    ):
        if request.get(field_name) != expected_value:
            errors.append(f"{label}: {field_name} must be {expected_value!r}")
    if not request.get("requested_evidence_ref"):
        errors.append(f"{label}: requested_evidence_ref required")
    _validate_governed_collection_binding(request, witness_requirements, errors, label)
    _validate_scope(request, errors, label)
    _validate_approval_request(request, errors, label)
    _validate_remaining_witnesses(request, errors, label)
    _validate_denials(request, errors, label)
    _validate_secret_surface(request, errors, label)
    _validate_no_mutation_routes(request, errors, label)
    _validate_no_implementation_claim(request, errors, label)


def _validate_scope(request: Mapping[str, Any], errors: list[str], label: str) -> None:
    scope = _mapping(request.get("scope"))
    if not scope:
        errors.append(f"{label}: scope must be an object")
        return
    if scope.get("read_only") is not True:
        errors.append(f"{label}: scope.read_only must be true")
    for field_name in ("tenant_id", "organization_id", "project_id", "repository_connection_id"):
        if not scope.get(field_name):
            errors.append(f"{label}: scope.{field_name} required")


def _validate_approval_request(request: Mapping[str, Any], errors: list[str], label: str) -> None:
    approval_request = _mapping(request.get("approval_request"))
    if not approval_request:
        errors.append(f"{label}: approval_request must be an object")
        return
    if approval_request.get("approver_role") != "operator":
        errors.append(f"{label}: approval_request.approver_role must be operator")
    if approval_request.get("decision_required") != "operator_response_required":
        errors.append(f"{label}: approval_request.decision_required mismatch")
    if tuple(approval_request.get("allowed_response_kinds", ())) != ALLOWED_RESPONSE_KINDS:
        errors.append(f"{label}: approval_request.allowed_response_kinds mismatch")
    if approval_request.get("default_response_kind") != "record_operator_rejection_witness":
        errors.append(f"{label}: approval_request.default_response_kind must reject by default")
    if approval_request.get("response_record_required") is not True:
        errors.append(f"{label}: approval_request.response_record_required must be true")
    if approval_request.get("response_record_collected") is not False:
        errors.append(f"{label}: approval_request.response_record_collected must be false")
    if approval_request.get("approval_effect") != "satisfies_operator_approval_witness_only":
        errors.append(f"{label}: approval_request.approval_effect must be witness-only")
    if approval_request.get("live_execution_authorized_after_response") is not False:
        errors.append(f"{label}: approval_request.live_execution_authorized_after_response must be false")


def _validate_remaining_witnesses(request: Mapping[str, Any], errors: list[str], label: str) -> None:
    remaining_witnesses = request.get("remaining_witnesses")
    if not isinstance(remaining_witnesses, list):
        errors.append(f"{label}: remaining_witnesses must be a list")
        return
    observed_kinds = [witness.get("witness_kind") for witness in remaining_witnesses if isinstance(witness, Mapping)]
    if tuple(observed_kinds) != REMAINING_WITNESS_KINDS:
        errors.append(f"{label}: remaining witness kinds must match required order")
    for witness in remaining_witnesses:
        if not isinstance(witness, Mapping):
            errors.append(f"{label}: remaining witness entries must be objects")
            continue
        witness_kind = str(witness.get("witness_kind", ""))
        if witness.get("status") != "AwaitingEvidence":
            errors.append(f"{label}: {witness_kind} status must be AwaitingEvidence")
        if witness.get("blocks_live_producer") is not True:
            errors.append(f"{label}: {witness_kind} must block live producer")
        if not witness.get("evidence_ref"):
            errors.append(f"{label}: {witness_kind} evidence_ref required")


def _validate_denials(request: Mapping[str, Any], errors: list[str], label: str) -> None:
    authority_denials = _mapping(request.get("authority_denials"))
    effect_boundary = _mapping(request.get("effect_boundary"))
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
    produced_request: Mapping[str, Any],
    errors: list[str],
) -> None:
    comparable_fields = (
        "request_id",
        "solver_outcome",
        "source_requirements_ref",
        "source_admission_gate_ref",
        "witness_kind",
        "requested_evidence_ref",
        "governed_collection_binding",
        "approval_status",
        "approval_collected",
        "authority_granted",
        "scope",
        "approval_request",
        "remaining_witnesses",
        "authority_denials",
        "effect_boundary",
        "validators",
    )
    for field_name in comparable_fields:
        if fixture.get(field_name) != produced_request.get(field_name):
            errors.append(f"fixture does not match produced operator approval request field: {field_name}")


def _validate_governed_collection_binding(
    request: Mapping[str, Any],
    witness_requirements: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    binding = _mapping(request.get("governed_collection_binding"))
    if not binding:
        errors.append(f"{label}: governed_collection_binding must be an object")
        return
    source_entry = _find_collection_entry(witness_requirements, OPERATOR_APPROVAL_WITNESS_KIND)
    expected_entry = _expected_collection_entry(OPERATOR_APPROVAL_WITNESS_KIND)
    expected_values = {
        "binding_id": "binding.operator_approval.governed_witness_collection",
        "collection_id": "collection.operator_approval",
        "witness_kind": OPERATOR_APPROVAL_WITNESS_KIND,
        "requirements_evidence_ref": source_entry.get(
            "requirements_evidence_ref",
            expected_entry.get("requirements_evidence_ref", ""),
        ),
        "governed_artifact_ref": source_entry.get(
            "governed_artifact_ref",
            expected_entry.get("governed_artifact_ref", ""),
        ),
        "validator_id": source_entry.get("validator_id", expected_entry.get("validator_id", "")),
        "validator_command": source_entry.get(
            "validator_command",
            expected_entry.get("validator_command", ""),
        ),
        "source_requirements_ref": f"requirements://{WITNESS_REQUIREMENTS_ID}",
        "request_id": OPERATOR_APPROVAL_REQUEST_ID,
        "request_artifact_ref": "examples/agentic_service_harness_live_producer_operator_approval_request.local.json",
        "request_validator_id": OPERATOR_APPROVAL_REQUEST_ID,
        "request_validator_command": "python scripts/validate_agentic_service_harness_live_producer_operator_approval_request.py",
        "binding_status": "AwaitingEvidence",
        "collection_status": "AwaitingEvidence",
        "authority_granted": False,
        "blocks_live_producer": True,
        "approval_collected": False,
        "live_execution_authorized": False,
    }
    for field_name, expected_value in expected_values.items():
        if binding.get(field_name) != expected_value:
            errors.append(f"{label}: governed_collection_binding.{field_name} mismatch")
    if source_entry and binding.get("collection_status") != source_entry.get("status"):
        errors.append(f"{label}: governed_collection_binding.collection_status must match source status")
    if source_entry and binding.get("authority_granted") != source_entry.get("authority_granted"):
        errors.append(f"{label}: governed_collection_binding.authority_granted must match source collection")
    if source_entry and binding.get("blocks_live_producer") != source_entry.get("blocks_live_producer"):
        errors.append(f"{label}: governed_collection_binding.blocks_live_producer must match source collection")
    artifact_ref = binding.get("governed_artifact_ref")
    if isinstance(artifact_ref, str) and not (REPO_ROOT / artifact_ref).is_file():
        errors.append(f"{label}: governed_collection_binding.governed_artifact_ref must exist")


def _find_collection_entry(requirements: Mapping[str, Any], witness_kind: str) -> Mapping[str, Any]:
    collection = requirements.get("governed_witness_collection")
    if not isinstance(collection, list):
        return {}
    for entry in collection:
        if isinstance(entry, Mapping) and entry.get("witness_kind") == witness_kind:
            return entry
    return {}


def _expected_collection_entry(witness_kind: str) -> Mapping[str, Any]:
    for entry in GOVERNED_WITNESS_COLLECTION:
        if entry.get("witness_kind") == witness_kind:
            return entry
    return {}


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
    """Run the live producer operator approval request validator."""
    args = build_arg_parser().parse_args(argv)
    validation, produced_request = validate_live_producer_operator_approval_request(
        schema_path=args.schema,
        fixture_path=args.fixture,
    )
    if args.json:
        payload = validation.as_dict()
        payload["produced_request"] = produced_request
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif validation.ok:
        print("AGENTIC SERVICE HARNESS LIVE PRODUCER OPERATOR APPROVAL REQUEST VALID")
    else:
        print(
            "AGENTIC SERVICE HARNESS LIVE PRODUCER OPERATOR APPROVAL REQUEST INVALID "
            f"errors={list(validation.errors)}"
        )
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
