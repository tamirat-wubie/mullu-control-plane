#!/usr/bin/env python3
"""Produce a TeamOps shared inbox provider observation receipt.

Purpose: bind an operator-observed read-only provider response to the TeamOps
live-probe chain without calling a mailbox connector or serializing raw payload.
Governance scope: TeamOps shared inbox live evidence, provider-observation
witnessing, redaction, read-only bounds, and no-effect producer separation.
Dependencies: schemas/team_ops_shared_inbox_provider_observation_receipt.schema.json
and scripts.validate_team_ops_shared_inbox_live_probe_operator_input_request.
Invariants:
  - This producer never calls Gmail, Teams, Slack, Microsoft Graph, or any
    external mailbox provider.
  - Passed receipts require admitted operator input, a redacted provider
    receipt ref, raw-response digest, redacted-response digest, and bounded
    observed message count.
  - Raw provider payload, mailbox content, secret values, and query text are not
    serialized.
  - External writes, sends, and provider mutations remain false.
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
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.produce_team_ops_shared_inbox_operator_handoff import SECRET_VALUE_MARKERS  # noqa: E402
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402
from scripts.validate_team_ops_shared_inbox_live_probe_operator_input_request import (  # noqa: E402
    DEFAULT_REQUEST,
    validate_team_ops_live_probe_operator_input_request,
)


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "team_ops_shared_inbox_provider_observation_receipt.schema.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "team_ops_shared_inbox_provider_observation_receipt.json"
SHA256_HEX_PATTERN = re.compile(r"^[0-9a-f]{64}$")
VALIDATION_COMMANDS = (
    "python scripts/validate_team_ops_shared_inbox_provider_observation_receipt.py --require-ready",
    "python scripts/validate_schemas.py --strict",
)


@dataclass(frozen=True, slots=True)
class TeamOpsSharedInboxProviderObservationReceipt:
    """Receipt for one operator-observed read-only provider response."""

    receipt_id: str
    schema_version: int
    workflow_id: str
    source_operator_input_request_ref: str
    source_authority_id: str
    operator_input_request_valid: bool
    operator_input_probe_allowed: bool
    status: str
    solver_outcome: str
    proof_state: str
    checked_at: str
    connector_id: str
    provider_operation: str
    query_hash: str
    max_message_count: int
    observed_message_count: int
    provider_receipt_ref: str
    provider_response_digest: str
    redacted_response_digest: str
    provider_call_observed_by_operator: bool
    provider_call_performed_by_producer: bool
    external_mailbox_write_performed: bool
    external_message_sent: bool
    provider_mutation_performed: bool
    raw_provider_payload_serialized: bool
    no_secret_values_serialized: bool
    read_only_observation_bound: bool
    blocked_until: tuple[str, ...]
    recovery_actions: tuple[str, ...]
    validation_commands: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-ready provider observation receipt."""

        payload = asdict(self)
        payload["blocked_until"] = list(self.blocked_until)
        payload["recovery_actions"] = list(self.recovery_actions)
        payload["validation_commands"] = list(self.validation_commands)
        return payload


