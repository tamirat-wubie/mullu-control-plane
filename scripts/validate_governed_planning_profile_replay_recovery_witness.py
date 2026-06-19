#!/usr/bin/env python3
"""Validate GovernedPlanningProfile replay/recovery witness.

Purpose: emit and validate a local-only replay/recovery witness for the
GovernedPlanningProfile runtime-promotion evidence ladder.
Governance scope: OCE replay/recovery control completeness, RAG approval packet
binding, CDCV hash traceability, CQTE no-authority constraints, UWMA witness
anchoring, SRCA bounded scenario enumeration, and PRS validation.
Dependencies: runtime-promotion approval packet validator, schema validator,
and canonical hashing.
Invariants:
  - The witness records replay/recovery evidence only; it does not execute
    replay or rollback.
  - The witness never grants runtime promotion, execution, dispatch,
    replanning, success, or terminal closure authority.
  - Terminal closure evidence remains required before runtime promotion can be
    authorized.
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
from scripts.validate_governed_planning_profile_runtime_promotion_approval_packet import (  # noqa: E402
    EXPECTED_PLAN_CLASSES,
    GENERATED_AT,
    build_runtime_promotion_approval_packet,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


SCHEMA_VERSION = "governed_planning_profile_replay_recovery_witness.v1"
WITNESS_ID_PREFIX = "governed-planning-profile-replay-recovery-witness"
DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "governed_planning_profile_replay_recovery_witness.schema.json"
DEFAULT_WITNESS = REPO_ROOT / "examples" / "governed_planning_profile_replay_recovery_witness.local.json"
SATISFIED_PROMOTION_GATE_IDS = (
    "operator_shadow_pilot_observation",
    "runtime_promotion_approval",
    "replay_recovery_witness",
)
REMAINING_PROMOTION_GATE_IDS = ("terminal_closure_certificate",)
REPLAY_RECOVERY_CONTROL_IDS = (
    "source_approval_packet_valid",
    "all_plan_classes_replay_probe_bound",
    "zero_replay_mismatches",
    "rollback_plan_documented",
    "recovery_handoff_documented",
    "authority_denials_preserved",
    "foundation_no_effect_boundary_preserved",
)


@dataclass(frozen=True, slots=True)
class ReplayRecoveryWitnessValidation:
    """Validation result for the planning-profile replay/recovery witness."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    witness_path: str
    witness_id: str
    source_approval_packet_id: str
    replay_recovery_control_count: int
    scenario_witness_count: int
    remaining_promotion_gate_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def build_replay_recovery_witness(
    approval_packet: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the deterministic local replay/recovery witness."""

    current_approval_packet = dict(approval_packet or build_runtime_promotion_approval_packet())
    scenario_witnesses = tuple(_scenario_replay_witnesses(current_approval_packet))
    controls = tuple(_replay_recovery_controls(current_approval_packet))
    remaining_gates = tuple(_remaining_promotion_gates())
    payload: dict[str, Any] = {
        "witness_id": "pending",
        "schema_version": SCHEMA_VERSION,
        "profile_id": str(current_approval_packet.get("profile_id", "")),
        "witnessed_at": GENERATED_AT,
        "solver_outcome": "AwaitingEvidence",
        "replay_recovery_witness_status": "CollectedNoEffect",
        "replay_recovery_gate_satisfied": True,
        "local_witness_only": True,
        "read_only": True,
        "mutation_route": False,
        "runtime_behavior_change": False,
        "runtime_promotion_authorized": False,
        "execution_allowed": False,
        "dispatch_allowed": False,
        "runtime_replanning_enabled": False,
        "success_claim_allowed": False,
        "terminal_closure": False,
        "replay_execution_performed": False,
        "rollback_execution_performed": False,
        "source_runtime_promotion_approval_packet": {
            "packet_id": str(current_approval_packet.get("packet_id", "")),
            "packet_hash": str(current_approval_packet.get("packet_hash", "")),
            "runtime_promotion_approval_status": str(
                current_approval_packet.get("runtime_promotion_approval_status", "")
            ),
            "runtime_promotion_approval_collected": bool(
                current_approval_packet.get("runtime_promotion_approval_collected")
            ),
            "runtime_promotion_gate_satisfied": bool(
                current_approval_packet.get("runtime_promotion_gate_satisfied")
            ),
            "scenario_approval_count": int(
                _mapping(current_approval_packet.get("promotion_gate_summary")).get(
                    "scenario_approval_count",
                    0,
                )
            ),
            "remaining_promotion_gate_count": int(
                len(_sequence(current_approval_packet.get("remaining_promotion_gates")))
            ),
        },
        "expected_plan_classes": list(EXPECTED_PLAN_CLASSES),
        "replay_recovery_controls": list(controls),
        "scenario_replay_witnesses": list(scenario_witnesses),
        "recovery_boundary": {
            "rollback_plan_documented": True,
            "recovery_handoff_documented": True,
            "incident_handoff_required_if_drift": True,
            "terminal_closure_required": True,
            "replay_execution_performed": False,
            "rollback_execution_performed": False,
        },
        "promotion_gate_summary": {
            "satisfied_promotion_gate_ids": list(SATISFIED_PROMOTION_GATE_IDS),
            "remaining_promotion_gate_ids": list(REMAINING_PROMOTION_GATE_IDS),
            "replay_recovery_control_count": len(controls),
            "scenario_witness_count": len(scenario_witnesses),
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
            "scripts/validate_governed_planning_profile_runtime_promotion_approval_packet.py",
            "scripts/validate_governed_planning_profile_replay_recovery_witness.py",
            "schemas/governed_planning_profile_replay_recovery_witness.schema.json",
            "examples/governed_planning_profile_replay_recovery_witness.local.json",
            "tests/test_validate_governed_planning_profile_replay_recovery_witness.py",
        ],
        "validators": [
            {
                "validator_id": "governed-planning-profile-replay-recovery-witness",
                "command": (
                    "python scripts/"
                    "validate_governed_planning_profile_replay_recovery_witness.py"
                ),
            }
        ],
        "next_action": "obtain terminal closure certificate before runtime promotion",
        "witness_hash": "",
    }
    witness_hash = canonical_hash(payload)
    payload["witness_id"] = f"{WITNESS_ID_PREFIX}-{witness_hash[:16]}"
    payload["witness_hash"] = witness_hash
    return payload


def validate_replay_recovery_witness(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    witness_path: Path = DEFAULT_WITNESS,
) -> tuple[ReplayRecoveryWitnessValidation, dict[str, Any]]:
    """Validate the checked-in replay/recovery witness and produced witness."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "replay/recovery witness schema", errors)
    witness = _load_json_object(witness_path, "replay/recovery witness", errors)
    produced_witness = build_replay_recovery_witness()
    if schema and witness:
        errors.extend(f"{_path_label(witness_path)}: {error}" for error in _validate_schema_instance(schema, witness))
        _validate_witness_semantics(witness, errors, _path_label(witness_path))
    if schema:
        errors.extend(
            f"produced replay/recovery witness: {error}"
            for error in _validate_schema_instance(schema, produced_witness)
        )
        _validate_witness_semantics(produced_witness, errors, "produced replay/recovery witness")
    if witness and witness != produced_witness:
        errors.append("replay/recovery witness fixture does not match deterministic produced witness")

    observed = witness or produced_witness
    validation = ReplayRecoveryWitnessValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        witness_path=_path_label(witness_path),
        witness_id=str(observed.get("witness_id", "")),
        source_approval_packet_id=str(
            _mapping(observed.get("source_runtime_promotion_approval_packet")).get("packet_id", "")
        ),
        replay_recovery_control_count=len(_sequence(observed.get("replay_recovery_controls"))),
        scenario_witness_count=len(_sequence(observed.get("scenario_replay_witnesses"))),
        remaining_promotion_gate_count=len(_sequence(observed.get("remaining_promotion_gates"))),
    )
    return validation, produced_witness


