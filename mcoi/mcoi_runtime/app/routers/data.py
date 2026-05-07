"""Data-plane endpoints: conversations, schemas, prompts, tools, state,
structured output, certification, daemon, search, API keys, export, and SLA.

Extracted from workflow.py to keep route files focused.
"""
from __future__ import annotations

from typing import NoReturn
from typing import Any

import hashlib
import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from mcoi_runtime.app.routers.deps import deps
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
from mcoi_runtime.core.data_export import ExportFormat, ExportRequest
from mcoi_runtime.core.tool_use import certify_tool_capability_policy_receipt
from mcoi_runtime.persistence import PathTraversalError

router = APIRouter()


def _data_error_detail(error: str, error_code: str) -> dict[str, object]:
    return {"error": error, "error_code": error_code, "governed": True}


def _certify_action_proof(
    *,
    endpoint: str,
    tenant_id: str,
    actor_id: str,
    target: str,
    action: str,
    succeeded: bool,
) -> dict[str, object]:
    """Certify a data-plane action response with a proof bridge receipt."""
    proof = deps.proof_bridge.certify_governance_decision(
        tenant_id=tenant_id or "system",
        endpoint=endpoint,
        guard_results=[
            {
                "guard_name": "data_action_closure",
                "allowed": True,
                "reason": "data action reached response boundary",
            }
        ],
        decision="allowed",
        actor_id=actor_id or "anonymous",
        reason="data action response certified",
    )
    return {
        "endpoint": endpoint,
        "target": target,
        "proof_phase": action,
        "succeeded": succeeded,
        "proof_receipt_id": proof.capsule.receipt.receipt_id,
        "proof_hash": proof.receipt_hash,
    }


# ── Pydantic request models ──────────────────────────────────────────────


class ConversationMessageRequest(BaseModel):
    conversation_id: str
    role: str = "user"
    content: str = ""
    tenant_id: str = ""


class ValidateRequest(BaseModel):
    schema_id: str
    data: dict[str, Any]


class PromptRenderRequest(BaseModel):
    template_id: str
    variables: dict[str, str]
    tenant_id: str = "system"
    budget_id: str = "default"
    execute: bool = False  # If True, also run the rendered prompt through LLM


class ToolInvokeRequest(BaseModel):
    tool_id: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    tenant_id: str = ""


class StateSaveRequest(BaseModel):
    state_type: str
    data: dict[str, Any]


class ParseOutputRequest(BaseModel):
    schema_id: str
    text: str


class SemanticSearchRequest(BaseModel):
    query: str
    limit: int = 10


class CreateAPIKeyRequest(BaseModel):
    tenant_id: str
    scopes: list[str]
    description: str = ""
    ttl_seconds: float | None = None


class DataExportRequest(BaseModel):
    source: str
    format: str = "json"
    fields: list[str] = Field(default_factory=list)
    filters: dict[str, Any] = Field(default_factory=dict)
    limit: int = 10_000


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


def _raise_prompt_execution_unavailable(
    *,
    template_id: str,
    tenant_id: str,
    exc: Exception,
) -> NoReturn:
    """Raise a sanitized prompt-execution failure."""
    deps.llm_circuit.record_failure()
    deps.metrics.inc("errors_total")
    deps.audit_trail.record(
        action="prompt.render",
        actor_id="api",
        tenant_id=tenant_id,
        target=template_id,
        outcome="error",
        detail={
            "error_type": type(exc).__name__,
            "reason": "llm_service_unavailable",
        },
    )
    raise HTTPException(
        503,
        detail={
            "error": "LLM service unavailable",
            "error_code": "llm_service_unavailable",
            "governed": True,
        },
    )


# ═══ Conversation Endpoints ══════════════════════════════════════════════


# Data Governance Endpoints


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


# Data Governance Endpoints


