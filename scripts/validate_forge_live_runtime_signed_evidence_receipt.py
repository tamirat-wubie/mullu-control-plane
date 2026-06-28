#!/usr/bin/env python3
"""Validate the Forge live-runtime signed evidence receipt shape.

Purpose: prove the Foundation Mode signed evidence receipt fixture defines the
future live evidence shape without claiming signed evidence or runtime
authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: gateway.forge_state_write_admission, signed evidence receipt
schema, signed evidence receipt fixture, and shared schema validation.
Invariants:
  - Signed live evidence is not present in the Foundation fixture.
  - Verification status remains not_verified until receipt refs are populated.
  - Runtime, production, commit, external effect, and terminal closure
    authority remain false.
  - The checked-in receipt matches the deterministic builder output.
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
    FORGE_LIVE_RUNTIME_SIGNED_EVIDENCE_RECEIPT_ID,
    FORGE_LIVE_RUNTIME_SIGNED_EVIDENCE_RECEIPT_SCHEMA_REF,
    FORGE_WRITE_SPINE_BRIDGE_ID,
    LIVE_RUNTIME_EVIDENCE_COLLECTION_TARGETS,
    LIVE_RUNTIME_SIGNED_EVIDENCE_RECEIPT_CONTROLS,
    REQUIRED_LIVE_RUNTIME_EVIDENCE_IDS,
    build_foundation_forge_live_runtime_evidence_acceptance_gate,
    build_foundation_forge_live_runtime_signed_evidence_receipt,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "forge_live_runtime_signed_evidence_receipt.schema.json"
DEFAULT_RECEIPT = REPO_ROOT / "examples" / "forge_live_runtime_signed_evidence_receipt.foundation.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "forge_live_runtime_signed_evidence_receipt_validation.json"


@dataclass(frozen=True, slots=True)
class ForgeLiveRuntimeSignedEvidenceReceiptValidation:
    """Validation report for the Forge live-runtime signed evidence receipt."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    receipt_path: str
    receipt_id: str
    receipt_status: str
    evidence_receipt_count: int
    blocked_reason_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_forge_live_runtime_signed_evidence_receipt(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    receipt_path: Path = DEFAULT_RECEIPT,
) -> tuple[ForgeLiveRuntimeSignedEvidenceReceiptValidation, dict[str, Any]]:
    """Validate signed evidence receipt schema, semantics, and fixture parity."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "Forge live-runtime signed evidence schema", errors)
    receipt = _load_json_object(receipt_path, "Forge live-runtime signed evidence receipt", errors)
    produced_receipt = build_foundation_forge_live_runtime_signed_evidence_receipt()

    if schema and receipt:
        errors.extend(f"{_path_label(receipt_path)}: {error}" for error in _validate_schema_instance(schema, receipt))
        _validate_receipt_semantics(receipt, errors, _path_label(receipt_path))
    if schema and produced_receipt:
        errors.extend(
            f"produced signed evidence receipt: {error}"
            for error in _validate_schema_instance(schema, produced_receipt)
        )
        _validate_receipt_semantics(produced_receipt, errors, "produced signed evidence receipt")
    if receipt and produced_receipt and receipt != produced_receipt:
        errors.append("fixture does not match deterministic Forge live-runtime signed evidence receipt")

    observed_receipt = produced_receipt or receipt
    evidence_receipts = observed_receipt.get("evidence_receipts", ())
    blocked_reasons = observed_receipt.get("blocked_reasons", ())
    validation = ForgeLiveRuntimeSignedEvidenceReceiptValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        receipt_path=_path_label(receipt_path),
        receipt_id=str(observed_receipt.get("receipt_id", "")),
        receipt_status=str(observed_receipt.get("receipt_status", "")),
        evidence_receipt_count=len(evidence_receipts) if isinstance(evidence_receipts, list) else 0,
        blocked_reason_count=len(blocked_reasons) if isinstance(blocked_reasons, list) else 0,
    )
    return validation, produced_receipt


def write_forge_live_runtime_signed_evidence_receipt_validation(
    validation: ForgeLiveRuntimeSignedEvidenceReceiptValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic signed evidence receipt validation report."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_receipt_semantics(receipt: Mapping[str, Any], errors: list[str], label: str) -> None:
    if receipt.get("receipt_id") != FORGE_LIVE_RUNTIME_SIGNED_EVIDENCE_RECEIPT_ID:
        errors.append(f"{label}: receipt_id mismatch")
    if receipt.get("schema_ref") != FORGE_LIVE_RUNTIME_SIGNED_EVIDENCE_RECEIPT_SCHEMA_REF:
        errors.append(f"{label}: schema_ref mismatch")
    if receipt.get("bridge_ref") != FORGE_WRITE_SPINE_BRIDGE_ID:
        errors.append(f"{label}: bridge_ref mismatch")
    if receipt.get("receipt_mode") != "signed_live_evidence_shape":
        errors.append(f"{label}: receipt_mode must remain signed_live_evidence_shape")
    if receipt.get("receipt_status") != "awaiting_signed_live_evidence":
        errors.append(f"{label}: receipt_status must remain awaiting_signed_live_evidence")
    if receipt.get("solver_outcome") != "AwaitingEvidence":
        errors.append(f"{label}: solver_outcome must remain AwaitingEvidence")
    acceptance_gate = build_foundation_forge_live_runtime_evidence_acceptance_gate()
    if receipt.get("source_acceptance_gate_hash") != acceptance_gate["gate_hash"]:
        errors.append(f"{label}: source_acceptance_gate_hash mismatch")
    _validate_evidence_receipts(receipt, errors, label)
    _validate_authority(receipt, errors, label)
    if tuple(receipt.get("required_controls", ())) != LIVE_RUNTIME_SIGNED_EVIDENCE_RECEIPT_CONTROLS:
        errors.append(f"{label}: required_controls drift")
    if receipt.get("next_allowed_action") != "populate_signed_live_receipt_refs_after_operator_approved_probe":
        errors.append(f"{label}: next_allowed_action drift")


def _validate_evidence_receipts(receipt: Mapping[str, Any], errors: list[str], label: str) -> None:
    evidence_receipts = receipt.get("evidence_receipts")
    blocked_reasons = receipt.get("blocked_reasons")
    if not isinstance(evidence_receipts, list):
        errors.append(f"{label}: evidence_receipts must be a list")
        return
    evidence_ids = tuple(str(item.get("evidence_id", "")) for item in evidence_receipts if isinstance(item, Mapping))
    if evidence_ids != REQUIRED_LIVE_RUNTIME_EVIDENCE_IDS:
        errors.append(f"{label}: evidence_receipts order drift")
    expected_blockers = tuple(
        f"{evidence_id}_signed_live_evidence_missing" for evidence_id in REQUIRED_LIVE_RUNTIME_EVIDENCE_IDS
    )
    if tuple(blocked_reasons or ()) != expected_blockers:
        errors.append(f"{label}: blocked_reasons drift")
    for item in evidence_receipts:
        evidence = _mapping(item)
        evidence_id = str(evidence.get("evidence_id", ""))
        if evidence.get("required_live_evidence_ref") != LIVE_RUNTIME_EVIDENCE_COLLECTION_TARGETS.get(evidence_id):
            errors.append(f"{label}: {evidence_id}.required_live_evidence_ref mismatch")
        if evidence.get("acceptance_blocker_reason") != f"{evidence_id}_signed_live_evidence_missing":
            errors.append(f"{label}: {evidence_id}.acceptance_blocker_reason mismatch")
        if evidence.get("signed_live_receipt_status") != "not_present":
            errors.append(f"{label}: {evidence_id}.signed_live_receipt_status must remain not_present")
        for empty_field in (
            "signed_live_receipt_ref",
            "signed_live_receipt_hash",
            "dependency_or_credential_probe_ref",
            "recovery_or_revocation_ref",
            "signing_key_id",
            "trust_epoch",
            "signature",
        ):
            if evidence.get(empty_field) != "":
                errors.append(f"{label}: {evidence_id}.{empty_field} must remain empty")
        if evidence.get("verification_status") != "not_verified":
            errors.append(f"{label}: {evidence_id}.verification_status must remain not_verified")
        if evidence.get("authority_effect") is not False:
            errors.append(f"{label}: {evidence_id}.authority_effect must remain false")
        if evidence.get("promotion_effect") is not False:
            errors.append(f"{label}: {evidence_id}.promotion_effect must remain false")


def _validate_authority(receipt: Mapping[str, Any], errors: list[str], label: str) -> None:
    disallowed_authority = _mapping(receipt.get("disallowed_authority"))
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
    """Parse Forge live-runtime signed evidence receipt validation arguments."""

    parser = argparse.ArgumentParser(description="Validate Forge live-runtime signed evidence receipt.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--receipt", default=str(DEFAULT_RECEIPT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for Forge live-runtime signed evidence receipt validation."""

    args = parse_args(argv)
    validation, produced_receipt = validate_forge_live_runtime_signed_evidence_receipt(
        schema_path=Path(args.schema),
        receipt_path=Path(args.receipt),
    )
    write_forge_live_runtime_signed_evidence_receipt_validation(validation, Path(args.output))
    if args.json:
        payload = validation.as_dict()
        payload["produced_receipt"] = produced_receipt
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif validation.ok:
        print("FORGE LIVE-RUNTIME SIGNED EVIDENCE RECEIPT VALID")
    else:
        print(f"FORGE LIVE-RUNTIME SIGNED EVIDENCE RECEIPT INVALID errors={list(validation.errors)}")
    return 0 if validation.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
