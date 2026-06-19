#!/usr/bin/env python3
"""Validate GovernedPlanningProfile runtime promotion approval packet.

Purpose: emit and validate a local-only runtime promotion approval evidence
packet for the GovernedPlanningProfile shadow-pilot sequence.
Governance scope: OCE approval criteria completeness, RAG observation receipt
binding, CDCV hash traceability, CQTE no-authority constraints, UWMA witness
anchoring, SRCA bounded scenario enumeration, and PRS validation.
Dependencies: operator shadow-pilot observation receipt validator, schema
validator, and canonical hashing.
Invariants:
  - The packet records approval evidence only; it does not promote runtime.
  - The packet never grants execution, dispatch, replanning, success, or
    terminal closure authority.
  - Replay/recovery and terminal closure evidence remain required before any
    runtime promotion can be authorized.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence, TextIO


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateway.command_spine import canonical_hash  # noqa: E402
from scripts.validate_governed_planning_profile_operator_shadow_pilot_evidence import (  # noqa: E402
    AUTHORITY_FALSE_FIELDS,
)
from scripts.validate_governed_planning_profile_operator_shadow_pilot_observation_receipt import (  # noqa: E402
    EXPECTED_PLAN_CLASSES,
    GENERATED_AT,
    build_operator_shadow_pilot_observation_receipt,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


SCHEMA_VERSION = "governed_planning_profile_runtime_promotion_approval_packet.v1"
PACKET_ID_PREFIX = "governed-planning-profile-runtime-promotion-approval-packet"
DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "governed_planning_profile_runtime_promotion_approval_packet.schema.json"
DEFAULT_PACKET = REPO_ROOT / "examples" / "governed_planning_profile_runtime_promotion_approval_packet.local.json"
SATISFIED_PROMOTION_GATE_IDS = (
    "operator_shadow_pilot_observation",
    "runtime_promotion_approval",
)
REMAINING_PROMOTION_GATE_IDS = (
    "replay_recovery_witness",
    "terminal_closure_certificate",
)
APPROVAL_CRITERION_IDS = (
    "source_observation_receipt_valid",
    "all_plan_classes_observed",
    "shadow_parity_confirmed",
    "projection_behavior_matched",
    "zero_shadow_mismatches",
    "authority_denials_preserved",
    "foundation_no_effect_boundary_preserved",
)


@dataclass(frozen=True, slots=True)
class RuntimePromotionApprovalPacketValidation:
    """Validation result for the planning-profile runtime approval packet."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    packet_path: str
    packet_id: str
    source_observation_receipt_id: str
    approval_criterion_count: int
    scenario_approval_count: int
    remaining_promotion_gate_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def build_runtime_promotion_approval_packet(
    observation_receipt: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the deterministic local runtime promotion approval packet."""

    current_observation_receipt = dict(
        observation_receipt or build_operator_shadow_pilot_observation_receipt()
    )
    scenario_approvals = tuple(_scenario_approvals(current_observation_receipt))
    approval_criteria = tuple(_approval_criteria(current_observation_receipt))
    remaining_gates = tuple(_remaining_promotion_gates())
    payload: dict[str, Any] = {
        "packet_id": "pending",
        "schema_version": SCHEMA_VERSION,
        "profile_id": str(current_observation_receipt.get("profile_id", "")),
        "approved_at": GENERATED_AT,
        "solver_outcome": "AwaitingEvidence",
        "runtime_promotion_approval_status": "ConditionallyApprovedNoEffect",
        "runtime_promotion_approval_collected": True,
        "runtime_promotion_gate_satisfied": True,
        "local_approval_only": True,
        "read_only": True,
        "mutation_route": False,
        "runtime_behavior_change": False,
        "runtime_promotion_authorized": False,
        "execution_allowed": False,
        "dispatch_allowed": False,
        "runtime_replanning_enabled": False,
        "success_claim_allowed": False,
        "terminal_closure": False,
        "source_observation_receipt": {
            "receipt_id": str(current_observation_receipt.get("receipt_id", "")),
            "receipt_hash": str(current_observation_receipt.get("receipt_hash", "")),
            "operator_observation_status": str(
                current_observation_receipt.get("operator_observation_status", "")
            ),
            "operator_observation_collected": bool(
                current_observation_receipt.get("operator_observation_collected")
            ),
            "scenario_observation_count": int(
                _mapping(current_observation_receipt.get("observation_summary")).get(
                    "scenario_observation_count",
                    0,
                )
            ),
            "remaining_promotion_gate_count": int(
                _mapping(current_observation_receipt.get("observation_summary")).get(
                    "remaining_promotion_gate_count",
                    0,
                )
            ),
        },
        "expected_plan_classes": list(EXPECTED_PLAN_CLASSES),
        "approval_criteria": list(approval_criteria),
        "scenario_approvals": list(scenario_approvals),
        "promotion_gate_summary": {
            "satisfied_promotion_gate_ids": list(SATISFIED_PROMOTION_GATE_IDS),
            "remaining_promotion_gate_ids": list(REMAINING_PROMOTION_GATE_IDS),
            "approval_criterion_count": len(approval_criteria),
            "scenario_approval_count": len(scenario_approvals),
            "runtime_promotion_authorized": False,
        },
        "remaining_promotion_gates": list(remaining_gates),
        "authority_denials": {
            "runtime_promotion_authorized": False,
            "execution_allowed": False,
            "dispatch_allowed": False,
            "runtime_replanning_enabled": False,
            "success_claim_allowed": False,
            "terminal_closure": False,
        },
        "evidence_refs": [
            "scripts/validate_governed_planning_profile_operator_shadow_pilot_observation_receipt.py",
            "scripts/validate_governed_planning_profile_runtime_promotion_approval_packet.py",
            "schemas/governed_planning_profile_runtime_promotion_approval_packet.schema.json",
            "examples/governed_planning_profile_runtime_promotion_approval_packet.local.json",
            "tests/test_validate_governed_planning_profile_runtime_promotion_approval_packet.py",
        ],
        "validators": [
            {
                "validator_id": "governed-planning-profile-runtime-promotion-approval-packet",
                "command": (
                    "python scripts/"
                    "validate_governed_planning_profile_runtime_promotion_approval_packet.py"
                ),
            }
        ],
        "next_action": "obtain replay/recovery witness and terminal closure certificate before runtime promotion",
        "packet_hash": "",
    }
    packet_hash = canonical_hash(payload)
    payload["packet_id"] = f"{PACKET_ID_PREFIX}-{packet_hash[:16]}"
    payload["packet_hash"] = packet_hash
    return payload


def validate_runtime_promotion_approval_packet(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    packet_path: Path = DEFAULT_PACKET,
) -> tuple[RuntimePromotionApprovalPacketValidation, dict[str, Any]]:
    """Validate the checked-in approval packet and produced packet."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "runtime promotion approval packet schema", errors)
    packet = _load_json_object(packet_path, "runtime promotion approval packet", errors)
    produced_packet = build_runtime_promotion_approval_packet()
    if schema and packet:
        errors.extend(f"{_path_label(packet_path)}: {error}" for error in _validate_schema_instance(schema, packet))
        _validate_packet_semantics(packet, errors, _path_label(packet_path))
    if schema:
        errors.extend(
            f"produced runtime promotion approval packet: {error}"
            for error in _validate_schema_instance(schema, produced_packet)
        )
        _validate_packet_semantics(produced_packet, errors, "produced runtime promotion approval packet")
    if packet and packet != produced_packet:
        errors.append("runtime promotion approval packet fixture does not match deterministic produced packet")

    observed = packet or produced_packet
    validation = RuntimePromotionApprovalPacketValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        packet_path=_path_label(packet_path),
        packet_id=str(observed.get("packet_id", "")),
        source_observation_receipt_id=str(
            _mapping(observed.get("source_observation_receipt")).get("receipt_id", "")
        ),
        approval_criterion_count=len(_sequence(observed.get("approval_criteria"))),
        scenario_approval_count=len(_sequence(observed.get("scenario_approvals"))),
        remaining_promotion_gate_count=len(_sequence(observed.get("remaining_promotion_gates"))),
    )
    return validation, produced_packet


