#!/usr/bin/env python3
"""Produce a TeamOps shared inbox read-only live-probe receipt.

Purpose: bind a TeamOps live-probe operator input request to redacted
observation evidence without running a mailbox connector.
Governance scope: TeamOps shared inbox read-only observation, operator-input
readiness, evidence redaction, and external-effect separation.
Dependencies: schemas/team_ops_shared_inbox_live_probe_receipt.schema.json and
scripts.validate_team_ops_shared_inbox_live_probe_operator_input_request.
Invariants:
  - This producer never calls Gmail, Teams, Slack, Microsoft Graph, or any
    external mailbox provider.
  - Ready receipts require an admitted operator-input request and redacted
    observation evidence.
  - Raw query text is hashed before serialization.
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
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.produce_team_ops_shared_inbox_operator_handoff import SECRET_VALUE_MARKERS  # noqa: E402
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402
from scripts.validate_team_ops_shared_inbox_live_probe_operator_input_request import (  # noqa: E402
    DEFAULT_REQUEST,
    validate_team_ops_live_probe_operator_input_request,
)


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "team_ops_shared_inbox_live_probe_receipt.schema.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "team_ops_shared_inbox_live_probe_receipt.json"
SHA256_HEX_PATTERN = re.compile(r"^[0-9a-f]{64}$")
VALIDATION_COMMANDS = (
    "python scripts/validate_team_ops_shared_inbox_live_probe_receipt.py --require-ready",
    "python scripts/validate_schemas.py --strict",
)


@dataclass(frozen=True, slots=True)
class TeamOpsSharedInboxLiveProbeReceipt:
    """Receipt for one TeamOps shared inbox read-only live-probe boundary."""

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
    response_digest: str
    evidence_refs: tuple[str, ...]
    no_secret_values_serialized: bool
    live_probe_observation_bound: bool
    external_provider_call_performed_by_producer: bool
    external_mailbox_write_performed: bool
    external_message_sent: bool
    provider_mutation_performed: bool
    forbidden_effects_observed: bool
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


def produce_team_ops_shared_inbox_live_probe_receipt(
    *,
    operator_input_path: Path = DEFAULT_REQUEST,
    schema_path: Path = DEFAULT_SCHEMA,
    checked_at: str | None = None,
    connector_id: str = "gmail",
    provider_operation: str = "email.search",
    response_digest: str = "",
    observed_message_count: int = 0,
    evidence_refs: Sequence[str] = (),
) -> TeamOpsSharedInboxLiveProbeReceipt:
    """Produce a read-only TeamOps shared inbox live-probe receipt."""

    request = _load_json_object(operator_input_path)
    validation = validate_team_ops_live_probe_operator_input_request(request_path=operator_input_path)
    summary = request.get("allowed_probe_summary", {}) if isinstance(request, dict) else {}
    query_hash = _hash_text(str(summary.get("query", "")))
    max_message_count = _bounded_max_message_count(summary.get("max_message_count", 1))
    safe_evidence_refs = tuple(_clean_evidence_refs(evidence_refs))
    evidence_supplied = bool(response_digest) or bool(safe_evidence_refs)
    has_redacted_observation = (
        bool(response_digest)
        and SHA256_HEX_PATTERN.fullmatch(response_digest) is not None
        and bool(safe_evidence_refs)
    )
    status, solver_outcome, proof_state, blocked_until, recovery_actions = _derive_status(
        operator_input_valid=validation.valid,
        probe_allowed=validation.probe_allowed,
        has_redacted_observation=has_redacted_observation,
        observed_message_count=observed_message_count,
        max_message_count=max_message_count,
        response_digest=response_digest,
        evidence_supplied=evidence_supplied,
    )
    receipt = TeamOpsSharedInboxLiveProbeReceipt(
        receipt_id=_receipt_id(
            operator_input_path=operator_input_path,
            source_authority_id=str(request.get("authority_id", "")),
            response_digest=response_digest,
            evidence_refs=safe_evidence_refs,
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
        response_digest=response_digest,
        evidence_refs=safe_evidence_refs,
        no_secret_values_serialized=True,
        live_probe_observation_bound=status == "passed",
        external_provider_call_performed_by_producer=False,
        external_mailbox_write_performed=False,
        external_message_sent=False,
        provider_mutation_performed=False,
        forbidden_effects_observed=False,
        blocked_until=blocked_until,
        recovery_actions=recovery_actions,
        validation_commands=VALIDATION_COMMANDS,
    )
    _assert_redacted(receipt.as_dict())
    _validate_receipt_against_schema(receipt, schema_path)
    return receipt


def write_team_ops_shared_inbox_live_probe_receipt(
    receipt: TeamOpsSharedInboxLiveProbeReceipt,
    output_path: Path,
) -> Path:
    """Write one TeamOps shared inbox live-probe receipt."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(receipt.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _derive_status(
    *,
    operator_input_valid: bool,
    probe_allowed: bool,
    has_redacted_observation: bool,
    observed_message_count: int,
    max_message_count: int,
    response_digest: str,
    evidence_supplied: bool,
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
            ("close TeamOps live-probe operator inputs before binding observation evidence",),
        )
    if observed_message_count > max_message_count:
        return (
            "failed",
            "GovernanceBlocked",
            "Fail",
            ("observed_message_count_exceeds_authority",),
            ("rerun the read-only probe with the authority-bounded max_message_count",),
        )
    if evidence_supplied and not SHA256_HEX_PATTERN.fullmatch(response_digest):
        return (
            "failed",
            "GovernanceBlocked",
            "Fail",
            ("response_digest_invalid",),
            ("supply a lowercase SHA-256 hex response digest for redacted observation evidence",),
        )
    if not has_redacted_observation:
        return (
            "blocked",
            "AwaitingEvidence",
            "Unknown",
            ("redacted_live_probe_observation_missing",),
            ("run the approved read-only live probe outside this producer and bind redacted evidence refs",),
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
    response_digest: str,
    evidence_refs: Sequence[str],
    status: str,
) -> str:
    material = {
        "operator_input_ref": _artifact_ref(operator_input_path),
        "source_authority_id": source_authority_id,
        "response_digest": response_digest,
        "evidence_refs": list(evidence_refs),
        "status": status,
    }
    digest = hashlib.sha256(json.dumps(material, sort_keys=True).encode("utf-8")).hexdigest()
    return f"teamops-shared-inbox-live-probe-receipt-{digest[:16]}"


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
            raise ValueError(f"TeamOps live-probe receipt contains secret marker: {marker}")


