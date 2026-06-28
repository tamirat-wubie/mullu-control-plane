#!/usr/bin/env python3
"""Validate the Forge live-runtime readiness gate.

Purpose: prove live Forge state-write runtime registration remains blocked
until the explicit production and operational evidence set exists.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: gateway.forge_state_write_admission, readiness gate schema,
readiness gate fixture, and shared schema validation.
Invariants:
  - Live runtime authority is blocked in Foundation Mode.
  - Commit, production, and external-effect authority remain false.
  - Required evidence remains explicit and absent in the Foundation fixture.
  - The checked-in gate matches the deterministic builder output.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateway.forge_state_write_admission import (  # noqa: E402
    FORGE_LIVE_RUNTIME_READINESS_GATE_ID,
    FORGE_LIVE_RUNTIME_READINESS_GATE_SCHEMA_REF,
    FORGE_WRITE_SPINE_BRIDGE_ID,
    LIVE_RUNTIME_REQUIRED_CONTROLS,
    REQUIRED_LIVE_RUNTIME_EVIDENCE_IDS,
    build_foundation_forge_live_runtime_readiness_gate,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "forge_live_runtime_readiness_gate.schema.json"
DEFAULT_GATE = REPO_ROOT / "examples" / "forge_live_runtime_readiness_gate.foundation.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "forge_live_runtime_readiness_gate_validation.json"


@dataclass(frozen=True, slots=True)
class ForgeLiveRuntimeReadinessGateValidation:
    """Validation report for the Forge live-runtime readiness gate."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    gate_path: str
    gate_id: str
    readiness_status: str
    blocked_reason_count: int
    evidence_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_forge_live_runtime_readiness_gate(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    gate_path: Path = DEFAULT_GATE,
) -> tuple[ForgeLiveRuntimeReadinessGateValidation, dict[str, Any]]:
    """Validate the readiness gate schema, semantics, and deterministic fixture."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "Forge live-runtime readiness gate schema", errors)
    gate = _load_json_object(gate_path, "Forge live-runtime readiness gate", errors)
    produced_gate = build_foundation_forge_live_runtime_readiness_gate()

    if schema and gate:
        errors.extend(f"{_path_label(gate_path)}: {error}" for error in _validate_schema_instance(schema, gate))
        _validate_gate_semantics(gate, errors, _path_label(gate_path))
    if schema and produced_gate:
        errors.extend(
            f"produced readiness gate: {error}" for error in _validate_schema_instance(schema, produced_gate)
        )
        _validate_gate_semantics(produced_gate, errors, "produced readiness gate")
    if gate and produced_gate and gate != produced_gate:
        errors.append("fixture does not match deterministic Forge live-runtime readiness gate")

    observed_gate = produced_gate or gate
    evidence = observed_gate.get("required_evidence", ())
    blocked_reasons = observed_gate.get("blocked_reasons", ())
    validation = ForgeLiveRuntimeReadinessGateValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        gate_path=_path_label(gate_path),
        gate_id=str(observed_gate.get("gate_id", "")),
        readiness_status=str(observed_gate.get("readiness_status", "")),
        blocked_reason_count=len(blocked_reasons) if isinstance(blocked_reasons, list) else 0,
        evidence_count=len(evidence) if isinstance(evidence, list) else 0,
    )
    return validation, produced_gate


def write_forge_live_runtime_readiness_gate_validation(
    validation: ForgeLiveRuntimeReadinessGateValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic readiness-gate validation report."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_gate_semantics(gate: Mapping[str, Any], errors: list[str], label: str) -> None:
    if gate.get("gate_id") != FORGE_LIVE_RUNTIME_READINESS_GATE_ID:
        errors.append(f"{label}: gate_id mismatch")
    if gate.get("schema_ref") != FORGE_LIVE_RUNTIME_READINESS_GATE_SCHEMA_REF:
        errors.append(f"{label}: schema_ref mismatch")
    if gate.get("bridge_ref") != FORGE_WRITE_SPINE_BRIDGE_ID:
        errors.append(f"{label}: bridge_ref mismatch")
    if gate.get("readiness_status") != "blocked_awaiting_evidence":
        errors.append(f"{label}: readiness_status must remain blocked_awaiting_evidence")
    if gate.get("solver_outcome") != "AwaitingEvidence":
        errors.append(f"{label}: solver_outcome must remain AwaitingEvidence")
    if gate.get("admission_decision") != "block_live_runtime":
        errors.append(f"{label}: admission_decision must block live runtime")
    for field_name in (
        "live_runtime_authorized",
        "state_write_runtime_registered",
        "production_authorized",
        "external_effects_allowed",
        "commit_allowed",
    ):
        if gate.get(field_name) is not False:
            errors.append(f"{label}: {field_name} must remain false")
    if gate.get("foundation_mode") is not True:
        errors.append(f"{label}: foundation_mode must remain true")
    _validate_required_evidence(gate, errors, label)
    _validate_required_controls(gate, errors, label)
    if gate.get("next_allowed_action") != "collect_local_evidence_without_registering_runtime_authority":
        errors.append(f"{label}: next_allowed_action drift")


def _validate_required_evidence(gate: Mapping[str, Any], errors: list[str], label: str) -> None:
    required_evidence = gate.get("required_evidence")
    blocked_reasons = gate.get("blocked_reasons")
    if not isinstance(required_evidence, list):
        errors.append(f"{label}: required_evidence must be a list")
        return
    evidence_ids = tuple(str(item.get("evidence_id", "")) for item in required_evidence if isinstance(item, Mapping))
    if evidence_ids != REQUIRED_LIVE_RUNTIME_EVIDENCE_IDS:
        errors.append(f"{label}: required_evidence order drift")
    expected_blockers = tuple(f"{evidence_id}_missing" for evidence_id in REQUIRED_LIVE_RUNTIME_EVIDENCE_IDS)
    if tuple(blocked_reasons or ()) != expected_blockers:
        errors.append(f"{label}: blocked_reasons drift")
    for item in required_evidence:
        evidence = _mapping(item)
        evidence_id = str(evidence.get("evidence_id", ""))
        if evidence.get("required") is not True:
            errors.append(f"{label}: {evidence_id}.required must be true")
        if evidence.get("present") is not False:
            errors.append(f"{label}: {evidence_id}.present must remain false")
        if evidence.get("evidence_ref") != "":
            errors.append(f"{label}: {evidence_id}.evidence_ref must remain empty in Foundation fixture")
        if evidence.get("blocker_reason") != f"{evidence_id}_missing":
            errors.append(f"{label}: {evidence_id}.blocker_reason mismatch")


def _validate_required_controls(gate: Mapping[str, Any], errors: list[str], label: str) -> None:
    required_controls = gate.get("required_controls")
    if not isinstance(required_controls, list) or tuple(required_controls) != LIVE_RUNTIME_REQUIRED_CONTROLS:
        errors.append(f"{label}: required_controls drift")


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    if not path.exists():
        errors.append(f"{label} file missing: {_path_label(path)}")
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except (OSError, json.JSONDecodeError, ValueError):
        errors.append(f"{label} JSON load failed: {_path_label(path)}")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{label} JSON root must be an object: {_path_label(path)}")
        return {}
    return payload


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError(f"non-finite JSON constants are not permitted: {raw_constant}")


def _mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse Forge live-runtime readiness gate validation arguments."""

    parser = argparse.ArgumentParser(description="Validate Forge live-runtime readiness gate.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--gate", default=str(DEFAULT_GATE))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for Forge live-runtime readiness gate validation."""

    args = parse_args(argv)
    validation, produced_gate = validate_forge_live_runtime_readiness_gate(
        schema_path=Path(args.schema),
        gate_path=Path(args.gate),
    )
    write_forge_live_runtime_readiness_gate_validation(validation, Path(args.output))
    if args.json:
        payload = validation.as_dict()
        payload["produced_gate"] = produced_gate
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif validation.ok:
        print("FORGE LIVE-RUNTIME READINESS GATE VALID")
    else:
        print(f"FORGE LIVE-RUNTIME READINESS GATE INVALID errors={list(validation.errors)}")
    return 0 if validation.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
