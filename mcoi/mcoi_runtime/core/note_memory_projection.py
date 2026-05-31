"""Read-only projection engine for governed note memory.

Purpose: materialize note-memory events, Concept Boxes, traversal findings, and
scores into operational state without executing actions.
Governance scope: append-only rebuildability, inactive-note exclusion,
conflict clustering, blocker detection, candidate-only action extraction, and
deterministic projection receipts.
Dependencies: dataclasses, note-memory mesh events, Concept Boxes, axis
findings, scoring receipts, and runtime invariant helpers.
Invariants: projections are derived state; expired, superseded, contradicted,
or rejected notes cannot silently influence execution.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import StrEnum
from hashlib import sha256
import json
from typing import Mapping, Sequence

from mcoi_runtime.core.concept_box_ledger import ConceptBox
from mcoi_runtime.core.incepta_scoring_adapter import InceptaScore
from mcoi_runtime.core.inceptadive_axis_traversal import AxisFinding, DeltaType
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, stable_identifier
from mcoi_runtime.core.note_memory_mesh import NoteAction, NoteMemoryEvent, ProofState


class ProjectedClaimState(StrEnum):
    """Materialized claim states."""

    ACTIVE = "active"
    SUPERSEDED = "superseded"
    CONTRADICTED = "contradicted"
    EXPIRED = "expired"
    REJECTED = "rejected"


class CandidateActionStatus(StrEnum):
    """Candidate action readiness classes."""

    READY_FOR_GOVERNANCE = "ready_for_governance"
    BLOCKED = "blocked"
    REPAIR_REQUIRED = "repair_required"


@dataclass(frozen=True)
class ProjectedClaim:
    """One active or inactive claim derived from note memory."""

    claim_id: str
    note_id: str
    event_id: str
    scope: str
    claim_text: str
    state: ProjectedClaimState
    proof_state: ProofState
    confidence: float
    evidence_refs: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible projected claim."""

        return {
            "claim_id": self.claim_id,
            "note_id": self.note_id,
            "event_id": self.event_id,
            "scope": self.scope,
            "claim_text": self.claim_text,
            "state": self.state.value,
            "proof_state": self.proof_state.value,
            "confidence": self.confidence,
            "evidence_refs": list(self.evidence_refs),
        }


@dataclass(frozen=True)
class ConflictCluster:
    """Contradiction cluster derived from note relation refs."""

    conflict_id: str
    source_note_ids: tuple[str, ...]
    relation_refs: tuple[str, ...]
    reason: str

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible conflict cluster."""

        return {
            "conflict_id": self.conflict_id,
            "source_note_ids": list(self.source_note_ids),
            "relation_refs": list(self.relation_refs),
            "reason": self.reason,
        }


@dataclass(frozen=True)
class ProjectionBlocker:
    """Operational blocker derived from active claims or fracture findings."""

    blocker_id: str
    source_ids: tuple[str, ...]
    scope: str
    reason: str
    severity: str

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible blocker."""

        return {
            "blocker_id": self.blocker_id,
            "source_ids": list(self.source_ids),
            "scope": self.scope,
            "reason": self.reason,
            "severity": self.severity,
        }


