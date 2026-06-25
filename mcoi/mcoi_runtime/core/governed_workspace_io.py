"""Purpose: canonical governed workspace file operation preflight.
Governance scope: path policy, operation risk, approval, rollback, receipt,
    and protected artifact classification before workspace file execution.
Dependencies: workspace file contracts and protected path policy.
Invariants:
  - The preflight function is pure and deterministic for the same request.
  - This module never reads, writes, deletes, moves, or chmods files.
  - Unanchorable paths fail closed.
  - Destructive operations remain proposal-only in this capability layer.
"""

from __future__ import annotations

import hashlib

from mcoi_runtime.contracts.workspace_file_capability import (
    WorkspaceFileAutonomyMode,
    WorkspaceFileDecision,
    WorkspaceFileOperation,
    WorkspaceFilePreflightRequest,
    WorkspaceFilePreflightResult,
    WorkspaceFileRiskLevel,
    workspace_file_capability_levels,
    workspace_file_operation_level,
)
from mcoi_runtime.governance.protected_paths import (
    DEFAULT_GOVERNANCE_PROTECTED_PATHS,
    ProtectedPathMatch,
    ProtectedPathPolicy,
)


_READ_ONLY_OPERATIONS = frozenset(
    {
        WorkspaceFileOperation.READ,
        WorkspaceFileOperation.DIFF_PROPOSE,
        WorkspaceFileOperation.PATCH_PREVIEW,
    }
)
_PATCH_MUTATIONS = frozenset(
    {
        WorkspaceFileOperation.CREATE,
        WorkspaceFileOperation.EDIT,
        WorkspaceFileOperation.APPLY_PATCH,
    }
)
_DESTRUCTIVE_OPERATIONS = frozenset(
    {
        WorkspaceFileOperation.DELETE,
        WorkspaceFileOperation.MOVE_RENAME,
        WorkspaceFileOperation.CHMOD_PERMISSION,
    }
)
_NO_PROTECTED_PATHS = ProtectedPathPolicy()


def preflight_workspace_file_operation(
    request: WorkspaceFilePreflightRequest,
    *,
    protected_paths: ProtectedPathPolicy | None = DEFAULT_GOVERNANCE_PROTECTED_PATHS,
) -> WorkspaceFilePreflightResult:
    """Classify one workspace file operation before any file effect.

    Error contract:
      - Raises ValueError only for malformed typed request inputs.
      - Governance denials are encoded as BLOCK or PROPOSAL_ONLY results.
    """
    if not isinstance(request, WorkspaceFilePreflightRequest):
        raise ValueError("request must be a WorkspaceFilePreflightRequest")

    operation = request.operation
    path_verdict = (
        protected_paths.classify(request.target_path)
        if protected_paths is not None
        else _NO_PROTECTED_PATHS.classify(request.target_path)
    )
    normalized_path = path_verdict.path
    risk_level = _risk_level_with_path_policy(operation, path_verdict.protected)
    world_mutating = operation not in _READ_ONLY_OPERATIONS
    approval_required = _approval_required(
        operation=operation,
        protected_path=path_verdict.protected,
        autonomy_mode=request.autonomy_mode,
    )
    rollback_required = world_mutating
    sandbox_required = world_mutating
    allowed_capability_ids = _allowed_capability_ids(
        operation=operation,
        protected_path=path_verdict.protected,
        approval_required=approval_required,
    )
    decision = _decision(
        operation=operation,
        path_unnormalizable=path_verdict.match is ProtectedPathMatch.UNNORMALIZABLE,
        protected_path=path_verdict.protected,
        approval_required=approval_required,
    )
    reasons = _reasons(
        operation=operation,
        autonomy_mode=request.autonomy_mode,
        decision=decision,
        path_unnormalizable=path_verdict.match is ProtectedPathMatch.UNNORMALIZABLE,
        protected_path=path_verdict.protected,
        protected_reason=path_verdict.reason,
    )
    metadata = {
        "canonical_levels": workspace_file_capability_levels(),
        "operation_level": workspace_file_operation_level(operation).value,
        "autonomy_mode": request.autonomy_mode.value,
        "protected_path_match": path_verdict.match.value,
        "protected_path_pattern": path_verdict.matched_pattern,
        "preflight_is_not_execution_authority": True,
        **dict(request.metadata),
    }
    return WorkspaceFilePreflightResult(
        receipt_id=_receipt_id(request, normalized_path, decision),
        request_id=request.request_id,
        operation=operation,
        target_path=normalized_path,
        secondary_path=request.secondary_path,
        decision=decision,
        risk_level=risk_level,
        actor_id=request.actor_id,
        purpose=request.purpose,
        autonomy_mode=request.autonomy_mode,
        world_mutating=world_mutating,
        approval_required=approval_required,
        sandbox_required=sandbox_required,
        receipt_required=True,
        rollback_required=rollback_required,
        coordination_lock_key=_coordination_lock_key(normalized_path, request.secondary_path),
        protected_path=path_verdict.protected,
        protected_reason=path_verdict.reason,
        required_evidence=_required_evidence(operation, approval_required, rollback_required),
        forbidden_effects=_forbidden_effects(operation),
        allowed_capability_ids=allowed_capability_ids,
        reasons=reasons,
        metadata=metadata,
    )


