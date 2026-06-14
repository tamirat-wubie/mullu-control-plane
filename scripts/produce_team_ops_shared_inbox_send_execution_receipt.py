#!/usr/bin/env python3
"""Produce a TeamOps shared inbox send execution receipt.

Purpose: bind ready TeamOps send-preparation evidence to redacted observed
provider dispatch evidence without performing the provider mutation locally.
Governance scope: TeamOps send-execution evidence admission, approval and
preparation carry-forward, redaction, no-local-provider-call enforcement, and
recovery.
Dependencies: schemas/team_ops_shared_inbox_send_execution_receipt.schema.json
and scripts.validate_team_ops_shared_inbox_send_preparation_receipt.
Invariants:
  - Only ready send-preparation receipts can admit provider send evidence.
  - This producer records observed execution evidence only; it never calls a provider.
  - Raw recipient, subject, body, message content, provider response, and
    secret-shaped values are rejected.
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

from scripts.produce_team_ops_shared_inbox_approval_queue_receipt import APPROVAL_QUEUE_ID  # noqa: E402
from scripts.produce_team_ops_shared_inbox_operator_handoff import SECRET_VALUE_MARKERS  # noqa: E402
from scripts.produce_team_ops_shared_inbox_send_preparation_receipt import (  # noqa: E402
    DEFAULT_OUTPUT as DEFAULT_SEND_PREPARATION_RECEIPT,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402
from scripts.validate_team_ops_shared_inbox_send_preparation_receipt import (  # noqa: E402
    validate_team_ops_shared_inbox_send_preparation_receipt,
)


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "team_ops_shared_inbox_send_execution_receipt.schema.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "team_ops_shared_inbox_send_execution_receipt.json"
SHA256_HEX_PATTERN = re.compile(r"^[0-9a-f]{64}$")
VALIDATION_COMMANDS = (
    "python scripts/validate_team_ops_shared_inbox_send_execution_receipt.py --require-ready",
    "python scripts/validate_schemas.py --strict",
)


@dataclass(frozen=True, slots=True)
class TeamOpsSharedInboxSendExecutionReceipt:
    """Receipt for one observed TeamOps send-execution event."""

    receipt_id: str
    schema_version: int
    workflow_id: str
    source_send_preparation_receipt_ref: str
    source_send_preparation_receipt_id: str
    send_preparation_receipt_valid: bool
    send_preparation_receipt_ready: bool
    status: str
    solver_outcome: str
    proof_state: str
    executed_at: str
    approval_queue_id: str
    approval_request_ref: str
    approval_decision_ref: str
    approver_ref: str
    decision: str
    approval_state: str
    external_send_authorized_by_decision: bool
    send_preparation_ref: str
    prepared_message_ref: str
    thread_ref: str
    recipient_hash: str
    prepared_message_hash: str
    send_execution_state: str
    send_execution_ready: bool
    send_execution_ref: str
    dispatch_receipt_ref: str
    provider_message_ref: str
    dispatch_receipt_hash: str
    provider_message_hash: str
    send_execution_observed: bool
    send_execution_performed_by_producer: bool
    external_message_sent: bool
    external_message_sent_by_producer: bool
    external_mailbox_write_performed_by_producer: bool
    provider_mutation_performed_by_producer: bool
    provider_call_performed_by_producer: bool
    draft_created_by_producer: bool
    raw_message_content_serialized: bool
    raw_recipient_serialized: bool
    raw_subject_serialized: bool
    raw_body_serialized: bool
    no_secret_values_serialized: bool
    requires_sent_message_observation_receipt: bool
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


def produce_team_ops_shared_inbox_send_execution_receipt(
    *,
    send_preparation_receipt_path: Path = DEFAULT_SEND_PREPARATION_RECEIPT,
    schema_path: Path = DEFAULT_SCHEMA,
    executed_at: str | None = None,
    send_execution_ref: str = "",
    dispatch_receipt_ref: str = "",
    provider_message_ref: str = "",
    dispatch_receipt_hash: str = "",
    provider_message_hash: str = "",
    evidence_refs: Sequence[str] = (),
) -> TeamOpsSharedInboxSendExecutionReceipt:
    """Produce a TeamOps send-execution evidence receipt."""

    preparation_validation = validate_team_ops_shared_inbox_send_preparation_receipt(
        receipt_path=send_preparation_receipt_path,
        require_ready=False,
    )
    preparation_receipt = _load_json_object(send_preparation_receipt_path)
    clean_send_execution_ref = _clean_text_ref(send_execution_ref, "send_execution_ref")
    clean_dispatch_receipt_ref = _clean_text_ref(dispatch_receipt_ref, "dispatch_receipt_ref")
    clean_provider_message_ref = _clean_text_ref(provider_message_ref, "provider_message_ref")
    clean_dispatch_receipt_hash = _clean_hash(dispatch_receipt_hash, "dispatch_receipt_hash")
    clean_provider_message_hash = _clean_hash(provider_message_hash, "provider_message_hash")
    safe_evidence_refs = tuple(
        _clean_evidence_refs(
            (
                clean_send_execution_ref,
                clean_dispatch_receipt_ref,
                clean_provider_message_ref,
                *evidence_refs,
            )
        )
    )
    status, solver_outcome, proof_state, blocked_until, recovery_actions = _derive_status(
        send_preparation_receipt_valid=preparation_validation.valid,
        send_preparation_receipt_ready=preparation_validation.ready,
        preparation_receipt=preparation_receipt,
        send_execution_ref=clean_send_execution_ref,
        dispatch_receipt_ref=clean_dispatch_receipt_ref,
        provider_message_ref=clean_provider_message_ref,
        dispatch_receipt_hash=clean_dispatch_receipt_hash,
        provider_message_hash=clean_provider_message_hash,
        evidence_refs=safe_evidence_refs,
    )
    source_ready = preparation_validation.ready
    receipt = TeamOpsSharedInboxSendExecutionReceipt(
        receipt_id=_receipt_id(
            send_preparation_receipt_path=send_preparation_receipt_path,
            source_send_preparation_receipt_id=str(preparation_receipt.get("receipt_id", "")),
            send_execution_ref=clean_send_execution_ref,
            dispatch_receipt_ref=clean_dispatch_receipt_ref,
            provider_message_ref=clean_provider_message_ref,
            provider_message_hash=clean_provider_message_hash,
            status=status,
        ),
        schema_version=1,
        workflow_id="team_ops.shared_inbox_triage",
        source_send_preparation_receipt_ref=_artifact_ref(send_preparation_receipt_path),
        source_send_preparation_receipt_id=str(preparation_receipt.get("receipt_id", "")),
        send_preparation_receipt_valid=preparation_validation.valid,
        send_preparation_receipt_ready=preparation_validation.ready,
        status=status,
        solver_outcome=solver_outcome,
        proof_state=proof_state,
        executed_at=executed_at or datetime.now(UTC).replace(microsecond=0).isoformat(),
        approval_queue_id=str(preparation_receipt.get("approval_queue_id", "")) if source_ready else "",
        approval_request_ref=str(preparation_receipt.get("approval_request_ref", "")) if source_ready else "",
        approval_decision_ref=str(preparation_receipt.get("approval_decision_ref", "")) if source_ready else "",
        approver_ref=str(preparation_receipt.get("approver_ref", "")) if source_ready else "",
        decision=str(preparation_receipt.get("decision", "")) if source_ready else "",
        approval_state=str(preparation_receipt.get("approval_state", "")) if source_ready else "missing",
        external_send_authorized_by_decision=source_ready
        and preparation_receipt.get("external_send_authorized_by_decision") is True,
        send_preparation_ref=str(preparation_receipt.get("send_preparation_ref", "")) if source_ready else "",
        prepared_message_ref=str(preparation_receipt.get("prepared_message_ref", "")) if source_ready else "",
        thread_ref=str(preparation_receipt.get("thread_ref", "")) if source_ready else "",
        recipient_hash=str(preparation_receipt.get("recipient_hash", "")) if source_ready else "",
        prepared_message_hash=str(preparation_receipt.get("prepared_message_hash", "")) if source_ready else "",
        send_execution_state=_send_execution_state(status),
        send_execution_ready=status == "passed",
        send_execution_ref=clean_send_execution_ref if status == "passed" else "",
        dispatch_receipt_ref=clean_dispatch_receipt_ref if status == "passed" else "",
        provider_message_ref=clean_provider_message_ref if status == "passed" else "",
        dispatch_receipt_hash=clean_dispatch_receipt_hash if status == "passed" else "",
        provider_message_hash=clean_provider_message_hash if status == "passed" else "",
        send_execution_observed=status == "passed",
        send_execution_performed_by_producer=False,
        external_message_sent=status == "passed",
        external_message_sent_by_producer=False,
        external_mailbox_write_performed_by_producer=False,
        provider_mutation_performed_by_producer=False,
        provider_call_performed_by_producer=False,
        draft_created_by_producer=False,
        raw_message_content_serialized=False,
        raw_recipient_serialized=False,
        raw_subject_serialized=False,
        raw_body_serialized=False,
        no_secret_values_serialized=True,
        requires_sent_message_observation_receipt=True,
        evidence_refs=safe_evidence_refs if status == "passed" else (),
        blocked_until=blocked_until,
        recovery_actions=recovery_actions,
        validation_commands=VALIDATION_COMMANDS,
    )
    _assert_redacted(receipt.as_dict())
    _validate_receipt_against_schema(receipt, schema_path)
    return receipt


def write_team_ops_shared_inbox_send_execution_receipt(
    receipt: TeamOpsSharedInboxSendExecutionReceipt,
    output_path: Path,
) -> Path:
    """Write one TeamOps send-execution receipt."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(receipt.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _derive_status(
    *,
    send_preparation_receipt_valid: bool,
    send_preparation_receipt_ready: bool,
    preparation_receipt: Mapping[str, Any],
    send_execution_ref: str,
    dispatch_receipt_ref: str,
    provider_message_ref: str,
    dispatch_receipt_hash: str,
    provider_message_hash: str,
    evidence_refs: Sequence[str],
) -> tuple[str, str, str, tuple[str, ...], tuple[str, ...]]:
    if not send_preparation_receipt_valid:
        return (
            "failed",
            "GovernanceBlocked",
            "Fail",
            ("send_preparation_receipt_invalid",),
            ("regenerate and validate the TeamOps send-preparation receipt",),
        )
    if not send_preparation_receipt_ready:
        return (
            "blocked",
            "AwaitingEvidence",
            "Unknown",
            ("send_preparation_receipt_not_ready",),
            ("record ready TeamOps send-preparation evidence before admitting send execution evidence",),
        )
    if (
        preparation_receipt.get("decision") != "approved"
        or preparation_receipt.get("approval_state") != "approved"
        or preparation_receipt.get("external_send_authorized_by_decision") is not True
        or preparation_receipt.get("send_preparation_state") != "prepared"
        or preparation_receipt.get("send_preparation_ready") is not True
    ):
        return (
            "failed",
            "GovernanceBlocked",
            "Fail",
            ("send_preparation_not_ready",),
            ("close or regenerate the TeamOps send-preparation receipt before external send execution",),
        )
    if (
        not send_execution_ref
        or not dispatch_receipt_ref
        or not provider_message_ref
        or not dispatch_receipt_hash
        or not provider_message_hash
        or not evidence_refs
    ):
        return (
            "blocked",
            "AwaitingEvidence",
            "Unknown",
            ("send_execution_evidence_missing",),
            ("bind redacted send-execution, dispatch receipt, provider message, and hash evidence",),
        )
    return ("passed", "SolvedVerified", "Pass", (), ())