@router.get("/api/v1/data-governance/summary")
def data_governance_summary(tenant_id: str | None = None):
    """Return data governance posture and optional tenant-scoped records."""
    deps.metrics.inc("requests_governed")
    engine = deps.data_governance
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
def classify_data_record(req: DataClassifyRequest):
    """Classify a data record under tenant, privacy, and residency scope."""
    deps.metrics.inc("requests_governed")
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
def register_data_policy(req: DataPolicyRequest):
    """Register a tenant data handling policy."""
    deps.metrics.inc("requests_governed")
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
def register_residency_constraint(req: ResidencyConstraintRequest):
    """Register allowed and denied residency regions for a tenant."""
    deps.metrics.inc("requests_governed")
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
def register_privacy_rule(req: PrivacyRuleRequest):
    """Register a tenant privacy-basis rule."""
    deps.metrics.inc("requests_governed")
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
def register_redaction_rule(req: RedactionRuleRequest):
    """Register a tenant redaction rule."""
    deps.metrics.inc("requests_governed")
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
def register_retention_rule(req: RetentionRuleRequest):
    """Register a tenant retention rule."""
    deps.metrics.inc("requests_governed")
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
def evaluate_data_handling(req: DataHandlingEvaluationRequest):
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


# Conversation Endpoints


@router.post("/api/v1/conversation/message")
def add_conversation_message(req: ConversationMessageRequest):
    """Add a message to a conversation."""
    deps.metrics.inc("requests_governed")
    conv = deps.conversation_store.get_or_create(req.conversation_id, tenant_id=req.tenant_id)
    msg = conv.add_message(req.role, req.content)
    return {
        "conversation_id": conv.conversation_id,
        "message_id": msg.message_id,
        "message_count": conv.message_count,
    }


@router.get("/api/v1/conversation/{conversation_id}")
def get_conversation(conversation_id: str):
    """Get conversation history."""
    conv = deps.conversation_store.get(conversation_id)
    if conv is None:
        raise HTTPException(404, detail="conversation not found")
    return {
        "conversation_id": conv.conversation_id,
        "messages": [{"role": m.role, "content": m.content, "id": m.message_id} for m in conv.messages],
        "summary": conv.summary(),
    }


@router.get("/api/v1/conversations")
def list_conversations(tenant_id: str | None = None):
    """List conversations."""
    convs = deps.conversation_store.list_conversations(tenant_id=tenant_id)
    return {
        "conversations": [c.summary() for c in convs],
        "count": len(convs),
    }


# ═══ Schema Validation ═══════════════════════════════════════════════════


@router.get("/api/v1/schemas")
def list_schemas():
    """List registered validation schemas."""
    return {
        "schemas": [
            {"id": s.schema_id, "name": s.name, "rules": len(s.rules)}
            for s in deps.schema_validator.list_schemas()
        ],
        "summary": deps.schema_validator.summary(),
    }


@router.post("/api/v1/schemas/validate")
def validate_data(req: ValidateRequest):
    """Validate data against a registered schema."""
    result = deps.schema_validator.validate(req.schema_id, req.data)
    return {
        "schema_id": result.schema_id,
        "valid": result.valid,
        "errors": [
            {"field": e.field, "rule": e.rule_type, "message": e.message}
            for e in result.errors
        ],
    }


# ═══ Prompt Template Endpoints ═══════════════════════════════════════════


@router.get("/api/v1/prompts")
def list_prompt_templates(category: str | None = None):
    """List registered prompt templates."""
    templates = deps.prompt_engine.list_templates(category=category)
    return {
        "templates": [
            {"id": t.template_id, "name": t.name, "variables": list(t.variables),
             "category": t.category, "version": t.version}
            for t in templates
        ],
        "summary": deps.prompt_engine.summary(),
    }


