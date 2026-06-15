#!/usr/bin/env python3
"""Validate Agentic Service Harness operator decision value record path.

Purpose: prove the value-record path contract is ready but blocked until an
actual explicit operator decision value exists.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: gateway.agentic_service_harness_live_producer_operator_decision_value_record_path,
schemas/agentic_service_harness_live_producer_operator_decision_value_record_path.schema.json,
examples/agentic_service_harness_live_producer_operator_decision_value_record_path.local.json,
and scripts.validate_agentic_service_harness_live_producer_operator_decision_value_collection_gate.
Invariants:
  - No operator decision value record is created by this path.
  - Credential-like values, mutation routes, and live authority claims fail closed.
  - Generic continuation remains rejected and cannot satisfy the record path.
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

from gateway.agentic_service_harness_live_producer_operator_decision_value_record_path import (  # noqa: E402
    OPERATOR_DECISION_VALUE_RECORD_PATH_ID,
    project_collection_gate_to_value_record_path,
)
from gateway.agentic_service_harness_live_producer_witness_requirements import FALSE_AUTHORITY_FLAGS  # noqa: E402
from scripts.validate_agentic_service_harness_live_producer_operator_decision_value_collection_gate import (  # noqa: E402
    validate_live_producer_operator_decision_value_collection_gate,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = (
    REPO_ROOT / "schemas" / "agentic_service_harness_live_producer_operator_decision_value_record_path.schema.json"
)
DEFAULT_FIXTURE = (
    REPO_ROOT / "examples" / "agentic_service_harness_live_producer_operator_decision_value_record_path.local.json"
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
class LiveProducerOperatorDecisionValueRecordPathValidation:
    """Validation result for the blocked value-record path."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    fixture_path: str
    record_path_id: str
    path_status: str
    accepted_record_kind_count: int
    rejected_input_kind_count: int
    authority_denial_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_live_producer_operator_decision_value_record_path(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    fixture_path: Path = DEFAULT_FIXTURE,
) -> tuple[LiveProducerOperatorDecisionValueRecordPathValidation, dict[str, Any]]:
    """Validate the checked-in blocked value-record path."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "operator decision value record path schema", errors)
    fixture = _load_json_object(fixture_path, "operator decision value record path fixture", errors)
    gate_validation, collection_gate = validate_live_producer_operator_decision_value_collection_gate()
    errors.extend(f"source operator decision value collection gate: {error}" for error in gate_validation.errors)

    produced_path: dict[str, Any] = {}
    if collection_gate:
        produced_path = project_collection_gate_to_value_record_path(collection_gate)

    if schema and fixture:
        errors.extend(f"{_path_label(fixture_path)}: {error}" for error in _validate_schema_instance(schema, fixture))
        _validate_record_path_semantics(fixture, errors, _path_label(fixture_path))
    if schema and produced_path:
        errors.extend(
            f"produced operator decision value record path: {error}"
            for error in _validate_schema_instance(schema, produced_path)
        )
        _validate_record_path_semantics(produced_path, errors, "produced operator decision value record path")
    if fixture and produced_path:
        _validate_fixture_matches_produced(fixture, produced_path, errors)

    observed = produced_path or fixture
    accepted_record_kinds = observed.get("accepted_record_kinds")
    rejected_input_kinds = observed.get("rejected_input_kinds")
    validation = LiveProducerOperatorDecisionValueRecordPathValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        fixture_path=_path_label(fixture_path),
        record_path_id=str(observed.get("record_path_id", "")),
        path_status=str(observed.get("path_status", "")),
        accepted_record_kind_count=len(accepted_record_kinds) if isinstance(accepted_record_kinds, list) else 0,
        rejected_input_kind_count=len(rejected_input_kinds) if isinstance(rejected_input_kinds, list) else 0,
        authority_denial_count=len(FALSE_AUTHORITY_FLAGS) + 1,
    )
    return validation, produced_path


def _validate_record_path_semantics(path: Mapping[str, Any], errors: list[str], label: str) -> None:
    if path.get("record_path_id") != OPERATOR_DECISION_VALUE_RECORD_PATH_ID:
        errors.append(f"{label}: record_path_id mismatch")
    for field_name, expected_value in (
        ("solver_outcome", "AwaitingEvidence"),
        ("path_status", "ready_blocked_awaiting_explicit_operator_value"),
        ("requested_input_kind", "explicit_operator_decision_value"),
        ("record_contract_ready", True),
        ("record_path_admitted", False),
        ("actual_operator_decision_value_present", False),
        ("operator_value_record_created", False),
        ("collection_gate_satisfied", False),
        ("authority_granted", False),
        ("planning_only", True),
        ("read_only", True),
        ("live_producer_implemented", False),
        ("terminal_closure", False),
    ):
        if path.get(field_name) != expected_value:
            errors.append(f"{label}: {field_name} must be {expected_value!r}")
    _validate_scope(path, errors, label)
    _validate_record_kinds(path, errors, label)
    _validate_record_controls(path, errors, label)
    _validate_denials(path, errors, label)
    _validate_secret_surface(path, errors, label)
    _validate_no_mutation_routes(path, errors, label)
    _validate_no_implementation_claim(path, errors, label)


def _validate_scope(path: Mapping[str, Any], errors: list[str], label: str) -> None:
    scope = _mapping(path.get("scope"))
    if not scope:
        errors.append(f"{label}: scope must be an object")
        return
    if scope.get("read_only") is not True:
        errors.append(f"{label}: scope.read_only must be true")
    for field_name in ("tenant_id", "organization_id", "project_id", "repository_connection_id"):
        if not scope.get(field_name):
            errors.append(f"{label}: scope.{field_name} required")


def _validate_record_kinds(path: Mapping[str, Any], errors: list[str], label: str) -> None:
    if tuple(path.get("accepted_record_kinds", ())) != (
        "explicit_operator_approval",
        "explicit_operator_rejection",
    ):
        errors.append(f"{label}: accepted_record_kinds mismatch")
    if tuple(path.get("rejected_input_kinds", ())) != ("generic_continuation", "template_packet"):
        errors.append(f"{label}: rejected_input_kinds mismatch")


def _validate_record_controls(path: Mapping[str, Any], errors: list[str], label: str) -> None:
    controls = _mapping(path.get("record_controls"))
    if not controls:
        errors.append(f"{label}: record_controls must be an object")
        return
    for flag_name in ("requires_collection_gate_satisfied", "requires_actual_operator_value"):
        if controls.get(flag_name) is not True:
            errors.append(f"{label}: record_controls.{flag_name} must be true")
    for flag_name in (
        "accepts_generic_continuation",
        "accepts_template_packet",
        "creates_operator_value_record",
        "stores_operator_value",
        "admits_mutation_route",
        "grants_live_authority",
    ):
        if controls.get(flag_name) is not False:
            errors.append(f"{label}: record_controls.{flag_name} must be false")


def _validate_denials(path: Mapping[str, Any], errors: list[str], label: str) -> None:
    authority_denials = _mapping(path.get("authority_denials"))
    effect_boundary = _mapping(path.get("effect_boundary"))
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
    produced_path: Mapping[str, Any],
    errors: list[str],
) -> None:
    comparable_fields = (
        "record_path_id",
        "solver_outcome",
        "source_collection_gate_ref",
        "path_status",
        "requested_input_kind",
        "accepted_record_kinds",
        "rejected_input_kinds",
        "record_contract_ready",
        "record_path_admitted",
        "actual_operator_decision_value_present",
        "operator_value_record_created",
        "collection_gate_satisfied",
        "authority_granted",
        "scope",
        "record_controls",
        "authority_denials",
        "effect_boundary",
        "validators",
    )
    for field_name in comparable_fields:
        if fixture.get(field_name) != produced_path.get(field_name):
            errors.append(f"fixture does not match produced operator decision value record path field: {field_name}")


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
    """Run the blocked value-record path validator."""
    args = build_arg_parser().parse_args(argv)
    validation, produced_path = validate_live_producer_operator_decision_value_record_path(
        schema_path=args.schema,
        fixture_path=args.fixture,
    )
    if args.json:
        payload = validation.as_dict()
        payload["produced_path"] = produced_path
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif validation.ok:
        print("AGENTIC SERVICE HARNESS LIVE PRODUCER OPERATOR DECISION VALUE RECORD PATH VALID")
    else:
        print(
            "AGENTIC SERVICE HARNESS LIVE PRODUCER OPERATOR DECISION VALUE RECORD PATH INVALID "
            f"errors={list(validation.errors)}"
        )
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
