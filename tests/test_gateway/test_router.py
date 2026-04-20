"""Gateway Router Tests.

Tests: Message routing, tenant resolution, governed session integration,
    error handling, channel adapter registration.
"""

import sys
from pathlib import Path

# Add gateway to path
_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pytest
from gateway.approval import ApprovalRouter
from gateway.router import GatewayMessage, GatewayResponse, GatewayRouter, TenantMapping


class StubPlatform:
    """Minimal platform stub for gateway testing."""

    def __init__(self, llm_response: str = "Hello! How can I help?", fail: bool = False):
        self._llm_response = llm_response
        self._fail = fail
        self.sessions_opened = 0

    def connect(self, *, identity_id: str, tenant_id: str):
        self.sessions_opened += 1
        if self._fail:
            raise PermissionError("tenant suspended")
        return StubSession(self._llm_response)


class StubSession:
    def __init__(self, response: str):
        self._response = response
        self.closed = False

    def llm(self, prompt, **kwargs):
        return StubLLMResult(self._response)

    def close(self):
        self.closed = True


class StubLLMResult:
    def __init__(self, content: str):
        self.content = content
        self.succeeded = True
        self.error = ""


class StubChannel:
    channel_name = "test"

    def __init__(self):
        self.sent_messages: list[tuple[str, str]] = []

    def send(self, recipient_id: str, body: str, **kwargs):
        self.sent_messages.append((recipient_id, body))
        return True


# ═══ Tenant Resolution ═══


class TestTenantResolution:
    def test_resolve_known_tenant(self):
        router = GatewayRouter(platform=StubPlatform())
        router.register_tenant_mapping(TenantMapping(
            channel="whatsapp", sender_id="+1234567890",
            tenant_id="t1", identity_id="user1",
        ))
        mapping = router.resolve_tenant("whatsapp", "+1234567890")
        assert mapping is not None
        assert mapping.tenant_id == "t1"

    def test_resolve_unknown_tenant(self):
        router = GatewayRouter(platform=StubPlatform())
        assert router.resolve_tenant("whatsapp", "+9999999999") is None

    def test_resolve_different_channels(self):
        router = GatewayRouter(platform=StubPlatform())
        router.register_tenant_mapping(TenantMapping(
            channel="whatsapp", sender_id="123", tenant_id="t1", identity_id="u1",
        ))
        router.register_tenant_mapping(TenantMapping(
            channel="telegram", sender_id="123", tenant_id="t2", identity_id="u2",
        ))
        assert router.resolve_tenant("whatsapp", "123").tenant_id == "t1"
        assert router.resolve_tenant("telegram", "123").tenant_id == "t2"


# ═══ Message Routing ═══


class TestMessageRouting:
    def test_successful_message(self):
        router = GatewayRouter(platform=StubPlatform(llm_response="The answer is 4."))
        router.register_tenant_mapping(TenantMapping(
            channel="whatsapp", sender_id="+1234567890",
            tenant_id="t1", identity_id="user1",
        ))
        msg = GatewayMessage(
            message_id="msg1", channel="whatsapp",
            sender_id="+1234567890", body="What is 2+2?",
        )
        response = router.handle_message(msg)
        assert response.body == "The answer is 4."
        assert response.governed is True
        assert response.channel == "whatsapp"
        assert response.recipient_id == "+1234567890"

    def test_unknown_tenant_returns_error(self):
        router = GatewayRouter(platform=StubPlatform())
        msg = GatewayMessage(
            message_id="msg1", channel="whatsapp",
            sender_id="+unknown", body="Hello",
        )
        response = router.handle_message(msg)
        assert "don't recognize" in response.body
        assert response.metadata.get("error") == "tenant_not_found"

    def test_suspended_tenant_returns_denial(self):
        router = GatewayRouter(platform=StubPlatform(fail=True))
        router.register_tenant_mapping(TenantMapping(
            channel="whatsapp", sender_id="+1234567890",
            tenant_id="t1", identity_id="user1",
        ))
        msg = GatewayMessage(
            message_id="msg1", channel="whatsapp",
            sender_id="+1234567890", body="Hello",
        )
        response = router.handle_message(msg)
        assert "Access denied" in response.body

    def test_message_count_increments(self):
        router = GatewayRouter(platform=StubPlatform())
        router.register_tenant_mapping(TenantMapping(
            channel="web", sender_id="u1", tenant_id="t1", identity_id="u1",
        ))
        assert router.message_count == 0
        router.handle_message(GatewayMessage(message_id="m1", channel="web", sender_id="u1", body="hi"))
        router.handle_message(GatewayMessage(message_id="m2", channel="web", sender_id="u1", body="there"))
        assert router.message_count == 2


