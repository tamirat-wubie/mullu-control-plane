#!/usr/bin/env python3
"""Validate Agentic Service Harness live producer effect receipt preflight.

Purpose: make the live producer effect receipt requirement explicit without
claiming a live effect, collecting a runtime receipt, or granting authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/agentic_service_harness_live_producer_effect_receipt_preflight.schema.json,
examples/agentic_service_harness_live_producer_effect_receipt_preflight.local.json,
and scripts.validate_agentic_service_harness_live_producer_operator_decision_value_record.
Invariants:
  - The effect receipt remains AwaitingEvidence.
  - Live producer implementation and runtime writes remain denied.
  - Mutation routes, credentials, live-effect claims, and terminal closure fail closed.
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
from gateway.agentic_service_harness_live_producer_witness_requirements import FALSE_AUTHORITY_FLAGS  # noqa: E402
from scripts.validate_agentic_service_harness_live_producer_operator_decision_value_record import (  # noqa: E402
    validate_live_producer_operator_decision_value_record,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = (
    REPO_ROOT
    / "schemas"
    / "agentic_service_harness_live_producer_effect_receipt_preflight.schema.json"
)
DEFAULT_FIXTURE = (
    REPO_ROOT
    / "examples"
    / "agentic_service_harness_live_producer_effect_receipt_preflight.local.json"
)
PREFLIGHT_ID = "agentic-service-harness-live-producer-effect-receipt-preflight"
REQUIRED_MISSING_EVIDENCE = (
    "admitted_action_ref",
    "effect_receipt_ref",
    "effect_hash_ref",
    "effect_reconciliation_ref",
    "rollback_link_ref",
    "redaction_ref",
)
ALLOWED_SECRET_KEYS = {"secret_handoff", "secret_mutation_enabled"}
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
FORBIDDEN_LIVE_CLAIM = re.compile(
    r"\b(?:live_producer_implemented|live_effect_observed|effect_receipt_collected)=true\b",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class LiveProducerEffectReceiptPreflightValidation:
    """Validation result for the live producer effect receipt preflight."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    fixture_path: str
    preflight_id: str
    target_witness_kind: str
    effect_receipt_status: str
    missing_evidence_count: int
    remaining_witness_count: int
    authority_denial_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_live_producer_effect_receipt_preflight(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    fixture_path: Path = DEFAULT_FIXTURE,
) -> LiveProducerEffectReceiptPreflightValidation:
    """Validate the checked-in live producer effect receipt preflight."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "effect receipt preflight schema", errors)
    fixture = _load_json_object(fixture_path, "effect receipt preflight fixture", errors)
    source_validation, source_record = validate_live_producer_operator_decision_value_record()
    errors.extend(f"source operator decision value record: {error}" for error in source_validation.errors)

    if schema and fixture:
        errors.extend(f"{_path_label(fixture_path)}: {error}" for error in _validate_schema_instance(schema, fixture))
        _validate_preflight_semantics(fixture, source_record, errors, _path_label(fixture_path))

    missing_evidence = fixture.get("missing_evidence")
    remaining_witnesses = fixture.get("remaining_witnesses")
    return LiveProducerEffectReceiptPreflightValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        fixture_path=_path_label(fixture_path),
        preflight_id=str(fixture.get("preflight_id", "")),
        target_witness_kind=str(fixture.get("target_witness_kind", "")),
        effect_receipt_status=str(fixture.get("effect_receipt_status", "")),
        missing_evidence_count=len(missing_evidence) if isinstance(missing_evidence, list) else 0,
        remaining_witness_count=len(remaining_witnesses) if isinstance(remaining_witnesses, list) else 0,
        authority_denial_count=len(FALSE_AUTHORITY_FLAGS) + 1,
    )


def _validate_preflight_semantics(
    preflight: Mapping[str, Any],
    source_record: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    if preflight.get("preflight_id") != PREFLIGHT_ID:
        errors.append(f"{label}: preflight_id mismatch")
    if source_record.get("approval_status") != "Satisfied":
        errors.append(f"{label}: source operator approval must be Satisfied")
    if source_record.get("operator_approval_witness_satisfied") is not True:
        errors.append(f"{label}: source operator approval witness must be satisfied")
    for field_name, expected_value in (
        ("solver_outcome", "AwaitingEvidence"),
        ("operator_approval_status", "Satisfied"),
        ("target_witness_kind", "effect_receipt"),
        ("effect_receipt_status", "AwaitingEvidence"),
        ("preflight_decision", "blocked_until_effect_receipt_exists"),
        ("planning_only", True),
        ("read_only", True),
        ("live_producer_implemented", False),
        ("live_effect_observed", False),
        ("effect_receipt_collected", False),
        ("authority_granted", False),
        ("terminal_closure", False),
    ):
        if preflight.get(field_name) != expected_value:
            errors.append(f"{label}: {field_name} must be {expected_value!r}")
    _validate_scope(preflight, errors, label)
    _validate_required_effect_receipt(preflight, errors, label)
    _validate_missing_evidence(preflight, errors, label)
    _validate_remaining_witnesses(preflight, errors, label)
    _validate_denials(preflight, errors, label)
    _validate_secret_surface(preflight, errors, label)
    _validate_no_mutation_routes(preflight, errors, label)
    _validate_no_live_claim(preflight, errors, label)


def _validate_scope(preflight: Mapping[str, Any], errors: list[str], label: str) -> None:
    scope = _mapping(preflight.get("scope"))
    if not scope:
        errors.append(f"{label}: scope must be an object")
        return
    if scope.get("read_only") is not True:
        errors.append(f"{label}: scope.read_only must be true")
    for field_name in ("tenant_id", "organization_id", "project_id", "repository_connection_id"):
        if not scope.get(field_name):
            errors.append(f"{label}: scope.{field_name} required")


def _validate_required_effect_receipt(
    preflight: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    receipt = _mapping(preflight.get("required_effect_receipt"))
    if not receipt:
        errors.append(f"{label}: required_effect_receipt must be an object")
        return
    for field_name in (
        "receipt_ref",
        "required_admitted_action_ref",
        "required_effect_hash_ref",
        "required_reconciliation_ref",
        "required_rollback_link_ref",
        "required_redaction_ref",
    ):
        if not receipt.get(field_name):
            errors.append(f"{label}: required_effect_receipt.{field_name} required")
    if receipt.get("status") != "AwaitingEvidence":
        errors.append(f"{label}: required effect receipt status must be AwaitingEvidence")
    if receipt.get("blocks_live_producer") is not True:
        errors.append(f"{label}: required effect receipt must block live producer")
    if receipt.get("authority_granted") is not False:
        errors.append(f"{label}: required effect receipt authority_granted must be false")


def _validate_missing_evidence(
    preflight: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    missing_evidence = preflight.get("missing_evidence")
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
        if item.get("blocks_live_producer") is not True:
            errors.append(f"{label}: {evidence_id} must block live producer")


def _validate_remaining_witnesses(
    preflight: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    remaining_witnesses = preflight.get("remaining_witnesses")
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
        if witness.get("authority_granted") is not False:
            errors.append(f"{label}: {witness_kind} authority_granted must be false")


def _validate_denials(preflight: Mapping[str, Any], errors: list[str], label: str) -> None:
    authority_denials = _mapping(preflight.get("authority_denials"))
    effect_boundary = _mapping(preflight.get("effect_boundary"))
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


def _validate_no_live_claim(payload: Any, errors: list[str], label: str) -> None:
    for path, value in _walk_strings(payload):
        if FORBIDDEN_LIVE_CLAIM.search(value):
            errors.append(f"{label}: live effect claim at {path}")


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
    """Run the live producer effect receipt preflight validator."""
    args = build_arg_parser().parse_args(argv)
    validation = validate_live_producer_effect_receipt_preflight(
        schema_path=args.schema,
        fixture_path=args.fixture,
    )
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("AGENTIC SERVICE HARNESS LIVE PRODUCER EFFECT RECEIPT PREFLIGHT VALID")
    else:
        print(
            "AGENTIC SERVICE HARNESS LIVE PRODUCER EFFECT RECEIPT PREFLIGHT INVALID "
            f"errors={list(validation.errors)}"
        )
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
