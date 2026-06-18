#!/usr/bin/env python3
"""Validate TeamOps sent-message observation receipts.

Purpose: reject malformed, raw-content-bearing, locally effect-bearing,
non-replayed, or inconsistent TeamOps sent-message observation receipts.
Governance scope: TeamOps external-send closure evidence, replay evidence,
duplicate-action protection, redacted observation, and local provider-effect denial.
Dependencies: schemas/team_ops_shared_inbox_sent_message_observation_receipt.schema.json.
Invariants:
  - Ready observation requires ready send-execution evidence.
  - Ready observation retains the upstream provider-observation witness.
  - Two provider observations must match the send-execution provider message hash.
  - Replay and duplicate-absence evidence are required before closure readiness.
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

from scripts.produce_team_ops_shared_inbox_operator_handoff import SECRET_VALUE_MARKERS  # noqa: E402
from scripts.produce_team_ops_shared_inbox_send_execution_receipt import SHA256_HEX_PATTERN  # noqa: E402
from scripts.produce_team_ops_shared_inbox_sent_message_observation_receipt import DEFAULT_OUTPUT  # noqa: E402
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "team_ops_shared_inbox_sent_message_observation_receipt.schema.json"
DEFAULT_VALIDATION_OUTPUT = (
    REPO_ROOT / ".change_assurance" / "team_ops_shared_inbox_sent_message_observation_receipt_validation.json"
)
RECEIPT_ID_PATTERN = re.compile(r"^teamops-shared-inbox-sent-message-observation-receipt-[0-9a-f]{16}$")
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
    "recipient",
    "raw_provider_response",
    "provider_response",
    "provider_message_id",
    "message_id",
    "raw_dispatch_receipt",
    "dispatch_receipt",
    "sent_message",
    "raw_sent_message",
    "provider_payload",
}
FALSE_PRODUCER_EFFECT_FIELDS = (
    "observation_performed_by_producer",
    "external_message_sent_by_producer",
    "external_mailbox_write_performed_by_producer",
    "provider_mutation_performed_by_producer",
    "provider_call_performed_by_producer",
    "draft_created_by_producer",
    "raw_message_content_serialized",
    "raw_recipient_serialized",
    "raw_subject_serialized",
    "raw_body_serialized",
    "raw_provider_payload_serialized",
)


@dataclass(frozen=True, slots=True)
class TeamOpsSharedInboxSentMessageObservationReceiptValidation:
    """Validation result for one TeamOps sent-message observation receipt."""

    valid: bool
    ready: bool
    receipt_path: str
    schema_path: str
    receipt_id: str
    status: str
    solver_outcome: str
    proof_state: str
    send_execution_receipt_ready: bool
    provider_observation_receipt_valid: bool
    sent_message_observation_state: str
    sent_message_observation_ready: bool
    observation_count: int
    duplicate_absence_observed: bool
    deterministic_replay_observed: bool
    workflow_closure_ready: bool
    blocked_until: tuple[str, ...]
    errors: tuple[str, ...]
    next_action: str

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-ready validation receipt."""

        payload = asdict(self)
        payload["blocked_until"] = list(self.blocked_until)
        payload["errors"] = list(self.errors)
        return payload


def validate_team_ops_shared_inbox_sent_message_observation_receipt(
    *,
    receipt_path: Path = DEFAULT_OUTPUT,
    schema_path: Path = DEFAULT_SCHEMA,
    require_ready: bool = False,
) -> TeamOpsSharedInboxSentMessageObservationReceiptValidation:
    """Validate one TeamOps sent-message observation receipt."""

    errors: list[str] = []
    try:
        schema = _load_schema(schema_path)
    except OSError:
        schema = {}
        errors.append("TeamOps sent-message observation receipt schema file missing")
    receipt = _load_json_object(receipt_path, "TeamOps sent-message observation receipt", errors)
    if schema and receipt:
        errors.extend(_validate_schema_instance(schema, receipt))
        _validate_semantics(receipt, errors)
        if require_ready and not _receipt_ready(receipt):
            errors.append("TeamOps sent-message observation receipt ready must be true")
    ready = not errors and _receipt_ready(receipt)
    return TeamOpsSharedInboxSentMessageObservationReceiptValidation(
        valid=not errors,
        ready=ready,
        receipt_path=_path_label(receipt_path),
        schema_path=_path_label(schema_path),
        receipt_id=str(receipt.get("receipt_id", "")),
        status=str(receipt.get("status", "")),
        solver_outcome=str(receipt.get("solver_outcome", "")),
        proof_state=str(receipt.get("proof_state", "")),
        send_execution_receipt_ready=receipt.get("send_execution_receipt_ready") is True,
        provider_observation_receipt_valid=receipt.get("provider_observation_receipt_valid") is True,
        sent_message_observation_state=str(receipt.get("sent_message_observation_state", "")),
        sent_message_observation_ready=receipt.get("sent_message_observation_ready") is True,
        observation_count=int(receipt.get("observation_count", 0)) if isinstance(receipt.get("observation_count", 0), int) else 0,
        duplicate_absence_observed=receipt.get("duplicate_absence_observed") is True,
        deterministic_replay_observed=receipt.get("deterministic_replay_observed") is True,
        workflow_closure_ready=receipt.get("workflow_closure_ready") is True,
        blocked_until=tuple(str(item) for item in receipt.get("blocked_until", ()))
        if isinstance(receipt.get("blocked_until", ()), list)
        else (),
        errors=tuple(errors),
        next_action=_next_action(receipt),
    )


