"""Build the Component Harness route-family ownership readiness projection.

Purpose: explain which declared route families already have selected component
ownership and which remain blocked behind proof, lifecycle, and authority
witnesses.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: foundation component registry, router inventory, and proof
binding artifacts.
Invariants:
  - Ownership readiness is projection-only and never mutates source artifacts.
  - Route-family classification does not grant execution authority.
  - Live execution, connector calls, mutation, and terminal closure stay false.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
REPORT_ID = "component_route_family_ownership.foundation.v1"
DEFAULT_RECEIPT_EXPECTATIONS = (
    "component_route_family_ownership_receipt",
    "component_router_inventory_validation_receipt",
    "component_proof_binding_validation_receipt",
    "component_lifecycle_transition_receipt",
    "component_authority_envelope_witness",
    "authority_upgrade_witness",
    "authority_denial_receipt",
)


class ComponentRouteFamilyOwnershipError(ValueError):
    """Raised when route-family ownership readiness cannot be projected."""


def build_component_route_family_ownership_report(
    *,
    registry_path: Path | None = None,
    router_inventory_path: Path | None = None,
    proof_binding_path: Path | None = None,
) -> dict[str, Any]:
    """Return the deterministic route-family ownership readiness report.

    Input contract: optional paths to foundation registry, router inventory,
    and proof binding artifacts. Output contract: JSON-serializable readiness
    report. Error contract: raises ComponentRouteFamilyOwnershipError for
    missing, malformed, or inconsistent source artifacts.
    """

    repo_root = _repo_root()
    effective_registry_path = registry_path or repo_root / "examples" / "component_registry.foundation.json"
    effective_router_inventory_path = (
        router_inventory_path or repo_root / "examples" / "component_router_inventory.foundation.json"
    )
    effective_proof_binding_path = proof_binding_path or repo_root / "examples" / "component_proof_binding.foundation.json"

    registry = _load_json_object(effective_registry_path, "component registry")
    router_inventory = _load_json_object(effective_router_inventory_path, "component router inventory")
    proof_binding = _load_json_object(effective_proof_binding_path, "component proof binding")

    component_ids = _component_ids(registry)
    selected_bound_owners = _selected_bound_owners(router_inventory, component_ids)
    route_binding_states = _route_binding_states(router_inventory, component_ids)
    proof_bound_surfaces = _proof_bound_surfaces(proof_binding, component_ids)
    records = _ownership_records(
        router_inventory=router_inventory,
        component_ids=component_ids,
        selected_bound_owners=selected_bound_owners,
        route_binding_states=route_binding_states,
        proof_bound_surfaces=proof_bound_surfaces,
    )
    summary = _summary(records)
    return {
        "schema_version": SCHEMA_VERSION,
        "report_id": REPORT_ID,
        "mode": str(router_inventory.get("mode", "foundation")),
        "governed": True,
        "ownership_readiness_is_not_execution_authority": True,
        "live_execution_enabled": False,
        "live_connector_send_enabled": False,
        "can_execute": False,
        "can_mutate": False,
        "can_call_connector": False,
        "can_claim_terminal_closure": False,
        "terminal_closure_required": True,
        "source_refs": {
            "component_registry": _path_label(effective_registry_path, repo_root),
            "router_inventory": _path_label(effective_router_inventory_path, repo_root),
            "component_proof_binding": _path_label(effective_proof_binding_path, repo_root),
            "component_authority_envelope_witnesses": "examples/component_authority_envelope_witnesses.foundation.json",
            "proof_matrix": "docs/40_proof_coverage_matrix.md",
        },
        "summary": summary,
        "ownership_records": records,
        "expected_receipts": list(DEFAULT_RECEIPT_EXPECTATIONS),
        "outcome": "AwaitingEvidence" if summary["promotion_blocked_count"] else "SolvedUnverified",
        "validators": [
            "component_route_family_ownership_validator",
            "component_route_family_ownership_tests",
            "component_router_inventory_validator",
            "component_proof_binding_validator",
            "component_registry_validator",
        ],
        "next_action": "Promote blocked route families only after route binding, proof, lifecycle, and authority witnesses exist.",
    }


def _ownership_records(
    *,
    router_inventory: dict[str, Any],
    component_ids: set[str],
    selected_bound_owners: dict[str, tuple[str, ...]],
    route_binding_states: dict[tuple[str, str], str],
    proof_bound_surfaces: dict[str, tuple[str, ...]],
) -> list[dict[str, Any]]:
    classifications = router_inventory.get("route_family_classifications")
    if not isinstance(classifications, list):
        raise ComponentRouteFamilyOwnershipError("router inventory route_family_classifications must be a list")
    records: list[dict[str, Any]] = []
    seen_surface_ids: set[str] = set()
    for classification in classifications:
        if not isinstance(classification, dict):
            raise ComponentRouteFamilyOwnershipError("route family classifications must be objects")
        surface_id = _required_text(classification, "surface_id", "route family classification")
        if surface_id in seen_surface_ids:
            raise ComponentRouteFamilyOwnershipError(f"duplicate route family classification {surface_id}")
        seen_surface_ids.add(surface_id)
        records.append(
            _ownership_record(
                classification=classification,
                component_ids=component_ids,
                selected_bound_owners=selected_bound_owners,
                route_binding_states=route_binding_states,
                proof_bound_surfaces=proof_bound_surfaces,
            )
        )
    return sorted(records, key=lambda record: record["surface_id"])


def _ownership_record(
    *,
    classification: dict[str, Any],
    component_ids: set[str],
    selected_bound_owners: dict[str, tuple[str, ...]],
    route_binding_states: dict[tuple[str, str], str],
    proof_bound_surfaces: dict[str, tuple[str, ...]],
) -> dict[str, Any]:
    surface_id = _required_text(classification, "surface_id", "route family classification")
    candidate_component_ids = _string_list(classification.get("component_ids"))
    missing_components = sorted(set(candidate_component_ids) - component_ids)
    if missing_components:
        raise ComponentRouteFamilyOwnershipError(
            f"route family {surface_id} references unregistered components {missing_components}"
        )

    selected_bound_component_ids = selected_bound_owners.get(surface_id, tuple())
    candidate_proof_bound_component_ids = tuple(
        component_id
        for component_id in candidate_component_ids
        if surface_id in proof_bound_surfaces.get(component_id, tuple())
    )
    component_route_binding_states = tuple(
        {
            "component_id": component_id,
            "binding_state": route_binding_states.get((component_id, surface_id), "unbound"),
            "proof_surface_present_in_route_binding": (component_id, surface_id) in route_binding_states,
            "route_binding_is_bound": route_binding_states.get((component_id, surface_id)) == "bound",
        }
        for component_id in candidate_component_ids
    )
    binding_level = _required_text(classification, "binding_level", f"route family {surface_id}")
    readiness_state = _readiness_state(
        binding_level=binding_level,
        selected_bound_component_ids=selected_bound_component_ids,
        candidate_proof_bound_component_ids=candidate_proof_bound_component_ids,
    )
    promotion_blockers = _promotion_blockers(
        readiness_state=readiness_state,
        surface_id=surface_id,
        sample_routes=_string_list(classification.get("sample_routes")),
        candidate_proof_bound_component_ids=candidate_proof_bound_component_ids,
    )
    return {
        "surface_id": surface_id,
        "binding_level": binding_level,
        "readiness_state": readiness_state,
        "component_lane": _required_text(classification, "component_lane", f"route family {surface_id}"),
        "component_ids": list(candidate_component_ids),
        "selected_bound_component_ids": list(selected_bound_component_ids),
        "candidate_proof_bound_component_ids": list(candidate_proof_bound_component_ids),
        "component_route_binding_states": list(component_route_binding_states),
        "declared_route_count": int(classification.get("declared_route_count", 0)),
        "sample_routes": list(_string_list(classification.get("sample_routes"))),
        "promotion_blockers": list(promotion_blockers),
        "required_next_evidence": list(_required_next_evidence(readiness_state)),
        "blocked_actions": list(_string_list(classification.get("blocked_actions"))),
        "ownership_is_not_execution_authority": True,
        "can_enable_live_action": False,
        "notes": _notes(readiness_state),
    }


def _readiness_state(
    *,
    binding_level: str,
    selected_bound_component_ids: tuple[str, ...],
    candidate_proof_bound_component_ids: tuple[str, ...],
) -> str:
    if binding_level == "selected_component_bound" and selected_bound_component_ids:
        return "selected_component_bound"
    if candidate_proof_bound_component_ids:
        return "blocked_needs_route_binding_witness"
    return "blocked_needs_proof_binding"


def _promotion_blockers(
    *,
    readiness_state: str,
    surface_id: str,
    sample_routes: tuple[str, ...],
    candidate_proof_bound_component_ids: tuple[str, ...],
) -> tuple[str, ...]:
    if readiness_state == "selected_component_bound":
        return tuple()
    blockers = [
        "missing_selected_component_route_binding",
        "missing_lifecycle_transition_receipt",
        "missing_authority_upgrade_witness",
    ]
    if not candidate_proof_bound_component_ids:
        blockers.append("missing_component_proof_surface_binding")
    else:
        blockers.append("requires_product_specific_route_ownership_decision")
    if _is_generic_connector_surface(surface_id, sample_routes):
        blockers.append("generic_connector_surface_not_product_specific_authority")
    return tuple(blockers)


def _required_next_evidence(readiness_state: str) -> tuple[str, ...]:
    if readiness_state == "selected_component_bound":
        return (
            "preserve_non_execution_route_binding",
            "preserve_terminal_closure_denial",
        )
    return (
        "component_route_binding_receipt",
        "component_proof_surface_binding",
        "component_lifecycle_transition_receipt",
        "authority_upgrade_witness",
        "operator_approval_if_external_effect",
    )


def _notes(readiness_state: str) -> str:
    if readiness_state == "selected_component_bound":
        return "Route family already has selected component ownership, but ownership does not grant execution authority."
    if readiness_state == "blocked_needs_route_binding_witness":
        return "Route family has candidate proof evidence but still needs route-binding, lifecycle, and authority witnesses before ownership promotion."
    return "Route family remains platform-classified and needs proof-surface binding before ownership promotion."


def _summary(records: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "route_family_count": len(records),
        "declared_route_count": sum(int(record["declared_route_count"]) for record in records),
        "selected_component_bound_count": sum(
            1 for record in records if record["readiness_state"] == "selected_component_bound"
        ),
        "platform_family_classified_count": sum(
            1 for record in records if record["binding_level"] == "platform_family_classified"
        ),
        "promotion_blocked_count": sum(
            1 for record in records if str(record["readiness_state"]).startswith("blocked_")
        ),
        "proof_binding_gap_count": sum(
            1
            for record in records
            if "missing_component_proof_surface_binding" in _string_list(record.get("promotion_blockers"))
        ),
        "route_binding_gap_count": sum(
            1
            for record in records
            if "missing_selected_component_route_binding" in _string_list(record.get("promotion_blockers"))
        ),
        "generic_connector_boundary_count": sum(
            1
            for record in records
            if "generic_connector_surface_not_product_specific_authority" in _string_list(record.get("promotion_blockers"))
        ),
        "live_action_enabled_count": sum(1 for record in records if record.get("can_enable_live_action") is True),
        "terminal_closure_claim_count": sum(
            1
            for record in records
            if "terminal_closure" not in _string_list(record.get("blocked_actions"))
        ),
    }


def _component_ids(registry: dict[str, Any]) -> set[str]:
    components = registry.get("components")
    if not isinstance(components, list):
        raise ComponentRouteFamilyOwnershipError("component registry components must be a list")
    result: set[str] = set()
    for component in components:
        if not isinstance(component, dict):
            raise ComponentRouteFamilyOwnershipError("component registry entries must be objects")
        component_id = _required_text(component, "id", "component registry entry")
        if component_id in result:
            raise ComponentRouteFamilyOwnershipError(f"duplicate component id {component_id}")
        result.add(component_id)
    return result


def _selected_bound_owners(
    router_inventory: dict[str, Any],
    component_ids: set[str],
) -> dict[str, tuple[str, ...]]:
    owners: dict[str, list[str]] = {}
    for binding in _route_bindings(router_inventory):
        component_id = _required_text(binding, "component_id", "route binding")
        if component_id not in component_ids:
            raise ComponentRouteFamilyOwnershipError(f"route binding references unregistered component {component_id}")
        if binding.get("binding_state") != "bound":
            continue
        for surface_id in _string_list(binding.get("proof_surface_ids")):
            owners.setdefault(surface_id, []).append(component_id)
    return {surface_id: tuple(sorted(set(surface_owners))) for surface_id, surface_owners in owners.items()}


def _route_binding_states(
    router_inventory: dict[str, Any],
    component_ids: set[str],
) -> dict[tuple[str, str], str]:
    states: dict[tuple[str, str], str] = {}
    for binding in _route_bindings(router_inventory):
        component_id = _required_text(binding, "component_id", "route binding")
        if component_id not in component_ids:
            raise ComponentRouteFamilyOwnershipError(f"route binding references unregistered component {component_id}")
        binding_state = _required_text(binding, "binding_state", f"route binding {component_id}")
        for surface_id in _string_list(binding.get("proof_surface_ids")):
            states[(component_id, surface_id)] = binding_state
    return states


def _proof_bound_surfaces(
    proof_binding: dict[str, Any],
    component_ids: set[str],
) -> dict[str, tuple[str, ...]]:
    component_bindings = proof_binding.get("component_bindings")
    if not isinstance(component_bindings, list):
        raise ComponentRouteFamilyOwnershipError("component proof binding component_bindings must be a list")
    result: dict[str, tuple[str, ...]] = {}
    for binding in component_bindings:
        if not isinstance(binding, dict):
            raise ComponentRouteFamilyOwnershipError("component proof binding entries must be objects")
        component_id = _required_text(binding, "component_id", "component proof binding")
        if component_id not in component_ids:
            raise ComponentRouteFamilyOwnershipError(f"proof binding references unregistered component {component_id}")
        if binding.get("proof_binding_state") != "proof_bound":
            result[component_id] = tuple()
            continue
        surfaces = sorted(
            set(_string_list(binding.get("required_surface_ids")))
            | set(_string_list(binding.get("inventory_surface_ids")))
        )
        result[component_id] = tuple(surfaces)
    return result


def _route_bindings(router_inventory: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    bindings = router_inventory.get("route_bindings")
    if not isinstance(bindings, list):
        raise ComponentRouteFamilyOwnershipError("component router inventory route_bindings must be a list")
    result: list[dict[str, Any]] = []
    for binding in bindings:
        if not isinstance(binding, dict):
            raise ComponentRouteFamilyOwnershipError("component router inventory route_bindings entries must be objects")
        result.append(binding)
    return tuple(result)


def _is_generic_connector_surface(surface_id: str, sample_routes: tuple[str, ...]) -> bool:
    if "connector" in surface_id:
        return True
    return any("/connectors" in route for route in sample_routes)


def _load_json_object(path: Path, label: str) -> dict[str, Any]:
    if not path.exists():
        raise ComponentRouteFamilyOwnershipError(f"{label} file missing: {_path_label(path, _repo_root())}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ComponentRouteFamilyOwnershipError(f"{label} JSON parse failed") from exc
    if not isinstance(payload, dict):
        raise ComponentRouteFamilyOwnershipError(f"{label} JSON root must be an object")
    return payload


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


def _required_text(payload: dict[str, Any], field_name: str, label: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value:
        raise ComponentRouteFamilyOwnershipError(f"{label} must carry {field_name}")
    return value


def _string_list(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return tuple()
    return tuple(str(item) for item in value)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _path_label(path: Path, repo_root: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(repo_root).as_posix()
    except ValueError:
        return path.name
