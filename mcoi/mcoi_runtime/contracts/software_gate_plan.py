"""Purpose: typed software quality gate planning contracts.
Governance scope: ordered validation gates, command intent, blast-radius
    evidence, rollback/review obligations, and full-suite escalation.
Dependencies: shared contract utilities, dataclasses, enum, and typing.
Invariants:
  - Every planned gate has an explicit id, tier, command, reason, and target.
  - Gate order is preserved by the immutable tuple on SoftwareGatePlan.
  - Full-suite escalation is explicit and causally justified.
  - Skipped gates are named so missing coverage is visible.
  - Gate plans are planning receipts only; they do not execute commands.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from ._base import (
    ContractRecord,
    freeze_value,
    require_non_empty_text,
    require_non_negative_int,
)


class GateExecutionTier(StrEnum):
    """Relative cost/latency tier for ordered gate execution."""

    STATIC = "static"
    FAST = "fast"
    TARGETED = "targeted"
    INTEGRATION = "integration"
    RELEASE = "release"


def _freeze_text_tuple(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    frozen_values = freeze_value(list(values))
    if not isinstance(frozen_values, tuple):
        raise ValueError(f"{field_name} must be a tuple of strings")
    for index, item in enumerate(frozen_values):
        require_non_empty_text(item, f"{field_name}[{index}]")
    return frozen_values


@dataclass(frozen=True, slots=True)
class PlannedSoftwareGate(ContractRecord):
    """One ordered quality gate selected for a software request."""

    gate_id: str
    tier: GateExecutionTier
    command: tuple[str, ...]
    reason: str
    target_refs: tuple[str, ...]
    order: int
    required: bool = True
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "gate_id", require_non_empty_text(self.gate_id, "gate_id"))
        if not isinstance(self.tier, GateExecutionTier):
            raise ValueError("tier must be a GateExecutionTier")
        command = _freeze_text_tuple(tuple(self.command), "command")
        if not command:
            raise ValueError("command must contain at least one item")
        object.__setattr__(self, "command", command)
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))
        target_refs = _freeze_text_tuple(tuple(self.target_refs), "target_refs")
        if not target_refs:
            raise ValueError("target_refs must contain at least one item")
        object.__setattr__(self, "target_refs", target_refs)
        object.__setattr__(self, "order", require_non_negative_int(self.order, "order"))
        if not isinstance(self.required, bool):
            raise ValueError("required must be a bool")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class SoftwareGatePlan(ContractRecord):
    """Ordered validation plan for one bounded software request."""

    plan_id: str
    repository: str
    commit_sha: str
    mode: str
    blast_radius: str
    affected_files: tuple[str, ...]
    gates: tuple[PlannedSoftwareGate, ...]
    skipped_gate_ids: tuple[str, ...] = ()
    full_suite_required: bool = False
    evidence_refs: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "plan_id", require_non_empty_text(self.plan_id, "plan_id"))
        object.__setattr__(self, "repository", require_non_empty_text(self.repository, "repository"))
        object.__setattr__(self, "commit_sha", require_non_empty_text(self.commit_sha, "commit_sha"))
        object.__setattr__(self, "mode", require_non_empty_text(self.mode, "mode"))
        object.__setattr__(self, "blast_radius", require_non_empty_text(self.blast_radius, "blast_radius"))
        affected_files = _freeze_text_tuple(tuple(self.affected_files), "affected_files")
        if not affected_files:
            raise ValueError("affected_files must contain at least one item")
        object.__setattr__(self, "affected_files", affected_files)
        if not self.gates:
            raise ValueError("gates must contain at least one item")
        for gate in self.gates:
            if not isinstance(gate, PlannedSoftwareGate):
                raise ValueError("gates must contain PlannedSoftwareGate records")
        object.__setattr__(self, "gates", freeze_value(list(self.gates)))
        object.__setattr__(self, "skipped_gate_ids", _freeze_text_tuple(tuple(self.skipped_gate_ids), "skipped_gate_ids"))
        if not isinstance(self.full_suite_required, bool):
            raise ValueError("full_suite_required must be a bool")
        object.__setattr__(self, "evidence_refs", _freeze_text_tuple(tuple(self.evidence_refs), "evidence_refs"))
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
