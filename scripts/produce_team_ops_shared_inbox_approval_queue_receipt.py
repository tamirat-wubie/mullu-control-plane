#!/usr/bin/env python3
"""Produce a TeamOps shared inbox approval queue receipt.

Purpose: bind a ready TeamOps observation-routing receipt to a redacted
approval queue obligation while preserving the external-send block.
Governance scope: TeamOps approval-gate composition, queue-obligation evidence,
approval/send separation, redaction, and external-effect rejection.
Dependencies: schemas/team_ops_shared_inbox_approval_queue_receipt.schema.json
and scripts.validate_team_ops_shared_inbox_observation_routing_receipt.
Invariants:
  - This producer never approves, drafts, sends, writes a mailbox, or mutates a provider.
  - Passed receipts require a ready routing receipt, retained provider-observation identity,
    and a redacted approval request ref.
  - Approval decision evidence is a later receipt, not produced here.
  - Raw message content and secret-shaped values are rejected before serialization.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.produce_team_ops_shared_inbox_observation_routing_receipt import (  # noqa: E402
    DEFAULT_OUTPUT as DEFAULT_ROUTING_RECEIPT,
)
from scripts.produce_team_ops_shared_inbox_operator_handoff import SECRET_VALUE_MARKERS  # noqa: E402
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402
from scripts.validate_team_ops_shared_inbox_observation_routing_receipt import (  # noqa: E402
    validate_team_ops_shared_inbox_observation_routing_receipt,
)


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "team_ops_shared_inbox_approval_queue_receipt.schema.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "team_ops_shared_inbox_approval_queue_receipt.json"
APPROVAL_QUEUE_ID = "team_ops.external_send_approval"
APPROVER_ROLES = {
    "team_ops_owner",
    "team_ops_manager",
    "security_reviewer",
    "finance_owner",
    "operations_owner",
}
VALIDATION_COMMANDS = (
    "python scripts/validate_team_ops_shared_inbox_approval_queue_receipt.py --require-ready",
    "python scripts/validate_schemas.py --strict",
)


@dataclass(frozen=True, slots=True)
class TeamOpsSharedInboxApprovalQueueReceipt:
    """Receipt for one TeamOps external-send approval queue obligation."""

    receipt_id: str
    schema_version: int
    workflow_id: str
    source_observation_routing_receipt_ref: str
    source_observation_routing_receipt_id: str
    routing_receipt_valid: bool
    routing_receipt_ready: bool
    provider_observation_receipt_ref: str
    provider_observation_receipt_id: str
    provider_observation_receipt_valid: bool
    status: str
    solver_outcome: str
    proof_state: str
    queued_at: str
    approval_queue_id: str
    approval_request_ref: str
    required_approver_role: str
    approval_state: str
    approval_decision_ref: str
    approval_required_before_external_send: bool
    approval_queue_obligation_bound: bool
    draft_response_required: bool
    external_send_allowed: bool
    approval_decision_performed_by_producer: bool
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
        payload["evidence_refs"] = list(self.evidence_refs)
        payload["blocked_until"] = list(self.blocked_until)
        payload["recovery_actions"] = list(self.recovery_actions)
        payload["validation_commands"] = list(self.validation_commands)
        return payload


def produce_team_ops_shared_inbox_approval_queue_receipt(
    *,
    routing_receipt_path: Path = DEFAULT_ROUTING_RECEIPT,
    schema_path: Path = DEFAULT_SCHEMA,
    queued_at: str | None = None,
    approval_request_ref: str = "",
    required_approver_role: str = "team_ops_owner",
    evidence_refs: Sequence[str] = (),
) -> TeamOpsSharedInboxApprovalQueueReceipt:
    """Produce a no-send TeamOps approval queue obligation receipt."""

    routing_validation = validate_team_ops_shared_inbox_observation_routing_receipt(
        receipt_path=routing_receipt_path,
        require_ready=False,
    )
    source_receipt = _load_json_object(routing_receipt_path)
    clean_approval_request_ref = _clean_text_ref(approval_request_ref, "approval_request_ref")
    safe_evidence_refs = tuple(_clean_evidence_refs(evidence_refs))
    clean_role = required_approver_role if required_approver_role in APPROVER_ROLES else ""
    status, solver_outcome, proof_state, blocked_until, recovery_actions = _derive_status(
        routing_receipt_valid=routing_validation.valid,
        routing_receipt_ready=routing_validation.ready,
        approval_request_ref=clean_approval_request_ref,
        required_approver_role=clean_role,
        evidence_refs=safe_evidence_refs,
    )
    receipt = TeamOpsSharedInboxApprovalQueueReceipt(
        receipt_id=_receipt_id(
            routing_receipt_path=routing_receipt_path,
            source_observation_routing_receipt_id=str(source_receipt.get("receipt_id", "")),
            provider_observation_receipt_id=str(source_receipt.get("provider_observation_receipt_id", "")),
            approval_request_ref=clean_approval_request_ref,
            required_approver_role=clean_role,
            status=status,
        ),
        schema_version=1,
        workflow_id="team_ops.shared_inbox_triage",
        source_observation_routing_receipt_ref=_artifact_ref(routing_receipt_path),
        source_observation_routing_receipt_id=str(source_receipt.get("receipt_id", "")),
        routing_receipt_valid=routing_validation.valid,
        routing_receipt_ready=routing_validation.ready,
        provider_observation_receipt_ref=str(source_receipt.get("provider_observation_receipt_ref", "")),
        provider_observation_receipt_id=str(source_receipt.get("provider_observation_receipt_id", "")),
        provider_observation_receipt_valid=source_receipt.get("provider_observation_receipt_valid") is True,
        status=status,
        solver_outcome=solver_outcome,
        proof_state=proof_state,
        queued_at=queued_at or datetime.now(UTC).replace(microsecond=0).isoformat(),
        approval_queue_id=APPROVAL_QUEUE_ID if routing_validation.ready else "",
        approval_request_ref=clean_approval_request_ref,
        required_approver_role=clean_role,
        approval_state="pending" if status == "passed" else "missing",
        approval_decision_ref="",
        approval_required_before_external_send=True,
        approval_queue_obligation_bound=status == "passed",
        draft_response_required=source_receipt.get("draft_response_required") is True,
        external_send_allowed=False,
        approval_decision_performed_by_producer=False,
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


def write_team_ops_shared_inbox_approval_queue_receipt(
    receipt: TeamOpsSharedInboxApprovalQueueReceipt,
    output_path: Path,
) -> Path:
    """Write one TeamOps shared inbox approval queue receipt."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(receipt.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _derive_status(
    *,
    routing_receipt_valid: bool,
    routing_receipt_ready: bool,
    approval_request_ref: str,
    required_approver_role: str,
    evidence_refs: Sequence[str],
) -> tuple[str, str, str, tuple[str, ...], tuple[str, ...]]:
    if not routing_receipt_valid:
        return (
            "failed",
            "GovernanceBlocked",
            "Fail",
            ("observation_routing_receipt_invalid",),
            ("regenerate and validate the TeamOps observation routing receipt",),
        )
    if not routing_receipt_ready:
        return (
            "blocked",
            "AwaitingEvidence",
            "Unknown",
            ("observation_routing_receipt_not_ready",),
            ("close TeamOps observation routing evidence before creating approval queue obligations",),
        )
    if not approval_request_ref or not required_approver_role or not evidence_refs:
        return (
            "blocked",
            "AwaitingEvidence",
            "Unknown",
            ("approval_queue_evidence_missing",),
            ("bind a redacted approval request ref, approver role, and queue evidence before claiming readiness",),
        )
    return ("passed", "SolvedVerified", "Pass", (), ())


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


