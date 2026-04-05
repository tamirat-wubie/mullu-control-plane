"""Purpose: executive control tower / strategic planning engine.
Governance scope: registering objectives, issuing directives, rebalancing
    priorities, triggering scenario plans, intervening in lower layers,
    producing strategic decisions and control tower snapshots.
Dependencies: executive_control contracts, event_spine, core invariants.
Invariants:
  - Objectives gate all directives.
  - Priority shifts are traceable.
  - Scenario plans require explicit completion.
  - Interventions reference directives.
  - Every mutation emits an event.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from ..contracts.executive_control import (
    ControlTowerHealth,
    ControlTowerSnapshot,
    DirectiveStatus,
    DirectiveType,
    ExecutiveIntervention,
    InterventionSeverity,
    ObjectiveStatus,
    PortfolioDirectiveBinding,
    PriorityLevel,
    PriorityShift,
    ScenarioOutcome,
    ScenarioPlan,
    ScenarioStatus,
    StrategicDecision,
    StrategicDirective,
    StrategicObjective,
)
from ..contracts.event import EventRecord, EventSource, EventType
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-ectl", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class ExecutiveControlEngine:
    """Engine for executive control tower and strategic planning."""

    def __init__(self, event_spine: EventSpineEngine) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._objectives: dict[str, StrategicObjective] = {}
        self._directives: dict[str, StrategicDirective] = {}
        self._priority_shifts: list[PriorityShift] = []
        self._scenarios: dict[str, ScenarioPlan] = {}
        self._scenario_outcomes: dict[str, ScenarioOutcome] = {}
        self._interventions: dict[str, ExecutiveIntervention] = {}
        self._decisions: dict[str, StrategicDecision] = {}
        self._bindings: list[PortfolioDirectiveBinding] = []

    # ------------------------------------------------------------------
    # Strategic objectives
    # ------------------------------------------------------------------

    def register_objective(
        self,
        objective_id: str,
        title: str,
        *,
        description: str = "",
        priority: PriorityLevel = PriorityLevel.P2_MEDIUM,
        target_kpi: str = "",
        target_value: float = 0.0,
        current_value: float = 0.0,
        tolerance_pct: float = 5.0,
        owner: str = "",
        scope_ref_ids: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> StrategicObjective:
        if objective_id in self._objectives:
            raise RuntimeCoreInvariantError("objective already exists")
        now = _now_iso()
        obj = StrategicObjective(
            objective_id=objective_id,
            title=title,
            description=description,
            priority=priority,
            status=ObjectiveStatus.ACTIVE,
            target_kpi=target_kpi,
            target_value=target_value,
            current_value=current_value,
            tolerance_pct=tolerance_pct,
            owner=owner,
            scope_ref_ids=tuple(scope_ref_ids or []),
            created_at=now,
            updated_at=now,
            metadata=metadata or {},
        )
        self._objectives[objective_id] = obj
        _emit(self._events, "objective_registered", {
            "objective_id": objective_id,
            "priority": priority.value,
            "target_kpi": target_kpi,
        }, objective_id)
        return obj

    def get_objective(self, objective_id: str) -> StrategicObjective | None:
        return self._objectives.get(objective_id)

    def update_objective_kpi(
        self,
        objective_id: str,
        current_value: float,
    ) -> StrategicObjective:
        if objective_id not in self._objectives:
            raise RuntimeCoreInvariantError("objective not found")
        old = self._objectives[objective_id]
        now = _now_iso()
        updated = StrategicObjective(
            objective_id=old.objective_id,
            title=old.title,
            description=old.description,
            priority=old.priority,
            status=old.status,
            target_kpi=old.target_kpi,
            target_value=old.target_value,
            current_value=current_value,
            tolerance_pct=old.tolerance_pct,
            owner=old.owner,
            scope_ref_ids=old.scope_ref_ids,
            created_at=old.created_at,
            updated_at=now,
            metadata=dict(old.metadata),
        )
        self._objectives[objective_id] = updated
        _emit(self._events, "objective_kpi_updated", {
            "objective_id": objective_id,
            "current_value": current_value,
            "target_value": old.target_value,
        }, objective_id)
        return updated

    def set_objective_status(
        self,
        objective_id: str,
        status: ObjectiveStatus,
    ) -> StrategicObjective:
        if objective_id not in self._objectives:
            raise RuntimeCoreInvariantError("objective not found")
        old = self._objectives[objective_id]
        now = _now_iso()
        updated = StrategicObjective(
            objective_id=old.objective_id,
            title=old.title,
            description=old.description,
            priority=old.priority,
            status=status,
            target_kpi=old.target_kpi,
            target_value=old.target_value,
            current_value=old.current_value,
            tolerance_pct=old.tolerance_pct,
            owner=old.owner,
            scope_ref_ids=old.scope_ref_ids,
            created_at=old.created_at,
            updated_at=now,
            metadata=dict(old.metadata),
        )
        self._objectives[objective_id] = updated
        _emit(self._events, "objective_status_changed", {
            "objective_id": objective_id,
            "status": status.value,
        }, objective_id)
        return updated

    def check_objective_health(self, objective_id: str) -> dict[str, Any]:
        """Check if an objective's KPI is on track."""
        if objective_id not in self._objectives:
            raise RuntimeCoreInvariantError("objective not found")
        obj = self._objectives[objective_id]
        if obj.target_value == 0:
            gap_pct = 0.0
        else:
            gap_pct = ((obj.target_value - obj.current_value) / abs(obj.target_value)) * 100
        on_track = gap_pct <= obj.tolerance_pct
        return {
            "objective_id": objective_id,
            "target_value": obj.target_value,
            "current_value": obj.current_value,
            "gap_pct": gap_pct,
            "tolerance_pct": obj.tolerance_pct,
            "on_track": on_track,
        }

    # ------------------------------------------------------------------
    # Directives
    # ------------------------------------------------------------------

    def issue_directive(
        self,
        directive_id: str,
        title: str,
        directive_type: DirectiveType,
        *,
        objective_id: str = "",
        reason: str = "",
        target_scope_ref_id: str = "",
        parameters: dict[str, Any] | None = None,
        issued_by: str = "",
        expires_at: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> StrategicDirective:
        if directive_id in self._directives:
            raise RuntimeCoreInvariantError("directive already exists")
        now = _now_iso()
        directive = StrategicDirective(
            directive_id=directive_id,
            objective_id=objective_id,
            directive_type=directive_type,
            status=DirectiveStatus.ISSUED,
            title=title,
            reason=reason,
            target_scope_ref_id=target_scope_ref_id,
            parameters=parameters or {},
            issued_by=issued_by,
            issued_at=now,
            expires_at=expires_at,
            metadata=metadata or {},
        )
        self._directives[directive_id] = directive
        _emit(self._events, "directive_issued", {
            "directive_id": directive_id,
            "directive_type": directive_type.value,
            "objective_id": objective_id,
        }, directive_id)
        return directive

    def get_directive(self, directive_id: str) -> StrategicDirective | None:
        return self._directives.get(directive_id)

    def acknowledge_directive(self, directive_id: str) -> StrategicDirective:
        if directive_id not in self._directives:
            raise RuntimeCoreInvariantError("directive not found")
        old = self._directives[directive_id]
        if old.status != DirectiveStatus.ISSUED:
            raise RuntimeCoreInvariantError("directive is not in ISSUED state")
        updated = StrategicDirective(
            directive_id=old.directive_id,
            objective_id=old.objective_id,
            directive_type=old.directive_type,
            status=DirectiveStatus.ACKNOWLEDGED,
            title=old.title,
            reason=old.reason,
            target_scope_ref_id=old.target_scope_ref_id,
            parameters=dict(old.parameters),
            issued_by=old.issued_by,
            issued_at=old.issued_at,
            expires_at=old.expires_at,
            metadata=dict(old.metadata),
        )
        self._directives[directive_id] = updated
        _emit(self._events, "directive_acknowledged", {
            "directive_id": directive_id,
        }, directive_id)
        return updated

    def execute_directive(self, directive_id: str) -> StrategicDirective:
        if directive_id not in self._directives:
            raise RuntimeCoreInvariantError("directive not found")
        old = self._directives[directive_id]
        if old.status not in (DirectiveStatus.ISSUED, DirectiveStatus.ACKNOWLEDGED):
            raise RuntimeCoreInvariantError("directive cannot be executed from current state")
        updated = StrategicDirective(
            directive_id=old.directive_id,
            objective_id=old.objective_id,
            directive_type=old.directive_type,
            status=DirectiveStatus.EXECUTED,
            title=old.title,
            reason=old.reason,
            target_scope_ref_id=old.target_scope_ref_id,
            parameters=dict(old.parameters),
            issued_by=old.issued_by,
            issued_at=old.issued_at,
            expires_at=old.expires_at,
            metadata=dict(old.metadata),
        )
        self._directives[directive_id] = updated
        _emit(self._events, "directive_executed", {
            "directive_id": directive_id,
            "directive_type": old.directive_type.value,
        }, directive_id)
        return updated

    def reject_directive(self, directive_id: str, *, reason: str = "") -> StrategicDirective:
        if directive_id not in self._directives:
            raise RuntimeCoreInvariantError("directive not found")
        old = self._directives[directive_id]
        updated = StrategicDirective(
            directive_id=old.directive_id,
            objective_id=old.objective_id,
            directive_type=old.directive_type,
            status=DirectiveStatus.REJECTED,
            title=old.title,
            reason=reason or old.reason,
            target_scope_ref_id=old.target_scope_ref_id,
            parameters=dict(old.parameters),
            issued_by=old.issued_by,
            issued_at=old.issued_at,
            expires_at=old.expires_at,
            metadata=dict(old.metadata),
        )
        self._directives[directive_id] = updated
        _emit(self._events, "directive_rejected", {
            "directive_id": directive_id,
            "reason": reason,
        }, directive_id)
        return updated

    # ------------------------------------------------------------------
    # Priority shifts
    # ------------------------------------------------------------------

    def shift_priority(
        self,
        shift_id: str,
        directive_id: str,
        target_scope_ref_id: str,
        from_priority: PriorityLevel,
        to_priority: PriorityLevel,
        *,
        reason: str = "",
    ) -> PriorityShift:
        now = _now_iso()
        shift = PriorityShift(
            shift_id=shift_id,
            directive_id=directive_id,
            from_priority=from_priority,
            to_priority=to_priority,
            target_scope_ref_id=target_scope_ref_id,
            reason=reason,
            shifted_at=now,
        )
        self._priority_shifts.append(shift)
        _emit(self._events, "priority_shifted", {
            "shift_id": shift_id,
            "directive_id": directive_id,
            "from": from_priority.value,
            "to": to_priority.value,
            "target": target_scope_ref_id,
        }, shift_id)
        return shift

    # ------------------------------------------------------------------
    # Scenario planning
    # ------------------------------------------------------------------

    def create_scenario(
        self,
        scenario_id: str,
        title: str,
        *,
        objective_id: str = "",
        baseline_snapshot: dict[str, Any] | None = None,
        projected_snapshot: dict[str, Any] | None = None,
        assumptions: list[str] | None = None,
        risk_score: float = 0.0,
        confidence: float = 0.0,
        metadata: dict[str, Any] | None = None,
    ) -> ScenarioPlan:
        if scenario_id in self._scenarios:
            raise RuntimeCoreInvariantError("scenario already exists")
        now = _now_iso()
        scenario = ScenarioPlan(
            scenario_id=scenario_id,
            objective_id=objective_id,
            title=title,
            status=ScenarioStatus.DRAFT,
            baseline_snapshot=baseline_snapshot or {},
            projected_snapshot=projected_snapshot or {},
            assumptions=tuple(assumptions or []),
            risk_score=risk_score,
            confidence=confidence,
            created_at=now,
            metadata=metadata or {},
        )
        self._scenarios[scenario_id] = scenario
        _emit(self._events, "scenario_created", {
            "scenario_id": scenario_id,
            "objective_id": objective_id,
        }, scenario_id)
        return scenario

    def run_scenario(self, scenario_id: str) -> ScenarioPlan:
        if scenario_id not in self._scenarios:
            raise RuntimeCoreInvariantError("scenario not found")
        old = self._scenarios[scenario_id]
        if old.status != ScenarioStatus.DRAFT:
            raise RuntimeCoreInvariantError("scenario is not in DRAFT state")
        now = _now_iso()
        updated = ScenarioPlan(
            scenario_id=old.scenario_id,
            objective_id=old.objective_id,
            title=old.title,
            status=ScenarioStatus.RUNNING,
            baseline_snapshot=dict(old.baseline_snapshot),
            projected_snapshot=dict(old.projected_snapshot),
            assumptions=old.assumptions,
            risk_score=old.risk_score,
            confidence=old.confidence,
            created_at=old.created_at,
            metadata=dict(old.metadata),
        )
        self._scenarios[scenario_id] = updated
        _emit(self._events, "scenario_running", {
            "scenario_id": scenario_id,
        }, scenario_id)
        return updated

    def complete_scenario(
        self,
        scenario_id: str,
        *,
        projected_snapshot: dict[str, Any] | None = None,
        confidence: float | None = None,
        risk_score: float | None = None,
    ) -> ScenarioPlan:
        if scenario_id not in self._scenarios:
            raise RuntimeCoreInvariantError("scenario not found")
        old = self._scenarios[scenario_id]
        if old.status != ScenarioStatus.RUNNING:
            raise RuntimeCoreInvariantError("scenario is not RUNNING")
        now = _now_iso()
        updated = ScenarioPlan(
            scenario_id=old.scenario_id,
            objective_id=old.objective_id,
            title=old.title,
            status=ScenarioStatus.COMPLETED,
            baseline_snapshot=dict(old.baseline_snapshot),
            projected_snapshot=projected_snapshot if projected_snapshot is not None else dict(old.projected_snapshot),
            assumptions=old.assumptions,
            risk_score=risk_score if risk_score is not None else old.risk_score,
            confidence=confidence if confidence is not None else old.confidence,
            created_at=old.created_at,
            completed_at=now,
            metadata=dict(old.metadata),
        )
        self._scenarios[scenario_id] = updated
        _emit(self._events, "scenario_completed", {
            "scenario_id": scenario_id,
            "confidence": updated.confidence,
        }, scenario_id)
        return updated

    def assess_scenario(
        self,
        outcome_id: str,
        scenario_id: str,
        verdict: str,
        *,
        projected_improvement_pct: float = 0.0,
        projected_risk_delta: float = 0.0,
        projected_cost_delta: float = 0.0,
        recommendation: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> ScenarioOutcome:
        if scenario_id not in self._scenarios:
            raise RuntimeCoreInvariantError("scenario not found")
        now = _now_iso()
        outcome = ScenarioOutcome(
            outcome_id=outcome_id,
            scenario_id=scenario_id,
            verdict=verdict,
            projected_improvement_pct=projected_improvement_pct,
            projected_risk_delta=projected_risk_delta,
            projected_cost_delta=projected_cost_delta,
            recommendation=recommendation,
            assessed_at=now,
            metadata=metadata or {},
        )
        self._scenario_outcomes[outcome_id] = outcome
        _emit(self._events, "scenario_assessed", {
            "outcome_id": outcome_id,
            "scenario_id": scenario_id,
            "verdict": verdict,
        }, outcome_id)
        return outcome

    def get_scenario(self, scenario_id: str) -> ScenarioPlan | None:
        return self._scenarios.get(scenario_id)

    def get_scenario_outcome(self, outcome_id: str) -> ScenarioOutcome | None:
        return self._scenario_outcomes.get(outcome_id)

    # ------------------------------------------------------------------
    # Executive interventions
    # ------------------------------------------------------------------

    def intervene(
        self,
        intervention_id: str,
        directive_id: str,
        action: str,
        *,
        severity: InterventionSeverity = InterventionSeverity.MEDIUM,
        target_engine: str = "",
        target_ref_id: str = "",
        reason: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> ExecutiveIntervention:
        if intervention_id in self._interventions:
            raise RuntimeCoreInvariantError("intervention already exists")
        now = _now_iso()
        intervention = ExecutiveIntervention(
            intervention_id=intervention_id,
            directive_id=directive_id,
            severity=severity,
            target_engine=target_engine,
            target_ref_id=target_ref_id,
            action=action,
            reason=reason,
            intervened_at=now,
            metadata=metadata or {},
        )
        self._interventions[intervention_id] = intervention
        _emit(self._events, "intervention_created", {
            "intervention_id": intervention_id,
            "directive_id": directive_id,
            "severity": severity.value,
            "action": action,
        }, intervention_id)
        return intervention

    def resolve_intervention(self, intervention_id: str) -> ExecutiveIntervention:
        if intervention_id not in self._interventions:
            raise RuntimeCoreInvariantError("intervention not found")
        old = self._interventions[intervention_id]
        now = _now_iso()
        updated = ExecutiveIntervention(
            intervention_id=old.intervention_id,
            directive_id=old.directive_id,
            severity=old.severity,
            target_engine=old.target_engine,
            target_ref_id=old.target_ref_id,
            action=old.action,
            reason=old.reason,
            intervened_at=old.intervened_at,
            resolved_at=now,
            metadata=dict(old.metadata),
        )
        self._interventions[intervention_id] = updated
        _emit(self._events, "intervention_resolved", {
            "intervention_id": intervention_id,
        }, intervention_id)
        return updated

    def get_intervention(self, intervention_id: str) -> ExecutiveIntervention | None:
        return self._interventions.get(intervention_id)

    # ------------------------------------------------------------------
    # Strategic decisions
    # ------------------------------------------------------------------

    def record_decision(
        self,
        decision_id: str,
        title: str,
        *,
        objective_id: str = "",
        directive_ids: list[str] | None = None,
        rationale: str = "",
        confidence: float = 0.8,
        risk_score: float = 0.2,
        metadata: dict[str, Any] | None = None,
    ) -> StrategicDecision:
        if decision_id in self._decisions:
            raise RuntimeCoreInvariantError("decision already exists")
        now = _now_iso()
        decision = StrategicDecision(
            decision_id=decision_id,
            objective_id=objective_id,
            directive_ids=tuple(directive_ids or []),
            title=title,
            rationale=rationale,
            confidence=confidence,
            risk_score=risk_score,
            decided_at=now,
            metadata=metadata or {},
        )
        self._decisions[decision_id] = decision
        _emit(self._events, "decision_recorded", {
            "decision_id": decision_id,
            "objective_id": objective_id,
            "confidence": confidence,
        }, decision_id)
        return decision

    def get_decision(self, decision_id: str) -> StrategicDecision | None:
        return self._decisions.get(decision_id)

    # ------------------------------------------------------------------
    # Portfolio directive bindings
    # ------------------------------------------------------------------

    def bind_directive_to_portfolio(
        self,
        binding_id: str,
        directive_id: str,
        *,
        portfolio_ref_id: str = "",
        campaign_ref_id: str = "",
        domain_ref_id: str = "",
        effect: str = "",
    ) -> PortfolioDirectiveBinding:
        if directive_id not in self._directives:
            raise RuntimeCoreInvariantError("directive not found")
        now = _now_iso()
        binding = PortfolioDirectiveBinding(
            binding_id=binding_id,
            directive_id=directive_id,
            portfolio_ref_id=portfolio_ref_id,
            campaign_ref_id=campaign_ref_id,
            domain_ref_id=domain_ref_id,
            effect=effect,
            bound_at=now,
        )
        self._bindings.append(binding)
        _emit(self._events, "directive_bound", {
            "binding_id": binding_id,
            "directive_id": directive_id,
            "portfolio_ref_id": portfolio_ref_id,
        }, binding_id)
        return binding

    # ------------------------------------------------------------------
    # Snapshots
    # ------------------------------------------------------------------

    def capture_snapshot(self, snapshot_id: str) -> ControlTowerSnapshot:
        active_obj = sum(1 for o in self._objectives.values() if o.status == ObjectiveStatus.ACTIVE)
        active_dir = sum(1 for d in self._directives.values() if d.status in (DirectiveStatus.ISSUED, DirectiveStatus.ACKNOWLEDGED))
        pending_sc = sum(1 for s in self._scenarios.values() if s.status in (ScenarioStatus.DRAFT, ScenarioStatus.RUNNING))
        active_int = sum(1 for i in self._interventions.values() if i.resolved_at == "")

        # Determine health
        if active_int > 0 and any(i.severity == InterventionSeverity.CRITICAL for i in self._interventions.values() if i.resolved_at == ""):
            health = ControlTowerHealth.CRITICAL
        elif active_int > 0:
            health = ControlTowerHealth.DEGRADED
        else:
            health = ControlTowerHealth.HEALTHY

        now = _now_iso()
        snap = ControlTowerSnapshot(
            snapshot_id=snapshot_id,
            health=health,
            active_objectives=active_obj,
            active_directives=active_dir,
            pending_scenarios=pending_sc,
            interventions_in_progress=active_int,
            total_priority_shifts=len(self._priority_shifts),
            total_decisions=len(self._decisions),
            captured_at=now,
        )
        _emit(self._events, "snapshot_captured", {
            "snapshot_id": snapshot_id,
            "health": health.value,
        }, snapshot_id)
        return snap

    # ------------------------------------------------------------------
    # Queries and properties
    # ------------------------------------------------------------------

    @property
    def objective_count(self) -> int:
        return len(self._objectives)

    @property
    def directive_count(self) -> int:
        return len(self._directives)

    @property
    def scenario_count(self) -> int:
        return len(self._scenarios)

    @property
    def intervention_count(self) -> int:
        return len(self._interventions)

    @property
    def decision_count(self) -> int:
        return len(self._decisions)

    @property
    def priority_shift_count(self) -> int:
        return len(self._priority_shifts)

    @property
    def binding_count(self) -> int:
        return len(self._bindings)

    def get_priority_shifts(self) -> tuple[PriorityShift, ...]:
        return tuple(self._priority_shifts)

    def get_bindings(self) -> tuple[PortfolioDirectiveBinding, ...]:
        return tuple(self._bindings)

    def state_hash(self) -> str:
        parts = [
            f"shifts={len(self._priority_shifts)}",
            f"bindings={len(self._bindings)}",
        ]
        for oid in sorted(self._objectives):
            o = self._objectives[oid]
            parts.append(f"obj:{oid}:{o.status.value}:{o.priority.value}")
        for did in sorted(self._directives):
            d = self._directives[did]
            parts.append(f"dir:{did}:{d.status.value}:{d.directive_type.value}")
        for sid in sorted(self._scenarios):
            s = self._scenarios[sid]
            parts.append(f"scn:{sid}:{s.status.value}")
        for iid in sorted(self._interventions):
            i = self._interventions[iid]
            parts.append(f"int:{iid}:{i.severity.value}")
        for dec_id in sorted(self._decisions):
            dec = self._decisions[dec_id]
            parts.append(f"dec:{dec_id}:{dec.confidence}")
        for soid in sorted(self._scenario_outcomes):
            so = self._scenario_outcomes[soid]
            parts.append(f"sout:{soid}:{so.verdict}")
        digest = sha256("|".join(parts).encode()).hexdigest()
        return digest
