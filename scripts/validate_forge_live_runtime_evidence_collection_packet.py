#!/usr/bin/env python3
"""Validate the Forge live-runtime evidence collection packet.

Purpose: prove Forge live-runtime evidence collection remains local planning
only and cannot register runtime authority or mark evidence collected.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: gateway.forge_state_write_admission, evidence collection schema,
evidence collection fixture, and shared schema validation.
Invariants:
  - Evidence collection is local planning only.
  - Evidence items remain not collected in the Foundation fixture.
  - Runtime, production, commit, external effect, and terminal closure
    authority remain false.
  - The checked-in packet matches the deterministic builder output.
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
    FORGE_LIVE_RUNTIME_EVIDENCE_COLLECTION_PACKET_ID,
    FORGE_LIVE_RUNTIME_EVIDENCE_COLLECTION_PACKET_SCHEMA_REF,
    FORGE_WRITE_SPINE_BRIDGE_ID,
    LIVE_RUNTIME_EVIDENCE_COLLECTION_CONTROLS,
    LIVE_RUNTIME_EVIDENCE_COLLECTION_TARGETS,
    REQUIRED_LIVE_RUNTIME_EVIDENCE_IDS,
    build_foundation_forge_live_runtime_evidence_collection_packet,
    build_foundation_forge_live_runtime_readiness_gate,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "forge_live_runtime_evidence_collection_packet.schema.json"
DEFAULT_PACKET = REPO_ROOT / "examples" / "forge_live_runtime_evidence_collection_packet.foundation.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "forge_live_runtime_evidence_collection_packet_validation.json"


@dataclass(frozen=True, slots=True)
class ForgeLiveRuntimeEvidenceCollectionPacketValidation:
    """Validation report for the Forge live-runtime evidence collection packet."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    packet_path: str
    packet_id: str
    collection_status: str
    evidence_count: int
    blocked_reason_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_forge_live_runtime_evidence_collection_packet(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    packet_path: Path = DEFAULT_PACKET,
) -> tuple[ForgeLiveRuntimeEvidenceCollectionPacketValidation, dict[str, Any]]:
    """Validate collection packet schema, semantics, and deterministic fixture."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "Forge live-runtime evidence collection schema", errors)
    packet = _load_json_object(packet_path, "Forge live-runtime evidence collection packet", errors)
    produced_packet = build_foundation_forge_live_runtime_evidence_collection_packet()

    if schema and packet:
        errors.extend(f"{_path_label(packet_path)}: {error}" for error in _validate_schema_instance(schema, packet))
        _validate_packet_semantics(packet, errors, _path_label(packet_path))
    if schema and produced_packet:
        errors.extend(
            f"produced evidence collection packet: {error}"
            for error in _validate_schema_instance(schema, produced_packet)
        )
        _validate_packet_semantics(produced_packet, errors, "produced evidence collection packet")
    if packet and produced_packet and packet != produced_packet:
        errors.append("fixture does not match deterministic Forge live-runtime evidence collection packet")

    observed_packet = produced_packet or packet
    evidence_items = observed_packet.get("evidence_items", ())
    blocked_reasons = observed_packet.get("blocked_reasons", ())
    validation = ForgeLiveRuntimeEvidenceCollectionPacketValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        packet_path=_path_label(packet_path),
        packet_id=str(observed_packet.get("packet_id", "")),
        collection_status=str(observed_packet.get("collection_status", "")),
        evidence_count=len(evidence_items) if isinstance(evidence_items, list) else 0,
        blocked_reason_count=len(blocked_reasons) if isinstance(blocked_reasons, list) else 0,
    )
    return validation, produced_packet


def write_forge_live_runtime_evidence_collection_packet_validation(
    validation: ForgeLiveRuntimeEvidenceCollectionPacketValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic evidence collection validation report."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_packet_semantics(packet: Mapping[str, Any], errors: list[str], label: str) -> None:
    if packet.get("packet_id") != FORGE_LIVE_RUNTIME_EVIDENCE_COLLECTION_PACKET_ID:
        errors.append(f"{label}: packet_id mismatch")
    if packet.get("schema_ref") != FORGE_LIVE_RUNTIME_EVIDENCE_COLLECTION_PACKET_SCHEMA_REF:
        errors.append(f"{label}: schema_ref mismatch")
    if packet.get("bridge_ref") != FORGE_WRITE_SPINE_BRIDGE_ID:
        errors.append(f"{label}: bridge_ref mismatch")
    if packet.get("collection_mode") != "local_evidence_planning_only":
        errors.append(f"{label}: collection_mode must remain local_evidence_planning_only")
    if packet.get("solver_outcome") != "AwaitingEvidence":
        errors.append(f"{label}: solver_outcome must remain AwaitingEvidence")
    if packet.get("collection_status") != "not_started":
        errors.append(f"{label}: collection_status must remain not_started")
    readiness_gate = build_foundation_forge_live_runtime_readiness_gate()
    if packet.get("source_readiness_gate_hash") != readiness_gate["gate_hash"]:
        errors.append(f"{label}: source_readiness_gate_hash mismatch")
    _validate_evidence_items(packet, errors, label)
    _validate_authority(packet, errors, label)
    if tuple(packet.get("required_controls", ())) != LIVE_RUNTIME_EVIDENCE_COLLECTION_CONTROLS:
        errors.append(f"{label}: required_controls drift")
    if packet.get("next_allowed_action") != "write_local_evidence_artifacts_without_registering_runtime_authority":
        errors.append(f"{label}: next_allowed_action drift")


def _validate_evidence_items(packet: Mapping[str, Any], errors: list[str], label: str) -> None:
    evidence_items = packet.get("evidence_items")
    blocked_reasons = packet.get("blocked_reasons")
    if not isinstance(evidence_items, list):
        errors.append(f"{label}: evidence_items must be a list")
        return
    evidence_ids = tuple(str(item.get("evidence_id", "")) for item in evidence_items if isinstance(item, Mapping))
    if evidence_ids != REQUIRED_LIVE_RUNTIME_EVIDENCE_IDS:
        errors.append(f"{label}: evidence_items order drift")
    expected_blockers = tuple(f"{evidence_id}_missing" for evidence_id in REQUIRED_LIVE_RUNTIME_EVIDENCE_IDS)
    if tuple(blocked_reasons or ()) != expected_blockers:
        errors.append(f"{label}: blocked_reasons drift")
    for item in evidence_items:
        evidence = _mapping(item)
        evidence_id = str(evidence.get("evidence_id", ""))
        if evidence.get("collection_status") != "not_collected":
            errors.append(f"{label}: {evidence_id}.collection_status must remain not_collected")
        if evidence.get("source_blocker_reason") != f"{evidence_id}_missing":
            errors.append(f"{label}: {evidence_id}.source_blocker_reason mismatch")
        if evidence.get("target_evidence_ref") != LIVE_RUNTIME_EVIDENCE_COLLECTION_TARGETS.get(evidence_id):
            errors.append(f"{label}: {evidence_id}.target_evidence_ref mismatch")
        if evidence.get("allowed_collection_mode") != "local_design_or_rehearsal_only":
            errors.append(f"{label}: {evidence_id}.allowed_collection_mode mismatch")
        if evidence.get("authority_effect") is not False:
            errors.append(f"{label}: {evidence_id}.authority_effect must remain false")
        if evidence.get("collected") is not False:
            errors.append(f"{label}: {evidence_id}.collected must remain false")


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
    """Parse Forge live-runtime evidence collection validation arguments."""

    parser = argparse.ArgumentParser(description="Validate Forge live-runtime evidence collection packet.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--packet", default=str(DEFAULT_PACKET))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for Forge live-runtime evidence collection validation."""

    args = parse_args(argv)
    validation, produced_packet = validate_forge_live_runtime_evidence_collection_packet(
        schema_path=Path(args.schema),
        packet_path=Path(args.packet),
    )
    write_forge_live_runtime_evidence_collection_packet_validation(validation, Path(args.output))
    if args.json:
        payload = validation.as_dict()
        payload["produced_packet"] = produced_packet
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif validation.ok:
        print("FORGE LIVE-RUNTIME EVIDENCE COLLECTION PACKET VALID")
    else:
        print(f"FORGE LIVE-RUNTIME EVIDENCE COLLECTION PACKET INVALID errors={list(validation.errors)}")
    return 0 if validation.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
