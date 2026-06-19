#!/usr/bin/env python3
"""Validate GovernedPlanningProfile terminal closure certificate.

Purpose: emit and validate a local-only terminal closure certificate for the
GovernedPlanningProfile runtime-promotion evidence ladder.
Governance scope: OCE terminal control completeness, RAG replay/recovery
witness binding, CDCV hash traceability, CQTE no-authority constraints, UWMA
certificate anchoring, SRCA bounded scenario enumeration, and PRS validation.
Dependencies: replay/recovery witness validator, schema validator, and
canonical hashing.
Invariants:
  - The certificate closes the local evidence ladder only; it does not activate
    runtime promotion.
  - The certificate never grants execution, dispatch, replanning, success, or
    terminal closure authority.
  - Runtime promotion still requires a separate authority-changing action.
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
)
from scripts.validate_governed_planning_profile_replay_recovery_witness import (  # noqa: E402
    build_replay_recovery_witness,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


SCHEMA_VERSION = "governed_planning_profile_terminal_closure_certificate.v1"
CERTIFICATE_ID_PREFIX = "governed-planning-profile-terminal-closure-certificate"
DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "governed_planning_profile_terminal_closure_certificate.schema.json"
DEFAULT_CERTIFICATE = REPO_ROOT / "examples" / "governed_planning_profile_terminal_closure_certificate.local.json"
SATISFIED_PROMOTION_GATE_IDS = (
    "operator_shadow_pilot_observation",
    "runtime_promotion_approval",
    "replay_recovery_witness",
    "terminal_closure_certificate",
)
TERMINAL_CLOSURE_CONTROL_IDS = (
    "source_replay_recovery_witness_valid",
    "all_promotion_gates_satisfied",
    "zero_shadow_mismatches_preserved",
    "zero_replay_mismatches_preserved",
    "rollback_and_recovery_handoff_bound",
    "authority_denials_preserved",
    "foundation_no_effect_boundary_preserved",
    "terminal_certificate_hash_bound",
)


@dataclass(frozen=True, slots=True)
class TerminalClosureCertificateValidation:
    """Validation result for the planning-profile terminal closure certificate."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    certificate_path: str
    certificate_id: str
    source_replay_recovery_witness_id: str
    terminal_closure_control_count: int
    scenario_closure_count: int
    remaining_promotion_gate_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def build_terminal_closure_certificate(
    replay_recovery_witness: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the deterministic local terminal closure certificate."""

    current_witness = dict(replay_recovery_witness or build_replay_recovery_witness())
    scenario_closures = tuple(_scenario_terminal_closures(current_witness))
    controls = tuple(_terminal_closure_controls(current_witness))
    payload: dict[str, Any] = {
        "certificate_id": "pending",
        "schema_version": SCHEMA_VERSION,
        "profile_id": str(current_witness.get("profile_id", "")),
        "certified_at": GENERATED_AT,
        "solver_outcome": "SolvedVerified",
        "terminal_closure_certificate_status": "CollectedNoEffect",
        "terminal_closure_gate_satisfied": True,
        "all_promotion_evidence_satisfied": True,
        "local_certificate_only": True,
        "read_only": True,
        "mutation_route": False,
        "runtime_behavior_change": False,
        "runtime_promotion_authorized": False,
        "execution_allowed": False,
        "dispatch_allowed": False,
        "runtime_replanning_enabled": False,
        "success_claim_allowed": False,
        "terminal_closure": False,
        "source_replay_recovery_witness": {
            "witness_id": str(current_witness.get("witness_id", "")),
            "witness_hash": str(current_witness.get("witness_hash", "")),
            "replay_recovery_witness_status": str(
                current_witness.get("replay_recovery_witness_status", "")
            ),
            "replay_recovery_gate_satisfied": bool(
                current_witness.get("replay_recovery_gate_satisfied")
            ),
            "scenario_witness_count": int(
                _mapping(current_witness.get("promotion_gate_summary")).get(
                    "scenario_witness_count",
                    0,
                )
            ),
            "remaining_promotion_gate_count": int(
                len(_sequence(current_witness.get("remaining_promotion_gates")))
            ),
        },
        "expected_plan_classes": list(EXPECTED_PLAN_CLASSES),
        "terminal_closure_controls": list(controls),
        "scenario_terminal_closures": list(scenario_closures),
        "certificate_boundary": {
            "source_replay_recovery_witness_bound": True,
            "all_prior_gates_satisfied": True,
            "terminal_certificate_collected": True,
            "runtime_promotion_authorization_required": True,
            "runtime_promotion_authorization_performed": False,
            "runtime_execution_performed": False,
            "terminal_closure_authority_granted": False,
        },
        "promotion_gate_summary": {
            "satisfied_promotion_gate_ids": list(SATISFIED_PROMOTION_GATE_IDS),
            "remaining_promotion_gate_ids": [],
            "terminal_closure_control_count": len(controls),
            "scenario_closure_count": len(scenario_closures),
            "all_promotion_evidence_satisfied": True,
            "runtime_promotion_authorized": False,
        },
        "remaining_promotion_gates": [],
        "authority_denials": {
            "runtime_promotion_authorized": False,
            "execution_allowed": False,
            "dispatch_allowed": False,
            "runtime_replanning_enabled": False,
            "success_claim_allowed": False,
            "terminal_closure": False,
        },
        "evidence_refs": [
            "scripts/validate_governed_planning_profile_replay_recovery_witness.py",
            "scripts/validate_governed_planning_profile_terminal_closure_certificate.py",
            "schemas/governed_planning_profile_terminal_closure_certificate.schema.json",
            "examples/governed_planning_profile_terminal_closure_certificate.local.json",
            "tests/test_validate_governed_planning_profile_terminal_closure_certificate.py",
        ],
        "validators": [
            {
                "validator_id": "governed-planning-profile-terminal-closure-certificate",
                "command": (
                    "python scripts/"
                    "validate_governed_planning_profile_terminal_closure_certificate.py"
                ),
            }
        ],
        "next_action": "submit separate runtime promotion authorization request before activation",
        "certificate_hash": "",
    }
    certificate_hash = canonical_hash(payload)
    payload["certificate_id"] = f"{CERTIFICATE_ID_PREFIX}-{certificate_hash[:16]}"
    payload["certificate_hash"] = certificate_hash
    return payload


def validate_terminal_closure_certificate(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    certificate_path: Path = DEFAULT_CERTIFICATE,
) -> tuple[TerminalClosureCertificateValidation, dict[str, Any]]:
    """Validate the checked-in terminal certificate and produced certificate."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "terminal closure certificate schema", errors)
    certificate = _load_json_object(certificate_path, "terminal closure certificate", errors)
    produced_certificate = build_terminal_closure_certificate()
    if schema and certificate:
        errors.extend(
            f"{_path_label(certificate_path)}: {error}"
            for error in _validate_schema_instance(schema, certificate)
        )
        _validate_certificate_semantics(certificate, errors, _path_label(certificate_path))
    if schema:
        errors.extend(
            f"produced terminal closure certificate: {error}"
            for error in _validate_schema_instance(schema, produced_certificate)
        )
        _validate_certificate_semantics(
            produced_certificate,
            errors,
            "produced terminal closure certificate",
        )
    if certificate and certificate != produced_certificate:
        errors.append("terminal closure certificate fixture does not match deterministic produced certificate")

    observed = certificate or produced_certificate
    validation = TerminalClosureCertificateValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        certificate_path=_path_label(certificate_path),
        certificate_id=str(observed.get("certificate_id", "")),
        source_replay_recovery_witness_id=str(
            _mapping(observed.get("source_replay_recovery_witness")).get("witness_id", "")
        ),
        terminal_closure_control_count=len(_sequence(observed.get("terminal_closure_controls"))),
        scenario_closure_count=len(_sequence(observed.get("scenario_terminal_closures"))),
        remaining_promotion_gate_count=len(_sequence(observed.get("remaining_promotion_gates"))),
    )
    return validation, produced_certificate