def write_team_ops_shared_inbox_sent_message_observation_receipt_validation(
    validation: TeamOpsSharedInboxSentMessageObservationReceiptValidation,
    output_path: Path,
) -> Path:
    """Write one TeamOps sent-message observation validation receipt."""

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
        errors.append("receipt_id must match TeamOps sent-message observation pattern")
    for field_name in FALSE_PRODUCER_EFFECT_FIELDS:
        if receipt.get(field_name) is not False:
            errors.append(f"{field_name} must be false")
    if receipt.get("no_secret_values_serialized") is not True:
        errors.append("no_secret_values_serialized must be true")
    if receipt.get("report_is_not_terminal_closure") is not True:
        errors.append("report_is_not_terminal_closure must be true")
    if receipt.get("terminal_closure_required") is not True:
        errors.append("terminal_closure_required must be true")
    if receipt.get("status") == "passed":
        _validate_ready_receipt(receipt, errors)
    elif receipt.get("status") == "blocked":
        _validate_blocked_receipt(receipt, errors)
    elif receipt.get("status") == "failed":
        _validate_failed_receipt(receipt, errors)
    else:
        errors.append("status must be blocked, failed, or passed")


def _validate_ready_receipt(receipt: dict[str, Any], errors: list[str]) -> None:
    if receipt.get("send_execution_receipt_valid") is not True:
        errors.append("passed receipt requires valid send execution receipt")
    if receipt.get("send_execution_receipt_ready") is not True:
        errors.append("passed receipt requires ready send execution receipt")
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
    for field_name in ("send_execution_ref", "dispatch_receipt_ref", "provider_message_ref"):
        if not str(receipt.get(field_name, "")).strip():
            errors.append(f"passed receipt requires {field_name}")
    for field_name in ("provider_message_hash", "first_observation_hash", "second_observation_hash", "replay_hash"):
        if SHA256_HEX_PATTERN.fullmatch(str(receipt.get(field_name, ""))) is None:
            errors.append(f"passed receipt requires {field_name} sha256 hex")
    for field_name in ("first_observation_ref", "second_observation_ref", "replay_ref"):
        if not str(receipt.get(field_name, "")).strip():
            errors.append(f"passed receipt requires {field_name}")
    if receipt.get("first_observation_hash") != receipt.get("provider_message_hash"):
        errors.append("first_observation_hash must match provider_message_hash")
    if receipt.get("second_observation_hash") != receipt.get("provider_message_hash"):
        errors.append("second_observation_hash must match provider_message_hash")
    if receipt.get("sent_message_observation_state") != "observed":
        errors.append("passed receipt requires sent_message_observation_state=observed")
    if receipt.get("sent_message_observation_ready") is not True:
        errors.append("passed receipt requires sent_message_observation_ready=true")
    if receipt.get("observation_count", 0) < 2:
        errors.append("passed receipt requires at least two observations")
    for field_name in (
        "provider_state_consistent",
        "provider_message_hash_matches_execution",
        "duplicate_absence_observed",
        "deterministic_replay_observed",
        "workflow_closure_ready",
    ):
        if receipt.get(field_name) is not True:
            errors.append(f"passed receipt requires {field_name}=true")
    if not isinstance(receipt.get("evidence_refs"), list) or len(receipt.get("evidence_refs", [])) < 4:
        errors.append("passed receipt requires observation and replay evidence_refs")
    if receipt.get("blocked_until") != []:
        errors.append("passed receipt must not carry blockers")


