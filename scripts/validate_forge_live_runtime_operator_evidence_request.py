#!/usr/bin/env python3
"""Validate the Forge live-runtime operator evidence request.

Purpose: prove the operator evidence request is non-executing, redacted, and
aligned with the Forge evidence chain read model.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: gateway.forge_state_write_admission, operator evidence request
schema, operator evidence request fixture, and shared schema validation.
Invariants:
  - The request does not execute live probes.
  - Secret values are never serialized.
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
    FORGE_LIVE_RUNTIME_OPERATOR_EVIDENCE_REQUEST_ID,
    FORGE_LIVE_RUNTIME_OPERATOR_EVIDENCE_REQUEST_SCHEMA_REF,
    FORGE_WRITE_SPINE_BRIDGE_ID,
    LIVE_RUNTIME_EVIDENCE_COLLECTION_TARGETS,
    LIVE_RUNTIME_OPERATOR_EVIDENCE_REQUEST_CONTROLS,
    LIVE_RUNTIME_OPERATOR_REQUIRED_EVIDENCE_CLASSES,
    REQUIRED_LIVE_RUNTIME_EVIDENCE_IDS,
    build_foundation_forge_live_runtime_evidence_chain_read_model,
    build_foundation_forge_live_runtime_operator_evidence_request,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "forge_live_runtime_operator_evidence_request.schema.json"
DEFAULT_REQUEST = REPO_ROOT / "examples" / "forge_live_runtime_operator_evidence_request.foundation.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "forge_live_runtime_operator_evidence_request_validation.json"


@dataclass(frozen=True, slots=True)
class ForgeLiveRuntimeOperatorEvidenceRequestValidation:
    """Validation report for the Forge operator evidence request."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    request_path: str
    request_id: str
    request_status: str
    required_input_count: int
    blocked_reason_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_forge_live_runtime_operator_evidence_request(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    request_path: Path = DEFAULT_REQUEST,
) -> tuple[ForgeLiveRuntimeOperatorEvidenceRequestValidation, dict[str, Any]]:
    """Validate operator evidence request schema, semantics, and fixture parity."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "Forge operator evidence request schema", errors)
    request = _load_json_object(request_path, "Forge operator evidence request", errors)
    produced_request = build_foundation_forge_live_runtime_operator_evidence_request()

    if schema and request:
        errors.extend(f"{_path_label(request_path)}: {error}" for error in _validate_schema_instance(schema, request))
        _validate_request_semantics(request, errors, _path_label(request_path))
    if schema and produced_request:
        errors.extend(
            f"produced operator evidence request: {error}"
            for error in _validate_schema_instance(schema, produced_request)
        )
        _validate_request_semantics(produced_request, errors, "produced operator evidence request")
    if request and produced_request and request != produced_request:
        errors.append("fixture does not match deterministic Forge live-runtime operator evidence request")

    observed = produced_request or request
    required_inputs = observed.get("required_inputs", ())
    blocked_reasons = observed.get("blocked_reasons", ())
    validation = ForgeLiveRuntimeOperatorEvidenceRequestValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        request_path=_path_label(request_path),
        request_id=str(observed.get("request_id", "")),
        request_status=str(observed.get("request_status", "")),
        required_input_count=len(required_inputs) if isinstance(required_inputs, list) else 0,
        blocked_reason_count=len(blocked_reasons) if isinstance(blocked_reasons, list) else 0,
    )
    return validation, produced_request


def write_forge_live_runtime_operator_evidence_request_validation(
    validation: ForgeLiveRuntimeOperatorEvidenceRequestValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic operator evidence request validation report."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_request_semantics(request: Mapping[str, Any], errors: list[str], label: str) -> None:
    if request.get("request_id") != FORGE_LIVE_RUNTIME_OPERATOR_EVIDENCE_REQUEST_ID:
        errors.append(f"{label}: request_id mismatch")
    if request.get("schema_ref") != FORGE_LIVE_RUNTIME_OPERATOR_EVIDENCE_REQUEST_SCHEMA_REF:
        errors.append(f"{label}: schema_ref mismatch")
    if request.get("bridge_ref") != FORGE_WRITE_SPINE_BRIDGE_ID:
        errors.append(f"{label}: bridge_ref mismatch")
    if request.get("request_status") != "blocked_awaiting_operator_live_evidence_refs":
        errors.append(f"{label}: request_status must remain blocked_awaiting_operator_live_evidence_refs")
    if request.get("solver_outcome") != "AwaitingEvidence":
        errors.append(f"{label}: solver_outcome must remain AwaitingEvidence")
    if request.get("proof_state") != "Unknown":
        errors.append(f"{label}: proof_state must remain Unknown")
    for field_name in (
        "execution_allowed",
        "external_effect_performed",
        "secret_values_serialized",
        "production_ready_claimed",
        "runtime_authority_effect",
    ):
        if request.get(field_name) is not False:
            errors.append(f"{label}: {field_name} must remain false")
    read_model = build_foundation_forge_live_runtime_evidence_chain_read_model()
    if request.get("source_evidence_chain_read_model_hash") != read_model["read_model_hash"]:
        errors.append(f"{label}: source_evidence_chain_read_model_hash mismatch")
    _validate_required_inputs(request, errors, label)
    _validate_authority(request, errors, label)
    if tuple(request.get("required_controls", ())) != LIVE_RUNTIME_OPERATOR_EVIDENCE_REQUEST_CONTROLS:
        errors.append(f"{label}: required_controls drift")
    if request.get("next_allowed_action") != "supply_operator_approved_live_evidence_refs_without_secret_values":
        errors.append(f"{label}: next_allowed_action drift")


def _validate_required_inputs(request: Mapping[str, Any], errors: list[str], label: str) -> None:
    required_inputs = request.get("required_inputs")
    blocked_reasons = request.get("blocked_reasons")
    if not isinstance(required_inputs, list):
        errors.append(f"{label}: required_inputs must be a list")
        return
    evidence_ids = tuple(str(item.get("evidence_id", "")) for item in required_inputs if isinstance(item, Mapping))
    if evidence_ids != REQUIRED_LIVE_RUNTIME_EVIDENCE_IDS:
        errors.append(f"{label}: required_inputs order drift")
    if request.get("required_input_count") != len(REQUIRED_LIVE_RUNTIME_EVIDENCE_IDS):
        errors.append(f"{label}: required_input_count drift")
    expected_blockers = tuple(
        f"{evidence_id}_operator_live_evidence_refs_missing" for evidence_id in REQUIRED_LIVE_RUNTIME_EVIDENCE_IDS
    )
    if tuple(blocked_reasons or ()) != expected_blockers:
        errors.append(f"{label}: blocked_reasons drift")
    for item in required_inputs:
        required_input = _mapping(item)
        evidence_id = str(required_input.get("evidence_id", ""))
        if required_input.get("target_evidence_ref") != LIVE_RUNTIME_EVIDENCE_COLLECTION_TARGETS.get(evidence_id):
            errors.append(f"{label}: {evidence_id}.target_evidence_ref mismatch")
        if tuple(required_input.get("required_evidence_classes", ())) != LIVE_RUNTIME_OPERATOR_REQUIRED_EVIDENCE_CLASSES:
            errors.append(f"{label}: {evidence_id}.required_evidence_classes drift")
        if required_input.get("current_state") != "missing":
            errors.append(f"{label}: {evidence_id}.current_state must remain missing")
        if required_input.get("operator_action_required") != "supply_refs_without_secret_values":
            errors.append(f"{label}: {evidence_id}.operator_action_required drift")
        if required_input.get("secret_values_allowed") is not False:
            errors.append(f"{label}: {evidence_id}.secret_values_allowed must remain false")
        if required_input.get("execution_allowed_after_input") is not False:
            errors.append(f"{label}: {evidence_id}.execution_allowed_after_input must remain false")
        if required_input.get("blocker_reason") != f"{evidence_id}_operator_live_evidence_refs_missing":
            errors.append(f"{label}: {evidence_id}.blocker_reason mismatch")


def _validate_authority(request: Mapping[str, Any], errors: list[str], label: str) -> None:
    disallowed_authority = _mapping(request.get("disallowed_authority"))
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
    """Parse Forge operator evidence request validation arguments."""

    parser = argparse.ArgumentParser(description="Validate Forge live-runtime operator evidence request.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--request", default=str(DEFAULT_REQUEST))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for Forge operator evidence request validation."""

    args = parse_args(argv)
    validation, produced_request = validate_forge_live_runtime_operator_evidence_request(
        schema_path=Path(args.schema),
        request_path=Path(args.request),
    )
    write_forge_live_runtime_operator_evidence_request_validation(validation, Path(args.output))
    if args.json:
        payload = validation.as_dict()
        payload["produced_request"] = produced_request
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif validation.ok:
        print("FORGE LIVE-RUNTIME OPERATOR EVIDENCE REQUEST VALID")
    else:
        print(f"FORGE LIVE-RUNTIME OPERATOR EVIDENCE REQUEST INVALID errors={list(validation.errors)}")
    return 0 if validation.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
