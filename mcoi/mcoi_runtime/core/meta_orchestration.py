"""Purpose: meta-orchestration / cross-runtime composition engine.
Governance scope: registering plans, composing steps across runtimes,
    managing dependencies, coordinating execution, tracking traces,
    detecting violations, producing snapshots.
Dependencies: meta_orchestration contracts, event_spine, core invariants.
Invariants:
  - Duplicate IDs raise.
  - Steps execute in dependency order.
  - Failed dependencies block downstream steps.
  - Every mutation emits an event.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from mcoi_runtime.core.engine_protocol import Clock, WallClock

from ..contracts.meta_orchestration import (
    CompositionAssessment,
    CompositionScope,
    CoordinationMode,
    DependencyDisposition,
    ExecutionTrace,
    OrchestrationClosureReport,
    OrchestrationDecision,
    OrchestrationDecisionStatus,
    OrchestrationPlan,
    OrchestrationSnapshot,
    OrchestrationStatus,
    OrchestrationStep,
    OrchestrationStepKind,
    OrchestrationViolation,
    RuntimeBinding,
    StepDependency,
)
from ..contracts.event import EventRecord, EventSource, EventType
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str, now: str = "") -> EventRecord:
    if not now:
        now = datetime.now(timezone.utc).isoformat()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-orch", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


_PLAN_TERMINAL = frozenset({OrchestrationStatus.COMPLETED, OrchestrationStatus.FAILED, OrchestrationStatus.CANCELLED})
_STEP_TERMINAL = frozenset({OrchestrationStatus.COMPLETED, OrchestrationStatus.FAILED, OrchestrationStatus.CANCELLED})


class MetaOrchestrationEngine:
    """Meta-orchestration / cross-runtime composition engine."""

    def __init__(self, event_spine: EventSpineEngine, *, clock: Any = None) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._clock: Clock = clock if isinstance(clock, Clock) else WallClock()
        self._plans: dict[str, OrchestrationPlan] = {}
        self._steps: dict[str, OrchestrationStep] = {}
        self._dependencies: dict[str, StepDependency] = {}
        self._bindings: dict[str, RuntimeBinding] = {}
        self._decisions: dict[str, OrchestrationDecision] = {}
        self._traces: dict[str, ExecutionTrace] = {}
        self._violations: dict[str, OrchestrationViolation] = {}
        self._assessments: dict[str, CompositionAssessment] = {}

    def _now(self) -> str:
        """Get current time from injected clock."""
        return self._clock.now_iso()

    # -- Properties ----------------------------------------------------------

    @property
    def plan_count(self) -> int:
        return len(self._plans)

    @property
    def step_count(self) -> int:
        return len(self._steps)

    @property
    def dependency_count(self) -> int:
        return len(self._dependencies)

    @property
    def binding_count(self) -> int:
        return len(self._bindings)

    @property
    def decision_count(self) -> int:
        return len(self._decisions)

    @property
    def trace_count(self) -> int:
        return len(self._traces)

    @property
    def violation_count(self) -> int:
        return len(self._violations)

    @property
    def assessment_count(self) -> int:
        return len(self._assessments)

    # -- Plans ---------------------------------------------------------------

    def register_plan(
        self,
        plan_id: str,
        tenant_id: str,
        display_name: str,
        coordination_mode: CoordinationMode = CoordinationMode.SEQUENTIAL,
        scope: CompositionScope = CompositionScope.TENANT,
    ) -> OrchestrationPlan:
        if plan_id in self._plans:
            raise RuntimeCoreInvariantError("duplicate plan_id")
        now = self._now()
        plan = OrchestrationPlan(
            plan_id=plan_id,
            tenant_id=tenant_id,
            display_name=display_name,
            status=OrchestrationStatus.DRAFT,
            coordination_mode=coordination_mode,
            scope=scope,
            step_count=0,
            completed_steps=0,
            failed_steps=0,
            created_at=now,
        )
        self._plans[plan_id] = plan
        _emit(self._events, "register_plan", {"plan_id": plan_id, "tenant_id": tenant_id}, plan_id, now=self._now())
        return plan

    def get_plan(self, plan_id: str) -> OrchestrationPlan:
        if plan_id not in self._plans:
            raise RuntimeCoreInvariantError("unknown plan_id")
        return self._plans[plan_id]

    def plans_for_tenant(self, tenant_id: str) -> tuple[OrchestrationPlan, ...]:
        return tuple(p for p in self._plans.values() if p.tenant_id == tenant_id)

    def _update_plan(self, plan_id: str, **overrides: Any) -> OrchestrationPlan:
        old = self.get_plan(plan_id)
        fields = {
            "plan_id": old.plan_id,
            "tenant_id": old.tenant_id,
            "display_name": old.display_name,
            "status": old.status,
            "coordination_mode": old.coordination_mode,
            "scope": old.scope,
            "step_count": old.step_count,
            "completed_steps": old.completed_steps,
            "failed_steps": old.failed_steps,
            "created_at": old.created_at,
        }
        fields.update(overrides)
        updated = OrchestrationPlan(**fields)
        self._plans[plan_id] = updated
        return updated

    # -- Steps ---------------------------------------------------------------

    def register_step(
        self,
        step_id: str,
        plan_id: str,
        tenant_id: str,
        display_name: str,
        kind: OrchestrationStepKind = OrchestrationStepKind.INVOKE,
        target_runtime: str = "unknown",
        target_action: str = "unknown",
        sequence_order: int = 0,
    ) -> OrchestrationStep:
        if step_id in self._steps:
            raise RuntimeCoreInvariantError("duplicate step_id")
        if plan_id not in self._plans:
            raise RuntimeCoreInvariantError("unknown plan_id")
        plan = self._plans[plan_id]
        if plan.status in _PLAN_TERMINAL:
            raise RuntimeCoreInvariantError("plan is in terminal state")
        now = self._now()
        step = OrchestrationStep(
            step_id=step_id,
            plan_id=plan_id,
            tenant_id=tenant_id,
            display_name=display_name,
            kind=kind,
            target_runtime=target_runtime,
            target_action=target_action,
            status=OrchestrationStatus.DRAFT,
            sequence_order=sequence_order,
            created_at=now,
        )
        self._steps[step_id] = step
        self._update_plan(plan_id, step_count=plan.step_count + 1)
        _emit(self._events, "register_step", {"step_id": step_id, "plan_id": plan_id}, step_id, now=self._now())
        return step

    def get_step(self, step_id: str) -> OrchestrationStep:
        if step_id not in self._steps:
            raise RuntimeCoreInvariantError("unknown step_id")
        return self._steps[step_id]

    def steps_for_plan(self, plan_id: str) -> tuple[OrchestrationStep, ...]:
        steps = [s for s in self._steps.values() if s.plan_id == plan_id]
        steps.sort(key=lambda s: s.sequence_order)
        return tuple(steps)

    def _update_step(self, step_id: str, **overrides: Any) -> OrchestrationStep:
        old = self.get_step(step_id)
        fields = {
            "step_id": old.step_id,
            "plan_id": old.plan_id,
            "tenant_id": old.tenant_id,
            "display_name": old.display_name,
            "kind": old.kind,
            "target_runtime": old.target_runtime,
            "target_action": old.target_action,
            "status": old.status,
            "sequence_order": old.sequence_order,
            "created_at": old.created_at,
        }
        fields.update(overrides)
        updated = OrchestrationStep(**fields)
        self._steps[step_id] = updated
        return updated

    # -- Dependencies --------------------------------------------------------

    def add_dependency(
        self,
        dependency_id: str,
        plan_id: str,
        tenant_id: str,
        from_step_id: str,
        to_step_id: str,
    ) -> StepDependency:
        if dependency_id in self._dependencies:
            raise RuntimeCoreInvariantError("duplicate dependency_id")
        if plan_id not in self._plans:
            raise RuntimeCoreInvariantError("unknown plan_id")
        if from_step_id not in self._steps:
            raise RuntimeCoreInvariantError("unknown from_step_id")
        if to_step_id not in self._steps:
            raise RuntimeCoreInvariantError("unknown to_step_id")
        now = self._now()
        dep = StepDependency(
            dependency_id=dependency_id,
            plan_id=plan_id,
            tenant_id=tenant_id,
            from_step_id=from_step_id,
            to_step_id=to_step_id,
            disposition=DependencyDisposition.BLOCKED,
            created_at=now,
        )
        self._dependencies[dependency_id] = dep
        _emit(self._events, "add_dependency", {"dependency_id": dependency_id, "from": from_step_id, "to": to_step_id}, dependency_id, now=self._now())
        return dep

    def dependencies_for_step(self, step_id: str) -> tuple[StepDependency, ...]:
        return tuple(d for d in self._dependencies.values() if d.to_step_id == step_id)

    def evaluate_dependencies(self, step_id: str) -> tuple[StepDependency, ...]:
        """Evaluate all dependencies for a step, updating their dispositions."""
        deps = [d for d in self._dependencies.values() if d.to_step_id == step_id]
        results: list[StepDependency] = []
        for dep in deps:
            from_step = self._steps.get(dep.from_step_id)
            if from_step is None:
                new_disp = DependencyDisposition.FAILED
            elif from_step.status == OrchestrationStatus.COMPLETED:
                new_disp = DependencyDisposition.SATISFIED
            elif from_step.status == OrchestrationStatus.FAILED:
                new_disp = DependencyDisposition.FAILED
            elif from_step.status == OrchestrationStatus.CANCELLED:
                new_disp = DependencyDisposition.SKIPPED
            else:
                new_disp = DependencyDisposition.BLOCKED
            updated = StepDependency(
                dependency_id=dep.dependency_id,
                plan_id=dep.plan_id,
                tenant_id=dep.tenant_id,
                from_step_id=dep.from_step_id,
                to_step_id=dep.to_step_id,
                disposition=new_disp,
                created_at=dep.created_at,
            )
            self._dependencies[dep.dependency_id] = updated
            results.append(updated)
        if results:
            _emit(self._events, "evaluate_dependencies", {"step_id": step_id, "count": len(results)}, step_id, now=self._now())
        return tuple(results)

    # -- Runtime bindings ----------------------------------------------------

    def bind_runtime(
        self,
        binding_id: str,
        step_id: str,
        tenant_id: str,
        runtime_name: str,
        action_name: str,
        config_ref: str = "default",
    ) -> RuntimeBinding:
        if binding_id in self._bindings:
            raise RuntimeCoreInvariantError("duplicate binding_id")
        if step_id not in self._steps:
            raise RuntimeCoreInvariantError("unknown step_id")
        now = self._now()
        binding = RuntimeBinding(
            binding_id=binding_id,
            step_id=step_id,
            tenant_id=tenant_id,
            runtime_name=runtime_name,
            action_name=action_name,
            config_ref=config_ref,
            created_at=now,
        )
        self._bindings[binding_id] = binding
        _emit(self._events, "bind_runtime", {"binding_id": binding_id, "step_id": step_id, "runtime": runtime_name}, binding_id, now=self._now())
        return binding

    def bindings_for_step(self, step_id: str) -> tuple[RuntimeBinding, ...]:
        return tuple(b for b in self._bindings.values() if b.step_id == step_id)

    # -- Execution -----------------------------------------------------------

    def start_execution(self, plan_id: str) -> OrchestrationPlan:
        plan = self.get_plan(plan_id)
        if plan.status in _PLAN_TERMINAL:
            raise RuntimeCoreInvariantError("plan is in terminal state")
        if plan.step_count == 0:
            raise RuntimeCoreInvariantError("plan has no steps")
        updated = self._update_plan(plan_id, status=OrchestrationStatus.IN_PROGRESS)
        # Mark first steps (no dependencies or all deps satisfied) as READY
        # Skip steps already in terminal state
        for step in self.steps_for_plan(plan_id):
            if step.status in _STEP_TERMINAL:
                continue
            deps = self.dependencies_for_step(step.step_id)
            if not deps:
                self._update_step(step.step_id, status=OrchestrationStatus.READY)
        _emit(self._events, "start_execution", {"plan_id": plan_id}, plan_id, now=self._now())
        return updated

    def advance_execution(self, plan_id: str) -> OrchestrationPlan:
        """Advance plan execution: evaluate deps, ready next steps, check completion."""
        plan = self.get_plan(plan_id)
        if plan.status != OrchestrationStatus.IN_PROGRESS:
            raise RuntimeCoreInvariantError("plan is not IN_PROGRESS")

        steps = self.steps_for_plan(plan_id)
        # Evaluate dependencies and ready blocked steps
        for step in steps:
            if step.status in (OrchestrationStatus.DRAFT, OrchestrationStatus.READY):
                deps = self.evaluate_dependencies(step.step_id)
                if deps:
                    all_satisfied = all(d.disposition == DependencyDisposition.SATISFIED for d in deps)
                    any_failed = any(d.disposition == DependencyDisposition.FAILED for d in deps)
                    if any_failed:
                        self._update_step(step.step_id, status=OrchestrationStatus.FAILED)
                        self._update_plan(plan_id, failed_steps=self.get_plan(plan_id).failed_steps + 1)
                    elif all_satisfied and step.status == OrchestrationStatus.DRAFT:
                        self._update_step(step.step_id, status=OrchestrationStatus.READY)

        # Check if plan is complete
        plan = self.get_plan(plan_id)
        steps = self.steps_for_plan(plan_id)
        all_terminal = all(s.status in _STEP_TERMINAL for s in steps)
        if all_terminal and steps:
            any_failed = any(s.status == OrchestrationStatus.FAILED for s in steps)
            if any_failed:
                self._update_plan(plan_id, status=OrchestrationStatus.FAILED)
            else:
                self._update_plan(plan_id, status=OrchestrationStatus.COMPLETED)

        _emit(self._events, "advance_execution", {"plan_id": plan_id}, plan_id, now=self._now())
        return self.get_plan(plan_id)

    def record_step_result(
        self,
        trace_id: str,
        plan_id: str,
        step_id: str,
        tenant_id: str,
        success: bool,
        duration_ms: float = 0.0,
    ) -> ExecutionTrace:
        if trace_id in self._traces:
            raise RuntimeCoreInvariantError("duplicate trace_id")
        step = self.get_step(step_id)
        if step.status in _STEP_TERMINAL:
            raise RuntimeCoreInvariantError("step is in terminal state")

        new_status = OrchestrationStatus.COMPLETED if success else OrchestrationStatus.FAILED
        self._update_step(step_id, status=new_status)

        # Update plan counters
        plan = self.get_plan(plan_id)
        if success:
            self._update_plan(plan_id, completed_steps=plan.completed_steps + 1)
        else:
            self._update_plan(plan_id, failed_steps=plan.failed_steps + 1)

        now = self._now()
        binding = None
        for b in self._bindings.values():
            if b.step_id == step_id:
                binding = b
                break

        trace = ExecutionTrace(
            trace_id=trace_id,
            plan_id=plan_id,
            step_id=step_id,
            tenant_id=tenant_id,
            runtime_name=binding.runtime_name if binding else step.target_runtime,
            action_name=binding.action_name if binding else step.target_action,
            status=new_status,
            duration_ms=duration_ms,
            created_at=now,
        )
        self._traces[trace_id] = trace
        _emit(self._events, "record_step_result", {"trace_id": trace_id, "step_id": step_id, "success": success}, trace_id, now=self._now())
        return trace

    def traces_for_plan(self, plan_id: str) -> tuple[ExecutionTrace, ...]:
        return tuple(t for t in self._traces.values() if t.plan_id == plan_id)

    # -- Decisions -----------------------------------------------------------

    def record_decision(
        self,
        decision_id: str,
        plan_id: str,
        step_id: str,
        tenant_id: str,
        status: OrchestrationDecisionStatus = OrchestrationDecisionStatus.APPROVED,
        reason: str = "auto-approved",
    ) -> OrchestrationDecision:
        if decision_id in self._decisions:
            raise RuntimeCoreInvariantError("duplicate decision_id")
        now = self._now()
        decision = OrchestrationDecision(
            decision_id=decision_id,
            plan_id=plan_id,
            step_id=step_id,
            tenant_id=tenant_id,
            status=status,
            reason=reason,
            decided_at=now,
        )
        self._decisions[decision_id] = decision

        # If denied, fail the step
        if status == OrchestrationDecisionStatus.DENIED:
            step = self.get_step(step_id)
            if step.status not in _STEP_TERMINAL:
                self._update_step(step_id, status=OrchestrationStatus.FAILED)
                plan = self.get_plan(plan_id)
                self._update_plan(plan_id, failed_steps=plan.failed_steps + 1)

        _emit(self._events, "record_decision", {"decision_id": decision_id, "status": status.value}, decision_id, now=self._now())
        return decision

    def decisions_for_plan(self, plan_id: str) -> tuple[OrchestrationDecision, ...]:
        return tuple(d for d in self._decisions.values() if d.plan_id == plan_id)

    # -- Cancel plan ---------------------------------------------------------

    def cancel_plan(self, plan_id: str) -> OrchestrationPlan:
        plan = self.get_plan(plan_id)
        if plan.status in _PLAN_TERMINAL:
            raise RuntimeCoreInvariantError("plan is in terminal state")
        # Cancel all non-terminal steps
        for step in self.steps_for_plan(plan_id):
            if step.status not in _STEP_TERMINAL:
                self._update_step(step.step_id, status=OrchestrationStatus.CANCELLED)
        updated = self._update_plan(plan_id, status=OrchestrationStatus.CANCELLED)
        _emit(self._events, "cancel_plan", {"plan_id": plan_id}, plan_id, now=self._now())
        return updated

    # -- Snapshots -----------------------------------------------------------

    def orchestration_snapshot(self, snapshot_id: str, tenant_id: str) -> OrchestrationSnapshot:
        now = self._now()
        plans = self.plans_for_tenant(tenant_id)
        active = [p for p in plans if p.status == OrchestrationStatus.IN_PROGRESS]
        steps = [s for s in self._steps.values() if s.tenant_id == tenant_id]
        completed = [s for s in steps if s.status == OrchestrationStatus.COMPLETED]
        failed = [s for s in steps if s.status == OrchestrationStatus.FAILED]
        traces = [t for t in self._traces.values() if t.tenant_id == tenant_id]
        violations = [v for v in self._violations.values() if v.tenant_id == tenant_id]

        snap = OrchestrationSnapshot(
            snapshot_id=snapshot_id,
            tenant_id=tenant_id,
            total_plans=len(plans),
            active_plans=len(active),
            total_steps=len(steps),
            completed_steps=len(completed),
            failed_steps=len(failed),
            total_traces=len(traces),
            total_violations=len(violations),
            captured_at=now,
        )
        _emit(self._events, "orchestration_snapshot", {"snapshot_id": snapshot_id}, snapshot_id, now=self._now())
        return snap

    # -- Assessment ----------------------------------------------------------

    def composition_assessment(self, assessment_id: str, tenant_id: str) -> CompositionAssessment:
        if assessment_id in self._assessments:
            raise RuntimeCoreInvariantError("duplicate assessment_id")
        now = self._now()
        plans = self.plans_for_tenant(tenant_id)
        active = [p for p in plans if p.status == OrchestrationStatus.IN_PROGRESS]
        completed = [p for p in plans if p.status == OrchestrationStatus.COMPLETED]
        failed = [p for p in plans if p.status == OrchestrationStatus.FAILED]
        violations = [v for v in self._violations.values() if v.tenant_id == tenant_id]

        total = len(plans)
        comp_rate = len(completed) / total if total > 0 else 1.0
        fail_rate = len(failed) / total if total > 0 else 0.0

        assessment = CompositionAssessment(
            assessment_id=assessment_id,
            tenant_id=tenant_id,
            total_plans=total,
            active_plans=len(active),
            completion_rate=round(min(1.0, max(0.0, comp_rate)), 4),
            failure_rate=round(min(1.0, max(0.0, fail_rate)), 4),
            total_violations=len(violations),
            assessed_at=now,
        )
        self._assessments[assessment_id] = assessment
        _emit(self._events, "composition_assessment", {"assessment_id": assessment_id}, assessment_id, now=self._now())
        return assessment

    # -- Violations ----------------------------------------------------------

    def detect_orchestration_violations(self, tenant_id: str) -> tuple[OrchestrationViolation, ...]:
        now = self._now()
        new_violations: list[OrchestrationViolation] = []

        for plan in self._plans.values():
            if plan.tenant_id != tenant_id:
                continue

            # Plan IN_PROGRESS with all steps failed
            if plan.status == OrchestrationStatus.IN_PROGRESS:
                steps = self.steps_for_plan(plan.plan_id)
                if steps and all(s.status == OrchestrationStatus.FAILED for s in steps):
                    vid = stable_identifier("viol-orch", {"op": "all_steps_failed", "plan_id": plan.plan_id})
                    if vid not in self._violations:
                        v = OrchestrationViolation(
                            violation_id=vid,
                            plan_id=plan.plan_id,
                            tenant_id=tenant_id,
                            operation="all_steps_failed",
                            reason="all steps in plan have failed",
                            detected_at=now,
                        )
                        self._violations[vid] = v
                        new_violations.append(v)

            # Plan with no steps
            if plan.status == OrchestrationStatus.DRAFT and plan.step_count == 0:
                vid = stable_identifier("viol-orch", {"op": "empty_plan", "plan_id": plan.plan_id})
                if vid not in self._violations:
                    v = OrchestrationViolation(
                        violation_id=vid,
                        plan_id=plan.plan_id,
                        tenant_id=tenant_id,
                        operation="empty_plan",
                        reason="plan has no steps",
                        detected_at=now,
                    )
                    self._violations[vid] = v
                    new_violations.append(v)

            # Steps with failed dependencies still in READY state
            if plan.status == OrchestrationStatus.IN_PROGRESS:
                for step in self.steps_for_plan(plan.plan_id):
                    if step.status == OrchestrationStatus.READY:
                        deps = self.dependencies_for_step(step.step_id)
                        if any(d.disposition == DependencyDisposition.FAILED for d in deps):
                            vid = stable_identifier("viol-orch", {"op": "blocked_by_failed_dep", "step_id": step.step_id})
                            if vid not in self._violations:
                                v = OrchestrationViolation(
                                    violation_id=vid,
                                    plan_id=plan.plan_id,
                                    tenant_id=tenant_id,
                                    operation="blocked_by_failed_dep",
                                    reason="step is READY but has failed dependencies",
                                    detected_at=now,
                                )
                                self._violations[vid] = v
                                new_violations.append(v)

        if new_violations:
            _emit(self._events, "detect_orchestration_violations", {"tenant_id": tenant_id, "count": len(new_violations)}, tenant_id, now=self._now())
        return tuple(new_violations)

    def violations_for_tenant(self, tenant_id: str) -> tuple[OrchestrationViolation, ...]:
        return tuple(v for v in self._violations.values() if v.tenant_id == tenant_id)

    # -- Closure report ------------------------------------------------------

    def closure_report(self, report_id: str, tenant_id: str) -> OrchestrationClosureReport:
        now = self._now()
        plans = self.plans_for_tenant(tenant_id)
        steps = [s for s in self._steps.values() if s.tenant_id == tenant_id]
        traces = [t for t in self._traces.values() if t.tenant_id == tenant_id]
        decisions = [d for d in self._decisions.values() if d.tenant_id == tenant_id]
        violations = self.violations_for_tenant(tenant_id)
        bindings = [b for b in self._bindings.values() if b.tenant_id == tenant_id]

        report = OrchestrationClosureReport(
            report_id=report_id,
            tenant_id=tenant_id,
            total_plans=len(plans),
            total_steps=len(steps),
            total_traces=len(traces),
            total_decisions=len(decisions),
            total_violations=len(violations),
            total_bindings=len(bindings),
            created_at=now,
        )
        _emit(self._events, "closure_report", {"report_id": report_id}, report_id, now=self._now())
        return report

    # -- State hash ----------------------------------------------------------

    def state_hash(self) -> str:
        parts: list[str] = []
        for k in sorted(self._plans):
            parts.append(f"plan:{k}:{self._plans[k].status.value}")
        for k in sorted(self._steps):
            parts.append(f"step:{k}:{self._steps[k].status.value}")
        for k in sorted(self._dependencies):
            parts.append(f"dep:{k}:{self._dependencies[k].disposition.value}")
        for k in sorted(self._bindings):
            parts.append(f"binding:{k}")
        for k in sorted(self._traces):
            parts.append(f"trace:{k}:{self._traces[k].status.value}")
        for k in sorted(self._decisions):
            parts.append(f"decision:{k}:{self._decisions[k].status.value}")
        for k in sorted(self._violations):
            parts.append(f"violation:{k}")
        return sha256("|".join(parts).encode()).hexdigest()

    # -- Snapshot / Restore --------------------------------------------------

    def _collections(self) -> dict[str, Any]:
        return {
            "plans": self._plans,
            "steps": self._steps,
            "dependencies": self._dependencies,
            "bindings": self._bindings,
            "decisions": self._decisions,
            "traces": self._traces,
            "violations": self._violations,
            "assessments": self._assessments,
        }

    def snapshot(self) -> dict[str, Any]:
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
