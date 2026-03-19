"""Purpose: canonical incident playbook contracts.
Governance scope: incident pattern matching, playbook descriptor, and execution record typing.
Dependencies: shared contract base helpers.
Invariants:
  - Playbooks are reviewed operational procedures for known incident patterns.
  - Pattern matching is deterministic for identical inputs.
  - Playbook execution is governed by review/approval/autonomy rules.
  - Outcomes feed back into telemetry and procedural confidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from ._base import ContractRecord, freeze_value, require_non_empty_text


class PlaybookStatus(StrEnum):
    DRAFT = "draft"
    REVIEWED = "reviewed"
    ACTIVE = "active"
    DEPRECATED = "deprecated"


class PatternMatchResult(StrEnum):
    MATCHED = "matched"
    NO_MATCH = "no_match"
    PARTIAL = "partial"


class PlaybookOutcome(StrEnum):
    RESOLVED = "resolved"
    PARTIALLY_RESOLVED = "partially_resolved"
    FAILED = "failed"
    BLOCKED = "blocked"
    ESCALATED = "escalated"


@dataclass(frozen=True, slots=True)
class IncidentPattern(ContractRecord):
    """A pattern that matches incidents to playbooks."""

    pattern_id: str
    failure_family: str
    source_type: str | None = None
    severity_min: str | None = None
    keyword_match: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "pattern_id", require_non_empty_text(self.pattern_id, "pattern_id"))
        object.__setattr__(self, "failure_family", require_non_empty_text(self.failure_family, "failure_family"))
        object.__setattr__(self, "keyword_match", freeze_value(list(self.keyword_match)))


@dataclass(frozen=True, slots=True)
class IncidentPlaybookDescriptor(ContractRecord):
    """A reviewed operational procedure for handling a known incident pattern."""

    playbook_id: str
    name: str
    description: str
    pattern: IncidentPattern
    status: PlaybookStatus
    steps: tuple[str, ...]
    recovery_action: str
    requires_review: bool = True
    requires_approval: bool = False
    review_id: str | None = None
    runbook_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "playbook_id", require_non_empty_text(self.playbook_id, "playbook_id"))
        object.__setattr__(self, "name", require_non_empty_text(self.name, "name"))
        object.__setattr__(self, "description", require_non_empty_text(self.description, "description"))
        if not isinstance(self.pattern, IncidentPattern):
            raise ValueError("pattern must be an IncidentPattern instance")
        if not isinstance(self.status, PlaybookStatus):
            raise ValueError("status must be a PlaybookStatus value")
        object.__setattr__(self, "steps", freeze_value(list(self.steps)))
        object.__setattr__(self, "recovery_action", require_non_empty_text(self.recovery_action, "recovery_action"))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))

    @property
    def is_executable(self) -> bool:
        return self.status in (PlaybookStatus.REVIEWED, PlaybookStatus.ACTIVE)


@dataclass(frozen=True, slots=True)
class IncidentMatchRecord(ContractRecord):
    """Result of matching an incident against known playbook patterns."""

    incident_id: str
    result: PatternMatchResult
    matched_playbook_id: str | None = None
    match_score: float = 0.0
    match_reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "incident_id", require_non_empty_text(self.incident_id, "incident_id"))
        if not isinstance(self.result, PatternMatchResult):
            raise ValueError("result must be a PatternMatchResult value")
        object.__setattr__(self, "match_reasons", freeze_value(list(self.match_reasons)))


@dataclass(frozen=True, slots=True)
class PlaybookExecutionRecord(ContractRecord):
    """Record of executing an incident playbook."""

    record_id: str
    playbook_id: str
    incident_id: str
    outcome: PlaybookOutcome
    steps_completed: int
    steps_total: int
    review_satisfied: bool
    approval_satisfied: bool
    started_at: str
    finished_at: str
    error_message: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "record_id", require_non_empty_text(self.record_id, "record_id"))
        object.__setattr__(self, "playbook_id", require_non_empty_text(self.playbook_id, "playbook_id"))
        object.__setattr__(self, "incident_id", require_non_empty_text(self.incident_id, "incident_id"))
        if not isinstance(self.outcome, PlaybookOutcome):
            raise ValueError("outcome must be a PlaybookOutcome value")
        object.__setattr__(self, "started_at", require_non_empty_text(self.started_at, "started_at"))
        object.__setattr__(self, "finished_at", require_non_empty_text(self.finished_at, "finished_at"))

    @property
    def succeeded(self) -> bool:
        return self.outcome is PlaybookOutcome.RESOLVED
