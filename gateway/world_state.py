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


@dataclass(frozen=True, slots=True)
class RepositoryObservationProjectionAdmission:
    """Typed admission result for one repository-observation projection object."""

    object_type: str
    admission: WorldStateAdmission


@dataclass(frozen=True, slots=True)
class RepositoryObservationWorldStateProjection:
    """World-state projection result for one repository observation packet."""

    packet_id: str
    tenant_id: str
    state: WorldState
    admissions: tuple[RepositoryObservationProjectionAdmission, ...]
    blocked_reasons: tuple[str, ...] = ()

    @property
    def admitted(self) -> bool:
        """Return whether every projected object was admitted."""

        return all(item.admission.accepted for item in self.admissions)


@dataclass(frozen=True, slots=True)
class ProblemStarEvidenceItem:
    """Schema-compatible ProblemStar evidence input item."""

    evidence_id: str
    source_ref: str
    statement: str
    confidence: float

    def as_receipt_evidence(self) -> dict[str, Any]:
        """Return the JSON object shape accepted by the ProblemStar receipt."""

        return {
            "evidence_id": self.evidence_id,
            "source_ref": self.source_ref,
            "statement": self.statement,
            "confidence": self.confidence,
        }


@dataclass(frozen=True, slots=True)
class ProblemStarEvidenceBinding:
    """Repository world-state to ProblemStar evidence binding result."""

    packet_id: str
    tenant_id: str
    state_id: str
    state_hash: str
    admitted: bool
    evidence_items: tuple[ProblemStarEvidenceItem, ...]
    proof_obligations: tuple[dict[str, str], ...]
    blocked_reasons: tuple[str, ...] = ()

    def as_problem_star_evidence(self) -> tuple[dict[str, Any], ...]:
        """Return separated ProblemStar evidence surface objects."""

        return tuple(item.as_receipt_evidence() for item in self.evidence_items)


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


