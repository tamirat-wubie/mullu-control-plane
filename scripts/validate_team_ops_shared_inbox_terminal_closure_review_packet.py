#!/usr/bin/env python3
"""Validate TeamOps terminal closure review packets.

Purpose: reject malformed, raw-content-bearing, effect-bearing, production-
claiming, or certificate-minting TeamOps terminal closure review packets.
Governance scope: TeamOps terminal closure review, evidence binding, replay
binding, duplicate-action protection, and no-terminal-closure-overclaim checks.
Dependencies: schemas/team_ops_shared_inbox_terminal_closure_review_packet.schema.json.
Invariants:
  - Ready packets require ready sent-message observation evidence.
  - Terminal closure review is not terminal closure certificate minting.
  - Raw message/provider fields and producer effect claims are rejected.
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
from scripts.produce_team_ops_shared_inbox_terminal_closure_review_packet import DEFAULT_OUTPUT  # noqa: E402
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "team_ops_shared_inbox_terminal_closure_review_packet.schema.json"
DEFAULT_VALIDATION_OUTPUT = (
    REPO_ROOT / ".change_assurance" / "team_ops_shared_inbox_terminal_closure_review_packet_validation.json"
)
RECEIPT_ID_PATTERN = re.compile(r"^teamops-shared-inbox-terminal-closure-review-packet-[0-9a-f]{16}$")
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
    "terminal_certificate",
    "closure_certificate",
}
FALSE_PRODUCER_EFFECT_FIELDS = (
    "review_performed_by_producer",
    "terminal_closure_certificate_minted_by_producer",
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
    "production_ready_claimed",
)


@dataclass(frozen=True, slots=True)
class TeamOpsSharedInboxTerminalClosureReviewPacketValidation:
    """Validation result for one TeamOps terminal closure review packet."""

    valid: bool
    ready: bool
    receipt_path: str
    schema_path: str
    receipt_id: str
    status: str
    solver_outcome: str
    proof_state: str
    sent_message_observation_receipt_ready: bool
    closure_review_state: str
    closure_review_ready: bool
    terminal_closure_candidate_ready: bool
    terminal_closure_certificate_required: bool
    required_terminal_evidence_count: int
    blocked_until: tuple[str, ...]
    errors: tuple[str, ...]
    next_action: str

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-ready validation receipt."""

        payload = asdict(self)
        payload["blocked_until"] = list(self.blocked_until)
        payload["errors"] = list(self.errors)
        return payload


def validate_team_ops_shared_inbox_terminal_closure_review_packet(
    *,
    packet_path: Path = DEFAULT_OUTPUT,
    schema_path: Path = DEFAULT_SCHEMA,
    require_ready: bool = False,
) -> TeamOpsSharedInboxTerminalClosureReviewPacketValidation:
    """Validate one TeamOps terminal closure review packet."""

    errors: list[str] = []
    try:
        schema = _load_schema(schema_path)
    except OSError:
        schema = {}
        errors.append("TeamOps terminal closure review packet schema file missing")
    packet = _load_json_object(packet_path, "TeamOps terminal closure review packet", errors)
    if schema and packet:
        errors.extend(_validate_schema_instance(schema, packet))
        _validate_semantics(packet, errors)
        if require_ready and not _packet_ready(packet):
            errors.append("TeamOps terminal closure review packet ready must be true")
    ready = not errors and _packet_ready(packet)
    required_refs = packet.get("required_terminal_evidence_refs", [])
    return TeamOpsSharedInboxTerminalClosureReviewPacketValidation(
        valid=not errors,
        ready=ready,
        receipt_path=_path_label(packet_path),
        schema_path=_path_label(schema_path),
        receipt_id=str(packet.get("receipt_id", "")),
        status=str(packet.get("status", "")),
        solver_outcome=str(packet.get("solver_outcome", "")),
        proof_state=str(packet.get("proof_state", "")),
        sent_message_observation_receipt_ready=packet.get("sent_message_observation_receipt_ready") is True,
        closure_review_state=str(packet.get("closure_review_state", "")),
        closure_review_ready=packet.get("closure_review_ready") is True,
        terminal_closure_candidate_ready=packet.get("terminal_closure_candidate_ready") is True,
        terminal_closure_certificate_required=packet.get("terminal_closure_certificate_required") is True,
        required_terminal_evidence_count=len(required_refs) if isinstance(required_refs, list) else 0,
        blocked_until=tuple(str(item) for item in packet.get("blocked_until", ()))
        if isinstance(packet.get("blocked_until", ()), list)
        else (),
        errors=tuple(errors),
        next_action=_next_action(packet),
    )


