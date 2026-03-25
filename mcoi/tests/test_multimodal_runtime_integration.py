"""Tests for multimodal runtime integration bridge."""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.multimodal_runtime import (
    InteractionMode,
    SessionChannel,
)
from mcoi_runtime.contracts.memory_mesh import MemoryRecord
from mcoi_runtime.core.multimodal_runtime import MultimodalRuntimeEngine
from mcoi_runtime.core.multimodal_runtime_integration import MultimodalRuntimeIntegration
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.engine_protocol import FixedClock


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TS = "2026-01-01T00:00:00+00:00"


@pytest.fixture
def clock():
    return FixedClock(TS)


@pytest.fixture
def es():
    return EventSpineEngine()


@pytest.fixture
def mem():
    return MemoryMeshEngine()


@pytest.fixture
def mmrt(es, clock):
    return MultimodalRuntimeEngine(es, clock=clock)


@pytest.fixture
def integration(mmrt, es, mem):
    return MultimodalRuntimeIntegration(mmrt, es, mem)


# =========================================================================
# Constructor validation
# =========================================================================


class TestConstructorValidation:
    def test_valid_construction(self, mmrt, es, mem):
        integ = MultimodalRuntimeIntegration(mmrt, es, mem)
        assert integ is not None

    def test_invalid_multimodal_engine(self, es, mem):
        with pytest.raises(RuntimeCoreInvariantError, match="MultimodalRuntimeEngine"):
            MultimodalRuntimeIntegration("not-an-engine", es, mem)

    def test_invalid_event_spine(self, mmrt, mem):
        with pytest.raises(RuntimeCoreInvariantError, match="EventSpineEngine"):
            MultimodalRuntimeIntegration(mmrt, "not-an-es", mem)

    def test_invalid_memory_engine(self, mmrt, es):
        with pytest.raises(RuntimeCoreInvariantError, match="MemoryMeshEngine"):
            MultimodalRuntimeIntegration(mmrt, es, "not-a-mem")

    def test_none_multimodal_engine(self, es, mem):
        with pytest.raises(RuntimeCoreInvariantError):
            MultimodalRuntimeIntegration(None, es, mem)

    def test_none_event_spine(self, mmrt, mem):
        with pytest.raises(RuntimeCoreInvariantError):
            MultimodalRuntimeIntegration(mmrt, None, mem)

    def test_none_memory_engine(self, mmrt, es):
        with pytest.raises(RuntimeCoreInvariantError):
            MultimodalRuntimeIntegration(mmrt, es, None)


# =========================================================================
# multimodal_from_copilot_session
# =========================================================================


class TestMultimodalFromCopilotSession:
    def test_basic(self, integration):
        result = integration.multimodal_from_copilot_session("t-1", "cop-1")
        assert result["source_type"] == "copilot_session"
        assert result["tenant_id"] == "t-1"
        assert result["status"] == "active"

    def test_auto_session_id(self, integration):
        result = integration.multimodal_from_copilot_session("t-1", "cop-1")
        assert result["session_id"]  # non-empty

    def test_explicit_session_id(self, integration):
        result = integration.multimodal_from_copilot_session(
            "t-1", "cop-1", session_id="my-sess")
        assert result["session_id"] == "my-sess"

    def test_default_mode(self, integration):
        result = integration.multimodal_from_copilot_session("t-1", "cop-1")
        assert result["mode"] == "voice"

    def test_default_channel(self, integration):
        result = integration.multimodal_from_copilot_session("t-1", "cop-1")
        assert result["channel"] == "web"

    def test_custom_mode(self, integration):
        result = integration.multimodal_from_copilot_session(
            "t-1", "cop-1", mode=InteractionMode.TEXT)
        assert result["mode"] == "text"

    def test_custom_channel(self, integration):
        result = integration.multimodal_from_copilot_session(
            "t-1", "cop-1", channel=SessionChannel.PHONE)
        assert result["channel"] == "phone"

    def test_emits_event(self, integration, es):
        before = es.event_count
        integration.multimodal_from_copilot_session("t-1", "cop-1")
        assert es.event_count > before

    def test_identity_ref_default(self, integration):
        result = integration.multimodal_from_copilot_session("t-1", "cop-1")
        assert result["identity_ref"] == "copilot_user"

    def test_custom_identity_ref(self, integration):
        result = integration.multimodal_from_copilot_session(
            "t-1", "cop-1", identity_ref="alice")
        assert result["identity_ref"] == "alice"