def _replay_recovery_controls(approval_packet: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "control_id": "source_approval_packet_valid",
            "status": "Pass",
            "evidence_ref": str(approval_packet.get("packet_id", "")),
            "blocks_runtime_promotion": False,
        },
        {
            "control_id": "all_plan_classes_replay_probe_bound",
            "status": "Pass",
            "evidence_ref": "scenario_replay_witnesses",
            "blocks_runtime_promotion": False,
        },
        {
            "control_id": "zero_replay_mismatches",
            "status": "Pass",
            "evidence_ref": "scenario_replay_witnesses.replay_mismatch_count",
            "blocks_runtime_promotion": False,
        },
        {
            "control_id": "rollback_plan_documented",
            "status": "Pass",
            "evidence_ref": "recovery_boundary.rollback_plan_documented",
            "blocks_runtime_promotion": False,
        },
        {
            "control_id": "recovery_handoff_documented",
            "status": "Pass",
            "evidence_ref": "recovery_boundary.recovery_handoff_documented",
            "blocks_runtime_promotion": False,
        },
        {
            "control_id": "authority_denials_preserved",
            "status": "Pass",
            "evidence_ref": "authority_denials",
            "blocks_runtime_promotion": False,
        },
        {
            "control_id": "foundation_no_effect_boundary_preserved",
            "status": "Pass",
            "evidence_ref": "local_witness_only",
            "blocks_runtime_promotion": False,
        },
    ]


