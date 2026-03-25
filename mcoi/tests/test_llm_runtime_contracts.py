"""Tests for LLM / model runtime contracts.

Covers 6 enums and 10 frozen dataclasses defined in
mcoi_runtime.contracts.llm_runtime.
"""

from __future__ import annotations

import dataclasses
import math
from types import MappingProxyType

import pytest

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


# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

TS = "2025-06-01T12:00:00+00:00"
TS2 = "2025-07-15T09:00:00+00:00"


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _model(**overrides) -> ModelDescriptor:
    defaults = dict(
        model_id="mdl-001",
        tenant_id="t-001",
        display_name="GPT-4o",
        provider_ref="openai",
        status=ModelStatus.ACTIVE,
        max_tokens=4096,
        cost_per_token=0.003,
        registered_at=TS,
    )
    defaults.update(overrides)
    return ModelDescriptor(**defaults)


def _route(**overrides) -> ProviderRoute:
    defaults = dict(
        route_id="rt-001",
        tenant_id="t-001",
        provider_ref="openai",
        model_id="mdl-001",
        priority=1,
        status=ProviderStatus.AVAILABLE,
        latency_budget_ms=5000,
        cost_budget=10.0,
        created_at=TS,
    )
    defaults.update(overrides)
    return ProviderRoute(**defaults)


def _template(**overrides) -> PromptTemplate:
    defaults = dict(
        template_id="tpl-001",
        tenant_id="t-001",
        display_name="Summariser",
        template_text="Summarise {{text}}",
        disposition=PromptDisposition.DRAFT,
        version=1,
        created_at=TS,
    )
    defaults.update(overrides)
    return PromptTemplate(**defaults)


def _pack(**overrides) -> ContextPack:
    defaults = dict(
        pack_id="pk-001",
        tenant_id="t-001",
        template_id="tpl-001",
        model_id="mdl-001",
        token_count=512,
        source_count=3,
        assembled_at=TS,
    )
    defaults.update(overrides)
    return ContextPack(**defaults)


def _gen_req(**overrides) -> GenerationRequest:
    defaults = dict(
        request_id="req-001",
        tenant_id="t-001",
        model_id="mdl-001",
        pack_id="pk-001",
        status=GenerationStatus.PENDING,
        token_budget=2048,
        cost_budget=5.0,
        latency_budget_ms=3000,
        requested_at=TS,
    )
    defaults.update(overrides)
    return GenerationRequest(**defaults)


def _gen_res(**overrides) -> GenerationResult:
    defaults = dict(
        result_id="res-001",
        request_id="req-001",
        tenant_id="t-001",
        model_id="mdl-001",
        status=GenerationStatus.COMPLETED,
        tokens_used=1024,
        cost_incurred=3.5,
        latency_ms=1200.0,
        output_ref="out-001",
        grounding_status=GroundingStatus.GROUNDED,
        safety_verdict=SafetyVerdict.SAFE,
        confidence=0.95,
        completed_at=TS,
    )
    defaults.update(overrides)
    return GenerationResult(**defaults)


def _perm(**overrides) -> ToolPermission:
    defaults = dict(
        permission_id="perm-001",
        tenant_id="t-001",
        model_id="mdl-001",
        tool_ref="tool-read",
        allowed=True,
        scope_ref="scope-001",
        created_at=TS,
    )
    defaults.update(overrides)
    return ToolPermission(**defaults)


def _evidence(**overrides) -> GroundingEvidence:
    defaults = dict(
        evidence_id="ev-001",
        result_id="res-001",
        tenant_id="t-001",
        source_ref="src-001",
        relevance_score=0.85,
        grounding_status=GroundingStatus.GROUNDED,
        created_at=TS,
    )
    defaults.update(overrides)
    return GroundingEvidence(**defaults)


def _safety(**overrides) -> SafetyAssessment:
    defaults = dict(
        assessment_id="sa-001",
        result_id="res-001",
        tenant_id="t-001",
        verdict=SafetyVerdict.SAFE,
        reason="No harmful content detected",
        confidence=0.99,
        assessed_at=TS,
    )
    defaults.update(overrides)
    return SafetyAssessment(**defaults)


def _snapshot(**overrides) -> LlmRuntimeSnapshot:
    defaults = dict(
        snapshot_id="snap-001",
        tenant_id="t-001",
        total_models=5,
        total_routes=10,
        total_templates=20,
        total_requests=100,
        total_results=95,
        total_permissions=30,
        total_violations=2,
        captured_at=TS,
    )
    defaults.update(overrides)
    return LlmRuntimeSnapshot(**defaults)


# ===================================================================
# ENUM TESTS
# ===================================================================


class TestModelStatus:
    def test_members(self):
        assert set(ModelStatus) == {
            ModelStatus.ACTIVE,
            ModelStatus.DEPRECATED,
            ModelStatus.DISABLED,
            ModelStatus.RETIRED,
        }

    @pytest.mark.parametrize("member,value", [
        (ModelStatus.ACTIVE, "active"),
        (ModelStatus.DEPRECATED, "deprecated"),
        (ModelStatus.DISABLED, "disabled"),
        (ModelStatus.RETIRED, "retired"),
    ])
    def test_values(self, member, value):
        assert member.value == value

    def test_member_count(self):
        assert len(ModelStatus) == 4


class TestProviderStatus:
    def test_members(self):
        assert set(ProviderStatus) == {
            ProviderStatus.AVAILABLE,
            ProviderStatus.DEGRADED,
            ProviderStatus.UNAVAILABLE,
            ProviderStatus.SUSPENDED,
        }

    @pytest.mark.parametrize("member,value", [
        (ProviderStatus.AVAILABLE, "available"),
        (ProviderStatus.DEGRADED, "degraded"),
        (ProviderStatus.UNAVAILABLE, "unavailable"),
        (ProviderStatus.SUSPENDED, "suspended"),
    ])
    def test_values(self, member, value):
        assert member.value == value

    def test_member_count(self):
        assert len(ProviderStatus) == 4


class TestPromptDisposition:
    def test_members(self):
        assert set(PromptDisposition) == {
            PromptDisposition.APPROVED,
            PromptDisposition.DRAFT,
            PromptDisposition.REJECTED,
            PromptDisposition.ARCHIVED,
        }

    @pytest.mark.parametrize("member,value", [
        (PromptDisposition.APPROVED, "approved"),
        (PromptDisposition.DRAFT, "draft"),
        (PromptDisposition.REJECTED, "rejected"),
        (PromptDisposition.ARCHIVED, "archived"),
    ])
    def test_values(self, member, value):
        assert member.value == value

    def test_member_count(self):
        assert len(PromptDisposition) == 4