def project_repository_observation_packet_to_world_state(
    packet: dict[str, Any],
    store: WorldStateStore,
) -> RepositoryObservationWorldStateProjection:
    """Project one repository observation evidence packet into world state.

    Input contract: packet is a repository observation evidence packet shaped
    as a dictionary and store admits existing World State assertions.
    Output contract: returns typed admission results and a tenant projection.
    Error contract: raises ValueError when required packet sections are absent.
    """

    packet_id = _require_text(packet, "packet_id")
    generated_at = _require_text(packet, "generated_at")
    scope = _require_mapping(packet, "observation_scope")
    observed_state = _require_mapping(packet, "observed_state")
    evidence_admission = _require_mapping(packet, "evidence_admission")
    tenant_id = _require_text(scope, "tenant_scope")
    repository_ref = _require_text(scope, "repository_ref")
    worktree_ref = _require_text(scope, "worktree_ref")
    observed_at = _require_text(observed_state, "observed_at")
    valid_until = str(observed_state.get("fresh_until", ""))
    proof_state = _require_text(evidence_admission, "proof_state")
    planning_allowed = evidence_admission.get("hard_constraint_planning_allowed") is True and proof_state == "Pass"
    evidence_ref = EvidenceRef(
        evidence_id=packet_id,
        evidence_type="repository_observation_evidence_packet",
        source=_require_text(scope, "collector_ref"),
        observed_at=observed_at,
        uri=packet_id,
        content_hash=_hash_payload_ref(packet),
        metadata={
            "observation_mode": str(scope.get("observation_mode", "")),
            "command_set_ref": str(observed_state.get("command_set_ref", "")),
        },
    )
    validity = ValidityWindow(
        valid_from=observed_at,
        valid_until=valid_until,
        requires_refresh=observed_state.get("freshness_state") != "fresh",
    )
    repository_entity_id = f"{packet_id}:repository"
    worktree_entity_id = f"{packet_id}:worktree"
    relation_id = f"{packet_id}:repository-worktree"
    repository_entity = WorldEntity(
        entity_id=repository_entity_id,
        tenant_id=tenant_id,
        entity_type="repository",
        display_name=repository_ref,
        evidence_refs=(evidence_ref,),
        source="repository_observation_evidence_packet",
        observed_at=observed_at,
        validity=validity,
        attributes={
            "repository_ref": repository_ref,
            "source_kind": str(scope.get("source_kind", "")),
        },
        trust_class="repository_observation",
        allowed_for_planning=planning_allowed,
        allowed_for_execution=False,
    )
    worktree_entity = WorldEntity(
        entity_id=worktree_entity_id,
        tenant_id=tenant_id,
        entity_type="repository_worktree",
        display_name=worktree_ref,
        evidence_refs=(evidence_ref,),
        source="repository_observation_evidence_packet",
        observed_at=observed_at,
        validity=validity,
        attributes={
            "worktree_ref": worktree_ref,
            "observation_mode": str(scope.get("observation_mode", "")),
        },
        trust_class="repository_observation",
        allowed_for_planning=planning_allowed,
        allowed_for_execution=False,
    )
    relation = WorldRelation(
        relation_id=relation_id,
        tenant_id=tenant_id,
        relation_type="repository_has_worktree",
        source_entity_id=repository_entity_id,
        target_entity_id=worktree_entity_id,
        evidence_refs=(evidence_ref,),
        source="repository_observation_evidence_packet",
        observed_at=observed_at,
        validity=validity,
        attributes={"packet_id": packet_id},
        trust_class="repository_observation",
        allowed_for_planning=planning_allowed,
        allowed_for_execution=False,
    )
    claim_specs = (
        ("observation_mode", str(scope.get("observation_mode", ""))),
        ("freshness_state", str(observed_state.get("freshness_state", ""))),
        ("proof_state", proof_state),
        ("planning_admission", str(evidence_admission.get("planning_admission", ""))),
        ("branch_digest_ref", str(observed_state.get("branch_digest_ref", ""))),
        ("git_status_digest_ref", str(observed_state.get("git_status_digest_ref", ""))),
        ("diff_digest_ref", str(observed_state.get("diff_digest_ref", ""))),
        ("file_inventory_digest_ref", str(observed_state.get("file_inventory_digest_ref", ""))),
    )
    claims = tuple(
        WorldClaim(
            claim_id=f"{packet_id}:claim:{predicate}",
            tenant_id=tenant_id,
            subject_ref=worktree_entity_id,
            predicate=f"repository_{predicate}",
            object_value=value,
            evidence_refs=(evidence_ref,),
            source="repository_observation_evidence_packet",
            observed_at=observed_at,
            validity=validity,
            confidence=1.0 if planning_allowed else 0.0,
            trust_class="repository_observation",
            freshness_window_days=1,
            domain_risk="medium",
            allowed_for_planning=planning_allowed,
            allowed_for_execution=False,
        )
        for predicate, value in claim_specs
    )
    event = WorldEvent(
        event_id=f"{packet_id}:event:observed",
        tenant_id=tenant_id,
        event_type="repository_observation_projected",
        occurred_at=generated_at,
        evidence_refs=(evidence_ref,),
        source="repository_observation_evidence_packet",
        entity_refs=(repository_entity_id, worktree_entity_id),
        relation_refs=(relation_id,),
        claim_refs=tuple(claim.claim_id for claim in claims),
        attributes={
            "solver_outcome": str(evidence_admission.get("solver_outcome", "")),
            "live_evidence_state": str(evidence_admission.get("live_evidence_state", "")),
        },
    )
    contradiction_refs = tuple(str(ref) for ref in observed_state.get("contradiction_refs", ()) if str(ref))
    contradiction = None
    if contradiction_refs or proof_state == "Fail":
        contradiction = Contradiction(
            contradiction_id=f"{packet_id}:contradiction:planning-block",
            tenant_id=tenant_id,
            refs=(
                f"{packet_id}:claim:proof_state",
                f"{packet_id}:claim:planning_admission",
                *contradiction_refs,
            ),
            reason=_repository_observation_block_reason(proof_state, contradiction_refs),
            evidence_refs=(evidence_ref,),
            source="repository_observation_evidence_packet",
            observed_at=observed_at,
            severity="high" if proof_state == "Fail" else "medium",
            status="open",
        )

    admissions: list[RepositoryObservationProjectionAdmission] = []
    admissions.append(RepositoryObservationProjectionAdmission("entity", store.add_entity(repository_entity)))
    admissions.append(RepositoryObservationProjectionAdmission("entity", store.add_entity(worktree_entity)))
    admissions.append(RepositoryObservationProjectionAdmission("relation", store.add_relation(relation)))
    for claim in claims:
        admissions.append(RepositoryObservationProjectionAdmission("claim", store.add_claim(claim)))
    admissions.append(RepositoryObservationProjectionAdmission("event", store.add_event(event)))
    if contradiction is not None:
        admissions.append(
            RepositoryObservationProjectionAdmission(
                "contradiction",
                store.add_contradiction(contradiction),
            )
        )
    blocked_reasons = tuple(
        item.admission.reason
        for item in admissions
        if not item.admission.accepted
    )
    if not planning_allowed:
        blocked_reasons += (_repository_observation_block_reason(proof_state, contradiction_refs),)
    return RepositoryObservationWorldStateProjection(
        packet_id=packet_id,
        tenant_id=tenant_id,
        state=store.materialize(tenant_id=tenant_id),
        admissions=tuple(admissions),
        blocked_reasons=blocked_reasons,
    )


