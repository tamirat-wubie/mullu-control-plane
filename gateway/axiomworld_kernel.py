"""AxiomWorld MVP-1 world-state kernel overlay.

Purpose: Provide a governed observe -> claim -> conflict -> receipt ->
    projection loop over the existing gateway world-state store.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: gateway.world_state, standard-library dataclasses, enum, and
    deterministic hashing through the underlying world-state store.
Invariants:
  - Symbols enter world state only through sourced observations.
  - Unsupported claims remain hypotheses outside the admitted world graph.
  - Simulated claims cannot be promoted as validated reality without evidence.
  - Identity collisions quarantine instead of silently merging symbols.
  - Projection hides private scoped records from public observers.
  - Actions are proposals until risk and reversibility gates are satisfied.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Any, Callable, Mapping

from gateway.world_state import (
    Contradiction,
    EvidenceRef,
    InMemoryWorldStateStore,
    ValidityWindow,
    WorldClaim,
    WorldEntity,
    WorldState,
    WorldStateAdmission,
    WorldStateStore,
)


def _utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


class AxiomTruthState(StrEnum):
    """Governed truth state for MVP-1 symbols and claims."""

    UNOBSERVED = "UNOBSERVED"
    PROPOSED = "PROPOSED"
    HYPOTHESIS = "HYPOTHESIS"
    SUPPORTED = "SUPPORTED"
    VALIDATED = "VALIDATED"
    CANONICAL = "CANONICAL"
    CONFLICTED = "CONFLICTED"
    REVOKED = "REVOKED"
    DEPRECATED = "DEPRECATED"
    SIMULATED = "SIMULATED"
    SUPERSEDED = "SUPERSEDED"


class AxiomDecision(StrEnum):
    """Decision envelope for kernel receipts."""

    ACCEPT = "ACCEPT"
    REJECT = "REJECT"
    QUARANTINE = "QUARANTINE"
    SIMULATE_ONLY = "SIMULATE_ONLY"
    REQUIRE_EVIDENCE = "REQUIRE_EVIDENCE"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"


class AxiomActionStatus(StrEnum):
    """Lifecycle state for action proposals."""

    PROPOSED = "PROPOSED"
    CHECKED = "CHECKED"
    SIMULATED = "SIMULATED"
    APPROVED = "APPROVED"
    EXECUTING = "EXECUTING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    COMMITTED = "COMMITTED"
    COMPENSATED = "COMPENSATED"


class AxiomRiskLevel(StrEnum):
    """Bounded action risk levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AxiomReversibility(StrEnum):
    """Rollback class for a proposed action."""

    FULL = "full"
    COMPENSATABLE = "compensatable"
    PARTIAL = "partial"
    IRREVERSIBLE = "irreversible"
    UNKNOWN = "unknown"


class AxiomProjectionScope(StrEnum):
    """Observer-visible projection scopes."""

    PUBLIC = "public"
    INTERNAL = "internal"
    PRIVATE = "private"
    SIMULATION = "simulation"


_ALLOWED_TRUTH_TRANSITIONS: dict[AxiomTruthState, frozenset[AxiomTruthState]] = {
    AxiomTruthState.UNOBSERVED: frozenset(
        {AxiomTruthState.PROPOSED, AxiomTruthState.HYPOTHESIS}
    ),
    AxiomTruthState.PROPOSED: frozenset(
        {AxiomTruthState.HYPOTHESIS, AxiomTruthState.SUPPORTED, AxiomTruthState.SIMULATED}
    ),
    AxiomTruthState.HYPOTHESIS: frozenset(
        {AxiomTruthState.SUPPORTED, AxiomTruthState.CONFLICTED, AxiomTruthState.REVOKED}
    ),
    AxiomTruthState.SUPPORTED: frozenset(
        {
            AxiomTruthState.VALIDATED,
            AxiomTruthState.CONFLICTED,
            AxiomTruthState.DEPRECATED,
            AxiomTruthState.REVOKED,
        }
    ),
    AxiomTruthState.VALIDATED: frozenset(
        {
            AxiomTruthState.CANONICAL,
            AxiomTruthState.CONFLICTED,
            AxiomTruthState.DEPRECATED,
            AxiomTruthState.REVOKED,
            AxiomTruthState.SUPERSEDED,
        }
    ),
    AxiomTruthState.CANONICAL: frozenset(
        {AxiomTruthState.SUPERSEDED, AxiomTruthState.CONFLICTED}
    ),
    AxiomTruthState.CONFLICTED: frozenset(
        {AxiomTruthState.SUPPORTED, AxiomTruthState.REVOKED, AxiomTruthState.DEPRECATED}
    ),
    AxiomTruthState.SIMULATED: frozenset(
        {AxiomTruthState.SUPPORTED, AxiomTruthState.REVOKED}
    ),
}

