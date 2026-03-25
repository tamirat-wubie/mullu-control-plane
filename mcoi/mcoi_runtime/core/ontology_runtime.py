"""Purpose: ontology / semantic alignment runtime engine.
Governance scope: managing concepts, relations, schema mappings, entity
    alignments, semantic conflicts, decisions; detecting ontology violations;
    producing assessments, snapshots, closure reports, and state hashes.
Dependencies: ontology_runtime contracts, event_spine, core invariants,
    engine_protocol Clock.
Invariants:
  - Terminal concept states (RETIRED) are immutable.
  - Every mutation emits an event.
  - All returns are frozen dataclasses.
  - Violation detection is idempotent.
"""

from __future__ import annotations

from hashlib import sha256
from typing import Any

from ..contracts.event import EventRecord, EventSource, EventType
from ..contracts.ontology_runtime import (
    AlignmentStrength,
    ConceptKind,
    ConceptRecord,
    ConceptRelation,
    EntityAlignment,
    MappingDisposition,
    OntologyAssessment,
    OntologyClosureReport,
    OntologyDecision,
    OntologySnapshot,
    OntologyStatus,
    OntologyViolation,
    SchemaMapping,
    SemanticConflict,
    SemanticConflictStatus,
)
from .engine_protocol import Clock, WallClock
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str, clock: Clock) -> EventRecord:
    now = clock.now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-ont", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class OntologyRuntimeEngine:
    """Ontology / semantic alignment runtime engine."""

    def __init__(self, event_spine: EventSpineEngine, *, clock: Any = None) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._clock: Clock = clock if isinstance(clock, Clock) else WallClock()
        self._concepts: dict[str, ConceptRecord] = {}
        self._relations: dict[str, ConceptRelation] = {}
        self._mappings: dict[str, SchemaMapping] = {}
        self._alignments: dict[str, EntityAlignment] = {}
        self._conflicts: dict[str, SemanticConflict] = {}
        self._decisions: dict[str, OntologyDecision] = {}
        self._violations: dict[str, OntologyViolation] = {}
        self._snapshot_ids: set[str] = set()

    # ------------------------------------------------------------------
    # Clock
    # ------------------------------------------------------------------

    def _now(self) -> str:
        """Get current time from injected clock."""
        return self._clock.now_iso()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def concept_count(self) -> int:
        return len(self._concepts)

    @property
    def relation_count(self) -> int:
        return len(self._relations)

    @property
    def mapping_count(self) -> int:
        return len(self._mappings)

    @property
    def alignment_count(self) -> int:
        return len(self._alignments)

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
    # Concepts
    # ------------------------------------------------------------------

    def register_concept(
        self,
        concept_id: str,
        tenant_id: str,
        display_name: str,
        kind: ConceptKind,
        canonical_form: str,
    ) -> ConceptRecord:
        """Register a new ontology concept."""
        if concept_id in self._concepts:
            raise RuntimeCoreInvariantError(f"Duplicate concept_id: {concept_id}")
        now = self._now()
        c = ConceptRecord(
            concept_id=concept_id,
            tenant_id=tenant_id,
            display_name=display_name,
            kind=kind,
            canonical_form=canonical_form,
            status=OntologyStatus.ACTIVE,
            created_at=now,
        )
        self._concepts[concept_id] = c
        _emit(self._events, "concept_registered", {
            "concept_id": concept_id, "tenant_id": tenant_id,
        }, concept_id, self._clock)
        return c

    def get_concept(self, concept_id: str) -> ConceptRecord:
        """Get a concept by ID."""
        c = self._concepts.get(concept_id)
        if c is None:
            raise RuntimeCoreInvariantError(f"Unknown concept_id: {concept_id}")
        return c

    def concepts_for_tenant(self, tenant_id: str) -> tuple[ConceptRecord, ...]:
        """Return all concepts for a tenant."""
        return tuple(c for c in self._concepts.values() if c.tenant_id == tenant_id)

    def _update_concept_status(self, concept_id: str, new_status: OntologyStatus) -> ConceptRecord:
        """Update a concept's status with terminal-state guard."""
        old = self._concepts.get(concept_id)
        if old is None:
            raise RuntimeCoreInvariantError(f"Unknown concept_id: {concept_id}")
        if old.status == OntologyStatus.RETIRED:
            raise RuntimeCoreInvariantError(
                f"Cannot transition concept from terminal state {old.status.value}"
            )
        updated = ConceptRecord(
            concept_id=old.concept_id,
            tenant_id=old.tenant_id,
            display_name=old.display_name,
            kind=old.kind,
            canonical_form=old.canonical_form,
            status=new_status,
            created_at=old.created_at,
            metadata=old.metadata,
        )
        self._concepts[concept_id] = updated
        _emit(self._events, "concept_status_updated", {
            "concept_id": concept_id, "status": new_status.value,
        }, concept_id, self._clock)
        return updated

    def deprecate_concept(self, concept_id: str) -> ConceptRecord:
        """Deprecate a concept (any non-terminal -> DEPRECATED)."""
        return self._update_concept_status(concept_id, OntologyStatus.DEPRECATED)

    def retire_concept(self, concept_id: str) -> ConceptRecord:
        """Retire a concept (any non-terminal -> RETIRED, terminal)."""
        return self._update_concept_status(concept_id, OntologyStatus.RETIRED)

    # ------------------------------------------------------------------
    # Relations
    # ------------------------------------------------------------------

    def register_relation(
        self,
        relation_id: str,
        tenant_id: str,
        parent_ref: str,
        child_ref: str,
        kind: ConceptKind,
        strength: AlignmentStrength = AlignmentStrength.STRONG,
    ) -> ConceptRelation:
        """Register a relation between two concepts."""
        if relation_id in self._relations:
            raise RuntimeCoreInvariantError(f"Duplicate relation_id: {relation_id}")
        if parent_ref not in self._concepts:
            raise RuntimeCoreInvariantError(f"Unknown parent_ref concept: {parent_ref}")
        if child_ref not in self._concepts:
            raise RuntimeCoreInvariantError(f"Unknown child_ref concept: {child_ref}")
        now = self._now()
        r = ConceptRelation(
            relation_id=relation_id,
            tenant_id=tenant_id,
            parent_ref=parent_ref,
            child_ref=child_ref,
            kind=kind,
            strength=strength,
            created_at=now,
        )
        self._relations[relation_id] = r
        _emit(self._events, "relation_registered", {
            "relation_id": relation_id, "parent_ref": parent_ref, "child_ref": child_ref,
        }, relation_id, self._clock)
        return r

    # ------------------------------------------------------------------
    # Schema mappings
    # ------------------------------------------------------------------

    def register_schema_mapping(
        self,
        mapping_id: str,
        tenant_id: str,
        source_schema: str,
        target_schema: str,
        disposition: MappingDisposition = MappingDisposition.EXACT,
        field_count: int = 0,
    ) -> SchemaMapping:
        """Register a schema mapping."""
        if mapping_id in self._mappings:
            raise RuntimeCoreInvariantError(f"Duplicate mapping_id: {mapping_id}")
        now = self._now()
        m = SchemaMapping(
            mapping_id=mapping_id,
            tenant_id=tenant_id,
            source_schema=source_schema,
            target_schema=target_schema,
            disposition=disposition,
            field_count=field_count,
            created_at=now,
        )
        self._mappings[mapping_id] = m
        _emit(self._events, "schema_mapping_registered", {
            "mapping_id": mapping_id, "source_schema": source_schema,
        }, mapping_id, self._clock)
        return m

    # ------------------------------------------------------------------
    # Entity alignments
    # ------------------------------------------------------------------

    def align_entity(
        self,
        alignment_id: str,
        tenant_id: str,
        source_ref: str,
        target_ref: str,
        strength: AlignmentStrength = AlignmentStrength.STRONG,
        confidence: float = 1.0,
    ) -> EntityAlignment:
        """Align two entities."""
        if alignment_id in self._alignments:
            raise RuntimeCoreInvariantError(f"Duplicate alignment_id: {alignment_id}")
        now = self._now()
        a = EntityAlignment(
            alignment_id=alignment_id,
            tenant_id=tenant_id,
            source_ref=source_ref,
            target_ref=target_ref,
            strength=strength,
            confidence=confidence,
            created_at=now,
        )
        self._alignments[alignment_id] = a
        _emit(self._events, "entity_aligned", {
            "alignment_id": alignment_id, "source_ref": source_ref, "target_ref": target_ref,
        }, alignment_id, self._clock)
        return a

    # ------------------------------------------------------------------
    # Semantic conflicts
    # ------------------------------------------------------------------

    def detect_semantic_conflicts(self, tenant_id: str) -> tuple[SemanticConflict, ...]:
        """Detect semantic conflicts for a tenant (idempotent).

        Checks:
        - Two concepts with same canonical_form but different kind.
        - Two mappings with conflicting dispositions for the same source schema.
        """
        now = self._now()
        new_conflicts: list[SemanticConflict] = []

        # Check concepts with same canonical_form but different kind
        tenant_concepts = [c for c in self._concepts.values() if c.tenant_id == tenant_id]
        canonical_groups: dict[str, list[ConceptRecord]] = {}
        for c in tenant_concepts:
            canonical_groups.setdefault(c.canonical_form, []).append(c)

        for canonical, group in canonical_groups.items():
            if len(group) < 2:
                continue
            kinds = {c.kind for c in group}
            if len(kinds) > 1:
                # Create pairwise conflicts for different kinds
                seen_pairs: set[tuple[str, str]] = set()
                for i, a in enumerate(group):
                    for b in group[i + 1:]:
                        if a.kind != b.kind:
                            pair = tuple(sorted([a.concept_id, b.concept_id]))
                            if pair in seen_pairs:
                                continue
                            seen_pairs.add(pair)
                            cid = stable_identifier("conf-ont", {
                                "a": pair[0], "b": pair[1], "op": "kind_mismatch",
                            })
                            if cid not in self._conflicts:
                                conflict = SemanticConflict(
                                    conflict_id=cid,
                                    tenant_id=tenant_id,
                                    concept_a_ref=pair[0],
                                    concept_b_ref=pair[1],
                                    status=SemanticConflictStatus.DETECTED,
                                    reason=f"Concepts share canonical form '{canonical}' but differ in kind: {a.kind.value} vs {b.kind.value}",
                                    detected_at=now,
                                )
                                self._conflicts[cid] = conflict
                                new_conflicts.append(conflict)

        # Check mappings with conflicting dispositions for same source schema
        tenant_mappings = [m for m in self._mappings.values() if m.tenant_id == tenant_id]
        source_groups: dict[str, list[SchemaMapping]] = {}
        for m in tenant_mappings:
            source_groups.setdefault(m.source_schema, []).append(m)

        for source, group in source_groups.items():
            if len(group) < 2:
                continue
            dispositions = {m.disposition for m in group}
            if len(dispositions) > 1:
                seen_pairs_m: set[tuple[str, str]] = set()
                for i, a in enumerate(group):
                    for b in group[i + 1:]:
                        if a.disposition != b.disposition:
                            pair = tuple(sorted([a.mapping_id, b.mapping_id]))
                            if pair in seen_pairs_m:
                                continue
                            seen_pairs_m.add(pair)
                            cid = stable_identifier("conf-ont", {
                                "a": pair[0], "b": pair[1], "op": "disposition_conflict",
                            })
                            if cid not in self._conflicts:
                                conflict = SemanticConflict(
                                    conflict_id=cid,
                                    tenant_id=tenant_id,
                                    concept_a_ref=pair[0],
                                    concept_b_ref=pair[1],
                                    status=SemanticConflictStatus.DETECTED,
                                    reason=f"Mappings for source '{source}' have conflicting dispositions: {a.disposition.value} vs {b.disposition.value}",
                                    detected_at=now,
                                )
                                self._conflicts[cid] = conflict
                                new_conflicts.append(conflict)

        if new_conflicts:
            _emit(self._events, "semantic_conflicts_detected", {
                "tenant_id": tenant_id, "count": len(new_conflicts),
            }, "conflict-scan", self._clock)
        return tuple(new_conflicts)

    def _update_conflict_status(
        self, conflict_id: str, new_status: SemanticConflictStatus,
    ) -> SemanticConflict:
        """Update a conflict's status."""
        old = self._conflicts.get(conflict_id)
        if old is None:
            raise RuntimeCoreInvariantError(f"Unknown conflict_id: {conflict_id}")
        if old.status != SemanticConflictStatus.DETECTED:
            raise RuntimeCoreInvariantError(
                f"Cannot transition conflict from {old.status.value} to {new_status.value}"
            )
        updated = SemanticConflict(
            conflict_id=old.conflict_id,
            tenant_id=old.tenant_id,
            concept_a_ref=old.concept_a_ref,
            concept_b_ref=old.concept_b_ref,
            status=new_status,
            reason=old.reason,
            detected_at=old.detected_at,
            metadata=old.metadata,
        )
        self._conflicts[conflict_id] = updated
        _emit(self._events, "conflict_status_updated", {
            "conflict_id": conflict_id, "status": new_status.value,
        }, conflict_id, self._clock)
        return updated

    def resolve_conflict(self, conflict_id: str) -> SemanticConflict:
        """Resolve a conflict (DETECTED -> RESOLVED)."""
        return self._update_conflict_status(conflict_id, SemanticConflictStatus.RESOLVED)

    def defer_conflict(self, conflict_id: str) -> SemanticConflict:
        """Defer a conflict (DETECTED -> DEFERRED)."""
        return self._update_conflict_status(conflict_id, SemanticConflictStatus.DEFERRED)

    def accept_conflict(self, conflict_id: str) -> SemanticConflict:
        """Accept a conflict (DETECTED -> ACCEPTED)."""
        return self._update_conflict_status(conflict_id, SemanticConflictStatus.ACCEPTED)

    # ------------------------------------------------------------------
    # Canonicalization
    # ------------------------------------------------------------------

    def canonicalize_term(self, tenant_id: str, term: str) -> str:
        """Look up concept by display_name, return canonical_form; if not found, return term as-is."""
        for c in self._concepts.values():
            if c.tenant_id == tenant_id and c.display_name == term:
                return c.canonical_form
        return term

    # ------------------------------------------------------------------
    # Assessment
    # ------------------------------------------------------------------

    def ontology_assessment(self, assessment_id: str, tenant_id: str) -> OntologyAssessment:
        """Produce an ontology assessment for a tenant."""
        now = self._now()
        t_concepts = sum(1 for c in self._concepts.values() if c.tenant_id == tenant_id)
        t_mappings = sum(1 for m in self._mappings.values() if m.tenant_id == tenant_id)
        t_conflicts = sum(
            1 for cf in self._conflicts.values()
            if cf.tenant_id == tenant_id and cf.status == SemanticConflictStatus.DETECTED
        )
        t_aligned = sum(1 for a in self._alignments.values() if a.tenant_id == tenant_id)
        total = t_aligned + t_conflicts
        score = round(t_aligned / total, 4) if total > 0 else 1.0

        assessment = OntologyAssessment(
            assessment_id=assessment_id,
            tenant_id=tenant_id,
            total_concepts=t_concepts,
            total_mappings=t_mappings,
            total_conflicts=t_conflicts,
            alignment_score=score,
            assessed_at=now,
        )
        _emit(self._events, "ontology_assessment", {
            "assessment_id": assessment_id,
        }, assessment_id, self._clock)
        return assessment

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------

    def ontology_snapshot(self, snapshot_id: str, tenant_id: str) -> OntologySnapshot:
        """Capture a point-in-time ontology state snapshot (tenant-scoped counts)."""
        if snapshot_id in self._snapshot_ids:
            raise RuntimeCoreInvariantError(f"Duplicate snapshot_id: {snapshot_id}")
        now = self._now()

        t_concepts = sum(1 for c in self._concepts.values() if c.tenant_id == tenant_id)
        t_relations = sum(1 for r in self._relations.values() if r.tenant_id == tenant_id)
        t_mappings = sum(1 for m in self._mappings.values() if m.tenant_id == tenant_id)
        t_alignments = sum(1 for a in self._alignments.values() if a.tenant_id == tenant_id)
        t_conflicts = sum(1 for cf in self._conflicts.values() if cf.tenant_id == tenant_id)
        t_violations = sum(1 for v in self._violations.values() if v.tenant_id == tenant_id)

        snap = OntologySnapshot(
            snapshot_id=snapshot_id,
            tenant_id=tenant_id,
            total_concepts=t_concepts,
            total_relations=t_relations,
            total_mappings=t_mappings,
            total_alignments=t_alignments,
            total_conflicts=t_conflicts,
            total_violations=t_violations,
            captured_at=now,
        )
        self._snapshot_ids.add(snapshot_id)
        _emit(self._events, "ontology_snapshot_captured", {
            "snapshot_id": snapshot_id, "tenant_id": tenant_id,
        }, snapshot_id, self._clock)
        return snap

    # ------------------------------------------------------------------
    # Closure report
    # ------------------------------------------------------------------

    def ontology_closure_report(self, report_id: str, tenant_id: str) -> OntologyClosureReport:
        """Generate a closure report for ontology state."""
        now = self._now()
        report = OntologyClosureReport(
            report_id=report_id,
            tenant_id=tenant_id,
            total_concepts=sum(1 for c in self._concepts.values() if c.tenant_id == tenant_id),
            total_mappings=sum(1 for m in self._mappings.values() if m.tenant_id == tenant_id),
            total_alignments=sum(1 for a in self._alignments.values() if a.tenant_id == tenant_id),
            total_conflicts=sum(1 for cf in self._conflicts.values() if cf.tenant_id == tenant_id),
            total_violations=sum(1 for v in self._violations.values() if v.tenant_id == tenant_id),
            created_at=now,
        )
        _emit(self._events, "ontology_closure_report", {
            "report_id": report_id,
        }, report_id, self._clock)
        return report

    # ------------------------------------------------------------------
    # Violation detection
    # ------------------------------------------------------------------

    def detect_ontology_violations(self, tenant_id: str) -> tuple[OntologyViolation, ...]:
        """Detect ontology governance violations (idempotent).

        Checks:
        - unresolved_conflict: conflict in DETECTED status.
        - orphan_relation: relation referencing a concept that doesn't exist.
        - mapping_no_concepts: schema mapping but no aligned concepts for that tenant.
        """
        now = self._now()
        new_violations: list[OntologyViolation] = []

        # unresolved_conflict
        for cf in self._conflicts.values():
            if cf.tenant_id == tenant_id and cf.status == SemanticConflictStatus.DETECTED:
                vid = stable_identifier(
                    "viol-ont", {"conflict": cf.conflict_id, "op": "unresolved_conflict"},
                )
                if vid not in self._violations:
                    v = OntologyViolation(
                        violation_id=vid,
                        tenant_id=tenant_id,
                        operation="unresolved_conflict",
                        reason=f"Conflict {cf.conflict_id} is unresolved",
                        detected_at=now,
                    )
                    self._violations[vid] = v
                    new_violations.append(v)

        # orphan_relation
        for rel in self._relations.values():
            if rel.tenant_id != tenant_id:
                continue
            for ref_name, ref_val in [("parent_ref", rel.parent_ref), ("child_ref", rel.child_ref)]:
                if ref_val not in self._concepts:
                    vid = stable_identifier(
                        "viol-ont", {"relation": rel.relation_id, "ref": ref_name, "op": "orphan_relation"},
                    )
                    if vid not in self._violations:
                        v = OntologyViolation(
                            violation_id=vid,
                            tenant_id=tenant_id,
                            operation="orphan_relation",
                            reason=f"Relation {rel.relation_id} references missing concept via {ref_name}: {ref_val}",
                            detected_at=now,
                        )
                        self._violations[vid] = v
                        new_violations.append(v)

        # mapping_no_concepts
        tenant_mappings = [m for m in self._mappings.values() if m.tenant_id == tenant_id]
        tenant_alignments = [a for a in self._alignments.values() if a.tenant_id == tenant_id]
        if tenant_mappings and not tenant_alignments:
            vid = stable_identifier(
                "viol-ont", {"tenant": tenant_id, "op": "mapping_no_concepts"},
            )
            if vid not in self._violations:
                v = OntologyViolation(
                    violation_id=vid,
                    tenant_id=tenant_id,
                    operation="mapping_no_concepts",
                    reason=f"Tenant {tenant_id} has {len(tenant_mappings)} schema mapping(s) but no aligned concepts",
                    detected_at=now,
                )
                self._violations[vid] = v
                new_violations.append(v)

        if new_violations:
            _emit(self._events, "ontology_violations_detected", {
                "tenant_id": tenant_id, "count": len(new_violations),
            }, "violation-scan", self._clock)
        return tuple(new_violations)

    # ------------------------------------------------------------------
    # State introspection
    # ------------------------------------------------------------------

    def _collections(self) -> dict[str, Any]:
        """Return all internal collections."""
        return {
            "concepts": self._concepts,
            "relations": self._relations,
            "mappings": self._mappings,
            "alignments": self._alignments,
            "conflicts": self._conflicts,
            "decisions": self._decisions,
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
        result["snapshot_ids"] = sorted(self._snapshot_ids)
        result["_state_hash"] = self.state_hash()
        return result

    def state_hash(self) -> str:
        """Compute SHA256 hash over sorted keys of all collections."""
        parts = sorted([
            f"alignments={self.alignment_count}",
            f"concepts={self.concept_count}",
            f"conflicts={self.conflict_count}",
            f"decisions={self.decision_count}",
            f"mappings={self.mapping_count}",
            f"relations={self.relation_count}",
            f"violations={self.violation_count}",
        ])
        return sha256("|".join(parts).encode()).hexdigest()
