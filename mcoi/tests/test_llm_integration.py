"""Phase 199A — LLM integration bridge tests.

Tests: LLMIntegrationBridge complete/chat, budget management, invocation history.
"""

import pytest
from mcoi_runtime.contracts.llm import (
    LLMBudget,
    LLMProvider,
    LLMResult,
)
from mcoi_runtime.adapters.llm_adapter import StubLLMBackend
from mcoi_runtime.core.llm_integration import LLMIntegrationBridge


FIXED_CLOCK = lambda: "2026-03-26T12:00:00Z"


class TestLLMIntegrationBridge:
    def _bridge(self, ledger_entries=None):
        entries = ledger_entries if ledger_entries is not None else []
        bridge = LLMIntegrationBridge(
            clock=FIXED_CLOCK,
            default_backend=StubLLMBackend(),
            ledger_sink=entries.append if entries is not None else None,
        )
        return bridge, entries

    # ═══ complete() ═══

    def test_basic_complete(self):
        bridge, _ = self._bridge()
        result = bridge.complete("What is 2+2?")
        assert result.succeeded is True
        assert result.content
        assert result.provider == LLMProvider.STUB
        assert bridge.invocation_count == 1

    def test_complete_with_system(self):
        bridge, _ = self._bridge()
        result = bridge.complete("hello", system="you are a math tutor")
        assert result.succeeded is True

    def test_complete_with_budget(self):
        bridge, _ = self._bridge()
        bridge.register_budget(LLMBudget(budget_id="b1", tenant_id="t1", max_cost=10.0))
        result = bridge.complete("test", budget_id="b1")
        assert result.succeeded is True

    def test_complete_budget_exhausted(self):
        bridge, _ = self._bridge()
        bridge.register_budget(LLMBudget(budget_id="b1", tenant_id="t1", max_cost=0.0001, max_calls=1))
        bridge.complete("first", budget_id="b1")
        result = bridge.complete("second", budget_id="b1")
        assert result.succeeded is False
        assert "budget" in result.error.lower()

    def test_complete_unknown_backend(self):
        bridge, _ = self._bridge()
        result = bridge.complete("test", backend_name="nonexistent")
        assert result.succeeded is False
        assert "unknown backend" in result.error

    def test_complete_custom_params(self):
        bridge, _ = self._bridge()
        result = bridge.complete(
            "test",
            model_name="custom-model",
            max_tokens=2048,
            temperature=0.5,
            tenant_id="tenant-x",
        )
        assert result.succeeded is True
        assert result.model_name == "custom-model"

    # ═══ chat() ═══

    def test_basic_chat(self):
        bridge, _ = self._bridge()
        result = bridge.chat([
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
            {"role": "user", "content": "How are you?"},
        ])
        assert result.succeeded is True
        assert result.content

    def test_chat_with_system(self):
        bridge, _ = self._bridge()
        result = bridge.chat([
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "test"},
        ])
        assert result.succeeded is True

    def test_chat_unknown_backend(self):
        bridge, _ = self._bridge()
        result = bridge.chat(
            [{"role": "user", "content": "test"}],
            backend_name="missing",
        )
        assert result.succeeded is False

    # ═══ Multi-backend ═══

    def test_register_multiple_backends(self):
        bridge, _ = self._bridge()
        bridge.register_backend("alt", StubLLMBackend(response_prefix="alt"))
        r1 = bridge.complete("test", backend_name="default")
        r2 = bridge.complete("test", backend_name="alt")
        assert r1.content != r2.content
        assert r1.content.startswith("stub-llm-response:")
        assert r2.content.startswith("alt:")

    # ═══ Reporting ═══

    def test_invocation_count(self):
        bridge, _ = self._bridge()
        assert bridge.invocation_count == 0
        bridge.complete("a")
        bridge.complete("b")
        assert bridge.invocation_count == 2

    def test_total_cost(self):
        bridge, _ = self._bridge()
        bridge.complete("a")
        bridge.complete("b")
        assert bridge.total_cost > 0

    def test_budget_summary(self):
        bridge, _ = self._bridge()
        bridge.register_budget(LLMBudget(budget_id="b1", tenant_id="t1", max_cost=10.0))
        bridge.complete("test", budget_id="b1")
        summary = bridge.budget_summary()
        assert len(summary["budgets"]) == 1
        assert summary["budgets"][0]["budget_id"] == "b1"
        assert summary["budgets"][0]["spent"] > 0
        assert summary["total_spent"] > 0

    def test_invocation_history(self):
        bridge, _ = self._bridge()
        bridge.complete("first")
        bridge.complete("second")
        history = bridge.invocation_history()
        assert len(history) == 2
        assert history[0]["id"] == "llm-1"
        assert history[1]["id"] == "llm-2"
        assert all(h["succeeded"] for h in history)

    def test_invocation_history_limit(self):
        bridge, _ = self._bridge()
        for i in range(5):
            bridge.complete(f"msg-{i}")
        history = bridge.invocation_history(limit=3)
        assert len(history) == 3

    # ═══ Ledger ═══

    def test_ledger_entries_recorded(self):
        bridge, entries = self._bridge()
        bridge.complete("test")
        assert len(entries) >= 1
        assert entries[0]["type"] == "llm_invocation"

    def test_no_ledger_sink_ok(self):
        bridge = LLMIntegrationBridge(
            clock=FIXED_CLOCK,
            default_backend=StubLLMBackend(),
            ledger_sink=None,
        )
        result = bridge.complete("test")
        assert result.succeeded is True


class TestLLMIntegrationBridgeBudgetEdgeCases:
    def _bridge(self):
        return LLMIntegrationBridge(
            clock=FIXED_CLOCK,
            default_backend=StubLLMBackend(),
        )

    def test_multiple_budgets_independent(self):
        bridge = self._bridge()
        bridge.register_budget(LLMBudget(budget_id="b1", tenant_id="t1", max_cost=10.0, max_calls=2))
        bridge.register_budget(LLMBudget(budget_id="b2", tenant_id="t2", max_cost=10.0, max_calls=2))

        bridge.complete("test", budget_id="b1")
        bridge.complete("test", budget_id="b1")
        # b1 exhausted
        r = bridge.complete("test", budget_id="b1")
        assert r.succeeded is False

        # b2 still works
        r = bridge.complete("test", budget_id="b2")
        assert r.succeeded is True

    def test_budget_summary_multiple(self):
        bridge = self._bridge()
        bridge.register_budget(LLMBudget(budget_id="a", tenant_id="t1", max_cost=5.0))
        bridge.register_budget(LLMBudget(budget_id="b", tenant_id="t2", max_cost=10.0))
        bridge.complete("x", budget_id="a")
        summary = bridge.budget_summary()
        assert len(summary["budgets"]) == 2
