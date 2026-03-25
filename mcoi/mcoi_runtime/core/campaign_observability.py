"""Purpose: campaign observability engine.
Governance scope: operator-grade visibility into campaign lifecycle,
    blocked/waiting/overdue/degraded campaigns, closure reports,
    and campaign lineage in memory/graph.
Dependencies: work_campaign engine, event_spine, memory_mesh, core invariants.
Invariants:
  - All queries return immutable results.
  - Every observation emits an event.
  - Overdue detection is deterministic given a cutoff.
  - Lineage traces full campaign ancestry.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..contracts.work_campaign import (
    CampaignClosureReport,
    CampaignDescriptor,
    CampaignEscalation,
    CampaignOutcomeVerdict,
    CampaignPriority,
    CampaignRun,
    CampaignStatus,
    CampaignStepStatus,
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
        event_id=stable_identifier("evt-cobs", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class CampaignObservabilityEngine:
    """Operator-grade visibility into campaign lifecycle and health."""

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
    # Active campaigns
    # ------------------------------------------------------------------

    def active_campaigns(self) -> tuple[CampaignDescriptor, ...]:
        """Return all campaigns with at least one active run."""
        active_runs = self._campaigns.list_runs(status=CampaignStatus.ACTIVE)
        seen: set[str] = set()
        result: list[CampaignDescriptor] = []
        for run in active_runs:
            if run.campaign_id not in seen:
                seen.add(run.campaign_id)
                result.append(self._campaigns.get_campaign(run.campaign_id))
        return tuple(sorted(result, key=lambda c: c.campaign_id))

    def active_runs(self) -> tuple[CampaignRun, ...]:
        """Return all active runs."""
        return self._campaigns.list_runs(status=CampaignStatus.ACTIVE)

    # ------------------------------------------------------------------
    # Blocked campaigns
    # ------------------------------------------------------------------

    def blocked_campaigns(self) -> tuple[dict[str, Any], ...]:
        """Return campaigns blocked by escalation, waiting, or pause."""
        blocked_statuses = (
            CampaignStatus.PAUSED,
            CampaignStatus.WAITING,
            CampaignStatus.ESCALATED,
        )
        result: list[dict[str, Any]] = []
        for status in blocked_statuses:
            for run in self._campaigns.list_runs(status=status):
                desc = self._campaigns.get_campaign(run.campaign_id)
                escalations = self._campaigns.get_escalations(run.run_id)
                result.append({
                    "run_id": run.run_id,
                    "campaign_id": run.campaign_id,
                    "campaign_name": desc.name,
                    "status": run.status.value,
                    "priority": desc.priority.value,
                    "current_step_index": run.current_step_index,
                    "escalation_count": len(escalations),
                    "started_at": run.started_at,
                })
        return tuple(sorted(result, key=lambda r: r["run_id"]))

    # ------------------------------------------------------------------
    # Waiting-on-human campaigns
    # ------------------------------------------------------------------

    def waiting_campaigns(self) -> tuple[dict[str, Any], ...]:
        """Return campaigns waiting for human response."""
        runs = self._campaigns.list_runs(status=CampaignStatus.WAITING)
        result: list[dict[str, Any]] = []
        for run in runs:
            desc = self._campaigns.get_campaign(run.campaign_id)
            # Find the waiting step
            waiting_step_id = ""
            waiting_step_name = ""
            steps = self._campaigns.get_steps(run.campaign_id)
            for step in steps:
                run_step = self._campaigns.get_run_step(run.run_id, step.step_id)
                if run_step.status == CampaignStepStatus.WAITING:
                    waiting_step_id = run_step.step_id
                    waiting_step_name = run_step.name
                    break
            result.append({
                "run_id": run.run_id,
                "campaign_id": run.campaign_id,
                "campaign_name": desc.name,
                "priority": desc.priority.value,
                "waiting_step_id": waiting_step_id,
                "waiting_step_name": waiting_step_name,
                "started_at": run.started_at,
            })
        return tuple(sorted(result, key=lambda r: r["run_id"]))

    # ------------------------------------------------------------------
    # Overdue campaigns
    # ------------------------------------------------------------------

    def overdue_campaigns(
        self, max_age_seconds: int = 86400,
    ) -> tuple[dict[str, Any], ...]:
        """Return campaigns that have been running longer than max_age_seconds."""
        now = datetime.now(timezone.utc)
        non_terminal = (
            CampaignStatus.ACTIVE,
            CampaignStatus.PAUSED,
            CampaignStatus.WAITING,
            CampaignStatus.ESCALATED,
        )
        result: list[dict[str, Any]] = []
        for status in non_terminal:
            for run in self._campaigns.list_runs(status=status):
                if not run.started_at:
                    continue
                try:
                    started = datetime.fromisoformat(run.started_at)
                except (ValueError, TypeError):
                    continue
                elapsed = (now - started).total_seconds()
                if elapsed > max_age_seconds:
                    desc = self._campaigns.get_campaign(run.campaign_id)
                    result.append({
                        "run_id": run.run_id,
                        "campaign_id": run.campaign_id,
                        "campaign_name": desc.name,
                        "status": run.status.value,
                        "priority": desc.priority.value,
                        "elapsed_seconds": elapsed,
                        "max_age_seconds": max_age_seconds,
                        "started_at": run.started_at,
                    })
        return tuple(sorted(result, key=lambda r: r["run_id"]))

    # ------------------------------------------------------------------
    # Degraded campaigns (escalated or with failures)
    # ------------------------------------------------------------------

    def degraded_campaigns(self) -> tuple[dict[str, Any], ...]:
        """Return campaigns in degraded mode (escalated or with step failures)."""
        result: list[dict[str, Any]] = []
        seen: set[str] = set()

        # Escalated runs
        for run in self._campaigns.list_runs(status=CampaignStatus.ESCALATED):
            if run.run_id in seen:
                continue
            seen.add(run.run_id)
            desc = self._campaigns.get_campaign(run.campaign_id)
            escalations = self._campaigns.get_escalations(run.run_id)
            result.append({
                "run_id": run.run_id,
                "campaign_id": run.campaign_id,
                "campaign_name": desc.name,
                "status": run.status.value,
                "priority": desc.priority.value,
                "escalation_count": len(escalations),
                "degradation_reason": "escalated",
            })

        # Active runs with failed steps
        for run in self._campaigns.list_runs(status=CampaignStatus.ACTIVE):
            if run.run_id in seen:
                continue
            records = self._campaigns.get_execution_records(run.run_id)
            failed_count = sum(1 for r in records if not r.success)
            if failed_count > 0:
                seen.add(run.run_id)
                desc = self._campaigns.get_campaign(run.campaign_id)
                result.append({
                    "run_id": run.run_id,
                    "campaign_id": run.campaign_id,
                    "campaign_name": desc.name,
                    "status": run.status.value,
                    "priority": desc.priority.value,
                    "escalation_count": 0,
                    "degradation_reason": "step_failures",
                    "failed_step_count": failed_count,
                })

        return tuple(sorted(result, key=lambda r: r["run_id"]))

    # ------------------------------------------------------------------
    # Closure reports
    # ------------------------------------------------------------------

    def all_closure_reports(self) -> tuple[CampaignClosureReport, ...]:
        """Return all closure reports across all runs."""
        reports: list[CampaignClosureReport] = []
        for run in self._campaigns.list_runs():
            report = self._campaigns.get_closure_report(run.run_id)
            if report is not None:
                reports.append(report)
        return tuple(sorted(reports, key=lambda r: r.run_id))

    def closure_reports_by_verdict(
        self, verdict: CampaignOutcomeVerdict,
    ) -> tuple[CampaignClosureReport, ...]:
        """Return closure reports filtered by outcome verdict."""
        return tuple(
            r for r in self.all_closure_reports() if r.outcome == verdict
        )

    # ------------------------------------------------------------------
    # Campaign lineage
    # ------------------------------------------------------------------

    def campaign_lineage(self, campaign_id: str) -> dict[str, Any]:
        """Return full lineage for a campaign: descriptor, runs, checkpoints, escalations, closures."""
        desc = self._campaigns.get_campaign(campaign_id)
        runs = self._campaigns.list_runs(campaign_id)

        lineage_runs: list[dict[str, Any]] = []
        for run in runs:
            ckpt = self._campaigns.get_checkpoint(run.run_id)
            escalations = self._campaigns.get_escalations(run.run_id)
            report = self._campaigns.get_closure_report(run.run_id)
            records = self._campaigns.get_execution_records(run.run_id)

            lineage_runs.append({
                "run_id": run.run_id,
                "status": run.status.value,
                "started_at": run.started_at,
                "completed_at": run.completed_at,
                "current_step_index": run.current_step_index,
                "checkpoint": ckpt,
                "escalation_count": len(escalations),
                "execution_record_count": len(records),
                "closure_report": report,
            })

        return {
            "campaign_id": campaign_id,
            "name": desc.name,
            "status": desc.status.value,
            "priority": desc.priority.value,
            "trigger": desc.trigger.value,
            "owner_id": desc.owner_id,
            "step_count": desc.step_count,
            "runs": lineage_runs,
            "total_runs": len(lineage_runs),
        }

    def campaign_lineage_to_memory(self, campaign_id: str) -> MemoryRecord:
        """Persist campaign lineage as a memory record."""
        lineage = self.campaign_lineage(campaign_id)
        now = _now_iso()

        # Simplify for memory storage (strip non-serializable objects)
        simplified_runs = []
        for r in lineage["runs"]:
            simplified_runs.append({
                "run_id": r["run_id"],
                "status": r["status"],
                "started_at": r["started_at"],
                "completed_at": r["completed_at"],
                "escalation_count": r["escalation_count"],
                "execution_record_count": r["execution_record_count"],
                "has_closure": r["closure_report"] is not None,
            })

        mem = MemoryRecord(
            memory_id=stable_identifier("mem-lineage", {
                "cid": campaign_id, "ts": now,
            }),
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            scope_ref_id=campaign_id,
            trust_level=MemoryTrustLevel.VERIFIED,
            title=f"Campaign lineage: {campaign_id}",
            content={
                "campaign_id": lineage["campaign_id"],
                "name": lineage["name"],
                "status": lineage["status"],
                "priority": lineage["priority"],
                "trigger": lineage["trigger"],
                "total_runs": lineage["total_runs"],
                "runs": simplified_runs,
            },
            source_ids=(campaign_id,),
            tags=("campaign", "lineage"),
            confidence=1.0,
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(mem)

        _emit(self._events, "campaign_lineage_persisted", {
            "campaign_id": campaign_id,
            "total_runs": lineage["total_runs"],
        }, campaign_id)

        return mem

    # ------------------------------------------------------------------
    # Dashboard summary
    # ------------------------------------------------------------------

    def dashboard_summary(self) -> dict[str, Any]:
        """Return a high-level dashboard summary of all campaigns."""
        all_runs = self._campaigns.list_runs()
        all_campaigns = self._campaigns.list_campaigns()

        status_counts: dict[str, int] = {}
        for run in all_runs:
            key = run.status.value
            status_counts[key] = status_counts.get(key, 0) + 1

        priority_counts: dict[str, int] = {}
        for camp in all_campaigns:
            key = camp.priority.value
            priority_counts[key] = priority_counts.get(key, 0) + 1

        reports = self.all_closure_reports()
        verdict_counts: dict[str, int] = {}
        for r in reports:
            key = r.outcome.value
            verdict_counts[key] = verdict_counts.get(key, 0) + 1

        return {
            "total_campaigns": len(all_campaigns),
            "total_runs": len(all_runs),
            "runs_by_status": status_counts,
            "campaigns_by_priority": priority_counts,
            "total_closure_reports": len(reports),
            "closures_by_verdict": verdict_counts,
            "active_count": status_counts.get("active", 0),
            "blocked_count": (
                status_counts.get("paused", 0)
                + status_counts.get("waiting", 0)
                + status_counts.get("escalated", 0)
            ),
        }