def produce_team_ops_shared_inbox_provider_observation_receipt(
    *,
    operator_input_path: Path = DEFAULT_REQUEST,
    schema_path: Path = DEFAULT_SCHEMA,
    checked_at: str | None = None,
    connector_id: str = "gmail",
    provider_operation: str = "email.search",
    provider_receipt_ref: str = "",
    provider_response_digest: str = "",
    redacted_response_digest: str = "",
    observed_message_count: int = 0,
) -> TeamOpsSharedInboxProviderObservationReceipt:
    """Produce a TeamOps provider observation receipt from redacted evidence."""

    request = _load_json_object(operator_input_path)
    validation = validate_team_ops_live_probe_operator_input_request(request_path=operator_input_path)
    allowed_probe = request.get("allowed_probe_summary", {}) if isinstance(request, dict) else {}
    max_message_count = _bounded_max_message_count(allowed_probe.get("max_message_count", 1))
    query_hash = _hash_text(str(allowed_probe.get("query", "")))
    clean_provider_receipt_ref = _clean_provider_receipt_ref(provider_receipt_ref)
    status, solver_outcome, proof_state, blocked_until, recovery_actions = _derive_status(
        operator_input_valid=validation.valid,
        probe_allowed=validation.probe_allowed,
        provider_receipt_ref=clean_provider_receipt_ref,
        provider_response_digest=provider_response_digest,
        redacted_response_digest=redacted_response_digest,
        observed_message_count=observed_message_count,
        max_message_count=max_message_count,
    )
    receipt = TeamOpsSharedInboxProviderObservationReceipt(
        receipt_id=_receipt_id(
            operator_input_path=operator_input_path,
            source_authority_id=str(request.get("authority_id", "")),
            provider_receipt_ref=clean_provider_receipt_ref,
            provider_response_digest=provider_response_digest,
            redacted_response_digest=redacted_response_digest,
            status=status,
        ),
        schema_version=1,
        workflow_id="team_ops.shared_inbox_triage",
        source_operator_input_request_ref=_artifact_ref(operator_input_path),
        source_authority_id=str(request.get("authority_id", "")),
        operator_input_request_valid=validation.valid,
        operator_input_probe_allowed=validation.probe_allowed,
        status=status,
        solver_outcome=solver_outcome,
        proof_state=proof_state,
        checked_at=checked_at or datetime.now(UTC).replace(microsecond=0).isoformat(),
        connector_id=connector_id if validation.probe_allowed else "",
        provider_operation=provider_operation if validation.probe_allowed else "",
        query_hash=query_hash,
        max_message_count=max_message_count,
        observed_message_count=observed_message_count,
        provider_receipt_ref=clean_provider_receipt_ref,
        provider_response_digest=provider_response_digest,
        redacted_response_digest=redacted_response_digest,
        provider_call_observed_by_operator=status == "passed",
        provider_call_performed_by_producer=False,
        external_mailbox_write_performed=False,
        external_message_sent=False,
        provider_mutation_performed=False,
        raw_provider_payload_serialized=False,
        no_secret_values_serialized=True,
        read_only_observation_bound=status == "passed",
        blocked_until=blocked_until,
        recovery_actions=recovery_actions,
        validation_commands=VALIDATION_COMMANDS,
    )
    _assert_redacted(receipt.as_dict())
    _validate_receipt_against_schema(receipt, schema_path)
    return receipt