def _terminal_closure_controls(replay_recovery_witness: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "control_id": "source_replay_recovery_witness_valid",
            "status": "Pass",
            "evidence_ref": str(replay_recovery_witness.get("witness_id", "")),
            "blocks_runtime_promotion_evidence": False,
        },
        {
            "control_id": "all_promotion_gates_satisfied",
            "status": "Pass",
            "evidence_ref": "promotion_gate_summary.satisfied_promotion_gate_ids",
            "blocks_runtime_promotion_evidence": False,
        },
        {
            "control_id": "zero_shadow_mismatches_preserved",
            "status": "Pass",
            "evidence_ref": "source_runtime_promotion_approval_packet",
            "blocks_runtime_promotion_evidence": False,
        },
        {
            "control_id": "zero_replay_mismatches_preserved",
            "status": "Pass",
            "evidence_ref": "scenario_terminal_closures.replay_mismatch_count",
            "blocks_runtime_promotion_evidence": False,
        },
        {
            "control_id": "rollback_and_recovery_handoff_bound",
            "status": "Pass",
            "evidence_ref": "source_replay_recovery_witness.recovery_boundary",
            "blocks_runtime_promotion_evidence": False,
        },
        {
            "control_id": "authority_denials_preserved",
            "status": "Pass",
            "evidence_ref": "authority_denials",
            "blocks_runtime_promotion_evidence": False,
        },
        {
            "control_id": "foundation_no_effect_boundary_preserved",
            "status": "Pass",
            "evidence_ref": "local_certificate_only",
            "blocks_runtime_promotion_evidence": False,
        },
        {
            "control_id": "terminal_certificate_hash_bound",
            "status": "Pass",
            "evidence_ref": "certificate_hash",
            "blocks_runtime_promotion_evidence": False,
        },
    ]


