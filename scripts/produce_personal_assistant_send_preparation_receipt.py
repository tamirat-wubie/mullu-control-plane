#!/usr/bin/env python3
"""Produce a Personal Assistant send-preparation receipt.

Purpose: bind approved Personal Assistant approval-decision evidence to redacted
send-preparation evidence without drafting, sending, mutating connectors, or
writing systems of record.
Governance scope: approval decision carry-forward, queue precondition binding,
redacted preparation evidence, no-effect enforcement, and recovery blockers.
Dependencies: personal_assistant_send_preparation_receipt schema and approval
decision validator.
Invariants:
  - Only valid approved decision evidence can prepare a send packet.
  - Approval decisions authorize preparation evidence only, not external send.
  - This producer never drafts, sends, mutates providers, writes memory, or
    writes systems of record.
  - Raw recipient, subject, body, message content, and secret-like values are
    rejected.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_personal_assistant_approval_decision import (  # noqa: E402
    DEFAULT_DECISION as DEFAULT_APPROVAL_DECISION,
    validate_personal_assistant_approval_decision,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "personal_assistant_send_preparation_receipt.schema.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "personal_assistant_send_preparation_receipt.json"
SHA256_HEX_PATTERN = re.compile(r"^[0-9a-f]{64}$")
SECRET_VALUE_PATTERNS = (
    re.compile(r"sk_live_[A-Za-z0-9]+"),
    re.compile(r"ghp_[A-Za-z0-9]+"),
    re.compile(r"github_pat_[A-Za-z0-9_]+"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]+"),
    re.compile(r"ya29\.[A-Za-z0-9._-]+"),
    re.compile(r"Bearer\s+[A-Za-z0-9._-]+", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"secret-(?:token|worker|key)-value", re.IGNORECASE),
    re.compile(r"client_secret", re.IGNORECASE),
)
VALIDATION_COMMANDS = (
    "python scripts/validate_personal_assistant_send_preparation_receipt.py --require-ready",
    "python scripts/validate_schemas.py --strict",
)


@dataclass(frozen=True, slots=True)
class PersonalAssistantSendPreparationReceipt:
    """Receipt for one no-effect Personal Assistant send-preparation packet."""

    receipt_id: str
    schema_version: int
    workflow_id: str
    source_approval_decision_ref: str
    source_decision_set_id: str
    source_decision_id: str
    approval_decision_valid: bool
    approval_decision_ready: bool
    approval_id: str
    request_id: str
    plan_id: str
    decision: str
    receipt_decision: str
    queue_precondition_sha256: str
    source_queue_state: str
    source_queue_receipt_id: str
    source_review_packet_id: str
    source_review_packet_sha256: str
    status: str
    solver_outcome: str
    proof_state: str
    prepared_at: str
    send_preparation_state: str
    send_preparation_ready: bool
    send_preparation_ref: str
    prepared_message_ref: str
    recipient_hash: str
    prepared_message_hash: str
    send_preparation_authorized_by_decision: bool
    external_send_authorized_by_decision: bool
    send_execution_performed_by_producer: bool
    requires_separate_send_execution_receipt: bool
    draft_created_by_producer: bool
    external_mailbox_write_performed: bool
    external_message_sent: bool
    connector_mutation_performed: bool
    system_of_record_write_performed: bool
    memory_write_performed: bool
    raw_message_content_serialized: bool
    raw_recipient_serialized: bool
    raw_subject_serialized: bool
    raw_body_serialized: bool
    no_secret_values_serialized: bool
    evidence_refs: tuple[str, ...]
    blocked_until: tuple[str, ...]
    recovery_actions: tuple[str, ...]
    validation_commands: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-ready receipt."""
        payload = asdict(self)
        payload["evidence_refs"] = list(self.evidence_refs)
        payload["blocked_until"] = list(self.blocked_until)
        payload["recovery_actions"] = list(self.recovery_actions)
        payload["validation_commands"] = list(self.validation_commands)
        return payload


