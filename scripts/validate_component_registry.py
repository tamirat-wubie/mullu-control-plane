#!/usr/bin/env python3
"""Validate the Mullu Component Harness registry.

Purpose: keep the first component registry canonical, foundation-scoped,
dependency-consistent, proof-aware, receipt-aware, and non-executing.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/component_registry.schema.json,
examples/component_registry.foundation.json, and scripts.validate_schemas.
Invariants:
  - Component IDs and aliases are unique.
  - Dependencies reference registered components.
  - Mounted, bootstrapped, live-probe, and approval-required components do not
    imply live execution authority.
  - Receipt-required components declare an explicit proof-bound surface.
  - Foundation guardrails block route binding, live execution, live connector
    sends, public readiness claims, and terminal closure.
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

from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "component_registry.schema.json"
DEFAULT_EXAMPLES = (
    REPO_ROOT / "examples" / "component_registry.foundation.json",
)
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "component_registry_validation.json"

REQUIRED_FOUNDATION_COMPONENT_IDS = (
    "governance_core",
    "agentic_service_harness",
    "snet",
    "inceptadive_shadow",
    "personal_assistant",
    "teamops_shared_inbox",
    "gmail_account_binding_gate",
    "worker_runtime",
    "capability_workers",
    "nested_mind_bridge",
)
REQUIRED_COMPONENT_BUNDLE_IDS = (
    "personal_assistant_v0",
    "symbolic_reasoning_read_only",
    "worker_runtime_foundation",
)
REQUIRED_VALIDATOR_COMMANDS = {
    "component_registry_validator": "python scripts/validate_component_registry.py",
    "component_registry_tests": "python -m pytest tests/test_validate_component_registry.py -q",
}
REQUIRED_GUARDRAILS = {
    "foundation_mode": True,
    "registry_only": True,
    "route_binding_enabled": False,
    "proof_matrix_binding_enforced": False,
    "live_execution_enabled": False,
    "live_connector_send_enabled": False,
    "public_customer_ready_claimed": False,
    "terminal_closure_claimed": False,
}
LIVE_AUTHORITY_FLAGS = (
    "can_execute",
    "can_mutate",
    "can_call_connector",
    "can_write_files",
    "can_send_external_message",
    "can_claim_terminal_closure",
)
AUTHORITY_TO_ALLOWED_FLAGS = {
    "none": frozenset(),
    "registry_only": frozenset(),
    "blocked": frozenset({"can_read", "can_preview"}),
    "read_only": frozenset({"can_read", "can_preview", "can_emit_receipt"}),
    "read_only_advisory": frozenset({"can_read", "can_preview", "can_emit_receipt"}),
    "draft_only": frozenset({"can_read", "can_preview", "can_draft", "can_emit_receipt"}),
    "live_probe": frozenset({"can_read", "can_preview", "can_emit_receipt"}),
    "approval_required": frozenset({"can_read", "can_preview", "can_emit_receipt"}),
    "approved_live_action": frozenset({"can_read", "can_preview", "can_emit_receipt"}),
}
STATES_REQUIRING_BLOCKED_ACTIONS = {
    "bootstrapped",
    "mounted",
    "live_probe",
    "approval_required",
    "approved_live_action",
    "live_action_enabled",
}
DISALLOWED_FOUNDATION_STATES = {
    "approved_live_action",
    "live_action_enabled",
}


@dataclass(frozen=True, slots=True)
class ComponentRegistryValidation:
    """Schema and semantic validation report for component registries."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_paths: tuple[str, ...]
    registry_count: int
    component_count: int
    bundle_count: int
    required_component_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        payload["example_paths"] = list(self.example_paths)
        return payload


