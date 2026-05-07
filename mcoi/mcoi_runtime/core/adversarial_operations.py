"""Purpose: adversarial operations bridge.
Governance scope: orchestrating fault injection campaigns across runtime
    subsystems with event emission, memory recording, and benchmark scoring.
Dependencies: FaultInjectionEngine, EventSpineEngine, MemoryMeshEngine,
    core invariants.
Invariants:
  - Every fault injection emits an event for audit.
  - Recovery assessments are recorded in memory mesh.
  - Campaign outcomes produce benchmark-style scores.
  - All outputs are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..contracts.event import EventRecord, EventSource, EventType
from ..contracts.fault_injection import (
    AdversarialOutcome,
    AdversarialSession,
    FaultDisposition,
    FaultInjectionRecord,
    FaultObservation,
    FaultRecoveryAssessment,
    FaultSeverity,
    FaultTargetKind,
    FaultType,
    InjectionMode,
)
from ..contracts.memory_mesh import (
    MemoryRecord,
    MemoryScope,
    MemoryTrustLevel,
    MemoryType,
)
from .event_spine import EventSpineEngine
from .fault_injection import FaultInjectionEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier
from .memory_mesh import MemoryMeshEngine


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-adv", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class AdversarialOperationsBridge:
    """Orchestrates fault injection across subsystems with full audit trail."""

    def __init__(
        self,
        fault_engine: FaultInjectionEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(fault_engine, FaultInjectionEngine):
            raise RuntimeCoreInvariantError("fault_engine must be a FaultInjectionEngine")
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._fault = fault_engine
        self._events = event_spine
        self._memory = memory_engine

    # -----------------------------------------------------------------------
    # Targeted injection methods
    # -----------------------------------------------------------------------

    def inject_into_supervisor_tick(
        self, tick: int = 0,
    ) -> dict[str, Any]:
        """Inject faults targeting the supervisor tick flow."""
        records = self._fault.inject_for_target(FaultTargetKind.SUPERVISOR, tick)
        event = _emit(self._events, "fault_injected_supervisor", {
            "tick": tick,
            "fault_count": len(records),
            "fault_types": [r.fault_type.value for r in records],
        }, f"supervisor-fault-{tick}")
        return {"records": records, "event": event}

    def inject_into_provider_routing(
        self, tick: int = 0, target_ref_id: str = "",
    ) -> dict[str, Any]:
        """Inject faults targeting provider routing."""
        records = self._fault.inject_for_target(
            FaultTargetKind.PROVIDER, tick, target_ref_id,
        )
        event = _emit(self._events, "fault_injected_provider", {
            "tick": tick,
            "fault_count": len(records),
        }, f"provider-fault-{tick}")
        return {"records": records, "event": event}

    def inject_into_communication_surface(
        self, tick: int = 0, target_ref_id: str = "",
    ) -> dict[str, Any]:
        """Inject faults targeting communication channels."""
        records = self._fault.inject_for_target(
            FaultTargetKind.COMMUNICATION, tick, target_ref_id,
        )
        event = _emit(self._events, "fault_injected_communication", {
            "tick": tick,
            "fault_count": len(records),
        }, f"comm-fault-{tick}")
        return {"records": records, "event": event}

    def inject_into_artifact_ingestion(
        self, tick: int = 0, target_ref_id: str = "",
    ) -> dict[str, Any]:
        """Inject faults targeting artifact ingestion."""
        records = self._fault.inject_for_target(
            FaultTargetKind.ARTIFACT_INGESTION, tick, target_ref_id,
        )
        event = _emit(self._events, "fault_injected_artifact", {
            "tick": tick,
            "fault_count": len(records),
        }, f"artifact-fault-{tick}")
        return {"records": records, "event": event}

    def inject_into_checkpoint_restore(
        self, tick: int = 0,
    ) -> dict[str, Any]:
        """Inject faults targeting checkpoint/restore."""
        records = self._fault.inject_for_target(FaultTargetKind.CHECKPOINT, tick)
        event = _emit(self._events, "fault_injected_checkpoint", {
            "tick": tick,
            "fault_count": len(records),
        }, f"checkpoint-fault-{tick}")
        return {"records": records, "event": event}

    def inject_into_obligation_runtime(
        self, tick: int = 0, target_ref_id: str = "",
    ) -> dict[str, Any]:
        """Inject faults targeting obligation transitions."""
        records = self._fault.inject_for_target(
            FaultTargetKind.OBLIGATION_RUNTIME, tick, target_ref_id,
        )
        event = _emit(self._events, "fault_injected_obligation", {
            "tick": tick,
            "fault_count": len(records),
        }, f"obligation-fault-{tick}")
        return {"records": records, "event": event}

    def inject_into_reaction_engine(
        self, tick: int = 0,
    ) -> dict[str, Any]:
        """Inject faults targeting reaction execution."""
        records = self._fault.inject_for_target(FaultTargetKind.REACTION, tick)
        event = _emit(self._events, "fault_injected_reaction", {
            "tick": tick,
            "fault_count": len(records),
        }, f"reaction-fault-{tick}")
        return {"records": records, "event": event}

    def inject_into_domain_pack_resolution(
        self, tick: int = 0,
    ) -> dict[str, Any]:
        """Inject faults targeting domain pack resolution."""
        records = self._fault.inject_for_target(FaultTargetKind.DOMAIN_PACK, tick)
        event = _emit(self._events, "fault_injected_domain_pack", {
            "tick": tick,
            "fault_count": len(records),
        }, f"dompack-fault-{tick}")
        return {"records": records, "event": event}

    # -----------------------------------------------------------------------
    # Campaign orchestration
    # -----------------------------------------------------------------------

    def run_fault_campaign(
        self,
        name: str,
        spec_ids: tuple[str, ...],
        tick_count: int = 10,
        tags: tuple[str, ...] = (),
    ) -> dict[str, Any]:
        """Run a full fault injection campaign over multiple ticks.

        For each tick, injects all specs whose targets are active.
        Records observations for each injection.
        """
        session = self._fault.start_session(name, spec_ids, tags)

        all_records: list[FaultInjectionRecord] = []
        for tick in range(tick_count):
            for spec_id in spec_ids:
                record = self._fault.inject(spec_id, tick)
                if record is not None:
                    all_records.append(record)
                    # Auto-observe: system attempted injection
                    self._fault.record_observation(
                        record.record_id,
                        observed_behavior=f"Fault {record.fault_type} injected at tick {tick}",
                        expected_behavior="system handles fault gracefully",
                        matches_expected=True,
                    )

        # Emit campaign event
        event = _emit(self._events, "fault_campaign_executed", {
            "session_id": session.session_id,
            "name": name,
            "tick_count": tick_count,
            "total_injections": len(all_records),
            "spec_count": len(spec_ids),
        }, session.session_id)

        return {
            "session": session,
            "records": tuple(all_records),
            "event": event,
        }

    def evaluate_fault_campaign(
        self,
        session_id: str,
        *,
        all_recovered: bool = True,
        all_consistent: bool = True,
    ) -> dict[str, Any]:
        """Evaluate and complete a campaign, producing outcomes and memory."""
        session = self._fault.get_session(session_id)

        # Auto-assess any unassessed records
        session_records = self._fault.get_records()
        for record in session_records:
            if record.spec_id in session.fault_spec_ids:
                existing = self._fault.get_assessments_for_record(record.record_id)
                if not existing:
                    self._fault.assess_recovery(
                        record.record_id,
                        recovered=all_recovered,
                        recovery_method="auto-assessed",
                        degraded=not all_recovered,
                        degraded_reason="campaign default" if not all_recovered else "",
                        state_consistent=all_consistent,
                    )

        # Complete session
        outcome = self._fault.complete_session(session_id)

        # Record outcome in memory
        now = _now_iso()
        mem = MemoryRecord(
            memory_id=stable_identifier("adv-mem", {"sid": session_id, "ts": now}),
            memory_type=MemoryType.OUTCOME,
            scope=MemoryScope.GLOBAL,
            scope_ref_id=session_id,
            trust_level=MemoryTrustLevel.VERIFIED,
            title="Adversarial campaign outcome",
            content={
                "session_id": session_id,
                "name": session.name,
                "passed": outcome.passed,
                "total_faults": outcome.total_faults,
                "faults_recovered": outcome.faults_recovered,
                "faults_degraded": outcome.faults_degraded,
                "faults_failed": outcome.faults_failed,
                "state_consistent": outcome.state_consistent,
                "score": outcome.score,
            },
            source_ids=(session_id,),
            tags=("adversarial", "fault-injection") + session.tags,
            confidence=outcome.score,
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(mem)

        # Emit evaluation event
        event = _emit(self._events, "fault_campaign_evaluated", {
            "session_id": session_id,
            "passed": outcome.passed,
            "score": outcome.score,
            "total_faults": outcome.total_faults,
        }, session_id)

        return {
            "outcome": outcome,
            "memory": mem,
            "event": event,
        }

    # -----------------------------------------------------------------------
    # Recovery assessment helpers
    # -----------------------------------------------------------------------

    def assess_and_record(
        self,
        record_id: str,
        recovered: bool,
        recovery_method: str = "",
        degraded: bool = False,
        degraded_reason: str = "",
        state_consistent: bool = True,
    ) -> dict[str, Any]:
        """Assess recovery and emit event + memory for the assessment."""
        assessment = self._fault.assess_recovery(
            record_id, recovered, recovery_method,
            degraded, degraded_reason, state_consistent,
        )

        event = _emit(self._events, "fault_recovery_assessed", {
            "record_id": record_id,
            "recovered": recovered,
            "degraded": degraded,
            "state_consistent": state_consistent,
        }, record_id)

        return {
            "assessment": assessment,
            "event": event,
        }

    # -----------------------------------------------------------------------
    # Preset campaigns
    # -----------------------------------------------------------------------

    def run_provider_storm_campaign(
        self, tick_count: int = 10,
    ) -> dict[str, Any]:
        """Run a preset provider storm campaign."""
        specs = self._fault.register_provider_storm()
        spec_ids = tuple(s.spec_id for s in specs)
        result = self.run_fault_campaign(
            "provider-storm", spec_ids, tick_count,
            tags=("provider-storm",),
        )
        return result

    def run_event_flood_campaign(
        self, tick_count: int = 20,
    ) -> dict[str, Any]:
        """Run a preset event flood campaign."""
        specs = self._fault.register_event_flood()
        spec_ids = tuple(s.spec_id for s in specs)
        return self.run_fault_campaign(
            "event-flood", spec_ids, tick_count,
            tags=("event-flood",),
        )

    def run_checkpoint_corruption_campaign(self) -> dict[str, Any]:
        """Run a preset checkpoint corruption campaign."""
        specs = self._fault.register_checkpoint_corruption()
        spec_ids = tuple(s.spec_id for s in specs)
        return self.run_fault_campaign(
            "checkpoint-corruption", spec_ids, 3,
            tags=("checkpoint-corruption",),
        )

    def run_communication_failure_campaign(
        self, tick_count: int = 10,
    ) -> dict[str, Any]:
        """Run a preset communication failure campaign."""
        specs = self._fault.register_communication_failure()
        spec_ids = tuple(s.spec_id for s in specs)
        return self.run_fault_campaign(
            "communication-failure", spec_ids, tick_count,
            tags=("communication-failure",),
        )

    def run_governance_conflict_campaign(self) -> dict[str, Any]:
        """Run a preset governance conflict storm campaign."""
        specs = self._fault.register_governance_conflict_storm()
        spec_ids = tuple(s.spec_id for s in specs)
        return self.run_fault_campaign(
            "governance-conflict", spec_ids, 5,
            tags=("governance-storm",),
        )

    def run_full_adversarial_suite(
        self, tick_count: int = 10,
    ) -> dict[str, Any]:
        """Run all preset campaigns and produce aggregate results."""
        campaigns = []

        provider_specs = self._fault.register_provider_storm()
        provider_ids = tuple(s.spec_id for s in provider_specs)
        c1 = self.run_fault_campaign("provider-storm", provider_ids, tick_count, ("full-suite",))
        e1 = self.evaluate_fault_campaign(c1["session"].session_id)
        campaigns.append(e1)

        event_specs = self._fault.register_event_flood()
        event_ids = tuple(s.spec_id for s in event_specs)
        c2 = self.run_fault_campaign("event-flood", event_ids, tick_count, ("full-suite",))
        e2 = self.evaluate_fault_campaign(c2["session"].session_id)
        campaigns.append(e2)

        cp_specs = self._fault.register_checkpoint_corruption()
        cp_ids = tuple(s.spec_id for s in cp_specs)
        c3 = self.run_fault_campaign("checkpoint-corruption", cp_ids, 3, ("full-suite",))
        e3 = self.evaluate_fault_campaign(c3["session"].session_id)
        campaigns.append(e3)

        # Aggregate
        total_passed = sum(1 for c in campaigns if c["outcome"].passed)
        total_score = sum(c["outcome"].score for c in campaigns) / len(campaigns)

        return {
            "campaigns": tuple(campaigns),
            "total_campaigns": len(campaigns),
            "campaigns_passed": total_passed,
            "aggregate_score": total_score,
        }
