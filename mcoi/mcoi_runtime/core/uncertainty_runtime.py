"""Purpose: uncertainty / belief runtime engine.
Governance scope: registering beliefs, hypotheses, evidence weights, confidence
    intervals, belief updates, competing hypothesis sets, ranking hypotheses,
    detecting violations, producing immutable snapshots.
Dependencies: uncertainty_runtime contracts, event_spine, core invariants.
Invariants:
  - Beliefs start PROVISIONAL with default confidence 0.5.
  - Evidence weight auto-updates belief confidence.
  - Confidence intervals require lower <= upper.
  - Every mutation emits an event.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Callable

from ..contracts.uncertainty_runtime import (
    BeliefDecision,
    BeliefRecord,
    BeliefStatus,
    BeliefUpdate,
    CompetingHypothesisSet,
    ConfidenceDisposition,
    ConfidenceInterval,
    EvidenceWeight,
    EvidenceWeightRecord,
    HypothesisDisposition,
    UncertaintyAssessment,
    UncertaintyClosureReport,
    UncertaintyHypothesis,
    UncertaintySnapshot,
    UncertaintyType,
)
from ..contracts.event import EventRecord, EventSource, EventType
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-uncert", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


_EVIDENCE_WEIGHT_DELTA: dict[EvidenceWeight, float] = {
    EvidenceWeight.DECISIVE: 0.3,
    EvidenceWeight.STRONG: 0.2,
    EvidenceWeight.MODERATE: 0.1,
    EvidenceWeight.WEAK: 0.05,
    EvidenceWeight.NEGLIGIBLE: 0.0,
}


class UncertaintyRuntimeEngine:
    """Uncertainty / belief tracking engine."""

    def __init__(self, event_spine: EventSpineEngine, *, clock: Callable[[], str] | None = None) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._clock = clock or _now_iso
        self._beliefs: dict[str, BeliefRecord] = {}
        self._hypotheses: dict[str, UncertaintyHypothesis] = {}
        self._weights: dict[str, EvidenceWeightRecord] = {}
        self._intervals: dict[str, ConfidenceInterval] = {}
        self._updates: dict[str, BeliefUpdate] = {}
        self._sets: dict[str, CompetingHypothesisSet] = {}
        self._decisions: dict[str, BeliefDecision] = {}
        self._violations: dict[str, Any] = {}
        self._snapshot_ids: set[str] = set()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def belief_count(self) -> int:
        return len(self._beliefs)

    @property
    def hypothesis_count(self) -> int:
        return len(self._hypotheses)

    @property
    def weight_count(self) -> int:
        return len(self._weights)

    @property
    def interval_count(self) -> int:
        return len(self._intervals)

    @property
    def update_count(self) -> int:
        return len(self._updates)

    @property
    def set_count(self) -> int:
        return len(self._sets)

    @property
    def violation_count(self) -> int:
        return len(self._violations)

    # ------------------------------------------------------------------
    # Beliefs
    # ------------------------------------------------------------------

    def register_belief(
        self,
        belief_id: str,
        tenant_id: str,
        content: str,
        *,
        confidence: float = 0.5,
    ) -> BeliefRecord:
        """Register a new belief as PROVISIONAL."""
        if belief_id in self._beliefs:
            raise RuntimeCoreInvariantError("Duplicate belief_id")
        now = self._clock()
        belief = BeliefRecord(
            belief_id=belief_id, tenant_id=tenant_id,
            content=content, status=BeliefStatus.PROVISIONAL,
            confidence=confidence, created_at=now,
        )
        self._beliefs[belief_id] = belief
        _emit(self._events, "belief_registered", {
            "belief_id": belief_id, "confidence": confidence,
        }, belief_id)
        return belief

    def get_belief(self, belief_id: str) -> BeliefRecord:
        """Get a belief by ID."""
        b = self._beliefs.get(belief_id)
        if b is None:
            raise RuntimeCoreInvariantError("Unknown belief_id")
        return b

    # ------------------------------------------------------------------
    # Hypotheses
    # ------------------------------------------------------------------

    def register_hypothesis(
        self,
        hypothesis_id: str,
        tenant_id: str,
        belief_ref: str,
        *,
        prior_confidence: float = 0.5,
        posterior_confidence: float = 0.5,
        disposition: HypothesisDisposition = HypothesisDisposition.COMPETING,
    ) -> UncertaintyHypothesis:
        """Register a hypothesis linked to a belief."""
        if hypothesis_id in self._hypotheses:
            raise RuntimeCoreInvariantError("Duplicate hypothesis_id")
        if belief_ref not in self._beliefs:
            raise RuntimeCoreInvariantError("Unknown belief_ref")
        now = self._clock()
        hyp = UncertaintyHypothesis(
            hypothesis_id=hypothesis_id, tenant_id=tenant_id,
            belief_ref=belief_ref, disposition=disposition,
            prior_confidence=prior_confidence,
            posterior_confidence=posterior_confidence,
            created_at=now,
        )
        self._hypotheses[hypothesis_id] = hyp
        _emit(self._events, "hypothesis_registered", {
            "hypothesis_id": hypothesis_id, "belief_ref": belief_ref,
        }, hypothesis_id)
        return hyp

    # ------------------------------------------------------------------
    # Evidence weights
    # ------------------------------------------------------------------

    def register_evidence_weight(
        self,
        weight_id: str,
        tenant_id: str,
        belief_ref: str,
        evidence_ref: str,
        *,
        weight: EvidenceWeight = EvidenceWeight.MODERATE,
    ) -> EvidenceWeightRecord:
        """Register evidence weight for a belief, auto-updating belief confidence."""
        if weight_id in self._weights:
            raise RuntimeCoreInvariantError("Duplicate weight_id")
        if belief_ref not in self._beliefs:
            raise RuntimeCoreInvariantError("Unknown belief_ref")
        delta = _EVIDENCE_WEIGHT_DELTA[weight]
        impact = delta
        now = self._clock()
        wr = EvidenceWeightRecord(
            weight_id=weight_id, tenant_id=tenant_id,
            belief_ref=belief_ref, evidence_ref=evidence_ref,
            weight=weight, impact=impact,
            created_at=now,
        )
        self._weights[weight_id] = wr

        # Auto-update belief confidence
        old_belief = self._beliefs[belief_ref]
        new_confidence = min(1.0, max(0.0, old_belief.confidence + delta))
        updated_belief = BeliefRecord(
            belief_id=old_belief.belief_id, tenant_id=old_belief.tenant_id,
            content=old_belief.content, status=old_belief.status,
            confidence=new_confidence, created_at=old_belief.created_at,
            metadata=old_belief.metadata,
        )
        self._beliefs[belief_ref] = updated_belief

        _emit(self._events, "evidence_weight_registered", {
            "weight_id": weight_id, "belief_ref": belief_ref,
            "weight": weight.value, "delta": delta,
            "new_confidence": new_confidence,
        }, weight_id)
        return wr

    # ------------------------------------------------------------------
    # Confidence intervals
    # ------------------------------------------------------------------

    def register_confidence_interval(
        self,
        interval_id: str,
        tenant_id: str,
        belief_ref: str,
        *,
        lower: float = 0.0,
        upper: float = 1.0,
        confidence_level: float = 0.95,
    ) -> ConfidenceInterval:
        """Register a confidence interval. Validates lower <= upper."""
        if interval_id in self._intervals:
            raise RuntimeCoreInvariantError("Duplicate interval_id")
        if lower > upper:
            raise RuntimeCoreInvariantError("Confidence interval lower must be <= upper")
        now = self._clock()
        ci = ConfidenceInterval(
            interval_id=interval_id, tenant_id=tenant_id,
            belief_ref=belief_ref, lower=lower, upper=upper,
            confidence_level=confidence_level, created_at=now,
        )
        self._intervals[interval_id] = ci
        _emit(self._events, "confidence_interval_registered", {
            "interval_id": interval_id, "belief_ref": belief_ref,
        }, interval_id)
        return ci

    # ------------------------------------------------------------------
    # Belief updates
    # ------------------------------------------------------------------

    def update_belief(
        self,
        update_id: str,
        tenant_id: str,
        belief_ref: str,
        evidence_ref: str,
        *,
        new_confidence: float,
    ) -> BeliefUpdate:
        """Update a belief's confidence and create a BeliefUpdate record."""
        if update_id in self._updates:
            raise RuntimeCoreInvariantError("Duplicate update_id")
        if belief_ref not in self._beliefs:
            raise RuntimeCoreInvariantError("Unknown belief_ref")
        old_belief = self._beliefs[belief_ref]
        prior = old_belief.confidence
        now = self._clock()
        bu = BeliefUpdate(
            update_id=update_id, tenant_id=tenant_id,
            belief_ref=belief_ref, prior_confidence=prior,
            posterior_confidence=new_confidence,
            evidence_ref=evidence_ref, updated_at=now,
        )
        self._updates[update_id] = bu

        # Update belief
        updated_belief = BeliefRecord(
            belief_id=old_belief.belief_id, tenant_id=old_belief.tenant_id,
            content=old_belief.content, status=old_belief.status,
            confidence=new_confidence, created_at=old_belief.created_at,
            metadata=old_belief.metadata,
        )
        self._beliefs[belief_ref] = updated_belief

        _emit(self._events, "belief_updated", {
            "update_id": update_id, "belief_ref": belief_ref,
            "prior": prior, "posterior": new_confidence,
        }, update_id)
        return bu

    # ------------------------------------------------------------------
    # Competing hypothesis sets
    # ------------------------------------------------------------------

    def create_competing_set(
        self,
        set_id: str,
        tenant_id: str,
        hypothesis_ids: list[str],
    ) -> CompetingHypothesisSet:
        """Create a set of competing hypotheses."""
        if set_id in self._sets:
            raise RuntimeCoreInvariantError("Duplicate set_id")
        if not hypothesis_ids:
            raise RuntimeCoreInvariantError("hypothesis_ids must not be empty")
        for hid in hypothesis_ids:
            if hid not in self._hypotheses:
                raise RuntimeCoreInvariantError("Unknown hypothesis_id")
        # Find leading hypothesis (highest posterior_confidence)
        ranked = sorted(
            hypothesis_ids,
            key=lambda hid: self._hypotheses[hid].posterior_confidence,
            reverse=True,
        )
        leading = ranked[0]
        now = self._clock()
        cs = CompetingHypothesisSet(
            set_id=set_id, tenant_id=tenant_id,
            hypothesis_count=len(hypothesis_ids),
            leading_hypothesis_ref=leading,
            created_at=now,
        )
        self._sets[set_id] = cs
        _emit(self._events, "competing_set_created", {
            "set_id": set_id, "count": len(hypothesis_ids), "leading": leading,
        }, set_id)
        return cs

    # ------------------------------------------------------------------
    # Ranking
    # ------------------------------------------------------------------

    def rank_hypotheses(self, belief_ref: str) -> tuple[UncertaintyHypothesis, ...]:
        """Return hypotheses for a belief sorted by posterior_confidence desc."""
        return tuple(sorted(
            (h for h in self._hypotheses.values() if h.belief_ref == belief_ref),
            key=lambda h: h.posterior_confidence,
            reverse=True,
        ))

    # ------------------------------------------------------------------
    # Assessment
    # ------------------------------------------------------------------

    def uncertainty_assessment(
        self,
        assessment_id: str,
        tenant_id: str,
    ) -> UncertaintyAssessment:
        """Produce an uncertainty assessment."""
        beliefs = list(self._beliefs.values())
        avg_conf = 0.0
        if beliefs:
            avg_conf = sum(b.confidence for b in beliefs) / len(beliefs)
        now = self._clock()
        assessment = UncertaintyAssessment(
            assessment_id=assessment_id, tenant_id=tenant_id,
            total_beliefs=self.belief_count,
            total_hypotheses=self.hypothesis_count,
            total_updates=self.update_count,
            avg_confidence=round(avg_conf, 6),
            assessed_at=now,
        )
        _emit(self._events, "uncertainty_assessment", {
            "assessment_id": assessment_id,
            "avg_confidence": round(avg_conf, 6),
        }, assessment_id)
        return assessment

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------

    def uncertainty_snapshot(
        self,
        snapshot_id: str,
        tenant_id: str,
    ) -> UncertaintySnapshot:
        """Capture a point-in-time uncertainty snapshot."""
        if snapshot_id in self._snapshot_ids:
            raise RuntimeCoreInvariantError("Duplicate snapshot_id")
        now = self._clock()
        snap = UncertaintySnapshot(
            snapshot_id=snapshot_id, tenant_id=tenant_id,
            total_beliefs=self.belief_count,
            total_hypotheses=self.hypothesis_count,
            total_weights=self.weight_count,
            total_intervals=self.interval_count,
            total_updates=self.update_count,
            total_violations=self.violation_count,
            captured_at=now,
        )
        self._snapshot_ids.add(snapshot_id)
        _emit(self._events, "uncertainty_snapshot_captured", {
            "snapshot_id": snapshot_id,
        }, snapshot_id)
        return snap

    # ------------------------------------------------------------------
    # Closure report
    # ------------------------------------------------------------------

    def uncertainty_closure_report(
        self,
        report_id: str,
        tenant_id: str,
    ) -> UncertaintyClosureReport:
        """Produce a closure report for the uncertainty runtime."""
        now = self._clock()
        report = UncertaintyClosureReport(
            report_id=report_id, tenant_id=tenant_id,
            total_beliefs=self.belief_count,
            total_hypotheses=self.hypothesis_count,
            total_updates=self.update_count,
            total_violations=self.violation_count,
            created_at=now,
        )
        _emit(self._events, "uncertainty_closure_report", {
            "report_id": report_id,
        }, report_id)
        return report

    # ------------------------------------------------------------------
    # Violation detection
    # ------------------------------------------------------------------

    def detect_uncertainty_violations(self) -> tuple:
        """Detect uncertainty violations (idempotent)."""
        now = self._clock()
        new_violations: list = []

        # Inverted interval: lower > upper (shouldn't happen due to validation,
        # but check stored intervals defensively)
        for ci in self._intervals.values():
            if ci.lower > ci.upper:
                vid = stable_identifier("viol-uncert", {
                    "interval": ci.interval_id, "op": "inverted_interval",
                })
                if vid not in self._violations:
                    v = {
                        "violation_id": vid,
                        "interval_id": ci.interval_id,
                        "tenant_id": ci.tenant_id,
                        "operation": "inverted_interval",
                        "reason": "confidence interval bounds are inverted",
                        "detected_at": now,
                    }
                    self._violations[vid] = v
                    new_violations.append(v)

        # Zero evidence high confidence: belief confidence > 0.8 with no evidence weights
        for b in self._beliefs.values():
            if b.confidence > 0.8:
                has_weights = any(
                    w.belief_ref == b.belief_id for w in self._weights.values()
                )
                if not has_weights:
                    vid = stable_identifier("viol-uncert", {
                        "belief": b.belief_id, "op": "zero_evidence_high_confidence",
                    })
                    if vid not in self._violations:
                        v = {
                            "violation_id": vid,
                            "belief_id": b.belief_id,
                            "tenant_id": b.tenant_id,
                            "operation": "zero_evidence_high_confidence",
                            "reason": "belief has high confidence without evidence",
                            "detected_at": now,
                        }
                        self._violations[vid] = v
                        new_violations.append(v)

        # Stale belief: no updates at all
        for b in self._beliefs.values():
            has_updates = any(
                u.belief_ref == b.belief_id for u in self._updates.values()
            )
            if not has_updates:
                vid = stable_identifier("viol-uncert", {
                    "belief": b.belief_id, "op": "stale_belief",
                })
                if vid not in self._violations:
                    v = {
                        "violation_id": vid,
                        "belief_id": b.belief_id,
                        "tenant_id": b.tenant_id,
                        "operation": "stale_belief",
                        "reason": "belief has no updates",
                        "detected_at": now,
                    }
                    self._violations[vid] = v
                    new_violations.append(v)

        if new_violations:
            _emit(self._events, "uncertainty_violations_detected", {
                "count": len(new_violations),
            }, "violation-scan")
        return tuple(new_violations)

    # ------------------------------------------------------------------
    # Collections / snapshot / state_hash
    # ------------------------------------------------------------------

    def _collections(self) -> dict[str, dict]:
        return {
            "beliefs": self._beliefs,
            "hypotheses": self._hypotheses,
            "weights": self._weights,
            "intervals": self._intervals,
            "updates": self._updates,
            "sets": self._sets,
            "decisions": self._decisions,
            "violations": self._violations,
        }

    def snapshot(self) -> dict[str, int]:
        return {
            "beliefs": self.belief_count,
            "hypotheses": self.hypothesis_count,
            "weights": self.weight_count,
            "intervals": self.interval_count,
            "updates": self.update_count,
            "sets": self.set_count,
            "violations": self.violation_count,
        }

    def state_hash(self) -> str:
        """Compute a hash of the current engine state."""
        parts = [
            f"beliefs={self.belief_count}",
            f"hypotheses={self.hypothesis_count}",
            f"weights={self.weight_count}",
            f"intervals={self.interval_count}",
            f"updates={self.update_count}",
            f"sets={self.set_count}",
            f"violations={self.violation_count}",
        ]
        return sha256("|".join(parts).encode()).hexdigest()
