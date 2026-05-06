"""Gateway data governance and privacy lifecycle.

Purpose: classify tenant data and gate sensitive persistence, export, deletion,
    legal hold, retention, residency, and encryption decisions.
Governance scope: PII classification, purpose limitation, consent records,
    data residency tags, encrypted persistence, retention policy, export,
    deletion workflow, legal hold, and hash-bound operator read models.
Dependencies: dataclasses, enum, datetime, and command-spine canonical hashing.
Invariants:
  - Sensitive production persistence requires encryption and retention.
  - Legal hold blocks deletion regardless of retention age.
  - Export requires tenant match, purpose compatibility, and residency proof.
  - Lifecycle decisions are records only; this module performs no deletion.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Iterable

from gateway.command_spine import canonical_hash


class DataClassification(StrEnum):
    """Gateway data classification."""

    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    SENSITIVE = "sensitive"
    PII = "pii"
    RESTRICTED = "restricted"
    SECRET = "secret"


class PrivacyBasis(StrEnum):
    """Processing basis."""

    CONSENT = "consent"
    CONTRACT = "contract"
    LEGAL_OBLIGATION = "legal_obligation"
    LEGITIMATE_INTEREST = "legitimate_interest"


class DataLifecycleAction(StrEnum):
    """Lifecycle action being evaluated."""

    PERSIST = "persist"
    EXPORT = "export"
    DELETE = "delete"
    LEGAL_HOLD = "legal_hold"
    RELEASE_HOLD = "release_hold"


class DataLifecycleVerdict(StrEnum):
    """Lifecycle decision verdict."""

    ALLOW = "allow"
    DENY = "deny"
    REVIEW = "review"


_SENSITIVE_CLASSIFICATIONS = frozenset({
    DataClassification.CONFIDENTIAL,
    DataClassification.SENSITIVE,
    DataClassification.PII,
    DataClassification.RESTRICTED,
    DataClassification.SECRET,
})


@dataclass(frozen=True, slots=True)
class DataGovernanceRecord:
    """Classified data object with privacy lifecycle controls."""

    data_id: str
    tenant_id: str
    classification: DataClassification
    purpose: str
    source_event_id: str
    created_at: str
    retention_until: str
    delete_after: str
    privacy_basis: PrivacyBasis
    data_residency: str
    encrypted: bool
    legal_hold: bool = False
    consent_ref: str = ""
    evidence_refs: tuple[str, ...] = ()
    record_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("data_id", "tenant_id", "purpose", "source_event_id", "created_at", "retention_until", "delete_after", "data_residency"):
            _require_text(getattr(self, field_name), field_name)
        if not isinstance(self.classification, DataClassification):
            raise ValueError("data_classification_invalid")
        if not isinstance(self.privacy_basis, PrivacyBasis):
            raise ValueError("privacy_basis_invalid")
        if self.classification is DataClassification.PII and self.privacy_basis is PrivacyBasis.CONSENT and not self.consent_ref:
            raise ValueError("consent_ref_required_for_pii_consent")
        if _parse_time(self.delete_after) < _parse_time(self.retention_until):
            raise ValueError("delete_after_must_not_precede_retention_until")
        object.__setattr__(self, "evidence_refs", _normalize_text_tuple(self.evidence_refs, "evidence_refs", allow_empty=True))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_json_dict(self) -> dict[str, Any]:
        """Return a schema-oriented JSON object."""
        return _json_ready(asdict(self))


@dataclass(frozen=True, slots=True)
class DataLifecycleRequest:
    """Request to evaluate a data lifecycle action."""

    request_id: str
    data_id: str
    tenant_id: str
    action: DataLifecycleAction
    requested_at: str
    actor_id: str
    purpose: str = ""
    target_residency: str = ""
    encryption_enabled: bool = False
    retention_policy_ref: str = ""
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name in ("request_id", "data_id", "tenant_id", "requested_at", "actor_id"):
            _require_text(getattr(self, field_name), field_name)
        if not isinstance(self.action, DataLifecycleAction):
            raise ValueError("data_lifecycle_action_invalid")
        object.__setattr__(self, "evidence_refs", _normalize_text_tuple(self.evidence_refs, "evidence_refs", allow_empty=True))


@dataclass(frozen=True, slots=True)
class DataLifecycleDecision:
    """Decision for one lifecycle request."""

    decision_id: str
    request_id: str
    data_id: str
    tenant_id: str
    action: DataLifecycleAction
    verdict: DataLifecycleVerdict
    reason: str
    required_controls: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    decided_at: str
    decision_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("decision_id", "request_id", "data_id", "tenant_id", "reason", "decided_at"):
            _require_text(getattr(self, field_name), field_name)
        if not isinstance(self.action, DataLifecycleAction):
            raise ValueError("data_lifecycle_action_invalid")
        if not isinstance(self.verdict, DataLifecycleVerdict):
            raise ValueError("data_lifecycle_verdict_invalid")
        object.__setattr__(self, "required_controls", _normalize_text_tuple(self.required_controls, "required_controls", allow_empty=True))
        object.__setattr__(self, "evidence_refs", _normalize_text_tuple(self.evidence_refs, "evidence_refs", allow_empty=True))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_json_dict(self) -> dict[str, Any]:
        """Return a schema-oriented JSON object."""
        return _json_ready(asdict(self))


@dataclass(frozen=True, slots=True)
class DataGovernanceSnapshot:
    """Operator read model for gateway data governance state."""

    snapshot_id: str
    records: tuple[DataGovernanceRecord, ...]
    decisions: tuple[DataLifecycleDecision, ...]
    sensitive_record_count: int
    legal_hold_count: int
    open_review_count: int
    snapshot_hash: str = ""

    def __post_init__(self) -> None:
        _require_text(self.snapshot_id, "snapshot_id")
        object.__setattr__(self, "records", tuple(self.records))
        object.__setattr__(self, "decisions", tuple(self.decisions))
        if self.sensitive_record_count < 0 or self.legal_hold_count < 0 or self.open_review_count < 0:
            raise ValueError("snapshot_counts_nonnegative_required")

    def to_json_dict(self) -> dict[str, Any]:
        """Return a schema-oriented JSON object."""
        return _json_ready(asdict(self))


class DataGovernanceRegistry:
    """In-memory gateway data governance registry."""

    def __init__(self, *, clock: Any | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(timezone.utc).isoformat())
        self._records: dict[str, DataGovernanceRecord] = {}
        self._decisions: list[DataLifecycleDecision] = []

    def register(self, record: DataGovernanceRecord) -> DataGovernanceRecord:
        """Register one stamped data governance record."""
        if record.data_id in self._records:
            raise ValueError("duplicate_data_id")
        stamped = _stamp_record(record)
        self._records[stamped.data_id] = stamped
        return stamped

    def evaluate(self, request: DataLifecycleRequest) -> DataLifecycleDecision:
        """Evaluate one lifecycle request and record the decision."""
        record = self._records.get(request.data_id)
        if record is None:
            return self._decision(request, DataLifecycleVerdict.DENY, "data_record_unknown", ("data_inventory",), ())
        if record.tenant_id != request.tenant_id:
            return self._decision(request, DataLifecycleVerdict.DENY, "tenant_boundary_denied", ("tenant_binding",), record.evidence_refs)
        if request.action is DataLifecycleAction.PERSIST:
            return self._evaluate_persist(record, request)
        if request.action is DataLifecycleAction.EXPORT:
            return self._evaluate_export(record, request)
        if request.action is DataLifecycleAction.DELETE:
            return self._evaluate_delete(record, request)
        if request.action is DataLifecycleAction.LEGAL_HOLD:
            return self._decision(request, DataLifecycleVerdict.ALLOW, "legal_hold_recorded", ("legal_hold_authority",), record.evidence_refs)
        if request.action is DataLifecycleAction.RELEASE_HOLD:
            return self._decision(request, DataLifecycleVerdict.REVIEW, "legal_hold_release_requires_review", ("legal_review",), record.evidence_refs)
        return self._decision(request, DataLifecycleVerdict.DENY, "unsupported_lifecycle_action", (), record.evidence_refs)

    def place_legal_hold(self, *, data_id: str, evidence_refs: Iterable[str]) -> DataGovernanceRecord:
        """Mark a data record as held; no deletion is performed."""
        record = self._require_record(data_id)
        refs = tuple(dict.fromkeys((*record.evidence_refs, *tuple(evidence_refs))))
        updated = _stamp_record(replace(record, legal_hold=True, evidence_refs=refs))
        self._records[data_id] = updated
        return updated

    def snapshot(self, *, snapshot_id: str) -> DataGovernanceSnapshot:
        """Return a stamped operator read model."""
        records = tuple(sorted(self._records.values(), key=lambda item: item.data_id))
        decisions = tuple(self._decisions)
        snapshot = DataGovernanceSnapshot(
            snapshot_id=snapshot_id,
            records=records,
            decisions=decisions,
            sensitive_record_count=sum(1 for record in records if _sensitive(record)),
            legal_hold_count=sum(1 for record in records if record.legal_hold),
            open_review_count=sum(1 for decision in decisions if decision.verdict is DataLifecycleVerdict.REVIEW),
        )
        payload = snapshot.to_json_dict()
        payload["snapshot_hash"] = ""
        return replace(snapshot, snapshot_hash=canonical_hash(payload))

    def _evaluate_persist(
        self,
        record: DataGovernanceRecord,
        request: DataLifecycleRequest,
    ) -> DataLifecycleDecision:
        if _sensitive(record) and not request.encryption_enabled:
            return self._decision(request, DataLifecycleVerdict.DENY, "sensitive_persistence_requires_encryption", ("encryption",), record.evidence_refs)
        if _sensitive(record) and not request.retention_policy_ref:
            return self._decision(request, DataLifecycleVerdict.DENY, "sensitive_persistence_requires_retention_policy", ("retention_policy",), record.evidence_refs)
        return self._decision(request, DataLifecycleVerdict.ALLOW, "persistence_controls_satisfied", ("tenant_binding", "retention_policy", "encryption"), record.evidence_refs)

    def _evaluate_export(
        self,
        record: DataGovernanceRecord,
        request: DataLifecycleRequest,
    ) -> DataLifecycleDecision:
        if request.purpose and request.purpose != record.purpose:
            return self._decision(request, DataLifecycleVerdict.DENY, "purpose_limitation_denied", ("purpose_limitation",), record.evidence_refs)
        if request.target_residency and request.target_residency != record.data_residency:
            return self._decision(request, DataLifecycleVerdict.REVIEW, "cross_residency_export_requires_review", ("residency_review",), record.evidence_refs)
        if _sensitive(record):
            return self._decision(request, DataLifecycleVerdict.REVIEW, "sensitive_export_requires_review", ("privacy_review", "audit_export"), record.evidence_refs)
        return self._decision(request, DataLifecycleVerdict.ALLOW, "export_controls_satisfied", ("audit_export",), record.evidence_refs)

    def _evaluate_delete(
        self,
        record: DataGovernanceRecord,
        request: DataLifecycleRequest,
    ) -> DataLifecycleDecision:
        if record.legal_hold:
            return self._decision(request, DataLifecycleVerdict.DENY, "legal_hold_blocks_deletion", ("legal_hold_release",), record.evidence_refs)
        if _parse_time(request.requested_at) < _parse_time(record.delete_after):
            return self._decision(request, DataLifecycleVerdict.REVIEW, "retention_window_not_expired", ("retention_review",), record.evidence_refs)
        return self._decision(request, DataLifecycleVerdict.ALLOW, "deletion_workflow_allowed", ("deletion_receipt", "audit_trail"), record.evidence_refs)

    def _decision(
        self,
        request: DataLifecycleRequest,
        verdict: DataLifecycleVerdict,
        reason: str,
        required_controls: tuple[str, ...],
        record_evidence_refs: tuple[str, ...],
    ) -> DataLifecycleDecision:
        decision = DataLifecycleDecision(
            decision_id="pending",
            request_id=request.request_id,
            data_id=request.data_id,
            tenant_id=request.tenant_id,
            action=request.action,
            verdict=verdict,
            reason=reason,
            required_controls=required_controls,
            evidence_refs=tuple(dict.fromkeys((*request.evidence_refs, *record_evidence_refs))),
            decided_at=self._clock(),
            metadata={"decision_is_not_deletion": True},
        )
        payload = decision.to_json_dict()
        payload["decision_hash"] = ""
        decision_hash = canonical_hash(payload)
        stamped = replace(decision, decision_id=f"data-decision-{decision_hash[:16]}", decision_hash=decision_hash)
        self._decisions.append(stamped)
        return stamped

    def _require_record(self, data_id: str) -> DataGovernanceRecord:
        record = self._records.get(data_id)
        if record is None:
            raise ValueError("data_record_unknown")
        return record


def data_governance_snapshot_to_json_dict(snapshot: DataGovernanceSnapshot) -> dict[str, Any]:
    """Return the public JSON-contract representation of a data governance snapshot."""
    return snapshot.to_json_dict()


def _sensitive(record: DataGovernanceRecord) -> bool:
    return record.classification in _SENSITIVE_CLASSIFICATIONS


def _stamp_record(record: DataGovernanceRecord) -> DataGovernanceRecord:
    payload = record.to_json_dict()
    payload["record_hash"] = ""
    return replace(record, record_hash=canonical_hash(payload))


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _normalize_text_tuple(values: tuple[str, ...], field_name: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    normalized = tuple(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))
    if not normalized and not allow_empty:
        raise ValueError(f"{field_name}_required")
    return normalized


def _require_text(value: str, field_name: str) -> None:
    if not str(value).strip():
        raise ValueError(f"{field_name}_required")


def _json_ready(value: Any) -> Any:
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    return value
