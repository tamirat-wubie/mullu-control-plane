#!/usr/bin/env python3
"""Validate Agentic Service Harness live producer execution authority admission.

Purpose: keep live producer execution authority blocked until all required
live authority evidence components exist.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: execution authority admission schema, fixture, source live-producer
validators, and scripts.validate_schemas.
Invariants: no live execution, connector call, receipt append, runtime write,
secret access, mutation route, or terminal closure is authorized.
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

from scripts.validate_agentic_service_harness_live_producer_admission_gate import validate_live_producer_admission_gate  # noqa: E402
from scripts.validate_agentic_service_harness_live_producer_effect_receipt_packet import validate_live_producer_effect_receipt_packet  # noqa: E402
from scripts.validate_agentic_service_harness_live_producer_external_adapter_evidence_packet import validate_live_producer_external_adapter_evidence_packet  # noqa: E402
from scripts.validate_agentic_service_harness_live_producer_operator_decision_value_record import validate_live_producer_operator_decision_value_record  # noqa: E402
from scripts.validate_agentic_service_harness_live_producer_rollback_proof_packet import validate_live_producer_rollback_proof_packet  # noqa: E402
from scripts.validate_agentic_service_harness_live_producer_secret_handoff_packet import validate_live_producer_secret_handoff_packet  # noqa: E402
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "agentic_service_harness_live_producer_execution_authority_admission.schema.json"
DEFAULT_FIXTURE = REPO_ROOT / "examples" / "agentic_service_harness_live_producer_execution_authority_admission.awaiting_evidence.json"
ADMISSION_ID = "agentic-service-harness-live-producer-execution-authority-admission"
ADMISSION_STATUS = "blocked_awaiting_live_execution_authority_components"
REQUIRED_COMPONENT_IDS = (
    "admission_gate_ref",
    "operator_approval_ref",
    "effect_receipt_packet_ref",
    "external_adapter_evidence_packet_ref",
    "secret_handoff_packet_ref",
    "rollback_proof_packet_ref",
    "uao_admission_ref",
    "life_meaning_judgment_ref",
    "temporal_lease_ref",
)
FALSE_FLAGS = (
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
ALLOWED_SECRET_KEYS = {"secret_handoff_packet_ref", "secret_mutation_enabled"}
FORBIDDEN_SECRET_KEY_TOKENS = ("access_token", "api_key", "credential", "password", "private_key", "refresh_token", "secret", "token")
FORBIDDEN_CREDENTIAL_VALUE_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]+PRIVATE KEY-----"),
    re.compile(r"\bghp_[A-Za-z0-9_]+\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]+\b"),
    re.compile(r"\bsk-[A-Za-z0-9_=-]{8,}\b"),
    re.compile(r"\b(access_token|api_key|password|private_key|refresh_token)="),
)
FORBIDDEN_MUTATION_ROUTE = re.compile(r"\b(?:POST|PUT|PATCH|DELETE)\s+/api\b", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class LiveProducerExecutionAuthorityAdmissionValidation:
    """Validation result for the live producer execution authority admission."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    fixture_path: str
    admission_id: str
    admission_status: str
    required_component_count: int
    missing_evidence_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_live_producer_execution_authority_admission(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    fixture_path: Path = DEFAULT_FIXTURE,
) -> tuple[LiveProducerExecutionAuthorityAdmissionValidation, dict[str, Any]]:
    """Validate the checked-in live producer execution authority admission."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "execution authority admission schema", errors)
    fixture = _load_json_object(fixture_path, "execution authority admission fixture", errors)
    _validate_source_surfaces(errors)

    if schema and fixture:
        errors.extend(f"{_path_label(fixture_path)}: {error}" for error in _validate_schema_instance(schema, fixture))
        _validate_semantics(fixture, errors, _path_label(fixture_path))

    required_components = fixture.get("required_components")
    missing_evidence = fixture.get("missing_evidence")
    validation = LiveProducerExecutionAuthorityAdmissionValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        fixture_path=_path_label(fixture_path),
        admission_id=str(fixture.get("admission_id", "")),
        admission_status=str(fixture.get("admission_status", "")),
        required_component_count=len(required_components) if isinstance(required_components, list) else 0,
        missing_evidence_count=len(missing_evidence) if isinstance(missing_evidence, list) else 0,
    )
    return validation, fixture


def _validate_source_surfaces(errors: list[str]) -> None:
    gate_validation, _gate = validate_live_producer_admission_gate()
    operator_validation, _operator_record = validate_live_producer_operator_decision_value_record()
    effect_validation, _effect = validate_live_producer_effect_receipt_packet()
    adapter_validation, _adapter = validate_live_producer_external_adapter_evidence_packet()
    secret_validation, _secret = validate_live_producer_secret_handoff_packet()
    rollback_validation, _rollback = validate_live_producer_rollback_proof_packet()

    source_results = (
        ("admission gate", gate_validation.ok, gate_validation.errors),
        ("operator decision value record", operator_validation.ok, operator_validation.errors),
        ("effect receipt packet", effect_validation.ok, effect_validation.errors),
        ("external adapter evidence packet", adapter_validation.ok, adapter_validation.errors),
        ("secret handoff packet", secret_validation.ok, secret_validation.errors),
        ("rollback proof packet", rollback_validation.ok, rollback_validation.errors),
    )
    for source_name, ok, source_errors in source_results:
        if ok is not True:
            errors.extend(f"source {source_name}: {error}" for error in source_errors)
    if gate_validation.gate_state != "blocked_pending_live_authority":
        errors.append("source admission gate must remain blocked_pending_live_authority")
    if operator_validation.approval_status != "Satisfied":
        errors.append("source operator approval must remain Satisfied")
    for source_name, validation in (
        ("effect receipt packet", effect_validation),
        ("external adapter evidence packet", adapter_validation),
        ("secret handoff packet", secret_validation),
        ("rollback proof packet", rollback_validation),
    ):
        if validation.packet_status.startswith("blocked_awaiting_") is not True:
            errors.append(f"source {source_name} must remain blocked AwaitingEvidence")


def _validate_semantics(fixture: Mapping[str, Any], errors: list[str], label: str) -> None:
    for field_name, expected in (
        ("admission_id", ADMISSION_ID),
        ("solver_outcome", "AwaitingEvidence"),
        ("admission_status", ADMISSION_STATUS),
        ("source_admission_gate_state", "blocked_pending_live_authority"),
        ("planning_only", True),
        ("read_only", True),
        ("live_producer_implemented", False),
        ("live_execution_authorized", False),
        ("authority_granted", False),
        ("terminal_closure", False),
    ):
        if fixture.get(field_name) != expected:
            errors.append(f"{label}: {field_name} must be {expected!r}")
    _validate_components(fixture.get("required_components"), "component_id", errors, label)
    _validate_components(fixture.get("missing_evidence"), "evidence_id", errors, label)
    _validate_denials(_mapping(fixture.get("authority_denials")), errors, label, "authority_denials")
    _validate_denials(_mapping(fixture.get("effect_boundary")), errors, label, "effect_boundary")
    if _mapping(fixture.get("effect_boundary")).get("network_policy") != "none":
        errors.append(f"{label}: effect_boundary.network_policy must be none")
    validators = fixture.get("validators")
    validator = validators[0] if isinstance(validators, list) and validators and isinstance(validators[0], Mapping) else {}
    if validator.get("command") != "python scripts/validate_agentic_service_harness_live_producer_execution_authority_admission.py":
        errors.append(f"{label}: validator command mismatch")
    _validate_secret_surface(fixture, errors, label)
    _validate_no_mutation_routes(fixture, errors, label)


def _validate_components(value: Any, id_key: str, errors: list[str], label: str) -> None:
    if not isinstance(value, list):
        errors.append(f"{label}: {id_key} collection must be a list")
        return
    observed_ids = tuple(item.get(id_key) for item in value if isinstance(item, Mapping))
    if observed_ids != REQUIRED_COMPONENT_IDS:
        errors.append(f"{label}: {id_key} order mismatch")
    for item in value:
        if not isinstance(item, Mapping):
            errors.append(f"{label}: {id_key} entries must be objects")
            continue
        item_id = str(item.get(id_key, ""))
        if item.get("status") != "AwaitingEvidence":
            errors.append(f"{label}: {item_id} status must be AwaitingEvidence")
        if item.get("blocks_live_execution") is not True:
            errors.append(f"{label}: {item_id} must block live execution")
        if id_key == "component_id" and not str(item.get("required_ref", "")).startswith("future://"):
            errors.append(f"{label}: {item_id} required_ref must stay future://")


def _validate_denials(value: Mapping[str, Any], errors: list[str], label: str, object_name: str) -> None:
    if not value:
        errors.append(f"{label}: {object_name} must be an object")
        return
    for flag in FALSE_FLAGS:
        if value.get(flag) is not False:
            errors.append(f"{label}: {object_name}.{flag} must be false")


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
        return path.name


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the live producer execution authority admission validator."""
    args = build_arg_parser().parse_args(argv)
    validation, fixture = validate_live_producer_execution_authority_admission(
        schema_path=args.schema,
        fixture_path=args.fixture,
    )
    if args.json:
        payload = validation.as_dict()
        payload["fixture"] = fixture
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif validation.ok:
        print("AGENTIC SERVICE HARNESS LIVE PRODUCER EXECUTION AUTHORITY ADMISSION VALID")
    else:
        print(f"AGENTIC SERVICE HARNESS LIVE PRODUCER EXECUTION AUTHORITY ADMISSION INVALID errors={list(validation.errors)}")
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
