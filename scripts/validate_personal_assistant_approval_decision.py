#!/usr/bin/env python3
"""Validate personal-assistant approval decision evidence.

Purpose: prove approval decisions are schema-backed evidence records that never
execute effect-bearing personal-assistant actions.
Governance scope: approve/reject/revise/expire decision evidence, packet and
receipt conformance, private payload redaction, and Foundation Mode no-effect
boundaries.
Dependencies: personal-assistant approval queue runtime helpers, approval
decision schema, approval packet schema, receipt schema, and schema validators.
Invariants:
  - Approval decisions record operator evidence only.
  - Approved decisions still defer execution to a later governed execution gate.
  - Rejected and expired decisions block execution.
  - Raw private payloads and secret-like values are rejected.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent
MCOI_ROOT = REPO_ROOT / "mcoi"
for candidate in (REPO_ROOT, MCOI_ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from mcoi_runtime.personal_assistant import (  # noqa: E402
    ApprovalDecision,
    ApprovalProposedAction,
    ApprovalScope,
    PersonalAssistantApprovalQueue,
)
from scripts.personal_assistant_source_digest import canonical_source_sha256  # noqa: E402
from scripts.validate_personal_assistant_receipt import validate_personal_assistant_receipt_payload  # noqa: E402
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402

DEFAULT_DECISION = REPO_ROOT / "examples" / "personal_assistant_approval_decision_evidence.json"
DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "personal_assistant_approval_decision.schema.json"
DEFAULT_APPROVAL_SCHEMA = REPO_ROOT / "schemas" / "personal_assistant_approval.schema.json"
DEFAULT_RECEIPT_SCHEMA = REPO_ROOT / "schemas" / "personal_assistant_receipt.schema.json"
DEFAULT_APPROVAL_REVIEW_PACKET = REPO_ROOT / "examples" / "personal_assistant_approval_review_packet.json"
RUNTIME_CREATED_AT = "2026-06-14T00:00:00+00:00"
RUNTIME_DECIDED_AT = "2026-06-14T00:03:00+00:00"

FALSE_EFFECT_BOUNDARY_FIELDS = frozenset(
    {
        "execution_allowed",
        "approval_is_execution",
        "live_connector_execution_allowed",
        "external_send_allowed",
        "calendar_write_allowed",
        "task_write_allowed",
        "memory_write_allowed",
        "connector_mutation_allowed",
        "system_of_record_write_allowed",
        "deployment_mutation_allowed",
        "nested_mind_live_activation_allowed",
        "public_readiness_claim_allowed",
    }
)
DECISION_VALUES = ("approved", "rejected", "revised", "expired")
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
        "decision_payload_projection",
        "payload_digest_only",
    }
)


@dataclass(frozen=True, slots=True)
class PersonalAssistantApprovalDecisionValidation:
    """Validation result for an approval decision evidence envelope."""

    valid: bool
    decision_path: str
    runtime_validated: bool
    decision_count: int
    receipt_count: int
    assurance_outcome: str
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        rendered = asdict(self)
        rendered["errors"] = list(self.errors)
        return rendered


def validate_personal_assistant_approval_decision(
    *,
    decision_path: Path = DEFAULT_DECISION,
    schema_path: Path = DEFAULT_SCHEMA,
    approval_schema_path: Path = DEFAULT_APPROVAL_SCHEMA,
    receipt_schema_path: Path = DEFAULT_RECEIPT_SCHEMA,
    validate_runtime: bool = True,
) -> PersonalAssistantApprovalDecisionValidation:
    """Validate a decision fixture and optional runtime-generated envelope."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "approval decision schema", errors)
    approval_schema = _load_json_object(approval_schema_path, "approval schema", errors)
    receipt_schema = _load_json_object(receipt_schema_path, "receipt schema", errors)
    decision = _load_json_object(decision_path, "approval decision evidence", errors)
    assurance_outcome = ""
    if schema and decision:
        errors.extend(_validate_schema_instance(schema, decision))
    if decision:
        assurance = _mapping(decision.get("assurance"))
        assurance_outcome = str(assurance.get("outcome", ""))
        errors.extend(_validate_decision_semantics(decision, approval_schema, receipt_schema))
        _scan_private_or_secret_payload(decision, errors, path="$")

    runtime_validated = False
    if validate_runtime and schema:
        runtime_decision = build_runtime_approval_decision_evidence()
        runtime_errors = list(_validate_schema_instance(schema, runtime_decision))
        runtime_errors.extend(_validate_decision_semantics(runtime_decision, approval_schema, receipt_schema))
        _scan_private_or_secret_payload(runtime_decision, runtime_errors, path="$runtime")
        if runtime_errors:
            errors.extend(f"runtime {message}" for message in runtime_errors)
        runtime_validated = not runtime_errors

    return PersonalAssistantApprovalDecisionValidation(
        valid=not errors,
        decision_path=_path_label(decision_path),
        runtime_validated=runtime_validated,
        decision_count=int(decision.get("decision_count", 0)) if isinstance(decision, dict) else 0,
        receipt_count=len(decision.get("receipt_ids", ())) if isinstance(decision, dict) else 0,
        assurance_outcome=assurance_outcome,
        errors=tuple(errors),
    )


