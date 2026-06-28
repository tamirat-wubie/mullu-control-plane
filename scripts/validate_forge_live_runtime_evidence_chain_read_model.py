#!/usr/bin/env python3
"""Validate the Forge live-runtime evidence chain read model.

Purpose: prove the Forge live-runtime evidence chain is projected read-only
without claiming live evidence, population, runtime authority, or terminal
closure.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: gateway.forge_state_write_admission, evidence chain read-model
schema, evidence chain read-model fixture, and shared schema validation.
Invariants:
  - The read model is projection-only.
  - Every stage remains AwaitingEvidence in the Foundation fixture.
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
    FORGE_LIVE_RUNTIME_EVIDENCE_CHAIN_READ_MODEL_ID,
    FORGE_LIVE_RUNTIME_EVIDENCE_CHAIN_READ_MODEL_SCHEMA_REF,
    FORGE_WRITE_SPINE_BRIDGE_ID,
    LIVE_RUNTIME_EVIDENCE_CHAIN_READ_MODEL_CONTROLS,
    build_foundation_forge_live_runtime_evidence_chain_read_model,
    build_foundation_forge_live_runtime_signed_receipt_population_gate,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "forge_live_runtime_evidence_chain_read_model.schema.json"
DEFAULT_READ_MODEL = REPO_ROOT / "examples" / "forge_live_runtime_evidence_chain_read_model.foundation.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "forge_live_runtime_evidence_chain_read_model_validation.json"
EXPECTED_STAGE_IDS = (
    "live_runtime_readiness_gate",
    "live_runtime_evidence_collection_packet",
    "live_runtime_local_evidence_bundle",
    "live_runtime_evidence_acceptance_gate",
    "live_runtime_signed_evidence_receipt",
    "live_runtime_probe_admission_packet",
    "live_runtime_approved_probe_output_packet",
    "live_runtime_post_probe_reconciliation_packet",
    "live_runtime_signed_receipt_population_gate",
)
EXPECTED_CONTINUATION_IDS = (
    "live_runtime_operator_evidence_request",
    "live_runtime_operator_evidence_submission_packet",
    "live_runtime_operator_evidence_verification_gate",
    "live_runtime_operator_evidence_acceptance_handoff_packet",
)


@dataclass(frozen=True, slots=True)
class ForgeLiveRuntimeEvidenceChainReadModelValidation:
    """Validation report for the Forge evidence chain read model."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    read_model_path: str
    read_model_id: str
    read_model_status: str
    stage_count: int
    blocked_stage_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_forge_live_runtime_evidence_chain_read_model(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    read_model_path: Path = DEFAULT_READ_MODEL,
) -> tuple[ForgeLiveRuntimeEvidenceChainReadModelValidation, dict[str, Any]]:
    """Validate read-model schema, semantics, and fixture parity."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "Forge evidence chain read-model schema", errors)
    read_model = _load_json_object(read_model_path, "Forge evidence chain read model", errors)
    produced_read_model = build_foundation_forge_live_runtime_evidence_chain_read_model()

    if schema and read_model:
        errors.extend(
            f"{_path_label(read_model_path)}: {error}"
            for error in _validate_schema_instance(schema, read_model)
        )
        _validate_read_model_semantics(read_model, errors, _path_label(read_model_path))
    if schema and produced_read_model:
        errors.extend(
            f"produced evidence chain read model: {error}"
            for error in _validate_schema_instance(schema, produced_read_model)
        )
        _validate_read_model_semantics(produced_read_model, errors, "produced evidence chain read model")
    if read_model and produced_read_model and read_model != produced_read_model:
        errors.append("fixture does not match deterministic Forge live-runtime evidence chain read model")

    observed = produced_read_model or read_model
    stage_items = observed.get("stage_items", ())
    validation = ForgeLiveRuntimeEvidenceChainReadModelValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        read_model_path=_path_label(read_model_path),
        read_model_id=str(observed.get("read_model_id", "")),
        read_model_status=str(observed.get("read_model_status", "")),
        stage_count=len(stage_items) if isinstance(stage_items, list) else 0,
        blocked_stage_count=int(observed.get("blocked_stage_count", 0))
        if not isinstance(observed.get("blocked_stage_count"), bool)
        else 0,
    )
    return validation, produced_read_model


def write_forge_live_runtime_evidence_chain_read_model_validation(
    validation: ForgeLiveRuntimeEvidenceChainReadModelValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic evidence chain read-model validation report."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_read_model_semantics(read_model: Mapping[str, Any], errors: list[str], label: str) -> None:
    if read_model.get("read_model_id") != FORGE_LIVE_RUNTIME_EVIDENCE_CHAIN_READ_MODEL_ID:
        errors.append(f"{label}: read_model_id mismatch")
    if read_model.get("schema_ref") != FORGE_LIVE_RUNTIME_EVIDENCE_CHAIN_READ_MODEL_SCHEMA_REF:
        errors.append(f"{label}: schema_ref mismatch")
    if read_model.get("bridge_ref") != FORGE_WRITE_SPINE_BRIDGE_ID:
        errors.append(f"{label}: bridge_ref mismatch")
    if read_model.get("read_model_mode") != "foundation_live_runtime_evidence_chain_projection":
        errors.append(f"{label}: read_model_mode must remain foundation_live_runtime_evidence_chain_projection")
    if read_model.get("read_model_status") != "blocked_awaiting_live_runtime_evidence":
        errors.append(f"{label}: read_model_status must remain blocked_awaiting_live_runtime_evidence")
    if read_model.get("solver_outcome") != "AwaitingEvidence":
        errors.append(f"{label}: solver_outcome must remain AwaitingEvidence")
    if read_model.get("stage_count") != len(EXPECTED_STAGE_IDS):
        errors.append(f"{label}: stage_count drift")
    if read_model.get("blocked_stage_count") != len(EXPECTED_STAGE_IDS):
        errors.append(f"{label}: blocked_stage_count drift")
    if read_model.get("continuation_count") != len(EXPECTED_CONTINUATION_IDS):
        errors.append(f"{label}: continuation_count drift")
    if read_model.get("live_evidence_present") is not False:
        errors.append(f"{label}: live_evidence_present must remain false")
    if read_model.get("runtime_authority_effect") is not False:
        errors.append(f"{label}: runtime_authority_effect must remain false")
    population_gate = build_foundation_forge_live_runtime_signed_receipt_population_gate()
    if read_model.get("source_signed_receipt_population_gate_hash") != population_gate["gate_hash"]:
        errors.append(f"{label}: source_signed_receipt_population_gate_hash mismatch")
    _validate_stage_items(read_model, errors, label)
    _validate_continuation_items(read_model, errors, label)
    _validate_authority(read_model, errors, label)
    if tuple(read_model.get("required_controls", ())) != LIVE_RUNTIME_EVIDENCE_CHAIN_READ_MODEL_CONTROLS:
        errors.append(f"{label}: required_controls drift")
    if read_model.get("next_allowed_action") != "inspect_read_model_or_collect_live_evidence_after_operator_approval":
        errors.append(f"{label}: next_allowed_action drift")


def _validate_stage_items(read_model: Mapping[str, Any], errors: list[str], label: str) -> None:
    stage_items = read_model.get("stage_items")
    if not isinstance(stage_items, list):
        errors.append(f"{label}: stage_items must be a list")
        return
    observed_stage_ids = tuple(str(item.get("stage_id", "")) for item in stage_items if isinstance(item, Mapping))
    if observed_stage_ids != EXPECTED_STAGE_IDS:
        errors.append(f"{label}: stage_items order drift")
    for item in stage_items:
        stage_item = _mapping(item)
        stage_id = str(stage_item.get("stage_id", ""))
        if not str(stage_item.get("artifact_ref", "")).startswith("examples/forge_live_runtime_"):
            errors.append(f"{label}: {stage_id}.artifact_ref must reference Forge live-runtime examples")
        if stage_item.get("solver_outcome") != "AwaitingEvidence":
            errors.append(f"{label}: {stage_id}.solver_outcome must remain AwaitingEvidence")
        if stage_item.get("authority_effect") is not False:
            errors.append(f"{label}: {stage_id}.authority_effect must remain false")
        if not str(stage_item.get("artifact_hash", "")).strip():
            errors.append(f"{label}: {stage_id}.artifact_hash required")


def _validate_continuation_items(read_model: Mapping[str, Any], errors: list[str], label: str) -> None:
    continuation_items = read_model.get("continuation_items")
    if not isinstance(continuation_items, list):
        errors.append(f"{label}: continuation_items must be a list")
        return
    observed_ids = tuple(str(item.get("continuation_id", "")) for item in continuation_items if isinstance(item, Mapping))
    if observed_ids != EXPECTED_CONTINUATION_IDS:
        errors.append(f"{label}: continuation_items order drift")
    for item in continuation_items:
        continuation_item = _mapping(item)
        continuation_id = str(continuation_item.get("continuation_id", ""))
        if not str(continuation_item.get("artifact_ref", "")).startswith("examples/forge_live_runtime_"):
            errors.append(f"{label}: {continuation_id}.artifact_ref must reference Forge live-runtime examples")
        if continuation_item.get("solver_outcome") != "AwaitingEvidence":
            errors.append(f"{label}: {continuation_id}.solver_outcome must remain AwaitingEvidence")
        if continuation_item.get("hash_included") is not False:
            errors.append(f"{label}: {continuation_id}.hash_included must remain false")
        if continuation_item.get("hash_exclusion_reason") != "downstream_artifact_depends_on_read_model_hash":
            errors.append(f"{label}: {continuation_id}.hash_exclusion_reason drift")
        if continuation_item.get("authority_effect") is not False:
            errors.append(f"{label}: {continuation_id}.authority_effect must remain false")


def _validate_authority(read_model: Mapping[str, Any], errors: list[str], label: str) -> None:
    disallowed_authority = _mapping(read_model.get("disallowed_authority"))
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
    """Parse Forge evidence chain read-model validation arguments."""

    parser = argparse.ArgumentParser(description="Validate Forge live-runtime evidence chain read model.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--read-model", default=str(DEFAULT_READ_MODEL))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for Forge evidence chain read-model validation."""

    args = parse_args(argv)
    validation, produced_read_model = validate_forge_live_runtime_evidence_chain_read_model(
        schema_path=Path(args.schema),
        read_model_path=Path(args.read_model),
    )
    write_forge_live_runtime_evidence_chain_read_model_validation(validation, Path(args.output))
    if args.json:
        payload = validation.as_dict()
        payload["produced_read_model"] = produced_read_model
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif validation.ok:
        print("FORGE LIVE-RUNTIME EVIDENCE CHAIN READ MODEL VALID")
    else:
        print(f"FORGE LIVE-RUNTIME EVIDENCE CHAIN READ MODEL INVALID errors={list(validation.errors)}")
    return 0 if validation.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
