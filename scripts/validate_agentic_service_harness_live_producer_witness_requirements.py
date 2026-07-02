#!/usr/bin/env python3
"""Validate Agentic Service Harness live producer witness requirements.

Purpose: prove the witnesses required before live producer implementation are
explicit, missing, and authority-denying.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: gateway.agentic_service_harness_live_producer_witness_requirements,
schemas/agentic_service_harness_live_producer_witness_requirements.schema.json,
examples/agentic_service_harness_live_producer_witness_requirements.local.json,
and scripts.validate_agentic_service_harness_live_producer_admission_gate.
Invariants:
  - Witness requirements are read-only, non-terminal, and `AwaitingEvidence`.
  - Required witnesses do not grant authority.
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

from gateway.agentic_service_harness_live_producer_witness_requirements import (  # noqa: E402
    FALSE_AUTHORITY_FLAGS,
    GOVERNED_WITNESS_COLLECTION,
    REQUIRED_WITNESS_KINDS,
    WITNESS_REQUIREMENTS_ID,
    project_admission_gate_to_witness_requirements,
)
from scripts.validate_agentic_service_harness_live_producer_admission_gate import (  # noqa: E402
    validate_live_producer_admission_gate,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "agentic_service_harness_live_producer_witness_requirements.schema.json"
DEFAULT_FIXTURE = REPO_ROOT / "examples" / "agentic_service_harness_live_producer_witness_requirements.local.json"
ALLOWED_SECRET_KEYS = {
    "secret_handoff",
    "secret_handoff_ref",
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
class LiveProducerWitnessRequirementsValidation:
    """Validation result for the live producer witness requirements packet."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    fixture_path: str
    requirements_id: str
    witness_count: int
    governed_collection_count: int
    authority_denial_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_live_producer_witness_requirements(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    fixture_path: Path = DEFAULT_FIXTURE,
) -> tuple[LiveProducerWitnessRequirementsValidation, dict[str, Any]]:
    """Validate the checked-in witness requirements and produced packet."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "witness requirements schema", errors)
    fixture = _load_json_object(fixture_path, "witness requirements fixture", errors)
    admission_validation, admission_gate = validate_live_producer_admission_gate()
    errors.extend(f"source admission gate: {error}" for error in admission_validation.errors)

    produced_requirements: dict[str, Any] = {}
    if admission_gate:
        produced_requirements = project_admission_gate_to_witness_requirements(admission_gate)

    if schema and fixture:
        errors.extend(f"{_path_label(fixture_path)}: {error}" for error in _validate_schema_instance(schema, fixture))
        _validate_requirements_semantics(fixture, errors, _path_label(fixture_path))
    if schema and produced_requirements:
        errors.extend(
            f"produced witness requirements: {error}"
            for error in _validate_schema_instance(schema, produced_requirements)
        )
        _validate_requirements_semantics(produced_requirements, errors, "produced witness requirements")
    if fixture and produced_requirements:
        _validate_fixture_matches_produced(fixture, produced_requirements, errors)

    observed = produced_requirements or fixture
    witnesses = observed.get("witnesses")
    validation = LiveProducerWitnessRequirementsValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        fixture_path=_path_label(fixture_path),
        requirements_id=str(observed.get("requirements_id", "")),
        witness_count=len(witnesses) if isinstance(witnesses, list) else 0,
        governed_collection_count=(
            len(observed.get("governed_witness_collection"))
            if isinstance(observed.get("governed_witness_collection"), list)
            else 0
        ),
        authority_denial_count=len(FALSE_AUTHORITY_FLAGS) + 1,
    )
    return validation, produced_requirements


def _validate_requirements_semantics(
    requirements: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    if requirements.get("requirements_id") != WITNESS_REQUIREMENTS_ID:
        errors.append(f"{label}: requirements_id mismatch")
    if requirements.get("solver_outcome") != "AwaitingEvidence":
        errors.append(f"{label}: solver_outcome must be AwaitingEvidence")
    if requirements.get("admission_decision") != "blocked":
        errors.append(f"{label}: admission_decision must be blocked")
    for field_name, expected_value in (
        ("planning_only", True),
        ("read_only", True),
        ("live_producer_implemented", False),
        ("report_is_not_terminal_closure", True),
        ("terminal_closure", False),
    ):
        if requirements.get(field_name) is not expected_value:
            errors.append(f"{label}: {field_name} must be {str(expected_value).lower()}")
    _validate_scope(requirements, errors, label)
    _validate_witnesses(requirements, errors, label)
    _validate_governed_witness_collection(requirements, errors, label)
    _validate_denials(requirements, errors, label)
    _validate_secret_surface(requirements, errors, label)
    _validate_no_mutation_routes(requirements, errors, label)
    _validate_no_implementation_claim(requirements, errors, label)


def _validate_scope(requirements: Mapping[str, Any], errors: list[str], label: str) -> None:
    scope = _mapping(requirements.get("scope"))
    if not scope:
        errors.append(f"{label}: scope must be an object")
        return
    if scope.get("read_only") is not True:
        errors.append(f"{label}: scope.read_only must be true")
    for field_name in ("tenant_id", "organization_id", "project_id", "repository_connection_id"):
        if not scope.get(field_name):
            errors.append(f"{label}: scope.{field_name} required")


def _validate_witnesses(requirements: Mapping[str, Any], errors: list[str], label: str) -> None:
    witnesses = requirements.get("witnesses")
    if not isinstance(witnesses, list):
        errors.append(f"{label}: witnesses must be a list")
        return
    observed_kinds = [witness.get("witness_kind") for witness in witnesses if isinstance(witness, Mapping)]
    if tuple(observed_kinds) != REQUIRED_WITNESS_KINDS:
        errors.append(f"{label}: witness kinds must match required order")
    for witness in witnesses:
        if not isinstance(witness, Mapping):
            errors.append(f"{label}: witness entries must be objects")
            continue
        witness_kind = str(witness.get("witness_kind", ""))
        if witness.get("required") is not True:
            errors.append(f"{label}: {witness_kind} required must be true")
        if witness.get("status") != "AwaitingEvidence":
            errors.append(f"{label}: {witness_kind} status must be AwaitingEvidence")
        if witness.get("admission_effect") != "blocks_live_producer":
            errors.append(f"{label}: {witness_kind} must block live producer")
        if witness.get("authority_granted") is not False:
            errors.append(f"{label}: {witness_kind} authority_granted must be false")
        if not witness.get("evidence_ref"):
            errors.append(f"{label}: {witness_kind} evidence_ref required")


def _validate_governed_witness_collection(
    requirements: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    collection = requirements.get("governed_witness_collection")
    witnesses = requirements.get("witnesses")
    if not isinstance(collection, list):
        errors.append(f"{label}: governed_witness_collection must be a list")
        return
    if not isinstance(witnesses, list):
        errors.append(f"{label}: governed_witness_collection requires witness list")
        return
    witness_evidence_by_kind = {
        str(witness.get("witness_kind")): str(witness.get("evidence_ref"))
        for witness in witnesses
        if isinstance(witness, Mapping)
    }
    observed_kinds = [entry.get("witness_kind") for entry in collection if isinstance(entry, Mapping)]
    if tuple(observed_kinds) != REQUIRED_WITNESS_KINDS:
        errors.append(f"{label}: governed witness collection must match required witness order")
    expected_by_kind = {entry["witness_kind"]: entry for entry in GOVERNED_WITNESS_COLLECTION}
    for entry in collection:
        if not isinstance(entry, Mapping):
            errors.append(f"{label}: governed witness collection entries must be objects")
            continue
        witness_kind = str(entry.get("witness_kind", ""))
        expected = expected_by_kind.get(witness_kind)
        if expected is None:
            errors.append(f"{label}: governed witness collection has unknown witness kind {witness_kind!r}")
            continue
        if entry.get("collection_id") != f"collection.{witness_kind}":
            errors.append(f"{label}: {witness_kind} collection_id mismatch")
        if entry.get("requirements_evidence_ref") != witness_evidence_by_kind.get(witness_kind):
            errors.append(f"{label}: {witness_kind} requirements_evidence_ref must match witness evidence_ref")
        for field_name in ("governed_artifact_ref", "validator_id", "validator_command"):
            if entry.get(field_name) != expected[field_name]:
                errors.append(f"{label}: {witness_kind} {field_name} mismatch")
        if entry.get("status") != "AwaitingEvidence":
            errors.append(f"{label}: {witness_kind} collection status must be AwaitingEvidence")
        if entry.get("authority_granted") is not False:
            errors.append(f"{label}: {witness_kind} collection authority_granted must be false")
        if entry.get("blocks_live_producer") is not True:
            errors.append(f"{label}: {witness_kind} collection must block live producer")
        artifact_ref = str(entry.get("governed_artifact_ref", ""))
        if artifact_ref and not (REPO_ROOT / artifact_ref).is_file():
            errors.append(f"{label}: {witness_kind} governed artifact missing: {artifact_ref}")


def _validate_denials(requirements: Mapping[str, Any], errors: list[str], label: str) -> None:
    authority_denials = _mapping(requirements.get("authority_denials"))
    effect_boundary = _mapping(requirements.get("effect_boundary"))
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
    produced_requirements: Mapping[str, Any],
    errors: list[str],
) -> None:
    comparable_fields = (
        "requirements_id",
        "solver_outcome",
        "source_admission_gate_ref",
        "admission_decision",
        "scope",
        "witnesses",
        "governed_witness_collection",
        "authority_denials",
        "effect_boundary",
        "validators",
    )
    for field_name in comparable_fields:
        if fixture.get(field_name) != produced_requirements.get(field_name):
            errors.append(f"fixture does not match produced witness requirements field: {field_name}")


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
    """Run the live producer witness requirements validator."""
    args = build_arg_parser().parse_args(argv)
    validation, produced_requirements = validate_live_producer_witness_requirements(
        schema_path=args.schema,
        fixture_path=args.fixture,
    )
    if args.json:
        payload = validation.as_dict()
        payload["produced_requirements"] = produced_requirements
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif validation.ok:
        print("AGENTIC SERVICE HARNESS LIVE PRODUCER WITNESS REQUIREMENTS VALID")
    else:
        print(
            "AGENTIC SERVICE HARNESS LIVE PRODUCER WITNESS REQUIREMENTS INVALID "
            f"errors={list(validation.errors)}"
        )
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
