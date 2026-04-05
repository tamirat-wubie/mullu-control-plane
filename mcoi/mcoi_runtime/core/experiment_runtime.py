"""Purpose: scientific method / experimentation runtime engine.
Governance scope: managing experiment designs, variables, control groups,
    results, falsification, replication, decisions, assessments, snapshots,
    violations, and closure reports.
Dependencies: experiment_runtime contracts, event_spine, core invariants.
Invariants:
  - COMPLETED/FAILED experiments are terminal.
  - Duplicate IDs raise RuntimeCoreInvariantError.
  - Every mutation emits an event.
  - All returns are immutable.
  - Clock is injected for deterministic timestamps.
"""

from __future__ import annotations

from hashlib import sha256
from typing import Any

from mcoi_runtime.core.engine_protocol import Clock, WallClock

from ..contracts.experiment_runtime import (
    ControlGroup,
    ExperimentAssessment,
    ExperimentClosureReport,
    ExperimentDecision,
    ExperimentDesign,
    ExperimentPhase,
    ExperimentResult,
    ExperimentSnapshot,
    ExperimentVariable,
    FalsificationRecord,
    FalsificationStatus,
    ReplicationRecord,
    ReplicationStatus,
    ResultSignificance,
    VariableRole,
)
from ..contracts.event import EventRecord, EventSource, EventType
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier


