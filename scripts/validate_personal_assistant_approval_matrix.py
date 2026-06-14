#!/usr/bin/env python3
"""Validate the personal-assistant approval matrix and approval packet.

Purpose: keep P0-P5 approval requirements decidable before any assistant
skill can cross an effect boundary.
Governance scope: approval tier order, P3/P4/P5 explicit approval, P5
evidence requirements, blocked action coverage, overclaim denial, and schema
conformance for approval packets.
Dependencies: governance/personal_assistant_approval_matrix.yaml,
schemas/personal_assistant_approval.schema.json, and
examples/personal_assistant_approval_packet.json.
Invariants:
  - P4 and P5 actions require explicit approval.
  - P5 actions remain blocked without named evidence and rollback or
    compensation references.
  - Public/customer/deployment/live-memory overclaims are false by default.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_schemas import _validate_schema_instance  # noqa: E402

DEFAULT_MATRIX = REPO_ROOT / "governance" / "personal_assistant_approval_matrix.yaml"
DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "personal_assistant_approval.schema.json"
DEFAULT_APPROVAL = REPO_ROOT / "examples" / "personal_assistant_approval_packet.json"

EXPECTED_RISK_LEVELS = ("P0", "P1", "P2", "P3", "P4", "P5")
APPROVAL_REQUIRED_LEVELS = frozenset({"P3", "P4", "P5"})
REQUIRED_BLOCKED_ACTIONS = frozenset(
    {
        "send",
        "delete",
        "archive",
        "forward",
        "create_event",
        "invite_people",
        "message_person",
        "public_post",
        "deploy_service",
        "pay_invoice",
        "publish",
        "connector_mutation",
        "system_of_record_write",
        "live_nested_mind_activation",
    }
)
REQUIRED_P5_EVIDENCE = frozenset(
    {
        "operator_approval_ref",
        "uao_admission_ref",
        "receipt_ref",
        "rollback_or_compensation_ref",
        "named_witness_ref",
    }
)


@dataclass(frozen=True, slots=True)
class PersonalAssistantApprovalMatrixValidation:
    """Validation result for the personal-assistant approval matrix."""

    valid: bool
    matrix_path: str
    approval_path: str
    risk_levels: tuple[str, ...]
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        rendered = asdict(self)
        rendered["risk_levels"] = list(self.risk_levels)
        rendered["errors"] = list(self.errors)
        return rendered


def validate_personal_assistant_approval_matrix(
    *,
    matrix_path: Path = DEFAULT_MATRIX,
    schema_path: Path = DEFAULT_SCHEMA,
    approval_path: Path = DEFAULT_APPROVAL,
) -> PersonalAssistantApprovalMatrixValidation:
    """Validate the approval matrix and representative approval packet."""
    errors: list[str] = []
    matrix = _load_json_object(matrix_path, "personal-assistant approval matrix", errors)
    schema = _load_json_object(schema_path, "personal-assistant approval schema", errors)
    approval = _load_json_object(approval_path, "personal-assistant approval packet", errors)
    if matrix:
        _validate_matrix_semantics(matrix, errors)
    if schema and approval:
        errors.extend(f"approval packet: {message}" for message in _validate_schema_instance(schema, approval))
        _validate_approval_packet_semantics(approval, errors)
    return _result(matrix_path=matrix_path, approval_path=approval_path, matrix=matrix, errors=errors)


def _validate_matrix_semantics(matrix: dict[str, Any], errors: list[str]) -> None:
    risk_entries = matrix.get("risk_levels", [])
    if not isinstance(risk_entries, list):
        errors.append("risk_levels must be a list")
        return
    levels = tuple(str(entry.get("level", "")) for entry in risk_entries if isinstance(entry, dict))
    if levels != EXPECTED_RISK_LEVELS:
        errors.append(f"risk_levels must be ordered {EXPECTED_RISK_LEVELS}")

    for entry in risk_entries:
        if not isinstance(entry, dict):
            errors.append("risk level entries must be objects")
            continue
        level = str(entry.get("level", ""))
        if level in APPROVAL_REQUIRED_LEVELS and entry.get("explicit_approval_required") is not True:
            errors.append(f"{level}: explicit_approval_required must be true")
        if level in APPROVAL_REQUIRED_LEVELS and entry.get("effect_bearing") is not True:
            errors.append(f"{level}: effect_bearing must be true")
        if level in {"P0", "P1", "P2"} and entry.get("explicit_approval_required") is True:
            errors.append(f"{level}: explicit approval must not be required by default")

    blocked = set(_string_list(matrix, "blocked_without_approval"))
    missing_blocked = sorted(REQUIRED_BLOCKED_ACTIONS - blocked)
    if missing_blocked:
        errors.append(f"blocked_without_approval missing required actions {missing_blocked}")

    action_classification = matrix.get("action_classification", {})
    if not isinstance(action_classification, dict):
        errors.append("action_classification must be an object")
    else:
        invalid_levels = sorted(
            f"{action}:{level}"
            for action, level in action_classification.items()
            if level not in EXPECTED_RISK_LEVELS
        )
        if invalid_levels:
            errors.append(f"action_classification has invalid levels {invalid_levels}")
        for action, level in action_classification.items():
            if level in APPROVAL_REQUIRED_LEVELS and _canonical_blocked_action(action) not in blocked:
                errors.append(f"{action}: {level} action must be blocked without approval")

    overclaim_blocks = matrix.get("overclaim_blocks", {})
    if not isinstance(overclaim_blocks, dict):
        errors.append("overclaim_blocks must be an object")
    else:
        for flag_name, flag_value in overclaim_blocks.items():
            if flag_value is not False:
                errors.append(f"overclaim_blocks.{flag_name} must be false")

    p5_evidence = set(_string_list(matrix, "required_evidence_for_p5"))
    missing_evidence = sorted(REQUIRED_P5_EVIDENCE - p5_evidence)
    if missing_evidence:
        errors.append(f"required_evidence_for_p5 missing {missing_evidence}")


def _validate_approval_packet_semantics(approval: dict[str, Any], errors: list[str]) -> None:
    risk_level = str(approval.get("risk_level", ""))
    if risk_level in APPROVAL_REQUIRED_LEVELS and approval.get("explicit_approval_required") is not True:
        errors.append(f"approval packet {risk_level}: explicit_approval_required must be true")
    proposed_actions = approval.get("proposed_actions", [])
    if not isinstance(proposed_actions, list) or not proposed_actions:
        errors.append("approval packet proposed_actions must be non-empty")
        return
    for action in proposed_actions:
        if not isinstance(action, dict):
            errors.append("approval packet proposed_actions entries must be objects")
            continue
        action_level = str(action.get("risk_level", ""))
        if action_level in APPROVAL_REQUIRED_LEVELS and approval.get("approval_state") == "not_required":
            errors.append(f"{action.get('action_id', '<unknown-action>')}: approval_state cannot be not_required")


def _canonical_blocked_action(action_name: str) -> str:
    mapping = {
        "send_email": "send",
        "create_calendar_event": "create_event",
        "invite_people": "invite_people",
        "write_task": "system_of_record_write",
        "publish_public_page": "publish",
        "deploy_service": "deploy_service",
        "pay_invoice": "pay_invoice",
        "activate_nested_mind_live": "live_nested_mind_activation",
    }
    return mapping.get(action_name, action_name)


def _result(
    *,
    matrix_path: Path,
    approval_path: Path,
    matrix: dict[str, Any],
    errors: list[str],
) -> PersonalAssistantApprovalMatrixValidation:
    risk_entries = matrix.get("risk_levels", []) if isinstance(matrix, dict) else []
    risk_levels = tuple(str(entry.get("level", "")) for entry in risk_entries if isinstance(entry, dict))
    return PersonalAssistantApprovalMatrixValidation(
        valid=not errors,
        matrix_path=_path_label(matrix_path),
        approval_path=_path_label(approval_path),
        risk_levels=risk_levels,
        errors=tuple(errors),
    )


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        errors.append(f"{label} could not be read")
        return {}
    except json.JSONDecodeError:
        errors.append(f"{label} must be JSON-compatible YAML")
        return {}
    if not isinstance(parsed, dict):
        errors.append(f"{label} root must be an object")
        return {}
    return parsed


def _string_list(payload: dict[str, Any], field_name: str) -> tuple[str, ...]:
    values = payload.get(field_name, ())
    return tuple(value for value in values if isinstance(value, str)) if isinstance(values, list) else ()


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse personal-assistant approval validation arguments."""
    parser = argparse.ArgumentParser(description="Validate personal-assistant approval matrix.")
    parser.add_argument("--matrix", default=str(DEFAULT_MATRIX))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--approval", default=str(DEFAULT_APPROVAL))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for personal-assistant approval matrix validation."""
    args = parse_args(argv)
    result = validate_personal_assistant_approval_matrix(
        matrix_path=Path(args.matrix),
        schema_path=Path(args.schema),
        approval_path=Path(args.approval),
    )
    if args.json:
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    elif result.valid:
        print(f"personal-assistant approval matrix ok levels={','.join(result.risk_levels)}")
    else:
        for error in result.errors:
            print(f"error: {error}")
    return 0 if result.valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
