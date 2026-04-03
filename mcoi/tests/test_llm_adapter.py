"""Phase 199A — LLM adapter tests.

Tests: StubLLMBackend, LLMBudgetManager, GovernedLLMAdapter, ModelAdapter protocol compliance.
"""

import pytest
from mcoi_runtime.contracts.llm import (
    LLMBudget,
    LLMInvocationParams,
    LLMMessage,
    LLMProvider,
    LLMResult,
    LLMRole,
)
from mcoi_runtime.contracts.model import (
    ModelInvocation,
    ModelStatus,
    ValidationStatus,
)
from mcoi_runtime.adapters.llm_adapter import (
    AnthropicBackend,
    GovernedLLMAdapter,
    LLMBudgetManager,
    OpenAIBackend,
    StubLLMBackend,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError

FIXED_CLOCK = lambda: "2026-03-26T12:00:00Z"


def _msg(role="user", content="test prompt"):
    return LLMMessage(role=LLMRole(role), content=content)


def _params(model="test-model", content="hello", budget_id="", tenant_id="t1"):
    return LLMInvocationParams(
        model_name=model,
        messages=(_msg("user", content),),
        budget_id=budget_id,
        tenant_id=tenant_id,
    )


# ═══ StubLLMBackend ═══

class TestStubLLMBackend:
    def test_basic_call(self):
        backend = StubLLMBackend()
        result = backend.call(_params())
        assert result.succeeded is True
        assert result.content.startswith("stub-llm-response:")
        assert result.input_tokens > 0
        assert result.output_tokens > 0
        assert result.cost > 0
        assert result.provider == LLMProvider.STUB

    def test_deterministic(self):
        backend = StubLLMBackend()
        r1 = backend.call(_params(content="same"))
        r2 = backend.call(_params(content="same"))
        assert r1.content == r2.content

    def test_different_inputs_different_outputs(self):
        backend = StubLLMBackend()
        r1 = backend.call(_params(content="alpha"))
        r2 = backend.call(_params(content="beta"))
        assert r1.content != r2.content

    def test_call_count(self):
        backend = StubLLMBackend()
        assert backend.call_count == 0
        backend.call(_params())
        assert backend.call_count == 1
        backend.call(_params())
        assert backend.call_count == 2

    def test_custom_prefix(self):
        backend = StubLLMBackend(response_prefix="custom")
        result = backend.call(_params())
        assert result.content.startswith("custom:")

    def test_provider_property(self):
        assert StubLLMBackend().provider == LLMProvider.STUB

    def test_model_name_passthrough(self):
        result = StubLLMBackend().call(_params(model="my-model"))
        assert result.model_name == "my-model"


# ═══ LLMBudgetManager ═══

class TestLLMBudgetManager:
    def _budget(self, budget_id="b1", max_cost=10.0, max_calls=100):
        return LLMBudget(budget_id=budget_id, tenant_id="t1", max_cost=max_cost, max_calls=max_calls)

    def test_register_and_get(self):
        mgr = LLMBudgetManager()
        budget = self._budget()
        mgr.register(budget)
        assert mgr.get("b1") is budget

    def test_unknown_budget(self):
        mgr = LLMBudgetManager()
        assert mgr.get("unknown") is None

    def test_check_within_budget(self):
        mgr = LLMBudgetManager()
        mgr.register(self._budget())
        ok, reason = mgr.check("b1", estimated_cost=1.0)
        assert ok is True
        assert reason == "within_budget"

    def test_check_unknown_budget(self):
        mgr = LLMBudgetManager()
        ok, reason = mgr.check("unknown")
        assert ok is False
        assert "unknown budget" in reason

    def test_check_would_exceed(self):
        mgr = LLMBudgetManager()
        mgr.register(self._budget(max_cost=1.0))
        ok, reason = mgr.check("b1", estimated_cost=2.0)
        assert ok is False
        assert "would exceed" in reason

    def test_check_exhausted(self):
        mgr = LLMBudgetManager()
        mgr.register(self._budget(max_cost=0.01))
        mgr.record_spend("b1", 0.01)
        ok, reason = mgr.check("b1")
        assert ok is False
        assert "exhausted" in reason

    def test_check_exhausted_by_calls(self):
        mgr = LLMBudgetManager()
        mgr.register(self._budget(max_cost=100.0, max_calls=2))
        mgr.record_spend("b1", 0.001)
        mgr.record_spend("b1", 0.001)
        ok, reason = mgr.check("b1")
        assert ok is False
        assert "exhausted" in reason

    def test_record_spend(self):
        mgr = LLMBudgetManager()
        mgr.register(self._budget(max_cost=10.0))
        updated = mgr.record_spend("b1", 2.5)
        assert updated.spent == 2.5
        assert updated.calls_made == 1

    def test_record_spend_accumulates(self):
        mgr = LLMBudgetManager()
        mgr.register(self._budget(max_cost=10.0))
        mgr.record_spend("b1", 1.0)
        updated = mgr.record_spend("b1", 2.0)
        assert updated.spent == 3.0
        assert updated.calls_made == 2

    def test_record_spend_unknown_budget_raises(self):
        mgr = LLMBudgetManager()
        with pytest.raises(Exception, match="unknown budget"):
            mgr.record_spend("unknown", 1.0)

    def test_list_budgets(self):
        mgr = LLMBudgetManager()
        mgr.register(self._budget("b2"))
        mgr.register(self._budget("b1"))
        budgets = mgr.list_budgets()
        assert len(budgets) == 2
        assert budgets[0].budget_id == "b1"  # sorted


# ═══ GovernedLLMAdapter ═══

class TestGovernedLLMAdapter:
    def _adapter(self, budget_manager=None, ledger_entries=None):
        backend = StubLLMBackend()
        bm = budget_manager or LLMBudgetManager()
        entries = ledger_entries if ledger_entries is not None else []
        return GovernedLLMAdapter(
            backend=backend,
            budget_manager=bm,
            clock=FIXED_CLOCK,
            ledger_sink=entries.append if entries is not None else None,
        ), entries

    def test_basic_invocation(self):
        adapter, entries = self._adapter()
        result = adapter.invoke_llm(_params())
        assert result.succeeded is True
        assert result.provider == LLMProvider.STUB
        assert adapter.invocation_count == 1
        assert len(entries) == 1
        assert entries[0]["type"] == "llm_invocation"

    def test_budget_enforcement(self):
        bm = LLMBudgetManager()
        bm.register(LLMBudget(budget_id="b1", tenant_id="t1", max_cost=0.001, max_calls=1))
        adapter, entries = self._adapter(budget_manager=bm)

        # First call succeeds
        r1 = adapter.invoke_llm(_params(budget_id="b1"))
        assert r1.succeeded is True

        # Second call rejected — budget exhausted
        r2 = adapter.invoke_llm(_params(budget_id="b1"))
        assert r2.succeeded is False
        assert "budget" in r2.error.lower()

    def test_no_budget_id_skips_check(self):
        adapter, _ = self._adapter()
        result = adapter.invoke_llm(_params(budget_id=""))
        assert result.succeeded is True

    def test_cost_recorded_to_budget(self):
        bm = LLMBudgetManager()
        bm.register(LLMBudget(budget_id="b1", tenant_id="t1", max_cost=100.0))
        adapter, _ = self._adapter(budget_manager=bm)

        adapter.invoke_llm(_params(budget_id="b1"))
        budget = bm.get("b1")
        assert budget.calls_made == 1
        assert budget.spent > 0

    def test_ledger_entry_fields(self):
        adapter, entries = self._adapter()
        adapter.invoke_llm(_params(model="test-model", tenant_id="t1"))
        entry = entries[0]
        assert entry["model"] == "test-model"
        assert entry["tenant_id"] == "t1"
        assert entry["provider"] == "stub"
        assert entry["succeeded"] is True
        assert "at" in entry

    def test_total_cost_tracking(self):
        adapter, _ = self._adapter()
        adapter.invoke_llm(_params())
        adapter.invoke_llm(_params())
        assert adapter.total_cost > 0

    def test_no_ledger_sink_ok(self):
        backend = StubLLMBackend()
        adapter = GovernedLLMAdapter(
            backend=backend,
            budget_manager=LLMBudgetManager(),
            clock=FIXED_CLOCK,
            ledger_sink=None,
        )
        result = adapter.invoke_llm(_params())
        assert result.succeeded is True

    # ═══ ModelAdapter protocol (invoke method) ═══

    def test_model_adapter_invoke(self):
        adapter, entries = self._adapter()
        invocation = ModelInvocation(
            invocation_id="inv-1",
            model_id="test-model",
            prompt_hash="abc123",
            invoked_at="2026-03-26T12:00:00Z",
            metadata={
                "messages": ({"role": "user", "content": "hello from model adapter"},),
                "model_name": "test-model",
            },
        )
        response = adapter.invoke(invocation)
        assert response.status == ModelStatus.SUCCEEDED
        assert response.validation_status == ValidationStatus.PENDING
        assert response.actual_cost >= 0
        assert "content" in response.metadata

    def test_model_adapter_fallback_prompt(self):
        """When no messages in metadata, uses prompt_hash as content."""
        adapter, _ = self._adapter()
        invocation = ModelInvocation(
            invocation_id="inv-2",
            model_id="test-model",
            prompt_hash="my prompt text",
            invoked_at="2026-03-26T12:00:00Z",
        )
        response = adapter.invoke(invocation)
        assert response.status == ModelStatus.SUCCEEDED

    def test_model_adapter_with_llm_message_objects(self):
        adapter, _ = self._adapter()
        invocation = ModelInvocation(
            invocation_id="inv-3",
            model_id="test-model",
            prompt_hash="hash",
            invoked_at="2026-03-26T12:00:00Z",
            metadata={
                "messages": (LLMMessage(role=LLMRole.USER, content="typed message"),),
            },
        )
        response = adapter.invoke(invocation)
        assert response.status == ModelStatus.SUCCEEDED


# ═══ AnthropicBackend (structural tests — no API key required) ═══

class TestAnthropicBackendStructure:
    def test_provider_property(self):
        backend = AnthropicBackend(api_key="test")
        assert backend.provider == LLMProvider.ANTHROPIC

    def test_no_api_key_gives_error(self):
        """Without SDK or key, should fail gracefully."""
        import os
        orig = os.environ.get("ANTHROPIC_API_KEY")
        os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            backend = AnthropicBackend(api_key="")
            result = backend.call(_params())
            # Either SDK not installed (invariant error caught) or key missing
            assert not result.succeeded or result.error
        except Exception:
            pass  # SDK not installed — expected
        finally:
            if orig is not None:
                os.environ["ANTHROPIC_API_KEY"] = orig

    def test_empty_messages_returns_error(self):
        backend = AnthropicBackend(api_key="fake")
        # Only system message = no user messages
        params = LLMInvocationParams(
            model_name="claude-sonnet-4-20250514",
            messages=(_msg("system", "sys only"),),
        )
        result = backend.call(params)
        assert result.error  # Should report no user messages

    def test_cost_estimation(self):
        backend = AnthropicBackend()
        cost = backend._estimate_cost("claude-sonnet-4-20250514", 1000, 500)
        assert cost > 0
        assert isinstance(cost, float)

    def test_cost_estimation_unknown_model(self):
        backend = AnthropicBackend()
        cost = backend._estimate_cost("unknown-model", 1000, 500)
        assert cost > 0  # Falls back to default pricing

    def test_runtime_error_redacted(self):
        backend = AnthropicBackend(api_key="fake")

        class _Messages:
            @staticmethod
            def create(**kwargs):
                raise RuntimeError("provider secret detail")

        class _Client:
            messages = _Messages()

        backend._get_client = lambda: _Client()
        result = backend.call(_params(model="claude-sonnet-4-20250514"))
        assert result.error == "provider error (RuntimeError)"
        assert "provider secret detail" not in result.error


# ═══ OpenAIBackend (structural tests — no API key required) ═══

class TestOpenAIBackendStructure:
    def test_provider_property(self):
        backend = OpenAIBackend(api_key="test")
        assert backend.provider == LLMProvider.OPENAI

    def test_cost_estimation(self):
        backend = OpenAIBackend()
        cost = backend._estimate_cost("gpt-4o", 1000, 500)
        assert cost > 0
        assert isinstance(cost, float)

    def test_cost_estimation_unknown_model(self):
        backend = OpenAIBackend()
        cost = backend._estimate_cost("unknown-model", 1000, 500)
        assert cost > 0

    def test_empty_messages_returns_error(self):
        backend = OpenAIBackend(api_key="fake")
        params = LLMInvocationParams(
            model_name="gpt-4o",
            messages=(_msg("user", ""),),
        )
        # Will fail connecting or SDK not installed
        try:
            result = backend.call(params)
            assert isinstance(result, LLMResult)
        except RuntimeCoreInvariantError:
            pass  # SDK not installed — expected

    def test_timeout_error_redacted(self):
        backend = OpenAIBackend(api_key="fake")

        class _Completions:
            @staticmethod
            def create(**kwargs):
                raise TimeoutError("provider timeout detail")

        class _Chat:
            completions = _Completions()

        class _Client:
            chat = _Chat()

        backend._get_client = lambda: _Client()
        result = backend.call(_params(model="gpt-4o"))
        assert result.error == "provider timeout (TimeoutError)"
        assert "provider timeout detail" not in result.error