@router.post("/api/v1/prompts/render")
def render_prompt(req: PromptRenderRequest):
    """Render a prompt template with variables, optionally execute via LLM."""
    deps.metrics.inc("requests_governed")
    try:
        rendered = deps.prompt_engine.render(req.template_id, req.variables)
    except ValueError:
        raise HTTPException(400, detail={"error": "invalid request", "error_code": "validation_error", "governed": True})

    response: dict[str, Any] = {
        "template_id": rendered.template_id,
        "prompt": rendered.prompt,
        "system_prompt": rendered.system_prompt,
        "version": rendered.version,
    }

    if req.execute:
        deps.metrics.inc("llm_calls_total")
        try:
            result = deps.llm_bridge.complete(
                rendered.prompt, system=rendered.system_prompt,
                budget_id=req.budget_id, tenant_id=req.tenant_id,
            )
        except Exception as exc:
            _raise_prompt_execution_unavailable(
                template_id=rendered.template_id,
                tenant_id=req.tenant_id,
                exc=exc,
            )
        response["llm_result"] = {
            "content": result.content,
            "model": result.model_name,
            "tokens": result.total_tokens,
            "cost": result.cost,
            "succeeded": result.succeeded,
        }
        if result.succeeded:
            deps.cost_analytics.record(req.tenant_id, result.model_name, result.cost, result.total_tokens)

    return response


# ═══ Tool Registry Endpoints ═════════════════════════════════════════════


@router.get("/api/v1/tools")
def list_tools(category: str | None = None):
    """List registered tools."""
    tools = deps.tool_registry.list_tools(category=category)
    return {
        "tools": [
            {"id": t.tool_id, "name": t.name, "description": t.description,
             "parameters": [{"name": p.name, "type": p.param_type, "required": p.required} for p in t.parameters],
             "category": t.category}
            for t in tools
        ],
        "count": len(tools),
    }


@router.post("/api/v1/tools/invoke")
def invoke_tool(req: ToolInvokeRequest):
    """Invoke a registered tool."""
    deps.metrics.inc("requests_governed")
    tool = deps.tool_registry.get(req.tool_id)
    result = deps.tool_registry.invoke(req.tool_id, req.arguments, tenant_id=req.tenant_id)
    policy_receipt = certify_tool_capability_policy_receipt(
        tool=tool,
        tool_id=req.tool_id,
        arguments=req.arguments,
        tenant_id=req.tenant_id,
        invocation_id=result.invocation_id,
        execution_succeeded=result.succeeded,
    )
    deps.audit_trail.record(
        action="tool.invoke", actor_id="api", tenant_id=req.tenant_id,
        target=req.tool_id, outcome="success" if result.succeeded else "error",
        detail={
            "capability_policy_receipt_id": policy_receipt["receipt_id"],
            "argument_hash": policy_receipt["argument_hash"],
            "policy_allowed": policy_receipt["policy_allowed"],
        },
    )
    return {
        "invocation_id": result.invocation_id, "tool_id": result.tool_id,
        "output": result.output, "succeeded": result.succeeded, "error": result.error,
        "capability_policy_receipt": policy_receipt,
        "action_proof": _certify_action_proof(
            endpoint="/api/v1/tools/invoke",
            tenant_id=req.tenant_id,
            actor_id="api",
            target=req.tool_id,
            action="tool.invoke",
            succeeded=result.succeeded,
        ),
    }


@router.get("/api/v1/tools/llm-format")
def tools_llm_format():
    """Export tools in LLM-compatible format."""
    return {"tools": deps.tool_registry.to_llm_tools()}


@router.get("/api/v1/tools/history")
def tool_history(limit: int = 50):
    """Tool invocation history."""
    return {"history": [
        {"id": r.invocation_id, "tool": r.tool_id, "succeeded": r.succeeded}
        for r in deps.tool_registry.invocation_history(limit=limit)
    ], "summary": deps.tool_registry.summary()}


# ═══ State Persistence ═══════════════════════════════════════════════════


@router.post("/api/v1/state/save")
def save_state(req: StateSaveRequest):
    """Save runtime state."""
    deps.metrics.inc("requests_governed")
    try:
        snap = deps.state_persistence.save(req.state_type, req.data)
    except PathTraversalError:
        raise HTTPException(400, detail={
            "error": "invalid state_type",
            "error_code": "invalid_state_type",
            "governed": True,
        })
    return {"state_type": snap.state_type, "hash": snap.state_hash[:16], "saved_at": snap.saved_at}


