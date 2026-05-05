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
    return _validate_event_record_fixture_dict(payload, path=path, field_name="runtime fixture")


def _validate_event_record_fixture_dict(
    payload: object,
    *,
    path: Path,
    field_name: str,
) -> list[str]:
    if not isinstance(payload, dict):
        return [f"{_relative_path(path)}: field '{field_name}' must be an object"]
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
        kind=field_name,
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


def _validate_event_envelope_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "envelope_id",
            "event",
            "target_subsystems",
            "priority",
            "delivered",
            "delivered_at",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors

    errors.extend(_require_non_empty_text(payload["envelope_id"], field_name="envelope_id", path=path))
    errors.extend(
        _validate_event_record_fixture_dict(payload["event"], path=path, field_name="event")
    )
    target_subsystems = payload["target_subsystems"]
    if not isinstance(target_subsystems, list) or not target_subsystems:
        errors.append(f"{_relative_path(path)}: field 'target_subsystems' must be a non-empty array")
    else:
        for index, subsystem in enumerate(target_subsystems):
            errors.extend(
                _require_non_empty_text(
                    subsystem,
                    field_name=f"target_subsystems[{index}]",
                    path=path,
                )
            )
    errors.extend(_require_non_negative_int(payload["priority"], field_name="priority", path=path))
    if not isinstance(payload["delivered"], bool):
        errors.append(f"{_relative_path(path)}: field 'delivered' must be boolean")
    errors.extend(
        _validate_iso8601_text(payload["delivered_at"], field_name="delivered_at", path=path)
    )
    return errors


