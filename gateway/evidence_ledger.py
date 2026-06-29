"""Gateway causal evidence continuity ledger.

Purpose: govern how observed artifacts become evidence, how evidence supports
    claims, how claim judgments are computed, and how proof-safe views are
    exposed without leaking raw artifacts.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: standard-library dataclasses, enum, hashing, datetime, and
    threading.
Invariants:
  - Evidence is not truth, and a claim is not evidence.
  - Inadmissible evidence is recorded but cannot support judgment.
  - Source authority is domain-scoped and bound into each judgment receipt.
  - Conflicts and missing expected evidence block premature certainty.
  - Every accepted or rejected state transition is append-only and hash-chained.
"""

from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Callable, Iterable


LEDGER_SCHEMA_VERSION = 2
LEDGER_RULE_VERSION = "causal-evidence-continuity-ledger-v2"
ONTOLOGY_VERSION = "evidence-ontology-v1"
SOURCE_REGISTRY_VERSION = "source-authority-registry-v1"


class EvidenceLedgerError(ValueError):
    """Raised when a ledger operation violates an explicit contract."""


class EvidenceKind(StrEnum):
    """Evidence kinds admitted by the universal evidence ledger kernel."""

    DOCUMENT = "document"
    EMAIL = "email"
    TRANSACTION = "transaction"
    API_RESPONSE = "api_response"
    LOG = "log"
    SENSOR_READING = "sensor_reading"
    HUMAN_STATEMENT = "human_statement"
    RAW_EVIDENCE = "raw_evidence"
    EXTRACTED_EVIDENCE = "extracted_evidence"
    INTERPRETED_EVIDENCE = "interpreted_evidence"
    DERIVED_EVIDENCE = "derived_evidence"
    JUDGMENT_EVIDENCE = "judgment_evidence"
    NEGATIVE_EVIDENCE = "negative_evidence"


class ClaimStatus(StrEnum):
    """Governed claim judgment states."""

    UNKNOWN = "unknown"
    NOT_READY_TO_JUDGE = "not_ready_to_judge"
    UNSUPPORTED = "unsupported"
    WEAKLY_SUPPORTED = "weakly_supported"
    PROVISIONALLY_SUPPORTED = "provisionally_supported"
    STRONGLY_SUPPORTED = "strongly_supported"
    CONFLICTED = "conflicted"
    REFUTED = "refuted"
    EXPIRED = "expired"
    REVOKED = "revoked"
    SUPERSEDED = "superseded"


class AdmissibilityState(StrEnum):
    """Evidence admissibility for claim judgment."""

    ADMITTED = "admitted"
    LIMITED_FOR_JUDGMENT = "limited_for_judgment"
    INADMISSIBLE_FOR_JUDGMENT = "inadmissible_for_judgment"


class LifecycleState(StrEnum):
    """Evidence and claim lifecycle states."""

    CREATED = "created"
    ADMITTED = "admitted"
    LINKED = "linked"
    ACTIVE = "active"
    CHALLENGED = "challenged"
    CORRECTED = "corrected"
    SUPERSEDED = "superseded"
    EXPIRED = "expired"
    REVOKED = "revoked"
    ARCHIVED = "archived"


class RelationType(StrEnum):
    """Causal relation types between evidence and claims."""

    SUPPORTS = "supports"
    REFUTES = "refutes"
    ABSENCE = "absence"
    CONTEXT = "context"
    DERIVED_FROM = "derived_from"
    DUPLICATES = "duplicates"
    CONTRADICTS = "contradicts"
    UPDATES = "updates"
    REVOKES = "revokes"


class ConflictType(StrEnum):
    """Conflict classes preserved as first-class symbolic objects."""

    DIRECT_CONTRADICTION = "direct_contradiction"
    TIMESTAMP_MISMATCH = "timestamp_mismatch"
    IDENTITY_MISMATCH = "identity_mismatch"
    SCOPE_MISMATCH = "scope_mismatch"
    DUPLICATE_SOURCE_ECHO = "duplicate_source_echo"
    DERIVED_FROM_SAME_ORIGIN = "derived_from_same_origin"
    STALE_EVIDENCE = "stale_evidence"
    AUTHORITY_CONFLICT = "authority_conflict"
    REDACTION_BLOCKS_VERIFICATION = "redaction_blocks_verification"


class ExposureViewType(StrEnum):
    """Permission-safe claim exposure views."""

    FULL_AUDIT = "full_audit_view"
    REDACTED_EVIDENCE = "redacted_evidence_view"
    CLAIM_SUMMARY = "claim_summary_view"
    PROOF_ONLY = "proof_only_view"
    EXTERNAL_COMPLIANCE = "external_compliance_view"


@dataclass(frozen=True, slots=True)
class SourceAuthority:
    """Domain-scoped authority record for one evidence source."""

    source_id: str
    source_type: str
    authority_domains: tuple[str, ...]
    forbidden_domains: tuple[str, ...] = ()
    reliability_score: float = 0.5
    verification_method: str = ""
    last_verified_at: str = ""
    authority_scope: str = ""

    def __post_init__(self) -> None:
        _require_text(self.source_id, "source_id")
        _require_text(self.source_type, "source_type")
        if not 0.0 <= self.reliability_score <= 1.0:
            raise EvidenceLedgerError("source_reliability_between_zero_and_one")
        domains = _normalize_text_tuple(self.authority_domains, "authority_domains")
        forbidden = _normalize_text_tuple(self.forbidden_domains, "forbidden_domains", allow_empty=True)
        object.__setattr__(self, "authority_domains", domains)
        object.__setattr__(self, "forbidden_domains", forbidden)

    def authorizes(self, authority_domain: str) -> bool:
        """Return whether this source may support the requested authority domain."""

        domain = authority_domain.strip()
        if not domain or domain in self.forbidden_domains:
            return False
        return "*" in self.authority_domains or domain in self.authority_domains


@dataclass(frozen=True, slots=True)
class ExpectedEvidenceProfile:
    """Claim readiness gate for required, optional, and blocking evidence."""

    required_evidence_kinds: tuple[str, ...] = ()
    optional_evidence_kinds: tuple[str, ...] = ()
    blocking_absences: tuple[str, ...] = ()
    minimum_independent_sources: int = 1
    freshness_window_days: int = 30
    high_authority_refutation_threshold: float = 0.8

    def __post_init__(self) -> None:
        if self.minimum_independent_sources < 1:
            raise EvidenceLedgerError("minimum_independent_sources_positive")
        if self.freshness_window_days < 0:
            raise EvidenceLedgerError("freshness_window_days_nonnegative")
        if not 0.0 <= self.high_authority_refutation_threshold <= 1.0:
            raise EvidenceLedgerError("refutation_threshold_between_zero_and_one")
        object.__setattr__(
            self,
            "required_evidence_kinds",
            _normalize_kind_tuple(self.required_evidence_kinds, "required_evidence_kinds", allow_empty=True),
        )
        object.__setattr__(
            self,
            "optional_evidence_kinds",
            _normalize_kind_tuple(self.optional_evidence_kinds, "optional_evidence_kinds", allow_empty=True),
        )
        object.__setattr__(
            self,
            "blocking_absences",
            _normalize_text_tuple(self.blocking_absences, "blocking_absences", allow_empty=True),
        )


