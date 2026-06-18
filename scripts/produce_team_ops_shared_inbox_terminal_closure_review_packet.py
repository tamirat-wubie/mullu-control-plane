#!/usr/bin/env python3
"""Produce a TeamOps terminal closure review packet.

Purpose: assemble a redacted terminal-closure candidate review packet from a
ready TeamOps sent-message observation receipt without minting terminal closure.
Governance scope: TeamOps workflow closure review, evidence binding, replay
binding, duplicate-action protection, no-production-claim, and no-effect checks.
Dependencies: schemas/team_ops_shared_inbox_terminal_closure_review_packet.schema.json
and scripts.validate_team_ops_shared_inbox_sent_message_observation_receipt.
Invariants:
  - Only ready sent-message observation receipts can assemble closure review.
  - Ready review packets retain provider-observation receipt identity from observation evidence.
  - Review packets bind evidence refs and hashes; raw message/provider data is rejected.
  - The producer does not call providers, send messages, create drafts, or mint closure certificates.
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

from scripts.produce_team_ops_shared_inbox_operator_handoff import SECRET_VALUE_MARKERS  # noqa: E402
from scripts.produce_team_ops_shared_inbox_sent_message_observation_receipt import (  # noqa: E402
    DEFAULT_OUTPUT as DEFAULT_SENT_MESSAGE_OBSERVATION_RECEIPT,
    SHA256_HEX_PATTERN,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402
from scripts.validate_team_ops_shared_inbox_sent_message_observation_receipt import (  # noqa: E402
    validate_team_ops_shared_inbox_sent_message_observation_receipt,
)


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "team_ops_shared_inbox_terminal_closure_review_packet.schema.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "team_ops_shared_inbox_terminal_closure_review_packet.json"
VALIDATION_COMMANDS = (
    "python scripts/validate_team_ops_shared_inbox_terminal_closure_review_packet.py --require-ready",
    "python scripts/validate_schemas.py --strict",
)


@dataclass(frozen=True, slots=True)
class TeamOpsSharedInboxTerminalClosureReviewPacket:
    """Receipt-like review packet for TeamOps terminal closure candidates."""

    receipt_id: str
    schema_version: int
    workflow_id: str
    source_sent_message_observation_receipt_ref: str
    source_sent_message_observation_receipt_id: str
    sent_message_observation_receipt_valid: bool
    sent_message_observation_receipt_ready: bool
    provider_observation_receipt_ref: str
    provider_observation_receipt_id: str
    provider_observation_receipt_valid: bool
    status: str
    solver_outcome: str
    proof_state: str
    reviewed_at: str
    closure_review_state: str
    closure_review_ready: bool
    terminal_closure_candidate_ready: bool
    terminal_closure_certificate_required: bool
    review_packet_ref: str
    review_packet_hash: str
    send_execution_ref: str
    dispatch_receipt_ref: str
    provider_message_ref: str
    provider_message_hash: str
    first_observation_ref: str
    first_observation_hash: str
    second_observation_ref: str
    second_observation_hash: str
    duplicate_absence_observed: bool
    replay_ref: str
    replay_hash: str
    deterministic_replay_observed: bool
    required_terminal_evidence_refs: tuple[str, ...]
    approval_chain_reviewed: bool
    send_execution_reviewed: bool
    sent_message_observation_reviewed: bool
    duplicate_absence_reviewed: bool
    deterministic_replay_reviewed: bool
    review_performed_by_producer: bool
    terminal_closure_certificate_minted_by_producer: bool
    external_message_sent_by_producer: bool
    external_mailbox_write_performed_by_producer: bool
    provider_mutation_performed_by_producer: bool
    provider_call_performed_by_producer: bool
    draft_created_by_producer: bool
    raw_message_content_serialized: bool
    raw_recipient_serialized: bool
    raw_subject_serialized: bool
    raw_body_serialized: bool
    raw_provider_payload_serialized: bool
    no_secret_values_serialized: bool
    report_is_not_terminal_closure: bool
    production_ready_claimed: bool
    evidence_refs: tuple[str, ...]
    blocked_until: tuple[str, ...]
    recovery_actions: tuple[str, ...]
    validation_commands: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-ready packet."""

        payload = asdict(self)
        payload["required_terminal_evidence_refs"] = list(self.required_terminal_evidence_refs)
        payload["evidence_refs"] = list(self.evidence_refs)
        payload["blocked_until"] = list(self.blocked_until)
        payload["recovery_actions"] = list(self.recovery_actions)
        payload["validation_commands"] = list(self.validation_commands)
        return payload