_INACTIVE_TRUTH_STATES = frozenset(
    {
        AxiomTruthState.REVOKED,
        AxiomTruthState.DEPRECATED,
        AxiomTruthState.SUPERSEDED,
    }
)


@dataclass(frozen=True, slots=True)
class AxiomConfidenceVector:
    """Explainable confidence components for a symbol or claim."""

    source_reliability: float = 0.5
    evidence_quality: float = 0.5
    temporal_freshness: float = 0.5
    causal_coherence: float = 0.5
    graph_consistency: float = 0.5
    permission_safety: float = 1.0
    counterevidence_pressure: float = 0.0

    def overall(self) -> float:
        """Return a bounded confidence score derived from all components."""
        positive = (
            self.source_reliability
            + self.evidence_quality
            + self.temporal_freshness
            + self.causal_coherence
            + self.graph_consistency
            + self.permission_safety
        ) / 6.0
        return _clip_unit(positive - self.counterevidence_pressure)


@dataclass(frozen=True, slots=True)
class AxiomObservationEvent:
    """Input contract for one observed symbol."""

    entity_id: str
    tenant_id: str
    entity_type: str
    display_name: str
    source: str
    observed_at: str
    evidence_refs: tuple[EvidenceRef, ...]
    stable_fingerprint: Mapping[str, Any]
    attributes: Mapping[str, Any] = field(default_factory=dict)
    aliases: tuple[str, ...] = ()
    scope: AxiomProjectionScope = AxiomProjectionScope.INTERNAL
    permissions: Mapping[str, bool] = field(default_factory=dict)
    validity: ValidityWindow | None = None
    confidence: AxiomConfidenceVector = field(default_factory=AxiomConfidenceVector)


@dataclass(frozen=True, slots=True)
class AxiomClaimProposal:
    """Input contract for one claim proposal."""

    claim_id: str
    tenant_id: str
    subject_ref: str
    predicate: str
    object_value: str
    source: str
    observed_at: str
    evidence_refs: tuple[EvidenceRef, ...] = ()
    confidence: AxiomConfidenceVector = field(default_factory=AxiomConfidenceVector)
    scope: AxiomProjectionScope = AxiomProjectionScope.INTERNAL
    simulated: bool = False
    allowed_for_planning: bool = True
    allowed_for_execution: bool = False
    validity: ValidityWindow | None = None


@dataclass(frozen=True, slots=True)
class AxiomActionProposal:
    """Input contract for one governed action proposal."""

    action_id: str
    tenant_id: str
    actor: str
    intent: str
    target_ref: str
    risk_level: AxiomRiskLevel
    reversibility: AxiomReversibility
    permissions_required: tuple[str, ...] = ()
    preconditions: tuple[str, ...] = ()
    expected_delta: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AxiomSymbolRecord:
    """Kernel-side index of an admitted symbol."""

    entity_id: str
    tenant_id: str
    kind: str
    label: str
    stable_fingerprint: Mapping[str, Any]
    aliases: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    truth_state: AxiomTruthState
    confidence: AxiomConfidenceVector
    scope: AxiomProjectionScope
    permissions: Mapping[str, bool]
    world_state_hash: str


@dataclass(frozen=True, slots=True)
class AxiomClaimRecord:
    """Kernel-side index of a governed claim."""

    claim_id: str
    tenant_id: str
    subject_ref: str
    predicate: str
    object_value: str
    evidence_ids: tuple[str, ...]
    truth_state: AxiomTruthState
    confidence: AxiomConfidenceVector
    scope: AxiomProjectionScope
    admitted_to_world_state: bool
    simulated: bool


