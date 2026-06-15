"""Build the Component Harness graph projection.

Purpose: join component registry, read-model, request simulation, and autopsy
signals into one dependency and request-path graph.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: component read model, request simulator, autopsy projection, and
foundation component registry.
Invariants:
  - The graph is projection-only and never mutates source artifacts.
  - Live execution, connector calls, mutation, and terminal closure stay false.
  - Every edge endpoint must reference a registered component.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from mcoi_runtime.app.component_autopsy import (
    ComponentAutopsyError,
    build_foundation_component_autopsies,
)
from mcoi_runtime.app.component_read_model import (
    ComponentReadModelError,
    build_component_read_model,
)
from mcoi_runtime.app.component_request_simulator import (
    ComponentRequestSimulationError,
    foundation_component_request_simulations,
)


SCHEMA_VERSION = 1
GRAPH_ID = "component_graph.foundation.v1"
DEFAULT_RECEIPT_EXPECTATIONS = (
    "component_graph_projection_receipt",
    "component_registry_validation_receipt",
    "component_read_model_validation_receipt",
    "component_request_simulation_receipt",
    "component_autopsy_receipt",
    "authority_denial_receipt",
)


class ComponentGraphError(ValueError):
    """Raised when the component graph cannot be built safely."""


def build_component_graph(
    *,
    registry_path: Path | None = None,
    read_model: dict[str, Any] | None = None,
    simulations: list[dict[str, Any]] | None = None,
    autopsies: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return the deterministic foundation Component Harness graph.

    Input contract: optional registry path and optional prebuilt read model,
    simulations, and autopsies. Output contract: JSON-serializable graph.
    Error contract: raises ComponentGraphError for malformed sources,
    unknown edge endpoints, or duplicate component identities.
    """

    repo_root = _repo_root()
    effective_registry_path = registry_path or repo_root / "examples" / "component_registry.foundation.json"
    registry = _load_json_object(effective_registry_path, "component registry")
    source_read_model = read_model or _build_read_model()
    source_simulations = simulations or _build_simulations()
    source_autopsies = autopsies or _build_autopsies()

    component_index = _component_index(source_read_model)
    bundle_memberships = _bundle_memberships(registry, component_index)
    request_path_index = _request_path_index(source_simulations, component_index)
    autopsy_index = _autopsy_index(source_autopsies, component_index)
    dependency_edges = _dependency_edges(component_index)
    request_path_edges = _request_path_edges(source_simulations, component_index)
    edges = _ordered_edges((*dependency_edges, *request_path_edges))
    _validate_edge_endpoints(edges, component_index)
    nodes = _nodes(
        component_index=component_index,
        edges=edges,
        bundle_memberships=bundle_memberships,
        request_path_index=request_path_index,
        autopsy_index=autopsy_index,
    )
    blocked_paths = _blocked_paths(autopsy_index)
    return {
        "schema_version": SCHEMA_VERSION,
        "graph_id": GRAPH_ID,
        "mode": str(source_read_model.get("mode", "foundation")),
        "governed": True,
        "graph_is_not_execution_authority": True,
        "live_execution_enabled": False,
        "live_connector_send_enabled": False,
        "can_execute": False,
        "can_mutate": False,
        "can_call_connector": False,
        "can_claim_terminal_closure": False,
        "terminal_closure_required": True,
        "source_refs": {
            "registry": _path_label(effective_registry_path, repo_root),
            "read_model": "examples/component_read_model.foundation.json",
            "request_simulations": "mcoi_runtime.app.component_request_simulator.foundation_component_request_simulations",
            "autopsies": "mcoi_runtime.app.component_autopsy.build_foundation_component_autopsies",
        },
        "summary": {
            "component_count": len(nodes),
            "edge_count": len(edges),
            "dependency_edge_count": sum(1 for edge in edges if edge["relation"] == "depends_on"),
            "request_path_edge_count": sum(1 for edge in edges if edge["relation"] == "request_path_next"),
            "bundle_membership_count": len(bundle_memberships),
            "blocked_component_count": sum(1 for node in nodes if node["mode"] == "blocked"),
            "proof_bound_count": sum(1 for node in nodes if node["proof_binding_state"] == "proof_bound"),
            "awaiting_binding_count": sum(1 for node in nodes if node["proof_binding_state"] != "proof_bound"),
            "cycle_count": _cycle_count(edges, set(component_index)),
        },
        "nodes": nodes,
        "edges": edges,
        "bundle_memberships": bundle_memberships,
        "blocked_paths": blocked_paths,
        "expected_receipts": list(DEFAULT_RECEIPT_EXPECTATIONS),
        "validators": [
            "component_graph_validator",
            "component_graph_tests",
            "component_registry_validator",
            "component_read_model_validator",
            "component_request_simulation_validator",
            "component_autopsy_validator",
        ],
        "next_action": "Feed component graph into readiness dashboard reporting without enabling live execution.",
    }


