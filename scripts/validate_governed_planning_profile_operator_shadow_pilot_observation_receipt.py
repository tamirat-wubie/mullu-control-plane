#!/usr/bin/env python3
"""Validate GovernedPlanningProfile operator shadow-pilot observation receipt.

Purpose: emit and validate a local-only observation receipt for the
GovernedPlanningProfile shadow-pilot evidence request.
Governance scope: OCE observation completeness, RAG evidence-request binding,
CDCV hash traceability, CQTE no-authority constraints, UWMA witness anchoring,
SRCA bounded scenario enumeration, and PRS validation.
Dependencies: governed planning profile shadow dossier reporter, operator
shadow-pilot evidence request validator, schema validator, and canonical
hashing.
Invariants:
  - The receipt records deterministic local observations only.
  - The receipt never grants runtime promotion, execution, dispatch,
    replanning, success, or terminal closure authority.
  - Runtime promotion remains blocked until approval, replay/recovery, and
    terminal closure evidence exist.
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
from scripts.validate_governed_planning_profile_operator_shadow_pilot_evidence import (  # noqa: E402
    AUTHORITY_FALSE_FIELDS,
    build_operator_shadow_pilot_evidence_request,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


SCHEMA_VERSION = "governed_planning_profile_operator_shadow_pilot_observation_receipt.v1"
RECEIPT_ID_PREFIX = "governed-planning-profile-operator-shadow-pilot-observation-receipt"
DEFAULT_SCHEMA = (
    REPO_ROOT
    / "schemas"
    / "governed_planning_profile_operator_shadow_pilot_observation_receipt.schema.json"
)
DEFAULT_RECEIPT = (
    REPO_ROOT
    / "examples"
    / "governed_planning_profile_operator_shadow_pilot_observation_receipt.local.json"
)
REMAINING_PROMOTION_GATE_IDS = (
    "runtime_promotion_approval",
    "replay_recovery_witness",
    "terminal_closure_certificate",
)


@dataclass(frozen=True, slots=True)
class OperatorShadowPilotObservationReceiptValidation:
    """Validation result for the planning-profile observation receipt."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    receipt_path: str
    receipt_id: str
    source_evidence_id: str
    scenario_observation_count: int
    remaining_promotion_gate_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def build_operator_shadow_pilot_observation_receipt(
    dossier: Mapping[str, Any] | None = None,
    evidence_request: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the deterministic local observation receipt."""

    current_dossier = dict(dossier or build_shadow_dossier())
    current_evidence_request = dict(
        evidence_request or build_operator_shadow_pilot_evidence_request(current_dossier)
    )
    scenario_observations = tuple(_scenario_observations(current_dossier))
    remaining_gates = tuple(_remaining_promotion_gates())
    payload: dict[str, Any] = {
        "receipt_id": "pending",
        "schema_version": SCHEMA_VERSION,
        "profile_id": str(current_dossier.get("profile_id", "")),
        "observed_at": GENERATED_AT,
        "solver_outcome": "AwaitingEvidence",
        "operator_observation_status": "Collected",
        "operator_observation_collected": True,
        "local_observation_only": True,
        "read_only": True,
        "mutation_route": False,
        "runtime_behavior_change": False,
        "runtime_promotion_authorized": False,
        "execution_allowed": False,
        "dispatch_allowed": False,
        "runtime_replanning_enabled": False,
        "success_claim_allowed": False,
        "terminal_closure": False,
        "source_evidence_request": {
            "evidence_id": str(current_evidence_request.get("evidence_id", "")),
            "evidence_hash": str(current_evidence_request.get("evidence_hash", "")),
            "operator_evidence_status": str(current_evidence_request.get("operator_evidence_status", "")),
            "operator_observation_collected": bool(
                current_evidence_request.get("operator_observation_collected")
            ),
        },
        "source_dossier": {
            "dossier_id": str(current_dossier.get("dossier_id", "")),
            "dossier_hash": str(current_dossier.get("dossier_hash", "")),
            "scenario_count": int(current_dossier.get("scenario_count", 0)),
            "report_count": int(current_dossier.get("report_count", 0)),
            "promotion_blocker_count": int(current_dossier.get("promotion_blocker_count", 0)),
            "shadow_mismatch_count": int(current_dossier.get("shadow_mismatch_count", 0)),
            "status": str(current_dossier.get("status", "")),
        },
        "expected_plan_classes": list(EXPECTED_PLAN_CLASSES),
        "scenario_observations": list(scenario_observations),
        "observation_summary": {
            "scenario_observation_count": len(scenario_observations),
            "parity_confirmed_count": sum(
                1 for observation in scenario_observations if observation["parity_confirmed"] is True
            ),
            "projection_match_count": sum(
                1
                for observation in scenario_observations
                if observation["observed_behavior_matches_projection"] is True
            ),
            "runtime_promotion_ready_count": sum(
                1 for observation in scenario_observations if observation["runtime_promotion_ready"] is True
            ),
            "remaining_promotion_gate_count": len(remaining_gates),
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
            "scripts/report_governed_planning_profile_shadow_dossier.py",
            "scripts/validate_governed_planning_profile_operator_shadow_pilot_evidence.py",
            "scripts/validate_governed_planning_profile_operator_shadow_pilot_observation_receipt.py",
            "schemas/governed_planning_profile_operator_shadow_pilot_observation_receipt.schema.json",
            "examples/governed_planning_profile_operator_shadow_pilot_observation_receipt.local.json",
            "tests/test_validate_governed_planning_profile_operator_shadow_pilot_observation_receipt.py",
        ],
        "validators": [
            {
                "validator_id": "governed-planning-profile-operator-shadow-pilot-observation-receipt",
                "command": (
                    "python scripts/"
                    "validate_governed_planning_profile_operator_shadow_pilot_observation_receipt.py"
                ),
            }
        ],
        "next_action": (
            "obtain runtime promotion approval, replay/recovery witness, and terminal closure certificate "
            "before runtime promotion"
        ),
        "receipt_hash": "",
    }
    receipt_hash = canonical_hash(payload)
    payload["receipt_id"] = f"{RECEIPT_ID_PREFIX}-{receipt_hash[:16]}"
    payload["receipt_hash"] = receipt_hash
    return payload


def validate_operator_shadow_pilot_observation_receipt(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    receipt_path: Path = DEFAULT_RECEIPT,
) -> tuple[OperatorShadowPilotObservationReceiptValidation, dict[str, Any]]:
    """Validate the checked-in observation receipt and produced receipt."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "operator shadow-pilot observation receipt schema", errors)
    receipt = _load_json_object(receipt_path, "operator shadow-pilot observation receipt", errors)
    produced_receipt = build_operator_shadow_pilot_observation_receipt()
    if schema and receipt:
        errors.extend(f"{_path_label(receipt_path)}: {error}" for error in _validate_schema_instance(schema, receipt))
        _validate_receipt_semantics(receipt, errors, _path_label(receipt_path))
    if schema:
        errors.extend(
            f"produced operator shadow-pilot observation receipt: {error}"
            for error in _validate_schema_instance(schema, produced_receipt)
        )
        _validate_receipt_semantics(produced_receipt, errors, "produced operator shadow-pilot observation receipt")
    if receipt and receipt != produced_receipt:
        errors.append("operator shadow-pilot observation receipt fixture does not match deterministic produced receipt")

    observed = receipt or produced_receipt
    validation = OperatorShadowPilotObservationReceiptValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        receipt_path=_path_label(receipt_path),
        receipt_id=str(observed.get("receipt_id", "")),
        source_evidence_id=str(_mapping(observed.get("source_evidence_request")).get("evidence_id", "")),
        scenario_observation_count=len(_sequence(observed.get("scenario_observations"))),
        remaining_promotion_gate_count=len(_sequence(observed.get("remaining_promotion_gates"))),
    )
    return validation, produced_receipt


