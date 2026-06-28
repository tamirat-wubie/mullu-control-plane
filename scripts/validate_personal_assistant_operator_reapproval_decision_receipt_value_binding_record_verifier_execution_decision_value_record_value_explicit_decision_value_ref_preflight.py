#!/usr/bin/env python3
"""Validate operator value-binding verifier execution explicit decision value-ref preflight."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parent.parent
MCOI_ROOT = REPO_ROOT / "mcoi"
for candidate in (REPO_ROOT, MCOI_ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from mcoi_runtime.personal_assistant import (  # noqa: E402
    DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_EXECUTION_DECISION_VALUE_RECORD_VALUE_EXPLICIT_DECISION_VALUE_REF_PREFLIGHT_GENERATED_AT,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_preflight,
)
from scripts.validate_personal_assistant_receipt import validate_personal_assistant_receipt_payload  # noqa: E402
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402

DEFAULT_SCHEMA = (
    REPO_ROOT
    / "schemas"
    / "personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_preflight.schema.json"
)
DEFAULT_RECEIPT_SCHEMA = REPO_ROOT / "schemas" / "personal_assistant_receipt.schema.json"
RUNTIME_GENERATED_AT = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_EXECUTION_DECISION_VALUE_RECORD_VALUE_EXPLICIT_DECISION_VALUE_REF_PREFLIGHT_GENERATED_AT
EXPECTED_REQUIRED_VALUE_REFS = (
    "operator_decision_value_ref",
    "operator_identity_ref",
    "operator_signature_ref",
    "operator_reapproval_decision_receipt_ref",
)
EXPECTED_EVIDENCE_KINDS = frozenset(EXPECTED_REQUIRED_VALUE_REFS)
EXPECTED_REQUIREMENT_KINDS = frozenset(
    {
        "verifier_identity_ref",
        "verification_method_ref",
        "evidence_integrity_hash_ref",
        "source_ref_reachability_witness_ref",
        "decision_receipt_crosscheck_ref",
    }
)
FALSE_FIELDS = frozenset(
    {
        "explicit_decision_value_ref_preflight_satisfied",
        "explicit_decision_value_refs_present",
        "explicit_decision_candidate_admitted",
        "explicit_operator_decision_value_bound",
        "record_value_explicit_decision_value_ref_preflight_admitted",
        "operator_value_record_created",
        "operator_decision_value_stored",
        "operator_decision_value_present",
        "operator_decision_value_collected",
        "operator_decision_value_admitted",
        "operator_approval_granted",
        "operator_approval_rejected",
        "verifier_execution_allowed",
        "verifier_execution_started",
        "verifier_result_present",
        "authority_granted",
        "execution_worker_admission_allowed",
        "dispatch_allowed",
        "live_connector_execution_allowed",
        "connector_mutation_allowed",
        "system_of_record_write_allowed",
        "memory_write_allowed",
        "deployment_mutation_allowed",
        "nested_mind_live_activation_allowed",
        "public_readiness_claim_allowed",
    }
)
SECRET_VALUE_PATTERNS = (
    re.compile(r"sk_live_[A-Za-z0-9]+"),
    re.compile(r"ghp_[A-Za-z0-9]+"),
    re.compile(r"github_pat_[A-Za-z0-9_]+"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]+"),
    re.compile(r"ya29\.[A-Za-z0-9._-]+"),
    re.compile(r"Bearer\s+[A-Za-z0-9._-]+", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"secret-(?:token|worker|key)-value", re.IGNORECASE),
)


@dataclass(frozen=True, slots=True)
class PersonalAssistantExplicitDecisionValueRefPreflightValidation:
    """Validation result for explicit decision value-ref preflight."""

    valid: bool
    runtime_validated: bool
    explicit_decision_value_ref_preflight_count: int
    required_value_ref_slot_count: int
    required_value_ref_absent_count: int
    required_value_ref_present_count: int
    required_value_ref_bound_count: int
    explicit_decision_value_ref_preflight_satisfied_count: int
    explicit_operator_decision_value_bound_count: int
    operator_decision_value_present_count: int
    operator_value_record_creation_count: int
    verifier_execution_allowed_count: int
    authority_grant_count: int
    assurance_outcome: str
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_preflight(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    receipt_schema_path: Path = DEFAULT_RECEIPT_SCHEMA,
) -> PersonalAssistantExplicitDecisionValueRefPreflightValidation:
    """Validate runtime verifier execution explicit decision value-ref preflight."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "explicit decision value-ref preflight schema", errors)
    receipt_schema = _load_json_object(receipt_schema_path, "receipt schema", errors)
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_preflight(
        generated_at=RUNTIME_GENERATED_AT,
    )
    summary = _mapping(envelope.get("summary"))
    assurance = _mapping(envelope.get("assurance"))
    if schema:
        errors.extend(_validate_schema_instance(schema, envelope))
    errors.extend(_validate_explicit_decision_value_ref_preflight_semantics(envelope, receipt_schema))
    _scan_secret_values(envelope, errors, path="$runtime")
    return PersonalAssistantExplicitDecisionValueRefPreflightValidation(
        valid=not errors,
        runtime_validated=not errors,
        explicit_decision_value_ref_preflight_count=int(envelope.get("explicit_decision_value_ref_preflight_count", 0)),
        required_value_ref_slot_count=int(summary.get("required_value_ref_slot_count", 0)),
        required_value_ref_absent_count=int(summary.get("required_value_ref_absent_count", 0)),
        required_value_ref_present_count=int(summary.get("required_value_ref_present_count", 0)),
        required_value_ref_bound_count=int(summary.get("required_value_ref_bound_count", 0)),
        explicit_decision_value_ref_preflight_satisfied_count=int(summary.get("explicit_decision_value_ref_preflight_satisfied_count", 0)),
        explicit_operator_decision_value_bound_count=int(summary.get("explicit_operator_decision_value_bound_count", 0)),
        operator_decision_value_present_count=int(summary.get("operator_decision_value_present_count", 0)),
        operator_value_record_creation_count=int(summary.get("operator_value_record_creation_count", 0)),
        verifier_execution_allowed_count=int(summary.get("verifier_execution_allowed_count", 0)),
        authority_grant_count=int(summary.get("authority_grant_count", 0)),
        assurance_outcome=str(assurance.get("outcome", "")),
        errors=tuple(errors),
    )


