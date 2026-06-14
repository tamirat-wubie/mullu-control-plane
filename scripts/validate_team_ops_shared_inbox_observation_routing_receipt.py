#!/usr/bin/env python3
"""Validate TeamOps shared inbox observation routing receipts.

Purpose: reject malformed, raw-content-bearing, effect-bearing, or unready
TeamOps shared inbox routing receipts before workflow promotion.
Governance scope: TeamOps no-send routing, redacted observation evidence,
assignment obligation, approval gating, and external-effect rejection.
Dependencies: schemas/team_ops_shared_inbox_observation_routing_receipt.schema.json.
Invariants:
  - Ready routing receipts require a ready live-probe receipt and redacted
    observation hashes.
  - Raw subject, sender, recipient, message body, and query fields are forbidden.
  - Draft creation, external sends, mailbox writes, and provider mutations fail closed.
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

from scripts.produce_team_ops_shared_inbox_observation_routing_receipt import DEFAULT_OUTPUT  # noqa: E402
from scripts.produce_team_ops_shared_inbox_operator_handoff import SECRET_VALUE_MARKERS  # noqa: E402
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "team_ops_shared_inbox_observation_routing_receipt.schema.json"
DEFAULT_VALIDATION_OUTPUT = (
    REPO_ROOT / ".change_assurance" / "team_ops_shared_inbox_observation_routing_receipt_validation.json"
)
RECEIPT_ID_PATTERN = re.compile(r"^teamops-shared-inbox-observation-routing-receipt-[0-9a-f]{16}$")
SHA256_HEX_PATTERN = re.compile(r"^[0-9a-f]{64}$")
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
}
READY_CLASSIFICATIONS = {
    "support_request",
    "sales_request",
    "finance_request",
    "security_request",
    "internal_ops",
}
READY_OWNER_QUEUES = {"support", "sales", "finance", "security", "operations"}


@dataclass(frozen=True, slots=True)
class TeamOpsSharedInboxObservationRoutingReceiptValidation:
    """Validation result for one TeamOps shared inbox routing receipt."""

    valid: bool
    ready: bool
    receipt_path: str
    schema_path: str
    receipt_id: str
    status: str
    solver_outcome: str
    proof_state: str
    live_probe_receipt_ready: bool
    classification: str
    owner_queue: str
    blocked_until: tuple[str, ...]
    errors: tuple[str, ...]
    next_action: str

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-ready validation receipt."""

        payload = asdict(self)
        payload["blocked_until"] = list(self.blocked_until)
        payload["errors"] = list(self.errors)
        return payload


def validate_team_ops_shared_inbox_observation_routing_receipt(
    *,
    receipt_path: Path = DEFAULT_OUTPUT,
    schema_path: Path = DEFAULT_SCHEMA,
    require_ready: bool = False,
) -> TeamOpsSharedInboxObservationRoutingReceiptValidation:
    """Validate one TeamOps shared inbox observation routing receipt."""

    errors: list[str] = []
    try:
        schema = _load_schema(schema_path)
    except OSError:
        schema = {}
        errors.append("TeamOps observation routing receipt schema file missing")
    receipt = _load_json_object(receipt_path, "TeamOps observation routing receipt", errors)
    if schema and receipt:
        errors.extend(_validate_schema_instance(schema, receipt))
        _validate_semantics(receipt, errors)
        if require_ready and not _receipt_ready(receipt):
            errors.append("TeamOps observation routing receipt ready must be true")
    ready = not errors and _receipt_ready(receipt)
    return TeamOpsSharedInboxObservationRoutingReceiptValidation(
        valid=not errors,
        ready=ready,
        receipt_path=_path_label(receipt_path),
        schema_path=_path_label(schema_path),
        receipt_id=str(receipt.get("receipt_id", "")),
        status=str(receipt.get("status", "")),
        solver_outcome=str(receipt.get("solver_outcome", "")),
        proof_state=str(receipt.get("proof_state", "")),
        live_probe_receipt_ready=receipt.get("live_probe_receipt_ready") is True,
        classification=str(receipt.get("classification", "")),
        owner_queue=str(receipt.get("owner_queue", "")),
        blocked_until=tuple(str(item) for item in receipt.get("blocked_until", ()))
        if isinstance(receipt.get("blocked_until", ()), list)
        else (),
        errors=tuple(errors),
        next_action=_next_action(receipt),
    )


def write_team_ops_shared_inbox_observation_routing_receipt_validation(
    validation: TeamOpsSharedInboxObservationRoutingReceiptValidation,
    output_path: Path,
) -> Path:
    """Write one TeamOps shared inbox observation routing validation receipt."""

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
        errors.append("receipt_id must match TeamOps observation routing pattern")
    for field_name in (
        "external_send_allowed",
        "draft_created_by_producer",
        "external_mailbox_write_performed",
        "external_message_sent",
        "provider_mutation_performed",
        "raw_message_content_serialized",
    ):
        if receipt.get(field_name) is not False:
            errors.append(f"{field_name} must be false")
    if receipt.get("no_secret_values_serialized") is not True:
        errors.append("no_secret_values_serialized must be true")
    if receipt.get("approval_required_before_external_send") is not True:
        errors.append("approval_required_before_external_send must be true")
    if receipt.get("status") == "passed":
        _validate_ready_receipt(receipt, errors)
    elif receipt.get("status") == "blocked":
        _validate_blocked_receipt(receipt, errors)
    elif receipt.get("status") == "failed":
        _validate_failed_receipt(receipt, errors)
    else:
        errors.append("status must be blocked, failed, or passed")


