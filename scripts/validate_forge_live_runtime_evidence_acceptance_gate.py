#!/usr/bin/env python3
"""Validate the Forge live-runtime evidence acceptance gate.

Purpose: prove Forge live-runtime promotion remains blocked until signed live
evidence is present for every readiness blocker.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: gateway.forge_state_write_admission, evidence acceptance schema,
evidence acceptance fixture, and shared schema validation.
Invariants:
  - Local design artifacts are not sufficient for live runtime promotion.
  - Signed live evidence is missing in Foundation Mode.
  - Runtime, production, commit, external effect, and terminal closure
    authority remain false.
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
    FORGE_LIVE_RUNTIME_EVIDENCE_ACCEPTANCE_GATE_ID,
    FORGE_LIVE_RUNTIME_EVIDENCE_ACCEPTANCE_GATE_SCHEMA_REF,
    FORGE_WRITE_SPINE_BRIDGE_ID,
    LIVE_RUNTIME_EVIDENCE_ACCEPTANCE_CONTROLS,
    LIVE_RUNTIME_EVIDENCE_COLLECTION_TARGETS,
    LIVE_RUNTIME_LOCAL_EVIDENCE_ARTIFACT_REFS,
    REQUIRED_LIVE_RUNTIME_EVIDENCE_IDS,
    build_foundation_forge_live_runtime_evidence_acceptance_gate,
    build_foundation_forge_live_runtime_local_evidence_bundle,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "forge_live_runtime_evidence_acceptance_gate.schema.json"
DEFAULT_GATE = REPO_ROOT / "examples" / "forge_live_runtime_evidence_acceptance_gate.foundation.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "forge_live_runtime_evidence_acceptance_gate_validation.json"
REQUIRED_WITNESSES = (
    "signed_live_receipt",
    "dependency_or_credential_probe",
    "recovery_or_revocation_path",
)


@dataclass(frozen=True, slots=True)
class ForgeLiveRuntimeEvidenceAcceptanceGateValidation:
    """Validation report for the Forge live-runtime evidence acceptance gate."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    gate_path: str
    gate_id: str
    acceptance_status: str
    acceptance_item_count: int
    blocked_reason_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_forge_live_runtime_evidence_acceptance_gate(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    gate_path: Path = DEFAULT_GATE,
) -> tuple[ForgeLiveRuntimeEvidenceAcceptanceGateValidation, dict[str, Any]]:
    """Validate acceptance gate schema, semantics, and deterministic fixture."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "Forge live-runtime evidence acceptance schema", errors)
    gate = _load_json_object(gate_path, "Forge live-runtime evidence acceptance gate", errors)
    produced_gate = build_foundation_forge_live_runtime_evidence_acceptance_gate()

    if schema and gate:
        errors.extend(f"{_path_label(gate_path)}: {error}" for error in _validate_schema_instance(schema, gate))
        _validate_gate_semantics(gate, errors, _path_label(gate_path))
    if schema and produced_gate:
        errors.extend(
            f"produced evidence acceptance gate: {error}"
            for error in _validate_schema_instance(schema, produced_gate)
        )
        _validate_gate_semantics(produced_gate, errors, "produced evidence acceptance gate")
    if gate and produced_gate and gate != produced_gate:
        errors.append("fixture does not match deterministic Forge live-runtime evidence acceptance gate")

    observed_gate = produced_gate or gate
    acceptance_items = observed_gate.get("acceptance_items", ())
    blocked_reasons = observed_gate.get("blocked_reasons", ())
    validation = ForgeLiveRuntimeEvidenceAcceptanceGateValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        gate_path=_path_label(gate_path),
        gate_id=str(observed_gate.get("gate_id", "")),
        acceptance_status=str(observed_gate.get("acceptance_status", "")),
        acceptance_item_count=len(acceptance_items) if isinstance(acceptance_items, list) else 0,
        blocked_reason_count=len(blocked_reasons) if isinstance(blocked_reasons, list) else 0,
    )
    return validation, produced_gate


def write_forge_live_runtime_evidence_acceptance_gate_validation(
    validation: ForgeLiveRuntimeEvidenceAcceptanceGateValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic evidence acceptance validation report."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_gate_semantics(gate: Mapping[str, Any], errors: list[str], label: str) -> None:
    if gate.get("gate_id") != FORGE_LIVE_RUNTIME_EVIDENCE_ACCEPTANCE_GATE_ID:
        errors.append(f"{label}: gate_id mismatch")
    if gate.get("schema_ref") != FORGE_LIVE_RUNTIME_EVIDENCE_ACCEPTANCE_GATE_SCHEMA_REF:
        errors.append(f"{label}: schema_ref mismatch")
    if gate.get("bridge_ref") != FORGE_WRITE_SPINE_BRIDGE_ID:
        errors.append(f"{label}: bridge_ref mismatch")
    if gate.get("acceptance_mode") != "signed_live_evidence_required":
        errors.append(f"{label}: acceptance_mode must remain signed_live_evidence_required")
    if gate.get("acceptance_status") != "blocked_awaiting_signed_live_evidence":
        errors.append(f"{label}: acceptance_status must remain blocked_awaiting_signed_live_evidence")
    if gate.get("solver_outcome") != "AwaitingEvidence":
        errors.append(f"{label}: solver_outcome must remain AwaitingEvidence")
    if gate.get("admission_decision") != "block_live_runtime_promotion":
        errors.append(f"{label}: admission_decision must remain block_live_runtime_promotion")
    local_bundle = build_foundation_forge_live_runtime_local_evidence_bundle()
    if gate.get("source_local_evidence_bundle_hash") != local_bundle["bundle_hash"]:
        errors.append(f"{label}: source_local_evidence_bundle_hash mismatch")
    _validate_acceptance_items(gate, errors, label)
    _validate_authority(gate, errors, label)
    if tuple(gate.get("required_controls", ())) != LIVE_RUNTIME_EVIDENCE_ACCEPTANCE_CONTROLS:
        errors.append(f"{label}: required_controls drift")
    if gate.get("next_allowed_action") != "collect_signed_live_evidence_under_operator_approval":
        errors.append(f"{label}: next_allowed_action drift")


def _validate_acceptance_items(gate: Mapping[str, Any], errors: list[str], label: str) -> None:
    acceptance_items = gate.get("acceptance_items")
    blocked_reasons = gate.get("blocked_reasons")
    if not isinstance(acceptance_items, list):
        errors.append(f"{label}: acceptance_items must be a list")
        return
    evidence_ids = tuple(str(item.get("evidence_id", "")) for item in acceptance_items if isinstance(item, Mapping))
    if evidence_ids != REQUIRED_LIVE_RUNTIME_EVIDENCE_IDS:
        errors.append(f"{label}: acceptance_items order drift")
    expected_blockers = tuple(
        f"{evidence_id}_signed_live_evidence_missing" for evidence_id in REQUIRED_LIVE_RUNTIME_EVIDENCE_IDS
    )
    if tuple(blocked_reasons or ()) != expected_blockers:
        errors.append(f"{label}: blocked_reasons drift")
    for item in acceptance_items:
        evidence = _mapping(item)
        evidence_id = str(evidence.get("evidence_id", ""))
        if evidence.get("source_local_artifact_ref") != LIVE_RUNTIME_LOCAL_EVIDENCE_ARTIFACT_REFS.get(evidence_id):
            errors.append(f"{label}: {evidence_id}.source_local_artifact_ref mismatch")
        if evidence.get("required_live_evidence_ref") != LIVE_RUNTIME_EVIDENCE_COLLECTION_TARGETS.get(evidence_id):
            errors.append(f"{label}: {evidence_id}.required_live_evidence_ref mismatch")
        if tuple(evidence.get("required_witnesses", ())) != REQUIRED_WITNESSES:
            errors.append(f"{label}: {evidence_id}.required_witnesses mismatch")
        if evidence.get("live_evidence_status") != "missing":
            errors.append(f"{label}: {evidence_id}.live_evidence_status must remain missing")
        if evidence.get("acceptance_status") != "blocked":
            errors.append(f"{label}: {evidence_id}.acceptance_status must remain blocked")
        if evidence.get("blocker_reason") != f"{evidence_id}_signed_live_evidence_missing":
            errors.append(f"{label}: {evidence_id}.blocker_reason mismatch")
        if evidence.get("local_artifact_sufficient") is not False:
            errors.append(f"{label}: {evidence_id}.local_artifact_sufficient must remain false")
        if evidence.get("authority_effect") is not False:
            errors.append(f"{label}: {evidence_id}.authority_effect must remain false")


def _validate_authority(gate: Mapping[str, Any], errors: list[str], label: str) -> None:
    disallowed_authority = _mapping(gate.get("disallowed_authority"))
    for field_name in (
        "live_runtime_authorized",
        "state_write_runtime_registered",
        "production_authorized",
        "external_effects_allowed",
        "commit_allowed",
        "terminal_closure",
    ):
        if disallowed_authority.get(field_name) is not False:
            errors.append(f"{label}: disallowed_authority.{field_name} must remain false")


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
    """Parse Forge live-runtime evidence acceptance validation arguments."""

    parser = argparse.ArgumentParser(description="Validate Forge live-runtime evidence acceptance gate.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--gate", default=str(DEFAULT_GATE))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for Forge live-runtime evidence acceptance validation."""

    args = parse_args(argv)
    validation, produced_gate = validate_forge_live_runtime_evidence_acceptance_gate(
        schema_path=Path(args.schema),
        gate_path=Path(args.gate),
    )
    write_forge_live_runtime_evidence_acceptance_gate_validation(validation, Path(args.output))
    if args.json:
        payload = validation.as_dict()
        payload["produced_gate"] = produced_gate
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif validation.ok:
        print("FORGE LIVE-RUNTIME EVIDENCE ACCEPTANCE GATE VALID")
    else:
        print(f"FORGE LIVE-RUNTIME EVIDENCE ACCEPTANCE GATE INVALID errors={list(validation.errors)}")
    return 0 if validation.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
