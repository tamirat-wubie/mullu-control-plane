#!/usr/bin/env python3
"""Validate the Mullu Component Harness router inventory.

Purpose: bind selected declared route families to registered component IDs and
proof surfaces without granting execution authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/component_router_inventory.schema.json,
examples/component_router_inventory.foundation.json,
examples/component_registry.foundation.json, scripts.proof_coverage_matrix,
and scripts.validate_schemas.
Invariants:
  - Router inventory is read-only and cannot enable live execution.
  - Every route binding references a registered component.
  - Bound route families resolve to declared routes and proof surfaces.
  - Prefix drift is explicit: a new route under a bound prefix fails until the
    inventory records the route.
  - Components without declared routes are explicitly marked no_declared_route.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sys
from typing import Any, Iterable, Sequence


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.proof_coverage_matrix import (  # noqa: E402
    discover_declared_routes,
    proof_coverage_matrix,
    route_coverage_report,
)
from scripts.validate_component_registry import (  # noqa: E402
    DEFAULT_EXAMPLES as DEFAULT_REGISTRY_EXAMPLES,
    validate_component_registry,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "component_router_inventory.schema.json"
DEFAULT_INVENTORY = REPO_ROOT / "examples" / "component_router_inventory.foundation.json"
DEFAULT_REGISTRY = DEFAULT_REGISTRY_EXAMPLES[0]
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "component_router_inventory_validation.json"

REQUIRED_VALIDATOR_COMMANDS = {
    "component_router_inventory_validator": "python scripts/validate_component_router_inventory.py",
    "component_router_inventory_tests": "python -m pytest tests/test_validate_component_router_inventory.py -q",
}
LIVE_GUARDRAILS = {
    "router_inventory_is_not_execution_authority": True,
    "live_execution_enabled": False,
    "live_connector_send_enabled": False,
    "terminal_closure_required": True,
}


@dataclass(frozen=True, slots=True)
class ComponentRouterInventoryValidation:
    """Schema and semantic validation report for router inventory."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    inventory_path: str
    registry_path: str
    route_binding_count: int
    bound_route_count: int
    discovered_route_count: int
    unclassified_route_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_component_router_inventory(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    inventory_path: Path = DEFAULT_INVENTORY,
    registry_path: Path = DEFAULT_REGISTRY,
) -> ComponentRouterInventoryValidation:
    """Validate router inventory against schema, registry, and route coverage."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "component router inventory schema", errors)
    inventory = _load_json_object(inventory_path, "component router inventory", errors)
    registry = _load_json_object(registry_path, "component registry", errors)
    if schema and inventory:
        errors.extend(
            f"{_path_label(inventory_path)}: {error}"
            for error in _validate_schema_instance(schema, inventory)
        )

    registry_validation = validate_component_registry(example_paths=(registry_path,))
    if not registry_validation.ok:
        errors.extend(
            f"{_path_label(registry_path)}: registry validation failed: {error}"
            for error in registry_validation.errors
        )

    matrix = proof_coverage_matrix()
    route_report = route_coverage_report(matrix["surfaces"], discover_declared_routes())
    route_records = {
        str(record["route"]): record
        for record in route_report["routes"]
        if isinstance(record, dict)
    }
    surface_ids = {str(surface["surface_id"]) for surface in matrix["surfaces"]}
    component_ids = _component_ids(registry)

    if inventory:
        _validate_inventory_semantics(
            inventory=inventory,
            component_ids=component_ids,
            surface_ids=surface_ids,
            route_records=route_records,
            errors=errors,
            label=_path_label(inventory_path),
        )

    bound_route_count = _bound_route_count(inventory)
    return ComponentRouterInventoryValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        inventory_path=_path_label(inventory_path),
        registry_path=_path_label(registry_path),
        route_binding_count=len(inventory.get("route_bindings", ())) if isinstance(inventory, dict) else 0,
        bound_route_count=bound_route_count,
        discovered_route_count=route_report["route_count"],
        unclassified_route_count=route_report["unclassified_route_count"],
    )


def write_component_router_inventory_validation(
    validation: ComponentRouterInventoryValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic router inventory validation report."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_inventory_semantics(
    *,
    inventory: dict[str, Any],
    component_ids: set[str],
    surface_ids: set[str],
    route_records: dict[str, dict[str, Any]],
    errors: list[str],
    label: str,
) -> None:
    _validate_guardrails(inventory, errors, label)
    _validate_validators(inventory, errors, label)
    bindings = inventory.get("route_bindings")
    if not isinstance(bindings, list):
        errors.append(f"{label}: route_bindings must be a list")
        return

    binding_component_ids = [
        str(binding.get("component_id"))
        for binding in bindings
        if isinstance(binding, dict) and binding.get("component_id")
    ]
    duplicate_component_ids = sorted(_duplicates(binding_component_ids))
    if duplicate_component_ids:
        errors.append(f"{label}: duplicate component route bindings {duplicate_component_ids}")
    missing_bindings = sorted(component_ids - set(binding_component_ids))
    if missing_bindings:
        errors.append(f"{label}: registered components missing route binding entries {missing_bindings}")

    owner_by_route: dict[str, str] = {}
    for binding in bindings:
        if not isinstance(binding, dict):
            errors.append(f"{label}: route_bindings entries must be objects")
            continue
        _validate_route_binding(
            binding=binding,
            component_ids=component_ids,
            surface_ids=surface_ids,
            route_records=route_records,
            owner_by_route=owner_by_route,
            errors=errors,
            label=label,
        )


def _validate_guardrails(
    inventory: dict[str, Any],
    errors: list[str],
    label: str,
) -> None:
    for guardrail_name, expected_value in LIVE_GUARDRAILS.items():
        if inventory.get(guardrail_name) is not expected_value:
            errors.append(f"{label}: {guardrail_name} must be {expected_value!r}")


def _validate_validators(
    inventory: dict[str, Any],
    errors: list[str],
    label: str,
) -> None:
    validators = inventory.get("validators")
    if not isinstance(validators, list):
        errors.append(f"{label}: validators must be a list")
        return
    validator_by_id: dict[str, dict[str, Any]] = {}
    for validator in validators:
        if not isinstance(validator, dict):
            errors.append(f"{label}: validators entries must be objects")
            continue
        validator_id = str(validator.get("validator_id", ""))
        if validator_id in validator_by_id:
            errors.append(f"{label}: duplicate validator id {validator_id}")
        validator_by_id[validator_id] = validator
    missing = sorted(set(REQUIRED_VALIDATOR_COMMANDS) - set(validator_by_id))
    if missing:
        errors.append(f"{label}: missing required validator declarations {missing}")
    for validator_id, expected_command in REQUIRED_VALIDATOR_COMMANDS.items():
        validator = validator_by_id.get(validator_id)
        if not validator:
            continue
        if validator.get("command") != expected_command:
            errors.append(
                f"{label}: validator {validator_id} command must be {expected_command!r}"
            )
        if validator.get("required_for_closure") is not True:
            errors.append(f"{label}: validator {validator_id} must be required_for_closure")


def _validate_route_binding(
    *,
    binding: dict[str, Any],
    component_ids: set[str],
    surface_ids: set[str],
    route_records: dict[str, dict[str, Any]],
    owner_by_route: dict[str, str],
    errors: list[str],
    label: str,
) -> None:
    component_id = str(binding.get("component_id", "<missing>"))
    binding_state = str(binding.get("binding_state", "<missing>"))
    proof_surface_ids = _string_list(binding.get("proof_surface_ids"))
    route_prefixes = _string_list(binding.get("route_prefixes"))
    expected_routes = _string_list(binding.get("expected_routes"))
    blocked_actions = _string_list(binding.get("blocked_actions"))

    if component_id not in component_ids:
        errors.append(f"{label}: route binding component {component_id} is not registered")
    if binding.get("binding_is_not_execution_authority") is not True:
        errors.append(f"{label}: component {component_id} binding must not be execution authority")
    if binding.get("can_enable_live_action") is not False:
        errors.append(f"{label}: component {component_id} binding cannot enable live action")
    if "terminal_closure" not in blocked_actions:
        errors.append(f"{label}: component {component_id} binding must block terminal_closure")
    for surface_id in proof_surface_ids:
        if surface_id not in surface_ids:
            errors.append(f"{label}: component {component_id} proof surface {surface_id} is not in proof matrix")

    if binding_state == "bound":
        _validate_bound_route_binding(
            component_id=component_id,
            proof_surface_ids=proof_surface_ids,
            route_prefixes=route_prefixes,
            expected_routes=expected_routes,
            route_records=route_records,
            owner_by_route=owner_by_route,
            errors=errors,
            label=label,
        )
        return
    if binding_state in {"no_declared_route", "deferred"}:
        if route_prefixes:
            errors.append(f"{label}: component {component_id} {binding_state} binding must not list route_prefixes")
        if expected_routes:
            errors.append(f"{label}: component {component_id} {binding_state} binding must not list expected_routes")
        return
    errors.append(f"{label}: component {component_id} has unknown binding_state {binding_state}")


def _validate_bound_route_binding(
    *,
    component_id: str,
    proof_surface_ids: tuple[str, ...],
    route_prefixes: tuple[str, ...],
    expected_routes: tuple[str, ...],
    route_records: dict[str, dict[str, Any]],
    owner_by_route: dict[str, str],
    errors: list[str],
    label: str,
) -> None:
    if not proof_surface_ids:
        errors.append(f"{label}: component {component_id} bound route binding must list proof_surface_ids")
    if not route_prefixes:
        errors.append(f"{label}: component {component_id} bound route binding must list route_prefixes")
    if not expected_routes:
        errors.append(f"{label}: component {component_id} bound route binding must list expected_routes")
    expected_route_set = set(expected_routes)
    for route in expected_routes:
        record = route_records.get(route)
        if record is None:
            errors.append(f"{label}: component {component_id} expected route {route} is not declared")
            continue
        route_surface = str(record.get("surface_id"))
        if route_surface not in proof_surface_ids:
            errors.append(
                f"{label}: component {component_id} expected route {route} maps to {route_surface}, not {sorted(proof_surface_ids)}"
            )
        existing_owner = owner_by_route.get(route)
        if existing_owner and existing_owner != component_id:
            errors.append(f"{label}: route {route} is bound by both {existing_owner} and {component_id}")
        owner_by_route[route] = component_id

    matched_routes = sorted(
        route
        for route in route_records
        if any(route.startswith(prefix) for prefix in route_prefixes)
    )
    if not matched_routes:
        errors.append(f"{label}: component {component_id} route_prefixes match no declared routes")
    unexpected_routes = sorted(set(matched_routes) - expected_route_set)
    if unexpected_routes:
        errors.append(f"{label}: component {component_id} has unrecorded routes under prefixes {unexpected_routes}")
    for route in matched_routes:
        route_surface = str(route_records[route].get("surface_id"))
        if route_surface not in proof_surface_ids:
            errors.append(
                f"{label}: component {component_id} prefix route {route} maps to {route_surface}, not {sorted(proof_surface_ids)}"
            )


def _component_ids(registry: dict[str, Any]) -> set[str]:
    components = registry.get("components", ())
    if not isinstance(components, list):
        return set()
    return {
        str(component["id"])
        for component in components
        if isinstance(component, dict) and isinstance(component.get("id"), str)
    }


def _bound_route_count(inventory: dict[str, Any]) -> int:
    bindings = inventory.get("route_bindings", ())
    if not isinstance(bindings, list):
        return 0
    routes: set[str] = set()
    for binding in bindings:
        if isinstance(binding, dict):
            routes.update(_string_list(binding.get("expected_routes")))
    return len(routes)


def _string_list(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return tuple()
    return tuple(str(item) for item in value)


def _duplicates(values: Iterable[str]) -> set[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return duplicates


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
    """Parse component router inventory validation arguments."""

    parser = argparse.ArgumentParser(description="Validate the Mullu Component Harness router inventory.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--inventory", default=str(DEFAULT_INVENTORY))
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for router inventory validation."""

    args = parse_args(argv)
    validation = validate_component_router_inventory(
        schema_path=Path(args.schema),
        inventory_path=Path(args.inventory),
        registry_path=Path(args.registry),
    )
    write_component_router_inventory_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("COMPONENT ROUTER INVENTORY VALID")
    else:
        print(f"COMPONENT ROUTER INVENTORY INVALID errors={list(validation.errors)}")
    return 0 if validation.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
