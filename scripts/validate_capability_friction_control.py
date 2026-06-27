#!/usr/bin/env python3
"""Validate the capability friction-control read model.

Purpose: prove the operator friction surface is a read-only projection of
governed capability records.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: gateway operator capability console projection, software-dev
capability pack, schema validator, and example read model.
Invariants:
  - Friction control is not execution authority.
  - Unlock levels and friction modes are deterministic.
  - Local lab readiness requires sandbox, receipt, rollback, and no-network
    boundaries.
  - Real-world effects remain disabled in Foundation Mode.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parent.parent
MCOI_ROOT = REPO_ROOT / "mcoi"
for import_root in (REPO_ROOT, MCOI_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from gateway.capability_fabric import build_software_dev_capability_admission_gate  # noqa: E402
from gateway.operator_capability_console import (  # noqa: E402
    build_capability_friction_control_read_model,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "capability_friction_control.schema.json"
DEFAULT_READ_MODEL = REPO_ROOT / "examples" / "capability_friction_control.foundation.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "capability_friction_control_validation.json"
EXPECTED_UNLOCK_LEVELS = tuple(f"L{index}" for index in range(10))
EXPECTED_FRICTION_MODES = ("strict", "balanced", "fast")
EXPECTED_SOFTWARE_DEV_CAPABILITIES = {
    "software_dev.repo_map.read",
    "software_dev.context_bundle.build",
    "software_dev.gate_plan.select",
    "software_dev.change.run",
    "software_dev.app_task_graph.plan",
    "software_dev.pr_candidate.prepare",
}
REQUIRED_VALIDATOR_COMMANDS = {
    "capability_friction_control_validator": "python scripts/validate_capability_friction_control.py",
    "capability_friction_control_tests": "python -m pytest tests/test_validate_capability_friction_control.py -q",
}
FORBIDDEN_CAPABILITY_FIELDS = {
    "extensions",
    "input_schema_ref",
    "output_schema_ref",
    "allowed_tools",
    "allowed_networks",
}


@dataclass(frozen=True, slots=True)
class CapabilityFrictionControlValidation:
    """Validation report for the capability friction-control read model."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    read_model_path: str
    capability_count: int
    fast_mode_lab_ready_count: int
    developer_workflow_status: str

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def build_default_capability_friction_control_read_model() -> dict[str, Any]:
    """Build the canonical Foundation Mode software-dev friction read model."""

    gate = build_software_dev_capability_admission_gate(
        clock=lambda: "2026-05-13T00:00:00+00:00",
        require_production_ready=False,
    )
    return build_capability_friction_control_read_model(
        capability_admission_gate=gate,
        domain="software_dev",
    )


def validate_capability_friction_control(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    read_model_path: Path = DEFAULT_READ_MODEL,
) -> CapabilityFrictionControlValidation:
    """Validate the friction-control example against schema and runtime state."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "capability friction-control schema", errors)
    read_model = _load_json_object(read_model_path, "capability friction-control read model", errors)
    runtime_model = build_default_capability_friction_control_read_model() if not errors else {}

    if schema and read_model:
        errors.extend(f"{_path_label(read_model_path)}: {error}" for error in _validate_schema_instance(schema, read_model))
        if read_model != runtime_model:
            errors.append(f"{_path_label(read_model_path)}: example does not match runtime projection")
    if read_model:
        _validate_read_model(read_model, runtime_model, errors, _path_label(read_model_path))

    summary = read_model.get("summary", {}) if isinstance(read_model, dict) else {}
    workflow = read_model.get("developer_workflow_v1", {}) if isinstance(read_model, dict) else {}
    return CapabilityFrictionControlValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        read_model_path=_path_label(read_model_path),
        capability_count=int(summary.get("capability_count", 0)) if isinstance(summary, dict) else 0,
        fast_mode_lab_ready_count=int(summary.get("fast_mode_lab_ready_count", 0)) if isinstance(summary, dict) else 0,
        developer_workflow_status=str(workflow.get("status", "")) if isinstance(workflow, dict) else "",
    )


def write_capability_friction_control_validation(
    validation: CapabilityFrictionControlValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic friction-control validation report."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def write_capability_friction_control_example(output_path: Path = DEFAULT_READ_MODEL) -> Path:
    """Write the canonical generated friction-control example."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            build_default_capability_friction_control_read_model(),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_read_model(
    read_model: dict[str, Any],
    runtime_model: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    if read_model.get("read_model_is_not_execution_authority") is not True:
        errors.append(f"{label}: read_model_is_not_execution_authority must be true")
    if read_model.get("live_execution_enabled") is not False:
        errors.append(f"{label}: live_execution_enabled must be false")
    if read_model.get("source_refs", {}).get("domain_filter") != "software_dev":
        errors.append(f"{label}: source_refs.domain_filter must be software_dev")
    _validate_unlock_levels(read_model, errors, label)
    _validate_friction_modes(read_model, errors, label)
    _validate_zones(read_model, errors, label)
    _validate_capabilities(read_model, errors, label)
    _validate_developer_workflow(read_model, errors, label)
    _validate_validators(read_model, errors, label)
    if runtime_model and read_model.get("summary") != runtime_model.get("summary"):
        errors.append(f"{label}: summary must match runtime projection")


