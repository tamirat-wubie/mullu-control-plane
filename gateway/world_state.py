"""Gateway world-state graph.

Purpose: Store sourced operational facts as typed world entities, relations,
    events, claims, contradictions, and materialized state projections.
Governance scope: world-state admission, append-only observation history,
    planning/execution eligibility, and contradiction blocking.
Dependencies: standard-library dataclasses, hashing, datetime, and threading.
Invariants:
  - No world assertion is admitted without tenant, source, and evidence.
  - Relations must reference admitted entities in the same tenant scope.
  - Claims marked contradicted are blocked from planning and execution.
  - State replacement is expressed through supersession fields, not deletion.
  - Store history is append-only; materialized state is a projection.
"""

from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from typing import Any, Callable, Iterable


def _canonical_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True, slots=True)
class EvidenceRef:
    """Reference to source evidence for one world assertion."""

    evidence_id: str
    evidence_type: str
    source: str
    observed_at: str
    uri: str = ""
    content_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ValidityWindow:
    """Validity bounds for a world assertion."""

    valid_from: str
    valid_until: str = ""
    requires_refresh: bool = False


@dataclass(frozen=True, slots=True)
class WorldEntity:
    """Stable operational object identity."""

    entity_id: str
    tenant_id: str
    entity_type: str
    display_name: str
    evidence_refs: tuple[EvidenceRef, ...]
    source: str
    observed_at: str
    validity: ValidityWindow
    attributes: dict[str, Any] = field(default_factory=dict)
    trust_class: str = "observed"
    supersedes: tuple[str, ...] = ()
    contradicts: tuple[str, ...] = ()
    allowed_for_planning: bool = True
    allowed_for_execution: bool = False
    created_at: str = ""
    state_hash: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_refs", tuple(self.evidence_refs))
        object.__setattr__(self, "supersedes", tuple(self.supersedes))
        object.__setattr__(self, "contradicts", tuple(self.contradicts))


@dataclass(frozen=True, slots=True)
class WorldRelation:
    """Typed relation between two admitted world entities."""

    relation_id: str
    tenant_id: str
    relation_type: str
    source_entity_id: str
    target_entity_id: str
    evidence_refs: tuple[EvidenceRef, ...]
    source: str
    observed_at: str
    validity: ValidityWindow
    attributes: dict[str, Any] = field(default_factory=dict)
    trust_class: str = "observed"
    supersedes: tuple[str, ...] = ()
    contradicts: tuple[str, ...] = ()
    allowed_for_planning: bool = True
    allowed_for_execution: bool = False
    created_at: str = ""
    state_hash: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_refs", tuple(self.evidence_refs))
        object.__setattr__(self, "supersedes", tuple(self.supersedes))
        object.__setattr__(self, "contradicts", tuple(self.contradicts))


@dataclass(frozen=True, slots=True)
class WorldEvent:
    """Timestamped operational observation or transition."""

    event_id: str
    tenant_id: str
    event_type: str
    occurred_at: str
    evidence_refs: tuple[EvidenceRef, ...]
    source: str
    entity_refs: tuple[str, ...] = ()
    relation_refs: tuple[str, ...] = ()
    claim_refs: tuple[str, ...] = ()
    attributes: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    event_hash: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_refs", tuple(self.evidence_refs))
        object.__setattr__(self, "entity_refs", tuple(self.entity_refs))
        object.__setattr__(self, "relation_refs", tuple(self.relation_refs))
        object.__setattr__(self, "claim_refs", tuple(self.claim_refs))


@dataclass(frozen=True, slots=True)
class WorldClaim:
    """Sourced proposition about operational state."""

    claim_id: str
    tenant_id: str
    subject_ref: str
    predicate: str
    object_value: str
    evidence_refs: tuple[EvidenceRef, ...]
    source: str
    observed_at: str
    validity: ValidityWindow
    confidence: float = 1.0
    trust_class: str = "source_claim"
    freshness_window_days: int = 30
    domain_risk: str = "low"
    supersedes: tuple[str, ...] = ()
    contradicts: tuple[str, ...] = ()
    allowed_for_planning: bool = True
    allowed_for_execution: bool = False
    created_at: str = ""
    claim_hash: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_refs", tuple(self.evidence_refs))
        object.__setattr__(self, "supersedes", tuple(self.supersedes))
        object.__setattr__(self, "contradicts", tuple(self.contradicts))