def build_runtime_approval_decision_evidence() -> dict[str, Any]:
    """Build deterministic approval decision evidence for all decision states."""
    decision_records: list[tuple[str, Mapping[str, Any], Mapping[str, Any]]] = []
    for index, decision in enumerate(DECISION_VALUES, start=1):
        queue = PersonalAssistantApprovalQueue()
        approval_id = f"pa_approval_decision_{decision}_{index:03d}"
        record = queue.enqueue(
            request_id=f"pa_request_decision_{decision}_{index:03d}",
            plan_id=f"pa_plan_decision_{decision}_{index:03d}",
            approver_ref="operator:tamirat",
            approval_scope=ApprovalScope.PER_RECIPIENT,
            proposed_actions=(
                ApprovalProposedAction(
                    action_id="send_prepared_email_draft",
                    skill_id="email.send.with_approval",
                    risk_level="P4",
                    effect_boundary="external_email_send",
                    summary="Send one approved email draft to one named recipient.",
                ),
            ),
            forbidden_without_approval=("send", "forward", "recipient_unapproved", "connector_mutation"),
            evidence_refs=(f"proof://personal-assistant/approval/{decision}-{index:03d}",),
            created_at=RUNTIME_CREATED_AT,
            approval_id=approval_id,
        )
        source_record = record.as_dict()
        updated = queue.record_decision(
            record.approval_id,
            decision=ApprovalDecision.coerce(decision),
            reason_codes=(f"operator_{decision}_preview",),
            decided_at=RUNTIME_DECIDED_AT,
            decision_evidence_ref=f"proof://personal-assistant/approval/operator-{decision}-{index:03d}",
            revision_request="Revise the draft before any future approval." if decision == "revised" else "",
        )
        decision_records.append((f"pa_approval_decision_{decision}_{index:03d}", source_record, updated.as_dict()))
    return build_approval_decision_evidence_envelope(
        generated_at=RUNTIME_DECIDED_AT,
        decision_records=tuple(decision_records),
    )


