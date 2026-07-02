#!/usr/bin/env python3
"""Validate InceptaDive live producer readiness binding.

Purpose: bind InceptaDive external-effect adapter readiness to the Agentic
Service Harness live-producer evidence packet chain without granting execution
authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/inceptadive_live_producer_readiness_binding.schema.json,
examples/inceptadive_live_producer_readiness_binding.awaiting_evidence.json,
scripts.validate_inceptadive_external_effect_adapter_readiness,
scripts.validate_agentic_service_harness_live_producer_evidence_packet_intake,
scripts.validate_agentic_service_harness_live_producer_effect_receipt_packet,
scripts.validate_agentic_service_harness_live_producer_external_adapter_evidence_packet,
and scripts.validate_schemas.
Invariants:
  - Binding remains AwaitingEvidence and non-terminal.
  - All source validators must pass while reporting AwaitingEvidence.
  - Live execution, authority grants, mutation routes, credentials, and terminal
    closure fail closed.
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

from scripts.validate_agentic_service_harness_live_producer_effect_receipt_packet import (  # noqa: E402
    validate_live_producer_effect_receipt_packet,
)
from scripts.validate_agentic_service_harness_live_producer_evidence_packet_intake import (  # noqa: E402
    validate_live_producer_evidence_packet_intake,
)
from scripts.validate_agentic_service_harness_live_producer_external_adapter_evidence_packet import (  # noqa: E402
    validate_live_producer_external_adapter_evidence_packet,
)
from scripts.validate_inceptadive_external_effect_adapter_readiness import (  # noqa: E402
    validate_inceptadive_external_effect_adapter_readiness,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "inceptadive_live_producer_readiness_binding.schema.json"
DEFAULT_FIXTURE = REPO_ROOT / "examples" / "inceptadive_live_producer_readiness_binding.awaiting_evidence.json"
BINDING_ID = "inceptadive-live-producer-readiness-binding"
REQUIRED_SOURCE_IDS = (
    "inceptadive_external_effect_adapter_readiness",
    "agentic_service_harness_live_producer_evidence_packet_intake",
    "agentic_service_harness_live_producer_effect_receipt_packet",
    "agentic_service_harness_live_producer_external_adapter_evidence_packet",
)
REQUIRED_BLOCKED_EVIDENCE = (
    "phi_gov_authority_receipt_ref",
    "uao_admission_receipt_ref",
    "dry_run_probe_receipt_ref",
    "redaction_receipt_ref",
    "rollback_recovery_receipt_ref",
    "signed_dispatch_receipt_ref",
)
FALSE_TOP_LEVEL_FLAGS = (
    "live_producer_implemented",
    "external_effect_adapter_implemented",
    "live_effect_observed",
    "effect_receipt_collected",
    "external_adapter_evidence_collected",
    "authority_granted",
    "terminal_closure",
)
FALSE_AUTHORITY_FLAGS = (
    "external_effect_execution_authorized",
    "live_producer_execution_authorized",
    "connector_dispatch_authority",
    "provider_mutation_authority",
    "credential_read_authority",
    "credential_serialization_authority",
    "runtime_state_write_authority",
    "terminal_closure_authority",
)
FALSE_EFFECT_FLAGS = (
    "mutation_routes_admitted",
    "provider_calls_allowed",
    "external_state_writes_allowed",
    "runtime_state_writes_allowed",
    "secret_values_allowed",
    "raw_payload_retention_allowed",
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
    r"\b(?:live_producer_implemented|external_effect_adapter_implemented|"
    r"live_effect_observed|effect_receipt_collected|"
    r"external_adapter_evidence_collected|authority_granted|"
    r"terminal_closure|external_effect_execution_authorized|"
    r"live_producer_execution_authorized)=true\b",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class InceptaDiveLiveProducerReadinessBindingValidation:
    """Validation result for the InceptaDive live producer readiness binding."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    fixture_path: str
    binding_id: str
    binding_status: str
    source_binding_count: int
    blocked_evidence_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_inceptadive_live_producer_readiness_binding(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    fixture_path: Path = DEFAULT_FIXTURE,
) -> tuple[InceptaDiveLiveProducerReadinessBindingValidation, dict[str, Any]]:
    """Validate the checked-in no-effect readiness binding fixture."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "InceptaDive live producer readiness binding schema", errors)
    fixture = _load_json_object(fixture_path, "InceptaDive live producer readiness binding fixture", errors)

    _validate_source_validators(errors)
    if schema and fixture:
        errors.extend(f"{_path_label(fixture_path)}: {error}" for error in _validate_schema_instance(schema, fixture))
        _validate_binding_semantics(fixture, errors, _path_label(fixture_path))

    source_bindings = fixture.get("source_bindings")
    blocked_evidence = fixture.get("blocked_evidence")
    validation = InceptaDiveLiveProducerReadinessBindingValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        fixture_path=_path_label(fixture_path),
        binding_id=str(fixture.get("binding_id", "")),
        binding_status=str(fixture.get("binding_status", "")),
        source_binding_count=len(source_bindings) if isinstance(source_bindings, list) else 0,
        blocked_evidence_count=len(blocked_evidence) if isinstance(blocked_evidence, list) else 0,
    )
    return validation, fixture


def _validate_source_validators(errors: list[str]) -> None:
    inceptadive_validation = validate_inceptadive_external_effect_adapter_readiness()
    intake_validation, intake_packet = validate_live_producer_evidence_packet_intake()
    effect_validation, _effect_packet = validate_live_producer_effect_receipt_packet()
    adapter_validation, _adapter_packet = validate_live_producer_external_adapter_evidence_packet()

    for source_label, validation in (
        ("inceptadive readiness", inceptadive_validation),
        ("live producer evidence intake", intake_validation),
        ("live producer effect receipt packet", effect_validation),
        ("live producer external adapter evidence packet", adapter_validation),
    ):
        if not validation.ok:
            errors.extend(f"{source_label}: {error}" for error in validation.errors)

    if inceptadive_validation.solver_outcome != "AwaitingEvidence":
        errors.append("inceptadive readiness must remain AwaitingEvidence")
    if intake_packet.get("solver_outcome") != "AwaitingEvidence":
        errors.append("live producer evidence intake must remain AwaitingEvidence")
    if effect_validation.packet_status != "blocked_awaiting_effect_receipt_components":
        errors.append("live producer effect receipt packet status mismatch")
    if adapter_validation.packet_status != "blocked_awaiting_external_adapter_evidence_components":
        errors.append("live producer external adapter evidence packet status mismatch")


def _validate_binding_semantics(binding: Mapping[str, Any], errors: list[str], label: str) -> None:
    for field_name, expected_value in (
        ("binding_id", BINDING_ID),
        ("solver_outcome", "AwaitingEvidence"),
        ("binding_status", "blocked_awaiting_live_producer_and_inceptadive_readiness_evidence"),
        ("binding_decision", "block_external_effect_execution_until_all_bound_packets_are_verified_and_authorized"),
        ("planning_only", True),
        ("read_only", True),
    ):
        if binding.get(field_name) != expected_value:
            errors.append(f"{label}: {field_name} must be {expected_value!r}")
    for flag_name in FALSE_TOP_LEVEL_FLAGS:
        if binding.get(flag_name) is not False:
            errors.append(f"{label}: {flag_name} must be false")

    _validate_source_bindings(binding, errors, label)
    _validate_source_statuses(binding, errors, label)
    _validate_blocked_evidence(binding, errors, label)
    _validate_authority_denials(binding, errors, label)
    _validate_effect_boundary(binding, errors, label)
    _validate_validator_ref(binding, errors, label)
    _validate_no_mutation_routes(binding, errors, label)
    _validate_no_live_claim(binding, errors, label)
    _validate_no_credential_values(binding, errors, label)


def _validate_source_bindings(binding: Mapping[str, Any], errors: list[str], label: str) -> None:
    source_bindings = binding.get("source_bindings")
    if not isinstance(source_bindings, list):
        errors.append(f"{label}: source_bindings must be a list")
        return
    observed_ids = tuple(entry.get("source_id") for entry in source_bindings if isinstance(entry, Mapping))
    if observed_ids != REQUIRED_SOURCE_IDS:
        errors.append(f"{label}: source binding order mismatch")
    for entry in source_bindings:
        if not isinstance(entry, Mapping):
            errors.append(f"{label}: source binding entries must be objects")
            continue
        source_id = str(entry.get("source_id", ""))
        if entry.get("status") != "AwaitingEvidence":
            errors.append(f"{label}: {source_id} status must be AwaitingEvidence")
        if entry.get("blocks_external_effect_execution") is not True:
            errors.append(f"{label}: {source_id} must block external effect execution")
        if entry.get("authority_granted") is not False:
            errors.append(f"{label}: {source_id} authority_granted must be false")
        if not entry.get("source_ref"):
            errors.append(f"{label}: {source_id} source_ref required")
        if not str(entry.get("validator_command", "")).startswith("python scripts/validate_"):
            errors.append(f"{label}: {source_id} validator_command must call a validator script")


def _validate_source_statuses(binding: Mapping[str, Any], errors: list[str], label: str) -> None:
    statuses = _mapping(binding.get("source_statuses"))
    if not statuses:
        errors.append(f"{label}: source_statuses must be an object")
        return
    for field_name in (
        "inceptadive_readiness",
        "live_producer_evidence_intake",
        "live_producer_effect_receipt_packet",
        "live_producer_external_adapter_evidence_packet",
    ):
        if statuses.get(field_name) != "AwaitingEvidence":
            errors.append(f"{label}: source_statuses.{field_name} must be AwaitingEvidence")


def _validate_blocked_evidence(binding: Mapping[str, Any], errors: list[str], label: str) -> None:
    blocked_evidence = binding.get("blocked_evidence")
    if not isinstance(blocked_evidence, list):
        errors.append(f"{label}: blocked_evidence must be a list")
        return
    observed_ids = tuple(entry.get("evidence_id") for entry in blocked_evidence if isinstance(entry, Mapping))
    if observed_ids != REQUIRED_BLOCKED_EVIDENCE:
        errors.append(f"{label}: blocked evidence order mismatch")
        missing_ids = [evidence_id for evidence_id in REQUIRED_BLOCKED_EVIDENCE if evidence_id not in observed_ids]
        if missing_ids:
            errors.append(f"{label}: missing blocked evidence ids: {', '.join(missing_ids)}")
    for entry in blocked_evidence:
        if not isinstance(entry, Mapping):
            errors.append(f"{label}: blocked_evidence entries must be objects")
            continue
        evidence_id = str(entry.get("evidence_id", ""))
        if entry.get("status") != "AwaitingEvidence":
            errors.append(f"{label}: {evidence_id} status must be AwaitingEvidence")
        if entry.get("blocks_external_effect_execution") is not True:
            errors.append(f"{label}: {evidence_id} must block external effect execution")


def _validate_authority_denials(binding: Mapping[str, Any], errors: list[str], label: str) -> None:
    authority_denials = _mapping(binding.get("authority_denials"))
    if not authority_denials:
        errors.append(f"{label}: authority_denials must be an object")
        return
    for flag_name in FALSE_AUTHORITY_FLAGS:
        if authority_denials.get(flag_name) is not False:
            errors.append(f"{label}: authority_denials.{flag_name} must be false")


def _validate_effect_boundary(binding: Mapping[str, Any], errors: list[str], label: str) -> None:
    effect_boundary = _mapping(binding.get("effect_boundary"))
    if not effect_boundary:
        errors.append(f"{label}: effect_boundary must be an object")
        return
    if effect_boundary.get("network_policy") != "none":
        errors.append(f"{label}: effect_boundary.network_policy must be none")
    for flag_name in FALSE_EFFECT_FLAGS:
        if effect_boundary.get(flag_name) is not False:
            errors.append(f"{label}: effect_boundary.{flag_name} must be false")


def _validate_validator_ref(binding: Mapping[str, Any], errors: list[str], label: str) -> None:
    validators = binding.get("validators")
    if not isinstance(validators, list) or not validators:
        errors.append(f"{label}: validators must be a non-empty list")
        return
    validator = validators[0] if isinstance(validators[0], Mapping) else {}
    if validator.get("validator_id") != BINDING_ID:
        errors.append(f"{label}: validator_id mismatch")
    if validator.get("command") != "python scripts/validate_inceptadive_live_producer_readiness_binding.py":
        errors.append(f"{label}: validator command mismatch")
    if validator.get("required_for_closure") is not True:
        errors.append(f"{label}: validator must be required for closure")


def _validate_no_mutation_routes(binding: Mapping[str, Any], errors: list[str], label: str) -> None:
    for path, value in _iter_leaf_values(binding):
        if isinstance(value, str) and FORBIDDEN_MUTATION_ROUTE.search(value):
            errors.append(f"{label}: mutation route string denied at {'.'.join(path)}")


def _validate_no_live_claim(binding: Mapping[str, Any], errors: list[str], label: str) -> None:
    for path, value in _iter_leaf_values(binding):
        if isinstance(value, str) and FORBIDDEN_LIVE_CLAIM.search(value):
            errors.append(f"{label}: live execution claim denied at {'.'.join(path)}")


def _validate_no_credential_values(binding: Mapping[str, Any], errors: list[str], label: str) -> None:
    for path, value in _iter_leaf_values(binding):
        if not isinstance(value, str):
            continue
        if any(pattern.search(value) for pattern in FORBIDDEN_CREDENTIAL_VALUE_PATTERNS):
            errors.append(f"{label}: credential-like value denied at {'.'.join(path)}")


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _iter_leaf_values(value: Any, path: tuple[str, ...] = ()) -> Iterable[tuple[tuple[str, ...], Any]]:
    if isinstance(value, Mapping):
        for key, child_value in value.items():
            yield from _iter_leaf_values(child_value, (*path, str(key)))
        return
    if isinstance(value, list):
        for index, child_value in enumerate(value):
            yield from _iter_leaf_values(child_value, (*path, str(index)))
        return
    yield path, value


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        errors.append(f"{label}: unable to read {path}: {exc}")
        return {}
    except json.JSONDecodeError as exc:
        errors.append(f"{label}: invalid JSON in {path}: {exc}")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{label}: must be a JSON object")
        return {}
    return payload


def _path_label(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def main(argv: list[str] | None = None) -> int:
    """Run the InceptaDive live producer readiness binding validator."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--json", action="store_true", help="emit machine-readable validation result")
    args = parser.parse_args(argv)

    validation, _fixture = validate_inceptadive_live_producer_readiness_binding(
        schema_path=args.schema,
        fixture_path=args.fixture,
    )
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("INCEPTADIVE LIVE PRODUCER READINESS BINDING VALID")
    else:
        for error in validation.errors:
            print(f"ERROR: {error}", file=sys.stderr)
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
