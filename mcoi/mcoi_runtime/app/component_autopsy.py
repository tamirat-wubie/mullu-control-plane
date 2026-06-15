"""Build Component Harness autopsy views.

Purpose: explain a registered component's blocked posture, present evidence,
missing evidence, forbidden actions, and next transition preview.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: component read model projection.
Invariants:
  - Autopsy views are read-only and never mutate source artifacts.
  - Autopsy views cannot grant execution, mutation, connector send, external
    send, file write, or terminal closure authority.
  - Unknown component IDs fail closed with bounded causal context.
"""

from __future__ import annotations

from typing import Any

from mcoi_runtime.app.component_read_model import (
    ComponentReadModelError,
    LIVE_AUTHORITY_FLAGS,
    build_component_read_model,
)


AUTOPSY_ROUTE_TEMPLATE = "/api/v1/components/{component_id}/autopsy"
SCHEMA_VERSION = 1
AUTOPSY_ID_PREFIX = "component_autopsy"
FOUNDATION_OUTCOMES = {"AwaitingEvidence", "GovernanceBlocked"}


class ComponentAutopsyError(ValueError):
    """Raised when a component autopsy cannot be built safely."""


def build_component_autopsy(
    component_id: str,
    *,
    read_model: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a deterministic, non-executing autopsy for one component.

    Input contract: a registered component ID and optional read-model payload.
    Output contract: JSON-serializable autopsy payload.
    Error contract: raises ComponentAutopsyError for unknown components or
    malformed read-model inputs.
    """

    normalized_component_id = _required_text(component_id, "component_id")
    source_read_model = read_model or _build_read_model()
    component = _component_by_id(source_read_model, normalized_component_id)
    lifecycle_receipt = _required_object(component, "lifecycle_receipt", normalized_component_id)
    proof_binding = _required_object(component, "proof_binding", normalized_component_id)
    route_binding = _required_object(component, "route_binding", normalized_component_id)
    authority = _required_object(component, "authority", normalized_component_id)
    blocked_actions = _string_list(component.get("blocked_actions"))
    forbidden_actions = _ordered_unique((*blocked_actions, "terminal_closure"))
    missing_evidence = _missing_evidence(component)
    blockers = _blockers(component, missing_evidence)
    outcome = "AwaitingEvidence" if missing_evidence else "GovernanceBlocked"

    return {
        "schema_version": SCHEMA_VERSION,
        "autopsy_id": f"{AUTOPSY_ID_PREFIX}.{normalized_component_id}.v1",
        "route": AUTOPSY_ROUTE_TEMPLATE,
        "component_id": normalized_component_id,
        "name": str(component.get("name", "")),
        "mode": str(component.get("mode", "")),
        "state": str(component.get("state", "")),
        "wiring_state": str(component.get("wiring_state", "")),
        "authority_level": str(component.get("authority_level", "")),
        "governed": True,
        "autopsy_is_not_execution_authority": True,
        "live_execution_enabled": False,
        "live_connector_send_enabled": False,
        "can_execute": False,
        "can_mutate": False,
        "can_call_connector": False,
        "can_write_files": False,
        "can_send_external_message": False,
        "can_claim_terminal_closure": False,
        "terminal_closure_required": True,
        "authority_snapshot": {flag_name: bool(authority.get(flag_name, False)) for flag_name in sorted(authority)},
        "forbidden_actions": list(forbidden_actions),
        "blockers": blockers,
        "evidence_present": {
            "lifecycle_receipt_id": str(lifecycle_receipt.get("receipt_id", "")),
            "lifecycle_evidence_refs": _string_list(lifecycle_receipt.get("evidence_refs")),
            "lifecycle_validator_refs": _string_list(lifecycle_receipt.get("validator_refs")),
            "proof_surface_ids": list(
                _ordered_unique(
                    (
                        *_string_list(proof_binding.get("required_surface_ids")),
                        *_string_list(proof_binding.get("inventory_surface_ids")),
                    )
                )
            ),
            "runtime_witness_count": int(proof_binding.get("runtime_witness_count", 0)),
            "proof_evidence_file_count": int(proof_binding.get("evidence_file_count", 0)),
            "route_binding_state": str(route_binding.get("state", "")),
            "route_count": int(route_binding.get("route_count", 0)),
        },
        "missing_evidence": list(missing_evidence),
        "next_transition_candidates": _next_transition_candidates(lifecycle_receipt),
        "expected_receipts": [
            "component_autopsy_receipt",
            "component_read_model_validation_receipt",
            "component_lifecycle_transition_receipt",
            "authority_denial_receipt",
        ],
        "outcome": outcome,
        "reason": _reason(normalized_component_id, missing_evidence),
        "source_refs": {
            "read_model": "examples/component_read_model.foundation.json",
            "lifecycle_transition_receipts": "examples/component_lifecycle_transition_receipts.foundation.json",
        },
        "validators": [
            "component_autopsy_validator",
            "component_autopsy_tests",
            "component_read_model_validator",
            "component_lifecycle_transition_receipts_validator",
        ],
    }


def build_foundation_component_autopsies() -> list[dict[str, Any]]:
    """Return autopsies for all foundation read-model components."""

    read_model = _build_read_model()
    components = read_model.get("components")
    if not isinstance(components, list):
        raise ComponentAutopsyError("component read model components must be a list")
    return [
        build_component_autopsy(
            _required_text(component.get("component_id"), "component_id"),
            read_model=read_model,
        )
        for component in components
        if isinstance(component, dict)
    ]


def _build_read_model() -> dict[str, Any]:
    try:
        return build_component_read_model()
    except ComponentReadModelError as exc:
        raise ComponentAutopsyError(str(exc)) from exc


def _component_by_id(read_model: dict[str, Any], component_id: str) -> dict[str, Any]:
    components = read_model.get("components")
    if not isinstance(components, list):
        raise ComponentAutopsyError("component read model components must be a list")
    for component in components:
        if isinstance(component, dict) and component.get("component_id") == component_id:
            return component
    raise ComponentAutopsyError(f"component {component_id} is not registered")


def _missing_evidence(component: dict[str, Any]) -> tuple[str, ...]:
    missing: list[str] = []
    component_id = str(component.get("component_id", "<missing>"))
    lifecycle_receipt = component.get("lifecycle_receipt")
    proof_binding = component.get("proof_binding")
    route_binding = component.get("route_binding")
    if not isinstance(lifecycle_receipt, dict):
        missing.append("lifecycle_transition_receipt")
    elif lifecycle_receipt.get("proof_state") != "Pass":
        missing.append("passing_lifecycle_transition_receipt")
    if not isinstance(proof_binding, dict):
        missing.append("proof_binding")
    else:
        if proof_binding.get("state") != "proof_bound":
            missing.append("proof_matrix_surface")
        if component.get("receipt_required") is True and int(proof_binding.get("runtime_witness_count", 0)) <= 0:
            missing.append("runtime_witness")
        if component.get("receipt_required") is True and int(proof_binding.get("evidence_file_count", 0)) <= 0:
            missing.append("proof_evidence_file")
    if not isinstance(route_binding, dict) or route_binding.get("state") == "missing":
        missing.append("declared_route_binding")
    if component.get("mode") in {"live_probe", "approval_required"}:
        missing.append("operator_approval")
    if component_id == "nested_mind_bridge" and "memory_topology_activation" in _string_list(component.get("blocked_actions")):
        missing.append("memory_topology_activation_witness")
    return _ordered_unique(missing)


def _blockers(component: dict[str, Any], missing_evidence: tuple[str, ...]) -> list[dict[str, Any]]:
    blockers = [
        {
            "blocker_id": "live_authority_denied",
            "reason": "approved live action authority is missing",
            "proof_state": "Pass",
        },
        {
            "blocker_id": "terminal_closure_blocked",
            "reason": "autopsy output cannot claim terminal closure",
            "proof_state": "Pass",
        },
    ]
    if missing_evidence:
        blockers.append(
            {
                "blocker_id": "missing_evidence",
                "reason": "evidence is required before authority promotion",
                "proof_state": "Unknown",
            }
        )
    return blockers


def _next_transition_candidates(lifecycle_receipt: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = lifecycle_receipt.get("next_transition_candidates")
    if not isinstance(candidates, list):
        return []
    return [
        {
            "from_state": str(candidate.get("from_state", "")),
            "to_state": str(candidate.get("to_state", "")),
            "requires_evidence": bool(candidate.get("requires_evidence")),
            "operator_approval_required": bool(candidate.get("operator_approval_required")),
            "external_effect": bool(candidate.get("external_effect")),
            "transition_is_not_authority": True,
        }
        for candidate in candidates
        if isinstance(candidate, dict)
    ]


def _reason(component_id: str, missing_evidence: tuple[str, ...]) -> str:
    if missing_evidence:
        return f"component {component_id} is visible but blocked by missing evidence: {', '.join(missing_evidence)}"
    return f"component {component_id} is visible with foundation live authority denied"


def _required_object(payload: dict[str, Any], field_name: str, component_id: str) -> dict[str, Any]:
    value = payload.get(field_name)
    if not isinstance(value, dict):
        raise ComponentAutopsyError(f"component {component_id} {field_name} must be an object")
    return value


def _required_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ComponentAutopsyError(f"{field_name} must be a non-empty string")
    return value


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _ordered_unique(values: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            ordered.append(value)
    return tuple(ordered)
