"""Purpose: work campaign integration bridge.
Governance scope: composing communication, artifacts, identities, obligations,
    workflows, connectors, memory, governance, and supervisor into campaign runs.
Dependencies: work_campaign engine, event_spine, memory_mesh, commitment_extraction,
    adapter_integration, external_connectors, core invariants.
Invariants:
  - Every campaign operation emits events.
  - Campaign state is attached to memory mesh and operational graph.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from ..contracts.work_campaign import (
    CampaignClosureReport,
    CampaignDescriptor,
    CampaignPriority,
    CampaignRun,
    CampaignStatus,
    CampaignStep,
    CampaignStepStatus,
    CampaignStepType,
    CampaignTrigger,
)
from ..contracts.event import EventRecord, EventSource, EventType
from ..contracts.memory_mesh import (
    MemoryRecord,
    MemoryScope,
    MemoryTrustLevel,
    MemoryType,
)
from .work_campaign import WorkCampaignEngine
from .event_spine import EventSpineEngine
from .memory_mesh import MemoryMeshEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-cint", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class WorkCampaignIntegration:
    """Integration bridge that composes all platform layers into campaign runs."""

    def __init__(
        self,
        campaign_engine: WorkCampaignEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(campaign_engine, WorkCampaignEngine):
            raise RuntimeCoreInvariantError(
                "campaign_engine must be a WorkCampaignEngine"
            )
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError(
                "event_spine must be an EventSpineEngine"
            )
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError(
                "memory_engine must be a MemoryMeshEngine"
            )
        self._campaigns = campaign_engine
        self._events = event_spine
        self._memory = memory_engine

    # ------------------------------------------------------------------
    # Campaign lifecycle
    # ------------------------------------------------------------------

    def run_campaign(
        self, campaign_id: str, context: dict[str, Any] | None = None,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        """Start and execute a full campaign run."""
        run = self._campaigns.start_run(campaign_id, run_id)

        self._attach_to_memory(run, "campaign_started")

        records = self._campaigns.execute_all_steps(run.run_id, context)
        final_run = self._campaigns.get_run(run.run_id)
        report = self._campaigns.get_closure_report(run.run_id)

        if report:
            self._attach_closure_to_memory(report)

        return {
            "run": final_run,
            "records": records,
            "closure_report": report,
        }

    def resume_campaign(
        self, run_id: str, context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Resume a paused/waiting/escalated campaign."""
        self._campaigns.resume_run(run_id)
        records = self._campaigns.execute_all_steps(run_id, context)
        final_run = self._campaigns.get_run(run_id)
        report = self._campaigns.get_closure_report(run_id)

        _emit(self._events, "campaign_resumed_via_integration", {
            "run_id": run_id,
            "steps_executed": len(records),
        }, run_id)

        return {
            "run": final_run,
            "records": records,
            "closure_report": report,
        }

    def pause_campaign(self, run_id: str) -> CampaignRun:
        """Pause a campaign run."""
        paused = self._campaigns.pause_run(run_id)
        self._attach_to_memory(paused, "campaign_paused")
        return paused

    def abort_campaign(self, run_id: str, reason: str = "") -> dict[str, Any]:
        """Abort a campaign run."""
        aborted = self._campaigns.abort_run(run_id, reason)
        report = self._campaigns.get_closure_report(run_id)

        self._attach_to_memory(aborted, "campaign_aborted")
        if report:
            self._attach_closure_to_memory(report)

        return {"run": aborted, "closure_report": report}

    # ------------------------------------------------------------------
    # Campaign creation from platform events
    # ------------------------------------------------------------------

    def campaign_from_commitments(
        self, campaign_id: str, name: str,
        commitments: list[dict[str, Any]],
        *,
        owner_id: str = "",
        priority: CampaignPriority = CampaignPriority.NORMAL,
    ) -> CampaignDescriptor:
        """Create a campaign from extracted commitments."""
        steps: list[CampaignStep] = []
        for i, c in enumerate(commitments):
            steps.append(CampaignStep(
                step_id=f"{campaign_id}-step-{i}",
                campaign_id=campaign_id,
                step_type=CampaignStepType.CREATE_OBLIGATION,
                status=CampaignStepStatus.PENDING,
                order=i,
                name="Create obligation",
                input_payload=c,
            ))
        # Final close step
        steps.append(CampaignStep(
            step_id=f"{campaign_id}-close",
            campaign_id=campaign_id,
            step_type=CampaignStepType.CLOSE,
            status=CampaignStepStatus.PENDING,
            order=len(commitments),
            name="Close campaign",
        ))

        return self._campaigns.register_campaign(
            campaign_id, name, steps,
            priority=priority,
            trigger=CampaignTrigger.COMMITMENT_EXTRACTED,
            owner_id=owner_id,
        )

    def campaign_from_artifact(
        self, campaign_id: str, name: str,
        artifact_ref: str,
        *,
        owner_id: str = "",
    ) -> CampaignDescriptor:
        """Create a campaign from an ingested artifact."""
        steps = [
            CampaignStep(
                step_id=f"{campaign_id}-ingest",
                campaign_id=campaign_id,
                step_type=CampaignStepType.INGEST_ARTIFACT,
                order=0,
                name="Ingest artifact",
                target_ref=artifact_ref,
            ),
            CampaignStep(
                step_id=f"{campaign_id}-extract",
                campaign_id=campaign_id,
                step_type=CampaignStepType.EXTRACT_COMMITMENTS,
                order=1,
                name="Extract commitments from artifact",
            ),
            CampaignStep(
                step_id=f"{campaign_id}-close",
                campaign_id=campaign_id,
                step_type=CampaignStepType.CLOSE,
                order=2,
                name="Close campaign",
            ),
        ]
        return self._campaigns.register_campaign(
            campaign_id, name, steps,
            trigger=CampaignTrigger.ARTIFACT_INGESTED,
            trigger_ref_id=artifact_ref,
            owner_id=owner_id,
        )

    def campaign_from_incident(
        self, campaign_id: str, name: str,
        incident_ref: str,
        escalation_chain: list[str],
        *,
        priority: CampaignPriority = CampaignPriority.URGENT,
    ) -> CampaignDescriptor:
        """Create a campaign from an incident."""
        steps: list[CampaignStep] = []
        steps.append(CampaignStep(
            step_id=f"{campaign_id}-classify",
            campaign_id=campaign_id,
            step_type=CampaignStepType.CHECK_CONDITION,
            order=0,
            name="Classify incident severity",
            target_ref=incident_ref,
        ))
        for i, identity in enumerate(escalation_chain):
            steps.append(CampaignStep(
                step_id=f"{campaign_id}-route-{i}",
                campaign_id=campaign_id,
                step_type=CampaignStepType.ROUTE_TO_IDENTITY,
                order=i + 1,
                name="Route to identity",
                target_ref=identity,
            ))
        steps.append(CampaignStep(
            step_id=f"{campaign_id}-escalate",
            campaign_id=campaign_id,
            step_type=CampaignStepType.ESCALATE,
            order=len(escalation_chain) + 1,
            name="Escalate if unresolved",
        ))
        steps.append(CampaignStep(
            step_id=f"{campaign_id}-close",
            campaign_id=campaign_id,
            step_type=CampaignStepType.CLOSE,
            order=len(escalation_chain) + 2,
            name="Close incident campaign",
        ))
        return self._campaigns.register_campaign(
            campaign_id, name, steps,
            priority=priority,
            trigger=CampaignTrigger.INCIDENT_DETECTED,
            trigger_ref_id=incident_ref,
        )

    def campaign_from_domain_pack(
        self, campaign_id: str, name: str,
        domain_pack_id: str,
        steps: list[CampaignStep],
    ) -> CampaignDescriptor:
        """Create a campaign from a domain pack specification."""
        return self._campaigns.register_campaign(
            campaign_id, name, steps,
            trigger=CampaignTrigger.DOMAIN_PACK,
            domain_pack_id=domain_pack_id,
        )

    # ------------------------------------------------------------------
    # Memory mesh attachment
    # ------------------------------------------------------------------

    def _attach_to_memory(
        self, run: CampaignRun, event_type: str,
    ) -> MemoryRecord:
        now = _now_iso()
        mem = MemoryRecord(
            memory_id=stable_identifier("mem-camp", {
                "rid": run.run_id, "event": event_type, "ts": now,
            }),
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            scope_ref_id=run.campaign_id,
            trust_level=MemoryTrustLevel.VERIFIED,
            title="Campaign state",
            content={
                "run_id": run.run_id,
                "campaign_id": run.campaign_id,
                "status": run.status.value,
                "event": event_type,
            },
            source_ids=(run.campaign_id,),
            tags=("campaign", event_type),
            confidence=1.0,
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(mem)
        return mem

    def _attach_closure_to_memory(
        self, report: CampaignClosureReport,
    ) -> MemoryRecord:
        now = _now_iso()
        mem = MemoryRecord(
            memory_id=stable_identifier("mem-camp-closure", {
                "rid": report.run_id, "ts": now,
            }),
            memory_type=MemoryType.ARTIFACT,
            scope=MemoryScope.GLOBAL,
            scope_ref_id=report.campaign_id,
            trust_level=MemoryTrustLevel.VERIFIED,
            title="Campaign closure",
            content={
                "run_id": report.run_id,
                "campaign_id": report.campaign_id,
                "verdict": report.outcome.value,
                "completed_steps": report.completed_steps,
                "total_steps": report.total_steps,
                "summary": report.summary,
            },
            source_ids=(report.campaign_id,),
            tags=("campaign", "closure", report.outcome.value),
            confidence=1.0,
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(mem)
        return mem

    def attach_campaign_to_memory_mesh(
        self, run_id: str,
    ) -> MemoryRecord:
        """Explicitly attach current campaign state to memory mesh."""
        run = self._campaigns.get_run(run_id)
        return self._attach_to_memory(run, "manual_snapshot")

    def attach_campaign_to_supervisor(
        self, run_id: str,
    ) -> dict[str, Any]:
        """Return campaign state suitable for supervisor tick consumption."""
        run = self._campaigns.get_run(run_id)
        desc = self._campaigns.get_campaign(run.campaign_id)
        ckpt = self._campaigns.checkpoint(run_id)
        escalations = self._campaigns.get_escalations(run_id)

        return {
            "run_id": run_id,
            "campaign_id": run.campaign_id,
            "name": desc.name,
            "status": run.status.value,
            "priority": desc.priority.value,
            "current_step_index": run.current_step_index,
            "checkpoint": ckpt,
            "escalation_count": len(escalations),
            "is_blocked": run.status in (
                CampaignStatus.WAITING,
                CampaignStatus.ESCALATED,
                CampaignStatus.PAUSED,
            ),
        }