# =========================================================================
# multimodal_from_operator_workspace
# =========================================================================


class TestMultimodalFromOperatorWorkspace:
    def test_basic(self, integration):
        result = integration.multimodal_from_operator_workspace("t-1", "ws-1")
        assert result["source_type"] == "operator_workspace"

    def test_default_mode_hybrid(self, integration):
        result = integration.multimodal_from_operator_workspace("t-1", "ws-1")
        assert result["mode"] == "hybrid"

    def test_identity_ref_default(self, integration):
        result = integration.multimodal_from_operator_workspace("t-1", "ws-1")
        assert result["identity_ref"] == "operator"

    def test_emits_event(self, integration, es):
        before = es.event_count
        integration.multimodal_from_operator_workspace("t-1", "ws-1")
        assert es.event_count > before


# =========================================================================
# multimodal_from_product_console
# =========================================================================


class TestMultimodalFromProductConsole:
    def test_basic(self, integration):
        result = integration.multimodal_from_product_console("t-1", "console-1")
        assert result["source_type"] == "product_console"

    def test_default_mode_text(self, integration):
        result = integration.multimodal_from_product_console("t-1", "console-1")
        assert result["mode"] == "text"

    def test_identity_ref_default(self, integration):
        result = integration.multimodal_from_product_console("t-1", "console-1")
        assert result["identity_ref"] == "product_user"


# =========================================================================
# multimodal_from_communication_surface
# =========================================================================


class TestMultimodalFromCommunicationSurface:
    def test_basic(self, integration):
        result = integration.multimodal_from_communication_surface("t-1", "comm-1")
        assert result["source_type"] == "communication_surface"

    def test_default_channel_phone(self, integration):
        result = integration.multimodal_from_communication_surface("t-1", "comm-1")
        assert result["channel"] == "phone"

    def test_default_mode_voice(self, integration):
        result = integration.multimodal_from_communication_surface("t-1", "comm-1")
        assert result["mode"] == "voice"

    def test_identity_ref_default(self, integration):
        result = integration.multimodal_from_communication_surface("t-1", "comm-1")
        assert result["identity_ref"] == "caller"


# =========================================================================
# multimodal_from_service_request
# =========================================================================


class TestMultimodalFromServiceRequest:
    def test_basic(self, integration):
        result = integration.multimodal_from_service_request("t-1", "svc-1")
        assert result["source_type"] == "service_request"

    def test_default_mode_hybrid(self, integration):
        result = integration.multimodal_from_service_request("t-1", "svc-1")
        assert result["mode"] == "hybrid"

    def test_default_channel_chat(self, integration):
        result = integration.multimodal_from_service_request("t-1", "svc-1")
        assert result["channel"] == "chat"

    def test_identity_ref_default(self, integration):
        result = integration.multimodal_from_service_request("t-1", "svc-1")
        assert result["identity_ref"] == "service_agent"


# =========================================================================
# multimodal_from_executive_control
# =========================================================================


class TestMultimodalFromExecutiveControl:
    def test_basic(self, integration):
        result = integration.multimodal_from_executive_control("t-1", "dir-1")
        assert result["source_type"] == "executive_control"

    def test_default_mode_streaming(self, integration):
        result = integration.multimodal_from_executive_control("t-1", "dir-1")
        assert result["mode"] == "streaming"

    def test_default_channel_api(self, integration):
        result = integration.multimodal_from_executive_control("t-1", "dir-1")
        assert result["channel"] == "api"

    def test_identity_ref_default(self, integration):
        result = integration.multimodal_from_executive_control("t-1", "dir-1")
        assert result["identity_ref"] == "executive"


