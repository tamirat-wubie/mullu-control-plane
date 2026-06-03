"""Purpose: a READ-ONLY plan-time cognitive context reader. At plan-compile time it
    consults the bootstrapped organs (meta-reasoning confidence + degraded mode,
    world-state, episodic prior outcomes) for the capabilities a plan will use and
    produces a structured advisory context - so the planner / operator can SEE what
    the system has learned about those capabilities BEFORE acting. This closes the
    "planner never reads the organs at plan time" gap (organs were written/gated only
    around dispatch, never consulted while a plan is being compiled).
Governance scope: observability / advisory only. This module NEVER writes any engine,
    NEVER mutates the governed plan, and NEVER gates. It produces a context the caller
    may attach to the plan response; it holds zero authority over plan content. Wired
    default-OFF (see cognitive_planning_integration).
Dependencies:
  - mcoi_runtime.core.cognitive_loop: decide_verdict / DecisionVerdict (shared logic).
  - mcoi_runtime.core.invariants: text validation.
Invariants:
  - Read-only + deterministic: identical organ state -> identical context.
  - No contract field carries interpolated text (the verdict is a fixed enum value),
    so the context is auditable and passes the reflective-contract guard.
  - Capability ids are de-duplicated, order-preserving.
"""

from __future__ import annotations

from dataclasses import dataclass

from mcoi_runtime.core.cognitive_loop import DecisionVerdict, decide_verdict
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, ensure_non_empty_text

# Mirror CognitiveLoop's DECIDE-phase defaults (kept in sync intentionally).
_PLAN_REPLAN_THRESHOLD = 0.3
_PLAN_CAUTION_THRESHOLD = 0.5
_PLAN_NEUTRAL_CONFIDENCE = 0.5


@dataclass(frozen=True, slots=True)
class CapabilityPlanContext:
    """Learned context for one capability a plan will use (read-only)."""

    capability_id: str
    confidence: float
    degraded: bool
    prior_outcomes: int
    decision_verdict: DecisionVerdict

    def to_dict(self) -> dict[str, object]:
        return {
            "capability_id": self.capability_id,
            "confidence": self.confidence,
            "degraded": self.degraded,
            "prior_outcomes": self.prior_outcomes,
            "verdict": self.decision_verdict.value,
        }


@dataclass(frozen=True, slots=True)
class CognitivePlanningContext:
    """Aggregate plan-time cognitive context across a plan's capabilities.

    ``caution_capabilities`` lists the capabilities whose DECIDE verdict is NOT a
    plain PROCEED (low confidence / degraded) - the advisory the operator surface
    can act on. Nothing here changes the plan; it only surfaces what was learned.
    """

    capabilities: tuple[CapabilityPlanContext, ...]
    caution_capabilities: tuple[str, ...]
    planning_entity_count: int
    has_caution: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "capabilities": [c.to_dict() for c in self.capabilities],
            "caution_capabilities": list(self.caution_capabilities),
            "planning_entity_count": self.planning_entity_count,
            "has_caution": self.has_caution,
        }


class CognitivePlanningReader:
    """Reads plan-time cognitive context for a set of capabilities, read-only.

    Uses the SAME read accessors as the shadow observer / gate (meta-reasoning
    confidence + degraded mode, world-state entity count, episodic prior outcomes)
    and the SAME pure ``decide_verdict`` logic, but writes nothing and gates nothing.
    """

    def __init__(
        self,
        *,
        meta_reasoning: object,
        world_state: object,
        episodic_memory: object,
        replan_threshold: float = _PLAN_REPLAN_THRESHOLD,
        caution_threshold: float = _PLAN_CAUTION_THRESHOLD,
    ) -> None:
        if meta_reasoning is None:
            raise RuntimeCoreInvariantError("planning reader requires a meta_reasoning engine")
        if world_state is None:
            raise RuntimeCoreInvariantError("planning reader requires a world_state engine")
        if episodic_memory is None:
            raise RuntimeCoreInvariantError("planning reader requires an episodic_memory engine")
        if not (0.0 <= replan_threshold <= caution_threshold <= 1.0):
            raise RuntimeCoreInvariantError(
                "thresholds must satisfy 0.0 <= replan_threshold <= caution_threshold <= 1.0"
            )
        self._meta = meta_reasoning
        self._world_state = world_state
        self._episodic = episodic_memory
        self._replan_threshold = float(replan_threshold)
        self._caution_threshold = float(caution_threshold)

    def read(self, capability_ids: tuple[str, ...]) -> CognitivePlanningContext:
        seen: set[str] = set()
        contexts: list[CapabilityPlanContext] = []
        caution: list[str] = []
        for raw in capability_ids:
            capability_id = ensure_non_empty_text("capability_id", raw)
            if capability_id in seen:
                continue
            seen.add(capability_id)
            confidence = round(self._confidence(capability_id), 4)
            degraded = self._degraded(capability_id)
            verdict, _reason = decide_verdict(
                confidence=confidence,
                degraded=degraded,
                replan_threshold=self._replan_threshold,
                caution_threshold=self._caution_threshold,
            )
            contexts.append(
                CapabilityPlanContext(
                    capability_id=capability_id,
                    confidence=confidence,
                    degraded=degraded,
                    prior_outcomes=self._prior_outcomes(capability_id),
                    decision_verdict=verdict,
                )
            )
            if verdict is not DecisionVerdict.PROCEED:
                caution.append(capability_id)
        return CognitivePlanningContext(
            capabilities=tuple(contexts),
            caution_capabilities=tuple(caution),
            planning_entity_count=self._planning_entities(),
            has_caution=bool(caution),
        )

    # --- read-only engine accessors (mirror the shadow observer; never mutate) ---

    def _confidence(self, capability_id: str) -> float:
        get_confidence = getattr(self._meta, "get_confidence", None)
        if get_confidence is None:
            return _PLAN_NEUTRAL_CONFIDENCE
        existing = get_confidence(capability_id)
        if existing is None:
            return _PLAN_NEUTRAL_CONFIDENCE
        return float(existing.overall_confidence)

    def _degraded(self, capability_id: str) -> bool:
        is_degraded = getattr(self._meta, "is_degraded", None)
        if is_degraded is None:
            return False
        return bool(is_degraded(capability_id))

    def _prior_outcomes(self, capability_id: str) -> int:
        list_entries = getattr(self._episodic, "list_entries", None)
        if list_entries is None:
            return 0
        count = 0
        for entry in list_entries():
            content = getattr(entry, "content", {})
            if content.get("capability_id") == capability_id or content.get("route") == capability_id:
                count += 1
        return count

    def _planning_entities(self) -> int:
        list_entities = getattr(self._world_state, "list_entities", None)
        if list_entities is None:
            return 0
        return len(list_entities())


__all__ = [
    "CapabilityPlanContext",
    "CognitivePlanningContext",
    "CognitivePlanningReader",
]