@dataclass(frozen=True, slots=True)
class EvidenceAtom:
    """Smallest governed unit of claim-supporting evidence."""

    evidence_id: str
    evidence_kind: EvidenceKind
    source_id: str
    observer_id: str
    capture_method: str
    custody_chain: tuple[str, ...]
    observed_at: str
    recorded_at: str
    raw_reference: str
    raw_hash: str
    canonical_reference: str
    canonical_hash: str
    ontology_type: str
    authority_domain: str
    sensitivity_level: str
    admissibility_state: AdmissibilityState
    risk_profile: dict[str, Any] = field(default_factory=dict)
    authority_scope: tuple[str, ...] = ()
    derivation_parents: tuple[str, ...] = ()
    linked_claims: tuple[str, ...] = ()
    lifecycle_state: LifecycleState = LifecycleState.CREATED
    evidence_family_id: str = ""
    rule_version: str = LEDGER_RULE_VERSION

    def __post_init__(self) -> None:
        _require_text(self.evidence_id, "evidence_id")
        object.__setattr__(self, "custody_chain", _normalize_text_tuple(self.custody_chain, "custody_chain", allow_empty=True))
        object.__setattr__(self, "risk_profile", dict(self.risk_profile))
        object.__setattr__(self, "authority_scope", _normalize_text_tuple(self.authority_scope, "authority_scope", allow_empty=True))
        object.__setattr__(
            self,
            "derivation_parents",
            _normalize_text_tuple(self.derivation_parents, "derivation_parents", allow_empty=True),
        )
        object.__setattr__(
            self,
            "linked_claims",
            _normalize_text_tuple(self.linked_claims, "linked_claims", allow_empty=True),
        )


@dataclass(frozen=True, slots=True)
class ClaimNode:
    """Proposition whose status is governed separately from evidence."""

    claim_id: str
    claim_type: str
    proposition: str
    subject: str
    scope: dict[str, Any]
    temporal_scope: dict[str, Any]
    expected_evidence_profile: ExpectedEvidenceProfile
    support_edges: tuple[str, ...] = ()
    refute_edges: tuple[str, ...] = ()
    absence_edges: tuple[str, ...] = ()
    conflict_nodes: tuple[str, ...] = ()
    current_judgment: ClaimStatus = ClaimStatus.UNKNOWN
    judgment_history: tuple[str, ...] = ()
    challenge_state: str = "unchallenged"
    expiration_policy: dict[str, Any] = field(default_factory=dict)
    lifecycle_state: LifecycleState = LifecycleState.CREATED
    created_at: str = ""
    claim_hash: str = ""

    def __post_init__(self) -> None:
        for field_name in ("claim_id", "claim_type", "proposition", "subject"):
            _require_text(getattr(self, field_name), field_name)
        object.__setattr__(self, "scope", dict(self.scope))
        object.__setattr__(self, "temporal_scope", dict(self.temporal_scope))
        object.__setattr__(
            self,
            "support_edges",
            _normalize_text_tuple(self.support_edges, "support_edges", allow_empty=True),
        )
        object.__setattr__(
            self,
            "refute_edges",
            _normalize_text_tuple(self.refute_edges, "refute_edges", allow_empty=True),
        )
        object.__setattr__(
            self,
            "absence_edges",
            _normalize_text_tuple(self.absence_edges, "absence_edges", allow_empty=True),
        )
        object.__setattr__(
            self,
            "conflict_nodes",
            _normalize_text_tuple(self.conflict_nodes, "conflict_nodes", allow_empty=True),
        )
        object.__setattr__(
            self,
            "judgment_history",
            _normalize_text_tuple(self.judgment_history, "judgment_history", allow_empty=True),
        )
        object.__setattr__(self, "expiration_policy", dict(self.expiration_policy))


@dataclass(frozen=True, slots=True)
class CausalEdge:
    """Typed causal relation from an evidence atom to a claim node."""

    edge_id: str
    from_evidence_id: str
    to_claim_id: str
    relation_type: RelationType
    rule_id: str
    weight: float
    confidence: float
    explanation: str
    created_at: str
    created_by: str
    edge_hash: str = ""

    def __post_init__(self) -> None:
        for field_name in ("edge_id", "from_evidence_id", "to_claim_id", "rule_id", "explanation", "created_at", "created_by"):
            _require_text(getattr(self, field_name), field_name)
        if not 0.0 <= self.weight <= 1.0:
            raise EvidenceLedgerError("edge_weight_between_zero_and_one")
        if not 0.0 <= self.confidence <= 1.0:
            raise EvidenceLedgerError("edge_confidence_between_zero_and_one")


@dataclass(frozen=True, slots=True)
class ConflictNode:
    """First-class record for unresolved evidence conflict."""

    conflict_id: str
    claim_id: str
    evidence_ids: tuple[str, ...]
    conflict_type: ConflictType
    severity: str
    possible_resolution: str
    status: str
    created_at: str
    conflict_hash: str = ""

    def __post_init__(self) -> None:
        _require_text(self.conflict_id, "conflict_id")
        _require_text(self.claim_id, "claim_id")
        object.__setattr__(self, "evidence_ids", _normalize_text_tuple(self.evidence_ids, "evidence_ids"))
        for field_name in ("severity", "possible_resolution", "status", "created_at"):
            _require_text(getattr(self, field_name), field_name)


@dataclass(frozen=True, slots=True)
class JudgmentReceipt:
    """Hash-bound receipt explaining one claim judgment transition."""

    receipt_id: str
    claim_id: str
    previous_judgment: ClaimStatus
    new_judgment: ClaimStatus
    evidence_included: tuple[str, ...]
    evidence_excluded: tuple[str, ...]
    missing_evidence: tuple[str, ...]
    conflicts: tuple[str, ...]
    negative_evidence: tuple[str, ...]
    independence_assessment: dict[str, Any]
    source_authority_assessment: dict[str, Any]
    rules_applied: tuple[str, ...]
    ontology_version: str
    source_registry_version: str
    confidence_limits: tuple[str, ...]
    exposure_limits: tuple[str, ...]
    timestamp: str
    verifier: str
    receipt_hash: str = ""

    def __post_init__(self) -> None:
        for field_name in ("receipt_id", "claim_id", "ontology_version", "source_registry_version", "timestamp", "verifier"):
            _require_text(getattr(self, field_name), field_name)
        object.__setattr__(
            self,
            "evidence_included",
            _normalize_text_tuple(self.evidence_included, "evidence_included", allow_empty=True),
        )
        object.__setattr__(
            self,
            "evidence_excluded",
            _normalize_text_tuple(self.evidence_excluded, "evidence_excluded", allow_empty=True),
        )
        object.__setattr__(
            self,
            "missing_evidence",
            _normalize_text_tuple(self.missing_evidence, "missing_evidence", allow_empty=True),
        )
        object.__setattr__(self, "conflicts", _normalize_text_tuple(self.conflicts, "conflicts", allow_empty=True))
        object.__setattr__(
            self,
            "negative_evidence",
            _normalize_text_tuple(self.negative_evidence, "negative_evidence", allow_empty=True),
        )
        object.__setattr__(self, "independence_assessment", dict(self.independence_assessment))
        object.__setattr__(self, "source_authority_assessment", dict(self.source_authority_assessment))
        object.__setattr__(self, "rules_applied", _normalize_text_tuple(self.rules_applied, "rules_applied"))
        object.__setattr__(
            self,
            "confidence_limits",
            _normalize_text_tuple(self.confidence_limits, "confidence_limits", allow_empty=True),
        )
        object.__setattr__(
            self,
            "exposure_limits",
            _normalize_text_tuple(self.exposure_limits, "exposure_limits", allow_empty=True),
        )

    def to_json_dict(self) -> dict[str, Any]:
        """Return a schema-oriented JSON object for the receipt."""

        return _json_ready(asdict(self))


