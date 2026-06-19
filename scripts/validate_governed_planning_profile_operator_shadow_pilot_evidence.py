#!/usr/bin/env python3
"""Validate GovernedPlanningProfile operator shadow-pilot evidence request.

Purpose: emit and validate the local-only operator evidence request that must
be satisfied before GovernedPlanningProfile runtime promotion can be considered.
Governance scope: OCE evidence completeness, RAG dossier-to-evidence binding,
CDCV hash traceability, CQTE no-authority constraints, UWMA witness anchoring,
SRCA bounded scenario enumeration, and PRS validation.
Dependencies: governed planning profile shadow dossier reporter, schema
validator, canonical hashing, and the checked-in AwaitingEvidence fixture.
Invariants:
  - The packet is read-only and does not collect operator observations.
  - The packet never grants runtime promotion, execution, dispatch, replanning,
    success, or terminal closure authority.
  - All scenario observations remain AwaitingEvidence until a later operator
    witness record supplies concrete evidence.
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
from scripts.report_governed_planning_profile_shadow_dossier import (  # noqa: E402
    EXPECTED_PLAN_CLASSES,
    GENERATED_AT,
    build_shadow_dossier,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


SCHEMA_VERSION = "governed_planning_profile_operator_shadow_pilot_evidence.v1"
EVIDENCE_ID_PREFIX = "governed-planning-profile-operator-shadow-pilot-evidence"
DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "governed_planning_profile_operator_shadow_pilot_evidence.schema.json"
DEFAULT_FIXTURE = REPO_ROOT / "examples" / "governed_planning_profile_operator_shadow_pilot_evidence.awaiting_evidence.json"
AUTHORITY_FALSE_FIELDS = (
    "runtime_promotion_authorized",
    "execution_allowed",
    "dispatch_allowed",
    "runtime_replanning_enabled",
    "success_claim_allowed",
    "terminal_closure",
)


@dataclass(frozen=True, slots=True)
class OperatorShadowPilotEvidenceValidation:
    """Validation result for the planning-profile operator evidence request."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    fixture_path: str
    evidence_id: str
    source_dossier_id: str
    scenario_observation_count: int
    promotion_gate_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def build_operator_shadow_pilot_evidence_request(
    dossier: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the deterministic no-effect operator shadow-pilot evidence request."""

    current_dossier = dict(dossier or build_shadow_dossier())
    source_dossier_id = str(current_dossier.get("dossier_id", ""))
    source_dossier_hash = str(current_dossier.get("dossier_hash", ""))
    scenarios = tuple(_scenario_observations(current_dossier))
    promotion_gates = (
        {
            "gate_id": "operator_shadow_pilot_observation",
            "status": "AwaitingEvidence",
            "required_evidence_ref": "unknown://governed-planning-profile/operator-shadow-pilot",
            "blocks_runtime_promotion": True,
        },
        {
            "gate_id": "runtime_promotion_approval",
            "status": "AwaitingEvidence",
            "required_evidence_ref": "unknown://governed-planning-profile/runtime-promotion-approval",
            "blocks_runtime_promotion": True,
        },
        {
            "gate_id": "replay_recovery_witness",
            "status": "AwaitingEvidence",
            "required_evidence_ref": "unknown://governed-planning-profile/replay-recovery-witness",
            "blocks_runtime_promotion": True,
        },
        {
            "gate_id": "terminal_closure_certificate",
            "status": "AwaitingEvidence",
            "required_evidence_ref": "unknown://governed-planning-profile/terminal-closure-certificate",
            "blocks_runtime_promotion": True,
        },
    )
    payload: dict[str, Any] = {
        "evidence_id": "pending",
        "schema_version": SCHEMA_VERSION,
        "profile_id": str(current_dossier.get("profile_id", "")),
        "generated_at": GENERATED_AT,
        "solver_outcome": "AwaitingEvidence",
        "operator_evidence_status": "AwaitingEvidence",
        "operator_observation_collected": False,
        "read_only": True,
        "mutation_route": False,
        "runtime_behavior_change": False,
        "runtime_promotion_authorized": False,
        "execution_allowed": False,
        "dispatch_allowed": False,
        "runtime_replanning_enabled": False,
        "success_claim_allowed": False,
        "terminal_closure": False,
        "source_dossier": {
            "dossier_id": source_dossier_id,
            "dossier_hash": source_dossier_hash,
            "scenario_count": int(current_dossier.get("scenario_count", 0)),
            "report_count": int(current_dossier.get("report_count", 0)),
            "promotion_blocker_count": int(current_dossier.get("promotion_blocker_count", 0)),
            "shadow_mismatch_count": int(current_dossier.get("shadow_mismatch_count", 0)),
            "status": str(current_dossier.get("status", "")),
        },
        "expected_plan_classes": list(EXPECTED_PLAN_CLASSES),
        "scenario_observations": list(scenarios),
        "promotion_gates": list(promotion_gates),
        "authority_denials": {
            "runtime_promotion_authorized": False,
            "execution_allowed": False,
            "dispatch_allowed": False,
            "runtime_replanning_enabled": False,
            "success_claim_allowed": False,
            "terminal_closure": False,
        },
        "evidence_refs": [
            "scripts/report_governed_planning_profile_shadow_dossier.py",
            "scripts/validate_governed_planning_profile_operator_shadow_pilot_evidence.py",
            "schemas/governed_planning_profile_operator_shadow_pilot_evidence.schema.json",
            "examples/governed_planning_profile_operator_shadow_pilot_evidence.awaiting_evidence.json",
            "tests/test_validate_governed_planning_profile_operator_shadow_pilot_evidence.py",
        ],
        "validators": [
            {
                "validator_id": "governed-planning-profile-operator-shadow-pilot-evidence",
                "command": "python scripts/validate_governed_planning_profile_operator_shadow_pilot_evidence.py",
            }
        ],
        "next_action": "record concrete operator shadow-pilot observations before runtime promotion",
        "evidence_hash": "",
    }
    evidence_hash = canonical_hash(payload)
    payload["evidence_id"] = f"{EVIDENCE_ID_PREFIX}-{evidence_hash[:16]}"
    payload["evidence_hash"] = evidence_hash
    return payload


def validate_operator_shadow_pilot_evidence(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    fixture_path: Path = DEFAULT_FIXTURE,
) -> tuple[OperatorShadowPilotEvidenceValidation, dict[str, Any]]:
    """Validate the checked-in evidence request fixture and produced packet."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "operator shadow-pilot evidence schema", errors)
    fixture = _load_json_object(fixture_path, "operator shadow-pilot evidence fixture", errors)
    produced_request = build_operator_shadow_pilot_evidence_request()
    if schema and fixture:
        errors.extend(f"{_path_label(fixture_path)}: {error}" for error in _validate_schema_instance(schema, fixture))
        _validate_packet_semantics(fixture, errors, _path_label(fixture_path))
    if schema:
        errors.extend(
            f"produced operator shadow-pilot evidence: {error}"
            for error in _validate_schema_instance(schema, produced_request)
        )
        _validate_packet_semantics(produced_request, errors, "produced operator shadow-pilot evidence")
    if fixture and fixture != produced_request:
        errors.append("operator shadow-pilot evidence fixture does not match deterministic produced packet")

    observed = fixture or produced_request
    validation = OperatorShadowPilotEvidenceValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        fixture_path=_path_label(fixture_path),
        evidence_id=str(observed.get("evidence_id", "")),
        source_dossier_id=str(_mapping(observed.get("source_dossier")).get("dossier_id", "")),
        scenario_observation_count=len(_sequence(observed.get("scenario_observations"))),
        promotion_gate_count=len(_sequence(observed.get("promotion_gates"))),
    )
    return validation, produced_request