def build_approval_decision_evidence_envelope(
    *,
    generated_at: str,
    decision_records: tuple[tuple[str, Mapping[str, Any], Mapping[str, Any]], ...],
) -> dict[str, Any]:
    """Build a schema-shaped no-effect envelope around approval decisions."""
    decisions: list[dict[str, Any]] = []
    decision_ids: list[str] = []
    approval_ids: list[str] = []
    receipt_ids: list[str] = []
    for decision_id, source_record, record in decision_records:
        packet = _mapping(record.get("packet"))
        receipts = record.get("receipts", ())
        if not isinstance(receipts, Sequence) or isinstance(receipts, (str, bytes)) or not receipts:
            receipt = {}
        else:
            receipt = _mapping(receipts[-1])
        approval_id = str(record.get("approval_id", packet.get("approval_id", "")))
        decision_record = _mapping(packet.get("decision_record"))
        decision_ids.append(decision_id)
        if approval_id and approval_id not in approval_ids:
            approval_ids.append(approval_id)
        receipt_id = str(receipt.get("receipt_id", ""))
        if receipt_id and receipt_id not in receipt_ids:
            receipt_ids.append(receipt_id)
        decisions.append(
            {
                "decision_id": decision_id,
                "approval_id": approval_id,
                "request_id": str(packet.get("request_id", "")),
                "plan_id": str(packet.get("plan_id", "")),
                "decision": str(decision_record.get("decision", "")),
                "decided_at": str(decision_record.get("decided_at", "")),
                "reason_codes": list(decision_record.get("reason_codes", ())),
                "queue_precondition_ref": _queue_precondition_ref(source_record),
                "packet": dict(packet),
                "receipt": dict(receipt),
            }
        )
    return {
        "decision_set_id": "pa_approval_decision_set_foundation_001",
        "generated_at": generated_at,
        "governed": True,
        "source_projection": "operator_supplied_decision_evidence",
        "decision_count": len(decisions),
        "decision_ids": decision_ids,
        "approval_ids": approval_ids,
        "receipt_ids": receipt_ids,
        "decisions": decisions,
        "effect_boundary": {
            "approval_decision_records_allowed": True,
            "execution_allowed": False,
            "approval_is_execution": False,
            "live_connector_execution_allowed": False,
            "external_send_allowed": False,
            "calendar_write_allowed": False,
            "task_write_allowed": False,
            "memory_write_allowed": False,
            "connector_mutation_allowed": False,
            "system_of_record_write_allowed": False,
            "deployment_mutation_allowed": False,
            "nested_mind_live_activation_allowed": False,
            "public_readiness_claim_allowed": False,
        },
        "private_payload_policy": {
            "raw_private_payload_serialized": False,
            "secret_values_serialized": False,
            "connector_payload_projection": "ref_only",
            "decision_payload_projection": "bounded_operator_decision_record",
        },
        "assurance": {
            "assurance_id": "personal_assistant_approval_decision_no_effect_assurance",
            "outcome": "SolvedVerified",
            "foundation_only": True,
            "ready_for_live_execution": False,
            "ready_for_customer_readiness_claim": False,
            "authority_drift_detected": False,
            "checked_controls": [
                "approval_decision_is_not_execution",
                "approved_decision_deferred",
                "rejected_decision_blocks_execution",
                "revised_decision_deferred",
                "expired_decision_blocks_execution",
                "no_live_connector_execution",
                "no_external_send",
                "no_connector_mutation",
                "no_memory_write",
                "no_secret_value_serialization",
            ],
            "blocking_reasons": [],
            "next_action": "continue execution-gate hardening before any effect-bearing dispatch",
        },
        "metadata": {
            "foundation_only": True,
            "projection_contract": "approval_decision_evidence_only",
            "runtime_boundary": "decision_does_not_execute",
            "live_connector_execution_allowed": False,
            "connector_mutation_allowed": False,
            "external_send_allowed": False,
            "system_of_record_write_allowed": False,
            "memory_write_allowed": False,
        },
    }


