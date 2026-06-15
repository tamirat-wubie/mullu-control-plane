"""Compile Component Harness bundles into preview-only readiness reports.

Purpose: join registry bundle declarations, component read-model posture, and
request simulations into a deterministic product-bundle compilation report.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: component registry, component read model, and request simulator.
Invariants:
  - Bundle compilation is not execution authority.
  - Live execution, connector calls, mutation, and terminal closure stay false.
  - Unknown bundles, unregistered components, and live-authority drift fail
    closed with explicit errors.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from mcoi_runtime.app.component_read_model import (
    ComponentReadModelError,
    LIVE_AUTHORITY_FLAGS,
    build_component_read_model,
)
from mcoi_runtime.app.component_request_simulator import (
    ComponentRequestSimulationError,
    foundation_component_request_simulations,
)


SCHEMA_VERSION = 1
DEFAULT_BUNDLE_ID = "personal_assistant_v0"
DEFAULT_RECEIPT_EXPECTATIONS = (
    "component_bundle_compilation_receipt",
    "component_registry_validation_receipt",
    "component_read_model_validation_receipt",
    "component_request_simulation_receipt",
    "authority_denial_receipt",
)
FORBIDDEN_BUNDLE_CLAIMS = (
    "production_ready",
    "customer_ready",
    "live_gmail_enabled",
    "autonomous_execution",
    "compliance_certified",
    "enterprise_sla",
    "nested_mind_live",
)


class ComponentBundleCompilationError(ValueError):
    """Raised when a component bundle cannot be compiled safely."""


def compile_component_bundle(
    bundle_id: str = DEFAULT_BUNDLE_ID,
    *,
    registry_path: Path | None = None,
    read_model: dict[str, Any] | None = None,
    simulations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return a deterministic, non-executing bundle compilation report.

    Input contract: a registered bundle ID plus optional source artifacts.
    Output contract: JSON-serializable readiness report.
    Error contract: raises ComponentBundleCompilationError when the bundle,
    component references, or source artifacts are missing or unsafe.
    """

    normalized_bundle_id = _required_text(bundle_id, "bundle_id")
    repo_root = _repo_root()
    effective_registry_path = registry_path or repo_root / "examples" / "component_registry.foundation.json"
    registry = _load_json_object(effective_registry_path, "component registry")
    source_read_model = read_model or _build_read_model()
    source_simulations = simulations or _build_simulations()

    bundle = _bundle_by_id(registry, normalized_bundle_id)
    component_ids = _string_list(bundle.get("components"))
    if not component_ids:
        raise ComponentBundleCompilationError(f"bundle {normalized_bundle_id} must list components")

    component_index = _component_index(source_read_model)
    missing_components = sorted(set(component_ids) - set(component_index))
    if missing_components:
        raise ComponentBundleCompilationError(
            f"bundle {normalized_bundle_id} references unregistered components {missing_components}"
        )

    selected_components = [component_index[component_id] for component_id in component_ids]
    _reject_live_authority(selected_components, normalized_bundle_id)

    relevant_simulations = _relevant_simulations(source_simulations, component_ids)
    blocked_actions = _ordered_unique(
        (
            *_string_list(bundle.get("blocked_actions")),
            *(
                action
                for component in selected_components
                for action in _string_list(component.get("blocked_actions"))
            ),
            *(
                action
                for simulation in relevant_simulations
                for action in _string_list(simulation.get("blocked_actions"))
            ),
            "terminal_closure",
        )
    )
    blocked_component_ids = _ordered_unique(
        (
            *(
                str(component["component_id"])
                for component in selected_components
                if component.get("mode") == "blocked"
                or component.get("proof_binding", {}).get("state") == "awaiting_binding"
            ),
            *(
                component_id
                for simulation in relevant_simulations
                for component_id in _string_list(simulation.get("blocked_component_ids"))
            ),
        )
    )
    expected_receipts = _ordered_unique(
        (
            *DEFAULT_RECEIPT_EXPECTATIONS,
            *(
                receipt
                for simulation in relevant_simulations
                for receipt in _string_list(simulation.get("expected_receipts"))
            ),
        )
    )
    missing_evidence = _ordered_unique(
        evidence
        for simulation in relevant_simulations
        for evidence in _string_list(simulation.get("needed_evidence"))
    )
    blocked_simulation_count = sum(
        1 for simulation in relevant_simulations if simulation.get("outcome") == "GovernanceBlocked"
    )
    awaiting_simulation_count = sum(
        1 for simulation in relevant_simulations if simulation.get("outcome") == "AwaitingEvidence"
    )
    outcome = _bundle_outcome(blocked_simulation_count, awaiting_simulation_count)
    reason = _bundle_reason(
        bundle_id=normalized_bundle_id,
        blocked_simulation_count=blocked_simulation_count,
        awaiting_simulation_count=awaiting_simulation_count,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "compilation_id": f"component_bundle_compilation.{normalized_bundle_id}.v1",
        "bundle_id": normalized_bundle_id,
        "name": _required_text(bundle.get("name"), f"bundle {normalized_bundle_id} name"),
        "mode": str(registry.get("mode", "foundation")),
        "allowed_mode": _required_text(bundle.get("allowed_mode"), f"bundle {normalized_bundle_id} allowed_mode"),
        "governed": True,
        "compiler_is_not_execution_authority": True,
        "bundle_is_not_execution_route": bool(bundle.get("bundle_is_not_execution_route")),
        "live_execution_enabled": False,
        "live_connector_send_enabled": False,
        "can_execute": False,
        "can_mutate": False,
        "can_call_connector": False,
        "can_claim_terminal_closure": False,
        "terminal_closure_required": True,
        "receipt_required": bool(bundle.get("receipt_required")),
        "component_ids": component_ids,
        "component_states": _component_states(selected_components),
        "summary": {
            "component_count": len(component_ids),
            "proof_bound_component_count": sum(
                1 for component in selected_components if component.get("proof_binding", {}).get("state") == "proof_bound"
            ),
            "awaiting_binding_component_count": sum(
                1
                for component in selected_components
                if component.get("proof_binding", {}).get("state") == "awaiting_binding"
            ),
            "route_count": sum(
                int(component.get("route_binding", {}).get("route_count", 0)) for component in selected_components
            ),
            "blocked_action_count": len(blocked_actions),
            "simulation_count": len(relevant_simulations),
            "blocked_simulation_count": blocked_simulation_count,
            "approval_required_simulation_count": sum(
                1 for simulation in relevant_simulations if simulation.get("approval_required") is True
            ),
            "preview_available": True,
            "live_action_ready": False,
        },
        "blocked_component_ids": list(blocked_component_ids),
        "blocked_actions": list(blocked_actions),
        "matching_simulations": _simulation_summaries(relevant_simulations),
        "expected_receipts": list(expected_receipts),
        "missing_evidence": list(missing_evidence),
        "forbidden_claims": list(FORBIDDEN_BUNDLE_CLAIMS),
        "outcome": outcome,
        "reason": reason,
        "source_refs": {
            "registry": _path_label(effective_registry_path, repo_root),
            "read_model": "examples/component_read_model.foundation.json",
            "request_simulations": "mcoi_runtime.app.component_request_simulator.foundation_component_request_simulations",
        },
        "validators": [
            "component_bundle_compiler_validator",
            "component_bundle_compiler_tests",
            "component_registry_validator",
            "component_read_model_validator",
            "component_request_simulation_validator",
        ],
    }


