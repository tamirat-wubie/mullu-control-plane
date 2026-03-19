"""Purpose: autonomy mode evaluation — action gating by runtime mode.
Governance scope: autonomy enforcement logic only.
Dependencies: autonomy contracts, invariant helpers.
Invariants:
  - Mode boundaries are enforced before dispatch.
  - Unknown action classes fail closed (rejected).
  - OBSERVE_ONLY and SUGGEST_ONLY never permit execution.
  - APPROVAL_REQUIRED blocks execution without explicit approval.
  - BOUNDED_AUTONOMOUS permits governed actions within scope.
"""

from __future__ import annotations

from mcoi_runtime.contracts.autonomy import (
    ActionClass,
    AutonomyDecision,
    AutonomyDecisionStatus,
    AutonomyMode,
    AutonomyStatus,
    AutonomyViolation,
)
from .invariants import ensure_non_empty_text, stable_identifier


# --- Mode permission tables ---

_OBSERVE_ALLOWED: frozenset[ActionClass] = frozenset({
    ActionClass.OBSERVE,
    ActionClass.ANALYZE,
})

_SUGGEST_ALLOWED: frozenset[ActionClass] = frozenset({
    ActionClass.OBSERVE,
    ActionClass.ANALYZE,
    ActionClass.SUGGEST,
    ActionClass.PLAN,
})

_APPROVAL_ALLOWED_WITHOUT_APPROVAL: frozenset[ActionClass] = frozenset({
    ActionClass.OBSERVE,
    ActionClass.ANALYZE,
    ActionClass.SUGGEST,
    ActionClass.PLAN,
})

_APPROVAL_ALLOWED_WITH_APPROVAL: frozenset[ActionClass] = frozenset({
    ActionClass.OBSERVE,
    ActionClass.ANALYZE,
    ActionClass.SUGGEST,
    ActionClass.PLAN,
    ActionClass.EXECUTE_READ,
    ActionClass.EXECUTE_WRITE,
    ActionClass.COMMUNICATE,
    ActionClass.APPROVE,
})

_AUTONOMOUS_ALLOWED: frozenset[ActionClass] = frozenset({
    ActionClass.OBSERVE,
    ActionClass.ANALYZE,
    ActionClass.SUGGEST,
    ActionClass.PLAN,
    ActionClass.EXECUTE_READ,
    ActionClass.EXECUTE_WRITE,
    ActionClass.COMMUNICATE,
    ActionClass.APPROVE,
})