def write_team_ops_shared_inbox_provider_observation_receipt(
    receipt: TeamOpsSharedInboxProviderObservationReceipt,
    output_path: Path,
) -> Path:
    """Write one TeamOps provider observation receipt."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(receipt.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _derive_status(
    *,
    operator_input_valid: bool,
    probe_allowed: bool,
    provider_receipt_ref: str,
    provider_response_digest: str,
    redacted_response_digest: str,
    observed_message_count: int,
    max_message_count: int,
) -> tuple[str, str, str, tuple[str, ...], tuple[str, ...]]:
    if not operator_input_valid:
        return (
            "failed",
            "GovernanceBlocked",
            "Fail",
            ("operator_input_request_invalid",),
            ("regenerate and validate the TeamOps live-probe operator input request",),
        )
    if not probe_allowed:
        return (
            "blocked",
            "AwaitingEvidence",
            "Unknown",
            ("operator_input_request_not_ready",),
            ("close TeamOps live-probe operator inputs before binding provider observation evidence",),
        )
    if observed_message_count > max_message_count:
        return (
            "failed",
            "GovernanceBlocked",
            "Fail",
            ("observed_message_count_exceeds_authority",),
            ("rerun the read-only provider observation with the authority-bounded max_message_count",),
        )
    missing: list[str] = []
    if not provider_receipt_ref:
        missing.append("provider_receipt_ref_missing")
    if not SHA256_HEX_PATTERN.fullmatch(provider_response_digest):
        missing.append("provider_response_digest_missing_or_invalid")
    if not SHA256_HEX_PATTERN.fullmatch(redacted_response_digest):
        missing.append("redacted_response_digest_missing_or_invalid")
    if missing:
        return (
            "blocked",
            "AwaitingEvidence",
            "Unknown",
            tuple(missing),
            ("bind redacted read-only provider observation evidence, then regenerate this receipt",),
        )
    return ("passed", "SolvedVerified", "Pass", (), ())


def _load_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _clean_provider_receipt_ref(value: str) -> str:
    ref = str(value).strip()
    if not ref:
        return ""
    _assert_redacted({"provider_receipt_ref": ref})
    return ref


def _bounded_max_message_count(value: Any) -> int:
    try:
        count = int(value)
    except (TypeError, ValueError):
        return 1
    return max(1, min(count, 50))


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _receipt_id(
    *,
    operator_input_path: Path,
    source_authority_id: str,
    provider_receipt_ref: str,
    provider_response_digest: str,
    redacted_response_digest: str,
    status: str,
) -> str:
    material = {
        "operator_input_ref": _artifact_ref(operator_input_path),
        "source_authority_id": source_authority_id,
        "provider_receipt_ref": provider_receipt_ref,
        "provider_response_digest": provider_response_digest,
        "redacted_response_digest": redacted_response_digest,
        "status": status,
    }
    digest = hashlib.sha256(json.dumps(material, sort_keys=True).encode("utf-8")).hexdigest()
    return f"teamops-shared-inbox-provider-observation-receipt-{digest[:16]}"


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
            raise ValueError(f"TeamOps provider observation receipt contains secret marker: {marker}")
    if "query" in payload:
        raise ValueError("TeamOps provider observation receipt must not serialize raw query")


def _validate_receipt_against_schema(
    receipt: TeamOpsSharedInboxProviderObservationReceipt,
    schema_path: Path,
) -> None:
    schema = _load_schema(schema_path)
    errors = _validate_schema_instance(schema, receipt.as_dict())
    if errors:
        raise RuntimeError(f"TeamOps provider observation receipt schema validation failed: {errors}")


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse TeamOps provider observation receipt arguments."""

    parser = argparse.ArgumentParser(description="Produce TeamOps shared inbox provider observation receipt.")
    parser.add_argument("--operator-input", default=str(DEFAULT_REQUEST))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--checked-at")
    parser.add_argument("--connector-id", default="gmail")
    parser.add_argument("--provider-operation", default="email.search")
    parser.add_argument("--provider-receipt-ref", default="")
    parser.add_argument("--provider-response-digest", default="")
    parser.add_argument("--redacted-response-digest", default="")
    parser.add_argument("--observed-message-count", type=int, default=0)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for TeamOps provider observation receipt production."""

    args = parse_args(argv)
    try:
        receipt = produce_team_ops_shared_inbox_provider_observation_receipt(
            operator_input_path=Path(args.operator_input),
            schema_path=Path(args.schema),
            checked_at=args.checked_at,
            connector_id=str(args.connector_id),
            provider_operation=str(args.provider_operation),
            provider_receipt_ref=str(args.provider_receipt_ref),
            provider_response_digest=str(args.provider_response_digest),
            redacted_response_digest=str(args.redacted_response_digest),
            observed_message_count=int(args.observed_message_count),
        )
        write_team_ops_shared_inbox_provider_observation_receipt(receipt, Path(args.output))
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
            print(f"TeamOps provider observation receipt failed: {exc}")
        return 1
    if args.json:
        print(json.dumps(receipt.as_dict(), indent=2, sort_keys=True))
    else:
        print(f"TeamOps provider observation receipt written: {receipt.receipt_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
