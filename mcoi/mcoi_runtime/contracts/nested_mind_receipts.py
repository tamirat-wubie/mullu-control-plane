"""Purpose: runtime-only nested-mind receipt and commit witness contracts.
Governance scope: nested-mind observation bridge evidence only; no public schema.
Dependencies: shared contract helpers and nested-mind observation planning contracts.
Invariants:
  - Commit success requires verified nested-mind commit and history hashes.
  - Raw response bodies and bearer tokens are never represented here.
  - Bridge success is reserved for VERIFIED witnesses only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from ._base import ContractRecord, freeze_value, require_datetime_text, require_non_empty_text


class NestedMindCommitWitnessStatus(StrEnum):
    OBSERVED = "observed"
    VERIFIED = "verified"
    BLOCKED = "blocked"


class NestedMindReceiptBridgeStatus(StrEnum):
    BRIDGED = "bridged"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class NestedMindCommitWitness(ContractRecord):
    witness_id: str
    proposal_evidence_id: str
    mind_id: str
    mullu_receipt_hash: str
    nested_mind_commit_hash: str
    nested_mind_history_hash: str
    witnessed_at: str
    status: NestedMindCommitWitnessStatus
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "witness_id",
            "proposal_evidence_id",
            "mind_id",
            "mullu_receipt_hash",
            "nested_mind_commit_hash",
            "nested_mind_history_hash",
        ):
            object.__setattr__(
                self,
                field_name,
                require_non_empty_text(getattr(self, field_name), field_name),
            )
        object.__setattr__(self, "witnessed_at", require_datetime_text(self.witnessed_at, "witnessed_at"))
        if not isinstance(self.status, NestedMindCommitWitnessStatus):
            raise ValueError("status must be a NestedMindCommitWitnessStatus value")
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class NestedMindReceiptBridgeReport(ContractRecord):
    report_id: str
    proposal_evidence_id: str
    mind_id: str
    commit_witness_id: str | None
    status: NestedMindReceiptBridgeStatus
    bridged_at: str
    blockers: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("report_id", "proposal_evidence_id", "mind_id"):
            object.__setattr__(
                self,
                field_name,
                require_non_empty_text(getattr(self, field_name), field_name),
            )
        if self.commit_witness_id is not None:
            object.__setattr__(
                self,
                "commit_witness_id",
                require_non_empty_text(self.commit_witness_id, "commit_witness_id"),
            )
        if not isinstance(self.status, NestedMindReceiptBridgeStatus):
            raise ValueError("status must be a NestedMindReceiptBridgeStatus value")
        object.__setattr__(self, "bridged_at", require_datetime_text(self.bridged_at, "bridged_at"))
        object.__setattr__(self, "blockers", tuple(self.blockers))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


def build_commit_witness(
    evidence: object,
    *,
    witness_id: str,
    nested_mind_commit_hash: str,
    nested_mind_history_hash: str,
    witnessed_at: str,
    status: NestedMindCommitWitnessStatus,
    metadata: Mapping[str, Any] | None = None,
) -> NestedMindCommitWitness:
    """Build a commit witness from already-verified response fields."""

    if status is NestedMindCommitWitnessStatus.VERIFIED:
        require_non_empty_text(nested_mind_commit_hash, "nested_mind_commit_hash")
        require_non_empty_text(nested_mind_history_hash, "nested_mind_history_hash")
    return NestedMindCommitWitness(
        witness_id=witness_id,
        proposal_evidence_id=require_non_empty_text(
            getattr(evidence, "evidence_id", getattr(evidence, "proposal_evidence_id", "")),
            "proposal_evidence_id",
        ),
        mind_id=require_non_empty_text(getattr(evidence, "mind_id"), "mind_id"),
        mullu_receipt_hash=require_non_empty_text(
            getattr(evidence, "mullu_receipt_hash"),
            "mullu_receipt_hash",
        ),
        nested_mind_commit_hash=nested_mind_commit_hash,
        nested_mind_history_hash=nested_mind_history_hash,
        witnessed_at=witnessed_at,
        status=status,
        metadata=metadata or {},
    )


def build_verified_observation_bridge_report(
    evidence: object,
    submission: object,
    witness: NestedMindCommitWitness | None,
    *,
    report_id: str,
    bridged_at: str,
) -> NestedMindReceiptBridgeReport:
    """Build a bridge report only for accepted submissions with VERIFIED witnesses."""

    blockers: list[str] = []
    evidence_id = require_non_empty_text(getattr(evidence, "evidence_id", ""), "proposal_evidence_id")
    mind_id = require_non_empty_text(getattr(evidence, "mind_id", ""), "mind_id")
    if getattr(submission, "status", None) != "accepted":
        blockers.append("submission_status_not_accepted")
    if witness is None:
        blockers.append("commit_witness_required")
    else:
        if witness.status is not NestedMindCommitWitnessStatus.VERIFIED:
            blockers.append("commit_witness_not_verified")
        if witness.proposal_evidence_id != evidence_id:
            blockers.append("proposal_evidence_id_mismatch")
        if witness.mind_id != mind_id:
            blockers.append("mind_id_mismatch")
        if witness.mullu_receipt_hash != getattr(evidence, "mullu_receipt_hash", ""):
            blockers.append("mullu_receipt_hash_mismatch")
        if getattr(submission, "commit_witness_id", None) != witness.witness_id:
            blockers.append("submission_commit_witness_id_mismatch")

    return NestedMindReceiptBridgeReport(
        report_id=report_id,
        proposal_evidence_id=evidence_id,
        mind_id=mind_id,
        commit_witness_id=witness.witness_id if witness is not None else None,
        status=(
            NestedMindReceiptBridgeStatus.BLOCKED
            if blockers
            else NestedMindReceiptBridgeStatus.BRIDGED
        ),
        bridged_at=bridged_at,
        blockers=tuple(blockers),
        metadata={
            "submission_report_id": getattr(submission, "report_id", ""),
        },
    )
