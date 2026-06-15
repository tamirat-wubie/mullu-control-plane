"""Detect Component Harness drift and dead-component candidates.

Purpose: classify registered components by route, proof, bundle, request-path,
and autopsy evidence so latent drift is visible before product claims advance.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: component graph and component read model projections.
Invariants:
  - Detection is advisory and never grants execution authority.
  - Blocked governed components are not removed or treated as dead by default.
  - Dead-candidate classification requires multiple missing relationship
    signals, not a single missing route.
"""

from __future__ import annotations

from typing import Any, Iterable

from mcoi_runtime.app.component_graph import ComponentGraphError, build_component_graph
from mcoi_runtime.app.component_read_model import (
    ComponentReadModelError,
    build_component_read_model,
)


SCHEMA_VERSION = 1
REPORT_ID = "component_dead_component_detection.foundation.v1"
DEFAULT_RECEIPT_EXPECTATIONS = (
    "component_dead_component_detection_receipt",
    "component_graph_projection_receipt",
    "component_read_model_validation_receipt",
    "authority_denial_receipt",
)


class ComponentDeadDetectorError(ValueError):
    """Raised when dead-component detection cannot be completed safely."""


def build_component_dead_component_report(
    *,
    graph: dict[str, Any] | None = None,
    read_model: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a deterministic dead-component detection report.

    Input contract: optional graph and read-model projections. Output contract:
    JSON-serializable drift report. Error contract: raises
    ComponentDeadDetectorError for malformed graph/read-model inputs.
    """

    source_graph = graph or _build_graph()
    source_read_model = read_model or _build_read_model()
    component_index = _component_index(source_read_model)
    node_index = _node_index(source_graph, component_index)
    detections = _detections(node_index)
    summary = _summary(detections)
    return {
        "schema_version": SCHEMA_VERSION,
        "report_id": REPORT_ID,
        "mode": str(source_graph.get("mode", "foundation")),
        "governed": True,
        "detector_is_not_execution_authority": True,
        "live_execution_enabled": False,
        "live_connector_send_enabled": False,
        "can_execute": False,
        "can_mutate": False,
        "can_call_connector": False,
        "can_claim_terminal_closure": False,
        "terminal_closure_required": True,
        "source_refs": {
            "component_graph": "examples/component_graph.foundation.json",
            "read_model": "examples/component_read_model.foundation.json",
        },
        "summary": summary,
        "detections": detections,
        "dead_component_candidates": [
            detection["component_id"]
            for detection in detections
            if detection["classification"] == "dead_candidate"
        ],
        "blocked_governed_components": [
            detection["component_id"]
            for detection in detections
            if detection["classification"] == "blocked_governed"
        ],
        "expected_receipts": list(DEFAULT_RECEIPT_EXPECTATIONS),
        "outcome": _outcome(summary),
        "validators": [
            "component_dead_detector_validator",
            "component_dead_detector_tests",
            "component_graph_validator",
            "component_read_model_validator",
        ],
        "next_action": "Convert dead candidates into explicit archive, bundle, proof, or deprecation decisions without enabling live execution.",
    }


def _build_graph() -> dict[str, Any]:
    try:
        return build_component_graph()
    except ComponentGraphError as exc:
        raise ComponentDeadDetectorError(str(exc)) from exc


def _build_read_model() -> dict[str, Any]:
    try:
        return build_component_read_model()
    except ComponentReadModelError as exc:
        raise ComponentDeadDetectorError(str(exc)) from exc


def _component_index(read_model: dict[str, Any]) -> dict[str, dict[str, Any]]:
    components = read_model.get("components")
    if not isinstance(components, list):
        raise ComponentDeadDetectorError("read model components must be a list")
    result: dict[str, dict[str, Any]] = {}
    for component in components:
        if not isinstance(component, dict):
            raise ComponentDeadDetectorError("read model component entries must be objects")
        component_id = component.get("component_id")
        if not isinstance(component_id, str) or not component_id:
            raise ComponentDeadDetectorError("read model component entries must carry component_id")
        result[component_id] = component
    return result


def _node_index(
    graph: dict[str, Any],
    component_index: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    nodes = graph.get("nodes")
    if not isinstance(nodes, list):
        raise ComponentDeadDetectorError("component graph nodes must be a list")
    result: dict[str, dict[str, Any]] = {}
    for node in nodes:
        if not isinstance(node, dict):
            raise ComponentDeadDetectorError("component graph node entries must be objects")
        component_id = node.get("component_id")
        if not isinstance(component_id, str) or not component_id:
            raise ComponentDeadDetectorError("component graph node entries must carry component_id")
        if component_id not in component_index:
            raise ComponentDeadDetectorError(f"component graph has unregistered node {component_id}")
        result[component_id] = node
    missing = sorted(set(component_index) - set(result))
    if missing:
        raise ComponentDeadDetectorError(f"component graph missing nodes {missing}")
    return result


def _detections(node_index: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [_detection(component_id, node_index[component_id]) for component_id in sorted(node_index)]


def _detection(component_id: str, node: dict[str, Any]) -> dict[str, Any]:
    route_count = int(node.get("route_count", 0))
    bundle_count = int(node.get("bundle_count", 0))
    request_path_count = int(node.get("request_path_count", 0))
    dependent_count = int(node.get("dependent_count", 0))
    dependency_count = int(node.get("dependency_count", 0))
    missing_evidence_count = int(node.get("missing_evidence_count", 0))
    proof_binding_state = str(node.get("proof_binding_state", ""))
    mode = str(node.get("mode", ""))
    signals = _signals(
        route_count=route_count,
        bundle_count=bundle_count,
        request_path_count=request_path_count,
        dependent_count=dependent_count,
        dependency_count=dependency_count,
        missing_evidence_count=missing_evidence_count,
        proof_binding_state=proof_binding_state,
    )
    classification = _classification(
        mode=mode,
        route_count=route_count,
        bundle_count=bundle_count,
        request_path_count=request_path_count,
        dependent_count=dependent_count,
        missing_evidence_count=missing_evidence_count,
        proof_binding_state=proof_binding_state,
    )
    return {
        "component_id": component_id,
        "name": str(node.get("name", "")),
        "classification": classification,
        "signals": list(signals),
        "route_count": route_count,
        "bundle_count": bundle_count,
        "request_path_count": request_path_count,
        "dependency_count": dependency_count,
        "dependent_count": dependent_count,
        "proof_binding_state": proof_binding_state,
        "autopsy_outcome": str(node.get("autopsy_outcome", "")),
        "missing_evidence_count": missing_evidence_count,
        "recommended_decisions": list(_recommended_decisions(classification, signals)),
        "detection_is_not_execution_authority": True,
    }


def _signals(
    *,
    route_count: int,
    bundle_count: int,
    request_path_count: int,
    dependent_count: int,
    dependency_count: int,
    missing_evidence_count: int,
    proof_binding_state: str,
) -> tuple[str, ...]:
    signals: list[str] = []
    if route_count == 0:
        signals.append("no_mounted_route")
    if proof_binding_state != "proof_bound":
        signals.append("proof_binding_missing")
    if bundle_count == 0:
        signals.append("no_bundle_membership")
    if request_path_count == 0:
        signals.append("no_request_path_coverage")
    if dependent_count == 0:
        signals.append("no_dependent_components")
    if dependency_count == 0:
        signals.append("no_declared_dependencies")
    if missing_evidence_count > 0:
        signals.append("missing_evidence")
    return tuple(signals)


def _classification(
    *,
    mode: str,
    route_count: int,
    bundle_count: int,
    request_path_count: int,
    dependent_count: int,
    missing_evidence_count: int,
    proof_binding_state: str,
) -> str:
    if mode == "blocked" or proof_binding_state != "proof_bound" or missing_evidence_count > 0:
        return "blocked_governed"
    if route_count == 0 and bundle_count == 0 and request_path_count == 0 and dependent_count == 0:
        return "dead_candidate"
    if route_count == 0:
        return "governed_watch"
    return "active_governed"


def _recommended_decisions(classification: str, signals: Iterable[str]) -> tuple[str, ...]:
    if classification == "dead_candidate":
        return (
            "decide_archive_or_deprecate",
            "bind_to_bundle_or_remove_registry_claim",
            "add_proof_surface_before_public_claim",
        )
    if classification == "blocked_governed":
        return (
            "preserve_blocked_status",
            "add_missing_evidence_before_lifecycle_transition",
            "keep_live_authority_false",
        )
    if classification == "governed_watch":
        decisions = ["keep_registered_and_monitored"]
        if "no_mounted_route" in set(signals):
            decisions.append("bind_route_only_if_product_surface_required")
        return tuple(decisions)
    return ("no_dead_component_action_required",)


def _summary(detections: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "component_count": len(detections),
        "active_governed_count": _classification_count(detections, "active_governed"),
        "governed_watch_count": _classification_count(detections, "governed_watch"),
        "blocked_governed_count": _classification_count(detections, "blocked_governed"),
        "dead_candidate_count": _classification_count(detections, "dead_candidate"),
        "no_route_count": _signal_count(detections, "no_mounted_route"),
        "no_bundle_membership_count": _signal_count(detections, "no_bundle_membership"),
        "no_request_path_count": _signal_count(detections, "no_request_path_coverage"),
        "awaiting_binding_count": _signal_count(detections, "proof_binding_missing"),
    }


def _classification_count(detections: list[dict[str, Any]], classification: str) -> int:
    return sum(1 for detection in detections if detection.get("classification") == classification)


def _signal_count(detections: list[dict[str, Any]], signal: str) -> int:
    return sum(1 for detection in detections if signal in _string_list(detection.get("signals")))


def _outcome(summary: dict[str, int]) -> str:
    if summary["dead_candidate_count"] > 0:
        return "GovernanceBlocked"
    if summary["blocked_governed_count"] > 0:
        return "AwaitingEvidence"
    return "SolvedUnverified"


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]