class TestGroundingStatus:
    def test_members(self):
        assert set(GroundingStatus) == {
            GroundingStatus.GROUNDED,
            GroundingStatus.PARTIALLY_GROUNDED,
            GroundingStatus.UNGROUNDED,
            GroundingStatus.NOT_CHECKED,
        }

    @pytest.mark.parametrize("member,value", [
        (GroundingStatus.GROUNDED, "grounded"),
        (GroundingStatus.PARTIALLY_GROUNDED, "partially_grounded"),
        (GroundingStatus.UNGROUNDED, "ungrounded"),
        (GroundingStatus.NOT_CHECKED, "not_checked"),
    ])
    def test_values(self, member, value):
        assert member.value == value

    def test_member_count(self):
        assert len(GroundingStatus) == 4


class TestSafetyVerdict:
    def test_members(self):
        assert set(SafetyVerdict) == {
            SafetyVerdict.SAFE,
            SafetyVerdict.FLAGGED,
            SafetyVerdict.BLOCKED,
            SafetyVerdict.REQUIRES_REVIEW,
        }

    @pytest.mark.parametrize("member,value", [
        (SafetyVerdict.SAFE, "safe"),
        (SafetyVerdict.FLAGGED, "flagged"),
        (SafetyVerdict.BLOCKED, "blocked"),
        (SafetyVerdict.REQUIRES_REVIEW, "requires_review"),
    ])
    def test_values(self, member, value):
        assert member.value == value

    def test_member_count(self):
        assert len(SafetyVerdict) == 4


class TestGenerationStatus:
    def test_members(self):
        assert set(GenerationStatus) == {
            GenerationStatus.PENDING,
            GenerationStatus.RUNNING,
            GenerationStatus.COMPLETED,
            GenerationStatus.FAILED,
            GenerationStatus.BLOCKED,
            GenerationStatus.TIMED_OUT,
        }

    @pytest.mark.parametrize("member,value", [
        (GenerationStatus.PENDING, "pending"),
        (GenerationStatus.RUNNING, "running"),
        (GenerationStatus.COMPLETED, "completed"),
        (GenerationStatus.FAILED, "failed"),
        (GenerationStatus.BLOCKED, "blocked"),
        (GenerationStatus.TIMED_OUT, "timed_out"),
    ])
    def test_values(self, member, value):
        assert member.value == value

    def test_member_count(self):
        assert len(GenerationStatus) == 6


# ===================================================================
# ModelDescriptor TESTS
# ===================================================================


class TestModelDescriptor:
    def test_valid_construction(self):
        m = _model()
        assert m.model_id == "mdl-001"
        assert m.tenant_id == "t-001"
        assert m.display_name == "GPT-4o"
        assert m.provider_ref == "openai"
        assert m.status is ModelStatus.ACTIVE
        assert m.max_tokens == 4096
        assert m.cost_per_token == 0.003
        assert m.registered_at == TS

    def test_frozen(self):
        m = _model()
        with pytest.raises(dataclasses.FrozenInstanceError):
            m.model_id = "other"  # type: ignore[misc]

    def test_metadata_frozen_to_mapping_proxy(self):
        m = _model(metadata={"key": "val"})
        assert isinstance(m.metadata, MappingProxyType)
        assert m.metadata["key"] == "val"

    def test_metadata_plain_dict_in_to_dict(self):
        m = _model(metadata={"key": "val"})
        d = m.to_dict()
        assert isinstance(d["metadata"], dict)
        assert d["metadata"] == {"key": "val"}

    def test_metadata_empty(self):
        m = _model()
        assert isinstance(m.metadata, MappingProxyType)
        assert len(m.metadata) == 0

    def test_to_dict_preserves_enum_objects(self):
        m = _model()
        d = m.to_dict()
        assert d["status"] is ModelStatus.ACTIVE

    def test_to_dict_roundtrip_fields(self):
        m = _model()
        d = m.to_dict()
        assert d["model_id"] == "mdl-001"
        assert d["max_tokens"] == 4096
        assert d["cost_per_token"] == 0.003

    @pytest.mark.parametrize("status", list(ModelStatus))
    def test_accepts_all_status_members(self, status):
        m = _model(status=status)
        assert m.status is status

    @pytest.mark.parametrize("bad", ["active", "ACTIVE", 0, None, True])
    def test_rejects_non_enum_status(self, bad):
        with pytest.raises(ValueError, match="ModelStatus"):
            _model(status=bad)

    # -- model_id validation --
    @pytest.mark.parametrize("bad", ["", "   ", "\t", "\n"])
    def test_model_id_rejects_empty(self, bad):
        with pytest.raises(ValueError, match="model_id"):
            _model(model_id=bad)

    # -- tenant_id validation --
    @pytest.mark.parametrize("bad", ["", "   "])
    def test_tenant_id_rejects_empty(self, bad):
        with pytest.raises(ValueError, match="tenant_id"):
            _model(tenant_id=bad)

    # -- display_name validation --
    @pytest.mark.parametrize("bad", ["", "   "])
    def test_display_name_rejects_empty(self, bad):
        with pytest.raises(ValueError, match="display_name"):
            _model(display_name=bad)

    # -- provider_ref validation --
    @pytest.mark.parametrize("bad", ["", "   "])
    def test_provider_ref_rejects_empty(self, bad):
        with pytest.raises(ValueError, match="provider_ref"):
            _model(provider_ref=bad)

    # -- max_tokens validation --
    def test_max_tokens_accepts_zero(self):
        m = _model(max_tokens=0)
        assert m.max_tokens == 0

    def test_max_tokens_accepts_positive(self):
        m = _model(max_tokens=128000)
        assert m.max_tokens == 128000

    @pytest.mark.parametrize("bad", [-1, -100])
    def test_max_tokens_rejects_negative(self, bad):
        with pytest.raises(ValueError, match="max_tokens"):
            _model(max_tokens=bad)

    @pytest.mark.parametrize("bad", [True, False])
    def test_max_tokens_rejects_bool(self, bad):
        with pytest.raises(ValueError, match="max_tokens"):
            _model(max_tokens=bad)

    @pytest.mark.parametrize("bad", [1.5, 2.0])
    def test_max_tokens_rejects_float(self, bad):
        with pytest.raises(ValueError, match="max_tokens"):
            _model(max_tokens=bad)

    # -- cost_per_token validation --
    def test_cost_per_token_accepts_zero(self):
        m = _model(cost_per_token=0.0)
        assert m.cost_per_token == 0.0

    def test_cost_per_token_accepts_positive(self):
        m = _model(cost_per_token=0.01)
        assert m.cost_per_token == 0.01

    def test_cost_per_token_rejects_negative(self):
        with pytest.raises(ValueError, match="cost_per_token"):
            _model(cost_per_token=-0.001)

    @pytest.mark.parametrize("bad", [True, False])
    def test_cost_per_token_rejects_bool(self, bad):
        with pytest.raises(ValueError, match="cost_per_token"):
            _model(cost_per_token=bad)

    def test_cost_per_token_rejects_string(self):
        with pytest.raises(ValueError, match="cost_per_token"):
            _model(cost_per_token="0.1")

    def test_cost_per_token_rejects_none(self):
        with pytest.raises(ValueError, match="cost_per_token"):
            _model(cost_per_token=None)

    def test_cost_per_token_accepts_int_coercion(self):
        m = _model(cost_per_token=1)
        assert m.cost_per_token == 1.0

    def test_cost_per_token_rejects_inf(self):
        with pytest.raises(ValueError, match="cost_per_token"):
            _model(cost_per_token=math.inf)

    def test_cost_per_token_rejects_nan(self):
        with pytest.raises(ValueError, match="cost_per_token"):
            _model(cost_per_token=math.nan)

    # -- registered_at validation --
    def test_registered_at_rejects_empty(self):
        with pytest.raises(ValueError, match="registered_at"):
            _model(registered_at="")

    def test_registered_at_rejects_garbage(self):
        with pytest.raises(ValueError, match="registered_at"):
            _model(registered_at="not-a-date")

    def test_registered_at_accepts_datetime(self):
        m = _model(registered_at="2025-06-01T12:00:00+00:00")
        assert m.registered_at == "2025-06-01T12:00:00+00:00"

    def test_registered_at_accepts_zulu(self):
        m = _model(registered_at="2025-06-01T12:00:00Z")
        assert m.registered_at == "2025-06-01T12:00:00Z"

    def test_registered_at_accepts_date_only(self):
        m = _model(registered_at="2025-06-01")
        assert m.registered_at == "2025-06-01"