@dataclass(frozen=True, slots=True)
class LedgerEvent:
    """Append-only event in the causal evidence ledger hash chain."""

    event_id: str
    event_type: str
    actor_id: str
    timestamp: str
    parent_hash: str
    payload_hash: str
    policy_result: dict[str, Any]
    receipt_id: str = ""
    signature: str = ""
    event_hash: str = ""

    def __post_init__(self) -> None:
        for field_name in ("event_id", "event_type", "actor_id", "timestamp", "payload_hash"):
            _require_text(getattr(self, field_name), field_name)
        object.__setattr__(self, "policy_result", dict(self.policy_result))


@dataclass(frozen=True, slots=True)
class EvidenceIngestionResult:
    """Result of evidence ingestion, including rejected evidence records."""

    accepted: bool
    reason: str
    evidence: EvidenceAtom
    event: LedgerEvent


@dataclass(frozen=True, slots=True)
class LinkResult:
    """Result of linking evidence to a claim."""

    accepted: bool
    reason: str
    edge: CausalEdge | None
    event: LedgerEvent


@dataclass(frozen=True, slots=True)
class LedgerChainVerification:
    """Hash-chain verification result."""

    verified: bool
    reason: str
    event_count: int
    head_hash: str


@dataclass(frozen=True, slots=True)
class ExposureView:
    """Permission-safe view over one claim judgment."""

    view_type: ExposureViewType
    claim_id: str
    actor_id: str
    purpose: str
    judgment: ClaimStatus
    receipt_id: str
    evidence_summaries: tuple[dict[str, Any], ...]
    exposure_limits: tuple[str, ...]
    generated_at: str
    exposure_hash: str

    def to_json_dict(self) -> dict[str, Any]:
        """Return a JSON-safe exposure view."""

        return _json_ready(asdict(self))


@dataclass(frozen=True, slots=True)
class ChallengeRecord:
    """Append-only challenge against an exposed judgment."""

    challenge_id: str
    claim_id: str
    challenger_id: str
    reason: str
    new_evidence_ids: tuple[str, ...]
    status: str
    created_at: str
    challenge_hash: str


@dataclass(frozen=True, slots=True)
class AuditReceipt:
    """Causal reconstruction receipt for one claim."""

    audit_receipt_id: str
    claim_id: str
    event_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    edge_ids: tuple[str, ...]
    judgment_receipt_ids: tuple[str, ...]
    conflict_ids: tuple[str, ...]
    challenge_ids: tuple[str, ...]
    chain_verified: bool
    head_hash: str
    generated_at: str
    audit_hash: str