def compile_foundation_component_bundles() -> list[dict[str, Any]]:
    """Return deterministic compilation reports for every foundation bundle."""

    registry = _load_json_object(_repo_root() / "examples" / "component_registry.foundation.json", "component registry")
    bundles = registry.get("component_bundles")
    if not isinstance(bundles, list):
        raise ComponentBundleCompilationError("component registry component_bundles must be a list")
    read_model = _build_read_model()
    simulations = _build_simulations()
    return [
        compile_component_bundle(
            _required_text(bundle.get("bundle_id"), "bundle_id"),
            read_model=read_model,
            simulations=simulations,
        )
        for bundle in bundles
        if isinstance(bundle, dict)
    ]


def _build_read_model() -> dict[str, Any]:
    try:
        return build_component_read_model()
    except ComponentReadModelError as exc:
        raise ComponentBundleCompilationError(str(exc)) from exc


def _build_simulations() -> list[dict[str, Any]]:
    try:
        return foundation_component_request_simulations()
    except ComponentRequestSimulationError as exc:
        raise ComponentBundleCompilationError(str(exc)) from exc


def _bundle_by_id(registry: dict[str, Any], bundle_id: str) -> dict[str, Any]:
    bundles = registry.get("component_bundles")
    if not isinstance(bundles, list):
        raise ComponentBundleCompilationError("component registry component_bundles must be a list")
    for bundle in bundles:
        if isinstance(bundle, dict) and bundle.get("bundle_id") == bundle_id:
            return bundle
    raise ComponentBundleCompilationError(f"component bundle {bundle_id} is not registered")


