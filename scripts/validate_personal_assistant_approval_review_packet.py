#!/usr/bin/env python3
"""Validate Personal Assistant approval review packets.

Purpose: keep approval review packets schema-backed, no-effect, and bounded to
operator review before any future approval queue or execution path.
Governance scope: approval proposal review, authority denial, evidence binding,
private payload redaction, and Foundation Mode readiness boundaries.
Dependencies: personal_assistant_approval_review_packet schema and schema
validation helper.
Invariants:
  - Review packets never enqueue, approve, or execute actions.
  - Every proposed action remains bound to explicit evidence and forbidden
    actions.
  - Raw private connector payloads and secret-like values are rejected.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_PACKET = REPO_ROOT / "examples" / "personal_assistant_approval_review_packet.json"
DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "personal_assistant_approval_review_packet.schema.json"
FALSE_EFFECT_FIELDS = frozenset(
    {
        "execution_allowed",
        "approval_is_execution",
        "approval_enqueued",
        "live_connector_execution_allowed",
        "external_send_allowed",
        "connector_mutation_allowed",
        "memory_write_allowed",
        "deployment_mutation_allowed",
        "system_of_record_write_allowed",
        "money_legal_public_action_allowed",
    }
)
FALSE_METADATA_FIELDS = frozenset(
    {
        "approval_packet_is_execution",
        "review_packet_is_execution",
        "live_nested_mind_activation_allowed",
        "customer_readiness_claim_allowed",
    }
)
RAW_PRIVATE_FIELD_NAMES = frozenset(
    {
        "raw_private_connector_payload",
        "raw_connector_payload",
        "private_connector_payload",
        "connector_response",
        "message_body",
        "email_body",
        "calendar_payload",
        "mailbox_payload",
        "raw_message",
        "raw_thread",
        "raw_chat_log",
        "chat_log",
        "transcript",
        "credential",
        "credentials",
        "token",
        "secret",
        "private_key",
        "authorization",
        "cookie",
    }
)
ALLOWED_POLICY_FIELD_NAMES = frozenset(
    {
        "approval_packet_is_execution",
        "review_packet_is_execution",
        "live_connector_execution_allowed",
        "live_nested_mind_activation_allowed",
        "customer_readiness_claim_allowed",
    }
)
SECRET_VALUE_PATTERNS = (
    re.compile(r"sk_live_[A-Za-z0-9]+"),
    re.compile(r"ghp_[A-Za-z0-9]+"),
    re.compile(r"github_pat_[A-Za-z0-9_]+"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]+"),
    re.compile(r"ya29\.[A-Za-z0-9._-]+"),
    re.compile(r"Bearer\s+[A-Za-z0-9._-]+", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"secret-(?:token|worker|key)-value", re.IGNORECASE),
)


@dataclass(frozen=True, slots=True)
class ApprovalReviewPacketValidation:
    """Validation result for a Personal Assistant approval review packet."""

    valid: bool
    packet_path: str
    review_packet_id: str
    solver_outcome: str
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        rendered = asdict(self)
        rendered["errors"] = list(self.errors)
        return rendered


def validate_personal_assistant_approval_review_packet(
    *,
    packet_path: Path = DEFAULT_PACKET,
    schema_path: Path = DEFAULT_SCHEMA,
) -> ApprovalReviewPacketValidation:
    """Validate a no-effect approval review packet fixture."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "approval review packet schema", errors)
    packet = _load_json_object(packet_path, "approval review packet", errors)
    review_packet_id = ""
    if schema and packet:
        errors.extend(_validate_schema_instance(schema, packet))
    if packet:
        review_packet_id = str(packet.get("review_packet_id", ""))
        errors.extend(_validate_semantics(packet))
        _scan_private_or_secret_payload(packet, errors, path="$")
    return ApprovalReviewPacketValidation(
        valid=not errors,
        packet_path=_path_label(packet_path),
        review_packet_id=review_packet_id,
        solver_outcome="SolvedVerified" if not errors else "GovernanceBlocked",
        errors=tuple(errors),
    )


