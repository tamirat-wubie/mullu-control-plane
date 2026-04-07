"""Session Action Limits Tests — Per-session policy enforcement.

Verifies that SessionPolicy constrains what a governed session can do:
max LLM calls, max operations, max execute actions, max cost.
"""

import pytest
from mcoi_runtime.core.governed_session import (
    GovernedSession,
    Platform,
    SessionPolicy,
)


def _platform(**kw):
    return Platform(clock=lambda: "2026-04-07T12:00:00Z", **kw)


# ── SessionPolicy validation ──────────────────────────────────

class TestSessionPolicyValidation:
    def test_default_policy_is_unlimited(self):
        p = SessionPolicy()
        assert p.max_llm_calls == 0
        assert p.max_operations == 0
        assert p.max_execute_actions == 0
        assert p.max_cost == 0.0

    def test_custom_limits(self):
        p = SessionPolicy(max_llm_calls=10, max_operations=50, max_cost=5.0)
        assert p.max_llm_calls == 10
        assert p.max_operations == 50

    def test_negative_llm_calls_rejected(self):
        with pytest.raises(ValueError, match="max_llm_calls"):
            SessionPolicy(max_llm_calls=-1)

    def test_negative_operations_rejected(self):
        with pytest.raises(ValueError, match="max_operations"):
            SessionPolicy(max_operations=-1)

    def test_negative_execute_rejected(self):
        with pytest.raises(ValueError, match="max_execute_actions"):
            SessionPolicy(max_execute_actions=-1)

    def test_negative_cost_rejected(self):
        with pytest.raises(ValueError, match="max_cost"):
            SessionPolicy(max_cost=-0.01)

    def test_policy_is_frozen(self):
        p = SessionPolicy(max_llm_calls=5)
        with pytest.raises(AttributeError):
            p.max_llm_calls = 10


# ── LLM call limits ───────────────────────────────────────────

class TestLLMCallLimits:
    def _session_with_llm(self, policy, llm_bridge=None):
        """Create a session with a stub LLM bridge and policy."""
        from dataclasses import dataclass

        @dataclass
        class StubResult:
            succeeded: bool = True
            content: str = "response"
            cost: float = 0.01
            model_name: str = "stub"
            input_tokens: int = 10
            output_tokens: int = 10
            error: str = ""

        class StubBridge:
            def complete(self, prompt, **kw):
                return StubResult()

        p = _platform(llm_bridge=llm_bridge or StubBridge())
        return p.connect(identity_id="user1", tenant_id="t1", session_policy=policy)

    def test_llm_limit_enforced(self):
        session = self._session_with_llm(SessionPolicy(max_llm_calls=2))
        session.llm("first")
        session.llm("second")
        with pytest.raises(RuntimeError, match="LLM call limit"):
            session.llm("third")

    def test_llm_limit_zero_means_unlimited(self):
        session = self._session_with_llm(SessionPolicy(max_llm_calls=0))
        for i in range(10):
            session.llm(f"call-{i}")
        # Should not raise

    def test_llm_limit_does_not_block_execute(self):
        session = self._session_with_llm(SessionPolicy(max_llm_calls=1))
        session.llm("one")
        # LLM exhausted, but execute should still work
        session.execute("test_action")

    def test_llm_limit_does_not_block_query(self):
        session = self._session_with_llm(SessionPolicy(max_llm_calls=1))
        session.llm("one")
        session.query("tenants")  # Should work


# ── Execute action limits ──────────────────────────────────────

class TestExecuteActionLimits:
    def test_execute_limit_enforced(self):
        p = _platform()
        session = p.connect(
            identity_id="user1", tenant_id="t1",
            session_policy=SessionPolicy(max_execute_actions=2),
        )
        session.execute("action1")
        session.execute("action2")
        with pytest.raises(RuntimeError, match="execute action limit"):
            session.execute("action3")

    def test_execute_limit_does_not_block_llm(self):
        from dataclasses import dataclass

        @dataclass
        class StubResult:
            succeeded: bool = True
            content: str = "ok"
            cost: float = 0.0
            model_name: str = "stub"
            input_tokens: int = 0
            output_tokens: int = 0
            error: str = ""

        class StubBridge:
            def complete(self, prompt, **kw):
                return StubResult()

        p = _platform(llm_bridge=StubBridge())
        session = p.connect(
            identity_id="user1", tenant_id="t1",
            session_policy=SessionPolicy(max_execute_actions=1),
        )
        session.execute("one")
        # Execute exhausted, but LLM should still work
        session.llm("hello")

    def test_execute_counter_tracked(self):
        p = _platform()
        session = p.connect(identity_id="user1", tenant_id="t1")
        session.execute("a")
        session.execute("b")
        assert session.execute_actions == 2


