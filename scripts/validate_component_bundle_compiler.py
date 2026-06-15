#!/usr/bin/env python3
"""Validate Component Harness bundle compilation artifacts.

Purpose: prove bundle compilation is schema-valid, deterministic from the
registry/read-model/simulation sources, and denied live authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/component_bundle_compilation.schema.json,
examples/component_bundle_compilation.personal_assistant_v0.json,
mcoi_runtime.app.component_bundle_compiler, and component harness validators.
Invariants:
  - The example payload equals the runtime compilation.
  - Every foundation bundle compiles from registered components only.
  - Terminal closure, connector calls, mutation, and execution remain blocked.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sys
from typing import Any, Sequence


REPO_ROOT = Path(__file__).resolve().parent.parent
MCOI_ROOT = REPO_ROOT / "mcoi"
for import_root in (REPO_ROOT, MCOI_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from mcoi_runtime.app.component_bundle_compiler import (  # noqa: E402
    compile_component_bundle,
    compile_foundation_component_bundles,
)
from scripts.validate_component_read_model import validate_component_read_model  # noqa: E402
from scripts.validate_component_registry import validate_component_registry  # noqa: E402
from scripts.validate_component_request_simulation import validate_component_request_simulation  # noqa: E402
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "component_bundle_compilation.schema.json"
DEFAULT_EXAMPLE = REPO_ROOT / "examples" / "component_bundle_compilation.personal_assistant_v0.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "component_bundle_compiler_validation.json"


@dataclass(frozen=True, slots=True)
class ComponentBundleCompilerValidation:
    """Schema and semantic validation report for bundle compilation."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_path: str
    bundle_count: int
    blocked_bundle_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_component_bundle_compiler(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_path: Path = DEFAULT_EXAMPLE,
) -> ComponentBundleCompilerValidation:
    """Validate bundle compiler schema, example, and foundation reports."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "component bundle compilation schema", errors)
    example = _load_json_object(example_path, "component bundle compilation example", errors)

    registry_validation = validate_component_registry()
    if not registry_validation.ok:
        errors.extend(f"component registry validation failed: {error}" for error in registry_validation.errors)
    read_model_validation = validate_component_read_model()
    if not read_model_validation.ok:
        errors.extend(f"component read model validation failed: {error}" for error in read_model_validation.errors)
    simulation_validation = validate_component_request_simulation()
    if not simulation_validation.ok:
        errors.extend(
            f"component request simulation validation failed: {error}"
            for error in simulation_validation.errors
        )

    expected_example = (
        compile_component_bundle(str(example.get("bundle_id", "")))
        if example
        else {}
    )
    bundle_reports = compile_foundation_component_bundles()

    if schema and example:
        errors.extend(
            f"{_path_label(example_path)}: {error}"
            for error in _validate_schema_instance(schema, example)
        )
        if example != expected_example:
            errors.append(f"{_path_label(example_path)}: example does not match runtime compilation")
        _validate_bundle_semantics(example, errors, _path_label(example_path))

    for index, report in enumerate(bundle_reports):
        _validate_bundle_semantics(report, errors, f"foundation bundle compilation {index}")

    return ComponentBundleCompilerValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_path=_path_label(example_path),
        bundle_count=len(bundle_reports),
        blocked_bundle_count=sum(1 for report in bundle_reports if report.get("outcome") == "GovernanceBlocked"),
    )


def write_component_bundle_compiler_validation(
    validation: ComponentBundleCompilerValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic bundle compiler validation report."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_bundle_semantics(
    report: dict[str, Any],
    errors: list[str],
    label: str,
) -> None:
    if report.get("governed") is not True:
        errors.append(f"{label}: governed must be true")
    if report.get("compiler_is_not_execution_authority") is not True:
        errors.append(f"{label}: compiler must not be execution authority")
    if report.get("bundle_is_not_execution_route") is not True:
        errors.append(f"{label}: bundle must not be execution route")
    for flag_name in (
        "live_execution_enabled",
        "live_connector_send_enabled",
        "can_execute",
        "can_mutate",
        "can_call_connector",
        "can_claim_terminal_closure",
    ):
        if report.get(flag_name) is not False:
            errors.append(f"{label}: {flag_name} must be false")
    if report.get("terminal_closure_required") is not True:
        errors.append(f"{label}: terminal_closure_required must be true")

    component_ids = _string_list(report.get("component_ids"))
    component_states = report.get("component_states")
    if not component_ids:
        errors.append(f"{label}: component_ids must not be empty")
    if not isinstance(component_states, list) or len(component_states) != len(component_ids):
        errors.append(f"{label}: component_states must match component_ids")
    else:
        state_ids = [str(state.get("component_id")) for state in component_states if isinstance(state, dict)]
        if state_ids != component_ids:
            errors.append(f"{label}: component_states order must match component_ids")

    summary = report.get("summary")
    if not isinstance(summary, dict):
        errors.append(f"{label}: summary must be an object")
    else:
        if summary.get("component_count") != len(component_ids):
            errors.append(f"{label}: summary.component_count must match component_ids")
        if summary.get("preview_available") is not True:
            errors.append(f"{label}: preview_available must be true")
        if summary.get("live_action_ready") is not False:
            errors.append(f"{label}: live_action_ready must be false")

    blocked_actions = _string_list(report.get("blocked_actions"))
    if "terminal_closure" not in blocked_actions:
        errors.append(f"{label}: blocked_actions must include terminal_closure")
    if not _string_list(report.get("expected_receipts")):
        errors.append(f"{label}: expected_receipts must not be empty")
    forbidden_claims = _string_list(report.get("forbidden_claims"))
    for forbidden_claim in ("production_ready", "customer_ready", "live_gmail_enabled", "autonomous_execution"):
        if forbidden_claim not in forbidden_claims:
            errors.append(f"{label}: forbidden_claims must include {forbidden_claim}")
    if report.get("outcome") not in {"AwaitingEvidence", "GovernanceBlocked", "SolvedUnverified"}:
        errors.append(f"{label}: outcome is not a governed solver outcome")


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


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse component bundle compiler validation arguments."""

    parser = argparse.ArgumentParser(description="Validate Component Harness bundle compiler.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--example", default=str(DEFAULT_EXAMPLE))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for component bundle compiler validation."""

    args = parse_args(argv)
    validation = validate_component_bundle_compiler(
        schema_path=Path(args.schema),
        example_path=Path(args.example),
    )
    write_component_bundle_compiler_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("COMPONENT BUNDLE COMPILER VALID")
    else:
        print(f"COMPONENT BUNDLE COMPILER INVALID errors={list(validation.errors)}")
    return 0 if validation.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
