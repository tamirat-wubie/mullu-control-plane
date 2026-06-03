"""Purpose: a RECORD-ONLY shadow observer that consults the bootstrapped cognitive
    organs (meta-reasoning, world-state, episodic memory) about a LIVE execution
    WITHOUT any authority over it. It answers "what would the DECIDE gate have said
    about this capability, and what did the engines observe?" purely for
    evidence-gathering on real traffic, and retains the result.
Governance scope: observability only. This module NEVER dispatches, NEVER writes
    back to any engine (no episodic.admit, no meta.update_confidence), and NEVER
    gates or alters the live response. It is the Stage-A shadow described in
    docs/design/COGNITIVE_LOOP_LIVE_WIRING.md (corrected to the live workflow seam).
Dependencies:
  - mcoi_runtime.core.cognitive_loop.decide_verdict (the SHARED pure DECIDE logic)
  - mcoi_runtime.core.cognitive_loop.DecisionVerdict / HardConstraint (taxonomy)
  - mcoi_runtime.core.invariants (deterministic ids + text validation)
Invariants:
  - Read-only: consults engines through read accessors only; mutates no engine.
  - Zero authority: observe() returns a report; callers store/discard it, but it
    never feeds the live decision or perturbs the live response.
  - Deterministic: identical (capability, engine state, clock) -> identical
    report_hash. No wall-clock, no randomness; the only IO is the injected clock
    and the injected read-only engines.
  - Bounded memory: the observer retains at most ``max_recent`` recent reports.
  - Auditable contract strings: the report carries no interpolated free-text
    contract field (verdict is an enum; everything else is a structured scalar),
    so it passes the reflective-contract guard.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Callable

from mcoi_runtime.core.cognitive_loop import (
    DecisionVerdict,
    HardConstraint,
    decide_verdict,
)
from mcoi_runtime.core.invariants import (
    RuntimeCoreInvariantError,
    ensure_non_empty_text,
    stable_identifier,
)

# Mirror CognitiveLoop's DECIDE-phase defaults (kept intentionally in sync). A
# previously-unseen capability has no confidence record and is treated as neutral
# so the shadow verdict matches the live single-step path's first-attempt parity.
_SHADOW_REPLAN_THRESHOLD = 0.3
_SHADOW_CAUTION_THRESHOLD = 0.5
_SHADOW_NEUTRAL_CONFIDENCE = 0.5

# Verdicts under which the live cognitive DECIDE gate would NOT have dispatched.
_BLOCKING_VERDICTS = frozenset(
    {DecisionVerdict.BLOCK_UNKNOWN_CONSTRAINT, DecisionVerdict.DEFER_TO_REVIEW}
)


@dataclass(frozen=True, slots=True)
class CognitiveShadowReport:
    """Immutable record of one shadow observation of a live execution.

    ``would_have_blocked`` is the safety-relevant signal: True when the cognitive
    DECIDE gate would have withheld dispatch. ``diverged`` is True when the live
    path proceeded-and-succeeded yet DECIDE would have withheld dispatch - the
    interesting evidence for promoting DECIDE from shadow to enforced later.
    """

    capability_id: str
    decision_verdict: DecisionVerdict
    confidence: float
    degraded: bool
    observed_planning_entities: int
    observed_prior_outcomes: int
    live_succeeded: bool
    would_have_blocked: bool
    diverged: bool
    observed_at: str
    report_hash: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "capability_id", ensure_non_empty_text("capability_id", self.capability_id)
        )
        if not isinstance(self.decision_verdict, DecisionVerdict):
            raise RuntimeCoreInvariantError("decision_verdict must be a DecisionVerdict")
        if not (0.0 <= float(self.confidence) <= 1.0):
            raise RuntimeCoreInvariantError("confidence must be in [0.0, 1.0]")
        for name in ("degraded", "live_succeeded", "would_have_blocked", "diverged"):
            if not isinstance(getattr(self, name), bool):
                raise RuntimeCoreInvariantError(f"{name} must be a bool")
        object.__setattr__(self, "observed_at", ensure_non_empty_text("observed_at", self.observed_at))
        object.__setattr__(self, "report_hash", ensure_non_empty_text("report_hash", self.report_hash))


@dataclass(frozen=True, slots=True)
class CognitiveShadowSummary:
    """Aggregate Stage-B decision signal over the observer's retained reports.

    ``diverged`` (live succeeded yet DECIDE would have withheld) and the derived
    ``divergence_rate`` are the headline: they quantify how much promoting DECIDE
    from shadow to enforced would change real outcomes. All fields are structured
    scalars / a sorted id tuple (no interpolated free text) so the summary passes
    the reflective-contract guard when surfaced through an endpoint.
    """

    observed: int
    would_have_blocked: int
    diverged: int
    degraded: int
    divergence_rate: float
    diverged_capabilities: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in ("observed", "would_have_blocked", "diverged", "degraded"):
            value = getattr(self, name)
            if not isinstance(value, int) or value < 0:
                raise RuntimeCoreInvariantError(f"{name} must be a non-negative int")
        if not (0.0 <= float(self.divergence_rate) <= 1.0):
            raise RuntimeCoreInvariantError("divergence_rate must be in [0.0, 1.0]")
        if not isinstance(self.diverged_capabilities, tuple):
            raise RuntimeCoreInvariantError("diverged_capabilities must be a tuple")


class ShadowCognitiveObserver:
    """Consults the cognitive organs about a live execution, record-only.

    Uses the SAME read accessors the live ``CognitiveLoop`` uses (meta-reasoning
    confidence + degraded mode, world-state entity count, episodic prior outcomes)
    and the SAME pure ``decide_verdict`` logic, but performs no ACT, no LEARN
    write-back, and holds no authority over the live response.
    """

    def __init__(
        self,
        *,
        meta_reasoning: object,
        world_state: object,
        episodic_memory: object,
        clock: Callable[[], str],
        replan_threshold: float = _SHADOW_REPLAN_THRESHOLD,
        caution_threshold: float = _SHADOW_CAUTION_THRESHOLD,
        max_recent: int = 256,
    ) -> None:
        if meta_reasoning is None:
            raise RuntimeCoreInvariantError("shadow observer requires a meta_reasoning engine")
        if world_state is None:
            raise RuntimeCoreInvariantError("shadow observer requires a world_state engine")
        if episodic_memory is None:
            raise RuntimeCoreInvariantError("shadow observer requires an episodic_memory engine")
        if clock is None:
            raise RuntimeCoreInvariantError("shadow observer requires an injected clock")
        if not (0.0 <= replan_threshold <= caution_threshold <= 1.0):
            raise RuntimeCoreInvariantError(
                "thresholds must satisfy 0.0 <= replan_threshold <= caution_threshold <= 1.0"
            )
        if int(max_recent) < 1:
            raise RuntimeCoreInvariantError("max_recent must be >= 1")
        self._meta = meta_reasoning
        self._world_state = world_state
        self._episodic = episodic_memory
        self._clock = clock
        self._replan_threshold = float(replan_threshold)
        self._caution_threshold = float(caution_threshold)
        self._recent: deque[CognitiveShadowReport] = deque(maxlen=int(max_recent))

    def observe(
        self,
        *,
        capability_id: str,
        live_succeeded: bool,
        hard_constraints: tuple[HardConstraint, ...] = (),
    ) -> CognitiveShadowReport:
        """Produce (and retain) one read-only shadow report. Mutates no engine."""
        capability_id = ensure_non_empty_text("capability_id", capability_id)
        confidence = round(self._capability_confidence(capability_id), 4)
        degraded = self._is_degraded(capability_id)
        verdict, _reason = decide_verdict(
            confidence=confidence,
            degraded=degraded,
            hard_constraints=hard_constraints,
            replan_threshold=self._replan_threshold,
            caution_threshold=self._caution_threshold,
        )
        planning_entities = self._observe_planning_entities()
        prior_outcomes = self._observe_prior_outcomes(capability_id)
        would_have_blocked = verdict in _BLOCKING_VERDICTS
        diverged = would_have_blocked and bool(live_succeeded)
        observed_at = self._clock()
        report_hash = stable_identifier(
            "cognitive-shadow-report",
            {
                "capability_id": capability_id,
                "verdict": verdict.value,
                "confidence": confidence,
                "degraded": bool(degraded),
                "planning_entities": planning_entities,
                "prior_outcomes": prior_outcomes,
                "live_succeeded": bool(live_succeeded),
            },
        )
        report = CognitiveShadowReport(
            capability_id=capability_id,
            decision_verdict=verdict,
            confidence=confidence,
            degraded=bool(degraded),
            observed_planning_entities=planning_entities,
            observed_prior_outcomes=prior_outcomes,
            live_succeeded=bool(live_succeeded),
            would_have_blocked=would_have_blocked,
            diverged=diverged,
            observed_at=observed_at,
            report_hash=report_hash,
        )
        self._recent.append(report)
        return report

    def recent_reports(self) -> tuple[CognitiveShadowReport, ...]:
        """Return the retained recent shadow reports (oldest first)."""
        return tuple(self._recent)

    def summary(self) -> CognitiveShadowSummary:
        """Aggregate the retained reports into the Stage-B decision signal.

        Pure read-only fold over ``recent_reports`` (no clock, no mutation). The
        headline is ``diverged`` - live executions that SUCCEEDED while the
        cognitive DECIDE gate would have WITHHELD dispatch. A high, well-
        understood divergence count is the evidence that promoting DECIDE from
        shadow (Stage A) to enforced (Stage B) would change real outcomes; a near-
        zero count is evidence it would be safe/low-impact. ``divergence_rate`` is
        diverged / observed (0.0 when nothing observed).
        """
        reports = self._recent
        observed = len(reports)
        would_have_blocked = sum(1 for r in reports if r.would_have_blocked)
        diverged = sum(1 for r in reports if r.diverged)
        degraded = sum(1 for r in reports if r.degraded)
        diverged_capabilities = tuple(
            sorted({r.capability_id for r in reports if r.diverged})
        )
        divergence_rate = round(diverged / observed, 4) if observed else 0.0
        return CognitiveShadowSummary(
            observed=observed,
            would_have_blocked=would_have_blocked,
            diverged=diverged,
            degraded=degraded,
            divergence_rate=divergence_rate,
            diverged_capabilities=diverged_capabilities,
        )

    # --- read-only engine accessors (mirror CognitiveLoop; never mutate) ---

    def _capability_confidence(self, capability_id: str) -> float:
        get_confidence = getattr(self._meta, "get_confidence", None)
        if get_confidence is None:
            return _SHADOW_NEUTRAL_CONFIDENCE
        existing = get_confidence(capability_id)
        if existing is None:
            return _SHADOW_NEUTRAL_CONFIDENCE
        return float(existing.overall_confidence)

    def _is_degraded(self, capability_id: str) -> bool:
        is_degraded = getattr(self._meta, "is_degraded", None)
        if is_degraded is None:
            return False
        return bool(is_degraded(capability_id))

    def _observe_planning_entities(self) -> int:
        list_entities = getattr(self._world_state, "list_entities", None)
        if list_entities is None:
            return 0
        return len(list_entities())

    def _observe_prior_outcomes(self, capability_id: str) -> int:
        list_entries = getattr(self._episodic, "list_entries", None)
        if list_entries is None:
            return 0
        count = 0
        for entry in list_entries():
            content = getattr(entry, "content", {})
            if content.get("capability_id") == capability_id or content.get("route") == capability_id:
                count += 1
        return count


__all__ = ["CognitiveShadowReport", "CognitiveShadowSummary", "ShadowCognitiveObserver"]
