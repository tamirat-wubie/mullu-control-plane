#!/usr/bin/env python3
"""Validate TeamOps shared inbox read-only live-probe receipts.

Purpose: reject malformed, effect-bearing, or unready TeamOps shared inbox
live-probe receipts before downstream TeamOps workflow promotion.
Governance scope: TeamOps read-only observation evidence, operator-input
binding, external-effect rejection, redaction, and readiness gating.
Dependencies: schemas/team_ops_shared_inbox_live_probe_receipt.schema.json.
Invariants:
  - Ready receipts require admitted operator-input authority and redacted
    observation evidence.
  - Raw query text must not be serialized; only query_hash is permitted.
  - No mailbox write, message send, provider mutation, or producer-side
    connector call may be claimed.
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

from scripts.produce_team_ops_shared_inbox_live_probe_receipt import DEFAULT_OUTPUT  # noqa: E402
from scripts.produce_team_ops_shared_inbox_operator_handoff import SECRET_VALUE_MARKERS  # noqa: E402
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "team_ops_shared_inbox_live_probe_receipt.schema.json"
DEFAULT_VALIDATION_OUTPUT = REPO_ROOT / ".change_assurance" / "team_ops_shared_inbox_live_probe_receipt_validation.json"
RECEIPT_ID_PATTERN = re.compile(r"^teamops-shared-inbox-live-probe-receipt-[0-9a-f]{16}$")
SHA256_HEX_PATTERN = re.compile(r"^[0-9a-f]{64}$")
READ_ONLY_OPERATIONS = {"email.search", "messaging.thread.search"}


@dataclass(frozen=True, slots=True)
class TeamOpsSharedInboxLiveProbeReceiptValidation:
    """Validation result for one TeamOps shared inbox live-probe receipt."""

    valid: bool
    ready: bool
    receipt_path: str
    schema_path: str
    receipt_id: str
    status: str
    solver_outcome: str
    proof_state: str
    operator_input_probe_allowed: bool
    provider_observation_receipt_valid: bool
    blocked_until: tuple[str, ...]
    errors: tuple[str, ...]
    next_action: str

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-ready validation receipt."""

        payload = asdict(self)
        payload["blocked_until"] = list(self.blocked_until)
        payload["errors"] = list(self.errors)
        return payload


def validate_team_ops_shared_inbox_live_probe_receipt(
    *,
    receipt_path: Path = DEFAULT_OUTPUT,
    schema_path: Path = DEFAULT_SCHEMA,
    require_ready: bool = False,
) -> TeamOpsSharedInboxLiveProbeReceiptValidation:
    """Validate one TeamOps shared inbox live-probe receipt."""

    errors: list[str] = []
    try:
        schema = _load_schema(schema_path)
    except OSError:
        schema = {}
        errors.append("TeamOps shared inbox live-probe receipt schema file missing")
    receipt = _load_json_object(receipt_path, "TeamOps shared inbox live-probe receipt", errors)
    if schema and receipt:
        errors.extend(_validate_schema_instance(schema, receipt))
        _validate_semantics(receipt, errors)
        if require_ready and not _receipt_ready(receipt):
            errors.append("TeamOps shared inbox live-probe receipt ready must be true")
    ready = not errors and _receipt_ready(receipt)
    return TeamOpsSharedInboxLiveProbeReceiptValidation(
        valid=not errors,
        ready=ready,
        receipt_path=_path_label(receipt_path),
        schema_path=_path_label(schema_path),
        receipt_id=str(receipt.get("receipt_id", "")),
        status=str(receipt.get("status", "")),
        solver_outcome=str(receipt.get("solver_outcome", "")),
        proof_state=str(receipt.get("proof_state", "")),
        operator_input_probe_allowed=receipt.get("operator_input_probe_allowed") is True,
        provider_observation_receipt_valid=receipt.get("provider_observation_receipt_valid") is True,
        blocked_until=tuple(str(item) for item in receipt.get("blocked_until", ()))
        if isinstance(receipt.get("blocked_until", ()), list)
        else (),
        errors=tuple(errors),
        next_action=_next_action(receipt),
    )