def _scenario_observations(dossier: Mapping[str, Any]) -> list[dict[str, Any]]:
    scenarios = _sequence(dossier.get("scenarios"))
    observations: list[dict[str, Any]] = []
    for scenario in scenarios:
        if not isinstance(scenario, Mapping):
            continue
        plan_class = str(scenario.get("plan_class", ""))
        observations.append({
            "scenario_id": str(scenario.get("scenario_id", "")),
            "plan_class": plan_class,
            "source_plan_id": str(scenario.get("source_plan_id", "")),
            "admission_report_id": str(scenario.get("admission_report_id", "")),
            "operator_observation_status": "AwaitingEvidence",
            "operator_observation_ref": f"unknown://governed-planning-profile/operator-shadow-pilot/{plan_class}",
            "parity_confirmed": False,
            "observed_behavior_matches_projection": False,
            "runtime_promotion_ready": False,
        })
    return observations


def _validate_packet_semantics(packet: Mapping[str, Any], errors: list[str], label: str) -> None:
    if packet.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"{label}: schema_version mismatch")
    if packet.get("solver_outcome") != "AwaitingEvidence":
        errors.append(f"{label}: solver_outcome must be AwaitingEvidence")
    if packet.get("operator_evidence_status") != "AwaitingEvidence":
        errors.append(f"{label}: operator_evidence_status must be AwaitingEvidence")
    for field_name, expected in (
        ("operator_observation_collected", False),
        ("read_only", True),
        ("mutation_route", False),
        ("runtime_behavior_change", False),
        *tuple((field_name, False) for field_name in AUTHORITY_FALSE_FIELDS),
    ):
        if packet.get(field_name) is not expected:
            errors.append(f"{label}: {field_name} must be {expected!r}")
    source_dossier = _mapping(packet.get("source_dossier"))
    if source_dossier.get("status") != "verified":
        errors.append(f"{label}: source_dossier.status must be verified")
    if source_dossier.get("scenario_count") != len(EXPECTED_PLAN_CLASSES):
        errors.append(f"{label}: source_dossier.scenario_count mismatch")
    observed_classes = tuple(packet.get("expected_plan_classes", ()))
    if observed_classes != EXPECTED_PLAN_CLASSES:
        errors.append(f"{label}: expected_plan_classes mismatch")
    _validate_scenario_observations(packet, errors, label)
    _validate_promotion_gates(packet, errors, label)
    _validate_authority_denials(packet, errors, label)


