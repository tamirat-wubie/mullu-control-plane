#!/usr/bin/env python3
"""Validate InceptaDive external-effect adapter readiness.

Purpose: keep the future InceptaDive external-effect adapter in a
non-authorizing AwaitingEvidence state until authority, dry-run, redaction,
rollback, scope, and effect-receipt evidence exists.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/inceptadive_external_effect_adapter_readiness.schema.json,
examples/inceptadive_external_effect_adapter_readiness.awaiting_evidence.json,
and scripts.validate_schemas.
Invariants:
  - Readiness is evidence-only and never grants execution authority.
  - Connector dispatch, provider calls, memory writes, credential access, and
    terminal closure remain denied.
  - Credential-like values, mutation routes, and live adapter claims fail closed.
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


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "inceptadive_external_effect_adapter_readiness.schema.json"
DEFAULT_FIXTURE = REPO_ROOT / "examples" / "inceptadive_external_effect_adapter_readiness.awaiting_evidence.json"
READINESS_ID = "inceptadive-external-effect-adapter-readiness"
REQUIRED_ACTION_FAMILIES = ("connector", "deployment", "document", "finance", "messaging", "repository")
REQUIRED_MISSING_EVIDENCE = (
    "operator_approval_policy_ref",
    "phi_gov_authority_receipt_ref",
    "uao_admission_receipt_ref",
    "dry_run_probe_receipt_ref",
    "redaction_receipt_ref",
    "rollback_recovery_receipt_ref",
    "effect_receipt_schema_ref",
    "adapter_scope_policy_ref",
)
TOP_LEVEL_FALSE_FLAGS = (
    "adapter_implemented",
    "dry_run_probe_completed",
    "live_effect_observed",
    "effect_receipt_collected",
    "external_effect_execution_authorized",
    "connector_dispatch_authority",
    "memory_write_authority",
    "governance_verdict_authority",
    "adapter_credentials_present",
    "adapter_credentials_serialized",
    "terminal_closure",
)
AUTHORITY_DENIAL_FLAGS = (
    "external_effect_execution_authorized",
    "connector_dispatch_authority",
    "memory_write_authority",
    "governance_verdict_authority",
    "provider_mutation_authority",
    "credential_read_authority",
    "credential_serialization_authority",
    "destructive_operation_authority",
    "terminal_closure_authority",
)
EFFECT_BOUNDARY_FALSE_FLAGS = (
    "mutation_routes_admitted",
    "provider_calls_allowed",
    "external_state_writes_allowed",
    "repository_writes_allowed",
    "secret_values_allowed",
    "raw_payload_retention_allowed",
)
ALLOWED_CREDENTIAL_KEYS = {
    "adapter_credentials_present",
    "adapter_credentials_serialized",
    "credential_read_authority",
    "credential_serialization_authority",
    "secret_values_allowed",
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
    r"\b(?:adapter_implemented|dry_run_probe_completed|live_effect_observed|"
    r"effect_receipt_collected|external_effect_execution_authorized|"
    r"connector_dispatch_authority|memory_write_authority|"
    r"governance_verdict_authority|adapter_credentials_present|"
    r"adapter_credentials_serialized|terminal_closure)=true\b",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class InceptaDiveExternalEffectAdapterReadinessValidation:
    """Validation result for the InceptaDive adapter readiness packet."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    fixture_path: str
    readiness_id: str
    solver_outcome: str
    missing_evidence_count: int
    action_family_count: int
    authority_denial_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_inceptadive_external_effect_adapter_readiness(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    fixture_path: Path = DEFAULT_FIXTURE,
) -> InceptaDiveExternalEffectAdapterReadinessValidation:
    """Validate the checked-in InceptaDive external-effect readiness packet."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "InceptaDive external-effect adapter readiness schema", errors)
    fixture = _load_json_object(fixture_path, "InceptaDive external-effect adapter readiness fixture", errors)

    if schema and fixture:
        errors.extend(f"{_path_label(fixture_path)}: {error}" for error in _validate_schema_instance(schema, fixture))
        _validate_readiness_semantics(fixture, errors, _path_label(fixture_path))

    missing_evidence = fixture.get("missing_evidence")
    action_families = fixture.get("action_families")
    return InceptaDiveExternalEffectAdapterReadinessValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        fixture_path=_path_label(fixture_path),
        readiness_id=str(fixture.get("readiness_id", "")),
        solver_outcome=str(fixture.get("solver_outcome", "")),
        missing_evidence_count=len(missing_evidence) if isinstance(missing_evidence, list) else 0,
        action_family_count=len(action_families) if isinstance(action_families, list) else 0,
        authority_denial_count=len(AUTHORITY_DENIAL_FLAGS),
    )


def _validate_readiness_semantics(readiness: Mapping[str, Any], errors: list[str], label: str) -> None:
    if readiness.get("readiness_id") != READINESS_ID:
        errors.append(f"{label}: readiness_id mismatch")
    for field_name, expected_value in (
        ("solver_outcome", "AwaitingEvidence"),
        ("target_adapter_kind", "external_effect_adapter"),
        ("readiness_decision", "blocked_until_authority_evidence_and_dry_run_receipts_exist"),
        ("planning_only", True),
        ("read_only", True),
    ):
        if readiness.get(field_name) != expected_value:
            errors.append(f"{label}: {field_name} must be {expected_value!r}")
    for flag_name in TOP_LEVEL_FALSE_FLAGS:
        if readiness.get(flag_name) is not False:
            errors.append(f"{label}: {flag_name} must be false")
    _validate_scope(readiness, errors, label)
    _validate_action_families(readiness, errors, label)
    _validate_required_evidence(readiness, errors, label)
    _validate_missing_evidence(readiness, errors, label)
    _validate_authority_denials(readiness, errors, label)
    _validate_effect_boundary(readiness, errors, label)
    _validate_credential_surface(readiness, errors, label)
    _validate_no_mutation_routes(readiness, errors, label)
    _validate_no_live_claim(readiness, errors, label)


def _validate_scope(readiness: Mapping[str, Any], errors: list[str], label: str) -> None:
    scope = _mapping(readiness.get("scope"))
    if not scope:
        errors.append(f"{label}: scope must be an object")
        return
    if scope.get("read_only") is not True:
        errors.append(f"{label}: scope.read_only must be true")
    for field_name in ("tenant_id", "organization_id", "project_id", "repository_id"):
        if not scope.get(field_name):
            errors.append(f"{label}: scope.{field_name} required")


def _validate_action_families(readiness: Mapping[str, Any], errors: list[str], label: str) -> None:
    action_families = readiness.get("action_families")
    if not isinstance(action_families, list):
        errors.append(f"{label}: action_families must be a list")
        return
    if tuple(action_families) != REQUIRED_ACTION_FAMILIES:
        errors.append(f"{label}: action_families must match required order")


def _validate_required_evidence(readiness: Mapping[str, Any], errors: list[str], label: str) -> None:
    evidence = _mapping(readiness.get("required_evidence"))
    if not evidence:
        errors.append(f"{label}: required_evidence must be an object")
        return
    for evidence_id in REQUIRED_MISSING_EVIDENCE:
        if not evidence.get(evidence_id):
            errors.append(f"{label}: required_evidence.{evidence_id} required")
    if evidence.get("status") != "AwaitingEvidence":
        errors.append(f"{label}: required_evidence.status must be AwaitingEvidence")
    if evidence.get("blocks_live_execution") is not True:
        errors.append(f"{label}: required_evidence.blocks_live_execution must be true")
    if evidence.get("authority_granted") is not False:
        errors.append(f"{label}: required_evidence.authority_granted must be false")


def _validate_missing_evidence(readiness: Mapping[str, Any], errors: list[str], label: str) -> None:
    missing_evidence = readiness.get("missing_evidence")
    if not isinstance(missing_evidence, list):
        errors.append(f"{label}: missing_evidence must be a list")
        return
    observed = [item.get("evidence_id") for item in missing_evidence if isinstance(item, Mapping)]
    if tuple(observed) != REQUIRED_MISSING_EVIDENCE:
        errors.append(f"{label}: missing evidence ids must match required order")
    for item in missing_evidence:
        if not isinstance(item, Mapping):
            errors.append(f"{label}: missing evidence entries must be objects")
            continue
        evidence_id = str(item.get("evidence_id", ""))
        if item.get("status") != "AwaitingEvidence":
            errors.append(f"{label}: {evidence_id} status must be AwaitingEvidence")
        if item.get("blocks_live_execution") is not True:
            errors.append(f"{label}: {evidence_id} must block live execution")


def _validate_authority_denials(readiness: Mapping[str, Any], errors: list[str], label: str) -> None:
    authority_denials = _mapping(readiness.get("authority_denials"))
    if not authority_denials:
        errors.append(f"{label}: authority_denials must be an object")
        return
    for flag_name in AUTHORITY_DENIAL_FLAGS:
        if authority_denials.get(flag_name) is not False:
            errors.append(f"{label}: authority_denials.{flag_name} must be false")


def _validate_effect_boundary(readiness: Mapping[str, Any], errors: list[str], label: str) -> None:
    effect_boundary = _mapping(readiness.get("effect_boundary"))
    if not effect_boundary:
        errors.append(f"{label}: effect_boundary must be an object")
        return
    if effect_boundary.get("network_egress_policy") != "none":
        errors.append(f"{label}: effect_boundary.network_egress_policy must be none")
    for flag_name in EFFECT_BOUNDARY_FALSE_FLAGS:
        if effect_boundary.get(flag_name) is not False:
            errors.append(f"{label}: effect_boundary.{flag_name} must be false")
    if effect_boundary.get("append_only_receipts_required") is not True:
        errors.append(f"{label}: effect_boundary.append_only_receipts_required must be true")


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
    """Run the InceptaDive external-effect adapter readiness validator."""

    args = build_arg_parser().parse_args(argv)
    validation = validate_inceptadive_external_effect_adapter_readiness(
        schema_path=args.schema,
        fixture_path=args.fixture,
    )
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("INCEPTADIVE EXTERNAL EFFECT ADAPTER READINESS VALID")
    else:
        print(f"INCEPTADIVE EXTERNAL EFFECT ADAPTER READINESS INVALID errors={list(validation.errors)}")
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