# ===================================================================
# ProviderRoute TESTS
# ===================================================================


class TestProviderRoute:
    def test_valid_construction(self):
        r = _route()
        assert r.route_id == "rt-001"
        assert r.tenant_id == "t-001"
        assert r.provider_ref == "openai"
        assert r.model_id == "mdl-001"
        assert r.priority == 1
        assert r.status is ProviderStatus.AVAILABLE
        assert r.latency_budget_ms == 5000
        assert r.cost_budget == 10.0
        assert r.created_at == TS

    def test_frozen(self):
        r = _route()
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.route_id = "other"  # type: ignore[misc]

    def test_metadata_frozen_to_mapping_proxy(self):
        r = _route(metadata={"a": 1})
        assert isinstance(r.metadata, MappingProxyType)

    def test_metadata_plain_dict_in_to_dict(self):
        r = _route(metadata={"a": 1})
        d = r.to_dict()
        assert isinstance(d["metadata"], dict)

    def test_to_dict_preserves_enum(self):
        r = _route()
        assert r.to_dict()["status"] is ProviderStatus.AVAILABLE

    @pytest.mark.parametrize("status", list(ProviderStatus))
    def test_accepts_all_status_members(self, status):
        r = _route(status=status)
        assert r.status is status

    @pytest.mark.parametrize("bad", ["available", 0, None])
    def test_rejects_non_enum_status(self, bad):
        with pytest.raises(ValueError, match="ProviderStatus"):
            _route(status=bad)

    # -- text field validation --
    @pytest.mark.parametrize("field", ["route_id", "tenant_id", "provider_ref", "model_id"])
    def test_text_fields_reject_empty(self, field):
        with pytest.raises(ValueError, match=field):
            _route(**{field: ""})

    @pytest.mark.parametrize("field", ["route_id", "tenant_id", "provider_ref", "model_id"])
    def test_text_fields_reject_whitespace(self, field):
        with pytest.raises(ValueError, match=field):
            _route(**{field: "   "})

    # -- priority validation --
    def test_priority_accepts_zero(self):
        r = _route(priority=0)
        assert r.priority == 0

    def test_priority_rejects_negative(self):
        with pytest.raises(ValueError, match="priority"):
            _route(priority=-1)

    @pytest.mark.parametrize("bad", [True, False])
    def test_priority_rejects_bool(self, bad):
        with pytest.raises(ValueError, match="priority"):
            _route(priority=bad)

    # -- latency_budget_ms validation --
    def test_latency_budget_ms_accepts_zero(self):
        r = _route(latency_budget_ms=0)
        assert r.latency_budget_ms == 0

    def test_latency_budget_ms_rejects_negative(self):
        with pytest.raises(ValueError, match="latency_budget_ms"):
            _route(latency_budget_ms=-1)

    @pytest.mark.parametrize("bad", [True, 1.5])
    def test_latency_budget_ms_rejects_non_int(self, bad):
        with pytest.raises(ValueError, match="latency_budget_ms"):
            _route(latency_budget_ms=bad)

    # -- cost_budget validation --
    def test_cost_budget_accepts_zero(self):
        r = _route(cost_budget=0.0)
        assert r.cost_budget == 0.0

    def test_cost_budget_rejects_negative(self):
        with pytest.raises(ValueError, match="cost_budget"):
            _route(cost_budget=-0.01)

    @pytest.mark.parametrize("bad", [True, "10.0", None])
    def test_cost_budget_rejects_bad_types(self, bad):
        with pytest.raises(ValueError, match="cost_budget"):
            _route(cost_budget=bad)

    def test_cost_budget_accepts_int_coercion(self):
        r = _route(cost_budget=5)
        assert r.cost_budget == 5.0

    # -- created_at validation --
    def test_created_at_rejects_empty(self):
        with pytest.raises(ValueError, match="created_at"):
            _route(created_at="")

    def test_created_at_rejects_garbage(self):
        with pytest.raises(ValueError, match="created_at"):
            _route(created_at="nope")


# ===================================================================
# PromptTemplate TESTS
# ===================================================================


class TestPromptTemplate:
    def test_valid_construction(self):
        t = _template()
        assert t.template_id == "tpl-001"
        assert t.tenant_id == "t-001"
        assert t.display_name == "Summariser"
        assert t.template_text == "Summarise {{text}}"
        assert t.disposition is PromptDisposition.DRAFT
        assert t.version == 1

    def test_frozen(self):
        t = _template()
        with pytest.raises(dataclasses.FrozenInstanceError):
            t.template_id = "x"  # type: ignore[misc]

    def test_to_dict_preserves_enum(self):
        t = _template()
        assert t.to_dict()["disposition"] is PromptDisposition.DRAFT

    @pytest.mark.parametrize("disp", list(PromptDisposition))
    def test_accepts_all_disposition_members(self, disp):
        t = _template(disposition=disp)
        assert t.disposition is disp

    @pytest.mark.parametrize("bad", ["draft", "DRAFT", 0, None])
    def test_rejects_non_enum_disposition(self, bad):
        with pytest.raises(ValueError, match="PromptDisposition"):
            _template(disposition=bad)

    @pytest.mark.parametrize("field", ["template_id", "tenant_id", "display_name", "template_text"])
    def test_text_fields_reject_empty(self, field):
        with pytest.raises(ValueError, match=field):
            _template(**{field: ""})

    @pytest.mark.parametrize("field", ["template_id", "tenant_id", "display_name", "template_text"])
    def test_text_fields_reject_whitespace(self, field):
        with pytest.raises(ValueError, match=field):
            _template(**{field: "\t\n"})

    # -- version validation --
    def test_version_accepts_zero(self):
        t = _template(version=0)
        assert t.version == 0

    def test_version_rejects_negative(self):
        with pytest.raises(ValueError, match="version"):
            _template(version=-1)

    @pytest.mark.parametrize("bad", [True, 1.0])
    def test_version_rejects_non_int(self, bad):
        with pytest.raises(ValueError, match="version"):
            _template(version=bad)

    def test_metadata_frozen(self):
        t = _template(metadata={"k": "v"})
        assert isinstance(t.metadata, MappingProxyType)

    def test_metadata_plain_dict_in_to_dict(self):
        t = _template(metadata={"k": "v"})
        assert isinstance(t.to_dict()["metadata"], dict)

    def test_created_at_rejects_empty(self):
        with pytest.raises(ValueError, match="created_at"):
            _template(created_at="")

    def test_created_at_rejects_garbage(self):
        with pytest.raises(ValueError, match="created_at"):
            _template(created_at="bad")