def produce_personal_assistant_send_preparation_receipt(
    *,
    approval_decision_path: Path = DEFAULT_APPROVAL_DECISION,
    schema_path: Path = DEFAULT_SCHEMA,
    approval_id: str = "",
    prepared_at: str | None = None,
    send_preparation_ref: str = "",
    prepared_message_ref: str = "",
    recipient_hash: str = "",
    prepared_message_hash: str = "",
    evidence_refs: Sequence[str] = (),
) -> PersonalAssistantSendPreparationReceipt:
    """Produce a no-send Personal Assistant send-preparation receipt."""
    decision_validation = validate_personal_assistant_approval_decision(
        decision_path=approval_decision_path,
        validate_runtime=False,
    )
    decision_envelope = _load_json_object(approval_decision_path)
    decision_item = _select_decision_item(decision_envelope, approval_id=approval_id)
    clean_send_preparation_ref = _clean_text_ref(send_preparation_ref, "send_preparation_ref")
    clean_prepared_message_ref = _clean_text_ref(prepared_message_ref, "prepared_message_ref")
    clean_recipient_hash = _clean_hash(recipient_hash, "recipient_hash")
    clean_prepared_message_hash = _clean_hash(prepared_message_hash, "prepared_message_hash")
    safe_evidence_refs = tuple(_clean_evidence_refs((clean_send_preparation_ref, *evidence_refs)))
    approval_decision_ready = _decision_item_ready(decision_validation.valid, decision_item)
    status, solver_outcome, proof_state, blocked_until, recovery_actions = _derive_status(
        approval_decision_valid=decision_validation.valid,
        approval_decision_ready=approval_decision_ready,
        decision=str(decision_item.get("decision", "")),
        receipt_decision=str(_mapping(decision_item.get("receipt")).get("decision", "")),
        send_preparation_ref=clean_send_preparation_ref,
        prepared_message_ref=clean_prepared_message_ref,
        recipient_hash=clean_recipient_hash,
        prepared_message_hash=clean_prepared_message_hash,
        evidence_refs=safe_evidence_refs,
    )
    queue_ref = _mapping(decision_item.get("queue_precondition_ref"))
    receipt = PersonalAssistantSendPreparationReceipt(
        receipt_id=_receipt_id(
            approval_decision_path=approval_decision_path,
            source_decision_id=str(decision_item.get("decision_id", "")),
            queue_precondition_sha256=str(queue_ref.get("queue_precondition_sha256", "")),
            send_preparation_ref=clean_send_preparation_ref,
            prepared_message_ref=clean_prepared_message_ref,
            recipient_hash=clean_recipient_hash,
            prepared_message_hash=clean_prepared_message_hash,
            status=status,
        ),
        schema_version=1,
        workflow_id="personal_assistant.email_send_with_approval",
        source_approval_decision_ref=_artifact_ref(approval_decision_path),
        source_decision_set_id=str(decision_envelope.get("decision_set_id", "")) if decision_validation.valid else "",
        source_decision_id=str(decision_item.get("decision_id", "")) if approval_decision_ready else "",
        approval_decision_valid=decision_validation.valid,
        approval_decision_ready=approval_decision_ready,
        approval_id=str(decision_item.get("approval_id", "")) if approval_decision_ready else "",
        request_id=str(decision_item.get("request_id", "")) if approval_decision_ready else "",
        plan_id=str(decision_item.get("plan_id", "")) if approval_decision_ready else "",
        decision=str(decision_item.get("decision", "")) if approval_decision_ready else "",
        receipt_decision=str(_mapping(decision_item.get("receipt")).get("decision", "")) if approval_decision_ready else "",
        queue_precondition_sha256=str(queue_ref.get("queue_precondition_sha256", "")) if approval_decision_ready else "",
        source_queue_state=str(queue_ref.get("source_queue_state", "")) if approval_decision_ready else "",
        source_queue_receipt_id=str(queue_ref.get("source_receipt_id", "")) if approval_decision_ready else "",
        source_review_packet_id=str(queue_ref.get("source_review_packet_id", "")) if approval_decision_ready else "",
        source_review_packet_sha256=str(queue_ref.get("source_review_packet_sha256", "")) if approval_decision_ready else "",
        status=status,
        solver_outcome=solver_outcome,
        proof_state=proof_state,
        prepared_at=prepared_at or datetime.now(UTC).replace(microsecond=0).isoformat(),
        send_preparation_state=_send_preparation_state(status),
        send_preparation_ready=status == "passed",
        send_preparation_ref=clean_send_preparation_ref if status == "passed" else "",
        prepared_message_ref=clean_prepared_message_ref if status == "passed" else "",
        recipient_hash=clean_recipient_hash if status == "passed" else "",
        prepared_message_hash=clean_prepared_message_hash if status == "passed" else "",
        send_preparation_authorized_by_decision=status == "passed",
        external_send_authorized_by_decision=False,
        send_execution_performed_by_producer=False,
        requires_separate_send_execution_receipt=True,
        draft_created_by_producer=False,
        external_mailbox_write_performed=False,
        external_message_sent=False,
        connector_mutation_performed=False,
        system_of_record_write_performed=False,
        memory_write_performed=False,
        raw_message_content_serialized=False,
        raw_recipient_serialized=False,
        raw_subject_serialized=False,
        raw_body_serialized=False,
        no_secret_values_serialized=True,
        evidence_refs=safe_evidence_refs if status == "passed" else (),
        blocked_until=blocked_until,
        recovery_actions=recovery_actions,
        validation_commands=VALIDATION_COMMANDS,
    )
    _assert_no_secret_values(receipt.as_dict())
    _validate_receipt_against_schema(receipt, schema_path)
    return receipt


