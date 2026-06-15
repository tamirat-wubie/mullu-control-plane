"""Build the Component Harness read-model projection.

Purpose: join the component registry, router inventory, and proof binding into
one bounded operator-facing projection.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: foundation component harness JSON artifacts.
Invariants:
  - The read model is projection-only and never mutates source artifacts.
  - Live execution, connector send, and terminal closure remain false.
  - Missing or malformed source artifacts fail closed with explicit errors.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


READ_MODEL_ROUTE = "/api/v1/components/read-model"
READ_MODEL_ID = "component_read_model.foundation.v1"
SCHEMA_VERSION = 1
LIVE_AUTHORITY_FLAGS = (
    "can_execute",
    "can_mutate",
    "can_call_connector",
    "can_write_files",
    "can_send_external_message",
    "can_claim_terminal_closure",
)


class ComponentReadModelError(ValueError):
    """Raised when the component read model cannot be built safely."""


def build_component_read_model(
    *,
    registry_path: Path | None = None,
    router_inventory_path: Path | None = None,
    proof_binding_path: Path | None = None,
    lifecycle_receipts_path: Path | None = None,
) -> dict[str, Any]:
    """Return the deterministic foundation Component Harness read model.

    Input contract: optional paths to the registry, router inventory, and proof
    binding JSON artifacts. Output contract: JSON-serializable read model.
    Error contract: raises ComponentReadModelError with bounded causal context
    when an artifact is missing, malformed, or structurally unusable.
    """

    repo_root = _repo_root()
    effective_registry_path = registry_path or repo_root / "examples" / "component_registry.foundation.json"
    effective_router_inventory_path = (
        router_inventory_path or repo_root / "examples" / "component_router_inventory.foundation.json"
    )
    effective_proof_binding_path = proof_binding_path or repo_root / "examples" / "component_proof_binding.foundation.json"
    effective_lifecycle_receipts_path = (
        lifecycle_receipts_path
        or repo_root / "examples" / "component_lifecycle_transition_receipts.foundation.json"
    )

    registry = _load_json_object(effective_registry_path, "component registry")
    router_inventory = _load_json_object(effective_router_inventory_path, "component router inventory")
    proof_binding = _load_json_object(effective_proof_binding_path, "component proof binding")
    lifecycle_receipts = _load_json_object(effective_lifecycle_receipts_path, "component lifecycle transition receipts")

    components = _component_records(
        registry=registry,
        router_inventory=router_inventory,
        proof_binding=proof_binding,
        lifecycle_receipts=lifecycle_receipts,
    )
    bundles = _bundle_records(registry)
    live_execution_enabled = (
        _registry_guardrail(registry, "live_execution_enabled")
        or bool(router_inventory.get("live_execution_enabled"))
        or bool(proof_binding.get("live_execution_enabled"))
    )
    live_connector_send_enabled = (
        _registry_guardrail(registry, "live_connector_send_enabled")
        or bool(router_inventory.get("live_connector_send_enabled"))
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "read_model_id": READ_MODEL_ID,
        "route": READ_MODEL_ROUTE,
        "mode": str(registry.get("mode", "foundation")),
        "governed": True,
        "read_model_is_not_execution_authority": True,
        "live_execution_enabled": live_execution_enabled,
        "live_connector_send_enabled": live_connector_send_enabled,
        "terminal_closure_required": True,
        "source_refs": {
            "registry": _path_label(effective_registry_path, repo_root),
            "router_inventory": _path_label(effective_router_inventory_path, repo_root),
            "proof_binding": _path_label(effective_proof_binding_path, repo_root),
            "lifecycle_transition_receipts": _path_label(effective_lifecycle_receipts_path, repo_root),
        },
        "summary": {
            "component_count": len(components),
            "bundle_count": len(bundles),
            "lifecycle_receipt_count": sum(
                1 for component in components if component["lifecycle_receipt"]["receipt_id"]
            ),
            "proof_bound_count": sum(
                1 for component in components if component["proof_binding"]["state"] == "proof_bound"
            ),
            "awaiting_binding_count": sum(
                1 for component in components if component["proof_binding"]["state"] == "awaiting_binding"
            ),
            "bound_route_count": sum(component["route_binding"]["route_count"] for component in components),
            "blocked_component_count": sum(
                1 for component in components if component["mode"] == "blocked"
            ),
        },
        "components": components,
        "bundles": bundles,
        "validators": [
            "component_registry_validator",
            "component_lifecycle_transition_receipts_validator",
            "component_router_inventory_validator",
            "component_proof_binding_validator",
            "component_read_model_validator",
        ],
    }


def _component_records(
    *,
    registry: dict[str, Any],
    router_inventory: dict[str, Any],
    proof_binding: dict[str, Any],
    lifecycle_receipts: dict[str, Any],
) -> list[dict[str, Any]]:
    components = registry.get("components")
    if not isinstance(components, list):
        raise ComponentReadModelError("component registry components must be a list")
    route_bindings = _object_by_id(
        router_inventory.get("route_bindings"),
        id_field="component_id",
        source_label="component router inventory route_bindings",
    )
    proof_bindings = _object_by_id(
        proof_binding.get("component_bindings"),
        id_field="component_id",
        source_label="component proof binding component_bindings",
    )
    lifecycle_receipts_by_component = _object_by_id(
        lifecycle_receipts.get("transition_receipts"),
        id_field="component_id",
        source_label="component lifecycle transition receipts transition_receipts",
    )
    next_transitions_by_state = _next_transitions_by_state(lifecycle_receipts)
    records: list[dict[str, Any]] = []
    for component in components:
        if not isinstance(component, dict):
            raise ComponentReadModelError("component registry entries must be objects")
        component_id = _required_text(component, "id", "component registry entry")
        route_binding = route_bindings.get(component_id, {})
        component_proof_binding = proof_bindings.get(component_id, {})
        lifecycle_receipt = lifecycle_receipts_by_component.get(component_id)
        if lifecycle_receipt is None:
            raise ComponentReadModelError(f"component {component_id} is missing lifecycle transition receipt")
        proof_surface = component.get("proof_surface")
        if not isinstance(proof_surface, dict):
            raise ComponentReadModelError(f"component {component_id} proof_surface must be an object")
        authority = component.get("authority")
        if not isinstance(authority, dict):
            raise ComponentReadModelError(f"component {component_id} authority must be an object")
        health_source = component.get("health_source")
        if not isinstance(health_source, dict):
            raise ComponentReadModelError(f"component {component_id} health_source must be an object")
        current_state = _required_text(component, "lifecycle_state", f"component {component_id}")
        records.append(
            {
                "component_id": component_id,
                "name": _required_text(component, "name", f"component {component_id}"),
                "type": _required_text(component, "type", f"component {component_id}"),
                "mode": _required_text(component, "mode", f"component {component_id}"),
                "state": current_state,
                "wiring_state": _required_text(component, "wiring_state", f"component {component_id}"),
                "authority_level": _required_text(component, "authority_level", f"component {component_id}"),
                "authority": {key: bool(authority.get(key, False)) for key in sorted(authority)},
                "receipt_required": bool(component.get("receipt_required")),
                "lifecycle_receipt": _lifecycle_receipt_summary(
                    component_id=component_id,
                    current_state=current_state,
                    lifecycle_receipt=lifecycle_receipt,
                    next_transition_candidates=next_transitions_by_state.get(current_state, ()),
                ),
                "health": {
                    "status": "known" if health_source.get("type") != "none" else "unknown",
                    "source": dict(health_source),
                },
                "proof_surface": {
                    "status": str(proof_surface.get("status", "")),
                    "surface_id": proof_surface.get("surface_id"),
                },
                "route_binding": {
                    "state": str(route_binding.get("binding_state", "missing")),
                    "proof_surface_ids": _string_list(route_binding.get("proof_surface_ids")),
                    "route_count": len(_string_list(route_binding.get("expected_routes"))),
                },
                "proof_binding": {
                    "state": str(component_proof_binding.get("proof_binding_state", "missing")),
                    "required_surface_ids": _string_list(component_proof_binding.get("required_surface_ids")),
                    "inventory_surface_ids": _string_list(component_proof_binding.get("inventory_surface_ids")),
                    "runtime_witness_count": len(
                        _string_list(component_proof_binding.get("required_runtime_witnesses"))
                    ),
                    "evidence_file_count": len(
                        _string_list(component_proof_binding.get("required_evidence_files"))
                    ),
                },
                "dependencies": _string_list(component.get("dependencies")),
                "blocked_actions": _string_list(component.get("blocked_actions")),
                "owner_surface": _required_text(component, "owner_surface", f"component {component_id}"),
            }
        )
    return records


def _lifecycle_receipt_summary(
    *,
    component_id: str,
    current_state: str,
    lifecycle_receipt: dict[str, Any],
    next_transition_candidates: tuple[dict[str, Any], ...],
) -> dict[str, Any]:
    receipt_id = _required_text(lifecycle_receipt, "receipt_id", f"component {component_id} lifecycle receipt")
    target_state = _required_text(lifecycle_receipt, "to_state", f"component {component_id} lifecycle receipt")
    if target_state != current_state:
        raise ComponentReadModelError(
            f"component {component_id} lifecycle receipt target {target_state} does not match state {current_state}"
        )
    return {
        "receipt_id": receipt_id,
        "from_state": _required_text(lifecycle_receipt, "from_state", f"component {component_id} lifecycle receipt"),
        "to_state": target_state,
        "proof_state": _required_text(lifecycle_receipt, "proof_state", f"component {component_id} lifecycle receipt"),
        "evidence_refs": _string_list(lifecycle_receipt.get("evidence_refs")),
        "validator_refs": _string_list(lifecycle_receipt.get("required_validator_refs")),
        "operator_approval_required": bool(lifecycle_receipt.get("operator_approval_required")),
        "external_effect": bool(lifecycle_receipt.get("external_effect")),
        "transition_is_not_execution_authority": bool(
            lifecycle_receipt.get("receipt_is_not_execution_authority")
        ),
        "can_claim_terminal_closure": lifecycle_receipt.get("receipt_is_not_terminal_closure") is not True,
        "next_transition_candidates": [
            {
                "from_state": _required_text(candidate, "from_state", "allowed lifecycle transition"),
                "to_state": _required_text(candidate, "to_state", "allowed lifecycle transition"),
                "requires_evidence": bool(candidate.get("requires_evidence")),
                "operator_approval_required": bool(candidate.get("operator_approval_required")),
                "external_effect": bool(candidate.get("external_effect")),
            }
            for candidate in next_transition_candidates
        ],
    }


def _next_transitions_by_state(lifecycle_receipts: dict[str, Any]) -> dict[str, tuple[dict[str, Any], ...]]:
    transition_graph = lifecycle_receipts.get("allowed_transition_graph")
    if not isinstance(transition_graph, list):
        raise ComponentReadModelError("component lifecycle transition graph must be a list")
    transitions_by_state: dict[str, list[dict[str, Any]]] = {}
    for transition in transition_graph:
        if not isinstance(transition, dict):
            raise ComponentReadModelError("component lifecycle transition graph entries must be objects")
        from_state = _required_text(transition, "from_state", "allowed lifecycle transition")
        transitions_by_state.setdefault(from_state, []).append(transition)
    return {state: tuple(transitions) for state, transitions in transitions_by_state.items()}


def _bundle_records(registry: dict[str, Any]) -> list[dict[str, Any]]:
    bundles = registry.get("component_bundles")
    if not isinstance(bundles, list):
        raise ComponentReadModelError("component registry component_bundles must be a list")
    records: list[dict[str, Any]] = []
    for bundle in bundles:
        if not isinstance(bundle, dict):
            raise ComponentReadModelError("component bundle entries must be objects")
        bundle_id = _required_text(bundle, "bundle_id", "component bundle")
        records.append(
            {
                "bundle_id": bundle_id,
                "allowed_mode": _required_text(bundle, "allowed_mode", f"bundle {bundle_id}"),
                "component_count": len(_string_list(bundle.get("components"))),
                "blocked_actions": _string_list(bundle.get("blocked_actions")),
                "receipt_required": bool(bundle.get("receipt_required")),
                "bundle_is_not_execution_route": bool(bundle.get("bundle_is_not_execution_route")),
                "terminal_closure_required": bool(bundle.get("terminal_closure_required")),
            }
        )
    return records


def _object_by_id(
    value: object,
    *,
    id_field: str,
    source_label: str,
) -> dict[str, dict[str, Any]]:
    if not isinstance(value, list):
        raise ComponentReadModelError(f"{source_label} must be a list")
    result: dict[str, dict[str, Any]] = {}
    for entry in value:
        if not isinstance(entry, dict):
            raise ComponentReadModelError(f"{source_label} entries must be objects")
        entry_id = _required_text(entry, id_field, source_label)
        result[entry_id] = entry
    return result


def _required_text(payload: dict[str, Any], field_name: str, source_label: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value:
        raise ComponentReadModelError(f"{source_label} must carry text field {field_name}")
    return value


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _registry_guardrail(registry: dict[str, Any], guardrail_name: str) -> bool:
    guardrails = registry.get("registry_guardrails")
    if not isinstance(guardrails, dict):
        raise ComponentReadModelError("component registry guardrails must be an object")
    return bool(guardrails.get(guardrail_name))


def _load_json_object(path: Path, label: str) -> dict[str, Any]:
    if not path.exists():
        raise ComponentReadModelError(f"{label} file missing: {_path_label(path, _repo_root())}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ComponentReadModelError(f"{label} JSON parse failed") from exc
    if not isinstance(payload, dict):
        raise ComponentReadModelError(f"{label} root must be an object")
    return payload


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


def _repo_root() -> Path:
    for candidate in (Path.cwd(), *Path(__file__).resolve().parents):
        if (candidate / "examples" / "component_registry.foundation.json").exists():
            return candidate
    raise ComponentReadModelError("repository root with component registry could not be found")


def _path_label(path: Path, repo_root: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(repo_root).as_posix()
    except ValueError:
        return path.name