def _validate_blocked_receipt(receipt: dict[str, Any], errors: list[str]) -> None:
    if receipt.get("solver_outcome") != "AwaitingEvidence":
        errors.append("blocked receipt requires solver_outcome=AwaitingEvidence")
    if receipt.get("proof_state") != "Unknown":
        errors.append("blocked receipt requires proof_state=Unknown")
    if receipt.get("sent_message_observation_ready") is not False:
        errors.append("blocked receipt must not be observation ready")
    if receipt.get("workflow_closure_ready") is not False:
        errors.append("blocked receipt must not be workflow-closure ready")
    if not isinstance(receipt.get("blocked_until"), list) or not receipt.get("blocked_until"):
        errors.append("blocked receipt must list blockers")


def _validate_failed_receipt(receipt: dict[str, Any], errors: list[str]) -> None:
    if receipt.get("solver_outcome") != "GovernanceBlocked":
        errors.append("failed receipt requires solver_outcome=GovernanceBlocked")
    if receipt.get("proof_state") != "Fail":
        errors.append("failed receipt requires proof_state=Fail")
    if receipt.get("sent_message_observation_ready") is not False:
        errors.append("failed receipt must not be observation ready")
    if receipt.get("workflow_closure_ready") is not False:
        errors.append("failed receipt must not be workflow-closure ready")
    if not isinstance(receipt.get("blocked_until"), list) or not receipt.get("blocked_until"):
        errors.append("failed receipt must list blockers")


def _receipt_ready(receipt: dict[str, Any]) -> bool:
    return (
        receipt.get("status") == "passed"
        and receipt.get("solver_outcome") == "SolvedVerified"
        and receipt.get("proof_state") == "Pass"
        and receipt.get("send_execution_receipt_valid") is True
        and receipt.get("send_execution_receipt_ready") is True
        and bool(str(receipt.get("provider_observation_receipt_ref", "")).strip())
        and _valid_provider_observation_receipt_id(receipt)
        and receipt.get("provider_observation_receipt_valid") is True
        and bool(str(receipt.get("send_execution_ref", "")).strip())
        and bool(str(receipt.get("dispatch_receipt_ref", "")).strip())
        and bool(str(receipt.get("provider_message_ref", "")).strip())
        and SHA256_HEX_PATTERN.fullmatch(str(receipt.get("provider_message_hash", ""))) is not None
        and bool(str(receipt.get("first_observation_ref", "")).strip())
        and bool(str(receipt.get("second_observation_ref", "")).strip())
        and receipt.get("first_observation_hash") == receipt.get("provider_message_hash")
        and receipt.get("second_observation_hash") == receipt.get("provider_message_hash")
        and receipt.get("observation_count", 0) >= 2
        and receipt.get("provider_state_consistent") is True
        and receipt.get("provider_message_hash_matches_execution") is True
        and receipt.get("duplicate_absence_observed") is True
        and bool(str(receipt.get("replay_ref", "")).strip())
        and SHA256_HEX_PATTERN.fullmatch(str(receipt.get("replay_hash", ""))) is not None
        and receipt.get("deterministic_replay_observed") is True
        and receipt.get("workflow_closure_ready") is True
        and all(receipt.get(field_name) is False for field_name in FALSE_PRODUCER_EFFECT_FIELDS)
        and receipt.get("no_secret_values_serialized") is True
        and receipt.get("report_is_not_terminal_closure") is True
        and receipt.get("terminal_closure_required") is True
        and isinstance(receipt.get("evidence_refs"), list)
        and len(receipt.get("evidence_refs", [])) >= 4
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
        return "prepare TeamOps shared inbox terminal closure review packet"
    recovery_actions = receipt.get("recovery_actions", [])
    if isinstance(recovery_actions, list) and recovery_actions:
        return str(recovery_actions[0])
    return "regenerate TeamOps sent-message observation receipt"


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse TeamOps sent-message observation validation arguments."""

    parser = argparse.ArgumentParser(description="Validate TeamOps sent-message observation receipt.")
    parser.add_argument("--receipt", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_VALIDATION_OUTPUT))
    parser.add_argument("--require-ready", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for TeamOps sent-message observation validation."""

    args = parse_args(argv)
    validation = validate_team_ops_shared_inbox_sent_message_observation_receipt(
        receipt_path=Path(args.receipt),
        schema_path=Path(args.schema),
        require_ready=args.require_ready,
    )
    write_team_ops_shared_inbox_sent_message_observation_receipt_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.valid:
        print(f"TeamOps sent-message observation receipt valid ready={validation.ready}")
    else:
        print(f"TeamOps sent-message observation receipt invalid errors={list(validation.errors)}")
    return 0 if validation.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
