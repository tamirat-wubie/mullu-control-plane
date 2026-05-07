"""Gateway claim verification graph.

Purpose: distinguish observed facts, user claims, source claims, model
inferences, verified results, stale results, and contradicted results before
claims enter planning or execution.
Governance scope: claim source evidence, support edges, contradiction edges,
freshness windows, domain risk, planning admission, execution admission, and
schema-backed verification reports.
Dependencies: dataclasses, datetime, enum, and command-spine canonical hashing.
Invariants:
  - Every claim source carries evidence refs.
  - Unsupported claims cannot enter execution.
  - Contradicted or stale claims cannot enter execution.
  - High-risk claims require independent support evidence.
  - Verification reports are non-mutating and hash-bound.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from gateway.command_spine import canonical_hash


class ClaimKind(StrEnum):
    """Governed claim provenance class."""

    OBSERVED_FACT = "observed_fact"
    USER_CLAIM = "user_claim"
    MODEL_INFERENCE = "model_inference"
    EXTERNAL_SOURCE_CLAIM = "external_source_claim"
    VERIFIED_RESULT = "verified_result"
    STALE_RESULT = "stale_result"
    CONTRADICTED_RESULT = "contradicted_result"


class ClaimRisk(StrEnum):
    """Claim domain risk tier."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ClaimVerificationStatus(StrEnum):
    """Claim verification result."""

    VERIFIED = "verified"
    UNSUPPORTED = "unsupported"
    CONTRADICTED = "contradicted"
    STALE = "stale"
    REQUIRES_REVIEW = "requires_review"


@dataclass(frozen=True, slots=True)
class ClaimSource:
    """Evidence-bearing source for one claim."""

    source_id: str
    source_type: str
    observed_at: str
    evidence_refs: tuple[str, ...]
    uri: str = ""
    source_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("source_id", "source_type", "observed_at"):
            _require_text(getattr(self, field_name), field_name)
        object.__setattr__(self, "evidence_refs", _normalize_text_tuple(self.evidence_refs, "evidence_refs"))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def stamped(self) -> "ClaimSource":
        """Return a hash-bound copy of the source."""
        stamped = replace(self, source_hash="")
        return replace(stamped, source_hash=canonical_hash(asdict(stamped)))


@dataclass(frozen=True, slots=True)
class ClaimNode:
    """Sourced proposition whose use must be verified."""

    claim_id: str
    tenant_id: str
    claim_text: str
    claim_kind: ClaimKind
    domain_risk: ClaimRisk
    confidence: float
    observed_at: str
    freshness_window_days: int
    sources: tuple[ClaimSource, ...]
    supported_by: tuple[str, ...] = ()
    contradicted_by: tuple[str, ...] = ()
    derived_from: tuple[str, ...] = ()
    valid_until: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("claim_id", "tenant_id", "claim_text", "observed_at"):
            _require_text(getattr(self, field_name), field_name)
        if not isinstance(self.claim_kind, ClaimKind):
            raise ValueError("claim_kind_invalid")
        if not isinstance(self.domain_risk, ClaimRisk):
            raise ValueError("claim_risk_invalid")
        if not 0 <= self.confidence <= 1:
            raise ValueError("claim_confidence_between_zero_and_one")
        if not isinstance(self.freshness_window_days, int) or isinstance(self.freshness_window_days, bool):
            raise ValueError("freshness_window_days_integer_required")
        if self.freshness_window_days < 0:
            raise ValueError("freshness_window_days_nonnegative_required")
        sources = tuple(source.stamped() for source in self.sources)
        if not sources:
            raise ValueError("claim_sources_required")
        object.__setattr__(self, "sources", sources)
        object.__setattr__(
            self,
            "supported_by",
            _normalize_text_tuple(self.supported_by, "supported_by", allow_empty=True),
        )
        object.__setattr__(
            self,
            "contradicted_by",
            _normalize_text_tuple(self.contradicted_by, "contradicted_by", allow_empty=True),
        )
        object.__setattr__(
            self,
            "derived_from",
            _normalize_text_tuple(self.derived_from, "derived_from", allow_empty=True),
        )
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class ClaimVerificationReport:
    """Hash-bound verification report for one claim."""

    report_id: str
    tenant_id: str
    claim_id: str
    claim_kind: ClaimKind
    status: ClaimVerificationStatus
    allowed_for_planning: bool
    allowed_for_execution: bool
    confidence: float
    domain_risk: ClaimRisk
    supported_by: tuple[str, ...]
    contradicted_by: tuple[str, ...]
    missing_requirements: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    checked_at: str
    report_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("report_id", "tenant_id", "claim_id", "checked_at"):
            _require_text(getattr(self, field_name), field_name)
        if not isinstance(self.claim_kind, ClaimKind):
            raise ValueError("claim_kind_invalid")
        if not isinstance(self.status, ClaimVerificationStatus):
            raise ValueError("claim_verification_status_invalid")
        if not isinstance(self.domain_risk, ClaimRisk):
            raise ValueError("claim_risk_invalid")
        if self.allowed_for_execution and not self.allowed_for_planning:
            raise ValueError("claim_execution_requires_planning")
        if self.allowed_for_execution and self.status != ClaimVerificationStatus.VERIFIED:
            raise ValueError("claim_execution_requires_verified_status")
        object.__setattr__(
            self,
            "supported_by",
            _normalize_text_tuple(self.supported_by, "supported_by", allow_empty=True),
        )
        object.__setattr__(
            self,
            "contradicted_by",
            _normalize_text_tuple(self.contradicted_by, "contradicted_by", allow_empty=True),
        )
        object.__setattr__(
            self,
            "missing_requirements",
            _normalize_text_tuple(self.missing_requirements, "missing_requirements", allow_empty=True),
        )
        object.__setattr__(self, "evidence_refs", _normalize_text_tuple(self.evidence_refs, "evidence_refs"))
        object.__setattr__(self, "metadata", _report_metadata(self.metadata))

    def to_json_dict(self) -> dict[str, Any]:
        """Return a schema-oriented JSON object."""
        return _json_ready(asdict(self))


