"""Purpose: runtime-only read-after-write reconciliation contracts.
Governance scope: nested-mind observation verification after live submission.
Dependencies: shared contract helpers and connector result identifiers.
Invariants:
  - Reconciliation is read-only and never admits semantic/procedural memory.
  - Projection and audit connector results are always recorded.
  - Commit and history expectations bind to the VERIFIED commit witness.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping, Sequence

from ._base import ContractRecord, freeze_value, require_datetime_text, require_non_empty_text


class NestedMindObservationReconciliationStatus(StrEnum):
    VERIFIED = "verified"
    NOT_VISIBLE = "not_visible"
    HISTORY_MISMATCH = "history_mismatch"
    PROJECTION_MISMATCH = "projection_mismatch"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class NestedMindObservationReconciliationReport(ContractRecord):
    report_id: str
    plan_id: str
    commit_witness_id: str
    mind_id: str
    mullu_receipt_hash: str
    expected_commit_hash: str
    expected_history_hash: str
    projection_connector_result_id: str
    audit_connector_result_id: str
    replay_connector_result_id: str | None
    status: NestedMindObservationReconciliationStatus
    checked_at: str
    blockers: Sequence[str] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "report_id",
            "plan_id",
            "commit_witness_id",
            "mind_id",
            "mullu_receipt_hash",
            "expected_commit_hash",
            "expected_history_hash",
            "projection_connector_result_id",
            "audit_connector_result_id",
        ):
            object.__setattr__(
                self,
                field_name,
                require_non_empty_text(getattr(self, field_name), field_name),
            )
        if self.replay_connector_result_id is not None:
            object.__setattr__(
                self,
                "replay_connector_result_id",
                require_non_empty_text(self.replay_connector_result_id, "replay_connector_result_id"),
            )
        if not isinstance(self.status, NestedMindObservationReconciliationStatus):
            raise ValueError("status must be a NestedMindObservationReconciliationStatus value")
        object.__setattr__(self, "checked_at", require_datetime_text(self.checked_at, "checked_at"))
        object.__setattr__(self, "blockers", tuple(self.blockers))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))
