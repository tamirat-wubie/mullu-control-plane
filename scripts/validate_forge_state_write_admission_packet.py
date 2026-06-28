#!/usr/bin/env python3
"""Validate the Forge state-write admission packet.

Purpose: prove the Forge bridge has a repository-local non-mutating admission
packet before any runtime state-write commit path exists.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: gateway.forge_state_write_admission, admission packet schema,
the admission packet fixture, and shared schema validation.
Invariants:
  - Admission is reference-only and cannot mutate live state.
  - Commit and production authority remain false.
  - The checked-in packet matches the deterministic adapter projection.
  - Stage order, Phi_gov certificate fields, and service boundary do not drift.
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
    BASE_REQUIRED_CONTROLS,
    EXPECTED_CERTIFICATE_FIELDS,
    EXPECTED_STAGE_IDS,
    FORGE_STATE_WRITE_ADMISSION_ADAPTER_ID,
    FORGE_STATE_WRITE_ADMISSION_PACKET_SCHEMA_REF,
    FORGE_WRITE_SPINE_BRIDGE_ID,
    build_forge_state_write_admission_packet,
    build_foundation_forge_state_write_request,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "forge_state_write_admission_packet.schema.json"
DEFAULT_PACKET = REPO_ROOT / "examples" / "forge_state_write_admission_packet.foundation.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "forge_state_write_admission_packet_validation.json"


@dataclass(frozen=True, slots=True)
class ForgeStateWriteAdmissionPacketValidation:
    """Validation report for the Forge state-write admission packet."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    packet_path: str
    adapter_id: str
    bridge_ref: str
    admission_decision: str
    blocked_reason_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_forge_state_write_admission_packet(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    packet_path: Path = DEFAULT_PACKET,
) -> tuple[ForgeStateWriteAdmissionPacketValidation, dict[str, Any]]:
    """Validate checked-in packet shape and deterministic adapter output."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "Forge admission packet schema", errors)
    packet = _load_json_object(packet_path, "Forge admission packet", errors)
    produced_packet = build_forge_state_write_admission_packet(build_foundation_forge_state_write_request())

    if schema and packet:
        errors.extend(f"{_path_label(packet_path)}: {error}" for error in _validate_schema_instance(schema, packet))
        _validate_packet_semantics(packet, errors, _path_label(packet_path))
    if schema and produced_packet:
        errors.extend(
            f"produced admission packet: {error}"
            for error in _validate_schema_instance(schema, produced_packet)
        )
        _validate_packet_semantics(produced_packet, errors, "produced admission packet")
    if packet and produced_packet:
        _validate_fixture_matches_produced_packet(packet, produced_packet, errors)

    observed_receipt = _mapping((produced_packet or packet).get("receipt"))
    validation = ForgeStateWriteAdmissionPacketValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        packet_path=_path_label(packet_path),
        adapter_id=str((produced_packet or packet).get("adapter_id", "")),
        bridge_ref=str((produced_packet or packet).get("bridge_ref", "")),
        admission_decision=str(observed_receipt.get("admission_decision", "")),
        blocked_reason_count=len(observed_receipt.get("blocked_reasons", ()))
        if isinstance(observed_receipt.get("blocked_reasons"), list)
        else 0,
    )
    return validation, produced_packet


def write_forge_state_write_admission_packet_validation(
    validation: ForgeStateWriteAdmissionPacketValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic Forge admission validation report."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_packet_semantics(packet: Mapping[str, Any], errors: list[str], label: str) -> None:
    if packet.get("packet_schema_ref") != FORGE_STATE_WRITE_ADMISSION_PACKET_SCHEMA_REF:
        errors.append(f"{label}: packet_schema_ref mismatch")
    if packet.get("adapter_id") != FORGE_STATE_WRITE_ADMISSION_ADAPTER_ID:
        errors.append(f"{label}: adapter_id mismatch")
    if packet.get("bridge_ref") != FORGE_WRITE_SPINE_BRIDGE_ID:
        errors.append(f"{label}: bridge_ref mismatch")
    request = _mapping(packet.get("request"))
    receipt = _mapping(packet.get("receipt"))
    invariants = _mapping(packet.get("invariants"))
    _validate_request_semantics(request, errors, label)
    _validate_receipt_semantics(receipt, errors, label)
    _validate_invariants(invariants, errors, label)


def _validate_request_semantics(request: Mapping[str, Any], errors: list[str], label: str) -> None:
    if request.get("bridge_ref") != FORGE_WRITE_SPINE_BRIDGE_ID:
        errors.append(f"{label}: request.bridge_ref mismatch")
    if request.get("requested_environment") != "dev_offline":
        errors.append(f"{label}: foundation request must remain dev_offline")
    if request.get("decision_status") != "conditional_accept":
        errors.append(f"{label}: request decision must remain conditional_accept")
    if request.get("mutation_performed") is not False:
        errors.append(f"{label}: request mutation_performed must be false")
    stages = request.get("stages")
    if not isinstance(stages, list):
        errors.append(f"{label}: request.stages must be a list")
    else:
        stage_ids = tuple(str(stage.get("stage_id", "")) for stage in stages if isinstance(stage, Mapping))
        orders = tuple(int(stage.get("order", 0) or 0) for stage in stages if isinstance(stage, Mapping))
        if stage_ids != EXPECTED_STAGE_IDS:
            errors.append(f"{label}: stage order drift")
        if orders != tuple(range(1, len(EXPECTED_STAGE_IDS) + 1)):
            errors.append(f"{label}: stage order fields drift")
        if any(_mapping(stage).get("satisfied") is not True for stage in stages):
            errors.append(f"{label}: all stages must be satisfied")
    certificate = _mapping(request.get("certificate"))
    if tuple(certificate.get("required_fields", ())) != EXPECTED_CERTIFICATE_FIELDS:
        errors.append(f"{label}: certificate required field order drift")
    if certificate.get("development_only") is not True:
        errors.append(f"{label}: certificate must remain development_only")
    service = _mapping(request.get("service_boundary"))
    if service.get("transport_confidentiality") is not False:
        errors.append(f"{label}: transport_confidentiality must remain false until production transport exists")
    if service.get("production_authorized") is not False:
        errors.append(f"{label}: service production_authorized must remain false")


def _validate_receipt_semantics(receipt: Mapping[str, Any], errors: list[str], label: str) -> None:
    if receipt.get("status") != "reference_prepare_admitted":
        errors.append(f"{label}: receipt.status must be reference_prepare_admitted")
    if receipt.get("admission_decision") != "allow_prepare_model":
        errors.append(f"{label}: admission_decision must be allow_prepare_model")
    for field_name in (
        "external_effects_allowed",
        "state_write_runtime_registered",
        "production_authorized",
        "commit_allowed",
        "live_mutation_allowed",
    ):
        if receipt.get(field_name) is not False:
            errors.append(f"{label}: receipt.{field_name} must be false")
    if receipt.get("prepared_transition_model_allowed") is not True:
        errors.append(f"{label}: prepared_transition_model_allowed must be true")
    if receipt.get("terminal_closure_required") is not True:
        errors.append(f"{label}: terminal_closure_required must be true")
    if receipt.get("blocked_reasons") != []:
        errors.append(f"{label}: foundation packet must not have blocked reasons")
    required_controls = receipt.get("required_controls")
    if not isinstance(required_controls, list) or tuple(required_controls) != BASE_REQUIRED_CONTROLS:
        errors.append(f"{label}: required_controls drift")


def _validate_invariants(invariants: Mapping[str, Any], errors: list[str], label: str) -> None:
    expected = {
        "reference_only": True,
        "mutation_performed": False,
        "live_mutation_allowed": False,
        "commit_allowed": False,
        "production_authorized": False,
        "state_write_runtime_registered": False,
        "external_effects_allowed": False,
        "terminal_closure_required": True,
    }
    for field_name, expected_value in expected.items():
        if invariants.get(field_name) is not expected_value:
            errors.append(f"{label}: invariant {field_name} must be {str(expected_value).lower()}")


def _validate_fixture_matches_produced_packet(
    fixture: Mapping[str, Any],
    produced_packet: Mapping[str, Any],
    errors: list[str],
) -> None:
    if fixture != produced_packet:
        errors.append("fixture does not match deterministic Forge state-write admission packet")


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
    """Parse Forge state-write admission packet validation arguments."""

    parser = argparse.ArgumentParser(description="Validate Forge state-write admission packet.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--packet", default=str(DEFAULT_PACKET))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for Forge state-write admission packet validation."""

    args = parse_args(argv)
    validation, produced_packet = validate_forge_state_write_admission_packet(
        schema_path=Path(args.schema),
        packet_path=Path(args.packet),
    )
    write_forge_state_write_admission_packet_validation(validation, Path(args.output))
    if args.json:
        payload = validation.as_dict()
        payload["produced_packet"] = produced_packet
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif validation.ok:
        print("FORGE STATE-WRITE ADMISSION PACKET VALID")
    else:
        print(f"FORGE STATE-WRITE ADMISSION PACKET INVALID errors={list(validation.errors)}")
    return 0 if validation.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
