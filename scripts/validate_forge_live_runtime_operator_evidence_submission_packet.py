#!/usr/bin/env python3
"""Validate the Forge live-runtime operator evidence submission packet.

Purpose: prove operator-supplied Forge live-runtime evidence is represented as
redacted references, not raw secrets or runtime authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: gateway.forge_state_write_admission, operator evidence submission
schema, operator evidence submission fixture, and shared schema validation.
Invariants:
  - Submitted evidence slots contain references only.
  - Secret values are never accepted.
  - A submitted packet does not grant runtime, production, commit, external
    effect, or terminal closure authority.
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
    FORGE_LIVE_RUNTIME_OPERATOR_EVIDENCE_SUBMISSION_PACKET_ID,
    FORGE_LIVE_RUNTIME_OPERATOR_EVIDENCE_SUBMISSION_PACKET_SCHEMA_REF,
    FORGE_WRITE_SPINE_BRIDGE_ID,
    LIVE_RUNTIME_EVIDENCE_COLLECTION_TARGETS,
    LIVE_RUNTIME_OPERATOR_EVIDENCE_SUBMISSION_CONTROLS,
    LIVE_RUNTIME_OPERATOR_REQUIRED_EVIDENCE_CLASSES,
    REQUIRED_LIVE_RUNTIME_EVIDENCE_IDS,
    build_foundation_forge_live_runtime_operator_evidence_request,
    build_foundation_forge_live_runtime_operator_evidence_submission_packet,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "forge_live_runtime_operator_evidence_submission_packet.schema.json"
DEFAULT_PACKET = REPO_ROOT / "examples" / "forge_live_runtime_operator_evidence_submission_packet.foundation.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "forge_live_runtime_operator_evidence_submission_packet_validation.json"
REQUIRED_TOTAL_REF_COUNT = len(REQUIRED_LIVE_RUNTIME_EVIDENCE_IDS) * len(LIVE_RUNTIME_OPERATOR_REQUIRED_EVIDENCE_CLASSES)


@dataclass(frozen=True, slots=True)
class ForgeLiveRuntimeOperatorEvidenceSubmissionPacketValidation:
    """Validation report for the Forge operator evidence submission packet."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    packet_path: str
    packet_id: str
    submission_status: str
    submission_item_count: int
    submitted_ref_count: int
    required_ref_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_forge_live_runtime_operator_evidence_submission_packet(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    packet_path: Path = DEFAULT_PACKET,
) -> tuple[ForgeLiveRuntimeOperatorEvidenceSubmissionPacketValidation, dict[str, Any]]:
    """Validate submission packet schema, semantics, and default fixture parity."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "Forge operator evidence submission schema", errors)
    packet = _load_json_object(packet_path, "Forge operator evidence submission packet", errors)
    produced_packet = build_foundation_forge_live_runtime_operator_evidence_submission_packet()

    if schema and packet:
        errors.extend(f"{_path_label(packet_path)}: {error}" for error in _validate_schema_instance(schema, packet))
        _validate_submission_packet_semantics(packet, errors, _path_label(packet_path))
    if schema and produced_packet:
        errors.extend(
            f"produced operator evidence submission packet: {error}"
            for error in _validate_schema_instance(schema, produced_packet)
        )
        _validate_submission_packet_semantics(
            produced_packet,
            errors,
            "produced operator evidence submission packet",
        )
    if _is_default_packet_path(packet_path) and packet and produced_packet and packet != produced_packet:
        errors.append("fixture does not match deterministic Forge live-runtime operator evidence submission packet")

    observed = packet or produced_packet
    submission_items = observed.get("submission_items", ())
    validation = ForgeLiveRuntimeOperatorEvidenceSubmissionPacketValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        packet_path=_path_label(packet_path),
        packet_id=str(observed.get("packet_id", "")),
        submission_status=str(observed.get("submission_status", "")),
        submission_item_count=len(submission_items) if isinstance(submission_items, list) else 0,
        submitted_ref_count=int(observed.get("submitted_ref_count", 0))
        if not isinstance(observed.get("submitted_ref_count"), bool)
        else 0,
        required_ref_count=int(observed.get("required_ref_count", 0))
        if not isinstance(observed.get("required_ref_count"), bool)
        else 0,
    )
    return validation, produced_packet


def write_forge_live_runtime_operator_evidence_submission_packet_validation(
    validation: ForgeLiveRuntimeOperatorEvidenceSubmissionPacketValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic operator evidence submission validation report."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_submission_packet_semantics(packet: Mapping[str, Any], errors: list[str], label: str) -> None:
    if packet.get("packet_id") != FORGE_LIVE_RUNTIME_OPERATOR_EVIDENCE_SUBMISSION_PACKET_ID:
        errors.append(f"{label}: packet_id mismatch")
    if packet.get("schema_ref") != FORGE_LIVE_RUNTIME_OPERATOR_EVIDENCE_SUBMISSION_PACKET_SCHEMA_REF:
        errors.append(f"{label}: schema_ref mismatch")
    if packet.get("bridge_ref") != FORGE_WRITE_SPINE_BRIDGE_ID:
        errors.append(f"{label}: bridge_ref mismatch")
    if packet.get("submission_mode") != "operator_live_evidence_ref_intake":
        errors.append(f"{label}: submission_mode drift")
    if packet.get("solver_outcome") != "AwaitingEvidence":
        errors.append(f"{label}: solver_outcome must remain AwaitingEvidence")
    if packet.get("proof_state") != "Unknown":
        errors.append(f"{label}: proof_state must remain Unknown")
    for field_name in (
        "secret_values_present",
        "runtime_authority_effect",
        "acceptance_allowed",
    ):
        if packet.get(field_name) is not False:
            errors.append(f"{label}: {field_name} must remain false")
    operator_request = build_foundation_forge_live_runtime_operator_evidence_request()
    if packet.get("source_operator_evidence_request_hash") != operator_request["request_hash"]:
        errors.append(f"{label}: source_operator_evidence_request_hash mismatch")
    _validate_submission_items(packet, errors, label)
    _validate_submission_summary(packet, errors, label)
    _validate_authority(packet, errors, label)
    if tuple(packet.get("required_controls", ())) != LIVE_RUNTIME_OPERATOR_EVIDENCE_SUBMISSION_CONTROLS:
        errors.append(f"{label}: required_controls drift")
    if packet.get("next_allowed_action") != "submit_redacted_operator_evidence_refs_for_validation":
        errors.append(f"{label}: next_allowed_action drift")


def _validate_submission_items(packet: Mapping[str, Any], errors: list[str], label: str) -> None:
    submission_items = packet.get("submission_items")
    if not isinstance(submission_items, list):
        errors.append(f"{label}: submission_items must be a list")
        return
    evidence_ids = tuple(str(item.get("evidence_id", "")) for item in submission_items if isinstance(item, Mapping))
    if evidence_ids != REQUIRED_LIVE_RUNTIME_EVIDENCE_IDS:
        errors.append(f"{label}: submission_items order drift")
    for item in submission_items:
        submission_item = _mapping(item)
        evidence_id = str(submission_item.get("evidence_id", ""))
        if submission_item.get("target_evidence_ref") != LIVE_RUNTIME_EVIDENCE_COLLECTION_TARGETS.get(evidence_id):
            errors.append(f"{label}: {evidence_id}.target_evidence_ref mismatch")
        expected_request_ref = f"request://forge/live-runtime/operator-evidence/{evidence_id.replace('_', '-')}"
        if submission_item.get("requested_input_ref") != expected_request_ref:
            errors.append(f"{label}: {evidence_id}.requested_input_ref mismatch")
        submitted_refs = submission_item.get("submitted_refs")
        if not isinstance(submitted_refs, list):
            errors.append(f"{label}: {evidence_id}.submitted_refs must be a list")
            continue
        if tuple(str(ref.get("evidence_class", "")) for ref in submitted_refs if isinstance(ref, Mapping)) != (
            LIVE_RUNTIME_OPERATOR_REQUIRED_EVIDENCE_CLASSES
        ):
            errors.append(f"{label}: {evidence_id}.submitted_refs class order drift")
        slot_submitted_count = 0
        for ref in submitted_refs:
            slot = _mapping(ref)
            evidence_class = str(slot.get("evidence_class", ""))
            if slot.get("secret_value_present") is not False:
                errors.append(f"{label}: {evidence_id}.{evidence_class}.secret_value_present must remain false")
            submitted = slot.get("submitted")
            evidence_ref = str(slot.get("evidence_ref", ""))
            ref_hash = str(slot.get("ref_hash", ""))
            validation_status = str(slot.get("validation_status", ""))
            if submitted is True:
                slot_submitted_count += 1
                if not evidence_ref:
                    errors.append(f"{label}: {evidence_id}.{evidence_class}.evidence_ref required when submitted")
                if not ref_hash.startswith("sha256:") or len(ref_hash) != 71:
                    errors.append(f"{label}: {evidence_id}.{evidence_class}.ref_hash must be sha256 ref")
                if validation_status != "submitted_unverified":
                    errors.append(f"{label}: {evidence_id}.{evidence_class}.validation_status must be submitted_unverified")
            else:
                if evidence_ref or ref_hash:
                    errors.append(f"{label}: {evidence_id}.{evidence_class}.missing slot must not carry refs")
                if validation_status != "missing":
                    errors.append(f"{label}: {evidence_id}.{evidence_class}.validation_status must be missing")
        if submission_item.get("submitted_ref_count") != slot_submitted_count:
            errors.append(f"{label}: {evidence_id}.submitted_ref_count mismatch")
        if submission_item.get("required_ref_count") != len(LIVE_RUNTIME_OPERATOR_REQUIRED_EVIDENCE_CLASSES):
            errors.append(f"{label}: {evidence_id}.required_ref_count drift")
        all_present = slot_submitted_count == len(LIVE_RUNTIME_OPERATOR_REQUIRED_EVIDENCE_CLASSES)
        if submission_item.get("all_required_refs_present") is not all_present:
            errors.append(f"{label}: {evidence_id}.all_required_refs_present mismatch")
        expected_status = "submitted_for_validation" if all_present else "blocked_missing_required_refs"
        if submission_item.get("submission_status") != expected_status:
            errors.append(f"{label}: {evidence_id}.submission_status must be {expected_status}")
        if submission_item.get("secret_values_present") is not False:
            errors.append(f"{label}: {evidence_id}.secret_values_present must remain false")


def _validate_submission_summary(packet: Mapping[str, Any], errors: list[str], label: str) -> None:
    submission_items = packet.get("submission_items")
    if not isinstance(submission_items, list):
        return
    submitted_ref_count = 0
    blocked_reasons = []
    for item in submission_items:
        submission_item = _mapping(item)
        submitted_ref_count += int(submission_item.get("submitted_ref_count", 0))
        if submission_item.get("submission_status") != "submitted_for_validation":
            blocked_reasons.append(str(submission_item.get("blocker_reason", "")))
    all_present = submitted_ref_count == REQUIRED_TOTAL_REF_COUNT
    expected_status = "submitted_for_validation" if all_present else "blocked_awaiting_operator_live_evidence_refs"
    if packet.get("submission_status") != expected_status:
        errors.append(f"{label}: submission_status must be {expected_status}")
    if packet.get("submission_item_count") != len(REQUIRED_LIVE_RUNTIME_EVIDENCE_IDS):
        errors.append(f"{label}: submission_item_count drift")
    if packet.get("submitted_ref_count") != submitted_ref_count:
        errors.append(f"{label}: submitted_ref_count mismatch")
    if packet.get("required_ref_count") != REQUIRED_TOTAL_REF_COUNT:
        errors.append(f"{label}: required_ref_count drift")
    if packet.get("all_required_refs_present") is not all_present:
        errors.append(f"{label}: all_required_refs_present mismatch")
    if list(packet.get("blocked_reasons", ())) != blocked_reasons:
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
    """Parse Forge operator evidence submission validation arguments."""

    parser = argparse.ArgumentParser(description="Validate Forge live-runtime operator evidence submission packet.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--packet", default=str(DEFAULT_PACKET))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for Forge operator evidence submission validation."""

    args = parse_args(argv)
    validation, produced_packet = validate_forge_live_runtime_operator_evidence_submission_packet(
        schema_path=Path(args.schema),
        packet_path=Path(args.packet),
    )
    write_forge_live_runtime_operator_evidence_submission_packet_validation(validation, Path(args.output))
    if args.json:
        payload = validation.as_dict()
        payload["produced_packet"] = produced_packet
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif validation.ok:
        print("FORGE LIVE-RUNTIME OPERATOR EVIDENCE SUBMISSION PACKET VALID")
    else:
        print(f"FORGE LIVE-RUNTIME OPERATOR EVIDENCE SUBMISSION PACKET INVALID errors={list(validation.errors)}")
    return 0 if validation.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
