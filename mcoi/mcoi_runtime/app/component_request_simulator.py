"""Simulate Component Harness request routing without execution.

Purpose: classify an operator request into a preview-only component path,
blocked actions, approval need, and expected receipts.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: component_read_model foundation projection.
Invariants:
  - Simulation is not execution authority.
  - Live execution, mutation, connector calls, and terminal closure stay false.
  - Unknown requests degrade to AwaitingEvidence instead of live action.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from mcoi_runtime.app.component_read_model import (
    ComponentReadModelError,
    build_component_read_model,
)


SIMULATION_ROUTE = "/api/v1/components/simulate"
SCHEMA_VERSION = 1
DEFAULT_RECEIPT_EXPECTATIONS = (
    "component_request_simulation_receipt",
    "component_path_preview_receipt",
    "authority_denial_receipt",
)


@dataclass(frozen=True, slots=True)
class ComponentRequestRule:
    """Deterministic request classification rule."""

    intent: str
    scenario_id: str
    tokens: tuple[str, ...]
    component_path: tuple[str, ...]
    requested_actions: tuple[str, ...]
    approval_required: bool
    outcome: str
    reason: str
    needed_evidence: tuple[str, ...]


REQUEST_RULES: tuple[ComponentRequestRule, ...] = (
    ComponentRequestRule(
        intent="send_email_request",
        scenario_id="send_email_blocked_preview",
        tokens=("send email", "send this email", "email this", "mail this", "external send"),
        component_path=("governance_core", "personal_assistant", "gmail_account_binding_gate"),
        requested_actions=("send_email", "external_send", "mailbox_mutation", "connector_call"),
        approval_required=True,
        outcome="GovernanceBlocked",
        reason="email send is blocked until account-binding, approval, connector, and live-send witnesses exist",
        needed_evidence=(
            "gmail_account_binding_evidence_receipt",
            "explicit_operator_send_approval_receipt",
            "live_send_authority_transition_receipt",
        ),
    ),
    ComponentRequestRule(
        intent="inbox_readiness_probe",
        scenario_id="inbox_readiness_probe_preview",
        tokens=("inbox readiness", "check my inbox", "mailbox readiness", "gmail readiness"),
        component_path=("governance_core", "personal_assistant", "gmail_account_binding_gate"),
        requested_actions=("connector_call", "mailbox_mutation", "external_send"),
        approval_required=True,
        outcome="AwaitingEvidence",
        reason="inbox readiness needs account-binding evidence before any mailbox or connector claim",
        needed_evidence=("gmail_account_binding_evidence_receipt",),
    ),
    ComponentRequestRule(
        intent="deep_symbolic_analysis",
        scenario_id="deep_symbolic_analysis_preview",
        tokens=("analyze this idea deeply", "deep analysis", "symbolic analysis", "inceptadive", "snet"),
        component_path=("governance_core", "inceptadive_shadow", "snet"),
        requested_actions=("route_execution", "connector_call", "filesystem_write", "external_send"),
        approval_required=False,
        outcome="SolvedUnverified",
        reason="read-only reasoning components can be selected for preview while execution remains blocked",
        needed_evidence=("component_request_simulation_receipt",),
    ),
    ComponentRequestRule(
        intent="worker_dispatch_request",
        scenario_id="worker_dispatch_blocked_preview",
        tokens=("run this worker", "dispatch worker", "worker task", "capability worker"),
        component_path=("governance_core", "worker_runtime", "capability_workers"),
        requested_actions=("live_dispatch", "filesystem_write", "runtime_mutation", "autonomous_execution"),
        approval_required=True,
        outcome="GovernanceBlocked",
        reason="worker dispatch is blocked until runner binding and live dispatch witnesses exist",
        needed_evidence=("runner_binding_witness_receipt", "live_dispatch_authority_transition_receipt"),
    ),
    ComponentRequestRule(
        intent="nested_mind_activation_request",
        scenario_id="nested_mind_activation_blocked_preview",
        tokens=("activate nested mind", "nested mind", "memory topology", "topology activation"),
        component_path=("governance_core", "nested_mind_bridge"),
        requested_actions=("memory_topology_activation", "runtime_mutation", "provider_write"),
        approval_required=True,
        outcome="GovernanceBlocked",
        reason="Nested Mind activation is blocked until bridge proof binding and activation witnesses exist",
        needed_evidence=("nested_mind_bridge_proof_binding_receipt", "memory_topology_activation_receipt"),
    ),
)

UNKNOWN_REQUEST_RULE = ComponentRequestRule(
    intent="unknown_component_request",
    scenario_id="unknown_component_request_preview",
    tokens=(),
    component_path=("governance_core",),
    requested_actions=(
        "autonomous_execution",
        "connector_call",
        "external_send",
        "filesystem_write",
        "live_dispatch",
        "runtime_mutation",
    ),
    approval_required=True,
    outcome="AwaitingEvidence",
    reason="request intent is not mapped to a governed component path",
    needed_evidence=("component_request_intent_classification_receipt",),
)


class ComponentRequestSimulationError(ValueError):
    """Raised when a request cannot be simulated against the read model."""


def simulate_component_request(
    request_text: str,
    *,
    read_model: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a deterministic, non-executing Component Harness route preview.

    Input contract: a non-empty request text and an optional read-model
    payload. Output contract: JSON-serializable simulation envelope.
    Error contract: raises ComponentRequestSimulationError for malformed
    inputs or missing component records.
    """

    normalized_request = _normalize_request_text(request_text)
    source_read_model = read_model or _build_read_model()
    component_index = _component_index(source_read_model)
    rule = _select_rule(normalized_request)
    missing_components = [component_id for component_id in rule.component_path if component_id not in component_index]
    if missing_components:
        raise ComponentRequestSimulationError(
            f"request rule {rule.intent} references unregistered components {missing_components}"
        )

    selected_components = [component_index[component_id] for component_id in rule.component_path]
    blocked_actions = _ordered_unique(
        (
            *rule.requested_actions,
            *(
                action
                for component in selected_components
                for action in _string_list(component.get("blocked_actions"))
            ),
            "terminal_closure",
        )
    )
    blocked_component_ids = tuple(
        component["component_id"]
        for component in selected_components
        if _component_blocks_requested_action(component, rule.requested_actions)
        or component.get("mode") == "blocked"
        or component.get("proof_binding", {}).get("state") == "awaiting_binding"
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "simulation_id": f"component_request_simulation.{rule.scenario_id}.v1",
        "route": SIMULATION_ROUTE,
        "mode": str(source_read_model.get("mode", "foundation")),
        "governed": True,
        "request_text": request_text,
        "intent": rule.intent,
        "scenario_id": rule.scenario_id,
        "simulation_is_not_execution_authority": True,
        "live_execution_enabled": False,
        "can_execute": False,
        "can_mutate": False,
        "can_call_connector": False,
        "can_claim_terminal_closure": False,
        "terminal_closure_required": True,
        "selected_component_ids": list(rule.component_path),
        "blocked_component_ids": list(blocked_component_ids),
        "blocked_actions": list(blocked_actions),
        "approval_required": rule.approval_required,
        "expected_receipts": list(_expected_receipts(rule)),
        "needed_evidence": list(rule.needed_evidence),
        "outcome": rule.outcome,
        "reason": rule.reason,
        "source_refs": {
            "read_model": "examples/component_read_model.foundation.json",
            "registry": str(source_read_model.get("source_refs", {}).get("registry", "")),
            "router_inventory": str(source_read_model.get("source_refs", {}).get("router_inventory", "")),
            "proof_binding": str(source_read_model.get("source_refs", {}).get("proof_binding", "")),
        },
        "validators": [
            "component_request_simulation_validator",
            "component_request_simulation_route_tests",
            "component_read_model_validator",
        ],
    }


