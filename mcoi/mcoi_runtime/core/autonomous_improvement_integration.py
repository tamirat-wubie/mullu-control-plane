"""Purpose: autonomous improvement integration bridge.
Governance scope: composing autonomous improvement engine with change runtime,
    optimization, governance, memory mesh, and operational graph.
Dependencies: autonomous_improvement engine, change_runtime engine,
    event_spine, memory_mesh, core invariants.
Invariants:
  - Every improvement operation emits events.
  - Improvement state is attached to memory mesh.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..contracts.autonomous_improvement import (
    AutonomyLevel,
    ImprovementDisposition,
    ImprovementOutcomeVerdict,
    LearningWindowStatus,
    SuppressionReason,
)
from ..contracts.event import EventRecord, EventSource, EventType
from ..contracts.memory_mesh import (
    MemoryRecord,
    MemoryScope,
    MemoryTrustLevel,
    MemoryType,
)
from .autonomous_improvement import AutonomousImprovementEngine
from .change_runtime import ChangeRuntimeEngine
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier
from .memory_mesh import MemoryMeshEngine


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-aint", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class AutonomousImprovementIntegration:
    """Integration bridge for autonomous improvement with platform layers."""

    def __init__(
        self,
        improvement_engine: AutonomousImprovementEngine,
        change_engine: ChangeRuntimeEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(improvement_engine, AutonomousImprovementEngine):
            raise RuntimeCoreInvariantError("improvement_engine must be an AutonomousImprovementEngine")
        if not isinstance(change_engine, ChangeRuntimeEngine):
            raise RuntimeCoreInvariantError("change_engine must be a ChangeRuntimeEngine")
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._improvement = improvement_engine
        self._change = change_engine
        self._events = event_spine
        self._memory = memory_engine

    # ------------------------------------------------------------------
    # Evaluate and auto-promote from optimization recommendations
    # ------------------------------------------------------------------

    def evaluate_from_optimization(
        self,
        candidate_id: str,
        recommendation_id: str,
        title: str,
        *,
        change_type: str = "optimization",
        scope_ref_id: str = "",
        confidence: float = 0.0,
        estimated_improvement_pct: float = 0.0,
        estimated_cost_delta: float = 0.0,
        risk_score: float = 0.0,
    ) -> dict[str, Any]:
        """Evaluate an optimization recommendation for autonomous promotion."""
        candidate = self._improvement.evaluate_candidate(
            candidate_id, recommendation_id, title,
            change_type=change_type,
            scope_ref_id=scope_ref_id,
            confidence=confidence,
            estimated_improvement_pct=estimated_improvement_pct,
            estimated_cost_delta=estimated_cost_delta,
            risk_score=risk_score,
        )
        _emit(self._events, "evaluate_from_optimization", {
            "candidate_id": candidate_id,
            "recommendation_id": recommendation_id,
            "disposition": candidate.disposition.value,
        }, candidate_id)
        return {
            "candidate_id": candidate_id,
            "source": "optimization",
            "disposition": candidate.disposition.value,
            "autonomy_level": candidate.autonomy_level.value,
            "reason": candidate.reason,
            "auto_promoted": candidate.disposition == ImprovementDisposition.AUTO_PROMOTED,
        }

    # ------------------------------------------------------------------
    # Evaluate and auto-promote from governance policy
    # ------------------------------------------------------------------

    def evaluate_from_governance(
        self,
        candidate_id: str,
        recommendation_id: str,
        title: str,
        *,
        change_type: str = "governance",
        scope_ref_id: str = "",
        confidence: float = 0.0,
        estimated_improvement_pct: float = 0.0,
        estimated_cost_delta: float = 0.0,
        risk_score: float = 0.0,
    ) -> dict[str, Any]:
        """Evaluate a governance-driven recommendation for autonomous promotion."""
        candidate = self._improvement.evaluate_candidate(
            candidate_id, recommendation_id, title,
            change_type=change_type,
            scope_ref_id=scope_ref_id,
            confidence=confidence,
            estimated_improvement_pct=estimated_improvement_pct,
            estimated_cost_delta=estimated_cost_delta,
            risk_score=risk_score,
        )
        _emit(self._events, "evaluate_from_governance", {
            "candidate_id": candidate_id,
            "disposition": candidate.disposition.value,
        }, candidate_id)
        return {
            "candidate_id": candidate_id,
            "source": "governance",
            "disposition": candidate.disposition.value,
            "autonomy_level": candidate.autonomy_level.value,
            "reason": candidate.reason,
            "auto_promoted": candidate.disposition == ImprovementDisposition.AUTO_PROMOTED,
        }

    # ------------------------------------------------------------------
    # Evaluate from fault campaign
    # ------------------------------------------------------------------

    def evaluate_from_fault_campaign(
        self,
        candidate_id: str,
        recommendation_id: str,
        title: str,
        *,
        change_type: str = "fault_remediation",
        scope_ref_id: str = "",
        confidence: float = 0.0,
        estimated_improvement_pct: float = 0.0,
        estimated_cost_delta: float = 0.0,
        risk_score: float = 0.0,
    ) -> dict[str, Any]:
        """Evaluate a fault-campaign recommendation for autonomous promotion."""
        candidate = self._improvement.evaluate_candidate(
            candidate_id, recommendation_id, title,
            change_type=change_type,
            scope_ref_id=scope_ref_id,
            confidence=confidence,
            estimated_improvement_pct=estimated_improvement_pct,
            estimated_cost_delta=estimated_cost_delta,
            risk_score=risk_score,
        )
        _emit(self._events, "evaluate_from_fault_campaign", {
            "candidate_id": candidate_id,
            "disposition": candidate.disposition.value,
        }, candidate_id)
        return {
            "candidate_id": candidate_id,
            "source": "fault_campaign",
            "disposition": candidate.disposition.value,
            "autonomy_level": candidate.autonomy_level.value,
            "reason": candidate.reason,
            "auto_promoted": candidate.disposition == ImprovementDisposition.AUTO_PROMOTED,
        }

    # ------------------------------------------------------------------
    # Run full improvement lifecycle
    # ------------------------------------------------------------------

    def run_improvement_lifecycle(
        self,
        session_id: str,
        candidate_id: str,
        change_id: str,
        metric_name: str,
        baseline_value: float,
        final_value: float,
        *,
        confidence: float = 0.8,
        window_duration_seconds: float = 3600.0,
    ) -> dict[str, Any]:
        """Run a complete improvement lifecycle: session → window → outcome."""
        # Start session
        session = self._improvement.start_session(session_id, candidate_id, change_id)

        # Open and close learning window
        window_id = f"{session_id}-win"
        window = self._improvement.open_learning_window(
            window_id, change_id, metric_name, baseline_value,
            candidate_id=candidate_id,
            duration_seconds=window_duration_seconds,
        )
        window = self._improvement.record_observation(window_id, final_value)
        window = self._improvement.close_learning_window(window_id)

        # Assess outcome
        outcome_id = f"{session_id}-out"
        outcome = self._improvement.assess_outcome(
            outcome_id, session_id,
            baseline_value=baseline_value,
            final_value=final_value,
            confidence=confidence,
        )

        _emit(self._events, "improvement_lifecycle_completed", {
            "session_id": session_id,
            "candidate_id": candidate_id,
            "verdict": outcome.verdict.value,
            "improvement_pct": outcome.improvement_pct,
        }, session_id)
        return {
            "session_id": session_id,
            "candidate_id": candidate_id,
            "change_id": change_id,
            "window_id": window_id,
            "outcome_id": outcome_id,
            "verdict": outcome.verdict.value,
            "improvement_pct": outcome.improvement_pct,
            "rollback_triggered": outcome.rollback_triggered,
            "suppression_triggered": outcome.suppression_triggered,
            "reinforcement_applied": outcome.reinforcement_applied,
        }

    # ------------------------------------------------------------------
    # Monitor and trigger rollback
    # ------------------------------------------------------------------

    def monitor_and_rollback(
        self,
        change_id: str,
        session_id: str,
        metric_name: str,
        baseline_value: float,
        observed_value: float,
        *,
        tolerance_pct: float | None = None,
    ) -> dict[str, Any]:
        """Check for rollback trigger and roll back the change if triggered."""
        trigger = self._improvement.check_rollback_trigger(
            change_id, session_id, metric_name,
            baseline_value, observed_value,
            tolerance_pct=tolerance_pct,
        )
        rolled_back = False
        if trigger is not None:
            try:
                self._change.rollback_change(change_id)
                rolled_back = True
            except (ValueError, RuntimeError):
                pass  # Change may not be in rollback-eligible state

        _emit(self._events, "monitor_and_rollback", {
            "change_id": change_id,
            "triggered": trigger is not None,
            "rolled_back": rolled_back,
        }, change_id)
        return {
            "change_id": change_id,
            "session_id": session_id,
            "metric_name": metric_name,
            "triggered": trigger is not None,
            "rolled_back": rolled_back,
            "degradation_pct": trigger.degradation_pct if trigger else 0.0,
            "tolerance_pct": trigger.tolerance_pct if trigger else 0.0,
        }

    # ------------------------------------------------------------------
    # Suppress pattern from change engine feedback
    # ------------------------------------------------------------------

    def suppress_from_change_failure(
        self,
        change_type: str,
        scope_ref_id: str,
        reason: SuppressionReason = SuppressionReason.REPEATED_FAILURE,
    ) -> dict[str, Any]:
        """Suppress an improvement pattern due to change failure."""
        record = self._improvement.suppress_pattern(change_type, scope_ref_id, reason)
        _emit(self._events, "suppress_from_change_failure", {
            "change_type": change_type,
            "scope_ref_id": scope_ref_id,
            "reason": reason.value,
        }, f"{change_type}:{scope_ref_id}")
        return {
            "suppression_id": record.suppression_id,
            "change_type": change_type,
            "scope_ref_id": scope_ref_id,
            "reason": reason.value,
            "failure_count": record.failure_count,
        }

    # ------------------------------------------------------------------
    # Memory mesh and graph attachment
    # ------------------------------------------------------------------

    def attach_improvement_to_memory_mesh(
        self,
        scope_ref_id: str,
    ) -> MemoryRecord:
        """Persist improvement state to memory mesh."""
        now = _now_iso()
        content: dict[str, Any] = {
            "scope_ref_id": scope_ref_id,
            "total_candidates": self._improvement.candidate_count,
            "total_sessions": self._improvement.session_count,
            "total_outcomes": self._improvement.outcome_count,
            "total_suppressions": self._improvement.suppression_count,
            "auto_changes": self._improvement.auto_change_count,
        }

        mem = MemoryRecord(
            memory_id=stable_identifier("mem-aim", {"id": scope_ref_id}),
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            scope_ref_id=scope_ref_id,
            trust_level=MemoryTrustLevel.VERIFIED,
            title=f"Improvement state: {scope_ref_id}",
            content=content,
            source_ids=(scope_ref_id,),
            tags=("improvement", "autonomous", "state"),
            confidence=1.0,
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(mem)

        _emit(self._events, "improvement_attached_to_memory", {
            "scope_ref_id": scope_ref_id,
            "memory_id": mem.memory_id,
        }, scope_ref_id)
        return mem

    def attach_improvement_to_graph(
        self,
        scope_ref_id: str,
    ) -> dict[str, Any]:
        """Return improvement state suitable for operational graph consumption."""
        suppressions = self._improvement.get_suppressions()
        return {
            "scope_ref_id": scope_ref_id,
            "total_candidates": self._improvement.candidate_count,
            "total_sessions": self._improvement.session_count,
            "total_outcomes": self._improvement.outcome_count,
            "total_suppressions": self._improvement.suppression_count,
            "auto_changes": self._improvement.auto_change_count,
            "suppressed_patterns": [
                {"change_type": s.change_type, "scope_ref_id": s.scope_ref_id, "reason": s.reason.value}
                for s in suppressions
            ],
        }
