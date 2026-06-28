#!/usr/bin/env python3
"""Validate the Forge live-runtime local evidence bundle.

Purpose: prove local Forge live-runtime evidence artifacts remain design and
rehearsal evidence only, without claiming live evidence or runtime authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: gateway.forge_state_write_admission, local evidence bundle
schema, local evidence bundle fixture, and shared schema validation.
Invariants:
  - Local artifacts do not satisfy live evidence.
  - Every blocker remains open until live evidence is separately validated.
  - Runtime, production, commit, external effect, and terminal closure
    authority remain false.
  - The checked-in bundle matches the deterministic builder output.
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
    FORGE_LIVE_RUNTIME_LOCAL_EVIDENCE_BUNDLE_ID,
    FORGE_LIVE_RUNTIME_LOCAL_EVIDENCE_BUNDLE_SCHEMA_REF,
    FORGE_WRITE_SPINE_BRIDGE_ID,
    LIVE_RUNTIME_EVIDENCE_COLLECTION_TARGETS,
    LIVE_RUNTIME_LOCAL_EVIDENCE_ACCEPTANCE_CRITERIA,
    LIVE_RUNTIME_LOCAL_EVIDENCE_ARTIFACT_KINDS,
    LIVE_RUNTIME_LOCAL_EVIDENCE_ARTIFACT_REFS,
    LIVE_RUNTIME_LOCAL_EVIDENCE_CONTROLS,
    REQUIRED_LIVE_RUNTIME_EVIDENCE_IDS,
    build_foundation_forge_live_runtime_evidence_collection_packet,
    build_foundation_forge_live_runtime_local_evidence_bundle,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "forge_live_runtime_local_evidence_bundle.schema.json"
DEFAULT_BUNDLE = REPO_ROOT / "examples" / "forge_live_runtime_local_evidence_bundle.foundation.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "forge_live_runtime_local_evidence_bundle_validation.json"


@dataclass(frozen=True, slots=True)
class ForgeLiveRuntimeLocalEvidenceBundleValidation:
    """Validation report for the Forge live-runtime local evidence bundle."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    bundle_path: str
    bundle_id: str
    bundle_status: str
    local_evidence_count: int
    blocked_reason_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_forge_live_runtime_local_evidence_bundle(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    bundle_path: Path = DEFAULT_BUNDLE,
) -> tuple[ForgeLiveRuntimeLocalEvidenceBundleValidation, dict[str, Any]]:
    """Validate local evidence bundle schema, semantics, and fixture parity."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "Forge live-runtime local evidence schema", errors)
    bundle = _load_json_object(bundle_path, "Forge live-runtime local evidence bundle", errors)
    produced_bundle = build_foundation_forge_live_runtime_local_evidence_bundle()

    if schema and bundle:
        errors.extend(f"{_path_label(bundle_path)}: {error}" for error in _validate_schema_instance(schema, bundle))
        _validate_bundle_semantics(bundle, errors, _path_label(bundle_path))
    if schema and produced_bundle:
        errors.extend(
            f"produced local evidence bundle: {error}"
            for error in _validate_schema_instance(schema, produced_bundle)
        )
        _validate_bundle_semantics(produced_bundle, errors, "produced local evidence bundle")
    if bundle and produced_bundle and bundle != produced_bundle:
        errors.append("fixture does not match deterministic Forge live-runtime local evidence bundle")

    observed_bundle = produced_bundle or bundle
    local_evidence_items = observed_bundle.get("local_evidence_items", ())
    blocked_reasons = observed_bundle.get("blocked_reasons", ())
    validation = ForgeLiveRuntimeLocalEvidenceBundleValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        bundle_path=_path_label(bundle_path),
        bundle_id=str(observed_bundle.get("bundle_id", "")),
        bundle_status=str(observed_bundle.get("bundle_status", "")),
        local_evidence_count=len(local_evidence_items) if isinstance(local_evidence_items, list) else 0,
        blocked_reason_count=len(blocked_reasons) if isinstance(blocked_reasons, list) else 0,
    )
    return validation, produced_bundle


def write_forge_live_runtime_local_evidence_bundle_validation(
    validation: ForgeLiveRuntimeLocalEvidenceBundleValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic local evidence bundle validation report."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_bundle_semantics(bundle: Mapping[str, Any], errors: list[str], label: str) -> None:
    if bundle.get("bundle_id") != FORGE_LIVE_RUNTIME_LOCAL_EVIDENCE_BUNDLE_ID:
        errors.append(f"{label}: bundle_id mismatch")
    if bundle.get("schema_ref") != FORGE_LIVE_RUNTIME_LOCAL_EVIDENCE_BUNDLE_SCHEMA_REF:
        errors.append(f"{label}: schema_ref mismatch")
    if bundle.get("bridge_ref") != FORGE_WRITE_SPINE_BRIDGE_ID:
        errors.append(f"{label}: bridge_ref mismatch")
    if bundle.get("bundle_mode") != "local_design_rehearsal_only":
        errors.append(f"{label}: bundle_mode must remain local_design_rehearsal_only")
    if bundle.get("bundle_status") != "local_design_artifacts_available":
        errors.append(f"{label}: bundle_status must remain local_design_artifacts_available")
    if bundle.get("solver_outcome") != "AwaitingEvidence":
        errors.append(f"{label}: solver_outcome must remain AwaitingEvidence")
    if bundle.get("readiness_status") != "blocked_awaiting_live_evidence":
        errors.append(f"{label}: readiness_status must remain blocked_awaiting_live_evidence")
    collection_packet = build_foundation_forge_live_runtime_evidence_collection_packet()
    if bundle.get("source_collection_packet_hash") != collection_packet["packet_hash"]:
        errors.append(f"{label}: source_collection_packet_hash mismatch")
    _validate_local_evidence_items(bundle, errors, label)
    _validate_authority(bundle, errors, label)
    if tuple(bundle.get("required_controls", ())) != LIVE_RUNTIME_LOCAL_EVIDENCE_CONTROLS:
        errors.append(f"{label}: required_controls drift")
    if bundle.get("next_allowed_action") != "replace_design_artifacts_with_validated_live_evidence_after_approval":
        errors.append(f"{label}: next_allowed_action drift")


def _validate_local_evidence_items(bundle: Mapping[str, Any], errors: list[str], label: str) -> None:
    local_evidence_items = bundle.get("local_evidence_items")
    blocked_reasons = bundle.get("blocked_reasons")
    if not isinstance(local_evidence_items, list):
        errors.append(f"{label}: local_evidence_items must be a list")
        return
    evidence_ids = tuple(str(item.get("evidence_id", "")) for item in local_evidence_items if isinstance(item, Mapping))
    if evidence_ids != REQUIRED_LIVE_RUNTIME_EVIDENCE_IDS:
        errors.append(f"{label}: local_evidence_items order drift")
    expected_blockers = tuple(f"{evidence_id}_missing" for evidence_id in REQUIRED_LIVE_RUNTIME_EVIDENCE_IDS)
    if tuple(blocked_reasons or ()) != expected_blockers:
        errors.append(f"{label}: blocked_reasons drift")
    for item in local_evidence_items:
        evidence = _mapping(item)
        evidence_id = str(evidence.get("evidence_id", ""))
        if evidence.get("source_target_evidence_ref") != LIVE_RUNTIME_EVIDENCE_COLLECTION_TARGETS.get(evidence_id):
            errors.append(f"{label}: {evidence_id}.source_target_evidence_ref mismatch")
        if evidence.get("local_artifact_ref") != LIVE_RUNTIME_LOCAL_EVIDENCE_ARTIFACT_REFS.get(evidence_id):
            errors.append(f"{label}: {evidence_id}.local_artifact_ref mismatch")
        if evidence.get("local_artifact_kind") != LIVE_RUNTIME_LOCAL_EVIDENCE_ARTIFACT_KINDS.get(evidence_id):
            errors.append(f"{label}: {evidence_id}.local_artifact_kind mismatch")
        if evidence.get("local_artifact_status") != "design_artifact_available":
            errors.append(f"{label}: {evidence_id}.local_artifact_status mismatch")
        if evidence.get("live_evidence_status") != "not_collected":
            errors.append(f"{label}: {evidence_id}.live_evidence_status must remain not_collected")
        if evidence.get("blocker_status") != "open":
            errors.append(f"{label}: {evidence_id}.blocker_status must remain open")
        if evidence.get("authority_effect") is not False:
            errors.append(f"{label}: {evidence_id}.authority_effect must remain false")
        if evidence.get("promotion_effect") is not False:
            errors.append(f"{label}: {evidence_id}.promotion_effect must remain false")
        if tuple(evidence.get("acceptance_criteria", ())) != LIVE_RUNTIME_LOCAL_EVIDENCE_ACCEPTANCE_CRITERIA.get(
            evidence_id,
            (),
        ):
            errors.append(f"{label}: {evidence_id}.acceptance_criteria mismatch")


def _validate_authority(bundle: Mapping[str, Any], errors: list[str], label: str) -> None:
    disallowed_authority = _mapping(bundle.get("disallowed_authority"))
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
    """Parse Forge live-runtime local evidence validation arguments."""

    parser = argparse.ArgumentParser(description="Validate Forge live-runtime local evidence bundle.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--bundle", default=str(DEFAULT_BUNDLE))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for Forge live-runtime local evidence validation."""

    args = parse_args(argv)
    validation, produced_bundle = validate_forge_live_runtime_local_evidence_bundle(
        schema_path=Path(args.schema),
        bundle_path=Path(args.bundle),
    )
    write_forge_live_runtime_local_evidence_bundle_validation(validation, Path(args.output))
    if args.json:
        payload = validation.as_dict()
        payload["produced_bundle"] = produced_bundle
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif validation.ok:
        print("FORGE LIVE-RUNTIME LOCAL EVIDENCE BUNDLE VALID")
    else:
        print(f"FORGE LIVE-RUNTIME LOCAL EVIDENCE BUNDLE INVALID errors={list(validation.errors)}")
    return 0 if validation.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
