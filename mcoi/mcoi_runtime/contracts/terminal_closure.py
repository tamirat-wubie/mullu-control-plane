"""Purpose: terminal command closure certificate contracts.
Governance scope: final command disposition after verification, compensation,
accepted risk, or review escalation.
Dependencies: shared contract base helpers.
Invariants:
  - Terminal closure has exactly one explicit disposition.
  - Every closure carries evidence references.
  - Compensation closure references compensation outcome.
  - Accepted-risk closure references accepted risk and case.
  - Review closure references a case.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from ._base import (
    ContractRecord,
    freeze_value,
    require_datetime_text,
    require_non_empty_text,
    require_non_empty_tuple,
)


class TerminalClosureDisposition(StrEnum):
    """Final governed disposition for an effect-bearing command."""

    COMMITTED = "committed"
    COMPENSATED = "compensated"
    ACCEPTED_RISK = "accepted_risk"
    REQUIRES_REVIEW = "requires_review"


@dataclass(frozen=True, slots=True)
class TerminalClosureCertificate(ContractRecord):
    """Final certificate binding command closure to proof surfaces."""

    certificate_id: str
    command_id: str
    execution_id: str
    disposition: TerminalClosureDisposition
    verification_result_id: str
    effect_reconciliation_id: str
    evidence_refs: tuple[str, ...]
    closed_at: str
    response_closure_ref: str | None = None
    memory_entry_id: str | None = None
    compensation_outcome_id: str | None = None
    accepted_risk_id: str | None = None
    case_id: str | None = None
    graph_refs: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "certificate_id",
            "command_id",
            "execution_id",
            "verification_result_id",
            "effect_reconciliation_id",
        ):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        if not isinstance(self.disposition, TerminalClosureDisposition):
            raise ValueError("disposition must be a TerminalClosureDisposition value")
        object.__setattr__(self, "evidence_refs", require_non_empty_tuple(self.evidence_refs, "evidence_refs"))
        for evidence_ref in self.evidence_refs:
            require_non_empty_text(evidence_ref, "evidence_refs element")
        object.__setattr__(self, "closed_at", require_datetime_text(self.closed_at, "closed_at"))
        for field_name in (
            "response_closure_ref",
            "memory_entry_id",
            "compensation_outcome_id",
            "accepted_risk_id",
            "case_id",
        ):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, require_non_empty_text(value, field_name))
        if not isinstance(self.graph_refs, tuple):
            object.__setattr__(self, "graph_refs", tuple(self.graph_refs))
        for graph_ref in self.graph_refs:
            require_non_empty_text(graph_ref, "graph_refs element")
        _validate_terminal_requirements(self)
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


def _validate_terminal_requirements(certificate: TerminalClosureCertificate) -> None:
    disposition = certificate.disposition
    if disposition is TerminalClosureDisposition.COMMITTED:
        if certificate.compensation_outcome_id is not None or certificate.accepted_risk_id is not None:
            raise ValueError("committed closure cannot reference compensation or accepted risk")
    elif disposition is TerminalClosureDisposition.COMPENSATED:
        if certificate.compensation_outcome_id is None:
            raise ValueError("compensated closure requires compensation_outcome_id")
    elif disposition is TerminalClosureDisposition.ACCEPTED_RISK:
        if certificate.accepted_risk_id is None:
            raise ValueError("accepted-risk closure requires accepted_risk_id")
        if certificate.case_id is None:
            raise ValueError("accepted-risk closure requires case_id")
    elif disposition is TerminalClosureDisposition.REQUIRES_REVIEW:
        if certificate.case_id is None:
            raise ValueError("review closure requires case_id")
