"""Purpose: process / physics simulation runtime engine.
Governance scope: managing process models, physical parameters, simulation
    scenarios, runs, results, constraint envelopes, violations, assessments,
    snapshots, and closure reports.
Dependencies: process_simulation_runtime contracts, event_spine, core invariants.
Invariants:
  - COMPLETED/FAILED/CANCELLED runs are terminal.
  - Duplicate IDs raise RuntimeCoreInvariantError.
  - Every mutation emits an event.
  - All returns are immutable.
  - Clock is injected for deterministic timestamps.
"""

from __future__ import annotations

from hashlib import sha256
from typing import Any

from mcoi_runtime.core.engine_protocol import Clock, WallClock

from ..contracts.process_simulation_runtime import (
    ConstraintEnvelope,
    PhysicalConstraintStatus,
    PhysicalParameter,
    ProcessAssessment,
    ProcessClosureReport,
    ProcessModel,
    ProcessModelKind,
    ProcessSimulationStatus,
    ProcessSnapshot,
    ProcessViolation,
    SimulationDisposition,
    SimulationOutcomeKind,
    SimulationResult,
    SimulationRun,
    SimulationScenario,
)
from ..contracts.event import EventRecord, EventSource, EventType
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier


_RUN_TERMINAL = frozenset({
    ProcessSimulationStatus.COMPLETED,
    ProcessSimulationStatus.FAILED,
    ProcessSimulationStatus.CANCELLED,
})


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str, now: str) -> EventRecord:
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-pcsim", {"action": action, "seq": str(es.event_count), "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class ProcessSimulationRuntimeEngine:
    """Engine for governed process / physics simulation runtime."""

    def __init__(self, event_spine: EventSpineEngine, *, clock: Any = None) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._clock: Clock = clock if isinstance(clock, Clock) else WallClock()
        self._models: dict[str, ProcessModel] = {}
        self._parameters: dict[str, PhysicalParameter] = {}
        self._scenarios: dict[str, SimulationScenario] = {}
        self._runs: dict[str, SimulationRun] = {}
        self._results: dict[str, SimulationResult] = {}
        self._envelopes: dict[str, ConstraintEnvelope] = {}
        self._violations: dict[str, ProcessViolation] = {}

    # ------------------------------------------------------------------
    # Clock
    # ------------------------------------------------------------------

    def _now(self) -> str:
        return self._clock.now_iso()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def model_count(self) -> int:
        return len(self._models)

    @property
    def parameter_count(self) -> int:
        return len(self._parameters)

    @property
    def scenario_count(self) -> int:
        return len(self._scenarios)

    @property
    def run_count(self) -> int:
        return len(self._runs)

    @property
    def result_count(self) -> int:
        return len(self._results)

    @property
    def envelope_count(self) -> int:
        return len(self._envelopes)

    @property
    def violation_count(self) -> int:
        return len(self._violations)

    # ------------------------------------------------------------------
    # Process Models
    # ------------------------------------------------------------------

    def register_process_model(
        self,
        model_id: str,
        tenant_id: str,
        display_name: str,
        kind: ProcessModelKind,
        parameter_count: int = 0,
    ) -> ProcessModel:
        """Register a new process model. Duplicate model_id raises."""
        if model_id in self._models:
            raise RuntimeCoreInvariantError(f"Duplicate model_id: {model_id}")
        now = self._now()
        model = ProcessModel(
            model_id=model_id,
            tenant_id=tenant_id,
            display_name=display_name,
            kind=kind,
            parameter_count=parameter_count,
            created_at=now,
        )
        self._models[model_id] = model
        _emit(self._events, "process_model_registered", {
            "model_id": model_id, "kind": kind.value,
        }, model_id, self._now())
        return model

    def get_model(self, model_id: str) -> ProcessModel:
        m = self._models.get(model_id)
        if m is None:
            raise RuntimeCoreInvariantError(f"Unknown model_id: {model_id}")
        return m

    def _replace_model(self, model_id: str, **kwargs: Any) -> ProcessModel:
        old = self.get_model(model_id)
        fields = {
            "model_id": old.model_id,
            "tenant_id": old.tenant_id,
            "display_name": old.display_name,
            "kind": old.kind,
            "parameter_count": old.parameter_count,
            "created_at": old.created_at,
            "metadata": old.metadata,
        }
        fields.update(kwargs)
        updated = ProcessModel(**fields)
        self._models[model_id] = updated
        return updated

    # ------------------------------------------------------------------
    # Physical Parameters
    # ------------------------------------------------------------------

    def register_physical_parameter(
        self,
        parameter_id: str,
        tenant_id: str,
        model_ref: str,
        name: str,
        value: float,
        unit: str,
    ) -> PhysicalParameter:
        """Register a physical parameter. Validates model exists and increments parameter_count."""
        if parameter_id in self._parameters:
            raise RuntimeCoreInvariantError(f"Duplicate parameter_id: {parameter_id}")
        model = self.get_model(model_ref)
        now = self._now()
        param = PhysicalParameter(
            parameter_id=parameter_id,
            tenant_id=tenant_id,
            model_ref=model_ref,
            name=name,
            value=value,
            unit=unit,
            created_at=now,
        )
        self._parameters[parameter_id] = param
        # Increment model parameter count
        self._replace_model(model_ref, parameter_count=model.parameter_count + 1)
        _emit(self._events, "physical_parameter_registered", {
            "parameter_id": parameter_id, "model_ref": model_ref,
        }, parameter_id, self._now())
        return param

    def get_parameter(self, parameter_id: str) -> PhysicalParameter:
        p = self._parameters.get(parameter_id)
        if p is None:
            raise RuntimeCoreInvariantError(f"Unknown parameter_id: {parameter_id}")
        return p

    # ------------------------------------------------------------------
    # Constraint Envelopes
    # ------------------------------------------------------------------

    def _compute_envelope_status(
        self, min_value: float, max_value: float, target_value: float,
    ) -> PhysicalConstraintStatus:
        """Auto-compute constraint status from envelope bounds and target."""
        span = max_value - min_value
        if span == 0:
            # Degenerate envelope
            if target_value == min_value:
                return PhysicalConstraintStatus.WITHIN_ENVELOPE
            return PhysicalConstraintStatus.CRITICAL

        # Check if target is way outside (>50% of span beyond boundary)
        threshold_50 = span * 0.5
        if target_value < min_value - threshold_50 or target_value > max_value + threshold_50:
            return PhysicalConstraintStatus.CRITICAL
        # Check if target is outside envelope
        if target_value < min_value or target_value > max_value:
            return PhysicalConstraintStatus.BREACH
        # Check if target is near boundary (within 10% of span)
        threshold_10 = span * 0.1
        if (target_value - min_value) < threshold_10 or (max_value - target_value) < threshold_10:
            return PhysicalConstraintStatus.WARNING
        return PhysicalConstraintStatus.WITHIN_ENVELOPE

    def register_constraint_envelope(
        self,
        envelope_id: str,
        tenant_id: str,
        parameter_ref: str,
        min_value: float,
        max_value: float,
        target_value: float,
    ) -> ConstraintEnvelope:
        """Register a constraint envelope. Auto-computes status."""
        if envelope_id in self._envelopes:
            raise RuntimeCoreInvariantError(f"Duplicate envelope_id: {envelope_id}")
        self.get_parameter(parameter_ref)  # validates existence
        now = self._now()
        status = self._compute_envelope_status(min_value, max_value, target_value)
        envelope = ConstraintEnvelope(
            envelope_id=envelope_id,
            tenant_id=tenant_id,
            parameter_ref=parameter_ref,
            min_value=min_value,
            max_value=max_value,
            target_value=target_value,
            status=status,
            created_at=now,
        )
        self._envelopes[envelope_id] = envelope
        _emit(self._events, "constraint_envelope_registered", {
            "envelope_id": envelope_id, "status": status.value,
        }, envelope_id, self._now())
        return envelope

    # ------------------------------------------------------------------
    # Simulation Scenarios
    # ------------------------------------------------------------------

    def register_simulation_scenario(
        self,
        scenario_id: str,
        tenant_id: str,
        model_ref: str,
        disposition: SimulationDisposition = SimulationDisposition.NOMINAL,
        description: str = "",
    ) -> SimulationScenario:
        """Register a simulation scenario. Validates model exists."""
        if scenario_id in self._scenarios:
            raise RuntimeCoreInvariantError(f"Duplicate scenario_id: {scenario_id}")
        self.get_model(model_ref)
        now = self._now()
        scenario = SimulationScenario(
            scenario_id=scenario_id,
            tenant_id=tenant_id,
            model_ref=model_ref,
            disposition=disposition,
            description=description or "no description",
            created_at=now,
        )
        self._scenarios[scenario_id] = scenario
        _emit(self._events, "simulation_scenario_registered", {
            "scenario_id": scenario_id, "disposition": disposition.value,
        }, scenario_id, self._now())
        return scenario

    def get_scenario(self, scenario_id: str) -> SimulationScenario:
        s = self._scenarios.get(scenario_id)
        if s is None:
            raise RuntimeCoreInvariantError(f"Unknown scenario_id: {scenario_id}")
        return s

    # ------------------------------------------------------------------
    # Simulation Runs
    # ------------------------------------------------------------------

    def run_simulation(
        self,
        run_id: str,
        tenant_id: str,
        scenario_ref: str,
    ) -> SimulationRun:
        """Start a simulation run. Status = RUNNING, duration_ms = 0.0."""
        if run_id in self._runs:
            raise RuntimeCoreInvariantError(f"Duplicate run_id: {run_id}")
        self.get_scenario(scenario_ref)
        now = self._now()
        run = SimulationRun(
            run_id=run_id,
            tenant_id=tenant_id,
            scenario_ref=scenario_ref,
            status=ProcessSimulationStatus.RUNNING,
            duration_ms=0.0,
            created_at=now,
        )
        self._runs[run_id] = run
        _emit(self._events, "simulation_run_started", {
            "run_id": run_id, "scenario_ref": scenario_ref,
        }, run_id, self._now())
        return run

    def get_run(self, run_id: str) -> SimulationRun:
        r = self._runs.get(run_id)
        if r is None:
            raise RuntimeCoreInvariantError(f"Unknown run_id: {run_id}")
        return r

    def _replace_run(self, run_id: str, **kwargs: Any) -> SimulationRun:
        old = self.get_run(run_id)
        fields = {
            "run_id": old.run_id,
            "tenant_id": old.tenant_id,
            "scenario_ref": old.scenario_ref,
            "status": old.status,
            "duration_ms": old.duration_ms,
            "created_at": old.created_at,
            "metadata": old.metadata,
        }
        fields.update(kwargs)
        updated = SimulationRun(**fields)
        self._runs[run_id] = updated
        return updated

    def complete_simulation(self, run_id: str, duration_ms: float) -> SimulationRun:
        """Complete a running simulation. Terminal guard."""
        old = self.get_run(run_id)
        if old.status in _RUN_TERMINAL:
            raise RuntimeCoreInvariantError(
                f"Run {run_id} is in terminal state {old.status.value}"
            )
        updated = self._replace_run(
            run_id,
            status=ProcessSimulationStatus.COMPLETED,
            duration_ms=duration_ms,
        )
        _emit(self._events, "simulation_run_completed", {
            "run_id": run_id, "duration_ms": duration_ms,
        }, run_id, self._now())
        return updated

    def fail_simulation(self, run_id: str) -> SimulationRun:
        """Fail a running simulation. Terminal guard."""
        old = self.get_run(run_id)
        if old.status in _RUN_TERMINAL:
            raise RuntimeCoreInvariantError(
                f"Run {run_id} is in terminal state {old.status.value}"
            )
        updated = self._replace_run(
            run_id,
            status=ProcessSimulationStatus.FAILED,
        )
        _emit(self._events, "simulation_run_failed", {
            "run_id": run_id,
        }, run_id, self._now())
        return updated

    # ------------------------------------------------------------------
    # Simulation Results
    # ------------------------------------------------------------------

    def record_simulation_result(
        self,
        result_id: str,
        tenant_id: str,
        run_ref: str,
        outcome: SimulationOutcomeKind,
        expected_value: float,
        actual_value: float,
    ) -> SimulationResult:
        """Record a simulation result. Auto-computes deviation = actual - expected."""
        if result_id in self._results:
            raise RuntimeCoreInvariantError(f"Duplicate result_id: {result_id}")
        self.get_run(run_ref)
        now = self._now()
        deviation = actual_value - expected_value
        result = SimulationResult(
            result_id=result_id,
            tenant_id=tenant_id,
            run_ref=run_ref,
            outcome=outcome,
            expected_value=expected_value,
            actual_value=actual_value,
            deviation=deviation,
            created_at=now,
        )
        self._results[result_id] = result
        _emit(self._events, "simulation_result_recorded", {
            "result_id": result_id, "outcome": outcome.value, "deviation": deviation,
        }, result_id, self._now())
        return result

    # ------------------------------------------------------------------
    # Compare Actual to Model
    # ------------------------------------------------------------------

    def compare_actual_to_model(
        self,
        parameter_id: str,
        actual_value: float,
    ) -> PhysicalConstraintStatus:
        """Check actual_value against envelope for parameter. Returns status."""
        self.get_parameter(parameter_id)
        # Find envelope for this parameter
        envelope = None
        for env in self._envelopes.values():
            if env.parameter_ref == parameter_id:
                envelope = env
                break
        if envelope is None:
            raise RuntimeCoreInvariantError(f"No envelope for parameter_id: {parameter_id}")

        span = envelope.max_value - envelope.min_value
        if span == 0:
            if actual_value == envelope.min_value:
                return PhysicalConstraintStatus.WITHIN_ENVELOPE
            return PhysicalConstraintStatus.CRITICAL

        threshold_50 = span * 0.5
        if actual_value < envelope.min_value - threshold_50 or actual_value > envelope.max_value + threshold_50:
            return PhysicalConstraintStatus.CRITICAL
        if actual_value < envelope.min_value or actual_value > envelope.max_value:
            return PhysicalConstraintStatus.BREACH
        threshold_10 = span * 0.1
        if (actual_value - envelope.min_value) < threshold_10 or (envelope.max_value - actual_value) < threshold_10:
            return PhysicalConstraintStatus.WARNING
        return PhysicalConstraintStatus.WITHIN_ENVELOPE

    # ------------------------------------------------------------------
    # Assessment
    # ------------------------------------------------------------------

    def assess_process_state(
        self,
        assessment_id: str,
        tenant_id: str,
    ) -> ProcessAssessment:
        """Assess process simulation state. safety_score = passes / (passes + fails) or 1.0."""
        now = self._now()
        tenant_models = [m for m in self._models.values() if m.tenant_id == tenant_id]
        tenant_runs = [r for r in self._runs.values() if r.tenant_id == tenant_id]
        tenant_results = [r for r in self._results.values() if r.tenant_id == tenant_id]
        tenant_violations = [v for v in self._violations.values() if v.tenant_id == tenant_id]

        passes = sum(
            1 for r in tenant_results
            if r.outcome in (SimulationOutcomeKind.PASS, SimulationOutcomeKind.MARGINAL)
        )
        fails = sum(
            1 for r in tenant_results
            if r.outcome in (SimulationOutcomeKind.FAIL, SimulationOutcomeKind.UNSAFE)
        )
        total = passes + fails
        safety_score = passes / total if total > 0 else 1.0

        asm = ProcessAssessment(
            assessment_id=assessment_id,
            tenant_id=tenant_id,
            total_models=len(tenant_models),
            total_runs=len(tenant_runs),
            total_violations=len(tenant_violations),
            safety_score=safety_score,
            assessed_at=now,
        )
        _emit(self._events, "process_assessed", {
            "assessment_id": assessment_id, "safety_score": safety_score,
        }, assessment_id, self._now())
        return asm

    # ------------------------------------------------------------------
    # Failure Mode Simulation
    # ------------------------------------------------------------------

    def simulate_failure_mode(
        self,
        scenario_id: str,
        tenant_id: str,
        model_ref: str,
    ) -> SimulationScenario:
        """Register a FAILURE disposition scenario."""
        return self.register_simulation_scenario(
            scenario_id=scenario_id,
            tenant_id=tenant_id,
            model_ref=model_ref,
            disposition=SimulationDisposition.FAILURE,
            description="failure mode simulation",
        )

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------

    def process_snapshot(
        self,
        snapshot_id: str,
        tenant_id: str,
    ) -> ProcessSnapshot:
        """Produce a point-in-time snapshot for a tenant."""
        now = self._now()
        snap = ProcessSnapshot(
            snapshot_id=snapshot_id,
            tenant_id=tenant_id,
            total_models=sum(1 for m in self._models.values() if m.tenant_id == tenant_id),
            total_parameters=sum(1 for p in self._parameters.values() if p.tenant_id == tenant_id),
            total_scenarios=sum(1 for s in self._scenarios.values() if s.tenant_id == tenant_id),
            total_runs=sum(1 for r in self._runs.values() if r.tenant_id == tenant_id),
            total_envelopes=sum(1 for e in self._envelopes.values() if e.tenant_id == tenant_id),
            total_violations=sum(1 for v in self._violations.values() if v.tenant_id == tenant_id),
            captured_at=now,
        )
        return snap

    # ------------------------------------------------------------------
    # Closure Report
    # ------------------------------------------------------------------

    def process_closure_report(
        self,
        report_id: str,
        tenant_id: str,
    ) -> ProcessClosureReport:
        """Produce a closure report for a tenant."""
        now = self._now()
        report = ProcessClosureReport(
            report_id=report_id,
            tenant_id=tenant_id,
            total_models=sum(1 for m in self._models.values() if m.tenant_id == tenant_id),
            total_runs=sum(1 for r in self._runs.values() if r.tenant_id == tenant_id),
            total_results=sum(1 for r in self._results.values() if r.tenant_id == tenant_id),
            total_violations=sum(1 for v in self._violations.values() if v.tenant_id == tenant_id),
            created_at=now,
        )
        _emit(self._events, "process_closure_report", {
            "report_id": report_id,
        }, report_id, self._now())
        return report

    # ------------------------------------------------------------------
    # Violation Detection
    # ------------------------------------------------------------------

    def detect_process_violations(self, tenant_id: str) -> tuple[ProcessViolation, ...]:
        """Detect process violations for a tenant. Idempotent."""
        now = self._now()
        new_violations: list[ProcessViolation] = []

        # 1) envelope_breach: parameter value outside its envelope
        for env in self._envelopes.values():
            if env.tenant_id != tenant_id:
                continue
            param = self._parameters.get(env.parameter_ref)
            if param is None:
                continue
            if param.value < env.min_value or param.value > env.max_value:
                vid = stable_identifier("viol-pcsim", {
                    "envelope": env.envelope_id, "op": "envelope_breach",
                })
                if vid not in self._violations:
                    v = ProcessViolation(
                        violation_id=vid,
                        tenant_id=tenant_id,
                        operation="envelope_breach",
                        reason=f"Parameter {env.parameter_ref} value {param.value} outside envelope [{env.min_value}, {env.max_value}]",
                        detected_at=now,
                    )
                    self._violations[vid] = v
                    new_violations.append(v)

        # 2) failed_run_no_result: FAILED run with no result recorded
        tenant_runs = [r for r in self._runs.values() if r.tenant_id == tenant_id]
        for run in tenant_runs:
            if run.status == ProcessSimulationStatus.FAILED:
                has_result = any(
                    r.run_ref == run.run_id for r in self._results.values()
                )
                if not has_result:
                    vid = stable_identifier("viol-pcsim", {
                        "run": run.run_id, "op": "failed_run_no_result",
                    })
                    if vid not in self._violations:
                        v = ProcessViolation(
                            violation_id=vid,
                            tenant_id=tenant_id,
                            operation="failed_run_no_result",
                            reason=f"Run {run.run_id} FAILED with no result recorded",
                            detected_at=now,
                        )
                        self._violations[vid] = v
                        new_violations.append(v)

        # 3) unsafe_outcome: result with UNSAFE outcome
        tenant_results = [r for r in self._results.values() if r.tenant_id == tenant_id]
        for result in tenant_results:
            if result.outcome == SimulationOutcomeKind.UNSAFE:
                vid = stable_identifier("viol-pcsim", {
                    "result": result.result_id, "op": "unsafe_outcome",
                })
                if vid not in self._violations:
                    v = ProcessViolation(
                        violation_id=vid,
                        tenant_id=tenant_id,
                        operation="unsafe_outcome",
                        reason=f"Result {result.result_id} has UNSAFE outcome",
                        detected_at=now,
                    )
                    self._violations[vid] = v
                    new_violations.append(v)

        return tuple(new_violations)

    # ------------------------------------------------------------------
    # Collections / snapshot / state_hash
    # ------------------------------------------------------------------

    def _collections(self) -> dict[str, Any]:
        """Return all internal collections."""
        return {
            "envelopes": self._envelopes,
            "models": self._models,
            "parameters": self._parameters,
            "results": self._results,
            "runs": self._runs,
            "scenarios": self._scenarios,
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
            f"envelopes={self.envelope_count}",
            f"models={self.model_count}",
            f"parameters={self.parameter_count}",
            f"results={self.result_count}",
            f"runs={self.run_count}",
            f"scenarios={self.scenario_count}",
            f"violations={self.violation_count}",
        ]
        return sha256("|".join(parts).encode()).hexdigest()
