"""Purpose: fault injection engine.
Governance scope: registering, activating, and managing fault injections
    across runtime subsystems with deterministic audit trails.
Dependencies: fault_injection contracts, core invariants.
Invariants:
  - Deterministic injection based on spec and tick.
  - Windowed activation — faults only fire within defined windows.
  - Severity tagging on every injection record.
  - Explicit target matching — no accidental fault application.
  - Immutable audit trail — every injection, observation, recovery recorded.
  - State hash support for checkpoint determinism.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Mapping

from ..contracts.fault_injection import (
    AdversarialOutcome,
    AdversarialSession,
    FaultDisposition,
    FaultInjectionRecord,
    FaultObservation,
    FaultRecoveryAssessment,
    FaultSeverity,
    FaultSpec,
    FaultTargetKind,
    FaultType,
    FaultWindow,
    InjectionMode,
)
from .invariants import RuntimeCoreInvariantError, stable_identifier


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class FaultInjectionEngine:
    """Manages fault injection lifecycle, windowing, and audit trails."""

    def __init__(self) -> None:
        self._specs: dict[str, FaultSpec] = {}
        self._windows: dict[str, FaultWindow] = {}
        self._records: list[FaultInjectionRecord] = []
        self._observations: dict[str, FaultObservation] = {}
        self._assessments: dict[str, FaultRecoveryAssessment] = {}
        self._sessions: dict[str, AdversarialSession] = {}
        self._outcomes: dict[str, AdversarialOutcome] = {}
        self._injection_counts: dict[str, int] = {}  # spec_id -> count

    # -----------------------------------------------------------------------
    # Spec management
    # -----------------------------------------------------------------------

    def register_spec(self, spec: FaultSpec) -> FaultSpec:
        """Register a fault specification. Rejects duplicates."""
        if not isinstance(spec, FaultSpec):
            raise RuntimeCoreInvariantError("spec must be a FaultSpec")
        if spec.spec_id in self._specs:
            raise RuntimeCoreInvariantError(
                f"fault spec '{spec.spec_id}' already registered"
            )
        self._specs[spec.spec_id] = spec
        self._injection_counts[spec.spec_id] = 0
        return spec

    def get_spec(self, spec_id: str) -> FaultSpec:
        """Get a spec by ID."""
        if spec_id not in self._specs:
            raise RuntimeCoreInvariantError(f"fault spec '{spec_id}' not found")
        return self._specs[spec_id]

    def list_specs(
        self,
        *,
        fault_type: FaultType | None = None,
        target_kind: FaultTargetKind | None = None,
        severity: FaultSeverity | None = None,
    ) -> tuple[FaultSpec, ...]:
        """List specs with optional filters."""
        result = list(self._specs.values())
        if fault_type is not None:
            result = [s for s in result if s.fault_type == fault_type]
        if target_kind is not None:
            result = [s for s in result if s.target_kind == target_kind]
        if severity is not None:
            result = [s for s in result if s.severity == severity]
        return tuple(sorted(result, key=lambda s: s.spec_id))

    # -----------------------------------------------------------------------
    # Window management
    # -----------------------------------------------------------------------

    def set_window(self, window: FaultWindow) -> FaultWindow:
        """Set an injection window for a spec. Spec must exist."""
        if not isinstance(window, FaultWindow):
            raise RuntimeCoreInvariantError("window must be a FaultWindow")
        if window.spec_id not in self._specs:
            raise RuntimeCoreInvariantError(
                f"fault spec '{window.spec_id}' not found"
            )
        if window.window_id in self._windows:
            raise RuntimeCoreInvariantError(
                f"window '{window.window_id}' already exists"
            )
        self._windows[window.window_id] = window
        return window

    def is_active_at_tick(self, spec_id: str, tick: int) -> bool:
        """Check if a fault spec is active at a given tick number."""
        if spec_id not in self._specs:
            return False
        # Check windows — if any window exists for this spec, require tick in range
        spec_windows = [w for w in self._windows.values()
                       if w.spec_id == spec_id and w.active]
        if not spec_windows:
            # No windows defined — always active (single/repeated mode)
            spec = self._specs[spec_id]
            if spec.injection_mode == InjectionMode.WINDOWED:
                return False  # Windowed mode requires a window
            return True
        # Active if tick falls within any active window
        return any(w.start_tick <= tick <= w.end_tick for w in spec_windows)

    # -----------------------------------------------------------------------
    # Fault injection
    # -----------------------------------------------------------------------

    def inject(
        self,
        spec_id: str,
        tick: int = 0,
        target_ref_id: str = "",
    ) -> FaultInjectionRecord | None:
        """Inject a fault. Returns None if not active or repeat limit reached."""
        spec = self.get_spec(spec_id)

        # Check activation window
        if not self.is_active_at_tick(spec_id, tick):
            return None

        # Check repeat limit
        current_count = self._injection_counts.get(spec_id, 0)
        if spec.injection_mode in (InjectionMode.SINGLE, InjectionMode.WINDOWED):
            if current_count >= spec.repeat_count:
                return None
        elif spec.injection_mode == InjectionMode.REPEATED:
            if current_count >= spec.repeat_count:
                return None

        now = _now_iso()
        record = FaultInjectionRecord(
            record_id=stable_identifier("fault-inj", {
                "spec": spec_id, "tick": tick, "n": current_count,
            }),
            spec_id=spec_id,
            fault_type=spec.fault_type,
            target_kind=spec.target_kind,
            target_ref_id=target_ref_id or spec.target_ref_id,
            severity=spec.severity,
            disposition=FaultDisposition.INJECTED,
            tick_number=tick,
            description=spec.description or f"Injected {spec.fault_type} at tick {tick}",
            injected_at=now,
        )
        self._records.append(record)
        self._injection_counts[spec_id] = current_count + 1
        return record

    def inject_for_target(
        self,
        target_kind: FaultTargetKind,
        tick: int = 0,
        target_ref_id: str = "",
    ) -> tuple[FaultInjectionRecord, ...]:
        """Inject all active faults targeting a specific subsystem."""
        results = []
        for spec_id, spec in sorted(self._specs.items()):
            if spec.target_kind == target_kind:
                record = self.inject(spec_id, tick, target_ref_id)
                if record is not None:
                    results.append(record)
        return tuple(results)

    # -----------------------------------------------------------------------
    # Observations
    # -----------------------------------------------------------------------

    def record_observation(
        self,
        record_id: str,
        observed_behavior: str,
        expected_behavior: str = "",
        matches_expected: bool = False,
    ) -> FaultObservation:
        """Record an observation about a fault injection's effect."""
        # Verify the injection record exists
        if not any(r.record_id == record_id for r in self._records):
            raise RuntimeCoreInvariantError(
                f"injection record '{record_id}' not found"
            )
        now = _now_iso()
        obs = FaultObservation(
            observation_id=stable_identifier("fault-obs", {
                "rec": record_id, "ts": now,
            }),
            record_id=record_id,
            observed_behavior=observed_behavior,
            expected_behavior=expected_behavior or "system handles fault gracefully",
            matches_expected=matches_expected,
            observed_at=now,
        )
        self._observations[obs.observation_id] = obs
        return obs

    def get_observations_for_record(
        self, record_id: str,
    ) -> tuple[FaultObservation, ...]:
        """Get all observations for a specific injection record."""
        return tuple(
            o for o in self._observations.values()
            if o.record_id == record_id
        )

    # -----------------------------------------------------------------------
    # Recovery assessments
    # -----------------------------------------------------------------------

    def assess_recovery(
        self,
        record_id: str,
        recovered: bool,
        recovery_method: str = "",
        degraded: bool = False,
        degraded_reason: str = "",
        state_consistent: bool = True,
    ) -> FaultRecoveryAssessment:
        """Assess whether the system recovered from a fault."""
        if not any(r.record_id == record_id for r in self._records):
            raise RuntimeCoreInvariantError(
                f"injection record '{record_id}' not found"
            )
        now = _now_iso()
        assessment = FaultRecoveryAssessment(
            assessment_id=stable_identifier("fault-assess", {
                "rec": record_id, "ts": now,
            }),
            record_id=record_id,
            recovered=recovered,
            recovery_method=recovery_method,
            degraded=degraded,
            degraded_reason=degraded_reason,
            state_consistent=state_consistent,
            assessed_at=now,
        )
        self._assessments[assessment.assessment_id] = assessment
        return assessment

    def get_assessments_for_record(
        self, record_id: str,
    ) -> tuple[FaultRecoveryAssessment, ...]:
        """Get all recovery assessments for a specific injection record."""
        return tuple(
            a for a in self._assessments.values()
            if a.record_id == record_id
        )

    # -----------------------------------------------------------------------
    # Adversarial sessions
    # -----------------------------------------------------------------------

    def start_session(
        self,
        name: str,
        spec_ids: tuple[str, ...],
        tags: tuple[str, ...] = (),
    ) -> AdversarialSession:
        """Start an adversarial campaign session."""
        for sid in spec_ids:
            if sid not in self._specs:
                raise RuntimeCoreInvariantError(f"fault spec '{sid}' not found")

        target_kinds = tuple(sorted({
            self._specs[sid].target_kind.value for sid in spec_ids
        }))
        now = _now_iso()
        session = AdversarialSession(
            session_id=stable_identifier("adv-session", {"name": name, "seq": str(len(self._sessions))}),
            name=name,
            fault_spec_ids=spec_ids,
            target_kinds=target_kinds,
            started_at=now,
            tags=tags,
        )
        self._sessions[session.session_id] = session
        return session

    def complete_session(self, session_id: str) -> AdversarialOutcome:
        """Complete a session and produce an outcome."""
        if session_id not in self._sessions:
            raise RuntimeCoreInvariantError(
                f"session '{session_id}' not found"
            )
        session = self._sessions[session_id]

        # Gather records for this session's specs
        session_records = [
            r for r in self._records
            if r.spec_id in session.fault_spec_ids
        ]
        total = len(session_records)
        detected = sum(1 for r in session_records
                      if r.record_id in {a.record_id for a in self._assessments.values()})
        recovered = sum(1 for a in self._assessments.values()
                       if a.record_id in {r.record_id for r in session_records}
                       and a.recovered)
        degraded = sum(1 for a in self._assessments.values()
                      if a.record_id in {r.record_id for r in session_records}
                      and a.degraded)
        failed = sum(1 for a in self._assessments.values()
                    if a.record_id in {r.record_id for r in session_records}
                    and not a.recovered and not a.degraded)
        consistent = all(
            a.state_consistent for a in self._assessments.values()
            if a.record_id in {r.record_id for r in session_records}
        )

        # Score: proportion of faults that were detected and recovered
        score = (recovered / total) if total > 0 else 1.0
        passed = consistent and failed == 0

        now = _now_iso()
        outcome = AdversarialOutcome(
            outcome_id=stable_identifier("adv-outcome", {"sid": session_id, "seq": str(len(self._outcomes))}),
            session_id=session_id,
            passed=passed,
            total_faults=total,
            faults_detected=detected,
            faults_recovered=recovered,
            faults_degraded=degraded,
            faults_failed=failed,
            state_consistent=consistent,
            score=min(score, 1.0),
            summary=f"{'PASSED' if passed else 'FAILED'}: {recovered}/{total} recovered, {degraded} degraded, {failed} failed",
            completed_at=now,
        )
        self._outcomes[outcome.outcome_id] = outcome

        # Update session with final counts
        updated_session = AdversarialSession(
            session_id=session.session_id,
            name=session.name,
            fault_spec_ids=session.fault_spec_ids,
            target_kinds=session.target_kinds,
            total_injections=total,
            total_observations=len([
                o for o in self._observations.values()
                if o.record_id in {r.record_id for r in session_records}
            ]),
            total_recoveries=recovered,
            started_at=session.started_at,
            completed_at=now,
            tags=session.tags,
        )
        self._sessions[session_id] = updated_session

        return outcome

    # -----------------------------------------------------------------------
    # Retrieval
    # -----------------------------------------------------------------------

    def get_records(
        self,
        *,
        spec_id: str = "",
        target_kind: FaultTargetKind | None = None,
        disposition: FaultDisposition | None = None,
    ) -> tuple[FaultInjectionRecord, ...]:
        """Get injection records with optional filters."""
        result = list(self._records)
        if spec_id:
            result = [r for r in result if r.spec_id == spec_id]
        if target_kind is not None:
            result = [r for r in result if r.target_kind == target_kind]
        if disposition is not None:
            result = [r for r in result if r.disposition == disposition]
        return tuple(result)

    def get_session(self, session_id: str) -> AdversarialSession:
        """Get an adversarial session by ID."""
        if session_id not in self._sessions:
            raise RuntimeCoreInvariantError(f"session '{session_id}' not found")
        return self._sessions[session_id]

    def get_outcome(self, outcome_id: str) -> AdversarialOutcome:
        """Get an adversarial outcome by ID."""
        if outcome_id not in self._outcomes:
            raise RuntimeCoreInvariantError(f"outcome '{outcome_id}' not found")
        return self._outcomes[outcome_id]

    def get_outcomes_for_session(
        self, session_id: str,
    ) -> tuple[AdversarialOutcome, ...]:
        """Get all outcomes for a session."""
        return tuple(
            o for o in self._outcomes.values()
            if o.session_id == session_id
        )

    # -----------------------------------------------------------------------
    # Built-in fault families
    # -----------------------------------------------------------------------

    def register_provider_storm(
        self, count: int = 5, severity: FaultSeverity = FaultSeverity.HIGH,
    ) -> tuple[FaultSpec, ...]:
        """Register a provider failure storm family."""
        specs = []
        now = _now_iso()
        for i, ft in enumerate([FaultType.TIMEOUT, FaultType.FAILURE, FaultType.UNAVAILABLE]):
            spec = FaultSpec(
                spec_id=f"provider-storm-{ft.value}-{i}",
                fault_type=ft,
                target_kind=FaultTargetKind.PROVIDER,
                severity=severity,
                injection_mode=InjectionMode.REPEATED,
                repeat_count=count,
                description=f"Provider {ft.value} storm ({count}x)",
                tags=("provider-storm",),
                created_at=now,
            )
            self.register_spec(spec)
            specs.append(spec)
        return tuple(specs)

    def register_event_flood(
        self, count: int = 100, severity: FaultSeverity = FaultSeverity.MEDIUM,
    ) -> tuple[FaultSpec, ...]:
        """Register an event flood family."""
        now = _now_iso()
        specs = []
        for i, ft in enumerate([FaultType.OVERLOAD, FaultType.DUPLICATE]):
            spec = FaultSpec(
                spec_id=f"event-flood-{ft.value}-{i}",
                fault_type=ft,
                target_kind=FaultTargetKind.EVENT_SPINE,
                severity=severity,
                injection_mode=InjectionMode.REPEATED,
                repeat_count=count,
                description=f"Event {ft.value} flood ({count}x)",
                tags=("event-flood",),
                created_at=now,
            )
            self.register_spec(spec)
            specs.append(spec)
        return tuple(specs)

    def register_checkpoint_corruption(
        self, severity: FaultSeverity = FaultSeverity.CRITICAL,
    ) -> tuple[FaultSpec, ...]:
        """Register checkpoint corruption family."""
        now = _now_iso()
        specs = []
        for i, ft in enumerate([FaultType.CORRUPTION, FaultType.MISMATCH]):
            spec = FaultSpec(
                spec_id=f"checkpoint-corrupt-{ft.value}-{i}",
                fault_type=ft,
                target_kind=FaultTargetKind.CHECKPOINT,
                severity=severity,
                injection_mode=InjectionMode.SINGLE,
                repeat_count=1,
                description=f"Checkpoint {ft.value}",
                tags=("checkpoint-corruption",),
                created_at=now,
            )
            self.register_spec(spec)
            specs.append(spec)
        return tuple(specs)

    def register_communication_failure(
        self, count: int = 3, severity: FaultSeverity = FaultSeverity.MEDIUM,
    ) -> tuple[FaultSpec, ...]:
        """Register communication failure family."""
        now = _now_iso()
        specs = []
        for i, ft in enumerate([FaultType.FAILURE, FaultType.TRUNCATION, FaultType.UNAVAILABLE]):
            spec = FaultSpec(
                spec_id=f"comm-failure-{ft.value}-{i}",
                fault_type=ft,
                target_kind=FaultTargetKind.COMMUNICATION,
                severity=severity,
                injection_mode=InjectionMode.REPEATED,
                repeat_count=count,
                description=f"Communication {ft.value} ({count}x)",
                tags=("communication-failure",),
                created_at=now,
            )
            self.register_spec(spec)
            specs.append(spec)
        return tuple(specs)

    def register_artifact_corruption(
        self, severity: FaultSeverity = FaultSeverity.MEDIUM,
    ) -> tuple[FaultSpec, ...]:
        """Register artifact ingestion corruption family."""
        now = _now_iso()
        specs = []
        for i, ft in enumerate([FaultType.CORRUPTION, FaultType.POLICY_BLOCK, FaultType.MISMATCH]):
            spec = FaultSpec(
                spec_id=f"artifact-corrupt-{ft.value}-{i}",
                fault_type=ft,
                target_kind=FaultTargetKind.ARTIFACT_INGESTION,
                severity=severity,
                injection_mode=InjectionMode.SINGLE,
                repeat_count=1,
                description=f"Artifact {ft.value}",
                tags=("artifact-corruption",),
                created_at=now,
            )
            self.register_spec(spec)
            specs.append(spec)
        return tuple(specs)

    def register_obligation_escalation_stress(
        self, count: int = 5, severity: FaultSeverity = FaultSeverity.HIGH,
    ) -> tuple[FaultSpec, ...]:
        """Register obligation escalation chain stress family."""
        now = _now_iso()
        specs = []
        for i, ft in enumerate([FaultType.TIMEOUT, FaultType.UNAVAILABLE, FaultType.FAILURE]):
            spec = FaultSpec(
                spec_id=f"obligation-stress-{ft.value}-{i}",
                fault_type=ft,
                target_kind=FaultTargetKind.OBLIGATION_RUNTIME,
                severity=severity,
                injection_mode=InjectionMode.REPEATED,
                repeat_count=count,
                description=f"Obligation escalation {ft.value} ({count}x)",
                tags=("obligation-stress",),
                created_at=now,
            )
            self.register_spec(spec)
            specs.append(spec)
        return tuple(specs)

    def register_governance_conflict_storm(
        self, severity: FaultSeverity = FaultSeverity.HIGH,
    ) -> tuple[FaultSpec, ...]:
        """Register governance conflict storm family."""
        now = _now_iso()
        specs = []
        for i, ft in enumerate([FaultType.CONFLICT, FaultType.POLICY_BLOCK]):
            spec = FaultSpec(
                spec_id=f"governance-storm-{ft.value}-{i}",
                fault_type=ft,
                target_kind=FaultTargetKind.GOVERNANCE,
                severity=severity,
                injection_mode=InjectionMode.REPEATED,
                repeat_count=3,
                description=f"Governance {ft.value} storm",
                tags=("governance-storm",),
                created_at=now,
            )
            self.register_spec(spec)
            specs.append(spec)
        return tuple(specs)

    def register_domain_pack_conflict_stress(
        self, severity: FaultSeverity = FaultSeverity.MEDIUM,
    ) -> tuple[FaultSpec, ...]:
        """Register domain-pack conflict and override stress family."""
        now = _now_iso()
        specs = []
        for i, ft in enumerate([FaultType.CONFLICT, FaultType.MISMATCH]):
            spec = FaultSpec(
                spec_id=f"dompack-stress-{ft.value}-{i}",
                fault_type=ft,
                target_kind=FaultTargetKind.DOMAIN_PACK,
                severity=severity,
                injection_mode=InjectionMode.REPEATED,
                repeat_count=3,
                description=f"Domain pack {ft.value} stress",
                tags=("domain-pack-stress",),
                created_at=now,
            )
            self.register_spec(spec)
            specs.append(spec)
        return tuple(specs)

    # -----------------------------------------------------------------------
    # Properties
    # -----------------------------------------------------------------------

    @property
    def spec_count(self) -> int:
        return len(self._specs)

    @property
    def record_count(self) -> int:
        return len(self._records)

    @property
    def observation_count(self) -> int:
        return len(self._observations)

    @property
    def assessment_count(self) -> int:
        return len(self._assessments)

    @property
    def session_count(self) -> int:
        return len(self._sessions)

    @property
    def outcome_count(self) -> int:
        return len(self._outcomes)

    def state_hash(self) -> str:
        """Deterministic hash over all engine state."""
        h = sha256()
        for sid in sorted(self._specs):
            s = self._specs[sid]
            h.update(f"spec:{sid}:{s.fault_type}:{s.target_kind}:{s.severity}".encode())
        for r in self._records:
            h.update(f"rec:{r.record_id}:{r.spec_id}:{r.tick_number}".encode())
        for oid in sorted(self._observations):
            o = self._observations[oid]
            h.update(f"obs:{oid}:{o.matches_expected}".encode())
        for aid in sorted(self._assessments):
            a = self._assessments[aid]
            h.update(f"assess:{aid}:{a.recovered}:{a.state_consistent}".encode())
        for sid in sorted(self._sessions):
            h.update(f"session:{sid}".encode())
        for oid in sorted(self._outcomes):
            o = self._outcomes[oid]
            h.update(f"outcome:{oid}:{o.passed}:{o.score}".encode())
        return h.hexdigest()