class EvidenceLedgerKernel:
    """In-memory proof-bound claim governance engine.

    Input contract: callers pass explicit source, observer, claim, actor, and
    permission context into each effect-bearing operation. Output contract:
    each state transition returns a typed receipt or result object. Error
    contract: malformed caller inputs raise EvidenceLedgerError with causal
    context; rejected evidence or links append rejection events.
    """

    def __init__(
        self,
        *,
        ledger_id: str,
        clock: Callable[[], str] | None = None,
        rule_version: str = LEDGER_RULE_VERSION,
        ontology_version: str = ONTOLOGY_VERSION,
        source_registry_version: str = SOURCE_REGISTRY_VERSION,
    ) -> None:
        _require_text(ledger_id, "ledger_id")
        self.ledger_id = ledger_id
        self.rule_version = rule_version
        self.ontology_version = ontology_version
        self.source_registry_version = source_registry_version
        self._clock = clock or _utc_now
        self._sources: dict[str, SourceAuthority] = {}
        self._evidence: dict[str, EvidenceAtom] = {}
        self._claims: dict[str, ClaimNode] = {}
        self._edges: dict[str, CausalEdge] = {}
        self._conflicts: dict[str, ConflictNode] = {}
        self._judgment_receipts: dict[str, JudgmentReceipt] = {}
        self._events: list[LedgerEvent] = []
        self._challenges: dict[str, ChallengeRecord] = {}
        self._lock = threading.Lock()

    def register_source_authority(self, source: SourceAuthority, *, actor_id: str) -> LedgerEvent:
        """Register one domain-scoped source authority record."""

        _require_text(actor_id, "actor_id")
        with self._lock:
            if source.source_id in self._sources:
                raise EvidenceLedgerError(f"source_authority_already_exists:{source.source_id}")
            self._sources[source.source_id] = source
            return self._append_event_no_lock(
                event_type="source_authority_registered",
                actor_id=actor_id,
                payload={"source": asdict(source), "source_registry_version": self.source_registry_version},
                policy_result={"accepted": True, "reason": "source_authority_registered"},
            )

    def create_claim(
        self,
        *,
        claim_id: str,
        claim_type: str,
        proposition: str,
        subject: str,
        scope: dict[str, Any],
        temporal_scope: dict[str, Any],
        expected_evidence_profile: ExpectedEvidenceProfile | None = None,
        actor_id: str,
        expiration_policy: dict[str, Any] | None = None,
    ) -> ClaimNode:
        """Create a claim separately from any evidence that may later support it."""

        _require_text(actor_id, "actor_id")
        with self._lock:
            if claim_id in self._claims:
                raise EvidenceLedgerError(f"claim_already_exists:{claim_id}")
            claim = ClaimNode(
                claim_id=claim_id,
                claim_type=claim_type,
                proposition=proposition,
                subject=subject,
                scope=scope,
                temporal_scope=temporal_scope,
                expected_evidence_profile=expected_evidence_profile or ExpectedEvidenceProfile(),
                expiration_policy=expiration_policy or {},
                created_at=self._clock(),
            )
            stored = _stamp_claim(claim)
            self._claims[stored.claim_id] = stored
            self._append_event_no_lock(
                event_type="claim_created",
                actor_id=actor_id,
                payload={"claim": asdict(stored), "rule_version": self.rule_version},
                policy_result={"accepted": True, "reason": "claim_created"},
            )
            return stored

    def ingest_evidence(
        self,
        *,
        evidence_kind: EvidenceKind | str,
        source_id: str,
        observer_id: str,
        capture_method: str,
        observed_at: str,
        raw_payload: Any,
        canonical_payload: Any,
        ontology_type: str,
        authority_domain: str,
        actor_id: str,
        sensitivity_level: str = "internal",
        raw_reference: str = "",
        canonical_reference: str = "",
        custody_chain: tuple[str, ...] = (),
        derivation_parents: tuple[str, ...] = (),
        risk_profile: dict[str, Any] | None = None,
    ) -> EvidenceIngestionResult:
        """Capture, hash, validate, and append one evidence atom."""

        kind = _evidence_kind(evidence_kind)
        _require_text(actor_id, "actor_id")
        recorded_at = self._clock()
        raw_hash = f"sha256:{_stable_hash(raw_payload)}"
        canonical_hash = f"sha256:{_stable_hash(canonical_payload)}"
        risk = dict(risk_profile or {})
        family_hash = _stable_hash({"raw_hash": raw_hash})
        with self._lock:
            admissibility, reason, authority_scope = self._admissibility_no_lock(
                source_id=source_id,
                observer_id=observer_id,
                capture_method=capture_method,
                observed_at=observed_at,
                authority_domain=authority_domain,
                raw_hash=raw_hash,
                canonical_hash=canonical_hash,
                risk_profile=risk,
            )
            evidence_id = self._next_id_no_lock(
                "evidence",
                {
                    "source_id": source_id,
                    "observer_id": observer_id,
                    "raw_hash": raw_hash,
                    "canonical_hash": canonical_hash,
                    "observed_at": observed_at,
                    "recorded_at": recorded_at,
                },
            )
            lifecycle = (
                LifecycleState.ADMITTED
                if admissibility != AdmissibilityState.INADMISSIBLE_FOR_JUDGMENT
                else LifecycleState.CREATED
            )
            evidence = EvidenceAtom(
                evidence_id=evidence_id,
                evidence_kind=kind,
                source_id=source_id,
                observer_id=observer_id,
                capture_method=capture_method,
                custody_chain=custody_chain,
                observed_at=observed_at,
                recorded_at=recorded_at,
                raw_reference=raw_reference,
                raw_hash=raw_hash,
                canonical_reference=canonical_reference,
                canonical_hash=canonical_hash,
                ontology_type=ontology_type,
                authority_domain=authority_domain,
                sensitivity_level=sensitivity_level,
                admissibility_state=admissibility,
                risk_profile=risk,
                authority_scope=authority_scope,
                derivation_parents=derivation_parents,
                lifecycle_state=lifecycle,
                evidence_family_id=f"evidence-family-{family_hash[:16]}",
                rule_version=self.rule_version,
            )
            self._evidence[evidence.evidence_id] = evidence
            event = self._append_event_no_lock(
                event_type=(
                    "evidence_ingested"
                    if admissibility != AdmissibilityState.INADMISSIBLE_FOR_JUDGMENT
                    else "evidence_rejected"
                ),
                actor_id=actor_id,
                payload={
                    "evidence_id": evidence.evidence_id,
                    "evidence_kind": evidence.evidence_kind,
                    "source_id": source_id,
                    "observer_id": observer_id,
                    "raw_hash": raw_hash,
                    "canonical_hash": canonical_hash,
                    "admissibility_state": evidence.admissibility_state,
                    "authority_domain": authority_domain,
                    "reason": reason,
                },
                policy_result={
                    "accepted": admissibility != AdmissibilityState.INADMISSIBLE_FOR_JUDGMENT,
                    "reason": reason,
                    "admissibility_state": admissibility,
                },
            )
            return EvidenceIngestionResult(
                accepted=admissibility != AdmissibilityState.INADMISSIBLE_FOR_JUDGMENT,
                reason=reason,
                evidence=evidence,
                event=event,
            )

    def link_evidence(
        self,
        *,
        evidence_id: str,
        claim_id: str,
        relation_type: RelationType | str,
        rule_id: str,
        weight: float,
        confidence: float,
        explanation: str,
        actor_id: str,
    ) -> LinkResult:
        """Link admitted evidence to a claim with an explicit causal relation."""

        relation = _relation_type(relation_type)
        _require_text(actor_id, "actor_id")
        with self._lock:
            evidence = self._evidence.get(evidence_id)
            claim = self._claims.get(claim_id)
            rejection_reason = ""
            if evidence is None:
                rejection_reason = f"unknown_evidence:{evidence_id}"
            elif claim is None:
                rejection_reason = f"unknown_claim:{claim_id}"
            elif (
                relation in {RelationType.SUPPORTS, RelationType.REFUTES, RelationType.ABSENCE}
                and evidence.admissibility_state == AdmissibilityState.INADMISSIBLE_FOR_JUDGMENT
            ):
                rejection_reason = "inadmissible_evidence_cannot_support_judgment"
            if rejection_reason:
                event = self._append_event_no_lock(
                    event_type="claim_link_rejected",
                    actor_id=actor_id,
                    payload={
                        "evidence_id": evidence_id,
                        "claim_id": claim_id,
                        "relation_type": relation,
                        "reason": rejection_reason,
                    },
                    policy_result={"accepted": False, "reason": rejection_reason},
                )
                return LinkResult(False, rejection_reason, None, event)

            assert evidence is not None
            assert claim is not None
            created_at = self._clock()
            edge = CausalEdge(
                edge_id=self._next_id_no_lock(
                    "edge",
                    {
                        "evidence_id": evidence_id,
                        "claim_id": claim_id,
                        "relation_type": relation,
                        "rule_id": rule_id,
                        "created_at": created_at,
                    },
                ),
                from_evidence_id=evidence_id,
                to_claim_id=claim_id,
                relation_type=relation,
                rule_id=rule_id,
                weight=weight,
                confidence=confidence,
                explanation=explanation,
                created_at=created_at,
                created_by=actor_id,
            )
            stored_edge = _stamp_edge(edge)
            self._edges[stored_edge.edge_id] = stored_edge
            self._evidence[evidence_id] = replace(
                evidence,
                linked_claims=_append_unique(evidence.linked_claims, claim_id),
                lifecycle_state=LifecycleState.LINKED,
            )
            self._claims[claim_id] = _stamp_claim(_claim_with_edge(claim, stored_edge))
            event = self._append_event_no_lock(
                event_type="claim_linked",
                actor_id=actor_id,
                payload={"edge": asdict(stored_edge), "rule_version": self.rule_version},
                policy_result={"accepted": True, "reason": "claim_linked"},
            )
            return LinkResult(True, "claim_linked", stored_edge, event)

    def detect_conflicts(self, *, claim_id: str, actor_id: str) -> tuple[ConflictNode, ...]:
        """Detect and preserve unresolved support/refutation conflicts."""

        _require_text(actor_id, "actor_id")
        with self._lock:
            claim = self._require_claim_no_lock(claim_id)
            conflicts = self._ensure_conflicts_no_lock(claim, actor_id=actor_id)
            return conflicts

    def judge_claim(self, *, claim_id: str, verifier: str) -> JudgmentReceipt:
        """Compute governed claim state and append a judgment receipt."""

        _require_text(verifier, "verifier")
        with self._lock:
            claim = self._require_claim_no_lock(claim_id)
            conflicts = self._ensure_conflicts_no_lock(claim, actor_id=verifier)
            support_edges = [self._edges[edge_id] for edge_id in claim.support_edges if edge_id in self._edges]
            refute_edges = [self._edges[edge_id] for edge_id in claim.refute_edges if edge_id in self._edges]
            absence_edges = [self._edges[edge_id] for edge_id in claim.absence_edges if edge_id in self._edges]
            included, excluded = self._included_and_excluded_evidence_no_lock(
                tuple(support_edges + refute_edges + absence_edges)
            )
            missing = self._missing_evidence_no_lock(claim, support_edges)
            negative_evidence = tuple(edge.from_evidence_id for edge in absence_edges)
            independence = self._independence_assessment_no_lock(support_edges)
            source_assessment = self._source_authority_assessment_no_lock(included)
            confidence_limits = list(self._confidence_limits_no_lock(
                claim=claim,
                support_edges=support_edges,
                included_evidence=included,
                conflicts=conflicts,
            ))
            new_status = self._judgment_status_no_lock(
                claim=claim,
                support_edges=support_edges,
                refute_edges=refute_edges,
                missing=missing,
                conflicts=conflicts,
                independence=independence,
                confidence_limits=tuple(confidence_limits),
            )
            timestamp = self._clock()
            draft = JudgmentReceipt(
                receipt_id="pending",
                claim_id=claim.claim_id,
                previous_judgment=claim.current_judgment,
                new_judgment=new_status,
                evidence_included=tuple(sorted(evidence.evidence_id for evidence in included)),
                evidence_excluded=tuple(sorted(evidence.evidence_id for evidence in excluded)),
                missing_evidence=missing,
                conflicts=tuple(sorted(conflict.conflict_id for conflict in conflicts)),
                negative_evidence=negative_evidence,
                independence_assessment=independence,
                source_authority_assessment=source_assessment,
                rules_applied=(
                    self.rule_version,
                    "claim_readiness_gate",
                    "source_authority_scope_check",
                    "independence_family_check",
                    "conflict_override_check",
                    "missing_expected_evidence_check",
                ),
                ontology_version=self.ontology_version,
                source_registry_version=self.source_registry_version,
                confidence_limits=tuple(confidence_limits),
                exposure_limits=("raw_payload_not_exposed", "permissioned_view_required"),
                timestamp=timestamp,
                verifier=verifier,
            )
            receipt = _stamp_receipt(draft)
            self._judgment_receipts[receipt.receipt_id] = receipt
            updated_claim = replace(
                claim,
                current_judgment=new_status,
                judgment_history=_append_unique(claim.judgment_history, receipt.receipt_id),
                lifecycle_state=LifecycleState.ACTIVE,
            )
            self._claims[claim_id] = _stamp_claim(updated_claim)
            self._append_event_no_lock(
                event_type="judgment_updated",
                actor_id=verifier,
                payload={"receipt": receipt.to_json_dict()},
                policy_result={"accepted": True, "reason": "judgment_updated", "new_judgment": new_status},
                receipt_id=receipt.receipt_id,
            )
            return receipt

    def expose_claim(
        self,
        *,
        claim_id: str,
        actor_id: str,
        purpose: str,
        view_type: ExposureViewType | str = ExposureViewType.PROOF_ONLY,
    ) -> ExposureView:
        """Return a permission-safe claim view without exposing raw artifacts."""

        _require_text(actor_id, "actor_id")
        _require_text(purpose, "purpose")
        view = _exposure_view_type(view_type)
        with self._lock:
            claim = self._require_claim_no_lock(claim_id)
            if not claim.judgment_history:
                raise EvidenceLedgerError(f"claim_has_no_judgment_receipt:{claim_id}")
            receipt = self._judgment_receipts[claim.judgment_history[-1]]
            evidence_summaries = tuple(
                self._evidence_summary_no_lock(self._evidence[evidence_id], view)
                for evidence_id in receipt.evidence_included
                if evidence_id in self._evidence
            )
            generated_at = self._clock()
            exposure_hash = _stable_hash(
                {
                    "claim_id": claim_id,
                    "view_type": view,
                    "judgment": claim.current_judgment,
                    "receipt_id": receipt.receipt_id,
                    "evidence_summaries": evidence_summaries,
                    "generated_at": generated_at,
                }
            )
            exposure = ExposureView(
                view_type=view,
                claim_id=claim_id,
                actor_id=actor_id,
                purpose=purpose,
                judgment=claim.current_judgment,
                receipt_id=receipt.receipt_id,
                evidence_summaries=evidence_summaries,
                exposure_limits=receipt.exposure_limits,
                generated_at=generated_at,
                exposure_hash=exposure_hash,
            )
            self._append_event_no_lock(
                event_type="exposure_view_generated",
                actor_id=actor_id,
                payload={
                    "claim_id": claim_id,
                    "view_type": view,
                    "purpose": purpose,
                    "exposure_hash": exposure_hash,
                },
                policy_result={"accepted": True, "reason": "permission_safe_view_generated"},
                receipt_id=receipt.receipt_id,
            )
            return exposure

    def challenge_judgment(
        self,
        *,
        claim_id: str,
        challenger_id: str,
        reason: str,
        new_evidence_ids: tuple[str, ...] = (),
    ) -> ChallengeRecord:
        """Append a challenge event and mark the claim for rejudgment."""

        _require_text(challenger_id, "challenger_id")
        _require_text(reason, "challenge_reason")
        with self._lock:
            claim = self._require_claim_no_lock(claim_id)
            for evidence_id in new_evidence_ids:
                if evidence_id not in self._evidence:
                    raise EvidenceLedgerError(f"unknown_challenge_evidence:{evidence_id}")
            created_at = self._clock()
            challenge_id = self._next_id_no_lock(
                "challenge",
                {
                    "claim_id": claim_id,
                    "challenger_id": challenger_id,
                    "reason": reason,
                    "new_evidence_ids": new_evidence_ids,
                    "created_at": created_at,
                },
            )
            challenge_hash = _stable_hash(
                {
                    "challenge_id": challenge_id,
                    "claim_id": claim_id,
                    "challenger_id": challenger_id,
                    "reason": reason,
                    "new_evidence_ids": new_evidence_ids,
                    "status": "open",
                    "created_at": created_at,
                }
            )
            challenge = ChallengeRecord(
                challenge_id=challenge_id,
                claim_id=claim_id,
                challenger_id=challenger_id,
                reason=reason,
                new_evidence_ids=_normalize_text_tuple(new_evidence_ids, "new_evidence_ids", allow_empty=True),
                status="open",
                created_at=created_at,
                challenge_hash=challenge_hash,
            )
            self._challenges[challenge.challenge_id] = challenge
            self._claims[claim_id] = _stamp_claim(
                replace(claim, challenge_state="challenged", lifecycle_state=LifecycleState.CHALLENGED)
            )
            self._append_event_no_lock(
                event_type="challenge_received",
                actor_id=challenger_id,
                payload=asdict(challenge),
                policy_result={"accepted": True, "reason": "challenge_recorded"},
            )
            return challenge

    def audit_claim(self, *, claim_id: str, actor_id: str) -> AuditReceipt:
        """Reconstruct the claim path across evidence, edges, receipts, and events."""

        _require_text(actor_id, "actor_id")
        with self._lock:
            claim = self._require_claim_no_lock(claim_id)
            audit_event = self._append_event_no_lock(
                event_type="audit_requested",
                actor_id=actor_id,
                payload={"claim_id": claim_id},
                policy_result={"accepted": True, "reason": "audit_requested"},
            )
            edge_ids = tuple(claim.support_edges + claim.refute_edges + claim.absence_edges)
            evidence_ids = tuple(
                dict.fromkeys(
                    self._edges[edge_id].from_evidence_id for edge_id in edge_ids if edge_id in self._edges
                )
            )
            chain = self.verify_event_chain()
            event_ids = tuple(event.event_id for event in self._events)
            challenge_ids = tuple(
                challenge.challenge_id for challenge in self._challenges.values() if challenge.claim_id == claim_id
            )
            payload = {
                "claim_id": claim_id,
                "event_ids": event_ids,
                "evidence_ids": evidence_ids,
                "edge_ids": edge_ids,
                "judgment_receipt_ids": claim.judgment_history,
                "conflict_ids": claim.conflict_nodes,
                "challenge_ids": challenge_ids,
                "chain_verified": chain.verified,
                "head_hash": chain.head_hash,
                "audit_event_id": audit_event.event_id,
            }
            audit_hash = _stable_hash(payload)
            return AuditReceipt(
                audit_receipt_id=f"audit-receipt-{audit_hash[:16]}",
                claim_id=claim_id,
                event_ids=event_ids,
                evidence_ids=evidence_ids,
                edge_ids=edge_ids,
                judgment_receipt_ids=claim.judgment_history,
                conflict_ids=claim.conflict_nodes,
                challenge_ids=challenge_ids,
                chain_verified=chain.verified,
                head_hash=chain.head_hash,
                generated_at=self._clock(),
                audit_hash=audit_hash,
            )

    def verify_event_chain(self) -> LedgerChainVerification:
        """Replay the append-only event chain and verify parent hashes."""

        expected_parent = ""
        for event in self._events:
            if event.parent_hash != expected_parent:
                return LedgerChainVerification(False, "parent_hash_mismatch", len(self._events), self.current_head_hash())
            if _event_hash(event) != event.event_hash:
                return LedgerChainVerification(False, "event_hash_mismatch", len(self._events), self.current_head_hash())
            expected_parent = event.event_hash
        return LedgerChainVerification(True, "verified", len(self._events), self.current_head_hash())

    def current_head_hash(self) -> str:
        """Return the current event-chain head hash."""

        if not self._events:
            return ""
        return self._events[-1].event_hash

    def history(self) -> tuple[LedgerEvent, ...]:
        """Return append-only ledger events."""

        return tuple(self._events)

    def get_claim(self, claim_id: str) -> ClaimNode | None:
        """Return one claim by id."""

        return self._claims.get(claim_id)

    def get_evidence(self, evidence_id: str) -> EvidenceAtom | None:
        """Return one evidence atom by id."""

        return self._evidence.get(evidence_id)

    def get_receipt(self, receipt_id: str) -> JudgmentReceipt | None:
        """Return one judgment receipt by id."""

        return self._judgment_receipts.get(receipt_id)

    def _admissibility_no_lock(
        self,
        *,
        source_id: str,
        observer_id: str,
        capture_method: str,
        observed_at: str,
        authority_domain: str,
        raw_hash: str,
        canonical_hash: str,
        risk_profile: dict[str, Any],
    ) -> tuple[AdmissibilityState, str, tuple[str, ...]]:
        required = {
            "source_id": source_id,
            "observer_id": observer_id,
            "capture_method": capture_method,
            "observed_at": observed_at,
            "authority_domain": authority_domain,
            "raw_hash": raw_hash,
            "canonical_hash": canonical_hash,
        }
        missing = tuple(name for name, value in required.items() if not str(value).strip())
        if missing:
            return (
                AdmissibilityState.INADMISSIBLE_FOR_JUDGMENT,
                f"missing_required_fields:{','.join(missing)}",
                (),
            )
        source = self._sources.get(source_id)
        if source is None:
            return AdmissibilityState.LIMITED_FOR_JUDGMENT, "source_authority_unknown", ()
        if authority_domain in source.forbidden_domains:
            return (
                AdmissibilityState.INADMISSIBLE_FOR_JUDGMENT,
                "source_forbidden_for_authority_domain",
                source.authority_domains,
            )
        if not source.authorizes(authority_domain):
            return (
                AdmissibilityState.LIMITED_FOR_JUDGMENT,
                "source_lacks_domain_authority",
                source.authority_domains,
            )
        if float(risk_profile.get("adversarial_risk", 0.0) or 0.0) >= 0.9:
            return (
                AdmissibilityState.LIMITED_FOR_JUDGMENT,
                "adversarial_risk_caps_judgment",
                source.authority_domains,
            )
        return AdmissibilityState.ADMITTED, "admitted", source.authority_domains

    def _require_claim_no_lock(self, claim_id: str) -> ClaimNode:
        claim = self._claims.get(claim_id)
        if claim is None:
            raise EvidenceLedgerError(f"unknown_claim:{claim_id}")
        return claim

    def _ensure_conflicts_no_lock(self, claim: ClaimNode, *, actor_id: str) -> tuple[ConflictNode, ...]:
        support_edges = [self._edges[edge_id] for edge_id in claim.support_edges if edge_id in self._edges]
        refute_edges = [self._edges[edge_id] for edge_id in claim.refute_edges if edge_id in self._edges]
        existing = [self._conflicts[conflict_id] for conflict_id in claim.conflict_nodes if conflict_id in self._conflicts]
        if not support_edges or not refute_edges:
            return tuple(existing)
        evidence_ids = tuple(sorted({edge.from_evidence_id for edge in support_edges + refute_edges}))
        conflict_hash = _stable_hash(
            {"claim_id": claim.claim_id, "evidence_ids": evidence_ids, "type": ConflictType.DIRECT_CONTRADICTION}
        )
        conflict_id = f"conflict-{conflict_hash[:16]}"
        if conflict_id in self._conflicts:
            return tuple(existing or [self._conflicts[conflict_id]])
        severity = "high" if any(edge.weight >= 0.8 for edge in refute_edges) else "medium"
        conflict = ConflictNode(
            conflict_id=conflict_id,
            claim_id=claim.claim_id,
            evidence_ids=evidence_ids,
            conflict_type=ConflictType.DIRECT_CONTRADICTION,
            severity=severity,
            possible_resolution="recheck source authority, temporal scope, and claim-specific match fields",
            status="open",
            created_at=self._clock(),
        )
        stored = _stamp_conflict(conflict)
        self._conflicts[stored.conflict_id] = stored
        self._claims[claim.claim_id] = _stamp_claim(
            replace(claim, conflict_nodes=_append_unique(claim.conflict_nodes, stored.conflict_id))
        )
        self._append_event_no_lock(
            event_type="conflict_detected",
            actor_id=actor_id,
            payload=asdict(stored),
            policy_result={"accepted": True, "reason": "conflict_preserved"},
        )
        return tuple(existing + [stored])

    def _included_and_excluded_evidence_no_lock(
        self,
        edges: tuple[CausalEdge, ...],
    ) -> tuple[tuple[EvidenceAtom, ...], tuple[EvidenceAtom, ...]]:
        included: list[EvidenceAtom] = []
        excluded: list[EvidenceAtom] = []
        seen: set[str] = set()
        for edge in edges:
            evidence = self._evidence.get(edge.from_evidence_id)
            if evidence is None or evidence.evidence_id in seen:
                continue
            seen.add(evidence.evidence_id)
            if evidence.admissibility_state == AdmissibilityState.INADMISSIBLE_FOR_JUDGMENT:
                excluded.append(evidence)
            else:
                included.append(evidence)
        return tuple(included), tuple(excluded)

    def _missing_evidence_no_lock(self, claim: ClaimNode, support_edges: Iterable[CausalEdge]) -> tuple[str, ...]:
        required = set(claim.expected_evidence_profile.required_evidence_kinds)
        observed = {
            self._evidence[edge.from_evidence_id].evidence_kind.value
            for edge in support_edges
            if edge.from_evidence_id in self._evidence
            and self._evidence[edge.from_evidence_id].admissibility_state != AdmissibilityState.INADMISSIBLE_FOR_JUDGMENT
        }
        return tuple(sorted(required.difference(observed)))

    def _independence_assessment_no_lock(self, support_edges: Iterable[CausalEdge]) -> dict[str, Any]:
        families: dict[str, set[str]] = {}
        for edge in support_edges:
            evidence = self._evidence.get(edge.from_evidence_id)
            if evidence is None or evidence.admissibility_state == AdmissibilityState.INADMISSIBLE_FOR_JUDGMENT:
                continue
            family = evidence.evidence_family_id or evidence.evidence_id
            families.setdefault(family, set()).add(evidence.source_id)
        return {
            "evidence_family_count": len(families),
            "independent_source_count": len({source for sources in families.values() for source in sources}),
            "duplicate_family_count": sum(1 for sources in families.values() if len(sources) > 1),
            "families": {family: sorted(sources) for family, sources in sorted(families.items())},
        }

    def _source_authority_assessment_no_lock(self, evidence_items: Iterable[EvidenceAtom]) -> dict[str, Any]:
        records: list[dict[str, Any]] = []
        for evidence in evidence_items:
            source = self._sources.get(evidence.source_id)
            records.append(
                {
                    "evidence_id": evidence.evidence_id,
                    "source_id": evidence.source_id,
                    "authority_domain": evidence.authority_domain,
                    "authority_known": source is not None,
                    "authority_scoped": source.authorizes(evidence.authority_domain) if source else False,
                    "reliability_score": source.reliability_score if source else 0.0,
                    "admissibility_state": evidence.admissibility_state,
                }
            )
        return {
            "source_registry_version": self.source_registry_version,
            "records": records,
        }

    def _confidence_limits_no_lock(
        self,
        *,
        claim: ClaimNode,
        support_edges: Iterable[CausalEdge],
        included_evidence: tuple[EvidenceAtom, ...],
        conflicts: tuple[ConflictNode, ...],
    ) -> tuple[str, ...]:
        limits: list[str] = []
        missing = self._missing_evidence_no_lock(claim, support_edges)
        if missing:
            limits.append(f"missing_required_evidence:{','.join(missing)}")
        if conflicts:
            limits.append("unresolved_conflict_present")
        if any(evidence.admissibility_state == AdmissibilityState.LIMITED_FOR_JUDGMENT for evidence in included_evidence):
            limits.append("limited_source_authority_caps_strength")
        if any(evidence.derivation_parents for evidence in included_evidence):
            limits.append("derived_evidence_cannot_outrank_raw_parent")
        if any(not self._is_fresh(evidence, claim.expected_evidence_profile.freshness_window_days) for evidence in included_evidence):
            limits.append("stale_evidence_caps_strength")
        if not tuple(support_edges):
            limits.append("supporting_evidence_absent")
        return tuple(dict.fromkeys(limits))

    def _judgment_status_no_lock(
        self,
        *,
        claim: ClaimNode,
        support_edges: tuple[CausalEdge, ...],
        refute_edges: tuple[CausalEdge, ...],
        missing: tuple[str, ...],
        conflicts: tuple[ConflictNode, ...],
        independence: dict[str, Any],
        confidence_limits: tuple[str, ...],
    ) -> ClaimStatus:
        if missing:
            return ClaimStatus.NOT_READY_TO_JUDGE
        if self._decisive_refutation_no_lock(claim, refute_edges):
            return ClaimStatus.REFUTED
        if any(conflict.status == "open" and conflict.severity in {"high", "critical"} for conflict in conflicts):
            return ClaimStatus.CONFLICTED
        if not support_edges:
            return ClaimStatus.UNSUPPORTED
        support_strength = self._support_strength_no_lock(claim, support_edges)
        minimum_sources = claim.expected_evidence_profile.minimum_independent_sources
        independent_sources = int(independence.get("independent_source_count", 0))
        if (
            support_strength >= max(0.8, 0.8 * minimum_sources)
            and independent_sources >= minimum_sources
            and not confidence_limits
        ):
            return ClaimStatus.STRONGLY_SUPPORTED
        if support_strength >= 0.8 and independent_sources >= 1:
            return ClaimStatus.PROVISIONALLY_SUPPORTED
        return ClaimStatus.WEAKLY_SUPPORTED

    def _decisive_refutation_no_lock(self, claim: ClaimNode, refute_edges: Iterable[CausalEdge]) -> bool:
        threshold = claim.expected_evidence_profile.high_authority_refutation_threshold
        for edge in refute_edges:
            evidence = self._evidence.get(edge.from_evidence_id)
            if evidence is None or evidence.admissibility_state == AdmissibilityState.INADMISSIBLE_FOR_JUDGMENT:
                continue
            source = self._sources.get(evidence.source_id)
            reliability = source.reliability_score if source else 0.0
            if edge.weight >= threshold and reliability >= threshold:
                return True
        return False

    def _support_strength_no_lock(self, claim: ClaimNode, support_edges: Iterable[CausalEdge]) -> float:
        family_scores: dict[str, float] = {}
        for edge in support_edges:
            evidence = self._evidence.get(edge.from_evidence_id)
            if evidence is None or evidence.admissibility_state == AdmissibilityState.INADMISSIBLE_FOR_JUDGMENT:
                continue
            source = self._sources.get(evidence.source_id)
            reliability = source.reliability_score if source else 0.4
            state_cap = 1.0 if evidence.admissibility_state == AdmissibilityState.ADMITTED else 0.4
            derivation_cap = 0.6 if evidence.derivation_parents else 1.0
            freshness_cap = (
                1.0
                if self._is_fresh(evidence, claim.expected_evidence_profile.freshness_window_days)
                else 0.5
            )
            score = edge.weight * edge.confidence * reliability * state_cap * derivation_cap * freshness_cap
            family_scores[evidence.evidence_family_id or evidence.evidence_id] = max(
                family_scores.get(evidence.evidence_family_id or evidence.evidence_id, 0.0),
                score,
            )
        return sum(family_scores.values())

    def _is_fresh(self, evidence: EvidenceAtom, freshness_window_days: int) -> bool:
        if freshness_window_days == 0:
            return True
        try:
            observed = _parse_time(evidence.observed_at)
            checked = _parse_time(self._clock())
        except ValueError:
            return False
        return (checked - observed).days <= freshness_window_days

    def _evidence_summary_no_lock(self, evidence: EvidenceAtom, view: ExposureViewType) -> dict[str, Any]:
        source = self._sources.get(evidence.source_id)
        summary = {
            "evidence_id": evidence.evidence_id,
            "evidence_kind": evidence.evidence_kind.value,
            "source_id": evidence.source_id,
            "source_authority_class": source.source_type if source else "unknown_source_authority",
            "authority_domain": evidence.authority_domain,
            "observed_at": evidence.observed_at,
            "raw_hash": evidence.raw_hash,
            "canonical_hash": evidence.canonical_hash,
            "admissibility_state": evidence.admissibility_state.value,
            "evidence_family_id": evidence.evidence_family_id,
            "redaction": "raw_payload_not_exposed",
        }
        if view == ExposureViewType.FULL_AUDIT:
            summary.update(
                {
                    "observer_id": evidence.observer_id,
                    "capture_method": evidence.capture_method,
                    "custody_chain": list(evidence.custody_chain),
                    "risk_profile": dict(evidence.risk_profile),
                    "raw_reference": evidence.raw_reference,
                    "canonical_reference": evidence.canonical_reference,
                }
            )
        return summary

    def _append_event_no_lock(
        self,
        *,
        event_type: str,
        actor_id: str,
        payload: dict[str, Any],
        policy_result: dict[str, Any],
        receipt_id: str = "",
    ) -> LedgerEvent:
        timestamp = self._clock()
        parent_hash = self.current_head_hash()
        payload_hash = _stable_hash(payload)
        event_id = self._next_id_no_lock(
            "event",
            {
                "event_type": event_type,
                "actor_id": actor_id,
                "timestamp": timestamp,
                "payload_hash": payload_hash,
                "parent_hash": parent_hash,
            },
        )
        event = LedgerEvent(
            event_id=event_id,
            event_type=event_type,
            actor_id=actor_id,
            timestamp=timestamp,
            parent_hash=parent_hash,
            payload_hash=payload_hash,
            policy_result=policy_result,
            receipt_id=receipt_id,
        )
        stamped = replace(event, event_hash=_event_hash(event))
        self._events.append(stamped)
        return stamped

    def _next_id_no_lock(self, prefix: str, payload: dict[str, Any]) -> str:
        digest = _stable_hash(
            {
                "ledger_id": self.ledger_id,
                "schema_version": LEDGER_SCHEMA_VERSION,
                "index": len(self._events),
                "payload": payload,
            }
        )
        return f"{prefix}-{digest[:16]}"