@router.get("/api/v1/state/{state_type}")
def load_state(state_type: str):
    """Load runtime state."""
    try:
        snap = deps.state_persistence.load(state_type)
    except PathTraversalError:
        raise HTTPException(400, detail=_data_error_detail("invalid state_type", "invalid_state_type"))
    if snap is None:
        raise HTTPException(404, detail=_data_error_detail("state not found", "state_not_found"))
    return {"state_type": snap.state_type, "data": snap.data, "hash": snap.state_hash[:16]}


@router.get("/api/v1/state")
def list_states():
    """List saved states."""
    return {"states": deps.state_persistence.list_states(), "summary": deps.state_persistence.summary()}


# ═══ Structured Output ═══════════════════════════════════════════════════


@router.post("/api/v1/output/parse")
def parse_structured_output(req: ParseOutputRequest):
    """Parse LLM output against a schema."""
    result = deps.structured_output.parse(req.schema_id, req.text)
    return {"schema_id": result.schema_id, "valid": result.valid, "parsed": result.parsed, "errors": list(result.errors)}


@router.get("/api/v1/output/schemas")
def list_output_schemas():
    """List output schemas."""
    return {"schemas": [{"id": s.schema_id, "name": s.name, "fields": s.fields} for s in deps.structured_output.list_schemas()]}


# ═══ Certification ═══════════════════════════════════════════════════════


@router.post("/api/v1/certify")
def run_certification():
    """Run full live-path certification: API -> DB -> LLM -> Ledger -> Restart."""
    chain = deps.certifier.run_full_certification(
        api_handle_fn=lambda req: {"governed": True, "status": "ok"},
        db_write_fn=lambda t, c: deps.store.append_ledger(
            "certification", "certifier", t, c,
            hashlib.sha256(json.dumps(c, sort_keys=True).encode()).hexdigest(),
        ),
        db_read_fn=lambda t: deps.store.query_ledger(t),
        llm_invoke_fn=lambda prompt: deps.llm_bridge.complete(prompt, budget_id="default"),
        ledger_entries=deps.store.query_ledger("system", limit=100),
        pre_state_fn=lambda: (
            hashlib.sha256(str(deps.store.ledger_count()).encode()).hexdigest(),
            deps.store.ledger_count(),
        ),
        post_state_fn=lambda: (
            hashlib.sha256(str(deps.store.ledger_count()).encode()).hexdigest(),
            deps.store.ledger_count(),
        ),
    )
    return {
        "chain_id": chain.chain_id,
        "all_passed": chain.all_passed,
        "chain_hash": chain.chain_hash,
        "action_proof": _certify_action_proof(
            endpoint="/api/v1/certify",
            tenant_id="system",
            actor_id="api",
            target=chain.chain_id,
            action="certification.run",
            succeeded=chain.all_passed,
        ),
        "steps": [
            {"name": s.name, "status": s.status.value, "proof_hash": s.proof_hash, "detail": s.detail}
            for s in chain.steps
        ],
    }


@router.get("/api/v1/certify/history")
def certification_history():
    """Certification chain history."""
    return {"certifications": deps.certifier.certification_history()}


# ═══ Certification Daemon ════════════════════════════════════════════════


@router.get("/api/v1/daemon/status")
def daemon_status():
    """Certification daemon health and run status."""
    return deps.cert_daemon.status()


@router.post("/api/v1/daemon/tick")
def daemon_tick():
    """Trigger a single certification daemon tick."""
    chain = deps.cert_daemon.tick()
    if chain is None:
        return {"ran": False, "reason": "disabled or interval not elapsed"}
    return {
        "ran": True,
        "chain_id": chain.chain_id,
        "all_passed": chain.all_passed,
    }


@router.post("/api/v1/daemon/force")
def daemon_force():
    """Force an immediate certification run regardless of interval."""
    chain = deps.cert_daemon.force_run()
    if chain is None:
        return {"ran": False}
    return {
        "ran": True,
        "chain_id": chain.chain_id,
        "all_passed": chain.all_passed,
        "chain_hash": chain.chain_hash,
    }