class AutonomyEngine:
    """Evaluates whether actions are permitted under the current autonomy mode.

    Tracks decisions and violations for operator visibility.
    """

    def __init__(self, mode: AutonomyMode) -> None:
        if not isinstance(mode, AutonomyMode):
            raise ValueError("mode must be an AutonomyMode value")
        self._mode = mode
        self._decisions: list[AutonomyDecision] = []
        self._violations: list[AutonomyViolation] = []

    @property
    def mode(self) -> AutonomyMode:
        return self._mode

    def evaluate(
        self,
        action_class: ActionClass,
        *,
        has_approval: bool = False,
        action_description: str = "",
    ) -> AutonomyDecision:
        """Evaluate whether an action is allowed under the current mode.

        Returns a typed decision with status and reason.
        """
        if not isinstance(action_class, ActionClass):
            decision = self._make_decision(
                action_class=ActionClass.OBSERVE,  # fallback for ID generation
                status=AutonomyDecisionStatus.REJECTED,
                reason="unknown action class",
            )
            self._decisions.append(decision)
            return decision

        decision = self._evaluate_mode(action_class, has_approval, action_description)
        self._decisions.append(decision)

        if decision.status is AutonomyDecisionStatus.REJECTED:
            self._violations.append(AutonomyViolation(
                violation_id=stable_identifier("violation", {
                    "decision_id": decision.decision_id,
                }),
                mode=self._mode,
                action_class=action_class,
                attempted_action=action_description or action_class.value,
                reason=decision.reason,
            ))

        return decision

    def _evaluate_mode(
        self,
        action_class: ActionClass,
        has_approval: bool,
        action_description: str,
    ) -> AutonomyDecision:
        if self._mode is AutonomyMode.OBSERVE_ONLY:
            if action_class in _OBSERVE_ALLOWED:
                return self._make_decision(action_class, AutonomyDecisionStatus.ALLOWED, "observe mode: action allowed")
            return self._make_decision(action_class, AutonomyDecisionStatus.REJECTED, f"observe mode: {action_class.value} not permitted")

        if self._mode is AutonomyMode.SUGGEST_ONLY:
            if action_class in _SUGGEST_ALLOWED:
                return self._make_decision(action_class, AutonomyDecisionStatus.ALLOWED, "suggest mode: action allowed")
            # Convert execution to suggestion
            if action_class in (ActionClass.EXECUTE_READ, ActionClass.EXECUTE_WRITE, ActionClass.COMMUNICATE):
                return self._make_decision(
                    action_class,
                    AutonomyDecisionStatus.CONVERTED_TO_SUGGESTION,
                    f"suggest mode: {action_class.value} converted to suggestion",
                    suggestion=f"suggested: {action_description or action_class.value}",
                )
            return self._make_decision(action_class, AutonomyDecisionStatus.REJECTED, f"suggest mode: {action_class.value} not permitted")

        if self._mode is AutonomyMode.APPROVAL_REQUIRED:
            if action_class in _APPROVAL_ALLOWED_WITHOUT_APPROVAL:
                return self._make_decision(action_class, AutonomyDecisionStatus.ALLOWED, "approval mode: planning action allowed")
            if has_approval and action_class in _APPROVAL_ALLOWED_WITH_APPROVAL:
                return self._make_decision(action_class, AutonomyDecisionStatus.ALLOWED, "approval mode: approved action allowed")
            if not has_approval:
                return self._make_decision(
                    action_class,
                    AutonomyDecisionStatus.BLOCKED_PENDING_APPROVAL,
                    f"approval mode: {action_class.value} requires approval",
                )
            return self._make_decision(action_class, AutonomyDecisionStatus.REJECTED, f"approval mode: {action_class.value} not permitted")

        if self._mode is AutonomyMode.BOUNDED_AUTONOMOUS:
            if action_class in _AUTONOMOUS_ALLOWED:
                return self._make_decision(action_class, AutonomyDecisionStatus.ALLOWED, "autonomous mode: action allowed within scope")
            return self._make_decision(action_class, AutonomyDecisionStatus.REJECTED, f"autonomous mode: {action_class.value} not permitted")

        # Unknown mode — fail closed
        return self._make_decision(action_class, AutonomyDecisionStatus.REJECTED, "unknown autonomy mode")

    def _make_decision(
        self,
        action_class: ActionClass,
        status: AutonomyDecisionStatus,
        reason: str,
        suggestion: str | None = None,
    ) -> AutonomyDecision:
        decision_id = stable_identifier("autonomy", {
            "mode": self._mode.value,
            "action_class": action_class.value,
            "decision_count": len(self._decisions),
        })
        return AutonomyDecision(
            decision_id=decision_id,
            mode=self._mode,
            action_class=action_class,
            status=status,
            reason=reason,
            suggestion=suggestion,
        )

    def get_status(self) -> AutonomyStatus:
        """Return current autonomy status for operator visibility."""
        return AutonomyStatus(
            mode=self._mode,
            total_decisions=len(self._decisions),
            allowed_count=sum(1 for d in self._decisions if d.status is AutonomyDecisionStatus.ALLOWED),
            blocked_count=sum(1 for d in self._decisions if d.status is AutonomyDecisionStatus.REJECTED),
            suggestion_count=sum(1 for d in self._decisions if d.status is AutonomyDecisionStatus.CONVERTED_TO_SUGGESTION),
            pending_approval_count=sum(1 for d in self._decisions if d.status is AutonomyDecisionStatus.BLOCKED_PENDING_APPROVAL),
            violations=tuple(self._violations),
        )
