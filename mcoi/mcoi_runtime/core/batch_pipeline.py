"""Phase 205C — Batch LLM Pipeline.

Purpose: Multi-step governed LLM chains for complex operations.
    Supports sequential steps where each step's output feeds the next.
    Full governance (budget, audit) at every step boundary.
Governance scope: pipeline orchestration only.
Dependencies: llm_integration.
Invariants:
  - Each step is independently budgeted.
  - Pipeline fails fast — first failed step stops execution.
  - Step outputs are immutable.
  - Total cost is sum of all step costs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(frozen=True, slots=True)
class PipelineStep:
    """Definition of a single step in a pipeline."""

    step_id: str
    name: str
    prompt_template: str  # May contain {input} placeholder
    model_name: str = "claude-sonnet-4-20250514"
    max_tokens: int = 1024
    system: str = ""


@dataclass(frozen=True, slots=True)
class StepResult:
    """Result of a single pipeline step."""

    step_id: str
    name: str
    content: str
    input_tokens: int
    output_tokens: int
    cost: float
    succeeded: bool
    error: str = ""


@dataclass(frozen=True, slots=True)
class PipelineResult:
    """Complete result of a pipeline execution."""

    pipeline_id: str
    steps: tuple[StepResult, ...]
    final_output: str
    total_cost: float
    total_tokens: int
    succeeded: bool
    error: str = ""


class BatchPipeline:
    """Multi-step governed LLM chain.

    Each step's output becomes available as {input} in the next step's
    prompt template. Budget is checked at each step boundary.
    """

    def __init__(
        self,
        *,
        clock: Callable[[], str],
        llm_complete_fn: Callable[..., Any],
    ) -> None:
        self._clock = clock
        self._llm_fn = llm_complete_fn
        self._history: list[PipelineResult] = []
        self._counter = 0

    def execute(
        self,
        steps: list[PipelineStep],
        *,
        initial_input: str = "",
        budget_id: str = "default",
        tenant_id: str = "",
    ) -> PipelineResult:
        """Execute a multi-step pipeline.

        Each step gets the previous step's output as {input}.
        Stops on first failure.
        """
        self._counter += 1
        pipeline_id = f"pipe-{self._counter}"
        step_results: list[StepResult] = []
        current_input = initial_input
        total_cost = 0.0
        total_tokens = 0

        for step in steps:
            # Format prompt with current input
            prompt = step.prompt_template.replace("{input}", current_input)

            try:
                result = self._llm_fn(
                    prompt,
                    model_name=step.model_name,
                    max_tokens=step.max_tokens,
                    system=step.system,
                    budget_id=budget_id,
                    tenant_id=tenant_id,
                )

                succeeded = getattr(result, "succeeded", True)
                content = getattr(result, "content", str(result))
                input_tokens = getattr(result, "input_tokens", 0)
                output_tokens = getattr(result, "output_tokens", 0)
                cost = getattr(result, "cost", 0.0)
                error = getattr(result, "error", "")

                step_result = StepResult(
                    step_id=step.step_id,
                    name=step.name,
                    content=content,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cost=cost,
                    succeeded=succeeded,
                    error=error,
                )
                step_results.append(step_result)
                total_cost += cost
                total_tokens += input_tokens + output_tokens

                if not succeeded:
                    pipe_result = PipelineResult(
                        pipeline_id=pipeline_id,
                        steps=tuple(step_results),
                        final_output="",
                        total_cost=total_cost,
                        total_tokens=total_tokens,
                        succeeded=False,
                        error=f"step {step.step_id} failed: {error}",
                    )
                    self._history.append(pipe_result)
                    return pipe_result

                current_input = content

            except Exception as exc:
                step_results.append(StepResult(
                    step_id=step.step_id, name=step.name,
                    content="", input_tokens=0, output_tokens=0,
                    cost=0.0, succeeded=False, error=str(exc),
                ))
                pipe_result = PipelineResult(
                    pipeline_id=pipeline_id,
                    steps=tuple(step_results),
                    final_output="",
                    total_cost=total_cost,
                    total_tokens=total_tokens,
                    succeeded=False,
                    error=str(exc),
                )
                self._history.append(pipe_result)
                return pipe_result

        pipe_result = PipelineResult(
            pipeline_id=pipeline_id,
            steps=tuple(step_results),
            final_output=current_input,
            total_cost=total_cost,
            total_tokens=total_tokens,
            succeeded=True,
        )
        self._history.append(pipe_result)
        return pipe_result

    def history(self, limit: int = 50) -> list[PipelineResult]:
        return self._history[-limit:]

    @property
    def total_pipelines(self) -> int:
        return len(self._history)

    def summary(self) -> dict[str, Any]:
        succeeded = sum(1 for p in self._history if p.succeeded)
        total_cost = sum(p.total_cost for p in self._history)
        return {
            "total": self.total_pipelines,
            "succeeded": succeeded,
            "failed": self.total_pipelines - succeeded,
            "total_cost": round(total_cost, 6),
        }
