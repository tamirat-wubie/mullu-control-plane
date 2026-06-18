#!/usr/bin/env python3
"""Validate Agentic Service Harness operator decision value record.

Purpose: prove an explicit operator approval value is recorded without granting
live producer authority or satisfying remaining live-effect witnesses.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: gateway.agentic_service_harness_live_producer_operator_decision_value_record,
schemas/agentic_service_harness_live_producer_operator_decision_value_record.schema.json,
examples/agentic_service_harness_live_producer_operator_decision_value_record.local.json,
and scripts.validate_agentic_service_harness_live_producer_operator_decision_value_record_path.
Invariants:
  - The explicit approval value satisfies only the operator approval witness.
  - Live execution authority, mutation routes, and runtime writes remain denied.
  - Raw operator input and secret-like values are not serialized.
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
    REMAINING_WITNESS_KINDS,
)
from gateway.agentic_service_harness_live_producer_operator_decision_value_record import (  # noqa: E402
    OPERATOR_DECISION_VALUE_RECORD_ID,
    project_record_path_to_operator_decision_value_record,
)
from gateway.agentic_service_harness_live_producer_witness_requirements import FALSE_AUTHORITY_FLAGS  # noqa: E402
from scripts.validate_agentic_service_harness_live_producer_operator_decision_value_record_path import (  # noqa: E402
    validate_live_producer_operator_decision_value_record_path,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = (
    REPO_ROOT / "schemas" / "agentic_service_harness_live_producer_operator_decision_value_record.schema.json"
)
DEFAULT_FIXTURE = (
    REPO_ROOT / "examples" / "agentic_service_harness_live_producer_operator_decision_value_record.local.json"
)
ALLOWED_SECRET_KEYS = {"secret_handoff", "secret_mutation_enabled", "stores_secret_values"}
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
class LiveProducerOperatorDecisionValueRecordValidation:
    """Validation result for the explicit operator decision value record."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    fixture_path: str
    record_id: str
    decision_kind: str
    approval_status: str
    remaining_witness_count: int
    authority_denial_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_live_producer_operator_decision_value_record(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    fixture_path: Path = DEFAULT_FIXTURE,
) -> tuple[LiveProducerOperatorDecisionValueRecordValidation, dict[str, Any]]:
    """Validate the checked-in approval value record and produced record."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "operator decision value record schema", errors)
    fixture = _load_json_object(fixture_path, "operator decision value record fixture", errors)
    path_validation, record_path = validate_live_producer_operator_decision_value_record_path()
    errors.extend(f"source operator decision value record path: {error}" for error in path_validation.errors)

    produced_record: dict[str, Any] = {}
    if record_path:
        produced_record = project_record_path_to_operator_decision_value_record(
            record_path,
            operator_decision_value="approve",
        )

    if schema and fixture:
        errors.extend(f"{_path_label(fixture_path)}: {error}" for error in _validate_schema_instance(schema, fixture))
        _validate_record_semantics(fixture, errors, _path_label(fixture_path))
    if schema and produced_record:
        errors.extend(
            f"produced operator decision value record: {error}"
            for error in _validate_schema_instance(schema, produced_record)
        )
        _validate_record_semantics(produced_record, errors, "produced operator decision value record")
    if fixture and produced_record:
        _validate_fixture_matches_produced(fixture, produced_record, errors)

    observed = produced_record or fixture
    remaining_witnesses = observed.get("remaining_witnesses")
    validation = LiveProducerOperatorDecisionValueRecordValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        fixture_path=_path_label(fixture_path),
        record_id=str(observed.get("record_id", "")),
        decision_kind=str(observed.get("decision_kind", "")),
        approval_status=str(observed.get("approval_status", "")),
        remaining_witness_count=len(remaining_witnesses) if isinstance(remaining_witnesses, list) else 0,
        authority_denial_count=len(FALSE_AUTHORITY_FLAGS) + 1,
    )
    return validation, produced_record


def _validate_record_semantics(record: Mapping[str, Any], errors: list[str], label: str) -> None:
    if record.get("record_id") != OPERATOR_DECISION_VALUE_RECORD_ID:
        errors.append(f"{label}: record_id mismatch")
    for field_name, expected_value in (
        ("solver_outcome", "SolvedVerified"),
        ("source_record_path_status", "ready_blocked_awaiting_explicit_operator_value"),
        ("decision_kind", "explicit_operator_approval"),
        ("normalized_decision_value", "approve"),
        ("raw_input_serialized", False),
        ("operator_value_record_created", True),
        ("actual_operator_decision_value_present", True),
        ("operator_approval_witness_satisfied", True),
        ("operator_rejection_recorded", False),
        ("approval_status", "Satisfied"),
        ("remaining_live_witnesses_status", "AwaitingEvidence"),
        ("authority_granted", False),
        ("planning_only", True),
        ("read_only", True),
        ("live_producer_implemented", False),
        ("terminal_closure", False),
    ):
        if record.get(field_name) != expected_value:
            errors.append(f"{label}: {field_name} must be {expected_value!r}")
    if not record.get("operator_input_ref"):
        errors.append(f"{label}: operator_input_ref required")
    _validate_scope(record, errors, label)
    _validate_remaining_witnesses(record, errors, label)
    _validate_record_controls(record, errors, label)
    _validate_denials(record, errors, label)
    _validate_secret_surface(record, errors, label)
    _validate_no_mutation_routes(record, errors, label)
    _validate_no_implementation_claim(record, errors, label)


def _validate_scope(record: Mapping[str, Any], errors: list[str], label: str) -> None:
    scope = _mapping(record.get("scope"))
    if not scope:
        errors.append(f"{label}: scope must be an object")
        return
    if scope.get("read_only") is not True:
        errors.append(f"{label}: scope.read_only must be true")
    for field_name in ("tenant_id", "organization_id", "project_id", "repository_connection_id"):
        if not scope.get(field_name):
            errors.append(f"{label}: scope.{field_name} required")


def _validate_remaining_witnesses(record: Mapping[str, Any], errors: list[str], label: str) -> None:
    remaining_witnesses = record.get("remaining_witnesses")
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


def _validate_record_controls(record: Mapping[str, Any], errors: list[str], label: str) -> None:
    controls = _mapping(record.get("record_controls"))
    if not controls:
        errors.append(f"{label}: record_controls must be an object")
        return
    if controls.get("requires_remaining_witnesses") is not True:
        errors.append(f"{label}: record_controls.requires_remaining_witnesses must be true")
    for flag_name in (
        "accepts_generic_continuation",
        "accepts_template_packet",
        "stores_raw_operator_input",
        "stores_secret_values",
        "admits_mutation_route",
        "grants_live_authority",
    ):
        if controls.get(flag_name) is not False:
            errors.append(f"{label}: record_controls.{flag_name} must be false")


def _validate_denials(record: Mapping[str, Any], errors: list[str], label: str) -> None:
    authority_denials = _mapping(record.get("authority_denials"))
    effect_boundary = _mapping(record.get("effect_boundary"))
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
    produced_record: Mapping[str, Any],
    errors: list[str],
) -> None:
    comparable_fields = (
        "record_id",
        "solver_outcome",
        "source_record_path_ref",
        "source_record_path_status",
        "operator_input_ref",
        "decision_kind",
        "normalized_decision_value",
        "raw_input_serialized",
        "operator_value_record_created",
        "actual_operator_decision_value_present",
        "operator_approval_witness_satisfied",
        "operator_rejection_recorded",
        "approval_status",
        "remaining_live_witnesses_status",
        "authority_granted",
        "scope",
        "remaining_witnesses",
        "record_controls",
        "authority_denials",
        "effect_boundary",
        "validators",
    )
    for field_name in comparable_fields:
        if fixture.get(field_name) != produced_record.get(field_name):
            errors.append(f"fixture does not match produced operator decision value record field: {field_name}")


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
    """Run the explicit operator decision value record validator."""
    args = build_arg_parser().parse_args(argv)
    validation, produced_record = validate_live_producer_operator_decision_value_record(
        schema_path=args.schema,
        fixture_path=args.fixture,
    )
    if args.json:
        payload = validation.as_dict()
        payload["produced_record"] = produced_record
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif validation.ok:
        print("AGENTIC SERVICE HARNESS LIVE PRODUCER OPERATOR DECISION VALUE RECORD VALID")
    else:
        print(
            "AGENTIC SERVICE HARNESS LIVE PRODUCER OPERATOR DECISION VALUE RECORD INVALID "
            f"errors={list(validation.errors)}"
        )
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