def _send_execution_state(status: str) -> str:
    if status == "passed":
        return "sent"
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
    send_preparation_receipt_path: Path,
    source_send_preparation_receipt_id: str,
    send_execution_ref: str,
    dispatch_receipt_ref: str,
    provider_message_ref: str,
    provider_message_hash: str,
    status: str,
) -> str:
    material = {
        "source_ref": _artifact_ref(send_preparation_receipt_path),
        "source_send_preparation_receipt_id": source_send_preparation_receipt_id,
        "send_execution_ref": send_execution_ref,
        "dispatch_receipt_ref": dispatch_receipt_ref,
        "provider_message_ref": provider_message_ref,
        "provider_message_hash": provider_message_hash,
        "status": status,
    }
    digest = hashlib.sha256(json.dumps(material, sort_keys=True).encode("utf-8")).hexdigest()
    return f"teamops-shared-inbox-send-execution-receipt-{digest[:16]}"


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
            raise ValueError(f"TeamOps send execution receipt contains secret marker: {marker}")


def _validate_receipt_against_schema(
    receipt: TeamOpsSharedInboxSendExecutionReceipt,
    schema_path: Path,
) -> None:
    schema = _load_schema(schema_path)
    errors = _validate_schema_instance(schema, receipt.as_dict())
    if errors:
        raise RuntimeError(f"TeamOps send execution receipt schema validation failed: {errors}")


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse TeamOps send-execution receipt arguments."""

    parser = argparse.ArgumentParser(description="Produce TeamOps shared inbox send-execution receipt.")
    parser.add_argument("--send-preparation-receipt", default=str(DEFAULT_SEND_PREPARATION_RECEIPT))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--executed-at")
    parser.add_argument("--send-execution-ref", default="")
    parser.add_argument("--dispatch-receipt-ref", default="")
    parser.add_argument("--provider-message-ref", default="")
    parser.add_argument("--dispatch-receipt-hash", default="")
    parser.add_argument("--provider-message-hash", default="")
    parser.add_argument("--evidence-ref", action="append", default=[])
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for TeamOps send-execution receipt production."""

    args = parse_args(argv)
    try:
        receipt = produce_team_ops_shared_inbox_send_execution_receipt(
            send_preparation_receipt_path=Path(args.send_preparation_receipt),
            schema_path=Path(args.schema),
            executed_at=args.executed_at,
            send_execution_ref=str(args.send_execution_ref),
            dispatch_receipt_ref=str(args.dispatch_receipt_ref),
            provider_message_ref=str(args.provider_message_ref),
            dispatch_receipt_hash=str(args.dispatch_receipt_hash),
            provider_message_hash=str(args.provider_message_hash),
            evidence_refs=tuple(str(ref) for ref in args.evidence_ref),
        )
        write_team_ops_shared_inbox_send_execution_receipt(receipt, Path(args.output))
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
            print(f"TeamOps shared inbox send execution receipt failed: {exc}")
        return 1
    if args.json:
        print(json.dumps(receipt.as_dict(), indent=2, sort_keys=True))
    else:
        print(f"TeamOps shared inbox send execution receipt written: {receipt.receipt_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
