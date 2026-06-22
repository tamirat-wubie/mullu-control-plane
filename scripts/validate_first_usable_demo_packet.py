#!/usr/bin/env python3
"""Validate the First Usable Demo Packet.

Purpose: keep the product-compression demo packet no-effect, reviewable,
and separated from deployment/customer-readiness claims.
Governance scope: first-demo sequencing, authority denial, evidence refs,
claim-boundary separation, and private/secret payload rejection.
Invariants:
  - The packet never grants execution, connector, send, payment, memory,
    deployment, launch, approval-as-execution, or customer-readiness authority.
  - The canonical demo lane must keep the expected eight-step order.
  - Promotion gates and deltas must be explicit before future work proceeds.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import re
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PACKET = REPO_ROOT / "examples" / "first_usable_demo_packet.json"

EXPECTED_PACKET_TYPE = "mullu.first_usable_demo_packet"
EXPECTED_DEMO_NAME = "Governed Personal Assistant First Usable Demo"
EXPECTED_STEP_IDS = (
    "01_intake",
    "02_missing_binding_review",
    "03_skill_route",
    "04_policy_risk",
    "05_draft_plan",
    "06_approval_review",
    "07_receipt_proof",
    "08_operator_read_model",
)
REQUIRED_FALSE_AUTHORITY_FIELDS = frozenset(
    {
        "execution_allowed",
        "live_connector_execution_allowed",
        "connector_mutation_allowed",
        "external_send_allowed",
        "money_movement_allowed",
        "memory_write_allowed",
        "deployment_mutation_allowed",
        "customer_readiness_claim_allowed",
        "public_launch_claim_allowed",
        "approval_is_execution",
    }
)
REQUIRED_FALSE_CLAIM_FIELDS = frozenset(
    {
        "deployment_health_evidence_is_customer_readiness",
        "public_health_endpoint_is_live_assistant_authority",
        "foundation_demo_is_paid_use_ready",
        "readiness_packet_is_legal_or_business_clearance",
    }
)
REQUIRED_READINESS_KEYS = frozenset(
    {
        "product_compression",
        "read_only_packet",
        "draft_only_walkthrough",
        "approval_review_binding",
        "dry_run_adapter",
        "live_connector",
        "customer_readiness",
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
class FirstUsableDemoPacketValidation:
    """Validation result for the first usable demo packet."""

    valid: bool
    packet_path: str
    packet_id: str
    solver_outcome: str
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        rendered = asdict(self)
        rendered["errors"] = list(self.errors)
        return rendered


def validate_first_usable_demo_packet(
    *,
    packet_path: Path = DEFAULT_PACKET,
) -> FirstUsableDemoPacketValidation:
    """Validate the no-effect first usable demo packet."""
    errors: list[str] = []
    packet = _load_json_object(packet_path, "first usable demo packet", errors)
    packet_id = ""
    if packet:
        packet_id = str(packet.get("packet_id", ""))
        errors.extend(_validate_semantics(packet))
        _scan_private_or_secret_payload(packet, errors, path="$")
    return FirstUsableDemoPacketValidation(
        valid=not errors,
        packet_path=_path_label(packet_path),
        packet_id=packet_id,
        solver_outcome="SolvedVerified" if not errors else "GovernanceBlocked",
        errors=tuple(errors),
    )


def _validate_semantics(packet: dict[str, Any]) -> tuple[str, ...]:
    errors: list[str] = []
    if packet.get("packet_type") != EXPECTED_PACKET_TYPE:
        errors.append(f"packet_type must be {EXPECTED_PACKET_TYPE}")
    if packet.get("demo_name") != EXPECTED_DEMO_NAME:
        errors.append(f"demo_name must be {EXPECTED_DEMO_NAME}")
    if packet.get("solver_outcome") != "AwaitingEvidence":
        errors.append("solver_outcome must be AwaitingEvidence")
    if packet.get("foundation_only") is not True:
        errors.append("foundation_only must be true")
    if not str(packet.get("demo_goal", "")).strip():
        errors.append("demo_goal must be present")
    errors.extend(_validate_user_story(packet.get("canonical_user_story")))
    errors.extend(_validate_false_map(packet.get("current_authority"), REQUIRED_FALSE_AUTHORITY_FIELDS, "current_authority"))
    errors.extend(_validate_lane(packet.get("first_demo_lane")))
    errors.extend(_validate_promotion_gates(packet.get("promotion_gates")))
    errors.extend(_validate_readiness_index(packet.get("readiness_index")))
    errors.extend(_validate_false_map(packet.get("claim_boundary"), REQUIRED_FALSE_CLAIM_FIELDS, "claim_boundary"))
    errors.extend(_validate_non_empty_string_list(packet.get("constructive_deltas"), "constructive_deltas", minimum=3))
    errors.extend(_validate_non_empty_string_list(packet.get("fracture_deltas"), "fracture_deltas", minimum=3))
    errors.extend(_validate_non_empty_string_list(packet.get("next_safe_actions"), "next_safe_actions", minimum=4))
    return tuple(errors)


def _validate_user_story(value: Any) -> tuple[str, ...]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return ("canonical_user_story must be an object",)
    for field_name in ("actor", "request", "observable_result"):
        if not str(value.get(field_name, "")).strip():
            errors.append(f"canonical_user_story.{field_name} must be present")
    non_goals = value.get("explicit_non_goals")
    required_non_goals = {
        "send_email",
        "pay_invoice",
        "mutate_gmail",
        "mutate_calendar",
        "mutate_accounting_record",
        "write_memory",
        "deploy_service",
        "claim_customer_readiness",
    }
    if not isinstance(non_goals, list):
        errors.append("canonical_user_story.explicit_non_goals must be a list")
    else:
        observed = {str(item) for item in non_goals}
        for required in sorted(required_non_goals - observed):
            errors.append(f"canonical_user_story.explicit_non_goals missing {required}")
    return tuple(errors)


def _validate_false_map(value: Any, required_fields: frozenset[str], label: str) -> tuple[str, ...]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return (f"{label} must be an object",)
    for field_name in sorted(required_fields):
        if value.get(field_name) is not False:
            errors.append(f"{label}.{field_name} must be false")
    return tuple(errors)


def _validate_lane(value: Any) -> tuple[str, ...]:
    errors: list[str] = []
    if not isinstance(value, list):
        return ("first_demo_lane must be a list",)
    observed_ids: list[str] = []
    for index, step in enumerate(value):
        if not isinstance(step, dict):
            errors.append(f"first_demo_lane[{index}] must be an object")
            continue
        step_id = str(step.get("step_id", ""))
        observed_ids.append(step_id)
        for field_name in ("surface", "expected_output", "authority", "evidence_ref"):
            if not str(step.get(field_name, "")).strip():
                errors.append(f"first_demo_lane[{index}].{field_name} must be present")
        authority = str(step.get("authority", ""))
        if authority not in {"no_effect", "approval_is_not_execution", "no_external_effect", "read_only"}:
            errors.append(f"first_demo_lane[{index}].authority is not an allowed no-effect authority")
        evidence_ref = str(step.get("evidence_ref", ""))
        if evidence_ref and _resolve_repo_path(evidence_ref) is None:
            errors.append(f"first_demo_lane[{index}].evidence_ref must stay under repository root")
    if tuple(observed_ids) != EXPECTED_STEP_IDS:
        errors.append("first_demo_lane step_id order must match expected first demo lane")
    return tuple(errors)


def _validate_promotion_gates(value: Any) -> tuple[str, ...]:
    errors: list[str] = []
    if not isinstance(value, list):
        return ("promotion_gates must be a list",)
    required_gate_ids = {
        "read_only_demo",
        "draft_only_demo",
        "approval_review_demo",
        "dry_run_adapter_demo",
        "live_connector_demo",
        "customer_pilot",
    }
    observed_gate_ids: set[str] = set()
    for index, gate in enumerate(value):
        if not isinstance(gate, dict):
            errors.append(f"promotion_gates[{index}] must be an object")
            continue
        gate_id = str(gate.get("gate_id", ""))
        observed_gate_ids.add(gate_id)
        if not gate_id:
            errors.append(f"promotion_gates[{index}].gate_id must be present")
        if not str(gate.get("required_before_promotion", "")).strip():
            errors.append(f"promotion_gates[{index}].required_before_promotion must be present")
    for required in sorted(required_gate_ids - observed_gate_ids):
        errors.append(f"promotion_gates missing {required}")
    return tuple(errors)


def _validate_readiness_index(value: Any) -> tuple[str, ...]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return ("readiness_index must be an object",)
    for required in sorted(REQUIRED_READINESS_KEYS):
        if not str(value.get(required, "")).strip():
            errors.append(f"readiness_index.{required} must be present")
    if value.get("customer_readiness") != "blocked":
        errors.append("readiness_index.customer_readiness must be blocked")
    if not str(value.get("live_connector", "")).startswith("blocked"):
        errors.append("readiness_index.live_connector must remain blocked")
    return tuple(errors)


def _validate_non_empty_string_list(value: Any, label: str, *, minimum: int) -> tuple[str, ...]:
    if not isinstance(value, list):
        return (f"{label} must be a list",)
    errors: list[str] = []
    if len(value) < minimum:
        errors.append(f"{label} must contain at least {minimum} items")
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            errors.append(f"{label}[{index}] must be a non-empty string")
    return tuple(errors)


def _resolve_repo_path(path_text: str) -> Path | None:
    candidate = (REPO_ROOT / path_text).resolve()
    root = REPO_ROOT.resolve()
    if candidate == root or root in candidate.parents:
        return candidate
    return None


def _scan_private_or_secret_payload(value: Any, errors: list[str], *, path: str) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            key_text = str(key)
            next_path = f"{path}.{key_text}"
            if key_text in RAW_PRIVATE_FIELD_NAMES:
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
    parser.add_argument("--json", action="store_true", help="Emit JSON validation result")
    args = parser.parse_args(argv)
    validation = validate_first_usable_demo_packet(packet_path=args.packet)
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    else:
        status = "PASS" if validation.valid else "FAIL"
        print(f"[{status}] first_usable_demo_packet {validation.packet_id}")
        for error in validation.errors:
            print(f"- {error}")
    return 0 if validation.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