def _component_index(read_model: dict[str, Any]) -> dict[str, dict[str, Any]]:
    components = read_model.get("components")
    if not isinstance(components, list):
        raise ComponentBundleCompilationError("read model components must be a list")
    result: dict[str, dict[str, Any]] = {}
    for component in components:
        if not isinstance(component, dict):
            raise ComponentBundleCompilationError("read model component entries must be objects")
        component_id = component.get("component_id")
        if not isinstance(component_id, str) or not component_id:
            raise ComponentBundleCompilationError("read model component entries must carry component_id")
        result[component_id] = component
    return result


def _reject_live_authority(components: Iterable[dict[str, Any]], bundle_id: str) -> None:
    for component in components:
        component_id = str(component.get("component_id", "<missing>"))
        authority = component.get("authority")
        if not isinstance(authority, dict):
            raise ComponentBundleCompilationError(f"component {component_id} authority must be an object")
        for flag_name in LIVE_AUTHORITY_FLAGS:
            if authority.get(flag_name) is not False:
                raise ComponentBundleCompilationError(
                    f"bundle {bundle_id} cannot compile component {component_id} with {flag_name}=true"
                )


def _relevant_simulations(simulations: list[dict[str, Any]], component_ids: list[str]) -> list[dict[str, Any]]:
    component_set = set(component_ids)
    relevant: list[dict[str, Any]] = []
    for simulation in simulations:
        if not isinstance(simulation, dict):
            raise ComponentBundleCompilationError("simulation entries must be objects")
        if simulation.get("intent") == "unknown_component_request":
            continue
        selected_component_ids = set(_string_list(simulation.get("selected_component_ids")))
        if selected_component_ids and selected_component_ids.issubset(component_set):
            relevant.append(simulation)
    return relevant


def _component_states(components: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    states: list[dict[str, Any]] = []
    for component in components:
        proof_binding = component.get("proof_binding", {})
        route_binding = component.get("route_binding", {})
        states.append(
            {
                "component_id": str(component.get("component_id", "")),
                "mode": str(component.get("mode", "")),
                "state": str(component.get("state", "")),
                "wiring_state": str(component.get("wiring_state", "")),
                "authority_level": str(component.get("authority_level", "")),
                "proof_binding_state": str(proof_binding.get("state", "")) if isinstance(proof_binding, dict) else "",
                "route_binding_state": str(route_binding.get("state", "")) if isinstance(route_binding, dict) else "",
            }
        )
    return states


def _simulation_summaries(simulations: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "simulation_id": str(simulation.get("simulation_id", "")),
            "intent": str(simulation.get("intent", "")),
            "outcome": str(simulation.get("outcome", "")),
            "approval_required": bool(simulation.get("approval_required")),
            "selected_component_ids": _string_list(simulation.get("selected_component_ids")),
            "blocked_actions": _string_list(simulation.get("blocked_actions")),
            "needed_evidence": _string_list(simulation.get("needed_evidence")),
        }
        for simulation in simulations
    ]


def _bundle_outcome(blocked_simulation_count: int, awaiting_simulation_count: int) -> str:
    if blocked_simulation_count:
        return "GovernanceBlocked"
    if awaiting_simulation_count:
        return "AwaitingEvidence"
    return "SolvedUnverified"


def _bundle_reason(
    *,
    bundle_id: str,
    blocked_simulation_count: int,
    awaiting_simulation_count: int,
) -> str:
    if blocked_simulation_count:
        return f"bundle {bundle_id} compiles for preview while live-action scenarios remain blocked"
    if awaiting_simulation_count:
        return f"bundle {bundle_id} compiles for preview while evidence is still required"
    return f"bundle {bundle_id} compiles for read-only preview only"


def _required_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ComponentBundleCompilationError(f"{field_name} must be a non-empty string")
    return value


def _ordered_unique(values: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            ordered.append(value)
    return tuple(ordered)


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _load_json_object(path: Path, label: str) -> dict[str, Any]:
    if not path.exists():
        raise ComponentBundleCompilationError(f"{label} file missing: {_path_label(path, _repo_root())}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ComponentBundleCompilationError(f"{label} JSON parse failed: {exc}") from exc
    if not isinstance(payload, dict):
        raise ComponentBundleCompilationError(f"{label} JSON root must be an object")
    return payload


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _path_label(path: Path, repo_root: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(repo_root).as_posix()
    except ValueError:
        return path.name