def _validate_event_subscription_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "subscription_id",
            "event_type",
            "subscriber_id",
            "reaction_id",
            "filter_source",
            "active",
            "created_at",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors

    for field_name in ("subscription_id", "event_type", "subscriber_id", "reaction_id", "filter_source"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if not isinstance(payload["active"], bool):
        errors.append(f"{_relative_path(path)}: field 'active' must be boolean")
    errors.extend(_validate_iso8601_text(payload["created_at"], field_name="created_at", path=path))
    return errors


def _validate_event_reaction_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "reaction_id",
            "event_id",
            "subscription_id",
            "action_taken",
            "result",
            "reacted_at",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors

    for field_name in ("reaction_id", "event_id", "subscription_id", "action_taken", "result"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(_validate_iso8601_text(payload["reacted_at"], field_name="reacted_at", path=path))
    return errors


def _validate_event_window_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "window_id",
            "correlation_id",
            "window_start",
            "window_end",
            "event_count",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors

    errors.extend(_require_non_empty_text(payload["window_id"], field_name="window_id", path=path))
    errors.extend(
        _require_non_empty_text(payload["correlation_id"], field_name="correlation_id", path=path)
    )
    errors.extend(_validate_iso8601_text(payload["window_start"], field_name="window_start", path=path))
    errors.extend(_validate_iso8601_text(payload["window_end"], field_name="window_end", path=path))
    errors.extend(_require_non_negative_int(payload["event_count"], field_name="event_count", path=path))
    return errors


def _validate_event_correlation_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "correlation_id",
            "event_ids",
            "root_event_id",
            "description",
            "created_at",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors

    errors.extend(
        _require_non_empty_text(payload["correlation_id"], field_name="correlation_id", path=path)
    )
    errors.extend(_require_non_empty_text(payload["root_event_id"], field_name="root_event_id", path=path))
    errors.extend(_require_non_empty_text(payload["description"], field_name="description", path=path))
    errors.extend(_validate_iso8601_text(payload["created_at"], field_name="created_at", path=path))

    event_ids = payload["event_ids"]
    if not isinstance(event_ids, list) or not event_ids:
        errors.append(f"{_relative_path(path)}: field 'event_ids' must be a non-empty array")
    else:
        for index, event_id in enumerate(event_ids):
            errors.extend(
                _require_non_empty_text(event_id, field_name=f"event_ids[{index}]", path=path)
            )
        if isinstance(payload["root_event_id"], str) and payload["root_event_id"] not in event_ids:
            errors.append(f"{_relative_path(path)}: root_event_id must be present in event_ids")
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

    errors.extend(
        _validate_obligation_owner_dict(payload["owner"], path=path, field_name="owner")
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


def _validate_obligation_owner_dict(owner: object, *, path: Path, field_name: str) -> list[str]:
    if not isinstance(owner, dict):
        return [f"{_relative_path(path)}: field '{field_name}' must be an object"]
    errors = _validate_exact_object_fields(
        owner,
        path=path,
        expected_fields=("owner_id", "owner_type", "display_name"),
        kind=field_name,
    )
    if errors:
        return errors
    for nested_field_name in ("owner_id", "owner_type", "display_name"):
        errors.extend(
            _require_non_empty_text(
                owner[nested_field_name],
                field_name=f"{field_name}.{nested_field_name}",
                path=path,
            )
        )
    return errors


def _validate_obligation_closure_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "closure_id",
            "obligation_id",
            "final_state",
            "reason",
            "closed_by",
            "closed_at",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("closure_id", "obligation_id", "final_state", "reason", "closed_by"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(_validate_iso8601_text(payload["closed_at"], field_name="closed_at", path=path))
    if payload["final_state"] not in {"completed", "expired", "cancelled"}:
        errors.append(
            f"{_relative_path(path)}: final_state must be one of completed, expired, or cancelled"
        )
    return errors


def _validate_obligation_transfer_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "transfer_id",
            "obligation_id",
            "from_owner",
            "to_owner",
            "reason",
            "transferred_at",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("transfer_id", "obligation_id", "reason"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(
        _validate_obligation_owner_dict(payload["from_owner"], path=path, field_name="from_owner")
    )
    errors.extend(
        _validate_obligation_owner_dict(payload["to_owner"], path=path, field_name="to_owner")
    )
    errors.extend(
        _validate_iso8601_text(payload["transferred_at"], field_name="transferred_at", path=path)
    )
    from_owner = payload["from_owner"]
    to_owner = payload["to_owner"]
    if (
        isinstance(from_owner, dict)
        and isinstance(to_owner, dict)
        and isinstance(from_owner.get("owner_id"), str)
        and isinstance(to_owner.get("owner_id"), str)
        and from_owner.get("owner_id") == to_owner.get("owner_id")
    ):
        errors.append(f"{_relative_path(path)}: from_owner.owner_id must differ from to_owner.owner_id")
    return errors


def _validate_obligation_escalation_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "escalation_id",
            "obligation_id",
            "escalated_to",
            "reason",
            "severity",
            "escalated_at",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("escalation_id", "obligation_id", "reason", "severity"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(
        _validate_obligation_owner_dict(payload["escalated_to"], path=path, field_name="escalated_to")
    )
    errors.extend(
        _validate_iso8601_text(payload["escalated_at"], field_name="escalated_at", path=path)
    )
    return errors


def _validate_operational_node_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    return _validate_operational_node_dict(payload, path=path, field_name="runtime fixture")


def _validate_operational_node_dict(payload: object, *, path: Path, field_name: str) -> list[str]:
    if not isinstance(payload, dict):
        return [f"{_relative_path(path)}: field '{field_name}' must be an object"]
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("node_id", "node_type", "label", "created_at", "metadata"),
        kind=field_name,
    )
    if errors:
        return errors
    prefix = "" if field_name == "runtime fixture" else f"{field_name}."
    for nested_field_name in ("node_id", "node_type", "label"):
        errors.extend(
            _require_non_empty_text(
                payload[nested_field_name],
                field_name=f"{prefix}{nested_field_name}".strip("."),
                path=path,
            )
        )
    errors.extend(
        _validate_iso8601_text(
            payload["created_at"],
            field_name=f"{prefix}created_at".strip("."),
            path=path,
        )
    )
    if not isinstance(payload["metadata"], dict):
        metadata_field_name = f"{prefix}metadata".strip(".")
        errors.append(f"{_relative_path(path)}: field '{metadata_field_name}' must be an object")
    return errors


def _validate_operational_edge_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    return _validate_operational_edge_dict(payload, path=path, field_name="runtime fixture")


def _validate_operational_edge_dict(payload: object, *, path: Path, field_name: str) -> list[str]:
    if not isinstance(payload, dict):
        return [f"{_relative_path(path)}: field '{field_name}' must be an object"]
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "edge_id",
            "edge_type",
            "source_node_id",
            "target_node_id",
            "label",
            "created_at",
            "metadata",
        ),
        kind=field_name,
    )
    if errors:
        return errors
    prefix = "" if field_name == "runtime fixture" else f"{field_name}."
    for nested_field_name in (
        "edge_id",
        "edge_type",
        "source_node_id",
        "target_node_id",
        "label",
    ):
        errors.extend(
            _require_non_empty_text(
                payload[nested_field_name],
                field_name=f"{prefix}{nested_field_name}".strip("."),
                path=path,
            )
        )
    errors.extend(
        _validate_iso8601_text(
            payload["created_at"],
            field_name=f"{prefix}created_at".strip("."),
            path=path,
        )
    )
    if not isinstance(payload["metadata"], dict):
        metadata_field_name = f"{prefix}metadata".strip(".")
        errors.append(f"{_relative_path(path)}: field '{metadata_field_name}' must be an object")
    return errors


def _validate_evidence_link_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "edge_id",
            "source_node_id",
            "target_node_id",
            "evidence_type",
            "confidence",
            "created_at",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("edge_id", "source_node_id", "target_node_id", "evidence_type"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(
        _require_number_in_range(
            payload["confidence"],
            field_name="confidence",
            path=path,
            minimum=0.0,
            maximum=1.0,
        )
    )
    errors.extend(_validate_iso8601_text(payload["created_at"], field_name="created_at", path=path))
    return errors


def _validate_decision_link_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "edge_id",
            "source_node_id",
            "target_node_id",
            "decision",
            "decided_by_id",
            "created_at",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("edge_id", "source_node_id", "target_node_id", "decision", "decided_by_id"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(_validate_iso8601_text(payload["created_at"], field_name="created_at", path=path))
    return errors


def _validate_obligation_link_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "edge_id",
            "source_node_id",
            "target_node_id",
            "obligation",
            "fulfilled",
            "created_at",
            "deadline",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("edge_id", "source_node_id", "target_node_id", "obligation"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if not isinstance(payload["fulfilled"], bool):
        errors.append(f"{_relative_path(path)}: field 'fulfilled' must be boolean")
    errors.extend(_validate_iso8601_text(payload["created_at"], field_name="created_at", path=path))
    errors.extend(_validate_iso8601_text(payload["deadline"], field_name="deadline", path=path))
    return errors


def _validate_state_delta_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("delta_id", "node_id", "field_name", "old_value", "new_value", "changed_at"),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("delta_id", "node_id", "field_name"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    for field_name in ("old_value", "new_value"):
        if not isinstance(payload[field_name], str):
            errors.append(f"{_relative_path(path)}: field '{field_name}' must be a string")
    errors.extend(_validate_iso8601_text(payload["changed_at"], field_name="changed_at", path=path))
    return errors


def _validate_causal_path_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("path_id", "node_ids", "edge_ids", "description"),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("path_id", "description"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    for list_name in ("node_ids", "edge_ids"):
        values = payload[list_name]
        if not isinstance(values, list) or not values:
            errors.append(f"{_relative_path(path)}: field '{list_name}' must be a non-empty array")
        else:
            for index, value in enumerate(values):
                errors.extend(_require_non_empty_text(value, field_name=f"{list_name}[{index}]", path=path))
    return errors


def _validate_graph_snapshot_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("snapshot_id", "node_count", "edge_count", "captured_at"),
        kind="runtime fixture",
    )
    if errors:
        return errors
    errors.extend(_require_non_empty_text(payload["snapshot_id"], field_name="snapshot_id", path=path))
    errors.extend(_require_non_negative_int(payload["node_count"], field_name="node_count", path=path))
    errors.extend(_require_non_negative_int(payload["edge_count"], field_name="edge_count", path=path))
    errors.extend(_validate_iso8601_text(payload["captured_at"], field_name="captured_at", path=path))
    return errors


def _validate_graph_query_result_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("query_id", "matched_nodes", "matched_edges", "executed_at"),
        kind="runtime fixture",
    )
    if errors:
        return errors
    errors.extend(_require_non_empty_text(payload["query_id"], field_name="query_id", path=path))
    errors.extend(_validate_iso8601_text(payload["executed_at"], field_name="executed_at", path=path))
    matched_nodes = payload["matched_nodes"]
    if not isinstance(matched_nodes, list):
        errors.append(f"{_relative_path(path)}: field 'matched_nodes' must be an array")
    else:
        for index, node in enumerate(matched_nodes):
            errors.extend(
                _validate_operational_node_dict(node, path=path, field_name=f"matched_nodes[{index}]")
            )
    matched_edges = payload["matched_edges"]
    if not isinstance(matched_edges, list):
        errors.append(f"{_relative_path(path)}: field 'matched_edges' must be an array")
    else:
        for index, edge in enumerate(matched_edges):
            errors.extend(
                _validate_operational_edge_dict(edge, path=path, field_name=f"matched_edges[{index}]")
            )
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


def _validate_function_policy_binding_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "binding_id",
            "function_id",
            "policy_pack_id",
            "autonomy_mode",
            "review_required",
            "deployment_profile_id",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in (
        "binding_id",
        "function_id",
        "policy_pack_id",
        "autonomy_mode",
        "deployment_profile_id",
    ):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if not isinstance(payload["review_required"], bool):
        errors.append(f"{_relative_path(path)}: field 'review_required' must be boolean")
    return errors


def _validate_function_sla_profile_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "function_id",
            "target_completion_minutes",
            "approval_latency_minutes",
            "escalation_threshold_minutes",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    errors.extend(_require_non_empty_text(payload["function_id"], field_name="function_id", path=path))
    for field_name in (
        "target_completion_minutes",
        "approval_latency_minutes",
        "escalation_threshold_minutes",
    ):
        errors.extend(_require_positive_int(payload[field_name], field_name=field_name, path=path))
    if (
        isinstance(payload["target_completion_minutes"], int)
        and isinstance(payload["escalation_threshold_minutes"], int)
        and not isinstance(payload["target_completion_minutes"], bool)
        and not isinstance(payload["escalation_threshold_minutes"], bool)
        and payload["escalation_threshold_minutes"] > payload["target_completion_minutes"]
    ):
        errors.append(
            f"{_relative_path(path)}: escalation_threshold_minutes must not exceed target_completion_minutes"
        )
    return errors


def _validate_function_queue_profile_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "function_id",
            "team_id",
            "default_role_id",
            "communication_style",
            "max_concurrent_jobs",
            "escalation_chain_id",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in (
        "function_id",
        "team_id",
        "default_role_id",
        "communication_style",
        "escalation_chain_id",
    ):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(
        _require_positive_int(
            payload["max_concurrent_jobs"],
            field_name="max_concurrent_jobs",
            path=path,
        )
    )
    return errors


def _validate_assignment_policy_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "policy_id",
            "role_id",
            "strategy",
            "fallback_team_id",
            "escalation_chain_id",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in (
        "policy_id",
        "role_id",
        "strategy",
        "fallback_team_id",
        "escalation_chain_id",
    ):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    return errors


def _validate_worker_capacity_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    return _validate_worker_capacity_fixture_dict(payload, path)


def _validate_team_queue_state_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "team_id",
            "queued_jobs",
            "assigned_jobs",
            "waiting_jobs",
            "overloaded_workers",
            "captured_at",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    errors.extend(_require_non_empty_text(payload["team_id"], field_name="team_id", path=path))
    for field_name in (
        "queued_jobs",
        "assigned_jobs",
        "waiting_jobs",
        "overloaded_workers",
    ):
        errors.extend(_require_non_negative_int(payload[field_name], field_name=field_name, path=path))
    errors.extend(_validate_iso8601_text(payload["captured_at"], field_name="captured_at", path=path))
    return errors


def _validate_worker_profile_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "worker_id",
            "name",
            "roles",
            "max_concurrent_jobs",
            "status",
            "metadata",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("worker_id", "name", "status"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    roles = payload["roles"]
    if not isinstance(roles, list) or not roles:
        errors.append(f"{_relative_path(path)}: field 'roles' must be a non-empty array")
    else:
        for index, role in enumerate(roles):
            if not isinstance(role, str) or not role.strip():
                errors.append(f"{_relative_path(path)}: roles[{index}] must be a non-empty string")
    errors.extend(
        _require_positive_int(
            payload["max_concurrent_jobs"],
            field_name="max_concurrent_jobs",
            path=path,
        )
    )
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_assignment_decision_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "decision_id",
            "job_id",
            "worker_id",
            "role_id",
            "reason",
            "decided_at",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("decision_id", "job_id", "worker_id", "role_id", "reason"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(_validate_iso8601_text(payload["decided_at"], field_name="decided_at", path=path))
    return errors


def _validate_handoff_record_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "handoff_id",
            "job_id",
            "from_worker_id",
            "to_worker_id",
            "reason",
            "thread_id",
            "handoff_at",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in (
        "handoff_id",
        "job_id",
        "from_worker_id",
        "to_worker_id",
        "reason",
        "thread_id",
    ):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(_validate_iso8601_text(payload["handoff_at"], field_name="handoff_at", path=path))
    if payload["from_worker_id"] == payload["to_worker_id"]:
        errors.append(f"{_relative_path(path)}: from_worker_id and to_worker_id must differ")
    return errors


def _validate_workload_snapshot_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("snapshot_id", "team_id", "worker_capacities", "captured_at"),
        kind="runtime fixture",
    )
    if errors:
        return errors
    errors.extend(_require_non_empty_text(payload["snapshot_id"], field_name="snapshot_id", path=path))
    errors.extend(_require_non_empty_text(payload["team_id"], field_name="team_id", path=path))
    errors.extend(_validate_iso8601_text(payload["captured_at"], field_name="captured_at", path=path))
    worker_capacities = payload["worker_capacities"]
    if not isinstance(worker_capacities, list) or not worker_capacities:
        errors.append(f"{_relative_path(path)}: field 'worker_capacities' must be a non-empty array")
        return errors
    seen_worker_ids: set[str] = set()
    for index, worker_capacity in enumerate(worker_capacities):
        if not isinstance(worker_capacity, dict):
            errors.append(f"{_relative_path(path)}: worker_capacities[{index}] must be an object")
            continue
        nested_path = Path(f"{path.as_posix()}#{index}")
        nested_errors = _validate_worker_capacity_fixture_dict(worker_capacity, nested_path)
        errors.extend(nested_errors)
        worker_id = worker_capacity.get("worker_id")
        if isinstance(worker_id, str) and worker_id in seen_worker_ids:
            errors.append(
                f"{_relative_path(path)}: worker_capacities must not repeat worker_id '{worker_id}'"
            )
        elif isinstance(worker_id, str):
            seen_worker_ids.add(worker_id)
    return errors


def _validate_function_outcome_record_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "outcome_id",
            "function_id",
            "job_id",
            "completed",
            "completion_minutes",
            "escalated",
            "drift_detected",
            "recorded_at",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("outcome_id", "function_id", "job_id"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    for field_name in ("completed", "escalated", "drift_detected"):
        if not isinstance(payload[field_name], bool):
            errors.append(f"{_relative_path(path)}: field '{field_name}' must be boolean")
    errors.extend(
        _require_non_negative_int(
            payload["completion_minutes"],
            field_name="completion_minutes",
            path=path,
        )
    )
    errors.extend(_validate_iso8601_text(payload["recorded_at"], field_name="recorded_at", path=path))
    return errors


def _validate_function_metrics_snapshot_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "function_id",
            "period_start",
            "period_end",
            "total_jobs",
            "completed_jobs",
            "failed_jobs",
            "avg_completion_minutes",
            "escalation_count",
            "drift_count",
            "captured_at",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    errors.extend(_require_non_empty_text(payload["function_id"], field_name="function_id", path=path))
    for field_name in ("period_start", "period_end", "captured_at"):
        errors.extend(_validate_iso8601_text(payload[field_name], field_name=field_name, path=path))
    for field_name in (
        "total_jobs",
        "completed_jobs",
        "failed_jobs",
        "escalation_count",
        "drift_count",
    ):
        errors.extend(_require_non_negative_int(payload[field_name], field_name=field_name, path=path))
    errors.extend(
        _require_number_in_range(
            payload["avg_completion_minutes"],
            field_name="avg_completion_minutes",
            path=path,
            minimum=0.0,
            maximum=1000000.0,
        )
    )
    return errors


def _validate_worker_capacity_fixture_dict(payload: dict[str, Any], path: Path) -> list[str]:
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "worker_id",
            "max_concurrent",
            "current_load",
            "available_slots",
            "updated_at",
        ),
        kind="worker_capacity",
    )
    if errors:
        return errors
    errors.extend(_require_non_empty_text(payload["worker_id"], field_name="worker_id", path=path))
    errors.extend(_require_positive_int(payload["max_concurrent"], field_name="max_concurrent", path=path))
    errors.extend(_require_non_negative_int(payload["current_load"], field_name="current_load", path=path))
    errors.extend(_require_non_negative_int(payload["available_slots"], field_name="available_slots", path=path))
    errors.extend(_validate_iso8601_text(payload["updated_at"], field_name="updated_at", path=path))
    if (
        isinstance(payload["max_concurrent"], int)
        and isinstance(payload["current_load"], int)
        and isinstance(payload["available_slots"], int)
        and not isinstance(payload["max_concurrent"], bool)
        and not isinstance(payload["current_load"], bool)
        and not isinstance(payload["available_slots"], bool)
    ):
        if payload["current_load"] > payload["max_concurrent"]:
            errors.append(f"{_relative_path(path)}: current_load cannot exceed max_concurrent")
        if payload["available_slots"] != payload["max_concurrent"] - payload["current_load"]:
            errors.append(
                f"{_relative_path(path)}: available_slots must equal max_concurrent - current_load"
            )
    return errors


def _validate_simulation_option_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "option_id",
            "label",
            "risk_level",
            "estimated_cost",
            "estimated_duration_seconds",
            "success_probability",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("option_id", "label", "risk_level"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(
        _require_non_negative_float(payload["estimated_cost"], field_name="estimated_cost", path=path)
    )
    errors.extend(
        _require_non_negative_float(
            payload["estimated_duration_seconds"],
            field_name="estimated_duration_seconds",
            path=path,
        )
    )
    errors.extend(
        _require_number_in_range(
            payload["success_probability"],
            field_name="success_probability",
            path=path,
            minimum=0.0,
            maximum=1.0,
        )
    )
    return errors


def _require_non_negative_float(value: Any, *, field_name: str, path: Path) -> list[str]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return [f"{_relative_path(path)}: field '{field_name}' must be a numeric value"]
    if value < 0:
        return [f"{_relative_path(path)}: field '{field_name}' must be non-negative"]
    return []


def _validate_simulation_request_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("request_id", "context_type", "context_id", "description", "options"),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("request_id", "context_type", "context_id", "description"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    options = payload["options"]
    if not isinstance(options, list) or not options:
        errors.append(f"{_relative_path(path)}: field 'options' must be a non-empty array")
        return errors
    seen_option_ids: set[str] = set()
    for index, option in enumerate(options):
        if not isinstance(option, dict):
            errors.append(f"{_relative_path(path)}: options[{index}] must be an object")
            continue
        nested_path = Path(f"{path.as_posix()}#options[{index}]")
        errors.extend(_validate_simulation_option_fixture_dict(option, nested_path))
        option_id = option.get("option_id")
        if isinstance(option_id, str) and option_id in seen_option_ids:
            errors.append(f"{_relative_path(path)}: options must not repeat option_id '{option_id}'")
        elif isinstance(option_id, str):
            seen_option_ids.add(option_id)
    return errors


def _validate_consequence_estimate_dict(payload: dict[str, Any], path: Path) -> list[str]:
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "estimate_id",
            "option_id",
            "affected_node_ids",
            "new_edges_count",
            "new_obligations_count",
            "blocked_nodes_count",
            "unblocked_nodes_count",
        ),
        kind="consequence",
    )
    if errors:
        return errors
    for field_name in ("estimate_id", "option_id"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    affected_node_ids = payload["affected_node_ids"]
    if not isinstance(affected_node_ids, list):
        errors.append(f"{_relative_path(path)}: field 'affected_node_ids' must be an array")
    else:
        for index, node_id in enumerate(affected_node_ids):
            if not isinstance(node_id, str) or not node_id.strip():
                errors.append(
                    f"{_relative_path(path)}: affected_node_ids[{index}] must be a non-empty string"
                )
    for field_name in (
        "new_edges_count",
        "new_obligations_count",
        "blocked_nodes_count",
        "unblocked_nodes_count",
    ):
        errors.extend(_require_non_negative_int(payload[field_name], field_name=field_name, path=path))
    return errors


def _validate_risk_estimate_dict(payload: dict[str, Any], path: Path) -> list[str]:
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "estimate_id",
            "option_id",
            "risk_level",
            "incident_probability",
            "review_burden",
            "provider_exposure_count",
            "verification_difficulty",
            "rationale",
        ),
        kind="risk",
    )
    if errors:
        return errors
    for field_name in ("estimate_id", "option_id", "risk_level", "verification_difficulty", "rationale"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(
        _require_number_in_range(
            payload["incident_probability"],
            field_name="incident_probability",
            path=path,
            minimum=0.0,
            maximum=1.0,
        )
    )
    for field_name in ("review_burden", "provider_exposure_count"):
        errors.extend(_require_non_negative_int(payload[field_name], field_name=field_name, path=path))
    return errors


def _validate_obligation_projection_dict(payload: dict[str, Any], path: Path) -> list[str]:
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "projection_id",
            "option_id",
            "new_obligations",
            "fulfilled_obligations",
            "deadline_pressure",
        ),
        kind="obligation_projection",
    )
    if errors:
        return errors
    for field_name in ("projection_id", "option_id"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    for list_name in ("new_obligations", "fulfilled_obligations"):
        values = payload[list_name]
        if not isinstance(values, list):
            errors.append(f"{_relative_path(path)}: field '{list_name}' must be an array")
        else:
            for index, obligation_id in enumerate(values):
                if not isinstance(obligation_id, str) or not obligation_id.strip():
                    errors.append(
                        f"{_relative_path(path)}: {list_name}[{index}] must be a non-empty string"
                    )
    errors.extend(
        _require_non_negative_int(
            payload["deadline_pressure"],
            field_name="deadline_pressure",
            path=path,
        )
    )
    return errors


def _validate_simulation_option_fixture_dict(payload: dict[str, Any], path: Path) -> list[str]:
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "option_id",
            "label",
            "risk_level",
            "estimated_cost",
            "estimated_duration_seconds",
            "success_probability",
        ),
        kind="simulation_option",
    )
    if errors:
        return errors
    for field_name in ("option_id", "label", "risk_level"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(_require_non_negative_float(payload["estimated_cost"], field_name="estimated_cost", path=path))
    errors.extend(
        _require_non_negative_float(
            payload["estimated_duration_seconds"],
            field_name="estimated_duration_seconds",
            path=path,
        )
    )
    errors.extend(
        _require_number_in_range(
            payload["success_probability"],
            field_name="success_probability",
            path=path,
            minimum=0.0,
            maximum=1.0,
        )
    )
    return errors


def _validate_simulation_outcome_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "outcome_id",
            "option_id",
            "consequence",
            "risk",
            "obligation_projection",
            "simulated_at",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    errors.extend(_require_non_empty_text(payload["outcome_id"], field_name="outcome_id", path=path))
    errors.extend(_require_non_empty_text(payload["option_id"], field_name="option_id", path=path))
    errors.extend(_validate_iso8601_text(payload["simulated_at"], field_name="simulated_at", path=path))
    for nested_name, validator in (
        ("consequence", _validate_consequence_estimate_dict),
        ("risk", _validate_risk_estimate_dict),
        ("obligation_projection", _validate_obligation_projection_dict),
    ):
        nested_value = payload[nested_name]
        if not isinstance(nested_value, dict):
            errors.append(f"{_relative_path(path)}: field '{nested_name}' must be an object")
        else:
            nested_path = Path(f"{path.as_posix()}#{nested_name}")
            errors.extend(validator(nested_value, nested_path))
            option_id = nested_value.get("option_id")
            if isinstance(option_id, str) and option_id != payload["option_id"]:
                errors.append(
                    f"{_relative_path(path)}: {nested_name}.option_id must match outcome option_id"
                )
    return errors


def _validate_simulation_verdict_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "verdict_id",
            "comparison_id",
            "verdict_type",
            "recommended_option_id",
            "confidence",
            "reasons",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("verdict_id", "comparison_id", "verdict_type", "recommended_option_id"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(
        _require_number_in_range(
            payload["confidence"],
            field_name="confidence",
            path=path,
            minimum=0.0,
            maximum=1.0,
        )
    )
    reasons = payload["reasons"]
    if not isinstance(reasons, list) or not reasons:
        errors.append(f"{_relative_path(path)}: field 'reasons' must be a non-empty array")
    else:
        for index, reason in enumerate(reasons):
            if not isinstance(reason, str) or not reason.strip():
                errors.append(f"{_relative_path(path)}: reasons[{index}] must be a non-empty string")
    return errors


def _validate_benchmark_scenario_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    return _validate_benchmark_scenario_dict(payload, path=path, field_name="runtime fixture")


def _validate_benchmark_scenario_dict(payload: object, *, path: Path, field_name: str) -> list[str]:
    if not isinstance(payload, dict):
        return [f"{_relative_path(path)}: field '{field_name}' must be an object"]
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "scenario_id",
            "name",
            "description",
            "category",
            "inputs",
            "expected_outcome",
            "expected_properties",
            "tags",
            "timeout_ms",
        ),
        kind=field_name,
    )
    if errors:
        return errors
    prefix = "" if field_name == "runtime fixture" else f"{field_name}."
    for nested_field_name in ("scenario_id", "name", "description", "category", "expected_outcome"):
        errors.extend(
            _require_non_empty_text(
                payload[nested_field_name],
                field_name=f"{prefix}{nested_field_name}".strip("."),
                path=path,
            )
        )
    for nested_field_name in ("inputs", "expected_properties"):
        if not isinstance(payload[nested_field_name], dict):
            errors.append(
                f"{_relative_path(path)}: field '{f'{prefix}{nested_field_name}'.strip('.')}' must be an object"
            )
    tags = payload["tags"]
    tags_field_name = f"{prefix}tags".strip(".")
    if not isinstance(tags, list):
        errors.append(f"{_relative_path(path)}: field '{tags_field_name}' must be an array")
    else:
        for index, tag in enumerate(tags):
            errors.extend(_require_non_empty_text(tag, field_name=f"{tags_field_name}[{index}]", path=path))
    errors.extend(
        _require_positive_int(
            payload["timeout_ms"],
            field_name=f"{prefix}timeout_ms".strip("."),
            path=path,
        )
    )
    return errors


def _validate_benchmark_suite_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("suite_id", "name", "category", "scenarios", "version", "created_at"),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("suite_id", "name", "category", "version"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(_validate_iso8601_text(payload["created_at"], field_name="created_at", path=path))
    scenarios = payload["scenarios"]
    if not isinstance(scenarios, list) or not scenarios:
        errors.append(f"{_relative_path(path)}: field 'scenarios' must be a non-empty array")
    else:
        seen_scenario_ids: set[str] = set()
        for index, scenario in enumerate(scenarios):
            errors.extend(
                _validate_benchmark_scenario_dict(
                    scenario,
                    path=path,
                    field_name=f"scenarios[{index}]",
                )
            )
            if isinstance(scenario, dict) and isinstance(scenario.get("scenario_id"), str):
                scenario_id = scenario["scenario_id"]
                if scenario_id in seen_scenario_ids:
                    errors.append(
                        f"{_relative_path(path)}: scenarios must not repeat scenario_id '{scenario_id}'"
                    )
                seen_scenario_ids.add(scenario_id)
    return errors


def _validate_benchmark_metric_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    return _validate_benchmark_metric_dict(payload, path=path, field_name="runtime fixture")


def _validate_benchmark_metric_dict(payload: object, *, path: Path, field_name: str) -> list[str]:
    if not isinstance(payload, dict):
        return [f"{_relative_path(path)}: field '{field_name}' must be an object"]
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("metric_id", "kind", "name", "value", "threshold", "passed"),
        kind=field_name,
    )
    if errors:
        return errors
    prefix = "" if field_name == "runtime fixture" else f"{field_name}."
    for nested_field_name in ("metric_id", "kind", "name"):
        errors.extend(
            _require_non_empty_text(
                payload[nested_field_name],
                field_name=f"{prefix}{nested_field_name}".strip("."),
                path=path,
            )
        )
    for nested_field_name in ("value", "threshold"):
        errors.extend(
            _require_number_in_range(
                payload[nested_field_name],
                field_name=f"{prefix}{nested_field_name}".strip("."),
                path=path,
                minimum=0.0,
                maximum=1.0,
            )
        )
    passed_field_name = f"{prefix}passed".strip(".")
    if not isinstance(payload["passed"], bool):
        errors.append(f"{_relative_path(path)}: field '{passed_field_name}' must be boolean")
    elif (
        isinstance(payload["value"], (int, float))
        and not isinstance(payload["value"], bool)
        and isinstance(payload["threshold"], (int, float))
        and not isinstance(payload["threshold"], bool)
        and payload["passed"] != (payload["value"] >= payload["threshold"])
    ):
        errors.append(
            f"{_relative_path(path)}: {passed_field_name} must be true iff value >= threshold"
        )
    return errors


def _validate_benchmark_result_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    return _validate_benchmark_result_dict(payload, path=path, field_name="runtime fixture")


def _validate_benchmark_result_dict(payload: object, *, path: Path, field_name: str) -> list[str]:
    if not isinstance(payload, dict):
        return [f"{_relative_path(path)}: field '{field_name}' must be an object"]
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "result_id",
            "scenario_id",
            "outcome",
            "metrics",
            "actual_properties",
            "error_message",
            "duration_ms",
            "executed_at",
        ),
        kind=field_name,
    )
    if errors:
        return errors
    prefix = "" if field_name == "runtime fixture" else f"{field_name}."
    for nested_field_name in ("result_id", "scenario_id", "outcome"):
        errors.extend(
            _require_non_empty_text(
                payload[nested_field_name],
                field_name=f"{prefix}{nested_field_name}".strip("."),
                path=path,
            )
        )
    metrics = payload["metrics"]
    metrics_field_name = f"{prefix}metrics".strip(".")
    if not isinstance(metrics, list):
        errors.append(f"{_relative_path(path)}: field '{metrics_field_name}' must be an array")
    else:
        for index, metric in enumerate(metrics):
            errors.extend(
                _validate_benchmark_metric_dict(
                    metric,
                    path=path,
                    field_name=f"{metrics_field_name}[{index}]",
                )
            )
    actual_properties_field_name = f"{prefix}actual_properties".strip(".")
    if not isinstance(payload["actual_properties"], dict):
        errors.append(
            f"{_relative_path(path)}: field '{actual_properties_field_name}' must be an object"
        )
    error_message_field_name = f"{prefix}error_message".strip(".")
    if payload["error_message"] is not None and not isinstance(payload["error_message"], str):
        errors.append(f"{_relative_path(path)}: field '{error_message_field_name}' must be a string or null")
    errors.extend(
        _require_non_negative_int(
            payload["duration_ms"],
            field_name=f"{prefix}duration_ms".strip("."),
            path=path,
        )
    )
    errors.extend(
        _validate_iso8601_text(
            payload["executed_at"],
            field_name=f"{prefix}executed_at".strip("."),
            path=path,
        )
    )
    return errors


def _validate_benchmark_run_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("run_id", "suite_id", "results", "started_at", "finished_at", "metadata"),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("run_id", "suite_id"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    results = payload["results"]
    if not isinstance(results, list):
        errors.append(f"{_relative_path(path)}: field 'results' must be an array")
    else:
        for index, result in enumerate(results):
            errors.extend(
                _validate_benchmark_result_dict(
                    result,
                    path=path,
                    field_name=f"results[{index}]",
                )
            )
    for field_name in ("started_at", "finished_at"):
        errors.extend(_validate_iso8601_text(payload[field_name], field_name=field_name, path=path))
    if not isinstance(payload["metadata"], dict):
        errors.append(f"{_relative_path(path)}: field 'metadata' must be an object")
    return errors


def _validate_adversarial_case_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "case_id",
            "name",
            "description",
            "category",
            "severity",
            "target_subsystem",
            "attack_vector",
            "inputs",
            "expected_behavior",
            "tags",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in (
        "case_id",
        "name",
        "description",
        "category",
        "severity",
        "target_subsystem",
        "attack_vector",
        "expected_behavior",
    ):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if not isinstance(payload["inputs"], dict):
        errors.append(f"{_relative_path(path)}: field 'inputs' must be an object")
    tags = payload["tags"]
    if not isinstance(tags, list):
        errors.append(f"{_relative_path(path)}: field 'tags' must be an array")
    else:
        for index, tag in enumerate(tags):
            errors.extend(_require_non_empty_text(tag, field_name=f"tags[{index}]", path=path))
    return errors


def _validate_regression_record_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    return _validate_regression_record_dict(payload, path=path, field_name="runtime fixture")


def _validate_regression_record_dict(payload: object, *, path: Path, field_name: str) -> list[str]:
    if not isinstance(payload, dict):
        return [f"{_relative_path(path)}: field '{field_name}' must be an object"]
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "regression_id",
            "metric_name",
            "category",
            "baseline_value",
            "current_value",
            "direction",
            "delta",
            "baseline_run_id",
            "current_run_id",
            "detected_at",
        ),
        kind=field_name,
    )
    if errors:
        return errors
    prefix = "" if field_name == "runtime fixture" else f"{field_name}."
    for nested_field_name in (
        "regression_id",
        "metric_name",
        "category",
        "direction",
        "baseline_run_id",
        "current_run_id",
    ):
        errors.extend(
            _require_non_empty_text(
                payload[nested_field_name],
                field_name=f"{prefix}{nested_field_name}".strip("."),
                path=path,
            )
        )
    for nested_field_name in ("baseline_value", "current_value"):
        errors.extend(
            _require_number_in_range(
                payload[nested_field_name],
                field_name=f"{prefix}{nested_field_name}".strip("."),
                path=path,
                minimum=0.0,
                maximum=1.0,
            )
        )
    delta_field_name = f"{prefix}delta".strip(".")
    if isinstance(payload["delta"], bool) or not isinstance(payload["delta"], (int, float)):
        errors.append(f"{_relative_path(path)}: field '{delta_field_name}' must be numeric")
    errors.extend(
        _validate_iso8601_text(
            payload["detected_at"],
            field_name=f"{prefix}detected_at".strip("."),
            path=path,
        )
    )
    return errors


