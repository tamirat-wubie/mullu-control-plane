#!/usr/bin/env python3
"""Produce a TeamOps shared inbox observation routing receipt.

Purpose: bind a ready TeamOps shared inbox live-probe receipt to a redacted
classification, owner assignment, and approval obligation plan.
Governance scope: TeamOps shared inbox routing, no-send workflow composition,
redaction, assignment obligation, and approval-before-external-send separation.
Dependencies: schemas/team_ops_shared_inbox_observation_routing_receipt.schema.json
and scripts.validate_team_ops_shared_inbox_live_probe_receipt.
Invariants:
  - This producer never calls mailbox providers or connector workers.
  - This producer never creates drafts, sends messages, or mutates provider state.
  - Ready routing receipts require a ready live-probe receipt and redacted
    observation hashes.
  - Raw subject, sender, recipient, message body, and query text are not
    accepted as serialized fields.
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

from scripts.produce_team_ops_shared_inbox_operator_handoff import SECRET_VALUE_MARKERS  # noqa: E402
from scripts.produce_team_ops_shared_inbox_live_probe_receipt import (  # noqa: E402
    DEFAULT_OUTPUT as DEFAULT_LIVE_PROBE_RECEIPT,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402
from scripts.validate_team_ops_shared_inbox_live_probe_receipt import (  # noqa: E402
    validate_team_ops_shared_inbox_live_probe_receipt,
)


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "team_ops_shared_inbox_observation_routing_receipt.schema.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "team_ops_shared_inbox_observation_routing_receipt.json"
SHA256_HEX_PATTERN = re.compile(r"^[0-9a-f]{64}$")
CLASSIFICATIONS = {
    "support_request",
    "sales_request",
    "finance_request",
    "security_request",
    "internal_ops",
    "unknown",
}
OWNER_QUEUES = {"support", "sales", "finance", "security", "operations", "triage"}
PRIORITIES = {"low", "normal", "high", "urgent"}
VALIDATION_COMMANDS = (
    "python scripts/validate_team_ops_shared_inbox_observation_routing_receipt.py --require-ready",
    "python scripts/validate_schemas.py --strict",
)


@dataclass(frozen=True, slots=True)
class TeamOpsSharedInboxObservationRoutingReceipt:
    """Receipt for one no-send TeamOps shared inbox routing decision."""

    receipt_id: str
    schema_version: int
    workflow_id: str
    source_live_probe_receipt_ref: str
    source_live_probe_receipt_id: str
    live_probe_receipt_valid: bool
    live_probe_receipt_ready: bool
    status: str
    solver_outcome: str
    proof_state: str
    routed_at: str
    observation_digest: str
    message_digest: str
    thread_digest: str
    subject_hash: str
    sender_hash: str
    recipient_hashes: tuple[str, ...]
    classification: str
    priority: str
    owner_queue: str
    assignment_required: bool
    assigned_owner_ref: str
    draft_response_required: bool
    approval_required_before_external_send: bool
    external_send_allowed: bool
    draft_created_by_producer: bool
    external_mailbox_write_performed: bool
    external_message_sent: bool
    provider_mutation_performed: bool
    raw_message_content_serialized: bool
    no_secret_values_serialized: bool
    evidence_refs: tuple[str, ...]
    blocked_until: tuple[str, ...]
    recovery_actions: tuple[str, ...]
    validation_commands: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-ready receipt."""

        payload = asdict(self)
        payload["recipient_hashes"] = list(self.recipient_hashes)
        payload["evidence_refs"] = list(self.evidence_refs)
        payload["blocked_until"] = list(self.blocked_until)
        payload["recovery_actions"] = list(self.recovery_actions)
        payload["validation_commands"] = list(self.validation_commands)
        return payload


