#!/usr/bin/env python3
"""Produce a TeamOps shared inbox send preparation receipt.

Purpose: bind a ready approved TeamOps approval-decision receipt to redacted
send-preparation evidence without executing an external send.
Governance scope: TeamOps send-preparation admission, approval carry-forward,
redaction, no-draft/no-send/no-provider-mutation enforcement, and recovery.
Dependencies: schemas/team_ops_shared_inbox_send_preparation_receipt.schema.json
and scripts.validate_team_ops_shared_inbox_approval_decision_receipt.
Invariants:
  - Only ready approved approval-decision receipts can prepare a send packet.
  - Passed receipts retain the upstream provider-observation witness from the decision.
  - This producer prepares evidence only; it never executes a send.
  - This producer never drafts, writes a mailbox, or mutates a provider.
  - Raw recipient, subject, body, message content, and secret-shaped values are rejected.
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

from scripts.produce_team_ops_shared_inbox_approval_decision_receipt import (  # noqa: E402
    DEFAULT_OUTPUT as DEFAULT_APPROVAL_DECISION_RECEIPT,
)
from scripts.produce_team_ops_shared_inbox_approval_queue_receipt import APPROVAL_QUEUE_ID  # noqa: E402
from scripts.produce_team_ops_shared_inbox_operator_handoff import SECRET_VALUE_MARKERS  # noqa: E402
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402
from scripts.validate_team_ops_shared_inbox_approval_decision_receipt import (  # noqa: E402
    validate_team_ops_shared_inbox_approval_decision_receipt,
)


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "team_ops_shared_inbox_send_preparation_receipt.schema.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "team_ops_shared_inbox_send_preparation_receipt.json"
SHA256_HEX_PATTERN = re.compile(r"^[0-9a-f]{64}$")
VALIDATION_COMMANDS = (
    "python scripts/validate_team_ops_shared_inbox_send_preparation_receipt.py --require-ready",
    "python scripts/validate_schemas.py --strict",
)


@dataclass(frozen=True, slots=True)
class TeamOpsSharedInboxSendPreparationReceipt:
    """Receipt for one TeamOps send-preparation packet."""

    receipt_id: str
    schema_version: int
    workflow_id: str
    source_approval_decision_receipt_ref: str
    source_approval_decision_receipt_id: str
    approval_decision_receipt_valid: bool
    approval_decision_receipt_ready: bool
    provider_observation_receipt_ref: str
    provider_observation_receipt_id: str
    provider_observation_receipt_valid: bool
    status: str
    solver_outcome: str
    proof_state: str
    prepared_at: str
    approval_queue_id: str
    approval_request_ref: str
    approval_decision_ref: str
    approver_ref: str
    decision: str
    approval_state: str
    external_send_authorized_by_decision: bool
    send_preparation_state: str
    send_preparation_ready: bool
    send_preparation_ref: str
    prepared_message_ref: str
    thread_ref: str
    recipient_hash: str
    prepared_message_hash: str
    send_execution_performed_by_producer: bool
    requires_separate_send_execution_receipt: bool
    draft_created_by_producer: bool
    external_mailbox_write_performed: bool
    external_message_sent: bool
    provider_mutation_performed: bool
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


def produce_team_ops_shared_inbox_send_preparation_receipt(
    *,
    approval_decision_receipt_path: Path = DEFAULT_APPROVAL_DECISION_RECEIPT,
    schema_path: Path = DEFAULT_SCHEMA,
    prepared_at: str | None = None,
    send_preparation_ref: str = "",
    prepared_message_ref: str = "",
    thread_ref: str = "",
    recipient_hash: str = "",
    prepared_message_hash: str = "",
    evidence_refs: Sequence[str] = (),
) -> TeamOpsSharedInboxSendPreparationReceipt:
    """Produce a no-send TeamOps send-preparation receipt."""

    decision_validation = validate_team_ops_shared_inbox_approval_decision_receipt(
        receipt_path=approval_decision_receipt_path,
        require_ready=False,
    )
    decision_receipt = _load_json_object(approval_decision_receipt_path)
    clean_send_preparation_ref = _clean_text_ref(send_preparation_ref, "send_preparation_ref")
    clean_prepared_message_ref = _clean_text_ref(prepared_message_ref, "prepared_message_ref")
    clean_thread_ref = _clean_text_ref(thread_ref, "thread_ref")
    clean_recipient_hash = _clean_hash(recipient_hash, "recipient_hash")
    clean_prepared_message_hash = _clean_hash(prepared_message_hash, "prepared_message_hash")
    safe_evidence_refs = tuple(_clean_evidence_refs((clean_send_preparation_ref, *evidence_refs)))
    status, solver_outcome, proof_state, blocked_until, recovery_actions = _derive_status(
        decision_receipt_valid=decision_validation.valid,
        decision_receipt_ready=decision_validation.ready,
        decision=str(decision_receipt.get("decision", "")),
        approval_state=str(decision_receipt.get("approval_state", "")),
        external_send_authorized_by_decision=decision_receipt.get("external_send_authorized_by_decision") is True,
        send_preparation_ref=clean_send_preparation_ref,
        prepared_message_ref=clean_prepared_message_ref,
        thread_ref=clean_thread_ref,
        recipient_hash=clean_recipient_hash,
        prepared_message_hash=clean_prepared_message_hash,
        evidence_refs=safe_evidence_refs,
    )
    receipt = TeamOpsSharedInboxSendPreparationReceipt(
        receipt_id=_receipt_id(
            approval_decision_receipt_path=approval_decision_receipt_path,
            source_approval_decision_receipt_id=str(decision_receipt.get("receipt_id", "")),
            provider_observation_receipt_id=str(decision_receipt.get("provider_observation_receipt_id", "")),
            send_preparation_ref=clean_send_preparation_ref,
            prepared_message_ref=clean_prepared_message_ref,
            recipient_hash=clean_recipient_hash,
            prepared_message_hash=clean_prepared_message_hash,
            status=status,
        ),
        schema_version=1,
        workflow_id="team_ops.shared_inbox_triage",
        source_approval_decision_receipt_ref=_artifact_ref(approval_decision_receipt_path),
        source_approval_decision_receipt_id=str(decision_receipt.get("receipt_id", "")),
        approval_decision_receipt_valid=decision_validation.valid,
        approval_decision_receipt_ready=decision_validation.ready,
        provider_observation_receipt_ref=str(decision_receipt.get("provider_observation_receipt_ref", "")),
        provider_observation_receipt_id=str(decision_receipt.get("provider_observation_receipt_id", "")),
        provider_observation_receipt_valid=decision_receipt.get("provider_observation_receipt_valid") is True,
        status=status,
        solver_outcome=solver_outcome,
        proof_state=proof_state,
        prepared_at=prepared_at or datetime.now(UTC).replace(microsecond=0).isoformat(),
        approval_queue_id=str(decision_receipt.get("approval_queue_id", "")) if decision_validation.ready else "",
        approval_request_ref=str(decision_receipt.get("approval_request_ref", "")) if decision_validation.ready else "",
        approval_decision_ref=str(decision_receipt.get("decision_evidence_ref", "")) if decision_validation.ready else "",
        approver_ref=str(decision_receipt.get("approver_ref", "")) if decision_validation.ready else "",
        decision=str(decision_receipt.get("decision", "")) if decision_validation.ready else "",
        approval_state=str(decision_receipt.get("approval_state", "")) if decision_validation.ready else "missing",
        external_send_authorized_by_decision=decision_validation.ready
        and decision_receipt.get("external_send_authorized_by_decision") is True,
        send_preparation_state=_send_preparation_state(status),
        send_preparation_ready=status == "passed",
        send_preparation_ref=clean_send_preparation_ref if status == "passed" else "",
        prepared_message_ref=clean_prepared_message_ref if status == "passed" else "",
        thread_ref=clean_thread_ref if status == "passed" else "",
        recipient_hash=clean_recipient_hash if status == "passed" else "",
        prepared_message_hash=clean_prepared_message_hash if status == "passed" else "",
        send_execution_performed_by_producer=False,
        requires_separate_send_execution_receipt=True,
        draft_created_by_producer=False,
        external_mailbox_write_performed=False,
        external_message_sent=False,
        provider_mutation_performed=False,
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
    _assert_redacted(receipt.as_dict())
    _validate_receipt_against_schema(receipt, schema_path)
    return receipt


def write_team_ops_shared_inbox_send_preparation_receipt(
    receipt: TeamOpsSharedInboxSendPreparationReceipt,
    output_path: Path,
) -> Path:
    """Write one TeamOps send-preparation receipt."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(receipt.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _derive_status(
    *,
    decision_receipt_valid: bool,
    decision_receipt_ready: bool,
    decision: str,
    approval_state: str,
    external_send_authorized_by_decision: bool,
    send_preparation_ref: str,
    prepared_message_ref: str,
    thread_ref: str,
    recipient_hash: str,
    prepared_message_hash: str,
    evidence_refs: Sequence[str],
) -> tuple[str, str, str, tuple[str, ...], tuple[str, ...]]:
    if not decision_receipt_valid:
        return (
            "failed",
            "GovernanceBlocked",
            "Fail",
            ("approval_decision_receipt_invalid",),
            ("regenerate and validate the TeamOps approval decision receipt",),
        )
    if not decision_receipt_ready:
        return (
            "blocked",
            "AwaitingEvidence",
            "Unknown",
            ("approval_decision_receipt_not_ready",),
            ("record an approved TeamOps approval decision before preparing send evidence",),
        )
    if decision != "approved" or approval_state != "approved" or not external_send_authorized_by_decision:
        return (
            "failed",
            "GovernanceBlocked",
            "Fail",
            ("approval_decision_not_approved",),
            ("close the TeamOps shared inbox request without external send",),
        )
    if (
        not send_preparation_ref
        or not prepared_message_ref
        or not thread_ref
        or not recipient_hash
        or not prepared_message_hash
        or not evidence_refs
    ):
        return (
            "blocked",
            "AwaitingEvidence",
            "Unknown",
            ("send_preparation_evidence_missing",),
            ("bind redacted send-preparation, prepared-message, thread, recipient-hash, and message-hash evidence",),
        )
    return ("passed", "SolvedVerified", "Pass", (), ())


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
    if not isinstance(payload, dict):
        return {}
    return payload


