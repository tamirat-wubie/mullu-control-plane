"""Purpose: causal / counterfactual runtime engine.
Governance scope: managing causal nodes, edges, interventions, counterfactual
    scenarios, attributions, propagation records, decisions, violations,
    assessments, snapshots, and closure reports.
Dependencies: causal_runtime contracts, event_spine, core invariants.
Invariants:
  - Duplicate IDs raise RuntimeCoreInvariantError.
  - Every mutation emits an event.
  - All returns are immutable.
  - Clock is injected for deterministic timestamps.
  - Violation detection is idempotent.
"""

from __future__ import annotations

from collections import deque
from hashlib import sha256
from typing import Any

from mcoi_runtime.core.engine_protocol import Clock, WallClock

from ..contracts.causal_runtime import (
    AttributionStrength,
    CausalAssessment,
    CausalAttribution,
    CausalClosureReport,
    CausalDecision,
    CausalEdge,
    CausalEdgeKind,
    CausalNode,
    CausalRiskLevel,
    CausalSnapshot,
    CausalStatus,
    CounterfactualScenario,
    CounterfactualStatus,
    InterventionDisposition,
    InterventionRecord,
    PropagationRecord,
)
from ..contracts.event import EventRecord, EventSource, EventType
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str, now: str) -> EventRecord:
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-causrt", {"action": action, "seq": str(es.event_count), "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class CausalRuntimeEngine:
    """Engine for governed causal / counterfactual runtime."""

    def __init__(self, event_spine: EventSpineEngine, *, clock: Any = None) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._clock: Clock = clock if isinstance(clock, Clock) else WallClock()
        self._nodes: dict[str, CausalNode] = {}
        self._edges: dict[str, CausalEdge] = {}
        self._interventions: dict[str, InterventionRecord] = {}
        self._counterfactuals: dict[str, CounterfactualScenario] = {}
        self._attributions: dict[str, CausalAttribution] = {}
        self._propagations: dict[str, PropagationRecord] = {}
        self._decisions: dict[str, CausalDecision] = {}
        self._violations: dict[str, dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Clock
    # ------------------------------------------------------------------

    def _now(self) -> str:
        return self._clock.now_iso()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    @property
    def edge_count(self) -> int:
        return len(self._edges)

    @property
    def intervention_count(self) -> int:
        return len(self._interventions)

    @property
    def counterfactual_count(self) -> int:
        return len(self._counterfactuals)

    @property
    def attribution_count(self) -> int:
        return len(self._attributions)

    @property
    def propagation_count(self) -> int:
        return len(self._propagations)

    @property
    def violation_count(self) -> int:
        return len(self._violations)

    # ------------------------------------------------------------------
    # Nodes
    # ------------------------------------------------------------------

    def register_causal_node(
        self,
        node_id: str,
        tenant_id: str,
        display_name: str,
        status: CausalStatus = CausalStatus.ACTIVE,
    ) -> CausalNode:
        """Register a new causal node. Duplicate node_id raises."""
        if node_id in self._nodes:
            raise RuntimeCoreInvariantError("Duplicate node_id")
        now = self._now()
        node = CausalNode(
            node_id=node_id,
            tenant_id=tenant_id,
            display_name=display_name,
            status=status,
            created_at=now,
        )
        self._nodes[node_id] = node
        _emit(self._events, "causal_node_registered", {
            "node_id": node_id, "display_name": display_name,
        }, node_id, self._now())
        return node

    # ------------------------------------------------------------------
    # Edges
    # ------------------------------------------------------------------

    def register_causal_edge(
        self,
        edge_id: str,
        tenant_id: str,
        cause_ref: str,
        effect_ref: str,
        kind: CausalEdgeKind = CausalEdgeKind.DIRECT,
        strength: AttributionStrength = AttributionStrength.MODERATE,
    ) -> CausalEdge:
        """Register a causal edge. Both nodes must exist. Duplicate edge_id raises."""
        if edge_id in self._edges:
            raise RuntimeCoreInvariantError("Duplicate edge_id")
        if cause_ref not in self._nodes:
            raise RuntimeCoreInvariantError("Unknown cause node")
        if effect_ref not in self._nodes:
            raise RuntimeCoreInvariantError("Unknown effect node")
        now = self._now()
        edge = CausalEdge(
            edge_id=edge_id,
            tenant_id=tenant_id,
            cause_ref=cause_ref,
            effect_ref=effect_ref,
            kind=kind,
            strength=strength,
            created_at=now,
        )
        self._edges[edge_id] = edge
        _emit(self._events, "causal_edge_registered", {
            "edge_id": edge_id, "cause_ref": cause_ref, "effect_ref": effect_ref,
        }, edge_id, self._now())
        return edge

    # ------------------------------------------------------------------
    # Interventions
    # ------------------------------------------------------------------

    def register_intervention(
        self,
        intervention_id: str,
        tenant_id: str,
        target_node_ref: str,
        expected_effect: str,
        disposition: InterventionDisposition = InterventionDisposition.PROPOSED,
    ) -> InterventionRecord:
        """Register an intervention. Duplicate intervention_id raises."""
        if intervention_id in self._interventions:
            raise RuntimeCoreInvariantError("Duplicate intervention_id")
        now = self._now()
        intervention = InterventionRecord(
            intervention_id=intervention_id,
            tenant_id=tenant_id,
            target_node_ref=target_node_ref,
            disposition=disposition,
            expected_effect=expected_effect,
            created_at=now,
        )
        self._interventions[intervention_id] = intervention
        _emit(self._events, "intervention_registered", {
            "intervention_id": intervention_id, "target": target_node_ref,
        }, intervention_id, self._now())
        return intervention

    # ------------------------------------------------------------------
    # Counterfactuals
    # ------------------------------------------------------------------

    def run_counterfactual(
        self,
        scenario_id: str,
        tenant_id: str,
        intervention_ref: str,
        premise: str,
    ) -> CounterfactualScenario:
        """Run a counterfactual scenario (PENDING -> EVALUATED)."""
        if scenario_id in self._counterfactuals:
            raise RuntimeCoreInvariantError("Duplicate scenario_id")
        if intervention_ref not in self._interventions:
            raise RuntimeCoreInvariantError("Unknown intervention_ref")
        now = self._now()
        scenario = CounterfactualScenario(
            scenario_id=scenario_id,
            tenant_id=tenant_id,
            intervention_ref=intervention_ref,
            premise=premise,
            status=CounterfactualStatus.EVALUATED,
            created_at=now,
        )
        self._counterfactuals[scenario_id] = scenario
        _emit(self._events, "counterfactual_evaluated", {
            "scenario_id": scenario_id, "intervention_ref": intervention_ref,
        }, scenario_id, self._now())
        return scenario

    def confirm_counterfactual(self, scenario_id: str) -> CounterfactualScenario:
        """Confirm a counterfactual scenario."""
        old = self._counterfactuals.get(scenario_id)
        if old is None:
            raise RuntimeCoreInvariantError("Unknown scenario_id")
        now = self._now()
        confirmed = CounterfactualScenario(
            scenario_id=old.scenario_id,
            tenant_id=old.tenant_id,
            intervention_ref=old.intervention_ref,
            premise=old.premise,
            status=CounterfactualStatus.CONFIRMED,
            created_at=old.created_at,
        )
        self._counterfactuals[scenario_id] = confirmed
        _emit(self._events, "counterfactual_confirmed", {
            "scenario_id": scenario_id,
        }, scenario_id, self._now())
        return confirmed

    def reject_counterfactual(self, scenario_id: str) -> CounterfactualScenario:
        """Reject a counterfactual scenario."""
        old = self._counterfactuals.get(scenario_id)
        if old is None:
            raise RuntimeCoreInvariantError("Unknown scenario_id")
        now = self._now()
        rejected = CounterfactualScenario(
            scenario_id=old.scenario_id,
            tenant_id=old.tenant_id,
            intervention_ref=old.intervention_ref,
            premise=old.premise,
            status=CounterfactualStatus.REJECTED,
            created_at=old.created_at,
        )
        self._counterfactuals[scenario_id] = rejected
        _emit(self._events, "counterfactual_rejected", {
            "scenario_id": scenario_id,
        }, scenario_id, self._now())
        return rejected

    # ------------------------------------------------------------------
    # Propagation (BFS)
    # ------------------------------------------------------------------

    def trace_propagation(
        self,
        tenant_id: str,
        source_node_id: str,
    ) -> tuple[PropagationRecord, ...]:
        """BFS from source through edges, creating PropagationRecords with hop_count."""
        if source_node_id not in self._nodes:
            raise RuntimeCoreInvariantError("Unknown source node")

        now = self._now()
        records: list[PropagationRecord] = []

        # Build adjacency list from edges
        adjacency: dict[str, list[str]] = {}
        for edge in self._edges.values():
            adjacency.setdefault(edge.cause_ref, []).append(edge.effect_ref)

        visited: set[str] = {source_node_id}
        queue: deque[tuple[str, int]] = deque()

        for neighbor in adjacency.get(source_node_id, []):
            if neighbor not in visited:
                queue.append((neighbor, 1))
                visited.add(neighbor)

        while queue:
            current, hops = queue.popleft()
            pid = stable_identifier("prop-causrt", {
                "source": source_node_id, "target": current, "hops": str(hops),
            })
            if pid not in self._propagations:
                rec = PropagationRecord(
                    propagation_id=pid,
                    tenant_id=tenant_id,
                    source_ref=source_node_id,
                    target_ref=current,
                    hop_count=hops,
                    created_at=now,
                )
                self._propagations[pid] = rec
                records.append(rec)

            for neighbor in adjacency.get(current, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, hops + 1))

        _emit(self._events, "propagation_traced", {
            "source": source_node_id, "records": len(records),
        }, source_node_id, self._now())
        return tuple(records)

    # ------------------------------------------------------------------
    # Attribution
    # ------------------------------------------------------------------

    def attribute_outcome(
        self,
        attribution_id: str,
        tenant_id: str,
        outcome_ref: str,
        cause_ref: str,
        strength: AttributionStrength = AttributionStrength.MODERATE,
        evidence_count: int = 0,
    ) -> CausalAttribution:
        """Create a causal attribution. Duplicate attribution_id raises."""
        if attribution_id in self._attributions:
            raise RuntimeCoreInvariantError("Duplicate attribution_id")
        now = self._now()
        attr = CausalAttribution(
            attribution_id=attribution_id,
            tenant_id=tenant_id,
            outcome_ref=outcome_ref,
            cause_ref=cause_ref,
            strength=strength,
            evidence_count=evidence_count,
            created_at=now,
        )
        self._attributions[attribution_id] = attr
        _emit(self._events, "outcome_attributed", {
            "attribution_id": attribution_id, "outcome": outcome_ref, "cause": cause_ref,
        }, attribution_id, self._now())
        return attr

    # ------------------------------------------------------------------
    # Assessment
    # ------------------------------------------------------------------

    def causal_assessment(
        self,
        assessment_id: str,
        tenant_id: str,
    ) -> CausalAssessment:
        """Produce a causal assessment for a tenant."""
        now = self._now()
        t_nodes = sum(1 for n in self._nodes.values() if n.tenant_id == tenant_id)
        t_edges = sum(1 for e in self._edges.values() if e.tenant_id == tenant_id)
        t_interventions = sum(1 for i in self._interventions.values() if i.tenant_id == tenant_id)
        t_attributions = sum(1 for a in self._attributions.values() if a.tenant_id == tenant_id)

        coverage = t_attributions / t_nodes if t_nodes > 0 else 1.0
        coverage = max(0.0, min(1.0, coverage))

        asm = CausalAssessment(
            assessment_id=assessment_id,
            tenant_id=tenant_id,
            total_nodes=t_nodes,
            total_edges=t_edges,
            total_interventions=t_interventions,
            attribution_coverage=coverage,
            assessed_at=now,
        )
        _emit(self._events, "causal_assessed", {
            "assessment_id": assessment_id, "coverage": coverage,
        }, assessment_id, self._now())
        return asm

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------

    def causal_snapshot(
        self,
        snapshot_id: str,
        tenant_id: str,
    ) -> CausalSnapshot:
        """Produce a point-in-time snapshot for a tenant."""
        now = self._now()
        return CausalSnapshot(
            snapshot_id=snapshot_id,
            tenant_id=tenant_id,
            total_nodes=sum(1 for n in self._nodes.values() if n.tenant_id == tenant_id),
            total_edges=sum(1 for e in self._edges.values() if e.tenant_id == tenant_id),
            total_interventions=sum(1 for i in self._interventions.values() if i.tenant_id == tenant_id),
            total_counterfactuals=sum(1 for c in self._counterfactuals.values() if c.tenant_id == tenant_id),
            total_attributions=sum(1 for a in self._attributions.values() if a.tenant_id == tenant_id),
            total_violations=sum(1 for v in self._violations.values() if v.get("tenant_id") == tenant_id),
            captured_at=now,
        )

    # ------------------------------------------------------------------
    # Closure report
    # ------------------------------------------------------------------

    def causal_closure_report(
        self,
        report_id: str,
        tenant_id: str,
    ) -> CausalClosureReport:
        """Produce a final closure report for a tenant."""
        now = self._now()
        return CausalClosureReport(
            report_id=report_id,
            tenant_id=tenant_id,
            total_nodes=sum(1 for n in self._nodes.values() if n.tenant_id == tenant_id),
            total_edges=sum(1 for e in self._edges.values() if e.tenant_id == tenant_id),
            total_interventions=sum(1 for i in self._interventions.values() if i.tenant_id == tenant_id),
            total_attributions=sum(1 for a in self._attributions.values() if a.tenant_id == tenant_id),
            total_violations=sum(1 for v in self._violations.values() if v.get("tenant_id") == tenant_id),
            created_at=now,
        )

    # ------------------------------------------------------------------
    # Violation detection
    # ------------------------------------------------------------------

    def detect_causal_violations(self, tenant_id: str) -> tuple[dict[str, Any], ...]:
        """Detect causal violations for a tenant. Idempotent.

        Checks:
        1. cycle_in_graph: detect cycles in directed causal edges.
        2. unresolved_intervention: interventions still PROPOSED.
        3. orphan_edge: edges referencing non-existent nodes.
        """
        now = self._now()
        new_violations: list[dict[str, Any]] = []

        # 1. cycle_in_graph (DFS-based cycle detection)
        tenant_edges = [e for e in self._edges.values() if e.tenant_id == tenant_id]
        adj: dict[str, list[str]] = {}
        for e in tenant_edges:
            adj.setdefault(e.cause_ref, []).append(e.effect_ref)

        WHITE, GRAY, BLACK = 0, 1, 2
        color: dict[str, int] = {}
        for n in self._nodes:
            color[n] = WHITE
        # Also include any node referenced in edges
        for e in tenant_edges:
            color.setdefault(e.cause_ref, WHITE)
            color.setdefault(e.effect_ref, WHITE)

        def _dfs(node: str) -> bool:
            color[node] = GRAY
            for neighbor in adj.get(node, []):
                if color.get(neighbor, WHITE) == GRAY:
                    return True
                if color.get(neighbor, WHITE) == WHITE and _dfs(neighbor):
                    return True
            color[node] = BLACK
            return False

        has_cycle = False
        for node in list(color):
            if color[node] == WHITE:
                if _dfs(node):
                    has_cycle = True
                    break

        if has_cycle:
            vid = stable_identifier("viol-causrt", {
                "tenant": tenant_id, "op": "cycle_in_graph",
            })
            if vid not in self._violations:
                v = {
                    "violation_id": vid,
                    "tenant_id": tenant_id,
                    "operation": "cycle_in_graph",
                    "reason": "Cycle detected in causal graph",
                    "detected_at": now,
                }
                self._violations[vid] = v
                new_violations.append(v)

        # 2. unresolved_intervention
        for iid, intervention in self._interventions.items():
            if intervention.tenant_id == tenant_id and intervention.disposition == InterventionDisposition.PROPOSED:
                vid = stable_identifier("viol-causrt", {
                    "intervention": iid, "op": "unresolved_intervention",
                })
                if vid not in self._violations:
                    v = {
                        "violation_id": vid,
                        "tenant_id": tenant_id,
                        "operation": "unresolved_intervention",
                        "reason": "Intervention remains unresolved",
                        "detected_at": now,
                    }
                    self._violations[vid] = v
                    new_violations.append(v)

        # 3. orphan_edge
        for eid, edge in list(self._edges.items()):
            if edge.tenant_id == tenant_id:
                if edge.cause_ref not in self._nodes or edge.effect_ref not in self._nodes:
                    vid = stable_identifier("viol-causrt", {
                        "edge": eid, "op": "orphan_edge",
                    })
                    if vid not in self._violations:
                        v = {
                            "violation_id": vid,
                            "tenant_id": tenant_id,
                            "operation": "orphan_edge",
                            "reason": "Causal edge references missing node",
                            "detected_at": now,
                        }
                        self._violations[vid] = v
                        new_violations.append(v)

        return tuple(new_violations)

    # ------------------------------------------------------------------
    # Collections / snapshot / state_hash
    # ------------------------------------------------------------------

    def _collections(self) -> dict[str, Any]:
        """Return all internal collections."""
        return {
            "attributions": self._attributions,
            "counterfactuals": self._counterfactuals,
            "decisions": self._decisions,
            "edges": self._edges,
            "interventions": self._interventions,
            "nodes": self._nodes,
            "propagations": self._propagations,
            "violations": self._violations,
        }

    def snapshot(self) -> dict[str, Any]:
        """Capture complete engine state as a serializable dict."""
        result: dict[str, Any] = {}
        for name, collection in self._collections().items():
            if isinstance(collection, dict):
                result[name] = {
                    k: v.to_dict() if hasattr(v, "to_dict") else v
                    for k, v in collection.items()
                }
            elif isinstance(collection, list):
                result[name] = [
                    v.to_dict() if hasattr(v, "to_dict") else v
                    for v in collection
                ]
        result["_state_hash"] = self.state_hash()
        return result

    def state_hash(self) -> str:
        """Compute a deterministic hash of engine state (sorted keys, full 64-char)."""
        parts = [
            f"attributions={self.attribution_count}",
            f"counterfactuals={self.counterfactual_count}",
            f"decisions={len(self._decisions)}",
            f"edges={self.edge_count}",
            f"interventions={self.intervention_count}",
            f"nodes={self.node_count}",
            f"propagations={self.propagation_count}",
            f"violations={self.violation_count}",
        ]
        return sha256("|".join(parts).encode()).hexdigest()