@dataclass(frozen=True, slots=True)
class AxiomActionRecord:
    """Kernel-side index of a governed action proposal."""

    action_id: str
    tenant_id: str
    actor: str
    intent: str
    target_ref: str
    risk_level: AxiomRiskLevel
    reversibility: AxiomReversibility
    status: AxiomActionStatus
    permissions_required: tuple[str, ...]
    preconditions: tuple[str, ...]
    expected_delta: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class AxiomWorldReceipt:
    """Append-only causal receipt for one kernel decision."""

    receipt_id: str
    decision: AxiomDecision
    reason: str
    object_id: str
    evidence_used: tuple[str, ...]
    rules_applied: tuple[str, ...]
    conflicts: tuple[str, ...] = ()
    reversible: bool = True
    world_state_hash: str = ""
    created_at: str = ""


@dataclass(frozen=True, slots=True)
class AxiomProjection:
    """Observer-safe projection over the kernel-side indexes."""

    observer: str
    scope: AxiomProjectionScope
    tenant_id: str
    symbols: tuple[Mapping[str, Any], ...]
    claims: tuple[Mapping[str, Any], ...]
    redactions: tuple[str, ...]
    projected_at: str
    world_state_hash: str


class AxiomWorldKernel:
    """MVP-1 governed world-state graph kernel.

    The kernel is an admission and projection overlay. It does not expose
    direct mutation of the underlying world-state store.
    """

    def __init__(
        self,
        *,
        store: WorldStateStore | None = None,
        clock: Callable[[], str] | None = None,
    ) -> None:
        self._clock = clock or _utc_now
        self._store = store or InMemoryWorldStateStore(clock=self._clock)
        self._symbols: dict[str, AxiomSymbolRecord] = {}
        self._claims: dict[str, AxiomClaimRecord] = {}
        self._actions: dict[str, AxiomActionRecord] = {}
        self._fingerprints: dict[str, str] = {}
        self._receipts: list[AxiomWorldReceipt] = []
        self._receipt_counter = 0

    def observe_event(self, event: AxiomObservationEvent) -> AxiomWorldReceipt:
        """Admit an observed symbol if evidence and identity checks pass."""
        fingerprint_key = _fingerprint_key(event.stable_fingerprint)
        existing_entity_id = self._fingerprints.get(fingerprint_key)
        if existing_entity_id and existing_entity_id != event.entity_id:
            return self._record_receipt(
                decision=AxiomDecision.QUARANTINE,
                reason="identity_conflict_detected",
                object_id=event.entity_id,
                evidence_used=_evidence_ids(event.evidence_refs),
                rules_applied=("no_silent_identity_merge",),
                conflicts=(f"possible_same_as:{existing_entity_id}",),
                reversible=True,
                tenant_id=event.tenant_id,
            )

        validity = event.validity or ValidityWindow(valid_from=event.observed_at)
        entity = WorldEntity(
            entity_id=event.entity_id,
            tenant_id=event.tenant_id,
            entity_type=event.entity_type,
            display_name=event.display_name,
            evidence_refs=event.evidence_refs,
            source=event.source,
            observed_at=event.observed_at,
            validity=validity,
            attributes={
                **dict(event.attributes),
                "stable_fingerprint": dict(event.stable_fingerprint),
                "scope": event.scope.value,
            },
            trust_class="observed",
            allowed_for_planning=True,
            allowed_for_execution=False,
        )
        admission = self._store.add_entity(entity)
        if not admission.accepted:
            return self._admission_receipt(
                admission,
                event.tenant_id,
                event.evidence_refs,
                ("world_state_entity_admission",),
            )

        self._symbols[event.entity_id] = AxiomSymbolRecord(
            entity_id=event.entity_id,
            tenant_id=event.tenant_id,
            kind=event.entity_type,
            label=event.display_name,
            stable_fingerprint=dict(event.stable_fingerprint),
            aliases=tuple(event.aliases),
            evidence_ids=_evidence_ids(event.evidence_refs),
            truth_state=AxiomTruthState.SUPPORTED,
            confidence=event.confidence,
            scope=event.scope,
            permissions=dict(event.permissions),
            world_state_hash=admission.object_hash,
        )
        self._fingerprints[fingerprint_key] = event.entity_id
        return self._record_receipt(
            decision=AxiomDecision.ACCEPT,
            reason="observation_admitted",
            object_id=event.entity_id,
            evidence_used=_evidence_ids(event.evidence_refs),
            rules_applied=("evidence_attached", "identity_created", "receipt_committed"),
            reversible=True,
            tenant_id=event.tenant_id,
        )

    def propose_claim(self, proposal: AxiomClaimProposal) -> AxiomWorldReceipt:
        """Propose a claim and govern its admission state."""
        if proposal.subject_ref not in self._symbols:
            return self._record_receipt(
                decision=AxiomDecision.REJECT,
                reason="subject_not_observed",
                object_id=proposal.claim_id,
                evidence_used=_evidence_ids(proposal.evidence_refs),
                rules_applied=("claim_subject_requires_symbol",),
                reversible=True,
                tenant_id=proposal.tenant_id,
            )
        if proposal.simulated:
            self._claims[proposal.claim_id] = _claim_record(
                proposal,
                AxiomTruthState.SIMULATED,
                admitted_to_world_state=False,
            )
            return self._record_receipt(
                decision=AxiomDecision.SIMULATE_ONLY,
                reason="simulated_claim_recorded_outside_reality_graph",
                object_id=proposal.claim_id,
                evidence_used=_evidence_ids(proposal.evidence_refs),
                rules_applied=("simulation_not_reality",),
                reversible=True,
                tenant_id=proposal.tenant_id,
            )
        if not proposal.evidence_refs:
            self._claims[proposal.claim_id] = _claim_record(
                proposal,
                AxiomTruthState.HYPOTHESIS,
                admitted_to_world_state=False,
            )
            return self._record_receipt(
                decision=AxiomDecision.REQUIRE_EVIDENCE,
                reason="claim_requires_evidence_before_admission",
                object_id=proposal.claim_id,
                evidence_used=(),
                rules_applied=("no_validation_without_evidence",),
                reversible=True,
                tenant_id=proposal.tenant_id,
            )

        conflicts = self._claim_conflicts(proposal)
        claim_admission = self._admit_world_claim(proposal)
        if not claim_admission.accepted:
            return self._admission_receipt(
                claim_admission,
                proposal.tenant_id,
                proposal.evidence_refs,
                ("world_state_claim_admission",),
            )

        truth_state = AxiomTruthState.CONFLICTED if conflicts else AxiomTruthState.SUPPORTED
        self._claims[proposal.claim_id] = _claim_record(
            proposal,
            truth_state,
            admitted_to_world_state=True,
        )

        if conflicts:
            for conflict in conflicts:
                existing = self._claims[conflict]
                self._claims[existing.claim_id] = replace(
                    existing,
                    truth_state=AxiomTruthState.CONFLICTED,
                    confidence=replace(existing.confidence, counterevidence_pressure=0.3),
                )
            contradiction = self._contradiction_for(proposal, conflicts)
            contradiction_admission = self._store.add_contradiction(contradiction)
            if not contradiction_admission.accepted:
                return self._admission_receipt(
                    contradiction_admission,
                    proposal.tenant_id,
                    proposal.evidence_refs,
                    ("conflict_preservation_failed",),
                )
            return self._record_receipt(
                decision=AxiomDecision.QUARANTINE,
                reason="claim_conflict_preserved",
                object_id=proposal.claim_id,
                evidence_used=_evidence_ids(proposal.evidence_refs),
                rules_applied=("conflict_preservation", "truth_transition_conflicted"),
                conflicts=tuple(conflicts),
                reversible=True,
                tenant_id=proposal.tenant_id,
            )

        return self._record_receipt(
            decision=AxiomDecision.ACCEPT,
            reason="claim_supported",
            object_id=proposal.claim_id,
            evidence_used=_evidence_ids(proposal.evidence_refs),
            rules_applied=("truth_transition_supported", "evidence_attached"),
            reversible=True,
            tenant_id=proposal.tenant_id,
        )

    def validate_claim(
        self,
        claim_id: str,
        *,
        evidence_refs: tuple[EvidenceRef, ...] = (),
    ) -> AxiomWorldReceipt:
        """Advance a claim through legal truth transitions when evidence allows."""
        record = self._claims.get(claim_id)
        if record is None:
            return self._record_receipt(
                decision=AxiomDecision.REJECT,
                reason="claim_not_found",
                object_id=claim_id,
                evidence_used=_evidence_ids(evidence_refs),
                rules_applied=("truth_transition_requires_claim",),
                reversible=True,
                tenant_id="",
            )
        if record.truth_state == AxiomTruthState.CONFLICTED:
            return self._record_receipt(
                decision=AxiomDecision.QUARANTINE,
                reason="conflicted_claim_requires_reconciliation",
                object_id=claim_id,
                evidence_used=record.evidence_ids + _evidence_ids(evidence_refs),
                rules_applied=("conflict_preservation",),
                conflicts=(claim_id,),
                reversible=True,
                tenant_id=record.tenant_id,
            )

        if record.truth_state == AxiomTruthState.SIMULATED and not evidence_refs:
            return self._record_receipt(
                decision=AxiomDecision.REQUIRE_EVIDENCE,
                reason="simulation_requires_real_evidence_before_support",
                object_id=claim_id,
                evidence_used=(),
                rules_applied=("simulation_not_reality",),
                reversible=True,
                tenant_id=record.tenant_id,
            )

        if record.truth_state == AxiomTruthState.HYPOTHESIS and not evidence_refs:
            return self._record_receipt(
                decision=AxiomDecision.REQUIRE_EVIDENCE,
                reason="hypothesis_requires_evidence_before_support",
                object_id=claim_id,
                evidence_used=(),
                rules_applied=("no_validation_without_evidence",),
                reversible=True,
                tenant_id=record.tenant_id,
            )

        target_state = _next_validation_state(record.truth_state, bool(evidence_refs))
        if not _truth_transition_allowed(record.truth_state, target_state):
            return self._record_receipt(
                decision=AxiomDecision.REJECT,
                reason="illegal_truth_transition",
                object_id=claim_id,
                evidence_used=record.evidence_ids + _evidence_ids(evidence_refs),
                rules_applied=("truth_state_machine",),
                reversible=True,
                tenant_id=record.tenant_id,
            )

        admitted_to_world_state = record.admitted_to_world_state
        if not admitted_to_world_state and target_state == AxiomTruthState.SUPPORTED:
            proposal = AxiomClaimProposal(
                claim_id=record.claim_id,
                tenant_id=record.tenant_id,
                subject_ref=record.subject_ref,
                predicate=record.predicate,
                object_value=record.object_value,
                source="validation_evidence",
                observed_at=self._clock(),
                evidence_refs=evidence_refs,
                confidence=record.confidence,
                scope=record.scope,
                simulated=False,
            )
            claim_admission = self._admit_world_claim(proposal)
            if not claim_admission.accepted:
                return self._admission_receipt(
                    claim_admission,
                    record.tenant_id,
                    evidence_refs,
                    ("world_state_claim_admission",),
                )
            admitted_to_world_state = True

        self._claims[claim_id] = replace(
            record,
            truth_state=target_state,
            evidence_ids=record.evidence_ids + _evidence_ids(evidence_refs),
            admitted_to_world_state=admitted_to_world_state,
            simulated=False if target_state == AxiomTruthState.SUPPORTED else record.simulated,
        )
        return self._record_receipt(
            decision=AxiomDecision.ACCEPT,
            reason=f"truth_transition_{target_state.value.lower()}",
            object_id=claim_id,
            evidence_used=record.evidence_ids + _evidence_ids(evidence_refs),
            rules_applied=("truth_state_machine", "evidence_attached"),
            reversible=True,
            tenant_id=record.tenant_id,
        )

    def propose_action(self, proposal: AxiomActionProposal) -> AxiomWorldReceipt:
        """Register an action proposal after risk and target checks."""
        if proposal.target_ref not in self._symbols and proposal.target_ref not in self._claims:
            return self._record_receipt(
                decision=AxiomDecision.REJECT,
                reason="action_target_not_observed",
                object_id=proposal.action_id,
                evidence_used=(),
                rules_applied=("action_target_requires_symbol_or_claim",),
                reversible=True,
                tenant_id=proposal.tenant_id,
            )

        gated = proposal.risk_level in {
            AxiomRiskLevel.HIGH,
            AxiomRiskLevel.CRITICAL,
        } or proposal.reversibility in {
            AxiomReversibility.IRREVERSIBLE,
            AxiomReversibility.UNKNOWN,
        }
        status = AxiomActionStatus.PROPOSED if gated else AxiomActionStatus.CHECKED
        self._actions[proposal.action_id] = AxiomActionRecord(
            action_id=proposal.action_id,
            tenant_id=proposal.tenant_id,
            actor=proposal.actor,
            intent=proposal.intent,
            target_ref=proposal.target_ref,
            risk_level=proposal.risk_level,
            reversibility=proposal.reversibility,
            status=status,
            permissions_required=tuple(proposal.permissions_required),
            preconditions=tuple(proposal.preconditions),
            expected_delta=dict(proposal.expected_delta),
        )
        if gated:
            return self._record_receipt(
                decision=AxiomDecision.REQUIRE_APPROVAL,
                reason="action_requires_approval",
                object_id=proposal.action_id,
                evidence_used=(),
                rules_applied=("high_risk_action_gate", "reversibility_gate"),
                reversible=proposal.reversibility == AxiomReversibility.FULL,
                tenant_id=proposal.tenant_id,
            )
        return self._record_receipt(
            decision=AxiomDecision.ACCEPT,
            reason="action_checked",
            object_id=proposal.action_id,
            evidence_used=(),
            rules_applied=("action_lifecycle_gate",),
            reversible=True,
            tenant_id=proposal.tenant_id,
        )

    def simulate_action(self, action_id: str) -> AxiomWorldReceipt:
        """Mark an action as simulated without mutating admitted world state."""
        action = self._actions.get(action_id)
        if action is None:
            return self._record_receipt(
                decision=AxiomDecision.REJECT,
                reason="action_not_found",
                object_id=action_id,
                evidence_used=(),
                rules_applied=("simulation_requires_action",),
                reversible=True,
                tenant_id="",
            )
        self._actions[action_id] = replace(action, status=AxiomActionStatus.SIMULATED)
        return self._record_receipt(
            decision=AxiomDecision.SIMULATE_ONLY,
            reason="action_simulated_without_world_state_mutation",
            object_id=action_id,
            evidence_used=(),
            rules_applied=("simulation_not_reality", "no_mutation_without_execution"),
            reversible=True,
            tenant_id=action.tenant_id,
        )

    def project(
        self,
        *,
        observer: str,
        scope: AxiomProjectionScope,
        tenant_id: str,
    ) -> AxiomProjection:
        """Return an observer-safe projection of admitted symbols and claims."""
        visible_symbols: list[Mapping[str, Any]] = []
        visible_claims: list[Mapping[str, Any]] = []
        redactions: list[str] = []
        visible_symbol_ids: set[str] = set()

        for symbol in sorted(self._symbols.values(), key=lambda item: item.entity_id):
            if symbol.tenant_id != tenant_id:
                continue
            if _can_project(symbol.scope, scope, symbol.permissions):
                visible_symbol_ids.add(symbol.entity_id)
                visible_symbols.append(
                    {
                        "entity_id": symbol.entity_id,
                        "kind": symbol.kind,
                        "label": symbol.label,
                        "truth_state": symbol.truth_state.value,
                        "confidence": symbol.confidence.overall(),
                    }
                )
            else:
                redactions.append("symbol_scope_redacted")

        for claim in sorted(self._claims.values(), key=lambda item: item.claim_id):
            if claim.tenant_id != tenant_id:
                continue
            if claim.subject_ref not in visible_symbol_ids:
                redactions.append("claim_subject_scope_redacted")
                continue
            if _claim_visible(claim, scope):
                visible_claims.append(
                    {
                        "claim_id": claim.claim_id,
                        "subject_ref": claim.subject_ref,
                        "predicate": claim.predicate,
                        "object_value": claim.object_value,
                        "truth_state": claim.truth_state.value,
                        "confidence": claim.confidence.overall(),
                    }
                )
            else:
                redactions.append("claim_scope_redacted")

        materialized = self._store.materialize(tenant_id=tenant_id)
        projection = AxiomProjection(
            observer=observer,
            scope=scope,
            tenant_id=tenant_id,
            symbols=tuple(visible_symbols),
            claims=tuple(visible_claims),
            redactions=tuple(redactions),
            projected_at=self._clock(),
            world_state_hash=materialized.state_hash,
        )
        self._record_receipt(
            decision=AxiomDecision.ACCEPT,
            reason="projection_emitted",
            object_id=f"projection:{tenant_id}:{scope.value}",
            evidence_used=(),
            rules_applied=("projection_scope_filter", "inference_leakage_guard"),
            reversible=True,
            tenant_id=tenant_id,
        )
        return projection

    def materialize(self, *, tenant_id: str) -> WorldState:
        """Return the underlying world-state projection for verification."""
        return self._store.materialize(tenant_id=tenant_id)

    def receipts(self) -> tuple[AxiomWorldReceipt, ...]:
        """Return append-only kernel receipts."""
        return tuple(self._receipts)

    def claim_record(self, claim_id: str) -> AxiomClaimRecord | None:
        """Return the kernel-side claim record."""
        return self._claims.get(claim_id)

    def action_record(self, action_id: str) -> AxiomActionRecord | None:
        """Return the kernel-side action record."""
        return self._actions.get(action_id)

    def _admit_world_claim(self, proposal: AxiomClaimProposal) -> WorldStateAdmission:
        validity = proposal.validity or ValidityWindow(valid_from=proposal.observed_at)
        return self._store.add_claim(
            WorldClaim(
                claim_id=proposal.claim_id,
                tenant_id=proposal.tenant_id,
                subject_ref=proposal.subject_ref,
                predicate=proposal.predicate,
                object_value=proposal.object_value,
                evidence_refs=proposal.evidence_refs,
                source=proposal.source,
                observed_at=proposal.observed_at,
                validity=validity,
                confidence=proposal.confidence.overall(),
                trust_class="source_claim",
                allowed_for_planning=proposal.allowed_for_planning,
                allowed_for_execution=proposal.allowed_for_execution,
            )
        )

    def _claim_conflicts(self, proposal: AxiomClaimProposal) -> list[str]:
        conflicts: list[str] = []
        for existing in self._claims.values():
            if existing.tenant_id != proposal.tenant_id:
                continue
            if existing.truth_state in _INACTIVE_TRUTH_STATES:
                continue
            if existing.subject_ref != proposal.subject_ref:
                continue
            if existing.predicate != proposal.predicate:
                continue
            if existing.object_value != proposal.object_value:
                conflicts.append(existing.claim_id)
        return conflicts

    def _contradiction_for(
        self,
        proposal: AxiomClaimProposal,
        conflict_claim_ids: list[str],
    ) -> Contradiction:
        refs = tuple(conflict_claim_ids + [proposal.claim_id])
        return Contradiction(
            contradiction_id=f"contradiction:{proposal.claim_id}",
            tenant_id=proposal.tenant_id,
            refs=refs,
            reason=f"claim_conflict:{proposal.subject_ref}:{proposal.predicate}",
            evidence_refs=proposal.evidence_refs,
            source=proposal.source,
            observed_at=proposal.observed_at,
            severity="high",
            status="open",
        )

    def _admission_receipt(
        self,
        admission: WorldStateAdmission,
        tenant_id: str,
        evidence_refs: tuple[EvidenceRef, ...],
        rules_applied: tuple[str, ...],
    ) -> AxiomWorldReceipt:
        return self._record_receipt(
            decision=AxiomDecision.REJECT,
            reason=admission.reason,
            object_id=admission.object_id,
            evidence_used=_evidence_ids(evidence_refs),
            rules_applied=rules_applied,
            reversible=True,
            tenant_id=tenant_id,
        )

    def _record_receipt(
        self,
        *,
        decision: AxiomDecision,
        reason: str,
        object_id: str,
        evidence_used: tuple[str, ...],
        rules_applied: tuple[str, ...],
        tenant_id: str,
        conflicts: tuple[str, ...] = (),
        reversible: bool = True,
    ) -> AxiomWorldReceipt:
        self._receipt_counter += 1
        state_hash = ""
        if tenant_id:
            state_hash = self._store.materialize(tenant_id=tenant_id).state_hash
        receipt = AxiomWorldReceipt(
            receipt_id=f"axiom-receipt-{self._receipt_counter:06d}",
            decision=decision,
            reason=reason,
            object_id=object_id,
            evidence_used=evidence_used,
            rules_applied=rules_applied,
            conflicts=conflicts,
            reversible=reversible,
            world_state_hash=state_hash,
            created_at=self._clock(),
        )
        self._receipts.append(receipt)
        return receipt


