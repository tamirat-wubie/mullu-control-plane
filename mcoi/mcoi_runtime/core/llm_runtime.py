"""Purpose: LLM / model runtime engine.
Governance scope: governed execution of language models with budget
    enforcement, tool permission scopes, grounding checks, safety
    assessments, provider fallback chains, and replayable traces.
Dependencies: event_spine, invariants, contracts.
Invariants:
  - LLMs are non-authoritative execution substrates.
  - Every generation is budgeted and traceable.
  - Duplicate IDs are rejected fail-closed.
  - Terminal states block further mutations.
  - All outputs are frozen.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from mcoi_runtime.contracts.event import EventRecord, EventSource, EventType
from mcoi_runtime.contracts.llm_runtime import (
    ContextPack,
    GenerationRequest,
    GenerationResult,
    GenerationStatus,
    GroundingEvidence,
    GroundingStatus,
    LlmAssessment,
    LlmClosureReport,
    LlmRuntimeSnapshot,
    ModelDescriptor,
    ModelStatus,
    PromptDisposition,
    PromptTemplate,
    ProviderRoute,
    ProviderStatus,
    SafetyAssessment,
    SafetyVerdict,
    ToolPermission,
)
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, stable_identifier


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_GENERATION_TERMINAL = frozenset({
    GenerationStatus.COMPLETED,
    GenerationStatus.FAILED,
    GenerationStatus.BLOCKED,
    GenerationStatus.TIMED_OUT,
})


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict[str, Any], cid: str) -> None:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-llm", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)


class LlmRuntimeEngine:
    """Governed LLM execution engine."""

    def __init__(self, event_spine: EventSpineEngine) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._models: dict[str, ModelDescriptor] = {}
        self._routes: dict[str, ProviderRoute] = {}
        self._templates: dict[str, PromptTemplate] = {}
        self._packs: dict[str, ContextPack] = {}
        self._requests: dict[str, GenerationRequest] = {}
        self._results: dict[str, GenerationResult] = {}
        self._permissions: dict[str, ToolPermission] = {}
        self._evidence: dict[str, GroundingEvidence] = {}
        self._assessments: dict[str, SafetyAssessment] = {}
        self._violations: dict[str, dict[str, Any]] = {}

    # -- Properties --
    @property
    def model_count(self) -> int:
        return len(self._models)

    @property
    def route_count(self) -> int:
        return len(self._routes)

    @property
    def template_count(self) -> int:
        return len(self._templates)

    @property
    def pack_count(self) -> int:
        return len(self._packs)

    @property
    def request_count(self) -> int:
        return len(self._requests)

    @property
    def result_count(self) -> int:
        return len(self._results)

    @property
    def permission_count(self) -> int:
        return len(self._permissions)

    @property
    def violation_count(self) -> int:
        return len(self._violations)

    # -- Models --
    def register_model(
        self,
        model_id: str,
        tenant_id: str,
        display_name: str,
        provider_ref: str = "default",
        max_tokens: int = 4096,
        cost_per_token: float = 0.0,
    ) -> ModelDescriptor:
        if model_id in self._models:
            raise RuntimeCoreInvariantError(f"duplicate model_id: {model_id}")
        now = _now_iso()
        model = ModelDescriptor(
            model_id=model_id, tenant_id=tenant_id, display_name=display_name,
            provider_ref=provider_ref, status=ModelStatus.ACTIVE,
            max_tokens=max_tokens, cost_per_token=cost_per_token,
            registered_at=now,
        )
        self._models[model_id] = model
        _emit(self._events, "register_model", {"model_id": model_id}, model_id)
        return model

    def get_model(self, model_id: str) -> ModelDescriptor:
        if model_id not in self._models:
            raise RuntimeCoreInvariantError(f"unknown model_id: {model_id}")
        return self._models[model_id]

    def deprecate_model(self, model_id: str) -> ModelDescriptor:
        model = self.get_model(model_id)
        if model.status == ModelStatus.RETIRED:
            raise RuntimeCoreInvariantError(f"model {model_id} is RETIRED")
        now = _now_iso()
        updated = ModelDescriptor(
            model_id=model.model_id, tenant_id=model.tenant_id,
            display_name=model.display_name, provider_ref=model.provider_ref,
            status=ModelStatus.DEPRECATED, max_tokens=model.max_tokens,
            cost_per_token=model.cost_per_token, registered_at=now,
        )
        self._models[model_id] = updated
        _emit(self._events, "deprecate_model", {"model_id": model_id}, model_id)
        return updated

    def disable_model(self, model_id: str) -> ModelDescriptor:
        model = self.get_model(model_id)
        if model.status == ModelStatus.RETIRED:
            raise RuntimeCoreInvariantError(f"model {model_id} is RETIRED")
        now = _now_iso()
        updated = ModelDescriptor(
            model_id=model.model_id, tenant_id=model.tenant_id,
            display_name=model.display_name, provider_ref=model.provider_ref,
            status=ModelStatus.DISABLED, max_tokens=model.max_tokens,
            cost_per_token=model.cost_per_token, registered_at=now,
        )
        self._models[model_id] = updated
        _emit(self._events, "disable_model", {"model_id": model_id}, model_id)
        return updated

    def retire_model(self, model_id: str) -> ModelDescriptor:
        model = self.get_model(model_id)
        if model.status == ModelStatus.RETIRED:
            raise RuntimeCoreInvariantError(f"model {model_id} is already RETIRED")
        now = _now_iso()
        updated = ModelDescriptor(
            model_id=model.model_id, tenant_id=model.tenant_id,
            display_name=model.display_name, provider_ref=model.provider_ref,
            status=ModelStatus.RETIRED, max_tokens=model.max_tokens,
            cost_per_token=model.cost_per_token, registered_at=now,
        )
        self._models[model_id] = updated
        _emit(self._events, "retire_model", {"model_id": model_id}, model_id)
        return updated

    def models_for_tenant(self, tenant_id: str) -> tuple[ModelDescriptor, ...]:
        return tuple(m for m in self._models.values() if m.tenant_id == tenant_id)

    # -- Provider Routes --
    def register_provider_route(
        self,
        route_id: str,
        tenant_id: str,
        provider_ref: str,
        model_id: str,
        priority: int = 0,
        latency_budget_ms: int = 30000,
        cost_budget: float = 1.0,
    ) -> ProviderRoute:
        if route_id in self._routes:
            raise RuntimeCoreInvariantError(f"duplicate route_id: {route_id}")
        if model_id not in self._models:
            raise RuntimeCoreInvariantError(f"unknown model_id: {model_id}")
        now = _now_iso()
        route = ProviderRoute(
            route_id=route_id, tenant_id=tenant_id, provider_ref=provider_ref,
            model_id=model_id, priority=priority, status=ProviderStatus.AVAILABLE,
            latency_budget_ms=latency_budget_ms, cost_budget=cost_budget,
            created_at=now,
        )
        self._routes[route_id] = route
        _emit(self._events, "register_provider_route", {"route_id": route_id}, route_id)
        return route

    def mark_route_degraded(self, route_id: str) -> ProviderRoute:
        if route_id not in self._routes:
            raise RuntimeCoreInvariantError(f"unknown route_id: {route_id}")
        route = self._routes[route_id]
        now = _now_iso()
        updated = ProviderRoute(
            route_id=route.route_id, tenant_id=route.tenant_id,
            provider_ref=route.provider_ref, model_id=route.model_id,
            priority=route.priority, status=ProviderStatus.DEGRADED,
            latency_budget_ms=route.latency_budget_ms, cost_budget=route.cost_budget,
            created_at=now,
        )
        self._routes[route_id] = updated
        _emit(self._events, "mark_route_degraded", {"route_id": route_id}, route_id)
        return updated

    def mark_route_unavailable(self, route_id: str) -> ProviderRoute:
        if route_id not in self._routes:
            raise RuntimeCoreInvariantError(f"unknown route_id: {route_id}")
        route = self._routes[route_id]
        now = _now_iso()
        updated = ProviderRoute(
            route_id=route.route_id, tenant_id=route.tenant_id,
            provider_ref=route.provider_ref, model_id=route.model_id,
            priority=route.priority, status=ProviderStatus.UNAVAILABLE,
            latency_budget_ms=route.latency_budget_ms, cost_budget=route.cost_budget,
            created_at=now,
        )
        self._routes[route_id] = updated
        _emit(self._events, "mark_route_unavailable", {"route_id": route_id}, route_id)
        return updated

    def choose_fallback_route(self, model_id: str) -> ProviderRoute | None:
        """Choose the best available route for a model, sorted by priority."""
        routes = [
            r for r in self._routes.values()
            if r.model_id == model_id and r.status == ProviderStatus.AVAILABLE
        ]
        if not routes:
            # Try degraded routes
            routes = [
                r for r in self._routes.values()
                if r.model_id == model_id and r.status == ProviderStatus.DEGRADED
            ]
        if not routes:
            return None
        routes.sort(key=lambda r: r.priority)
        return routes[0]

    def routes_for_model(self, model_id: str) -> tuple[ProviderRoute, ...]:
        return tuple(r for r in self._routes.values() if r.model_id == model_id)

    # -- Prompt Templates --
    def register_prompt_template(
        self,
        template_id: str,
        tenant_id: str,
        display_name: str,
        template_text: str,
        version: int = 1,
    ) -> PromptTemplate:
        if template_id in self._templates:
            raise RuntimeCoreInvariantError(f"duplicate template_id: {template_id}")
        now = _now_iso()
        template = PromptTemplate(
            template_id=template_id, tenant_id=tenant_id,
            display_name=display_name, template_text=template_text,
            disposition=PromptDisposition.DRAFT, version=version,
            created_at=now,
        )
        self._templates[template_id] = template
        _emit(self._events, "register_prompt_template", {"template_id": template_id}, template_id)
        return template

    def approve_template(self, template_id: str) -> PromptTemplate:
        if template_id not in self._templates:
            raise RuntimeCoreInvariantError(f"unknown template_id: {template_id}")
        t = self._templates[template_id]
        if t.disposition == PromptDisposition.ARCHIVED:
            raise RuntimeCoreInvariantError(f"template {template_id} is ARCHIVED")
        now = _now_iso()
        updated = PromptTemplate(
            template_id=t.template_id, tenant_id=t.tenant_id,
            display_name=t.display_name, template_text=t.template_text,
            disposition=PromptDisposition.APPROVED, version=t.version,
            created_at=now,
        )
        self._templates[template_id] = updated
        _emit(self._events, "approve_template", {"template_id": template_id}, template_id)
        return updated

    def get_template(self, template_id: str) -> PromptTemplate:
        if template_id not in self._templates:
            raise RuntimeCoreInvariantError(f"unknown template_id: {template_id}")
        return self._templates[template_id]

    # -- Context Packs --
    def build_context_pack(
        self,
        pack_id: str,
        tenant_id: str,
        template_id: str,
        model_id: str,
        token_count: int = 0,
        source_count: int = 0,
    ) -> ContextPack:
        if pack_id in self._packs:
            raise RuntimeCoreInvariantError(f"duplicate pack_id: {pack_id}")
        if template_id not in self._templates:
            raise RuntimeCoreInvariantError(f"unknown template_id: {template_id}")
        if model_id not in self._models:
            raise RuntimeCoreInvariantError(f"unknown model_id: {model_id}")
        # Budget check: token count must not exceed model max
        model = self._models[model_id]
        if model.max_tokens > 0 and token_count > model.max_tokens:
            raise RuntimeCoreInvariantError(
                f"token_count {token_count} exceeds model max_tokens {model.max_tokens}"
            )
        now = _now_iso()
        pack = ContextPack(
            pack_id=pack_id, tenant_id=tenant_id, template_id=template_id,
            model_id=model_id, token_count=token_count, source_count=source_count,
            assembled_at=now,
        )
        self._packs[pack_id] = pack
        _emit(self._events, "build_context_pack", {"pack_id": pack_id}, pack_id)
        return pack

    def get_pack(self, pack_id: str) -> ContextPack:
        if pack_id not in self._packs:
            raise RuntimeCoreInvariantError(f"unknown pack_id: {pack_id}")
        return self._packs[pack_id]

    # -- Tool Permissions --
    def register_tool_permission(
        self,
        permission_id: str,
        tenant_id: str,
        model_id: str,
        tool_ref: str,
        allowed: bool = True,
        scope_ref: str = "global",
    ) -> ToolPermission:
        if permission_id in self._permissions:
            raise RuntimeCoreInvariantError(f"duplicate permission_id: {permission_id}")
        if model_id not in self._models:
            raise RuntimeCoreInvariantError(f"unknown model_id: {model_id}")
        now = _now_iso()
        perm = ToolPermission(
            permission_id=permission_id, tenant_id=tenant_id, model_id=model_id,
            tool_ref=tool_ref, allowed=allowed, scope_ref=scope_ref,
            created_at=now,
        )
        self._permissions[permission_id] = perm
        _emit(self._events, "register_tool_permission", {"permission_id": permission_id}, permission_id)
        return perm

    def check_tool_permission(self, model_id: str, tool_ref: str) -> bool:
        """Check if a tool is allowed for a model. Default: denied if no rule."""
        for p in self._permissions.values():
            if p.model_id == model_id and p.tool_ref == tool_ref:
                return p.allowed
        return False  # Fail-closed: no permission = denied

    def permissions_for_model(self, model_id: str) -> tuple[ToolPermission, ...]:
        return tuple(p for p in self._permissions.values() if p.model_id == model_id)

    # -- Generation Requests --
    def request_generation(
        self,
        request_id: str,
        tenant_id: str,
        model_id: str,
        pack_id: str,
        token_budget: int = 4096,
        cost_budget: float = 1.0,
        latency_budget_ms: int = 30000,
    ) -> GenerationRequest:
        if request_id in self._requests:
            raise RuntimeCoreInvariantError(f"duplicate request_id: {request_id}")
        if model_id not in self._models:
            raise RuntimeCoreInvariantError(f"unknown model_id: {model_id}")
        model = self._models[model_id]
        if model.status in (ModelStatus.DISABLED, ModelStatus.RETIRED):
            raise RuntimeCoreInvariantError(f"model {model_id} is {model.status.value}")
        if pack_id not in self._packs:
            raise RuntimeCoreInvariantError(f"unknown pack_id: {pack_id}")
        now = _now_iso()
        req = GenerationRequest(
            request_id=request_id, tenant_id=tenant_id, model_id=model_id,
            pack_id=pack_id, status=GenerationStatus.PENDING,
            token_budget=token_budget, cost_budget=cost_budget,
            latency_budget_ms=latency_budget_ms, requested_at=now,
        )
        self._requests[request_id] = req
        _emit(self._events, "request_generation", {"request_id": request_id}, request_id)
        return req

    def get_request(self, request_id: str) -> GenerationRequest:
        if request_id not in self._requests:
            raise RuntimeCoreInvariantError(f"unknown request_id: {request_id}")
        return self._requests[request_id]

    def start_generation(self, request_id: str) -> GenerationRequest:
        req = self.get_request(request_id)
        if req.status in _GENERATION_TERMINAL:
            raise RuntimeCoreInvariantError(f"request {request_id} is terminal: {req.status.value}")
        now = _now_iso()
        updated = GenerationRequest(
            request_id=req.request_id, tenant_id=req.tenant_id,
            model_id=req.model_id, pack_id=req.pack_id,
            status=GenerationStatus.RUNNING, token_budget=req.token_budget,
            cost_budget=req.cost_budget, latency_budget_ms=req.latency_budget_ms,
            requested_at=now,
        )
        self._requests[request_id] = updated
        _emit(self._events, "start_generation", {"request_id": request_id}, request_id)
        return updated

    def block_generation(self, request_id: str) -> GenerationRequest:
        req = self.get_request(request_id)
        if req.status in _GENERATION_TERMINAL:
            raise RuntimeCoreInvariantError(f"request {request_id} is terminal: {req.status.value}")
        now = _now_iso()
        updated = GenerationRequest(
            request_id=req.request_id, tenant_id=req.tenant_id,
            model_id=req.model_id, pack_id=req.pack_id,
            status=GenerationStatus.BLOCKED, token_budget=req.token_budget,
            cost_budget=req.cost_budget, latency_budget_ms=req.latency_budget_ms,
            requested_at=now,
        )
        self._requests[request_id] = updated
        _emit(self._events, "block_generation", {"request_id": request_id}, request_id)
        return updated

    def timeout_generation(self, request_id: str) -> GenerationRequest:
        req = self.get_request(request_id)
        if req.status != GenerationStatus.RUNNING:
            raise RuntimeCoreInvariantError(f"request {request_id} must be RUNNING to timeout")
        now = _now_iso()
        updated = GenerationRequest(
            request_id=req.request_id, tenant_id=req.tenant_id,
            model_id=req.model_id, pack_id=req.pack_id,
            status=GenerationStatus.TIMED_OUT, token_budget=req.token_budget,
            cost_budget=req.cost_budget, latency_budget_ms=req.latency_budget_ms,
            requested_at=now,
        )
        self._requests[request_id] = updated
        _emit(self._events, "timeout_generation", {"request_id": request_id}, request_id)
        return updated

    def requests_for_tenant(self, tenant_id: str) -> tuple[GenerationRequest, ...]:
        return tuple(r for r in self._requests.values() if r.tenant_id == tenant_id)

    # -- Generation Results --
    def record_generation_result(
        self,
        result_id: str,
        request_id: str,
        tenant_id: str,
        tokens_used: int = 0,
        cost_incurred: float = 0.0,
        latency_ms: float = 0.0,
        output_ref: str = "none",
        confidence: float = 0.5,
    ) -> GenerationResult:
        if result_id in self._results:
            raise RuntimeCoreInvariantError(f"duplicate result_id: {result_id}")
        if request_id not in self._requests:
            raise RuntimeCoreInvariantError(f"unknown request_id: {request_id}")
        req = self._requests[request_id]
        # Auto-complete the request
        now = _now_iso()
        completed_req = GenerationRequest(
            request_id=req.request_id, tenant_id=req.tenant_id,
            model_id=req.model_id, pack_id=req.pack_id,
            status=GenerationStatus.COMPLETED, token_budget=req.token_budget,
            cost_budget=req.cost_budget, latency_budget_ms=req.latency_budget_ms,
            requested_at=now,
        )
        self._requests[request_id] = completed_req

        # Check budget overruns
        budget_violated = False
        if req.token_budget > 0 and tokens_used > req.token_budget:
            budget_violated = True
        if req.cost_budget > 0 and cost_incurred > req.cost_budget:
            budget_violated = True

        if budget_violated:
            vid = stable_identifier("viol-llm", {"request_id": request_id, "reason": "budget_exceeded"})
            if vid not in self._violations:
                self._violations[vid] = {
                    "violation_id": vid, "tenant_id": tenant_id,
                    "request_id": request_id, "operation": "budget_exceeded",
                    "reason": f"tokens_used={tokens_used} cost={cost_incurred}",
                }

        result = GenerationResult(
            result_id=result_id, request_id=request_id, tenant_id=tenant_id,
            model_id=req.model_id, status=GenerationStatus.COMPLETED,
            tokens_used=tokens_used, cost_incurred=cost_incurred,
            latency_ms=latency_ms, output_ref=output_ref,
            grounding_status=GroundingStatus.NOT_CHECKED,
            safety_verdict=SafetyVerdict.SAFE,
            confidence=confidence, completed_at=now,
        )
        self._results[result_id] = result
        _emit(self._events, "record_generation_result", {"result_id": result_id}, result_id)
        return result

    def get_result(self, result_id: str) -> GenerationResult:
        if result_id not in self._results:
            raise RuntimeCoreInvariantError(f"unknown result_id: {result_id}")
        return self._results[result_id]

    def results_for_request(self, request_id: str) -> tuple[GenerationResult, ...]:
        return tuple(r for r in self._results.values() if r.request_id == request_id)

    # -- Grounding --
    def assess_grounding(
        self,
        evidence_id: str,
        result_id: str,
        tenant_id: str,
        source_ref: str,
        relevance_score: float = 0.5,
        grounding_status: GroundingStatus = GroundingStatus.GROUNDED,
    ) -> GroundingEvidence:
        if evidence_id in self._evidence:
            raise RuntimeCoreInvariantError(f"duplicate evidence_id: {evidence_id}")
        if result_id not in self._results:
            raise RuntimeCoreInvariantError(f"unknown result_id: {result_id}")
        now = _now_iso()
        evidence = GroundingEvidence(
            evidence_id=evidence_id, result_id=result_id, tenant_id=tenant_id,
            source_ref=source_ref, relevance_score=relevance_score,
            grounding_status=grounding_status, created_at=now,
        )
        self._evidence[evidence_id] = evidence

        # Update the result's grounding status
        result = self._results[result_id]
        updated_result = GenerationResult(
            result_id=result.result_id, request_id=result.request_id,
            tenant_id=result.tenant_id, model_id=result.model_id,
            status=result.status, tokens_used=result.tokens_used,
            cost_incurred=result.cost_incurred, latency_ms=result.latency_ms,
            output_ref=result.output_ref, grounding_status=grounding_status,
            safety_verdict=result.safety_verdict, confidence=result.confidence,
            completed_at=result.completed_at,
        )
        self._results[result_id] = updated_result

        _emit(self._events, "assess_grounding", {"evidence_id": evidence_id}, evidence_id)
        return evidence

    def evidence_for_result(self, result_id: str) -> tuple[GroundingEvidence, ...]:
        return tuple(e for e in self._evidence.values() if e.result_id == result_id)

    # -- Safety --
    def assess_safety(
        self,
        assessment_id: str,
        result_id: str,
        tenant_id: str,
        verdict: SafetyVerdict = SafetyVerdict.SAFE,
        reason: str = "no issues",
        confidence: float = 1.0,
    ) -> SafetyAssessment:
        if assessment_id in self._assessments:
            raise RuntimeCoreInvariantError(f"duplicate assessment_id: {assessment_id}")
        if result_id not in self._results:
            raise RuntimeCoreInvariantError(f"unknown result_id: {result_id}")
        now = _now_iso()
        assessment = SafetyAssessment(
            assessment_id=assessment_id, result_id=result_id, tenant_id=tenant_id,
            verdict=verdict, reason=reason, confidence=confidence,
            assessed_at=now,
        )
        self._assessments[assessment_id] = assessment

        # Update the result's safety verdict
        result = self._results[result_id]
        updated_result = GenerationResult(
            result_id=result.result_id, request_id=result.request_id,
            tenant_id=result.tenant_id, model_id=result.model_id,
            status=result.status, tokens_used=result.tokens_used,
            cost_incurred=result.cost_incurred, latency_ms=result.latency_ms,
            output_ref=result.output_ref, grounding_status=result.grounding_status,
            safety_verdict=verdict, confidence=result.confidence,
            completed_at=result.completed_at,
        )
        self._results[result_id] = updated_result

        # BLOCKED verdict creates violation
        if verdict == SafetyVerdict.BLOCKED:
            vid = stable_identifier("viol-llm", {"result_id": result_id, "reason": "unsafe_output"})
            if vid not in self._violations:
                self._violations[vid] = {
                    "violation_id": vid, "tenant_id": tenant_id,
                    "result_id": result_id, "operation": "unsafe_output",
                    "reason": reason,
                }

        _emit(self._events, "assess_safety", {"assessment_id": assessment_id}, assessment_id)
        return assessment

    def assessments_for_result(self, result_id: str) -> tuple[SafetyAssessment, ...]:
        return tuple(a for a in self._assessments.values() if a.result_id == result_id)

    # -- Snapshot --
    def llm_snapshot(self, snapshot_id: str, tenant_id: str) -> LlmRuntimeSnapshot:
        now = _now_iso()
        snap = LlmRuntimeSnapshot(
            snapshot_id=snapshot_id, tenant_id=tenant_id,
            total_models=len([m for m in self._models.values() if m.tenant_id == tenant_id]),
            total_routes=len([r for r in self._routes.values() if r.tenant_id == tenant_id]),
            total_templates=len([t for t in self._templates.values() if t.tenant_id == tenant_id]),
            total_requests=len([r for r in self._requests.values() if r.tenant_id == tenant_id]),
            total_results=len([r for r in self._results.values() if r.tenant_id == tenant_id]),
            total_permissions=len([p for p in self._permissions.values() if p.tenant_id == tenant_id]),
            total_violations=len([v for v in self._violations.values() if v.get("tenant_id") == tenant_id]),
            captured_at=now,
        )
        _emit(self._events, "llm_snapshot", {"snapshot_id": snapshot_id}, snapshot_id)
        return snap

    # -- Violations --
    def detect_llm_violations(self, tenant_id: str) -> tuple[dict[str, Any], ...]:
        new_violations: list[dict[str, Any]] = []

        # 1. Completed results with no grounding check (for sensitive tasks)
        for result in self._results.values():
            if result.tenant_id != tenant_id:
                continue
            if result.grounding_status == GroundingStatus.NOT_CHECKED:
                vid = stable_identifier("viol-llm", {
                    "result_id": result.result_id, "reason": "ungrounded_result",
                })
                if vid not in self._violations:
                    v = {
                        "violation_id": vid, "tenant_id": tenant_id,
                        "result_id": result.result_id, "operation": "ungrounded_result",
                        "reason": f"result {result.result_id} has no grounding check",
                    }
                    self._violations[vid] = v
                    new_violations.append(v)

        # 2. Results with BLOCKED safety verdict
        for result in self._results.values():
            if result.tenant_id != tenant_id:
                continue
            if result.safety_verdict == SafetyVerdict.BLOCKED:
                vid = stable_identifier("viol-llm", {
                    "result_id": result.result_id, "reason": "blocked_safety",
                })
                if vid not in self._violations:
                    v = {
                        "violation_id": vid, "tenant_id": tenant_id,
                        "result_id": result.result_id, "operation": "blocked_safety",
                        "reason": f"result {result.result_id} blocked by safety assessment",
                    }
                    self._violations[vid] = v
                    new_violations.append(v)

        # 3. Models with no routes
        for model in self._models.values():
            if model.tenant_id != tenant_id:
                continue
            if model.status == ModelStatus.ACTIVE:
                routes = [r for r in self._routes.values() if r.model_id == model.model_id]
                if not routes:
                    vid = stable_identifier("viol-llm", {
                        "model_id": model.model_id, "reason": "no_routes",
                    })
                    if vid not in self._violations:
                        v = {
                            "violation_id": vid, "tenant_id": tenant_id,
                            "model_id": model.model_id, "operation": "no_routes",
                            "reason": f"active model {model.model_id} has no provider routes",
                        }
                        self._violations[vid] = v
                        new_violations.append(v)

        if new_violations:
            _emit(self._events, "detect_llm_violations", {
                "tenant_id": tenant_id, "count": len(new_violations),
            }, tenant_id)
        return tuple(new_violations)

    # -- Assessment --
    def llm_assessment(self, assessment_id: str, tenant_id: str) -> LlmAssessment:
        now = _now_iso()
        tenant_models = [m for m in self._models.values() if m.tenant_id == tenant_id]
        tenant_routes = [r for r in self._routes.values() if r.tenant_id == tenant_id]
        tenant_requests = [r for r in self._requests.values() if r.tenant_id == tenant_id]
        tenant_results = [r for r in self._results.values() if r.tenant_id == tenant_id]
        tenant_violations = [v for v in self._violations.values() if v.get("tenant_id") == tenant_id]
        completed = [r for r in tenant_requests if r.status == GenerationStatus.COMPLETED]
        rate = len(completed) / len(tenant_requests) if tenant_requests else 0.0
        assessment = LlmAssessment(
            assessment_id=assessment_id, tenant_id=tenant_id,
            total_models=len(tenant_models), total_routes=len(tenant_routes),
            total_requests=len(tenant_requests), total_results=len(tenant_results),
            total_violations=len(tenant_violations),
            completion_rate=round(rate, 4),
            assessed_at=now,
        )
        _emit(self._events, "llm_assessment", {"assessment_id": assessment_id}, assessment_id)
        return assessment

    # -- Closure report --
    def llm_closure_report(self, report_id: str, tenant_id: str) -> LlmClosureReport:
        now = _now_iso()
        report = LlmClosureReport(
            report_id=report_id, tenant_id=tenant_id,
            total_models=len([m for m in self._models.values() if m.tenant_id == tenant_id]),
            total_routes=len([r for r in self._routes.values() if r.tenant_id == tenant_id]),
            total_requests=len([r for r in self._requests.values() if r.tenant_id == tenant_id]),
            total_results=len([r for r in self._results.values() if r.tenant_id == tenant_id]),
            total_violations=len([v for v in self._violations.values() if v.get("tenant_id") == tenant_id]),
            created_at=now,
        )
        _emit(self._events, "llm_closure_report", {"report_id": report_id}, report_id)
        return report

    # -- State hash --
    def state_hash(self) -> str:
        parts: list[str] = []
        for k in sorted(self._models):
            parts.append(f"model:{k}:{self._models[k].status.value}")
        for k in sorted(self._routes):
            parts.append(f"route:{k}:{self._routes[k].status.value}")
        for k in sorted(self._templates):
            parts.append(f"template:{k}:{self._templates[k].disposition.value}")
        for k in sorted(self._packs):
            parts.append(f"pack:{k}")
        for k in sorted(self._requests):
            parts.append(f"request:{k}:{self._requests[k].status.value}")
        for k in sorted(self._results):
            parts.append(f"result:{k}:{self._results[k].grounding_status.value}")
        for k in sorted(self._permissions):
            parts.append(f"permission:{k}:{self._permissions[k].allowed}")
        for k in sorted(self._evidence):
            parts.append(f"evidence:{k}:{self._evidence[k].grounding_status.value}")
        for k in sorted(self._assessments):
            parts.append(f"assessment:{k}:{self._assessments[k].verdict.value}")
        for k in sorted(self._violations):
            parts.append(f"violation:{k}")
        return sha256("|".join(parts).encode()).hexdigest()