def foundation_component_request_simulations() -> list[dict[str, Any]]:
    """Return the deterministic built-in foundation simulation set."""

    requests = (
        "Send this email to the customer",
        "Check my inbox readiness",
        "Analyze this idea deeply",
        "Run this worker task",
        "Activate Nested Mind memory topology",
        "Classify this new component request",
    )
    read_model = _build_read_model()
    return [
        simulate_component_request(request_text, read_model=read_model)
        for request_text in requests
    ]


def _build_read_model() -> dict[str, Any]:
    try:
        return build_component_read_model()
    except ComponentReadModelError as exc:
        raise ComponentRequestSimulationError(str(exc)) from exc


def _normalize_request_text(request_text: str) -> str:
    if not isinstance(request_text, str):
        raise ComponentRequestSimulationError("request_text must be a string")
    stripped = request_text.strip()
    if not stripped:
        raise ComponentRequestSimulationError("request_text must not be empty")
    if len(stripped) > 500:
        raise ComponentRequestSimulationError("request_text must be at most 500 characters")
    return " ".join(stripped.casefold().split())


def _select_rule(normalized_request: str) -> ComponentRequestRule:
    for rule in REQUEST_RULES:
        if any(token in normalized_request for token in rule.tokens):
            return rule
    return UNKNOWN_REQUEST_RULE


def _component_index(read_model: dict[str, Any]) -> dict[str, dict[str, Any]]:
    components = read_model.get("components")
    if not isinstance(components, list):
        raise ComponentRequestSimulationError("read model components must be a list")
    result: dict[str, dict[str, Any]] = {}
    for component in components:
        if not isinstance(component, dict):
            raise ComponentRequestSimulationError("read model component entries must be objects")
        component_id = component.get("component_id")
        if not isinstance(component_id, str) or not component_id:
            raise ComponentRequestSimulationError("read model component entries must carry component_id")
        result[component_id] = component
    return result


def _component_blocks_requested_action(
    component: dict[str, Any],
    requested_actions: Iterable[str],
) -> bool:
    component_blocked_actions = set(_string_list(component.get("blocked_actions")))
    return any(requested_action in component_blocked_actions for requested_action in requested_actions)


def _expected_receipts(rule: ComponentRequestRule) -> tuple[str, ...]:
    return _ordered_unique((*DEFAULT_RECEIPT_EXPECTATIONS, *rule.needed_evidence))


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
