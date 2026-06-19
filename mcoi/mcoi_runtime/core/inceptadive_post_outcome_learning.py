"""Post-outcome learning candidates for InceptaDive Shadow Pass.

Purpose: compare expected governed plans with actual outcomes and emit bounded
learning candidates that can be written only through separate governance.
Governance scope: learning-candidate generation only; this module cannot mutate
memory, approve future actions, execute remediation, or promote truth.
Dependencies: dataclasses, shared shadow types, and deterministic identifiers.
Invariants: every candidate is traceable to outcome evidence and remains
governance_pending until another governed write path accepts it.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Mapping, Sequence

from mcoi_runtime.core.inceptadive_shadow_types import ShadowReceipt
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, stable_identifier


class OutcomeLearningKind(StrEnum):
    """Bounded post-outcome learning classes."""

    EXPECTATION_MATCHED = "expectation_matched"
    EXPECTATION_MISMATCH = "expectation_mismatch"
    MISSING_EVIDENCE = "missing_evidence"
    GOVERNANCE_DRIFT = "governance_drift"
    REPAIR_INCOMPLETE = "repair_incomplete"


@dataclass(frozen=True)
class InceptaDiveOutcomeLearningCandidate:
    """Governance-pending learning candidate derived from an outcome."""

    candidate_id: str
    request_id: str
    kind: OutcomeLearningKind
    summary: str
    evidence_refs: tuple[str, ...]
    source_receipt_ids: tuple[str, ...]
    recommended_repair: str = ""
    governance_pending: bool = True
    memory_write_authority: bool = False
    execution_authority: bool = False

    def __post_init__(self) -> None:
        if not self.candidate_id.strip():
            raise RuntimeCoreInvariantError("candidate_id must be non-empty")
        if not self.request_id.strip():
            raise RuntimeCoreInvariantError("request_id must be non-empty")
        if not self.summary.strip():
            raise RuntimeCoreInvariantError("summary must be non-empty")
        if not self.evidence_refs:
            raise RuntimeCoreInvariantError("outcome learning candidate requires evidence_refs")
        if not self.source_receipt_ids:
            raise RuntimeCoreInvariantError("outcome learning candidate requires source_receipt_ids")
        if not self.governance_pending:
            raise RuntimeCoreInvariantError("outcome learning candidates must remain governance_pending")
        if self.memory_write_authority or self.execution_authority:
            raise RuntimeCoreInvariantError("outcome learning candidate cannot carry write or execution authority")

    def to_dict(self) -> dict[str, object]:
        return {
            "candidate_id": self.candidate_id,
            "request_id": self.request_id,
            "kind": self.kind.value,
            "summary": self.summary,
            "evidence_refs": list(self.evidence_refs),
            "source_receipt_ids": list(self.source_receipt_ids),
            "recommended_repair": self.recommended_repair,
            "governance_pending": self.governance_pending,
            "memory_write_authority": False,
            "execution_authority": False,
        }


def build_outcome_learning_candidate(
    *,
    request_id: str,
    expected_state: Mapping[str, object],
    actual_state: Mapping[str, object],
    shadow_receipts: Sequence[ShadowReceipt],
    evidence_refs: Sequence[str],
) -> InceptaDiveOutcomeLearningCandidate:
    """Build one governance-pending learning candidate from outcome evidence."""

    checked_evidence = tuple(str(ref).strip() for ref in evidence_refs if str(ref).strip())
    receipt_ids = tuple(receipt.receipt_id for receipt in shadow_receipts if receipt.receipt_id.strip())
    if not checked_evidence:
        kind = OutcomeLearningKind.MISSING_EVIDENCE
        summary = "post-outcome comparison lacks outcome evidence"
        repair = "attach outcome evidence before memory learning"
        checked_evidence = ("missing-outcome-evidence",)
    elif _normalized(expected_state) == _normalized(actual_state):
        kind = OutcomeLearningKind.EXPECTATION_MATCHED
        summary = "post-outcome comparison matched expected state"
        repair = ""
    elif _governance_verdict_drift(shadow_receipts):
        kind = OutcomeLearningKind.GOVERNANCE_DRIFT
        summary = "post-outcome comparison found governance verdict drift"
        repair = "review shadow and governance verdict lineage"
    elif any("repair" in str(value).lower() for value in actual_state.values()):
        kind = OutcomeLearningKind.REPAIR_INCOMPLETE
        summary = "post-outcome comparison found unresolved repair residue"
        repair = "keep repair item open until follow-up evidence closes it"
    else:
        kind = OutcomeLearningKind.EXPECTATION_MISMATCH
        summary = "post-outcome comparison differed from expected state"
        repair = "record mismatch as governed learning candidate"

    candidate_id = stable_identifier(
        "inceptadive-outcome-learning",
        {
            "request_id": request_id,
            "kind": kind.value,
            "expected": _normalized(expected_state),
            "actual": _normalized(actual_state),
            "receipt_ids": receipt_ids or ("no-shadow-receipt",),
            "evidence_refs": checked_evidence,
        },
    )
    return InceptaDiveOutcomeLearningCandidate(
        candidate_id=candidate_id,
        request_id=request_id,
        kind=kind,
        summary=summary,
        evidence_refs=checked_evidence,
        source_receipt_ids=receipt_ids or ("no-shadow-receipt",),
        recommended_repair=repair,
    )


def _normalized(value: Mapping[str, object]) -> tuple[tuple[str, str], ...]:
    return tuple(sorted((str(key), str(item)) for key, item in value.items()))


def _governance_verdict_drift(receipts: Sequence[ShadowReceipt]) -> bool:
    return any(
        receipt.governance_verdict not in {"not_evaluated", "", receipt.shadow_verdict.value}
        for receipt in receipts
    )
