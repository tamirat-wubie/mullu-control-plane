#!/usr/bin/env python3
"""Produce a TeamOps shared inbox approval decision receipt.

Purpose: bind a ready TeamOps approval queue obligation to redacted operator
decision evidence while preserving the separate send-receipt boundary.
Governance scope: TeamOps approval decision recording, separation of duty,
redaction, no-draft/no-send/no-provider-mutation enforcement, and recovery
evidence.
Dependencies: schemas/team_ops_shared_inbox_approval_decision_receipt.schema.json
and scripts.validate_team_ops_shared_inbox_approval_queue_receipt.
Invariants:
  - This producer records operator decision evidence; it does not make the decision.
  - Passed receipts retain the upstream provider-observation witness from the queue.
  - Approved decisions authorize only a later separate send-preparation receipt.
  - This producer never drafts, sends, writes a mailbox, or mutates a provider.
  - Raw message content, raw decision text, and secret-shaped values are rejected.
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

from scripts.produce_team_ops_shared_inbox_approval_queue_receipt import (  # noqa: E402
    APPROVAL_QUEUE_ID,
    APPROVER_ROLES,
    DEFAULT_OUTPUT as DEFAULT_QUEUE_RECEIPT,
)
from scripts.produce_team_ops_shared_inbox_operator_handoff import SECRET_VALUE_MARKERS  # noqa: E402
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402
from scripts.validate_team_ops_shared_inbox_approval_queue_receipt import (  # noqa: E402
    validate_team_ops_shared_inbox_approval_queue_receipt,
)


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "team_ops_shared_inbox_approval_decision_receipt.schema.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "team_ops_shared_inbox_approval_decision_receipt.json"
DECISIONS = {"approved", "denied", "expired"}
VALIDATION_COMMANDS = (
    "python scripts/validate_team_ops_shared_inbox_approval_decision_receipt.py --require-ready",
    "python scripts/validate_schemas.py --strict",
)


@dataclass(frozen=True, slots=True)
class TeamOpsSharedInboxApprovalDecisionReceipt:
    """Receipt for one TeamOps operator approval decision."""

    receipt_id: str
    schema_version: int
    workflow_id: str
    source_approval_queue_receipt_ref: str
    source_approval_queue_receipt_id: str
    approval_queue_receipt_valid: bool
    approval_queue_receipt_ready: bool
    provider_observation_receipt_ref: str
    provider_observation_receipt_id: str
    provider_observation_receipt_valid: bool
    status: str
    solver_outcome: str
    proof_state: str
    decided_at: str
    approval_queue_id: str
    approval_request_ref: str
    required_approver_role: str
    approver_ref: str
    approver_role: str
    decision: str
    approval_state: str
    decision_evidence_ref: str
    decision_reason_ref: str
    operator_decision_evidence_recorded: bool
    approval_decision_performed_by_producer: bool
    external_send_authorized_by_decision: bool
    requires_separate_send_receipt: bool
    draft_created_by_producer: bool
    external_mailbox_write_performed: bool
    external_message_sent: bool
    provider_mutation_performed: bool
    raw_message_content_serialized: bool
    raw_decision_text_serialized: bool
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


def produce_team_ops_shared_inbox_approval_decision_receipt(
    *,
    approval_queue_receipt_path: Path = DEFAULT_QUEUE_RECEIPT,
    schema_path: Path = DEFAULT_SCHEMA,
    decided_at: str | None = None,
    approver_ref: str = "",
    approver_role: str = "team_ops_owner",
    decision: str = "",
    decision_evidence_ref: str = "",
    decision_reason_ref: str = "",
    evidence_refs: Sequence[str] = (),
) -> TeamOpsSharedInboxApprovalDecisionReceipt:
    """Produce a no-send TeamOps approval decision receipt."""

    queue_validation = validate_team_ops_shared_inbox_approval_queue_receipt(
        receipt_path=approval_queue_receipt_path,
        require_ready=False,
    )
    queue_receipt = _load_json_object(approval_queue_receipt_path)
    clean_approver_ref = _clean_text_ref(approver_ref, "approver_ref")
    clean_decision_evidence_ref = _clean_text_ref(decision_evidence_ref, "decision_evidence_ref")
    clean_decision_reason_ref = _clean_text_ref(decision_reason_ref, "decision_reason_ref")
    clean_decision = decision if decision in DECISIONS else ""
    clean_approver_role = approver_role if approver_role in APPROVER_ROLES else ""
    required_approver_role = str(queue_receipt.get("required_approver_role", ""))
    safe_evidence_refs = tuple(_clean_evidence_refs((clean_decision_evidence_ref, *evidence_refs)))
    status, solver_outcome, proof_state, blocked_until, recovery_actions = _derive_status(
        queue_receipt_valid=queue_validation.valid,
        queue_receipt_ready=queue_validation.ready,
        approver_ref=clean_approver_ref,
        approver_role=clean_approver_role,
        required_approver_role=required_approver_role,
        decision=clean_decision,
        decision_evidence_ref=clean_decision_evidence_ref,
        evidence_refs=safe_evidence_refs,
    )
    receipt = TeamOpsSharedInboxApprovalDecisionReceipt(
        receipt_id=_receipt_id(
            approval_queue_receipt_path=approval_queue_receipt_path,
            source_approval_queue_receipt_id=str(queue_receipt.get("receipt_id", "")),
            provider_observation_receipt_id=str(queue_receipt.get("provider_observation_receipt_id", "")),
            approver_ref=clean_approver_ref,
            approver_role=clean_approver_role,
            decision=clean_decision,
            decision_evidence_ref=clean_decision_evidence_ref,
            status=status,
        ),
        schema_version=1,
        workflow_id="team_ops.shared_inbox_triage",
        source_approval_queue_receipt_ref=_artifact_ref(approval_queue_receipt_path),
        source_approval_queue_receipt_id=str(queue_receipt.get("receipt_id", "")),
        approval_queue_receipt_valid=queue_validation.valid,
        approval_queue_receipt_ready=queue_validation.ready,
        provider_observation_receipt_ref=str(queue_receipt.get("provider_observation_receipt_ref", "")),
        provider_observation_receipt_id=str(queue_receipt.get("provider_observation_receipt_id", "")),
        provider_observation_receipt_valid=queue_receipt.get("provider_observation_receipt_valid") is True,
        status=status,
        solver_outcome=solver_outcome,
        proof_state=proof_state,
        decided_at=decided_at or datetime.now(UTC).replace(microsecond=0).isoformat(),
        approval_queue_id=str(queue_receipt.get("approval_queue_id", "")) if queue_validation.ready else "",
        approval_request_ref=str(queue_receipt.get("approval_request_ref", "")) if queue_validation.ready else "",
        required_approver_role=required_approver_role if queue_validation.ready else "",
        approver_ref=clean_approver_ref,
        approver_role=clean_approver_role,
        decision=clean_decision,
        approval_state=_approval_state(clean_decision, status),
        decision_evidence_ref=clean_decision_evidence_ref,
        decision_reason_ref=clean_decision_reason_ref,
        operator_decision_evidence_recorded=status == "passed",
        approval_decision_performed_by_producer=False,
        external_send_authorized_by_decision=status == "passed" and clean_decision == "approved",
        requires_separate_send_receipt=True,
        draft_created_by_producer=False,
        external_mailbox_write_performed=False,
        external_message_sent=False,
        provider_mutation_performed=False,
        raw_message_content_serialized=False,
        raw_decision_text_serialized=False,
        no_secret_values_serialized=True,
        evidence_refs=safe_evidence_refs,
        blocked_until=blocked_until,
        recovery_actions=recovery_actions,
        validation_commands=VALIDATION_COMMANDS,
    )
    _assert_redacted(receipt.as_dict())
    _validate_receipt_against_schema(receipt, schema_path)
    return receipt


def write_team_ops_shared_inbox_approval_decision_receipt(
    receipt: TeamOpsSharedInboxApprovalDecisionReceipt,
    output_path: Path,
) -> Path:
    """Write one TeamOps approval decision receipt."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(receipt.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _derive_status(
    *,
    queue_receipt_valid: bool,
    queue_receipt_ready: bool,
    approver_ref: str,
    approver_role: str,
    required_approver_role: str,
    decision: str,
    decision_evidence_ref: str,
    evidence_refs: Sequence[str],
) -> tuple[str, str, str, tuple[str, ...], tuple[str, ...]]:
    if not queue_receipt_valid:
        return (
            "failed",
            "GovernanceBlocked",
            "Fail",
            ("approval_queue_receipt_invalid",),
            ("regenerate and validate the TeamOps approval queue receipt",),
        )
    if not queue_receipt_ready:
        return (
            "blocked",
            "AwaitingEvidence",
            "Unknown",
            ("approval_queue_receipt_not_ready",),
            ("close TeamOps approval queue evidence before recording an approval decision",),
        )
    if not approver_ref or not approver_role or not decision or not decision_evidence_ref or not evidence_refs:
        return (
            "blocked",
            "AwaitingEvidence",
            "Unknown",
            ("approval_decision_evidence_missing",),
            ("bind redacted approver, decision, and decision evidence refs before claiming readiness",),
        )
    if approver_role != required_approver_role:
        return (
            "failed",
            "GovernanceBlocked",
            "Fail",
            ("approver_role_mismatch",),
            ("record a decision from the required approver role or regenerate the approval queue obligation",),
        )
    return ("passed", "SolvedVerified", "Pass", (), ())