# ── Total operations limit ─────────────────────────────────────

class TestOperationsLimit:
    def test_operations_limit_caps_all_types(self):
        from dataclasses import dataclass

        @dataclass
        class StubResult:
            succeeded: bool = True
            content: str = "ok"
            cost: float = 0.0
            model_name: str = "stub"
            input_tokens: int = 0
            output_tokens: int = 0
            error: str = ""

        class StubBridge:
            def complete(self, prompt, **kw):
                return StubResult()

        p = _platform(llm_bridge=StubBridge())
        session = p.connect(
            identity_id="user1", tenant_id="t1",
            session_policy=SessionPolicy(max_operations=3),
        )
        session.llm("one")        # op 1
        session.execute("two")    # op 2
        session.query("three")    # op 3
        with pytest.raises(RuntimeError, match="operation limit"):
            session.llm("four")

    def test_operations_limit_blocks_query(self):
        p = _platform()
        session = p.connect(
            identity_id="user1", tenant_id="t1",
            session_policy=SessionPolicy(max_operations=1),
        )
        session.query("tenants")
        with pytest.raises(RuntimeError, match="operation limit"):
            session.query("tenants")


# ── Cost limit ─────────────────────────────────────────────────

class TestCostLimit:
    def test_cost_limit_blocks_llm(self):
        from dataclasses import dataclass

        @dataclass
        class StubResult:
            succeeded: bool = True
            content: str = "ok"
            cost: float = 0.50
            model_name: str = "stub"
            input_tokens: int = 100
            output_tokens: int = 100
            error: str = ""

        class StubBridge:
            def complete(self, prompt, **kw):
                return StubResult()

        p = _platform(llm_bridge=StubBridge())
        session = p.connect(
            identity_id="user1", tenant_id="t1",
            session_policy=SessionPolicy(max_cost=1.0),
        )
        session.llm("a")  # cost=0.50
        session.llm("b")  # cost=1.00 — at limit
        with pytest.raises(RuntimeError, match="cost limit"):
            session.llm("c")  # Would exceed

    def test_cost_limit_zero_means_unlimited(self):
        from dataclasses import dataclass

        @dataclass
        class StubResult:
            succeeded: bool = True
            content: str = "ok"
            cost: float = 10.0
            model_name: str = "stub"
            input_tokens: int = 0
            output_tokens: int = 0
            error: str = ""

        class StubBridge:
            def complete(self, prompt, **kw):
                return StubResult()

        p = _platform(llm_bridge=StubBridge())
        session = p.connect(
            identity_id="user1", tenant_id="t1",
            session_policy=SessionPolicy(max_cost=0.0),
        )
        for _ in range(5):
            session.llm("expensive")  # No limit — should not raise


# ── No policy = backward compatible ────────────────────────────

class TestNoPolicyBackwardCompat:
    def test_no_policy_allows_unlimited(self):
        p = _platform()
        session = p.connect(identity_id="user1", tenant_id="t1")
        # No policy — should allow everything
        for _ in range(20):
            session.execute("action")
            session.query("stuff")
        assert session.operations == 40

    def test_session_policy_property(self):
        p = _platform()
        s1 = p.connect(identity_id="user1", tenant_id="t1")
        assert s1.session_policy is None

        policy = SessionPolicy(max_llm_calls=5)
        s2 = p.connect(identity_id="user1", tenant_id="t1", session_policy=policy)
        assert s2.session_policy is policy
        assert s2.session_policy.max_llm_calls == 5


# ── Combined limits ────────────────────────────────────────────

class TestCombinedLimits:
    def test_tightest_limit_wins(self):
        """When multiple limits are set, the tightest one triggers first."""
        p = _platform()
        session = p.connect(
            identity_id="user1", tenant_id="t1",
            session_policy=SessionPolicy(
                max_operations=10,
                max_execute_actions=2,
            ),
        )
        session.execute("a")
        session.execute("b")
        # execute_actions=2 is tighter than operations=10
        with pytest.raises(RuntimeError, match="execute action limit"):
            session.execute("c")

    def test_error_message_is_bounded(self):
        """Error messages don't leak internal state."""
        p = _platform()
        session = p.connect(
            identity_id="user1", tenant_id="secret-tenant",
            session_policy=SessionPolicy(max_operations=1),
        )
        session.query("test")
        with pytest.raises(RuntimeError) as exc_info:
            session.query("test")
        assert "secret-tenant" not in str(exc_info.value)
