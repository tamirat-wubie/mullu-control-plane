#!/usr/bin/env python3
"""Validate the Forge live-runtime operator evidence verification gate.

Purpose: prove submitted operator evidence references are not treated as
verified evidence until independent verification exists.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: gateway.forge_state_write_admission, verification gate schema,
verification gate fixture, and shared schema validation.
Invariants:
  - Submitted refs are not accepted as verification.
  - Runtime, production, commit, external-effect, signed-receipt population,
    promotion, and terminal closure authority remain false.
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
    FORGE_LIVE_RUNTIME_OPERATOR_EVIDENCE_VERIFICATION_GATE_ID,
    FORGE_LIVE_RUNTIME_OPERATOR_EVIDENCE_VERIFICATION_GATE_SCHEMA_REF,
    FORGE_WRITE_SPINE_BRIDGE_ID,
    LIVE_RUNTIME_EVIDENCE_COLLECTION_TARGETS,
    LIVE_RUNTIME_OPERATOR_EVIDENCE_VERIFICATION_CONTROLS,
    LIVE_RUNTIME_OPERATOR_REQUIRED_EVIDENCE_CLASSES,
    REQUIRED_LIVE_RUNTIME_EVIDENCE_IDS,
    build_foundation_forge_live_runtime_operator_evidence_submission_packet,
    build_foundation_forge_live_runtime_operator_evidence_verification_gate,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "forge_live_runtime_operator_evidence_verification_gate.schema.json"
DEFAULT_GATE = REPO_ROOT / "examples" / "forge_live_runtime_operator_evidence_verification_gate.foundation.json"
DEFAULT_SUBMISSION_PACKET = REPO_ROOT / "examples" / "forge_live_runtime_operator_evidence_submission_packet.foundation.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "forge_live_runtime_operator_evidence_verification_gate_validation.json"
REQUIRED_TOTAL_VERIFICATION_COUNT = len(REQUIRED_LIVE_RUNTIME_EVIDENCE_IDS) * len(LIVE_RUNTIME_OPERATOR_REQUIRED_EVIDENCE_CLASSES)


@dataclass(frozen=True, slots=True)
class ForgeLiveRuntimeOperatorEvidenceVerificationGateValidation:
    """Validation report for the Forge operator evidence verification gate."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    gate_path: str
    gate_id: str
    verification_status: str
    verification_item_count: int
    verified_ref_count: int
    required_verification_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_forge_live_runtime_operator_evidence_verification_gate(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    gate_path: Path = DEFAULT_GATE,
    submission_packet_path: Path = DEFAULT_SUBMISSION_PACKET,
) -> tuple[ForgeLiveRuntimeOperatorEvidenceVerificationGateValidation, dict[str, Any]]:
    """Validate verification gate schema, semantics, and fixture parity."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "Forge operator evidence verification schema", errors)
    gate = _load_json_object(gate_path, "Forge operator evidence verification gate", errors)
    submission_packet = _load_json_object(submission_packet_path, "Forge operator evidence submission packet", errors)
    produced_gate = build_foundation_forge_live_runtime_operator_evidence_verification_gate()

    if schema and gate:
        errors.extend(f"{_path_label(gate_path)}: {error}" for error in _validate_schema_instance(schema, gate))
        _validate_gate_semantics(gate, submission_packet, errors, _path_label(gate_path), _path_label(submission_packet_path))
    if schema and produced_gate:
        errors.extend(
            f"produced operator evidence verification gate: {error}"
            for error in _validate_schema_instance(schema, produced_gate)
        )
        default_submission_packet = build_foundation_forge_live_runtime_operator_evidence_submission_packet()
        _validate_gate_semantics(
            produced_gate,
            default_submission_packet,
            errors,
            "produced operator evidence verification gate",
            "examples/forge_live_runtime_operator_evidence_submission_packet.foundation.json",
        )
    if _is_default_gate_path(gate_path) and gate and produced_gate and gate != produced_gate:
        errors.append("fixture does not match deterministic Forge live-runtime operator evidence verification gate")

    observed = gate or produced_gate
    verification_items = observed.get("verification_items", ())
    validation = ForgeLiveRuntimeOperatorEvidenceVerificationGateValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        gate_path=_path_label(gate_path),
        gate_id=str(observed.get("gate_id", "")),
        verification_status=str(observed.get("verification_status", "")),
        verification_item_count=len(verification_items) if isinstance(verification_items, list) else 0,
        verified_ref_count=int(observed.get("verified_ref_count", 0))
        if not isinstance(observed.get("verified_ref_count"), bool)
        else 0,
        required_verification_count=int(observed.get("required_verification_count", 0))
        if not isinstance(observed.get("required_verification_count"), bool)
        else 0,
    )
    return validation, produced_gate


def write_forge_live_runtime_operator_evidence_verification_gate_validation(
    validation: ForgeLiveRuntimeOperatorEvidenceVerificationGateValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic operator evidence verification validation report."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_gate_semantics(
    gate: Mapping[str, Any],
    submission_packet: Mapping[str, Any],
    errors: list[str],
    label: str,
    submission_label: str,
) -> None:
    if gate.get("gate_id") != FORGE_LIVE_RUNTIME_OPERATOR_EVIDENCE_VERIFICATION_GATE_ID:
        errors.append(f"{label}: gate_id mismatch")
    if gate.get("schema_ref") != FORGE_LIVE_RUNTIME_OPERATOR_EVIDENCE_VERIFICATION_GATE_SCHEMA_REF:
        errors.append(f"{label}: schema_ref mismatch")
    if gate.get("bridge_ref") != FORGE_WRITE_SPINE_BRIDGE_ID:
        errors.append(f"{label}: bridge_ref mismatch")
    if gate.get("verification_status") not in {
        "blocked_awaiting_operator_evidence_verification",
        "verified_pending_acceptance",
    }:
        errors.append(f"{label}: verification_status invalid")
    if gate.get("solver_outcome") != "AwaitingEvidence":
        errors.append(f"{label}: solver_outcome must remain AwaitingEvidence")
    if gate.get("proof_state") != "Unknown":
        errors.append(f"{label}: proof_state must remain Unknown")
    for field_name in (
        "promotion_allowed",
        "signed_receipt_population_allowed",
        "runtime_authority_effect",
        "secret_values_present",
    ):
        if gate.get(field_name) is not False:
            errors.append(f"{label}: {field_name} must remain false")
    if gate.get("source_operator_evidence_submission_packet_ref") != submission_label:
        errors.append(f"{label}: source_operator_evidence_submission_packet_ref mismatch")
    if gate.get("source_operator_evidence_submission_packet_hash") != submission_packet.get("packet_hash"):
        errors.append(f"{label}: source_operator_evidence_submission_packet_hash mismatch")
    source_slots = _submission_slot_index(submission_packet)
    _validate_verification_items(gate, source_slots, errors, label)
    _validate_summary(gate, errors, label)
    _validate_authority(gate, errors, label)
    if tuple(gate.get("required_controls", ())) != LIVE_RUNTIME_OPERATOR_EVIDENCE_VERIFICATION_CONTROLS:
        errors.append(f"{label}: required_controls drift")
    if gate.get("next_allowed_action") != "verify_submitted_operator_evidence_refs_before_acceptance":
        errors.append(f"{label}: next_allowed_action drift")


def _validate_verification_items(
    gate: Mapping[str, Any],
    source_slots: Mapping[tuple[str, str], Mapping[str, Any]],
    errors: list[str],
    label: str,
) -> None:
    verification_items = gate.get("verification_items")
    if not isinstance(verification_items, list):
        errors.append(f"{label}: verification_items must be a list")
        return
    evidence_ids = tuple(str(item.get("evidence_id", "")) for item in verification_items if isinstance(item, Mapping))
    if evidence_ids != REQUIRED_LIVE_RUNTIME_EVIDENCE_IDS:
        errors.append(f"{label}: verification_items order drift")
    for item in verification_items:
        verification_item = _mapping(item)
        evidence_id = str(verification_item.get("evidence_id", ""))
        if verification_item.get("target_evidence_ref") != LIVE_RUNTIME_EVIDENCE_COLLECTION_TARGETS.get(evidence_id):
            errors.append(f"{label}: {evidence_id}.target_evidence_ref mismatch")
        expected_submission_ref = f"submission://forge/live-runtime/operator-evidence/{evidence_id.replace('_', '-')}"
        if verification_item.get("source_submission_ref") != expected_submission_ref:
            errors.append(f"{label}: {evidence_id}.source_submission_ref mismatch")
        if verification_item.get("required_verification_count") != len(LIVE_RUNTIME_OPERATOR_REQUIRED_EVIDENCE_CLASSES):
            errors.append(f"{label}: {evidence_id}.required_verification_count drift")
        slots = verification_item.get("verification_slots")
        if not isinstance(slots, list):
            errors.append(f"{label}: {evidence_id}.verification_slots must be a list")
            continue
        if tuple(str(slot.get("evidence_class", "")) for slot in slots if isinstance(slot, Mapping)) != (
            LIVE_RUNTIME_OPERATOR_REQUIRED_EVIDENCE_CLASSES
        ):
            errors.append(f"{label}: {evidence_id}.verification_slots class order drift")
        submitted_count = 0
        verified_count = 0
        for slot in slots:
            slot_submitted, slot_verified = _validate_slot(_mapping(slot), source_slots, errors, label, evidence_id)
            if slot_submitted:
                submitted_count += 1
            if slot_verified:
                verified_count += 1
        if verification_item.get("submitted_ref_count") != submitted_count:
            errors.append(f"{label}: {evidence_id}.submitted_ref_count mismatch")
        if verification_item.get("verified_ref_count") != verified_count:
            errors.append(f"{label}: {evidence_id}.verified_ref_count mismatch")
        if verification_item.get("all_slots_verified") is not (verified_count == len(LIVE_RUNTIME_OPERATOR_REQUIRED_EVIDENCE_CLASSES)):
            errors.append(f"{label}: {evidence_id}.all_slots_verified mismatch")
        expected_status = "verified_pending_acceptance" if verified_count == len(LIVE_RUNTIME_OPERATOR_REQUIRED_EVIDENCE_CLASSES) else "blocked_awaiting_submitted_refs"
        if verification_item.get("verification_status") != expected_status:
            errors.append(f"{label}: {evidence_id}.verification_status must be {expected_status}")


def _validate_slot(
    slot: Mapping[str, Any],
    source_slots: Mapping[tuple[str, str], Mapping[str, Any]],
    errors: list[str],
    label: str,
    evidence_id: str,
) -> tuple[bool, bool]:
    evidence_class = str(slot.get("evidence_class", ""))
    source_evidence_ref = str(slot.get("source_evidence_ref", ""))
    source_ref_hash = str(slot.get("source_ref_hash", ""))
    verification_ref = str(slot.get("verification_ref", ""))
    verifier_identity_ref = str(slot.get("verifier_identity_ref", ""))
    verification_passed = slot.get("verification_passed") is True
    source_slot = source_slots.get((evidence_id, evidence_class), {})
    if source_evidence_ref:
        if source_evidence_ref != source_slot.get("evidence_ref"):
            errors.append(f"{label}: {evidence_id}.{evidence_class}.source_evidence_ref mismatch")
        if source_ref_hash != source_slot.get("ref_hash"):
            errors.append(f"{label}: {evidence_id}.{evidence_class}.source_ref_hash mismatch")
        if not verification_ref:
            errors.append(f"{label}: {evidence_id}.{evidence_class}.verification_ref required")
        if not verifier_identity_ref:
            errors.append(f"{label}: {evidence_id}.{evidence_class}.verifier_identity_ref required")
        if slot.get("verification_status") != "verified":
            errors.append(f"{label}: {evidence_id}.{evidence_class}.verification_status must be verified")
        if not verification_passed:
            errors.append(f"{label}: {evidence_id}.{evidence_class}.verification_passed must be true")
    else:
        for field_name in ("source_ref_hash", "verification_ref", "verifier_identity_ref"):
            if str(slot.get(field_name, "")):
                errors.append(f"{label}: {evidence_id}.{evidence_class}.{field_name} must remain empty when source missing")
        if slot.get("verification_status") != "not_submitted":
            errors.append(f"{label}: {evidence_id}.{evidence_class}.verification_status must be not_submitted")
        if verification_passed:
            errors.append(f"{label}: {evidence_id}.{evidence_class}.verification_passed must be false when source missing")
    if slot.get("authority_effect") is not False:
        errors.append(f"{label}: {evidence_id}.{evidence_class}.authority_effect must remain false")
    return bool(source_evidence_ref), verification_passed


def _validate_summary(gate: Mapping[str, Any], errors: list[str], label: str) -> None:
    if gate.get("verification_item_count") != len(REQUIRED_LIVE_RUNTIME_EVIDENCE_IDS):
        errors.append(f"{label}: verification_item_count drift")
    verification_items = gate.get("verification_items")
    if not isinstance(verification_items, list):
        return
    submitted_ref_count = sum(int(_mapping(item).get("submitted_ref_count", 0)) for item in verification_items)
    verified_ref_count = sum(int(_mapping(item).get("verified_ref_count", 0)) for item in verification_items)
    if gate.get("submitted_ref_count") != submitted_ref_count:
        errors.append(f"{label}: submitted_ref_count mismatch")
    if gate.get("verified_ref_count") != verified_ref_count:
        errors.append(f"{label}: verified_ref_count mismatch")
    if gate.get("required_verification_count") != REQUIRED_TOTAL_VERIFICATION_COUNT:
        errors.append(f"{label}: required_verification_count drift")
    all_verified = verified_ref_count == REQUIRED_TOTAL_VERIFICATION_COUNT
    if gate.get("all_submitted_refs_verified") is not all_verified:
        errors.append(f"{label}: all_submitted_refs_verified mismatch")
    expected_status = "verified_pending_acceptance" if all_verified else "blocked_awaiting_operator_evidence_verification"
    if gate.get("verification_status") != expected_status:
        errors.append(f"{label}: verification_status must be {expected_status}")
    expected_blockers = tuple(
        f"{evidence_id}_verification_missing"
        for evidence_id in REQUIRED_LIVE_RUNTIME_EVIDENCE_IDS
        if not _item_verified(gate, evidence_id)
    )
    if tuple(gate.get("blocked_reasons", ())) != expected_blockers:
        errors.append(f"{label}: blocked_reasons drift")


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


def _submission_slot_index(submission_packet: Mapping[str, Any]) -> dict[tuple[str, str], Mapping[str, Any]]:
    indexed: dict[tuple[str, str], Mapping[str, Any]] = {}
    for item in submission_packet.get("submission_items", []):
        submission_item = _mapping(item)
        evidence_id = str(submission_item.get("evidence_id", ""))
        for slot in submission_item.get("submitted_refs", []):
            submission_slot = _mapping(slot)
            evidence_class = str(submission_slot.get("evidence_class", ""))
            indexed[(evidence_id, evidence_class)] = submission_slot
    return indexed


def _item_verified(gate: Mapping[str, Any], evidence_id: str) -> bool:
    for item in gate.get("verification_items", []):
        verification_item = _mapping(item)
        if verification_item.get("evidence_id") == evidence_id:
            return verification_item.get("all_slots_verified") is True
    return False


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


def _is_default_gate_path(path: Path) -> bool:
    return path.resolve(strict=False) == DEFAULT_GATE.resolve(strict=False)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse Forge operator evidence verification gate validation arguments."""

    parser = argparse.ArgumentParser(description="Validate Forge live-runtime operator evidence verification gate.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--gate", default=str(DEFAULT_GATE))
    parser.add_argument("--submission-packet", default=str(DEFAULT_SUBMISSION_PACKET))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for Forge operator evidence verification gate validation."""

    args = parse_args(argv)
    validation, produced_gate = validate_forge_live_runtime_operator_evidence_verification_gate(
        schema_path=Path(args.schema),
        gate_path=Path(args.gate),
        submission_packet_path=Path(args.submission_packet),
    )
    write_forge_live_runtime_operator_evidence_verification_gate_validation(validation, Path(args.output))
    if args.json:
        payload = validation.as_dict()
        payload["produced_gate"] = produced_gate
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif validation.ok:
        print("FORGE LIVE-RUNTIME OPERATOR EVIDENCE VERIFICATION GATE VALID")
    else:
        print(f"FORGE LIVE-RUNTIME OPERATOR EVIDENCE VERIFICATION GATE INVALID errors={list(validation.errors)}")
    return 0 if validation.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
