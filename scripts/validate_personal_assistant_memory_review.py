#!/usr/bin/env python3
"""Validate personal-assistant memory observation review evidence.

Purpose: prove memory review decisions are schema-backed evidence records that
never write live memory or activate Nested Mind.
Governance scope: kept/rejected/revision/deferred/expired review evidence,
candidate and receipt conformance, private payload redaction, and Foundation
Mode no-effect boundaries.
Dependencies: personal-assistant memory runtime helpers, memory review schema,
memory observation schema, receipt schema, and schema validators.
Invariants:
  - Memory reviews record operator evidence only.
  - Kept and deferred reviews still do not admit observations into live memory.
  - Rejected and expired reviews block memory admission.
  - Raw private payloads and secret-like values are rejected.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent
MCOI_ROOT = REPO_ROOT / "mcoi"
for candidate_path in (REPO_ROOT, MCOI_ROOT):
    if str(candidate_path) not in sys.path:
        sys.path.insert(0, str(candidate_path))

from mcoi_runtime.personal_assistant import (  # noqa: E402
    MemoryConfidence,
    MemoryObservationSource,
    MemoryObservationType,
    MemoryRetentionPolicy,
    MemoryReviewDecision,
    MemoryScope,
    MemorySensitivity,
    NestedMindStatus,
    prepare_memory_observation,
    review_memory_observation_candidate,
)
from scripts.validate_personal_assistant_receipt import validate_personal_assistant_receipt_payload  # noqa: E402
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402

DEFAULT_REVIEW = REPO_ROOT / "examples" / "personal_assistant_memory_review_evidence.json"
DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "personal_assistant_memory_review.schema.json"
DEFAULT_OBSERVATION_SCHEMA = REPO_ROOT / "schemas" / "personal_assistant_memory_observation.schema.json"
DEFAULT_RECEIPT_SCHEMA = REPO_ROOT / "schemas" / "personal_assistant_receipt.schema.json"
RUNTIME_OBSERVED_AT = "2026-06-15T00:00:00+00:00"
RUNTIME_REVIEWED_AT = "2026-06-15T00:04:00+00:00"

REVIEW_DECISION_VALUES = (
    "kept_for_operator_review",
    "rejected",
    "revision_requested",
    "deferred",
    "expired",
)
FALSE_EFFECT_BOUNDARY_FIELDS = frozenset(
    {
        "execution_allowed",
        "live_memory_write_allowed",
        "memory_admission_allowed",
        "nested_mind_live_activation_allowed",
        "raw_private_payload_storage_allowed",
        "secret_value_storage_allowed",
        "connector_mutation_allowed",
        "system_of_record_write_allowed",
        "deployment_mutation_allowed",
        "public_readiness_claim_allowed",
        "customer_readiness_claim_allowed",
    }
)
FALSE_REVIEW_FIELDS = frozenset(
    {
        "live_memory_write_allowed",
        "memory_admission_allowed",
        "nested_mind_live_activation_allowed",
        "raw_private_payload_storage_allowed",
        "secret_value_storage_allowed",
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
RAW_PRIVATE_FIELD_NAMES = frozenset(
    {
        "raw_private_connector_payload",
        "raw_connector_payload",
        "private_connector_payload",
        "connector_response",
        "message_body",
        "email_body",
        "calendar_payload",
        "mailbox_payload",
        "raw_message",
        "raw_thread",
        "raw_calendar_event",
        "raw_task_payload",
        "raw_chat_log",
        "chat_log",
        "transcript",
        "credential",
        "credentials",
        "token",
        "secret",
        "private_key",
        "authorization",
        "cookie",
    }
)
ALLOWED_POLICY_FIELD_NAMES = frozenset(
    {
        "private_payload_policy",
        "raw_private_payload_serialized",
        "secret_values_serialized",
        "connector_payload_projection",
        "body_projection",
        "review_payload_projection",
    }
)


@dataclass(frozen=True, slots=True)
class PersonalAssistantMemoryReviewValidation:
    """Validation result for a memory review evidence envelope."""

    valid: bool
    review_path: str
    runtime_validated: bool
    review_count: int
    receipt_count: int
    assurance_outcome: str
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        rendered = asdict(self)
        rendered["errors"] = list(self.errors)
        return rendered


def validate_personal_assistant_memory_review(
    *,
    review_path: Path = DEFAULT_REVIEW,
    schema_path: Path = DEFAULT_SCHEMA,
    observation_schema_path: Path = DEFAULT_OBSERVATION_SCHEMA,
    receipt_schema_path: Path = DEFAULT_RECEIPT_SCHEMA,
    validate_runtime: bool = True,
) -> PersonalAssistantMemoryReviewValidation:
    """Validate a memory review fixture and optional runtime-generated envelope."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "memory review schema", errors)
    observation_schema = _load_json_object(observation_schema_path, "memory observation schema", errors)
    receipt_schema = _load_json_object(receipt_schema_path, "receipt schema", errors)
    review = _load_json_object(review_path, "memory review evidence", errors)
    assurance_outcome = ""
    if schema and review:
        errors.extend(_validate_schema_instance(schema, review))
    if review:
        assurance = _mapping(review.get("assurance"))
        assurance_outcome = str(assurance.get("outcome", ""))
        errors.extend(_validate_review_semantics(review, observation_schema, receipt_schema))
        _scan_private_or_secret_payload(review, errors, path="$")

    runtime_validated = False
    if validate_runtime and schema:
        runtime_review = build_runtime_memory_review_evidence()
        runtime_errors = list(_validate_schema_instance(schema, runtime_review))
        runtime_errors.extend(_validate_review_semantics(runtime_review, observation_schema, receipt_schema))
        _scan_private_or_secret_payload(runtime_review, runtime_errors, path="$runtime")
        if runtime_errors:
            errors.extend(f"runtime {message}" for message in runtime_errors)
        runtime_validated = not runtime_errors

    return PersonalAssistantMemoryReviewValidation(
        valid=not errors,
        review_path=_path_label(review_path),
        runtime_validated=runtime_validated,
        review_count=int(review.get("review_count", 0)) if isinstance(review, dict) else 0,
        receipt_count=len(review.get("receipt_ids", ())) if isinstance(review, dict) else 0,
        assurance_outcome=assurance_outcome,
        errors=tuple(errors),
    )