class ClaimVerificationEngine:
    """Verify sourced claims against support, contradiction, and freshness gates."""

    def verify(self, claim: ClaimNode, *, checked_at: str) -> ClaimVerificationReport:
        """Return a deterministic verification report for one claim."""
        _require_text(checked_at, "checked_at")
        evidence_refs = _claim_evidence_refs(claim)
        missing: list[str] = []
        status = ClaimVerificationStatus.VERIFIED
        planning = True
        execution = True

        if claim.contradicted_by or claim.claim_kind == ClaimKind.CONTRADICTED_RESULT:
            status = ClaimVerificationStatus.CONTRADICTED
            planning = False
            execution = False
        elif _is_stale(claim, checked_at) or claim.claim_kind == ClaimKind.STALE_RESULT:
            status = ClaimVerificationStatus.STALE
            planning = False
            execution = False
        else:
            if not claim.supported_by and claim.claim_kind not in {ClaimKind.OBSERVED_FACT, ClaimKind.VERIFIED_RESULT}:
                missing.append("supporting_claim_or_source_required")
            if claim.claim_kind == ClaimKind.MODEL_INFERENCE and not claim.derived_from:
                missing.append("inference_derivation_required")
            if (
                claim.domain_risk in {ClaimRisk.HIGH, ClaimRisk.CRITICAL}
                and _independent_source_count(claim) < 2
            ):
                missing.append("independent_support_sources_required")
            if missing:
                if claim.domain_risk in {ClaimRisk.HIGH, ClaimRisk.CRITICAL}:
                    status = ClaimVerificationStatus.REQUIRES_REVIEW
                else:
                    status = ClaimVerificationStatus.UNSUPPORTED
                execution = False
                planning = claim.domain_risk in {ClaimRisk.LOW, ClaimRisk.MEDIUM}

        report = ClaimVerificationReport(
            report_id="pending",
            tenant_id=claim.tenant_id,
            claim_id=claim.claim_id,
            claim_kind=claim.claim_kind,
            status=status,
            allowed_for_planning=planning,
            allowed_for_execution=execution,
            confidence=claim.confidence,
            domain_risk=claim.domain_risk,
            supported_by=claim.supported_by or tuple(source.source_id for source in claim.sources),
            contradicted_by=claim.contradicted_by,
            missing_requirements=tuple(missing),
            evidence_refs=evidence_refs,
            checked_at=checked_at,
            metadata={
                "freshness_window_days": claim.freshness_window_days,
                "source_count": len(claim.sources),
                "claim_text_hash": canonical_hash({"claim_text": claim.claim_text}),
            },
        )
        report_hash = canonical_hash(asdict(report))
        return replace(report, report_id=f"claim-verification-{report_hash[:16]}", report_hash=report_hash)


def _claim_evidence_refs(claim: ClaimNode) -> tuple[str, ...]:
    refs: list[str] = []
    for source in claim.sources:
        refs.extend(source.evidence_refs)
    return tuple(dict.fromkeys(refs))


def _independent_source_count(claim: ClaimNode) -> int:
    return len({source.source_id for source in claim.sources})


def _is_stale(claim: ClaimNode, checked_at: str) -> bool:
    if claim.freshness_window_days == 0:
        return False
    observed = _parse_time(claim.observed_at)
    checked = _parse_time(checked_at)
    return (checked - observed).days > claim.freshness_window_days


def _parse_time(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _report_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    payload = dict(metadata)
    payload["claim_type_declared"] = True
    payload["source_evidence_required"] = True
    payload["contradictions_block_execution"] = True
    payload["stale_claims_block_execution"] = True
    payload["high_risk_requires_independent_support"] = True
    return payload


def _normalize_text_tuple(
    values: tuple[str, ...],
    field_name: str,
    *,
    allow_empty: bool = False,
) -> tuple[str, ...]:
    normalized = tuple(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))
    if not normalized and not allow_empty:
        raise ValueError(f"{field_name}_required")
    return normalized


def _require_text(value: str, field_name: str) -> None:
    if not str(value).strip():
        raise ValueError(f"{field_name}_required")


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