def _validate_unlock_levels(read_model: Mapping[str, Any], errors: list[str], label: str) -> None:
    levels = read_model.get("unlock_levels")
    if not isinstance(levels, list):
        errors.append(f"{label}: unlock_levels must be a list")
        return
    observed = tuple(str(item.get("level", "")) for item in levels if isinstance(item, dict))
    if observed != EXPECTED_UNLOCK_LEVELS:
        errors.append(f"{label}: unlock_levels must be L0 through L9 in order")


def _validate_friction_modes(read_model: Mapping[str, Any], errors: list[str], label: str) -> None:
    modes = read_model.get("friction_modes")
    if not isinstance(modes, list):
        errors.append(f"{label}: friction_modes must be a list")
        return
    observed = tuple(str(item.get("mode", "")) for item in modes if isinstance(item, dict))
    if observed != EXPECTED_FRICTION_MODES:
        errors.append(f"{label}: friction_modes must be strict, balanced, fast")


def _validate_zones(read_model: Mapping[str, Any], errors: list[str], label: str) -> None:
    safe = read_model.get("safe_automatic_zones")
    dangerous = read_model.get("dangerous_zones")
    if not isinstance(safe, list) or not isinstance(dangerous, list):
        errors.append(f"{label}: safe_automatic_zones and dangerous_zones must be lists")
        return
    overlap = sorted(set(safe).intersection(dangerous))
    if overlap:
        errors.append(f"{label}: safe and dangerous zones overlap: {overlap}")
    if "write_tests" not in safe or "deploy" not in dangerous:
        errors.append(f"{label}: safe/dangerous zone anchors are missing")


def _validate_capabilities(read_model: Mapping[str, Any], errors: list[str], label: str) -> None:
    capabilities = _list_of_objects(read_model.get("capabilities"))
    summary = read_model.get("summary")
    if not isinstance(summary, Mapping):
        errors.append(f"{label}: summary must be an object")
        return
    capability_ids = {str(item.get("capability_id", "")) for item in capabilities}
    if capability_ids != EXPECTED_SOFTWARE_DEV_CAPABILITIES:
        errors.append(f"{label}: capabilities must match software_dev registry entries")
    if summary.get("capability_count") != len(capabilities):
        errors.append(f"{label}: summary.capability_count must match capability cards")
    if summary.get("fast_mode_lab_ready_count") != sum(
        1 for item in capabilities if item.get("fast_mode_admission") == "allowed_lab"
    ):
        errors.append(f"{label}: fast_mode_lab_ready_count must match capability cards")
    if summary.get("lab_mode_allowed_count") != sum(1 for item in capabilities if item.get("lab_mode_allowed") is True):
        errors.append(f"{label}: lab_mode_allowed_count must match capability cards")
    if summary.get("real_world_mode_allowed_count") != 0:
        errors.append(f"{label}: real_world_mode_allowed_count must remain zero in Foundation Mode")
    for card in capabilities:
        _validate_capability_card(card, errors, label)