def write_team_ops_shared_inbox_live_probe_receipt_validation(
    validation: TeamOpsSharedInboxLiveProbeReceiptValidation,
    output_path: Path,
) -> Path:
    """Write one TeamOps shared inbox live-probe receipt validation."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_semantics(receipt: dict[str, Any], errors: list[str]) -> None:
    serialized = json.dumps(receipt, sort_keys=True)
    for marker in SECRET_VALUE_MARKERS:
        if marker.lower() in serialized.lower():
            errors.append(f"receipt must not serialize secret marker: {marker}")
    if "query" in receipt:
        errors.append("receipt must not serialize raw query")
    if not RECEIPT_ID_PATTERN.fullmatch(str(receipt.get("receipt_id", ""))):
        errors.append("receipt_id must match TeamOps shared inbox live-probe pattern")
    for field_name in (
        "no_secret_values_serialized",
        "external_provider_call_performed_by_producer",
        "external_mailbox_write_performed",
        "external_message_sent",
        "provider_mutation_performed",
        "forbidden_effects_observed",
    ):
        expected = True if field_name == "no_secret_values_serialized" else False
        if receipt.get(field_name) is not expected:
            errors.append(f"{field_name} must be {str(expected).lower()}")
    if not SHA256_HEX_PATTERN.fullmatch(str(receipt.get("query_hash", ""))):
        errors.append("query_hash must be lowercase SHA-256 hex")
    if receipt.get("status") == "passed":
        _validate_ready_receipt(receipt, errors)
    elif receipt.get("status") == "blocked":
        _validate_blocked_receipt(receipt, errors)
    elif receipt.get("status") == "failed":
        _validate_failed_receipt(receipt, errors)
    else:
        errors.append("status must be blocked, failed, or passed")
    _validate_count_bound(receipt, errors)


def _validate_ready_receipt(receipt: dict[str, Any], errors: list[str]) -> None:
    if receipt.get("operator_input_request_valid") is not True:
        errors.append("passed receipt requires valid operator input request")
    if receipt.get("operator_input_probe_allowed") is not True:
        errors.append("passed receipt requires allowed operator input probe")
    if receipt.get("solver_outcome") != "SolvedVerified":
        errors.append("passed receipt requires solver_outcome=SolvedVerified")
    if receipt.get("proof_state") != "Pass":
        errors.append("passed receipt requires proof_state=Pass")
    if receipt.get("provider_operation") not in READ_ONLY_OPERATIONS:
        errors.append("passed receipt requires read-only provider_operation")
    if not str(receipt.get("provider_observation_receipt_ref", "")).strip():
        errors.append("passed receipt requires provider_observation_receipt_ref")
    if not str(receipt.get("provider_observation_receipt_id", "")).startswith(
        "teamops-shared-inbox-provider-observation-receipt-"
    ):
        errors.append("passed receipt requires provider_observation_receipt_id")
    if receipt.get("provider_observation_receipt_valid") is not True:
        errors.append("passed receipt requires provider_observation_receipt_valid=true")
    if not SHA256_HEX_PATTERN.fullmatch(str(receipt.get("response_digest", ""))):
        errors.append("passed receipt requires lowercase SHA-256 response_digest")
    if not isinstance(receipt.get("evidence_refs"), list) or not receipt.get("evidence_refs"):
        errors.append("passed receipt requires evidence_refs")
    if receipt.get("live_probe_observation_bound") is not True:
        errors.append("passed receipt requires live_probe_observation_bound=true")
    if receipt.get("blocked_until") != []:
        errors.append("passed receipt must not carry blockers")


def _validate_blocked_receipt(receipt: dict[str, Any], errors: list[str]) -> None:
    if receipt.get("solver_outcome") != "AwaitingEvidence":
        errors.append("blocked receipt requires solver_outcome=AwaitingEvidence")
    if receipt.get("proof_state") != "Unknown":
        errors.append("blocked receipt requires proof_state=Unknown")
    if not isinstance(receipt.get("blocked_until"), list) or not receipt.get("blocked_until"):
        errors.append("blocked receipt must list blockers")
    if receipt.get("live_probe_observation_bound") is not False:
        errors.append("blocked receipt must not bind live probe observation")


def _validate_failed_receipt(receipt: dict[str, Any], errors: list[str]) -> None:
    if receipt.get("solver_outcome") != "GovernanceBlocked":
        errors.append("failed receipt requires solver_outcome=GovernanceBlocked")
    if receipt.get("proof_state") != "Fail":
        errors.append("failed receipt requires proof_state=Fail")
    if not isinstance(receipt.get("blocked_until"), list) or not receipt.get("blocked_until"):
        errors.append("failed receipt must list blockers")
    if receipt.get("live_probe_observation_bound") is not False:
        errors.append("failed receipt must not bind live probe observation")


def _validate_count_bound(receipt: dict[str, Any], errors: list[str]) -> None:
    observed = receipt.get("observed_message_count")
    maximum = receipt.get("max_message_count")
    if isinstance(observed, int) and isinstance(maximum, int) and observed > maximum:
        errors.append("observed_message_count must not exceed max_message_count")


def _receipt_ready(receipt: dict[str, Any]) -> bool:
    return (
        receipt.get("status") == "passed"
        and receipt.get("solver_outcome") == "SolvedVerified"
        and receipt.get("proof_state") == "Pass"
        and receipt.get("operator_input_request_valid") is True
        and receipt.get("operator_input_probe_allowed") is True
        and receipt.get("provider_operation") in READ_ONLY_OPERATIONS
        and bool(str(receipt.get("provider_observation_receipt_ref", "")).strip())
        and str(receipt.get("provider_observation_receipt_id", "")).startswith(
            "teamops-shared-inbox-provider-observation-receipt-"
        )
        and receipt.get("provider_observation_receipt_valid") is True
        and SHA256_HEX_PATTERN.fullmatch(str(receipt.get("response_digest", ""))) is not None
        and isinstance(receipt.get("evidence_refs"), list)
        and bool(receipt.get("evidence_refs"))
        and receipt.get("live_probe_observation_bound") is True
        and receipt.get("external_provider_call_performed_by_producer") is False
        and receipt.get("external_mailbox_write_performed") is False
        and receipt.get("external_message_sent") is False
        and receipt.get("provider_mutation_performed") is False
        and receipt.get("forbidden_effects_observed") is False
        and receipt.get("blocked_until") == []
        and isinstance(receipt.get("observed_message_count"), int)
        and isinstance(receipt.get("max_message_count"), int)
        and receipt["observed_message_count"] <= receipt["max_message_count"]
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
        return "promote TeamOps shared inbox read-only observation evidence to workflow closure checks"
    recovery_actions = receipt.get("recovery_actions", [])
    if isinstance(recovery_actions, list) and recovery_actions:
        return str(recovery_actions[0])
    return "regenerate TeamOps shared inbox live-probe receipt"


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse TeamOps shared inbox live-probe receipt validation arguments."""

    parser = argparse.ArgumentParser(description="Validate TeamOps shared inbox live-probe receipt.")
    parser.add_argument("--receipt", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_VALIDATION_OUTPUT))
    parser.add_argument("--require-ready", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for TeamOps shared inbox live-probe receipt validation."""

    args = parse_args(argv)
    validation = validate_team_ops_shared_inbox_live_probe_receipt(
        receipt_path=Path(args.receipt),
        schema_path=Path(args.schema),
        require_ready=args.require_ready,
    )
    write_team_ops_shared_inbox_live_probe_receipt_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.valid:
        print(f"TeamOps shared inbox live-probe receipt valid ready={validation.ready}")
    else:
        print(f"TeamOps shared inbox live-probe receipt invalid errors={list(validation.errors)}")
    return 0 if validation.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