def bind_repository_world_state_projection_to_problem_star_evidence(
    projection: RepositoryObservationWorldStateProjection,
    planning_claims: Iterable[WorldClaim],
) -> ProblemStarEvidenceBinding:
    """Bind admitted repository world-state claims into ProblemStar evidence.

    Input contract: projection comes from a repository observation packet and
    planning_claims are already filtered by the World State Store.
    Output contract: returns schema-compatible evidence items only for
    same-tenant, same-packet, planning-eligible claims.
    Error contract: blocked or contradicted projections return no evidence
    items and expose proof obligations; no exception is raised for denial.
    """

    blocked_reasons = list(projection.blocked_reasons)
    if not projection.admitted:
        blocked_reasons.extend(
            f"{item.object_type}:{item.admission.reason}"
            for item in projection.admissions
            if not item.admission.accepted
        )
    if projection.state.open_contradiction_count:
        blocked_reasons.append("repository world-state projection has open contradictions")

    eligible_claims = tuple(
        sorted(
            (
                claim
                for claim in planning_claims
                if _claim_belongs_to_repository_projection(projection, claim)
            ),
            key=lambda claim: claim.claim_id,
        )
    )
    if blocked_reasons or not eligible_claims:
        if not blocked_reasons:
            blocked_reasons.append("repository world-state projection has no admitted planning claims")
        return ProblemStarEvidenceBinding(
            packet_id=projection.packet_id,
            tenant_id=projection.tenant_id,
            state_id=projection.state.state_id,
            state_hash=projection.state.state_hash,
            admitted=False,
            evidence_items=(),
            proof_obligations=(
                {
                    "obligation_id": f"{projection.packet_id}:proof:repository-world-state-evidence-blocked",
                    "description": "Repository world-state evidence cannot enter ProblemStar until planning claims are admitted.",
                    "proof_state": _blocked_problem_star_proof_state(tuple(blocked_reasons)),
                    "required_before": "solver_routing",
                },
            ),
            blocked_reasons=tuple(_ordered_unique(blocked_reasons)),
        )

    evidence_items = tuple(
        ProblemStarEvidenceItem(
            evidence_id=f"{claim.claim_id}:problem-star-evidence",
            source_ref=f"world-state://{projection.state.state_id}/claims/{claim.claim_id}",
            statement=(
                f"{claim.subject_ref} asserts {claim.predicate} = {claim.object_value} "
                f"under state {projection.state.state_hash}"
            ),
            confidence=claim.confidence,
        )
        for claim in eligible_claims
    )
    return ProblemStarEvidenceBinding(
        packet_id=projection.packet_id,
        tenant_id=projection.tenant_id,
        state_id=projection.state.state_id,
        state_hash=projection.state.state_hash,
        admitted=True,
        evidence_items=evidence_items,
        proof_obligations=(
            {
                "obligation_id": f"{projection.packet_id}:proof:repository-world-state-evidence-bound",
                "description": "Admitted repository world-state planning claims were converted into separated ProblemStar evidence items.",
                "proof_state": "Pass",
                "required_before": "solver_routing",
            },
        ),
        blocked_reasons=(),
    )


def _repository_observation_block_reason(
    proof_state: str,
    contradiction_refs: tuple[str, ...],
) -> str:
    if contradiction_refs:
        return "repository observation command contradiction blocks planning admission"
    if proof_state != "Pass":
        return f"repository observation proof state {proof_state} blocks hard planning"
    return "repository observation planning admission blocked"


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


def _require_mapping(payload: dict[str, Any], field_name: str) -> dict[str, Any]:
    value = payload.get(field_name)
    if not isinstance(value, dict):
        raise ValueError(f"repository observation packet missing object field: {field_name}")
    return value


def _require_text(payload: dict[str, Any], field_name: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value:
        raise ValueError(f"repository observation packet missing text field: {field_name}")
    return value


def _hash_payload_ref(payload: dict[str, Any]) -> str:
    return f"hash://sha256/{_canonical_hash(payload)}"


def _claim_belongs_to_repository_projection(
    projection: RepositoryObservationWorldStateProjection,
    claim: WorldClaim,
) -> bool:
    return (
        claim.tenant_id == projection.tenant_id
        and claim.claim_id.startswith(f"{projection.packet_id}:claim:")
        and claim.allowed_for_planning
        and not claim.allowed_for_execution
    )


def _blocked_problem_star_proof_state(blocked_reasons: tuple[str, ...]) -> str:
    if any("contradiction" in reason or "Fail" in reason for reason in blocked_reasons):
        return "Fail"
    return "Unknown"


def _ordered_unique(values: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return tuple(unique)


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
