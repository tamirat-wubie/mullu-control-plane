"""Purpose: learning feedback loop — lesson recording, confidence updates, promotion suggestions.
Governance scope: learning engine logic only.
Dependencies: knowledge ingestion contracts, knowledge registry, invariant helpers.
Invariants:
  - Confidence derives from outcome history, never fabricated.
  - Confidence is always clamped to [0.0, 1.0].
  - Promotion suggestions are advisory; they do not mutate lifecycle state.
  - Clock is injected for determinism.
"""

from __future__ import annotations

import math
from typing import Any, Callable

from mcoi_runtime.contracts.knowledge_ingestion import (
    ConfidenceLevel,
    KnowledgeLifecycle,
    LessonRecord,
)
from .invariants import RuntimeCoreInvariantError, ensure_non_empty_text, stable_identifier
from .knowledge import KnowledgeRegistry


class LearningEngine:
    """Feedback loop for knowledge improvement: lessons, confidence, promotion suggestions.

    This engine:
    - Records lessons from operational experience
    - Updates confidence based on success/failure outcomes
    - Suggests lifecycle promotions when confidence thresholds are met
    - Retrieves relevant lessons by keyword matching
    """

    def __init__(self, *, clock: Callable[[], str]) -> None:
        self._clock = clock
        self._lessons: list[LessonRecord] = []
        self._confidences: dict[str, float] = {}

    def record_lesson(
        self,
        source_id: str,
        context: str,
        action: str,
        outcome: str,
        lesson: str,
    ) -> LessonRecord:
        """Record a lesson learned from operational experience."""
        ensure_non_empty_text("source_id", source_id)
        ensure_non_empty_text("context", context)
        ensure_non_empty_text("action", action)
        ensure_non_empty_text("outcome", outcome)
        ensure_non_empty_text("lesson", lesson)

        now = self._clock()

        lesson_id = stable_identifier("lesson", {
            "source_id": source_id,
            "recorded_at": now,
            "action": action,
        })

        record = LessonRecord(
            lesson_id=lesson_id,
            source_id=source_id,
            context=context,
            action_taken=action,
            outcome=outcome,
            lesson=lesson,
            created_at=now,
        )

        self._lessons.append(record)
        return record

    def update_confidence(
        self,
        knowledge_id: str,
        outcome_success: bool,
        weight: float = 0.1,
    ) -> ConfidenceLevel:
        """Update confidence for a knowledge artifact based on outcome.

        Success increases confidence by weight * (1 - current).
        Failure decreases confidence by weight * current.
        Result is clamped to [0.0, 1.0].
        """
        ensure_non_empty_text("knowledge_id", knowledge_id)
        if not isinstance(weight, (int, float)) or not math.isfinite(weight) or not (0.0 <= weight <= 1.0):
            raise RuntimeCoreInvariantError("weight must be in [0.0, 1.0]")

        current = self._confidences.get(knowledge_id, 0.5)

        if outcome_success:
            new_value = current + weight * (1.0 - current)
        else:
            new_value = current - weight * current

        # Clamp to [0.0, 1.0]
        new_value = max(0.0, min(1.0, new_value))
        self._confidences[knowledge_id] = new_value

        now = self._clock()
        reason = (
            "outcome-based confidence increase"
            if outcome_success
            else "outcome-based confidence decrease"
        )

        return ConfidenceLevel(
            value=round(new_value, 6),
            reason=reason,
            assessed_at=now,
        )

    def get_confidence(self, knowledge_id: str) -> float:
        """Return the current confidence value for a knowledge artifact."""
        ensure_non_empty_text("knowledge_id", knowledge_id)
        return self._confidences.get(knowledge_id, 0.5)

    def set_confidence(self, knowledge_id: str, value: float) -> None:
        """Directly set confidence for a knowledge artifact (for initialization)."""
        ensure_non_empty_text("knowledge_id", knowledge_id)
        if not isinstance(value, (int, float)) or not math.isfinite(value) or not (0.0 <= value <= 1.0):
            raise RuntimeCoreInvariantError("confidence value must be in [0.0, 1.0]")
        self._confidences[knowledge_id] = value

    def suggest_promotion(
        self,
        knowledge_id: str,
        registry: KnowledgeRegistry,
    ) -> str | None:
        """Suggest a lifecycle promotion based on confidence thresholds.

        Returns the suggested target lifecycle name, or None if no promotion is warranted.
        - confidence >= 0.8 and lifecycle is candidate -> suggest "provisional"
        - confidence >= 0.9 and lifecycle is provisional -> suggest "verified"
        - confidence >= 0.95 and lifecycle is verified -> suggest "trusted"
        """
        ensure_non_empty_text("knowledge_id", knowledge_id)
        confidence = self._confidences.get(knowledge_id, 0.5)
        lifecycle = registry.get_lifecycle(knowledge_id)

        if lifecycle is None:
            return None

        if lifecycle == KnowledgeLifecycle.CANDIDATE and confidence >= 0.8:
            return "provisional"
        if lifecycle == KnowledgeLifecycle.PROVISIONAL and confidence >= 0.9:
            return "verified"
        if lifecycle == KnowledgeLifecycle.VERIFIED and confidence >= 0.95:
            return "trusted"

        return None

    def find_relevant_lessons(
        self,
        context_keywords: tuple[str, ...],
        lessons: list[LessonRecord] | None = None,
    ) -> tuple[LessonRecord, ...]:
        """Find lessons matching any of the given context keywords.

        Simple keyword matching against the lesson's context field.
        If lessons is None, searches the engine's own recorded lessons.
        """
        source = lessons if lessons is not None else self._lessons
        if not context_keywords:
            return ()

        matched: list[LessonRecord] = []
        keywords_lower = tuple(kw.lower() for kw in context_keywords)
        for record in source:
            context_lower = record.context.lower()
            if any(kw in context_lower for kw in keywords_lower):
                matched.append(record)
        return tuple(matched)