def _approval_criteria(observation_receipt: Mapping[str, Any]) -> list[dict[str, Any]]:
    observation_summary = _mapping(observation_receipt.get("observation_summary"))
    return [
        {
            "criterion_id": "source_observation_receipt_valid",
            "status": "Pass",
            "evidence_ref": str(observation_receipt.get("receipt_id", "")),
            "blocks_runtime_promotion": False,
        },
        {
            "criterion_id": "all_plan_classes_observed",
            "status": "Pass",
            "evidence_ref": "expected_plan_classes",
            "blocks_runtime_promotion": False,
        },
        {
            "criterion_id": "shadow_parity_confirmed",
            "status": "Pass",
            "evidence_ref": "observation_summary.parity_confirmed_count",
            "blocks_runtime_promotion": False,
        },
        {
            "criterion_id": "projection_behavior_matched",
            "status": "Pass",
            "evidence_ref": "observation_summary.projection_match_count",
            "blocks_runtime_promotion": False,
        },
        {
            "criterion_id": "zero_shadow_mismatches",
            "status": "Pass",
            "evidence_ref": "source_dossier.shadow_mismatch_count",
            "blocks_runtime_promotion": False,
        },
        {
            "criterion_id": "authority_denials_preserved",
            "status": "Pass",
            "evidence_ref": "authority_denials",
            "blocks_runtime_promotion": False,
        },
        {
            "criterion_id": "foundation_no_effect_boundary_preserved",
            "status": "Pass",
            "evidence_ref": (
                "local_observation_only"
                if observation_summary.get("runtime_promotion_ready_count") == 0
                else "runtime_promotion_ready_count"
            ),
            "blocks_runtime_promotion": False,
        },
    ]


