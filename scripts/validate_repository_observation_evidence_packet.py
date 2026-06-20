#!/usr/bin/env python3
"""Validate the RepositoryObservationEvidencePacket contract.

Purpose: verify that repository observation evidence remains digest-only,
Foundation Mode safe, and separated from filesystem writes, file-content reads,
secret reads, connector calls, runtime dispatch, terminal closure, and success
claims.
Governance scope: OCE schema completeness, RAG artifact refs, CDCV
observation-to-admission causality, CQTE proof-state gates, UWMA receipt
anchoring, SRCA finite validation, and PRS focused closure.
Dependencies: Python standard library, scripts.validate_schemas,
schemas/repository_observation_evidence_packet.schema.json, and
examples/repository_observation_evidence_packet.foundation.json.
Invariants:
  - Validation is read-only and deterministic.
  - The Foundation example performs no live repository read.
  - Live local observations may claim read-only repository observation only.
  - Hard-constraint planning remains blocked while ProofState is Unknown.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
import sys
from pathlib import Path
from typing import Any


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA_PATH = WORKSPACE_ROOT / "schemas" / "repository_observation_evidence_packet.schema.json"
DEFAULT_PACKET_PATH = WORKSPACE_ROOT / "examples" / "repository_observation_evidence_packet.foundation.json"

EXPECTED_SCHEMA_ID = "urn:mullusi:schema:repository-observation-evidence-packet:1"
EXPECTED_SCHEMA_TITLE = "Repository Observation Evidence Packet"
EXPECTED_PACKET_VERSION = "repository_observation_evidence_packet.v1"
REQUIRED_RECEIPT_REFS = {
    "repository_observation_evidence_packet_schema": "schemas/repository_observation_evidence_packet.schema.json",
    "observation_evidence_acquisition_architecture_doc": "docs/94_observation_evidence_acquisition_architecture.md",
    "universal_action_orchestration_schema": "schemas/universal_action_orchestration.schema.json",
    "life_meaning_judgment_schema": "schemas/life_meaning_judgment.schema.json",
}
REQUIRED_ARTIFACT_REFS = (
    "schemas/repository_observation_evidence_packet.schema.json",
    "examples/repository_observation_evidence_packet.foundation.json",
    "scripts/produce_repository_observation_evidence_packet.py",
    "scripts/validate_repository_observation_evidence_packet.py",
    "tests/test_validate_repository_observation_evidence_packet.py",
    "docs/95_repository_observation_evidence_packet_contract.md",
    "docs/94_observation_evidence_acquisition_architecture.md",
    "schemas/universal_action_orchestration.schema.json",
)
FOUNDATION_OBSERVATION_MODE = "foundation_digest_example"
LIVE_OBSERVATION_MODE = "local_read_only_git_status"
SUPPORTED_OBSERVATION_MODES = (FOUNDATION_OBSERVATION_MODE, LIVE_OBSERVATION_MODE)
LIVE_READ_AUTHORITY_FIELD = "live_repository_read_performed"
MUTATING_DENIED_AUTHORITY_FIELDS = (
    "filesystem_write_performed",
    "file_content_read_performed",
    "secret_read_performed",
    "connector_call_performed",
    "external_write_performed",
    "runtime_dispatch_performed",
    "deployment_mutation_allowed",
    "terminal_closure_allowed",
    "success_claim_allowed",
)
DENIED_AUTHORITY_FIELDS = (
    "live_repository_read_performed",
    "filesystem_write_performed",
    "file_content_read_performed",
    "secret_read_performed",
    "connector_call_performed",
    "external_write_performed",
    "runtime_dispatch_performed",
    "deployment_mutation_allowed",
    "terminal_closure_allowed",
    "success_claim_allowed",
)
RAW_STORAGE_FIELDS = (
    "raw_git_status_stored",
    "raw_diff_stored",
    "raw_file_inventory_stored",
    "raw_file_contents_stored",
    "raw_secret_value_stored",
)
DIGEST_FIELDS = (
    ("observed_state", "branch_digest_ref"),
    ("observed_state", "git_status_digest_ref"),
    ("observed_state", "diff_digest_ref"),
    ("observed_state", "file_inventory_digest_ref"),
)


class RepositoryObservationEvidencePacketError(ValueError):
    """Raised when a repository observation packet cannot load."""


def load_json_object(json_path: Path, label: str) -> dict[str, Any]:
    """Load one JSON object from disk."""

    path = json_path if json_path.is_absolute() else WORKSPACE_ROOT / json_path
    if not path.exists():
        raise FileNotFoundError(f"missing {label}: {path}")
    if not path.is_file():
        raise IsADirectoryError(f"{label} path is not a file: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RepositoryObservationEvidencePacketError(f"{label} must be a JSON object")
    return payload


def validate_schema_artifact(schema: dict[str, Any]) -> list[str]:
    """Return deterministic schema artifact errors."""

    errors: list[str] = []
    if schema.get("$id") != EXPECTED_SCHEMA_ID:
        errors.append("schema $id is invalid")
    if schema.get("title") != EXPECTED_SCHEMA_TITLE:
        errors.append("schema title is invalid")
    if schema.get("type") != "object":
        errors.append("schema root type must be object")
    if schema.get("additionalProperties") is not False:
        errors.append("schema root must close additional properties")
    required_fields = schema.get("required")
    properties = schema.get("properties")
    if not isinstance(required_fields, list):
        errors.append("schema required field must be a list")
    if not isinstance(properties, dict):
        errors.append("schema properties must be an object")
    if isinstance(required_fields, list) and isinstance(properties, dict):
        for field_name in (
            "packet_id",
            "packet_version",
            "observation_scope",
            "observed_state",
            "evidence_admission",
            "authority_boundary",
            "privacy_guard",
            "receipt_refs",
            "contract_summary",
            "evidence_refs",
        ):
            if field_name not in required_fields:
                errors.append(f"schema missing required field: {field_name}")
            if field_name not in properties:
                errors.append(f"schema missing property: {field_name}")
    return errors


def validate_repository_observation_evidence_packet_record(
    record: Any,
    schema: dict[str, Any] | None = None,
) -> list[str]:
    """Return deterministic validation errors for one repository observation packet."""

    schema_payload = schema or _load_schema(DEFAULT_SCHEMA_PATH)
    errors = _validate_schema_instance(schema_payload, record)
    if not isinstance(record, dict):
        errors.append("repository observation evidence packet must be a JSON object")
        return errors

    observation_mode = _observation_mode(record)
    _validate_top_level(record, errors)
    _validate_observation_scope(record.get("observation_scope"), errors)
    _validate_observed_state(record.get("observed_state"), observation_mode, errors)
    _validate_evidence_admission(
        record.get("evidence_admission"),
        record.get("observed_state"),
        observation_mode,
        errors,
    )
    _validate_authority_boundary(record.get("authority_boundary"), observation_mode, errors)
    _validate_privacy_guard(record.get("privacy_guard"), errors)
    _validate_receipt_refs(record.get("receipt_refs"), errors)
    _validate_contract_summary(record, errors)
    _require_subset(record, "evidence_refs", REQUIRED_ARTIFACT_REFS, errors)
    return errors


def validate_repository_observation_evidence_packet(
    schema_path: Path = DEFAULT_SCHEMA_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[str]:
    """Validate the schema artifact and default Foundation Mode packet."""

    schema = _load_schema(schema_path)
    packet = load_json_object(packet_path, "RepositoryObservationEvidencePacket")
    errors = validate_schema_artifact(schema)
    errors.extend(validate_repository_observation_evidence_packet_record(packet, schema))
    return errors


def build_mutated_repository_observation_evidence_packet(**updates: Any) -> dict[str, Any]:
    """Build a deterministic mutated copy of the default packet."""

    packet = load_json_object(DEFAULT_PACKET_PATH, "RepositoryObservationEvidencePacket")
    mutated = deepcopy(packet)
    for dotted_key, value in updates.items():
        target = mutated
        segments = dotted_key.split("__")
        for segment in segments[:-1]:
            next_target = target.get(segment)
            if not isinstance(next_target, dict):
                next_target = {}
                target[segment] = next_target
            target = next_target
        target[segments[-1]] = value
    return mutated


def workspace_display_path(path: Path) -> str:
    """Return a stable workspace-relative display path when possible."""

    resolved_path = path if path.is_absolute() else WORKSPACE_ROOT / path
    try:
        return str(resolved_path.resolve().relative_to(WORKSPACE_ROOT))
    except ValueError:
        return str(path)


def _validate_top_level(record: dict[str, Any], errors: list[str]) -> None:
    if record.get("packet_version") != EXPECTED_PACKET_VERSION:
        errors.append("packet_version must match repository_observation_evidence_packet.v1")
    for parent_name, field_name in DIGEST_FIELDS:
        parent = record.get(parent_name)
        value = parent.get(field_name) if isinstance(parent, dict) else None
        _validate_digest_ref(f"{parent_name}.{field_name}", value, errors)


def _observation_mode(record: dict[str, Any]) -> str:
    scope = record.get("observation_scope")
    mode = scope.get("observation_mode") if isinstance(scope, dict) else ""
    return str(mode) if isinstance(mode, str) else ""


def _validate_observation_scope(scope: Any, errors: list[str]) -> None:
    if not isinstance(scope, dict):
        errors.append("observation_scope must be an object")
        return
    if scope.get("observation_mode") not in SUPPORTED_OBSERVATION_MODES:
        errors.append(
            "observation_scope.observation_mode must be foundation_digest_example or local_read_only_git_status"
        )
    if scope.get("source_kind") != "repository":
        errors.append("observation_scope.source_kind must be repository")
    if scope.get("tenant_scope") != "foundation-local-only":
        errors.append("observation_scope.tenant_scope must be foundation-local-only")
    if scope.get("observation_mode") == LIVE_OBSERVATION_MODE:
        expected_live_refs = {
            "collector_ref": "collector://repository-observation/local-read-only-git-status",
            "uao_ref": "uao://repository-observation/local-read-only-git-status",
            "life_meaning_judgment_ref": "life-meaning://repository-observation/local-read-only-git-status",
        }
        for field_name, expected_value in expected_live_refs.items():
            if scope.get(field_name) != expected_value:
                errors.append(f"observation_scope.{field_name} must be {expected_value}")
    for field_name in ("repository_ref", "worktree_ref", "collector_ref", "uao_ref", "life_meaning_judgment_ref"):
        if not isinstance(scope.get(field_name), str) or scope.get(field_name) == "":
            errors.append(f"observation_scope.{field_name} must be non-empty")


def _validate_observed_state(state: Any, observation_mode: str, errors: list[str]) -> None:
    if not isinstance(state, dict):
        errors.append("observed_state must be an object")
        return
    if observation_mode == FOUNDATION_OBSERVATION_MODE and state.get("freshness_state") != "awaiting_live_observation":
        errors.append("observed_state.freshness_state must be awaiting_live_observation")
    if observation_mode == LIVE_OBSERVATION_MODE:
        contradiction_refs = state.get("contradiction_refs")
        has_contradictions = isinstance(contradiction_refs, list) and bool(contradiction_refs)
        expected_freshness = "stale" if has_contradictions else "fresh"
        if state.get("freshness_state") != expected_freshness:
            errors.append(f"observed_state.freshness_state must be {expected_freshness}")
    if not isinstance(state.get("command_set_ref"), str) or state.get("command_set_ref") == "":
        errors.append("observed_state.command_set_ref must be non-empty")
    recovery_actions = state.get("recovery_actions")
    if not isinstance(recovery_actions, list) or not recovery_actions:
        errors.append("observed_state.recovery_actions must be a non-empty list")


def _validate_evidence_admission(
    admission: Any,
    observed_state: Any,
    observation_mode: str,
    errors: list[str],
) -> None:
    if not isinstance(admission, dict):
        errors.append("evidence_admission must be an object")
        return
    if observation_mode == LIVE_OBSERVATION_MODE:
        contradiction_refs = observed_state.get("contradiction_refs") if isinstance(observed_state, dict) else None
        has_contradictions = isinstance(contradiction_refs, list) and bool(contradiction_refs)
        expected_values = {
            "planning_admission": "reject" if has_contradictions else "admit",
            "proof_state": "Fail" if has_contradictions else "Pass",
            "solver_outcome": "GovernanceBlocked" if has_contradictions else "SolvedVerified",
            "hard_constraint_planning_allowed": False if has_contradictions else True,
            "soft_utility_planning_allowed": False if has_contradictions else True,
            "live_evidence_required": True,
            "live_evidence_state": "AwaitingEvidence" if has_contradictions else "SolvedVerified",
        }
    else:
        expected_values = {
            "planning_admission": "defer",
            "proof_state": "Unknown",
            "solver_outcome": "AwaitingEvidence",
            "hard_constraint_planning_allowed": False,
            "soft_utility_planning_allowed": True,
            "live_evidence_required": True,
            "live_evidence_state": "AwaitingEvidence",
        }
    for field_name, expected_value in expected_values.items():
        if admission.get(field_name) != expected_value:
            errors.append(f"evidence_admission.{field_name} must be {expected_value!r}")
    reason_refs = admission.get("admission_reason_refs")
    if not isinstance(reason_refs, list) or not reason_refs:
        errors.append("evidence_admission.admission_reason_refs must be a non-empty list")


def _validate_authority_boundary(boundary: Any, observation_mode: str, errors: list[str]) -> None:
    if not isinstance(boundary, dict):
        errors.append("authority_boundary must be an object")
        return
    expected_live_read = observation_mode == LIVE_OBSERVATION_MODE
    if boundary.get(LIVE_READ_AUTHORITY_FIELD) is not expected_live_read:
        errors.append(f"authority_boundary.{LIVE_READ_AUTHORITY_FIELD} must be {str(expected_live_read).lower()}")
    for field_name in MUTATING_DENIED_AUTHORITY_FIELDS:
        if boundary.get(field_name) is not False:
            errors.append(f"authority_boundary.{field_name} must be false")


def _validate_privacy_guard(guard: Any, errors: list[str]) -> None:
    if not isinstance(guard, dict):
        errors.append("privacy_guard must be an object")
        return
    for field_name in RAW_STORAGE_FIELDS:
        if guard.get(field_name) is not False:
            errors.append(f"privacy_guard.{field_name} must be false")
    if guard.get("private_payload_redacted") is not True:
        errors.append("privacy_guard.private_payload_redacted must be true")
    if guard.get("operator_review_required") is not True:
        errors.append("privacy_guard.operator_review_required must be true")
    if not isinstance(guard.get("retention_policy_ref"), str) or guard.get("retention_policy_ref") == "":
        errors.append("privacy_guard.retention_policy_ref must be non-empty")


def _validate_receipt_refs(refs: Any, errors: list[str]) -> None:
    if not isinstance(refs, dict):
        errors.append("receipt_refs must be an object")
        return
    for field_name, expected_ref in REQUIRED_RECEIPT_REFS.items():
        if refs.get(field_name) != expected_ref:
            errors.append(f"receipt_refs.{field_name} must be {expected_ref}")


def _validate_contract_summary(record: dict[str, Any], errors: list[str]) -> None:
    boundary = record.get("authority_boundary")
    guard = record.get("privacy_guard")
    refs = record.get("receipt_refs")
    summary = record.get("contract_summary")
    if not isinstance(boundary, dict) or not isinstance(guard, dict) or not isinstance(refs, dict) or not isinstance(summary, dict):
        errors.append("authority_boundary, privacy_guard, receipt_refs, and contract_summary must be typed")
        return
    admission = record.get("evidence_admission")
    hard_constraint_allowed = (
        admission.get("hard_constraint_planning_allowed")
        if isinstance(admission, dict)
        else None
    )
    false_authority_count = sum(1 for value in boundary.values() if value is False)
    expected_values = {
        "digest_only": True,
        "authority_denied": True,
        "hard_constraint_blocked": False if hard_constraint_allowed is True else True,
        "authority_denial_count": false_authority_count,
        "privacy_guard_count": len(guard),
        "receipt_ref_count": len(refs),
        "evidence_ref_count": _list_len(record.get("evidence_refs")),
    }
    for field_name, expected_value in expected_values.items():
        if expected_value is not None and summary.get(field_name) != expected_value:
            errors.append(f"contract_summary.{field_name} must match {expected_value!r}")


def _validate_digest_ref(label: str, value: Any, errors: list[str]) -> None:
    if not isinstance(value, str) or value == "":
        errors.append(f"{label} must be non-empty")
        return
    if not value.startswith("hash://sha256/"):
        errors.append(f"{label} must use hash://sha256/ digest ref")
    if "http://" in value or "https://" in value:
        errors.append(f"{label} must not store a raw URL")


def _list_len(value: Any) -> int | None:
    return len(value) if isinstance(value, list) else None


def _require_subset(record: dict[str, Any], field_name: str, required_values: tuple[str, ...], errors: list[str]) -> None:
    values = record.get(field_name)
    if not isinstance(values, list):
        errors.append(f"{field_name} must be a list")
        return
    for missing_value in sorted(set(required_values) - set(values)):
        errors.append(f"{field_name} missing required ref: {missing_value}")


def main(argv: list[str] | None = None) -> int:
    """Validate RepositoryObservationEvidencePacket artifacts from the CLI."""

    parser = argparse.ArgumentParser(description="Validate RepositoryObservationEvidencePacket contract.")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    parser.add_argument("--json", action="store_true", help="emit a machine-readable validation receipt")
    args = parser.parse_args(argv)
    errors = validate_repository_observation_evidence_packet(args.schema, args.packet)
    if args.json:
        print(
            json.dumps(
                {
                    "receipt_id": "repository_observation_evidence_packet_validation",
                    "schema_path": workspace_display_path(args.schema),
                    "packet_path": workspace_display_path(args.packet),
                    "status": "passed" if not errors else "failed",
                    "errors": errors,
                },
                indent=2,
                sort_keys=True,
            )
        )
    elif errors:
        for error in errors:
            print(f"[FAIL] {error}")
    else:
        print("[PASS] repository_observation_evidence_packet")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