def _approval_state(decision: str, status: str) -> str:
    if status == "failed":
        return "invalid"
    if status != "passed":
        return "missing"
    return decision


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
    approval_queue_receipt_path: Path,
    source_approval_queue_receipt_id: str,
    provider_observation_receipt_id: str,
    approver_ref: str,
    approver_role: str,
    decision: str,
    decision_evidence_ref: str,
    status: str,
) -> str:
    material = {
        "queue_ref": _artifact_ref(approval_queue_receipt_path),
        "source_approval_queue_receipt_id": source_approval_queue_receipt_id,
        "provider_observation_receipt_id": provider_observation_receipt_id,
        "approver_ref": approver_ref,
        "approver_role": approver_role,
        "decision": decision,
        "decision_evidence_ref": decision_evidence_ref,
        "status": status,
    }
    digest = hashlib.sha256(json.dumps(material, sort_keys=True).encode("utf-8")).hexdigest()
    return f"teamops-shared-inbox-approval-decision-receipt-{digest[:16]}"


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
            raise ValueError(f"TeamOps approval decision receipt contains secret marker: {marker}")


def _validate_receipt_against_schema(
    receipt: TeamOpsSharedInboxApprovalDecisionReceipt,
    schema_path: Path,
) -> None:
    schema = _load_schema(schema_path)
    errors = _validate_schema_instance(schema, receipt.as_dict())
    if errors:
        raise RuntimeError(f"TeamOps approval decision receipt schema validation failed: {errors}")


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse TeamOps approval decision receipt arguments."""

    parser = argparse.ArgumentParser(description="Produce TeamOps shared inbox approval decision receipt.")
    parser.add_argument("--approval-queue-receipt", default=str(DEFAULT_QUEUE_RECEIPT))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--decided-at")
    parser.add_argument("--approver-ref", default="")
    parser.add_argument("--approver-role", default="team_ops_owner")
    parser.add_argument("--decision", default="")
    parser.add_argument("--decision-evidence-ref", default="")
    parser.add_argument("--decision-reason-ref", default="")
    parser.add_argument("--evidence-ref", action="append", default=[])
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for TeamOps approval decision receipt production."""

    args = parse_args(argv)
    try:
        receipt = produce_team_ops_shared_inbox_approval_decision_receipt(
            approval_queue_receipt_path=Path(args.approval_queue_receipt),
            schema_path=Path(args.schema),
            decided_at=args.decided_at,
            approver_ref=str(args.approver_ref),
            approver_role=str(args.approver_role),
            decision=str(args.decision),
            decision_evidence_ref=str(args.decision_evidence_ref),
            decision_reason_ref=str(args.decision_reason_ref),
            evidence_refs=tuple(str(ref) for ref in args.evidence_ref),
        )
        write_team_ops_shared_inbox_approval_decision_receipt(receipt, Path(args.output))
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
            print(f"TeamOps shared inbox approval decision receipt failed: {exc}")
        return 1
    if args.json:
        print(json.dumps(receipt.as_dict(), indent=2, sort_keys=True))
    else:
        print(f"TeamOps shared inbox approval decision receipt written: {receipt.receipt_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