def _claim_record(
    proposal: AxiomClaimProposal,
    truth_state: AxiomTruthState,
    *,
    admitted_to_world_state: bool,
) -> AxiomClaimRecord:
    return AxiomClaimRecord(
        claim_id=proposal.claim_id,
        tenant_id=proposal.tenant_id,
        subject_ref=proposal.subject_ref,
        predicate=proposal.predicate,
        object_value=proposal.object_value,
        evidence_ids=_evidence_ids(proposal.evidence_refs),
        truth_state=truth_state,
        confidence=proposal.confidence,
        scope=proposal.scope,
        admitted_to_world_state=admitted_to_world_state,
        simulated=proposal.simulated,
    )


def _truth_transition_allowed(
    source: AxiomTruthState,
    target: AxiomTruthState,
) -> bool:
    return target in _ALLOWED_TRUTH_TRANSITIONS.get(source, frozenset())


def _next_validation_state(
    current: AxiomTruthState,
    has_new_evidence: bool,
) -> AxiomTruthState:
    if current in {AxiomTruthState.HYPOTHESIS, AxiomTruthState.SIMULATED}:
        if has_new_evidence:
            return AxiomTruthState.SUPPORTED
        return current
    if current == AxiomTruthState.SUPPORTED:
        return AxiomTruthState.VALIDATED
    return current


