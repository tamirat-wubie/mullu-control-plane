#!/usr/bin/env python3
"""Validate Personal Assistant send-preparation receipts.

Purpose: reject malformed, raw-content-bearing, effect-bearing, unapproved, or
unready Personal Assistant send-preparation receipts before send execution.
Governance scope: approval decision carry-forward, queue precondition binding,
redacted preparation evidence, and external-effect denial.
Dependencies: personal_assistant_send_preparation_receipt schema.
Invariants:
  - Ready preparation requires approved decision carry-forward.
  - Send execution remains outside this receipt.
  - Raw fields, secret markers, bad hashes, and effect drift fail closed.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.produce_personal_assistant_send_preparation_receipt import (  # noqa: E402
    DEFAULT_OUTPUT,
    SHA256_HEX_PATTERN,
    SECRET_VALUE_PATTERNS,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "personal_assistant_send_preparation_receipt.schema.json"
DEFAULT_VALIDATION_OUTPUT = REPO_ROOT / ".change_assurance" / "personal_assistant_send_preparation_receipt_validation.json"
RECEIPT_ID_PATTERN = re.compile(r"^pa_send_preparation_receipt_[0-9a-f]{16}$")
RAW_FIELD_NAMES = {
    "raw_subject",
    "subject",
    "message_body",
    "body",
    "raw_sender",
    "sender_email",
    "recipient_email",
    "raw_recipient",
    "recipient",
    "query",
    "raw_decision_text",
    "decision_text",
    "raw_prepared_message",
    "prepared_message_body",
}
FALSE_EFFECT_FIELDS = (
    "external_send_authorized_by_decision",
    "send_execution_performed_by_producer",
    "draft_created_by_producer",
    "external_mailbox_write_performed",
    "external_message_sent",
    "connector_mutation_performed",
    "system_of_record_write_performed",
    "memory_write_performed",
    "raw_message_content_serialized",
    "raw_recipient_serialized",
    "raw_subject_serialized",
    "raw_body_serialized",
)


@dataclass(frozen=True, slots=True)
class PersonalAssistantSendPreparationReceiptValidation:
    """Validation result for one Personal Assistant send-preparation receipt."""

    valid: bool
    ready: bool
    receipt_path: str
    schema_path: str
    receipt_id: str
    status: str
    solver_outcome: str
    proof_state: str
    approval_decision_ready: bool
    decision: str
    receipt_decision: str
    send_preparation_state: str
    send_preparation_ready: bool
    blocked_until: tuple[str, ...]
    errors: tuple[str, ...]
    next_action: str

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-ready validation receipt."""
        payload = asdict(self)
        payload["blocked_until"] = list(self.blocked_until)
        payload["errors"] = list(self.errors)
        return payload


def validate_personal_assistant_send_preparation_receipt(
    *,
    receipt_path: Path = DEFAULT_OUTPUT,
    schema_path: Path = DEFAULT_SCHEMA,
    require_ready: bool = False,
) -> PersonalAssistantSendPreparationReceiptValidation:
    """Validate one Personal Assistant send-preparation receipt."""
    errors: list[str] = []
    try:
        schema = _load_schema(schema_path)
    except OSError:
        schema = {}
        errors.append("Personal Assistant send preparation receipt schema file missing")
    receipt = _load_json_object(receipt_path, "Personal Assistant send preparation receipt", errors)
    if schema and receipt:
        errors.extend(_validate_schema_instance(schema, receipt))
        _validate_semantics(receipt, errors)
        if require_ready and not _receipt_ready(receipt):
            errors.append("Personal Assistant send preparation receipt ready must be true")
    ready = not errors and _receipt_ready(receipt)
    return PersonalAssistantSendPreparationReceiptValidation(
        valid=not errors,
        ready=ready,
        receipt_path=_path_label(receipt_path),
        schema_path=_path_label(schema_path),
        receipt_id=str(receipt.get("receipt_id", "")),
        status=str(receipt.get("status", "")),
        solver_outcome=str(receipt.get("solver_outcome", "")),
        proof_state=str(receipt.get("proof_state", "")),
        approval_decision_ready=receipt.get("approval_decision_ready") is True,
        decision=str(receipt.get("decision", "")),
        receipt_decision=str(receipt.get("receipt_decision", "")),
        send_preparation_state=str(receipt.get("send_preparation_state", "")),
        send_preparation_ready=receipt.get("send_preparation_ready") is True,
        blocked_until=tuple(str(item) for item in receipt.get("blocked_until", ()))
        if isinstance(receipt.get("blocked_until", ()), list)
        else (),
        errors=tuple(errors),
        next_action=_next_action(receipt),
    )