def _claim_with_edge(claim: ClaimNode, edge: CausalEdge) -> ClaimNode:
    if edge.relation_type == RelationType.SUPPORTS:
        return replace(claim, support_edges=_append_unique(claim.support_edges, edge.edge_id))
    if edge.relation_type == RelationType.REFUTES:
        return replace(claim, refute_edges=_append_unique(claim.refute_edges, edge.edge_id))
    if edge.relation_type == RelationType.ABSENCE:
        return replace(claim, absence_edges=_append_unique(claim.absence_edges, edge.edge_id))
    return claim


def _stamp_claim(claim: ClaimNode) -> ClaimNode:
    payload = asdict(replace(claim, claim_hash=""))
    return replace(claim, claim_hash=_stable_hash(payload))


def _stamp_edge(edge: CausalEdge) -> CausalEdge:
    payload = asdict(replace(edge, edge_hash=""))
    return replace(edge, edge_hash=_stable_hash(payload))


def _stamp_conflict(conflict: ConflictNode) -> ConflictNode:
    payload = asdict(replace(conflict, conflict_hash=""))
    return replace(conflict, conflict_hash=_stable_hash(payload))


def _stamp_receipt(receipt: JudgmentReceipt) -> JudgmentReceipt:
    payload = asdict(receipt)
    payload["receipt_id"] = ""
    payload["receipt_hash"] = ""
    receipt_hash = _stable_hash(payload)
    return replace(receipt, receipt_id=f"judgment-receipt-{receipt_hash[:16]}", receipt_hash=receipt_hash)


