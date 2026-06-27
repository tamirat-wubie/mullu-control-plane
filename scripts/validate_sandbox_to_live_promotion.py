#!/usr/bin/env python3
"""Validate sandbox-to-live promotion paths.

Purpose: prove governed capabilities use a reusable ordered promotion path
instead of jumping from demo evidence directly to live action.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/sandbox_to_live_promotion.schema.json,
examples/sandbox_to_live_promotion.foundation.json, capability passports, gate
template registry, and evidence passports.
Invariants:
  - Every capability passport has exactly one promotion path.
  - Promotion paths are read models and never execution authority.
  - Foundation mode keeps pilot, live, approved-live, and production stages blocked.
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

from mcoi_runtime.app.capability_passports import build_capability_passports  # noqa: E402
from mcoi_runtime.app.sandbox_to_live_promotion import (  # noqa: E402
    STAGE_ORDER,
    build_sandbox_to_live_promotion_paths,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "sandbox_to_live_promotion.schema.json"
DEFAULT_PROMOTION_PATHS = REPO_ROOT / "examples" / "sandbox_to_live_promotion.foundation.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "sandbox_to_live_promotion_validation.json"

REQUIRED_VALIDATOR_COMMANDS = {
    "sandbox_to_live_promotion_validator": "python scripts/validate_sandbox_to_live_promotion.py",
    "sandbox_to_live_promotion_tests": "python -m pytest tests/test_validate_sandbox_to_live_promotion.py -q",
}
LIVE_STAGE_IDS = {"pilot", "limited_live", "approved_live", "production"}


@dataclass(frozen=True, slots=True)
class SandboxToLivePromotionValidation:
    """Validation report for sandbox-to-live promotion paths."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    promotion_paths_path: str
    promotion_path_count: int
    capability_count: int
    blocked_path_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_sandbox_to_live_promotion(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    promotion_paths_path: Path = DEFAULT_PROMOTION_PATHS,
) -> SandboxToLivePromotionValidation:
    """Validate promotion paths against schema and runtime projections."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "sandbox-to-live promotion schema", errors)
    promotion_paths = _load_json_object(promotion_paths_path, "sandbox-to-live promotion example", errors)
    runtime_promotion_paths = build_sandbox_to_live_promotion_paths() if not errors else {}
    runtime_passports = build_capability_passports() if not errors else {}

    if schema and promotion_paths:
        errors.extend(
            f"{_path_label(promotion_paths_path)}: {error}"
            for error in _validate_schema_instance(schema, promotion_paths)
        )
        if promotion_paths != runtime_promotion_paths:
            errors.append(f"{_path_label(promotion_paths_path)}: example does not match runtime projection")
    if promotion_paths:
        _validate_promotion_path_set(promotion_paths, runtime_passports, errors, _path_label(promotion_paths_path))

    summary = promotion_paths.get("summary", {}) if isinstance(promotion_paths, dict) else {}
    entries = promotion_paths.get("promotion_paths", ()) if isinstance(promotion_paths, dict) else ()
    runtime_entries = runtime_passports.get("passports", ()) if isinstance(runtime_passports, dict) else ()
    return SandboxToLivePromotionValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        promotion_paths_path=_path_label(promotion_paths_path),
        promotion_path_count=len(entries) if isinstance(entries, list) else 0,
        capability_count=len(runtime_entries) if isinstance(runtime_entries, list) else 0,
        blocked_path_count=int(summary.get("blocked_path_count", 0)) if isinstance(summary, dict) else 0,
    )


def write_sandbox_to_live_promotion_validation(
    validation: SandboxToLivePromotionValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic sandbox-to-live promotion validation report."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_promotion_path_set(
    promotion_paths: dict[str, Any],
    runtime_passports: dict[str, Any],
    errors: list[str],
    label: str,
) -> None:
    if promotion_paths.get("promotion_path_set_is_not_execution_authority") is not True:
        errors.append(f"{label}: promotion_path_set_is_not_execution_authority must be true")
    if promotion_paths.get("live_execution_enabled") is not False:
        errors.append(f"{label}: live_execution_enabled must be false")
    if tuple(promotion_paths.get("stage_order", ())) != STAGE_ORDER:
        errors.append(f"{label}: stage_order must match canonical sandbox-to-live sequence")
    _validate_validators(promotion_paths, errors, label)

    path_entries = _list_of_objects(promotion_paths.get("promotion_paths"))
    passport_entries = _list_of_objects(runtime_passports.get("passports"))
    path_by_capability: dict[str, dict[str, Any]] = {}
    for path in path_entries:
        capability_id = str(path.get("capability_id", ""))
        if capability_id in path_by_capability:
            errors.append(f"{label}: duplicate promotion path for {capability_id}")
        path_by_capability[capability_id] = path
        _validate_promotion_path(path, errors, label)

    passport_ids = {str(passport.get("capability_id", "")) for passport in passport_entries}
    path_ids = set(path_by_capability)
    missing = sorted(passport_ids - path_ids)
    extra = sorted(path_ids - passport_ids)
    if missing:
        errors.append(f"{label}: registered capabilities missing promotion paths {missing}")
    if extra:
        errors.append(f"{label}: promotion paths for unknown capabilities {extra}")
    _validate_summary(promotion_paths, path_entries, passport_entries, errors, label)


def _validate_promotion_path(path: dict[str, Any], errors: list[str], label: str) -> None:
    capability_id = str(path.get("capability_id", "<missing>"))
    if path.get("promotion_path_is_not_execution_authority") is not True:
        errors.append(f"{label}: {capability_id} promotion_path_is_not_execution_authority must be true")
    if path.get("live_action_enabled") is not False:
        errors.append(f"{label}: {capability_id} live_action_enabled must be false")
    if path.get("stage_count") != len(STAGE_ORDER):
        errors.append(f"{label}: {capability_id} stage_count must be {len(STAGE_ORDER)}")
    current_stage = str(path.get("current_stage", ""))
    next_stage = str(path.get("next_stage", ""))
    if current_stage in STAGE_ORDER and next_stage in STAGE_ORDER:
        if STAGE_ORDER.index(next_stage) < STAGE_ORDER.index(current_stage):
            errors.append(f"{label}: {capability_id} next_stage cannot precede current_stage")
    stages = _list_of_objects(path.get("stages"))
    if tuple(stage.get("stage_id") for stage in stages) != STAGE_ORDER:
        errors.append(f"{label}: {capability_id} stages must preserve canonical order")
    if [stage.get("sequence") for stage in stages] != list(range(1, len(STAGE_ORDER) + 1)):
        errors.append(f"{label}: {capability_id} stages must preserve sequence 1..8")

    current_count = sum(1 for stage in stages if stage.get("stage_status") == "current")
    if current_count != 1:
        errors.append(f"{label}: {capability_id} must have exactly one current stage")
    blocked_stage_ids = _string_list(path.get("blocked_stage_ids"))
    projected_blocked = [str(stage.get("stage_id")) for stage in stages if stage.get("stage_status") == "blocked"]
    if blocked_stage_ids != projected_blocked:
        errors.append(f"{label}: {capability_id} blocked_stage_ids must match blocked stages")
    if path.get("promotion_blocked") != bool(blocked_stage_ids):
        errors.append(f"{label}: {capability_id} promotion_blocked must match blocked_stage_ids")
    for stage in stages:
        _validate_stage(stage, current_stage, capability_id, errors, label)


def _validate_stage(
    stage: Mapping[str, Any],
    current_stage: str,
    capability_id: str,
    errors: list[str],
    label: str,
) -> None:
    stage_id = str(stage.get("stage_id", ""))
    if stage.get("live_execution_allowed") is not False:
        errors.append(f"{label}: {capability_id} {stage_id} live_execution_allowed must be false")
    if stage_id in LIVE_STAGE_IDS and stage.get("stage_status") == "complete":
        errors.append(f"{label}: {capability_id} live stage {stage_id} cannot be complete in foundation mode")
    if stage_id == current_stage and stage.get("stage_status") != "current":
        errors.append(f"{label}: {capability_id} current stage {current_stage} must be marked current")
    if stage.get("stage_status") == "blocked" and not _string_list(stage.get("missing_controls")):
        errors.append(f"{label}: {capability_id} blocked stage {stage_id} requires missing controls")


def _validate_summary(
    promotion_paths: Mapping[str, Any],
    path_entries: list[dict[str, Any]],
    passport_entries: list[dict[str, Any]],
    errors: list[str],
    label: str,
) -> None:
    summary = promotion_paths.get("summary")
    if not isinstance(summary, dict):
        errors.append(f"{label}: summary must be an object")
        return
    if summary.get("capability_count") != len(passport_entries):
        errors.append(f"{label}: summary.capability_count must match runtime capabilities")
    if summary.get("promotion_path_count") != len(path_entries):
        errors.append(f"{label}: summary.promotion_path_count must match promotion paths")
    expected_stage_counts = {
        stage: sum(1 for path in path_entries if path.get("current_stage") == stage)
        for stage in STAGE_ORDER
    }
    if summary.get("current_stage_counts") != expected_stage_counts:
        errors.append(f"{label}: summary.current_stage_counts must match promotion paths")
    if summary.get("blocked_path_count") != sum(1 for path in path_entries if path.get("promotion_blocked")):
        errors.append(f"{label}: summary.blocked_path_count must match promotion paths")
    if summary.get("live_action_enabled_count") != 0:
        errors.append(f"{label}: summary.live_action_enabled_count must be zero")
    if summary.get("production_stage_count") != 0:
        errors.append(f"{label}: summary.production_stage_count must be zero")


def _validate_validators(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    validators = payload.get("validators")
    if not isinstance(validators, list):
        errors.append(f"{label}: validators must be a list")
        return
    validator_by_id = {
        str(validator.get("validator_id", "")): validator
        for validator in validators
        if isinstance(validator, dict)
    }
    for validator_id, expected_command in REQUIRED_VALIDATOR_COMMANDS.items():
        validator = validator_by_id.get(validator_id)
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


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, str)]


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
    """Parse sandbox-to-live promotion validation arguments."""

    parser = argparse.ArgumentParser(description="Validate sandbox-to-live promotion paths.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--promotion-paths", default=str(DEFAULT_PROMOTION_PATHS))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for sandbox-to-live promotion validation."""

    args = parse_args(argv)
    validation = validate_sandbox_to_live_promotion(
        schema_path=Path(args.schema),
        promotion_paths_path=Path(args.promotion_paths),
    )
    write_sandbox_to_live_promotion_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("SANDBOX TO LIVE PROMOTION VALID")
    else:
        print(f"SANDBOX TO LIVE PROMOTION INVALID errors={list(validation.errors)}")
    return 0 if validation.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