def produce_team_ops_shared_inbox_terminal_closure_review_packet(
    *,
    sent_message_observation_receipt_path: Path = DEFAULT_SENT_MESSAGE_OBSERVATION_RECEIPT,
    schema_path: Path = DEFAULT_SCHEMA,
    reviewed_at: str | None = None,
    evidence_refs: Sequence[str] = (),
) -> TeamOpsSharedInboxTerminalClosureReviewPacket:
    """Produce a TeamOps terminal closure review packet."""

    observation_validation = validate_team_ops_shared_inbox_sent_message_observation_receipt(
        receipt_path=sent_message_observation_receipt_path,
        require_ready=False,
    )
    observation_receipt = _load_json_object(sent_message_observation_receipt_path)
    observation_ready = observation_validation.ready
    required_refs = _derive_required_terminal_evidence_refs(observation_receipt) if observation_ready else ()
    safe_extra_refs = _clean_evidence_refs(tuple(evidence_refs))
    evidence = tuple(dict.fromkeys((*required_refs, *safe_extra_refs)))
    status, solver_outcome, proof_state, blocked_until, recovery_actions = _derive_status(
        sent_message_observation_receipt_valid=observation_validation.valid,
        sent_message_observation_receipt_ready=observation_ready,
        required_terminal_evidence_refs=evidence,
    )
    passed = status == "passed"
    review_packet_hash = _review_packet_hash(observation_receipt, evidence) if passed else ""
    review_packet_ref = f"teamops-terminal-closure-review:{review_packet_hash[:16]}" if passed else ""
    packet = TeamOpsSharedInboxTerminalClosureReviewPacket(
        receipt_id=_receipt_id(
            sent_message_observation_receipt_path=sent_message_observation_receipt_path,
            source_sent_message_observation_receipt_id=str(observation_receipt.get("receipt_id", "")),
            status=status,
            evidence_refs=evidence,
        ),
        schema_version=1,
        workflow_id="team_ops.shared_inbox_triage",
        source_sent_message_observation_receipt_ref=_artifact_ref(sent_message_observation_receipt_path),
        source_sent_message_observation_receipt_id=str(observation_receipt.get("receipt_id", "")),
        sent_message_observation_receipt_valid=observation_validation.valid,
        sent_message_observation_receipt_ready=observation_ready,
        provider_observation_receipt_ref=str(observation_receipt.get("provider_observation_receipt_ref", ""))
        if passed
        else "",
        provider_observation_receipt_id=str(observation_receipt.get("provider_observation_receipt_id", ""))
        if passed
        else "",
        provider_observation_receipt_valid=observation_receipt.get("provider_observation_receipt_valid") is True
        if passed
        else False,
        status=status,
        solver_outcome=solver_outcome,
        proof_state=proof_state,
        reviewed_at=reviewed_at or datetime.now(UTC).replace(microsecond=0).isoformat(),
        closure_review_state="assembled" if passed else ("invalid" if status == "failed" else "missing"),
        closure_review_ready=passed,
        terminal_closure_candidate_ready=passed,
        terminal_closure_certificate_required=True,
        review_packet_ref=review_packet_ref,
        review_packet_hash=review_packet_hash,
        send_execution_ref=str(observation_receipt.get("send_execution_ref", "")) if passed else "",
        dispatch_receipt_ref=str(observation_receipt.get("dispatch_receipt_ref", "")) if passed else "",
        provider_message_ref=str(observation_receipt.get("provider_message_ref", "")) if passed else "",
        provider_message_hash=str(observation_receipt.get("provider_message_hash", "")) if passed else "",
        first_observation_ref=str(observation_receipt.get("first_observation_ref", "")) if passed else "",
        first_observation_hash=str(observation_receipt.get("first_observation_hash", "")) if passed else "",
        second_observation_ref=str(observation_receipt.get("second_observation_ref", "")) if passed else "",
        second_observation_hash=str(observation_receipt.get("second_observation_hash", "")) if passed else "",
        duplicate_absence_observed=observation_receipt.get("duplicate_absence_observed") is True if passed else False,
        replay_ref=str(observation_receipt.get("replay_ref", "")) if passed else "",
        replay_hash=str(observation_receipt.get("replay_hash", "")) if passed else "",
        deterministic_replay_observed=observation_receipt.get("deterministic_replay_observed") is True if passed else False,
        required_terminal_evidence_refs=evidence if passed else (),
        approval_chain_reviewed=passed,
        send_execution_reviewed=passed,
        sent_message_observation_reviewed=passed,
        duplicate_absence_reviewed=passed,
        deterministic_replay_reviewed=passed,
        review_performed_by_producer=False,
        terminal_closure_certificate_minted_by_producer=False,
        external_message_sent_by_producer=False,
        external_mailbox_write_performed_by_producer=False,
        provider_mutation_performed_by_producer=False,
        provider_call_performed_by_producer=False,
        draft_created_by_producer=False,
        raw_message_content_serialized=False,
        raw_recipient_serialized=False,
        raw_subject_serialized=False,
        raw_body_serialized=False,
        raw_provider_payload_serialized=False,
        no_secret_values_serialized=True,
        report_is_not_terminal_closure=True,
        production_ready_claimed=False,
        evidence_refs=evidence if passed else (),
        blocked_until=blocked_until,
        recovery_actions=recovery_actions,
        validation_commands=VALIDATION_COMMANDS,
    )
    _assert_redacted(packet.as_dict())
    _validate_packet_against_schema(packet, schema_path)
    return packet