def build_runtime_memory_review_evidence() -> dict[str, Any]:
    """Build deterministic memory review evidence for all review decisions."""
    review_records: list[tuple[str, Mapping[str, Any]]] = []
    for index, decision in enumerate(REVIEW_DECISION_VALUES, start=1):
        candidate = prepare_memory_observation(
            request_id=f"pa_request_memory_review_{index:03d}",
            memory_observation_id=f"pa_memory_review_candidate_{decision}_{index:03d}",
            memory_type=MemoryObservationType.PREFERENCE,
            claim="User prefers one-at-a-time repository closures.",
            source=MemoryObservationSource(
                source_type="user_confirmation",
                source_ref=f"conversation:memory-review-{index:03d}",
                observed_at=RUNTIME_OBSERVED_AT,
            ),
            confidence=MemoryConfidence.HIGH,
            scope=MemoryScope.ASSISTANT_WORKFLOW,
            mutable=True,
            receipt_id=f"pa_receipt_memory_review_source_{index:03d}",
            evidence_refs=(f"proof://personal-assistant/memory/review-source-{index:03d}",),
            observed_at=RUNTIME_OBSERVED_AT,
            sensitivity=MemorySensitivity.INTERNAL,
            retention_policy=MemoryRetentionPolicy.OPERATOR_REVIEW,
            nested_mind_status=NestedMindStatus.STAGING_ONLY,
            metadata={"fixture": "runtime_memory_review_evidence"},
        )
        review = review_memory_observation_candidate(
            candidate=candidate,
            review_id=f"pa_memory_review_{decision}_{index:03d}",
            decision=MemoryReviewDecision.coerce(decision),
            reviewer_ref="operator:tamirat",
            reason_codes=(f"operator_{decision}_preview",),
            reviewed_at=RUNTIME_REVIEWED_AT,
            review_evidence_ref=f"proof://personal-assistant/memory/operator-review-{index:03d}",
            revision_request="Clarify scope before any future review." if decision == "revision_requested" else "",
            deferred_until="2026-06-16T00:00:00+00:00" if decision == "deferred" else "",
            expires_at="2026-06-15T01:00:00+00:00" if decision == "expired" else "",
            metadata={"fixture": "runtime_memory_review_evidence"},
        )
        review_records.append((review.review_id, review.as_dict()))
    return build_memory_review_evidence_envelope(
        generated_at=RUNTIME_REVIEWED_AT,
        review_records=tuple(review_records),
    )


