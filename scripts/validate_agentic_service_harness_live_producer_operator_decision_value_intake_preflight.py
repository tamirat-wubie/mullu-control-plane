#!/usr/bin/env python3
"""Validate Agentic Service Harness operator decision value intake preflight.

Purpose: prove the future explicit operator decision value contract is defined
without collecting a value or granting live producer authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: gateway.agentic_service_harness_live_producer_operator_decision_value_intake_preflight,
schemas/agentic_service_harness_live_producer_operator_decision_value_intake_preflight.schema.json,
examples/agentic_service_harness_live_producer_operator_decision_value_intake_preflight.local.json,
and scripts.validate_agentic_service_harness_live_producer_operator_decision_pending_status.
Invariants:
  - Intake preflight remains `AwaitingEvidence`.
  - No operator value is collected by this preflight.
  - Credential-like values, mutation routes, and live authority claims fail closed.
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

from gateway.agentic_service_harness_live_producer_operator_decision_record import (  # noqa: E402
    ACCEPTED_RECORD_KINDS,
    REQUIRED_DECISION_RECORD_FIELDS,
)
from gateway.agentic_service_harness_live_producer_operator_decision_value_intake_preflight import (  # noqa: E402
    FORBIDDEN_DECISION_VALUE_FIELDS,
    OPERATOR_DECISION_VALUE_INTAKE_PREFLIGHT_ID,
    project_pending_status_to_value_intake_preflight,
)
from gateway.agentic_service_harness_live_producer_witness_requirements import FALSE_AUTHORITY_FLAGS  # noqa: E402
from scripts.validate_agentic_service_harness_live_producer_operator_decision_pending_status import (  # noqa: E402
    validate_live_producer_operator_decision_pending_status,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = (
    REPO_ROOT / "schemas" / "agentic_service_harness_live_producer_operator_decision_value_intake_preflight.schema.json"
)
DEFAULT_FIXTURE = (
    REPO_ROOT / "examples" / "agentic_service_harness_live_producer_operator_decision_value_intake_preflight.local.json"
)
ALLOWED_SECRET_KEYS = {"secret_mutation_enabled"}
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
class LiveProducerOperatorDecisionValueIntakePreflightValidation:
    """Validation result for operator decision value intake preflight."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    fixture_path: str
    preflight_boundary_id: str
    intake_status: str
    accepted_value_contract_count: int
    authority_denial_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_live_producer_operator_decision_value_intake_preflight(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    fixture_path: Path = DEFAULT_FIXTURE,
) -> tuple[LiveProducerOperatorDecisionValueIntakePreflightValidation, dict[str, Any]]:
    """Validate the checked-in intake preflight and produced packet."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "operator decision value intake preflight schema", errors)
    fixture = _load_json_object(fixture_path, "operator decision value intake preflight fixture", errors)
    pending_validation, pending_status = validate_live_producer_operator_decision_pending_status()
    errors.extend(f"source operator decision pending status: {error}" for error in pending_validation.errors)

    produced_preflight: dict[str, Any] = {}
    if pending_status:
        produced_preflight = project_pending_status_to_value_intake_preflight(pending_status)

    if schema and fixture:
        errors.extend(f"{_path_label(fixture_path)}: {error}" for error in _validate_schema_instance(schema, fixture))
        _validate_preflight_semantics(fixture, errors, _path_label(fixture_path))
    if schema and produced_preflight:
        errors.extend(
            f"produced operator decision value intake preflight: {error}"
            for error in _validate_schema_instance(schema, produced_preflight)
        )
        _validate_preflight_semantics(produced_preflight, errors, "produced operator decision value intake preflight")
    if fixture and produced_preflight:
        _validate_fixture_matches_produced(fixture, produced_preflight, errors)

    observed = produced_preflight or fixture
    accepted_value_contracts = observed.get("accepted_value_contracts")
    validation = LiveProducerOperatorDecisionValueIntakePreflightValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        fixture_path=_path_label(fixture_path),
        preflight_boundary_id=str(observed.get("preflight_boundary_id", "")),
        intake_status=str(observed.get("intake_status", "")),
        accepted_value_contract_count=len(accepted_value_contracts) if isinstance(accepted_value_contracts, list) else 0,
        authority_denial_count=len(FALSE_AUTHORITY_FLAGS) + 1,
    )
    return validation, produced_preflight


def _validate_preflight_semantics(preflight: Mapping[str, Any], errors: list[str], label: str) -> None:
    if preflight.get("preflight_boundary_id") != OPERATOR_DECISION_VALUE_INTAKE_PREFLIGHT_ID:
        errors.append(f"{label}: preflight_boundary_id mismatch")
    for field_name, expected_value in (
        ("solver_outcome", "AwaitingEvidence"),
        ("intake_status", "AwaitingEvidence"),
        ("current_input_kind", "generic_continuation"),
        ("schema_ready", True),
        ("operator_value_collected", False),
        ("generic_continuation_accepted_as_decision", False),
        ("explicit_operator_value_present", False),
        ("authority_granted", False),
        ("planning_only", True),
        ("read_only", True),
        ("live_producer_implemented", False),
        ("terminal_closure", False),
    ):
        if preflight.get(field_name) != expected_value:
            errors.append(f"{label}: {field_name} must be {expected_value!r}")
    _validate_scope(preflight, errors, label)
    _validate_accepted_value_contracts(preflight, errors, label)
    _validate_denials(preflight, errors, label)
    _validate_secret_surface(preflight, errors, label)
    _validate_no_mutation_routes(preflight, errors, label)
    _validate_no_implementation_claim(preflight, errors, label)


def _validate_scope(preflight: Mapping[str, Any], errors: list[str], label: str) -> None:
    scope = _mapping(preflight.get("scope"))
    if not scope:
        errors.append(f"{label}: scope must be an object")
        return
    if scope.get("read_only") is not True:
        errors.append(f"{label}: scope.read_only must be true")
    for field_name in ("tenant_id", "organization_id", "project_id", "repository_connection_id"):
        if not scope.get(field_name):
            errors.append(f"{label}: scope.{field_name} required")


def _validate_accepted_value_contracts(preflight: Mapping[str, Any], errors: list[str], label: str) -> None:
    contracts = preflight.get("accepted_value_contracts")
    if not isinstance(contracts, list):
        errors.append(f"{label}: accepted_value_contracts must be a list")
        return
    observed_kinds = [entry.get("decision_kind") for entry in contracts if isinstance(entry, Mapping)]
    if tuple(observed_kinds) != ACCEPTED_RECORD_KINDS:
        errors.append(f"{label}: accepted value contract kinds must match required order")
    for entry in contracts:
        if not isinstance(entry, Mapping):
            errors.append(f"{label}: accepted value contract entries must be objects")
            continue
        decision_kind = str(entry.get("decision_kind", ""))
        if entry.get("required") is not True:
            errors.append(f"{label}: {decision_kind} required must be true")
        if entry.get("status") != "AwaitingEvidence":
            errors.append(f"{label}: {decision_kind} status must be AwaitingEvidence")
        if tuple(entry.get("required_fields", ())) != REQUIRED_DECISION_RECORD_FIELDS:
            errors.append(f"{label}: {decision_kind} required_fields mismatch")
        if tuple(entry.get("forbidden_fields", ())) != FORBIDDEN_DECISION_VALUE_FIELDS:
            errors.append(f"{label}: {decision_kind} forbidden_fields mismatch")
        for flag_name in (
            "scope_must_match_pending_status",
            "witness_ref_required",
            "records_operator_intent_only",
        ):
            if entry.get(flag_name) is not True:
                errors.append(f"{label}: {decision_kind} {flag_name} must be true")
        if entry.get("grants_live_authority") is not False:
            errors.append(f"{label}: {decision_kind} grants_live_authority must be false")


def _validate_denials(preflight: Mapping[str, Any], errors: list[str], label: str) -> None:
    authority_denials = _mapping(preflight.get("authority_denials"))
    effect_boundary = _mapping(preflight.get("effect_boundary"))
    for object_name, object_value in (("authority_denials", authority_denials), ("effect_boundary", effect_boundary)):
        if not object_value:
            errors.append(f"{label}: {object_name} must be an object")
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
    produced_preflight: Mapping[str, Any],
    errors: list[str],
) -> None:
    comparable_fields = (
        "preflight_boundary_id",
        "solver_outcome",
        "source_pending_status_ref",
        "intake_status",
        "current_input_kind",
        "schema_ready",
        "operator_value_collected",
        "generic_continuation_accepted_as_decision",
        "explicit_operator_value_present",
        "authority_granted",
        "scope",
        "accepted_value_contracts",
        "authority_denials",
        "effect_boundary",
        "validators",
    )
    for field_name in comparable_fields:
        if fixture.get(field_name) != produced_preflight.get(field_name):
            errors.append(f"fixture does not match produced operator decision value intake preflight field: {field_name}")


def _validate_secret_surface(payload: Any, errors: list[str], label: str) -> None:
    for path, key, value in _walk_json(payload):
        key_lower = key.lower()
        if any(token in key_lower for token in FORBIDDEN_SECRET_KEY_TOKENS) and key_lower not in ALLOWED_SECRET_KEYS:
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
    """Run the live producer operator decision value intake preflight validator."""
    args = build_arg_parser().parse_args(argv)
    validation, produced_preflight = validate_live_producer_operator_decision_value_intake_preflight(
        schema_path=args.schema,
        fixture_path=args.fixture,
    )
    if args.json:
        payload = validation.as_dict()
        payload["produced_preflight"] = produced_preflight
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif validation.ok:
        print("AGENTIC SERVICE HARNESS LIVE PRODUCER OPERATOR DECISION VALUE INTAKE PREFLIGHT VALID")
    else:
        print(
            "AGENTIC SERVICE HARNESS LIVE PRODUCER OPERATOR DECISION VALUE INTAKE PREFLIGHT INVALID "
            f"errors={list(validation.errors)}"
        )
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
