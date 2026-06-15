#!/usr/bin/env python3
"""Validate the Mullu Component Harness proof binding.

Purpose: bind registered components and router inventory proof declarations to
the generated proof coverage matrix without granting execution authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/component_proof_binding.schema.json,
examples/component_proof_binding.foundation.json,
examples/component_registry.foundation.json,
examples/component_router_inventory.foundation.json, scripts.proof_coverage_matrix,
scripts.validate_component_registry, scripts.validate_component_router_inventory,
and scripts.validate_schemas.
Invariants:
  - Every registered component has exactly one proof binding entry.
  - Receipt-required components are proof-bound and backed by runtime witnesses.
  - Every referenced surface exists in both generated and fixture proof matrices.
  - Router inventory proof declarations are mirrored by component proof binding.
  - Proof binding never grants execution, mutation, connector send, or terminal
    closure authority.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from functools import lru_cache
import json
from pathlib import Path
import sys
from typing import Any, Iterable, Sequence


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.proof_coverage_matrix import proof_coverage_matrix  # noqa: E402
from scripts.validate_component_registry import (  # noqa: E402
    DEFAULT_EXAMPLES as DEFAULT_REGISTRY_EXAMPLES,
    validate_component_registry,
)
from scripts.validate_component_router_inventory import (  # noqa: E402
    DEFAULT_INVENTORY as DEFAULT_ROUTER_INVENTORY,
    validate_component_router_inventory,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "component_proof_binding.schema.json"
DEFAULT_BINDING = REPO_ROOT / "examples" / "component_proof_binding.foundation.json"
DEFAULT_REGISTRY = DEFAULT_REGISTRY_EXAMPLES[0]
DEFAULT_PROOF_MATRIX = REPO_ROOT / "tests" / "fixtures" / "proof_coverage_matrix.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "component_proof_binding_validation.json"

REQUIRED_VALIDATOR_COMMANDS = {
    "component_proof_binding_validator": "python scripts/validate_component_proof_binding.py",
    "component_proof_binding_tests": "python -m pytest tests/test_validate_component_proof_binding.py -q",
}
LIVE_GUARDRAILS = {
    "proof_binding_is_not_execution_authority": True,
    "live_execution_enabled": False,
    "terminal_closure_required": True,
}
PROOF_BOUND_STATES = {"proven", "witnessed"}


@dataclass(frozen=True, slots=True)
class ComponentProofBindingValidation:
    """Schema and semantic validation report for component proof binding."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    binding_path: str
    registry_path: str
    router_inventory_path: str
    proof_matrix_path: str
    binding_count: int
    proof_bound_count: int
    referenced_surface_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_component_proof_binding(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    binding_path: Path = DEFAULT_BINDING,
    registry_path: Path = DEFAULT_REGISTRY,
    router_inventory_path: Path = DEFAULT_ROUTER_INVENTORY,
    proof_matrix_path: Path = DEFAULT_PROOF_MATRIX,
) -> ComponentProofBindingValidation:
    """Validate proof binding against schema, registry, inventory, and matrix."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "component proof binding schema", errors)
    binding = _load_json_object(binding_path, "component proof binding", errors)
    registry = _load_json_object(registry_path, "component registry", errors)
    router_inventory = _load_json_object(router_inventory_path, "component router inventory", errors)
    fixture_matrix = _load_json_object(proof_matrix_path, "proof coverage matrix fixture", errors)
    generated_matrix = _generated_proof_coverage_matrix()

    if schema and binding:
        errors.extend(
            f"{_path_label(binding_path)}: {error}"
            for error in _validate_schema_instance(schema, binding)
        )

    registry_validation = _validate_component_registry_cached(str(registry_path))
    if not registry_validation.ok:
        errors.extend(
            f"{_path_label(registry_path)}: registry validation failed: {error}"
            for error in registry_validation.errors
        )

    router_validation = _validate_component_router_inventory_cached(
        str(router_inventory_path),
        str(registry_path),
    )
    if not router_validation.ok:
        errors.extend(
            f"{_path_label(router_inventory_path)}: router inventory validation failed: {error}"
            for error in router_validation.errors
        )

    generated_surfaces = _surface_map(generated_matrix)
    fixture_surfaces = _surface_map(fixture_matrix)
    if binding:
        _validate_binding_semantics(
            binding=binding,
            registry=registry,
            router_inventory=router_inventory,
            generated_surfaces=generated_surfaces,
            fixture_surfaces=fixture_surfaces,
            registry_path=registry_path,
            router_inventory_path=router_inventory_path,
            proof_matrix_path=proof_matrix_path,
            errors=errors,
            label=_path_label(binding_path),
        )

    binding_entries = binding.get("component_bindings", ()) if isinstance(binding, dict) else ()
    referenced_surface_ids = _referenced_surface_ids(binding_entries)
    return ComponentProofBindingValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        binding_path=_path_label(binding_path),
        registry_path=_path_label(registry_path),
        router_inventory_path=_path_label(router_inventory_path),
        proof_matrix_path=_path_label(proof_matrix_path),
        binding_count=len(binding_entries) if isinstance(binding_entries, list) else 0,
        proof_bound_count=sum(
            1
            for entry in binding_entries
            if isinstance(entry, dict) and entry.get("proof_binding_state") == "proof_bound"
        )
        if isinstance(binding_entries, list)
        else 0,
        referenced_surface_count=len(referenced_surface_ids),
    )


def write_component_proof_binding_validation(
    validation: ComponentProofBindingValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic proof binding validation report."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


@lru_cache(maxsize=1)
def _generated_proof_coverage_matrix() -> dict[str, Any]:
    """Return generated proof coverage matrix for this validation process."""

    return proof_coverage_matrix()


@lru_cache(maxsize=16)
def _validate_component_registry_cached(registry_path: str) -> Any:
    """Return cached registry validation for stable path inputs."""

    return validate_component_registry(example_paths=(Path(registry_path),))


@lru_cache(maxsize=16)
def _validate_component_router_inventory_cached(
    router_inventory_path: str,
    registry_path: str,
) -> Any:
    """Return cached router inventory validation for stable path inputs."""

    return validate_component_router_inventory(
        inventory_path=Path(router_inventory_path),
        registry_path=Path(registry_path),
    )


def _validate_binding_semantics(
    *,
    binding: dict[str, Any],
    registry: dict[str, Any],
    router_inventory: dict[str, Any],
    generated_surfaces: dict[str, dict[str, Any]],
    fixture_surfaces: dict[str, dict[str, Any]],
    registry_path: Path,
    router_inventory_path: Path,
    proof_matrix_path: Path,
    errors: list[str],
    label: str,
) -> None:
    _validate_guardrails(binding, errors, label)
    _validate_source_refs(
        binding=binding,
        registry_path=registry_path,
        router_inventory_path=router_inventory_path,
        proof_matrix_path=proof_matrix_path,
        errors=errors,
        label=label,
    )
    _validate_validators(binding, errors, label)

    components = _component_map(registry)
    inventory_surfaces_by_component = _inventory_surfaces_by_component(router_inventory)
    component_bindings = binding.get("component_bindings")
    if not isinstance(component_bindings, list):
        errors.append(f"{label}: component_bindings must be a list")
        return

    binding_component_ids = [
        str(component_binding.get("component_id"))
        for component_binding in component_bindings
        if isinstance(component_binding, dict) and component_binding.get("component_id")
    ]
    duplicate_component_ids = sorted(_duplicates(binding_component_ids))
    if duplicate_component_ids:
        errors.append(f"{label}: duplicate component proof bindings {duplicate_component_ids}")

    missing_component_ids = sorted(set(components) - set(binding_component_ids))
    extra_component_ids = sorted(set(binding_component_ids) - set(components))
    if missing_component_ids:
        errors.append(f"{label}: registered components missing proof bindings {missing_component_ids}")
    if extra_component_ids:
        errors.append(f"{label}: proof bindings reference unregistered components {extra_component_ids}")

    for component_binding in component_bindings:
        if not isinstance(component_binding, dict):
            errors.append(f"{label}: component_bindings entries must be objects")
            continue
        _validate_component_binding(
            component_binding=component_binding,
            component=components.get(str(component_binding.get("component_id"))),
            inventory_surface_ids=inventory_surfaces_by_component.get(
                str(component_binding.get("component_id")),
                frozenset(),
            ),
            generated_surfaces=generated_surfaces,
            fixture_surfaces=fixture_surfaces,
            errors=errors,
            label=label,
        )


def _validate_guardrails(
    binding: dict[str, Any],
    errors: list[str],
    label: str,
) -> None:
    for guardrail_name, expected_value in LIVE_GUARDRAILS.items():
        if binding.get(guardrail_name) is not expected_value:
            errors.append(f"{label}: {guardrail_name} must be {expected_value!r}")


def _validate_source_refs(
    *,
    binding: dict[str, Any],
    registry_path: Path,
    router_inventory_path: Path,
    proof_matrix_path: Path,
    errors: list[str],
    label: str,
) -> None:
    expected_sources = {
        "source_registry": _path_label(registry_path),
        "source_router_inventory": _path_label(router_inventory_path),
        "source_proof_matrix": _path_label(proof_matrix_path),
    }
    for field_name, expected_value in expected_sources.items():
        if binding.get(field_name) != expected_value:
            errors.append(f"{label}: {field_name} must be {expected_value!r}")


def _validate_validators(
    binding: dict[str, Any],
    errors: list[str],
    label: str,
) -> None:
    validators = binding.get("validators")
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


def _validate_component_binding(
    *,
    component_binding: dict[str, Any],
    component: dict[str, Any] | None,
    inventory_surface_ids: frozenset[str],
    generated_surfaces: dict[str, dict[str, Any]],
    fixture_surfaces: dict[str, dict[str, Any]],
    errors: list[str],
    label: str,
) -> None:
    component_id = str(component_binding.get("component_id", "<missing>"))
    if component is None:
        return

    if component_binding.get("binding_is_not_execution_authority") is not True:
        errors.append(f"{label}: component {component_id} binding must not be execution authority")
    if component_binding.get("can_claim_terminal_closure") is not False:
        errors.append(f"{label}: component {component_id} cannot claim terminal closure")

    blocked_actions = set(_string_list(component_binding.get("blocked_actions")))
    component_blocked_actions = set(_string_list(component.get("blocked_actions")))
    missing_blocked_actions = sorted(component_blocked_actions - blocked_actions)
    if missing_blocked_actions:
        errors.append(
            f"{label}: component {component_id} proof binding omits blocked actions {missing_blocked_actions}"
        )
    if "terminal_closure" not in blocked_actions:
        errors.append(f"{label}: component {component_id} must block terminal_closure")

    if component_binding.get("receipt_required") is not component.get("receipt_required"):
        errors.append(f"{label}: component {component_id} receipt_required must match registry")

    proof_surface = component.get("proof_surface")
    if not isinstance(proof_surface, dict):
        errors.append(f"{label}: component {component_id} registry proof_surface must be an object")
        return

    proof_status = str(proof_surface.get("status"))
    registry_surface_id = proof_surface.get("surface_id")
    proof_binding_state = str(component_binding.get("proof_binding_state"))
    required_surface_ids = set(_string_list(component_binding.get("required_surface_ids")))
    binding_inventory_surface_ids = set(_string_list(component_binding.get("inventory_surface_ids")))
    required_evidence_files = set(_string_list(component_binding.get("required_evidence_files")))
    required_runtime_witnesses = set(_string_list(component_binding.get("required_runtime_witnesses")))

    if proof_status == "proof_bound":
        _validate_proof_bound_component(
            component_id=component_id,
            proof_binding_state=proof_binding_state,
            registry_surface_id=registry_surface_id,
            required_surface_ids=required_surface_ids,
            binding_inventory_surface_ids=binding_inventory_surface_ids,
            inventory_surface_ids=inventory_surface_ids,
            required_evidence_files=required_evidence_files,
            required_runtime_witnesses=required_runtime_witnesses,
            receipt_required=component.get("receipt_required") is True,
            generated_surfaces=generated_surfaces,
            fixture_surfaces=fixture_surfaces,
            errors=errors,
            label=label,
        )
        return

    if proof_status == "awaiting_binding":
        _validate_awaiting_binding_component(
            component_id=component_id,
            proof_binding_state=proof_binding_state,
            required_surface_ids=required_surface_ids,
            binding_inventory_surface_ids=binding_inventory_surface_ids,
            inventory_surface_ids=inventory_surface_ids,
            required_evidence_files=required_evidence_files,
            required_runtime_witnesses=required_runtime_witnesses,
            receipt_required=component_binding.get("receipt_required") is True,
            errors=errors,
            label=label,
        )
        return

    if proof_binding_state != "not_applicable":
        errors.append(f"{label}: component {component_id} proof status {proof_status} must be not_applicable")


def _validate_proof_bound_component(
    *,
    component_id: str,
    proof_binding_state: str,
    registry_surface_id: object,
    required_surface_ids: set[str],
    binding_inventory_surface_ids: set[str],
    inventory_surface_ids: frozenset[str],
    required_evidence_files: set[str],
    required_runtime_witnesses: set[str],
    receipt_required: bool,
    generated_surfaces: dict[str, dict[str, Any]],
    fixture_surfaces: dict[str, dict[str, Any]],
    errors: list[str],
    label: str,
) -> None:
    if proof_binding_state != "proof_bound":
        errors.append(f"{label}: component {component_id} must be proof_bound")
    if not isinstance(registry_surface_id, str) or not registry_surface_id:
        errors.append(f"{label}: component {component_id} registry proof_bound surface must name surface_id")
    elif registry_surface_id not in required_surface_ids:
        errors.append(
            f"{label}: component {component_id} required_surface_ids must include registry surface {registry_surface_id}"
        )
    if binding_inventory_surface_ids != set(inventory_surface_ids):
        errors.append(
            f"{label}: component {component_id} inventory_surface_ids must match router inventory {sorted(inventory_surface_ids)}"
        )
    if not required_surface_ids:
        errors.append(f"{label}: component {component_id} proof_bound binding must list required_surface_ids")
    if receipt_required and not required_runtime_witnesses:
        errors.append(f"{label}: component {component_id} receipt_required binding must list runtime witnesses")
    if not required_evidence_files:
        errors.append(f"{label}: component {component_id} proof_bound binding must list evidence files")

    referenced_surface_ids = required_surface_ids | binding_inventory_surface_ids
    surface_evidence_files: set[str] = set()
    surface_runtime_witnesses: set[str] = set()
    for surface_id in sorted(referenced_surface_ids):
        generated_surface = generated_surfaces.get(surface_id)
        fixture_surface = fixture_surfaces.get(surface_id)
        if generated_surface is None:
            errors.append(f"{label}: component {component_id} surface {surface_id} is not in generated proof matrix")
            continue
        if fixture_surface is None:
            errors.append(f"{label}: component {component_id} surface {surface_id} is not in fixture proof matrix")
        if generated_surface.get("coverage_state") not in PROOF_BOUND_STATES:
            errors.append(
                f"{label}: component {component_id} surface {surface_id} coverage_state must be proven or witnessed"
            )
        surface_evidence_files.update(_string_list(generated_surface.get("evidence_files")))
        surface_runtime_witnesses.update(_string_list(generated_surface.get("runtime_witnesses")))

    missing_evidence_files = sorted(required_evidence_files - surface_evidence_files)
    if missing_evidence_files:
        errors.append(
            f"{label}: component {component_id} evidence files are not present on referenced surfaces {missing_evidence_files}"
        )
    missing_runtime_witnesses = sorted(required_runtime_witnesses - surface_runtime_witnesses)
    if missing_runtime_witnesses:
        errors.append(
            f"{label}: component {component_id} runtime witnesses are not present on referenced surfaces {missing_runtime_witnesses}"
        )

    for evidence_file in sorted(required_evidence_files):
        if not (REPO_ROOT / evidence_file).exists():
            errors.append(f"{label}: component {component_id} evidence file missing on disk: {evidence_file}")


def _validate_awaiting_binding_component(
    *,
    component_id: str,
    proof_binding_state: str,
    required_surface_ids: set[str],
    binding_inventory_surface_ids: set[str],
    inventory_surface_ids: frozenset[str],
    required_evidence_files: set[str],
    required_runtime_witnesses: set[str],
    receipt_required: bool,
    errors: list[str],
    label: str,
) -> None:
    if proof_binding_state != "awaiting_binding":
        errors.append(f"{label}: component {component_id} must remain awaiting_binding")
    if required_surface_ids:
        errors.append(f"{label}: component {component_id} awaiting_binding must not list required_surface_ids")
    if binding_inventory_surface_ids or inventory_surface_ids:
        errors.append(f"{label}: component {component_id} awaiting_binding must not list inventory_surface_ids")
    if required_evidence_files:
        errors.append(f"{label}: component {component_id} awaiting_binding must not list evidence files")
    if required_runtime_witnesses:
        errors.append(f"{label}: component {component_id} awaiting_binding must not list runtime witnesses")
    if receipt_required:
        errors.append(f"{label}: component {component_id} awaiting_binding cannot require receipts")


def _component_map(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    components = registry.get("components", ())
    if not isinstance(components, list):
        return {}
    return {
        str(component["id"]): component
        for component in components
        if isinstance(component, dict) and isinstance(component.get("id"), str)
    }


def _inventory_surfaces_by_component(router_inventory: dict[str, Any]) -> dict[str, frozenset[str]]:
    route_bindings = router_inventory.get("route_bindings", ())
    if not isinstance(route_bindings, list):
        return {}
    surfaces_by_component: dict[str, frozenset[str]] = {}
    for route_binding in route_bindings:
        if not isinstance(route_binding, dict):
            continue
        component_id = str(route_binding.get("component_id", ""))
        if not component_id:
            continue
        surfaces_by_component[component_id] = frozenset(_string_list(route_binding.get("proof_surface_ids")))
    return surfaces_by_component


def _surface_map(matrix: dict[str, Any]) -> dict[str, dict[str, Any]]:
    surfaces = matrix.get("surfaces", ())
    if not isinstance(surfaces, list):
        return {}
    return {
        str(surface["surface_id"]): surface
        for surface in surfaces
        if isinstance(surface, dict) and isinstance(surface.get("surface_id"), str)
    }


def _referenced_surface_ids(component_bindings: object) -> set[str]:
    if not isinstance(component_bindings, list):
        return set()
    surface_ids: set[str] = set()
    for component_binding in component_bindings:
        if not isinstance(component_binding, dict):
            continue
        surface_ids.update(_string_list(component_binding.get("required_surface_ids")))
        surface_ids.update(_string_list(component_binding.get("inventory_surface_ids")))
    return surface_ids


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
    """Parse component proof binding validation arguments."""

    parser = argparse.ArgumentParser(description="Validate the Mullu Component Harness proof binding.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--binding", default=str(DEFAULT_BINDING))
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--router-inventory", default=str(DEFAULT_ROUTER_INVENTORY))
    parser.add_argument("--proof-matrix", default=str(DEFAULT_PROOF_MATRIX))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for proof binding validation."""

    args = parse_args(argv)
    validation = validate_component_proof_binding(
        schema_path=Path(args.schema),
        binding_path=Path(args.binding),
        registry_path=Path(args.registry),
        router_inventory_path=Path(args.router_inventory),
        proof_matrix_path=Path(args.proof_matrix),
    )
    write_component_proof_binding_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("COMPONENT PROOF BINDING VALID")
    else:
        print(f"COMPONENT PROOF BINDING INVALID errors={list(validation.errors)}")
    return 0 if validation.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