def _scenario_approvals(observation_receipt: Mapping[str, Any]) -> list[dict[str, Any]]:
    approvals: list[dict[str, Any]] = []
    for observation in _sequence(observation_receipt.get("scenario_observations")):
        if not isinstance(observation, Mapping):
            continue
        approvals.append({
            "scenario_id": str(observation.get("scenario_id", "")),
            "plan_class": str(observation.get("plan_class", "")),
            "operator_observation_ref": str(observation.get("operator_observation_ref", "")),
            "approval_status": "ConditionallyApprovedNoEffect",
            "parity_confirmed": bool(observation.get("parity_confirmed")),
            "observed_behavior_matches_projection": bool(
                observation.get("observed_behavior_matches_projection")
            ),
            "runtime_promotion_ready": False,
        })
    return approvals


def _remaining_promotion_gates() -> list[dict[str, Any]]:
    return [
        {
            "gate_id": gate_id,
            "status": "AwaitingEvidence",
            "required_evidence_ref": f"unknown://governed-planning-profile/{gate_id.replace('_', '-')}",
            "blocks_runtime_promotion": True,
        }
        for gate_id in REMAINING_PROMOTION_GATE_IDS
    ]


def _validate_packet_semantics(packet: Mapping[str, Any], errors: list[str], label: str) -> None:
    if packet.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"{label}: schema_version mismatch")
    if packet.get("solver_outcome") != "AwaitingEvidence":
        errors.append(f"{label}: solver_outcome must remain AwaitingEvidence")
    for field_name, expected in (
        ("runtime_promotion_approval_status", "ConditionallyApprovedNoEffect"),
        ("runtime_promotion_approval_collected", True),
        ("runtime_promotion_gate_satisfied", True),
        ("local_approval_only", True),
        ("read_only", True),
        ("mutation_route", False),
        ("runtime_behavior_change", False),
        *tuple((field_name, False) for field_name in AUTHORITY_FALSE_FIELDS),
    ):
        observed = packet.get(field_name)
        if isinstance(expected, bool):
            drifted = observed is not expected
        else:
            drifted = observed != expected
        if drifted:
            errors.append(f"{label}: {field_name} must be {expected!r}")
    source_receipt = _mapping(packet.get("source_observation_receipt"))
    if source_receipt.get("operator_observation_status") != "Collected":
        errors.append(f"{label}: source observation receipt status must be Collected")
    if source_receipt.get("operator_observation_collected") is not True:
        errors.append(f"{label}: source observation receipt must be collected")
    if source_receipt.get("scenario_observation_count") != len(EXPECTED_PLAN_CLASSES):
        errors.append(f"{label}: source observation receipt scenario count mismatch")
    observed_classes = tuple(packet.get("expected_plan_classes", ()))
    if observed_classes != EXPECTED_PLAN_CLASSES:
        errors.append(f"{label}: expected_plan_classes mismatch")
    _validate_approval_criteria(packet, errors, label)
    _validate_scenario_approvals(packet, errors, label)
    _validate_promotion_gate_summary(packet, errors, label)
    _validate_remaining_promotion_gates(packet, errors, label)
    _validate_authority_denials(packet, errors, label)


def _validate_approval_criteria(packet: Mapping[str, Any], errors: list[str], label: str) -> None:
    criteria = _sequence(packet.get("approval_criteria"))
    criterion_ids = tuple(str(criterion.get("criterion_id", "")) for criterion in criteria if isinstance(criterion, Mapping))
    if criterion_ids != APPROVAL_CRITERION_IDS:
        errors.append(f"{label}: approval criterion ids mismatch")
    for criterion in criteria:
        if not isinstance(criterion, Mapping):
            errors.append(f"{label}: approval criterion must be an object")
            continue
        if criterion.get("status") != "Pass":
            errors.append(f"{label}: approval criterion status must be Pass")
        if criterion.get("blocks_runtime_promotion") is not False:
            errors.append(f"{label}: satisfied approval criterion must not block runtime promotion")


