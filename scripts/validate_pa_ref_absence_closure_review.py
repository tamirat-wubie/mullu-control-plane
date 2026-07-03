#!/usr/bin/env python3
"""Validate personal-assistant ref absence closure review."""

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

from mcoi_runtime.personal_assistant import build_default_personal_assistant_ref_absence_closure_review  # noqa: E402
from scripts.validate_personal_assistant_receipt import validate_personal_assistant_receipt_payload  # noqa: E402
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "pa_ref_absence_closure_review.schema.json"
DEFAULT_RECEIPT_SCHEMA = REPO_ROOT / "schemas" / "personal_assistant_receipt.schema.json"
EXPECTED_REQUIRED_VALUE_REFS = (
    "operator_decision_value_ref",
    "operator_identity_ref",
    "operator_signature_ref",
    "operator_reapproval_decision_receipt_ref",
)
FALSE_FIELDS = frozenset(
    {
        "review_satisfied",
        "closure_satisfied",
        "terminal_closure_claimed",
        "source_closure_packet_satisfied",
        "explicit_decision_value_refs_verified",
        "explicit_decision_value_refs_accepted",
        "explicit_decision_value_refs_bound",
        "explicit_decision_value_refs_validated",
        "explicit_decision_value_refs_stored",
        "verification_result_present",
        "verification_result_accepted",
        "verification_result_bound",
        "verification_result_stored",
        "operator_value_record_created",
        "operator_decision_value_present",
        "operator_decision_value_collected",
        "operator_decision_value_stored",
        "ready_for_verifier_execution",
        "verifier_execution_allowed",
        "verifier_execution_started",
        "verifier_execution_completed",
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
class PersonalAssistantRefAbsenceClosureReviewValidation:
    """Validation result for a ref absence closure review."""

    valid: bool
    runtime_validated: bool
    reviewed_obligation_count: int
    pending_evidence_obligation_count: int
    missing_verification_result_count: int
    blocking_reason_count: int
    verification_result_present_count: int
    verified_ref_count: int
    accepted_ref_count: int
    bound_ref_count: int
    stored_ref_count: int
    authority_grant_count: int
    verifier_execution_grant_count: int
    assurance_outcome: str
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_personal_assistant_ref_absence_closure_review(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    receipt_schema_path: Path = DEFAULT_RECEIPT_SCHEMA,
) -> PersonalAssistantRefAbsenceClosureReviewValidation:
    """Validate runtime closure review against schema and no-effect rules."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "closure review schema", errors)
    receipt_schema = _load_json_object(receipt_schema_path, "receipt schema", errors)
    envelope = build_default_personal_assistant_ref_absence_closure_review()
    summary = _mapping(envelope.get("summary"))
    assurance = _mapping(envelope.get("assurance"))
    if schema:
        errors.extend(_validate_schema_instance(schema, envelope))
    errors.extend(_validate_ref_absence_closure_review_semantics(envelope, receipt_schema))
    _scan_secret_values(envelope, errors, path="$runtime")
    return PersonalAssistantRefAbsenceClosureReviewValidation(
        valid=not errors,
        runtime_validated=not errors,
        reviewed_obligation_count=int(summary.get("reviewed_obligation_count", 0)),
        pending_evidence_obligation_count=int(summary.get("pending_evidence_obligation_count", 0)),
        missing_verification_result_count=int(summary.get("missing_verification_result_count", 0)),
        blocking_reason_count=int(summary.get("blocking_reason_count", 0)),
        verification_result_present_count=int(summary.get("verification_result_present_count", 0)),
        verified_ref_count=int(summary.get("verified_ref_count", 0)),
        accepted_ref_count=int(summary.get("accepted_ref_count", 0)),
        bound_ref_count=int(summary.get("bound_ref_count", 0)),
        stored_ref_count=int(summary.get("stored_ref_count", 0)),
        authority_grant_count=int(summary.get("authority_grant_count", 0)),
        verifier_execution_grant_count=int(summary.get("verifier_execution_grant_count", 0)),
        assurance_outcome=str(assurance.get("outcome", "")),
        errors=tuple(errors),
    )


def _validate_ref_absence_closure_review_semantics(envelope: Mapping[str, Any], receipt_schema: Mapping[str, Any]) -> tuple[str, ...]:
    errors: list[str] = []
    for field_name, expected_value in {
        "ref_absence_closure_review_state": "closure_review_blocked_awaiting_verification_results",
        "decision": "blocked",
        "outcome": "AwaitingEvidence",
        "source_projection": "personal_assistant_ref_absence_closure_packet",
    }.items():
        if envelope.get(field_name) != expected_value:
            errors.append(f"{field_name} must be {expected_value}")
    review_state = _mapping(envelope.get("review_state"))
    for field_name in ("can_close_review", "can_close_source_packet", "can_close_verifier_execution", "can_close_authority_grant", "can_close_terminal_readiness"):
        if review_state.get(field_name) is not False:
            errors.append(f"review_state.{field_name} must be false")
    for field_name in ("reviewed_obligation_count", "pending_evidence_obligation_count", "missing_verification_result_count", "blocking_reason_count"):
        if review_state.get(field_name) != len(EXPECTED_REQUIRED_VALUE_REFS):
            errors.append(f"review_state.{field_name} must be four")
    effect_boundary = _mapping(envelope.get("effect_boundary"))
    for field_name in ("closure_review_allowed", "source_closure_packet_projection_allowed", "pending_evidence_obligation_review_allowed", "review_recorded", "required_value_refs_submitted", "submitted_ref_only", "verification_result_requested", "verification_result_absence_recorded", "verification_result_absence_status_ledgered", "source_closure_packet_recorded", "operator_decision_required", "operator_decision_value_required", "verifier_ref_only"):
        if effect_boundary.get(field_name) is not True:
            errors.append(f"effect_boundary.{field_name} must be true")
    _require_false_fields(effect_boundary, FALSE_FIELDS, "effect_boundary", errors)
    review_items = envelope.get("review_items")
    if not isinstance(review_items, list):
        errors.append("review_items must be a list")
        return tuple(errors)
    names: list[str] = []
    blocking_reasons: list[str] = []
    for index, item in enumerate(review_items):
        if not isinstance(item, dict):
            errors.append(f"review_items[{index}] must be an object")
            continue
        names.append(str(item.get("ref_name", "")))
        blocking_reasons.append(str(item.get("blocking_reason", "")))
        _require_review_item(index, item, errors)
    if tuple(names) != EXPECTED_REQUIRED_VALUE_REFS:
        errors.append("review_items must match canonical required ref order")
    if envelope.get("blocking_reasons") != blocking_reasons:
        errors.append("blocking_reasons must match review item order")
    receipt = _mapping(envelope.get("receipt"))
    if receipt_schema:
        errors.extend(f"receipt {message}" for message in _validate_schema_instance(dict(receipt_schema), receipt))
    errors.extend(f"receipt {message}" for message in validate_personal_assistant_receipt_payload(dict(receipt)))
    metadata = _mapping(receipt.get("metadata"))
    if metadata.get("ref_absence_closure_review_is_execution") is not False:
        errors.append("receipt.metadata execution flag must be false")
    if metadata.get("review_only") is not True:
        errors.append("receipt.metadata review_only must be true")
    _require_false_fields(metadata, FALSE_FIELDS | {"external_write_allowed"}, "receipt.metadata", errors)
    _require_summary(envelope, review_items, errors)
    return tuple(errors)


def _require_review_item(index: int, item: Mapping[str, Any], errors: list[str]) -> None:
    expected = {
        "review_result": "blocked_missing_governed_verification_result",
        "required_next_evidence": "governed_verification_result",
        "reviewed": True,
        "pending": True,
        "verification_result_present": False,
        "verified": False,
        "accepted": False,
        "bound": False,
        "stored": False,
        "grants_authority": False,
        "grants_verifier_execution": False,
    }
    for field_name, expected_value in expected.items():
        if item.get(field_name) != expected_value:
            errors.append(f"review_items[{index}].{field_name} must be {expected_value}")
    ref_name = str(item.get("ref_name", ""))
    if item.get("blocking_reason") != f"{ref_name}_verification_result_absent":
        errors.append(f"review_items[{index}].blocking_reason must match ref_name")


def _require_summary(envelope: Mapping[str, Any], review_items: list[Any], errors: list[str]) -> None:
    summary = _mapping(envelope.get("summary"))
    expected = {
        "reviewed_obligation_count": 4,
        "pending_evidence_obligation_count": 4,
        "missing_verification_result_count": 4,
        "blocking_reason_count": 4,
        "verification_result_present_count": 0,
        "verified_ref_count": 0,
        "accepted_ref_count": 0,
        "bound_ref_count": 0,
        "stored_ref_count": 0,
        "authority_grant_count": 0,
        "verifier_execution_grant_count": 0,
    }
    for field_name, expected_value in expected.items():
        if summary.get(field_name) != expected_value:
            errors.append(f"summary.{field_name} must be {expected_value}")
    if len(review_items) != len(EXPECTED_REQUIRED_VALUE_REFS):
        errors.append("summary source review item count must stay canonical")


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
    """Run the personal-assistant ref absence closure review validator."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--receipt-schema", type=Path, default=DEFAULT_RECEIPT_SCHEMA)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    validation = validate_personal_assistant_ref_absence_closure_review(schema_path=args.schema, receipt_schema_path=args.receipt_schema)
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.valid:
        print("personal assistant ref absence closure review: valid")
    else:
        print("personal assistant ref absence closure review: invalid")
        for error in validation.errors:
            print(f"  - {error}")
    return 0 if validation.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
