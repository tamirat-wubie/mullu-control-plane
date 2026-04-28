"""Policy version registry endpoints.

Purpose: expose governed operator routes for immutable policy artifacts,
promotion, rollback, diff, and shadow governance comparison.
Governance scope: policy registry read/write surface only.
Dependencies: FastAPI, policy version registry, policy input contracts.
Invariants: artifacts remain immutable; promotion targets registered versions;
shadow evaluation never promotes a candidate version.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from mcoi_runtime.app.routers.deps import deps
from mcoi_runtime.governance.policy.engine import PolicyInput
from mcoi_runtime.governance.policy.versioning import (
    PolicyArtifact,
    ShadowGovernanceEvaluator,
    VersionedPolicyRule,
)

router = APIRouter()


class PolicyRuleRequest(BaseModel):
    rule_id: str
    description: str
    condition: str
    action: str


class PolicyArtifactRequest(BaseModel):
    policy_id: str
    version: str
    rules: list[PolicyRuleRequest] = Field(default_factory=list)


class ShadowPolicyInputRequest(BaseModel):
    subject_id: str
    goal_id: str
    blocked_knowledge_ids: list[str] = Field(default_factory=list)
    missing_capability_ids: list[str] = Field(default_factory=list)
    requires_operator_review: bool = False
    has_write_effects: bool = True


class ShadowEvaluationRequest(BaseModel):
    policy_input: ShadowPolicyInputRequest


def _artifact_to_dict(artifact: PolicyArtifact) -> dict[str, Any]:
    return {
        "policy_id": artifact.policy_id,
        "version": artifact.version,
        "artifact_hash": artifact.artifact_hash,
        "created_at": artifact.created_at,
        "rules": [
            {
                "rule_id": rule.rule_id,
                "description": rule.description,
                "condition": rule.condition,
                "action": rule.action,
            }
            for rule in artifact.rules
        ],
    }


def _registry() -> Any:
    return deps.policy_version_registry


@router.post("/api/v1/policies/{policy_id}/versions")
def register_policy_version(policy_id: str, req: PolicyArtifactRequest) -> dict[str, Any]:
    """Register an immutable policy version artifact."""
    deps.metrics.inc("requests_governed")
    if req.policy_id != policy_id:
        raise HTTPException(400, detail={
            "error": "policy id mismatch",
            "error_code": "policy_id_mismatch",
            "governed": True,
        })
    try:
        artifact = PolicyArtifact.create(
            policy_id=req.policy_id,
            version=req.version,
            rules=tuple(
                VersionedPolicyRule(
                    rule_id=rule.rule_id,
                    description=rule.description,
                    condition=rule.condition,
                    action=rule.action,  # type: ignore[arg-type]
                )
                for rule in req.rules
            ),
            created_at=deps._clock(),
        )
        stored = _registry().register(artifact)
    except ValueError as exc:
        raise HTTPException(400, detail={
            "error": "policy version registration failed",
            "error_code": "policy_version_registration_failed",
            "reason": str(exc),
            "governed": True,
        }) from exc

    deps.audit_trail.record(
        action="policy.version.register",
        actor_id="api",
        tenant_id="system",
        target=f"{policy_id}:{req.version}",
        outcome="success",
        detail={"artifact_hash": stored.artifact_hash},
    )
    return {"artifact": _artifact_to_dict(stored), "governed": True}


@router.get("/api/v1/policies/{policy_id}/versions/{version}")
def get_policy_version(policy_id: str, version: str) -> dict[str, Any]:
    """Fetch a registered policy version artifact."""
    deps.metrics.inc("requests_governed")
    artifact = _registry().get_version(policy_id, version)
    if artifact is None:
        raise HTTPException(404, detail={
            "error": "policy version not found",
            "error_code": "policy_version_not_found",
            "governed": True,
        })
    return {"artifact": _artifact_to_dict(artifact), "governed": True}


@router.post("/api/v1/policies/{policy_id}/versions/{version}/promote")
def promote_policy_version(policy_id: str, version: str) -> dict[str, Any]:
    """Promote a registered policy version to active."""
    deps.metrics.inc("requests_governed")
    try:
        artifact = _registry().promote(policy_id, version)
    except ValueError as exc:
        raise HTTPException(400, detail={
            "error": "policy version promotion failed",
            "error_code": "policy_version_promotion_failed",
            "reason": str(exc),
            "governed": True,
        }) from exc
    deps.audit_trail.record(
        action="policy.version.promote",
        actor_id="api",
        tenant_id="system",
        target=f"{policy_id}:{version}",
        outcome="success",
    )
    return {"active": _artifact_to_dict(artifact), "governed": True}


@router.post("/api/v1/policies/{policy_id}/rollback")
def rollback_policy_version(policy_id: str) -> dict[str, Any]:
    """Rollback to the previous active registered policy version."""
    deps.metrics.inc("requests_governed")
    try:
        artifact = _registry().rollback(policy_id)
    except ValueError as exc:
        raise HTTPException(400, detail={
            "error": "policy version rollback failed",
            "error_code": "policy_version_rollback_failed",
            "reason": str(exc),
            "governed": True,
        }) from exc
    deps.audit_trail.record(
        action="policy.version.rollback",
        actor_id="api",
        tenant_id="system",
        target=f"{policy_id}:{artifact.version}",
        outcome="success",
    )
    return {"active": _artifact_to_dict(artifact), "governed": True}


@router.get("/api/v1/policies/{policy_id}/diff")
def diff_policy_versions(policy_id: str, from_version: str, to_version: str) -> dict[str, Any]:
    """Return a deterministic diff between two policy versions."""
    deps.metrics.inc("requests_governed")
    try:
        diff = _registry().diff(policy_id, from_version, to_version)
    except ValueError as exc:
        raise HTTPException(400, detail={
            "error": "policy version diff failed",
            "error_code": "policy_version_diff_failed",
            "reason": str(exc),
            "governed": True,
        }) from exc
    return {
        "diff": {
            "policy_id": diff.policy_id,
            "from_version": diff.from_version,
            "to_version": diff.to_version,
            "changed": diff.changed,
            "rule_diffs": [
                {
                    "rule_id": rule_diff.rule_id,
                    "change": rule_diff.change,
                    "before": rule_diff.before,
                    "after": rule_diff.after,
                }
                for rule_diff in diff.rule_diffs
            ],
        },
        "governed": True,
    }


@router.post("/api/v1/policies/{policy_id}/shadow/{shadow_version}")
def shadow_policy_version(
    policy_id: str,
    shadow_version: str,
    req: ShadowEvaluationRequest,
) -> dict[str, Any]:
    """Compare the active policy version with a shadow candidate."""
    deps.metrics.inc("requests_governed")
    evaluator = ShadowGovernanceEvaluator(_registry())
    try:
        result = evaluator.evaluate(
            PolicyInput(
                subject_id=req.policy_input.subject_id,
                goal_id=req.policy_input.goal_id,
                issued_at=deps._clock(),
                blocked_knowledge_ids=tuple(req.policy_input.blocked_knowledge_ids),
                missing_capability_ids=tuple(req.policy_input.missing_capability_ids),
                requires_operator_review=req.policy_input.requires_operator_review,
                has_write_effects=req.policy_input.has_write_effects,
            ),
            policy_id=policy_id,
            shadow_version=shadow_version,
        )
    except ValueError as exc:
        raise HTTPException(400, detail={
            "error": "policy shadow evaluation failed",
            "error_code": "policy_shadow_evaluation_failed",
            "reason": str(exc),
            "governed": True,
        }) from exc
    return {
        "result": {
            "policy_id": result.policy_id,
            "active_version": result.active_version,
            "shadow_version": result.shadow_version,
            "active_status": result.active_status,
            "shadow_status": result.shadow_status,
            "verdict_changed": result.verdict_changed,
            "active_reason_codes": list(result.active_reason_codes),
            "shadow_reason_codes": list(result.shadow_reason_codes),
            "promoted": result.promoted,
        },
        "governed": True,
    }
