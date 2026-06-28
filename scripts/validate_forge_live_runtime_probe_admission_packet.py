#!/usr/bin/env python3
"""Validate the Forge live-runtime probe admission packet.

Purpose: prove future Forge live-runtime probes require explicit operator
approval and complete bounded inputs before any signed evidence refs can be
populated.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: gateway.forge_state_write_admission, probe admission schema,
probe admission fixture, and shared schema validation.
Invariants:
  - Probe execution is blocked in the Foundation fixture.
  - External effects are not requested.
  - Signed receipt population is not allowed.
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
    FORGE_LIVE_RUNTIME_PROBE_ADMISSION_PACKET_ID,
    FORGE_LIVE_RUNTIME_PROBE_ADMISSION_PACKET_SCHEMA_REF,
    FORGE_WRITE_SPINE_BRIDGE_ID,
    LIVE_RUNTIME_EVIDENCE_COLLECTION_TARGETS,
    LIVE_RUNTIME_PROBE_ADMISSION_CONTROLS,
    LIVE_RUNTIME_PROBE_REQUIRED_INPUTS,
    REQUIRED_LIVE_RUNTIME_EVIDENCE_IDS,
    build_foundation_forge_live_runtime_probe_admission_packet,
    build_foundation_forge_live_runtime_signed_evidence_receipt,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "forge_live_runtime_probe_admission_packet.schema.json"
DEFAULT_PACKET = REPO_ROOT / "examples" / "forge_live_runtime_probe_admission_packet.foundation.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "forge_live_runtime_probe_admission_packet_validation.json"


@dataclass(frozen=True, slots=True)
class ForgeLiveRuntimeProbeAdmissionPacketValidation:
    """Validation report for the Forge live-runtime probe admission packet."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    packet_path: str
    packet_id: str
    admission_status: str
    probe_item_count: int
    blocked_reason_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_forge_live_runtime_probe_admission_packet(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    packet_path: Path = DEFAULT_PACKET,
) -> tuple[ForgeLiveRuntimeProbeAdmissionPacketValidation, dict[str, Any]]:
    """Validate probe admission packet schema, semantics, and fixture parity."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "Forge live-runtime probe admission schema", errors)
    packet = _load_json_object(packet_path, "Forge live-runtime probe admission packet", errors)
    produced_packet = build_foundation_forge_live_runtime_probe_admission_packet()

    if schema and packet:
        errors.extend(f"{_path_label(packet_path)}: {error}" for error in _validate_schema_instance(schema, packet))
        _validate_packet_semantics(packet, errors, _path_label(packet_path))
    if schema and produced_packet:
        errors.extend(
            f"produced probe admission packet: {error}"
            for error in _validate_schema_instance(schema, produced_packet)
        )
        _validate_packet_semantics(produced_packet, errors, "produced probe admission packet")
    if packet and produced_packet and packet != produced_packet:
        errors.append("fixture does not match deterministic Forge live-runtime probe admission packet")

    observed_packet = produced_packet or packet
    probe_items = observed_packet.get("probe_items", ())
    blocked_reasons = observed_packet.get("blocked_reasons", ())
    validation = ForgeLiveRuntimeProbeAdmissionPacketValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        packet_path=_path_label(packet_path),
        packet_id=str(observed_packet.get("packet_id", "")),
        admission_status=str(observed_packet.get("admission_status", "")),
        probe_item_count=len(probe_items) if isinstance(probe_items, list) else 0,
        blocked_reason_count=len(blocked_reasons) if isinstance(blocked_reasons, list) else 0,
    )
    return validation, produced_packet


def write_forge_live_runtime_probe_admission_packet_validation(
    validation: ForgeLiveRuntimeProbeAdmissionPacketValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic probe admission validation report."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_packet_semantics(packet: Mapping[str, Any], errors: list[str], label: str) -> None:
    if packet.get("packet_id") != FORGE_LIVE_RUNTIME_PROBE_ADMISSION_PACKET_ID:
        errors.append(f"{label}: packet_id mismatch")
    if packet.get("schema_ref") != FORGE_LIVE_RUNTIME_PROBE_ADMISSION_PACKET_SCHEMA_REF:
        errors.append(f"{label}: schema_ref mismatch")
    if packet.get("bridge_ref") != FORGE_WRITE_SPINE_BRIDGE_ID:
        errors.append(f"{label}: bridge_ref mismatch")
    if packet.get("admission_mode") != "operator_approved_live_probe_required":
        errors.append(f"{label}: admission_mode must remain operator_approved_live_probe_required")
    if packet.get("admission_status") != "blocked_awaiting_operator_approval":
        errors.append(f"{label}: admission_status must remain blocked_awaiting_operator_approval")
    if packet.get("solver_outcome") != "AwaitingEvidence":
        errors.append(f"{label}: solver_outcome must remain AwaitingEvidence")
    signed_receipt = build_foundation_forge_live_runtime_signed_evidence_receipt()
    if packet.get("source_signed_evidence_receipt_hash") != signed_receipt["receipt_hash"]:
        errors.append(f"{label}: source_signed_evidence_receipt_hash mismatch")
    _validate_probe_items(packet, errors, label)
    _validate_authority(packet, errors, label)
    if tuple(packet.get("required_controls", ())) != LIVE_RUNTIME_PROBE_ADMISSION_CONTROLS:
        errors.append(f"{label}: required_controls drift")
    if packet.get("next_allowed_action") != "request_operator_approval_for_bounded_live_probe_inputs":
        errors.append(f"{label}: next_allowed_action drift")


def _validate_probe_items(packet: Mapping[str, Any], errors: list[str], label: str) -> None:
    probe_items = packet.get("probe_items")
    blocked_reasons = packet.get("blocked_reasons")
    if not isinstance(probe_items, list):
        errors.append(f"{label}: probe_items must be a list")
        return
    evidence_ids = tuple(str(item.get("evidence_id", "")) for item in probe_items if isinstance(item, Mapping))
    if evidence_ids != REQUIRED_LIVE_RUNTIME_EVIDENCE_IDS:
        errors.append(f"{label}: probe_items order drift")
    expected_blockers = tuple(
        f"{evidence_id}_operator_approved_probe_missing" for evidence_id in REQUIRED_LIVE_RUNTIME_EVIDENCE_IDS
    )
    if tuple(blocked_reasons or ()) != expected_blockers:
        errors.append(f"{label}: blocked_reasons drift")
    for item in probe_items:
        probe = _mapping(item)
        evidence_id = str(probe.get("evidence_id", ""))
        expected_probe_ref = f"probe://forge/live-runtime/{evidence_id.replace('_', '-')}"
        if probe.get("target_signed_evidence_ref") != LIVE_RUNTIME_EVIDENCE_COLLECTION_TARGETS.get(evidence_id):
            errors.append(f"{label}: {evidence_id}.target_signed_evidence_ref mismatch")
        if probe.get("probe_ref") != expected_probe_ref:
            errors.append(f"{label}: {evidence_id}.probe_ref mismatch")
        if tuple(probe.get("required_inputs", ())) != LIVE_RUNTIME_PROBE_REQUIRED_INPUTS:
            errors.append(f"{label}: {evidence_id}.required_inputs mismatch")
        if probe.get("operator_approval_status") != "not_approved":
            errors.append(f"{label}: {evidence_id}.operator_approval_status must remain not_approved")
        if probe.get("probe_admission_status") != "blocked":
            errors.append(f"{label}: {evidence_id}.probe_admission_status must remain blocked")
        if probe.get("probe_execution_allowed") is not False:
            errors.append(f"{label}: {evidence_id}.probe_execution_allowed must remain false")
        if probe.get("external_effects_requested") is not False:
            errors.append(f"{label}: {evidence_id}.external_effects_requested must remain false")
        if probe.get("signed_receipt_population_allowed") is not False:
            errors.append(f"{label}: {evidence_id}.signed_receipt_population_allowed must remain false")
        if probe.get("blocker_reason") != f"{evidence_id}_operator_approved_probe_missing":
            errors.append(f"{label}: {evidence_id}.blocker_reason mismatch")
        if probe.get("authority_effect") is not False:
            errors.append(f"{label}: {evidence_id}.authority_effect must remain false")


def _validate_authority(packet: Mapping[str, Any], errors: list[str], label: str) -> None:
    disallowed_authority = _mapping(packet.get("disallowed_authority"))
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
    """Parse Forge live-runtime probe admission validation arguments."""

    parser = argparse.ArgumentParser(description="Validate Forge live-runtime probe admission packet.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--packet", default=str(DEFAULT_PACKET))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for Forge live-runtime probe admission validation."""

    args = parse_args(argv)
    validation, produced_packet = validate_forge_live_runtime_probe_admission_packet(
        schema_path=Path(args.schema),
        packet_path=Path(args.packet),
    )
    write_forge_live_runtime_probe_admission_packet_validation(validation, Path(args.output))
    if args.json:
        payload = validation.as_dict()
        payload["produced_packet"] = produced_packet
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif validation.ok:
        print("FORGE LIVE-RUNTIME PROBE ADMISSION PACKET VALID")
    else:
        print(f"FORGE LIVE-RUNTIME PROBE ADMISSION PACKET INVALID errors={list(validation.errors)}")
    return 0 if validation.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
