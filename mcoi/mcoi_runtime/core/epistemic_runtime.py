"""Purpose: epistemic governance / knowledge trust runtime engine.
Governance scope: managing knowledge claims, evidence sources, trust assessments,
    source reliability, claim conflicts, epistemic decisions, violations,
    assessments, snapshots, and closure reports.
Dependencies: epistemic_runtime contracts, event_spine, core invariants.
Invariants:
  - Duplicate IDs raise RuntimeCoreInvariantError.
  - Every mutation emits an event.
  - All returns are immutable.
  - Clock is injected for deterministic timestamps.
  - Violation detection is idempotent.
"""

from __future__ import annotations

from hashlib import sha256
from typing import Any

from mcoi_runtime.core.engine_protocol import Clock, WallClock

from ..contracts.epistemic_runtime import (
    AssertionMode,
    ClaimConflict,
    ConflictDisposition,
    EpistemicAssessment,
    EpistemicClosureReport,
    EpistemicDecision,
    EpistemicRiskLevel,
    EpistemicSnapshot,
    EpistemicViolation,
    EvidenceOrigin,
    EvidenceSource,
    KnowledgeClaim,
    KnowledgeStatus,
    SourceReliabilityRecord,
    TrustAssessment,
    TrustLevel,
)
from ..contracts.event import EventRecord, EventSource, EventType
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str, now: str) -> EventRecord:
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-eprt", {"action": action, "seq": str(es.event_count), "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


def _derive_trust_level(status: KnowledgeStatus) -> TrustLevel:
    """Derive trust level from knowledge status."""
    if status in (KnowledgeStatus.OBSERVED, KnowledgeStatus.PROVEN):
        return TrustLevel.VERIFIED
    if status == KnowledgeStatus.INFERRED:
        return TrustLevel.HIGH
    if status == KnowledgeStatus.REPORTED:
        return TrustLevel.MODERATE
    if status == KnowledgeStatus.SIMULATED:
        return TrustLevel.LOW
    if status == KnowledgeStatus.RETRACTED:
        return TrustLevel.UNTRUSTED
    return TrustLevel.UNKNOWN


def _score_to_trust_level(score: float) -> TrustLevel:
    """Convert a combined confidence score to a trust level."""
    if score >= 0.8:
        return TrustLevel.VERIFIED
    if score >= 0.6:
        return TrustLevel.HIGH
    if score >= 0.4:
        return TrustLevel.MODERATE
    if score >= 0.2:
        return TrustLevel.LOW
    return TrustLevel.UNTRUSTED