def _clean_evidence_refs(values: Sequence[str]) -> tuple[str, ...]:
    cleaned: list[str] = []
    for value in values:
        ref = str(value).strip()
        if not ref:
            continue
        _assert_redacted({"evidence_ref": ref})
        cleaned.append(ref)
    return tuple(dict.fromkeys(cleaned))


def _clean_text_ref(value: str, label: str) -> str:
    text = str(value).strip()
    if text:
        _assert_redacted({label: text})
    return text


def _clean_hash(value: str, label: str) -> str:
    text = _clean_text_ref(value, label)
    if text and SHA256_HEX_PATTERN.fullmatch(text) is None:
        return ""
    return text


def _receipt_id(
    *,
    approval_decision_receipt_path: Path,
    source_approval_decision_receipt_id: str,
    provider_observation_receipt_id: str,
    send_preparation_ref: str,
    prepared_message_ref: str,
    recipient_hash: str,
    prepared_message_hash: str,
    status: str,
) -> str:
    material = {
        "decision_ref": _artifact_ref(approval_decision_receipt_path),
        "source_approval_decision_receipt_id": source_approval_decision_receipt_id,
        "provider_observation_receipt_id": provider_observation_receipt_id,
        "send_preparation_ref": send_preparation_ref,
        "prepared_message_ref": prepared_message_ref,
        "recipient_hash": recipient_hash,
        "prepared_message_hash": prepared_message_hash,
        "status": status,
    }
    digest = hashlib.sha256(json.dumps(material, sort_keys=True).encode("utf-8")).hexdigest()
    return f"teamops-shared-inbox-send-preparation-receipt-{digest[:16]}"