@dataclass(frozen=True, slots=True)
class Contradiction:
    """Conflict between world claims, states, or relations."""

    contradiction_id: str
    tenant_id: str
    refs: tuple[str, ...]
    reason: str
    evidence_refs: tuple[EvidenceRef, ...]
    source: str
    observed_at: str
    severity: str = "medium"
    status: str = "open"
    resolution_ref: str = ""
    created_at: str = ""
    contradiction_hash: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "refs", tuple(self.refs))
        object.__setattr__(self, "evidence_refs", tuple(self.evidence_refs))


@dataclass(frozen=True, slots=True)
class WorldState:
    """Materialized tenant-scoped projection over admitted world assertions."""

    tenant_id: str
    state_id: str
    entity_count: int
    relation_count: int
    event_count: int
    claim_count: int
    contradiction_count: int
    open_contradiction_count: int
    projected_at: str
    state_hash: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class WorldStateAdmission:
    """Admission decision for one world-state assertion."""

    accepted: bool
    reason: str
    object_id: str = ""
    object_hash: str = ""


class WorldStateStore:
    """Persistence contract for world-state graph assertions."""

    def add_entity(self, entity: WorldEntity) -> WorldStateAdmission:
        """Admit one world entity."""
        raise NotImplementedError

    def add_relation(self, relation: WorldRelation) -> WorldStateAdmission:
        """Admit one world relation."""
        raise NotImplementedError

    def add_event(self, event: WorldEvent) -> WorldStateAdmission:
        """Admit one world event."""
        raise NotImplementedError

    def add_claim(self, claim: WorldClaim) -> WorldStateAdmission:
        """Admit one world claim."""
        raise NotImplementedError

    def add_contradiction(self, contradiction: Contradiction) -> WorldStateAdmission:
        """Admit one contradiction."""
        raise NotImplementedError

    def materialize(self, *, tenant_id: str) -> WorldState:
        """Return a tenant-scoped materialized state projection."""
        raise NotImplementedError