# ===================================================================
# ContextPack TESTS
# ===================================================================


class TestContextPack:
    def test_valid_construction(self):
        p = _pack()
        assert p.pack_id == "pk-001"
        assert p.tenant_id == "t-001"
        assert p.template_id == "tpl-001"
        assert p.model_id == "mdl-001"
        assert p.token_count == 512
        assert p.source_count == 3

    def test_frozen(self):
        p = _pack()
        with pytest.raises(dataclasses.FrozenInstanceError):
            p.pack_id = "x"  # type: ignore[misc]

    @pytest.mark.parametrize("field", ["pack_id", "tenant_id", "template_id", "model_id"])
    def test_text_fields_reject_empty(self, field):
        with pytest.raises(ValueError, match=field):
            _pack(**{field: ""})

    @pytest.mark.parametrize("field", ["pack_id", "tenant_id", "template_id", "model_id"])
    def test_text_fields_reject_whitespace(self, field):
        with pytest.raises(ValueError, match=field):
            _pack(**{field: "  "})

    # -- token_count --
    def test_token_count_accepts_zero(self):
        assert _pack(token_count=0).token_count == 0

    def test_token_count_rejects_negative(self):
        with pytest.raises(ValueError, match="token_count"):
            _pack(token_count=-1)

    @pytest.mark.parametrize("bad", [True, 1.0])
    def test_token_count_rejects_non_int(self, bad):
        with pytest.raises(ValueError, match="token_count"):
            _pack(token_count=bad)

    # -- source_count --
    def test_source_count_accepts_zero(self):
        assert _pack(source_count=0).source_count == 0

    def test_source_count_rejects_negative(self):
        with pytest.raises(ValueError, match="source_count"):
            _pack(source_count=-1)

    @pytest.mark.parametrize("bad", [True, 2.5])
    def test_source_count_rejects_non_int(self, bad):
        with pytest.raises(ValueError, match="source_count"):
            _pack(source_count=bad)

    def test_assembled_at_rejects_empty(self):
        with pytest.raises(ValueError, match="assembled_at"):
            _pack(assembled_at="")

    def test_assembled_at_rejects_garbage(self):
        with pytest.raises(ValueError, match="assembled_at"):
            _pack(assembled_at="xyz")

    def test_metadata_frozen(self):
        p = _pack(metadata={"x": 1})
        assert isinstance(p.metadata, MappingProxyType)

    def test_metadata_plain_dict_in_to_dict(self):
        p = _pack(metadata={"x": 1})
        assert isinstance(p.to_dict()["metadata"], dict)

    def test_to_dict_all_fields(self):
        p = _pack()
        d = p.to_dict()
        assert set(d.keys()) == {
            "pack_id", "tenant_id", "template_id", "model_id",
            "token_count", "source_count", "assembled_at", "metadata",
        }


# ===================================================================
# GenerationRequest TESTS
# ===================================================================


class TestGenerationRequest:
    def test_valid_construction(self):
        g = _gen_req()
        assert g.request_id == "req-001"
        assert g.tenant_id == "t-001"
        assert g.model_id == "mdl-001"
        assert g.pack_id == "pk-001"
        assert g.status is GenerationStatus.PENDING
        assert g.token_budget == 2048
        assert g.cost_budget == 5.0
        assert g.latency_budget_ms == 3000

    def test_frozen(self):
        g = _gen_req()
        with pytest.raises(dataclasses.FrozenInstanceError):
            g.request_id = "x"  # type: ignore[misc]

    def test_to_dict_preserves_enum(self):
        g = _gen_req()
        assert g.to_dict()["status"] is GenerationStatus.PENDING

    @pytest.mark.parametrize("status", list(GenerationStatus))
    def test_accepts_all_status_members(self, status):
        g = _gen_req(status=status)
        assert g.status is status

    @pytest.mark.parametrize("bad", ["pending", 0, None, True])
    def test_rejects_non_enum_status(self, bad):
        with pytest.raises(ValueError, match="GenerationStatus"):
            _gen_req(status=bad)

    @pytest.mark.parametrize("field", ["request_id", "tenant_id", "model_id", "pack_id"])
    def test_text_fields_reject_empty(self, field):
        with pytest.raises(ValueError, match=field):
            _gen_req(**{field: ""})

    @pytest.mark.parametrize("field", ["request_id", "tenant_id", "model_id", "pack_id"])
    def test_text_fields_reject_whitespace(self, field):
        with pytest.raises(ValueError, match=field):
            _gen_req(**{field: "   "})

    # -- token_budget --
    def test_token_budget_accepts_zero(self):
        assert _gen_req(token_budget=0).token_budget == 0

    def test_token_budget_rejects_negative(self):
        with pytest.raises(ValueError, match="token_budget"):
            _gen_req(token_budget=-1)

    @pytest.mark.parametrize("bad", [True, 1.0])
    def test_token_budget_rejects_non_int(self, bad):
        with pytest.raises(ValueError, match="token_budget"):
            _gen_req(token_budget=bad)

    # -- cost_budget --
    def test_cost_budget_accepts_zero(self):
        assert _gen_req(cost_budget=0.0).cost_budget == 0.0

    def test_cost_budget_rejects_negative(self):
        with pytest.raises(ValueError, match="cost_budget"):
            _gen_req(cost_budget=-0.01)

    @pytest.mark.parametrize("bad", [True, "5", None])
    def test_cost_budget_rejects_bad_types(self, bad):
        with pytest.raises(ValueError, match="cost_budget"):
            _gen_req(cost_budget=bad)

    def test_cost_budget_accepts_int_coercion(self):
        assert _gen_req(cost_budget=5).cost_budget == 5.0

    # -- latency_budget_ms --
    def test_latency_budget_ms_accepts_zero(self):
        assert _gen_req(latency_budget_ms=0).latency_budget_ms == 0

    def test_latency_budget_ms_rejects_negative(self):
        with pytest.raises(ValueError, match="latency_budget_ms"):
            _gen_req(latency_budget_ms=-1)

    @pytest.mark.parametrize("bad", [True, 1.0])
    def test_latency_budget_ms_rejects_non_int(self, bad):
        with pytest.raises(ValueError, match="latency_budget_ms"):
            _gen_req(latency_budget_ms=bad)

    # -- requested_at --
    def test_requested_at_rejects_empty(self):
        with pytest.raises(ValueError, match="requested_at"):
            _gen_req(requested_at="")

    def test_requested_at_rejects_garbage(self):
        with pytest.raises(ValueError, match="requested_at"):
            _gen_req(requested_at="nope")

    def test_metadata_frozen(self):
        g = _gen_req(metadata={"a": "b"})
        assert isinstance(g.metadata, MappingProxyType)

    def test_metadata_plain_dict_in_to_dict(self):
        g = _gen_req(metadata={"a": "b"})
        assert isinstance(g.to_dict()["metadata"], dict)