def validate_component_registry(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_paths: Sequence[Path] = DEFAULT_EXAMPLES,
) -> ComponentRegistryValidation:
    """Validate component registry examples against schema and invariants."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "component registry schema", errors)
    registries: list[dict[str, Any]] = []

    for example_path in example_paths:
        registry = _load_json_object(
            example_path,
            f"component registry example {_path_label(example_path)}",
            errors,
        )
        if not registry:
            continue
        registries.append(registry)
        if schema:
            errors.extend(
                f"{_path_label(example_path)}: {error}"
                for error in _validate_schema_instance(schema, registry)
            )
        _validate_registry_semantics(registry, errors, _path_label(example_path))

    component_count = sum(
        len(registry.get("components", ()))
        for registry in registries
        if isinstance(registry.get("components"), list)
    )
    bundle_count = sum(
        len(registry.get("component_bundles", ()))
        for registry in registries
        if isinstance(registry.get("component_bundles"), list)
    )
    return ComponentRegistryValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_paths=tuple(_path_label(path) for path in example_paths),
        registry_count=len(registries),
        component_count=component_count,
        bundle_count=bundle_count,
        required_component_count=len(REQUIRED_FOUNDATION_COMPONENT_IDS),
    )


def write_component_registry_validation(
    validation: ComponentRegistryValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic component registry validation report."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_registry_semantics(
    registry: dict[str, Any],
    errors: list[str],
    label: str,
) -> None:
    _validate_guardrails(registry, errors, label)
    _validate_validators(registry, errors, label)
    components = registry.get("components")
    if not isinstance(components, list):
        errors.append(f"{label}: components must be a list")
        return
    component_objects = [component for component in components if isinstance(component, dict)]
    component_ids = _validate_component_ids(component_objects, errors, label)
    _validate_required_components(component_ids, errors, label)
    _validate_aliases(component_objects, component_ids, errors, label)
    _validate_component_bundles(registry, component_ids, errors, label)
    for component in component_objects:
        _validate_component_semantics(component, component_ids, errors, label)


def _validate_guardrails(
    registry: dict[str, Any],
    errors: list[str],
    label: str,
) -> None:
    guardrails = registry.get("registry_guardrails")
    if not isinstance(guardrails, dict):
        errors.append(f"{label}: registry_guardrails must be an object")
        return
    for guardrail_name, expected_value in REQUIRED_GUARDRAILS.items():
        if guardrails.get(guardrail_name) is not expected_value:
            errors.append(f"{label}: registry_guardrails.{guardrail_name} must be {expected_value!r}")
    if registry.get("registry_is_not_terminal_closure") is not True:
        errors.append(f"{label}: registry_is_not_terminal_closure must be true")
    if registry.get("terminal_closure_required") is not True:
        errors.append(f"{label}: terminal_closure_required must be true")


def _validate_validators(
    registry: dict[str, Any],
    errors: list[str],
    label: str,
) -> None:
    validators = registry.get("validators")
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


def _validate_component_ids(
    components: Sequence[dict[str, Any]],
    errors: list[str],
    label: str,
) -> set[str]:
    ids = [str(component.get("id")) for component in components if component.get("id")]
    duplicate_ids = sorted(_duplicates(ids))
    if duplicate_ids:
        errors.append(f"{label}: duplicate component ids {duplicate_ids}")
    return set(ids)


def _validate_required_components(
    component_ids: set[str],
    errors: list[str],
    label: str,
) -> None:
    missing = sorted(set(REQUIRED_FOUNDATION_COMPONENT_IDS) - component_ids)
    if missing:
        errors.append(f"{label}: missing required foundation components {missing}")


def _validate_aliases(
    components: Sequence[dict[str, Any]],
    component_ids: set[str],
    errors: list[str],
    label: str,
) -> None:
    owner_by_alias: dict[str, str] = {}
    for component in components:
        component_id = str(component.get("id", "<missing>"))
        aliases = component.get("aliases", ())
        if not isinstance(aliases, list):
            errors.append(f"{label}: component {component_id} aliases must be a list")
            continue
        for alias in aliases:
            alias_text = str(alias)
            if alias_text in component_ids and alias_text != component_id:
                errors.append(f"{label}: alias {alias_text} collides with component id")
            existing_owner = owner_by_alias.get(alias_text)
            if existing_owner and existing_owner != component_id:
                errors.append(f"{label}: alias {alias_text} claimed by {existing_owner} and {component_id}")
            owner_by_alias[alias_text] = component_id


def _validate_component_bundles(
    registry: dict[str, Any],
    component_ids: set[str],
    errors: list[str],
    label: str,
) -> None:
    bundles = registry.get("component_bundles")
    if not isinstance(bundles, list):
        errors.append(f"{label}: component_bundles must be a list")
        return
    bundle_ids = [
        str(bundle.get("bundle_id"))
        for bundle in bundles
        if isinstance(bundle, dict) and bundle.get("bundle_id")
    ]
    duplicate_bundle_ids = sorted(_duplicates(bundle_ids))
    if duplicate_bundle_ids:
        errors.append(f"{label}: duplicate component bundle ids {duplicate_bundle_ids}")
    missing = sorted(set(REQUIRED_COMPONENT_BUNDLE_IDS) - set(bundle_ids))
    if missing:
        errors.append(f"{label}: missing required component bundles {missing}")
    for bundle in bundles:
        if not isinstance(bundle, dict):
            errors.append(f"{label}: component_bundles entries must be objects")
            continue
        bundle_id = str(bundle.get("bundle_id", "<missing>"))
        bundle_components = bundle.get("components")
        blocked_actions = bundle.get("blocked_actions")
        if bundle.get("bundle_is_not_execution_route") is not True:
            errors.append(f"{label}: bundle {bundle_id} must declare bundle_is_not_execution_route")
        if bundle.get("terminal_closure_required") is not True:
            errors.append(f"{label}: bundle {bundle_id} must require terminal closure later")
        if not isinstance(bundle_components, list):
            errors.append(f"{label}: bundle {bundle_id} components must be a list")
        else:
            duplicate_component_refs = sorted(_duplicates(str(ref) for ref in bundle_components))
            if duplicate_component_refs:
                errors.append(
                    f"{label}: bundle {bundle_id} duplicate component refs {duplicate_component_refs}"
                )
            for component_ref in bundle_components:
                if str(component_ref) not in component_ids:
                    errors.append(
                        f"{label}: bundle {bundle_id} component {component_ref} is not registered"
                    )
        if not isinstance(blocked_actions, list):
            errors.append(f"{label}: bundle {bundle_id} blocked_actions must be a list")
        else:
            if "terminal_closure" not in blocked_actions:
                errors.append(f"{label}: bundle {bundle_id} must block terminal_closure")
            if bundle.get("allowed_mode") == "demo_v0" and "external_send" not in blocked_actions:
                errors.append(f"{label}: bundle {bundle_id} demo_v0 must block external_send")


def _validate_component_semantics(
    component: dict[str, Any],
    component_ids: set[str],
    errors: list[str],
    label: str,
) -> None:
    component_id = str(component.get("id", "<missing>"))
    _validate_dependencies(component, component_ids, errors, label, component_id)
    _validate_authority(component, errors, label, component_id)
    _validate_blocked_actions(component, errors, label, component_id)
    _validate_proof_surface(component, errors, label, component_id)
    _validate_health_source(component, errors, label, component_id)


def _validate_dependencies(
    component: dict[str, Any],
    component_ids: set[str],
    errors: list[str],
    label: str,
    component_id: str,
) -> None:
    dependencies = component.get("dependencies")
    if not isinstance(dependencies, list):
        errors.append(f"{label}: component {component_id} dependencies must be a list")
        return
    for dependency in dependencies:
        dependency_id = str(dependency)
        if dependency_id == component_id:
            errors.append(f"{label}: component {component_id} cannot depend on itself")
        if dependency_id not in component_ids:
            errors.append(f"{label}: component {component_id} dependency {dependency_id} is not registered")


def _validate_authority(
    component: dict[str, Any],
    errors: list[str],
    label: str,
    component_id: str,
) -> None:
    authority = component.get("authority")
    authority_level = str(component.get("authority_level"))
    lifecycle_state = str(component.get("lifecycle_state"))
    wiring_state = str(component.get("wiring_state"))
    if not isinstance(authority, dict):
        errors.append(f"{label}: component {component_id} authority must be an object")
        return
    if lifecycle_state in DISALLOWED_FOUNDATION_STATES:
        errors.append(f"{label}: component {component_id} lifecycle_state {lifecycle_state} is blocked in foundation")
    if wiring_state in DISALLOWED_FOUNDATION_STATES:
        errors.append(f"{label}: component {component_id} wiring_state {wiring_state} is blocked in foundation")
    for flag_name in LIVE_AUTHORITY_FLAGS:
        if authority.get(flag_name) is not False:
            errors.append(f"{label}: component {component_id} authority.{flag_name} must remain false")
    allowed_flags = AUTHORITY_TO_ALLOWED_FLAGS.get(authority_level, frozenset())
    for flag_name, flag_value in authority.items():
        if flag_value is True and flag_name not in allowed_flags:
            errors.append(
                f"{label}: component {component_id} authority.{flag_name} is not allowed for {authority_level}"
            )
    if authority_level == "approved_live_action":
        errors.append(f"{label}: component {component_id} cannot be approved_live_action in foundation registry")


def _validate_blocked_actions(
    component: dict[str, Any],
    errors: list[str],
    label: str,
    component_id: str,
) -> None:
    blocked_actions = component.get("blocked_actions")
    lifecycle_state = str(component.get("lifecycle_state"))
    wiring_state = str(component.get("wiring_state"))
    if not isinstance(blocked_actions, list):
        errors.append(f"{label}: component {component_id} blocked_actions must be a list")
        return
    if (
        lifecycle_state in STATES_REQUIRING_BLOCKED_ACTIONS
        or wiring_state in STATES_REQUIRING_BLOCKED_ACTIONS
    ) and not blocked_actions:
        errors.append(f"{label}: component {component_id} must list blocked actions for {lifecycle_state}/{wiring_state}")
    if "terminal_closure" not in blocked_actions:
        errors.append(f"{label}: component {component_id} must block terminal_closure")


def _validate_proof_surface(
    component: dict[str, Any],
    errors: list[str],
    label: str,
    component_id: str,
) -> None:
    proof_surface = component.get("proof_surface")
    if not isinstance(proof_surface, dict):
        errors.append(f"{label}: component {component_id} proof_surface must be an object")
        return
    status = proof_surface.get("status")
    surface_id = proof_surface.get("surface_id")
    evidence_refs = proof_surface.get("evidence_refs")
    if not isinstance(evidence_refs, list):
        errors.append(f"{label}: component {component_id} proof_surface.evidence_refs must be a list")
        return
    if status == "proof_bound":
        if not isinstance(surface_id, str) or not surface_id:
            errors.append(f"{label}: component {component_id} proof_bound surface must name surface_id")
        if not evidence_refs:
            errors.append(f"{label}: component {component_id} proof_bound surface must include evidence_refs")
        component_evidence_refs = component.get("evidence_refs")
        if isinstance(component_evidence_refs, list):
            proof_ref_set = {str(ref) for ref in evidence_refs}
            component_ref_set = {str(ref) for ref in component_evidence_refs}
            missing_component_refs = sorted(proof_ref_set - component_ref_set)
            if missing_component_refs:
                errors.append(
                    f"{label}: component {component_id} proof_surface evidence_refs missing from component evidence_refs {missing_component_refs}"
                )
    if status in {"not_applicable", "awaiting_binding"} and surface_id is not None:
        errors.append(f"{label}: component {component_id} {status} proof_surface must not name surface_id")
    if status == "declared" and (not isinstance(surface_id, str) or not surface_id):
        errors.append(f"{label}: component {component_id} declared proof_surface must name surface_id")
    if component.get("receipt_required") is True and status != "proof_bound":
        errors.append(f"{label}: component {component_id} receipt_required components must be proof_bound")


def _validate_health_source(
    component: dict[str, Any],
    errors: list[str],
    label: str,
    component_id: str,
) -> None:
    health_source = component.get("health_source")
    if not isinstance(health_source, dict):
        errors.append(f"{label}: component {component_id} health_source must be an object")
        return
    source_type = health_source.get("type")
    source_ref = health_source.get("ref")
    if source_type == "none" and source_ref is not None:
        errors.append(f"{label}: component {component_id} health_source none must not carry ref")
    if source_type != "none" and not isinstance(source_ref, str):
        errors.append(f"{label}: component {component_id} health_source {source_type} must carry ref")


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


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse component registry validation arguments."""

    parser = argparse.ArgumentParser(description="Validate the Mullu Component Harness registry.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--example", action="append", default=None)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for component registry validation."""

    args = parse_args(argv)
    example_paths = (
        tuple(Path(example) for example in args.example)
        if args.example
        else DEFAULT_EXAMPLES
    )
    validation = validate_component_registry(
        schema_path=Path(args.schema),
        example_paths=example_paths,
    )
    write_component_registry_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("COMPONENT REGISTRY VALID")
    else:
        print(f"COMPONENT REGISTRY INVALID errors={list(validation.errors)}")
    return 0 if validation.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
