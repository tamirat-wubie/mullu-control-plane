"""Explanation Engine — structured reasoning for governance decisions.

Purpose: generate human-readable explanations for any governed action,
    answering: why was it allowed/denied? which guard decided? what
    policy pack was active? what cost/risk path was chosen?
Governance scope: explanation generation only — read-only, never mutates.
Dependencies: audit trail (read), guard chain (read).
Invariants:
  - Explanations are deterministic given the same audit entry.
  - Never modifies runtime state.
  - Explanation cache is bounded.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class GovernanceExplanation:
    """Structured explanation of a governance decision."""

    explanation_id: str
    action: str
    actor_id: str
    target: str
    decision: str  # "allowed", "denied", "error"
    reasons: list[str]
    guard_chain_path: list[dict[str, Any]]
    policy_context: dict[str, Any]
    cost_context: dict[str, Any]
    timestamp: str
    confidence: str = "high"  # "high", "medium", "low"


class ExplanationEngine:
    """Generates structured explanations for governance decisions.

    Can explain:
    - Why an action was allowed or denied
    - Which guard in the chain made the decision
    - What policy pack was active
    - What cost/budget context applied
    - What the mission/goal hierarchy was
    """

    _MAX_CACHE = 5_000

    def __init__(
        self,
        *,
        clock: Callable[[], str],
        audit_trail: Any | None = None,
        guard_chain: Any | None = None,
    ) -> None:
        self._clock = clock
        self._audit_trail = audit_trail
        self._guard_chain = guard_chain
        self._cache: dict[str, GovernanceExplanation] = {}
        self._explanation_counter = 0
        self._lock = threading.Lock()

    def explain_action(
        self,
        action_type: str,
        target: str,
        *,
        tenant_id: str = "",
        budget_id: str = "",
        actor_id: str = "",
    ) -> GovernanceExplanation:
        """Generate an explanation for what would happen if this action ran now."""
        now = self._clock()
        with self._lock:
            self._explanation_counter += 1
            exp_id = f"exp-{self._explanation_counter:06d}"

        reasons: list[str] = []
        guard_path: list[dict[str, Any]] = []
        decision = "allowed"

        # Evaluate through guard chain
        if self._guard_chain is not None:
            ctx = {
                "action_type": action_type,
                "target": target,
                "tenant_id": tenant_id,
                "budget_id": budget_id,
                "agent_id": actor_id or "explanation",
            }
            result = self._guard_chain.evaluate(ctx)
            decision = "allowed" if result.allowed else "denied"

            if result.allowed:
                reasons.append("All governance guards passed")
                for guard_name in self._guard_chain.guard_names():
                    guard_path.append({"guard": guard_name, "result": "pass"})
            else:
                reasons.append(f"Blocked by {result.guard_name}: {result.reason}")
                for guard_name in self._guard_chain.guard_names():
                    if guard_name == result.guard_name:
                        guard_path.append({
                            "guard": guard_name,
                            "result": "deny",
                            "reason": result.reason,
                        })
                        break
                    guard_path.append({"guard": guard_name, "result": "pass"})
        else:
            reasons.append("No guard chain configured — default allow")

        # Cost context
        cost_ctx: dict[str, Any] = {}
        if budget_id:
            cost_ctx["budget_id"] = budget_id
            cost_ctx["note"] = "budget enforcement active"
        else:
            cost_ctx["note"] = "no budget bound"

        # Policy context
        policy_ctx: dict[str, Any] = {
            "tenant_id": tenant_id or "none",
            "action_type": action_type,
        }

        explanation = GovernanceExplanation(
            explanation_id=exp_id,
            action=action_type,
            actor_id=actor_id,
            target=target,
            decision=decision,
            reasons=reasons,
            guard_chain_path=guard_path,
            policy_context=policy_ctx,
            cost_context=cost_ctx,
            timestamp=now,
        )

        with self._lock:
            self._cache[exp_id] = explanation
            if len(self._cache) > self._MAX_CACHE:
                oldest = next(iter(self._cache))
                del self._cache[oldest]

        return explanation

    def explain_audit_entry(self, entry: Any) -> GovernanceExplanation:
        """Generate an explanation from an existing audit trail entry."""
        action = getattr(entry, "action", "unknown")
        actor_id = getattr(entry, "actor_id", "")
        target = getattr(entry, "target", "")
        outcome = getattr(entry, "outcome", "")
        detail = getattr(entry, "detail", {})
        timestamp = getattr(entry, "recorded_at", "")

        reasons = []
        if outcome == "success" or outcome == "allowed":
            reasons.append("Action completed successfully")
        elif outcome == "denied" or outcome == "blocked":
            guard = detail.get("guard", "unknown")
            reason = detail.get("reason", "policy denied")
            reasons.append(f"Blocked by {guard}: {reason}")
        elif outcome == "error":
            reasons.append(f"Action failed: {detail.get('error_type', 'unknown error')}")
        else:
            reasons.append(f"Outcome: {outcome}")

        # Extract goal hierarchy if present
        goal_ctx = {}
        if detail.get("mission_id"):
            goal_ctx["mission_id"] = detail["mission_id"]
            reasons.append(f"Part of mission: {detail['mission_id']}")
        if detail.get("goal_id"):
            goal_ctx["goal_id"] = detail["goal_id"]
            reasons.append(f"Goal: {detail['goal_id']}")

        with self._lock:
            self._explanation_counter += 1
            exp_id = f"exp-{self._explanation_counter:06d}"

        return GovernanceExplanation(
            explanation_id=exp_id,
            action=action,
            actor_id=actor_id,
            target=target,
            decision="allowed" if outcome in ("success", "allowed") else "denied",
            reasons=reasons,
            guard_chain_path=[],
            policy_context={**goal_ctx, "action": action},
            cost_context={},
            timestamp=timestamp or self._clock(),
        )

    def get_explanation(self, explanation_id: str) -> GovernanceExplanation | None:
        return self._cache.get(explanation_id)

    def summary(self) -> dict[str, Any]:
        with self._lock:
            return {
                "total_explanations": self._explanation_counter,
                "cached": len(self._cache),
            }