class InMemoryWorldStateStore(WorldStateStore):
    """In-memory append-only world-state store for local runtime and tests."""

    def __init__(self, *, clock: Callable[[], str] | None = None) -> None:
        self._clock = clock or _utc_now
        self._entities: dict[str, WorldEntity] = {}
        self._relations: dict[str, WorldRelation] = {}
        self._events: list[WorldEvent] = []
        self._claims: dict[str, WorldClaim] = {}
        self._contradictions: dict[str, Contradiction] = {}
        self._history: list[dict[str, str]] = []
        self._lock = threading.Lock()

    def add_entity(self, entity: WorldEntity) -> WorldStateAdmission:
        denial = _validate_assertion(
            object_id=entity.entity_id,
            tenant_id=entity.tenant_id,
            source=entity.source,
            observed_at=entity.observed_at,
            evidence_refs=entity.evidence_refs,
            validity=entity.validity,
        )
        if denial:
            return denial
        if not entity.entity_type:
            return WorldStateAdmission(False, "entity_type_required")
        if not entity.display_name:
            return WorldStateAdmission(False, "display_name_required")
        with self._lock:
            if entity.entity_id in self._entities:
                return WorldStateAdmission(False, "entity_already_exists", object_id=entity.entity_id)
            stored = _stamp_entity(entity, self._clock())
            self._entities[stored.entity_id] = stored
            self._append_history("entity", stored.entity_id, stored.state_hash, stored.tenant_id)
            return WorldStateAdmission(True, "admitted", stored.entity_id, stored.state_hash)

    def add_relation(self, relation: WorldRelation) -> WorldStateAdmission:
        denial = _validate_assertion(
            object_id=relation.relation_id,
            tenant_id=relation.tenant_id,
            source=relation.source,
            observed_at=relation.observed_at,
            evidence_refs=relation.evidence_refs,
            validity=relation.validity,
        )
        if denial:
            return denial
        if not relation.relation_type:
            return WorldStateAdmission(False, "relation_type_required")
        with self._lock:
            if relation.relation_id in self._relations:
                return WorldStateAdmission(False, "relation_already_exists", relation.relation_id)
            source_entity = self._entities.get(relation.source_entity_id)
            target_entity = self._entities.get(relation.target_entity_id)
            if source_entity is None or target_entity is None:
                return WorldStateAdmission(False, "relation_entities_required", relation.relation_id)
            if source_entity.tenant_id != relation.tenant_id or target_entity.tenant_id != relation.tenant_id:
                return WorldStateAdmission(False, "relation_tenant_mismatch", relation.relation_id)
            stored = _stamp_relation(relation, self._clock())
            self._relations[stored.relation_id] = stored
            self._append_history("relation", stored.relation_id, stored.state_hash, stored.tenant_id)
            return WorldStateAdmission(True, "admitted", stored.relation_id, stored.state_hash)

    def add_event(self, event: WorldEvent) -> WorldStateAdmission:
        if not event.event_type:
            return WorldStateAdmission(False, "event_type_required", event.event_id)
        denial = _validate_evidence(
            object_id=event.event_id,
            tenant_id=event.tenant_id,
            source=event.source,
            observed_at=event.occurred_at,
            evidence_refs=event.evidence_refs,
        )
        if denial:
            return denial
        with self._lock:
            unresolved = _missing_refs(
                event.entity_refs,
                self._entities,
                tenant_id=event.tenant_id,
            )
            unresolved += _missing_refs(
                event.relation_refs,
                self._relations,
                tenant_id=event.tenant_id,
            )
            unresolved += _missing_refs(
                event.claim_refs,
                self._claims,
                tenant_id=event.tenant_id,
            )
            if unresolved:
                return WorldStateAdmission(False, "event_refs_required", event.event_id)
            stored = _stamp_event(event, self._clock())
            self._events.append(stored)
            self._append_history("event", stored.event_id, stored.event_hash, stored.tenant_id)
            return WorldStateAdmission(True, "admitted", stored.event_id, stored.event_hash)

    def add_claim(self, claim: WorldClaim) -> WorldStateAdmission:
        denial = _validate_assertion(
            object_id=claim.claim_id,
            tenant_id=claim.tenant_id,
            source=claim.source,
            observed_at=claim.observed_at,
            evidence_refs=claim.evidence_refs,
            validity=claim.validity,
        )
        if denial:
            return denial
        if not claim.subject_ref:
            return WorldStateAdmission(False, "subject_ref_required", claim.claim_id)
        if not claim.predicate:
            return WorldStateAdmission(False, "predicate_required", claim.claim_id)
        if claim.confidence < 0.0 or claim.confidence > 1.0:
            return WorldStateAdmission(False, "confidence_out_of_range", claim.claim_id)
        with self._lock:
            if claim.claim_id in self._claims:
                return WorldStateAdmission(False, "claim_already_exists", claim.claim_id)
            stored = _stamp_claim(claim, self._clock())
            self._claims[stored.claim_id] = stored
            self._append_history("claim", stored.claim_id, stored.claim_hash, stored.tenant_id)
            return WorldStateAdmission(True, "admitted", stored.claim_id, stored.claim_hash)

    def add_contradiction(self, contradiction: Contradiction) -> WorldStateAdmission:
        denial = _validate_evidence(
            object_id=contradiction.contradiction_id,
            tenant_id=contradiction.tenant_id,
            source=contradiction.source,
            observed_at=contradiction.observed_at,
            evidence_refs=contradiction.evidence_refs,
        )
        if denial:
            return denial
        if len(contradiction.refs) < 2:
            return WorldStateAdmission(False, "contradiction_refs_required", contradiction.contradiction_id)
        if not contradiction.reason:
            return WorldStateAdmission(False, "contradiction_reason_required", contradiction.contradiction_id)
        with self._lock:
            if contradiction.contradiction_id in self._contradictions:
                return WorldStateAdmission(
                    False,
                    "contradiction_already_exists",
                    contradiction.contradiction_id,
                )
            stored = _stamp_contradiction(contradiction, self._clock())
            self._contradictions[stored.contradiction_id] = stored
            self._append_history(
                "contradiction",
                stored.contradiction_id,
                stored.contradiction_hash,
                stored.tenant_id,
            )
            return WorldStateAdmission(
                True,
                "admitted",
                stored.contradiction_id,
                stored.contradiction_hash,
            )

    def materialize(self, *, tenant_id: str) -> WorldState:
        with self._lock:
            entities = [entity for entity in self._entities.values() if entity.tenant_id == tenant_id]
            relations = [relation for relation in self._relations.values() if relation.tenant_id == tenant_id]
            events = [event for event in self._events if event.tenant_id == tenant_id]
            claims = [claim for claim in self._claims.values() if claim.tenant_id == tenant_id]
            contradictions = [
                contradiction
                for contradiction in self._contradictions.values()
                if contradiction.tenant_id == tenant_id
            ]
            open_contradictions = [
                contradiction
                for contradiction in contradictions
                if contradiction.status == "open"
            ]
            projected_at = self._clock()
            payload = {
                "tenant_id": tenant_id,
                "entities": sorted(entity.state_hash for entity in entities),
                "relations": sorted(relation.state_hash for relation in relations),
                "events": sorted(event.event_hash for event in events),
                "claims": sorted(claim.claim_hash for claim in claims),
                "contradictions": sorted(
                    contradiction.contradiction_hash for contradiction in contradictions
                ),
                "projected_at": projected_at,
            }
            state_hash = _canonical_hash(payload)
            return WorldState(
                tenant_id=tenant_id,
                state_id=f"world-state-{state_hash[:16]}",
                entity_count=len(entities),
                relation_count=len(relations),
                event_count=len(events),
                claim_count=len(claims),
                contradiction_count=len(contradictions),
                open_contradiction_count=len(open_contradictions),
                projected_at=projected_at,
                state_hash=state_hash,
            )

    def planning_claims(self, *, tenant_id: str) -> tuple[WorldClaim, ...]:
        """Return claim facts admitted for planning and not openly contradicted."""
        return self._eligible_claims(tenant_id=tenant_id, execution=False)

    def execution_claims(self, *, tenant_id: str) -> tuple[WorldClaim, ...]:
        """Return claim facts admitted for execution and not openly contradicted."""
        return self._eligible_claims(tenant_id=tenant_id, execution=True)

    def history(self, *, tenant_id: str = "") -> tuple[dict[str, str], ...]:
        """Return append-only admission history."""
        with self._lock:
            records = self._history
            if tenant_id:
                records = [record for record in records if record["tenant_id"] == tenant_id]
            return tuple(dict(record) for record in records)

    def get_claim(self, claim_id: str) -> WorldClaim | None:
        """Return one claim by id."""
        with self._lock:
            return self._claims.get(claim_id)

    def _eligible_claims(self, *, tenant_id: str, execution: bool) -> tuple[WorldClaim, ...]:
        with self._lock:
            blocked_refs = _open_contradiction_refs(self._contradictions.values(), tenant_id=tenant_id)
            claims: list[WorldClaim] = []
            for claim in self._claims.values():
                if claim.tenant_id != tenant_id:
                    continue
                if claim.claim_id in blocked_refs or set(claim.contradicts).intersection(blocked_refs):
                    continue
                if execution and not claim.allowed_for_execution:
                    continue
                if not execution and not claim.allowed_for_planning:
                    continue
                claims.append(claim)
            return tuple(sorted(claims, key=lambda claim: claim.claim_id))

    def _append_history(self, object_type: str, object_id: str, object_hash: str, tenant_id: str) -> None:
        self._history.append(
            {
                "object_type": object_type,
                "object_id": object_id,
                "object_hash": object_hash,
                "tenant_id": tenant_id,
                "recorded_at": self._clock(),
            }
        )