def _scenario_observations(dossier: Mapping[str, Any]) -> list[dict[str, Any]]:
    scenarios = _sequence(dossier.get("scenarios"))
    observations: list[dict[str, Any]] = []
    for scenario in scenarios:
        if not isinstance(scenario, Mapping):
            continue
        plan_class = str(scenario.get("plan_class", ""))
        mismatch_count = int(scenario.get("shadow_mismatch_count", -1))
        observations.append({
            "scenario_id": str(scenario.get("scenario_id", "")),
            "plan_class": plan_class,
            "source_plan_id": str(scenario.get("source_plan_id", "")),
            "admission_report_id": str(scenario.get("admission_report_id", "")),
            "admission_decision": str(scenario.get("admission_decision", "")),
            "shadow_parity_status": str(scenario.get("shadow_parity_status", "")),
            "solver_outcome": str(scenario.get("solver_outcome", "")),
            "risk_tier": str(scenario.get("risk_tier", "")),
            "promotion_blocker_count": int(scenario.get("promotion_blocker_count", 0)),
            "shadow_mismatch_count": mismatch_count,
            "operator_observation_status": "Collected",
            "operator_observation_ref": f"receipt://governed-planning-profile/operator-shadow-pilot/{plan_class}",
            "parity_confirmed": mismatch_count == 0,
            "observed_behavior_matches_projection": mismatch_count == 0,
            "runtime_promotion_ready": False,
        })
    return observations


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