def _can_project(
    record_scope: AxiomProjectionScope,
    requested_scope: AxiomProjectionScope,
    permissions: Mapping[str, bool],
) -> bool:
    if requested_scope == AxiomProjectionScope.PRIVATE:
        return True
    if requested_scope == AxiomProjectionScope.INTERNAL:
        return record_scope in {AxiomProjectionScope.PUBLIC, AxiomProjectionScope.INTERNAL}
    if requested_scope == AxiomProjectionScope.SIMULATION:
        return record_scope == AxiomProjectionScope.SIMULATION
    if requested_scope == AxiomProjectionScope.PUBLIC:
        return record_scope == AxiomProjectionScope.PUBLIC and permissions.get("public", False)
    return False


def _claim_visible(claim: AxiomClaimRecord, requested_scope: AxiomProjectionScope) -> bool:
    if requested_scope == AxiomProjectionScope.PRIVATE:
        return True
    if requested_scope == AxiomProjectionScope.INTERNAL:
        return claim.scope in {AxiomProjectionScope.PUBLIC, AxiomProjectionScope.INTERNAL}
    if requested_scope == AxiomProjectionScope.SIMULATION:
        return claim.truth_state == AxiomTruthState.SIMULATED
    if requested_scope == AxiomProjectionScope.PUBLIC:
        return claim.scope == AxiomProjectionScope.PUBLIC
    return False


def _fingerprint_key(fingerprint: Mapping[str, Any]) -> str:
    items = tuple(sorted((str(key), str(value)) for key, value in fingerprint.items()))
    return repr(items)


def _evidence_ids(evidence_refs: tuple[EvidenceRef, ...]) -> tuple[str, ...]:
    return tuple(evidence.evidence_id for evidence in evidence_refs)


def _clip_unit(value: float) -> float:
    return max(0.0, min(1.0, value))