def _validate_assertion(
    *,
    object_id: str,
    tenant_id: str,
    source: str,
    observed_at: str,
    evidence_refs: tuple[EvidenceRef, ...],
    validity: ValidityWindow,
) -> WorldStateAdmission | None:
    denial = _validate_evidence(
        object_id=object_id,
        tenant_id=tenant_id,
        source=source,
        observed_at=observed_at,
        evidence_refs=evidence_refs,
    )
    if denial:
        return denial
    if not validity.valid_from:
        return WorldStateAdmission(False, "valid_from_required", object_id)
    return None


def _validate_evidence(
    *,
    object_id: str,
    tenant_id: str,
    source: str,
    observed_at: str,
    evidence_refs: tuple[EvidenceRef, ...],
) -> WorldStateAdmission | None:
    if not object_id:
        return WorldStateAdmission(False, "object_id_required")
    if not tenant_id:
        return WorldStateAdmission(False, "tenant_required", object_id)
    if not source:
        return WorldStateAdmission(False, "source_required", object_id)
    if not observed_at:
        return WorldStateAdmission(False, "observed_at_required", object_id)
    if not evidence_refs:
        return WorldStateAdmission(False, "evidence_required", object_id)
    for evidence in evidence_refs:
        if not evidence.evidence_id or not evidence.evidence_type or not evidence.source:
            return WorldStateAdmission(False, "evidence_incomplete", object_id)
    return None