def _event_hash(event: LedgerEvent) -> str:
    payload = asdict(replace(event, event_hash=""))
    return _stable_hash(payload)


def _stable_hash(payload: Any) -> str:
    encoded = json.dumps(_json_ready(payload), sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _evidence_kind(value: EvidenceKind | str) -> EvidenceKind:
    try:
        return value if isinstance(value, EvidenceKind) else EvidenceKind(str(value))
    except ValueError as exc:
        raise EvidenceLedgerError(f"evidence_kind_invalid:{value}") from exc


def _relation_type(value: RelationType | str) -> RelationType:
    try:
        return value if isinstance(value, RelationType) else RelationType(str(value))
    except ValueError as exc:
        raise EvidenceLedgerError(f"relation_type_invalid:{value}") from exc


def _exposure_view_type(value: ExposureViewType | str) -> ExposureViewType:
    try:
        return value if isinstance(value, ExposureViewType) else ExposureViewType(str(value))
    except ValueError as exc:
        raise EvidenceLedgerError(f"exposure_view_type_invalid:{value}") from exc


def _require_text(value: str, field_name: str) -> None:
    if not str(value).strip():
        raise EvidenceLedgerError(f"{field_name}_required")


def _normalize_text_tuple(values: Iterable[str], field_name: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    normalized = tuple(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))
    if not normalized and not allow_empty:
        raise EvidenceLedgerError(f"{field_name}_required")
    return normalized


def _normalize_kind_tuple(values: Iterable[str], field_name: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    normalized: list[str] = []
    for value in values:
        kind = _evidence_kind(value)
        if kind.value not in normalized:
            normalized.append(kind.value)
    if not normalized and not allow_empty:
        raise EvidenceLedgerError(f"{field_name}_required")
    return tuple(normalized)


def _append_unique(values: tuple[str, ...], value: str) -> tuple[str, ...]:
    if value in values:
        return values
    return (*values, value)


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, StrEnum):
        return value.value
    return value