# ═══ Semantic Search ═════════════════════════════════════════════════════


@router.post("/api/v1/search")
def semantic_search_endpoint(req: SemanticSearchRequest):
    """Semantic search across indexed documents."""
    results = deps.semantic_search.search(req.query, limit=req.limit)
    return {
        "results": [{"doc_id": r.doc_id, "score": r.score, "matched": list(r.matched_terms)} for r in results],
        "count": len(results),
    }


@router.get("/api/v1/search/stats")
def search_stats():
    """Semantic search index statistics."""
    return deps.semantic_search.summary()


# ═══ API Key Management ══════════════════════════════════════════════════


@router.post("/api/v1/api-keys")
def create_api_key(req: CreateAPIKeyRequest):
    """Create a new API key."""
    deps.metrics.inc("requests_governed")
    if "*" in req.scopes and not deps.api_key_mgr.allow_wildcard_keys:
        raise HTTPException(
            400,
            detail=_data_error_detail(
                "wildcard api keys disabled",
                "wildcard_api_keys_disabled",
            ),
        )
    try:
        raw_key, api_key = deps.api_key_mgr.create_key(
            req.tenant_id,
            frozenset(req.scopes),
            description=req.description,
            ttl_seconds=req.ttl_seconds,
        )
    except ValueError:
        raise HTTPException(
            400,
            detail=_data_error_detail(
                "invalid api key request",
                "api_key_validation_error",
            ),
        )
    return {
        "raw_key": raw_key,
        "key": api_key.to_dict(),
        "governed": True,
    }


@router.get("/api/v1/api-keys")
def list_api_keys(tenant_id: str | None = None):
    """List API keys."""
    deps.metrics.inc("requests_governed")
    keys = deps.api_key_mgr.list_keys(tenant_id=tenant_id)
    return {"keys": [k.to_dict() for k in keys], "governed": True}


@router.delete("/api/v1/api-keys/{key_id}")
def revoke_api_key(key_id: str):
    """Revoke an API key."""
    deps.metrics.inc("requests_governed")
    if not deps.api_key_mgr.revoke(key_id):
        raise HTTPException(404, detail=_data_error_detail("api key not found", "api_key_not_found"))
    return {"revoked": True, "key_id": key_id, "governed": True}


# ═══ Data Export ═════════════════════════════════════════════════════════


@router.get("/api/v1/export/sources")
def list_export_sources():
    """List available data export sources."""
    deps.metrics.inc("requests_governed")
    return {"sources": deps.data_export.list_sources(), "governed": True}


@router.post("/api/v1/export")
def export_data(req: DataExportRequest):
    """Export data in CSV, JSON, or JSONL format."""
    deps.metrics.inc("requests_governed")
    try:
        fmt = ExportFormat(req.format)
    except ValueError:
        raise HTTPException(400, detail=_data_error_detail("unsupported export format", "unsupported_export_format"))
    try:
        result = deps.data_export.export(ExportRequest(
            source=req.source, format=fmt,
            fields=tuple(req.fields), filters=req.filters, limit=req.limit,
        ))
    except ValueError:
        raise HTTPException(400, detail={"error": "invalid request", "error_code": "validation_error", "governed": True})
    return {
        "export": result.to_dict(),
        "content": result.content,
        "governed": True,
    }


# ═══ SLA Monitoring ═════════════════════════════════════════════════════


@router.get("/api/v1/sla")
def get_sla_summary():
    """Return SLA monitoring summary."""
    deps.metrics.inc("requests_governed")
    return {"sla": deps.sla_monitor.summary(), "governed": True}


@router.get("/api/v1/sla/violations")
def get_sla_violations(sla_id: str | None = None):
    """Return SLA violations."""
    deps.metrics.inc("requests_governed")
    violations = deps.sla_monitor.violations(sla_id)
    return {
        "violations": [{"sla_id": v.sla_id, "actual": v.actual_value,
                         "threshold": v.threshold} for v in violations],
        "count": len(violations),
        "governed": True,
    }