def produce_team_ops_shared_inbox_observation_routing_receipt(
    *,
    live_probe_receipt_path: Path = DEFAULT_LIVE_PROBE_RECEIPT,
    schema_path: Path = DEFAULT_SCHEMA,
    routed_at: str | None = None,
    observation_digest: str = "",
    message_digest: str = "",
    thread_digest: str = "",
    subject_hash: str = "",
    sender_hash: str = "",
    recipient_hashes: Sequence[str] = (),
    classification: str = "unknown",
    priority: str = "normal",
    owner_queue: str = "triage",
    assignment_required: bool = True,
    assigned_owner_ref: str = "",
    draft_response_required: bool = True,
    evidence_refs: Sequence[str] = (),
) -> TeamOpsSharedInboxObservationRoutingReceipt:
    """Produce a no-send TeamOps shared inbox observation routing receipt."""

    live_validation = validate_team_ops_shared_inbox_live_probe_receipt(
        receipt_path=live_probe_receipt_path,
        require_ready=False,
    )
    source_receipt = _load_json_object(live_probe_receipt_path)
    safe_recipient_hashes = tuple(_clean_hashes(recipient_hashes, "recipient_hash"))
    safe_evidence_refs = tuple(_clean_evidence_refs(evidence_refs))
    normalized_classification = classification if classification in CLASSIFICATIONS else "unknown"
    normalized_priority = priority if priority in PRIORITIES else "normal"
    normalized_owner_queue = owner_queue if owner_queue in OWNER_QUEUES else "triage"
    clean_owner_ref = _clean_text_ref(assigned_owner_ref, "assigned_owner_ref")
    status, solver_outcome, proof_state, blocked_until, recovery_actions = _derive_status(
        live_probe_receipt_valid=live_validation.valid,
        live_probe_receipt_ready=live_validation.ready,
        observation_digest=observation_digest,
        message_digest=message_digest,
        thread_digest=thread_digest,
        subject_hash=subject_hash,
        sender_hash=sender_hash,
        recipient_hashes=safe_recipient_hashes,
        classification=normalized_classification,
        owner_queue=normalized_owner_queue,
        assignment_required=assignment_required,
        assigned_owner_ref=clean_owner_ref,
        evidence_refs=safe_evidence_refs,
    )
    receipt = TeamOpsSharedInboxObservationRoutingReceipt(
        receipt_id=_receipt_id(
            live_probe_receipt_path=live_probe_receipt_path,
            source_live_probe_receipt_id=str(source_receipt.get("receipt_id", "")),
            observation_digest=observation_digest,
            message_digest=message_digest,
            classification=normalized_classification,
            owner_queue=normalized_owner_queue,
            assigned_owner_ref=clean_owner_ref,
            status=status,
        ),
        schema_version=1,
        workflow_id="team_ops.shared_inbox_triage",
        source_live_probe_receipt_ref=_artifact_ref(live_probe_receipt_path),
        source_live_probe_receipt_id=str(source_receipt.get("receipt_id", "")),
        live_probe_receipt_valid=live_validation.valid,
        live_probe_receipt_ready=live_validation.ready,
        status=status,
        solver_outcome=solver_outcome,
        proof_state=proof_state,
        routed_at=routed_at or datetime.now(UTC).replace(microsecond=0).isoformat(),
        observation_digest=observation_digest,
        message_digest=message_digest,
        thread_digest=thread_digest,
        subject_hash=subject_hash,
        sender_hash=sender_hash,
        recipient_hashes=safe_recipient_hashes,
        classification=normalized_classification,
        priority=normalized_priority,
        owner_queue=normalized_owner_queue,
        assignment_required=assignment_required,
        assigned_owner_ref=clean_owner_ref,
        draft_response_required=draft_response_required,
        approval_required_before_external_send=True,
        external_send_allowed=False,
        draft_created_by_producer=False,
        external_mailbox_write_performed=False,
        external_message_sent=False,
        provider_mutation_performed=False,
        raw_message_content_serialized=False,
        no_secret_values_serialized=True,
        evidence_refs=safe_evidence_refs,
        blocked_until=blocked_until,
        recovery_actions=recovery_actions,
        validation_commands=VALIDATION_COMMANDS,
    )
    _assert_redacted(receipt.as_dict())
    _validate_receipt_against_schema(receipt, schema_path)
    return receipt