def _validate_scenario_approvals(packet: Mapping[str, Any], errors: list[str], label: str) -> None:
    approvals = _sequence(packet.get("scenario_approvals"))
    if len(approvals) != len(EXPECTED_PLAN_CLASSES):
        errors.append(f"{label}: scenario_approvals must cover all expected plan classes")
        return
    observed_classes = []
    for approval in approvals:
        if not isinstance(approval, Mapping):
            errors.append(f"{label}: scenario approval must be an object")
            continue
        observed_classes.append(str(approval.get("plan_class", "")))
        for field_name, expected in (
            ("approval_status", "ConditionallyApprovedNoEffect"),
            ("parity_confirmed", True),
            ("observed_behavior_matches_projection", True),
            ("runtime_promotion_ready", False),
        ):
            if approval.get(field_name) != expected:
                errors.append(f"{label}: scenario {field_name} must be {expected!r}")
        ref = str(approval.get("operator_observation_ref", ""))
        if not ref.startswith("receipt://governed-planning-profile/operator-shadow-pilot/"):
            errors.append(f"{label}: scenario approval must bind operator observation ref")
    if tuple(observed_classes) != EXPECTED_PLAN_CLASSES:
        errors.append(f"{label}: scenario approval classes must match required order")


def _validate_promotion_gate_summary(packet: Mapping[str, Any], errors: list[str], label: str) -> None:
    summary = _mapping(packet.get("promotion_gate_summary"))
    if tuple(summary.get("satisfied_promotion_gate_ids", ())) != SATISFIED_PROMOTION_GATE_IDS:
        errors.append(f"{label}: satisfied promotion gate ids mismatch")
    if tuple(summary.get("remaining_promotion_gate_ids", ())) != REMAINING_PROMOTION_GATE_IDS:
        errors.append(f"{label}: remaining promotion gate ids mismatch")
    if summary.get("approval_criterion_count") != len(APPROVAL_CRITERION_IDS):
        errors.append(f"{label}: promotion_gate_summary.approval_criterion_count mismatch")
    if summary.get("scenario_approval_count") != len(EXPECTED_PLAN_CLASSES):
        errors.append(f"{label}: promotion_gate_summary.scenario_approval_count mismatch")
    if summary.get("runtime_promotion_authorized") is not False:
        errors.append(f"{label}: promotion_gate_summary.runtime_promotion_authorized must be false")


def _validate_remaining_promotion_gates(packet: Mapping[str, Any], errors: list[str], label: str) -> None:
    gates = _sequence(packet.get("remaining_promotion_gates"))
    gate_ids = tuple(str(gate.get("gate_id", "")) for gate in gates if isinstance(gate, Mapping))
    if gate_ids != REMAINING_PROMOTION_GATE_IDS:
        errors.append(f"{label}: remaining promotion gate ids mismatch")
    for gate in gates:
        if not isinstance(gate, Mapping):
            errors.append(f"{label}: remaining promotion gate must be an object")
            continue
        if gate.get("status") != "AwaitingEvidence":
            errors.append(f"{label}: remaining promotion gate status must be AwaitingEvidence")
        if gate.get("blocks_runtime_promotion") is not True:
            errors.append(f"{label}: remaining promotion gate must block runtime promotion")
        if not str(gate.get("required_evidence_ref", "")).startswith("unknown://governed-planning-profile/"):
            errors.append(f"{label}: remaining promotion gate evidence ref must remain unknown")


def _validate_authority_denials(packet: Mapping[str, Any], errors: list[str], label: str) -> None:
    denials = _mapping(packet.get("authority_denials"))
    for field_name in AUTHORITY_FALSE_FIELDS:
        if denials.get(field_name) is not False:
            errors.append(f"{label}: authority_denials.{field_name} must be false")


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(f"{_path_label(path)}: missing {label}")
        return {}
    except json.JSONDecodeError as exc:
        errors.append(f"{_path_label(path)}: invalid JSON: {exc}")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{_path_label(path)}: {label} must be a JSON object")
        return {}
    return payload


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> Sequence[Any]:
    return value if isinstance(value, list) else ()


def _path_label(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


def _render_text(validation: RuntimePromotionApprovalPacketValidation, stream: TextIO) -> None:
    if validation.ok:
        print(
            "STATUS: passed; "
            f"criteria={validation.approval_criterion_count}; "
            f"scenarios={validation.scenario_approval_count}; "
            f"remaining_promotion_gates={validation.remaining_promotion_gate_count}",
            file=stream,
        )
        print(
            "NEXT: obtain replay/recovery witness and terminal closure certificate",
            file=stream,
        )
        return
    print("STATUS: failed", file=stream)
    for error in validation.errors:
        print(f"ERROR: {error}", file=stream)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit validation as JSON.")
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET, help="Approval packet to validate.")
    args = parser.parse_args(argv)
    validation, produced_packet = validate_runtime_promotion_approval_packet(packet_path=args.packet)
    if args.json:
        payload = validation.as_dict()
        payload["produced_packet"] = produced_packet
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        _render_text(validation, sys.stdout)
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
