#!/usr/bin/env python3
"""Produce a TeamOps sent-message observation and replay receipt.

Purpose: bind ready send-execution evidence to two redacted sent-message
observations and deterministic replay evidence without reading provider state.
Governance scope: TeamOps external-send closure evidence, replay binding,
redaction, duplicate-action protection, and no-local-provider-call enforcement.
Dependencies: schemas/team_ops_shared_inbox_sent_message_observation_receipt.schema.json
and scripts.validate_team_ops_shared_inbox_send_execution_receipt.
Invariants:
  - Only ready send-execution receipts can close sent-message observation.
  - Provider state observations are refs and hashes only; raw payloads are rejected.
  - This producer records supplied observation evidence only; it never calls a provider.
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
from scripts.produce_team_ops_shared_inbox_send_execution_receipt import (  # noqa: E402
    DEFAULT_OUTPUT as DEFAULT_SEND_EXECUTION_RECEIPT,
    SHA256_HEX_PATTERN,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402
from scripts.validate_team_ops_shared_inbox_send_execution_receipt import (  # noqa: E402
    validate_team_ops_shared_inbox_send_execution_receipt,
)


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "team_ops_shared_inbox_sent_message_observation_receipt.schema.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "team_ops_shared_inbox_sent_message_observation_receipt.json"
VALIDATION_COMMANDS = (
    "python scripts/validate_team_ops_shared_inbox_sent_message_observation_receipt.py --require-ready",
    "python scripts/validate_schemas.py --strict",
)


@dataclass(frozen=True, slots=True)
class TeamOpsSharedInboxSentMessageObservationReceipt:
    """Receipt for redacted sent-message observation and replay evidence."""

    receipt_id: str
    schema_version: int
    workflow_id: str
    source_send_execution_receipt_ref: str
    source_send_execution_receipt_id: str
    send_execution_receipt_valid: bool
    send_execution_receipt_ready: bool
    status: str
    solver_outcome: str
    proof_state: str
    observed_at: str
    send_execution_ref: str
    dispatch_receipt_ref: str
    provider_message_ref: str
    provider_message_hash: str
    sent_message_observation_state: str
    sent_message_observation_ready: bool
    first_observation_ref: str
    first_observation_hash: str
    second_observation_ref: str
    second_observation_hash: str
    observation_count: int
    provider_state_consistent: bool
    provider_message_hash_matches_execution: bool
    duplicate_absence_observed: bool
    replay_ref: str
    replay_hash: str
    deterministic_replay_observed: bool
    workflow_closure_ready: bool
    observation_performed_by_producer: bool
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
    terminal_closure_required: bool
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


def produce_team_ops_shared_inbox_sent_message_observation_receipt(
    *,
    send_execution_receipt_path: Path = DEFAULT_SEND_EXECUTION_RECEIPT,
    schema_path: Path = DEFAULT_SCHEMA,
    observed_at: str | None = None,
    first_observation_ref: str = "",
    first_observation_hash: str = "",
    second_observation_ref: str = "",
    second_observation_hash: str = "",
    duplicate_absence_observed: bool = False,
    replay_ref: str = "",
    replay_hash: str = "",
    deterministic_replay_observed: bool = False,
    evidence_refs: Sequence[str] = (),
) -> TeamOpsSharedInboxSentMessageObservationReceipt:
    """Produce a TeamOps sent-message observation receipt."""

    execution_validation = validate_team_ops_shared_inbox_send_execution_receipt(
        receipt_path=send_execution_receipt_path,
        require_ready=False,
    )
    execution_receipt = _load_json_object(send_execution_receipt_path)
    clean_first_observation_ref = _clean_text_ref(first_observation_ref, "first_observation_ref")
    clean_first_observation_hash = _clean_hash(first_observation_hash, "first_observation_hash")
    clean_second_observation_ref = _clean_text_ref(second_observation_ref, "second_observation_ref")
    clean_second_observation_hash = _clean_hash(second_observation_hash, "second_observation_hash")
    clean_replay_ref = _clean_text_ref(replay_ref, "replay_ref")
    clean_replay_hash = _clean_hash(replay_hash, "replay_hash")
    source_ready = execution_validation.ready
    provider_message_hash = str(execution_receipt.get("provider_message_hash", "")) if source_ready else ""
    hash_matches = (
        bool(provider_message_hash)
        and clean_first_observation_hash == provider_message_hash
        and clean_second_observation_hash == provider_message_hash
    )
    observation_count = sum(
        1
        for ref, digest in (
            (clean_first_observation_ref, clean_first_observation_hash),
            (clean_second_observation_ref, clean_second_observation_hash),
        )
        if ref and digest
    )
    provider_state_consistent = hash_matches and observation_count >= 2
    safe_evidence_refs = tuple(
        _clean_evidence_refs(
            (
                clean_first_observation_ref,
                clean_second_observation_ref,
                clean_replay_ref,
                *evidence_refs,
            )
        )
    )
    status, solver_outcome, proof_state, blocked_until, recovery_actions = _derive_status(
        send_execution_receipt_valid=execution_validation.valid,
        send_execution_receipt_ready=execution_validation.ready,
        observation_count=observation_count,
        provider_message_hash=provider_message_hash,
        provider_state_consistent=provider_state_consistent,
        provider_message_hash_matches_execution=hash_matches,
        duplicate_absence_observed=duplicate_absence_observed,
        replay_ref=clean_replay_ref,
        replay_hash=clean_replay_hash,
        deterministic_replay_observed=deterministic_replay_observed,
        evidence_refs=safe_evidence_refs,
    )
    passed = status == "passed"
    receipt = TeamOpsSharedInboxSentMessageObservationReceipt(
        receipt_id=_receipt_id(
            send_execution_receipt_path=send_execution_receipt_path,
            source_send_execution_receipt_id=str(execution_receipt.get("receipt_id", "")),
            first_observation_ref=clean_first_observation_ref,
            second_observation_ref=clean_second_observation_ref,
            replay_ref=clean_replay_ref,
            status=status,
        ),
        schema_version=1,
        workflow_id="team_ops.shared_inbox_triage",
        source_send_execution_receipt_ref=_artifact_ref(send_execution_receipt_path),
        source_send_execution_receipt_id=str(execution_receipt.get("receipt_id", "")),
        send_execution_receipt_valid=execution_validation.valid,
        send_execution_receipt_ready=execution_validation.ready,
        status=status,
        solver_outcome=solver_outcome,
        proof_state=proof_state,
        observed_at=observed_at or datetime.now(UTC).replace(microsecond=0).isoformat(),
        send_execution_ref=str(execution_receipt.get("send_execution_ref", "")) if source_ready else "",
        dispatch_receipt_ref=str(execution_receipt.get("dispatch_receipt_ref", "")) if source_ready else "",
        provider_message_ref=str(execution_receipt.get("provider_message_ref", "")) if source_ready else "",
        provider_message_hash=provider_message_hash if source_ready else "",
        sent_message_observation_state=_observation_state(status),
        sent_message_observation_ready=passed,
        first_observation_ref=clean_first_observation_ref if passed else "",
        first_observation_hash=clean_first_observation_hash if passed else "",
        second_observation_ref=clean_second_observation_ref if passed else "",
        second_observation_hash=clean_second_observation_hash if passed else "",
        observation_count=observation_count if source_ready else 0,
        provider_state_consistent=provider_state_consistent if source_ready else False,
        provider_message_hash_matches_execution=hash_matches if source_ready else False,
        duplicate_absence_observed=duplicate_absence_observed if source_ready else False,
        replay_ref=clean_replay_ref if passed else "",
        replay_hash=clean_replay_hash if passed else "",
        deterministic_replay_observed=deterministic_replay_observed if source_ready else False,
        workflow_closure_ready=passed,
        observation_performed_by_producer=False,
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
        terminal_closure_required=True,
        evidence_refs=safe_evidence_refs if passed else (),
        blocked_until=blocked_until,
        recovery_actions=recovery_actions,
        validation_commands=VALIDATION_COMMANDS,
    )
    _assert_redacted(receipt.as_dict())
    _validate_receipt_against_schema(receipt, schema_path)
    return receipt


def write_team_ops_shared_inbox_sent_message_observation_receipt(
    receipt: TeamOpsSharedInboxSentMessageObservationReceipt,
    output_path: Path,
) -> Path:
    """Write one TeamOps sent-message observation receipt."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(receipt.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _derive_status(
    *,
    send_execution_receipt_valid: bool,
    send_execution_receipt_ready: bool,
    observation_count: int,
    provider_message_hash: str,
    provider_state_consistent: bool,
    provider_message_hash_matches_execution: bool,
    duplicate_absence_observed: bool,
    replay_ref: str,
    replay_hash: str,
    deterministic_replay_observed: bool,
    evidence_refs: Sequence[str],
) -> tuple[str, str, str, tuple[str, ...], tuple[str, ...]]:
    if not send_execution_receipt_valid:
        return (
            "failed",
            "GovernanceBlocked",
            "Fail",
            ("send_execution_receipt_invalid",),
            ("regenerate and validate the TeamOps send-execution receipt",),
        )
    if not send_execution_receipt_ready:
        return (
            "blocked",
            "AwaitingEvidence",
            "Unknown",
            ("send_execution_receipt_not_ready",),
            ("record ready TeamOps send-execution evidence before observing sent-message closure",),
        )
    if (
        observation_count < 2
        or not provider_message_hash
        or not replay_ref
        or not replay_hash
        or len(evidence_refs) < 4
    ):
        return (
            "blocked",
            "AwaitingEvidence",
            "Unknown",
            ("sent_message_observation_or_replay_evidence_missing",),
            ("bind two redacted sent-message observations and deterministic replay evidence",),
        )
    if not provider_message_hash_matches_execution or not provider_state_consistent:
        return (
            "failed",
            "GovernanceBlocked",
            "Fail",
            ("sent_message_observation_hash_mismatch",),
            ("reconcile provider observation hashes with the send-execution provider message hash",),
        )
    if not duplicate_absence_observed or not deterministic_replay_observed:
        return (
            "blocked",
            "AwaitingEvidence",
            "Unknown",
            ("duplicate_absence_or_replay_not_observed",),
            ("observe duplicate absence and deterministic replay before closure",),
        )
    return ("passed", "SolvedVerified", "Pass", (), ())


