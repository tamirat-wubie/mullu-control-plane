"""Purpose: policy simulation / governance sandbox runtime engine.
Governance scope: registering sandbox scenarios, applying candidate rules
    without mutating live state, comparing baseline vs simulated outcomes,
    aggregating impact, scoring adoption readiness, detecting violations.
Dependencies: policy_simulation contracts, event_spine, core invariants.
Invariants:
  - Duplicate IDs raise.
  - Sandbox never mutates live runtimes.
  - Every mutation emits an event.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from ..contracts.policy_simulation import (
    AdoptionReadiness,
    AdoptionRecommendation,
    DiffDisposition,
    PolicyDiffRecord,
    PolicyImpactLevel,
    PolicySimulationRequest,
    PolicySimulationResult,
    PolicySimulationScenario,
    RuntimeImpactRecord,
    SandboxAssessment,
    SandboxClosureReport,
    SandboxScope,
    SandboxSnapshot,
    SandboxViolation,
    SimulationMode,
    SimulationStatus,
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
        event_id=stable_identifier("evt-psim", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


_SIM_TERMINAL = frozenset({SimulationStatus.COMPLETED, SimulationStatus.FAILED, SimulationStatus.CANCELLED})

_IMPACT_RANK = {
    PolicyImpactLevel.NONE: 0,
    PolicyImpactLevel.LOW: 1,
    PolicyImpactLevel.MEDIUM: 2,
    PolicyImpactLevel.HIGH: 3,
    PolicyImpactLevel.CRITICAL: 4,
}


class PolicySimulationEngine:
    """Policy simulation / governance sandbox runtime engine."""

    def __init__(self, event_spine: EventSpineEngine) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._requests: dict[str, PolicySimulationRequest] = {}
        self._scenarios: dict[str, PolicySimulationScenario] = {}
        self._results: dict[str, PolicySimulationResult] = {}
        self._diffs: dict[str, PolicyDiffRecord] = {}
        self._impacts: dict[str, RuntimeImpactRecord] = {}
        self._recommendations: dict[str, AdoptionRecommendation] = {}
        self._violations: dict[str, SandboxViolation] = {}
        self._assessments: dict[str, SandboxAssessment] = {}

    # -- Properties ----------------------------------------------------------

    @property
    def request_count(self) -> int:
        return len(self._requests)

    @property
    def scenario_count(self) -> int:
        return len(self._scenarios)

    @property
    def result_count(self) -> int:
        return len(self._results)

    @property
    def diff_count(self) -> int:
        return len(self._diffs)

    @property
    def impact_count(self) -> int:
        return len(self._impacts)

    @property
    def recommendation_count(self) -> int:
        return len(self._recommendations)

    @property
    def violation_count(self) -> int:
        return len(self._violations)

    @property
    def assessment_count(self) -> int:
        return len(self._assessments)

    # -- Simulation requests -------------------------------------------------

    def register_simulation(
        self,
        request_id: str,
        tenant_id: str,
        display_name: str,
        mode: SimulationMode = SimulationMode.DRY_RUN,
        scope: SandboxScope = SandboxScope.TENANT,
        candidate_rule_count: int = 0,
    ) -> PolicySimulationRequest:
        if request_id in self._requests:
            raise RuntimeCoreInvariantError(f"duplicate request_id: {request_id}")
        now = _now_iso()
        req = PolicySimulationRequest(
            request_id=request_id, tenant_id=tenant_id, display_name=display_name,
            mode=mode, scope=scope, status=SimulationStatus.DRAFT,
            candidate_rule_count=candidate_rule_count, created_at=now,
        )
        self._requests[request_id] = req
        _emit(self._events, "register_simulation", {"request_id": request_id}, request_id)
        return req

    def get_simulation(self, request_id: str) -> PolicySimulationRequest:
        if request_id not in self._requests:
            raise RuntimeCoreInvariantError(f"unknown request_id: {request_id}")
        return self._requests[request_id]

    def start_simulation(self, request_id: str) -> PolicySimulationRequest:
        req = self.get_simulation(request_id)
        if req.status in _SIM_TERMINAL:
            raise RuntimeCoreInvariantError(f"simulation {request_id} is in terminal state")
        now = _now_iso()
        updated = PolicySimulationRequest(
            request_id=req.request_id, tenant_id=req.tenant_id, display_name=req.display_name,
            mode=req.mode, scope=req.scope, status=SimulationStatus.RUNNING,
            candidate_rule_count=req.candidate_rule_count, created_at=now,
        )
        self._requests[request_id] = updated
        _emit(self._events, "start_simulation", {"request_id": request_id}, request_id)
        return updated

    def complete_simulation(self, request_id: str) -> PolicySimulationRequest:
        req = self.get_simulation(request_id)
        if req.status in _SIM_TERMINAL:
            raise RuntimeCoreInvariantError(f"simulation {request_id} is in terminal state")
        now = _now_iso()
        updated = PolicySimulationRequest(
            request_id=req.request_id, tenant_id=req.tenant_id, display_name=req.display_name,
            mode=req.mode, scope=req.scope, status=SimulationStatus.COMPLETED,
            candidate_rule_count=req.candidate_rule_count, created_at=now,
        )
        self._requests[request_id] = updated
        _emit(self._events, "complete_simulation", {"request_id": request_id}, request_id)
        return updated

    def fail_simulation(self, request_id: str) -> PolicySimulationRequest:
        req = self.get_simulation(request_id)
        if req.status in _SIM_TERMINAL:
            raise RuntimeCoreInvariantError(f"simulation {request_id} is in terminal state")
        now = _now_iso()
        updated = PolicySimulationRequest(
            request_id=req.request_id, tenant_id=req.tenant_id, display_name=req.display_name,
            mode=req.mode, scope=req.scope, status=SimulationStatus.FAILED,
            candidate_rule_count=req.candidate_rule_count, created_at=now,
        )
        self._requests[request_id] = updated
        _emit(self._events, "fail_simulation", {"request_id": request_id}, request_id)
        return updated

    def cancel_simulation(self, request_id: str) -> PolicySimulationRequest:
        req = self.get_simulation(request_id)
        if req.status in _SIM_TERMINAL:
            raise RuntimeCoreInvariantError(f"simulation {request_id} is in terminal state")
        now = _now_iso()
        updated = PolicySimulationRequest(
            request_id=req.request_id, tenant_id=req.tenant_id, display_name=req.display_name,
            mode=req.mode, scope=req.scope, status=SimulationStatus.CANCELLED,
            candidate_rule_count=req.candidate_rule_count, created_at=now,
        )
        self._requests[request_id] = updated
        _emit(self._events, "cancel_simulation", {"request_id": request_id}, request_id)
        return updated

    def simulations_for_tenant(self, tenant_id: str) -> tuple[PolicySimulationRequest, ...]:
        return tuple(r for r in self._requests.values() if r.tenant_id == tenant_id)

    # -- Scenarios -----------------------------------------------------------

    def add_scenario(
        self,
        scenario_id: str,
        request_id: str,
        tenant_id: str,
        display_name: str,
        target_runtime: str,
        baseline_outcome: str,
        simulated_outcome: str,
        impact_level: PolicyImpactLevel = PolicyImpactLevel.NONE,
    ) -> PolicySimulationScenario:
        if scenario_id in self._scenarios:
            raise RuntimeCoreInvariantError(f"duplicate scenario_id: {scenario_id}")
        if request_id not in self._requests:
            raise RuntimeCoreInvariantError(f"unknown request_id: {request_id}")
        now = _now_iso()
        # Auto-determine impact if outcomes differ
        if baseline_outcome != simulated_outcome and impact_level == PolicyImpactLevel.NONE:
            impact_level = PolicyImpactLevel.MEDIUM
        scenario = PolicySimulationScenario(
            scenario_id=scenario_id, request_id=request_id, tenant_id=tenant_id,
            display_name=display_name, target_runtime=target_runtime,
            baseline_outcome=baseline_outcome, simulated_outcome=simulated_outcome,
            impact_level=impact_level, created_at=now,
        )
        self._scenarios[scenario_id] = scenario
        _emit(self._events, "add_scenario", {"scenario_id": scenario_id, "impact": impact_level.value}, scenario_id)
        return scenario

    def get_scenario(self, scenario_id: str) -> PolicySimulationScenario:
        if scenario_id not in self._scenarios:
            raise RuntimeCoreInvariantError(f"unknown scenario_id: {scenario_id}")
        return self._scenarios[scenario_id]

    def scenarios_for_simulation(self, request_id: str) -> tuple[PolicySimulationScenario, ...]:
        return tuple(s for s in self._scenarios.values() if s.request_id == request_id)

    # -- Diffs ---------------------------------------------------------------

    def record_diff(
        self,
        diff_id: str,
        request_id: str,
        tenant_id: str,
        rule_ref: str,
        disposition: DiffDisposition,
        before_value: str,
        after_value: str,
    ) -> PolicyDiffRecord:
        if diff_id in self._diffs:
            raise RuntimeCoreInvariantError(f"duplicate diff_id: {diff_id}")
        if request_id not in self._requests:
            raise RuntimeCoreInvariantError(f"unknown request_id: {request_id}")
        now = _now_iso()
        diff = PolicyDiffRecord(
            diff_id=diff_id, request_id=request_id, tenant_id=tenant_id,
            rule_ref=rule_ref, disposition=disposition,
            before_value=before_value, after_value=after_value, created_at=now,
        )
        self._diffs[diff_id] = diff
        _emit(self._events, "record_diff", {"diff_id": diff_id, "disposition": disposition.value}, diff_id)
        return diff

    def diffs_for_simulation(self, request_id: str) -> tuple[PolicyDiffRecord, ...]:
        return tuple(d for d in self._diffs.values() if d.request_id == request_id)

    # -- Runtime impacts -----------------------------------------------------

    def record_impact(
        self,
        impact_id: str,
        request_id: str,
        tenant_id: str,
        target_runtime: str,
        impact_level: PolicyImpactLevel,
        affected_actions: int = 0,
        blocked_actions: int = 0,
    ) -> RuntimeImpactRecord:
        if impact_id in self._impacts:
            raise RuntimeCoreInvariantError(f"duplicate impact_id: {impact_id}")
        if request_id not in self._requests:
            raise RuntimeCoreInvariantError(f"unknown request_id: {request_id}")
        now = _now_iso()
        impact = RuntimeImpactRecord(
            impact_id=impact_id, request_id=request_id, tenant_id=tenant_id,
            target_runtime=target_runtime, impact_level=impact_level,
            affected_actions=affected_actions, blocked_actions=blocked_actions,
            created_at=now,
        )
        self._impacts[impact_id] = impact
        _emit(self._events, "record_impact", {"impact_id": impact_id, "level": impact_level.value}, impact_id)
        return impact

    def impacts_for_simulation(self, request_id: str) -> tuple[RuntimeImpactRecord, ...]:
        return tuple(i for i in self._impacts.values() if i.request_id == request_id)

    # -- Results and recommendations -----------------------------------------

    def produce_result(self, request_id: str) -> PolicySimulationResult:
        req = self.get_simulation(request_id)
        scenarios = self.scenarios_for_simulation(request_id)
        impacts = self.impacts_for_simulation(request_id)

        impacted = [s for s in scenarios if s.impact_level != PolicyImpactLevel.NONE]
        max_impact = PolicyImpactLevel.NONE
        for s in scenarios:
            if _IMPACT_RANK.get(s.impact_level, 0) > _IMPACT_RANK.get(max_impact, 0):
                max_impact = s.impact_level
        for i in impacts:
            if _IMPACT_RANK.get(i.impact_level, 0) > _IMPACT_RANK.get(max_impact, 0):
                max_impact = i.impact_level

        # Readiness: CRITICAL→BLOCKED, HIGH→NOT_READY, MEDIUM→CAUTION, else→READY
        if max_impact == PolicyImpactLevel.CRITICAL:
            readiness = AdoptionReadiness.BLOCKED
            score = 0.0
        elif max_impact == PolicyImpactLevel.HIGH:
            readiness = AdoptionReadiness.NOT_READY
            score = 0.3
        elif max_impact == PolicyImpactLevel.MEDIUM:
            readiness = AdoptionReadiness.CAUTION
            score = 0.6
        else:
            readiness = AdoptionReadiness.READY
            score = 1.0

        now = _now_iso()
        rid = stable_identifier("res-psim", {"request_id": request_id, "ts": now})
        result = PolicySimulationResult(
            result_id=rid, request_id=request_id, tenant_id=req.tenant_id,
            scenario_count=len(scenarios), impacted_count=len(impacted),
            max_impact_level=max_impact, adoption_readiness=readiness,
            readiness_score=score, completed_at=now,
        )
        self._results[rid] = result
        _emit(self._events, "produce_result", {"result_id": rid, "readiness": readiness.value}, rid)
        return result

    def results_for_simulation(self, request_id: str) -> tuple[PolicySimulationResult, ...]:
        return tuple(r for r in self._results.values() if r.request_id == request_id)

    def recommend_adoption(
        self,
        recommendation_id: str,
        request_id: str,
        tenant_id: str,
    ) -> AdoptionRecommendation:
        if recommendation_id in self._recommendations:
            raise RuntimeCoreInvariantError(f"duplicate recommendation_id: {recommendation_id}")
        results = self.results_for_simulation(request_id)
        if not results:
            raise RuntimeCoreInvariantError(f"no results for simulation {request_id}")
        latest = results[-1]
        now = _now_iso()
        reason = f"max impact: {latest.max_impact_level.value}, readiness: {latest.adoption_readiness.value}"
        rec = AdoptionRecommendation(
            recommendation_id=recommendation_id, request_id=request_id,
            tenant_id=tenant_id, readiness=latest.adoption_readiness,
            readiness_score=latest.readiness_score, reason=reason,
            recommended_at=now,
        )
        self._recommendations[recommendation_id] = rec
        _emit(self._events, "recommend_adoption", {"recommendation_id": recommendation_id}, recommendation_id)
        return rec

    # -- Snapshots -----------------------------------------------------------

    def sandbox_snapshot(self, snapshot_id: str, tenant_id: str) -> SandboxSnapshot:
        now = _now_iso()
        sims = self.simulations_for_tenant(tenant_id)
        completed = [s for s in sims if s.status == SimulationStatus.COMPLETED]
        scenarios = [s for s in self._scenarios.values() if s.tenant_id == tenant_id]
        diffs = [d for d in self._diffs.values() if d.tenant_id == tenant_id]
        impacts = [i for i in self._impacts.values() if i.tenant_id == tenant_id]
        violations = [v for v in self._violations.values() if v.tenant_id == tenant_id]

        snap = SandboxSnapshot(
            snapshot_id=snapshot_id, tenant_id=tenant_id,
            total_simulations=len(sims), completed_simulations=len(completed),
            total_scenarios=len(scenarios), total_diffs=len(diffs),
            total_impacts=len(impacts), total_violations=len(violations),
            captured_at=now,
        )
        _emit(self._events, "sandbox_snapshot", {"snapshot_id": snapshot_id}, snapshot_id)
        return snap

    # -- Assessment ----------------------------------------------------------

    def sandbox_assessment(self, assessment_id: str, tenant_id: str) -> SandboxAssessment:
        if assessment_id in self._assessments:
            raise RuntimeCoreInvariantError(f"duplicate assessment_id: {assessment_id}")
        now = _now_iso()
        sims = self.simulations_for_tenant(tenant_id)
        completed = [s for s in sims if s.status == SimulationStatus.COMPLETED]
        results = [r for r in self._results.values() if r.tenant_id == tenant_id]
        violations = [v for v in self._violations.values() if v.tenant_id == tenant_id]

        total = len(sims)
        comp_rate = len(completed) / total if total > 0 else 1.0
        avg_score = sum(r.readiness_score for r in results) / len(results) if results else 1.0

        assessment = SandboxAssessment(
            assessment_id=assessment_id, tenant_id=tenant_id,
            total_simulations=total,
            completion_rate=round(min(1.0, max(0.0, comp_rate)), 4),
            avg_readiness_score=round(min(1.0, max(0.0, avg_score)), 4),
            total_violations=len(violations), assessed_at=now,
        )
        self._assessments[assessment_id] = assessment
        _emit(self._events, "sandbox_assessment", {"assessment_id": assessment_id}, assessment_id)
        return assessment

    # -- Violations ----------------------------------------------------------

    def detect_sandbox_violations(self, tenant_id: str) -> tuple[SandboxViolation, ...]:
        now = _now_iso()
        new_violations: list[SandboxViolation] = []

        # Simulations stuck in RUNNING
        for req in self._requests.values():
            if req.tenant_id != tenant_id:
                continue
            if req.status == SimulationStatus.RUNNING:
                vid = stable_identifier("viol-psim", {"op": "stuck_running", "request_id": req.request_id})
                if vid not in self._violations:
                    v = SandboxViolation(
                        violation_id=vid, tenant_id=tenant_id,
                        operation="stuck_running",
                        reason=f"simulation {req.request_id} stuck in RUNNING state",
                        detected_at=now,
                    )
                    self._violations[vid] = v
                    new_violations.append(v)

        # Completed simulations with no result
        for req in self._requests.values():
            if req.tenant_id != tenant_id:
                continue
            if req.status == SimulationStatus.COMPLETED:
                has_result = any(r.request_id == req.request_id for r in self._results.values())
                if not has_result:
                    vid = stable_identifier("viol-psim", {"op": "completed_no_result", "request_id": req.request_id})
                    if vid not in self._violations:
                        v = SandboxViolation(
                            violation_id=vid, tenant_id=tenant_id,
                            operation="completed_no_result",
                            reason=f"completed simulation {req.request_id} has no result",
                            detected_at=now,
                        )
                        self._violations[vid] = v
                        new_violations.append(v)

        # BLOCKED adoption with no recommendation
        for result in self._results.values():
            if result.tenant_id != tenant_id:
                continue
            if result.adoption_readiness == AdoptionReadiness.BLOCKED:
                has_rec = any(r.request_id == result.request_id for r in self._recommendations.values())
                if not has_rec:
                    vid = stable_identifier("viol-psim", {"op": "blocked_no_recommendation", "result_id": result.result_id})
                    if vid not in self._violations:
                        v = SandboxViolation(
                            violation_id=vid, tenant_id=tenant_id,
                            operation="blocked_no_recommendation",
                            reason=f"blocked result {result.result_id} has no recommendation",
                            detected_at=now,
                        )
                        self._violations[vid] = v
                        new_violations.append(v)

        if new_violations:
            _emit(self._events, "detect_sandbox_violations", {"tenant_id": tenant_id, "count": len(new_violations)}, tenant_id)
        return tuple(new_violations)

    def violations_for_tenant(self, tenant_id: str) -> tuple[SandboxViolation, ...]:
        return tuple(v for v in self._violations.values() if v.tenant_id == tenant_id)

    # -- Closure report ------------------------------------------------------

    def closure_report(self, report_id: str, tenant_id: str) -> SandboxClosureReport:
        now = _now_iso()
        report = SandboxClosureReport(
            report_id=report_id, tenant_id=tenant_id,
            total_simulations=len(self.simulations_for_tenant(tenant_id)),
            total_scenarios=len([s for s in self._scenarios.values() if s.tenant_id == tenant_id]),
            total_diffs=len([d for d in self._diffs.values() if d.tenant_id == tenant_id]),
            total_impacts=len([i for i in self._impacts.values() if i.tenant_id == tenant_id]),
            total_recommendations=len([r for r in self._recommendations.values() if r.tenant_id == tenant_id]),
            total_violations=len(self.violations_for_tenant(tenant_id)),
            created_at=now,
        )
        _emit(self._events, "closure_report", {"report_id": report_id}, report_id)
        return report

    # -- State hash ----------------------------------------------------------

    def state_hash(self) -> str:
        parts: list[str] = []
        for k in sorted(self._requests):
            parts.append(f"sim:{k}:{self._requests[k].status.value}")
        for k in sorted(self._scenarios):
            parts.append(f"scenario:{k}:{self._scenarios[k].impact_level.value}")
        for k in sorted(self._results):
            parts.append(f"result:{k}:{self._results[k].adoption_readiness.value}")
        for k in sorted(self._diffs):
            parts.append(f"diff:{k}:{self._diffs[k].disposition.value}")
        for k in sorted(self._impacts):
            parts.append(f"impact:{k}:{self._impacts[k].impact_level.value}")
        for k in sorted(self._violations):
            parts.append(f"violation:{k}")
        return sha256("|".join(parts).encode()).hexdigest()