@dataclass(frozen=True)
class ProjectionCandidateAction:
    """Candidate action extracted from projected state."""

    candidate_action_id: str
    action_type: str
    source_note_ids: tuple[str, ...]
    status: CandidateActionStatus
    reason: str
    execution_allowed: bool = False

    def __post_init__(self) -> None:
        if self.execution_allowed:
            raise RuntimeCoreInvariantError("projection candidate actions cannot allow execution")

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible candidate action."""

        return {
            "candidate_action_id": self.candidate_action_id,
            "action_type": self.action_type,
            "source_note_ids": list(self.source_note_ids),
            "status": self.status.value,
            "reason": self.reason,
            "execution_allowed": self.execution_allowed,
        }


@dataclass(frozen=True)
class ProjectionReceipt:
    """Deterministic receipt for one projection rebuild."""

    projection_id: str
    source_event_ids: tuple[str, ...]
    box_ids: tuple[str, ...]
    finding_ids: tuple[str, ...]
    score_ids: tuple[str, ...]
    active_claim_ids: tuple[str, ...]
    conflict_ids: tuple[str, ...]
    blocker_ids: tuple[str, ...]
    candidate_action_ids: tuple[str, ...]
    assessed_at: str
    snapshot_hash: str = ""

    def to_dict(self, *, include_snapshot_hash: bool = True) -> dict[str, object]:
        """Return a JSON-compatible receipt."""

        value: dict[str, object] = {
            "projection_id": self.projection_id,
            "source_event_ids": list(self.source_event_ids),
            "box_ids": list(self.box_ids),
            "finding_ids": list(self.finding_ids),
            "score_ids": list(self.score_ids),
            "active_claim_ids": list(self.active_claim_ids),
            "conflict_ids": list(self.conflict_ids),
            "blocker_ids": list(self.blocker_ids),
            "candidate_action_ids": list(self.candidate_action_ids),
            "assessed_at": self.assessed_at,
        }
        if include_snapshot_hash:
            value["snapshot_hash"] = self.snapshot_hash
        return value

    def expected_snapshot_hash(self) -> str:
        """Return the deterministic receipt hash."""

        return _hash_mapping(self.to_dict(include_snapshot_hash=False))

    def with_integrity(self) -> "ProjectionReceipt":
        """Return the receipt with deterministic snapshot hash populated."""

        unsigned = replace(self, snapshot_hash="")
        return replace(unsigned, snapshot_hash=unsigned.expected_snapshot_hash())


@dataclass(frozen=True)
class NoteMemoryProjection:
    """Current operational state derived from governed memory."""

    projection_id: str
    active_claims: tuple[ProjectedClaim, ...]
    inactive_claims: tuple[ProjectedClaim, ...]
    conflict_clusters: tuple[ConflictCluster, ...]
    blockers: tuple[ProjectionBlocker, ...]
    candidate_actions: tuple[ProjectionCandidateAction, ...]
    constructive_delta_ids: tuple[str, ...]
    fracture_delta_ids: tuple[str, ...]
    receipt: ProjectionReceipt

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible projection."""

        return {
            "projection_id": self.projection_id,
            "active_claims": [claim.to_dict() for claim in self.active_claims],
            "inactive_claims": [claim.to_dict() for claim in self.inactive_claims],
            "conflict_clusters": [cluster.to_dict() for cluster in self.conflict_clusters],
            "blockers": [blocker.to_dict() for blocker in self.blockers],
            "candidate_actions": [action.to_dict() for action in self.candidate_actions],
            "constructive_delta_ids": list(self.constructive_delta_ids),
            "fracture_delta_ids": list(self.fracture_delta_ids),
            "receipt": self.receipt.to_dict(),
        }


@dataclass(frozen=True)
class _MaterializedEventState:
    event: NoteMemoryEvent
    state: ProjectedClaimState


def project_note_memory(
    events: Sequence[NoteMemoryEvent],
    *,
    concept_boxes: Sequence[ConceptBox] = (),
    axis_findings: Sequence[AxisFinding] = (),
    scores: Sequence[InceptaScore] = (),
    assessed_at: str | None = None,
) -> NoteMemoryProjection:
    """Build a read-only operational projection from governed memory inputs."""

    now = assessed_at or datetime.now(timezone.utc).isoformat()
    materialized = _materialize_events(events, now)
    active_claims: list[ProjectedClaim] = []
    inactive_claims: list[ProjectedClaim] = []
    for state in materialized:
        claim = _claim_from_state(state)
        if claim.state == ProjectedClaimState.ACTIVE:
            active_claims.append(claim)
        else:
            inactive_claims.append(claim)
    conflicts = _conflicts_from_events(events)
    blockers = _blockers_from_claims(active_claims) + _blockers_from_findings(axis_findings, concept_boxes)
    candidate_actions = _candidate_actions_from_claims(active_claims, blockers)
    constructive_delta_ids = tuple(finding.finding_id for finding in axis_findings if finding.delta_type == DeltaType.CONSTRUCTIVE)
    fracture_delta_ids = tuple(finding.finding_id for finding in axis_findings if finding.delta_type == DeltaType.FRACTURE)
    projection_id = stable_identifier(
        "note-memory-projection",
        {
            "source_event_ids": tuple(event.event_id for event in events),
            "box_ids": tuple(box.box_id for box in concept_boxes),
            "finding_ids": tuple(finding.finding_id for finding in axis_findings),
            "score_ids": tuple(score.score_id for score in scores),
            "assessed_at": now,
        },
    )
    receipt = ProjectionReceipt(
        projection_id=projection_id,
        source_event_ids=tuple(event.event_id for event in events),
        box_ids=tuple(box.box_id for box in concept_boxes),
        finding_ids=tuple(finding.finding_id for finding in axis_findings),
        score_ids=tuple(score.score_id for score in scores),
        active_claim_ids=tuple(claim.claim_id for claim in active_claims),
        conflict_ids=tuple(conflict.conflict_id for conflict in conflicts),
        blocker_ids=tuple(blocker.blocker_id for blocker in blockers),
        candidate_action_ids=tuple(action.candidate_action_id for action in candidate_actions),
        assessed_at=now,
    ).with_integrity()
    return NoteMemoryProjection(
        projection_id=projection_id,
        active_claims=tuple(active_claims),
        inactive_claims=tuple(inactive_claims),
        conflict_clusters=tuple(conflicts),
        blockers=tuple(blockers),
        candidate_actions=tuple(candidate_actions),
        constructive_delta_ids=constructive_delta_ids,
        fracture_delta_ids=fracture_delta_ids,
        receipt=receipt,
    )