def _validate_receipt_semantics(receipt: Mapping[str, Any], errors: list[str], label: str) -> None:
    if receipt.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"{label}: schema_version mismatch")
    if receipt.get("solver_outcome") != "AwaitingEvidence":
        errors.append(f"{label}: solver_outcome must remain AwaitingEvidence")
    for field_name, expected in (
        ("operator_observation_status", "Collected"),
        ("operator_observation_collected", True),
        ("local_observation_only", True),
        ("read_only", True),
        ("mutation_route", False),
        ("runtime_behavior_change", False),
        *tuple((field_name, False) for field_name in AUTHORITY_FALSE_FIELDS),
    ):
        observed = receipt.get(field_name)
        if isinstance(expected, bool):
            drifted = observed is not expected
        else:
            drifted = observed != expected
        if drifted:
            errors.append(f"{label}: {field_name} must be {expected!r}")
    source_request = _mapping(receipt.get("source_evidence_request"))
    if source_request.get("operator_evidence_status") != "AwaitingEvidence":
        errors.append(f"{label}: source evidence request status must be AwaitingEvidence")
    if source_request.get("operator_observation_collected") is not False:
        errors.append(f"{label}: source evidence request must remain uncollected")
    source_dossier = _mapping(receipt.get("source_dossier"))
    if source_dossier.get("status") != "verified":
        errors.append(f"{label}: source_dossier.status must be verified")
    if source_dossier.get("shadow_mismatch_count") != 0:
        errors.append(f"{label}: source_dossier.shadow_mismatch_count must be zero")
    observed_classes = tuple(receipt.get("expected_plan_classes", ()))
    if observed_classes != EXPECTED_PLAN_CLASSES:
        errors.append(f"{label}: expected_plan_classes mismatch")
    _validate_scenario_observations(receipt, errors, label)
    _validate_observation_summary(receipt, errors, label)
    _validate_remaining_promotion_gates(receipt, errors, label)
    _validate_authority_denials(receipt, errors, label)


def _validate_scenario_observations(receipt: Mapping[str, Any], errors: list[str], label: str) -> None:
    observations = _sequence(receipt.get("scenario_observations"))
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
            ("operator_observation_status", "Collected"),
            ("parity_confirmed", True),
            ("observed_behavior_matches_projection", True),
            ("runtime_promotion_ready", False),
            ("shadow_mismatch_count", 0),
        ):
            if observation.get(field_name) != expected:
                errors.append(f"{label}: scenario {field_name} must be {expected!r}")
        if str(observation.get("solver_outcome", "")) != "AwaitingEvidence":
            errors.append(f"{label}: scenario solver_outcome must remain AwaitingEvidence")
        ref = str(observation.get("operator_observation_ref", ""))
        if not ref.startswith("receipt://governed-planning-profile/operator-shadow-pilot/"):
            errors.append(f"{label}: scenario operator_observation_ref must be receipt-bound")
    if tuple(observed_classes) != EXPECTED_PLAN_CLASSES:
        errors.append(f"{label}: scenario observation classes must match required order")


def _validate_observation_summary(receipt: Mapping[str, Any], errors: list[str], label: str) -> None:
    summary = _mapping(receipt.get("observation_summary"))
    observations = _sequence(receipt.get("scenario_observations"))
    if summary.get("scenario_observation_count") != len(observations):
        errors.append(f"{label}: observation_summary.scenario_observation_count mismatch")
    if summary.get("parity_confirmed_count") != len(observations):
        errors.append(f"{label}: observation_summary.parity_confirmed_count mismatch")
    if summary.get("projection_match_count") != len(observations):
        errors.append(f"{label}: observation_summary.projection_match_count mismatch")
    if summary.get("runtime_promotion_ready_count") != 0:
        errors.append(f"{label}: observation_summary.runtime_promotion_ready_count must be zero")
    if summary.get("remaining_promotion_gate_count") != len(REMAINING_PROMOTION_GATE_IDS):
        errors.append(f"{label}: observation_summary.remaining_promotion_gate_count mismatch")


def _validate_remaining_promotion_gates(receipt: Mapping[str, Any], errors: list[str], label: str) -> None:
    gates = _sequence(receipt.get("remaining_promotion_gates"))
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


def _validate_authority_denials(receipt: Mapping[str, Any], errors: list[str], label: str) -> None:
    denials = _mapping(receipt.get("authority_denials"))
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


def _render_text(validation: OperatorShadowPilotObservationReceiptValidation, stream: TextIO) -> None:
    if validation.ok:
        print(
            "STATUS: passed; "
            f"scenarios={validation.scenario_observation_count}; "
            f"remaining_promotion_gates={validation.remaining_promotion_gate_count}",
            file=stream,
        )
        print(
            "NEXT: obtain runtime promotion approval, replay/recovery witness, and terminal closure certificate",
            file=stream,
        )
        return
    print("STATUS: failed", file=stream)
    for error in validation.errors:
        print(f"ERROR: {error}", file=stream)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit validation as JSON.")
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT, help="Observation receipt to validate.")
    args = parser.parse_args(argv)
    validation, produced_receipt = validate_operator_shadow_pilot_observation_receipt(receipt_path=args.receipt)
    if args.json:
        payload = validation.as_dict()
        payload["produced_receipt"] = produced_receipt
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        _render_text(validation, sys.stdout)
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
