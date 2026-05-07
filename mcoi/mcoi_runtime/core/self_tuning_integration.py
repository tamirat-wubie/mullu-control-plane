"""Purpose: self-tuning integration bridge.
Governance scope: composing self-tuning engine with event spine, memory mesh,
    and operational graph. Provides convenience methods to create improvement
    proposals from various observability and operational signal sources.
Dependencies: self_tuning engine, event_spine, memory_mesh, core invariants.
Invariants:
  - Every improvement operation emits events.
  - Improvement state is attached to memory mesh.
  - All returns are immutable dicts or MemoryRecord instances.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..contracts.event import EventRecord, EventSource, EventType
from ..contracts.memory_mesh import (
    MemoryRecord,
    MemoryScope,
    MemoryTrustLevel,
    MemoryType,
)
from ..contracts.self_tuning import (
    ImprovementKind,
    ImprovementRiskLevel,
    ImprovementScope,
    LearningSignalKind,
)
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier
from .memory_mesh import MemoryMeshEngine
from .self_tuning import SelfTuningEngine


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-stint", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class SelfTuningIntegration:
    """Integration bridge for self-tuning with platform layers."""

    def __init__(
        self,
        tuning_engine: SelfTuningEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(tuning_engine, SelfTuningEngine):
            raise RuntimeCoreInvariantError("tuning_engine must be a SelfTuningEngine")
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._tuning = tuning_engine
        self._events = event_spine
        self._memory = memory_engine
        self._bridge_seq = 0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _next_ids(self, tenant_id: str, source_type: str) -> tuple[str, str]:
        """Generate deterministic signal and proposal IDs from seq."""
        self._bridge_seq += 1
        seq = str(self._bridge_seq)
        signal_id = stable_identifier("sig-stun", {"tenant": tenant_id, "source": source_type, "seq": seq})
        proposal_id = stable_identifier("prop-stun", {"tenant": tenant_id, "source": source_type, "seq": seq})
        return signal_id, proposal_id

    def _improve(
        self,
        tenant_id: str,
        ref: str,
        source_type: str,
        description: str,
        kind: ImprovementKind,
        scope: ImprovementScope,
        risk_level: ImprovementRiskLevel,
        signal_kind: LearningSignalKind,
    ) -> dict[str, Any]:
        """Register a signal and propose an improvement."""
        signal_id, proposal_id = self._next_ids(tenant_id, source_type)

        signal = self._tuning.register_learning_signal(
            signal_id=signal_id,
            tenant_id=tenant_id,
            kind=signal_kind,
            source_runtime=source_type,
            description=description,
        )
        proposal = self._tuning.propose_improvement(
            proposal_id=proposal_id,
            tenant_id=tenant_id,
            signal_ref=signal_id,
            kind=kind,
            scope=scope,
            risk_level=risk_level,
            description=description,
            justification=f"Auto-generated from {source_type} signal {ref}",
        )

        _emit(self._events, f"improvement_from_{source_type}", {
            "tenant_id": tenant_id,
            "signal_id": signal_id,
            "proposal_id": proposal_id,
            "ref": ref,
        }, signal_id)

        return {
            "signal_id": signal_id,
            "proposal_id": proposal_id,
            "source_type": source_type,
            "tenant_id": tenant_id,
            "kind": proposal.kind.value,
            "scope": proposal.scope.value,
            "risk_level": proposal.risk_level.value,
            "status": proposal.status.value,
        }

    # ------------------------------------------------------------------
    # Signal-based improvement methods
    # ------------------------------------------------------------------

    def improvement_from_observability(
        self,
        tenant_id: str,
        anomaly_ref: str,
        description: str = "Observability anomaly",
    ) -> dict[str, Any]:
        """Create improvement from an observability anomaly."""
        return self._improve(
            tenant_id=tenant_id,
            ref=anomaly_ref,
            source_type="observability",
            description=description,
            kind=ImprovementKind.PARAMETER,
            scope=ImprovementScope.RUNTIME,
            risk_level=ImprovementRiskLevel.LOW,
            signal_kind=LearningSignalKind.OBSERVABILITY_ANOMALY,
        )

    def improvement_from_execution_failures(
        self,
        tenant_id: str,
        execution_ref: str,
        description: str = "Execution failure pattern",
    ) -> dict[str, Any]:
        """Create improvement from execution failure patterns."""
        return self._improve(
            tenant_id=tenant_id,
            ref=execution_ref,
            source_type="execution_failures",
            description=description,
            kind=ImprovementKind.EXECUTION,
            scope=ImprovementScope.RUNTIME,
            risk_level=ImprovementRiskLevel.LOW,
            signal_kind=LearningSignalKind.EXECUTION_FAILURE,
        )

    def improvement_from_policy_simulation(
        self,
        tenant_id: str,
        simulation_ref: str,
        description: str = "Policy simulation insight",
    ) -> dict[str, Any]:
        """Create improvement from policy simulation results."""
        return self._improve(
            tenant_id=tenant_id,
            ref=simulation_ref,
            source_type="policy_simulation",
            description=description,
            kind=ImprovementKind.POLICY,
            scope=ImprovementScope.TENANT,
            risk_level=ImprovementRiskLevel.MEDIUM,
            signal_kind=LearningSignalKind.POLICY_SIMULATION,
        )

    def improvement_from_forecasting_error(
        self,
        tenant_id: str,
        forecast_ref: str,
        description: str = "Forecasting error detected",
    ) -> dict[str, Any]:
        """Create improvement from forecasting errors."""
        return self._improve(
            tenant_id=tenant_id,
            ref=forecast_ref,
            source_type="forecasting_error",
            description=description,
            kind=ImprovementKind.PARAMETER,
            scope=ImprovementScope.RUNTIME,
            risk_level=ImprovementRiskLevel.LOW,
            signal_kind=LearningSignalKind.FORECAST_DRIFT,
        )

    def improvement_from_workforce_overload(
        self,
        tenant_id: str,
        workforce_ref: str,
        description: str = "Workforce overload detected",
    ) -> dict[str, Any]:
        """Create improvement from workforce overload signals."""
        return self._improve(
            tenant_id=tenant_id,
            ref=workforce_ref,
            source_type="workforce_overload",
            description=description,
            kind=ImprovementKind.STAFFING,
            scope=ImprovementScope.TENANT,
            risk_level=ImprovementRiskLevel.MEDIUM,
            signal_kind=LearningSignalKind.WORKFORCE_OVERLOAD,
        )

    def improvement_from_financial_loss(
        self,
        tenant_id: str,
        financial_ref: str,
        description: str = "Financial loss detected",
    ) -> dict[str, Any]:
        """Create improvement from financial loss signals."""
        return self._improve(
            tenant_id=tenant_id,
            ref=financial_ref,
            source_type="financial_loss",
            description=description,
            kind=ImprovementKind.THRESHOLD,
            scope=ImprovementScope.TENANT,
            risk_level=ImprovementRiskLevel.MEDIUM,
            signal_kind=LearningSignalKind.FINANCIAL_LOSS,
        )

    def improvement_from_constitutional_violation(
        self,
        tenant_id: str,
        violation_ref: str,
        description: str = "Constitutional violation detected",
    ) -> dict[str, Any]:
        """Create improvement from constitutional violations. Always CRITICAL, never auto-applies."""
        return self._improve(
            tenant_id=tenant_id,
            ref=violation_ref,
            source_type="constitutional_violation",
            description=description,
            kind=ImprovementKind.POLICY,
            scope=ImprovementScope.CONSTITUTIONAL,
            risk_level=ImprovementRiskLevel.CRITICAL,
            signal_kind=LearningSignalKind.CONSTITUTIONAL_VIOLATION,
        )

    # ------------------------------------------------------------------
    # Memory mesh and graph attachment
    # ------------------------------------------------------------------

    def attach_improvement_state_to_memory_mesh(
        self,
        scope_ref_id: str,
    ) -> MemoryRecord:
        """Persist improvement state to memory mesh."""
        now = _now_iso()
        mid = stable_identifier("mem-stun", {
            "scope": scope_ref_id,
            "seq": str(self._memory.memory_count),
        })
        content: dict[str, Any] = {
            "scope_ref_id": scope_ref_id,
            "total_signals": self._tuning.signal_count,
            "total_proposals": self._tuning.proposal_count,
            "total_adjustments": self._tuning.adjustment_count,
            "total_policy_tunings": self._tuning.policy_tuning_count,
            "total_execution_tunings": self._tuning.execution_tuning_count,
            "total_decisions": self._tuning.decision_count,
            "total_violations": self._tuning.violation_count,
        }
        record = MemoryRecord(
            memory_id=mid,
            scope_ref_id=scope_ref_id,
            title="Self-tuning state",
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            trust_level=MemoryTrustLevel.VERIFIED,
            content=content,
            source_ids=(scope_ref_id,),
            tags=("self_tuning", "improvement", "learning"),
            confidence=1.0,
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(record)
        _emit(self._events, "improvement_state_attached_to_memory", {
            "scope_ref_id": scope_ref_id,
            "memory_id": mid,
        }, scope_ref_id)
        return record

    def attach_improvement_state_to_graph(
        self,
        scope_ref_id: str,
    ) -> dict[str, Any]:
        """Return improvement state suitable for operational graph consumption."""
        return {
            "scope_ref_id": scope_ref_id,
            "total_signals": self._tuning.signal_count,
            "total_proposals": self._tuning.proposal_count,
            "total_adjustments": self._tuning.adjustment_count,
            "total_policy_tunings": self._tuning.policy_tuning_count,
            "total_execution_tunings": self._tuning.execution_tuning_count,
            "total_decisions": self._tuning.decision_count,
            "total_violations": self._tuning.violation_count,
        }
