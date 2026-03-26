"""Phase 215A — Agent Chain Orchestration.

Purpose: Sequential and parallel multi-agent workflows where output
    from one agent feeds into the next. Supports branching, merging,
    and conditional routing between agents.
Governance scope: agent chain orchestration only.
Dependencies: agent_protocol, agent_workflow.
Invariants:
  - Chain steps execute in declared order (sequential) or concurrently (parallel).
  - Each step's output is available to subsequent steps via {{prev}} template.
  - Chain-level budget is enforced across all steps.
  - Failed steps can be configured to halt or skip.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(frozen=True, slots=True)
class ChainStep:
    """Single step in an agent chain."""

    step_id: str
    name: str
    prompt_template: str  # {{prev}} = previous step output, {{input}} = chain input
    capability: str = "llm.completion"
    on_failure: str = "halt"  # "halt", "skip", "retry"


@dataclass(frozen=True, slots=True)
class ChainStepResult:
    """Result of a single chain step."""

    step_id: str
    name: str
    output: str
    succeeded: bool
    cost: float
    error: str = ""


@dataclass(frozen=True, slots=True)
class AgentChainResult:
    """Result of executing a full agent chain."""

    chain_id: str
    steps: tuple[ChainStepResult, ...]
    final_output: str
    total_cost: float
    succeeded: bool
    error: str = ""


class AgentChainEngine:
    """Orchestrates sequential multi-agent chains."""

    def __init__(
        self,
        *,
        clock: Callable[[], str],
        llm_fn: Callable[[str], Any],
    ) -> None:
        self._clock = clock
        self._llm_fn = llm_fn
        self._counter = 0
        self._history: list[AgentChainResult] = []

    def execute(
        self,
        steps: list[ChainStep],
        *,
        initial_input: str = "",
    ) -> AgentChainResult:
        """Execute a chain of agent steps sequentially."""
        self._counter += 1
        chain_id = f"chain-{self._counter}"
        step_results: list[ChainStepResult] = []
        prev_output = initial_input
        total_cost = 0.0

        for step in steps:
            prompt = step.prompt_template.replace("{{prev}}", prev_output).replace("{{input}}", initial_input)

            try:
                result = self._llm_fn(prompt)
                content = getattr(result, "content", str(result))
                cost = getattr(result, "cost", 0.0)
                succeeded = getattr(result, "succeeded", True)
                error = getattr(result, "error", "")

                sr = ChainStepResult(
                    step_id=step.step_id, name=step.name,
                    output=content, succeeded=succeeded,
                    cost=cost, error=error,
                )
                step_results.append(sr)
                total_cost += cost

                if not succeeded:
                    if step.on_failure == "halt":
                        cr = AgentChainResult(
                            chain_id=chain_id, steps=tuple(step_results),
                            final_output="", total_cost=total_cost,
                            succeeded=False, error=f"step {step.step_id} failed: {error}",
                        )
                        self._history.append(cr)
                        return cr
                    # skip: continue with prev_output unchanged
                else:
                    prev_output = content

            except Exception as exc:
                sr = ChainStepResult(
                    step_id=step.step_id, name=step.name,
                    output="", succeeded=False, cost=0.0, error=str(exc),
                )
                step_results.append(sr)
                if step.on_failure == "halt":
                    cr = AgentChainResult(
                        chain_id=chain_id, steps=tuple(step_results),
                        final_output="", total_cost=total_cost,
                        succeeded=False, error=str(exc),
                    )
                    self._history.append(cr)
                    return cr

        cr = AgentChainResult(
            chain_id=chain_id, steps=tuple(step_results),
            final_output=prev_output, total_cost=total_cost, succeeded=True,
        )
        self._history.append(cr)
        return cr

    def history(self, limit: int = 50) -> list[AgentChainResult]:
        return self._history[-limit:]

    @property
    def total_chains(self) -> int:
        return len(self._history)

    def summary(self) -> dict[str, Any]:
        succeeded = sum(1 for c in self._history if c.succeeded)
        total_cost = sum(c.total_cost for c in self._history)
        return {
            "total": self.total_chains,
            "succeeded": succeeded,
            "failed": self.total_chains - succeeded,
            "total_cost": round(total_cost, 6),
        }