def _artifact_ref(path: Path) -> str:
    label = path.as_posix().replace("\\", "/")
    if not path.is_absolute():
        return label
    resolved_path = path.resolve(strict=False)
    try:
        relative_label = os.path.relpath(str(resolved_path), str(REPO_ROOT)).replace(os.sep, "/")
    except ValueError:
        return path.name
    if relative_label == "." or relative_label.startswith("../") or relative_label.startswith("..\\"):
        return path.name
    return relative_label


def _assert_redacted(payload: Mapping[str, Any]) -> None:
    serialized = json.dumps(payload, sort_keys=True)
    for marker in SECRET_VALUE_MARKERS:
        if marker.lower() in serialized.lower():
            raise ValueError(f"TeamOps send preparation receipt contains secret marker: {marker}")


def _validate_receipt_against_schema(
    receipt: TeamOpsSharedInboxSendPreparationReceipt,
    schema_path: Path,
) -> None:
    schema = _load_schema(schema_path)
    errors = _validate_schema_instance(schema, receipt.as_dict())
    if errors:
        raise RuntimeError(f"TeamOps send preparation receipt schema validation failed: {errors}")


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse TeamOps send-preparation receipt arguments."""

    parser = argparse.ArgumentParser(description="Produce TeamOps shared inbox send-preparation receipt.")
    parser.add_argument("--approval-decision-receipt", default=str(DEFAULT_APPROVAL_DECISION_RECEIPT))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--prepared-at")
    parser.add_argument("--send-preparation-ref", default="")
    parser.add_argument("--prepared-message-ref", default="")
    parser.add_argument("--thread-ref", default="")
    parser.add_argument("--recipient-hash", default="")
    parser.add_argument("--prepared-message-hash", default="")
    parser.add_argument("--evidence-ref", action="append", default=[])
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for TeamOps send-preparation receipt production."""

    args = parse_args(argv)
    try:
        receipt = produce_team_ops_shared_inbox_send_preparation_receipt(
            approval_decision_receipt_path=Path(args.approval_decision_receipt),
            schema_path=Path(args.schema),
            prepared_at=args.prepared_at,
            send_preparation_ref=str(args.send_preparation_ref),
            prepared_message_ref=str(args.prepared_message_ref),
            thread_ref=str(args.thread_ref),
            recipient_hash=str(args.recipient_hash),
            prepared_message_hash=str(args.prepared_message_hash),
            evidence_refs=tuple(str(ref) for ref in args.evidence_ref),
        )
        write_team_ops_shared_inbox_send_preparation_receipt(receipt, Path(args.output))
    except (RuntimeError, ValueError) as exc:
        if args.json:
            print(
                json.dumps(
                    {
                        "error": str(exc),
                        "receipt_written": False,
                        "solver_outcome": "GovernanceBlocked",
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
        else:
            print(f"TeamOps shared inbox send preparation receipt failed: {exc}")
        return 1
    if args.json:
        print(json.dumps(receipt.as_dict(), indent=2, sort_keys=True))
    else:
        print(f"TeamOps shared inbox send preparation receipt written: {receipt.receipt_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