def _observation_state(status: str) -> str:
    if status == "passed":
        return "observed"
    if status == "failed":
        return "inconsistent"
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
    send_execution_receipt_path: Path,
    source_send_execution_receipt_id: str,
    first_observation_ref: str,
    second_observation_ref: str,
    replay_ref: str,
    status: str,
) -> str:
    material = {
        "source_ref": _artifact_ref(send_execution_receipt_path),
        "source_send_execution_receipt_id": source_send_execution_receipt_id,
        "first_observation_ref": first_observation_ref,
        "second_observation_ref": second_observation_ref,
        "replay_ref": replay_ref,
        "status": status,
    }
    digest = hashlib.sha256(json.dumps(material, sort_keys=True).encode("utf-8")).hexdigest()
    return f"teamops-shared-inbox-sent-message-observation-receipt-{digest[:16]}"


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
            raise ValueError(f"TeamOps sent-message observation receipt contains secret marker: {marker}")


def _validate_receipt_against_schema(
    receipt: TeamOpsSharedInboxSentMessageObservationReceipt,
    schema_path: Path,
) -> None:
    schema = _load_schema(schema_path)
    errors = _validate_schema_instance(schema, receipt.as_dict())
    if errors:
        raise RuntimeError(f"TeamOps sent-message observation receipt schema validation failed: {errors}")


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse TeamOps sent-message observation receipt arguments."""

    parser = argparse.ArgumentParser(description="Produce TeamOps sent-message observation receipt.")
    parser.add_argument("--send-execution-receipt", default=str(DEFAULT_SEND_EXECUTION_RECEIPT))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--observed-at")
    parser.add_argument("--first-observation-ref", default="")
    parser.add_argument("--first-observation-hash", default="")
    parser.add_argument("--second-observation-ref", default="")
    parser.add_argument("--second-observation-hash", default="")
    parser.add_argument("--duplicate-absence-observed", action="store_true")
    parser.add_argument("--replay-ref", default="")
    parser.add_argument("--replay-hash", default="")
    parser.add_argument("--deterministic-replay-observed", action="store_true")
    parser.add_argument("--evidence-ref", action="append", default=[])
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for TeamOps sent-message observation production."""

    args = parse_args(argv)
    try:
        receipt = produce_team_ops_shared_inbox_sent_message_observation_receipt(
            send_execution_receipt_path=Path(args.send_execution_receipt),
            schema_path=Path(args.schema),
            observed_at=args.observed_at,
            first_observation_ref=str(args.first_observation_ref),
            first_observation_hash=str(args.first_observation_hash),
            second_observation_ref=str(args.second_observation_ref),
            second_observation_hash=str(args.second_observation_hash),
            duplicate_absence_observed=bool(args.duplicate_absence_observed),
            replay_ref=str(args.replay_ref),
            replay_hash=str(args.replay_hash),
            deterministic_replay_observed=bool(args.deterministic_replay_observed),
            evidence_refs=tuple(str(ref) for ref in args.evidence_ref),
        )
        write_team_ops_shared_inbox_sent_message_observation_receipt(receipt, Path(args.output))
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
            print(f"TeamOps sent-message observation receipt failed: {exc}")
        return 1
    if args.json:
        print(json.dumps(receipt.as_dict(), indent=2, sort_keys=True))
    else:
        print(f"TeamOps sent-message observation receipt written: {receipt.receipt_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