# =========================================================================
# Memory mesh attachment
# =========================================================================


class TestAttachMultimodalStateToMemoryMesh:
    def test_basic_attachment(self, integration):
        result = integration.attach_multimodal_state_to_memory_mesh("scope-1")
        assert isinstance(result, MemoryRecord)

    def test_memory_title(self, integration):
        result = integration.attach_multimodal_state_to_memory_mesh("scope-1")
        assert "scope-1" in result.title

    def test_memory_content_keys(self, integration):
        integration.multimodal_from_copilot_session("t-1", "cop-1")
        result = integration.attach_multimodal_state_to_memory_mesh("scope-1")
        content = result.content
        assert "total_sessions" in content
        assert "total_turns" in content

    def test_memory_tags(self, integration):
        result = integration.attach_multimodal_state_to_memory_mesh("scope-1")
        tags = result.tags
        assert "multimodal" in tags
        assert "voice" in tags

    def test_emits_event(self, integration, es):
        before = es.event_count
        integration.attach_multimodal_state_to_memory_mesh("scope-1")
        assert es.event_count > before

    def test_memory_count_reflects_sessions(self, integration, mmrt):
        integration.multimodal_from_copilot_session("t-1", "cop-1")
        result = integration.attach_multimodal_state_to_memory_mesh("scope-1")
        assert result.content["total_sessions"] == 1


# =========================================================================
# Graph attachment
# =========================================================================


class TestAttachMultimodalStateToGraph:
    def test_basic(self, integration):
        result = integration.attach_multimodal_state_to_graph("scope-1")
        assert isinstance(result, dict)
        assert result["scope_ref_id"] == "scope-1"

    def test_contains_all_counts(self, integration):
        result = integration.attach_multimodal_state_to_graph("scope-1")
        for key in ("total_sessions", "total_turns", "total_transcripts",
                    "total_presence", "total_interruptions", "total_plans",
                    "total_decisions", "total_violations"):
            assert key in result

    def test_counts_reflect_engine_state(self, integration, mmrt):
        integration.multimodal_from_copilot_session("t-1", "cop-1")
        result = integration.attach_multimodal_state_to_graph("scope-1")
        assert result["total_sessions"] == 1


# =========================================================================
# Cross-surface / multi-session
# =========================================================================


class TestCrossSurfaceScenarios:
    def test_multiple_sources_same_tenant(self, integration):
        r1 = integration.multimodal_from_copilot_session("t-1", "cop-1")
        r2 = integration.multimodal_from_operator_workspace("t-1", "ws-1")
        r3 = integration.multimodal_from_product_console("t-1", "console-1")
        assert r1["session_id"] != r2["session_id"]
        assert r2["session_id"] != r3["session_id"]

    def test_duplicate_explicit_session_id_rejected(self, integration):
        integration.multimodal_from_copilot_session("t-1", "cop-1", session_id="dup")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            integration.multimodal_from_operator_workspace("t-1", "ws-1", session_id="dup")

    def test_all_sources_emit_events(self, integration, es):
        before = es.event_count
        integration.multimodal_from_copilot_session("t-1", "cop-1")
        integration.multimodal_from_operator_workspace("t-1", "ws-1")
        integration.multimodal_from_product_console("t-1", "console-1")
        integration.multimodal_from_communication_surface("t-1", "comm-1")
        integration.multimodal_from_service_request("t-1", "svc-1")
        integration.multimodal_from_executive_control("t-1", "dir-1")
        # Each source emits at least 2 events (session start + bridge event)
        assert es.event_count >= before + 12

    def test_graph_reflects_all_sessions(self, integration):
        integration.multimodal_from_copilot_session("t-1", "cop-1")
        integration.multimodal_from_operator_workspace("t-1", "ws-1")
        result = integration.attach_multimodal_state_to_graph("scope-1")
        assert result["total_sessions"] == 2
