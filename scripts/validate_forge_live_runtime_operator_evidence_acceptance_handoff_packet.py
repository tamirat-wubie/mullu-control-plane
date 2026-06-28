#!/usr/bin/env python3
"""Validate the Forge live-runtime operator evidence acceptance handoff packet.

Purpose: prove independently verified operator evidence can be routed toward
acceptance review without treating the handoff itself as evidence acceptance,
runtime authority, production authority, commit authority, or signed receipt
population authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: gateway.forge_state_write_admission, acceptance handoff schema,
acceptance handoff fixture, verification gate fixture, and shared schema
validation.
Invariants:
  - Only fully verified evidence items become ready for acceptance review.
  - Acceptance review readiness does not grant acceptance authority.
  - Runtime, production, commit, external-effect, signed-receipt population,
    and terminal closure authority remain false.
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
    FORGE_LIVE_RUNTIME_OPERATOR_EVIDENCE_ACCEPTANCE_HANDOFF_PACKET_ID,
    FORGE_LIVE_RUNTIME_OPERATOR_EVIDENCE_ACCEPTANCE_HANDOFF_PACKET_SCHEMA_REF,
    FORGE_WRITE_SPINE_BRIDGE_ID,
    LIVE_RUNTIME_EVIDENCE_COLLECTION_TARGETS,
    LIVE_RUNTIME_OPERATOR_EVIDENCE_ACCEPTANCE_HANDOFF_CONTROLS,
    LIVE_RUNTIME_OPERATOR_REQUIRED_EVIDENCE_CLASSES,
    REQUIRED_LIVE_RUNTIME_EVIDENCE_IDS,
    build_foundation_forge_live_runtime_operator_evidence_acceptance_handoff_packet,
    build_foundation_forge_live_runtime_operator_evidence_verification_gate,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = (
    REPO_ROOT / "schemas" / "forge_live_runtime_operator_evidence_acceptance_handoff_packet.schema.json"
)
DEFAULT_PACKET = (
    REPO_ROOT / "examples" / "forge_live_runtime_operator_evidence_acceptance_handoff_packet.foundation.json"
)
DEFAULT_VERIFICATION_GATE = (
    REPO_ROOT / "examples" / "forge_live_runtime_operator_evidence_verification_gate.foundation.json"
)
DEFAULT_OUTPUT = (
    REPO_ROOT / ".change_assurance" / "forge_live_runtime_operator_evidence_acceptance_handoff_packet_validation.json"
)
REQUIRED_TOTAL_ITEM_COUNT = len(REQUIRED_LIVE_RUNTIME_EVIDENCE_IDS)


@dataclass(frozen=True, slots=True)
class ForgeLiveRuntimeOperatorEvidenceAcceptanceHandoffPacketValidation:
    """Validation report for the Forge operator evidence acceptance handoff packet."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    packet_path: str
    packet_id: str
    handoff_status: str
    handoff_item_count: int
    ready_item_count: int
    required_item_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_forge_live_runtime_operator_evidence_acceptance_handoff_packet(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    packet_path: Path = DEFAULT_PACKET,
    verification_gate_path: Path = DEFAULT_VERIFICATION_GATE,
) -> tuple[ForgeLiveRuntimeOperatorEvidenceAcceptanceHandoffPacketValidation, dict[str, Any]]:
    """Validate acceptance handoff packet schema, semantics, and fixture parity."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "Forge operator evidence acceptance handoff schema", errors)
    packet = _load_json_object(packet_path, "Forge operator evidence acceptance handoff packet", errors)
    verification_gate = _load_json_object(verification_gate_path, "Forge operator evidence verification gate", errors)
    produced_packet = build_foundation_forge_live_runtime_operator_evidence_acceptance_handoff_packet()

    if schema and packet:
        errors.extend(f"{_path_label(packet_path)}: {error}" for error in _validate_schema_instance(schema, packet))
        _validate_packet_semantics(
            packet,
            verification_gate,
            errors,
            _path_label(packet_path),
            _path_label(verification_gate_path),
        )
    if schema and produced_packet:
        errors.extend(
            f"produced operator evidence acceptance handoff packet: {error}"
            for error in _validate_schema_instance(schema, produced_packet)
        )
        default_verification_gate = build_foundation_forge_live_runtime_operator_evidence_verification_gate()
        _validate_packet_semantics(
            produced_packet,
            default_verification_gate,
            errors,
            "produced operator evidence acceptance handoff packet",
            "examples/forge_live_runtime_operator_evidence_verification_gate.foundation.json",
        )
    if _is_default_packet_path(packet_path) and packet and produced_packet and packet != produced_packet:
        errors.append("fixture does not match deterministic Forge live-runtime operator evidence acceptance handoff packet")

    observed = packet or produced_packet
    handoff_items = observed.get("handoff_items", ())
    validation = ForgeLiveRuntimeOperatorEvidenceAcceptanceHandoffPacketValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        packet_path=_path_label(packet_path),
        packet_id=str(observed.get("packet_id", "")),
        handoff_status=str(observed.get("handoff_status", "")),
        handoff_item_count=len(handoff_items) if isinstance(handoff_items, list) else 0,
        ready_item_count=int(observed.get("ready_item_count", 0))
        if not isinstance(observed.get("ready_item_count"), bool)
        else 0,
        required_item_count=int(observed.get("required_item_count", 0))
        if not isinstance(observed.get("required_item_count"), bool)
        else 0,
    )
    return validation, produced_packet


def write_forge_live_runtime_operator_evidence_acceptance_handoff_packet_validation(
    validation: ForgeLiveRuntimeOperatorEvidenceAcceptanceHandoffPacketValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic operator evidence acceptance handoff validation report."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_packet_semantics(
    packet: Mapping[str, Any],
    verification_gate: Mapping[str, Any],
    errors: list[str],
    label: str,
    verification_gate_label: str,
) -> None:
    if packet.get("packet_id") != FORGE_LIVE_RUNTIME_OPERATOR_EVIDENCE_ACCEPTANCE_HANDOFF_PACKET_ID:
        errors.append(f"{label}: packet_id mismatch")
    if packet.get("schema_ref") != FORGE_LIVE_RUNTIME_OPERATOR_EVIDENCE_ACCEPTANCE_HANDOFF_PACKET_SCHEMA_REF:
        errors.append(f"{label}: schema_ref mismatch")
    if packet.get("bridge_ref") != FORGE_WRITE_SPINE_BRIDGE_ID:
        errors.append(f"{label}: bridge_ref mismatch")
    if packet.get("source_operator_evidence_verification_gate_ref") != verification_gate_label:
        errors.append(f"{label}: source_operator_evidence_verification_gate_ref mismatch")
    if packet.get("source_operator_evidence_verification_gate_hash") != verification_gate.get("gate_hash"):
        errors.append(f"{label}: source_operator_evidence_verification_gate_hash mismatch")
    if packet.get("handoff_mode") != "verified_operator_evidence_to_acceptance_review":
        errors.append(f"{label}: handoff_mode drift")
    if packet.get("solver_outcome") != "AwaitingEvidence":
        errors.append(f"{label}: solver_outcome must remain AwaitingEvidence")
    if packet.get("proof_state") != "Unknown":
        errors.append(f"{label}: proof_state must remain Unknown")
    for field_name in (
        "acceptance_authority_effect",
        "signed_receipt_population_allowed",
        "runtime_authority_effect",
        "secret_values_present",
    ):
        if packet.get(field_name) is not False:
            errors.append(f"{label}: {field_name} must remain false")
    _validate_handoff_items(packet, _verification_item_index(verification_gate), errors, label)
    _validate_summary(packet, errors, label)
    _validate_authority(packet, errors, label)
    if tuple(packet.get("required_controls", ())) != LIVE_RUNTIME_OPERATOR_EVIDENCE_ACCEPTANCE_HANDOFF_CONTROLS:
        errors.append(f"{label}: required_controls drift")
    if packet.get("next_allowed_action") != "route_verified_operator_evidence_to_acceptance_review":
        errors.append(f"{label}: next_allowed_action drift")


def _validate_handoff_items(
    packet: Mapping[str, Any],
    verification_items_by_id: Mapping[str, Mapping[str, Any]],
    errors: list[str],
    label: str,
) -> None:
    handoff_items = packet.get("handoff_items")
    if not isinstance(handoff_items, list):
        errors.append(f"{label}: handoff_items must be a list")
        return
    evidence_ids = tuple(str(item.get("evidence_id", "")) for item in handoff_items if isinstance(item, Mapping))
    if evidence_ids != REQUIRED_LIVE_RUNTIME_EVIDENCE_IDS:
        errors.append(f"{label}: handoff_items order drift")
    for item in handoff_items:
        handoff_item = _mapping(item)
        evidence_id = str(handoff_item.get("evidence_id", ""))
        verification_item = verification_items_by_id.get(evidence_id, {})
        expected_verification_ref = (
            f"verification://forge/live-runtime/operator-evidence/{evidence_id.replace('_', '-')}"
        )
        if handoff_item.get("target_evidence_ref") != LIVE_RUNTIME_EVIDENCE_COLLECTION_TARGETS.get(evidence_id):
            errors.append(f"{label}: {evidence_id}.target_evidence_ref mismatch")
        if handoff_item.get("source_verification_ref") != expected_verification_ref:
            errors.append(f"{label}: {evidence_id}.source_verification_ref mismatch")
        if handoff_item.get("required_verification_count") != len(LIVE_RUNTIME_OPERATOR_REQUIRED_EVIDENCE_CLASSES):
            errors.append(f"{label}: {evidence_id}.required_verification_count drift")
        verified_count = int(verification_item.get("verified_ref_count", 0))
        if isinstance(verification_item.get("verified_ref_count"), bool):
            verified_count = 0
        ready = verification_item.get("all_slots_verified") is True and verified_count == len(
            LIVE_RUNTIME_OPERATOR_REQUIRED_EVIDENCE_CLASSES
        )
        expected_status = "verified_pending_acceptance" if ready else "missing"
        expected_blocker = "" if ready else f"{evidence_id}_verified_operator_evidence_missing"
        if handoff_item.get("verified_ref_count") != verified_count:
            errors.append(f"{label}: {evidence_id}.verified_ref_count mismatch")
        if handoff_item.get("ready_for_acceptance_review") is not ready:
            errors.append(f"{label}: {evidence_id}.ready_for_acceptance_review mismatch")
        if handoff_item.get("verification_status") != expected_status:
            errors.append(f"{label}: {evidence_id}.verification_status must be {expected_status}")
        if handoff_item.get("blocker_reason") != expected_blocker:
            errors.append(f"{label}: {evidence_id}.blocker_reason mismatch")
        if handoff_item.get("acceptance_authority_effect") is not False:
            errors.append(f"{label}: {evidence_id}.acceptance_authority_effect must remain false")
        if handoff_item.get("signed_receipt_population_allowed") is not False:
            errors.append(f"{label}: {evidence_id}.signed_receipt_population_allowed must remain false")


def _validate_summary(packet: Mapping[str, Any], errors: list[str], label: str) -> None:
    handoff_items = packet.get("handoff_items")
    if not isinstance(handoff_items, list):
        return
    ready_item_count = sum(
        1 for item in handoff_items if _mapping(item).get("ready_for_acceptance_review") is True
    )
    all_ready = ready_item_count == REQUIRED_TOTAL_ITEM_COUNT
    expected_status = (
        "verified_operator_evidence_ready_for_acceptance_review"
        if all_ready
        else "blocked_awaiting_verified_operator_evidence"
    )
    expected_blockers = [
        str(_mapping(item).get("blocker_reason", ""))
        for item in handoff_items
        if _mapping(item).get("ready_for_acceptance_review") is not True
    ]
    if packet.get("handoff_status") != expected_status:
        errors.append(f"{label}: handoff_status must be {expected_status}")
    if packet.get("handoff_item_count") != REQUIRED_TOTAL_ITEM_COUNT:
        errors.append(f"{label}: handoff_item_count drift")
    if packet.get("ready_item_count") != ready_item_count:
        errors.append(f"{label}: ready_item_count mismatch")
    if packet.get("required_item_count") != REQUIRED_TOTAL_ITEM_COUNT:
        errors.append(f"{label}: required_item_count drift")
    if packet.get("all_items_ready_for_acceptance_review") is not all_ready:
        errors.append(f"{label}: all_items_ready_for_acceptance_review mismatch")
    if packet.get("acceptance_review_allowed") is not all_ready:
        errors.append(f"{label}: acceptance_review_allowed mismatch")
    if list(packet.get("blocked_reasons", ())) != expected_blockers:
        errors.append(f"{label}: blocked_reasons mismatch")


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


def _verification_item_index(verification_gate: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        str(_mapping(item).get("evidence_id", "")): _mapping(item)
        for item in verification_gate.get("verification_items", [])
    }


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


def _is_default_packet_path(path: Path) -> bool:
    return path.resolve(strict=False) == DEFAULT_PACKET.resolve(strict=False)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse Forge operator evidence acceptance handoff validation arguments."""

    parser = argparse.ArgumentParser(
        description="Validate Forge live-runtime operator evidence acceptance handoff packet."
    )
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--packet", default=str(DEFAULT_PACKET))
    parser.add_argument("--verification-gate", default=str(DEFAULT_VERIFICATION_GATE))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for Forge operator evidence acceptance handoff validation."""

    args = parse_args(argv)
    validation, produced_packet = validate_forge_live_runtime_operator_evidence_acceptance_handoff_packet(
        schema_path=Path(args.schema),
        packet_path=Path(args.packet),
        verification_gate_path=Path(args.verification_gate),
    )
    write_forge_live_runtime_operator_evidence_acceptance_handoff_packet_validation(
        validation,
        Path(args.output),
    )
    if args.json:
        payload = validation.as_dict()
        payload["produced_packet"] = produced_packet
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif validation.ok:
        print("FORGE LIVE-RUNTIME OPERATOR EVIDENCE ACCEPTANCE HANDOFF PACKET VALID")
    else:
        print(
            "FORGE LIVE-RUNTIME OPERATOR EVIDENCE ACCEPTANCE HANDOFF PACKET INVALID "
            f"errors={list(validation.errors)}"
        )
    return 0 if validation.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
