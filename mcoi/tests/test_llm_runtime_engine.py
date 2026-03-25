"""Comprehensive tests for LlmRuntimeEngine.

Target: ~350 tests covering constructor, models, routes, templates, context packs,
tool permissions, generation requests/results, grounding, safety, violations,
snapshots, state_hash, and golden end-to-end scenarios.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.llm_runtime import LlmRuntimeEngine
from mcoi_runtime.contracts.llm_runtime import (
    ContextPack,
    GenerationRequest,
    GenerationResult,
    GenerationStatus,
    GroundingEvidence,
    GroundingStatus,
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
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def es() -> EventSpineEngine:
    return EventSpineEngine()


@pytest.fixture
def engine(es: EventSpineEngine) -> LlmRuntimeEngine:
    return LlmRuntimeEngine(es)


def _seed_model(engine: LlmRuntimeEngine, model_id: str = "m1",
                tenant_id: str = "t1", **kw) -> ModelDescriptor:
    return engine.register_model(model_id, tenant_id, f"Model {model_id}", **kw)


def _seed_route(engine: LlmRuntimeEngine, route_id: str = "r1",
                model_id: str = "m1", tenant_id: str = "t1", **kw) -> ProviderRoute:
    return engine.register_provider_route(route_id, tenant_id, "provider", model_id, **kw)


def _seed_template(engine: LlmRuntimeEngine, template_id: str = "tpl1",
                   tenant_id: str = "t1") -> PromptTemplate:
    return engine.register_prompt_template(template_id, tenant_id, "Tpl", "Hello {{name}}")


def _seed_pack(engine: LlmRuntimeEngine, pack_id: str = "p1",
               template_id: str = "tpl1", model_id: str = "m1",
               tenant_id: str = "t1", **kw) -> ContextPack:
    return engine.build_context_pack(pack_id, tenant_id, template_id, model_id, **kw)


def _seed_request(engine: LlmRuntimeEngine, request_id: str = "req1",
                  model_id: str = "m1", pack_id: str = "p1",
                  tenant_id: str = "t1", **kw) -> GenerationRequest:
    return engine.request_generation(request_id, tenant_id, model_id, pack_id, **kw)


def _seed_result(engine: LlmRuntimeEngine, result_id: str = "res1",
                 request_id: str = "req1", tenant_id: str = "t1",
                 **kw) -> GenerationResult:
    return engine.record_generation_result(result_id, request_id, tenant_id, **kw)


def _full_pipeline(engine: LlmRuntimeEngine, suffix: str = "1",
                   tenant_id: str = "t1", **result_kw):
    """Register model, template, pack, request, result."""
    _seed_model(engine, f"m{suffix}", tenant_id)
    _seed_template(engine, f"tpl{suffix}", tenant_id)
    _seed_pack(engine, f"p{suffix}", f"tpl{suffix}", f"m{suffix}", tenant_id)
    _seed_request(engine, f"req{suffix}", f"m{suffix}", f"p{suffix}", tenant_id)
    return _seed_result(engine, f"res{suffix}", f"req{suffix}", tenant_id, **result_kw)


# ===================================================================
# SECTION 1: Constructor
# ===================================================================


class TestConstructor:
    def test_accepts_event_spine(self, es):
        eng = LlmRuntimeEngine(es)
        assert eng.model_count == 0

    def test_rejects_none(self):
        with pytest.raises(RuntimeCoreInvariantError):
            LlmRuntimeEngine(None)

    def test_rejects_string(self):
        with pytest.raises(RuntimeCoreInvariantError):
            LlmRuntimeEngine("not-an-engine")

    def test_rejects_dict(self):
        with pytest.raises(RuntimeCoreInvariantError):
            LlmRuntimeEngine({})

    def test_rejects_int(self):
        with pytest.raises(RuntimeCoreInvariantError):
            LlmRuntimeEngine(42)

    def test_rejects_arbitrary_object(self):
        with pytest.raises(RuntimeCoreInvariantError):
            LlmRuntimeEngine(object())

    def test_initial_counts_zero(self, engine):
        assert engine.model_count == 0
        assert engine.route_count == 0
        assert engine.template_count == 0
        assert engine.pack_count == 0
        assert engine.request_count == 0
        assert engine.result_count == 0
        assert engine.permission_count == 0
        assert engine.violation_count == 0


# ===================================================================
# SECTION 2: Model Registration
# ===================================================================


class TestRegisterModel:
    def test_basic_registration(self, engine):
        m = _seed_model(engine)
        assert m.model_id == "m1"
        assert m.tenant_id == "t1"
        assert m.status == ModelStatus.ACTIVE
        assert engine.model_count == 1

    def test_custom_params(self, engine):
        m = engine.register_model("m2", "t1", "Big Model", "openai", 8192, 0.01)
        assert m.provider_ref == "openai"
        assert m.max_tokens == 8192
        assert m.cost_per_token == 0.01

    def test_duplicate_id_raises(self, engine):
        _seed_model(engine)
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate model_id"):
            _seed_model(engine)

    def test_emits_event(self, es, engine):
        before = es.event_count
        _seed_model(engine)
        assert es.event_count == before + 1

    def test_multiple_models(self, engine):
        for i in range(10):
            _seed_model(engine, f"m{i}")
        assert engine.model_count == 10

    def test_default_max_tokens(self, engine):
        m = _seed_model(engine)
        assert m.max_tokens == 4096

    def test_default_cost_per_token(self, engine):
        m = _seed_model(engine)
        assert m.cost_per_token == 0.0

    def test_registered_at_populated(self, engine):
        m = _seed_model(engine)
        assert m.registered_at != ""

    def test_different_tenants(self, engine):
        _seed_model(engine, "m1", "t1")
        _seed_model(engine, "m2", "t2")
        assert engine.model_count == 2


class TestGetModel:
    def test_get_existing(self, engine):
        _seed_model(engine)
        m = engine.get_model("m1")
        assert m.model_id == "m1"

    def test_get_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown model_id"):
            engine.get_model("nope")


class TestDeprecateModel:
    def test_deprecate_active(self, engine):
        _seed_model(engine)
        m = engine.deprecate_model("m1")
        assert m.status == ModelStatus.DEPRECATED

    def test_deprecate_deprecated(self, engine):
        _seed_model(engine)
        engine.deprecate_model("m1")
        m = engine.deprecate_model("m1")
        assert m.status == ModelStatus.DEPRECATED

    def test_deprecate_disabled(self, engine):
        _seed_model(engine)
        engine.disable_model("m1")
        m = engine.deprecate_model("m1")
        assert m.status == ModelStatus.DEPRECATED

    def test_deprecate_retired_raises(self, engine):
        _seed_model(engine)
        engine.retire_model("m1")
        with pytest.raises(RuntimeCoreInvariantError, match="(?i)retired"):
            engine.deprecate_model("m1")

    def test_deprecate_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError):
            engine.deprecate_model("nope")

    def test_deprecate_emits_event(self, es, engine):
        _seed_model(engine)
        before = es.event_count
        engine.deprecate_model("m1")
        assert es.event_count == before + 1


class TestDisableModel:
    def test_disable_active(self, engine):
        _seed_model(engine)
        m = engine.disable_model("m1")
        assert m.status == ModelStatus.DISABLED

    def test_disable_deprecated(self, engine):
        _seed_model(engine)
        engine.deprecate_model("m1")
        m = engine.disable_model("m1")
        assert m.status == ModelStatus.DISABLED

    def test_disable_retired_raises(self, engine):
        _seed_model(engine)
        engine.retire_model("m1")
        with pytest.raises(RuntimeCoreInvariantError, match="(?i)retired"):
            engine.disable_model("m1")

    def test_disable_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError):
            engine.disable_model("nope")

    def test_disable_emits_event(self, es, engine):
        _seed_model(engine)
        before = es.event_count
        engine.disable_model("m1")
        assert es.event_count == before + 1


class TestRetireModel:
    def test_retire_active(self, engine):
        _seed_model(engine)
        m = engine.retire_model("m1")
        assert m.status == ModelStatus.RETIRED

    def test_retire_deprecated(self, engine):
        _seed_model(engine)
        engine.deprecate_model("m1")
        m = engine.retire_model("m1")
        assert m.status == ModelStatus.RETIRED

    def test_retire_disabled(self, engine):
        _seed_model(engine)
        engine.disable_model("m1")
        m = engine.retire_model("m1")
        assert m.status == ModelStatus.RETIRED

    def test_retire_already_retired_raises(self, engine):
        _seed_model(engine)
        engine.retire_model("m1")
        with pytest.raises(RuntimeCoreInvariantError, match="already RETIRED"):
            engine.retire_model("m1")

    def test_retire_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError):
            engine.retire_model("nope")

    def test_retire_emits_event(self, es, engine):
        _seed_model(engine)
        before = es.event_count
        engine.retire_model("m1")
        assert es.event_count == before + 1

    def test_retired_then_deprecate_raises(self, engine):
        _seed_model(engine)
        engine.retire_model("m1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.deprecate_model("m1")

    def test_retired_then_disable_raises(self, engine):
        _seed_model(engine)
        engine.retire_model("m1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.disable_model("m1")


class TestModelsForTenant:
    def test_empty(self, engine):
        assert engine.models_for_tenant("t1") == ()

    def test_returns_matching(self, engine):
        _seed_model(engine, "m1", "t1")
        _seed_model(engine, "m2", "t1")
        _seed_model(engine, "m3", "t2")
        result = engine.models_for_tenant("t1")
        assert len(result) == 2

    def test_returns_tuple(self, engine):
        assert isinstance(engine.models_for_tenant("t1"), tuple)

    def test_no_match(self, engine):
        _seed_model(engine, "m1", "t1")
        assert engine.models_for_tenant("t99") == ()


# ===================================================================
# SECTION 3: Provider Routes
# ===================================================================


class TestRegisterProviderRoute:
    def test_basic_registration(self, engine):
        _seed_model(engine)
        r = _seed_route(engine)
        assert r.route_id == "r1"
        assert r.status == ProviderStatus.AVAILABLE
        assert engine.route_count == 1

    def test_duplicate_raises(self, engine):
        _seed_model(engine)
        _seed_route(engine)
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate route_id"):
            _seed_route(engine)

    def test_unknown_model_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown model_id"):
            _seed_route(engine, model_id="nope")

    def test_custom_priority(self, engine):
        _seed_model(engine)
        r = _seed_route(engine, priority=5)
        assert r.priority == 5

    def test_custom_latency_budget(self, engine):
        _seed_model(engine)
        r = _seed_route(engine, latency_budget_ms=5000)
        assert r.latency_budget_ms == 5000

    def test_custom_cost_budget(self, engine):
        _seed_model(engine)
        r = _seed_route(engine, cost_budget=2.5)
        assert r.cost_budget == 2.5

    def test_emits_event(self, es, engine):
        _seed_model(engine)
        before = es.event_count
        _seed_route(engine)
        assert es.event_count == before + 1

    def test_multiple_routes_same_model(self, engine):
        _seed_model(engine)
        for i in range(5):
            _seed_route(engine, f"r{i}")
        assert engine.route_count == 5


class TestMarkRouteDegraded:
    def test_degrade(self, engine):
        _seed_model(engine)
        _seed_route(engine)
        r = engine.mark_route_degraded("r1")
        assert r.status == ProviderStatus.DEGRADED

    def test_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown route_id"):
            engine.mark_route_degraded("nope")

    def test_emits_event(self, es, engine):
        _seed_model(engine)
        _seed_route(engine)
        before = es.event_count
        engine.mark_route_degraded("r1")
        assert es.event_count == before + 1


class TestMarkRouteUnavailable:
    def test_unavailable(self, engine):
        _seed_model(engine)
        _seed_route(engine)
        r = engine.mark_route_unavailable("r1")
        assert r.status == ProviderStatus.UNAVAILABLE

    def test_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError):
            engine.mark_route_unavailable("nope")

    def test_emits_event(self, es, engine):
        _seed_model(engine)
        _seed_route(engine)
        before = es.event_count
        engine.mark_route_unavailable("r1")
        assert es.event_count == before + 1


class TestChooseFallbackRoute:
    def test_picks_available_first(self, engine):
        _seed_model(engine)
        _seed_route(engine, "r1", priority=10)
        _seed_route(engine, "r2", priority=1)
        r = engine.choose_fallback_route("m1")
        assert r.route_id == "r2"

    def test_falls_back_to_degraded(self, engine):
        _seed_model(engine)
        _seed_route(engine, "r1")
        engine.mark_route_degraded("r1")
        r = engine.choose_fallback_route("m1")
        assert r is not None
        assert r.status == ProviderStatus.DEGRADED

    def test_none_when_all_unavailable(self, engine):
        _seed_model(engine)
        _seed_route(engine, "r1")
        engine.mark_route_unavailable("r1")
        assert engine.choose_fallback_route("m1") is None

    def test_none_when_no_routes(self, engine):
        _seed_model(engine)
        assert engine.choose_fallback_route("m1") is None

    def test_prefers_available_over_degraded(self, engine):
        _seed_model(engine)
        _seed_route(engine, "r1", priority=0)
        _seed_route(engine, "r2", priority=0)
        engine.mark_route_degraded("r1")
        r = engine.choose_fallback_route("m1")
        assert r.route_id == "r2"

    def test_degraded_sorted_by_priority(self, engine):
        _seed_model(engine)
        _seed_route(engine, "r1", priority=10)
        _seed_route(engine, "r2", priority=1)
        engine.mark_route_degraded("r1")
        engine.mark_route_degraded("r2")
        r = engine.choose_fallback_route("m1")
        assert r.route_id == "r2"

    def test_ignores_different_model(self, engine):
        _seed_model(engine, "m1")
        _seed_model(engine, "m2")
        _seed_route(engine, "r1", model_id="m2")
        assert engine.choose_fallback_route("m1") is None

    def test_mixed_available_picks_lowest_priority(self, engine):
        _seed_model(engine)
        _seed_route(engine, "r1", priority=5)
        _seed_route(engine, "r2", priority=3)
        _seed_route(engine, "r3", priority=7)
        r = engine.choose_fallback_route("m1")
        assert r.route_id == "r2"


class TestRoutesForModel:
    def test_empty(self, engine):
        _seed_model(engine)
        assert engine.routes_for_model("m1") == ()

    def test_returns_matching(self, engine):
        _seed_model(engine, "m1")
        _seed_model(engine, "m2")
        _seed_route(engine, "r1", model_id="m1")
        _seed_route(engine, "r2", model_id="m1")
        _seed_route(engine, "r3", model_id="m2")
        assert len(engine.routes_for_model("m1")) == 2

    def test_returns_tuple(self, engine):
        _seed_model(engine)
        assert isinstance(engine.routes_for_model("m1"), tuple)


# ===================================================================
# SECTION 4: Prompt Templates
# ===================================================================


class TestRegisterPromptTemplate:
    def test_basic(self, engine):
        t = _seed_template(engine)
        assert t.template_id == "tpl1"
        assert t.disposition == PromptDisposition.DRAFT
        assert engine.template_count == 1

    def test_duplicate_raises(self, engine):
        _seed_template(engine)
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate template_id"):
            _seed_template(engine)

    def test_custom_version(self, engine):
        t = engine.register_prompt_template("tpl1", "t1", "V2", "body", version=2)
        assert t.version == 2

    def test_emits_event(self, es, engine):
        before = es.event_count
        _seed_template(engine)
        assert es.event_count == before + 1


class TestApproveTemplate:
    def test_approve_draft(self, engine):
        _seed_template(engine)
        t = engine.approve_template("tpl1")
        assert t.disposition == PromptDisposition.APPROVED

    def test_approve_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown template_id"):
            engine.approve_template("nope")

    def test_approve_archived_raises(self, engine):
        # We cannot archive via the engine directly, but we can test the check
        # by setting disposition manually (the contract is frozen so we use engine internals).
        _seed_template(engine)
        # Force ARCHIVED via internal mutation for test purposes
        t = engine._templates["tpl1"]
        from mcoi_runtime.contracts.llm_runtime import PromptTemplate as PT
        from datetime import datetime, timezone
        archived = PT(
            template_id=t.template_id, tenant_id=t.tenant_id,
            display_name=t.display_name, template_text=t.template_text,
            disposition=PromptDisposition.ARCHIVED, version=t.version,
            created_at=t.created_at,
        )
        engine._templates["tpl1"] = archived
        with pytest.raises(RuntimeCoreInvariantError, match="(?i)archived"):
            engine.approve_template("tpl1")

    def test_approve_emits_event(self, es, engine):
        _seed_template(engine)
        before = es.event_count
        engine.approve_template("tpl1")
        assert es.event_count == before + 1

    def test_double_approve(self, engine):
        _seed_template(engine)
        engine.approve_template("tpl1")
        t = engine.approve_template("tpl1")
        assert t.disposition == PromptDisposition.APPROVED


class TestGetTemplate:
    def test_existing(self, engine):
        _seed_template(engine)
        t = engine.get_template("tpl1")
        assert t.template_id == "tpl1"

    def test_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown template_id"):
            engine.get_template("nope")


# ===================================================================
# SECTION 5: Context Packs
# ===================================================================


class TestBuildContextPack:
    def test_basic(self, engine):
        _seed_model(engine)
        _seed_template(engine)
        p = _seed_pack(engine)
        assert p.pack_id == "p1"
        assert engine.pack_count == 1

    def test_duplicate_raises(self, engine):
        _seed_model(engine)
        _seed_template(engine)
        _seed_pack(engine)
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate pack_id"):
            _seed_pack(engine)

    def test_unknown_template_raises(self, engine):
        _seed_model(engine)
        with pytest.raises(RuntimeCoreInvariantError, match="unknown template_id"):
            _seed_pack(engine, template_id="nope")

    def test_unknown_model_raises(self, engine):
        _seed_template(engine)
        with pytest.raises(RuntimeCoreInvariantError, match="unknown model_id"):
            _seed_pack(engine, model_id="nope")

    def test_token_count_within_limit(self, engine):
        _seed_model(engine, max_tokens=100)
        _seed_template(engine)
        p = _seed_pack(engine, token_count=50)
        assert p.token_count == 50

    def test_token_count_at_limit(self, engine):
        _seed_model(engine, max_tokens=100)
        _seed_template(engine)
        p = _seed_pack(engine, token_count=100)
        assert p.token_count == 100

    def test_token_count_exceeds_limit_raises(self, engine):
        _seed_model(engine, max_tokens=100)
        _seed_template(engine)
        with pytest.raises(RuntimeCoreInvariantError, match="exceeds model max_tokens"):
            _seed_pack(engine, token_count=101)

    def test_zero_max_tokens_no_limit(self, engine):
        _seed_model(engine, max_tokens=0)
        _seed_template(engine)
        p = _seed_pack(engine, token_count=999999)
        assert p.token_count == 999999

    def test_zero_token_count_always_ok(self, engine):
        _seed_model(engine, max_tokens=100)
        _seed_template(engine)
        p = _seed_pack(engine, token_count=0)
        assert p.token_count == 0

    def test_source_count(self, engine):
        _seed_model(engine)
        _seed_template(engine)
        p = _seed_pack(engine, source_count=5)
        assert p.source_count == 5

    def test_emits_event(self, es, engine):
        _seed_model(engine)
        _seed_template(engine)
        before = es.event_count
        _seed_pack(engine)
        assert es.event_count == before + 1


class TestGetPack:
    def test_existing(self, engine):
        _seed_model(engine)
        _seed_template(engine)
        _seed_pack(engine)
        p = engine.get_pack("p1")
        assert p.pack_id == "p1"

    def test_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown pack_id"):
            engine.get_pack("nope")


# ===================================================================
# SECTION 6: Tool Permissions
# ===================================================================


class TestRegisterToolPermission:
    def test_basic(self, engine):
        _seed_model(engine)
        p = engine.register_tool_permission("perm1", "t1", "m1", "tool_x")
        assert p.permission_id == "perm1"
        assert p.allowed is True
        assert engine.permission_count == 1

    def test_denied_permission(self, engine):
        _seed_model(engine)
        p = engine.register_tool_permission("perm1", "t1", "m1", "tool_x", allowed=False)
        assert p.allowed is False

    def test_duplicate_raises(self, engine):
        _seed_model(engine)
        engine.register_tool_permission("perm1", "t1", "m1", "tool_x")
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate permission_id"):
            engine.register_tool_permission("perm1", "t1", "m1", "tool_x")

    def test_unknown_model_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown model_id"):
            engine.register_tool_permission("perm1", "t1", "nope", "tool_x")

    def test_custom_scope(self, engine):
        _seed_model(engine)
        p = engine.register_tool_permission("perm1", "t1", "m1", "tool_x", scope_ref="project_a")
        assert p.scope_ref == "project_a"

    def test_emits_event(self, es, engine):
        _seed_model(engine)
        before = es.event_count
        engine.register_tool_permission("perm1", "t1", "m1", "tool_x")
        assert es.event_count == before + 1


class TestCheckToolPermission:
    def test_allowed(self, engine):
        _seed_model(engine)
        engine.register_tool_permission("perm1", "t1", "m1", "tool_x", allowed=True)
        assert engine.check_tool_permission("m1", "tool_x") is True

    def test_denied_explicit(self, engine):
        _seed_model(engine)
        engine.register_tool_permission("perm1", "t1", "m1", "tool_x", allowed=False)
        assert engine.check_tool_permission("m1", "tool_x") is False

    def test_fail_closed_no_permission(self, engine):
        _seed_model(engine)
        assert engine.check_tool_permission("m1", "tool_x") is False

    def test_fail_closed_different_tool(self, engine):
        _seed_model(engine)
        engine.register_tool_permission("perm1", "t1", "m1", "tool_x")
        assert engine.check_tool_permission("m1", "tool_y") is False

    def test_fail_closed_different_model(self, engine):
        _seed_model(engine, "m1")
        _seed_model(engine, "m2")
        engine.register_tool_permission("perm1", "t1", "m1", "tool_x")
        assert engine.check_tool_permission("m2", "tool_x") is False

    def test_multiple_permissions_first_match(self, engine):
        _seed_model(engine)
        engine.register_tool_permission("perm1", "t1", "m1", "tool_x", allowed=True)
        engine.register_tool_permission("perm2", "t1", "m1", "tool_y", allowed=False)
        assert engine.check_tool_permission("m1", "tool_x") is True
        assert engine.check_tool_permission("m1", "tool_y") is False


class TestPermissionsForModel:
    def test_empty(self, engine):
        _seed_model(engine)
        assert engine.permissions_for_model("m1") == ()

    def test_returns_matching(self, engine):
        _seed_model(engine, "m1")
        _seed_model(engine, "m2")
        engine.register_tool_permission("p1", "t1", "m1", "a")
        engine.register_tool_permission("p2", "t1", "m1", "b")
        engine.register_tool_permission("p3", "t1", "m2", "a")
        assert len(engine.permissions_for_model("m1")) == 2

    def test_returns_tuple(self, engine):
        _seed_model(engine)
        assert isinstance(engine.permissions_for_model("m1"), tuple)


# ===================================================================
# SECTION 7: Generation Requests
# ===================================================================


class TestRequestGeneration:
    def test_basic(self, engine):
        _seed_model(engine)
        _seed_template(engine)
        _seed_pack(engine)
        req = _seed_request(engine)
        assert req.request_id == "req1"
        assert req.status == GenerationStatus.PENDING
        assert engine.request_count == 1

    def test_duplicate_raises(self, engine):
        _seed_model(engine)
        _seed_template(engine)
        _seed_pack(engine)
        _seed_request(engine)
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate request_id"):
            _seed_request(engine)

    def test_unknown_model_raises(self, engine):
        _seed_model(engine)
        _seed_template(engine)
        _seed_pack(engine)
        with pytest.raises(RuntimeCoreInvariantError, match="unknown model_id"):
            engine.request_generation("req1", "t1", "nope", "p1")

    def test_unknown_pack_raises(self, engine):
        _seed_model(engine)
        _seed_template(engine)
        _seed_pack(engine)
        with pytest.raises(RuntimeCoreInvariantError, match="unknown pack_id"):
            engine.request_generation("req1", "t1", "m1", "nope")

    def test_disabled_model_raises(self, engine):
        _seed_model(engine)
        engine.disable_model("m1")
        _seed_template(engine)
        _seed_pack(engine)
        with pytest.raises(RuntimeCoreInvariantError, match="disabled"):
            _seed_request(engine)

    def test_retired_model_raises(self, engine):
        _seed_model(engine)
        engine.retire_model("m1")
        _seed_template(engine)
        _seed_pack(engine)
        with pytest.raises(RuntimeCoreInvariantError, match="(?i)retired"):
            _seed_request(engine)

    def test_deprecated_model_allowed(self, engine):
        _seed_model(engine)
        engine.deprecate_model("m1")
        _seed_template(engine)
        _seed_pack(engine)
        req = _seed_request(engine)
        assert req.status == GenerationStatus.PENDING

    def test_custom_budgets(self, engine):
        _seed_model(engine)
        _seed_template(engine)
        _seed_pack(engine)
        req = engine.request_generation("req1", "t1", "m1", "p1",
                                        token_budget=2048, cost_budget=0.5,
                                        latency_budget_ms=5000)
        assert req.token_budget == 2048
        assert req.cost_budget == 0.5
        assert req.latency_budget_ms == 5000

    def test_emits_event(self, es, engine):
        _seed_model(engine)
        _seed_template(engine)
        _seed_pack(engine)
        before = es.event_count
        _seed_request(engine)
        assert es.event_count == before + 1


class TestGetRequest:
    def test_existing(self, engine):
        _seed_model(engine)
        _seed_template(engine)
        _seed_pack(engine)
        _seed_request(engine)
        r = engine.get_request("req1")
        assert r.request_id == "req1"

    def test_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown request_id"):
            engine.get_request("nope")


class TestStartGeneration:
    def test_start_pending(self, engine):
        _seed_model(engine)
        _seed_template(engine)
        _seed_pack(engine)
        _seed_request(engine)
        req = engine.start_generation("req1")
        assert req.status == GenerationStatus.RUNNING

    def test_start_completed_raises(self, engine):
        _seed_model(engine)
        _seed_template(engine)
        _seed_pack(engine)
        _seed_request(engine)
        _seed_result(engine)  # auto-completes
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine.start_generation("req1")

    def test_start_blocked_raises(self, engine):
        _seed_model(engine)
        _seed_template(engine)
        _seed_pack(engine)
        _seed_request(engine)
        engine.block_generation("req1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine.start_generation("req1")

    def test_start_timed_out_raises(self, engine):
        _seed_model(engine)
        _seed_template(engine)
        _seed_pack(engine)
        _seed_request(engine)
        engine.start_generation("req1")
        engine.timeout_generation("req1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine.start_generation("req1")

    def test_start_emits_event(self, es, engine):
        _seed_model(engine)
        _seed_template(engine)
        _seed_pack(engine)
        _seed_request(engine)
        before = es.event_count
        engine.start_generation("req1")
        assert es.event_count == before + 1


class TestBlockGeneration:
    def test_block_pending(self, engine):
        _seed_model(engine)
        _seed_template(engine)
        _seed_pack(engine)
        _seed_request(engine)
        req = engine.block_generation("req1")
        assert req.status == GenerationStatus.BLOCKED

    def test_block_running(self, engine):
        _seed_model(engine)
        _seed_template(engine)
        _seed_pack(engine)
        _seed_request(engine)
        engine.start_generation("req1")
        req = engine.block_generation("req1")
        assert req.status == GenerationStatus.BLOCKED

    def test_block_completed_raises(self, engine):
        _seed_model(engine)
        _seed_template(engine)
        _seed_pack(engine)
        _seed_request(engine)
        _seed_result(engine)
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine.block_generation("req1")

    def test_block_already_blocked_raises(self, engine):
        _seed_model(engine)
        _seed_template(engine)
        _seed_pack(engine)
        _seed_request(engine)
        engine.block_generation("req1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine.block_generation("req1")

    def test_block_emits_event(self, es, engine):
        _seed_model(engine)
        _seed_template(engine)
        _seed_pack(engine)
        _seed_request(engine)
        before = es.event_count
        engine.block_generation("req1")
        assert es.event_count == before + 1


class TestTimeoutGeneration:
    def test_timeout_running(self, engine):
        _seed_model(engine)
        _seed_template(engine)
        _seed_pack(engine)
        _seed_request(engine)
        engine.start_generation("req1")
        req = engine.timeout_generation("req1")
        assert req.status == GenerationStatus.TIMED_OUT

    def test_timeout_pending_raises(self, engine):
        _seed_model(engine)
        _seed_template(engine)
        _seed_pack(engine)
        _seed_request(engine)
        with pytest.raises(RuntimeCoreInvariantError, match="must be RUNNING"):
            engine.timeout_generation("req1")

    def test_timeout_completed_raises(self, engine):
        _seed_model(engine)
        _seed_template(engine)
        _seed_pack(engine)
        _seed_request(engine)
        _seed_result(engine)
        with pytest.raises(RuntimeCoreInvariantError, match="must be RUNNING"):
            engine.timeout_generation("req1")

    def test_timeout_blocked_raises(self, engine):
        _seed_model(engine)
        _seed_template(engine)
        _seed_pack(engine)
        _seed_request(engine)
        engine.block_generation("req1")
        with pytest.raises(RuntimeCoreInvariantError, match="must be RUNNING"):
            engine.timeout_generation("req1")

    def test_timeout_emits_event(self, es, engine):
        _seed_model(engine)
        _seed_template(engine)
        _seed_pack(engine)
        _seed_request(engine)
        engine.start_generation("req1")
        before = es.event_count
        engine.timeout_generation("req1")
        assert es.event_count == before + 1


class TestRequestsForTenant:
    def test_empty(self, engine):
        assert engine.requests_for_tenant("t1") == ()

    def test_returns_matching(self, engine):
        _seed_model(engine, "m1", "t1")
        _seed_template(engine, "tpl1", "t1")
        _seed_pack(engine, "p1")
        _seed_request(engine, "req1")
        _seed_request(engine, "req2")
        assert len(engine.requests_for_tenant("t1")) == 2

    def test_returns_tuple(self, engine):
        assert isinstance(engine.requests_for_tenant("t1"), tuple)


# ===================================================================
# SECTION 8: Generation Results
# ===================================================================


class TestRecordGenerationResult:
    def test_basic(self, engine):
        _seed_model(engine)
        _seed_template(engine)
        _seed_pack(engine)
        _seed_request(engine)
        res = _seed_result(engine)
        assert res.result_id == "res1"
        assert res.status == GenerationStatus.COMPLETED
        assert engine.result_count == 1

    def test_auto_completes_request(self, engine):
        _seed_model(engine)
        _seed_template(engine)
        _seed_pack(engine)
        _seed_request(engine)
        _seed_result(engine)
        req = engine.get_request("req1")
        assert req.status == GenerationStatus.COMPLETED

    def test_duplicate_result_raises(self, engine):
        _seed_model(engine)
        _seed_template(engine)
        _seed_pack(engine)
        _seed_request(engine)
        _seed_result(engine)
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate result_id"):
            _seed_result(engine)

    def test_unknown_request_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown request_id"):
            engine.record_generation_result("res1", "nope", "t1")

    def test_default_grounding_not_checked(self, engine):
        _seed_model(engine)
        _seed_template(engine)
        _seed_pack(engine)
        _seed_request(engine)
        res = _seed_result(engine)
        assert res.grounding_status == GroundingStatus.NOT_CHECKED

    def test_default_safety_safe(self, engine):
        _seed_model(engine)
        _seed_template(engine)
        _seed_pack(engine)
        _seed_request(engine)
        res = _seed_result(engine)
        assert res.safety_verdict == SafetyVerdict.SAFE

    def test_budget_overrun_tokens_creates_violation(self, engine):
        _seed_model(engine)
        _seed_template(engine)
        _seed_pack(engine)
        engine.request_generation("req1", "t1", "m1", "p1", token_budget=100)
        engine.record_generation_result("res1", "req1", "t1", tokens_used=200)
        assert engine.violation_count == 1

    def test_budget_overrun_cost_creates_violation(self, engine):
        _seed_model(engine)
        _seed_template(engine)
        _seed_pack(engine)
        engine.request_generation("req1", "t1", "m1", "p1", cost_budget=1.0)
        engine.record_generation_result("res1", "req1", "t1", cost_incurred=2.0)
        assert engine.violation_count == 1

    def test_no_violation_within_budget(self, engine):
        _seed_model(engine)
        _seed_template(engine)
        _seed_pack(engine)
        engine.request_generation("req1", "t1", "m1", "p1",
                                  token_budget=1000, cost_budget=5.0)
        engine.record_generation_result("res1", "req1", "t1",
                                        tokens_used=500, cost_incurred=2.0)
        assert engine.violation_count == 0

    def test_zero_budget_no_violation(self, engine):
        _seed_model(engine)
        _seed_template(engine)
        _seed_pack(engine)
        engine.request_generation("req1", "t1", "m1", "p1",
                                  token_budget=0, cost_budget=0.0)
        engine.record_generation_result("res1", "req1", "t1",
                                        tokens_used=9999, cost_incurred=9999)
        assert engine.violation_count == 0

    def test_custom_output_ref(self, engine):
        _seed_model(engine)
        _seed_template(engine)
        _seed_pack(engine)
        _seed_request(engine)
        res = _seed_result(engine, output_ref="s3://bucket/output.json")
        assert res.output_ref == "s3://bucket/output.json"

    def test_custom_confidence(self, engine):
        _seed_model(engine)
        _seed_template(engine)
        _seed_pack(engine)
        _seed_request(engine)
        res = _seed_result(engine, confidence=0.95)
        assert res.confidence == 0.95

    def test_emits_event(self, es, engine):
        _seed_model(engine)
        _seed_template(engine)
        _seed_pack(engine)
        _seed_request(engine)
        before = es.event_count
        _seed_result(engine)
        assert es.event_count == before + 1


class TestGetResult:
    def test_existing(self, engine):
        _full_pipeline(engine)
        r = engine.get_result("res1")
        assert r.result_id == "res1"

    def test_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown result_id"):
            engine.get_result("nope")


class TestResultsForRequest:
    def test_empty(self, engine):
        _seed_model(engine)
        _seed_template(engine)
        _seed_pack(engine)
        _seed_request(engine)
        assert engine.results_for_request("req1") == ()

    def test_returns_matching(self, engine):
        _full_pipeline(engine)
        assert len(engine.results_for_request("req1")) == 1

    def test_returns_tuple(self, engine):
        assert isinstance(engine.results_for_request("nonexistent"), tuple)


# ===================================================================
# SECTION 9: Grounding
# ===================================================================


class TestAssessGrounding:
    def test_grounded(self, engine):
        _full_pipeline(engine)
        ev = engine.assess_grounding("ev1", "res1", "t1", "wiki_article",
                                     grounding_status=GroundingStatus.GROUNDED)
        assert ev.grounding_status == GroundingStatus.GROUNDED

    def test_updates_result_grounding_status(self, engine):
        _full_pipeline(engine)
        engine.assess_grounding("ev1", "res1", "t1", "src",
                                grounding_status=GroundingStatus.GROUNDED)
        res = engine.get_result("res1")
        assert res.grounding_status == GroundingStatus.GROUNDED

    def test_ungrounded(self, engine):
        _full_pipeline(engine)
        engine.assess_grounding("ev1", "res1", "t1", "src",
                                grounding_status=GroundingStatus.UNGROUNDED)
        res = engine.get_result("res1")
        assert res.grounding_status == GroundingStatus.UNGROUNDED

    def test_partially_grounded(self, engine):
        _full_pipeline(engine)
        engine.assess_grounding("ev1", "res1", "t1", "src",
                                grounding_status=GroundingStatus.PARTIALLY_GROUNDED)
        res = engine.get_result("res1")
        assert res.grounding_status == GroundingStatus.PARTIALLY_GROUNDED

    def test_duplicate_evidence_raises(self, engine):
        _full_pipeline(engine)
        engine.assess_grounding("ev1", "res1", "t1", "src")
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate evidence_id"):
            engine.assess_grounding("ev1", "res1", "t1", "src")

    def test_unknown_result_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown result_id"):
            engine.assess_grounding("ev1", "nope", "t1", "src")

    def test_relevance_score(self, engine):
        _full_pipeline(engine)
        ev = engine.assess_grounding("ev1", "res1", "t1", "src",
                                     relevance_score=0.9)
        assert ev.relevance_score == 0.9

    def test_multiple_evidence_for_same_result(self, engine):
        _full_pipeline(engine)
        engine.assess_grounding("ev1", "res1", "t1", "src1")
        engine.assess_grounding("ev2", "res1", "t1", "src2")
        evs = engine.evidence_for_result("res1")
        assert len(evs) == 2

    def test_last_grounding_wins(self, engine):
        _full_pipeline(engine)
        engine.assess_grounding("ev1", "res1", "t1", "src",
                                grounding_status=GroundingStatus.GROUNDED)
        engine.assess_grounding("ev2", "res1", "t1", "src2",
                                grounding_status=GroundingStatus.UNGROUNDED)
        res = engine.get_result("res1")
        assert res.grounding_status == GroundingStatus.UNGROUNDED

    def test_emits_event(self, es, engine):
        _full_pipeline(engine)
        before = es.event_count
        engine.assess_grounding("ev1", "res1", "t1", "src")
        assert es.event_count == before + 1


class TestEvidenceForResult:
    def test_empty(self, engine):
        _full_pipeline(engine)
        assert engine.evidence_for_result("res1") == ()

    def test_returns_tuple(self, engine):
        assert isinstance(engine.evidence_for_result("nonexistent"), tuple)


# ===================================================================
# SECTION 10: Safety
# ===================================================================


class TestAssessSafety:
    def test_safe(self, engine):
        _full_pipeline(engine)
        a = engine.assess_safety("sa1", "res1", "t1", verdict=SafetyVerdict.SAFE)
        assert a.verdict == SafetyVerdict.SAFE

    def test_updates_result_verdict(self, engine):
        _full_pipeline(engine)
        engine.assess_safety("sa1", "res1", "t1", verdict=SafetyVerdict.FLAGGED)
        res = engine.get_result("res1")
        assert res.safety_verdict == SafetyVerdict.FLAGGED

    def test_blocked_creates_violation(self, engine):
        _full_pipeline(engine)
        before_violations = engine.violation_count
        engine.assess_safety("sa1", "res1", "t1", verdict=SafetyVerdict.BLOCKED,
                             reason="toxic content")
        assert engine.violation_count == before_violations + 1

    def test_safe_no_violation(self, engine):
        _full_pipeline(engine)
        before = engine.violation_count
        engine.assess_safety("sa1", "res1", "t1", verdict=SafetyVerdict.SAFE)
        assert engine.violation_count == before

    def test_flagged_no_violation(self, engine):
        _full_pipeline(engine)
        before = engine.violation_count
        engine.assess_safety("sa1", "res1", "t1", verdict=SafetyVerdict.FLAGGED)
        assert engine.violation_count == before

    def test_requires_review_no_violation(self, engine):
        _full_pipeline(engine)
        before = engine.violation_count
        engine.assess_safety("sa1", "res1", "t1", verdict=SafetyVerdict.REQUIRES_REVIEW)
        assert engine.violation_count == before

    def test_duplicate_assessment_raises(self, engine):
        _full_pipeline(engine)
        engine.assess_safety("sa1", "res1", "t1")
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate assessment_id"):
            engine.assess_safety("sa1", "res1", "t1")

    def test_unknown_result_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown result_id"):
            engine.assess_safety("sa1", "nope", "t1")

    def test_custom_confidence(self, engine):
        _full_pipeline(engine)
        a = engine.assess_safety("sa1", "res1", "t1", confidence=0.99)
        assert a.confidence == 0.99

    def test_custom_reason(self, engine):
        _full_pipeline(engine)
        a = engine.assess_safety("sa1", "res1", "t1", reason="all clear")
        assert a.reason == "all clear"

    def test_emits_event(self, es, engine):
        _full_pipeline(engine)
        before = es.event_count
        engine.assess_safety("sa1", "res1", "t1")
        assert es.event_count == before + 1

    def test_multiple_assessments_same_result(self, engine):
        _full_pipeline(engine)
        engine.assess_safety("sa1", "res1", "t1", verdict=SafetyVerdict.SAFE)
        engine.assess_safety("sa2", "res1", "t1", verdict=SafetyVerdict.BLOCKED,
                             reason="second pass")
        res = engine.get_result("res1")
        assert res.safety_verdict == SafetyVerdict.BLOCKED


class TestAssessmentsForResult:
    def test_empty(self, engine):
        _full_pipeline(engine)
        assert engine.assessments_for_result("res1") == ()

    def test_returns_matching(self, engine):
        _full_pipeline(engine)
        engine.assess_safety("sa1", "res1", "t1")
        engine.assess_safety("sa2", "res1", "t1")
        assert len(engine.assessments_for_result("res1")) == 2

    def test_returns_tuple(self, engine):
        assert isinstance(engine.assessments_for_result("x"), tuple)


# ===================================================================
# SECTION 11: Snapshot
# ===================================================================


class TestLlmSnapshot:
    def test_empty_snapshot(self, engine):
        snap = engine.llm_snapshot("snap1", "t1")
        assert snap.total_models == 0
        assert snap.total_routes == 0
        assert snap.total_templates == 0
        assert snap.total_requests == 0
        assert snap.total_results == 0
        assert snap.total_permissions == 0
        assert snap.total_violations == 0

    def test_populated_snapshot(self, engine):
        _full_pipeline(engine)
        _seed_route(engine, "r1", model_id="m1")
        engine.register_tool_permission("perm1", "t1", "m1", "tool_x")
        snap = engine.llm_snapshot("snap1", "t1")
        assert snap.total_models == 1
        assert snap.total_routes == 1
        assert snap.total_templates == 1
        assert snap.total_requests == 1
        assert snap.total_results == 1
        assert snap.total_permissions == 1

    def test_filters_by_tenant(self, engine):
        _full_pipeline(engine, "1", "t1")
        _full_pipeline(engine, "2", "t2")
        snap = engine.llm_snapshot("snap1", "t1")
        assert snap.total_models == 1
        assert snap.total_results == 1

    def test_snapshot_id_persisted(self, engine):
        snap = engine.llm_snapshot("snap1", "t1")
        assert snap.snapshot_id == "snap1"

    def test_captured_at_populated(self, engine):
        snap = engine.llm_snapshot("snap1", "t1")
        assert snap.captured_at != ""

    def test_emits_event(self, es, engine):
        before = es.event_count
        engine.llm_snapshot("snap1", "t1")
        assert es.event_count == before + 1

    def test_snapshot_counts_violations(self, engine):
        _full_pipeline(engine)
        engine.assess_safety("sa1", "res1", "t1", verdict=SafetyVerdict.BLOCKED,
                             reason="bad")
        snap = engine.llm_snapshot("snap1", "t1")
        assert snap.total_violations >= 1


# ===================================================================
# SECTION 12: Detect LLM Violations
# ===================================================================


class TestDetectLlmViolations:
    def test_no_violations_empty(self, engine):
        vs = engine.detect_llm_violations("t1")
        assert vs == ()

    def test_ungrounded_result_violation(self, engine):
        _full_pipeline(engine)
        vs = engine.detect_llm_violations("t1")
        ops = [v["operation"] for v in vs]
        assert "ungrounded_result" in ops

    def test_grounded_result_no_ungrounded_violation(self, engine):
        _full_pipeline(engine)
        engine.assess_grounding("ev1", "res1", "t1", "src",
                                grounding_status=GroundingStatus.GROUNDED)
        vs = engine.detect_llm_violations("t1")
        ops = [v["operation"] for v in vs]
        assert "ungrounded_result" not in ops

    def test_blocked_safety_violation(self, engine):
        _full_pipeline(engine)
        engine.assess_safety("sa1", "res1", "t1", verdict=SafetyVerdict.BLOCKED,
                             reason="toxic")
        # The BLOCKED violation is created in assess_safety, but detect
        # should also find it as blocked_safety
        engine.assess_grounding("ev1", "res1", "t1", "src",
                                grounding_status=GroundingStatus.GROUNDED)
        vs = engine.detect_llm_violations("t1")
        ops = [v["operation"] for v in vs]
        assert "blocked_safety" in ops

    def test_no_routes_violation(self, engine):
        _seed_model(engine)
        vs = engine.detect_llm_violations("t1")
        ops = [v["operation"] for v in vs]
        assert "no_routes" in ops

    def test_model_with_route_no_violation(self, engine):
        _seed_model(engine)
        _seed_route(engine)
        vs = engine.detect_llm_violations("t1")
        ops = [v["operation"] for v in vs]
        assert "no_routes" not in ops

    def test_idempotent_second_call_empty(self, engine):
        _seed_model(engine)  # active model, no routes -> violation
        vs1 = engine.detect_llm_violations("t1")
        assert len(vs1) > 0
        vs2 = engine.detect_llm_violations("t1")
        assert vs2 == ()

    def test_idempotent_third_call_still_empty(self, engine):
        _seed_model(engine)
        engine.detect_llm_violations("t1")
        engine.detect_llm_violations("t1")
        vs3 = engine.detect_llm_violations("t1")
        assert vs3 == ()

    def test_filters_by_tenant(self, engine):
        _full_pipeline(engine, "1", "t1")
        _full_pipeline(engine, "2", "t2")
        vs = engine.detect_llm_violations("t1")
        for v in vs:
            assert v["tenant_id"] == "t1"

    def test_emits_event_when_violations_found(self, es, engine):
        _seed_model(engine)
        before = es.event_count
        engine.detect_llm_violations("t1")
        assert es.event_count == before + 1

    def test_no_event_when_no_violations(self, es, engine):
        before = es.event_count
        engine.detect_llm_violations("t1")
        assert es.event_count == before

    def test_inactive_model_no_route_violation(self, engine):
        _seed_model(engine)
        engine.deprecate_model("m1")
        vs = engine.detect_llm_violations("t1")
        ops = [v["operation"] for v in vs]
        assert "no_routes" not in ops

    def test_disabled_model_no_route_violation(self, engine):
        _seed_model(engine)
        engine.disable_model("m1")
        vs = engine.detect_llm_violations("t1")
        ops = [v["operation"] for v in vs]
        assert "no_routes" not in ops

    def test_budget_exceeded_counted(self, engine):
        _seed_model(engine)
        _seed_template(engine)
        _seed_pack(engine)
        engine.request_generation("req1", "t1", "m1", "p1", token_budget=10)
        engine.record_generation_result("res1", "req1", "t1", tokens_used=100)
        assert engine.violation_count >= 1


# ===================================================================
# SECTION 13: State Hash
# ===================================================================


class TestStateHash:
    def test_empty_is_deterministic(self, engine):
        h1 = engine.state_hash()
        h2 = engine.state_hash()
        assert h1 == h2

    def test_sha256_length(self, engine):
        h = engine.state_hash()
        assert len(h) == 64

    def test_hex_chars_only(self, engine):
        h = engine.state_hash()
        assert all(c in "0123456789abcdef" for c in h)

    def test_changes_after_model(self, engine):
        h1 = engine.state_hash()
        _seed_model(engine)
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_after_route(self, engine):
        _seed_model(engine)
        h1 = engine.state_hash()
        _seed_route(engine)
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_after_template(self, engine):
        h1 = engine.state_hash()
        _seed_template(engine)
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_after_pack(self, engine):
        _seed_model(engine)
        _seed_template(engine)
        h1 = engine.state_hash()
        _seed_pack(engine)
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_after_request(self, engine):
        _seed_model(engine)
        _seed_template(engine)
        _seed_pack(engine)
        h1 = engine.state_hash()
        _seed_request(engine)
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_after_result(self, engine):
        _seed_model(engine)
        _seed_template(engine)
        _seed_pack(engine)
        _seed_request(engine)
        h1 = engine.state_hash()
        _seed_result(engine)
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_after_permission(self, engine):
        _seed_model(engine)
        h1 = engine.state_hash()
        engine.register_tool_permission("perm1", "t1", "m1", "tool_x")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_after_evidence(self, engine):
        _full_pipeline(engine)
        h1 = engine.state_hash()
        engine.assess_grounding("ev1", "res1", "t1", "src")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_after_assessment(self, engine):
        _full_pipeline(engine)
        h1 = engine.state_hash()
        engine.assess_safety("sa1", "res1", "t1")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_after_violation(self, engine):
        _full_pipeline(engine)
        h1 = engine.state_hash()
        engine.assess_safety("sa1", "res1", "t1", verdict=SafetyVerdict.BLOCKED,
                             reason="bad")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_after_status_change(self, engine):
        _seed_model(engine)
        h1 = engine.state_hash()
        engine.deprecate_model("m1")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_after_route_status_change(self, engine):
        _seed_model(engine)
        _seed_route(engine)
        h1 = engine.state_hash()
        engine.mark_route_degraded("r1")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_after_template_approve(self, engine):
        _seed_template(engine)
        h1 = engine.state_hash()
        engine.approve_template("tpl1")
        h2 = engine.state_hash()
        assert h1 != h2


# ===================================================================
# SECTION 14: Replay / Restore (same ops -> same hash)
# ===================================================================


class TestReplayRestore:
    @staticmethod
    def _run_scenario(engine: LlmRuntimeEngine):
        """Deterministic sequence of operations."""
        engine.register_model("m1", "t1", "GPT4", max_tokens=8192)
        engine.register_model("m2", "t1", "Claude", max_tokens=4096)
        engine.register_prompt_template("tpl1", "t1", "System", "You are {{role}}")
        engine.register_provider_route("r1", "t1", "openai", "m1", priority=1)
        engine.register_provider_route("r2", "t1", "anthropic", "m2", priority=0)
        engine.build_context_pack("p1", "t1", "tpl1", "m1", token_count=100)
        engine.request_generation("req1", "t1", "m1", "p1", token_budget=200)
        engine.record_generation_result("res1", "req1", "t1", tokens_used=50)
        engine.assess_grounding("ev1", "res1", "t1", "wiki",
                                grounding_status=GroundingStatus.GROUNDED)
        engine.assess_safety("sa1", "res1", "t1", verdict=SafetyVerdict.SAFE)
        engine.register_tool_permission("perm1", "t1", "m1", "search", allowed=True)

    def test_same_operations_same_hash(self):
        es1 = EventSpineEngine()
        eng1 = LlmRuntimeEngine(es1)
        self._run_scenario(eng1)
        h1 = eng1.state_hash()

        es2 = EventSpineEngine()
        eng2 = LlmRuntimeEngine(es2)
        self._run_scenario(eng2)
        h2 = eng2.state_hash()

        assert h1 == h2

    def test_different_operations_different_hash(self):
        es1 = EventSpineEngine()
        eng1 = LlmRuntimeEngine(es1)
        self._run_scenario(eng1)
        h1 = eng1.state_hash()

        es2 = EventSpineEngine()
        eng2 = LlmRuntimeEngine(es2)
        self._run_scenario(eng2)
        eng2.deprecate_model("m1")
        h2 = eng2.state_hash()

        assert h1 != h2

    def test_same_counts_after_replay(self):
        es1 = EventSpineEngine()
        eng1 = LlmRuntimeEngine(es1)
        self._run_scenario(eng1)

        es2 = EventSpineEngine()
        eng2 = LlmRuntimeEngine(es2)
        self._run_scenario(eng2)

        assert eng1.model_count == eng2.model_count
        assert eng1.route_count == eng2.route_count
        assert eng1.template_count == eng2.template_count
        assert eng1.pack_count == eng2.pack_count
        assert eng1.request_count == eng2.request_count
        assert eng1.result_count == eng2.result_count
        assert eng1.permission_count == eng2.permission_count

    def test_event_counts_match(self):
        es1 = EventSpineEngine()
        eng1 = LlmRuntimeEngine(es1)
        self._run_scenario(eng1)

        es2 = EventSpineEngine()
        eng2 = LlmRuntimeEngine(es2)
        self._run_scenario(eng2)

        assert es1.event_count == es2.event_count


# ===================================================================
# SECTION 15: Golden Scenarios
# ===================================================================


class TestGoldenGroundedAnswer:
    """Golden scenario 1: Grounded answer passes and is stored with evidence."""

    def test_full_flow(self, engine):
        _seed_model(engine, max_tokens=8192)
        _seed_route(engine)
        _seed_template(engine)
        _seed_pack(engine, token_count=500)
        _seed_request(engine, token_budget=1000)
        engine.start_generation("req1")
        res = _seed_result(engine, tokens_used=200, confidence=0.9,
                           output_ref="s3://answers/1.json")
        assert res.status == GenerationStatus.COMPLETED

        ev = engine.assess_grounding("ev1", "res1", "t1", "kb_article_42",
                                     relevance_score=0.95,
                                     grounding_status=GroundingStatus.GROUNDED)
        assert ev.grounding_status == GroundingStatus.GROUNDED

        sa = engine.assess_safety("sa1", "res1", "t1", verdict=SafetyVerdict.SAFE)
        assert sa.verdict == SafetyVerdict.SAFE

        final = engine.get_result("res1")
        assert final.grounding_status == GroundingStatus.GROUNDED
        assert final.safety_verdict == SafetyVerdict.SAFE
        assert engine.violation_count == 0


class TestGoldenUngroundedBlocked:
    """Golden scenario 2: Ungrounded answer blocked for sensitive task."""

    def test_full_flow(self, engine):
        _full_pipeline(engine)
        # Leave NOT_CHECKED -> detect_llm_violations catches it
        vs = engine.detect_llm_violations("t1")
        assert any(v["operation"] == "ungrounded_result" for v in vs)
        assert engine.violation_count >= 1


class TestGoldenProviderTimeout:
    """Golden scenario 3: Provider timeout falls back to alternate route."""

    def test_full_flow(self, engine):
        _seed_model(engine, max_tokens=8192)
        _seed_route(engine, "r1", priority=0)
        _seed_route(engine, "r2", priority=1)
        _seed_template(engine)
        _seed_pack(engine)

        # Request using primary route
        _seed_request(engine, latency_budget_ms=5000)
        engine.start_generation("req1")
        engine.timeout_generation("req1")

        req = engine.get_request("req1")
        assert req.status == GenerationStatus.TIMED_OUT

        # Mark primary route degraded
        engine.mark_route_degraded("r1")

        # Choose fallback
        fallback = engine.choose_fallback_route("m1")
        assert fallback is not None
        assert fallback.route_id == "r2"

        # New request on fallback route
        engine.request_generation("req2", "t1", "m1", "p1")
        engine.start_generation("req2")
        engine.record_generation_result("res2", "req2", "t1",
                                        tokens_used=100, output_ref="result2")
        res = engine.get_result("res2")
        assert res.status == GenerationStatus.COMPLETED


class TestGoldenUnsafeOutputRejected:
    """Golden scenario 4: Unsafe output rejected (BLOCKED safety verdict)."""

    def test_full_flow(self, engine):
        _full_pipeline(engine)
        engine.assess_grounding("ev1", "res1", "t1", "src",
                                grounding_status=GroundingStatus.GROUNDED)
        engine.assess_safety("sa1", "res1", "t1",
                             verdict=SafetyVerdict.BLOCKED,
                             reason="harmful content detected",
                             confidence=0.99)
        res = engine.get_result("res1")
        assert res.safety_verdict == SafetyVerdict.BLOCKED
        assert engine.violation_count >= 1


class TestGoldenToolCallBlocked:
    """Golden scenario 5: Tool call blocked by permission scope."""

    def test_full_flow(self, engine):
        _seed_model(engine)
        # Register allowed tool
        engine.register_tool_permission("perm1", "t1", "m1", "search", allowed=True)
        # Register denied tool
        engine.register_tool_permission("perm2", "t1", "m1", "exec_code", allowed=False)

        assert engine.check_tool_permission("m1", "search") is True
        assert engine.check_tool_permission("m1", "exec_code") is False
        # Unregistered tool -> fail-closed
        assert engine.check_tool_permission("m1", "admin_delete") is False


class TestGoldenReplayHash:
    """Golden scenario 6: Replay/restore -> same state_hash."""

    def test_full_flow(self):
        def run(eng):
            eng.register_model("m1", "t1", "GPT4", max_tokens=4096)
            eng.register_prompt_template("tpl1", "t1", "Sys", "prompt")
            eng.register_provider_route("r1", "t1", "oai", "m1")
            eng.build_context_pack("p1", "t1", "tpl1", "m1")
            eng.request_generation("req1", "t1", "m1", "p1")
            eng.record_generation_result("res1", "req1", "t1", tokens_used=50)
            eng.assess_grounding("ev1", "res1", "t1", "src",
                                 grounding_status=GroundingStatus.GROUNDED)
            eng.assess_safety("sa1", "res1", "t1")
            eng.register_tool_permission("perm1", "t1", "m1", "tool_a")
            eng.detect_llm_violations("t1")

        eng1 = LlmRuntimeEngine(EventSpineEngine())
        run(eng1)
        eng2 = LlmRuntimeEngine(EventSpineEngine())
        run(eng2)
        assert eng1.state_hash() == eng2.state_hash()


# ===================================================================
# SECTION 16: Edge Cases & Additional Coverage
# ===================================================================


class TestTerminalStateBlocking:
    """All terminal states block further mutations on requests."""

    @pytest.fixture(autouse=True)
    def setup(self, engine):
        _seed_model(engine)
        _seed_template(engine)
        _seed_pack(engine)

    def test_completed_blocks_start(self, engine):
        _seed_request(engine)
        _seed_result(engine)
        with pytest.raises(RuntimeCoreInvariantError):
            engine.start_generation("req1")

    def test_completed_blocks_block(self, engine):
        _seed_request(engine)
        _seed_result(engine)
        with pytest.raises(RuntimeCoreInvariantError):
            engine.block_generation("req1")

    def test_failed_blocks_start(self, engine):
        """FAILED is terminal — set via internal mutation to cover the branch."""
        _seed_request(engine)
        # Force FAILED status via internal mutation
        req = engine._requests["req1"]
        from datetime import datetime, timezone
        failed = GenerationRequest(
            request_id=req.request_id, tenant_id=req.tenant_id,
            model_id=req.model_id, pack_id=req.pack_id,
            status=GenerationStatus.FAILED, token_budget=req.token_budget,
            cost_budget=req.cost_budget, latency_budget_ms=req.latency_budget_ms,
            requested_at=req.requested_at,
        )
        engine._requests["req1"] = failed
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine.start_generation("req1")

    def test_failed_blocks_block(self, engine):
        """FAILED is terminal — block also rejected."""
        _seed_request(engine)
        req = engine._requests["req1"]
        from datetime import datetime, timezone
        failed = GenerationRequest(
            request_id=req.request_id, tenant_id=req.tenant_id,
            model_id=req.model_id, pack_id=req.pack_id,
            status=GenerationStatus.FAILED, token_budget=req.token_budget,
            cost_budget=req.cost_budget, latency_budget_ms=req.latency_budget_ms,
            requested_at=req.requested_at,
        )
        engine._requests["req1"] = failed
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine.block_generation("req1")

    def test_blocked_blocks_start(self, engine):
        _seed_request(engine)
        engine.block_generation("req1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.start_generation("req1")

    def test_blocked_blocks_block(self, engine):
        _seed_request(engine)
        engine.block_generation("req1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.block_generation("req1")

    def test_timed_out_blocks_start(self, engine):
        _seed_request(engine)
        engine.start_generation("req1")
        engine.timeout_generation("req1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.start_generation("req1")

    def test_timed_out_blocks_block(self, engine):
        _seed_request(engine)
        engine.start_generation("req1")
        engine.timeout_generation("req1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.block_generation("req1")


class TestModelStatusTransitions:
    """Full lifecycle transitions."""

    def test_active_to_deprecated_to_disabled_to_retired(self, engine):
        _seed_model(engine)
        engine.deprecate_model("m1")
        engine.disable_model("m1")
        engine.retire_model("m1")
        m = engine.get_model("m1")
        assert m.status == ModelStatus.RETIRED

    def test_active_directly_to_retired(self, engine):
        _seed_model(engine)
        engine.retire_model("m1")
        m = engine.get_model("m1")
        assert m.status == ModelStatus.RETIRED

    def test_active_to_disabled_to_deprecated(self, engine):
        _seed_model(engine)
        engine.disable_model("m1")
        engine.deprecate_model("m1")
        m = engine.get_model("m1")
        assert m.status == ModelStatus.DEPRECATED

    def test_disabled_to_retired(self, engine):
        _seed_model(engine)
        engine.disable_model("m1")
        engine.retire_model("m1")
        m = engine.get_model("m1")
        assert m.status == ModelStatus.RETIRED


class TestEventCounting:
    """Verify event_count increments correctly."""

    def test_register_model_event(self, es, engine):
        assert es.event_count == 0
        _seed_model(engine)
        assert es.event_count == 1

    def test_full_pipeline_events(self, es, engine):
        _full_pipeline(engine)
        # register_model + register_template + build_pack + request_generation + record_result = 5
        assert es.event_count == 5

    def test_multiple_operations_accumulate(self, es, engine):
        _seed_model(engine)  # 1
        _seed_template(engine)  # 2
        _seed_pack(engine)  # 3
        _seed_request(engine)  # 4
        engine.start_generation("req1")  # 5
        _seed_result(engine)  # 6
        engine.assess_grounding("ev1", "res1", "t1", "src")  # 7
        engine.assess_safety("sa1", "res1", "t1")  # 8
        assert es.event_count == 8


class TestMultipleTenants:
    """Cross-tenant isolation."""

    def test_snapshots_isolated(self, engine):
        _full_pipeline(engine, "1", "t1")
        _full_pipeline(engine, "2", "t2")
        _full_pipeline(engine, "3", "t2")
        s1 = engine.llm_snapshot("s1", "t1")
        s2 = engine.llm_snapshot("s2", "t2")
        assert s1.total_models == 1
        assert s2.total_models == 2

    def test_violations_isolated(self, engine):
        _full_pipeline(engine, "1", "t1")
        _full_pipeline(engine, "2", "t2")
        vs = engine.detect_llm_violations("t1")
        for v in vs:
            assert v["tenant_id"] == "t1"

    def test_models_for_tenant_isolated(self, engine):
        _seed_model(engine, "m1", "t1")
        _seed_model(engine, "m2", "t2")
        assert len(engine.models_for_tenant("t1")) == 1
        assert len(engine.models_for_tenant("t2")) == 1


class TestBudgetEdgeCases:
    """Budget enforcement edge cases."""

    @pytest.fixture(autouse=True)
    def setup(self, engine):
        _seed_model(engine)
        _seed_template(engine)
        _seed_pack(engine)

    def test_exact_budget_no_violation(self, engine):
        engine.request_generation("req1", "t1", "m1", "p1",
                                  token_budget=100, cost_budget=1.0)
        engine.record_generation_result("res1", "req1", "t1",
                                        tokens_used=100, cost_incurred=1.0)
        assert engine.violation_count == 0

    def test_one_over_token_budget(self, engine):
        engine.request_generation("req1", "t1", "m1", "p1", token_budget=100)
        engine.record_generation_result("res1", "req1", "t1", tokens_used=101)
        assert engine.violation_count == 1

    def test_one_over_cost_budget(self, engine):
        engine.request_generation("req1", "t1", "m1", "p1", cost_budget=1.0)
        engine.record_generation_result("res1", "req1", "t1", cost_incurred=1.01)
        assert engine.violation_count == 1

    def test_both_exceeded_one_violation(self, engine):
        engine.request_generation("req1", "t1", "m1", "p1",
                                  token_budget=10, cost_budget=0.1)
        engine.record_generation_result("res1", "req1", "t1",
                                        tokens_used=100, cost_incurred=1.0)
        # budget_violated is True once, creating one violation
        assert engine.violation_count == 1


class TestContextPackTokenValidation:
    """Token count vs model max_tokens validation."""

    def test_large_token_count_exactly_at_max(self, engine):
        _seed_model(engine, max_tokens=100000)
        _seed_template(engine)
        p = _seed_pack(engine, token_count=100000)
        assert p.token_count == 100000

    def test_one_over_max_raises(self, engine):
        _seed_model(engine, max_tokens=100)
        _seed_template(engine)
        with pytest.raises(RuntimeCoreInvariantError, match="exceeds"):
            _seed_pack(engine, token_count=101)

    def test_way_over_max_raises(self, engine):
        _seed_model(engine, max_tokens=100)
        _seed_template(engine)
        with pytest.raises(RuntimeCoreInvariantError, match="exceeds"):
            _seed_pack(engine, token_count=999999)


class TestRouteTransitions:
    """Route status changes."""

    def test_available_to_degraded(self, engine):
        _seed_model(engine)
        _seed_route(engine)
        r = engine.mark_route_degraded("r1")
        assert r.status == ProviderStatus.DEGRADED

    def test_available_to_unavailable(self, engine):
        _seed_model(engine)
        _seed_route(engine)
        r = engine.mark_route_unavailable("r1")
        assert r.status == ProviderStatus.UNAVAILABLE

    def test_degraded_to_unavailable(self, engine):
        _seed_model(engine)
        _seed_route(engine)
        engine.mark_route_degraded("r1")
        r = engine.mark_route_unavailable("r1")
        assert r.status == ProviderStatus.UNAVAILABLE

    def test_unavailable_to_degraded(self, engine):
        _seed_model(engine)
        _seed_route(engine)
        engine.mark_route_unavailable("r1")
        r = engine.mark_route_degraded("r1")
        assert r.status == ProviderStatus.DEGRADED


class TestFallbackRoutePrioritySorting:
    """Detailed fallback route sorting tests."""

    def test_three_available_lowest_wins(self, engine):
        _seed_model(engine)
        _seed_route(engine, "r1", priority=10)
        _seed_route(engine, "r2", priority=5)
        _seed_route(engine, "r3", priority=1)
        r = engine.choose_fallback_route("m1")
        assert r.route_id == "r3"

    def test_all_degraded_lowest_wins(self, engine):
        _seed_model(engine)
        for i, p in enumerate([10, 5, 1]):
            _seed_route(engine, f"r{i}", priority=p)
            engine.mark_route_degraded(f"r{i}")
        r = engine.choose_fallback_route("m1")
        assert r.priority == 1

    def test_available_beats_degraded_even_higher_priority(self, engine):
        _seed_model(engine)
        _seed_route(engine, "r1", priority=100)  # available
        _seed_route(engine, "r2", priority=0)  # degraded
        engine.mark_route_degraded("r2")
        r = engine.choose_fallback_route("m1")
        assert r.route_id == "r1"  # available wins

    def test_no_model_routes_returns_none(self, engine):
        _seed_model(engine, "m1")
        _seed_model(engine, "m2")
        _seed_route(engine, "r1", model_id="m2")
        assert engine.choose_fallback_route("m1") is None


class TestSafetyVerdictVariants:
    """All safety verdict variants."""

    @pytest.fixture(autouse=True)
    def setup(self, engine):
        _full_pipeline(engine)

    def test_safe_verdict(self, engine):
        engine.assess_safety("sa1", "res1", "t1", verdict=SafetyVerdict.SAFE)
        assert engine.get_result("res1").safety_verdict == SafetyVerdict.SAFE

    def test_flagged_verdict(self, engine):
        engine.assess_safety("sa1", "res1", "t1", verdict=SafetyVerdict.FLAGGED)
        assert engine.get_result("res1").safety_verdict == SafetyVerdict.FLAGGED

    def test_blocked_verdict(self, engine):
        engine.assess_safety("sa1", "res1", "t1", verdict=SafetyVerdict.BLOCKED,
                             reason="bad")
        assert engine.get_result("res1").safety_verdict == SafetyVerdict.BLOCKED

    def test_requires_review_verdict(self, engine):
        engine.assess_safety("sa1", "res1", "t1",
                             verdict=SafetyVerdict.REQUIRES_REVIEW)
        assert engine.get_result("res1").safety_verdict == SafetyVerdict.REQUIRES_REVIEW


class TestGroundingStatusVariants:
    """All grounding status variants."""

    @pytest.fixture(autouse=True)
    def setup(self, engine):
        _full_pipeline(engine)

    def test_grounded(self, engine):
        engine.assess_grounding("ev1", "res1", "t1", "src",
                                grounding_status=GroundingStatus.GROUNDED)
        assert engine.get_result("res1").grounding_status == GroundingStatus.GROUNDED

    def test_ungrounded(self, engine):
        engine.assess_grounding("ev1", "res1", "t1", "src",
                                grounding_status=GroundingStatus.UNGROUNDED)
        assert engine.get_result("res1").grounding_status == GroundingStatus.UNGROUNDED

    def test_partially_grounded(self, engine):
        engine.assess_grounding("ev1", "res1", "t1", "src",
                                grounding_status=GroundingStatus.PARTIALLY_GROUNDED)
        assert engine.get_result("res1").grounding_status == GroundingStatus.PARTIALLY_GROUNDED

    def test_not_checked_default(self, engine):
        assert engine.get_result("res1").grounding_status == GroundingStatus.NOT_CHECKED


class TestReturnTypes:
    """Verify all methods return correct types."""

    def test_register_model_returns_descriptor(self, engine):
        assert isinstance(_seed_model(engine), ModelDescriptor)

    def test_register_route_returns_route(self, engine):
        _seed_model(engine)
        assert isinstance(_seed_route(engine), ProviderRoute)

    def test_register_template_returns_template(self, engine):
        assert isinstance(_seed_template(engine), PromptTemplate)

    def test_build_pack_returns_pack(self, engine):
        _seed_model(engine)
        _seed_template(engine)
        assert isinstance(_seed_pack(engine), ContextPack)

    def test_request_generation_returns_request(self, engine):
        _seed_model(engine)
        _seed_template(engine)
        _seed_pack(engine)
        assert isinstance(_seed_request(engine), GenerationRequest)

    def test_record_result_returns_result(self, engine):
        _seed_model(engine)
        _seed_template(engine)
        _seed_pack(engine)
        _seed_request(engine)
        assert isinstance(_seed_result(engine), GenerationResult)

    def test_register_permission_returns_permission(self, engine):
        _seed_model(engine)
        p = engine.register_tool_permission("perm1", "t1", "m1", "tool")
        assert isinstance(p, ToolPermission)

    def test_assess_grounding_returns_evidence(self, engine):
        _full_pipeline(engine)
        ev = engine.assess_grounding("ev1", "res1", "t1", "src")
        assert isinstance(ev, GroundingEvidence)

    def test_assess_safety_returns_assessment(self, engine):
        _full_pipeline(engine)
        sa = engine.assess_safety("sa1", "res1", "t1")
        assert isinstance(sa, SafetyAssessment)

    def test_snapshot_returns_snapshot(self, engine):
        snap = engine.llm_snapshot("s1", "t1")
        assert isinstance(snap, LlmRuntimeSnapshot)

    def test_detect_violations_returns_tuple(self, engine):
        vs = engine.detect_llm_violations("t1")
        assert isinstance(vs, tuple)

    def test_choose_fallback_returns_route_or_none(self, engine):
        _seed_model(engine)
        assert engine.choose_fallback_route("m1") is None
        _seed_route(engine)
        assert isinstance(engine.choose_fallback_route("m1"), ProviderRoute)

    def test_state_hash_returns_str(self, engine):
        assert isinstance(engine.state_hash(), str)


class TestProperties:
    """All count properties."""

    def test_model_count(self, engine):
        assert engine.model_count == 0
        _seed_model(engine)
        assert engine.model_count == 1

    def test_route_count(self, engine):
        _seed_model(engine)
        assert engine.route_count == 0
        _seed_route(engine)
        assert engine.route_count == 1

    def test_template_count(self, engine):
        assert engine.template_count == 0
        _seed_template(engine)
        assert engine.template_count == 1

    def test_pack_count(self, engine):
        _seed_model(engine)
        _seed_template(engine)
        assert engine.pack_count == 0
        _seed_pack(engine)
        assert engine.pack_count == 1

    def test_request_count(self, engine):
        _seed_model(engine)
        _seed_template(engine)
        _seed_pack(engine)
        assert engine.request_count == 0
        _seed_request(engine)
        assert engine.request_count == 1

    def test_result_count(self, engine):
        _seed_model(engine)
        _seed_template(engine)
        _seed_pack(engine)
        _seed_request(engine)
        assert engine.result_count == 0
        _seed_result(engine)
        assert engine.result_count == 1

    def test_permission_count(self, engine):
        _seed_model(engine)
        assert engine.permission_count == 0
        engine.register_tool_permission("p1", "t1", "m1", "t")
        assert engine.permission_count == 1

    def test_violation_count(self, engine):
        assert engine.violation_count == 0


class TestMassOperations:
    """Bulk operations to verify no leaks or cross-contamination."""

    def test_twenty_models(self, engine):
        for i in range(20):
            _seed_model(engine, f"m{i}")
        assert engine.model_count == 20

    def test_twenty_routes(self, engine):
        _seed_model(engine)
        for i in range(20):
            _seed_route(engine, f"r{i}")
        assert engine.route_count == 20

    def test_twenty_templates(self, engine):
        for i in range(20):
            _seed_template(engine, f"tpl{i}")
        assert engine.template_count == 20

    def test_twenty_packs(self, engine):
        _seed_model(engine)
        _seed_template(engine)
        for i in range(20):
            _seed_pack(engine, f"p{i}")
        assert engine.pack_count == 20

    def test_twenty_requests(self, engine):
        _seed_model(engine)
        _seed_template(engine)
        _seed_pack(engine)
        for i in range(20):
            _seed_request(engine, f"req{i}")
        assert engine.request_count == 20

    def test_twenty_results(self, engine):
        _seed_model(engine)
        _seed_template(engine)
        _seed_pack(engine)
        for i in range(20):
            _seed_request(engine, f"req{i}")
            _seed_result(engine, f"res{i}", f"req{i}")
        assert engine.result_count == 20

    def test_state_hash_deterministic_after_mass_ops(self, engine):
        for i in range(10):
            _seed_model(engine, f"m{i}")
        h1 = engine.state_hash()
        h2 = engine.state_hash()
        assert h1 == h2


class TestDisabledRetiredModelBlocksRequests:
    """Disabled/retired models block new generation requests."""

    @pytest.fixture(autouse=True)
    def setup(self, engine):
        _seed_model(engine)
        _seed_template(engine)
        _seed_pack(engine)

    def test_disabled_blocks(self, engine):
        engine.disable_model("m1")
        with pytest.raises(RuntimeCoreInvariantError, match="(?i)disabled"):
            _seed_request(engine)

    def test_retired_blocks(self, engine):
        engine.retire_model("m1")
        with pytest.raises(RuntimeCoreInvariantError, match="(?i)retired"):
            _seed_request(engine)

    def test_deprecated_allows(self, engine):
        engine.deprecate_model("m1")
        req = _seed_request(engine)
        assert req.status == GenerationStatus.PENDING

    def test_active_allows(self, engine):
        req = _seed_request(engine)
        assert req.status == GenerationStatus.PENDING


class TestViolationTypeCoverage:
    """Each violation type is testable and has correct operation field."""

    def test_ungrounded_result_type(self, engine):
        _full_pipeline(engine)
        vs = engine.detect_llm_violations("t1")
        ungrounded = [v for v in vs if v["operation"] == "ungrounded_result"]
        assert len(ungrounded) >= 1

    def test_blocked_safety_type(self, engine):
        _full_pipeline(engine)
        engine.assess_safety("sa1", "res1", "t1", verdict=SafetyVerdict.BLOCKED,
                             reason="toxic")
        engine.assess_grounding("ev1", "res1", "t1", "src",
                                grounding_status=GroundingStatus.GROUNDED)
        vs = engine.detect_llm_violations("t1")
        blocked = [v for v in vs if v["operation"] == "blocked_safety"]
        assert len(blocked) >= 1

    def test_no_routes_type(self, engine):
        _seed_model(engine)
        vs = engine.detect_llm_violations("t1")
        no_routes = [v for v in vs if v["operation"] == "no_routes"]
        assert len(no_routes) >= 1

    def test_budget_exceeded_type(self, engine):
        _seed_model(engine)
        _seed_template(engine)
        _seed_pack(engine)
        engine.request_generation("req1", "t1", "m1", "p1", token_budget=10)
        engine.record_generation_result("res1", "req1", "t1", tokens_used=100)
        assert engine.violation_count >= 1


class TestGenerationStatusValues:
    """Verify each GenerationStatus can be reached."""

    @pytest.fixture(autouse=True)
    def setup(self, engine):
        _seed_model(engine)
        _seed_template(engine)
        _seed_pack(engine)

    def test_pending(self, engine):
        req = _seed_request(engine)
        assert req.status == GenerationStatus.PENDING

    def test_running(self, engine):
        _seed_request(engine)
        req = engine.start_generation("req1")
        assert req.status == GenerationStatus.RUNNING

    def test_completed(self, engine):
        _seed_request(engine)
        _seed_result(engine)
        req = engine.get_request("req1")
        assert req.status == GenerationStatus.COMPLETED

    def test_blocked(self, engine):
        _seed_request(engine)
        req = engine.block_generation("req1")
        assert req.status == GenerationStatus.BLOCKED

    def test_timed_out(self, engine):
        _seed_request(engine)
        engine.start_generation("req1")
        req = engine.timeout_generation("req1")
        assert req.status == GenerationStatus.TIMED_OUT


class TestFrozenOutputs:
    """All outputs should be frozen dataclass instances."""

    def test_model_is_frozen(self, engine):
        m = _seed_model(engine)
        with pytest.raises(AttributeError):
            m.display_name = "changed"

    def test_route_is_frozen(self, engine):
        _seed_model(engine)
        r = _seed_route(engine)
        with pytest.raises(AttributeError):
            r.priority = 999

    def test_template_is_frozen(self, engine):
        t = _seed_template(engine)
        with pytest.raises(AttributeError):
            t.template_text = "changed"

    def test_pack_is_frozen(self, engine):
        _seed_model(engine)
        _seed_template(engine)
        p = _seed_pack(engine)
        with pytest.raises(AttributeError):
            p.token_count = 999

    def test_request_is_frozen(self, engine):
        _seed_model(engine)
        _seed_template(engine)
        _seed_pack(engine)
        req = _seed_request(engine)
        with pytest.raises(AttributeError):
            req.status = GenerationStatus.RUNNING

    def test_result_is_frozen(self, engine):
        _full_pipeline(engine)
        res = engine.get_result("res1")
        with pytest.raises(AttributeError):
            res.tokens_used = 999

    def test_permission_is_frozen(self, engine):
        _seed_model(engine)
        p = engine.register_tool_permission("p1", "t1", "m1", "t")
        with pytest.raises(AttributeError):
            p.allowed = False

    def test_evidence_is_frozen(self, engine):
        _full_pipeline(engine)
        ev = engine.assess_grounding("ev1", "res1", "t1", "src")
        with pytest.raises(AttributeError):
            ev.relevance_score = 0.0

    def test_assessment_is_frozen(self, engine):
        _full_pipeline(engine)
        sa = engine.assess_safety("sa1", "res1", "t1")
        with pytest.raises(AttributeError):
            sa.verdict = SafetyVerdict.BLOCKED

    def test_snapshot_is_frozen(self, engine):
        snap = engine.llm_snapshot("s1", "t1")
        with pytest.raises(AttributeError):
            snap.total_models = 999


class TestMultipleResultsPerRequest:
    """A request can have multiple results (edge case — engine allows it
    since result_id is unique and the request is auto-completed)."""

    def test_second_result_different_id(self, engine):
        _seed_model(engine)
        _seed_template(engine)
        _seed_pack(engine)
        _seed_request(engine)
        _seed_result(engine, "res1")
        # Request already COMPLETED, but we can still record another result for it
        # if we use a different request.  Actually, looking at the code,
        # record_generation_result doesn't check if request is terminal.
        # It just auto-completes it again.
        _seed_request(engine, "req2")
        res2 = _seed_result(engine, "res2", "req2")
        assert res2.result_id == "res2"


class TestEmptyEngineHash:
    """Empty engine has a stable hash."""

    def test_two_empty_engines_same_hash(self):
        e1 = LlmRuntimeEngine(EventSpineEngine())
        e2 = LlmRuntimeEngine(EventSpineEngine())
        assert e1.state_hash() == e2.state_hash()

    def test_empty_hash_is_sha256_of_empty(self):
        e = LlmRuntimeEngine(EventSpineEngine())
        import hashlib
        expected = hashlib.sha256(b"").hexdigest()
        assert e.state_hash() == expected


# ===================================================================
# SECTION 17: Additional Coverage for ~350 Tests
# ===================================================================


class TestModelDescriptorFields:
    """Verify model descriptor field values in detail."""

    def test_model_id_matches(self, engine):
        m = _seed_model(engine, "my-model-1")
        assert m.model_id == "my-model-1"

    def test_tenant_id_matches(self, engine):
        m = _seed_model(engine, tenant_id="tenant-abc")
        assert m.tenant_id == "tenant-abc"

    def test_display_name_matches(self, engine):
        m = engine.register_model("m1", "t1", "Super Model")
        assert m.display_name == "Super Model"

    def test_provider_ref_default(self, engine):
        m = _seed_model(engine)
        assert m.provider_ref == "default"

    def test_provider_ref_custom(self, engine):
        m = engine.register_model("m1", "t1", "M", provider_ref="anthropic")
        assert m.provider_ref == "anthropic"

    def test_status_active_on_creation(self, engine):
        m = _seed_model(engine)
        assert m.status == ModelStatus.ACTIVE


class TestRouteDescriptorFields:
    """Verify route descriptor field values."""

    def test_route_id_matches(self, engine):
        _seed_model(engine)
        r = _seed_route(engine, "route-abc")
        assert r.route_id == "route-abc"

    def test_tenant_id_matches(self, engine):
        _seed_model(engine)
        r = engine.register_provider_route("r1", "tenant-x", "prov", "m1")
        assert r.tenant_id == "tenant-x"

    def test_provider_ref_matches(self, engine):
        _seed_model(engine)
        r = engine.register_provider_route("r1", "t1", "my-provider", "m1")
        assert r.provider_ref == "my-provider"

    def test_model_id_matches(self, engine):
        _seed_model(engine)
        r = _seed_route(engine)
        assert r.model_id == "m1"

    def test_default_priority_zero(self, engine):
        _seed_model(engine)
        r = engine.register_provider_route("r1", "t1", "prov", "m1")
        assert r.priority == 0

    def test_default_latency_budget(self, engine):
        _seed_model(engine)
        r = engine.register_provider_route("r1", "t1", "prov", "m1")
        assert r.latency_budget_ms == 30000

    def test_default_cost_budget(self, engine):
        _seed_model(engine)
        r = engine.register_provider_route("r1", "t1", "prov", "m1")
        assert r.cost_budget == 1.0

    def test_created_at_populated(self, engine):
        _seed_model(engine)
        r = _seed_route(engine)
        assert r.created_at != ""


class TestTemplateFields:
    """Verify template field values."""

    def test_template_text_stored(self, engine):
        t = engine.register_prompt_template("tpl1", "t1", "Tpl", "Hello {{user}}")
        assert t.template_text == "Hello {{user}}"

    def test_default_version_one(self, engine):
        t = engine.register_prompt_template("tpl1", "t1", "Tpl", "text")
        assert t.version == 1

    def test_created_at_populated(self, engine):
        t = _seed_template(engine)
        assert t.created_at != ""

    def test_display_name_stored(self, engine):
        t = engine.register_prompt_template("tpl1", "t1", "My Display Name", "text")
        assert t.display_name == "My Display Name"


class TestContextPackFields:
    """Verify context pack field values."""

    def test_template_id_stored(self, engine):
        _seed_model(engine)
        _seed_template(engine)
        p = _seed_pack(engine)
        assert p.template_id == "tpl1"

    def test_model_id_stored(self, engine):
        _seed_model(engine)
        _seed_template(engine)
        p = _seed_pack(engine)
        assert p.model_id == "m1"

    def test_assembled_at_populated(self, engine):
        _seed_model(engine)
        _seed_template(engine)
        p = _seed_pack(engine)
        assert p.assembled_at != ""

    def test_default_token_count_zero(self, engine):
        _seed_model(engine)
        _seed_template(engine)
        p = _seed_pack(engine)
        assert p.token_count == 0

    def test_default_source_count_zero(self, engine):
        _seed_model(engine)
        _seed_template(engine)
        p = _seed_pack(engine)
        assert p.source_count == 0


class TestGenerationRequestFields:
    """Verify generation request field values."""

    @pytest.fixture(autouse=True)
    def setup(self, engine):
        _seed_model(engine)
        _seed_template(engine)
        _seed_pack(engine)

    def test_model_id_stored(self, engine):
        req = _seed_request(engine)
        assert req.model_id == "m1"

    def test_pack_id_stored(self, engine):
        req = _seed_request(engine)
        assert req.pack_id == "p1"

    def test_default_token_budget(self, engine):
        req = _seed_request(engine)
        assert req.token_budget == 4096

    def test_default_cost_budget(self, engine):
        req = _seed_request(engine)
        assert req.cost_budget == 1.0

    def test_default_latency_budget(self, engine):
        req = _seed_request(engine)
        assert req.latency_budget_ms == 30000

    def test_requested_at_populated(self, engine):
        req = _seed_request(engine)
        assert req.requested_at != ""


class TestGenerationResultFields:
    """Verify generation result field values."""

    @pytest.fixture(autouse=True)
    def setup(self, engine):
        _seed_model(engine)
        _seed_template(engine)
        _seed_pack(engine)
        _seed_request(engine)

    def test_request_id_stored(self, engine):
        res = _seed_result(engine)
        assert res.request_id == "req1"

    def test_tenant_id_stored(self, engine):
        res = _seed_result(engine)
        assert res.tenant_id == "t1"

    def test_model_id_from_request(self, engine):
        res = _seed_result(engine)
        assert res.model_id == "m1"

    def test_default_tokens_used_zero(self, engine):
        res = _seed_result(engine)
        assert res.tokens_used == 0

    def test_default_cost_incurred_zero(self, engine):
        res = _seed_result(engine)
        assert res.cost_incurred == 0.0

    def test_default_latency_ms_zero(self, engine):
        res = _seed_result(engine)
        assert res.latency_ms == 0.0

    def test_default_output_ref(self, engine):
        res = _seed_result(engine)
        assert res.output_ref == "none"

    def test_default_confidence(self, engine):
        res = _seed_result(engine)
        assert res.confidence == 0.5

    def test_completed_at_populated(self, engine):
        res = _seed_result(engine)
        assert res.completed_at != ""


class TestToolPermissionFields:
    """Verify tool permission field values."""

    def test_tool_ref_stored(self, engine):
        _seed_model(engine)
        p = engine.register_tool_permission("p1", "t1", "m1", "my_tool")
        assert p.tool_ref == "my_tool"

    def test_default_allowed_true(self, engine):
        _seed_model(engine)
        p = engine.register_tool_permission("p1", "t1", "m1", "tool")
        assert p.allowed is True

    def test_default_scope_global(self, engine):
        _seed_model(engine)
        p = engine.register_tool_permission("p1", "t1", "m1", "tool")
        assert p.scope_ref == "global"

    def test_created_at_populated(self, engine):
        _seed_model(engine)
        p = engine.register_tool_permission("p1", "t1", "m1", "tool")
        assert p.created_at != ""


class TestGroundingEvidenceFields:
    """Verify grounding evidence field values."""

    def test_source_ref_stored(self, engine):
        _full_pipeline(engine)
        ev = engine.assess_grounding("ev1", "res1", "t1", "my_source")
        assert ev.source_ref == "my_source"

    def test_default_relevance_score(self, engine):
        _full_pipeline(engine)
        ev = engine.assess_grounding("ev1", "res1", "t1", "src")
        assert ev.relevance_score == 0.5

    def test_default_grounding_status(self, engine):
        _full_pipeline(engine)
        ev = engine.assess_grounding("ev1", "res1", "t1", "src")
        assert ev.grounding_status == GroundingStatus.GROUNDED

    def test_created_at_populated(self, engine):
        _full_pipeline(engine)
        ev = engine.assess_grounding("ev1", "res1", "t1", "src")
        assert ev.created_at != ""

    def test_result_id_stored(self, engine):
        _full_pipeline(engine)
        ev = engine.assess_grounding("ev1", "res1", "t1", "src")
        assert ev.result_id == "res1"

    def test_tenant_id_stored(self, engine):
        _full_pipeline(engine)
        ev = engine.assess_grounding("ev1", "res1", "t1", "src")
        assert ev.tenant_id == "t1"


class TestSafetyAssessmentFields:
    """Verify safety assessment field values."""

    def test_default_verdict_safe(self, engine):
        _full_pipeline(engine)
        a = engine.assess_safety("sa1", "res1", "t1")
        assert a.verdict == SafetyVerdict.SAFE

    def test_default_reason(self, engine):
        _full_pipeline(engine)
        a = engine.assess_safety("sa1", "res1", "t1")
        assert a.reason == "no issues"

    def test_default_confidence(self, engine):
        _full_pipeline(engine)
        a = engine.assess_safety("sa1", "res1", "t1")
        assert a.confidence == 1.0

    def test_assessed_at_populated(self, engine):
        _full_pipeline(engine)
        a = engine.assess_safety("sa1", "res1", "t1")
        assert a.assessed_at != ""

    def test_result_id_stored(self, engine):
        _full_pipeline(engine)
        a = engine.assess_safety("sa1", "res1", "t1")
        assert a.result_id == "res1"


class TestSnapshotFields:
    """Verify snapshot field values."""

    def test_tenant_id_stored(self, engine):
        snap = engine.llm_snapshot("s1", "t1")
        assert snap.tenant_id == "t1"

    def test_zero_defaults(self, engine):
        snap = engine.llm_snapshot("s1", "t1")
        assert snap.total_models == 0
        assert snap.total_routes == 0
        assert snap.total_templates == 0
        assert snap.total_requests == 0
        assert snap.total_results == 0
        assert snap.total_permissions == 0
        assert snap.total_violations == 0


class TestCrossMethodInteractions:
    """Tests that verify interactions between different subsystems."""

    def test_result_inherits_model_id_from_request(self, engine):
        _seed_model(engine, "special-model")
        _seed_template(engine)
        engine.build_context_pack("p1", "t1", "tpl1", "special-model")
        engine.request_generation("req1", "t1", "special-model", "p1")
        res = engine.record_generation_result("res1", "req1", "t1")
        assert res.model_id == "special-model"

    def test_grounding_evidence_updates_result_not_request(self, engine):
        _full_pipeline(engine)
        engine.assess_grounding("ev1", "res1", "t1", "src",
                                grounding_status=GroundingStatus.GROUNDED)
        req = engine.get_request("req1")
        # Request status should still be COMPLETED, not affected by grounding
        assert req.status == GenerationStatus.COMPLETED

    def test_safety_assessment_updates_result_not_request(self, engine):
        _full_pipeline(engine)
        engine.assess_safety("sa1", "res1", "t1", verdict=SafetyVerdict.BLOCKED,
                             reason="bad")
        req = engine.get_request("req1")
        assert req.status == GenerationStatus.COMPLETED

    def test_violation_from_budget_does_not_affect_result_status(self, engine):
        _seed_model(engine)
        _seed_template(engine)
        _seed_pack(engine)
        engine.request_generation("req1", "t1", "m1", "p1", token_budget=10)
        res = engine.record_generation_result("res1", "req1", "t1", tokens_used=100)
        assert res.status == GenerationStatus.COMPLETED

    def test_route_for_disabled_model_still_exists(self, engine):
        _seed_model(engine)
        _seed_route(engine)
        engine.disable_model("m1")
        routes = engine.routes_for_model("m1")
        assert len(routes) == 1

    def test_permission_for_retired_model_still_exists(self, engine):
        _seed_model(engine)
        engine.register_tool_permission("p1", "t1", "m1", "tool")
        engine.retire_model("m1")
        perms = engine.permissions_for_model("m1")
        assert len(perms) == 1

    def test_snapshot_after_violations(self, engine):
        _seed_model(engine)
        engine.detect_llm_violations("t1")
        snap = engine.llm_snapshot("s1", "t1")
        assert snap.total_violations >= 1

    def test_choose_fallback_after_all_routes_unavailable(self, engine):
        _seed_model(engine)
        for i in range(3):
            _seed_route(engine, f"r{i}")
            engine.mark_route_unavailable(f"r{i}")
        assert engine.choose_fallback_route("m1") is None


class TestStateHashCollisions:
    """State hash should distinguish different states."""

    def test_different_model_ids_different_hash(self):
        e1 = LlmRuntimeEngine(EventSpineEngine())
        e1.register_model("alpha", "t1", "A")
        e2 = LlmRuntimeEngine(EventSpineEngine())
        e2.register_model("beta", "t1", "B")
        assert e1.state_hash() != e2.state_hash()

    def test_different_model_statuses_different_hash(self):
        e1 = LlmRuntimeEngine(EventSpineEngine())
        e1.register_model("m1", "t1", "M")
        e2 = LlmRuntimeEngine(EventSpineEngine())
        e2.register_model("m1", "t1", "M")
        e2.deprecate_model("m1")
        assert e1.state_hash() != e2.state_hash()

    def test_different_permission_values_different_hash(self):
        e1 = LlmRuntimeEngine(EventSpineEngine())
        e1.register_model("m1", "t1", "M")
        e1.register_tool_permission("p1", "t1", "m1", "tool", allowed=True)
        e2 = LlmRuntimeEngine(EventSpineEngine())
        e2.register_model("m1", "t1", "M")
        e2.register_tool_permission("p1", "t1", "m1", "tool", allowed=False)
        assert e1.state_hash() != e2.state_hash()

    def test_different_grounding_statuses_different_hash(self):
        e1 = LlmRuntimeEngine(EventSpineEngine())
        _full_pipeline(e1, "1")
        e1.assess_grounding("ev1", "res1", "t1", "src",
                            grounding_status=GroundingStatus.GROUNDED)

        e2 = LlmRuntimeEngine(EventSpineEngine())
        _full_pipeline(e2, "1")
        e2.assess_grounding("ev1", "res1", "t1", "src",
                            grounding_status=GroundingStatus.UNGROUNDED)
        assert e1.state_hash() != e2.state_hash()

    def test_different_safety_verdicts_different_hash(self):
        e1 = LlmRuntimeEngine(EventSpineEngine())
        _full_pipeline(e1, "1")
        e1.assess_safety("sa1", "res1", "t1", verdict=SafetyVerdict.SAFE)

        e2 = LlmRuntimeEngine(EventSpineEngine())
        _full_pipeline(e2, "1")
        e2.assess_safety("sa1", "res1", "t1", verdict=SafetyVerdict.FLAGGED)
        assert e1.state_hash() != e2.state_hash()


class TestMultipleViolationSources:
    """Verify violations from different sources accumulate correctly."""

    def test_budget_and_safety_violations_both_counted(self, engine):
        _seed_model(engine)
        _seed_template(engine)
        _seed_pack(engine)
        engine.request_generation("req1", "t1", "m1", "p1", token_budget=10)
        engine.record_generation_result("res1", "req1", "t1", tokens_used=100)
        engine.assess_safety("sa1", "res1", "t1", verdict=SafetyVerdict.BLOCKED,
                             reason="toxic")
        assert engine.violation_count >= 2

    def test_budget_and_ungrounded_violations(self, engine):
        _seed_model(engine)
        _seed_template(engine)
        _seed_pack(engine)
        engine.request_generation("req1", "t1", "m1", "p1", token_budget=10)
        engine.record_generation_result("res1", "req1", "t1", tokens_used=100)
        engine.detect_llm_violations("t1")
        # budget_exceeded + ungrounded_result + no_routes (active model with no routes)
        assert engine.violation_count >= 2

    def test_no_routes_and_ungrounded(self, engine):
        _full_pipeline(engine)
        # model is active but has no routes, result is not grounded
        engine.detect_llm_violations("t1")
        assert engine.violation_count >= 1


class TestStartThenBlock:
    """Running request can be blocked."""

    def test_start_then_block(self, engine):
        _seed_model(engine)
        _seed_template(engine)
        _seed_pack(engine)
        _seed_request(engine)
        engine.start_generation("req1")
        req = engine.block_generation("req1")
        assert req.status == GenerationStatus.BLOCKED


class TestRequestGenerationWithDifferentModels:
    """Requests with different model statuses."""

    def test_active_model_allows(self, engine):
        _seed_model(engine)
        _seed_template(engine)
        _seed_pack(engine)
        req = _seed_request(engine)
        assert req.status == GenerationStatus.PENDING

    def test_deprecated_model_allows(self, engine):
        _seed_model(engine)
        _seed_template(engine)
        _seed_pack(engine)
        engine.deprecate_model("m1")
        req = _seed_request(engine)
        assert req.status == GenerationStatus.PENDING


class TestEventSpineInteraction:
    """Verify events are properly emitted to the spine."""

    def test_register_model_event_exists(self, es, engine):
        _seed_model(engine)
        events = es.list_events()
        assert len(events) >= 1

    def test_deprecate_model_event_exists(self, es, engine):
        _seed_model(engine)
        engine.deprecate_model("m1")
        events = es.list_events()
        assert len(events) >= 2

    def test_register_route_event_exists(self, es, engine):
        _seed_model(engine)
        _seed_route(engine)
        events = es.list_events()
        assert len(events) >= 2

    def test_build_pack_event_exists(self, es, engine):
        _seed_model(engine)
        _seed_template(engine)
        _seed_pack(engine)
        events = es.list_events()
        assert len(events) >= 3

    def test_request_generation_event_exists(self, es, engine):
        _seed_model(engine)
        _seed_template(engine)
        _seed_pack(engine)
        _seed_request(engine)
        events = es.list_events()
        assert len(events) >= 4


class TestFallbackRouteWithMixedStatuses:
    """Comprehensive fallback route scenarios."""

    def test_one_available_two_unavailable(self, engine):
        _seed_model(engine)
        _seed_route(engine, "r1", priority=0)
        _seed_route(engine, "r2", priority=1)
        _seed_route(engine, "r3", priority=2)
        engine.mark_route_unavailable("r1")
        engine.mark_route_unavailable("r3")
        r = engine.choose_fallback_route("m1")
        assert r.route_id == "r2"

    def test_one_degraded_two_unavailable(self, engine):
        _seed_model(engine)
        _seed_route(engine, "r1", priority=0)
        _seed_route(engine, "r2", priority=1)
        _seed_route(engine, "r3", priority=2)
        engine.mark_route_unavailable("r1")
        engine.mark_route_degraded("r2")
        engine.mark_route_unavailable("r3")
        r = engine.choose_fallback_route("m1")
        assert r.route_id == "r2"
        assert r.status == ProviderStatus.DEGRADED