def _build_read_model() -> dict[str, Any]:
    try:
        return build_component_read_model()
    except ComponentReadModelError as exc:
        raise ComponentGraphError(str(exc)) from exc


def _build_simulations() -> list[dict[str, Any]]:
    try:
        return foundation_component_request_simulations()
    except ComponentRequestSimulationError as exc:
        raise ComponentGraphError(str(exc)) from exc


def _build_autopsies() -> list[dict[str, Any]]:
    try:
        return build_foundation_component_autopsies()
    except ComponentAutopsyError as exc:
        raise ComponentGraphError(str(exc)) from exc


def _component_index(read_model: dict[str, Any]) -> dict[str, dict[str, Any]]:
    components = read_model.get("components")
    if not isinstance(components, list):
        raise ComponentGraphError("read model components must be a list")
    result: dict[str, dict[str, Any]] = {}
    for component in components:
        if not isinstance(component, dict):
            raise ComponentGraphError("read model component entries must be objects")
        component_id = component.get("component_id")
        if not isinstance(component_id, str) or not component_id:
            raise ComponentGraphError("read model component entries must carry component_id")
        if component_id in result:
            raise ComponentGraphError(f"duplicate component_id {component_id}")
        result[component_id] = component
    return result


def _bundle_memberships(
    registry: dict[str, Any],
    component_index: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    bundles = registry.get("component_bundles")
    if not isinstance(bundles, list):
        raise ComponentGraphError("component registry component_bundles must be a list")
    memberships: list[dict[str, Any]] = []
    for bundle in bundles:
        if not isinstance(bundle, dict):
            raise ComponentGraphError("component bundle entries must be objects")
        bundle_id = _required_text(bundle, "bundle_id", "component bundle")
        for component_id in _string_list(bundle.get("components")):
            if component_id not in component_index:
                raise ComponentGraphError(f"bundle {bundle_id} references unregistered component {component_id}")
            memberships.append(
                {
                    "bundle_id": bundle_id,
                    "component_id": component_id,
                    "allowed_mode": str(bundle.get("allowed_mode", "")),
                    "membership_is_not_execution_authority": True,
                }
            )
    return memberships


def _request_path_index(
    simulations: list[dict[str, Any]],
    component_index: dict[str, dict[str, Any]],
) -> dict[str, tuple[str, ...]]:
    result: dict[str, list[str]] = {component_id: [] for component_id in component_index}
    for simulation in simulations:
        if not isinstance(simulation, dict):
            raise ComponentGraphError("simulation entries must be objects")
        intent = _required_text(simulation, "intent", "component request simulation")
        for component_id in _string_list(simulation.get("selected_component_ids")):
            if component_id not in component_index:
                raise ComponentGraphError(f"simulation {intent} references unregistered component {component_id}")
            result[component_id].append(intent)
    return {component_id: _ordered_unique(intents) for component_id, intents in result.items()}


def _autopsy_index(
    autopsies: list[dict[str, Any]],
    component_index: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for autopsy in autopsies:
        if not isinstance(autopsy, dict):
            raise ComponentGraphError("autopsy entries must be objects")
        component_id = _required_text(autopsy, "component_id", "component autopsy")
        if component_id not in component_index:
            raise ComponentGraphError(f"autopsy references unregistered component {component_id}")
        result[component_id] = autopsy
    missing = sorted(set(component_index) - set(result))
    if missing:
        raise ComponentGraphError(f"autopsy projection missing components {missing}")
    return result


def _dependency_edges(component_index: dict[str, dict[str, Any]]) -> tuple[dict[str, Any], ...]:
    edges: list[dict[str, Any]] = []
    for component_id in sorted(component_index):
        component = component_index[component_id]
        for dependency_id in _string_list(component.get("dependencies")):
            edges.append(
                {
                    "edge_id": f"edge.{component_id}.depends_on.{dependency_id}",
                    "from_component_id": component_id,
                    "to_component_id": dependency_id,
                    "relation": "depends_on",
                    "source": "component_registry.dependencies",
                    "scenario_refs": [],
                    "edge_is_not_execution_authority": True,
                }
            )
    return tuple(edges)


def _request_path_edges(
    simulations: list[dict[str, Any]],
    component_index: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], ...]:
    edge_refs: dict[tuple[str, str], list[str]] = {}
    for simulation in simulations:
        if not isinstance(simulation, dict):
            raise ComponentGraphError("simulation entries must be objects")
        intent = _required_text(simulation, "intent", "component request simulation")
        selected_component_ids = _string_list(simulation.get("selected_component_ids"))
        for component_id in selected_component_ids:
            if component_id not in component_index:
                raise ComponentGraphError(f"simulation {intent} references unregistered component {component_id}")
        for from_component_id, to_component_id in zip(selected_component_ids, selected_component_ids[1:]):
            edge_refs.setdefault((from_component_id, to_component_id), []).append(intent)
    return tuple(
        {
            "edge_id": f"edge.{from_component_id}.request_path_next.{to_component_id}",
            "from_component_id": from_component_id,
            "to_component_id": to_component_id,
            "relation": "request_path_next",
            "source": "component_request_simulation.selected_component_ids",
            "scenario_refs": list(_ordered_unique(intents)),
            "edge_is_not_execution_authority": True,
        }
        for (from_component_id, to_component_id), intents in sorted(edge_refs.items())
    )


def _ordered_edges(edges: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(edges, key=lambda edge: (str(edge["relation"]), str(edge["from_component_id"]), str(edge["to_component_id"])))


def _validate_edge_endpoints(edges: list[dict[str, Any]], component_index: dict[str, dict[str, Any]]) -> None:
    component_ids = set(component_index)
    for edge in edges:
        from_component_id = str(edge.get("from_component_id", ""))
        to_component_id = str(edge.get("to_component_id", ""))
        if from_component_id not in component_ids or to_component_id not in component_ids:
            raise ComponentGraphError(f"edge {edge.get('edge_id')} has unregistered endpoint")


def _nodes(
    *,
    component_index: dict[str, dict[str, Any]],
    edges: list[dict[str, Any]],
    bundle_memberships: list[dict[str, Any]],
    request_path_index: dict[str, tuple[str, ...]],
    autopsy_index: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    dependency_count_by_component = _edge_count_by_from(edges, "depends_on")
    dependent_count_by_component = _edge_count_by_to(edges, "depends_on")
    request_path_count_by_component = _request_path_count_by_component(request_path_index)
    bundle_count_by_component = _membership_count_by_component(bundle_memberships)
    nodes: list[dict[str, Any]] = []
    for component_id in sorted(component_index):
        component = component_index[component_id]
        proof_binding = _object_or_empty(component.get("proof_binding"))
        route_binding = _object_or_empty(component.get("route_binding"))
        autopsy = autopsy_index[component_id]
        nodes.append(
            {
                "component_id": component_id,
                "name": str(component.get("name", "")),
                "type": str(component.get("type", "")),
                "mode": str(component.get("mode", "")),
                "state": str(component.get("state", "")),
                "wiring_state": str(component.get("wiring_state", "")),
                "authority_level": str(component.get("authority_level", "")),
                "proof_binding_state": str(proof_binding.get("state", "")),
                "route_binding_state": str(route_binding.get("state", "")),
                "route_count": int(route_binding.get("route_count", 0)),
                "dependency_count": dependency_count_by_component.get(component_id, 0),
                "dependent_count": dependent_count_by_component.get(component_id, 0),
                "bundle_count": bundle_count_by_component.get(component_id, 0),
                "request_path_count": request_path_count_by_component.get(component_id, 0),
                "blocked_action_count": len(_string_list(component.get("blocked_actions"))),
                "missing_evidence_count": len(_string_list(autopsy.get("missing_evidence"))),
                "autopsy_outcome": str(autopsy.get("outcome", "")),
            }
        )
    return nodes


def _blocked_paths(autopsy_index: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    blocked_paths: list[dict[str, Any]] = []
    for component_id in sorted(autopsy_index):
        autopsy = autopsy_index[component_id]
        blocked_paths.append(
            {
                "component_id": component_id,
                "outcome": str(autopsy.get("outcome", "")),
                "forbidden_actions": _string_list(autopsy.get("forbidden_actions")),
                "missing_evidence": _string_list(autopsy.get("missing_evidence")),
                "next_transition_targets": [
                    str(candidate.get("to_state", ""))
                    for candidate in autopsy.get("next_transition_candidates", [])
                    if isinstance(candidate, dict)
                ],
                "terminal_closure_blocked": autopsy.get("can_claim_terminal_closure") is False,
            }
        )
    return blocked_paths


def _edge_count_by_from(edges: list[dict[str, Any]], relation: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for edge in edges:
        if edge.get("relation") == relation:
            component_id = str(edge.get("from_component_id", ""))
            counts[component_id] = counts.get(component_id, 0) + 1
    return counts


def _edge_count_by_to(edges: list[dict[str, Any]], relation: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for edge in edges:
        if edge.get("relation") == relation:
            component_id = str(edge.get("to_component_id", ""))
            counts[component_id] = counts.get(component_id, 0) + 1
    return counts


def _request_path_count_by_component(request_path_index: dict[str, tuple[str, ...]]) -> dict[str, int]:
    return {component_id: len(intents) for component_id, intents in request_path_index.items()}


def _membership_count_by_component(bundle_memberships: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for membership in bundle_memberships:
        component_id = str(membership.get("component_id", ""))
        counts[component_id] = counts.get(component_id, 0) + 1
    return counts


def _cycle_count(edges: list[dict[str, Any]], component_ids: set[str]) -> int:
    adjacency: dict[str, list[str]] = {component_id: [] for component_id in component_ids}
    for edge in edges:
        if edge.get("relation") != "depends_on":
            continue
        adjacency[str(edge["from_component_id"])].append(str(edge["to_component_id"]))

    visiting: set[str] = set()
    visited: set[str] = set()
    cycles = 0

    def visit(component_id: str) -> None:
        nonlocal cycles
        if component_id in visiting:
            cycles += 1
            return
        if component_id in visited:
            return
        visiting.add(component_id)
        for neighbor_id in adjacency.get(component_id, []):
            visit(neighbor_id)
        visiting.remove(component_id)
        visited.add(component_id)

    for component_id in sorted(component_ids):
        visit(component_id)
    return cycles


def _load_json_object(path: Path, label: str) -> dict[str, Any]:
    if not path.exists():
        raise ComponentGraphError(f"{label} file missing: {_path_label(path, _repo_root())}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ComponentGraphError(f"{label} JSON parse failed") from exc
    if not isinstance(payload, dict):
        raise ComponentGraphError(f"{label} root must be an object")
    return payload


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


def _object_or_empty(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _required_text(payload: dict[str, Any], field_name: str, source_label: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value:
        raise ComponentGraphError(f"{source_label} must carry text field {field_name}")
    return value


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _ordered_unique(values: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            ordered.append(value)
    return tuple(ordered)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _path_label(path: Path, repo_root: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(repo_root).as_posix()
    except ValueError:
        return path.name