def _validate_explicit_decision_value_ref_preflight_semantics(envelope: Mapping[str, Any], receipt_schema: Mapping[str, Any]) -> tuple[str, ...]:
    errors: list[str] = []
    expected_top = {
        "explicit_decision_value_ref_preflight_state": "explicit_decision_value_refs_absent_not_bound",
        "decision": "blocked",
        "outcome": "AwaitingEvidence",
        "source_projection": "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_candidate",
    }
    for field_name, expected_value in expected_top.items():
        if envelope.get(field_name) != expected_value:
            errors.append(f"{field_name} must be {expected_value}")
    effect_boundary = _mapping(envelope.get("effect_boundary"))
    for field_name in (
        "explicit_decision_candidate_classes_present",
        "required_value_refs_declared",
        "required_value_refs_absent",
        "operator_decision_required",
        "operator_decision_value_required",
        "record_contract_ready",
        "verifier_ref_only",
    ):
        if effect_boundary.get(field_name) is not True:
            errors.append(f"effect_boundary.{field_name} must be true")
    _require_false_fields(effect_boundary, FALSE_FIELDS, "effect_boundary", errors)

    records = envelope.get("explicit_decision_value_ref_preflights")
    if not isinstance(records, list):
        errors.append("explicit_decision_value_ref_preflights must be a list")
        return tuple(errors)
    if envelope.get("explicit_decision_value_ref_preflight_count") != len(records):
        errors.append("explicit_decision_value_ref_preflight_count must equal explicit_decision_value_ref_preflights length")
    item_ids: list[str] = []
    receipt_ids: list[str] = []
    coverage: dict[str, set[str]] = {}
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            errors.append(f"explicit_decision_value_ref_preflights[{index}] must be an object")
            continue
        item_ids.append(str(record.get("explicit_decision_value_ref_preflight_item_id", "")))
        evidence_kind = str(record.get("evidence_kind", ""))
        requirement_kind = str(record.get("requirement_kind", ""))
        coverage.setdefault(evidence_kind, set()).add(requirement_kind)
        _require_source_ref(index, _mapping(record.get("explicit_decision_candidate_ref")), errors)
        _require_preflight(index, _mapping(record.get("explicit_decision_value_ref_preflight")), errors)
        _require_false_fields(_mapping(record.get("authority_status")), FALSE_FIELDS | {"operator_value_bound"}, f"explicit_decision_value_ref_preflights[{index}].authority_status", errors)
        receipt = _mapping(record.get("receipt"))
        if receipt_schema:
            errors.extend(f"explicit_decision_value_ref_preflights[{index}].receipt {message}" for message in _validate_schema_instance(dict(receipt_schema), receipt))
        errors.extend(f"explicit_decision_value_ref_preflights[{index}].receipt {message}" for message in validate_personal_assistant_receipt_payload(receipt))
        metadata = _mapping(receipt.get("metadata"))
        if metadata.get("operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_preflight_is_execution") is not False:
            errors.append(f"explicit_decision_value_ref_preflights[{index}].receipt.metadata execution flag must be false")
        if metadata.get("required_value_refs_absent") is not True:
            errors.append(f"explicit_decision_value_ref_preflights[{index}].receipt.metadata required_value_refs_absent must be true")
        _require_false_fields(metadata, FALSE_FIELDS | {"external_write_allowed"}, f"explicit_decision_value_ref_preflights[{index}].receipt.metadata", errors)
        receipt_ids.append(str(receipt.get("receipt_id", "")))
    if set(coverage) != EXPECTED_EVIDENCE_KINDS:
        errors.append("explicit_decision_value_ref_preflights must cover all governed evidence kinds")
    for evidence_kind, requirement_kinds in coverage.items():
        if requirement_kinds != EXPECTED_REQUIREMENT_KINDS:
            errors.append(f"explicit_decision_value_ref_preflights for {evidence_kind} must cover all verifier requirement kinds")
    if envelope.get("explicit_decision_value_ref_preflight_item_ids") != item_ids:
        errors.append("explicit_decision_value_ref_preflight_item_ids must match item order")
    if envelope.get("receipt_ids") != receipt_ids:
        errors.append("receipt_ids must match item receipts")
    _require_summary(envelope, records, errors)
    return tuple(errors)