def _risk_level_with_path_policy(
    operation: WorkspaceFileOperation,
    protected_path: bool,
) -> WorkspaceFileRiskLevel:
    if protected_path and operation not in _READ_ONLY_OPERATIONS:
        return WorkspaceFileRiskLevel.LEVEL_4_GOVERNANCE_ARTIFACT_MUTATION
    return workspace_file_operation_level(operation)


def _approval_required(
    *,
    operation: WorkspaceFileOperation,
    protected_path: bool,
    autonomy_mode: WorkspaceFileAutonomyMode,
) -> bool:
    if protected_path or operation in _DESTRUCTIVE_OPERATIONS or operation is WorkspaceFileOperation.GOVERNANCE_ARTIFACT_MUTATION:
        return True
    return autonomy_mode is WorkspaceFileAutonomyMode.APPROVAL_REQUIRED and operation not in _READ_ONLY_OPERATIONS


def _decision(
    *,
    operation: WorkspaceFileOperation,
    path_unnormalizable: bool,
    protected_path: bool,
    approval_required: bool,
) -> WorkspaceFileDecision:
    if path_unnormalizable:
        return WorkspaceFileDecision.BLOCK
    if operation in _DESTRUCTIVE_OPERATIONS or operation is WorkspaceFileOperation.GOVERNANCE_ARTIFACT_MUTATION:
        return WorkspaceFileDecision.PROPOSAL_ONLY
    if protected_path or approval_required:
        return WorkspaceFileDecision.REQUIRE_APPROVAL
    return WorkspaceFileDecision.ALLOW


def _allowed_capability_ids(
    *,
    operation: WorkspaceFileOperation,
    protected_path: bool,
    approval_required: bool,
) -> tuple[str, ...]:
    if protected_path or approval_required:
        return ()
    if operation in _READ_ONLY_OPERATIONS:
        return ("computer.filesystem.observe",)
    if operation in _PATCH_MUTATIONS:
        return ("computer.code.patch", "software_dev.change.run")
    return ()


def _required_evidence(
    operation: WorkspaceFileOperation,
    approval_required: bool,
    rollback_required: bool,
) -> tuple[str, ...]:
    evidence = [
        "target_path",
        "purpose",
        "risk_level",
        "protected_path_status",
        "coordination_lock_key",
        "workspace_file_preflight_receipt_id",
    ]
    if operation in _PATCH_MUTATIONS:
        evidence.extend(["unified_diff", "before_hash", "after_hash", "test_command_or_untested_mark"])
    if rollback_required:
        evidence.append("rollback_plan")
    if approval_required:
        evidence.append("approval_ref")
    return tuple(evidence)


def _forbidden_effects(operation: WorkspaceFileOperation) -> tuple[str, ...]:
    common = [
        "path_outside_workspace_written",
        "credential_file_read",
        "raw_secret_value_recorded",
        "receipt_without_redaction",
    ]
    if operation in _READ_ONLY_OPERATIONS:
        return tuple([*common, "workspace_file_written", "workspace_file_deleted", "permission_changed"])
    if operation in _PATCH_MUTATIONS:
        return tuple([*common, "protected_governance_file_mutated_without_approval", "destructive_mutation_without_rollback"])
    return tuple([*common, "destructive_mutation_executed_by_preflight", "permission_changed_without_elevated_authority"])


def _reasons(
    *,
    operation: WorkspaceFileOperation,
    autonomy_mode: WorkspaceFileAutonomyMode,
    decision: WorkspaceFileDecision,
    path_unnormalizable: bool,
    protected_path: bool,
    protected_reason: str,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if path_unnormalizable:
        reasons.append("path is not safely workspace-relative")
    if protected_path:
        reasons.append(protected_reason or "path is protected")
    if operation in _READ_ONLY_OPERATIONS:
        reasons.append("operation is observation only")
    elif operation in _PATCH_MUTATIONS:
        reasons.append("operation may proceed only through guarded patch or software-change capability")
    else:
        reasons.append("operation is proposal-only until elevated authority and rollback evidence exist")
    reasons.append(f"autonomy_mode:{autonomy_mode.value}")
    reasons.append(f"decision:{decision.value}")
    return tuple(reasons)


def _coordination_lock_key(target_path: str, secondary_path: str = "") -> str:
    material = target_path if not secondary_path else f"{target_path}->{secondary_path}"
    return f"workspace_file:{hashlib.sha256(material.encode('utf-8', errors='replace')).hexdigest()[:16]}"


def _receipt_id(
    request: WorkspaceFilePreflightRequest,
    normalized_path: str,
    decision: WorkspaceFileDecision,
) -> str:
    material = "|".join(
        (
            request.request_id,
            request.operation.value,
            normalized_path,
            request.secondary_path,
            request.actor_id,
            decision.value,
        )
    )
    digest = hashlib.sha256(material.encode("utf-8", errors="replace")).hexdigest()
    return f"workspace-file-preflight-{digest[:16]}"