def _missing_refs(
    refs: Iterable[str],
    objects: dict[str, Any],
    *,
    tenant_id: str,
) -> list[str]:
    missing: list[str] = []
    for ref in refs:
        stored = objects.get(ref)
        if stored is None or getattr(stored, "tenant_id", "") != tenant_id:
            missing.append(ref)
    return missing


def _open_contradiction_refs(contradictions: Iterable[Contradiction], *, tenant_id: str) -> set[str]:
    blocked: set[str] = set()
    for contradiction in contradictions:
        if contradiction.tenant_id == tenant_id and contradiction.status == "open":
            blocked.update(contradiction.refs)
    return blocked


def _stamp_entity(entity: WorldEntity, now: str) -> WorldEntity:
    created_at = entity.created_at or now
    payload = asdict(replace(entity, created_at=created_at, state_hash=""))
    return replace(entity, created_at=created_at, state_hash=_canonical_hash(payload))


def _stamp_relation(relation: WorldRelation, now: str) -> WorldRelation:
    created_at = relation.created_at or now
    payload = asdict(replace(relation, created_at=created_at, state_hash=""))
    return replace(relation, created_at=created_at, state_hash=_canonical_hash(payload))


def _stamp_event(event: WorldEvent, now: str) -> WorldEvent:
    created_at = event.created_at or now
    payload = asdict(replace(event, created_at=created_at, event_hash=""))
    return replace(event, created_at=created_at, event_hash=_canonical_hash(payload))


def _stamp_claim(claim: WorldClaim, now: str) -> WorldClaim:
    created_at = claim.created_at or now
    payload = asdict(replace(claim, created_at=created_at, claim_hash=""))
    return replace(claim, created_at=created_at, claim_hash=_canonical_hash(payload))


def _stamp_contradiction(contradiction: Contradiction, now: str) -> Contradiction:
    created_at = contradiction.created_at or now
    payload = asdict(replace(contradiction, created_at=created_at, contradiction_hash=""))
    return replace(
        contradiction,
        created_at=created_at,
        contradiction_hash=_canonical_hash(payload),
    )