def _require_source_ref(index: int, payload: Mapping[str, Any], errors: list[str]) -> None:
    expected = {
        "source_explicit_decision_candidate_state": "explicit_operator_decision_candidate_projected_not_admitted",
        "source_outcome": "AwaitingEvidence",
        "source_explicit_decision_candidate_classes_projected": True,
        "source_actual_operator_decision_value_absent": True,
        "source_explicit_decision_candidate_admitted": False,
        "source_operator_decision_value_present": False,
        "source_operator_value_record_created": False,
        "source_verifier_execution_allowed": False,
        "source_authority_granted": False,
    }
    for field_name, expected_value in expected.items():
        if payload.get(field_name) != expected_value:
            errors.append(f"explicit_decision_value_ref_preflights[{index}].explicit_decision_candidate_ref.{field_name} must be {expected_value}")


def _require_preflight(index: int, payload: Mapping[str, Any], errors: list[str]) -> None:
    for field_name in (
        "record_contract_ready",
        "required_value_refs_declared",
        "requires_all_required_refs",
        "requires_actual_operator_decision_value",
        "required_value_refs_absent",
    ):
        if payload.get(field_name) is not True:
            errors.append(f"explicit_decision_value_ref_preflights[{index}].explicit_decision_value_ref_preflight.{field_name} must be true")
    _require_false_fields(payload, FALSE_FIELDS, f"explicit_decision_value_ref_preflights[{index}].explicit_decision_value_ref_preflight", errors)
    ref_slots = payload.get("required_value_refs")
    if not isinstance(ref_slots, list):
        errors.append(f"explicit_decision_value_ref_preflights[{index}].explicit_decision_value_ref_preflight.required_value_refs must be a list")
        return
    if tuple(str(slot.get("ref_name", "")) for slot in ref_slots if isinstance(slot, dict)) != EXPECTED_REQUIRED_VALUE_REFS:
        errors.append(f"explicit_decision_value_ref_preflights[{index}].explicit_decision_value_ref_preflight.required_value_refs must match canonical order")
    for slot_index, slot in enumerate(ref_slots):
        if not isinstance(slot, Mapping):
            errors.append(f"explicit_decision_value_ref_preflights[{index}].explicit_decision_value_ref_preflight.required_value_refs[{slot_index}] must be an object")
            continue
        if slot.get("required") is not True:
            errors.append(f"explicit_decision_value_ref_preflights[{index}].explicit_decision_value_ref_preflight.required_value_refs[{slot_index}].required must be true")
        for field_name in ("present", "bound", "validated", "grants_authority", "grants_verifier_execution"):
            if slot.get(field_name) is not False:
                errors.append(f"explicit_decision_value_ref_preflights[{index}].explicit_decision_value_ref_preflight.required_value_refs[{slot_index}].{field_name} must be false")