def _materialize_events(events: Sequence[NoteMemoryEvent], now: str) -> tuple[_MaterializedEventState, ...]:
    latest_by_note: dict[str, NoteMemoryEvent] = {}
    blocked_note_ids: dict[str, ProjectedClaimState] = {}
    event_to_note = {event.event_id: event.note_id for event in events}
    for event in sorted(events, key=lambda item: item.event_seq):
        latest_by_note[event.note_id] = event
        if event.action == NoteAction.SUPERSEDE:
            for relation_ref in event.relation_refs:
                blocked_note_ids[_related_note_id(relation_ref, event_to_note)] = ProjectedClaimState.SUPERSEDED
        if event.action == NoteAction.CONTRADICT:
            for relation_ref in event.relation_refs:
                blocked_note_ids[_related_note_id(relation_ref, event_to_note)] = ProjectedClaimState.CONTRADICTED
    states: list[_MaterializedEventState] = []
    now_dt = _parse_iso(now)
    for note_id, event in latest_by_note.items():
        state = blocked_note_ids.get(note_id, ProjectedClaimState.ACTIVE)
        if event.action == NoteAction.EXPIRE or (event.expires_at and _parse_iso(event.expires_at) <= now_dt):
            state = ProjectedClaimState.EXPIRED
        if event.proof_state == ProofState.FAIL:
            state = ProjectedClaimState.REJECTED
        states.append(_MaterializedEventState(event=event, state=state))
    return tuple(sorted(states, key=lambda item: item.event.event_seq))


def _claim_from_state(state: _MaterializedEventState) -> ProjectedClaim:
    event = state.event
    claim_id = stable_identifier(
        "projected-claim",
        {"event_id": event.event_id, "note_id": event.note_id, "state": state.state.value},
    )
    return ProjectedClaim(
        claim_id=claim_id,
        note_id=event.note_id,
        event_id=event.event_id,
        scope=event.scope.value,
        claim_text=event.content_summary,
        state=state.state,
        proof_state=event.proof_state,
        confidence=_confidence_for(event.proof_state),
        evidence_refs=event.evidence_refs,
    )


def _conflicts_from_events(events: Sequence[NoteMemoryEvent]) -> tuple[ConflictCluster, ...]:
    clusters: list[ConflictCluster] = []
    event_to_note = {event.event_id: event.note_id for event in events}
    for event in events:
        if event.action != NoteAction.CONTRADICT:
            continue
        source_note_ids = tuple(sorted({event.note_id, *(_related_note_id(ref, event_to_note) for ref in event.relation_refs)}))
        conflict_id = stable_identifier("memory-conflict", {"source_note_ids": source_note_ids, "event_id": event.event_id})
        clusters.append(
            ConflictCluster(
                conflict_id=conflict_id,
                source_note_ids=source_note_ids,
                relation_refs=event.relation_refs,
                reason=event.content_summary,
            )
        )
    return tuple(clusters)


