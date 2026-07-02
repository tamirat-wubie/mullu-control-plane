#!/usr/bin/env python3
"""Validate Agentic Service Harness live producer evidence packet intake.

Purpose: prove the live producer evidence packet intake is read-only,
non-authorizing, and blocked until all required witness packets exist.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/agentic_service_harness_live_producer_evidence_packet_intake.schema.json,
examples/agentic_service_harness_live_producer_evidence_packet_intake.local.json,
and scripts.validate_schemas.
Invariants:
  - Intake remains `AwaitingEvidence` and non-terminal.
  - All required witness packet refs remain future refs.
  - Live execution, runtime writes, mutation routes, and external effects stay denied.
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
from scripts.validate_agentic_service_harness_live_producer_operator_response_witness import (  # noqa: E402
    validate_live_producer_operator_response_witness,
)


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "agentic_service_harness_live_producer_evidence_packet_intake.schema.json"
DEFAULT_FIXTURE = REPO_ROOT / "examples" / "agentic_service_harness_live_producer_evidence_packet_intake.local.json"
PACKET_ID = "agentic-service-harness-live-producer-evidence-packet-intake"
PACKET_FIXTURE_REF = "examples/agentic_service_harness_live_producer_evidence_packet_intake.local.json"
PACKET_VALIDATOR_COMMAND = "python scripts/validate_agentic_service_harness_live_producer_evidence_packet_intake.py"
OPERATOR_RESPONSE_WITNESS_REF = (
    "examples/agentic_service_harness_live_producer_operator_response_witness.local.json"
)
OPERATOR_RESPONSE_VALIDATOR_ID = "agentic-service-harness-live-producer-operator-response-witness"
OPERATOR_RESPONSE_VALIDATOR_COMMAND = (
    "python scripts/validate_agentic_service_harness_live_producer_operator_response_witness.py"
)
REQUIRED_WITNESS_KINDS = (
    "effect_receipt",
    "external_adapter_evidence",
    "secret_handoff",
    "rollback_proof",
)
FALSE_AUTHORITY_FLAGS = (
    "ui_created",
    "mutation_endpoints_admitted",
    "external_adapter_integrated",
    "branch_write_enabled",
    "pull_request_creation_enabled",
    "deployment_enabled",
    "dns_mutation_enabled",
    "secret_mutation_enabled",
    "destructive_operation_enabled",
    "runtime_state_written",
)
FORBIDDEN_MUTATION_ROUTE = re.compile(r"\b(?:POST|PUT|PATCH|DELETE)\s+/api\b", re.IGNORECASE)
FORBIDDEN_IMPLEMENTATION_CLAIM = re.compile(r"\blive_producer_implemented=true\b", re.IGNORECASE)
FORBIDDEN_CREDENTIAL_VALUE_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]+PRIVATE KEY-----"),
    re.compile(r"\bghp_[A-Za-z0-9_]+\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]+\b"),
    re.compile(r"\bsk-[A-Za-z0-9_=-]{8,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{8,}\b"),
    re.compile(r"\b(access_token|api_key|password|private_key|refresh_token)="),
)


@dataclass(frozen=True, slots=True)
class LiveProducerEvidencePacketIntakeValidation:
    """Validation result for the live producer evidence packet intake."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    fixture_path: str
    packet_id: str
    source_preflight_count: int
    witness_packet_requirement_count: int
    missing_evidence_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_live_producer_evidence_packet_intake(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    fixture_path: Path = DEFAULT_FIXTURE,
) -> tuple[LiveProducerEvidencePacketIntakeValidation, dict[str, Any]]:
    """Validate the checked-in evidence packet intake fixture."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "evidence packet intake schema", errors)
    fixture = _load_json_object(fixture_path, "evidence packet intake fixture", errors)
    response_validation, response_witness = validate_live_producer_operator_response_witness()
    errors.extend(f"source operator response witness: {error}" for error in response_validation.errors)
    if schema and fixture:
        errors.extend(f"{_path_label(fixture_path)}: {error}" for error in _validate_schema_instance(schema, fixture))
        _validate_intake_semantics(fixture, response_witness, errors, _path_label(fixture_path))

    source_preflights = fixture.get("source_preflights")
    witness_packet_requirements = fixture.get("witness_packet_requirements")
    missing_evidence = fixture.get("missing_evidence")
    validation = LiveProducerEvidencePacketIntakeValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        fixture_path=_path_label(fixture_path),
        packet_id=str(fixture.get("packet_id", "")),
        source_preflight_count=len(source_preflights) if isinstance(source_preflights, list) else 0,
        witness_packet_requirement_count=(
            len(witness_packet_requirements) if isinstance(witness_packet_requirements, list) else 0
        ),
        missing_evidence_count=len(missing_evidence) if isinstance(missing_evidence, list) else 0,
    )
    return validation, fixture


def _validate_intake_semantics(
    packet: Mapping[str, Any],
    response_witness: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    if packet.get("packet_id") != PACKET_ID:
        errors.append(f"{label}: packet_id mismatch")
    for field_name, expected_value in (
        ("solver_outcome", "AwaitingEvidence"),
        ("packet_status", "blocked_awaiting_witness_packets"),
        ("intake_decision", "blocked_until_all_required_witness_packets_exist"),
        ("planning_only", True),
        ("read_only", True),
        ("live_producer_implemented", False),
        ("authority_granted", False),
        ("terminal_closure", False),
    ):
        if packet.get(field_name) != expected_value:
            errors.append(f"{label}: {field_name} must be {expected_value!r}")
    _validate_source_preflights(packet, errors, label)
    _validate_operator_response_collection_binding(packet, response_witness, errors, label)
    _validate_witness_packet_requirements(packet, errors, label)
    _validate_missing_evidence(packet, errors, label)
    _validate_denials(packet, errors, label)
    _validate_validator_ref(packet, errors, label)
    _validate_secret_surface(packet, errors, label)
    _validate_no_mutation_routes(packet, errors, label)
    _validate_no_implementation_claim(packet, errors, label)


def _validate_source_preflights(packet: Mapping[str, Any], errors: list[str], label: str) -> None:
    source_preflights = packet.get("source_preflights")
    if not isinstance(source_preflights, list):
        errors.append(f"{label}: source_preflights must be a list")
        return
    observed_kinds = tuple(entry.get("witness_kind") for entry in source_preflights if isinstance(entry, Mapping))
    if observed_kinds != REQUIRED_WITNESS_KINDS:
        errors.append(f"{label}: source_preflights witness order mismatch")
    for entry in source_preflights:
        if not isinstance(entry, Mapping):
            errors.append(f"{label}: source_preflights entries must be objects")
            continue
        witness_kind = str(entry.get("witness_kind", ""))
        if entry.get("preflight_status") != "AwaitingEvidence":
            errors.append(f"{label}: {witness_kind} preflight_status must be AwaitingEvidence")
        if entry.get("blocks_live_producer") is not True:
            errors.append(f"{label}: {witness_kind} must block live producer")
        if entry.get("authority_granted") is not False:
            errors.append(f"{label}: {witness_kind} authority_granted must be false")
        preflight_ref = entry.get("preflight_ref")
        if isinstance(preflight_ref, str) and not (REPO_ROOT / preflight_ref).is_file():
            errors.append(f"{label}: {witness_kind} preflight_ref must exist")


def _validate_operator_response_collection_binding(
    packet: Mapping[str, Any],
    response_witness: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    binding = _mapping(packet.get("operator_response_collection_binding"))
    source_binding = _mapping(response_witness.get("approval_request_collection_binding"))
    if not binding:
        errors.append(f"{label}: operator_response_collection_binding must be an object")
        return
    expected_values = {
        "binding_id": "binding.evidence_packet_intake.operator_response_collection",
        "source_response_witness_id": response_witness.get("response_witness_id", ""),
        "source_response_witness_ref": OPERATOR_RESPONSE_WITNESS_REF,
        "source_response_validator_id": OPERATOR_RESPONSE_VALIDATOR_ID,
        "source_response_validator_command": OPERATOR_RESPONSE_VALIDATOR_COMMAND,
        "source_approval_request_collection_binding_id": source_binding.get("binding_id", ""),
        "source_approval_request_collection_status": source_binding.get("binding_status", ""),
        "source_response_status": response_witness.get("response_status", ""),
        "source_response_record_collected": response_witness.get("response_record_collected"),
        "source_approval_satisfied": response_witness.get("approval_satisfied"),
        "source_authority_granted": response_witness.get("authority_granted"),
        "source_live_execution_authorized": _mapping(response_witness.get("authority_denials")).get(
            "live_execution_authorized"
        ),
        "intake_packet_id": PACKET_ID,
        "intake_packet_ref": PACKET_FIXTURE_REF,
        "intake_validator_id": PACKET_ID,
        "intake_validator_command": PACKET_VALIDATOR_COMMAND,
        "binding_status": "AwaitingEvidence",
        "witness_packets_collected": False,
        "authority_granted": False,
        "live_execution_authorized": False,
        "blocks_live_producer": True,
    }
    for field_name, expected_value in expected_values.items():
        if binding.get(field_name) != expected_value:
            errors.append(f"{label}: operator_response_collection_binding.{field_name} mismatch")
    for artifact_field in ("source_response_witness_ref", "intake_packet_ref"):
        artifact_ref = binding.get(artifact_field)
        if isinstance(artifact_ref, str) and not (REPO_ROOT / artifact_ref).is_file():
            errors.append(f"{label}: operator_response_collection_binding.{artifact_field} must exist")


def _validate_witness_packet_requirements(packet: Mapping[str, Any], errors: list[str], label: str) -> None:
    requirements = packet.get("witness_packet_requirements")
    if not isinstance(requirements, list):
        errors.append(f"{label}: witness_packet_requirements must be a list")
        return
    observed_kinds = tuple(entry.get("witness_kind") for entry in requirements if isinstance(entry, Mapping))
    if observed_kinds != REQUIRED_WITNESS_KINDS:
        errors.append(f"{label}: witness_packet_requirements witness order mismatch")
    for entry in requirements:
        if not isinstance(entry, Mapping):
            errors.append(f"{label}: witness_packet_requirements entries must be objects")
            continue
        witness_kind = str(entry.get("witness_kind", ""))
        if not str(entry.get("required_packet_ref", "")).startswith("future://"):
            errors.append(f"{label}: {witness_kind} required_packet_ref must stay future://")
        if entry.get("status") != "AwaitingEvidence":
            errors.append(f"{label}: {witness_kind} status must be AwaitingEvidence")
        if entry.get("blocks_live_producer") is not True:
            errors.append(f"{label}: {witness_kind} must block live producer")
        if entry.get("authority_granted") is not False:
            errors.append(f"{label}: {witness_kind} authority_granted must be false")


def _validate_missing_evidence(packet: Mapping[str, Any], errors: list[str], label: str) -> None:
    missing_evidence = packet.get("missing_evidence")
    if not isinstance(missing_evidence, list):
        errors.append(f"{label}: missing_evidence must be a list")
        return
    expected_ids = tuple(f"{witness_kind}_packet" for witness_kind in REQUIRED_WITNESS_KINDS)
    observed_ids = tuple(entry.get("evidence_id") for entry in missing_evidence if isinstance(entry, Mapping))
    if observed_ids != expected_ids:
        errors.append(f"{label}: missing_evidence order mismatch")
    for entry in missing_evidence:
        if not isinstance(entry, Mapping):
            errors.append(f"{label}: missing_evidence entries must be objects")
            continue
        evidence_id = str(entry.get("evidence_id", ""))
        if entry.get("status") != "AwaitingEvidence":
            errors.append(f"{label}: {evidence_id} status must be AwaitingEvidence")
        if entry.get("blocks_live_producer") is not True:
            errors.append(f"{label}: {evidence_id} must block live producer")


def _validate_denials(packet: Mapping[str, Any], errors: list[str], label: str) -> None:
    authority_denials = _mapping(packet.get("authority_denials"))
    effect_boundary = _mapping(packet.get("effect_boundary"))
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
        errors.append(f"{label}: authority_denials.live_execution_authorized must be false")
    if effect_boundary and effect_boundary.get("network_policy") != "none":
        errors.append(f"{label}: effect_boundary.network_policy must be none")


def _validate_validator_ref(packet: Mapping[str, Any], errors: list[str], label: str) -> None:
    validators = packet.get("validators")
    if not isinstance(validators, list) or not validators:
        errors.append(f"{label}: validators must be a non-empty list")
        return
    validator = validators[0] if isinstance(validators[0], Mapping) else {}
    if validator.get("validator_id") != PACKET_ID:
        errors.append(f"{label}: validator_id mismatch")
    if validator.get("command") != PACKET_VALIDATOR_COMMAND:
        errors.append(f"{label}: validator command mismatch")
    if validator.get("required_for_closure") is not True:
        errors.append(f"{label}: validator required_for_closure must be true")


def _validate_secret_surface(payload: Any, errors: list[str], label: str) -> None:
    for path, value in _walk_strings(payload):
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
    """Run the live producer evidence packet intake validator."""
    args = build_arg_parser().parse_args(argv)
    validation, fixture = validate_live_producer_evidence_packet_intake(
        schema_path=args.schema,
        fixture_path=args.fixture,
    )
    if args.json:
        payload = validation.as_dict()
        payload["fixture"] = fixture
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif validation.ok:
        print("AGENTIC SERVICE HARNESS LIVE PRODUCER EVIDENCE PACKET INTAKE VALID")
    else:
        print(
            "AGENTIC SERVICE HARNESS LIVE PRODUCER EVIDENCE PACKET INTAKE INVALID "
            f"errors={list(validation.errors)}"
        )
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