# ═══ Channel Adapter Integration ═══


class TestChannelAdapterIntegration:
    def test_response_sent_through_channel(self):
        channel = StubChannel()
        router = GatewayRouter(platform=StubPlatform(llm_response="Got it!"))
        router.register_channel(channel)
        router.register_tenant_mapping(TenantMapping(
            channel="test", sender_id="u1", tenant_id="t1", identity_id="u1",
        ))
        router.handle_message(GatewayMessage(
            message_id="m1", channel="test", sender_id="u1", body="hello",
        ))
        assert len(channel.sent_messages) == 1
        assert channel.sent_messages[0] == ("u1", "Got it!")

    def test_no_channel_adapter_still_returns_response(self):
        router = GatewayRouter(platform=StubPlatform(llm_response="Response"))
        router.register_tenant_mapping(TenantMapping(
            channel="unknown", sender_id="u1", tenant_id="t1", identity_id="u1",
        ))
        response = router.handle_message(GatewayMessage(
            message_id="m1", channel="unknown", sender_id="u1", body="hello",
        ))
        assert response.body == "Response"

    def test_channel_approval_callback_resolves_for_same_identity(self):
        times = [
            "2026-04-20T12:00:00+00:00",
            "2026-04-20T12:00:01+00:00",
            "2026-04-20T12:00:02+00:00",
        ]

        def clock():
            return times.pop(0) if len(times) > 1 else times[0]

        channel = StubChannel()
        platform = StubPlatform(llm_response="pending")
        router = GatewayRouter(
            platform=platform,
            clock=clock,
            approval_router=ApprovalRouter(clock=clock, timeout_seconds=300),
        )
        router.register_channel(channel)
        router.register_tenant_mapping(TenantMapping(
            channel="test", sender_id="u1", tenant_id="t1", identity_id="identity-1",
        ))

        pending = router.handle_message(GatewayMessage(
            message_id="m1", channel="test", sender_id="u1", body="delete all files",
        ))
        request_id = pending.metadata["request_id"]

        resolved = router.handle_message(GatewayMessage(
            message_id="m2", channel="test", sender_id="u1", body=f"approve:{request_id}",
        ))

        assert pending.metadata["approval_required"] is True
        assert resolved.metadata["approval_resolved"] is True
        assert resolved.metadata["status"] == "approved"
        assert "approved" in resolved.body
        assert platform.sessions_opened == 1
        assert channel.sent_messages[-1] == ("u1", resolved.body)

    def test_channel_approval_callback_denies_mismatched_identity(self):
        times = [
            "2026-04-20T12:00:00+00:00",
            "2026-04-20T12:00:01+00:00",
        ]

        def clock():
            return times.pop(0) if len(times) > 1 else times[0]

        router = GatewayRouter(
            platform=StubPlatform(llm_response="pending"),
            clock=clock,
            approval_router=ApprovalRouter(clock=clock, timeout_seconds=300),
        )
        router.register_tenant_mapping(TenantMapping(
            channel="test", sender_id="owner", tenant_id="t1", identity_id="identity-1",
        ))
        router.register_tenant_mapping(TenantMapping(
            channel="test", sender_id="other", tenant_id="t1", identity_id="identity-2",
        ))

        pending = router.handle_message(GatewayMessage(
            message_id="m1", channel="test", sender_id="owner", body="delete all files",
        ))
        request_id = pending.metadata["request_id"]

        denied = router.handle_message(GatewayMessage(
            message_id="m2", channel="test", sender_id="other", body=f"approve:{request_id}",
        ))

        assert denied.metadata["error"] == "approval_context_denied"
        assert "not allowed" in denied.body
        assert router.pending_approvals == 1


# ═══ Summary ═══


class TestRouterSummary:
    def test_summary(self):
        channel = StubChannel()
        router = GatewayRouter(platform=StubPlatform())
        router.register_channel(channel)
        router.register_tenant_mapping(TenantMapping(
            channel="test", sender_id="u1", tenant_id="t1", identity_id="u1",
        ))
        summary = router.summary()
        assert summary["channels"] == ["test"]
        assert summary["tenant_mappings"] == 1
