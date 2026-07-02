#!/usr/bin/env python3
"""Build an operator workflow next-action packet.

Purpose: derive one compact operator handoff artifact from the projection-only
operator workflow dashboard readiness lane.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: gateway.operator_workflow_dashboard and JSON schema validation.
Invariants:
  - The packet is projection-only and never executes workflow stages.
  - It does not grant file write, branch push, PR creation, merge, deployment,
    connector, email, money, production-write, or live execution authority.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateway.operator_workflow_dashboard import (  # noqa: E402
    DEFAULT_OUTPUT as DEFAULT_DASHBOARD,
    validate_operator_workflow_dashboard_read_model,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


SCHEMA_REF = "urn:mullusi:schema:operator-workflow-next-action-packet:1"
PACKET_ID = "operator_workflow_next_action_packet.foundation.v1"
DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "operator_workflow_next_action_packet.schema.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "operator_workflow_next_action_packet.generated.json"


@dataclass(frozen=True, slots=True)
class OperatorWorkflowNextActionPacketValidation:
    """Validation report for an operator workflow next-action packet."""

    ok: bool
    errors: tuple[str, ...]
    packet_path: str
    lane_status: str
    operator_outcome: str

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def build_operator_workflow_next_action_packet(
    *,
    dashboard: Mapping[str, Any],
    dashboard_path: Path,
) -> dict[str, Any]:
    """Return a compact next-action packet from a dashboard readiness lane."""

    dashboard_validation = validate_operator_workflow_dashboard_read_model(
        dashboard=dashboard,
        dashboard_path=dashboard_path,
    )
    if not dashboard_validation.ok:
        raise ValueError(f"operator_workflow_dashboard_invalid:{list(dashboard_validation.errors)}")
    rows = dashboard.get("rows", ())
    if not isinstance(rows, list) or not rows or not isinstance(rows[0], Mapping):
        raise ValueError("operator_workflow_dashboard_first_row_missing")
    row = rows[0]
    readiness_lane = _mapping(row.get("readiness_lane"))
    linked_receipts = _mapping(readiness_lane.get("linked_receipts"))
    packet = {
        "schema_ref": SCHEMA_REF,
        "packet_id": PACKET_ID,
        "source_dashboard_id": str(dashboard.get("dashboard_id") or "operator_workflow_dashboard.foundation.v1"),
        "task": str(row.get("task") or "Mullu Developer Workflow v1"),
        "lane_status": str(readiness_lane.get("lane_status") or "AwaitingEvidence"),
        "proof_state": str(readiness_lane.get("proof_state") or "AwaitingEvidence"),
        "operator_outcome": str(readiness_lane.get("operator_outcome") or "AwaitingEvidence"),
        "primary_blocker": str(readiness_lane.get("primary_blocker") or "unknown"),
        "current_gate_id": str(readiness_lane.get("current_gate_id") or "unknown"),
        "next_action": str(readiness_lane.get("next_action") or row.get("next_action") or "inspect dashboard"),
        "required_evidence_refs": _string_list(readiness_lane.get("required_evidence_refs"))[:12],
        "linked_receipts": {
            "closure_packet": linked_receipts.get("closure_packet") is True,
            "safe_local_action_rehearsal": linked_receipts.get("safe_local_action_rehearsal") is True,
            "causal_repair": linked_receipts.get("causal_repair") is True,
        },
        "approval": {
            "needed": _mapping(row.get("approval")).get("needed") is True,
            "status": str(_mapping(row.get("approval")).get("status") or "unknown"),
            "performed": False,
        },
        "blocked_effects": _string_list(dashboard.get("blocked_effects"))[:16],
        "source_refs": {
            "dashboard": _path_label(dashboard_path),
            "builder": "scripts/build_operator_workflow_next_action_packet.py",
        },
        "readiness_is_not_execution_authority": True,
        "projection_only": True,
        "execution_authority_granted": False,
        "execution_performed": False,
        "live_execution_enabled": False,
        "external_effects_allowed": False,
        "packet_hash": "",
    }
    packet["packet_hash"] = canonical_hash(packet)
    return packet


def validate_operator_workflow_next_action_packet(
    *,
    packet: Mapping[str, Any],
    schema_path: Path = DEFAULT_SCHEMA,
    packet_path: Path = Path("<generated>"),
) -> OperatorWorkflowNextActionPacketValidation:
    """Validate schema, hash, and no-effect semantics for a next-action packet."""

    errors = [str(error) for error in _validate_schema_instance(_load_json_object(schema_path), dict(packet))]
    for field_name in (
        "readiness_is_not_execution_authority",
        "projection_only",
    ):
        if packet.get(field_name) is not True:
            errors.append(f"{field_name}_must_be_true")
    for field_name in (
        "execution_authority_granted",
        "execution_performed",
        "live_execution_enabled",
        "external_effects_allowed",
    ):
        if packet.get(field_name) is not False:
            errors.append(f"{field_name}_must_be_false")
    if _mapping(packet.get("approval")).get("performed") is not False:
        errors.append("approval_performed_must_be_false")
    if packet.get("packet_hash") != canonical_hash({**dict(packet), "packet_hash": ""}):
        errors.append("packet_hash_mismatch")
    return OperatorWorkflowNextActionPacketValidation(
        ok=not errors,
        errors=tuple(errors),
        packet_path=_path_label(packet_path),
        lane_status=str(packet.get("lane_status") or ""),
        operator_outcome=str(packet.get("operator_outcome") or ""),
    )


def write_operator_workflow_next_action_packet(packet: Mapping[str, Any], output_path: Path) -> Path:
    """Write a deterministic next-action packet."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def canonical_hash(payload: Mapping[str, Any]) -> str:
    """Return a deterministic SHA-256 hash for a JSON-compatible payload."""

    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"json_parse_failed:{path}") from exc
    if not isinstance(payload, Mapping):
        raise ValueError(f"json_root_must_be_object:{path}")
    return dict(payload)


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse next-action packet builder arguments."""

    parser = argparse.ArgumentParser(description="Build operator workflow next-action packet.")
    parser.add_argument("--dashboard", default=str(DEFAULT_DASHBOARD))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for next-action packet building."""

    args = parse_args(argv)
    try:
        dashboard_path = Path(args.dashboard)
        packet = build_operator_workflow_next_action_packet(
            dashboard=_load_json_object(dashboard_path),
            dashboard_path=dashboard_path,
        )
        output_path = write_operator_workflow_next_action_packet(packet, Path(args.output))
        validation = validate_operator_workflow_next_action_packet(
            packet=packet,
            schema_path=Path(args.schema),
            packet_path=output_path,
        )
    except ValueError as exc:
        print(f"OPERATOR WORKFLOW NEXT ACTION PACKET INVALID error={exc}")
        return 2
    if not validation.ok:
        print(f"OPERATOR WORKFLOW NEXT ACTION PACKET INVALID errors={list(validation.errors)}")
        return 2
    if args.json:
        print(json.dumps(packet, indent=2, sort_keys=True))
    else:
        print(f"OPERATOR WORKFLOW NEXT ACTION PACKET BUILT path={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