def _require_summary(envelope: Mapping[str, Any], records: list[Any], errors: list[str]) -> None:
    summary = _mapping(envelope.get("summary"))
    ref_slot_count = len(records) * len(EXPECTED_REQUIRED_VALUE_REFS)
    expected = {
        "explicit_decision_value_ref_preflight_count": len(records),
        "required_value_ref_slot_count": ref_slot_count,
        "required_value_ref_absent_count": ref_slot_count,
        "required_value_ref_present_count": 0,
        "required_value_ref_bound_count": 0,
        "explicit_decision_value_ref_preflight_satisfied_count": 0,
        "explicit_operator_decision_value_bound_count": 0,
        "operator_decision_value_present_count": 0,
        "operator_value_record_creation_count": 0,
        "verifier_execution_allowed_count": 0,
        "authority_grant_count": 0,
    }
    for field_name, expected_value in expected.items():
        if summary.get(field_name) != expected_value:
            errors.append(f"summary.{field_name} must be {expected_value}")


def _require_false_fields(payload: Mapping[str, Any], field_names: set[str] | frozenset[str], path: str, errors: list[str]) -> None:
    for field_name in sorted(field_names):
        if field_name in payload and payload.get(field_name) is not False:
            errors.append(f"{path}.{field_name} must be false")


def _scan_secret_values(value: Any, errors: list[str], *, path: str) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            _scan_secret_values(child, errors, path=f"{path}.{key}")
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            _scan_secret_values(child, errors, path=f"{path}[{index}]")
        return
    if isinstance(value, str):
        for pattern in SECRET_VALUE_PATTERNS:
            if pattern.search(value):
                errors.append(f"{path} must not contain secret-like values")


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        errors.append(f"{label} could not be read: {exc}")
        return {}
    except json.JSONDecodeError as exc:
        errors.append(f"{label} is invalid JSON: {exc}")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{label} must be an object")
        return {}
    return payload


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def main(argv: list[str] | None = None) -> int:
    """Run the explicit decision value-ref preflight validator."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--receipt-schema", type=Path, default=DEFAULT_RECEIPT_SCHEMA)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    validation = validate_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_preflight(
        schema_path=args.schema,
        receipt_schema_path=args.receipt_schema,
    )
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.valid:
        print("personal assistant verifier execution explicit decision value-ref preflight: valid")
    else:
        print("personal assistant verifier execution explicit decision value-ref preflight: invalid")
        for error in validation.errors:
            print(f"  - {error}")
    return 0 if validation.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