def write_team_ops_shared_inbox_observation_routing_receipt(
    receipt: TeamOpsSharedInboxObservationRoutingReceipt,
    output_path: Path,
) -> Path:
    """Write one TeamOps shared inbox observation routing receipt."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(receipt.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _derive_status(
    *,
    live_probe_receipt_valid: bool,
    live_probe_receipt_ready: bool,
    observation_digest: str,
    message_digest: str,
    thread_digest: str,
    subject_hash: str,
    sender_hash: str,
    recipient_hashes: Sequence[str],
    classification: str,
    owner_queue: str,
    assignment_required: bool,
    assigned_owner_ref: str,
    evidence_refs: Sequence[str],
) -> tuple[str, str, str, tuple[str, ...], tuple[str, ...]]:
    if not live_probe_receipt_valid:
        return (
            "failed",
            "GovernanceBlocked",
            "Fail",
            ("live_probe_receipt_invalid",),
            ("regenerate and validate the TeamOps live-probe receipt",),
        )
    if not live_probe_receipt_ready:
        return (
            "blocked",
            "AwaitingEvidence",
            "Unknown",
            ("live_probe_receipt_not_ready",),
            ("close TeamOps read-only live-probe evidence before routing observations",),
        )
    if not _redacted_observation_complete(
        observation_digest=observation_digest,
        message_digest=message_digest,
        thread_digest=thread_digest,
        subject_hash=subject_hash,
        sender_hash=sender_hash,
        recipient_hashes=recipient_hashes,
        evidence_refs=evidence_refs,
    ):
        return (
            "blocked",
            "AwaitingEvidence",
            "Unknown",
            ("redacted_observation_missing",),
            ("bind message, thread, subject, sender, recipient, and evidence hashes before routing",),
        )
    if classification == "unknown" or owner_queue == "triage":
        return (
            "blocked",
            "AwaitingEvidence",
            "Unknown",
            ("routing_classification_missing",),
            ("supply a non-unknown classification and non-triage owner queue from redacted evidence",),
        )
    if assignment_required and not assigned_owner_ref:
        return (
            "blocked",
            "AwaitingEvidence",
            "Unknown",
            ("assigned_owner_ref_missing",),
            ("bind a redacted owner reference before claiming assignment readiness",),
        )
    return ("passed", "SolvedVerified", "Pass", (), ())


def _redacted_observation_complete(
    *,
    observation_digest: str,
    message_digest: str,
    thread_digest: str,
    subject_hash: str,
    sender_hash: str,
    recipient_hashes: Sequence[str],
    evidence_refs: Sequence[str],
) -> bool:
    return (
        SHA256_HEX_PATTERN.fullmatch(observation_digest) is not None
        and SHA256_HEX_PATTERN.fullmatch(message_digest) is not None
        and SHA256_HEX_PATTERN.fullmatch(thread_digest) is not None
        and SHA256_HEX_PATTERN.fullmatch(subject_hash) is not None
        and SHA256_HEX_PATTERN.fullmatch(sender_hash) is not None
        and bool(recipient_hashes)
        and bool(evidence_refs)
    )


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


def _clean_hashes(values: Sequence[str], label: str) -> tuple[str, ...]:
    cleaned: list[str] = []
    for value in values:
        text = str(value).strip()
        if not text:
            continue
        _assert_redacted({label: text})
        if SHA256_HEX_PATTERN.fullmatch(text) is None:
            raise ValueError(f"{label} must be lowercase SHA-256 hex")
        cleaned.append(text)
    return tuple(dict.fromkeys(cleaned))


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


def _receipt_id(
    *,
    live_probe_receipt_path: Path,
    source_live_probe_receipt_id: str,
    observation_digest: str,
    message_digest: str,
    classification: str,
    owner_queue: str,
    assigned_owner_ref: str,
    status: str,
) -> str:
    material = {
        "live_probe_ref": _artifact_ref(live_probe_receipt_path),
        "source_live_probe_receipt_id": source_live_probe_receipt_id,
        "observation_digest": observation_digest,
        "message_digest": message_digest,
        "classification": classification,
        "owner_queue": owner_queue,
        "assigned_owner_ref": assigned_owner_ref,
        "status": status,
    }
    digest = hashlib.sha256(json.dumps(material, sort_keys=True).encode("utf-8")).hexdigest()
    return f"teamops-shared-inbox-observation-routing-receipt-{digest[:16]}"


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
            raise ValueError(f"TeamOps observation routing receipt contains secret marker: {marker}")


def _validate_receipt_against_schema(
    receipt: TeamOpsSharedInboxObservationRoutingReceipt,
    schema_path: Path,
) -> None:
    schema = _load_schema(schema_path)
    errors = _validate_schema_instance(schema, receipt.as_dict())
    if errors:
        raise RuntimeError(f"TeamOps observation routing receipt schema validation failed: {errors}")


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse TeamOps shared inbox observation routing receipt arguments."""

    parser = argparse.ArgumentParser(description="Produce TeamOps shared inbox observation routing receipt.")
    parser.add_argument("--live-probe-receipt", default=str(DEFAULT_LIVE_PROBE_RECEIPT))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--routed-at")
    parser.add_argument("--observation-digest", default="")
    parser.add_argument("--message-digest", default="")
    parser.add_argument("--thread-digest", default="")
    parser.add_argument("--subject-hash", default="")
    parser.add_argument("--sender-hash", default="")
    parser.add_argument("--recipient-hash", action="append", default=[])
    parser.add_argument("--classification", default="unknown")
    parser.add_argument("--priority", default="normal")
    parser.add_argument("--owner-queue", default="triage")
    parser.add_argument("--assigned-owner-ref", default="")
    parser.add_argument("--assignment-required", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--draft-response-required", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--evidence-ref", action="append", default=[])
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for TeamOps shared inbox observation routing receipts."""

    args = parse_args(argv)
    try:
        receipt = produce_team_ops_shared_inbox_observation_routing_receipt(
            live_probe_receipt_path=Path(args.live_probe_receipt),
            schema_path=Path(args.schema),
            routed_at=args.routed_at,
            observation_digest=str(args.observation_digest),
            message_digest=str(args.message_digest),
            thread_digest=str(args.thread_digest),
            subject_hash=str(args.subject_hash),
            sender_hash=str(args.sender_hash),
            recipient_hashes=tuple(str(item) for item in args.recipient_hash),
            classification=str(args.classification),
            priority=str(args.priority),
            owner_queue=str(args.owner_queue),
            assignment_required=bool(args.assignment_required),
            assigned_owner_ref=str(args.assigned_owner_ref),
            draft_response_required=bool(args.draft_response_required),
            evidence_refs=tuple(str(ref) for ref in args.evidence_ref),
        )
        write_team_ops_shared_inbox_observation_routing_receipt(receipt, Path(args.output))
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
            print(f"TeamOps shared inbox observation routing receipt failed: {exc}")
        return 1
    if args.json:
        print(json.dumps(receipt.as_dict(), indent=2, sort_keys=True))
    else:
        print(f"TeamOps shared inbox observation routing receipt written: {receipt.receipt_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