def _validate_ready_receipt(receipt: dict[str, Any], errors: list[str]) -> None:
    if receipt.get("live_probe_receipt_valid") is not True:
        errors.append("passed receipt requires valid live-probe receipt")
    if receipt.get("live_probe_receipt_ready") is not True:
        errors.append("passed receipt requires ready live-probe receipt")
    if receipt.get("solver_outcome") != "SolvedVerified":
        errors.append("passed receipt requires solver_outcome=SolvedVerified")
    if receipt.get("proof_state") != "Pass":
        errors.append("passed receipt requires proof_state=Pass")
    for field_name in ("observation_digest", "message_digest", "thread_digest", "subject_hash", "sender_hash"):
        if not SHA256_HEX_PATTERN.fullmatch(str(receipt.get(field_name, ""))):
            errors.append(f"passed receipt requires lowercase SHA-256 {field_name}")
    if not isinstance(receipt.get("recipient_hashes"), list) or not receipt.get("recipient_hashes"):
        errors.append("passed receipt requires recipient_hashes")
    if receipt.get("classification") not in READY_CLASSIFICATIONS:
        errors.append("passed receipt requires non-unknown classification")
    if receipt.get("owner_queue") not in READY_OWNER_QUEUES:
        errors.append("passed receipt requires non-triage owner_queue")
    if receipt.get("assignment_required") is True and not str(receipt.get("assigned_owner_ref", "")).strip():
        errors.append("passed receipt requires assigned_owner_ref when assignment_required")
    if not isinstance(receipt.get("evidence_refs"), list) or not receipt.get("evidence_refs"):
        errors.append("passed receipt requires evidence_refs")
    if receipt.get("blocked_until") != []:
        errors.append("passed receipt must not carry blockers")


def _validate_blocked_receipt(receipt: dict[str, Any], errors: list[str]) -> None:
    if receipt.get("solver_outcome") != "AwaitingEvidence":
        errors.append("blocked receipt requires solver_outcome=AwaitingEvidence")
    if receipt.get("proof_state") != "Unknown":
        errors.append("blocked receipt requires proof_state=Unknown")
    if not isinstance(receipt.get("blocked_until"), list) or not receipt.get("blocked_until"):
        errors.append("blocked receipt must list blockers")


def _validate_failed_receipt(receipt: dict[str, Any], errors: list[str]) -> None:
    if receipt.get("solver_outcome") != "GovernanceBlocked":
        errors.append("failed receipt requires solver_outcome=GovernanceBlocked")
    if receipt.get("proof_state") != "Fail":
        errors.append("failed receipt requires proof_state=Fail")
    if not isinstance(receipt.get("blocked_until"), list) or not receipt.get("blocked_until"):
        errors.append("failed receipt must list blockers")


def _receipt_ready(receipt: dict[str, Any]) -> bool:
    return (
        receipt.get("status") == "passed"
        and receipt.get("solver_outcome") == "SolvedVerified"
        and receipt.get("proof_state") == "Pass"
        and receipt.get("live_probe_receipt_valid") is True
        and receipt.get("live_probe_receipt_ready") is True
        and all(
            SHA256_HEX_PATTERN.fullmatch(str(receipt.get(field_name, ""))) is not None
            for field_name in ("observation_digest", "message_digest", "thread_digest", "subject_hash", "sender_hash")
        )
        and isinstance(receipt.get("recipient_hashes"), list)
        and bool(receipt.get("recipient_hashes"))
        and receipt.get("classification") in READY_CLASSIFICATIONS
        and receipt.get("owner_queue") in READY_OWNER_QUEUES
        and (receipt.get("assignment_required") is not True or bool(str(receipt.get("assigned_owner_ref", "")).strip()))
        and receipt.get("approval_required_before_external_send") is True
        and receipt.get("external_send_allowed") is False
        and receipt.get("draft_created_by_producer") is False
        and receipt.get("external_mailbox_write_performed") is False
        and receipt.get("external_message_sent") is False
        and receipt.get("provider_mutation_performed") is False
        and receipt.get("raw_message_content_serialized") is False
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
        return "promote TeamOps shared inbox routing plan to approval queue checks"
    recovery_actions = receipt.get("recovery_actions", [])
    if isinstance(recovery_actions, list) and recovery_actions:
        return str(recovery_actions[0])
    return "regenerate TeamOps shared inbox observation routing receipt"


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse TeamOps shared inbox observation routing validation arguments."""

    parser = argparse.ArgumentParser(description="Validate TeamOps shared inbox observation routing receipt.")
    parser.add_argument("--receipt", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_VALIDATION_OUTPUT))
    parser.add_argument("--require-ready", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for TeamOps shared inbox observation routing validation."""

    args = parse_args(argv)
    validation = validate_team_ops_shared_inbox_observation_routing_receipt(
        receipt_path=Path(args.receipt),
        schema_path=Path(args.schema),
        require_ready=args.require_ready,
    )
    write_team_ops_shared_inbox_observation_routing_receipt_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.valid:
        print(f"TeamOps shared inbox observation routing receipt valid ready={validation.ready}")
    else:
        print(f"TeamOps shared inbox observation routing receipt invalid errors={list(validation.errors)}")
    return 0 if validation.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
