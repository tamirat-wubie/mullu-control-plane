#!/usr/bin/env python3
"""Validate TeamOps shared inbox approval decision receipts.

Purpose: reject malformed, raw-content-bearing, effect-bearing, or unready
TeamOps approval decision receipts before send-preparation promotion.
Governance scope: TeamOps approval decision recording, separation of duty,
redacted evidence, and external-effect rejection.
Dependencies: schemas/team_ops_shared_inbox_approval_decision_receipt.schema.json.
Invariants:
  - Ready decision receipts require a ready approval queue receipt and retained
    provider-observation witness identity.
  - Approved decisions authorize only a later separate send receipt.
  - Draft creation, external sends, mailbox writes, provider mutations, raw
    message content, raw decision text, and secret markers fail closed.
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

from scripts.produce_team_ops_shared_inbox_approval_decision_receipt import (  # noqa: E402
    DECISIONS,
    DEFAULT_OUTPUT,
)
from scripts.produce_team_ops_shared_inbox_approval_queue_receipt import (  # noqa: E402
    APPROVAL_QUEUE_ID,
    APPROVER_ROLES,
)
from scripts.produce_team_ops_shared_inbox_operator_handoff import SECRET_VALUE_MARKERS  # noqa: E402
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "team_ops_shared_inbox_approval_decision_receipt.schema.json"
DEFAULT_VALIDATION_OUTPUT = (
    REPO_ROOT / ".change_assurance" / "team_ops_shared_inbox_approval_decision_receipt_validation.json"
)
RECEIPT_ID_PATTERN = re.compile(r"^teamops-shared-inbox-approval-decision-receipt-[0-9a-f]{16}$")
PROVIDER_OBSERVATION_RECEIPT_ID_PATTERN = re.compile(
    r"^teamops-shared-inbox-provider-observation-receipt-[0-9a-f]{16}$"
)
RAW_FIELD_NAMES = {
    "raw_subject",
    "subject",
    "message_body",
    "body",
    "raw_sender",
    "sender_email",
    "recipient_email",
    "raw_recipient",
    "query",
    "raw_decision_text",
    "decision_text",
}
FALSE_EFFECT_FIELDS = (
    "approval_decision_performed_by_producer",
    "draft_created_by_producer",
    "external_mailbox_write_performed",
    "external_message_sent",
    "provider_mutation_performed",
    "raw_message_content_serialized",
    "raw_decision_text_serialized",
)


@dataclass(frozen=True, slots=True)
class TeamOpsSharedInboxApprovalDecisionReceiptValidation:
    """Validation result for one TeamOps approval decision receipt."""

    valid: bool
    ready: bool
    receipt_path: str
    schema_path: str
    receipt_id: str
    status: str
    solver_outcome: str
    proof_state: str
    approval_queue_receipt_ready: bool
    provider_observation_receipt_valid: bool
    decision: str
    approval_state: str
    external_send_authorized_by_decision: bool
    blocked_until: tuple[str, ...]
    errors: tuple[str, ...]
    next_action: str

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-ready validation receipt."""

        payload = asdict(self)
        payload["blocked_until"] = list(self.blocked_until)
        payload["errors"] = list(self.errors)
        return payload


def validate_team_ops_shared_inbox_approval_decision_receipt(
    *,
    receipt_path: Path = DEFAULT_OUTPUT,
    schema_path: Path = DEFAULT_SCHEMA,
    require_ready: bool = False,
) -> TeamOpsSharedInboxApprovalDecisionReceiptValidation:
    """Validate one TeamOps shared inbox approval decision receipt."""

    errors: list[str] = []
    try:
        schema = _load_schema(schema_path)
    except OSError:
        schema = {}
        errors.append("TeamOps approval decision receipt schema file missing")
    receipt = _load_json_object(receipt_path, "TeamOps approval decision receipt", errors)
    if schema and receipt:
        errors.extend(_validate_schema_instance(schema, receipt))
        _validate_semantics(receipt, errors)
        if require_ready and not _receipt_ready(receipt):
            errors.append("TeamOps approval decision receipt ready must be true")
    ready = not errors and _receipt_ready(receipt)
    return TeamOpsSharedInboxApprovalDecisionReceiptValidation(
        valid=not errors,
        ready=ready,
        receipt_path=_path_label(receipt_path),
        schema_path=_path_label(schema_path),
        receipt_id=str(receipt.get("receipt_id", "")),
        status=str(receipt.get("status", "")),
        solver_outcome=str(receipt.get("solver_outcome", "")),
        proof_state=str(receipt.get("proof_state", "")),
        approval_queue_receipt_ready=receipt.get("approval_queue_receipt_ready") is True,
        provider_observation_receipt_valid=receipt.get("provider_observation_receipt_valid") is True,
        decision=str(receipt.get("decision", "")),
        approval_state=str(receipt.get("approval_state", "")),
        external_send_authorized_by_decision=receipt.get("external_send_authorized_by_decision") is True,
        blocked_until=tuple(str(item) for item in receipt.get("blocked_until", ()))
        if isinstance(receipt.get("blocked_until", ()), list)
        else (),
        errors=tuple(errors),
        next_action=_next_action(receipt),
    )


