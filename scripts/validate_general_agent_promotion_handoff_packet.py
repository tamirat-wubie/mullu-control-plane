#!/usr/bin/env python3
"""Validate the general-agent promotion handoff packet artifact.

Purpose: keep the operator handoff packet machine-readable, schema-valid, and
aligned with closure-plan, checklist, blocker, and terminal proof gates.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: examples/general_agent_promotion_handoff_packet.json,
schemas/general_agent_promotion_handoff_packet.schema.json, and promotion
closure validation artifacts.
Invariants:
  - The packet never claims production readiness while blockers remain.
  - Required blockers and approval-required blockers remain visible.
  - Entry points name the runbook, checklist, validators, preflight, and closure reports.
  - The terminal proof command is strict and writes the readiness artifact.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_schemas import _validate_schema_instance  # noqa: E402

DEFAULT_PACKET = REPO_ROOT / "examples" / "general_agent_promotion_handoff_packet.json"
DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "general_agent_promotion_handoff_packet.schema.json"

REQUIRED_OPEN_BLOCKERS = frozenset(
    {
        "adapter_evidence_not_closed",
        "browser_adapter_not_closed",
        "voice_adapter_not_closed",
        "email_calendar_adapter_not_closed",
        "deployment_witness_not_published",
        "production_health_not_declared",
    }
)
REQUIRED_APPROVAL_BLOCKERS = frozenset(
    {
        "voice_dependency_missing:OPENAI_API_KEY",
        "email_calendar_dependency_missing:EMAIL_CALENDAR_CONNECTOR_TOKEN",
        "deployment_witness_not_published",
        "production_health_not_declared",
    }
)
REQUIRED_ENTRY_POINTS = {
    "human_runbook": "docs/58_general_agent_promotion_operator_runbook.md",
    "machine_checklist": "examples/general_agent_promotion_operator_checklist.json",
    "machine_handoff_packet": "examples/general_agent_promotion_handoff_packet.json",
    "environment_binding_contract": "examples/general_agent_promotion_environment_bindings.json",
    "checklist_validator": "scripts/validate_general_agent_promotion_operator_checklist.py",
    "handoff_packet_validator": "scripts/validate_general_agent_promotion_handoff_packet.py",
    "environment_binding_validator": "scripts/validate_general_agent_promotion_environment_bindings.py",
    "environment_binding_receipt_emitter": "scripts/emit_general_agent_promotion_environment_binding_receipt.py",
    "environment_binding_receipt_validator": "scripts/validate_general_agent_promotion_environment_binding_receipt.py",
    "handoff_preflight": "scripts/preflight_general_agent_promotion_handoff.py",
    "handoff_preflight_validator": "scripts/validate_general_agent_promotion_handoff_preflight.py",
    "aggregate_closure_plan": ".change_assurance/general_agent_promotion_closure_plan.json",
    "schema_validation_report": ".change_assurance/general_agent_promotion_closure_plan_schema_validation.json",
    "drift_validation_report": ".change_assurance/general_agent_promotion_closure_plan_validation.json",
    "readiness_report": ".change_assurance/general_agent_promotion_readiness.json",
    "preflight_report": ".change_assurance/general_agent_promotion_handoff_preflight.json",
    "environment_binding_receipt": ".change_assurance/general_agent_promotion_environment_binding_receipt.json",
}
REQUIRED_VALIDATION_REPORTS = frozenset(
    {
        "general_agent_promotion_operator_checklist valid=true",
        "general_agent_promotion_closure_plan_schema_validation ok=true",
        "general_agent_promotion_closure_plan_validation ok=true",
    }
)
REQUIRED_SEQUENCE_ITEMS = frozenset(
    {
        "validate_operator_checklist",
        "regenerate_adapter_evidence",
        "write_promotion_readiness",
        "write_source_closure_plans",
        "write_aggregate_closure_plan",
        "validate_aggregate_closure_plan_schema",
        "validate_aggregate_closure_plan_drift",
        "validate_environment_binding_receipt",
        "complete_dependency_and_credential_actions",
        "produce_live_adapter_receipts",
        "publish_deployment_witness",
        "declare_public_health_after_witness",
        "run_terminal_promotion_validation",
    }
)


@dataclass(frozen=True, slots=True)
class PromotionHandoffPacketValidation:
    """Validation result for one promotion handoff packet."""

    valid: bool
    packet_id: str
    packet_path: str
    schema_path: str
    open_blocker_count: int
    approval_required_count: int
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        """Return deterministic JSON-ready validation output."""
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_general_agent_promotion_handoff_packet(
    *,
    packet_path: Path = DEFAULT_PACKET,
    schema_path: Path = DEFAULT_SCHEMA,
) -> PromotionHandoffPacketValidation:
    """Validate one general-agent promotion handoff packet."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "handoff packet schema", errors)
    packet = _load_json_object(packet_path, "handoff packet", errors)
    if not schema or not packet:
        return _validation_result(packet_path, schema_path, packet, errors)

    errors.extend(_validate_schema_instance(schema, packet))
    _validate_scalar_fields(packet, errors)
    _validate_required_sets(packet, errors)
    _validate_entry_points(packet, errors)
    _validate_terminal_proof(packet, errors)
    return _validation_result(packet_path, schema_path, packet, errors)


