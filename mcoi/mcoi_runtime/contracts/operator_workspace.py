"""Purpose: UI / operator workspace runtime contracts.
Governance scope: typed descriptors for workspace views, panels, queues,
    worklist items, operator actions, decisions, snapshots, violations,
    assessments, and closure reports.
Dependencies: _base contract utilities.
Invariants:
  - Every workspace references a tenant.
  - Queues are scoped to operator visibility.
  - All outputs are frozen.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

from ._base import (
    ContractRecord,
    freeze_value,
    require_datetime_text,
    require_non_empty_text,
    require_non_negative_int,
    require_unit_float,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class WorkspaceStatus(Enum):
    """Status of a workspace view or panel."""
    ACTIVE = "active"
    DRAFT = "draft"
    SUSPENDED = "suspended"
    RETIRED = "retired"


class PanelKind(Enum):
    """Kind of workspace panel."""
    QUEUE = "queue"
    DASHBOARD = "dashboard"
    REVIEW = "review"
    APPROVAL = "approval"
    INVESTIGATION = "investigation"


class QueueStatus(Enum):
    """Status of a queue item."""
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ESCALATED = "escalated"


class ViewDisposition(Enum):
    """Disposition of a workspace view."""
    OPEN = "open"
    FILTERED = "filtered"
    PINNED = "pinned"
    ARCHIVED = "archived"


class OperatorActionStatus(Enum):
    """Status of an operator action."""
    INITIATED = "initiated"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkspaceScope(Enum):
    """Scope of workspace visibility."""
    TENANT = "tenant"
    WORKSPACE = "workspace"
    TEAM = "team"
    PERSONAL = "personal"
    EXECUTIVE = "executive"
    GLOBAL = "global"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class WorkspaceView(ContractRecord):
    """A workspace view for an operator."""

    view_id: str = ""
    tenant_id: str = ""
    operator_ref: str = ""
    display_name: str = ""
    scope: WorkspaceScope = WorkspaceScope.PERSONAL
    disposition: ViewDisposition = ViewDisposition.OPEN
    status: WorkspaceStatus = WorkspaceStatus.ACTIVE
    panel_count: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "view_id", require_non_empty_text(self.view_id, "view_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "operator_ref", require_non_empty_text(self.operator_ref, "operator_ref"))
        object.__setattr__(self, "display_name", require_non_empty_text(self.display_name, "display_name"))
        if not isinstance(self.scope, WorkspaceScope):
            raise ValueError("scope must be a WorkspaceScope")
        if not isinstance(self.disposition, ViewDisposition):
            raise ValueError("disposition must be a ViewDisposition")
        if not isinstance(self.status, WorkspaceStatus):
            raise ValueError("status must be a WorkspaceStatus")
        object.__setattr__(self, "panel_count", require_non_negative_int(self.panel_count, "panel_count"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class WorkspacePanel(ContractRecord):
    """A panel within a workspace view."""

    panel_id: str = ""
    view_id: str = ""
    tenant_id: str = ""
    display_name: str = ""
    kind: PanelKind = PanelKind.QUEUE
    target_runtime: str = ""
    item_count: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "panel_id", require_non_empty_text(self.panel_id, "panel_id"))
        object.__setattr__(self, "view_id", require_non_empty_text(self.view_id, "view_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "display_name", require_non_empty_text(self.display_name, "display_name"))
        if not isinstance(self.kind, PanelKind):
            raise ValueError("kind must be a PanelKind")
        object.__setattr__(self, "target_runtime", require_non_empty_text(self.target_runtime, "target_runtime"))
        object.__setattr__(self, "item_count", require_non_negative_int(self.item_count, "item_count"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class QueueRecord(ContractRecord):
    """A queue entry for operator processing."""

    queue_id: str = ""
    panel_id: str = ""
    tenant_id: str = ""
    source_ref: str = ""
    source_runtime: str = ""
    assignee_ref: str = ""
    priority: int = 0
    status: QueueStatus = QueueStatus.PENDING
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "queue_id", require_non_empty_text(self.queue_id, "queue_id"))
        object.__setattr__(self, "panel_id", require_non_empty_text(self.panel_id, "panel_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "source_ref", require_non_empty_text(self.source_ref, "source_ref"))
        object.__setattr__(self, "source_runtime", require_non_empty_text(self.source_runtime, "source_runtime"))
        object.__setattr__(self, "assignee_ref", require_non_empty_text(self.assignee_ref, "assignee_ref"))
        object.__setattr__(self, "priority", require_non_negative_int(self.priority, "priority"))
        if not isinstance(self.status, QueueStatus):
            raise ValueError("status must be a QueueStatus")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class WorklistItem(ContractRecord):
    """A worklist item for operator attention."""

    item_id: str = ""
    tenant_id: str = ""
    operator_ref: str = ""
    source_ref: str = ""
    source_runtime: str = ""
    title: str = ""
    priority: int = 0
    status: QueueStatus = QueueStatus.PENDING
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "item_id", require_non_empty_text(self.item_id, "item_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "operator_ref", require_non_empty_text(self.operator_ref, "operator_ref"))
        object.__setattr__(self, "source_ref", require_non_empty_text(self.source_ref, "source_ref"))
        object.__setattr__(self, "source_runtime", require_non_empty_text(self.source_runtime, "source_runtime"))
        object.__setattr__(self, "title", require_non_empty_text(self.title, "title"))
        object.__setattr__(self, "priority", require_non_negative_int(self.priority, "priority"))
        if not isinstance(self.status, QueueStatus):
            raise ValueError("status must be a QueueStatus")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class OperatorAction(ContractRecord):
    """An action taken by an operator."""

    action_id: str = ""
    tenant_id: str = ""
    operator_ref: str = ""
    target_ref: str = ""
    target_runtime: str = ""
    action_name: str = ""
    status: OperatorActionStatus = OperatorActionStatus.INITIATED
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "action_id", require_non_empty_text(self.action_id, "action_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "operator_ref", require_non_empty_text(self.operator_ref, "operator_ref"))
        object.__setattr__(self, "target_ref", require_non_empty_text(self.target_ref, "target_ref"))
        object.__setattr__(self, "target_runtime", require_non_empty_text(self.target_runtime, "target_runtime"))
        object.__setattr__(self, "action_name", require_non_empty_text(self.action_name, "action_name"))
        if not isinstance(self.status, OperatorActionStatus):
            raise ValueError("status must be an OperatorActionStatus")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class WorkspaceDecision(ContractRecord):
    """A decision made through workspace interaction."""

    decision_id: str = ""
    tenant_id: str = ""
    operator_ref: str = ""
    action_id: str = ""
    disposition: str = ""
    reason: str = ""
    decided_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision_id", require_non_empty_text(self.decision_id, "decision_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "operator_ref", require_non_empty_text(self.operator_ref, "operator_ref"))
        object.__setattr__(self, "action_id", require_non_empty_text(self.action_id, "action_id"))
        object.__setattr__(self, "disposition", require_non_empty_text(self.disposition, "disposition"))
        require_datetime_text(self.decided_at, "decided_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class WorkspaceSnapshot(ContractRecord):
    """Point-in-time snapshot of workspace state."""

    snapshot_id: str = ""
    tenant_id: str = ""
    total_views: int = 0
    active_views: int = 0
    total_panels: int = 0
    total_queue_items: int = 0
    pending_queue_items: int = 0
    total_worklist_items: int = 0
    total_actions: int = 0
    captured_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_views", require_non_negative_int(self.total_views, "total_views"))
        object.__setattr__(self, "active_views", require_non_negative_int(self.active_views, "active_views"))
        object.__setattr__(self, "total_panels", require_non_negative_int(self.total_panels, "total_panels"))
        object.__setattr__(self, "total_queue_items", require_non_negative_int(self.total_queue_items, "total_queue_items"))
        object.__setattr__(self, "pending_queue_items", require_non_negative_int(self.pending_queue_items, "pending_queue_items"))
        object.__setattr__(self, "total_worklist_items", require_non_negative_int(self.total_worklist_items, "total_worklist_items"))
        object.__setattr__(self, "total_actions", require_non_negative_int(self.total_actions, "total_actions"))
        require_datetime_text(self.captured_at, "captured_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class WorkspaceViolation(ContractRecord):
    """A workspace violation."""

    violation_id: str = ""
    tenant_id: str = ""
    operation: str = ""
    reason: str = ""
    detected_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "violation_id", require_non_empty_text(self.violation_id, "violation_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "operation", require_non_empty_text(self.operation, "operation"))
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))
        require_datetime_text(self.detected_at, "detected_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class WorkspaceAssessment(ContractRecord):
    """An assessment of workspace health."""

    assessment_id: str = ""
    tenant_id: str = ""
    total_views: int = 0
    active_views: int = 0
    queue_depth: int = 0
    pending_rate: float = 0.0
    total_violations: int = 0
    assessed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "assessment_id", require_non_empty_text(self.assessment_id, "assessment_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_views", require_non_negative_int(self.total_views, "total_views"))
        object.__setattr__(self, "active_views", require_non_negative_int(self.active_views, "active_views"))
        object.__setattr__(self, "queue_depth", require_non_negative_int(self.queue_depth, "queue_depth"))
        object.__setattr__(self, "pending_rate", require_unit_float(self.pending_rate, "pending_rate"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.assessed_at, "assessed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class WorkspaceClosureReport(ContractRecord):
    """Closure report for workspace."""

    report_id: str = ""
    tenant_id: str = ""
    total_views: int = 0
    total_panels: int = 0
    total_queue_items: int = 0
    total_worklist_items: int = 0
    total_actions: int = 0
    total_violations: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_views", require_non_negative_int(self.total_views, "total_views"))
        object.__setattr__(self, "total_panels", require_non_negative_int(self.total_panels, "total_panels"))
        object.__setattr__(self, "total_queue_items", require_non_negative_int(self.total_queue_items, "total_queue_items"))
        object.__setattr__(self, "total_worklist_items", require_non_negative_int(self.total_worklist_items, "total_worklist_items"))
        object.__setattr__(self, "total_actions", require_non_negative_int(self.total_actions, "total_actions"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