def _receipt_id(
    *,
    routing_receipt_path: Path,
    source_observation_routing_receipt_id: str,
    provider_observation_receipt_id: str,
    approval_request_ref: str,
    required_approver_role: str,
    status: str,
) -> str:
    material = {
        "routing_ref": _artifact_ref(routing_receipt_path),
        "source_observation_routing_receipt_id": source_observation_routing_receipt_id,
        "provider_observation_receipt_id": provider_observation_receipt_id,
        "approval_request_ref": approval_request_ref,
        "required_approver_role": required_approver_role,
        "status": status,
    }
    digest = hashlib.sha256(json.dumps(material, sort_keys=True).encode("utf-8")).hexdigest()
    return f"teamops-shared-inbox-approval-queue-receipt-{digest[:16]}"


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
            raise ValueError(f"TeamOps approval queue receipt contains secret marker: {marker}")


def _validate_receipt_against_schema(
    receipt: TeamOpsSharedInboxApprovalQueueReceipt,
    schema_path: Path,
) -> None:
    schema = _load_schema(schema_path)
    errors = _validate_schema_instance(schema, receipt.as_dict())
    if errors:
        raise RuntimeError(f"TeamOps approval queue receipt schema validation failed: {errors}")


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse TeamOps shared inbox approval queue receipt arguments."""

    parser = argparse.ArgumentParser(description="Produce TeamOps shared inbox approval queue receipt.")
    parser.add_argument("--routing-receipt", default=str(DEFAULT_ROUTING_RECEIPT))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--queued-at")
    parser.add_argument("--approval-request-ref", default="")
    parser.add_argument("--required-approver-role", default="team_ops_owner")
    parser.add_argument("--evidence-ref", action="append", default=[])
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for TeamOps approval queue receipt production."""

    args = parse_args(argv)
    try:
        receipt = produce_team_ops_shared_inbox_approval_queue_receipt(
            routing_receipt_path=Path(args.routing_receipt),
            schema_path=Path(args.schema),
            queued_at=args.queued_at,
            approval_request_ref=str(args.approval_request_ref),
            required_approver_role=str(args.required_approver_role),
            evidence_refs=tuple(str(ref) for ref in args.evidence_ref),
        )
        write_team_ops_shared_inbox_approval_queue_receipt(receipt, Path(args.output))
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
            print(f"TeamOps shared inbox approval queue receipt failed: {exc}")
        return 1
    if args.json:
        print(json.dumps(receipt.as_dict(), indent=2, sort_keys=True))
    else:
        print(f"TeamOps shared inbox approval queue receipt written: {receipt.receipt_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