def build_memory_review_evidence_envelope(
    *,
    generated_at: str,
    review_records: tuple[tuple[str, Mapping[str, Any]], ...],
) -> dict[str, Any]:
    """Build a schema-shaped no-effect envelope around memory reviews."""
    reviews: list[dict[str, Any]] = []
    review_ids: list[str] = []
    memory_observation_ids: list[str] = []
    receipt_ids: list[str] = []
    for review_id, record in review_records:
        review = _mapping(record.get("review"))
        candidate = _mapping(record.get("candidate"))
        receipt = _mapping(record.get("receipt"))
        observation_id = str(record.get("memory_observation_id", review.get("memory_observation_id", "")))
        review_ids.append(review_id)
        if observation_id and observation_id not in memory_observation_ids:
            memory_observation_ids.append(observation_id)
        receipt_id = str(receipt.get("receipt_id", ""))
        if receipt_id and receipt_id not in receipt_ids:
            receipt_ids.append(receipt_id)
        reviews.append(
            {
                "review_id": review_id,
                "memory_observation_id": observation_id,
                "decision": str(record.get("decision", review.get("decision", ""))),
                "reviewed_at": str(review.get("reviewed_at", "")),
                "reviewer_ref": str(review.get("reviewer_ref", "")),
                "reason_codes": list(review.get("reason_codes", ())),
                "review": dict(review),
                "candidate": dict(candidate),
                "receipt": dict(receipt),
            }
        )
    return {
        "review_set_id": "pa_memory_review_set_foundation_001",
        "generated_at": generated_at,
        "governed": True,
        "source_projection": "operator_supplied_memory_review_evidence",
        "review_count": len(reviews),
        "review_ids": review_ids,
        "memory_observation_ids": memory_observation_ids,
        "receipt_ids": receipt_ids,
        "reviews": reviews,
        "effect_boundary": {
            "memory_review_records_allowed": True,
            "execution_allowed": False,
            "live_memory_write_allowed": False,
            "memory_admission_allowed": False,
            "nested_mind_live_activation_allowed": False,
            "raw_private_payload_storage_allowed": False,
            "secret_value_storage_allowed": False,
            "connector_mutation_allowed": False,
            "system_of_record_write_allowed": False,
            "deployment_mutation_allowed": False,
            "public_readiness_claim_allowed": False,
            "customer_readiness_claim_allowed": False,
        },
        "private_payload_policy": {
            "raw_private_payload_serialized": False,
            "secret_values_serialized": False,
            "connector_payload_projection": "ref_only",
            "review_payload_projection": "bounded_operator_review_record",
        },
        "assurance": {
            "assurance_id": "personal_assistant_memory_review_no_effect_assurance",
            "outcome": "SolvedVerified",
            "foundation_only": True,
            "ready_for_live_memory_write": False,
            "ready_for_live_nested_mind_activation": False,
            "ready_for_customer_readiness_claim": False,
            "authority_drift_detected": False,
            "checked_controls": [
                "memory_review_is_not_memory_admission",
                "kept_review_deferred_without_write",
                "rejected_review_blocks_memory_admission",
                "revision_review_deferred_without_write",
                "deferred_review_deferred_without_write",
                "expired_review_blocks_memory_admission",
                "no_live_memory_write",
                "no_nested_mind_live_activation",
                "no_connector_mutation",
                "no_raw_private_payload_storage",
                "no_secret_value_serialization",
            ],
            "blocking_reasons": [],
            "next_action": "continue governed memory admission hardening before any live memory write",
        },
        "metadata": {
            "foundation_only": True,
            "projection_contract": "memory_review_evidence_only",
            "runtime_boundary": "review_does_not_write_memory",
            "live_memory_write_allowed": False,
            "memory_admission_allowed": False,
            "nested_mind_live_activation_allowed": False,
            "connector_mutation_allowed": False,
            "system_of_record_write_allowed": False,
        },
    }