# ===================================================================
# GenerationResult TESTS
# ===================================================================


class TestGenerationResult:
    def test_valid_construction(self):
        r = _gen_res()
        assert r.result_id == "res-001"
        assert r.request_id == "req-001"
        assert r.tenant_id == "t-001"
        assert r.model_id == "mdl-001"
        assert r.status is GenerationStatus.COMPLETED
        assert r.tokens_used == 1024
        assert r.cost_incurred == 3.5
        assert r.latency_ms == 1200.0
        assert r.output_ref == "out-001"
        assert r.grounding_status is GroundingStatus.GROUNDED
        assert r.safety_verdict is SafetyVerdict.SAFE
        assert r.confidence == 0.95

    def test_frozen(self):
        r = _gen_res()
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.result_id = "x"  # type: ignore[misc]

    def test_to_dict_preserves_enums(self):
        r = _gen_res()
        d = r.to_dict()
        assert d["status"] is GenerationStatus.COMPLETED
        assert d["grounding_status"] is GroundingStatus.GROUNDED
        assert d["safety_verdict"] is SafetyVerdict.SAFE

    @pytest.mark.parametrize("status", list(GenerationStatus))
    def test_accepts_all_status_members(self, status):
        r = _gen_res(status=status)
        assert r.status is status

    @pytest.mark.parametrize("bad", ["completed", 0, None])
    def test_rejects_non_enum_status(self, bad):
        with pytest.raises(ValueError, match="GenerationStatus"):
            _gen_res(status=bad)

    @pytest.mark.parametrize("gs", list(GroundingStatus))
    def test_accepts_all_grounding_status_members(self, gs):
        r = _gen_res(grounding_status=gs)
        assert r.grounding_status is gs

    @pytest.mark.parametrize("bad", ["grounded", 0, None])
    def test_rejects_non_enum_grounding_status(self, bad):
        with pytest.raises(ValueError, match="GroundingStatus"):
            _gen_res(grounding_status=bad)

    @pytest.mark.parametrize("sv", list(SafetyVerdict))
    def test_accepts_all_safety_verdict_members(self, sv):
        r = _gen_res(safety_verdict=sv)
        assert r.safety_verdict is sv

    @pytest.mark.parametrize("bad", ["safe", 0, None])
    def test_rejects_non_enum_safety_verdict(self, bad):
        with pytest.raises(ValueError, match="SafetyVerdict"):
            _gen_res(safety_verdict=bad)

    @pytest.mark.parametrize("field", ["result_id", "request_id", "tenant_id", "model_id", "output_ref"])
    def test_text_fields_reject_empty(self, field):
        with pytest.raises(ValueError, match=field):
            _gen_res(**{field: ""})

    @pytest.mark.parametrize("field", ["result_id", "request_id", "tenant_id", "model_id", "output_ref"])
    def test_text_fields_reject_whitespace(self, field):
        with pytest.raises(ValueError, match=field):
            _gen_res(**{field: "  "})

    # -- tokens_used --
    def test_tokens_used_accepts_zero(self):
        assert _gen_res(tokens_used=0).tokens_used == 0

    def test_tokens_used_rejects_negative(self):
        with pytest.raises(ValueError, match="tokens_used"):
            _gen_res(tokens_used=-1)

    @pytest.mark.parametrize("bad", [True, 1.0])
    def test_tokens_used_rejects_non_int(self, bad):
        with pytest.raises(ValueError, match="tokens_used"):
            _gen_res(tokens_used=bad)

    # -- cost_incurred --
    def test_cost_incurred_accepts_zero(self):
        assert _gen_res(cost_incurred=0.0).cost_incurred == 0.0

    def test_cost_incurred_rejects_negative(self):
        with pytest.raises(ValueError, match="cost_incurred"):
            _gen_res(cost_incurred=-0.01)

    @pytest.mark.parametrize("bad", [True, "3.5", None])
    def test_cost_incurred_rejects_bad_types(self, bad):
        with pytest.raises(ValueError, match="cost_incurred"):
            _gen_res(cost_incurred=bad)

    def test_cost_incurred_accepts_int_coercion(self):
        assert _gen_res(cost_incurred=3).cost_incurred == 3.0

    # -- latency_ms --
    def test_latency_ms_accepts_zero(self):
        assert _gen_res(latency_ms=0.0).latency_ms == 0.0

    def test_latency_ms_rejects_negative(self):
        with pytest.raises(ValueError, match="latency_ms"):
            _gen_res(latency_ms=-0.01)

    @pytest.mark.parametrize("bad", [True, "1200", None])
    def test_latency_ms_rejects_bad_types(self, bad):
        with pytest.raises(ValueError, match="latency_ms"):
            _gen_res(latency_ms=bad)

    def test_latency_ms_accepts_int_coercion(self):
        assert _gen_res(latency_ms=100).latency_ms == 100.0

    def test_latency_ms_rejects_inf(self):
        with pytest.raises(ValueError, match="latency_ms"):
            _gen_res(latency_ms=math.inf)

    # -- confidence (unit float) --
    def test_confidence_accepts_zero(self):
        assert _gen_res(confidence=0.0).confidence == 0.0

    def test_confidence_accepts_one(self):
        assert _gen_res(confidence=1.0).confidence == 1.0

    def test_confidence_accepts_mid(self):
        assert _gen_res(confidence=0.5).confidence == 0.5

    def test_confidence_rejects_above_one(self):
        with pytest.raises(ValueError, match="confidence"):
            _gen_res(confidence=1.01)

    def test_confidence_rejects_negative(self):
        with pytest.raises(ValueError, match="confidence"):
            _gen_res(confidence=-0.01)

    @pytest.mark.parametrize("bad", [True, "0.5", None])
    def test_confidence_rejects_bad_types(self, bad):
        with pytest.raises(ValueError, match="confidence"):
            _gen_res(confidence=bad)

    def test_confidence_rejects_inf(self):
        with pytest.raises(ValueError, match="confidence"):
            _gen_res(confidence=math.inf)

    def test_confidence_rejects_nan(self):
        with pytest.raises(ValueError, match="confidence"):
            _gen_res(confidence=math.nan)

    def test_confidence_accepts_int_zero(self):
        assert _gen_res(confidence=0).confidence == 0.0

    def test_confidence_accepts_int_one(self):
        assert _gen_res(confidence=1).confidence == 1.0

    # -- completed_at --
    def test_completed_at_rejects_empty(self):
        with pytest.raises(ValueError, match="completed_at"):
            _gen_res(completed_at="")

    def test_completed_at_rejects_garbage(self):
        with pytest.raises(ValueError, match="completed_at"):
            _gen_res(completed_at="nope")

    def test_metadata_frozen(self):
        r = _gen_res(metadata={"k": "v"})
        assert isinstance(r.metadata, MappingProxyType)

    def test_metadata_plain_dict_in_to_dict(self):
        r = _gen_res(metadata={"k": "v"})
        assert isinstance(r.to_dict()["metadata"], dict)

    def test_to_dict_all_fields(self):
        r = _gen_res()
        d = r.to_dict()
        assert set(d.keys()) == {
            "result_id", "request_id", "tenant_id", "model_id",
            "status", "tokens_used", "cost_incurred", "latency_ms",
            "output_ref", "grounding_status", "safety_verdict",
            "confidence", "completed_at", "metadata",
        }


