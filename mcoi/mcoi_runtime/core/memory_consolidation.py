"""Purpose: strategic memory consolidation / long-horizon personalization engine.
Governance scope: managing memory candidates, consolidation decisions, retention
    rules, personalization profiles, memory conflicts, consolidation batches,
    assessments, violations, snapshots, and closure reports.
Dependencies: memory_consolidation contracts, event_spine, core invariants.
Invariants:
  - Duplicate candidate_id raises.
  - Consolidation batch promotes CRITICAL/HIGH, demotes LOW with occurrence_count==1.
  - Conflict resolution requires explicit completion.
  - Violation detection is idempotent.
  - Every mutation emits an event.
  - All returns are immutable.
  - Clock is injected for deterministic timestamps.
"""

from __future__ import annotations

from hashlib import sha256
from typing import Any

from mcoi_runtime.core.engine_protocol import Clock, WallClock

from ..contracts.memory_consolidation import (
    ConflictResolutionMode,
    ConsolidationAssessment,
    ConsolidationBatch,
    ConsolidationDecision,
    ConsolidationStatus,
    MemoryCandidate,
    MemoryConflict,
    MemoryConsolidationClosureReport,
    MemoryConsolidationSnapshot,
    MemoryConsolidationViolation,
    MemoryImportance,
    MemoryRiskLevel,
    PersonalizationProfile,
    PersonalizationScope,
    RetentionDisposition,
    RetentionRule,
)
from ..contracts.event import EventRecord, EventSource, EventType
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str, now: str) -> EventRecord:
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-mcrt", {"action": action, "seq": str(es.event_count), "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class MemoryConsolidationEngine:
    """Engine for governed strategic memory consolidation and personalization."""

    def __init__(self, event_spine: EventSpineEngine, *, clock: Any = None) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._clock: Clock = clock if isinstance(clock, Clock) else WallClock()
        self._candidates: dict[str, MemoryCandidate] = {}
        self._decisions: dict[str, ConsolidationDecision] = {}
        self._rules: dict[str, RetentionRule] = {}
        self._profiles: dict[str, PersonalizationProfile] = {}
        self._conflicts: dict[str, MemoryConflict] = {}
        self._batches: dict[str, ConsolidationBatch] = {}
        self._violations: dict[str, MemoryConsolidationViolation] = {}

    # ------------------------------------------------------------------
    # Clock
    # ------------------------------------------------------------------

    def _now(self) -> str:
        return self._clock.now_iso()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def candidate_count(self) -> int:
        return len(self._candidates)

    @property
    def decision_count(self) -> int:
        return len(self._decisions)

    @property
    def rule_count(self) -> int:
        return len(self._rules)

    @property
    def profile_count(self) -> int:
        return len(self._profiles)

    @property
    def conflict_count(self) -> int:
        return len(self._conflicts)

    @property
    def batch_count(self) -> int:
        return len(self._batches)

    @property
    def violation_count(self) -> int:
        return len(self._violations)

    # ------------------------------------------------------------------
    # Memory Candidates
    # ------------------------------------------------------------------

    def register_memory_candidate(
        self,
        candidate_id: str,
        tenant_id: str,
        source_ref: str,
        content_summary: str,
        importance: MemoryImportance = MemoryImportance.MEDIUM,
        occurrence_count: int = 1,
    ) -> MemoryCandidate:
        """Register a new memory candidate. Duplicate candidate_id raises."""
        if candidate_id in self._candidates:
            raise RuntimeCoreInvariantError(f"Duplicate candidate_id: {candidate_id}")
        now = self._now()
        candidate = MemoryCandidate(
            candidate_id=candidate_id,
            tenant_id=tenant_id,
            source_ref=source_ref,
            content_summary=content_summary,
            importance=importance,
            status=ConsolidationStatus.CANDIDATE,
            occurrence_count=occurrence_count,
            first_seen_at=now,
            last_seen_at=now,
        )
        self._candidates[candidate_id] = candidate
        _emit(self._events, "memory_candidate_registered", {
            "candidate_id": candidate_id, "importance": importance.value,
        }, candidate_id, self._now())
        return candidate

    def get_candidate(self, candidate_id: str) -> MemoryCandidate:
        c = self._candidates.get(candidate_id)
        if c is None:
            raise RuntimeCoreInvariantError(f"Unknown candidate_id: {candidate_id}")
        return c

    def candidates_for_tenant(self, tenant_id: str) -> tuple[MemoryCandidate, ...]:
        return tuple(c for c in self._candidates.values() if c.tenant_id == tenant_id)

    def _replace_candidate(self, candidate_id: str, **kwargs: Any) -> MemoryCandidate:
        """Replace a candidate with updated fields."""
        old = self.get_candidate(candidate_id)
        fields = {
            "candidate_id": old.candidate_id,
            "tenant_id": old.tenant_id,
            "source_ref": old.source_ref,
            "content_summary": old.content_summary,
            "importance": old.importance,
            "status": old.status,
            "occurrence_count": old.occurrence_count,
            "first_seen_at": old.first_seen_at,
            "last_seen_at": old.last_seen_at,
            "metadata": old.metadata,
        }
        fields.update(kwargs)
        updated = MemoryCandidate(**fields)
        self._candidates[candidate_id] = updated
        return updated

    # ------------------------------------------------------------------
    # Importance Scoring
    # ------------------------------------------------------------------

    def score_memory_importance(self, candidate_id: str) -> MemoryImportance:
        """Score memory importance based on occurrence_count.
        >=10 -> CRITICAL, >=5 -> HIGH, >=2 -> MEDIUM, 1 -> LOW.
        Updates candidate importance."""
        candidate = self.get_candidate(candidate_id)
        count = candidate.occurrence_count
        if count >= 10:
            importance = MemoryImportance.CRITICAL
        elif count >= 5:
            importance = MemoryImportance.HIGH
        elif count >= 2:
            importance = MemoryImportance.MEDIUM
        else:
            importance = MemoryImportance.LOW
        self._replace_candidate(candidate_id, importance=importance)
        _emit(self._events, "memory_importance_scored", {
            "candidate_id": candidate_id, "importance": importance.value,
        }, candidate_id, self._now())
        return importance

    # ------------------------------------------------------------------
    # Batch Consolidation
    # ------------------------------------------------------------------

    def consolidate_batch(
        self,
        batch_id: str,
        tenant_id: str,
    ) -> ConsolidationBatch:
        """Consolidate a batch of candidates for a tenant.
        CRITICAL/HIGH -> PROMOTED, LOW with occurrence_count==1 -> DEMOTED.
        Others stay CANDIDATE."""
        if batch_id in self._batches:
            raise RuntimeCoreInvariantError(f"Duplicate batch_id: {batch_id}")
        now = self._now()
        tenant_candidates = [
            c for c in self._candidates.values()
            if c.tenant_id == tenant_id and c.status == ConsolidationStatus.CANDIDATE
        ]
        promoted_count = 0
        demoted_count = 0
        merged_count = 0

        for candidate in tenant_candidates:
            if candidate.importance in (MemoryImportance.CRITICAL, MemoryImportance.HIGH):
                self._replace_candidate(candidate.candidate_id, status=ConsolidationStatus.PROMOTED)
                decision_id = stable_identifier("dec-mcrt", {
                    "batch": batch_id, "candidate": candidate.candidate_id, "disposition": "promoted",
                })
                decision = ConsolidationDecision(
                    decision_id=decision_id,
                    tenant_id=tenant_id,
                    candidate_ref=candidate.candidate_id,
                    disposition=ConsolidationStatus.PROMOTED,
                    reason=f"Importance {candidate.importance.value} qualifies for promotion",
                    decided_at=now,
                )
                self._decisions[decision_id] = decision
                promoted_count += 1
            elif candidate.importance == MemoryImportance.LOW and candidate.occurrence_count == 1:
                self._replace_candidate(candidate.candidate_id, status=ConsolidationStatus.DEMOTED)
                decision_id = stable_identifier("dec-mcrt", {
                    "batch": batch_id, "candidate": candidate.candidate_id, "disposition": "demoted",
                })
                decision = ConsolidationDecision(
                    decision_id=decision_id,
                    tenant_id=tenant_id,
                    candidate_ref=candidate.candidate_id,
                    disposition=ConsolidationStatus.DEMOTED,
                    reason="LOW importance with single occurrence demoted",
                    decided_at=now,
                )
                self._decisions[decision_id] = decision
                demoted_count += 1

        batch = ConsolidationBatch(
            batch_id=batch_id,
            tenant_id=tenant_id,
            candidate_count=len(tenant_candidates),
            promoted_count=promoted_count,
            demoted_count=demoted_count,
            merged_count=merged_count,
            processed_at=now,
        )
        self._batches[batch_id] = batch
        _emit(self._events, "consolidation_batch_processed", {
            "batch_id": batch_id, "promoted": promoted_count, "demoted": demoted_count,
        }, batch_id, self._now())
        return batch

    # ------------------------------------------------------------------
    # Conflict Resolution
    # ------------------------------------------------------------------

    def resolve_memory_conflict(
        self,
        conflict_id: str,
        tenant_id: str,
        candidate_a_ref: str,
        candidate_b_ref: str,
        resolution_mode: ConflictResolutionMode = ConflictResolutionMode.NEWER_WINS,
    ) -> MemoryConflict:
        """Register a memory conflict. Resolved=False initially."""
        if conflict_id in self._conflicts:
            raise RuntimeCoreInvariantError(f"Duplicate conflict_id: {conflict_id}")
        now = self._now()
        conflict = MemoryConflict(
            conflict_id=conflict_id,
            tenant_id=tenant_id,
            candidate_a_ref=candidate_a_ref,
            candidate_b_ref=candidate_b_ref,
            resolution_mode=resolution_mode,
            resolved=False,
            detected_at=now,
        )
        self._conflicts[conflict_id] = conflict
        _emit(self._events, "memory_conflict_registered", {
            "conflict_id": conflict_id, "mode": resolution_mode.value,
        }, conflict_id, self._now())
        return conflict

    def complete_conflict_resolution(self, conflict_id: str) -> MemoryConflict:
        """Complete a conflict resolution. Sets resolved=True."""
        old = self._conflicts.get(conflict_id)
        if old is None:
            raise RuntimeCoreInvariantError(f"Unknown conflict_id: {conflict_id}")
        if old.resolved:
            raise RuntimeCoreInvariantError(f"Conflict {conflict_id} is already resolved")
        now = self._now()
        updated = MemoryConflict(
            conflict_id=old.conflict_id,
            tenant_id=old.tenant_id,
            candidate_a_ref=old.candidate_a_ref,
            candidate_b_ref=old.candidate_b_ref,
            resolution_mode=old.resolution_mode,
            resolved=True,
            detected_at=old.detected_at,
            metadata=old.metadata,
        )
        self._conflicts[conflict_id] = updated
        _emit(self._events, "conflict_resolution_completed", {
            "conflict_id": conflict_id,
        }, conflict_id, self._now())
        return updated

    # ------------------------------------------------------------------
    # Retention Rules
    # ------------------------------------------------------------------

    def apply_retention_rule(
        self,
        rule_id: str,
        tenant_id: str,
        scope: PersonalizationScope,
        disposition: RetentionDisposition,
        max_age_days: int = 90,
    ) -> RetentionRule:
        """Apply a retention rule."""
        if rule_id in self._rules:
            raise RuntimeCoreInvariantError(f"Duplicate rule_id: {rule_id}")
        now = self._now()
        rule = RetentionRule(
            rule_id=rule_id,
            tenant_id=tenant_id,
            scope=scope,
            disposition=disposition,
            max_age_days=max_age_days,
            created_at=now,
        )
        self._rules[rule_id] = rule
        _emit(self._events, "retention_rule_applied", {
            "rule_id": rule_id, "scope": scope.value, "disposition": disposition.value,
        }, rule_id, self._now())
        return rule

    def get_rule(self, rule_id: str) -> RetentionRule:
        r = self._rules.get(rule_id)
        if r is None:
            raise RuntimeCoreInvariantError(f"Unknown rule_id: {rule_id}")
        return r

    def rules_for_tenant(self, tenant_id: str) -> tuple[RetentionRule, ...]:
        return tuple(r for r in self._rules.values() if r.tenant_id == tenant_id)

    # ------------------------------------------------------------------
    # Personalization Profiles
    # ------------------------------------------------------------------

    def build_personalization_profile(
        self,
        profile_id: str,
        tenant_id: str,
        identity_ref: str,
        scope: PersonalizationScope = PersonalizationScope.USER,
    ) -> PersonalizationProfile:
        """Build a personalization profile.
        preference_count = count of PROMOTED candidates for tenant.
        confidence = promoted / (promoted + demoted) or 1.0."""
        if profile_id in self._profiles:
            raise RuntimeCoreInvariantError(f"Duplicate profile_id: {profile_id}")
        now = self._now()
        tenant_candidates = [c for c in self._candidates.values() if c.tenant_id == tenant_id]
        promoted = sum(1 for c in tenant_candidates if c.status == ConsolidationStatus.PROMOTED)
        demoted = sum(1 for c in tenant_candidates if c.status == ConsolidationStatus.DEMOTED)
        total = promoted + demoted
        confidence = promoted / total if total > 0 else 1.0
        profile = PersonalizationProfile(
            profile_id=profile_id,
            tenant_id=tenant_id,
            identity_ref=identity_ref,
            scope=scope,
            preference_count=promoted,
            confidence=confidence,
            updated_at=now,
        )
        self._profiles[profile_id] = profile
        _emit(self._events, "personalization_profile_built", {
            "profile_id": profile_id, "preference_count": promoted, "confidence": confidence,
        }, profile_id, self._now())
        return profile

    def get_profile(self, profile_id: str) -> PersonalizationProfile:
        p = self._profiles.get(profile_id)
        if p is None:
            raise RuntimeCoreInvariantError(f"Unknown profile_id: {profile_id}")
        return p

    def profiles_for_tenant(self, tenant_id: str) -> tuple[PersonalizationProfile, ...]:
        return tuple(p for p in self._profiles.values() if p.tenant_id == tenant_id)

    # ------------------------------------------------------------------
    # Assessment
    # ------------------------------------------------------------------

    def consolidation_assessment(
        self,
        assessment_id: str,
        tenant_id: str,
    ) -> ConsolidationAssessment:
        """Produce a consolidation assessment for a tenant.
        consolidation_rate = promoted / (promoted + demoted) or 1.0."""
        now = self._now()
        tenant_candidates = [c for c in self._candidates.values() if c.tenant_id == tenant_id]
        promoted = sum(1 for c in tenant_candidates if c.status == ConsolidationStatus.PROMOTED)
        demoted = sum(1 for c in tenant_candidates if c.status == ConsolidationStatus.DEMOTED)
        total = promoted + demoted
        rate = promoted / total if total > 0 else 1.0

        asm = ConsolidationAssessment(
            assessment_id=assessment_id,
            tenant_id=tenant_id,
            total_candidates=len(tenant_candidates),
            total_promoted=promoted,
            total_demoted=demoted,
            consolidation_rate=rate,
            assessed_at=now,
        )
        _emit(self._events, "consolidation_assessed", {
            "assessment_id": assessment_id, "consolidation_rate": rate,
        }, assessment_id, self._now())
        return asm

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------

    def consolidation_snapshot(
        self,
        snapshot_id: str,
        tenant_id: str,
    ) -> MemoryConsolidationSnapshot:
        """Produce a point-in-time snapshot for a tenant."""
        now = self._now()
        snap = MemoryConsolidationSnapshot(
            snapshot_id=snapshot_id,
            tenant_id=tenant_id,
            total_candidates=sum(1 for c in self._candidates.values() if c.tenant_id == tenant_id),
            total_decisions=sum(1 for d in self._decisions.values() if d.tenant_id == tenant_id),
            total_profiles=sum(1 for p in self._profiles.values() if p.tenant_id == tenant_id),
            total_conflicts=sum(1 for cf in self._conflicts.values() if cf.tenant_id == tenant_id),
            total_batches=sum(1 for b in self._batches.values() if b.tenant_id == tenant_id),
            total_violations=sum(1 for v in self._violations.values() if v.tenant_id == tenant_id),
            captured_at=now,
        )
        return snap

    # ------------------------------------------------------------------
    # Violation Detection
    # ------------------------------------------------------------------

    def detect_consolidation_violations(self, tenant_id: str) -> tuple[MemoryConsolidationViolation, ...]:
        """Detect consolidation violations for a tenant. Idempotent."""
        now = self._now()
        new_violations: list[MemoryConsolidationViolation] = []

        # 1) unresolved_conflict: conflict with resolved=False
        for conflict in self._conflicts.values():
            if conflict.tenant_id == tenant_id and not conflict.resolved:
                vid = stable_identifier("viol-mcrt", {
                    "conflict": conflict.conflict_id, "op": "unresolved_conflict",
                })
                if vid not in self._violations:
                    v = MemoryConsolidationViolation(
                        violation_id=vid,
                        tenant_id=tenant_id,
                        operation="unresolved_conflict",
                        reason=f"Conflict {conflict.conflict_id} is not resolved",
                        detected_at=now,
                    )
                    self._violations[vid] = v
                    new_violations.append(v)

        # 2) candidate_no_decision: CANDIDATE with occurrence_count>=10 and no decision
        for candidate in self._candidates.values():
            if (
                candidate.tenant_id == tenant_id
                and candidate.status == ConsolidationStatus.CANDIDATE
                and candidate.occurrence_count >= 10
            ):
                has_decision = any(
                    d.candidate_ref == candidate.candidate_id
                    for d in self._decisions.values()
                )
                if not has_decision:
                    vid = stable_identifier("viol-mcrt", {
                        "candidate": candidate.candidate_id, "op": "candidate_no_decision",
                    })
                    if vid not in self._violations:
                        v = MemoryConsolidationViolation(
                            violation_id=vid,
                            tenant_id=tenant_id,
                            operation="candidate_no_decision",
                            reason=f"Candidate {candidate.candidate_id} has occurrence_count>={candidate.occurrence_count} with no consolidation decision",
                            detected_at=now,
                        )
                        self._violations[vid] = v
                        new_violations.append(v)

        # 3) profile_low_confidence: profile with confidence < 0.3
        for profile in self._profiles.values():
            if profile.tenant_id == tenant_id and profile.confidence < 0.3:
                vid = stable_identifier("viol-mcrt", {
                    "profile": profile.profile_id, "op": "profile_low_confidence",
                })
                if vid not in self._violations:
                    v = MemoryConsolidationViolation(
                        violation_id=vid,
                        tenant_id=tenant_id,
                        operation="profile_low_confidence",
                        reason=f"Profile {profile.profile_id} has confidence {profile.confidence} < 0.3",
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
            "candidates": self._candidates,
            "decisions": self._decisions,
            "rules": self._rules,
            "profiles": self._profiles,
            "conflicts": self._conflicts,
            "batches": self._batches,
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
            elif isinstance(collection, list):
                result[name] = [
                    v.to_dict() if hasattr(v, "to_dict") else v
                    for v in collection
                ]
        result["_state_hash"] = self.state_hash()
        return result

    def state_hash(self) -> str:
        """Compute a deterministic hash of engine state (sorted keys)."""
        parts = [
            f"batches={self.batch_count}",
            f"candidates={self.candidate_count}",
            f"conflicts={self.conflict_count}",
            f"decisions={self.decision_count}",
            f"profiles={self.profile_count}",
            f"rules={self.rule_count}",
            f"violations={self.violation_count}",
        ]
        return sha256("|".join(parts).encode()).hexdigest()