def _scenario_replay_witnesses(approval_packet: Mapping[str, Any]) -> list[dict[str, Any]]:
    witnesses: list[dict[str, Any]] = []
    for approval in _sequence(approval_packet.get("scenario_approvals")):
        if not isinstance(approval, Mapping):
            continue
        plan_class = str(approval.get("plan_class", ""))
        probe_material = {
            "scenario_id": str(approval.get("scenario_id", "")),
            "plan_class": plan_class,
            "operator_observation_ref": str(approval.get("operator_observation_ref", "")),
            "approval_status": str(approval.get("approval_status", "")),
            "witness_kind": "no_effect_replay_recovery_probe",
        }
        probe_hash = canonical_hash(probe_material)
        witnesses.append({
            "scenario_id": str(approval.get("scenario_id", "")),
            "plan_class": plan_class,
            "source_approval_status": str(approval.get("approval_status", "")),
            "operator_observation_ref": str(approval.get("operator_observation_ref", "")),
            "replay_probe_ref": f"hash://sha256/{probe_hash}",
            "replay_probe_status": "WitnessBound",
            "replay_mismatch_count": 0,
            "recovery_path_ref": f"recovery://governed-planning-profile/{plan_class}",
            "rollback_path_documented": True,
            "incident_handoff_documented": True,
            "replay_execution_performed": False,
            "rollback_execution_performed": False,
            "runtime_promotion_ready": False,
        })
    return witnesses


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


def _validate_witness_semantics(witness: Mapping[str, Any], errors: list[str], label: str) -> None:
    if witness.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"{label}: schema_version mismatch")
    if witness.get("solver_outcome") != "AwaitingEvidence":
        errors.append(f"{label}: solver_outcome must remain AwaitingEvidence")
    for field_name, expected in (
        ("replay_recovery_witness_status", "CollectedNoEffect"),
        ("replay_recovery_gate_satisfied", True),
        ("local_witness_only", True),
        ("read_only", True),
        ("mutation_route", False),
        ("runtime_behavior_change", False),
        ("replay_execution_performed", False),
        ("rollback_execution_performed", False),
        *tuple((field_name, False) for field_name in AUTHORITY_FALSE_FIELDS),
    ):
        observed = witness.get(field_name)
        if isinstance(expected, bool):
            drifted = observed is not expected
        else:
            drifted = observed != expected
        if drifted:
            errors.append(f"{label}: {field_name} must be {expected!r}")
    source_packet = _mapping(witness.get("source_runtime_promotion_approval_packet"))
    if source_packet.get("runtime_promotion_approval_status") != "ConditionallyApprovedNoEffect":
        errors.append(f"{label}: source approval status must be ConditionallyApprovedNoEffect")
    if source_packet.get("runtime_promotion_approval_collected") is not True:
        errors.append(f"{label}: source approval must be collected")
    if source_packet.get("runtime_promotion_gate_satisfied") is not True:
        errors.append(f"{label}: source runtime promotion approval gate must be satisfied")
    if source_packet.get("scenario_approval_count") != len(EXPECTED_PLAN_CLASSES):
        errors.append(f"{label}: source scenario approval count mismatch")
    observed_classes = tuple(witness.get("expected_plan_classes", ()))
    if observed_classes != EXPECTED_PLAN_CLASSES:
        errors.append(f"{label}: expected_plan_classes mismatch")
    _validate_controls(witness, errors, label)
    _validate_scenario_witnesses(witness, errors, label)
    _validate_recovery_boundary(witness, errors, label)
    _validate_promotion_gate_summary(witness, errors, label)
    _validate_remaining_promotion_gates(witness, errors, label)
    _validate_authority_denials(witness, errors, label)


def _validate_controls(witness: Mapping[str, Any], errors: list[str], label: str) -> None:
    controls = _sequence(witness.get("replay_recovery_controls"))
    control_ids = tuple(str(control.get("control_id", "")) for control in controls if isinstance(control, Mapping))
    if control_ids != REPLAY_RECOVERY_CONTROL_IDS:
        errors.append(f"{label}: replay/recovery control ids mismatch")
    for control in controls:
        if not isinstance(control, Mapping):
            errors.append(f"{label}: replay/recovery control must be an object")
            continue
        if control.get("status") != "Pass":
            errors.append(f"{label}: replay/recovery control status must be Pass")
        if control.get("blocks_runtime_promotion") is not False:
            errors.append(f"{label}: satisfied replay/recovery control must not block runtime promotion")


