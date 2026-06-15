#!/usr/bin/env python3
"""Validate Component Harness request simulation artifacts.

Purpose: prove request simulation is schema-valid, deterministic from the
read model, and denied live authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/component_request_simulation.schema.json,
examples/component_request_simulation.foundation.json,
mcoi_runtime.app.component_request_simulator, and component read-model
validation.
Invariants:
  - The example payload equals the runtime projection.
  - Every built-in scenario is preview-only and references registered
    components.
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

from mcoi_runtime.app.component_read_model import build_component_read_model  # noqa: E402
from mcoi_runtime.app.component_request_simulator import (  # noqa: E402
    SIMULATION_ROUTE,
    foundation_component_request_simulations,
    simulate_component_request,
)
from scripts.validate_component_read_model import validate_component_read_model  # noqa: E402
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "component_request_simulation.schema.json"
DEFAULT_EXAMPLE = REPO_ROOT / "examples" / "component_request_simulation.foundation.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "component_request_simulation_validation.json"


@dataclass(frozen=True, slots=True)
class ComponentRequestSimulationValidation:
    """Schema and semantic validation report for request simulation."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_path: str
    scenario_count: int
    blocked_scenario_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_component_request_simulation(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_path: Path = DEFAULT_EXAMPLE,
) -> ComponentRequestSimulationValidation:
    """Validate request simulation schema, example, and built-in scenarios."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "component request simulation schema", errors)
    example = _load_json_object(example_path, "component request simulation example", errors)

    read_model_validation = validate_component_read_model()
    if not read_model_validation.ok:
        errors.extend(
            f"component read model validation failed: {error}"
            for error in read_model_validation.errors
        )

    read_model = build_component_read_model()
    expected_example = simulate_component_request(str(example.get("request_text", "")), read_model=read_model) if example else {}
    scenarios = foundation_component_request_simulations()

    if schema and example:
        errors.extend(
            f"{_path_label(example_path)}: {error}"
            for error in _validate_schema_instance(schema, example)
        )
        if example != expected_example:
            errors.append(f"{_path_label(example_path)}: example does not match runtime projection")
        _validate_simulation_semantics(
            simulation=example,
            read_model=read_model,
            errors=errors,
            label=_path_label(example_path),
        )

    for index, scenario in enumerate(scenarios):
        _validate_simulation_semantics(
            simulation=scenario,
            read_model=read_model,
            errors=errors,
            label=f"foundation scenario {index}",
        )

    return ComponentRequestSimulationValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_path=_path_label(example_path),
        scenario_count=len(scenarios),
        blocked_scenario_count=sum(1 for scenario in scenarios if scenario.get("outcome") == "GovernanceBlocked"),
    )


def write_component_request_simulation_validation(
    validation: ComponentRequestSimulationValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic request simulation validation report."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_simulation_semantics(
    *,
    simulation: dict[str, Any],
    read_model: dict[str, Any],
    errors: list[str],
    label: str,
) -> None:
    component_ids = _component_ids(read_model)
    if simulation.get("route") != SIMULATION_ROUTE:
        errors.append(f"{label}: route must be {SIMULATION_ROUTE}")
    if simulation.get("governed") is not True:
        errors.append(f"{label}: governed must be true")
    if simulation.get("simulation_is_not_execution_authority") is not True:
        errors.append(f"{label}: simulation must not be execution authority")
    for flag_name in (
        "live_execution_enabled",
        "can_execute",
        "can_mutate",
        "can_call_connector",
        "can_claim_terminal_closure",
    ):
        if simulation.get(flag_name) is not False:
            errors.append(f"{label}: {flag_name} must be false")
    if simulation.get("terminal_closure_required") is not True:
        errors.append(f"{label}: terminal_closure_required must be true")

    selected_component_ids = _string_list(simulation.get("selected_component_ids"))
    blocked_component_ids = _string_list(simulation.get("blocked_component_ids"))
    missing_selected = sorted(set(selected_component_ids) - component_ids)
    missing_blocked = sorted(set(blocked_component_ids) - component_ids)
    if missing_selected:
        errors.append(f"{label}: selected components are not registered {missing_selected}")
    if missing_blocked:
        errors.append(f"{label}: blocked components are not registered {missing_blocked}")
    if not set(blocked_component_ids).issubset(set(selected_component_ids)):
        errors.append(f"{label}: blocked components must be selected components")

    blocked_actions = _string_list(simulation.get("blocked_actions"))
    if "terminal_closure" not in blocked_actions:
        errors.append(f"{label}: blocked_actions must include terminal_closure")
    if not blocked_actions:
        errors.append(f"{label}: blocked_actions must not be empty")
    expected_receipts = _string_list(simulation.get("expected_receipts"))
    if "authority_denial_receipt" not in expected_receipts:
        errors.append(f"{label}: expected_receipts must include authority_denial_receipt")
    if not _string_list(simulation.get("needed_evidence")):
        errors.append(f"{label}: needed_evidence must not be empty")
    if simulation.get("outcome") == "GovernanceBlocked" and not blocked_component_ids:
        errors.append(f"{label}: GovernanceBlocked scenarios must identify blocked components")
    if simulation.get("outcome") not in {"AwaitingEvidence", "GovernanceBlocked", "SolvedUnverified"}:
        errors.append(f"{label}: outcome is not a governed solver outcome")


def _component_ids(read_model: dict[str, Any]) -> set[str]:
    components = read_model.get("components")
    if not isinstance(components, list):
        return set()
    return {
        str(component.get("component_id"))
        for component in components
        if isinstance(component, dict) and isinstance(component.get("component_id"), str)
    }


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
    """Parse component request simulation validation arguments."""

    parser = argparse.ArgumentParser(description="Validate Component Harness request simulation.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--example", default=str(DEFAULT_EXAMPLE))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for component request simulation validation."""

    args = parse_args(argv)
    validation = validate_component_request_simulation(
        schema_path=Path(args.schema),
        example_path=Path(args.example),
    )
    write_component_request_simulation_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("COMPONENT REQUEST SIMULATION VALID")
    else:
        print(f"COMPONENT REQUEST SIMULATION INVALID errors={list(validation.errors)}")
    return 0 if validation.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
