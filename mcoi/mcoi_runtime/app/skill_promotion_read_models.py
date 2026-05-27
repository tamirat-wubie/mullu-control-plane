"""Purpose: read-only operator models for skill promotion evidence receipts.
Governance scope: operator-facing skill promotion receipt inspection only.
Dependencies: skill promotion contracts and structured errors.
Invariants:
  - Models are read-only projections and never mutate registry or receipt state.
  - Filters are explicit and bounded.
  - Missing or failed storage reads are represented as structured errors.
"""

from __future__ import annotations

from dataclasses import dataclass

from mcoi_runtime.contracts.skill import SkillLifecycle, SkillPromotionEvidence
from mcoi_runtime.core.errors import StructuredError
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


@dataclass(frozen=True, slots=True)
class SkillPromotionReceiptReadRequest:
    """Request to inspect persisted skill promotion evidence receipts."""

    request_id: str
    subject_id: str
    skill_id: str = ""
    target_lifecycle: SkillLifecycle | None = None
    limit: int | None = None

    def __post_init__(self) -> None:
        for field_name in ("request_id", "subject_id"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise RuntimeCoreInvariantError(f"{field_name} must be a non-empty string")
        if not isinstance(self.skill_id, str):
            raise RuntimeCoreInvariantError("skill_id must be a string")
        if self.target_lifecycle is not None and not isinstance(self.target_lifecycle, SkillLifecycle):
            raise RuntimeCoreInvariantError("target_lifecycle must be a SkillLifecycle value")
        if self.limit is not None and (not isinstance(self.limit, int) or self.limit < 1):
            raise RuntimeCoreInvariantError("limit must be a positive integer")


@dataclass(frozen=True, slots=True)
class SkillPromotionReceiptSummary:
    """Operator-facing projection of one skill promotion evidence receipt."""

    evidence_id: str
    skill_id: str
    target_lifecycle: SkillLifecycle
    execution_record_ids: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    verification_ids: tuple[str, ...]
    created_at: str
    reason: str

    @staticmethod
    def from_evidence(evidence: SkillPromotionEvidence) -> "SkillPromotionReceiptSummary":
        return SkillPromotionReceiptSummary(
            evidence_id=evidence.evidence_id,
            skill_id=evidence.skill_id,
            target_lifecycle=evidence.target_lifecycle,
            execution_record_ids=evidence.execution_record_ids,
            evidence_refs=evidence.evidence_refs,
            verification_ids=evidence.verification_ids,
            created_at=evidence.created_at,
            reason=evidence.reason,
        )


@dataclass(frozen=True, slots=True)
class SkillPromotionReceiptReadReport:
    """Report from read-only skill promotion receipt inspection."""

    request_id: str
    store_configured: bool
    receipt_count: int
    receipts: tuple[SkillPromotionReceiptSummary, ...]
    skill_id_filter: str = ""
    target_lifecycle_filter: SkillLifecycle | None = None
    errors: tuple[StructuredError, ...] = ()
