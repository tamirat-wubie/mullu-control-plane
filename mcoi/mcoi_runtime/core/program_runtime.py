"""Purpose: program / initiative / OKR runtime engine.
Governance scope: registering objectives, programs, initiatives, milestones;
    binding campaigns/portfolios; computing attainment and progress;
    detecting blocked initiatives; producing health snapshots and decisions.
Dependencies: program_runtime contracts, event_spine, core invariants.
Invariants:
  - Objectives decompose into initiatives via programs.
  - Milestones gate initiative progress.
  - Dependencies enforce ordering constraints.
  - Every mutation emits an event.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from ..contracts.program_runtime import (
    AttainmentLevel,
    AttainmentSnapshot,
    DependencyKind,
    InitiativeDependency,
    InitiativeRecord,
    InitiativeStatus,
    MilestoneRecord,
    MilestoneStatus,
    ObjectiveBinding,
    ObjectiveRecord,
    ObjectiveType,
    ProgramClosureReport,
    ProgramDecision,
    ProgramHealth,
    ProgramRecord,
    ProgramStatus,
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
        event_id=stable_identifier("evt-prog", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class ProgramRuntimeEngine:
    """Engine for program / initiative / OKR management."""

    def __init__(self, event_spine: EventSpineEngine) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._objectives: dict[str, ObjectiveRecord] = {}
        self._programs: dict[str, ProgramRecord] = {}
        self._initiatives: dict[str, InitiativeRecord] = {}
        self._milestones: dict[str, MilestoneRecord] = {}
        self._bindings: list[ObjectiveBinding] = []
        self._dependencies: list[InitiativeDependency] = []
        self._decisions: dict[str, ProgramDecision] = {}

    # ------------------------------------------------------------------
    # Objectives
    # ------------------------------------------------------------------

    def register_objective(
        self,
        objective_id: str,
        title: str,
        *,
        description: str = "",
        objective_type: ObjectiveType = ObjectiveType.STRATEGIC,
        parent_objective_id: str = "",
        target_value: float = 0.0,
        current_value: float = 0.0,
        unit: str = "",
        weight: float = 1.0,
        owner: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> ObjectiveRecord:
        if objective_id in self._objectives:
            raise RuntimeCoreInvariantError("objective already exists")
        now = _now_iso()
        obj = ObjectiveRecord(
            objective_id=objective_id,
            title=title,
            description=description,
            objective_type=objective_type,
            parent_objective_id=parent_objective_id,
            target_value=target_value,
            current_value=current_value,
            unit=unit,
            attainment=AttainmentLevel.NOT_STARTED,
            weight=weight,
            owner=owner,
            created_at=now,
            updated_at=now,
            metadata=metadata or {},
        )
        self._objectives[objective_id] = obj
        _emit(self._events, "objective_registered", {
            "objective_id": objective_id,
            "objective_type": objective_type.value,
        }, objective_id)
        return obj

    def get_objective(self, objective_id: str) -> ObjectiveRecord | None:
        return self._objectives.get(objective_id)

    def update_objective_value(
        self,
        objective_id: str,
        current_value: float,
    ) -> ObjectiveRecord:
        if objective_id not in self._objectives:
            raise RuntimeCoreInvariantError("objective not found")
        old = self._objectives[objective_id]
        attainment = self._compute_attainment_level(old.target_value, current_value)
        now = _now_iso()
        updated = ObjectiveRecord(
            objective_id=old.objective_id,
            title=old.title,
            description=old.description,
            objective_type=old.objective_type,
            parent_objective_id=old.parent_objective_id,
            target_value=old.target_value,
            current_value=current_value,
            unit=old.unit,
            attainment=attainment,
            weight=old.weight,
            owner=old.owner,
            created_at=old.created_at,
            updated_at=now,
            metadata=dict(old.metadata),
        )
        self._objectives[objective_id] = updated
        _emit(self._events, "objective_value_updated", {
            "objective_id": objective_id,
            "current_value": current_value,
            "attainment": attainment.value,
        }, objective_id)
        return updated

    def _compute_attainment_level(self, target: float, current: float) -> AttainmentLevel:
        if target == 0:
            return AttainmentLevel.ON_TRACK
        pct = (current / target) * 100
        if pct >= 110:
            return AttainmentLevel.EXCEEDED
        if pct >= 90:
            return AttainmentLevel.ON_TRACK
        if pct >= 70:
            return AttainmentLevel.AT_RISK
        if pct >= 30:
            return AttainmentLevel.BEHIND
        if pct > 0:
            return AttainmentLevel.BEHIND
        return AttainmentLevel.NOT_STARTED

    # ------------------------------------------------------------------
    # Programs
    # ------------------------------------------------------------------

    def register_program(
        self,
        program_id: str,
        title: str,
        *,
        description: str = "",
        objective_ids: list[str] | None = None,
        owner: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> ProgramRecord:
        if program_id in self._programs:
            raise RuntimeCoreInvariantError("program already exists")
        now = _now_iso()
        prog = ProgramRecord(
            program_id=program_id,
            title=title,
            description=description,
            status=ProgramStatus.ACTIVE,
            objective_ids=tuple(objective_ids or []),
            initiative_ids=(),
            owner=owner,
            created_at=now,
            updated_at=now,
            metadata=metadata or {},
        )
        self._programs[program_id] = prog
        _emit(self._events, "program_registered", {
            "program_id": program_id,
            "objective_count": len(prog.objective_ids),
        }, program_id)
        return prog

    def get_program(self, program_id: str) -> ProgramRecord | None:
        return self._programs.get(program_id)

    def set_program_status(self, program_id: str, status: ProgramStatus) -> ProgramRecord:
        if program_id not in self._programs:
            raise RuntimeCoreInvariantError("program not found")
        old = self._programs[program_id]
        now = _now_iso()
        updated = ProgramRecord(
            program_id=old.program_id,
            title=old.title,
            description=old.description,
            status=status,
            objective_ids=old.objective_ids,
            initiative_ids=old.initiative_ids,
            owner=old.owner,
            created_at=old.created_at,
            updated_at=now,
            metadata=dict(old.metadata),
        )
        self._programs[program_id] = updated
        _emit(self._events, "program_status_changed", {
            "program_id": program_id,
            "status": status.value,
        }, program_id)
        return updated

    # ------------------------------------------------------------------
    # Initiatives
    # ------------------------------------------------------------------

    def register_initiative(
        self,
        initiative_id: str,
        program_id: str,
        title: str,
        *,
        objective_id: str = "",
        description: str = "",
        priority: int = 0,
        owner: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> InitiativeRecord:
        if initiative_id in self._initiatives:
            raise RuntimeCoreInvariantError("initiative already exists")
        if program_id not in self._programs:
            raise RuntimeCoreInvariantError("program not found")
        now = _now_iso()
        ini = InitiativeRecord(
            initiative_id=initiative_id,
            program_id=program_id,
            objective_id=objective_id,
            title=title,
            description=description,
            status=InitiativeStatus.ACTIVE,
            priority=priority,
            progress_pct=0.0,
            owner=owner,
            created_at=now,
            updated_at=now,
            metadata=metadata or {},
        )
        self._initiatives[initiative_id] = ini

        # Update program initiative_ids
        prog = self._programs[program_id]
        new_ids = prog.initiative_ids + (initiative_id,)
        updated_prog = ProgramRecord(
            program_id=prog.program_id,
            title=prog.title,
            description=prog.description,
            status=prog.status,
            objective_ids=prog.objective_ids,
            initiative_ids=new_ids,
            owner=prog.owner,
            created_at=prog.created_at,
            updated_at=now,
            metadata=dict(prog.metadata),
        )
        self._programs[program_id] = updated_prog

        _emit(self._events, "initiative_registered", {
            "initiative_id": initiative_id,
            "program_id": program_id,
            "objective_id": objective_id,
        }, initiative_id)
        return ini

    def get_initiative(self, initiative_id: str) -> InitiativeRecord | None:
        return self._initiatives.get(initiative_id)

    def set_initiative_status(self, initiative_id: str, status: InitiativeStatus) -> InitiativeRecord:
        if initiative_id not in self._initiatives:
            raise RuntimeCoreInvariantError("initiative not found")
        old = self._initiatives[initiative_id]
        now = _now_iso()
        updated = InitiativeRecord(
            initiative_id=old.initiative_id,
            program_id=old.program_id,
            objective_id=old.objective_id,
            title=old.title,
            description=old.description,
            status=status,
            priority=old.priority,
            progress_pct=old.progress_pct,
            campaign_ids=old.campaign_ids,
            portfolio_ids=old.portfolio_ids,
            milestone_ids=old.milestone_ids,
            owner=old.owner,
            created_at=old.created_at,
            updated_at=now,
            metadata=dict(old.metadata),
        )
        self._initiatives[initiative_id] = updated
        _emit(self._events, "initiative_status_changed", {
            "initiative_id": initiative_id,
            "status": status.value,
        }, initiative_id)
        return updated

    def update_initiative_progress(self, initiative_id: str, progress_pct: float) -> InitiativeRecord:
        if initiative_id not in self._initiatives:
            raise RuntimeCoreInvariantError("initiative not found")
        old = self._initiatives[initiative_id]
        now = _now_iso()
        updated = InitiativeRecord(
            initiative_id=old.initiative_id,
            program_id=old.program_id,
            objective_id=old.objective_id,
            title=old.title,
            description=old.description,
            status=old.status,
            priority=old.priority,
            progress_pct=progress_pct,
            campaign_ids=old.campaign_ids,
            portfolio_ids=old.portfolio_ids,
            milestone_ids=old.milestone_ids,
            owner=old.owner,
            created_at=old.created_at,
            updated_at=now,
            metadata=dict(old.metadata),
        )
        self._initiatives[initiative_id] = updated
        return updated

    # ------------------------------------------------------------------
    # Milestones
    # ------------------------------------------------------------------

    def register_milestone(
        self,
        milestone_id: str,
        initiative_id: str,
        title: str,
        *,
        description: str = "",
        target_date: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> MilestoneRecord:
        if milestone_id in self._milestones:
            raise RuntimeCoreInvariantError("milestone already exists")
        if initiative_id not in self._initiatives:
            raise RuntimeCoreInvariantError("initiative not found")
        now = _now_iso()
        ms = MilestoneRecord(
            milestone_id=milestone_id,
            initiative_id=initiative_id,
            title=title,
            description=description,
            status=MilestoneStatus.PENDING,
            target_date=target_date,
            progress_pct=0.0,
            created_at=now,
            metadata=metadata or {},
        )
        self._milestones[milestone_id] = ms

        # Update initiative milestone_ids
        ini = self._initiatives[initiative_id]
        new_ms_ids = ini.milestone_ids + (milestone_id,)
        updated_ini = InitiativeRecord(
            initiative_id=ini.initiative_id,
            program_id=ini.program_id,
            objective_id=ini.objective_id,
            title=ini.title,
            description=ini.description,
            status=ini.status,
            priority=ini.priority,
            progress_pct=ini.progress_pct,
            campaign_ids=ini.campaign_ids,
            portfolio_ids=ini.portfolio_ids,
            milestone_ids=new_ms_ids,
            owner=ini.owner,
            created_at=ini.created_at,
            updated_at=_now_iso(),
            metadata=dict(ini.metadata),
        )
        self._initiatives[initiative_id] = updated_ini

        _emit(self._events, "milestone_registered", {
            "milestone_id": milestone_id,
            "initiative_id": initiative_id,
        }, milestone_id)
        return ms

    def get_milestone(self, milestone_id: str) -> MilestoneRecord | None:
        return self._milestones.get(milestone_id)

    def record_milestone_progress(
        self,
        milestone_id: str,
        progress_pct: float,
        *,
        status: MilestoneStatus | None = None,
    ) -> MilestoneRecord:
        if milestone_id not in self._milestones:
            raise RuntimeCoreInvariantError("milestone not found")
        old = self._milestones[milestone_id]
        new_status = status if status is not None else old.status
        if status is None and progress_pct >= 100.0:
            new_status = MilestoneStatus.ACHIEVED
        now = _now_iso()
        completed_date = now if new_status == MilestoneStatus.ACHIEVED else old.completed_date
        updated = MilestoneRecord(
            milestone_id=old.milestone_id,
            initiative_id=old.initiative_id,
            title=old.title,
            description=old.description,
            status=new_status,
            target_date=old.target_date,
            completed_date=completed_date,
            progress_pct=progress_pct,
            created_at=old.created_at,
            metadata=dict(old.metadata),
        )
        self._milestones[milestone_id] = updated
        _emit(self._events, "milestone_progress_recorded", {
            "milestone_id": milestone_id,
            "progress_pct": progress_pct,
            "status": new_status.value,
        }, milestone_id)
        return updated

    # ------------------------------------------------------------------
    # Bindings
    # ------------------------------------------------------------------

    def bind_campaign(
        self,
        binding_id: str,
        initiative_id: str,
        campaign_ref_id: str,
        *,
        objective_id: str = "",
        weight: float = 1.0,
    ) -> ObjectiveBinding:
        if initiative_id not in self._initiatives:
            raise RuntimeCoreInvariantError("initiative not found")
        now = _now_iso()
        binding = ObjectiveBinding(
            binding_id=binding_id,
            objective_id=objective_id,
            initiative_id=initiative_id,
            campaign_ref_id=campaign_ref_id,
            weight=weight,
            bound_at=now,
        )
        self._bindings.append(binding)

        # Update initiative campaign_ids
        ini = self._initiatives[initiative_id]
        if campaign_ref_id not in ini.campaign_ids:
            new_campaign_ids = ini.campaign_ids + (campaign_ref_id,)
            updated_ini = InitiativeRecord(
                initiative_id=ini.initiative_id,
                program_id=ini.program_id,
                objective_id=ini.objective_id,
                title=ini.title,
                description=ini.description,
                status=ini.status,
                priority=ini.priority,
                progress_pct=ini.progress_pct,
                campaign_ids=new_campaign_ids,
                portfolio_ids=ini.portfolio_ids,
                milestone_ids=ini.milestone_ids,
                owner=ini.owner,
                created_at=ini.created_at,
                updated_at=_now_iso(),
                metadata=dict(ini.metadata),
            )
            self._initiatives[initiative_id] = updated_ini

        _emit(self._events, "campaign_bound", {
            "binding_id": binding_id,
            "initiative_id": initiative_id,
            "campaign_ref_id": campaign_ref_id,
        }, binding_id)
        return binding

    def bind_portfolio(
        self,
        binding_id: str,
        initiative_id: str,
        portfolio_ref_id: str,
        *,
        objective_id: str = "",
        weight: float = 1.0,
    ) -> ObjectiveBinding:
        if initiative_id not in self._initiatives:
            raise RuntimeCoreInvariantError("initiative not found")
        now = _now_iso()
        binding = ObjectiveBinding(
            binding_id=binding_id,
            objective_id=objective_id,
            initiative_id=initiative_id,
            portfolio_ref_id=portfolio_ref_id,
            weight=weight,
            bound_at=now,
        )
        self._bindings.append(binding)

        # Update initiative portfolio_ids
        ini = self._initiatives[initiative_id]
        if portfolio_ref_id not in ini.portfolio_ids:
            new_portfolio_ids = ini.portfolio_ids + (portfolio_ref_id,)
            updated_ini = InitiativeRecord(
                initiative_id=ini.initiative_id,
                program_id=ini.program_id,
                objective_id=ini.objective_id,
                title=ini.title,
                description=ini.description,
                status=ini.status,
                priority=ini.priority,
                progress_pct=ini.progress_pct,
                campaign_ids=ini.campaign_ids,
                portfolio_ids=new_portfolio_ids,
                milestone_ids=ini.milestone_ids,
                owner=ini.owner,
                created_at=ini.created_at,
                updated_at=_now_iso(),
                metadata=dict(ini.metadata),
            )
            self._initiatives[initiative_id] = updated_ini

        _emit(self._events, "portfolio_bound", {
            "binding_id": binding_id,
            "initiative_id": initiative_id,
            "portfolio_ref_id": portfolio_ref_id,
        }, binding_id)
        return binding

    # ------------------------------------------------------------------
    # Dependencies
    # ------------------------------------------------------------------

    def add_dependency(
        self,
        dependency_id: str,
        from_initiative_id: str,
        to_initiative_id: str,
        *,
        kind: DependencyKind = DependencyKind.REQUIRES,
        description: str = "",
    ) -> InitiativeDependency:
        now = _now_iso()
        dep = InitiativeDependency(
            dependency_id=dependency_id,
            from_initiative_id=from_initiative_id,
            to_initiative_id=to_initiative_id,
            kind=kind,
            description=description,
            created_at=now,
        )
        self._dependencies.append(dep)
        _emit(self._events, "dependency_added", {
            "dependency_id": dependency_id,
            "from": from_initiative_id,
            "to": to_initiative_id,
            "kind": kind.value,
        }, dependency_id)
        return dep

    # ------------------------------------------------------------------
    # Attainment computation
    # ------------------------------------------------------------------

    def compute_attainment(self, objective_id: str, snapshot_id: str) -> AttainmentSnapshot:
        if objective_id not in self._objectives:
            raise RuntimeCoreInvariantError("objective not found")
        obj = self._objectives[objective_id]

        # Find initiatives for this objective
        related = [i for i in self._initiatives.values() if i.objective_id == objective_id]
        total = len(related)
        completed = sum(1 for i in related if i.status == InitiativeStatus.COMPLETED)
        blocked = sum(1 for i in related if i.status == InitiativeStatus.BLOCKED)

        if obj.target_value != 0:
            progress = (obj.current_value / obj.target_value) * 100
        elif total > 0:
            progress = (completed / total) * 100
        else:
            progress = 0.0

        now = _now_iso()
        snap = AttainmentSnapshot(
            snapshot_id=snapshot_id,
            objective_id=objective_id,
            attainment=obj.attainment,
            target_value=obj.target_value,
            current_value=obj.current_value,
            progress_pct=progress,
            initiative_count=total,
            completed_initiatives=completed,
            blocked_initiatives=blocked,
            captured_at=now,
        )
        _emit(self._events, "attainment_computed", {
            "snapshot_id": snapshot_id,
            "objective_id": objective_id,
            "attainment": obj.attainment.value,
            "progress_pct": progress,
        }, snapshot_id)
        return snap

    # ------------------------------------------------------------------
    # Blocked initiative detection
    # ------------------------------------------------------------------

    def blocked_initiatives(self) -> tuple[InitiativeRecord, ...]:
        """Return initiatives that are blocked by dependency failures."""
        blocked = []
        for ini in self._initiatives.values():
            if ini.status == InitiativeStatus.BLOCKED:
                blocked.append(ini)
                continue
            # Check dependencies
            for dep in self._dependencies:
                if dep.from_initiative_id == ini.initiative_id and dep.kind in (DependencyKind.REQUIRES, DependencyKind.BLOCKS):
                    target = self._initiatives.get(dep.to_initiative_id)
                    if target and target.status in (InitiativeStatus.FAILED, InitiativeStatus.CANCELLED, InitiativeStatus.BLOCKED):
                        blocked.append(ini)
                        break
        return tuple(blocked)

    # ------------------------------------------------------------------
    # Program health
    # ------------------------------------------------------------------

    def program_health(self, program_id: str, health_id: str) -> ProgramHealth:
        if program_id not in self._programs:
            raise RuntimeCoreInvariantError("program not found")
        prog = self._programs[program_id]

        initiatives = [self._initiatives[iid] for iid in prog.initiative_ids if iid in self._initiatives]
        total_ini = len(initiatives)
        active_ini = sum(1 for i in initiatives if i.status == InitiativeStatus.ACTIVE)
        blocked_ini = sum(1 for i in initiatives if i.status == InitiativeStatus.BLOCKED)
        completed_ini = sum(1 for i in initiatives if i.status == InitiativeStatus.COMPLETED)

        # Milestones for this program's initiatives
        ini_ids = set(prog.initiative_ids)
        milestones = [m for m in self._milestones.values() if m.initiative_id in ini_ids]
        total_ms = len(milestones)
        achieved_ms = sum(1 for m in milestones if m.status == MilestoneStatus.ACHIEVED)
        missed_ms = sum(1 for m in milestones if m.status == MilestoneStatus.MISSED)

        if total_ini > 0:
            overall = sum(i.progress_pct for i in initiatives) / total_ini
        else:
            overall = 0.0

        now = _now_iso()
        health = ProgramHealth(
            health_id=health_id,
            program_id=program_id,
            status=prog.status,
            total_initiatives=total_ini,
            active_initiatives=active_ini,
            blocked_initiatives=blocked_ini,
            completed_initiatives=completed_ini,
            total_milestones=total_ms,
            achieved_milestones=achieved_ms,
            missed_milestones=missed_ms,
            overall_progress_pct=overall,
            assessed_at=now,
        )
        _emit(self._events, "program_health_assessed", {
            "health_id": health_id,
            "program_id": program_id,
            "overall_progress_pct": overall,
            "blocked": blocked_ini,
            "missed_milestones": missed_ms,
        }, health_id)
        return health

    # ------------------------------------------------------------------
    # Decisions
    # ------------------------------------------------------------------

    def record_decision(
        self,
        decision_id: str,
        title: str,
        *,
        program_id: str = "",
        initiative_id: str = "",
        rationale: str = "",
        action: str = "",
        confidence: float = 0.8,
        metadata: dict[str, Any] | None = None,
    ) -> ProgramDecision:
        if decision_id in self._decisions:
            raise RuntimeCoreInvariantError("decision already exists")
        now = _now_iso()
        dec = ProgramDecision(
            decision_id=decision_id,
            program_id=program_id,
            initiative_id=initiative_id,
            title=title,
            rationale=rationale,
            action=action,
            confidence=confidence,
            decided_at=now,
            metadata=metadata or {},
        )
        self._decisions[decision_id] = dec
        _emit(self._events, "decision_recorded", {
            "decision_id": decision_id,
            "program_id": program_id,
        }, decision_id)
        return dec

    def get_decision(self, decision_id: str) -> ProgramDecision | None:
        return self._decisions.get(decision_id)

    # ------------------------------------------------------------------
    # Closure
    # ------------------------------------------------------------------

    def close_program(
        self,
        report_id: str,
        program_id: str,
        *,
        final_status: ProgramStatus = ProgramStatus.COMPLETED,
        lessons: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ProgramClosureReport:
        if program_id not in self._programs:
            raise RuntimeCoreInvariantError("program not found")
        prog = self._programs[program_id]

        initiatives = [self._initiatives[iid] for iid in prog.initiative_ids if iid in self._initiatives]
        total_ini = len(initiatives)
        completed_ini = sum(1 for i in initiatives if i.status == InitiativeStatus.COMPLETED)
        failed_ini = sum(1 for i in initiatives if i.status == InitiativeStatus.FAILED)

        ini_ids = set(prog.initiative_ids)
        milestones = [m for m in self._milestones.values() if m.initiative_id in ini_ids]
        total_ms = len(milestones)
        achieved_ms = sum(1 for m in milestones if m.status == MilestoneStatus.ACHIEVED)
        missed_ms = sum(1 for m in milestones if m.status == MilestoneStatus.MISSED)

        attainment = (completed_ini / total_ini * 100) if total_ini > 0 else 0.0

        now = _now_iso()
        report = ProgramClosureReport(
            report_id=report_id,
            program_id=program_id,
            final_status=final_status,
            total_initiatives=total_ini,
            completed_initiatives=completed_ini,
            failed_initiatives=failed_ini,
            total_milestones=total_ms,
            achieved_milestones=achieved_ms,
            missed_milestones=missed_ms,
            overall_attainment_pct=attainment,
            lessons=tuple(lessons or []),
            closed_at=now,
            metadata=metadata or {},
        )

        # Update program status
        self.set_program_status(program_id, final_status)

        _emit(self._events, "program_closed", {
            "report_id": report_id,
            "program_id": program_id,
            "final_status": final_status.value,
            "attainment_pct": attainment,
        }, report_id)
        return report

    # ------------------------------------------------------------------
    # Properties and queries
    # ------------------------------------------------------------------

    @property
    def objective_count(self) -> int:
        return len(self._objectives)

    @property
    def program_count(self) -> int:
        return len(self._programs)

    @property
    def initiative_count(self) -> int:
        return len(self._initiatives)

    @property
    def milestone_count(self) -> int:
        return len(self._milestones)

    @property
    def binding_count(self) -> int:
        return len(self._bindings)

    @property
    def dependency_count(self) -> int:
        return len(self._dependencies)

    @property
    def decision_count(self) -> int:
        return len(self._decisions)

    def get_bindings(self) -> tuple[ObjectiveBinding, ...]:
        return tuple(self._bindings)

    def get_dependencies(self) -> tuple[InitiativeDependency, ...]:
        return tuple(self._dependencies)

    def state_hash(self) -> str:
        parts: list[str] = []
        for k in sorted(self._objectives):
            parts.append(f"obj:{k}:{self._objectives[k].attainment.value}")
        for k in sorted(self._programs):
            parts.append(f"prog:{k}:{self._programs[k].status.value}")
        for k in sorted(self._initiatives):
            parts.append(f"ini:{k}:{self._initiatives[k].status.value}")
        for k in sorted(self._milestones):
            parts.append(f"ms:{k}:{self._milestones[k].status.value}")
        for k in sorted(self._decisions):
            parts.append(f"dec:{k}:{self._decisions[k].action}")
        parts.append(f"bindings={len(self._bindings)}")
        parts.append(f"dependencies={len(self._dependencies)}")
        digest = sha256("|".join(parts).encode()).hexdigest()
        return digest