_EXPERIMENT_TERMINAL = frozenset({ExperimentPhase.COMPLETED, ExperimentPhase.FAILED})


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str, now: str) -> EventRecord:
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-expt", {"action": action, "seq": str(es.event_count), "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class ExperimentRuntimeEngine:
    """Engine for governed scientific method / experimentation runtime."""

    def __init__(self, event_spine: EventSpineEngine, *, clock: Any = None) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._clock: Clock = clock if isinstance(clock, Clock) else WallClock()
        self._designs: dict[str, ExperimentDesign] = {}
        self._variables: dict[str, ExperimentVariable] = {}
        self._groups: dict[str, ControlGroup] = {}
        self._results: dict[str, ExperimentResult] = {}
        self._falsifications: dict[str, FalsificationRecord] = {}
        self._replications: dict[str, ReplicationRecord] = {}
        self._decisions: dict[str, ExperimentDecision] = {}
        self._violations: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Clock
    # ------------------------------------------------------------------

    def _now(self) -> str:
        return self._clock.now_iso()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def design_count(self) -> int:
        return len(self._designs)

    @property
    def variable_count(self) -> int:
        return len(self._variables)

    @property
    def group_count(self) -> int:
        return len(self._groups)

    @property
    def result_count(self) -> int:
        return len(self._results)

    @property
    def falsification_count(self) -> int:
        return len(self._falsifications)

    @property
    def replication_count(self) -> int:
        return len(self._replications)

    @property
    def violation_count(self) -> int:
        return len(self._violations)

    # ------------------------------------------------------------------
    # Experiment Designs
    # ------------------------------------------------------------------

    def register_design(
        self,
        design_id: str,
        tenant_id: str,
        hypothesis_ref: str,
        display_name: str,
    ) -> ExperimentDesign:
        """Register a new experiment design."""
        if design_id in self._designs:
            raise RuntimeCoreInvariantError("Duplicate design_id")
        now = self._now()
        design = ExperimentDesign(
            design_id=design_id,
            tenant_id=tenant_id,
            hypothesis_ref=hypothesis_ref,
            display_name=display_name,
            phase=ExperimentPhase.DESIGN,
            variable_count=0,
            created_at=now,
        )
        self._designs[design_id] = design
        _emit(self._events, "design_registered", {
            "design_id": design_id, "hypothesis_ref": hypothesis_ref,
        }, design_id, now)
        return design

    def get_design(self, design_id: str) -> ExperimentDesign:
        """Get a design by ID."""
        d = self._designs.get(design_id)
        if d is None:
            raise RuntimeCoreInvariantError("Unknown design_id")
        return d

    # ------------------------------------------------------------------
    # Variables
    # ------------------------------------------------------------------

    def add_variable(
        self,
        variable_id: str,
        tenant_id: str,
        design_ref: str,
        name: str,
        *,
        role: VariableRole = VariableRole.INDEPENDENT,
        unit: str = "unit",
    ) -> ExperimentVariable:
        """Add a variable to an experiment design."""
        if variable_id in self._variables:
            raise RuntimeCoreInvariantError("Duplicate variable_id")
        if design_ref not in self._designs:
            raise RuntimeCoreInvariantError("Unknown design_ref")
        design = self._designs[design_ref]
        if design.phase in _EXPERIMENT_TERMINAL:
            raise RuntimeCoreInvariantError("Cannot add variable to terminal experiment")
        now = self._now()
        var = ExperimentVariable(
            variable_id=variable_id,
            tenant_id=tenant_id,
            design_ref=design_ref,
            name=name,
            role=role,
            unit=unit,
            created_at=now,
        )
        self._variables[variable_id] = var
        # Update design variable_count
        new_count = sum(1 for v in self._variables.values() if v.design_ref == design_ref)
        updated = ExperimentDesign(
            design_id=design.design_id, tenant_id=design.tenant_id,
            hypothesis_ref=design.hypothesis_ref, display_name=design.display_name,
            phase=design.phase, variable_count=new_count,
            created_at=design.created_at, metadata=design.metadata,
        )
        self._designs[design_ref] = updated
        _emit(self._events, "variable_added", {
            "variable_id": variable_id, "design_ref": design_ref, "role": role.value,
        }, variable_id, now)
        return var

    # ------------------------------------------------------------------
    # Control Groups
    # ------------------------------------------------------------------

    def add_control_group(
        self,
        group_id: str,
        tenant_id: str,
        design_ref: str,
        display_name: str,
        *,
        sample_size: int = 0,
    ) -> ControlGroup:
        """Add a control group to an experiment design."""
        if group_id in self._groups:
            raise RuntimeCoreInvariantError("Duplicate group_id")
        if design_ref not in self._designs:
            raise RuntimeCoreInvariantError("Unknown design_ref")
        design = self._designs[design_ref]
        if design.phase in _EXPERIMENT_TERMINAL:
            raise RuntimeCoreInvariantError("Cannot add control group to terminal experiment")
        now = self._now()
        group = ControlGroup(
            group_id=group_id,
            tenant_id=tenant_id,
            design_ref=design_ref,
            display_name=display_name,
            sample_size=sample_size,
            created_at=now,
        )
        self._groups[group_id] = group
        _emit(self._events, "control_group_added", {
            "group_id": group_id, "design_ref": design_ref,
        }, group_id, now)
        return group

    # ------------------------------------------------------------------
    # Phase transitions
    # ------------------------------------------------------------------

    def start_experiment(self, design_id: str) -> ExperimentDesign:
        """Transition experiment from DESIGN to RUNNING."""
        old = self.get_design(design_id)
        if old.phase != ExperimentPhase.DESIGN:
            raise RuntimeCoreInvariantError("Can only start DESIGN experiments")
        now = self._now()
        updated = ExperimentDesign(
            design_id=old.design_id, tenant_id=old.tenant_id,
            hypothesis_ref=old.hypothesis_ref, display_name=old.display_name,
            phase=ExperimentPhase.RUNNING, variable_count=old.variable_count,
            created_at=old.created_at, metadata=old.metadata,
        )
        self._designs[design_id] = updated
        _emit(self._events, "experiment_started", {"design_id": design_id}, design_id, now)
        return updated

    def analyze_experiment(self, design_id: str) -> ExperimentDesign:
        """Transition experiment from RUNNING to ANALYSIS."""
        old = self.get_design(design_id)
        if old.phase != ExperimentPhase.RUNNING:
            raise RuntimeCoreInvariantError("Can only analyze RUNNING experiments")
        now = self._now()
        updated = ExperimentDesign(
            design_id=old.design_id, tenant_id=old.tenant_id,
            hypothesis_ref=old.hypothesis_ref, display_name=old.display_name,
            phase=ExperimentPhase.ANALYSIS, variable_count=old.variable_count,
            created_at=old.created_at, metadata=old.metadata,
        )
        self._designs[design_id] = updated
        _emit(self._events, "experiment_analyzing", {"design_id": design_id}, design_id, now)
        return updated

    def complete_experiment(self, design_id: str) -> ExperimentDesign:
        """Transition experiment from ANALYSIS to COMPLETED."""
        old = self.get_design(design_id)
        if old.phase != ExperimentPhase.ANALYSIS:
            raise RuntimeCoreInvariantError("Can only complete ANALYSIS experiments")
        now = self._now()
        updated = ExperimentDesign(
            design_id=old.design_id, tenant_id=old.tenant_id,
            hypothesis_ref=old.hypothesis_ref, display_name=old.display_name,
            phase=ExperimentPhase.COMPLETED, variable_count=old.variable_count,
            created_at=old.created_at, metadata=old.metadata,
        )
        self._designs[design_id] = updated
        _emit(self._events, "experiment_completed", {"design_id": design_id}, design_id, now)
        return updated

    def fail_experiment(self, design_id: str) -> ExperimentDesign:
        """Mark an experiment as FAILED."""
        old = self.get_design(design_id)
        if old.phase in _EXPERIMENT_TERMINAL:
            raise RuntimeCoreInvariantError("Experiment already in terminal phase")
        now = self._now()
        updated = ExperimentDesign(
            design_id=old.design_id, tenant_id=old.tenant_id,
            hypothesis_ref=old.hypothesis_ref, display_name=old.display_name,
            phase=ExperimentPhase.FAILED, variable_count=old.variable_count,
            created_at=old.created_at, metadata=old.metadata,
        )
        self._designs[design_id] = updated
        _emit(self._events, "experiment_failed", {"design_id": design_id}, design_id, now)
        return updated

    # ------------------------------------------------------------------
    # Results
    # ------------------------------------------------------------------

    def record_result(
        self,
        result_id: str,
        tenant_id: str,
        design_ref: str,
        *,
        significance: ResultSignificance = ResultSignificance.UNDETERMINED,
        effect_size: float = 0.0,
        p_value: float = 0.5,
    ) -> ExperimentResult:
        """Record a result for an experiment."""
        if result_id in self._results:
            raise RuntimeCoreInvariantError("Duplicate result_id")
        if design_ref not in self._designs:
            raise RuntimeCoreInvariantError("Unknown design_ref")
        now = self._now()
        result = ExperimentResult(
            result_id=result_id,
            tenant_id=tenant_id,
            design_ref=design_ref,
            significance=significance,
            effect_size=effect_size,
            p_value=p_value,
            created_at=now,
        )
        self._results[result_id] = result
        _emit(self._events, "result_recorded", {
            "result_id": result_id, "design_ref": design_ref,
            "significance": significance.value,
        }, result_id, now)
        return result

    # ------------------------------------------------------------------
    # Falsification
    # ------------------------------------------------------------------

    def record_falsification(
        self,
        record_id: str,
        tenant_id: str,
        hypothesis_ref: str,
        evidence_ref: str,
        *,
        status: FalsificationStatus = FalsificationStatus.UNFALSIFIED,
    ) -> FalsificationRecord:
        """Record a falsification attempt for a hypothesis."""
        if record_id in self._falsifications:
            raise RuntimeCoreInvariantError("Duplicate falsification record_id")
        now = self._now()
        record = FalsificationRecord(
            record_id=record_id,
            tenant_id=tenant_id,
            hypothesis_ref=hypothesis_ref,
            status=status,
            evidence_ref=evidence_ref,
            created_at=now,
        )
        self._falsifications[record_id] = record
        _emit(self._events, "falsification_recorded", {
            "record_id": record_id, "hypothesis_ref": hypothesis_ref,
            "status": status.value,
        }, record_id, now)
        return record

    # ------------------------------------------------------------------
    # Replication
    # ------------------------------------------------------------------

    def record_replication(
        self,
        replication_id: str,
        tenant_id: str,
        original_ref: str,
        *,
        status: ReplicationStatus = ReplicationStatus.PENDING,
        confidence: float = 0.0,
    ) -> ReplicationRecord:
        """Record a replication attempt."""
        if replication_id in self._replications:
            raise RuntimeCoreInvariantError("Duplicate replication_id")
        now = self._now()
        record = ReplicationRecord(
            replication_id=replication_id,
            tenant_id=tenant_id,
            original_ref=original_ref,
            status=status,
            confidence=confidence,
            created_at=now,
        )
        self._replications[replication_id] = record
        _emit(self._events, "replication_recorded", {
            "replication_id": replication_id, "original_ref": original_ref,
            "status": status.value,
        }, replication_id, now)
        return record

    # ------------------------------------------------------------------
    # Assessment
    # ------------------------------------------------------------------

    def experiment_assessment(
        self,
        assessment_id: str,
        tenant_id: str,
    ) -> ExperimentAssessment:
        """Produce an assessment of experimentation activity."""
        now = self._now()
        total_designs = sum(1 for d in self._designs.values() if d.tenant_id == tenant_id)
        total_results = sum(1 for r in self._results.values() if r.tenant_id == tenant_id)
        total_replications = sum(1 for r in self._replications.values() if r.tenant_id == tenant_id)
        successful = sum(
            1 for r in self._replications.values()
            if r.tenant_id == tenant_id and r.status == ReplicationStatus.SUCCESSFUL
        )
        success_rate = successful / total_replications if total_replications > 0 else 0.0
        assessment = ExperimentAssessment(
            assessment_id=assessment_id,
            tenant_id=tenant_id,
            total_designs=total_designs,
            total_results=total_results,
            total_replications=total_replications,
            success_rate=success_rate,
            assessed_at=now,
        )
        _emit(self._events, "experiment_assessment", {
            "assessment_id": assessment_id, "total_designs": total_designs,
        }, assessment_id, now)
        return assessment

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------

    def experiment_snapshot(
        self,
        snapshot_id: str,
        tenant_id: str,
    ) -> ExperimentSnapshot:
        """Capture a point-in-time experiment snapshot."""
        now = self._now()
        snap = ExperimentSnapshot(
            snapshot_id=snapshot_id,
            tenant_id=tenant_id,
            total_designs=self.design_count,
            total_variables=self.variable_count,
            total_groups=self.group_count,
            total_results=self.result_count,
            total_falsifications=self.falsification_count,
            total_violations=self.violation_count,
            captured_at=now,
        )
        _emit(self._events, "experiment_snapshot_captured", {
            "snapshot_id": snapshot_id,
        }, snapshot_id, now)
        return snap

    # ------------------------------------------------------------------
    # Closure Report
    # ------------------------------------------------------------------

    def experiment_closure_report(
        self,
        report_id: str,
        tenant_id: str,
    ) -> ExperimentClosureReport:
        """Produce a closure report for experimentation activity."""
        now = self._now()
        report = ExperimentClosureReport(
            report_id=report_id,
            tenant_id=tenant_id,
            total_designs=self.design_count,
            total_results=self.result_count,
            total_replications=self.replication_count,
            total_violations=self.violation_count,
            created_at=now,
        )
        _emit(self._events, "experiment_closure_report", {
            "report_id": report_id,
        }, report_id, now)
        return report

    # ------------------------------------------------------------------
    # Violation detection
    # ------------------------------------------------------------------

    def detect_experiment_violations(self, tenant_id: str = "") -> tuple:
        """Detect experiment violations (idempotent).

        Checks:
        1. no_control_group: design with no control groups
        2. no_variables: design with no variables
        3. result_without_analysis: result recorded for a non-ANALYSIS/COMPLETED design
        """
        now = self._now()
        new_violations: list = []

        for design in self._designs.values():
            if tenant_id and design.tenant_id != tenant_id:
                continue

            # 1) no_control_group
            has_group = any(g.design_ref == design.design_id for g in self._groups.values())
            if not has_group and design.phase not in {ExperimentPhase.DESIGN}:
                vid = stable_identifier("viol-expt", {
                    "design": design.design_id, "op": "no_control_group",
                })
                if vid not in self._violations:
                    v = {
                        "violation_id": vid,
                        "tenant_id": design.tenant_id,
                        "operation": "no_control_group",
                        "reason": "experiment has no control group",
                        "detected_at": now,
                    }
                    self._violations[vid] = v
                    new_violations.append(v)

            # 2) no_variables
            has_var = any(v.design_ref == design.design_id for v in self._variables.values())
            if not has_var and design.phase not in {ExperimentPhase.DESIGN}:
                vid = stable_identifier("viol-expt", {
                    "design": design.design_id, "op": "no_variables",
                })
                if vid not in self._violations:
                    v = {
                        "violation_id": vid,
                        "tenant_id": design.tenant_id,
                        "operation": "no_variables",
                        "reason": "experiment has no variables defined",
                        "detected_at": now,
                    }
                    self._violations[vid] = v
                    new_violations.append(v)

        # 3) result_without_analysis
        for result in self._results.values():
            if tenant_id and result.tenant_id != tenant_id:
                continue
            design = self._designs.get(result.design_ref)
            if design and design.phase not in {ExperimentPhase.ANALYSIS, ExperimentPhase.COMPLETED}:
                vid = stable_identifier("viol-expt", {
                    "result": result.result_id, "op": "result_without_analysis",
                })
                if vid not in self._violations:
                    v = {
                        "violation_id": vid,
                        "tenant_id": result.tenant_id,
                        "operation": "result_without_analysis",
                        "reason": "result recorded before analysis phase",
                        "detected_at": now,
                    }
                    self._violations[vid] = v
                    new_violations.append(v)

        if new_violations:
            _emit(self._events, "experiment_violations_detected", {
                "count": len(new_violations),
            }, "violation-scan", now)
        return tuple(new_violations)

    # ------------------------------------------------------------------
    # Collections / snapshot / state_hash
    # ------------------------------------------------------------------

    def _collections(self) -> dict[str, Any]:
        """Return all internal collections."""
        return {
            "designs": self._designs,
            "falsifications": self._falsifications,
            "groups": self._groups,
            "replications": self._replications,
            "results": self._results,
            "variables": self._variables,
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
        """Compute a deterministic hash of engine state."""
        parts = [
            f"designs={self.design_count}",
            f"falsifications={self.falsification_count}",
            f"groups={self.group_count}",
            f"replications={self.replication_count}",
            f"results={self.result_count}",
            f"variables={self.variable_count}",
            f"violations={self.violation_count}",
        ]
        return sha256("|".join(parts).encode()).hexdigest()
