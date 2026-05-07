"""Gateway Integration Tests.

Tests: Approval flow in router, session manager context tracking,
    end-to-end message → approval → response flow.
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gateway.router import GatewayMessage, GatewayRouter, TenantMapping  # noqa: E402
from gateway.approval import ApprovalRouter  # noqa: E402
from gateway.session import SessionManager  # noqa: E402


# ═══ Stubs ═══


class StubPlatform:
    def __init__(self, response="Hello!"):
        self._response = response

    def connect(self, *, identity_id, tenant_id):
        return StubSession(self._response)


class StubSession:
    def __init__(self, response):
        self._response = response
        self.closed = False

    def llm(self, prompt, **kwargs):
        return type("R", (), {"content": self._response, "succeeded": True, "error": "", "cost": 0.001})()

    def close(self):
        self.closed = True


# ═══ Approval in Router ═══


class TestApprovalInRouter:
    def test_low_risk_auto_approved(self):
        router = GatewayRouter(platform=StubPlatform(response="42"))
        router.register_tenant_mapping(TenantMapping(
            channel="web", sender_id="u1", tenant_id="t1", identity_id="u1",
        ))
        # "what is 2+2" is low-risk → auto-approve → LLM response
        resp = router.handle_message(GatewayMessage(
            message_id="m1", channel="web", sender_id="u1", body="what is 2+2?",
        ))
        assert resp.body == "42"
        assert resp.metadata.get("approval_required") is None

    def test_high_risk_requires_approval(self):
        router = GatewayRouter(platform=StubPlatform())
        router.register_tenant_mapping(TenantMapping(
            channel="web", sender_id="u1", tenant_id="t1", identity_id="u1",
        ))
        # "delete all files" is high-risk → pending approval
        resp = router.handle_message(GatewayMessage(
            message_id="m1", channel="web", sender_id="u1", body="delete all old files",
        ))
        assert "requires approval" in resp.body
        assert resp.metadata.get("approval_required") is True
        assert router.pending_approvals == 1

    def test_approval_callback_resolves(self):
        router = GatewayRouter(platform=StubPlatform())
        router.register_tenant_mapping(TenantMapping(
            channel="web", sender_id="u1", tenant_id="t1", identity_id="u1",
        ))
        resp = router.handle_message(GatewayMessage(
            message_id="m1", channel="web", sender_id="u1", body="send_email to client",
        ))
        request_id = resp.metadata["request_id"]
        # Approve
        callback_resp = router.handle_approval_callback(request_id, approved=True)
        assert callback_resp is not None
        assert "approved" in callback_resp.body
        assert router.pending_approvals == 0

    def test_approval_callback_deny(self):
        router = GatewayRouter(platform=StubPlatform())
        router.register_tenant_mapping(TenantMapping(
            channel="web", sender_id="u1", tenant_id="t1", identity_id="u1",
        ))
        resp = router.handle_message(GatewayMessage(
            message_id="m1", channel="web", sender_id="u1", body="execute dangerous script",
        ))
        request_id = resp.metadata["request_id"]
        callback_resp = router.handle_approval_callback(request_id, approved=False)
        assert "denied" in callback_resp.body

    def test_approval_callback_unknown_request(self):
        router = GatewayRouter(platform=StubPlatform())
        assert router.handle_approval_callback("nonexistent", approved=True) is None

    def test_approval_callback_reports_expired_request(self):
        times = [
            "2026-04-20T12:00:00+00:00",
            "2026-04-20T12:10:00+00:00",
        ]

        def clock() -> str:
            return times.pop(0) if len(times) > 1 else times[0]

        router = GatewayRouter(
            platform=StubPlatform(),
            approval_router=ApprovalRouter(clock=clock, timeout_seconds=60),
        )
        router.register_tenant_mapping(TenantMapping(
            channel="web", sender_id="u1", tenant_id="t1", identity_id="u1",
        ))
        resp = router.handle_message(GatewayMessage(
            message_id="m1", channel="web", sender_id="u1", body="delete all old files",
        ))
        request_id = resp.metadata["request_id"]
        callback_resp = router.handle_approval_callback(request_id, approved=True)
        assert callback_resp is not None
        assert "expired" in callback_resp.body
        assert router.pending_approvals == 0


# ═══ Session Manager ═══


class TestSessionManager:
    def test_create_new_context(self):
        mgr = SessionManager()
        ctx = mgr.get_or_create(
            channel="whatsapp", sender_id="+1234",
            tenant_id="t1", identity_id="u1",
        )
        assert ctx.channel == "whatsapp"
        assert ctx.sender_id == "+1234"
        assert ctx.tenant_id == "t1"
        assert ctx.message_count == 0

    def test_get_existing_context(self):
        mgr = SessionManager()
        ctx1 = mgr.get_or_create(channel="web", sender_id="u1", tenant_id="t1", identity_id="u1")
        ctx2 = mgr.get_or_create(channel="web", sender_id="u1", tenant_id="t1", identity_id="u1")
        assert ctx1.session_id == ctx2.session_id

    def test_expired_context_is_replaced(self):
        timestamps = iter((
            "2026-04-24T00:00:00+00:00",
            "2026-04-24T00:00:30+00:00",
        ))
        mgr = SessionManager(clock=lambda: next(timestamps), session_ttl_seconds=10)
        ctx1 = mgr.get_or_create(channel="web", sender_id="u1", tenant_id="t1", identity_id="u1")
        ctx1.messages.append({"role": "user", "content": "stale"})

        ctx2 = mgr.get_or_create(channel="web", sender_id="u1", tenant_id="t1", identity_id="u1")

        assert ctx2.session_id != ctx1.session_id
        assert ctx2.message_count == 0
        assert ctx2.last_active_at == "2026-04-24T00:00:30+00:00"
        assert mgr.active_sessions == 1
        assert mgr.summary()["total_evicted"] == 1
        assert mgr.summary()["eviction_reasons"] == {"ttl_expired": 1}

    def test_invalid_ttl_timestamp_evicts_context_and_counts_repair(self):
        timestamps = iter((
            "2026-04-24T00:00:00+00:00",
            "2026-04-24T00:00:05+00:00",
        ))
        mgr = SessionManager(clock=lambda: next(timestamps), session_ttl_seconds=10)
        ctx1 = mgr.get_or_create(channel="web", sender_id="u1", tenant_id="t1", identity_id="u1")
        ctx1.last_active_at = "not-a-timestamp"
        ctx1.messages.append({"role": "user", "content": "unsafe stale context"})

        ctx2 = mgr.get_or_create(channel="web", sender_id="u1", tenant_id="t1", identity_id="u1")

        assert ctx2.session_id != ctx1.session_id
        assert ctx2.message_count == 0
        assert mgr.ttl_parse_failures == 1
        assert mgr.summary()["ttl_parse_failures"] == 1
        assert mgr.summary()["total_evicted"] == 1
        assert mgr.summary()["eviction_reasons"] == {"invalid_ttl_timestamp": 1}
        assert mgr.active_sessions == 1

    def test_capacity_eviction_reports_bounded_reason(self):
        timestamps = iter((
            "2026-04-24T00:00:00+00:00",
            "2026-04-24T00:00:01+00:00",
        ))
        mgr = SessionManager(clock=lambda: next(timestamps))
        mgr.MAX_SESSIONS = 1
        first = mgr.get_or_create(channel="web", sender_id="secret-user-1", tenant_id="t1", identity_id="u1")
        second = mgr.get_or_create(channel="web", sender_id="secret-user-2", tenant_id="t1", identity_id="u2")
        summary = mgr.summary()

        assert first.session_id != second.session_id
        assert mgr.active_sessions == 1
        assert mgr.get_context("web", "secret-user-1", tenant_id="t1") is None
        assert mgr.get_context("web", "secret-user-2", tenant_id="t1") is not None
        assert summary["total_evicted"] == 1
        assert summary["eviction_reasons"] == {"capacity_pressure": 1}
        assert "secret-user-1" not in summary["eviction_reasons"]

    def test_add_message(self):
        mgr = SessionManager()
        mgr.get_or_create(channel="web", sender_id="u1", tenant_id="t1", identity_id="u1")
        mgr.add_message("web", "u1", "user", "hello", tenant_id="t1")
        mgr.add_message("web", "u1", "assistant", "hi there", tenant_id="t1")
        ctx = mgr.get_context("web", "u1", tenant_id="t1")
        assert ctx.message_count == 2
        assert ctx.messages[0]["role"] == "user"
        assert ctx.messages[1]["role"] == "assistant"

    def test_message_pruning(self):
        mgr = SessionManager(max_context_messages=5)
        mgr.get_or_create(channel="web", sender_id="u1", tenant_id="t1", identity_id="u1")
        for i in range(10):
            mgr.add_message("web", "u1", "user", f"msg-{i}", tenant_id="t1")
        ctx = mgr.get_context("web", "u1", tenant_id="t1")
        assert ctx.message_count == 5
        assert ctx.messages[0]["content"] == "msg-5"  # Oldest pruned

    def test_clear_context(self):
        mgr = SessionManager()
        mgr.get_or_create(channel="web", sender_id="u1", tenant_id="t1", identity_id="u1")
        assert mgr.active_sessions == 1
        mgr.clear_context("web", "u1", tenant_id="t1")
        assert mgr.active_sessions == 0

    def test_different_users_separate_contexts(self):
        mgr = SessionManager()
        mgr.get_or_create(channel="web", sender_id="u1", tenant_id="t1", identity_id="u1")
        mgr.get_or_create(channel="web", sender_id="u2", tenant_id="t1", identity_id="u2")
        assert mgr.active_sessions == 2

    def test_same_user_different_channels(self):
        mgr = SessionManager()
        mgr.get_or_create(channel="whatsapp", sender_id="123", tenant_id="t1", identity_id="u1")
        mgr.get_or_create(channel="telegram", sender_id="123", tenant_id="t1", identity_id="u1")
        assert mgr.active_sessions == 2

    def test_get_nonexistent_context(self):
        mgr = SessionManager()
        assert mgr.get_context("web", "unknown") is None

    def test_summary(self):
        mgr = SessionManager(max_context_messages=10)
        assert mgr.summary()["active_sessions"] == 0
        assert mgr.summary()["max_context_messages"] == 10
        assert mgr.summary()["ttl_parse_failures"] == 0
        assert mgr.summary()["total_evicted"] == 0
        assert mgr.summary()["eviction_reasons"] == {}