def write_team_ops_shared_inbox_terminal_closure_review_packet(
    packet: TeamOpsSharedInboxTerminalClosureReviewPacket,
    output_path: Path,
) -> Path:
    """Write one TeamOps terminal closure review packet."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(packet.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _derive_status(
    *,
    sent_message_observation_receipt_valid: bool,
    sent_message_observation_receipt_ready: bool,
    required_terminal_evidence_refs: Sequence[str],
) -> tuple[str, str, str, tuple[str, ...], tuple[str, ...]]:
    if not sent_message_observation_receipt_valid:
        return (
            "failed",
            "GovernanceBlocked",
            "Fail",
            ("sent_message_observation_receipt_invalid",),
            ("regenerate and validate the TeamOps sent-message observation receipt",),
        )
    if not sent_message_observation_receipt_ready:
        return (
            "blocked",
            "AwaitingEvidence",
            "Unknown",
            ("sent_message_observation_receipt_not_ready",),
            ("record ready TeamOps sent-message observation evidence before terminal closure review",),
        )
    if len(required_terminal_evidence_refs) < 8:
        return (
            "blocked",
            "AwaitingEvidence",
            "Unknown",
            ("terminal_closure_review_evidence_missing",),
            ("bind all required TeamOps terminal review evidence refs before closure review",),
        )
    return ("passed", "SolvedVerified", "Pass", (), ())


def _derive_required_terminal_evidence_refs(receipt: Mapping[str, Any]) -> tuple[str, ...]:
    refs = (
        str(receipt.get("source_send_execution_receipt_ref", "")),
        str(receipt.get("provider_observation_receipt_ref", "")),
        str(receipt.get("send_execution_ref", "")),
        str(receipt.get("dispatch_receipt_ref", "")),
        str(receipt.get("provider_message_ref", "")),
        str(receipt.get("first_observation_ref", "")),
        str(receipt.get("second_observation_ref", "")),
        str(receipt.get("replay_ref", "")),
        *tuple(str(ref) for ref in receipt.get("evidence_refs", ()) if isinstance(ref, str)),
    )
    return _clean_evidence_refs(refs)


def _review_packet_hash(receipt: Mapping[str, Any], evidence_refs: Sequence[str]) -> str:
    material = {
        "source_receipt_id": str(receipt.get("receipt_id", "")),
        "provider_observation_receipt_id": str(receipt.get("provider_observation_receipt_id", "")),
        "provider_message_hash": str(receipt.get("provider_message_hash", "")),
        "first_observation_hash": str(receipt.get("first_observation_hash", "")),
        "second_observation_hash": str(receipt.get("second_observation_hash", "")),
        "replay_hash": str(receipt.get("replay_hash", "")),
        "evidence_refs": list(evidence_refs),
    }
    return hashlib.sha256(json.dumps(material, sort_keys=True).encode("utf-8")).hexdigest()


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


def _receipt_id(
    *,
    sent_message_observation_receipt_path: Path,
    source_sent_message_observation_receipt_id: str,
    status: str,
    evidence_refs: Sequence[str],
) -> str:
    material = {
        "source_ref": _artifact_ref(sent_message_observation_receipt_path),
        "source_sent_message_observation_receipt_id": source_sent_message_observation_receipt_id,
        "provider_observation_receipt_id": str(
            _load_json_object(sent_message_observation_receipt_path).get("provider_observation_receipt_id", "")
        ),
        "status": status,
        "evidence_refs": list(evidence_refs),
    }
    digest = hashlib.sha256(json.dumps(material, sort_keys=True).encode("utf-8")).hexdigest()
    return f"teamops-shared-inbox-terminal-closure-review-packet-{digest[:16]}"


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
            raise ValueError(f"TeamOps terminal closure review packet contains secret marker: {marker}")


def _validate_packet_against_schema(
    packet: TeamOpsSharedInboxTerminalClosureReviewPacket,
    schema_path: Path,
) -> None:
    schema = _load_schema(schema_path)
    errors = _validate_schema_instance(schema, packet.as_dict())
    if errors:
        raise RuntimeError(f"TeamOps terminal closure review packet schema validation failed: {errors}")


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse TeamOps terminal closure review packet arguments."""

    parser = argparse.ArgumentParser(description="Produce TeamOps terminal closure review packet.")
    parser.add_argument("--sent-message-observation-receipt", default=str(DEFAULT_SENT_MESSAGE_OBSERVATION_RECEIPT))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--reviewed-at")
    parser.add_argument("--evidence-ref", action="append", default=[])
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for TeamOps terminal closure review packet production."""

    args = parse_args(argv)
    try:
        packet = produce_team_ops_shared_inbox_terminal_closure_review_packet(
            sent_message_observation_receipt_path=Path(args.sent_message_observation_receipt),
            schema_path=Path(args.schema),
            reviewed_at=args.reviewed_at,
            evidence_refs=tuple(str(ref) for ref in args.evidence_ref),
        )
        write_team_ops_shared_inbox_terminal_closure_review_packet(packet, Path(args.output))
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
            print(f"TeamOps terminal closure review packet failed: {exc}")
        return 1
    if args.json:
        print(json.dumps(packet.as_dict(), indent=2, sort_keys=True))
    else:
        print(f"TeamOps terminal closure review packet written: {packet.receipt_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
