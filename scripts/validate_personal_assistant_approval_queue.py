#!/usr/bin/env python3
"""Validate a personal-assistant approval queue read-model fixture.

Purpose: ensure approval queue projections remain evidence-only, schema-backed,
and unable to imply send, connector mutation, or system-of-record execution.
Governance scope: approval packet schema conformance, receipt conformance,
no secret serialization, no raw private payload projection, and no approval-as-
execution overclaim.
Dependencies: personal-assistant approval queue schema, approval schema,
receipt schema, and example read-model fixture.
Invariants:
  - Approval queue read models never grant execution authority.
  - Every queued packet validates against the approval packet schema.
  - Every queue receipt validates against the receipt schema and semantic checks.
  - Secret-like values and raw private connector payloads are rejected.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.personal_assistant_source_digest import canonical_source_sha256  # noqa: E402
from scripts.validate_personal_assistant_receipt import validate_personal_assistant_receipt_payload  # noqa: E402
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402

DEFAULT_QUEUE = REPO_ROOT / "examples" / "personal_assistant_approval_queue_read_model.json"
DEFAULT_QUEUE_SCHEMA = REPO_ROOT / "schemas" / "personal_assistant_approval_queue.schema.json"
DEFAULT_APPROVAL_SCHEMA = REPO_ROOT / "schemas" / "personal_assistant_approval.schema.json"
DEFAULT_RECEIPT_SCHEMA = REPO_ROOT / "schemas" / "personal_assistant_receipt.schema.json"

SECRET_VALUE_PATTERNS = (
    re.compile(r"sk_live_[A-Za-z0-9]+"),
    re.compile(r"ghp_[A-Za-z0-9]+"),
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
    }
)
WORKFLOW_STAGE_ORDER = (
    "draft_action",
    "risk_class",
    "requested_approval",
    "operator_decision",
    "receipt",
)
WORKFLOW_DECISION_CONTROLS = ("approve", "reject", "revise")
WORKFLOW_FALSE_FIELDS = (
    "approval_decision_executes_action",
    "execution_allowed",
    "live_connector_execution_allowed",
    "external_send_allowed",
    "connector_mutation_allowed",
    "system_of_record_write_allowed",
)
EXPECTED_REVIEW_REF_PATHS = {
    "source_ref": "examples/personal_assistant_approval_review_packet.json",
    "schema_ref": "schemas/personal_assistant_approval_review_packet.schema.json",
}
REVIEW_REF_FALSE_FIELDS = ("execution_allowed", "approval_enqueued")


@dataclass(frozen=True, slots=True)
class PersonalAssistantApprovalQueueValidation:
    """Validation result for one approval queue projection."""

    valid: bool
    queue_path: str
    approval_count: int
    receipt_count: int
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        rendered = asdict(self)
        rendered["errors"] = list(self.errors)
        return rendered


def validate_personal_assistant_approval_queue(
    *,
    queue_path: Path = DEFAULT_QUEUE,
    queue_schema_path: Path = DEFAULT_QUEUE_SCHEMA,
    approval_schema_path: Path = DEFAULT_APPROVAL_SCHEMA,
    receipt_schema_path: Path = DEFAULT_RECEIPT_SCHEMA,
) -> PersonalAssistantApprovalQueueValidation:
    """Validate one personal-assistant approval queue read model."""
    errors: list[str] = []
    queue_schema = _load_json_object(queue_schema_path, "approval queue schema", errors)
    approval_schema = _load_json_object(approval_schema_path, "approval schema", errors)
    receipt_schema = _load_json_object(receipt_schema_path, "receipt schema", errors)
    queue = _load_json_object(queue_path, "approval queue read model", errors)
    if queue_schema and queue:
        errors.extend(_validate_schema_instance(queue_schema, queue))
    if queue:
        errors.extend(_validate_queue_semantics(queue, approval_schema, receipt_schema))
        _scan_private_or_secret_payload(queue, errors, path="$")
    return PersonalAssistantApprovalQueueValidation(
        valid=not errors,
        queue_path=_path_label(queue_path),
        approval_count=int(queue.get("approval_count", 0)) if isinstance(queue, dict) else 0,
        receipt_count=len(queue.get("receipt_ids", ())) if isinstance(queue, dict) else 0,
        errors=tuple(errors),
    )


def _validate_queue_semantics(
    queue: dict[str, Any],
    approval_schema: dict[str, Any],
    receipt_schema: dict[str, Any],
) -> tuple[str, ...]:
    errors: list[str] = []
    for field_name in (
        "execution_allowed",
        "live_connector_execution_allowed",
        "external_send_allowed",
        "connector_mutation_allowed",
        "system_of_record_write_allowed",
        "approval_is_execution",
    ):
        if queue.get(field_name) is not False:
            errors.append(f"{field_name} must be false")
    metadata = queue.get("metadata", {})
    if not isinstance(metadata, dict):
        errors.append("metadata must be an object")
    else:
        if metadata.get("foundation_only") is not True:
            errors.append("metadata.foundation_only must be true")
        if metadata.get("approval_decision_executes_action") is not False:
            errors.append("metadata.approval_decision_executes_action must be false")

    records = queue.get("records", ())
    if not isinstance(records, list):
        errors.append("records must be a list")
        return tuple(errors)
    if queue.get("approval_count") != len(records):
        errors.append("approval_count must equal records length")

    receipt_ids: list[str] = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            errors.append(f"records[{index}] must be an object")
            continue
        packet = record.get("packet")
        receipts = record.get("receipts")
        _validate_review_packet_ref(record.get("review_packet_ref"), errors, label=f"records[{index}].review_packet_ref")
        if isinstance(packet, dict) and approval_schema:
            errors.extend(f"records[{index}].packet {message}" for message in _validate_schema_instance(approval_schema, packet))
            if packet.get("approval_id") != record.get("approval_id"):
                errors.append(f"records[{index}].approval_id must match packet.approval_id")
        else:
            errors.append(f"records[{index}].packet must be an object")
        if not isinstance(receipts, list) or not receipts:
            errors.append(f"records[{index}].receipts must be a non-empty list")
            continue
        for receipt_index, receipt in enumerate(receipts):
            if not isinstance(receipt, dict):
                errors.append(f"records[{index}].receipts[{receipt_index}] must be an object")
                continue
            if receipt_schema:
                errors.extend(
                    f"records[{index}].receipts[{receipt_index}] {message}"
                    for message in _validate_schema_instance(receipt_schema, receipt)
                )
            errors.extend(
                f"records[{index}].receipts[{receipt_index}] {message}"
                for message in validate_personal_assistant_receipt_payload(receipt)
            )
            receipt_id = receipt.get("receipt_id")
            if isinstance(receipt_id, str):
                receipt_ids.append(receipt_id)
    if sorted(queue.get("receipt_ids", ())) != sorted(receipt_ids):
        errors.append("receipt_ids must match receipts embedded in records")
    _validate_workflow_v0(queue, records, receipt_ids, errors)
    return tuple(errors)


def _validate_workflow_v0(
    queue: dict[str, Any],
    records: list[Any],
    receipt_ids: list[str],
    errors: list[str],
) -> None:
    workflow = queue.get("workflow_v0")
    if not isinstance(workflow, dict):
        errors.append("workflow_v0 must be an object")
        return
    if tuple(workflow.get("stage_order", ())) != WORKFLOW_STAGE_ORDER:
        errors.append("workflow_v0.stage_order must match Approval Queue v0 stages")
    if tuple(workflow.get("decision_controls", ())) != WORKFLOW_DECISION_CONTROLS:
        errors.append("workflow_v0.decision_controls must be approve/reject/revise")
    if workflow.get("approval_decision_records_allowed") is not True:
        errors.append("workflow_v0.approval_decision_records_allowed must be true")
    for field_name in WORKFLOW_FALSE_FIELDS:
        if workflow.get(field_name) is not False:
            errors.append(f"workflow_v0.{field_name} must be false")
    items = workflow.get("items")
    if not isinstance(items, list):
        errors.append("workflow_v0.items must be a list")
        return
    if workflow.get("requested_approval_count") != len(records):
        errors.append("workflow_v0.requested_approval_count must match records length")
    if workflow.get("receipt_count") != len(receipt_ids):
        errors.append("workflow_v0.receipt_count must match queue receipt count")
    if workflow.get("draft_action_count") != _workflow_draft_action_count(items):
        errors.append("workflow_v0.draft_action_count must match workflow item draft actions")
    pending_count = 0
    terminal_count = 0
    records_by_id = {
        str(record["approval_id"]): record
        for record in records
        if isinstance(record, dict) and isinstance(record.get("approval_id"), str)
    }
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(f"workflow_v0.items[{index}] must be an object")
            continue
        approval_id = str(item.get("approval_id", ""))
        record = records_by_id.get(approval_id)
        if record is None:
            errors.append(f"workflow_v0.items[{index}].approval_id must reference a queue record")
            continue
        _validate_workflow_item(index, item, record, errors)
        decision = _mapping(item.get("decision")).get("current_decision")
        if decision == "pending":
            pending_count += 1
        else:
            terminal_count += 1
    if workflow.get("pending_decision_count") != pending_count:
        errors.append("workflow_v0.pending_decision_count must match pending workflow decisions")
    if workflow.get("terminal_decision_count") != terminal_count:
        errors.append("workflow_v0.terminal_decision_count must match terminal workflow decisions")


def _validate_workflow_item(index: int, item: dict[str, Any], record: dict[str, Any], errors: list[str]) -> None:
    label = f"workflow_v0.items[{index}]"
    packet = _mapping(record.get("packet"))
    receipts = record.get("receipts") if isinstance(record.get("receipts"), list) else []
    latest_receipt = _mapping(receipts[-1]) if receipts else {}
    proposed_actions = packet.get("proposed_actions") if isinstance(packet.get("proposed_actions"), list) else []
    if item.get("request_id") != packet.get("request_id"):
        errors.append(f"{label}.request_id must match packet.request_id")
    if item.get("review_packet_ref") != record.get("review_packet_ref"):
        errors.append(f"{label}.review_packet_ref must match record review_packet_ref")
    if item.get("plan_id") != packet.get("plan_id"):
        errors.append(f"{label}.plan_id must match packet.plan_id")
    if item.get("draft_action_count") != len(proposed_actions):
        errors.append(f"{label}.draft_action_count must match packet proposed actions")
    if item.get("receipt_count") != len(receipts):
        errors.append(f"{label}.receipt_count must match record receipts")
    risk_class = _mapping(item.get("risk_class"))
    if risk_class.get("risk_level") != packet.get("risk_level"):
        errors.append(f"{label}.risk_class.risk_level must match packet.risk_level")
    if risk_class.get("explicit_approval_required") is not True:
        errors.append(f"{label}.risk_class.explicit_approval_required must be true")
    requested = _mapping(item.get("requested_approval"))
    if requested.get("approval_state") != packet.get("approval_state"):
        errors.append(f"{label}.requested_approval.approval_state must match packet.approval_state")
    if requested.get("approval_request_recorded") is not True:
        errors.append(f"{label}.requested_approval.approval_request_recorded must be true")
    decision = _mapping(item.get("decision"))
    packet_decision = _mapping(packet.get("decision_record"))
    if decision.get("current_decision") != packet_decision.get("decision"):
        errors.append(f"{label}.decision.current_decision must match packet decision")
    if tuple(decision.get("available_decisions", ())) != ("approved", "rejected", "revised"):
        errors.append(f"{label}.decision.available_decisions must be approved/rejected/revised")
    if decision.get("approval_is_execution") is not False:
        errors.append(f"{label}.decision.approval_is_execution must be false")
    if decision.get("execution_allowed") is not False:
        errors.append(f"{label}.decision.execution_allowed must be false")
    receipt = _mapping(item.get("receipt"))
    if receipt.get("latest_receipt_id") != latest_receipt.get("receipt_id"):
        errors.append(f"{label}.receipt.latest_receipt_id must match latest receipt")
    if receipt.get("latest_receipt_decision") != latest_receipt.get("decision"):
        errors.append(f"{label}.receipt.latest_receipt_decision must match latest receipt")
    if receipt.get("receipt_required") is not True:
        errors.append(f"{label}.receipt.receipt_required must be true")
    effect_boundary = _mapping(item.get("effect_boundary"))
    if effect_boundary.get("approval_decision_records_allowed") is not True:
        errors.append(f"{label}.effect_boundary.approval_decision_records_allowed must be true")
    for field_name in WORKFLOW_FALSE_FIELDS:
        if effect_boundary.get(field_name) is not False:
            errors.append(f"{label}.effect_boundary.{field_name} must be false")


def _validate_review_packet_ref(value: Any, errors: list[str], *, label: str) -> None:
    if not isinstance(value, dict):
        errors.append(f"{label} must be an object")
        return
    for field_name, expected in EXPECTED_REVIEW_REF_PATHS.items():
        if value.get(field_name) != expected:
            errors.append(f"{label}.{field_name} must be {expected}")
    source_path = _resolve_repo_path(str(value.get("source_ref", "")), errors, f"{label}.source_ref")
    schema_path = _resolve_repo_path(str(value.get("schema_ref", "")), errors, f"{label}.schema_ref")
    if schema_path is not None and not schema_path.exists():
        errors.append(f"{label}.schema_ref does not exist")
    if source_path is None:
        return
    if not source_path.exists():
        errors.append(f"{label}.source_ref does not exist")
        return
    observed_sha256 = canonical_source_sha256(source_path)
    if value.get("source_sha256") != observed_sha256:
        errors.append(f"{label}.source_sha256 does not match approval review packet")
    source_payload = _load_json_object(source_path, f"{label} source approval review packet", errors)
    if not source_payload:
        return
    for field_name in ("review_packet_id", "request_id", "plan_id", "review_state"):
        if value.get(field_name) != source_payload.get(field_name):
            errors.append(f"{label}.{field_name} must match approval review packet")
    if value.get("solver_outcome") != "SolvedVerified":
        errors.append(f"{label}.solver_outcome must be SolvedVerified")
    if value.get("preview_only") is not True:
        errors.append(f"{label}.preview_only must be true")
    if value.get("payload_digest_only") is not True:
        errors.append(f"{label}.payload_digest_only must be true")
    for field_name in REVIEW_REF_FALSE_FIELDS:
        if value.get(field_name) is not False:
            errors.append(f"{label}.{field_name} must be false")
    effect_boundary = source_payload.get("effect_boundary")
    if not isinstance(effect_boundary, dict):
        errors.append(f"{label} source effect_boundary must be an object")
    else:
        if effect_boundary.get("execution_allowed") is not False:
            errors.append(f"{label} source effect_boundary.execution_allowed must be false")
        if effect_boundary.get("approval_enqueued") is not False:
            errors.append(f"{label} source effect_boundary.approval_enqueued must be false")
    metadata = source_payload.get("metadata")
    if not isinstance(metadata, dict):
        errors.append(f"{label} source metadata must be an object")
    elif metadata.get("source_payloads_serialized") is not False:
        errors.append(f"{label} source metadata.source_payloads_serialized must be false")


def _resolve_repo_path(path_text: str, errors: list[str], label: str) -> Path | None:
    if not path_text:
        errors.append(f"{label} must be present")
        return None
    candidate = (REPO_ROOT / path_text).resolve()
    root = REPO_ROOT.resolve()
    if candidate != root and root not in candidate.parents:
        errors.append(f"{label} must stay under repository root")
        return None
    return candidate


def _workflow_draft_action_count(items: list[Any]) -> int:
    count = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        draft_actions = item.get("draft_actions")
        if isinstance(draft_actions, list):
            count += len(draft_actions)
    return count


def _mapping(payload: Any) -> dict[str, Any]:
    return dict(payload) if isinstance(payload, dict) else {}


def _scan_private_or_secret_payload(payload: Any, errors: list[str], *, path: str) -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            normalized_key = str(key).lower()
            if normalized_key in RAW_PRIVATE_FIELD_NAMES:
                errors.append(f"{path}.{key}: raw private connector payload field is forbidden")
            _scan_private_or_secret_payload(value, errors, path=f"{path}.{key}")
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            _scan_private_or_secret_payload(value, errors, path=f"{path}[{index}]")
    elif isinstance(payload, str):
        for pattern in SECRET_VALUE_PATTERNS:
            if pattern.search(payload):
                errors.append(f"{path}: secret-like value must not be serialized")
                break


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
    """Parse personal-assistant approval queue validation arguments."""
    parser = argparse.ArgumentParser(description="Validate personal-assistant approval queue read model.")
    parser.add_argument("--queue", default=str(DEFAULT_QUEUE))
    parser.add_argument("--schema", default=str(DEFAULT_QUEUE_SCHEMA))
    parser.add_argument("--approval-schema", default=str(DEFAULT_APPROVAL_SCHEMA))
    parser.add_argument("--receipt-schema", default=str(DEFAULT_RECEIPT_SCHEMA))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for personal-assistant approval queue validation."""
    args = parse_args(argv)
    result = validate_personal_assistant_approval_queue(
        queue_path=Path(args.queue),
        queue_schema_path=Path(args.schema),
        approval_schema_path=Path(args.approval_schema),
        receipt_schema_path=Path(args.receipt_schema),
    )
    if args.json:
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    elif result.valid:
        print(
            "personal-assistant approval queue ok "
            f"approvals={result.approval_count} receipts={result.receipt_count}"
        )
    else:
        for error in result.errors:
            print(f"error: {error}")
    return 0 if result.valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