# ===================================================================
# ToolPermission TESTS
# ===================================================================


class TestToolPermission:
    def test_valid_construction_allowed(self):
        p = _perm(allowed=True)
        assert p.allowed is True

    def test_valid_construction_disallowed(self):
        p = _perm(allowed=False)
        assert p.allowed is False

    def test_frozen(self):
        p = _perm()
        with pytest.raises(dataclasses.FrozenInstanceError):
            p.permission_id = "x"  # type: ignore[misc]

    @pytest.mark.parametrize("field", ["permission_id", "tenant_id", "model_id", "tool_ref", "scope_ref"])
    def test_text_fields_reject_empty(self, field):
        with pytest.raises(ValueError, match=field):
            _perm(**{field: ""})

    @pytest.mark.parametrize("field", ["permission_id", "tenant_id", "model_id", "tool_ref", "scope_ref"])
    def test_text_fields_reject_whitespace(self, field):
        with pytest.raises(ValueError, match=field):
            _perm(**{field: "  "})

    # -- allowed must be bool --
    @pytest.mark.parametrize("bad", [0, 1, "true", "yes", None, "True"])
    def test_allowed_rejects_non_bool(self, bad):
        with pytest.raises(ValueError, match="allowed"):
            _perm(allowed=bad)

    def test_created_at_rejects_empty(self):
        with pytest.raises(ValueError, match="created_at"):
            _perm(created_at="")

    def test_created_at_rejects_garbage(self):
        with pytest.raises(ValueError, match="created_at"):
            _perm(created_at="nope")

    def test_metadata_frozen(self):
        p = _perm(metadata={"x": 1})
        assert isinstance(p.metadata, MappingProxyType)

    def test_metadata_plain_dict_in_to_dict(self):
        p = _perm(metadata={"x": 1})
        assert isinstance(p.to_dict()["metadata"], dict)

    def test_to_dict_all_fields(self):
        p = _perm()
        d = p.to_dict()
        assert set(d.keys()) == {
            "permission_id", "tenant_id", "model_id", "tool_ref",
            "allowed", "scope_ref", "created_at", "metadata",
        }

    def test_to_dict_allowed_bool(self):
        assert _perm(allowed=True).to_dict()["allowed"] is True
        assert _perm(allowed=False).to_dict()["allowed"] is False


# ===================================================================
# GroundingEvidence TESTS
# ===================================================================


class TestGroundingEvidence:
    def test_valid_construction(self):
        e = _evidence()
        assert e.evidence_id == "ev-001"
        assert e.result_id == "res-001"
        assert e.tenant_id == "t-001"
        assert e.source_ref == "src-001"
        assert e.relevance_score == 0.85
        assert e.grounding_status is GroundingStatus.GROUNDED

    def test_frozen(self):
        e = _evidence()
        with pytest.raises(dataclasses.FrozenInstanceError):
            e.evidence_id = "x"  # type: ignore[misc]

    def test_to_dict_preserves_enum(self):
        e = _evidence()
        assert e.to_dict()["grounding_status"] is GroundingStatus.GROUNDED

    @pytest.mark.parametrize("gs", list(GroundingStatus))
    def test_accepts_all_grounding_status_members(self, gs):
        e = _evidence(grounding_status=gs)
        assert e.grounding_status is gs

    @pytest.mark.parametrize("bad", ["grounded", 0, None])
    def test_rejects_non_enum_grounding_status(self, bad):
        with pytest.raises(ValueError, match="GroundingStatus"):
            _evidence(grounding_status=bad)

    @pytest.mark.parametrize("field", ["evidence_id", "result_id", "tenant_id", "source_ref"])
    def test_text_fields_reject_empty(self, field):
        with pytest.raises(ValueError, match=field):
            _evidence(**{field: ""})

    @pytest.mark.parametrize("field", ["evidence_id", "result_id", "tenant_id", "source_ref"])
    def test_text_fields_reject_whitespace(self, field):
        with pytest.raises(ValueError, match=field):
            _evidence(**{field: "  "})

    # -- relevance_score (unit float) --
    def test_relevance_score_accepts_zero(self):
        assert _evidence(relevance_score=0.0).relevance_score == 0.0

    def test_relevance_score_accepts_one(self):
        assert _evidence(relevance_score=1.0).relevance_score == 1.0

    def test_relevance_score_accepts_mid(self):
        assert _evidence(relevance_score=0.5).relevance_score == 0.5

    def test_relevance_score_rejects_above_one(self):
        with pytest.raises(ValueError, match="relevance_score"):
            _evidence(relevance_score=1.01)

    def test_relevance_score_rejects_negative(self):
        with pytest.raises(ValueError, match="relevance_score"):
            _evidence(relevance_score=-0.01)

    @pytest.mark.parametrize("bad", [True, "0.5", None])
    def test_relevance_score_rejects_bad_types(self, bad):
        with pytest.raises(ValueError, match="relevance_score"):
            _evidence(relevance_score=bad)

    def test_relevance_score_rejects_inf(self):
        with pytest.raises(ValueError, match="relevance_score"):
            _evidence(relevance_score=math.inf)

    def test_relevance_score_rejects_nan(self):
        with pytest.raises(ValueError, match="relevance_score"):
            _evidence(relevance_score=math.nan)

    def test_relevance_score_accepts_int_zero(self):
        assert _evidence(relevance_score=0).relevance_score == 0.0

    def test_relevance_score_accepts_int_one(self):
        assert _evidence(relevance_score=1).relevance_score == 1.0

    def test_created_at_rejects_empty(self):
        with pytest.raises(ValueError, match="created_at"):
            _evidence(created_at="")

    def test_metadata_frozen(self):
        e = _evidence(metadata={"k": "v"})
        assert isinstance(e.metadata, MappingProxyType)

    def test_metadata_plain_dict_in_to_dict(self):
        e = _evidence(metadata={"k": "v"})
        assert isinstance(e.to_dict()["metadata"], dict)