def _validate_decision_semantics(
    decision: dict[str, Any],
    approval_schema: dict[str, Any],
    receipt_schema: dict[str, Any],
) -> tuple[str, ...]:
    errors: list[str] = []
    effect_boundary = _mapping(decision.get("effect_boundary"))
    if effect_boundary.get("approval_decision_records_allowed") is not True:
        errors.append("effect_boundary.approval_decision_records_allowed must be true")
    _require_false_fields(effect_boundary, FALSE_EFFECT_BOUNDARY_FIELDS, "effect_boundary", errors)
    private_policy = _mapping(decision.get("private_payload_policy"))
    if private_policy.get("raw_private_payload_serialized") is not False:
        errors.append("private_payload_policy.raw_private_payload_serialized must be false")
    if private_policy.get("secret_values_serialized") is not False:
        errors.append("private_payload_policy.secret_values_serialized must be false")
    assurance = _mapping(decision.get("assurance"))
    if assurance.get("foundation_only") is not True:
        errors.append("assurance.foundation_only must be true")
    if assurance.get("ready_for_live_execution") is not False:
        errors.append("assurance.ready_for_live_execution must be false")
    if assurance.get("ready_for_customer_readiness_claim") is not False:
        errors.append("assurance.ready_for_customer_readiness_claim must be false")
    if assurance.get("authority_drift_detected") is False and assurance.get("blocking_reasons") != []:
        errors.append("assurance.blocking_reasons must be empty when authority_drift_detected is false")

    items = decision.get("decisions")
    if not isinstance(items, list):
        errors.append("decisions must be a list")
        return tuple(errors)
    if decision.get("decision_count") != len(items):
        errors.append("decision_count must equal decisions length")
    decision_ids: list[str] = []
    approval_ids: list[str] = []
    receipt_ids: list[str] = []
    seen_decisions: set[str] = set()
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(f"decisions[{index}] must be an object")
            continue
        decision_id = item.get("decision_id")
        if isinstance(decision_id, str):
            decision_ids.append(decision_id)
        approval_id = item.get("approval_id")
        if isinstance(approval_id, str) and approval_id not in approval_ids:
            approval_ids.append(approval_id)
        packet = _mapping(item.get("packet"))
        receipt = _mapping(item.get("receipt"))
        queue_precondition_ref = _mapping(item.get("queue_precondition_ref"))
        if approval_schema:
            errors.extend(
                f"decisions[{index}].packet {message}"
                for message in _validate_schema_instance(approval_schema, packet)
            )
        if receipt_schema:
            errors.extend(
                f"decisions[{index}].receipt {message}"
                for message in _validate_schema_instance(receipt_schema, receipt)
            )
        errors.extend(
            f"decisions[{index}].receipt {message}"
            for message in validate_personal_assistant_receipt_payload(receipt)
        )
        packet_decision = _mapping(packet.get("decision_record")).get("decision")
        item_decision = item.get("decision")
        seen_decisions.add(str(item_decision))
        if item_decision != packet_decision:
            errors.append(f"decisions[{index}].decision must match packet decision_record.decision")
        if packet.get("approval_id") != item.get("approval_id"):
            errors.append(f"decisions[{index}].approval_id must match packet.approval_id")
        if packet.get("request_id") != item.get("request_id"):
            errors.append(f"decisions[{index}].request_id must match packet.request_id")
        if packet.get("plan_id") != item.get("plan_id"):
            errors.append(f"decisions[{index}].plan_id must match packet.plan_id")
        errors.extend(
            _validate_queue_precondition_ref(
                queue_precondition_ref,
                item,
                source_review_packet_path=DEFAULT_APPROVAL_REVIEW_PACKET,
                label=f"decisions[{index}].queue_precondition_ref",
            )
        )
        if receipt.get("approval_ref") != item.get("approval_id"):
            errors.append(f"decisions[{index}].receipt.approval_ref must match approval_id")
        if receipt.get("approval_required") is not True:
            errors.append(f"decisions[{index}].receipt.approval_required must be true")
        if item_decision in {"approved", "revised"} and receipt.get("decision") != "deferred":
            errors.append(f"decisions[{index}].receipt.decision must be deferred for {item_decision}")
        if item_decision in {"rejected", "expired"} and receipt.get("decision") != "blocked":
            errors.append(f"decisions[{index}].receipt.decision must be blocked for {item_decision}")
        receipt_metadata = _mapping(receipt.get("metadata"))
        for field_name in (
            "approval_is_execution",
            "live_connector_execution_allowed",
            "connector_mutation_allowed",
            "external_write_allowed",
            "system_of_record_write_allowed",
            "money_legal_public_action_allowed",
        ):
            if receipt_metadata.get(field_name) is not False:
                errors.append(f"decisions[{index}].receipt.metadata.{field_name} must be false")
        receipt_id = receipt.get("receipt_id")
        if isinstance(receipt_id, str):
            receipt_ids.append(receipt_id)
    missing_decisions = set(DECISION_VALUES).difference(seen_decisions)
    if missing_decisions:
        errors.append(f"decisions must include {','.join(sorted(missing_decisions))}")
    if decision.get("decision_ids") != decision_ids:
        errors.append("decision_ids must match decisions order")
    if sorted(decision.get("approval_ids", ())) != sorted(approval_ids):
        errors.append("approval_ids must match embedded packets")
    if sorted(decision.get("receipt_ids", ())) != sorted(receipt_ids):
        errors.append("receipt_ids must match embedded receipts")
    return tuple(errors)


def _queue_precondition_ref(source_record: Mapping[str, Any]) -> dict[str, Any]:
    source_packet = _mapping(source_record.get("packet"))
    source_metadata = _mapping(source_packet.get("metadata"))
    source_receipts = source_record.get("receipts", ())
    if isinstance(source_receipts, Sequence) and not isinstance(source_receipts, (str, bytes)) and source_receipts:
        source_receipt = _mapping(source_receipts[-1])
    else:
        source_receipt = {}
    review_packet_ref = _mapping(source_record.get("review_packet_ref"))
    ref = {
        "source_projection": "personal_assistant_approval_queue_read_model",
        "approval_id": str(source_record.get("approval_id", source_packet.get("approval_id", ""))),
        "request_id": str(source_packet.get("request_id", "")),
        "plan_id": str(source_packet.get("plan_id", "")),
        "source_queue_state": str(source_metadata.get("queue_state", source_packet.get("approval_state", ""))),
        "source_receipt_id": str(source_receipt.get("receipt_id", "")),
        "source_review_packet_id": str(review_packet_ref.get("review_packet_id", "")),
        "source_review_packet_sha256": str(review_packet_ref.get("source_sha256", "")),
        "payload_digest_only": True,
        "decision_precondition_met": True,
        "execution_allowed": False,
        "approval_is_execution": False,
        "external_send_allowed": False,
        "connector_mutation_allowed": False,
        "system_of_record_write_allowed": False,
    }
    ref["queue_precondition_sha256"] = _queue_precondition_sha256(ref)
    return ref