def _scenario_terminal_closures(replay_recovery_witness: Mapping[str, Any]) -> list[dict[str, Any]]:
    closures: list[dict[str, Any]] = []
    for scenario_witness in _sequence(replay_recovery_witness.get("scenario_replay_witnesses")):
        if not isinstance(scenario_witness, Mapping):
            continue
        plan_class = str(scenario_witness.get("plan_class", ""))
        closures.append({
            "scenario_id": str(scenario_witness.get("scenario_id", "")),
            "plan_class": plan_class,
            "source_replay_probe_ref": str(scenario_witness.get("replay_probe_ref", "")),
            "source_recovery_path_ref": str(scenario_witness.get("recovery_path_ref", "")),
            "terminal_closure_status": "ClosedNoEffect",
            "replay_mismatch_count": int(scenario_witness.get("replay_mismatch_count", -1)),
            "rollback_path_documented": bool(scenario_witness.get("rollback_path_documented")),
            "incident_handoff_documented": bool(scenario_witness.get("incident_handoff_documented")),
            "runtime_promotion_authorization_required": True,
            "runtime_promotion_authorized": False,
            "runtime_execution_performed": False,
        })
    return closures


def _validate_certificate_semantics(certificate: Mapping[str, Any], errors: list[str], label: str) -> None:
    if certificate.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"{label}: schema_version mismatch")
    if certificate.get("solver_outcome") != "SolvedVerified":
        errors.append(f"{label}: solver_outcome must be SolvedVerified")
    for field_name, expected in (
        ("terminal_closure_certificate_status", "CollectedNoEffect"),
        ("terminal_closure_gate_satisfied", True),
        ("all_promotion_evidence_satisfied", True),
        ("local_certificate_only", True),
        ("read_only", True),
        ("mutation_route", False),
        ("runtime_behavior_change", False),
        *tuple((field_name, False) for field_name in AUTHORITY_FALSE_FIELDS),
    ):
        observed = certificate.get(field_name)
        if isinstance(expected, bool):
            drifted = observed is not expected
        else:
            drifted = observed != expected
        if drifted:
            errors.append(f"{label}: {field_name} must be {expected!r}")
    source_witness = _mapping(certificate.get("source_replay_recovery_witness"))
    if source_witness.get("replay_recovery_witness_status") != "CollectedNoEffect":
        errors.append(f"{label}: source replay/recovery witness status must be CollectedNoEffect")
    if source_witness.get("replay_recovery_gate_satisfied") is not True:
        errors.append(f"{label}: source replay/recovery gate must be satisfied")
    if source_witness.get("scenario_witness_count") != len(EXPECTED_PLAN_CLASSES):
        errors.append(f"{label}: source scenario witness count mismatch")
    if source_witness.get("remaining_promotion_gate_count") != 1:
        errors.append(f"{label}: source remaining promotion gate count must be 1")
    observed_classes = tuple(certificate.get("expected_plan_classes", ()))
    if observed_classes != EXPECTED_PLAN_CLASSES:
        errors.append(f"{label}: expected_plan_classes mismatch")
    _validate_terminal_closure_controls(certificate, errors, label)
    _validate_scenario_terminal_closures(certificate, errors, label)
    _validate_certificate_boundary(certificate, errors, label)
    _validate_promotion_gate_summary(certificate, errors, label)
    _validate_authority_denials(certificate, errors, label)


def _validate_terminal_closure_controls(certificate: Mapping[str, Any], errors: list[str], label: str) -> None:
    controls = _sequence(certificate.get("terminal_closure_controls"))
    control_ids = tuple(str(control.get("control_id", "")) for control in controls if isinstance(control, Mapping))
    if control_ids != TERMINAL_CLOSURE_CONTROL_IDS:
        errors.append(f"{label}: terminal closure control ids mismatch")
    for control in controls:
        if not isinstance(control, Mapping):
            errors.append(f"{label}: terminal closure control must be an object")
            continue
        if control.get("status") != "Pass":
            errors.append(f"{label}: terminal closure control status must be Pass")
        if control.get("blocks_runtime_promotion_evidence") is not False:
            errors.append(f"{label}: satisfied terminal closure control must not block promotion evidence")