def _validate_scenario_observations(packet: Mapping[str, Any], errors: list[str], label: str) -> None:
    observations = _sequence(packet.get("scenario_observations"))
    if len(observations) != len(EXPECTED_PLAN_CLASSES):
        errors.append(f"{label}: scenario_observations must cover all expected plan classes")
        return
    observed_classes = []
    for observation in observations:
        if not isinstance(observation, Mapping):
            errors.append(f"{label}: scenario observation must be an object")
            continue
        observed_classes.append(str(observation.get("plan_class", "")))
        for field_name, expected in (
            ("operator_observation_status", "AwaitingEvidence"),
            ("parity_confirmed", False),
            ("observed_behavior_matches_projection", False),
            ("runtime_promotion_ready", False),
        ):
            if observation.get(field_name) != expected:
                errors.append(f"{label}: scenario {field_name} must be {expected!r}")
        ref = str(observation.get("operator_observation_ref", ""))
        if not ref.startswith("unknown://governed-planning-profile/operator-shadow-pilot/"):
            errors.append(f"{label}: scenario operator_observation_ref must remain unknown")
    if tuple(observed_classes) != EXPECTED_PLAN_CLASSES:
        errors.append(f"{label}: scenario observation classes must match required order")


def _validate_promotion_gates(packet: Mapping[str, Any], errors: list[str], label: str) -> None:
    gates = _sequence(packet.get("promotion_gates"))
    if len(gates) < 4:
        errors.append(f"{label}: promotion_gates must include required blockers")
    for gate in gates:
        if not isinstance(gate, Mapping):
            errors.append(f"{label}: promotion gate must be an object")
            continue
        if gate.get("status") != "AwaitingEvidence":
            errors.append(f"{label}: promotion gate status must be AwaitingEvidence")
        if gate.get("blocks_runtime_promotion") is not True:
            errors.append(f"{label}: promotion gate must block runtime promotion")
        if not str(gate.get("required_evidence_ref", "")).startswith("unknown://governed-planning-profile/"):
            errors.append(f"{label}: promotion gate evidence ref must remain unknown")


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


def _render_text(validation: OperatorShadowPilotEvidenceValidation, stream: TextIO) -> None:
    if validation.ok:
        print(
            "STATUS: passed; "
            f"scenarios={validation.scenario_observation_count}; "
            f"promotion_gates={validation.promotion_gate_count}",
            file=stream,
        )
        print("NEXT: record concrete operator shadow-pilot observations before runtime promotion", file=stream)
        return
    print("STATUS: failed", file=stream)
    for error in validation.errors:
        print(f"ERROR: {error}", file=stream)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit validation as JSON.")
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE, help="Evidence fixture to validate.")
    args = parser.parse_args(argv)
    validation, produced_request = validate_operator_shadow_pilot_evidence(fixture_path=args.fixture)
    if args.json:
        payload = validation.as_dict()
        payload["produced_request"] = produced_request
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        _render_text(validation, sys.stdout)
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