def _validate_scalar_fields(packet: dict[str, Any], errors: list[str]) -> None:
    expected_scalars: dict[str, Any] = {
        "schema_version": 1,
        "packet_id": "general-agent-promotion-handoff-v1",
        "status": "blocked_until_live_evidence",
        "readiness_level": "pilot-governed-core",
        "capability_capsules": 10,
        "governed_capabilities": 52,
        "aggregate_closure_actions": 13,
        "approval_required_actions": 4,
        "production_promotion": "blocked",
    }
    for field_name, expected_value in expected_scalars.items():
        if packet.get(field_name) != expected_value:
            errors.append(f"{field_name} must be {expected_value!r}")


def _validate_required_sets(packet: dict[str, Any], errors: list[str]) -> None:
    _require_superset(packet, "open_blockers", REQUIRED_OPEN_BLOCKERS, errors)
    _require_superset(packet, "approval_required_blockers", REQUIRED_APPROVAL_BLOCKERS, errors)
    _require_superset(packet, "required_validation_reports", REQUIRED_VALIDATION_REPORTS, errors)
    _require_superset(packet, "operator_sequence", REQUIRED_SEQUENCE_ITEMS, errors)
    open_blockers = packet.get("open_blockers", [])
    approval_blockers = packet.get("approval_required_blockers", [])
    if isinstance(open_blockers, list) and packet.get("production_promotion") == "ready" and open_blockers:
        errors.append("production_promotion cannot be ready while open_blockers are present")
    if isinstance(approval_blockers, list) and len(approval_blockers) != packet.get("approval_required_actions"):
        errors.append("approval_required_actions does not match approval_required_blockers length")


def _validate_entry_points(packet: dict[str, Any], errors: list[str]) -> None:
    entry_points = packet.get("entry_points", {})
    if not isinstance(entry_points, dict):
        errors.append("entry_points must be an object")
        return
    for key, expected_value in REQUIRED_ENTRY_POINTS.items():
        if entry_points.get(key) != expected_value:
            errors.append(f"entry_points.{key} must be {expected_value}")


def _validate_terminal_proof(packet: dict[str, Any], errors: list[str]) -> None:
    terminal_command = str(packet.get("terminal_proof_command", ""))
    for token in (
        "validate_general_agent_promotion.py",
        "--strict",
        "--output",
        ".change_assurance/general_agent_promotion_readiness.json",
    ):
        if token not in terminal_command:
            errors.append(f"terminal_proof_command missing token {token}")


def _require_superset(
    packet: dict[str, Any],
    field_name: str,
    required_values: frozenset[str],
    errors: list[str],
) -> None:
    observed = packet.get(field_name, [])
    if not isinstance(observed, list):
        errors.append(f"{field_name} must be a list")
        return
    missing = sorted(required_values - {str(item) for item in observed})
    if missing:
        errors.append(f"{field_name} missing {missing}")


def _validation_result(
    packet_path: Path,
    schema_path: Path,
    packet: dict[str, Any],
    errors: list[str],
) -> PromotionHandoffPacketValidation:
    open_blockers = packet.get("open_blockers", ())
    approval_blockers = packet.get("approval_required_blockers", ())
    return PromotionHandoffPacketValidation(
        valid=not errors,
        packet_id=str(packet.get("packet_id", "")),
        packet_path=str(packet_path),
        schema_path=str(schema_path),
        open_blocker_count=len(open_blockers) if isinstance(open_blockers, list) else 0,
        approval_required_count=len(approval_blockers) if isinstance(approval_blockers, list) else 0,
        errors=tuple(errors),
    )


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        errors.append(f"{label} could not be read: {exc}")
        return {}
    except json.JSONDecodeError as exc:
        errors.append(f"{label} must be JSON: {exc}")
        return {}
    if not isinstance(parsed, dict):
        errors.append(f"{label} root must be an object")
        return {}
    return parsed


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse promotion handoff packet validation arguments."""
    parser = argparse.ArgumentParser(description="Validate general-agent promotion handoff packet.")
    parser.add_argument("--packet", default=str(DEFAULT_PACKET))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for promotion handoff packet validation."""
    args = parse_args(argv)
    result = validate_general_agent_promotion_handoff_packet(
        packet_path=Path(args.packet),
        schema_path=Path(args.schema),
    )
    if args.json:
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    elif result.valid:
        print(f"general-agent promotion handoff packet ok blockers={result.open_blocker_count}")
    else:
        for error in result.errors:
            print(f"error: {error}")
    return 0 if result.valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