def write_personal_assistant_send_preparation_receipt_validation(
    validation: PersonalAssistantSendPreparationReceiptValidation,
    output_path: Path,
) -> Path:
    """Write one Personal Assistant send-preparation validation receipt."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_semantics(receipt: dict[str, Any], errors: list[str]) -> None:
    serialized = json.dumps(receipt, sort_keys=True)
    for pattern in SECRET_VALUE_PATTERNS:
        if pattern.search(serialized):
            errors.append("receipt must not serialize secret-like value")
            break
    for field_name in RAW_FIELD_NAMES:
        if field_name in receipt:
            errors.append(f"receipt must not serialize raw field: {field_name}")
    if not RECEIPT_ID_PATTERN.fullmatch(str(receipt.get("receipt_id", ""))):
        errors.append("receipt_id must match Personal Assistant send preparation pattern")
    for field_name in FALSE_EFFECT_FIELDS:
        if receipt.get(field_name) is not False:
            errors.append(f"{field_name} must be false")
    if receipt.get("requires_separate_send_execution_receipt") is not True:
        errors.append("requires_separate_send_execution_receipt must be true")
    if receipt.get("no_secret_values_serialized") is not True:
        errors.append("no_secret_values_serialized must be true")
    if receipt.get("status") == "passed":
        _validate_ready_receipt(receipt, errors)
    elif receipt.get("status") == "blocked":
        _validate_blocked_receipt(receipt, errors)
    elif receipt.get("status") == "failed":
        _validate_failed_receipt(receipt, errors)
    else:
        errors.append("status must be blocked, failed, or passed")


def _validate_ready_receipt(receipt: dict[str, Any], errors: list[str]) -> None:
    if receipt.get("approval_decision_valid") is not True:
        errors.append("passed receipt requires valid approval decision evidence")
    if receipt.get("approval_decision_ready") is not True:
        errors.append("passed receipt requires ready approval decision evidence")
    if receipt.get("decision") != "approved":
        errors.append("passed receipt requires approved decision")
    if receipt.get("receipt_decision") != "deferred":
        errors.append("passed receipt requires deferred decision receipt")
    if not str(receipt.get("queue_precondition_sha256", "")).strip():
        errors.append("passed receipt requires queue_precondition_sha256")
    if receipt.get("source_queue_state") != "requested":
        errors.append("passed receipt requires requested source queue state")
    if not str(receipt.get("source_queue_receipt_id", "")).endswith("_request"):
        errors.append("passed receipt requires request queue receipt id")
    if receipt.get("source_review_packet_id") != "pa_approval_review_approval_review_packet_001":
        errors.append("passed receipt requires approval review packet id")
    if SHA256_HEX_PATTERN.fullmatch(str(receipt.get("source_review_packet_sha256", ""))) is None:
        errors.append("passed receipt requires approval review packet sha256")
    if receipt.get("solver_outcome") != "SolvedVerified":
        errors.append("passed receipt requires solver_outcome=SolvedVerified")
    if receipt.get("proof_state") != "Pass":
        errors.append("passed receipt requires proof_state=Pass")
    if receipt.get("send_preparation_state") != "prepared":
        errors.append("passed receipt requires send_preparation_state=prepared")
    if receipt.get("send_preparation_ready") is not True:
        errors.append("passed receipt requires send_preparation_ready=true")
    if receipt.get("send_preparation_authorized_by_decision") is not True:
        errors.append("passed receipt requires send_preparation_authorized_by_decision=true")
    for field_name in ("send_preparation_ref", "prepared_message_ref"):
        if not str(receipt.get(field_name, "")).strip():
            errors.append(f"passed receipt requires {field_name}")
    for field_name in ("recipient_hash", "prepared_message_hash"):
        if SHA256_HEX_PATTERN.fullmatch(str(receipt.get(field_name, ""))) is None:
            errors.append(f"passed receipt requires {field_name} sha256 hex")
    if not isinstance(receipt.get("evidence_refs"), list) or not receipt.get("evidence_refs"):
        errors.append("passed receipt requires evidence_refs")
    if receipt.get("blocked_until") != []:
        errors.append("passed receipt must not carry blockers")


def _validate_blocked_receipt(receipt: dict[str, Any], errors: list[str]) -> None:
    if receipt.get("solver_outcome") != "AwaitingEvidence":
        errors.append("blocked receipt requires solver_outcome=AwaitingEvidence")
    if receipt.get("proof_state") != "Unknown":
        errors.append("blocked receipt requires proof_state=Unknown")
    if receipt.get("send_preparation_ready") is not False:
        errors.append("blocked receipt must not be send-preparation ready")
    if not isinstance(receipt.get("blocked_until"), list) or not receipt.get("blocked_until"):
        errors.append("blocked receipt must list blockers")


def _validate_failed_receipt(receipt: dict[str, Any], errors: list[str]) -> None:
    if receipt.get("solver_outcome") != "GovernanceBlocked":
        errors.append("failed receipt requires solver_outcome=GovernanceBlocked")
    if receipt.get("proof_state") != "Fail":
        errors.append("failed receipt requires proof_state=Fail")
    if receipt.get("send_preparation_ready") is not False:
        errors.append("failed receipt must not be send-preparation ready")
    if not isinstance(receipt.get("blocked_until"), list) or not receipt.get("blocked_until"):
        errors.append("failed receipt must list blockers")


def _receipt_ready(receipt: dict[str, Any]) -> bool:
    return (
        receipt.get("status") == "passed"
        and receipt.get("solver_outcome") == "SolvedVerified"
        and receipt.get("proof_state") == "Pass"
        and receipt.get("approval_decision_valid") is True
        and receipt.get("approval_decision_ready") is True
        and receipt.get("decision") == "approved"
        and receipt.get("receipt_decision") == "deferred"
        and bool(str(receipt.get("queue_precondition_sha256", "")).strip())
        and receipt.get("source_queue_state") == "requested"
        and str(receipt.get("source_queue_receipt_id", "")).endswith("_request")
        and receipt.get("source_review_packet_id") == "pa_approval_review_approval_review_packet_001"
        and SHA256_HEX_PATTERN.fullmatch(str(receipt.get("source_review_packet_sha256", ""))) is not None
        and receipt.get("send_preparation_state") == "prepared"
        and receipt.get("send_preparation_ready") is True
        and bool(str(receipt.get("send_preparation_ref", "")).strip())
        and bool(str(receipt.get("prepared_message_ref", "")).strip())
        and SHA256_HEX_PATTERN.fullmatch(str(receipt.get("recipient_hash", ""))) is not None
        and SHA256_HEX_PATTERN.fullmatch(str(receipt.get("prepared_message_hash", ""))) is not None
        and receipt.get("send_preparation_authorized_by_decision") is True
        and receipt.get("requires_separate_send_execution_receipt") is True
        and all(receipt.get(field_name) is False for field_name in FALSE_EFFECT_FIELDS)
        and receipt.get("no_secret_values_serialized") is True
        and isinstance(receipt.get("evidence_refs"), list)
        and bool(receipt.get("evidence_refs"))
        and receipt.get("blocked_until") == []
    )


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    if not path.exists():
        errors.append(f"{label} file missing")
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError):
        errors.append(f"{label} JSON parse failed")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{label} JSON root must be an object")
        return {}
    return payload


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


def _next_action(receipt: dict[str, Any]) -> str:
    if _receipt_ready(receipt):
        return "execute separate Personal Assistant send-execution receipt only after final effect preflight"
    recovery_actions = receipt.get("recovery_actions", [])
    if isinstance(recovery_actions, list) and recovery_actions:
        return str(recovery_actions[0])
    return "regenerate Personal Assistant send preparation receipt"


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse Personal Assistant send-preparation validation arguments."""
    parser = argparse.ArgumentParser(description="Validate Personal Assistant send-preparation receipt.")
    parser.add_argument("--receipt", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_VALIDATION_OUTPUT))
    parser.add_argument("--require-ready", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for Personal Assistant send-preparation validation."""
    args = parse_args(argv)
    validation = validate_personal_assistant_send_preparation_receipt(
        receipt_path=Path(args.receipt),
        schema_path=Path(args.schema),
        require_ready=args.require_ready,
    )
    write_personal_assistant_send_preparation_receipt_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.valid:
        print(f"Personal Assistant send preparation receipt valid ready={validation.ready}")
    else:
        print(f"Personal Assistant send preparation receipt invalid errors={list(validation.errors)}")
    return 0 if validation.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
