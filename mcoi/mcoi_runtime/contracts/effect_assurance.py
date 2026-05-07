"""Purpose: effect assurance contracts for governed reality-changing execution.
Governance scope: expected effects, observed effects, verification comparison,
and reconciliation closure.
Dependencies: shared contract base helpers and execution/verification semantics.
Invariants:
  - Every effect plan has at least one expected effect.
  - Every effect plan has at least one forbidden effect.
  - Observed effects must carry evidence references.
  - Reconciliation status is explicit and terminal for a comparison.
  - Actual effects are observation records, never assumptions.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from ._base import (
    ContractRecord,
    freeze_value,
    require_datetime_text,
    require_non_empty_text,
    require_non_empty_tuple,
)


class ReconciliationStatus(StrEnum):
    """Outcome of comparing expected effects against observed effects."""

    MATCH = "match"
    PARTIAL_MATCH = "partial_match"
    MISMATCH = "mismatch"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ExpectedEffect(ContractRecord):
    """One pre-dispatch effect that must or may be observed after execution."""

    effect_id: str
    name: str
    target_ref: str
    required: bool
    verification_method: str
    expected_value: Any | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "effect_id", require_non_empty_text(self.effect_id, "effect_id"))
        object.__setattr__(self, "name", require_non_empty_text(self.name, "name"))
        object.__setattr__(self, "target_ref", require_non_empty_text(self.target_ref, "target_ref"))
        if not isinstance(self.required, bool):
            raise ValueError("required must be a boolean")
        object.__setattr__(
            self,
            "verification_method",
            require_non_empty_text(self.verification_method, "verification_method"),
        )
        object.__setattr__(self, "expected_value", freeze_value(self.expected_value))


@dataclass(frozen=True, slots=True)
class EffectPlan(ContractRecord):
    """Pre-dispatch declaration of intended, forbidden, recovery, and graph effects."""

    effect_plan_id: str
    command_id: str
    tenant_id: str
    capability_id: str
    expected_effects: tuple[ExpectedEffect, ...]
    forbidden_effects: tuple[str, ...]
    rollback_plan_id: str | None
    compensation_plan_id: str | None
    graph_node_refs: tuple[str, ...]
    graph_edge_refs: tuple[str, ...]
    created_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "effect_plan_id", require_non_empty_text(self.effect_plan_id, "effect_plan_id"))
        object.__setattr__(self, "command_id", require_non_empty_text(self.command_id, "command_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "capability_id", require_non_empty_text(self.capability_id, "capability_id"))
        if not self.expected_effects:
            raise ValueError("expected_effects must contain at least one item")
        object.__setattr__(self, "expected_effects", require_non_empty_tuple(self.expected_effects, "expected_effects"))
        for effect in self.expected_effects:
            if not isinstance(effect, ExpectedEffect):
                raise ValueError("expected_effects must contain ExpectedEffect values")
        if not self.forbidden_effects:
            raise ValueError("forbidden_effects must contain at least one item")
        object.__setattr__(self, "forbidden_effects", require_non_empty_tuple(self.forbidden_effects, "forbidden_effects"))
        for effect_name in self.forbidden_effects:
            require_non_empty_text(effect_name, "forbidden_effects element")
        if self.rollback_plan_id is not None:
            object.__setattr__(
                self,
                "rollback_plan_id",
                require_non_empty_text(self.rollback_plan_id, "rollback_plan_id"),
            )
        if self.compensation_plan_id is not None:
            object.__setattr__(
                self,
                "compensation_plan_id",
                require_non_empty_text(self.compensation_plan_id, "compensation_plan_id"),
            )
        if not isinstance(self.graph_node_refs, tuple):
            object.__setattr__(self, "graph_node_refs", tuple(self.graph_node_refs))
        if not isinstance(self.graph_edge_refs, tuple):
            object.__setattr__(self, "graph_edge_refs", tuple(self.graph_edge_refs))
        for node_ref in self.graph_node_refs:
            require_non_empty_text(node_ref, "graph_node_refs element")
        for edge_ref in self.graph_edge_refs:
            require_non_empty_text(edge_ref, "graph_edge_refs element")
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))


@dataclass(frozen=True, slots=True)
class ObservedEffect(ContractRecord):
    """Post-dispatch fact collected from an observer, provider, or verifier."""

    effect_id: str
    name: str
    source: str
    observed_value: Any | None
    evidence_ref: str
    observed_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "effect_id", require_non_empty_text(self.effect_id, "effect_id"))
        object.__setattr__(self, "name", require_non_empty_text(self.name, "name"))
        object.__setattr__(self, "source", require_non_empty_text(self.source, "source"))
        object.__setattr__(self, "observed_value", freeze_value(self.observed_value))
        object.__setattr__(self, "evidence_ref", require_non_empty_text(self.evidence_ref, "evidence_ref"))
        object.__setattr__(self, "observed_at", require_datetime_text(self.observed_at, "observed_at"))


@dataclass(frozen=True, slots=True)
class EffectReconciliation(ContractRecord):
    """Terminal comparison record for one effect plan and observation set."""

    reconciliation_id: str
    command_id: str
    effect_plan_id: str
    status: ReconciliationStatus
    matched_effects: tuple[str, ...]
    missing_effects: tuple[str, ...]
    unexpected_effects: tuple[str, ...]
    verification_result_id: str | None
    case_id: str | None
    decided_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "reconciliation_id", require_non_empty_text(self.reconciliation_id, "reconciliation_id"))
        object.__setattr__(self, "command_id", require_non_empty_text(self.command_id, "command_id"))
        object.__setattr__(self, "effect_plan_id", require_non_empty_text(self.effect_plan_id, "effect_plan_id"))
        if not isinstance(self.status, ReconciliationStatus):
            raise ValueError("status must be a ReconciliationStatus value")
        for field_name in ("matched_effects", "missing_effects", "unexpected_effects"):
            values = getattr(self, field_name)
            if not isinstance(values, tuple):
                object.__setattr__(self, field_name, tuple(values))
            for value in getattr(self, field_name):
                require_non_empty_text(value, f"{field_name} element")
        if self.verification_result_id is not None:
            object.__setattr__(
                self,
                "verification_result_id",
                require_non_empty_text(self.verification_result_id, "verification_result_id"),
            )
        if self.case_id is not None:
            object.__setattr__(self, "case_id", require_non_empty_text(self.case_id, "case_id"))
        object.__setattr__(self, "decided_at", require_datetime_text(self.decided_at, "decided_at"))