def _validate_scenario_witnesses(witness: Mapping[str, Any], errors: list[str], label: str) -> None:
    scenario_witnesses = _sequence(witness.get("scenario_replay_witnesses"))
    if len(scenario_witnesses) != len(EXPECTED_PLAN_CLASSES):
        errors.append(f"{label}: scenario_replay_witnesses must cover all expected plan classes")
        return
    observed_classes = []
    for scenario_witness in scenario_witnesses:
        if not isinstance(scenario_witness, Mapping):
            errors.append(f"{label}: scenario replay witness must be an object")
            continue
        observed_classes.append(str(scenario_witness.get("plan_class", "")))
        for field_name, expected in (
            ("source_approval_status", "ConditionallyApprovedNoEffect"),
            ("replay_probe_status", "WitnessBound"),
            ("replay_mismatch_count", 0),
            ("rollback_path_documented", True),
            ("incident_handoff_documented", True),
            ("replay_execution_performed", False),
            ("rollback_execution_performed", False),
            ("runtime_promotion_ready", False),
        ):
            if scenario_witness.get(field_name) != expected:
                errors.append(f"{label}: scenario {field_name} must be {expected!r}")
        if not str(scenario_witness.get("replay_probe_ref", "")).startswith("hash://sha256/"):
            errors.append(f"{label}: scenario replay_probe_ref must be digest-bound")
        if not str(scenario_witness.get("operator_observation_ref", "")).startswith(
            "receipt://governed-planning-profile/operator-shadow-pilot/"
        ):
            errors.append(f"{label}: scenario operator_observation_ref must be receipt-bound")
        if not str(scenario_witness.get("recovery_path_ref", "")).startswith(
            "recovery://governed-planning-profile/"
        ):
            errors.append(f"{label}: scenario recovery_path_ref must be recovery-bound")
    if tuple(observed_classes) != EXPECTED_PLAN_CLASSES:
        errors.append(f"{label}: scenario replay witness classes must match required order")


def _validate_recovery_boundary(witness: Mapping[str, Any], errors: list[str], label: str) -> None:
    boundary = _mapping(witness.get("recovery_boundary"))
    for field_name in (
        "rollback_plan_documented",
        "recovery_handoff_documented",
        "incident_handoff_required_if_drift",
        "terminal_closure_required",
    ):
        if boundary.get(field_name) is not True:
            errors.append(f"{label}: recovery_boundary.{field_name} must be true")
    for field_name in ("replay_execution_performed", "rollback_execution_performed"):
        if boundary.get(field_name) is not False:
            errors.append(f"{label}: recovery_boundary.{field_name} must be false")


def _validate_promotion_gate_summary(witness: Mapping[str, Any], errors: list[str], label: str) -> None:
    summary = _mapping(witness.get("promotion_gate_summary"))
    if tuple(summary.get("satisfied_promotion_gate_ids", ())) != SATISFIED_PROMOTION_GATE_IDS:
        errors.append(f"{label}: satisfied promotion gate ids mismatch")
    if tuple(summary.get("remaining_promotion_gate_ids", ())) != REMAINING_PROMOTION_GATE_IDS:
        errors.append(f"{label}: remaining promotion gate ids mismatch")
    if summary.get("replay_recovery_control_count") != len(REPLAY_RECOVERY_CONTROL_IDS):
        errors.append(f"{label}: promotion_gate_summary.replay_recovery_control_count mismatch")
    if summary.get("scenario_witness_count") != len(EXPECTED_PLAN_CLASSES):
        errors.append(f"{label}: promotion_gate_summary.scenario_witness_count mismatch")
    if summary.get("runtime_promotion_authorized") is not False:
        errors.append(f"{label}: promotion_gate_summary.runtime_promotion_authorized must be false")


def _validate_remaining_promotion_gates(witness: Mapping[str, Any], errors: list[str], label: str) -> None:
    gates = _sequence(witness.get("remaining_promotion_gates"))
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


def _validate_authority_denials(witness: Mapping[str, Any], errors: list[str], label: str) -> None:
    denials = _mapping(witness.get("authority_denials"))
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


def _render_text(validation: ReplayRecoveryWitnessValidation, stream: TextIO) -> None:
    if validation.ok:
        print(
            "STATUS: passed; "
            f"controls={validation.replay_recovery_control_count}; "
            f"scenarios={validation.scenario_witness_count}; "
            f"remaining_promotion_gates={validation.remaining_promotion_gate_count}",
            file=stream,
        )
        print("NEXT: obtain terminal closure certificate before runtime promotion", file=stream)
        return
    print("STATUS: failed", file=stream)
    for error in validation.errors:
        print(f"ERROR: {error}", file=stream)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit validation as JSON.")
    parser.add_argument("--witness", type=Path, default=DEFAULT_WITNESS, help="Replay/recovery witness to validate.")
    args = parser.parse_args(argv)
    validation, produced_witness = validate_replay_recovery_witness(witness_path=args.witness)
    if args.json:
        payload = validation.as_dict()
        payload["produced_witness"] = produced_witness
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        _render_text(validation, sys.stdout)
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
