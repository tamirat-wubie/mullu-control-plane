"""Purpose: recovery decision engine — governed incident response.
Governance scope: recovery evaluation and attempt orchestration only.
Dependencies: incident contracts, autonomy contracts, invariant helpers.
Invariants:
  - No recovery action proceeds without governance check.
  - Retries are bounded, not infinite.
  - Rollbacks require explicit approval in approval-required mode.
  - Escalation is always available as a fallback.
  - All decisions and attempts are fully auditable.
"""

from __future__ import annotations

from typing import Callable

from mcoi_runtime.contracts.incident import (
    IncidentRecord,
    IncidentSeverity,
    IncidentStatus,
    RecoveryAction,
    RecoveryAttempt,
    RecoveryDecision,
    RecoveryDecisionStatus,
)
from .invariants import ensure_non_empty_text, stable_identifier


# Actions permitted per autonomy mode
_MODE_ALLOWED_ACTIONS: dict[str, frozenset[RecoveryAction]] = {
    "observe_only": frozenset({RecoveryAction.REOBSERVE, RecoveryAction.ESCALATE, RecoveryAction.NO_ACTION}),
    "suggest_only": frozenset({RecoveryAction.REOBSERVE, RecoveryAction.ESCALATE, RecoveryAction.NO_ACTION, RecoveryAction.SKIP}),
    "approval_required": frozenset({
        RecoveryAction.REOBSERVE, RecoveryAction.ESCALATE, RecoveryAction.NO_ACTION,
        RecoveryAction.SKIP,
        # retry/replan/rollback allowed only with approval (handled separately)
    }),
    "bounded_autonomous": frozenset({
        RecoveryAction.RETRY, RecoveryAction.RETRY_VARIANT, RecoveryAction.REOBSERVE,
        RecoveryAction.REPLAN, RecoveryAction.ESCALATE, RecoveryAction.SKIP, RecoveryAction.NO_ACTION,
        # rollback still requires explicit decision even in autonomous mode
    }),
}

# Actions that require approval even in approval_required mode
_APPROVAL_GATED_ACTIONS = frozenset({RecoveryAction.RETRY, RecoveryAction.RETRY_VARIANT, RecoveryAction.REPLAN, RecoveryAction.ROLLBACK})

MAX_RETRY_ATTEMPTS = 3


class RecoveryEngine:
    """Evaluates and executes governed recovery actions for incidents.

    Rules:
    - Autonomy mode restricts which actions are available
    - Rollback always requires explicit approval
    - Retries are bounded to MAX_RETRY_ATTEMPTS
    - Escalation is always available
    - All decisions are recorded
    """

    def __init__(self, *, clock: Callable[[], str]) -> None:
        self._clock = clock
        self._incidents: dict[str, IncidentRecord] = {}
        self._decisions: list[RecoveryDecision] = []
        self._attempts: list[RecoveryAttempt] = []
        self._retry_counts: dict[str, int] = {}

    def register_incident(self, incident: IncidentRecord) -> IncidentRecord:
        """Register a new incident."""
        self._incidents[incident.incident_id] = incident
        return incident

    def get_incident(self, incident_id: str) -> IncidentRecord | None:
        return self._incidents.get(incident_id)

    def list_open_incidents(self) -> tuple[IncidentRecord, ...]:
        return tuple(
            i for i in sorted(self._incidents.values(), key=lambda x: x.incident_id)
            if i.status in (IncidentStatus.OPEN, IncidentStatus.RECOVERING)
        )

    def decide(
        self,
        incident_id: str,
        action: RecoveryAction,
        *,
        autonomy_mode: str,
        profile_id: str | None = None,
        has_approval: bool = False,
    ) -> RecoveryDecision:
        """Evaluate whether a recovery action is permitted."""
        ensure_non_empty_text("incident_id", incident_id)

        incident = self._incidents.get(incident_id)
        if incident is None:
            decision = RecoveryDecision(
                decision_id=self._make_id("recovery-decision"),
                incident_id=incident_id,
                action=action,
                status=RecoveryDecisionStatus.NOT_APPLICABLE,
                reason="incident not found",
                autonomy_mode=autonomy_mode,
                profile_id=profile_id,
            )
            self._decisions.append(decision)
            return decision

        # Check retry limit
        if action in (RecoveryAction.RETRY, RecoveryAction.RETRY_VARIANT):
            count = self._retry_counts.get(incident_id, 0)
            if count >= MAX_RETRY_ATTEMPTS:
                decision = RecoveryDecision(
                    decision_id=self._make_id("recovery-decision"),
                    incident_id=incident_id,
                    action=action,
                    status=RecoveryDecisionStatus.BLOCKED_POLICY,
                    reason="retry limit reached",
                    autonomy_mode=autonomy_mode,
                    profile_id=profile_id,
                )
                self._decisions.append(decision)
                return decision

        # Check autonomy mode
        allowed = _MODE_ALLOWED_ACTIONS.get(autonomy_mode, frozenset())

        # Approval-gated actions in approval_required mode
        if autonomy_mode == "approval_required" and action in _APPROVAL_GATED_ACTIONS:
            if has_approval:
                status = RecoveryDecisionStatus.APPROVED
                reason = "recovery action approved by operator"
            else:
                status = RecoveryDecisionStatus.BLOCKED_AUTONOMY
                reason = "approval required for recovery action"
        elif action in allowed:
            status = RecoveryDecisionStatus.APPROVED
            reason = "recovery action permitted"
        elif action is RecoveryAction.ROLLBACK:
            # Rollback always needs explicit approval
            if has_approval:
                status = RecoveryDecisionStatus.APPROVED
                reason = "rollback approved by operator"
            else:
                status = RecoveryDecisionStatus.BLOCKED_AUTONOMY
                reason = "rollback requires explicit approval"
        else:
            status = RecoveryDecisionStatus.BLOCKED_AUTONOMY
            reason = "recovery action blocked by autonomy mode"

        decision = RecoveryDecision(
            decision_id=self._make_id("recovery-decision"),
            incident_id=incident_id,
            action=action,
            status=status,
            reason=reason,
            autonomy_mode=autonomy_mode,
            profile_id=profile_id,
        )
        self._decisions.append(decision)
        return decision

    def record_attempt(
        self,
        decision: RecoveryDecision,
        *,
        succeeded: bool,
        error_message: str | None = None,
        result_run_id: str | None = None,
    ) -> RecoveryAttempt:
        """Record the outcome of executing a recovery action."""
        started_at = self._clock()
        attempt = RecoveryAttempt(
            attempt_id=self._make_id("recovery-attempt"),
            incident_id=decision.incident_id,
            decision_id=decision.decision_id,
            action=decision.action,
            succeeded=succeeded,
            started_at=started_at,
            finished_at=self._clock(),
            error_message=error_message,
            result_run_id=result_run_id,
        )
        self._attempts.append(attempt)

        # Track retry count
        if decision.action in (RecoveryAction.RETRY, RecoveryAction.RETRY_VARIANT):
            self._retry_counts[decision.incident_id] = self._retry_counts.get(decision.incident_id, 0) + 1

        return attempt

    def list_decisions(self) -> tuple[RecoveryDecision, ...]:
        return tuple(self._decisions)

    def list_attempts(self) -> tuple[RecoveryAttempt, ...]:
        return tuple(self._attempts)

    def _make_id(self, prefix: str) -> str:
        return stable_identifier(prefix, {
            "count": len(self._decisions) + len(self._attempts),
            "time": self._clock(),
        })