def _validate_capability_scorecard_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "scorecard_id",
            "category",
            "status",
            "pass_rate",
            "metric_count",
            "metrics_passing",
            "adversarial_pass_rate",
            "regressions",
            "confidence_trend",
            "assessed_at",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("scorecard_id", "category", "status", "confidence_trend"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    for field_name in ("pass_rate", "adversarial_pass_rate"):
        errors.extend(
            _require_number_in_range(
                payload[field_name],
                field_name=field_name,
                path=path,
                minimum=0.0,
                maximum=1.0,
            )
        )
    for field_name in ("metric_count", "metrics_passing"):
        errors.extend(_require_non_negative_int(payload[field_name], field_name=field_name, path=path))
    if (
        isinstance(payload["metric_count"], int)
        and not isinstance(payload["metric_count"], bool)
        and isinstance(payload["metrics_passing"], int)
        and not isinstance(payload["metrics_passing"], bool)
        and payload["metrics_passing"] > payload["metric_count"]
    ):
        errors.append(f"{_relative_path(path)}: metrics_passing cannot exceed metric_count")
    regressions = payload["regressions"]
    if not isinstance(regressions, list):
        errors.append(f"{_relative_path(path)}: field 'regressions' must be an array")
    else:
        for index, regression in enumerate(regressions):
            errors.extend(
                _validate_regression_record_dict(
                    regression,
                    path=path,
                    field_name=f"regressions[{index}]",
                )
            )
    errors.extend(_validate_iso8601_text(payload["assessed_at"], field_name="assessed_at", path=path))
    return errors


def _validate_resource_budget_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("resource_id", "resource_type", "total", "consumed", "reserved"),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("resource_id", "resource_type"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    for field_name in ("total", "consumed", "reserved"):
        errors.extend(_require_non_negative_float(payload[field_name], field_name=field_name, path=path))
    if (
        isinstance(payload["total"], (int, float))
        and isinstance(payload["consumed"], (int, float))
        and isinstance(payload["reserved"], (int, float))
        and not isinstance(payload["total"], bool)
        and not isinstance(payload["consumed"], bool)
        and not isinstance(payload["reserved"], bool)
        and payload["consumed"] + payload["reserved"] > payload["total"]
    ):
        errors.append(f"{_relative_path(path)}: consumed + reserved must not exceed total")
    return errors


def _validate_decision_factor_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    return _validate_decision_factor_dict(payload, path=path, field_name="runtime fixture")


def _validate_decision_factor_dict(payload: object, *, path: Path, field_name: str) -> list[str]:
    if not isinstance(payload, dict):
        return [f"{_relative_path(path)}: field '{field_name}' must be an object"]
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("factor_id", "kind", "weight", "value", "label"),
        kind=field_name,
    )
    if errors:
        return errors
    prefix = "" if field_name == "runtime fixture" else f"{field_name}."
    for nested_field_name in ("factor_id", "kind", "label"):
        errors.extend(
            _require_non_empty_text(
                payload[nested_field_name],
                field_name=f"{prefix}{nested_field_name}".strip("."),
                path=path,
            )
        )
    for nested_field_name in ("weight", "value"):
        errors.extend(
            _require_number_in_range(
                payload[nested_field_name],
                field_name=f"{prefix}{nested_field_name}".strip("."),
                path=path,
                minimum=0.0,
                maximum=1.0,
            )
        )
    return errors


def _validate_utility_profile_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "profile_id",
            "context_type",
            "context_id",
            "factors",
            "tradeoff_direction",
            "created_at",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("profile_id", "context_type", "context_id", "tradeoff_direction"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(_validate_iso8601_text(payload["created_at"], field_name="created_at", path=path))
    factors = payload["factors"]
    if not isinstance(factors, list) or not factors:
        errors.append(f"{_relative_path(path)}: field 'factors' must be a non-empty array")
    else:
        total_weight = 0.0
        for index, factor in enumerate(factors):
            errors.extend(
                _validate_decision_factor_dict(
                    factor,
                    path=path,
                    field_name=f"factors[{index}]",
                )
            )
            if (
                isinstance(factor, dict)
                and isinstance(factor.get("weight"), (int, float))
                and not isinstance(factor.get("weight"), bool)
            ):
                total_weight += float(factor["weight"])
        if total_weight <= 0.0:
            errors.append(f"{_relative_path(path)}: sum of factor weights must be greater than 0")
    return errors


def _validate_option_utility_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    return _validate_option_utility_dict(payload, path=path, field_name="runtime fixture")


def _validate_option_utility_dict(payload: object, *, path: Path, field_name: str) -> list[str]:
    if not isinstance(payload, dict):
        return [f"{_relative_path(path)}: field '{field_name}' must be an object"]
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=("option_id", "raw_score", "weighted_score", "factor_contributions", "rank"),
        kind=field_name,
    )
    if errors:
        return errors
    prefix = "" if field_name == "runtime fixture" else f"{field_name}."
    errors.extend(
        _require_non_empty_text(
            payload["option_id"],
            field_name=f"{prefix}option_id".strip("."),
            path=path,
        )
    )
    errors.extend(
        _require_number_in_range(
            payload["raw_score"],
            field_name=f"{prefix}raw_score".strip("."),
            path=path,
            minimum=0.0,
            maximum=1.0,
        )
    )
    errors.extend(
        _require_number_in_range(
            payload["weighted_score"],
            field_name=f"{prefix}weighted_score".strip("."),
            path=path,
            minimum=0.0,
            maximum=1.0,
        )
    )
    factor_contributions = payload["factor_contributions"]
    if not isinstance(factor_contributions, dict):
        factor_field_name = f"{prefix}factor_contributions".strip(".")
        errors.append(
            f"{_relative_path(path)}: field '{factor_field_name}' must be an object"
        )
    else:
        for factor_id, contribution in factor_contributions.items():
            if not isinstance(factor_id, str) or not factor_id.strip():
                errors.append(f"{_relative_path(path)}: factor_contributions keys must be non-empty strings")
                break
            if isinstance(contribution, bool) or not isinstance(contribution, (int, float)):
                errors.append(
                    f"{_relative_path(path)}: factor_contributions['{factor_id}'] must be numeric"
                )
    errors.extend(
        _require_positive_int(payload["rank"], field_name=f"{prefix}rank".strip("."), path=path)
    )
    return errors


def _validate_decision_comparison_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "comparison_id",
            "profile_id",
            "option_utilities",
            "best_option_id",
            "spread",
            "decided_at",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("comparison_id", "profile_id", "best_option_id"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(_require_non_negative_float(payload["spread"], field_name="spread", path=path))
    errors.extend(_validate_iso8601_text(payload["decided_at"], field_name="decided_at", path=path))
    option_utilities = payload["option_utilities"]
    if not isinstance(option_utilities, list) or not option_utilities:
        errors.append(f"{_relative_path(path)}: field 'option_utilities' must be a non-empty array")
    else:
        option_ids: set[str] = set()
        for index, option_utility in enumerate(option_utilities):
            errors.extend(
                _validate_option_utility_dict(
                    option_utility,
                    path=path,
                    field_name=f"option_utilities[{index}]",
                )
            )
            if isinstance(option_utility, dict) and isinstance(option_utility.get("option_id"), str):
                option_ids.add(option_utility["option_id"])
        if isinstance(payload["best_option_id"], str) and payload["best_option_id"] not in option_ids:
            errors.append(f"{_relative_path(path)}: best_option_id must reference an option in option_utilities")
    return errors


def _validate_tradeoff_record_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "tradeoff_id",
            "comparison_id",
            "chosen_option_id",
            "rejected_option_ids",
            "tradeoff_direction",
            "rationale",
            "recorded_at",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("tradeoff_id", "comparison_id", "chosen_option_id", "tradeoff_direction", "rationale"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(_validate_iso8601_text(payload["recorded_at"], field_name="recorded_at", path=path))
    rejected_option_ids = payload["rejected_option_ids"]
    if not isinstance(rejected_option_ids, list):
        errors.append(f"{_relative_path(path)}: field 'rejected_option_ids' must be an array")
    else:
        for index, option_id in enumerate(rejected_option_ids):
            errors.extend(
                _require_non_empty_text(option_id, field_name=f"rejected_option_ids[{index}]", path=path)
            )
    return errors


def _validate_decision_policy_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "policy_id",
            "name",
            "min_confidence",
            "max_risk_tolerance",
            "max_cost",
            "deadline_weight",
            "require_human_above_risk",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("policy_id", "name"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    for field_name in ("min_confidence", "max_risk_tolerance", "deadline_weight", "require_human_above_risk"):
        errors.extend(
            _require_number_in_range(
                payload[field_name],
                field_name=field_name,
                path=path,
                minimum=0.0,
                maximum=1.0,
            )
        )
    errors.extend(_require_non_negative_float(payload["max_cost"], field_name="max_cost", path=path))
    return errors


def _validate_utility_verdict_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "verdict_id",
            "comparison_id",
            "policy_id",
            "approved",
            "recommended_option_id",
            "confidence",
            "reasons",
            "decided_at",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("verdict_id", "comparison_id", "policy_id", "recommended_option_id"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    if not isinstance(payload["approved"], bool):
        errors.append(f"{_relative_path(path)}: field 'approved' must be boolean")
    errors.extend(
        _require_number_in_range(
            payload["confidence"],
            field_name="confidence",
            path=path,
            minimum=0.0,
            maximum=1.0,
        )
    )
    reasons = payload["reasons"]
    if not isinstance(reasons, list) or not reasons:
        errors.append(f"{_relative_path(path)}: field 'reasons' must be a non-empty array")
    else:
        for index, reason in enumerate(reasons):
            errors.extend(_require_non_empty_text(reason, field_name=f"reasons[{index}]", path=path))
    errors.extend(_validate_iso8601_text(payload["decided_at"], field_name="decided_at", path=path))
    return errors


def _validate_supervisor_policy_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "policy_id",
            "tick_interval_ms",
            "max_events_per_tick",
            "max_actions_per_tick",
            "backpressure_threshold",
            "livelock_repeat_threshold",
            "livelock_strategy",
            "heartbeat_every_n_ticks",
            "checkpoint_every_n_ticks",
            "max_consecutive_errors",
            "created_at",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    errors.extend(_require_non_empty_text(payload["policy_id"], field_name="policy_id", path=path))
    errors.extend(_require_non_empty_text(payload["livelock_strategy"], field_name="livelock_strategy", path=path))
    for field_name in (
        "tick_interval_ms",
        "max_events_per_tick",
        "max_actions_per_tick",
        "backpressure_threshold",
        "livelock_repeat_threshold",
        "heartbeat_every_n_ticks",
        "checkpoint_every_n_ticks",
        "max_consecutive_errors",
    ):
        errors.extend(_require_positive_int(payload[field_name], field_name=field_name, path=path))
    errors.extend(_validate_iso8601_text(payload["created_at"], field_name="created_at", path=path))
    return errors


def _validate_supervisor_health_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "health_id",
            "tick_number",
            "phase",
            "consecutive_errors",
            "consecutive_idle_ticks",
            "backpressure_active",
            "livelock_detected",
            "open_obligations",
            "pending_events",
            "overall_confidence",
            "assessed_at",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("health_id", "phase"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    for field_name in (
        "tick_number",
        "consecutive_errors",
        "consecutive_idle_ticks",
        "open_obligations",
        "pending_events",
    ):
        errors.extend(_require_non_negative_int(payload[field_name], field_name=field_name, path=path))
    for field_name in ("backpressure_active", "livelock_detected"):
        if not isinstance(payload[field_name], bool):
            errors.append(f"{_relative_path(path)}: field '{field_name}' must be boolean")
    errors.extend(
        _require_number_in_range(
            payload["overall_confidence"],
            field_name="overall_confidence",
            path=path,
            minimum=0.0,
            maximum=1.0,
        )
    )
    errors.extend(_validate_iso8601_text(payload["assessed_at"], field_name="assessed_at", path=path))
    return errors


def _validate_runtime_heartbeat_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "heartbeat_id",
            "tick_number",
            "phase",
            "outcome_of_last_tick",
            "open_obligations",
            "pending_events",
            "uptime_ticks",
            "emitted_at",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("heartbeat_id", "phase", "outcome_of_last_tick"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    for field_name in ("tick_number", "open_obligations", "pending_events", "uptime_ticks"):
        errors.extend(_require_non_negative_int(payload[field_name], field_name=field_name, path=path))
    errors.extend(_validate_iso8601_text(payload["emitted_at"], field_name="emitted_at", path=path))
    return errors


def _validate_supervisor_checkpoint_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "checkpoint_id",
            "tick_number",
            "phase",
            "status",
            "open_obligation_ids",
            "pending_event_count",
            "consecutive_errors",
            "consecutive_idle_ticks",
            "recent_tick_outcomes",
            "state_hash",
            "created_at",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("checkpoint_id", "phase", "status", "state_hash"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    for field_name in (
        "tick_number",
        "pending_event_count",
        "consecutive_errors",
        "consecutive_idle_ticks",
    ):
        errors.extend(_require_non_negative_int(payload[field_name], field_name=field_name, path=path))
    for list_name in ("open_obligation_ids", "recent_tick_outcomes"):
        values = payload[list_name]
        if not isinstance(values, list):
            errors.append(f"{_relative_path(path)}: field '{list_name}' must be an array")
        else:
            for index, value in enumerate(values):
                if not isinstance(value, str) or not value.strip():
                    errors.append(f"{_relative_path(path)}: {list_name}[{index}] must be a non-empty string")
    errors.extend(_validate_iso8601_text(payload["created_at"], field_name="created_at", path=path))
    return errors


def _validate_livelock_record_fixture(path: Path) -> list[str]:
    payload = _load_json_object(path, kind="MAF runtime fixture")
    errors = _validate_exact_object_fields(
        payload,
        path=path,
        expected_fields=(
            "livelock_id",
            "tick_number",
            "repeated_pattern",
            "repeat_count",
            "strategy_applied",
            "resolved",
            "detected_at",
            "resolution_detail",
        ),
        kind="runtime fixture",
    )
    if errors:
        return errors
    for field_name in ("livelock_id", "repeated_pattern", "strategy_applied"):
        errors.extend(_require_non_empty_text(payload[field_name], field_name=field_name, path=path))
    errors.extend(_require_non_negative_int(payload["tick_number"], field_name="tick_number", path=path))
    errors.extend(_require_positive_int(payload["repeat_count"], field_name="repeat_count", path=path))
    if not isinstance(payload["resolved"], bool):
        errors.append(f"{_relative_path(path)}: field 'resolved' must be boolean")
    errors.extend(_validate_iso8601_text(payload["detected_at"], field_name="detected_at", path=path))
    if not isinstance(payload["resolution_detail"], str):
        errors.append(f"{_relative_path(path)}: field 'resolution_detail' must be a string")
    return errors


MAF_RUNTIME_FIXTURE_VALIDATORS: dict[str, MAFRuntimeFixtureValidator] = {
    "adversarial_case.json": _validate_adversarial_case_fixture,
    "assignment_policy.json": _validate_assignment_policy_fixture,
    "assignment_decision.json": _validate_assignment_decision_fixture,
    "benchmark_metric.json": _validate_benchmark_metric_fixture,
    "benchmark_result.json": _validate_benchmark_result_fixture,
    "benchmark_run.json": _validate_benchmark_run_fixture,
    "benchmark_scenario.json": _validate_benchmark_scenario_fixture,
    "benchmark_suite.json": _validate_benchmark_suite_fixture,
    "causal_path.json": _validate_causal_path_fixture,
    "capability_scorecard.json": _validate_capability_scorecard_fixture,
    "decision_comparison.json": _validate_decision_comparison_fixture,
    "decision_factor.json": _validate_decision_factor_fixture,
    "decision_link.json": _validate_decision_link_fixture,
    "decision_policy.json": _validate_decision_policy_fixture,
    "evidence_link.json": _validate_evidence_link_fixture,
    "event_correlation.json": _validate_event_correlation_fixture,
    "event_envelope.json": _validate_event_envelope_fixture,
    "event_record.json": _validate_event_record_fixture,
    "event_reaction.json": _validate_event_reaction_fixture,
    "event_subscription.json": _validate_event_subscription_fixture,
    "event_window.json": _validate_event_window_fixture,
    "function_metrics_snapshot.json": _validate_function_metrics_snapshot_fixture,
    "function_outcome_record.json": _validate_function_outcome_record_fixture,
    "function_policy_binding.json": _validate_function_policy_binding_fixture,
    "function_queue_profile.json": _validate_function_queue_profile_fixture,
    "function_sla_profile.json": _validate_function_sla_profile_fixture,
    "handoff_record.json": _validate_handoff_record_fixture,
    "job_descriptor.json": _validate_job_descriptor_fixture,
    "livelock_record.json": _validate_livelock_record_fixture,
    "goal_plan.json": _validate_goal_plan_fixture,
    "graph_query_result.json": _validate_graph_query_result_fixture,
    "graph_snapshot.json": _validate_graph_snapshot_fixture,
    "obligation_closure.json": _validate_obligation_closure_fixture,
    "obligation_escalation.json": _validate_obligation_escalation_fixture,
    "obligation_link.json": _validate_obligation_link_fixture,
    "obligation_record.json": _validate_obligation_record_fixture,
    "obligation_transfer.json": _validate_obligation_transfer_fixture,
    "operational_edge.json": _validate_operational_edge_fixture,
    "operational_node.json": _validate_operational_node_fixture,
    "role_descriptor.json": _validate_role_descriptor_fixture,
    "runtime_heartbeat.json": _validate_runtime_heartbeat_fixture,
    "option_utility.json": _validate_option_utility_fixture,
    "resource_budget.json": _validate_resource_budget_fixture,
    "regression_record.json": _validate_regression_record_fixture,
    "service_function_template.json": _validate_service_function_template_fixture,
    "simulation_option.json": _validate_simulation_option_fixture,
    "simulation_outcome.json": _validate_simulation_outcome_fixture,
    "simulation_request.json": _validate_simulation_request_fixture,
    "simulation_comparison.json": _validate_simulation_comparison_fixture,
    "simulation_verdict.json": _validate_simulation_verdict_fixture,
    "supervisor_checkpoint.json": _validate_supervisor_checkpoint_fixture,
    "supervisor_health.json": _validate_supervisor_health_fixture,
    "supervisor_policy.json": _validate_supervisor_policy_fixture,
    "supervisor_tick.json": _validate_supervisor_tick_fixture,
    "state_delta.json": _validate_state_delta_fixture,
    "team_queue_state.json": _validate_team_queue_state_fixture,
    "tradeoff_record.json": _validate_tradeoff_record_fixture,
    "utility_profile.json": _validate_utility_profile_fixture,
    "utility_verdict.json": _validate_utility_verdict_fixture,
    "worker_profile.json": _validate_worker_profile_fixture,
    "worker_capacity.json": _validate_worker_capacity_fixture,
    "workload_snapshot.json": _validate_workload_snapshot_fixture,
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
