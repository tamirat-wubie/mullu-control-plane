"""Data governance endpoints: classify, policies, residency, privacy,
redaction, retention, evaluation."""
from __future__ import annotations

from typing import NoReturn

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from mcoi_runtime.app.routers._tenant_scope import enforce_tenant_scope, scoped_listing_tenant
from mcoi_runtime.app.routers.data._common import (
    _certify_action_proof,
    _data_error_detail,
    deps,
)
from mcoi_runtime.contracts.data_governance import (
    DataClassification,
    DataPolicy,
    DataRecord,
    DataViolation,
    GovernanceDecision,
    HandlingDecision,
    HandlingDisposition,
    PrivacyBasis,
    PrivacyRule,
    RedactionLevel,
    RedactionRule,
    ResidencyConstraint,
    ResidencyRegion,
    RetentionDisposition,
    RetentionRule,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError

router = APIRouter()


class DataClassifyRequest(BaseModel):
    data_id: str
    tenant_id: str
    classification: DataClassification = DataClassification.INTERNAL
    residency: ResidencyRegion = ResidencyRegion.GLOBAL
    privacy_basis: PrivacyBasis = PrivacyBasis.LEGITIMATE_INTEREST
    domain: str = ""
    source_id: str = ""


class DataPolicyRequest(BaseModel):
    policy_id: str
    tenant_id: str
    classification: DataClassification = DataClassification.INTERNAL
    disposition: HandlingDisposition = HandlingDisposition.DENY
    residency: ResidencyRegion = ResidencyRegion.GLOBAL
    scope_ref_id: str = ""
    description: str = ""


class ResidencyConstraintRequest(BaseModel):
    constraint_id: str
    tenant_id: str
    allowed_regions: list[str] = Field(default_factory=list)
    denied_regions: list[str] = Field(default_factory=list)


class PrivacyRuleRequest(BaseModel):
    rule_id: str
    tenant_id: str
    classification: DataClassification = DataClassification.PII
    required_basis: PrivacyBasis = PrivacyBasis.CONSENT
    scope_ref_id: str = ""
    description: str = ""


class RedactionRuleRequest(BaseModel):
    rule_id: str
    tenant_id: str
    classification: DataClassification = DataClassification.SENSITIVE
    redaction_level: RedactionLevel = RedactionLevel.FULL
    scope_ref_id: str = ""
    field_patterns: list[str] = Field(default_factory=list)


class RetentionRuleRequest(BaseModel):
    rule_id: str
    tenant_id: str
    classification: DataClassification = DataClassification.INTERNAL
    retention_days: int = 365
    disposition: RetentionDisposition = RetentionDisposition.DELETE
    scope_ref_id: str = ""


class DataHandlingEvaluationRequest(BaseModel):
    data_id: str
    operation: str
    target_region: ResidencyRegion | None = None


def _raise_data_governance_error(exc: RuntimeCoreInvariantError) -> NoReturn:
    """Map engine invariant failures to bounded HTTP errors."""
    message = str(exc)
    if "Duplicate" in message:
        raise HTTPException(
            409,
            detail=_data_error_detail(
                "data governance resource already exists",
                "data_governance_conflict",
            ),
        )
    if "Unknown data_id" in message:
        raise HTTPException(
            404,
            detail=_data_error_detail(
                "data record not found",
                "data_record_not_found",
            ),
        )
    raise HTTPException(
        400,
        detail=_data_error_detail(
            "invalid data governance request",
            "data_governance_validation_error",
        ),
    )


def _record_response(record: DataRecord) -> dict[str, object]:
    return {
        "data_id": record.data_id,
        "tenant_id": record.tenant_id,
        "classification": record.classification.value,
        "residency": record.residency.value,
        "privacy_basis": record.privacy_basis.value,
        "domain": record.domain,
        "source_id": record.source_id,
        "created_at": record.created_at,
    }


def _policy_response(policy: DataPolicy) -> dict[str, object]:
    return {
        "policy_id": policy.policy_id,
        "tenant_id": policy.tenant_id,
        "classification": policy.classification.value,
        "disposition": policy.disposition.value,
        "residency": policy.residency.value,
        "scope_ref_id": policy.scope_ref_id,
        "description": policy.description,
        "created_at": policy.created_at,
    }


def _residency_response(constraint: ResidencyConstraint) -> dict[str, object]:
    return {
        "constraint_id": constraint.constraint_id,
        "tenant_id": constraint.tenant_id,
        "allowed_regions": list(constraint.allowed_regions),
        "denied_regions": list(constraint.denied_regions),
        "created_at": constraint.created_at,
    }


def _privacy_rule_response(rule: PrivacyRule) -> dict[str, object]:
    return {
        "rule_id": rule.rule_id,
        "tenant_id": rule.tenant_id,
        "classification": rule.classification.value,
        "required_basis": rule.required_basis.value,
        "scope_ref_id": rule.scope_ref_id,
        "description": rule.description,
        "created_at": rule.created_at,
    }


def _redaction_rule_response(rule: RedactionRule) -> dict[str, object]:
    return {
        "rule_id": rule.rule_id,
        "tenant_id": rule.tenant_id,
        "classification": rule.classification.value,
        "redaction_level": rule.redaction_level.value,
        "scope_ref_id": rule.scope_ref_id,
        "field_patterns": list(rule.field_patterns),
        "created_at": rule.created_at,
    }


def _retention_rule_response(rule: RetentionRule) -> dict[str, object]:
    return {
        "rule_id": rule.rule_id,
        "tenant_id": rule.tenant_id,
        "classification": rule.classification.value,
        "retention_days": rule.retention_days,
        "disposition": rule.disposition.value,
        "scope_ref_id": rule.scope_ref_id,
        "created_at": rule.created_at,
    }


def _decision_response(decision: HandlingDecision) -> dict[str, object]:
    return {
        "decision_id": decision.decision_id,
        "data_id": decision.data_id,
        "tenant_id": decision.tenant_id,
        "operation": decision.operation,
        "decision": decision.decision.value,
        "disposition": decision.disposition.value,
        "redaction_level": decision.redaction_level.value,
        "reason": decision.reason,
        "decided_at": decision.decided_at,
    }


def _violation_response(violation: DataViolation) -> dict[str, object]:
    return {
        "violation_id": violation.violation_id,
        "data_id": violation.data_id,
        "tenant_id": violation.tenant_id,
        "operation": violation.operation,
        "reason": violation.reason,
        "classification": violation.classification.value,
        "detected_at": violation.detected_at,
    }


@router.get("/api/v1/data-governance/summary")
def data_governance_summary(request: Request, tenant_id: str | None = None):
    """Return data governance posture and optional tenant-scoped records."""
    deps.metrics.inc("requests_governed")
    engine = deps.data_governance
    # Cross-tenant read guard: an authenticated, non-operator caller is forced to
    # its own tenant; tenant_id=None no longer widens the tenant-scoped block to
    # another tenant's records. Global aggregate counts below are non-tenant.
    tenant_id = scoped_listing_tenant(request, tenant_id)
    records = engine.records_for_tenant(tenant_id) if tenant_id else ()
    violations = engine.violations_for_tenant(tenant_id) if tenant_id else ()
    return {
        "governed": True,
        "summary": {
            "records": engine.record_count,
            "policies": engine.policy_count,
            "residency_constraints": engine.residency_constraint_count,
            "privacy_rules": engine.privacy_rule_count,
            "redaction_rules": engine.redaction_rule_count,
            "retention_rules": engine.retention_rule_count,
            "decisions": engine.decision_count,
            "violations": engine.violation_count,
            "state_hash": engine.state_hash(),
        },
        "tenant": {
            "tenant_id": tenant_id,
            "record_count": len(records),
            "violation_count": len(violations),
            "records": [_record_response(record) for record in records],
            "violations": [_violation_response(violation) for violation in violations],
        } if tenant_id else None,
    }


@router.post("/api/v1/data-governance/classify")
def classify_data_record(req: DataClassifyRequest, request: Request):
    """Classify a data record under tenant, privacy, and residency scope."""
    deps.metrics.inc("requests_governed")
    enforce_tenant_scope(request, req.tenant_id)
    try:
        record = deps.data_governance.classify_data(
            req.data_id,
            req.tenant_id,
            classification=req.classification,
            residency=req.residency,
            privacy_basis=req.privacy_basis,
            domain=req.domain,
            source_id=req.source_id,
        )
    except RuntimeCoreInvariantError as exc:
        _raise_data_governance_error(exc)
    return {
        "record": _record_response(record),
        "governed": True,
        "action_proof": _certify_action_proof(
            endpoint="/api/v1/data-governance/classify",
            tenant_id=req.tenant_id,
            actor_id="api",
            target=req.data_id,
            action="data.classify",
            succeeded=True,
        ),
    }


@router.post("/api/v1/data-governance/policies")
def register_data_policy(req: DataPolicyRequest, request: Request):
    """Register a tenant data handling policy."""
    deps.metrics.inc("requests_governed")
    enforce_tenant_scope(request, req.tenant_id)
    try:
        policy = deps.data_governance.register_policy(
            req.policy_id,
            req.tenant_id,
            classification=req.classification,
            disposition=req.disposition,
            residency=req.residency,
            scope_ref_id=req.scope_ref_id,
            description=req.description,
        )
    except RuntimeCoreInvariantError as exc:
        _raise_data_governance_error(exc)
    return {
        "policy": _policy_response(policy),
        "governed": True,
        "action_proof": _certify_action_proof(
            endpoint="/api/v1/data-governance/policies",
            tenant_id=req.tenant_id,
            actor_id="api",
            target=req.policy_id,
            action="data.policy.register",
            succeeded=True,
        ),
    }


@router.post("/api/v1/data-governance/residency-constraints")
def register_residency_constraint(req: ResidencyConstraintRequest, request: Request):
    """Register allowed and denied residency regions for a tenant."""
    deps.metrics.inc("requests_governed")
    enforce_tenant_scope(request, req.tenant_id)
    try:
        constraint = deps.data_governance.register_residency_constraint(
            req.constraint_id,
            req.tenant_id,
            allowed_regions=req.allowed_regions,
            denied_regions=req.denied_regions,
        )
    except RuntimeCoreInvariantError as exc:
        _raise_data_governance_error(exc)
    return {
        "constraint": _residency_response(constraint),
        "governed": True,
        "action_proof": _certify_action_proof(
            endpoint="/api/v1/data-governance/residency-constraints",
            tenant_id=req.tenant_id,
            actor_id="api",
            target=req.constraint_id,
            action="data.residency.register",
            succeeded=True,
        ),
    }


@router.post("/api/v1/data-governance/privacy-rules")
def register_privacy_rule(req: PrivacyRuleRequest, request: Request):
    """Register a tenant privacy-basis rule."""
    deps.metrics.inc("requests_governed")
    enforce_tenant_scope(request, req.tenant_id)
    try:
        rule = deps.data_governance.register_privacy_rule(
            req.rule_id,
            req.tenant_id,
            classification=req.classification,
            required_basis=req.required_basis,
            scope_ref_id=req.scope_ref_id,
            description=req.description,
        )
    except RuntimeCoreInvariantError as exc:
        _raise_data_governance_error(exc)
    return {
        "rule": _privacy_rule_response(rule),
        "governed": True,
        "action_proof": _certify_action_proof(
            endpoint="/api/v1/data-governance/privacy-rules",
            tenant_id=req.tenant_id,
            actor_id="api",
            target=req.rule_id,
            action="data.privacy.register",
            succeeded=True,
        ),
    }


@router.post("/api/v1/data-governance/redaction-rules")
def register_redaction_rule(req: RedactionRuleRequest, request: Request):
    """Register a tenant redaction rule."""
    deps.metrics.inc("requests_governed")
    enforce_tenant_scope(request, req.tenant_id)
    try:
        rule = deps.data_governance.register_redaction_rule(
            req.rule_id,
            req.tenant_id,
            classification=req.classification,
            redaction_level=req.redaction_level,
            scope_ref_id=req.scope_ref_id,
            field_patterns=req.field_patterns,
        )
    except RuntimeCoreInvariantError as exc:
        _raise_data_governance_error(exc)
    return {
        "rule": _redaction_rule_response(rule),
        "governed": True,
        "action_proof": _certify_action_proof(
            endpoint="/api/v1/data-governance/redaction-rules",
            tenant_id=req.tenant_id,
            actor_id="api",
            target=req.rule_id,
            action="data.redaction.register",
            succeeded=True,
        ),
    }


@router.post("/api/v1/data-governance/retention-rules")
def register_retention_rule(req: RetentionRuleRequest, request: Request):
    """Register a tenant retention rule."""
    deps.metrics.inc("requests_governed")
    enforce_tenant_scope(request, req.tenant_id)
    try:
        rule = deps.data_governance.register_retention_rule(
            req.rule_id,
            req.tenant_id,
            classification=req.classification,
            retention_days=req.retention_days,
            disposition=req.disposition,
            scope_ref_id=req.scope_ref_id,
        )
    except RuntimeCoreInvariantError as exc:
        _raise_data_governance_error(exc)
    return {
        "rule": _retention_rule_response(rule),
        "governed": True,
        "action_proof": _certify_action_proof(
            endpoint="/api/v1/data-governance/retention-rules",
            tenant_id=req.tenant_id,
            actor_id="api",
            target=req.rule_id,
            action="data.retention.register",
            succeeded=True,
        ),
    }


@router.post("/api/v1/data-governance/evaluate")
def evaluate_data_handling(req: DataHandlingEvaluationRequest, request: Request):
    """Evaluate a data handling operation against policy and residency rules."""
    deps.metrics.inc("requests_governed")
    try:
        decision = deps.data_governance.evaluate_handling(
            req.data_id,
            req.operation,
            target_region=req.target_region,
        )
    except RuntimeCoreInvariantError as exc:
        _raise_data_governance_error(exc)
    # Cross-tenant guard: the request carries no tenant_id (the engine resolves
    # the owning tenant from data_id), so enforce against the record's true
    # tenant. An authenticated tenant-A caller cannot read tenant-B's decision.
    enforce_tenant_scope(request, decision.tenant_id)
    succeeded = decision.decision in {
        GovernanceDecision.ALLOWED,
        GovernanceDecision.REDACTED,
        GovernanceDecision.REQUIRES_REVIEW,
    }
    if decision.decision == GovernanceDecision.DENIED:
        deps.data_governance.detect_violations()
    return {
        "decision": _decision_response(decision),
        "governed": True,
        "action_proof": _certify_action_proof(
            endpoint="/api/v1/data-governance/evaluate",
            tenant_id=decision.tenant_id,
            actor_id="api",
            target=req.data_id,
            action="data.handling.evaluate",
            succeeded=succeeded,
        ),
    }