class EpistemicRuntimeEngine:
    """Engine for governed epistemic / knowledge trust runtime."""

    def __init__(self, event_spine: EventSpineEngine, *, clock: Any = None) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._clock: Clock = clock if isinstance(clock, Clock) else WallClock()
        self._claims: dict[str, KnowledgeClaim] = {}
        self._sources: dict[str, EvidenceSource] = {}
        self._assessments: dict[str, TrustAssessment] = {}
        self._reliability_updates: dict[str, SourceReliabilityRecord] = {}
        self._conflicts: dict[str, ClaimConflict] = {}
        self._decisions: dict[str, EpistemicDecision] = {}
        self._violations: dict[str, EpistemicViolation] = {}

    # ------------------------------------------------------------------
    # Clock
    # ------------------------------------------------------------------

    def _now(self) -> str:
        return self._clock.now_iso()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def claim_count(self) -> int:
        return len(self._claims)

    @property
    def source_count(self) -> int:
        return len(self._sources)

    @property
    def assessment_count(self) -> int:
        return len(self._assessments)

    @property
    def reliability_update_count(self) -> int:
        return len(self._reliability_updates)

    @property
    def conflict_count(self) -> int:
        return len(self._conflicts)

    @property
    def decision_count(self) -> int:
        return len(self._decisions)

    @property
    def violation_count(self) -> int:
        return len(self._violations)

    # ------------------------------------------------------------------
    # Claims
    # ------------------------------------------------------------------

    def register_claim(
        self,
        claim_id: str,
        tenant_id: str,
        content: str,
        status: KnowledgeStatus = KnowledgeStatus.REPORTED,
        assertion_mode: AssertionMode = AssertionMode.FACTUAL,
        source_ref: str = "unknown",
        confidence: float = 0.5,
    ) -> KnowledgeClaim:
        """Register a new knowledge claim. Duplicate claim_id raises."""
        if claim_id in self._claims:
            raise RuntimeCoreInvariantError("Duplicate claim_id")
        now = self._now()
        trust_level = _derive_trust_level(status)
        claim = KnowledgeClaim(
            claim_id=claim_id,
            tenant_id=tenant_id,
            content=content,
            status=status,
            assertion_mode=assertion_mode,
            trust_level=trust_level,
            source_ref=source_ref,
            confidence=confidence,
            created_at=now,
        )
        self._claims[claim_id] = claim
        _emit(self._events, "claim_registered", {
            "claim_id": claim_id, "status": status.value, "trust_level": trust_level.value,
        }, claim_id, self._now())
        return claim

    def get_claim(self, claim_id: str) -> KnowledgeClaim:
        """Get a claim by ID. Raises if not found."""
        claim = self._claims.get(claim_id)
        if claim is None:
            raise RuntimeCoreInvariantError("Unknown claim_id")
        return claim

    def claims_for_tenant(self, tenant_id: str) -> tuple[KnowledgeClaim, ...]:
        """Return all claims for a tenant."""
        return tuple(c for c in self._claims.values() if c.tenant_id == tenant_id)

    def claims_by_status(self, tenant_id: str, status: KnowledgeStatus) -> tuple[KnowledgeClaim, ...]:
        """Return all claims for a tenant with a given status."""
        return tuple(
            c for c in self._claims.values()
            if c.tenant_id == tenant_id and c.status == status
        )

    def retract_claim(self, claim_id: str) -> KnowledgeClaim:
        """Retract a claim: set status=RETRACTED, trust=UNTRUSTED."""
        old = self._claims.get(claim_id)
        if old is None:
            raise RuntimeCoreInvariantError("Unknown claim_id")
        retracted = KnowledgeClaim(
            claim_id=old.claim_id,
            tenant_id=old.tenant_id,
            content=old.content,
            status=KnowledgeStatus.RETRACTED,
            assertion_mode=old.assertion_mode,
            trust_level=TrustLevel.UNTRUSTED,
            source_ref=old.source_ref,
            confidence=old.confidence,
            created_at=old.created_at,
            metadata=old.metadata,
        )
        self._claims[claim_id] = retracted
        _emit(self._events, "claim_retracted", {
            "claim_id": claim_id,
        }, claim_id, self._now())
        return retracted

    # ------------------------------------------------------------------
    # Evidence Sources
    # ------------------------------------------------------------------

    def register_evidence_source(
        self,
        source_id: str,
        tenant_id: str,
        display_name: str,
        origin: EvidenceOrigin,
        reliability_score: float = 0.7,
    ) -> EvidenceSource:
        """Register an evidence source. Duplicate source_id raises."""
        if source_id in self._sources:
            raise RuntimeCoreInvariantError("Duplicate source_id")
        now = self._now()
        source = EvidenceSource(
            source_id=source_id,
            tenant_id=tenant_id,
            display_name=display_name,
            origin=origin,
            reliability_score=reliability_score,
            claim_count=0,
            created_at=now,
        )
        self._sources[source_id] = source
        _emit(self._events, "source_registered", {
            "source_id": source_id, "origin": origin.value,
        }, source_id, self._now())
        return source

    def get_source(self, source_id: str) -> EvidenceSource:
        """Get a source by ID. Raises if not found."""
        source = self._sources.get(source_id)
        if source is None:
            raise RuntimeCoreInvariantError("Unknown source_id")
        return source

    def sources_for_tenant(self, tenant_id: str) -> tuple[EvidenceSource, ...]:
        """Return all sources for a tenant."""
        return tuple(s for s in self._sources.values() if s.tenant_id == tenant_id)

    # ------------------------------------------------------------------
    # Source Reliability Updates
    # ------------------------------------------------------------------

    def update_source_reliability(
        self,
        record_id: str,
        tenant_id: str,
        source_ref: str,
        new_score: float,
        reason: str,
    ) -> SourceReliabilityRecord:
        """Update a source's reliability score."""
        if record_id in self._reliability_updates:
            raise RuntimeCoreInvariantError("Duplicate record_id")
        source = self._sources.get(source_ref)
        if source is None:
            raise RuntimeCoreInvariantError("Unknown source_ref")
        now = self._now()
        previous_score = source.reliability_score
        record = SourceReliabilityRecord(
            record_id=record_id,
            tenant_id=tenant_id,
            source_ref=source_ref,
            previous_score=previous_score,
            updated_score=new_score,
            reason=reason,
            updated_at=now,
        )
        self._reliability_updates[record_id] = record

        # Update the source with new reliability score
        updated_source = EvidenceSource(
            source_id=source.source_id,
            tenant_id=source.tenant_id,
            display_name=source.display_name,
            origin=source.origin,
            reliability_score=new_score,
            claim_count=source.claim_count,
            created_at=source.created_at,
            metadata=source.metadata,
        )
        self._sources[source_ref] = updated_source

        _emit(self._events, "source_reliability_updated", {
            "record_id": record_id, "source_ref": source_ref,
            "previous_score": previous_score, "new_score": new_score,
        }, record_id, self._now())
        return record

    # ------------------------------------------------------------------
    # Trust Assessment
    # ------------------------------------------------------------------

    def assess_trust(
        self,
        assessment_id: str,
        tenant_id: str,
        claim_ref: str,
        source_ref: str,
    ) -> TrustAssessment:
        """Assess trust for a claim given an evidence source.

        Combines claim.confidence * source.reliability_score to derive trust_level.
        """
        if assessment_id in self._assessments:
            raise RuntimeCoreInvariantError("Duplicate assessment_id")
        claim = self._claims.get(claim_ref)
        if claim is None:
            raise RuntimeCoreInvariantError("Unknown claim_ref")
        source = self._sources.get(source_ref)
        if source is None:
            raise RuntimeCoreInvariantError("Unknown source_ref")

        now = self._now()
        combined = claim.confidence * source.reliability_score
        trust_level = _score_to_trust_level(combined)
        basis = f"confidence={claim.confidence:.2f} * reliability={source.reliability_score:.2f} = {combined:.4f}"

        assessment = TrustAssessment(
            assessment_id=assessment_id,
            tenant_id=tenant_id,
            claim_ref=claim_ref,
            source_ref=source_ref,
            trust_level=trust_level,
            confidence=combined,
            basis=basis,
            assessed_at=now,
        )
        self._assessments[assessment_id] = assessment

        _emit(self._events, "trust_assessed", {
            "assessment_id": assessment_id, "trust_level": trust_level.value,
            "combined_score": combined,
        }, assessment_id, self._now())
        return assessment

    # ------------------------------------------------------------------
    # Claim Conflict Detection
    # ------------------------------------------------------------------

    def detect_claim_conflicts(self, tenant_id: str) -> tuple[ClaimConflict, ...]:
        """Detect conflicts between claims for a tenant. Idempotent.

        Conflict: two claims with same content but different status, or
        same source_ref with contradictory assertion modes (FACTUAL vs SPECULATIVE).
        """
        now = self._now()
        new_conflicts: list[ClaimConflict] = []
        tenant_claims = [
            c for c in self._claims.values()
            if c.tenant_id == tenant_id and c.status != KnowledgeStatus.RETRACTED
        ]

        for i, ca in enumerate(tenant_claims):
            for cb in tenant_claims[i + 1:]:
                is_conflict = False

                # Same content, different status
                if ca.content == cb.content and ca.status != cb.status:
                    is_conflict = True
                # Same source_ref, contradictory assertion modes
                elif (ca.source_ref == cb.source_ref
                      and ca.source_ref != "unknown"
                      and ca.assertion_mode != cb.assertion_mode
                      and {ca.assertion_mode, cb.assertion_mode} & {AssertionMode.FACTUAL}
                      and {ca.assertion_mode, cb.assertion_mode} & {AssertionMode.SPECULATIVE}):
                    is_conflict = True

                if is_conflict:
                    cid = stable_identifier("conf-eprt", {
                        "a": ca.claim_id, "b": cb.claim_id,
                    })
                    if cid not in self._conflicts:
                        rec = ClaimConflict(
                            conflict_id=cid,
                            tenant_id=tenant_id,
                            claim_a_ref=ca.claim_id,
                            claim_b_ref=cb.claim_id,
                            disposition=ConflictDisposition.UNRESOLVED,
                            resolution_basis="",
                            detected_at=now,
                        )
                        self._conflicts[cid] = rec
                        new_conflicts.append(rec)

        return tuple(new_conflicts)

    def resolve_conflict(
        self,
        conflict_id: str,
        disposition: ConflictDisposition,
        resolution_basis: str,
    ) -> ClaimConflict:
        """Resolve an existing claim conflict."""
        old = self._conflicts.get(conflict_id)
        if old is None:
            raise RuntimeCoreInvariantError("Unknown conflict_id")
        now = self._now()
        resolved = ClaimConflict(
            conflict_id=old.conflict_id,
            tenant_id=old.tenant_id,
            claim_a_ref=old.claim_a_ref,
            claim_b_ref=old.claim_b_ref,
            disposition=disposition,
            resolution_basis=resolution_basis,
            detected_at=old.detected_at,
        )
        self._conflicts[conflict_id] = resolved
        _emit(self._events, "conflict_resolved", {
            "conflict_id": conflict_id, "disposition": disposition.value,
        }, conflict_id, self._now())
        return resolved

    # ------------------------------------------------------------------
    # Epistemic Assessment
    # ------------------------------------------------------------------

    def epistemic_assessment(
        self,
        assessment_id: str,
        tenant_id: str,
    ) -> EpistemicAssessment:
        """Produce an epistemic assessment for a tenant.

        avg_trust = mean of all claim confidences * source reliabilities.
        """
        now = self._now()
        tenant_claims = [c for c in self._claims.values() if c.tenant_id == tenant_id]
        tenant_sources = [s for s in self._sources.values() if s.tenant_id == tenant_id]
        tenant_conflicts = [
            c for c in self._conflicts.values()
            if c.tenant_id == tenant_id and c.disposition == ConflictDisposition.UNRESOLVED
        ]

        # Compute avg_trust: mean of claim.confidence * best-matching source reliability
        scores: list[float] = []
        source_map = {s.source_id: s for s in tenant_sources}
        for claim in tenant_claims:
            source = source_map.get(claim.source_ref)
            reliability = source.reliability_score if source else 0.5
            scores.append(claim.confidence * reliability)

        avg_trust = sum(scores) / len(scores) if scores else 0.0
        avg_trust = max(0.0, min(1.0, avg_trust))

        asm = EpistemicAssessment(
            assessment_id=assessment_id,
            tenant_id=tenant_id,
            total_claims=len(tenant_claims),
            total_sources=len(tenant_sources),
            total_conflicts=len(tenant_conflicts),
            avg_trust=avg_trust,
            assessed_at=now,
        )
        _emit(self._events, "epistemic_assessed", {
            "assessment_id": assessment_id, "avg_trust": avg_trust,
        }, assessment_id, self._now())
        return asm

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------

    def epistemic_snapshot(
        self,
        snapshot_id: str,
        tenant_id: str,
    ) -> EpistemicSnapshot:
        """Produce a point-in-time snapshot for a tenant."""
        now = self._now()
        return EpistemicSnapshot(
            snapshot_id=snapshot_id,
            tenant_id=tenant_id,
            total_claims=sum(1 for c in self._claims.values() if c.tenant_id == tenant_id),
            total_sources=sum(1 for s in self._sources.values() if s.tenant_id == tenant_id),
            total_assessments=sum(1 for a in self._assessments.values() if a.tenant_id == tenant_id),
            total_conflicts=sum(1 for c in self._conflicts.values() if c.tenant_id == tenant_id),
            total_reliability_updates=sum(1 for r in self._reliability_updates.values() if r.tenant_id == tenant_id),
            total_violations=sum(1 for v in self._violations.values() if v.tenant_id == tenant_id),
            captured_at=now,
        )

    # ------------------------------------------------------------------
    # Closure Report
    # ------------------------------------------------------------------

    def epistemic_closure_report(
        self,
        report_id: str,
        tenant_id: str,
    ) -> EpistemicClosureReport:
        """Produce a final closure report for a tenant."""
        now = self._now()
        return EpistemicClosureReport(
            report_id=report_id,
            tenant_id=tenant_id,
            total_claims=sum(1 for c in self._claims.values() if c.tenant_id == tenant_id),
            total_sources=sum(1 for s in self._sources.values() if s.tenant_id == tenant_id),
            total_conflicts=sum(1 for c in self._conflicts.values() if c.tenant_id == tenant_id),
            total_violations=sum(1 for v in self._violations.values() if v.tenant_id == tenant_id),
            created_at=now,
        )

    # ------------------------------------------------------------------
    # Violation Detection
    # ------------------------------------------------------------------

    def detect_epistemic_violations(self, tenant_id: str) -> tuple[EpistemicViolation, ...]:
        """Detect epistemic violations for a tenant. Idempotent.

        Checks:
        1. insufficient_basis: claim has HIGH trust but no trust assessment.
        2. unresolved_conflict: conflicts with UNRESOLVED disposition.
        3. untrusted_source_high_claim: source reliability < 0.3 but claim confidence > 0.8.
        """
        now = self._now()
        new_violations: list[EpistemicViolation] = []

        # 1. insufficient_basis: claim with VERIFIED/HIGH trust but no assessment
        assessed_claim_refs = {a.claim_ref for a in self._assessments.values() if a.tenant_id == tenant_id}
        for cid, claim in self._claims.items():
            if claim.tenant_id == tenant_id and claim.trust_level in (TrustLevel.VERIFIED, TrustLevel.HIGH):
                if claim.claim_id not in assessed_claim_refs:
                    vid = stable_identifier("viol-eprt", {
                        "claim": cid, "op": "insufficient_basis",
                    })
                    if vid not in self._violations:
                        v = EpistemicViolation(
                            violation_id=vid,
                            tenant_id=tenant_id,
                            operation="insufficient_basis",
                            reason="high-trust claim lacks trust assessment",
                            detected_at=now,
                        )
                        self._violations[vid] = v
                        new_violations.append(v)

        # 2. unresolved_conflict
        for cfid, conflict in self._conflicts.items():
            if conflict.tenant_id == tenant_id and conflict.disposition == ConflictDisposition.UNRESOLVED:
                vid = stable_identifier("viol-eprt", {
                    "conflict": cfid, "op": "unresolved_conflict",
                })
                if vid not in self._violations:
                    v = EpistemicViolation(
                        violation_id=vid,
                        tenant_id=tenant_id,
                        operation="unresolved_conflict",
                        reason="conflict is unresolved",
                        detected_at=now,
                    )
                    self._violations[vid] = v
                    new_violations.append(v)

        # 3. untrusted_source_high_claim: source reliability < 0.3, claim confidence > 0.8
        source_map = {s.source_id: s for s in self._sources.values() if s.tenant_id == tenant_id}
        for cid, claim in self._claims.items():
            if claim.tenant_id == tenant_id and claim.confidence > 0.8:
                source = source_map.get(claim.source_ref)
                if source is not None and source.reliability_score < 0.3:
                    vid = stable_identifier("viol-eprt", {
                        "claim": cid, "source": claim.source_ref, "op": "untrusted_source_high_claim",
                    })
                    if vid not in self._violations:
                        v = EpistemicViolation(
                            violation_id=vid,
                            tenant_id=tenant_id,
                            operation="untrusted_source_high_claim",
                            reason="high-confidence claim depends on untrusted source",
                            detected_at=now,
                        )
                        self._violations[vid] = v
                        new_violations.append(v)

        return tuple(new_violations)

    # ------------------------------------------------------------------
    # Collections / snapshot / state_hash
    # ------------------------------------------------------------------

    def _collections(self) -> dict[str, Any]:
        """Return all internal collections."""
        return {
            "assessments": self._assessments,
            "claims": self._claims,
            "conflicts": self._conflicts,
            "decisions": self._decisions,
            "reliability_updates": self._reliability_updates,
            "sources": self._sources,
            "violations": self._violations,
        }

    def snapshot(self) -> dict[str, Any]:
        """Capture complete engine state as a serializable dict."""
        result: dict[str, Any] = {}
        for name, collection in self._collections().items():
            if isinstance(collection, dict):
                result[name] = {
                    k: v.to_dict() if hasattr(v, "to_dict") else v
                    for k, v in collection.items()
                }
        result["_state_hash"] = self.state_hash()
        return result

    def state_hash(self) -> str:
        """Compute a deterministic hash of engine state (sorted keys, full 64-char)."""
        parts = [
            f"assessments={self.assessment_count}",
            f"claims={self.claim_count}",
            f"conflicts={self.conflict_count}",
            f"decisions={self.decision_count}",
            f"reliability_updates={self.reliability_update_count}",
            f"sources={self.source_count}",
            f"violations={self.violation_count}",
        ]
        return sha256("|".join(parts).encode()).hexdigest()