def _validate_queue_precondition_ref(
    ref: Mapping[str, Any],
    item: Mapping[str, Any],
    *,
    source_review_packet_path: Path,
    label: str,
) -> tuple[str, ...]:
    errors: list[str] = []
    if not ref:
        return (f"{label} must be an object",)
    expected_pairs = {
        "source_projection": "personal_assistant_approval_queue_read_model",
        "approval_id": item.get("approval_id"),
        "request_id": item.get("request_id"),
        "plan_id": item.get("plan_id"),
        "source_queue_state": "requested",
        "source_review_packet_id": "pa_approval_review_approval_review_packet_001",
    }
    for field_name, expected in expected_pairs.items():
        if ref.get(field_name) != expected:
            errors.append(f"{label}.{field_name} must be {expected}")
    source_receipt_id = ref.get("source_receipt_id")
    if not isinstance(source_receipt_id, str) or not source_receipt_id.startswith("pa_receipt_"):
        errors.append(f"{label}.source_receipt_id must be a receipt id")
    elif not source_receipt_id.endswith("_request"):
        errors.append(f"{label}.source_receipt_id must bind the requested queue receipt")
    if source_receipt_id == _mapping(item.get("receipt")).get("receipt_id"):
        errors.append(f"{label}.source_receipt_id must differ from decision receipt")
    if source_review_packet_path.exists():
        observed_sha256 = canonical_source_sha256(source_review_packet_path)
        if ref.get("source_review_packet_sha256") != observed_sha256:
            errors.append(f"{label}.source_review_packet_sha256 does not match approval review packet")
    else:
        errors.append(f"{label}.source_review_packet source does not exist")
    for field_name in (
        "payload_digest_only",
        "decision_precondition_met",
    ):
        if ref.get(field_name) is not True:
            errors.append(f"{label}.{field_name} must be true")
    for field_name in (
        "execution_allowed",
        "approval_is_execution",
        "external_send_allowed",
        "connector_mutation_allowed",
        "system_of_record_write_allowed",
    ):
        if ref.get(field_name) is not False:
            errors.append(f"{label}.{field_name} must be false")
    expected_digest = _queue_precondition_sha256(ref)
    if ref.get("queue_precondition_sha256") != expected_digest:
        errors.append(f"{label}.queue_precondition_sha256 does not match queue precondition fields")
    return tuple(errors)


def _queue_precondition_sha256(ref: Mapping[str, Any]) -> str:
    material = {key: value for key, value in ref.items() if key != "queue_precondition_sha256"}
    encoded = json.dumps(material, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


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
    """Parse approval decision validation arguments."""
    parser = argparse.ArgumentParser(description="Validate personal-assistant approval decision evidence.")
    parser.add_argument("--decision", default=str(DEFAULT_DECISION))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--approval-schema", default=str(DEFAULT_APPROVAL_SCHEMA))
    parser.add_argument("--receipt-schema", default=str(DEFAULT_RECEIPT_SCHEMA))
    parser.add_argument("--skip-runtime", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for approval decision validation."""
    args = parse_args(argv)
    result = validate_personal_assistant_approval_decision(
        decision_path=Path(args.decision),
        schema_path=Path(args.schema),
        approval_schema_path=Path(args.approval_schema),
        receipt_schema_path=Path(args.receipt_schema),
        validate_runtime=not args.skip_runtime,
    )
    if args.json:
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    elif result.valid:
        print(
            "personal-assistant approval decision ok "
            f"decisions={result.decision_count} receipts={result.receipt_count} "
            f"runtime_validated={result.runtime_validated}"
        )
    else:
        for error in result.errors:
            print(f"error: {error}")
    return 0 if result.valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
