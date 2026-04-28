"""Policy Sandbox — dry-run simulation of governance decisions.

Purpose: simulate what would happen if a policy, budget, or provider
    configuration changed, without actually changing runtime state.
    Answers: "what gets blocked?", "what cost changes?", "what breaks?"
Governance scope: read-only simulation only — never mutates real state.
Dependencies: governance guards, audit trail (read-only).
Invariants:
  - Simulations never modify real runtime state.
  - All simulation results are deterministic given the same inputs.
  - Simulation history is bounded.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Callable


class SimulationScenario(StrEnum):
    """Types of policy simulation scenarios."""

    POLICY_CHANGE = "policy_change"
    BUDGET_CHANGE = "budget_change"
    PROVIDER_FAILURE = "provider_failure"
    RATE_LIMIT_CHANGE = "rate_limit_change"
    TENANT_DISABLE = "tenant_disable"
    CUSTOM = "custom"


@dataclass(frozen=True, slots=True)
class SimulationRequest:
    """A request to simulate a governance scenario."""

    simulation_id: str
    scenario: SimulationScenario
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)
    test_actions: tuple[dict[str, Any], ...] = ()


@dataclass
class ActionSimResult:
    """Result of simulating a single action."""

    action_type: str
    target: str
    current_decision: str  # "allow" or "deny"
    simulated_decision: str  # "allow" or "deny"
    changed: bool
    reason: str = ""


@dataclass
class SimulationResult:
    """Result of a complete simulation run."""

    simulation_id: str
    scenario: str
    description: str
    actions_tested: int
    actions_changed: int
    newly_blocked: int
    newly_allowed: int
    action_results: list[ActionSimResult]
    summary: dict[str, Any]
    simulated_at: str


class PolicySandbox:
    """Dry-run simulation engine for governance policy changes.

    Runs test actions through both the current guard chain and a
    modified scenario to show the diff. Never modifies real state.
    """

    _MAX_HISTORY = 1_000

    def __init__(
        self,
        *,
        clock: Callable[[], str],
        guard_chain: Any | None = None,
    ) -> None:
        self._clock = clock
        self._guard_chain = guard_chain
        self._history: list[SimulationResult] = []
        self._simulation_counter = 0
        self._lock = threading.Lock()

    def simulate(self, request: SimulationRequest) -> SimulationResult:
        """Run a policy simulation — compare current vs modified decisions."""
        now = self._clock()
        action_results: list[ActionSimResult] = []

        for test_action in request.test_actions:
            action_type = test_action.get("action_type", "unknown")
            target = test_action.get("target", "")
            tenant_id = test_action.get("tenant_id", "")
            budget_id = test_action.get("budget_id", "")

            # Current decision
            current = self._evaluate_current(action_type, target, tenant_id, budget_id)

            # Simulated decision based on scenario
            simulated = self._evaluate_simulated(
                request.scenario, request.parameters,
                action_type, target, tenant_id, budget_id,
            )

            changed = current != simulated
            action_results.append(ActionSimResult(
                action_type=action_type,
                target=target,
                current_decision=current,
                simulated_decision=simulated,
                changed=changed,
                reason=self._explain_change(request.scenario, request.parameters, current, simulated),
            ))

        newly_blocked = sum(1 for r in action_results if r.current_decision == "allow" and r.simulated_decision == "deny")
        newly_allowed = sum(1 for r in action_results if r.current_decision == "deny" and r.simulated_decision == "allow")
        actions_changed = sum(1 for r in action_results if r.changed)

        result = SimulationResult(
            simulation_id=request.simulation_id,
            scenario=request.scenario.value,
            description=request.description,
            actions_tested=len(action_results),
            actions_changed=actions_changed,
            newly_blocked=newly_blocked,
            newly_allowed=newly_allowed,
            action_results=action_results,
            summary={
                "impact": "high" if newly_blocked > 0 else "low" if actions_changed > 0 else "none",
                "recommendation": (
                    "review before applying — actions will be blocked"
                    if newly_blocked > 0
                    else "safe to apply" if actions_changed == 0
                    else "minor impact — review changed actions"
                ),
            },
            simulated_at=now,
        )

        with self._lock:
            self._history.append(result)
            if len(self._history) > self._MAX_HISTORY:
                self._history = self._history[-self._MAX_HISTORY:]

        return result

    def _evaluate_current(
        self, action_type: str, target: str, tenant_id: str, budget_id: str,
    ) -> str:
        """Evaluate an action against the current guard chain."""
        if self._guard_chain is None:
            return "allow"
        ctx = {
            "action_type": action_type,
            "target": target,
            "tenant_id": tenant_id,
            "budget_id": budget_id,
            "agent_id": "simulation",
        }
        result = self._guard_chain.evaluate(ctx)
        return "allow" if result.allowed else "deny"

    def _evaluate_simulated(
        self,
        scenario: SimulationScenario,
        parameters: dict[str, Any],
        action_type: str, target: str,
        tenant_id: str, budget_id: str,
    ) -> str:
        """Evaluate an action under a simulated scenario."""
        if scenario == SimulationScenario.PROVIDER_FAILURE:
            # Simulate all LLM actions being denied
            if "llm" in action_type or "complete" in action_type:
                return "deny"
            return self._evaluate_current(action_type, target, tenant_id, budget_id)

        if scenario == SimulationScenario.BUDGET_CHANGE:
            new_max = parameters.get("new_max_cost", 0)
            current_spent = parameters.get("current_spent", 0)
            if current_spent >= new_max:
                return "deny"
            return self._evaluate_current(action_type, target, tenant_id, budget_id)

        if scenario == SimulationScenario.TENANT_DISABLE:
            disabled_tenant = parameters.get("tenant_id", "")
            if tenant_id == disabled_tenant:
                return "deny"
            return self._evaluate_current(action_type, target, tenant_id, budget_id)

        if scenario == SimulationScenario.RATE_LIMIT_CHANGE:
            new_limit = parameters.get("new_max_tokens", 0)
            if new_limit <= 0:
                return "deny"
            return self._evaluate_current(action_type, target, tenant_id, budget_id)

        # POLICY_CHANGE and CUSTOM — use blocked_actions list
        blocked = set(parameters.get("blocked_actions", []))
        if action_type in blocked:
            return "deny"
        allowed = set(parameters.get("allowed_actions", []))
        if action_type in allowed:
            return "allow"
        return self._evaluate_current(action_type, target, tenant_id, budget_id)

    def _explain_change(
        self,
        scenario: SimulationScenario,
        parameters: dict[str, Any],
        current: str, simulated: str,
    ) -> str:
        if current == simulated:
            return "no change"
        if simulated == "deny":
            return f"would be blocked under {scenario.value} scenario"
        return f"would be allowed under {scenario.value} scenario"

    def recent_simulations(self, limit: int = 20) -> list[SimulationResult]:
        with self._lock:
            return list(reversed(self._history[-limit:]))

    def summary(self) -> dict[str, Any]:
        with self._lock:
            return {
                "total_simulations": len(self._history),
                "scenarios_tested": len(set(r.scenario for r in self._history)),
            }