# ===================================================================
# SafetyAssessment TESTS
# ===================================================================


class TestSafetyAssessment:
    def test_valid_construction(self):
        s = _safety()
        assert s.assessment_id == "sa-001"
        assert s.result_id == "res-001"
        assert s.tenant_id == "t-001"
        assert s.verdict is SafetyVerdict.SAFE
        assert s.reason == "No harmful content detected"
        assert s.confidence == 0.99

    def test_frozen(self):
        s = _safety()
        with pytest.raises(dataclasses.FrozenInstanceError):
            s.assessment_id = "x"  # type: ignore[misc]

    def test_to_dict_preserves_enum(self):
        s = _safety()
        assert s.to_dict()["verdict"] is SafetyVerdict.SAFE

    @pytest.mark.parametrize("v", list(SafetyVerdict))
    def test_accepts_all_verdict_members(self, v):
        s = _safety(verdict=v)
        assert s.verdict is v

    @pytest.mark.parametrize("bad", ["safe", 0, None, True])
    def test_rejects_non_enum_verdict(self, bad):
        with pytest.raises(ValueError, match="SafetyVerdict"):
            _safety(verdict=bad)

    @pytest.mark.parametrize("field", ["assessment_id", "result_id", "tenant_id", "reason"])
    def test_text_fields_reject_empty(self, field):
        with pytest.raises(ValueError, match=field):
            _safety(**{field: ""})

    @pytest.mark.parametrize("field", ["assessment_id", "result_id", "tenant_id", "reason"])
    def test_text_fields_reject_whitespace(self, field):
        with pytest.raises(ValueError, match=field):
            _safety(**{field: "  "})

    # -- confidence (unit float) --
    def test_confidence_accepts_zero(self):
        assert _safety(confidence=0.0).confidence == 0.0

    def test_confidence_accepts_one(self):
        assert _safety(confidence=1.0).confidence == 1.0

    def test_confidence_accepts_mid(self):
        assert _safety(confidence=0.5).confidence == 0.5

    def test_confidence_rejects_above_one(self):
        with pytest.raises(ValueError, match="confidence"):
            _safety(confidence=1.01)

    def test_confidence_rejects_negative(self):
        with pytest.raises(ValueError, match="confidence"):
            _safety(confidence=-0.01)

    @pytest.mark.parametrize("bad", [True, "0.5", None])
    def test_confidence_rejects_bad_types(self, bad):
        with pytest.raises(ValueError, match="confidence"):
            _safety(confidence=bad)

    def test_confidence_rejects_inf(self):
        with pytest.raises(ValueError, match="confidence"):
            _safety(confidence=math.inf)

    def test_confidence_rejects_nan(self):
        with pytest.raises(ValueError, match="confidence"):
            _safety(confidence=math.nan)

    def test_confidence_accepts_int_zero(self):
        assert _safety(confidence=0).confidence == 0.0

    def test_confidence_accepts_int_one(self):
        assert _safety(confidence=1).confidence == 1.0

    def test_assessed_at_rejects_empty(self):
        with pytest.raises(ValueError, match="assessed_at"):
            _safety(assessed_at="")

    def test_assessed_at_rejects_garbage(self):
        with pytest.raises(ValueError, match="assessed_at"):
            _safety(assessed_at="nope")

    def test_metadata_frozen(self):
        s = _safety(metadata={"k": "v"})
        assert isinstance(s.metadata, MappingProxyType)

    def test_metadata_plain_dict_in_to_dict(self):
        s = _safety(metadata={"k": "v"})
        assert isinstance(s.to_dict()["metadata"], dict)

    def test_to_dict_all_fields(self):
        s = _safety()
        d = s.to_dict()
        assert set(d.keys()) == {
            "assessment_id", "result_id", "tenant_id",
            "verdict", "reason", "confidence",
            "assessed_at", "metadata",
        }


# ===================================================================
# LlmRuntimeSnapshot TESTS
# ===================================================================


class TestLlmRuntimeSnapshot:
    def test_valid_construction(self):
        s = _snapshot()
        assert s.snapshot_id == "snap-001"
        assert s.tenant_id == "t-001"
        assert s.total_models == 5
        assert s.total_routes == 10
        assert s.total_templates == 20
        assert s.total_requests == 100
        assert s.total_results == 95
        assert s.total_permissions == 30
        assert s.total_violations == 2

    def test_frozen(self):
        s = _snapshot()
        with pytest.raises(dataclasses.FrozenInstanceError):
            s.snapshot_id = "x"  # type: ignore[misc]

    @pytest.mark.parametrize("field", ["snapshot_id", "tenant_id"])
    def test_text_fields_reject_empty(self, field):
        with pytest.raises(ValueError, match=field):
            _snapshot(**{field: ""})

    @pytest.mark.parametrize("field", ["snapshot_id", "tenant_id"])
    def test_text_fields_reject_whitespace(self, field):
        with pytest.raises(ValueError, match=field):
            _snapshot(**{field: "  "})

    # -- all int fields --
    INT_FIELDS = [
        "total_models", "total_routes", "total_templates",
        "total_requests", "total_results", "total_permissions",
        "total_violations",
    ]

    @pytest.mark.parametrize("field", INT_FIELDS)
    def test_int_fields_accept_zero(self, field):
        s = _snapshot(**{field: 0})
        assert getattr(s, field) == 0

    @pytest.mark.parametrize("field", INT_FIELDS)
    def test_int_fields_accept_positive(self, field):
        s = _snapshot(**{field: 42})
        assert getattr(s, field) == 42

    @pytest.mark.parametrize("field", INT_FIELDS)
    def test_int_fields_reject_negative(self, field):
        with pytest.raises(ValueError, match=field):
            _snapshot(**{field: -1})

    @pytest.mark.parametrize("field", INT_FIELDS)
    def test_int_fields_reject_bool(self, field):
        with pytest.raises(ValueError, match=field):
            _snapshot(**{field: True})

    @pytest.mark.parametrize("field", INT_FIELDS)
    def test_int_fields_reject_float(self, field):
        with pytest.raises(ValueError, match=field):
            _snapshot(**{field: 1.0})

    def test_captured_at_rejects_empty(self):
        with pytest.raises(ValueError, match="captured_at"):
            _snapshot(captured_at="")

    def test_captured_at_rejects_garbage(self):
        with pytest.raises(ValueError, match="captured_at"):
            _snapshot(captured_at="nope")

    def test_captured_at_accepts_zulu(self):
        s = _snapshot(captured_at="2025-06-01T00:00:00Z")
        assert s.captured_at == "2025-06-01T00:00:00Z"

    def test_captured_at_accepts_date_only(self):
        s = _snapshot(captured_at="2025-06-01")
        assert s.captured_at == "2025-06-01"

    def test_metadata_frozen(self):
        s = _snapshot(metadata={"k": "v"})
        assert isinstance(s.metadata, MappingProxyType)

    def test_metadata_plain_dict_in_to_dict(self):
        s = _snapshot(metadata={"k": "v"})
        assert isinstance(s.to_dict()["metadata"], dict)

    def test_to_dict_all_fields(self):
        s = _snapshot()
        d = s.to_dict()
        assert set(d.keys()) == {
            "snapshot_id", "tenant_id",
            "total_models", "total_routes", "total_templates",
            "total_requests", "total_results", "total_permissions",
            "total_violations", "captured_at", "metadata",
        }


