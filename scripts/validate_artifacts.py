#!/usr/bin/env python3
"""Governed artifact validation for MCOI examples, pilot assets, and MAF runtime fixtures.

Validates:
  1. Shipped config artifacts deserialize through AppConfig without silent key drift.
  2. Shipped request artifacts normalize through the governed CLI request contract.
  3. Request templates validate without executing adapters or mutating runtime state.
  4. Request action routes are admitted by their paired config artifact or by default config.
  5. Auxiliary pilot JSON artifacts remain inventory-bounded and contract-validated.
  6. MAF runtime fixtures remain inventory-bounded and structurally governed.
  7. Operator and pilot markdown references stay aligned with governed artifact inventory.
  8. Release and pilot operational documents stay aligned with live profiles, packs, and witnesses.

Usage:
  python scripts/validate_artifacts.py
  python scripts/validate_artifacts.py --strict
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable


REPO_ROOT = Path(__file__).resolve().parent.parent
MCOI_PATH = REPO_ROOT / "mcoi"
MCOI_EXAMPLES_DIR = MCOI_PATH / "examples"
PILOT_EXAMPLES_DIR = REPO_ROOT / "examples" / "pilots"
MAF_RUNTIME_FIXTURE_DIR = REPO_ROOT / "integration" / "contracts_compat" / "fixtures" / "maf_runtime"

if str(MCOI_PATH) not in sys.path:
    sys.path.insert(0, str(MCOI_PATH))

from mcoi_runtime.app.cli import _build_operator_request
from mcoi_runtime.app.config import AppConfig
from mcoi_runtime.app.policy_packs import PolicyPackRegistry
from mcoi_runtime.app.profiles import list_profiles
from mcoi_runtime.contracts.document import DocumentVerificationStatus
from mcoi_runtime.core.document import extract_json_fields, ingest_document, verify_extraction
from mcoi_runtime.core.template_validator import TemplateValidationError, TemplateValidator


@dataclass(frozen=True, slots=True)
class ExampleArtifactInventory:
    """Deterministic inventory of governed JSON artifacts."""

    config_paths: tuple[Path, ...]
    request_paths: tuple[Path, ...]
    auxiliary_paths: tuple[Path, ...]
    maf_runtime_fixture_paths: tuple[Path, ...]
    pilot_directories: tuple[Path, ...]


@dataclass(frozen=True, slots=True)
class OperationalDocumentExpectation:
    """Required dynamic and static content for governed non-JSON documents."""

    required_literals: tuple[str, ...] = ()
    forbidden_literals: tuple[str, ...] = ()
    require_all_profiles: bool = False
    require_all_policy_packs: bool = False


AuxiliaryArtifactValidator = Callable[[Path], list[str]]
MAFRuntimeFixtureValidator = Callable[[Path], list[str]]


def _sort_paths(paths: list[Path]) -> tuple[Path, ...]:
    return tuple(sorted(paths, key=lambda path: path.relative_to(REPO_ROOT).as_posix()))


def _relative_path(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _load_json_object(path: Path, *, kind: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{_relative_path(path)}: invalid {kind} JSON: {exc.msg}") from exc
    except OSError as exc:
        raise ValueError(f"{_relative_path(path)}: cannot read {kind} artifact: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError(f"{_relative_path(path)}: {kind} JSON root must be an object")
    return payload


def _validate_iso8601_text(value: Any, *, field_name: str, path: Path) -> list[str]:
    if not isinstance(value, str) or not value.strip():
        return [f"{_relative_path(path)}: field '{field_name}' must be a non-empty ISO 8601 string"]
    normalized = value.replace("Z", "+00:00")
    try:
        datetime.fromisoformat(normalized)
    except ValueError:
        return [f"{_relative_path(path)}: field '{field_name}' must be a valid ISO 8601 string"]
    return []


def _require_non_empty_text(value: Any, *, field_name: str, path: Path) -> list[str]:
    if isinstance(value, str) and value.strip():
        return []
    return [f"{_relative_path(path)}: field '{field_name}' must be a non-empty string"]


def _require_positive_int(value: Any, *, field_name: str, path: Path) -> list[str]:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return [f"{_relative_path(path)}: field '{field_name}' must be a positive integer"]
    return []


def _require_non_negative_int(value: Any, *, field_name: str, path: Path) -> list[str]:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return [f"{_relative_path(path)}: field '{field_name}' must be a non-negative integer"]
    return []


def _require_number_in_range(
    value: Any,
    *,
    field_name: str,
    path: Path,
    minimum: float,
    maximum: float,
) -> list[str]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return [f"{_relative_path(path)}: field '{field_name}' must be a numeric value"]
    if value < minimum or value > maximum:
        return [
            f"{_relative_path(path)}: field '{field_name}' must be between {minimum} and {maximum}"
        ]
    return []


def _validate_exact_object_fields(
    payload: dict[str, Any],
    *,
    path: Path,
    expected_fields: tuple[str, ...],
    kind: str,
) -> list[str]:
    errors: list[str] = []
    unknown_fields = sorted(set(payload) - set(expected_fields))
    missing_fields = tuple(field for field in expected_fields if field not in payload)
    if unknown_fields:
        errors.append(
            f"{_relative_path(path)}: unexpected {kind} fields: {', '.join(unknown_fields)}"
        )
    if missing_fields:
        errors.append(f"{_relative_path(path)}: missing {kind} fields: {', '.join(missing_fields)}")
    return errors


def _validate_document_to_action_input(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="pilot auxiliary")
    errors: list[str] = []
    expected_keys = ("task", "target", "retention_days", "notify_email")

    unknown_keys = sorted(set(payload) - set(expected_keys))
    if unknown_keys:
        errors.append(
            f"{_relative_path(path)}: unexpected auxiliary fields: {', '.join(unknown_keys)}"
        )

    missing_keys = tuple(key for key in expected_keys if key not in payload)
    if missing_keys:
        errors.append(
            f"{_relative_path(path)}: missing auxiliary fields: {', '.join(missing_keys)}"
        )
        return errors

    errors.extend(_require_non_empty_text(payload["task"], field_name="task", path=path))
    errors.extend(_require_non_empty_text(payload["target"], field_name="target", path=path))
    errors.extend(_require_positive_int(payload["retention_days"], field_name="retention_days", path=path))
    errors.extend(_require_non_empty_text(payload["notify_email"], field_name="notify_email", path=path))
    if errors:
        return errors

    content = path.read_text(encoding="utf-8")
    document_one = ingest_document(
        "pilot-document-to-action-input",
        _relative_path(path),
        content,
    )
    document_two = ingest_document(
        "pilot-document-to-action-input",
        _relative_path(path),
        content,
    )
    extraction = extract_json_fields(document_one, expected_keys)
    verification = verify_extraction(extraction, expected_keys)

    if document_one.fingerprint.content_hash != document_two.fingerprint.content_hash:
        errors.append(f"{_relative_path(path)}: document fingerprint must be deterministic")
    if extraction.extracted_count != len(expected_keys):
        errors.append(f"{_relative_path(path)}: extracted_count must equal expected field count")
    if extraction.missing_count != 0:
        errors.append(f"{_relative_path(path)}: extraction must not miss required pilot fields")
    if extraction.malformed_count != 0:
        errors.append(f"{_relative_path(path)}: extraction must not mark pilot fields malformed")
    if verification.status is not DocumentVerificationStatus.PASS:
        errors.append(f"{_relative_path(path)}: verification must pass for the shipped pilot document")

    return errors


AUXILIARY_PILOT_VALIDATORS: dict[str, AuxiliaryArtifactValidator] = {
    "examples/pilots/document_to_action/input_document.json": _validate_document_to_action_input,
}


def _validate_event_record_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "event_id",
            "event_type",
            "source",
            "correlation_id",
            "payload",
            "emitted_at",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors

    errors.extend(_require_non_empty_text(payload["event_id"], field_name="event_id", path=path))
    errors.extend(_require_non_empty_text(payload["event_type"], field_name="event_type", path=path))
    errors.extend(_require_non_empty_text(payload["source"], field_name="source", path=path))
    errors.extend(
        _require_non_empty_text(payload["correlation_id"], field_name="correlation_id", path=path)
    )
    errors.extend(_validate_iso8601_text(payload["emitted_at"], field_name="emitted_at", path=path))
    if not isinstance(payload["payload"], dict) or not payload["payload"]:
        errors.append(f"{_relative_path(path)}: field 'payload' must be a non-empty object")
    return errors


def _validate_supervisor_tick_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "tick_id",
            "tick_number",
            "phase_sequence",
            "events_polled",
            "obligations_evaluated",
            "deadlines_checked",
            "reactions_fired",
            "decisions",
            "outcome",
            "errors",
            "started_at",
            "completed_at",
            "duration_ms",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors

    errors.extend(_require_non_empty_text(payload["tick_id"], field_name="tick_id", path=path))
    errors.extend(_require_non_negative_int(payload["tick_number"], field_name="tick_number", path=path))
    for field_name in (
        "events_polled",
        "obligations_evaluated",
        "deadlines_checked",
        "reactions_fired",
        "duration_ms",
    ):
        errors.extend(_require_non_negative_int(payload[field_name], field_name=field_name, path=path))
    for field_name in ("started_at", "completed_at"):
        errors.extend(_validate_iso8601_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(_require_non_empty_text(payload["outcome"], field_name="outcome", path=path))

    phase_sequence = payload["phase_sequence"]
    if not isinstance(phase_sequence, list) or not phase_sequence:
        errors.append(f"{_relative_path(path)}: field 'phase_sequence' must be a non-empty array")
    else:
        for index, phase in enumerate(phase_sequence):
            if not isinstance(phase, str) or not phase.strip():
                errors.append(
                    f"{_relative_path(path)}: phase_sequence[{index}] must be a non-empty string"
                )

    decision_fields = (
        "decision_id",
        "action_type",
        "target_id",
        "reason",
        "governance_approved",
        "decided_at",
        "metadata",
    )
    decisions = payload["decisions"]
    if not isinstance(decisions, list):
        errors.append(f"{_relative_path(path)}: field 'decisions' must be an array")
    else:
        for index, decision in enumerate(decisions):
            if not isinstance(decision, dict):
                errors.append(f"{_relative_path(path)}: decisions[{index}] must be an object")
                continue
            nested_errors = _validate_exact_object_fields(
                decision,
                path=path,
                expected_fields=decision_fields,
                kind=f"decision[{index}]",
            )
            if nested_errors:
                errors.extend(nested_errors)
                continue
            for field_name in ("decision_id", "action_type", "target_id", "reason"):
                errors.extend(
                    _require_non_empty_text(
                        decision[field_name],
                        field_name=f"decisions[{index}].{field_name}",
                        path=path,
                    )
                )
            if not isinstance(decision["governance_approved"], bool):
                errors.append(
                    f"{_relative_path(path)}: field 'decisions[{index}].governance_approved' must be boolean"
                )
            errors.extend(
                _validate_iso8601_text(
                    decision["decided_at"],
                    field_name=f"decisions[{index}].decided_at",
                    path=path,
                )
            )
            if not isinstance(decision["metadata"], dict):
                errors.append(
                    f"{_relative_path(path)}: field 'decisions[{index}].metadata' must be an object"
                )

    error_values = payload["errors"]
    if not isinstance(error_values, list):
        errors.append(f"{_relative_path(path)}: field 'errors' must be an array")
    else:
        for index, error_value in enumerate(error_values):
            if not isinstance(error_value, str) or not error_value.strip():
                errors.append(f"{_relative_path(path)}: errors[{index}] must be a non-empty string")

    return errors


def _validate_simulation_comparison_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "comparison_id",
            "request_id",
            "ranked_option_ids",
            "scores",
            "top_risk_level",
            "review_burden",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors

    errors.extend(
        _require_non_empty_text(payload["comparison_id"], field_name="comparison_id", path=path)
    )
    errors.extend(_require_non_empty_text(payload["request_id"], field_name="request_id", path=path))
    errors.extend(
        _require_non_empty_text(payload["top_risk_level"], field_name="top_risk_level", path=path)
    )
    errors.extend(
        _require_number_in_range(
            payload["review_burden"],
            field_name="review_burden",
            path=path,
            minimum=0.0,
            maximum=1.0,
        )
    )

    ranked_option_ids = payload["ranked_option_ids"]
    if not isinstance(ranked_option_ids, list) or not ranked_option_ids:
        errors.append(f"{_relative_path(path)}: field 'ranked_option_ids' must be a non-empty array")
    else:
        for index, option_id in enumerate(ranked_option_ids):
            if not isinstance(option_id, str) or not option_id.strip():
                errors.append(
                    f"{_relative_path(path)}: ranked_option_ids[{index}] must be a non-empty string"
                )
        if len(set(ranked_option_ids)) != len(ranked_option_ids):
            errors.append(f"{_relative_path(path)}: ranked_option_ids must not contain duplicates")

    scores = payload["scores"]
    if not isinstance(scores, dict) or not scores:
        errors.append(f"{_relative_path(path)}: field 'scores' must be a non-empty object")
    else:
        for option_id, score in scores.items():
            if not isinstance(option_id, str) or not option_id.strip():
                errors.append(f"{_relative_path(path)}: scores keys must be non-empty strings")
                break
            if isinstance(score, bool) or not isinstance(score, (int, float)):
                errors.append(
                    f"{_relative_path(path)}: score for option '{option_id}' must be numeric"
                )
        if isinstance(ranked_option_ids, list) and ranked_option_ids:
            if set(scores.keys()) != set(ranked_option_ids):
                errors.append(
                    f"{_relative_path(path)}: scores keys must match ranked_option_ids exactly"
                )

    return errors


def _validate_job_descriptor_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "job_id",
            "name",
            "description",
            "priority",
            "created_at",
            "goal_id",
            "workflow_id",
            "deadline",
            "sla_target_minutes",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors

    for field_name in (
        "job_id",
        "name",
        "description",
        "priority",
        "goal_id",
        "workflow_id",
    ):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    for field_name in ("created_at", "deadline"):
        errors.extend(_validate_iso8601_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(
        _require_positive_int(
            payload["sla_target_minutes"],
            field_name="sla_target_minutes",
            path=path,
        )
    )
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")

    return errors


def _validate_goal_plan_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("plan_id", "goal_id", "sub_goals", "created_at", "version"),
        kind="runtime fixture",
    )
    if errors:
        return errors

    errors.extend(_require_non_empty_text(payload["plan_id"], field_name="plan_id", path=path))
    errors.extend(_require_non_empty_text(payload["goal_id"], field_name="goal_id", path=path))
    errors.extend(_validate_iso8601_text(payload["created_at"], field_name="created_at", path=path))
    errors.extend(_require_positive_int(payload["version"], field_name="version", path=path))

    sub_goals = payload["sub_goals"]
    if not isinstance(sub_goals, list) or not sub_goals:
        errors.append(f"{_relative_path(path)}: field 'sub_goals' must be a non-empty array")
        return errors

    sub_goal_fields = (
        "sub_goal_id",
        "goal_id",
        "description",
        "status",
        "skill_id",
        "workflow_id",
        "predecessors",
    )
    sub_goal_ids: list[str] = []
    predecessor_pairs: list[tuple[str, list[str]]] = []
    for index, sub_goal in enumerate(sub_goals):
        if not isinstance(sub_goal, dict):
            errors.append(f"{_relative_path(path)}: sub_goals[{index}] must be an object")
            continue
        nested_errors = _validate_exact_object_fields(
            sub_goal,
            path=path,
            expected_fields=sub_goal_fields,
            kind=f"sub_goal[{index}]",
        )
        if nested_errors:
            errors.extend(nested_errors)
            continue
        for field_name in ("sub_goal_id", "goal_id", "description", "status", "skill_id", "workflow_id"):
            errors.extend(
                _require_non_empty_text(
                    sub_goal[field_name],
                    field_name=f"sub_goals[{index}].{field_name}",
                    path=path,
                )
            )
        predecessors = sub_goal["predecessors"]
        if not isinstance(predecessors, list):
            errors.append(f"{_relative_path(path)}: sub_goals[{index}].predecessors must be an array")
        else:
            for predecessor_index, predecessor in enumerate(predecessors):
                if not isinstance(predecessor, str) or not predecessor.strip():
                    errors.append(
                        f"{_relative_path(path)}: sub_goals[{index}].predecessors[{predecessor_index}] must be a non-empty string"
                    )
        sub_goal_id = sub_goal["sub_goal_id"]
        sub_goal_ids.append(sub_goal_id)
        predecessor_pairs.append((sub_goal_id, list(predecessors) if isinstance(predecessors, list) else []))

    known_ids = set(sub_goal_ids)
    if len(known_ids) != len(sub_goal_ids):
        errors.append(f"{_relative_path(path)}: sub_goals must have unique sub_goal_id values")
    for sub_goal_id, predecessors in predecessor_pairs:
        for predecessor in predecessors:
            if predecessor not in known_ids:
                errors.append(
                    f"{_relative_path(path)}: sub_goal '{sub_goal_id}' references unknown predecessor '{predecessor}'"
                )
            elif predecessor == sub_goal_id:
                errors.append(
                    f"{_relative_path(path)}: sub_goal '{sub_goal_id}' must not list itself as a predecessor"
                )

    return errors


def _validate_obligation_record_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "obligation_id",
            "trigger",
            "trigger_ref_id",
            "state",
            "owner",
            "deadline",
            "description",
            "correlation_id",
            "metadata",
            "created_at",
            "updated_at",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors

    for field_name in (
        "obligation_id",
        "trigger",
        "trigger_ref_id",
        "state",
        "description",
        "correlation_id",
    ):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    for field_name in ("created_at", "updated_at"):
        errors.extend(_validate_iso8601_text(payload[field_name], field_name=field_name, path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")

    owner = payload["owner"]
    if not isinstance(owner, dict):
        errors.append(f"{_relative_path(path)}: field 'owner' must be an object")
    else:
        owner_errors = _validate_exact_object_fields(
            owner,
            path=path,
            expected_fields=("owner_id", "owner_type", "display_name"),
            kind="owner",
        )
        if owner_errors:
            errors.extend(owner_errors)
        else:
            for field_name in ("owner_id", "owner_type", "display_name"):
                errors.extend(
                    _require_non_empty_text(
                        owner[field_name],
                        field_name=f"owner.{field_name}",
                        path=path,
                    )
                )

    deadline = payload["deadline"]
    if not isinstance(deadline, dict):
        errors.append(f"{_relative_path(path)}: field 'deadline' must be an object")
    else:
        deadline_errors = _validate_exact_object_fields(
            deadline,
            path=path,
            expected_fields=("deadline_id", "due_at", "warn_at", "hard"),
            kind="deadline",
        )
        if deadline_errors:
            errors.extend(deadline_errors)
        else:
            errors.extend(
                _require_non_empty_text(
                    deadline["deadline_id"],
                    field_name="deadline.deadline_id",
                    path=path,
                )
            )
            errors.extend(
                _validate_iso8601_text(deadline["due_at"], field_name="deadline.due_at", path=path)
            )
            errors.extend(
                _validate_iso8601_text(
                    deadline["warn_at"],
                    field_name="deadline.warn_at",
                    path=path,
                )
            )
            if not isinstance(deadline["hard"], bool):
                errors.append(f"{_relative_path(path)}: field 'deadline.hard' must be boolean")

    return errors


def _validate_service_function_template_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "function_id",
            "name",
            "function_type",
            "description",
            "created_at",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors

    for field_name in ("function_id", "name", "function_type", "description"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(_validate_iso8601_text(payload["created_at"], field_name="created_at", path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")

    return errors


def _validate_role_descriptor_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "role_id",
            "name",
            "description",
            "required_skills",
            "approval_required",
            "max_concurrent_per_worker",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors

    for field_name in ("role_id", "name", "description"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    required_skills = payload["required_skills"]
    if not isinstance(required_skills, list) or not required_skills:
        errors.append(f"{_relative_path(path)}: field 'required_skills' must be a non-empty array")
    else:
        for index, skill in enumerate(required_skills):
            if not isinstance(skill, str) or not skill.strip():
                errors.append(
                    f"{_relative_path(path)}: required_skills[{index}] must be a non-empty string"
                )
    if not isinstance(payload["approval_required"], bool):
        errors.append(f"{_relative_path(path)}: field 'approval_required' must be boolean")
    errors.extend(
        _require_positive_int(
            payload["max_concurrent_per_worker"],
            field_name="max_concurrent_per_worker",
            path=path,
        )
    )
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")

    return errors


MAF_RUNTIME_FIXTURE_VALIDATORS: dict[str, MAFRuntimeFixtureValidator] = {
    "event_record.json": _validate_event_record_fixture,
    "job_descriptor.json": _validate_job_descriptor_fixture,
    "goal_plan.json": _validate_goal_plan_fixture,
    "obligation_record.json": _validate_obligation_record_fixture,
    "role_descriptor.json": _validate_role_descriptor_fixture,
    "service_function_template.json": _validate_service_function_template_fixture,
    "simulation_comparison.json": _validate_simulation_comparison_fixture,
    "supervisor_tick.json": _validate_supervisor_tick_fixture,
}

DOCUMENT_ARTIFACT_EXPECTATIONS: dict[str, tuple[str, ...]] = {
    "OPERATOR_GUIDE_v0.1.md": (
        "mcoi/examples/config-local-dev.json",
        "mcoi/examples/config-safe-readonly.json",
        "mcoi/examples/request-echo.json",
        "mcoi/examples/request-with-bindings.json",
    ),
    "PILOT_WORKFLOWS_v0.1.md": (
        "examples/pilots/approval_gated_command/config.json",
        "examples/pilots/approval_gated_command/request.json",
        "examples/pilots/document_to_action/config.json",
        "examples/pilots/document_to_action/input_document.json",
        "examples/pilots/failure_escalation/config.json",
    ),
}

OPERATIONAL_DOCUMENT_EXPECTATIONS: dict[str, OperationalDocumentExpectation] = {
    "RELEASE_CHECKLIST_v0.1.md": OperationalDocumentExpectation(
        required_literals=(
            "RELEASE_NOTES_v0.1.md",
            "KNOWN_LIMITATIONS_v0.1.md",
            "SECURITY_MODEL_v0.1.md",
            "OPERATOR_GUIDE_v0.1.md",
            "PILOT_WORKFLOWS_v0.1.md",
            "PILOT_CHECKLIST_v0.1.md",
            "PILOT_OPERATIONS_GUIDE_v0.1.md",
            "pytest -q",
            "cargo test",
            "scripts/validate_schemas.py --strict",
            "scripts/validate_artifacts.py --strict",
            "scripts/validate_release_status.py --strict",
        ),
        forbidden_literals=(
            "352+ tests",
            "All 4 profiles load correctly",
            "18 architecture docs complete",
            "22 JSON schemas validated",
        ),
        require_all_profiles=True,
        require_all_policy_packs=True,
    ),
    "RELEASE_NOTES_v0.1.md": OperationalDocumentExpectation(
        required_literals=(
            "OPERATOR_GUIDE_v0.1.md",
            "PILOT_WORKFLOWS_v0.1.md",
            "PILOT_CHECKLIST_v0.1.md",
            "PILOT_OPERATIONS_GUIDE_v0.1.md",
            "scripts/validate_schemas.py --strict",
            "scripts/validate_release_status.py --strict",
            "pytest -q",
            "cargo test",
        ),
        forbidden_literals=(
            "Configuration profiles: local-dev, safe-readonly, operator-approved, sandboxed",
            "**Python:** 352 tests",
            "**JSON schemas:** 16 schemas",
            "18 documents covering all planes and subsystems",
        ),
        require_all_profiles=True,
    ),
    "PILOT_CHECKLIST_v0.1.md": OperationalDocumentExpectation(
        required_literals=(
            "pytest -q",
            "cargo test",
            "scripts/validate_artifacts.py --strict",
            "examples/pilots/approval_gated_command/config.json",
            "examples/pilots/approval_gated_command/request.json",
            "examples/pilots/document_to_action/config.json",
            "examples/pilots/document_to_action/input_document.json",
            "examples/pilots/failure_escalation/config.json",
            "PILOT_WORKFLOWS_v0.1.md",
        ),
        forbidden_literals=(
            "556+ Python tests",
            "21 Rust tests",
        ),
    ),
    "PILOT_OPERATIONS_GUIDE_v0.1.md": OperationalDocumentExpectation(
        required_literals=(
            "OPERATOR_GUIDE_v0.1.md",
            "PILOT_WORKFLOWS_v0.1.md",
            "PILOT_CHECKLIST_v0.1.md",
        ),
    ),
}

_DOC_ARTIFACT_PATTERN = re.compile(
    r"(mcoi/examples/[A-Za-z0-9._/-]+\.json|examples/pilots/[A-Za-z0-9._/-]+\.json)"
)


def discover_example_inventory() -> ExampleArtifactInventory:
    """Discover the governed artifact inventory."""
    pilot_directories = (
        _sort_paths([path for path in PILOT_EXAMPLES_DIR.iterdir() if path.is_dir()])
        if PILOT_EXAMPLES_DIR.exists()
        else ()
    )
    config_paths = _sort_paths(
        list(MCOI_EXAMPLES_DIR.glob("config-*.json"))
        + [path / "config.json" for path in pilot_directories if (path / "config.json").exists()]
    )
    request_paths = _sort_paths(
        list(MCOI_EXAMPLES_DIR.glob("request-*.json"))
        + [path / "request.json" for path in pilot_directories if (path / "request.json").exists()]
    )
    auxiliary_paths = _sort_paths(
        [
            path
            for pilot_directory in pilot_directories
            for path in pilot_directory.glob("*.json")
            if path.name not in {"config.json", "request.json"}
        ]
    )
    maf_runtime_fixture_paths = (
        _sort_paths(list(MAF_RUNTIME_FIXTURE_DIR.glob("*.json")))
        if MAF_RUNTIME_FIXTURE_DIR.exists()
        else ()
    )
    return ExampleArtifactInventory(
        config_paths=config_paths,
        request_paths=request_paths,
        auxiliary_paths=auxiliary_paths,
        maf_runtime_fixture_paths=maf_runtime_fixture_paths,
        pilot_directories=pilot_directories,
    )


def validate_config_artifact(path: Path) -> list[str]:
    """Validate a shipped config artifact against the app config contract."""
    try:
        payload = _load_json_object(path, kind="config")
        AppConfig.from_mapping(payload)
    except ValueError as exc:
        return [f"{_relative_path(path)}: {exc}"]
    return []


def _load_request_config(request_path: Path) -> tuple[AppConfig | None, list[str]]:
    paired_config_path = request_path.parent / "config.json"
    if not paired_config_path.exists():
        return AppConfig(), []
    errors = validate_config_artifact(paired_config_path)
    if errors:
        return None, errors
    return AppConfig.from_mapping(_load_json_object(paired_config_path, kind="config")), []


def validate_request_artifact(path: Path) -> list[str]:
    """Validate a shipped request artifact against the CLI request and template contracts."""
    errors: list[str] = []

    try:
        payload = _load_json_object(path, kind="request")
        request = _build_operator_request(payload, source_name=_relative_path(path))
    except ValueError as exc:
        return [str(exc)]

    validator = TemplateValidator()
    try:
        validated_template = validator.validate(request.template, request.bindings)
    except TemplateValidationError as exc:
        errors.append(f"{_relative_path(path)}: invalid request template {exc.code}: {exc}")
        return errors

    config, config_errors = _load_request_config(path)
    errors.extend(config_errors)
    if config is None:
        return errors

    if validated_template.action_type.value not in config.enabled_executor_routes:
        errors.append(
            f"{_relative_path(path)}: action route '{validated_template.action_type.value}' "
            "is not enabled by the paired config"
        )

    return errors


def validate_auxiliary_artifact(path: Path, *, artifact_key: str | None = None) -> list[str]:
    """Validate one governed auxiliary pilot artifact."""
    validator_key = artifact_key or _relative_path(path)
    validator = AUXILIARY_PILOT_VALIDATORS.get(validator_key)
    if validator is None:
        return [f"{_relative_path(path)}: no auxiliary validator registered"]
    return validator(path)


def validate_maf_runtime_fixture(path: Path, *, fixture_name: str | None = None) -> list[str]:
    """Validate one governed MAF runtime fixture witness."""
    validator_key = fixture_name or path.name
    validator = MAF_RUNTIME_FIXTURE_VALIDATORS.get(validator_key)
    if validator is None:
        return [f"{_relative_path(path)}: no MAF runtime fixture validator registered"]
    return validator(path)


def validate_maf_runtime_fixtures(*, strict: bool = False) -> list[str]:
    """Validate governed MAF runtime fixture inventory and witness shape."""
    errors: list[str] = []
    inventory = discover_example_inventory()
    actual_paths = inventory.maf_runtime_fixture_paths
    actual_names = {path.name for path in actual_paths}
    expected_names = set(MAF_RUNTIME_FIXTURE_VALIDATORS)

    if not MAF_RUNTIME_FIXTURE_DIR.exists():
        return [f"MAF runtime fixture directory not found: {_relative_path(MAF_RUNTIME_FIXTURE_DIR)}"]

    missing_fixtures = sorted(expected_names - actual_names)
    if missing_fixtures:
        errors.append(f"missing governed MAF runtime fixtures: {missing_fixtures}")
    if strict:
        unexpected_fixtures = sorted(actual_names - expected_names)
        if unexpected_fixtures:
            errors.append(f"unexpected MAF runtime fixtures: {unexpected_fixtures}")
    if strict and not actual_paths:
        errors.append("no governed MAF runtime fixtures discovered")

    for fixture_path in actual_paths:
        errors.extend(validate_maf_runtime_fixture(fixture_path))

    return errors


def validate_document_artifact_reference_text(
    *,
    document_name: str,
    content: str,
    expected_paths: tuple[str, ...],
    governed_paths: set[str],
    strict: bool = False,
) -> list[str]:
    """Validate governed artifact references within one markdown document."""
    errors: list[str] = []
    referenced_paths = tuple(sorted(set(_DOC_ARTIFACT_PATTERN.findall(content))))

    missing_expected = sorted(set(expected_paths) - set(referenced_paths))
    if missing_expected:
        errors.append(
            f"{document_name}: missing governed artifact references {missing_expected}"
        )

    for referenced_path in referenced_paths:
        artifact_path = REPO_ROOT / referenced_path
        if referenced_path not in governed_paths:
            errors.append(
                f"{document_name}: references ungoverned artifact path {referenced_path}"
            )
        elif not artifact_path.exists():
            errors.append(
                f"{document_name}: references missing artifact path {referenced_path}"
            )

    if strict:
        unexpected_references = sorted(set(referenced_paths) - set(expected_paths))
        if unexpected_references:
            errors.append(
                f"{document_name}: unexpected governed artifact references {unexpected_references}"
            )

    return errors


def validate_documented_artifact_references(*, strict: bool = False) -> list[str]:
    """Validate markdown references to governed artifacts."""
    errors: list[str] = []
    inventory = discover_example_inventory()
    governed_paths = {
        _relative_path(path)
        for path in (
            list(inventory.config_paths)
            + list(inventory.request_paths)
            + list(inventory.auxiliary_paths)
        )
    }

    for document_name, expected_paths in DOCUMENT_ARTIFACT_EXPECTATIONS.items():
        document_path = REPO_ROOT / document_name
        if not document_path.exists():
            errors.append(f"{document_name}: documentation file not found")
            continue

        content = document_path.read_text(encoding="utf-8")
        errors.extend(
            validate_document_artifact_reference_text(
                document_name=document_name,
                content=content,
                expected_paths=expected_paths,
                governed_paths=governed_paths,
                strict=strict,
            )
        )

    return errors


def validate_operational_document_text(
    *,
    document_name: str,
    content: str,
    strict: bool = False,
) -> list[str]:
    """Validate non-JSON governed documents against live inventories."""
    expectation = OPERATIONAL_DOCUMENT_EXPECTATIONS.get(document_name)
    if expectation is None:
        return [f"{document_name}: no operational document expectation registered"] if strict else []

    errors: list[str] = []

    missing_literals = tuple(
        literal for literal in expectation.required_literals if literal not in content
    )
    if missing_literals:
        errors.append(f"{document_name}: missing required literals {list(missing_literals)}")

    stale_literals = tuple(
        literal for literal in expectation.forbidden_literals if literal in content
    )
    if stale_literals:
        errors.append(f"{document_name}: contains stale literals {list(stale_literals)}")

    if expectation.require_all_profiles:
        missing_profiles = tuple(
            profile_name for profile_name in list_profiles() if profile_name not in content
        )
        if missing_profiles:
            errors.append(f"{document_name}: missing built-in profiles {list(missing_profiles)}")

    if expectation.require_all_policy_packs:
        pack_ids = tuple(pack.pack_id for pack in PolicyPackRegistry().list_packs())
        missing_pack_ids = tuple(pack_id for pack_id in pack_ids if pack_id not in content)
        if missing_pack_ids:
            errors.append(f"{document_name}: missing policy pack IDs {list(missing_pack_ids)}")

    return errors


def validate_operational_documents(*, strict: bool = False) -> list[str]:
    """Validate release and pilot operational docs against governed inventories."""
    errors: list[str] = []

    for document_name in OPERATIONAL_DOCUMENT_EXPECTATIONS:
        document_path = REPO_ROOT / document_name
        if not document_path.exists():
            errors.append(f"{document_name}: operational document not found")
            continue

        content = document_path.read_text(encoding="utf-8")
        errors.extend(
            validate_operational_document_text(
                document_name=document_name,
                content=content,
                strict=strict,
            )
        )

    return errors


def validate_example_artifacts(*, strict: bool = False) -> list[str]:
    """Validate the shipped example inventory."""
    inventory = discover_example_inventory()
    errors: list[str] = []

    if strict and not inventory.config_paths:
        errors.append("no shipped config artifacts discovered")
    if strict and not inventory.request_paths:
        errors.append("no shipped request artifacts discovered")
    if strict and not inventory.maf_runtime_fixture_paths:
        errors.append("no governed MAF runtime fixtures discovered")
    if strict:
        expected_auxiliary = set(AUXILIARY_PILOT_VALIDATORS)
        actual_auxiliary = {_relative_path(path) for path in inventory.auxiliary_paths}
        missing_auxiliary = sorted(expected_auxiliary - actual_auxiliary)
        unexpected_auxiliary = sorted(actual_auxiliary - expected_auxiliary)
        if missing_auxiliary:
            errors.append(f"missing governed auxiliary pilot artifacts: {missing_auxiliary}")
        if unexpected_auxiliary:
            errors.append(f"unexpected auxiliary pilot artifacts: {unexpected_auxiliary}")

    for pilot_directory in inventory.pilot_directories:
        if not (pilot_directory / "config.json").exists():
            errors.append(
                f"{_relative_path(pilot_directory)}: pilot directory missing required config.json"
            )

    for config_path in inventory.config_paths:
        errors.extend(validate_config_artifact(config_path))

    for request_path in inventory.request_paths:
        errors.extend(validate_request_artifact(request_path))

    for auxiliary_path in inventory.auxiliary_paths:
        errors.extend(validate_auxiliary_artifact(auxiliary_path))

    errors.extend(validate_maf_runtime_fixtures(strict=strict))
    errors.extend(validate_documented_artifact_references(strict=strict))
    errors.extend(validate_operational_documents(strict=strict))

    return errors


def main() -> None:
    strict = "--strict" in sys.argv
    inventory = discover_example_inventory()

    print("=== Artifact Inventory ===")
    print(f"  config artifacts:  {len(inventory.config_paths)}")
    print(f"  request artifacts: {len(inventory.request_paths)}")
    print(f"  auxiliary files:   {len(inventory.auxiliary_paths)}")
    print(f"  MAF fixtures:      {len(inventory.maf_runtime_fixture_paths)}")
    print(f"  pilot directories: {len(inventory.pilot_directories)}")

    print("\n=== Artifact Validation ===")
    errors = validate_example_artifacts(strict=strict)
    if errors:
        print(f"\n{'=' * 40}")
        print(f"FAILED - {len(errors)} error(s):")
        for error in errors:
            print(f"  X {error}")
        sys.exit(1)

    print(f"\n{'=' * 40}")
    print("ALL CHECKS PASSED")
    sys.exit(0)


if __name__ == "__main__":
    main()