def _validate_review_semantics(
    review: dict[str, Any],
    observation_schema: dict[str, Any],
    receipt_schema: dict[str, Any],
) -> tuple[str, ...]:
    errors: list[str] = []
    effect_boundary = _mapping(review.get("effect_boundary"))
    if effect_boundary.get("memory_review_records_allowed") is not True:
        errors.append("effect_boundary.memory_review_records_allowed must be true")
    _require_false_fields(effect_boundary, FALSE_EFFECT_BOUNDARY_FIELDS, "effect_boundary", errors)
    private_policy = _mapping(review.get("private_payload_policy"))
    if private_policy.get("raw_private_payload_serialized") is not False:
        errors.append("private_payload_policy.raw_private_payload_serialized must be false")
    if private_policy.get("secret_values_serialized") is not False:
        errors.append("private_payload_policy.secret_values_serialized must be false")
    assurance = _mapping(review.get("assurance"))
    if assurance.get("foundation_only") is not True:
        errors.append("assurance.foundation_only must be true")
    if assurance.get("ready_for_live_memory_write") is not False:
        errors.append("assurance.ready_for_live_memory_write must be false")
    if assurance.get("ready_for_live_nested_mind_activation") is not False:
        errors.append("assurance.ready_for_live_nested_mind_activation must be false")
    if assurance.get("ready_for_customer_readiness_claim") is not False:
        errors.append("assurance.ready_for_customer_readiness_claim must be false")
    if assurance.get("authority_drift_detected") is False and assurance.get("blocking_reasons") != []:
        errors.append("assurance.blocking_reasons must be empty when authority_drift_detected is false")

    items = review.get("reviews")
    if not isinstance(items, list):
        errors.append("reviews must be a list")
        return tuple(errors)
    if review.get("review_count") != len(items):
        errors.append("review_count must equal reviews length")
    review_ids: list[str] = []
    observation_ids: list[str] = []
    receipt_ids: list[str] = []
    seen_decisions: set[str] = set()
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(f"reviews[{index}] must be an object")
            continue
        review_ids.append(str(item.get("review_id", "")))
        item_review = _mapping(item.get("review"))
        candidate = _mapping(item.get("candidate"))
        observation = _mapping(candidate.get("observation"))
        candidate_receipt = _mapping(candidate.get("receipt"))
        review_receipt = _mapping(item.get("receipt"))
        item_decision = str(item.get("decision", ""))
        seen_decisions.add(item_decision)
        observation_id = str(item.get("memory_observation_id", ""))
        if observation_id and observation_id not in observation_ids:
            observation_ids.append(observation_id)
        if observation_schema:
            errors.extend(
                f"reviews[{index}].candidate.observation {message}"
                for message in _validate_schema_instance(observation_schema, observation)
            )
        if receipt_schema:
            errors.extend(
                f"reviews[{index}].candidate.receipt {message}"
                for message in _validate_schema_instance(receipt_schema, candidate_receipt)
            )
            errors.extend(
                f"reviews[{index}].receipt {message}"
                for message in _validate_schema_instance(receipt_schema, review_receipt)
            )
        errors.extend(
            f"reviews[{index}].candidate.receipt {message}"
            for message in validate_personal_assistant_receipt_payload(candidate_receipt)
        )
        errors.extend(
            f"reviews[{index}].receipt {message}"
            for message in validate_personal_assistant_receipt_payload(review_receipt)
        )
        if item_review.get("review_id") != item.get("review_id"):
            errors.append(f"reviews[{index}].review_id must match review.review_id")
        if item_review.get("memory_observation_id") != observation_id:
            errors.append(f"reviews[{index}].memory_observation_id must match review.memory_observation_id")
        if observation.get("memory_observation_id") != observation_id:
            errors.append(f"reviews[{index}].memory_observation_id must match candidate observation")
        if item_review.get("decision") != item_decision:
            errors.append(f"reviews[{index}].decision must match review.decision")
        _require_false_fields(item_review, FALSE_REVIEW_FIELDS, f"reviews[{index}].review", errors)
        if item_decision == "revision_requested" and not item_review.get("revision_request"):
            errors.append(f"reviews[{index}].review.revision_request is required for revision_requested")
        if item_decision == "deferred" and not item_review.get("deferred_until"):
            errors.append(f"reviews[{index}].review.deferred_until is required for deferred")
        if item_decision == "expired" and not item_review.get("expires_at"):
            errors.append(f"reviews[{index}].review.expires_at is required for expired")
        expected_receipt_decision = "blocked" if item_decision in {"rejected", "expired"} else "deferred"
        if review_receipt.get("decision") != expected_receipt_decision:
            errors.append(f"reviews[{index}].receipt.decision must be {expected_receipt_decision} for {item_decision}")
        if observation_id not in review_receipt.get("memory_observation_refs", ()):
            errors.append(f"reviews[{index}].receipt.memory_observation_refs must include memory_observation_id")
        receipt_metadata = _mapping(review_receipt.get("metadata"))
        for field_name in (
            "live_memory_write_allowed",
            "memory_admission_allowed",
            "nested_mind_live_activation_allowed",
        ):
            if receipt_metadata.get(field_name) is not False:
                errors.append(f"reviews[{index}].receipt.metadata.{field_name} must be false")
        receipt_id = review_receipt.get("receipt_id")
        if isinstance(receipt_id, str):
            receipt_ids.append(receipt_id)
    missing_decisions = set(REVIEW_DECISION_VALUES).difference(seen_decisions)
    if missing_decisions:
        errors.append(f"reviews must include {','.join(sorted(missing_decisions))}")
    if review.get("review_ids") != review_ids:
        errors.append("review_ids must match reviews order")
    if sorted(review.get("memory_observation_ids", ())) != sorted(observation_ids):
        errors.append("memory_observation_ids must match embedded candidates")
    if sorted(review.get("receipt_ids", ())) != sorted(receipt_ids):
        errors.append("receipt_ids must match embedded receipts")
    return tuple(errors)


