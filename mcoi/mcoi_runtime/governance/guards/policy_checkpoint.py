"""Purpose: declare canonical governance policy checkpoints by execution phase.
Governance scope: guard-chain documentation, session enforcement checkpoints,
and review-visible drift detection.
Dependencies: content-safety stage constants and protected-variable monitors;
this module has no side effects.
Invariants:
  - Checkpoint identifiers are stable, non-empty, and unique.
  - HTTP guard-chain checkpoints preserve their documented guard order.
  - Session LLM checkpoints include adjacent output safety and PII redaction.
  - Protected checkpoints cannot be silently removed without test drift.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from mcoi_runtime.governance.guards.content_safety import (
    LAMBDA_INPUT_SAFETY,
    LAMBDA_OUTPUT_SAFETY,
)
from mcoi_runtime.governance.protected_variables import (
    ProtectedVariable,
    ProtectedVariableMonitor,
    ProtectionRule,
)


class PolicyCheckpointPhase(str, Enum):
    """Where a checkpoint runs relative to the governed operation."""

    PRE_DISPATCH = "pre_dispatch"
    DISPATCH = "dispatch"
    POST_DISPATCH = "post_dispatch"


class PolicyCheckpointSurface(str, Enum):
    """Runtime surface that owns the checkpoint."""

    HTTP_GUARD_CHAIN = "http_guard_chain"
    SESSION_ADJACENT = "session_adjacent"


@dataclass(frozen=True, slots=True)
class PolicyCheckpoint:
    """A named governance checkpoint in the request/operation lifecycle."""

    checkpoint_id: str
    phase: PolicyCheckpointPhase
    surface: PolicyCheckpointSurface
    enforcer: str
    blocks_on_fail: bool
    mutates_payload: bool = False
    emits_receipt: bool = False


HTTP_POLICY_CHECKPOINTS: tuple[PolicyCheckpoint, ...] = (
    PolicyCheckpoint("api_key", PolicyCheckpointPhase.PRE_DISPATCH, PolicyCheckpointSurface.HTTP_GUARD_CHAIN, "api_key_guard", True),
    PolicyCheckpoint("jwt", PolicyCheckpointPhase.PRE_DISPATCH, PolicyCheckpointSurface.HTTP_GUARD_CHAIN, "jwt_guard", True),
    PolicyCheckpoint("tenant", PolicyCheckpointPhase.PRE_DISPATCH, PolicyCheckpointSurface.HTTP_GUARD_CHAIN, "tenant_guard", True),
    PolicyCheckpoint("tenant_gating", PolicyCheckpointPhase.PRE_DISPATCH, PolicyCheckpointSurface.HTTP_GUARD_CHAIN, "tenant_gating_guard", True),
    PolicyCheckpoint("rbac", PolicyCheckpointPhase.PRE_DISPATCH, PolicyCheckpointSurface.HTTP_GUARD_CHAIN, "rbac_guard", True),
    PolicyCheckpoint(LAMBDA_INPUT_SAFETY, PolicyCheckpointPhase.PRE_DISPATCH, PolicyCheckpointSurface.HTTP_GUARD_CHAIN, "input_content_safety_guard", True),
    PolicyCheckpoint("temporal", PolicyCheckpointPhase.PRE_DISPATCH, PolicyCheckpointSurface.HTTP_GUARD_CHAIN, "temporal_guard", True),
    PolicyCheckpoint("rate_limit", PolicyCheckpointPhase.PRE_DISPATCH, PolicyCheckpointSurface.HTTP_GUARD_CHAIN, "rate_limit_guard", True),
    PolicyCheckpoint("budget", PolicyCheckpointPhase.PRE_DISPATCH, PolicyCheckpointSurface.HTTP_GUARD_CHAIN, "budget_guard", True),
)


SESSION_LLM_POLICY_CHECKPOINTS: tuple[PolicyCheckpoint, ...] = (
    PolicyCheckpoint("closed_check", PolicyCheckpointPhase.PRE_DISPATCH, PolicyCheckpointSurface.SESSION_ADJACENT, "GovernedSession._require_open", True),
    PolicyCheckpoint("policy", PolicyCheckpointPhase.PRE_DISPATCH, PolicyCheckpointSurface.SESSION_ADJACENT, "GovernedSession._check_policy", True),
    PolicyCheckpoint("tenant_gating", PolicyCheckpointPhase.PRE_DISPATCH, PolicyCheckpointSurface.SESSION_ADJACENT, "GovernedSession._check_tenant_gating", True),
    PolicyCheckpoint("rbac", PolicyCheckpointPhase.PRE_DISPATCH, PolicyCheckpointSurface.SESSION_ADJACENT, "GovernedSession._check_rbac", True),
    PolicyCheckpoint("rate_limit", PolicyCheckpointPhase.PRE_DISPATCH, PolicyCheckpointSurface.SESSION_ADJACENT, "GovernedSession._check_rate_limit", True),
    PolicyCheckpoint(LAMBDA_INPUT_SAFETY, PolicyCheckpointPhase.PRE_DISPATCH, PolicyCheckpointSurface.SESSION_ADJACENT, "GovernedSession._check_content_safety", True),
    PolicyCheckpoint("budget", PolicyCheckpointPhase.PRE_DISPATCH, PolicyCheckpointSurface.SESSION_ADJACENT, "GovernedSession._check_budget", True),
    PolicyCheckpoint("proof", PolicyCheckpointPhase.PRE_DISPATCH, PolicyCheckpointSurface.SESSION_ADJACENT, "GovernedSession._certify_proof", True, emits_receipt=True),
    PolicyCheckpoint("llm_call", PolicyCheckpointPhase.DISPATCH, PolicyCheckpointSurface.SESSION_ADJACENT, "llm_bridge.complete", True),
    PolicyCheckpoint(LAMBDA_OUTPUT_SAFETY, PolicyCheckpointPhase.POST_DISPATCH, PolicyCheckpointSurface.SESSION_ADJACENT, "evaluate_output_safety", True, mutates_payload=True),
    PolicyCheckpoint("pii_redaction", PolicyCheckpointPhase.POST_DISPATCH, PolicyCheckpointSurface.SESSION_ADJACENT, "evaluate_output_safety.pii_scanner", False, mutates_payload=True),
    PolicyCheckpoint("audit", PolicyCheckpointPhase.POST_DISPATCH, PolicyCheckpointSurface.SESSION_ADJACENT, "GovernedSession._record_audit", True),
)

PROTECTED_HTTP_CHECKPOINT_IDS: tuple[str, ...] = (
    "api_key",
    "jwt",
    "tenant",
    "tenant_gating",
    "rbac",
    LAMBDA_INPUT_SAFETY,
    "temporal",
    "rate_limit",
    "budget",
)

PROTECTED_SESSION_LLM_CHECKPOINT_IDS: tuple[str, ...] = (
    "closed_check",
    "policy",
    "tenant_gating",
    "rbac",
    "rate_limit",
    LAMBDA_INPUT_SAFETY,
    "budget",
    "proof",
    "llm_call",
    LAMBDA_OUTPUT_SAFETY,
    "pii_redaction",
    "audit",
)

_PROTECTED_CHECKPOINT_IDS_FIELD = "checkpoint_ids"


def checkpoint_ids(checkpoints: tuple[PolicyCheckpoint, ...]) -> tuple[str, ...]:
    """Return checkpoint identifiers in canonical order."""
    return tuple(checkpoint.checkpoint_id for checkpoint in checkpoints)


def assert_unique_checkpoint_ids(checkpoints: tuple[PolicyCheckpoint, ...]) -> None:
    """Raise ValueError when a checkpoint contract contains duplicate identifiers."""
    ids = checkpoint_ids(checkpoints)
    duplicates = sorted({checkpoint_id for checkpoint_id in ids if ids.count(checkpoint_id) > 1})
    if duplicates:
        raise ValueError("duplicate policy checkpoint ids: " + ", ".join(duplicates))


def assert_protected_checkpoint_ids(
    checkpoints: tuple[PolicyCheckpoint, ...],
    *,
    required_ids: tuple[str, ...],
    surface_name: str,
) -> None:
    """Raise ValueError when a protected checkpoint is missing from a surface."""
    monitor = ProtectedVariableMonitor()
    monitor.register(
        ProtectedVariable(
            name=_PROTECTED_CHECKPOINT_IDS_FIELD,
            rule=ProtectionRule.REQUIRED_SUPERSET,
            required_members=required_ids,
        )
    )
    report = monitor.check(
        {},
        {_PROTECTED_CHECKPOINT_IDS_FIELD: checkpoint_ids(checkpoints)},
    )
    if not report.ok:
        reason = report.violations[0].reason
        raise ValueError(f"missing protected policy checkpoint ids for {surface_name}: {reason}")