def _validate_receipt_against_schema(
    receipt: TeamOpsSharedInboxLiveProbeReceipt,
    schema_path: Path,
) -> None:
    schema = _load_schema(schema_path)
    errors = _validate_schema_instance(schema, receipt.as_dict())
    if errors:
        raise RuntimeError(f"TeamOps live-probe receipt schema validation failed: {errors}")


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse TeamOps shared inbox live-probe receipt arguments."""

    parser = argparse.ArgumentParser(description="Produce TeamOps shared inbox live-probe receipt.")
    parser.add_argument("--operator-input", default=str(DEFAULT_REQUEST))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--checked-at")
    parser.add_argument("--connector-id", default="gmail")
    parser.add_argument("--provider-operation", default="email.search")
    parser.add_argument("--response-digest", default="")
    parser.add_argument("--observed-message-count", type=int, default=0)
    parser.add_argument("--evidence-ref", action="append", default=[])
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for TeamOps shared inbox live-probe receipt production."""

    args = parse_args(argv)
    try:
        receipt = produce_team_ops_shared_inbox_live_probe_receipt(
            operator_input_path=Path(args.operator_input),
            schema_path=Path(args.schema),
            checked_at=args.checked_at,
            connector_id=str(args.connector_id),
            provider_operation=str(args.provider_operation),
            response_digest=str(args.response_digest),
            observed_message_count=int(args.observed_message_count),
            evidence_refs=tuple(str(ref) for ref in args.evidence_ref),
        )
        write_team_ops_shared_inbox_live_probe_receipt(receipt, Path(args.output))
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
            print(f"TeamOps shared inbox live-probe receipt failed: {exc}")
        return 1
    if args.json:
        print(json.dumps(receipt.as_dict(), indent=2, sort_keys=True))
    else:
        print(f"TeamOps shared inbox live-probe receipt written: {receipt.receipt_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
