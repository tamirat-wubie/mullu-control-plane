#!/usr/bin/env python3
"""Validate Agentic Service Harness explicit operator decision value templates.

Purpose: prove approval and rejection templates are available without accepting
the templates as operator values or granting live producer authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: gateway.agentic_service_harness_live_producer_operator_decision_value_template,
schemas/agentic_service_harness_live_producer_operator_decision_value_template.schema.json,
examples/agentic_service_harness_live_producer_operator_decision_value_template.local.json,
and scripts.validate_agentic_service_harness_live_producer_operator_decision_value_request.
Invariants:
  - Templates remain `template_only`.
  - No operator value is collected by this packet.
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

from gateway.agentic_service_harness_live_producer_operator_decision_record import ACCEPTED_RECORD_KINDS  # noqa: E402
from gateway.agentic_service_harness_live_producer_operator_decision_value_template import (  # noqa: E402
    OPERATOR_DECISION_VALUE_TEMPLATE_ID,
    project_value_request_to_value_template,
)
from gateway.agentic_service_harness_live_producer_witness_requirements import FALSE_AUTHORITY_FLAGS  # noqa: E402
from scripts.validate_agentic_service_harness_live_producer_operator_decision_value_request import (  # noqa: E402
    validate_live_producer_operator_decision_value_request,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = (
    REPO_ROOT / "schemas" / "agentic_service_harness_live_producer_operator_decision_value_template.schema.json"
)
DEFAULT_FIXTURE = (
    REPO_ROOT / "examples" / "agentic_service_harness_live_producer_operator_decision_value_template.local.json"
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
class LiveProducerOperatorDecisionValueTemplateValidation:
    """Validation result for explicit operator decision value templates."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    fixture_path: str
    template_packet_id: str
    template_status: str
    decision_value_template_count: int
    authority_denial_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_live_producer_operator_decision_value_template(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    fixture_path: Path = DEFAULT_FIXTURE,
) -> tuple[LiveProducerOperatorDecisionValueTemplateValidation, dict[str, Any]]:
    """Validate the checked-in explicit operator decision value template packet."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "operator decision value template schema", errors)
    fixture = _load_json_object(fixture_path, "operator decision value template fixture", errors)
    request_validation, value_request = validate_live_producer_operator_decision_value_request()
    errors.extend(f"source operator decision value request: {error}" for error in request_validation.errors)

    produced_template: dict[str, Any] = {}
    if value_request:
        produced_template = project_value_request_to_value_template(value_request)

    if schema and fixture:
        errors.extend(f"{_path_label(fixture_path)}: {error}" for error in _validate_schema_instance(schema, fixture))
        _validate_template_semantics(fixture, errors, _path_label(fixture_path))
    if schema and produced_template:
        errors.extend(
            f"produced operator decision value template: {error}"
            for error in _validate_schema_instance(schema, produced_template)
        )
        _validate_template_semantics(produced_template, errors, "produced operator decision value template")
    if fixture and produced_template:
        _validate_fixture_matches_produced(fixture, produced_template, errors)

    observed = produced_template or fixture
    templates = observed.get("decision_value_templates")
    validation = LiveProducerOperatorDecisionValueTemplateValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        fixture_path=_path_label(fixture_path),
        template_packet_id=str(observed.get("template_packet_id", "")),
        template_status=str(observed.get("template_status", "")),
        decision_value_template_count=len(templates) if isinstance(templates, list) else 0,
        authority_denial_count=len(FALSE_AUTHORITY_FLAGS) + 1,
    )
    return validation, produced_template


def _validate_template_semantics(template_packet: Mapping[str, Any], errors: list[str], label: str) -> None:
    if template_packet.get("template_packet_id") != OPERATOR_DECISION_VALUE_TEMPLATE_ID:
        errors.append(f"{label}: template_packet_id mismatch")
    for field_name, expected_value in (
        ("solver_outcome", "AwaitingEvidence"),
        ("template_status", "template_only_awaiting_operator_value"),
        ("requested_input_kind", "explicit_operator_decision_value"),
        ("operator_value_collected", False),
        ("explicit_operator_value_present", False),
        ("template_accepted_as_value", False),
        ("authority_granted", False),
        ("planning_only", True),
        ("read_only", True),
        ("live_producer_implemented", False),
        ("terminal_closure", False),
    ):
        if template_packet.get(field_name) != expected_value:
            errors.append(f"{label}: {field_name} must be {expected_value!r}")
    _validate_scope(template_packet, errors, label)
    _validate_decision_value_templates(template_packet, errors, label)
    _validate_template_controls(template_packet, errors, label)
    _validate_denials(template_packet, errors, label)
    _validate_secret_surface(template_packet, errors, label)
    _validate_no_mutation_routes(template_packet, errors, label)
    _validate_no_implementation_claim(template_packet, errors, label)


def _validate_scope(template_packet: Mapping[str, Any], errors: list[str], label: str) -> None:
    scope = _mapping(template_packet.get("scope"))
    if not scope:
        errors.append(f"{label}: scope must be an object")
        return
    if scope.get("read_only") is not True:
        errors.append(f"{label}: scope.read_only must be true")
    for field_name in ("tenant_id", "organization_id", "project_id", "repository_connection_id"):
        if not scope.get(field_name):
            errors.append(f"{label}: scope.{field_name} required")


def _validate_decision_value_templates(template_packet: Mapping[str, Any], errors: list[str], label: str) -> None:
    templates = template_packet.get("decision_value_templates")
    if not isinstance(templates, list):
        errors.append(f"{label}: decision_value_templates must be a list")
        return
    observed_kinds = [entry.get("decision_kind") for entry in templates if isinstance(entry, Mapping)]
    if tuple(observed_kinds) != ACCEPTED_RECORD_KINDS:
        errors.append(f"{label}: decision value template kinds must match required order")
    for entry in templates:
        if not isinstance(entry, Mapping):
            errors.append(f"{label}: decision value template entries must be objects")
            continue
        decision_kind = str(entry.get("decision_kind", ""))
        for flag_name in ("template_only",):
            if entry.get(flag_name) is not True:
                errors.append(f"{label}: {decision_kind} {flag_name} must be true")
        for flag_name in ("accepted_as_value", "grants_live_authority"):
            if entry.get(flag_name) is not False:
                errors.append(f"{label}: {decision_kind} {flag_name} must be false")
        field_templates = _mapping(entry.get("field_templates"))
        if field_templates.get("decision_kind") != decision_kind:
            errors.append(f"{label}: {decision_kind} field_templates.decision_kind mismatch")
        for field_name in ("operator_id", "decision_text", "created_at", "witness_ref"):
            if not field_templates.get(field_name):
                errors.append(f"{label}: {decision_kind} field_templates.{field_name} required")
        scope = _mapping(field_templates.get("scope"))
        for scope_field in ("tenant_id", "organization_id", "project_id", "repository_connection_id"):
            if not scope.get(scope_field):
                errors.append(f"{label}: {decision_kind} field_templates.scope.{scope_field} required")


def _validate_template_controls(template_packet: Mapping[str, Any], errors: list[str], label: str) -> None:
    controls = _mapping(template_packet.get("template_controls"))
    if not controls:
        errors.append(f"{label}: template_controls must be an object")
        return
    if controls.get("template_only") is not True:
        errors.append(f"{label}: template_controls.template_only must be true")
    for flag_name in (
        "stores_operator_value",
        "accepts_template_as_value",
        "credential_values_allowed",
        "mutation_route_allowed",
        "live_authority_on_template",
    ):
        if controls.get(flag_name) is not False:
            errors.append(f"{label}: template_controls.{flag_name} must be false")


def _validate_denials(template_packet: Mapping[str, Any], errors: list[str], label: str) -> None:
    authority_denials = _mapping(template_packet.get("authority_denials"))
    effect_boundary = _mapping(template_packet.get("effect_boundary"))
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
    produced_template: Mapping[str, Any],
    errors: list[str],
) -> None:
    comparable_fields = (
        "template_packet_id",
        "solver_outcome",
        "source_value_request_ref",
        "template_status",
        "requested_input_kind",
        "operator_value_collected",
        "explicit_operator_value_present",
        "template_accepted_as_value",
        "authority_granted",
        "scope",
        "decision_value_templates",
        "template_controls",
        "authority_denials",
        "effect_boundary",
        "validators",
    )
    for field_name in comparable_fields:
        if fixture.get(field_name) != produced_template.get(field_name):
            errors.append(f"fixture does not match produced operator decision value template field: {field_name}")


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
    """Run the explicit operator decision value template validator."""
    args = build_arg_parser().parse_args(argv)
    validation, produced_template = validate_live_producer_operator_decision_value_template(
        schema_path=args.schema,
        fixture_path=args.fixture,
    )
    if args.json:
        payload = validation.as_dict()
        payload["produced_template"] = produced_template
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif validation.ok:
        print("AGENTIC SERVICE HARNESS LIVE PRODUCER OPERATOR DECISION VALUE TEMPLATE VALID")
    else:
        print(
            "AGENTIC SERVICE HARNESS LIVE PRODUCER OPERATOR DECISION VALUE TEMPLATE INVALID "
            f"errors={list(validation.errors)}"
        )
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