def _validate_semantics(packet: dict[str, Any]) -> tuple[str, ...]:
    errors: list[str] = []
    if packet.get("review_state") != "preview_only":
        errors.append("review_state must be preview_only")
    if packet.get("risk_level") not in {"P3", "P4", "P5"}:
        errors.append("risk_level must require explicit approval")
    if not packet.get("evidence_refs"):
        errors.append("evidence_refs must not be empty")
    if not packet.get("forbidden_without_approval"):
        errors.append("forbidden_without_approval must not be empty")
    required_checks = packet.get("required_operator_checks")
    if not isinstance(required_checks, list) or len(required_checks) < 6:
        errors.append("required_operator_checks must contain the base review checks")
    else:
        for required in (
            "confirm_request_identity",
            "confirm_plan_identity",
            "confirm_proposed_action_scope",
            "confirm_evidence_refs_present",
            "confirm_forbidden_actions_remain_unexecuted",
            "confirm_receipt_required",
        ):
            if required not in required_checks:
                errors.append(f"required_operator_checks missing {required}")
    denials = packet.get("authority_denials")
    if not isinstance(denials, list) or not denials:
        errors.append("authority_denials must not be empty")
    else:
        denied_authorities = {
            str(item.get("authority"))
            for item in denials
            if isinstance(item, dict) and item.get("denied") is True
        }
        for required in ("execution", "approval_enqueue", "connector_mutation", "memory_write"):
            if required not in denied_authorities:
                errors.append(f"authority_denials missing {required}")
    effect_boundary = packet.get("effect_boundary")
    if not isinstance(effect_boundary, dict):
        errors.append("effect_boundary must be an object")
    else:
        for field_name in sorted(FALSE_EFFECT_FIELDS):
            if effect_boundary.get(field_name) is not False:
                errors.append(f"effect_boundary.{field_name} must be false")
    metadata = packet.get("metadata")
    if not isinstance(metadata, dict):
        errors.append("metadata must be an object")
    else:
        if metadata.get("foundation_only") is not True:
            errors.append("metadata.foundation_only must be true")
        if not metadata.get("approval_matrix_ref"):
            errors.append("metadata.approval_matrix_ref must be present")
        for field_name in sorted(FALSE_METADATA_FIELDS):
            if metadata.get(field_name) is not False:
                errors.append(f"metadata.{field_name} must be false")
    return tuple(errors)


def _scan_private_or_secret_payload(value: Any, errors: list[str], *, path: str) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            key_text = str(key)
            next_path = f"{path}.{key_text}"
            if key_text in RAW_PRIVATE_FIELD_NAMES and key_text not in ALLOWED_POLICY_FIELD_NAMES:
                errors.append(f"{next_path} must not serialize raw private payloads")
                continue
            _scan_private_or_secret_payload(nested, errors, path=next_path)
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _scan_private_or_secret_payload(nested, errors, path=f"{path}[{index}]")
    elif isinstance(value, str):
        for pattern in SECRET_VALUE_PATTERNS:
            if pattern.search(value):
                errors.append(f"{path} contains secret-like value")
                return


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(f"{label} not found: {_path_label(path)}")
        return {}
    except json.JSONDecodeError as exc:
        errors.append(f"{label} is not valid JSON: {exc}")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{label} must be a JSON object")
        return {}
    return payload


def _path_label(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--json", action="store_true", help="Emit JSON validation result")
    args = parser.parse_args(argv)
    validation = validate_personal_assistant_approval_review_packet(
        packet_path=args.packet,
        schema_path=args.schema,
    )
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    else:
        status = "PASS" if validation.valid else "FAIL"
        print(f"[{status}] personal_assistant_approval_review_packet {validation.review_packet_id}")
        for error in validation.errors:
            print(f"- {error}")
    return 0 if validation.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
