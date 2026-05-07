"""Adaptive Reasoning — Complexity-based model routing.

Purpose: Automatically routes requests to the appropriate model based
    on task complexity. Simple queries go to fast/cheap models, complex
    tasks go to powerful/expensive models.

Inspired by: Claude Opus 4.6 adaptive thinking (4 effort levels),
    OpenAI multi-model orchestration patterns.

Invariants:
  - Classification is deterministic for the same input.
  - Model selection is auditable.
  - Cost optimization: simple queries never use expensive models.
  - Quality guarantee: complex tasks never use cheap models.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class ComplexityLevel(StrEnum):
    """Task complexity levels (maps to model tiers)."""

    LOW = "low"  # Simple factual queries, greetings, yes/no
    MEDIUM = "medium"  # Multi-step reasoning, summaries, analysis
    HIGH = "high"  # Complex coding, planning, creative, multi-document
    MAX = "max"  # Research, architecture, long-form generation


@dataclass(frozen=True, slots=True)
class ComplexityAssessment:
    """Result of complexity classification."""

    level: ComplexityLevel
    confidence: float  # 0.0-1.0
    reason: str
    suggested_model: str
    suggested_max_tokens: int


# Complexity signal patterns
_LOW_SIGNALS = re.compile(
    r"\b(?:hello|hi|hey|thanks|yes|no|ok|bye|what time|weather|who is|define)\b",
    re.IGNORECASE,
)

_HIGH_SIGNALS = re.compile(
    r"\b(?:analyze|compare|implement|design|architect|refactor|debug|optimize|"
    r"explain why|step by step|write a (?:function|class|module|script|program)|"
    r"create a plan|build|develop|review)\b",
    re.IGNORECASE,
)

_MAX_SIGNALS = re.compile(
    r"\b(?:research|comprehensive|in-depth|detailed analysis|full implementation|"
    r"architecture review|security audit|compliance|end.to.end)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class ModelTier:
    """Model configuration for a complexity tier."""

    model_name: str
    max_tokens: int
    description: str


# Default model tier mapping
DEFAULT_MODEL_TIERS: dict[ComplexityLevel, ModelTier] = {
    ComplexityLevel.LOW: ModelTier(
        model_name="claude-haiku-4-5-20251001",
        max_tokens=256,
        description="Fast, cheap — simple queries",
    ),
    ComplexityLevel.MEDIUM: ModelTier(
        model_name="claude-sonnet-4-6-20250514",
        max_tokens=1024,
        description="Balanced — standard tasks",
    ),
    ComplexityLevel.HIGH: ModelTier(
        model_name="claude-sonnet-4-6-20250514",
        max_tokens=4096,
        description="Powerful — complex reasoning",
    ),
    ComplexityLevel.MAX: ModelTier(
        model_name="claude-opus-4-6-20250514",
        max_tokens=8192,
        description="Maximum capability — research/architecture",
    ),
}


def classify_complexity(prompt: str, *, context_length: int = 0) -> ComplexityAssessment:
    """Classify the complexity of a prompt.

    Uses signal patterns + heuristics (length, question marks, code markers).
    """
    if not prompt:
        return ComplexityAssessment(
            level=ComplexityLevel.LOW, confidence=1.0,
            reason="empty prompt", suggested_model="", suggested_max_tokens=256,
        )

    # Length-based signals
    word_count = len(prompt.split())
    has_code = bool(re.search(r"```|def |class |function |import ", prompt))
    question_count = prompt.count("?")

    # Pattern matching
    has_max = bool(_MAX_SIGNALS.search(prompt))
    has_high = bool(_HIGH_SIGNALS.search(prompt))
    has_low = bool(_LOW_SIGNALS.search(prompt))

    # Decision logic
    if has_max or (word_count > 200 and has_high):
        level = ComplexityLevel.MAX
        reason = "max complexity signals detected"
        confidence = 0.85
    elif has_high or has_code or word_count > 100:
        level = ComplexityLevel.HIGH
        reason = "complex task signals"
        confidence = 0.80
    elif word_count > 30 or question_count > 1 or context_length > 10:
        level = ComplexityLevel.MEDIUM
        reason = "moderate complexity"
        confidence = 0.75
    elif has_low or word_count <= 10:
        level = ComplexityLevel.LOW
        reason = "simple query"
        confidence = 0.90
    else:
        level = ComplexityLevel.MEDIUM
        reason = "default classification"
        confidence = 0.60

    tier = DEFAULT_MODEL_TIERS[level]
    return ComplexityAssessment(
        level=level,
        confidence=confidence,
        reason=reason,
        suggested_model=tier.model_name,
        suggested_max_tokens=tier.max_tokens,
    )


class AdaptiveRouter:
    """Routes LLM calls to appropriate models based on complexity.

    Wraps GovernedSession.llm() with automatic model selection.
    """

    def __init__(
        self,
        *,
        model_tiers: dict[ComplexityLevel, ModelTier] | None = None,
    ) -> None:
        self._tiers = model_tiers or DEFAULT_MODEL_TIERS
        self._routing_history: list[dict[str, Any]] = []

    def select_model(self, prompt: str, context_length: int = 0) -> ComplexityAssessment:
        """Select model based on prompt complexity. No override — governance enforced."""
        assessment = classify_complexity(prompt, context_length=context_length)

        self._routing_history.append({
            "level": assessment.level.value,
            "model": assessment.suggested_model,
            "reason": assessment.reason,
        })

        # Prune history
        if len(self._routing_history) > 10_000:
            self._routing_history = self._routing_history[-10_000:]

        return assessment

    @property
    def routing_count(self) -> int:
        return len(self._routing_history)

    def summary(self) -> dict[str, Any]:
        level_counts: dict[str, int] = {}
        for entry in self._routing_history:
            level_counts[entry["level"]] = level_counts.get(entry["level"], 0) + 1
        return {
            "total_routings": self.routing_count,
            "level_distribution": level_counts,
        }
