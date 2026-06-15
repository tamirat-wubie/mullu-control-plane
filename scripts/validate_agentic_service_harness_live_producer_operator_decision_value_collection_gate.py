#!/usr/bin/env python3
"""Validate Agentic Service Harness operator decision value collection gate.

Purpose: prove value collection remains blocked after template publication
until an actual explicit operator decision value exists.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: gateway.agentic_service_harness_live_producer_operator_decision_value_collection_gate,
schemas/agentic_service_harness_live_producer_operator_decision_value_collection_gate.schema.json,
examples/agentic_service_harness_live_producer_operator_decision_value_collection_gate.local.json,
and scripts.validate_agentic_service_harness_live_producer_operator_decision_value_template.
Invariants:
  - No collection route is admitted by this gate.
  - No operator value is collected by this gate.
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

from gateway.agentic_service_harness_live_producer_operator_decision_value_collection_gate import (  # noqa: E402
    OPERATOR_DECISION_VALUE_COLLECTION_GATE_ID,
    project_value_template_to_collection_gate,
)
from gateway.agentic_service_harness_live_producer_witness_requirements import FALSE_AUTHORITY_FLAGS  # noqa: E402
from scripts.validate_agentic_service_harness_live_producer_operator_decision_value_template import (  # noqa: E402
    validate_live_producer_operator_decision_value_template,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = (
    REPO_ROOT / "schemas" / "agentic_service_harness_live_producer_operator_decision_value_collection_gate.schema.json"
)
DEFAULT_FIXTURE = (
    REPO_ROOT / "examples" / "agentic_service_harness_live_producer_operator_decision_value_collection_gate.local.json"
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
class LiveProducerOperatorDecisionValueCollectionGateValidation:
    """Validation result for the blocked value collection gate."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    fixture_path: str
    collection_gate_id: str
    gate_status: str
    accepted_input_kind_count: int
    rejected_input_kind_count: int
    authority_denial_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_live_producer_operator_decision_value_collection_gate(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    fixture_path: Path = DEFAULT_FIXTURE,
) -> tuple[LiveProducerOperatorDecisionValueCollectionGateValidation, dict[str, Any]]:
    """Validate the checked-in blocked value collection gate."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "operator decision value collection gate schema", errors)
    fixture = _load_json_object(fixture_path, "operator decision value collection gate fixture", errors)
    template_validation, template_packet = validate_live_producer_operator_decision_value_template()
    errors.extend(f"source operator decision value template: {error}" for error in template_validation.errors)

    produced_gate: dict[str, Any] = {}
    if template_packet:
        produced_gate = project_value_template_to_collection_gate(template_packet)

    if schema and fixture:
        errors.extend(f"{_path_label(fixture_path)}: {error}" for error in _validate_schema_instance(schema, fixture))
        _validate_gate_semantics(fixture, errors, _path_label(fixture_path))
    if schema and produced_gate:
        errors.extend(
            f"produced operator decision value collection gate: {error}"
            for error in _validate_schema_instance(schema, produced_gate)
        )
        _validate_gate_semantics(produced_gate, errors, "produced operator decision value collection gate")
    if fixture and produced_gate:
        _validate_fixture_matches_produced(fixture, produced_gate, errors)

    observed = produced_gate or fixture
    accepted_input_kinds = observed.get("accepted_input_kinds")
    rejected_input_kinds = observed.get("rejected_input_kinds")
    validation = LiveProducerOperatorDecisionValueCollectionGateValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        fixture_path=_path_label(fixture_path),
        collection_gate_id=str(observed.get("collection_gate_id", "")),
        gate_status=str(observed.get("gate_status", "")),
        accepted_input_kind_count=len(accepted_input_kinds) if isinstance(accepted_input_kinds, list) else 0,
        rejected_input_kind_count=len(rejected_input_kinds) if isinstance(rejected_input_kinds, list) else 0,
        authority_denial_count=len(FALSE_AUTHORITY_FLAGS) + 1,
    )
    return validation, produced_gate


def _validate_gate_semantics(gate: Mapping[str, Any], errors: list[str], label: str) -> None:
    if gate.get("collection_gate_id") != OPERATOR_DECISION_VALUE_COLLECTION_GATE_ID:
        errors.append(f"{label}: collection_gate_id mismatch")
    for field_name, expected_value in (
        ("solver_outcome", "AwaitingEvidence"),
        ("gate_status", "blocked_awaiting_explicit_operator_value"),
        ("requested_input_kind", "explicit_operator_decision_value"),
        ("collection_route_admitted", False),
        ("template_accepted_as_value", False),
        ("operator_value_collected", False),
        ("explicit_operator_value_present", False),
        ("authority_granted", False),
        ("planning_only", True),
        ("read_only", True),
        ("live_producer_implemented", False),
        ("terminal_closure", False),
    ):
        if gate.get(field_name) != expected_value:
            errors.append(f"{label}: {field_name} must be {expected_value!r}")
    _validate_scope(gate, errors, label)
    _validate_input_kinds(gate, errors, label)
    _validate_gate_controls(gate, errors, label)
    _validate_denials(gate, errors, label)
    _validate_secret_surface(gate, errors, label)
    _validate_no_mutation_routes(gate, errors, label)
    _validate_no_implementation_claim(gate, errors, label)


def _validate_scope(gate: Mapping[str, Any], errors: list[str], label: str) -> None:
    scope = _mapping(gate.get("scope"))
    if not scope:
        errors.append(f"{label}: scope must be an object")
        return
    if scope.get("read_only") is not True:
        errors.append(f"{label}: scope.read_only must be true")
    for field_name in ("tenant_id", "organization_id", "project_id", "repository_connection_id"):
        if not scope.get(field_name):
            errors.append(f"{label}: scope.{field_name} required")


def _validate_input_kinds(gate: Mapping[str, Any], errors: list[str], label: str) -> None:
    if tuple(gate.get("accepted_input_kinds", ())) != (
        "explicit_operator_approval",
        "explicit_operator_rejection",
    ):
        errors.append(f"{label}: accepted_input_kinds mismatch")
    if tuple(gate.get("rejected_input_kinds", ())) != ("generic_continuation", "template_packet"):
        errors.append(f"{label}: rejected_input_kinds mismatch")


def _validate_gate_controls(gate: Mapping[str, Any], errors: list[str], label: str) -> None:
    controls = _mapping(gate.get("gate_controls"))
    if not controls:
        errors.append(f"{label}: gate_controls must be an object")
        return
    if controls.get("requires_actual_operator_value") is not True:
        errors.append(f"{label}: gate_controls.requires_actual_operator_value must be true")
    for flag_name in (
        "accepts_generic_continuation",
        "accepts_template_packet",
        "admits_mutation_route",
        "stores_operator_value",
        "grants_live_authority",
    ):
        if controls.get(flag_name) is not False:
            errors.append(f"{label}: gate_controls.{flag_name} must be false")


def _validate_denials(gate: Mapping[str, Any], errors: list[str], label: str) -> None:
    authority_denials = _mapping(gate.get("authority_denials"))
    effect_boundary = _mapping(gate.get("effect_boundary"))
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
    produced_gate: Mapping[str, Any],
    errors: list[str],
) -> None:
    comparable_fields = (
        "collection_gate_id",
        "solver_outcome",
        "source_template_ref",
        "gate_status",
        "requested_input_kind",
        "accepted_input_kinds",
        "rejected_input_kinds",
        "collection_route_admitted",
        "template_accepted_as_value",
        "operator_value_collected",
        "explicit_operator_value_present",
        "authority_granted",
        "scope",
        "gate_controls",
        "authority_denials",
        "effect_boundary",
        "validators",
    )
    for field_name in comparable_fields:
        if fixture.get(field_name) != produced_gate.get(field_name):
            errors.append(f"fixture does not match produced operator decision value collection gate field: {field_name}")


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
    """Run the blocked value collection gate validator."""
    args = build_arg_parser().parse_args(argv)
    validation, produced_gate = validate_live_producer_operator_decision_value_collection_gate(
        schema_path=args.schema,
        fixture_path=args.fixture,
    )
    if args.json:
        payload = validation.as_dict()
        payload["produced_gate"] = produced_gate
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif validation.ok:
        print("AGENTIC SERVICE HARNESS LIVE PRODUCER OPERATOR DECISION VALUE COLLECTION GATE VALID")
    else:
        print(
            "AGENTIC SERVICE HARNESS LIVE PRODUCER OPERATOR DECISION VALUE COLLECTION GATE INVALID "
            f"errors={list(validation.errors)}"
        )
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
