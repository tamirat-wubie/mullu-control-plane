"""Comprehensive tests for PersonaRuntimeIntegration.

Tests cover: construction, surface-specific persona methods, memory mesh attachment,
graph attachment, multi-tenant, event emission, and end-to-end workflows.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.persona_runtime import (
    AuthorityMode,
    InteractionStyle,
    PersonaKind,
)
from mcoi_runtime.contracts.memory_mesh import MemoryRecord
from mcoi_runtime.core.persona_runtime import PersonaRuntimeEngine
from mcoi_runtime.core.persona_runtime_integration import PersonaRuntimeIntegration
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine
from mcoi_runtime.core.engine_protocol import FixedClock
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture()
def clock():
    return FixedClock("2026-01-01T00:00:00+00:00")


@pytest.fixture()
def es():
    return EventSpineEngine()


@pytest.fixture()
def mem():
    return MemoryMeshEngine()


@pytest.fixture()
def persona_engine(es, clock):
    return PersonaRuntimeEngine(es, clock=clock)


@pytest.fixture()
def integration(persona_engine, es, mem):
    return PersonaRuntimeIntegration(persona_engine, es, mem)


# ===================================================================
# Construction Tests
# ===================================================================


class TestConstruction:
    def test_valid_construction(self, persona_engine, es, mem):
        integ = PersonaRuntimeIntegration(persona_engine, es, mem)
        assert integ is not None

    def test_invalid_persona_engine_rejected(self, es, mem):
        with pytest.raises(RuntimeCoreInvariantError):
            PersonaRuntimeIntegration("not_engine", es, mem)

    def test_invalid_event_spine_rejected(self, persona_engine, mem):
        with pytest.raises(RuntimeCoreInvariantError):
            PersonaRuntimeIntegration(persona_engine, "not_es", mem)

    def test_invalid_memory_engine_rejected(self, persona_engine, es):
        with pytest.raises(RuntimeCoreInvariantError):
            PersonaRuntimeIntegration(persona_engine, es, "not_mem")

    def test_none_persona_engine_rejected(self, es, mem):
        with pytest.raises(RuntimeCoreInvariantError):
            PersonaRuntimeIntegration(None, es, mem)

    def test_none_event_spine_rejected(self, persona_engine, mem):
        with pytest.raises(RuntimeCoreInvariantError):
            PersonaRuntimeIntegration(persona_engine, None, mem)

    def test_none_memory_engine_rejected(self, persona_engine, es):
        with pytest.raises(RuntimeCoreInvariantError):
            PersonaRuntimeIntegration(persona_engine, es, None)


# ===================================================================
# Operator Workspace Tests
# ===================================================================


class TestOperatorWorkspace:
    def test_persona_for_operator_workspace(self, integration):
        result = integration.persona_for_operator_workspace("t-1", "ws-1")
        assert isinstance(result, dict)
        assert result["kind"] == "operator"
        assert result["status"] == "active"
        assert result["tenant_id"] == "t-1"

    def test_operator_workspace_creates_persona(self, integration, persona_engine):
        integration.persona_for_operator_workspace("t-1", "ws-1")
        assert persona_engine.persona_count == 1

    def test_operator_workspace_creates_binding(self, integration, persona_engine):
        integration.persona_for_operator_workspace("t-1", "ws-1")
        assert persona_engine.binding_count == 1

    def test_operator_workspace_emits_event(self, integration, es):
        before = es.event_count
        integration.persona_for_operator_workspace("t-1", "ws-1")
        assert es.event_count > before

    def test_operator_workspace_custom_persona_id(self, integration):
        result = integration.persona_for_operator_workspace("t-1", "ws-1", persona_id="my-op")
        assert result["persona_id"] == "my-op"

    def test_operator_workspace_custom_session_ref(self, integration):
        result = integration.persona_for_operator_workspace("t-1", "ws-1", session_ref="custom-sess")
        assert result["source_type"] == "operator_workspace"

    def test_operator_workspace_default_session_ref(self, integration):
        result = integration.persona_for_operator_workspace("t-1", "ws-1")
        # session_ref defaults to workspace_ref
        assert result["source_type"] == "operator_workspace"

    def test_operator_interaction_style_concise(self, integration):
        result = integration.persona_for_operator_workspace("t-1", "ws-1")
        assert result["interaction_style"] == "concise"

    def test_operator_authority_guided(self, integration):
        result = integration.persona_for_operator_workspace("t-1", "ws-1")
        assert result["authority_mode"] == "guided"


# ===================================================================
# Product Console Tests
# ===================================================================


class TestProductConsole:
    def test_persona_for_product_console(self, integration):
        result = integration.persona_for_product_console("t-1", "console-1")
        assert result["kind"] == "technical"
        assert result["status"] == "active"

    def test_creates_persona_and_binding(self, integration, persona_engine):
        integration.persona_for_product_console("t-1", "console-1")
        assert persona_engine.persona_count == 1
        assert persona_engine.binding_count == 1

    def test_emits_event(self, integration, es):
        before = es.event_count
        integration.persona_for_product_console("t-1", "console-1")
        assert es.event_count > before


# ===================================================================
# Executive Control Tests
# ===================================================================


class TestExecutiveControl:
    def test_persona_for_executive_control(self, integration):
        result = integration.persona_for_executive_control("t-1", "dir-1")
        assert result["kind"] == "executive"
        assert result["authority_mode"] == "autonomous"

    def test_creates_persona_and_binding(self, integration, persona_engine):
        integration.persona_for_executive_control("t-1", "dir-1")
        assert persona_engine.persona_count == 1
        assert persona_engine.binding_count == 1

    def test_emits_event(self, integration, es):
        before = es.event_count
        integration.persona_for_executive_control("t-1", "dir-1")
        assert es.event_count > before

    def test_executive_authority_autonomous(self, integration):
        result = integration.persona_for_executive_control("t-1", "dir-1")
        assert result["authority_mode"] == "autonomous"


# ===================================================================
# Customer Support Tests
# ===================================================================


class TestCustomerSupport:
    def test_persona_for_customer_support(self, integration):
        result = integration.persona_for_customer_support("t-1", "cust-1")
        assert result["kind"] == "customer_support"
        assert result["interaction_style"] == "conversational"

    def test_creates_persona_and_binding(self, integration, persona_engine):
        integration.persona_for_customer_support("t-1", "cust-1")
        assert persona_engine.persona_count == 1
        assert persona_engine.binding_count == 1

    def test_emits_event(self, integration, es):
        before = es.event_count
        integration.persona_for_customer_support("t-1", "cust-1")
        assert es.event_count > before


# ===================================================================
# Regulatory Response Tests
# ===================================================================


class TestRegulatoryResponse:
    def test_persona_for_regulatory_response(self, integration):
        result = integration.persona_for_regulatory_response("t-1", "reg-1")
        assert result["kind"] == "regulatory"
        assert result["interaction_style"] == "formal"
        assert result["authority_mode"] == "restricted"

    def test_creates_persona_and_binding(self, integration, persona_engine):
        integration.persona_for_regulatory_response("t-1", "reg-1")
        assert persona_engine.persona_count == 1
        assert persona_engine.binding_count == 1

    def test_emits_event(self, integration, es):
        before = es.event_count
        integration.persona_for_regulatory_response("t-1", "reg-1")
        assert es.event_count > before

    # Golden scenario 4: regulatory -> FORMAL + RESTRICTED
    def test_regulatory_forces_formal_restricted(self, integration):
        result = integration.persona_for_regulatory_response("t-1", "reg-1")
        assert result["interaction_style"] == "formal"
        assert result["authority_mode"] == "restricted"


# ===================================================================
# Multimodal Session Tests
# ===================================================================


class TestMultimodalSession:
    def test_persona_for_multimodal_session(self, integration):
        result = integration.persona_for_multimodal_session("t-1", "mm-1")
        assert result["kind"] == "operator"

    def test_creates_persona_and_binding(self, integration, persona_engine):
        integration.persona_for_multimodal_session("t-1", "mm-1")
        assert persona_engine.persona_count == 1
        assert persona_engine.binding_count == 1


# ===================================================================
# Memory Mesh Attachment Tests
# ===================================================================


class TestMemoryMeshAttachment:
    def test_attach_persona_state_to_memory_mesh(self, integration, mem):
        result = integration.attach_persona_state_to_memory_mesh("scope-1")
        assert isinstance(result, MemoryRecord)

    def test_attach_emits_event(self, integration, es):
        before = es.event_count
        integration.attach_persona_state_to_memory_mesh("scope-1")
        assert es.event_count > before

    def test_attach_increments_memory_count(self, integration, mem):
        before = mem.memory_count
        integration.attach_persona_state_to_memory_mesh("scope-1")
        assert mem.memory_count == before + 1

    def test_attach_content_has_counts(self, integration):
        integration.persona_for_operator_workspace("t-1", "ws-1")
        record = integration.attach_persona_state_to_memory_mesh("scope-1")
        content = record.content
        assert "total_personas" in content
        assert "total_bindings" in content
        assert content["total_personas"] == 1

    def test_attach_memory_record_fields(self, integration):
        record = integration.attach_persona_state_to_memory_mesh("scope-1")
        assert record.scope_ref_id == "scope-1"
        assert record.title == "Persona state"
        assert "scope-1" not in record.title
        assert "persona" in record.tags or "persona" in list(record.tags)


# ===================================================================
# Graph Attachment Tests
# ===================================================================


class TestGraphAttachment:
    def test_attach_persona_state_to_graph(self, integration):
        result = integration.attach_persona_state_to_graph("scope-1")
        assert isinstance(result, dict)
        assert result["scope_ref_id"] == "scope-1"

    def test_graph_attachment_counts(self, integration, persona_engine):
        integration.persona_for_operator_workspace("t-1", "ws-1")
        result = integration.attach_persona_state_to_graph("scope-1")
        assert result["total_personas"] == 1
        assert result["total_bindings"] == 1

    def test_graph_attachment_empty(self, integration):
        result = integration.attach_persona_state_to_graph("scope-1")
        assert result["total_personas"] == 0
        assert result["total_policies"] == 0


# ===================================================================
# Multi-source / Multi-tenant Tests
# ===================================================================


class TestMultiSourceMultiTenant:
    def test_multiple_sources_same_tenant(self, integration, persona_engine):
        integration.persona_for_operator_workspace("t-1", "ws-1")
        integration.persona_for_product_console("t-1", "console-1")
        integration.persona_for_executive_control("t-1", "dir-1")
        assert persona_engine.persona_count == 3
        assert persona_engine.binding_count == 3

    def test_multiple_tenants(self, integration, persona_engine):
        integration.persona_for_operator_workspace("t-1", "ws-1")
        integration.persona_for_operator_workspace("t-2", "ws-2")
        assert persona_engine.persona_count == 2

    def test_end_to_end_workflow(self, integration, persona_engine, es, mem):
        """Full integration workflow."""
        # Create personas for multiple surfaces
        op = integration.persona_for_operator_workspace("t-1", "ws-1")
        ex = integration.persona_for_executive_control("t-1", "dir-1")
        cs = integration.persona_for_customer_support("t-1", "cust-1")
        reg = integration.persona_for_regulatory_response("t-1", "reg-1")

        assert persona_engine.persona_count == 4
        assert persona_engine.binding_count == 4

        # Attach to memory mesh
        record = integration.attach_persona_state_to_memory_mesh("t-1")
        assert record.content["total_personas"] == 4

        # Attach to graph
        graph = integration.attach_persona_state_to_graph("t-1")
        assert graph["total_personas"] == 4
        assert graph["total_bindings"] == 4

        # Verify events emitted
        assert es.event_count > 0

    def test_source_type_in_result(self, integration):
        r1 = integration.persona_for_operator_workspace("t-1", "ws-1")
        r2 = integration.persona_for_product_console("t-1", "c-1")
        r3 = integration.persona_for_executive_control("t-1", "d-1")
        r4 = integration.persona_for_customer_support("t-1", "cs-1")
        r5 = integration.persona_for_regulatory_response("t-1", "rg-1")
        r6 = integration.persona_for_multimodal_session("t-1", "mm-1")
        assert r1["source_type"] == "operator_workspace"
        assert r2["source_type"] == "product_console"
        assert r3["source_type"] == "executive_control"
        assert r4["source_type"] == "customer_support"
        assert r5["source_type"] == "regulatory_response"
        assert r6["source_type"] == "multimodal_session"

    def test_all_result_keys_present(self, integration):
        expected_keys = {"persona_id", "binding_id", "source_type",
                         "tenant_id", "kind", "status",
                         "interaction_style", "authority_mode"}
        result = integration.persona_for_operator_workspace("t-1", "ws-1")
        assert set(result.keys()) == expected_keys