def _validate_scenario_terminal_closures(certificate: Mapping[str, Any], errors: list[str], label: str) -> None:
    scenario_closures = _sequence(certificate.get("scenario_terminal_closures"))
    if len(scenario_closures) != len(EXPECTED_PLAN_CLASSES):
        errors.append(f"{label}: scenario_terminal_closures must cover all expected plan classes")
        return
    observed_classes = []
    for scenario_closure in scenario_closures:
        if not isinstance(scenario_closure, Mapping):
            errors.append(f"{label}: scenario terminal closure must be an object")
            continue
        observed_classes.append(str(scenario_closure.get("plan_class", "")))
        for field_name, expected in (
            ("terminal_closure_status", "ClosedNoEffect"),
            ("replay_mismatch_count", 0),
            ("rollback_path_documented", True),
            ("incident_handoff_documented", True),
            ("runtime_promotion_authorization_required", True),
            ("runtime_promotion_authorized", False),
            ("runtime_execution_performed", False),
        ):
            if scenario_closure.get(field_name) != expected:
                errors.append(f"{label}: scenario {field_name} must be {expected!r}")
        if not str(scenario_closure.get("source_replay_probe_ref", "")).startswith("hash://sha256/"):
            errors.append(f"{label}: scenario source_replay_probe_ref must be digest-bound")
        if not str(scenario_closure.get("source_recovery_path_ref", "")).startswith(
            "recovery://governed-planning-profile/"
        ):
            errors.append(f"{label}: scenario source_recovery_path_ref must be recovery-bound")
    if tuple(observed_classes) != EXPECTED_PLAN_CLASSES:
        errors.append(f"{label}: scenario terminal closure classes must match required order")


def _validate_certificate_boundary(certificate: Mapping[str, Any], errors: list[str], label: str) -> None:
    boundary = _mapping(certificate.get("certificate_boundary"))
    for field_name in (
        "source_replay_recovery_witness_bound",
        "all_prior_gates_satisfied",
        "terminal_certificate_collected",
        "runtime_promotion_authorization_required",
    ):
        if boundary.get(field_name) is not True:
            errors.append(f"{label}: certificate_boundary.{field_name} must be true")
    for field_name in (
        "runtime_promotion_authorization_performed",
        "runtime_execution_performed",
        "terminal_closure_authority_granted",
    ):
        if boundary.get(field_name) is not False:
            errors.append(f"{label}: certificate_boundary.{field_name} must be false")


def _validate_promotion_gate_summary(certificate: Mapping[str, Any], errors: list[str], label: str) -> None:
    summary = _mapping(certificate.get("promotion_gate_summary"))
    if tuple(summary.get("satisfied_promotion_gate_ids", ())) != SATISFIED_PROMOTION_GATE_IDS:
        errors.append(f"{label}: satisfied promotion gate ids mismatch")
    if tuple(summary.get("remaining_promotion_gate_ids", ())) != ():
        errors.append(f"{label}: remaining promotion gate ids must be empty")
    if summary.get("terminal_closure_control_count") != len(TERMINAL_CLOSURE_CONTROL_IDS):
        errors.append(f"{label}: promotion_gate_summary.terminal_closure_control_count mismatch")
    if summary.get("scenario_closure_count") != len(EXPECTED_PLAN_CLASSES):
        errors.append(f"{label}: promotion_gate_summary.scenario_closure_count mismatch")
    if summary.get("all_promotion_evidence_satisfied") is not True:
        errors.append(f"{label}: promotion_gate_summary.all_promotion_evidence_satisfied must be true")
    if summary.get("runtime_promotion_authorized") is not False:
        errors.append(f"{label}: promotion_gate_summary.runtime_promotion_authorized must be false")
    if _sequence(certificate.get("remaining_promotion_gates")):
        errors.append(f"{label}: remaining_promotion_gates must be empty")


def _validate_authority_denials(certificate: Mapping[str, Any], errors: list[str], label: str) -> None:
    denials = _mapping(certificate.get("authority_denials"))
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


def _render_text(validation: TerminalClosureCertificateValidation, stream: TextIO) -> None:
    if validation.ok:
        print(
            "STATUS: passed; "
            f"controls={validation.terminal_closure_control_count}; "
            f"scenarios={validation.scenario_closure_count}; "
            f"remaining_promotion_gates={validation.remaining_promotion_gate_count}",
            file=stream,
        )
        print("NEXT: submit separate runtime promotion authorization request", file=stream)
        return
    print("STATUS: failed", file=stream)
    for error in validation.errors:
        print(f"ERROR: {error}", file=stream)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit validation as JSON.")
    parser.add_argument(
        "--certificate",
        type=Path,
        default=DEFAULT_CERTIFICATE,
        help="Terminal closure certificate to validate.",
    )
    args = parser.parse_args(argv)
    validation, produced_certificate = validate_terminal_closure_certificate(certificate_path=args.certificate)
    if args.json:
        payload = validation.as_dict()
        payload["produced_certificate"] = produced_certificate
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        _render_text(validation, sys.stdout)
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
