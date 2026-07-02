#!/usr/bin/env python3
"""Validate Agentic Service Harness live producer external adapter evidence packet.

Purpose: define the external adapter evidence witness packet while keeping
provider identity, adapter descriptor, capability scope, egress policy,
redaction proof, signed dispatch, and effect receipt linkage AwaitingEvidence.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/agentic_service_harness_live_producer_external_adapter_evidence_packet.schema.json,
examples/agentic_service_harness_live_producer_external_adapter_evidence_packet.awaiting_evidence.json,
scripts.validate_agentic_service_harness_live_producer_external_adapter_evidence_preflight,
and scripts.validate_schemas.
Invariants:
  - Packet remains AwaitingEvidence and non-terminal.
  - Required component refs remain future refs.
  - Adapter integration, network egress, signed dispatch, credentials, mutation routes,
    live probes, and live execution fail closed.
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

from scripts.validate_agentic_service_harness_live_producer_external_adapter_evidence_preflight import (  # noqa: E402
    validate_live_producer_external_adapter_evidence_preflight,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = (
    REPO_ROOT
    / "schemas"
    / "agentic_service_harness_live_producer_external_adapter_evidence_packet.schema.json"
)
DEFAULT_FIXTURE = (
    REPO_ROOT
    / "examples"
    / "agentic_service_harness_live_producer_external_adapter_evidence_packet.awaiting_evidence.json"
)
PACKET_ID = "agentic-service-harness-live-producer-external-adapter-evidence-packet"
REQUIRED_COMPONENT_IDS = (
    "external_adapter_evidence_ref",
    "provider_identity_ref",
    "adapter_descriptor_ref",
    "capability_scope_ref",
    "egress_policy_ref",
    "redaction_ref",
    "effect_receipt_ref",
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
ALLOWED_CREDENTIAL_KEYS = {
    "adapter_credentials_present",
    "adapter_credentials_serialized",
    "secret_mutation_enabled",
}
FORBIDDEN_CREDENTIAL_KEY_TOKENS = (
    "access_token",
    "api_key",
    "credential",
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
FORBIDDEN_LIVE_CLAIM = re.compile(
    r"\b(?:external_adapter_integrated|adapter_credentials_present|adapter_credentials_serialized|"
    r"network_egress_opened|signed_dispatch_collected|live_adapter_probe_executed|"
    r"live_producer_implemented|live_execution_authorized)=true\b",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class LiveProducerExternalAdapterEvidencePacketValidation:
    """Validation result for the live producer external adapter evidence packet."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    fixture_path: str
    packet_id: str
    packet_status: str
    required_component_count: int
    missing_evidence_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_live_producer_external_adapter_evidence_packet(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    fixture_path: Path = DEFAULT_FIXTURE,
) -> tuple[LiveProducerExternalAdapterEvidencePacketValidation, dict[str, Any]]:
    """Validate the checked-in live producer external adapter evidence packet."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "external adapter evidence packet schema", errors)
    fixture = _load_json_object(fixture_path, "external adapter evidence packet fixture", errors)
    source_validation = validate_live_producer_external_adapter_evidence_preflight()
    errors.extend(f"source external adapter evidence preflight: {error}" for error in source_validation.errors)
    if getattr(source_validation, "external_adapter_evidence_status", "") != "AwaitingEvidence":
        errors.append("source external adapter evidence preflight must remain AwaitingEvidence")

    if schema and fixture:
        errors.extend(f"{_path_label(fixture_path)}: {error}" for error in _validate_schema_instance(schema, fixture))
        _validate_packet_semantics(fixture, errors, _path_label(fixture_path))

    components = fixture.get("required_components")
    missing_evidence = fixture.get("missing_evidence")
    validation = LiveProducerExternalAdapterEvidencePacketValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        fixture_path=_path_label(fixture_path),
        packet_id=str(fixture.get("packet_id", "")),
        packet_status=str(fixture.get("packet_status", "")),
        required_component_count=len(components) if isinstance(components, list) else 0,
        missing_evidence_count=len(missing_evidence) if isinstance(missing_evidence, list) else 0,
    )
    return validation, fixture


def _validate_packet_semantics(packet: Mapping[str, Any], errors: list[str], label: str) -> None:
    for field_name, expected_value in (
        ("packet_id", PACKET_ID),
        ("solver_outcome", "AwaitingEvidence"),
        ("packet_status", "blocked_awaiting_external_adapter_evidence_components"),
        ("source_preflight_status", "AwaitingEvidence"),
        ("planning_only", True),
        ("read_only", True),
        ("live_producer_implemented", False),
        ("external_adapter_integrated", False),
        ("adapter_credentials_present", False),
        ("adapter_credentials_serialized", False),
        ("network_egress_opened", False),
        ("signed_dispatch_collected", False),
        ("live_adapter_probe_executed", False),
        ("authority_granted", False),
        ("terminal_closure", False),
    ):
        if packet.get(field_name) != expected_value:
            errors.append(f"{label}: {field_name} must be {expected_value!r}")
    if packet.get("source_preflight_ref") != (
        "examples/agentic_service_harness_live_producer_external_adapter_evidence_preflight.local.json"
    ):
        errors.append(f"{label}: source_preflight_ref mismatch")
    _validate_required_components(packet, errors, label)
    _validate_missing_evidence(packet, errors, label)
    _validate_denials(packet, errors, label)
    _validate_validator_ref(packet, errors, label)
    _validate_credential_surface(packet, errors, label)
    _validate_no_mutation_routes(packet, errors, label)
    _validate_no_live_claim(packet, errors, label)


def _validate_required_components(packet: Mapping[str, Any], errors: list[str], label: str) -> None:
    components = packet.get("required_components")
    if not isinstance(components, list):
        errors.append(f"{label}: required_components must be a list")
        return
    observed_ids = tuple(entry.get("component_id") for entry in components if isinstance(entry, Mapping))
    if observed_ids != REQUIRED_COMPONENT_IDS:
        errors.append(f"{label}: required component order mismatch")
    for entry in components:
        if not isinstance(entry, Mapping):
            errors.append(f"{label}: required component entries must be objects")
            continue
        component_id = str(entry.get("component_id", ""))
        if not str(entry.get("required_ref", "")).startswith("future://"):
            errors.append(f"{label}: {component_id} required_ref must stay future://")
        if entry.get("status") != "AwaitingEvidence":
            errors.append(f"{label}: {component_id} status must be AwaitingEvidence")
        if entry.get("blocks_live_producer") is not True:
            errors.append(f"{label}: {component_id} must block live producer")


def _validate_missing_evidence(packet: Mapping[str, Any], errors: list[str], label: str) -> None:
    missing_evidence = packet.get("missing_evidence")
    if not isinstance(missing_evidence, list):
        errors.append(f"{label}: missing_evidence must be a list")
        return
    observed_ids = tuple(entry.get("evidence_id") for entry in missing_evidence if isinstance(entry, Mapping))
    if observed_ids != REQUIRED_COMPONENT_IDS:
        errors.append(f"{label}: missing evidence order mismatch")
    for entry in missing_evidence:
        if not isinstance(entry, Mapping):
            errors.append(f"{label}: missing evidence entries must be objects")
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
    if validator.get("command") != (
        "python scripts/validate_agentic_service_harness_live_producer_external_adapter_evidence_packet.py"
    ):
        errors.append(f"{label}: validator command mismatch")
    if validator.get("required_for_closure") is not True:
        errors.append(f"{label}: validator required_for_closure must be true")


def _validate_credential_surface(payload: Any, errors: list[str], label: str) -> None:
    for path, key, value in _walk_json(payload):
        key_lower = key.lower()
        if any(token in key_lower for token in FORBIDDEN_CREDENTIAL_KEY_TOKENS) and key_lower not in ALLOWED_CREDENTIAL_KEYS:
            errors.append(f"{label}: forbidden credential-bearing key at {path}")
        if isinstance(value, str):
            for pattern in FORBIDDEN_CREDENTIAL_VALUE_PATTERNS:
                if pattern.search(value):
                    errors.append(f"{label}: credential-like value at {path}")
                    break


def _validate_no_mutation_routes(payload: Any, errors: list[str], label: str) -> None:
    for path, value in _walk_strings(payload):
        if FORBIDDEN_MUTATION_ROUTE.search(value):
            errors.append(f"{label}: mutation route string at {path}")


def _validate_no_live_claim(payload: Any, errors: list[str], label: str) -> None:
    for path, value in _walk_strings(payload):
        if FORBIDDEN_LIVE_CLAIM.search(value):
            errors.append(f"{label}: live adapter claim at {path}")


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
    """Run the live producer external adapter evidence packet validator."""
    args = build_arg_parser().parse_args(argv)
    validation, fixture = validate_live_producer_external_adapter_evidence_packet(
        schema_path=args.schema,
        fixture_path=args.fixture,
    )
    if args.json:
        payload = validation.as_dict()
        payload["fixture"] = fixture
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif validation.ok:
        print("AGENTIC SERVICE HARNESS LIVE PRODUCER EXTERNAL ADAPTER EVIDENCE PACKET VALID")
    else:
        print(
            "AGENTIC SERVICE HARNESS LIVE PRODUCER EXTERNAL ADAPTER EVIDENCE PACKET INVALID "
            f"errors={list(validation.errors)}"
        )
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