def write_team_ops_shared_inbox_terminal_closure_review_packet_validation(
    validation: TeamOpsSharedInboxTerminalClosureReviewPacketValidation,
    output_path: Path,
) -> Path:
    """Write one TeamOps terminal closure review packet validation receipt."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_semantics(packet: dict[str, Any], errors: list[str]) -> None:
    serialized = json.dumps(packet, sort_keys=True)
    for marker in SECRET_VALUE_MARKERS:
        if marker.lower() in serialized.lower():
            errors.append(f"packet must not serialize secret marker: {marker}")
    for field_name in RAW_FIELD_NAMES:
        if field_name in packet:
            errors.append(f"packet must not serialize raw field: {field_name}")
    if not RECEIPT_ID_PATTERN.fullmatch(str(packet.get("receipt_id", ""))):
        errors.append("receipt_id must match TeamOps terminal closure review pattern")
    for field_name in FALSE_PRODUCER_EFFECT_FIELDS:
        if packet.get(field_name) is not False:
            errors.append(f"{field_name} must be false")
    if packet.get("no_secret_values_serialized") is not True:
        errors.append("no_secret_values_serialized must be true")
    if packet.get("report_is_not_terminal_closure") is not True:
        errors.append("report_is_not_terminal_closure must be true")
    if packet.get("terminal_closure_certificate_required") is not True:
        errors.append("terminal_closure_certificate_required must be true")
    if packet.get("status") == "passed":
        _validate_ready_packet(packet, errors)
    elif packet.get("status") == "blocked":
        _validate_blocked_packet(packet, errors)
    elif packet.get("status") == "failed":
        _validate_failed_packet(packet, errors)
    else:
        errors.append("status must be blocked, failed, or passed")


def _validate_ready_packet(packet: dict[str, Any], errors: list[str]) -> None:
    if packet.get("sent_message_observation_receipt_valid") is not True:
        errors.append("passed packet requires valid sent-message observation receipt")
    if packet.get("sent_message_observation_receipt_ready") is not True:
        errors.append("passed packet requires ready sent-message observation receipt")
    if packet.get("solver_outcome") != "SolvedVerified":
        errors.append("passed packet requires solver_outcome=SolvedVerified")
    if packet.get("proof_state") != "Pass":
        errors.append("passed packet requires proof_state=Pass")
    if packet.get("closure_review_state") != "assembled":
        errors.append("passed packet requires closure_review_state=assembled")
    for field_name in (
        "closure_review_ready",
        "terminal_closure_candidate_ready",
        "approval_chain_reviewed",
        "send_execution_reviewed",
        "sent_message_observation_reviewed",
        "duplicate_absence_reviewed",
        "deterministic_replay_reviewed",
        "duplicate_absence_observed",
        "deterministic_replay_observed",
    ):
        if packet.get(field_name) is not True:
            errors.append(f"passed packet requires {field_name}=true")
    for field_name in (
        "review_packet_ref",
        "send_execution_ref",
        "dispatch_receipt_ref",
        "provider_message_ref",
        "first_observation_ref",
        "second_observation_ref",
        "replay_ref",
    ):
        if not str(packet.get(field_name, "")).strip():
            errors.append(f"passed packet requires {field_name}")
    for field_name in (
        "review_packet_hash",
        "provider_message_hash",
        "first_observation_hash",
        "second_observation_hash",
        "replay_hash",
    ):
        if SHA256_HEX_PATTERN.fullmatch(str(packet.get(field_name, ""))) is None:
            errors.append(f"passed packet requires {field_name} sha256 hex")
    if packet.get("first_observation_hash") != packet.get("provider_message_hash"):
        errors.append("first_observation_hash must match provider_message_hash")
    if packet.get("second_observation_hash") != packet.get("provider_message_hash"):
        errors.append("second_observation_hash must match provider_message_hash")
    if not isinstance(packet.get("required_terminal_evidence_refs"), list) or len(
        packet.get("required_terminal_evidence_refs", [])
    ) < 8:
        errors.append("passed packet requires all required terminal evidence refs")
    if not isinstance(packet.get("evidence_refs"), list) or len(packet.get("evidence_refs", [])) < 8:
        errors.append("passed packet requires evidence_refs")
    if packet.get("blocked_until") != []:
        errors.append("passed packet must not carry blockers")


def _validate_blocked_packet(packet: dict[str, Any], errors: list[str]) -> None:
    if packet.get("solver_outcome") != "AwaitingEvidence":
        errors.append("blocked packet requires solver_outcome=AwaitingEvidence")
    if packet.get("proof_state") != "Unknown":
        errors.append("blocked packet requires proof_state=Unknown")
    if packet.get("closure_review_ready") is not False:
        errors.append("blocked packet must not be closure-review ready")
    if packet.get("terminal_closure_candidate_ready") is not False:
        errors.append("blocked packet must not be terminal-closure-candidate ready")
    if not isinstance(packet.get("blocked_until"), list) or not packet.get("blocked_until"):
        errors.append("blocked packet must list blockers")


def _validate_failed_packet(packet: dict[str, Any], errors: list[str]) -> None:
    if packet.get("solver_outcome") != "GovernanceBlocked":
        errors.append("failed packet requires solver_outcome=GovernanceBlocked")
    if packet.get("proof_state") != "Fail":
        errors.append("failed packet requires proof_state=Fail")
    if packet.get("closure_review_ready") is not False:
        errors.append("failed packet must not be closure-review ready")
    if packet.get("terminal_closure_candidate_ready") is not False:
        errors.append("failed packet must not be terminal-closure-candidate ready")
    if not isinstance(packet.get("blocked_until"), list) or not packet.get("blocked_until"):
        errors.append("failed packet must list blockers")


def _packet_ready(packet: dict[str, Any]) -> bool:
    return (
        packet.get("status") == "passed"
        and packet.get("solver_outcome") == "SolvedVerified"
        and packet.get("proof_state") == "Pass"
        and packet.get("sent_message_observation_receipt_valid") is True
        and packet.get("sent_message_observation_receipt_ready") is True
        and packet.get("closure_review_state") == "assembled"
        and packet.get("closure_review_ready") is True
        and packet.get("terminal_closure_candidate_ready") is True
        and packet.get("terminal_closure_certificate_required") is True
        and SHA256_HEX_PATTERN.fullmatch(str(packet.get("review_packet_hash", ""))) is not None
        and bool(str(packet.get("review_packet_ref", "")).strip())
        and packet.get("first_observation_hash") == packet.get("provider_message_hash")
        and packet.get("second_observation_hash") == packet.get("provider_message_hash")
        and packet.get("duplicate_absence_observed") is True
        and packet.get("deterministic_replay_observed") is True
        and all(packet.get(field_name) is False for field_name in FALSE_PRODUCER_EFFECT_FIELDS)
        and packet.get("no_secret_values_serialized") is True
        and packet.get("report_is_not_terminal_closure") is True
        and isinstance(packet.get("required_terminal_evidence_refs"), list)
        and len(packet.get("required_terminal_evidence_refs", [])) >= 8
        and isinstance(packet.get("evidence_refs"), list)
        and len(packet.get("evidence_refs", [])) >= 8
        and packet.get("blocked_until") == []
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


def _next_action(packet: dict[str, Any]) -> str:
    if _packet_ready(packet):
        return "mint TeamOps terminal closure certificate from reviewed packet"
    recovery_actions = packet.get("recovery_actions", [])
    if isinstance(recovery_actions, list) and recovery_actions:
        return str(recovery_actions[0])
    return "regenerate TeamOps terminal closure review packet"


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse TeamOps terminal closure review validation arguments."""

    parser = argparse.ArgumentParser(description="Validate TeamOps terminal closure review packet.")
    parser.add_argument("--packet", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_VALIDATION_OUTPUT))
    parser.add_argument("--require-ready", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for TeamOps terminal closure review packet validation."""

    args = parse_args(argv)
    validation = validate_team_ops_shared_inbox_terminal_closure_review_packet(
        packet_path=Path(args.packet),
        schema_path=Path(args.schema),
        require_ready=args.require_ready,
    )
    write_team_ops_shared_inbox_terminal_closure_review_packet_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.valid:
        print(f"TeamOps terminal closure review packet valid ready={validation.ready}")
    else:
        print(f"TeamOps terminal closure review packet invalid errors={list(validation.errors)}")
    return 0 if validation.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
