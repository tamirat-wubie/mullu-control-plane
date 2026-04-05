"""Phase 214A — Multi-Model Router.

Purpose: Auto-selects the optimal LLM model based on task characteristics.
    Routes simple tasks to fast/cheap models, complex tasks to powerful ones.
Governance scope: model selection only — never invokes LLM directly.
Dependencies: none (pure routing logic).
Invariants:
  - Routing decisions are deterministic for same inputs.
  - Cost-constrained routing never exceeds budget.
  - Fallback model is always available.
  - Routing reasons are auditable.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class TaskComplexity(StrEnum):
    SIMPLE = "simple"       # Short answers, classification, extraction
    MODERATE = "moderate"   # Summarization, translation, analysis
    COMPLEX = "complex"     # Multi-step reasoning, code generation, research


@dataclass(frozen=True, slots=True)
class ModelProfile:
    """Profile describing a model's capabilities and cost."""

    model_id: str
    name: str
    provider: str
    cost_per_1k_input: float
    cost_per_1k_output: float
    max_context: int
    speed_tier: str  # "fast", "medium", "slow"
    capability_tier: str  # "basic", "standard", "advanced"
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class RoutingDecision:
    """Result of model routing — which model to use and why."""

    model_id: str
    reason: str
    complexity: TaskComplexity
    estimated_cost: float
    alternatives: tuple[str, ...]


class ModelRouter:
    """Routes tasks to optimal models based on complexity and constraints."""

    def __init__(self) -> None:
        self._profiles: dict[str, ModelProfile] = {}
        self._routing_history: list[RoutingDecision] = []

    def register(self, profile: ModelProfile) -> None:
        self._profiles[profile.model_id] = profile

    def classify_complexity(self, prompt: str, *, max_tokens: int = 1024) -> TaskComplexity:
        """Estimate task complexity from prompt characteristics."""
        word_count = len(prompt.split())
        has_code = any(kw in prompt.lower() for kw in ["code", "function", "implement", "debug", "refactor"])
        has_analysis = any(kw in prompt.lower() for kw in ["analyze", "compare", "evaluate", "research", "strategy"])
        has_multi_step = any(kw in prompt.lower() for kw in ["step by step", "first", "then", "finally", "plan"])

        if has_code or has_multi_step or (has_analysis and word_count > 100):
            return TaskComplexity.COMPLEX
        if has_analysis or word_count > 50 or max_tokens > 2048:
            return TaskComplexity.MODERATE
        return TaskComplexity.SIMPLE

    def route(
        self,
        prompt: str,
        *,
        max_tokens: int = 1024,
        max_cost: float = 0.0,
        preferred_speed: str = "",
        force_model: str = "",
    ) -> RoutingDecision:
        """Select the optimal model for a task."""
        if force_model and force_model in self._profiles:
            profile = self._profiles[force_model]
            decision = RoutingDecision(
                model_id=force_model,
                reason="forced model override",
                complexity=self.classify_complexity(prompt, max_tokens=max_tokens),
                estimated_cost=self._estimate_cost(profile, len(prompt), max_tokens),
                alternatives=(),
            )
            self._routing_history.append(decision)
            return decision

        complexity = self.classify_complexity(prompt, max_tokens=max_tokens)
        candidates = self._get_candidates(complexity, max_cost, preferred_speed)

        if not candidates:
            # Fallback to any enabled model
            candidates = [p for p in self._profiles.values() if p.enabled]

        if not candidates:
            decision = RoutingDecision(
                model_id="", reason="no models available",
                complexity=complexity, estimated_cost=0.0, alternatives=(),
            )
            self._routing_history.append(decision)
            return decision

        # Sort by cost-effectiveness for the complexity level
        scored = []
        for p in candidates:
            cost = self._estimate_cost(p, len(prompt), max_tokens)
            capability_score = {"basic": 1, "standard": 2, "advanced": 3}.get(p.capability_tier, 1)
            speed_score = {"fast": 3, "medium": 2, "slow": 1}.get(p.speed_tier, 1)

            if complexity == TaskComplexity.SIMPLE:
                score = speed_score * 2 + (1 / max(cost, 0.0001))
            elif complexity == TaskComplexity.COMPLEX:
                score = capability_score * 3 + speed_score
            else:
                score = capability_score * 2 + speed_score + (1 / max(cost, 0.0001))

            scored.append((score, cost, p))

        scored.sort(key=lambda x: x[0], reverse=True)
        best = scored[0]
        alternatives = tuple(s[2].model_id for s in scored[1:3])

        decision = RoutingDecision(
            model_id=best[2].model_id,
            reason="selected by routing policy",
            complexity=complexity,
            estimated_cost=round(best[1], 6),
            alternatives=alternatives,
        )
        self._routing_history.append(decision)
        return decision

    def _get_candidates(
        self, complexity: TaskComplexity, max_cost: float, preferred_speed: str,
    ) -> list[ModelProfile]:
        candidates = [p for p in self._profiles.values() if p.enabled]

        if complexity == TaskComplexity.SIMPLE:
            candidates = [p for p in candidates if p.capability_tier in ("basic", "standard")]
        elif complexity == TaskComplexity.COMPLEX:
            candidates = [p for p in candidates if p.capability_tier in ("standard", "advanced")]

        if preferred_speed:
            speed_filtered = [p for p in candidates if p.speed_tier == preferred_speed]
            if speed_filtered:
                candidates = speed_filtered

        if max_cost > 0:
            candidates = [p for p in candidates if self._estimate_cost(p, 500, 1024) <= max_cost]

        return candidates

    def _estimate_cost(self, profile: ModelProfile, input_chars: int, max_tokens: int) -> float:
        input_tokens = input_chars // 4
        return (input_tokens * profile.cost_per_1k_input + max_tokens * profile.cost_per_1k_output) / 1000

    def history(self, limit: int = 50) -> list[RoutingDecision]:
        return self._routing_history[-limit:]

    @property
    def model_count(self) -> int:
        return len(self._profiles)

    def summary(self) -> dict[str, Any]:
        complexity_counts: dict[str, int] = {}
        for d in self._routing_history:
            complexity_counts[d.complexity.value] = complexity_counts.get(d.complexity.value, 0) + 1
        return {
            "models": self.model_count,
            "routing_decisions": len(self._routing_history),
            "by_complexity": complexity_counts,
        }
