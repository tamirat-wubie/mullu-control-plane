"""Purpose: work campaign engine.
Governance scope: instantiating campaign runs, executing steps under governance,
    persisting state, checkpointing progress, pause/resume/retry/escalate/abort,
    dependency ordering, and producing immutable closure reports.
Dependencies: work_campaign contracts, event_spine, core invariants.
Invariants:
  - No duplicate campaign or run IDs.
  - Steps execute in dependency/order sequence.
  - Every step execution emits an execution record.
  - Checkpoints capture full state.
  - Closure reports are immutable.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Callable, Mapping

from ..contracts.work_campaign import (
    CampaignCheckpoint,
    CampaignClosureReport,
    CampaignDependency,
    CampaignDescriptor,
    CampaignEscalation,
    CampaignEscalationReason,
    CampaignExecutionRecord,
    CampaignOutcome,
    CampaignOutcomeVerdict,
    CampaignPriority,
    CampaignRun,
    CampaignStatus,
    CampaignStep,
    CampaignStepStatus,
    CampaignStepType,
    CampaignTrigger,
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
        event_id=stable_identifier("evt-camp", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


# Step handler type: receives step + context, returns (success, output_payload)
StepHandler = Callable[
    [CampaignStep, dict[str, Any]],
    tuple[bool, dict[str, Any]],
]

_TERMINAL_STATUSES = frozenset({
    CampaignStatus.COMPLETED,
    CampaignStatus.FAILED,
    CampaignStatus.ABORTED,
})


class WorkCampaignEngine:
    """Core engine for instantiating and executing work campaigns."""

    def __init__(self, event_spine: EventSpineEngine) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError(
                "event_spine must be an EventSpineEngine"
            )
        self._events = event_spine
        self._campaigns: dict[str, CampaignDescriptor] = {}
        self._steps: dict[str, list[CampaignStep]] = {}  # campaign_id -> steps
        self._dependencies: dict[str, list[CampaignDependency]] = {}
        self._runs: dict[str, CampaignRun] = {}  # run_id -> run
        self._run_steps: dict[str, dict[str, CampaignStep]] = {}  # run_id -> {step_id -> step}
        self._checkpoints: dict[str, CampaignCheckpoint] = {}  # run_id -> latest
        self._execution_records: list[CampaignExecutionRecord] = []
        self._escalations: list[CampaignEscalation] = []
        self._closure_reports: dict[str, CampaignClosureReport] = {}  # run_id -> report
        self._step_handlers: dict[CampaignStepType, StepHandler] = {}
        self._counters: dict[str, dict[str, int]] = {}  # run_id -> counters

    # ------------------------------------------------------------------
    # Step handler registration
    # ------------------------------------------------------------------

    def register_step_handler(
        self, step_type: CampaignStepType, handler: StepHandler,
    ) -> None:
        """Register a handler for a step type."""
        if not isinstance(step_type, CampaignStepType):
            raise RuntimeCoreInvariantError(
                "step_type must be a CampaignStepType"
            )
        self._step_handlers[step_type] = handler

    # ------------------------------------------------------------------
    # Campaign registration
    # ------------------------------------------------------------------

    def register_campaign(
        self,
        campaign_id: str,
        name: str,
        steps: list[CampaignStep],
        *,
        priority: CampaignPriority = CampaignPriority.NORMAL,
        trigger: CampaignTrigger = CampaignTrigger.MANUAL,
        trigger_ref_id: str = "",
        owner_id: str = "",
        domain_pack_id: str = "",
        tags: tuple[str, ...] = (),
        dependencies: list[CampaignDependency] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CampaignDescriptor:
        if campaign_id in self._campaigns:
            raise RuntimeCoreInvariantError(
                f"campaign '{campaign_id}' already registered"
            )
        now = _now_iso()
        desc = CampaignDescriptor(
            campaign_id=campaign_id,
            name=name,
            status=CampaignStatus.DRAFT,
            priority=priority,
            trigger=trigger,
            trigger_ref_id=trigger_ref_id,
            owner_id=owner_id,
            domain_pack_id=domain_pack_id,
            step_count=len(steps),
            tags=tags,
            created_at=now,
            metadata=metadata or {},
        )
        self._campaigns[campaign_id] = desc
        self._steps[campaign_id] = sorted(steps, key=lambda s: s.order)
        self._dependencies[campaign_id] = list(dependencies or [])

        _emit(self._events, "campaign_registered", {
            "campaign_id": campaign_id,
            "name": name,
            "step_count": len(steps),
            "priority": priority.value,
        }, campaign_id)

        return desc

    def get_campaign(self, campaign_id: str) -> CampaignDescriptor:
        if campaign_id not in self._campaigns:
            raise RuntimeCoreInvariantError(
                f"campaign '{campaign_id}' not found"
            )
        return self._campaigns[campaign_id]

    def get_steps(self, campaign_id: str) -> tuple[CampaignStep, ...]:
        if campaign_id not in self._steps:
            raise RuntimeCoreInvariantError(
                f"campaign '{campaign_id}' not found"
            )
        return tuple(self._steps[campaign_id])

    # ------------------------------------------------------------------
    # Campaign runs
    # ------------------------------------------------------------------

    def start_run(
        self, campaign_id: str, run_id: str | None = None,
    ) -> CampaignRun:
        """Start a new run of a campaign."""
        if campaign_id not in self._campaigns:
            raise RuntimeCoreInvariantError(
                f"campaign '{campaign_id}' not found"
            )
        now = _now_iso()
        rid = run_id or stable_identifier("run", {
            "cid": campaign_id, "ts": now,
        })
        if rid in self._runs:
            raise RuntimeCoreInvariantError(f"run '{rid}' already exists")

        run = CampaignRun(
            run_id=rid,
            campaign_id=campaign_id,
            status=CampaignStatus.ACTIVE,
            started_at=now,
        )
        self._runs[rid] = run

        # Copy steps for this run
        self._run_steps[rid] = {
            s.step_id: s for s in self._steps[campaign_id]
        }
        self._counters[rid] = {
            "obligations_created": 0,
            "messages_sent": 0,
            "artifacts_processed": 0,
            "connector_calls": 0,
            "retries": 0,
        }

        # Update campaign status
        desc = self._campaigns[campaign_id]
        self._campaigns[campaign_id] = CampaignDescriptor(
            campaign_id=desc.campaign_id,
            name=desc.name,
            description=desc.description,
            status=CampaignStatus.ACTIVE,
            priority=desc.priority,
            trigger=desc.trigger,
            trigger_ref_id=desc.trigger_ref_id,
            owner_id=desc.owner_id,
            domain_pack_id=desc.domain_pack_id,
            step_count=desc.step_count,
            tags=desc.tags,
            created_at=desc.created_at,
            metadata=dict(desc.metadata),
        )

        _emit(self._events, "campaign_run_started", {
            "campaign_id": campaign_id,
            "run_id": rid,
        }, rid)

        return run

    def get_run(self, run_id: str) -> CampaignRun:
        if run_id not in self._runs:
            raise RuntimeCoreInvariantError(f"run '{run_id}' not found")
        return self._runs[run_id]

    # ------------------------------------------------------------------
    # Step execution
    # ------------------------------------------------------------------

    def execute_next_step(
        self, run_id: str, context: dict[str, Any] | None = None,
    ) -> CampaignExecutionRecord | None:
        """Execute the next pending step in a run."""
        run = self.get_run(run_id)
        if run.status in _TERMINAL_STATUSES:
            return None
        if run.status == CampaignStatus.PAUSED:
            return None

        steps = self._steps[run.campaign_id]
        ctx = context or {}

        # Find next pending step (respecting order and dependencies)
        for step in steps:
            run_step = self._run_steps[run_id].get(step.step_id, step)
            if run_step.status != CampaignStepStatus.PENDING:
                continue

            # Check dependencies
            if not self._deps_satisfied(run_id, step.step_id, run.campaign_id):
                continue

            return self._execute_step(run_id, run_step, ctx)

        # No more steps — campaign is done
        self._complete_run(run_id)
        return None

    def execute_all_steps(
        self, run_id: str, context: dict[str, Any] | None = None,
    ) -> tuple[CampaignExecutionRecord, ...]:
        """Execute all remaining steps in order."""
        records: list[CampaignExecutionRecord] = []
        while True:
            record = self.execute_next_step(run_id, context)
            if record is None:
                break
            records.append(record)
            # Stop if run entered terminal or waiting state
            run = self._runs[run_id]
            if run.status in _TERMINAL_STATUSES or run.status == CampaignStatus.WAITING:
                break
        return tuple(records)

    def _execute_step(
        self, run_id: str, step: CampaignStep, context: dict[str, Any],
    ) -> CampaignExecutionRecord:
        """Execute a single step."""
        now = _now_iso()
        run = self._runs[run_id]

        # Mark step active
        active_step = CampaignStep(
            step_id=step.step_id,
            campaign_id=step.campaign_id,
            step_type=step.step_type,
            status=CampaignStepStatus.ACTIVE,
            order=step.order,
            name=step.name,
            description=step.description,
            target_ref=step.target_ref,
            input_payload=dict(step.input_payload),
            retry_count=step.retry_count,
            max_retries=step.max_retries,
            timeout_seconds=step.timeout_seconds,
            started_at=now,
            tags=step.tags,
            metadata=dict(step.metadata),
        )
        self._run_steps[run_id][step.step_id] = active_step

        # Update run position
        step_index = next(
            (i for i, s in enumerate(self._steps[run.campaign_id])
             if s.step_id == step.step_id), 0
        )
        self._runs[run_id] = CampaignRun(
            run_id=run.run_id,
            campaign_id=run.campaign_id,
            status=CampaignStatus.ACTIVE,
            current_step_index=step_index,
            started_at=run.started_at,
            retry_count=run.retry_count,
            metadata=dict(run.metadata),
        )

        # Execute via handler
        handler = self._step_handlers.get(step.step_type)
        success = False
        output: dict[str, Any] = {}
        error_msg = ""

        if handler:
            try:
                success, output = handler(active_step, context)
                # Track counters
                self._track_counters(run_id, step.step_type, success)
            except Exception as exc:
                error_msg = str(exc)
                success = False
        else:
            # Default: auto-succeed for unhandled step types
            success = True
            output = {"auto": True}

        # Determine step outcome
        if success:
            final_status = CampaignStepStatus.COMPLETED
        elif step.retry_count < step.max_retries:
            final_status = CampaignStepStatus.RETRYING
            self._counters[run_id]["retries"] += 1
        else:
            final_status = CampaignStepStatus.FAILED

        # Handle WAIT_FOR_REPLY — mark as waiting
        if step.step_type == CampaignStepType.WAIT_FOR_REPLY and success:
            final_status = CampaignStepStatus.WAITING
            self._runs[run_id] = CampaignRun(
                run_id=run.run_id,
                campaign_id=run.campaign_id,
                status=CampaignStatus.WAITING,
                current_step_index=step_index,
                started_at=run.started_at,
                retry_count=run.retry_count,
                metadata=dict(run.metadata),
            )

        completed_at = _now_iso()
        final_step = CampaignStep(
            step_id=step.step_id,
            campaign_id=step.campaign_id,
            step_type=step.step_type,
            status=final_status,
            order=step.order,
            name=step.name,
            description=step.description,
            target_ref=step.target_ref,
            input_payload=dict(step.input_payload),
            output_payload=output,
            retry_count=step.retry_count + (1 if final_status == CampaignStepStatus.RETRYING else 0),
            max_retries=step.max_retries,
            timeout_seconds=step.timeout_seconds,
            started_at=active_step.started_at,
            completed_at=completed_at if final_status != CampaignStepStatus.RETRYING else "",
            error_message=error_msg,
            tags=step.tags,
            metadata=dict(step.metadata),
        )
        self._run_steps[run_id][step.step_id] = final_step

        # If step failed terminally, check if campaign should fail
        if final_status == CampaignStepStatus.FAILED:
            self._handle_step_failure(run_id, final_step)

        # Create execution record
        record = CampaignExecutionRecord(
            record_id=stable_identifier("exec-camp", {
                "rid": run_id, "sid": step.step_id, "ts": completed_at,
            }),
            campaign_id=run.campaign_id,
            run_id=run_id,
            step_id=step.step_id,
            step_type=step.step_type,
            success=success,
            input_summary=step.name,
            output_summary=str(output)[:200] if output else "",
            error_message=error_msg,
            executed_at=completed_at,
        )
        self._execution_records.append(record)

        _emit(self._events, "campaign_step_executed", {
            "campaign_id": run.campaign_id,
            "run_id": run_id,
            "step_id": step.step_id,
            "step_type": step.step_type.value,
            "success": success,
        }, run_id)

        return record

    def _track_counters(
        self, run_id: str, step_type: CampaignStepType, success: bool,
    ) -> None:
        counters = self._counters[run_id]
        if step_type == CampaignStepType.SEND_COMMUNICATION and success:
            counters["messages_sent"] += 1
        elif step_type == CampaignStepType.INGEST_ARTIFACT and success:
            counters["artifacts_processed"] += 1
        elif step_type == CampaignStepType.CREATE_OBLIGATION and success:
            counters["obligations_created"] += 1
        elif step_type == CampaignStepType.CALL_CONNECTOR:
            counters["connector_calls"] += 1

    def _deps_satisfied(
        self, run_id: str, step_id: str, campaign_id: str,
    ) -> bool:
        """Check if all required dependencies are satisfied."""
        deps = self._dependencies.get(campaign_id, [])
        for dep in deps:
            if dep.target_step_id != step_id:
                continue
            source = self._run_steps[run_id].get(dep.source_step_id)
            if source is None:
                if dep.required:
                    return False
                continue
            if dep.required and source.status != CampaignStepStatus.COMPLETED:
                return False
        return True

    def _handle_step_failure(
        self, run_id: str, step: CampaignStep,
    ) -> None:
        """Handle a terminal step failure — escalate or fail campaign."""
        run = self._runs[run_id]

        # Check if step type should trigger escalation
        if step.step_type in (
            CampaignStepType.SEND_COMMUNICATION,
            CampaignStepType.REQUEST_APPROVAL,
            CampaignStepType.CALL_CONNECTOR,
        ):
            self._escalate(
                run_id, step,
                CampaignEscalationReason.STEP_FAILURE,
                f"Step '{step.name}' failed: {step.error_message}",
            )
        else:
            # Fail the campaign
            self._runs[run_id] = CampaignRun(
                run_id=run.run_id,
                campaign_id=run.campaign_id,
                status=CampaignStatus.FAILED,
                current_step_index=run.current_step_index,
                started_at=run.started_at,
                retry_count=run.retry_count,
                metadata=dict(run.metadata),
            )

    def _escalate(
        self, run_id: str, step: CampaignStep,
        reason: CampaignEscalationReason, description: str,
    ) -> CampaignEscalation:
        now = _now_iso()
        run = self._runs[run_id]
        esc = CampaignEscalation(
            escalation_id=stable_identifier("esc", {
                "rid": run_id, "sid": step.step_id, "ts": now,
            }),
            campaign_id=run.campaign_id,
            run_id=run_id,
            reason=reason,
            failed_step_id=step.step_id,
            description=description,
            escalated_at=now,
        )
        self._escalations.append(esc)

        self._runs[run_id] = CampaignRun(
            run_id=run.run_id,
            campaign_id=run.campaign_id,
            status=CampaignStatus.ESCALATED,
            current_step_index=run.current_step_index,
            started_at=run.started_at,
            retry_count=run.retry_count,
            metadata=dict(run.metadata),
        )

        _emit(self._events, "campaign_escalated", {
            "campaign_id": run.campaign_id,
            "run_id": run_id,
            "reason": reason.value,
            "step_id": step.step_id,
        }, run_id)

        return esc

    def _complete_run(self, run_id: str) -> None:
        """Mark a run as completed and generate closure report."""
        run = self._runs[run_id]
        now = _now_iso()

        self._runs[run_id] = CampaignRun(
            run_id=run.run_id,
            campaign_id=run.campaign_id,
            status=CampaignStatus.COMPLETED,
            current_step_index=run.current_step_index,
            started_at=run.started_at,
            completed_at=now,
            retry_count=run.retry_count,
            metadata=dict(run.metadata),
        )

        self._generate_closure_report(run_id)

    # ------------------------------------------------------------------
    # Pause / resume / abort
    # ------------------------------------------------------------------

    def pause_run(self, run_id: str) -> CampaignRun:
        run = self.get_run(run_id)
        if run.status in _TERMINAL_STATUSES:
            raise RuntimeCoreInvariantError(
                f"cannot pause run in terminal status '{run.status.value}'"
            )
        now = _now_iso()
        paused = CampaignRun(
            run_id=run.run_id,
            campaign_id=run.campaign_id,
            status=CampaignStatus.PAUSED,
            current_step_index=run.current_step_index,
            started_at=run.started_at,
            paused_at=now,
            retry_count=run.retry_count,
            metadata=dict(run.metadata),
        )
        self._runs[run_id] = paused
        self._checkpoint(run_id)

        _emit(self._events, "campaign_paused", {
            "campaign_id": run.campaign_id,
            "run_id": run_id,
        }, run_id)

        return paused

    def resume_run(self, run_id: str) -> CampaignRun:
        run = self.get_run(run_id)
        if run.status not in (CampaignStatus.PAUSED, CampaignStatus.WAITING,
                               CampaignStatus.ESCALATED):
            raise RuntimeCoreInvariantError(
                f"cannot resume run in status '{run.status.value}'"
            )
        resumed = CampaignRun(
            run_id=run.run_id,
            campaign_id=run.campaign_id,
            status=CampaignStatus.ACTIVE,
            current_step_index=run.current_step_index,
            started_at=run.started_at,
            retry_count=run.retry_count,
            metadata=dict(run.metadata),
        )
        self._runs[run_id] = resumed

        _emit(self._events, "campaign_resumed", {
            "campaign_id": run.campaign_id,
            "run_id": run_id,
        }, run_id)

        return resumed

    def abort_run(self, run_id: str, reason: str = "") -> CampaignRun:
        run = self.get_run(run_id)
        if run.status in _TERMINAL_STATUSES:
            raise RuntimeCoreInvariantError(
                f"cannot abort run in terminal status '{run.status.value}'"
            )
        now = _now_iso()
        aborted = CampaignRun(
            run_id=run.run_id,
            campaign_id=run.campaign_id,
            status=CampaignStatus.ABORTED,
            current_step_index=run.current_step_index,
            started_at=run.started_at,
            aborted_at=now,
            retry_count=run.retry_count,
            metadata=dict(run.metadata),
        )
        self._runs[run_id] = aborted
        self._generate_closure_report(run_id)

        _emit(self._events, "campaign_aborted", {
            "campaign_id": run.campaign_id,
            "run_id": run_id,
            "reason": reason,
        }, run_id)

        return aborted

    # ------------------------------------------------------------------
    # Retry
    # ------------------------------------------------------------------

    def retry_step(
        self, run_id: str, step_id: str, context: dict[str, Any] | None = None,
    ) -> CampaignExecutionRecord | None:
        """Retry a failed or retrying step."""
        run = self.get_run(run_id)
        step = self._run_steps[run_id].get(step_id)
        if step is None:
            raise RuntimeCoreInvariantError(f"step '{step_id}' not found in run")
        if step.status not in (CampaignStepStatus.FAILED, CampaignStepStatus.RETRYING):
            raise RuntimeCoreInvariantError(
                f"cannot retry step in status '{step.status.value}'"
            )
        # Reset step to pending with incremented retry count
        reset_step = CampaignStep(
            step_id=step.step_id,
            campaign_id=step.campaign_id,
            step_type=step.step_type,
            status=CampaignStepStatus.PENDING,
            order=step.order,
            name=step.name,
            description=step.description,
            target_ref=step.target_ref,
            input_payload=dict(step.input_payload),
            retry_count=step.retry_count,
            max_retries=step.max_retries,
            timeout_seconds=step.timeout_seconds,
            tags=step.tags,
            metadata=dict(step.metadata),
        )
        self._run_steps[run_id][step_id] = reset_step

        # If campaign was failed/escalated, resume to active
        if run.status in (CampaignStatus.FAILED, CampaignStatus.ESCALATED):
            self._runs[run_id] = CampaignRun(
                run_id=run.run_id,
                campaign_id=run.campaign_id,
                status=CampaignStatus.ACTIVE,
                current_step_index=run.current_step_index,
                started_at=run.started_at,
                retry_count=run.retry_count + 1,
                metadata=dict(run.metadata),
            )

        return self._execute_step(run_id, reset_step, context or {})

    # ------------------------------------------------------------------
    # Checkpointing
    # ------------------------------------------------------------------

    def _checkpoint(self, run_id: str) -> CampaignCheckpoint:
        run = self._runs[run_id]
        now = _now_iso()

        completed_ids = tuple(
            sid for sid, s in self._run_steps[run_id].items()
            if s.status == CampaignStepStatus.COMPLETED
        )
        failed_ids = tuple(
            sid for sid, s in self._run_steps[run_id].items()
            if s.status == CampaignStepStatus.FAILED
        )
        current = None
        for sid, s in self._run_steps[run_id].items():
            if s.status in (CampaignStepStatus.ACTIVE, CampaignStepStatus.WAITING):
                current = sid
                break

        ckpt = CampaignCheckpoint(
            checkpoint_id=stable_identifier("ckpt", {
                "rid": run_id, "ts": now,
            }),
            campaign_id=run.campaign_id,
            run_id=run_id,
            status=run.status,
            current_step_id=current or "",
            completed_step_ids=completed_ids,
            failed_step_ids=failed_ids,
            created_at=now,
        )
        self._checkpoints[run_id] = ckpt
        return ckpt

    def checkpoint(self, run_id: str) -> CampaignCheckpoint:
        """Create a checkpoint for the current run state."""
        self.get_run(run_id)
        return self._checkpoint(run_id)

    def get_checkpoint(self, run_id: str) -> CampaignCheckpoint | None:
        return self._checkpoints.get(run_id)

    # ------------------------------------------------------------------
    # Closure reports
    # ------------------------------------------------------------------

    def _generate_closure_report(self, run_id: str) -> CampaignClosureReport:
        run = self._runs[run_id]
        now = _now_iso()
        steps = self._run_steps[run_id]

        completed = sum(1 for s in steps.values() if s.status == CampaignStepStatus.COMPLETED)
        failed = sum(1 for s in steps.values() if s.status == CampaignStepStatus.FAILED)
        skipped = sum(1 for s in steps.values() if s.status == CampaignStepStatus.SKIPPED)
        total = len(steps)

        # Determine verdict
        if run.status == CampaignStatus.ABORTED:
            verdict = CampaignOutcomeVerdict.ABORTED
        elif failed > 0 and completed > 0:
            verdict = CampaignOutcomeVerdict.PARTIAL_SUCCESS
        elif failed > 0:
            verdict = CampaignOutcomeVerdict.FAILURE
        elif run.status == CampaignStatus.ESCALATED:
            verdict = CampaignOutcomeVerdict.ESCALATED
        else:
            verdict = CampaignOutcomeVerdict.SUCCESS

        counters = self._counters.get(run_id, {})
        esc_count = sum(1 for e in self._escalations if e.run_id == run_id)

        step_summaries = []
        for s in sorted(steps.values(), key=lambda s: s.order):
            step_summaries.append({
                "step_id": s.step_id,
                "name": s.name,
                "type": s.step_type.value,
                "status": s.status.value,
                "error": s.error_message,
            })

        report = CampaignClosureReport(
            report_id=stable_identifier("closure", {"rid": run_id, "ts": now}),
            campaign_id=run.campaign_id,
            run_id=run_id,
            final_status=run.status,
            outcome=verdict,
            total_steps=total,
            completed_steps=completed,
            failed_steps=failed,
            skipped_steps=skipped,
            escalation_count=esc_count,
            retry_count=counters.get("retries", 0),
            obligations_created=counters.get("obligations_created", 0),
            messages_sent=counters.get("messages_sent", 0),
            artifacts_processed=counters.get("artifacts_processed", 0),
            connector_calls=counters.get("connector_calls", 0),
            summary=f"Campaign {run.campaign_id}: {verdict.value} ({completed}/{total} steps)",
            step_summaries=step_summaries,
            created_at=now,
        )
        self._closure_reports[run_id] = report

        _emit(self._events, "campaign_closure_report", {
            "campaign_id": run.campaign_id,
            "run_id": run_id,
            "verdict": verdict.value,
            "completed": completed,
            "total": total,
        }, run_id)

        return report

    def get_closure_report(self, run_id: str) -> CampaignClosureReport | None:
        return self._closure_reports.get(run_id)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def list_campaigns(
        self, *, status: CampaignStatus | None = None,
    ) -> tuple[CampaignDescriptor, ...]:
        result = list(self._campaigns.values())
        if status is not None:
            result = [c for c in result if c.status == status]
        return tuple(sorted(result, key=lambda c: c.campaign_id))

    def list_runs(
        self, campaign_id: str | None = None,
        *, status: CampaignStatus | None = None,
    ) -> tuple[CampaignRun, ...]:
        result = list(self._runs.values())
        if campaign_id is not None:
            result = [r for r in result if r.campaign_id == campaign_id]
        if status is not None:
            result = [r for r in result if r.status == status]
        return tuple(sorted(result, key=lambda r: r.run_id))

    def get_execution_records(
        self, run_id: str | None = None,
    ) -> tuple[CampaignExecutionRecord, ...]:
        if run_id is None:
            return tuple(self._execution_records)
        return tuple(r for r in self._execution_records if r.run_id == run_id)

    def get_escalations(
        self, run_id: str | None = None,
    ) -> tuple[CampaignEscalation, ...]:
        if run_id is None:
            return tuple(self._escalations)
        return tuple(e for e in self._escalations if e.run_id == run_id)

    def get_run_step(
        self, run_id: str, step_id: str,
    ) -> CampaignStep:
        if run_id not in self._run_steps:
            raise RuntimeCoreInvariantError(f"run '{run_id}' not found")
        if step_id not in self._run_steps[run_id]:
            raise RuntimeCoreInvariantError(f"step '{step_id}' not in run")
        return self._run_steps[run_id][step_id]

    @property
    def campaign_count(self) -> int:
        return len(self._campaigns)

    @property
    def run_count(self) -> int:
        return len(self._runs)

    def state_hash(self) -> str:
        h = sha256()
        for cid in sorted(self._campaigns):
            c = self._campaigns[cid]
            h.update(f"camp:{cid}:{c.status.value}:{c.step_count}".encode())
        for rid in sorted(self._runs):
            r = self._runs[rid]
            h.update(f"run:{rid}:{r.status.value}:{r.current_step_index}".encode())
        return h.hexdigest()