def _validate_capability_card(card: Mapping[str, Any], errors: list[str], label: str) -> None:
    capability_id = str(card.get("capability_id", "<missing>"))
    forbidden = sorted(FORBIDDEN_CAPABILITY_FIELDS & set(card))
    if forbidden:
        errors.append(f"{label}: {capability_id} exposes internal fields {forbidden}")
    blocked_actions = card.get("blocked_actions")
    if not isinstance(blocked_actions, list):
        errors.append(f"{label}: {capability_id} blocked_actions must be a list")
        return
    if card.get("blocked_action_count") != len(blocked_actions):
        errors.append(f"{label}: {capability_id} blocked_action_count must match blocked_actions")
    if card.get("real_world_mode_allowed") is True:
        errors.append(f"{label}: {capability_id} cannot allow real-world mode in foundation example")
    if capability_id in {"software_dev.change.run", "software_dev.pr_candidate.prepare"}:
        if card.get("fast_mode_admission") != "allowed_lab":
            errors.append(f"{label}: {capability_id} must be fast-mode lab ready")
        if card.get("rollback_default") is not True:
            errors.append(f"{label}: {capability_id} must expose rollback_default")


def _validate_developer_workflow(read_model: Mapping[str, Any], errors: list[str], label: str) -> None:
    workflow = read_model.get("developer_workflow_v1")
    if not isinstance(workflow, Mapping):
        errors.append(f"{label}: developer_workflow_v1 must be an object")
        return
    if workflow.get("status") != "preflight_ready":
        errors.append(f"{label}: developer workflow must be preflight_ready")
    if workflow.get("lab_mode_allowed") is not True:
        errors.append(f"{label}: developer workflow must allow lab mode")
    if workflow.get("real_world_effects_allowed") is not False:
        errors.append(f"{label}: developer workflow must block real-world effects")
    if workflow.get("missing_capability_ids") != []:
        errors.append(f"{label}: developer workflow must not have missing capabilities")
    stages = _list_of_objects(workflow.get("stages"))
    stage_ids = [str(stage.get("stage_id", "")) for stage in stages]
    expected_stage_ids = [
        "request_intake",
        "repo_map",
        "context_bundle",
        "gate_plan",
        "sandbox_change",
        "test_run",
        "diff_review",
        "receipt_review",
        "operator_approval",
        "pr_candidate",
    ]
    if stage_ids != expected_stage_ids:
        errors.append(f"{label}: developer workflow stages are not in canonical order")
    if any(stage.get("verification_required") is not True for stage in stages):
        errors.append(f"{label}: every developer workflow stage must require verification")


def _validate_validators(read_model: Mapping[str, Any], errors: list[str], label: str) -> None:
    validators = read_model.get("validators")
    if not isinstance(validators, list):
        errors.append(f"{label}: validators must be a list")
        return
    by_id = {
        str(validator.get("validator_id", "")): validator
        for validator in validators
        if isinstance(validator, Mapping)
    }
    for validator_id, expected_command in REQUIRED_VALIDATOR_COMMANDS.items():
        validator = by_id.get(validator_id)
        if validator is None:
            errors.append(f"{label}: missing validator {validator_id}")
            continue
        if validator.get("command") != expected_command:
            errors.append(f"{label}: validator {validator_id} command must be {expected_command!r}")
        if validator.get("required_for_closure") is not True:
            errors.append(f"{label}: validator {validator_id} must be required_for_closure")


def _list_of_objects(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    if not path.exists():
        errors.append(f"{label} file missing: {_path_label(path)}")
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError):
        errors.append(f"{label} JSON parse failed")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{label} JSON root must be an object")
        return {}
    return payload


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse capability friction-control validation arguments."""

    parser = argparse.ArgumentParser(description="Validate capability friction-control read model.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--read-model", default=str(DEFAULT_READ_MODEL))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--refresh-example", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for friction-control validation."""

    args = parse_args(argv)
    if args.refresh_example:
        write_capability_friction_control_example(Path(args.read_model))
    validation = validate_capability_friction_control(
        schema_path=Path(args.schema),
        read_model_path=Path(args.read_model),
    )
    write_capability_friction_control_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("CAPABILITY FRICTION CONTROL VALID")
    else:
        print(f"CAPABILITY FRICTION CONTROL INVALID errors={list(validation.errors)}")
    return 0 if validation.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