def _blockers_from_claims(claims: Sequence[ProjectedClaim]) -> tuple[ProjectionBlocker, ...]:
    markers = ("blocked", "pending", "missing", "requires", "required", "not approved", "unsafe", "risk")
    blockers: list[ProjectionBlocker] = []
    for claim in claims:
        lower_claim = claim.claim_text.lower()
        if any(marker in lower_claim for marker in markers):
            blocker_id = stable_identifier("projection-blocker", {"claim_id": claim.claim_id, "reason": claim.claim_text})
            blockers.append(
                ProjectionBlocker(
                    blocker_id=blocker_id,
                    source_ids=(claim.note_id,),
                    scope=claim.scope,
                    reason=claim.claim_text,
                    severity="high" if any(marker in lower_claim for marker in ("blocked", "unsafe", "risk")) else "medium",
                )
            )
    return tuple(blockers)


def _blockers_from_findings(
    findings: Sequence[AxisFinding],
    concept_boxes: Sequence[ConceptBox],
) -> tuple[ProjectionBlocker, ...]:
    box_note_ids = {box.box_id: box.source_note_ids for box in concept_boxes}
    blockers: list[ProjectionBlocker] = []
    for finding in findings:
        if finding.delta_type != DeltaType.FRACTURE:
            continue
        source_note_ids = box_note_ids.get(finding.source_box_id, ())
        if not source_note_ids:
            raise RuntimeCoreInvariantError("fracture finding blocker requires Concept Box source note lineage")
        blocker_id = stable_identifier("projection-blocker", {"finding_id": finding.finding_id})
        blockers.append(
            ProjectionBlocker(
                blocker_id=blocker_id,
                source_ids=source_note_ids,
                scope="axis-finding",
                reason=finding.repair_requirement,
                severity="high" if finding.suppression.execution_risk >= 0.5 else "medium",
            )
        )
    return tuple(blockers)


def _candidate_actions_from_claims(
    claims: Sequence[ProjectedClaim],
    blockers: Sequence[ProjectionBlocker],
) -> tuple[ProjectionCandidateAction, ...]:
    action_markers = {
        "deploy": ("deploy", "release", "publish"),
        "test": ("test", "verify", "validation"),
        "review": ("review", "approval", "approve"),
        "repair": ("repair", "fix", "resolve"),
        "request_evidence": ("evidence", "missing", "pending"),
        "update_documentation": ("document", "docs", "readme"),
    }
    blocking_note_ids = {source_id for blocker in blockers for source_id in blocker.source_ids}
    actions: list[ProjectionCandidateAction] = []
    for claim in claims:
        lower_claim = claim.claim_text.lower()
        for action_type, markers in action_markers.items():
            if not any(marker in lower_claim for marker in markers):
                continue
            blocked = claim.note_id in blocking_note_ids or (action_type == "deploy" and bool(blockers))
            status = CandidateActionStatus.BLOCKED if blocked else CandidateActionStatus.READY_FOR_GOVERNANCE
            reason = "blocked by projection blockers" if blocked else "candidate requires governance verdict before execution"
            candidate_action_id = stable_identifier(
                "candidate-action",
                {"claim_id": claim.claim_id, "action_type": action_type, "status": status.value},
            )
            actions.append(
                ProjectionCandidateAction(
                    candidate_action_id=candidate_action_id,
                    action_type=action_type,
                    source_note_ids=(claim.note_id,),
                    status=status,
                    reason=reason,
                )
            )
    return tuple(actions)


def _related_note_id(relation_ref: str, event_to_note: Mapping[str, str]) -> str:
    return event_to_note.get(relation_ref, relation_ref)


def _confidence_for(proof_state: ProofState) -> float:
    return {
        ProofState.PASS: 0.9,
        ProofState.UNKNOWN: 0.45,
        ProofState.BUDGET_UNKNOWN: 0.2,
        ProofState.FAIL: 0.0,
    }[proof_state]


def _parse_iso(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError as exc:
        raise RuntimeCoreInvariantError(f"invalid iso timestamp: {value}") from exc


def _hash_mapping(value: Mapping[str, object]) -> str:
    material = json.dumps(dict(value), sort_keys=True, separators=(",", ":"), default=str)
    return sha256(material.encode("utf-8")).hexdigest()