# ===================================================================
# Cross-cutting / misc tests
# ===================================================================


class TestMetadataNestedFreezing:
    """Verify metadata with nested dicts/lists gets frozen and thawed."""

    def test_nested_dict_frozen(self):
        m = _model(metadata={"outer": {"inner": 1}})
        assert isinstance(m.metadata["outer"], MappingProxyType)
        assert m.metadata["outer"]["inner"] == 1

    def test_nested_list_frozen_to_tuple(self):
        m = _model(metadata={"items": [1, 2, 3]})
        assert isinstance(m.metadata["items"], tuple)
        assert m.metadata["items"] == (1, 2, 3)

    def test_nested_dict_thawed_in_to_dict(self):
        m = _model(metadata={"outer": {"inner": 1}})
        d = m.to_dict()
        assert isinstance(d["metadata"], dict)
        assert isinstance(d["metadata"]["outer"], dict)
        assert d["metadata"]["outer"]["inner"] == 1

    def test_nested_list_thawed_in_to_dict(self):
        m = _model(metadata={"items": [1, 2, 3]})
        d = m.to_dict()
        assert isinstance(d["metadata"]["items"], list)
        assert d["metadata"]["items"] == [1, 2, 3]


class TestDatetimeFormats:
    """Verify various datetime formats across dataclasses."""

    @pytest.mark.parametrize("ts", [
        "2025-06-01T12:00:00+00:00",
        "2025-06-01T12:00:00Z",
        "2025-06-01T12:00:00+05:30",
        "2025-06-01T12:00:00-08:00",
        "2025-06-01",
    ])
    def test_model_accepts_various_datetimes(self, ts):
        m = _model(registered_at=ts)
        assert m.registered_at == ts

    @pytest.mark.parametrize("ts", [
        "2025-06-01T12:00:00+00:00",
        "2025-06-01T12:00:00Z",
        "2025-06-01",
    ])
    def test_route_accepts_various_datetimes(self, ts):
        r = _route(created_at=ts)
        assert r.created_at == ts

    @pytest.mark.parametrize("bad", [
        "not-a-date",
        "13/06/2025",
        "June 1, 2025",
        "2025-13-01T00:00:00+00:00",
    ])
    def test_model_rejects_bad_datetimes(self, bad):
        with pytest.raises(ValueError, match="registered_at"):
            _model(registered_at=bad)


class TestImmutabilityAcrossAllDataclasses:
    """Verify frozen semantics for every dataclass."""

    @pytest.mark.parametrize("factory,field", [
        (_model, "model_id"),
        (_route, "route_id"),
        (_template, "template_id"),
        (_pack, "pack_id"),
        (_gen_req, "request_id"),
        (_gen_res, "result_id"),
        (_perm, "permission_id"),
        (_evidence, "evidence_id"),
        (_safety, "assessment_id"),
        (_snapshot, "snapshot_id"),
    ])
    def test_cannot_mutate(self, factory, field):
        obj = factory()
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            setattr(obj, field, "changed")


class TestToDictFieldCompleteness:
    """Ensure to_dict() includes every declared field for each dataclass."""

    @pytest.mark.parametrize("factory,cls", [
        (_model, ModelDescriptor),
        (_route, ProviderRoute),
        (_template, PromptTemplate),
        (_pack, ContextPack),
        (_gen_req, GenerationRequest),
        (_gen_res, GenerationResult),
        (_perm, ToolPermission),
        (_evidence, GroundingEvidence),
        (_safety, SafetyAssessment),
        (_snapshot, LlmRuntimeSnapshot),
    ])
    def test_to_dict_has_all_fields(self, factory, cls):
        obj = factory()
        d = obj.to_dict()
        declared = {f.name for f in dataclasses.fields(cls)}
        assert set(d.keys()) == declared


class TestMetadataMutationBlockedAtRuntime:
    """Verify that MappingProxyType actually prevents mutation."""

    def test_model_metadata_not_writable(self):
        m = _model(metadata={"key": "val"})
        with pytest.raises(TypeError):
            m.metadata["key"] = "new"  # type: ignore[index]

    def test_model_metadata_no_new_keys(self):
        m = _model(metadata={"key": "val"})
        with pytest.raises(TypeError):
            m.metadata["new_key"] = "x"  # type: ignore[index]


class TestNonNegativeFloatEdgeCases:
    """Edge-case coverage for require_non_negative_float fields."""

    def test_cost_per_token_rejects_neg_inf(self):
        with pytest.raises(ValueError):
            _model(cost_per_token=-math.inf)

    def test_cost_budget_rejects_inf(self):
        with pytest.raises(ValueError):
            _route(cost_budget=math.inf)

    def test_cost_budget_rejects_nan(self):
        with pytest.raises(ValueError):
            _route(cost_budget=math.nan)


class TestUnitFloatBoundary:
    """Boundary tests for require_unit_float fields."""

    @pytest.mark.parametrize("val", [0.0, 0.001, 0.5, 0.999, 1.0])
    def test_confidence_boundary_accepted(self, val):
        r = _gen_res(confidence=val)
        assert r.confidence == pytest.approx(val)

    @pytest.mark.parametrize("val", [-0.001, 1.001, 2.0, -1.0])
    def test_confidence_boundary_rejected(self, val):
        with pytest.raises(ValueError, match="confidence"):
            _gen_res(confidence=val)

    @pytest.mark.parametrize("val", [0.0, 0.001, 0.5, 0.999, 1.0])
    def test_relevance_score_boundary_accepted(self, val):
        e = _evidence(relevance_score=val)
        assert e.relevance_score == pytest.approx(val)

    @pytest.mark.parametrize("val", [-0.001, 1.001, 2.0, -1.0])
    def test_relevance_score_boundary_rejected(self, val):
        with pytest.raises(ValueError, match="relevance_score"):
            _evidence(relevance_score=val)

    @pytest.mark.parametrize("val", [0.0, 0.5, 1.0])
    def test_safety_confidence_boundary_accepted(self, val):
        s = _safety(confidence=val)
        assert s.confidence == pytest.approx(val)

    @pytest.mark.parametrize("val", [-0.001, 1.001])
    def test_safety_confidence_boundary_rejected(self, val):
        with pytest.raises(ValueError, match="confidence"):
            _safety(confidence=val)