def _require_false_fields(payload: Mapping[str, Any], fields: frozenset[str], label: str, errors: list[str]) -> None:
    model = _mapping(payload)
    if not model:
        errors.append(f"{label} must be an object")
        return
    for field_name in sorted(fields):
        if model.get(field_name) is not False:
            errors.append(f"{label}.{field_name} must be false")


def _scan_private_or_secret_payload(payload: Any, errors: list[str], *, path: str) -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            normalized_key = str(key).lower()
            if normalized_key not in ALLOWED_POLICY_FIELD_NAMES and normalized_key in RAW_PRIVATE_FIELD_NAMES:
                errors.append(f"{path}.{key}: raw private or secret field is forbidden")
            _scan_private_or_secret_payload(value, errors, path=f"{path}.{key}")
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            _scan_private_or_secret_payload(value, errors, path=f"{path}[{index}]")
    elif isinstance(payload, str):
        for pattern in SECRET_VALUE_PATTERNS:
            if pattern.search(payload):
                errors.append(f"{path}: secret-like value must not be serialized")
                break


def _mapping(payload: Any) -> dict[str, Any]:
    return dict(payload) if isinstance(payload, dict) else {}


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        errors.append(f"{label} could not be read")
        return {}
    except json.JSONDecodeError:
        errors.append(f"{label} must be JSON")
        return {}
    if not isinstance(parsed, dict):
        errors.append(f"{label} root must be an object")
        return {}
    return parsed


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse memory review validation arguments."""
    parser = argparse.ArgumentParser(description="Validate personal-assistant memory review evidence.")
    parser.add_argument("--review", default=str(DEFAULT_REVIEW))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--observation-schema", default=str(DEFAULT_OBSERVATION_SCHEMA))
    parser.add_argument("--receipt-schema", default=str(DEFAULT_RECEIPT_SCHEMA))
    parser.add_argument("--skip-runtime", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for memory review validation."""
    args = parse_args(argv)
    result = validate_personal_assistant_memory_review(
        review_path=Path(args.review),
        schema_path=Path(args.schema),
        observation_schema_path=Path(args.observation_schema),
        receipt_schema_path=Path(args.receipt_schema),
        validate_runtime=not args.skip_runtime,
    )
    if args.json:
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    elif result.valid:
        print(
            "personal-assistant memory review ok "
            f"reviews={result.review_count} receipts={result.receipt_count} "
            f"runtime_validated={result.runtime_validated}"
        )
    else:
        for error in result.errors:
            print(f"error: {error}")
    return 0 if result.valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
