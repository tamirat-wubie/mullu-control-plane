"""Purpose: canonical contracts for governed workspace file operations.
Governance scope: workspace read, creation, edit, destructive mutation,
    authority mutation, protected artifact mutation, and preflight receipts.
Dependencies: shared contract base helpers and Python standard library enums.
Invariants:
  - File operations are classified before execution authority is considered.
  - Destructive and authority mutations do not gain execution authority here.
  - Protected governance artifacts require elevated authority.
  - Receipts expose bounded references and never raw file content.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from ._base import ContractRecord, freeze_value, require_non_empty_text, require_non_empty_tuple


class WorkspaceFileOperation(StrEnum):
    """Canonical operation classes for workspace file authority."""

    READ = "read"
    CREATE = "create"
    EDIT = "edit"
    APPLY_PATCH = "apply_patch"
    DIFF_PROPOSE = "diff_propose"
    PATCH_PREVIEW = "patch_preview"
    DELETE = "delete"
    MOVE_RENAME = "move_rename"
    CHMOD_PERMISSION = "chmod_permission"
    GOVERNANCE_ARTIFACT_MUTATION = "governance_artifact_mutation"


class WorkspaceFileRiskLevel(StrEnum):
    """Bounded workspace file risk levels."""

    LEVEL_0_READONLY_INSPECT = "level_0_readonly_inspect"
    LEVEL_1_CREATE_NEW_FILE = "level_1_create_new_file"
    LEVEL_2_EDIT_EXISTING_FILE = "level_2_edit_existing_file"
    LEVEL_3_DESTRUCTIVE_MUTATION = "level_3_destructive_mutation"
    LEVEL_4_GOVERNANCE_ARTIFACT_MUTATION = "level_4_governance_artifact_mutation"


class WorkspaceFileDecision(StrEnum):
    """Preflight decision for a requested workspace file operation."""

    ALLOW = "allow"
    REQUIRE_APPROVAL = "require_approval"
    PROPOSAL_ONLY = "proposal_only"
    BLOCK = "block"


class WorkspaceFileAutonomyMode(StrEnum):
    """Autonomy modes accepted by workspace file preflight."""

    AUTONOMOUS_LOCAL = "autonomous_local"
    BOUNDED_AUTONOMOUS = "bounded_autonomous"
    APPROVAL_REQUIRED = "approval_required"


def coerce_workspace_file_operation(value: WorkspaceFileOperation | str) -> WorkspaceFileOperation:
    """Return a WorkspaceFileOperation or raise a bounded validation error."""
    if isinstance(value, WorkspaceFileOperation):
        return value
    try:
        return WorkspaceFileOperation(str(value))
    except ValueError as exc:
        raise ValueError("operation must be a known workspace file operation") from exc


def coerce_workspace_file_autonomy_mode(value: WorkspaceFileAutonomyMode | str) -> WorkspaceFileAutonomyMode:
    """Return a WorkspaceFileAutonomyMode or raise a bounded validation error."""
    if isinstance(value, WorkspaceFileAutonomyMode):
        return value
    try:
        return WorkspaceFileAutonomyMode(str(value))
    except ValueError as exc:
        raise ValueError("autonomy_mode must be a known workspace file autonomy mode") from exc


@dataclass(frozen=True, slots=True)
class WorkspaceFilePreflightRequest(ContractRecord):
    """Input contract for one workspace file operation preflight."""

    request_id: str
    operation: WorkspaceFileOperation | str
    target_path: str
    actor_id: str
    purpose: str
    secondary_path: str = ""
    expected_diff_hash: str = ""
    autonomy_mode: WorkspaceFileAutonomyMode | str = WorkspaceFileAutonomyMode.AUTONOMOUS_LOCAL
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "request_id", require_non_empty_text(self.request_id, "request_id"))
        object.__setattr__(self, "operation", coerce_workspace_file_operation(self.operation))
        object.__setattr__(self, "target_path", require_non_empty_text(self.target_path, "target_path"))
        object.__setattr__(self, "actor_id", require_non_empty_text(self.actor_id, "actor_id"))
        object.__setattr__(self, "purpose", require_non_empty_text(self.purpose, "purpose"))
        if self.secondary_path:
            object.__setattr__(self, "secondary_path", require_non_empty_text(self.secondary_path, "secondary_path"))
        if self.expected_diff_hash:
            object.__setattr__(
                self,
                "expected_diff_hash",
                require_non_empty_text(self.expected_diff_hash, "expected_diff_hash"),
            )
        object.__setattr__(self, "autonomy_mode", coerce_workspace_file_autonomy_mode(self.autonomy_mode))
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class WorkspaceFilePreflightResult(ContractRecord):
    """Governed preflight receipt for a workspace file operation."""

    receipt_id: str
    request_id: str
    operation: WorkspaceFileOperation | str
    target_path: str
    decision: WorkspaceFileDecision | str
    risk_level: WorkspaceFileRiskLevel | str
    actor_id: str
    purpose: str
    autonomy_mode: WorkspaceFileAutonomyMode | str
    world_mutating: bool
    approval_required: bool
    sandbox_required: bool
    receipt_required: bool
    rollback_required: bool
    coordination_lock_key: str
    protected_path: bool
    protected_reason: str = ""
    secondary_path: str = ""
    required_evidence: tuple[str, ...] = ()
    forbidden_effects: tuple[str, ...] = ()
    allowed_capability_ids: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "receipt_id", require_non_empty_text(self.receipt_id, "receipt_id"))
        object.__setattr__(self, "request_id", require_non_empty_text(self.request_id, "request_id"))
        object.__setattr__(self, "operation", coerce_workspace_file_operation(self.operation))
        object.__setattr__(self, "target_path", require_non_empty_text(self.target_path, "target_path"))
        object.__setattr__(self, "decision", WorkspaceFileDecision(str(self.decision)))
        object.__setattr__(self, "risk_level", WorkspaceFileRiskLevel(str(self.risk_level)))
        object.__setattr__(self, "actor_id", require_non_empty_text(self.actor_id, "actor_id"))
        object.__setattr__(self, "purpose", require_non_empty_text(self.purpose, "purpose"))
        object.__setattr__(self, "autonomy_mode", coerce_workspace_file_autonomy_mode(self.autonomy_mode))
        if not isinstance(self.world_mutating, bool):
            raise ValueError("world_mutating must be a boolean")
        if not isinstance(self.approval_required, bool):
            raise ValueError("approval_required must be a boolean")
        if not isinstance(self.sandbox_required, bool):
            raise ValueError("sandbox_required must be a boolean")
        if not isinstance(self.receipt_required, bool):
            raise ValueError("receipt_required must be a boolean")
        if not isinstance(self.rollback_required, bool):
            raise ValueError("rollback_required must be a boolean")
        object.__setattr__(
            self,
            "coordination_lock_key",
            require_non_empty_text(self.coordination_lock_key, "coordination_lock_key"),
        )
        if not isinstance(self.protected_path, bool):
            raise ValueError("protected_path must be a boolean")
        if self.protected_reason:
            object.__setattr__(self, "protected_reason", require_non_empty_text(self.protected_reason, "protected_reason"))
        if self.secondary_path:
            object.__setattr__(self, "secondary_path", require_non_empty_text(self.secondary_path, "secondary_path"))
        object.__setattr__(self, "required_evidence", require_non_empty_tuple(self.required_evidence, "required_evidence"))
        object.__setattr__(self, "forbidden_effects", require_non_empty_tuple(self.forbidden_effects, "forbidden_effects"))
        object.__setattr__(self, "allowed_capability_ids", freeze_value(list(self.allowed_capability_ids)))
        object.__setattr__(self, "reasons", require_non_empty_tuple(self.reasons, "reasons"))
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


def workspace_file_operation_level(operation: WorkspaceFileOperation | str) -> WorkspaceFileRiskLevel:
    """Return the canonical risk level for an operation before path policy."""
    normalized = coerce_workspace_file_operation(operation)
    if normalized in {
        WorkspaceFileOperation.READ,
        WorkspaceFileOperation.DIFF_PROPOSE,
        WorkspaceFileOperation.PATCH_PREVIEW,
    }:
        return WorkspaceFileRiskLevel.LEVEL_0_READONLY_INSPECT
    if normalized is WorkspaceFileOperation.CREATE:
        return WorkspaceFileRiskLevel.LEVEL_1_CREATE_NEW_FILE
    if normalized in {WorkspaceFileOperation.EDIT, WorkspaceFileOperation.APPLY_PATCH}:
        return WorkspaceFileRiskLevel.LEVEL_2_EDIT_EXISTING_FILE
    if normalized in {
        WorkspaceFileOperation.DELETE,
        WorkspaceFileOperation.MOVE_RENAME,
        WorkspaceFileOperation.CHMOD_PERMISSION,
    }:
        return WorkspaceFileRiskLevel.LEVEL_3_DESTRUCTIVE_MUTATION
    return WorkspaceFileRiskLevel.LEVEL_4_GOVERNANCE_ARTIFACT_MUTATION


def workspace_file_capability_levels() -> tuple[dict[str, str], ...]:
    """Expose the canonical level map as JSON-safe records."""
    return (
        {
            "level": WorkspaceFileRiskLevel.LEVEL_0_READONLY_INSPECT.value,
            "operations": "read,diff_propose,patch_preview",
            "authority": "observation only",
        },
        {
            "level": WorkspaceFileRiskLevel.LEVEL_1_CREATE_NEW_FILE.value,
            "operations": "create",
            "authority": "state creation with receipt and rollback binding",
        },
        {
            "level": WorkspaceFileRiskLevel.LEVEL_2_EDIT_EXISTING_FILE.value,
            "operations": "edit,apply_patch",
            "authority": "state mutation through guarded patch capability",
        },
        {
            "level": WorkspaceFileRiskLevel.LEVEL_3_DESTRUCTIVE_MUTATION.value,
            "operations": "delete,move_rename,chmod_permission",
            "authority": "proposal only until elevated approval and rollback evidence exist",
        },
        {
            "level": WorkspaceFileRiskLevel.LEVEL_4_GOVERNANCE_ARTIFACT_MUTATION.value,
            "operations": "governance_artifact_mutation",
            "authority": "proposal only; protected governance spine requires elevated authority",
        },
    )
