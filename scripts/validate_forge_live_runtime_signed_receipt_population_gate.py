#!/usr/bin/env python3
"""Validate the Forge live-runtime signed receipt population gate.

Purpose: prove signed live evidence receipt population remains blocked until
probe outputs are reconciled and signature evidence exists.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: gateway.forge_state_write_admission, signed receipt population
gate schema, signed receipt population fixture, and shared schema validation.
Invariants:
  - Signed receipt population is blocked in the Foundation fixture.
  - Signing key, trust epoch, signature, and receipt refs remain empty.
  - Runtime authority is not granted by receipt population planning.
  - Runtime, production, commit, external effect, and terminal closure
    authority remain false.
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
    FORGE_LIVE_RUNTIME_SIGNED_RECEIPT_POPULATION_GATE_ID,
    FORGE_LIVE_RUNTIME_SIGNED_RECEIPT_POPULATION_GATE_SCHEMA_REF,
    FORGE_WRITE_SPINE_BRIDGE_ID,
    LIVE_RUNTIME_EVIDENCE_COLLECTION_TARGETS,
    LIVE_RUNTIME_SIGNED_RECEIPT_POPULATION_CONTROLS,
    REQUIRED_LIVE_RUNTIME_EVIDENCE_IDS,
    build_foundation_forge_live_runtime_post_probe_reconciliation_packet,
    build_foundation_forge_live_runtime_signed_receipt_population_gate,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "forge_live_runtime_signed_receipt_population_gate.schema.json"
DEFAULT_GATE = REPO_ROOT / "examples" / "forge_live_runtime_signed_receipt_population_gate.foundation.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "forge_live_runtime_signed_receipt_population_gate_validation.json"


@dataclass(frozen=True, slots=True)
class ForgeLiveRuntimeSignedReceiptPopulationGateValidation:
    """Validation report for the Forge signed receipt population gate."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    gate_path: str
    gate_id: str
    population_status: str
    population_item_count: int
    blocked_reason_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_forge_live_runtime_signed_receipt_population_gate(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    gate_path: Path = DEFAULT_GATE,
) -> tuple[ForgeLiveRuntimeSignedReceiptPopulationGateValidation, dict[str, Any]]:
    """Validate signed receipt population gate schema, semantics, and fixture parity."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "Forge signed receipt population gate schema", errors)
    gate = _load_json_object(gate_path, "Forge signed receipt population gate", errors)
    produced_gate = build_foundation_forge_live_runtime_signed_receipt_population_gate()

    if schema and gate:
        errors.extend(f"{_path_label(gate_path)}: {error}" for error in _validate_schema_instance(schema, gate))
        _validate_gate_semantics(gate, errors, _path_label(gate_path))
    if schema and produced_gate:
        errors.extend(
            f"produced signed receipt population gate: {error}"
            for error in _validate_schema_instance(schema, produced_gate)
        )
        _validate_gate_semantics(produced_gate, errors, "produced signed receipt population gate")
    if gate and produced_gate and gate != produced_gate:
        errors.append("fixture does not match deterministic Forge live-runtime signed receipt population gate")

    observed_gate = produced_gate or gate
    population_items = observed_gate.get("population_items", ())
    blocked_reasons = observed_gate.get("blocked_reasons", ())
    validation = ForgeLiveRuntimeSignedReceiptPopulationGateValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        gate_path=_path_label(gate_path),
        gate_id=str(observed_gate.get("gate_id", "")),
        population_status=str(observed_gate.get("population_status", "")),
        population_item_count=len(population_items) if isinstance(population_items, list) else 0,
        blocked_reason_count=len(blocked_reasons) if isinstance(blocked_reasons, list) else 0,
    )
    return validation, produced_gate


def write_forge_live_runtime_signed_receipt_population_gate_validation(
    validation: ForgeLiveRuntimeSignedReceiptPopulationGateValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic signed receipt population gate validation report."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_gate_semantics(gate: Mapping[str, Any], errors: list[str], label: str) -> None:
    if gate.get("gate_id") != FORGE_LIVE_RUNTIME_SIGNED_RECEIPT_POPULATION_GATE_ID:
        errors.append(f"{label}: gate_id mismatch")
    if gate.get("schema_ref") != FORGE_LIVE_RUNTIME_SIGNED_RECEIPT_POPULATION_GATE_SCHEMA_REF:
        errors.append(f"{label}: schema_ref mismatch")
    if gate.get("bridge_ref") != FORGE_WRITE_SPINE_BRIDGE_ID:
        errors.append(f"{label}: bridge_ref mismatch")
    if gate.get("population_mode") != "signed_receipt_population_requires_reconciled_probe_outputs":
        errors.append(f"{label}: population_mode must remain signed_receipt_population_requires_reconciled_probe_outputs")
    if gate.get("population_status") != "blocked_awaiting_reconciled_probe_outputs":
        errors.append(f"{label}: population_status must remain blocked_awaiting_reconciled_probe_outputs")
    if gate.get("solver_outcome") != "AwaitingEvidence":
        errors.append(f"{label}: solver_outcome must remain AwaitingEvidence")
    if gate.get("receipt_population_allowed") is not False:
        errors.append(f"{label}: receipt_population_allowed must remain false")
    if gate.get("signed_receipt_refs_populated") is not False:
        errors.append(f"{label}: signed_receipt_refs_populated must remain false")
    if gate.get("runtime_authority_effect") is not False:
        errors.append(f"{label}: runtime_authority_effect must remain false")
    reconciliation_packet = build_foundation_forge_live_runtime_post_probe_reconciliation_packet()
    if gate.get("source_post_probe_reconciliation_packet_hash") != reconciliation_packet["packet_hash"]:
        errors.append(f"{label}: source_post_probe_reconciliation_packet_hash mismatch")
    _validate_population_items(gate, errors, label)
    _validate_authority(gate, errors, label)
    if tuple(gate.get("required_controls", ())) != LIVE_RUNTIME_SIGNED_RECEIPT_POPULATION_CONTROLS:
        errors.append(f"{label}: required_controls drift")
    if gate.get("next_allowed_action") != "populate_signed_receipts_after_reconciliation_and_signature_verification":
        errors.append(f"{label}: next_allowed_action drift")


def _validate_population_items(gate: Mapping[str, Any], errors: list[str], label: str) -> None:
    population_items = gate.get("population_items")
    blocked_reasons = gate.get("blocked_reasons")
    if not isinstance(population_items, list):
        errors.append(f"{label}: population_items must be a list")
        return
    evidence_ids = tuple(str(item.get("evidence_id", "")) for item in population_items if isinstance(item, Mapping))
    if evidence_ids != REQUIRED_LIVE_RUNTIME_EVIDENCE_IDS:
        errors.append(f"{label}: population_items order drift")
    expected_blockers = tuple(
        f"{evidence_id}_reconciled_probe_output_missing" for evidence_id in REQUIRED_LIVE_RUNTIME_EVIDENCE_IDS
    )
    if tuple(blocked_reasons or ()) != expected_blockers:
        errors.append(f"{label}: blocked_reasons drift")
    for item in population_items:
        population_item = _mapping(item)
        evidence_id = str(population_item.get("evidence_id", ""))
        expected_reconciliation_ref = f"reconciliation://forge/live-runtime/{evidence_id.replace('_', '-')}"
        if population_item.get("source_reconciliation_ref") != expected_reconciliation_ref:
            errors.append(f"{label}: {evidence_id}.source_reconciliation_ref mismatch")
        if population_item.get("target_signed_evidence_ref") != LIVE_RUNTIME_EVIDENCE_COLLECTION_TARGETS.get(
            evidence_id
        ):
            errors.append(f"{label}: {evidence_id}.target_signed_evidence_ref mismatch")
        for field_name in (
            "signed_receipt_update_ref",
            "signed_live_receipt_ref",
            "signing_key_id",
            "trust_epoch",
            "signature",
        ):
            if population_item.get(field_name) != "":
                errors.append(f"{label}: {evidence_id}.{field_name} must remain empty")
        if population_item.get("verification_status") != "not_verified":
            errors.append(f"{label}: {evidence_id}.verification_status must remain not_verified")
        if population_item.get("population_status") != "blocked":
            errors.append(f"{label}: {evidence_id}.population_status must remain blocked")
        if population_item.get("blocker_reason") != f"{evidence_id}_reconciled_probe_output_missing":
            errors.append(f"{label}: {evidence_id}.blocker_reason mismatch")
        if population_item.get("authority_effect") is not False:
            errors.append(f"{label}: {evidence_id}.authority_effect must remain false")
        if population_item.get("promotion_effect") is not False:
            errors.append(f"{label}: {evidence_id}.promotion_effect must remain false")


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
    """Parse Forge signed receipt population gate validation arguments."""

    parser = argparse.ArgumentParser(description="Validate Forge live-runtime signed receipt population gate.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--gate", default=str(DEFAULT_GATE))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for Forge signed receipt population gate validation."""

    args = parse_args(argv)
    validation, produced_gate = validate_forge_live_runtime_signed_receipt_population_gate(
        schema_path=Path(args.schema),
        gate_path=Path(args.gate),
    )
    write_forge_live_runtime_signed_receipt_population_gate_validation(validation, Path(args.output))
    if args.json:
        payload = validation.as_dict()
        payload["produced_gate"] = produced_gate
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif validation.ok:
        print("FORGE LIVE-RUNTIME SIGNED RECEIPT POPULATION GATE VALID")
    else:
        print(f"FORGE LIVE-RUNTIME SIGNED RECEIPT POPULATION GATE INVALID errors={list(validation.errors)}")
    return 0 if validation.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
