"""Purpose: autonomous improvement loop engine.
Governance scope: evaluating recommendations for autonomous promotion,
    enforcing autonomy policies, managing learning windows, triggering
    rollbacks, suppressing bad patterns, reinforcing successful changes.
Dependencies: autonomous_improvement contracts, event_spine, core invariants.
Invariants:
  - Autonomy policies gate all auto-promotion decisions.
  - Suppressed patterns cannot be auto-promoted.
  - Rollback triggers fire when KPI degrades beyond tolerance.
  - Every mutation emits an event.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from ..contracts.autonomous_improvement import (
    AutonomyLevel,
    AutonomyPolicy,
    ImprovementCandidate,
    ImprovementDisposition,
    ImprovementOutcome,
    ImprovementOutcomeVerdict,
    ImprovementSession,
    LearningWindow,
    LearningWindowStatus,
    RollbackTrigger,
    SuppressionReason,
    SuppressionRecord,
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
        event_id=stable_identifier("evt-aim", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class AutonomousImprovementEngine:
    """Engine for autonomous improvement loop management."""

    def __init__(self, event_spine: EventSpineEngine) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._policies: dict[str, AutonomyPolicy] = {}
        self._candidates: dict[str, ImprovementCandidate] = {}
        self._sessions: dict[str, ImprovementSession] = {}
        self._windows: dict[str, LearningWindow] = {}
        self._suppressions: dict[str, SuppressionRecord] = {}
        self._outcomes: dict[str, ImprovementOutcome] = {}
        self._rollback_triggers: list[RollbackTrigger] = []
        # Track failure counts per (change_type, scope_ref_id)
        self._failure_counts: dict[tuple[str, str], int] = {}
        # Track auto-changes in current window
        self._auto_change_count: int = 0

    # ------------------------------------------------------------------
    # Policy management
    # ------------------------------------------------------------------

    def register_policy(
        self,
        policy_id: str,
        change_type: str = "",
        *,
        min_confidence: float = 0.8,
        max_risk_score: float = 0.3,
        max_cost_delta: float = 100.0,
        max_auto_changes_per_window: int = 5,
        require_approval_above_cost: float = 500.0,
        require_approval_above_risk: float = 0.5,
        failure_suppression_threshold: int = 3,
        learning_window_seconds: float = 3600.0,
        rollback_tolerance_pct: float = 5.0,
        enabled: bool = True,
    ) -> AutonomyPolicy:
        if policy_id in self._policies:
            raise RuntimeCoreInvariantError(f"policy '{policy_id}' already exists")
        now = _now_iso()
        policy = AutonomyPolicy(
            policy_id=policy_id,
            change_type=change_type,
            min_confidence=min_confidence,
            max_risk_score=max_risk_score,
            max_cost_delta=max_cost_delta,
            max_auto_changes_per_window=max_auto_changes_per_window,
            require_approval_above_cost=require_approval_above_cost,
            require_approval_above_risk=require_approval_above_risk,
            failure_suppression_threshold=failure_suppression_threshold,
            learning_window_seconds=learning_window_seconds,
            rollback_tolerance_pct=rollback_tolerance_pct,
            enabled=enabled,
            created_at=now,
        )
        self._policies[policy_id] = policy
        _emit(self._events, "policy_registered", {
            "policy_id": policy_id,
            "change_type": change_type,
        }, policy_id)
        return policy

    def get_policy(self, policy_id: str) -> AutonomyPolicy | None:
        return self._policies.get(policy_id)

    def find_policy_for_type(self, change_type: str) -> AutonomyPolicy | None:
        """Find the most specific policy for a change type."""
        for p in self._policies.values():
            if p.change_type == change_type and p.enabled:
                return p
        # Fall back to default (empty change_type)
        for p in self._policies.values():
            if p.change_type == "" and p.enabled:
                return p
        return None

    # ------------------------------------------------------------------
    # Candidate evaluation
    # ------------------------------------------------------------------

    def evaluate_candidate(
        self,
        candidate_id: str,
        recommendation_id: str,
        title: str,
        *,
        change_type: str = "",
        scope_ref_id: str = "",
        confidence: float = 0.0,
        estimated_improvement_pct: float = 0.0,
        estimated_cost_delta: float = 0.0,
        risk_score: float = 0.0,
        metadata: dict[str, Any] | None = None,
    ) -> ImprovementCandidate:
        """Evaluate a recommendation and determine its disposition."""
        if candidate_id in self._candidates:
            raise RuntimeCoreInvariantError(f"candidate '{candidate_id}' already exists")

        now = _now_iso()
        policy = self.find_policy_for_type(change_type)

        # Check suppression
        suppression_key = (change_type, scope_ref_id)
        if self._is_suppressed(change_type, scope_ref_id):
            disposition = ImprovementDisposition.SUPPRESSED
            autonomy = AutonomyLevel.FULL_HUMAN
            reason = "pattern suppressed due to prior failures"
        elif policy is None:
            disposition = ImprovementDisposition.APPROVAL_REQUIRED
            autonomy = AutonomyLevel.APPROVAL_REQUIRED
            reason = "no autonomy policy found"
        elif not policy.enabled:
            disposition = ImprovementDisposition.APPROVAL_REQUIRED
            autonomy = AutonomyLevel.APPROVAL_REQUIRED
            reason = "policy disabled"
        else:
            disposition, autonomy, reason = self._evaluate_against_policy(
                policy, confidence, risk_score, estimated_cost_delta,
            )

        candidate = ImprovementCandidate(
            candidate_id=candidate_id,
            recommendation_id=recommendation_id,
            change_type=change_type,
            scope_ref_id=scope_ref_id,
            title=title,
            confidence=confidence,
            estimated_improvement_pct=estimated_improvement_pct,
            estimated_cost_delta=estimated_cost_delta,
            risk_score=risk_score,
            disposition=disposition,
            autonomy_level=autonomy,
            reason=reason,
            created_at=now,
            metadata=metadata or {},
        )
        self._candidates[candidate_id] = candidate

        if disposition == ImprovementDisposition.AUTO_PROMOTED:
            self._auto_change_count += 1

        _emit(self._events, "candidate_evaluated", {
            "candidate_id": candidate_id,
            "disposition": disposition.value,
            "autonomy_level": autonomy.value,
            "confidence": confidence,
            "risk_score": risk_score,
        }, candidate_id)
        return candidate

    def _evaluate_against_policy(
        self,
        policy: AutonomyPolicy,
        confidence: float,
        risk_score: float,
        cost_delta: float,
    ) -> tuple[ImprovementDisposition, AutonomyLevel, str]:
        """Evaluate candidate against autonomy policy."""
        # Check if auto-change window is exhausted
        if self._auto_change_count >= policy.max_auto_changes_per_window:
            return (
                ImprovementDisposition.APPROVAL_REQUIRED,
                AutonomyLevel.APPROVAL_REQUIRED,
                f"auto-change limit reached ({policy.max_auto_changes_per_window})",
            )

        # Check confidence threshold
        if confidence < policy.min_confidence:
            return (
                ImprovementDisposition.APPROVAL_REQUIRED,
                AutonomyLevel.APPROVAL_REQUIRED,
                f"confidence {confidence:.2f} below minimum {policy.min_confidence:.2f}",
            )

        # Check risk threshold
        if risk_score > policy.max_risk_score:
            if risk_score > policy.require_approval_above_risk:
                return (
                    ImprovementDisposition.APPROVAL_REQUIRED,
                    AutonomyLevel.FULL_HUMAN,
                    f"risk score {risk_score:.2f} exceeds approval threshold {policy.require_approval_above_risk:.2f}",
                )
            return (
                ImprovementDisposition.APPROVAL_REQUIRED,
                AutonomyLevel.APPROVAL_REQUIRED,
                f"risk score {risk_score:.2f} exceeds max {policy.max_risk_score:.2f}",
            )

        # Check cost threshold
        if abs(cost_delta) > policy.max_cost_delta:
            if abs(cost_delta) > policy.require_approval_above_cost:
                return (
                    ImprovementDisposition.APPROVAL_REQUIRED,
                    AutonomyLevel.FULL_HUMAN,
                    f"cost delta {cost_delta:.2f} exceeds approval threshold {policy.require_approval_above_cost:.2f}",
                )
            return (
                ImprovementDisposition.APPROVAL_REQUIRED,
                AutonomyLevel.APPROVAL_REQUIRED,
                f"cost delta {cost_delta:.2f} exceeds max {policy.max_cost_delta:.2f}",
            )

        # All checks passed — auto-promote
        return (
            ImprovementDisposition.AUTO_PROMOTED,
            AutonomyLevel.BOUNDED_AUTO,
            "meets all autonomy policy thresholds",
        )

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    def start_session(
        self,
        session_id: str,
        candidate_id: str,
        change_id: str = "",
    ) -> ImprovementSession:
        if session_id in self._sessions:
            raise RuntimeCoreInvariantError(f"session '{session_id}' already exists")
        if candidate_id not in self._candidates:
            raise RuntimeCoreInvariantError(f"candidate '{candidate_id}' not found")

        candidate = self._candidates[candidate_id]
        now = _now_iso()
        session = ImprovementSession(
            session_id=session_id,
            candidate_id=candidate_id,
            change_id=change_id,
            autonomy_level=candidate.autonomy_level,
            disposition=candidate.disposition,
            started_at=now,
        )
        self._sessions[session_id] = session

        _emit(self._events, "session_started", {
            "session_id": session_id,
            "candidate_id": candidate_id,
            "autonomy_level": candidate.autonomy_level.value,
        }, session_id)
        return session

    def get_session(self, session_id: str) -> ImprovementSession | None:
        return self._sessions.get(session_id)

    # ------------------------------------------------------------------
    # Learning windows
    # ------------------------------------------------------------------

    def open_learning_window(
        self,
        window_id: str,
        change_id: str,
        metric_name: str,
        baseline_value: float,
        *,
        candidate_id: str = "",
        duration_seconds: float = 3600.0,
    ) -> LearningWindow:
        if window_id in self._windows:
            raise RuntimeCoreInvariantError(f"window '{window_id}' already exists")
        now = _now_iso()
        window = LearningWindow(
            window_id=window_id,
            change_id=change_id,
            candidate_id=candidate_id,
            metric_name=metric_name,
            baseline_value=baseline_value,
            duration_seconds=duration_seconds,
            status=LearningWindowStatus.ACTIVE,
            current_value=baseline_value,
            started_at=now,
        )
        self._windows[window_id] = window

        _emit(self._events, "learning_window_opened", {
            "window_id": window_id,
            "change_id": change_id,
            "metric_name": metric_name,
            "baseline_value": baseline_value,
        }, window_id)
        return window

    def record_observation(
        self,
        window_id: str,
        observed_value: float,
    ) -> LearningWindow:
        if window_id not in self._windows:
            raise RuntimeCoreInvariantError(f"window '{window_id}' not found")
        old = self._windows[window_id]
        if old.status != LearningWindowStatus.ACTIVE:
            raise RuntimeCoreInvariantError(f"window '{window_id}' is not active")

        baseline = old.baseline_value
        improvement = ((observed_value - baseline) / abs(baseline) * 100) if baseline != 0 else 0.0

        updated = LearningWindow(
            window_id=old.window_id,
            change_id=old.change_id,
            candidate_id=old.candidate_id,
            metric_name=old.metric_name,
            baseline_value=old.baseline_value,
            duration_seconds=old.duration_seconds,
            status=LearningWindowStatus.ACTIVE,
            current_value=observed_value,
            improvement_pct=improvement,
            samples_collected=old.samples_collected + 1,
            started_at=old.started_at,
        )
        self._windows[window_id] = updated
        return updated

    def close_learning_window(
        self,
        window_id: str,
        *,
        status: LearningWindowStatus = LearningWindowStatus.COMPLETED,
    ) -> LearningWindow:
        if window_id not in self._windows:
            raise RuntimeCoreInvariantError(f"window '{window_id}' not found")
        old = self._windows[window_id]
        now = _now_iso()
        updated = LearningWindow(
            window_id=old.window_id,
            change_id=old.change_id,
            candidate_id=old.candidate_id,
            metric_name=old.metric_name,
            baseline_value=old.baseline_value,
            duration_seconds=old.duration_seconds,
            status=status,
            current_value=old.current_value,
            improvement_pct=old.improvement_pct,
            samples_collected=old.samples_collected,
            started_at=old.started_at,
            completed_at=now,
        )
        self._windows[window_id] = updated

        _emit(self._events, "learning_window_closed", {
            "window_id": window_id,
            "status": status.value,
            "improvement_pct": old.improvement_pct,
        }, window_id)
        return updated

    # ------------------------------------------------------------------
    # Rollback trigger evaluation
    # ------------------------------------------------------------------

    def check_rollback_trigger(
        self,
        change_id: str,
        session_id: str,
        metric_name: str,
        baseline_value: float,
        observed_value: float,
        *,
        tolerance_pct: float | None = None,
    ) -> RollbackTrigger | None:
        """Check if observed value degrades beyond tolerance. Returns trigger if so."""
        # Find applicable policy
        candidate_id = None
        session = self._sessions.get(session_id)
        if session:
            candidate_id = session.candidate_id
        candidate = self._candidates.get(candidate_id or "")
        policy = self.find_policy_for_type(candidate.change_type if candidate else "")

        tol = tolerance_pct if tolerance_pct is not None else (
            policy.rollback_tolerance_pct if policy else 5.0
        )

        if baseline_value == 0:
            return None

        degradation = ((baseline_value - observed_value) / abs(baseline_value)) * 100
        if degradation > tol:
            now = _now_iso()
            trigger = RollbackTrigger(
                trigger_id=stable_identifier("rbkt", {"cid": change_id, "m": metric_name, "ts": now}),
                change_id=change_id,
                session_id=session_id,
                metric_name=metric_name,
                baseline_value=baseline_value,
                observed_value=observed_value,
                degradation_pct=degradation,
                tolerance_pct=tol,
                triggered_at=now,
            )
            self._rollback_triggers.append(trigger)

            _emit(self._events, "rollback_triggered", {
                "change_id": change_id,
                "metric_name": metric_name,
                "degradation_pct": degradation,
                "tolerance_pct": tol,
            }, change_id)
            return trigger
        return None

    # ------------------------------------------------------------------
    # Suppression
    # ------------------------------------------------------------------

    def record_failure(
        self,
        change_type: str,
        scope_ref_id: str,
    ) -> SuppressionRecord | None:
        """Record a failure and suppress if threshold is reached."""
        key = (change_type, scope_ref_id)
        self._failure_counts[key] = self._failure_counts.get(key, 0) + 1
        count = self._failure_counts[key]

        policy = self.find_policy_for_type(change_type)
        threshold = policy.failure_suppression_threshold if policy else 3

        if count >= threshold:
            return self._suppress(change_type, scope_ref_id, SuppressionReason.REPEATED_FAILURE, count)
        return None

    def suppress_pattern(
        self,
        change_type: str,
        scope_ref_id: str,
        reason: SuppressionReason,
    ) -> SuppressionRecord:
        """Manually suppress a pattern."""
        count = self._failure_counts.get((change_type, scope_ref_id), 0)
        return self._suppress(change_type, scope_ref_id, reason, count)

    def _suppress(
        self,
        change_type: str,
        scope_ref_id: str,
        reason: SuppressionReason,
        failure_count: int,
    ) -> SuppressionRecord:
        now = _now_iso()
        key = f"{change_type}:{scope_ref_id}"
        record = SuppressionRecord(
            suppression_id=stable_identifier("supp", {"k": key, "ts": now}),
            change_type=change_type,
            scope_ref_id=scope_ref_id,
            reason=reason,
            failure_count=failure_count,
            suppressed_at=now,
        )
        self._suppressions[key] = record

        _emit(self._events, "pattern_suppressed", {
            "change_type": change_type,
            "scope_ref_id": scope_ref_id,
            "reason": reason.value,
            "failure_count": failure_count,
        }, key)
        return record

    def _is_suppressed(self, change_type: str, scope_ref_id: str) -> bool:
        return f"{change_type}:{scope_ref_id}" in self._suppressions

    def is_suppressed(self, change_type: str, scope_ref_id: str) -> bool:
        return self._is_suppressed(change_type, scope_ref_id)

    def get_suppressions(self) -> tuple[SuppressionRecord, ...]:
        return tuple(self._suppressions.values())

    # ------------------------------------------------------------------
    # Outcome assessment
    # ------------------------------------------------------------------

    def assess_outcome(
        self,
        outcome_id: str,
        session_id: str,
        *,
        baseline_value: float = 0.0,
        final_value: float = 0.0,
        confidence: float = 0.8,
    ) -> ImprovementOutcome:
        if session_id not in self._sessions:
            raise RuntimeCoreInvariantError(f"session '{session_id}' not found")
        session = self._sessions[session_id]
        candidate = self._candidates.get(session.candidate_id)
        change_id = session.change_id

        if baseline_value == 0:
            improvement = 0.0
        else:
            improvement = ((final_value - baseline_value) / abs(baseline_value)) * 100

        # Determine verdict
        if improvement > 1.0:
            verdict = ImprovementOutcomeVerdict.IMPROVED
        elif improvement < -1.0:
            verdict = ImprovementOutcomeVerdict.DEGRADED
        elif confidence < 0.5:
            verdict = ImprovementOutcomeVerdict.INCONCLUSIVE
        else:
            verdict = ImprovementOutcomeVerdict.NEUTRAL

        # Handle consequences
        rollback_triggered = False
        suppression_triggered = False
        reinforcement_applied = False

        if verdict == ImprovementOutcomeVerdict.DEGRADED:
            # Record failure
            if candidate:
                supp = self.record_failure(candidate.change_type, candidate.scope_ref_id)
                suppression_triggered = supp is not None
            rollback_triggered = True

        elif verdict == ImprovementOutcomeVerdict.IMPROVED:
            reinforcement_applied = True

        now = _now_iso()
        outcome = ImprovementOutcome(
            outcome_id=outcome_id,
            session_id=session_id,
            candidate_id=session.candidate_id,
            change_id=change_id,
            verdict=verdict,
            baseline_value=baseline_value,
            final_value=final_value,
            improvement_pct=improvement,
            confidence=confidence,
            rollback_triggered=rollback_triggered,
            suppression_triggered=suppression_triggered,
            reinforcement_applied=reinforcement_applied,
            assessed_at=now,
        )
        self._outcomes[outcome_id] = outcome

        # Update session
        old_session = self._sessions[session_id]
        updated_session = ImprovementSession(
            session_id=old_session.session_id,
            candidate_id=old_session.candidate_id,
            change_id=old_session.change_id,
            autonomy_level=old_session.autonomy_level,
            disposition=ImprovementDisposition.COMPLETED if verdict != ImprovementOutcomeVerdict.DEGRADED else ImprovementDisposition.ROLLED_BACK,
            verdict=verdict,
            improvement_pct=improvement,
            rollback_triggered=rollback_triggered,
            suppression_applied=suppression_triggered,
            learning_window_ids=old_session.learning_window_ids,
            started_at=old_session.started_at,
            completed_at=now,
            metadata=dict(old_session.metadata),
        )
        self._sessions[session_id] = updated_session

        _emit(self._events, "outcome_assessed", {
            "outcome_id": outcome_id,
            "session_id": session_id,
            "verdict": verdict.value,
            "improvement_pct": improvement,
            "rollback_triggered": rollback_triggered,
            "reinforcement_applied": reinforcement_applied,
        }, outcome_id)
        return outcome

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_candidate(self, candidate_id: str) -> ImprovementCandidate | None:
        return self._candidates.get(candidate_id)

    def get_outcome(self, outcome_id: str) -> ImprovementOutcome | None:
        return self._outcomes.get(outcome_id)

    def get_learning_window(self, window_id: str) -> LearningWindow | None:
        return self._windows.get(window_id)

    def get_rollback_triggers(self) -> tuple[RollbackTrigger, ...]:
        return tuple(self._rollback_triggers)

    @property
    def candidate_count(self) -> int:
        return len(self._candidates)

    @property
    def session_count(self) -> int:
        return len(self._sessions)

    @property
    def outcome_count(self) -> int:
        return len(self._outcomes)

    @property
    def suppression_count(self) -> int:
        return len(self._suppressions)

    @property
    def auto_change_count(self) -> int:
        return self._auto_change_count

    # ------------------------------------------------------------------
    # State hash
    # ------------------------------------------------------------------

    def state_hash(self) -> str:
        parts = [
            f"auto_changes={self._auto_change_count}",
        ]
        for cid in sorted(self._candidates):
            c = self._candidates[cid]
            parts.append(f"cand:{cid}:{c.disposition.value}")
        for sid in sorted(self._sessions):
            s = self._sessions[sid]
            parts.append(f"sess:{sid}:{s.disposition.value}:{s.verdict.value}")
        for oid in sorted(self._outcomes):
            o = self._outcomes[oid]
            parts.append(f"out:{oid}:{o.verdict.value}")
        for sk in sorted(self._suppressions):
            sr = self._suppressions[sk]
            parts.append(f"supp:{sk}:{sr.reason.value}:{sr.failure_count}")
        digest = sha256("|".join(parts).encode()).hexdigest()
        return digest