def write_personal_assistant_send_preparation_receipt(
    receipt: PersonalAssistantSendPreparationReceipt,
    output_path: Path,
) -> Path:
    """Write one Personal Assistant send-preparation receipt."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(receipt.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _derive_status(
    *,
    approval_decision_valid: bool,
    approval_decision_ready: bool,
    decision: str,
    receipt_decision: str,
    send_preparation_ref: str,
    prepared_message_ref: str,
    recipient_hash: str,
    prepared_message_hash: str,
    evidence_refs: Sequence[str],
) -> tuple[str, str, str, tuple[str, ...], tuple[str, ...]]:
    if not approval_decision_valid:
        return (
            "failed",
            "GovernanceBlocked",
            "Fail",
            ("approval_decision_evidence_invalid",),
            ("regenerate and validate Personal Assistant approval decision evidence",),
        )
    if not approval_decision_ready:
        return (
            "failed",
            "GovernanceBlocked",
            "Fail",
            ("approval_decision_not_approved",),
            ("record an approved Personal Assistant approval decision before preparing send evidence",),
        )
    if decision != "approved" or receipt_decision != "deferred":
        return (
            "failed",
            "GovernanceBlocked",
            "Fail",
            ("approval_decision_not_approved",),
            ("close the Personal Assistant request without send preparation",),
        )
    if (
        not send_preparation_ref
        or not prepared_message_ref
        or not recipient_hash
        or not prepared_message_hash
        or not evidence_refs
    ):
        return (
            "blocked",
            "AwaitingEvidence",
            "Unknown",
            ("send_preparation_evidence_missing",),
            ("bind redacted send-preparation, prepared-message, recipient-hash, and message-hash evidence",),
        )
    return ("passed", "SolvedVerified", "Pass", (), ())


def _decision_item_ready(decision_valid: bool, item: Mapping[str, Any]) -> bool:
    if not decision_valid or not item:
        return False
    return (
        item.get("decision") == "approved"
        and _mapping(item.get("receipt")).get("decision") == "deferred"
        and _mapping(item.get("queue_precondition_ref")).get("source_queue_state") == "requested"
        and _mapping(item.get("queue_precondition_ref")).get("decision_precondition_met") is True
    )


def _select_decision_item(envelope: Mapping[str, Any], *, approval_id: str) -> dict[str, Any]:
    items = envelope.get("decisions", ())
    if isinstance(items, (str, bytes)) or not isinstance(items, Sequence):
        return {}
    candidates = [dict(item) for item in items if isinstance(item, Mapping)]
    if approval_id:
        for item in candidates:
            if item.get("approval_id") == approval_id:
                return item
        return {}
    for item in candidates:
        if item.get("decision") == "approved":
            return item
    return {}


def _send_preparation_state(status: str) -> str:
    if status == "passed":
        return "prepared"
    if status == "failed":
        return "not_authorized"
    return "missing"


def _load_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError):
        return {}
    return dict(payload) if isinstance(payload, dict) else {}


def _clean_evidence_refs(values: Sequence[str]) -> tuple[str, ...]:
    cleaned: list[str] = []
    for value in values:
        ref = str(value).strip()
        if not ref:
            continue
        _assert_no_secret_values({"evidence_ref": ref})
        cleaned.append(ref)
    return tuple(dict.fromkeys(cleaned))


def _clean_text_ref(value: str, label: str) -> str:
    text = str(value).strip()
    if text:
        _assert_no_secret_values({label: text})
    return text


def _clean_hash(value: str, label: str) -> str:
    text = _clean_text_ref(value, label)
    if text and SHA256_HEX_PATTERN.fullmatch(text) is None:
        return ""
    return text


def _receipt_id(
    *,
    approval_decision_path: Path,
    source_decision_id: str,
    queue_precondition_sha256: str,
    send_preparation_ref: str,
    prepared_message_ref: str,
    recipient_hash: str,
    prepared_message_hash: str,
    status: str,
) -> str:
    material = {
        "decision_ref": _artifact_ref(approval_decision_path),
        "source_decision_id": source_decision_id,
        "queue_precondition_sha256": queue_precondition_sha256,
        "send_preparation_ref": send_preparation_ref,
        "prepared_message_ref": prepared_message_ref,
        "recipient_hash": recipient_hash,
        "prepared_message_hash": prepared_message_hash,
        "status": status,
    }
    digest = hashlib.sha256(json.dumps(material, sort_keys=True).encode("utf-8")).hexdigest()
    return f"pa_send_preparation_receipt_{digest[:16]}"


def _artifact_ref(path: Path) -> str:
    if not path.is_absolute():
        return path.as_posix().replace("\\", "/")
    resolved_path = path.resolve(strict=False)
    try:
        relative_label = os.path.relpath(str(resolved_path), str(REPO_ROOT)).replace(os.sep, "/")
    except ValueError:
        return path.name
    if relative_label == "." or relative_label.startswith("../") or relative_label.startswith("..\\"):
        return path.name
    return relative_label


def _assert_no_secret_values(payload: Mapping[str, Any]) -> None:
    serialized = json.dumps(payload, sort_keys=True)
    for pattern in SECRET_VALUE_PATTERNS:
        if pattern.search(serialized):
            raise ValueError("Personal Assistant send preparation receipt contains secret-like value")


def _validate_receipt_against_schema(
    receipt: PersonalAssistantSendPreparationReceipt,
    schema_path: Path,
) -> None:
    schema = _load_schema(schema_path)
    errors = _validate_schema_instance(schema, receipt.as_dict())
    if errors:
        raise RuntimeError(f"Personal Assistant send preparation receipt schema validation failed: {errors}")


def _mapping(payload: Any) -> dict[str, Any]:
    return dict(payload) if isinstance(payload, Mapping) else {}


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse Personal Assistant send-preparation receipt arguments."""
    parser = argparse.ArgumentParser(description="Produce Personal Assistant send-preparation receipt.")
    parser.add_argument("--approval-decision", default=str(DEFAULT_APPROVAL_DECISION))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--approval-id", default="")
    parser.add_argument("--prepared-at")
    parser.add_argument("--send-preparation-ref", default="")
    parser.add_argument("--prepared-message-ref", default="")
    parser.add_argument("--recipient-hash", default="")
    parser.add_argument("--prepared-message-hash", default="")
    parser.add_argument("--evidence-ref", action="append", default=[])
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for Personal Assistant send-preparation receipt production."""
    args = parse_args(argv)
    try:
        receipt = produce_personal_assistant_send_preparation_receipt(
            approval_decision_path=Path(args.approval_decision),
            schema_path=Path(args.schema),
            approval_id=str(args.approval_id),
            prepared_at=args.prepared_at,
            send_preparation_ref=str(args.send_preparation_ref),
            prepared_message_ref=str(args.prepared_message_ref),
            recipient_hash=str(args.recipient_hash),
            prepared_message_hash=str(args.prepared_message_hash),
            evidence_refs=tuple(str(ref) for ref in args.evidence_ref),
        )
        write_personal_assistant_send_preparation_receipt(receipt, Path(args.output))
    except (RuntimeError, ValueError) as exc:
        if args.json:
            print(json.dumps({"error": str(exc), "receipt_written": False}, indent=2, sort_keys=True))
        else:
            print(f"Personal Assistant send preparation receipt failed: {exc}")
        return 1
    if args.json:
        print(json.dumps(receipt.as_dict(), indent=2, sort_keys=True))
    else:
        print(f"Personal Assistant send preparation receipt written: {receipt.receipt_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