def write_team_ops_shared_inbox_approval_decision_receipt_validation(
    validation: TeamOpsSharedInboxApprovalDecisionReceiptValidation,
    output_path: Path,
) -> Path:
    """Write one TeamOps approval decision validation receipt."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_semantics(receipt: dict[str, Any], errors: list[str]) -> None:
    serialized = json.dumps(receipt, sort_keys=True)
    for marker in SECRET_VALUE_MARKERS:
        if marker.lower() in serialized.lower():
            errors.append(f"receipt must not serialize secret marker: {marker}")
    for field_name in RAW_FIELD_NAMES:
        if field_name in receipt:
            errors.append(f"receipt must not serialize raw field: {field_name}")
    if not RECEIPT_ID_PATTERN.fullmatch(str(receipt.get("receipt_id", ""))):
        errors.append("receipt_id must match TeamOps approval decision pattern")
    for field_name in FALSE_EFFECT_FIELDS:
        if receipt.get(field_name) is not False:
            errors.append(f"{field_name} must be false")
    if receipt.get("requires_separate_send_receipt") is not True:
        errors.append("requires_separate_send_receipt must be true")
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
    if receipt.get("approval_queue_receipt_valid") is not True:
        errors.append("passed receipt requires valid approval queue receipt")
    if receipt.get("approval_queue_receipt_ready") is not True:
        errors.append("passed receipt requires ready approval queue receipt")
    if not str(receipt.get("provider_observation_receipt_ref", "")).strip():
        errors.append("passed receipt requires provider_observation_receipt_ref")
    if not _valid_provider_observation_receipt_id(receipt):
        errors.append("passed receipt requires provider_observation_receipt_id")
    if receipt.get("provider_observation_receipt_valid") is not True:
        errors.append("passed receipt requires provider_observation_receipt_valid=true")
    if receipt.get("solver_outcome") != "SolvedVerified":
        errors.append("passed receipt requires solver_outcome=SolvedVerified")
    if receipt.get("proof_state") != "Pass":
        errors.append("passed receipt requires proof_state=Pass")
    if receipt.get("approval_queue_id") != APPROVAL_QUEUE_ID:
        errors.append("passed receipt requires TeamOps approval queue id")
    if not str(receipt.get("approval_request_ref", "")).strip():
        errors.append("passed receipt requires approval_request_ref")
    if receipt.get("required_approver_role") not in APPROVER_ROLES:
        errors.append("passed receipt requires allowed required approver role")
    if not str(receipt.get("approver_ref", "")).strip():
        errors.append("passed receipt requires approver_ref")
    if receipt.get("approver_role") != receipt.get("required_approver_role"):
        errors.append("passed receipt requires approver_role to match required_approver_role")
    if receipt.get("decision") not in DECISIONS:
        errors.append("passed receipt requires approved, denied, or expired decision")
    if receipt.get("approval_state") != receipt.get("decision"):
        errors.append("passed receipt requires approval_state to match decision")
    if not str(receipt.get("decision_evidence_ref", "")).strip():
        errors.append("passed receipt requires decision_evidence_ref")
    if receipt.get("operator_decision_evidence_recorded") is not True:
        errors.append("passed receipt requires operator_decision_evidence_recorded=true")
    if receipt.get("external_send_authorized_by_decision") is not (receipt.get("decision") == "approved"):
        errors.append("external_send_authorized_by_decision must match approved decision only")
    if not isinstance(receipt.get("evidence_refs"), list) or not receipt.get("evidence_refs"):
        errors.append("passed receipt requires evidence_refs")
    if receipt.get("blocked_until") != []:
        errors.append("passed receipt must not carry blockers")


def _validate_blocked_receipt(receipt: dict[str, Any], errors: list[str]) -> None:
    if receipt.get("solver_outcome") != "AwaitingEvidence":
        errors.append("blocked receipt requires solver_outcome=AwaitingEvidence")
    if receipt.get("proof_state") != "Unknown":
        errors.append("blocked receipt requires proof_state=Unknown")
    if receipt.get("external_send_authorized_by_decision") is not False:
        errors.append("blocked receipt must not authorize send")
    if not isinstance(receipt.get("blocked_until"), list) or not receipt.get("blocked_until"):
        errors.append("blocked receipt must list blockers")


def _validate_failed_receipt(receipt: dict[str, Any], errors: list[str]) -> None:
    if receipt.get("solver_outcome") != "GovernanceBlocked":
        errors.append("failed receipt requires solver_outcome=GovernanceBlocked")
    if receipt.get("proof_state") != "Fail":
        errors.append("failed receipt requires proof_state=Fail")
    if receipt.get("external_send_authorized_by_decision") is not False:
        errors.append("failed receipt must not authorize send")
    if not isinstance(receipt.get("blocked_until"), list) or not receipt.get("blocked_until"):
        errors.append("failed receipt must list blockers")


def _receipt_ready(receipt: dict[str, Any]) -> bool:
    return (
        receipt.get("status") == "passed"
        and receipt.get("solver_outcome") == "SolvedVerified"
        and receipt.get("proof_state") == "Pass"
        and receipt.get("approval_queue_receipt_valid") is True
        and receipt.get("approval_queue_receipt_ready") is True
        and bool(str(receipt.get("provider_observation_receipt_ref", "")).strip())
        and _valid_provider_observation_receipt_id(receipt)
        and receipt.get("provider_observation_receipt_valid") is True
        and receipt.get("approval_queue_id") == APPROVAL_QUEUE_ID
        and bool(str(receipt.get("approval_request_ref", "")).strip())
        and receipt.get("required_approver_role") in APPROVER_ROLES
        and bool(str(receipt.get("approver_ref", "")).strip())
        and receipt.get("approver_role") == receipt.get("required_approver_role")
        and receipt.get("decision") in DECISIONS
        and receipt.get("approval_state") == receipt.get("decision")
        and bool(str(receipt.get("decision_evidence_ref", "")).strip())
        and receipt.get("operator_decision_evidence_recorded") is True
        and receipt.get("external_send_authorized_by_decision") is (receipt.get("decision") == "approved")
        and receipt.get("requires_separate_send_receipt") is True
        and all(receipt.get(field_name) is False for field_name in FALSE_EFFECT_FIELDS)
        and receipt.get("no_secret_values_serialized") is True
        and isinstance(receipt.get("evidence_refs"), list)
        and bool(receipt.get("evidence_refs"))
        and receipt.get("blocked_until") == []
    )


def _valid_provider_observation_receipt_id(receipt: dict[str, Any]) -> bool:
    return (
        PROVIDER_OBSERVATION_RECEIPT_ID_PATTERN.fullmatch(
            str(receipt.get("provider_observation_receipt_id", ""))
        )
        is not None
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
        if receipt.get("decision") == "approved":
            return "prepare separate TeamOps send-preparation receipt before any external send"
        return "close TeamOps shared inbox request without external send"
    recovery_actions = receipt.get("recovery_actions", [])
    if isinstance(recovery_actions, list) and recovery_actions:
        return str(recovery_actions[0])
    return "regenerate TeamOps shared inbox approval decision receipt"


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse TeamOps approval decision validation arguments."""

    parser = argparse.ArgumentParser(description="Validate TeamOps shared inbox approval decision receipt.")
    parser.add_argument("--receipt", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_VALIDATION_OUTPUT))
    parser.add_argument("--require-ready", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for TeamOps approval decision validation."""

    args = parse_args(argv)
    validation = validate_team_ops_shared_inbox_approval_decision_receipt(
        receipt_path=Path(args.receipt),
        schema_path=Path(args.schema),
        require_ready=args.require_ready,
    )
    write_team_ops_shared_inbox_approval_decision_receipt_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.valid:
        print(f"TeamOps shared inbox approval decision receipt valid ready={validation.ready}")
    else:
        print(f"TeamOps shared inbox approval decision receipt invalid errors={list(validation.errors)}")
    return 0 if validation.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
